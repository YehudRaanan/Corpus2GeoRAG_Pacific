"""Recover linked QID candidates from saved revisions, never mention assignments.

This separate stage reads the unresolved audit and original collection. It adds
flat Ship-template targets and retries failed article links in a new directory.
Historical raw evidence and current title/QID metadata remain separate.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from GG_Data.entity_resolution.attach_source_page_ids import (
    read_json,
    save_json,
    sha256,
)
from GG_Data.entity_resolution.hundred_page_pilot.collect_entities import (
    DATA,
    PROTECTED,
    WD,
    WIKI,
    EvidenceClient,
    metadata_row,
    title_response,
    utc_now,
    validate_revision,
    write_table,
)

LOG = logging.getLogger(__name__)
SHIP = re.compile(r"\{\{\s*ship\s*\|([^{}]*)\}\}", re.I)
RULE = "https://en.wikipedia.org/wiki/Template:Ship/doc#Basic_usage"


def template_targets(text: str) -> list[dict[str, Any]]:
    """Read flat Ship parameters only; unsupported syntax is never guessed.

    The fourth parameter changes display, not the title or its year. This is a
    source-parameter reconstruction using documented rules, not a historical
    snapshot of the transcluded template implementation.
    """
    masked = PROTECTED.sub(lambda match: " " * len(match.group()), text)
    rows = []
    for match in SHIP.finditer(masked):
        parts = [part.strip() for part in match[1].split("|")]
        positional, options = [], {}
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                options[key.strip().lower()] = value.strip()
            else:
                positional.append(part)
        status = "SUPPORTED_DOCUMENTED_SHIP_TARGET"
        if any(key not in {"wl", "up"} for key in options) or len(positional) > 4:
            status = "REVIEW_UNSUPPORTED_PARAMETERS"
        elif options.get("wl", "").lower() in {"no", "n", "false", "0"}:
            status = "UNLINKED_TEMPLATE"
        elif options.get("wl", "").lower() not in {"", "yes"} or options.get(
            "up", ""
        ).lower() not in {"", "yes", "no"}:
            status = "REVIEW_UNSUPPORTED_PARAMETERS"
        title = None
        if status == "SUPPORTED_DOCUMENTED_SHIP_TARGET":
            prefix, name, identifier, _display = (positional + [""] * 4)[:4]
            title = " ".join(part for part in (prefix, name) if part)
            if identifier:
                title += f" ({identifier})"
            if _display not in {"", "1", "2", "3", "5", "6"}:
                status, title = "REVIEW_UNSUPPORTED_DISPLAY", None
            elif not name or any(char in title for char in "[]<>#:"):
                status, title = "REVIEW_UNSUPPORTED_TARGET", None
        rows.append(
            dict(
                target_title=title,
                raw_start=match.start(),
                raw_end=match.end(),
                raw_text=text[match.start() : match.end()],
                link_origin="RAW_SHIP_TEMPLATE",
                template_status=status,
                target_rule=RULE,
                target_rule_temporal_basis="DOCUMENTED_RULE_NOT_HISTORICAL_TEMPLATE_SNAPSHOT",
            )
        )
    return rows


def checked_title(title: str, data: dict, path: str, retrieved: str) -> dict:
    """Use the collector resolver, adding the requested disambiguation guard."""
    result = title_response(title, data, path, retrieved)
    result["verified_qid"] = result.get("qid")
    pages = data.get("query", {}).get("pages", [])
    if isinstance(pages, dict):
        pages = list(pages.values())
    page = next(
        (p for p in pages if p.get("title") == result["canonical_target_title"]), {}
    )
    result["disambiguation_checked"] = True
    if "disambiguation" in page.get("pageprops", {}):
        result.update(qid=None, qid_status="DISAMBIGUATION_PAGE_REVIEW")
    query = data.get("query", {})
    redirects = {row["from"]: row for row in query.get("redirects", [])}
    aliases = {
        row["from"]: row["to"]
        for key in ("normalized", "redirects", "converted")
        for row in query.get(key, [])
    }
    chain, seen, current = [], set(), title
    while current in aliases and current not in seen:
        seen.add(current)
        if current in redirects:
            chain.append(redirects[current])
        current = aliases[current]
    result["redirect_chain"] = chain
    # A section target identifies an entry within an article, not that article.
    if any("tofragment" in redirect for redirect in result["redirect_chain"]):
        result.update(qid=None, qid_status="SECTION_REDIRECT_REVIEW")
    source_year = re.search(r"\((\d{4})\)$", title)
    target_year = re.search(r"\((\d{4})\)$", result["canonical_target_title"])
    if source_year and target_year and source_year[1] != target_year[1]:
        result.update(qid=None, qid_status="IDENTIFIER_YEAR_CHANGED_REVIEW")
    return result


def verify_hashes(hashes: dict[str, str]) -> None:
    changed = [name for name, digest in hashes.items() if sha256(Path(name)) != digest]
    if changed:
        raise ValueError(f"Protected inputs changed: {changed}")


def checked_metadata(qid: str, entity: dict) -> dict:
    """Reject missing/invalid stubs and responses for a different identity."""
    valid = (
        entity.get("id") == qid
        and not {"missing", "invalid"} & entity.keys()
        and {"labels", "claims"} <= entity.keys()
    )
    return metadata_row(qid, entity if valid else None)


def recover(
    base: Path,
    output: Path,
    allow_api: bool,
    max_requests: int = 20,
    request_cache: Path | None = None,
) -> dict:
    started, start = utc_now(), time.monotonic()
    # A new directory prevents accidental replacement of any previous run.
    output.mkdir(parents=True, exist_ok=False)
    audit, collection = base / "audit_deep_20261029", base / "collection_v2"
    protected = read_json(base / "audit_20261029/results_final/summary.json")[
        "input_sha256"
    ]
    for path in [
        audit / "final/unresolved_mentions.csv",
        audit / "final/review_groups.jsonl",
        collection / "entities.parquet",
        collection / "wiki_link_occurrences.parquet",
        collection / "collection_revisions.parquet",
        collection / "title_qid_mapping.parquet",
        collection / "native_metadata.parquet",
        base / "selected_mentions.parquet",
    ]:
        protected[str(path.resolve())] = sha256(path)
    verify_hashes(protected)
    with (audit / "final/unresolved_mentions.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        cases = list(csv.DictReader(stream))
    scopes = {(int(r["page_id"]), int(r["revision_id"])) for r in cases}
    if len(cases) != 369 or scopes != {
        (781032, 1379821139),
        (23680822, 1375594940),
        (29607850, 1323366204),
    }:
        raise ValueError(
            "This approved pilot requires 369 unresolved rows / 3 revisions"
        )
    revisions = [
        r
        for r in pq.read_table(collection / "collection_revisions.parquet").to_pylist()
        if (r["page_id"], r["revision_id"]) in scopes
    ]
    if {(r["page_id"], r["revision_id"]) for r in revisions} != scopes:
        raise ValueError("Missing exact source revision")
    source, targets = {}, []
    for revision in revisions:
        raw = validate_revision(revision)
        scope = revision["page_id"], revision["revision_id"]
        source[scope] = raw
        for row in template_targets(raw):
            row.update(
                page_id=scope[0],
                revision_id=scope[1],
                wiki_title=revision["wiki_title"],
                revision_timestamp=revision["revision_timestamp"],
                raw_evidence_path=revision["wikitext_path"],
                raw_sha256=revision["sha256"],
                revision_binding_evidence=revision["evidence_path"],
            )
            targets.append(row)
    failed_nonarticles = 0
    for link in pq.read_table(collection / "wiki_link_occurrences.parquet").to_pylist():
        scope = link["page_id"], link["revision_id"]
        if scope not in scopes or link.get("qid"):
            continue
        if ":" in link["target_title"]:
            failed_nonarticles += 1
            continue
        link.update(
            raw_text=source[scope][link["raw_start"] : link["raw_end"]],
            template_status="FAILED_ORDINARY_ARTICLE_LOOKUP",
            previous_lookup_evidence=link.get("mapping_evidence"),
        )
        targets.append(link)

    cached = {
        r["target_title"]: r
        for r in pq.read_table(collection / "title_qid_mapping.parquet").to_pylist()
    }
    for filename in (
        "current_template_title_lookup.json",
        "current_template_title_followup.json",
    ):
        path = audit / "misc" / filename
        saved = read_json(path)
        protected[str(path.resolve())] = sha256(path)
        for title in saved["query_titles"]:
            cached[title] = title_response(
                title, saved["response"], str(path.resolve()), saved["retrieval_utc"]
            )
    titles = sorted({r["target_title"] for r in targets if r.get("target_title")})
    client = EvidenceClient(
        request_cache or output / "requests",
        allow_api,
        max_requests,
        time.monotonic() + 300,
    )
    mapping = {}
    # Cache first; one explicit current check also requests the pageprops absent
    # from the saved responses. Failed lookups are new recorded attempts, not retries.
    for offset in range(0, len(titles), 50):
        batch = titles[offset : offset + 50]
        try:
            data, evidence, retrieved = client.query(
                WIKI,
                dict(
                    action="query",
                    prop="pageprops",
                    ppprop="wikibase_item|disambiguation",
                    redirects=1,
                    titles="|".join(batch),
                ),
            )
            for title in batch:
                result = checked_title(title, data, evidence, retrieved)
                previous = cached.get(title, {})
                result["cached_mapping_evidence"] = previous.get("mapping_evidence")
                result["cached_qid"] = previous.get("qid")
                if (
                    previous.get("qid")
                    and result.get("qid")
                    and previous["qid"] != result["qid"]
                ):
                    result.update(qid=None, qid_status="QID_CHANGED_SINCE_CACHE_REVIEW")
                mapping[title] = result
        except RuntimeError as error:
            client.failures.append(dict(titles=batch, error=str(error)))
            for title in batch:
                mapping[title] = {
                    **cached.get(title, {}),
                    "target_title": title,
                    "qid": None,
                    "qid_status": "CURRENT_CHECK_UNAVAILABLE_REVIEW",
                }

    native_schema = pq.read_schema(collection / "native_metadata.parquet")
    native = {
        r["qid"]: r
        for r in pq.read_table(collection / "native_metadata.parquet").to_pylist()
    }
    # A replay can reuse saved full API records even when the requested QID
    # subset changed after review. Never issue a new call just to split a batch.
    if request_cache is not None:
        for path in request_cache.glob("*.json.gz"):
            saved = read_json(path)
            protected[str(path.resolve())] = sha256(path)
            if saved.get("endpoint") != WD or not saved.get("ok"):
                continue
            for qid, entity in (
                json.loads(saved["response_text"]).get("entities", {}).items()
            ):
                row = checked_metadata(qid, entity)
                row.update(
                    metadata_source="WIKIDATA_API",
                    metadata_path=str(path.resolve()),
                    metadata_retrieval_utc=saved["retrieved_utc"],
                    metadata_snapshot_utc=saved["retrieved_utc"],
                )
                if row["metadata_status"] == "AVAILABLE":
                    native[qid] = row
    needed = sorted(
        {r["qid"] for r in mapping.values() if r.get("qid")} - native.keys()
    )
    for offset in range(0, len(needed), 50):
        batch = needed[offset : offset + 50]
        try:
            data, evidence, retrieved = client.query(
                WD,
                dict(
                    action="wbgetentities",
                    ids="|".join(batch),
                    props="labels|aliases|descriptions|claims|info",
                    languages="en",
                ),
            )
            for qid in batch:
                entity = data.get("entities", {}).get(qid, {})
                row = checked_metadata(qid, entity)
                row.update(
                    metadata_source="WIKIDATA_API",
                    metadata_path=evidence,
                    metadata_retrieval_utc=retrieved,
                    metadata_snapshot_utc=retrieved,
                )
                native[qid] = row
        except RuntimeError as error:
            client.failures.append(dict(qids=batch, error=str(error)))

    all_entities = pq.read_table(collection / "entities.parquet")
    original = [
        r
        for r in all_entities.to_pylist()
        if (r["page_id"], r["revision_id"]) in scopes
    ]
    existing = {(r["page_id"], r["revision_id"], r["qid"]): r for r in original}
    added, accepted = {}, []
    for target in targets:
        result = mapping.get(target.get("target_title"), {})
        target.update(result)
        qid = result.get("qid")
        info = native.get(qid, {})
        usable = bool(
            qid
            and info.get("metadata_status") == "AVAILABLE"
            and "Q4167410" not in info.get("native_types", [])
        )
        target["recovery_status"] = (
            "SUPPORTED_CURRENT_QID_CANDIDATE" if usable else "REVIEW_OR_NO_QID"
        )
        target["mapping_evidence_sha256"] = (
            sha256(Path(result["mapping_evidence"]))
            if result.get("mapping_evidence")
            else None
        )
        if not usable:
            continue
        accepted.append(target)
        key = target["page_id"], target["revision_id"], qid
        target["already_in_page_inventory"] = key in existing
        if key in existing:
            continue
        if key not in added:
            added[key] = {
                **info,
                "page_id": key[0],
                "revision_id": key[1],
                "revision_timestamp": target["revision_timestamp"],
                "wiki_title": target["wiki_title"],
                "link_origin": [],
                "link_evidence": [],
                "linked_titles": [],
                "raw_link_occurrences": 0,
                "collection_status": "RECOVERED_SOURCE_TARGET_CURRENT_MAPPING",
                "unlinked_entity_coverage": "NOT_ENUMERATED",
                "rendered_expansion_coverage": "SOURCE_PARAMETERS_ONLY_NO_CURRENT_NAVIGATION_EXPANSION",
            }
        row = added[key]
        for column, value in [
            ("link_origin", target["link_origin"]),
            ("link_evidence", target["raw_evidence_path"]),
            ("linked_titles", target["target_title"]),
        ]:
            row[column] = sorted(set(row[column]) | {value})
        row["raw_link_occurrences"] += int(target["link_origin"] == "RAW_DIRECT_LINK")

    selected = {
        r["source_row_index"]: r
        for r in pq.read_table(base / "selected_mentions.parquet").to_pylist()
    }
    groups = {
        r["group_id"]: r
        for r in (
            json.loads(line)
            for line in (audit / "final/review_groups.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    }
    for case in cases:
        scope = int(case["page_id"]), int(case["revision_id"])
        mention = selected[int(case["source_row_index"])]
        page_new = sorted(key[2] for key in added if key[:2] == scope)
        overlap = set()
        for target in accepted:
            if case["type"] == "DATE":
                continue
            if (target["page_id"], target["revision_id"]) != scope or target[
                "qid"
            ] not in page_new:
                continue
            # Offsets are in Daniel's passage, not in the full raw revision.
            # Literal enclosure is source support, never an identity assignment.
            for found in re.finditer(re.escape(target["raw_text"]), mention["Text"]):
                if found.start() < mention["end"] and mention["start"] < found.end():
                    overlap.add(target["qid"])
        hypotheses = {
            r["qid"] for r in groups[case["group_id"]].get("proposed_qids", [])
        }
        newly_supported = (
            hypotheses & set(page_new) if case["type"] != "DATE" else set()
        )
        if case["type"] == "DATE":
            case_status = "DATE_OUTSIDE_QID_RECOVERY"
        elif overlap:
            case_status = "NEW_SOURCE_ENCLOSURE_CANDIDATE"
        elif newly_supported:
            case_status = "AUDIT_HYPOTHESIS_NEWLY_AVAILABLE"
        else:
            case_status = "NO_CASE_SPECIFIC_NEW_SUPPORT"
        case.update(
            new_page_candidate_qids=page_new,
            new_source_enclosure_candidate_qids=sorted(overlap),
            audit_hypotheses_newly_available=sorted(newly_supported),
            assignment_changed=False,
            recovery_case_status=case_status,
        )

    merged = [*original, *added.values()]
    keys = [(r["page_id"], r["revision_id"], r["qid"]) for r in merged]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate page/revision/QID inventory rows")
    verify_hashes(protected)
    write_table(targets, output / "target_evidence.parquet")
    write_table(
        list(added.values()), output / "added_entities.parquet", all_entities.schema
    )
    write_table(merged, output / "entities.parquet", all_entities.schema)
    used_qids = sorted({r["qid"] for r in added.values()})
    write_table(
        [native[qid] for qid in used_qids],
        output / "native_metadata.parquet",
        native_schema,
    )
    write_table(cases, output / "unresolved_case_report.parquet")
    with (output / "unresolved_case_report.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cases[0]))
        writer.writeheader()
        writer.writerows(
            {
                k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v
                for k, v in row.items()
            }
            for row in cases
        )
    summary = dict(
        status="COMPLETE_CANDIDATE_RECOVERY_NOT_MENTION_RESOLUTION",
        started_utc=started,
        completed_utc=utc_now(),
        elapsed_seconds=time.monotonic() - start,
        active_work_seconds=None,
        approval_wait_seconds=None,
        environment_wait_seconds=None,
        page_revisions=len(scopes),
        unresolved_mentions=len(cases),
        unresolved_groups=len(groups),
        template_occurrences=sum(
            r["link_origin"] == "RAW_SHIP_TEMPLATE" for r in targets
        ),
        failed_article_links=sum(
            r["link_origin"] == "RAW_DIRECT_LINK" for r in targets
        ),
        nonarticle_null_links_excluded=failed_nonarticles,
        target_titles=len(titles),
        target_statuses=dict(Counter(r["recovery_status"] for r in targets)),
        lookup_statuses=dict(
            Counter(r.get("qid_status", "NO_TARGET") for r in targets)
        ),
        original_entity_page_revision_rows=len(original),
        added_entity_page_revision_rows=len(added),
        added_distinct_qids=len(used_qids),
        merged_entity_page_revision_rows=len(merged),
        case_statuses=dict(Counter(r["recovery_case_status"] for r in cases)),
        source_enclosure_is_identity_gold=False,
        assignment_changes=0,
        inference_runs=0,
        new_paid_cost_usd=0,
        api_requests=client.requests,
        request_cache=str(client.directory.resolve()),
        script_sha256=sha256(Path(__file__)),
        failures=client.failures,
        protected_input_hashes=protected,
        protected_input_hashes_unchanged=True,
        unsupported_template_families="All except flat Ship; parameterless IJN is navigation",
        issues=[
            "Yugiri spelling and Yura ship-type repair not applied",
            "Asagumo source year 1938 redirects to 1937; excluded pending review",
            "Current mappings are not historical identity gold",
            "Dates and unlinked names not recovered",
        ],
        output_sha256={p.name: sha256(p) for p in output.glob("*.parquet")},
    )
    save_json(output / "summary.json", summary)
    LOG.info(
        "Recovery: %s added entity-page rows; %s cases; %s API requests",
        len(added),
        len(cases),
        client.requests,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DATA)
    parser.add_argument("--output", type=Path, default=DATA / "qid_recovery_20261029")
    parser.add_argument("--allow-api", action="store_true")
    parser.add_argument("--max-api-requests", type=int, default=20)
    parser.add_argument("--request-cache", type=Path)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    recover(
        args.base,
        args.output,
        args.allow_api,
        args.max_api_requests,
        args.request_cache,
    )


if __name__ == "__main__":
    main()
