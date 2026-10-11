"""Test whether graph context separates EventKG `country` relation meanings."""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

import run_mapping_discovery as discovery
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier, export_text

OUT = Path(__file__).resolve().parent / "country_context_poc"
TARGETS = {"P17", "P8047"}
EXCLUDED_CONTEXT = TARGETS | {"P31", "P279"}
SUPPORT_FLOOR = 10


def country_pairs() -> set[tuple[str, str]]:
    resource_to_qid, kind = discovery.resource_qids()
    pairs = set()
    for name in discovery.REIFIED:
        if not discovery.complete(name):
            continue
        for _, graph, role, subject, target in discovery.reified_groups(name):
            if (
                discovery.short(role) != "country"
                or discovery.short(graph) != "dbpedia_en"
            ):
                continue
            qs, qt = resource_to_qid.get(subject), resource_to_qid.get(target)
            if qs and qt and kind.get(qs) == kind.get(qt) == "entity":
                pairs.add((qs, qt))
    return pairs


def item_claims(entity: dict):
    for prop, statements in entity.get("claims", {}).items():
        for statement in statements:
            if statement.get("rank") == "deprecated":
                continue
            value = statement.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(value, dict) and value.get("entity-type") == "item":
                yield prop, value["id"]


def wikidata_context(
    pairs: set[tuple[str, str]],
) -> tuple[dict, dict, dict, dict, dict]:
    endpoints = {qid for pair in pairs for qid in pair}
    pair_properties: dict[tuple[str, str], set[str]] = defaultdict(set)
    direct_types: dict[str, set[str]] = defaultdict(set)
    neighbor_properties: dict[str, set[str]] = defaultdict(set)
    parents: dict[str, set[str]] = defaultdict(set)
    labels = {}
    with gzip.open(
        discovery.BASE / "wikidata_entities.jsonl.gz", "rt", encoding="utf-8"
    ) as stream:
        for line in stream:
            record = json.loads(line)
            qid = record["requested_qid"]
            entity = record.get("entity", {})
            labels[qid] = entity.get("labels", {}).get("en", {}).get("value", "")
            claims = list(item_claims(entity))
            for prop, target in claims:
                if prop == "P279":
                    parents[qid].add(target)
                if qid not in endpoints:
                    continue
                if prop == "P31":
                    direct_types[qid].add(target)
                elif prop not in EXCLUDED_CONTEXT:
                    neighbor_properties[qid].add(prop)
                if (qid, target) in pairs and prop in TARGETS:
                    pair_properties[(qid, target)].add(prop)
    parent_types = {
        qid: {parent for type_qid in types for parent in parents.get(type_qid, set())}
        for qid, types in direct_types.items()
    }
    return pair_properties, direct_types, parent_types, neighbor_properties, labels


def signature(properties: set[str]) -> str:
    return "|".join(sorted(properties & TARGETS)) or "unrecorded"


def features(
    pair: tuple[str, str],
    direct_types: dict[str, set[str]],
    parent_types: dict[str, set[str]],
    neighbors: dict[str, set[str]],
) -> dict[str, int]:
    subject, target = pair
    result = {f"S_TYPE_{qid}": 1 for qid in direct_types.get(subject, set())}
    result.update({f"O_TYPE_{qid}": 1 for qid in direct_types.get(target, set())})
    result.update({f"S_PARENT_{qid}": 1 for qid in parent_types.get(subject, set())})
    result.update({f"O_PARENT_{qid}": 1 for qid in parent_types.get(target, set())})
    result.update(
        {
            f"S_PROP_{prop}": 1
            for prop in neighbors.get(subject, set())
            if prop not in EXCLUDED_CONTEXT
        }
    )
    result.update(
        {
            f"O_PROP_{prop}": 1
            for prop in neighbors.get(target, set())
            if prop not in EXCLUDED_CONTEXT
        }
    )
    return result


def fit_models(matrix, observed, indices) -> dict[str, DecisionTreeClassifier]:
    models = {}
    for code in sorted(TARGETS):
        model = DecisionTreeClassifier(
            max_depth=4,
            min_samples_leaf=20,
            class_weight="balanced",
            random_state=42,
        )
        model.fit(matrix[indices], [int(code in observed[i]) for i in indices])
        models[code] = model
    return models


def predict_signatures(models, matrix) -> list[str]:
    by_code = {code: model.predict(matrix).tolist() for code, model in models.items()}
    return [
        "|".join(code for code in sorted(TARGETS) if by_code[code][i]) or "unresolved"
        for i in range(matrix.shape[0])
    ]


