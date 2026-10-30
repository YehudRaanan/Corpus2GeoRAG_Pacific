"""Auditable corrections of the simple source-page Event population.

The first release and Daniel mention identities remain immutable. Concrete
native Events use native source identities, independently of their labels.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

# These are concrete occurrence families, not the broad "occurrence" root.
EVENT_FAMILIES = {
    "Q178561",
    "Q645883",
    "Q831663",
    "Q198",
    "Q350604",
    "Q3199915",
    "Q3882219",
    "Q3839081",
    "Q171558",
    "Q7944",
    "Q40231",
    "Q124734",
    "Q45382",
    "Q188686",
    "Q357104",
    "Q752783",
    "Q5916",
    "Q27020041",
    "Q1539532",
    "Q114609228",
    "Q16913666",
    "Q2627975",
    "Q366301",
    "Q1072326",
    "Q175331",
    "Q124757",
    "Q934744",
    "Q2223653",
    "Q10931",
    "Q98391050",
    "Q8092",
    "Q861911",
    "Q15238777",
    "Q2334719",
    "Q263233",
    "Q131656428",
    "Q114350932",
    "Q3002772",
    "Q12890393",
    "Q625994",
    "Q14547231",
    "Q217901",
    "Q107706",
    "Q290178",
    "Q8068",
    "Q202875",
    "Q101965",
    "Q210112",
    "Q98607365",
    "Q19776345",
    "Q24189077",
}

# Direct native classes prove these are objects, descriptions or series rather
# than individual occurrences. Subclasses are not inferred through arbitrary
# polyhierarchy paths: concrete Event evidence takes precedence on other types.
NON_EVENT_DIRECT = {
    "Q476068",
    "Q131569",
    "Q625298",
    "Q9557810",
    "Q6934728",
    "Q7755",
    "Q102410240",
    "Q1338798",
    "Q19692072",
    "Q35127",
    "Q43229",
    "Q4830453",
    "Q109473326",
    "Q17544377",
    "Q17524420",
    "Q20136634",
    "Q12909644",
    "Q7257",
    "Q11862829",
    "Q1047113",
    "Q15221623",
    "Q623109",
    "Q15991290",
    "Q6631808",
    "Q30634609",
    "Q349",
    "Q3028081",
    "Q19978220",
    "Q12812139",
    "Q1075",
    "Q56053097",
    "Q376346",
    "Q545779",
    "Q2101619",
    "Q1260524",
    "Q1353040",
    "Q2551394",
    "Q1758690",
    "Q781132",
    "Q176799",
    "Q1127126",
    "Q3254959",
    "Q2992826",
    "Q7397",
    "Q618779",
    "Q378427",
    "Q19020",
    "Q2001867",
    "Q615699",
    "Q3220391",
    "Q5398426",
    "Q1358344",
    "Q15141321",
    "Q130583773",
    "Q14904124",
    "Q2245405",
    "Q32015063",
    "Q2915955",
}
SERIES_DIRECT = {
    "Q15275719",
    "Q18608583",
    "Q11483816",
    "Q1197685",
    "Q1445650",
    "Q60075825",
    "Q5440532",
    "Q3001412",
    "Q132241",
    "Q220505",
}


def classify_event(
    fact: dict,
    own: dict,
    ancestors: dict,
    candidate_types: set[str],
    *,
    war_connection: bool = False,
) -> dict:
    """Separate proved occurrences, proved non-events, and unresolved candidates."""
    types = set(fact.get("native_types", []))
    recognized = sorted(types & candidate_types)
    result = dict(recognized_types=recognized, policy="SOURCE_EVENT_V2")

    def finish(status, reason):
        return dict(result, status=status, reason=reason)

    if not fact or fact.get("metadata_status") == "MISSING_METADATA":
        return finish("UNKNOWN_METADATA_MISSING", "NATIVE_METADATA_UNAVAILABLE")
    if "Q718893" in types:
        return finish("NON_EVENT", "MILITARY_THEATER_IS_OPERATIONAL_AREA")
    concrete = own.get("concrete_event_infobox", False)
    if (
        not recognized
        and concrete
        and not types
        and own.get("source", {}).get("status") == "AVAILABLE"
    ):
        return finish("EVENT", "OWN_EVENT_INFOBOX_NO_NATIVE_TYPE")
    if not recognized:
        return finish(
            "NON_EVENT" if types else "UNKNOWN_NO_P31", "NO_CANDIDATE_EVENT_TYPE"
        )
    families = {
        root for t in types for root in ancestors.get(t, [t]) if root in EVENT_FAMILIES
    }
    # A real occupation may also carry the country-overview type, and an actual
    # conference may also carry a treaty type. Preserve the explicit Event facet.
    if types & NON_EVENT_DIRECT and not concrete and not (types & EVENT_FAMILIES):
        return finish("NON_EVENT", "DIRECT_NON_EVENT_CLASS")
    if types & SERIES_DIRECT:
        return finish("NON_EVENT", "EVENT_SERIES_NOT_INDIVIDUAL_OCCURRENCE")
    dates = fact.get("dates") or own.get("dates")
    if fact.get("parents") and not dates and not concrete:
        return finish("REVIEW_EVENT_IDENTITY", "GENERIC_CLASS_OR_UNDATED_OCCURRENCE")
    result["event_families"] = sorted(families)
    if concrete or (families and dates):
        return finish(
            "EVENT", "OWN_EVENT_INFOBOX" if concrete else "SPECIFIC_EVENT_TYPE_AND_DATE"
        )
    if war_connection and types & EVENT_FAMILIES and not fact.get("parents"):
        return finish(
            "EVENT", "SPECIFIC_EVENT_INSTANCE_AND_WAR_CONNECTION; SOURCE_DATE_UNKNOWN"
        )
    return finish(
        "REVIEW_EVENT_IDENTITY", "INSUFFICIENT_INDIVIDUAL_OCCURRENCE_EVIDENCE"
    )


def scoped_decision(qid, fact, own, ancestors, candidate_types, paths):
    decision = classify_event(
        fact, own, ancestors, candidate_types, war_connection=qid in paths
    )
    decision["occurrence_status"] = decision["status"]
    if qid in paths:
        decision["war_connection"] = paths[qid]
    else:
        decision.update(
            status="EXCLUDED_NO_PROVEN_WWII_CONNECTION",
            scope_reason="NO_PINNED_PART_OF_PATH_TO_Q362",
        )
    decision["scope_policy"] = "WWII_PART_OF_Q362; SOURCE_PAGE_SUPPORT_REQUIRED"
    return decision


def native_event_id(qid: str) -> str:
    if not re.fullmatch(r"Q[1-9]\d*", qid):
        raise ValueError("Invalid native Event identity")
    return "event:" + qid


def invalid_key(name: str) -> bool:
    """Exclude audited fragments and empty/punctuation-only extraction keys."""
    return invalid_reason(name) is not None


def invalid_reason(name: str) -> str | None:
    if not any(char.isalnum() for char in name):
        return "NO_UNICODE_ALPHANUMERIC"
    if name in {"The", "the", "and", "of", "Battle of"}:
        return "PROVED_INCOMPLETE_NER_FRAGMENT"
    return None


def correct_population(
    entities: list[dict], memberships: list[dict], pages: list[dict], extra: dict
):
    """Every original key is retained or explicitly accounted for as invalid."""
    from GG_Data.pipeline.simplified_page_events import merge_population

    excluded = [
        dict(row, reason=invalid_reason(row["name"]))
        for row in entities
        if invalid_key(row["name"])
    ]
    invalid = {r["entity_id"] for r in excluded}
    result = merge_population(
        [r for r in entities if r["entity_id"] not in invalid],
        [r for r in memberships if r["entity_id"] not in invalid],
        pages,
        extra,
    )
    return result, excluded


def normalize_event_dates(source: dict) -> tuple[dict, dict]:
    """Apply OWNER's export defaults; keep original evidence outside this view."""
    from Agent.geo_agent.compact_dates import date_bounds

    changes = set()
    invalid = []

    def day(value):
        match = re.fullmatch(r"([+-]?\d+)-(\d{2})-(\d{2})T.*Z", value["time"])
        if not match:
            raise ValueError("Invalid source Event date")
        year, month, date = match.groups()
        precision = value["precision"]
        if precision <= 9 or month == "00":
            month, date = "01", "01"
            changes.add("YEAR_TO_JANUARY_1")
        elif precision == 10 or date == "00":
            date = "01"
            changes.add("MONTH_TO_DAY_1")
        normalized = dict(
            value,
            time=f"{year}-{month}-{date}T00:00:00Z",
            precision=11,
            before=0,
            after=0,
        )
        try:
            date_bounds(normalized)
        except ValueError as error:
            invalid.append(
                dict(value=value, reason="INVALID_SOURCE_DATE", detail=str(error))
            )
            changes.add("INVALID_SOURCE_DATE")
            return None
        return normalized

    def period(row):
        result = []
        for child in row.get("periods", []):
            result.extend(period(child))
        starts = [d for v in row.get("start_date", []) if (d := day(v)) is not None]
        ends = [d for v in row.get("end_date", []) if (d := day(v)) is not None]
        if starts or ends:
            if not starts or not ends:
                changes.add("SINGLE_BOUND_COPIED_TO_BOTH")
            result.append(dict(start_date=starts or ends, end_date=ends or starts))
        for point in row.get("point_date", []):
            value = day(point)
            if value is None:
                continue
            result.append(dict(start_date=[value], end_date=[dict(value)]))
            changes.add("POINT_COPIED_TO_BOTH")
        return result

    periods = period(source)
    basis = "SOURCE_DATE"
    if not periods:
        basis = "OWNER_WWII_DEFAULT"
        changes.add("MISSING_DATE_TO_WWII_PERIOD")

        def default(value):
            return dict(
                time=value + "T00:00:00Z",
                precision=11,
                calendarmodel="http://www.wikidata.org/entity/Q1985727",
                timezone=0,
                before=0,
                after=0,
            )

        periods = [
            dict(start_date=[default("+1939-09-01")], end_date=[default("+1945-09-02")])
        ]
    return (
        periods[0] if len(periods) == 1 else dict(periods=periods),
        dict(
            policy="OWNER_FIRST_DAY_SINGLE_DATE_AND_WWII_DEFAULT_V1",
            basis=basis,
            rules_applied=sorted(changes),
            invalid_source_dates=invalid,
            source_precision_preserved_in="date_sources",
        ),
    )


