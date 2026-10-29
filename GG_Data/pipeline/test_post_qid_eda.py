"""Population controls use original mentions and pages, never revision fanout."""

import copy
import gzip
import json

import pytest

from GG_Data.pipeline import post_qid_eda as eda


@pytest.fixture
def tables():
    rows = [
        dict(
            source_row_index=i,
            page_id=page,
            revision_id=revision,
            word=name,
            entity_group=typ,
            Source=f"P{page}",
            Text=name,
            start=0,
            end=len(name),
        )
        for i, page, revision, name, typ in [
            (0, 1, 10, "Alpha", "DATE"),
            (1, 1, 11, "Alias", "PER"),
            (2, 2, 20, "Alpha", "DATE"),
            (3, 1, 10, "Unknown", "LOC"),
        ]
    ]
    mentions = [
        {
            **r,
            "mention_id": f"m{i}",
            "wiki_site": "enwiki",
            "wiki_page_id": r["page_id"],
            "raw": dict(r),
        }
        for i, r in enumerate(rows)
    ]
    links = [
        dict(
            mention_id=mid,
            entity_id=eid,
            entity_type=typ,
            method=method,
            methods=[method],
        )
        for mid, eid, typ, method in [
            ("m0", "Q1", "DATE", "model"),
            ("m0", "Q2", "DATE", "exact"),
            ("m1", "Q1", "PER", "exact"),
            ("m2", "Q1", "DATE", "model"),
            ("m3", "PROV_one", "LOC", "unresolved"),
        ]
    ]
    entities = [
        dict(
            entity_id=eid,
            type=typ,
            importance=count * pages,
            unique_original_mention_count=count,
            distinct_source_page_count=pages,
            identity_status=(
                "QID_MATCHED" if eid.startswith("Q") else "PROVISIONAL_UNRESOLVED"
            ),
            native_record_status="MISSING" if eid == "Q2" else "AVAILABLE",
            labels={"en": {"value": "Alpha"}} if eid == "Q1" else {},
            attributes={
                "importance_basis": {
                    "total_mentions": count,
                    "distinct_source_pages": pages,
                },
                "normalized_mention_frequency": count / 4,
                "normalized_mention_frequency_denominator": 4,
            },
        )
        for eid, typ, count, pages in [
            ("Q1", "DATE", 3, 2),
            ("Q1", "PER", 3, 2),
            ("Q2", "DATE", 1, 1),
            ("PROV_one", "LOC", 1, 1),
        ]
    ]
    pages = [
        dict(wiki_site="enwiki", wiki_page_id=p, revision_id=r)
        for p, r in [(1, 10), (1, 11), (2, 20)]
    ]
    return dict(
        mentions=mentions,
        mention_entity_links=links,
        entities=entities,
        wiki_pages=pages,
    )


def test_denominators_typed_identity_and_page_cooccurrence(tables):
    original = copy.deepcopy(tables)
    report = eda.summarize(tables, include_cooccurrence=True)
    assert tables == original
    assert report["denominators"] == dict(
        original_mentions=4, source_pages=2, used_revisions=3, bridge_rows=5
    )
    assert report["identities"] == dict(
        qid_typed_rows=3,
        qid_distinct=2,
        provisional_typed_rows=1,
        provisional_distinct=1,
    )
    assert report["many_to_many"]["mentions_with_multiple_qids"] == 1
    assert report["many_to_many"]["qids_with_multiple_daniel_names"] == 1
    assert report["methods"]["bridge_rows"] == {"exact": 2, "model": 2, "unresolved": 1}
    assert report["optional_tables"]["events"]["status"] == "NOT_EVALUATED"
    assert report["accuracy_status"] == "NOT_EVALUATED_POSITIVE_ONLY_REFERENCE"
    assert report["native_records"]["missing_qid_typed_rows"] == 1
    assert report["native_records"]["blank_english_label_qid_typed_rows"] == 1
    graph = report["page_cooccurrence"]
    assert len(graph["nodes"]) == 4
    assert all(edge["shared_page_count"] == 1 for edge in graph["edges"])
    assert len(graph["edges"]) == 6
    assert report["importance"]["verified_typed_rows"] == 4


