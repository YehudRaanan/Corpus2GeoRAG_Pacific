"""Build an exhaustive Level 1 to Level 2 option map from the local catalog."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, top_k_accuracy_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import FeatureUnion, Pipeline

HERE = Path(__file__).resolve().parent
INPUT = HERE / "relation_catalog_eda"
OUT = HERE / "level1_level2_full_map"
REPORT = HERE / "FULL_LEVEL1_LEVEL2_MAP_2026-10-11.md"
UNASSIGNED = "UNASSIGNED_REVIEW"

# These meanings stay separate in the catalog. The group affects evaluation only.
EVALUATION_GROUPS = {
    "wd:P17": "COUNTRY_ASSOCIATION",
    "wd:P495": "COUNTRY_ASSOCIATION",
    "wd:P8047": "COUNTRY_ASSOCIATION",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows for {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def relation_text(row: dict[str, str]) -> str:
    """Use all available semantic text without changing the source relation."""
    predicates = row["source_predicates"].replace("|", " ").replace("_", " ")
    return " ".join(
        [
            row["label"],
            row["label"],
            row["description"],
            predicates,
            row["sources"].replace("|", " "),
        ]
    )


def classifier() -> Pipeline:
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    strip_accents="unicode",
                    sublinear_tf=True,
                ),
            ),
            (
                "character",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                    sublinear_tf=True,
                ),
            ),
        ]
    )
    return Pipeline(
        [
            ("features", features),
            (
                "model",
                LogisticRegression(
                    C=4,
                    class_weight="balanced",
                    max_iter=4000,
                    random_state=42,
                ),
            ),
        ]
    )


def source_statistics(inventory: list[dict[str, str]]) -> list[dict]:
    rows = []
    for source in sorted({row["source"] for row in inventory}):
        members = [row for row in inventory if row["source"] == source]
        eligible = [row for row in members if row["eligibility"] == "LEVEL2_CANDIDATE"]
        rows.append(
            {
                "source": source,
                "predicate_rows": len(members),
                "eligible_relation_rows": len(eligible),
                "excluded_rows": len(members) - len(eligible),
                "observed_rows": sum(
                    row["observation_status"] == "OBSERVED" for row in members
                ),
                "defined_not_observed_rows": sum(
                    row["observation_status"] == "DEFINED_NOT_OBSERVED"
                    for row in members
                ),
                "canonical_level2_ids": len(
                    {row["canonical_level2_id"] for row in eligible}
                ),
                "eligible_occurrences_sum": sum(
                    int(row["occurrence_count"]) for row in eligible
                ),
                "independent_occurrences_sum": sum(
                    int(row["independent_occurrence_count"]) for row in eligible
                ),
            }
        )
    return rows


def build(
    input_dir: Path = INPUT,
    output_dir: Path = OUT,
    report_path: Path = REPORT,
) -> dict:
    relations = read_csv(input_dir / "level2_relations.csv")
    inventory = read_csv(input_dir / "source_predicate_inventory.csv")
    base_summary = json.loads((input_dir / "summary.json").read_text(encoding="utf-8"))

    assigned = [row for row in relations if row["level1_family"] != UNASSIGNED]
    unresolved = [row for row in relations if row["level1_family"] == UNASSIGNED]
    families = sorted({row["level1_family"] for row in assigned})
    texts = [relation_text(row) for row in assigned]
    labels = [row["level1_family"] for row in assigned]

    model = classifier()
    folds = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)
    cv_probabilities = cross_val_predict(
        model, texts, labels, cv=folds, method="predict_proba"
    )
    cv_classes = sorted(set(labels))
    cv_predictions = [cv_classes[index] for index in cv_probabilities.argmax(axis=1)]
    cv = {
        "method": "4-fold stratified cross-validation on existing catalog families",
        "training_rows": len(assigned),
        "accuracy": round(float(accuracy_score(labels, cv_predictions)), 6),
        "macro_f1": round(
            float(f1_score(labels, cv_predictions, average="macro")), 6
        ),
        "top3_accuracy": round(
            float(
                top_k_accuracy_score(
                    labels,
                    cv_probabilities,
                    k=3,
                    labels=cv_classes,
                )
            ),
            6,
        ),
    }

    model.fit(texts, labels)
    model_classes = list(model.named_steps["model"].classes_)
    unresolved_probabilities = model.predict_proba(
        [relation_text(row) for row in unresolved]
    )

    ranked_by_id: dict[str, list[tuple[str, float]]] = {}
    candidate_rows = []
    for row, probabilities in zip(unresolved, unresolved_probabilities, strict=True):
        ranking = sorted(
            zip(model_classes, probabilities, strict=True),
            key=lambda item: (-item[1], item[0]),
        )
        ranked_by_id[row["canonical_level2_id"]] = ranking
        for rank, (family, score) in enumerate(ranking, start=1):
            candidate_rows.append(
                {
                    "canonical_level2_id": row["canonical_level2_id"],
                    "label": row["label"],
                    "candidate_rank": rank,
                    "candidate_level1_family": family,
                    "ranking_score": f"{score:.6f}",
                    "candidate_status": "RANKED_FOR_REVIEW",
                }
            )

    map_rows = []
    for row in relations:
        relation_id = row["canonical_level2_id"]
        if row["level1_family"] == UNASSIGNED:
            ranking = ranked_by_id[relation_id]
            selected_family = ranking[0][0]
            top_score = ranking[0][1]
            score_margin = ranking[0][1] - ranking[1][1]
            status = "RANKED_REVIEW_REQUIRED"
            options = "|".join(
                f"{family}:{score:.6f}" for family, score in ranking
            )
        else:
            selected_family = row["level1_family"]
            top_score = 1.0
            score_margin = 1.0
            status = "EXISTING_CATALOG_ASSIGNMENT"
            options = selected_family
        map_rows.append(
            {
                "level1_family": selected_family,
                "canonical_level2_id": relation_id,
                "level2_label": row["label"],
                "level2_description": row["description"],
                "assignment_status": status,
                "top_ranking_score": f"{top_score:.6f}",
                "top_score_margin": f"{score_margin:.6f}",
                "all_ranked_level1_options": options,
                "evaluation_acceptance_group": EVALUATION_GROUPS.get(
                    relation_id, ""
                ),
                "sources": row["sources"],
                "source_predicates": row["source_predicates"],
                "source_occurrences_sum": row["source_occurrences_sum"],
                "independent_occurrences_sum": row["independent_occurrences_sum"],
                "mapping_statuses": row["mapping_statuses"],
                "source_mapping_requires_review": row["requires_review"],
            }
        )
    map_rows.sort(key=lambda row: (row["level1_family"], row["canonical_level2_id"]))

    family_members: dict[str, list[dict]] = defaultdict(list)
    for row in map_rows:
        family_members[row["level1_family"]].append(row)
    family_rows = []
    for family in families:
        members = family_members[family]
        sources = Counter(
            source for row in members for source in row["sources"].split("|")
        )
        family_rows.append(
            {
                "level1_family": family,
                "existing_level2_count": sum(
                    row["assignment_status"] == "EXISTING_CATALOG_ASSIGNMENT"
                    for row in members
                ),
                "ranked_review_level2_count": sum(
                    row["assignment_status"] == "RANKED_REVIEW_REQUIRED"
                    for row in members
                ),
                "total_level2_count": len(members),
                "source_occurrences_sum": sum(
                    int(row["source_occurrences_sum"]) for row in members
                ),
                "independent_occurrences_sum": sum(
                    int(row["independent_occurrences_sum"]) for row in members
                ),
                "eventkg_level2_count": sources["EventKG"],
                "wikidata_level2_count": sources["Wikidata"],
                "warsampo_level2_count": sources["WarSampo"],
                "low_separation_review_count": sum(
                    row["assignment_status"] == "RANKED_REVIEW_REQUIRED"
                    and float(row["top_score_margin"]) < 0.10
                    for row in members
                ),
            }
        )

    evaluation_rows = [
        {
            "evaluation_acceptance_group": "COUNTRY_ASSOCIATION",
            "canonical_level2_id": relation_id,
            "label": next(
                row["label"]
                for row in relations
                if row["canonical_level2_id"] == relation_id
            ),
            "evaluation_rule": "NON_FAILURE_FOR_PROJECT_EVALUATION",
            "catalog_rule": "KEEP_AS_DISTINCT_LEVEL2",
        }
        for relation_id in ("wd:P17", "wd:P495", "wd:P8047")
    ]
    source_rows = source_statistics(inventory)

    eligible_inventory = [
        row for row in inventory if row["eligibility"] == "LEVEL2_CANDIDATE"
    ]
    summary = {
        "scope": {
            "wikidata_population_qids": base_summary["population_qids"],
            "eventkg_mapped_qids": base_summary["eventkg_mapped_qids"],
            "warsampo_scope": "full local release",
        },
        "source_predicate_rows": len(inventory),
        "eligible_source_relation_rows": len(eligible_inventory),
        "excluded_source_predicate_rows": len(inventory) - len(eligible_inventory),
        "eligible_rows_represented_in_map": sum(
            row["canonical_level2_id"]
            in {member["canonical_level2_id"] for member in map_rows}
            for row in eligible_inventory
        ),
        "distinct_level2_relations": len(map_rows),
        "distinct_level1_families": len(families),
        "existing_family_assignments": len(assigned),
        "ranked_review_assignments": len(unresolved),
        "unmapped_level2_relations": 0,
        "evaluation_groups": 1,
        "evaluation_group_members": len(evaluation_rows),
        "family_ranking_validation": cv,
        "family_rankings_are_accepted_mappings": False,
        "entity_pair_classifier_run": False,
        "source_data_modified": False,
    }

    write_csv(output_dir / "level1_level2_map.csv", map_rows)
    write_csv(output_dir / "level1_candidate_rankings.csv", candidate_rows)
    write_csv(output_dir / "level1_statistics.csv", family_rows)
    write_csv(output_dir / "source_statistics.csv", source_rows)
    write_csv(output_dir / "evaluation_acceptable_options.csv", evaluation_rows)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    family_table = "\n".join(
        f"| {row['level1_family']} | {row['existing_level2_count']} | "
        f"{row['ranked_review_level2_count']} | {row['total_level2_count']} |"
        for row in family_rows
    )
    source_table = "\n".join(
        f"| {row['source']} | {row['predicate_rows']} | "
        f"{row['eligible_relation_rows']} | {row['excluded_rows']} | "
        f"{row['canonical_level2_ids']} |"
        for row in source_rows
    )
    report = f"""# Full Level 1 to Level 2 relation map

