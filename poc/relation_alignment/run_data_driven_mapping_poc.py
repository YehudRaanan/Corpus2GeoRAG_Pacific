"""Rank relation mappings from instance evidence, without label features."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DISCOVERY = ROOT / "mapping_discovery"
CATALOG = ROOT / "relation_catalog_eda"
CONTEXT = ROOT / "context_split_poc"
OUT = ROOT / "data_driven_mapping_poc"

SAMPLE_GROUPS = {
    ("award", "dbpedia_en", "entity", "entity", "reified"),
    ("battle", "dbpedia_en", "entity", "event", "reified"),
    ("country", "dbpedia_en", "entity", "entity", "reified"),
    ("hasPlace", "dbpedia_en", "event", "entity", "direct"),
    ("hasPlace", "yago", "event", "entity", "direct"),
    ("hasWonPrize", "yago", "entity", "entity", "reified"),
    ("isCitizenOf", "yago", "entity", "entity", "reified"),
    ("hasSubEvent", "source_unknown", "event", "event", "direct"),
    ("subEventOf", "source_unknown", "event", "event", "direct"),
    ("usedInWar", "dbpedia_en", "entity", "event", "reified"),
}

GROUP_FIELDS = ("ek_role", "ek_graph", "subject_kind", "object_kind", "format")
NUMERIC_SCORE_FIELDS = (
    "shared_pairs",
    "pct_of_ek_co_connected",
    "after_largest_target_pct",
    "test_pairs",
    "test_pct_of_ek_co_connected",
)


def evidence_score(row: dict[str, str]) -> float:
    """Return a name-blind score from repeated endpoint evidence."""
    shared = int(row["shared_pairs"])
    coverage = float(row["pct_of_ek_co_connected"]) / 100
    robust = float(row["after_largest_target_pct"]) / 100
    held_out = float(row["test_pct_of_ek_co_connected"]) / 100
    support = min(shared / 100, 1)
    return round(
        100 * (0.45 * coverage + 0.25 * robust + 0.20 * held_out + 0.10 * support), 1
    )


def evidence_status(row: dict[str, str]) -> str:
    """Apply statistical gates; names and definitions are not inputs."""
    shared = int(row["shared_pairs"])
    coverage = float(row["pct_of_ek_co_connected"])
    robust = float(row["after_largest_target_pct"])
    held_out = float(row["test_pct_of_ek_co_connected"])
    distinct_targets = int(row["distinct_targets"])
    if shared < 20 or int(row["test_pairs"]) < 5 or distinct_targets < 5:
        return "INSUFFICIENT_SUPPORT"
    if coverage >= 90 and robust >= 80 and held_out >= 80:
        return "STRONG_CANDIDATE"
    if coverage >= 50 and robust >= 70:
        return "PROMISING_BUT_MIXED"
    return "MIXED_RELATION"


def compose_direction(first: str, second: str) -> str:
    return "same" if first == second else "reverse"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    candidates = read_csv(DISCOVERY / "eventkg_wikidata_candidates.csv")
    metadata = json.loads(
        (CATALOG / "wikidata_property_metadata.json").read_text(encoding="utf-8")
    )["properties"]

    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        key = tuple(row[field] for field in GROUP_FIELDS)
        if key in SAMPLE_GROUPS:
            grouped[key].append(row)

    rankings = []
    decisions = []
    top_by_group = {}
    for key in sorted(grouped):
        ranked = sorted(grouped[key], key=evidence_score, reverse=True)
        top_by_group[key] = ranked[0]
        for rank, row in enumerate(ranked[:5], start=1):
            prop = row["wd_property"]
            rankings.append(
                {
                    **{field: row[field] for field in GROUP_FIELDS},
                    "rank": rank,
                    "wd_property": prop,
                    "wd_label_for_review_only": metadata.get(prop, {}).get("label", ""),
                    "direction": row["direction"],
                    **{field: row[field] for field in NUMERIC_SCORE_FIELDS},
                    "distinct_targets": row["distinct_targets"],
                    "evidence_score": evidence_score(row),
                    "evidence_status": evidence_status(row),
                }
            )
        top, second = ranked[0], ranked[1] if len(ranked) > 1 else None
        status = evidence_status(top)
        margin = (
            round(evidence_score(top) - evidence_score(second), 1) if second else 100.0
        )
        decisions.append(
            {
                **dict(zip(GROUP_FIELDS, key, strict=True)),
                "top_wd_property": top["wd_property"],
                "top_direction": top["direction"],
                "top_score": evidence_score(top),
                "runner_up": second["wd_property"] if second else "",
                "score_margin": margin,
                "decision": status,
                "automatic_action": (
                    "PROVISIONAL_MAP"
                    if status == "STRONG_CANDIDATE" and margin >= 15
                    else "KEEP_UNRESOLVED"
                ),
            }
        )

    war_paths = []
    for row in read_csv(DISCOVERY / "warsampo_eventkg_candidates.csv"):
        ek_key = tuple(row[field] for field in GROUP_FIELDS)
        top = top_by_group.get(ek_key)
        if not top or evidence_status(top) != "STRONG_CANDIDATE":
            continue
        support = int(row["shared_pairs"])
        war_paths.append(
            {
                "war_predicate": row["war_predicate"],
                "via_eventkg_predicate": row["ek_role"],
                "candidate_wd_property": top["wd_property"],
                "composed_direction": compose_direction(
                    row["direction"], top["direction"]
                ),
                "war_eventkg_shared_pairs": support,
                "eventkg_wikidata_score": evidence_score(top),
                "decision": (
                    "PROVISIONAL_MAP" if support >= 20 else "INSUFFICIENT_SUPPORT"
                ),
            }
        )

    context = json.loads((CONTEXT / "summary.json").read_text(encoding="utf-8"))
    summary = {
        "method": "name-blind endpoint evidence with endpoint-kind and source-graph context",
        "sample_groups": len(grouped),
        "candidate_rows_ranked": len(rankings),
        "provisional_eventkg_wikidata_maps": sum(
            row["automatic_action"] == "PROVISIONAL_MAP" for row in decisions
        ),
        "unresolved_eventkg_groups": sum(
            row["automatic_action"] == "KEEP_UNRESOLVED" for row in decisions
        ),
        "warsampo_transitive_paths": len(war_paths),
        "warsampo_paths_with_enough_support": sum(
            row["decision"] == "PROVISIONAL_MAP" for row in war_paths
        ),
        "hasplace_context_check": {
            "pairs": context["pairs"],
            "coded_pairs": context["labeled_pairs"],
            "type_only_cv_exact_match": context["grouped_cv_types_only"][
                "tree_exact_match"
            ],
            "all_context_cv_exact_match": context["grouped_cv_all_features"][
                "tree_exact_match"
            ],
            "result": "context helps but does not resolve hasPlace",
        },
        "predicate_names_used_in_score": False,
        "source_data_modified": False,
    }

    OUT.mkdir(exist_ok=True)
    write_csv(OUT / "candidate_rankings.csv", rankings)
    write_csv(OUT / "group_decisions.csv", decisions)
    write_csv(OUT / "warsampo_transitive_candidates.csv", war_paths)
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
