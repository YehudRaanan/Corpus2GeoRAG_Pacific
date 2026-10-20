"""Current Wikidata acquisition: population S2T sections 1 and 7.

This adapter only retrieves source evidence. It never extracts Daniel mentions,
changes matching, or declares candidate events included in the data model.
"""

from __future__ import annotations

import hashlib
import gzip
import json
import logging
import math
import re
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
import ijson

from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.relations import ACCEPTED_ENTITIES_SHA, SourceException

EVENT_ROOT = "Q140451665"
QUERY_URL = "https://query.wikidata.org/sparql"
SCHOLARLY_QUERY_URL = "https://query-scholarly.wikidata.org/sparql"
LOG = logging.getLogger(__name__)
RETRY_HTTP_STATUS = {429, 502, 503, 504}
RETRY_WAITS = (10, 30)
REQUEST_PAUSE = 5
USER_AGENT = "GeoAI-Daniel-POC/1.0 (https://github.com/EtzionR/Corpus2GeoRAG_Pacific)"


def cache_path(store: Path, url: str, params: dict) -> Path:
    request = {"url": url, "params": params}
    key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    return store / key


def cached_json(store: Path, url: str, params: dict) -> tuple[dict, dict]:
    """Cache untouched responses and request evidence before interpreting them.

    S2T 7: the user approved three total attempts for connection failures and
    HTTP 429/502/503/504,
    with waits of at least 10/30 seconds and the server's Retry-After deadline.
    Existing failures count toward that budget. New requests pause five seconds.
    Attempts are append-only; all other failures still stop immediately.
    """
    request = {"url": url, "params": params}
    root = cache_path(store, url, params)
    for attempt in range(1, 4):
        directory = root if attempt == 1 else root / f"attempt_{attempt}"
        if directory.exists():
            metadata = directory / "request.json"
            body = directory / "response.json"
            if not metadata.exists():
                raise SourceException(
                    "Incomplete current Wikidata cache", cache=str(directory)
                )
            evidence = read_json(metadata)
            # Append-only annotation for the approved pre-policy connection
            # failure. Its original request receipt remains unchanged.
            annotation = directory / "connection_failure.json"
            if annotation.exists():
                note = read_json(annotation)
                if (
                    note["request_receipt_sha256"] != digest(metadata)
                    or note["connection_failure"] is not True
                ):
                    raise SourceException(
                        "Connection annotation mismatch", cache=str(directory)
                    )
                evidence = dict(evidence, connection_failure=True)
            if evidence["request"] != request or (
                body.exists() and digest(body) != evidence["sha256"]
            ):
                raise SourceException(
                    "Current Wikidata cache mismatch", cache=str(directory)
                )
            if not body.exists() and not (
                evidence["status"] == "FAILED"
                and evidence.get("connection_failure") is True
                and "http_status" not in evidence
                and "sha256" not in evidence
            ):
                raise SourceException(
                    "Incomplete current Wikidata cache", cache=str(directory)
                )
        else:
            try:
                return _request_json(directory, request)
            except SourceException as exc:
                evidence = exc.case
        if evidence["status"] == "OK":
            return read_json(body), evidence
        retryable = (
            evidence.get("http_status") in RETRY_HTTP_STATUS
            or evidence.get("connection_failure") is True
        )
        if not retryable or attempt == 3:
            raise SourceException(
                "Current Wikidata request failed",
                **{k: v for k, v in evidence.items() if k != "reason"},
            )
        # A saved later attempt is reused without another wait or network call.
        if not (root / f"attempt_{attempt + 1}").exists():
            delay = retry_delay(evidence, attempt, datetime.now(timezone.utc))
            LOG.warning(
                "Wikidata %s; attempt %s/3 after %ss",
                evidence.get("http_status", "connection failure"),
                attempt + 1,
                delay,
            )
            # Short sleeps keep a long server cooldown observable/interruption-safe.
            while delay > 0:
                step = min(delay, 30)
                time.sleep(step)
                delay -= step
                if delay:
                    LOG.info("Wikidata retry wait: %ss remaining", delay)
    raise AssertionError("Unreachable retry state")


