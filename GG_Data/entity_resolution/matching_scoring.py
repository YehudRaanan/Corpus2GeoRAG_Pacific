"""Approved 23 October scoring; population S2T section 3.1.

Retrieval still uses raw trigram Dice >=0.80 because penalties never increase
a score. Relevance describes page-scope concentration, not match confidence.
"""

from __future__ import annotations

import math

POLICY = {
    "version": "entity-match-penalties-v1",
    "threshold": 0.80,
    "conflicting_type_factor": 0.90,
    "low_relevance_factor": 0.95,
    "low_relevance_below": 0.01,
    "unknown_evidence_factor": 1.0,
}


def require_measurements(measured: dict, qids: set[str]) -> None:
    """A completed unavailable measurement differs from absent processing."""
    missing = qids - measured.keys()
    if missing:
        raise ValueError(f"Candidate relevance not measured: {sorted(missing)}")
    for qid in qids:
        row = measured[qid]
        value = row.get("relevance")
        status = row.get("relevance_status")
        if status == "SCORED":
            if value is None or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"Invalid measured relevance: {qid}")
        elif status != "UNAVAILABLE_BOTH_LANGUAGES" or value is not None:
            raise ValueError(f"Incomplete candidate relevance: {qid}: {status}")


def score_candidate(candidate: dict, group: str, types: set[str], record: dict) -> dict:
    """Preserve raw evidence; unknown is neither a conflict nor a zero score."""
    raw = candidate["name_similarity"]
    if not math.isfinite(raw) or not 0 <= raw <= 1:
        raise ValueError("Invalid raw name similarity")
    relevance = record.get("matching_relevance", {})
    value = relevance.get("relevance")
    if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
        raise ValueError("Invalid candidate relevance")
    conflict = bool(types) and group != "ANY" and group not in types
    type_factor = POLICY["conflicting_type_factor"] if conflict else 1.0
    low = value is not None and value < POLICY["low_relevance_below"]
    relevance_factor = POLICY["low_relevance_factor"] if low else 1.0
    return {
        **candidate,
        "raw_name_similarity": raw,
        "adjusted_similarity": raw * type_factor * relevance_factor,
        "type_factor": type_factor,
        "type_conflict": conflict,
        "relevance_factor": relevance_factor,
        "relevance": value,
        "relevance_status": relevance.get("relevance_status", "UNMEASURED"),
        "relevance_evidence": relevance,
        "scoring_policy": POLICY["version"],
    }
