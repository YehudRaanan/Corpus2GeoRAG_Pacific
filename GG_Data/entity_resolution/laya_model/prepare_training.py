"""Normalize frozen public decisions and full-annotation reverse supervision.

No model, pipeline, network, or tokenizer is imported. Public labels are
incomplete; STOP means no annotated positive remains in this presented pool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
import zipfile
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from GG_Data.entity_resolution.decision_model.prepare_training import (
    make_groups,
    removal_states,
)
from GG_Data.entity_resolution.luke_pilot.data import read_jsonl, sha256

LOG = logging.getLogger(__name__)
SPLITS = ("train", "validation", "calibration", "public_test")
STOP_TEXT = {
    "forward": "None of the remaining mention groups refers to this entity.",
    "reverse": "This mention does not refer to any of the remaining entities.",
}
SEED = 20261030


def normalize_record(row: dict, direction: str) -> dict:
    """Preserve identities and labels; attach an explicit joint target vector."""
    if direction not in STOP_TEXT:
        raise ValueError("direction must be forward or reverse")
    for key in (
        "id",
        "base_id",
        "entity",
        "candidates",
        "positive_ids",
        "full_positive_ids",
        "removed_ids",
        "synthetic_stop",
        "source_page_id",
        "source_document_index",
        "source_text_sha256",
    ):
        if key not in row:
            raise ValueError(f"Missing required field {key}")
    ids = [c["id"] for c in row["candidates"]]
    positives = set(row["positive_ids"])
    removed = set(row["removed_ids"])
    if len(ids) != len(set(ids)) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("Candidate identities must be unique nonempty strings")
    if len(positives) != len(row["positive_ids"]) or not positives.issubset(ids):
        raise ValueError("Invalid positive identities in presented pool")
    full = set(row["full_positive_ids"])
    if not full or not removed.issubset(full) or removed.intersection(ids):
        raise ValueError("Invalid full positive/removal identities")
    if positives != (full - removed).intersection(ids):
        raise ValueError("Remaining positive identities differ from preserved gold")
    if bool(row["synthetic_stop"]) != (not positives):
        raise ValueError("Synthetic stop contradicts remaining positive labels")
    if not row["entity"].get("name") or any(
        not c.get("name") for c in row["candidates"]
    ):
        raise ValueError("Query and candidate names are required")
    result = dict(row)
    result["remaining_full_positive_ids"] = sorted(full - removed)
    result["entity"] = {"context": "", **row["entity"]}
    result["candidates"] = [{"context": "", **c} for c in row["candidates"]]
    result.update(
        direction=direction,
        stop_text=STOP_TEXT[direction],
        public_annotations_incomplete=True,
        label_scope="remaining_public_annotated_positives_in_presented_pool_only",
    )
    result["target_probabilities"] = [
        1 / len(positives) if i in positives else 0.0 for i in ids
    ] + [0.0 if positives else 1.0]
    return result


def _validation_membership(pages: set[int]) -> dict[int, str]:
    if len(pages) < 2:
        raise ValueError(
            "At least two original validation pages are required for disjoint calibration"
        )
    ordered = sorted(
        pages,
        key=lambda page: hashlib.sha256(
            f"{SEED}:calibration:{page}".encode()
        ).hexdigest(),
    )
    calibration = set(ordered[: len(ordered) // 2])
    return {
        page: "calibration" if page in calibration else "validation" for page in pages
    }


def _cached_sections(
    archive: Path, sections: dict[int, dict]
) -> tuple[dict, dict, dict]:
    groups_by_section, labels_by_section, descriptions = {}, {}, {}
    needed_titles = set()
    with zipfile.ZipFile(archive) as cache:
        with cache.open("zelda/train_data/zelda_train.jsonl") as stream:
            for index, line in enumerate(stream):
                if index not in sections:
                    continue
                document = json.loads(line)
                reference = sections[index]["reference"]
                if (
                    int(document["page_id"]) != reference["source_page_id"]
                    or hashlib.sha256(document["text"].encode()).hexdigest()
                    != reference["source_text_sha256"]
                ):
                    raise ValueError(
                        f"Cached section identity/hash mismatch at index {index}"
                    )
                groups, positives = make_groups(document)
                group_map = {group["id"]: group for group in groups}
                if not sections[index]["group_ids"].issubset(group_map):
                    raise ValueError(
                        f"Retained candidate missing from cached full annotation at {index}"
                    )
                for base in sections[index]["bases"].values():
                    if set(base["full_positive_ids"]) != positives.get(
                        base["entity"]["name"], set()
                    ):
                        raise ValueError(
                            f"Cached full positive mapping differs for {base['base_id']}"
                        )
                groups_by_section[index], labels_by_section[index] = (
                    group_map,
                    positives,
                )
                needed_titles.update(positives)
                if len(groups_by_section) == len(sections):
                    break
        if groups_by_section.keys() != sections.keys():
            raise ValueError("Required source section missing from cached archive")
        with cache.open("zelda/other/entity_descriptions.jsonl") as stream:
            for line in stream:
                row = json.loads(line)
                title = row["wikipedia_title"].replace("_", " ")
                if title in needed_titles:
                    descriptions[title] = (row.get("description") or "")[:600]
    return groups_by_section, labels_by_section, descriptions


def prepare_records(
    source: Path, output: Path, direction: str, *, archive: Path | None = None
) -> dict:
    """Convert a frozen training_k80_v2 directory; direction may also be 'both'.

    An explicit archive is required for reverse/both. It must match the frozen
    source manifest. Outputs are exclusive-create and never replace prior data.
    """
    started = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    if direction not in (*STOP_TEXT, "both"):
        raise ValueError("direction must be forward, reverse, or both")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            "Prepared output must be empty; preserve prior frozen artifacts"
        )
    manifest_path = source / "public_manifest.json"
    original = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_files, records, page_sets, seen_ids = {}, {}, {}, set()
    sections = {}
    for split in ("train", "validation", "public_test"):
        path = source / f"{split}.jsonl"
        digest = sha256(path)
        if digest != original["files"][path.name]:
            raise ValueError(f"Frozen source hash mismatch: {path.name}")
        source_files[path.name] = digest
        rows = read_jsonl(path)
        if len(rows) != original["splits"][split]["states"]:
            raise ValueError(f"Frozen source row count mismatch: {split}")
        records[split] = rows
        page_sets[split] = {row["source_page_id"] for row in rows}
        for row in rows:
            normalize_record(row, "forward")
            if row["id"] in seen_ids:
                raise ValueError("Duplicate source state identity")
            seen_ids.add(row["id"])
            index = row["source_document_index"]
            section = sections.setdefault(
                index,
                {"reference": row, "bases": {}, "group_ids": set(), "split": split},
            )
            if section["split"] != split or any(
                section["reference"][k] != row[k]
                for k in ("source_page_id", "source_text_sha256")
            ):
                raise ValueError("Inconsistent section provenance")
            if row["removal_index"] == 0:
                section["bases"][row["base_id"]] = row
                section["group_ids"].update(c["id"] for c in row["candidates"])
    if any(page_sets[a] & page_sets[b] for a in page_sets for b in page_sets if a != b):
        raise ValueError("Source page leakage across original splits")
    if any(not section["bases"] for section in sections.values()):
        raise ValueError("Source section lacks initial states")
    validation = _validation_membership(page_sets["validation"])
    archive_hash, cached_groups, cached_labels, descriptions = None, {}, {}, {}
    if direction in ("reverse", "both"):
        if archive is None:
            raise ValueError(
                "Explicit cached archive is required for full reverse supervision"
            )
        archive_hash = sha256(archive)
        if archive_hash != original["archive_sha256"]:
            raise ValueError("Cached archive hash differs from frozen source manifest")
        cached_groups, cached_labels, descriptions = _cached_sections(archive, sections)
    output.mkdir(parents=True, exist_ok=True)
    counts = {split: Counter() for split in SPLITS}
    pages = {split: set() for split in SPLITS}
    candidate_counts = {split: [] for split in SPLITS}
    forward_ids = {split: [] for split in SPLITS}
    reverse_queries = {split: [] for split in SPLITS}
    with ExitStack() as stack:
        streams = {
            split: stack.enter_context(
                (output / f"{split}.jsonl").open("x", encoding="utf-8")
            )
            for split in SPLITS
        }

        def emit(row: dict, source_split: str, kind: str) -> None:
            row = normalize_record(row, kind)
            split = (
                validation[row["source_page_id"]]
                if source_split == "validation"
                else source_split
            )
            row["split"], row["original_split"] = split, source_split
            streams[split].write(json.dumps(row, ensure_ascii=False) + "\n")
            counts[split][kind] += 1
            counts[split]["synthetic_stop"] += row["synthetic_stop"]
            counts[split]["multi_positive"] += len(row["positive_ids"]) > 1
            counts[split]["singleton_positive_coverage"] += (
                row["state_kind"] == "singleton_positive_coverage"
            )
            counts[split]["unpresented_annotated_positive_states"] += bool(
                set(row["full_positive_ids"])
                - set(row["removed_ids"])
                - {c["id"] for c in row["candidates"]}
            )
            pages[split].add(row["source_page_id"])
            candidate_counts[split].append(len(row["candidates"]))
            if kind == "forward":
                forward_ids[split].append(row["id"])

        if direction in ("forward", "both"):
            for split, rows in records.items():
                for row in rows:
                    emit(row, split, "forward")
        if direction in ("reverse", "both"):
            for index, section in sorted(sections.items()):
                reference = section["reference"]
                labels = cached_labels[index]
                candidates = [
                    {
                        "id": "wikipedia_title:" + title,
                        "name": title,
                        "description": descriptions.get(title, ""),
                        "context": "",
                        "type": None,
                    }
                    for title in sorted(labels)
                ]
                by_group = defaultdict(set)
                for title, group_ids in labels.items():
                    for group_id in group_ids:
                        by_group[group_id].add("wikipedia_title:" + title)
                for group_id in sorted(section["group_ids"]):
                    positive_ids = sorted(by_group[group_id])
                    if not positive_ids:
                        raise ValueError("Missing reverse full positive labels")
                    identity = f"{reference['pool_id']}:reverse:{group_id}"
                    base = {
                        k: reference[k]
                        for k in (
                            "document_id",
                            "source_page_id",
                            "source_document_index",
                            "source_text_sha256",
                            "pool_id",
                        )
                    }
                    base.update(
                        id=identity,
                        entity=cached_groups[index][group_id],
                        candidates=candidates,
                        positive_ids=positive_ids,
                        full_positive_ids=positive_ids,
                        full_candidate_count=len(candidates),
                        source_base_ids=sorted(section["bases"]),
                        candidate_source="all_annotated_entity_titles_in_cached_public_source_section",
                        type_status="native_Daniel_type_not_available_in_public_annotations",
                        reverse_supervision="full_cached_section_annotations",
                    )
                    if "section_name" in reference:
                        base["section_name"] = reference["section_name"]
                    split = (
                        validation[reference["source_page_id"]]
                        if section["split"] == "validation"
                        else section["split"]
                    )
                    reverse_queries[split].append(identity)
                    for state in removal_states(base):
                        emit(state, section["split"], "reverse")
    result = {
        "stage": "prepare_laya_joint_records",
        "schema_version": 1,
        "direction": direction,
        "seed": SEED,
        "started_utc": started_utc,
        "ended_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.monotonic() - started,
        "active_work": "unknown",
        "approval_wait": 0,
        "environment_wait": 0,
        "gpu_seconds": 0,
        "api_requests": 0,
        "source_directory": str(source.resolve()),
        "source_manifest_sha256": sha256(manifest_path),
        "source_files": source_files,
        "archive_sha256": archive_hash,
        "original_source_manifest": original,
        "original_rows": {split: len(rows) for split, rows in records.items()},
        "source_pages_disjoint": True,
        "validation_split_policy": f"sha256('{SEED}:calibration:<page>') sorted first floor(N/2) pages are calibration",
        "page_membership": {split: sorted(values) for split, values in pages.items()},
        "forward_source_state_ids": forward_ids,
        "reverse_base_ids": reverse_queries,
        "reverse_supervision": (
            "full_cached_section_annotations" if archive_hash else "not_requested"
        ),
        "reverse_query_scope": "union of retained candidates from original initial forward states; all annotated titles in each original section are options",
        "target_set_changes": 0,
        "annotations_incomplete": True,
        "synthetic_stop_caveat": "No annotated positive remains in presented pool; not verified exhaustive negative truth",
        "public_test": "held-out pages from cached ZELDA training archive, not official benchmark",
        "splits": {
            split: {
                "states": counts[split]["forward"] + counts[split]["reverse"],
                "directions": {kind: counts[split][kind] for kind in STOP_TEXT},
                "source_pages": len(pages[split]),
                "synthetic_stop_states": counts[split]["synthetic_stop"],
                "multiple_positive_states": counts[split]["multi_positive"],
                "singleton_positive_coverage_states": counts[split][
                    "singleton_positive_coverage"
                ],
                "unpresented_annotated_positive_states": counts[split][
                    "unpresented_annotated_positive_states"
                ],
                "candidate_min": min(candidate_counts[split], default=0),
                "candidate_max": max(candidate_counts[split], default=0),
                "candidate_total": sum(candidate_counts[split]),
            }
            for split in SPLITS
        },
        "files": {
            f"{split}.jsonl": sha256(output / f"{split}.jsonl") for split in SPLITS
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--direction", choices=(*STOP_TEXT, "both"), default="both")
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = prepare_records(
        args.source, args.output, args.direction, archive=args.archive
    )
    LOG.info("Prepared split workloads: %s", json.dumps(result["splits"]))


if __name__ == "__main__":
    main()
