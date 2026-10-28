"""Small contract tests for the variable-candidate decision pilot."""

import math

import pytest

from data import candidates_unique, choose_options, metric_summary, stable_head


def test_candidates_deduplicate_identity_not_name():
    rows = [{"id": "Q1", "name": "Alpha"}, {"id": "Q1", "name": "Alias"},
            {"id": "Q2", "name": "Alpha"}]
    assert [x["id"] for x in candidates_unique(rows)] == ["Q1", "Q2"]


def test_none_when_gold_absent_and_variable_options():
    rows = [{"id": str(i), "name": str(i)} for i in range(9)]
    options, target = choose_options(rows, "9", 3)
    assert len(options) == 3 and target is None
    options, target = choose_options(rows, "2", 8)
    assert len(options) == 8 and target == "2"
    with pytest.raises(ValueError):
        choose_options(rows, "0", 0)


def test_metrics_do_not_count_unverified_or_hide_none_errors():
    gold = [{"id": "a", "target": "Q1", "verified": True},
            {"id": "b", "target": None, "verified": True},
            {"id": "c", "target": "Q3", "verified": True},
            {"id": "d", "target": None, "verified": False}]
    preds = [{"id": "a", "prediction": "Q1"}, {"id": "b", "prediction": None},
             {"id": "c", "prediction": None}, {"id": "d", "prediction": None}]
    result = metric_summary(gold, preds)
    assert result["verified"] == 3 and result["unverified"] == 1
    assert result["correct"] == 2 and result["accuracy"] == pytest.approx(2/3)
    assert result["none_precision"] == 0.5 and result["none_recall"] == 1.0
    assert result["predicted_none"] == 2
    assert metric_summary([], [])["none_precision"] is None
    with pytest.raises(ValueError):
        metric_summary(gold, preds[:-1])


def test_stability_requires_three_small_finite_changes():
    assert not stable_head([1.0, 0.5, 0.4, 0.3])
    assert stable_head([1.0, 0.999, 1.001, 1.002])
    assert not stable_head([1.0, 1.0, math.nan, 1.0])
    assert not stable_head([1.0, 1.0, 1.0])


def test_budget_guard_rejects_expired_or_invalid_limits():
    from data import runtime_allowed
    assert runtime_allowed(10, 20, 1, .71, 2, 15)
    assert not runtime_allowed(0, 3601, 1, .71, 2, 15)
    assert not runtime_allowed(0, 60, 8, 20, 2, 15)
    assert not runtime_allowed(0, math.nan, 8, .71, 2, 15)


def test_sha256_supports_cloud_python310(tmp_path, monkeypatch):
    import hashlib
    from data import sha256
    monkeypatch.delattr(hashlib, "file_digest", raising=False)
    path = tmp_path / "input.txt"
    path.write_bytes(b"pilot")
    assert sha256(path) == hashlib.sha256(b"pilot").hexdigest()


def test_variable_group_loss_and_candidate_permutation():
    import torch
    from model import grouped_loss, group_predictions
    values = torch.tensor([1., 3., 0., 4., 1.], requires_grad=True)
    loss = grouped_loss(values, [3, 2], [1, 0])
    expected = (torch.nn.functional.cross_entropy(values[:3][None], torch.tensor([1])) +
                torch.nn.functional.cross_entropy(values[3:][None], torch.tensor([0]))) / 2
    assert torch.allclose(loss, expected)
    loss.backward()
    assert values.grad is not None
    assert group_predictions(values.detach(), [3, 2]) == [1, 0]
    assert group_predictions(values.detach()[torch.tensor([1, 0, 2, 3, 4])], [3, 2]) == [0, 0]
    with pytest.raises(ValueError):
        grouped_loss(values, [3, 3], [1, 0])


