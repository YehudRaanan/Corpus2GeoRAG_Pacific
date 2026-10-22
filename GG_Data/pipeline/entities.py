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


def native_record(envelope: dict, qid: str) -> dict:
    """A missing/redirected ID needs a decision, never an automatic reassignment."""
    entity = envelope["entity"]
    if envelope["requested_qid"] != qid or entity.get("id") != qid:
        raise ValueError(f"Full reference ID differs: {qid}: {entity.get('id')}")
    if "missing" in entity or "claims" not in entity:
        raise ValueError(f"Full Wikidata record unavailable: {qid}")
    return entity


def choose_name(qid: str, full: dict, matching: dict, mentions: list[dict]) -> dict:
    """S2T 1/6: EN -> JA -> Daniel from the selected whole source record.

    Latest 20 October approval supersedes cross-version name ranking and
    per-QID exceptions. Matching evidence remains frozen, not a name source.
    """
    for language in ("en", "ja"):
        value = full.get("labels", {}).get(language, {}).get("value")
        if value:
            return dict(
                value=value,
                language=language,
                source="full_record",
                revision=full.get("lastrevid"),
            )
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


def select_reference(
    qid: str, pinned: tuple[dict, dict] | None, available: list[tuple[dict, dict]]
) -> tuple[dict, dict]:
    """S2T 1: snapshot first, otherwise latest available complete same-ID record.

    Select a whole record, never combine fields or redirect a matched QID.
    Source provenance remains; no archived-versus-snapshot difference log.
    """
    if pinned is not None:
        native_record(pinned[0], qid)
        return pinned
    if not available:
        raise ValueError(f"No available Wikidata version: {qid}")
    for envelope, _ in available:
        record = native_record(envelope, qid)
        if type(record.get("lastrevid")) is not int:
            raise ValueError(f"Cannot order available Wikidata versions: {qid}")
    return max(available, key=lambda pair: pair[0]["entity"]["lastrevid"])


def acquire_missing(
    qids: set[str],
    store: Path,
    reference: dict,
    *,
    prefix: str = "Q",
    available_records: dict[str, list[tuple[dict, dict]]] | None = None,
) -> tuple[dict, dict]:
    """S2T 1/T02: full `item`, not the legacy P31/P279-only projection.

    Reuse the existing CLI, query cache, pinned snapshot, dry run, billing cap
    and result-count check. The legacy scripts use sibling imports, so this
    narrow adapter temporarily exposes their directory; no matcher is called.
    """
    if not qids:
        return {}, {}
    # Relations S2T 8, 20 October approval: P records are catalog metadata,
    # never new Entities. Reuse the same pinned query/cache path for them.
    if prefix not in {"Q", "P"} or any(
        not re.fullmatch(prefix + r"[1-9]\d*", q) for q in qids
    ):
        raise ValueError("Invalid requested Wikidata identifier")
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
    sql = f"SELECT id, item FROM {client.source} WHERE numeric_id IN ({numbers}) AND STARTS_WITH(id,'{prefix}')"
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
    if missing and available_records is not None:
        for qid in missing:
            records[qid], provenance[qid] = select_reference(
                qid, None, available_records.get(qid, [])
            )
    elif missing:
        raise ValueError(f"BigQuery full records missing ({len(missing)}): {missing}")
    return records, provenance


def digest_sql(sql: str) -> str:
    import hashlib

    return hashlib.sha256(sql.encode()).hexdigest()


def populate(
    mentions: list[dict],
    records: dict,
    metadata: dict,
    provenance: dict,
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
                raw_reference=(
                    {"mention_id": group[0]["mention_id"]}
                    if synthetic
                    else {"full": records[qid], "matching": matching}
                ),
            )
        )
    if {(r["entity_id"], r["type"]) for r in result} != set(groups):
        raise ValueError("Entities population differs from existing mention identities")
    return result


