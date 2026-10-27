"""Audit incremental recovery without matching any previously accepted passage."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from attach_source_page_ids import normalize, read_json, render_text, save_json, sha256
from export_wiki_revision_versions import verify_saved_evidence


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    staged = root / "source_page_versions_staged_20261027"
    output = root / "source_page_versions_history_20261027"
    for directory in [
        root / "source_page_ids_20261026",
        root / "source_page_ids_history_pilot_20261027",
        staged,
    ]:
        verify_saved_evidence(directory)
    assert read_json(output / "progress.json")["phase"] == "export_complete"
    old_path = next(staged.glob("*_v2_revision_metadata.parquet"))
    new_path = next(output.glob("*_v3_historical_continuation.parquet"))
    summary = read_json(output / "summary.json")
    assert sha256(old_path) == summary["input_sha256"]
    assert sha256(new_path) == summary["output_sha256"]
    old, new = pq.read_table(old_path), pq.read_table(new_path)
    assert old.num_rows == new.num_rows == 309864
    assert old.schema.equals(new.schema, check_metadata=True)
    accepted = pa.array([x is not None for x in old["wiki_page_id"].to_pylist()])
    assert old.filter(accepted).equals(new.filter(accepted), check_metadata=True)
    raw = [name for name in old.column_names if not name.startswith("wiki_")]
    assert old.select(raw).equals(new.select(raw), check_metadata=True)
    previous, current = old.to_pydict(), new.to_pydict()
    pending = {(x["Source"], x["Text"]): x for x in read_json(output / "pending.json")}
    matches = {(x["Source"], x["Text"]): x for x in read_json(output / "matches.json")}
    assert len(pending) == 414 and sum(x["rows"] for x in pending.values()) == 5922
    assert matches.keys() <= pending.keys()
    changed_rows = set()
    for key, item in pending.items():
        assert item["rows"] == len(item["raw_row_indices"])
        for index in item["raw_row_indices"]:
            assert previous["wiki_page_id"][index] is None
            assert (current["Source"][index], current["Text"][index]) == key
        if key not in matches:
            continue
        match = matches[key]
        assert item["context"]["pageids"] == [match["pageid"]]
        if not item["context"]["direct"]:
            assert len(normalize(key[1])) >= 50 and len(key[1].split()) >= 8
        evidence = read_json(Path(match["evidence"]))
        if match["evidence_kind"] == "parse_response":
            assert evidence["ok"]
            assert evidence["params"]["oldid"] == match["revid"]
            parsed = json.loads(evidence["response_text"])["parse"]
            assert parsed["pageid"] == match["pageid"]
            assert parsed["revid"] == match["revid"]
            body = render_text(parsed["text"])
        else:
            assert match["evidence_kind"] == "saved_page_cache"
            assert evidence["pageid"] == match["pageid"]
            assert evidence["lastrevid"] == match["revid"]
            body = evidence["rendered"]
        assert normalize(key[1]) in normalize(body)
        meta = read_json(Path(match["metadata_evidence"]))
        assert meta["ok"]
        pages = json.loads(meta["response_text"])["query"]["pages"]
        bound = [
            (page, rev)
            for page in pages
            for rev in page.get("revisions", [])
            if rev["revid"] == match["revid"]
        ]
        assert len(bound) == 1
        page, rev = bound[0]
        assert page["pageid"] == match["pageid"] and page["ns"] == 0
        assert rev["timestamp"] == match["timestamp"]
        for index in item["raw_row_indices"]:
            assert current["wiki_page_id"][index] == match["pageid"]
            assert current["wiki_page_title"][index] == match["title"]
            assert current["wiki_revision_id"][index] == match["revid"]
            assert current["wiki_revision_timestamp"][index].isoformat() == match[
                "timestamp"
            ].replace("Z", "+00:00")
            assert current["wiki_revision_url"][index] == (
                f"https://en.wikipedia.org/w/index.php?oldid={match['revid']}"
            )
            assert current["wiki_match_status"][index] == (
                "VERIFIED_HISTORICAL_NEW_EVIDENCE"
            )
            refs = json.loads(current["wiki_revision_evidence"][index])
            assert refs["page_or_parse_evidence"] == match["evidence"]
            assert refs["revision_metadata"] == match["metadata_evidence"]
            assert (
                current["wiki_text_sha256"][index]
                == hashlib.sha256(key[1].encode()).hexdigest()
            )
            changed_rows.add(index)
    metadata = [
        "wiki_page_title",
        "wiki_revision_id",
        "wiki_revision_timestamp",
        "wiki_revision_url",
        "wiki_match_method",
        "wiki_revision_evidence",
    ]
    for index, pageid in enumerate(current["wiki_page_id"]):
        assert all(
            (current[name][index] is None) == (pageid is None) for name in metadata
        )
        if previous["wiki_page_id"][index] is None:
            assert (pageid is not None) == (index in changed_rows)
    assert len(changed_rows) == summary["newly_resolved_rows"]
    entities = set(zip(current["word"], current["entity_group"]))
    assert len(entities) == 74339
    records = [read_json(path) for path in (output / "requests").glob("*.gz")]
    result = {
        "verified": True,
        "rows": new.num_rows,
        "previous_accepted_rows_unchanged": old.num_rows
        - old["wiki_page_id"].null_count,
        "original_values_order_schema_metadata_unchanged": True,
        "new_pairs_full_text_and_revision_evidence_verified": len(matches),
        "new_rows_verified": len(changed_rows),
        "remaining_pairs": len(pending) - len(matches),
        "remaining_rows": new["wiki_page_id"].null_count,
        "distinct_entity_name_type_pairs": len(entities),
        "entity_types": dict(Counter(kind for _, kind in entities)),
        "saved_new_requests": len(records),
        "failed_new_requests": sum(not x["ok"] for x in records),
        "summed_new_request_seconds": sum(x["elapsed_seconds"] for x in records),
        "accepted_passages_rematched": False,
        "entity_extraction_run": False,
    }
    save_json(output / "verification.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
