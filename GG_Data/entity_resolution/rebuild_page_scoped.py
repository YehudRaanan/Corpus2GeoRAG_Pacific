"""Rebuild matching from verified source caches, never from saved decisions.

Population S2T section 3, page-scope correction of 22 October 2026.
Only source article records, compact Wikidata metadata and the approved WWII
reference are reused. No previous candidates, matches or frozen IDs are copied.
This entry point makes no network calls; unavailable evidence stops the run.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path

from bilingual_page_pilot import LiveData, digest, read
from full_direct_wikidata import INPUT_SHA256, run, save


class SavedData(LiveData):
    def __init__(self) -> None:
        self.entities = {}
        self.requests = []

    def entities_for(self, qids: set[str]) -> None:
        missing = sorted(qids - self.entities.keys())
        if missing:
            raise ValueError(f"Saved matching metadata missing: {missing}")

    def get(self, url: str, params: dict, post: bool = False) -> dict:
        raise ValueError(
            f"Saved hierarchy evidence unavailable; network disabled: {url}"
        )


def prepare(source: Path, output: Path) -> None:
    """Verify all reusable inputs before creating a fresh, isolated output."""
    if output.exists():
        raise ValueError("Rebuild requires a new output directory")
    manifest = read(source / "manifest.json")
    if manifest["input_sha256"] != INPUT_SHA256:
        raise ValueError("Source cache belongs to a different Daniel version")
    names = ["entity_metadata.json.gz", "world.json.gz", "reference_manifest.json"]
    files = {Path(n): manifest["outputs"][n] for n in names}
    files.update({Path("pages") / n: h for n, h in manifest["page_evidence"].items()})
    for path, expected in files.items():
        if digest(source / path) != expected:
            raise ValueError(f"Source cache checksum differs: {path}")
    output.mkdir(parents=True)
    (output / "pages").mkdir()
    for path in files:
        shutil.copyfile(source / path, output / path)
    save(
        output / "rebuild_source_manifest.json",
        {
            "source": str(source.resolve()),
            "source_manifest_sha256": digest(source / "manifest.json"),
            "reused_files": {str(p): h for p, h in files.items()},
            "previous_decisions_reused": False,
        },
    )


def validate_london(output: Path) -> dict:
    """User-required case check; report, never correct or force an assignment."""
    row = next(
        r for r in read(output / "matches.json.gz") if r["input_row_number"] == 75398
    )
    if (row["raw"]["word"], row["raw"]["Source"]) != (
        "London",
        "Battle of the Mediterranean",
    ):
        raise ValueError("London validation input differs")
    result = {
        "mention_id": row["mention_id"],
        "input_row_number": row["input_row_number"],
        "raw": row["raw"],
        "assigned_id": row["assigned_id"],
        "matched_stage": row["matched_stage"],
        "attempts": row["attempts"],
        "expected_wikidata_id": "Q84",
        "status": (
            "CORRECT_QID"
            if row["assigned_id"] == "Q84"
            else (
                "UNRESOLVED" if row["assigned_id"].startswith("SYN_") else "WRONG_QID"
            )
        ),
        "assignment_changed_by_validation": False,
    }
    save(output / "london_validation.json", result)
    if result["status"] == "WRONG_QID":
        raise ValueError(f"London still has an incorrect QID: {row['assigned_id']}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-workers", type=int, default=2)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    prepare(args.source, args.output)
    try:
        result = run(args.output, api=SavedData(), page_workers=args.page_workers)
        validate_london(args.output)
    except Exception as exc:
        save(args.output / "failure.json", {"error": str(exc)})
        raise
    print(json.dumps(result, indent=2))
