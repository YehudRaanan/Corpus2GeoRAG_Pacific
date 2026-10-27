"""Collect native Wikidata/EventKG metadata for the saved corpus hyperlinks."""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from attach_source_page_ids import WikiClient, read_json, save_json, sha256
from native_corpus_graphs import (
    OUTPUT,
    export_frame,
    memberships,
    project_entity,
    write_edges,
)
from rdflib.util import from_n3

LOG = logging.getLogger(__name__)
BQ = Path.home() / ".cache/geoai_bigquery_20261018"
EVENTKG = Path("D:/Projects/GeoAI/Data/external/wwii_task_force/eventkg_v3_2")
WD = "http://www.wikidata.org/entity/"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
PREF_LABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"
SAME_AS = "http://www.w3.org/2002/07/owl#sameAs"
NQUAD = re.compile(
    r'^<([^>]+)>\s+<([^>]+)>\s+(<[^>]+>|"(?:[^"\\]|\\.)*"(?:@[a-zA-Z-]+|\^\^<[^>]+>)?)\s+<([^>]+)>\s+\.\s*$'
)


def cached_request(
    endpoint: str, params: dict[str, Any], directory: Path
) -> tuple[dict, str]:
    directory.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(
        json.dumps([endpoint, params], sort_keys=True).encode()
    ).hexdigest()
    path = directory / f"{key}.json.gz"
    if not path.exists():
        start = time.monotonic()
        record = {
            "endpoint": endpoint,
            "params": params,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        }
        try:
            response = requests.get(
                endpoint,
                params=params,
                headers={
                    "User-Agent": "Corpus2GeoRAG-Pacific-native-graphs/0.1 (https://github.com/EtzionR/Corpus2GeoRAG_Pacific)"
                },
                timeout=30,
            )
            record.update(http_status=response.status_code, response_text=response.text)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise RuntimeError(str(data["error"]))
            record["ok"] = True
        except (requests.RequestException, ValueError, RuntimeError) as error:
            record.update(ok=False, error=f"{type(error).__name__}: {error}")
        record["elapsed_seconds"] = time.monotonic() - start
        save_json(path, record)
        time.sleep(0.1)
    record = read_json(path)
    if not record["ok"]:
        raise RuntimeError(
            f"Saved call failed, no automatic retry: {path}: {record.get('error')}"
        )
    return json.loads(record["response_text"]), str(path.resolve())


def resolve_alias(title: str, aliases: dict[str, str]) -> str | None:
    seen = set()
    while title in aliases:
        if title in seen:
            return None
        seen.add(title)
        title = aliases[title]
    return title


def cached_title_status(entity: dict[str, Any]) -> tuple[str, str | None]:
    if "Q4167410" in entity.get("direct_types", []):
        return "DISAMBIGUATION_TARGET", None
    return "BQ_EXACT_ENWIKI_SITELINK", entity["id"]


