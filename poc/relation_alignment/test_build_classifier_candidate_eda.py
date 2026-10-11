from build_classifier_candidate_eda import (
    candidate_support,
    non_text_evidence,
    type_closure,
)


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


def evidence_row(**updates: str) -> dict[str, str]:
    row = {
        "full_article_evidence_text": "",
        "page_anchored_evidence_text": "",
        "lead_evidence_status": "",
        "infobox_matching_fields": "",
        "full_article_object_link_anchors": "",
        "qualifier_relation_paths": "",
    }
    row.update(updates)
    return row


def test_infobox_candidates_use_empirical_support_and_allowed_list() -> None:
    result = non_text_evidence(
        evidence_row(infobox_matching_fields="country"),
        ["P17", "P8047"],
        {"country": {"P17": 4, "P8047": 9, "P495": 20}},
    )
    assert result["non_text_candidate_ids"] == "P8047|P17"
    assert result["non_text_review_status"] == "INFOBOX_EMPIRICAL_CANDIDATES_READY"


def test_qualifier_context_keeps_main_and_qualifier_properties() -> None:
    result = non_text_evidence(
        evidence_row(qualifier_relation_paths="P17/P2348"),
        ["P17", "P945"],
        {},
    )
    assert result["non_text_candidate_ids"] == ""
    assert result["qualifier_main_properties"] == "P17"
    assert result["qualifier_properties"] == "P2348"
    assert result["non_text_review_status"] == "QUALIFIER_CONTEXT_READY"
