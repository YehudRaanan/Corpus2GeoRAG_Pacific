"""Explicit local full-record sources, with no hidden acquisition."""

import gzip
import json
from copy import deepcopy

import pytest

from GG_Data.pipeline import post_qid_native as api


def history(qid="Q1"):
    def revision(number, content):
        return dict(
            revid=number,
            timestamp=f"2026-01-0{number}T00:00:00Z",
            slots={
                "main": dict(
                    contentmodel="wikibase-item",
                    contentformat="application/json",
                    content=json.dumps(content),
                )
            },
        )

    full = dict(
        id=qid,
        type="item",
        claims={"P31": []},
        labels={},
        descriptions={},
        aliases={},
        sitelinks={},
    )
    return {
        "query": {
            "pages": [
                dict(
                    title=qid,
                    ns=0,
                    revisions=[
                        revision(3, dict(entity=qid, redirect="Q999")),
                        revision(2, {**full, "claims": {}}),
                        revision(1, full),
                    ],
                )
            ]
        }
    }


def test_historical_record_selects_full_original_and_derives_info():
    raw = history()
    before = deepcopy(raw)
    result = api.historical_record(raw, "Q1")
    assert result["entity"]["id"] == "Q1"
    assert result["entity"]["lastrevid"] == 1
    assert result["entity"]["modified"] == "2026-01-01T00:00:00Z"
    assert raw == before


def test_historical_record_skips_mediawiki_empty_array_merge_content():
    raw = history()
    cleared = dict(
        id="Q1",
        type="item",
        **{k: [] for k in ("claims", "labels", "descriptions", "aliases", "sitelinks")},
    )
    raw["query"]["pages"][0]["revisions"][1]["slots"]["main"]["content"] = json.dumps(
        cleared
    )
    assert api.historical_record(raw, "Q1")["entity"]["lastrevid"] == 1


@pytest.mark.parametrize(
    "damage",
    ["title", "duplicate", "order", "wrong_id", "missing_field", "redirect_only"],
)
def test_historical_record_rejects_malformed_evidence(damage):
    raw = history()
    page = raw["query"]["pages"][0]
    if damage == "title":
        page["title"] = "Q2"
    elif damage == "duplicate":
        page["revisions"][1]["revid"] = 3
    elif damage == "order":
        page["revisions"].reverse()
    elif damage == "redirect_only":
        page["revisions"] = page["revisions"][:1]
    else:
        slot = page["revisions"][-1]["slots"]["main"]
        content = json.loads(slot["content"])
        if damage == "wrong_id":
            content["id"] = "Q2"
        else:
            del content["labels"]
        slot["content"] = json.dumps(content)
    with pytest.raises(ValueError):
        api.historical_record(raw, "Q1")


def completion_fixture(tmp_path):
    api_dir, history_dir = tmp_path / "api", tmp_path / "history"
    api.acquire_api(
        {"Q1", "Q2"},
        api_dir,
        session=Session([Response({"entities": {"Q1": full_entity("Q1")}})]),
    )
    history_dir.mkdir()
    raw = history_dir / "Q2.response.body"
    raw.write_text(json.dumps(history("Q2")), encoding="utf-8")
    request = dict(
        endpoint="https://www.wikidata.org/w/api.php",
        params=dict(
            action="query",
            format="json",
            formatversion=2,
            prop="revisions",
            titles="Q2",
            rvslots="main",
            rvprop="ids|timestamp|content|contentmodel",
            rvlimit=5,
        ),
        retrieved_at="2026-10-29T00:00:00Z",
        status=200,
        sha256=api.digest(raw),
    )
    (history_dir / "Q2.request.json").write_text(json.dumps(request), encoding="utf-8")
    return api_dir, history_dir


