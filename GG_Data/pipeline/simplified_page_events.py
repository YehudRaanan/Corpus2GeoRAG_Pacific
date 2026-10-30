"""Source-page Event enrichment for the simplified exact-name/type model."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import time
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from GG_Data.entity_resolution.hundred_page_pilot.collect_entities import (
    WD,
    WIKI,
    EvidenceClient,
    metadata_row,
    raw_links,
    title_response,
)
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.simplified_agent import (
    entity_id,
    native_graph,
    write_array,
    write_object,
)

LOG = logging.getLogger(__name__)


def content_links(raw: str) -> list[dict]:
    """Classify literal links using the existing article-source-v3 policy."""
    from GG_Data.entity_resolution.hundred_page_pilot.filter_source_content import (
        classify_span,
        source_intervals,
    )

    spans, headings = source_intervals(raw)
    return [
        dict(
            link,
            **{
                k: v
                for k, v in classify_span(
                    link["anchor_start"], link["anchor_end"], spans, headings
                ).items()
                if k != "evidence"
            },
        )
        for link in raw_links(raw)
    ]


def merge_population(entities, memberships, pages, extra):
    """Keep all source keys, but count a resolved physical page only once."""
    canonical = {}
    source_pages = {}
    for page in sorted(pages, key=lambda p: p["page_index"]):
        index, wiki_id = page["page_index"], page["wiki_page_id"]
        if index in source_pages or not isinstance(wiki_id, int) or wiki_id <= 0:
            raise ValueError("Invalid resolved page scope")
        canonical.setdefault(wiki_id, index)
        source_pages[index] = canonical[wiki_id]
    all_entities = {}
    for row in entities + extra["entities"]:
        key = row["entity_id"]
        if key in all_entities:
            raise ValueError("Duplicate exact entity identity")
        all_entities[key] = dict(row, page_count=0)
    pairs = set()
    for row in memberships + extra["memberships"]:
        if (
            row["entity_id"] not in all_entities
            or row["page_index"] not in source_pages
        ):
            raise ValueError("Membership endpoint outside scope")
        pairs.add((row["entity_id"], source_pages[row["page_index"]]))
    ordered = sorted(all_entities.values(), key=lambda r: (r["type"], r["name"]))
    indices = {r["entity_id"]: i for i, r in enumerate(ordered)}
    combined = []
    for key, index in sorted(pairs):
        all_entities[key]["page_count"] += 1
        combined.append(dict(entity_id=key, node_index=indices[key], page_index=index))
    for row in ordered:
        row["node_index"] = indices[row["entity_id"]]
        if not row["page_count"]:
            raise ValueError("Entity without page membership")
    return dict(
        entities=ordered,
        memberships=combined,
        wiki_pages=[
            dict(p, canonical_page_index=source_pages[p["page_index"]]) for p in pages
        ],
    )


def assemble(
    prepared: Path, pages_dir: Path, links_dir: Path, hierarchy: Path, output: Path
):
    """Publish a new immutable population, retaining all raw mention rows."""
    from GG_Data.pipeline.post_qid_events import _occurrence_types

    if output.exists():
        raise FileExistsError(output)
    manifests = {}
    for folder in [prepared, pages_dir, links_dir]:
        manifests[folder] = read_json(folder / "manifest.json")
        for name, sha in manifests[folder]["outputs"].items():
            if digest(folder / name) != sha:
                raise ValueError(f"Input artifact changed: {folder / name}")
    if manifests[links_dir]["source_pages_sha256"] != digest(
        pages_dir / "page_sources.json.gz"
    ):
        raise ValueError("Link metadata belongs to a different source scope")
    approval_sha = digest(hierarchy / "recognition_approval.json")
    event_types, rule = _occurrence_types(hierarchy, approval_sha)
    pages = read_json(pages_dir / "page_sources.json.gz")
    original_pages = read_json(prepared / "wiki_pages.json.gz")
    if {(p["page_index"], p["source_key"]) for p in pages} != {
        (p["page_index"], p["source_key"]) for p in original_pages
    }:
        raise ValueError("Source population changed")
    extra = event_population(
        pages,
        {
            r["target_title"]: r.get("qid")
            for r in read_json(links_dir / "title_mapping.json.gz")
        },
        read_json(links_dir / "native_metadata.json"),
        event_types,
    )
    population = merge_population(
        read_json(prepared / "entities.json.gz"),
        read_json(prepared / "memberships.json.gz"),
        pages,
        extra,
    )
    if shutil.disk_usage(output.parent).free < 15 * 1024**3:
        raise OSError("Insufficient disk reserve")
    output.mkdir()
    for name, rows in population.items():
        write_array(output / f"{name}.json.gz", rows)
    write_array(
        output / "geography.json.gz",
        (
            dict(
                place_id=r["entity_id"],
                name=r["name"],
                status="PENDING_LAST_STAGE",
                geometry=None,
            )
            for r in population["entities"]
            if r["type"] == "LOC"
        ),
    )
    for name in ["events", "recognition_audit", "memberships"]:
        write_array(output / f"event_{name}.json.gz", extra[name])
    native_graph().export_frame(
        pd.DataFrame(population["memberships"])[["node_index", "page_index"]],
        output / "memberships.parquet",
    )
    shutil.copyfile(prepared / "mentions.json.gz", output / "mentions.json.gz")
    scope = [
        [p["source_key"], p["wiki_page_id"], p["canonical_page_index"]]
        for p in population["wiki_pages"]
    ]
    result = dict(
        manifests[prepared],
        stage="PAGE_EVENTS_ADDED",
        page_scope_id=hashlib.sha256(
            json.dumps(scope, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest(),
        page_scope_basis="DISTINCT_RESOLVED_WIKIPEDIA_PAGE_IDS_WITH_ORIGINAL_SOURCE_KEYS",
        event_rule=[dict(path=str(p.resolve()), sha256=digest(p)) for p in rule],
        event_approval_sha256=approval_sha,
        source_manifests={
            str(p.resolve()): digest(p / "manifest.json") for p in manifests
        },
        counts=dict(
            manifests[prepared]["counts"],
            entities=len(population["entities"]),
            pages=len({p["wiki_page_id"] for p in pages}),
            source_keys=len(pages),
            events=len(extra["entities"]),
            memberships=len(population["memberships"]),
        ),
        outputs={p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()},
    )
    write_object(output / "manifest.json", result)
    return result


class PageEvidenceClient(EvidenceClient):
    def __init__(
        self,
        *args,
        retry_disconnected=False,
        retry_rate_limited=False,
        min_interval=1.0,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.retry_disconnected = retry_disconnected
        self.retry_rate_limited = retry_rate_limited
        self.min_interval = min_interval
        self.next_request = 0.0

    def _once(self, endpoint, params):
        merged = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
        key = hashlib.sha256(
            json.dumps([endpoint, merged], sort_keys=True).encode()
        ).hexdigest()
        started = self.directory / f"{key}.started.json"
        completed = self.directory / f"{key}.json.gz"
        if (
            started.exists() or started.with_name(started.name + ".part").exists()
        ) and not completed.exists():
            raise RuntimeError(f"INCOMPLETE_REQUEST_REQUIRES_REVIEW: {started}")
        original_get = self.session.get

        def paced_get(*args, **kwargs):
            pause = max(0.0, self.next_request - time.monotonic())
            if pause:
                time.sleep(pause)
            write_object(
                started,
                dict(
                    status="STARTED",
                    endpoint=endpoint,
                    params=merged,
                    started_utc=datetime.now(timezone.utc).isoformat(),
                ),
            )
            response = original_get(*args, **kwargs)
            self.next_request = time.monotonic() + self.min_interval
            if response.status_code == 429:
                path = self.directory / f"{key}.rate_limit.json"
                if not path.exists():
                    write_object(
                        path,
                        dict(
                            retry_after=response.headers.get("Retry-After"),
                            observed_utc=datetime.now(timezone.utc).isoformat(),
                        ),
                    )
            return response

        self.session.get = paced_get
        try:
            return super().query(endpoint, params)
        finally:
            self.session.get = original_get

    def query(self, endpoint, params):
        try:
            return self._once(endpoint, params)
        except RuntimeError as error:
            original = self.directory
            if self.retry_disconnected and "RemoteDisconnected" in str(error):
                retry_folder = "disconnected_retry_1"
            elif self.retry_rate_limited and "429 Client Error" in str(error):
                merged = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
                key = hashlib.sha256(
                    json.dumps([endpoint, merged], sort_keys=True).encode()
                ).hexdigest()
                receipt = read_json(original / f"{key}.json.gz")
                observed = datetime.fromisoformat(receipt["retrieved_utc"]).timestamp()
                wait_until = observed + 300
                sidecar = original / f"{key}.rate_limit.json"
                after = (
                    read_json(sidecar).get("retry_after") if sidecar.exists() else None
                )
                if after:
                    try:
                        wait_until = max(wait_until, observed + float(after))
                    except ValueError:
                        wait_until = max(
                            wait_until, parsedate_to_datetime(after).timestamp()
                        )
                if time.time() < wait_until:
                    raise RuntimeError(
                        f"RATE_LIMIT_COOLDOWN_UNTIL_UTC {datetime.fromtimestamp(wait_until, timezone.utc).isoformat()}"
                    ) from error
                retry_folder = "rate_limit_retry_1"
            else:
                raise
            self.directory = original / retry_folder
            self.directory.mkdir(exist_ok=True)
            LOG.warning(
                "One recorded retry (%s); original failure retained: %s",
                retry_folder,
                error,
            )
            try:
                return self._once(endpoint, params)
            finally:
                self.directory = original


def collect_link_metadata(
    pages_dir: Path,
    output: Path,
    metadata_path: Path,
    event_types: set[str],
    client,
    title_cache: Path | None = None,
) -> dict:
    """Resolve only explicit page titles, then recognize Events using saved P31 rules."""
    if (output / "manifest.json").exists():
        result = read_json(output / "manifest.json")
        for name, sha in result["outputs"].items():
            if digest(output / name) != sha:
                raise ValueError("Link metadata hash changed")
        return result
    page_manifest = read_json(pages_dir / "manifest.json")
    page_path = pages_dir / "page_sources.json.gz"
    if digest(page_path) != page_manifest["outputs"][page_path.name]:
        raise ValueError("Page evidence hash changed")
    pages = read_json(page_path)
    wanted_titles = {t for p in pages for t in p["links"]}
    metadata_sha = digest(metadata_path)
    records = read_json(metadata_path)
    known = defaultdict(set)
    for qid, record in records.items():
        title = record.get("sitelinks", {}).get("enwiki", {}).get("title")
        if title in wanted_titles:
            known[title].add(qid)
    reused = {}
    if title_cache is not None:
        for row in pq.read_table(title_cache).to_pylist():
            if row["target_title"] in wanted_titles and row.get("qid"):
                known[row["target_title"]].add(row["qid"])
                reused[row["target_title"]] = str(title_cache.resolve())
    mapping, pending = [], []
    for title in sorted(wanted_titles):
        qids = known.get(title, set())
        if len(qids) == 1:
            qid = next(iter(qids))
            disambiguation = (
                "Q4167410" in metadata_row(qid, records.get(qid))["native_types"]
            )
            mapping.append(
                dict(
                    target_title=title,
                    qid=None if disambiguation else qid,
                    status=(
                        "DISAMBIGUATION_TARGET"
                        if disambiguation
                        else "SAVED_EXPLICIT_PAGE_QID"
                    ),
                    metadata_evidence=reused.get(title, str(metadata_path.resolve())),
                )
            )
        else:
            pending.append(title)
    LOG.info(
        "Explicit link titles: %s cached; %s need page metadata",
        len(mapping),
        len(pending),
    )
    for start in range(0, len(pending), 50):
        batch = pending[start : start + 50]
        data, evidence, stamp = client.query(
            WIKI,
            dict(
                action="query",
                prop="pageprops",
                ppprop="wikibase_item|disambiguation",
                titles="|".join(batch),
                redirects=1,
            ),
        )
        response_pages = data.get("query", {}).get("pages", [])
        if isinstance(response_pages, dict):
            response_pages = list(response_pages.values())
        for title in batch:
            row = title_response(title, data, evidence, stamp)
            canonical = row["canonical_target_title"]
            page = next((p for p in response_pages if p.get("title") == canonical), {})
            if "disambiguation" in page.get("pageprops", {}):
                row.update(qid=None, qid_status="DISAMBIGUATION_TARGET")
            mapping.append(row)
        if start % 1000 == 0:
            LOG.info(
                "Explicit link metadata %s/%s",
                min(start + 50, len(pending)),
                len(pending),
            )
    qids = {r["qid"] for r in mapping if r.get("qid")} | {
        p["source_subject_qid"] for p in pages if p.get("source_subject_qid")
    }
    missing = sorted(qids - records.keys())
    record_evidence = {
        q: dict(file=str(metadata_path.resolve()), sha256=metadata_sha)
        for q in qids
        if q in records
    }
    for start in range(0, len(missing), 50):
        batch = missing[start : start + 50]
        data, evidence, stamp = client.query(
            WD,
            dict(
                action="wbgetentities",
                ids="|".join(batch),
                props="labels|claims|info",
                languages="en",
            ),
        )
        for qid in batch:
            record = data.get("entities", {}).get(qid)
            if record is None:
                raise ValueError(f"Missing native metadata response: {qid}; {evidence}")
            records[qid] = record
            record_evidence[qid] = dict(file=evidence, retrieved_utc=stamp)
        if start % 1000 == 0:
            LOG.info(
                "Native page-link records %s/%s",
                min(start + 50, len(missing)),
                len(missing),
            )
    event_qids = sorted(
        q
        for q in qids
        if set(metadata_row(q, records[q])["native_types"]) & event_types
    )
    missing_dates = [q for q in event_qids if "claims" not in records[q]]
    for start in range(0, len(missing_dates), 50):
        batch = missing_dates[start : start + 50]
        data, evidence, stamp = client.query(
            WD,
            dict(
                action="wbgetentities",
                ids="|".join(batch),
                props="labels|claims|info",
                languages="en",
            ),
        )
        for qid in batch:
            record = data.get("entities", {}).get(qid)
            if record is None or "missing" in record:
                raise ValueError(
                    f"Recognized Event record unavailable: {qid}; {evidence}"
                )
            records[qid] = record
            record_evidence[qid] = dict(file=evidence, retrieved_utc=stamp)
        LOG.info(
            "Event detail records %s/%s",
            min(start + 50, len(missing_dates)),
            len(missing_dates),
        )
    output.mkdir(parents=True, exist_ok=True)
    write_array(output / "title_mapping.json.gz", mapping)
    write_object(output / "native_metadata.json", {q: records[q] for q in sorted(qids)})
    write_object(output / "native_evidence.json", record_evidence)
    result = dict(
        stage="PAGE_LINK_METADATA_COLLECTED",
        source_pages_sha256=digest(page_path),
        source_metadata=dict(path=str(metadata_path.resolve()), sha256=metadata_sha),
        title_cache=(
            None
            if title_cache is None
            else dict(path=str(title_cache.resolve()), sha256=digest(title_cache))
        ),
        titles=len(mapping),
        mapped_titles=sum(bool(r.get("qid")) for r in mapping),
        unresolved_titles=sum(not r.get("qid") for r in mapping),
        native_records=len(qids),
        recognized_native_events=len(event_qids),
        outputs={p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()},
    )
    write_object(output / "manifest.json", result)
    return result


def collect_pages(prepared: Path, output: Path, metadata_path: Path, client) -> dict:
    """Fetch source revisions in fixed batches; the existing client prevents retries."""
    core = read_json(prepared / "manifest.json")
    if digest(prepared / "wiki_pages.json.gz") != core["outputs"]["wiki_pages.json.gz"]:
        raise ValueError("Prepared page hash changed")
    if (output / "manifest.json").exists():
        result = read_json(output / "manifest.json")
        for name, sha in result["outputs"].items():
            if digest(output / name) != sha:
                raise ValueError("Collected source hash changed")
        return result
    output.mkdir(parents=True, exist_ok=True)
    (output / "raw").mkdir(exist_ok=True)
    (output / "pages").mkdir(exist_ok=True)
    metadata_sha = digest(metadata_path)
    metadata = read_json(metadata_path)
    source_pages = read_json(prepared / "wiki_pages.json.gz")
    titles = {}
    title_evidence = {}
    for p in source_pages:
        key, qid = p["source_key"], p["source_subject_qid"]
        title = (
            metadata.get(qid, {}).get("sitelinks", {}).get("enwiki", {}).get("title")
            if qid
            else key
        )
        if title:
            titles[key] = title
            title_evidence[key] = (
                str(metadata_path.resolve()) if qid else "INPUT_SOURCE_TITLE"
            )
    missing = [
        p["source_subject_qid"] for p in source_pages if p["source_key"] not in titles
    ]
    for start in range(0, len(missing), 50):
        batch = missing[start : start + 50]
        data, evidence, _ = client.query(
            WD,
            dict(
                action="wbgetentities",
                ids="|".join(batch),
                props="sitelinks",
                sitefilter="enwiki",
            ),
        )
        for qid in batch:
            title = (
                data.get("entities", {})
                .get(qid, {})
                .get("sitelinks", {})
                .get("enwiki", {})
                .get("title")
            )
            if not title:
                raise ValueError(
                    f"Source QID has no enwiki page: {qid}; evidence: {evidence}"
                )
            titles[qid], title_evidence[qid] = title, evidence
        LOG.info(
            "Source title acquisition %s/%s",
            min(start + 50, len(missing)),
            len(missing),
        )
    del metadata
    collected = []
    for start in range(0, len(source_pages), 20):
        batch = source_pages[start : start + 20]
        params = dict(
            action="query",
            titles="|".join(dict.fromkeys(titles[p["source_key"]] for p in batch)),
            prop="revisions|pageprops",
            rvprop="ids|timestamp|content",
            rvslots="main",
            redirects=1,
        )
        data, evidence, stamp = client.query(WIKI, params)
        response_pages = data.get("query", {}).get("pages", [])
        if isinstance(response_pages, dict):
            response_pages = list(response_pages.values())
        by_title = {p["title"]: p for p in response_pages}
        for p in batch:
            title = titles[p["source_key"]]
            resolution = title_response(title, data, evidence, stamp)
            page = by_title.get(resolution["canonical_target_title"], {})
            revisions = page.get("revisions", [])
            if len(revisions) != 1 or page.get("ns") != 0:
                raise ValueError(
                    f"Source revision unavailable: {p['source_key']}; evidence: {evidence}"
                )
            revision = revisions[0]
            raw = revision.get("slots", {}).get("main", {}).get("content")
            if not isinstance(raw, str) or not isinstance(revision.get("revid"), int):
                raise ValueError(
                    f"Source revision content unavailable: {p['source_key']}"
                )
            raw_path = output / "raw" / f"page-{p['page_index']:05d}.txt"
            if raw_path.exists():
                if raw_path.read_bytes() != raw.encode("utf-8"):
                    raise ValueError("Saved raw revision changed")
            else:
                raw_path.write_bytes(raw.encode("utf-8"))
            links = sorted(
                {
                    r["target_title"]
                    for r in raw_links(raw)
                    if r["target_title"].split(":", 1)[0].lower()
                    not in native_graph().NAMESPACES
                }
            )
            row = dict(
                p,
                title=page["title"],
                wiki_page_id=page["pageid"],
                revision_id=revision["revid"],
                revision_timestamp=revision.get("timestamp"),
                revision_basis="RETRIEVED_REVISION_NOT_DANIEL_EXACT_REVISION",
                status="AVAILABLE",
                source_subject_qid=resolution["qid"] or p["source_subject_qid"],
                input_subject_qid=p["source_subject_qid"],
                title_mapping_evidence=title_evidence[p["source_key"]],
                evidence=evidence,
                retrieved_utc=stamp,
                raw_path=str(raw_path.resolve()),
                raw_sha256=digest(raw_path),
                links=links,
            )
            row_path = output / "pages" / f"page-{p['page_index']:05d}.json"
            if row_path.exists():
                if read_json(row_path) != row:
                    raise ValueError("Saved page evidence changed")
            else:
                write_object(row_path, row)
            collected.append(row)
        LOG.info("Source revisions %s/%s", len(collected), len(source_pages))
    write_array(output / "page_sources.json.gz", collected)
    result = dict(
        stage="SOURCE_PAGES_COLLECTED",
        page_scope_id=core["page_scope_id"],
        available_pages=len(collected),
        expected_pages=len(source_pages),
        unique_link_titles=len({t for p in collected for t in p["links"]}),
        source_metadata=dict(path=str(metadata_path.resolve()), sha256=metadata_sha),
        outputs={"page_sources.json.gz": digest(output / "page_sources.json.gz")},
    )
    write_object(output / "manifest.json", result)
    return result


def event_population(
    pages: list[dict],
    mapping: dict,
    records: dict,
    event_types: set[str],
    *,
    native_identity: bool = False,
    decisions: dict | None = None,
) -> dict:
    """Recognize only page subjects/direct links, without native neighbour gates."""
    if len({p["page_index"] for p in pages}) != len(pages):
        raise ValueError("Duplicate source page")
    entities, events, audit = {}, {}, []
    presence = defaultdict(list)
    for page in pages:
        if page["status"] != "AVAILABLE":
            raise ValueError(f"Unavailable source page: {page['page_index']}")
        if not isinstance(page.get("revision_id"), int) or page["revision_id"] <= 0:
            raise ValueError("Missing source revision")
        candidates = defaultdict(set)
        if page.get("source_subject_qid"):
            candidates[page["source_subject_qid"]].add("SOURCE_PAGE_SUBJECT")
        for title in page["links"]:
            if mapping.get(title):
                candidates[mapping[title]].add("SOURCE_PAGE_DIRECT_LINK")
        for qid, methods in sorted(candidates.items()):
            record = records.get(qid)
            meta = metadata_row(qid, record)
            matched = sorted(set(meta["native_types"]) & event_types)
            status = (
                "UNKNOWN_METADATA_MISSING"
                if meta["metadata_status"] != "AVAILABLE"
                else (
                    "EVENT"
                    if matched
                    else "NON_EVENT" if meta["native_types"] else "UNKNOWN_NO_P31"
                )
            )
            decision = decisions.get(qid) if decisions is not None else None
            if decision is not None:
                status = decision["status"]
                matched = decision.get("recognized_types", matched)
            audit.append(
                dict(
                    page_index=page["page_index"],
                    revision_id=page["revision_id"],
                    qid=qid,
                    status=status,
                    recognized_types=matched,
                    methods=sorted(methods),
                    evidence=page["evidence"],
                    **({"decision": decision} if decision is not None else {}),
                )
            )
            if status != "EVENT":
                continue
            name = meta["label"] or qid
            if native_identity:
                from GG_Data.pipeline.simplified_correction import native_event_id

                key = native_event_id(qid)
            else:
                key = entity_id(name, "event")
            if key not in entities:
                entities[key] = dict(
                    entity_id=key,
                    name=name,
                    type="event",
                    native_ids=[],
                    page_count=0,
                    mention_count=0,
                    name_status=(
                        "ENGLISH_LABEL" if meta["label"] else "NATIVE_ID_FALLBACK"
                    ),
                )
                events[key] = dict(event_id=key, entity_id=key, native_records=[])
            if qid not in entities[key]["native_ids"]:
                entities[key]["native_ids"].append(qid)
                events[key]["native_records"].append(
                    dict(
                        qid=qid,
                        metadata=record,
                        recognized_types=matched,
                        temporal_status=(
                            "NATIVE_CLAIMS" if "claims" in record else "NOT_CACHED"
                        ),
                    )
                )
            presence[(key, page["page_index"])].append(
                dict(
                    qid=qid,
                    methods=sorted(methods),
                    revision_id=page["revision_id"],
                    evidence=page["evidence"],
                )
            )
    memberships = []
    for (key, page_index), sources in sorted(presence.items()):
        entities[key]["page_count"] += 1
        memberships.append(
            dict(
                entity_id=key,
                page_index=page_index,
                presence_method="SOURCE_PAGE_EVENT",
                evidence=sources,
            )
        )
    for entity in entities.values():
        entity["native_ids"].sort()
    return dict(
        entities=list(entities.values()),
        events=list(events.values()),
        memberships=memberships,
        recognition_audit=audit,
    )


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("stage", choices=["collect-pages", "collect-links", "assemble"])
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--pages", type=Path)
    parser.add_argument("--links", type=Path)
    parser.add_argument("--hierarchy", type=Path)
    parser.add_argument("--title-cache", type=Path)
    parser.add_argument("--max-seconds", type=int, default=480)
    parser.add_argument("--max-requests", type=int, default=1000)
    parser.add_argument("--retry-disconnected", action="store_true")
    parser.add_argument("--retry-rate-limited", action="store_true")
    parser.add_argument("--min-interval", type=float, default=1.0)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if args.stage == "assemble":
        if any(x is None for x in [args.pages, args.links, args.hierarchy]):
            parser.error("assemble requires --pages, --links and --hierarchy")
        LOG.info(
            "Finished: %s",
            assemble(
                args.prepared, args.pages, args.links, args.hierarchy, args.output
            )["counts"],
        )
        return
    if args.metadata is None:
        parser.error("collection requires --metadata")
    client = PageEvidenceClient(
        args.output / "requests",
        True,
        args.max_requests,
        time.monotonic() + args.max_seconds,
        retry_disconnected=args.retry_disconnected,
        retry_rate_limited=args.retry_rate_limited,
        min_interval=args.min_interval,
    )
    if args.stage == "collect-pages":
        result = collect_pages(args.prepared, args.output, args.metadata, client)
    else:
        from GG_Data.pipeline.post_qid_events import _occurrence_types

        if args.hierarchy is None:
            parser.error("collect-links requires --hierarchy")
        event_types, _ = _occurrence_types(
            args.hierarchy, digest(args.hierarchy / "recognition_approval.json")
        )
        result = collect_link_metadata(
            args.prepared,
            args.output,
            args.metadata,
            event_types,
            client,
            args.title_cache,
        )
    LOG.info("Finished: %s", result)


if __name__ == "__main__":
    main()
