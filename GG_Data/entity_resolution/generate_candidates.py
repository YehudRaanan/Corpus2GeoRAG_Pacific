"""First full candidate run. No entity selection, model calls, or graph changes.

python GG_Data/entity_resolution/generate_candidates.py --output <new-directory>
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import logging
import platform
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow
from prepare_examples import (
    COMMIT,
    ROOT,
    URL,
    exclusion_reason,
    load_exclusions,
    original_endpoints,
    sha256,
)

METHOD = "page-trigram-candidates-v0.1.0"
MAP_VERSION = "relation-map-v2.1.0"
LOG = logging.getLogger(__name__)


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", folded))


def trigrams(text: str) -> frozenset[str]:
    text = normalize(text)
    return (
        frozenset(text[i : i + 3] for i in range(len(text) - 2))
        if len(text) >= 3
        else frozenset([text]) - {""}
    )


def similarity(left: str, right: str) -> float:
    a, b = trigrams(left), trigrams(right)
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


def mention_id(row: dict[str, Any]) -> str:
    identity = [row[k] for k in ("Source", "Index", "start", "end", "entity_group")]
    return (
        "mention-"
        + hashlib.sha256(
            json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
    )


class NameIndex:
    """Trigram postings avoid comparing every mention with every page alias."""

    def __init__(
        self, entity_ids: list[str], metadata: dict[str, dict[str, Any]]
    ) -> None:
        self.names: list[tuple[str, str, str, frozenset[str], bool]] = []
        self.postings: dict[str, list[int]] = defaultdict(list)
        for qid in sorted(entity_ids):
            entity = metadata.get(qid, {})
            names = {name: "alias" for name in entity.get("aliases", []) if name}
            if entity.get("label"):
                names[entity["label"]] = "label"
            for name, kind in sorted(names.items()):
                grams = trigrams(name)
                if not grams:
                    continue
                index = len(self.names)
                self.names.append(
                    (qid, name, kind, grams, "Q5" in entity.get("direct_types", []))
                )
                for gram in sorted(grams):
                    self.postings[gram].append(index)

    def find(self, word: str, group: str, threshold: float) -> list[dict[str, Any]]:
        if not 0 <= threshold <= 1:
            raise ValueError("Name threshold must be in [0, 1]")
        grams = trigrams(word)
        if not grams:
            return []
        shared = Counter(
            i for gram in sorted(grams) for i in self.postings.get(gram, [])
        )
        best = {}
        for index in range(len(self.names)) if threshold == 0 else sorted(shared):
            qid, name, kind, target, human = self.names[index]
            if group == "PER" and not human:
                continue
            score = 2 * shared[index] / (len(grams) + len(target))
            if score < threshold:
                continue
            candidate = {
                "entity_id": qid,
                "matched_name": name,
                "matched_name_kind": kind,
                "name_similarity": score,
                "type_check": "EXPLICIT_HUMAN_Q5" if group == "PER" else "PENDING",
            }
            # Name iteration is sorted: equal scores keep the first source name.
            if qid not in best or score > best[qid]["name_similarity"]:
                best[qid] = candidate
        return sorted(
            best.values(), key=lambda r: (-r["name_similarity"], r["entity_id"])
        )


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_line(stream: Any, value: Any) -> None:
    stream.write(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        + "\n"
    )


def load_metadata(path: Path, titles: set[str]) -> tuple[dict, dict]:
    metadata, title_ids = {}, defaultdict(set)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            entity = json.loads(line).get("entity")
            if not entity or "id" not in entity:
                continue
            qid = entity["id"]
            types = []
            for claim in entity.get("claims", {}).get("P31", []):
                value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(value, dict) and value.get("id"):
                    types.append(value["id"])
            metadata[qid] = {
                "entity_id": qid,
                "label": entity.get("labels", {}).get("en", {}).get("value", ""),
                "aliases": sorted(
                    {a["value"] for a in entity.get("aliases", {}).get("en", [])}
                ),
                "direct_types": sorted(set(types)),
                "wikidata_revision": entity.get("lastrevid"),
                "name_source": "Wikidata",
                "name_language": "en",
            }
            title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
            if title in titles:
                title_ids[title].add(qid)
    return metadata, title_ids


def page_contexts(
    titles: set[str],
    page_path: Path,
    title_ids: dict,
    assertions: Path,
    mapping_path: Path,
) -> tuple[dict, dict]:
    evidence = defaultdict(list)
    with page_path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["article_title"] in titles and row.get("qid"):
                evidence[row["article_title"]].append(
                    {
                        "entity_id": row["qid"],
                        "method": "article_qids_exact_title",
                        "article_title": row["article_title"],
                        "resolved_title": row.get("resolved_title"),
                        "article_pageid": row.get("article_pageid"),
                    }
                )
    pages = {}
    for title in sorted(titles):
        support = evidence[title]
        # Use the saved sitelink only when the article map has no exact entry.
        if not support:
            support = [
                {
                    "entity_id": q,
                    "method": "wikidata_enwiki_exact_title",
                    "article_title": title,
                }
                for q in sorted(title_ids.get(title, []))
            ]
        ids = sorted({r["entity_id"] for r in support})
        pages[title] = {
            "Source": title,
            "page_qid": ids[0] if len(ids) == 1 else None,
            "page_status": (
                "RESOLVED"
                if len(ids) == 1
                else "AMBIGUOUS" if ids else "NOT_IN_SNAPSHOT"
            ),
            "resolution_evidence": support,
        }
    page_ids = {p["page_qid"] for p in pages.values() if p["page_qid"]}
    mapping = {}
    with mapping_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row["source"], row["source_predicate"])
            if key in mapping or row["relation_map_version"] != MAP_VERSION:
                raise ValueError(f"Unexpected mapping key/version: {key}")
            mapping[key] = row
    exclusions = load_exclusions()
    neighbours = {q: defaultdict(list) for q in page_ids}
    counts = Counter()
    with assertions.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            counts["input_assertions"] += 1
            source = row["selected_source"]
            a, b = original_endpoints(row)
            if exclusion_reason(
                source,
                {
                    "source_record_id": row["source_record_id"],
                    "predicate": row["selected_source_predicate"],
                    "subject_qid": a,
                    "object_qid": b,
                },
                exclusions,
            ):
                counts["excluded_assertions"] += 1
                continue
            rule = mapping[(source, row["selected_source_predicate"])]
            if a not in page_ids and b not in page_ids:
                continue
            direction = rule["direction_to_level2"]
            if direction not in {"same", "reverse"}:
                raise ValueError(f"Unexpected mapping direction: {direction}")
            x, y = (b, a) if direction == "reverse" else (a, b)
            link = {
                "subject": x,
                "object": y,
                "relation": rule["level2_relation_id"],
                "source": source,
                "source_predicate": row["selected_source_predicate"],
                "source_record_id": row["source_record_id"],
                "observation_id": row["observation_id"],
                "original_subject": a,
                "original_object": b,
                "mapping_direction": direction,
                "assertion_qa_required": rule["assertion_qa_required"],
            }
            for page, other in {(x, y), (y, x)}:
                if page in neighbours:
                    neighbours[page][other].append(link)
            counts["page_context_assertions"] += 1
    return (pages, {"neighbours": neighbours, "counts": dict(counts)})


def run(output: Path, threshold: float) -> None:
    raw_path = ROOT / "Data/external/daniel_20261017.parquet"
    external = ROOT / "Data/external/wwii_task_force"
    metadata_path = external / "wikidata_entities.jsonl.gz"
    page_path = external / "article_qids.jsonl"
    assertions = (
        ROOT
        / "GG_Data/mapping/outputs/relation-map-v1.0.0/complete_mapped_relations_v1.0.0.csv"
    )
    mapping_path = ROOT / "GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.0.csv"
    inputs = [
        raw_path,
        metadata_path,
        page_path,
        assertions,
        mapping_path,
        ROOT / "GG_Data/mapping/ASSERTION_EXCLUSIONS.csv",
        Path(__file__),
        ROOT / "GG_Data/entity_resolution/prepare_examples.py",
        ROOT / "GG_Data/mapping/assertion_exclusions.py",
        ROOT / "GG_Data/mapping/run_relation_mapping_sanity.py",
    ]
    LOG.info("Hashing frozen input files")
    hashes = {p.relative_to(ROOT).as_posix(): sha256(p) for p in inputs}
    blob = hashlib.sha1(
        f"blob {raw_path.stat().st_size}\0".encode() + raw_path.read_bytes()
    ).hexdigest()
    if blob != "dcf304ad0dd38ca9874f3172609eb0597aa4f285":
        raise ValueError("Input does not match Daniel's pinned upload")
    params = {
        "method": METHOD,
        "min_name_similarity": threshold,
        "mapping_version": MAP_VERSION,
        "page_scope": "page identity plus direct incoming/outgoing graph neighbours",
        "PER_type_policy": "explicit P31=Q5",
        "other_type_policy": "PENDING",
        "DATE_policy": "DEFERRED",
        "candidate_cap": None,
        "name_language": "en",
        "identity_selection": False,
    }
    run_id = (
        "candidates-"
        + hashlib.sha256(
            json.dumps([hashes, params], sort_keys=True).encode()
        ).hexdigest()[:20]
    )
    frame = pd.read_parquet(raw_path)
    columns = [
        "entity_group",
        "score",
        "word",
        "start",
        "end",
        "Source",
        "Index",
        "Text",
        "subtype",
    ]
    if set(frame.columns) != set(columns) or frame.isna().any().any():
        raise ValueError("Unexpected input schema or missing fields")
    titles = set(frame.Source)
    LOG.info("Loading saved names and exact Wikipedia sitelinks")
    metadata, title_ids = load_metadata(metadata_path, titles)
    LOG.info("Building page contexts from unified assertions")
    pages, graph_info = page_contexts(
        titles, page_path, title_ids, assertions, mapping_path
    )
    neighbours = graph_info["neighbours"]
    used_entities, pools = set(), {}
    with gzip.open(output / "page_context.jsonl.gz", "wt", encoding="utf-8") as stream:
        for title, page in pages.items():
            qid = page["page_qid"]
            pool = sorted({qid} | set(neighbours[qid])) if qid else []
            pools[title] = pool
            used_entities.update(pool)
            write_line(
                stream,
                {
                    **page,
                    "run_id": run_id,
                    "pool": [
                        {
                            "entity_id": q,
                            "context_id": f"{qid}|{q}",
                            "page_identity": q == qid,
                            "assertions": neighbours[qid].get(q, []),
                        }
                        for q in pool
                    ],
                },
            )
    with gzip.open(
        output / "entity_metadata.jsonl.gz", "wt", encoding="utf-8"
    ) as stream:
        for qid in sorted(used_entities):
            write_line(
                stream,
                metadata.get(qid, {"entity_id": qid, "metadata_status": "MISSING"}),
            )
    counters: dict[str, Counter] = defaultdict(Counter)
    ids, seen_rows, pair_count = set(), set(), 0
    page_summaries = []
    LOG.info(
        "Generating candidates for %d mentions on %d pages", len(frame), len(titles)
    )
    with gzip.open(
        output / "mention_candidates.jsonl.gz", "wt", encoding="utf-8"
    ) as stream:
        for number, (title, group_frame) in enumerate(
            frame.groupby("Source", sort=True), start=1
        ):
            page, pool = pages[title], pools[title]
            index = NameIndex(pool, metadata)
            cache = {}
            page_counts = Counter()
            for input_row, values in zip(
                group_frame.index, group_frame.itertuples(index=False, name=None)
            ):
                row = dict(zip(frame.columns, values))
                if not (
                    isinstance(row["start"], int)
                    and isinstance(row["end"], int)
                    and 0 <= row["start"] < row["end"] <= len(row["Text"])
                    and row["Text"][row["start"] : row["end"]] == row["word"]
                ):
                    raise ValueError(f"Invalid mention span at input row {input_row}")
                mid = mention_id(row)
                if mid in ids:
                    raise ValueError(
                        f"Duplicate mention identity at input row {input_row}"
                    )
                ids.add(mid)
                seen_rows.add(int(input_row))
                entity_group = row["entity_group"]
                if entity_group == "DATE":
                    candidates, status = [], "DEFERRED_DATE"
                elif page["page_status"] != "RESOLVED":
                    candidates, status = [], "PAGE_" + page["page_status"]
                else:
                    key = (entity_group, normalize(row["word"]))
                    if key not in cache:
                        cache[key] = index.find(row["word"], entity_group, threshold)
                    candidates = cache[key]
                    status = "CANDIDATES_FOUND" if candidates else "NO_NAME_CANDIDATE"
                candidates = [
                    {
                        **candidate,
                        "context_id": f"{page['page_qid']}|{candidate['entity_id']}",
                    }
                    for candidate in candidates
                ]
                write_line(
                    stream,
                    {
                        "run_id": run_id,
                        "input_row_number": int(input_row),
                        "mention_id": mid,
                        "raw": row,
                        "page_qid": page["page_qid"],
                        "page_status": page["page_status"],
                        "candidate_status": status,
                        "type_policy": (
                            "EXPLICIT_HUMAN_Q5"
                            if entity_group == "PER"
                            else (
                                "DEFERRED_DATE" if entity_group == "DATE" else "PENDING"
                            )
                        ),
                        "candidate_count": len(candidates),
                        "candidates": candidates,
                    },
                )
                counters[entity_group][status] += 1
                page_counts[status] += 1
                pair_count += len(candidates)
            page_summaries.append(
                {
                    **page,
                    "input_mentions": len(group_frame),
                    "pool_entities": len(pool),
                    "pool_entities_with_names": len({name[0] for name in index.names}),
                    "statuses": dict(page_counts),
                }
            )
            if number % 25 == 0 or number == len(titles):
                LOG.info(
                    "Pages %d/%d; preserved mentions %d; candidate pairs %d",
                    number,
                    len(titles),
                    len(ids),
                    pair_count,
                )
    if len(ids) != len(frame) or seen_rows != set(range(len(frame))):
        raise ValueError("Input/output mention reconciliation failed")
    LOG.info("Verifying output records and source integrity")
    verified_ids, verified_pairs, verified_counts = set(), 0, defaultdict(Counter)
    with gzip.open(
        output / "mention_candidates.jsonl.gz", "rt", encoding="utf-8"
    ) as stream:
        for line in stream:
            row = json.loads(line)
            mid = row["mention_id"]
            if (
                mid in verified_ids
                or mid != mention_id(row["raw"])
                or row["raw"] != frame.iloc[row["input_row_number"]].to_dict()
            ):
                raise ValueError(
                    "Written mention differs from raw input or repeats an ID"
                )
            verified_ids.add(mid)
            candidate_ids = [c["entity_id"] for c in row["candidates"]]
            if (
                len(candidate_ids) != len(set(candidate_ids))
                or len(candidate_ids) != row["candidate_count"]
            ):
                raise ValueError("Candidate count/identity reconciliation failed")
            for candidate in row["candidates"]:
                qid = candidate["entity_id"]
                entity = metadata[qid]
                names = [entity["label"]] + entity["aliases"]
                if (
                    qid not in pools[row["raw"]["Source"]]
                    or candidate["matched_name"] not in names
                    or similarity(row["raw"]["word"], candidate["matched_name"])
                    != candidate["name_similarity"]
                    or candidate["name_similarity"] < threshold
                    or (
                        row["raw"]["entity_group"] == "PER"
                        and "Q5" not in entity["direct_types"]
                    )
                ):
                    raise ValueError("Written candidate lacks source/name/type support")
            verified_pairs += len(candidate_ids)
            verified_counts[row["raw"]["entity_group"]][row["candidate_status"]] += 1
    if (
        verified_ids != ids
        or verified_pairs != pair_count
        or dict(verified_counts) != dict(counters)
    ):
        raise ValueError("Written candidate output reconciliation failed")
    if hashes != {p.relative_to(ROOT).as_posix(): sha256(p) for p in inputs}:
        raise ValueError("An input or code file changed during the run")
    summary = {
        "run_id": run_id,
        "input_mentions": len(frame),
        "output_mentions": len(ids),
        "candidate_pairs": pair_count,
        "pages": len(titles),
        "page_statuses": dict(Counter(p["page_status"] for p in pages.values())),
        "by_entity_group": {
            kind: {"total_mentions": sum(counts.values()), "statuses": dict(counts)}
            for kind, counts in sorted(counters.items())
        },
        "pool_entity_ids": len(used_entities),
        "pool_entities_missing_metadata": len(used_entities - metadata.keys()),
        "graph_assertions": graph_info["counts"],
        "pages_detail": page_summaries,
        "accuracy_measured": False,
        "candidate_recall_measured": False,
        "final_identity_links": 0,
    }
    write_json(output / "summary.json", summary)
    outputs = {
        p.name: {"sha256": sha256(p), "bytes": p.stat().st_size}
        for p in sorted(output.iterdir())
        if p.is_file()
    }
    write_json(
        output / "run_manifest.json",
        {
            "status": "COMPLETED",
            "run_id": run_id,
            "completed_utc": datetime.now(timezone.utc).isoformat(),
            "parameters": params,
            "inputs_sha256": hashes,
            "daniel_commit": COMMIT,
            "daniel_git_blob": blob,
            "daniel_url": URL,
            "runtime": {
                "python": platform.python_version(),
                "pandas": pd.__version__,
                "pyarrow": pyarrow.__version__,
            },
            "outputs": outputs,
            "verification": {
                "all_raw_rows_preserved": True,
                "stable_ids_unique": True,
                "all_candidate_names_scores_types_and_page_membership_verified": True,
                "inputs_unchanged_during_run": True,
            },
        },
    )
    LOG.info("Completed: %s", output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-name-similarity", type=float, default=0.35)
    args = parser.parse_args()
    if not 0 <= args.min_name_similarity <= 1:
        parser.error("--min-name-similarity must be in [0, 1]")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    run(output, args.min_name_similarity)


if __name__ == "__main__":
    main()
