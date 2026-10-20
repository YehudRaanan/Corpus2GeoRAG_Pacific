"""Full-population discovery must preserve both directions and stop on failure."""

import json

import pytest

from GG_Data.pipeline import event_discovery, events
from GG_Data.pipeline.poc import digest
from GG_Data.pipeline.relations import SourceException


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
