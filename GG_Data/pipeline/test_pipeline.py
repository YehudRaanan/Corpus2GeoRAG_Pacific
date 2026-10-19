"""In-memory checks only: no Daniel POC run, network call, or data output."""

import copy
import hashlib
import io
import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

from GG_Data.pipeline import entities, graph_contract, poc


def saved_row(stage="PAGE_DIRECT_WIKIDATA", assigned="Q1", entity_type="LOC"):
    raw = dict(
        zip(poc.RAW_COLUMNS, ["LOC", 0.97, "Tokyo", 0, 5, "Tokyo", 7, "Tokyo", None])
    )
    identity = [
        0,
        *[raw[k] for k in ("Source", "Index", "start", "end", "entity_group")],
    ]
    mid = (
        "mention-"
        + hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
    )
    return {
        "input_row_number": 0,
        "mention_id": mid,
        "raw": raw,
        "matched_stage": stage,
        "assigned_id": assigned,
        "score": 0.88,
        "type_metadata": {
            "resolved_type": entity_type,
            "extra_evidence": ["untouched"],
        },
        "attempts": [{"rejected": [{"entity_id": "Q2", "why": "TYPE_MISMATCH"}]}],
    }


def test_sample_is_reproducible_without_replacement_and_in_source_order():
    positions = poc.sample_indices(poc.INPUT_COUNT)
    assert positions == poc.sample_indices(poc.INPUT_COUNT)
    assert len(positions) == len(set(positions)) == 10_000
    assert positions == sorted(positions)
    assert positions[-1] < poc.INPUT_COUNT


def test_mention_preserves_source_and_nested_decisions_and_separates_scores():
    saved = saved_row()
    original = copy.deepcopy(saved)
    mention = poc.mention_from_match(saved, saved["raw"], "manifest-hash")
    assert saved == original
    assert mention["raw"] == original["raw"]
    assert mention["attempts"] == original["attempts"]
    assert mention["ner_score"] == 0.97 and mention["match_score"] == 0.88
    assert (mention["entity_id"], mention["entity_type"]) == ("Q1", "LOC")


def test_synthetic_keeps_original_type_without_changing_null_saved_type():
    saved = saved_row("SYNTHETIC", "SYN_TYPE_original", None)
    saved["unresolved_reason"] = "TYPE_MISMATCH"
    mention = poc.mention_from_match(saved, saved["raw"], "manifest-hash")
    assert mention["entity_type"] == "LOC"
    assert mention["type_metadata"]["resolved_type"] is None
    assert mention["assigned_id"] == "SYN_TYPE_original"


def test_normalized_date_has_no_entity_fk():
    saved = saved_row("DATE_NORMALIZED", "DATE:1942-03", "DATE")
    saved["date"] = {"value": "1942-03", "precision": "month"}
    mention = poc.mention_from_match(saved, saved["raw"], "manifest-hash")
    assert mention["entity_id"] is None and mention["entity_type"] is None
    assert mention["date"] == saved["date"]


@pytest.mark.parametrize("change", ["raw", "mention_id", "score", "type"])
def test_input_or_saved_decision_drift_stops(change):
    saved = saved_row()
    raw = copy.deepcopy(saved["raw"])
    if change == "raw":
        raw["word"] = "another entity"
    elif change == "mention_id":
        saved["mention_id"] = "new-id"
    elif change == "score":
        saved["score"] = 0.79
    else:
        saved["type_metadata"]["resolved_type"] = None
    with pytest.raises(ValueError):
        poc.mention_from_match(saved, raw, "manifest-hash")


def test_output_hold_precedes_all_source_io(monkeypatch):
    def forbidden(*args):
        pytest.fail("Input was read before output approval")

    monkeypatch.setattr(poc, "prepare", forbidden)
    with pytest.raises(PermissionError, match="approval"):
        poc.run(Path("input"), Path("cache"), Path("output"), output_approved=False)


