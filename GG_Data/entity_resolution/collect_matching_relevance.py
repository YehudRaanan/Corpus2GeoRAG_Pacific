"""Select measurement QIDs without assigning identities (population S2T 3.1).

Penalties never increase similarity. The union of >=80% candidates therefore
contains every possible penalized decision. The already-matched-stage superset
uses only QIDs that occur as a page-stage name candidate somewhere in Daniel.
Actual matching still freezes ONLY the newly accepted page matches.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
from pathlib import Path

import pandas as pd

from bilingual_page_pilot import digest, read
from direct_wikidata_pilot import page_candidate_ids, page_find
from full_direct_wikidata import INPUT, INPUT_SHA256, page_indexes, save
from generate_candidates import NameIndex

LOG = logging.getLogger(__name__)


def collect(source: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Preserve previous candidate measurement selections")
    manifest = read(source / "manifest.json")
    if digest(INPUT) != INPUT_SHA256:
        raise ValueError("Daniel version changed")
    for name in ("entity_metadata.json.gz", "world.json.gz"):
        if digest(source / name) != manifest["outputs"][name]:
            raise ValueError(f"Saved candidate metadata changed: {name}")
    output.mkdir(parents=True)
    metadata = read(source / "entity_metadata.json.gz")
    frame = pd.read_parquet(INPUT, columns=["Source", "word", "entity_group"])
    frame = frame.loc[frame.entity_group != "DATE"]
    page_ids = set()
    groups = frame.groupby("Source", sort=True)
    for number, (title, group) in enumerate(groups, 1):
        path = (
            source / "pages" / (hashlib.sha256(title.encode()).hexdigest() + ".json.gz")
        )
        if digest(path) != manifest["page_evidence"][path.name]:
            raise ValueError("Page candidate source changed")
        original, cleaned, maps = page_indexes(
            page_candidate_ids(read(path)["articles"]), metadata
        )
        for word in sorted(set(group.word)):
            page_ids.update(
                c["entity_id"] for c in page_find(original, cleaned, word, maps)
            )
        if number % 20 == 0 or number == len(groups):
            save(
                output / "progress.json",
                dict(
                    stage="PAGE_CANDIDATES",
                    completed=number,
                    total=len(groups),
                    candidate_qids=len(page_ids),
                ),
            )
            LOG.info(
                "Page candidates %s/%s: %s QIDs", number, len(groups), len(page_ids)
            )
    needed = set(page_ids)
    words = sorted(set(frame.word))
    for stage, pool, names in (
        ("POSSIBLE_ALREADY_MATCHED", page_ids, metadata),
        ("WWII", None, read(source / "world.json.gz")),
    ):
        index = NameIndex(sorted(pool if pool is not None else names), names)
        for number, word in enumerate(words, 1):
            needed.update(c["entity_id"] for c in index.find(word, "MISC", 0.8))
            if number % 1000 == 0 or number == len(words):
                save(
                    output / "progress.json",
                    dict(
                        stage=stage,
                        completed=number,
                        total=len(words),
                        candidate_qids=len(needed),
                    ),
                )
                LOG.info("%s %s/%s: %s QIDs", stage, number, len(words), len(needed))
        del index
    missing = needed - metadata.keys()
    if missing:
        raise ValueError(f"Candidate metadata unavailable: {sorted(missing)}")
    save(
        output / "selection.json",
        [dict(qid=q, title=metadata[q].get("label", q)) for q in sorted(needed)],
    )
    report = dict(
        status="CANDIDATE_MEASUREMENT_SUPERSET_READY",
        population="ALL_DANIEL_MATCHING_CANDIDATES",
        page_candidate_qids=len(page_ids),
        candidate_qids=len(needed),
        distinct_words=len(words),
        identity_assignments_made=False,
        previous_decisions_reused=False,
        inputs={
            str(p): digest(p) for p in (INPUT, source / "manifest.json", Path(__file__))
        },
        outputs={"selection.json": digest(output / "selection.json")},
    )
    save(output / "manifest.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    collect(args.source, args.output)
