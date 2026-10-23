"""Twenty-input diagnostic of the owner's 45/30/15/7/3 Geography ranking.

Population S2T section 9: preserve identities and the main model. Reuse native
source evidence, not WHG scores or representative points as accepted geometry.
This is a ranked proposal test, not a production acceptance or accuracy test.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import re
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
from pyproj import CRS, Geod, Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform

from .geography_context_sample import compatible, exact_alias
from .geography_coordinate_sample import coordinate
from .geography_local_polygon_sample import date_eligible
from .geography_sample import tools
from .graph_contract import load_geometry
from .poc import ROOT, digest, read_json
from .rebuild_poc import write

PARAMETERS = dict(
    version="geo-ranking-20-experiment-v3",
    weights=dict(qid=45, coordinate=30, context=15, name=7, feature_type=3),
    candidate_only_qid_points=20,
    distance_bands_m=[[1000, 25], [5000, 15], [20000, 5]],
    fuzzy_name_minimum=0.8,
    no_universal_minimum_score=True,
    no_production_assignments=True,
    name_or_qid_required_for_selection=False,
    geonames_containment_context_points=10,
    always_select_available_geometry=True,
    selection="highest_score_then_polygon_then_stable_source_id",
    uncertainty_flags_do_not_exclude=True,
    wikidata_points_compete_by_score=True,
)


def similarity(left: str, right: str) -> float:
    """Reuse the notebook's Unicode trigram Dice despite legacy sibling imports."""
    previous = list(sys.path)
    sys.path.insert(0, str(ROOT / "GG_Data/entity_resolution"))
    try:
        return importlib.import_module("generate_candidates").similarity(left, right)
    finally:
        sys.path[:] = previous


def contains(text: str, term: str) -> bool:
    return bool(
        term and re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I)
    )


def distance_m(geometry, xy: list[float]) -> float:
    """Measure to the actual shape, never its centroid (owner ranking rule).

    Local azimuthal-equidistant projection keeps distance from the anchor in
    metres. Exact containment is checked first. No source shape is modified.
    """
    point = Point(*xy)
    if geometry.covers(point):
        return 0.0
    if geometry.geom_type == "Point":
        return abs(Geod(ellps="WGS84").inv(*xy, geometry.x, geometry.y)[2])
    local = CRS.from_proj4(
        f"+proj=aeqd +lat_0={xy[1]} +lon_0={xy[0]} +datum=WGS84 +units=m"
    )
    project = Transformer.from_crs("EPSG:4326", local, always_xy=True).transform
    result = transform(project, geometry).distance(Point(0, 0))
    if not 0 <= result < float("inf"):
        raise ValueError("Unsupported non-finite shape distance")
    return result