def collect_wikidata(output: Path) -> dict[str, Any]:
    links = pd.read_parquet(output / "wiki_link_occurrences.parquet")
    titles = sorted(set(links.target_title))
    LOG.info("Loading saved BigQuery entities for %s article targets", len(titles))
    entities = read_json(BQ / "entity_metadata.json.gz")
    title_qids: dict[str, set[str]] = defaultdict(set)
    for qid, entity in entities.items():
        title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
        if title:
            title_qids[title].add(qid)
    associations, pending = [], []
    for title in titles:
        qids = title_qids.get(title, set())
        if len(qids) == 1:
            status, qid = cached_title_status(entities[next(iter(qids))])
            associations.append(
                {
                    "target_title": title,
                    "qid": qid,
                    "status": status,
                    "metadata_evidence": str(
                        (BQ / "entity_metadata.json.gz").resolve()
                    ),
                }
            )
        else:
            pending.append(title)
    del title_qids
    LOG.info(
        "BigQuery exact sitelinks %s; titles needing explicit Wiki metadata %s",
        len(associations),
        len(pending),
    )
    client = WikiClient(output / "title_qid_requests")
    for offset in range(0, len(pending), 50):
        batch = pending[offset : offset + 50]
        try:
            data, key = client.query(
                {
                    "action": "query",
                    "prop": "pageprops",
                    "ppprop": "wikibase_item|disambiguation",
                    "titles": "|".join(batch),
                    "redirects": 1,
                }
            )
            evidence = str((client.cache / key).resolve())
            query = data.get("query", {})
            aliases = {
                item["from"]: item["to"]
                for group in ["normalized", "redirects", "converted"]
                for item in query.get(group, [])
            }
            pages = {page.get("title"): page for page in query.get("pages", [])}
            for title in batch:
                canonical = resolve_alias(title, aliases)
                page = pages.get(canonical, {})
                props = page.get("pageprops", {})
                qid = props.get("wikibase_item")
                if page.get("ns") != 0 or "missing" in page or "invalid" in page:
                    status, qid = "MISSING_OR_NON_ARTICLE", None
                elif "disambiguation" in props:
                    status, qid = "DISAMBIGUATION_TARGET", None
                elif not re.fullmatch(r"Q\d+", qid or ""):
                    status, qid = "NO_QID", None
                else:
                    status = "WIKI_EXPLICIT_PAGE_QID"
                associations.append(
                    {
                        "target_title": title,
                        "canonical_target_title": canonical,
                        "qid": qid,
                        "target_page_id": page.get("pageid"),
                        "status": status,
                        "metadata_evidence": evidence,
                    }
                )
        except RuntimeError as error:
            associations.extend(
                {
                    "target_title": title,
                    "qid": None,
                    "status": "QID_METADATA_FETCH_FAILED",
                    "metadata_evidence": str(error),
                }
                for title in batch
            )
        LOG.info(
            "QID metadata titles %s/%s", min(offset + 50, len(pending)), len(pending)
        )
        save_json(
            output / "qid_progress.json",
            {"completed_titles": len(associations), "total_titles": len(titles)},
        )
    mapping = pd.DataFrame(associations)
    export_frame(mapping, output / "title_qid_mapping.parquet")
    qids = set(mapping.qid.dropna())
    missing = sorted(qids - entities.keys(), key=lambda x: int(x[1:]))
    api_evidence = {}
    for offset in range(0, len(missing), 50):
        batch = missing[offset : offset + 50]
        try:
            data, evidence = cached_request(
                "https://www.wikidata.org/w/api.php",
                {
                    "format": "json",
                    "formatversion": 2,
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "labels|claims|info",
                    "languages": "en",
                },
                output / "wikidata_requests",
            )
            for qid, entity in data.get("entities", {}).items():
                entities[qid] = project_entity(entity)
                api_evidence[qid] = evidence
        except RuntimeError as error:
            for qid in batch:
                api_evidence[qid] = str(error)
        LOG.info(
            "New Wikidata entities %s/%s", min(offset + 50, len(missing)), len(missing)
        )
    needed_types = {
        t for qid in qids for t in entities.get(qid, {}).get("direct_types", [])
    }
    missing_types = sorted(needed_types - entities.keys(), key=lambda x: int(x[1:]))
    for offset in range(0, len(missing_types), 50):
        batch = missing_types[offset : offset + 50]
        try:
            data, evidence = cached_request(
                "https://www.wikidata.org/w/api.php",
                {
                    "format": "json",
                    "formatversion": 2,
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "labels|info",
                    "languages": "en",
                },
                output / "wikidata_requests",
            )
            for qid, entity in data.get("entities", {}).items():
                entities[qid] = project_entity(entity)
                api_evidence[qid] = evidence
        except RuntimeError as error:
            for qid in batch:
                api_evidence[qid] = str(error)
    selected = {qid: entities[qid] for qid in qids | needed_types if qid in entities}
    del entities
    gc.collect()
    save_json(output / "wikidata_corpus_metadata.json.gz", selected)
    save_json(output / "wikidata_api_evidence.json", api_evidence)
    save_json(output / "bigquery_snapshot.json", read_json(BQ / "table_snapshot.json"))
    stats = {
        "target_titles": len(titles),
        "title_statuses": mapping.status.value_counts().to_dict(),
        "corpus_qids": len(qids),
        "corpus_qids_with_metadata": sum(qid in selected for qid in qids),
        "corpus_qids_without_direct_type": sum(
            not selected.get(qid, {}).get("direct_types") for qid in qids
        ),
        "cached_bigquery_metadata_sha256": sha256(BQ / "entity_metadata.json.gz"),
        "new_wikidata_qids_requested": len(missing),
        "new_type_labels_requested": len(missing_types),
    }
    save_json(output / "wikidata_collection_summary.json", stats)
    return stats