def retry_delay(evidence: dict, attempt: int, now: datetime) -> int:
    """Respect both forms of Retry-After, including when resuming saved failures.

    A seconds value runs from response receipt; an HTTP date is an absolute
    deadline. Reopening the cache never resets the attempt count or cooldown.
    """
    headers = {k.lower(): v for k, v in evidence.get("response_headers", {}).items()}
    value = headers.get("retry-after")
    delay = RETRY_WAITS[attempt - 1]
    if value is None:
        return delay
    try:
        if re.fullmatch(r"\d+", value.strip()):
            received = datetime.fromisoformat(evidence["retrieved_at"])
            remaining = int(value) - (now - received).total_seconds()
        else:
            deadline = parsedate_to_datetime(value)
            remaining = (deadline - now).total_seconds()
        return max(delay, math.ceil(remaining))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise SourceException(
            "Invalid Retry-After evidence", cache=evidence["cache"]
        ) from exc


def _request_json(directory: Path, request: dict) -> tuple[dict, dict]:
    """Save one untouched attempt before the caller applies the retry policy."""
    metadata = directory / "request.json"
    body = directory / "response.json"
    directory.mkdir(parents=True)
    evidence = {
        "request": request,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAILED",
        "cache": str(directory),
    }
    try:
        # Single polite reader; this helper makes exactly one request.
        time.sleep(REQUEST_PAUSE)
        response = requests.get(
            request["url"],
            params=request["params"],
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=45,
            allow_redirects=False,
        )
        body.write_bytes(response.content)
        evidence.update(
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            http_status=response.status_code,
            response_headers=dict(response.headers),
            sha256=digest(body),
        )
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError("Unexpected source redirect")
        data = response.json()
        if not isinstance(data, dict) or "error" in data or "errors" in data:
            raise ValueError("Unexpected Wikidata JSON or API error")
        evidence["status"] = "OK"
    except (requests.RequestException, ValueError) as exc:
        evidence["error"] = str(exc)
        # The approved extension covers connections only. Read/connect
        # timeouts, TLS validation and malformed source data still stop.
        if isinstance(exc, requests.exceptions.ConnectionError) and not isinstance(
            exc, (requests.exceptions.SSLError, requests.exceptions.Timeout)
        ):
            evidence["connection_failure"] = True
        raise SourceException("Current Wikidata request failed", **evidence) from exc
    finally:
        metadata.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return data, evidence


def incoming_query(qid: str) -> str:
    """Approved smaller requests: retrieve incoming links for one Daniel QID.

    S2T 7 still requires both directions and all ranks. Outgoing links come from
    the complete native record; incoming links use full statements, without a
    hierarchy join or LIMIT. Neither step establishes Event membership.
    """
    if not re.fullmatch(r"Q[1-9]\d*", qid):
        raise ValueError("Expected a native Daniel QID")
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT DISTINCT ?subject ?statement ?property ?rank WHERE {{
  ?statement ?statementProperty wd:{qid} .
  ?property wikibase:claim ?claim ;
            wikibase:statementProperty ?statementProperty .
  ?subject ?claim ?statement .
  ?statement wikibase:rank ?rank .
  FILTER(STRSTARTS(STR(?subject), "http://www.wikidata.org/entity/Q"))
}}
"""


def incoming_page_query(
    qid: str,
    after: str | None = None,
    size: int = 5000,
    *,
    property_id: str | None = None,
) -> str:
    """Page the same full assertions; never cap the Event discovery population.

    Continuation approved after the Canada stop: order by native statement URI
    and advance only after a complete validated page. No OFFSET or hierarchy
    join is added. Existing failed unpaged responses remain untouched.
    """
    if type(size) is not int or not 1 <= size <= 5000:
        raise ValueError("Expected a page size from 1 through 5000")
    cursor = ""
    if after is not None:
        if not re.fullmatch(
            r"http://www.wikidata.org/entity/statement/[Qq][1-9]\d*-[0-9a-fA-F-]+",
            after,
        ):
            raise ValueError("Expected a native statement URI cursor")
        cursor = f"  FILTER(STR(?statement) > {json.dumps(after)})\n"
    query = incoming_query(qid)
    if property_id is not None:
        # Approved retrieval test: bind one native property in both p/ps joins.
        # This partitions requests, not the eligible Event/relation population.
        if not re.fullmatch(r"P[1-9]\d*", property_id):
            raise ValueError("Expected a native Wikidata property ID")
        query = f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT DISTINCT ?subject ?statement ?property ?rank WHERE {{
  ?statement ps:{property_id} wd:{qid} .
  ?subject p:{property_id} ?statement .
  ?statement wikibase:rank ?rank .
  BIND(wd:{property_id} AS ?property)
  FILTER(STRSTARTS(STR(?subject), "http://www.wikidata.org/entity/Q"))
}}
"""
    return (
        query.rstrip()[:-1] + cursor + f"}}\nORDER BY STR(?statement)\nLIMIT {size}\n"
    )


