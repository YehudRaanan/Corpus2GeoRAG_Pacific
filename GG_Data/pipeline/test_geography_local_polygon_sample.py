"""Check area order, full containment and country-scope exclusion."""

from shapely.geometry import Point, box

from GG_Data.pipeline.geography_local_polygon_sample import (
    smallest_covering_polygon,
    source_local_scope,
)


def test_smallest_polygon_must_cover_all_locations_and_have_local_scope():
    rows = [
        dict(source_id="too-small", geometry=box(0, 0, 1, 1), scope="local"),
        dict(source_id="local", geometry=box(0, 0, 3, 3), scope="local"),
        dict(source_id="larger-local", geometry=box(0, 0, 4, 4), scope="local"),
        dict(source_id="country", geometry=box(0, 0, 2.5, 2.5), scope="country"),
        dict(source_id="continent", geometry=box(0, 0, 2.5, 2.5), scope="larger"),
    ]
    assert (
        smallest_covering_polygon(rows, [Point(0.5, 0.5), Point(2, 2)])["source_id"]
        == "local"
    )
    assert smallest_covering_polygon(rows[3:], [Point(0.5, 0.5)]) is None
    assert smallest_covering_polygon(rows, [Point(10, 10)]) is None
    assert smallest_covering_polygon(rows, []) is None


def test_country_and_unknown_metadata_do_not_establish_local_scope():
    row = dict(
        name="Village",
        type="administrative",
        addresstype="town",
        extratags=dict(admin_level="8"),
        address=dict(town="Village"),
    )
    assert source_local_scope(row)
    assert not source_local_scope(row | dict(addresstype="country"))
    assert not source_local_scope(row | dict(extratags=dict(admin_level="2")))
    assert not source_local_scope(row | dict(extratags=None))