def iter_quads(path: Path):
    """Parse the finite standard N-Quads form used by the saved EventKG files."""
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            match = NQUAD.fullmatch(line)
            if not match:
                raise ValueError(f"Unsupported EventKG quad: {path}:{number}")
            subject, predicate, raw, graph = match.groups()
            if raw.startswith("<"):
                yield subject, predicate, raw[1:-1], "uri", "", graph
            else:
                literal = from_n3(raw)
                yield subject, predicate, str(literal), "literal", str(
                    literal.language or ""
                ), graph


def validate_saved_scan(directory: Path) -> list[dict[str, Any]]:
    evidence = []
    for name in [
        "events",
        "entities",
        "types",
        "types_dbpedia",
        "types_wikidata",
        "preferred_labels",
    ]:
        folder = directory / name
        state = read_json(folder / "manifest.json")
        parts = list(folder.glob("part_*.nq.gz"))
        if state["next_offset"] != state["source_bytes"] or len(parts) != state["part"]:
            raise ValueError(f"Incomplete saved EventKG scan: {folder}")
        if (
            name in {"events", "entities"}
            and len(list(folder.glob("part_*.qid_map.tsv"))) != state["part"]
        ):
            raise ValueError(f"Incomplete saved EventKG QID map: {folder}")
        evidence.append(
            {
                "path": str((folder / "manifest.json").resolve()),
                "sha256": sha256(folder / "manifest.json"),
                **state,
            }
        )
    return evidence


