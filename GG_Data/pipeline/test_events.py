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


@pytest.mark.parametrize("http_status", [200, 400])
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


@pytest.mark.parametrize(
    "statuses", [(502, 503, 200), (504, 502, 503), (429, 429, 429)]
)
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
    assert sleeps == [5, 10, 5, 30, 5]
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
    assert calls == [1] and sleeps == [10, 5]
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


@pytest.mark.parametrize("value", ["120", "Tue, 20 Oct 2026 00:02:00 GMT"])
def test_retry_after_deadline_is_respected_across_cache_resume(value):
    from datetime import datetime, timezone

    received = datetime(2026, 10, 20, tzinfo=timezone.utc)
    evidence = {
        "response_headers": {"Retry-After": value},
        "retrieved_at": received.isoformat(),
        "cache": "saved",
    }
    assert events.retry_delay(evidence, 1, received) == 120
    assert events.retry_delay(evidence, 2, received.replace(minute=1)) == 60
    assert events.retry_delay(evidence, 1, received.replace(minute=3)) == 10
    evidence["response_headers"]["Retry-After"] = "invalid"
    with pytest.raises(SourceException, match="Invalid Retry-After"):
        events.retry_delay(evidence, 1, received)


def test_rank_diagnostic_removes_deprecated_paths_without_mutating_source():
    from GG_Data.pipeline.event_hierarchy_rank_test import compare

    def edge(parent, rank="normal"):
        return {"parent": parent, "rank": rank, "statement": "native"}

    root = events.EVENT_ROOT
    edges = {
        "P31": {
            "Q1": [edge("Q2")],
            "Q3": [edge("Q4")],
            "Q5": [edge(root, "deprecated")],
            "Q6": [edge("Q7")],
        },
        "P279": {
            "Q2": [edge(root)],
            "Q4": [edge(root, "http://wikiba.se/ontology#DeprecatedRank")],
            "Q7": [edge(root, "deprecated"), edge("Q8")],
            "Q8": [edge(root)],
        },
    }
    original = json.dumps(edges)
    rows = compare(edges)
    assert sum(row["all_ranks_match"] for row in rows) == 4
    assert {row["qid"] for row in rows if row["non_deprecated_match"]} == {"Q1", "Q6"}
    assert json.dumps(edges) == original


def test_approved_classifier_rejects_unknown_source_rank():
    edges = {
        "P31": {"Q1": [{"parent": events.EVENT_ROOT, "rank": "unknown"}]},
        "P279": {},
    }
    with pytest.raises(SourceException, match="Unknown Event hierarchy rank"):
        events.classify_events(edges)


@pytest.mark.parametrize("changed", [False, True])
def test_candidate_check_keeps_source_and_stops_on_native_classification_change(
    tmp_path, monkeypatch, changed
):
    from GG_Data.pipeline.event_candidate_check import run

    source = tmp_path / "source"
    source.mkdir()
    edges = {
        "P31": {
            "Q1": [
                {"parent": events.EVENT_ROOT, "rank": "normal", "statement": "Q1-guid"}
            ]
        },
        "P279": {},
    }
    path = source / "hierarchy_edges.json"
    path.write_text(json.dumps(edges))
    before = path.read_bytes()
    (source / "verification.json").write_text(
        json.dumps({"outputs": {path.name: events.digest(path)}})
    )
    claim = {
        "id": "Q1$guid",
        "rank": "deprecated" if changed else "normal",
        "mainsnak": {
            "property": "P31",
            "datatype": "wikibase-item",
            "datavalue": {"value": {"entity-type": "item", "id": events.EVENT_ROOT}},
        },
    }
    record = {
        "id": "Q1",
        "labels": {"en": {"value": "native name"}},
        "claims": {"P31": [claim]},
        "lastrevid": 1,
    }
    monkeypatch.setattr(events, "current_record", lambda *a: (record, {"status": "OK"}))
    output = tmp_path / "output"
    result = run(source, output, tmp_path / "cache")
    assert path.read_bytes() == before
    assert result["event_rows_written"] == 0
    assert result["event_population_complete"] is False
    assert not (output / "events.json").exists()
    if changed:
        assert result["status"] == "BLOCKED_CANDIDATE_CHECK"
        assert len(result["records"]) == 0
    else:
        assert result["status"] == "NATIVE_CANDIDATES_CHECKED_LINK_GATE_PENDING"
        assert result["records"][0]["name"] == "native name"


def test_event_link_gate_keeps_all_ranks_deduplicates_statements_and_checks_exclusions(
    monkeypatch,
):
    from GG_Data.pipeline import event_candidate_check as check

    def link(sid, target, rank="normal"):
        return dict(
            subject_qid="Q1",
            object_qid=target,
            source_predicate="wd:P17",
            source_record_id=sid,
            rank=rank,
        )

    rule = dict(
        direction_to_level2="same",
        formal_component_conflict="False",
        level2_relation_id="wd:P17",
        relation_map_version="test",
    )
    approved_exclusion = dict(
        source_predicate="wd:P17",
        subject_qid="Q1",
        object_qid="Q4",
        reason="exact approved case",
    )
    monkeypatch.setattr(
        check, "load_exclusions", lambda: {("Wikidata", "Q1$CC"): approved_exclusion}
    )
    rows = [
        link("Q1$AA", "Q2"),
        link("http://www.wikidata.org/entity/statement/Q1-AA", "Q2"),
        link("Q1$BB", "Q3", "deprecated"),
        link("Q1$CC", "Q4"),
        link("Q1$DD", "Q5"),
    ]
    kept, excluded = check.qualifying_links(
        rows, "Q1", {"Q2", "Q3", "Q4"}, {("Wikidata", "wd:P17"): rule}
    )
    assert len(kept) == 2 and {r["daniel_qid"] for r in kept} == {"Q2", "Q3"}
    assert len(excluded) == 1 and excluded[0]["reason"] == "exact approved case"
    rows[1]["object_qid"] = "Q3"
    with pytest.raises(SourceException, match="Conflicting Event assertion retrievals"):
        check.qualifying_links(
            rows, "Q1", {"Q2", "Q3", "Q4"}, {("Wikidata", "wd:P17"): rule}
        )


def test_incoming_event_links_validate_direct_statement_identity():
    from GG_Data.pipeline.event_candidate_check import incoming_links

    row = {
        k: dict(value=v)
        for k, v in dict(
            subject="http://www.wikidata.org/entity/Q1",
            property="http://www.wikidata.org/entity/P17",
            statement="http://www.wikidata.org/entity/statement/Q1-AB-CD",
            rank="http://wikiba.se/ontology#DeprecatedRank",
        ).items()
    }
    data = {"results": {"bindings": [row]}}
    parsed = incoming_links(data, "Q2")
    assert parsed[0]["object_qid"] == "Q2" and parsed[0]["rank"] == "deprecated"
    row["subject"]["value"] = "http://www.wikidata.org/entity/Q3"
    with pytest.raises(SourceException, match="Unexpected incoming Event assertion"):
        incoming_links(data, "Q2")


def test_bounded_query_preserves_direct_all_rank_scope_and_validates_populations():
    query = events.incoming_candidates_query(["Q1", "Q2"], ["Q3"])
    assert "VALUES ?subject { wd:Q1 wd:Q2 }" in query
    assert "VALUES ?event { wd:Q3 }" in query
    assert "?statement ?statementProperty ?event ; wikibase:rank ?rank" in query
    assert all(
        word not in query for word in ("wdt:", "LIMIT", "DeprecatedRank", "P279")
    )
    for subjects, targets in (
        ([], ["Q3"]),
        (["Q1"] * 251, ["Q3"]),
        (["Q1"], ["Q2"] * 8),
        (["Q1"], ["SYN_bad"]),
    ):
        with pytest.raises(ValueError):
            events.incoming_candidates_query(subjects, targets)


