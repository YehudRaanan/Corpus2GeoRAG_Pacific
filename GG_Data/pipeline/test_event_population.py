"""Completed-job recovery must not silently reuse another or partial query."""

import gzip
import hashlib
import json

import pytest

from GG_Data.pipeline import event_population


@pytest.mark.parametrize("problem", [None, "sql", "truncated", "job", "duplicate"])
def test_completed_partition_recovery(tmp_path, monkeypatch, problem):
    sql = "SELECT approved_snapshot_and_scope"
    key = hashlib.sha256(sql.encode()).hexdigest()
    query = tmp_path / "query.sql"
    query.write_text(sql, encoding="utf-8")
    saved = dict(
        sql_sha256=key,
        job_id="geoai_" + key[:32],
        recovered_from_completed_job=True,
        result_table_rows=2,
        rows=[dict(qid="Q1"), dict(qid="Q2")],
    )
    if problem == "truncated":
        saved["result_table_rows"] = 3
    if problem == "job":
        saved["job_id"] = "unrelated"
    if problem == "duplicate":
        saved["rows"][1]["qid"] = "Q1"
    cache = tmp_path / (key + ".json.gz")
    with gzip.open(cache, "wt", encoding="utf-8") as stream:
        json.dump(saved, stream)
    monkeypatch.setattr(event_population, "STORE", tmp_path)
    if problem is None:
        recovered, path = event_population.recovered_partition(query, sql)
        assert recovered == saved
        assert path == cache
    else:
        with pytest.raises(ValueError, match="Recovered"):
            event_population.recovered_partition(
                query, "different scope" if problem == "sql" else sql
            )