def score(place: dict, evidence: dict, candidate: dict, anchors: list[dict]) -> dict:
    """Apply the approved experimental weights; expose every evidence reason.

    Missing data receives zero, never a redistributed weight. A candidate's
    own P625 is candidate-derived support, not independent identity proof.
    Context uses original text/page and source parent labels without an old
    pre-search parent gate; it does not create new entity or paragraph rows.
    """
    qid = candidate.get("qid")
    qid_points = 45 if qid and qid == place["wikidata_id"] else 0
    if not place["wikidata_id"] and qid in evidence["candidate_qids"]:
        qid_points = 20
    geo = shape(candidate["geometry"]) if candidate.get("geometry") else None
    if geo is not None and (geo.is_empty or not geo.is_valid):
        raise ValueError(f"Invalid source geometry: {candidate['source_id']}")
    checks = []
    for anchor in anchors:
        if geo is None:
            continue
        # Unrelated candidate QIDs must not borrow each other's P625 evidence.
        if anchor["role"] == "CANDIDATE_ONLY" and qid and qid != anchor["qid"]:
            continue
        distance = distance_m(geo, anchor["xy"])
        points = (
            30
            if distance == 0
            else next(
                (
                    points
                    for limit, points in PARAMETERS["distance_bands_m"]
                    if distance <= limit
                ),
                0,
            )
        )
        checks.append(
            dict(
                qid=anchor["qid"],
                role=anchor["role"],
                distance_m=distance,
                points=points,
            )
        )
    coordinate_points = max((c["points"] for c in checks), default=0)
    names = candidate.get("aliases", [])
    sim = max((similarity(place["name"], n) for n in names if n), default=0)
    name_points = 7 if exact_alias(place["name"], names) else 5 if sim >= 0.8 else 0
    # Parent strings from the candidate are tested against input context;
    # they are never treated as independent context merely by existing.
    parents = [
        p for p in candidate.get("parents", []) if p and not exact_alias(p, names)
    ]
    text, title = evidence["text"], evidence["source_page"]
    start = evidence.get("start", 0)
    near = text[max(0, start - 150) : start + len(evidence["original_name"]) + 150]
    matches = [
        dict(
            parent=p,
            near=contains(near, p),
            text=contains(text, p),
            page=contains(title, p)
            or any(
                contains(n, p) for n in evidence.get("same_page_location_names", [])
            ),
        )
        for p in parents
    ]
    context_points = max(
        (
            10 if p["near"] else 7 if p["text"] else 3 if p["page"] else 0
            for p in matches
        ),
        default=0,
    )
    # Owner approval, 22 October: source coordinates can support a containing
    # local polygon. Reuse the existing geographic-context maximum (10), not
    # the Wikidata coordinate weight (30). These are retrieval hypotheses,
    # not independent identity proof, and a Point never validates itself.
    spatial_checks = []
    if geo is not None and geo.geom_type in {"Polygon", "MultiPolygon"}:
        for anchor in evidence.get("geonames_coordinate_context", []):
            covered = geo.covers(Point(*anchor["xy"]))
            spatial_checks.append(anchor | dict(contained=covered))
        if any(c["contained"] for c in spatial_checks):
            context_points = max(
                context_points, PARAMETERS["geonames_containment_context_points"]
            )
    tags = candidate.get("tags", {})
    supplied_dates = {k: tags[k] for k in ("start_date", "end_date") if tags.get(k)}
    temporal_ok = date_eligible(dict(extratags=tags), place["selection_date"])
    historical_points = 5 if supplied_dates and temporal_ok else 0
    kinds = {f["value"] for f in evidence["context"]["features"]}
    type_points = 3 if any(compatible(k, candidate) for k in kinds) else 0
    if (
        not type_points
        and "airport" in kinds
        and candidate.get("feature_code") in {"INSM", "military"}
    ):
        type_points = 2
    components = dict(
        qid=qid_points,
        coordinate=coordinate_points,
        context=context_points + historical_points,
        name=name_points,
        feature_type=type_points,
    )
    reasons = []
    if not temporal_ok:
        reasons.append("OUTSIDE_SELECTION_DATE")
    if place["wikidata_id"] and qid and qid != place["wikidata_id"]:
        reasons.append("DIFFERENT_QID_FOR_DIRECT_PLACE")
    if candidate.get("feature_class") in {"highway"} or candidate.get(
        "feature_code"
    ) in {"road", "track", "path", "footway", "residential", "unclassified"}:
        reasons.append("REVERSE_ROAD_IS_CONTEXT_NOT_TARGET")
    if not any(c.isalnum() for c in place["name"]):
        reasons.append("PUNCTUATION_INPUT")
    return candidate | dict(
        components=components,
        total=sum(components.values()),
        name_similarity=sim,
        coordinate_checks=checks,
        context_matches=matches,
        source_coordinate_context_checks=spatial_checks,
        supplied_dates=supplied_dates,
        uncertainty_flags=reasons,
        geometry_available=geo is not None,
        ranking_is_not_identity_probability=True,
    )


def select_proposal(ranked: list[dict]) -> dict | None:
    """Latest owner rule: an available geometry must never become unresolved.

    The caller supplies score order with stable ties. Keep low scores and
    conflicts as uncertainty metadata, not vetoes. P625 Points now compete
    by score; this explicitly supersedes the earlier source-first fallback.
    Identity IDs stay unchanged even when the selected location is uncertain.
    """
    return next((c for c in ranked if c["geometry_available"]), None)


