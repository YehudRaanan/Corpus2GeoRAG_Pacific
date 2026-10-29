"""Offline checks for bounded, retained-source enrichment and all-row controls."""

import copy
import gzip
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from GG_Data.pipeline import post_qid_eda as eda
from GG_Data.pipeline import post_qid_events as events
from GG_Data.pipeline.test_post_qid_events import claim, hierarchy, sha, write


def article_fixture(tmp_path, scope="3"):
    from GG_Data.entity_resolution.hundred_page_pilot.collect_entities import raw_links

    core = tmp_path / "core"
    core.mkdir()
    page_ids = list(range(1, int(scope) + 1))
    text = (
        "[[Body event|Body]] <ref>[[Citation event]]</ref>\n"
        "{{navbox|list1=[[Navigation event]]}}\n"
        "==References==\n[[Reference event]]"
    )
    raw = tmp_path / "article.txt"
    raw.write_text(text, encoding="utf-8")
    pages = [
        dict(
            wiki_page_id=p,
            revision_id=20,
            raw_reference=dict(wikitext_path=str(raw), sha256=sha(raw)),
        )
        for p in page_ids
    ]
    for name, value in {
        "entities.json.gz": [dict(entity_id=q, type="MISC") for q in ("Q1", "Q2")],
        "wiki_pages.json.gz": pages,
    }.items():
        with gzip.open(core / name, "wt", encoding="utf-8") as stream:
            json.dump(value, stream)
    write(
        core / "manifest.json",
        dict(
            scope=scope,
            page_ids=page_ids,
            outputs={
                n: sha(core / n) for n in ("entities.json.gz", "wiki_pages.json.gz")
            },
        ),
    )
    links = [
        dict(
            link,
            page_id=1,
            revision_id=20,
            qid=q,
            raw_evidence_path=str(raw),
            raw_sha256=sha(raw),
        )
        for link, q in zip(raw_links(text), ("Q3", "Q4", "Q5", "Q6"))
    ]
    table = tmp_path / "wiki_link_occurrences.parquet"
    pq.write_table(pa.Table.from_pylist(links), table)
    collection = write(
        tmp_path / "collection.json", {"outputs": {table.name: sha(table)}}
    )
    return core, table, collection


@pytest.mark.parametrize("scope", ["3", "10", "100"])
def test_article_boundary_excludes_citation_and_navigation_but_keeps_raw_audit(
    tmp_path, monkeypatch, scope
):
    core, table, collection = article_fixture(tmp_path, scope)
    broad = tmp_path / "broad"
    records = {
        q: dict(requested_qid=q, entity=dict(id=q, claims={}))
        for q in ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6")
    }
    events._write_stage(
        broad,
        {
            "full_records.json.gz": records,
            "sources.json": {q: {"provider": "FIXTURE"} for q in records},
            "events.json.gz": [{"event_id": q} for q in ("Q1", "Q3", "Q4", "Q5", "Q6")],
            "event_entities.json.gz": [
                {"entity_id": q} for q in ("Q1", "Q3", "Q4", "Q5", "Q6")
            ],
            "event_decisions.json": [
                dict(qid=q, keep_event=True) for q in ("Q1", "Q3", "Q4", "Q5", "Q6")
            ],
        },
        dict(scope=scope, temporal_basis="MIXED"),
    )
    monkeypatch.setattr(events, "_mapping", lambda *args: ({}, {}))
    out = tmp_path / "out"
    result = events.restrict_events_to_articles(
        core, broad, table, collection, tmp_path, collection, sha(collection), out
    )
    assert {r["event_id"] for r in events.read_json(out / "events.json.gz")} == {
        "Q1",
        "Q3",
    }
    audit = events.read_json(out / "article_presence_evidence.json")
    assert {r["qid"] for r in audit} == {"Q3", "Q4", "Q5", "Q6"}
    assert [r["qid"] for r in audit if r["retained_content_link"]] == ["Q3"]
    assert result["scope"] == scope


