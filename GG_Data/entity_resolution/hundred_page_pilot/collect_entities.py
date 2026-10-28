"""Collect direct raw-revision links and current/cached Wikidata metadata.

Inputs are revision-pinned raw files from prepare_pages and existing local caches.
Outputs keep link occurrences, unresolved titles and native metadata separate. Raw
links in every source section are retained. Contemporary template expansions are
not added without source-section evidence; unlinked mentions are outside scope.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pyarrow as pa
import pyarrow.parquet as pq
import requests

from GG_Data.entity_resolution.attach_source_page_ids import read_json, save_json, sha256
from GG_Data.entity_resolution.hundred_page_pilot.prepare_pages import raw_revision_rows

LOG = logging.getLogger(__name__)
DATA = Path("Data/external/hundred_page_pilot_20261028")
OLD = Path("D:/Projects/GeoAI-source-page-ids-20261026/Data/external/native_corpus_graphs_20261028")
BQ = Path.home() / ".cache/geoai_bigquery_20261018"
WIKI = "https://en.wikipedia.org/w/api.php"
WD = "https://www.wikidata.org/w/api.php"
USER_AGENT = "Corpus2GeoRAG-Pacific-pilot/0.1 (https://github.com/EtzionR/Corpus2GeoRAG_Pacific)"
PROTECTED = re.compile(r"<!--[\s\S]*?(?:-->|$)|<(?:nowiki|pre|source|syntaxhighlight|math)\b[^>]*/\s*>|<(nowiki|pre|source|syntaxhighlight|math)\b[^>]*>[\s\S]*?(?:</\1\s*>|$)", re.I)
LINK = re.compile(r"\[\[([^\[\]]+)\]\]")
HEADING = re.compile(r"^={1,6}\s*(.*?)\s*={1,6}\s*$", re.M)


def raw_links(text: str) -> list[dict[str, Any]]:
    """Enumerate literal wikilinks, without stripping references or templates."""
    masked = PROTECTED.sub(lambda match: " " * len(match.group()), text)
    headings = [(match.start(), match.group(1)) for match in HEADING.finditer(masked)]
    result = []
    heading_index, section = 0, "Lead"
    for match in LINK.finditer(masked):
        while heading_index < len(headings) and headings[heading_index][0] < match.start():
            section = headings[heading_index][1]
            heading_index += 1
        target, pipe, anchor = match.group(1).partition("|")
        # Wikipedia title spaces/underscores and escaped category/file links.
        title = html.unescape(unquote(target.strip().lstrip(":"))).split("#", 1)[0].replace("_", " ").strip()
        if not title:
            continue  # Same-page fragment; page-own QID is collected separately.
        result.append({
            "target_title": title, "anchor_text": anchor if pipe else target,
            "anchor_start": match.start() + 2 + (len(target) + 1 if pipe else 0),
            "anchor_end": match.end() - 2,
            "raw_start": match.start(), "raw_end": match.end(),
            "section_heading": section, "link_origin": "RAW_DIRECT_LINK",
            "source_scope": "ALL_RAW_SOURCE_SECTIONS",
        })
    return result


def metadata_row(qid: str, entity: dict[str, Any] | None) -> dict[str, Any]:
    entity = entity or {}
    raw = "claims" in entity or isinstance(entity.get("labels", {}).get("en"), dict)
    if raw:
        label = entity.get("labels", {}).get("en", {}).get("value")
        aliases = [item["value"] for item in entity.get("aliases", {}).get("en", [])]
        description = entity.get("descriptions", {}).get("en", {}).get("value")
        native_types = sorted({
            claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            for claim in entity.get("claims", {}).get("P31", [])
            if claim.get("rank") != "deprecated"
            and isinstance(claim.get("mainsnak", {}).get("datavalue", {}).get("value"), dict)
            and claim["mainsnak"]["datavalue"]["value"].get("id")
        })
    else:
        label, aliases = entity.get("label"), entity.get("aliases", [])
        description = entity.get("description")
        native_types = entity.get("direct_types", [])
    missing = not entity or ("missing" in entity if raw else bool(entity.get("missing", False)))
    return {
        "qid": qid, "label": label, "aliases": aliases,
        "description": description, "native_types": native_types,
        "metadata_status": "MISSING_METADATA" if missing else "AVAILABLE",
        "label_status": "AVAILABLE" if label else "NO_ENGLISH_LABEL",
        "aliases_status": "ENGLISH_API" if raw else "ENGLISH_BIGQUERY" if entity.get("aliases_language") == "en" else "CACHED_MERGED_LANGUAGES" if "aliases" in entity else "NOT_CACHED",
        "description_status": "AVAILABLE" if description else "NO_ENGLISH_DESCRIPTION" if raw or entity.get("metadata_fields_complete") else "NOT_CACHED",
        "p31_status": "UNKNOWN_METADATA_MISSING" if missing else "AVAILABLE" if native_types else "NO_P31",
        "metadata_revision": entity.get("lastrevid", entity.get("revision")),
        "metadata_modified": entity.get("modified"),
        "metadata_snapshot_utc": entity.get("metadata_snapshot_utc"),
        "metadata_temporal_basis": "CURRENT_OR_CACHED_WIKIDATA_NOT_HISTORICAL_WIKIPEDIA",
    }


def validate_revision(revision: dict[str, Any]) -> str:
    path = Path(revision["wikitext_path"])
    if sha256(path) != revision["sha256"]:
        raise ValueError(f"Raw revision hash mismatch: {path}")
    if int(revision["page_id"]) <= 0 or int(revision["revision_id"]) <= 0:
        raise ValueError("Positive page and revision IDs required")
    text = path.read_bytes().decode("utf-8")
    evidence = Path(revision["evidence_path"])
    source_rows = raw_revision_rows(read_json(evidence), evidence)
    if not any(row["page_id"] == revision["page_id"] and row["revision_id"] == revision["revision_id"] and row["raw"] == text for row in source_rows):
        raise ValueError(f"Source evidence does not bind raw text to page/revision: {evidence}")
    return text


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_table(rows: list[dict[str, Any]], path: Path, schema: pa.Schema | None = None) -> None:
    if path.exists():
        raise FileExistsError(f"Preserve output: {path}")
    temporary = path.with_suffix(".parquet.tmp")
    if schema is None and rows:
        columns = list(dict.fromkeys(key for row in rows for key in row))
        rows = [{key: row.get(key) for key in columns} for row in rows]
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), temporary, compression="zstd")
    temporary.replace(path)


class EvidenceClient:
    """Bounded, cached calls; a saved failed call is never retried silently."""

    def __init__(self, directory: Path, allow_api: bool, max_requests: int, deadline: float):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.allow_api, self.max_requests, self.deadline = allow_api, max_requests, deadline
        self.requests = 0
        self.failures: list[dict[str, Any]] = []
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def query(self, endpoint: str, params: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
        params = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
        key = hashlib.sha256(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()
        path = self.directory / f"{key}.json.gz"
        if not path.exists():
            if not self.allow_api or self.requests >= self.max_requests or time.monotonic() >= self.deadline:
                raise RuntimeError("API_DISABLED_OR_REQUEST_TIME_LIMIT")
            record = {"endpoint": endpoint, "params": params, "retrieved_utc": utc_now()}
            start = time.monotonic()
            self.requests += 1
            try:
                response = self.session.get(endpoint, params=params, timeout=30)
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
        record = read_json(path)
        if not record["ok"]:
            self.failures.append({"path": str(path), "error": record.get("error")})
            raise RuntimeError(f"Saved failed request; no retry: {path}: {record.get('error')}")
        return json.loads(record["response_text"]), str(path.resolve()), record["retrieved_utc"]


def title_response(title: str, data: dict[str, Any], evidence: str, retrieval: str) -> dict[str, Any]:
    query = data.get("query", {})
    aliases = {item["from"]: item["to"] for key in ("normalized", "redirects", "converted") for item in query.get(key, [])}
    canonical, seen = title, set()
    while canonical in aliases and canonical not in seen:
        seen.add(canonical)
        canonical = aliases[canonical]
    pages = query.get("pages", [])
    if isinstance(pages, dict):
        pages = list(pages.values())
    page = next((page for page in pages if page.get("title") == canonical), {})
    qid = page.get("pageprops", {}).get("wikibase_item")
    if not page or "missing" in page or "invalid" in page:
        status, qid = "MISSING_OR_INVALID_PAGE", None
    elif page.get("ns") != 0:
        status, qid = "NON_ARTICLE_LINK", None
    elif not re.fullmatch(r"Q[1-9]\d*", qid or ""):
        status, qid = "NO_QID", None
    else:
        status = "CURRENT_EXPLICIT_WIKIPEDIA_QID"
    return {"target_title": title, "canonical_target_title": canonical, "qid": qid,
            "target_page_id": page.get("pageid"), "qid_status": status,
            "mapping_evidence": evidence, "mapping_retrieval_utc": retrieval,
            "mapping_temporal_basis": "CURRENT_OR_CACHED_TITLE_RESOLUTION"}


def collect(revisions_path: Path, output: Path, old: Path, bq: Path, allow_api: bool,
            max_requests: int, max_seconds: float, passages_path: Path | None = None,
            reuse_collection: Path | None = None, enrich_metadata: bool = True,
            metadata_enrichment: Path | None = None) -> dict[str, Any]:
    start, started = time.monotonic(), utc_now()
    output.mkdir(parents=True, exist_ok=True)
    for name in ("entities.parquet", "native_metadata.parquet", "wiki_link_occurrences.parquet"):
        if (output / name).exists():
            raise FileExistsError(f"Preserve output: {output / name}")
    client = EvidenceClient(output / "collection_requests", allow_api, max_requests, start + max_seconds)
    input_sha256 = sha256(revisions_path)
    revisions = pq.read_table(revisions_path).to_pylist()
    unused_revisions = 0
    if passages_path is not None:
        used = {(row["page_id"], row["revision_id"]) for row in pq.read_table(passages_path, columns=["page_id", "revision_id"]).to_pylist() if row["page_id"] is not None and row["revision_id"] is not None}
        unused_revisions = sum((row["page_id"], row["revision_id"]) not in used for row in revisions)
        revisions = [row for row in revisions if (row["page_id"], row["revision_id"]) in used]
    keys = [(row["page_id"], row["revision_id"]) for row in revisions]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate page/revision input")
    write_table(revisions, output / "collection_revisions.parquet", pq.read_schema(revisions_path))
    occurrences, revision_audit = [], []
    for revision in revisions:
        try:
            text = validate_revision(revision)
        except (OSError, ValueError) as error:
            revision_audit.append({**revision, "collection_status": "RAW_EVIDENCE_FAILED", "error": str(error)})
            continue
        found = raw_links(text)
        found.append({"target_title": revision["wiki_title"], "anchor_text": revision["wiki_title"],
                      "raw_start": None, "raw_end": None, "anchor_start": None, "anchor_end": None, "section_heading": None,
                      "link_origin": "PAGE_OWN_QID", "source_scope": "PAGE_IDENTITY"})
        occurrences.extend({**item, "page_id": revision["page_id"], "revision_id": revision["revision_id"],
                            "wiki_title": revision["wiki_title"], "revision_timestamp": revision["revision_timestamp"],
                            "raw_evidence_path": revision["wikitext_path"], "raw_sha256": revision["sha256"],
                            "raw_retrieval_utc": revision["retrieval_utc"]} for item in found)
        revision_audit.append({**revision, "collection_status": "RAW_DIRECT_LINKS_COLLECTED", "raw_link_occurrences": len(found) - 1})
    titles = sorted({row["target_title"] for row in occurrences})
    title_set = set(titles)
    LOG.info("%s revisions, %s occurrences, %s target titles", len(revisions), len(occurrences), len(titles))
    mapping: dict[str, dict[str, Any]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    provenance: dict[str, tuple[str, str, str]] = {}
    snapshot_path = bq / "table_snapshot.json"
    snapshot_time = read_json(snapshot_path).get("snapshot_at") if snapshot_path.exists() else None
    cache_path = bq / "entity_metadata.json.gz"
    if cache_path.exists():
        metadata = read_json(cache_path)
        for qid, entity in metadata.items():
            title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
            if title in title_set:
                if title in mapping and mapping[title]["qid"] != qid:
                    raise ValueError(f"Conflicting cached sitelinks: {title}")
                mapping[title] = {"target_title": title, "canonical_target_title": title, "qid": qid,
                                  "target_page_id": None, "qid_status": "CACHED_EXACT_ENWIKI_SITELINK",
                                  "mapping_evidence": str(cache_path.resolve()), "mapping_retrieval_utc": snapshot_time,
                                  "mapping_temporal_basis": "CACHED_CURRENT_TITLE_RESOLUTION"}
    old_mapping = old / "title_qid_mapping.parquet"
    if old_mapping.exists():
        for row in pq.read_table(old_mapping).to_pylist():
            title = row["target_title"]
            if title in title_set and title not in mapping:
                mapping[title] = {"target_title": title, "canonical_target_title": row.get("canonical_target_title") or title,
                                  "qid": row.get("qid"), "target_page_id": row.get("target_page_id"),
                                  "qid_status": row.get("status"), "mapping_evidence": row.get("metadata_evidence"),
                                  "mapping_retrieval_utc": None, "mapping_temporal_basis": "OLD_CACHE_RETRIEVAL_TIME_UNKNOWN"}
    if reuse_collection is not None:
        for row in pq.read_table(reuse_collection / "title_qid_mapping.parquet").to_pylist():
            if row["target_title"] in title_set and row.get("qid_status") != "QID_LOOKUP_UNAVAILABLE":
                mapping[row["target_title"]] = row
    pending_titles = [title for title in titles if title not in mapping]
    for offset in range(0, len(pending_titles), 50):
        batch = pending_titles[offset:offset + 50]
        try:
            data, evidence, retrieval = client.query(WIKI, {"action": "query", "prop": "pageprops", "ppprop": "wikibase_item|disambiguation", "redirects": 1, "titles": "|".join(batch)})
            mapping.update({title: title_response(title, data, evidence, retrieval) for title in batch})
        except RuntimeError as error:
            mapping.update({title: {"target_title": title, "qid": None, "qid_status": "QID_LOOKUP_UNAVAILABLE", "mapping_evidence": str(error)} for title in batch})
        if offset % 500 == 0:
            LOG.info("Title lookup %s/%s; new requests %s", min(offset + 50, len(pending_titles)), len(pending_titles), client.requests)
    own_page_qids: dict[int, str] = {}
    pages_path = passages_path.parent / "pages.json" if passages_path is not None else None
    if pages_path is not None and pages_path.exists():
        evidence_cache: dict[str, dict[str, Any]] = {}
        for context in read_json(pages_path):
            evidence_path = context["evidence_path"]
            if evidence_path not in evidence_cache:
                evidence_cache[evidence_path] = read_json(Path(evidence_path))
            record = evidence_cache[evidence_path]
            data = json.loads(record["response_text"]) if "response_text" in record else record
            candidates = data.get("query", {}).get("pages", [data])
            page = next((item for item in candidates if item.get("pageid") == context["pageid"]), {})
            qid = page.get("pageprops", {}).get("wikibase_item")
            cached_qid = mapping.get(context["title"], {}).get("qid")
            if qid and cached_qid != qid:
                raise ValueError(f"Page-own QID conflicts with page-ID evidence: {context['pageid']}: {cached_qid}/{qid}")
            if qid:
                own_page_qids[context["pageid"]] = qid
    qids = sorted({row["qid"] for row in mapping.values() if row.get("qid")})
    # Retain only selected linked entities before reading the smaller native cache.
    metadata = {qid: metadata[qid] for qid in qids if qid in metadata}
    provenance = {qid: ("BIGQUERY_LOCAL_CACHE", str(cache_path.resolve()), snapshot_time) for qid in metadata}
    native_path = old / "wikidata_corpus_metadata.json.gz"
    if native_path.exists():
        native = read_json(native_path)
        for qid in qids:
            if qid in native and qid not in metadata:
                metadata[qid] = native[qid]
                provenance[qid] = ("NATIVE_LOCAL_CACHE", str(native_path.resolve()), None)
        del native
    if reuse_collection is not None:
        saved_metadata = read_json(reuse_collection / "collection_enriched_metadata.json.gz")
        for qid in qids:
            if qid in saved_metadata:
                item = saved_metadata[qid]
                metadata[qid] = item["entity"]
                provenance[qid] = tuple(item["provenance"])
    if metadata_enrichment is not None:
        enrichment = read_json(metadata_enrichment)
        for entity in enrichment["entities"]:
            qid = entity["id"]
            if qid in qids:
                metadata[qid] = {**entity, "aliases_language": "en", "metadata_fields_complete": True,
                                 "metadata_snapshot_utc": enrichment.get("snapshot_at")}
                provenance[qid] = ("BIGQUERY_SELECTED_METADATA", str(metadata_enrichment.resolve()), enrichment["retrieved_utc"])
    pending_metadata = [qid for qid in qids if enrich_metadata and provenance.get(qid, (None,))[0] not in {"WIKIDATA_API", "BIGQUERY_SELECTED_METADATA"}]
    # Projected old caches discarded descriptions and alias language tags. Fetch
    # native current metadata for selected QIDs, retaining old data on failure.
    for offset in range(0, len(pending_metadata), 50):
        batch = pending_metadata[offset:offset + 50]
        try:
            data, evidence, retrieval = client.query(WD, {"action": "wbgetentities", "ids": "|".join(batch), "props": "labels|aliases|descriptions|claims|info", "languages": "en"})
            for qid in batch:
                entity = data.get("entities", {}).get(qid)
                if entity is not None:
                    metadata[qid] = entity
                    provenance[qid] = ("WIKIDATA_API", evidence, retrieval)
        except RuntimeError as error:
            client.failures.append({"qids": batch, "error": str(error), "fallback": "PRESERVE_LOCAL_METADATA"})
        if offset % 500 == 0:
            LOG.info("Metadata %s/%s; new requests %s", min(offset + 50, len(pending_metadata)), len(pending_metadata), client.requests)
        save_json(output / "collection_progress.json", {"utc": utc_now(), "metadata_processed": min(offset + 50, len(pending_metadata)), "total_qids": len(qids), "api_requests": client.requests})
    save_json(output / "collection_enriched_metadata.json.gz", {qid: {"entity": metadata[qid], "provenance": provenance[qid]} for qid in metadata})
    native_rows = []
    for qid in qids:
        row = metadata_row(qid, metadata.get(qid))
        source, evidence, retrieval = provenance.get(qid, ("UNAVAILABLE", None, None))
        row.update(metadata_source=source, metadata_path=evidence, metadata_retrieval_utc=retrieval)
        if source == "BIGQUERY_LOCAL_CACHE":
            row["metadata_snapshot_utc"] = snapshot_time
        native_rows.append(row)
    lookup = {row["qid"]: row for row in native_rows}
    for row in occurrences:
        row.update(mapping[row["target_title"]])
        if row["link_origin"] == "PAGE_OWN_QID":
            row["page_own_qid_page_id_verified"] = own_page_qids.get(row["page_id"]) == row.get("qid") if own_page_qids else None
    grouped: dict[tuple[int, int, str], list[dict[str, Any]]] = {}
    for row in occurrences:
        if row.get("qid"):
            grouped.setdefault((row["page_id"], row["revision_id"], row["qid"]), []).append(row)
    entities = []
    for (page_id, revision_id, qid), links in sorted(grouped.items()):
        native = lookup[qid]
        entities.append({**native, "page_id": page_id, "revision_id": revision_id,
                         "revision_timestamp": links[0]["revision_timestamp"], "wiki_title": links[0]["wiki_title"],
                         "link_origin": sorted({row["link_origin"] for row in links}),
                         "link_evidence": sorted({row["raw_evidence_path"] for row in links}),
                         "linked_titles": sorted({row["target_title"] for row in links}),
                         "raw_link_occurrences": sum(row["link_origin"] == "RAW_DIRECT_LINK" for row in links),
                         "collection_status": "COMPLETE_NATIVE_METADATA" if native["metadata_source"] in {"WIKIDATA_API", "BIGQUERY_SELECTED_METADATA"} else "CACHED_METADATA_FIELDS_MAY_BE_INCOMPLETE",
                         "unlinked_entity_coverage": "NOT_ENUMERATED",
                         "rendered_expansion_coverage": "NOT_ADDED_WITHOUT_MATCHING_SOURCE_SECTION_EVIDENCE"})
    entity_schema = pa.schema([
        ("qid", pa.string()), ("label", pa.string()), ("aliases", pa.list_(pa.string())),
        ("description", pa.string()), ("native_types", pa.list_(pa.string())),
        *[(name, pa.string()) for name in ("metadata_status", "label_status", "aliases_status", "description_status", "p31_status")],
        ("metadata_revision", pa.int64()),
        *[(name, pa.string()) for name in ("metadata_modified", "metadata_snapshot_utc", "metadata_temporal_basis", "metadata_source", "metadata_path", "metadata_retrieval_utc")],
        ("page_id", pa.int64()), ("revision_id", pa.int64()), ("revision_timestamp", pa.string()), ("wiki_title", pa.string()),
        ("link_origin", pa.list_(pa.string())), ("link_evidence", pa.list_(pa.string())), ("linked_titles", pa.list_(pa.string())),
        ("raw_link_occurrences", pa.int64()), ("collection_status", pa.string()),
        ("unlinked_entity_coverage", pa.string()), ("rendered_expansion_coverage", pa.string())])
    write_table(entities, output / "entities.parquet", entity_schema)
    write_table(native_rows, output / "native_metadata.parquet", pa.schema(list(entity_schema)[:entity_schema.get_field_index("page_id")]))
    write_table(occurrences, output / "wiki_link_occurrences.parquet")
    write_table(list(mapping.values()), output / "title_qid_mapping.parquet")
    write_table(revision_audit, output / "collection_revision_audit.parquet")
    save_json(output / "collection_failures.json", client.failures)
    summary = {"stage": "collect_entities", "owner": "collection_implementation", "start_utc": started, "end_utc": utc_now(),
               "elapsed_seconds": time.monotonic() - start, "active_work": "unknown", "approval_wait": 0,
               "environment_wait": "unknown", "gpu_seconds": 0, "bigquery_bytes": 0, "estimated_cost_usd": 0,
               "input_path": str(revisions_path.resolve()), "input_sha256": input_sha256,
               "unused_recovery_revisions_excluded": unused_revisions,
               "input_revisions": len(revisions), "revision_statuses": dict(Counter(row["collection_status"] for row in revision_audit)),
               "link_occurrences": len(occurrences), "target_titles": len(titles), "qids": len(qids), "entity_page_revision_rows": len(entities),
               "qid_statuses": dict(Counter(row.get("qid_status") for row in mapping.values())),
               "metadata_sources": dict(Counter(row["metadata_source"] for row in native_rows)),
               "missing_labels": sum(not row["label"] for row in native_rows), "missing_p31": sum(not row["native_types"] for row in native_rows),
               "missing_descriptions": sum(not row["description"] for row in native_rows), "api_requests": client.requests,
               "page_own_qids_verified_against_page_id_evidence": len(own_page_qids),
               "failures": len(client.failures), "unlinked_mentions": "NOT_ENUMERATED",
               "rendered_transclusions": "EXCLUDED_WITHOUT_SOURCE_SECTION_EVIDENCE",
               "outputs": {name: sha256(output / name) for name in ("entities.parquet", "native_metadata.parquet", "wiki_link_occurrences.parquet", "title_qid_mapping.parquet", "collection_revision_audit.parquet")}}
    save_json(output / "collection_summary.json", summary)
    with (output / "collection_runtime.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revisions", type=Path, default=DATA / "revisions.parquet")
    parser.add_argument("--passages", type=Path, default=DATA / "passages.parquet")
    parser.add_argument("--output", type=Path, default=DATA)
    parser.add_argument("--old-cache", type=Path, default=OLD)
    parser.add_argument("--bq-cache", type=Path, default=BQ)
    parser.add_argument("--allow-api", action="store_true")
    parser.add_argument("--reuse-collection", type=Path)
    parser.add_argument("--skip-metadata-api", action="store_true")
    parser.add_argument("--metadata-enrichment", type=Path)
    parser.add_argument("--max-api-requests", type=int, default=1000)
    parser.add_argument("--max-seconds", type=float, default=5400)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    summary = collect(args.revisions, args.output, args.old_cache, args.bq_cache,
                      args.allow_api, args.max_api_requests, args.max_seconds, args.passages, args.reuse_collection, not args.skip_metadata_api, args.metadata_enrichment)
    LOG.info("Collection summary: %s", json.dumps(summary, ensure_ascii=True))


def test_raw_links_keep_all_sections_and_offsets() -> None:
    text = "[[Lead]]\n== Sources ==\n<ref>[[Reference|Ref]]</ref>{{T|[[Template target]]}}\n{|\n| [[Table target]]\n|}\n<!-- [[Hidden]] --><nowiki>[[Literal]]</nowiki>"
    links = raw_links(text)
    assert [row["target_title"] for row in links] == [
        "Lead", "Reference", "Template target", "Table target"
    ]
    assert all(text[row["raw_start"]:row["raw_end"]].startswith("[[") for row in links)
    assert all(text[row["anchor_start"]:row["anchor_end"]] == row["anchor_text"] for row in links)
    assert links[1]["section_heading"] == "Sources"


def test_self_closing_protection_does_not_hide_later_links() -> None:
    for tag in ("<nowiki/>", "<nowiki />", "<NOWIKI/>", "<source/>"):
        assert [row["target_title"] for row in raw_links(f"[[Before]] {tag} [[After]]")] == ["Before", "After"]
    text = "[[Before]] <nowiki/> [[After]] <nowiki>[[Hidden]]</nowiki> [[End]]"
    assert [row["target_title"] for row in raw_links(text)] == ["Before", "After", "End"]


def test_metadata_missing_qid_and_p31_remain_explicit() -> None:
    assert metadata_row("Q1", None)["metadata_status"] == "MISSING_METADATA"
    row = metadata_row("Q2", {"label": "Example", "direct_types": []})
    assert row["native_types"] == []
    assert row["p31_status"] == "NO_P31"


def test_revision_binding_rejects_changed_raw(tmp_path: Path) -> None:
    path = tmp_path / "raw.txt"
    path.write_text("[[One]]", encoding="utf-8")
    revision = {"page_id": 1, "revision_id": 2, "wikitext_path": str(path), "sha256": "wrong"}
    try:
        validate_revision(revision)
    except ValueError:
        return
    raise AssertionError("Changed raw revision must fail")


def test_revision_binding_rejects_other_api_revision(tmp_path: Path) -> None:
    path, evidence = tmp_path / "raw.txt", tmp_path / "evidence.json"
    path.write_text("[[One]]", encoding="utf-8")
    save_json(evidence, {"ok": True, "response_text": json.dumps({"parse": {
        "pageid": 1, "revid": 999, "title": "Self", "wikitext": "[[One]]"}})})
    row = {"page_id": 1, "revision_id": 10, "wikitext_path": str(path), "sha256": sha256(path), "evidence_path": str(evidence)}
    try:
        validate_revision(row)
    except ValueError:
        return
    raise AssertionError("Another API revision must fail even with identical raw text")


def test_collection_keeps_two_revisions_and_unresolved_links(tmp_path: Path) -> None:
    bq, old, output = (tmp_path / name for name in ("bq", "old", "out"))
    bq.mkdir()
    old.mkdir()
    save_json(bq / "entity_metadata.json.gz", {
        "Q1": {"id": "Q1", "label": "One", "aliases": [], "direct_types": [], "sitelinks": {"enwiki": {"title": "One"}}},
        "Q2": {"id": "Q2", "label": "Two", "aliases": [], "direct_types": ["Q5"], "sitelinks": {"enwiki": {"title": "Two"}}},
    })
    revisions = []
    for revision_id, text in ((10, "[[One]] [[Unknown]]"), (20, "<ref>[[Two]]</ref>")):
        path = tmp_path / f"{revision_id}.txt"
        path.write_text(text, encoding="utf-8")
        evidence = tmp_path / f"{revision_id}.json"
        save_json(evidence, {"ok": True, "response_text": json.dumps({"parse": {
            "pageid": 1, "revid": revision_id, "title": "Self", "wikitext": text}})})
        revisions.append({"page_id": 1, "revision_id": revision_id, "wiki_title": "Self",
                          "revision_timestamp": "2020-01-01T00:00:00Z", "wikitext_path": str(path),
                          "sha256": sha256(path), "evidence_path": str(evidence), "retrieval_utc": "2026-10-28T00:00:00Z"})
    revisions_path = tmp_path / "revisions.parquet"
    pq.write_table(pa.Table.from_pylist(revisions), revisions_path)
    result = collect(revisions_path, output, old, bq, False, 0, 30)
    assert result["api_requests"] == 0
    entities = pq.read_table(output / "entities.parquet").to_pylist()
    assert {(row["revision_id"], row["qid"]) for row in entities} == {(10, "Q1"), (20, "Q2")}
    links = pq.read_table(output / "wiki_link_occurrences.parquet").to_pylist()
    assert any(row["target_title"] == "Unknown" and row["qid"] is None for row in links)
    assert result["missing_p31"] == 1


if __name__ == "__main__":
    main()
