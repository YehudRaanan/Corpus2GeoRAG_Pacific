"""Measurement selection includes candidates without making assignments."""

import hashlib

import pandas as pd

import collect_matching_relevance as collector
from bilingual_page_pilot import digest, read
from full_direct_wikidata import save


def test_page_and_world_candidates_are_measured_without_global_page_injection(
    tmp_path, monkeypatch
):
    source, output = tmp_path / "source", tmp_path / "selected"
    (source / "pages").mkdir(parents=True)
    data = tmp_path / "input.parquet"
    pd.DataFrame(
        [
            dict(Source="Page", word="Alpha", entity_group="LOC"),
            dict(Source="Page", word="Beta", entity_group="LOC"),
            dict(Source="Page", word="1942", entity_group="DATE"),
        ]
    ).to_parquet(data)
    metadata = {
        q: dict(label=name, aliases=[], direct_types=[])
        for q, name in (("Q1", "Alpha"), ("Q2", "Beta"), ("Q3", "Zebra"))
    }
    save(source / "entity_metadata.json.gz", metadata)
    save(source / "world.json.gz", {"Q2": metadata["Q2"]})
    page = source / "pages" / (hashlib.sha256(b"Page").hexdigest() + ".json.gz")
    save(page, dict(articles=[dict(qid="Q1", links=[dict(qid="Q3")])]))
    save(
        source / "manifest.json",
        dict(
            outputs={
                n: digest(source / n)
                for n in ("entity_metadata.json.gz", "world.json.gz")
            },
            page_evidence={page.name: digest(page)},
        ),
    )
    monkeypatch.setattr(collector, "INPUT", data)
    monkeypatch.setattr(collector, "INPUT_SHA256", digest(data))
    result = collector.collect(source, output)
    assert result["page_candidate_qids"] == 1
    assert not result["identity_assignments_made"]
    assert {r["qid"] for r in read(output / "selection.json")} == {"Q1", "Q2"}
