"""Recovery must preserve literal source evidence and never guess ship titles."""

import hashlib

import pytest

from GG_Data.entity_resolution.hundred_page_pilot.collect_entities import (
    validate_revision,
)


def test_ship_year_and_display_parameter_preserve_target_and_offsets():
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        template_targets,
    )

    raw = "{{sHiP|Japanese battleship|Fusō|1914|2}}"
    text = "前文\n" + raw + " followed by " + raw
    rows = template_targets(text)
    assert [row["target_title"] for row in rows] == [
        "Japanese battleship Fusō (1914)",
        "Japanese battleship Fusō (1914)",
    ]
    assert [row["raw_start"] for row in rows] == [3, 3 + len(raw) + 13]
    for row in rows:
        assert text[row["raw_start"] : row["raw_end"]] == raw
        assert row["raw_text"] == raw
        assert row["link_origin"] == "RAW_SHIP_TEMPLATE"
        assert row["template_status"]


@pytest.mark.parametrize(
    "suffix, expected", [("", "USS Example"), ("|1942", "USS Example (1942)")]
)
def test_optional_ship_identifier(suffix, expected):
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        template_targets,
    )

    rows = template_targets("{{Ship|USS|Example" + suffix + "}}")
    assert [row["target_title"] for row in rows] == [expected]


@pytest.mark.parametrize(
    "wrapper",
    [
        "<!-- {} -->",
        "<nowiki>{}</nowiki>",
        "<pre>{}</pre>",
        "<source>{}</source>",
        "<math>{}</math>",
    ],
)
def test_protected_ship_templates_are_not_links(wrapper):
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        template_targets,
    )

    assert template_targets(wrapper.format("{{Ship|USS|Hidden|1942}}")) == []


@pytest.mark.parametrize(
    "raw",
    [
        "{{Ship|USS|Example|1942|wl=no}}",
        "{{Ship|USS|Example|1942|unknown=other}}",
        "{{Ship|USS|{{Other|Example}}|1942}}",
        "{{Ship|USS|Example|1942|unsupported-display}}",
    ],
)
def test_unlinked_or_unsupported_templates_do_not_invent_titles(raw):
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        template_targets,
    )

    assert all(row["target_title"] is None for row in template_targets(raw))


def test_explicit_position_parameters_are_supported_or_marked_for_review():
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        template_targets,
    )

    rows = template_targets("{{Ship|2=Example|3=1942|1=USS}}")
    assert len(rows) == 1
    row = rows[0]
    assert row["target_title"] in {"USS Example (1942)", None}
    if row["target_title"] is None:
        assert "REVIEW" in row["template_status"].upper()


def test_saved_revision_hash_guard_rejects_modified_source(tmp_path):
    path = tmp_path / "revision.wikitext"
    original = b"{{Ship|USS|Example|1942}}"
    path.write_bytes(original + b" changed")
    revision = {
        "wikitext_path": str(path),
        "sha256": hashlib.sha256(original).hexdigest(),
        "page_id": 1,
        "revision_id": 2,
        "evidence_path": str(tmp_path / "not_read_when_hash_is_wrong.json"),
    }
    with pytest.raises(ValueError, match="Raw revision hash mismatch"):
        validate_revision(revision)


@pytest.mark.parametrize(
    "page_flags, props, expected_qid, expected_status",
    [
        ({}, {"wikibase_item": "Q123"}, "Q123", "CURRENT_EXPLICIT_WIKIPEDIA_QID"),
        (
            {},
            {"wikibase_item": "Q123", "disambiguation": ""},
            None,
            "DISAMBIGUATION_PAGE_REVIEW",
        ),
        ({"missing": True}, {"wikibase_item": "Q123"}, None, "MISSING_OR_INVALID_PAGE"),
    ],
)
def test_checked_title_preserves_redirect_and_rejects_unsafe_qids(
    page_flags, props, expected_qid, expected_status
):
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        checked_title,
    )

    redirects = [{"from": "USS Example", "to": "USS Example (1942)"}]
    data = {
        "query": {
            "redirects": redirects,
            "pages": [
                {
                    "pageid": 123,
                    "ns": 0,
                    "title": "USS Example (1942)",
                    "pageprops": props,
                    **page_flags,
                }
            ],
        }
    }
    result = checked_title(
        "USS Example", data, "saved-response.json", "2026-10-29T10:00:00Z"
    )
    assert result["qid"] == expected_qid
    assert result["qid_status"] == expected_status
    assert result["canonical_target_title"] == "USS Example (1942)"
    assert result["redirect_chain"] == redirects
    assert result["mapping_evidence"] == "saved-response.json"
    assert result["mapping_retrieval_utc"] == "2026-10-29T10:00:00Z"


