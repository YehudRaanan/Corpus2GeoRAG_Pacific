"""Offline threshold comparison for the three-page pilot; no assignments promoted."""

from __future__ import annotations

import argparse
import csv
import random
from collections import Counter
from pathlib import Path

from bilingual_page_pilot import choose, digest, dump, read
from direct_wikidata_pilot import BASE, SEED, clean_name, page_find
from generate_candidates import NameIndex

SOURCE = Path(__file__).parent / "runs/direct_wikidata_single_type_20261018_v2"
THRESHOLDS = (0.70, 0.75, 0.80, 0.85, 0.90, 0.95)


def run(output: Path) -> list[dict]:
    source_manifest = read(SOURCE / "manifest.json")
    for filename, expected in source_manifest["outputs"].items():
        assert digest(SOURCE / filename) == expected, filename
    article_file = BASE / "articles_and_page_inventory.json.gz"
    assert (
        digest(article_file)
        == read(BASE / "run_manifest.json")["outputs"][article_file.name]
    )
    rows = read(SOURCE / "matches.json.gz")
    metadata = read(SOURCE / "entity_metadata.json.gz")
    pools = read(SOURCE / "candidate_evidence.json.gz")["page_pools"]
    linked = {page: set() for page in pools}
    for article in read(article_file):
        linked[article["daniel_source"]].update(
            {article["qid"]} | {link["qid"] for link in article["links"]}
        )
    indexes, originals = {}, {}
    for page, ids in pools.items():
        maps, cleaned = {}, {}
        for qid in sorted(ids):
            entity = metadata[qid]
            names = sorted(set(entity.get("aliases", [])) | {entity.get("label", "")})
            maps[qid] = {clean_name(n): n for n in names if clean_name(n)}
            cleaned[qid] = {**entity, "label": "", "aliases": sorted(maps[qid])}
        originals[page] = maps
        indexes[page] = NameIndex(ids, metadata), NameIndex(ids, cleaned)

    records, decisions = [], {t: {} for t in THRESHOLDS}
    mentions = [r for r in rows if r["raw"]["entity_group"] != "DATE"]
    for row in mentions:
        raw, mention = row["raw"], row["mention_id"]
        candidates = page_find(
            *indexes[raw["Source"]],
            raw["word"],
            originals[raw["Source"]],
            threshold=min(THRESHOLDS),
        )
        for threshold in THRESHOLDS:
            decision = choose(
                [c for c in candidates if c["name_similarity"] >= threshold],
                raw["entity_group"],
                metadata,
                random.Random(f"{SEED}:PAGE_DIRECT_WIKIDATA:{mention}"),
                prefer_single_wikidata_type=True,
            )
            decisions[threshold][mention] = decision
            if threshold == 0.8:
                assert row["attempts"][0] == {
                    "stage": "PAGE_DIRECT_WIKIDATA",
                    **decision,
                }
            records.append(
                {
                    "threshold": threshold,
                    "mention_id": mention,
                    "input_row_number": row["input_row_number"],
                    "Source": raw["Source"],
                    "word": raw["word"],
                    "entity_group": raw["entity_group"],
                    "context": raw["Text"],
                    "status": decision["status"],
                    "entity_id": decision.get("entity_id", ""),
                    "matched_name": decision.get("matched_name", ""),
                    "score": decision.get("name_similarity", ""),
                    "qid_linked_from_source": decision.get("entity_id")
                    in linked[raw["Source"]],
                    "equal_top_qids": len(decision.get("tied_ids", [])),
                }
            )
    summaries = []
    baseline = decisions[0.8]
    for threshold, results in decisions.items():
        matched = [d for d in results.values() if d["status"] == "MATCHED"]
        summaries.append(
            {
                "threshold": threshold,
                "non_date_mentions": len(mentions),
                "page_matched": len(matched),
                "page_unresolved": len(mentions) - len(matched),
                "added_vs_80": sum(
                    d["status"] == "MATCHED" and baseline[m]["status"] != "MATCHED"
                    for m, d in results.items()
                ),
                "lost_vs_80": sum(
                    d["status"] != "MATCHED" and baseline[m]["status"] == "MATCHED"
                    for m, d in results.items()
                ),
                "changed_qid_vs_80": sum(
                    d["status"] == baseline[m]["status"] == "MATCHED"
                    and d["entity_id"] != baseline[m]["entity_id"]
                    for m, d in results.items()
                ),
                "exact_name_matches": sum(d["name_similarity"] == 1 for d in matched),
                "multiple_equal_top_qids": sum(len(d["tied_ids"]) > 1 for d in matched),
                "statuses": dict(Counter(d["status"] for d in results.values())),
            }
        )
    assert len(mentions) == 324
    assert next(s for s in summaries if s["threshold"] == 0.8)["page_matched"] == 263
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "decisions.json.gz", decisions)
    dump(output / "summary.json", summaries)
    with (output / "comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    dump(
        output / "manifest.json",
        {
            "source": str(SOURCE),
            "source_manifest_sha256": digest(SOURCE / "manifest.json"),
            "article_sha256": digest(article_file),
            "thresholds": THRESHOLDS,
            "code_sha256": {
                p.name: digest(p)
                for p in (
                    Path(__file__),
                    Path(__file__).with_name("direct_wikidata_pilot.py"),
                    Path(__file__).with_name("bilingual_page_pilot.py"),
                    Path(__file__).with_name("generate_candidates.py"),
                )
            },
            "seed": SEED,
            "stage": "PAGE_DIRECT_WIKIDATA_ONLY",
            "limits": [
                "Not an accuracy evaluation; no complete labelled gold set.",
                "Fallback stages are not rerun; lower-threshold WWII candidate type coverage is incomplete.",
                "Dates excluded; all 324 original non-date mentions used; no extraction or normalization change.",
                "Fixed saved candidates, current type rule, same random seed at every threshold; 80% reproduces every stored page decision.",
                "Working threshold and canonical graph unchanged.",
            ],
            "outputs": {p.name: digest(p) for p in output.iterdir()},
        },
    )
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(run(parser.parse_args().output))
