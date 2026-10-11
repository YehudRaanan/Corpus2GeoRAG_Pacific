"""Small, source-preserving context split for EventKG hasPlace collisions.

The Wikidata properties are observed codes, not semantic truth labels.
Run after the local EventKG events, entities, and relations_events_base files
have complete manifests. No full-corpus relation extraction is performed.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.cluster import KMeans
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier, export_text

import run_mapping_discovery as discovery

OUT = Path(__file__).resolve().parent / "context_split_poc"
TARGET_PROPERTIES = {"P17", "P276", "P710"}


def eventkg_pairs(resource_to_qid: dict[str, str], kind: dict[str, str]) -> dict:
    if not discovery.complete("relations_events_base"):
        raise RuntimeError("EventKG relations_events_base is incomplete")
    rows: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"graphs": set(), "eventkg_ids": set()}
    )
    for subject, predicate, target, graph in discovery.direct_edges(
        "relations_events_base"
    ):
        if discovery.short(predicate) != "hasPlace":
            continue
        qs, qt = resource_to_qid.get(subject), resource_to_qid.get(target)
        if qs and qt and kind.get(qs) == "event" and kind.get(qt) == "entity":
            pair = (qs, qt)
            rows[pair]["graphs"].add(discovery.short(graph))
            rows[pair]["eventkg_ids"].add(discovery.short(subject))
    return {pair: row for pair, row in rows.items() if "event_kg" in row["graphs"]}


def wikidata_context(qids: set[str]) -> dict[str, dict]:
    context: dict[str, dict] = {}
    with gzip.open(
        discovery.BASE / "wikidata_entities.jsonl.gz", "rt", encoding="utf-8"
    ) as stream:
        for line in stream:
            record = json.loads(line)
            qid = record["requested_qid"]
            if qid not in qids:
                continue
            entity = record.get("entity", {})
            types = set()
            for statement in entity.get("claims", {}).get("P31", []):
                if statement.get("rank") == "deprecated":
                    continue
                value = statement.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(value, dict) and value.get("entity-type") == "item":
                    types.add(value["id"])
            context[qid] = {
                "types": types,
                "label": entity.get("labels", {}).get("en", {}).get("value", ""),
            }
    if qids - context.keys():
        raise RuntimeError("Missing Wikidata context for selected QIDs")
    return context


def feature_dict(pair: tuple[str, str], info: dict, context: dict) -> dict[str, int]:
    subject, target = pair
    features = {f"subject_type_{qid}": 1 for qid in context[subject]["types"]}
    features.update({f"object_type_{qid}": 1 for qid in context[target]["types"]})
    features.update(
        {
            f"source_{graph}": 1
            for graph in info["graphs"]
            if graph not in {"event_kg", "wikidata", "source_unknown"}
        }
    )
    return features


def observed_signature(properties: set[str]) -> str:
    """An absent code is unrecorded, never a confirmed negative relation."""
    return "|".join(sorted(properties & TARGET_PROPERTIES)) or "unrecorded"


def grouped_tree_check(matrix, labeled, groups, ordered_pairs, signatures) -> dict:
    folds = []
    actual, predicted, baseline_predicted = [], [], []
    out_of_fold = {}
    for fold_number, (train_local, test_local) in enumerate(
        GroupKFold(n_splits=5).split(labeled, groups=groups), start=1
    ):
        train = [labeled[i] for i in train_local]
        test = [labeled[i] for i in test_local]
        train_objects = {ordered_pairs[i][1] for i in train}
        test_objects = {ordered_pairs[i][1] for i in test}
        assert train_objects.isdisjoint(test_objects)
        model = DecisionTreeClassifier(
            max_depth=2, min_samples_leaf=12, random_state=42
        )
        model.fit(matrix[train], [signatures[i] for i in train])
        fold_actual = [signatures[i] for i in test]
        fold_predicted = model.predict(matrix[test]).tolist()
        out_of_fold.update(zip(test, fold_predicted, strict=True))
        baseline = Counter(signatures[i] for i in train).most_common(1)[0][0]
        actual.extend(fold_actual)
        predicted.extend(fold_predicted)
        baseline_predicted.extend([baseline] * len(test))
        folds.append(
            {
                "fold": fold_number,
                "train_pairs": len(train),
                "test_pairs": len(test),
                "test_objects": len(test_objects),
                "baseline_exact_match": round(
                    accuracy_score(fold_actual, [baseline] * len(test)), 3
                ),
                "tree_exact_match": round(
                    accuracy_score(fold_actual, fold_predicted), 3
                ),
            }
        )
    return {
        "folds": folds,
        "baseline_exact_match": round(accuracy_score(actual, baseline_predicted), 3),
        "tree_exact_match": round(accuracy_score(actual, predicted), 3),
        "observed_signatures": dict(Counter(actual)),
        "predicted_signatures": dict(Counter(predicted)),
        "out_of_fold": out_of_fold,
    }


def main(include_wikidata_only: bool = False) -> None:
    resource_to_qid, kind = discovery.resource_qids()
    all_pairs = eventkg_pairs(resource_to_qid, kind)
    pairs = {
        pair: info
        for pair, info in all_pairs.items()
        if include_wikidata_only or info["graphs"] & {"yago", "dbpedia_en"}
    }
    population = set(
        (discovery.BASE / "wikidata_qids.txt").read_text(encoding="utf-8").splitlines()
    )
    wd, _ = discovery.wd_pairs(population)
    qids = {qid for pair in pairs for qid in pair}
    context = wikidata_context(qids)
    ordered_pairs = sorted(pairs)
    feature_rows = [feature_dict(pair, pairs[pair], context) for pair in ordered_pairs]
    signatures = [observed_signature(wd.get(pair, set())) for pair in ordered_pairs]

    # Keep only features found on several pairs. This selection uses no labels.
    feature_counts = Counter(key for row in feature_rows for key in row)
    features = {
        key for key, count in feature_counts.items() if 10 <= count <= len(pairs) - 10
    }
    vectors = [{key: 1 for key in row if key in features} for row in feature_rows]
    encoder = DictVectorizer(sparse=False)
    matrix = encoder.fit_transform(vectors)
    if not matrix.shape[1]:
        raise RuntimeError("No context features meet the support floor")

    clusters = KMeans(n_clusters=3, n_init=20, random_state=42).fit_predict(matrix)
    cluster_signatures = defaultdict(Counter)
    for cluster, signature in zip(clusters, signatures, strict=True):
        cluster_signatures[int(cluster)][signature] += 1

    labeled = [i for i, signature in enumerate(signatures) if signature != "unrecorded"]
    groups = [ordered_pairs[i][1] for i in labeled]
    names = list(encoder.get_feature_names_out())
    full_check = grouped_tree_check(matrix, labeled, groups, ordered_pairs, signatures)
    out_of_fold = full_check.pop("out_of_fold")
    type_columns = [i for i, name in enumerate(names) if "_type_" in name]
    source_columns = [i for i, name in enumerate(names) if name.startswith("source_")]
    type_check = grouped_tree_check(
        matrix[:, type_columns], labeled, groups, ordered_pairs, signatures
    )
    source_check = grouped_tree_check(
        matrix[:, source_columns], labeled, groups, ordered_pairs, signatures
    )
    source_check.pop("out_of_fold")
    type_check.pop("out_of_fold")
    tree = DecisionTreeClassifier(max_depth=2, min_samples_leaf=12, random_state=42)
    tree.fit(matrix[labeled], [signatures[i] for i in labeled])

    OUT.mkdir(exist_ok=True)
    case_rows = []
    for i, (subject, target) in enumerate(ordered_pairs):
        case_rows.append(
            {
                "event_qid": subject,
                "event_label": context[subject]["label"],
                "object_qid": target,
                "object_label": context[target]["label"],
                "eventkg_ids": "|".join(
                    sorted(pairs[(subject, target)]["eventkg_ids"])
                ),
                "eventkg_graphs": "|".join(sorted(pairs[(subject, target)]["graphs"])),
                "subject_p31": "|".join(sorted(context[subject]["types"])),
                "object_p31": "|".join(sorted(context[target]["types"])),
                "wikidata_observed": signatures[i],
                "cluster": int(clusters[i]),
                "tree_leaf": int(tree.apply(matrix[i : i + 1])[0]),
                "cv_predicted_signature": out_of_fold.get(i, ""),
            }
        )
    prefix = "all_sources_" if include_wikidata_only else ""
    with (OUT / f"{prefix}cases.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=case_rows[0])
        writer.writeheader()
        writer.writerows(case_rows)
    summary = {
        "eventkg_role": "hasPlace",
        "eventkg_graph": "event_kg",
        "scope": (
            "all_fused_pairs" if include_wikidata_only else "non_wikidata_source_pairs"
        ),
        "all_fused_pairs": len(all_pairs),
        "wikidata_only_source_pairs_total": sum(
            not info["graphs"] & {"yago", "dbpedia_en"} for info in all_pairs.values()
        ),
        "wikidata_only_pairs_with_selected_code": sum(
            observed_signature(wd.get(pair, set())) != "unrecorded"
            for pair, info in all_pairs.items()
            if not info["graphs"] & {"yago", "dbpedia_en"}
        ),
        "wikidata_only_source_pairs_excluded": len(all_pairs) - len(pairs),
        "non_wikidata_graph_rule": "has yago or dbpedia_en hasPlace graph",
        "pairs": len(pairs),
        "objects": len({target for _, target in pairs}),
        "observed_signatures": dict(Counter(signatures)),
        "largest_object": Counter(target for _, target in pairs).most_common(1)[0],
        "historical_country_pairs": sum(
            "Q3024240" in context[target]["types"] for _, target in pairs
        ),
        "context_features": matrix.shape[1],
        "feature_support_floor": 10,
        "cluster_observed_signatures": {
            str(cluster): dict(counts)
            for cluster, counts in sorted(cluster_signatures.items())
        },
        "tree": export_text(tree, feature_names=names),
        "tree_leaf_observed_signatures": {
            str(leaf): dict(
                Counter(
                    row["wikidata_observed"]
                    for row in case_rows
                    if row["tree_leaf"] == leaf
                )
            )
            for leaf in sorted({row["tree_leaf"] for row in case_rows})
        },
        "labeled_pairs": len(labeled),
        "labeled_objects": len(set(groups)),
        "grouped_cv_all_features": full_check,
        "grouped_cv_types_only": type_check,
        "grouped_cv_sources_only": source_check,
    }
    (OUT / f"{prefix}summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-wikidata-only",
        action="store_true",
        help="Reproduce the broad control that retains Wikidata-only place links",
    )
    main(parser.parse_args().include_wikidata_only)
