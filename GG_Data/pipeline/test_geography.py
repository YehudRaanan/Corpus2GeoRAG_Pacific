"""Population S2T 9.1-9.2: existing LOC identities and native date precision."""

import gzip
import json

import geopandas as gpd
import pytest
from shapely.geometry import Point

from GG_Data.pipeline.geography import prepare, selection_date, selection_value
from GG_Data.pipeline.graph_contract import load_geometry
from GG_Data.pipeline.poc import digest


def value(time, precision):
    return dict(time=time, precision=precision, source_id="saved-record")


def test_selection_date_preserves_partial_uncertainty():
    assert selection_date([], "Q1") == "1941-12-07"
    exact = value("+1942-03-04T00:00:00Z", 11)
    later = value("+1945-00-00T00:00:00Z", 9)
    assert selection_date([exact, later], "Q1") == "1942-03-04"
    outside = value("+1941-10-00T00:00:00Z", 10)
    assert selection_date([outside], "Q1") == "1941-12-07"
    assert selection_date([value("+1942-00-00T00:00:00Z", 9), exact], "Q1") == "1942"
    assert selection_date([later], "Q1") == "1945"
    assert selection_date([value("+1944-09-00T00:00:00Z", 10)], "Q1") == "1944-09"
    assert selection_value([value("+1940-00-00T00:00:00Z", 8)], "Q1") == dict(
        selection_date="1940", selection_precision=8
    )


def test_prepare_includes_separate_synthetic_locations_and_source_context(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    entities = [
        dict(
            entity_id=entity_id,
            name="Same name",
            type=kind,
            identity_status=(
                "SYNTHETIC_UNRESOLVED" if entity_id.startswith("SYN_") else "MATCHED"
            ),
            aliases=["Original alias"],
        )
        for entity_id, kind in (
            ("Q1", "LOC"),
            ("SYN_one", "LOC"),
            ("SYN_two", "LOC"),
            ("SYN_org", "ORG"),
        )
    ]
    mentions = tmp_path / "mentions.json.gz"

    def write(path, rows):
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            json.dump(rows, stream)

    write(
        mentions,
        [
            dict(
                entity_id=row["entity_id"],
                mention_id=f"m-{i}",
                word="Same name",
                entity_group=row["type"],
                Source="Source page",
                wiki_site="enwiki",
                wiki_page_id=42,
                Text="Do not extract or copy paragraph content",
            )
            for i, row in enumerate(entities)
        ],
    )
    for name, rows in (("entities", entities), ("events", []), ("relations", [])):
        write(model / f"{name}.json.gz", rows)
    manifest = dict(
        outputs={p.name: digest(p) for p in model.iterdir()},
        inputs={str(mentions): digest(mentions)},
    )
    (model / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    before = {p.name: digest(p) for p in model.iterdir()}
    output = tmp_path / "output"
    report = prepare(model, output)
    targets = json.loads((output / "targets.json").read_text(encoding="utf-8"))
    assert report["total_loc_targets"] == 3
    assert report["confirmed_place_qids"] == 1 and report["synthetic_loc_rows"] == 2
    assert {r["place_id"] for r in targets} == {"Q1", "SYN_one", "SYN_two"}
    for row in targets:
        synthetic = row["place_id"].startswith("SYN_")
        assert row["wikidata_id"] == (None if synthetic else "Q1")
        if synthetic:
            assert row["lookup_method"] == "NAME_ALIAS_CONTEXT"
            assert row["identity_status"] == "SYNTHETIC_UNRESOLVED"
        assert row["selection_date"] == "1941-12-07"
        assert row["source_context"][0]["wiki_page_id"] == 42
        assert (
            row["source_context"][0]["Text"]
            == "Do not extract or copy paragraph content"
        )
        assert "P625" in row["geographic_evidence"]
    assert before == {p.name: digest(p) for p in model.iterdir()}
    with pytest.raises(ValueError, match="already exists"):
        prepare(model, output)
    mentions.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="mentions checksum"):
        prepare(model, tmp_path / "bad-source")


def test_synthetic_geometry_round_trip_keeps_model_id(tmp_path):
    place_id = "SYN_01912ac9cc98235e83235ce0"
    geometry = Point(155.1, -6.2)
    path = tmp_path / "geography.parquet"
    gpd.GeoDataFrame(
        {"place_id": [place_id]}, geometry=[geometry], crs="EPSG:4326"
    ).to_parquet(path)
    pointer = dict(file=path.name, place_id=place_id, sha256=digest(path))
    assert load_geometry(pointer, tmp_path).equals(geometry)
    for invalid in ("SYN_", "SYN_../Q1", "not-an-id", "Q0"):
        with pytest.raises(ValueError, match="place_id"):
            load_geometry({**pointer, "place_id": invalid}, tmp_path)