def test_native_link_check_covers_both_directions_and_frozen_raw_non_date_population(
    tmp_path, monkeypatch
):
    from GG_Data.mapping.build_relation_mapping_v2_1 import write_csv
    from GG_Data.pipeline.event_candidate_check import check_links

    mentions = tmp_path / "mentions.json.gz"
    import gzip

    with gzip.open(mentions, "wt", encoding="utf-8") as stream:
        json.dump(
            [
                dict(entity_id=qid, raw=dict(entity_group=kind))
                for qid, kind in (
                    ("Q2", "ORG"),
                    ("Q2", "ORG"),
                    ("Q3", "MISC"),
                    ("Q4", "DATE"),
                    ("SYN_a", "ORG"),
                )
            ],
            stream,
        )
    (tmp_path / "manifest.json").write_text(
        json.dumps(dict(outputs={mentions.name: events.digest(mentions)}))
    )
    relations = tmp_path / "relations"
    (relations / "mapping").mkdir(parents=True)
    mapping = relations / "mapping/RELATION_MAPPING_TABLE_v2.1.2.csv"
    write_csv(
        mapping,
        [
            dict(
                source="Wikidata",
                source_predicate="wd:P17",
                direction_to_level2="same",
                formal_component_conflict="False",
                level2_relation_id="wd:P17",
                relation_map_version="test",
            )
        ],
    )
    (relations / "manifest.json").write_text(
        json.dumps(dict(mapping_artifacts={str(mapping): events.digest(mapping)}))
    )
    output = tmp_path / "output"
    output.mkdir()
    (output / "Q1.json").write_text(
        json.dumps(
            dict(
                id="Q1",
                claims={
                    "P17": [
                        dict(
                            id="Q1$AA",
                            rank="normal",
                            mainsnak=dict(
                                property="P17",
                                datatype="wikibase-item",
                                datavalue=dict(
                                    value={"entity-type": "item", "id": "Q2"}
                                ),
                            ),
                        )
                    ]
                },
            )
        )
    )
    report = dict(records=[dict(qid="Q1", name="event")])
    calls = []

    def source(store, qids, saved_entities=None):
        calls.append(qids)
        assert qids == ["Q2", "Q3"]
        yield {
            qid: dict(
                id=qid,
                lastrevid=1,
                modified="2026-10-20T00:00:00Z",
                claims=(
                    {
                        "P17": [
                            dict(
                                id="Q3$BB",
                                rank="deprecated",
                                mainsnak=dict(
                                    property="P17",
                                    datatype="wikibase-item",
                                    datavalue=dict(
                                        value={"entity-type": "item", "id": "Q1"}
                                    ),
                                ),
                            )
                        ]
                    }
                    if qid == "Q3"
                    else {}
                ),
            )
            for qid in qids
        }, {"status": "OK"}

    monkeypatch.setattr(events, "current_records", source)
    check_links(report, output, tmp_path / "cache", mentions, relations, lambda: None)
    assert calls == [["Q2", "Q3"]]
    assert report["native_records_checked"] == 2
    assert report["daniel_distinct_qids"] == 2
    assert report["eligibility"][0]["distinct_daniel_count"] == 2
    assert report["eligibility"][0]["qualifying_statements"] == 2
    assert report["eligibility"][0]["passes_two_entity_gate"] is True
    assert report["status"] == "SEVEN_CANDIDATE_ELIGIBILITY_CHECK_ONLY"


def test_native_batches_reuse_saved_records_and_require_exact_full_population(
    tmp_path, monkeypatch
):
    calls = []

    def source(store, url, params):
        qids = params["ids"].split("|") if params else ["Q1"]
        calls.append((url, params, qids))
        return {
            "entities": {
                qid: dict(
                    id=qid,
                    type="item",
                    claims={},
                    lastrevid=1,
                    modified="2026-10-20T00:00:00Z",
                )
                for qid in qids
            }
        }, {"status": "OK"}

    events.cache_path(
        tmp_path, "https://www.wikidata.org/wiki/Special:EntityData/Q1.json", {}
    ).mkdir()
    monkeypatch.setattr(events, "cached_json", source)
    records = list(
        events.current_records(tmp_path, [f"Q{i}" for i in range(102, 0, -1)])
    )
    assert [len(r) for r, _ in records] == [1, 50, 50, 1]
    assert len({qid for r, _ in records for qid in r}) == 102
    assert all(
        p["redirects"] == "no" and "props" not in p and "languages" not in p
        for _, p, _ in calls[1:]
    )
    assert calls[1][2] == [f"Q{i}" for i in range(2, 52)]
    valid = records[0][0]["Q1"]
    for data in (
        {"entities": {}},
        {"entities": {"Q2": valid}},
        {"entities": {"Q1": dict(valid, missing="")}},
        {"entities": {"Q1": dict(valid, claims=None)}},
        {"entities": {"Q1": valid}, "redirects": []},
        {
            "entities": {"Q1": valid},
            "warnings": {"result": {"*": "unexpected warning"}},
        },
    ):
        with pytest.raises(SourceException):
            events.native_records(data, ["Q1"], {})