def current_record(store: Path, qid: str) -> tuple[dict, dict]:
    """Retrieve the complete native JSON; never redirect or project claims."""
    if not re.fullmatch(r"Q[1-9]\d*", qid):
        raise ValueError("Expected a native QID")
    data, evidence = cached_json(
        store, f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json", {}
    )
    return native_records(data, [qid], evidence)[qid], evidence


def native_records(data: dict, qids: list[str], evidence: dict) -> dict[str, dict]:
    """An omitted, missing or redirected ID is a source stop, never no links."""
    records = data.get("entities", {})
    if (
        not isinstance(records, dict)
        or set(records) != set(qids)
        or "redirects" in data
        or data.get("warnings")
    ):
        raise SourceException(
            "Unexpected native record population",
            qids=qids,
            returned_qids=list(records) if isinstance(records, dict) else None,
            warnings=data.get("warnings"),
            source=evidence,
        )
    for qid, record in records.items():
        if (
            record.get("id") != qid
            or record.get("type") != "item"
            or any(k in record for k in ("missing", "redirect", "redirects"))
            or not isinstance(record.get("claims"), dict)
            or not isinstance(record.get("lastrevid"), int)
            or not record.get("modified")
        ):
            raise SourceException(
                "Unexpected current native record", qid=qid, source=evidence
            )
    return records


def current_records(
    store: Path, qids: list[str], saved_entities: Path | None = None
) -> Iterator[tuple[dict[str, dict], dict]]:
    """S2T 7: approved native batches, full records and explicit no redirects.

    Reuse verified Special:EntityData entries first, then stable batches of at
    most 50. Raw API wrappers stay in the shared evidence cache. No claim/rank
    or language projection is applied; repeat runs reuse the same batch keys.
    """
    if (
        not qids
        or len(qids) != len(set(qids))
        or any(not re.fullmatch(r"Q[1-9]\d*", qid) for qid in qids)
    ):
        raise ValueError("Expected distinct native QIDs")
    pending = []
    for qid in sorted(qids, key=lambda q: int(q[1:])):
        url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
        if cache_path(store, url, {}).exists():
            record, evidence = current_record(store, qid)
            yield {qid: record}, evidence
        else:
            pending.append(qid)
    for offset in range(0, len(pending), 50):
        yield from _current_batch(
            store, pending[offset : offset + 50], saved_entities=saved_entities
        )


def saved_native_records(path: Path, qids: set[str]) -> tuple[dict, list[dict]]:
    """S2T 7: approved missing-current fallback, preserving original QIDs.

    Read only the accepted Entities artifact. Preserve its native revision/date;
    never search for another entity or overwrite the missing-current response.
    """
    manifest_path = path.parent / "manifest.json"
    manifest = read_json(manifest_path)
    sha = digest(path)
    if (
        digest(manifest_path) != ACCEPTED_ENTITIES_SHA
        or sha != manifest["outputs"][path.name]
    ):
        raise SourceException("Saved native fallback checksum mismatch", file=str(path))
    found = {}
    with gzip.open(path, "rb") as stream:
        for row in ijson.items(stream, "item", use_float=True):
            qid = row["entity_id"]
            if qid not in qids:
                continue
            record = row["raw_reference"]["full"]["entity"]
            native_records({"entities": {qid: record}}, [qid], {})
            if qid in found and found[qid] != record:
                raise SourceException(
                    "Conflicting saved native fallback records", qid=qid
                )
            found[qid] = record
    if set(found) != qids:
        raise SourceException(
            "Saved native fallback unavailable", missing=sorted(qids - set(found))
        )
    lineage = [
        dict(
            qid=qid,
            reason="CURRENT_API_MARKS_MISSING",
            file=str(path),
            sha256=sha,
            manifest_sha256=ACCEPTED_ENTITIES_SHA,
            revision=r["lastrevid"],
            modified=r["modified"],
        )
        for qid, r in found.items()
    ]
    return found, lineage


