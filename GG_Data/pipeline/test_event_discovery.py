"""Full-population discovery must preserve both directions and stop on failure."""

import json

import pytest

from GG_Data.pipeline import event_discovery, events
from GG_Data.pipeline.poc import digest
from GG_Data.pipeline.relations import SourceException


def test_paged_incoming_keeps_all_pages_reuses_cache_and_rejects_overlap(
    tmp_path, monkeypatch
):
    qid, url = "Q1", events.QUERY_URL
    ids = [f"http://www.wikidata.org/entity/statement/Q2-{i:032x}" for i in range(3)]
    calls = []

    def cached(store, source, params):
        calls.append(params["query"])
        index = 0 if len(calls) == 1 else 2
        return {"ids": ids[index : index + 2]}, dict(cache="test", status="OK")

    monkeypatch.setattr(events, "cached_json", cached)
    monkeypatch.setattr(
        event_discovery,
        "incoming_links",
        lambda data, _: [dict(source_record_id=sid) for sid in data["ids"]],
    )
    pages = list(event_discovery.incoming_pages(tmp_path, url, qid, 2))
    assert [len(rows) for rows, _, _ in pages] == [2, 1]
    assert [complete for _, _, complete in pages] == [False, True]
    assert ids[1] in calls[1] and "LIMIT 2" in calls[1]
    # A complete older unpaged response is reused rather than requested anew.
    receipt = (
        events.cache_path(
            tmp_path, url, {"query": events.incoming_query(qid), "format": "json"}
        )
        / "request.json"
    )
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps(dict(status="OK")))
    calls.clear()
    pages = list(event_discovery.incoming_pages(tmp_path, url, qid, 2))
    assert len(pages) == 1 and calls == [events.incoming_query(qid)]
    assert pages[0][1]["reused_unpaged"] is True
    # A failed old response remains intact; it is not treated as complete data.
    receipt.write_text(json.dumps(dict(status="FAILED")))
    monkeypatch.setattr(
        events, "cached_json", lambda *args: ({"ids": [ids[1], ids[0]]}, {})
    )
    with pytest.raises(SourceException, match="Invalid incoming page"):
        list(event_discovery.incoming_pages(tmp_path, url, qid, 2))
    assert json.loads(receipt.read_text())["status"] == "FAILED"
    monkeypatch.setattr(events, "cached_json", lambda *args: ({"ids": ids[:2]}, {}))
    with pytest.raises(SourceException, match="Invalid incoming page"):
        list(event_discovery.incoming_pages(tmp_path, url, qid, 2))


def test_page_query_validates_cursor_and_size_without_changing_source_scope():
    query = events.incoming_page_query("Q16")
    assert "LIMIT 5000" in query and "ORDER BY STR(?statement)" in query
    assert "wikibase:rank ?rank" in query and "P279" not in query
    for size in (0, 5001, True):
        with pytest.raises(ValueError):
            events.incoming_page_query("Q16", size=size)
    with pytest.raises(ValueError):
        events.incoming_page_query("Q16", 'x") } UNION { ?s ?p ?o')


def test_property_partition_binds_native_predicates_and_preserves_ranks(
    tmp_path, monkeypatch
):
    query = events.incoming_page_query("Q16", property_id="P17")
    assert "?statement ps:P17 wd:Q16" in query
    assert "?subject p:P17 ?statement" in query
    assert "BIND(wd:P17 AS ?property)" in query
    assert "wikibase:rank ?rank" in query and "DeprecatedRank" not in query
    assert "ORDER BY STR(?statement)" in query and "LIMIT 5000" in query
    with pytest.raises(ValueError):
        events.incoming_page_query("Q16", property_id="P17 } UNION {")
    monkeypatch.setattr(events, "cached_json", lambda *args: ({}, {}))
    monkeypatch.setattr(
        event_discovery,
        "incoming_links",
        lambda *args: [
            dict(
                source_record_id="http://www.wikidata.org/entity/statement/Q1-01234567",
                source_predicate="wd:P31",
            )
        ],
    )
    with pytest.raises(SourceException, match="Invalid incoming page"):
        list(
            event_discovery.incoming_pages(
                tmp_path, events.QUERY_URL, "Q16", 5000, property_id="P17"
            )
        )


