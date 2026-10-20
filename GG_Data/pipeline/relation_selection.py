"""Approved non-event cap: population S2T 8 and ERD 6.

Score existing Daniel identities without a graph. Select only after the complete Event
population is supplied, so no Event link can accidentally consume a capped slot.
Raw statements, matching decisions and previous outputs are never modified.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path

from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.relations import SourceException

LOG = logging.getLogger(__name__)
POLICY = "daniel-mutual-top-20-v1.0.1"
LIMIT = 20


def importance(mentions: list[dict]) -> dict[str, dict]:
    """Count original mention occurrences and distinct Daniel source pages.

    `raw.Source` is Daniel's supplied source-page title, not the separately
    retrieved bilingual page inventory. Count accepted non-DATE QIDs and all
    existing synthetic identities, once per original mention. Synthetic DATE
    errors remain Entity rows, unlike successfully normalized dates. Count no
    extra mentions for repeated types; invent no source-page identities.
    """
    seen, counts, pages = set(), Counter(), defaultdict(set)
    for row in mentions:
        mid = row["mention_id"]
        if mid in seen:
            raise SourceException(
                "Repeated original mention in importance input", mention_id=mid
            )
        seen.add(mid)
        qid = row.get("entity_id")
        synthetic = isinstance(qid, str) and qid.startswith("SYN_")
        if not synthetic and (
            row["raw"]["entity_group"] == "DATE"
            or not re.fullmatch(r"Q[1-9]\d*", qid or "")
        ):
            continue
        source = row["raw"]["Source"]
        if not isinstance(source, str) or not source.strip():
            raise SourceException(
                "Missing Daniel source page for importance", mention_id=mid
            )
        counts[qid] += 1
        pages[qid].add(source)
        if synthetic and counts[qid] > 1:
            raise SourceException(
                "Synthetic identity reused across mentions", entity_id=qid
            )
    return {
        qid: dict(
            distinct_source_pages=len(pages[qid]),
            total_mentions=count,
            score=len(pages[qid]) * count,
            source_pages=sorted(pages[qid]),
        )
        for qid, count in sorted(counts.items())
    }


def select(
    relations: list[dict],
    scores: dict[str, dict],
    included_events: set[str],
    *,
    event_population_complete: bool,
) -> tuple[list[dict], list[dict]]:
    """Keep uncapped Event links and the intersection of endpoint top-20 sets.

    S2T 8: budget base assertions, not entity pairs or generated reverse views.
    No refill after intersection. Unapproved cutoff ties stop before returning
    any selected population; all source records remain available to the caller.
    """
    if not event_population_complete:
        raise SourceException(
            "Complete Event membership required before relation selection"
        )
    incident, ids = defaultdict(list), set()
    for row in relations:
        oid = row["observation_id"]
        if oid in ids or row.get("derived") or row.get("source_edge_id"):
            raise SourceException(
                "Expected unique base assertions before selection", observation_id=oid
            )
        ids.add(oid)
        subject, target = row["subject_entity_id"], row["object_entity_id"]
        if not all(re.fullmatch(r"Q[1-9]\d*", qid or "") for qid in (subject, target)):
            raise SourceException("Expected native item endpoints", observation_id=oid)
        if included_events.intersection((subject, target)):
            continue
        for qid in {subject, target}:
            other = target if qid == subject else subject
            if other not in scores:
                raise SourceException(
                    "Missing Daniel importance input", qid=other, observation_id=oid
                )
            incident[qid].append((scores[other]["score"], oid, other))
    choices = {}
    for qid, rows in sorted(incident.items()):
        ordered = sorted(rows, key=lambda row: -row[0])
        if len(ordered) > LIMIT and ordered[LIMIT - 1][0] == ordered[LIMIT][0]:
            boundary = ordered[LIMIT][0]
            raise SourceException(
                "Unapproved importance tie at relation cutoff",
                qid=qid,
                score=boundary,
                incident_assertions=len(rows),
                tied_assertions=[
                    dict(observation_id=oid, other_qid=other)
                    for score, oid, other in ordered
                    if score == boundary
                ],
            )
        choices[qid] = {oid for _, oid, _ in ordered[:LIMIT]}
    retained, audit = [], []
    for row in relations:
        oid = row["observation_id"]
        endpoints = {row["subject_entity_id"], row["object_entity_id"]}
        exempt = bool(included_events.intersection(endpoints))
        decisions = (
            {qid: oid in choices[qid] for qid in sorted(endpoints)}
            if not exempt
            else {}
        )
        keep = exempt or all(decisions.values())
        audit.append(
            dict(
                observation_id=oid,
                retained=keep,
                event_exempt=exempt,
                endpoint_selections=decisions,
            )
        )
        if keep:
            retained.append(row)
    # Reverse views are generated later (graph S2T); they never spend a slot.
    degrees = Counter(
        qid
        for row in retained
        if not included_events.intersection(
            (row["subject_entity_id"], row["object_entity_id"])
        )
        for qid in {row["subject_entity_id"], row["object_entity_id"]}
    )
    if any(count > LIMIT for count in degrees.values()):
        raise AssertionError("Mutual selection exceeded its endpoint budget")
    return retained, audit


def attach_importance(
    entities: list[dict], scores: dict[str, dict], population_sha256: str
) -> list[dict]:
    """ERD 1 / population S2T 6: persist the approved identity-level score.

    Separate typed rows retain their identities and share their QID's score.
    Synthetic identities use their own mention/page counts, independent of
    Wikidata matching. Each per-mention synthetic ID therefore scores 1.
    """
    result, seen, qids = [], set(), set()
    for row in entities:
        qid = row["entity_id"]
        key = (qid, row["type"])
        if key in seen:
            raise SourceException("Repeated Entity identity", entity_id=qid)
        seen.add(key)
        if "importance" in row or "importance_basis" in row["attributes"]:
            raise SourceException("Entity importance already supplied", entity_id=qid)
        qids.add(qid)
        if qid not in scores:
            raise SourceException("Entity importance missing", entity_id=qid)
        score = scores[qid]
        basis = dict(
            policy=POLICY,
            population_sha256=population_sha256,
            status="SCORED",
            distinct_source_pages=score["distinct_source_pages"],
            total_mentions=score["total_mentions"],
        )
        result.append(
            {
                **row,
                "importance": score["score"],
                "attributes": {**row["attributes"], "importance_basis": basis},
            }
        )
    if qids != set(scores):
        raise SourceException("Entity and importance populations differ")
    return result


def prepare(mentions: Path, output: Path, entities_source: Path | None = None) -> dict:
    """Prepare verified frozen POC scores, optionally saved on Entity rows.

    This is scoring only: it does not classify Events or select Relations. A
    later caller must supply verified complete Event membership to `select`.
    """
    if output.exists() or not output.resolve().is_relative_to(
        ROOT / "GG_Data/pipeline/outputs"
    ):
        raise ValueError("Use a new directory under the approved D: pipeline outputs")
    manifest = read_json(mentions.parent / "manifest.json")
    if manifest["outputs"].get(mentions.name) != digest(mentions):
        raise SourceException("Frozen mention input checksum differs")
    scores = importance(read_json(mentions))
    entities = None
    if entities_source is not None:
        entity_manifest_path = entities_source / "manifest.json"
        entity_manifest = read_json(entity_manifest_path)
        if entity_manifest["status"] != "ENTITIES_STEP_ONLY" or entity_manifest[
            "step1_manifest"
        ]["sha256"] != digest(mentions.parent / "manifest.json"):
            raise SourceException("Entities and importance input lineage differs")
        for name, sha256 in entity_manifest["outputs"].items():
            if digest(entities_source / name) != sha256:
                raise SourceException("Entities input checksum differs", file=name)
        entities = attach_importance(
            read_json(entities_source / "entities.json.gz"),
            scores,
            digest(mentions),
        )
    output.mkdir(parents=True, exist_ok=False)
    destination = output / "entity_importance.json.gz"
    with gzip.open(destination, "wt", encoding="utf-8") as stream:
        json.dump(scores, stream, ensure_ascii=False)
    if read_json(destination) != scores:
        raise ValueError("Importance output readback differs")
    report = dict(
        status="IMPORTANCE_ONLY_EVENTS_PENDING",
        policy=POLICY,
        input=dict(
            file=str(mentions),
            sha256=digest(mentions),
            manifest_sha256=digest(mentions.parent / "manifest.json"),
        ),
        source_page_basis="Original raw.Source values supplied by Daniel",
        qids_scored=sum(qid.startswith("Q") for qid in scores),
        synthetic_ids_scored=sum(qid.startswith("SYN_") for qid in scores),
        mentions_scored=sum(row["total_mentions"] for row in scores.values()),
        matched_non_date_mentions=sum(
            row["total_mentions"] for qid, row in scores.items() if qid.startswith("Q")
        ),
        code_sha256=digest(Path(__file__)),
        outputs={destination.name: digest(destination)},
        capped_relations_written=0,
        event_population_complete=False,
    )
    if entities is not None:
        entity_file = output / "entities.json.gz"
        with gzip.open(entity_file, "wt", encoding="utf-8") as stream:
            json.dump(entities, stream, ensure_ascii=False, allow_nan=False)
        if read_json(entity_file) != entities:
            raise ValueError("Entities importance output readback differs")
        report.update(
            status="ENTITIES_IMPORTANCE_ONLY_EVENTS_PENDING",
            entity_count=len(entities),
            scored_entity_rows=sum(r["importance"] is not None for r in entities),
            synthetic_entity_rows=sum(
                r["entity_id"].startswith("SYN_") for r in entities
            ),
            entities_input=dict(
                file=str(entity_manifest_path), sha256=digest(entity_manifest_path)
            ),
        )
        report["outputs"][entity_file.name] = digest(entity_file)
        # This is a new table version; old accepted Entities/Relations stay intact.
        (output / "manifest.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    LOG.info(
        "Prepared importance for %s Daniel identities; no Relations selected",
        len(scores),
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mentions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--entities", type=Path, help="Accepted Entities directory")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    prepare(args.mentions, args.output, args.entities)