def run(
    step1: Path,
    cache: Path,
    archive: Path,
    store: Path,
    output: Path,
    *,
    available_entities: Path | None = None,
) -> None:
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
    archived, archive_sources = full_records(qids, archive)
    available = {q: [(r, archive_sources[q])] for q, r in archived.items()}
    if available_entities is not None:
        # S2T 1: reuse whole same-ID source records only. Never import saved
        # identities, aggregates or matching decisions from the older model.
        prior_manifest = read_json(available_entities / "manifest.json")
        prior_path = available_entities / "entities.json.gz"
        if digest(prior_path) != prior_manifest["outputs"][prior_path.name]:
            raise ValueError("Available source records differ from their manifest")
        for row in read_json(prior_path):
            qid = row["entity_id"]
            if qid in qids:
                available.setdefault(qid, []).append(
                    (row["raw_reference"]["full"], row["sources"][0])
                )
    reference_path = cache / "reference_manifest.json"
    reference = read_json(reference_path)
    records, provenance = acquire_missing(
        qids,
        store,
        reference,
        available_records=available,
    )
    reused_count = sum(
        source["provider"] != "BIGQUERY" for source in provenance.values()
    )
    entities = populate(mentions, records, metadata, provenance)
    from GG_Data.pipeline.relation_selection import importance

    # S2T 6/8: recompute page-count * mention-count from corrected identities;
    # each existing synthetic mention also has its own score of one.
    scores = importance(mentions)
    for row in entities:
        qid = row["entity_id"]
        row["importance"] = scores[qid]["score"]
        row["attributes"]["importance"] = scores[qid]
        source = provenance.get(qid)
        row["attributes"]["bq_availability"] = dict(
            status=(
                "NOT_APPLICABLE_SYNTHETIC"
                if qid.startswith("SYN_")
                else (
                    "PRESENT_IN_PINNED_BQ"
                    if source["provider"] == "BIGQUERY"
                    else "MISSING_IN_PINNED_BQ"
                )
            ),
            snapshot_at=reference["table_snapshot"]["snapshot_at"],
        )
    for page in pages:
        page["about_entity_id"] = (
            page["wikidata_qid"] if page["wikidata_qid"] in qids else None
        )
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in (
        ("entities", entities),
        ("wiki_pages", pages),
        ("full_records", records),
    ):
        with gzip.open(output / f"{name}.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(rows, stream, ensure_ascii=False, allow_nan=False)
    completion = dict(
        status="ENTITIES_SNAPSHOT_FIRST",
        snapshot_at=reference["table_snapshot"]["snapshot_at"],
        source_rule="AGREED_SNAPSHOT_THEN_LATEST_AVAILABLE_SAME_QID",
        provenance=provenance,
        inputs={
            str(p): digest(p)
            for p in (manifest_path, reference_path, step1 / "mentions.json.gz")
        },
        step1_manifest=dict(file=str(manifest_path), sha256=digest(manifest_path)),
        entity_count=len(entities),
        qid_count=len(qids),
        reused_full_records=reused_count,
        acquired_full_records=len(records) - reused_count,
        pending_stages=["Events", "Relations", "Geography", "graph", "Agent"],
        outputs={p.name: digest(p) for p in output.glob("*.json.gz")},
    )
    (output / "manifest.json").write_text(
        json.dumps(completion, indent=2), encoding="utf-8"
    )
    if read_json(output / "entities.json.gz") != entities:
        raise ValueError("Entity output readback differs")
    (output / "verification.json").write_text(
        json.dumps(
            dict(
                status="VERIFIED_ENTITIES_SNAPSHOT_FIRST",
                manifest_sha256=digest(output / "manifest.json"),
                original_sample_preserved=True,
                importance_recomputed=True,
                output_readback=True,
            ),
            indent=2,
        ),
        encoding="utf-8",
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
    parser.add_argument("--available-entities", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(
        args.step1,
        args.cache,
        args.archive,
        args.store,
        args.output,
        available_entities=args.available_entities,
    )


if __name__ == "__main__":
    main()
