"""Add the smallest useful context split to an unresolved relation group."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.model_selection import GroupKFold

HERE = Path(__file__).resolve().parent
INPUT = HERE / "context_split_poc" / "cases.csv"
OUTPUT = HERE / "incremental_distinct_summary.json"
MIN_PAIRS = 3
MIN_OBJECTS = 2


def features(row: dict[str, str]) -> set[str]:
    values = {
        f"{side}_type_{qid}"
        for side, column in (("subject", "subject_p31"), ("object", "object_p31"))
        for qid in row[column].split("|")
        if qid
    }
    values.update(
        f"source_{graph}"
        for graph in row["eventkg_graphs"].split("|")
        if graph not in {"event_kg", "wikidata", "source_unknown"}
    )
    return values


def partition(rows: list[dict], selected: list[str]) -> dict:
    groups: dict[tuple[bool, ...], list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(field in row["features"] for field in selected)].append(row)
    return groups


def mixed_pairs(groups: dict) -> int:
    return sum(
        len(group)
        for group in groups.values()
        if len({row["wikidata_observed"] for row in group}) > 1
    )


def supported(group: list[dict]) -> bool:
    return (
        len(group) >= MIN_PAIRS and len({r["object_qid"] for r in group}) >= MIN_OBJECTS
    )


def choose_fields(
    rows: list[dict], initial: tuple[str, ...] = ()
) -> tuple[list[str], list[dict]]:
    """Use the fewest new groups that reduce code-set ambiguity; then stop."""
    selected = list(initial)
    steps: list[dict] = []
    counts = Counter(feature for row in rows for feature in row["features"])
    candidates = sorted(
        feature
        for feature, count in counts.items()
        if MIN_PAIRS <= count <= len(rows) - MIN_PAIRS
    )
    while True:
        old_groups = partition(rows, selected)
        old_mixed = mixed_pairs(old_groups)
        options = []
        for field in candidates:
            if field in selected:
                continue
            new_groups = partition(rows, [*selected, field])
            added_groups = len(new_groups) - len(old_groups)
            if added_groups == 0:
                continue
            # A split made from one object or a few pairs does not define a reusable case.
            if any(not supported(group) for group in new_groups.values()):
                continue
            reduction = old_mixed - mixed_pairs(new_groups)
            if reduction > 0:
                options.append((added_groups, -reduction, field, new_groups))
        if not options:
            break
        added, negative_reduction, field, new_groups = min(options, key=lambda x: x[:3])
        selected.append(field)
        steps.append(
            {
                "field": field,
                "added_groups": added,
                "groups": len(new_groups),
                "mixed_pairs": mixed_pairs(new_groups),
                "ambiguity_reduction": -negative_reduction,
                "consistent_supported_pairs": sum(
                    len(group)
                    for group in new_groups.values()
                    if len({row["wikidata_observed"] for row in group}) == 1
                ),
            }
        )
    return selected, steps


def held_out_check(rows: list[dict]) -> dict:
    applied = correct = 0
    folds = []
    for fold, (train_ids, test_ids) in enumerate(
        GroupKFold(n_splits=5).split(rows, groups=[r["object_qid"] for r in rows]),
        start=1,
    ):
        train = [rows[i] for i in train_ids]
        test = [rows[i] for i in test_ids]
        selected, _ = choose_fields(train)
        rules = partition(train, selected)
        fold_applied = fold_correct = 0
        for row in test:
            key = tuple(field in row["features"] for field in selected)
            group = rules.get(key, [])
            if supported(group) and len({r["wikidata_observed"] for r in group}) == 1:
                fold_applied += 1
                fold_correct += (
                    group[0]["wikidata_observed"] == row["wikidata_observed"]
                )
        applied += fold_applied
        correct += fold_correct
        folds.append(
            {
                "fold": fold,
                "test_pairs": len(test),
                "selected_fields": selected,
                "rule_applications": fold_applied,
                "correct_recorded_code_sets": fold_correct,
            }
        )
    return {
        "rule_applications": applied,
        "correct_recorded_code_sets": correct,
        "folds": folds,
    }


def main() -> None:
    with INPUT.open(encoding="utf-8", newline="") as stream:
        all_rows = list(csv.DictReader(stream))
    rows = [row for row in all_rows if row["wikidata_observed"] != "unrecorded"]
    for row in rows:
        row["features"] = features(row)
    selected, steps = choose_fields(rows)
    summary = {
        "source_role": "EventKG hasPlace",
        "pairs": len(all_rows),
        "coded_pairs": len(rows),
        "unrecorded_pairs": len(all_rows) - len(rows),
        "minimum_pairs_per_group": MIN_PAIRS,
        "minimum_object_qids_per_group": MIN_OBJECTS,
        "candidate_fields": len({field for row in rows for field in row["features"]}),
        "start_mixed_pairs": mixed_pairs(partition(rows, [])),
        "selected_fields": selected,
        "steps": steps,
        "stop_reason": "no unused field creates a supported split and reduces mixed coded pairs",
        "held_out_by_object": held_out_check(rows),
    }
    OUTPUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