def collect_eventkg(output: Path) -> dict[str, Any]:
    qids = set(pd.read_parquet(output / "title_qid_mapping.parquet").qid.dropna())
    scope_path = EVENTKG.parent / "wikidata_qids.txt"
    prior_scope = set(scope_path.read_text("ascii").splitlines())
    archive_folder = output / "eventkg_archive"
    full_scan = (archive_folder / "filter_manifest.json").exists()
    if full_scan:
        archive_manifest = read_json(archive_folder / "filter_manifest.json")
        if not archive_manifest["completed"] or archive_manifest[
            "title_qid_mapping_sha256"
        ] != sha256(output / "title_qid_mapping.parquet"):
            raise ValueError("Full archive scan does not match the current corpus QIDs")
        for name, expected in archive_manifest["output_sha256"].items():
            if sha256(archive_folder / "corpus" / name) != expected:
                raise ValueError(f"Changed full-archive corpus evidence: {name}")
        manifests = [archive_manifest]
        map_paths = [archive_folder / "corpus/resource_qids.tsv"]
        data_paths = sorted((archive_folder / "corpus").glob("*.nq.gz"))
        if len(data_paths) != 6:
            raise ValueError("Incomplete full-archive native metadata outputs")
    else:
        manifests = validate_saved_scan(EVENTKG)
        map_paths = [
            path
            for name in ["events", "entities"]
            for path in sorted((EVENTKG / name).glob("part_*.qid_map.tsv"))
        ]
        data_paths = [
            path
            for name in [
                "events",
                "entities",
                "types",
                "types_dbpedia",
                "types_wikidata",
                "preferred_labels",
            ]
            for path in sorted((EVENTKG / name).glob("part_*.nq.gz"))
        ]
    resources = defaultdict(set)
    for path in map_paths:
        for line in path.read_text("ascii").splitlines():
            qid, resource = line.split("\t")
            if qid in qids:
                resources[resource.strip("<>")].add(qid)
    rows = []
    source_files = []
    for path in data_paths:
        for s, p, o, kind, language, graph in iter_quads(path):
            if s in resources:
                rows.append((s, p, o, kind, language, graph, str(path.resolve())))
        source_files.append({"path": str(path.resolve()), "sha256": sha256(path)})
    export_frame(
        pd.DataFrame(
            rows,
            columns=[
                "resource",
                "predicate",
                "object",
                "object_kind",
                "language",
                "source_graph",
                "evidence",
            ],
        ),
        output / "eventkg_corpus_assertions.parquet",
    )
    qid_rows = [(resource, qid) for resource, ids in resources.items() for qid in ids]
    export_frame(
        pd.DataFrame(qid_rows, columns=["resource", "qid"]),
        output / "eventkg_resource_qids.parquet",
    )
    # The public interface query is a bounded coverage check, never a weight source.
    probe_error = None
    try:
        _, evidence = cached_request(
            "https://eventkginterface.l3s.uni-hannover.de/sparql",
            {
                "query": "SELECT ?s WHERE { ?s <http://www.w3.org/2002/07/owl#sameAs> <http://www.wikidata.org/entity/Q362> } LIMIT 1",
                "format": "application/sparql-results+json",
            },
            output / "eventkg_endpoint_probe",
        )
        probe_error = "ENDPOINT_AVAILABLE_REQUIRES_CORPUS_QUERY"
    except RuntimeError as error:
        probe_error = str(error)
    found_qids = set().union(*resources.values()) if resources else set()
    coverage = [
        {
            "qid": qid,
            "status": (
                "FOUND_IN_FULL_EVENTKG_ARCHIVE"
                if full_scan and qid in found_qids
                else (
                    "ABSENT_FROM_FULL_EVENTKG_EVENT_ENTITY_SCAN"
                    if full_scan
                    else (
                        "FOUND_IN_SAVED_EVENTKG"
                        if qid in found_qids
                        else (
                            "ABSENT_FROM_COMPLETED_SAVED_SCOPE_SCAN"
                            if qid in prior_scope
                            else "OUTSIDE_SAVED_EVENTKG_FILTER_NOT_CHECKED"
                        )
                    )
                )
            ),
            "within_prior_filter_scope": qid in prior_scope,
        }
        for qid in sorted(qids, key=lambda x: int(x[1:]))
    ]
    export_frame(pd.DataFrame(coverage), output / "eventkg_qid_coverage.parquet")
    stats = {
        "corpus_qids": len(qids),
        "corpus_qids_inside_completed_filter_scope": len(qids & prior_scope),
        "corpus_qids_outside_filter_scope": len(qids - prior_scope),
        "matched_eventkg_resources": len(resources),
        "saved_source_assertions": len(rows),
        "coverage_statuses": pd.DataFrame(coverage).status.value_counts().to_dict(),
        "endpoint_probe": probe_error,
        "eventkg_release": "3.2",
        "complete_corpus_coverage": full_scan or not bool(qids - prior_scope),
        "full_official_archive_scanned": full_scan,
    }
    for name in ["graphs.ttl", "schema.ttl", "void.ttl"]:
        path = EVENTKG / "metadata" / name
        source_files.append({"path": str(path.resolve()), "sha256": sha256(path)})
    save_json(output / "eventkg_saved_scan_manifests.json", manifests)
    save_json(output / "eventkg_source_files.json", source_files)
    save_json(output / "eventkg_collection_summary.json", stats)
    return stats