def test_cached_enrichment_uses_only_article_qids_and_reports_missing_records(
    tmp_path, monkeypatch
):
    core, table, collection = article_fixture(tmp_path)
    native = tmp_path / "native"
    records = {
        q: dict(requested_qid=q, entity=dict(id=q, claims={}))
        for q in ("Q1", "Q2", "Q3", "Q4")
    }
    for q in ("Q3", "Q4"):
        records[q]["entity"]["claims"] = {
            "P31": [claim(q, "P31", "Q1190554", "type")],
            "P17": [claim(q, "P17", t, t) for t in ("Q1", "Q2")],
        }
    raw = write(tmp_path / "records.json", records)
    events._write_stage(
        native,
        {
            "full_records.json.gz": records,
            "sources.json": {
                q: dict(
                    provider="LOCAL_FULL_NATIVE_CACHE", file=str(raw), sha256=sha(raw)
                )
                for q in records
            },
        },
        dict(
            phase="NATIVE_CONSOLIDATION",
            inputs={str(raw): sha(raw)},
            source_files={str(raw.resolve()): sha(raw)},
            counts={"missing": 0},
        ),
    )
    h = hierarchy(tmp_path)
    monkeypatch.setattr(events, "_mapping", lambda *args: ({}, {}))
    out = tmp_path / "out"
    result = events.apply_cached_events(
        core_dir=core,
        native_dir=native,
        link_table=table,
        collection_manifest=collection,
        hierarchy=h,
        approval_sha256=sha(h / "recognition_approval.json"),
        mapping_dir=tmp_path,
        mapping_manifest=collection,
        mapping_manifest_sha256=sha(collection),
        output=out,
    )
    assert {r["event_id"] for r in events.read_json(out / "events.json.gz")} == {"Q3"}
    assert (
        result["missing_article_qids"] == []
    )  # Removed links do not require acquisition.
    assert result["counts"]["stored_directed_rows"] == 4
    assert result["acquisition_executed"] is False
    del records["Q3"]
    native2 = tmp_path / "native2"
    raw2 = write(tmp_path / "records2.json", records)
    events._write_stage(
        native2,
        {
            "full_records.json.gz": records,
            "sources.json": {
                q: dict(file=str(raw2), sha256=sha(raw2)) for q in records
            },
        },
        dict(
            phase="NATIVE_CONSOLIDATION",
            inputs={str(raw2): sha(raw2)},
            source_files={str(raw2.resolve()): sha(raw2)},
            counts={"missing": 0},
        ),
    )
    result = events.apply_cached_events(
        core_dir=core,
        native_dir=native2,
        link_table=table,
        collection_manifest=collection,
        hierarchy=h,
        approval_sha256=sha(h / "recognition_approval.json"),
        mapping_dir=tmp_path,
        mapping_manifest=collection,
        mapping_manifest_sha256=sha(collection),
        output=tmp_path / "incomplete",
    )
    assert result["missing_article_qids"] == ["Q3"]
    assert result["status"] == "ARTICLE_NATIVE_CACHE_INCOMPLETE"


def revised_tables():
    rows = [
        dict(
            source_row_index=i,
            page_id=p,
            revision_id=r,
            word=w,
            word_original="[[Alpha|A]]" if i == 0 else w,
            entity_group="PER",
            Source="Q50",
            source_title="Page",
            Text="[[Alpha|A]]" if i == 0 else w,
            start=0,
            end=11 if i == 0 else len(w),
            Text_clean="A" if i == 0 else w,
            clean_start=0 if i == 0 else None,
            clean_end=1 if i == 0 else None,
            clean_status="mapped" if i == 0 else "excluded",
            matching_eligible=i == 0,
            matching_eligibility_reason="eligible" if i == 0 else "source_excluded",
        )
        for i, p, r, w in [
            (0, 1, 10, "A"),
            (1, 1, 10, "Excluded"),
            (2, None, None, "Missing"),
        ]
    ]
    rows[2].update(
        clean_status="uncertain", matching_eligibility_reason="page_revision_unresolved"
    )
    mentions = []
    for row, status in zip(
        rows, ("PENDING_MATCHING", "SOURCE_EXCLUDED", "PAGE_REVISION_UNRESOLVED")
    ):
        raw = {
            key: row[key] for key in ("entity_group", "start", "end", "Source", "Text")
        }
        raw.update(word=row["word_original"], score=0.9, Index=0, subtype=None)
        mentions.append(
            dict(
                row,
                score=0.9,
                Index=0,
                subtype=None,
                mention_id=f"m{row['source_row_index']}",
                wiki_site="enwiki",
                wiki_page_id=row["page_id"],
                raw=raw,
                processing_status=status,
            )
        )
    return dict(
        mentions=mentions,
        mention_entity_links=[],
        entities=[],
        wiki_pages=[dict(wiki_site="enwiki", wiki_page_id=1, revision_id=10)],
    )


