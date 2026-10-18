"""The full runner must reproduce the accepted page-pass decisions."""

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