def test_redirect_to_section_does_not_assign_the_destination_page_qid():
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        checked_title,
    )

    data = {
        "query": {
            "redirects": [
                {"from": "Example ship", "to": "Ship list", "tofragment": "Example"}
            ],
            "pages": [
                {
                    "pageid": 123,
                    "ns": 0,
                    "title": "Ship list",
                    "pageprops": {"wikibase_item": "Q123"},
                }
            ],
        }
    }
    assert (
        checked_title("Example ship", data, "saved.json", "2026-10-29")["qid"] is None
    )


@pytest.mark.parametrize(
    "entity",
    [
        {"id": "Q123", "missing": ""},
        {"id": "Q123", "invalid": ""},
        {"id": "Q456", "labels": {}, "claims": {}},
        {"id": "Q123"},
    ],
)
def test_checked_metadata_rejects_unbound_or_missing_entity(entity):
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        checked_metadata,
    )

    assert checked_metadata("Q123", entity)["metadata_status"] == "MISSING_METADATA"


def test_checked_metadata_retains_valid_empty_metadata_revision():
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        checked_metadata,
    )

    row = checked_metadata(
        "Q123", {"id": "Q123", "labels": {}, "claims": {}, "lastrevid": 42}
    )
    assert row["metadata_status"] == "AVAILABLE"
    assert row["metadata_revision"] == 42


def test_unrelated_fragment_redirect_does_not_reject_another_title():
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        checked_title,
    )

    data = {
        "query": {
            "redirects": [
                {"from": "Other person", "to": "List of people", "tofragment": "Other"}
            ],
            "pages": [
                {
                    "title": "Mikasa",
                    "ns": 0,
                    "pageid": 1,
                    "pageprops": {"wikibase_item": "Q696891"},
                }
            ],
        }
    }
    row = checked_title("Mikasa", data, "evidence.json", "2026-10-29")
    assert row["qid"] == "Q696891"
    assert row["redirect_chain"] == []


def test_redirect_cannot_silently_change_explicit_ship_year():
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        checked_title,
    )

    data = {
        "query": {
            "redirects": [
                {
                    "from": "Japanese destroyer Asagumo (1938)",
                    "to": "Japanese destroyer Asagumo (1937)",
                }
            ],
            "pages": [
                {
                    "title": "Japanese destroyer Asagumo (1937)",
                    "ns": 0,
                    "pageprops": {"wikibase_item": "Q2991436"},
                }
            ],
        }
    }
    row = checked_title(
        "Japanese destroyer Asagumo (1938)", data, "evidence.json", "2026-10-29"
    )
    assert row["qid"] is None
    assert row["verified_qid"] == "Q2991436"
    assert row["qid_status"] == "IDENTIFIER_YEAR_CHANGED_REVIEW"


@pytest.mark.parametrize(
    "raw, expected, name",
    [
        ("{{USS|Enterprise|CV-6|2}}", "USS Enterprise (CV-6)", "Enterprise"),
        ("{{Jsub|I-24|1939|2}}", "Japanese submarine I-24 (1939)", "I-24"),
        (
            "{{Sclass|Königsberg|cruiser|||1905}}",
            "Königsberg-class cruiser (1905)",
            "Königsberg",
        ),
        ("{{Sclass2|Flower|corvette|1}}", "Flower-class corvette", "Flower"),
        ("{{HMS|Hoxa|T16|6}}", "HMS Hoxa (T16)", "Hoxa"),
        ("{{Ship|2=Example|3=1942|1=USS}}", "USS Example (1942)", "Example"),
    ],
)
def test_documented_families_keep_name_parameter_offsets(raw, expected, name):
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        template_targets,
    )

    text = "前文 " + raw + " " + raw
    rows = template_targets(text)
    assert len(rows) == 2
    for row in rows:
        assert row["target_title"] == expected
        assert row["name"] == name
        assert text[row["name_start"] : row["name_end"]] == name
        assert text[row["raw_start"] : row["raw_end"]] == raw


def test_nested_parent_does_not_hide_ship_and_nested_name_is_reviewed():
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        template_targets,
    )

    rows = template_targets(
        "{{Infobox|ships={{USS|Example|1942}}}} {{Ship|USS|{{lang|en|Other}}|1943}}"
    )
    assert [row["target_title"] for row in rows] == ["USS Example (1942)", None]
    assert rows[1]["template_status"] == "REVIEW_NESTED_OR_MARKUP_PARAMETER"


