"""Pin the approved forward-then-reverse population boundary."""

import pytest

from GG_Data.entity_resolution.hundred_page_pilot.match_remaining import (
    bind_resume,
    choose_reverse,
    option_scores,
    reverse_jobs,
    save_rows,
    scoped_rows,
    split_population,
    unresolved_rows,
)


def test_new_rows_forward_old_rows_reverse_even_when_the_group_name_is_equal():
    rows = [dict(source_row_index=i) for i in (1, 2, 3)]
    groups = [dict(source_row_indices=[1, 2])]
    statuses = {1: "SOURCE_REVIEW", 2: "ENTITY_UNRESOLVED", 3: "ACCEPTED_MODEL"}
    forward, previous = split_population(rows, groups, statuses)
    assert [r["source_row_index"] for r in forward] == [1]
    assert [r["source_row_index"] for r in previous] == [2]
    result = unresolved_rows(
        forward, previous, [dict(id="same", source_row_indices=[1])], {"same"}
    )
    assert [r["source_row_index"] for r in result] == [2]


def test_resume_accepts_identical_results_without_overwriting(tmp_path):
    path = tmp_path / "pairs.jsonl"
    save_rows(path, [{"id": "same"}])
    before = path.read_bytes()
    save_rows(path, [{"id": "same"}])
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="differs"):
        save_rows(path, [{"id": "changed"}])


def test_reverse_is_same_revision_and_compatible_and_preserves_unknown():
    group = dict(id="g", page_id=1, revision_id=2, type="PER", name="A", context="A")

    def entity(qid, revision=2, categories=None, unknown=False):
        return dict(
            qid=qid,
            page_id=1,
            revision_id=revision,
            label=qid,
            aliases=[],
            description="",
            type_categories=categories or [],
            type_unknown=unknown,
            qid_source_status="KEEP",
        )

    jobs = reverse_jobs(
        [group],
        [
            entity("Q1", categories=["PER"]),
            entity("Q2", categories=["LOC"]),
            entity("Q3", revision=3, categories=["PER"]),
            entity("Q4", unknown=True),
        ],
    )
    assert [e["qid"] for e in jobs[0]["entities"]] == ["Q1", "Q4"]


def test_stop_wins_ties_and_nonfinite_scores_fail():
    assert choose_reverse({"Q1": 1.0}, 1.0) is None
    assert choose_reverse({"Q2": 2.0, "Q1": 2.0}, 1.0) == "Q1"
    assert choose_reverse({}, 0.0) is None
    with pytest.raises(ValueError, match="finite"):
        choose_reverse({"Q1": float("nan")}, 0.0)


def test_saved_duplicate_options_cannot_be_silently_reused():
    with pytest.raises(ValueError, match="identities"):
        option_scores(
            dict(
                options=[
                    dict(id="Q1", score=1),
                    dict(id="Q1", score=2),
                    dict(id=None, score=0),
                ]
            ),
            {"Q1", None},
        )


def test_scope_requires_exact_saved_revision():
    rows = [dict(page_id=1, revision_id=r) for r in (2, 3)]
    assert scoped_rows(rows, {"3": {"used_revisions": [[1, 2]]}}, 3) == rows[:1]


def test_resume_rejects_orphan_scores_and_changed_binding(tmp_path):
    scores = tmp_path / "scores.jsonl"
    receipt = tmp_path / "inputs.json"
    scores.write_text("{}\n")
    with pytest.raises(ValueError, match="no original"):
        bind_resume(receipt, {"scope": 3}, [scores])
    scores.write_text("")
    bind_resume(receipt, {"scope": 3}, [scores])
    with pytest.raises(ValueError, match="differs"):
        bind_resume(receipt, {"scope": 10}, [scores])
