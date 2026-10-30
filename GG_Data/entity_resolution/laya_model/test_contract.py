"""Small joint-decision contract checks; no weights or network required."""

from copy import deepcopy

import pytest

from GG_Data.entity_resolution.laya_model.model import (
    STOP_KEY,
    STOP_TEXT,
    choose_remaining,
    make_question,
    partition_record,
    partition_removal_states,
    strict_items_from_rows,
)


def record(n=3, positives=("c0", "c2")):
    return {
        "id": "fixture",
        "entity": {"id": "Q99999", "name": "Alice", "context": "Alice arrived."},
        "candidates": [
            {"id": f"c{i}", "name": "Alice", "context": f"distinct evidence {i}"}
            for i in range(n)
        ],
        "positive_ids": list(positives),
    }


@pytest.mark.parametrize("direction", ["forward", "reverse"])
def test_stop_and_multi_positive_identity(direction):
    row = make_question(record(), direction)
    criteria = row["questions"]["match"]["criteria"]
    assert criteria[STOP_KEY] == STOP_TEXT[direction]
    assert "Q99999" not in row["state"]
    ids = row["metadata"]["option_ids"]
    assert set(ids.values()) == {"c0", "c1", "c2", None}
    gold = row["gold"]["match"]["probabilities"]
    assert {ids[k] for k, p in gold.items() if p} == {"c0", "c2"}
    assert sorted(gold.values()) == [0, 0, 0.5, 0.5]


def test_keys_survive_reordering_and_duplicate_names():
    first = record()
    other = deepcopy(first)
    other["candidates"].reverse()
    a, b = make_question(first, "forward"), make_question(other, "forward")
    assert a["metadata"]["option_ids"] == b["metadata"]["option_ids"]
    assert len(a["questions"]["match"]["criteria"]) == 4


@pytest.mark.parametrize("bad", ["missing", "duplicate", "zero_mass", "wrong_mass"])
def test_invalid_records_fail(bad):
    row = record()
    if bad == "missing":
        row["positive_ids"].append("absent")
    elif bad == "duplicate":
        row["candidates"][1]["id"] = "c0"
    else:
        row["target_probabilities"] = (
            [0, 0, 0, 0] if bad == "zero_mass" else [1, 0, 0, 0]
        )
    with pytest.raises(ValueError):
        make_question(row, "forward")


def test_unlabelled_inference_has_no_gold():
    row = record()
    del row["positive_ids"]
    assert "gold" not in make_question(row, "reverse")


@pytest.fixture(scope="module")
def tokenizer():
    import sys
    from pathlib import Path

    base = Path(__file__).resolve().parents[3] / "Data/external/laya_pilot_20261030"
    source, path = base / "upstream", base / "tokenizer/tokenizer"
    if not source.exists() or not path.exists():
        pytest.skip("pinned upstream/tokenizer not available; no network in tests")
    sys.path.insert(0, str(source))
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(path, local_files_only=True)


@pytest.mark.parametrize("n", [5, 10, 15, 20])
def test_partition_retains_all_options_and_gold(tokenizer, n):
    raw = record(n, ("c0", f"c{n-1}"))
    chunks = partition_record(
        raw, "forward", tokenizer=tokenizer, max_len=512, head_max_len=192
    )
    assert [c["id"] for chunk in chunks for c in chunk["candidates"]] == [
        c["id"] for c in raw["candidates"]
    ]
    assert set().union(*(set(c["positive_ids"]) for c in chunks)) == set(
        raw["positive_ids"]
    )
    rows = [make_question(c, "forward") for c in chunks]
    assert len(strict_items_from_rows(tokenizer, rows, 512, 192)) == len(chunks)


def test_context_shortening_is_explicit_and_original_unchanged(tokenizer):
    raw = record(1, ("c0",))
    raw["entity"]["context"] = "long contextual evidence " * 1000
    raw["candidates"][0]["context"] = "other context " * 1000
    original = deepcopy(raw)
    chunks = partition_record(
        raw, "forward", tokenizer=tokenizer, max_len=512, head_max_len=192
    )
    assert chunks[0]["context_shortening"]
    assert raw == original
    assert (
        len(
            strict_items_from_rows(
                tokenizer, [make_question(chunks[0], "forward")], 512, 192
            )
        )
        == 1
    )


