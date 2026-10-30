"""Protect exact identities, full input lineage and directional page counts."""

import json
import time

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.pipeline import simplified_agent as subject
from GG_Data.pipeline.poc import digest, read_json


def test_rate_limited_reads_wait_for_explicit_resume_and_preserve_receipt(
    tmp_path, monkeypatch
):
    import requests

    from GG_Data.pipeline.simplified_page_events import PageEvidenceClient

    client = PageEvidenceClient(
        tmp_path / "requests",
        True,
        10,
        time.monotonic() + 60,
        retry_rate_limited=True,
        min_interval=1.0,
    )
    replies = []

    def get(*args, **kwargs):
        response = requests.Response()
        response.status_code = 429 if not replies else 200
        response._content = b'{"query":{}}'
        response.headers["Retry-After"] = "600"
        replies.append(response)
        return response

    monkeypatch.setattr(client.session, "get", get)
    with pytest.raises(RuntimeError, match="COOLDOWN"):
        client.query("https://example.test", {"action": "query"})
    assert len(replies) == 1
    receipts = list((tmp_path / "requests").glob("*.json.gz"))
    assert len(receipts) == 1 and read_json(receipts[0])["http_status"] == 429


def input_file(tmp_path):
    keys = [
        ("A", "PER", "Q1"),
        ("A", "PER", "Q1"),
        ("A", "ORG", "Q1"),
        ("a", "PER", "Q2"),
        (" A", "PER", "Unresolved page"),
        ("1941", "DATE", "Q1"),
    ]
    rows = [
        dict(
            word=name,
            entity_group=kind,
            Source=page,
            score=0.8,
            start=0,
            end=len(name),
            Index=i,
            Text=name,
            subtype=kind,
        )
        for i, (name, kind, page) in enumerate(keys)
    ]
    path = tmp_path / "input.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path, rows


def test_prepare_keeps_exact_keys_and_every_raw_row(tmp_path):
    source, raw = input_file(tmp_path)
    out = tmp_path / "prepared"
    result = subject.prepare(source, out, expected_sha256=digest(source))
    entities = read_json(out / "entities.json.gz")
    mentions = read_json(out / "mentions.json.gz")
    assert {(r["name"], r["type"]) for r in entities} == {
        ("A", "PER"),
        ("A", "ORG"),
        ("a", "PER"),
        (" A", "PER"),
    }
    assert [r["raw"] for r in mentions] == raw
    assert [r["source_row_index"] for r in mentions] == list(range(6))
    assert mentions[-1]["entity_id"] is None
    assert mentions[-1]["exclusion_reason"] == "DATE_EXCLUDED"
    assert mentions[0]["entity_id"] == mentions[1]["entity_id"]
    assert mentions[0]["entity_id"] != mentions[2]["entity_id"]
    a = next(r for r in entities if (r["name"], r["type"]) == ("A", "PER"))
    assert a["mention_count"] == 2 and a["page_count"] == 1
    assert not any("qid" in r for r in entities)
    pages = read_json(out / "wiki_pages.json.gz")
    assert {r["source_key"] for r in pages} == {"Q1", "Q2", "Unresolved page"}
    assert all(r["wiki_page_id"] is None and r["revision_id"] is None for r in pages)
    assert result["counts"] == dict(
        raw_rows=6, excluded_date_rows=1, entities=4, pages=3, memberships=4
    )
    for name, sha in result["outputs"].items():
        assert digest(out / name) == sha
    assert json.loads((out / "manifest.json").read_text())["input"]["sha256"] == digest(
        source
    )


def test_independent_raw_replay_checks_all_fields_and_date_exclusion(tmp_path):
    from GG_Data.pipeline.simplified_verify import verify_raw_rows

    source, _ = input_file(tmp_path)
    out = tmp_path / "prepared"
    subject.prepare(source, out, expected_sha256=digest(source))
    result = verify_raw_rows(out)
    assert result["raw_rows_verified"] == 6 and result["date_rows_verified"] == 1
    assert result["exact_entities_verified"] == 4


def test_prepare_rejects_wrong_hash_before_writing(tmp_path):
    source, _ = input_file(tmp_path)
    out = tmp_path / "prepared"
    with pytest.raises(ValueError, match="SHA256"):
        subject.prepare(source, out, expected_sha256="wrong")
    assert not out.exists()


def test_prepare_preserves_existing_output(tmp_path):
    source, _ = input_file(tmp_path)
    out = tmp_path / "prepared"
    out.mkdir()
    marker = out / "marker"
    marker.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        subject.prepare(source, out, expected_sha256=digest(source))
    assert marker.read_bytes() == b"keep"