def event_date_payload(
    native: dict, own: dict, *, cancelled: bool = False, owner_policy: bool = False
) -> dict:
    """Retain both sources; fill absent native fields, keeping planned dates apart."""
    wiki = own.get("dates", {})
    dates = dict(wiki or native)
    if wiki and not dates.get("periods") and not dates.get("point_date"):
        for field in ("start_date", "end_date"):
            if field not in dates and native.get(field):
                dates[field] = native[field]
    planned = own.get("planned_dates", {})
    if cancelled:
        all_planned = [v for v in [dates, planned] if v]
        planned = (
            all_planned[0]
            if len(all_planned) == 1
            else dict(periods=all_planned) if all_planned else {}
        )
        dates = {}
    result = dict(
        event_dates=dates,
        planned_dates=planned,
        date_status=(
            "DATED" if dates else "PLANNED_ONLY" if planned else "SOURCE_DATE_UNKNOWN"
        ),
        date_sources=dict(
            native=native,
            wiki=wiki,
            wiki_source=own.get("source"),
            wiki_fields=own.get("evidence", []),
        ),
        date_selection="OWN_EXPLICIT_EVENT_DATES_FIRST; NATIVE_FALLBACK_AND_MISSING_BOUNDS; ALL_SOURCE_DATES_PRESERVED; PLANNED_DATES_SEPARATE",
    )
    if owner_policy:
        normalized, metadata = normalize_event_dates(dates or planned)
        metadata["date_role"] = (
            "OWNER_DEFAULT"
            if metadata["basis"] == "OWNER_WWII_DEFAULT"
            else "EVENT" if dates else "PLANNED"
        )
        result["date_sources"]["selected_before_normalization"] = dates
        result["date_sources"]["planned_before_normalization"] = planned
        result.update(event_dates=normalized, date_normalization=metadata)
    return result