def test_complete_api_history_preserves_current_and_failed_evidence(tmp_path):
    api_dir, history_dir = completion_fixture(tmp_path)
    original = (api_dir / "receipt.json").read_bytes()
    before = json.load(
        gzip.open(api_dir / "full_records.json.gz", "rt", encoding="utf-8")
    )
    out = tmp_path / "completed"
    result = api.complete_api_history(api_dir, history_dir, out)
    records = json.load(gzip.open(out / "full_records.json.gz", "rt", encoding="utf-8"))
    assert records["Q1"] == before["Q1"]
    assert records["Q2"] == api.historical_record(history("Q2"), "Q2")
    assert result["counts"] == dict(required=2, acquired=2, missing=0)
    assert result["missing"] == result["failures"] == []
    assert result["resolved_failures"][0]["original_failure"]["qid"] == "Q2"
    assert (api_dir / "receipt.json").read_bytes() == original
    source = json.loads((out / "sources.json").read_text())["Q2"]
    assert source["provider"] == "WIKIDATA_API_HISTORICAL"
    assert [v["reason"] for v in source["skipped_newer_revisions"]] == [
        "REDIRECT",
        "EMPTY_CLAIMS",
    ]
    assert result["inputs"][source["request_file"]] == source["request_sha256"]


@pytest.mark.parametrize(
    "damage", ["history_raw", "history_request", "current_raw", "output"]
)
def test_complete_api_history_rejects_changed_evidence_before_output(tmp_path, damage):
    api_dir, history_dir = completion_fixture(tmp_path)
    if damage == "history_raw":
        (history_dir / "Q2.response.body").write_text("{}")
    elif damage == "history_request":
        path = history_dir / "Q2.request.json"
        request = json.loads(path.read_text())
        request["params"]["titles"] = "Q3"
        path.write_text(json.dumps(request))
    elif damage == "current_raw":
        next(api_dir.glob("*.response.body")).write_text("{}")
    else:
        (api_dir / "sources.json").write_text("{}")
    with pytest.raises(ValueError):
        api.complete_api_history(api_dir, history_dir, tmp_path / "completed")
    assert not (tmp_path / "completed").exists()


def envelope(qid):
    return {"requested_qid": qid, "entity": {"id": qid, "claims": {}, "lastrevid": 7}}


