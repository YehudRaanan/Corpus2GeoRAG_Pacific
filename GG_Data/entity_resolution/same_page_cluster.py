"""Export a complete small A/B example on identical saved Wikipedia pages."""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
import shutil
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from attach_source_page_ids import save_json, sha256
from native_corpus_graphs import OUTPUT, export_frame, write_edges
from verify_native_corpus_graphs import verify_graph

TARGET = OUTPUT.parent / "same_page_cluster_20261028"


def csv_frame(frame: pd.DataFrame, path: Path) -> None:
    result = frame.copy()
    for column in result:
        if result[column].map(lambda x: isinstance(x, (list, np.ndarray))).any():
            result[column] = result[column].map(
                lambda x: json.dumps(list(x), ensure_ascii=False)
            )
    result.to_csv(path, index=False, encoding="utf-8-sig")


def main() -> None:
    if TARGET.exists() or TARGET.with_suffix(".zip").exists():
        raise FileExistsError("Preserve existing example outputs")
    hashes = {
        line[66:]: line[:64]
        for line in (OUTPUT / "manifest.sha256").read_text("utf-8").splitlines()
    }
    inputs = {}

    def table(name: str) -> pd.DataFrame:
        digest = sha256(OUTPUT / name)
        if digest != hashes[name]:
            raise ValueError(f"Parent input changed: {name}")
        inputs[name] = digest
        return pd.read_parquet(OUTPUT / name)

    inventory = table("corpus_revisions.parquet")
    titles = inventory.drop_duplicates("wiki_page_id").set_index("wiki_page_id")
    presence = {g: table(f"graph_{g}/node_page_presence.parquet") for g in "ab"}
    page_sets = {
        g: frame.groupby("wiki_page_id").node_id.agg(set).to_dict()
        for g, frame in presence.items()
    }
    candidates = sorted(
        p
        for p in titles.index
        if 50 <= len(page_sets["a"][p]) <= 350 and 10 <= len(page_sets["b"][p]) <= 160
    )
    ranking = []
    for ids in itertools.combinations(candidates, 3):
        minima = {}
        for g in "ab":
            sets = [page_sets[g][p] for p in ids]
            minima[g] = min(
                len(x & y) / len(x | y) for x, y in itertools.combinations(sets, 2)
            )
        if min(minima.values()) > 0:
            ranking.append(
                {
                    "page_ids": list(ids),
                    "minimum_pair_jaccard": minima,
                    "score": 2 * minima["a"] * minima["b"] / sum(minima.values()),
                }
            )
    ranking.sort(key=lambda x: (-x["score"], x["page_ids"]))
    ids = sorted(ranking[0]["page_ids"], key=lambda p: titles.loc[p, "wiki_page_title"])
    selected_revisions = inventory.loc[inventory.wiki_page_id.isin(ids)].copy()
    TARGET.mkdir()
    export_frame(selected_revisions, TARGET / "selected_revisions.parquet")
    csv_frame(selected_revisions, TARGET / "selected_revisions.csv")
    save_json(
        TARGET / "selection.json",
        {
            "candidate_pages": len(candidates),
            "connected_triples": len(ranking),
            "policy": "A 50..350 nodes, B 10..160 nodes per page; maximize harmonic mean of weakest pairwise Jaccard within A and B; ties use sorted page IDs",
            "ranking": ranking,
        },
    )
    links = table("wiki_link_occurrences.parquet")
    links = links.loc[links.wiki_page_id.isin(ids)].copy()
    mapping = table("title_qid_mapping.parquet")
    mapping = mapping.loc[mapping.target_title.isin(links.target_title)].copy()
    qid_links = links.merge(mapping[["target_title", "qid"]], on="target_title")
    qids = set(qid_links.qid.dropna())
    export_frame(qid_links, TARGET / "linked_qid_presence.parquet")
    export_frame(mapping, TARGET / "title_qid_mapping.parquet")
    native = table("graph_a/native_entity_types.parquet")
    native = native.loc[native.qid.isin(qids)].copy()
    summaries, overlaps = {}, []
    for g in "ab":
        out = TARGET / f"graph_{g}"
        parents = table(f"graph_{g}/nodes.parquet")
        member = presence[g].loc[presence[g].wiki_page_id.isin(ids)].copy()
        nodes = parents.loc[parents.node_id.isin(member.node_id)].copy()
        nodes = nodes.rename(
            columns={
                "node_id": "parent_node_id",
                "page_count": "parent_page_count",
                "mention_count": "parent_mention_count",
                "unresolved_mentions": "parent_unresolved_mentions",
                "subtypes": "parent_subtypes",
            }
        ).reset_index(drop=True)
        nodes.insert(0, "node_id", np.arange(len(nodes), dtype=np.int32))
        local_ids = nodes.set_index("parent_node_id").node_id.to_dict()
        member["node_id"] = member.node_id.map(local_ids).astype("int32")
        revisions = table(f"graph_{g}/node_revision_presence.parquet")
        revisions = revisions.loc[revisions.wiki_page_id.isin(ids)].copy()
        revisions["node_id"] = revisions.node_id.map(local_ids).astype("int32")
        nodes["page_count"] = nodes.node_id.map(
            member.groupby("node_id").size()
        ).astype("int32")
        if g == "a":
            extras = native.groupby(["name", "type"]).agg(
                qids=("qid", lambda x: sorted(set(x))),
                sources=("source", lambda x: sorted(set(x))),
                type_labels=("type_label", lambda x: sorted(set(x))),
                resources=("resource", lambda x: sorted(set(x))),
            )
            nodes = nodes.drop(columns=list(extras.columns)).merge(
                extras.reset_index(), on=["name", "type"], validate="one_to_one"
            )
            assert nodes.qids.map(set).map(lambda x: x <= qids and bool(x)).all()
            export_frame(native, out / "native_entity_types.parquet")
            audit = table("graph_a/qid_type_audit.parquet")
            export_frame(
                audit.loc[audit.qid.isin(qids)], out / "qid_type_audit.parquet"
            )
        export_frame(nodes, out / "nodes.parquet")
        export_frame(member, out / "node_page_presence.parquet")
        export_frame(revisions, out / "node_revision_presence.parquet")
        csv_frame(nodes, out / "nodes.csv")
        stats = write_edges(nodes, member, out / "edges")
        edges = pd.read_parquet(out / "edges")
        sets = member.groupby("node_id").wiki_page_id.agg(set).to_dict()
        edges["wiki_page_ids"] = [
            sorted(int(p) for p in sets[s] & sets[t])
            for s, t in zip(edges.source, edges.target)
        ]
        assert edges.wiki_page_ids.map(len).tolist() == edges.weight.tolist()
        csv_frame(edges, out / "edges.csv")
        graph = nx.Graph()
        for row in nodes.to_dict("records"):
            node_id = row.pop("node_id")
            graph.add_node(
                node_id,
                **{
                    k: (
                        json.dumps(list(v), ensure_ascii=False)
                        if isinstance(v, (list, np.ndarray))
                        else v
                    )
                    for k, v in row.items()
                },
            )
        for row in edges.itertuples(index=False):
            graph.add_edge(
                row.source,
                row.target,
                weight=int(row.weight),
                wiki_page_ids=json.dumps(row.wiki_page_ids),
            )
        nx.write_graphml(graph, out / "graph.graphml")
        restored = nx.read_graphml(out / "graph.graphml", node_type=int)
        assert set(restored.nodes) == set(graph.nodes)
        assert {tuple(sorted((s, t))): d for s, t, d in restored.edges(data=True)} == {
            tuple(sorted((s, t))): d for s, t, d in graph.edges(data=True)
        }
        assert dict(restored.nodes(data=True)) == dict(graph.nodes(data=True))
        assert set(member.wiki_page_id) == set(ids)
        parent_by_id = parents.set_index("node_id")
        assert all(
            (row.name, row.type)
            == tuple(parent_by_id.loc[row.parent_node_id, ["name", "type"]])
            for row in nodes.itertuples(index=False)
        )
        stats.update(
            distinct_native_types=int(nodes.type.nunique()),
            weight_distribution={
                str(k): int(v)
                for k, v in edges.weight.value_counts().sort_index().items()
            },
            shared_on_all_three=int(nodes.page_count.eq(3).sum()),
            shared_on_at_least_two=int(nodes.page_count.ge(2).sum()),
        )
        save_json(out / "summary.json", stats)
        result = verify_graph(out)
        result.update(
            parent_identity_preserved=True,
            same_selected_pages=True,
            graphml_roundtrip=True,
            explicit_edge_page_sets_verified=True,
        )
        save_json(out / "verification.json", result)
        summaries[g] = stats
        for left, right in itertools.combinations(ids, 2):
            shared = page_sets[g][left] & page_sets[g][right]
            overlaps.append(
                {
                    "graph": g,
                    "page_1": int(left),
                    "page_2": int(right),
                    "shared_native_entities": len(shared),
                }
            )
    export_frame(pd.DataFrame(overlaps), TARGET / "page_overlap.parquet")
    csv_frame(pd.DataFrame(overlaps), TARGET / "page_overlap.csv")
    audit = table("wiki_revision_audit.parquet")
    audit = audit.loc[audit.wiki_page_id.isin(ids)].copy()
    portable = table("portable_evidence_index.parquet").set_index("original_path")
    evidence = TARGET / "evidence"
    evidence.mkdir()
    paths = []
    for row in audit.itertuples(index=False):
        record = portable.loc[row.html_evidence]
        source = OUTPUT / record.portable_path
        assert sha256(source) == record.sha256
        dest = evidence / source.name
        shutil.copy2(source, dest)
        paths.append(dest.relative_to(TARGET).as_posix())
    audit["portable_evidence"] = paths
    export_frame(audit, TARGET / "selected_revision_audit.parquet")
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    positions = {ids[0]: (0, 0.8), ids[1]: (-0.85, -0.6), ids[2]: (0.85, -0.6)}
    for g, ax, color in zip("ab", axes, ["#d9eafb", "#dcefdc"]):
        graph = nx.Graph()
        graph.add_nodes_from(ids)
        graph.add_edges_from(
            (x["page_1"], x["page_2"]) for x in overlaps if x["graph"] == g
        )
        labels = {
            p: titles.loc[p, "wiki_page_title"]
            .replace(" (", "\n(")
            .replace(" Strait", "\nStrait")
            + f"\n{len(page_sets[g][p])} entity/type nodes"
            for p in ids
        }
        edge_labels = {
            (x["page_1"], x["page_2"]): f"{x['shared_native_entities']} shared"
            for x in overlaps
            if x["graph"] == g
        }
        nx.draw_networkx_nodes(
            graph,
            positions,
            node_size=6800,
            node_color=color,
            edgecolors="#52616b",
            ax=ax,
        )
        nx.draw_networkx_edges(graph, positions, width=1.6, edge_color="#82909a", ax=ax)
        nx.draw_networkx_labels(graph, positions, labels, font_size=9, ax=ax)
        nx.draw_networkx_edge_labels(
            graph, positions, edge_labels, font_size=10, rotate=False, ax=ax
        )
        ax.set_title(
            f"Graph {g.upper()}: {'Wikidata + EventKG' if g == 'a' else 'Daniel'}\n{summaries[g]['nodes']} nodes / {summaries[g]['edges']:,} edges"
        )
        ax.set_xlim(-1.65, 1.65)
        ax.set_ylim(-1.2, 1.45)
        ax.axis("off")
    fig.suptitle("Same three saved Wikipedia pages: page-overlap preview", fontsize=15)
    fig.text(
        0.5,
        0.035,
        "Each circle is a page. Edge labels count shared native entity/type identities.\nThe exported graphs contain entity/type nodes; all nodes are retained.",
        ha="center",
        fontsize=10,
    )
    fig.subplots_adjust(bottom=0.19, top=0.78, wspace=0.08)
    fig.savefig(TARGET / "page_overlap.png", dpi=160)
    fig.savefig(TARGET / "page_overlap.svg")
    plt.close(fig)
    report = {
        "graphs": summaries,
        "page_ids": [int(p) for p in ids],
        "revision_ids": selected_revisions.wiki_revision_id.astype(int).tolist(),
        "parent_inputs_sha256": inputs,
        "weight_scope": "selected page IDs only; binary membership; union across saved revisions of each page",
        "alignment": False,
        "type_mapping": False,
        "parent_full_edges_read": False,
        "raw_mentions_read": False,
        "backup_status": "Local checkpoint only; ignored data is local",
    }
    save_json(TARGET / "run_summary.json", report)
    page_lines = "\n".join(
        f"- {row.wiki_page_title}: page {row.wiki_page_id}, [revision {row.wiki_revision_id}]({row.wiki_revision_url}), {row.wiki_revision_timestamp}"
        for row in selected_revisions.itertuples(index=False)
    )
    summary_lines = "\n".join(
        f"| {g.upper()} | {s['nodes']:,} | {s['edges']:,} | {s['shared_on_all_three']} | {s['weight_distribution']} |"
        for g, s in summaries.items()
    )
    (TARGET / "README.md").write_text(
        f"""# Same-page native graph example

Both complete subgraphs use exactly these saved page/revision records:

{page_lines}

| Graph | Nodes | Edges | Nodes on all 3 pages | Edge weight distribution |
|---|---:|---:|---:|---|
{summary_lines}

Equivalent means the same page IDs and exact saved revisions, not aligned entities or equal graph sizes. A retains native Wikidata/EventKG names and type URIs, with QIDs. B retains exact Daniel name/entity_group identities. No cross-source identity or type mapping was performed. All nodes occurring on the selected pages are included. Weights count only these three pages, so a weight of 2 means presence on two selected pages, regardless of occurrences elsewhere in the full corpus.

Selection: among {len(candidates)} small candidate pages (A 50–350 nodes, B 10–160), enumerate connected three-page sets and maximize the harmonic mean of the minimum pairwise Jaccard score within each graph. The selected triple ranks first among {len(ranking)} connected triples. This deliberately cohesive example is not a representative statistical sample. See selection.json for the full ranking.

Each graph folder contains nodes.parquet, node_page_presence.parquet, node_revision_presence.parquet, partitioned Parquet edges, nodes.csv, edges.csv, graph.graphml, summary.json and verification.json. CSV list fields and GraphML list attributes are JSON strings. Node IDs are local to each example; parent_node_id links to the full source graph. parent_page_count, parent_mention_count, parent_unresolved_mentions and parent_subtypes retain full-parent context, not selected-page statistics. A QID/source/type metadata is restricted to QIDs explicitly linked on selected pages; native_entity_types.parquet retains the assertions and provenance.

Open graph.graphml in Gephi or another GraphML reader to inspect the entity network. edges.csv includes the exact shared wiki_page_ids for every edge. page_overlap.png/svg is a page-level preview, not the exported entity network. selected_revisions.csv/parquet records page IDs, oldids, timestamps and permanent URLs. Selected HTML response evidence is portable under evidence/, indexed in selected_revision_audit.parquet. linked_qid_presence.parquet retains anchors, link targets, QIDs and page/revision context.

Every local edge weight was independently verified from page sets. GraphML nodes and weighted edges passed a round-trip check, all native names/types match their parent identities, and graph files are bound to verification hashes. Parent inputs were checked against the parent dataset manifest. No parent full edge data or raw 309K mention rows were read. No extraction or page matching was repeated. The parent 545 unresolved rows remain unchanged and unassigned; they cannot belong to this page-selected example.

Source limits remain those of the parent dataset: A covers internal links and article headings, not unlinked NER mentions. Exact saved article revisions do not establish original extraction dates; rendered templates can reflect later state. Wikidata and EventKG types are source snapshots, not reconstructed historical types. Untyped QIDs remain in A's QID audit. The parent README contains full source-release and version limits. Both parent graphs and their ZIP remain unchanged.

Backup status: Local checkpoint only. Data is local and is not backed up to GitHub.
""",
        encoding="utf-8",
    )
    files = sorted(p for p in TARGET.rglob("*") if p.is_file())
    with (TARGET / "manifest.sha256").open("x", encoding="utf-8") as stream:
        for path in files:
            stream.write(
                sha256(path) + "  " + path.relative_to(TARGET).as_posix() + "\n"
            )
    files.append(TARGET / "manifest.sha256")
    with zipfile.ZipFile(
        TARGET.with_suffix(".zip"), "x", zipfile.ZIP_DEFLATED
    ) as bundle:
        for path in files:
            bundle.write(path, path.relative_to(TARGET))
    with zipfile.ZipFile(TARGET.with_suffix(".zip")) as bundle:
        assert bundle.testzip() is None
        for path in files:
            assert hashlib.sha256(
                bundle.read(path.relative_to(TARGET).as_posix())
            ).hexdigest() == sha256(path)
    logging.info("Complete: %s", json.dumps(report["graphs"]))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    main()
