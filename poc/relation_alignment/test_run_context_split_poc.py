import run_context_split_poc as poc


def test_observed_signature_preserves_multiple_codes_and_missingness():
    assert poc.observed_signature({"P17", "P710", "P361"}) == "P17|P710"
    assert poc.observed_signature({"P361"}) == "unrecorded"


def test_context_features_exclude_copied_wikidata_graph():
    context = {
        "Q1": {"types": {"Q100"}},
        "Q2": {"types": {"Q3024240"}},
    }
    info = {"graphs": {"event_kg", "wikidata", "yago", "source_unknown"}}
    assert poc.feature_dict(("Q1", "Q2"), info, context) == {
        "subject_type_Q100": 1,
        "object_type_Q3024240": 1,
        "source_yago": 1,
    }