def test_prepare_rejects_missing_identity(tmp_path):
    source, _ = input_file(tmp_path)
    table = pq.read_table(source).to_pylist()
    table[0]["word"] = None
    pq.write_table(pa.Table.from_pylist(table), source)
    with pytest.raises(ValueError, match="identity"):
        subject.prepare(source, tmp_path / "prepared", expected_sha256=digest(source))


def test_page_events_use_only_page_support_and_merge_exact_event_names(tmp_path):
    from GG_Data.pipeline import simplified_page_events as events

    source, _ = input_file(tmp_path)
    prepared = tmp_path / "prepared"
    subject.prepare(source, prepared, expected_sha256=digest(source))
    pages = [
        dict(
            page_index=0,
            source_subject_qid="Q90",
            title="Own event",
            revision_id=10,
            status="AVAILABLE",
            evidence="source-1",
            links=["Event A", "Unknown", "Person"],
        ),
        dict(
            page_index=1,
            source_subject_qid="Q91",
            title="Other",
            revision_id=20,
            status="AVAILABLE",
            evidence="source-2",
            links=["Event B", "Event A"],
        ),
        dict(
            page_index=2,
            source_subject_qid=None,
            title="Unresolved page",
            revision_id=30,
            status="AVAILABLE",
            evidence="source-3",
            links=[],
        ),
    ]
    mapping = {"Event A": "Q92", "Event B": "Q93", "Unknown": "Q94", "Person": "Q95"}
    records = {
        q: dict(id=q, label=name, direct_types=types)
        for q, name, types in [
            ("Q90", "Own event", ["Q1190554"]),
            ("Q91", "Other", ["Q5"]),
            ("Q92", "Same event", ["Q1190554"]),
            ("Q93", "Same event", ["Q1190554"]),
            ("Q95", "Person", ["Q5"]),
            ("Q96", "Unlinked event", ["Q1190554"]),
        ]
    }
    result = events.event_population(pages, mapping, records, {"Q1190554"})
    assert {(r["name"], r["type"]) for r in result["entities"]} == {
        ("Own event", "event"),
        ("Same event", "event"),
    }
    same = next(r for r in result["entities"] if r["name"] == "Same event")
    assert same["page_count"] == 2 and same["native_ids"] == ["Q92", "Q93"]
    assert len(result["memberships"]) == 3
    assert not any(r["name"] == "Unlinked event" for r in result["entities"])
    unknown = next(r for r in result["recognition_audit"] if r["qid"] == "Q94")
    assert unknown["status"] == "UNKNOWN_METADATA_MISSING"
    assert all(r["page_index"] in {0, 1} for r in result["memberships"])


def test_page_event_scope_rejects_duplicate_pages_or_missing_revisions():
    from GG_Data.pipeline import simplified_page_events as events

    row = dict(
        page_index=0,
        source_subject_qid="Q1",
        title="A",
        revision_id=1,
        status="AVAILABLE",
        evidence="file",
        links=[],
    )
    with pytest.raises(ValueError, match="Duplicate"):
        events.event_population([row, row], {}, {}, {"Q1190554"})
    with pytest.raises(ValueError, match="revision"):
        events.event_population([dict(row, revision_id=None)], {}, {}, {"Q1190554"})


def test_assemble_publishes_portable_tables_with_pinned_event_rule(tmp_path):
    from GG_Data.pipeline import simplified_page_events as events

    source, _ = input_file(tmp_path)
    prepared = tmp_path / "prepared"
    subject.prepare(source, prepared, expected_sha256=digest(source))
    folders = {name: tmp_path / name for name in ["pages", "links", "hierarchy"]}
    for folder in folders.values():
        folder.mkdir()
    pages = [
        dict(
            p,
            title=f"Page {i}",
            wiki_page_id=10 + i,
            revision_id=100 + i,
            status="AVAILABLE",
            evidence="receipt",
            links=["Event"],
        )
        for i, p in enumerate(read_json(prepared / "wiki_pages.json.gz"))
    ]
    subject.write_array(folders["pages"] / "page_sources.json.gz", pages)
    subject.write_array(
        folders["links"] / "title_mapping.json.gz",
        [dict(target_title="Event", qid="Q99")],
    )
    subject.write_object(
        folders["links"] / "native_metadata.json",
        {"Q99": dict(id="Q99", label="Event", direct_types=["Q1190554"])},
    )
    for name in ["pages", "links"]:
        folder = folders[name]
        subject.write_object(
            folder / "manifest.json",
            dict(
                outputs={p.name: digest(p) for p in folder.iterdir()},
                source_pages_sha256=digest(folders["pages"] / "page_sources.json.gz"),
            ),
        )
    params = folders["hierarchy"] / "parameters"
    params.mkdir()
    (params / "event_types.csv").write_text("subtype_qid\nQ1190554\n", encoding="utf-8")
    subject.write_object(
        folders["hierarchy"] / "recognition_approval.json",
        dict(
            status="RECOGNITION_RULE_ACCEPTED",
            root_qid="Q1190554",
            parameter_hashes={"event_types.csv": digest(params / "event_types.csv")},
        ),
    )
    out = tmp_path / "model"
    result = events.assemble(
        prepared, folders["pages"], folders["links"], folders["hierarchy"], out
    )
    assert result["counts"]["entities"] == 5 and result["counts"]["events"] == 1
    assert result["counts"]["memberships"] == 7
    assert digest(out / "mentions.json.gz") == digest(prepared / "mentions.json.gz")
    assert (
        read_json(out / "event_events.json.gz")[0]["native_records"][0]["qid"] == "Q99"
    )
    assert (out / "geography.json.gz").is_file()


