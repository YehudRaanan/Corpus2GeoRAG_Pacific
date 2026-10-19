"""Source/cache checks only; no live requests or Daniel matching."""

import json

import pytest

from GG_Data.pipeline import events
from GG_Data.pipeline.relations import SourceException


def test_discovery_preserves_ranks_directions_and_scope():
    query = events.discovery_query(["Q17", "Q30"])
    assert "VALUES ?entity { wd:Q17 wd:Q30 }" in query
    assert "D_TO_E" in query and "E_TO_D" in query
    assert "p:P31/ps:P31/(p:P279/ps:P279)* wd:Q140451665" in query
    assert "wdt:" not in query and "LIMIT" not in query
    for invalid in ([], ["Q17", "Q17"], ["Q17 } UNION { ?s ?p ?o"]):
        with pytest.raises(ValueError):
            events.discovery_query(invalid)


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


def test_failed_request_is_saved_and_never_automatically_retried(tmp_path, monkeypatch):
    calls = []

    class Response:
        content = b'{"error": {"code": "maxlag"}}'
        status_code = 200
        headers = {}
        is_redirect = False

        def raise_for_status(self):
            pass

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
