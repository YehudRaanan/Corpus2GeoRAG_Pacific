"""Entity relevance columns and their immutable page evidence (S2T 6.1).

One QID-level measurement is shared by separate typed rows. Synthetic IDs
keep null relevance: Daniel mention frequency is the separate importance.
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
from pathlib import Path

from .poc import digest, read_json
from .scope_concentration_filter import combine_language_rows


def records(english: dict, japanese: dict, references: dict) -> dict[str, dict]:
    """Reuse the approved redirect-aware counts; never pool languages."""
    if english["dump_date"] != japanese["dump_date"]:
        raise ValueError("Relevance languages use different snapshots")
    by_language = {
        report["wiki"]: {row["qid"]: row for row in report["rows"]}
        for report in (english, japanese)
    }
    return {
        row["qid"]: dict(
            relevance_en=row["enwiki_relevance"],
            relevance_ja=row["jawiki_relevance"],
            relevance=row["maximum_relevance"],
            relevance_status=(
                "SCORED"
                if row["maximum_relevance"] is not None
                else "UNAVAILABLE_BOTH_LANGUAGES"
            ),
            evidence={
                "dump_date": english["dump_date"],
                "maximum_score_wiki": row["maximum_score_wiki"],
                "languages": {
                    w: values[row["qid"]] for w, values in by_language.items()
                },
                "reports": references,
            },
        )
        for row in combine_language_rows(english["rows"], japanese["rows"])
    }


def load(english: Path, japanese: Path) -> dict[str, dict]:
    reports = []
    for path in (english, japanese):
        report = read_json(path)
        for name, expected in report.get("outputs", {}).items():
            if digest(path.parent / name) != expected:
                raise ValueError(f"Relevance evidence changed: {path.parent / name}")
        reports.append(report)
    # The page scope is independent of matching decisions and must remain the
    # same in both reports. Different selection files are not scope evidence.
    shared = reports[0].get("inputs", {}).keys() & reports[1].get("inputs", {}).keys()
    for name in shared:
        if reports[0]["inputs"][name] != reports[1]["inputs"][name]:
            raise ValueError(f"Different relevance input lineage: {name}")
    return records(*reports, {str(p): digest(p) for p in (english, japanese)})


def attach(entities: list[dict], measured: dict[str, dict]) -> list[dict]:
    result = []
    for entity in entities:
        qid = entity["entity_id"]
        values = measured.get(qid)
        if values is None:
            values = dict(
                relevance_en=None,
                relevance_ja=None,
                relevance=None,
                relevance_status=(
                    "NOT_APPLICABLE_SYNTHETIC"
                    if qid.startswith("SYN_")
                    else "UNMEASURED"
                ),
                evidence={},
            )
        result.append(
            {
                **entity,
                **{k: v for k, v in values.items() if k != "evidence"},
                "attributes": {
                    **entity.get("attributes", {}),
                    "relevance_basis": values["evidence"],
                },
            }
        )
    return result


def reuse_languages(measured_path: Path, qids: set[str], output: Path) -> list[dict]:
    """S2T 3.1/6.1: project verified candidate counts onto the new POC IDs.

    Scope and snapshot do not depend on which candidates matching accepted.
    Reuse original per-language rows verbatim, including unavailable results;
    never substitute mention counts or rerun the same multi-GB dump scan.
    """
    receipt = read_json(measured_path.parent / "report.json")
    if digest(measured_path) != receipt["outputs"][measured_path.name]:
        raise ValueError("Candidate relevance artifact changed")
    measured = read_json(measured_path)
    if missing := qids - measured.keys():
        raise ValueError(f"Matched QIDs lack candidate relevance: {sorted(missing)}")
    sources = {
        path: sha
        for q in qids
        for path, sha in measured[q]["evidence"]["reports"].items()
    }
    for path, sha in sources.items():
        if digest(Path(path)) != sha:
            raise ValueError(f"Candidate language report changed: {path}")
    reports = []
    for wiki in ("enwiki", "jawiki"):
        rows = [measured[q]["evidence"]["languages"][wiki] for q in sorted(qids)]
        dates = {measured[q]["evidence"]["dump_date"] for q in qids}
        if len(dates) != 1 or any(r["wiki"] != wiki for r in rows):
            raise ValueError("Candidate language/snapshot evidence differs")
        report = dict(
            status="VERIFIED_CANDIDATE_COUNTS_REUSED",
            wiki=wiki,
            dump_date=dates.pop(),
            selected_qids=len(rows),
            rows=rows,
            network_requests=0,
            inputs={str(measured_path): digest(measured_path), **sources},
            outputs={},
        )
        folder = output / wiki
        folder.mkdir()
        (folder / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        reports.append(report)
    return reports


def measure_missing(
    selection: Path, output: Path, english: Path, japanese: Path
) -> dict:
    """Measure before matching; reuse verified same-scope counts (S2T 3.1/6.1)."""
    from .snapshot_link_relevance_probe import run as measure

    if output.exists():
        raise ValueError("Preserve previous candidate measurements")
    measured = load(english, japanese)
    selected = read_json(selection)
    if len({r["qid"] for r in selected}) != len(selected):
        raise ValueError("Duplicate candidate QID")
    missing = [r for r in selected if r["qid"] not in measured]
    output.mkdir(parents=True)
    if missing:
        pending = output / "selection.json"
        pending.write_text(json.dumps(missing, ensure_ascii=False), encoding="utf-8")
        (output / "manifest.json").write_text(
            json.dumps(
                dict(
                    population="MATCHING_CANDIDATE_RELEVANCE",
                    inputs={str(selection): digest(selection)},
                    outputs={pending.name: digest(pending)},
                )
            ),
            encoding="utf-8",
        )
        for wiki in ("enwiki", "jawiki"):
            fresh = measure(wiki, True, output / wiki, pending)
            if fresh["dump_date"] != read_json(english)["dump_date"]:
                raise ValueError(
                    "Candidate measurement snapshot differs from reused scores"
                )
        measured.update(
            load(output / "enwiki/report.json", output / "jawiki/report.json")
        )
    selected_records = {r["qid"]: measured[r["qid"]] for r in selected}
    with gzip.open(
        output / "matching_relevance.json.gz", "wt", encoding="utf-8"
    ) as stream:
        json.dump(selected_records, stream, ensure_ascii=False, allow_nan=False)
    report = dict(
        status="MATCHING_CANDIDATE_RELEVANCE_COMPLETE",
        candidate_qids=len(selected),
        reused_qids=len(selected) - len(missing),
        measured_qids=len(missing),
        network_requests=0,
        inputs={str(p): digest(p) for p in (selection, english, japanese)},
        outputs={
            "matching_relevance.json.gz": digest(output / "matching_relevance.json.gz")
        },
    )
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def populate(model: Path, output: Path, english: Path, japanese: Path) -> dict:
    """Write a new model version, keeping old tables and decisions unchanged."""
    if output.exists():
        raise ValueError("Use a new model output directory")
    manifest = read_json(model / "manifest.json")
    for name, expected in manifest["outputs"].items():
        if digest(model / name) != expected:
            raise ValueError(f"Model table changed: {name}")
    measured = load(english, japanese)
    entities = attach(read_json(model / "entities.json.gz"), measured)
    output.mkdir(parents=True)
    with gzip.open(output / "entities.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(entities, stream, ensure_ascii=False, allow_nan=False)
    # Preserve the existing physical table interface; no new storage layer.
    for name in manifest["outputs"]:
        if name != "entities.json.gz":
            shutil.copyfile(model / name, output / name)
    report = dict(
        **{
            k: v
            for k, v in manifest.items()
            if k not in {"status", "inputs", "outputs", "entity_rows"}
        },
        status="RELEVANCE_COLUMNS_POPULATED_BASELINE_IDENTITIES_UNCHANGED",
        entity_rows=len(entities),
        score_statuses={
            status: sum(r["relevance_status"] == status for r in entities)
            for status in sorted({r["relevance_status"] for r in entities})
        },
        identities_changed=False,
        inputs={
            **manifest.get("inputs", {}),
            **{str(p): digest(p) for p in (model / "manifest.json", english, japanese)},
        },
        outputs={name: digest(output / name) for name in manifest["outputs"]},
    )
    (output / "manifest.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("populate", "measure"))
    parser.add_argument("--model", type=Path)
    parser.add_argument("--selection", type=Path)
    for argument in ("output", "english", "japanese"):
        parser.add_argument("--" + argument, type=Path, required=True)
    args = parser.parse_args()
    if args.phase == "measure":
        print(
            json.dumps(
                measure_missing(
                    args.selection, args.output, args.english, args.japanese
                )
            )
        )
    else:
        print(
            json.dumps(populate(args.model, args.output, args.english, args.japanese))
        )
