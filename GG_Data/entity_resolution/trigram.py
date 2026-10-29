"""Pure character-trigram Dice retrieval shared by training and matching."""

from __future__ import annotations

import re
import unicodedata


def trigrams(text: str) -> frozenset[str]:
    # Same Dice definition as generate_candidates.py; that CLI has non-package imports.
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = " ".join(re.findall(r"[^\W_]+", text))
    return (
        frozenset(text[i : i + 3] for i in range(len(text) - 2))
        if len(text) >= 3
        else frozenset([text]) - {""}
    )


def rank_candidates(entity: dict, groups: list[dict], count: int = 0) -> list[dict]:
    if count < 0:
        raise ValueError("Candidate count must be zero (all) or positive")
    names = [entity.get("label", ""), *(entity.get("aliases") or [])]
    grams = [trigrams(n) for n in names if n]
    result = []
    for group in groups:
        if (group["page_id"], group["revision_id"]) != (
            entity["page_id"],
            entity["revision_id"],
        ):
            continue
        a = trigrams(group["name"])
        score = max(
            (2 * len(a & b) / (len(a) + len(b)) for b in grams if a and b), default=0.0
        )
        result.append({**group, "trigram": score})
    result.sort(key=lambda g: (-g["trigram"], g["id"]))
    return result[:count] if count else result
