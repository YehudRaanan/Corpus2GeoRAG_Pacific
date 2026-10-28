"""Match one QID to Daniel groups on the same saved Wikipedia revision.

Prepare groups and exact pairs first. Rank the remaining local groups with
character-trigram Dice. A trained shared scorer then selects one group at a
time until the full stop sentence wins. Scores are computed once because
removing an option does not change the query or the other option texts.
All original row indices remain in groups.jsonl for an auditable join.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from GG_Data.entity_resolution.luke_pilot.data import (read_jsonl, sha256,
                                                       write_jsonl)

LOG = logging.getLogger(__name__)


def identity(parts: list) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def group_mentions(rows: list[dict]) -> list[dict]:
    """Keep literal name/type identity and every occurrence, per revision."""
    grouped = {}
    for row in rows:
        if row.get("page_id") is None or row.get("revision_id") is None:
            continue
        key = (
            int(row["page_id"]),
            int(row["revision_id"]),
            row["word"],
            row["entity_group"],
        )
        if key not in grouped:
            grouped[key] = {
                "id": identity(list(key)),
                "page_id": key[0],
                "revision_id": key[1],
                "name": key[2],
                "type": key[3],
                "source_row_indices": [],
                "contexts": [],
            }
        group = grouped[key]
        group["source_row_indices"].append(int(row["source_row_index"]))
        text = row["Text"] or ""
        start, end = int(row["start"]), int(row["end"])
        context = text[max(0, start - 160) : min(len(text), end + 160)]
        if context not in group["contexts"]:
            group["contexts"].append(context)
    result = []
    for group in grouped.values():
        group["context"] = "\n".join(group["contexts"][:3])
        result.append(group)
    return sorted(result, key=lambda g: (g["page_id"], g["revision_id"], g["id"]))


def exact_pairs(groups: list[dict], entities: list[dict]) -> list[dict]:
    """Exact means literal label, one Daniel type and one QID on that revision."""
    names = defaultdict(set)
    qids = defaultdict(set)
    for g in groups:
        names[g["page_id"], g["revision_id"], g["name"]].add(g["type"])
    for e in entities:
        if e.get("label") and e.get("qid"):
            qids[int(e["page_id"]), int(e["revision_id"]), e["label"]].add(e["qid"])
    result = []
    for g in groups:
        key = (g["page_id"], g["revision_id"], g["name"])
        if len(names[key]) == len(qids[key]) == 1:
            result.append(
                {
                    "page_id": g["page_id"],
                    "revision_id": g["revision_id"],
                    "group_id": g["id"],
                    "qid": next(iter(qids[key])),
                    "name": g["name"],
                    "entity_group": g["type"],
                    "method": "exact",
                }
            )
    return result


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


def select_loop(
    scores: dict[str, float], stop_score: float
) -> tuple[list[str], list[dict]]:
    if not all(math.isfinite(v) for v in [stop_score, *scores.values()]):
        raise ValueError("All scores must be finite")
    remaining = dict(scores)
    selected, trace = [], []
    while remaining:
        best = min(remaining, key=lambda k: (-remaining[k], k))
        if remaining[best] <= stop_score:
            break
        trace.append(
            {
                "step": len(trace),
                "decision": "select",
                "group_id": best,
                "score": remaining[best],
                "stop_score": stop_score,
                "remaining_count": len(remaining),
            }
        )
        selected.append(best)
        del remaining[best]
    trace.append(
        {
            "step": len(trace),
            "decision": "stop",
            "group_id": None,
            "score": stop_score,
            "remaining_count": len(remaining),
        }
    )
    return selected, trace


def prepare(mentions: Path, entity_path: Path, output: Path, count: int) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq

    groups = group_mentions(pq.read_table(mentions).to_pylist())
    entities = pq.read_table(entity_path).to_pylist()
    keys = [(e["page_id"], e["revision_id"], e["qid"]) for e in entities]
    if len(set(keys)) != len(keys):
        raise ValueError("Entity table must have unique page/revision/QID rows")
    exact = exact_pairs(groups, entities)
    accepted = defaultdict(set)
    for pair in exact:
        accepted[pair["page_id"], pair["revision_id"], pair["qid"]].add(
            pair["group_id"]
        )
    by_page = defaultdict(list)
    for group in groups:
        by_page[group["page_id"], group["revision_id"]].append(group)
    jobs, missing_names = [], 0
    counts = {str(k): 0 for k in (10, 20, 40, 80, 0)}
    for entity in entities:
        if not entity.get("label"):
            missing_names += 1
            continue
        key = (entity["page_id"], entity["revision_id"], entity["qid"])
        local = [g for g in by_page[key[:2]] if g["id"] not in accepted[key]]
        ranked = rank_candidates(entity, local)
        for k in counts:
            counts[k] += min(int(k), len(ranked)) + 1 if int(k) else len(ranked) + 1
        candidates = ranked[:count] if count else ranked
        jobs.append(
            {
                "id": identity(list(key)),
                "page_id": key[0],
                "revision_id": key[1],
                "qid": key[2],
                "entity": {
                    "name": entity["label"],
                    "aliases": entity.get("aliases") or [],
                    "description": entity.get("description") or "",
                },
                "candidates": [
                    {k: g[k] for k in ("id", "name", "type", "context", "trigram")}
                    for g in candidates
                ],
                "total_local_candidates": len(ranked),
                "excluded_count": len(ranked) - len(candidates),
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "groups.jsonl", groups)
    write_jsonl(output / "jobs.jsonl", jobs)
    schema = pa.schema(
        [
            ("page_id", pa.int64()),
            ("revision_id", pa.int64()),
            ("group_id", pa.string()),
            ("qid", pa.string()),
            ("name", pa.string()),
            ("entity_group", pa.string()),
            ("method", pa.string()),
        ]
    )
    pq.write_table(
        pa.Table.from_pylist(exact, schema=schema), output / "exact_pairs.parquet"
    )
    return {
        "groups": len(groups),
        "entities": len(entities),
        "missing_entity_names": missing_names,
        "exact_pairs": len(exact),
        "model_questions": len(jobs),
        "candidate_limit": count,
        "pair_counts_by_k_zero_means_all": counts,
        "input_hashes": {str(p): sha256(p) for p in (mentions, entity_path)},
    }


def infer(
    jobs_path: Path,
    checkpoint: Path,
    output: Path,
    max_hours: float,
    pair_batch_size: int,
    device: str,
) -> dict:
    """Resume only a matching checkpoint/input; append each completed score row."""
    from GG_Data.entity_resolution.hundred_page_pilot.model import (
        load_scorer, score_record)

    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=True)
    signature = {
        "jobs_sha256": sha256(jobs_path),
        "checkpoint_sha256": sha256(checkpoint),
    }
    manifest = output / "inference_inputs.json"
    if manifest.exists():
        if json.loads(manifest.read_text(encoding="utf-8")) != signature:
            raise ValueError("Resume inputs/checkpoint differ from the saved inference")
    else:
        manifest.write_text(json.dumps(signature, indent=2), encoding="utf-8")
    score_path = output / "scores.jsonl"
    saved = read_jsonl(score_path) if score_path.exists() else []
    scores_by_id = {r["id"]: r for r in saved}
    if len(scores_by_id) != len(saved):
        raise ValueError("Duplicate completed inference IDs")
    jobs = read_jsonl(jobs_path)
    job_ids = {j["id"] for j in jobs}
    if len(job_ids) != len(jobs) or not scores_by_id.keys() <= job_ids:
        raise ValueError("Saved scores do not match unique current jobs")
    model, tokenizer, metadata = load_scorer(checkpoint, device)
    with score_path.open("a", encoding="utf-8") as stream:
        for i, job in enumerate(jobs):
            if job["id"] in scores_by_id:
                continue
            if time.monotonic() - started >= max_hours * 3600:
                raise TimeoutError(
                    "Inference time allowance reached; completed scores preserved"
                )
            scores = score_record(
                model, tokenizer, job, device=device, pair_batch_size=pair_batch_size
            )
            if not all(math.isfinite(v) for v in scores.values()):
                raise ValueError("Nonfinite model score")
            row = {
                "id": job["id"],
                "options": [{"id": k, "score": v} for k, v in scores.items()],
            }
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            scores_by_id[row["id"]] = row
            if i % 50 == 0:
                LOG.info("Scored %d/%d entity/revision questions", i + 1, len(jobs))
    pairs, traces = [], []
    for job in jobs:
        scores = {v["id"]: v["score"] for v in scores_by_id[job["id"]]["options"]}
        expected = {c["id"] for c in job["candidates"]} | {None}
        if scores.keys() != expected:
            raise ValueError("Option scores do not match this question")
        selected, trace = select_loop(
            {k: v for k, v in scores.items() if k is not None}, scores[None]
        )
        key = {k: job[k] for k in ("id", "page_id", "revision_id", "qid")}
        types = {c["id"]: c.get("type") for c in job["candidates"]}
        pairs.extend(
            {**key, "group_id": g, "entity_group": types[g], "method": "model"}
            for g in selected
        )
        traces.extend(
            {**key, **step, "excluded_count": job["excluded_count"]} for step in trace
        )
    # Derived files can be rebuilt from the append-only score evidence after interruption.
    for name, rows in (("model_pairs.jsonl", pairs), ("decisions.jsonl", traces)):
        with (output / name).open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {
        "questions": len(jobs),
        "selected_pairs": len(pairs),
        "decisions": len(traces),
        "pair_evaluations": sum(len(j["candidates"]) + 1 for j in jobs),
        "elapsed_seconds": time.monotonic() - started,
        "active_work_seconds": None,
        "checkpoint": metadata,
        **signature,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mentions", type=Path)
    parser.add_argument("--entities", type=Path)
    parser.add_argument(
        "--jobs", type=Path, help="Existing prepared jobs; enables inference"
    )
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-hours", type=float, default=1.0)
    parser.add_argument("--pair-batch-size", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--candidates", type=int, default=0, help="0 evaluates all local groups"
    )
    args = parser.parse_args()
    if args.jobs:
        if not args.checkpoint or args.max_hours <= 0:
            parser.error("Inference requires --checkpoint and positive --max-hours")
        summary = infer(
            args.jobs,
            args.checkpoint,
            args.output,
            args.max_hours,
            args.pair_batch_size,
            args.device,
        )
        (args.output / "inference_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        return
    if not args.mentions or not args.entities:
        parser.error("Preparation requires --mentions and --entities")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Use a new output directory; existing outputs are preserved")
    started, utc = time.monotonic(), datetime.now(timezone.utc).isoformat()
    summary = prepare(args.mentions, args.entities, args.output, args.candidates)
    summary.update(
        started_utc=utc,
        elapsed_seconds=time.monotonic() - started,
        active_work_seconds=None,
        stage="candidate_preparation",
    )
    (args.output / "matching_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    LOG.info("Candidate preparation: %s", summary)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
