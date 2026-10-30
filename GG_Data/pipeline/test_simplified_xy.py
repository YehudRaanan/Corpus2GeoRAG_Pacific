"""Offline arbitrary points preserve IDs, source evidence and missing values."""

import gzip
import json
import zipfile

import pytest

from GG_Data.pipeline.poc import digest, read_json


def test_loc_uses_stable_source_order_and_original_vertex_not_score():
    from GG_Data.pipeline.simplified_xy import choose_loc

    polygon = {
        "type": "Polygon",
        "coordinates": [[[10, 20], [11, 20], [10, 21], [10, 20]]],
    }
    row = {
        "ranking": [
            dict(
                source="Z",
                source_id="1",
                total=100,
                geometry_available=True,
                geometry={"type": "Point", "coordinates": [99, 20]},
            ),
            dict(
                source="A",
                source_id="2",
                total=0,
                geometry_available=True,
                geometry=polygon,
                receipt="original.json",
                uncertainty_flags=["WEAK"],
            ),
        ]
    }
    result = choose_loc(row)
    assert (result["x"], result["y"]) == (10, 20)
    assert result["coordinate_method"] == "FIRST_SOURCE_GEOMETRY_VERTEX"
    assert result["source_geometry"] == polygon
    assert result["source_object_id"] == "2"
    assert result["identity_verified"] is False
    assert result["source_uncertainty_flags"] == ["WEAK"]


def test_event_uses_statement_id_retains_multiple_and_unknown_globes():
    from GG_Data.pipeline.simplified_xy import choose_event

    def claim(identifier, x, globe="http://www.wikidata.org/entity/Q2", rank="normal"):
        return dict(
            id=identifier,
            rank=rank,
            qualifiers={"P518": [{"original": True}]},
            mainsnak=dict(
                datavalue=dict(
                    value=dict(longitude=x, latitude=20, globe=globe, precision=0.1)
                )
            ),
        )

    claims = [
        claim("z", 20),
        claim("a", 10),
        claim("0", 30, globe="unknown"),
        claim("-1", 40, rank="deprecated"),
        claim("-2", float("nan")),
    ]
    result = choose_event({"id": "Q1", "claims": {"P625": claims}})
    assert result["x"] == 10
    assert result["source_object_id"] == "a"
    assert result["valid_coordinate_alternatives"] == 2
    assert result["arbitrary_among_multiple"] is True
    assert result["native_coordinate_statements"] == claims
    assert result["chosen_statement"]["qualifiers"] == claims[1]["qualifiers"]


@pytest.mark.parametrize("xy", [[181, 0], [0, -91], [True, 1], [float("inf"), 0]])
def test_bad_point_never_becomes_an_invented_coordinate(xy):
    from GG_Data.pipeline.simplified_xy import choose_loc

    assert (
        choose_loc(
            {
                "ranking": [
                    dict(
                        source="A",
                        source_id="1",
                        geometry_available=True,
                        geometry={"type": "Point", "coordinates": xy},
                    )
                ]
            }
        )
        is None
    )


def test_complete_overlay_filters_stale_loc_ids_and_preserves_no_source(tmp_path):
    from GG_Data.pipeline.simplified_xy import build

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "wt", encoding="utf-8") as stream:
            json.dump(value, stream)

    model, ranking = tmp_path / "model", tmp_path / "ranking"
    entities = [
        dict(entity_id="ent:a", name="A", type="LOC"),
        dict(entity_id="ent:b", name="B", type="LOC"),
        dict(entity_id="ent:c", name="C", type="LOC"),
        dict(entity_id="event:Q1", name="Event", type="event"),
    ]
    write(model / "entities.json.gz", entities)
    write(
        model / "event_events.json.gz",
        [dict(entity_id="event:Q1", native_records=[dict(qid="Q1")])],
    )
    write(model / "entity_exclusions.json.gz", [dict(entity_id="ent:old")])
    write(
        model / "manifest.json",
        dict(outputs={p.name: digest(p) for p in model.iterdir()}),
    )
    results = [
        dict(input=dict(place_id=k, name=k), ranking=[])
        for k in ["ent:a", "ent:b", "ent:old"]
    ]
    results[0]["ranking"] = [
        dict(
            source="S",
            source_id="1",
            geometry_available=True,
            geometry=dict(type="Point", coordinates=[1, 2]),
        )
    ]
    write(ranking / "audit.json", dict(results=results))
    write(
        ranking / "verification.json",
        dict(
            status="VERIFIED_RANKING_PROPOSALS",
            inputs=3,
            outputs={"audit.json": digest(ranking / "audit.json")},
        ),
    )
    native = tmp_path / "native.json"
    write(native, {"Q1": {"id": "Q1", "claims": {}}})
    output = tmp_path / "out"
    report = build(model, ranking, native, output)
    rows = {r["entity_id"]: r for r in read_json(output / "xy_overlay.json.gz")}
    assert set(rows) == {r["entity_id"] for r in entities}
    assert rows["ent:a"]["geometry"] == dict(type="Point", coordinates=[1, 2])
    assert rows["ent:b"]["status"] == "NO_SOURCE_COORDINATE"
    assert rows["ent:c"]["status"] == "NO_SAVED_COORDINATE"
    assert rows["event:Q1"]["status"] == "NO_SOURCE_COORDINATE"
    assert rows["event:Q1"]["x"] is None
    assert report["excluded_cached_loc_ids"] == ["ent:old"]
    with pytest.raises(FileExistsError):
        build(model, ranking, native, output)


