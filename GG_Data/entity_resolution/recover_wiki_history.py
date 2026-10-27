"""Recover only pending passages; preserve all accepted V2 rows byte-for-value."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from attach_source_page_ids import (
    WikiClient,
    normalize,
    read_json,
    render_text,
    save_json,
    sha256,
)
from export_wiki_revision_versions import verify_saved_evidence, write_new

LOG = logging.getLogger(__name__)
DATES = [
    "2026-10-24",
    "2026-07-01",
    "2026-01-01",
    "2025-07-01",
    "2025-01-01",
    "2024-07-01",
    "2024-01-01",
    "2023-01-01",
]
REFINEMENT = [
    "2026-10-01",
    "2026-09-01",
    "2026-08-01",
    "2026-06-01",
    "2026-05-01",
    "2026-04-01",
    "2026-03-01",
    "2026-02-01",
    "2025-10-01",
    "2025-04-01",
    "2024-10-01",
    "2024-04-01",
    "2022-01-01",
    "2021-01-01",
    "2020-01-01",
    "2018-01-01",
]


def eligible(text: str, direct: bool) -> bool:
    return bool(normalize(text)) and (
        direct or (len(normalize(text)) >= 50 and len(text.split()) >= 8)
    )


def choose_match(candidates: list[dict]) -> dict | None:
    if len({x["pageid"] for x in candidates}) != 1:
        return None
    return max(candidates, key=lambda x: (x.get("timestamp", ""), x["revid"]))


def apply_updates(table: pa.Table, matches: dict, statuses: dict) -> pa.Table:
    columns = {}
    for index, (source, text, old_id) in enumerate(
        zip(
            table["Source"].to_pylist(),
            table["Text"].to_pylist(),
            table["wiki_page_id"].to_pylist(),
        )
    ):
        key = (source, text)
        if old_id is not None:
            if key in matches:
                raise ValueError("Update targets an accepted row")
            continue
        update = matches.get(key) or {
            "wiki_match_status": statuses.get(
                key, "UNRESOLVED_NO_FULL_MATCH_IN_CHECKED_REVISIONS"
            )
        }
        for name, value in update.items():
            if name not in table.column_names or name in {
                "Source",
                "Text",
                "wiki_text_sha256",
                "wiki_baseline_status",
            }:
                raise ValueError(f"Invalid metadata update field: {name}")
            if name not in columns:
                columns[name] = table[name].to_pylist()
            if name == "wiki_revision_timestamp" and isinstance(value, str):
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            columns[name][index] = value
    result = table
    for name, values in columns.items():
        result = result.set_column(
            result.schema.get_field_index(name),
            table.schema.field(name),
            pa.array(values, type=table[name].type),
        )
    return result


class SearchLimit(RuntimeError):
    pass


class HistoryClient(WikiClient):
    def __init__(self, output: Path, cache_roots: list[Path]):
        super().__init__(output)
        self.cache_roots = cache_roots
        self.started = time.monotonic()
        self.new_calls = 0

    def query(self, params: dict[str, Any]) -> tuple[dict, str]:
        canonical = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
        key = (
            hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
            + ".json.gz"
        )
        for root in [self.cache, *self.cache_roots]:
            path = root / key
            if path.exists():
                record = read_json(path)
                if not record["ok"]:
                    raise RuntimeError(f"Saved failed request; no retry: {path}")
                return json.loads(record["response_text"]), str(path.resolve())
        if self.new_calls >= 2200 or time.monotonic() - self.started >= 7200:
            raise SearchLimit("New request or retrieval-time limit reached")
        if (
            self.new_calls % 25 == 0
            and sum(p.stat().st_size for p in self.cache.glob("*.gz")) >= 3 * 1024**3
        ):
            raise SearchLimit("Saved request evidence storage limit reached")
        self.new_calls += 1
        data, evidence = super().query(params)
        return data, str((self.cache / evidence).resolve())


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    base = root / "source_page_ids_20261026"
    pilot = root / "source_page_ids_history_pilot_20261027"
    staged = root / "source_page_versions_staged_20261027"
    output = root / "source_page_versions_history_20261027"
    output.mkdir(exist_ok=True)
    target = (
        output
        / "georag_selected_v2_full_n36335_r345732948_20261024_v3_historical_continuation.parquet"
    )
    if target.exists() or (output / "progress.json").exists():
        raise FileExistsError(
            "Existing continuation state must be reviewed before resuming"
        )
    for directory in [base, pilot, staged]:
        LOG.info("Verifying saved evidence: %s", directory.name)
        verify_saved_evidence(directory)
    v2_path = next(staged.glob("*_v2_revision_metadata.parquet"))
    v2_digest = sha256(v2_path)
    with (staged / "remaining_unresolved_rows.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    pending = {}
    for row in rows:
        key = (row["Source"], row["Text"])
        if key not in pending:
            pending[key] = {
                "Source": key[0],
                "Text": key[1],
                "rows": 0,
                "raw_row_indices": [],
            }
        pending[key]["rows"] += 1
        pending[key]["raw_row_indices"].append(int(row["row_index"]))
    assert len(pending) == 414 and len(rows) == 5922
    ids_by_source = defaultdict(set)
    with gzip.open(
        base / "passage_decisions.jsonl.gz", "rt", encoding="utf-8"
    ) as stream:
        for decision in map(json.loads, stream):
            if decision["wiki_page_id"] is not None:
                ids_by_source[decision["Source"]].add(decision["wiki_page_id"])
    contexts = {}
    for source, _ in pending:
        if source in contexts:
            continue
        page = read_json(
            base / "pages" / (hashlib.sha256(source.encode()).hexdigest() + ".json.gz")
        )
        direct = page.get("status") == "ARTICLE"
        pageids = {page["pageid"]} if direct else ids_by_source[source]
        contexts[source] = {"direct": direct, "pageids": sorted(pageids)}
    save_json(
        output / "pending.json",
        [{**item, "context": contexts[key[0]]} for key, item in pending.items()],
    )
    client = HistoryClient(
        output, [base / "requests", pilot / "requests", staged / "requests"]
    )
    snapshots = defaultdict(list)
    wanted_ids = {
        pageid for context in contexts.values() for pageid in context["pageids"]
    }
    known_meta = {
        int(k): v for k, v in read_json(staged / "revision_metadata.json").items()
    }
    for directory in ["pages", "candidate_pages"]:
        for path in (base / directory).glob("*.json.gz"):
            page = read_json(path)
            if page.get("pageid") in wanted_ids and page.get("rendered"):
                revision = page["lastrevid"]
                if revision in known_meta:
                    snapshots[page["pageid"]].append(
                        {
                            "pageid": page["pageid"],
                            "title": page["title"],
                            "revid": revision,
                            "timestamp": known_meta[revision]["timestamp"],
                            "evidence": str(path.resolve()),
                            "metadata_evidence": known_meta[revision]["evidence"],
                            "evidence_kind": "saved_page_cache",
                            "_text": normalize(page["rendered"]),
                        }
                    )
    for snapshot in read_json(pilot / "results.json")["snapshots"]:
        with gzip.open(
            pilot / "requests" / snapshot["parse_evidence"], "rt", encoding="utf-8"
        ) as stream:
            parsed = json.loads(json.load(stream)["response_text"])["parse"]
        snapshots[snapshot["pageid"]].append(
            {
                "pageid": snapshot["pageid"],
                "title": snapshot["title"],
                "revid": snapshot["revid"],
                "timestamp": snapshot["timestamp"],
                "evidence": str(
                    (pilot / "requests" / snapshot["parse_evidence"]).resolve()
                ),
                "metadata_evidence": str(
                    (pilot / "requests" / snapshot["metadata_evidence"]).resolve()
                ),
                "evidence_kind": "parse_response",
                "_text": normalize(render_text(parsed["text"])),
            }
        )
    seen = {(s["pageid"], s["revid"]) for group in snapshots.values() for s in group}
    attempts, errors, attempted_ids, matches, statuses = [], [], set(), {}, {}

    def decide() -> None:
        for key, item in pending.items():
            context = contexts[key[0]]
            if not eligible(key[1], context["direct"]):
                statuses[key] = "INSUFFICIENT_TEXT_FOR_GLOBAL_RECOVERY"
                continue
            found = [
                snapshot
                for pageid in context["pageids"]
                for snapshot in snapshots[pageid]
                if normalize(key[1]) in snapshot["_text"]
            ]
            chosen = choose_match(found)
            if chosen:
                matches[key] = chosen
            elif found:
                statuses[key] = "AMBIGUOUS_MATCHING_PAGES"
                matches.pop(key, None)
            elif not context["pageids"]:
                statuses[key] = "NO_VERIFIED_SOURCE_CONTEXT"
            else:
                statuses[key] = "UNRESOLVED_NO_FULL_MATCH_IN_CHECKED_REVISIONS"

    def checkpoint(phase: str) -> None:
        save_json(
            output / "matches.json",
            [
                {
                    "Source": key[0],
                    "Text": key[1],
                    "rows": pending[key]["rows"],
                    **{k: v for k, v in value.items() if k != "_text"},
                }
                for key, value in matches.items()
            ],
        )
        save_json(
            output / "progress.json",
            {
                "phase": phase,
                "pending_pairs": len(pending),
                "pending_rows": len(rows),
                "matched_pairs": len(matches),
                "matched_rows": sum(pending[key]["rows"] for key in matches),
                "remaining_pairs": len(pending) - len(matches),
                "remaining_rows": len(rows)
                - sum(pending[key]["rows"] for key in matches),
                "new_api_calls": client.new_calls,
                "attempts": len(attempts),
                "errors": len(errors),
                "cached_or_new_snapshots": sum(len(x) for x in snapshots.values()),
                "retrieval_elapsed_seconds": time.monotonic() - client.started,
            },
        )

    decide()
    checkpoint("cache_complete")
    limit = None
    try:
        for phase, dates in [
            ("initial_dates", DATES),
            ("refinement_dates", REFINEMENT),
        ]:
            for date in dates:
                for pageid in sorted(wanted_ids):
                    unresolved = [
                        key
                        for key in pending
                        if key not in matches
                        and pageid in contexts[key[0]]["pageids"]
                        and eligible(key[1], contexts[key[0]]["direct"])
                    ]
                    if not unresolved:
                        continue
                    attempted_ids.add(pageid)
                    attempt = {"phase": phase, "date": date, "pageid": pageid}
                    try:
                        response, meta_evidence = client.query(
                            {
                                "action": "query",
                                "prop": "revisions",
                                "pageids": pageid,
                                "rvprop": "ids|timestamp|sha1",
                                "rvlimit": 1,
                                "rvstart": date + "T23:59:59Z",
                                "rvdir": "older",
                            }
                        )
                        page = response["query"]["pages"][0]
                        if page["pageid"] != pageid or page.get("ns") != 0:
                            raise ValueError("Wrong page identity or namespace")
                        if not page.get("revisions"):
                            attempt["status"] = "NO_REVISION_AT_DATE"
                        else:
                            revision = page["revisions"][0]
                            assert revision["timestamp"] <= date + "T23:59:59Z"
                            revid = revision["revid"]
                            attempt["revid"] = revid
                            if (pageid, revid) not in seen:
                                seen.add((pageid, revid))
                                data, parse_evidence = client.query(
                                    {
                                        "action": "parse",
                                        "oldid": revid,
                                        "prop": "text|wikitext|revid",
                                        "disableeditsection": 1,
                                    }
                                )
                                parsed = data["parse"]
                                if (
                                    parsed["pageid"] != pageid
                                    or parsed["revid"] != revid
                                ):
                                    raise ValueError(
                                        "Wrong parsed page/revision identity"
                                    )
                                snapshot = {
                                    "pageid": pageid,
                                    "title": page["title"],
                                    "revid": revid,
                                    "timestamp": revision["timestamp"],
                                    "evidence": parse_evidence,
                                    "metadata_evidence": meta_evidence,
                                    "evidence_kind": "parse_response",
                                    "_text": normalize(render_text(parsed["text"])),
                                }
                                snapshots[pageid].append(snapshot)
                            attempt["status"] = "CHECKED_REVISION"
                            decide()
                    except (
                        RuntimeError,
                        ValueError,
                        KeyError,
                        AssertionError,
                    ) as error:
                        if isinstance(error, SearchLimit):
                            raise
                        attempt.update(
                            status="REQUEST_OR_EVIDENCE_FAILURE", error=str(error)
                        )
                        errors.append(attempt)
                    attempts.append(attempt)
                    with (output / "attempts.jsonl").open(
                        "a", encoding="utf-8"
                    ) as stream:
                        stream.write(json.dumps(attempt) + "\n")
                    checkpoint(phase)
                    LOG.info(
                        "%s %s page=%s matches=%d/%d rows=%d requests=%d",
                        phase,
                        date,
                        pageid,
                        len(matches),
                        len(pending),
                        sum(pending[key]["rows"] for key in matches),
                        client.new_calls,
                    )
    except SearchLimit as error:
        limit = str(error)
        LOG.warning("Collection stopped at approved limit: %s", limit)
    for key in pending:
        if (
            key not in matches
            and statuses.get(key) == "UNRESOLVED_NO_FULL_MATCH_IN_CHECKED_REVISIONS"
        ):
            if limit:
                statuses[key] = "UNRESOLVED_SEARCH_LIMIT_REACHED"
            elif any(x["pageid"] in contexts[key[0]]["pageids"] for x in errors):
                statuses[key] = "UNRESOLVED_PARTIAL_REQUEST_FAILURE"
    checkpoint("collection_complete")
    save_json(
        output / "search_summary.json",
        {
            "initial_dates": DATES,
            "refinement_dates": REFINEMENT,
            "attempted_pageids": sorted(attempted_ids),
            "errors": errors,
            "limit": limit,
            "new_api_calls": client.new_calls,
        },
    )
    updates = {}
    for key, match in matches.items():
        updates[key] = {
            "wiki_page_id": match["pageid"],
            "wiki_page_title": match["title"],
            "wiki_revision_id": match["revid"],
            "wiki_revision_timestamp": match["timestamp"],
            "wiki_revision_url": f"https://en.wikipedia.org/w/index.php?oldid={match['revid']}",
            "wiki_match_method": "VERIFIED_FULL_NORMALIZED_RENDERED",
            "wiki_match_status": "VERIFIED_HISTORICAL_NEW_EVIDENCE",
            "wiki_revision_evidence": json.dumps(
                {
                    "page_or_parse_evidence": match["evidence"],
                    "revision_metadata": match["metadata_evidence"],
                    "evidence_kind": match["evidence_kind"],
                },
                sort_keys=True,
            ),
        }
    v2 = pq.read_table(v2_path)
    v3 = write_new(apply_updates(v2, updates, statuses), target)
    accepted = pa.array([value is not None for value in v2["wiki_page_id"].to_pylist()])
    assert v3.filter(accepted).equals(v2.filter(accepted), check_metadata=True)
    raw_columns = [name for name in v2.column_names if not name.startswith("wiki_")]
    assert v3.select(raw_columns).equals(v2.select(raw_columns), check_metadata=True)
    assert sha256(v2_path) == v2_digest
    with (output / "unresolved_rows.csv").open(
        "x", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["row_index", "Source", "Text", "status"]
        )
        writer.writeheader()
        for key, item in pending.items():
            if key not in matches:
                writer.writerows(
                    {
                        "row_index": index,
                        "Source": key[0],
                        "Text": key[1],
                        "status": statuses[key],
                    }
                    for index in item["raw_row_indices"]
                )
    summary = {
        "input_rows": v2.num_rows,
        "previous_accepted_rows_preserved": v2.num_rows - v2["wiki_page_id"].null_count,
        "searched_pairs_only": len(pending),
        "searched_raw_rows_only": len(rows),
        "newly_resolved_pairs": len(matches),
        "newly_resolved_rows": sum(pending[key]["rows"] for key in matches),
        "assigned_rows": v3.num_rows - v3["wiki_page_id"].null_count,
        "unresolved_rows": v3["wiki_page_id"].null_count,
        "statuses": dict(Counter(v3["wiki_match_status"].to_pylist())),
        "input_sha256": v2_digest,
        "output_sha256": sha256(target),
        "limit": limit,
        "new_api_calls": client.new_calls,
        "v2_accepted_rows_unchanged": True,
        "raw_values_unchanged": True,
        "entity_extraction_run": False,
        "accepted_passages_rematched": False,
    }
    save_json(output / "summary.json", summary)
    checkpoint("export_complete")
    LOG.info("Export complete: %s", json.dumps(summary))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    main()
