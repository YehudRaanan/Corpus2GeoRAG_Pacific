"""Approved penalties: boundaries, ranking, overrides and legacy replay."""

import copy
import random

import pytest

from bilingual_page_pilot import choose
from full_direct_wikidata import assign
from matching_scoring import require_measurements, score_candidate


def test_measured_unknown_is_valid_but_incomplete_processing_stops():
    require_measurements(
        {"Q1": {"relevance_status": "UNAVAILABLE_BOTH_LANGUAGES", "relevance": None}},
        {"Q1"},
    )
    for measured in (
        {},
        {"Q1": {"relevance_status": "UNMEASURED", "relevance": None}},
        {"Q1": {"relevance_status": "SCORED", "relevance": None}},
    ):
        with pytest.raises(ValueError):
            require_measurements(measured, {"Q1"})


def test_failed_regression_gate_prevents_rebuild_before_output(tmp_path):
    import json
    from rebuild_page_scoped import prepare

    gate = tmp_path / "gate.json"
    gate.write_text(
        json.dumps({"full_matching_authorized_by_gate": False}), encoding="utf-8"
    )
    output = tmp_path / "new_run"
    with pytest.raises(ValueError, match="regression gate"):
        prepare(tmp_path / "unused_source", output, tmp_path / "unused_scores", gate)
    assert not output.exists()


@pytest.mark.parametrize(
    "raw,types,relevance,expected",
    [
        (1.0, {"LOC"}, 0.01, 1.0),
        (1.0, {"LOC"}, 0.009, 0.95),
        (1.0, {"PER"}, 0.009, 0.855),
        (1.0, {"PER"}, None, 0.90),
        (0.8, {"LOC"}, None, 0.8),
        (0.8, set(), None, 0.8),
    ],
)
def test_penalties_preserve_raw_score_and_unknown(raw, types, relevance, expected):
    candidate = {"entity_id": "Q1", "name_similarity": raw}
    record = {"matching_relevance": {"relevance": relevance}}
    before = copy.deepcopy((candidate, record))
    result = score_candidate(candidate, "LOC", types, record)
    assert result["adjusted_similarity"] == pytest.approx(expected)
    assert result["name_similarity"] == result["raw_name_similarity"] == raw
    assert (candidate, record) == before


@pytest.mark.parametrize(
    "field,value", [("raw", float("nan")), ("raw", 1.1), ("relevance", -1)]
)
def test_invalid_scores_stop(field, value):
    with pytest.raises(ValueError):
        score_candidate(
            {"name_similarity": value if field == "raw" else 1},
            "LOC",
            {"LOC"},
            {
                "matching_relevance": {
                    "relevance": value if field == "relevance" else None
                }
            },
        )


def test_adjusted_ranking_and_conflicting_single_type_override():
    metadata = {
        "Q1": {
            "direct_types": ["Q5"],
            "matching_relevance": {"relevance": 0.001, "relevance_status": "SCORED"},
        },
        "Q2": {"direct_types": ["Q5"], "matching_relevance": {"relevance": 0.1}},
        "Q5": {"parents": []},
    }
    candidates = [
        {"entity_id": "Q1", "name_similarity": 1.0, "matched_name": "One"},
        {"entity_id": "Q2", "name_similarity": 0.98, "matched_name": "Two"},
    ]
    selected = choose(
        candidates,
        "PER",
        metadata,
        random.Random(1),
        prefer_single_wikidata_type=True,
        apply_penalties=True,
    )
    assert selected["entity_id"] == "Q2"
    row = {"mention_id": "mention-test", "raw": {"entity_group": "LOC"}, "attempts": []}
    assign(row, candidates[:1], metadata, "PAGE_DIRECT_WIKIDATA", apply_penalties=True)
    assert row["score"] == pytest.approx(0.855)
    assert row["type_metadata"]["resolved_type"] == "PER"
    assert row["matching_penalties"]["type_conflict"] is True
    assert row["raw_name_similarity"] == 1


def test_threshold_failure_retains_evidence_and_unknown_type_stays_unknown():
    candidate = {"entity_id": "Q1", "name_similarity": 0.8}
    metadata = {
        "Q1": {"direct_types": ["Q5"], "matching_relevance": {"relevance": 0.001}},
        "Q5": {"parents": []},
    }
    result = choose(
        [candidate],
        "PER",
        metadata,
        random.Random(1),
        prefer_single_wikidata_type=True,
        apply_penalties=True,
    )
    assert result["status"] == "NO_ADJUSTED_SCORE_ABOVE_THRESHOLD"
    assert result["rejected"][0]["adjusted_similarity"] == pytest.approx(0.76)
    metadata["Q1"]["direct_types"] = []
    assert (
        choose(
            [candidate],
            "PER",
            metadata,
            random.Random(1),
            prefer_single_wikidata_type=True,
            apply_penalties=True,
        )["status"]
        == "TYPE_UNKNOWN"
    )


def test_ties_remain_seeded_and_legacy_replay_is_explicit():
    candidates = [{"entity_id": q, "name_similarity": 1.0} for q in ("Q1", "Q2")]
    metadata = {q: {"direct_types": ["Q5"]} for q in ("Q1", "Q2")}
    first = choose(candidates, "PER", metadata, random.Random(42), apply_penalties=True)
    assert first == choose(
        candidates, "PER", metadata, random.Random(42), apply_penalties=True
    )
    assert first["tied_ids"] == ["Q1", "Q2"]
    legacy = choose(candidates, "PER", metadata, random.Random(42))
    assert "adjusted_similarity" not in legacy


def test_unmeasured_real_candidate_stops_before_decision():
    row = {"mention_id": "mention-x", "raw": {"entity_group": "LOC"}, "attempts": []}
    with pytest.raises(ValueError):
        assign(
            row,
            [{"entity_id": "Q1", "name_similarity": 1}],
            {"Q1": {"direct_types": []}},
            "PAGE_DIRECT_WIKIDATA",
            apply_penalties=True,
        )
    assert not row["attempts"]


def test_review_gate_preserves_automatic_report_and_requires_exact_qid(tmp_path):
    import json
    from bilingual_page_pilot import digest
    from evaluate_matching_penalties import accept_review
    from matching_scoring import POLICY

    source = tmp_path / "source.json"
    source.write_text("{}", encoding="utf-8")
    report_file = tmp_path / "report.json"
    report_file.write_text(
        json.dumps(
            dict(
                scoring_policy=POLICY,
                baseline={"wrong": 1},
                rows=[
                    dict(
                        index=1,
                        outcome="CORRECT",
                        expected_baseline="CORRECT",
                        updated={"assigned_id": "Q1"},
                    ),
                    dict(
                        index=2,
                        outcome="CHANGED_QID_REQUIRES_REVIEW",
                        expected_baseline="WRONG",
                        updated={"assigned_id": "Q2"},
                    ),
                ],
            )
        ),
        encoding="utf-8",
    )
    original = digest(report_file)
    review = dict(
        automatic_report_sha256=original,
        source_records=str(source),
        source_records_sha256=digest(source),
        reviewed_counts={"CORRECT": 1, "WRONG": 1},
        cases=[dict(index=2, assigned_id="Q3", outcome="WRONG")],
    )
    path = tmp_path / "case_review.json"
    path.write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(ValueError, match="changes an assignment"):
        accept_review(tmp_path, path)
    review["cases"][0]["assigned_id"] = "Q2"
    path.write_text(json.dumps(review), encoding="utf-8")
    gate = accept_review(tmp_path, path)
    assert gate["full_matching_authorized_by_gate"]
    assert gate["known_wrong_case_indices"] == [2]
    assert digest(report_file) == original
