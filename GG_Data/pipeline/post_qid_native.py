"""Reuse named full records, or explicitly acquire missing records from Wikidata.

Local reuse does not call a network client. File order is whole-record priority;
records from different sources are never merged. Event discovery remains a
separate completeness obligation even when all required records are available.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import ijson

from GG_Data.pipeline.entities import native_record
from GG_Data.pipeline.poc import digest


def _open(path: Path):
    return gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")


def _source(path: Path) -> dict:
    if any(
        word in path.parent.name.lower() or word in path.name.lower()
        for word in ("filtered", "partial", "event")
    ):
        raise ValueError(
            f"Cannot use filtered/event/partial cache as full source: {path}"
        )
    if not path.is_file():
        raise FileNotFoundError(path)
    snapshot = path.parent / "table_snapshot.json"
    source = dict(
        provider="LOCAL_FULL_NATIVE_CACHE",
        file=str(path.resolve()),
        sha256=digest(path),
        snapshot_at=None,
        retrieved_at=None,
    )
    if snapshot.is_file():
        source["snapshot_at"] = json.loads(snapshot.read_text(encoding="utf-8")).get(
            "snapshot_at"
        )
    return source


def _records(path: Path, source: dict):
    """Stream supported exports, not recursive cache-directory discovery."""
    with _open(path) as stream:
        first = next(ijson.parse(stream), None)
    if first == ("", "start_array", None):
        if path.name not in {"full_records.json", "full_records.json.gz"}:
            raise ValueError(f"Expected named full_records export: {path}")
        with _open(path) as stream:
            yield from (
                (None, row) for row in ijson.items(stream, "item", use_float=True)
            )
        return
    if first != ("", "start_map", None):
        raise ValueError(f"Expected full-record object/list: {path}")
    with _open(path) as stream:
        key = next(
            (
                value
                for prefix, event, value in ijson.parse(stream)
                if prefix == "" and event == "map_key"
            ),
            None,
        )
    if key is None or re.fullmatch(r"Q[1-9]\d*", key):
        if path.name not in {"full_records.json", "full_records.json.gz"}:
            raise ValueError(f"Expected named full_records export: {path}")
        with _open(path) as stream:
            yield from ijson.kvitems(stream, "", use_float=True)
        return
    sql_path = path.with_suffix("") if path.suffix == ".gz" else path
    sql_path = sql_path.with_suffix(".sql")
    sql = sql_path.read_text(encoding="utf-8") if sql_path.is_file() else ""
    # The inspected legacy cache uses this complete full-item membership query.
    if not re.fullmatch(
        r"\s*SELECT\s+id\s*,\s*item\s+FROM\s+`[^`]+`"
        r"(?:\s+AS\s+\w+)?(?:\s+FOR\s+SYSTEM_TIME\s+AS\s+OF\s+TIMESTAMP\s+'[^']+')?"
        r"\s+WHERE\s+numeric_id\s+IN\s*\([\d,\s]+\)"
        r"\s+AND\s+STARTS_WITH\(id,\s*'Q'\)\s*;?\s*",
        sql,
        re.IGNORECASE,
    ):
        raise ValueError(f"No complete full-item query proof: {path}")
    source["sql_file"] = str(sql_path.resolve())
    source["sql_sha256"] = digest(sql_path)
    with _open(path) as stream:
        source["retrieved_at"] = next(ijson.items(stream, "retrieved_at"), None)
    with _open(path) as stream:
        for row in ijson.items(stream, "rows.item", use_float=True):
            yield row["id"], {
                "requested_qid": row["id"],
                "entity": json.loads(row["item"].rstrip(",\n\r ")),
            }


def reuse_native(required_qids: set[str], cache_paths: list[Path]) -> dict:
    """Return required envelopes, source evidence and the exact missing set."""
    if any(
        not isinstance(q, str) or not re.fullmatch(r"Q[1-9]\d*", q)
        for q in required_qids
    ):
        raise ValueError("Required IDs must be QIDs")
    records, sources, inventory = {}, {}, []
    for priority, raw_path in enumerate(cache_paths):
        path = Path(raw_path)
        source = _source(path)
        seen, selected, available = set(), 0, 0
        for key, row in _records(path, source):
            if not isinstance(row, dict):
                raise ValueError(f"Invalid full-record row: {path}")
            envelope = (
                row
                if "entity" in row
                else {"requested_qid": key or row.get("id"), "entity": row}
            )
            qid = envelope.get("requested_qid")
            if key is not None and qid != key:
                raise ValueError(f"Full export key ID differs: {key}")
            if qid not in required_qids:
                continue
            full = native_record(envelope, qid)
            if not isinstance(full["claims"], dict):
                raise ValueError(f"Full native claims must be an object: {qid}")
            if qid in seen:
                raise ValueError(f"Duplicate full record within cache: {qid}")
            seen.add(qid)
            available += 1
            if qid not in records:
                records[qid] = envelope
                sources[qid] = dict(
                    source,
                    record_id=qid,
                    cache_priority=priority,
                    native_modified=full.get("modified"),
                    native_revision=full.get("lastrevid"),
                )
                selected += 1
        inventory.append(
            dict(source, required_available=available, selected_records=selected)
        )
        if digest(path) != source["sha256"]:
            raise ValueError(f"Native cache changed during read: {path}")
    missing = sorted(required_qids - records.keys())
    return dict(
        status=(
            "MISSING_NATIVE_RECORDS" if missing else "REQUIRED_NATIVE_RECORDS_AVAILABLE"
        ),
        records=records,
        sources=sources,
        missing=missing,
        counts=dict(
            required=len(required_qids), reused=len(records), missing=len(missing)
        ),
        caches=inventory,
        selection_policy="FIRST_EXPLICIT_CACHE_WHOLE_RECORD",
        event_discovery_completeness="NOT_ESTABLISHED",
    )


def acquire_api(
    missing_qids: set[str], output: Path, *, batch_size: int = 50, session=None
) -> dict:
    """Acquire full current records; retain every attempt and explicit failure.

    Only HTTP 429/503 retry, at most three attempts, with waits capped at 30 s.
    No languages filter, redirect reassignment, source merge or hidden retry.
    """
    import requests

    if any(
        not isinstance(q, str) or not re.fullmatch(r"Q[1-9]\d*", q)
        for q in missing_qids
    ):
        raise ValueError("Missing IDs must be QIDs")
    if type(batch_size) is not int or not 1 <= batch_size <= 50:
        raise ValueError("API batch size must be from 1 to 50")
    output.mkdir(parents=True, exist_ok=False)
    endpoint = "https://www.wikidata.org/w/api.php"
    client = session if session is not None else requests.Session()
    records, sources, failures, attempts = {}, {}, {}, []
    requested = sorted(missing_qids, key=lambda q: int(q[1:]))
    try:
        for offset in range(0, len(requested), batch_size):
            batch = requested[offset : offset + batch_size]
            params = dict(
                action="wbgetentities",
                format="json",
                formatversion=2,
                props="info|labels|descriptions|aliases|sitelinks|claims",
                ids="|".join(batch),
            )
            reason, data, final_evidence = "NO_VALID_RESPONSE", None, None
            for attempt in range(1, 4):
                prefix = f"batch_{offset // batch_size:05d}_attempt_{attempt}"
                evidence = dict(
                    endpoint=endpoint,
                    params=params,
                    requested_ids=batch,
                    attempt=attempt,
                    retrieval_utc=datetime.now(timezone.utc).isoformat(),
                    timeout_seconds=30,
                )
                raw_path = output / f"{prefix}.response.body"
                try:
                    response = client.get(
                        endpoint,
                        params=params,
                        timeout=30,
                        headers={
                            "User-Agent": "GeoAI-research-native-records/1.0 (explicit bounded acquisition)"
                        },
                    )
                    raw_path.write_bytes(response.content)
                    evidence.update(
                        raw_file=str(raw_path.resolve()),
                        sha256=digest(raw_path),
                        http_status=response.status_code,
                        response_url=getattr(response, "url", endpoint),
                        retry_after=response.headers.get("Retry-After"),
                    )
                    reason = f"HTTP_{response.status_code}"
                    if response.status_code in (429, 503) and attempt < 3:
                        delay = 2 ** (attempt - 1)
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                try:
                                    delay = (
                                        parsedate_to_datetime(retry_after)
                                        - datetime.now(timezone.utc)
                                    ).total_seconds()
                                except (ValueError, TypeError, OverflowError):
                                    pass
                        delay = min(30, max(0, delay))
                        evidence["retry_wait_seconds"] = delay
                    else:
                        delay = None
                    if response.status_code == 200:
                        data = json.loads(response.content)
                        if (
                            not isinstance(data, dict)
                            or data.get("error")
                            or not isinstance(data.get("entities"), dict)
                        ):
                            raise ValueError(
                                "API response lacks complete entity object or contains an error"
                            )
                        if not data["entities"].keys() <= set(batch):
                            raise ValueError(
                                "API returned unrequested or redirected record IDs"
                            )
                        final_evidence = evidence
                except (
                    requests.RequestException,
                    TimeoutError,
                    OSError,
                    ValueError,
                    TypeError,
                ) as exc:
                    evidence.update(error_type=type(exc).__name__, error=str(exc))
                    reason = f"{type(exc).__name__}: {exc}"
                    delay, data = None, None
                attempts.append(evidence)
                (output / f"{prefix}.request.json").write_text(
                    json.dumps(evidence, indent=2), encoding="utf-8"
                )
                if delay is None:
                    break
                time.sleep(delay)
            for qid in batch:
                try:
                    if data is None or final_evidence is None:
                        raise ValueError(reason)
                    entity = data["entities"].get(qid)
                    if not isinstance(entity, dict):
                        raise ValueError("Requested QID is absent from response")
                    envelope = dict(requested_qid=qid, entity=entity)
                    full = native_record(envelope, qid)
                    if (
                        not isinstance(full["claims"], dict)
                        or type(full.get("lastrevid")) is not int
                        or full["lastrevid"] <= 0
                        or not isinstance(full.get("modified"), str)
                        or not full["modified"]
                    ):
                        raise ValueError(
                            "Full native claims/revision/modified metadata is missing or invalid"
                        )
                    for field in ("labels", "descriptions", "aliases", "sitelinks"):
                        if not isinstance(full.get(field), dict):
                            raise ValueError(
                                f"Full native {field} is missing or invalid"
                            )
                    records[qid] = envelope
                    sources[qid] = dict(
                        provider="WIKIDATA_API",
                        record_id=qid,
                        file=final_evidence["raw_file"],
                        sha256=final_evidence["sha256"],
                        endpoint=endpoint,
                        params=params,
                        retrieved_at=final_evidence["retrieval_utc"],
                        snapshot_at=None,
                        temporal_basis="CURRENT_WIKIDATA_API_NOT_PINNED_DUMP",
                        native_modified=full["modified"],
                        native_revision=full["lastrevid"],
                    )
                except (KeyError, ValueError, TypeError) as exc:
                    failures[qid] = dict(
                        qid=qid, reason=str(exc), last_attempt=attempts[-1]
                    )
    finally:
        if session is None:
            client.close()
    missing = sorted(missing_qids - records.keys(), key=lambda q: int(q[1:]))
    with gzip.open(output / "full_records.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False, allow_nan=False)
    (output / "sources.json").write_text(
        json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    receipt = dict(
        status=(
            "MISSING_NATIVE_RECORDS" if missing else "REQUIRED_NATIVE_RECORDS_AVAILABLE"
        ),
        requested_ids=requested,
        missing=missing,
        failures=[failures[q] for q in missing],
        attempts=attempts,
        counts=dict(
            required=len(requested), acquired=len(records), missing=len(missing)
        ),
        event_discovery_completeness="NOT_ESTABLISHED",
        selection_policy="CURRENT_API_WHOLE_RECORD_NO_MERGE",
        outputs={
            name: digest(output / name)
            for name in ("full_records.json.gz", "sources.json")
        },
    )
    (output / "receipt.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    return receipt


def _history(raw: dict, qid: str) -> tuple[dict, dict]:
    """Validate the complete saved window before selecting one original record."""
    try:
        if not re.fullmatch(r"Q[1-9]\d*", qid) or raw.get("error"):
            raise ValueError("Invalid history identity or API error")
        pages = raw["query"]["pages"]
        if len(pages) != 1 or pages[0]["title"] != qid or pages[0]["ns"] != 0:
            raise ValueError("History page differs from requested original QID")
        revisions = pages[0]["revisions"]
        if not isinstance(revisions, list) or not 1 <= len(revisions) <= 5:
            raise ValueError("Missing history revisions")
        previous_id, previous_time = None, None
        selected, skipped = None, []
        for revision in revisions:
            number, timestamp = revision["revid"], revision["timestamp"]
            instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if (
                type(number) is not int
                or number <= 0
                or instant.tzinfo is None
                or (previous_id is not None and number >= previous_id)
                or (previous_time is not None and instant > previous_time)
            ):
                raise ValueError("History revision order or metadata is invalid")
            previous_id, previous_time = number, instant
            slot = revision["slots"]["main"]
            if (
                slot["contentmodel"] != "wikibase-item"
                or slot["contentformat"] != "application/json"
            ):
                raise ValueError("Expected full Wikibase JSON history content")
            entity = json.loads(slot["content"])
            if "redirect" in entity:
                if (
                    entity.get("entity") != qid
                    or not re.fullmatch(r"Q[1-9]\d*", entity["redirect"])
                    or entity["redirect"] == qid
                ):
                    raise ValueError("Invalid original-QID redirect evidence")
                reason = "REDIRECT"
            else:
                if (
                    entity.get("id") != qid
                    or entity.get("type") != "item"
                    or "missing" in entity
                ):
                    raise ValueError(
                        "History content has a different original identity"
                    )
                for field in (
                    "claims",
                    "labels",
                    "descriptions",
                    "aliases",
                    "sitelinks",
                ):
                    # MediaWiki serializes cleared merge maps as []. Such
                    # rows may be skipped, but never selected as full data.
                    if not isinstance(entity.get(field), dict) and not (
                        entity.get("claims") == [] and entity.get(field) == []
                    ):
                        raise ValueError(f"Missing full historical {field}")
                reason = "EMPTY_CLAIMS" if not entity["claims"] else None
            if selected is None:
                if reason:
                    skipped.append(
                        dict(revid=number, timestamp=timestamp, reason=reason)
                    )
                else:
                    entity = dict(entity, lastrevid=number, modified=timestamp)
                    selected = dict(requested_qid=qid, entity=entity)
        if selected is None:
            raise ValueError("No full nonempty original entity in saved history")
        return selected, dict(
            native_revision=selected["entity"]["lastrevid"],
            native_modified=selected["entity"]["modified"],
            derived_info_fields={
                "lastrevid": "MediaWiki.revid",
                "modified": "MediaWiki.timestamp",
            },
            selection_policy="LATEST_NONEMPTY_ORIGINAL_ENTITY_BEFORE_REDIRECT_OR_MERGE",
            skipped_newer_revisions=skipped,
        )
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError("Malformed or missing full history evidence") from exc


def historical_record(raw: dict, qid: str) -> dict:
    """Return the latest full original entity in a saved newest-first window."""
    return _history(raw, qid)[0]


def historical_selection(raw: dict, qid: str) -> dict:
    """Return explicit revision derivation and skipped newer history evidence."""
    return _history(raw, qid)[1]


def complete_api_history(api_dir: Path, history_dir: Path, output: Path) -> dict:
    """Complete a failed acquisition from saved history only; never fetch."""
    if output.exists():
        raise FileExistsError(output)

    def read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    receipt_path = api_dir / "receipt.json"
    receipt_sha = digest(receipt_path)
    receipt = read(receipt_path)
    for filename, expected in receipt.get("inputs", {}).items():
        if digest(Path(filename)) != expected:
            raise ValueError("Original acquisition input hash differs")
    for name, expected in receipt["outputs"].items():
        if Path(name).name != name or digest(api_dir / name) != expected:
            raise ValueError("Acquisition output hash differs")
    with gzip.open(api_dir / "full_records.json.gz", "rt", encoding="utf-8") as stream:
        records = json.load(stream)
    sources = read(api_dir / "sources.json")
    requested, missing = receipt["requested_ids"], receipt["missing"]
    failures = {r["qid"]: r for r in receipt["failures"]}
    if (
        receipt["status"] != "MISSING_NATIVE_RECORDS"
        or not missing
        or len(set(requested)) != len(requested)
        or len(set(missing)) != len(missing)
        or len(failures) != len(receipt["failures"])
        or set(failures) != set(missing)
        or records.keys() != sources.keys()
        or records.keys() & set(missing)
        or records.keys() | set(missing) != set(requested)
        or receipt["counts"]
        != dict(required=len(requested), acquired=len(records), missing=len(missing))
    ):
        raise ValueError("Failed acquisition scope or failure accounting differs")
    inputs = {**receipt.get("inputs", {}), str(receipt_path.resolve()): receipt_sha}
    # Bind every unchanged current record to its saved raw API response/request.
    raw_cache, request_cache, raw_hashes = {}, {}, {}
    for qid, envelope in records.items():
        native_record(envelope, qid)
        source = sources[qid]
        raw_path = Path(source["file"])
        request_path = raw_path.with_name(
            raw_path.name.replace(".response.body", ".request.json")
        )
        key = str(raw_path.resolve())
        if key not in raw_hashes:
            raw_hashes[key] = digest(raw_path)
            raw_cache[key] = read(raw_path)
            request_cache[key] = read(request_path)
            inputs[str(request_path.resolve())] = digest(request_path)
        if raw_hashes[key] != source["sha256"]:
            raise ValueError("Current raw response hash differs")
        request = request_cache[key]
        if (
            request.get("sha256") != source["sha256"]
            or request.get("http_status") != 200
            or qid not in request["requested_ids"]
            or Path(request["raw_file"]).resolve() != raw_path.resolve()
            or request.get("params") != source.get("params")
        ):
            raise ValueError("Current request evidence differs")
        if raw_cache[key]["entities"].get(qid) != envelope["entity"]:
            raise ValueError("Current envelope differs from raw source")
        inputs[str(raw_path.resolve())] = source["sha256"]
    resolved = []
    for qid in missing:
        raw_path, request_path = (
            history_dir / f"{qid}.response.body",
            history_dir / f"{qid}.request.json",
        )
        request = read(request_path)
        raw_sha = digest(raw_path)
        params = request.get("params", {})
        expected_params = dict(
            action="query",
            format="json",
            formatversion=2,
            prop="revisions",
            titles=qid,
            rvslots="main",
            rvprop="ids|timestamp|content|contentmodel",
            rvlimit=5,
        )
        if (
            params != expected_params
            or request.get("sha256") != raw_sha
            or request.get("status") != 200
            or request.get("endpoint") != "https://www.wikidata.org/w/api.php"
            or datetime.fromisoformat(
                request["retrieved_at"].replace("Z", "+00:00")
            ).tzinfo
            is None
        ):
            raise ValueError("Historical request or raw response hash differs")
        raw = read(raw_path)
        records[qid] = historical_record(raw, qid)
        sources[qid] = dict(
            provider="WIKIDATA_API_HISTORICAL",
            record_id=qid,
            file=str(raw_path.resolve()),
            sha256=raw_sha,
            request_file=str(request_path.resolve()),
            request_sha256=digest(request_path),
            endpoint=request["endpoint"],
            params=params,
            retrieved_at=request["retrieved_at"],
            snapshot_at=None,
            temporal_basis="HISTORICAL_ORIGINAL_BEFORE_MERGE_NOT_CURRENT_API",
            **historical_selection(raw, qid),
        )
        inputs[str(raw_path.resolve())], inputs[str(request_path.resolve())] = (
            raw_sha,
            digest(request_path),
        )
        resolved.append(
            dict(
                original_failure=failures[qid],
                resolution="SAVED_FULL_ORIGINAL_HISTORY",
                native_revision=sources[qid]["native_revision"],
            )
        )
    if digest(receipt_path) != receipt_sha:
        raise ValueError("Original failed receipt changed")
    output.mkdir(parents=True, exist_ok=False)
    with gzip.open(output / "full_records.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False, allow_nan=False)
    (output / "sources.json").write_text(
        json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    completed = dict(
        status="REQUIRED_NATIVE_RECORDS_AVAILABLE",
        requested_ids=requested,
        missing=[],
        failures=[],
        counts=dict(required=len(requested), acquired=len(records), missing=0),
        inputs=inputs,
        original_failed_receipt=dict(
            file=str(receipt_path.resolve()), sha256=receipt_sha
        ),
        original_input_bindings=receipt.get("inputs", {}),
        resolved_failures=resolved,
        selection_policy="UNCHANGED_CURRENT_API_PLUS_HISTORICAL_ORIGINAL_QIDS_NO_MERGE",
        event_discovery_completeness="NOT_ESTABLISHED",
        outputs={
            name: digest(output / name)
            for name in ("full_records.json.gz", "sources.json")
        },
    )
    (output / "receipt.json").write_text(
        json.dumps(completed, indent=2), encoding="utf-8"
    )
    return completed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--required-ids", type=Path, required=True)
    parser.add_argument("--cache", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    required = json.loads(args.required_ids.read_text(encoding="utf-8"))
    if not isinstance(required, list) or len(required) != len(set(required)):
        raise ValueError("Required IDs file must be a unique JSON list")
    result = reuse_native(set(required), args.cache)
    args.output.mkdir(parents=True, exist_ok=False)
    with gzip.open(
        args.output / "full_records.json.gz", "wt", encoding="utf-8"
    ) as stream:
        json.dump(result.pop("records"), stream, ensure_ascii=False, allow_nan=False)
    (args.output / "sources.json").write_text(
        json.dumps(result.pop("sources"), indent=2), encoding="utf-8"
    )
    result["required_ids"] = dict(
        file=str(args.required_ids.resolve()), sha256=digest(args.required_ids)
    )
    result["outputs"] = {
        name: digest(args.output / name)
        for name in ("full_records.json.gz", "sources.json")
    }
    (args.output / "receipt.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