def test_eda_preserves_clean_working_values_and_all_original_audit_rows():
    tables = revised_tables()
    report = eda.summarize(tables)
    assert report["denominators"]["original_mentions"] == 3
    assert report["processing_status_counts"] == {
        "PAGE_REVISION_UNRESOLVED": 1,
        "PENDING_MATCHING": 1,
        "SOURCE_EXCLUDED": 1,
    }
    corrupt = copy.deepcopy(tables)
    corrupt["mentions"][0]["wiki_page_id"] = 999
    with pytest.raises(ValueError, match="revision FK"):
        eda.summarize(corrupt)


def test_eda_rejects_unexplained_unlinked_mentions_and_bad_clean_slices():
    tables = revised_tables()
    tables["mentions"][0]["processing_status"] = "ACCEPTED_EXACT"
    with pytest.raises(ValueError, match="bridge"):
        eda.summarize(tables)
    tables = revised_tables()
    tables["mentions"][0]["clean_end"] = 0
    with pytest.raises(ValueError, match="clean"):
        eda.summarize(tables)


@pytest.mark.parametrize(
    "corruption", ["unknown_scope", "unknown_page", "missing_membership"]
)
def test_article_enrichment_rejects_unbounded_or_changed_page_scope(
    tmp_path, corruption
):
    core, table, collection = article_fixture(tmp_path, "10")
    manifest = events.read_json(core / "manifest.json")
    if corruption == "unknown_scope":
        manifest["scope"] = "all"
    elif corruption == "unknown_page":
        manifest["page_ids"][-1] = 999
    else:
        del manifest["page_ids"]
    write(core / "manifest.json", manifest)
    with pytest.raises(ValueError, match="scope|page_ids"):
        events._article_evidence(core, table, collection)


def test_relation_export_rejects_orphan_derived_inverse():
    from GG_Data.pipeline.post_qid_relations import export_stored_relations
    from GG_Data.pipeline.test_post_qid_relations import build, inputs

    rows = build(inputs())["relations"]
    rows[1]["source_edge_id"] = "missing"
    with pytest.raises(ValueError, match="inverse"):
        export_stored_relations(rows)


@pytest.mark.parametrize(
    "field",
    ["source_record", "input_assertion", "time_from", "time_to", "time_point", "count"],
)
def test_relation_inverse_cannot_change_native_or_temporal_evidence(field):
    from GG_Data.pipeline.post_qid_relations import export_stored_relations
    from GG_Data.pipeline.test_post_qid_relations import build, inputs

    rows = build(inputs())["relations"]
    if field == "source_record":
        rows[1]["input_assertion"][field] = {"invented": True}
    else:
        rows[1][field] = {"invented": True} if field == "input_assertion" else "changed"
    with pytest.raises(ValueError, match="inverse"):
        export_stored_relations(rows)


def test_eda_rejects_relations_with_missing_endpoints():
    from GG_Data.pipeline.test_post_qid_relations import build, inputs

    tables = revised_tables()
    tables["relations"] = build(inputs())["relations"]
    with pytest.raises(ValueError, match="endpoint"):
        eda.summarize(tables)


def test_revised_eda_counts_source_pages_from_page_identity():
    first = revised_tables()["mentions"][0]
    first["processing_status"] = "ACCEPTED_EXACT"
    second = copy.deepcopy(first)
    second.update(
        mention_id="m1", source_row_index=1, page_id=2, wiki_page_id=2, revision_id=20
    )
    tables = dict(
        mentions=[first, second],
        wiki_pages=[
            dict(wiki_site="enwiki", wiki_page_id=p, revision_id=r)
            for p, r in [(1, 10), (2, 20)]
        ],
        mention_entity_links=[
            dict(
                mention_id=f"m{i}",
                entity_id="Q10",
                entity_type="PER",
                method="exact",
                methods=["exact"],
            )
            for i in range(2)
        ],
        entities=[
            dict(
                entity_id="Q10",
                type="PER",
                importance=4,
                unique_original_mention_count=2,
                distinct_source_page_count=2,
                attributes=dict(
                    importance_basis=dict(total_mentions=2, distinct_source_pages=2),
                    normalized_mention_frequency=1.0,
                    normalized_mention_frequency_denominator=2,
                ),
            )
        ],
    )
    assert eda.summarize(tables)["denominators"]["source_pages"] == 2