def native_dates(record: dict) -> dict:
    """Keep native date values, including calendar, uncertainty and precision."""
    result = {}
    for field, prop in [
        ("start_date", "P580"),
        ("end_date", "P582"),
        ("point_date", "P585"),
        ("start_date", "P619"),
        ("end_date", "P620"),
    ]:
        values = result.get(field, [])
        for statement in record.get("claims", {}).get(prop, []):
            value = statement.get("mainsnak", {}).get("datavalue", {}).get("value")
            if (
                statement.get("rank") != "deprecated"
                and isinstance(value, dict)
                and "time" in value
            ):
                if value not in values:
                    values.append(value)
        if values:
            result[field] = values
    return result


def source_fact(qid: str, record: dict) -> dict:
    from GG_Data.entity_resolution.hundred_page_pilot.collect_entities import (
        metadata_row,
    )

    parents = record.get("parents", record.get("parent_types", []))
    if "claims" in record:
        parents = sorted(
            {
                s["mainsnak"]["datavalue"]["value"]["id"]
                for s in record.get("claims", {}).get("P279", [])
                if s.get("rank") != "deprecated"
                and s.get("mainsnak", {})
                .get("datavalue", {})
                .get("value", {})
                .get("id")
            }
        )
    return dict(
        metadata_row(qid, record),
        parents=parents,
        dates=native_dates(record),
        enwiki=record.get("sitelinks", {}).get("enwiki"),
        claims_available="claims" in record,
    )


