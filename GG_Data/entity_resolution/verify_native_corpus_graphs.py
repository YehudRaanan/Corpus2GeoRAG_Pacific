"""Independently verify every edge with packed page-set intersections."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from attach_source_page_ids import save_json, sha256
from native_corpus_graphs import INPUT, INPUT_HASH, OUTPUT

LOG = logging.getLogger(__name__)


def verify_graph(path: Path) -> dict:
    nodes = pd.read_parquet(path / "nodes.parquet")
    pages = pd.read_parquet(path / "node_page_presence.parquet")
    revisions = pd.read_parquet(path / "node_revision_presence.parquet")
    summary = json.loads((path / "summary.json").read_text("utf-8"))
    if nodes.duplicated(["name", "type"]).any():
        raise ValueError("Duplicate exact name/type nodes")
    if pages.duplicated(["node_id", "wiki_page_id"]).any():
        raise ValueError("Duplicate entity/page membership")
    if revisions.duplicated().any():
        raise ValueError("Duplicate revision membership")
    pd.testing.assert_frame_equal(
        pages.sort_values(["node_id", "wiki_page_id"]).reset_index(drop=True),
        revisions[["node_id", "wiki_page_id"]]
        .drop_duplicates()
        .sort_values(["node_id", "wiki_page_id"])
        .reset_index(drop=True),
        check_dtype=False,
    )
    if nodes.node_id.tolist() != list(range(len(nodes))):
        raise ValueError("Nonsequential node IDs")
    unique_pages, page_index = np.unique(pages.wiki_page_id, return_inverse=True)
    words = (len(unique_pages) + 63) // 64
    packed = np.zeros((len(nodes), words), dtype=np.uint64)
    np.bitwise_or.at(
        packed,
        (pages.node_id.to_numpy(), page_index // 64),
        np.left_shift(np.uint64(1), (page_index % 64).astype(np.uint64)),
    )
    actual_counts = np.bitwise_count(packed).sum(axis=1)
    if not np.array_equal(actual_counts, nodes.page_count.to_numpy()):
        raise ValueError("Node page counts differ")
    total_edges = total_weight = max_weight = 0
    previous_source = -1
    for i, part in enumerate(sorted((path / "edges").glob("*.parquet"))):
        table = pq.read_table(part)
        source = table["source"].to_numpy()
        target = table["target"].to_numpy()
        weight = table["weight"].to_numpy()
        if not len(source):
            continue
        if source.min() <= previous_source:
            raise ValueError(f"Overlapping source partitions: {part}")
        previous_source = int(source.max())
        if (
            (source < 0).any()
            or (target >= len(nodes)).any()
            or not (source < target).all()
        ):
            raise ValueError(f"Invalid undirected endpoints: {part}")
        keys = source.astype(np.uint64) * np.uint64(len(nodes)) + target
        if len(np.unique(keys)) != len(keys):
            raise ValueError(f"Duplicate edges: {part}")
        for offset in range(0, len(source), 100000):
            sl = slice(offset, offset + 100000)
            expected = np.bitwise_count(packed[source[sl]] & packed[target[sl]]).sum(
                axis=1
            )
            if not np.array_equal(expected, weight[sl]):
                raise ValueError(
                    f"Edge weight differs from independent page intersection: {part}"
                )
        total_edges += len(weight)
        total_weight += int(weight.sum(dtype=np.int64))
        max_weight = max(max_weight, int(weight.max()))
        if i % 25 == 0:
            LOG.info(
                "Verified %s: %s edge partitions, %s edges",
                path.name,
                i + 1,
                total_edges,
            )
    counts = pages.groupby("wiki_page_id").size().to_numpy(dtype=np.int64)
    expected_sum = int((counts * (counts - 1) // 2).sum())
    if (
        total_weight != expected_sum
        or total_weight != summary["weight_sum"]
        or total_edges != summary["edges"]
    ):
        raise ValueError("Graph denominator differs")
    return {
        "nodes": len(nodes),
        "node_page_pairs": len(pages),
        "node_revision_pairs": len(revisions),
        "edges_verified_individually": total_edges,
        "weight_sum": total_weight,
        "max_weight": max_weight,
        "unique_edges": True,
        "every_weight_verified_by_independent_page_set_intersection": True,
    }


def verify_b(output: Path) -> dict:
    if sha256(INPUT) != INPUT_HASH:
        raise ValueError("V3 input changed")
    raw = pq.read_table(INPUT)
    unresolved = pd.read_parquet(output / "graph_b/unresolved_rows.parquet")
    expected = raw.to_pandas().loc[lambda df: df.wiki_page_id.isna()].copy()
    pd.testing.assert_frame_equal(
        unresolved.drop(columns="source_row_index").reset_index(drop=True),
        expected.reset_index(drop=True),
    )
    if (
        unresolved.source_row_index.tolist() != expected.index.tolist()
        or len(unresolved) != 545
    ):
        raise ValueError("Unresolved row identity changed")
    nodes = pd.read_parquet(output / "graph_b/nodes.parquet")
    identities = raw.select(["word", "entity_group"]).to_pandas().drop_duplicates()
    if set(map(tuple, identities.to_numpy())) != set(zip(nodes.name, nodes.type)):
        raise ValueError("Graph B identities differ from original")
    result = verify_graph(output / "graph_b")
    result.update(
        unresolved_rows_unchanged=545,
        original_v3_sha256=sha256(INPUT),
        source_page_matching_rerun=False,
    )
    save_json(output / "graph_b/verification.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("graph", choices=["a", "b"])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    result = (
        verify_b(args.output)
        if args.graph == "b"
        else verify_graph(args.output / "graph_a")
    )
    if args.graph == "a":
        save_json(args.output / "graph_a/verification.json", result)
    LOG.info("Verified: %s", json.dumps(result))


if __name__ == "__main__":
    main()
