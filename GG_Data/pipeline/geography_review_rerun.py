"""Rerun a reviewed mention cohort against the current model (S2T 3.1/9.7).

Keep the original Daniel mentions, not their old QIDs. Reuse complete source
responses only for identical current targets/queries; do not change the model,
identity decisions, Geography weights, or the frozen review.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd

from . import geography_comparison, geography_population, geography_ranking_sample
from . import osm_bigquery
from .poc import digest, read_json
from .rebuild_poc import write


def cohort(review: list[dict], mentions: list[dict], targets: list[dict]) -> list[dict]:
    """Preserve every reviewed mention; a corrected non-LOC is not a new LOC."""
    by_mid = {m["mention_id"]: m for m in mentions}
    by_pid = {p["place_id"]: p for p in targets}
    rows = []
    for old in review:
        m = by_mid[old["mention_id"]]
        if (m["word"], m["Text"]) != (old["daniel_name"], old["daniel_text"]):
            raise ValueError("Reviewed Daniel input changed")
        rows.append(
            dict(
                index=old["index"],
                mention_id=m["mention_id"],
                daniel_name=m["word"],
                old_entity_id=old["place_id"],
                entity_id=m["entity_id"],
                entity_type=m["entity_type"],
                status=(
                    "LOC" if m["entity_id"] in by_pid else "NON_LOC_AFTER_MATCHING"
                ),
            )
        )
    if len({r["mention_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate reviewed mention")
    return rows


def prepare(base: Path, previous_review: Path, output: Path) -> dict:
    """Project cached population results; retain their full parent receipts."""
    if output.exists():
        raise ValueError("Preserve prior results; choose a new output directory")
    parent = base / "geography_retrieval"
    if read_json(parent / "progress.json")["status"] != "RETRIEVED":
        raise ValueError("Population source retrieval is incomplete")
    old = read_json(previous_review)["rows"]
    if len(old) != 100:
        raise ValueError("Expected the original 100 reviewed mentions")
    mentions = read_json(base / "mentions_pages/mentions.json.gz")
    targets = read_json(parent / "sample.json")
    rows = cohort(old, mentions, targets)
    ids = {r["entity_id"] for r in rows if r["status"] == "LOC"}
    if len(ids) != sum(r["status"] == "LOC" for r in rows):
        raise ValueError("Multiple sample mentions now share one LOC target")
    inputs = read_json(parent / "plan.json")["inputs"] | {
        str(previous_review): digest(previous_review),
        str(parent / "progress.json"): digest(parent / "progress.json"),
    }
    for path, sha in inputs.items():
        if digest(Path(path)) != sha:
            raise ValueError(f"Changed source input: {path}")
    sample = [p for p in targets if p["place_id"] in ids]
    by_mid = {m["mention_id"]: m for m in mentions}
    evidence = read_json(parent / "evidence.json")
    # Ranking must see the same reviewed occurrence, even when the current
    # aggregate target's first occurrence comes from a different source page.
    for row in rows:
        if row["status"] != "LOC":
            continue
        m = by_mid[row["mention_id"]]
        evidence[row["entity_id"]].update(
            mention_id=m["mention_id"],
            original_name=m["word"],
            text=m["Text"],
            source_page=m["Source"],
            wiki_site=m["wiki_site"],
            wiki_page_id=m["wiki_page_id"],
            context=geography_comparison.context(m),
        )
    comp = output / "comparison"
    (comp / "sources").mkdir(parents=True)
    write(output / "cohort.json", rows)
    write(comp / "sample.json", sample)
    write(comp / "evidence.json", {p: evidence[p] for p in ids})
    queries = read_json(parent / "queries.json")
    subset_queries = {}
    for arm in ("native", "existing_dated"):
        path = parent / f"sources/whg_{arm}.json"
        saved = read_json(path)
        selected = {k: q for k, q in queries[arm].items() if k in ids}
        if saved["queries"] != queries[arm]:
            raise ValueError("WHG cache queries changed")
        geography_comparison.validate_response(saved["response"], queries[arm])
        inputs[str(path)] = digest(path)
        write(
            comp / "sources" / path.name,
            saved
            | dict(
                queries=selected,
                response={k: saved["response"][k] for k in selected},
                subset_of=str(path),
            ),
        )
        subset_queries[arm] = selected
    write(comp / "queries.json", subset_queries)
    qids = sorted(p["wikidata_id"] for p in sample if p["wikidata_id"])
    path = parent / "sources/first_50_openhistoricalmap.json"
    saved = read_json(path)
    geography_comparison.validate_overpass(saved["response"], saved["qids"], "OHM")
    inputs[str(path)] = digest(path)
    write(
        comp / "sources" / path.name,
        saved
        | dict(
            qids=qids,
            subset_of=str(path),
            response=dict(
                elements=[
                    e
                    for e in saved["response"]["elements"]
                    if e.get("tags", {}).get("wikidata") in qids
                ]
            ),
        ),
    )
    path = parent / "sources" / osm_bigquery.NAME
    full_qids = [p["wikidata_id"] for p in targets if p["wikidata_id"]]
    # load() verifies the entire parent population and raw retrieval receipts
    # before any subset is taken. The subset does not claim a new cloud query.
    candidates = [c for c in osm_bigquery.load(path, full_qids) if c["qid"] in qids]
    inputs[str(path)] = digest(path)
    write(
        comp / "sources" / path.name,
        dict(
            qids=qids,
            candidates=candidates,
            inputs={str(path): inputs[str(path)]},
            subset_of=str(path),
            query_evidence=[
                dict(
                    parent_cache=str(path),
                    retrieved_at=(
                        candidates[0].get("retrieved_at") if candidates else None
                    ),
                )
            ],
        ),
    )
    write(
        comp / "plan.json",
        dict(
            status="PREPARED_FROM_VERIFIED_CACHE",
            input_count=len(sample),
            reviewed_mentions=len(rows),
            identities_changed=False,
            inputs=inputs,
            documents=["docs/SOURCES_TO_ENTITY_DATA_MODEL_S2T.md sections 3.1/9.7"],
            outputs={p.name: digest(p) for p in comp.iterdir() if p.is_file()},
        ),
    )
    result = dict(status="RETRIEVED", requests=0, reused=4, inputs=len(sample))
    write(comp / "progress.json", result)
    return result


def compare(previous_review: Path, output: Path) -> dict:
    """Carry a verdict forward only for identical identity, object and shape.

    S2T 9.7 review criterion: any supported real geographic connection counts.
    A score or QID agreement is not a correctness label. Changed cases require
    an explicit review; non-LOC corrections stay in the original denominator.
    """
    previous = read_json(previous_review)
    old_inputs = previous["verification"]["source_sha256"]
    for name, sha in old_inputs.items():
        if digest(Path(name)) != sha:
            raise ValueError(f"Frozen review source changed: {name}")
    old_geometry = next(
        Path(p) for p in old_inputs if p.endswith("proposed_geometries.parquet")
    )
    frame = gpd.read_parquet(old_geometry)
    old_shapes = dict(zip(frame.place_id, frame.geometry))
    ranked = output / "ranking"
    verification = read_json(ranked / "verification.json")
    for name, sha in verification["outputs"].items():
        if digest(ranked / name) != sha:
            raise ValueError(f"Rerun output changed: {name}")
    frame = gpd.read_parquet(ranked / "proposed_geometries.parquet")
    shapes = dict(zip(frame.place_id, frame.geometry))
    cohort_rows = read_json(output / "cohort.json")
    results = {
        r["input"]["place_id"]: r for r in read_json(ranked / "audit.json")["results"]
    }
    old_rows = {r["mention_id"]: r for r in previous["rows"]}
    rows = []
    for row in cohort_rows:
        old = old_rows[row["mention_id"]]
        selected = (
            results[row["entity_id"]]["proposed"] if row["status"] == "LOC" else None
        )
        before = old["selected_geometry"]
        same_identity = row["old_entity_id"] == row["entity_id"]
        same_object = bool(
            before
            and selected
            and (before["source"], before["source_id"])
            == (selected["source"], selected["source_id"])
        )
        same_geometry = bool(
            selected
            and row["old_entity_id"] in old_shapes
            and old_shapes[row["old_entity_id"]].equals_exact(
                shapes[row["entity_id"]], 0
            )
        )
        reuse = same_identity and same_object and same_geometry
        summary = (
            None
            if selected is None
            else {
                k: selected.get(k)
                for k in (
                    "source",
                    "source_id",
                    "name",
                    "qid",
                    "total",
                    "components",
                    "receipt",
                    "uncertainty_flags",
                    "context_matches",
                    "coordinate_checks",
                )
            }
        )
        if summary:
            summary["geometry_type"] = shapes[row["entity_id"]].geom_type
            summary["bounds"] = list(shapes[row["entity_id"]].bounds)
            summary["source_url"] = geography_population.source_url(selected)
        rows.append(
            row
            | dict(
                previous_verdict=old["verdict"],
                previous_reason=old["reason"],
                previous_selection=before,
                selected_geometry=summary,
                same_identity=same_identity,
                same_source_object=same_object,
                exact_same_geometry=same_geometry,
                previous_review_reused=reuse,
                verdict=(
                    "NON_LOC"
                    if row["status"] != "LOC"
                    else (
                        "MISSING"
                        if not selected
                        else old["verdict"] if reuse else "REVIEW_REQUIRED"
                    )
                ),
                reason=old["reason"] if reuse else None,
                source_page=old["source_page"],
                daniel_text=old["daniel_text"],
            )
        )
    if len(rows) != 100 or len({r["mention_id"] for r in rows}) != 100:
        raise ValueError("Lost an original reviewed mention")
    result = dict(
        status="CHANGED_RESULTS_REQUIRE_REVIEW",
        rows=rows,
        ranking_verification=verification,
        previous_review_sha256=digest(previous_review),
    )
    write(output / "evaluation_draft.json", result)
    return dict(
        rows=len(rows),
        review_required=sum(r["verdict"] == "REVIEW_REQUIRED" for r in rows),
        reused=sum(r["previous_review_reused"] for r in rows),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "records", "rank", "compare"])
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous-review", type=Path)
    parser.add_argument("--request-cache", type=Path)
    args = parser.parse_args()
    comp = args.output / "comparison"
    if args.phase == "prepare":
        result = prepare(args.base, args.previous_review, args.output)
    elif args.phase == "records":
        result = geography_population.candidate_records(args.base, comp)
        # Full source receipts stay in the cache; keep terminal output bounded.
        result = {
            k: result[k] for k in ("status", "candidate_qids", "identities_added")
        }
    elif args.phase == "rank":
        result = geography_ranking_sample.run(
            args.output / "ranking", args.request_cache, comp, base_dir=args.base
        )
    else:
        result = compare(args.previous_review, args.output)
    print(result)
