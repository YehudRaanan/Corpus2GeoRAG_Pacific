"""Source relevance and lossless quality corrections for the new core release."""

from GG_Data.pipeline import simplified_page_events as subject


def claim(value, rank="normal"):
    return {"rank": rank, "mainsnak": {"datavalue": {"value": value}}}


def test_native_dates_preserve_all_facts_and_do_not_use_organization_inception():
    from GG_Data.pipeline.simplified_correction import native_dates

    a = dict(
        time="+1941-12-08T00:00:00Z",
        precision=11,
        calendarmodel="http://www.wikidata.org/entity/Q1985727",
    )
    b = dict(a, time="+1945-08-15T00:00:00Z")
    record = {
        "claims": {
            "P585": [claim(a), claim(b), claim(a, "deprecated")],
            "P571": [claim(a)],
        }
    }
    assert native_dates(record) == {"point_date": [a, b]}
    assert native_dates({"claims": {"P571": [claim(a)]}}) == {}


def test_quality_excludes_only_proved_invalid_keys_and_separates_native_events():
    from GG_Data.pipeline.simplified_correction import invalid_key, native_event_id

    assert invalid_key(". – &")
    assert not invalid_key("A")
    assert not invalid_key("1941")
    assert not invalid_key("O'Brien")
    assert native_event_id("Q696900") != native_event_id("Q699897")


def test_own_page_dates_use_event_infobox_and_keep_planning_separate():
    from GG_Data.pipeline.simplified_correction import wiki_event_dates

    found = wiki_event_dates("{{operational plan|date=June 1945 – September 1946}}")
    assert found["dates"]["start_date"][0]["time"] == "+1945-06-00T00:00:00Z"
    assert found["dates"]["end_date"][0]["precision"] == 10
    found = wiki_event_dates(
        "{{operational plan|planned=April 1942|date=|outcome=Abandoned}}"
    )
    assert (
        found["dates"] == {}
        and found["planned_dates"]["point_date"][0]["precision"] == 10
    )
    assert wiki_event_dates("{{Infobox website|date=1941}}")["dates"] == {}


def test_own_page_date_templates_shared_days_and_citations():
    from GG_Data.pipeline.simplified_correction import wiki_event_dates

    found = wiki_event_dates(
        "{{Infobox military conflict|date={{Start date|1944|02|29|df=y}}–{{End date|df=y|1944|05|18}}<br/>80 days<ref>{{cite book|year=1999}}</ref>}}"
    )
    assert found["dates"]["start_date"][0]["time"] == "+1944-02-29T00:00:00Z"
    assert found["dates"]["end_date"][0]["time"] == "+1944-05-18T00:00:00Z"
    assert (
        wiki_event_dates("{{Infobox event|date=7–8 December 1941}}")["dates"][
            "end_date"
        ][0]["time"]
        == "+1941-12-08T00:00:00Z"
    )
    assert wiki_event_dates("{{Infobox event|date=Every 7 December}}")["dates"] == {}


def test_corrected_population_separates_same_name_native_events():
    records = {
        q: dict(id=q, label="Battle of Guam", direct_types=["Q178561"])
        for q in ["Q696900", "Q699897"]
    }
    page = dict(
        page_index=0,
        source_subject_qid=None,
        title="Source",
        revision_id=10,
        status="AVAILABLE",
        evidence="source",
        links=["Guam 1941", "Guam 1944"],
    )
    result = subject.event_population(
        [page],
        {"Guam 1941": "Q699897", "Guam 1944": "Q696900"},
        records,
        {"Q178561"},
        native_identity=True,
    )
    assert len(result["entities"]) == 2
    assert {r["entity_id"] for r in result["entities"]} == {
        "event:Q699897",
        "event:Q696900",
    }


