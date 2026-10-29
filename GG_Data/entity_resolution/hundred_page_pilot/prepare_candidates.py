"""Prepare literal groups, strict exact pairs and local trigram candidate jobs.

This step reads saved mention/entity tables and does not load a decision model.
Every original occurrence remains in groups.jsonl for an auditable join.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from GG_Data.entity_resolution.luke_pilot.data import sha256, write_jsonl
from GG_Data.entity_resolution.trigram import rank_candidates

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mentions", type=Path, required=True)
    parser.add_argument("--entities", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--candidates", type=int, default=0, help="0 evaluates all local groups"
    )
    args = parser.parse_args()
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
