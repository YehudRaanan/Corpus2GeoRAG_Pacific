"""Profile the current assertion export after deterministic v2.1 replay.

Read-only inputs; all outputs stay in GG_Data. No network or model calls.
Endpoint-pair repetition is measured, never treated as permission to delete.
"""

from __future__ import annotations

import calendar
import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rebuild_relation_mapping import read_csv, write_csv
from run_relation_mapping_sanity import Reservoir, iter_json_array, original_endpoints

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "assertion_eda_v2_1_2026-10-15"
ASSERTIONS = HERE / "outputs/relation-map-v1.0.0/complete_mapped_relations_v1.0.0.csv"
GRAPH = ROOT / "GG_Data/agent_export/outputs/wwii_agent_graph_draft_v0.1.0.json"
DATE_RE = re.compile(r"^([+-]?\d+)-(\d{2})-(\d{2})(?:T.*)?$")
QID_RE = re.compile(r"(?:wd:)?Q\d+")
SEED = 20261015
Pair = tuple[str, str]
TimeKey = tuple[str, str, str]


def date_bounds(
    value: str, precision: list[int | str]
) -> tuple[int, tuple, tuple] | None:
    """Gregorian calendar bounds; preserve coarse precision and extended years.

    Month/day zero can represent unknown components. This checks calendar
    components, not clock/timezone syntax. Dates outside WWII are not errors.
    """
    match = DATE_RE.fullmatch(value)
    if not match:
        return None
    year, month, day = map(int, match.groups())
    if not 0 <= month <= 12 or not 0 <= day <= 31:
        return None
    if day and not month:
        return None
    if month and day and day > calendar.monthrange(year, month)[1]:
        return None
    units = {
        "unitDay": 11,
        "unitMonth": 10,
        "unitYear": 9,
        "https://eventkg.l3s.uni-hannover.de/schema/unitDecade": 8,
        "day": 11,
        "month": 10,
        "year": 9,
    }
    scales = [p if isinstance(p, int) else units[p] for p in precision]
    scale = min(scales) if scales else 0
    if scale < 9:
        # Broad source precision needs its own uncertainty interval; do not
        # invent one for the interval-order check.
        return year, (), ()
    if scale == 9 or not month:
        return year, (year, 1, 1), (year, 12, 31)
    if scale == 10 or not day:
        return (
            year,
            (year, month, 1),
            (year, month, calendar.monthrange(year, month)[1]),
        )
    return year, (year, month, day), (year, month, day)


