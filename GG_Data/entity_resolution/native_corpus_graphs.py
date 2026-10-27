"""Build exact name/type graphs without repeating extraction or page matching."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from attach_source_page_ids import WikiClient, read_json, save_json, sha256
from bs4 import BeautifulSoup
from scipy.sparse import csr_matrix

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "Data/external"
INPUT = (
    DATA
    / "source_page_versions_history_20261027/georag_selected_v2_full_n36335_r345732948_20261024_v3_historical_continuation.parquet"
)
OUTPUT = DATA / "native_corpus_graphs_20261028"
INPUT_HASH = "5378e8124979f04be6eca62a62a7f104fb2fdb88d5c0ba378ebf8d3db86f5bb7"
NAMESPACES = {
    "media",
    "special",
    "talk",
    "user",
    "user talk",
    "wikipedia",
    "wikipedia talk",
    "file",
    "file talk",
    "mediawiki",
    "mediawiki talk",
    "template",
    "template talk",
    "help",
    "help talk",
    "category",
    "category talk",
    "portal",
    "portal talk",
    "draft",
    "draft talk",
    "timedtext",
    "timedtext talk",
    "module",
    "module talk",
    "book",
    "book talk",
    "education program",
    "topic",
    "wp",
    "image",
    "wt",
}


def export_frame(frame: pd.DataFrame, path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"Preserve existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".parquet.tmp")
    pq.write_table(
        pa.Table.from_pandas(frame, preserve_index=False), temporary, compression="zstd"
    )
    temporary.replace(path)


def memberships(rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Keep exact names/types, unresolved-only nodes and binary page membership."""
    if rows[["name", "type"]].isna().any().any():
        raise ValueError("Identity needs an explicit source name and type")
    nodes = (
        rows[["name", "type"]]
        .drop_duplicates()
        .sort_values(["name", "type"])
        .reset_index(drop=True)
    )
    nodes.insert(0, "node_id", np.arange(len(nodes), dtype=np.int32))
    attached = rows.merge(nodes, on=["name", "type"], validate="many_to_one")
    pages = attached.dropna(subset=["wiki_page_id"])[
        ["node_id", "wiki_page_id"]
    ].drop_duplicates()
    pages["wiki_page_id"] = pages.wiki_page_id.astype("int64")
    pages = pages.sort_values(["node_id", "wiki_page_id"]).reset_index(drop=True)
    revisions = attached.dropna(subset=["wiki_page_id", "wiki_revision_id"])[
        ["node_id", "wiki_page_id", "wiki_revision_id"]
    ].drop_duplicates()
    revisions[["wiki_page_id", "wiki_revision_id"]] = revisions[
        ["wiki_page_id", "wiki_revision_id"]
    ].astype("int64")
    nodes["page_count"] = (
        nodes.node_id.map(pages.groupby("node_id").size()).fillna(0).astype("int32")
    )
    return nodes, pages, revisions.reset_index(drop=True)


