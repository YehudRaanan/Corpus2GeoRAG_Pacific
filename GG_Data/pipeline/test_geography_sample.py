"""Regression: old geometry source keys must never restore old entity QIDs."""

import gzip

import pytest

from GG_Data.pipeline import geography_sample
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.rebuild_poc import write


@pytest.mark.parametrize("old_source_scope", [False, True])
def test_sample_keeps_corrected_ids_and_rejects_old_source_scope(
    tmp_path, monkeypatch, old_source_scope
):
    client = geography_sample.tools()
    monkeypatch.setattr(geography_sample, "tools", lambda: client)
    monkeypatch.setattr(geography_sample, "ROOT", tmp_path)
    base = tmp_path / "rebuilt"
    original = tmp_path / "GG_Data/pipeline/outputs/poc_geography_10_sources_20261022"
    for path in (
        base / "model",
        base / "entities",
        base / "geography_sample",
        base / "geography_sources",
        original,
    ):
        path.mkdir(parents=True)
    model_file = base / "model/entities.json"
    write(model_file, [dict(entity_id="Q84", type="LOC")])
    write(
        base / "model/manifest.json",
        dict(outputs={model_file.name: digest(model_file)}),
    )
    sample = [
        dict(
            place_id="Q84",
            wikidata_id="Q84",
            name="London",
            selection_date="1942",
            previous_place_id="Q1001456",
        )
    ]
    sample += [
        dict(
            place_id=f"SYN_{i}",
            wikidata_id=None,
            name=".",
            selection_date="1941-12-07",
            previous_place_id=f"Q{i+1000}",
            source_context=[dict(subtype="LOC")],
        )
        for i in range(9)
    ]
    out = base / "geography_sample"
    write(out / "sample.json", sample)
    write(
        out / "inputs_report.json",
        dict(outputs={"sample.json": digest(out / "sample.json")}),
    )
    with gzip.open(
        base / "entities/full_records.json.gz", "wt", encoding="utf-8"
    ) as stream:
        stream.write('{"Q84":{"entity":{"descriptions":{"en":{"value":"city"}}}}}')
    source_qid = "Q1001456" if old_source_scope else "Q84"
    candidate = dict(
        type="node",
        id=123,
        lat=51.5,
        lon=-0.1,
        tags=dict(wikidata=source_qid, place="city", start_date="1800"),
    )
    for source in client.OVERPASS:
        write(
            base / f"geography_sources/first_50_{source.casefold()}.json",
            dict(
                qids=[source_qid],
                retrieved_at="2026-10-22",
                elements=[candidate] if source == "OpenHistoricalMap" else [],
            ),
        )
    write(original / "whg_results.json", dict(queries=[], results={}))
    write(
        original / "geonames_candidates.json",
        dict(
            results={
                "Q1000": [dict(fields=["raw record"], wikidata_external_id_match=True)]
            }
        ),
    )

    if old_source_scope:
        with pytest.raises(ValueError, match="superseded sample QIDs"):
            geography_sample.run(base)
        assert not (out / "geometries.parquet").exists()
    else:
        result = geography_sample.run(base)
        assert result["accepted"] == 1 and result["unresolved"] == 9
        rows = read_json(out / "geography.json")
        assert [r["place_id"] for r in rows] == ["Q84"]
        unresolved = read_json(out / "audit.json")["results"][1]
        assert unresolved["geometry_ref"] is None
        assert unresolved["geonames_record_fields"] == [["raw record"]]
        assert "wikidata_external_id_match" not in str(unresolved)
        assert (
            digest(model_file)
            == read_json(base / "model/manifest.json")["outputs"][model_file.name]
        )
