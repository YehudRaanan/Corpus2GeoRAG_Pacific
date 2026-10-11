from run_data_driven_mapping_poc import (
    compose_direction,
    evidence_score,
    evidence_status,
)


def row(**changes: str) -> dict[str, str]:
    values = {
        "ek_role": "ignored name",
        "wd_property": "ignored property",
        "shared_pairs": "100",
        "pct_of_ek_co_connected": "95",
        "after_largest_target_pct": "90",
        "test_pairs": "20",
        "test_pct_of_ek_co_connected": "92",
        "distinct_targets": "10",
    }
    values.update(changes)
    return values


def test_score_does_not_use_names() -> None:
    first = row(ek_role="country", wd_property="P17")
    second = row(ek_role="unrelated text", wd_property="P999999")
    assert evidence_score(first) == evidence_score(second)
    assert evidence_status(first) == evidence_status(second) == "STRONG_CANDIDATE"


def test_support_gate_and_direction_composition() -> None:
    assert evidence_status(row(shared_pairs="5")) == "INSUFFICIENT_SUPPORT"
    assert compose_direction("same", "same") == "same"
    assert compose_direction("reverse", "reverse") == "same"
    assert compose_direction("same", "reverse") == "reverse"
