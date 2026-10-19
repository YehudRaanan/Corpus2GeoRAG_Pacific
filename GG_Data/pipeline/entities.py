"""POC step 2: populate Entities from preserved mentions and native Wikidata.

Contract: population S2T sections 2, 6 and 10; ERD section 1. No matching,
extraction or type inference. Exceptions stop before any model output is written.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

import ijson

from GG_Data.pipeline.poc import ROOT, digest, read_json

LOG = logging.getLogger(__name__)
ARCHIVE_SHA256 = "95c6a8aa5ab803d904a0f5e85bfc5d2dade97b5b5f18c0c33ea48a54fc217277"
# S2T 6, user approval 20 October: retain these older English labels despite
# their absence in the newer full record. Other such cases still need approval.
APPROVED_OLDER_ENGLISH = {
    "Q132537": ("Robert Oppenheimer", 2380462137, 2555601950),
    "Q1771928": ("Why We Fight", 2286990634, 2506639226),
}


def native_record(envelope: dict, qid: str) -> dict:
    """A missing/redirected ID needs a decision, never an automatic reassignment."""
    entity = envelope["entity"]
    if envelope["requested_qid"] != qid or entity.get("id") != qid:
        raise ValueError(f"Full reference ID differs: {qid}: {entity.get('id')}")
    if "missing" in entity or "claims" not in entity:
        raise ValueError(f"Full Wikidata record unavailable: {qid}")
    return entity


def choose_name(qid: str, full: dict, matching: dict, mentions: list[dict]) -> dict:
    """S2T 6: EN -> JA -> Daniel; approved newer revision wins label conflicts."""
    for language in ("en", "ja"):
        native = full.get("labels", {}).get(language, {}).get("value")
        prior = matching.get("labels", {}).get(language)
        candidates = [
            (native, full.get("lastrevid"), "full_record"),
            (prior, matching.get("revision"), "matching_reference"),
        ]
        approved_older_english = (
            language == "en"
            and not native
            and qid in APPROVED_OLDER_ENGLISH
            and (prior, matching.get("revision"), full.get("lastrevid"))
            == APPROVED_OLDER_ENGLISH[qid]
        )
        for value, revision, source in candidates:
            for other_value, other_revision, other_source in candidates:
                if (
                    value
                    and not other_value
                    and type(revision) is int
                    and type(other_revision) is int
                    and other_revision > revision
                    and not approved_older_english
                ):
                    raise ValueError(
                        f"Newer reference lacks {language} label: {qid}; "
                        f"{source}={value!r} at {revision}; "
                        f"{other_source} at {other_revision}; discuss language/version priority"
                    )
        candidates = [c for c in candidates if c[0]]
        if not candidates:
            continue
        if len(candidates) == 2 and native != prior:
            revisions = [c[1] for c in candidates]
            if (
                any(type(r) is not int for r in revisions)
                or revisions[0] == revisions[1]
            ):
                raise ValueError(
                    f"Cannot order conflicting name revisions: {qid}: {candidates}"
                )
            candidates.sort(key=lambda c: c[1], reverse=True)
        value, revision, source = candidates[0]
        selection = dict(
            value=value, language=language, source=source, revision=revision
        )
        if approved_older_english:
            selection["approval"] = "2026-10-20_KEEP_OLDER_ENGLISH"
        return selection
    names = sorted({m["raw"]["word"] for m in mentions})
    if len(names) != 1:
        raise ValueError(f"Conflicting Daniel fallback names: {qid}: {names}")
    return dict(value=names[0], language=None, source="Daniel", revision=None)


def full_records(qids: set[str], archive: Path) -> tuple[dict, dict]:
    """Reuse only requested QIDs; cached candidates never expand Entities (S2T 2)."""
    if digest(archive) != ARCHIVE_SHA256:
        raise ValueError("Full Wikidata archive differs from the inspected source")
    records, provenance = {}, {}
    with gzip.open(archive, "rt", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            envelope = json.loads(line)
            qid = envelope["requested_qid"]
            if qid not in qids:
                continue
            if qid in records:
                raise ValueError(f"Duplicate full record: {qid}")
            native_record(envelope, qid)
            records[qid] = envelope
            provenance[qid] = dict(
                provider="WIKIDATA",
                file=str(archive),
                sha256=ARCHIVE_SHA256,
                line=number,
                record_id=qid,
            )
    return records, provenance


def acquire_missing(qids: set[str], store: Path, reference: dict) -> tuple[dict, dict]:
    """S2T 1/T02: full `item`, not the legacy P31/P279-only projection.

    Reuse the existing CLI, query cache, pinned snapshot, dry run, billing cap
    and result-count check. The legacy scripts use sibling imports, so this
    narrow adapter temporarily exposes their directory; no matcher is called.
    """
    if not qids:
        return {}, {}
    if any(not re.fullmatch(r"Q[1-9]\d*", q) for q in qids):
        raise ValueError("Invalid requested QID")
    store.mkdir(parents=True, exist_ok=True)
    snapshot_path = store / "table_snapshot.json"
    snapshot = reference["table_snapshot"]
    if snapshot_path.exists():
        if read_json(snapshot_path) != snapshot:
            raise ValueError("Full-record query cache snapshot differs")
    else:
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    sys.path.insert(0, str(ROOT / "GG_Data/entity_resolution"))
    try:
        from bigquery_direct_wikidata import BigQueryData
    finally:
        sys.path.pop(0)
    client = BigQueryData(reference["project"], store)
    numbers = ",".join(q[1:] for q in sorted(qids))
    sql = f"SELECT id, item FROM {client.source} WHERE numeric_id IN ({numbers}) AND STARTS_WITH(id,'Q')"
    rows = client.query(sql)  # No retry, alternative provider or snapshot fallback.
    query_file = store / (digest_sql(sql) + ".json.gz")
    source = dict(
        provider="BIGQUERY",
        file=str(query_file),
        sha256=digest(query_file),
        snapshot_at=snapshot["snapshot_at"],
        request=client.requests[-1],
    )
    records, provenance = {}, {}
    for row in rows:
        qid = row["id"]
        if qid not in qids or qid in records:
            raise ValueError(f"Unexpected/duplicate BigQuery QID: {qid}")
        # Same dump terminator handling as the existing SQL projection. The
        # untouched `item` string also remains in the cached query result.
        envelope = {
            "requested_qid": qid,
            "entity": json.loads(row["item"].rstrip(",\n\r ")),
        }
        native_record(envelope, qid)
        records[qid] = envelope
        provenance[qid] = {**source, "record_id": qid}
    missing = sorted(qids - records.keys())
    if missing:
        raise ValueError(f"BigQuery full records missing ({len(missing)}): {missing}")
    return records, provenance


def digest_sql(sql: str) -> str:
    import hashlib

    return hashlib.sha256(sql.encode()).hexdigest()


def populate(
    mentions: list[dict], records: dict, metadata: dict, provenance: dict
) -> list[dict]:
    """One row per existing ID/type; normalized dates do not produce Entities."""
    groups = defaultdict(list)
    by_qid = defaultdict(list)
    for mention in mentions:
        if mention["entity_id"] is not None:
            groups[mention["entity_id"], mention["entity_type"]].append(mention)
            by_qid[mention["entity_id"]].append(mention)
    result = []
    for (qid, typ), group in sorted(groups.items()):
        synthetic = qid.startswith("SYN_")
        if synthetic and len(group) != 1:
            raise ValueError(f"Synthetic identity reused: {qid}")
        matching = {} if synthetic else metadata[qid]
        full = {} if synthetic else native_record(records[qid], qid)
        name = choose_name(qid, full, matching, by_qid[qid])
        details = []
        for language, value in full.get("labels", {}).items():
            details.append(
                dict(
                    label=value["value"],
                    kind="label",
                    provider="WIKIDATA",
                    record_id=qid,
                    language=language,
                )
            )
        for language, aliases in full.get("aliases", {}).items():
            for alias in aliases:
                details.append(
                    dict(
                        label=alias["value"],
                        kind="alias",
                        provider="WIKIDATA",
                        record_id=qid,
                        language=language,
                    )
                )
        # Compact aliases merge labels, aliases and sitelink titles. Their lost
        # kind/language cannot be reconstructed; keep that limitation explicit.
        for value in matching.get("aliases", []):
            details.append(
                dict(
                    label=value,
                    kind="matching_reference_name",
                    provider="WIKIDATA",
                    record_id=qid,
                    language=None,
                )
            )
        for mention in group:
            details.append(
                dict(
                    label=mention["raw"]["word"],
                    kind="mention",
                    provider="Daniel",
                    record_id=mention["mention_id"],
                    language=None,
                )
            )
        result.append(
            dict(
                entity_id=qid,
                type=typ,
                name=name["value"],
                labels=full.get("labels", {}),
                descriptions=full.get("descriptions", {}),
                aliases=sorted({d["label"] for d in details}),
                alias_details=details,
                identity_status="SYNTHETIC_UNRESOLVED" if synthetic else "QID_MATCHED",
                review_status="NOT_REVIEWED",
                sources=[] if synthetic else [provenance[qid]],
                text=None,
                embedding=None,
                attributes={
                    "name_selection": name,
                    "mention_ids": [m["mention_id"] for m in group],
                    "type_evidence_revision": matching.get("revision"),
                    "supplied_property_claims": {
                        p: full["claims"][p]
                        for p in ("P17", "P879", "P729", "P730")
                        if p in full.get("claims", {})
                    },
                },
                direct_types=matching.get("direct_types", []),
                parents=matching.get("parents", []),
                sitelinks=full.get("sitelinks", {}),
                revision=full.get("lastrevid"),
                modified=full.get("modified"),
                missing=None if synthetic else False,
                reference_source="Daniel" if synthetic else provenance[qid]["provider"],
                raw_reference={"mention_id": group[0]["mention_id"]}
                if synthetic
                else {"full": records[qid], "matching": matching},
            )
        )
    if {(r["entity_id"], r["type"]) for r in result} != set(groups):
        raise ValueError("Entities population differs from existing mention identities")
    return result


def run(step1: Path, cache: Path, archive: Path, store: Path, output: Path) -> None:
    # D: output is approved. Keep the completed first step immutable; a new
    # manifest marks this step only after every source and entity check passes.
    for path in (store, output):
        if path.resolve().drive.upper() != "D:" or not path.resolve().is_relative_to(
            ROOT
        ):
            raise ValueError("Use the approved D: project for cache and outputs")
    if output.exists():
        raise ValueError("Use a new Entities output directory")
    manifest_path = step1 / "manifest.json"
    manifest = read_json(manifest_path)
    if manifest["status"] != "STEP_1_ONLY":
        raise ValueError("Expected the completed first-step manifest")
    for file, sha in manifest["outputs"].items():
        if digest(step1 / file) != sha:
            raise ValueError(f"Step 1 hash differs: {file}")
    mentions = read_json(step1 / "mentions.json.gz")
    pages = read_json(step1 / "wiki_pages.json.gz")
    qids = {m["entity_id"] for m in mentions if (m["entity_id"] or "").startswith("Q")}
    saved_manifest = read_json(cache / "manifest.json")
    if digest(cache / "manifest.json") != manifest["resolution_run_id"]:
        raise ValueError("Matching manifest differs from Step 1")
    for file in ("entity_metadata.json.gz", "reference_manifest.json"):
        if digest(cache / file) != saved_manifest["outputs"][file]:
            raise ValueError(f"Matching source hash differs: {file}")
    with gzip.open(cache / "entity_metadata.json.gz", "rb") as stream:
        metadata = {
            q: m for q, m in ijson.kvitems(stream, "", use_float=True) if q in qids
        }
    if metadata.keys() != qids:
        raise ValueError("Saved matching metadata is incomplete")
    records, provenance = full_records(qids, archive)
    reused_count = len(records)
    LOG.info(
        "Full records reused=%d; BigQuery acquisition needed=%d",
        reused_count,
        len(qids - records.keys()),
    )
    acquired, sources = acquire_missing(
        qids - records.keys(), store, read_json(cache / "reference_manifest.json")
    )
    records.update(acquired)
    provenance.update(sources)
    entities = populate(mentions, records, metadata, provenance)
    for page in pages:
        page["about_entity_id"] = (
            page["wikidata_qid"] if page["wikidata_qid"] in qids else None
        )
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in (("entities", entities), ("wiki_pages", pages)):
        with gzip.open(output / f"{name}.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(rows, stream, ensure_ascii=False, allow_nan=False)
    completion = dict(
        status="ENTITIES_STEP_ONLY",
        step1_manifest=dict(file=str(manifest_path), sha256=digest(manifest_path)),
        entity_count=len(entities),
        qid_count=len(qids),
        reused_full_records=reused_count,
        acquired_full_records=len(acquired),
        pending_stages=["Events", "Relations", "Geography", "graph", "Agent"],
        outputs={p.name: digest(p) for p in output.glob("*.json.gz")},
    )
    (output / "manifest.json").write_text(
        json.dumps(completion, indent=2), encoding="utf-8"
    )
    LOG.info(
        "Entities complete: %d rows; remaining pipeline stages pending", len(entities)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--step1", type=Path, default=ROOT / "GG_Data/pipeline/outputs/poc_10k"
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path.home()
        / ".cache/geoai_full_daniel_dump_bigquery_parallel_20261019",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=ROOT / "Data/external/wwii_task_force/wikidata_entities.jsonl.gz",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=ROOT / "GG_Data/pipeline/outputs/wikidata_full_cache",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.step1, args.cache, args.archive, args.store, args.output)


if __name__ == "__main__":
    main()