def coordinate_candidates(entity: dict) -> list[dict]:
    """Owner approval, 22 October: retain every non-deprecated P625 candidate.

    Keep rank and precision in each original statement. The existing ranking
    and stable assertion-ID tie rule select among them; no coordinate average
    or replacement identity is created. Existing Earth/value checks still apply.
    """
    return [
        coordinate(entity | {"claims": {"P625": [claim]}})
        for claim in entity.get("claims", {}).get("P625", [])
        if claim.get("rank") != "deprecated"
    ]


def native_candidate(row: dict, source: str, receipt: str) -> dict:
    """Nominatim source geometry and tags, with the complete receipt retained."""
    aliases = [row.get("name", "")]
    for v in (row.get("namedetails") or {}).values():
        if isinstance(v, str):
            aliases.extend(v.split(";"))
    tags = row.get("extratags") or {}
    return dict(
        source=source,
        source_id=f"{row['osm_type']}:{row['osm_id']}",
        name=row.get("name", ""),
        aliases=aliases,
        qid=tags.get("wikidata"),
        feature_code=row.get("type"),
        feature_class=row.get("category", row.get("class")),
        address_type=row.get("addresstype"),
        parents=[
            v
            for k, v in (row.get("address") or {}).items()
            if k not in {"postcode", "country_code", "road", "house_number"}
        ],
        tags=tags,
        geometry=row.get("geojson"),
        receipt=receipt,
    )


def wide_approximation(place: dict, candidate: dict) -> bool:
    """S2T 9.2: exclude country/larger substitutes, not country entities.

    Use explicit native scope metadata only. Do not introduce an area/radius
    cutoff. A source identifying the target itself is not an approximation.
    """
    level = str(candidate.get("tags", {}).get("admin_level", ""))
    wide = (
        candidate.get("feature_code")
        in {
            "country",
            "continent",
            "PCLI",
            "PCL",
            "PCLD",
            "PCLF",
            "PCLH",
            "PCLIX",
            "PCLS",
            "CONT",
        }
        or candidate.get("address_type") in {"country", "continent"}
        or (level.isdigit() and int(level) <= 2)
    )
    same_target = bool(
        place["wikidata_id"] and candidate.get("qid") == place["wikidata_id"]
    ) or exact_alias(place["name"], candidate.get("aliases", []))
    return bool(wide and not same_target)


