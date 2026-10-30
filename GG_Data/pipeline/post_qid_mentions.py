"""Preserve original mention rows and write typed, many-to-many identity links."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.post_qid_entities import (
    accepted_pair_evidence,
    finalization,
    mention_id,
    provisional_id,
)

ORIGINAL_FIELDS = (
    "entity_group",
    "score",
    "word",
    "start",
    "end",
    "Source",
    "Index",
    "Text",
    "subtype",
)


def _processing_status(row: dict) -> str:
    """Classify audit-only rows before considering matching outcomes."""
    if (
        row.get("page_id") is None
        or row.get("revision_id") is None
        or row.get("revision_status", "VERIFIED_RAW_CONTENT") != "VERIFIED_RAW_CONTENT"
        or row.get("matching_eligibility_reason") == "page_revision_unresolved"
    ):
        return "PAGE_REVISION_UNRESOLVED"
    if (
        row.get("clean_status") == "excluded"
        or row.get("source_scope_status") == "EXCLUDE"
        or row.get("matching_eligibility_reason") == "source_excluded"
    ):
        return "SOURCE_EXCLUDED"
    if row["entity_group"] == "DATE":
        return "DEFERRED_DATE"
    if row.get("matching_eligible") is not True:
        return "SOURCE_REVIEW"
    return "PENDING_MATCHING"


def populate(
    rows: list[dict],
    groups: list[dict],
    pairs: list[dict],
    *,
    input_sha256: str,
    dataset_namespace: str,
    stage: str = "legacy",
    finalize: bool | None = None,
) -> dict:
    """Reject lost or conflicting source rows; never propagate a match to a name."""
    mention_id(input_sha256, 0)
    provisional_id("validation", "MISC", dataset_namespace)
    closed = finalization(stage, finalize)
    revised = stage != "legacy"
    if revised:
        from GG_Data.entity_resolution.hundred_page_pilot.filter_source_content import (
            source_policy,
        )
        from GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates import (
            matching_context,
            matching_eligibility,
        )

        policy = source_policy(rows)
    by_index = {}
    for row in rows:
        index = row["source_row_index"]
        mention_id(input_sha256, index)
        if index in by_index:
            raise ValueError("Duplicate original source row index")
        for field in ("page_id", "revision_id"):
            if (row.get(field) is not None or not revised) and (
                type(row.get(field)) is not int or row[field] <= 0
            ):
                raise ValueError("Original row lacks a valid page/revision identity")
        if row.get("wiki_site", "enwiki") != "enwiki" or row.get(
            "wiki_page_id", row.get("page_id")
        ) != row.get("page_id"):
            raise ValueError("Original Wikipedia identity conflicts with enwiki scope")
        if (
            "raw" in row
            or (
                "mention_id" in row
                and row["mention_id"] != mention_id(input_sha256, index)
            )
            or (
                "occurrence_id" in row
                and row["occurrence_id"] != mention_id(input_sha256, index)
            )
            or ("input_sha256" in row and row["input_sha256"] != input_sha256)
        ):
            raise ValueError("Original row conflicts with generated mention fields")
        if revised and type(row.get("matching_eligible")) is not bool:
            raise ValueError("Revised row requires explicit matching eligibility")
        if (
            revised
            and row["matching_eligible"]
            and not matching_eligibility(row, policy)[0]
        ):
            raise ValueError(
                "Matching eligibility conflicts with clean/revision evidence"
            )
        provisional_id(row["word"], row["entity_group"], dataset_namespace)
        by_index[index] = row
    by_group, group_for_row = {}, {}
    for group in groups:
        gid = group["id"]
        if not isinstance(gid, str) or not gid or gid in by_group:
            raise ValueError("Group identity must be unique and nonempty")
        by_group[gid] = group
        if any(
            type(group[field]) is not int or group[field] <= 0
            for field in ("page_id", "revision_id")
        ):
            raise ValueError("Group lacks a valid page/revision identity")
        if not group["source_row_indices"]:
            raise ValueError("Empty original mention group")
        for index in group["source_row_indices"]:
            mention_id(input_sha256, index)
            if index not in by_index or index in group_for_row:
                raise ValueError("Unknown or conflicting original group row")
            row = by_index[index]
            if revised and _processing_status(row) != "PENDING_MATCHING":
                raise ValueError("Saved group includes a row not eligible for matching")
            if (
                group["name"],
                group["type"],
                group["page_id"],
                group["revision_id"],
            ) != (row["word"], row["entity_group"], row["page_id"], row["revision_id"]):
                raise ValueError(
                    "Group literal/type/page/revision differs from original row"
                )
            group_for_row[index] = gid
    required = {
        index
        for index, row in by_index.items()
        if not revised
        or (stage != "pending" and _processing_status(row) == "PENDING_MATCHING")
    }
    if not required <= group_for_row.keys():
        raise ValueError("Original mention has no saved group")
    accepted = accepted_pair_evidence(by_group, pairs, stage=stage)
    mentions, links = [], []
    for source in rows:
        index = source["source_row_index"]
        mid, gid = mention_id(input_sha256, index), group_for_row.get(index)
        status = _processing_status(source) if revised else None
        targets = accepted[gid] if gid in accepted else {}
        if revised and targets:
            status = (
                "ACCEPTED_MODEL"
                if any(
                    pair["method"] == "model"
                    for evidence in targets.values()
                    for pair in evidence.values()
                )
                else "ACCEPTED_EXACT"
            )
        if not targets and closed and (not revised or status == "PENDING_MATCHING"):
            targets = {
                provisional_id(
                    source["word"], source["entity_group"], dataset_namespace
                ): {}
            }
            if revised:
                status = "ENTITY_UNRESOLVED"
        raw = dict(source)
        if revised:
            raw = {field: source[field] for field in ORIGINAL_FIELDS}
            raw["word"] = source.get(
                "raw_original_word", source.get("word_original", source["word"])
            )
        mentions.append(
            {
                **source,
                "mention_id": mid,
                "wiki_site": "enwiki",
                "wiki_page_id": source["page_id"],
                "raw": raw,
                **(
                    {
                        "occurrence_id": mid,
                        "processing_status": status,
                        "matching_context_basis": (
                            matching_context(source)["basis"]
                            if source["matching_eligible"]
                            else None
                        ),
                    }
                    if revised
                    else {}
                ),
            }
        )
        for target, evidence_by_key in sorted(targets.items()):
            evidence = [dict(evidence_by_key[key]) for key in sorted(evidence_by_key)]
            methods = sorted({p["method"] for p in evidence}) or ["unresolved"]
            links.append(
                dict(
                    mention_id=mid,
                    entity_id=target,
                    entity_type=source["entity_group"],
                    group_id=gid,
                    method=methods[0],
                    methods=methods,
                    evidence=evidence,
                )
            )
    return {"mentions": mentions, "mention_entity_links": links}


def _records(path: Path) -> list[dict]:
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq

        return pq.read_table(path).to_pylist()
    if path.suffix == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return read_json(path)


def run(
    mentions_path: Path,
    groups_path: Path,
    pairs_path: Path,
    output: Path,
    *,
    input_sha256: str,
    dataset_namespace: str,
    page_ids: set[int] | None = None,
    stage: str = "legacy",
    finalize: bool | None = None,
) -> dict:
    rows, groups, pairs = (
        _records(path) for path in (mentions_path, groups_path, pairs_path)
    )
    if page_ids is not None:
        all_group_ids = {g["id"] for g in groups}
        if any(pair["group_id"] not in all_group_ids for pair in pairs):
            raise ValueError("Accepted pair has no saved group")
        rows = [row for row in rows if row["page_id"] in page_ids]
        groups = [group for group in groups if group["page_id"] in page_ids]
        selected = {g["id"] for g in groups}
        pairs = [pair for pair in pairs if pair["group_id"] in selected]
        if {row["page_id"] for row in rows} != page_ids:
            raise ValueError("Selected page has no original mentions")
    tables = populate(
        rows,
        groups,
        pairs,
        input_sha256=input_sha256,
        dataset_namespace=dataset_namespace,
        stage=stage,
        finalize=finalize,
    )
    output.mkdir(parents=True, exist_ok=False)
    for name, records in tables.items():
        with gzip.open(output / f"{name}.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(records, stream, ensure_ascii=False)
    manifest = dict(
        original_input_sha256=input_sha256,
        dataset_namespace=dataset_namespace,
        page_ids=sorted(
            {row["page_id"] for row in rows if row.get("page_id") is not None}
        ),
        stage=stage,
        finalized=finalization(stage, finalize),
        inputs={
            str(path): digest(path) for path in (mentions_path, groups_path, pairs_path)
        },
        counts={name: len(records) for name, records in tables.items()},
        outputs={
            f"{name}.json.gz": digest(output / f"{name}.json.gz") for name in tables
        },
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("mentions", "groups", "pairs", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--dataset-namespace", required=True)
    parser.add_argument("--page-ids", type=int, nargs="+")
    parser.add_argument(
        "--stage",
        choices=("legacy", "pending", "exact", "model", "final"),
        default="legacy",
    )
    parser.add_argument(
        "--finalize", action=argparse.BooleanOptionalAction, default=None
    )
    args = parser.parse_args()
    run(
        args.mentions,
        args.groups,
        args.pairs,
        args.output,
        input_sha256=args.input_sha256,
        dataset_namespace=args.dataset_namespace,
        page_ids=set(args.page_ids) if args.page_ids else None,
        stage=args.stage,
        finalize=args.finalize,
    )


if __name__ == "__main__":
    main()
