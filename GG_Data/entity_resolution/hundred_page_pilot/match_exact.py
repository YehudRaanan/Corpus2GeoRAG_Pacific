"""Strict literal exact matching, saved as a separate auditable pipeline stage."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from GG_Data.entity_resolution.luke_pilot.data import sha256, write_jsonl

EXACT_SCHEMA = pa.schema(
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
        if g.get("repaired_source_row_indices") or g.get("source_review_statuses"):
            continue
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


def prepare(
    mentions: Path,
    entities: Path,
    output: Path,
    *,
    exclude_date: bool = True,
    source_policy: str | None = None,
) -> dict:
    """Write exact groups and accepted pairs without model candidate work."""
    from GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates import (
        group_mentions,
    )

    if output.exists():
        raise FileExistsError(f"Preserve existing output: {output}")
    groups = group_mentions(
        pq.read_table(mentions).to_pylist(),
        exclude_date=exclude_date,
        source_policy=source_policy,
    )
    rows = pq.read_table(entities).to_pylist()
    keys = [(r["page_id"], r["revision_id"], r["qid"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Entity table must have unique page/revision/QID rows")
    pairs = exact_pairs(groups, rows)
    output.mkdir(parents=True, exist_ok=False)
    write_jsonl(output / "groups.jsonl", groups)
    pq.write_table(
        pa.Table.from_pylist(pairs, schema=EXACT_SCHEMA), output / "exact_pairs.parquet"
    )
    summary = dict(
        groups=len(groups),
        exact_pairs=len(pairs),
        exclude_date=exclude_date,
        source_policy=source_policy,
        input_hashes={str(p): sha256(p) for p in (mentions, entities)},
    )
    (output / "exact_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary
