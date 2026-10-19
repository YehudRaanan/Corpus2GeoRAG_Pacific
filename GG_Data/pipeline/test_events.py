"""Source/cache checks only; no live requests or Daniel matching."""

import json

import pytest

from GG_Data.pipeline import events
from GG_Data.pipeline.relations import SourceException


def test_small_incoming_query_preserves_all_ranks_without_hierarchy_join():
    query = events.incoming_query("Q17")
    assert "?statement ?statementProperty wd:Q17" in query
    assert "wikibase:statementProperty ?statementProperty" in query
    assert "?subject ?claim ?statement" in query
    assert "wikibase:rank ?rank" in query
    assert all(word not in query for word in ("wdt:", "LIMIT", "P279"))
    assert '"http://www.wikidata.org/entity/Q"' in query
    with pytest.raises(ValueError):
        events.incoming_query("Q17 } UNION { ?s ?p ?o")


def test_native_outgoing_links_keep_all_ranks_and_only_main_item_values():
    claims = [
        {
            "id": f"Q17${rank}",
            "rank": rank,
            "mainsnak": {
                "property": "P17",
                "datatype": "wikibase-item",
                "datavalue": {"value": {"entity-type": "item", "id": "Q30"}},
            },
        }
        for rank in ("normal", "preferred", "deprecated")
    ]
    record = {
        "id": "Q17",
        "claims": {"P17": claims + [{"mainsnak": {"snaktype": "novalue"}}]},
    }
    links = events.item_links(record)
    assert {r["raw_statement"]["rank"] for r in links} == {
        "normal",
        "preferred",
        "deprecated",
    }
    assert len(links) == 3 and all(r["object_qid"] == "Q30" for r in links)
    claims[0]["mainsnak"]["datavalue"]["value"]["id"] = "SYN_new"
    with pytest.raises(SourceException):
        events.item_links(record)


def test_cache_preserves_raw_response_reuses_success_and_rejects_tampering(
    tmp_path, monkeypatch
):
    raw = b'{"unknown": [1], "claims": {"P31": [{"rank": "deprecated"}]}}'

    class Response:
        content = raw
        status_code = 200
        headers = {"content-type": "application/json"}
        is_redirect = False

        def raise_for_status(self):
            pass

        def json(self):
            return json.loads(raw)

    calls = []
    monkeypatch.setattr(events.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        events.requests, "get", lambda *a, **kw: calls.append(kw) or Response()
    )
    data, evidence = events.cached_json(tmp_path, events.QUERY_URL, {"query": "ASK{}"})
    assert data["claims"]["P31"][0]["rank"] == "deprecated"
    assert evidence["status"] == "OK"
    assert len(calls) == 1 and calls[0]["allow_redirects"] is False
    assert events.cached_json(tmp_path, events.QUERY_URL, {"query": "ASK{}"}) == (
        data,
        evidence,
    )
    assert len(calls) == 1
    body = tmp_path / next(iter(tmp_path.iterdir())).name / "response.json"
    assert body.read_bytes() == raw
    body.write_bytes(b"{}")
    with pytest.raises(SourceException, match="cache mismatch"):
        events.cached_json(tmp_path, events.QUERY_URL, {"query": "ASK{}"})


@pytest.mark.parametrize("http_status", [200, 502])
def test_failed_request_is_saved_and_never_automatically_retried(
    tmp_path, monkeypatch, http_status
):
    calls = []

    class Response:
        content = (
            b'{"error": {"code": "maxlag"}}'
            if http_status == 200
            else b"<html>502 Bad Gateway</html>"
        )
        status_code = http_status
        headers = {}
        is_redirect = False

        def raise_for_status(self):
            if self.status_code == 502:
                raise events.requests.exceptions.HTTPError("502 Bad Gateway")

        def json(self):
            return json.loads(self.content)

    monkeypatch.setattr(events.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        events.requests, "get", lambda *a, **kw: calls.append(1) or Response()
    )
    for _ in range(2):
        with pytest.raises(SourceException):
            events.cached_json(tmp_path, events.QUERY_URL, {"query": "ASK{}"})
    assert calls == [1]
    directory = next(tmp_path.iterdir())
    assert (directory / "response.json").read_bytes() == Response.content
    evidence = json.loads((directory / "request.json").read_text())
    assert evidence["http_status"] == http_status and evidence["status"] == "FAILED"


def test_timeout_is_recorded_without_retry_or_partial_success(tmp_path, monkeypatch):
    calls = []

    def timeout(*args, **kwargs):
        calls.append(1)
        raise events.requests.exceptions.ReadTimeout("read timeout=45")

    monkeypatch.setattr(events.time, "sleep", lambda _: None)
    monkeypatch.setattr(events.requests, "get", timeout)
    with pytest.raises(SourceException, match="request failed"):
        events.cached_json(tmp_path, events.QUERY_URL, {"query": "ASK{}"})
    directory = next(tmp_path.iterdir())
    evidence = json.loads((directory / "request.json").read_text())
    assert evidence["status"] == "FAILED" and "timeout=45" in evidence["error"]
    assert not (directory / "response.json").exists()
    with pytest.raises(SourceException, match="Incomplete current Wikidata cache"):
        events.cached_json(tmp_path, events.QUERY_URL, {"query": "ASK{}"})
    assert calls == [1]


def test_direct_hierarchy_edges_and_cycle_safe_path_have_no_truthy_or_depth_filter():
    query = events.class_edges_query(["Q1", "Q2"], "P279")
    assert "p:P279 ?statement" in query and "ps:P279 ?parent" in query
    assert "?present" in query and "OPTIONAL" in query
    assert all(word not in query for word in ("DeprecatedRank", "wdt:", "LIMIT"))
    for qids, prop in (([], "P279"), (["Q1"], "P17"), (["Q1"] * 11, "P31")):
        with pytest.raises(ValueError):
            events.class_edges_query(qids, prop)
    cycle = {"parent": "Q1", "statement": "cycle", "rank": "deprecated"}
    root = {"parent": events.EVENT_ROOT, "statement": "root", "rank": "normal"}
    parents = {"Q1": [{"parent": "Q2", "statement": "a"}], "Q2": [cycle, root]}
    path = events.hierarchy_path("Q1", parents)
    assert [edge["statement"] for edge in path] == ["a", "root"]
    assert events.hierarchy_path("Q1", {"Q1": [cycle]}) is None
    assert events.hierarchy_path(events.EVENT_ROOT, {}) == []
    with pytest.raises(SourceException, match="Incomplete Event hierarchy"):
        events.hierarchy_path("Q1", {"Q1": [{"parent": "Q2"}]})