def test_prepare_joins_original_positions_and_saved_pages_in_memory(monkeypatch):
    """Exercise the read/validate/join path, using only three invented test rows."""
    rows = []
    for number in range(3):
        row = saved_row()
        row["input_row_number"] = number
        raw = row["raw"]
        identity = [
            number,
            *[raw[k] for k in ("Source", "Index", "start", "end", "entity_group")],
        ]
        row["mention_id"] = (
            "mention-"
            + hashlib.sha256(
                json.dumps(identity, ensure_ascii=False).encode()
            ).hexdigest()
        )
        rows.append(row)
    payload = {
        "source": "Tokyo",
        "status": "RESOLVED",
        "articles": [{"language": "en", "pageid": 1, "title": "Tokyo", "qid": "Q1"}],
    }
    page_name = hashlib.sha256(b"Tokyo").hexdigest() + ".json.gz"
    manifest = {
        "input_sha256": poc.INPUT_SHA256,
        "threshold": 0.8,
        "seed": poc.SEED,
        "outputs": {"matches.json.gz": "artifact-hash"},
        "page_evidence": {page_name: "artifact-hash"},
    }
    monkeypatch.setattr(poc, "INPUT_COUNT", 3)
    monkeypatch.setattr(poc, "SAMPLE_COUNT", 2)
    monkeypatch.setattr(poc, "sample_indices", lambda _: [0, 2])
    monkeypatch.setattr(
        poc,
        "digest",
        lambda p: poc.INPUT_SHA256 if p.name == "input.parquet" else "artifact-hash",
    )
    monkeypatch.setattr(
        poc, "read_json", lambda p: manifest if p.name == "manifest.json" else payload
    )
    monkeypatch.setattr(
        poc.pd, "read_parquet", lambda _: poc.pd.DataFrame([r["raw"] for r in rows])
    )
    monkeypatch.setattr(
        poc.gzip, "open", lambda *args, **kwargs: io.BytesIO(json.dumps(rows).encode())
    )
    result = poc.prepare(Path("input.parquet"), Path("cache"))
    assert [m["input_row_number"] for m in result["mentions"]] == [0, 2]
    assert result["manifest"]["sample_count"] == 2
    assert result["manifest"]["status"] == "STEP_1_ONLY"
    assert len(result["wiki_pages"]) == 1
    assert result["page_evidence"]["Tokyo"] == payload


def test_saved_bilingual_page_keys_and_failure_are_retained():
    mentions = [{"raw": {"Source": source}} for source in ("Tokyo", "missing")]
    articles = [
        {"language": "en", "pageid": 1, "title": "Tokyo", "qid": "Q1"},
        {"language": "ja", "pageid": 2, "title": "東京都", "qid": "Q1"},
    ]
    payloads = {
        "Tokyo": {"source": "Tokyo", "status": "RESOLVED", "articles": articles},
        "missing": {"source": "missing", "status": "MISSING", "articles": []},
    }
    pages = poc.attach_pages(mentions, payloads)
    assert len(pages) == 2
    assert (mentions[0]["wiki_site"], mentions[0]["wiki_page_id"]) == ("enwiki", 1)
    assert mentions[1]["wiki_page_id"] is None
    assert pages[0]["counterpart_page_id"] == 2
    assert mentions[1]["page_resolution"]["status"] == "MISSING"
    assert mentions[1]["page_resolution"]["reference"] == {
        "file": "page_evidence.json.gz",
        "record": "missing",
    }


def test_separate_nodes_resolve_one_assertion_without_copying_it():
    nodes = [
        {"id": graph_contract.graph_node_id(qid, typ), "wikidata_id": qid}
        for qid, typ in [("Q1", "LOC"), ("Q1", "ORG"), ("Q2", "PER")]
    ]
    edges = [{"id": "statement-1", "source": "Q1", "target": "Q2"}]
    original = copy.deepcopy(edges)
    index = graph_contract.endpoint_index(nodes, edges)
    assert index["Q1"] == ("Q1::LOC", "Q1::ORG")
    assert len(edges) == 1 and edges == original
    assert (
        graph_contract.graph_node_id("SYN_NAME_original", "MISC") == "SYN_NAME_original"
    )
    with pytest.raises(ValueError, match="Unknown QID"):
        graph_contract.endpoint_index(nodes, [{"source": "Q1", "target": "Q999"}])


def test_geometry_loader_returns_stored_shapely_and_errors_on_bad_reference(
    monkeypatch,
):
    geometry = Point(139.7, 35.7)
    frame = gpd.GeoDataFrame({"place_id": ["Q1"]}, geometry=[geometry], crs="EPSG:4326")
    monkeypatch.setattr(graph_contract, "digest", lambda _: "a" * 64)
    monkeypatch.setattr(graph_contract.gpd, "read_parquet", lambda _: frame)
    pointer = {"file": "geography.parquet", "place_id": "Q1", "sha256": "a" * 64}
    assert graph_contract.load_geometry(None, Path.cwd()) is None
    assert graph_contract.load_geometry(pointer, Path.cwd()).equals(geometry)
    with pytest.raises(ValueError, match="checksum"):
        graph_contract.load_geometry({**pointer, "sha256": "b" * 64}, Path.cwd())
    with pytest.raises(ValueError, match="found 0"):
        graph_contract.load_geometry({**pointer, "place_id": "Q2"}, Path.cwd())
    with pytest.raises(ValueError, match="leaves"):
        graph_contract.load_geometry(
            {**pointer, "file": "../outside.parquet"}, Path.cwd()
        )