def test_merge_population_counts_distinct_physical_pages_and_keeps_source_keys():
    from GG_Data.pipeline.simplified_page_events import merge_population

    a, b, e = (
        subject.entity_id(n, t) for n, t in [("A", "PER"), ("B", "ORG"), ("E", "event")]
    )
    entities = [
        dict(
            entity_id=a,
            name="A",
            type="PER",
            node_index=0,
            page_count=2,
            mention_count=3,
        ),
        dict(
            entity_id=b,
            name="B",
            type="ORG",
            node_index=1,
            page_count=1,
            mention_count=1,
        ),
    ]
    memberships = [dict(entity_id=a, node_index=0, page_index=p) for p in [0, 1]] + [
        dict(entity_id=b, node_index=1, page_index=2)
    ]
    pages = [
        dict(page_index=i, wiki_page_id=wid, source_key=f"Q{i+1}")
        for i, wid in enumerate([10, 10, 20])
    ]
    extra = dict(
        entities=[
            dict(entity_id=e, name="E", type="event", page_count=2, mention_count=0)
        ],
        memberships=[dict(entity_id=e, page_index=p) for p in [0, 1]],
    )
    result = merge_population(entities, memberships, pages, extra)
    assert len(result["entities"]) == 3
    assert len(result["memberships"]) == 3
    assert {r["page_index"] for r in result["memberships"]} == {0, 2}
    assert all(r["page_count"] == 1 for r in result["entities"])
    assert (
        next(r for r in result["entities"] if r["entity_id"] == a)["mention_count"] == 3
    )
    assert [r["canonical_page_index"] for r in result["wiki_pages"]] == [0, 0, 2]
    assert {r["source_key"] for r in result["wiki_pages"]} == {"Q1", "Q2", "Q3"}


def test_build_graph_exports_every_pair_and_both_strengths(tmp_path):
    from Agent.geo_agent.compact_format import records
    from GG_Data.pipeline.simplified_relations import build_graph

    model = tmp_path / "model"
    model.mkdir()
    pages_by_node = [[0, 1, 2, 3], [0, 1, 4, 5, 6], [0], [0, 6]]
    entities = [
        dict(
            entity_id=subject.entity_id(name, kind),
            name=name,
            type=kind,
            node_index=i,
            page_count=len(pages_by_node[i]),
            mention_count=0,
        )
        for i, (name, kind) in enumerate(
            [("A", "PER"), ("B", "ORG"), ("E", "event"), ("F", "event")]
        )
    ]
    subject.write_array(model / "entities.json.gz", entities)
    memberships = [
        dict(node_index=i, page_index=p)
        for i, ps in enumerate(pages_by_node)
        for p in ps
    ]
    pq.write_table(pa.Table.from_pylist(memberships), model / "memberships.parquet")
    subject.write_array(
        model / "wiki_pages.json.gz",
        [
            dict(
                page_index=p,
                canonical_page_index=p,
                source_key=f"Q{p+1}",
                title=f"Page {p}",
                wiki_page_id=p + 1,
                revision_id=p + 100,
            )
            for p in range(7)
        ],
    )
    subject.write_array(model / "event_events.json.gz", [])
    subject.write_object(
        model / "manifest.json",
        dict(
            page_scope_id="fixture",
            geography_status="PENDING_LAST_STAGE",
            input=None,
            outputs={p.name: digest(p) for p in model.iterdir()},
        ),
    )
    result = build_graph(model, tmp_path / "graph")
    output = list(records(tmp_path / "graph" / "agent_graph.json.gz"))
    pairs = [r for kind, r in output if kind == "pair"]
    assert len(pairs) == result["pair_count"] == 6
    ab = next(r for r in pairs if r[:2] == [0, 1])
    assert ab == [0, 1, 2, 0.5, 0.4]
    assert sum(r[2] for r in pairs) == 8  # Six on page 0; one each on pages 1 and 6.
    assert all(r[0] < r[1] for r in pairs)
    assert len(read_json(tmp_path / "graph" / "relations.json.gz")) == 6