def test_source_links_keep_body_and_infobox_but_exclude_reference_support():
    raw = """{{Infobox military conflict|partof=[[Campaign]]}}
The [[Battle]] was important.<ref>{{cite book|title=[[Unrelated event]]}}</ref>
== References ==
* [[Reference-only event]]
== External links ==
* [[External-only event]]
"""
    found = subject.content_links(raw)
    kept = {r["target_title"] for r in found if r["status"] != "EXCLUDE"}
    assert kept == {"Campaign", "Battle"}
    assert all(raw[r["anchor_start"] : r["anchor_end"]] for r in found)
    assert (
        next(r for r in found if r["target_title"] == "Battle")["reason"]
        == "article_text"
    )


def test_source_repeated_link_retains_body_evidence_after_citation_exclusion():
    raw = "[[Battle]] is relevant.\n== References ==\n[[Battle]]"
    found = subject.content_links(raw)
    assert [(r["target_title"], r["status"]) for r in found] == [
        ("Battle", "KEEP"),
        ("Battle", "EXCLUDE"),
    ]


def test_spaceflight_dates_use_launch_and_landing_not_publication():
    from GG_Data.pipeline.simplified_correction import native_dates

    a = dict(
        time="+1969-07-16T00:00:00Z",
        precision=11,
        calendarmodel="http://www.wikidata.org/entity/Q1985727",
    )
    b = dict(a, time="+1969-07-24T00:00:00Z")
    assert native_dates(
        {"claims": {"P619": [claim(a)], "P620": [claim(b)], "P577": [claim(a)]}}
    ) == {"start_date": [a], "end_date": [b]}


def test_compound_template_and_independent_periods_and_recurring_series():
    from GG_Data.pipeline.simplified_correction import wiki_event_dates

    found = wiki_event_dates(
        "{{Infobox military conflict|date={{Start and end dates|1965|11|3|1965|11|4}}}}"
    )
    assert found["dates"]["end_date"][0]["time"] == "+1965-11-04T00:00:00Z"
    found = wiki_event_dates(
        "{{Infobox event|date=June 9–11, 2004 (funeral)<br/>June 5–July 3, 2004 (mourning)}}"
    )
    assert len(found["dates"]["periods"]) == 2
    assert not wiki_event_dates(
        "{{Infobox recurring event|date=7 December|begins=1941}}"
    )["concrete_event_infobox"]


def test_multiline_operation_and_concrete_event_facet_take_precedence():
    from GG_Data.pipeline.simplified_correction import classify_event, wiki_event_dates

    own = wiki_event_dates("{{operational plan\n|planned=April 1942\n|date=}}")
    assert own["concrete_event_infobox"] and own["planned_dates"]
    assert (
        classify_event(
            dict(native_types=["Q645883"], parents=["Q1"], dates={}),
            own,
            {},
            {"Q645883"},
        )["status"]
        == "EVENT"
    )
    fact = dict(native_types=["Q109473326", "Q188686"], dates={"point_date": [{}]})
    assert classify_event(fact, {}, {}, {"Q188686"})["status"] == "EVENT"
    assert (
        classify_event(dict(native_types=["Q3028081"]), {}, {}, {"Q3028081"})["status"]
        == "NON_EVENT"
    )
    assert (
        classify_event(dict(native_types=["Q1190554"]), {}, {}, {"Q1190554"})["status"]
        == "REVIEW_EVENT_IDENTITY"
    )


def test_quality_filter_preserves_raw_population_accountability():
    from GG_Data.pipeline.simplified_correction import correct_population

    entities = [
        dict(entity_id="good", name="A", type="PER"),
        dict(entity_id="bad", name=".", type="ORG"),
    ]
    memberships = [dict(entity_id=e["entity_id"], page_index=0) for e in entities]
    page = dict(page_index=0, wiki_page_id=1)
    result, exclusions = correct_population(
        entities, memberships, [page], dict(entities=[], memberships=[])
    )
    assert [e["entity_id"] for e in result["entities"]] == ["good"]
    assert exclusions == [dict(entities[1], reason="NO_UNICODE_ALPHANUMERIC")]