def test_geometry_duplicate_rows_are_not_silently_selected(monkeypatch):
    frame = gpd.GeoDataFrame(
        {"place_id": ["Q1", "Q1"]}, geometry=[Point(1, 1), Point(2, 2)], crs="EPSG:4326"
    )
    monkeypatch.setattr(graph_contract, "digest", lambda _: "a" * 64)
    monkeypatch.setattr(graph_contract.gpd, "read_parquet", lambda _: frame)
    with pytest.raises(ValueError, match="found 2"):
        graph_contract.load_geometry(
            {"file": "geography.parquet", "place_id": "Q1", "sha256": "a" * 64},
            Path.cwd(),
        )


def test_entity_name_uses_newer_revision_without_changing_language_order():
    full = {"lastrevid": 20, "labels": {"en": {"value": "rōmusha"}}}
    matching = {"revision": 10, "labels": {"en": "Romusha"}}
    assert entities.choose_name("Q1", full, matching, [])["value"] == "rōmusha"
    matching["revision"] = 30
    assert (
        entities.choose_name("Q1", full, matching, [])["source"] == "matching_reference"
    )
    matching["revision"] = 20
    with pytest.raises(ValueError, match="Cannot order"):
        entities.choose_name("Q1", full, matching, [])
    assert (
        entities.choose_name("Q1", {}, {"labels": {"ja": "日本"}}, [])["value"]
        == "日本"
    )
    with pytest.raises(ValueError, match="fallback names"):
        entities.choose_name("Q1", {}, {}, [{"raw": {"word": w}} for w in ("a", "b")])


def test_missing_english_in_newer_record_stops_before_choosing_older_english():
    full = {"lastrevid": 20, "labels": {"ja": {"value": "日本"}}}
    matching = {"revision": 10, "labels": {"en": "older English"}}
    with pytest.raises(ValueError, match="discuss language/version priority"):
        entities.choose_name("Q1", full, matching, [])


@pytest.mark.parametrize("qid", ["Q132537", "Q1771928"])
def test_approved_older_english_is_pinned_and_recorded(qid):
    name, older_revision, newer_revision = entities.APPROVED_OLDER_ENGLISH[qid]
    full = {"lastrevid": newer_revision, "labels": {"ja": {"value": "日本"}}}
    matching = {"revision": older_revision, "labels": {"en": name}}
    assert entities.choose_name(qid, full, matching, []) == {
        "value": name,
        "language": "en",
        "source": "matching_reference",
        "revision": older_revision,
        "approval": "2026-10-20_KEEP_OLDER_ENGLISH",
    }
    full["lastrevid"] += 1
    with pytest.raises(ValueError, match="discuss language/version priority"):
        entities.choose_name(qid, full, matching, [])


def test_entities_keep_typed_pairs_synthetic_ids_and_full_native_evidence():
    mentions = [
        {"entity_id": qid, "entity_type": typ, "mention_id": mid, "raw": {"word": word}}
        for qid, typ, mid, word in [
            ("Q1", "LOC", "m1", "original place"),
            ("Q1", "ORG", "m2", "original organization"),
            ("SYN_one", "MISC", "m3", "original unresolved"),
            (None, None, "m4", "1942"),
        ]
    ]
    envelope = {
        "requested_qid": "Q1",
        "entity": {
            "id": "Q1",
            "lastrevid": 20,
            "labels": {"en": {"value": "native name"}},
            "claims": {"P879": [{"unknown": "retained"}]},
            "unknown": {"nested": True},
        },
    }
    metadata = {
        "Q1": {"labels": {"en": "older name"}, "revision": 10, "direct_types": ["Q9"]}
    }
    original = copy.deepcopy(mentions)
    rows = entities.populate(
        mentions, {"Q1": envelope}, metadata, {"Q1": {"provider": "WIKIDATA"}}
    )
    assert mentions == original
    assert {(r["entity_id"], r["type"]) for r in rows} == {
        ("Q1", "LOC"),
        ("Q1", "ORG"),
        ("SYN_one", "MISC"),
    }
    qid_rows = [r for r in rows if r["entity_id"] == "Q1"]
    assert all(r["raw_reference"]["full"] == envelope for r in qid_rows)
    assert all(
        r["direct_types"] == ["Q9"] and r["name"] == "native name" for r in qid_rows
    )
    synthetic = next(r for r in rows if r["entity_id"] == "SYN_one")
    assert synthetic["name"] == "original unresolved" and synthetic["missing"] is None
    assert synthetic["identity_status"] == "SYNTHETIC_UNRESOLVED"
    bad = copy.deepcopy(envelope)
    bad["entity"]["id"] = "Q2"
    with pytest.raises(ValueError, match="ID differs"):
        entities.native_record(bad, "Q1")
