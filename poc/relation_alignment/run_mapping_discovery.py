"""Audit relation-type evidence; never export source facts as graph edges.

Run again after EventKG scans finish. Incomplete directories are excluded and
reported. Only EventKG records with two QID-mapped endpoints can vote.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "Data/external/wwii_task_force"
EK = BASE / "eventkg_v3_2"
OUT = Path(__file__).resolve().parent / "mapping_discovery"
AUDIT = Path(__file__).resolve().parent / "audit_2026-10-11"

QUAD = re.compile(r"^<([^>]+)> <([^>]+)> <([^>]+)> (?:<([^>]+)> )?\.$")
DATE_QUAD = re.compile(r'^<([^>]+)> <([^>]+)> "([^"]+)"\^\^<[^>]+> <([^>]+)> \.$')
ROLE = "http://semanticweb.cs.vu.nl/2009/11/sem/roleType"
SUBJECT = "http://www.w3.org/1999/02/22-rdf-syntax-ns#subject"
OBJECT = "http://www.w3.org/1999/02/22-rdf-syntax-ns#object"
WD_GRAPH = "https://eventkg.l3s.uni-hannover.de/graph/wikidata"
REIFIED = (
    "relations_events_other",
    "relations_entities_temporal",
    "relations_entities_other",
    "relations_events_literals",
)
DIRECT = ("events", "relations_events_base", "entities", "relations_entities_base")


def complete(name: str) -> bool:
    return (EK / name / "manifest.json").exists()


def part_lines(name: str):
    for path in sorted((EK / name).glob("part_*.nq.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            yield from stream


def resource_qids() -> tuple[dict[str, str], dict[str, str]]:
    resource_to_qid: dict[str, str] = {}
    kind: dict[str, str] = {}
    for name, type_name in (("events", "event"), ("entities", "entity")):
        if not complete(name):
            raise RuntimeError(f"QID map is incomplete: {name}")
        for path in sorted((EK / name).glob("part_*.qid_map.tsv")):
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    qid, resource = line.rstrip("\n").split("\t", 1)
                    resource_to_qid[resource.strip("<>")] = qid
                    kind[qid] = type_name
    return resource_to_qid, kind


def wd_pairs(population: set[str]) -> tuple[dict[tuple[str, str], set[str]], Counter]:
    pairs: dict[tuple[str, str], set[str]] = defaultdict(set)
    stats: Counter = Counter()
    with gzip.open(
        BASE / "wikidata_entities.jsonl.gz", "rt", encoding="utf-8"
    ) as stream:
        for line in stream:
            record = json.loads(line)
            entity = record.get("entity", {})
            subject = record["requested_qid"]
            stats["records"] += 1
            if entity.get("id") != subject:
                stats["redirected_or_missing_records"] += 1
                continue
            for prop, statements in entity.get("claims", {}).items():
                for statement in statements:
                    snak = statement.get("mainsnak", {})
                    value = snak.get("datavalue", {}).get("value")
                    if (
                        not isinstance(value, dict)
                        or value.get("entity-type") != "item"
                    ):
                        continue
                    if statement.get("rank") == "deprecated":
                        stats["deprecated_item_claims"] += 1
                        continue
                    stats["item_claims"] += 1
                    if statement.get("qualifiers"):
                        stats["qualified_item_claims"] += 1
                    target = value["id"]
                    if target in population:
                        pairs[(subject, target)].add(prop)
                        stats["in_population_item_claims"] += 1
                    else:
                        stats["boundary_item_claims"] += 1
    return pairs, stats


def reified_groups(name: str):
    """Yield (relation ID, graph, role, subject URI, object URI)."""
    current = None
    graphs: dict[str, dict[str, str]] = defaultdict(dict)

    def emit():
        for graph, values in graphs.items():
            if all(key in values for key in (ROLE, SUBJECT, OBJECT)):
                yield current, graph, values[ROLE], values[SUBJECT], values[OBJECT]

    for line in part_lines(name):
        match = QUAD.match(line.rstrip("\n"))
        if not match:
            continue
        relation, predicate, value, graph = match.groups()
        if relation != current:
            if current is not None:
                yield from emit()
            current = relation
            graphs = defaultdict(dict)
        if predicate in (ROLE, SUBJECT, OBJECT):
            graphs[graph or "source_unknown"][predicate] = value
    if current is not None:
        yield from emit()


def direct_edges(name: str):
    for line in part_lines(name):
        match = QUAD.match(line.rstrip("\n"))
        if match:
            subject, predicate, target, graph = match.groups()
            if predicate.startswith(
                "http://semanticweb.cs.vu.nl/2009/11/sem/"
            ) and predicate.rsplit("/", 1)[-1] in {
                "hasSubEvent",
                "subEventOf",
                "hasPlace",
                "hasActor",
            }:
                yield subject, predicate, target, graph or "source_unknown"


def short(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def date_variants(r2q: dict[str, str]) -> dict:
    dates: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    if not complete("relations_events_base"):
        return {"incomplete": True}
    for line in part_lines("relations_events_base"):
        match = DATE_QUAD.match(line.rstrip("\n"))
        if not match:
            continue
        resource, predicate, value, graph = match.groups()
        field = short(predicate)
        qid = r2q.get(resource)
        if qid and field in {"hasBeginTimeStamp", "hasEndTimeStamp"}:
            dates[(qid, field)][short(graph)].add(value)
    same_graph = [
        key
        for key, by_graph in dates.items()
        if any(len(v) > 1 for v in by_graph.values())
    ]
    cross_graph = [
        key for key, by_graph in dates.items() if len(set.union(*by_graph.values())) > 1
    ]
    examples = {
        qid: {
            field: {
                graph: sorted(values)
                for graph, values in dates.get((qid, field), {}).items()
            }
            for field in ("hasBeginTimeStamp", "hasEndTimeStamp")
        }
        for qid in ("Q134949", "Q122100")
    }
    return {
        "event_fields_with_dates": len(dates),
        "same_graph_multivalue_fields": len(same_graph),
        "cross_graph_multivalue_fields": len(cross_graph),
        "same_graph_example_qids": sorted({key[0] for key in same_graph})[:10],
        "cross_graph_example_qids": sorted({key[0] for key in cross_graph})[:10],
        "known_examples": examples,
    }


def score_candidates(
    ek_pairs: dict[tuple[str, str, str, str, str], set[tuple[str, str]]],
    wd: dict[tuple[str, str], set[str]],
    source_ids: (
        dict[tuple[tuple[str, str, str, str, str], tuple[str, str]], str] | None
    ) = None,
):
    # Key: EventKG role, graph, subject kind, object kind, relation format.
    votes: dict[tuple, set[tuple[str, str]]] = defaultdict(set)
    role_connected: dict[tuple, set[tuple[str, str]]] = defaultdict(set)
    role_targets: dict[tuple, Counter] = defaultdict(Counter)
    for role_key, pairs in ek_pairs.items():
        for pair in pairs:
            same, reverse = wd.get(pair, set()), wd.get(pair[::-1], set())
            if not same and not reverse:
                continue
            role_connected[role_key].add(pair)
            for direction, props in (("same", same), ("reverse", reverse)):
                for prop in props:
                    candidate = (*role_key, prop, direction)
                    votes[candidate].add(pair)
                    role_targets[candidate][pair[1]] += 1
    rows = []
    for candidate, pairs in votes.items():
        role_key = candidate[:5]
        targets = role_targets[candidate]

        def is_test(pair: tuple[str, str]) -> bool:
            return int(hashlib.sha256(pair[1].encode()).hexdigest(), 16) % 5 == 0

        heldout = {pair for pair in pairs if is_test(pair)}
        heldout_connected = {pair for pair in role_connected[role_key] if is_test(pair)}
        main_target, main_count = targets.most_common(1)[0]
        other_connected = {
            pair for pair in role_connected[role_key] if pair[1] != main_target
        }
        rows.append(
            {
                "ek_role": candidate[0],
                "ek_graph": candidate[1],
                "subject_kind": candidate[2],
                "object_kind": candidate[3],
                "format": candidate[4],
                "wd_property": candidate[5],
                "direction": candidate[6],
                "shared_pairs": len(pairs),
                "ek_pairs": len(ek_pairs[role_key]),
                "ek_co_connected_pairs": len(role_connected[role_key]),
                "pct_of_ek_co_connected": round(
                    100 * len(pairs) / len(role_connected[role_key]), 1
                ),
                "distinct_targets": len(targets),
                "largest_target_qid": main_target,
                "largest_target_pct": round(
                    100 * max(targets.values()) / len(pairs), 1
                ),
                "after_largest_target_pairs": len(pairs) - main_count,
                "after_largest_target_pct": (
                    round(100 * (len(pairs) - main_count) / len(other_connected), 1)
                    if other_connected
                    else 0
                ),
                "test_pairs": len(heldout),
                "test_pct_of_ek_co_connected": (
                    round(100 * len(heldout) / len(heldout_connected), 1)
                    if heldout_connected
                    else 0
                ),
                "example_qid_pairs": "|".join(f"{a}>{b}" for a, b in sorted(pairs)[:3]),
                "example_eventkg_ids": "|".join(
                    (source_ids or {}).get((role_key, pair), "")
                    for pair in sorted(pairs)[:3]
                ),
            }
        )
    rows.sort(
        key=lambda row: (-row["shared_pairs"], row["ek_role"], row["wd_property"])
    )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    population = set(
        (BASE / "wikidata_qids.txt").read_text(encoding="utf-8").splitlines()
    )
    r2q, kind = resource_qids()
    wd, wd_stats = wd_pairs(population)
    ek_pairs: dict[tuple[str, str, str, str, str], set[tuple[str, str]]] = defaultdict(
        set
    )
    source_ids: dict[tuple[tuple[str, str, str, str, str], tuple[str, str]], str] = {}
    stats = Counter()
    for name in REIFIED:
        if not complete(name):
            stats[f"incomplete_{name}"] = 1
            continue
        for relation, graph, role, subject, target in reified_groups(name):
            stats[f"reified_{name}"] += 1
            qs, qt = r2q.get(subject), r2q.get(target)
            if not qs or not qt:
                stats[f"unmapped_endpoint_{name}"] += 1
                continue
            if graph == WD_GRAPH:
                stats["reified_wikidata_copy"] += 1
                continue
            key = (short(role), short(graph), kind[qs], kind[qt], "reified")
            pair = (qs, qt)
            ek_pairs[key].add(pair)
            source_ids.setdefault((key, pair), short(relation))
    for name in DIRECT:
        if not complete(name):
            stats[f"incomplete_{name}"] = 1
            continue
        for subject, predicate, target, graph in direct_edges(name):
            stats[f"direct_{name}"] += 1
            qs, qt = r2q.get(subject), r2q.get(target)
            if not qs or not qt:
                stats[f"unmapped_direct_{name}"] += 1
                continue
            if graph == WD_GRAPH:
                stats["direct_wikidata_copy"] += 1
                continue
            key = (short(predicate), short(graph), kind[qs], kind[qt], "direct")
            pair = (qs, qt)
            ek_pairs[key].add(pair)
            source_ids.setdefault((key, pair), short(subject))
    rows = score_candidates(ek_pairs, wd, source_ids)
    write_csv(OUT / "eventkg_wikidata_candidates.csv", rows)
    with (AUDIT / "joint_relation_pairs.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        war_rows = list(csv.DictReader(stream))
    war_distinct = {(row["war_subject_qid"], row["war_object_qid"]) for row in war_rows}
    war_votes: dict[tuple, set[tuple[str, str]]] = defaultdict(set)
    war_ek_pairs: set[tuple[str, str]] = set()
    for row in war_rows:
        pair = row["war_subject_qid"], row["war_object_qid"]
        for ek_key, pairs in ek_pairs.items():
            for direction, oriented in (("same", pair), ("reverse", pair[::-1])):
                if oriented in pairs:
                    war_votes[(row["war_predicate"], *ek_key, direction)].add(pair)
                    war_ek_pairs.add(pair)
    war_candidate_rows = [
        {
            "war_predicate": key[0],
            "ek_role": key[1],
            "ek_graph": key[2],
            "subject_kind": key[3],
            "object_kind": key[4],
            "format": key[5],
            "direction": key[6],
            "shared_pairs": len(pairs),
            "example_qid_pairs": "|".join(f"{a}>{b}" for a, b in sorted(pairs)[:3]),
        }
        for key, pairs in war_votes.items()
    ]
    war_candidate_rows.sort(
        key=lambda row: (-row["shared_pairs"], row["war_predicate"], row["ek_role"])
    )
    write_csv(OUT / "warsampo_eventkg_candidates.csv", war_candidate_rows)
    with (AUDIT / "identity_candidates.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        identity_status = Counter(
            row["review_status"] for row in csv.DictReader(stream)
        )
    result = {
        "population_qids": len(population),
        "eventkg_mapped_qids": len(kind),
        "wikidata": dict(wd_stats),
        "wikidata_distinct_pairs": len(wd),
        "eventkg": dict(stats),
        "eventkg_non_wikidata_role_groups": len(ek_pairs),
        "candidate_rows": len(rows),
        "date_checks": date_variants(r2q),
        "warsampo_screened_shared_pairs": len(war_distinct),
        "warsampo_identity_status": dict(identity_status),
        "warsampo_eventkg_shared_pairs": len(war_ek_pairs),
        "warsampo_eventkg_candidate_rows": len(war_candidate_rows),
        "complete_eventkg_files": [
            name for name in (*REIFIED, *DIRECT) if complete(name)
        ],
        "incomplete_eventkg_files": [
            name for name in (*REIFIED, *DIRECT) if not complete(name)
        ],
    }
    (OUT / "run_summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    for row in rows[:20]:
        print(row)
    for row in war_candidate_rows[:10]:
        print(row)


if __name__ == "__main__":
    main()
