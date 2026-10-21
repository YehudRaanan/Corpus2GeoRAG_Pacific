"""Geography input preflight: population S2T section 9; no source retrieval.

Use the populated model, not the older first-50 draft graph. Source selection
and geometry population must wait until this date preflight passes.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import defaultdict
from pathlib import Path

from .poc import digest, read_json
from .relation_selection import PERIOD_START, temporal_group, year_span
from .relations import SourceException, date_parts

LOG = logging.getLogger(__name__)


def selection_value(values: list[dict], place_id: str) -> dict:
    """S2T 9.2: retain partial dates; compare at their supplied precision.

    Approved 21 October after the Transcarpathia stop. Missing dates use the
    existing 7 December 1941 default. Zero month/day values are not real days;
    use them only to order the native prefixes, never to construct a date.
    """
    candidates = []
    for value in values:
        precision = value["precision"]
        probe = {
            "observation_id": value["source_id"],
            "time_point": value["time"],
            "time_precision": {"point": [precision]},
            "attributes": {"qualifiers": {"P585": [{"datavalue": {"value": value}}]}},
        }
        if temporal_group(probe) == "OUTSIDE_PERIOD":
            continue
        parts = date_parts(value["time"])[:3]
        supplied = max(1, min(3, precision - 8))
        prefix = parts[:supplied]
        lower_year, _ = year_span(parts[0], precision)
        candidates.append(((lower_year, *prefix[1:]), precision, prefix))
    if not candidates:
        return dict(
            selection_date="%04d-%02d-%02d" % PERIOD_START, selection_precision=11
        )
    _, precision, earliest = min(candidates)
    # Native precision accompanies the value: 1940 + precision 8 means the
    # 1940s, not 1 January 1940. Reuse approved ranges, not invented dates.
    return dict(
        selection_date="-".join(
            f"{part:04d}" if i == 0 else f"{part:02d}"
            for i, part in enumerate(earliest)
        ),
        selection_precision=precision,
    )


def selection_date(values: list[dict], place_id: str) -> str:
    """Display only; source comparison must also use selection_precision."""
    return selection_value(values, place_id)["selection_date"]


def prepare(model: Path, output: Path) -> dict:
    """Pin existing model files; stop on the first exception without geometry IO."""
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    manifest = read_json(model / "manifest.json")
    for name, expected in manifest["outputs"].items():
        if digest(model / name) != expected:
            raise ValueError(f"Model artifact checksum differs: {name}")
    entities = read_json(model / "entities.json.gz")
    # S2T 9.1, approved synthetic-LOC extension (21 October): a missing
    # Wikidata identity is not a reason to skip geographic identity matching.
    places = {row["entity_id"]: row for row in entities if row["type"] == "LOC"}
    for place_id in places:
        if not re.fullmatch(r"Q[1-9][0-9]*|SYN_[A-Za-z0-9_]+", place_id):
            raise ValueError(f"Unexpected location identity: {place_id!r}")
    # Reuse the frozen Daniel input already pinned by the populated model.
    # Page references are context, not evidence that a place lies in that page's
    # named area. Do not infer a parent, extract names, or parse paragraph text.
    mention_paths = [
        Path(name)
        for name in manifest["inputs"]
        if Path(name).name == "mentions.json.gz"
    ]
    if len(mention_paths) != 1:
        raise ValueError("Expected one pinned Daniel mentions artifact")
    mention_path = mention_paths[0]
    if digest(mention_path) != manifest["inputs"][str(mention_path)]:
        raise ValueError("Daniel mentions checksum differs")
    contexts = defaultdict(list)
    for mention in read_json(mention_path):
        if mention["entity_id"] in places:
            contexts[mention["entity_id"]].append(
                {
                    key: mention.get(key)
                    for key in (
                        "mention_id",
                        "word",
                        "entity_group",
                        "subtype",
                        "Source",
                        "wiki_site",
                        "wiki_page_id",
                    )
                }
            )
    events = {row["event_id"]: row for row in read_json(model / "events.json.gz")}
    dates = defaultdict(list)
    for row in read_json(model / "relations.json.gz"):
        linked = places.keys() & {row["subject_entity_id"], row["object_entity_id"]}
        precisions = json.loads(row["time_precision"])
        for qid in sorted(linked):
            for field, key in (
                ("time_from", "from"),
                ("time_to", "to"),
                ("time_point", "point"),
            ):
                if not row[field]:
                    continue
                decision = (
                    row.get("attributes", {})
                    .get("time_selection", {})
                    .get("decisions", {})
                    .get(key, {})
                )
                supplied = decision.get("selected_precision", precisions[key])
                if len(supplied) != 1:
                    raise SourceException(
                        "Geography date precision is ambiguous",
                        source_record_id=row["source_record_id"],
                    )
                prop = {"from": "P580", "to": "P582", "point": "P585"}[key]
                snaks = row.get("attributes", {}).get("qualifiers", {}).get(prop, [])
                calendars = {
                    s.get("datavalue", {}).get("value", {}).get("calendarmodel")
                    for s in snaks
                }
                if len(calendars) > 1:
                    raise SourceException(
                        "Geography date calendars differ",
                        source_record_id=row["source_record_id"],
                    )
                dates[qid].append(
                    dict(
                        time=row[field],
                        precision=supplied[0],
                        calendarmodel=next(iter(calendars), None),
                        source_id=row["source_record_id"],
                    )
                )
            other = (
                row["object_entity_id"]
                if qid == row["subject_entity_id"]
                else row["subject_entity_id"]
            )
            if other in events:
                for field in ("start_date", "end_date", "point_date"):
                    dates[qid].extend(
                        {**v, "source_id": other, "event_field": field}
                        for v in events[other][field]
                    )
    report = dict(
        status="GEOGRAPHY_INPUTS_READY",
        total_loc_targets=len(places),
        confirmed_place_qids=sum(
            bool(re.fullmatch(r"Q[1-9][0-9]*", place_id)) for place_id in places
        ),
        synthetic_loc_rows=sum(
            r["type"] == "LOC" and r["entity_id"].startswith("SYN_") for r in entities
        ),
        source_manifest_sha256=digest(model / "manifest.json"),
        source_mentions_sha256=digest(mention_path),
        code_sha256=digest(Path(__file__)),
        new_source_requests=0,
        geometry_rows_written=0,
    )
    targets = []
    try:
        for qid, row in sorted(places.items()):
            targets.append(
                dict(
                    place_id=qid,
                    name=row["name"],
                    aliases=row.get("aliases", []),
                    type=row["type"],
                    identity_status=row["identity_status"],
                    # Never send a SYN ID as wikidata=QID to a source service.
                    wikidata_id=None if qid.startswith("SYN_") else qid,
                    lookup_method=(
                        "NAME_ALIAS_CONTEXT"
                        if qid.startswith("SYN_")
                        else "EXACT_QID_THEN_NAME_ALIAS_CONTEXT"
                    ),
                    source_context=contexts[qid],
                    **selection_value(dates[qid], qid),
                )
            )
    except SourceException as error:
        report.update(status="STOPPED_FOR_CONSULTATION", case=error.case)
    report["checked_places_before_stop"] = len(targets)
    output.mkdir(parents=True)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if report["status"] == "GEOGRAPHY_INPUTS_READY":
        (output / "targets.json").write_text(
            json.dumps(targets, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    LOG.info("%s", json.dumps(prepare(args.model, args.output), ensure_ascii=True))
