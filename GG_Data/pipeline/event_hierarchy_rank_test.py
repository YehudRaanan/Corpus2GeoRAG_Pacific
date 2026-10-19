"""User-approved diagnostic: Event hierarchy without deprecated statements.

Population S2T 7: this is a comparison only. The non-deprecated rule was later
approved for Event classification; historical diagnostic artifacts stay intact.
Read complete saved P31/P279 evidence; never retrieve or change source records,
matching, Entities, Relations, or accepted Event classifications.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from GG_Data.pipeline.events import classify_events, hierarchy_path
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.relations import SourceException


def compare(edges: dict) -> list[dict]:
    """Compare all ranks with non-deprecated P31 and P279, without mutation."""
    approved = {row["qid"]: row["paths"] for row in classify_events(edges)}
    result = []
    for qid, rows in edges["P31"].items():
        original, tested = [], approved[qid]
        for row in rows:
            path = hierarchy_path(row["parent"], edges["P279"])
            if path is not None:
                original.append(dict(P31=row, P279=path))
        result.append(
            dict(
                qid=qid,
                all_ranks_match=bool(original),
                non_deprecated_match=bool(tested),
                non_deprecated_paths=tested,
            )
        )
    return result


def run(source: Path, output: Path) -> dict:
    """Protect the complete source probe and write a distinct diagnostic output."""
    verification = read_json(source / "verification.json")
    for name, sha in verification["outputs"].items():
        if digest(source / name) != sha:
            raise SourceException("Rank-test source checksum mismatch", file=name)
    edges = read_json(source / "hierarchy_edges.json")
    results = compare(edges)
    output.mkdir(parents=True, exist_ok=False)
    (output / "comparison.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    before = {r["qid"] for r in results if r["all_ranks_match"]}
    after = {r["qid"] for r in results if r["non_deprecated_match"]}
    assert after <= before
    report = dict(
        status="DIAGNOSTIC_ONLY",
        source=str(source),
        source_edges_sha256=digest(source / "hierarchy_edges.json"),
        candidates=len(results),
        all_ranks_matches=len(before),
        non_deprecated_matches=len(after),
        removed=sorted(before - after, key=lambda q: int(q[1:])),
        event_rows_written=0,
        classification_rule_changed=False,
        network_requests=0,
        comparison_sha256=digest(output / "comparison.json"),
    )
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.source, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "removed"}))
