"""Small Daniel-first query test; population S2T 7, not full Event discovery.

Reuse the verified 165-item hierarchy probe as a bounded test reference. Its
absence cannot reject other candidates. Only native snapshot links are queried;
no live hierarchy walk, full-record download or model population is launched.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
from pathlib import Path

from GG_Data.mapping.build_relation_mapping_v2_1 import read_csv
from GG_Data.pipeline import events
from GG_Data.pipeline.event_candidate_check import qualifying_links, statement_key
from GG_Data.pipeline.poc import ROOT, digest, read_json
from GG_Data.pipeline.relations import SourceException
from GG_Data.pipeline.scope_concentration_filter import combine_language_rows

BASE = ROOT / "GG_Data/pipeline/outputs"


def sample_query(source: str, daniel: list[str], classified: list[dict]) -> str:
    """Count distinct Daniel endpoints before returning any candidate links.

    The SQL gate is preliminary: approved mapping and exact exclusions still
    apply locally before the final two-distinct-QID decision (S2T 7/8).
    Classifications are cached latest-hierarchy evidence, not snapshot types.
    """
    classes = {r["qid"]: r["event_hierarchy_match"] for r in classified}
    ids = set(daniel) | set(classes)
    if not daniel or any(not re.fullmatch(r"Q[1-9]\d*", q) for q in ids):
        raise ValueError("Expected native Daniel and classified reference QIDs")
    if len(classes) != len(classified) or len(set(daniel)) != len(daniel):
        raise ValueError("Duplicate test input IDs")
    targets = ",".join(f"'{q}'" for q in daniel)
    positive = ",".join(f"'{q}'" for q, yes in classes.items() if yes)
    numbers = ",".join(q[1:] for q in sorted(ids))
    return f"""WITH daniel AS (
 SELECT qid FROM UNNEST([{targets}]) AS qid
), records AS (
 SELECT id, PARSE_JSON(RTRIM(item, ',\\n\\r '), wide_number_mode=>'round')['claims'] AS claims
 FROM {source} WHERE numeric_id IN ({numbers}) AND STARTS_WITH(id, 'Q')
), links AS (
 SELECT id AS subject_qid, p AS property_id,
   JSON_VALUE(s, '$.mainsnak.datavalue.value.id') AS object_qid,
   TO_JSON_STRING(s) AS statement_json
 FROM records, UNNEST(JSON_KEYS(claims, 1)) AS p,
   UNNEST(JSON_QUERY_ARRAY(claims[p])) AS s
 WHERE JSON_VALUE(s, '$.mainsnak.datavalue.value.entity-type') = 'item'
), connected AS (
 SELECT e AS event_qid, d.qid AS daniel_qid, l.*
 FROM daniel AS d JOIN links AS l
 ON d.qid IN (l.subject_qid, l.object_qid)
 CROSS JOIN UNNEST(IF(l.subject_qid=d.qid, [l.object_qid], [l.subject_qid])) AS e
 WHERE e IN ({positive})
), eligible AS (
 SELECT event_qid FROM connected GROUP BY event_qid
 HAVING COUNT(DISTINCT daniel_qid) >= 2
)
SELECT ARRAY(SELECT id FROM records ORDER BY id) AS present_qids,
 ARRAY(SELECT AS STRUCT c.* FROM connected AS c JOIN eligible USING(event_qid)
       ORDER BY event_qid, subject_qid, object_qid, property_id, statement_json) AS links"""


def filtered_sample(selection: Path, sample: Path) -> tuple[list[str], dict]:
    """S2T 6.1: filter only known MISC IDs, holding unknowns separately.

    This bounded test reuses the previous random sample without replacements.
    Original Entity/Mention records remain intact. Other types are unaffected.
    """
    saved = read_json(selection)
    if saved["status"] != "COMPLETE_MAXIMUM_LANGUAGE_THRESHOLD":
        raise ValueError("Expected the approved maximum-language filter")
    for name, sha in saved["outputs"].items():
        if digest(selection.parent / name) != sha:
            raise ValueError("Combined filter output changed")
    sources = [Path(p) for p in saved["inputs"] if Path(p).name == "report.json"]
    for source in sources:
        if digest(source) != saved["inputs"][str(source)]:
            raise ValueError("Combined filter language evidence changed")
    by_wiki = {read_json(p)["wiki"]: read_json(p) for p in sources}
    replayed = combine_language_rows(
        by_wiki["enwiki"]["rows"], by_wiki["jawiki"]["rows"]
    )
    if replayed != saved["rows"]:
        raise ValueError("Combined filter decisions differ from language evidence")
    original = read_json(sample)["daniel_qids"]
    if len(set(original)) != len(original):
        raise ValueError("Repeated QID in the saved random sample")
    decisions = {r["qid"]: r["keep_for_event_retrieval"] for r in replayed}
    excluded = sorted(q for q in original if q in decisions and decisions[q] is False)
    held = sorted(q for q in original if q in decisions and decisions[q] is None)
    kept = sorted(set(original) - set(excluded) - set(held))
    if len(kept) < 2:
        raise ValueError(
            "Fewer than two usable sample entities; consult before testing"
        )
    return kept, dict(
        original_sample_qids=original,
        retained_daniel_qids=kept,
        below_threshold_qids=excluded,
        held_unknown_qids=held,
        unknown_policy="Held outside this bounded test; no exclusion decision",
    )


def run(
    selection: Path | None = None,
    reuse_sample: Path | None = None,
    output: Path | None = None,
) -> dict:
    """Five random Daniel QIDs plus a separately identified positive control.

    Controls Q352/Q8007 already occur in Daniel and link to WWII in the frozen
    snapshot. They test a positive; they are not a random or coverage estimate.
    """
    entities = BASE / "poc_10k_entities_snapshot_first_20261020"
    prior = BASE / "poc_10k_event_snapshot_measurement_20261020"
    relations = BASE / "poc_10k_relations_original_historical_dates_20261020"
    output = output or BASE / "poc_10k_event_sample_query_20261020"
    store = BASE / "wikidata_event_snapshot_discovery_cache"
    if output.exists():
        raise ValueError("Keep prior test outputs unchanged")
    accepted = read_json(entities / "verification.json")
    manifest = read_json(entities / "manifest.json")
    if digest(entities / "manifest.json") != accepted["manifest_sha256"]:
        raise ValueError("Frozen Entity manifest changed")
    for name, sha in manifest["outputs"].items():
        if digest(entities / name) != sha:
            raise ValueError(f"Frozen Entity output changed: {name}")
    probe = read_json(prior / "report.json")
    if (
        digest(prior / "report.json")
        != read_json(prior / "verification.json")["report_sha256"]
    ):
        raise ValueError("Accepted hierarchy probe reference changed")
    # Revalidate the complete saved hierarchy, not only a list of positive IDs.
    for name, sha in probe["inputs"].items():
        if digest(Path(name)) != sha:
            raise ValueError(f"Probe input changed: {name}")
    hierarchy = next(
        Path(p) for p in probe["inputs"] if p.endswith("hierarchy_edges.json")
    )
    classified = events.classify_events(read_json(hierarchy))
    if (
        classified != read_json(prior / "classifications.json")
        or digest(prior / "classifications.json")
        != probe["outputs"]["classifications.json"]
    ):
        raise ValueError("Saved Event classifications differ")
    records = read_json(entities / "full_records.json.gz")
    sample_evidence = {}
    if selection is not None:
        if reuse_sample is None:
            raise ValueError("Filtered test requires an unchanged prior sample")
        previous = read_json(reuse_sample.parent / "report.json")
        if digest(reuse_sample) != previous["outputs"][reuse_sample.name]:
            raise ValueError("Previous random sample changed")
        random_qids, sample_evidence = filtered_sample(selection, reuse_sample)
        controls = []  # Do not add or replace entities after filtering.
    else:
        random_qids = random.Random(20261020).sample(sorted(records), 5)
        controls = ["Q352", "Q8007"]
    if not set(controls) <= set(records):
        raise ValueError("Positive controls must already occur in Daniel")
    sample = sorted(set(random_qids + controls))
    if not set(sample) <= set(records):
        raise ValueError("Sample QIDs must already occur in frozen Daniel data")
    for qid in controls:
        if not any(
            link["object_qid"] == "Q362"
            for link in events.item_links(records[qid]["entity"])
        ):
            raise ValueError("Saved positive control differs")
    reference = next(
        Path(p) for p in probe["inputs"] if p.endswith("reference_manifest.json")
    )
    ref = read_json(reference)
    if read_json(store / "table_snapshot.json") != ref["table_snapshot"]:
        raise ValueError("Query cache uses another snapshot")
    mapping_path = relations / "mapping/RELATION_MAPPING_TABLE_v2.1.2.csv"
    relation_manifest = read_json(relations / "manifest.json")
    if (
        digest(mapping_path)
        != relation_manifest["mapping_artifacts"][str(mapping_path.relative_to(ROOT))]
    ):
        raise ValueError("Accepted mapping changed")
    mapping = {(r["source"], r["source_predicate"]): r for r in read_csv(mapping_path)}
    sys.path.insert(0, str(ROOT / "GG_Data/entity_resolution"))
    try:
        from bigquery_direct_wikidata import BigQueryData
    finally:
        sys.path.pop(0)
    client = BigQueryData(ref["project"], store)
    output.mkdir()
    report = dict(
        status="TESTING_DANIEL_FIRST_QUERY",
        seed=20261020,
        random_daniel_qids=random_qids,
        positive_control_qids=controls,
        filter_evidence=sample_evidence,
        reference_scope="165_CACHED_CLASSIFIED_CANDIDATES_ONLY",
        reference_count=len(classified),
        snapshot_at=ref["table_snapshot"]["snapshot_at"],
        events_complete=False,
        event_rows_written=0,
        final_graph_written=False,
        code_sha256=digest(Path(__file__)),
        inputs={
            str(p): digest(p)
            for p in (
                entities / "manifest.json",
                prior / "report.json",
                hierarchy,
                reference,
                mapping_path,
            )
        },
    )
    if selection is not None:
        report["inputs"].update(
            {
                str(p): digest(p)
                for p in (selection, reuse_sample, reuse_sample.parent / "report.json")
            }
        )

    def save():
        (output / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )

    save()
    try:
        # Independent check against complete native cached records. This catches
        # a lost direction or duplicate mention count in the new SQL, not just
        # whether BigQuery accepts its syntax (S2T 7 acceptance).
        cached = BASE / "poc_10k_event_classification_first_checked_20261020"
        cached_report = read_json(cached / "report.json")
        if (
            digest(cached / "report.json")
            != read_json(cached / "verification.json")["report_sha256"]
        ):
            raise SourceException("Accepted sample Event records changed")
        if (
            digest(cached / "full_records.json.gz")
            != cached_report["outputs"]["full_records.json.gz"]
        ):
            raise SourceException("Cached native sample records changed")
        native = read_json(cached / "full_records.json.gz")
        native.update({q: records[q] for q in sample})
        all_links = [
            link
            for record in native.values()
            for link in events.item_links(record["entity"])
        ]
        expected = {}
        for case in classified:
            if not case["event_hierarchy_match"]:
                continue
            kept, _ = qualifying_links(all_links, case["qid"], set(sample), mapping)
            if len({link["daniel_qid"] for link in kept}) >= 2:
                expected[case["qid"]] = sorted(
                    statement_key(link["source_record_id"]) for link in kept
                )
        report["expected_qualified_qids"] = sorted(expected)
        report["inputs"][str(cached / "report.json")] = digest(cached / "report.json")
        report["inputs"][str(cached / "full_records.json.gz")] = digest(
            cached / "full_records.json.gz"
        )
        save()
        sql = sample_query(client.source, sample, classified)
        (output / "query.sql").write_text(sql, encoding="utf-8")
        answer = client.query(sql)
        report["source"] = client.requests[-1]
        (output / "query_result.json").write_text(
            json.dumps(answer, indent=2), encoding="utf-8"
        )
        if len(answer) != 1:
            raise SourceException("Unexpected sample query result shape")
        present = set(answer[0]["present_qids"])
        positives = {r["qid"] for r in classified if r["event_hierarchy_match"]}
        if (set(sample) | positives) - present:
            raise SourceException(
                "Sample query records missing",
                qids=sorted((set(sample) | positives) - present),
            )
        by_event = {}
        for row in answer[0]["links"]:
            event_qid = row["event_qid"]
            statement = json.loads(row["statement_json"])
            parsed = events.item_links(
                dict(id=row["subject_qid"], claims={row["property_id"]: [statement]})
            )
            if (
                len(parsed) != 1
                or parsed[0]["object_qid"] != row["object_qid"]
                or row["daniel_qid"] not in sample
                or event_qid not in positives
            ):
                raise SourceException("Unexpected sample query link", row=row)
            by_event.setdefault(event_qid, []).extend(parsed)
        decisions = []
        for event_qid, links in sorted(by_event.items()):
            kept, excluded = qualifying_links(links, event_qid, set(sample), mapping)
            endpoints = sorted({r["daniel_qid"] for r in kept})
            decisions.append(
                dict(
                    qid=event_qid,
                    eligible=len(endpoints) >= 2,
                    daniel_qids=endpoints,
                    distinct_daniel_count=len(endpoints),
                    links=kept,
                    excluded=excluded,
                )
            )
        if controls and not any(
            r["qid"] == "Q362" and r["eligible"] for r in decisions
        ):
            raise SourceException("Known-positive Event did not pass")
        actual = {
            row["qid"]: sorted(
                statement_key(link["source_record_id"]) for link in row["links"]
            )
            for row in decisions
            if row["eligible"]
        }
        if actual != expected:
            raise SourceException(
                "SQL differs from native-record check", expected=expected, actual=actual
            )
        (output / "decisions.json").write_text(
            json.dumps(decisions, indent=2), encoding="utf-8"
        )
        report.update(
            status="SAMPLE_QUERY_VALIDATED_BOUNDED_REFERENCE_ONLY",
            qualified_qids=[r["qid"] for r in decisions if r["eligible"]],
            returned_links=len(answer[0]["links"]),
            decisions=[
                {k: v for k, v in r.items() if k not in {"links", "excluded"}}
                for r in decisions
            ],
        )
    except (ValueError, RuntimeError) as exc:
        # The POC stops on a new data/query/source problem. No altered source,
        # relaxed gate, timeout retry or full-run continuation is inferred.
        report.update(
            status="BLOCKED_SAMPLE_QUERY",
            exception=getattr(exc, "case", {"reason": str(exc)}),
        )
    report["outputs"] = {
        p.name: digest(p) for p in output.iterdir() if p.name != "report.json"
    }
    save()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--reuse-sample", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = run(args.selection, args.reuse_sample, args.output)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"inputs", "outputs", "source"}
            },
            ensure_ascii=True,
        )
    )
    raise SystemExit(1 if result["status"].startswith("BLOCKED") else 0)
