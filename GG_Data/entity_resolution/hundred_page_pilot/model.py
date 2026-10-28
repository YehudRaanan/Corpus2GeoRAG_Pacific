"""Score an entity question against mention groups with the existing LUKE head.

Inputs are entity names, aliases and descriptions plus literal mention groups
and context. QIDs remain metadata. Each option has an independent score, so
unchanged options can be encoded once and reused during local removal.
"""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import torch

from GG_Data.entity_resolution.luke_pilot.model import CandidateScorer

MODEL = "studio-ousia/luke-base"
REVISION = "7438924defd9f3c2018d63c16073bf4bcb6a70aa"
STOP_SENTENCE = "None of the remaining mention groups refers to this entity."
QUERY_ALIASES_MAX = 12
QUERY_ALIASES_CHARACTERS = 600
QUERY_DESCRIPTION_CHARACTERS = 600


def pair_texts(row: dict) -> tuple[list[str], list[str], list[int]]:
    entity = row["entity"]
    aliases = "; ".join((entity.get("aliases") or [])[:QUERY_ALIASES_MAX])[
        :QUERY_ALIASES_CHARACTERS
    ]
    query = (
        f"Entity: {entity['name']}. Aliases: {aliases}. "
        f"Description: {(entity.get('description') or '')[:QUERY_DESCRIPTION_CHARACTERS]}"
    )
    candidates = row["candidates"]
    ids = [candidate["id"] for candidate in candidates]
    if len(ids) != len(set(ids)) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("Candidate IDs must be unique nonempty strings")
    options = [
        f"Mention: {c['name']}. "
        + (f"Type: {c['type']}. " if c.get("type") else "")
        + f"Context: {c.get('context') or ''}"
        for c in candidates
    ]
    options.append(STOP_SENTENCE)
    positives = set(row.get("positive_ids", []))
    if not positives.issubset(ids):
        raise ValueError("Positive ID absent from remaining candidate pool")
    targets = [i for i, identity in enumerate(ids) if identity in positives]
    return [query] * len(options), options, targets or [len(ids)]


def marginal_set_loss(
    logits: torch.Tensor, sizes: list[int], targets: list[list[int]]
) -> torch.Tensor:
    """Negative log probability of any remaining labelled positive (or stop)."""
    if (
        not sizes
        or len(sizes) != len(targets)
        or min(sizes) < 1
        or sum(sizes) != logits.numel()
    ):
        raise ValueError("Invalid grouped candidate layout")
    if any(
        not t or len(t) != len(set(t)) or min(t) < 0 or max(t) >= n
        for t, n in zip(targets, sizes)
    ):
        raise ValueError("Invalid positive index set")
    return torch.stack(
        [
            group.logsumexp(0) - group[target].logsumexp(0)
            for group, target in zip(logits.split(sizes), targets)
        ]
    ).mean()


def score_record(
    model: CandidateScorer,
    tokenizer,
    row: dict,
    device="cpu",
    max_length: int = 256,
    pair_batch_size: int = 16,
) -> dict:
    """Return independent candidate logits and the stop logit under None."""
    if pair_batch_size < 1:
        raise ValueError("pair_batch_size must be positive")
    queries, options, _ = pair_texts(row)
    model.eval()
    scores = []
    with torch.no_grad():
        for start in range(0, len(options), pair_batch_size):
            encoded = tokenizer(
                queries[start : start + pair_batch_size],
                options[start : start + pair_batch_size],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            precision = (
                torch.autocast("cuda", dtype=torch.bfloat16)
                if torch.device(device).type == "cuda"
                else nullcontext()
            )
            with precision:
                logits = model(**{k: v.to(device) for k, v in encoded.items()})
            scores.extend(logits.float().cpu().tolist())
    return dict(zip([c["id"] for c in row["candidates"]] + [None], scores))


def load_scorer(checkpoint: Path, device="cpu"):
    """Restore owned tuned weights, or the pinned encoder plus a frozen head."""
    from transformers import AutoModel, AutoTokenizer

    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if saved["model_id"] != MODEL or saved["revision"] != REVISION:
        raise ValueError("Checkpoint does not use the pinned pilot encoder")
    model = CandidateScorer(AutoModel.from_pretrained(MODEL, revision=REVISION))
    (model.scorer if saved.get("head_only") else model).load_state_dict(saved["model"])
    model.to(device).eval()
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    metadata = {k: saved[k] for k in ("model_id", "revision", "progress")}
    metadata["inference_dtype"] = (
        "bfloat16_autocast" if torch.device(device).type == "cuda" else "float32"
    )
    return model, tokenizer, metadata
