"""Preserve original mention rows and write typed, many-to-many identity links."""

from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import defaultdict
from pathlib import Path

from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.post_qid_entities import mention_id, provisional_id


def populate(
    rows: list[dict],
    groups: list[dict],
    pairs: list[dict],
    *,
    input_sha256: str,
    dataset_namespace: str,
) -> dict:
    """Reject lost or conflicting source rows; never propagate a match to a name."""
    mention_id(input_sha256, 0)
    provisional_id("validation", "MISC", dataset_namespace)
    by_index = {}
    for row in rows:
        index = row["source_row_index"]
        mention_id(input_sha256, index)
        if index in by_index:
            raise ValueError("Duplicate original source row index")
        for field in ("page_id", "revision_id"):
            if type(row[field]) is not int or row[field] <= 0:
                raise ValueError("Original row lacks a valid page/revision identity")
        if (
            row.get("wiki_site", "enwiki") != "enwiki"
            or row.get("wiki_page_id", row["page_id"]) != row["page_id"]
        ):
            raise ValueError("Original Wikipedia identity conflicts with enwiki scope")
        if "raw" in row or (
            "mention_id" in row and row["mention_id"] != mention_id(input_sha256, index)
        ):
            raise ValueError("Original row conflicts with generated mention fields")
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
    if group_for_row.keys() != by_index.keys():
        raise ValueError("Original mention has no saved group")
    accepted = defaultdict(lambda: defaultdict(dict))
    model_identities = set()
    for pair in pairs:
        gid, qid = pair["group_id"], pair["qid"]
        if (
            gid not in by_group
            or not isinstance(qid, str)
            or not re.fullmatch(r"Q[1-9]\d*", qid)
        ):
            raise ValueError("Unknown accepted group or invalid QID")
        group = by_group[gid]
        expected = dict(
            page_id=group["page_id"],
            wiki_page_id=group["page_id"],
            revision_id=group["revision_id"],
            entity_group=group["type"],
            entity_type=group["type"],
            name=group["name"],
            wiki_site="enwiki",
        )
        if any(
            pair[field] != value for field, value in expected.items() if field in pair
        ):
            raise ValueError(
                "Accepted pair differs from group literal/type/revision scope"
            )
        if pair.get("method") not in {"exact", "model"}:
            raise ValueError("Accepted pair requires exact or model method")
        if pair["method"] == "model":
            reference = pair.get("decision_reference")
            if not isinstance(reference, dict):
                raise ValueError(
                    "Model pair provenance requires a decision reference object"
                )
            texts = [
                pair.get("run_id"),
                reference.get("path"),
                reference.get("record_id"),
            ]
            hashes = [
                pair.get("checkpoint_sha256"),
                pair.get("readiness_sha256"),
                reference.get("sha256"),
            ]
            if not (
                all(isinstance(value, str) and value.strip() for value in texts)
                and all(
                    isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                    for value in hashes
                )
            ):
                raise ValueError(
                    "Model pair provenance requires run, checkpoint, readiness and decision identities"
                )
            model_identities.add((pair["checkpoint_sha256"], pair["readiness_sha256"]))
            if len(model_identities) > 1:
                raise ValueError("Model pairs mix checkpoint/readiness identities")
        accepted[gid][qid][json.dumps(pair, sort_keys=True, ensure_ascii=False)] = pair
    mentions, links = [], []
    for source in rows:
        index = source["source_row_index"]
        mid, gid = mention_id(input_sha256, index), group_for_row[index]
        mentions.append(
            {
                **source,
                "mention_id": mid,
                "wiki_site": "enwiki",
                "wiki_page_id": source["page_id"],
                "raw": dict(source),
            }
        )
        targets = accepted[gid]
        if not targets:
            targets = {
                provisional_id(
                    source["word"], source["entity_group"], dataset_namespace
                ): {}
            }
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
    )
    output.mkdir(parents=True, exist_ok=False)
    for name, records in tables.items():
        with gzip.open(output / f"{name}.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(records, stream, ensure_ascii=False)
    manifest = dict(
        original_input_sha256=input_sha256,
        dataset_namespace=dataset_namespace,
        page_ids=sorted({row["page_id"] for row in rows}),
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
    args = parser.parse_args()
    run(
        args.mentions,
        args.groups,
        args.pairs,
        args.output,
        input_sha256=args.input_sha256,
        dataset_namespace=args.dataset_namespace,
        page_ids=set(args.page_ids) if args.page_ids else None,
    )


if __name__ == "__main__":
    main()