def run(
    output: Path,
    request_cache: Path | None = None,
    comparison: Path | None = None,
    *,
    base_dir: Path | None = None,
) -> dict:
    """Rank fixed tests, or new-model LOC targets with the same S2T 9.7 rule.

    Population mode has no dependency on hand-reviewed sample candidates.
    It uses the freshly prepared source queries and snapshot candidate records.
    """
    started = time.perf_counter()
    root = ROOT / "GG_Data/pipeline/outputs"
    base, comp = (
        root / "rebuild_page_scope_20261022",
        root / "geography_comparison_40_20261022",
    )
    population = base_dir is not None
    if population:
        if comparison is None:
            raise ValueError("New-model ranking requires its own source comparison")
        base = base_dir
    if comparison:
        comp = comparison
        if read_json(comp / "progress.json")["status"] != "RETRIEVED":
            raise ValueError("Wider sample source retrieval is incomplete")
        for filename, sha in read_json(comp / "plan.json")["inputs"].items():
            if digest(Path(filename)) != sha:
                raise ValueError(f"Frozen comparison input changed: {filename}")
    prior = root / "geography_coordinate_10_20261022_points_applied"
    diagnostic = root / "geography_context_evidence_5_20261022"
    if output.exists():
        raise ValueError("Preserve prior experiment; choose a new output directory")
    output.mkdir(parents=True)
    cache = output / "sources"
    cache.mkdir()
    original = (
        read_json(prior / "audit.json") if not population else {"protected_sha256": {}}
    )
    protected = dict(original["protected_sha256"])
    for folder in (
        (comp, request_cache)
        if population
        else (prior, comp, diagnostic, request_cache)
    ):
        if folder is None:
            continue
        for p in folder.rglob("*"):
            if p.is_file():
                protected[str(p)] = digest(p)
    all_sample = read_json(comp / "sample.json")
    sample = (
        all_sample
        if comparison
        else all_sample[:10] + all_sample[10:15] + all_sample[25:30]
    )
    if len({p["place_id"] for p in sample}) != len(sample):
        raise ValueError("Expected distinct preserved identities")
    write(output / "sample.json", sample)
    write(
        output / "parameters.json",
        PARAMETERS | {"no_production_assignments": not population},
    )
    evidence = read_json(comp / "evidence.json")
    # Use the full native snapshot records already selected by the pipeline.
    raw_path = base / "entities/full_records.json.gz"
    protected[str(raw_path)] = digest(raw_path)
    records = {q: r["entity"] for q, r in read_json(raw_path).items()}
    candidate_cache = (
        comp / "candidate_records.json.gz"
        if population
        else (
            root
            / "wikidata_full_cache/1c8841ce530789458d059e9f8b92254f0fb0835e46a32301852d69b8aa00a8ce.json.gz"
        )
    )
    protected[str(candidate_cache)] = digest(candidate_cache)
    if population:
        if (
            digest(candidate_cache)
            != read_json(comp / "candidate_records_report.json")["outputs"][
                candidate_cache.name
            ]
        ):
            raise ValueError("Geography candidate coordinate records changed")
        for qid, r in read_json(candidate_cache).items():
            records.setdefault(qid, r["entity"])
    else:
        for r in read_json(candidate_cache)["rows"]:
            records.setdefault(r["id"], json.loads(r["item"].rstrip(",\r\n ")))
    crabs = (
        read_json(diagnostic / "crabs_wikidata_coordinate.json")
        if not population
        else {}
    )
    saved_crabs = crabs.get("coordinate", {})
    anchors_extra = {saved_crabs["qid"]: saved_crabs} if saved_crabs else {}
    analysis = (
        read_json(base / "geography_candidate_analysis/candidate_review.json")
        if not population
        else {"reviews": []}
    )
    reviews = {r["place_id"]: r for r in analysis["reviews"]}
    for p in sample:
        if p["place_id"] in reviews:
            reviews[p["place_id"]]["candidates"].extend(
                analysis["additional_cached_alias_search"].get(p["name"], [])
            )
    whg = []
    for arm in ("native", "existing_dated"):
        whg.append(read_json(comp / f"sources/whg_{arm}.json")["response"])
    mentions_path = base / "mentions_pages/mentions.json.gz"
    protected[str(mentions_path)] = digest(mentions_path)
    mentions = read_json(mentions_path)
    by_mid = {m["mention_id"]: m for m in mentions}
    candidates = {p["place_id"]: [] for p in sample}
    anchors = {}
    for p in sample:
        pid = p["place_id"]
        ev = evidence[pid]
        mention = by_mid[ev["mention_id"]]
        ev["same_page_location_names"] = sorted(
            {
                m["word"]
                for m in mentions
                if m["entity_group"] == "LOC"
                and (m["wiki_site"], m["wiki_page_id"])
                == (mention["wiki_site"], mention["wiki_page_id"])
            }
        )
        ev["start"] = mention["start"]
        linked = {
            r["id"].split(":")[-1]
            for arm in whg
            for r in arm.get(pid, {}).get("result", [])
            if r["id"].startswith("place:wd:")
            and max(
                (
                    similarity(p["name"], n)
                    for n in [r["name"], *r.get("alt_names", [])]
                ),
                default=0,
            )
            >= 0.8
        }
        # The saved Crabs spelling candidate is included by the same >=80% rule.
        for c in reviews.get(pid, {}).get("candidates", []):
            if (
                c["source_id"].startswith("place:wd:")
                and max(
                    (similarity(p["name"], n) for n in c.get("aliases", [])), default=0
                )
                >= 0.8
            ):
                linked.add(c["source_id"].split(":")[-1])
        ev["candidate_qids"] = sorted(linked)
        anchors[pid] = []
        qids = [p["wikidata_id"]] if p["wikidata_id"] else sorted(linked)
        for q in qids:
            available = (
                [anchors_extra[q]]
                if q in anchors_extra
                else coordinate_candidates(records.get(q, {}))
            )
            for a in available:
                anchors[pid].append(
                    a
                    | dict(
                        role="MATCHED_INPUT" if p["wikidata_id"] else "CANDIDATE_ONLY"
                    )
                )
                native = records.get(q, {})
                labels = [v["value"] for v in native.get("labels", {}).values()]
                labels += [
                    a["value"]
                    for rows in native.get("aliases", {}).values()
                    for a in rows
                ]
                if q == saved_crabs.get("qid"):
                    labels += [v["value"] for v in crabs["labels"].values()]
                parents = [
                    v["value"]
                    for prop in ("P17", "P131")
                    for claim in native.get("claims", {}).get(prop, [])
                    for parent in [
                        claim.get("mainsnak", {})
                        .get("datavalue", {})
                        .get("value", {})
                        .get("id")
                    ]
                    for v in records.get(parent, {}).get("labels", {}).values()
                ]
                candidates[pid].append(
                    dict(
                        source="Wikidata",
                        source_id=a["statement"].get("id", q),
                        name=labels[0] if labels else q,
                        aliases=labels,
                        qid=q,
                        parents=parents,
                        tags={},
                        geometry=mapping(Point(*a["xy"])),
                        receipt=(
                            str(candidate_cache)
                            if not p["wikidata_id"]
                            else str(raw_path)
                        ),
                        coordinate_fallback=True,
                    )
                )
        for c in reviews.get(pid, {}).get("candidates", []):
            if c["source"] == "GeoNames":
                candidates[pid].append(
                    c
                    | dict(
                        qid=None,
                        parents=[],
                        tags={},
                        geometry=mapping(Point(*c["coordinate"])),
                        receipt=str(
                            base / "geography_candidate_analysis/candidate_review.json"
                        ),
                    )
                )
        for arm in whg:
            for c in arm.get(pid, {}).get("result", []):
                candidates[pid].append(
                    dict(
                        source="WHG",
                        source_id=c["id"],
                        name=c["name"],
                        aliases=[c["name"], *c.get("alt_names", [])],
                        qid=(
                            c["id"].split(":")[-1]
                            if c["id"].startswith("place:wd:")
                            else None
                        ),
                        parents=[],
                        tags={},
                        geometry=None,
                        receipt=str(comp / "sources"),
                    )
                )
    if not population:
        # Reuse all original per-input Nominatim results, including zero-result
        # searches, reverse evidence and the wider-context diagnostic. No global
        # cache name join is allowed to associate a result with a different input.
        old = read_json(base / "geography_sample/audit.json")
        for row in old["results"]:
            pid = row["input"]["place_id"]
            if pid not in candidates:
                continue
            for filename in row.get("name_source_files", []):
                path = Path(filename)
                if not path.is_absolute():
                    path = ROOT / path
                data = read_json(path)
                protected[str(path)] = digest(path)
                for r in data["rows"]:
                    candidates[pid].append(
                        native_candidate(r, data.get("source", "Nominatim"), str(path))
                    )
        for row in read_json(diagnostic / "retrieval.json")["results"]:
            if row["place_id"] not in candidates:
                continue
            for r in row["rows"]:
                if r.get("osm_id"):
                    candidates[row["place_id"]].append(
                        native_candidate(r, "OpenStreetMap", row["source_file"])
                    )
        for row in original["results"]:
            pid = row["input"]["place_id"]
            if pid not in candidates:
                continue
            if row.get("geometry_ref"):
                geo = load_geometry(row["geometry_ref"], prior)
                candidates[pid].append(
                    dict(
                        source=row["source_dataset"],
                        source_id=row["source_object_id"],
                        name=row["input"]["name"],
                        aliases=[row["input"]["name"]],
                        qid=row["input"]["wikidata_id"],
                        geometry=mapping(geo),
                        parents=[],
                        tags={},
                        receipt=str(prior / "audit.json"),
                        prior_selected_geometry=True,
                    )
                )
    # Reuse original GN records, not WHG representative points as geometry.
    wanted_gn = {
        c["source_id"].split(":")[-1]
        for rows in candidates.values()
        for c in rows
        if c["source_id"].startswith("place:gn:")
    }
    gn_records, admin = {}, {}
    for archive in sorted((ROOT / "GG_Data/geocoding/cache/geonames").glob("*.zip")):
        protected[str(archive)] = digest(archive)
        with zipfile.ZipFile(archive) as zipped, zipped.open(
            archive.stem + ".txt"
        ) as stream:
            for line in stream:
                f = line.decode("utf-8").rstrip("\r\n").split("\t")
                aliases = [f[1], f[2], *f[3].split(",")]
                if f[7] in {"PCLI", "ADM1"}:
                    admin[(f[8], "" if f[7] == "PCLI" else f[10])] = aliases
                if f[0] in wanted_gn:
                    gn_records[f[0]] = dict(
                        source="GeoNames",
                        source_id=f[0],
                        name=f[1],
                        aliases=aliases,
                        qid=None,
                        parents=[],
                        tags={},
                        feature_class=f[6],
                        feature_code=f[7],
                        country_code=f[8],
                        admin1=f[10],
                        geometry=mapping(Point(float(f[5]), float(f[4]))),
                        receipt=str(archive),
                        native_fields=f,
                    )
    for rows in candidates.values():
        for c in list(rows):
            if c["source_id"].startswith("place:gn:"):
                native = gn_records.get(c["source_id"].split(":")[-1])
                if native:
                    rows.append(dict(native))
        for c in rows:
            if c["source"] == "GeoNames":
                c["parents"] = admin.get((c.get("country_code"), ""), []) + admin.get(
                    (c.get("country_code"), c.get("admin1")), []
                )
            for prop in ("P17", "P131"):
                for claim in (
                    records.get(c.get("qid"), {}).get("claims", {}).get(prop, [])
                ):
                    parent = (
                        claim.get("mainsnak", {})
                        .get("datavalue", {})
                        .get("value", {})
                        .get("id")
                    )
                    c.setdefault("parents", []).extend(
                        v["value"]
                        for v in records.get(parent, {}).get("labels", {}).values()
                    )
    client = tools()
    request_count = 0
    reused_requests = 0
    # S2T 9: reuse a receipt only when the complete endpoint and parameters
    # agree. This is request reuse, never an identity/name join across inputs.
    request_index = {}
    if population:
        folders = sorted(root.glob("geography_ranking*"))
        if request_cache:
            folders.append(request_cache)
        for folder in folders:
            for path in sorted(folder.rglob("*.json")):
                if path.parent.name != "sources":
                    continue
                saved = read_json(path)
                if (
                    isinstance(saved, dict)
                    and {"url", "params", "response"} <= saved.keys()
                ):
                    key = json.dumps([saved["url"], saved["params"]], sort_keys=True)
                    request_index.setdefault(key, path)

    def fetch(
        kind: str, params: dict, source: str = "OpenStreetMap"
    ) -> tuple[list[dict], str]:
        nonlocal request_count, reused_requests
        params = (
            dict(
                format="jsonv2",
                polygon_geojson="1",
                extratags="1",
                namedetails="1",
                addressdetails="1",
            )
            | params
        )
        path = cache / f"{request_count:02d}_{kind}.json"
        url = client.NOMINATIM[source] + "/" + kind
        previous = request_cache / path.name if request_cache else None
        if population:
            key = json.dumps([url, params], sort_keys=True)
            path = cache / (hashlib.sha256(key.encode()).hexdigest() + ".json")
            previous = request_index.get(key)
        if previous and previous.exists():
            saved = read_json(previous)
            if saved["url"] != url or saved["params"] != params:
                raise ValueError("Cached request differs from experiment")
            protected[str(previous)] = digest(previous)
            payload = saved["response"]
            reused_requests += 1
        else:
            payload = client.request_json(url, params=params)
            saved = dict(
                url=url,
                params=params,
                response=payload,
                retrieved_at=datetime.now(timezone.utc).isoformat(),
            )
            time.sleep(1.1)
        write(path, saved)
        if population:
            request_index[key] = path
        request_count += 1
        if kind == "reverse" and isinstance(payload, dict):
            return ([payload] if payload.get("osm_id") else []), str(path)
        if not isinstance(payload, list):
            raise ValueError("Unexpected Nominatim response")
        return payload, str(path)

    # Existing exact-QID source inventory; one native lookup for all new OSM
    # objects. Full geometry remains required; tag centres are never shapes.
    inventory = read_json(comp / "sources/first_50_openstreetmap.json")["response"][
        "elements"
    ]
    fresh_sample = sample if comparison else sample[10:]
    new_ids = {p["place_id"] for p in fresh_sample}
    objects = [e for e in inventory if e.get("tags", {}).get("wikidata") in new_ids]
    # Nominatim lookup accepts at most 50 native object IDs per request.
    for offset in range(0, len(objects), 50):
        rows, receipt = fetch(
            "lookup",
            dict(
                osm_ids=",".join(
                    {"node": "N", "way": "W", "relation": "R"}[e["type"]] + str(e["id"])
                    for e in objects[offset : offset + 50]
                )
            ),
        )
        for r in rows:
            q = (r.get("extratags") or {}).get("wikidata")
            if q in candidates:
                candidates[q].append(native_candidate(r, "OpenStreetMap", receipt))
    for index, p in enumerate(fresh_sample, 1):
        pid = p["place_id"]
        rows, receipt = fetch("search", dict(q=p["name"], limit="10"))
        for r in rows:
            candidates[pid].append(native_candidate(r, "OpenStreetMap", receipt))
        for a in anchors[pid]:
            rows, receipt = fetch(
                "reverse", dict(lon=str(a["xy"][0]), lat=str(a["xy"][1]))
            )
            for r in rows:
                candidates[pid].append(native_candidate(r, "OpenStreetMap", receipt))
        write(
            output / "progress.json",
            dict(
                status="RETRIEVING",
                completed_new_inputs=index,
                total_inputs=len(fresh_sample),
                requests=request_count,
            ),
        )
    if comparison:
        # S2T 9: both approved exact-QID inventories need native geometries.
        # Historical tag centres are not polygons and must not become shapes.
        # Place this after existing requests so a saved OSM run replays exactly.
        historical = read_json(comp / "sources/first_50_openhistoricalmap.json")[
            "response"
        ]["elements"]
        for offset in range(0, len(historical), 50):
            rows, receipt = fetch(
                "lookup",
                dict(
                    osm_ids=",".join(
                        {"node": "N", "way": "W", "relation": "R"}[e["type"]]
                        + str(e["id"])
                        for e in historical[offset : offset + 50]
                    )
                ),
                source="OpenHistoricalMap",
            )
            for row in rows:
                qid = (row.get("extratags") or {}).get("wikidata")
                if qid in candidates:
                    candidates[qid].append(
                        native_candidate(row, "OpenHistoricalMap", receipt)
                    )
    for p in sample:
        pid = p["place_id"]
        # Keep input-local source links; never join another input's candidates
        # by a global name. Preserve all source hypotheses rather than silently
        # resolving GeoNames identity or replacing a synthetic entity's ID.
        context_points = {}
        for c in candidates[pid]:
            if c["source"] == "GeoNames" and c.get("geometry"):
                geometry = shape(c["geometry"])
                if geometry.geom_type == "Point":
                    context_points[c["source_id"]] = dict(
                        source="GeoNames",
                        source_id=c["source_id"],
                        name=c["name"],
                        xy=[geometry.x, geometry.y],
                        receipt=c["receipt"],
                        identity_status="CANDIDATE_ONLY",
                    )
        evidence[pid]["geonames_coordinate_context"] = list(context_points.values())
    write(
        output / "evidence.json",
        {p["place_id"]: evidence[p["place_id"]] for p in sample},
    )
    write(output / "coordinates.json", anchors)
    write(output / "candidates.json", candidates)
    results, proposals = [], []
    for p in sample:
        pid = p["place_id"]
        ranked = [score(p, evidence[pid], c, anchors[pid]) for c in candidates[pid]]
        if population:
            for c in ranked:
                if wide_approximation(p, c):
                    c["geometry_available"] = False
                    c["uncertainty_flags"].append(
                        "COUNTRY_OR_LARGER_APPROXIMATION_EXCLUDED"
                    )
        # Deduplicate by source/object while preserving the richest observation.
        unique = {}
        for c in ranked:
            key = (c["source"], c["source_id"])
            if key not in unique or (c["geometry_available"], c["total"]) > (
                unique[key]["geometry_available"],
                unique[key]["total"],
            ):
                unique[key] = c
        ranked = sorted(
            unique.values(),
            key=lambda c: (
                -c["total"],
                not (c.get("geometry") or {}).get("type", "").endswith("Polygon"),
                c["source"],
                c["source_id"],
            ),
        )
        chosen = select_proposal(ranked)
        results.append(
            dict(
                input=p,
                ranking=ranked,
                proposed=chosen,
                status="RANKED_PROPOSAL" if chosen else "NO_ELIGIBLE_SOURCE_GEOMETRY",
                anchors_available=len(anchors[pid]),
            )
        )
        if chosen:
            proposals.append(
                dict(
                    place_id=pid,
                    name=p["name"],
                    source=chosen["source"],
                    source_id=chosen["source_id"],
                    total=chosen["total"],
                    geometry=shape(chosen["geometry"]),
                )
            )
    path = output / "proposed_geometries.parquet"
    frame = gpd.GeoDataFrame(proposals, geometry="geometry", crs="EPSG:4326")
    frame.to_parquet(path, index=False)
    restored = gpd.read_parquet(path)
    assert len(restored) == len(proposals)
    assert all(a.equals_exact(b, 0) for a, b in zip(frame.geometry, restored.geometry))
    # S2T 9.7: verify the owner's central rule over the complete denominator.
    with_geometry = sum(
        any(c["geometry_available"] for c in r["ranking"]) for r in results
    )
    if len(results) != len(sample) or with_geometry != len(proposals):
        raise ValueError("Lost input or an available geometry was left unresolved")
    with (output / "results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "place_id",
                "input_name",
                "wikidata_id",
                "source_page",
                "status",
                "selected_name",
                "source",
                "source_id",
                "geometry_type",
                "score",
                "qid",
                "coordinate",
                "context",
                "name",
                "feature_type",
                "uncertainty_flags",
                "geometry_candidates",
                "wikidata_coordinates",
            ],
        )
        writer.writeheader()
        for result in results:
            p, chosen = result["input"], result["proposed"]
            writer.writerow(
                dict(
                    place_id=p["place_id"],
                    input_name=p["name"],
                    wikidata_id=p["wikidata_id"],
                    source_page=evidence[p["place_id"]]["source_page"],
                    status=result["status"],
                    selected_name=chosen["name"] if chosen else None,
                    source=chosen["source"] if chosen else None,
                    source_id=chosen["source_id"] if chosen else None,
                    geometry_type=chosen["geometry"]["type"] if chosen else None,
                    score=chosen["total"] if chosen else None,
                    **(chosen["components"] if chosen else {}),
                    uncertainty_flags=json.dumps(
                        chosen["uncertainty_flags"] if chosen else []
                    ),
                    geometry_candidates=sum(
                        c["geometry_available"] for c in result["ranking"]
                    ),
                    wikidata_coordinates=result["anchors_available"],
                )
            )
    for name, sha in protected.items():
        if digest(Path(name)) != sha:
            raise ValueError(f"Protected input changed: {name}")
    summary = dict(
        status=(
            "VERIFIED_RANKING_PROPOSALS"
            if comparison
            else "VERIFIED_TWENTY_RANKING_PROPOSALS"
        ),
        inputs=len(sample),
        original=0 if comparison else 10,
        new=len(fresh_sample),
        geometry_proposals=len(proposals),
        no_geometry_proposal=len(sample) - len(proposals),
        requests=request_count,
        new_requests=request_count - reused_requests,
        reused_requests=reused_requests,
        elapsed_seconds=time.perf_counter() - started,
        main_model_changed=False,
        identity_assignments_changed=False,
        accepted_geometry_assignments=0,
        inputs_with_available_geometry=with_geometry,
        avoidable_unresolved=with_geometry - len(proposals),
        selected_sources=dict(Counter(p["source"] for p in proposals)),
        geometry_types=dict(Counter(p["geometry"].geom_type for p in proposals)),
        selected_zero_score=sum(p["total"] == 0 for p in proposals),
    )
    write(
        output / "audit.json",
        dict(summary=summary, results=results, protected_sha256=protected),
    )
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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--request-cache", type=Path)
    parser.add_argument("--comparison", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.request_cache, args.comparison)))
