"""Incremental recovery must never rematch or alter accepted rows."""

import pyarrow as pa
import pytest
import recover_wiki_history as subject


def test_direct_context_allows_short_text_but_global_candidate_does_not():
    assert subject.eligible("1941", direct=True)
    assert not subject.eligible("1941", direct=False)
    assert subject.eligible(
        "This is a complete paragraph with more than eight distinct words.",
        direct=False,
    )


def test_apply_preserves_accepted_rows_and_rejects_nonnull_target():
    table = pa.table(
        {
            "Source": ["A", "B"],
            "Text": ["Known", "Pending"],
            "wiki_page_id": pa.array([1, None], type=pa.int64()),
            "wiki_revision_id": pa.array([10, None], type=pa.int64()),
            "wiki_match_status": ["ACCEPTED", "PENDING"],
            "wiki_text_sha256": ["a", "b"],
        }
    )
    match = {
        "wiki_page_id": 2,
        "wiki_revision_id": 20,
        "wiki_match_status": "VERIFIED_HISTORICAL_NEW_EVIDENCE",
    }
    result = subject.apply_updates(table, {("B", "Pending"): match}, {})
    assert result.slice(0, 1).equals(table.slice(0, 1), check_metadata=True)
    assert result["wiki_page_id"].to_pylist() == [1, 2]
    assert result["wiki_text_sha256"].equals(table["wiki_text_sha256"])
    with pytest.raises(ValueError, match="accepted"):
        subject.apply_updates(table, {("A", "Known"): match}, {})


def test_multiple_candidate_page_matches_are_not_accepted():
    candidates = [{"pageid": 1, "revid": 10}, {"pageid": 2, "revid": 20}]
    assert subject.choose_match(candidates) is None
    assert (
        subject.choose_match([candidates[0], {"pageid": 1, "revid": 11}])["revid"] == 11
    )