def test_frozen_encoder_unchanged_then_updates_with_tiny_luke():
    import torch
    from transformers import LukeConfig, LukeModel
    from model import CandidateScorer
    torch.manual_seed(4)
    torch.set_num_threads(2)
    encoder = LukeModel(LukeConfig(vocab_size=41, entity_vocab_size=8, hidden_size=16,
                       entity_emb_size=8, num_hidden_layers=1, num_attention_heads=2,
                       intermediate_size=32, max_position_embeddings=64))
    model = CandidateScorer(encoder)
    inputs = {"input_ids": torch.tensor([[0, 4, 5, 2], [0, 7, 8, 2]]),
              "attention_mask": torch.ones(2, 4, dtype=torch.long)}
    model.freeze_encoder(True)
    model.train()
    assert not model.encoder.training
    before = {k: v.clone() for k, v in encoder.state_dict().items()}
    opt = torch.optim.SGD([p for p in model.parameters() if p.requires_grad], lr=.1)
    torch.nn.functional.cross_entropy(model(**inputs)[None], torch.tensor([0])).backward()
    opt.step()
    assert all(torch.equal(v, before[k]) for k, v in encoder.state_dict().items())
    model.freeze_encoder(False)
    opt = torch.optim.SGD(model.parameters(), lr=.1)
    opt.zero_grad()
    torch.nn.functional.cross_entropy(model(**inputs)[None], torch.tensor([1])).backward()
    opt.step()
    assert any(not torch.equal(v, before[k]) for k, v in encoder.state_dict().items())


def test_frozen_checkpoint_restores_original_encoder_after_full_training(tmp_path, monkeypatch):
    import copy
    from types import SimpleNamespace
    import torch
    from model import CandidateScorer
    from train import Runner
    original = torch.nn.Linear(2, 2)
    original.config = SimpleNamespace(hidden_size=2)
    runner = Runner.__new__(Runner)
    runner.args = SimpleNamespace(output=tmp_path)
    runner.device = torch.device("cpu")
    runner.model = CandidateScorer(copy.deepcopy(original))
    runner.encoder_pristine = False
    runner.model.freeze_encoder(True)
    with torch.no_grad():
        runner.model.encoder.weight.add_(1.)
    torch.save({"model": runner.model.scorer.state_dict(), "head_only": True}, tmp_path / "frozen_best.pt")
    monkeypatch.setattr("train.AutoModel.from_pretrained", lambda *a, **k: copy.deepcopy(original))
    runner.load("frozen_best")
    assert torch.equal(runner.model.encoder.weight, original.weight)

def test_baseline_join_and_verified_breakdowns():
    from evaluate import baseline_predictions, compare_systems, wilson
    sample = [
        {"id": "a", "wiki_page_id": 1, "wiki_revision_id": 2, "mention": "Alias", "type": "PER", "candidates": [{"id": "Q1", "name": "Name"}]},
        {"id": "b", "wiki_page_id": 1, "wiki_revision_id": 2, "mention": "Absent", "type": "LOC", "candidates": [{"id": "Q1", "name": "Name"}]},
        {"id": "c", "wiki_page_id": 1, "wiki_revision_id": 2, "mention": "Unknown", "type": "MISC", "candidates": [{"id": "Q1", "name": "Name"}]},
    ]
    records = [{"wiki_page_id": "1", "wiki_revision_id": "2", "source_name": x["mention"], "source_type": x["type"], "target_qid": "Q1", "status": "exact_name_unique" if x["id"] == "a" else "no_close_name", "top_score": "0.2"} for x in sample]
    top, accepted = baseline_predictions(sample, records)
    refs = [{"id": "a", "target": "Q1", "verified": True}, {"id": "b", "target": None, "verified": True}, {"id": "c", "target": None, "verified": False}]
    result = compare_systems(sample, refs, {"forced": top, "accepted": accepted})
    assert result["systems"]["accepted"]["overall"]["accuracy"] == 1.0
    assert result["systems"]["forced"]["overall"]["accuracy"] == .5
    assert result["systems"]["accepted"]["by_type"]["MISC"]["verified"] == 0
    assert result["systems"]["accepted"]["overall"]["candidate_mrr_linked"] is None
    assert result["candidate_reference_counts"] == {"total": 3, "verified_linked_in_pool": 1, "verified_none": 1, "unverified": 1}
    assert wilson(0, 0) is None
    assert wilson(9, 10)[0] < .9 < wilson(9, 10)[1]
    with pytest.raises(ValueError):
        baseline_predictions(sample, records[:-1])
