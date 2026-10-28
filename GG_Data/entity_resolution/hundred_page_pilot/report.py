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
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from GG_Data.entity_resolution.hundred_page_pilot.match import identity
from GG_Data.entity_resolution.luke_pilot.data import read_jsonl, sha256


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
        text = mention.get("Text") or ""
        content = raw.get(key, "")
        first = content.find(text) if text else -1
        if first < 0 or content.find(text, first + 1) >= 0:
            continue
        start, end = first + mention["start"], first + mention["end"]
        if content[start:end] != mention["word"]:
            continue
        for link in anchors[key[0], key[1], mention["word"]]:
            if (link.get("anchor_start"), link.get("anchor_end")) != (start, end):
                continue
            group_id = identity([*key, mention["word"], mention["entity_group"]])
            pair = (*key, group_id, link["qid"])
            positives[pair] = {
                "page_id": key[0],
                "revision_id": key[1],
                "group_id": group_id,
                "qid": link["qid"],
                "name": mention["word"],
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

    mentions = pq.read_table(mentions_path)
    if passages_path:
        passages = {
            r["passage_id"]: r for r in pq.read_table(passages_path).to_pylist()
        }
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
    exact = pq.read_table(matching / "exact_pairs.parquet").to_pylist()
    model = read_jsonl(inference / "model_pairs.jsonl")
    pairs = exact + model
    keys = [(p["page_id"], p["revision_id"], p["group_id"], p["qid"]) for p in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate selected group/QID pair")
    by_group = defaultdict(set)
    methods = defaultdict(set)
    for pair in pairs:
        by_group[pair["group_id"]].add(pair["qid"])
        methods[pair["group_id"]].add(pair["method"])
    by_row = {row: g for g in groups for row in g["source_row_indices"]}
    qids, statuses, row_methods = [], [], []
    for row in mentions.to_pylist():
        group = by_row.get(row["source_row_index"])
        matched = sorted(by_group[group["id"]]) if group else []
        qids.append(matched)
        statuses.append(
            "MATCHED"
            if matched
            else "UNRESOLVED_ENTITY" if group else "UNRESOLVED_PAGE_VERSION"
        )
        row_methods.append(sorted(methods[group["id"]]) if group else [])
    enriched = mentions.append_column(
        "matched_qids", pa.array(qids, type=pa.list_(pa.string()))
    )
    enriched = enriched.append_column("entity_match_status", pa.array(statuses))
    enriched = enriched.append_column(
        "entity_match_methods", pa.array(row_methods, type=pa.list_(pa.string()))
    )
    if not enriched.select(mentions.column_names).equals(mentions):
        raise ValueError("Original selected rows changed during export")
    output.mkdir(parents=True, exist_ok=False)
    pq.write_table(enriched, output / "matched_mentions.parquet", compression="zstd")
    unresolved = enriched.filter(pa.array([status != "MATCHED" for status in statuses]))
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
    reference = read_jsonl(references)
    summary = {
        "selected_rows": mentions.num_rows,
        "exported_rows": enriched.num_rows,
        "row_status_counts": dict(Counter(statuses)),
        "groups": len(groups),
        "matched_groups": len(by_group),
        "unresolved_resolved_page_groups": len(groups) - len(by_group),
        "exact_pairs": len(exact),
        "model_pairs": len(model),
        "groups_with_multiple_qids": sum(len(q) > 1 for q in by_group.values()),
        "final_qid_type_entities": len({(p["qid"], p["entity_group"]) for p in pairs}),
        "reference_check": source_positive_metrics(reference, pairs),
        "reference_sha256": sha256(references),
        "original_columns_preserved": True,
    }
    (output / "results.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    import pyarrow.parquet as pq

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mentions", type=Path, required=True)
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
    args = parser.parse_args()
    if args.freeze_reference:
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
        if not args.matching or not args.inference or not args.references:
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
