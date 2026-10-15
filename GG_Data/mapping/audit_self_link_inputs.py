"""Trace saved self-links and verify approved output exclusions without rewriting input.

Run: Agent/.venv/Scripts/python.exe GG_Data/mapping/audit_self_link_inputs.py
"""

from __future__ import annotations

import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from assertion_exclusions import exclusion_reason, load_exclusions
from run_relation_mapping_sanity import original_endpoints

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "Data/external/wwii_task_force"
OUT = HERE / "self_link_review_2026-10-15"
ASSERTIONS = HERE / "outputs/relation-map-v1.0.0/complete_mapped_relations_v1.0.0.csv"


def main() -> None:
    rules = load_exclusions()
    self_links: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    total = 0
    with ASSERTIONS.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            total += 1
            subject, target = original_endpoints(row)
            record = {
                "source_record_id": row["source_record_id"],
                "predicate": row["selected_source_predicate"],
                "subject_qid": subject,
                "object_qid": target,
            }
            if exclusion_reason(row["selected_source"], record, rules):
                excluded.append(row)
            if subject == target:
                self_links.append(row)
    assert Counter(
        (r["selected_source"], r["source_record_id"]) for r in excluded
    ) == Counter({key: 1 for key in rules})

    # Keep original N-Quads and absolute decompressed line numbers for every
    # EventKG self-link, not only the three approved exclusions.
    groups: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in self_links:
        if row["selected_source"] == "EventKG":
            path, resource = row["source_reference"].split(":", 1)
            groups[path][resource] = {"assertion": row, "raw_lines": [], "values": {}}
    for path, resources in groups.items():
        with gzip.open(DATA / "eventkg_v3_2" / path, "rt", encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                uri = line.split(" ", 1)[0].strip("<>")
                if uri not in resources:
                    continue
                evidence = resources[uri]
                evidence["raw_lines"].append(
                    {"line": number, "text": line.rstrip("\n")}
                )
                terms = re.findall(r"<([^>]+)>", line)
                if len(terms) >= 3:
                    evidence["values"][terms[1]] = terms[2]
    eventkg = [
        dict(path=path, resource=uri, **evidence)
        for path, resources in groups.items()
        for uri, evidence in resources.items()
    ]
    for evidence in eventkg:
        values = evidence["values"]
        assert (
            values["http://www.w3.org/1999/02/22-rdf-syntax-ns#subject"]
            == values["http://www.w3.org/1999/02/22-rdf-syntax-ns#object"]
        )

    wikidata_rows = {
        r["source_record_id"]: r
        for r in self_links
        if r["selected_source"] == "Wikidata"
    }
    wanted = {r["subject_qid"] for r in wikidata_rows.values()}
    wikidata: list[dict] = []
    profile: list[dict] = []
    with gzip.open(
        DATA / "wikidata_entities.jsonl.gz", "rt", encoding="utf-8"
    ) as stream:
        for number, line in enumerate(stream, 1):
            entity = json.loads(line).get("entity") or {}
            qid = entity.get("id")
            if qid not in wanted:
                continue
            for prop, statements in entity.get("claims", {}).items():
                for statement in statements:
                    sid = statement.get("id")
                    if sid not in wikidata_rows:
                        continue
                    row = wikidata_rows[sid]
                    value = statement["mainsnak"]["datavalue"]["value"]
                    assert value["id"] == qid == row["object_qid"]
                    assert row["selected_source_predicate"] == "wd:" + prop
                    assert statement["rank"] != "deprecated"
                    label = entity.get("labels", {}).get("en", {}).get("value", qid)
                    if prop == "P17":
                        review = (
                            "REVIEW_TERRITORY_SCOPE"
                            if qid == "Q55306"
                            else "KEEP_COUNTRY_SELF_REFERENCE_CONVENTION"
                        )
                        explanation = "P17 officially includes Germany -> country -> Germany as an example; self-reference alone is not an error. Review historical country/territory scope separately."
                    elif prop in {"P1365", "P1366"}:
                        review = "REVIEW_SUCCESSION_IDENTITY_OR_SOURCE_IMPORT"
                        explanation = "Same item is its own predecessor/successor. Reference says imported from Russian Wikipedia. SUCCESSION_TRACE.md documents five verified source-field/current-redirect paths and three unresolved cases; exact import edits are not traced."
                    elif prop == "P6379":
                        review = "REVIEW_SUBJECT_ROLE_AND_REFERENCE"
                        explanation = "Museum is said to have works in its own collection. Reference title concerns a photo series; inspect whether collection holder was used as subject. Cause not established."
                    else:
                        review = "STRONG_INPUT_ERROR_CANDIDATE"
                        explanation = {
                            "P40": "Historical person is their own child.",
                            "P749": "Military unit is its own parent unit.",
                            "P176": "Ship class is its own manufacturer.",
                        }[prop]
                    reference_urls = [
                        snak["datavalue"]["value"]
                        for ref in statement.get("references", [])
                        for p, snaks in ref.get("snaks", {}).items()
                        if p in {"P854", "P4656"}
                        for snak in snaks
                        if "datavalue" in snak
                    ]
                    approved = ("Wikidata", sid) in rules
                    if approved:
                        review = "EXCLUDE_APPROVED_INPUT_ERROR"
                    profile.append(
                        {
                            "observation_id": row["observation_id"],
                            "qid": qid,
                            "name": label,
                            "source_predicate": "wd:" + prop,
                            "source_record_id": sid,
                            "source_line": number,
                            "source_revision": entity.get("lastrevid"),
                            "rank": statement["rank"],
                            "qualifier_count": sum(
                                len(v) for v in statement.get("qualifiers", {}).values()
                            ),
                            "reference_count": len(statement.get("references", [])),
                            "reference_urls": "|".join(reference_urls),
                            "review_status": review,
                            "explanation": explanation,
                            "output_action": (
                                "EXCLUDE_APPROVED_INPUT_ERROR"
                                if approved
                                else "RETAIN_NO_APPROVED_EXCLUSION"
                            ),
                            "pinned_entity_url": f"https://www.wikidata.org/w/index.php?title={qid}&oldid={entity.get('lastrevid')}",
                        }
                    )
                    wikidata.append(
                        {
                            "assertion": row,
                            "archive_line": number,
                            "entity_id": qid,
                            "label": label,
                            "description": entity.get("descriptions", {}).get("en"),
                            "lastrevid": entity.get("lastrevid"),
                            "modified": entity.get("modified"),
                            "property": prop,
                            "statement": statement,
                        }
                    )
    assert {e["statement"]["id"] for e in wikidata} == set(wikidata_rows)
    summary = {
        "date": "2026-10-15",
        "input_rows": total,
        "approved_excluded_rows": len(excluded),
        "rows_retained_by_exclusion_gate": total - len(excluded),
        "self_links_before": len(self_links),
        "self_links_after_approved_gate": len(self_links) - len(excluded),
        "eventkg_raw_self_links_confirmed": len(eventkg),
        "wikidata_saved_self_statements_confirmed": len(wikidata),
        "wikidata_entities": len(wanted),
        "wikidata_review_status_counts": dict(
            Counter(r["review_status"] for r in profile)
        ),
        "wikidata_rank_counts": dict(Counter(r["rank"] for r in profile)),
        "wikidata_with_qualifiers": sum(bool(r["qualifier_count"]) for r in profile),
        "wikidata_with_references": sum(bool(r["reference_count"]) for r in profile),
        "approved_wikidata_exclusions": sum(
            r["selected_source"] == "Wikidata" for r in excluded
        ),
        "input_modified": False,
        "graph_rebuilt": False,
        "filtered_assertion_csv_written": False,
        "verification": "Streaming dry run of approved gate; shared notebook writer tested separately.",
    }
    OUT.mkdir(exist_ok=True)
    payload = {
        "wikidata_archive": str(
            (DATA / "wikidata_entities.jsonl.gz").relative_to(ROOT)
        ),
        "assertion_input": str(ASSERTIONS.relative_to(ROOT)),
        "approved_excluded_assertions": excluded,
        "eventkg": eventkg,
        "wikidata": wikidata,
    }
    (OUT / "source_evidence.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    with (OUT / "wikidata_review.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(profile[0]))
        writer.writeheader()
        writer.writerows(profile)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
