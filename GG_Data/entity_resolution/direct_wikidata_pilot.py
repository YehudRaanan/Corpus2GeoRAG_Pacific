"""Small rerun: Daniel mentions -> Wikidata; no article name extraction."""

from __future__ import annotations

import argparse
import calendar
import csv
import logging
import random
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from bilingual_page_pilot import LiveData, choose, digest, dump, read, synthetic_id
from generate_candidates import NameIndex

BASE = Path(__file__).parent / "runs/bilingual_pilot_20261018_v1"
MONTHS = {n.casefold(): i for i, n in enumerate(calendar.month_name) if n}
SEED = 20261018
PAGE_CANDIDATE_SCOPE = "SOURCE_PAGE_EN_JA_LINKS_ONLY_V1"


def page_candidate_ids(articles: list[dict]) -> set[str]:
    """Population S2T section 3: only this source page and its EN/JA links.

    A global label/alias hit proves a name exists, not that its QID occurs on
    this page. Never add such hits, extracted names or a former saved pool.
    """
    return {a["qid"] for a in articles if a.get("qid")} | {
        link["qid"] for a in articles for link in a["links"]
    }


def clean_name(text: str) -> str:
    """Delete punctuation/symbols, retain letters, digits and word spaces."""
    cleaned = " ".join(
        "".join(
            c for c in unicodedata.normalize("NFKC", text) if c.isalnum() or c.isspace()
        ).split()
    )
    return re.sub(
        r"\b(?:[A-Za-z] )+[A-Za-z]\b", lambda m: m[0].replace(" ", ""), cleaned
    )


def normalize_date(text: str) -> dict:
    text = " ".join(text.strip().split())
    if text.casefold() in MONTHS:
        return {
            "value": f"--{MONTHS[text.casefold()]:02}",
            "precision": "month_of_year",
        }
    year = re.fullmatch(r"(?:(early|mid|late)\s+)?(\d{4})", text, re.I)
    if year:
        return {"value": year[2], "precision": "year", "qualifier": year[1]}
    span = re.fullmatch(r"(\d{4})\s*[-–—]\s*(\d{2}|\d{4})", text)
    if span:
        start, end = span.groups()
        if len(end) == 2:
            end = start[:2] + end
            if int(end) < int(start):
                end = str(int(end) + 100)
        if int(start) <= int(end):
            return {"value": f"{start}/{end}", "precision": "year_range"}
        return {"error": "INVALID_DATE_RANGE"}
    formats = [
        ("%d %B %Y", "day"),
        ("%b %d, %Y", "day"),
        ("%B %d, %Y", "day"),
        ("%Y-%m-%d", "day"),
        ("%B %Y", "month"),
        ("%b %Y", "month"),
    ]
    for fmt, precision in formats:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        value = parsed.strftime("%Y-%m-%d" if precision == "day" else "%Y-%m")
        return {"value": value, "precision": precision}
    return {"error": "INVALID_OR_UNSUPPORTED_DATE"}


def page_find(
    index: NameIndex,
    cleaned: NameIndex,
    word: str,
    originals: dict,
    threshold: float = 0.8,
) -> list:
    """Original and cleaned scores are permitted only in the source-page pass."""
    best = {c["entity_id"]: c for c in index.find(word, "MISC", threshold)}
    for c in cleaned.find(clean_name(word), "MISC", threshold):
        q = c["entity_id"]
        if q not in best or c["name_similarity"] > best[q]["name_similarity"]:
            best[q] = {
                **c,
                "comparison_name": c["matched_name"],
                "comparison_query": clean_name(word),
                "matched_name": originals[q][c["matched_name"]],
                "normalization": "PAGE_ONLY_SPACE_SYMBOL_CLEANUP",
            }
    return list(best.values())


