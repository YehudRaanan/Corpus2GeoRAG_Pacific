from build_classifier_candidate_eda import candidate_support, type_closure


def test_type_closure_obeys_depth() -> None:
    entities = {
        "Q1": {"claims": {"P279": [{"mainsnak": {"datavalue": {"value": {"id": "Q2"}}}}]}},
        "Q2": {"claims": {"P279": [{"mainsnak": {"datavalue": {"value": {"id": "Q3"}}}}]}},
    }
    assert type_closure({"Q1"}, entities, 0) == {"Q1"}
    assert type_closure({"Q1"}, entities, 1) == {"Q1", "Q2"}
    assert type_closure({"Q1"}, entities, 2) == {"Q1", "Q2", "Q3"}


def test_candidate_support_uses_narrowest_matching_tier() -> None:
    entities = {
        "Q_CHILD": {
            "claims": {
                "P279": [
                    {"mainsnak": {"datavalue": {"value": {"id": "Q_PARENT"}}}}
                ]
            }
        },
        "Q_PARENT": {"claims": {}},
        "Q_COUNTRY": {"claims": {}},
    }
    seeds = [
        ("S1", "P17", "O1", {"Q_PARENT"}, {"Q_COUNTRY"}),
        ("S2", "P945", "O2", {"Q_CHILD"}, {"Q_COUNTRY"}),
    ]
    tier, support = candidate_support(
        {"Q_CHILD"}, {"Q_COUNTRY"}, seeds, entities
    )
    assert tier == "DIRECT_P31"
    assert support == {"P945": 1}
