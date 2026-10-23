"""Offline checks for the approved OSM BigQuery retrieval adapter."""

import json

import pytest
from shapely.geometry import Point, shape

from GG_Data.pipeline.osm_bigquery import TABLE, load, project
from GG_Data.pipeline.poc import digest


@pytest.mark.parametrize(
    "layer,way,expected",
    [
        ("points", None, "node:12"),
        ("lines", None, "way:12"),
        ("multipolygons", "34", "way:34"),
        ("multipolygons", None, "relation:12"),
        ("multilinestrings", None, "relation:12"),
        ("other_relations", None, "relation:12"),
    ],
)
def test_native_object_ids_and_geometry_are_preserved(layer, way, expected):
    point = Point(35, 32)
    row = dict(
        feature_type=layer,
        osm_id="12",
        osm_way_id=way,
        geometry_wkb=point.wkb_hex,
        all_tags=[
            dict(key="wikidata", value="Q84"),
            dict(key="name", value="London"),
            dict(key="old_name", value="Historical name"),
        ],
    )
    candidate = project(row, {"Q84"}, "receipt")
    assert candidate["source_id"] == expected
    assert candidate["qid"] == "Q84"
    assert shape(candidate["geometry"]).equals_exact(point, 0)
    assert "Historical name" in candidate["aliases"]
    assert candidate["feature_code"] is None  # No invented classification.
    with pytest.raises(ValueError, match="out-of-scope"):
        project(row, {"Q1"}, "receipt")
    with pytest.raises(ValueError, match="Unknown native"):
        project(row | {"feature_type": "new_layer"}, {"Q84"}, "receipt")


def test_cache_reuse_checks_targets_and_source_receipts(tmp_path):
    raw = tmp_path / "raw"
    raw.write_text("source", encoding="utf-8")
    path = tmp_path / "normalized.json"
    path.write_text(
        json.dumps(
            dict(
                qids=["Q84"],
                candidates=[dict(qid="Q84")],
                inputs={str(raw): digest(raw)},
            )
        ),
        encoding="utf-8",
    )
    assert load(path, ["Q84", "Q84"]) == [dict(qid="Q84")]
    with pytest.raises(ValueError, match="different targets"):
        load(path, ["Q1"])
    raw.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Changed"):
        load(path, ["Q84"])


def test_bq_custom_table_snapshot_cannot_be_reused_for_another_table(
    tmp_path, monkeypatch
):
    import sys
    from GG_Data.pipeline.poc import ROOT

    sys.path.insert(0, str(ROOT / "GG_Data/entity_resolution"))
    try:
        from bigquery_direct_wikidata import BigQueryData
    finally:
        sys.path.pop(0)
    monkeypatch.setattr("bigquery_direct_wikidata.shutil.which", lambda _: "bq.cmd")
    monkeypatch.setattr(
        BigQueryData, "cli", lambda *a: json.dumps(dict(id=TABLE.replace(".", ":", 1)))
    )
    client = BigQueryData("geo-hagai-ndvi", tmp_path, table=TABLE)
    assert TABLE in client.source
    with pytest.raises(ValueError, match="different table"):
        BigQueryData("geo-hagai-ndvi", tmp_path)