def _wiki_date_values(raw: str) -> list[dict]:
    """Parse explicit dated infobox values only, never surrounding prose years."""
    import mwparserfromhell

    raw = re.sub(
        r"<ref\b[^>]*(?:/>|>.*?</ref\s*>)|<!--.*?-->", "", raw, flags=re.I | re.S
    )
    raw = re.sub(r"<br\s*/?>", " ", raw, flags=re.I)
    if re.search(
        r"\b(?:circa|before|after|about|approximately|O\.S\.|N\.S\.|Julian)\b",
        raw,
        re.I,
    ):
        return []
    code = mwparserfromhell.parse(raw)
    for template in list(code.filter_templates(recursive=False)):
        name = re.sub(r"[ _-]", "", str(template.name)).lower().strip()
        replacement = ""
        if name in {
            "startdate",
            "enddate",
            "startdateandage",
            "enddateandage",
            "date",
            "dts",
        }:
            args = [
                str(p.value).strip()
                for p in template.params
                if str(p.name).strip().isdigit()
            ]
            if args and all(a.isdigit() for a in args[:3]):
                replacement = "-".join(args[:3])
        elif name in {"startandenddates", "daterangeandageinyears,months,weeksanddays"}:
            args = [
                str(p.value).strip()
                for p in template.params
                if str(p.name).strip().isdigit()
            ]
            if len(args) == 6 and all(a.isdigit() for a in args):
                replacement = "-".join(args[:3]) + " – " + "-".join(args[3:])
        elif name in {"ndash", "endash", "spacedndah", "spacedndash", "snd", "spnd"}:
            replacement = " – "
        code.replace(template, replacement)
    text = code.strip_code(normalize=True, collapse=True)
    # Shared month/year in explicit day ranges, e.g. 7–8 December 1941.
    text = re.sub(
        r"\b(\d{1,2})\s*[–—]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b",
        r"\1 \3 \4 – \2 \3 \4",
        text,
    )
    text = re.sub(
        r"\b([A-Za-z]+)\s+(\d{1,2})\s*[–—]\s*(\d{1,2}),?\s+(\d{4})\b",
        r"\1 \2, \4 – \1 \3, \4",
        text,
    )
    text = re.sub(
        r"\b([A-Za-z]+)\s+(\d{1,2})\s*[–—]\s*([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b",
        r"\1 \2, \5 – \3 \4, \5",
        text,
    )
    months = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    text = re.sub(
        rf"\b(\d{{1,2}})\s+({months})\s*[–—]\s*(\d{{1,2}})\s+({months})\s+(\d{{4}})\b",
        r"\1 \2 \5 – \3 \4 \5",
        text,
        flags=re.I,
    )
    text = re.sub(
        rf"\b({months})\s*[–—]\s*({months})\s+(\d{{4}})\b",
        r"\1 \3 – \2 \3",
        text,
        flags=re.I,
    )
    pattern = (
        rf"\b(?:\d{{1,2}}\s+{months}\s+\d{{4}}|{months}\s+\d{{1,2}},?\s+\d{{4}}|"
        rf"{months}\s+\d{{4}}|\d{{4}}-\d{{1,2}}-\d{{1,2}}|\d{{4}}-\d{{1,2}}|\d{{4}})\b"
    )
    values = []
    for match in re.finditer(pattern, text, re.I):
        token = match.group().replace("Sept ", "Sep ")
        parsed = None
        for fmt, precision in [
            ("%d %B %Y", 11),
            ("%d %b %Y", 11),
            ("%B %d, %Y", 11),
            ("%b %d, %Y", 11),
            ("%B %d %Y", 11),
            ("%b %d %Y", 11),
            ("%Y-%m-%d", 11),
            ("%B %Y", 10),
            ("%b %Y", 10),
            ("%Y-%m", 10),
            ("%Y", 9),
        ]:
            try:
                parsed = datetime.strptime(token, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            return []
        value = dict(
            time=f"+{parsed.year:04}-{parsed.month if precision >= 10 else 0:02}-{parsed.day if precision >= 11 else 0:02}T00:00:00Z",
            precision=precision,
            calendarmodel="http://www.wikidata.org/entity/Q1985727",
            timezone=0,
            before=0,
            after=0,
        )
        if value not in values:
            values.append(value)
    # More than two explicit values need reviewed pairing, never min/max merging.
    return values if len(values) <= 2 else []


def wiki_event_dates(raw: str, *, occupation: bool = False) -> dict:
    """Recover Event-own infobox dates with raw field provenance and status."""
    import mwparserfromhell

    dates, planned, evidence = {}, {}, []
    concrete = False
    for template in mwparserfromhell.parse(raw).filter_templates(recursive=False):
        name = re.sub(r"[ _-]", "", str(template.name)).lower().strip()
        is_event = name == "operationalplan" or (
            name.startswith("infobox")
            and re.search(
                r"militaryconflict|militaryoperation|civilconflict|civilianattack|operationalplan|nuclearweaponstest|nucleartest|summitmeeting|courtcase|olympicgames|event|election|season|competition|tournament|championship|spaceflight|earthquake|flood|eruption|aircraftoccurrence|conference|convention|tropicalcyclone",
                name,
            )
        )
        if occupation and name in {"infoboxformercountry", "infoboxformersubdivision"}:
            is_event = True
        if not is_event or "recurring" in name:
            continue
        concrete = True
        for param in template.params:
            field = re.sub(r"[ _-]", "", str(param.name)).lower().strip()
            field = {
                "opening": "startdate",
                "closing": "enddate",
                "datedecided": "date",
            }.get(field, field)
            if occupation:
                field = {"yearstart": "startdate", "yearend": "enddate"}.get(
                    field, field
                )
            if "season" in name and field in {"year", "season"}:
                field = "date"
            if field not in {"date", "dates", "startdate", "enddate", "planned"}:
                continue
            text = str(param.value).strip()
            if not text:
                continue
            segments = re.split(r"<br\s*/?>", text, flags=re.I)
            periods = []
            for segment in segments:
                vv = _wiki_date_values(segment)
                if len(vv) == 2:
                    periods.append(dict(start_date=vv[:1], end_date=vv[1:]))
                elif len(vv) == 1:
                    periods.append(dict(point_date=vv))
            values = _wiki_date_values(text)
            is_planned = field == "planned" or bool(
                re.search(r"\bplanned\b", text, re.I)
            )
            target = planned if is_planned else dates
            if len(periods) > 1:
                target.setdefault("periods", []).extend(periods)
            elif field in {"startdate", "enddate"} and len(values) == 1:
                target["start_date" if field == "startdate" else "end_date"] = values
            elif len(values) == 2:
                target.update(start_date=values[:1], end_date=values[1:])
            elif len(values) == 1:
                target["point_date"] = values
            evidence.append(
                dict(
                    template=str(template.name).strip(),
                    field=str(param.name).strip(),
                    raw_value=text,
                    status=(
                        "PARSED"
                        if values or len(periods) > 1
                        else "UNPARSED_EXPLICIT_SOURCE_DATE"
                    ),
                    date_role="PLANNED" if is_planned else "EVENT",
                )
            )
    return dict(
        dates=dates,
        planned_dates=planned,
        evidence=evidence,
        concrete_event_infobox=concrete,
    )


def assemble_corrected(base, correction, output):
    """Write a new source-bound population; do not mutate previous artifacts."""
    import hashlib
    import json
    import shutil
    from collections import Counter
    from pathlib import Path

    import pandas as pd

    from GG_Data.pipeline.poc import digest, read_json
    from GG_Data.pipeline.post_qid_events import _occurrence_types
    from GG_Data.pipeline.simplified_agent import (
        native_graph,
        write_array,
        write_object,
    )
    from GG_Data.pipeline.simplified_page_events import event_population

    base, correction, output = Path(base), Path(correction), Path(output)
    if output.exists():
        raise FileExistsError(output)
    if shutil.disk_usage(output.parent).free < 15 * 1024**3:
        raise OSError("Insufficient disk reserve")
    previous = read_json(base / "population/manifest.json")
    prepared = base / "prepared"
    original = read_json(prepared / "manifest.json")
    for name, sha in original["outputs"].items():
        if digest(prepared / name) != sha:
            raise ValueError("Changed prepared input: " + name)
    hierarchy = Path(previous["event_rule"][0]["path"]).parent
    types, rule = _occurrence_types(hierarchy, previous["event_approval_sha256"])
    facts = read_json(correction / "source_facts_v4.json")
    own = read_json(correction / "own_scope_audit_v3.json")
    ancestors = read_json(correction / "type_ancestors_final.json")
    pages_path = correction / "content/page_sources.json.gz"
    pages = read_json(pages_path)
    content_manifest = read_json(correction / "content/manifest.json")
    if digest(pages_path) != content_manifest["outputs"]["page_sources.json.gz"]:
        raise ValueError("Changed content scope")
    mapping = {
        r["target_title"]: r.get("qid")
        for r in read_json(base / "page_link_metadata/title_mapping.json.gz")
    }
    wanted = {mapping[t] for page in pages for t in page["links"] if mapping.get(t)} | {
        p["source_subject_qid"] for p in pages if p.get("source_subject_qid")
    }
    from GG_Data.pipeline.simplified_war_scope import war_paths

    paths = war_paths(
        read_json(correction / "event_partof_graph_v2.json"),
        own,
        read_json(correction / "war_wiki_ancestors/title_mapping.json"),
    )
    decisions = {
        q: scoped_decision(q, facts.get(q, {}), own.get(q, {}), ancestors, types, paths)
        for q in wanted
    }
    records = {
        q: dict(
            id=q,
            label=f["label"],
            direct_types=f["native_types"],
            description=f["description"],
            revision=f["metadata_revision"],
            missing=f["metadata_status"] != "AVAILABLE",
        )
        for q, f in facts.items()
        if q in wanted
    }
    extra = event_population(
        pages, mapping, records, types, native_identity=True, decisions=decisions
    )
    for event in extra["events"]:
        q = event["native_records"][0]["qid"]
        event.update(
            event_date_payload(
                facts[q]["dates"],
                own.get(q, {}),
                cancelled="Q114350932" in facts[q]["native_types"],
                owner_policy=True,
            )
        )
        event["recognition"] = decisions[q]
        event["native_records"][0]["temporal_status"] = event["date_status"]
        event["native_records"][0]["metadata_evidence"] = (
            "correction_evidence/event_native_records_v2.json#" + q
        )
    population, excluded = correct_population(
        read_json(prepared / "entities.json.gz"),
        read_json(prepared / "memberships.json.gz"),
        pages,
        extra,
    )
    output.mkdir()
    for name, rows in population.items():
        write_array(output / (name + ".json.gz"), rows)
    for name in ["events", "recognition_audit", "memberships"]:
        write_array(output / ("event_" + name + ".json.gz"), extra[name])
    write_array(output / "entity_exclusions.json.gz", excluded)
    write_array(
        output / "event_decisions.json.gz",
        [dict(qid=q, **v) for q, v in sorted(decisions.items())],
    )
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
    native_graph().export_frame(
        pd.DataFrame(population["memberships"])[["node_index", "page_index"]],
        output / "memberships.parquet",
    )
    shutil.copyfile(prepared / "mentions.json.gz", output / "mentions.json.gz")
    scope = [
        [p["source_key"], p["wiki_page_id"], p["canonical_page_index"]]
        for p in population["wiki_pages"]
    ]
    audit = dict(
        event_decision_counts=dict(Counter(v["status"] for v in decisions.values())),
        date_status_counts=dict(Counter(e["date_status"] for e in extra["events"])),
        invalid_entity_keys=len(excluded),
        invalid_mentions=sum(e["mention_count"] for e in excluded),
        unknown_source_titles=sum(
            not mapping.get(t) for p in pages for t in set(p["links"])
        ),
        source_revision_status="DANIEL_EXACT_REVISION_UNKNOWN",
    )
    write_object(output / "completeness.json", audit)
    pinned = [
        correction / n
        for n in [
            "source_facts_v4.json",
            "own_scope_audit_v3.json",
            "type_ancestors_final.json",
            "event_native_records_v2.json",
            "event_partof_graph_v2.json",
            "war_wiki_ancestors/title_mapping.json",
            "content/manifest.json",
            "content/page_sources.json.gz",
        ]
    ]
    result = dict(
        previous,
        schema_version="simplified-agent-v2",
        stage="SOURCE_CORRECTED_POPULATION",
        created_utc=datetime.now(timezone.utc).isoformat(),
        page_scope_id=hashlib.sha256(
            json.dumps(scope, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest(),
        event_rule=[
            dict(path=str(p.resolve()), sha256=digest(p))
            for p in rule + [Path(__file__)]
        ],
        correction_inputs=[
            dict(path=str(p.resolve()), sha256=digest(p)) for p in pinned
        ],
        quality_policy="EXCLUDE_NO_UNICODE_ALPHANUMERIC_AND_AUDITED_FIVE_FRAGMENT_STRINGS; RAW_ROWS_UNCHANGED",
        event_scope="WWII_PART_OF_Q362; SOURCE_PAGE_SUPPORT_REQUIRED",
        event_identity="NATIVE_SOURCE_QID; NER_EXACT_NAME_TYPE_UNCHANGED",
        date_policy="OWNER_FIRST_DAY_SINGLE_DATE_AND_WWII_DEFAULT_V1",
        deferred_reviews=[
            "ADDITIONAL_EVENT_COMPLETENESS_AND_IDENTITY",
            "SOURCE_DATE_CONFLICTS_AND_RANGES",
        ],
        counts=dict(
            original["counts"],
            entities=len(population["entities"]),
            events=len(extra["events"]),
            memberships=len(population["memberships"]),
            source_keys=len(pages),
            pages=len({p["wiki_page_id"] for p in pages}),
        ),
        outputs={p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()},
    )
    write_object(output / "manifest.json", result)
    return result
