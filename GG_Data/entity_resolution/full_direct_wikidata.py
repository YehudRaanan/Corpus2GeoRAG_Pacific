"""Run the accepted direct-Wikidata pilot rules on every pinned Daniel row.

Large evidence and resumable checkpoints live in --output (on C: by default).
No article name extraction, graph mutation, or manual identity overrides.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import logging
import os
import random
import time
from collections import Counter, defaultdict
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from bilingual_page_pilot import (
    LiveData,
    ancestry,
    article,
    choose,
    digest,
    dump,
    read,
    synthetic_id,
)
from direct_wikidata_pilot import (
    BASE,
    PAGE_CANDIDATE_SCOPE,
    SEED,
    clean_name,
    normalize_date,
    page_candidate_ids,
    page_find,
)
from generate_candidates import NameIndex
from prepare_examples import ROOT, URL

HERE = Path(__file__).resolve().parent
INPUT = ROOT / "Data/external/daniel_20261017.parquet"
INPUT_SHA256 = "dcd51dfa237b63378279ced4f9739a45d8cf8ce3991579f20848295448f83f16"
DEFAULT_OUTPUT = Path.home() / ".cache/geoai_full_daniel_20261018"
LOG = logging.getLogger(__name__)


def save(path: Path, value: object) -> None:
    """Replace only this run's own checkpoint after a complete write."""
    temporary = path.with_name("partial-" + path.name)
    dump(temporary, value)
    temporary.replace(path)


def input_rows() -> list[dict]:
    if digest(INPUT) != INPUT_SHA256:
        raise ValueError("Daniel input differs from the agreed pinned file")
    frame = pd.read_parquet(INPUT)
    rows = []
    for number, raw in enumerate(frame.to_dict("records")):
        # Same original row-number identity as the accepted bilingual pilot.
        identity = [
            number,
            *[raw[k] for k in ("Source", "Index", "start", "end", "entity_group")],
        ]
        mid = (
            "mention-"
            + hashlib.sha256(
                json.dumps(identity, ensure_ascii=False).encode()
            ).hexdigest()
        )
        rows.append(
            {"input_row_number": number, "mention_id": mid, "raw": raw, "attempts": []}
        )
    if len({r["mention_id"] for r in rows}) != len(rows):
        raise ValueError("Mention identities are not unique")
    return rows


def page_indexes(pool: set[str], metadata: dict) -> tuple:
    maps, normalized = {}, {}
    for qid in sorted(pool):
        entity = metadata[qid]
        names = sorted(set(entity.get("aliases", [])) | {entity.get("label", "")})
        maps[qid] = {clean_name(n): n for n in names if clean_name(n)}
        normalized[qid] = {**entity, "label": "", "aliases": sorted(maps[qid])}
    return NameIndex(sorted(pool), metadata), NameIndex(sorted(pool), normalized), maps


def assign(row: dict, candidates: list, metadata: dict, stage: str) -> None:
    decision = choose(
        candidates,
        row["raw"]["entity_group"],
        metadata,
        random.Random(f"{SEED}:{stage}:{row['mention_id']}"),
        prefer_single_wikidata_type=True,
    )
    row["attempts"].append({"stage": stage, **decision})
    if decision["status"] == "MATCHED":
        row.update(
            assigned_id=decision["entity_id"],
            matched_stage=stage,
            matched_name=decision["matched_name"],
            score=decision["name_similarity"],
            type_metadata=decision["type_metadata"],
        )


def match_page(source: str, rows: list[dict], pool: set[str], metadata: dict) -> tuple:
    """Match original mentions only; workers perform no retrieval or file writes."""
    original, cleaned, maps = page_indexes(pool, metadata)
    cached = {}
    for row in rows:
        if "assigned_id" not in row:
            word = row["raw"]["word"]
            if word not in cached:
                cached[word] = page_find(original, cleaned, word, maps)
            assign(row, cached[word], metadata, "PAGE_DIRECT_WIKIDATA")
    return source, os.getpid(), rows


