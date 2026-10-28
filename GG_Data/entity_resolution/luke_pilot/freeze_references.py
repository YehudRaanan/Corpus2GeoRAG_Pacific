"""Convert prediction-free source review decisions into frozen pilot references."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from data import normalized, read_jsonl, sha256, write_jsonl


def freeze(inputs: Path, decisions: Path) -> dict:
    sample = read_jsonl(inputs / "sample.jsonl")
    proposals = {r["id"]: r for r in read_jsonl(inputs / "reference_proposals.jsonl")}
    reviewed = json.loads(decisions.read_text(encoding="utf-8"))
    refs = []
    seen_pages = set()
    generic = {"and", "of", "the", "in", "in the", "s", "people", "officer", "investors", "century"}
    for i, row in enumerate(sample):
        page = str(row["wiki_page_id"])
        decision = reviewed["pages"][page]
        seen_pages.add(page)
        low, high = decision["reviewed_indices"]
        if not low <= i <= high:
            raise ValueError(f"Review row ordering changed: {i}")
        pool = {c["id"] for c in row["candidates"]}
        anchors = proposals[row["id"]]["proposed_direct_anchor_qids"]
        verified = i not in decision["unverified"]
        target, method = None, "SOURCE_CONTEXT_REVIEW_POOL_ABSENT"
        if (decision["accept_reviewed_direct_anchors"] and len(anchors) == 1
                and i not in decision.get("reject_direct_indices", [])):
            target, method = anchors[0], "CONTEXT_REVIEWED_SAVED_ANCHOR"
        if str(i) in decision["links"]:
            target, method = decision["links"][str(i)], "SOURCE_CONTEXT_REVIEW_ALIAS_OR_COREFERENCE"
        if target is not None and target not in pool:
            raise ValueError(f"Reference outside page pool: {row['id']} {target}")
        if not verified:
            target, method = None, "UNVERIFIED_AMBIGUOUS_SPAN_OR_IDENTITY"
        elif target is None and row["type"] == "DATE":
            method = "SOURCE_CONTEXT_REVIEW_DATE_ABSENT_FROM_POOL"
        elif target is None and normalized(row["mention"]) in generic:
            method = "SOURCE_CONTEXT_REVIEW_GENERIC_OR_INVALID_SPAN"
        assert decision["remaining_reviewed_are_none"]
        refs.append({"id": row["id"], "target": target, "verified": verified,
                     "reference_method": method, "reference_notes": decision["notes"],
                     "source_contexts": row["contexts"], "source_page_id": row["wiki_page_id"],
                     "source_revision_id": row["wiki_revision_id"], "mention": row["mention"],
                     "type": row["type"], "review_row_index": i,
                     "saved_anchor_qids": anchors, "labelled_before_predictions": True,
                     "reviewer": "assistant source review; not independent human annotation"})
    assert seen_pages == set(reviewed["pages"]) and len(refs) == 642
    path = inputs / "references.jsonl"
    write_jsonl(path, refs)
    manifest = {"sha256": sha256(path), "decision_sha256": sha256(decisions),
                "sample_sha256": sha256(inputs / "sample.jsonl"),
                "frozen_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "records": len(refs), "verified": sum(r["verified"] for r in refs),
                "verified_linked": sum(r["verified"] and r["target"] is not None for r in refs),
                "verified_none": sum(r["verified"] and r["target"] is None for r in refs),
                "unverified": sum(not r["verified"] for r in refs),
                "policy": reviewed["policy"], "no_predictions_consulted": True}
    (inputs / "reference_freeze.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--decisions", type=Path, default=Path(__file__).with_name("reference_decisions.json"))
    args = p.parse_args()
    print(json.dumps(freeze(args.inputs, args.decisions), indent=2))