@dataclass
class Profile:
    metrics: Counter[str] = field(default_factory=Counter)
    subjects: Counter[str] = field(default_factory=Counter)
    objects: Counter[str] = field(default_factory=Counter)
    facts: Counter[Pair] = field(default_factory=Counter)
    timed_facts: set[tuple] = field(default_factory=set)
    first_time: dict[Pair, TimeKey] = field(default_factory=dict)
    varied_time: set[Pair] = field(default_factory=set)
    source_masks: dict[Pair, int] = field(default_factory=dict)
    records: set[tuple[str, str]] = field(default_factory=set)
    years: list[int] = field(default_factory=list)

    def add(
        self,
        subject: str,
        obj: str,
        time: TimeKey,
        source_bit: int,
        source: str,
        record_id: str,
        flags: dict[str, bool],
        years: list[int],
    ) -> None:
        self.metrics["assertions"] += 1
        self.metrics.update(key for key, value in flags.items() if value)
        self.subjects[subject] += 1
        self.objects[obj] += 1
        pair = (subject, obj)
        self.facts[pair] += 1
        self.timed_facts.add((*pair, *time))
        if pair in self.first_time and self.first_time[pair] != time:
            self.varied_time.add(pair)
        self.first_time.setdefault(pair, time)
        self.source_masks[pair] = self.source_masks.get(pair, 0) | source_bit
        if record_id:
            self.records.add((source, record_id))
        self.years.extend(years)

    def row(self, nodes: dict[str, dict[str, Any]]) -> dict[str, Any]:
        n = self.metrics["assertions"]
        subject, top_s = self.subjects.most_common(1)[0] if n else ("", 0)
        obj, top_o = self.objects.most_common(1)[0] if n else ("", 0)
        result = dict(self.metrics)
        for name in FLAGS:
            result.setdefault(name, 0)
        result.update(
            assertions=n,
            distinct_subjects=len(self.subjects),
            distinct_objects=len(self.objects),
            distinct_endpoint_pairs=len(self.facts),
            repeated_endpoint_pair_groups=sum(v > 1 for v in self.facts.values()),
            extra_rows_over_endpoint_pairs=n - len(self.facts),
            distinct_endpoint_time_keys=len(self.timed_facts),
            extra_rows_over_endpoint_time_keys=n - len(self.timed_facts),
            repeated_pairs_with_different_time_values=len(self.varied_time),
            endpoint_pairs_seen_in_multiple_selected_sources=sum(
                v.bit_count() > 1 for v in self.source_masks.values()
            ),
            distinct_nonempty_source_record_keys=len(self.records),
            min_present_year=min(self.years) if self.years else "",
            max_present_year=max(self.years) if self.years else "",
            top_subject_qid=subject,
            top_subject_name=nodes.get(subject, {}).get("name", subject),
            top_subject_rows=top_s,
            top_subject_share_percent=round(100 * top_s / n, 3) if n else 0,
            top_object_qid=obj,
            top_object_name=nodes.get(obj, {}).get("name", obj),
            top_object_rows=top_o,
            top_object_share_percent=round(100 * top_o / n, 3) if n else 0,
        )
        return result


FLAGS = (
    "self_loops",
    "missing_endpoint_node",
    "qid_only_subject_name",
    "qid_only_object_name",
    "either_name_qid_only",
    "either_type_other",
    "either_classification_unresolved",
    "either_endpoint_text_empty",
    "both_endpoint_text_empty",
    "both_endpoints_core",
    "neither_endpoint_core",
    "any_date",
    "both_interval_bounds",
    "point_date",
    "no_date",
    "invalid_calendar_date",
    "definitely_reversed_interval",
    "date_outside_1939_1945",
    "no_source_record_id",
    "no_source_graph",
    "no_source_reference",
    "empty_support_list",
    "empty_evidence_list",
    "multiple_support_entries",
    "multiple_support_sources",
    "wikidata_reference_hash_present",
    "assertion_qa_required",
    "mapping_reverses_endpoints",
    "level2_changed_from_v1",
    "legacy_ranked_level1_promoted",
    "exact_duplicate_full_row",
    "repeated_observation_id",
    "repeated_selected_source_record_key",
    "unselected_date_with_precision",
    "mixed_time_precision",
    "date_precision_unknown",
)


def self_check() -> None:
    assert date_bounds("+1942-02-29T00:00:00Z", [11]) is None
    assert date_bounds("+1944-02-29T00:00:00Z", [11]) is not None
    assert date_bounds("+1942-00-00T00:00:00Z", [9])[1:] == (
        (1942, 1, 1),
        (1942, 12, 31),
    )
    assert date_bounds("+6194-01-01T00:00:00Z", [9])[0] == 6194
    assert date_bounds("1942-01-01", ["unitYear"])[1:] == ((1942, 1, 1), (1942, 12, 31))
    assert date_bounds("1942-12-31", ["unitMonth"])[1:] == (
        (1942, 12, 1),
        (1942, 12, 31),
    )
    assert date_bounds("1942-01-01", [])[1:] == ((), ())
    p = Profile()
    p.add("A", "B", ("", "", ""), 1, "X", "r1", {}, [])
    p.add("A", "B", ("1942", "", ""), 2, "Y", "r2", {}, [])
    result = p.row({})
    assert result["extra_rows_over_endpoint_pairs"] == 1
    assert result["extra_rows_over_endpoint_time_keys"] == 0
    assert result["repeated_pairs_with_different_time_values"] == 1
    assert result["endpoint_pairs_seen_in_multiple_selected_sources"] == 1


