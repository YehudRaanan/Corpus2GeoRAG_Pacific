from build_source_ontology_map import (
    build_rows,
    make_level1_statistics,
    make_statistics,
    parse_rdf_xml,
)


def relation(source: str, predicate: str, uri: str | None = None) -> dict[str, str]:
    return {
        "source": source,
        "source_predicate": predicate,
        "predicate_uri": uri or predicate,
        "label": predicate.rsplit("/", 1)[-1],
        "occurrence_count": "3",
    }


def test_declared_parents_stay_separate_and_missing_parent_is_explicit() -> None:
    first = "http://example.org/first"
    second = "http://example.org/second"
    metadata = {
        first: {
            "parents": {
                ("http://example.org/a", "RDFS_SUBPROPERTY", "source", "same", ""): None,
                ("http://example.org/b", "RDFS_SUBPROPERTY", "source", "reverse", "scope"): None,
            },
            "domains": {"http://example.org/Event"},
            "ranges": {"http://example.org/Place"},
            "types": set(),
        }
    }
    inventory = [relation("WarSampo", first), relation("WarSampo", second)]

    rows = build_rows(inventory, metadata, {})
    statistics = make_statistics(inventory, rows)

    assert len(rows) == 3
    assert {row["level1_uri"] for row in rows if row["level2_uri"] == first} == {
        "http://example.org/a",
        "http://example.org/b",
    }
    assert next(row for row in rows if row["level2_uri"] == second)[
        "resolution_status"
    ] == "NO_DECLARED_PARENT"
    assert statistics == [
        {
            "source": "WarSampo",
            "eligible_level2_rows": "2",
            "level2_with_declared_parent": "1",
            "level2_without_declared_parent": "1",
            "level2_with_multiple_parents": "1",
            "declared_parent_edges": "2",
            "coverage_pct": "50.00",
        }
    ]


def test_eventkg_mapping_is_not_applied_to_wikidata_source() -> None:
    uri = "http://www.wikidata.org/prop/direct/P276"
    metadata = {
        uri: {
            "parents": {
                (
                    "http://semanticweb.cs.vu.nl/2009/11/sem/hasPlace",
                    "EVENTKG_MANUAL_MAPPING",
                    "source",
                    "same",
                    "scope",
                ): None
            },
            "domains": set(),
            "ranges": set(),
            "types": set(),
        }
    }
    inventory = [relation("EventKG", uri), relation("Wikidata", "wd:P276")]

    rows = build_rows(inventory, metadata, {})

    assert rows[0]["resolution_status"] == "DECLARED_PARENT"
    assert rows[1]["resolution_status"] == "NO_DECLARED_PARENT"


def test_statistics_use_uri_when_short_names_repeat() -> None:
    first = "http://example.org/scope-a/unit"
    second = "http://example.org/scope-b/unit"
    metadata = {
        first: {
            "parents": {
                ("http://example.org/member", "RDFS_SUBPROPERTY", "source", "same", ""): None
            },
            "domains": set(),
            "ranges": set(),
            "types": set(),
        },
        second: {"parents": {}, "domains": set(), "ranges": set(), "types": set()},
    }
    inventory = [
        relation("WarSampo", "unit", first),
        relation("WarSampo", "unit", second),
    ]

    rows = build_rows(inventory, metadata, {})
    statistics = make_statistics(inventory, rows)

    assert statistics[0]["level2_with_declared_parent"] == "1"
    assert statistics[0]["level2_without_declared_parent"] == "1"


def test_rdf_xml_resolves_relative_property_uris() -> None:
    metadata: dict = {}
    data = b'''<rdf:RDF
        xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
        xml:base="http://example.org/ontology/">
      <rdf:Property rdf:about="child">
        <rdfs:subPropertyOf rdf:resource="parent" />
      </rdf:Property>
    </rdf:RDF>'''

    parse_rdf_xml(data, metadata, "https://example.org/schema.rdf")

    parents = metadata["http://example.org/ontology/child"]["parents"]
    assert next(iter(parents))[0] == "http://example.org/ontology/parent"


def test_level1_statistics_count_children_and_occurrences() -> None:
    parent = "http://example.org/parent"
    metadata = {
        uri: {
            "parents": {(parent, "RDFS_SUBPROPERTY", "source", "same", ""): None},
            "domains": set(),
            "ranges": set(),
            "types": set(),
        }
        for uri in ("http://example.org/a", "http://example.org/b")
    }
    inventory = [
        relation("WarSampo", "a", "http://example.org/a"),
        relation("WarSampo", "b", "http://example.org/b"),
    ]

    statistics = make_level1_statistics(build_rows(inventory, metadata, {}))

    assert statistics[0]["level2_count"] == "2"
    assert statistics[0]["total_level2_occurrences"] == "6"