def test_known_event_infobox_variants_and_season_year():
    from GG_Data.pipeline.simplified_correction import wiki_event_dates

    for template in [
        "Infobox nuclear weapons test",
        "Infobox military operation",
        "infobox civilian attack",
        "Infobox summit meeting",
    ]:
        assert (
            wiki_event_dates("{{" + template + "|date=7 December 1941}}")["dates"][
                "point_date"
            ][0]["precision"]
            == 11
        )
    season = wiki_event_dates("{{Infobox NFL team season|year=1941}}")
    assert season["dates"]["point_date"][0]["time"] == "+1941-00-00T00:00:00Z"
    raw = "{{Infobox former country|year_start=1942|year_end=1945}}"
    assert not wiki_event_dates(raw)["dates"]
    assert (
        wiki_event_dates(raw, occupation=True)["dates"]["start_date"][0]["precision"]
        == 9
    )


def test_undated_war_operation_and_untyped_own_event_evidence():
    from GG_Data.pipeline.simplified_correction import classify_event

    fact = dict(native_types=["Q645883"], dates={})
    assert (
        classify_event(fact, {}, {}, {"Q645883"}, war_connection=True)["status"]
        == "EVENT"
    )
    assert (
        classify_event(
            dict(fact, parents=["Q1"]), {}, {}, {"Q645883"}, war_connection=True
        )["status"]
        == "REVIEW_EVENT_IDENTITY"
    )
    own = dict(concrete_event_infobox=True, source=dict(status="AVAILABLE"))
    decision = classify_event(dict(native_types=[]), own, {}, set())
    assert decision["status"] == "EVENT" and decision["recognized_types"] == []
    assert decision["reason"] == "OWN_EVENT_INFOBOX_NO_NATIVE_TYPE"


def test_shared_month_ranges_date_range_template_and_planned_date_role():
    from GG_Data.pipeline.simplified_correction import wiki_event_dates

    actual = wiki_event_dates(
        "{{Infobox military conflict|date={{Date range and age in years, months, weeks and days|1944|11|15|1944|11|30}}}}"
    )
    assert actual["dates"]["start_date"][0]["time"] == "+1944-11-15T00:00:00Z"
    planned = wiki_event_dates(
        "{{Infobox military operation|date=Planned invasion: February–March 1945}}"
    )
    assert not planned["dates"]
    assert planned["planned_dates"]["start_date"][0]["time"] == "+1945-02-00T00:00:00Z"
    assert planned["planned_dates"]["end_date"][0]["time"] == "+1945-03-00T00:00:00Z"


def test_war_scope_requires_connection_and_does_not_turn_theaters_into_events():
    from GG_Data.pipeline.simplified_correction import classify_event, scoped_decision

    fact = dict(native_types=["Q718893", "Q645883"], dates={})
    assert (
        classify_event(
            fact,
            dict(concrete_event_infobox=True),
            {},
            {"Q718893", "Q645883"},
            war_connection=True,
        )["status"]
        == "NON_EVENT"
    )
    event = dict(native_types=["Q645883"], dates={})
    assert (
        scoped_decision("Q1", event, {}, {}, {"Q645883"}, {})["status"]
        == "EXCLUDED_NO_PROVEN_WWII_CONNECTION"
    )
    path = [dict(**{"from": "Q1", "to": "Q362"}, property="P361")]
    assert (
        scoped_decision("Q1", event, {}, {}, {"Q645883"}, {"Q1": path})[
            "war_connection"
        ]
        == path
    )


def test_proved_fragment_keys_are_excluded_without_dropping_short_names():
    from GG_Data.pipeline.simplified_correction import invalid_key, invalid_reason

    for name in ["The", "the", "and", "of", "Battle of"]:
        assert (
            invalid_key(name)
            and invalid_reason(name) == "PROVED_INCOMPLETE_NER_FRAGMENT"
        )
    for name in ["A", "USS", "I", "The Sullivans", "Battle of Guam"]:
        assert not invalid_key(name)


