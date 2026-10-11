from collections import defaultdict

import run_mapping_discovery as discovery


def test_candidate_direction_and_unique_pair_denominator():
    role = ("battle", "dbpedia_en", "entity", "event", "reified")
    ek = defaultdict(set, {role: {("Q1", "Q2"), ("Q3", "Q2")}})
    wd = {("Q1", "Q2"): {"P607"}, ("Q2", "Q3"): {"P710"}}
    rows = discovery.score_candidates(ek, wd)
    by_property = {row["wd_property"]: row for row in rows}
    assert by_property["P607"]["direction"] == "same"
    assert by_property["P710"]["direction"] == "reverse"
    assert all(row["ek_co_connected_pairs"] == 2 for row in rows)
    assert all(row["shared_pairs"] == 1 for row in rows)


def test_reified_groups_keep_named_graphs_separate(monkeypatch):
    base = "https://eventkg.l3s.uni-hannover.de/resource/"
    graph = "https://eventkg.l3s.uni-hannover.de/graph/dbpedia_en"
    lines = [
        f"<{base}relation_1> <{discovery.SUBJECT}> <{base}entity_1> <{graph}> .\n",
        f"<{base}relation_1> <{discovery.OBJECT}> <{base}event_1> <{graph}> .\n",
        f"<{base}relation_1> <{discovery.ROLE}> <http://dbpedia.org/ontology/battle> <{graph}> .\n",
    ]
    monkeypatch.setattr(discovery, "part_lines", lambda _name: iter(lines))
    assert list(discovery.reified_groups("fixture")) == [
        (
            f"{base}relation_1",
            graph,
            "http://dbpedia.org/ontology/battle",
            f"{base}entity_1",
            f"{base}event_1",
        )
    ]


def test_date_variants_do_not_pick_an_arbitrary_value(monkeypatch):
    resource = "https://eventkg.l3s.uni-hannover.de/resource/event_1"
    field = "http://semanticweb.cs.vu.nl/2009/11/sem/hasBeginTimeStamp"
    graph = "https://eventkg.l3s.uni-hannover.de/graph/wikidata"
    lines = [
        f'<{resource}> <{field}> "1941-01-01"^^<http://www.w3.org/2001/XMLSchema#date> <{graph}> .\n',
        f'<{resource}> <{field}> "1944-01-01"^^<http://www.w3.org/2001/XMLSchema#date> <{graph}> .\n',
    ]
    monkeypatch.setattr(discovery, "complete", lambda _name: True)
    monkeypatch.setattr(discovery, "part_lines", lambda _name: iter(lines))
    result = discovery.date_variants({resource: "Q122100"})
    assert result["same_graph_multivalue_fields"] == 1
    assert result["known_examples"]["Q122100"]["hasBeginTimeStamp"]["wikidata"] == [
        "1941-01-01",
        "1944-01-01",
    ]
