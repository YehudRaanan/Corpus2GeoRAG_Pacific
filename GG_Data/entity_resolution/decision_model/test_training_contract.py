"""CPU contracts for the canonical model and independent training package."""

import ast
import importlib
import inspect
from types import SimpleNamespace

import torch
from torch import nn


def test_training_modules_do_not_depend_on_pipeline_or_experimental_model():
    forbidden = (
        "GG_Data.entity_resolution.hundred_page_pilot",
        "GG_Data.entity_resolution.luke_pilot.model",
    )
    for name in ("model", "train", "prepare_training"):
        module = importlib.import_module(
            f"GG_Data.entity_resolution.decision_model.{name}"
        )
        tree = ast.parse(inspect.getsource(module))
        imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        ] + [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        assert not any(value.startswith(forbidden) for value in imports)


class TinyEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.config = SimpleNamespace(hidden_size=4)
        self.embedding = nn.Embedding(8, 4)
        self.dropout = nn.Dropout(0.5)

    def forward(self, input_ids):
        return SimpleNamespace(
            last_hidden_state=self.dropout(self.embedding(input_ids))
        )


def test_canonical_scorer_retains_checkpoint_keys_and_freeze_behavior():
    from GG_Data.entity_resolution.decision_model.model import CandidateScorer

    model = CandidateScorer(TinyEncoder())
    assert (
        CandidateScorer.__module__ == "GG_Data.entity_resolution.decision_model.model"
    )
    assert set(model.state_dict()) == {
        "encoder.embedding.weight",
        "scorer.0.weight",
        "scorer.0.bias",
        "scorer.1.weight",
        "scorer.1.bias",
        "scorer.3.weight",
        "scorer.3.bias",
    }
    restored = CandidateScorer(TinyEncoder())
    restored.load_state_dict(model.state_dict(), strict=True)
    model.freeze_encoder(True)
    model.train()
    inputs = {"input_ids": torch.tensor([[1, 2], [3, 4]])}
    assert not model.encoder.training
    assert all(not parameter.requires_grad for parameter in model.encoder.parameters())
    assert torch.equal(model(**inputs), model(**inputs))
    model(**inputs).sum().backward()
    assert model.encoder.embedding.weight.grad is None
    assert model.scorer[-1].weight.grad is not None
    model.freeze_encoder(False)
    assert model.encoder.training
    assert all(parameter.requires_grad for parameter in model.encoder.parameters())
    model(**inputs).sum().backward()
    assert model.encoder.embedding.weight.grad is not None


def test_shared_trigram_preserves_normalization_dice_order_and_scope():
    from GG_Data.entity_resolution.trigram import rank_candidates, trigrams

    assert trigrams("É_AB!") == frozenset({"e a", " ab"})
    groups = [
        {"id": "b", "name": "abcd", "page_id": 1, "revision_id": 2},
        {"id": "a", "name": "abc", "page_id": 1, "revision_id": 2},
        {"id": "c", "name": "abc", "page_id": 1, "revision_id": 3},
        {"id": "0", "name": "abc", "page_id": 1, "revision_id": 2},
    ]
    entity = {"label": "abc", "page_id": 1, "revision_id": 2}
    ranked = rank_candidates(entity, groups)
    assert [(row["id"], row["trigram"]) for row in ranked] == [
        ("0", 1.0),
        ("a", 1.0),
        ("b", 2 / 3),
    ]
    assert rank_candidates(entity, groups, count=1) == ranked[:1]
