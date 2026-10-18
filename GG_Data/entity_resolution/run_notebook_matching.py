"""One offline, all-type run of the notebook's fixed unsupervised method.

Reuses the verified first run's page pools and saved names. Rebuilds the full
directed graph, generates candidates for every type, then ranks each paragraph.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import logging
import platform
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd
from generate_candidates import (
    MAP_VERSION,
    NameIndex,
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


def select(candidates: list[dict[str, Any]]) -> dict:
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
    return decide(
        options, PARAMETERS["min_accept_name"], PARAMETERS["min_authority_gap"]
    )


def run(output: Path) -> None:
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
    run_id = (
        "matching-"
        + hashlib.sha256(
            json.dumps([inputs, PARAMETERS], sort_keys=True).encode()
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
    counters, reasons = defaultdict(Counter), defaultdict(Counter)
    seen_ids, seen_rows = set(), set()
    pair_count = paragraph_count = graph_count = 0
    page_summaries = []
    # Low gzip level keeps this one-time run fast and within the available disk space.
    with gzip.open(
        output / "mention_matches.jsonl.gz", "wt", encoding="utf-8", compresslevel=1
    ) as matches, gzip.open(
        output / "graph_contexts.jsonl.gz", "wt", encoding="utf-8", compresslevel=1
    ) as contexts:
        for number, (title, page_frame) in enumerate(
            frame.groupby("Source", sort=True), 1
        ):
            page = pages[title]
            pool = [e["entity_id"] for e in page["pool"]]
            index = NameIndex(pool, metadata)
            name_cache, graph_cache = {}, {}
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
                            PARAMETERS["min_name_similarity"],
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
                                "page_context_id": f"{page['page_qid']}|{c['entity_id']}",
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
                        decisions[decision_key] = select(candidates)
                    decision = dict(decisions[decision_key])
                    if page["page_status"] != "RESOLVED":
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
                c["entity_id"] not in pool_ids
                or c["matched_name"]
                not in [entity.get("label", "")] + entity.get("aliases", [])
                or c["name_similarity"] != similarity(raw["word"], c["matched_name"])
                or c["name_similarity"] < PARAMETERS["min_name_similarity"]
                or c["authority"]
                != context_scores[record["graph_context_id"]][c["entity_id"]]
                or (
                    raw["entity_group"] == "PER"
                    and "Q5" not in entity.get("direct_types", [])
                )
            ):
                raise ValueError("Written name, type, page or graph score mismatch")
        expected = select(found)
        if record["page_status"] != "RESOLVED":
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
    )
    write_json(output / "summary.json", summary)
    write_json(
        output / "run_manifest.json",
        dict(
            status="COMPLETED",
            run_id=run_id,
            completed_utc=datetime.now(timezone.utc).isoformat(),
            parameters=PARAMETERS,
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
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    run(output)


if __name__ == "__main__":
    main()
