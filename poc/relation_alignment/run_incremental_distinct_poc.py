"""Test whether added context fields yield reusable relation-code groups."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from sklearn.model_selection import GroupKFold

HERE = Path(__file__).resolve().parent
INPUT = HERE / "context_split_poc" / "cases.csv"
OUTPUT = HERE / "incremental_distinct_summary.json"
MIN_SUPPORT = 3
STAGES = [
    ("no context", ()),
    ("object types", ("object_p31",)),
    ("object types + source", ("object_p31", "source")),
    ("object types + source + event types", ("object_p31", "source", "subject_p31")),
    (
        "plus both IDs (overfit check)",
        ("object_p31", "source", "subject_p31", "event_qid", "object_qid"),
    ),
]


def key(row: dict[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(row[field] for field in fields)


def groups_for(rows: list[dict[str, str]], fields: tuple[str, ...]) -> dict:
    groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for row in rows:
        groups[key(row, fields)].append(row["wikidata_observed"])
    return groups


def measure(rows: list[dict[str, str]], fields: tuple[str, ...]) -> dict:
    groups = groups_for(rows, fields)
    object_groups: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for row in rows:
        object_groups[key(row, fields)].add(row["object_qid"])
    folds = GroupKFold(n_splits=5)
    applied = correct = 0
    for train, test in folds.split(rows, groups=[r["object_qid"] for r in rows]):
        training = groups_for([rows[i] for i in train], fields)
        for i in test:
            labels = training.get(key(rows[i], fields), [])
            if len(labels) >= MIN_SUPPORT and len(set(labels)) == 1:
                applied += 1
                correct += labels[0] == rows[i]["wikidata_observed"]
    return {
        "groups": len(groups),
        "singleton_pairs": sum(len(v) for v in groups.values() if len(v) == 1),
        "mixed_pairs": sum(len(v) for v in groups.values() if len(set(v)) > 1),
        "supported_consistent_pairs": sum(
            len(v)
            for v in groups.values()
            if len(v) >= MIN_SUPPORT and len(set(v)) == 1
        ),
        "supported_pairs_across_objects": sum(
            len(v)
            for group, v in groups.items()
            if len(v) >= MIN_SUPPORT
            and len(set(v)) == 1
            and len(object_groups[group]) >= 2
        ),
        "held_out_rules_applied": applied,
        "held_out_correct_code_sets": correct,
    }


def main() -> None:
    with INPUT.open(encoding="utf-8", newline="") as stream:
        all_rows = list(csv.DictReader(stream))
    rows = [row for row in all_rows if row["wikidata_observed"] != "unrecorded"]
    for row in rows:
        row["source"] = "|".join(
            sorted(
                set(row["eventkg_graphs"].split("|"))
                - {"event_kg", "wikidata", "source_unknown"}
            )
        )
    summary = {
        "source_role": "EventKG hasPlace",
        "pairs": len(all_rows),
        "coded_pairs": len(rows),
        "unrecorded_pairs": len(all_rows) - len(rows),
        "minimum_rule_support": MIN_SUPPORT,
        "test": "5-fold object-QID-held-out; exact recorded Wikidata code set",
        "stages": [
            {"stage": name, "fields": fields, **measure(rows, fields)}
            for name, fields in STAGES
        ],
    }
    OUTPUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
