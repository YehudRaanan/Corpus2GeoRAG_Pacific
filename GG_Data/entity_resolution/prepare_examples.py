"""Rebuild the notebook's small, source-preserving example snapshot.

Run from the repository root: python GG_Data/entity_resolution/prepare_examples.py
Uses existing local graph inputs; downloads only Daniel's pinned parquet if absent.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "GG_Data/mapping"))
from assertion_exclusions import exclusion_reason, load_exclusions  # noqa: E402
from run_relation_mapping_sanity import original_endpoints  # noqa: E402

COMMIT = "43e35453421b032fc67d426d7d16fe436574b0fa"
FILENAME = "georag_selected_v2_full_n36335_r482092353_20261016.parquet"
URL = f"https://raw.githubusercontent.com/EtzionR/Corpus2GeoRAG_Pacific/{COMMIT}/Data/{FILENAME}"
SOURCES = ["14th Indian Infantry Division", "Attack on Pearl Harbor"]
HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    raw = ROOT / "Data/external/daniel_20261017.parquet"
    raw.parent.mkdir(parents=True, exist_ok=True)
    if not raw.exists():
        urlretrieve(URL, raw)
    # Verify Git's blob ID against the uploaded file before using it.
    blob = hashlib.sha1(
        f"blob {raw.stat().st_size}\0".encode() + raw.read_bytes()
    ).hexdigest()
    if blob != "dcf304ad0dd38ca9874f3172609eb0597aa4f285":
        raise ValueError("Daniel's input does not match the pinned Git blob")
    frame = pd.read_parquet(raw)
    # Keep all rows of the chosen paragraphs, including non-person mentions.
    choices = {SOURCES[0]: [1, 6, 34], SOURCES[1]: [1, 2, 3, 8, 11]}
    records = frame[
        [int(i) in choices.get(s, []) for s, i in zip(frame.Source, frame.Index)]
    ]
    assert all(r.Text[r.start : r.end] == r.word for r in records.itertuples())

    external = ROOT / "Data/external/wwii_task_force"
    page_path = external / "article_qids.jsonl"
    pages = {}
    for line in page_path.open(encoding="utf-8"):
        row = json.loads(line)
        if row["article_title"] in SOURCES:
            pages[row["article_title"]] = row["qid"]
    assert set(pages) == set(SOURCES)

    mapping_path = ROOT / "GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.0.csv"
    mapping = {}
    for row in csv.DictReader(mapping_path.open(encoding="utf-8-sig")):
        key = (row["source"], row["source_predicate"])
        assert key not in mapping
        mapping[key] = row
    assertions = (
        ROOT
        / "GG_Data/mapping/outputs/relation-map-v1.0.0/complete_mapped_relations_v1.0.0.csv"
    )
    exclusions = load_exclusions()
    edges = []
    neighbours = defaultdict(set)
    outgoing = defaultdict(set)
    for row in csv.DictReader(assertions.open(encoding="utf-8-sig", newline="")):
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
            continue
        rule = mapping[(source, row["selected_source_predicate"])]
        assert rule["direction_to_level2"] in {"same", "reverse"}
        if rule["direction_to_level2"] == "reverse":
            a, b = b, a
        edges.append(
            (
                a,
                b,
                rule["level2_relation_id"],
                source,
                row["selected_source_predicate"],
                row["source_record_id"],
                row["observation_id"],
            )
        )
        neighbours[a].add(b)
        neighbours[b].add(a)
        outgoing[a].add(b)

    # Page scope uses incoming OR outgoing links. Ranking keeps original direction.
    pools = {title: sorted(neighbours[qid] | {qid}) for title, qid in pages.items()}
    pool_ids = set().union(*map(set, pools.values()))
    entity_path = external / "wikidata_entities.jsonl.gz"
    people = set()
    with gzip.open(entity_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            entity = json.loads(line)["entity"]
            if entity["id"] in pool_ids:
                types = [
                    c.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value", {})
                    .get("id")
                    for c in entity.get("claims", {}).get("P31", [])
                ]
                if "Q5" in types:
                    people.add(entity["id"])
    seeds = people | set(pages.values())
    nodes = seeds | {target for q in seeds for target in outgoing[q]}
    subset = [
        dict(
            zip(
                [
                    "subject",
                    "object",
                    "relation",
                    "source",
                    "source_predicate",
                    "source_record_id",
                    "observation_id",
                ],
                e,
            )
        )
        for e in edges
        if e[0] in nodes and e[1] in nodes
    ]
    entities = {}
    needed = nodes | pool_ids
    with gzip.open(entity_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            e = json.loads(line)["entity"]
            if e["id"] in needed:
                label = e.get("labels", {}).get("en", {}).get("value", "")
                aliases = [a["value"] for a in e.get("aliases", {}).get("en", [])]
                entities[e["id"]] = {
                    "label": label,
                    "aliases": aliases,
                    "is_person": e["id"] in people,
                    "revision": e.get("lastrevid"),
                    "description": e.get("descriptions", {})
                    .get("en", {})
                    .get("value", ""),
                }
    missing = sorted((nodes | pool_ids) - entities.keys())
    for qid in missing:
        entities[qid] = {
            "label": qid,
            "aliases": [],
            "is_person": False,
            "revision": None,
            "description": "metadata unavailable",
        }
    inputs = [
        raw,
        page_path,
        mapping_path,
        assertions,
        entity_path,
        ROOT / "GG_Data/mapping/ASSERTION_EXCLUSIONS.csv",
    ]
    bundle = {
        "provenance": {
            "daniel_commit": COMMIT,
            "daniel_url": URL,
            "daniel_git_blob": blob,
            "mapping_version": "relation-map-v2.1.0",
            "max_graph_depth": 1,
            "missing_metadata_ids": missing,
            "inputs_sha256": {
                p.relative_to(ROOT).as_posix(): sha256(p) for p in inputs
            },
        },
        "pages": pages,
        "page_pools": pools,
        "mentions": records.to_dict("records"),
        "entities": entities,
        "edges": subset,
    }
    output = HERE / "real_examples.json"
    output.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"Saved {len(records)} raw rows, {len(people)} people, {len(entities)} graph nodes, {len(subset)} assertions"
    )


if __name__ == "__main__":
    main()
