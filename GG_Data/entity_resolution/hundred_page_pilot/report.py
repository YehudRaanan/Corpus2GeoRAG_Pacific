"""Freeze source-link reference evidence, then export the pilot and its report.

The reference contains only positive pairs supported by a Daniel span equal to
a complete raw Wikipedia link anchor. It is made before model predictions.
It is an incomplete source-derived check, not complete human-labelled truth;
it cannot establish precision, negative truth or stop accuracy on 100 pages.
The final export preserves every selected input row and stores all QID matches
as a list, so many-to-many matches do not duplicate or discard source rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from GG_Data.entity_resolution.hundred_page_pilot.filter_source_content import (
    LEGACY_POLICY,
    is_eligible,
    source_policy,
)
from GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates import (
    group_mentions,
    identity,
)
from GG_Data.entity_resolution.luke_pilot.data import read_jsonl, sha256


def _valid_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and set(value) <= set("0123456789abcdef")
    )


def freeze_reference(
    mentions: list[dict], revisions: list[dict], links: list[dict]
) -> list[dict]:
    """Keep unique exact-passage placements and complete anchor spans only."""
    raw = {
        (r["page_id"], r["revision_id"]): Path(r["wikitext_path"]).read_text(
            encoding="utf-8"
        )
        for r in revisions
    }
    anchors = defaultdict(list)
    for link in links:
        if link.get("qid") and link.get("link_origin") == "RAW_DIRECT_LINK":
            anchors[
                link["page_id"], link["revision_id"], link.get("anchor_text")
            ].append(link)
    positives = {}
    for mention in mentions:
        key = (mention.get("page_id"), mention.get("revision_id"))
        original_word = mention.get("word_original", mention["word"])
        text = mention.get("Text") or ""
        content = raw.get(key, "")
        first = content.find(text) if text else -1
        if first < 0 or content.find(text, first + 1) >= 0:
            continue
        start, end = first + mention["start"], first + mention["end"]
        if content[start:end] != original_word:
            continue
        for link in anchors[key[0], key[1], original_word]:
            if (link.get("anchor_start"), link.get("anchor_end")) != (start, end):
                continue
            group_id = identity([*key, original_word, mention["entity_group"]])
            pair = (*key, group_id, link["qid"])
            positives[pair] = {
                "page_id": key[0],
                "revision_id": key[1],
                "group_id": group_id,
                "qid": link["qid"],
                "name": original_word,
                "entity_group": mention["entity_group"],
                "source_row_index": mention["source_row_index"],
                "raw_start": start,
                "raw_end": end,
                "evidence_path": link.get("raw_evidence_path"),
                "mapping_evidence": link.get("mapping_evidence"),
                "basis": "EXACT_COMPLETE_RAW_LINK_ANCHOR_POSITIVE_ONLY",
            }
    return sorted(
        positives.values(),
        key=lambda p: (p["page_id"], p["revision_id"], p["group_id"], p["qid"]),
    )


def source_positive_metrics(reference: list[dict], pairs: list[dict]) -> dict:
    def key(p: dict) -> tuple:
        return (p["page_id"], p["revision_id"], p["group_id"], p["qid"])

    expected, predicted = {key(p) for p in reference}, {key(p) for p in pairs}
    return {
        "supported_positive_pairs": len(expected),
        "recovered_supported_pairs": len(expected & predicted),
        "source_positive_recall": (
            len(expected & predicted) / len(expected) if expected else None
        ),
        "precision": None,
        "stop_precision": None,
        "limitation": "Incomplete positive-only link evidence; other predictions are unverified, not false.",
    }


def original_row_reference_metrics(reference: list[dict], rows: list[dict]) -> dict:
    """Expand frozen original literal groups, never repaired group identities."""
    original_groups = defaultdict(list)
    for row in rows:
        key = (
            row.get("page_id"),
            row.get("revision_id"),
            row.get("word_original", row["word"]),
            row["entity_group"],
        )
        original_groups[identity(list(key))].append(row)
    expected = set()
    for pair in reference:
        key = (pair["page_id"], pair["revision_id"], pair["name"], pair["entity_group"])
        if pair["group_id"] != identity(list(key)):
            raise ValueError(
                "Reference identity differs from original frozen name/type"
            )
        group_rows = original_groups.get(pair["group_id"], [])
        if not group_rows:
            raise ValueError("Reference pair has no original source group")
        expected.update((r["source_row_index"], pair["qid"]) for r in group_rows)
    predicted = {
        (r["source_row_index"], q) for r in rows for q in r.get("matched_qids", [])
    }
    return {
        "supported_positive_row_qid_pairs": len(expected),
        "recovered_supported_row_qid_pairs": len(expected & predicted),
        "source_positive_recall": (
            len(expected & predicted) / len(expected) if expected else None
        ),
        "precision": None,
        "stop_precision": None,
        "limitation": "Frozen original-group positive-only evidence expanded to original rows; accuracy and precision remain unknown.",
    }


def _completed_model_pairs(jobs: list[dict], inference: Path) -> set[tuple]:
    """Require one finite complete score record per job before any final export."""
    from GG_Data.entity_resolution.hundred_page_pilot.resolve_entities import (
        select_loop,
    )

    path = inference / "scores.jsonl"
    if not path.is_file():
        raise ValueError("Export requires completed scores for every matching job")
    records = read_jsonl(path)
    by_id = {r["id"]: r for r in records}
    if len(by_id) != len(records) or set(by_id) != {j["id"] for j in jobs}:
        raise ValueError(
            "Export requires unique completed scores for every matching job"
        )
    expected_pairs = set()
    for job in jobs:
        options = by_id[job["id"]]["options"]
        scores = {v["id"]: v["score"] for v in options}
        if (
            len(scores) != len(options)
            or set(scores) != {c["id"] for c in job["candidates"]} | {None}
            or not all(
                type(v) in (int, float) and math.isfinite(v) for v in scores.values()
            )
        ):
            raise ValueError("Export completed score options differ from matching job")
        selected, _ = select_loop(
            {k: v for k, v in scores.items() if k is not None}, scores[None]
        )
        expected_pairs.update(
            (job["page_id"], job["revision_id"], g, job["qid"]) for g in selected
        )
    return expected_pairs


def export(
    mentions_path: Path,
    matching: Path,
    inference: Path,
    references: Path,
    output: Path,
    passages_path: Path | None = None,
) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq

    summary_path = matching / "matching_summary.json"
    manifest_path = inference / "inference_inputs.json"
    if not summary_path.exists() or not manifest_path.exists():
        raise ValueError("Export requires matching and inference input lineage")
    matching_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    exclude_date = matching_summary.get("exclude_date", False)
    input_hashes = {
        Path(path).resolve(): digest
        for path, digest in matching_summary.get("input_hashes", {}).items()
    }
    if input_hashes.get(mentions_path.resolve()) != sha256(mentions_path):
        raise ValueError("Matching mentions input hash does not match export")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not _valid_digest(manifest.get("checkpoint_sha256")):
        raise ValueError("Export requires a valid inference checkpoint SHA-256 binding")
    if manifest.get("jobs_sha256") != sha256(matching / "jobs.jsonl"):
        raise ValueError("Inference jobs input hash does not match matching")
    mentions = pq.read_table(mentions_path)
    if {"matched_qids", "entity_match_status", "entity_match_methods"} & set(
        mentions.column_names
    ):
        raise ValueError(
            "Export input already contains matching results; preserve the historical export"
        )
    if passages_path:
        passage_rows = pq.read_table(passages_path).to_pylist()
        passages = {r["passage_id"]: r for r in passage_rows}
        if len(passages) != len(passage_rows):
            raise ValueError("Duplicate passage IDs")
        for source, name in [
            ("revision_timestamp", "wiki_revision_timestamp"),
            ("revision_url", "wiki_revision_url"),
            ("match_method", "wiki_revision_match_method"),
            ("evidence_path", "wiki_revision_evidence_path"),
            ("text_sha256", "source_text_sha256"),
        ]:
            mentions = mentions.append_column(
                name,
                pa.array(
                    [
                        passages[pid].get(source)
                        for pid in mentions["passage_id"].to_pylist()
                    ],
                    type=pa.string(),
                ),
            )
    groups = read_jsonl(matching / "groups.jsonl")
    group_by_id = {g["id"]: g for g in groups}
    if len(group_by_id) != len(groups):
        raise ValueError("Duplicate group IDs")
    source_rows = mentions.to_pylist()
    policy = source_policy(
        source_rows, matching_summary.get("source_policy", LEGACY_POLICY)
    )
    scope_counts = dict(
        Counter(r.get("source_scope_status", LEGACY_POLICY) for r in source_rows)
    )
    if policy != LEGACY_POLICY:
        if matching_summary.get("source_scope_counts") != scope_counts:
            raise ValueError("Matching source scope counts differ from export")
        if groups != group_mentions(
            source_rows, exclude_date=exclude_date, source_policy=policy
        ):
            raise ValueError("Matching groups differ from eligible source scope")
    source_by_id = {r["source_row_index"]: r for r in source_rows}
    if len(source_by_id) != len(source_rows):
        raise ValueError("Duplicate source row indices")
    by_row = {}
    for group in groups:
        if exclude_date and group["type"] == "DATE":
            raise ValueError("DATE group is outside the declared matching experiment")
        expected = (
            group["page_id"],
            group["revision_id"],
            group["name"],
            group["type"],
        )
        if group["id"] != identity(list(expected)):
            raise ValueError("Group ID does not match its source identity")
        if not group["source_row_indices"]:
            raise ValueError("Group has no source rows")
        for index in group["source_row_indices"]:
            if index in by_row or index not in source_by_id:
                raise ValueError("Duplicate or unknown group source row reference")
            row = source_by_id[index]
            if not is_eligible(row, policy):
                raise ValueError(
                    "Group contains a row outside the declared source scope"
                )
            actual = (
                row["page_id"],
                row["revision_id"],
                row["word"],
                row["entity_group"],
            )
            if actual != expected:
                raise ValueError("Group source row identity does not match export")
            by_row[index] = group
    if any(
        r.get("page_id") is not None
        and r.get("revision_id") is not None
        and not (exclude_date and r["entity_group"] == "DATE")
        and is_eligible(r, policy)
        and r["source_row_index"] not in by_row
        for r in source_rows
    ):
        raise ValueError("Resolved source row is missing its matching group")
    jobs = read_jsonl(matching / "jobs.jsonl")
    job_by_id = {j["id"]: j for j in jobs}
    query_keys = {(j["page_id"], j["revision_id"], j["qid"]) for j in jobs}
    if len(job_by_id) != len(jobs) or len(query_keys) != len(jobs):
        raise ValueError("Duplicate matching job IDs or query identities")
    for job in jobs:
        candidate_ids = [candidate["id"] for candidate in job["candidates"]]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("Duplicate matching candidate IDs")
        for candidate in job["candidates"]:
            group = group_by_id.get(candidate["id"])
            if group is None or (
                group["page_id"],
                group["revision_id"],
                group["type"],
            ) != (job["page_id"], job["revision_id"], candidate.get("type")):
                raise ValueError("Candidate references an unknown group/revision/type")
            if policy != LEGACY_POLICY and any(
                candidate.get(k) != group.get(k) for k in ("name", "context")
            ):
                raise ValueError("Candidate text differs from eligible source scope")
    exact = pq.read_table(matching / "exact_pairs.parquet").to_pylist()
    model = read_jsonl(inference / "model_pairs.jsonl")
    expected_model_pairs = _completed_model_pairs(jobs, inference)
    if expected_model_pairs != {
        (p["page_id"], p["revision_id"], p["group_id"], p["qid"]) for p in model
    }:
        raise ValueError("Export model pairs differ from completed score decisions")
    if any(p["method"] != "exact" for p in exact) or any(
        p["method"] != "model" for p in model
    ):
        raise ValueError("Pair method does not match its evidence file")
    pairs = exact + model
    keys = [(p["page_id"], p["revision_id"], p["group_id"], p["qid"]) for p in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate selected group/QID pair")
    by_group = defaultdict(set)
    methods = defaultdict(set)
    for pair in pairs:
        group = group_by_id.get(pair["group_id"])
        if group is None:
            raise ValueError("Pair references an unknown group")
        if (pair["page_id"], pair["revision_id"], pair["entity_group"]) != (
            group["page_id"],
            group["revision_id"],
            group["type"],
        ):
            raise ValueError("Pair revision/type does not match its group")
        if (pair["page_id"], pair["revision_id"], pair["qid"]) not in query_keys:
            raise ValueError("Pair references an unknown entity query")
        if pair["method"] == "model":
            job = job_by_id.get(pair.get("id"))
            if (
                job is None
                or (job["page_id"], job["revision_id"], job["qid"])
                != (pair["page_id"], pair["revision_id"], pair["qid"])
                or pair["group_id"] not in {c["id"] for c in job["candidates"]}
            ):
                raise ValueError("Model pair references an unknown job/candidate")
        by_group[pair["group_id"]].add(pair["qid"])
        methods[pair["group_id"]].add(pair["method"])
    qids, statuses, row_methods = [], [], []
    for row in source_rows:
        group = by_row.get(row["source_row_index"])
        matched = sorted(by_group.get(group["id"], ())) if group else []
        qids.append(matched)
        statuses.append(
            (
                "EXCLUDED_SOURCE"
                if row["source_scope_status"] == "EXCLUDE"
                else "REVIEW_SOURCE"
            )
            if not is_eligible(row, policy)
            else (
                "EXCLUDED_DATE"
                if exclude_date and row["entity_group"] == "DATE"
                else (
                    "MATCHED"
                    if matched
                    else "UNRESOLVED_ENTITY" if group else "UNRESOLVED_PAGE_VERSION"
                )
            )
        )
        row_methods.append(sorted(methods.get(group["id"], ())) if group else [])
    enriched = mentions.append_column(
        "matched_qids", pa.array(qids, type=pa.list_(pa.string()))
    )
    enriched = enriched.append_column("entity_match_status", pa.array(statuses))
    enriched = enriched.append_column(
        "entity_match_methods", pa.array(row_methods, type=pa.list_(pa.string()))
    )
    if not enriched.select(mentions.column_names).equals(mentions):
        raise ValueError("Original selected rows changed during export")
    reference = read_jsonl(references)
    # A subset delivery checks only its original page/revision scope. The saved
    # reference bytes stay unchanged for every arm and every subset.
    scope = {(r.get("page_id"), r.get("revision_id")) for r in source_rows}
    eligible_rows = [
        r
        for r in enriched.to_pylist()
        if is_eligible(r, policy) and not (exclude_date and r["entity_group"] == "DATE")
    ]
    local_reference = [
        p
        for p in reference
        if (p["page_id"], p["revision_id"]) in scope
        and not (exclude_date and p["entity_group"] == "DATE")
        and (
            policy == LEGACY_POLICY
            or (
                p.get("source_row_index") in source_by_id
                and is_eligible(source_by_id[p["source_row_index"]], policy)
            )
        )
    ]
    reference_check = original_row_reference_metrics(local_reference, eligible_rows)
    if policy != LEGACY_POLICY:
        reference_check["scope"] = (
            "ELIGIBLE_FROZEN_REFERENCE_SUBSET; original evidence row must be KEEP"
        )
    output.mkdir(parents=True, exist_ok=False)
    pq.write_table(enriched, output / "matched_mentions.parquet", compression="zstd")
    unresolved = enriched.filter(
        pa.array(
            [
                status in {"UNRESOLVED_ENTITY", "UNRESOLVED_PAGE_VERSION"}
                for status in statuses
            ],
            type=pa.bool_(),
        )
    )
    pq.write_table(
        unresolved, output / "unresolved_mentions.parquet", compression="zstd"
    )
    pair_schema = pa.schema(
        [
            ("page_id", pa.int64()),
            ("revision_id", pa.int64()),
            ("group_id", pa.string()),
            ("qid", pa.string()),
            ("entity_group", pa.string()),
            ("method", pa.string()),
        ]
    )
    pq.write_table(
        pa.Table.from_pylist(pairs, schema=pair_schema),
        output / "matched_pairs.parquet",
    )
    summary = {
        "selected_rows": mentions.num_rows,
        "exported_rows": enriched.num_rows,
        "row_status_counts": dict(Counter(statuses)),
        "source_policy": policy,
        "source_scope_counts": scope_counts,
        "source_eligible_rows": sum(is_eligible(r, policy) for r in source_rows),
        "unresolved_rows": unresolved.num_rows,
        "groups": len(groups),
        "matched_groups": len(by_group),
        "unresolved_resolved_page_groups": len(groups) - len(by_group),
        "exact_pairs": len(exact),
        "model_pairs": len(model),
        "completed_questions": len(jobs),
        "inference_complete": True,
        "excluded_date_rows": sum(status == "EXCLUDED_DATE" for status in statuses),
        "groups_with_multiple_qids": sum(len(q) > 1 for q in by_group.values()),
        "final_qid_type_entities": len({(p["qid"], p["entity_group"]) for p in pairs}),
        "reference_check": reference_check,
        "reference_group_check_legacy": source_positive_metrics(local_reference, pairs),
        "reference_sha256": sha256(references),
        "inference_inputs": manifest,
        "matching_summary": matching_summary,
        "original_columns_preserved": True,
    }
    (output / "results.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def compare_exports(
    baseline: Path,
    corrected: Path,
    output: Path,
    correction_summary_path: Path | None = None,
) -> dict:
    """Compare stable original row/QID pairs, retaining all many-to-many results."""
    import pyarrow.parquet as pq

    directories = (baseline, corrected)
    tables = [
        pq.read_table(p / "matched_mentions.parquet").to_pylist() for p in directories
    ]
    summaries = [
        json.loads((p / "results.json").read_text(encoding="utf-8"))
        for p in directories
    ]
    if any(
        summary.get("inference_complete") is not True
        or summary.get("exported_rows") != len(rows)
        for summary, rows in zip(summaries, tables)
    ):
        raise ValueError(
            "Comparison requires complete exports with verified row counts"
        )
    if not all(
        _valid_digest(s.get("reference_sha256")) for s in summaries
    ) or summaries[0].get("reference_sha256") != summaries[1].get("reference_sha256"):
        raise ValueError("Comparison requires the same original frozen reference")
    checkpoints = [
        s.get("inference_inputs", {}).get("checkpoint_sha256") for s in summaries
    ]
    date_scopes = [s.get("matching_summary", {}).get("exclude_date") for s in summaries]
    source_policies = [
        s.get(
            "source_policy",
            s.get("matching_summary", {}).get("source_policy", LEGACY_POLICY),
        )
        for s in summaries
    ]
    if source_policies[0] != source_policies[1]:
        raise ValueError(
            "Comparison requires identical source policies; source filtering is not a model-only change"
        )
    if (
        not all(type(scope) is bool for scope in date_scopes)
        or date_scopes[0] != date_scopes[1]
    ):
        raise ValueError("Comparison requires explicit identical DATE exclusion scopes")
    if (
        not all(_valid_digest(digest) for digest in checkpoints)
        or checkpoints[0] != checkpoints[1]
    ):
        raise ValueError("Comparison inference checkpoints differ")
    by_id = [{r["source_row_index"]: r for r in rows} for rows in tables]
    if any(len(index) != len(rows) for index, rows in zip(by_id, tables)) or set(
        by_id[0]
    ) != set(by_id[1]):
        raise ValueError("Comparison original row IDs differ or are duplicated")
    for index, before in by_id[0].items():
        after = by_id[1][index]
        for column in (
            "page_id",
            "revision_id",
            "entity_group",
            "Text",
            "start",
            "end",
            "passage_id",
            "Index",
            "Source",
        ):
            if before.get(column) != after.get(column):
                raise ValueError(
                    f"Comparison original source field differs: {column}, row {index}"
                )
        if before.get("word_original", before["word"]) != after.get(
            "word_original", after["word"]
        ):
            raise ValueError(f"Comparison original word differs: row {index}")

    def counts(indices):
        new = lost = newly = unmatched = changed = multiple = repaired = 0
        for index in indices:
            before, after = by_id[0][index], by_id[1][index]
            old, current = set(before["matched_qids"]), set(after["matched_qids"])
            new += len(current - old)
            lost += len(old - current)
            newly += bool(current) and not old
            unmatched += bool(old) and not current
            changed += bool(old) and bool(current) and old != current
            multiple += len(current) > 1
            repaired += after.get("word_original", after["word"]) != after["word"]
        return dict(
            original_rows=len(indices),
            baseline_matched_rows=sum(
                bool(by_id[0][i]["matched_qids"]) for i in indices
            ),
            corrected_matched_rows=sum(
                bool(by_id[1][i]["matched_qids"]) for i in indices
            ),
            baseline_row_qid_pairs=sum(
                len(set(by_id[0][i]["matched_qids"])) for i in indices
            ),
            corrected_row_qid_pairs=sum(
                len(set(by_id[1][i]["matched_qids"])) for i in indices
            ),
            new_row_qid_pairs=new,
            lost_row_qid_pairs=lost,
            newly_matched_rows=newly,
            lost_all_matches_rows=unmatched,
            changed_qid_rows=changed,
            corrected_multiple_qid_rows=multiple,
            corrected_repaired_rows=repaired,
        )

    indices = sorted(by_id[0])
    result = {
        **counts(indices),
        "by_type": {},
        "by_page": {},
        "precision": None,
        "accuracy": None,
        "reference_sha256": summaries[0].get("reference_sha256"),
        "checkpoint_sha256": checkpoints[0],
        "checkpoint_identity_verified": bool(checkpoints[0]),
        "limitation": "Changes are unverified outcomes; positive-only reference cannot establish accuracy or precision.",
        "baseline_results": summaries[0],
        "corrected_results": summaries[1],
        "input_hashes": {
            str(p / "matched_mentions.parquet"): sha256(p / "matched_mentions.parquet")
            for p in directories
        },
    }
    for label, column in (("by_type", "entity_group"), ("by_page", "page_id")):
        subsets = defaultdict(list)
        for index in indices:
            subsets[str(by_id[0][index].get(column))].append(index)
        result[label] = {key: counts(values) for key, values in sorted(subsets.items())}
    result["repair_status_counts"] = dict(
        Counter(r.get("repair_status", "unchanged") for r in tables[1])
    )
    result["repair_method_counts"] = dict(
        Counter(r.get("repair_method") or "none" for r in tables[1])
    )
    result["source_preparation_summary"] = None
    if correction_summary_path is not None:
        result["source_preparation_summary"] = json.loads(
            correction_summary_path.read_text(encoding="utf-8")
        )
        result["input_hashes"][str(correction_summary_path)] = sha256(
            correction_summary_path
        )
    output.mkdir(parents=True, exist_ok=False)
    with (output / "row_changes.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "source_row_index",
                "page_id",
                "revision_id",
                "entity_group",
                "word_original",
                "word_corrected",
                "baseline_qids",
                "corrected_qids",
            ],
        )
        writer.writeheader()
        for index in indices:
            before, after = by_id[0][index], by_id[1][index]
            if (
                set(before["matched_qids"]) != set(after["matched_qids"])
                or before["word"] != after["word"]
            ):
                writer.writerow(
                    {
                        "source_row_index": index,
                        **{
                            k: before[k]
                            for k in ("page_id", "revision_id", "entity_group")
                        },
                        "word_original": before.get("word_original", before["word"]),
                        "word_corrected": after["word"],
                        "baseline_qids": json.dumps(sorted(before["matched_qids"])),
                        "corrected_qids": json.dumps(sorted(after["matched_qids"])),
                    }
                )
    (output / "comparison.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    import pyarrow.parquet as pq

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mentions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze-reference", action="store_true")
    parser.add_argument("--revisions", type=Path)
    parser.add_argument(
        "--passages", type=Path, help="Copy revision metadata into final rows"
    )
    parser.add_argument("--links", type=Path)
    parser.add_argument("--matching", type=Path)
    parser.add_argument("--inference", type=Path)
    parser.add_argument("--references", type=Path)
    parser.add_argument("--compare-baseline", type=Path)
    parser.add_argument("--compare-corrected", type=Path)
    parser.add_argument("--correction-summary", type=Path)
    args = parser.parse_args()
    if args.compare_baseline or args.compare_corrected:
        if (
            not args.compare_baseline
            or not args.compare_corrected
            or args.freeze_reference
        ):
            parser.error(
                "Comparison requires both exported directories and no freeze flag"
            )
        compare_exports(
            args.compare_baseline,
            args.compare_corrected,
            args.output,
            args.correction_summary,
        )
    elif args.freeze_reference:
        if not args.mentions:
            parser.error("Freeze requires mentions")
        if not args.revisions or not args.links or args.output.exists():
            parser.error("Freeze requires revisions, links and a new output path")
        rows = freeze_reference(
            pq.read_table(args.mentions).to_pylist(),
            pq.read_table(args.revisions).to_pylist(),
            pq.read_table(args.links).to_pylist(),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    else:
        if (
            not args.mentions
            or not args.matching
            or not args.inference
            or not args.references
        ):
            parser.error("Export requires matching, inference and references")
        started = time.monotonic()
        summary = export(
            args.mentions,
            args.matching,
            args.inference,
            args.references,
            args.output,
            args.passages,
        )
        summary.update(
            ended_utc=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic() - started,
            active_work_seconds=None,
        )
        (args.output / "results.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