def test_long_name_is_rejected_instead_of_silently_cut(tokenizer):
    raw = record(1, ("c0",))
    raw["candidates"][0]["name"] = "Very Long Entity Name " * 100
    with pytest.raises(ValueError, match="fit|option"):
        partition_record(raw, "forward", tokenizer=tokenizer)


def test_removal_rescores_and_chunk_stop_is_local(tokenizer):
    class Agent:
        tok = tokenizer

        def __init__(self):
            self.calls = []

        def system_one(self, state, questions, **kwargs):
            assert "gold" not in questions
            keys = list(questions["match"]["criteria"])
            self.calls.append(keys)
            choice = keys[0] if len(self.calls) == 1 else STOP_KEY
            return {
                "answers": {
                    "match": {
                        "choice": choice,
                        "probabilities": {k: float(k == choice) for k in keys},
                    }
                },
                "usage": {},
            }

    agent = Agent()
    traces = choose_remaining(agent, record(), "forward", max_options=2)
    assert [t["candidate_id"] for t in traces] == ["c0", None, None]
    assert [t["chunk_index"] for t in traces] == [0, 0, 1]
    assert len(agent.calls[1]) == len(agent.calls[0]) - 1
    assert traces[-1]["coverage"]["presented_candidate_count"] == 3


def test_empty_pool_is_one_stop_decision(tokenizer):
    raw = record(0, ())
    chunks = partition_record(raw, "reverse", tokenizer=tokenizer)
    assert len(chunks) == 1
    row = make_question(chunks[0], "reverse")
    assert row["gold"]["match"]["probabilities"] == {STOP_KEY: 1.0}


def test_strict_training_rejects_zero_gold(tokenizer):
    row = make_question(record(), "forward")
    row["gold"]["match"]["probabilities"] = {
        k: 0 for k in row["gold"]["match"]["probabilities"]
    }
    with pytest.raises(ValueError, match="gold"):
        strict_items_from_rows(tokenizer, [row], 512, 192)


def test_removed_positive_is_not_reported_as_retrieval_miss(tokenizer):
    raw = record(1, ("c0",))
    raw.update(
        full_positive_ids=["c0", "already_removed", "outside_pool"],
        removed_ids=["already_removed"],
    )
    chunks = partition_record(raw, "forward", tokenizer=tokenizer)
    assert chunks[0]["retrieval_missing_positive_ids"] == ["outside_pool"]


def test_runtime_unknown_choice_fails(tokenizer):
    class Agent:
        tok = tokenizer

        def system_one(self, *args, **kwargs):
            return {
                "answers": {
                    "match": {"choice": "invented", "probabilities": {"invented": 1}}
                }
            }

    with pytest.raises(ValueError, match="runtime"):
        choose_remaining(Agent(), record(), "forward")


def test_training_removals_keep_initial_chunks(tokenizer):
    initial = record(5, ("c0", "c2"))
    initial.update(base_id="base", removal_index=0, direction="forward")
    later = deepcopy(initial)
    later.update(id="later", removal_index=1, positive_ids=["c2"], removed_ids=["c0"])
    later["candidates"] = later["candidates"][1:]
    chunks = partition_removal_states(
        [initial, later], tokenizer=tokenizer, max_options=2
    )
    first = chunks[:3]
    second = chunks[3:]
    assert [[c["id"] for c in chunk["candidates"]] for chunk in first] == [
        ["c0", "c1"],
        ["c2", "c3"],
        ["c4"],
    ]
    assert [[c["id"] for c in chunk["candidates"]] for chunk in second] == [
        ["c1"],
        ["c2", "c3"],
        ["c4"],
    ]
    assert [chunk["positive_ids"] for chunk in second] == [[], ["c2"], []]
    assert all(chunk["entity"] == initial["entity"] for chunk in chunks)
    original_context = {c["id"]: c["context"] for c in initial["candidates"]}
    assert all(
        c["context"] == original_context[c["id"]]
        for chunk in chunks
        for c in chunk["candidates"]
    )


def test_removal_evidence_drift_is_rejected(tokenizer):
    initial = record(1, ("c0",))
    initial.update(base_id="base", removal_index=0, direction="forward")
    later = deepcopy(initial)
    later.update(id="later", removal_index=1)
    later["candidates"][0]["context"] = "silently changed evidence"
    with pytest.raises(ValueError, match="evidence"):
        partition_removal_states([initial, later], tokenizer=tokenizer)
