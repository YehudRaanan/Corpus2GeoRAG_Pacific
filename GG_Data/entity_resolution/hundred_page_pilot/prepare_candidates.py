"""Prepare literal groups, strict exact pairs and local trigram candidate jobs.

This step reads saved mention/entity tables and does not load a decision model.
Every eligible occurrence remains in groups.jsonl for an auditable join.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from GG_Data.entity_resolution.hundred_page_pilot.filter_source_content import (
    LEGACY_POLICY,
    SUPPORTED_POLICIES,
    is_eligible,
    source_policy as validate_source_policy,
)
from GG_Data.entity_resolution.hundred_page_pilot.match_exact import EXACT_SCHEMA, exact_pairs
from GG_Data.entity_resolution.luke_pilot.data import sha256, write_jsonl
from GG_Data.entity_resolution.trigram import rank_candidates

LOG = logging.getLogger(__name__)
SOURCE_REVIEW_STATUSES = {
    "source_target_review",
    "source_context_review",
    "source_type_review",
    "ambiguous_surface",
    "partial_source_overlap",
    "invalid_original_offsets",
}


def identity(parts: list) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def matching_eligibility(
    row: dict, policy: str = LEGACY_POLICY, *, exclude_date: bool = True
) -> tuple[bool, str]:
    """Use one source/span decision for matching and table writes."""
    if not all(type(row.get(key)) is int and row[key] > 0 for key in ("page_id", "revision_id")):
        return False, "page_revision_unresolved"
    if row.get("revision_status", "VERIFIED_RAW_CONTENT") != "VERIFIED_RAW_CONTENT":
        return False, "page_revision_unresolved"
    if not is_eligible(row, policy):
        return False, "source_excluded" if row.get("source_scope_status") == "EXCLUDE" else "source_review"
    if "clean_status" in row or "Text_clean" in row:
        if row.get("repair_status") in SOURCE_REVIEW_STATUSES:
            return False, "source_review"
        if row.get("clean_status") != "mapped":
            return False, "source_excluded" if row.get("clean_status") == "excluded" else "source_review"
        if row.get("clean_source_status") != "unique_raw_placement" or not row.get("clean_revision_sha256"):
            return False, "source_review"
        if row.get("clean_text_needs_review"):
            return False, "context_review"
        text, start, end = row.get("Text_clean"), row.get("clean_start"), row.get("clean_end")
        if not (isinstance(text, str) and type(start) is int and type(end) is int
                and 0 <= start < end <= len(text) and text[start:end] == row["word"]):
            return False, "invalid_clean_span"
    if exclude_date and row["entity_group"] == "DATE":
        return False, "deferred_date"
    return True, "eligible"


def group_mentions(
    rows: list[dict], *, exclude_date: bool = False, source_policy: str | None = None
) -> list[dict]:
    """Keep literal name/type identity and every occurrence, per revision."""
    policy = validate_source_policy(rows, source_policy)
    clean_flags = ["clean_status" in row or "Text_clean" in row for row in rows]
    if any(clean_flags) and not all(clean_flags):
        raise ValueError("Mixed clean and raw mention rows")
    grouped = {}
    for row in rows:
        if not matching_eligibility(row, policy, exclude_date=exclude_date)[0]:
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
                "source_candidate_qids": [],
                "repaired_source_row_indices": [],
                "repair_methods": [],
                "repair_qid_guided": False,
                "source_review_statuses": [],
                "occurrence_ids": [],
            }
        group = grouped[key]
        group["source_row_indices"].append(int(row["source_row_index"]))
        if row.get("occurrence_id"):
            group["occurrence_ids"].append(row["occurrence_id"])
        group["source_candidate_qids"] = sorted(
            set(group["source_candidate_qids"])
            | set(row.get("source_candidate_qids") or [])
        )
        if (
            row.get("word_original", row["word"]) != row["word"]
            or row.get("repair_status") == "repaired"
        ):
            group["repaired_source_row_indices"].append(int(row["source_row_index"]))
        if row.get("repair_method"):
            group["repair_methods"] = sorted(
                set(group["repair_methods"]) | {row["repair_method"]}
            )
        group["repair_qid_guided"] |= bool(row.get("repair_qid_guided"))
        if row.get("repair_status") in SOURCE_REVIEW_STATUSES:
            group["source_review_statuses"] = sorted(
                set(group["source_review_statuses"]) | {row["repair_status"]}
            )
        cleaned = "Text_clean" in row
        text = (row["Text_clean"] if cleaned else row["Text"]) or ""
        start, end = (int(row["clean_start"]), int(row["clean_end"])) if cleaned else (int(row["start"]), int(row["end"]))
        context = (
            row["source_scope_context"]
            if policy != LEGACY_POLICY and not cleaned
            else text[max(0, start - 160) : min(len(text), end + 160)]
        )
        if context not in group["contexts"]:
            group["contexts"].append(context)
    result = []
    for group in grouped.values():
        group["context"] = "\n".join(group["contexts"][:3])
        result.append(group)
    return sorted(result, key=lambda g: (g["page_id"], g["revision_id"], g["id"]))



def prepare(
    mentions: Path,
    entity_path: Path,
    output: Path,
    count: int,
    *,
    exclude_date: bool = False,
    source_policy: str | None = None,
    exact_path: Path | None = None,
) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq

    if count < 0:
        raise ValueError("Candidate count must be zero (all) or positive")
    rows = pq.read_table(mentions).to_pylist()
    policy = validate_source_policy(rows, source_policy)
    groups = group_mentions(rows, exclude_date=exclude_date, source_policy=policy)
    entities = pq.read_table(entity_path).to_pylist()
    keys = [(e["page_id"], e["revision_id"], e["qid"]) for e in entities]
    if len(set(keys)) != len(keys):
        raise ValueError("Entity table must have unique page/revision/QID rows")
    computed = exact_pairs(groups, entities)
    exact = pq.read_table(exact_path).to_pylist() if exact_path is not None else computed
    if exact != computed:
        raise ValueError("Exact stage pairs do not match current groups and entities")
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
        top = ranked[:count] if count else ranked
        top_ids = {g["id"] for g in top}
        protected = {g["id"] for g in ranked if key[2] in g["source_candidate_qids"]}
        candidates = [g for g in ranked if g["id"] in top_ids | protected]
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
                "protected_candidate_count": len(protected),
                "protected_candidates_added": len(protected - top_ids),
                "top_trigram_candidate_count": len(top),
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "groups.jsonl", groups)
    write_jsonl(output / "jobs.jsonl", jobs)
    pq.write_table(
        pa.Table.from_pylist(exact, schema=EXACT_SCHEMA), output / "exact_pairs.parquet"
    )
    return {
        "groups": len(groups),
        "entities": len(entities),
        "missing_entity_names": missing_names,
        "exact_pairs": len(exact),
        "model_questions": len(jobs),
        "candidate_limit": count,
        "exclude_date": exclude_date,
        "source_policy": policy,
        "source_scope_counts": dict(
            Counter(r.get("source_scope_status", "LEGACY_UNFILTERED") for r in rows)
        ),
        "source_eligible_rows": sum(is_eligible(r, policy) for r in rows),
        "matching_eligible_rows": sum(matching_eligibility(r, policy, exclude_date=exclude_date)[0] for r in rows),
        "matching_eligibility_reason_counts": dict(Counter(matching_eligibility(r, policy, exclude_date=exclude_date)[1] for r in rows)),
        "excluded_date_rows": (
            sum(r["entity_group"] == "DATE" and is_eligible(r, policy) for r in rows)
            if exclude_date
            else 0
        ),
        "candidate_union_pairs_including_stop": sum(
            len(j["candidates"]) + 1 for j in jobs
        ),
        "protected_candidate_pairs": sum(j["protected_candidate_count"] for j in jobs),
        "protected_candidate_pairs_added": sum(
            j["protected_candidates_added"] for j in jobs
        ),
        "pair_counts_by_k_zero_means_all": counts,
        "input_hashes": {str(p): sha256(p) for p in (mentions, entity_path)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mentions", type=Path, required=True)
    parser.add_argument("--entities", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--source-policy",
        choices=[*SUPPORTED_POLICIES, LEGACY_POLICY],
        help="Require this source policy; otherwise detect annotations and reject mixed inputs",
    )
    parser.add_argument(
        "--exclude-date",
        action="store_true",
        help="Preserve DATE rows outside this matching experiment",
    )
    parser.add_argument(
        "--candidates", type=int, default=0, help="0 evaluates all local groups"
    )
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Use a new output directory; existing outputs are preserved")
    started, utc = time.monotonic(), datetime.now(timezone.utc).isoformat()
    summary = prepare(
        args.mentions,
        args.entities,
        args.output,
        args.candidates,
        exclude_date=args.exclude_date,
        source_policy=args.source_policy,
    )
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
