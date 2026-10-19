"""Check the seven probe candidates; population S2T 7, not full discovery.

Use the approved saved hierarchy and cache current native candidate records.
Check native P31 evidence and, when given the frozen sample, direct links to
its distinct matched QIDs. No new Daniel entity, matching decision, model Event
row, or graph assertion is created here. Incoming full-statement materialization
belongs to population, after this eligibility check.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from GG_Data.mapping.assertion_exclusions import exclusion_reason, load_exclusions
from GG_Data.mapping.build_relation_mapping_v2_1 import read_csv
from GG_Data.pipeline import events
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.relations import SourceException

LOG = logging.getLogger(__name__)


def statement_key(sid: str) -> str:
    """Compare native/RDF spellings of one statement, never endpoint dedup."""
    return sid.rsplit("/", 1)[-1].replace("$", "-").lower()


def incoming_links(data: dict, target: str) -> list[dict]:
    """Full p/ps query rows are direct assertions, not truthy or reverse views."""
    ranks = {
        f"http://wikiba.se/ontology#{r.title()}Rank": r
        for r in ("normal", "preferred", "deprecated")
    }
    result = []
    for row in data["results"]["bindings"]:
        subject, prop, sid, rank = [
            row[key]["value"] for key in ("subject", "property", "statement", "rank")
        ]
        if (
            not re.fullmatch(r"http://www.wikidata.org/entity/Q[1-9]\d*", subject)
            or not re.fullmatch(r"http://www.wikidata.org/entity/P[1-9]\d*", prop)
            or not re.fullmatch(
                r"http://www.wikidata.org/entity/statement/[Qq][1-9]\d*-[0-9a-fA-F-]+",
                sid,
            )
            or rank not in ranks
            or statement_key(sid).split("-", 1)[0] != subject.rsplit("/", 1)[-1].lower()
        ):
            raise SourceException(
                "Unexpected incoming Event assertion", qid=target, row=row
            )
        result.append(
            dict(
                subject_qid=subject.rsplit("/", 1)[-1],
                object_qid=target,
                source_predicate="wd:" + prop.rsplit("/", 1)[-1],
                source_record_id=sid,
                rank=ranks[rank],
                raw_query_row=row,
            )
        )
    return result


def qualifying_links(
    links: list[dict], qid: str, daniel: set[str], mapping: dict
) -> tuple[list[dict], list[dict]]:
    """S2T 7/8: exact exclusions, approved mapping, one native assertion.

    The distinct-QID count is separate from assertion count. All statement ranks
    remain eligible here; the deprecated-rank filter applies to ancestry only.
    """
    exclusions = load_exclusions()
    excluded_ids = {
        statement_key(sid): sid for source, sid in exclusions if source == "Wikidata"
    }
    unique, excluded = {}, []
    for link in links:
        subject, target = link["subject_qid"], link["object_qid"]
        other = target if subject == qid else subject
        if qid not in {subject, target} or other not in daniel:
            continue
        case = dict(link)
        rank = case.get("rank") or case["raw_statement"]["rank"]
        case["rank"] = rank
        key = statement_key(case["source_record_id"])
        if key in unique:
            previous = unique[key]
            if any(
                previous[k] != case[k]
                for k in ("subject_qid", "object_qid", "source_predicate", "rank")
            ):
                raise SourceException("Conflicting Event assertion retrievals", **case)
            continue
        reason = exclusion_reason(
            "Wikidata",
            dict(
                case,
                source_record_id=excluded_ids.get(key, case["source_record_id"]),
                predicate=case["source_predicate"],
            ),
            exclusions,
        )
        if reason:
            excluded.append(dict(case, reason=reason))
            continue
        rule = mapping.get(("Wikidata", case["source_predicate"]))
        if rule is None:
            # S2T 8 approves native additions, but a mapped eligibility result
            # must wait for the corresponding versioned parameter row.
            raise SourceException(
                "Event property needs approved native catalog extension", **case
            )
        if rule["direction_to_level2"] not in {"same", "reverse"} or (
            rule["formal_component_conflict"] != "False"
            and not (
                rule["level2_relation_id"] == case["source_predicate"]
                and rule["direction_to_level2"] == "same"
                and rule["level2_decision"]
                == "RETAIN_SOURCE_ID_BLOCK_FORMAL_TRANSLATION"
            )
        ):
            raise SourceException("Conflicting Event relation mapping", **case)
        unique[key] = dict(
            case,
            daniel_qid=other,
            level2_relation_id=rule["level2_relation_id"],
            relation_map_version=rule["relation_map_version"],
        )
    return list(unique.values()), excluded


def check_links(
    report: dict, output: Path, store: Path, mentions: Path, relations: Path, save
) -> None:
    """Check both query graphs against all frozen sample QIDs, not five seeds."""
    first = read_json(mentions.parent / "manifest.json")
    if digest(mentions) != first["outputs"][mentions.name]:
        raise SourceException("Daniel sample checksum mismatch")
    daniel = {
        r["entity_id"]
        for r in read_json(mentions)
        if r["raw"]["entity_group"] != "DATE"
        and re.fullmatch(r"Q[1-9]\d*", r.get("entity_id") or "")
    }
    manifest = read_json(relations / "manifest.json")
    mapping_path = relations / "mapping/RELATION_MAPPING_TABLE_v2.1.2.csv"
    expected = manifest["mapping_artifacts"].get(str(mapping_path))
    if not expected or digest(mapping_path) != expected:
        raise SourceException("Accepted relation mapping checksum mismatch")
    rows = read_csv(mapping_path)
    mapping = {(r["source"], r["source_predicate"]): r for r in rows}
    if len(mapping) != len(rows):
        raise SourceException("Duplicate Event mapping keys")
    report.update(
        status="CHECKING_DIRECT_LINKS",
        daniel_distinct_qids=len(daniel),
        mentions_sha256=digest(mentions),
        mapping_sha256=digest(mapping_path),
        queries=[],
        eligibility=[],
    )
    save()
    candidates = [r["qid"] for r in report["records"]]
    by_candidate = {
        qid: events.item_links(read_json(output / f"{qid}.json")) for qid in candidates
    }
    ordered = sorted(daniel, key=lambda q: int(q[1:]))
    report["incoming_request_policy"] = dict(
        subject_batch_size=250,
        candidate_targets=candidates,
        expected_requests=2 * ((len(ordered) + 249) // 250),
        approval="User agreed after discussing incomplete HTTP-200 response",
    )
    save()
    for offset in range(0, len(ordered), 250):
        batch = ordered[offset : offset + 250]
        query = events.incoming_candidates_query(batch, candidates)
        (output / f"incoming_{offset//250:03d}.sparql").write_text(
            query, encoding="utf-8"
        )
        for endpoint in (events.QUERY_URL, events.SCHOLARLY_QUERY_URL):
            data, evidence = events.cached_json(
                store, endpoint, {"query": query, "format": "json"}
            )
            report["queries"].append(
                dict(
                    batch_offset=offset,
                    endpoint=endpoint,
                    source=evidence,
                    rows=len(data["results"]["bindings"]),
                )
            )
            save()
            groups = {qid: [] for qid in candidates}
            for row in data["results"]["bindings"]:
                uri = row["event"]["value"]
                qid = uri.rsplit("/", 1)[-1]
                if (
                    uri != f"http://www.wikidata.org/entity/{qid}"
                    or qid not in groups
                    or row["subject"]["value"]
                    not in {f"http://www.wikidata.org/entity/{s}" for s in batch}
                ):
                    raise SourceException("Incoming batch population differs", row=row)
                groups[qid].append(row)
            for qid, bindings in groups.items():
                by_candidate[qid].extend(
                    incoming_links({"results": {"bindings": bindings}}, qid)
                )
            LOG.info(
                "Saved incoming request %s/%s: %s rows",
                len(report["queries"]),
                report["incoming_request_policy"]["expected_requests"],
                len(data["results"]["bindings"]),
            )
    for record_info in report["records"]:
        qid = record_info["qid"]
        links = by_candidate[qid]
        retained, excluded = qualifying_links(links, qid, daniel, mapping)
        distinct = sorted({r["daniel_qid"] for r in retained}, key=lambda q: int(q[1:]))
        (output / f"{qid}_links.json").write_text(
            json.dumps(
                dict(retained=retained, excluded=excluded), ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
        report["eligibility"].append(
            dict(
                qid=qid,
                name=record_info["name"],
                distinct_daniel_qids=distinct,
                distinct_daniel_count=len(distinct),
                qualifying_statements=len(retained),
                excluded_statements=len(excluded),
                passes_two_entity_gate=len(distinct) >= 2,
            )
        )
        save()
        LOG.info(
            "Checked %s: %s distinct Daniel QIDs, %s assertions",
            qid,
            len(distinct),
            len(retained),
        )
    report["status"] = "SEVEN_CANDIDATE_ELIGIBILITY_CHECK_ONLY"
    report["full_incoming_statement_materialization"] = "PENDING_POPULATION"


def run(
    source: Path,
    output: Path,
    store: Path,
    mentions: Path | None = None,
    relations: Path | None = None,
) -> dict:
    """Approve the saved classification and inspect native candidates first.

    The immutable earlier diagnostic is evidence, not a mutable run state.
    Save after each request so any data exception stops with a visible record.
    """
    verification = read_json(source / "verification.json")
    for name, sha in verification["outputs"].items():
        if digest(source / name) != sha:
            raise SourceException("Candidate source checksum mismatch", file=name)
    classified = events.classify_events(read_json(source / "hierarchy_edges.json"))
    candidates = [row for row in classified if row["event_hierarchy_match"]]
    output.mkdir(parents=True, exist_ok=False)
    (output / "classifications.json").write_text(
        json.dumps(classified, indent=2), encoding="utf-8"
    )
    report = dict(
        status="CHECKING_NATIVE_CANDIDATES",
        classification_rule="event-nondeprecated-P31-P279-v1",
        root=events.EVENT_ROOT,
        hierarchy_source=str(source),
        hierarchy_sha256=digest(source / "hierarchy_edges.json"),
        candidates=[row["qid"] for row in candidates],
        records=[],
        event_rows_written=0,
        event_population_complete=False,
    )

    def save() -> None:
        (output / "report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    save()
    try:
        for candidate in candidates:
            qid = candidate["qid"]
            record, evidence = events.current_record(store, qid)
            links = events.item_links(record)
            # Native P31 must still support the saved query-service path. A
            # changed source is a visible stop, not an automatic reclassification.
            p31 = {
                link["source_record_id"].replace("$", "-").lower(): link
                for link in links
                if link["source_predicate"] == "wd:P31"
            }
            for path in candidate["paths"]:
                edge = path["P31"]
                sid = edge["statement"].rsplit("/", 1)[-1].replace("$", "-").lower()
                link = p31.get(sid)
                if (
                    not link
                    or link["object_qid"] != edge["parent"]
                    or link["raw_statement"]["rank"] == "deprecated"
                ):
                    raise SourceException(
                        "Native candidate differs from saved Event classification",
                        qid=qid,
                        edge=edge,
                        source=evidence,
                    )
            (output / f"{qid}.json").write_text(
                json.dumps(record, ensure_ascii=False), encoding="utf-8"
            )
            report["records"].append(
                dict(
                    qid=qid,
                    name=record.get("labels", {}).get("en", {}).get("value")
                    or record.get("labels", {}).get("ja", {}).get("value"),
                    labels=record.get("labels", {}),
                    descriptions=record.get("descriptions", {}),
                    revision=record["lastrevid"],
                    P31=[
                        link for link in links if link["source_predicate"] == "wd:P31"
                    ],
                    source=evidence,
                )
            )
            save()
            LOG.info("Saved candidate %s: %s", qid, report["records"][-1]["name"])
        report["status"] = "NATIVE_CANDIDATES_CHECKED_LINK_GATE_PENDING"
        if mentions is not None and relations is not None:
            check_links(report, output, store, mentions, relations, save)
    except SourceException as exc:
        report.update(status="BLOCKED_CANDIDATE_CHECK", exception=exc.case)
        LOG.error("Stopped: %s", exc.case["reason"])
    except (KeyError, TypeError, ValueError) as exc:
        report.update(
            status="BLOCKED_CANDIDATE_CHECK",
            exception=dict(
                reason="Malformed candidate source or mapping", error=str(exc)
            ),
        )
        LOG.error("Stopped: malformed candidate source or mapping")
    finally:
        save()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--mentions", type=Path)
    parser.add_argument("--relations", type=Path)
    args = parser.parse_args()
    if (args.mentions is None) != (args.relations is None):
        parser.error("--mentions and --relations must be supplied together")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(args.source, args.output, args.store, args.mentions, args.relations)
    print(json.dumps(dict(status=result["status"], records=len(result["records"]))))
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)