def run(output: Path, snapshot: Path | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    manifest = read(BASE / "run_manifest.json")
    for filename, expected in manifest["outputs"].items():
        assert digest(BASE / filename) == expected, filename
    if snapshot:
        for filename, expected in read(snapshot / "manifest.json")["outputs"].items():
            assert digest(snapshot / filename) == expected, filename
    rows = read(BASE / "matches.json.gz")
    articles = read(BASE / "articles_and_page_inventory.json.gz")
    api = LiveData(Path.home() / ".cache/geoai_bilingual_pilot_20261018")
    api.entities = read((snapshot or BASE) / "entity_metadata.json.gz")
    pools: dict[str, set[str]] = {}
    for a in articles:
        # Only saved page references and direct hyperlinks; never extracted_names,
        # searches, or the former phrase-derived article pool.
        pools.setdefault(a["daniel_source"], set()).update(page_candidate_ids([a]))
    for row in rows:
        for key in list(row):
            if key not in {"input_row_number", "mention_id", "raw"}:
                del row[key]
        row["attempts"] = []
    lookup = []
    # Rebuild from article links even when replaying a historical snapshot.
    # Its global-name candidate pools are not eligible source-page evidence.
    if not snapshot:
        api.hierarchy(set().union(*pools.values()))
    world = read(BASE / "fresh_wwii_names.json.gz")
    original_maps, indexes = {}, {}
    for page, pool in pools.items():
        maps, normalized = {}, {}
        for q in sorted(pool):
            entity = api.entities[q]
            originals = sorted(
                set(entity.get("aliases", [])) | {entity.get("label", "")}
            )
            maps[q] = {clean_name(n): n for n in originals if clean_name(n)}
            normalized[q] = {**entity, "label": "", "aliases": sorted(maps[q])}
        original_maps[page] = maps
        indexes[page] = (
            NameIndex(sorted(pool), api.entities),
            NameIndex(sorted(pool), normalized),
        )

    def assign(stage: str, index: NameIndex | None = None) -> None:
        for row in rows:
            if "assigned_id" in row:
                continue
            raw = row["raw"]
            candidates = (
                page_find(
                    *indexes[raw["Source"]], raw["word"], original_maps[raw["Source"]]
                )
                if index is None
                else index.find(raw["word"], "MISC", 0.8)
            )
            decision = choose(
                candidates,
                raw["entity_group"],
                api.entities,
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

    for row in rows:
        if row["raw"]["entity_group"] == "DATE":
            date = normalize_date(row["raw"]["word"])
            row["date"] = date
            if "value" in date:
                row.update(
                    assigned_id="DATE:" + date["value"], matched_stage="DATE_NORMALIZED"
                )
            else:
                row.update(
                    assigned_id="SYN_DATE_" + row["mention_id"][8:32],
                    matched_stage="SYNTHETIC",
                    unresolved_reason=date["error"],
                )
    assign("PAGE_DIRECT_WIKIDATA")
    frozen = sorted(
        {
            r["assigned_id"]
            for r in rows
            if r.get("matched_stage") == "PAGE_DIRECT_WIKIDATA"
        }
    )
    assign("ALREADY_MATCHED", NameIndex(frozen, api.entities))
    world_index = NameIndex(sorted(world), world)
    needed = {
        c["entity_id"]
        for row in rows
        if "assigned_id" not in row
        for c in world_index.find(row["raw"]["word"], "MISC", 0.8)
    }
    if snapshot:
        assert needed <= api.entities.keys(), "Snapshot lacks candidate metadata"
    else:
        api.hierarchy(needed)
    assign("FRESH_WWII", world_index)
    for row in rows:
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
    assert len(rows) == 362
    assert all(
        r["raw"] == old["raw"] for r, old in zip(rows, read(BASE / "matches.json.gz"))
    )
    synthetic = [r["assigned_id"] for r in rows if r["matched_stage"] == "SYNTHETIC"]
    assert len(synthetic) == len(set(synthetic))
    assert all(not r["attempts"] for r in rows if r["raw"]["entity_group"] == "DATE")
    summary = {
        "mentions": len(rows),
        "stages": dict(Counter(r["matched_stage"] for r in rows)),
        "unresolved": dict(
            Counter(
                r["unresolved_reason"]
                for r in rows
                if r["matched_stage"] == "SYNTHETIC"
            )
        ),
        "page_pool_sizes": {p: len(q) for p, q in pools.items()},
        "article_name_extraction": False,
        "type_changes": sum(r["type_metadata"]["type_changed"] for r in rows),
    }
    dump(output / "matches.json.gz", rows)
    dump(output / "summary.json", summary)
    dump(
        output / "candidate_evidence.json.gz",
        {
            "page_candidate_scope": PAGE_CANDIDATE_SCOPE,
            "page_pools": {p: sorted(q) for p, q in pools.items()},
            "daniel_name_lookups": lookup,
            "frozen_matched_ids": frozen,
        },
    )
    dump(output / "entity_metadata.json.gz", api.entities)
    dump(output / "request_evidence.json.gz", api.requests)
    fields = [
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
    with (output / "matches.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {k: r["raw"].get(k, r.get(k, "")) for k in fields}
                | {
                    "date_value": r.get("date", {}).get("value", ""),
                    "date_precision": r.get("date", {}).get("precision", ""),
                    **{
                        key: r["type_metadata"].get(key, "")
                        for key in ("resolved_type", "type_changed", "type_source")
                    },
                    "wikidata_direct_types": "|".join(
                        r["type_metadata"].get("wikidata_direct_types", [])
                    ),
                }
            )
    dump(
        output / "manifest.json",
        {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "source": str(BASE),
            "source_manifest_sha256": digest(BASE / "run_manifest.json"),
            "code_sha256": digest(Path(__file__)),
            "decision_code_sha256": digest(
                Path(__file__).with_name("bilingual_page_pilot.py")
            ),
            "replayed_snapshot": str(snapshot) if snapshot else None,
            "type_policy": "Compatible candidates first. If none, use a single mapped type shared by all highest-scoring candidates; preserve original Daniel type and Wikidata evidence.",
            "input_sha256": manifest["input_sha256"],
            "threshold": 0.8,
            "seed": SEED,
            "same_page_only_cleanup": True,
            "page_candidate_scope": PAGE_CANDIDATE_SCOPE,
            "titles_removed": False,
            "fresh_wwii": "Reused verified same-day 103235-ID snapshot",
            "outputs": {p.name: digest(p) for p in output.iterdir() if p.is_file()},
            "limits": [
                "Exact label/alias lookup can miss name variants.",
                "Broad saved type rules and trigram false matches remain.",
                "Date values are calendar values, not Wikidata QIDs; no missing year/day is inferred.",
                "Page candidates use only source EN/JA article links and page QIDs; no global name lookups or article phrase extraction.",
            ],
        },
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, help="Replay saved candidates offline")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    print(run(args.output, args.snapshot))