def build_a(output: Path) -> dict[str, Any]:
    links = pd.read_parquet(output / "wiki_link_occurrences.parquet")
    mapping = pd.read_parquet(output / "title_qid_mapping.parquet")
    selected = read_json(output / "wikidata_corpus_metadata.json.gz")
    associations = links.merge(
        mapping[["target_title", "qid", "status"]],
        on="target_title",
        validate="many_to_one",
    )
    presence = associations.dropna(subset=["qid"])[
        ["qid", "wiki_page_id", "wiki_revision_id"]
    ].drop_duplicates()
    title_fallback = (
        associations.dropna(subset=["qid"])
        .groupby("qid")
        .target_title.first()
        .to_dict()
    )
    native = []
    qid_audit = []
    for qid in sorted(set(presence.qid)):
        entity = selected.get(qid, {})
        name = entity.get("label") or title_fallback[qid]
        qid_audit.append(
            {
                "qid": qid,
                "name": name,
                "status": (
                    "TYPED" if entity.get("direct_types") else "MISSING_NATIVE_P31"
                ),
                "name_source": (
                    "WIKIDATA_EN_LABEL" if entity.get("label") else "WIKI_TARGET_TITLE"
                ),
                "metadata_source": entity.get("reference_source"),
                "wikidata_revision": entity.get("revision"),
                "wikidata_modified": entity.get("modified"),
            }
        )
        for direct_type in entity.get("direct_types", []):
            native.append(
                {
                    "qid": qid,
                    "name": name,
                    "type": WD + direct_type,
                    "type_label": selected.get(direct_type, {}).get("label")
                    or direct_type,
                    "source": "WIKIDATA",
                    "type_source_graph": "P31",
                    "resource": qid,
                }
            )
    quads = pd.read_parquet(output / "eventkg_corpus_assertions.parquet")
    resource_qids = pd.read_parquet(output / "eventkg_resource_qids.parquet")
    labels = quads.loc[quads.predicate.eq(PREF_LABEL) & quads.language.eq("en")]
    fallback_labels = quads.loc[
        quads.predicate.eq(RDFS_LABEL) & quads.language.eq("en")
    ]
    labels = pd.concat([labels, fallback_labels]).drop_duplicates(
        ["resource", "object"]
    )
    label_map = (
        labels.groupby("resource").object.agg(lambda x: sorted(set(x))).to_dict()
    )
    types = quads.loc[quads.predicate.eq(RDF_TYPE) & quads.object_kind.eq("uri")]
    resource_types = types.merge(resource_qids, on="resource", validate="many_to_many")
    for row in resource_types.itertuples(index=False):
        for name in label_map.get(row.resource, [title_fallback[row.qid]]):
            type_id = row.object.rsplit("/", 1)[-1]
            native.append(
                {
                    "qid": row.qid,
                    "name": name,
                    "type": row.object,
                    "type_label": selected.get(type_id, {}).get("label") or type_id,
                    "source": "EVENTKG",
                    "type_source_graph": row.source_graph,
                    "resource": row.resource,
                }
            )
    metadata = pd.DataFrame(native).drop_duplicates()
    rows = presence.merge(metadata, on="qid", validate="many_to_many")
    # Multiple source types and names stay distinct; QID never replaces name/type identity.
    nodes, pages, revisions = memberships(rows)
    extras = metadata.groupby(["name", "type"]).agg(
        qids=("qid", lambda x: sorted(set(x))),
        sources=("source", lambda x: sorted(set(x))),
        type_labels=("type_label", lambda x: sorted(set(x))),
        resources=("resource", lambda x: sorted(set(x))),
    )
    nodes = nodes.merge(
        extras.reset_index(), on=["name", "type"], validate="one_to_one"
    )
    out = output / "graph_a"
    export_frame(nodes, out / "nodes.parquet")
    export_frame(pages, out / "node_page_presence.parquet")
    export_frame(revisions, out / "node_revision_presence.parquet")
    export_frame(metadata, out / "native_entity_types.parquet")
    export_frame(pd.DataFrame(qid_audit), out / "qid_type_audit.parquet")
    export_frame(
        associations.loc[associations.qid.isna()], out / "links_without_qid.parquet"
    )
    stats = write_edges(nodes, pages, out / "edges")
    stats.update(
        distinct_native_types=nodes.type.nunique(),
        native_type_assertions=len(metadata),
        qids_with_missing_p31=sum(
            x["status"] == "MISSING_NATIVE_P31" for x in qid_audit
        ),
        qids_with_typed_nodes=metadata.qid.nunique(),
        source_counts=metadata.groupby("source").size().to_dict(),
        eventkg_event_nodes=int(
            nodes.type.eq("http://semanticweb.cs.vu.nl/2009/11/sem/Event").sum()
        ),
        name_type_qid_collisions=int(nodes.qids.map(len).gt(1).sum()),
        eventkg_complete_corpus_coverage=read_json(
            output / "eventkg_collection_summary.json"
        )["complete_corpus_coverage"],
    )
    save_json(out / "summary.json", stats)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("stage", choices=["wikidata", "eventkg", "a"])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    functions = {"wikidata": collect_wikidata, "eventkg": collect_eventkg, "a": build_a}
    LOG.info("Finished: %s", json.dumps(functions[args.stage](args.output)))


if __name__ == "__main__":
    main()
