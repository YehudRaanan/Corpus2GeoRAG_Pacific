"""Correction regressions: fresh populations, language maxima and stage paths."""

import gzip
import json

import pytest

from GG_Data.pipeline import rebuild_poc
from GG_Data.pipeline.poc import digest, read_json


def test_write_streams_json_and_preserves_existing_file_on_failure(
    tmp_path, monkeypatch
):
    value = {"name": "ירושלים", "coordinates": [[35.2, 31.8]] * 1000}
    expected = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    path = tmp_path / "large.json"

    def no_whole_document(*args, **kwargs):
        raise AssertionError("Do not allocate the complete JSON text")

    monkeypatch.setattr(json, "dumps", no_whole_document)
    rebuild_poc.write(path, value)
    assert path.read_text(encoding="utf-8") == expected
    rebuild_poc.write(path, value, compact=True)
    assert read_json(path) == value
    assert path.stat().st_size < len(expected.encode("utf-8"))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Out of range float"):
        rebuild_poc.write(path, {"invalid": float("nan")})
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_geography_sample_follows_original_mentions_to_corrected_ids(tmp_path):
    (tmp_path / "mentions_pages").mkdir()
    (tmp_path / "geography_inputs").mkdir()
    contexts = [dict(mention_id=f"mention-{i}") for i in range(10)]
    sample = [
        dict(place_id=f"Q{i + 100}", source_context=[context])
        for i, context in enumerate(contexts)
    ]
    rebuild_poc.write(tmp_path / "original.json", sample)
    with gzip.open(
        tmp_path / "mentions_pages/mentions.json.gz", "wt", encoding="utf-8"
    ) as stream:
        json.dump([dict(**c, entity_id="Q84") for c in contexts], stream)
    target = dict(
        place_id="Q84", name="London", selection_date="1942", source_context=contexts
    )
    rebuild_poc.write(tmp_path / "geography_inputs/targets.json", [target])
    result = rebuild_poc.geography_sample_inputs(tmp_path, tmp_path / "original.json")
    assert len(result) == 10
    assert [r["original_mention_id"] for r in result] == [
        r["mention_id"] for r in contexts
    ]
    assert all(r["place_id"] == "Q84" and r["selection_date"] == "1942" for r in result)
    target["source_context"] = contexts[1:]
    rebuild_poc.write(tmp_path / "geography_inputs/targets.json", [target])
    with pytest.raises(ValueError, match="absent from corrected target"):
        rebuild_poc.geography_sample_inputs(tmp_path, tmp_path / "original.json")


def test_relevance_uses_corrected_qids_and_preserves_model_rows(tmp_path, monkeypatch):
    source = tmp_path / "entities"
    source.mkdir()
    entities = [
        dict(entity_id="Q1", type="MISC", name="one"),
        dict(entity_id="Q2", type="MISC", name="two"),
        dict(entity_id="Q3", type="LOC", name="three"),
        dict(entity_id="SYN_original", type="MISC", name="unmatched"),
    ]
    for name, value in (
        ("entities", entities),
        ("full_records", {q: {} for q in ("Q1", "Q2", "Q3")}),
    ):
        with gzip.open(source / f"{name}.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(value, stream)
    manifest = dict(outputs={p.name: digest(p) for p in source.iterdir()})
    rebuild_poc.write(source / "manifest.json", manifest)
    rebuild_poc.write(
        source / "verification.json",
        dict(manifest_sha256=digest(source / "manifest.json")),
    )

    def measure(wiki, population, output, selection):
        assert population is True
        assert {r["qid"] for r in read_json(selection)} == {"Q1", "Q2", "Q3"}
        output.mkdir()
        rows = []
        for qid, num, den in (
            ("Q1", 4 if wiki == "enwiki" else 5, 100),
            ("Q2", None, None),
            ("Q3", 1, 1000),
        ):
            rows.append(
                dict(
                    qid=qid,
                    name=qid,
                    wiki=wiki,
                    scope_linking_pages=num,
                    all_linking_pages=den,
                    relevance=num / den if den else None,
                    score_status="SCORED" if den else "UNAVAILABLE_SNAPSHOT_PAGE",
                )
            )
        report = dict(rows=rows)
        rebuild_poc.write(output / "report.json", report)
        return report

    monkeypatch.setattr(rebuild_poc, "measure", measure)
    result = rebuild_poc.relevance(tmp_path)
    assert result["retained_qids"] == 2
    assert result["held_unknown_misc"] == 1
    scores = {r["qid"]: r for r in read_json(tmp_path / "relevance/entity_scores.json")}
    assert scores.keys() == {"Q1", "Q3"}
    assert scores["Q1"]["maximum_relevance"] == 0.05
    assert scores["Q3"]["maximum_relevance"] == 0.001  # LOC bypasses MISC filter.
    assert (
        digest(source / "entities.json.gz") == manifest["outputs"]["entities.json.gz"]
    )


def test_event_stage_routes_only_fresh_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(rebuild_poc, "ROOT", tmp_path)
    base = tmp_path / "GG_Data/pipeline/outputs/corrected"
    matching = base / "matching"
    matching.mkdir(parents=True)
    rebuild_poc.write(
        matching / "manifest.json",
        dict(page_candidate_scope=rebuild_poc.PAGE_CANDIDATE_SCOPE),
    )
    rebuild_poc.write(matching / "london_validation.json", dict(status="CORRECT_QID"))
    calls = []
    monkeypatch.setattr(
        rebuild_poc.event_population,
        "run",
        lambda *a, **kw: calls.append((a, kw)) or {},
    )
    rebuild_poc.run("events", base)
    args, kwargs = calls[0]
    assert args == (base / "events",)
    assert kwargs["fresh_scope"] is True
    assert kwargs["entities_dir"] == base / "entities"
    assert kwargs["scores_dir"] == base / "relevance"


def test_model_resume_and_geography_use_explicit_new_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(rebuild_poc, "ROOT", tmp_path)
    base = tmp_path / "GG_Data/pipeline/outputs/corrected"
    (base / "matching").mkdir(parents=True)
    rebuild_poc.write(
        base / "matching/manifest.json",
        dict(page_candidate_scope=rebuild_poc.PAGE_CANDIDATE_SCOPE),
    )
    rebuild_poc.write(
        base / "matching/london_validation.json", dict(status="CORRECT_QID")
    )
    failed = base / "model"
    failed.mkdir()
    rebuild_poc.write(failed / "report.json", {"status": "STOPPED_FOR_CONSULTATION"})
    stopped_hash = digest(failed / "report.json")
    model = base / "model_qid_name"
    calls = []
    monkeypatch.setattr(
        rebuild_poc.event_model, "run", lambda *a, **kw: calls.append(a) or {}
    )
    monkeypatch.setattr(
        rebuild_poc.geography, "prepare", lambda *a: calls.append(a) or {}
    )
    rebuild_poc.run("model", base, model_dir=model)
    rebuild_poc.run("geography-inputs", base, model_dir=model)
    assert calls == [(model,), (model, base / "geography_inputs")]
    assert digest(failed / "report.json") == stopped_hash
    with pytest.raises(ValueError, match="inside this rebuild bundle"):
        rebuild_poc.run("model", base, model_dir=base.parent / "outside")