def evaluate(matrix, labels, groups, indices) -> tuple[dict, dict[int, str]]:
    actual, predicted, baseline_predictions = [], [], []
    out_of_fold = {}
    folds = []
    splitter = GroupKFold(n_splits=min(5, len(set(groups))))
    for fold, (train_local, test_local) in enumerate(
        splitter.split(indices, groups=groups), start=1
    ):
        train = [indices[i] for i in train_local]
        test = [indices[i] for i in test_local]
        models = fit_models(matrix, labels, train)
        fold_actual = [labels[i] for i in test]
        fold_predicted = predict_signatures(models, matrix[test])
        baseline_codes = [
            code
            for code in sorted(TARGETS)
            if sum(code in labels[i] for i in train) >= len(train) / 2
        ]
        baseline = (
            "|".join(baseline_codes)
            or Counter(labels[i] for i in train).most_common(1)[0][0]
        )
        actual.extend(fold_actual)
        predicted.extend(fold_predicted)
        baseline_predictions.extend([baseline] * len(test))
        out_of_fold.update(zip(test, fold_predicted, strict=True))
        folds.append(
            {
                "fold": fold,
                "train_pairs": len(train),
                "test_pairs": len(test),
                "held_out_type_groups": len({groups[i] for i in test_local}),
                "exact_match": round(accuracy_score(fold_actual, fold_predicted), 3),
            }
        )
    actual_binary = [
        [int(code in value) for code in sorted(TARGETS)] for value in actual
    ]
    predicted_binary = [
        [int(code in value) for code in sorted(TARGETS)] for value in predicted
    ]
    precision, recall, f1, support = precision_recall_fscore_support(
        actual_binary, predicted_binary, average=None, zero_division=0
    )
    signature_recall = {
        value: {
            "correct": sum(
                expected == predicted_value
                for expected, predicted_value in zip(actual, predicted, strict=True)
                if expected == value
            ),
            "total": actual.count(value),
        }
        for value in sorted(set(actual))
    }
    return (
        {
            "folds": folds,
            "exact_match": round(accuracy_score(actual, predicted), 3),
            "macro_label_f1": round(
                f1_score(
                    actual_binary,
                    predicted_binary,
                    average="macro",
                    zero_division=0,
                ),
                3,
            ),
            "per_label": {
                code: {
                    "precision": round(float(precision[i]), 3),
                    "recall": round(float(recall[i]), 3),
                    "f1": round(float(f1[i]), 3),
                    "support": int(support[i]),
                }
                for i, code in enumerate(sorted(TARGETS))
            },
            "baseline_exact_match": round(
                accuracy_score(actual, baseline_predictions), 3
            ),
            "actual": dict(Counter(actual)),
            "predicted": dict(Counter(predicted)),
            "signature_exact_counts": signature_recall,
        },
        out_of_fold,
    )