def test_page_collection_binds_raw_source_and_never_reads_entity_neighbours(tmp_path):
    from GG_Data.pipeline import simplified_page_events as events

    source, _ = input_file(tmp_path)
    prepared = tmp_path / "prepared"
    subject.prepare(source, prepared, expected_sha256=digest(source))
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                q: dict(id=q, sitelinks={"enwiki": {"title": title}})
                for q, title in [("Q1", "Page A"), ("Q2", "Page B")]
            }
        )
    )

    class Client:
        def query(self, endpoint, params):
            assert params["action"] == "query"
            titles = params["titles"].split("|")
            pages = [
                dict(
                    pageid=i + 10,
                    ns=0,
                    title=title,
                    pageprops={
                        "wikibase_item": {"Page A": "Q1", "Page B": "Q2"}.get(title)
                    },
                    revisions=[
                        dict(
                            revid=i + 100,
                            timestamp="2026-10-30T00:00:00Z",
                            slots={
                                "main": {
                                    "content": "[[Event A]] [[File:X]] <!-- [[Hidden]] -->"
                                }
                            },
                        )
                    ],
                )
                for i, title in enumerate(titles)
            ]
            return (
                {"batchcomplete": True, "query": {"pages": pages}},
                "api-evidence",
                "now",
            )

    out = tmp_path / "pages"
    result = events.collect_pages(prepared, out, metadata, Client())
    pages = read_json(out / "page_sources.json.gz")
    assert len(pages) == 3 and result["available_pages"] == 3
    assert all(p["links"] == ["Event A"] for p in pages)
    assert all(p["revision_id"] is not None for p in pages)
    assert all(
        p["revision_basis"] == "RETRIEVED_REVISION_NOT_DANIEL_EXACT_REVISION"
        for p in pages
    )
    assert all(
        digest(__import__("pathlib").Path(p["raw_path"])) == p["raw_sha256"]
        for p in pages
    )
    assert all(p["status"] == "AVAILABLE" for p in pages)


def test_link_metadata_uses_exact_sitelinks_and_retains_unresolved_titles(tmp_path):
    from GG_Data.pipeline import simplified_page_events as events

    pages = tmp_path / "pages"
    pages.mkdir()
    subject.write_array(
        pages / "page_sources.json.gz",
        [dict(page_index=0, source_subject_qid="Q1", links=["Known", "Unknown"])],
    )
    subject.write_object(
        pages / "manifest.json",
        dict(outputs={"page_sources.json.gz": digest(pages / "page_sources.json.gz")}),
    )
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "Q1": dict(
                    id="Q1",
                    label="Known",
                    direct_types=["Q5"],
                    sitelinks={"enwiki": {"title": "Known"}},
                )
            }
        )
    )

    class Client:
        def query(self, endpoint, params):
            assert params["action"] == "query" and params["titles"] == "Unknown"
            return (
                {"query": {"pages": [dict(title="Unknown", ns=0, missing=True)]}},
                "receipt",
                "now",
            )

    out = tmp_path / "metadata"
    result = events.collect_link_metadata(pages, out, metadata, {"Q1190554"}, Client())
    rows = read_json(out / "title_mapping.json.gz")
    assert {(r["target_title"], r["qid"]) for r in rows} == {
        ("Known", "Q1"),
        ("Unknown", None),
    }
    assert result["mapped_titles"] == 1 and result["unresolved_titles"] == 1


def test_disconnected_read_retry_preserves_failure_and_runs_once(tmp_path, monkeypatch):
    import time

    import requests

    from GG_Data.pipeline import simplified_page_events as events

    client = events.PageEvidenceClient(
        tmp_path, True, 10, time.monotonic() + 60, retry_disconnected=True
    )
    calls = []

    def get(*args, **kwargs):
        calls.append(1)
        raise requests.ConnectionError(
            "RemoteDisconnected: remote closed read connection"
        )

    monkeypatch.setattr(client.session, "get", get)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="Saved failed request"):
            client.query(
                "https://en.wikipedia.org/w/api.php", {"action": "query", "titles": "A"}
            )
    assert len(calls) == 2
    failures = list(tmp_path.rglob("*.json.gz"))
    assert len(failures) == 2 and all(not read_json(p)["ok"] for p in failures)