@pytest.mark.parametrize(
    "corruption",
    [
        "duplicate_link",
        "bad_entity_fk",
        "bad_mention_fk",
        "bad_page_fk",
        "duplicate_mention",
        "duplicate_entity",
        "duplicate_revision",
        "lost_link",
        "raw_changed",
        "wrong_type",
        "wrong_importance",
        "wrong_denominator",
    ],
)
def test_invalid_population_fails(tables, corruption):
    if corruption == "duplicate_link":
        tables["mention_entity_links"].append(dict(tables["mention_entity_links"][0]))
    elif corruption == "bad_entity_fk":
        tables["mention_entity_links"][0]["entity_id"] = "Q999"
    elif corruption == "bad_mention_fk":
        tables["mention_entity_links"][0]["mention_id"] = "missing"
    elif corruption == "bad_page_fk":
        tables["mentions"][0]["wiki_page_id"] = 99
    elif corruption == "duplicate_mention":
        tables["mentions"].append(dict(tables["mentions"][0]))
    elif corruption == "duplicate_entity":
        tables["entities"].append(dict(tables["entities"][0]))
    elif corruption == "duplicate_revision":
        tables["wiki_pages"].append(dict(tables["wiki_pages"][0]))
    elif corruption == "lost_link":
        tables["mention_entity_links"].pop()
    elif corruption == "raw_changed":
        tables["mentions"][0]["word"] = "Changed"
    elif corruption == "wrong_type":
        tables["mention_entity_links"][0]["entity_type"] = "PER"
    elif corruption == "wrong_importance":
        tables["entities"][0]["importance"] = 0.75
    elif corruption == "wrong_denominator":
        tables["entities"][0]["attributes"][
            "normalized_mention_frequency_denominator"
        ] = 5
    with pytest.raises(ValueError):
        eda.summarize(tables)


def test_event_only_entity_does_not_invent_mentions_or_corpus_importance(tables):
    tables["entities"].append(
        dict(
            entity_id="Q9",
            type="EVENT",
            importance=None,
            native_record_status="AVAILABLE",
            labels={},
        )
    )
    report = eda.summarize(tables, include_cooccurrence=True)
    assert report["denominators"]["original_mentions"] == 4
    assert report["importance"]["verified_typed_rows"] == 4
    assert report["importance"]["event_only_typed_rows"] == 1
    node = next(
        n for n in report["page_cooccurrence"]["nodes"] if n["entity_id"] == "Q9"
    )
    assert node["degree"] == 0


def test_existing_native_event_rows_lowercase_type_and_source_coverage(tables):
    from GG_Data.pipeline.event_model import event_rows

    entity, event = event_rows(
        {"id": "Q9", "claims": {}, "labels": {"en": {"value": "Native event"}}},
        {"provider": "FIXTURE"},
        {"status": "FIXTURE_SELECTED"},
    )
    tables["entities"].append(entity)
    tables["events"] = [event]
    report = eda.summarize(tables)
    assert entity["type"] == "event"
    assert report["importance"]["event_only_typed_rows"] == 1
    assert report["native_records"]["missing_qid_typed_rows"] == 1
    assert report["native_records"]["event_only_source_coverage"] == {
        "status": "NOT_EVALUATED_EVENT_SOURCE",
        "typed_rows": 1,
    }


def test_run_checks_manifest_counts_and_optional_tables(tmp_path, tables):
    for name, rows in tables.items():
        with gzip.open(tmp_path / f"{name}.json.gz", "wt", encoding="utf8") as stream:
            json.dump(rows, stream)
    with gzip.open(tmp_path / "events.json.gz", "wt", encoding="utf8") as stream:
        json.dump([], stream)
    manifest = {
        "counts": {name: len(rows) for name, rows in tables.items()},
        "quality_status": "FAIL_OR_UNKNOWN",
        "page_ids": [1, 2],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    report = eda.run(tmp_path, tmp_path / "report")
    assert report["quality_status"] == "FAIL_OR_UNKNOWN"
    assert report["optional_tables"]["events"] == {
        "status": "PRESENT_NOT_EVALUATED",
        "row_count": 0,
    }
    assert (tmp_path / "report/eda.json").is_file()
    manifest["counts"]["mentions"] = 999
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        eda.run(tmp_path, tmp_path / "bad-report")
    assert not (tmp_path / "bad-report").exists()
