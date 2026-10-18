"""Check fixed notebook rules, all extraction groups, and directed expansion."""

import networkx as nx
import numpy as np
import pandas as pd
import pytest
from generate_candidates import NameIndex
from notebook_rules import decide, hits_steps
from run_notebook_matching import PARAMETERS, context_graph, select


def test_all_groups_use_the_same_name_search_including_dates() -> None:
    metadata = {
        "human": {"label": "Example", "aliases": [], "direct_types": ["Q5"]},
        "other": {"label": "Example", "aliases": [], "direct_types": []},
    }
    index = NameIndex(list(metadata), metadata)
    for group in PARAMETERS["entity_groups"]:
        expected = {"human"} if group == "PER" else {"human", "other"}
        assert {c["entity_id"] for c in index.find("Example", group, 0.35)} == expected
    date = NameIndex(["year"], {"year": {"label": "1945", "aliases": []}})
    assert date.find("1945", "DATE", 0.35)[0]["name_similarity"] == 1.0


def test_hits_matches_matrix_updates_and_preserves_notebook_history() -> None:
    known = nx.DiGraph(
        [("page", "a"), ("page", "b"), ("a", "b"), ("b", "c"), ("c", "outside")]
    )
    graph = context_graph(known, {"page", "a", "isolated"})
    assert set(graph) == {"page", "a", "b", "isolated"}
    assert set(graph.edges()) == {("page", "a"), ("page", "b"), ("a", "b")}
    all_steps = hits_steps(graph, 20)
    last = hits_steps(graph, 20, keep_history=False)
    pd.testing.assert_frame_equal(
        all_steps[all_steps.iteration == 20].reset_index(drop=True), last
    )
    matrix = nx.to_numpy_array(graph)
    hubs = np.full(len(graph), 1 / len(graph))
    for _ in range(20):
        authority = matrix.T @ hubs
        authority /= authority.sum() or 1
        hubs = matrix @ authority
        hubs /= hubs.sum() or 1
    assert last.authority.to_numpy() == pytest.approx(authority)
    assert last.hub.to_numpy() == pytest.approx(hubs)
    assert last.set_index("qid").loc["isolated", "authority"] == 0


def test_automatic_rule_rejects_ties_and_weak_graph_winners() -> None:
    def options(rows):
        return pd.DataFrame(rows, columns=["qid", "name_similarity", "authority"])

    assert select([])["decision"] == "UNRESOLVED"
    single = options([("a", 0.8, 0.0)])
    assert decide(single, 0.8, 0.2)["suggested_qid"] == "a"
    tied = options([("a", 1.0, 0.5), ("b", 1.0, 0.5)])
    assert decide(tied, 0.8, 0.0)["decision"] == "UNRESOLVED"
    weak_winner = options([("a", 0.79, 0.9), ("b", 1.0, 0.1)])
    assert decide(weak_winner, 0.8, 0.2)["decision"] == "UNRESOLVED"
    separated = options([("a", 0.8, 0.8), ("b", 1.0, 0.2)])
    result = decide(separated, 0.8, 0.2)
    assert result["suggested_qid"] == "a"
    assert result["authority_gap"] == pytest.approx(0.75)
