"""Complete page-co-occurrence model and memory-bounded Agent JSON export."""

from __future__ import annotations

import argparse
import logging
import shutil
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from Agent.geo_agent.compact_format import COLUMNS, write_graph
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.simplified_agent import (
    entity_id,
    native_graph,
    write_array,
    write_object,
)

LOG = logging.getLogger(__name__)
TYPES = {
    "LOC": "location",
    "PER": "person",
    "ORG": "org",
    "MISC": "misc",
    "event": "event",
}


def build_graph(model: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    manifest = read_json(model / "manifest.json")
    for name, sha in manifest["outputs"].items():
        if digest(model / name) != sha:
            raise ValueError(f"Changed model input: {name}")
    entities = read_json(model / "entities.json.gz")
    if [r["node_index"] for r in entities] != list(range(len(entities))):
        raise ValueError("Non-contiguous node index")
    membership_frame = pq.read_table(model / "memberships.parquet").to_pandas()
    memberships = defaultdict(list)
    for row in membership_frame.itertuples(index=False):
        memberships[int(row.node_index)].append(int(row.page_index))
    if any(
        len(set(memberships[i])) != r["page_count"]
        or len(memberships[i]) != r["page_count"]
        for i, r in enumerate(entities)
    ):
        raise ValueError("Page denominator differs from binary memberships")
    if any(not 0 <= i < len(entities) for i in memberships):
        raise ValueError("Invalid membership endpoint")
    # Conservative bound before materializing: every per-page pair is unique.
    page_sizes = membership_frame.groupby("page_index").size()
    raw_sum = sum(int(n) * (int(n) - 1) // 2 for n in page_sizes)
    estimate = raw_sum * 200 + len(entities) * 4096
    if shutil.disk_usage(output.parent).free < estimate + 15 * 1024**3:
        raise OSError(
            f"Insufficient storage: conservative graph/index reserve {estimate} bytes"
        )
    output.mkdir()
    counts = native_graph().write_edges(
        pd.DataFrame(entities).rename(columns={"node_index": "node_id"}),
        membership_frame.rename(
            columns={"node_index": "node_id", "page_index": "wiki_page_id"}
        ),
        output / "pair_parts",
    )
    if counts["weight_sum"] != raw_sum:
        raise ValueError("Raw count conservation failed")
    page_rows = read_json(model / "wiki_pages.json.gz")
    pages = {
        r.get("canonical_page_index", r["page_index"]): r for r in reversed(page_rows)
    }
    by_source = {r["source_key"]: r for r in page_rows}
    by_id = {r["entity_id"]: r for r in entities}
    first_mentions = {}
    source = manifest.get("input")
    if source:
        input_path = Path(source["path"])
        if digest(input_path) != source["sha256"]:
            raise ValueError("Pinned Daniel input changed")
        index = 0
        for batch in pq.ParquetFile(input_path).iter_batches(
            batch_size=8192, columns=["word", "entity_group", "Text", "Source", "Index"]
        ):
            for raw in batch.to_pylist():
                if raw["entity_group"] != "DATE":
                    key = entity_id(raw["word"], raw["entity_group"])
                    if key not in by_id:
                        raise ValueError("Raw mention identity absent from graph")
                    first_mentions.setdefault(key, dict(row=index, raw=raw))
                index += 1
    events = {r["entity_id"]: r for r in read_json(model / "event_events.json.gz")}
    nodes = []
    for row in entities:
        key = row["entity_id"]
        indices = sorted(memberships[row["node_index"]])
        attrs = dict(
            entity_group=row["type"],
            page_count=row["page_count"],
            page_indices=indices,
            mention_count=row["mention_count"],
            geography_status=(
                "PENDING_LAST_STAGE" if row["type"] == "LOC" else "NOT_APPLICABLE"
            ),
        )
        sources = []
        text = ""
        if key in first_mentions:
            first = first_mentions[key]
            raw = first["raw"]
            text = raw["Text"]
            attrs.update(
                first_mention_row=first["row"],
                raw_text_scope="FIRST_ORIGINAL_MENTION_PARAGRAPH; ALL_ROWS_IN_MENTIONS_JSON",
                source_revision_status="DANIEL_EXACT_REVISION_UNKNOWN",
            )
            page = by_source[raw["Source"]]
            sources = [
                dict(
                    page=page.get("title", raw["Source"]),
                    paragraph=int(raw["Index"]),
                    url=f"https://en.wikipedia.org/?curid={page['wiki_page_id']}",
                    source_key=raw["Source"],
                )
            ]
        if key in events:
            attrs.update(
                event_detail=events[key],
                semantics="EVENT_RECOGNIZED_FROM_SOURCE_PAGE_SUBJECT_OR_DIRECT_LINK",
            )
            sources = [
                dict(
                    page=pages[i]["title"],
                    url=f"https://en.wikipedia.org/w/index.php?oldid={pages[i]['revision_id']}",
                    page_index=i,
                )
                for i in indices
            ]
        nodes.append(
            dict(
                id=key,
                name=row["name"],
                type=TYPES.get(row["type"], row["type"]),
                attributes=attrs,
                sources=sources,
                text=text,
            )
        )
    parts = sorted((output / "pair_parts").glob("*.parquet"))

    def pairs():
        for part in parts:
            for batch in pq.ParquetFile(part).iter_batches(batch_size=16384):
                for row in batch.to_pylist():
                    a, b, n = row["source"], row["target"], row["weight"]
                    yield [
                        a,
                        b,
                        n,
                        n / entities[a]["page_count"],
                        n / entities[b]["page_count"],
                    ]

    metadata = dict(
        node_count=len(nodes),
        pair_count=counts["edges"],
        directed_view_count=2 * counts["edges"],
        raw_shared_page_count_sum=raw_sum,
        page_scope_id=manifest["page_scope_id"],
        relation_type="CO_OCCURS_ON_PAGE",
        relation_semantics="PAGE_CO_OCCURRENCE_ONLY",
        denominator_unit="distinct_source_pages",
        edge_columns=COLUMNS,
        geography_status="PENDING_LAST_STAGE",
        model_manifest_sha256=digest(model / "manifest.json"),
        pages=[
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
            for r in page_rows
        ],
    )
    write_graph(output / "agent_graph.json.gz", metadata, nodes, pairs())
    write_array(output / "relations.json.gz", pairs())
    write_object(
        output / "relations_schema.json",
        dict(
            columns=COLUMNS,
            entity_index="entities.json.gz node_index",
            relation_type="CO_OCCURS_ON_PAGE",
            page_scope_id=manifest["page_scope_id"],
            denominator_unit="distinct_source_pages",
        ),
    )
    result = dict(
        metadata,
        stage="CORE_GRAPH_EXPORTED",
        model_path=str(model.resolve()),
        outputs={p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()},
    )
    write_object(output / "manifest.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    result = build_graph(args.model, args.output)
    LOG.info(
        "Finished: nodes=%s pairs=%s directed_views=%s",
        result["node_count"],
        result["pair_count"],
        result["directed_view_count"],
    )


if __name__ == "__main__":
    main()