def match_pages(
    by_page: dict[str, list[dict]],
    pools: dict[str, set[str]],
    metadata: dict,
    workers: int,
) -> Iterator[tuple[str, int, list[dict]]]:
    """Keep the same page decisions, including type ancestry and seeded ties."""
    if workers < 1:
        raise ValueError("Page worker count must be positive")
    if workers == 1:
        for source in sorted(by_page):
            yield match_page(source, by_page[source], pools[source], metadata)
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        pending = []
        for source in sorted(by_page):
            pool = pools[source]
            types = ancestry(
                [t for q in pool for t in metadata[q].get("direct_types", [])],
                metadata,
            )
            # Send this page's candidates and full type closure, not the whole cache.
            subset = {q: metadata[q] for q in pool | types if q in metadata}
            pending.append(
                executor.submit(match_page, source, by_page[source], pool, subset)
            )
        for future in as_completed(pending):
            yield future.result()


def update_report(output: Path, summary: dict) -> None:
    """Fill the run report when the unattended job finishes."""
    report = HERE / "FULL_DIRECT_RUN_2026-10-18.md"
    marker = "Status: **RUNNING**. Final counts are not available yet."
    text = report.read_text(encoding="utf-8")
    counts = "\n".join(
        f"- {stage}: **{count:,}**" for stage, count in summary["stages"].items()
    )
    replacement = (
        "Status: **COMPLETE**. All **309,864** input mentions were processed.\n\n"
        + counts
        + "\n\nResults: `"
        + str(output / "matches.csv.gz")
        + "`.\n"
        + "Verification passed: input preservation, mention IDs, threshold, three-stage "
        "coverage for unresolved non-date mentions, and unique synthetic IDs."
    )
    if marker in text:
        report.write_text(text.replace(marker, replacement, 1), encoding="utf-8")


