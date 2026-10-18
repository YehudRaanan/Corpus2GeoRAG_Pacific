"""Reference fetching preserves graph IDs and records explicit missing IDs."""

import requests
from complete_graph_reference import fetch_batch, project_entity


def test_projected_reference_keeps_graph_id_revision_and_person_type() -> None:
    entity = {
        "id": "Q2",
        "lastrevid": 123,
        "labels": {"en": {"value": "Example"}},
        "aliases": {"en": [{"value": "Alias"}]},
        "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}]},
    }
    row = project_entity("Q1", entity)
    assert row["entity_id"] == "Q1"
    assert row["canonical_wikidata_id"] == "Q2"
    assert row["wikidata_revision"] == 123
    assert row["direct_types"] == ["Q5"]
    assert row["aliases"] == ["Alias"]
    assert project_entity("Q9", {"missing": True})["metadata_status"] == "MISSING"
    assert (
        project_entity("Q1", {"id": "Q1", "lastrevid": 1})["metadata_status"]
        == "NO_ENGLISH_NAME"
    )


def test_fetch_records_missing_ids_and_redirects_without_dropping_others(
    monkeypatch,
) -> None:
    payloads = [
        {"error": {"code": "no-such-entity", "id": "Q9"}},
        {
            "redirects": [{"from": "Q1", "to": "Q2"}],
            "entities": {
                "Q2": {
                    "id": "Q2",
                    "lastrevid": 1,
                    "labels": {"en": {"value": "Example"}},
                }
            },
        },
    ]
    requests_seen = []

    class Response:
        content = b"original response bytes"

        def raise_for_status(self):
            pass

        def json(self):
            return payloads.pop(0)

    def get(self, url, *, params, timeout):
        requests_seen.append(params["ids"])
        return Response()

    monkeypatch.setattr(requests.Session, "get", get)
    result = fetch_batch(["Q1", "Q9"])
    records = {r["entity_id"]: r for r in result["records"]}
    assert requests_seen == ["Q1|Q9", "Q1"]
    assert records["Q9"]["metadata_status"] == "MISSING"
    assert records["Q1"]["canonical_wikidata_id"] == "Q2"
    assert len(result["requests"]) == 2
    assert result["requests"][0]["error"]["id"] == "Q9"
