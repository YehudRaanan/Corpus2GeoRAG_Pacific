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


@pytest.mark.parametrize("http_status", [200, 429])
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
            if self.status_code >= 400:
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


@pytest.mark.parametrize("statuses", [(502, 503, 200), (504, 502, 503)])
def test_http_retry_budget_is_persistent_and_attempts_are_immutable(
    tmp_path, monkeypatch, statuses
):
    calls, sleeps = [], []

    class Response:
        headers = {}
        is_redirect = False

        def __init__(self, status):
            self.status_code = status
            self.content = b'{"ok": true}' if status == 200 else b"upstream failure"

        def raise_for_status(self):
            if self.status_code >= 400:
                raise events.requests.exceptions.HTTPError(str(self.status_code))

        def json(self):
            return json.loads(self.content)

    def get(*args, **kwargs):
        status = statuses[len(calls)]
        calls.append(status)
        return Response(status)

    monkeypatch.setattr(events.requests, "get", get)
    monkeypatch.setattr(events.time, "sleep", sleeps.append)
    params = {"query": "ASK{}"}
    for _ in range(2):
        if statuses[-1] == 200:
            data, evidence = events.cached_json(tmp_path, events.QUERY_URL, params)
            assert data == {"ok": True} and evidence["cache"].endswith("attempt_3")
        else:
            with pytest.raises(SourceException):
                events.cached_json(tmp_path, events.QUERY_URL, params)
    assert calls == list(statuses)
    assert sleeps == [1.1, 10, 1.1, 30, 1.1]
    root = next(tmp_path.iterdir())
    assert (root / "response.json").read_bytes() == b"upstream failure"
    assert (root / "attempt_2/response.json").read_bytes() == b"upstream failure"
    assert len(list(root.rglob("request.json"))) == 3
    (root / "response.json").write_bytes(b"changed")
    with pytest.raises(SourceException, match="cache mismatch"):
        events.cached_json(tmp_path, events.QUERY_URL, params)
    assert calls == list(statuses)


def test_resume_old_cached_502_counts_as_attempt_one(tmp_path, monkeypatch):
    import hashlib

    request = {"url": events.QUERY_URL, "params": {"query": "ASK{}"}}
    key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    root = tmp_path / key
    root.mkdir()
    (root / "response.json").write_bytes(b"old 502")
    metadata = {
        "request": request,
        "status": "FAILED",
        "http_status": 502,
        "sha256": events.digest(root / "response.json"),
        "cache": str(root),
    }
    (root / "request.json").write_text(json.dumps(metadata))
    original = (root / "request.json").read_bytes()
    sleeps, calls = [], []

    class Response:
        content = b"{}"
        status_code = 200
        headers = {}
        is_redirect = False

        def raise_for_status(self):
            pass

        def json(self):
            return {}

    monkeypatch.setattr(events.time, "sleep", sleeps.append)
    monkeypatch.setattr(
        events.requests, "get", lambda *a, **kw: calls.append(1) or Response()
    )
    _, evidence = events.cached_json(tmp_path, request["url"], request["params"])
    assert evidence["cache"].endswith("attempt_2")
    assert calls == [1] and sleeps == [10, 1.1]
    assert (root / "request.json").read_bytes() == original
    assert (root / "response.json").read_bytes() == b"old 502"


@pytest.mark.parametrize("malformed", [False, True])
def test_resume_hierarchy_reuses_prior_edges_and_writes_no_model_rows(
    tmp_path, monkeypatch, malformed
):
    from GG_Data.pipeline.event_hierarchy_probe import resume

    prior = tmp_path / "prior"
    prior.mkdir()
    edges = {
        "P31": {"Q1": [{"parent": "Q2", "statement": "p31", "rank": "normal"}]},
        "P279": {},
    }
    (prior / "hierarchy_edges.json").write_text(json.dumps(edges))
    report = {
        "status": "BLOCKED_HIERARCHY_PROBE",
        "queries": [],
        "event_population_complete": False,
        "exception": {
            "request": {"params": {"query": events.class_edges_query(["Q2"], "P279")}}
        },
    }
    (prior / "probe.json").write_text(json.dumps(report))
    (prior / "verification.json").write_text(
        json.dumps(
            {
                "probe_sha256": events.digest(prior / "probe.json"),
                "outputs": {
                    "hierarchy_edges.json": events.digest(
                        prior / "hierarchy_edges.json"
                    )
                },
            }
        )
    )
    before = (prior / "probe.json").read_bytes()
    calls = []

    def source(store, url, params):
        calls.append(params)
        if malformed:
            raise SourceException("Unexpected source data")
        return {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q2"},
                        "present": {"value": "true"},
                        "parent": {
                            "value": f"http://www.wikidata.org/entity/{events.EVENT_ROOT}"
                        },
                        "statement": {"value": "native-statement"},
                        "rank": {"value": "normal"},
                    }
                ]
            }
        }, {"status": "OK"}

    monkeypatch.setattr(events, "cached_json", source)
    output = tmp_path / "output"
    result = resume(prior, output, tmp_path / "cache")
    assert len(calls) == 1
    assert result["event_population_complete"] is False
    assert (prior / "probe.json").read_bytes() == before
    assert not (output / "events.json").exists()
    if malformed:
        assert result["status"] == "BLOCKED_HIERARCHY_PROBE"
        assert not (output / "candidate_classifications.json").exists()
    else:
        assert result["status"] == "HIERARCHY_PROBE_ONLY"
        assert result["event_hierarchy_matches"] == ["Q1"]