def test_local_exact_alias_lookup_keeps_first_row_and_distinct_native_ids(tmp_path):
    from GG_Data.pipeline.simplified_xy import exact_geonames

    def native(identifier, name, ascii_name="", aliases="", lat="20", lon="10"):
        return "\t".join([identifier, name, ascii_name, aliases, lat, lon] + [""] * 13)

    first, last = tmp_path / "AA.zip", tmp_path / "ZZ.zip"
    with zipfile.ZipFile(first, "w") as z:
        z.writestr(
            "AA.txt",
            "\n".join(
                [
                    native("9", "Harbour", aliases="ALPHA   PORT,alpha port"),
                    native("9", "Alpha Port"),
                    native("1", "Alpha Port"),
                    native("2", "Bad", lon="181"),
                    native("3", "Bad", lat="nan"),
                    "4\tBad\tmalformed",
                ]
            ),
        )
    with zipfile.ZipFile(last, "w") as z:
        z.writestr("ZZ.txt", native("0", "Alpha Port"))
    matches, report = exact_geonames({"alpha port", "bad", "absent"}, [last, first])
    assert set(matches) == {"alpha port"}
    chosen = matches["alpha port"]
    assert chosen["source_object_id"] == "9"
    assert chosen["matched_name_field"] == "alternatenames"
    assert chosen["distinct_native_candidates"] == 3
    assert chosen["source_row_number"] == 1
    assert chosen["source_archive_sha256"] == digest(first)
    assert chosen["native_row"][0] == "9"
    assert chosen["identity_verified"] is False
    assert report["invalid_matching_coordinate_rows"] == 2
    assert report["malformed_rows"] == 1


def test_local_extension_preserves_existing_points_and_binds_sources(tmp_path):
    from GG_Data.pipeline.simplified_xy import extend_local

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "wt", encoding="utf-8") as stream:
            json.dump(value, stream)

    model, prior, archives = (
        tmp_path / "model",
        tmp_path / "prior",
        tmp_path / "archives",
    )
    write(model / "manifest.json", {"stage": "fixture"})
    existing = dict(
        entity_id="ent:keep",
        type="LOC",
        name="Keep",
        geometry={"type": "Point", "coordinates": [8, 9]},
        x=8,
        y=9,
        status="SOURCE_POINT_SELECTED_ARBITRARILY",
        identity_verified=False,
    )
    missing = dict(
        entity_id="ent:fill",
        type="LOC",
        name=" Alpha   Port ",
        geometry=None,
        x=None,
        y=None,
        status="NO_SAVED_COORDINATE",
        identity_verified=False,
    )
    event = dict(
        entity_id="event:Q1",
        type="event",
        name="Event",
        geometry=None,
        x=None,
        y=None,
        status="NO_SOURCE_COORDINATE",
        identity_verified=False,
    )
    write(prior / "xy_overlay.json.gz", [existing, missing, event])
    write(
        prior / "manifest.json",
        dict(
            core_model_manifest_sha256=digest(model / "manifest.json"),
            inputs={},
            outputs={"xy_overlay.json.gz": digest(prior / "xy_overlay.json.gz")},
        ),
    )
    write(
        prior / "verification.json",
        dict(
            manifest_sha256=digest(prior / "manifest.json"),
            overlay_sha256=digest(prior / "xy_overlay.json.gz"),
        ),
    )
    archives.mkdir()
    with zipfile.ZipFile(archives / "AA.zip", "w") as z:
        z.writestr(
            "AA.txt", "\t".join(["12", "Alpha Port", "", "", "20", "10"] + [""] * 13)
        )
    output = tmp_path / "out"
    report = extend_local(prior, model, archives, output)
    rows = {r["entity_id"]: r for r in read_json(output / "xy_overlay.json.gz")}
    assert rows["ent:keep"] == existing
    assert rows["event:Q1"] == event
    assert rows["ent:fill"]["geometry"]["coordinates"] == [10, 20]
    assert report["new_loc_points"] == 1
    assert report["existing_rows_preserved"] is True
    with pytest.raises(FileExistsError):
        extend_local(prior, model, archives, output)
    write(model / "manifest.json", {"stage": "changed"})
    with pytest.raises(ValueError, match="core"):
        extend_local(prior, model, archives, tmp_path / "bad")
