"""Offline test of Daniel page count / existing Wikipedia incoming-link count.

Approved diagnostic, 20 October 2026. Population S2T sections 4/5 and frozen
matching decisions remain unchanged. Only the existing English probe is used:
English source page IDs in the 10K sample form the numerator, current English
CirrusSearch counts form the denominator. This is not an identity confidence,
an all-language measure, or a snapshot-aligned share of Wikipedia backlinks.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict

from GG_Data.pipeline.incoming_links_probe import BASE
from GG_Data.pipeline.poc import ROOT, digest, read_json


def relevance_rows(mentions: list[dict], counts: list[dict]) -> list[dict]:
    """Repeated mentions and types do not add pages; missing/zero stays unknown."""
    pages = defaultdict(set)
    occurrences = defaultdict(int)
    names = defaultdict(set)
    for mention in mentions:
        if mention["wiki_site"] != "enwiki":
            continue
        qid = mention.get("entity_id")
        page_id = mention.get("wiki_page_id")
        if not isinstance(page_id, int) or isinstance(page_id, bool):
            raise ValueError("English mention lacks a resolved page ID")
        pages[qid].add(page_id)
        occurrences[qid] += 1
        names[qid].add(mention["raw"]["word"])
    result = []
    for row in counts:
        qid, denominator = row["qid"], row["incoming_links"]
        if denominator is not None and (
            type(denominator) is not int or denominator < 0
        ):
            raise ValueError("Invalid incoming-link count")
        if not pages[qid]:
            raise ValueError(f"No English Daniel source page for {qid}")
        numerator = len(pages[qid])
        result.append(
            {
                "qid": qid,
                "name": row["title"],
                "daniel_english_pages_in_10k": numerator,
                "daniel_english_mentions_in_10k": occurrences[qid],
                "original_names": sorted(names[qid]),
                "english_incoming_links": denominator,
                "relevance": numerator / denominator if denominator else None,
                "score_status": "SCORED" if denominator else "UNKNOWN_DENOMINATOR",
            }
        )
    return sorted(
        result, key=lambda r: (r["relevance"] is None, -(r["relevance"] or 0), r["qid"])
    )


def run() -> dict:
    prior = BASE / "poc_10k_misc_incoming_links_probe_20261020"
    mentions = BASE / "poc_10k/mentions.json.gz"
    source = prior / "partial_analysis.json"
    output = BASE / "poc_10k_misc_relevance_probe_20261020"
    if output.exists():
        raise ValueError("Keep previous diagnostic evidence unchanged")
    manifest = read_json(prior / "report.json")
    if digest(source) != manifest["outputs"][source.name]:
        raise ValueError("Saved count analysis changed")
    if digest(mentions) != manifest["inputs"][str(mentions.relative_to(ROOT))]:
        raise ValueError("Frozen Daniel mentions changed")
    rows = relevance_rows(read_json(mentions), read_json(source)["counts"])
    report = {
        "status": "OFFLINE_RATIO_TEST_ONLY",
        "formula": "distinct English Daniel page IDs / English incoming_links",
        "numerator_scope": "FROZEN_10K_SAMPLE_ALL_TYPES_COUNTED_ONCE_PER_QID_AND_PAGE",
        "denominator_scope": "SAVED_CURRENT_ENGLISH_CIRRUSSEARCH_RESPONSE",
        "network_requests": 0,
        "matches_changed": False,
        "filter_applied": False,
        "scored_qids": sum(r["relevance"] is not None for r in rows),
        "unknown_qids": sum(r["relevance"] is None for r in rows),
        "rows": rows,
        "limits": [
            "Selected diagnostic sample, not an accuracy estimate.",
            "Existing QID matching errors also affect the numerator.",
            "Small denominators can inflate the score.",
            "Current counts and historical matching are not snapshot-aligned.",
            "Daniel mentions and Wikipedia hyperlinks are different observations.",
        ],
        "inputs": {
            str(p.relative_to(ROOT)): digest(p)
            for p in (mentions, source, prior / "report.json")
        },
    }
    output.mkdir()
    with (output / "scores.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report["outputs"] = {"scores.csv": digest(output / "scores.csv")}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
