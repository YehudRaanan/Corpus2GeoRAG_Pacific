"""Owner ranking: strong source identity, real geometry distance, no road match."""

from shapely.geometry import Point, Polygon, mapping

from GG_Data.pipeline.geography_ranking_sample import distance_m, score


def test_qid_and_coordinates_dominate_names_without_counting_reverse_road():
    place = dict(name="Example", wikidata_id="Q1", selection_date="1942")
    evidence = dict(
        candidate_qids=[],
        text="Example, Region",
        source_page="Campaign",
        start=0,
        original_name="Example",
        context=dict(features=[]),
    )
    anchor = dict(qid="Q1", xy=[0, 0], role="MATCHED_INPUT")
    source = dict(
        source_id="node:1",
        qid="Q1",
        name="Example",
        aliases=["Example"],
        parents=["Region"],
        tags={},
        geometry=mapping(Point(0, 0)),
        feature_class="place",
        feature_code="village",
    )
    ranked = score(place, evidence, source, [anchor])
    assert ranked["components"] == dict(
        qid=45, coordinate=30, context=10, name=7, feature_type=0
    )
    assert ranked["total"] == 92
    wrong = score(place, evidence, source | dict(qid="Q2"), [anchor])
    assert "DIFFERENT_QID_FOR_DIRECT_PLACE" in wrong["excluded_reasons"]
    road = score(place, evidence, source | dict(feature_class="highway"), [anchor])
    assert "REVERSE_ROAD_IS_CONTEXT_NOT_TARGET" in road["excluded_reasons"]
    assert distance_m(Polygon([(-1, -1), (1, -1), (1, 1), (-1, 1)]), [0, 0]) == 0
    missing = score(place, evidence, source, [])
    assert missing["components"]["coordinate"] == 0
    assert missing["components"]["qid"] == 45