def test_duplicate_parameter_never_chooses_by_iteration_order():
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        template_targets,
    )

    rows = template_targets("{{USS|Example|1=Other|1942}}")
    assert rows[0]["target_title"] is None
    assert rows[0]["template_status"] == "REVIEW_DUPLICATE_PARAMETER"


def test_checked_metadata_keeps_japanese_separate_from_english():
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        checked_metadata,
    )

    row = checked_metadata(
        "Q123",
        {
            "id": "Q123",
            "labels": {"en": {"value": "Example"}, "ja": {"value": "例"}},
            "aliases": {"ja": [{"value": "別名"}]},
            "claims": {},
            "sitelinks": {"jawiki": {"title": "例"}},
        },
    )
    assert row["label"] == "Example"
    assert row["aliases"] == []
    assert row["label_ja"] == "例"
    assert row["aliases_ja"] == ["別名"]
    assert row["jawiki_title"] == "例"


def test_inventory_is_manifest_bound_cache_only_and_preserves_existing_rows(tmp_path):
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    from GG_Data.entity_resolution.attach_source_page_ids import save_json, sha256
    from GG_Data.entity_resolution.hundred_page_pilot.collect_entities import WIKI
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        recover_inventory,
    )

    collection = tmp_path / "collection"
    collection.mkdir()
    raw = "[[Existing|Existing]] {{USS|Example|1942|2}} {{unknown|Other}}"
    source = tmp_path / "raw.txt"
    source.write_text(raw, encoding="utf8")
    evidence = tmp_path / "revision.json"
    save_json(
        evidence,
        {
            "ok": True,
            "response_text": json.dumps(
                {"parse": {"pageid": 1, "revid": 2, "title": "Source", "wikitext": raw}}
            ),
        },
    )
    revisions = tmp_path / "revisions.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                dict(
                    page_id=1,
                    revision_id=2,
                    wiki_title="Source",
                    revision_timestamp="2020-01-01",
                    wikitext_path=str(source),
                    evidence_path=str(evidence),
                    sha256=sha256(source),
                )
            ]
        ),
        revisions,
    )
    mentions = tmp_path / "mentions.parquet"
    pq.write_table(pa.Table.from_pylist([dict(page_id=1, revision_id=2)]), mentions)
    original = [
        dict(page_id=1, revision_id=2, qid="Q1", label="Existing"),
        dict(page_id=9, revision_id=10, qid="Q9", label="Outside preserved"),
    ]
    pq.write_table(pa.Table.from_pylist(original), collection / "entities.parquet")
    pq.write_table(
        pa.Table.from_pylist(
            [
                dict(
                    qid="Q1",
                    label="Existing",
                    metadata_status="AVAILABLE",
                    native_types=[],
                ),
                dict(
                    qid="Q2",
                    label="Example",
                    metadata_status="AVAILABLE",
                    native_types=[],
                ),
            ]
        ),
        collection / "native_metadata.parquet",
    )
    cache = tmp_path / "requests"
    cache.mkdir()
    response = {
        "query": {
            "pages": [
                dict(
                    title="USS Example (1942)",
                    ns=0,
                    pageid=20,
                    pageprops={"wikibase_item": "Q2"},
                ),
                dict(
                    title="Existing", ns=0, pageid=10, pageprops={"wikibase_item": "Q1"}
                ),
            ]
        }
    }
    save_json(
        cache / "previous-batch.json.gz",
        dict(
            endpoint=WIKI,
            params=dict(
                titles="USS Example (1942)|Existing",
                ppprop="wikibase_item|disambiguation",
            ),
            ok=True,
            response_text=json.dumps(response),
            retrieved_utc="2026-10-29T00:00:00Z",
        ),
    )
    summary = recover_inventory(
        mentions, revisions, collection, tmp_path / "out", request_cache=cache
    )
    rows = pq.read_table(tmp_path / "out/entities.parquet").to_pylist()
    assert rows[:2] == original
    assert {(row["page_id"], row["revision_id"], row["qid"]) for row in rows} == {
        (1, 2, "Q1"),
        (9, 10, "Q9"),
        (1, 2, "Q2"),
    }
    targets = pq.read_table(tmp_path / "out/target_evidence.parquet").to_pylist()
    assert {row["qid"] for row in targets if row.get("qid")} == {"Q1", "Q2"}
    assert any(
        row["template_status"] == "REVIEW_UNSUPPORTED_TEMPLATE" for row in targets
    )
    assert summary["api_requests"] == 0
    assert summary["page_revisions"] == 1
    assert summary["protected_input_hashes_unchanged"] is True
    conflict_response = {
        "query": {
            "pages": [
                dict(
                    title="USS Example (1942)",
                    ns=0,
                    pageid=30,
                    pageprops={"wikibase_item": "Q3"},
                )
            ]
        }
    }
    save_json(
        cache / "z-conflict.json.gz",
        dict(
            endpoint=WIKI,
            params=dict(
                titles="USS Example (1942)", ppprop="wikibase_item|disambiguation"
            ),
            ok=True,
            response_text=json.dumps(conflict_response),
            retrieved_utc="2026-10-29T01:00:00Z",
        ),
    )
    conflict = recover_inventory(
        mentions, revisions, collection, tmp_path / "conflict", request_cache=cache
    )
    assert conflict["added_entity_page_revision_rows"] == 0
    assert conflict["lookup_statuses"]["QID_CHANGED_SINCE_CACHE_REVIEW"] == 1
    unsafe_response = {
        "query": {
            "pages": [
                dict(
                    title="USS Example (1942)",
                    ns=0,
                    pageid=20,
                    pageprops={"wikibase_item": "Q2", "disambiguation": ""},
                )
            ]
        }
    }
    save_json(
        cache / "a-unsafe.json.gz",
        dict(
            endpoint=WIKI,
            params=dict(
                titles="USS Example (1942)", ppprop="wikibase_item|disambiguation"
            ),
            ok=True,
            response_text=json.dumps(unsafe_response),
            retrieved_utc="2026-10-29T01:00:00Z",
        ),
    )
    (cache / "z-conflict.json.gz").unlink()
    unsafe = recover_inventory(
        mentions, revisions, collection, tmp_path / "unsafe", request_cache=cache
    )
    assert unsafe["added_entity_page_revision_rows"] == 0
    assert unsafe["lookup_statuses"]["DISAMBIGUATION_PAGE_REVIEW"] == 1
    pq.write_table(
        pa.Table.from_pylist([dict(target_title="USS Example (1942)", qid="Q2")]),
        collection / "title_qid_mapping.parquet",
    )
    unchecked = recover_inventory(
        mentions,
        revisions,
        collection,
        tmp_path / "unchecked",
        request_cache=tmp_path / "empty-cache",
    )
    assert unchecked["added_entity_page_revision_rows"] == 0
    import shutil

    reused = tmp_path / "qid_recovery_20261029_v2"
    reused.mkdir()
    reused_hashes = {}
    for filename in (
        "added_entities.parquet",
        "native_metadata.parquet",
        "target_evidence.parquet",
    ):
        shutil.copyfile(tmp_path / "out" / filename, reused / filename)
        reused_hashes[filename] = sha256(reused / filename)
    save_json(
        reused / "summary.json",
        dict(protected_input_hashes_unchanged=True, output_sha256=reused_hashes),
    )
    rejected_reuse = recover_inventory(
        mentions,
        revisions,
        collection,
        tmp_path / "rejected-reuse",
        request_cache=cache,
    )
    assert rejected_reuse["reused_entity_page_revision_rows"] == 1
    assert rejected_reuse["added_entity_page_revision_rows"] == 0
    assert (
        pq.read_table(tmp_path / "rejected-reuse/entities.parquet").to_pylist()
        == original
    )
    with pytest.raises(FileExistsError, match="Preserve output"):
        recover_inventory(mentions, revisions, collection, tmp_path / "out")
    with pytest.raises(ValueError, match="at most 200"):
        recover_inventory(
            mentions, revisions, collection, tmp_path / "too-many", max_requests=201
        )
    pq.write_table(pa.Table.from_pylist([dict(page_id=99, revision_id=100)]), mentions)
    with pytest.raises(ValueError, match="Missing or duplicate"):
        recover_inventory(mentions, revisions, collection, tmp_path / "wrong-scope")


def test_unknown_families_have_explicit_review_evidence_only_when_requested():
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        template_targets,
    )

    assert template_targets("{{IJN}} {{unknown|Name}}") == []
    rows = template_targets("{{IJN}} {{unknown|Name}}", include_unsupported=True)
    assert len(rows) == 2
    assert all(row["target_title"] is None for row in rows)
    assert all(row["template_status"] == "REVIEW_UNSUPPORTED_TEMPLATE" for row in rows)


def test_blank_name_parameter_has_an_empty_valid_span():
    from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
        template_targets,
    )

    row = template_targets("{{USS|   |1942}} ")[0]
    assert row["target_title"] is None
    assert row["name_start"] == row["name_end"]
