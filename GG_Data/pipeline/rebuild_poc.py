"""Resume the approved page-scope correction using existing population stages.

Population S2T 3 invalidates old matching-dependent outputs. S2T 6.1/7/8
rules remain unchanged. Only saved source records and approved mapping/hierarchy
parameters are reusable; no old populations, scores or selections are imported.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from time import perf_counter

from GG_Data.pipeline import event_model, event_population, geography
from GG_Data.pipeline.event_selection import prepare
from GG_Data.pipeline.poc import PAGE_CANDIDATE_SCOPE, ROOT, digest, read_json
from GG_Data.pipeline.scope_concentration_filter import combine_language_rows
from GG_Data.pipeline.snapshot_link_relevance_probe import run as measure


def write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def geography_sample_inputs(base: Path, original_sample: Path) -> list[dict]:
    """S2T 3/9: preserve the ten mention IDs, never the superseded QIDs.

    A corrected QID can have more model contexts than the original example.
    Retain those supported contexts and the new model's selection date. This
    step prepares inputs only; it neither selects geometry nor repairs IDs.
    """
    old = read_json(original_sample)
    if len(old) != 10:
        raise ValueError("Expected the approved ten-input Geography sample")
    mentions = {
        r["mention_id"]: r for r in read_json(base / "mentions_pages/mentions.json.gz")
    }
    targets = {
        r["place_id"]: r for r in read_json(base / "geography_inputs/targets.json")
    }
    sample = []
    for rank, previous in enumerate(old, 1):
        mention_id = previous["source_context"][0]["mention_id"]
        mention = mentions[mention_id]
        target = targets[mention["entity_id"]]
        if not any(r["mention_id"] == mention_id for r in target["source_context"]):
            raise ValueError("Original sample mention is absent from corrected target")
        sample.append(
            dict(
                **target,
                input_rank=rank,
                original_mention_id=mention_id,
                previous_place_id=previous["place_id"],
            )
        )
    return sample


def relevance(base: Path) -> dict:
    """S2T 6.1: measure corrected QIDs against the unchanged full page scope.

    Measure every matched QID once per language, then use the same source
    counts for the MISC retrieval filter and retained-entity Event relevance.
    Synthetics never acquire Wikimedia scores; their Daniel importance is
    independently populated in Entities under S2T 6/8.
    """
    started = perf_counter()
    source = base / "entities"
    output = base / "relevance"
    if output.exists():
        raise ValueError("Preserve existing relevance output")
    manifest = read_json(source / "manifest.json")
    if (
        digest(source / "manifest.json")
        != read_json(source / "verification.json")["manifest_sha256"]
    ):
        raise ValueError("Corrected Entity manifest changed")
    for name, expected in manifest["outputs"].items():
        if digest(source / name) != expected:
            raise ValueError(f"Corrected Entity artifact changed: {name}")
    entities = read_json(source / "entities.json.gz")
    names = {
        r["entity_id"]: r["name"] for r in entities if r["entity_id"].startswith("Q")
    }
    misc = {r["entity_id"] for r in entities if r["type"] == "MISC"} & names.keys()
    output.mkdir()
    write(
        output / "selection.json", [dict(qid=q, title=names[q]) for q in sorted(names)]
    )
    write(
        output / "manifest.json",
        dict(
            population="CORRECTED_DANIEL_QIDS_FOR_FIXED_10K",
            inputs={str(source / "manifest.json"): digest(source / "manifest.json")},
            outputs={"selection.json": digest(output / "selection.json")},
        ),
    )
    languages = [
        measure(wiki, True, output / wiki, output / "selection.json")
        for wiki in ("enwiki", "jawiki")
    ]
    combined = combine_language_rows(languages[0]["rows"], languages[1]["rows"])
    if {r["qid"] for r in combined} != names.keys():
        raise ValueError("Language measurements do not cover corrected Daniel QIDs")
    scope_rows = [r for r in combined if r["qid"] in misc]
    filtered = output / "misc_filter"
    filtered.mkdir()
    write(filtered / "decisions.json", scope_rows)
    write(
        filtered / "report.json",
        dict(
            status="COMPLETE_MAXIMUM_LANGUAGE_THRESHOLD",
            threshold_percent=5,
            rows=scope_rows,
            inputs={
                str(output / w / "report.json"): digest(output / w / "report.json")
                for w in ("enwiki", "jawiki")
            },
            outputs={"decisions.json": digest(filtered / "decisions.json")},
        ),
    )
    # Reuse the approved unknown-MISC hold and 5% rule, never a new decision.
    # prepare() writes a separate scope receipt without changing model rows.
    scope = prepare(output / "scope", source, filtered / "report.json")
    retained = set(scope["retained_qids"])
    scores = [r for r in combined if r["qid"] in retained]
    write(output / "entity_scores.json", scores)
    report = dict(
        status="CORRECTED_ENTITY_RELEVANCE_COMPLETE",
        matched_qids=len(names),
        retained_qids=len(retained),
        misc_qids=len(misc),
        below_misc_5pct=len(scope["below_misc_5pct_qids"]),
        held_unknown_misc=len(scope["held_unknown_misc_qids"]),
        elapsed_seconds=perf_counter() - started,
        inputs={str(source / "manifest.json"): digest(source / "manifest.json")},
        outputs={
            "manifest.json": digest(output / "manifest.json"),
            "entity_scores.json": digest(output / "entity_scores.json"),
        },
    )
    write(output / "report.json", report)
    return report


def run(stage: str, base: Path, *, model_dir: Path | None = None) -> dict:
    """Explicit stage paths prevent fallback to the historical POC outputs."""
    if not base.resolve().is_relative_to(ROOT / "GG_Data/pipeline/outputs"):
        raise ValueError("Use the approved local pipeline output directory")
    # Preserve stopped attempts; all dependent stages use the explicit new model.
    model = model_dir or base / "model"
    if not model.resolve().is_relative_to(base.resolve()):
        raise ValueError("The model output must stay inside this rebuild bundle")
    matching = base / "matching"
    if (
        read_json(matching / "manifest.json").get("page_candidate_scope")
        != PAGE_CANDIDATE_SCOPE
    ):
        raise ValueError("Corrected page-scope matching is required")
    if read_json(matching / "london_validation.json")["status"] not in {
        "CORRECT_QID",
        "UNRESOLVED",
    }:
        raise ValueError("London validation failed; stop downstream population")
    try:
        if stage == "relevance":
            return relevance(base)
        if stage == "events":
            return event_population.run(
                base / "events",
                entities_dir=base / "entities",
                scores_dir=base / "relevance",
                scope_report=base / "relevance/misc_filter/report.json",
                fresh_scope=True,
            )
        if stage == "model":
            return event_model.run(
                model,
                selection=base / "events",
                entities=base / "entities",
                mentions=base / "mentions_pages/mentions.json.gz",
                scores_dir=base / "relevance",
            )
        if stage == "geography-inputs":
            return geography.prepare(model, base / "geography_inputs")
        if stage == "geography-sample-inputs":
            original = (
                ROOT
                / "GG_Data/pipeline/outputs/poc_geography_10_input_consultation_20261022/sample.json"
            )
            if (
                digest(original)
                != "e5ac13b4e2fcbf9460693d05b28ac4efbcbaded05a569023c58400c5dde3c06a"
            ):
                raise ValueError("Approved ten-input sample changed")
            output = base / "geography_sample"
            if output.exists():
                raise ValueError("Preserve existing Geography sample outputs")
            sample = geography_sample_inputs(base, original)
            output.mkdir()
            write(output / "sample.json", sample)
            report = dict(
                status="CORRECTED_TEN_INPUT_SAMPLE_READY",
                sample_rows=len(sample),
                geometry_rows_written=0,
                inputs={
                    str(p): digest(p)
                    for p in (
                        original,
                        base / "geography_inputs/targets.json",
                        base / "mentions_pages/mentions.json.gz",
                    )
                },
                outputs={"sample.json": digest(output / "sample.json")},
            )
            write(output / "inputs_report.json", report)
            return report
        raise ValueError(f"Unknown rebuild stage: {stage}")
    except Exception as exc:
        write(
            base / f"{stage}_failure.json",
            dict(
                status="STOPPED_FOR_CONSULTATION",
                stage=stage,
                error=f"{type(exc).__name__}: {exc}",
                case=getattr(exc, "case", None),
            ),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage",
        choices=(
            "relevance",
            "events",
            "model",
            "geography-inputs",
            "geography-sample-inputs",
        ),
    )
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.info(
        "%s",
        json.dumps(
            run(args.stage, args.base, model_dir=args.model_dir), ensure_ascii=True
        ),
    )
