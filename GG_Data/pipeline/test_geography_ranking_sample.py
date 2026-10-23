"""Owner ranking: select available geometry and keep uncertainty explicit."""

import pytest
import errno
import urllib.error
from types import SimpleNamespace
from shapely.geometry import Point, Polygon, mapping

from GG_Data.pipeline.geography_ranking_sample import (
    coordinate_candidates,
    distance_m,
    score,
    select_proposal,
    nominatim_request,
)


def test_nominatim_connection_budget_is_preserved_on_resume(tmp_path, monkeypatch):
    from GG_Data.pipeline import geography_ranking_sample as ranking

    waits, calls = [], []
    monkeypatch.setattr(ranking.time, "sleep", waits.append)

    def fail(*args, **kwargs):
        calls.append(1)
        raise urllib.error.URLError(OSError(errno.EHOSTUNREACH, "unreachable"))

    ledger = tmp_path / "attempts.json"
    client = SimpleNamespace(request_json=fail)
    with pytest.raises(urllib.error.URLError):
        nominatim_request(
            client,
            "https://example.test/reverse",
            {},
            ledger,
            prior={"file": "old-stop"},
        )
    assert len(calls) == 2  # The approved earlier failed request counts as attempt 1.
    assert waits == [10, 30]
    with pytest.raises(ValueError, match="budget exhausted"):
        nominatim_request(client, "https://example.test/reverse", {}, ledger)
    assert len(calls) == 2


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timeout"),
        urllib.error.HTTPError("url", 429, "limited", {}, None),
        ValueError("bad JSON"),
    ],
)
def test_nominatim_other_errors_stop_without_retry(tmp_path, monkeypatch, error):
    from GG_Data.pipeline import geography_ranking_sample as ranking

    waits = []
    monkeypatch.setattr(ranking.time, "sleep", waits.append)

    def fail(*args, **kwargs):
        raise error

    with pytest.raises(type(error)):
        nominatim_request(
            SimpleNamespace(request_json=fail), "url", {}, tmp_path / "attempts.json"
        )
    assert waits == []


def test_nominatim_recovers_from_connection_failure(tmp_path, monkeypatch):
    from GG_Data.pipeline import geography_ranking_sample as ranking

    waits = []
    monkeypatch.setattr(ranking.time, "sleep", waits.append)
    outcomes = iter(
        [urllib.error.URLError(ConnectionResetError("reset")), [dict(osm_id=1)]]
    )

    def request(*args, **kwargs):
        value = next(outcomes)
        if isinstance(value, Exception):
            raise value
        return value

    assert nominatim_request(
        SimpleNamespace(request_json=request), "url", {}, tmp_path / "attempts.json"
    ) == [dict(osm_id=1)]
    assert waits == [10]


def test_qid_and_coordinates_dominate_names_with_explicit_uncertainty():
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
    assert "DIFFERENT_QID_FOR_DIRECT_PLACE" in wrong["uncertainty_flags"]
    road = score(place, evidence, source | dict(feature_class="highway"), [anchor])
    assert "REVERSE_ROAD_IS_CONTEXT_NOT_TARGET" in road["uncertainty_flags"]
    assert distance_m(Polygon([(-1, -1), (1, -1), (1, 1), (-1, 1)]), [0, 0]) == 0
    missing = score(place, evidence, source, [])
    assert missing["components"]["coordinate"] == 0
    assert missing["components"]["qid"] == 45


def test_source_coordinate_context_and_always_select_available_geometry():
    place = dict(name="Historical Air Base", wikidata_id=None, selection_date="1942")
    evidence = dict(
        candidate_qids=[],
        text="Historical Air Base",
        source_page="Campaign",
        start=0,
        original_name="Historical Air Base",
        context=dict(features=[]),
        geonames_coordinate_context=[dict(source="GeoNames", source_id="1", xy=[0, 0])],
    )
    polygon = dict(
        source="OpenStreetMap",
        source_id="way:1",
        qid=None,
        name="Modern Airport",
        aliases=["Modern Airport"],
        parents=[],
        tags={},
        geometry=mapping(Polygon([(-1, -1), (1, -1), (1, 1), (-1, 1)])),
    )
    ranked = score(place, evidence, polygon, [])
    assert ranked["components"] == dict(
        qid=0, coordinate=0, context=10, name=0, feature_type=0
    )
    assert ranked["source_coordinate_context_checks"][0]["contained"]
    assert select_proposal([ranked]) == ranked
    flagged = ranked | dict(uncertainty_flags=["CONFLICT"])
    assert select_proposal([flagged]) == flagged
    point = score(place, evidence, polygon | dict(geometry=mapping(Point(0, 0))), [])
    assert point["components"]["context"] == 0  # No self-coordinate support.
    fallback = ranked | dict(total=100, coordinate_fallback=True)
    assert select_proposal([fallback, ranked]) == fallback
    zero_score = ranked | dict(total=0, uncertainty_flags=["LOW_SUPPORT"])
    assert select_proposal([zero_score]) == zero_score
    assert select_proposal([zero_score | dict(geometry_available=False)]) is None
    assert select_proposal([]) is None


def test_multiple_coordinates_keep_native_values_and_skip_deprecated():
    value = dict(
        latitude=1,
        longitude=2,
        altitude=None,
        globe="http://www.wikidata.org/entity/Q2",
    )
    statements = [
        dict(
            id=f"Q1${rank}",
            rank=rank,
            mainsnak=dict(snaktype="value", datavalue=dict(value=value)),
        )
        for rank in ("normal", "preferred", "deprecated")
    ]
    entity = dict(id="Q1", claims=dict(P625=statements))
    result = coordinate_candidates(entity)
    assert [r["statement"]["rank"] for r in result] == ["normal", "preferred"]
    assert all(r["xy"] == [2, 1] for r in result)
    assert len(entity["claims"]["P625"]) == 3
    assert coordinate_candidates(dict(id="Q2")) == []


def test_non_earth_coordinates_keep_evidence_and_other_candidates():
    def statement(globe, latitude=1):
        return dict(
            id=f"Q1${globe.rsplit('/', 1)[-1]}",
            rank="normal",
            mainsnak=dict(
                snaktype="value",
                datavalue=dict(
                    value=dict(
                        latitude=latitude, longitude=2, altitude=None, globe=globe
                    )
                ),
            ),
        )

    earth = statement("http://www.wikidata.org/entity/Q2")
    other = statement("http://www.wikidata.org/entity/Q405")
    entity = dict(id="Q1", claims=dict(P625=[other, earth]))
    unusable = []
    result = coordinate_candidates(entity, unusable=unusable)
    assert [r["xy"] for r in result] == [[2, 1]]
    assert unusable == [dict(qid="Q1", statement=other, reason="NON_EARTH_COORDINATE")]
    assert entity["claims"]["P625"] == [other, earth]
    # Only the approved non-Earth exception changes; malformed Earth data stops.
    with pytest.raises(ValueError, match="Unsupported coordinate representation"):
        coordinate_candidates(
            dict(
                id="Q1",
                claims=dict(
                    P625=[
                        statement(
                            earth["mainsnak"]["datavalue"]["value"]["globe"],
                            latitude=91,
                        )
                    ]
                ),
            )
        )