def run(output: Path, api: LiveData | None = None, page_workers: int = 2) -> dict:
    if page_workers < 1:
        raise ValueError("Page worker count must be positive")
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").exists():
        manifest = read(output / "manifest.json")
        if manifest.get("page_candidate_scope") != PAGE_CANDIDATE_SCOPE:
            raise ValueError(
                "Historical matching scope is invalid; use a new output directory"
            )
        for name, expected in manifest["outputs"].items():
            assert digest(output / name) == expected, name
        return read(output / "summary.json")
    rows = input_rows()
    by_page = defaultdict(list)
    for row in rows:
        by_page[row["raw"]["Source"]].append(row)
    sources = sorted(by_page)
    api = api or LiveData(Path.home() / ".cache/geoai_bilingual_pilot_20261018")
    metadata_path = output / "entity_metadata.json.gz"
    api.entities = read(
        metadata_path
        if metadata_path.exists()
        else HERE
        / "runs/direct_wikidata_single_type_20261018_v2/entity_metadata.json.gz"
    )
    progress_path = output / "progress.json"

    def progress(stage: str, **counts: object) -> None:
        save(
            progress_path,
            {
                "stage": stage,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "input_mentions": len(rows),
                "source_pages": len(sources),
                **counts,
            },
        )
        LOG.info("%s %s", stage, counts)

    pages_dir = output / "pages"
    pages_dir.mkdir(exist_ok=True)
    pools = {s: set() for s in sources}
    page_status = []
    for number, source in enumerate(sources):
        path = pages_dir / (hashlib.sha256(source.encode()).hexdigest() + ".json.gz")
        if path.exists():
            saved = read(path)
        else:
            try:
                english = article(api, "en", source)
            except ValueError as exc:
                if not str(exc).startswith("Missing article:"):
                    raise
                saved = {
                    "source": source,
                    "status": "MISSING_ENGLISH_PAGE",
                    "articles": [],
                    "error": str(exc),
                }
            else:
                articles = [english]
                qid = english["qid"]
                title = None
                if qid:
                    api.entities_for({qid})
                    title = (
                        api.entities[qid]["sitelinks"].get("jawiki", {}).get("title")
                    )
                english["japanese_counterpart"] = title
                if title:
                    japanese = article(api, "ja", title)
                    if japanese["qid"] != qid:
                        raise ValueError(f"Language counterpart QIDs differ: {source}")
                    articles.append(japanese)
                saved = {
                    "source": source,
                    "status": "RESOLVED" if qid else "NO_PAGE_QID",
                    "articles": articles,
                }
            save(path, saved)
            save(metadata_path, api.entities)
        if saved["source"] != source:
            raise ValueError(f"Page cache source differs: {source}")
        pools[source] = page_candidate_ids(saved["articles"])
        page_status.append(
            {
                "source": source,
                "status": saved["status"],
                "mentions": len(by_page[source]),
                "linked_qids": len(pools[source]),
                "articles": [
                    {
                        k: a.get(k)
                        for k in (
                            "language",
                            "title",
                            "pageid",
                            "qid",
                            "revision",
                            "url",
                        )
                    }
                    for a in saved["articles"]
                ],
            }
        )
        progress("COLLECT_PAGES", completed=number + 1, total=len(sources))
    save(output / "page_status.json", page_status)

    evidence_path = output / "candidate_evidence.json.gz"
    if evidence_path.exists():
        evidence = read(evidence_path)
        cached_pools = {p: set(ids) for p, ids in evidence["page_pools"].items()}
        if cached_pools != pools or evidence.get("daniel_name_lookups"):
            raise ValueError(
                "Cached page candidates include non-page QIDs; use a new run"
            )
        if (output / "page_matches.json.gz").exists() and evidence.get(
            "page_candidate_scope"
        ) != PAGE_CANDIDATE_SCOPE:
            raise ValueError("Historical page matches cannot be resumed")
    elif (output / "page_matches.json.gz").exists():
        raise ValueError("Page matches have no verified candidate-scope evidence")
    # S2T section 3 correction: the pool is reconstructed from page links.
    # Never import historical name-search pools or their frozen matched IDs.
    save(
        evidence_path,
        {
            "page_candidate_scope": PAGE_CANDIDATE_SCOPE,
            "page_pools": {p: sorted(ids) for p, ids in pools.items()},
            "daniel_name_lookups": [],
        },
    )
    all_page_ids = set().union(*pools.values())
    progress("PAGE_CANDIDATE_METADATA", candidate_qids=len(all_page_ids))
    # Fetch only missing IDs: BigQuery has already populated the saved metadata.
    # Preserve each newly fetched batch if a later public request fails.
    for offset in range(0, len(ids := sorted(all_page_ids - api.entities.keys())), 500):
        api.entities_for(set(ids[offset : offset + 500]))
        save(metadata_path, api.entities)
        progress(
            "PAGE_CANDIDATE_METADATA",
            completed=min(offset + 500, len(ids)),
            total=len(ids),
        )
    api.hierarchy(all_page_ids)
    save(metadata_path, api.entities)

    page_checkpoint = output / "page_matches.json.gz"
    if page_checkpoint.exists():
        rows = read(page_checkpoint)
    else:
        for row in rows:
            if row["raw"]["entity_group"] == "DATE":
                date = normalize_date(row["raw"]["word"])
                row["date"] = date
                if "value" in date:
                    row.update(
                        assigned_id="DATE:" + date["value"],
                        matched_stage="DATE_NORMALIZED",
                    )
                else:
                    row.update(
                        assigned_id="SYN_DATE_" + row["mention_id"][8:32],
                        matched_stage="SYNTHETIC",
                        unresolved_reason=date["error"],
                    )
        worker_pids = set()
        for number, (source, worker_pid, matched) in enumerate(
            match_pages(by_page, pools, api.entities, page_workers)
        ):
            for row in matched:
                rows[row["input_row_number"]] = row
            worker_pids.add(worker_pid)
            progress(
                "PAGE_MATCHING",
                completed=number + 1,
                total=len(sources),
                workers=page_workers,
                worker_pids=sorted(worker_pids),
                last_source=source,
            )
        save(page_checkpoint, rows)
    # Freeze only after every page result has been collected, regardless of order.
    frozen = sorted(
        {
            r["assigned_id"]
            for r in rows
            if r.get("matched_stage") == "PAGE_DIRECT_WIKIDATA"
        }
    )
    index = NameIndex(frozen, api.entities)
    cached = {}
    for number, row in enumerate(rows):
        if "assigned_id" not in row:
            word = row["raw"]["word"]
            if word not in cached:
                cached[word] = index.find(word, "MISC", 0.8)
            assign(row, cached[word], api.entities, "ALREADY_MATCHED")
        if number % 10000 == 0:
            progress("ALREADY_MATCHED", completed=number, total=len(rows))
    del index, cached
    reference_path = output / "reference_manifest.json"
    reference = read(reference_path) if reference_path.exists() else None
    world_path = (
        output / "world.json.gz" if reference else BASE / "fresh_wwii_names.json.gz"
    )
    expected = (
        reference["world_sha256"]
        if reference
        else read(BASE / "run_manifest.json")["outputs"][world_path.name]
    )
    assert digest(world_path) == expected
    world = read(world_path)
    world_index = NameIndex(sorted(world), world)
    cached = {}
    for number, row in enumerate(rows):
        if "assigned_id" not in row and (word := row["raw"]["word"]) not in cached:
            cached[word] = world_index.find(word, "MISC", 0.8)
        if number % 10000 == 0:
            progress("FRESH_WWII_CANDIDATES", completed=number, total=len(rows))
    needed = {c["entity_id"] for candidates in cached.values() for c in candidates}
    for offset in range(0, len(ids := sorted(needed - api.entities.keys())), 500):
        api.entities_for(set(ids[offset : offset + 500]))
        save(metadata_path, api.entities)
        progress(
            "FRESH_WWII_METADATA", completed=min(offset + 500, len(ids)), total=len(ids)
        )
    api.hierarchy(needed)
    save(metadata_path, api.entities)
    for row in rows:
        if "assigned_id" not in row:
            assign(row, cached[row["raw"]["word"]], api.entities, "FRESH_WWII")
        if "assigned_id" not in row:
            statuses = {a["status"] for a in row["attempts"]}
            reason = next(
                (s for s in ["TYPE_MISMATCH", "TYPE_UNKNOWN"] if s in statuses),
                "NO_NAME_ABOVE_THRESHOLD",
            )
            row.update(
                assigned_id=synthetic_id(row, reason),
                matched_stage="SYNTHETIC",
                unresolved_reason=reason,
            )
        row.setdefault(
            "type_metadata",
            {
                "original_type": row["raw"]["entity_group"],
                "resolved_type": (
                    "DATE" if row.get("matched_stage") == "DATE_NORMALIZED" else None
                ),
                "type_changed": False,
                "type_source": (
                    "CALENDAR_VALIDATION"
                    if row.get("matched_stage") == "DATE_NORMALIZED"
                    else "UNRESOLVED"
                ),
            },
        )
    progress("VERIFY_AND_EXPORT")
    original_rows = input_rows()
    assert len(rows) == len(original_rows)
    assert all(
        r["raw"] == original["raw"] and r["mention_id"] == original["mention_id"]
        for r, original in zip(rows, original_rows)
    )
    synthetic = [r["assigned_id"] for r in rows if r["matched_stage"] == "SYNTHETIC"]
    assert len(synthetic) == len(set(synthetic))
    assert all(not r["attempts"] for r in rows if r["raw"]["entity_group"] == "DATE")
    assert all(r["score"] >= 0.8 for r in rows if r["assigned_id"].startswith("Q"))
    assert all(
        len(r["attempts"]) == 3
        for r in rows
        if r["raw"]["entity_group"] != "DATE" and r["matched_stage"] == "SYNTHETIC"
    )
    summary = {
        "mentions": len(rows),
        "source_pages": len(sources),
        "types": dict(Counter(r["raw"]["entity_group"] for r in rows)),
        "stages": dict(Counter(r["matched_stage"] for r in rows)),
        "unresolved": dict(
            Counter(
                r["unresolved_reason"]
                for r in rows
                if r["matched_stage"] == "SYNTHETIC"
            )
        ),
        "distinct_matched_qids": len(
            {r["assigned_id"] for r in rows if r["assigned_id"].startswith("Q")}
        ),
        "page_statuses": dict(Counter(p["status"] for p in page_status)),
        "english_articles": sum(
            a["language"] == "en" for p in page_status for a in p["articles"]
        ),
        "japanese_articles": sum(
            a["language"] == "ja" for p in page_status for a in p["articles"]
        ),
        "fresh_wwii_ids": len(world),
        "frozen_page_matched_qids": len(frozen),
        "article_name_extraction": False,
        "threshold": 0.8,
        "type_changes": sum(r["type_metadata"]["type_changed"] for r in rows),
        "by_type": {
            t: dict(
                Counter(
                    r["matched_stage"] for r in rows if r["raw"]["entity_group"] == t
                )
            )
            for t in sorted({r["raw"]["entity_group"] for r in rows})
        },
    }
    save(output / "matches.json.gz", rows)
    save(output / "summary.json", summary)
    evidence = read(evidence_path)
    evidence["frozen_matched_ids"] = frozen
    save(evidence_path, evidence)
    save(output / "request_evidence.json.gz", api.requests)
    with gzip.open(
        output / "matches.csv.gz", "wt", encoding="utf-8", newline=""
    ) as stream:
        fields = [
            "input_row_number",
            "mention_id",
            "Source",
            "word",
            "entity_group",
            "assigned_id",
            "matched_stage",
            "matched_name",
            "score",
            "unresolved_reason",
            "date_value",
            "date_precision",
            "resolved_type",
            "type_changed",
            "type_source",
            "wikidata_direct_types",
        ]
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {k: row["raw"].get(k, row.get(k, "")) for k in fields}
                | {
                    "date_value": row.get("date", {}).get("value", ""),
                    "date_precision": row.get("date", {}).get("precision", ""),
                    **{
                        k: row["type_metadata"].get(k, "")
                        for k in ("resolved_type", "type_changed", "type_source")
                    },
                    "wikidata_direct_types": "|".join(
                        row["type_metadata"].get("wikidata_direct_types", [])
                    ),
                }
            )
    save(
        output / "manifest.json",
        {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "input_url": URL,
            "input_sha256": INPUT_SHA256,
            "threshold": 0.8,
            "seed": SEED,
            "page_candidate_scope": PAGE_CANDIDATE_SCOPE,
            "execution": {"page_workers": page_workers},
            "code_sha256": {
                p.name: digest(p)
                for p in [
                    Path(__file__),
                    HERE / "direct_wikidata_pilot.py",
                    HERE / "bilingual_page_pilot.py",
                    HERE / "generate_candidates.py",
                ]
            },
            "fresh_wwii_snapshot": str(world_path),
            "fresh_wwii_sha256": digest(world_path),
            "reference": reference,
            "outputs": {
                p.name: digest(p)
                for p in output.iterdir()
                if p.is_file() and p.name != "progress.json"
            },
            "page_evidence": {p.name: digest(p) for p in pages_dir.glob("*.json.gz")},
            "limits": [
                "Counts are not accuracy measurements. Existing trigram/type/homonym errors remain.",
                "Only source EN/JA page QIDs and direct page hyperlinks; no global name lookups or independent name extraction.",
                (
                    "WWII membership uses the agreed same-day query population; names/types use the recorded BigQuery snapshot."
                    if reference
                    else "The fresh same-day WWII snapshot is the agreed query population, not all Wikidata."
                ),
            ],
        },
    )
    progress("COMPLETE", summary=summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--page-workers", type=int, default=2)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    for retry in range(20):
        try:
            result = run(args.output, page_workers=args.page_workers)
            update_report(args.output, result)
            print(json.dumps(result, indent=2))
            break
        except (requests.RequestException, RuntimeError) as exc:
            # Retry only public-service failures; validation errors must stop.
            if isinstance(exc, RuntimeError) and not str(exc).startswith(
                "Request failed after retries:"
            ):
                raise
            if retry == 19:
                save(
                    args.output / "failure.json", {"error": str(exc), "retries": retry}
                )
                raise
            delay = min(300, 60 * (retry + 1))
            last = read(args.output / "progress.json")
            save(
                args.output / "progress.json",
                {
                    "stage": "WAITING_FOR_PUBLIC_SERVICE",
                    "last_progress": last,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "retry": retry + 1,
                    "retry_delay_seconds": delay,
                    "error": str(exc),
                },
            )
            LOG.warning(
                "Public service unavailable; resume checkpoints in %ss: %s", delay, exc
            )
            time.sleep(delay)
