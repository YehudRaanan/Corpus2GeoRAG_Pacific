"""Model-to-graph S2T exporter; no acquisition, matching or source selection.

Contract: docs/ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md sections 2-8. Geography
and original date precision/calendar stay in the model for the Agent join.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from .graph_contract import endpoint_index, graph_node_id
from .poc import digest, read_json
from .relations import date_parts


def event_date_attributes(event: dict) -> dict[str, str]:
    """S2T 4: native earliest start/latest end, without the relation 1900 floor.

    The model retains every original value and its precision/calendar. Existing
    P585 coverage ranges already supply bounds; do not mint a point. Explicit
    bounds with several point dates keep those bounds and omit the scalar point
    (owner approval, 23 October 2026); no new coverage range is derived here.
    This helper is shared with the Agent's model-backed date validation.
    """
    result = {}
    for field, choose in (("start_date", min), ("end_date", max), ("point_date", min)):
        values = event.get(field) or []
        if not isinstance(values, list) or any(
            not isinstance(v, dict) or not v.get("time") for v in values
        ):
            raise ValueError(f"Unsupported Event date: {event['event_id']} {field}")
        if not values:
            continue
        if len({v.get("calendarmodel") for v in values}) > 1:
            raise ValueError(f"Mixed Event calendars: {event['event_id']} {field}")
        times = {v["time"] for v in values}
        for value in times:
            date_parts(value)
        if field == "point_date" and len(times) > 1:
            if not (
                event.get("temporal_evidence", {}).get("derived_range")
                or event.get("start_date")
                or event.get("end_date")
            ):
                raise ValueError(f"Unbounded multiple points: {event['event_id']}")
            continue
        result[field] = choose(times, key=date_parts)
    return result


def build_graph(
    entities: list[dict],
    events: list[dict],
    relations: list[dict],
    mapping: list[dict],
    directions: list[dict],
    metadata: dict,
) -> tuple[dict, dict]:
    """Copy the completed model; reject unsupported values instead of repairing."""
    for key in ("schema_version", "relation_map_version", "release_status", "scope"):
        if not metadata.get(key):
            raise ValueError(f"Caller must supply release metadata: {key}")
    version = metadata["relation_map_version"]
    if any(
        r["relation_map_version"] != version for r in mapping + directions + relations
    ):
        raise ValueError("Applied relation mapping versions differ")
    event_by_id = {e["event_id"]: e for e in events}
    if len(event_by_id) != len(events):
        raise ValueError("Duplicate Event IDs")
    nodes, date_decisions = [], []
    for entity in entities:
        stored_type = entity["type"]
        if stored_type == "DATE":
            continue  # S2T 2: all DATE rows remain in the temporal source model.
        qid = entity["entity_id"]
        if not isinstance(entity.get("name"), str) or not entity["name"].strip():
            raise ValueError(f"Missing entity name: {qid}")
        aliases = entity.get("aliases") or []
        if not isinstance(aliases, list) or not all(
            isinstance(a, str) for a in aliases
        ):
            raise ValueError(f"Non-string entity aliases: {qid}")
        node = dict(
            id=graph_node_id(qid, stored_type),
            wikidata_id=None if qid.startswith("SYN_") else qid,
            name=entity["name"],
            type={"PER": "person", "ORG": "org", "LOC": "location"}.get(
                stored_type, stored_type
            ),
            aliases=aliases,
        )
        if stored_type == "event":
            event = event_by_id[qid]
            attributes = event_date_attributes(event)
            if attributes:
                node["attributes"] = attributes
            # Native class-QID lists are not approved Agent kind labels (S2T 4).
            if event.get("kind") or any(
                len(event.get(k) or []) > 1
                for k in ("start_date", "end_date", "point_date")
            ):
                date_decisions.append(
                    dict(
                        event_id=qid,
                        selected_dates=attributes,
                        original_dates={
                            k: event.get(k)
                            for k in ("start_date", "end_date", "point_date")
                        },
                        omitted_kind=event.get("kind"),
                        derived_range=event.get("temporal_evidence", {}).get(
                            "derived_range", {}
                        ),
                    )
                )
        nodes.append(node)
    if {n["wikidata_id"] for n in nodes if n["type"] == "event"} != set(event_by_id):
        raise ValueError("Event and event-typed Entity populations differ")

    # Population S2T is Wikidata-only. Reuse its exact (source, predicate) key,
    # rather than importing a different provider's classification of the ID.
    applied_keys = {
        (r["selected_source"], r["selected_source_predicate"]) for r in relations
    }
    by_id, applied = defaultdict(list), {}
    for row in mapping:
        by_id[row["level2_relation_id"]].append(row)
        key = row["source"], row["source_predicate"]
        if key in applied_keys:
            if key in applied:
                raise ValueError(f"Duplicate applied mapping key: {key}")
            applied[key] = row
    if set(applied) != applied_keys:
        raise ValueError(f"Missing applied mapping keys: {applied_keys - set(applied)}")
    lookup = {}
    for row in directions:
        key = row["input_relation_id"]
        if key in lookup and lookup[key] != row:
            raise ValueError(f"Conflicting reverse lookup: {key}")
        lookup[key] = row
    catalog, edges, ids = {}, [], set()

    def catalog_entry(relation_id: str, label: str, family: str) -> None:
        families = {family}
        definition = dict(
            id=relation_id,
            labels=[label],
            level1_families=[family],
            source_predicates=[],
        )
        for row in applied.values():
            if row["level2_relation_id"] == relation_id:
                if row["level2_relation_label"] != label:
                    raise ValueError(
                        f"Conflicting applied catalog definition: {relation_id}"
                    )
                families.add(row["level1_family"])
                item = dict(
                    source=row["source"],
                    predicate=row["source_predicate"],
                    direction=row["direction_to_level2"],
                )
                if item not in definition["source_predicates"]:
                    definition["source_predicates"].append(item)
        if relation_id in catalog:
            previous = catalog[relation_id]
            if previous["labels"] != definition["labels"]:
                raise ValueError(
                    f"Conflicting directional catalog label: {relation_id}"
                )
            families.update(previous["level1_families"])
        # Existing draft builder Step 7 collects supplied family values into a
        # sorted set. UNRESOLVED records an unassigned state, not a second
        # assigned category; each assertion keeps its own family unchanged.
        if len(families - {"UNRESOLVED", ""}) > 1:
            raise ValueError(f"Conflicting assigned catalog families: {relation_id}")
        definition["level1_families"] = sorted(families)
        catalog[relation_id] = definition

    for row in relations:
        relation_id = row["level2_relation"]
        rule = applied[row["selected_source"], row["selected_source_predicate"]]
        if (
            rule["level2_relation_id"],
            rule["level1_family"],
            rule["level2_relation_label"],
        ) != (relation_id, row["level1_relation"], row["level2_label"]):
            raise ValueError(f"Applied mapping differs: {row['observation_id']}")
        if row["count"] != 1:
            raise ValueError(f"Unexpected assertion count: {row['observation_id']}")
        edge = dict(
            id=row["observation_id"],
            source=row["subject_entity_id"],
            target=row["object_entity_id"],
            type=relation_id,
            relation_family=row["level1_relation"],
            count=row["count"],
        )
        for target, source in (
            ("start_date", "time_from"),
            ("end_date", "time_to"),
            ("point_date", "time_point"),
        ):
            edge[target] = row.get(source) or None
            if edge[target] is not None:
                date_parts(edge[target])
        catalog_entry(relation_id, row["level2_label"], row["level1_relation"])
        edges.append(edge)
        if edge["source"] != edge["target"]:
            reverse = lookup[relation_id]
            if reverse["endpoint_action"] != "SWAP_SOURCE_TARGET":
                raise ValueError(f"Unsupported reverse endpoint action: {relation_id}")
            reverse_id, label = (
                reverse["output_reverse_relation_id"],
                reverse["output_reverse_relation_label"],
            )
            catalog_entry(reverse_id, label, edge["relation_family"])
            edges.append(
                dict(
                    edge,
                    id=edge["id"] + "::REVERSE",
                    source=edge["target"],
                    target=edge["source"],
                    type=reverse_id,
                    relation_label=label,
                    direction_pair_id=reverse["direction_pair_id"],
                    base_level2_relation_id=relation_id,
                    derived=True,
                    derived_direction="REVERSE",
                    source_edge_id=edge["id"],
                )
            )
    for edge in edges:
        if edge["id"] in ids:
            raise ValueError(f"Duplicate directional view ID: {edge['id']}")
        ids.add(edge["id"])
    index = endpoint_index(nodes, edges)
    report = dict(
        entity_rows=len(entities),
        nodes=len(nodes),
        model_only_date_rows=sum(e["type"] == "DATE" for e in entities),
        events=len(events),
        base_assertions=len(relations),
        directional_views=len(edges),
        reverse_views=len(edges) - len(relations),
        self_assertions=sum(
            r["subject_entity_id"] == r["object_entity_id"] for r in relations
        ),
        relation_definitions=len(catalog),
        multi_type_qids=sum(len(v) > 1 for v in index.values()),
        node_types=dict(Counter(n["type"] for n in nodes)),
        unassigned_reverse_family_pairs={
            key: value["level1_families"]
            for key, value in catalog.items()
            if len(value["level1_families"]) > 1
        },
        event_serialization=date_decisions,
        unused_provider_family_conflicts=[
            dict(
                relation_id=rid,
                applied_family=definition["level1_families"],
                unused_definitions=[
                    dict(
                        source=r["source"],
                        predicate=r["source_predicate"],
                        family=r["level1_family"],
                    )
                    for r in by_id[rid]
                    if (r["source"], r["source_predicate"]) not in applied_keys
                    and r["level1_family"] not in definition["level1_families"]
                ],
            )
            for rid, definition in catalog.items()
            if any(
                r["level1_family"] not in definition["level1_families"]
                for r in by_id[rid]
            )
        ],
        geography="MODEL_ONLY_NOT_EXPORTED",
        precision_calendar="RETAINED_IN_MODEL_REQUIRES_AGENT_MODEL_JOIN",
    )
    return (
        dict(
            metadata=dict(metadata), relation_catalog=catalog, nodes=nodes, edges=edges
        ),
        report,
    )


def run(
    model_dir: Path, metadata: dict, output: Path, *, dry_run: bool = False
) -> dict:
    """Pin consumed model/mapping files and write only to a new output directory."""
    if output.exists():
        raise ValueError("Use a new graph export output directory")
    manifest = read_json(model_dir / "manifest.json")
    inputs = {"manifest.json": digest(model_dir / "manifest.json")}
    data = {}
    for name in ("entities", "events", "relations"):
        file = name + ".json.gz"
        sha = digest(model_dir / file)
        if manifest["outputs"].get(file) != sha:
            raise ValueError(f"Model checksum differs: {file}")
        inputs[file] = sha
        data[name] = read_json(model_dir / file)
    tables = []
    for prefix in ("RELATION_MAPPING_TABLE", "RELATION_DIRECTION_LOOKUP"):
        paths = list((model_dir / "mapping").glob(prefix + "_v*.csv"))
        if len(paths) != 1:
            raise ValueError(f"Require one pinned mapping file: {prefix}")
        path = paths[0]
        sha = digest(path)
        # event_model extends these generated catalogs after reading its pinned
        # historical inputs. Pin the actual generated files at export, rather
        # than confusing those input hashes with generated-output checksums.
        relative = str(path.relative_to(model_dir))
        expected = manifest["outputs"].get(relative)
        if expected is not None and expected != sha:
            raise ValueError(f"Mapping checksum differs: {path.name}")
        inputs[relative] = sha
        with path.open(encoding="utf-8-sig", newline="") as stream:
            tables.append(list(csv.DictReader(stream)))
    graph, report = build_graph(
        **data, mapping=tables[0], directions=tables[1], metadata=metadata
    )
    report.update(
        status=(
            "DRY_RUN_VALIDATED" if dry_run else "GRAPH_WRITTEN_PENDING_AGENT_VALIDATION"
        ),
        inputs=inputs,
        model_dir=str(model_dir.resolve()),
        metadata=metadata,
        graph_written=not dry_run,
        mapping_checksum_scope="GENERATED_MODEL_MAPPING_PINNED_AT_EXPORT",
    )
    output.mkdir(parents=True)
    if not dry_run:
        path = output / "graph.json"
        path.write_text(
            json.dumps(graph, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        if read_json(path) != graph:
            raise ValueError("Written graph differs on readback")
        report["graph_readback_verified"] = True
        report["graph_sha256"] = digest(path)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = run(
        args.model_dir, read_json(args.metadata), args.output, dry_run=args.dry_run
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("status", "nodes", "base_assertions", "directional_views")
            }
        )
    )


if __name__ == "__main__":
    main()
