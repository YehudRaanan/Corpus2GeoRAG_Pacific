from run_country_context_poc import features, signature


def test_signature_is_multilabel_and_missing_is_unknown() -> None:
    assert signature({"P17", "P8047"}) == "P17|P8047"
    assert signature(set()) == "unrecorded"


def test_target_codes_are_not_features() -> None:
    row = features(
        ("Q1", "Q2"),
        {"Q1": {"Q10"}, "Q2": {"Q20"}},
        {"Q1": {"Q30"}, "Q2": {"Q40"}},
        {"Q1": {"P17", "P50"}, "Q2": {"P8047", "P60"}},
    )
    assert "S_TYPE_Q10" in row
    assert "O_PARENT_Q40" in row
    assert "S_PROP_P50" in row
    assert "O_PROP_P60" in row
    assert "S_PROP_P17" not in row
    assert "O_PROP_P8047" not in row
