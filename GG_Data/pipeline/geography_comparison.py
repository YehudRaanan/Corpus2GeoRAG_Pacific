"""Bounded Geography comparison approved 22 October 2026; never populate the model.

Population S2T section 9 and GEOCODING_HIGH_LEVEL_PROCESS.md govern identities,
sources, dates and geometry. This experiment compares the existing conservative
selector with WHG's native reconciliation candidates. WHG scores/flags are NOT
acceptance probabilities. No new score threshold, entity, QID or geometry is
assigned. The published WHG workflow requires context and review; measure those
gaps instead of silently converting its top result into an accepted location.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
import urllib.request
from urllib.parse import urlencode
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .geography_context_sample import context, exact_alias
from .poc import digest, read_json
from .rebuild_poc import write

SEED = 20261022
ENDPOINT = "https://whgazetteer.org/reconcile"
DOC = "https://docs.whgazetteer.org/content/technical/apis.html"


def sample_targets(targets: list[dict], originals: list[dict]) -> list[dict]:
    """Freeze 10 regression inputs + 15 random QID and 15 random SYN inputs.

    Stratification deliberately stresses unresolved inputs; this is not an
    estimate of the population-wide match rate. Never exclude poor input names.
    """
    if len(originals) != 10 or len({r["place_id"] for r in originals}) != 10:
        raise ValueError("Expected the original ten distinct identities")
    ids = {r["place_id"] for r in originals}
    rng = random.Random(SEED)
    selected = [r | {"cohort": "original_10"} for r in originals]
    for synthetic in (False, True):
        pool = sorted(
            (
                r
                for r in targets
                if r["place_id"] not in ids
                and r["place_id"].startswith("SYN_") == synthetic
            ),
            key=lambda r: r["place_id"],
        )
        selected.extend(
            r | {"cohort": "random_synthetic" if synthetic else "random_qid"}
            for r in rng.sample(pool, 15)
        )
    if len({r["place_id"] for r in selected}) != 40:
        raise ValueError("Comparison inputs are not distinct")
    return selected


def claims(entity: dict, prop: str) -> list:
    """Read saved snapshot evidence, never look up replacement identities."""
    raw = entity.get("raw_reference", {}).get("full", {}).get("entity", {})
    return raw.get("claims", {}).get(prop, []) or entity.get("attributes", {}).get(
        "supplied_property_claims", {}
    ).get(prop, [])


def values(entity: dict, prop: str) -> list:
    return [
        c["mainsnak"]["datavalue"]["value"]
        for c in claims(entity, prop)
        if c.get("mainsnak", {}).get("snaktype") == "value"
        and "datavalue" in c["mainsnak"]
    ]


def query_for(place: dict, countries: list[str], dated: bool) -> dict:
    """Use native fields, not concatenated parent strings or invented types.

    The dated arm reproduces the existing WHG query. The native arm leaves
    acquisition dates unfiltered because WHG documents modern record-date
    exclusions. Both are candidate diagnostics only: actual source geometry
    validity still requires S2T checks. No date rule is changed in production.
    """
    result = dict(query=place["name"], mode="fuzzy", limit=10)
    if dated:
        year = int(place["selection_date"][:4])
        result.update(start=year, end=year, undated=True, temporal_mode="definitely")
    elif countries:
        result["countries"] = countries
    return result


def prepare(base: Path, output: Path, frozen_sample: Path | None = None) -> dict:
    if output.exists():
        raise ValueError("Preserve prior comparison; use a new output directory")
    files = [
        base / "geography_inputs/targets.json",
        base / "geography_inputs/report.json",
        base / "geography_sample/sample.json",
        base / "geography_context_parent_checked/verification.json",
        base / "geography_context_parent_checked/audit.json",
        base / "model_qid_name/entities.json.gz",
        base / "model_qid_name/manifest.json",
        base / "mentions_pages/mentions.json.gz",
    ]
    inputs = {str(p): digest(p) for p in files}
    original_dir = base / "geography_context_parent_checked"
    verification = read_json(original_dir / "verification.json")
    for name, expected in verification["outputs"].items():
        path = original_dir / name
        if digest(path) != expected:
            raise ValueError(f"Changed original sample: {path}")
        inputs[str(path)] = expected
    manifest = read_json(base / "model_qid_name/manifest.json")
    if (
        digest(base / "model_qid_name/entities.json.gz")
        != manifest["outputs"]["entities.json.gz"]
    ):
        raise ValueError("Model entities differ from the saved manifest")
    targets = read_json(files[0])
    sample = (
        read_json(frozen_sample)
        if frozen_sample
        else sample_targets(targets, read_json(files[2]))
    )
    if frozen_sample:
        # S2T 9: a wider test uses existing LOC rows, never invented identities.
        inputs[str(frozen_sample)] = digest(frozen_sample)
        target_by_id = {r["place_id"]: r for r in targets}
        if len({r["place_id"] for r in sample}) != len(sample) or any(
            r != target_by_id.get(r["place_id"]) for r in sample
        ):
            raise ValueError("Frozen sample differs from the existing LOC targets")
    entities = {
        e["entity_id"]: e
        for e in read_json(base / "model_qid_name/entities.json.gz")
        if e["type"] == "LOC"
    }
    mentions = {
        m["mention_id"]: m for m in read_json(base / "mentions_pages/mentions.json.gz")
    }
    queries = {"existing_dated": {}, "native": {}}
    evidence = {}
    for place in sample:
        pid = place["place_id"]
        entity = entities[pid]
        mid = (
            place.get("original_mention_id") or place["source_context"][0]["mention_id"]
        )
        mention = mentions[mid]
        clue = context(mention)
        country_qids = sorted(
            {
                v["id"]
                for v in values(entity, "P17")
                if isinstance(v, dict) and "id" in v
            }
        )
        # Reuse only already saved ISO codes. Never infer a country from a
        # page title, candidate coordinates, or a country-name lookup result.
        codes = sorted(
            {
                v
                for qid in country_qids
                for v in values(entities.get(qid, {}), "P297")
                if isinstance(v, str) and re.fullmatch(r"[A-Z]{2}", v)
            }
        )
        # Several historical country claims or incomplete code coverage do
        # not establish one safe scope. Retain evidence without choosing one.
        safe_codes = codes if len(country_qids) == len(codes) == 1 else []
        evidence[pid] = dict(
            mention_id=mid,
            original_name=mention["word"],
            source_page=mention["Source"],
            wiki_site=mention["wiki_site"],
            wiki_page_id=mention["wiki_page_id"],
            text=mention["Text"],
            context=clue,
            country_qids=country_qids,
            country_codes_used=safe_codes,
            expected_geonames_ids=sorted(str(v) for v in values(entity, "P1566")),
            japanese_label=entity.get("labels", {}).get("ja", {}).get("value"),
            reference_is_saved_matching_not_gold=True,
        )
        if any(c.isalnum() for c in place["name"]):
            for arm in queries:
                queries[arm][pid] = query_for(
                    place, safe_codes, arm == "existing_dated"
                )
    output.mkdir(parents=True)
    (output / "sources").mkdir()
    write(output / "sample.json", sample)
    write(output / "evidence.json", evidence)
    write(output / "queries.json", queries)
    plan = dict(
        status="PREPARED",
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=None if frozen_sample else SEED,
        input_count=len(sample),
        population_count=len(targets),
        cohorts=dict(Counter(p.get("cohort", "new_random") for p in sample)),
        source_languages=dict(Counter(e["wiki_site"] for e in evidence.values())),
        query_counts={k: len(v) for k, v in queries.items()},
        country_scoped=sum(bool(e["country_codes_used"]) for e in evidence.values()),
        acceptance_thresholds_added=False,
        identities_changed=False,
        model_population=False,
        geometry_population=False,
        documents=["docs/SOURCES_TO_ENTITY_DATA_MODEL_S2T.md section 9", DOC],
        inputs=inputs,
        outputs={
            n: digest(output / n)
            for n in ["sample.json", "evidence.json", "queries.json"]
        },
    )
    write(output / "plan.json", plan)
    return plan


def validate_response(payload: object, queries: dict) -> None:
    """A missing query is a failed response, never a zero-candidate result."""
    if not isinstance(payload, dict) or not set(queries) <= payload.keys():
        raise ValueError("WHG response omits requested query IDs")
    for key in queries:
        row = payload[key]
        if not isinstance(row, dict) or not isinstance(row.get("result"), list):
            raise ValueError(f"Malformed WHG result: {key}")
        if row.get("error") or row.get("errors"):
            raise ValueError(f"WHG query error: {key}")
        for candidate in row["result"]:
            if not isinstance(candidate, dict) or not isinstance(
                candidate.get("id"), str
            ):
                raise ValueError(f"Malformed WHG candidate: {key}")


def retrieve(output: Path) -> dict:
    """Cache full native responses. Stop on source failures; no silent retry."""
    from .geography_sample import tools

    client = tools()
    # Existing credential accessor: read only this service's setting, never log
    # it or serialize request headers. This is the already agreed WHG source.
    import importlib

    legacy = importlib.import_module("GEO_OBJECT_EXTRACTION_POC")
    plan = read_json(output / "plan.json")
    for name, expected in plan["outputs"].items():
        if digest(output / name) != expected:
            raise ValueError(f"Changed frozen input: {name}")
    queries = read_json(output / "queries.json")
    progress = dict(status="RETRIEVING", completed_arms=[], requests=0, reused=0)
    write(output / "progress.json", progress)
    started = time.perf_counter()
    try:
        for arm, batch in queries.items():
            path = output / "sources" / f"whg_{arm}.json"
            if path.exists():
                saved = read_json(path)
                if saved["queries"] != batch:
                    raise ValueError("Cached WHG query differs from frozen query")
                validate_response(saved["response"], batch)
                progress["reused"] += 1
            else:
                request = urllib.request.Request(
                    ENDPOINT,
                    data=json.dumps({"queries": batch}).encode(),
                    headers={
                        "Authorization": f"Bearer {legacy.env_value('WHG_key')}",
                        "Content-Type": "application/json",
                        "User-Agent": legacy.USER_AGENT,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=60) as response:
                    raw = response.read()
                # Preserve the response before interpretation; malformed JSON
                # must remain evidence of a failure, not become an empty cache.
                path.with_suffix(".response").write_bytes(raw)
                payload = json.loads(raw)
                validate_response(payload, batch)
                write(
                    path,
                    dict(
                        queries=batch,
                        response=payload,
                        retrieved_at=datetime.now(timezone.utc).isoformat(),
                    ),
                )
                progress["requests"] += 1
            progress["completed_arms"].append(arm)
            write(output / "progress.json", progress)
        # Reuse the current exact-QID source client in an isolated cache. Its
        # tag responses support baseline checks, not completed geometry rows.
        sample = read_json(output / "sample.json")
        qids = sorted(p["wikidata_id"] for p in sample if p["wikidata_id"])
        client.CACHE = output / "sources"
        for source in client.OVERPASS:
            path = client.CACHE / f"first_50_{source.casefold()}.json"
            existed = path.exists()
            if existed:
                saved = read_json(path)
                if saved["qids"] != qids:
                    raise ValueError("Exact-QID cache has different targets")
                response = saved["response"]
            else:
                # Same batch query as cached_overpass, but retain the complete
                # source response: a timeout 'remark' must not become zero hits.
                pattern = "|".join(qids)
                query = f'[out:json][timeout:45];nwr["wikidata"~"^({pattern})$"];out tags center;'
                request = urllib.request.Request(
                    client.OVERPASS[source],
                    data=urlencode({"data": query}).encode(),
                    headers={"User-Agent": legacy.USER_AGENT},
                )
                with urllib.request.urlopen(request, timeout=60) as handle:
                    raw = handle.read()
                path.with_suffix(".response").write_bytes(raw)
                response = json.loads(raw)
                write(
                    path,
                    dict(
                        qids=qids,
                        query=query,
                        response=response,
                        retrieved_at=datetime.now(timezone.utc).isoformat(),
                    ),
                )
            if response.get("remark") or not isinstance(response.get("elements"), list):
                raise ValueError(f"Incomplete exact-QID response: {source}")
            elements = response["elements"]
            if any(e.get("tags", {}).get("wikidata") not in qids for e in elements):
                raise ValueError("Exact-QID query returned an out-of-scope object")
            progress["reused" if existed else "requests"] += 1
            progress["completed_arms"].append(source)
            write(output / "progress.json", progress)
        progress["status"] = "RETRIEVED"
    except Exception as exc:
        progress.update(
            status="STOPPED_FOR_CONSULTATION",
            error_type=type(exc).__name__,
            error=str(exc),
        )
    progress["elapsed_seconds"] = time.perf_counter() - started
    write(output / "progress.json", progress)
    return progress


def candidate_profile(rows: list[dict], expected: set[str], name: str) -> dict:
    """Measure candidate evidence, never turn WHG rank into an assignment.

    Distinct tied IDs can be duplicates or different places. Report the tie;
    do not resolve it with a new distance, containment or popularity rule.
    Expected IDs are agreement checks against saved identity, not gold labels.
    """
    top = rows[0] if rows else None
    tied = [r for r in rows if top and r.get("score") == top.get("score")]
    return dict(
        returned=len(rows),
        top=top,
        top_reference_agreement=bool(top and top["id"] in expected),
        reference_ranks=[i + 1 for i, r in enumerate(rows) if r["id"] in expected],
        top_score_distinct_ids=sorted({r["id"] for r in tied}),
        tied_reference_and_other_ids=bool(
            {r["id"] for r in tied} & expected and {r["id"] for r in tied} - expected
        ),
        exact_recorded_name_or_alias=bool(
            top and exact_alias(name, [top.get("name", ""), *top.get("alt_names", [])])
        ),
        accepted=False,
    )


def analyze(output: Path) -> dict:
    """Complete the cached 40-input candidate comparison without model writes.

    S2T section 9 requires original-source geometry validation after identity
    evidence. This experiment stops before that step; tag/WHG candidates must
    never be reported as 40 completed geocoding decisions.
    """
    from .geography_sample import tools

    started = time.perf_counter()
    plan = read_json(output / "plan.json")
    if read_json(output / "progress.json")["status"] != "RETRIEVED":
        raise ValueError("Source retrieval is incomplete")
    for path, sha in plan["inputs"].items():
        if digest(Path(path)) != sha:
            raise ValueError(f"Protected source/model changed: {path}")
    for path, sha in plan["outputs"].items():
        if digest(output / path) != sha:
            raise ValueError(f"Frozen comparison input changed: {path}")
    base = next(
        Path(p).parent
        for p in plan["inputs"]
        if Path(p).parts[-2:] == ("geography_sample", "sample.json")
    ).parent
    original = {
        r["input"]["place_id"]: r
        for r in read_json(base / "geography_context_parent_checked/audit.json")[
            "results"
        ]
    }
    entities = {
        e["entity_id"]: e
        for e in read_json(base / "model_qid_name/entities.json.gz")
        if e["type"] == "LOC"
    }
    sample = read_json(output / "sample.json")
    evidence = read_json(output / "evidence.json")
    queries = read_json(output / "queries.json")
    arms = {}
    for arm in queries:
        saved = read_json(output / "sources" / f"whg_{arm}.json")
        if saved["queries"] != queries[arm]:
            raise ValueError("Cached query differs from frozen query")
        validate_response(saved["response"], queries[arm])
        arms[arm] = saved["response"]
    client = tools()
    maps = {
        source: read_json(output / "sources" / f"first_50_{source.casefold()}.json")[
            "response"
        ]["elements"]
        for source in client.OVERPASS
    }
    results = []
    for place in sample:
        pid = place["place_id"]
        ev = evidence[pid]
        expected = {f"place:gn:{gid}" for gid in ev["expected_geonames_ids"]}
        tagged = {}
        kind = None
        if place["wikidata_id"]:
            expected.add(f"place:wd:{pid}")
            entity = entities[pid]
            kind = client.infer_place_type(
                dict(
                    name=entity["name"],
                    text=entity.get("descriptions", {}).get("en", {}).get("value", ""),
                    attributes=dict(p31=entity.get("direct_types", [])),
                )
            )
            for source, elements in maps.items():
                native = [c for c in elements if c["tags"]["wikidata"] == pid]
                prefix = place["selection_date"]
                eligible = []
                for candidate in native:
                    tags = candidate["tags"]
                    # Same supplied-precision comparison as the approved ten-
                    # input runner. No day or new historical interval is added.
                    for key in ("start_date", "end_date"):
                        if tags.get(key) and not re.fullmatch(
                            r"\d{4}(?:-\d{2}){0,2}", tags[key]
                        ):
                            raise ValueError(f"Unsupported date: {pid}, {key}")
                    date_ok = (
                        not tags.get("start_date")
                        or tags["start_date"][: len(prefix)] <= prefix
                    ) and (
                        not tags.get("end_date")
                        or prefix <= tags["end_date"][: len(prefix)]
                    )
                    type_ok = (
                        kind != "not_place" and client.type_score(kind, candidate) == 2
                    )
                    namespace = "ohm" if source == "OpenHistoricalMap" else "osm"
                    source_id = (
                        f"place:{namespace}:{candidate['type'][0]}{candidate['id']}"
                    )
                    expected.add(source_id)
                    eligible.append(
                        dict(
                            id=source_id,
                            date_agreement=date_ok,
                            existing_type_agreement=type_ok,
                        )
                    )
                tagged[source] = eligible
        profiles = {
            arm: candidate_profile(
                payload.get(pid, {}).get("result", []), expected, place["name"]
            )
            for arm, payload in arms.items()
        }
        if pid in original:
            baseline = dict(
                status=original[pid]["review_status"],
                reason=original[pid]["decision_reason"],
                reused_verified_ten=True,
            )
        elif place["wikidata_id"]:
            eligible_count = sum(
                c["date_agreement"] and c["existing_type_agreement"]
                for rows in tagged.values()
                for c in rows
            )
            baseline = dict(
                status=(
                    "EXACT_QID_TAG_CANDIDATES_GEOMETRY_UNTESTED"
                    if eligible_count
                    else "NO_ELIGIBLE_EXACT_QID_TAG_CANDIDATE"
                ),
                eligible_count=eligible_count,
                complete_geocoding=False,
            )
        elif not any(c.isalnum() for c in place["name"]):
            baseline = dict(status="INPUT_NOT_SEARCHABLE", complete_geocoding=False)
        elif not ev["context"]["features"]:
            baseline = dict(
                status="BLOCKED_EXISTING_FEATURE_PARSER", complete_geocoding=False
            )
        else:
            baseline = dict(status="FALLBACK_NOT_REPLAYED", complete_geocoding=False)
        results.append(
            dict(
                input=place,
                evidence=ev,
                expected_reference_ids=sorted(expected),
                existing_place_type=kind,
                exact_qid_tag_checks=tagged,
                baseline=baseline,
                arms=profiles,
                identity_changed=False,
                geometry_assigned=False,
            )
        )
    if len(results) != 40 or len({r["input"]["place_id"] for r in results}) != 40:
        raise ValueError("Comparison lost or duplicated inputs")
    summary = dict(
        status="VERIFIED_CANDIDATE_COMPARISON_ONLY",
        inputs=40,
        qid_inputs=17,
        synthetic_inputs=23,
        searchable=sum(r["input"]["place_id"] in queries["native"] for r in results),
        original_ten_accepted=sum(
            r["baseline"]["status"] == "ACCEPTED_AUTO" for r in results
        ),
        baseline_statuses=dict(Counter(r["baseline"]["status"] for r in results)),
        arms={
            arm: dict(
                with_candidates=sum(bool(r["arms"][arm]["returned"]) for r in results),
                reference_covered_qids=sum(
                    bool(r["arms"][arm]["reference_ranks"])
                    for r in results
                    if r["input"]["wikidata_id"]
                ),
                top_reference_agreement_qids=sum(
                    r["arms"][arm]["top_reference_agreement"]
                    for r in results
                    if r["input"]["wikidata_id"]
                ),
                distinct_id_top_score_ties=sum(
                    len(r["arms"][arm]["top_score_distinct_ids"]) > 1 for r in results
                ),
            )
            for arm in arms
        },
        retrieval=read_json(output / "progress.json"),
        analysis_seconds=time.perf_counter() - started,
        new_geometry_assignments=0,
        new_identity_assignments=0,
        accuracy_estimated=False,
        production_rules_changed=False,
        protected_input_hashes_verified=True,
    )
    write(output / "audit.json", dict(summary=summary, results=results))
    # A flat human-readable index complements, rather than replaces, full raw
    # source responses and all ten candidates preserved in sources/.
    with (output / "comparison.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "place_id",
                "name",
                "cohort",
                "baseline",
                "arm",
                "top_id",
                "top_name",
                "top_score",
                "top_confidence",
                "top_reference_agreement",
                "reference_ranks",
                "top_score_distinct_ids",
            ],
        )
        writer.writeheader()
        for r in results:
            for arm, profile in r["arms"].items():
                top = profile["top"] or {}
                writer.writerow(
                    dict(
                        place_id=r["input"]["place_id"],
                        name=r["input"]["name"],
                        cohort=r["input"]["cohort"],
                        baseline=r["baseline"]["status"],
                        arm=arm,
                        top_id=top.get("id"),
                        top_name=top.get("name"),
                        top_score=top.get("score"),
                        top_confidence=top.get("confidence"),
                        top_reference_agreement=profile["top_reference_agreement"],
                        reference_ranks=json.dumps(profile["reference_ranks"]),
                        top_score_distinct_ids=json.dumps(
                            profile["top_score_distinct_ids"]
                        ),
                    )
                )
    summary["outputs"] = {
        str(p.relative_to(output)): digest(p)
        for p in output.rglob("*")
        if p.is_file() and p.name != "verification.json"
    }
    write(output / "verification.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "retrieve", "analyze"])
    parser.add_argument("--base", type=Path)
    parser.add_argument("--frozen-sample", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.phase == "prepare":
        result = prepare(args.base, args.output, args.frozen_sample)
    else:
        result = {"retrieve": retrieve, "analyze": analyze}[args.phase](args.output)
    print(json.dumps(result, ensure_ascii=True))
    if result["status"] == "STOPPED_FOR_CONSULTATION":
        raise SystemExit(1)