def test_only_explicit_oversized_batches_split_without_accepting_partial_records(
    tmp_path, monkeypatch
):
    calls = []
    truncation = {
        "result": {
            "*": "This result was truncated because it would otherwise be larger than the limit of 12,582,912 bytes."
        }
    }

    def source(store, url, params):
        qids = params["ids"].split("|")
        calls.append(qids)
        records = {
            qid: dict(
                id=qid,
                type="item",
                claims={},
                lastrevid=1,
                modified="2026-10-20T00:00:00Z",
            )
            for qid in qids
        }
        return (
            dict(entities={}, warnings=truncation)
            if len(qids) > 1
            else dict(entities=records)
        ), dict(cache="test_cache", sha256="test_sha")

    monkeypatch.setattr(events, "cached_json", source)
    result = list(events.current_records(tmp_path, ["Q3", "Q1", "Q2"]))
    assert calls == [["Q1", "Q2", "Q3"], ["Q1"], ["Q2", "Q3"], ["Q2"], ["Q3"]]
    assert [list(records) for records, _ in result] == [["Q1"], ["Q2"], ["Q3"]]
    assert [len(e["oversized_ancestors"]) for _, e in result] == [1, 2, 2]
    monkeypatch.setattr(
        events, "cached_json", lambda *a: (dict(entities={}, warnings=truncation), {})
    )
    with pytest.raises(
        SourceException, match="Single native record exceeds API size limit"
    ):
        list(events.current_records(tmp_path, ["Q1"]))
    monkeypatch.setattr(events, "cached_json", lambda *a: (dict(entities={}), {}))
    with pytest.raises(SourceException, match="Unexpected native record population"):
        list(events.current_records(tmp_path, ["Q1", "Q2"]))


def test_missing_current_fallback_keeps_native_id_revision_and_raw_missing_evidence(
    tmp_path, monkeypatch
):
    import gzip

    old = dict(
        id="Q1", type="item", claims={}, lastrevid=123, modified="2019-09-27T16:40:15Z"
    )
    path = tmp_path / "entities.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(
            [dict(entity_id="Q1", raw_reference=dict(full=dict(entity=old)))], stream
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(dict(outputs={path.name: events.digest(path)})))
    monkeypatch.setattr(events, "ACCEPTED_ENTITIES_SHA", events.digest(manifest))
    raw = {"entities": {"Q1": {"id": "Q1", "missing": ""}}}
    monkeypatch.setattr(
        events,
        "cached_json",
        lambda *a: (raw, {"cache": "current_missing", "sha256": "raw_sha"}),
    )
    records, source = next(events.current_records(tmp_path / "cache", ["Q1"], path))
    assert records == {"Q1": old}
    assert raw == {"entities": {"Q1": {"id": "Q1", "missing": ""}}}
    assert source["cache"] == "current_missing"
    assert source["saved_record_fallbacks"][0]["revision"] == 123
    assert source["saved_record_fallbacks"][0]["modified"] == old["modified"]
    assert source["saved_record_fallbacks"][0]["qid"] == "Q1"
    with pytest.raises(SourceException, match="Saved native fallback unavailable"):
        events.saved_native_records(path, {"Q2"})
    with pytest.raises(SourceException, match="Unexpected native record population"):
        raw["entities"] = {}
        list(events.current_records(tmp_path / "cache", ["Q1"], path))
    path.write_bytes(b"changed")
    with pytest.raises(
        SourceException, match="Saved native fallback checksum mismatch"
    ):
        events.saved_native_records(path, {"Q1"})
