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
