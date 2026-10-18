import random

from bilingual_page_pilot import choose
from direct_wikidata_pilot import clean_name, normalize_date, page_find
from generate_candidates import NameIndex


def test_date_precision_and_validation():
    assert normalize_date("March 1942") == {"value": "1942-03", "precision": "month"}
    assert normalize_date("Feb 2, 1955")["value"] == "1955-02-02"
    assert normalize_date("1942–43")["value"] == "1942/1943"
    assert normalize_date("late 1942")["qualifier"] == "late"
    assert normalize_date("December")["value"] == "--12"
    assert "error" in normalize_date("29 February 1943")
    assert normalize_date("29 February 1944")["value"] == "1944-02-29"
    assert "error" in normalize_date("yesterday")


def test_cleanup_is_page_only_and_keeps_raw_names():
    assert clean_name("  U. S. ★ ") == "US"
    assert clean_name("U.S.") == "US"
    md = {"Q1": {"label": "U.S.", "direct_types": ["Q618123"]}}
    normal = {"Q1": {**md["Q1"], "label": "US"}}
    original, cleaned = NameIndex(["Q1"], md), NameIndex(["Q1"], normal)
    assert not original.find("US", "MISC", 0.8)
    result = choose(
        page_find(original, cleaned, "US", {"Q1": {"US": "U.S."}}),
        "LOC",
        md,
        random.Random(1),
    )
    assert result["entity_id"] == "Q1"
    assert result["matched_name"] == "U.S."
    assert result["normalization"] == "PAGE_ONLY_SPACE_SYMBOL_CLEANUP"


def test_single_wikidata_type_override_preserves_evidence():
    md = {
        "place": {"direct_types": ["Q618123"]},
        "ambiguous": {"direct_types": ["Q43229", "Q618123"]},
        "unknown": {"direct_types": []},
        "list": {"direct_types": ["Q13406463"]},
        "university": {"direct_types": ["Q43229", "bad_branch"]},
        "bad_branch": {"parents": ["Q13406463"]},
    }

    def candidate(q: str) -> dict:
        return {"entity_id": q, "name_similarity": 1.0}

    result = choose(
        [candidate("place")],
        "ORG",
        md,
        random.Random(1),
        prefer_single_wikidata_type=True,
    )
    assert result["type_metadata"] == {
        "original_type": "ORG",
        "resolved_type": "LOC",
        "type_changed": True,
        "type_source": "WIKIDATA_SINGLE_MAPPED_TYPE",
        "wikidata_mapped_types": ["LOC"],
        "wikidata_direct_types": ["Q618123"],
    }
    for q in ("ambiguous", "unknown", "list"):
        assert (
            choose(
                [candidate(q)],
                "PER",
                md,
                random.Random(1),
                prefer_single_wikidata_type=True,
            )["status"]
            != "MATCHED"
        )
    assert (
        choose(
            [candidate("university")],
            "ORG",
            md,
            random.Random(1),
            prefer_single_wikidata_type=True,
        )["type_metadata"]["resolved_type"]
        == "ORG"
    )
    result = choose(
        [candidate("place"), candidate("university")],
        "ORG",
        md,
        random.Random(1),
        prefer_single_wikidata_type=True,
    )
    assert result["entity_id"] == "university"
    assert (
        choose(
            [candidate("place"), candidate("university")],
            "PER",
            md,
            random.Random(1),
            prefer_single_wikidata_type=True,
        )["status"]
        == "TYPE_MISMATCH"
    )