Date: 2026-10-11

## Result

The map contains all **{len(map_rows):,} distinct Level 2 relations** in the
current local relation inventory. It represents all **{len(eligible_inventory):,}
eligible source relation rows**. No eligible source relation is absent.

The source meanings remain separate. In particular, Wikidata `P17` country,
`P495` country of origin, and `P8047` country of registry are three Level 2
relations. They share only the `COUNTRY_ASSOCIATION` non-failure group for
project evaluation.

## Assignment status

- {len(assigned):,} Level 2 relations retain their existing Level 1 family.
- {len(unresolved):,} Level 2 relations have ranked family options and require
  review.
- 0 Level 2 relations are missing from the output.
- The ranker does not accept or merge a relation.
- No entity-pair relation classifier was run.

The four-fold check on the existing assignments produced
**{cv['accuracy']:.1%} exact family accuracy** and **{cv['top3_accuracy']:.1%}
top-three family coverage**. These figures measure how well the ranker repeats
the existing catalog rules. They do not prove that those rules are correct.

## Level 1 statistics

| Level 1 family | Existing | Ranked review | Total options |
|---|---:|---:|---:|
{family_table}

## Source coverage

| Source | Predicate rows | Eligible relations | Excluded | Canonical Level 2 IDs |
|---|---:|---:|---:|---:|
{source_table}

The Wikidata scope is {base_summary['population_qids']:,} World War II task
force QIDs. EventKG maps {base_summary['eventkg_mapped_qids']:,} of those QIDs
and uses all local relation files. WarSampo uses the full local release.

## Files

- `level1_level2_map.csv`: one row per Level 2 relation, with its current or
  proposed Level 1 family and full provenance.
- `level1_candidate_rankings.csv`: all {len(families)} family options for every
  relation that still needs family review.
- `level1_statistics.csv`: counts and occurrence totals per Level 1 family.
- `source_statistics.csv`: source inventory and coverage counts.
- `evaluation_acceptable_options.csv`: non-failure options kept separate from
  the semantic catalog.
- `summary.json`: machine-readable totals and validation statistics.

## Use rule

The complete catalog prevents an observed source relation from disappearing.
The ranked Level 1 family can order review work, but it cannot remove a Level 2
option from later relation selection. An unknown future predicate must enter a
new review row instead of being forced into an existing relation.
"""
    report_path.write_text(report, encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
