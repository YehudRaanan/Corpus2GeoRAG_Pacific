"""Coordinate fallback retains original positions and source priority."""

import pytest
from shapely.geometry import Point

from GG_Data.pipeline.geography_coordinate_sample import coordinate, fallback_point


def test_candidate_point_fallback_preserves_xy_and_existing_geometry():
    evidence = dict(xy=[145.62444444444444, 14.96861111111111])
    assert fallback_point(evidence, has_geometry=False).equals_exact(
        Point(*evidence["xy"]), 0
    )
    assert fallback_point(evidence, has_geometry=True) is None
    assert fallback_point(None, has_geometry=False) is None


def test_coordinate_conflicts_and_wrong_globes_stop():
    claim = dict(
        rank="normal",
        mainsnak=dict(
            snaktype="value",
            datavalue=dict(
                value=dict(
                    longitude=1,
                    latitude=2,
                    globe="http://www.wikidata.org/entity/Q2",
                    altitude=None,
                )
            ),
        ),
    )
    entity = dict(id="Q1", claims=dict(P625=[claim]))
    assert coordinate(entity)["xy"] == [1, 2]
    with pytest.raises(ValueError, match="need review"):
        coordinate(entity | dict(claims=dict(P625=[claim, claim])))
    claim["mainsnak"]["datavalue"]["value"]["globe"] = "Mars"
    with pytest.raises(ValueError, match="representation"):
        coordinate(entity)
