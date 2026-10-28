"""Small, auditable data and evaluation contracts; no model-derived labels."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from pathlib import Path


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def candidates_unique(rows: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for row in rows:
        if not row.get("id") or not row.get("name"):
            raise ValueError("Candidate identity and name are required")
        if row["id"] not in seen:
            seen.add(row["id"])
            result.append(row)
    return result


def choose_options(rows: list[dict], gold: str | None, count: int) -> tuple[list[dict], str | None]:
    if count < 1:
        raise ValueError("At least one candidate is required")
    options = candidates_unique(rows)[:count]
    return options, gold if gold in {x["id"] for x in options} else None


def stable_head(losses: list[float], tolerance: float = 0.01) -> bool:
    if len(losses) < 4 or not all(math.isfinite(x) and x > 0 for x in losses[-4:]):
        return False
    return all(abs(b-a) / max(abs(a), 1e-8) <= tolerance
               for a, b in zip(losses[-4:-1], losses[-3:]))


def runtime_allowed(start: float, now: float, max_hours: float, hourly_cost: float,
                    other_cost: float, stop_cost: float) -> bool:
    values = [start, now, max_hours, hourly_cost, other_cost, stop_cost]
    if not all(math.isfinite(x) for x in values) or now < start or max_hours <= 0:
        return False
    if hourly_cost < 0 or other_cost < 0 or max_hours*hourly_cost + other_cost >= stop_cost:
        return False
    hours = (now-start)/3600
    return hours < max_hours and hours*hourly_cost + other_cost < stop_cost


def metric_summary(references: list[dict], predictions: list[dict]) -> dict:
    ref = {x["id"]: x for x in references}
    pred = {x["id"]: x for x in predictions}
    if len(ref) != len(references) or len(pred) != len(predictions) or ref.keys() != pred.keys():
        raise ValueError("Unique reference and prediction IDs must match exactly")
    rows = [(r, pred[k]) for k, r in ref.items() if r.get("verified", True)]
    def correct(r, p):
        return p["prediction"] in r.get("acceptable_targets", [r["target"]])
    total = len(rows)
    hits = sum(correct(r, p) for r, p in rows)
    pn = sum(p["prediction"] is None for r, p in rows)
    gn = sum(r["target"] is None for r, p in rows)
    tn = sum(r["target"] is None and p["prediction"] is None for r, p in rows)
    linked = [(r, p) for r, p in rows if r["target"] is not None]
    return {"total": len(ref), "verified": total, "unverified": len(ref)-total,
            "correct": hits, "accuracy": hits/total if total else None,
            "linked_count": len(linked),
            "linked_accuracy": sum(correct(r,p) for r,p in linked)/len(linked) if linked else None,
            "gold_none": gn, "predicted_none": pn, "correct_none": tn,
            "none_precision": tn/pn if pn else None,
            "none_recall": tn/gn if gn else None}


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
