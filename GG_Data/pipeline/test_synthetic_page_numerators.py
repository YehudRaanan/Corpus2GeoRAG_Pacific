"""Synthetic identities keep Daniel's page relationship without a guessed QID."""

from copy import deepcopy

from GG_Data.pipeline.synthetic_page_numerators import synthetic_row


def test_source_relationship_is_counted_without_matching_or_date_rows():
    row = {
        "raw": {"Source": "Missing", "word": "Unknown name", "entity_group": "PER"},
        "assigned_id": "SYN_123",
        "matched_stage": "SYNTHETIC",
        "unresolved_reason": "NO_NAME_ABOVE_THRESHOLD",
        "mention_id": "mention-123",
        "input_row_number": 7,
    }
    original = deepcopy(row)
    result = synthetic_row(row, {"Missing"})
    assert result["entity_id"] == "SYN_123" and result["scope_page_count"] == 1
    assert result["source_title"] == "Missing"
    assert all(
        result[k] is None
        for k in ("qid", "wiki_page_id", "all_linking_pages", "relevance")
    )
    assert row == original
    assert synthetic_row(row, {"Other"}) is None
    assert (
        synthetic_row({**row, "matched_stage": "ALREADY_MATCHED"}, {"Missing"}) is None
    )
    row["raw"]["entity_group"] = "DATE"
    assert synthetic_row(row, {"Missing"}) is None
