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
from .relation_selection import PERIOD_START, temporal_group
from .relations import SourceException, date_parts

LOG = logging.getLogger(__name__)


def selection_date(values: list[dict], place_id: str) -> str:
    """Reuse approved precision comparisons, never turn a partial date into a day.

    Partial dates later than an already established exact minimum cannot change
    that minimum. An earlier/overlapping partial date requires user agreement.
    Missing dates use the existing 7 December 1941 default (S2T 9.2).
    """
    exact, partial = [], []
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
        if precision >= 11:
            exact.append(parts)
        else:
            partial.append(value)
    earliest = min(exact) if exact else None
    for value in partial:
        supplied = max(1, min(3, value["precision"] - 8))
        prefix = date_parts(value["time"])[:supplied]
        if earliest is None or (
            earliest != PERIOD_START and prefix <= earliest[:supplied]
        ):
            raise SourceException(
                "Geography selection date needs partial-date agreement",
                place_id=place_id,
                earliest_exact_date=earliest,
                partial_date=value,
            )
    return "%04d-%02d-%02d" % (earliest or PERIOD_START)


def prepare(model: Path, output: Path) -> dict:
    """Pin existing model files; stop on the first exception without geometry IO."""
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    manifest = read_json(model / "manifest.json")
    for name, expected in manifest["outputs"].items():
        if digest(model / name) != expected:
            raise ValueError(f"Model artifact checksum differs: {name}")
    entities = read_json(model / "entities.json.gz")
    # S2T 9.1: use resolved LOC rows; do not promote synthetic names to QIDs.
    places = {
        row["entity_id"]: row
        for row in entities
        if row["type"] == "LOC" and re.fullmatch(r"Q[1-9][0-9]*", row["entity_id"])
    }
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
        confirmed_place_qids=len(places),
        synthetic_loc_rows=sum(
            r["type"] == "LOC" and r["entity_id"].startswith("SYN_") for r in entities
        ),
        source_manifest_sha256=digest(model / "manifest.json"),
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
                    selection_date=selection_date(dates[qid], qid),
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
