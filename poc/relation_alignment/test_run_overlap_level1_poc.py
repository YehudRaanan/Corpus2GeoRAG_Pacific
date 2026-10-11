from run_overlap_level1_poc import (
    decide_eventkg_group,
    warsampo_evidence_status,
    wikidata_parents,
)


def eventkg_candidate(property_id: str, score_case: str = "strong") -> dict[str, str]:
    strong = score_case == "strong"
    return {
        "wd_property": property_id,
        "shared_pairs": "100" if strong else "5",
        "pct_of_ek_co_connected": "95" if strong else "40",
        "after_largest_target_pct": "90" if strong else "30",
        "test_pairs": "20" if strong else "1",
        "test_pct_of_ek_co_connected": "90" if strong else "20",
        "distinct_targets": "20" if strong else "2",
    }


def test_strong_overlap_inherits_all_wikidata_parents() -> None:
    source_rows = [
        {
            "source": "Wikidata",
            "resolution_status": "DECLARED_PARENT",
            "normalized_level2_uri": "http://www.wikidata.org/prop/direct/P1",
            "level1_uri": "http://example.org/parent",
            "level1_label": "parent",
            "mapping_basis": "WIKIDATA_P1647",
        }
    ]
    parents = wikidata_parents(source_rows)

    action, margin = decide_eventkg_group([eventkg_candidate("P1")], parents)

    assert action == "PROVISIONAL_LEVEL1"
    assert margin == 100
    assert parents["P1"][0]["level1_uri"] == "http://example.org/parent"


def test_strong_level2_match_without_parent_stays_without_level1() -> None:
    action, _ = decide_eventkg_group([eventkg_candidate("P1")], {})

    assert action == "LEVEL2_ONLY_NO_WIKIDATA_PARENT"


def test_warsampo_gate_requires_repeated_pair_support() -> None:
    strong = {
        "shared_pairs": "20",
        "pct_of_war_co_connected": "100",
        "pct_of_wd_co_connected": "90",
    }
    weak = strong | {"shared_pairs": "3"}

    assert warsampo_evidence_status(strong) == "STRONG_CANDIDATE"
    assert warsampo_evidence_status(weak) == "INSUFFICIENT_SUPPORT"