def write_edges(
    nodes: pd.DataFrame, pages: pd.DataFrame, target: Path, block_size: int = 512
) -> dict[str, int]:
    """Compute exact counts in bounded row blocks, using installed SciPy."""
    target.mkdir(parents=True, exist_ok=True)
    if list(target.glob("*.parquet")):
        raise FileExistsError(f"Existing edges: {target}")
    page_ids, page_indices = np.unique(
        pages.wiki_page_id.to_numpy(), return_inverse=True
    )
    matrix = csr_matrix(
        (np.ones(len(pages), dtype=np.int32), (pages.node_id.to_numpy(), page_indices)),
        shape=(len(nodes), len(page_ids)),
        dtype=np.int32,
    )
    matrix.sum_duplicates()
    if len(pages) and matrix.data.max() != 1:
        raise ValueError("Duplicate entity/page membership")
    transpose = matrix.T.tocsr()
    edges = weight_sum = max_weight = 0
    for part, start in enumerate(range(0, len(nodes), block_size)):
        product = (matrix[start : start + block_size] @ transpose).tocoo()
        source = product.row + start
        keep = source < product.col
        values = product.data[keep]
        table = pa.table(
            {
                "source": pa.array(source[keep], type=pa.int32()),
                "target": pa.array(product.col[keep], type=pa.int32()),
                "weight": pa.array(values, type=pa.int32()),
            }
        )
        pq.write_table(table, target / f"part-{part:05d}.parquet", compression="zstd")
        edges += len(values)
        weight_sum += int(values.sum(dtype=np.int64))
        max_weight = max(max_weight, int(values.max(initial=0)))
        if part % 20 == 0:
            LOG.info(
                "Edges %s: %s/%s nodes; %s edges",
                target.parent.name,
                start,
                len(nodes),
                edges,
            )
    counts = pages.groupby("wiki_page_id").size().to_numpy(dtype=np.int64)
    expected = int((counts * (counts - 1) // 2).sum())
    if weight_sum != expected:
        raise ValueError(
            f"Edge weight denominator mismatch: {weight_sum} != {expected}"
        )
    return {
        "edges": edges,
        "weight_sum": weight_sum,
        "max_weight": max_weight,
        "pages": len(page_ids),
        "nodes": len(nodes),
        "node_page_pairs": len(pages),
        "nodes_without_page": int(nodes.page_count.eq(0).sum()),
    }


def project_entity(entity: dict[str, Any]) -> dict[str, Any]:
    types = set()
    for claim in entity.get("claims", {}).get("P31", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if (
            claim.get("rank") != "deprecated"
            and isinstance(value, dict)
            and value.get("id")
        ):
            types.add(value["id"])
    return {
        "id": entity.get("id"),
        "label": entity.get("labels", {}).get("en", {}).get("value", ""),
        "direct_types": sorted(types),
        "revision": entity.get("lastrevid"),
        "modified": entity.get("modified"),
        "missing": "missing" in entity,
        "sitelinks": entity.get("sitelinks", {}),
        "reference_source": "WIKIDATA_API",
    }


def article_links(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("script, style, .mw-editsection, .mw-cite-backlink"):
        node.decompose()
    result = set()
    for anchor in soup.find_all("a", href=True):
        parsed = urlsplit(anchor["href"])
        if parsed.netloc and parsed.netloc not in {
            "en.wikipedia.org",
            "www.en.wikipedia.org",
        }:
            continue
        if not parsed.path.startswith("/wiki/"):
            continue
        title = unquote(parsed.path[len("/wiki/") :]).replace("_", " ")
        if not title or title.split(":", 1)[0].lower() in NAMESPACES:
            continue
        # Interwiki prefixes are handled by the authoritative ns=0 lookup later.
        text = anchor.get_text(" ", strip=True)
        if text:
            result.add((title, text))
    return sorted(result)


def validate_parse(data: dict[str, Any], page_id: int, revision_id: int) -> None:
    if (
        data.get("pageid") != page_id
        or data.get("revid") != revision_id
        or not isinstance(data.get("text"), str)
    ):
        raise ValueError(
            f"Parse page/revision identity mismatch: {page_id}/{revision_id}"
        )


def checked_input() -> pa.Table:
    if sha256(INPUT) != INPUT_HASH:
        raise ValueError("V3 input bytes changed")
    table = pq.read_table(INPUT)
    if table.num_rows != 309864 or table["wiki_page_id"].null_count != 545:
        raise ValueError("Unexpected V3 input counts")
    return table


def build_b(output: Path) -> dict[str, Any]:
    table = checked_input()
    frame = table.to_pandas()
    rows = frame.rename(columns={"word": "name", "entity_group": "type"})
    nodes, pages, revisions = memberships(rows)
    pairs = rows.groupby(["name", "type"], sort=False)
    extras = pairs.agg(
        mention_count=("name", "size"),
        unresolved_mentions=("wiki_page_id", lambda x: int(x.isna().sum())),
        subtypes=("subtype", lambda x: sorted(set(x))),
    )
    nodes = nodes.merge(
        extras.reset_index(), on=["name", "type"], validate="one_to_one"
    )
    if len(nodes) != 74339 or len(pages) != 147548:
        raise ValueError("Graph B identity/page denominator mismatch")
    out = output / "graph_b"
    export_frame(nodes, out / "nodes.parquet")
    export_frame(pages, out / "node_page_presence.parquet")
    export_frame(revisions, out / "node_revision_presence.parquet")
    unresolved = frame.loc[frame.wiki_page_id.isna()].copy()
    unresolved.insert(0, "source_row_index", unresolved.index.to_numpy(dtype=np.int64))
    export_frame(unresolved, out / "unresolved_rows.parquet")
    inventory = frame.dropna(subset=["wiki_page_id", "wiki_revision_id"])[
        [
            "wiki_page_id",
            "wiki_page_title",
            "wiki_revision_id",
            "wiki_revision_timestamp",
            "wiki_revision_url",
        ]
    ].drop_duplicates()
    inventory[["wiki_page_id", "wiki_revision_id"]] = inventory[
        ["wiki_page_id", "wiki_revision_id"]
    ].astype("int64")
    export_frame(inventory, output / "corpus_revisions.parquet")
    stats = write_edges(nodes, pages, out / "edges")
    stats.update(
        input_rows=table.num_rows,
        unresolved_rows=len(unresolved),
        revision_ids=len(inventory),
        pair_contributions=43449334,
        entity_types=nodes.groupby("type").size().to_dict(),
    )
    save_json(out / "summary.json", stats)
    return stats


def collect_wiki(output: Path) -> dict[str, Any]:
    """Reuse exact saved parse responses; request only missing exact oldids."""
    inventory = pd.read_parquet(output / "corpus_revisions.parquet")
    wanted = dict(zip(inventory.wiki_revision_id, inventory.wiki_page_id))
    cached = {}
    source_dirs = [
        DATA / name / "requests"
        for name in [
            "source_page_ids_20261026",
            "source_page_ids_history_pilot_20261027",
            "source_page_versions_history_20261027",
        ]
    ]
    for directory in source_dirs:
        for path in directory.glob("*.json.gz"):
            record = read_json(path)
            if record.get("ok") and record.get("params", {}).get("action") == "parse":
                data = json.loads(record["response_text"]).get("parse", {})
                revision = data.get("revid")
                if revision in wanted:
                    validate_parse(data, int(wanted[revision]), int(revision))
                    cached[revision] = (path, record.get("retrieved_utc"))
    LOG.info("Exact revision HTML cache: %s/%s", len(cached), len(wanted))
    client = WikiClient(output / "wiki_parse")
    links, audit = [], []
    new_calls = 0
    for i, row in enumerate(inventory.itertuples(index=False)):
        page_id, revision_id = int(row.wiki_page_id), int(row.wiki_revision_id)
        if revision_id in cached:
            path, retrieved = cached[revision_id]
            data = json.loads(read_json(path)["response_text"])["parse"]
            source = "SAVED_EXACT_REVISION_HTML"
        else:
            try:
                response, key = client.query(
                    {
                        "action": "parse",
                        "oldid": revision_id,
                        "prop": "text|revid",
                        "disableeditsection": 1,
                    }
                )
                data = response["parse"]
                path = client.cache / key
                retrieved = read_json(path).get("retrieved_utc")
                source = "NEW_EXACT_REVISION_HTML"
                new_calls += 1
            except (RuntimeError, KeyError) as error:
                audit.append(
                    {
                        "wiki_page_id": page_id,
                        "wiki_revision_id": revision_id,
                        "status": "FETCH_FAILED",
                        "error": str(error),
                    }
                )
                save_json(
                    output / "wiki_progress.json",
                    {
                        "completed": i + 1,
                        "total": len(inventory),
                        "new_calls": new_calls,
                        "failed": sum(x["status"] == "FETCH_FAILED" for x in audit),
                    },
                )
                continue
        validate_parse(data, page_id, revision_id)
        evidence = str(path.resolve())
        for title, anchor in article_links(data["text"]):
            links.append(
                (page_id, revision_id, title, anchor, "ARTICLE_HYPERLINK", evidence)
            )
        links.append(
            (
                page_id,
                revision_id,
                row.wiki_page_title,
                row.wiki_page_title,
                "ARTICLE_HEADING",
                evidence,
            )
        )
        audit.append(
            {
                "wiki_page_id": page_id,
                "wiki_revision_id": revision_id,
                "status": source,
                "html_evidence": evidence,
                "html_retrieved_utc": retrieved,
                "article_revision_timestamp": str(row.wiki_revision_timestamp),
            }
        )
        if i % 20 == 0:
            LOG.info(
                "Article links %s/%s; new parse calls %s",
                i + 1,
                len(inventory),
                new_calls,
            )
            save_json(
                output / "wiki_progress.json",
                {"completed": i + 1, "total": len(inventory), "new_calls": new_calls},
            )
    export_frame(
        pd.DataFrame(
            links,
            columns=[
                "wiki_page_id",
                "wiki_revision_id",
                "target_title",
                "anchor_text",
                "presence_method",
                "evidence",
            ],
        ),
        output / "wiki_link_occurrences.parquet",
    )
    export_frame(pd.DataFrame(audit), output / "wiki_revision_audit.parquet")
    stats = {
        "expected_revisions": len(inventory),
        "cached_exact_revisions": len(cached),
        "new_parse_calls": new_calls,
        "failed_revisions": sum(x["status"] == "FETCH_FAILED" for x in audit),
        "link_records": len(links),
        "distinct_target_titles": len({x[2] for x in links}),
    }
    save_json(output / "wiki_collection_summary.json", stats)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("stage", choices=["b", "wiki"])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args.output.mkdir(parents=True, exist_ok=True)
    stats = build_b(args.output) if args.stage == "b" else collect_wiki(args.output)
    LOG.info("Finished: %s", json.dumps(stats))


if __name__ == "__main__":
    main()
