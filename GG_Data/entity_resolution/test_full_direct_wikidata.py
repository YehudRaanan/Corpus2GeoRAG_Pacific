"""The full runner must reproduce the accepted page-pass decisions."""

import copy
import hashlib
import os
from collections import defaultdict

import pytest

import full_direct_wikidata as runner
from bilingual_page_pilot import read
from direct_wikidata_pilot import page_find
from full_direct_wikidata import HERE, assign, input_rows, page_indexes


def test_full_runner_reproduces_pilot_page_decisions():
    pilot = HERE / "runs/direct_wikidata_single_type_20261018_v2"
    rows = read(pilot / "matches.json.gz")
    metadata = read(pilot / "entity_metadata.json.gz")
    pools = read(pilot / "candidate_evidence.json.gz")["page_pools"]
    all_rows = input_rows()
    indexes = {p: page_indexes(set(ids), metadata) for p, ids in pools.items()}
    matched = 0
    for old in rows:
        row = all_rows[old["input_row_number"]]
        # The old pilot serialized extraction confidence with ten decimal places.
        assert {k: v for k, v in row["raw"].items() if k != "score"} == {
            k: v for k, v in old["raw"].items() if k != "score"
        }
        assert abs(row["raw"]["score"] - old["raw"]["score"]) < 1e-9
        assert row["mention_id"] == old["mention_id"]
        if row["raw"]["entity_group"] == "DATE":
            continue
        original, cleaned, maps = indexes[row["raw"]["Source"]]
        assign(
            row,
            page_find(original, cleaned, row["raw"]["word"], maps),
            metadata,
            "PAGE_DIRECT_WIKIDATA",
        )
        assert row["attempts"][0] == old["attempts"][0]
        matched += "assigned_id" in row
    assert matched == 263


@pytest.mark.parametrize("preloaded", [False, True])
def test_metadata_batches_reuse_cache_and_keep_unresolved_workflow(
    tmp_path, monkeypatch, preloaded
):
    """Cached metadata skips batch writes; missing page/WWII IDs still load."""
    entities = {
        qid: {
            "id": qid,
            "label": label,
            "aliases": [],
            "direct_types": types,
            "parents": [],
        }
        for qid, label, types in [
            ("Q1", "Completely different", ["Q5"]),
            ("Q2", "Target", ["Q5"]),
            ("Q5", "human", []),
        ]
    }
    rows = [
        {
            "input_row_number": 0,
            "mention_id": "mention-example",
            "raw": {"Source": "Example", "word": "Target", "entity_group": "PER"},
            "attempts": [],
        }
    ]
    monkeypatch.setattr(runner, "input_rows", lambda: copy.deepcopy(rows))
    (tmp_path / "pages").mkdir()
    page = hashlib.sha256(b"Example").hexdigest() + ".json.gz"
    runner.save(
        tmp_path / "pages" / page,
        {
            "source": "Example",
            "status": "RESOLVED",
            "articles": [{"language": "en", "qid": "Q1", "links": []}],
        },
    )
    runner.save(
        tmp_path / "candidate_evidence.json.gz",
        {"page_pools": {"Example": ["Q1"]}, "daniel_name_lookups": []},
    )
    metadata_path = tmp_path / "entity_metadata.json.gz"
    runner.save(metadata_path, entities if preloaded else {"Q5": entities["Q5"]})
    runner.save(tmp_path / "world.json.gz", {"Q2": entities["Q2"]})
    runner.save(
        tmp_path / "reference_manifest.json",
        {"world_sha256": runner.digest(tmp_path / "world.json.gz")},
    )

    class CachedData:
        requests = []

        def __init__(self):
            self.calls = []

        def entities_for(self, qids):
            self.calls.append(qids)
            self.entities.update({q: entities[q] for q in qids})

        def hierarchy(self, qids):
            assert qids <= self.entities.keys()
            assert all(
                t in self.entities
                for q in qids
                for t in self.entities[q]["direct_types"]
            )

    api = CachedData()
    summary = runner.run(tmp_path, api=api, page_workers=1)
    assert api.calls == ([] if preloaded else [{"Q1"}, {"Q2"}])
    assert read(metadata_path) == entities
    result = read(tmp_path / "matches.json.gz")[0]
    assert result["raw"] == rows[0]["raw"]
    assert result["assigned_id"] == "Q2"
    assert [a["stage"] for a in result["attempts"]] == [
        "PAGE_DIRECT_WIKIDATA",
        "ALREADY_MATCHED",
        "FRESH_WWII",
    ]
    assert summary["mentions"] == 1
    assert summary["article_name_extraction"] is False


def test_parallel_page_matching_equals_serial_and_accepted_pilot():
    pilot = HERE / "runs/direct_wikidata_single_type_20261018_v2"
    original = read(pilot / "matches.json.gz")
    metadata = read(pilot / "entity_metadata.json.gz")
    pools = {
        s: set(ids)
        for s, ids in read(pilot / "candidate_evidence.json.gz")["page_pools"].items()
    }
    by_page = defaultdict(list)
    for row in original:
        if row["raw"]["entity_group"] != "DATE":
            by_page[row["raw"]["Source"]].append(
                {
                    "input_row_number": row["input_row_number"],
                    "mention_id": row["mention_id"],
                    "raw": row["raw"],
                    "attempts": [],
                }
            )

    def collect(workers):
        results = list(
            runner.match_pages(copy.deepcopy(by_page), pools, metadata, workers)
        )
        return {r["mention_id"]: r for _, _, rows in results for r in rows}, {
            pid for _, pid, _ in results
        }

    serial, serial_pids = collect(1)
    parallel, parallel_pids = collect(2)
    assert parallel == serial
    assert serial_pids == {os.getpid()}
    assert parallel_pids and os.getpid() not in parallel_pids
    for row in original:
        if row["mention_id"] in parallel:
            assert parallel[row["mention_id"]]["attempts"][0] == row["attempts"][0]