def main() -> None:
    pairs = sorted(country_pairs())
    pair_props, direct_types, parent_types, neighbors, labels = wikidata_context(
        set(pairs)
    )
    observed = [signature(pair_props.get(pair, set())) for pair in pairs]
    raw_features = [
        features(pair, direct_types, parent_types, neighbors) for pair in pairs
    ]
    counts = Counter(key for row in raw_features for key in row)
    allowed = {
        key
        for key, count in counts.items()
        if SUPPORT_FLOOR <= count <= len(pairs) - SUPPORT_FLOOR
    }
    vectors = [{key: 1 for key in row if key in allowed} for row in raw_features]
    encoder = DictVectorizer(sparse=True)
    matrix = encoder.fit_transform(vectors)
    feature_names = list(encoder.get_feature_names_out())

    coded = [i for i, value in enumerate(observed) if value != "unrecorded"]
    type_groups = [
        "|".join(sorted(direct_types.get(pairs[i][0], set()))) or "UNTYPED"
        for i in coded
    ]
    type_columns = [
        i
        for i, name in enumerate(feature_names)
        if "_TYPE_" in name or "_PARENT_" in name
    ]
    context_columns = [i for i, name in enumerate(feature_names) if "_PROP_" in name]
    without_p137_columns = [
        i for i, name in enumerate(feature_names) if name != "S_PROP_P137"
    ]
    all_check, out_of_fold = evaluate(matrix, observed, type_groups, coded)
    type_check, _ = evaluate(matrix[:, type_columns], observed, type_groups, coded)
    context_check, _ = evaluate(
        matrix[:, context_columns], observed, type_groups, coded
    )
    p137_ablation_check, _ = evaluate(
        matrix[:, without_p137_columns], observed, type_groups, coded
    )

    models = fit_models(matrix, observed, coded)
    final_predictions = predict_signatures(models, matrix)
    probabilities = {
        code: model.predict_proba(matrix)[:, list(model.classes_).index(1)].tolist()
        for code, model in models.items()
    }
    leaves = {code: model.apply(matrix).tolist() for code, model in models.items()}
    leaf_support = {
        code: Counter(model.apply(matrix[coded]).tolist())
        for code, model in models.items()
    }

    property_meta = json.loads(
        (
            Path(__file__).resolve().parent
            / "relation_catalog_eda/wikidata_property_metadata.json"
        ).read_text(encoding="utf-8")
    )["properties"]

    def feature_label(name: str) -> str:
        identifier = name.rsplit("_", 1)[-1]
        if identifier.startswith("P"):
            return property_meta.get(identifier, {}).get("label", "")
        return labels.get(identifier, "")

    importance = []
    for code, model in models.items():
        importance.extend(
            {
                "target_code": code,
                "feature": feature_names[i],
                "review_label": feature_label(feature_names[i]),
                "importance": round(float(value), 4),
                "support": counts[feature_names[i]],
            }
            for i, value in sorted(
                enumerate(model.feature_importances_),
                key=lambda item: item[1],
                reverse=True,
            )
            if value > 0
        )

    cases = []
    for i, (subject, target) in enumerate(pairs):
        predicted = final_predictions[i]
        provisional_codes = [
            code
            for code in sorted(TARGETS)
            if probabilities[code][i] >= 0.8
            and leaf_support[code][leaves[code][i]] >= 20
        ]
        provisional = "|".join(provisional_codes)
        if observed[i] != "unrecorded":
            action = "OBSERVED_CODE"
        elif provisional:
            action = "CANDIDATE_FOR_TEXT_CHECK"
        else:
            action = "UNRESOLVED"
        cases.append(
            {
                "subject_qid": subject,
                "subject_label": labels.get(subject, ""),
                "object_qid": target,
                "object_label": labels.get(target, ""),
                "subject_p31": "|".join(sorted(direct_types.get(subject, set()))),
                "subject_parent_types": "|".join(
                    sorted(parent_types.get(subject, set()))
                ),
                "subject_has_p137": "P137" in neighbors.get(subject, set()),
                "observed_wikidata_codes": observed[i],
                "oof_prediction": out_of_fold.get(i, ""),
                "final_model_prediction": predicted,
                "p17_probability": round(probabilities["P17"][i], 3),
                "p8047_probability": round(probabilities["P8047"][i], 3),
                "provisional_prediction": provisional,
                "action": action,
            }
        )

    summary = {
        "eventkg_relation": "country",
        "eventkg_graph": "dbpedia_en",
        "pair_count": len(pairs),
        "coded_pairs": len(coded),
        "unrecorded_pairs": len(pairs) - len(coded),
        "observed_signatures": dict(Counter(observed)),
        "direct_subject_type_groups": len(set(type_groups)),
        "features": len(feature_names),
        "type_features": len(type_columns),
        "neighbor_property_features": len(context_columns),
        "support_floor": SUPPORT_FLOOR,
        "grouping_rule": "hold out complete direct-subject-P31 signatures",
        "all_features": all_check,
        "types_only": type_check,
        "neighbor_properties_only": context_check,
        "without_subject_p137": p137_ablation_check,
        "top_features": {
            code: [row for row in importance if row["target_code"] == code][:10]
            for code in sorted(TARGETS)
        },
        "trees": {
            code: export_text(model, feature_names=feature_names)
            for code, model in models.items()
        },
        "unrecorded_actions": dict(
            Counter(
                row["action"]
                for row in cases
                if row["observed_wikidata_codes"] == "unrecorded"
            )
        ),
        "p137_by_observed_signature": {
            value: {
                "present": sum(
                    observed[i] == value and "P137" in neighbors.get(pairs[i][0], set())
                    for i in range(len(pairs))
                ),
                "absent": sum(
                    observed[i] == value
                    and "P137" not in neighbors.get(pairs[i][0], set())
                    for i in range(len(pairs))
                ),
            }
            for value in sorted(set(observed))
        },
        "unrecorded_predictions_are_accepted": False,
        "relation_names_used_as_features": False,
        "target_codes_used_as_features": False,
        "source_data_modified": False,
    }

    OUT.mkdir(exist_ok=True)
    with (OUT / "cases.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cases[0]))
        writer.writeheader()
        writer.writerows(cases)
    with (OUT / "feature_importance.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(importance[0]))
        writer.writeheader()
        writer.writerows(importance)
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