def main() -> None:
    self_check()
    OUT.mkdir(exist_ok=True)
    mapping = read_csv(HERE / "RELATION_MAPPING_TABLE_v2.1.0.csv")
    by_key = {(r["source"], r["source_predicate"]): r for r in mapping}
    assert len(by_key) == len(mapping)
    catalog = {
        r["level2_relation_id"]: r
        for r in read_csv(HERE / "RELATION_DIRECTION_CATALOG_v2.1.0.csv")
    }
    groups: dict[str, Profile] = {rid: Profile() for rid in catalog}
    source_groups = {key: Profile() for key in by_key}
    nodes = {}
    print("Reading draft node metadata...", flush=True)
    for node in iter_json_array(GRAPH, "nodes"):
        qid = node["id"].removeprefix("wd:")
        attrs = node.get("attributes", {})
        nodes[qid] = {
            "name": node.get("name", ""),
            "type": node.get("type", "MISSING"),
            "text_empty": not bool(node.get("text", "").strip()),
            "core": bool(attrs.get("wwii_task_force_core")),
            "unresolved": attrs.get("classification_status") == "UNRESOLVED",
        }
    print(f"Indexed {len(nodes):,} nodes. Reading assertion rows...", flush=True)
    sources = {s: 1 << i for i, s in enumerate(sorted({r["source"] for r in mapping}))}
    selected_sources: Counter[str] = Counter()
    source_counts: Counter[tuple] = Counter()
    graph_counts: Counter[tuple] = Counter()
    type_pairs: Counter[tuple] = Counter()
    years_count: Counter[tuple] = Counter()
    precision_counts: Counter[tuple] = Counter()
    statuses: Counter[tuple] = Counter()
    all_metrics: Counter[str] = Counter()
    observations: set[str] = set()
    source_records: set[tuple[str, str]] = set()
    full_rows: set[bytes] = set()
    pair_facts: dict[str, dict[Pair, set[str]]] = defaultdict(dict)
    pair_counts: Counter[str] = Counter()
    samplers: dict[str, Reservoir] = {}
    issue_examples: dict[tuple[str, str], list[dict]] = defaultdict(list)
    with ASSERTIONS.open(encoding="utf-8-sig", newline="") as stream:
        for index, row in enumerate(csv.DictReader(stream), 1):
            key = (row["selected_source"], row["selected_source_predicate"])
            rule = by_key[key]  # A missing key is an error, not a fallback.
            rid = rule["level2_relation_id"]
            subject, obj = original_endpoints(row)
            if rule["direction_to_level2"] == "reverse":
                subject, obj = obj, subject
            sn, on = nodes.get(subject, {}), nodes.get(obj, {})
            support = json.loads(row["source_support"])
            evidence = json.loads(row["evidence_references"])
            reference = row["source_reference"]
            reference_hashes = []
            if key[0] == "Wikidata" and reference:
                reference_hashes = json.loads(reference).get("reference_hashes", [])
            time = (row["time_from"], row["time_to"], row["time_point"])
            precision = json.loads(row["time_precision"])
            parsed = [
                date_bounds(v, precision.get(part, [])) if v else None
                for v, part in zip(time, ("from", "to", "point"))
            ]
            present_years = [v[0] for v in parsed if v is not None]
            invalid = any(value and bound is None for value, bound in zip(time, parsed))
            reversed_time = bool(
                parsed[0]
                and parsed[1]
                and parsed[0][1]
                and parsed[1][2]
                and parsed[0][1] > parsed[1][2]
            )
            record = (key[0], row["source_record_id"])
            digest = hashlib.sha256(
                json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
            ).digest()
            flags = dict(
                zip(
                    FLAGS,
                    (
                        subject == obj,
                        not sn or not on,
                        bool(QID_RE.fullmatch(sn.get("name", ""))),
                        bool(QID_RE.fullmatch(on.get("name", ""))),
                        bool(
                            QID_RE.fullmatch(sn.get("name", ""))
                            or QID_RE.fullmatch(on.get("name", ""))
                        ),
                        sn.get("type") == "other" or on.get("type") == "other",
                        sn.get("unresolved", False) or on.get("unresolved", False),
                        sn.get("text_empty", True) or on.get("text_empty", True),
                        sn.get("text_empty", True) and on.get("text_empty", True),
                        sn.get("core", False) and on.get("core", False),
                        not sn.get("core", False) and not on.get("core", False),
                        any(time),
                        bool(time[0] and time[1]),
                        bool(time[2]),
                        not any(time),
                        invalid,
                        reversed_time,
                        any(y < 1939 or y > 1945 for y in present_years),
                        not row["source_record_id"],
                        not row["source_graph"],
                        not reference,
                        not support,
                        not evidence,
                        len(support) > 1,
                        len({x["source"] for x in support}) > 1,
                        bool(reference_hashes),
                        rule["assertion_qa_required"] == "YES",
                        rule["direction_to_level2"] == "reverse",
                        row["level2_relation"] != rid,
                        row["level1_assignment_status"] == "RANKED_REVIEW_REQUIRED"
                        and row["level1_relation"] != "UNRESOLVED",
                        digest in full_rows,
                        row["observation_id"] in observations,
                        bool(row["source_record_id"]) and record in source_records,
                        any(
                            not value and precision.get(part)
                            for value, part in zip(time, ("from", "to", "point"))
                        ),
                        any(len(v) > 1 for v in precision.values()),
                        any(
                            value and not precision.get(part)
                            for value, part in zip(time, ("from", "to", "point"))
                        ),
                    ),
                    strict=True,
                )
            )
            full_rows.add(digest)
            observations.add(row["observation_id"])
            if row["source_record_id"]:
                source_records.add(record)
            for profile in (groups[rid], source_groups[key]):
                profile.add(
                    subject,
                    obj,
                    time,
                    sources[key[0]],
                    key[0],
                    row["source_record_id"],
                    flags,
                    present_years,
                )
            all_metrics["assertions"] += 1
            all_metrics.update(k for k, v in flags.items() if v)
            selected_sources[key[0]] += 1
            source_counts[(rid, key[0])] += 1
            graph_counts[(rid, key[0], row["source_graph"])] += 1
            type_pairs[(rid, sn.get("type", "MISSING"), on.get("type", "MISSING"))] += 1
            for part, value in zip(("from", "to", "point"), parsed):
                if value is not None:
                    years_count[(rid, part, value[0])] += 1
                units = precision.get(part, [])
                if units or row["time_" + part]:
                    precision_counts[
                        (
                            rid,
                            key[0],
                            part,
                            json.dumps(units),
                            bool(row["time_" + part]),
                        )
                    ] += 1
            for field_name in (
                "time_status",
                "selection_status",
                "final_review_status",
                "mapping_origin",
                "level1_assignment_status",
            ):
                statuses[(rid, "legacy_" + field_name, row[field_name])] += 1
            for field_name in (
                "level2_decision",
                "level1_assignment_status",
                "reverse_status",
            ):
                statuses[(rid, "current_" + field_name, rule[field_name])] += 1
            direction = catalog[rid]
            pair_id = direction["direction_pair_id"]
            reverse_id = direction["reverse_relation_id"]
            pair_subject, pair_object = subject, obj
            if direction["reverse_resolution_type"] == "SYMMETRIC":
                pair_subject, pair_object = sorted((subject, obj))
            elif rid > reverse_id:
                pair_subject, pair_object = obj, subject
            pair_facts[pair_id].setdefault((pair_subject, pair_object), set()).add(rid)
            pair_counts[pair_id] += 1
            example = {
                "level2_relation_id": rid,
                "level2_label": direction["level2_relation_label"],
                "observation_id": row["observation_id"],
                "source": key[0],
                "source_predicate": key[1],
                "subject_qid": subject,
                "subject_name": sn.get("name", subject),
                "subject_type": sn.get("type", "MISSING"),
                "object_qid": obj,
                "object_name": on.get("name", obj),
                "object_type": on.get("type", "MISSING"),
                "time_from": time[0],
                "time_to": time[1],
                "time_point": time[2],
                "source_record_id": row["source_record_id"],
                "source_graph": row["source_graph"],
                "source_reference": reference,
                "review_flags": "|".join(k for k, v in flags.items() if v),
            }
            if rid not in samplers:
                seed = int(hashlib.sha256(f"{SEED}|{rid}".encode()).hexdigest(), 16)
                samplers[rid] = Reservoir(3, random.Random(seed))
            samplers[rid].add(example)
            for issue in (
                "self_loops",
                "invalid_calendar_date",
                "definitely_reversed_interval",
                "missing_endpoint_node",
                "exact_duplicate_full_row",
                "repeated_selected_source_record_key",
            ):
                if flags[issue] and len(issue_examples[(rid, issue)]) < 3:
                    issue_examples[(rid, issue)].append(
                        dict(example, sample_reason=issue)
                    )
            if index % 200000 == 0:
                print(f"Read {index:,} assertions...", flush=True)

    profiles = []
    for rid, profile in groups.items():
        row = dict(catalog[rid])
        row.update(profile.row(nodes))
        row["selected_source_counts"] = json.dumps(
            {
                s: source_counts[(rid, s)]
                for s in sorted(sources)
                if source_counts[(rid, s)]
            },
            separators=(",", ":"),
        )
        row["selected_source_count"] = sum(source_counts[(rid, s)] > 0 for s in sources)
        row["share_of_all_assertions_percent"] = round(
            100 * row["assertions"] / all_metrics["assertions"], 4
        )
        profiles.append(row)
    profiles.sort(key=lambda r: (-r["assertions"], r["level2_relation_id"]))
    source_profiles = []
    for key, profile in source_groups.items():
        row = {
            field_name: by_key[key][field_name]
            for field_name in (
                "source",
                "source_predicate",
                "normalized_relation_id",
                "relation_label",
                "level2_relation_id",
                "direction_to_level2",
                "level2_mapping_basis",
                "level2_decision",
                "source_occurrence_count",
            )
        }
        row.update(profile.row(nodes))
        source_profiles.append(row)
    source_profiles.sort(
        key=lambda r: (-r["assertions"], r["source"], r["source_predicate"])
    )
    assert (
        sum(r["assertions"] for r in profiles)
        == sum(r["assertions"] for r in source_profiles)
        == all_metrics["assertions"]
    )
    write_csv(OUT / "relation_profile.csv", profiles)
    write_csv(OUT / "source_relation_profile.csv", source_profiles)
    for filename, counts, fields in (
        (
            "endpoint_type_pairs.csv",
            type_pairs,
            ("level2_relation_id", "subject_draft_type", "object_draft_type"),
        ),
        (
            "source_graph_profile.csv",
            graph_counts,
            ("level2_relation_id", "source", "source_graph"),
        ),
        ("year_profile.csv", years_count, ("level2_relation_id", "date_field", "year")),
        (
            "time_precision_profile.csv",
            precision_counts,
            (
                "level2_relation_id",
                "source",
                "date_field",
                "source_precision_values",
                "selected_date_present",
            ),
        ),
        ("status_profile.csv", statuses, ("level2_relation_id", "dimension", "status")),
    ):
        write_csv(
            OUT / filename,
            [
                dict(zip(fields, key), assertions=value)
                for key, value in sorted(counts.items())
            ],
        )
    pair_rows = []
    for pair_id in sorted({r["direction_pair_id"] for r in catalog.values()}):
        facts = pair_facts[pair_id]
        effective = sorted(
            rid for rid, r in catalog.items() if r["direction_pair_id"] == pair_id
        )
        pair_rows.append(
            {
                "direction_pair_id": pair_id,
                "effective_relation_ids": "|".join(effective),
                "assertions": pair_counts[pair_id],
                "distinct_direction_normalized_endpoint_pairs": len(facts),
                "endpoint_pairs_with_both_named_relation_ids": sum(
                    len(values) > 1 for values in facts.values()
                ),
            }
        )
    write_csv(OUT / "direction_pair_profile.csv", pair_rows)
    examples = [
        dict(row, sample_reason="seeded_random_per_relation")
        for rid in sorted(samplers)
        for row in samplers[rid].rows
    ]
    examples.extend(
        row for key in sorted(issue_examples) for row in issue_examples[key]
    )
    write_csv(OUT / "examples.csv", examples)
    used = [r for r in profiles if r["assertions"]]
    total = all_metrics["assertions"]
    summary = {
        "mapping_version": "relation-map-v2.1.0",
        "assertion_input_version": "relation-map-v1.0.0",
        "inputs": {
            "assertions": str(ASSERTIONS.relative_to(ROOT)),
            "graph": str(GRAPH.relative_to(ROOT)),
            "mapping": "GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.0.csv",
        },
        "input_sizes_bytes": {
            "assertions": ASSERTIONS.stat().st_size,
            "graph": GRAPH.stat().st_size,
        },
        "seed": SEED,
        "nodes_indexed": len(nodes),
        "totals": dict(all_metrics),
        "selected_source_assertions": dict(selected_sources),
        "mapped_source_keys": len(mapping),
        "observed_source_keys": sum(
            p.metrics["assertions"] > 0 for p in source_groups.values()
        ),
        "catalog_level2_relations": len(catalog),
        "observed_level2_relations": len(used),
        "catalog_relations_with_zero_assertions": len(profiles) - len(used),
        "relations_with_1_to_9_assertions": sum(
            0 < r["assertions"] < 10 for r in profiles
        ),
        "relations_with_10_to_99_assertions": sum(
            10 <= r["assertions"] < 100 for r in profiles
        ),
        "top_10_relation_share_percent": round(
            100 * sum(r["assertions"] for r in profiles[:10]) / total, 3
        ),
        "distinct_endpoint_pairs_within_relation": sum(
            r["distinct_endpoint_pairs"] for r in profiles
        ),
        "extra_rows_over_endpoint_pairs": sum(
            r["extra_rows_over_endpoint_pairs"] for r in profiles
        ),
        "extra_rows_over_endpoint_time_keys": sum(
            r["extra_rows_over_endpoint_time_keys"] for r in profiles
        ),
        "repeated_endpoint_pair_groups": sum(
            r["repeated_endpoint_pair_groups"] for r in profiles
        ),
        "repeated_pairs_with_different_time_values": sum(
            r["repeated_pairs_with_different_time_values"] for r in profiles
        ),
        "endpoint_pairs_seen_in_multiple_selected_sources": sum(
            r["endpoint_pairs_seen_in_multiple_selected_sources"] for r in profiles
        ),
        "endpoint_pairs_with_both_named_relation_ids": sum(
            r["endpoint_pairs_with_both_named_relation_ids"] for r in pair_rows
        ),
        "distinct_observation_ids": len(observations),
        "distinct_full_rows": len(full_rows),
        "sample_rows": len(examples),
        "limits": [
            "Counts are exported assertion rows, not all raw source statements or Agent-generated reverse views.",
            "The current draft is a WWII mechanism test; its metadata says the Pacific corpus was not used.",
            "Common endpoint or endpoint-time keys do not prove duplicate facts: qualifiers, records, provenance and source reuse can differ.",
            "Different sources can reuse Wikidata and are not necessarily independent evidence.",
            "Draft endpoint names, types and classifications are diagnostics, not ground truth.",
            "Date ranges outside 1939-1945 are context flags, not automatic errors; precision is retained for interval checks.",
            "Reference hashes and source record pointers do not establish readable answer-supporting passages.",
            "Full non-temporal qualifiers and source reference contents are not present in this assertion CSV.",
            "Geometry is deferred and is not a quality failure in this EDA.",
            "No formal domain/range compliance or historical assertion truth is inferred from endpoint type frequencies.",
        ],
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
