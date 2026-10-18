"""One offline, all-type run of the notebook's fixed unsupervised method.

Reuses the verified first run's page pools and saved names. Rebuilds the full
directed graph, generates candidates for every type, then ranks each paragraph.
With --page-map, rebuilds page pools using the saved Wikipedia identities and
the same frozen graph and Wikidata snapshot. No live data is fetched.
With --wide-search, trial the full saved name index and apply name/type
eligibility before constructing the paragraph graph. Default rules stay fixed.
With --metadata-supplement, require verified coverage of every mapped graph ID
and add the completed reference without changing matching rules.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import logging
import platform
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd
from complete_graph_reference import ids_hash
from generate_candidates import (
    MAP_VERSION,
    NameIndex,
    load_metadata,
    mention_id,
    normalize,
    similarity,
    write_json,
    write_line,
)
from notebook_rules import decide, hits_steps
from prepare_examples import (
    COMMIT,
    ROOT,
    exclusion_reason,
    load_exclusions,
    original_endpoints,
    sha256,
)

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "runs/first_candidates_v0.1.0_20261018"
PARAMETERS = {
    "method": "notebook-trigrams-hits-all-types-v0.1.0",
    "entity_groups": ["PER", "LOC", "ORG", "MISC", "DATE"],
    "min_name_similarity": 0.35,
    "graph_depth": 1,
    "hits_steps": 20,
    "min_accept_name": 0.80,
    "min_authority_gap": 0.20,
    "mapping_version": MAP_VERSION,
    "candidate_scope": "page plus direct incoming/outgoing neighbours",
    "ranking_scope": "all candidates in the paragraph plus page; outgoing depth 1",
    "PER_type_policy": "explicit saved P31=Q5, unchanged from notebook",
    "other_type_policy": "assume compatible; no type classifier",
    "DATE_policy": "same name/graph rules; no date parser or inferred date IDs",
    "candidate_cap": None,
    "name_language": "en",
    "manual_overrides": 0,
    "training_labels": 0,
    "model_calls": 0,
    "live_lookups": 0,
    "unknown_entity_creation": False,
    "threshold_tuning": False,
}
LOG = logging.getLogger(__name__)


def read_lines(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def build_graph(assertions: Path, mapping_path: Path, output: Path):
    """Replay mapped assertions once; preserve every record, deduplicate HITS pairs."""
    with mapping_path.open(encoding="utf-8-sig", newline="") as stream:
        rules = {}
        for row in csv.DictReader(stream):
            key = row["source"], row["source_predicate"]
            if key in rules or row["relation_map_version"] != MAP_VERSION:
                raise ValueError("Unexpected mapping key/version")
            rules[key] = row
    exclusions = load_exclusions()
    graph = nx.DiGraph()
    counts = Counter()
    with assertions.open(encoding="utf-8-sig", newline="") as source, gzip.open(
        output, "wt", encoding="utf-8", compresslevel=1
    ) as target:
        for row in csv.DictReader(source):
            counts["input_assertions"] += 1
            a, b = original_endpoints(row)
            selected = row["selected_source"]
            predicate = row["selected_source_predicate"]
            if exclusion_reason(
                selected,
                dict(
                    source_record_id=row["source_record_id"],
                    predicate=predicate,
                    subject_qid=a,
                    object_qid=b,
                ),
                exclusions,
            ):
                counts["excluded_assertions"] += 1
                continue
            rule = rules[selected, predicate]
            direction = rule["direction_to_level2"]
            if direction not in {"same", "reverse"}:
                raise ValueError("Unexpected mapping direction")
            x, y = (b, a) if direction == "reverse" else (a, b)
            graph.add_edge(x, y)
            write_line(
                target,
                dict(
                    subject=x,
                    object=y,
                    relation=rule["level2_relation_id"],
                    source=selected,
                    source_predicate=predicate,
                    source_record_id=row["source_record_id"],
                    observation_id=row["observation_id"],
                    original_subject=a,
                    original_object=b,
                    mapping_direction=direction,
                    assertion_qa_required=rule["assertion_qa_required"],
                ),
            )
            counts["mapped_assertions"] += 1
    counts["directed_pairs"] = graph.number_of_edges()
    return graph, dict(counts)


def context_graph(known: nx.DiGraph, seeds: set[str]) -> nx.DiGraph:
    reached = seeds | {
        target for q in sorted(seeds) if q in known for target in known.successors(q)
    }
    # Same one-step induced graph as the notebook; sorted order makes replay stable.
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(reached))
    graph.add_edges_from(sorted(known.subgraph(reached).edges()))
    return graph


def select(candidates: list[dict[str, Any]], *, eligible_first: bool = False) -> dict:
    if eligible_first:
        candidates = [
            c
            for c in candidates
            if c["name_similarity"] >= PARAMETERS["min_accept_name"]
        ]
    options = pd.DataFrame(
        [
            {
                "qid": c["entity_id"],
                "name_similarity": c["name_similarity"],
                "authority": c["authority"],
            }
            for c in candidates
        ]
    )
    result = decide(
        options, PARAMETERS["min_accept_name"], PARAMETERS["min_authority_gap"]
    )
    if eligible_first and not candidates:
        result["reason"] = "no eligible name/type candidate in saved reference"
    return result


def pages_from_map(rows: list[dict], graph: nx.DiGraph) -> dict[str, dict]:
    """Use confirmed page IDs with the unchanged direct-neighbour pool rule."""
    pages = {}
    for row in rows:
        title, qid = row["Source"], row["page_qid"]
        if title in pages:
            raise ValueError(f"Duplicate source in page map: {title}")
        if (row["status"] == "RESOLVED") != bool(qid):
            raise ValueError(f"Inconsistent page-map status: {title}")
        if qid and (
            not re.fullmatch(r"Q[1-9][0-9]*", qid)
            or not isinstance(row.get("wikipedia_page_id"), int)
            or row["wikipedia_page_id"] <= 0
        ):
            raise ValueError(f"Invalid page identity: {title}")
        pool = {qid} if qid else set()
        if qid in graph:
            pool.update(graph.predecessors(qid))
            pool.update(graph.successors(qid))
        pages[title] = {
            "Source": title,
            "page_qid": qid,
            "page_status": row["status"],
            "resolution_evidence": row,
            "pool": [
                {"entity_id": q, "context_id": f"{qid}|{q}", "page_identity": q == qid}
                for q in sorted(pool)
            ],
        }
    return pages


def load_supplement(path: Path, inputs: dict[str, str]) -> tuple[dict, dict]:
    manifest_path = path.parent / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "COMPLETED" or not manifest.get("coverage_verified"):
        raise ValueError("Graph reference supplement is incomplete")
    if path.name != "entity_metadata.jsonl.gz":
        raise ValueError("Expected verified supplement entity_metadata.jsonl.gz")
    for name, info in manifest["outputs"].items():
        if sha256(path.parent / name) != info["sha256"]:
            raise ValueError(f"Changed reference supplement output: {name}")
    for name, expected in manifest["inputs_sha256"].items():
        if sha256(ROOT / name) != expected:
            raise ValueError(f"Changed reference supplement input: {name}")
        inputs[name] = expected
    for item in (path, manifest_path):
        inputs[item.relative_to(ROOT).as_posix()] = sha256(item)
    rows = list(read_lines(path))
    records = {r["entity_id"]: r for r in rows}
    if len(records) != len(rows):
        raise ValueError("Duplicate reference supplement ID")
    return records, manifest


def merge_graph_reference(
    metadata: dict, supplement: dict, graph_ids: set[str], expected_ids_hash: str
) -> dict:
    if ids_hash(graph_ids) != expected_ids_hash or not supplement.keys() <= graph_ids:
        raise ValueError("Reference supplement belongs to a different graph")
    for qid, row in supplement.items():
        if metadata.get(qid, {}).get("label"):
            raise ValueError(f"Supplement would replace a frozen named entity: {qid}")
        if row.get("metadata_status") not in {
            "AVAILABLE",
            "NO_ENGLISH_NAME",
            "MISSING",
        }:
            raise ValueError(f"Unaccounted reference status: {qid}")
    merged = {**metadata, **supplement}
    if not graph_ids <= merged.keys():
        raise ValueError("Graph reference coverage is incomplete")
    return merged


def run(
    output: Path,
    page_map: Path | None = None,
    *,
    wide_search: bool = False,
    metadata_supplement: Path | None = None,
) -> None:
    if wide_search and page_map is None:
        raise ValueError("Wide search requires the verified source-page map")
    if metadata_supplement is not None and not wide_search:
        raise ValueError("Graph reference supplement requires wide search")
    baseline_manifest = json.loads((BASELINE / "run_manifest.json").read_text())
    if baseline_manifest["status"] != "COMPLETED":
        raise ValueError("The page/name cache is incomplete")
    LOG.info("Verifying the frozen page/name cache and all original inputs")
    for name, info in baseline_manifest["outputs"].items():
        if sha256(BASELINE / name) != info["sha256"]:
            raise ValueError(f"Changed baseline output: {name}")
    for name, expected in baseline_manifest["inputs_sha256"].items():
        if sha256(ROOT / name) != expected:
            raise ValueError(f"Changed baseline input: {name}")
    inputs = {
        **baseline_manifest["inputs_sha256"],
        **{
            (BASELINE / n).relative_to(ROOT).as_posix(): sha256(BASELINE / n)
            for n in [
                "run_manifest.json",
                "page_context.jsonl.gz",
                "entity_metadata.jsonl.gz",
            ]
        },
        **{
            (HERE / n).relative_to(ROOT).as_posix(): sha256(HERE / n)
            for n in [
                "run_notebook_matching.py",
                "notebook_rules.py",
                "ENTITY_MATCHING_STEP_BY_STEP.ipynb",
            ]
        },
    }
    parameters = dict(PARAMETERS)
    if wide_search:
        parameters.update(
            method="global-trigrams-eligible-first-hits-v0.2.0",
            candidate_scope="all English names in the same saved Wikidata snapshot",
            min_name_similarity=PARAMETERS["min_accept_name"],
            eligibility_before_graph=True,
            page_identity_required_for_matching=False,
            ranking_scope="eligible paragraph candidates plus optional page; outgoing depth 1",
        )
    mapped_pages = None
    if page_map is not None:
        page_map = page_map.resolve()
        manifest_path = page_map.parent / "run_manifest.json"
        lookup_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if lookup_manifest["status"] != "COMPLETED":
            raise ValueError("Source-page lookup is incomplete")
        if page_map.name != "page_map.json":
            raise ValueError("Expected the verified page_map.json output")
        for name, expected in lookup_manifest["outputs_sha256"].items():
            path = page_map.parent / name
            if sha256(path) != expected:
                raise ValueError(f"Changed page-lookup output: {name}")
            inputs[path.relative_to(ROOT).as_posix()] = expected
        for name, expected in lookup_manifest["inputs_sha256"].items():
            if sha256(ROOT / name) != expected:
                raise ValueError(f"Changed page-lookup input: {name}")
            inputs[Path(name).as_posix()] = expected
        inputs[manifest_path.relative_to(ROOT).as_posix()] = sha256(manifest_path)
        mapped_pages = json.loads(page_map.read_text(encoding="utf-8"))
        parameters["page_identity_source"] = page_map.relative_to(ROOT).as_posix()
        parameters["metadata_source"] = "same frozen full Wikidata snapshot"
    supplement, supplement_manifest = {}, None
    if metadata_supplement is not None:
        metadata_supplement = metadata_supplement.resolve()
        supplement, supplement_manifest = load_supplement(metadata_supplement, inputs)
        parameters.update(
            candidate_scope="frozen English names plus completed mapped graph reference",
            metadata_source=metadata_supplement.relative_to(ROOT).as_posix(),
            graph_reference_coverage_required=True,
        )
    compression_level = 6 if supplement_manifest is not None else 1
    run_id = (
        "matching-"
        + hashlib.sha256(
            json.dumps([inputs, parameters], sort_keys=True).encode()
        ).hexdigest()[:20]
    )
    frame = pd.read_parquet(ROOT / "Data/external/daniel_20261017.parquet")
    if frame.isna().any().any() or set(frame.entity_group) != set(
        PARAMETERS["entity_groups"]
    ):
        raise ValueError("Unexpected missing fields or extraction groups")
    pages = {p["Source"]: p for p in read_lines(BASELINE / "page_context.jsonl.gz")}
    metadata = {
        e["entity_id"]: e for e in read_lines(BASELINE / "entity_metadata.jsonl.gz")
    }
    if set(pages) != set(frame.Source):
        raise ValueError("Page cache does not cover all input titles")
    graph, graph_counts = build_graph(
        ROOT
        / "GG_Data/mapping/outputs/relation-map-v1.0.0/complete_mapped_relations_v1.0.0.csv",
        ROOT / "GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.0.csv",
        output / "mapped_graph.jsonl.gz",
    )
    LOG.info("Graph loaded: %s", graph_counts)
    if mapped_pages is not None:
        rebuilt = pages_from_map(mapped_pages, graph)
        if set(rebuilt) != set(frame.Source):
            raise ValueError("Source-page map does not cover exactly Daniel's titles")
        for title, old in pages.items():
            if old["page_status"] == "RESOLVED" and (
                rebuilt[title]["page_qid"] != old["page_qid"]
                or {e["entity_id"] for e in rebuilt[title]["pool"]}
                != {e["entity_id"] for e in old["pool"]}
            ):
                raise ValueError(
                    f"Previously resolved page identity/pool changed: {title}"
                )
        pages = rebuilt
        metadata, _ = load_metadata(
            ROOT / "Data/external/wwii_task_force/wikidata_entities.jsonl.gz", set()
        )
        for entity in read_lines(BASELINE / "entity_metadata.jsonl.gz"):
            qid = entity["entity_id"]
            for field in ("label", "aliases", "direct_types"):
                if entity.get(field) != metadata.get(qid, {}).get(field):
                    raise ValueError(f"Previously cached metadata changed: {qid}")
        if supplement_manifest is not None:
            metadata = merge_graph_reference(
                metadata,
                supplement,
                set(graph),
                supplement_manifest["graph_entity_ids_sha256"],
            )
            LOG.info("Verified reference coverage for all %d graph IDs", len(graph))
        with gzip.open(
            output / "page_context.jsonl.gz", "wt", encoding="utf-8"
        ) as stream:
            for page in pages.values():
                write_line(stream, {"run_id": run_id, **page})
        pool_ids = {e["entity_id"] for p in pages.values() for e in p["pool"]}
        saved_ids = pool_ids | metadata.keys() if wide_search else pool_ids
        with gzip.open(
            output / "entity_metadata.jsonl.gz", "wt", encoding="utf-8"
        ) as stream:
            for qid in sorted(saved_ids):
                write_line(
                    stream,
                    metadata.get(qid, {"entity_id": qid, "metadata_status": "MISSING"}),
                )
        LOG.info(
            "Rebuilt pools for %d resolved pages; %d pool IDs; %d without metadata",
            sum(p["page_status"] == "RESOLVED" for p in pages.values()),
            len(pool_ids),
            len(pool_ids - metadata.keys()),
        )
    counters, reasons = defaultdict(Counter), defaultdict(Counter)
    global_index = NameIndex(list(metadata), metadata) if wide_search else None
    global_name_cache = {}
    seen_ids, seen_rows = set(), set()
    pair_count = paragraph_count = graph_count = 0
    page_summaries = []
    # Compress supplemented runs more strongly to limit their extra disk use.
    with gzip.open(
        output / "mention_matches.jsonl.gz",
        "wt",
        encoding="utf-8",
        compresslevel=compression_level,
    ) as matches, gzip.open(
        output / "graph_contexts.jsonl.gz",
        "wt",
        encoding="utf-8",
        compresslevel=compression_level,
    ) as contexts:
        for number, (title, page_frame) in enumerate(
            frame.groupby("Source", sort=True), 1
        ):
            page = pages[title]
            pool = [e["entity_id"] for e in page["pool"]]
            pool_ids = set(pool)
            index = global_index if wide_search else NameIndex(pool, metadata)
            name_cache = global_name_cache if wide_search else {}
            graph_cache = {}
            page_counts = Counter()
            for paragraph_index, paragraph in page_frame.groupby("Index", sort=True):
                paragraph_count += 1
                rows, seeds = [], {page["page_qid"]} if page["page_qid"] else set()
                for input_row, values in zip(
                    paragraph.index, paragraph.itertuples(index=False, name=None)
                ):
                    raw = dict(zip(frame.columns, values))
                    if not (
                        0 <= raw["start"] < raw["end"] <= len(raw["Text"])
                        and raw["Text"][raw["start"] : raw["end"]] == raw["word"]
                    ):
                        raise ValueError(f"Invalid raw span: {input_row}")
                    mid = mention_id(raw)
                    if mid in seen_ids:
                        raise ValueError(f"Repeated mention identity: {input_row}")
                    seen_ids.add(mid)
                    seen_rows.add(int(input_row))
                    key = raw["entity_group"], normalize(raw["word"])
                    if key not in name_cache:
                        found = index.find(
                            raw["word"],
                            raw["entity_group"],
                            parameters["min_name_similarity"],
                        )
                        name_cache[key] = [
                            {
                                **c,
                                "type_check": (
                                    "EXPLICIT_HUMAN_Q5"
                                    if raw["entity_group"] == "PER"
                                    else "ASSUMED_COMPATIBLE"
                                ),
                            }
                            for c in found
                        ]
                    candidates = name_cache[key]
                    seeds.update(c["entity_id"] for c in candidates)
                    rows.append((int(input_row), mid, raw, candidates))
                context_id, authority = None, {}
                if seeds:
                    key = tuple(sorted(seeds))
                    if key not in graph_cache:
                        local = context_graph(graph, seeds)
                        scores = hits_steps(
                            local, PARAMETERS["hits_steps"], keep_history=False
                        )
                        authority = scores.set_index("qid").authority.to_dict()
                        context_id = (
                            "context-"
                            + hashlib.sha256(
                                json.dumps([run_id, title, key]).encode()
                            ).hexdigest()[:24]
                        )
                        write_line(
                            contexts,
                            dict(
                                run_id=run_id,
                                context_id=context_id,
                                Source=title,
                                seeds=list(key),
                                nodes=len(local),
                                directed_pairs=local.number_of_edges(),
                                graph_sha256=hashlib.sha256(
                                    json.dumps(
                                        [sorted(local), sorted(local.edges())]
                                    ).encode()
                                ).hexdigest(),
                                seed_scores=scores[scores.qid.isin(seeds)].to_dict(
                                    "records"
                                ),
                            ),
                        )
                        graph_cache[key] = context_id, authority
                        graph_count += 1
                    context_id, authority = graph_cache[key]
                decisions = {}
                for input_row, mid, raw, found in rows:
                    candidates = sorted(
                        [
                            {
                                **c,
                                "authority": authority.get(c["entity_id"], 0.0),
                                "page_context_id": (
                                    f"{page['page_qid']}|{c['entity_id']}"
                                    if c["entity_id"] in pool_ids
                                    else None
                                ),
                                **(
                                    {"in_page_pool": c["entity_id"] in pool_ids}
                                    if wide_search
                                    else {}
                                ),
                            }
                            for c in found
                        ],
                        key=lambda c: (
                            -c["authority"],
                            -c["name_similarity"],
                            c["entity_id"],
                        ),
                    )
                    decision_key = raw["entity_group"], normalize(raw["word"])
                    if decision_key not in decisions:
                        decisions[decision_key] = select(
                            candidates, eligible_first=wide_search
                        )
                    decision = dict(decisions[decision_key])
                    if not wide_search and page["page_status"] != "RESOLVED":
                        decision["reason"] = "page_" + page["page_status"].lower()
                    proposed = decision["suggested_qid"]
                    write_line(
                        matches,
                        dict(
                            run_id=run_id,
                            input_row_number=input_row,
                            mention_id=mid,
                            raw=raw,
                            page_qid=page["page_qid"],
                            page_status=page["page_status"],
                            graph_context_id=context_id,
                            type_policy=(
                                "EXPLICIT_HUMAN_Q5"
                                if raw["entity_group"] == "PER"
                                else "ASSUMED_COMPATIBLE"
                            ),
                            candidate_count=len(candidates),
                            candidates=candidates,
                            **decision,
                            suggested_label=(
                                metadata[proposed].get("label") if proposed else None
                            ),
                        ),
                    )
                    counters[raw["entity_group"]][decision["decision"]] += 1
                    reasons[raw["entity_group"]][decision["reason"]] += 1
                    page_counts[decision["decision"]] += 1
                    pair_count += len(candidates)
            page_summaries.append(
                dict(
                    Source=title,
                    page_status=page["page_status"],
                    page_qid=page["page_qid"],
                    input_mentions=len(page_frame),
                    pool_entities=len(pool),
                    pool_entities_with_names=sum(
                        bool(
                            metadata.get(q, {}).get("label")
                            or metadata.get(q, {}).get("aliases")
                        )
                        for q in pool
                    ),
                    decisions=dict(page_counts),
                )
            )
            if number % 10 == 0 or number == len(pages):
                LOG.info(
                    "Pages %d/%d; mentions %d; paragraphs %d; HITS contexts %d",
                    number,
                    len(pages),
                    len(seen_ids),
                    paragraph_count,
                    graph_count,
                )
    if seen_rows != set(range(len(frame))) or len(seen_ids) != len(frame):
        raise ValueError("Not all raw rows were processed")
    LOG.info(
        "Verifying every saved match against raw data, names, graph scores and rules"
    )
    context_scores = {
        c["context_id"]: {s["qid"]: s["authority"] for s in c["seed_scores"]}
        for c in read_lines(output / "graph_contexts.jsonl.gz")
    }
    verified_ids, verified_counts = set(), defaultdict(Counter)
    verified_rows, verified_pairs = set(), 0
    for record in read_lines(output / "mention_matches.jsonl.gz"):
        raw, mid = record["raw"], record["mention_id"]
        input_row = record["input_row_number"]
        if (
            raw != frame.iloc[input_row].to_dict()
            or mid != mention_id(raw)
            or mid in verified_ids
        ):
            raise ValueError("Written raw row or identity mismatch")
        verified_ids.add(mid)
        verified_rows.add(input_row)
        found = record["candidates"]
        qids = [c["entity_id"] for c in found]
        if len(qids) != len(set(qids)) or len(qids) != record["candidate_count"]:
            raise ValueError("Written candidate count mismatch")
        pool_ids = {c["entity_id"] for c in pages[raw["Source"]]["pool"]}
        for c in found:
            entity = metadata[c["entity_id"]]
            if (
                (not wide_search and c["entity_id"] not in pool_ids)
                or c["matched_name"]
                not in [entity.get("label", "")] + entity.get("aliases", [])
                or c["name_similarity"] != similarity(raw["word"], c["matched_name"])
                or c["name_similarity"] < parameters["min_name_similarity"]
                or c["authority"]
                != context_scores[record["graph_context_id"]][c["entity_id"]]
                or (
                    raw["entity_group"] == "PER"
                    and "Q5" not in entity.get("direct_types", [])
                )
            ):
                raise ValueError("Written name, type, page or graph score mismatch")
            if wide_search and (
                c["in_page_pool"] != (c["entity_id"] in pool_ids)
                or c["page_context_id"]
                != (
                    f"{record['page_qid']}|{c['entity_id']}"
                    if c["entity_id"] in pool_ids
                    else None
                )
            ):
                raise ValueError("Written page-context membership mismatch")
        expected = select(found, eligible_first=wide_search)
        if not wide_search and record["page_status"] != "RESOLVED":
            expected["reason"] = "page_" + record["page_status"].lower()
        if any(record[k] != v for k, v in expected.items()):
            raise ValueError("Written automatic decision differs from notebook rule")
        verified_counts[raw["entity_group"]][record["decision"]] += 1
        verified_pairs += len(found)
    if (
        verified_ids != seen_ids
        or verified_rows != seen_rows
        or verified_pairs != pair_count
        or dict(verified_counts) != dict(counters)
    ):
        raise ValueError("Written totals do not reconcile")
    for name, expected in inputs.items():
        if sha256(ROOT / name) != expected:
            raise ValueError(f"Input changed during matching: {name}")
    summary = dict(
        run_id=run_id,
        input_mentions=len(frame),
        output_mentions=len(seen_ids),
        pages=len(pages),
        paragraphs=paragraph_count,
        unique_hits_contexts=graph_count,
        page_statuses=dict(Counter(p["page_status"] for p in pages.values())),
        candidate_pairs=pair_count,
        by_entity_group={
            g: dict(
                total_mentions=sum(c.values()),
                decisions=dict(c),
                reasons=dict(reasons[g]),
            )
            for g, c in sorted(counters.items())
        },
        decisions=dict(sum(counters.values(), Counter())),
        graph_assertions=graph_counts,
        pages_detail=page_summaries,
        accuracy_measured=False,
        type_compatibility_validated=False,
        manually_selected_matches=0,
        new_entities_created=0,
        reference_coverage=dict(
            graph_ids=len(graph),
            graph_ids_with_metadata=sum(
                q in metadata and metadata[q].get("metadata_status") != "MISSING"
                for q in graph
            ),
            graph_ids_with_english_names=sum(
                bool(
                    metadata.get(q, {}).get("label")
                    or metadata.get(q, {}).get("aliases")
                )
                for q in graph
            ),
            graph_ids_without_reference_record=sorted(set(graph) - metadata.keys()),
            supplement_used=supplement_manifest is not None,
        ),
    )
    write_json(output / "summary.json", summary)
    write_json(
        output / "run_manifest.json",
        dict(
            status="COMPLETED",
            run_id=run_id,
            completed_utc=datetime.now(timezone.utc).isoformat(),
            parameters=parameters,
            inputs_sha256=inputs,
            baseline_run_id=baseline_manifest["run_id"],
            daniel_commit=COMMIT,
            outputs={
                p.name: dict(sha256=sha256(p), bytes=p.stat().st_size)
                for p in sorted(output.iterdir())
                if p.is_file()
            },
            runtime=dict(
                python=platform.python_version(),
                pandas=pd.__version__,
                networkx=nx.__version__,
            ),
            verification=dict(
                all_raw_rows_preserved=True,
                all_five_types_processed=True,
                all_candidates_and_decisions_rechecked=True,
                inputs_unchanged_during_run=True,
            ),
        ),
    )
    LOG.info("COMPLETED: %s", json.dumps(summary["decisions"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--metadata-supplement",
        type=Path,
        help="Verified completed graph reference entity_metadata.jsonl.gz",
    )
    parser.add_argument(
        "--page-map", type=Path, help="Verified source-page lookup page_map.json"
    )
    parser.add_argument(
        "--wide-search",
        action="store_true",
        help="Separate trial: search the full saved name index; filter before HITS",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    run(
        output,
        args.page_map,
        wide_search=args.wide_search,
        metadata_supplement=args.metadata_supplement,
    )


if __name__ == "__main__":
    main()
