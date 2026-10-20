"""Read existing CirrusSearch counts; never modify matching or model tables.

Exploratory test approved 20 October 2026, after the stopped Event benchmark.
Population S2T sections 4/5 remain unchanged. This is a current-index diagnostic,
not snapshot-aligned evidence and not an approved automatic exclusion rule.
Schema: https://www.mediawiki.org/wiki/Extension:CirrusSearch/Schema
Debug interface (unstable): https://www.mediawiki.org/wiki/Help:CirrusSearch/Debug
"""

from __future__ import annotations

import csv
import gzip
import json
import random
import time
from collections import Counter
from datetime import datetime, timezone

import requests

from GG_Data.pipeline.poc import ROOT, digest, read_json

BASE = ROOT / "GG_Data/pipeline/outputs"
SEED = 20261020


def indexed_counts(payload: dict, expected: set[str]) -> dict:
    """Fail on source/schema drift; missing indexed values must never mean zero."""
    if "error" in payload or "warnings" in payload or "continue" in payload:
        raise ValueError("Incomplete or unexpected CirrusSearch response")
    result = {}
    for page in payload["query"]["pages"]:
        if "missing" in page or page.get("ns") != 0:
            raise ValueError(f"Missing/changed article: {page.get('title')}")
        docs = page.get("cirrusdoc", [])
        if len(docs) != 1:
            raise ValueError(f"Expected one indexed document: {page['title']}")
        doc = docs[0]
        source = doc["source"]
        qid = source["wikibase_item"]
        count = source["incoming_links"]
        if qid not in expected or qid in result or type(count) is not int or count < 0:
            raise ValueError(f"Unexpected QID/count: {qid} {count}")
        result[qid] = {
            "title": page["title"],
            "page_id": page["pageid"],
            "incoming_links": count,
            "index": doc["index"],
            "indexed_article_revision_timestamp": source.get("timestamp"),
        }
    if set(result) != expected:
        raise ValueError("Response did not cover all requested QIDs")
    return result


def run() -> dict:
    output = BASE / "poc_10k_misc_incoming_links_probe_20261020"
    if output.exists():
        raise ValueError("Keep previous probe evidence unchanged")
    mentions = BASE / "poc_10k/mentions.json.gz"
    records_path = (
        BASE / "poc_10k_entities_snapshot_first_20261020/full_records.json.gz"
    )
    for path in (mentions, records_path):
        if (
            digest(path)
            != read_json(path.parent / "manifest.json")["outputs"][path.name]
        ):
            raise ValueError(f"Frozen input changed: {path}")
    rows = read_json(mentions)
    records = read_json(records_path)
    population = [
        r
        for r in rows
        if r["raw"]["entity_group"] == "MISC"
        and str(r.get("entity_id", "")).startswith("Q")
    ]
    counts = Counter(r["entity_id"] for r in population)
    links = {q: records[q]["entity"].get("sitelinks", {}) for q in sorted(counts)}
    eligible = [q for q in links if any(s in links[q] for s in ("enwiki", "jawiki"))]
    selected = ["Q5287", "Q750553"]  # Known problem matches, not new identities.
    selected += sorted(
        (q for q in eligible if q not in selected), key=lambda q: (-counts[q], q)
    )[:6]
    selected += random.Random(SEED).sample(
        [q for q in eligible if q not in selected], 20 - len(selected)
    )
    if not set(selected) <= set(eligible):
        raise ValueError("A diagnostic control has no saved EN/JA page")
    output.mkdir()
    report = {
        "status": "FETCHING_COUNTS",
        "seed": SEED,
        "scope": "DIAGNOSTIC_ONLY_NO_ASSIGNMENTS_OR_FILTER_CHANGED",
        "count_source": "CURRENT_CIRRUSSEARCH_INDEX_NOT_AGREED_HISTORICAL_SNAPSHOT",
        "count_scope": "PER_WIKI_NOT_ALL_LANGUAGES",
        "selection": "two known problems + six frequent eligible QIDs + twelve random",
        "misc_matched_mentions": len(population),
        "misc_distinct_qids": len(counts),
        "qids_with_saved_en_or_ja_page": len(eligible),
        "qids_without_saved_en_or_ja_page": len(counts) - len(eligible),
        "inputs": {
            str(p.relative_to(ROOT)): digest(p) for p in (mentions, records_path)
        },
        "requests": [],
        "rows": [],
    }

    def save() -> None:
        (output / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )

    save()
    try:
        measured = {}
        for site in ("enwiki", "jawiki"):
            qids = [q for q in selected if site in links[q]]
            if not qids:
                continue
            if measured:
                time.sleep(5)
            url = f"https://{site[:2]}.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "prop": "cirrusdoc",
                "format": "json",
                "formatversion": 2,
                "titles": "|".join(links[q][site]["title"] for q in qids),
            }
            # One attempt: unexpected data/network failures stop under the POC rule.
            response = requests.get(
                url,
                params=params,
                timeout=45,
                headers={
                    "User-Agent": "GeoAI-entity-filter-pilot/0.1 (small research sample)"
                },
            )
            raw = output / f"{site}_response.json.gz"
            with gzip.open(raw, "wb") as stream:
                stream.write(response.content)
            report["requests"].append(
                {
                    "url": response.url,
                    "http_status": response.status_code,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "raw_file": raw.name,
                    "sha256": digest(raw),
                }
            )
            save()
            response.raise_for_status()
            measured[site] = indexed_counts(response.json(), set(qids))
        for qid in selected:
            original = [r for r in population if r["entity_id"] == qid]
            item = records[qid]["entity"]
            report["rows"].append(
                {
                    "qid": qid,
                    "name": item.get("labels", {}).get("en", {}).get("value"),
                    "original_names": sorted({r["raw"]["word"] for r in original}),
                    "daniel_mentions_in_10k": counts[qid],
                    "daniel_pages_in_10k": len({r["raw"]["Source"] for r in original}),
                    "counts": {
                        s: measured.get(s, {}).get(qid) for s in ("enwiki", "jawiki")
                    },
                }
            )
        # Sensitivity only. No limit is selected and no identity is rejected.
        en = [r for r in report["rows"] if r["counts"]["enwiki"] is not None]
        report["english_threshold_sensitivity"] = [
            {
                "limit": x,
                "qids_above": sum(
                    r["counts"]["enwiki"]["incoming_links"] > x for r in en
                ),
                "measured_qids": len(en),
            }
            for x in (1000, 5000, 10000, 20000, 50000)
        ]
        with (output / "counts.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "qid",
                    "name",
                    "daniel_mentions",
                    "enwiki_incoming_links",
                    "jawiki_incoming_links",
                ]
            )
            for row in report["rows"]:
                writer.writerow(
                    [
                        row["qid"],
                        row["name"],
                        row["daniel_mentions_in_10k"],
                        *[
                            (row["counts"][s] or {}).get("incoming_links")
                            for s in ("enwiki", "jawiki")
                        ],
                    ]
                )
        report["status"] = "COUNTS_RETRIEVED_NO_FILTER_APPLIED"
    except Exception as exc:
        report["status"] = "STOPPED_FOR_CONSULTATION"
        report["error"] = f"{type(exc).__name__}: {exc}"
        save()
        raise
    report["outputs"] = {
        p.name: digest(p) for p in output.iterdir() if p.name != "report.json"
    }
    save()
    return report


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {k: result[k] for k in ("status", "english_threshold_sensitivity")},
            indent=2,
        )
    )
