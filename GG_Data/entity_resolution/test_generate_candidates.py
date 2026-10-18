"""Small checks for candidate completeness, identity, and source evidence."""

from generate_candidates import NameIndex, mention_id, similarity


def test_index_preserves_alias_evidence_ties_and_type_policy() -> None:
    metadata = {
        "Q1": {
            "label": "Isoroku Yamamoto",
            "aliases": ["Yamamoto"],
            "direct_types": ["Q5"],
        },
        "Q2": {"label": "Yamamoto", "aliases": [], "direct_types": ["Q5"]},
        "Q3": {"label": "Yamamoto", "aliases": [], "direct_types": ["Q43229"]},
        "Q4": {"label": "Noel Irwin", "aliases": [], "direct_types": ["Q5"]},
    }
    index = NameIndex(list(metadata), metadata)
    people = index.find("YAMAMOTO", "PER", 0.8)
    assert [r["entity_id"] for r in people] == ["Q1", "Q2"]
    assert people[0]["matched_name_kind"] == "alias"
    assert people[0]["name_similarity"] == 1
    assert {r["entity_id"] for r in index.find("Yamamoto", "ORG", 1)} == {
        "Q1",
        "Q2",
        "Q3",
    }
    assert all(r["type_check"] == "PENDING" for r in index.find("Yamamoto", "ORG", 1))
    assert index.find("xyz", "PER", 0.35) == []
    assert index.find("", "PER", 0) == []
    assert len(index.find("xyz", "PER", 0)) == 3
    # Compare indexed search to exhaustive label/alias scoring on independent inputs.
    for word in ["Yamamoto", "General Noel Irwin", "Noel", "N\u00f6el Irwin", "x"]:
        for threshold in [0.0, 0.35, 0.8, 1.0]:
            actual = {
                r["entity_id"]: r["name_similarity"]
                for r in index.find(word, "PER", threshold)
            }
            expected = {
                qid: max(similarity(word, name) for name in [e["label"]] + e["aliases"])
                for qid, e in metadata.items()
                if "Q5" in e["direct_types"]
            }
            assert actual == {
                qid: score for qid, score in expected.items() if score >= threshold
            }


def test_mention_identity_is_stable_and_keeps_overlapping_spans() -> None:
    row = {
        "Source": "Example",
        "Index": 6,
        "start": 1,
        "end": 29,
        "entity_group": "PER",
        "score": 0.8,
    }
    assert mention_id(row) == mention_id({**row, "score": 0.99})
    assert mention_id(row) != mention_id({**row, "start": 20})
    assert mention_id(row) != mention_id({**row, "entity_group": "ORG"})
