import run_incremental_distinct_poc as poc


def test_grouping_keeps_multi_codes_and_never_treats_singletons_as_rules():
    rows = [
        {
            "object_qid": "Q1",
            "event_qid": "E1",
            "object_p31": "T",
            "wikidata_observed": "P17|P710",
        },
        {
            "object_qid": "Q2",
            "event_qid": "E2",
            "object_p31": "T",
            "wikidata_observed": "P17|P710",
        },
        {
            "object_qid": "Q3",
            "event_qid": "E3",
            "object_p31": "T",
            "wikidata_observed": "P710",
        },
        {
            "object_qid": "Q4",
            "event_qid": "E4",
            "object_p31": "U",
            "wikidata_observed": "P276",
        },
        {
            "object_qid": "Q5",
            "event_qid": "E5",
            "object_p31": "U",
            "wikidata_observed": "P276",
        },
    ]
    result = poc.measure(rows, ("object_p31",))
    assert result["mixed_pairs"] == 3
    assert result["supported_consistent_pairs"] == 0
    assert result["held_out_rules_applied"] == 0
    assert poc.measure(rows, ("event_qid",))["singleton_pairs"] == 5
