"""Small CPU checks for the frozen-to-full transition and resource boundary."""

import json
import time
from types import SimpleNamespace

import pytest
import torch

from GG_Data.entity_resolution.laya_model.train import (
    BudgetStop,
    RunGuard,
    freeze_encoder,
    save_model,
    select_records,
    validation,
    validate_split_pages,
    validation_metrics,
)


def test_freeze_then_unfreeze_changes_encoder_only_after_warmup():
    model = torch.nn.Module()
    model.encoder = torch.nn.Linear(2, 2)
    model.head = torch.nn.Linear(2, 1)
    before = model.encoder.weight.detach().clone()
    freeze_encoder(model, True)
    assert not model.encoder.training
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
    optimizer.zero_grad()
    model.head(model.encoder(torch.ones(1, 2))).sum().backward()
    optimizer.step()
    assert model.encoder.weight.grad is None
    assert torch.equal(before, model.encoder.weight)
    freeze_encoder(model, False)
    optimizer.zero_grad()
    model.head(model.encoder(torch.ones(1, 2))).sum().backward()
    optimizer.step()
    assert model.encoder.weight.grad is not None
    assert not torch.equal(before, model.encoder.weight)


def test_guard_stops_before_next_forward_and_on_stop_file(tmp_path):
    guard = RunGuard(time.monotonic() - 1, tmp_path / "STOP")
    with pytest.raises(BudgetStop, match="deadline"):
        guard.check()
    guard = RunGuard(time.monotonic() + 60, tmp_path / "STOP")
    guard.check()
    guard.stop_file.touch()
    with pytest.raises(BudgetStop, match="STOP"):
        guard.check()


def test_page_split_guard_rejects_cross_split_sources():
    rows = {
        "train": [{"source_page_id": 1, "id": "a"}],
        "validation": [{"source_page_id": 2, "id": "b"}],
    }
    validate_split_pages(rows)
    rows["calibration"] = [{"source_page_id": 1, "id": "c"}]
    with pytest.raises(ValueError, match="overlap"):
        validate_split_pages(rows)


def test_budget_subset_keeps_complete_base_states_and_both_directions(tmp_path):
    path = tmp_path / "train.jsonl"
    rows = [
        {
            "id": f"{direction}:{base}:{state}",
            "base_id": str(base),
            "direction": direction,
            "removal_index": state,
            "source_page_id": 1,
        }
        for direction in ("forward", "reverse")
        for base in range(4)
        for state in range(3)
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    selected, receipt = select_records(path, 2)
    assert len(selected) == 12
    assert receipt["available_states"] == 24
    for direction, base in receipt["base_keys"]:
        assert {
            row["removal_index"]
            for row in selected
            if (row["direction"], row["base_id"]) == (direction, base)
        } == {0, 1, 2}
    assert select_records(path, 2)[0] == selected


def test_upstream_joint_head_trains_with_frozen_encoder_then_updates_encoder():
    """Exercise the actual joint head, including its frozen-input checkpoint path."""
    from laya.common import DecisionModel

    class Encoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.config = SimpleNamespace(hidden_size=64)
            self.embedding = torch.nn.Embedding(16, 64)

        def forward(self, input_ids, attention_mask):
            return SimpleNamespace(last_hidden_state=self.embedding(input_ids))

    model = DecisionModel(Encoder(), head_layers=2, dropout=0)
    model.head_checkpointing = True
    inputs = (
        torch.tensor([[1, 2, 3, 4]]),
        torch.ones(1, 4, dtype=torch.long),
        torch.tensor([[1, 3]]),
        torch.tensor([[True, True]]),
        torch.tensor([0]),
    )
    original_encoder = model.encoder.embedding.weight.detach().clone()
    original_head = model.scorer[-1].weight.detach().clone()
    for frozen in (True, False):
        freeze_encoder(model, frozen)
        optimizer = torch.optim.AdamW(
            [p for p in model.parameters() if p.requires_grad], lr=0.01
        )
        logits, _ = model(*inputs, detach_encoder=frozen)
        torch.nn.functional.cross_entropy(logits, torch.tensor([0])).backward()
        optimizer.step()
        if frozen:
            assert model.encoder.embedding.weight.grad is None
            assert torch.equal(original_encoder, model.encoder.embedding.weight)
            assert not torch.equal(original_head, model.scorer[-1].weight)
        else:
            assert model.encoder.embedding.weight.grad is not None
            assert not torch.equal(original_encoder, model.encoder.embedding.weight)


def test_metrics_do_not_hide_positive_failures_behind_many_stops():
    records = [(0, [0.0, 2.0], [0.0, 1.0], 2)] * 9 + [(0, [0.0, 2.0], [1.0, 0.0], 2)]
    result = validation_metrics(records)
    assert result["valid_set_accuracy"] == 0.9
    assert result["positive_selection_accuracy"] == 0
    assert result["positive_items"] == 1
    # Any of several valid choices must count as correct.
    assert (
        validation_metrics([(0, [0.0, 2.0, -1.0], [0.5, 0.5, 0.0], 3)])[
            "positive_correct"
        ]
        == 1
    )


def test_checkpoint_preserves_verified_tokenizer_bytes_and_rejects_mutation(tmp_path):
    """Save metadata can change with Transformers; model token semantics cannot."""
    from pathlib import Path

    from transformers import AutoTokenizer

    source = Path("Data/external/laya_pilot_20261030/base_checkpoint/tokenizer")
    tok = AutoTokenizer.from_pretrained(str(source), local_files_only=True)

    def fake_save(model, tokenizer, cfg, destination):
        path = Path(destination)
        path.mkdir(parents=True)
        tokenizer.save_pretrained(path / "tokenizer")
        (path / "model.safetensors").write_bytes(b"small-test-weight")
        (path / "rl_agent_config.json").write_text("{}")

    upstream = SimpleNamespace(save_checkpoint=fake_save)
    output = tmp_path / "valid"
    save_model(upstream, None, tok, {}, output, source)
    for original in source.iterdir():
        assert (
            output / "tokenizer" / original.name
        ).read_bytes() == original.read_bytes()
    tok.padding_side = "left" if tok.padding_side == "right" else "right"
    with pytest.raises(ValueError, match="tokenizer changed"):
        save_model(upstream, None, tok, {}, tmp_path / "invalid", source)
    assert not (tmp_path / "invalid" / "rl_agent_config.json").exists()


def test_validation_uses_its_own_batch_size():
    calls = []

    def records(*args, batch_size):
        calls.append(batch_size)
        return [(0, [2.0, 0.0], [1.0, 0.0], 2)]

    upstream = SimpleNamespace(calibration_records=records)
    args = SimpleNamespace(max_len=1024, head_max_len=256, validation_batch=16)
    items = [
        {
            "q": {
                "crit": {
                    "STOP": "None of the remaining mention groups refers to this entity."
                }
            }
        }
    ]
    assert validation(upstream, None, None, items, "cpu", args)["positive_correct"] == 1
    validation(upstream, None, None, items, "cpu", args, batch_size=4)
    assert calls == [16, 4]
