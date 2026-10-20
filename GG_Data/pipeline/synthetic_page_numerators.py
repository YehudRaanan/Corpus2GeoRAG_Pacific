"""Add existing synthetic IDs using Daniel's own source-page relationships.

Approved follow-up to the page-link diagnostic: the four missing source pages
still have Daniel mentions. Count their non-date synthetic IDs on those source
titles without inventing a Wikipedia page ID, QID, or global denominator.
Population S2T sections 4/5: preserve original mentions and saved assignments.
"""

import csv
import gzip
import json
from collections import Counter
from pathlib import Path

import ijson

from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.snapshot_link_relevance_probe import BASE


def synthetic_row(row: dict, sources: set[str]) -> dict | None:
    """Use original Source, not string matching or a guessed missing page ID."""
    raw = row["raw"]
    if (
        raw["Source"] not in sources
        or row["matched_stage"] != "SYNTHETIC"
        or raw["entity_group"] == "DATE"
    ):
        return None
    if not row["assigned_id"].startswith("SYN_") or not row.get("unresolved_reason"):
        raise ValueError("Invalid saved synthetic identity or missing reason")
    return {
        "entity_id": row["assigned_id"],
        "qid": None,
        "name": raw["word"],
        "entity_type": raw["entity_group"],
        "scope_page_count": 1,
        "all_linking_pages": None,
        "relevance": None,
        "numerator_source": "DANIEL_SOURCE_RELATIONSHIP",
        "source_title": raw["Source"],
        "wiki_page_id": None,
        "page_resolution_status": "MISSING_PAGE",
        "mention_id": row["mention_id"],
        "input_row_number": row["input_row_number"],
        "unresolved_reason": row["unresolved_reason"],
    }


def run() -> dict:
    prior = BASE / "poc_10k_misc_snapshot_link_relevance_20261020/report.json"
    saved = read_json(prior)
    sources = set(saved["missing_source_titles"])
    cache = Path.home() / ".cache/geoai_full_daniel_dump_bigquery_parallel_20261019"
    matches = cache / "matches.json.gz"
    manifest_path, summary_path = cache / "manifest.json", cache / "summary.json"
    manifest, summary = read_json(manifest_path), read_json(summary_path)
    match_hash = digest(matches)
    if match_hash != manifest["outputs"][matches.name]:
        raise ValueError("Saved matching file checksum changed")
    rows, stages, total = [], Counter(), 0
    with gzip.open(matches, "rb") as stream:
        for row in ijson.items(stream, "item"):
            total += 1
            stages[row["matched_stage"]] += 1
            if result := synthetic_row(row, sources):
                rows.append(result)
    if total != summary["mentions"] or dict(stages) != summary["stages"]:
        raise ValueError("Full matching coverage changed")
    if len({r["entity_id"] for r in rows}) != len(rows):
        raise ValueError("Expected one existing synthetic ID per mention")
    counts = Counter(r["source_title"] for r in rows)
    # These are the verified four-page counts discussed with the user.
    if dict(counts) != {
        "BUROGU": 34,
        "Conscription in Japan": 45,
        "Gabriel Maur\u00edcio Teixeira": 54,
        "Two Lords Incident": 1,
    }:
        raise ValueError("Synthetic population differs from the approved scope")
    output = BASE / "missing_pages_synthetic_numerators_20261020"
    output.mkdir()  # Refuse to overwrite existing evidence.
    for path, expected in saved["outputs"].items():
        if digest(prior.parent / path) != expected:
            raise ValueError("Original QID diagnostic output changed")
    # QID counts remain actual links; synthetic counts use Daniel's Source.
    # These evidence types stay explicit and are never added to each other.
    combined = [
        {
            "entity_id": r["qid"],
            "qid": r["qid"],
            "name": r["name"],
            "scope_page_count": r["scope_linking_pages"],
            "all_linking_pages": r["all_linking_pages"],
            "relevance": r["relevance"],
            "numerator_source": "WIKIPEDIA_SNAPSHOT_LINKS",
        }
        for r in saved["rows"]
    ] + rows
    with (output / "numerators.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = list(dict.fromkeys(k for r in combined for k in r))
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(combined)
    report = {
        "status": "COMPLETE_SYNTHETIC_PAGE_NUMERATORS_UNKNOWN_DENOMINATORS",
        "source_scope": sorted(sources),
        "verified_daniel_mentions": total,
        "synthetic_entities": len(rows),
        "synthetic_entities_by_source": dict(counts),
        "existing_qid_rows": len(saved["rows"]),
        "rows": combined,
        "limits": [
            "Synthetic numerators use Daniel source titles, not verified page links.",
            "Missing page IDs, QIDs, denominators and relevance remain null.",
            "Dates excluded; each existing synthetic mention keeps its separate ID.",
        ],
        "matches_changed": False,
        "filter_applied": False,
        "network_requests": 0,
        "inputs": {
            str(p): digest(p)
            for p in (prior, matches, manifest_path, summary_path, Path(__file__))
        },
        "outputs": {"numerators.csv": digest(output / "numerators.csv")},
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {k: v for k, v in report.items() if k != "rows"}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
