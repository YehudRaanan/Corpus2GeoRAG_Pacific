"""Data conversion checks using a tiny full-annotation cache."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from GG_Data.entity_resolution.decision_model.prepare_training import (
    make_groups,
    removal_states,
)
from GG_Data.entity_resolution.laya_model.prepare_training import prepare_records
from GG_Data.entity_resolution.luke_pilot.data import read_jsonl, sha256, write_jsonl


def corpus(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    documents, splits = [], {"train": [], "validation": [], "public_test": []}
    for index, (page, split) in enumerate(
        [(1, "train"), (2, "validation"), (3, "validation"), (4, "public_test")]
    ):
        document = {
            "page_id": page,
            "text": "Alpha Alpha Beta",
            "index": [[0, 5], [6, 11], [12, 16]],
            "wikipedia_titles": ["One", "Hidden", "Other"],
        }
        documents.append(document)
        groups, positives = make_groups(document)
        base = {
            "id": f"base:{page}",
            "document_id": f"wiki:{page}",
            "source_page_id": page,
            "source_document_index": index,
            "source_text_sha256": __import__("hashlib")
            .sha256(document["text"].encode())
            .hexdigest(),
            "entity": {"name": "One", "description": "First entity"},
            "candidates": groups,
            "positive_ids": sorted(positives["One"]),
            "full_positive_ids": sorted(positives["One"]),
            "pool_id": f"pool:{page}",
        }
        splits[split].extend(removal_states(base))
    archive = tmp_path / "cache.zip"
    with zipfile.ZipFile(archive, "w") as cache:
        cache.writestr(
            "zelda/train_data/zelda_train.jsonl",
            "\n".join(json.dumps(d) for d in documents),
        )
        cache.writestr(
            "zelda/other/entity_descriptions.jsonl",
            "\n".join(
                json.dumps({"wikipedia_title": t, "description": t + " description"})
                for t in ("One", "Hidden", "Other")
            ),
        )
    for split, rows in splits.items():
        write_jsonl(source / f"{split}.jsonl", rows)
    manifest = {
        "archive_sha256": sha256(archive),
        "files": {
            f"{split}.jsonl": sha256(source / f"{split}.jsonl") for split in splits
        },
        "splits": {split: {"states": len(rows)} for split, rows in splits.items()},
    }
    (source / "public_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return source, archive


def output_rows(path: Path) -> dict[str, list[dict]]:
    return {
        split: read_jsonl(path / f"{split}.jsonl")
        for split in ("train", "validation", "calibration", "public_test")
    }


def test_forward_preserves_rows_splits_stop_and_target_mass(tmp_path):
    source, _ = corpus(tmp_path)
    out = tmp_path / "prepared"
    manifest = prepare_records(source, out, "forward")
    outputs = output_rows(out)
    assert sum(map(len, outputs.values())) == 8
    assert len(outputs["validation"]) == len(outputs["calibration"]) == 2
    pages = {
        split: {r["source_page_id"] for r in rows} for split, rows in outputs.items()
    }
    assert all(not pages[a] & pages[b] for a in pages for b in pages if a != b)
    assert (
        manifest["source_files"]
        == json.loads((source / "public_manifest.json").read_text())["files"]
    )
    for rows in outputs.values():
        for row in rows:
            assert row["direction"] == "forward"
            assert (
                row["stop_text"]
                == "None of the remaining mention groups refers to this entity."
            )
            assert sum(row["target_probabilities"]) == pytest.approx(1)
            assert row["target_probabilities"][-1] == int(row["synthetic_stop"])
            assert row["public_annotations_incomplete"] is True


def test_reverse_uses_full_annotations_and_builds_multi_positive_removal(tmp_path):
    source, archive = corpus(tmp_path)
    out = tmp_path / "reverse"
    prepare_records(source, out, "reverse", archive=archive)
    rows = output_rows(out)["train"]
    alpha = [r for r in rows if r["entity"]["name"] == "Alpha"]
    initial = next(r for r in alpha if r["removal_index"] == 0)
    assert {c["name"] for c in initial["candidates"]} == {"One", "Hidden", "Other"}
    assert initial["positive_ids"] == ["wikipedia_title:Hidden", "wikipedia_title:One"]
    assert sorted(initial["target_probabilities"]) == [0, 0, 0.5, 0.5]
    assert initial["source_base_ids"] == ["base:1"]
    assert {tuple(r["positive_ids"]) for r in alpha} >= {
        (),
        ("wikipedia_title:One",),
        ("wikipedia_title:Hidden",),
    }
    assert all(
        r["stop_text"]
        == "This mention does not refer to any of the remaining entities."
        for r in rows
    )
    assert all(r["full_positive_ids"] for r in rows)


def test_combined_accounts_each_original_state_once(tmp_path):
    source, archive = corpus(tmp_path)
    out = tmp_path / "both"
    manifest = prepare_records(source, out, "both", archive=archive)
    assert sum(v["directions"]["forward"] for v in manifest["splits"].values()) == 8
    assert sum(v["directions"]["reverse"] for v in manifest["splits"].values()) == 24
    assert manifest["target_set_changes"] == 0
    assert manifest["reverse_supervision"] == "full_cached_section_annotations"


def test_rejects_changed_source_hash(tmp_path):
    source, _ = corpus(tmp_path)
    with (source / "train.jsonl").open("a") as stream:
        stream.write("{}\n")
    with pytest.raises(ValueError, match="hash"):
        prepare_records(source, tmp_path / "bad", "forward")


def test_rejects_missing_or_invalid_gold_without_silent_skip(tmp_path):
    source, _ = corpus(tmp_path)
    rows = read_jsonl(source / "train.jsonl")
    rows[0]["positive_ids"] = ["missing"]
    (source / "train.jsonl").unlink()
    write_jsonl(source / "train.jsonl", rows)
    manifest = json.loads((source / "public_manifest.json").read_text())
    manifest["files"]["train.jsonl"] = sha256(source / "train.jsonl")
    (source / "public_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="positive"):
        prepare_records(source, tmp_path / "bad", "forward")


def test_rejects_archive_mismatch_and_existing_outputs(tmp_path):
    source, archive = corpus(tmp_path)
    with zipfile.ZipFile(archive, "a") as cache:
        cache.writestr("changed", "different")
    with pytest.raises(ValueError, match="archive hash"):
        prepare_records(source, tmp_path / "bad", "reverse", archive=archive)
    out = tmp_path / "existing"
    out.mkdir()
    (out / "keep").write_text("keep")
    with pytest.raises(FileExistsError):
        prepare_records(source, out, "forward")


def test_reports_remaining_full_gold_separate_from_presented_gold(tmp_path):
    source, archive = corpus(tmp_path)
    out = tmp_path / "remaining"
    prepare_records(source, out, "both", archive=archive)
    for rows in output_rows(out).values():
        for row in rows:
            assert row["remaining_full_positive_ids"] == sorted(
                set(row["full_positive_ids"]) - set(row["removed_ids"])
            )
            assert set(row["positive_ids"]).issubset(row["remaining_full_positive_ids"])


def test_rejects_missing_cached_section_without_publishing_outputs(tmp_path):
    source, archive = corpus(tmp_path)
    replacement = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(archive) as old, zipfile.ZipFile(replacement, "w") as cache:
        cache.writestr(
            "zelda/train_data/zelda_train.jsonl",
            old.read("zelda/train_data/zelda_train.jsonl").decode().splitlines()[0],
        )
        cache.writestr(
            "zelda/other/entity_descriptions.jsonl",
            old.read("zelda/other/entity_descriptions.jsonl"),
        )
    manifest = json.loads((source / "public_manifest.json").read_text())
    manifest["archive_sha256"] = sha256(replacement)
    (source / "public_manifest.json").write_text(json.dumps(manifest))
    out = tmp_path / "bad"
    with pytest.raises(ValueError, match="missing"):
        prepare_records(source, out, "reverse", archive=replacement)
    assert not out.exists()


def test_forward_multi_positive_and_terminal_do_not_become_single_answer(tmp_path):
    from GG_Data.entity_resolution.laya_model.prepare_training import normalize_record

    source, _ = corpus(tmp_path)
    row = read_jsonl(source / "train.jsonl")[0]
    row["positive_ids"] = row["full_positive_ids"] = [
        c["id"] for c in row["candidates"]
    ]
    result = normalize_record(row, "forward")
    assert result["target_probabilities"] == [0.5, 0.5, 0]
    assert result["positive_ids"] == row["positive_ids"]
    terminal = removal_states({**row, "id": "base:new"})
    assert all(
        sum(normalize_record(s, "forward")["target_probabilities"]) == pytest.approx(1)
        for s in terminal
    )


def test_unpresented_positive_stays_a_retrieval_miss_not_verified_negative(tmp_path):
    from GG_Data.entity_resolution.laya_model.prepare_training import normalize_record

    source, _ = corpus(tmp_path)
    row = read_jsonl(source / "train.jsonl")[0]
    row["candidates"] = [
        c for c in row["candidates"] if c["id"] not in row["positive_ids"]
    ]
    row["positive_ids"] = []
    row["synthetic_stop"] = True
    result = normalize_record(row, "forward")
    assert result["positive_ids"] == []
    assert result["remaining_full_positive_ids"] == row["full_positive_ids"]
    assert result["target_probabilities"] == [0, 1]
    assert result["public_annotations_incomplete"] is True