@pytest.mark.parametrize("fail_incoming", [False, True])
def test_inventory_reuses_native_records_covers_both_graphs_and_stops(
    tmp_path, monkeypatch, fail_incoming
):
    source = tmp_path / "prior"
    source.mkdir()
    mentions = tmp_path / "mentions.json"
    mentions.write_text(
        json.dumps(
            [
                dict(
                    entity_id="Q1", raw=dict(entity_group="MISC"), resolved_type="DATE"
                ),
                dict(entity_id="Q1", raw=dict(entity_group="ORG")),
                dict(entity_id="Q2", raw=dict(entity_group="DATE")),
                dict(entity_id="SYN_1", raw=dict(entity_group="LOC")),
            ]
        )
    )
    upstream = {str(mentions): digest(mentions)}
    (source / "verification.json").write_text(
        json.dumps(
            dict(
                status="VERIFIED_SEVEN_CANDIDATE_ELIGIBILITY_ONLY",
                outputs={},
                upstream_output_hashes=upstream,
                daniel_population=1,
            )
        )
    )
    native = dict(id="Q1", lastrevid=7, modified="2019-09-27T16:40:15Z")
    requests = []

    def records(store, qids, saved_entities):
        assert qids == ["Q1"]
        yield {"Q1": native}, dict(saved_record_fallbacks=[dict(qid="Q1")])

    def incoming(store, url, params):
        requests.append(url)
        assert params["query"] == events.incoming_query("Q1")
        if fail_incoming:
            raise SourceException("Unexpected source data")
        return {
            "results": {
                "bindings": [
                    {
                        "subject": {"value": "http://www.wikidata.org/entity/Q4"},
                        "property": {"value": "http://www.wikidata.org/entity/P17"},
                        "statement": {
                            "value": "http://www.wikidata.org/entity/statement/Q4-00000000-0000-0000-0000-000000000000"
                        },
                        "rank": {"value": "http://wikiba.se/ontology#DeprecatedRank"},
                    }
                ]
            }
        }, dict(cache="test")

    monkeypatch.setattr(events, "current_records", records)
    monkeypatch.setattr(
        events, "item_links", lambda _: [dict(object_qid="Q3", raw_statement={})]
    )
    monkeypatch.setattr(events, "cached_json", incoming)
    output = tmp_path / "output"
    report = event_discovery.run(source, mentions, tmp_path / "saved", output, tmp_path)
    assert report["native_records_checked"] == 1
    assert report["native_sources"][0]["records"][0]["revision"] == 7
    assert report["event_rows_written"] == 0
    assert report["event_population_complete"] is False
    assert report["full_10k_event_discovery_complete"] is False
    assert not (output / "events.json").exists()
    assert json.loads((output / "candidate_qids.json").read_text()) == (
        ["Q3"] if fail_incoming else ["Q3", "Q4"]
    )
    if fail_incoming:
        assert requests == [events.QUERY_URL]
        assert report["status"] == "BLOCKED_EVENT_DISCOVERY"
        assert report["incoming_requests_complete"] == 0
    else:
        assert requests == [events.QUERY_URL, events.SCHOLARLY_QUERY_URL]
        assert report["status"] == "DIRECT_CANDIDATE_ACQUISITION_ONLY"
        assert report["incoming_requests_complete"] == 2
        assert report["incoming_statements"] == 2
    # Changed accepted evidence stops before another request or output creation.
    mentions.write_text("[]")
    with pytest.raises(SourceException, match="Accepted upstream output changed"):
        event_discovery.run(
            source, mentions, tmp_path / "saved", tmp_path / "other", tmp_path
        )
