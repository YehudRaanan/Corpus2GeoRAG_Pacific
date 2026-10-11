"""Run the adaptive distinct process with all usable complete local fields.

Identifiers and the target Wikidata properties are join/evaluation data, not
predictors. Incomplete EventKG directories are reported and skipped.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

from run_incremental_distinct_poc import (
    choose_fields,
    held_out_check,
    mixed_pairs,
    partition,
)

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = ROOT / "Data" / "external" / "wwii_task_force"
EK = BASE / "eventkg_v3_2"
INPUT = HERE / "context_split_poc" / "cases.csv"
OUTPUT = HERE / "all_fields_distinct_summary.json"
ASSIGNMENTS = HERE / "all_fields_distinct_assignments.csv"

TARGET_PROPERTIES = {"P17", "P276", "P710"}
WIKIDATA_GRAPH = "https://eventkg.l3s.uni-hannover.de/graph/wikidata"
COMPLETE_DIRECT = (
    "events",
    "entities",
    "preferred_labels",
    "relations_events_base",
    "relations_entities_base",
    "events_first_sentences",
    "events_descriptions_from_text_events",
    "types",
    "types_dbpedia",
    "types_wikidata",
    "text_events",
)
COMPLETE_REIFIED = (
    "relations_events_other",
    "relations_events_literals",
    "relations_entities_temporal",
    "text_event_links",
)
KNOWN_INCOMPLETE = (
    "entity_links",
    "entity_mentions",
    "event_links",
    "event_mentions",
    "relations_entities_other",
)

URI = re.compile(r"^<([^>]+)>$")
LINE = re.compile(r"^<([^>]+)> <([^>]+)> (.+?)(?: <([^>]+)>)? \.$")
LITERAL = re.compile(r'^"((?:[^"\\]|\\.)*)"(?:@([A-Za-z0-9-]+)|\^\^<([^>]+)>)?$')
TOKEN = re.compile(r"[^\W_]{3,}", re.UNICODE)
YEAR = re.compile(r"^[+-]?(\d{3,4})")

RDF_SUBJECT = "http://www.w3.org/1999/02/22-rdf-syntax-ns#subject"
RDF_OBJECT = "http://www.w3.org/1999/02/22-rdf-syntax-ns#object"
ROLE_TYPE = "http://semanticweb.cs.vu.nl/2009/11/sem/roleType"
TEXT_PREDICATES = {
    "http://www.w3.org/2004/02/skos/core#prefLabel",
    "http://www.w3.org/2000/01/rdf-schema#label",
    "http://purl.org/dc/terms/description",
}
STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "has",
    "into",
    "its",
    "that",
    "the",
    "their",
    "this",
    "was",
    "were",
    "with",
}


def short(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    if value <= 3:
        return "2_3"
    if value <= 10:
        return "4_10"
    return "11_plus"


def tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in TOKEN.findall(text)
        if token.casefold() not in STOPWORDS
    }


def parse_line(line: str) -> tuple[str, str, str, str | None] | None:
    match = LINE.match(line.rstrip("\n"))
    return match.groups() if match else None


def parse_object(value: str) -> tuple[str, str, str | None]:
    match = URI.match(value)
    if match:
        return "uri", match.group(1), None
    match = LITERAL.match(value)
    if match:
        raw, language, datatype = match.groups()
        text = bytes(raw, "utf-8").decode("unicode_escape") if "\\" in raw else raw
        return "literal", text, language or datatype
    return "other", value, None


def wikidata_value_features(prefix: str, prop: str, value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict) and value.get("entity-type"):
        if value.get("id"):
            result.add(f"{prefix}:wd:value:{prop}={value['id']}")
        return result
    if isinstance(value, dict) and "time" in value:
        year_match = YEAR.match(str(value["time"]).lstrip("+"))
        result.add(
            f"{prefix}:wd:time_precision:{prop}={value.get('precision', 'unknown')}"
        )
        if year_match:
            year = int(year_match.group(1))
            result.add(f"{prefix}:wd:time_decade:{prop}={year // 10 * 10}")
        return result
    if isinstance(value, dict) and {"latitude", "longitude"} <= value.keys():
        lat, lon = float(value["latitude"]), float(value["longitude"])
        result.update(
            {
                f"{prefix}:wd:coordinate:{prop}",
                f"{prefix}:wd:lat_band:{prop}={math.floor(lat / 10) * 10}",
                f"{prefix}:wd:lon_band:{prop}={math.floor(lon / 10) * 10}",
            }
        )
        return result
    if isinstance(value, dict) and "amount" in value:
        try:
            amount = abs(float(value["amount"]))
            magnitude = "zero" if amount == 0 else str(math.floor(math.log10(amount)))
        except (ValueError, OverflowError):
            magnitude = "unknown"
        result.add(f"{prefix}:wd:quantity_magnitude:{prop}={magnitude}")
        unit = value.get("unit")
        if unit and unit != "1":
            result.add(f"{prefix}:wd:quantity_unit:{prop}={short(unit)}")
        return result
    if isinstance(value, dict) and "text" in value:
        language = value.get("language", "unknown")
        result.add(f"{prefix}:wd:text_language:{prop}={language}")
        if language == "en":
            result.update(
                f"{prefix}:wd:text_token:{prop}={token}"
                for token in tokens(str(value["text"]))
            )
        return result
    if isinstance(value, str):
        result.add(f"{prefix}:wd:string_length:{prop}={bucket(len(value))}")
    return result


def wikidata_features(
    qids: set[str], sides: dict[str, set[str]]
) -> tuple[dict[str, set[str]], dict[str, list[str]], Counter[str]]:
    features: dict[str, set[str]] = defaultdict(set)
    names: dict[str, list[str]] = defaultdict(list)
    stats: Counter[str] = Counter()
    with gzip.open(
        BASE / "wikidata_entities.jsonl.gz", "rt", encoding="utf-8"
    ) as stream:
        for line in stream:
            record = json.loads(line)
            qid = record["requested_qid"]
            if qid not in qids:
                continue
            entity = record.get("entity", {})
            if entity.get("id") != qid:
                stats["redirected_or_missing"] += 1
                continue
            stats["entities"] += 1
            for side in sides[qid]:
                prefix = side
                for field in ("labels", "descriptions", "aliases"):
                    values = entity.get(field, {})
                    features[qid].update(
                        f"{prefix}:wd:{field}_language={language}"
                        for language in values
                    )
                    english = values.get("en", [] if field == "aliases" else {})
                    if isinstance(english, dict):
                        english = [english]
                    for entry in english:
                        text = entry.get("value", "")
                        if text:
                            if field in {"labels", "aliases"}:
                                names[qid].append(text)
                            features[qid].update(
                                f"{prefix}:wd:{field}_token={token}"
                                for token in tokens(text)
                            )
                sites = entity.get("sitelinks", {})
                features[qid].update(f"{prefix}:wd:sitelink={site}" for site in sites)
                features[qid].add(f"{prefix}:wd:sitelink_count={bucket(len(sites))}")
                for prop, statements in entity.get("claims", {}).items():
                    if prop in TARGET_PROPERTIES:
                        stats["excluded_target_statements"] += len(statements)
                        continue
                    live = [s for s in statements if s.get("rank") != "deprecated"]
                    if not live:
                        continue
                    features[qid].add(f"{prefix}:wd:property={prop}")
                    features[qid].add(
                        f"{prefix}:wd:claim_count:{prop}={bucket(len(live))}"
                    )
                    for statement in live:
                        snak = statement.get("mainsnak", {})
                        datatype = snak.get("datatype", "unknown")
                        rank = statement.get("rank", "unknown")
                        features[qid].update(
                            {
                                f"{prefix}:wd:datatype:{prop}={datatype}",
                                f"{prefix}:wd:rank:{prop}={rank}",
                            }
                        )
                        value = snak.get("datavalue", {}).get("value")
                        features[qid].update(
                            wikidata_value_features(prefix, prop, value)
                        )
                        for qualifier_prop, qualifiers in statement.get(
                            "qualifiers", {}
                        ).items():
                            features[qid].add(
                                f"{prefix}:wd:qualifier:{prop}={qualifier_prop}"
                            )
                            for qualifier in qualifiers:
                                features[qid].add(
                                    f"{prefix}:wd:qualifier_datatype:{prop}:{qualifier_prop}="
                                    f"{qualifier.get('datatype', 'unknown')}"
                                )
                        for reference in statement.get("references", []):
                            for reference_prop in reference.get("snaks", {}):
                                features[qid].add(
                                    f"{prefix}:wd:reference:{prop}={reference_prop}"
                                )
    return features, names, stats


def qid_resources(qids: set[str]) -> tuple[dict[str, set[str]], dict[str, str]]:
    by_qid: dict[str, set[str]] = defaultdict(set)
    by_uri: dict[str, str] = {}
    for directory in ("events", "entities"):
        for path in sorted((EK / directory).glob("part_*.qid_map.tsv")):
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    qid, uri = line.rstrip("\n").split("\t", 1)
                    if qid in qids:
                        uri = uri.strip("<>")
                        by_qid[qid].add(uri)
                        by_uri[uri] = qid
    return by_qid, by_uri


def part_lines(directory: str) -> Iterator[str]:
    for path in sorted((EK / directory).glob("part_*.nq.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            yield from stream


def eventkg_direct_features(
    by_uri: dict[str, str], sides: dict[str, set[str]]
) -> tuple[dict[str, set[str]], dict[str, list[str]], Counter[str]]:
    features: dict[str, set[str]] = defaultdict(set)
    texts: dict[str, list[str]] = defaultdict(list)
    stats: Counter[str] = Counter()
    for directory in COMPLETE_DIRECT:
        if not (EK / directory / "manifest.json").exists():
            stats[f"missing_{directory}"] += 1
            continue
        for line in part_lines(directory):
            parsed = parse_line(line)
            if not parsed:
                stats[f"unparsed_{directory}"] += 1
                continue
            subject, predicate, raw_object, graph = parsed
            qid = by_uri.get(subject)
            if not qid:
                continue
            stats[f"matched_{directory}"] += 1
            kind, value, language_or_datatype = parse_object(raw_object)
            pred, graph_name = short(predicate), short(graph or "source_unknown")
            for side in sides[qid]:
                prefix = side
                features[qid].update(
                    {
                        f"{prefix}:ek:predicate={pred}",
                        f"{prefix}:ek:graph={graph_name}",
                        f"{prefix}:ek:predicate_graph:{pred}={graph_name}",
                        f"{prefix}:ek:object_kind:{pred}={kind}",
                    }
                )
                if kind == "uri":
                    if "/resource/event_" in value or "/resource/entity_" in value:
                        features[qid].add(
                            f"{prefix}:ek:resource_link:{pred}="
                            f"{'event' if '/event_' in value else 'entity'}"
                        )
                    elif pred != "sameAs":
                        features[qid].add(f"{prefix}:ek:value:{pred}={short(value)}")
                else:
                    features[qid].add(
                        f"{prefix}:ek:literal_meta:{pred}="
                        f"{short(language_or_datatype or 'plain')}"
                    )
                    if predicate in TEXT_PREDICATES and language_or_datatype == "en":
                        texts[qid].append(value)
                        features[qid].update(
                            f"{prefix}:ek:text_token:{pred}={token}"
                            for token in tokens(value)
                        )
                    year_match = YEAR.match(value.lstrip("+"))
                    if year_match:
                        year = int(year_match.group(1))
                        features[qid].add(
                            f"{prefix}:ek:literal_decade:{pred}={year // 10 * 10}"
                        )
    return features, texts, stats


def relation_blocks(directory: str) -> Iterator[list[tuple[str, str, str, str | None]]]:
    current = None
    block: list[tuple[str, str, str, str | None]] = []
    for line in part_lines(directory):
        parsed = parse_line(line)
        if not parsed:
            continue
        relation = parsed[0]
        if current is not None and relation != current:
            yield block
            block = []
        current = relation
        block.append(parsed)
    if block:
        yield block


def eventkg_relation_features(
    by_uri: dict[str, str], sides: dict[str, set[str]]
) -> tuple[dict[str, set[str]], Counter[str]]:
    features: dict[str, set[str]] = defaultdict(set)
    stats: Counter[str] = Counter()
    for directory in COMPLETE_REIFIED:
        if not (EK / directory / "manifest.json").exists():
            stats[f"missing_{directory}"] += 1
            continue
        for block in relation_blocks(directory):
            common = [item for item in block if item[3] is None]
            graphs = {item[3] for item in block if item[3] is not None}
            for graph in graphs or {None}:
                if graph == WIKIDATA_GRAPH:
                    stats[f"excluded_wikidata_copy_{directory}"] += 1
                    continue
                values: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
                for _, predicate, raw_object, _ in [
                    *common,
                    *(item for item in block if item[3] == graph),
                ]:
                    kind, value, _ = parse_object(raw_object)
                    values[predicate].append((value, kind))
                role_values = [short(value) for value, _ in values.get(ROLE_TYPE, [])]
                roles = [role for role in role_values if role not in TARGET_PROPERTIES]
                if role_values and not roles:
                    stats[f"excluded_target_role_{directory}"] += 1
                    continue
                roles = roles or ["link_relation"]
                endpoints = []
                for direction, predicate in (("out", RDF_SUBJECT), ("in", RDF_OBJECT)):
                    for value, kind in values.get(predicate, []):
                        if kind == "uri" and value in by_uri:
                            endpoints.append((direction, by_uri[value]))
                graph_name = short(graph or "source_unknown")
                for direction, qid in endpoints:
                    stats[f"matched_{directory}"] += 1
                    for side in sides[qid]:
                        prefix = side
                        for role in roles:
                            features[qid].add(
                                f"{prefix}:ek:near_relation:{directory}:{direction}={role}"
                            )
                            features[qid].add(
                                f"{prefix}:ek:near_relation_graph:{direction}:{role}="
                                f"{graph_name}"
                            )
    return features, stats


def pair_text_features(
    row: dict[str, str], names: dict[str, list[str]], texts: dict[str, list[str]]
) -> set[str]:
    result: set[str] = set()
    event_text = " ".join(texts.get(row["event_qid"], [])).casefold()
    if not event_text:
        return result
    matched = False
    for name in names.get(row["object_qid"], []):
        clean_name = name.casefold().strip()
        if len(clean_name) < 3:
            continue
        start = event_text.find(clean_name)
        if start < 0:
            continue
        matched = True
        left = event_text[max(0, start - 100) : start]
        right = event_text[start + len(clean_name) : start + len(clean_name) + 100]
        result.update(
            f"pair:text_context={token}" for token in tokens(left + " " + right)
        )
    result.add(f"pair:object_mentioned={str(matched).lower()}")
    return result


def pair_source_features(row: dict[str, str]) -> set[str]:
    return {
        f"pair:eventkg_graph={graph}"
        for graph in row["eventkg_graphs"].split("|")
        if graph not in {"event_kg", "wikidata", "source_unknown"}
    }


def warsampo_overlap(rows: list[dict[str, str]]) -> dict[str, int]:
    relevant_qids = {row[key] for row in rows for key in ("event_qid", "object_qid")}
    identity_path = HERE / "audit_2026-10-11" / "identity_candidates.csv"
    relation_path = HERE / "audit_2026-10-11" / "joint_relation_pairs.csv"
    with identity_path.open(encoding="utf-8", newline="") as stream:
        screened = {
            row["wikidata_qid"]
            for row in csv.DictReader(stream)
            if row["review_status"] == "screened"
        }
    with relation_path.open(encoding="utf-8", newline="") as stream:
        war_pairs = {
            (row["war_subject_qid"], row["war_object_qid"])
            for row in csv.DictReader(stream)
        }
    case_pairs = {(row["event_qid"], row["object_qid"]) for row in rows}
    return {
        "screened_identity_qids_in_cases": len(relevant_qids & screened),
        "same_relation_pairs_in_cases": len(case_pairs & war_pairs),
    }


def category(feature: str) -> str:
    if feature.startswith(("pair:text_context", "pair:object_mentioned")):
        return "pair_text_context"
    if feature.startswith("pair:eventkg_graph"):
        return "pair_source_graph"
    parts = feature.split(":")
    if len(parts) >= 3:
        return ":".join(parts[:2]) + ":" + parts[2].split("=", 1)[0]
    return feature


def main() -> None:
    with INPUT.open(encoding="utf-8", newline="") as stream:
        all_rows = list(csv.DictReader(stream))
    rows = [row for row in all_rows if row["wikidata_observed"] != "unrecorded"]
    qids = {row[key] for row in all_rows for key in ("event_qid", "object_qid")}
    sides: dict[str, set[str]] = defaultdict(set)
    for row in all_rows:
        sides[row["event_qid"]].add("subject")
        sides[row["object_qid"]].add("object")

    wd, names, wd_stats = wikidata_features(qids, sides)
    _, by_uri = qid_resources(qids)
    ek, texts, direct_stats = eventkg_direct_features(by_uri, sides)
    relations, relation_stats = eventkg_relation_features(by_uri, sides)

    all_feature_counts: Counter[str] = Counter()
    for row in all_rows:
        row["features"] = (
            wd[row["event_qid"]]
            | wd[row["object_qid"]]
            | ek[row["event_qid"]]
            | ek[row["object_qid"]]
            | relations[row["event_qid"]]
            | relations[row["object_qid"]]
            | pair_text_features(row, names, texts)
            | pair_source_features(row)
        )
        all_feature_counts.update(row["features"])

    feature_counts = Counter(feature for row in rows for feature in row["features"])
    selected, steps = choose_fields(rows)
    groups = partition(rows, selected)
    all_groups = partition(all_rows, selected)
    assignments = []
    group_summary = []
    for group_id, (key, group) in enumerate(sorted(all_groups.items()), start=1):
        coded_group = [row for row in group if row["wikidata_observed"] != "unrecorded"]
        codes = sorted({row["wikidata_observed"] for row in coded_group})
        code_counts = Counter(row["wikidata_observed"] for row in coded_group)
        pattern = "".join("1" if value else "0" for value in key)
        group_summary.append(
            {
                "group": group_id,
                "selected_pattern": pattern,
                "pairs": len(group),
                "coded_pairs": len(coded_group),
                "unrecorded_pairs": len(group) - len(coded_group),
                "distinct_object_qids": len({row["object_qid"] for row in group}),
                "recorded_code_counts": dict(sorted(code_counts.items())),
                "coded_consistent": bool(coded_group) and len(codes) == 1,
            }
        )
        for row in group:
            assignments.append(
                {
                    "group": group_id,
                    "event_qid": row["event_qid"],
                    "object_qid": row["object_qid"],
                    "recorded_codes": row["wikidata_observed"],
                    "group_code_sets": "|".join(codes),
                    "coded_group_consistent": bool(coded_group) and len(codes) == 1,
                    "selected_pattern": pattern,
                }
            )
    with ASSIGNMENTS.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=assignments[0].keys())
        writer.writeheader()
        writer.writerows(assignments)

    usable_candidates = {
        field for field, count in feature_counts.items() if 3 <= count <= len(rows) - 3
    }
    summary = {
        "source_role": "EventKG hasPlace",
        "pairs": len(all_rows),
        "coded_pairs": len(rows),
        "unrecorded_pairs": len(all_rows) - len(rows),
        "distinct_event_qids": len({row["event_qid"] for row in rows}),
        "distinct_object_qids": len({row["object_qid"] for row in rows}),
        "feature_count_raw_all_pairs": len(all_feature_counts),
        "feature_count_raw_coded_pairs": len(feature_counts),
        "feature_count_support_eligible": len(usable_candidates),
        "feature_families_raw": dict(
            sorted(Counter(category(field) for field in all_feature_counts).items())
        ),
        "complete_eventkg_direct": list(COMPLETE_DIRECT),
        "complete_eventkg_reified": list(COMPLETE_REIFIED),
        "excluded_incomplete_eventkg": [
            directory
            for directory in KNOWN_INCOMPLETE
            if not (EK / directory / "manifest.json").exists()
        ],
        "excluded_predictors": [
            "event_qid and object_qid",
            "EventKG resource and relation IDs",
            "Wikidata P17, P276, and P710 claims",
            "previous cluster, tree leaf, and model prediction outputs",
            "technical revision, page, and modified-time metadata",
        ],
        "wikidata_scan": dict(wd_stats),
        "eventkg_direct_scan": dict(direct_stats),
        "eventkg_relation_scan": dict(relation_stats),
        "warsampo_overlap": warsampo_overlap(all_rows),
        "start_mixed_pairs": mixed_pairs(partition(rows, [])),
        "selected_fields": selected,
        "steps": steps,
        "final_coded_groups": len(groups),
        "all_pair_groups": len(all_groups),
        "final_mixed_pairs": mixed_pairs(groups),
        "final_consistent_pairs": len(rows) - mixed_pairs(groups),
        "final_group_summary": group_summary,
        "stop_reason": "no unused field creates a supported split and reduces mixed coded pairs",
        "held_out_by_object": held_out_check(rows),
    }
    OUTPUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "pairs",
                    "coded_pairs",
                    "feature_count_raw_all_pairs",
                    "feature_count_support_eligible",
                    "selected_fields",
                    "final_mixed_pairs",
                    "final_consistent_pairs",
                    "held_out_by_object",
                    "warsampo_overlap",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
