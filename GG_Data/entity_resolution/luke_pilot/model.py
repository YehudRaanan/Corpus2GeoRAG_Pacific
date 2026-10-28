"""JEV-style shared scalar head over one encoder forward per answer option.

Scorer pattern: https://github.com/he-jev/laya/blob/main/rl_common.py
This is a per-pair CLS adaptation, not Laya's joint marker architecture.
"""

from __future__ import annotations

import torch
from torch import nn


class CandidateScorer(nn.Module):
    def __init__(self, encoder: nn.Module):
        super().__init__()
        self.encoder = encoder
        d = encoder.config.hidden_size
        self.scorer = nn.Sequential(nn.LayerNorm(d), nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1))
        self.frozen = False

    def freeze_encoder(self, frozen: bool = True) -> None:
        self.frozen = frozen
        self.encoder.requires_grad_(not frozen)
        self.encoder.eval() if frozen else self.encoder.train(self.training)

    def train(self, mode: bool = True):
        super().train(mode)
        if self.frozen:
            self.encoder.eval()
        return self

    def encode(self, **inputs) -> torch.Tensor:
        if self.frozen:
            with torch.no_grad():
                return self.encoder(**inputs).last_hidden_state[:, 0]
        return self.encoder(**inputs).last_hidden_state[:, 0]

    def forward(self, **inputs) -> torch.Tensor:
        return self.scorer(self.encode(**inputs).float()).squeeze(-1)


def grouped_loss(logits: torch.Tensor, sizes: list[int], targets: list[int]) -> torch.Tensor:
    if sum(sizes) != len(logits) or len(sizes) != len(targets) or not sizes or min(sizes) < 1:
        raise ValueError("Invalid grouped candidate layout")
    if any(t < 0 or t >= n for t, n in zip(targets, sizes)):
        raise ValueError("Target outside candidate group")
    return torch.stack([torch.nn.functional.cross_entropy(group[None],
                        torch.tensor([target], device=logits.device))
                        for group, target in zip(logits.split(sizes), targets)]).mean()


def group_predictions(logits: torch.Tensor, sizes: list[int]) -> list[int]:
    if sum(sizes) != len(logits) or not sizes or min(sizes) < 1:
        raise ValueError("Invalid grouped candidate layout")
    return [int(group.argmax()) for group in logits.split(sizes)]


def pair_texts(row: dict) -> tuple[list[str], list[str], int]:
    query = f"Mention: {row['mention']}. Context: {row['context']}"
    options = [f"Entity: {c['name']}. {c.get('description', '')}" for c in row["candidates"]]
    options.append("NONE: None of the listed entities refers to this mention.")
    ids = [x["id"] for x in row["candidates"]] + [None]
    target = ids.index(row["target"]) if "target" in row and row["target"] in ids else len(ids)-1
    return [query] * len(options), options, target
