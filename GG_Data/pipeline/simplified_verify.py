"""Independent full-population raw JSON and model integrity checks."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import logging
import os
import shutil
import struct
from collections import Counter, defaultdict
from itertools import zip_longest
from pathlib import Path

import ijson
import pyarrow.parquet as pq

from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.simplified_agent import entity_id, write_array, write_object

LOG = logging.getLogger(__name__)


def verify_corrected_sources(
    model: Path, pages: list[dict], events: list[dict]
) -> dict:
    """Rebuild page candidates and verify each retained Event against source facts."""
    from Agent.geo_agent.compact_dates import date_bounds
    from GG_Data.pipeline.post_qid_events import _occurrence_types
    from GG_Data.pipeline.simplified_correction import (
        event_date_payload,
        native_dates,
        scoped_decision,
    )
    from GG_Data.pipeline.simplified_war_scope import war_paths, wiki_partof

    manifest = read_json(model / "manifest.json")
    inputs = {
        Path(r["path"]).name: Path(r["path"]) for r in manifest["correction_inputs"]
    }
    for row in manifest["correction_inputs"]:
        if digest(Path(row["path"])) != row["sha256"]:
            raise ValueError("Changed correction source: " + row["path"])
    root = inputs["source_facts_v4.json"].parent
    facts = read_json(inputs["source_facts_v4.json"])
    own = read_json(inputs["own_scope_audit_v3.json"])
    native = read_json(inputs["event_native_records_v2.json"])
    graph = read_json(inputs["event_partof_graph_v2.json"])
    mapping = read_json(root / "war_wiki_ancestors/title_mapping.json")
    paths = war_paths(graph, own, mapping)
    titles = {
        r["target_title"]: r.get("qid")
        for r in read_json(root.parent / "page_link_metadata/title_mapping.json.gz")
    }
    candidates = {
        (p["page_index"], q)
        for p in pages
        for q in (
            {titles[t] for t in p["links"] if titles.get(t)}
            | ({p["source_subject_qid"]} if p.get("source_subject_qid") else set())
        )
    }
    audit = read_json(model / "event_recognition_audit.json.gz")
    if (
        len(audit) != len(candidates)
        or {(a["page_index"], a["qid"]) for a in audit} != candidates
    ):
        raise ValueError("Event candidate audit does not cover source pages")
    ancestors = read_json(inputs["type_ancestors_final.json"])
    hierarchy = Path(manifest["event_rule"][0]["path"]).parent
    types, _ = _occurrence_types(hierarchy, manifest["event_approval_sha256"])
    decisions = {
        q: scoped_decision(q, facts.get(q, {}), own.get(q, {}), ancestors, types, paths)
        for q in {q for _, q in candidates}
    }
    for row in audit:
        if (
            row.get("decision") != decisions[row["qid"]]
            or row["status"] != decisions[row["qid"]]["status"]
        ):
            raise ValueError("Event recognition differs from pinned source decision")
    accepted = {q for q, d in decisions.items() if d["status"] == "EVENT"}
    if {r["native_records"][0]["qid"] for r in events} != accepted:
        raise ValueError("WWII Event population differs from source decisions")
    checked_sources = set()
    for q in accepted:
        for edge in paths[q]:
            prop = edge["property"]
            if prop in {"P361", "P527_INVERSE"}:
                source = edge["source_qid"]
                target = edge["to"] if prop == "P361" else edge["from"]
                p = "P361" if prop == "P361" else "P527"
                statements = native.get(source, {}).get("claims", {}).get(p, [])
                if not any(
                    s.get("rank") != "deprecated"
                    and s.get("id") == edge.get("statement_id")
                    and s.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value", {})
                    .get("id")
                    == target
                    for s in statements
                ):
                    raise ValueError("WWII path has no native source statement")
            elif prop == "WIKI_INFOBOX_PARTOF":
                source = own[edge["from"]]["source"]
                path = Path(source["path"])
                if source["path"] not in checked_sources:
                    if digest(path) != source["sha256"]:
                        raise ValueError("WWII Wiki source changed")
                    checked_sources.add(source["path"])
                parts = wiki_partof(read_json(path).get("raw", ""))
                if not any(
                    all(
                        part.get(k) == edge.get(k)
                        for k in ["target_title", "field", "raw_value", "template"]
                    )
                    and mapping.get(part["target_title"]) == edge["to"]
                    for part in parts
                ):
                    raise ValueError("WWII path is absent from own infobox")
            else:
                raise ValueError("Unsupported war connection proof")

    def check_dates(values):
        for period in values.get("periods", []):
            check_dates(period)
        for key in ["start_date", "end_date", "point_date"]:
            for value in values.get(key, []):
                date_bounds(value)

    for event in events:
        q = event["native_records"][0]["qid"]
        if q not in native or native_dates(native[q]) != facts[q]["dates"]:
            raise ValueError("Event dates are not bound to native records")
        expected = event_date_payload(
            facts[q]["dates"],
            own.get(q, {}),
            cancelled="Q114350932" in facts[q]["native_types"],
            owner_policy=True,
        )
        if any(event.get(k) != v for k, v in expected.items()):
            raise ValueError("Event dates differ from source payload")
        check_dates(event["event_dates"])
        check_dates(event["planned_dates"])
    return dict(
        status="PASS",
        source_page_candidates=len(candidates),
        wwii_events=len(accepted),
        connection_rule="P361; INVERSE_P527; OWN_WIKI_INFOBOX_PARTOF; ROOT_Q362",
        date_statuses=dict(Counter(e["date_status"] for e in events)),
    )


def verify_population(prepared: Path, model: Path) -> dict:
    manifest = read_json(model / "manifest.json")
    for rule in manifest.get("event_rule", []):
        if digest(Path(rule["path"])) != rule["sha256"]:
            raise ValueError("Changed Event rule: " + rule["path"])
    for name, sha in manifest["outputs"].items():
        if digest(model / name) != sha:
            raise ValueError(f"Changed model artifact: {name}")
    if digest(model / "mentions.json.gz") != digest(prepared / "mentions.json.gz"):
        raise ValueError("Original raw mentions changed")
    entities = read_json(model / "entities.json.gz")
    by_id = {r["entity_id"]: r for r in entities}
    original = read_json(prepared / "entities.json.gz")
    corrected = (
        manifest.get("event_identity")
        == "NATIVE_SOURCE_QID; NER_EXACT_NAME_TYPE_UNCHANGED"
    )
    exclusions = read_json(model / "entity_exclusions.json.gz") if corrected else []
    excluded = {r["entity_id"]: r for r in exclusions}
    original_by_id = {r["entity_id"]: r for r in original}
    from GG_Data.pipeline.simplified_correction import invalid_reason

    if len(excluded) != len(exclusions) or any(
        r["entity_id"] not in original_by_id
        or invalid_reason(r["name"]) is None
        or r.get("reason") != invalid_reason(r["name"])
        or any(
            r.get(k) != original_by_id[r["entity_id"]][k]
            for k in ["name", "type", "mention_count"]
        )
        or r["entity_id"] in by_id
        for r in exclusions
    ):
        raise ValueError("Unproved original Entity exclusion")
    if len(by_id) != len(entities) or any(
        r["node_index"] != i
        or r["type"] == "DATE"
        or (
            len(r.get("native_ids", [])) != 1
            or r["entity_id"] != "event:" + r["native_ids"][0]
            if corrected and r["type"] == "event"
            else entity_id(r["name"], r["type"]) != r["entity_id"]
        )
        for i, r in enumerate(entities)
    ):
        raise ValueError("Invalid full exact-key population")
    for row in original:
        if row["entity_id"] in excluded:
            continue
        saved = by_id.get(row["entity_id"], {})
        if any(saved.get(k) != row[k] for k in ["name", "type", "mention_count"]):
            raise ValueError("Original exact-key entity changed or disappeared")
    pages = read_json(model / "wiki_pages.json.gz")
    canonical = {p["page_index"]: p["canonical_page_index"] for p in pages}
    old_pages = read_json(prepared / "wiki_pages.json.gz")
    if {(p["page_index"], p["source_key"]) for p in pages} != {
        (p["page_index"], p["source_key"]) for p in old_pages
    }:
        raise ValueError("Source page scope changed")
    expected = {
        (m["entity_id"], canonical[m["page_index"]])
        for m in read_json(prepared / "memberships.json.gz")
        if m["entity_id"] not in excluded
    }
    qid_to_id = {}
    event_rows = read_json(model / "event_events.json.gz")
    source_verification = (
        verify_corrected_sources(model, pages, event_rows) if corrected else None
    )
    for event in event_rows:
        key = event["entity_id"]
        if key not in by_id or by_id[key]["type"] != "event":
            raise ValueError("Event foreign key failed")
        for native in event["native_records"]:
            qid_to_id[native["qid"]] = key
    statuses = Counter()
    for row in read_json(model / "event_recognition_audit.json.gz"):
        statuses[row["status"]] += 1
        if row["status"] == "EVENT":
            if row["qid"] not in qid_to_id or (
                not row["recognized_types"]
                and row.get("decision", {}).get("reason")
                != "OWN_EVENT_INFOBOX_NO_NATIVE_TYPE"
            ):
                raise ValueError("Recognized page event missing from population")
            expected.add((qid_to_id[row["qid"]], canonical[row["page_index"]]))
    memberships = read_json(model / "memberships.json.gz")
    actual = {(m["entity_id"], m["page_index"]) for m in memberships}
    if (
        actual != expected
        or len(actual) != len(memberships)
        or any(
            by_id[m["entity_id"]]["node_index"] != m["node_index"] for m in memberships
        )
    ):
        raise ValueError(
            "Full membership population differs from original and page events"
        )
    binary = [
        (r["node_index"], r["page_index"])
        for batch in pq.ParquetFile(model / "memberships.parquet").iter_batches()
        for r in batch.to_pylist()
    ]
    if len(binary) != len(memberships) or set(binary) != {
        (r["node_index"], r["page_index"]) for r in memberships
    }:
        raise ValueError("Binary memberships differ from verified JSON memberships")
    entity_counts = Counter(k for k, _ in actual)
    if any(r["page_count"] != entity_counts[r["entity_id"]] for r in entities):
        raise ValueError("Full entity denominator differs from membership")
    page_sizes = Counter(p for _, p in actual)
    return dict(
        status="PASS",
        exact_original_entities=len(original),
        excluded_invalid_entity_keys=len(excluded),
        retained_original_entities=len(original) - len(excluded),
        entities=len(entities),
        events=sum(r["type"] == "event" for r in entities),
        memberships=len(actual),
        event_recognition_statuses=dict(statuses),
        raw_shared_page_count_sum=sum(c * (c - 1) // 2 for c in page_sizes.values()),
        source_revision_status="DANIEL_EXACT_REVISION_UNKNOWN",
        corrected_source_verification=source_verification,
    )


def verify_graph_nodes(model: Path, graph: Path) -> dict:
    """Bind every Agent endpoint and denominator to the independent JSON model."""
    from Agent.geo_agent.compact_format import records
    from GG_Data.pipeline.simplified_relations import TYPES

    entities = read_json(model / "entities.json.gz")
    events = {e["entity_id"]: e for e in read_json(model / "event_events.json.gz")}
    memberships = defaultdict(set)
    for row in read_json(model / "memberships.json.gz"):
        memberships[row["node_index"]].add(row["page_index"])
    reader = records(graph)
    try:
        _, metadata = next(reader)
        if metadata["node_count"] != len(entities):
            raise ValueError("Graph node count differs from model")
        for row in entities:
            kind, node = next(reader)
            attrs = node.get("attributes", {})
            if kind != "node" or (
                node["id"],
                node["name"],
                node["type"],
                attrs.get("entity_group"),
                attrs.get("page_count"),
                attrs.get("page_indices"),
                attrs.get("mention_count"),
            ) != (
                row["entity_id"],
                row["name"],
                TYPES.get(row["type"], row["type"]),
                row["type"],
                row["page_count"],
                sorted(memberships[row["node_index"]]),
                row["mention_count"],
            ):
                raise ValueError(
                    f"Graph node differs from verified model: {row['entity_id']}"
                )
            if row["entity_id"] in events:
                event = events[row["entity_id"]]
                if any(
                    attrs.get(field) != event.get(field)
                    for field in [
                        "event_dates",
                        "planned_dates",
                        "date_status",
                        "date_selection",
                        "date_normalization",
                    ]
                ):
                    raise ValueError("Graph Event dates differ from the model")
        manifest = read_json(model / "manifest.json")
        pages = {
            r["canonical_page_index"]: r
            for r in reversed(read_json(model / "wiki_pages.json.gz"))
        }
        expected_pages = [
            {
                k: r[k]
                for k in [
                    "page_index",
                    "source_key",
                    "title",
                    "wiki_page_id",
                    "revision_id",
                ]
            }
            for r in pages.values()
        ]
        if metadata["page_scope_id"] != manifest["page_scope_id"] or sorted(
            metadata["pages"], key=lambda r: r["page_index"]
        ) != sorted(expected_pages, key=lambda r: r["page_index"]):
            raise ValueError("Agent page scope differs from model")
        return dict(
            status="PASS",
            nodes_verified=len(entities),
            complete_membership_binding=True,
        )
    finally:
        reader.close()


def verify_geography(model: Path, acceptance: dict) -> dict:
    """Independently compare all model LOC shapes/statuses to the loaded Agent."""
    places = {
        r["entity_id"]
        for r in read_json(model / "entities.json.gz")
        if r["type"] == "LOC"
    }
    rows = read_json(model / "geography.json.gz")
    by_id = {r["place_id"]: r for r in rows}
    if len(rows) != len(places) or set(by_id) != places:
        raise ValueError("Geography does not account for every exact LOC key")
    status = read_json(model / "manifest.json").get(
        "geography_status", "PENDING_LAST_STAGE"
    )
    if acceptance["geography_status"] != status:
        raise ValueError("Agent and model Geography stage differ")
    row_sha = hashlib.sha256()
    for key, row in sorted(by_id.items()):
        if status.startswith("COMPLETE") and (
            "PENDING" in row["status"] or not row["status"]
        ):
            raise ValueError("Geography still contains pending targets")
        row_sha.update(
            json.dumps(
                [key, row.get("geometry"), row["status"]],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        )
    checked = acceptance["geography"]
    if (
        checked["locations"] != len(places)
        or checked["geometry_rows_sha256"] != row_sha.hexdigest()
    ):
        raise ValueError("Agent Geography differs from complete model Geography")
    bundle_check = None
    if status.startswith("COMPLETE"):
        bundle = model / "geography_evidence.json.gz"
        artifacts = {}
        with gzip.open(bundle, "rb") as stream:
            for record in ijson.items(stream, "item", use_float=True):
                if (
                    record["original_path"] in artifacts
                    or record["encoding"] != "base64"
                ):
                    raise ValueError("Duplicate or unsupported Geography evidence")
                if (
                    hashlib.sha256(
                        base64.b64decode(record["content_base64"], validate=True)
                    ).hexdigest()
                    != record["sha256"]
                ):
                    raise ValueError("Portable Geography evidence hash differs")
                artifacts[record["original_path"]] = (
                    record["artifact_path"],
                    record["sha256"],
                )
        for row in rows:
            evidence = row.get("evidence")
            if evidence and (
                evidence["path"] not in artifacts
                or artifacts[evidence["path"]][1] != evidence["sha256"]
            ):
                raise ValueError("Geography audit is not portable")
            receipt = (row.get("selection") or {}).get("receipt")
            if (
                receipt
                and not receipt.endswith(".zip")
                and receipt not in artifacts
                and not any(
                    p.startswith(receipt.rstrip("/\\") + os.sep) for p in artifacts
                )
            ):
                raise ValueError("Selected Geography receipt is not portable")
        bundle_check = dict(
            status="PASS",
            artifact_count=len(artifacts),
            sha256=digest(bundle),
            format="geography-evidence-base64-v1",
            original_paths_resolve_without_source_files=True,
        )
    return dict(
        status=status,
        locations=len(places),
        status_counts=dict(Counter(r["status"] for r in rows)),
        geometry_rows_sha256=row_sha.hexdigest(),
        spatial_checks=checked["spatial_checks"],
        evidence_bundle=bundle_check,
    )


def package_correction_sources(model: Path, output: Path) -> list[dict]:
    """Preserve exact correction evidence with portable path/hash bindings."""
    manifest = read_json(model / "manifest.json")
    pinned = manifest.get("correction_inputs", [])
    if not pinned:
        return []
    root = Path(pinned[0]["path"]).parent
    paths = {Path(row["path"]).resolve() for row in pinned}
    own = read_json(root / "own_scope_audit_v3.json")
    for row in own.values():
        source = row.get("source", {})
        if source.get("path"):
            path = Path(source["path"]).resolve()
            if digest(path) != source["sha256"]:
                raise ValueError("Correction own-page source changed")
            paths.add(path)
    for name in [
        "class_graph.json.gz",
        "class_graph_manifest.json",
        "fragment_mention_evidence.json.gz",
        "fragment_quality_census.json",
    ]:
        if (root / name).is_file():
            paths.add((root / name).resolve())
    for folder in [
        "content",
        "native_refresh",
        "maxlag_resume_1",
        "type_refresh",
        "event_own_pages",
        "event_own_pages_dated",
        "event_own_pages_link_titles",
        "event_own_pages_new_candidates",
        "untyped_own_pages",
        "war_wiki_ancestors",
        "war_parent_sources",
    ]:
        if (root / folder).is_dir():
            paths.update(
                p.resolve()
                for p in (root / folder).rglob("*")
                if p.is_file()
                and (p.name.endswith(".json") or p.name.endswith(".json.gz"))
            )
    bundle = output / "correction_evidence"
    bundle.mkdir()
    entries = []
    for path in sorted(paths):
        relative = (
            path.relative_to(root.resolve())
            if path.is_relative_to(root.resolve())
            else Path("external")
            / (hashlib.sha256(str(path).encode()).hexdigest()[:16] + "_" + path.name)
        )
        target = bundle / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        os.link(path, target)
        entries.append(
            dict(
                original_path=str(path),
                artifact_path=target.relative_to(output).as_posix(),
                sha256=digest(target),
            )
        )
    write_object(bundle / "index.json", entries)
    return entries


def verify_and_package(prepared: Path, model: Path, graph: Path, output: Path) -> dict:
    """Publish immutable JSON files only after full model and Agent checks pass."""
    if output.exists():
        raise FileExistsError(output)
    population = verify_population(prepared, model)
    graph_nodes = verify_graph_nodes(model, graph / "agent_graph.json.gz")
    graph_manifest = read_json(graph / "manifest.json")
    for name, sha in graph_manifest["outputs"].items():
        if digest(graph / name) != sha:
            raise ValueError(f"Changed graph artifact: {name}")
    acceptance = read_json(graph / "agent_acceptance.json")
    geography = verify_geography(model, acceptance)
    agent_root = Path(__file__).resolve().parents[2] / "Agent"
    code_paths = sorted((agent_root / "geo_agent").glob("*.py"))
    if {p.name: digest(p) for p in code_paths} != acceptance["agent_code_sha256"]:
        raise ValueError("Agent adapter differs from the fully verified code")
    raw_report = read_json(prepared.parent / "raw_verification.json")
    if (
        acceptance["status"] != "PASS"
        or acceptance["graph_sha256"] != digest(graph / "agent_graph.json.gz")
        or acceptance["node_count"] != population["entities"]
        or acceptance["coverage"]["raw_shared_page_count_sum"]
        != population["raw_shared_page_count_sum"]
        or graph_manifest["model_manifest_sha256"] != digest(model / "manifest.json")
        or raw_report["status"] != "PASS"
        or raw_report["prepared_manifest_sha256"] != digest(prepared / "manifest.json")
    ):
        raise ValueError("Acceptance reports do not match this complete population")
    rows_sha = hashlib.sha256()
    count = 0
    with gzip.open(graph / "relations.json.gz", "rb") as stream:
        for row in ijson.items(stream, "item", use_float=True):
            rows_sha.update(struct.pack("<qqqdd", *row))
            count += 1
            if count % 10000000 == 0:
                LOG.info("Relations JSON rows compared %s", count)
    if (
        count != acceptance["coverage"]["pair_count"]
        or rows_sha.hexdigest() != acceptance["coverage"]["pair_rows_sha256"]
    ):
        raise ValueError("Relations JSON differs from the fully verified Agent graph")
    output.mkdir()
    correction_evidence = package_correction_sources(model, output)
    model_manifest = read_json(model / "manifest.json")
    for folder, destination in [(model, "model"), (graph, "agent")]:
        target = output / destination
        target.mkdir()
        for path in folder.iterdir():
            if (
                path.is_file()
                and not path.name.endswith(".sqlite.json")
                and (
                    destination == "model"
                    or path.name.endswith(".json")
                    or path.name.endswith(".json.gz")
                )
            ):
                os.link(path, target / path.name)
    os.link(prepared.parent / "raw_verification.json", output / "raw_verification.json")
    adapter = output / "agent_adapter"
    (adapter / "geo_agent").mkdir(parents=True)
    for path in code_paths:
        # Copy code: later development must not mutate the release via a hard link.
        shutil.copyfile(path, adapter / "geo_agent" / path.name)
    for name in ["pyproject.toml", "README.md"]:
        shutil.copyfile(agent_root / name, adapter / name)
    write_object(
        output / "agent_contract.json",
        dict(
            format="simplified-cooccurrence-v1",
            graph="agent/agent_graph.json.gz",
            adapter="agent_adapter/geo_agent",
            loader="geo_agent.graph_store.GraphStore.from_json",
            edge_columns=[
                "source_index",
                "target_index",
                "shared_page_count",
                "strength_source_target",
                "strength_target_source",
            ],
            entity_index="model/entities.json.gz node_index",
            complete_pair_population=True,
            derived_index="Read-only SQLite index is built locally on first load; it is not required for interchange",
            edge_count_semantics="Integer shared-page count; fractional weights use each endpoint's distinct-page denominator",
            relation_semantics="PAGE_CO_OCCURRENCE_ONLY",
            date_policy=model_manifest.get("date_policy", "SOURCE_DATE_UNKNOWN"),
            event_scope=model_manifest.get("event_scope", "SOURCE_PAGES"),
            deferred_reviews=model_manifest.get("deferred_reviews", []),
            temporal_semantics="Date filters use exported Event endpoint ranges, including explicitly marked OWNER defaults and planned dates; coappearance edges have no occurrence date",
            correction_evidence=(
                "correction_evidence/index.json" if correction_evidence else None
            ),
            geography_status=geography["status"],
            geography_evidence=(
                dict(
                    path="model/geography_evidence.json.gz",
                    format="geography-evidence-base64-v1",
                    decoding="Each array item maps original_path to artifact_path and contains exact source bytes in content_base64; verify sha256 after decoding. Native GeoNames rows and archive hashes are retained in the audits.",
                )
                if geography["evidence_bundle"]
                else None
            ),
            source_revision_status="DANIEL_EXACT_REVISION_UNKNOWN",
            llm_invoked=False,
            agent_code_sha256=acceptance["agent_code_sha256"],
        ),
    )
    provenance = output / "provenance"
    provenance.mkdir()
    for folder_name, names in [
        ("page_acquisition", ["page_sources.json.gz", "manifest.json"]),
        (
            "page_link_metadata",
            [
                "title_mapping.json.gz",
                "native_metadata.json",
                "native_evidence.json",
                "manifest.json",
            ],
        ),
    ]:
        source_dir = prepared.parent / folder_name
        target_dir = provenance / folder_name
        target_dir.mkdir()
        for name in names:
            os.link(source_dir / name, target_dir / name)

    def raw_pages():
        for page in read_json(
            prepared.parent / "page_acquisition/page_sources.json.gz"
        ):
            path = Path(page["raw_path"])
            if digest(path) != page["raw_sha256"]:
                raise ValueError("Source revision raw evidence changed")
            yield dict(
                page_index=page["page_index"],
                revision_id=page["revision_id"],
                raw_sha256=page["raw_sha256"],
                raw_wikitext=path.read_text(encoding="utf-8"),
            )

    write_array(provenance / "raw_page_revisions.json.gz", raw_pages())
    write_object(
        provenance / "event_recognition_rule.json",
        [
            dict(
                path=r["path"],
                sha256=r["sha256"],
                content=Path(r["path"]).read_text(encoding="utf-8"),
            )
            for r in read_json(model / "manifest.json")["event_rule"]
        ],
    )
    result = dict(
        stage=(
            "ENRICHED_RELEASE"
            if geography["status"].startswith("COMPLETE")
            else "CORE_RELEASE_GEOGRAPHY_PENDING"
        ),
        population_verification=population,
        graph_node_verification=graph_nodes,
        raw_verification=raw_report,
        agent_graph="agent/agent_graph.json.gz",
        relation_count=count,
        directed_view_count=2 * count,
        geography_status=geography["status"],
        geography_verification=geography,
        relation_rule="shared_page_count / distinct_pages_containing_source",
        exclusions=[
            "DATE entities",
            "entity identity matching",
            "factual native relations",
        ],
        outputs={
            p.relative_to(output).as_posix(): digest(p)
            for p in output.rglob("*")
            if p.is_file()
        },
    )
    write_object(output / "manifest.json", result)
    return result


def verify_raw_rows(prepared: Path):
    manifest = read_json(prepared / "manifest.json")
    for name in ["entities.json.gz", "wiki_pages.json.gz", "mentions.json.gz"]:
        if digest(prepared / name) != manifest["outputs"][name]:
            raise ValueError(f"Changed artifact: {name}")
    source = Path(manifest["input"]["path"])
    if digest(source) != manifest["input"]["sha256"]:
        raise ValueError("Pinned input hash changed")
    entities = read_json(prepared / "entities.json.gz")
    by_key = {(r["name"], r["type"]): r for r in entities}
    if len(by_key) != len(entities) or any(
        k[1] == "DATE" or entity_id(*k) != r["entity_id"] for k, r in by_key.items()
    ):
        raise ValueError("Invalid exact identity population")
    pages = {
        r["source_key"]: r["page_index"]
        for r in read_json(prepared / "wiki_pages.json.gz")
    }
    appearances = defaultdict(set)
    mentions = Counter()
    parquet = pq.ParquetFile(source)
    originals = (
        r for batch in parquet.iter_batches(batch_size=8192) for r in batch.to_pylist()
    )
    total = dates = 0
    with gzip.open(prepared / "mentions.json.gz", "rb") as stream:
        for index, (raw, saved) in enumerate(
            zip_longest(originals, ijson.items(stream, "item", use_float=True))
        ):
            if (
                raw is None
                or saved is None
                or saved["raw"] != raw
                or saved["source_row_index"] != index
                or saved["mention_id"] != f"mention:{index}"
                or saved["page_index"] != pages[raw["Source"]]
            ):
                raise ValueError(f"Raw row differs at {index}")
            excluded = raw["entity_group"] == "DATE"
            key = (raw["word"], raw["entity_group"])
            expected = None if excluded else by_key[key]["entity_id"]
            if saved["entity_id"] != expected or saved["exclusion_reason"] != (
                "DATE_EXCLUDED" if excluded else None
            ):
                raise ValueError(f"Identity/exclusion differs at {index}")
            dates += int(excluded)
            total += 1
            if not excluded:
                mentions[key] += 1
                appearances[key].add(pages[raw["Source"]])
            if total % 262144 == 0:
                LOG.info(
                    "Independently verified raw rows %s/%s",
                    total,
                    parquet.metadata.num_rows,
                )
    if (
        total != parquet.metadata.num_rows
        or dates != manifest["counts"]["excluded_date_rows"]
        or set(mentions) != set(by_key)
    ):
        raise ValueError("Raw population accounting failed")
    for key, row in by_key.items():
        if (
            row["page_count"] != len(appearances[key])
            or row["mention_count"] != mentions[key]
        ):
            raise ValueError("Entity count differs from original rows")
    if digest(source) != manifest["input"]["sha256"]:
        raise ValueError("Input changed during verification")
    return dict(
        status="PASS",
        raw_rows_verified=total,
        date_rows_verified=dates,
        exact_entities_verified=len(entities),
        distinct_memberships_verified=sum(map(len, appearances.values())),
        input_sha256=manifest["input"]["sha256"],
        prepared_manifest_sha256=digest(prepared / "manifest.json"),
    )


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--release", type=Path)
    args = parser.parse_args()
    if args.report and args.report.exists():
        raise FileExistsError(args.report)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if args.release:
        if args.model is None or args.graph is None:
            parser.error("--release requires --model and --graph")
        result = verify_and_package(args.prepared, args.model, args.graph, args.release)
    else:
        if args.report is None:
            parser.error("Raw replay requires --report")
        result = verify_raw_rows(args.prepared)
        write_object(args.report, result)
    LOG.info("Finished: %s", result)


if __name__ == "__main__":
    main()
