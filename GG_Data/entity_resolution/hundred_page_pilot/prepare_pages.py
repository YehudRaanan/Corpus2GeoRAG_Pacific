"""Preserve selected Daniel rows and bind passages to evidenced raw Wiki revisions.

Selection is frozen before recovery. Cached raw revisions are checked first, then
bounded Wikipedia requests inspect dated snapshots. Original text and offsets
stay unchanged; failures and damaged text remain explicit in the output tables.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import shutil
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from GG_Data.entity_resolution.attach_source_page_ids import (
    WikiClient,
    normalize,
    read_json,
    resolve_page,
    save_json,
    sha256,
)

LOG = logging.getLogger(__name__)
INPUT_SHA256 = "eb99863511b68c79aca37a6ef16e1b53fdb5c48a9fbd8d602db43b6a638f1deb"
ORIGINAL = [
    "entity_group",
    "score",
    "word",
    "start",
    "end",
    "Source",
    "Index",
    "Text",
    "subtype",
]
REVISION_SCHEMA = pa.schema(
    [
        ("page_id", pa.int64()),
        ("revision_id", pa.int64()),
        ("wiki_title", pa.string()),
        ("revision_timestamp", pa.string()),
        ("wikitext_path", pa.string()),
        ("evidence_path", pa.string()),
        ("sha256", pa.string()),
        ("retrieval_utc", pa.string()),
        ("revision_metadata_status", pa.string()),
        ("metadata_evidence_path", pa.string()),
    ]
)
DATES = [
    "2026-10-28",
    "2026-10-24",
    "2026-10-01",
    "2026-09-01",
    "2026-08-01",
    "2026-07-01",
    "2026-04-01",
    "2026-01-01",
    "2025-10-01",
    "2025-07-01",
    "2025-04-01",
    "2025-01-01",
    "2024-07-01",
    "2024-01-01",
    "2023-01-01",
    "2022-01-01",
    "2021-01-01",
    "2020-01-01",
    "2018-01-01",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def passage_id(source: str, index: int, text: str) -> str:
    return hashlib.sha256(
        json.dumps(
            [source, index, text], ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def match_method(text: str, raw: str) -> str | None:
    """Never render markup or repair damaged text to establish containment."""
    if not text.strip():
        return None
    if text == raw:
        return "EXACT_RAW_EQUALITY"
    if text in raw:
        return "EXACT_RAW_CONTAINMENT"
    if normalize(text) in normalize(raw):
        return "NFC_WHITESPACE_RAW_CONTAINMENT"
    return None


def atomic_parquet(table: pa.Table, target: Path) -> None:
    temporary = target.with_suffix(".parquet.tmp")
    pq.write_table(table, temporary, compression="zstd")
    temporary.replace(target)


def freeze_selection(input_path: Path, old_root: Path, output: Path) -> dict:
    path = output / "selection.json"
    if path.exists():
        selection = read_json(path)
        if selection["input_sha256"] != INPUT_SHA256:
            raise ValueError("Frozen selection belongs to another input")
        return selection
    old = pq.read_table(
        old_root
        / "ten_page_structure_alignment_20261028"
        / "selected_revisions.parquet"
    )["wiki_page_title"].to_pylist()
    titles: set[str] = set()
    for batch in pq.ParquetFile(input_path).iter_batches(columns=["Source"]):
        titles.update(batch.column(0).to_pylist())
    seed = 20261028
    included = [title for title in old if title in titles]
    remaining = sorted(
        titles - set(included),
        key=lambda title: hashlib.sha256(f"{seed}\0{title}".encode()).hexdigest(),
    )
    selection = {
        "seed": seed,
        "source_titles": included + remaining[: 100 - len(included)],
        "input_sha256": INPUT_SHA256,
        "old_ten_titles": old,
        "selection_method": "Previous ten literal titles if present, then ascending SHA256(UTF8(str(seed)+NUL+Source)); select before page recovery and predictions.",
        "distinct_input_source_count": len(titles),
    }
    save_json(path, selection)
    return selection


def read_selected(input_path: Path, titles: list[str]) -> pa.Table:
    chunks = []
    offset = 0
    wanted = pa.array(titles, type=pa.string())
    for batch in pq.ParquetFile(input_path).iter_batches():
        selected = pc.is_in(
            batch.column(batch.schema.get_field_index("Source")), value_set=wanted
        )
        if pc.any(selected).as_py():
            table = pa.Table.from_batches([batch]).append_column(
                "source_row_index",
                pa.array(range(offset, offset + batch.num_rows), type=pa.int64()),
            )
            chunks.append(table.filter(selected))
        offset += batch.num_rows
    return pa.concat_tables(chunks)


def export_old_exact_joins(passages: list[dict], old_root: Path, output: Path) -> dict:
    """Audit exact old Source/Text/hash joins; rendered evidence cannot accept raw rows."""
    by_key = defaultdict(list)
    for passage in passages:
        by_key[(passage["Source"], passage["Text"], passage["text_sha256"])].append(
            passage["passage_id"]
        )
    evidence = old_root / "source_page_ids_20261026" / "passage_decisions.jsonl.gz"
    rows = []
    with gzip.open(evidence, "rt", encoding="utf-8") as stream:
        for line in stream:
            decision = json.loads(line)
            key = (decision["Source"], decision["Text"], decision["text_sha256"])
            for pid in by_key.get(key, []):
                rows.append(
                    {
                        "passage_id": pid,
                        "Source": key[0],
                        "text_sha256": key[2],
                        "old_page_id": decision.get("wiki_page_id"),
                        "old_revision_id": decision.get("revision_id"),
                        "old_status": decision["status"],
                        "old_decision_evidence_path": str(evidence.resolve()),
                        "acceptance_basis": "Candidate provenance only; raw containment checked independently",
                    }
                )
    schema = pa.schema(
        [
            ("passage_id", pa.string()),
            ("Source", pa.string()),
            ("text_sha256", pa.string()),
            ("old_page_id", pa.int64()),
            ("old_revision_id", pa.int64()),
            ("old_status", pa.string()),
            ("old_decision_evidence_path", pa.string()),
            ("acceptance_basis", pa.string()),
        ]
    )
    atomic_parquet(
        pa.Table.from_pylist(rows, schema=schema),
        output / "old_exact_passage_joins.parquet",
    )
    summary = {
        "matched_passages": len(rows),
        "join_fields": ["Source", "Text", "text_sha256"],
        "old_evidence_sha256": sha256(evidence),
        "raw_acceptance_inferred_from_old_rendered_decisions": False,
    }
    save_json(output / "old_exact_passage_joins_summary.json", summary)
    return summary


def verify_exports(input_path: Path, output: Path) -> dict:
    """Verify persisted lineage and make reused revision evidence portable."""
    selection = read_json(output / "selection.json")
    expected = read_selected(input_path, selection["source_titles"])
    mentions = pq.read_table(output / "selected_mentions.parquet")
    if not mentions.select(ORIGINAL + ["source_row_index"]).equals(
        expected, check_metadata=True
    ):
        raise ValueError("Persisted original values or source row indices changed")
    passage_rows = pq.read_table(output / "passages.parquet").to_pylist()
    rewrites: dict[str, str] = {}
    for name in ["revisions.parquet", "checked_revisions.parquet"]:
        table = pq.read_table(output / name)
        rows = table.to_pylist()
        for row in rows:
            raw_path = Path(row["wikitext_path"])
            if sha256(raw_path) != row["sha256"]:
                raise ValueError("Revision wikitext hash changed")
            for field in ["evidence_path", "metadata_evidence_path"]:
                path = Path(row[field])
                if not path.is_relative_to(output):
                    target = (
                        output
                        / "reused_evidence"
                        / (sha256(path) + path.suffixes[-2] + path.suffix)
                    )
                    target.parent.mkdir(exist_ok=True)
                    if not target.exists():
                        shutil.copyfile(path, target)
                    if sha256(path) != sha256(target):
                        raise ValueError("Copied old evidence hash changed")
                    rewrites[str(path)] = str(target.resolve())
                    row[field] = str(target.resolve())
        atomic_parquet(pa.Table.from_pylist(rows, schema=table.schema), output / name)
    for passage in passage_rows:
        if passage["evidence_path"] in rewrites:
            passage["evidence_path"] = rewrites[passage["evidence_path"]]
    old_schema = pq.read_schema(output / "passages.parquet")
    atomic_parquet(
        pa.Table.from_pylist(passage_rows, schema=old_schema),
        output / "passages.parquet",
    )
    revisions = pq.read_table(output / "revisions.parquet").to_pylist()
    revision_map = {(r["page_id"], r["revision_id"]): r for r in revisions}
    raws = {
        key: Path(r["wikitext_path"]).read_text(encoding="utf-8")
        for key, r in revision_map.items()
    }
    used = {
        (p["page_id"], p["revision_id"])
        for p in passage_rows
        if p["revision_id"] is not None
    }
    if used != set(revision_map):
        raise ValueError("Used revision manifest has missing or extra revisions")
    for passage in passage_rows:
        if passage["revision_id"] is not None:
            key = (passage["page_id"], passage["revision_id"])
            if match_method(passage["Text"], raws[key]) != passage["match_method"]:
                raise ValueError("Persisted raw containment does not reproduce")
    for revision in revisions:
        raw_records = raw_revision_rows(
            read_json(Path(revision["evidence_path"])), Path(revision["evidence_path"])
        )
        key = (revision["page_id"], revision["revision_id"])
        if not any(
            (r["page_id"], r["revision_id"]) == key and r["raw"] == raws[key]
            for r in raw_records
        ):
            raise ValueError("Raw bytes are not supported by their API evidence")
        metadata = read_json(Path(revision["metadata_evidence_path"]))
        data = json.loads(metadata["response_text"])
        if revision["revision_timestamp"] and not any(
            page["pageid"] == revision["page_id"]
            and item["revid"] == revision["revision_id"]
            and item.get("timestamp") == revision["revision_timestamp"]
            for page in data.get("query", {}).get("pages", [])
            for item in page.get("revisions", [])
        ):
            raise ValueError("Timestamp/page/revision absent from metadata evidence")
    checks = {
        "original_nine_columns_and_global_row_indices_verified": True,
        "all_used_revisions_supported_by_raw_api_evidence": True,
        "raw_containment_reproduced_for_all_resolved_passages": True,
        "used_revision_manifest_exact": True,
        "metadata_timestamps_verified": True,
        "reused_evidence_copies_sha256_verified": True,
        "selected_rows": mentions.num_rows,
        "passages": len(passage_rows),
        "used_revisions": len(revisions),
        "verified_utc": utc_now(),
    }
    save_json(output / "prepare_pages_verification.json", checks)
    summary = read_json(output / "prepare_pages_summary.json")
    records = [
        read_json(p) for p in (output / "page_requests" / "requests").glob("*.json.gz")
    ]
    prior_path = output / "prepare_pages_interrupted_run_summary.json"
    prior = read_json(prior_path) if prior_path.exists() else None
    summary.update(
        new_api_calls_this_process=summary.get(
            "new_api_calls_this_process", summary["new_api_calls"]
        ),
        new_api_calls=len(records),
        durable_api_request_records=len(records),
        api_request_elapsed_seconds=sum(r["elapsed_seconds"] for r in records),
        successful_api_records=sum(r["ok"] for r in records),
        interrupted_run=prior,
        first_process_measured_elapsed_seconds_lower_bound=(
            prior["elapsed_seconds"] if prior else None
        ),
        cumulative_measured_process_elapsed_seconds_lower_bound=summary[
            "elapsed_seconds"
        ]
        + (prior["elapsed_seconds"] if prior else 0),
        active_work_seconds=None,
        output_sha256={
            name: sha256(output / name)
            for name in [
                "selection.json",
                "selected_mentions.parquet",
                "passages.parquet",
                "revisions.parquet",
                "checked_revisions.parquet",
            ]
        },
        verification=checks,
    )
    save_json(output / "prepare_pages_summary.json", summary)
    files = {
        str(p.relative_to(output)): sha256(p)
        for p in output.rglob("*")
        if p.is_file()
        and (
            p.name.startswith("prepare_pages")
            or p.name
            in {
                "selection.json",
                "selected_mentions.parquet",
                "passages.parquet",
                "revisions.parquet",
                "checked_revisions.parquet",
            }
            or p.relative_to(output).parts[0]
            in {"wikitext", "reused_evidence", "page_requests"}
        )
        and p.name
        not in {"prepare_pages_artifacts.sha256.json", "prepare_pages_ledger.jsonl"}
    }
    save_json(output / "prepare_pages_artifacts.sha256.json", files)
    with (output / "prepare_pages_ledger.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps({"record_type": "aggregate_verified_summary", **summary}) + "\n"
        )
    return checks


class BoundedClient(WikiClient):
    def __init__(self, output: Path, deadline: float, cache_roots: list[Path]):
        super().__init__(output)
        self.deadline = deadline
        self.cache_roots = cache_roots
        self.new_calls = 0
        self.cached_calls = 0

    def query(self, params: dict[str, Any]) -> tuple[dict, str]:
        canonical = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
        name = (
            hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
            + ".json.gz"
        )
        for root in [self.cache, *self.cache_roots]:
            path = root / name
            if path.exists():
                record = read_json(path)
                self.cached_calls += 1
                if not record["ok"]:
                    raise RuntimeError(f"Saved failed request; no retry: {path}")
                return json.loads(record["response_text"]), str(path.resolve())
        if time.monotonic() >= self.deadline or self.new_calls >= 2200:
            raise TimeoutError("Approved recovery time/request cap reached")
        self.new_calls += 1
        data, evidence = super().query(params)
        return data, str((self.cache / evidence).resolve())


def raw_revision_rows(record: dict, evidence: Path) -> list[dict]:
    """Read either existing parse evidence or revision-content API evidence."""
    if not record.get("ok") or "response_text" not in record:
        return []
    data = json.loads(record["response_text"])
    parsed = data.get("parse", {})
    if "wikitext" in parsed:
        raw = parsed["wikitext"]
        raw = raw.get("*", "") if isinstance(raw, dict) else raw
        return [
            {
                "page_id": parsed["pageid"],
                "revision_id": parsed["revid"],
                "wiki_title": parsed["title"],
                "revision_timestamp": "",
                "raw": raw,
                "evidence_path": str(evidence.resolve()),
                "retrieval_utc": record.get("retrieved_utc", ""),
            }
        ]
    result = []
    for page in data.get("query", {}).get("pages", []):
        for revision in page.get("revisions", []):
            slot = revision.get("slots", {}).get("main", revision)
            raw = slot.get("content", slot.get("*"))
            if isinstance(raw, str):
                result.append(
                    {
                        "page_id": page["pageid"],
                        "revision_id": revision["revid"],
                        "wiki_title": page["title"],
                        "revision_timestamp": revision.get("timestamp", ""),
                        "raw": raw,
                        "evidence_path": str(evidence.resolve()),
                        "retrieval_utc": record.get("retrieved_utc", ""),
                    }
                )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--old-cache-root", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=6600)
    parser.add_argument("--cache-only", action="store_true")
    args = parser.parse_args()
    started, start_utc = time.monotonic(), utc_now()
    deadline = started + min(args.max_seconds, 7200)
    output, old_root = args.output.resolve(), args.old_cache_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if sha256(args.input) != INPUT_SHA256:
        raise ValueError("Input SHA256 differs from approved input")
    selection = freeze_selection(args.input, old_root, output)
    titles = selection["source_titles"]
    if len(titles) != 100 or len(set(titles)) != 100:
        raise ValueError("Frozen sample must contain 100 unique literal sources")
    selected = read_selected(args.input, titles)
    source_values = selected["Source"].to_pylist()
    text_values = selected["Text"].to_pylist()
    index_values = selected["Index"].to_pylist()
    ids = [
        passage_id(s, i, t) for s, i, t in zip(source_values, index_values, text_values)
    ]
    passages = {}
    for source, index, text, pid in zip(source_values, index_values, text_values, ids):
        passages.setdefault(
            pid,
            {
                "Source": source,
                "Index": index,
                "Text": text,
                "passage_id": pid,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "damaged_text": "\ufffd" in text,
                "source_scope": "ALL_SUPPLIED_RAW_SECTIONS_NO_FILTER",
                "page_id": None,
                "revision_id": None,
                "wiki_title": None,
                "page_status": "PAGE_PENDING",
                "revision_status": "RAW_REVISION_PENDING",
                "match_method": None,
                "evidence_path": None,
                "revision_timestamp": None,
                "revision_url": None,
                "failure_reason": "Recovery not yet complete",
            },
        )
    selected = selected.append_column("passage_id", pa.array(ids, type=pa.string()))
    # Publish the original selected texts immediately for training leak exclusion.
    atomic_parquet(selected, output / "selected_raw_mentions.parquet")
    atomic_parquet(
        pa.Table.from_pylist(list(passages.values())),
        output / "selected_raw_passages.parquet",
    )
    export_old_exact_joins(list(passages.values()), old_root, output)
    cache_dirs = [
        old_root / name / "requests"
        for name in [
            "source_page_ids_20261026",
            "source_page_ids_history_pilot_20261027",
            "source_page_versions_staged_20261027",
            "source_page_versions_history_20261027",
        ]
    ]
    client = BoundedClient(output / "page_requests", deadline, cache_dirs)
    contexts: dict[str, dict] = {}
    snapshots: dict[tuple[int, int], dict] = {}
    errors, attempts = [], []
    timestamp_by_revision = {}
    for name in [
        "source_page_versions_staged_20261027",
        "source_page_versions_history_20261027",
    ]:
        path = old_root / name / "revision_metadata.json"
        if path.exists():
            timestamp_by_revision.update(
                {int(k): v["timestamp"] for k, v in read_json(path).items()}
            )
    by_source = defaultdict(list)
    for passage in passages.values():
        by_source[passage["Source"]].append(passage)

    def add_snapshot(snapshot: dict) -> None:
        key = (snapshot["page_id"], snapshot["revision_id"])
        if key in snapshots:
            return
        snapshot["revision_timestamp"] = snapshot[
            "revision_timestamp"
        ] or timestamp_by_revision.get(key[1], "")
        raw = snapshot.pop("raw")
        raw_dir = output / "wikitext"
        raw_dir.mkdir(exist_ok=True)
        target = raw_dir / f"{key[0]}_{key[1]}.txt"
        encoded = raw.encode("utf-8")
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("Immutable raw revision bytes changed")
        if not target.exists():
            target.write_bytes(encoded)
        snapshot.update(
            wikitext_path=str(target.resolve()),
            sha256=hashlib.sha256(encoded).hexdigest(),
            revision_metadata_status=(
                "COMPLETE" if snapshot["revision_timestamp"] else "TIMESTAMP_UNRESOLVED"
            ),
            metadata_evidence_path=snapshot["evidence_path"],
        )
        snapshots[key] = snapshot
        for source, context in contexts.items():
            if context.get("pageid") != key[0]:
                continue
            for passage in by_source[source]:
                if passage["revision_id"] is not None:
                    continue
                method = match_method(passage["Text"], raw)
                if method:
                    passage.update(
                        page_id=key[0],
                        revision_id=key[1],
                        wiki_title=snapshot["wiki_title"],
                        page_status=context["status"],
                        revision_status="VERIFIED_RAW_CONTENT",
                        match_method=method,
                        evidence_path=snapshot["evidence_path"],
                        revision_timestamp=snapshot["revision_timestamp"],
                        revision_url=f"https://en.wikipedia.org/w/index.php?oldid={key[1]}",
                        failure_reason=None,
                    )

    def publish(phase: str) -> None:
        used = {
            (p["page_id"], p["revision_id"])
            for p in passages.values()
            if p["revision_id"] is not None
        }
        atomic_parquet(
            pa.Table.from_pylist(list(snapshots.values()), schema=REVISION_SCHEMA),
            output / "checked_revisions.parquet",
        )
        atomic_parquet(
            pa.Table.from_pylist(
                [s for key, s in snapshots.items() if key in used],
                schema=REVISION_SCHEMA,
            ),
            output / "revisions.parquet",
        )
        # Explicit schema prevents all-null intermediate outputs from changing types.
        passage_table = pa.Table.from_pylist(list(passages.values()))
        for field in ["page_id", "revision_id"]:
            i = passage_table.schema.get_field_index(field)
            passage_table = passage_table.set_column(
                i, field, passage_table[field].cast(pa.int64())
            )
        atomic_parquet(passage_table, output / "passages.parquet")
        enriched = selected
        for name, dtype in [
            ("page_id", pa.int64()),
            ("revision_id", pa.int64()),
            ("wiki_title", pa.string()),
            ("page_status", pa.string()),
            ("revision_status", pa.string()),
            ("damaged_text", pa.bool_()),
        ]:
            enriched = enriched.append_column(
                name, pa.array([passages[pid][name] for pid in ids], type=dtype)
            )
        offset_valid = [
            isinstance(start, int)
            and isinstance(end, int)
            and 0 <= start <= end <= len(text)
            and text[start:end] == word
            for start, end, text, word in zip(
                selected["start"].to_pylist(),
                selected["end"].to_pylist(),
                text_values,
                selected["word"].to_pylist(),
            )
        ]
        enriched = enriched.append_column(
            "original_offset_literal_valid", pa.array(offset_valid)
        )
        if not enriched.select(ORIGINAL).equals(
            selected.select(ORIGINAL), check_metadata=True
        ):
            raise ValueError("Original selected columns changed")
        atomic_parquet(enriched, output / "selected_mentions.parquet")
        save_json(output / "pages.json", list(contexts.values()))
        summary = {
            "stage": "prepare_pages",
            "owner": "pages_implementation",
            "phase": phase,
            "started_utc": start_utc,
            "updated_utc": utc_now(),
            "elapsed_seconds": time.monotonic() - started,
            "active_work_seconds": None,
            "approval_wait_seconds": None,
            "environment_wait_seconds": None,
            "gpu_seconds": 0,
            "estimated_cost_usd": 0,
            "input_sha256": INPUT_SHA256,
            "selected_sources": len(titles),
            "selected_rows": selected.num_rows,
            "passages": len(passages),
            "resolved_passages": sum(
                p["revision_id"] is not None for p in passages.values()
            ),
            "resolved_rows": enriched.num_rows - enriched["revision_id"].null_count,
            "revisions": len(used),
            "checked_revisions": len(snapshots),
            "new_api_calls": client.new_calls,
            "cached_api_calls": client.cached_calls,
            "errors": len(errors),
            "damaged_passages": sum(p["damaged_text"] for p in passages.values()),
            "literal_offset_mismatch_rows": len(offset_valid) - sum(offset_valid),
            "original_columns_unchanged": True,
            "revision_semantics": "Saved raw content contains copied passage; precise extraction revision is not proven.",
            "revision_status_counts": dict(
                Counter(p["revision_status"] for p in passages.values())
            ),
        }
        save_json(output / "prepare_pages_summary.json", summary)
        LOG.info(
            "%s rows=%d/%d passages=%d/%d revisions=%d requests=%d errors=%d",
            phase,
            summary["resolved_rows"],
            selected.num_rows,
            summary["resolved_passages"],
            len(passages),
            len(used),
            client.new_calls,
            len(errors),
        )

    # Resolve cached source aliases first. Never treat old rendered text as raw evidence.
    for source in titles:
        path = (
            old_root
            / "source_page_ids_20261026"
            / "pages"
            / (hashlib.sha256(source.encode()).hexdigest() + ".json.gz")
        )
        if path.exists():
            old_page = read_json(path)
            contexts[source] = {
                k: old_page[k]
                for k in ["Source", "status", "pageid", "title", "aliases"]
                if k in old_page
            }
            contexts[source]["evidence_path"] = str(path.resolve())
    pending_titles = [s for s in titles if s not in contexts]
    if not args.cache_only:
        for offset in range(0, len(pending_titles), 50):
            batch = pending_titles[offset : offset + 50]
            try:
                data, evidence = client.query(
                    {
                        "action": "query",
                        "titles": "|".join(batch),
                        "redirects": 1,
                        "prop": "info|pageprops",
                        "inprop": "url",
                    }
                )
                for source in batch:
                    page = resolve_page(source, data)
                    contexts[source] = {
                        k: page[k]
                        for k in ["Source", "status", "pageid", "title", "aliases"]
                        if k in page
                    }
                    contexts[source]["evidence_path"] = evidence
            except (RuntimeError, TimeoutError) as error:
                errors.append(
                    {"phase": "resolve_titles", "titles": batch, "error": str(error)}
                )
    for source in titles:
        context = contexts.setdefault(
            source, {"Source": source, "status": "UNRESOLVED_PAGE_REQUEST_FAILURE"}
        )
        for passage in by_source[source]:
            passage.update(
                page_id=context.get("pageid"),
                wiki_title=context.get("title"),
                page_status=context["status"],
            )
    wanted_ids = {p.get("pageid") for p in contexts.values() if p.get("pageid")}
    for directory in [*cache_dirs, client.cache]:
        for evidence in directory.glob("*.json.gz"):
            try:
                for snapshot in raw_revision_rows(read_json(evidence), evidence):
                    if snapshot["page_id"] in wanted_ids:
                        add_snapshot(snapshot)
            except (ValueError, KeyError, OSError) as error:
                errors.append(
                    {
                        "phase": "read_old_cache",
                        "evidence": str(evidence),
                        "error": str(error),
                    }
                )
    # Complete historical timestamps separately; missing fields remain explicit.
    missing_metadata = [
        key[1] for key, s in snapshots.items() if not s["revision_timestamp"]
    ]
    if not args.cache_only:
        for offset in range(0, len(missing_metadata), 50):
            try:
                data, evidence = client.query(
                    {
                        "action": "query",
                        "prop": "revisions",
                        "revids": "|".join(
                            map(str, missing_metadata[offset : offset + 50])
                        ),
                        "rvprop": "ids|timestamp|sha1",
                    }
                )
                for page in data.get("query", {}).get("pages", []):
                    for revision in page.get("revisions", []):
                        key = (page["pageid"], revision["revid"])
                        if key in snapshots:
                            snapshots[key].update(
                                revision_timestamp=revision["timestamp"],
                                revision_metadata_status="COMPLETE",
                                metadata_evidence_path=evidence,
                            )
                            for p in passages.values():
                                if (p["page_id"], p["revision_id"]) == key:
                                    p["revision_timestamp"] = revision["timestamp"]
            except (RuntimeError, ValueError, KeyError, TimeoutError) as error:
                errors.append({"phase": "revision_timestamp", "error": str(error)})
    publish("old_raw_cache_checked")

    def recover(source: str, date: str, phase: str) -> None:
        context = contexts[source]
        if not context.get("pageid") or all(
            p["revision_id"] is not None for p in by_source[source]
        ):
            return
        attempt = {
            "Source": source,
            "page_id": context["pageid"],
            "date": date,
            "utc": utc_now(),
            "phase": phase,
        }
        try:
            data, evidence = client.query(
                {
                    "action": "query",
                    "prop": "revisions",
                    "pageids": context["pageid"],
                    "rvprop": "ids|timestamp|content|sha1",
                    "rvslots": "main",
                    "rvlimit": 1,
                    "rvstart": date + "T23:59:59Z",
                    "rvdir": "older",
                }
            )
            recovered = raw_revision_rows(read_json(Path(evidence)), Path(evidence))
            for snapshot in recovered:
                if snapshot["page_id"] != context["pageid"]:
                    raise ValueError("Revision response changed page identity")
                add_snapshot(snapshot)
            attempt.update(
                status=(
                    "RAW_REVISION_CHECKED" if recovered else "NO_RAW_REVISION_RETURNED"
                ),
                evidence_path=evidence,
                revision_ids=[s["revision_id"] for s in recovered],
            )
        except (RuntimeError, ValueError, KeyError) as error:
            attempt.update(status="REQUEST_OR_EVIDENCE_FAILURE", error=str(error))
            errors.append(attempt.copy())
        attempts.append(attempt)
        with (output / "page_recovery_attempts.jsonl").open(
            "a", encoding="utf-8"
        ) as stream:
            stream.write(json.dumps(attempt, ensure_ascii=False) + "\n")
        publish(f"{phase}_{date}")

    stop_reason = "CACHE_ONLY" if args.cache_only else None
    if not args.cache_only:
        try:
            spike_start = time.monotonic()
            for date in DATES:
                if time.monotonic() - spike_start >= 1200:
                    break
                for source in titles[:3]:
                    recover(source, date, "three_page_spike")
            spike = {
                "sources": titles[:3],
                "elapsed_seconds": time.monotonic() - spike_start,
                "question": "Can copied raw markup be verified without rendering or repairing source text?",
                "exit_check": [
                    {
                        "Source": s,
                        "passages": len(by_source[s]),
                        "resolved_passages": sum(
                            p["revision_id"] is not None for p in by_source[s]
                        ),
                    }
                    for s in titles[:3]
                ],
                "adaptation": "Reuse raw-content evidence; preserve remaining unmatched passages and continue dated snapshot recovery within original cap.",
            }
            save_json(output / "three_page_evidence_spike.json", spike)
            LOG.info("THREE_PAGE_SPIKE_COMPLETE %s", json.dumps(spike))
            for date in DATES:
                for source in titles[3:]:
                    recover(source, date, "recovery")
        except TimeoutError as error:
            stop_reason = str(error)
    for passage in passages.values():
        if passage["revision_id"] is None:
            passage["revision_status"] = (
                "UNRESOLVED_DAMAGED_RAW_TEXT"
                if passage["damaged_text"]
                else (
                    "UNRESOLVED_RECOVERY_LIMIT"
                    if stop_reason
                    else "UNRESOLVED_NO_FULL_RAW_MATCH_IN_CHECKED_REVISIONS"
                )
            )
            passage["failure_reason"] = (
                stop_reason
                or "No exact or NFC/whitespace raw containment in checked revisions; historical search is bounded, not exhaustive."
            )
    save_json(output / "page_recovery_errors.json", errors)
    collisions = defaultdict(list)
    for source, context in contexts.items():
        if context.get("pageid"):
            collisions[context["pageid"]].append(source)
    save_json(
        output / "redirect_collisions.json",
        {str(k): v for k, v in collisions.items() if len(v) > 1},
    )
    publish("complete")
    summary = read_json(output / "prepare_pages_summary.json")
    summary.update(
        ended_utc=utc_now(),
        stop_reason=stop_reason,
        recovery_dates=DATES,
        output_sha256={
            name: sha256(output / name)
            for name in [
                "selection.json",
                "selected_mentions.parquet",
                "passages.parquet",
                "revisions.parquet",
            ]
        },
    )
    save_json(output / "prepare_pages_summary.json", summary)
    with (output / "prepare_pages_ledger.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(summary) + "\n")
    verify_exports(args.input, output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    main()