def test_cancelled_operation_dates_do_not_assert_actual_execution():
    from GG_Data.pipeline.simplified_correction import event_date_payload

    native = {
        "point_date": [
            dict(
                time="+1945-11-01T00:00:00Z",
                precision=11,
                calendarmodel="http://www.wikidata.org/entity/Q1985727",
            )
        ]
    }
    found = event_date_payload(native, {}, cancelled=True)
    assert not found["event_dates"] and found["planned_dates"] == native
    assert found["date_status"] == "PLANNED_ONLY"
    normalized = event_date_payload(native, {}, cancelled=True, owner_policy=True)
    assert normalized["date_normalization"]["date_role"] == "PLANNED"
    assert (
        normalized["event_dates"]["start_date"] == normalized["event_dates"]["end_date"]
    )
    assert normalized["date_sources"]["selected_before_normalization"] == {}


def test_own_explicit_event_period_takes_priority_over_conflicting_native_year():
    from GG_Data.pipeline.simplified_correction import (
        event_date_payload,
        wiki_event_dates,
    )

    own = wiki_event_dates("{{Infobox event|date=17 July – 2 August 1945}}")
    assert own["dates"]["start_date"][0]["time"] == "+1945-07-17T00:00:00Z"
    native = {"point_date": [dict(time="+1939-00-00T00:00:00Z", precision=9)]}
    payload = event_date_payload(native, own)
    assert payload["event_dates"] == own["dates"]
    assert payload["date_sources"]["native"] == native


def test_owner_date_defaults_missing_single_month_year_and_independent_points():
    from GG_Data.pipeline.simplified_correction import normalize_event_dates

    def value(time, precision=11):
        return dict(
            time=time + "T00:00:00Z",
            precision=precision,
            calendarmodel="http://www.wikidata.org/entity/Q1985727",
        )

    empty, meta = normalize_event_dates({})
    assert empty["start_date"][0]["time"] == "+1939-09-01T00:00:00Z"
    assert empty["end_date"][0]["time"] == "+1945-09-02T00:00:00Z"
    assert meta["basis"] == "OWNER_WWII_DEFAULT"
    for date in [
        value("+1942-00-00", 9),
        value("+1942-01-00", 10),
        value("+1942-01-01"),
    ]:
        for field in ["point_date", "start_date", "end_date"]:
            normalized, meta = normalize_event_dates({field: [date]})
            assert normalized["start_date"] == normalized["end_date"]
            assert normalized["start_date"][0]["time"] == "+1942-01-01T00:00:00Z"
            assert normalized["start_date"][0]["precision"] == 11
            assert date["precision"] in {9, 10, 11}  # Input evidence is unchanged.
    dates = {"point_date": [value("+1941-12-08"), value("+1944-07-21")]}
    normalized, _ = normalize_event_dates(dates)
    assert len(normalized["periods"]) == 2
    assert all(p["start_date"] == p["end_date"] for p in normalized["periods"])


def test_invalid_source_day_is_preserved_but_not_exported_as_a_usable_date():
    from GG_Data.pipeline.simplified_correction import event_date_payload

    value = dict(
        time="+1943-06-31T00:00:00Z",
        precision=11,
        calendarmodel="http://www.wikidata.org/entity/Q1985727",
    )
    payload = event_date_payload({"point_date": [value]}, {}, owner_policy=True)
    assert payload["event_dates"]["start_date"][0]["time"] == "+1939-09-01T00:00:00Z"
    assert payload["date_normalization"]["date_role"] == "OWNER_DEFAULT"
    assert (
        payload["date_normalization"]["invalid_source_dates"][0]["reason"]
        == "INVALID_SOURCE_DATE"
    )
    assert payload["date_sources"]["native"]["point_date"] == [value]
    # Month precision has no day assertion: the requested first-day rule applies.
    month = event_date_payload(
        {"point_date": [dict(value, precision=10)]}, {}, owner_policy=True
    )
    assert month["event_dates"]["start_date"][0]["time"] == "+1943-06-01T00:00:00Z"
    valid = dict(value, time="+1943-06-30T00:00:00Z")
    mixed = event_date_payload({"point_date": [value, valid]}, {}, owner_policy=True)
    assert (
        mixed["event_dates"]["start_date"]
        == mixed["event_dates"]["end_date"]
        == [dict(valid, before=0, after=0)]
    )
