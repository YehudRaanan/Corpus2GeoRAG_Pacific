"""War scope requires source relations, independently of dates or page topic."""

from GG_Data.pipeline.simplified_war_scope import war_paths, wiki_partof


def test_direct_transitive_inverse_paths_and_cycles():
    graph = {
        "Q362": {"parents": [], "children": [{"qid": "Q10", "property": "P527"}]},
        "Q20": {"parents": [{"qid": "Q10", "property": "P361"}], "children": []},
        "Q30": {"parents": [{"qid": "Q40", "property": "P361"}], "children": []},
        "Q40": {"parents": [{"qid": "Q30", "property": "P361"}], "children": []},
    }
    paths = war_paths(graph, {}, {})
    assert paths["Q362"] == []
    assert [(e["from"], e["to"]) for e in paths["Q20"]] == [
        ("Q20", "Q10"),
        ("Q10", "Q362"),
    ]
    assert paths["Q10"][0]["property"] == "P527_INVERSE"
    assert "Q30" not in paths


def test_wiki_partof_is_explicit_not_incidental_mention_or_date_overlap():
    own = wiki_partof(
        """{{Infobox military conflict|partof=The [[Pacific War]] of [[World War II]]|date=1941}}
An unrelated comparison with [[World War I]]."""
    )
    assert {r["target_title"] for r in own} == {"Pacific War", "World War II"}
    paths = war_paths(
        {},
        {"Q50": dict(partof=own, source={"sha256": "evidence"})},
        {"World War II": "Q362", "Pacific War": "Q10"},
    )
    assert paths["Q50"][-1]["to"] == "Q362"
    assert "Q60" not in paths  # A WWII page or a 1941 date supplies no edge.
    assert paths["Q50"][0]["source"]["sha256"] == "evidence"


def test_unmapped_parent_title_is_not_a_name_identity_assignment():
    own = {
        "Q50": dict(partof=wiki_partof("{{Infobox event|partof=[[Unknown campaign]]}}"))
    }
    assert "Q50" not in war_paths({}, own, {})


def test_reviewed_explicit_context_can_connect_children_but_not_rejected_mentions():
    graph = {"Q51": {"parents": [{"qid": "Q50", "property": "P361"}]}}
    evidence = {
        "Q50": dict(
            status="ACCEPT",
            source={"sha256": "proof"},
            start=0,
            end=20,
            excerpt="An Allied WWII trial",
            reason="WWII_WAR_CRIMES_TRIAL",
        ),
        "Q60": dict(status="REJECT", reason="COMPARISON_ONLY"),
    }
    paths = war_paths(graph, {}, {}, evidence)
    assert paths["Q51"][-1]["property"] == "WIKI_EXPLICIT_WWII_CONTEXT"
    assert paths["Q50"][0]["evidence"] == evidence["Q50"]
    assert "Q60" not in paths
