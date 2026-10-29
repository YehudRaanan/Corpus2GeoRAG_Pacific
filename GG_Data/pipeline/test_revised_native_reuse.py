"""Reuse must retain validated native provenance across consolidations."""

from pathlib import Path
import json

import pytest

from GG_Data.pipeline import post_qid_native as native
from GG_Data.pipeline.test_post_qid_native import historical_inputs


def historical_cache(tmp_path):
    inventory, api_dir, source = historical_inputs(tmp_path)
    output = tmp_path / "historical_complete"
    native.consolidate_native(inventory, api_dir, {"Q1", "Q2"}, output)
    return output, source


def test_reuse_preserves_validated_historical_source(tmp_path):
    output, source = historical_cache(tmp_path)
    reused = native.reuse_native({"Q2"}, [output / "full_records.json.gz"])
    assert reused["sources"]["Q2"] == source
    assert reused["records"]["Q2"] == native.historical_record(
        native.read_json(Path(source["file"])), "Q2"
    )


def test_reuse_rechecks_historical_ancestry(tmp_path):
    output, source = historical_cache(tmp_path)
    Path(source["request_file"]).write_text("changed")
    with pytest.raises(ValueError, match="hash differs"):
        native.reuse_native({"Q2"}, [output / "full_records.json.gz"])


def test_historical_empty_map_arrays_are_explicit_and_reproducible(tmp_path):
    _, _, source = historical_inputs(tmp_path)
    raw = native.read_json(Path(source["file"]))
    slot = raw["query"]["pages"][0]["revisions"][0]["slots"]["main"]
    entity = json.loads(slot["content"])
    entity.update(aliases=[], sitelinks=[])
    slot["content"] = json.dumps(entity)
    original = json.dumps(raw)
    record = native.historical_record(raw, "Q2")
    assert record["entity"]["aliases"] == {}
    assert record["entity"]["sitelinks"] == {}
    assert native.historical_selection(raw, "Q2")["derived_empty_map_fields"] == [
        "aliases",
        "sitelinks",
    ]
    assert json.dumps(raw) == original


def test_historical_nonempty_map_array_is_rejected(tmp_path):
    _, _, source = historical_inputs(tmp_path)
    raw = native.read_json(Path(source["file"]))
    slot = raw["query"]["pages"][0]["revisions"][0]["slots"]["main"]
    entity = json.loads(slot["content"])
    entity["aliases"] = ["invented"]
    slot["content"] = json.dumps(entity)
    with pytest.raises(ValueError, match="Missing full historical aliases"):
        native.historical_record(raw, "Q2")