def save(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(content, stream)
    return path


@pytest.mark.parametrize("as_list", [False, True])
def test_full_export_reuses_only_required_records_and_reports_missing(
    tmp_path, as_list
):
    content = (
        [envelope("Q1"), envelope("Q2")]
        if as_list
        else {"Q1": envelope("Q1"), "Q2": envelope("Q2")}
    )
    path = save(tmp_path / "full_records.json.gz", content)
    result = api.reuse_native({"Q1", "Q3"}, [path])
    assert set(result["records"]) == {"Q1"}
    assert result["missing"] == ["Q3"]
    assert result["status"] == "MISSING_NATIVE_RECORDS"
    assert result["sources"]["Q1"]["sha256"]
    assert result["sources"]["Q1"]["snapshot_at"] is None
    assert result["event_discovery_completeness"] == "NOT_ESTABLISHED"


def test_bq_full_item_wrapper_has_source_time_and_validates_sql(tmp_path):
    path = save(
        tmp_path / "wikidata_full_cache" / "abc.json.gz",
        {
            "retrieved_at": "2026-10-20T00:00:00Z",
            "rows": [
                {"id": "Q1", "item": json.dumps(envelope("Q1")["entity"]) + ",\n"}
            ],
        },
    )
    path.with_suffix("").with_suffix(".sql").write_text(
        "SELECT id, item FROM `x.y.z` WHERE numeric_id IN (1) AND STARTS_WITH(id,'Q')"
    )
    (path.parent / "table_snapshot.json").write_text(
        json.dumps({"snapshot_at": "2026-10-18T00:00:00Z"})
    )
    result = api.reuse_native({"Q1"}, [path])
    assert result["records"]["Q1"] == envelope("Q1")
    assert result["sources"]["Q1"]["snapshot_at"] == "2026-10-18T00:00:00Z"
    assert result["sources"]["Q1"]["retrieved_at"] == "2026-10-20T00:00:00Z"
    path.with_suffix("").with_suffix(".sql").write_text(
        "SELECT id, instance_of FROM `x.y.z`"
    )
    with pytest.raises(ValueError, match="full-item"):
        api.reuse_native({"Q1"}, [path])


def test_filtered_event_source_and_corrupt_envelope_fail(tmp_path):
    for folder in ("filtered", "event_selection", "partial"):
        path = save(tmp_path / folder / "full_records.json.gz", {"Q1": envelope("Q1")})
        with pytest.raises(ValueError, match="filtered"):
            api.reuse_native({"Q1"}, [path])
    bad = envelope("Q1")
    bad["entity"]["id"] = "Q2"
    path = save(tmp_path / "complete" / "full_records.json.gz", {"Q1": bad})
    with pytest.raises(ValueError, match="ID differs"):
        api.reuse_native({"Q1"}, [path])


def test_cli_writes_missing_receipt_and_never_overwrites(tmp_path):
    path = save(tmp_path / "full_records.json.gz", {"Q1": envelope("Q1")})
    ids = tmp_path / "ids.json"
    ids.write_text('["Q1", "Q3"]')
    out = tmp_path / "delivery"
    api.main(["--required-ids", str(ids), "--cache", str(path), "--output", str(out)])
    receipt = json.loads((out / "receipt.json").read_text())
    assert receipt["missing"] == ["Q3"]
    assert receipt["counts"] == {"required": 2, "reused": 1, "missing": 1}
    with pytest.raises(FileExistsError):
        api.main(
            ["--required-ids", str(ids), "--cache", str(path), "--output", str(out)]
        )


def test_explicit_priority_selects_whole_record_and_duplicate_in_file_fails(tmp_path):
    first = envelope("Q1")
    second = envelope("Q1")
    second["entity"]["lastrevid"] = 99
    second["entity"]["claims"] = {"P31": []}
    a = save(tmp_path / "first" / "full_records.json.gz", {"Q1": first})
    b = save(tmp_path / "second" / "full_records.json.gz", {"Q1": second})
    result = api.reuse_native({"Q1"}, [a, b])
    assert result["records"]["Q1"] == first
    assert result["caches"][1]["required_available"] == 1
    assert result["caches"][1]["selected_records"] == 0
    duplicate = save(tmp_path / "duplicate" / "full_records.json.gz", [first, first])
    with pytest.raises(ValueError, match="Duplicate full record"):
        api.reuse_native({"Q1"}, [duplicate])


class Response:
    def __init__(self, data, status=200, headers=None):
        self.content = json.dumps(data, ensure_ascii=False).encode("utf8")
        self.status_code = status
        self.headers = headers or {}


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def full_entity(qid):
    return dict(
        id=qid,
        claims={},
        labels={
            "en": {"value": "Name"},
            "ja": {"value": "名前"},
            "fr": {"value": "Nom"},
        },
        descriptions={},
        aliases={},
        sitelinks={},
        lastrevid=42,
        modified="2026-10-29T00:00:00Z",
    )


def test_api_saves_full_languages_exact_raw_bytes_and_current_record_evidence(tmp_path):
    import hashlib

    response = Response(
        {"entities": {"Q1": full_entity("Q1"), "Q2": full_entity("Q2")}}
    )
    client = Session([response])
    result = api.acquire_api({"Q2", "Q1"}, tmp_path / "api", session=client)
    assert (
        result["status"] == "REQUIRED_NATIVE_RECORDS_AVAILABLE"
        and result["failures"] == []
    )
    records = json.load(
        gzip.open(tmp_path / "api/full_records.json.gz", "rt", encoding="utf8")
    )
    assert records["Q1"]["entity"] == full_entity("Q1")
    assert "fr" in records["Q1"]["entity"]["labels"]
    params = client.calls[0][1]["params"]
    assert params["props"] == "info|labels|descriptions|aliases|sitelinks|claims"
    assert "languages" not in params and client.calls[0][1]["timeout"] == 30
    source = json.loads((tmp_path / "api/sources.json").read_text())["Q1"]
    assert (
        source["snapshot_at"] is None
        and source["temporal_basis"] == "CURRENT_WIKIDATA_API_NOT_PINNED_DUMP"
    )
    assert source["native_revision"] == 42
    raw = __import__("pathlib").Path(source["file"])
    assert (
        raw.read_bytes() == response.content
        and source["sha256"] == hashlib.sha256(response.content).hexdigest()
    )
    assert result["attempts"][0]["retrieval_utc"]
    with pytest.raises(FileExistsError):
        api.acquire_api({"Q1"}, tmp_path / "api", session=client)


def test_api_retries_only_transient_http_with_three_attempt_limit(
    tmp_path, monkeypatch
):
    waits = []
    monkeypatch.setattr("time.sleep", waits.append)
    client = Session(
        [
            Response({}, 429, {"Retry-After": "999"}),
            Response({}, 503),
            Response({}, 503),
        ]
    )
    result = api.acquire_api({"Q1"}, tmp_path / "api", session=client)
    assert len(client.calls) == 3 and waits == [30, 2]
    assert result["status"] == "MISSING_NATIVE_RECORDS" and result["missing"] == ["Q1"]
    assert len(result["failures"]) == 1 and len(result["attempts"]) == 3
    assert all(
        __import__("pathlib").Path(a["raw_file"]).is_file() for a in result["attempts"]
    )


def test_api_partial_success_keeps_valid_records_but_never_calls_it_complete(tmp_path):
    client = Session(
        [
            Response(
                {
                    "entities": {
                        "Q1": full_entity("Q1"),
                        "Q2": {"id": "Q2", "missing": True},
                    }
                }
            ),
            Response({"error": {"code": "denied"}}, 403),
        ]
    )
    result = api.acquire_api(
        {"Q1", "Q2", "Q3"}, tmp_path / "api", batch_size=2, session=client
    )
    assert result["missing"] == ["Q2", "Q3"] and len(result["failures"]) == 2
    assert len(client.calls) == 2 and result["counts"] == {
        "required": 3,
        "acquired": 1,
        "missing": 2,
    }
    assert result["status"] == "MISSING_NATIVE_RECORDS"


@pytest.mark.parametrize(
    "bad",
    [
        {"claims": {}},
        {"id": "Q1", "claims": {}},
        {"id": "Q2", "claims": {}, "lastrevid": 1, "modified": "x"},
    ],
)
def test_api_rejects_incomplete_or_redirected_native_info(tmp_path, bad):
    result = api.acquire_api(
        {"Q1"}, tmp_path / "api", session=Session([Response({"entities": {"Q1": bad}})])
    )
    assert result["missing"] == ["Q1"] and len(result["failures"]) == 1


def test_api_request_failure_preserves_receipt_and_continues_other_batches(tmp_path):
    client = Session(
        [TimeoutError("timeout"), Response({"entities": {"Q2": full_entity("Q2")}})]
    )
    result = api.acquire_api(
        {"Q1", "Q2"}, tmp_path / "api", batch_size=1, session=client
    )
    assert result["missing"] == ["Q1"] and len(client.calls) == 2
    assert result["attempts"][0]["error_type"] == "TimeoutError"


def test_api_transient_retry_can_succeed_without_duplicate_native_records(
    tmp_path, monkeypatch
):
    waits = []
    monkeypatch.setattr("time.sleep", waits.append)
    client = Session(
        [
            Response({}, 503, {"Retry-After": "0"}),
            Response({"entities": {"Q1": full_entity("Q1")}}),
        ]
    )
    result = api.acquire_api({"Q1"}, tmp_path / "api", session=client)
    assert waits == [0] and result["counts"] == {
        "required": 1,
        "acquired": 1,
        "missing": 0,
    }
    assert result["failures"] == [] and len(result["attempts"]) == 2


@pytest.mark.parametrize("ids,size", [({"Q0"}, 50), ({"Q1"}, 51), ({"Q1"}, 0)])
def test_api_invalid_request_stops_before_output(tmp_path, ids, size):
    client = Session([])
    with pytest.raises(ValueError):
        api.acquire_api(ids, tmp_path / "api", batch_size=size, session=client)
    assert not (tmp_path / "api").exists() and not client.calls
