"""Automatic context-aware Geography run for the same ten frozen LOC inputs.

Population S2T section 9 and GEOCODING_HIGH_LEVEL_PROCESS.md govern sources,
selection dates, identity evidence, Shapely storage and model-only pointers.
The owner approved this bounded context experiment on 22 October 2026.
No original entity, mention, date or completed model artifact is modified.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import ijson
from shapely.geometry import Point, shape

from .geography_sample import tools
from .graph_contract import load_geometry
from .poc import ROOT, digest, read_json
from .rebuild_poc import write

# These are literal feature words, not inferred classes or new entity records.
# Restrict context to the name and immediately adjacent words: a distant
# "airfield" in the same text must not turn a different place into an airport.
FEATURE_WORDS = {
    "settlement": r"town|city|village|hamlet|settlement",
    "airport": r"airfield|airport|aerodrome|air base|fighter strip",
    "peninsula": r"peninsula",
    "bay": r"bay",
    "island": r"island",
    "harbor": r"harbor|harbour",
    "river": r"river",
}
GN_TYPES = {
    "settlement": {
        "PPL",
        "PPLA",
        "PPLA2",
        "PPLA3",
        "PPLA4",
        "PPLC",
        "PPLW",
        "PPLL",
        "PPLX",
    },
    "airport": {"AIRP", "AIRF", "AIRB"},
    "peninsula": {"PEN"},
    "bay": {"BAY"},
    "island": {"ISL"},
    "harbor": {"HBR"},
    "river": {"STM"},
}


def context(mention: dict) -> dict:
    """Use only literal, local evidence; preserve exact source offsets.

    Parent patterns are '<mention>, Proper Name' and '<mention> in Proper
    Name'. They yield clues, not a verified geographic parent. Country or
    region agreement must subsequently be checked against the source record.
    No page-title inheritance, text-date extraction or new entity extraction.
    """
    text, start, end = mention["Text"], mention["start"], mention["end"]
    if text[start:end] != mention["word"]:
        raise ValueError("Mention span differs from pinned Daniel text")
    features = []
    for kind, words in FEATURE_WORDS.items():
        pattern = rf"\b(?:{words})\b"
        probes = [(mention["word"], start)]
        suffix = re.match(rf"\s+(?P<term>{words})\b", text[end:], re.I)
        if suffix:
            probes.append((suffix.group("term"), end + suffix.start("term")))
        for value, offset in probes:
            for match in re.finditer(pattern, value, re.I):
                features.append(
                    dict(
                        value=kind,
                        literal=match.group(),
                        start=offset + match.start(),
                        end=offset + match.end(),
                    )
                )
    proper = r"[A-Z][A-Za-z'’-]*(?:\s+[A-Z][A-Za-z'’-]*){0,5}"
    parent = re.match(rf"(?:\s*,\s*|\s+in\s+)(?P<parent>{proper})", text[end:])
    parents = []
    if parent:
        parents.append(
            dict(
                value=parent.group("parent"),
                start=end + parent.start("parent"),
                end=end + parent.end("parent"),
            )
        )
    return dict(
        mention_id=mention["mention_id"],
        features=features,
        parents=parents,
        evidence_status="LITERAL_CLUES_REQUIRE_CANDIDATE_CHECK",
        dates_from_text=False,
    )


def exact_alias(name: str, aliases: list[str]) -> bool:
    """Reuse the established exact-name/recorded-alias fallback acceptance.

    Trigram similarity from the earlier diagnostic is not promoted into a new
    Geography acceptance threshold. Non-exact names remain review candidates.
    """
    return name.strip().casefold() in {n.strip().casefold() for n in aliases if n}


def parent_labels(candidate: dict, admin: dict) -> list[str]:
    if candidate["source"] == "GeoNames":
        labels = []
        for key in (
            (candidate["country_code"], ""),
            (candidate["country_code"], candidate.get("admin1", "")),
        ):
            labels.extend(admin.get(key, []))
        return labels
    return [
        v
        for k, v in candidate.get("address", {}).items()
        if k in {"country", "state", "region", "county", "island"}
    ]


def compatible(kind: str, candidate: dict) -> bool:
    if candidate["source"] == "GeoNames":
        return candidate.get("feature_code") in GN_TYPES.get(kind, set())
    code, category = candidate.get("feature_code"), candidate.get("feature_class")
    return code in {
        "settlement": {"city", "town", "village", "hamlet"},
        "airport": {"aerodrome", "airfield"},
        "peninsula": {"peninsula"},
        "bay": {"bay"},
        "island": {"island"},
        "harbor": {"harbour"},
        "river": {"river"},
    }.get(kind, set()) or (
        kind == "settlement" and category == "boundary" and code == "administrative"
    )


def run(base: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Preserve prior output; choose a new directory")
    old = base / "geography_sample"
    original = read_json(old / "audit.json")
    analysis_path = base / "geography_candidate_analysis/candidate_review.json"
    analysis = read_json(analysis_path)
    source_hashes = {str(analysis_path): digest(analysis_path)}
    for value, expected in original["source_evidence"].items():
        path = Path(value)
        if not path.is_absolute():
            path = ROOT / path
        if digest(path) != expected:
            raise ValueError(f"Changed source: {path}")
        source_hashes[str(path)] = expected
    # Bind every source used by the offline candidate analysis, including the
    # country archives. Candidate annotations do not become identity decisions.
    for value, expected in analysis["source_sha256"].items():
        if digest(Path(value)) != expected:
            raise ValueError(f"Changed candidate evidence: {value}")
        source_hashes[value] = expected
    protected = {
        str(p): digest(p)
        for folder in (old, base / "model_qid_name")
        for p in folder.iterdir()
        if p.is_file()
    }
    mentions_path = base / "mentions_pages/mentions.json.gz"
    mentions = {m["mention_id"]: m for m in read_json(mentions_path)}
    sample = read_json(old / "sample.json")
    if len(sample) != 10 or len({p["place_id"] for p in sample}) != 10:
        raise ValueError("Expected the same ten distinct input identities")
    sample_ids = [p["place_id"] for p in sample]
    audits = {r["input"]["place_id"]: r for r in original["results"]}
    prior_candidates = {r["place_id"]: r for r in analysis["reviews"]}
    entities = {}
    with gzip.open(base / "model_qid_name/entities.json.gz", "rb") as stream:
        for row in ijson.items(stream, "item", use_float=True):
            if row["entity_id"] in sample_ids and row["type"] == "LOC":
                entities[row["entity_id"]] = row
    if set(entities) != set(sample_ids):
        raise ValueError("Sample identity is absent from the completed model")
    client = tools()
    output.mkdir(parents=True)
    cache = output / "sources"
    cache.mkdir()
    report = dict(status="RUNNING", inputs=10, results=[], new_requests=0)
    contexts = {
        p["place_id"]: context(mentions[p["original_mention_id"]]) for p in sample
    }
    write(output / "contexts.json", contexts)
    candidates = {
        pid: list(prior_candidates[pid].get("candidates", [])) for pid in sample_ids
    }
    for name, rows in analysis["additional_cached_alias_search"].items():
        pid = next(p["place_id"] for p in sample if p["name"] == name)
        candidates[pid].extend(rows)

    # Cache parent-name evidence from existing country archives. A gazetteer's
    # own parent must match the independent literal input clue; it cannot fill
    # in a missing clue by itself. No new country downloads are performed.
    admin = {}
    countries = {
        c["country_code"]
        for rows in candidates.values()
        for c in rows
        if c["source"] == "GeoNames"
    }
    for country in sorted(countries):
        archive = ROOT / f"GG_Data/geocoding/cache/geonames/{country}.zip"
        if not archive.exists():
            continue
        source_hashes[str(archive)] = digest(archive)
        with (
            zipfile.ZipFile(archive) as zipped,
            zipped.open(country + ".txt") as stream,
        ):
            for raw in stream:
                fields = raw.decode("utf-8").rstrip("\r\n").split("\t")
                if fields[7] in {"PCLI", "ADM1"}:
                    key = (fields[8], "" if fields[7] == "PCLI" else fields[10])
                    admin[key] = [fields[1], fields[2], *fields[3].split(",")]

    try:
        for place in sample:
            pid, name = place["place_id"], place["name"]
            clue = contexts[pid]
            result = dict(
                input=place,
                context=clue,
                review_status="UNRESOLVED",
                geometry_ref=None,
                candidates=[],
            )
            if not any(c.isalnum() for c in name):
                result["decision_reason"] = (
                    "INPUT_NOT_SEARCHABLE: original punctuation-only mention retained"
                )
                report["results"].append(result)
                continue
            if place["wikidata_id"]:
                # Re-evaluate exact QID source candidates, not former matching
                # IDs or diagnostic WHG match flags. Reuse verified full shapes.
                entity = entities[pid]
                kind = client.infer_place_type(
                    dict(
                        name=entity["name"],
                        text=entity.get("descriptions", {})
                        .get("en", {})
                        .get("value", ""),
                        attributes=dict(p31=entity.get("direct_types", [])),
                    )
                )
                chosen = None
                for source in client.OVERPASS:
                    path = base / f"geography_sources/first_50_{source.casefold()}.json"
                    native = [
                        c
                        for c in read_json(path)["elements"]
                        if c.get("tags", {}).get("wikidata") == pid
                    ]
                    # Compare at supplied precision, as required by S2T 9.2.
                    prefix = place["selection_date"]
                    eligible = [
                        c
                        for c in native
                        if (
                            not c.get("tags", {}).get("start_date")
                            or c["tags"]["start_date"][: len(prefix)] <= prefix
                        )
                        and (
                            not c.get("tags", {}).get("end_date")
                            or prefix <= c["tags"]["end_date"][: len(prefix)]
                        )
                    ]
                    candidate, reason = client.select_candidate(
                        dict(place_type=kind, selection_date=prefix), eligible
                    )
                    if candidate and client.type_score(kind, candidate) == 2:
                        chosen = source, candidate, reason
                        break
                if (
                    chosen is None
                    or client.osm_key(chosen[1]) != audits[pid]["source_object_id"]
                ):
                    raise ValueError(f"Unexpected exact-QID selection change: {pid}")
                geometry = load_geometry(audits[pid]["geometry_ref"], old)
                result.update(
                    review_status="ACCEPTED_AUTO",
                    source_dataset=chosen[0],
                    source_object_id=client.osm_key(chosen[1]),
                    place_type=kind,
                    decision_reason=chosen[2],
                    match_method="EXACT_QID_DATE_TYPE",
                )
            else:
                # Query the existing approved name services with the literal
                # adjacent parent. No new identity is created from that query.
                if clue["parents"]:
                    query = name + ", " + clue["parents"][0]["value"]
                    for source, url in client.NOMINATIM.items():
                        params = dict(
                            q=query,
                            format="jsonv2",
                            polygon_geojson="1",
                            extratags="1",
                            addressdetails="1",
                            namedetails="1",
                            limit="50",
                        )
                        rows = client.request_json(url + "/search", params=params)
                        if not isinstance(rows, list):
                            raise ValueError("Unexpected name-service response")
                        path = cache / f"{pid}_{source}.json"
                        write(
                            path,
                            dict(
                                query=params,
                                rows=rows,
                                retrieved_at=datetime.now(timezone.utc).isoformat(),
                            ),
                        )
                        source_hashes[str(path)] = digest(path)
                        report["new_requests"] += 1
                        for row in rows:
                            aliases = [row.get("name", "")]
                            for value in row.get("namedetails", {}).values():
                                if isinstance(value, str):
                                    aliases.extend(value.split(";"))
                            candidates[pid].append(
                                dict(
                                    source=url + "/search",
                                    source_id=f"{row.get('osm_type')}:{row.get('osm_id')}",
                                    name=row.get("name"),
                                    aliases=aliases,
                                    address=row.get("address", {}),
                                    feature_code=row.get("type"),
                                    feature_class=row.get("category"),
                                    source_tags=row.get("extratags") or {},
                                    raw_geometry=row.get("geojson"),
                                )
                            )
                        write(
                            output / "progress.json",
                            dict(
                                current=name,
                                completed=len(report["results"]),
                                requests=report["new_requests"],
                            ),
                        )
                        time.sleep(1.1)
                supported = []
                seen = set()
                kinds = {f["value"] for f in clue["features"]}
                for c in candidates[pid]:
                    key = c["source"], c["source_id"]
                    if key in seen:
                        continue
                    seen.add(key)
                    name_ok = exact_alias(name, c.get("aliases", []))
                    type_ok = len(kinds) == 1 and compatible(next(iter(kinds)), c)
                    parent_ok = any(
                        exact_alias(p["value"], parent_labels(c, admin))
                        for p in clue["parents"]
                    )
                    reasons = []
                    if not name_ok:
                        reasons.append("NO_EXACT_RECORDED_NAME_OR_ALIAS")
                    if not type_ok:
                        reasons.append("MISSING_OR_INCOMPATIBLE_INPUT_FEATURE_TYPE")
                    if not parent_ok:
                        reasons.append("NO_VERIFIED_ADJACENT_PARENT_AGREEMENT")
                    if c["source"] == "WHG":
                        reasons.append("WHG_IS_RECONCILIATION_NOT_ORIGINAL_GEOMETRY")
                    tags = c.get("source_tags", {})
                    for tag in ("start_date", "end_date"):
                        value = tags.get(tag)
                        if value and not re.fullmatch(r"\d{4}(?:-\d{2}){0,2}", value):
                            raise ValueError(f"Unsupported source date {tag}: {value}")
                    prefix = place["selection_date"]
                    if (
                        tags.get("start_date")
                        and tags["start_date"][: len(prefix)] > prefix
                    ) or (
                        tags.get("end_date")
                        and tags["end_date"][: len(prefix)] < prefix
                    ):
                        reasons.append(
                            "SOURCE_OUTSIDE_SELECTION_DATE_AT_SUPPLIED_PRECISION"
                        )
                    decision = dict(
                        source=c["source"],
                        source_id=c["source_id"],
                        name=c.get("name"),
                        name_agreement=name_ok,
                        type_agreement=type_ok,
                        parent_agreement=parent_ok,
                        feature_code=c.get("feature_code"),
                        reasons=reasons,
                    )
                    result["candidates"].append(decision)
                    if not reasons:
                        if c["source"] == "GeoNames":
                            geo = Point(*c["coordinate"])
                        elif c.get("raw_geometry"):
                            geo = shape(c["raw_geometry"])
                        else:
                            decision["reasons"].append(
                                "FULL_ORIGINAL_GEOMETRY_NOT_IN_THIS_RECORD"
                            )
                            continue
                        if geo.is_empty or not geo.is_valid:
                            decision["reasons"].append("INVALID_OR_EMPTY_GEOMETRY")
                            continue
                        # GeoNames country files have no validity interval;
                        # undated original-source geometry is eligible under
                        # S2T 9. The same rule applies to undated name responses.
                        supported.append((c, geo))
                geometry = None
                if len(supported) == 1:
                    candidate, geometry = supported[0]
                    result.update(
                        review_status="ACCEPTED_AUTO",
                        source_dataset=candidate["source"],
                        source_object_id=candidate["source_id"],
                        place_type=next(iter(kinds)),
                        match_method="EXACT_NAME_ALIAS_TYPE_PARENT",
                        decision_reason="One original-source object passed exact alias, explicit feature type and independent adjacent parent checks; source undated",
                    )
                elif supported:
                    result["decision_reason"] = (
                        "Multiple supported fallback objects require identity/representation disambiguation"
                    )
                else:
                    result["decision_reason"] = (
                        "No candidate passed exact name/alias, specific feature type, independent parent and original-geometry checks"
                    )
            if geometry is not None:
                result["_geometry"] = geometry
            report["results"].append(result)
            write(
                output / "progress.json",
                dict(
                    current=name,
                    completed=len(report["results"]),
                    requests=report["new_requests"],
                ),
            )
    except Exception as error:
        report.update(
            status="STOPPED_FOR_CONSULTATION",
            error_type=type(error).__name__,
            error=str(error),
        )
        write(output / "stop.json", {k: v for k, v in report.items() if k != "results"})
        write(
            output / "partial_audit.json",
            [
                {k: v for k, v in row.items() if k != "_geometry"}
                for row in report["results"]
            ],
        )
        raise

    accepted = []
    for result in report["results"]:
        geometry = result.pop("_geometry", None)
        if geometry is not None:
            accepted.append(
                dict(
                    place_id=result["input"]["place_id"],
                    name=result["input"]["name"],
                    source_dataset=result["source_dataset"],
                    source_object_id=result["source_object_id"],
                    match_method=result["match_method"],
                    geometry=geometry,
                )
            )
    path = output / "geometries.parquet"
    frame = gpd.GeoDataFrame(accepted, geometry="geometry", crs="EPSG:4326")
    frame.to_parquet(path, index=False)
    geography = []
    for result in report["results"]:
        if result["review_status"] != "ACCEPTED_AUTO":
            continue
        pointer = dict(
            file=path.name, place_id=result["input"]["place_id"], sha256=digest(path)
        )
        geometry = load_geometry(pointer, output)
        expected = frame.loc[frame.place_id == pointer["place_id"]].geometry.iloc[0]
        if not geometry.equals_exact(expected, 0):
            raise ValueError("Shapely round-trip changed")
        result["geometry_ref"] = pointer
        geography.append(
            dict(
                place_id=pointer["place_id"],
                geometry_ref=pointer,
                source_dataset=result["source_dataset"],
                source_object_id=result["source_object_id"],
            )
        )
    if any(digest(Path(p)) != sha for p, sha in protected.items()):
        raise ValueError("Protected input/model artifact changed")
    if [r["input"]["place_id"] for r in report["results"]] != sample_ids:
        raise ValueError("Output identity/order differs")
    report.update(
        status="VERIFIED_AUTOMATIC_TEN_CONTEXT_SAMPLE",
        accepted=len(accepted),
        unresolved=10 - len(accepted),
        name_rule="Existing exact name/recorded alias acceptance; trigram diagnostic not promoted",
        source_sha256=source_hashes,
        main_model_changed=False,
        identity_assignments_changed=False,
        pointers_in_model_only=True,
        protected_sha256=protected,
    )
    write(output / "audit.json", report)
    write(output / "geography.json", geography)
    summary = {
        k: report[k]
        for k in (
            "status",
            "inputs",
            "accepted",
            "unresolved",
            "new_requests",
            "main_model_changed",
            "identity_assignments_changed",
        )
    }
    write(
        output / "verification.json",
        summary
        | dict(
            geometry_roundtrip_exact=True,
            outputs={
                p.name: digest(p)
                for p in output.iterdir()
                if p.is_file() and p.name != "verification.json"
            },
        ),
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.base.resolve(), args.output.resolve())))
