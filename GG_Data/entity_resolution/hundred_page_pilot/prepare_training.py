"""Build reverse entity-to-mention public pools and complete removal states.

Read cached ZELDA, the frozen selected-source inventory and selected passages.
Exclude selected source IDs/titles and detectable copied text, then split by
public source page before grouping literal mention strings. Public annotations
are incomplete: synthetic terminal states mean no labelled positive remains.
No Daniel type, alias, QID or external metadata is invented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import time
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from GG_Data.entity_resolution.luke_pilot.data import sha256, write_jsonl

LOG = logging.getLogger(__name__)
SEED = 20261028
ARCHIVE_SHA256 = "0c6c1fdb2bd5e3b530fe13644bc7b299ad26b575b1e8d1c94f2c934043d7e472"


def title_key(value: str) -> str:
    return " ".join(
        unicodedata.normalize("NFC", value.replace("_", " ")).casefold().split()
    )


def text_words(value: str) -> list[str]:
    return unicodedata.normalize("NFC", value).casefold().split()


def copied_anchors(texts: list[str]) -> tuple[set[tuple[str, ...]], set[str]]:
    anchors, short = set(), set()
    for text in texts:
        words = text_words(text)
        if len(words) >= 8:
            # Every selected eight-word window detects copied fragments; public
            # candidates use the same windows, including a changed outer context.
            anchors.update(tuple(words[i : i + 8]) for i in range(len(words) - 7))
        elif text.strip():
            short.add(" ".join(words))
    return anchors, short


def contains_copied_text(
    text: str, anchors: set[tuple[str, ...]], short: set[str]
) -> bool:
    words = text_words(text)
    return " ".join(words) in short or any(
        tuple(words[i : i + 8]) in anchors for i in range(len(words) - 7)
    )


def document_split(page_id: int) -> str:
    rank = (
        int(hashlib.sha256(f"{SEED}:split:{page_id}".encode()).hexdigest()[:8], 16)
        % 100
    )
    return "train" if rank < 80 else "validation" if rank < 90 else "public_test"


def make_groups(document: dict) -> tuple[list[dict], dict[str, set[str]]]:
    text = document["text"]
    indices, titles = document["index"], document["wikipedia_titles"]
    if len(indices) != len(titles):
        raise ValueError("Public annotation offsets and titles differ in length")
    by_name: dict[str, dict] = {}
    positives: dict[str, set[str]] = defaultdict(set)
    for (start, end), raw_title in zip(indices, titles):
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or not 0 <= start < end <= len(text)
        ):
            raise ValueError("Invalid public raw-text annotation offset")
        name = text[start:end]
        title = raw_title.replace("_", " ")
        if not name.strip() or not title or title.startswith("--"):
            continue
        identity = "mention:" + hashlib.sha256(name.encode()).hexdigest()[:20]
        context = (
            text[max(0, start - 180) : start]
            + " [MENTION] "
            + name
            + " [/MENTION] "
            + text[end : end + 180]
        )
        group = by_name.setdefault(
            name,
            {"id": identity, "name": name, "context": "", "type": None, "contexts": []},
        )
        if context not in group["contexts"]:
            group["contexts"].append(context)
        positives[title].add(identity)
    groups = list(by_name.values())
    for group in groups:
        group["context"] = " Alternative context: ".join(group.pop("contexts")[:3])[
            :1200
        ]
    return groups, dict(positives)


def removal_states(base: dict, seed: int = SEED) -> list[dict]:
    """Keep removal sequences and require every labelled positive to beat stop."""
    candidates = base["candidates"]
    ids = [candidate["id"] for candidate in candidates]
    positive = set(base["positive_ids"])
    if len(ids) != len(set(ids)) or not positive.issubset(ids):
        raise ValueError("Invalid initial candidate/positive set")
    order = sorted(positive)
    random.Random(f"{seed}:{base['id']}").shuffle(order)
    removed, states = set(), []
    for index in range(len(order) + 1):
        remaining = positive - removed
        states.append(
            {
                **base,
                "id": f"{base['id']}:state:{index}",
                "base_id": base["id"],
                "removal_index": index,
                "state_kind": "sequential_removal",
                "candidates": [c for c in candidates if c["id"] not in removed],
                "positive_ids": sorted(remaining),
                "removed_ids": sorted(removed),
                "synthetic_stop": not remaining,
                "label_scope": "remaining_public_labelled_positive_groups_only",
                "public_annotations_incomplete": True,
            }
        )
        if index < len(order):
            removed.add(order[index])
    # Marginal set loss alone lets one positive hide earlier positives in a
    # fixed removal order. Each singleton directly trains its positive above
    # stop. Retain negatives and deduplicate states already in the sequence.
    signatures = {tuple(state["removed_ids"]) for state in states}
    for identity in sorted(positive):
        removed = positive - {identity}
        signature = tuple(sorted(removed))
        if signature in signatures:
            continue
        states.append(
            {
                **base,
                "id": f"{base['id']}:singleton:{identity}",
                "base_id": base["id"],
                "removal_index": len(removed),
                "state_kind": "singleton_positive_coverage",
                "candidates": [c for c in candidates if c["id"] not in removed],
                "positive_ids": [identity],
                "removed_ids": sorted(removed),
                "synthetic_stop": False,
                "label_scope": "remaining_public_labelled_positive_groups_only",
                "public_annotations_incomplete": True,
            }
        )
        signatures.add(signature)
    return states


def prepare(
    archive: Path,
    selection_path: Path,
    passages_path: Path,
    out: Path,
    train_limit: int = 5000,
    validation_limit: int = 600,
    test_limit: int = 600,
    page_ids_path: Path | None = None,
    candidate_count: int = 40,
    questions_per_page: int = 10,
) -> dict:
    import pyarrow.parquet as pq

    from GG_Data.entity_resolution.hundred_page_pilot.match import rank_candidates

    started, started_utc = time.monotonic(), datetime.now(timezone.utc).isoformat()
    if (
        any(
            n < 1
            for n in (train_limit, validation_limit, test_limit, questions_per_page)
        )
        or candidate_count < 0
    ):
        raise ValueError("All split limits must be positive")
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(
            "Training output must be empty; preserve previous frozen inputs"
        )
    out.mkdir(parents=True, exist_ok=True)
    archive_hash = sha256(archive)
    if archive_hash != ARCHIVE_SHA256:
        raise ValueError(
            "ZELDA archive hash differs from the approved cached public archive"
        )
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selected_titles = {title_key(t) for t in selection["source_titles"]}
    passages = pq.read_table(passages_path, columns=["Source", "Text"]).to_pylist()
    passage_titles = {row["Source"] for row in passages}
    if passage_titles != set(selection["source_titles"]):
        raise ValueError(
            "Passage inventory must cover exactly the frozen source titles"
        )
    selected_texts = list({row["Text"] for row in passages})
    anchors, short = copied_anchors(selected_texts)
    excluded_pages = set(selection.get("page_ids", []))
    if page_ids_path is not None:
        page_rows = json.loads(page_ids_path.read_text(encoding="utf-8"))
        if {row["Source"] for row in page_rows} != set(selection["source_titles"]):
            raise ValueError(
                "Page-ID inventory does not cover the frozen source selection"
            )
        excluded_pages.update(
            int(row["pageid"]) for row in page_rows if row.get("pageid") is not None
        )
    output: dict[str, list[dict]] = {"train": [], "validation": [], "public_test": []}
    limits = dict(zip(output, (train_limit, validation_limit, test_limit)))
    sequential_counts = dict.fromkeys(output, 0)
    counters: Counter = Counter()
    needed = set()
    questions_by_page: Counter = Counter()
    with zipfile.ZipFile(archive) as zipped:
        # ZELDA source records contain IDs, not source titles. Resolve exclusions
        # from the public title/ID inventory before constructing any states.
        with zipped.open("zelda/other/entity_descriptions.jsonl") as stream:
            for line in stream:
                row = json.loads(line)
                if title_key(row["wikipedia_title"]) in selected_titles:
                    excluded_pages.add(int(row["wikipedia_id"]))
        with zipped.open("zelda/train_data/zelda_train.jsonl") as stream:
            for source_index, line in enumerate(stream):
                counters["documents_scanned"] += 1
                document = json.loads(line)
                page = int(document["page_id"])
                if page in excluded_pages:
                    counters["documents_excluded_selected_page"] += 1
                    continue
                split = document_split(page)
                if sequential_counts[split] >= limits[split]:
                    continue
                if questions_by_page[page] >= questions_per_page:
                    continue
                # A stable public page sample limits preparation work. Split is
                # assigned first and every section on a page uses that split.
                rank = int(
                    hashlib.sha256(f"{SEED}:sample:{page}".encode()).hexdigest()[:8], 16
                )
                if rank % 100 >= 20:
                    continue
                if contains_copied_text(document["text"], anchors, short):
                    counters["documents_excluded_copied_text"] += 1
                    continue
                groups, positives = make_groups(document)
                if len(groups) < 2:
                    counters["documents_fewer_than_two_groups"] += 1
                    continue
                text_hash = hashlib.sha256(document["text"].encode()).hexdigest()
                entity_titles = sorted(
                    positives,
                    key=lambda title: hashlib.sha256(
                        f"{SEED}:{page}:{text_hash}:{title}".encode()
                    ).hexdigest(),
                )
                for title in entity_titles:
                    if (
                        sequential_counts[split] >= limits[split]
                        or questions_by_page[page] >= questions_per_page
                    ):
                        break
                    ranked = rank_candidates(
                        {"label": title, "page_id": 0, "revision_id": 0},
                        [{**group, "page_id": 0, "revision_id": 0} for group in groups],
                    )
                    natural = ranked[:candidate_count] if candidate_count else ranked
                    natural_ids = {group["id"] for group in natural}
                    full_positive_ids = positives[title]
                    chosen = natural
                    # Injection applies only to training. Validation and test
                    # preserve the natural trigram list and expose missed gold.
                    injected = (
                        full_positive_ids - natural_ids if split == "train" else set()
                    )
                    if injected:
                        known = [
                            group
                            for group in ranked
                            if group["id"] in full_positive_ids
                        ]
                        negatives = [
                            group
                            for group in natural
                            if group["id"] not in full_positive_ids
                        ]
                        chosen = (
                            known + negatives[: max(0, candidate_count - len(known))]
                        )
                    chosen = [
                        {key: group[key] for key in ("id", "name", "context", "type")}
                        for group in chosen
                    ]
                    retained = full_positive_ids & {group["id"] for group in chosen}
                    trials = {}
                    for count in (10, 20, 40, 80, 0):
                        trial_ids = {
                            group["id"]
                            for group in (ranked[:count] if count else ranked)
                        }
                        trials[str(count) if count else "all"] = {
                            "retrieved": len(full_positive_ids & trial_ids),
                            "positive_count": len(full_positive_ids),
                            "candidate_count": len(trial_ids),
                        }
                    identity = hashlib.sha256(
                        f"{page}:{source_index}:{text_hash}:{title}".encode()
                    ).hexdigest()[:24]
                    base = {
                        "id": identity,
                        "document_id": f"wiki:{page}",
                        "source_page_id": page,
                        "source_document_index": source_index,
                        "source_text_sha256": text_hash,
                        "section_name": document.get("section_name"),
                        "entity": {
                            "name": title,
                            "aliases": [],
                            "description": "",
                            "aliases_status": "not_provided_by_public_dataset",
                        },
                        "candidates": chosen,
                        "positive_ids": sorted(retained),
                        "full_positive_ids": sorted(full_positive_ids),
                        "full_candidate_count": len(groups),
                        "candidate_trials": trials,
                        "candidate_count_limit": candidate_count,
                        "natural_retrieved_positive_ids": sorted(
                            full_positive_ids & natural_ids
                        ),
                        "gold_injected_ids": sorted(injected),
                        "excluded_candidate_count": len(groups) - len(chosen),
                        "pool_id": f"{page}:{source_index}:{text_hash[:16]}",
                        "candidate_source": "all_labelled_literal_groups_in_public_source_section",
                        "type_status": "native_Daniel_type_not_available_in_public_annotations",
                    }
                    states = removal_states(base)
                    output[split].extend(states)
                    sequential_counts[split] += sum(
                        s["state_kind"] == "sequential_removal" for s in states
                    )
                    needed.add(title)
                    questions_by_page[page] += 1
                if all(sequential_counts[key] >= limits[key] for key in output):
                    break
        descriptions = {}
        with zipped.open("zelda/other/entity_descriptions.jsonl") as stream:
            for line in stream:
                row = json.loads(line)
                title = row["wikipedia_title"].replace("_", " ")
                if title in needed:
                    descriptions[title] = row.get("description") or ""
    documents = {}
    for split, records in output.items():
        if not records:
            raise ValueError(f"No records prepared for {split}")
        documents[split] = {row["document_id"] for row in records}
        for row in records:
            row["entity"]["description"] = descriptions.get(row["entity"]["name"], "")[
                :600
            ]
            row["entity"]["description_status"] = (
                "public_description" if row["entity"]["description"] else "absent"
            )
        write_jsonl(out / f"{split}.jsonl", records)
    if any(documents[a] & documents[b] for a in documents for b in documents if a != b):
        raise ValueError("Public source-page leakage across splits")
    manifest = {
        "stage": "prepare_training",
        "owner": "model_worker",
        "seed": SEED,
        "started_utc": started_utc,
        "ended_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.monotonic() - started,
        "active_work": "unknown",
        "approval_wait": "unknown",
        "environment_wait": "unknown",
        "gpu_seconds": 0,
        "api_requests": 0,
        "estimated_cost_usd": 0,
        "archive_sha256": archive_hash,
        "selection_sha256": sha256(selection_path),
        "passages_sha256": sha256(passages_path),
        "selected_source_titles": selection["source_titles"],
        "page_ids_sha256": sha256(page_ids_path) if page_ids_path else None,
        "excluded_public_source_page_ids": sorted(excluded_pages),
        "copied_text_policy": "NFC/casefold whitespace eight-word overlap; exact shorter whole documents",
        "selected_passages": len(selected_texts),
        "copied_text_anchors": len(anchors),
        "source_page_split_before_states": True,
        "source_pages_disjoint": True,
        "annotations_incomplete": True,
        "singleton_positive_coverage": "Every retained labelled positive has a singleton-positive state; original removal sequences retained",
        "state_limits": "Limits count original sequential states; extra singleton states preserve the same base questions as v1",
        "candidate_count_limit": candidate_count,
        "questions_per_source_page_limit": questions_per_page,
        "adaptation": "Bound public trigram pools and source-page questions after full pools exceeded measured workload; preserve natural validation/test retrieval and label training gold injection",
        "synthetic_stop_caveat": "No remaining labelled positive; does not prove exhaustive negative truth",
        "public_test": "held-out source pages from ZELDA training archive; bounded diagnostic, not official benchmark",
        "scan_counts": dict(counters),
        "splits": {},
        "files": {},
    }
    for split, rows in output.items():
        sizes = [len(row["candidates"]) for row in rows]
        unique_pairs = set()
        for row in rows:
            unique_pairs.update((row["base_id"], c["id"]) for c in row["candidates"])
            unique_pairs.add((row["base_id"], None))
        manifest["splits"][split] = {
            "states": len(rows),
            "source_pages": len(documents[split]),
            "questions": len({r["base_id"] for r in rows}),
            "synthetic_stop_states": sum(r["synthetic_stop"] for r in rows),
            "multiple_positive_states": sum(len(r["positive_ids"]) > 1 for r in rows),
            "added_singleton_states": sum(
                r["state_kind"] == "singleton_positive_coverage" for r in rows
            ),
            "gold_injected_questions": sum(
                bool(r["gold_injected_ids"]) for r in rows if r["removal_index"] == 0
            ),
            "candidate_min": min(sizes),
            "candidate_max": max(sizes),
            "candidate_mean": sum(sizes) / len(sizes),
            "state_pair_count": sum(n + 1 for n in sizes),
            "unique_cached_pairs": len(unique_pairs),
        }
        manifest["files"][f"{split}.jsonl"] = sha256(out / f"{split}.jsonl")
    for name in ("public_manifest.json", "prepare_training_summary.json"):
        (out / name).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--passages", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--page-ids", type=Path, required=True)
    parser.add_argument(
        "--candidate-count",
        type=int,
        default=40,
        help="0 means all; training workload cap, not architectural limit",
    )
    parser.add_argument("--questions-per-page", type=int, default=10)
    parser.add_argument("--train-limit", type=int, default=5000)
    parser.add_argument("--validation-limit", type=int, default=600)
    parser.add_argument("--test-limit", type=int, default=600)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = prepare(
        args.archive,
        args.selection,
        args.passages,
        args.out,
        args.train_limit,
        args.validation_limit,
        args.test_limit,
        args.page_ids,
        args.candidate_count,
        args.questions_per_page,
    )
    LOG.info("Prepared split workloads: %s", json.dumps(result["splits"]))


if __name__ == "__main__":
    main()