def _current_batch(
    store: Path,
    batch: list[str],
    oversized: tuple[dict, ...] = (),
    saved_entities: Path | None = None,
) -> Iterator[tuple[dict[str, dict], dict]]:
    """S2T 7: split only explicit response-size truncations, approved 20 October.

    Preserve the parent response; never accept its partial records. Each child
    must return all requested IDs. A one-ID truncation or any other warning,
    malformed response, ID change or unapproved service error still stops.
    """
    data, evidence = cached_json(
        store,
        "https://www.wikidata.org/w/api.php",
        {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "redirects": "no",
            "format": "json",
        },
    )
    warning = data.get("warnings", {}).get("result", {}).get("*", "")
    if re.fullmatch(
        r"This result was truncated because it would otherwise be larger than the limit of [\d,]+ bytes\.",
        warning,
    ):
        if len(batch) == 1:
            raise SourceException(
                "Single native record exceeds API size limit",
                qid=batch[0],
                source=evidence,
            )
        middle = len(batch) // 2
        LOG.warning(
            "Splitting oversized native batch: %s into %s + %s",
            len(batch),
            middle,
            len(batch) - middle,
        )
        parents = oversized + (
            dict(
                cache=evidence["cache"],
                sha256=evidence["sha256"],
                qids=batch,
                warning=warning,
            ),
        )
        yield from _current_batch(store, batch[:middle], parents, saved_entities)
        yield from _current_batch(store, batch[middle:], parents, saved_entities)
    else:
        fallbacks = []
        entities = data.get("entities", {})
        # Only explicit missing markers qualify. Omitted IDs, redirects or other
        # malformed records still fail the unchanged native-record validation.
        if (
            saved_entities is not None
            and isinstance(entities, dict)
            and set(entities) == set(batch)
        ):
            missing = {
                qid for qid, r in entities.items() if r == {"id": qid, "missing": ""}
            }
            if missing:
                saved, fallbacks = saved_native_records(saved_entities, missing)
                data = dict(data, entities={**entities, **saved})
                LOG.warning(
                    "Using approved saved native records for missing IDs: %s",
                    ", ".join(sorted(missing)),
                )
        records = native_records(data, batch, evidence)
        yield records, dict(
            evidence,
            oversized_ancestors=list(oversized),
            saved_record_fallbacks=fallbacks,
        )


