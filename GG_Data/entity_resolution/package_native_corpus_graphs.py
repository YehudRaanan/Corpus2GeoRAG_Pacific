"""Package verified graph tables with portable evidence and a SHA256 manifest."""

from __future__ import annotations

import json
import logging
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from attach_source_page_ids import read_json, save_json, sha256
from native_corpus_graphs import INPUT, INPUT_HASH, OUTPUT, export_frame
from native_graph_reference import EVENTKG

LOG = logging.getLogger(__name__)
ORIGINAL = Path(
    "D:/Projects/entity_count_20261026_8pj6qtu2/georag_selected_v2_full_n36335_r345732948_20261024.parquet"
)
ORIGINAL_HASH = "dcd51dfa237b63378279ced4f9739a45d8cf8ce3991579f20848295448f83f16"


def package(output: Path) -> dict:
    if sha256(INPUT) != INPUT_HASH or sha256(ORIGINAL) != ORIGINAL_HASH:
        raise ValueError("An immutable source Parquet changed")
    summaries = {
        graph: read_json(output / f"graph_{graph}/summary.json") for graph in ["a", "b"]
    }
    for graph in ["a", "b"]:
        result = read_json(output / f"graph_{graph}/verification.json")
        if not result["every_weight_verified_by_independent_page_set_intersection"]:
            raise ValueError("Finish independent graph verification before packaging")
    if not summaries["a"]["eventkg_complete_corpus_coverage"]:
        raise ValueError("Do not publish an incomplete EventKG graph as complete")
    evidence_dir = output / "evidence/wiki_exact"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    audit = pd.read_parquet(output / "wiki_revision_audit.parquet")
    evidence_rows = []
    for path in sorted(set(audit.html_evidence)):
        source = Path(path)
        digest = sha256(source)
        target = evidence_dir / (digest + ".json.gz")
        if not target.exists():
            shutil.copy2(source, target)
        evidence_rows.append(
            {
                "original_path": path,
                "portable_path": target.relative_to(output).as_posix(),
                "sha256": digest,
            }
        )
    export_frame(
        pd.DataFrame(evidence_rows), output / "portable_evidence_index.parquet"
    )
    inputs = output / "inputs"
    inputs.mkdir(exist_ok=True)
    shutil.copy2(INPUT, inputs / "corpus_v3.parquet")
    source_metadata = output / "evidence/eventkg_metadata"
    source_metadata.mkdir(exist_ok=True)
    for name in ["graphs.ttl", "schema.ttl", "void.ttl", "manifest.json"]:
        shutil.copy2(EVENTKG / "metadata" / name, source_metadata / name)
    run = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_v3_sha256": INPUT_HASH,
        "original_parquet_sha256": ORIGINAL_HASH,
        "input_rows": 309864,
        "resolved_rows": 309319,
        "unresolved_rows_preserved": 545,
        "wiki_pages": 425,
        "wiki_revisions": 571,
        "identity": "exact name + source-native type",
        "weight": "count of distinct shared Wikipedia page IDs; binary node/page membership",
        "revision_policy": "union across saved revisions of the same page",
        "cross_source_alignment": False,
        "type_mapping": False,
        "source_page_matching_rerun": False,
        "extraction_rerun": False,
        "graphs": summaries,
        "wiki_collection": read_json(output / "wiki_collection_summary.json"),
        "wikidata_collection": read_json(output / "wikidata_collection_summary.json"),
        "eventkg_collection": read_json(output / "eventkg_collection_summary.json"),
        "eventkg_archive_transfer_elapsed_seconds": read_json(
            output / "eventkg_archive/download_manifest.json"
        )["elapsed_seconds"],
        "time_basis": {
            "estimate_minutes": [90, 180],
            "estimated_start_israel": "2026-10-28T01:12:00+02:00",
            "active_work": "unmeasured",
            "approval_wait": "unmeasured",
            "note": "Elapsed time is not active work. Estimates are model-derived, not calibrated P80.",
        },
        "backup_status": "Local checkpoint only; ignored graph data is local and is not protected on GitHub",
    }
    save_json(output / "run_summary.json", run)
    a, b = summaries["a"], summaries["b"]
    text = f"""# Native corpus graphs — 28 October 2026

Both graphs are built locally from the saved corpus assignments. No extraction or source-page matching was repeated. The original Parquet and V3 hashes are unchanged. All 545 unresolved rows are retained unchanged in graph B and excluded from page weights.

| Graph | Nodes | Edges | Node/page pairs | Sum of weights |
|---|---:|---:|---:|---:|
| A: Wikidata + EventKG native types | {a['nodes']:,} | {a['edges']:,} | {a['node_page_pairs']:,} | {a['weight_sum']:,} |
| B: Daniel name + entity_group | {b['nodes']:,} | {b['edges']:,} | {b['node_page_pairs']:,} | {b['weight_sum']:,} |

## Rules

Identity is the exact source name plus native type. Names are not case-folded or merged as aliases. Graph A uses Wikidata P31 URIs and EventKG RDF type URIs; graph B uses Daniel's entity_group and retains subtype metadata. No source-type mapping or alignment to graph B was performed. A name/type pair with several QIDs remains one requested identity; every QID is retained. EventKG English preferred labels and English source labels remain distinct names. EVENT occurs only in A as its native sem:Event type.

Each edge is undirected and stored once, with source < target. Its integer weight is the count of distinct shared Wikipedia page IDs. A node contributes at most once per page. Presence is the union across the saved revisions of that page; two different revisions can therefore supply the two endpoints. Revision IDs do not increase the page count. Self-edges are excluded. All 425 corpus pages are represented. There are 571 saved revisions; 124 pages have more than one saved revision.

## Source and version limits

Graph A uses internal article hyperlinks and the article heading from each exact saved oldid. It does not identify unlinked names or date literals through a new NER run. Link targets are associated with QIDs using explicit English Wikipedia sitelinks or page properties, including explicit redirects. Disambiguation pages and missing QIDs remain audited. This association is not an alignment to Daniel's names.

All 571 page/revision identities were checked. A saved revision is a text-matching revision from the earlier run, not proof of the original extraction date. HTML was rendered when its recorded request was made; transcluded templates can reflect later state. Wikipedia source revision time and HTML retrieval time are separate fields in wiki_revision_audit.parquet.

Wikidata metadata uses the saved BigQuery snapshot captured 18 October 2026 plus explicit API records collected in this run. The table snapshot, per-item revision/modified fields, API evidence and QID audit are included. Types and target QID associations are not reconstructed as of each historical Wikipedia revision. The {run['wikidata_collection']['corpus_qids_without_direct_type']:,} QIDs without direct P31 are audited; no MISC type was invented. EventKG types can still supply nodes for these QIDs.

EventKG release 3.2 is sourced from the official full N-Quads archive. The archive's published MD5 and current SHA256 were verified. All event/entity identity records were scanned for the corpus QIDs, followed by all native metadata records in events, entities, types, types_dbpedia, types_wikidata and preferred_labels. All named source graphs in these records are retained. Coverage means all corpus QIDs were checked for explicit EventKG owl:sameAs identity; it does not mean EventKG contains every QID, that every source entity has a QID, or that EventKG has these Wikipedia revisions. No fuzzy association of EventKG resources without an explicit QID was attempted. The earlier WWII filter was not used as the final coverage boundary. Global EventKG co-mention counts were not used as corpus weights.

## Files

- graph_a/ and graph_b/: nodes.parquet, node_page_presence.parquet, node_revision_presence.parquet, edges/part-*.parquet, summary.json and verification.json. Node IDs are local to each graph. Read the edge directory as one Parquet dataset; do not load both full graphs into memory without checking available RAM.
- graph_a/native_entity_types.parquet: native name/type/QID/source assertions. qid_type_audit.parquet keeps missing direct types. links_without_qid.parquet keeps link-association limits.
- graph_b/unresolved_rows.parquet: 545 unchanged original V3 records, with source_row_index. Graph B contains {b['nodes_without_page']} nodes with no resolved page.
- corpus_revisions.parquet, wiki_link_occurrences.parquet, wiki_revision_audit.parquet: exact page/revision inventory and linked-presence evidence.
- title_qid_mapping.parquet, wikidata_corpus_metadata.json.gz, wikidata_api_evidence.json, bigquery_snapshot.json: explicit identity/type evidence and snapshot metadata.
- eventkg_corpus_assertions.parquet, eventkg_resource_qids.parquet, eventkg_type_labels.parquet, eventkg_qid_coverage.parquet: source-native assertions and per-QID coverage.
- eventkg_archive/corpus/: original selected N-Quads and explicit resource/QID map. Archive/filter manifests identify the source release, full scan and selected-file hashes.
- inputs/corpus_v3.parquet: unchanged V3 input copy. portable_evidence_index.parquet maps original absolute HTML evidence paths to portable copies under evidence/wiki_exact/. EventKG graph/schema metadata is under evidence/eventkg_metadata/.
- run_summary.json and manifest.sha256: counts, rules, limits, source hashes and package integrity. The ZIP includes selected corpus data and evidence; it excludes the 7.8 GB global archive and HTTP range copies, which remain local.

## Verification and storage

Every stored edge weight in both graphs was independently checked by intersecting packed page sets, separately from sparse graph construction. Checks also cover exact node identities, unique memberships/edges, revision collapse, all native type assertions, all A revision memberships, all 545 unchanged unresolved records and immutable input hashes. See verification.json in each graph directory.

Code and report have local Git checkpoints only. Ignored graph data and source archives are local; they have not been pushed or backed up on GitHub.

Sources: [EventKG release 3.2](https://zenodo.org/records/10424118), [EventKG source files](https://eventkg.l3s.uni-hannover.de/data.html), [MediaWiki revision parsing](https://www.mediawiki.org/wiki/API:Parsing_wikitext), [Wikidata data access](https://www.wikidata.org/wiki/Wikidata:Data_access).
"""
    (output / "README.md").write_text(text, encoding="utf-8")
    files = sorted(
        path
        for path in output.rglob("*")
        if path.is_file()
        and path.name != "manifest.sha256"
        and not (
            path.parent == output / "eventkg_archive"
            and (path.suffix == ".bin" or path.name.endswith(".tar.gz"))
        )
    )
    with (output / "manifest.sha256").open("x", encoding="utf-8") as stream:
        for path in files:
            stream.write(
                sha256(path) + "  " + path.relative_to(output).as_posix() + "\n"
            )
    files.append(output / "manifest.sha256")
    target = output.with_suffix(".zip")
    with zipfile.ZipFile(
        target, "x", compression=zipfile.ZIP_STORED, allowZip64=True
    ) as bundle:
        for path in files:
            bundle.write(path, path.relative_to(output))
    with zipfile.ZipFile(target) as bundle:
        if bundle.testzip() is not None:
            raise ValueError("ZIP integrity check failed")
    LOG.info(
        "Packaged %s files, ZIP %s bytes, SHA256 %s",
        len(files),
        target.stat().st_size,
        sha256(target),
    )
    return {
        "files": len(files),
        "zip": str(target),
        "zip_bytes": target.stat().st_size,
        "zip_sha256": sha256(target),
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    LOG.info(
        "Finished: %s",
        json.dumps(package(Path(sys.argv[1]) if len(sys.argv) > 1 else OUTPUT)),
    )
