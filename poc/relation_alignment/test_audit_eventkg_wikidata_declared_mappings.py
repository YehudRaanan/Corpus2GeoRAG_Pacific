from audit_eventkg_wikidata_declared_mappings import classify_predicates, normalize_uri


def source(predicate: str, count: str = "3") -> dict[str, str]:
    return {
        "source_predicate": predicate,
        "source_label": predicate.rsplit("/", 1)[-1],
        "source_occurrence_count": count,
    }


def candidate(predicate: str, target: str, relation: str) -> dict[str, str]:
    return {
        "eventkg_predicate": predicate,
        "wikidata_property": target,
        "mapping_relation": relation,
    }


def test_normalize_uri_treats_http_and_https_as_the_same_external_term() -> None:
    assert normalize_uri("https://schema.org/creator/") == "http://schema.org/creator"


def test_exact_conflict_is_not_accepted_as_one_mapping() -> None:
    predicate = "http://dbpedia.org/ontology/voice"
    rows = classify_predicates(
        [source(predicate)],
        [
            candidate(predicate, "P725", "EXACT"),
            candidate(predicate, "P990", "EXACT_CHAIN"),
        ],
    )

    assert rows[0]["audit_status"] == "DECLARED_EXACT_CONFLICT"
    assert rows[0]["exact_wikidata_options"] == "P725|P990"


def test_group_and_broader_options_stay_separate() -> None:
    predicate = "http://schema.org/containedInPlace"
    rows = classify_predicates(
        [source(predicate)],
        [
            candidate(predicate, "P131", "EVENTKG_NORMALIZATION_OPTION"),
            candidate(predicate, "P131", "EVENTKG_BROADER_THAN_WIKIDATA"),
        ],
    )

    assert rows[0]["audit_status"] == "NORMALIZED_MULTI_OPTION"
    assert rows[0]["normalization_options"] == "P131"
    assert rows[0]["broader_narrower_options"] == "P131"