def incoming_candidates_query(subjects: list[str], candidates: list[str]) -> str:
    """S2T 7: approved bounded retrieval after the incomplete World War II reply.

    Restrict to the frozen Daniel population before downloading. Every direct
    statement/rank between these subjects and candidate targets remains eligible;
    this changes acquisition size, not Event inclusion or mapping.
    """
    if (
        not 1 <= len(subjects) <= 250
        or not 1 <= len(candidates) <= 7
        or len(subjects) != len(set(subjects))
        or len(candidates) != len(set(candidates))
        or any(not re.fullmatch(r"Q[1-9]\d*", qid) for qid in subjects + candidates)
    ):
        raise ValueError("Expected up to 250 distinct Daniel QIDs and seven candidates")
    source_values = " ".join(f"wd:{qid}" for qid in subjects)
    target_values = " ".join(f"wd:{qid}" for qid in candidates)
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT DISTINCT ?subject ?event ?statement ?property ?rank WHERE {{
  VALUES ?subject {{ {source_values} }}
  VALUES ?event {{ {target_values} }}
  ?subject ?claim ?statement .
  ?property wikibase:claim ?claim ;
            wikibase:statementProperty ?statementProperty .
  ?statement ?statementProperty ?event ; wikibase:rank ?rank .
}}
"""


def item_links(record: dict) -> list[dict]:
    """S2T 7/8: native item-valued main statements only, preserving all ranks.

    Non-item, unknown-value and no-value claims remain in the full cached JSON.
    They do not generate a candidate identity or an Event participation link.
    """
    links = []
    for prop, statements in record["claims"].items():
        for statement in statements:
            snak = statement.get("mainsnak", {})
            value = snak.get("datavalue", {}).get("value")
            if not isinstance(value, dict) or value.get("entity-type") != "item":
                continue
            if (
                not re.fullmatch(r"Q[1-9]\d*", value.get("id", ""))
                or snak.get("property") != prop
                or snak.get("datatype") != "wikibase-item"
                or not statement.get("id")
                or statement.get("rank") not in {"normal", "preferred", "deprecated"}
            ):
                raise SourceException(
                    "Unexpected current item statement",
                    qid=record["id"],
                    statement=statement,
                )
            links.append(
                dict(
                    subject_qid=record["id"],
                    object_qid=value["id"],
                    source_predicate=f"wd:{prop}",
                    source_record_id=statement["id"],
                    raw_statement=statement,
                )
            )
    return links


def class_edges_query(qids: list[str], prop: str) -> str:
    """Retrieve one hierarchy hop for at most ten reference QIDs (S2T 7).

    The approved split avoids server-side recursive joins. Local traversal uses
    all direct P31/P279 statements without a depth cutoff. Acquisition retains
    deprecated rank; Event classification alone excludes it. S2T 7.
    """
    if (
        not 1 <= len(qids) <= 10
        or len(qids) != len(set(qids))
        or any(not re.fullmatch(r"Q[1-9]\d*", qid) for qid in qids)
        or prop not in {"P31", "P279"}
    ):
        raise ValueError("Expected up to ten distinct hierarchy QIDs and P31/P279")
    values = " ".join(f"wd:{qid}" for qid in qids)
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?item ?present ?statement ?parent ?rank WHERE {{
  VALUES ?item {{ {values} }}
  BIND(EXISTS {{ ?item ?predicate ?value }} AS ?present)
  OPTIONAL {{
    ?item p:{prop} ?statement .
    ?statement ps:{prop} ?parent ; wikibase:rank ?rank .
    FILTER(STRSTARTS(STR(?parent), "http://www.wikidata.org/entity/Q"))
  }}
}}
"""


def hierarchy_path(qid: str, parents: dict[str, list[dict]]) -> list[dict] | None:
    """Cycle-safe native P279 traversal; no guessed class or depth limit.

    A missing fetched node is incomplete acquisition, not a negative result.
    A path is supporting evidence only; it does not add a business entity.
    """
    pending = [(qid, [])]
    visited = set()
    while pending:
        current, path = pending.pop()
        if current == EVENT_ROOT:
            return path
        if current in visited:
            continue
        visited.add(current)
        if current not in parents:
            raise SourceException("Incomplete Event hierarchy", qid=current)
        pending.extend((edge["parent"], path + [edge]) for edge in parents[current])
    return None


def classify_events(edges: dict) -> list[dict]:
    """S2T 7: approved non-deprecated P31/P279 Event ancestry, 20 October.

    Filter a separate view, preserving every fetched node and all raw evidence.
    Traverse again so an alternative valid path can survive a deprecated path.
    This establishes ancestry only, not the two-distinct-Daniel-QID gate.
    Relations and their ranks do not use this filter.
    """
    deprecated = {"deprecated", "http://wikiba.se/ontology#DeprecatedRank"}
    allowed = deprecated | {
        "normal",
        "preferred",
        "http://wikiba.se/ontology#NormalRank",
        "http://wikiba.se/ontology#PreferredRank",
    }
    for prop, nodes in edges.items():
        for qid, rows in nodes.items():
            if any(edge.get("rank") not in allowed for edge in rows):
                raise SourceException(
                    "Unknown Event hierarchy rank", qid=qid, prop=prop
                )
    parents = {
        qid: [edge for edge in rows if edge["rank"] not in deprecated]
        for qid, rows in edges["P279"].items()
    }
    result = []
    for qid, rows in edges["P31"].items():
        paths = []
        for row in rows:
            if row["rank"] in deprecated:
                continue
            path = hierarchy_path(row["parent"], parents)
            if path is not None:
                paths.append(dict(P31=row, P279=path))
        result.append(dict(qid=qid, event_hierarchy_match=bool(paths), paths=paths))
    return result
