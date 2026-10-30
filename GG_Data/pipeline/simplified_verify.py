"""Independent full-population raw JSON and model integrity checks."""

from __future__ import annotations

import argparse
import gzip
import logging
from collections import Counter, defaultdict
from itertools import zip_longest
from pathlib import Path

import ijson
import pyarrow.parquet as pq

from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.simplified_agent import entity_id, write_object

LOG = logging.getLogger(__name__)


def verify_raw_rows(prepared: Path):
    manifest = read_json(prepared / "manifest.json")
    for name in ["entities.json.gz", "wiki_pages.json.gz", "mentions.json.gz"]:
        if digest(prepared / name) != manifest["outputs"][name]:
            raise ValueError(f"Changed artifact: {name}")
    source = Path(manifest["input"]["path"])
    if digest(source) != manifest["input"]["sha256"]:
        raise ValueError("Pinned input hash changed")
    entities = read_json(prepared / "entities.json.gz")
    by_key = {(r["name"], r["type"]): r for r in entities}
    if len(by_key) != len(entities) or any(
        k[1] == "DATE" or entity_id(*k) != r["entity_id"] for k, r in by_key.items()
    ):
        raise ValueError("Invalid exact identity population")
    pages = {
        r["source_key"]: r["page_index"]
        for r in read_json(prepared / "wiki_pages.json.gz")
    }
    appearances = defaultdict(set)
    mentions = Counter()
    parquet = pq.ParquetFile(source)
    originals = (
        r for batch in parquet.iter_batches(batch_size=8192) for r in batch.to_pylist()
    )
    total = dates = 0
    with gzip.open(prepared / "mentions.json.gz", "rb") as stream:
        for index, (raw, saved) in enumerate(
            zip_longest(originals, ijson.items(stream, "item", use_float=True))
        ):
            if (
                raw is None
                or saved is None
                or saved["raw"] != raw
                or saved["source_row_index"] != index
                or saved["mention_id"] != f"mention:{index}"
                or saved["page_index"] != pages[raw["Source"]]
            ):
                raise ValueError(f"Raw row differs at {index}")
            excluded = raw["entity_group"] == "DATE"
            key = (raw["word"], raw["entity_group"])
            expected = None if excluded else by_key[key]["entity_id"]
            if saved["entity_id"] != expected or saved["exclusion_reason"] != (
                "DATE_EXCLUDED" if excluded else None
            ):
                raise ValueError(f"Identity/exclusion differs at {index}")
            dates += int(excluded)
            total += 1
            if not excluded:
                mentions[key] += 1
                appearances[key].add(pages[raw["Source"]])
            if total % 262144 == 0:
                LOG.info(
                    "Independently verified raw rows %s/%s",
                    total,
                    parquet.metadata.num_rows,
                )
    if (
        total != parquet.metadata.num_rows
        or dates != manifest["counts"]["excluded_date_rows"]
        or set(mentions) != set(by_key)
    ):
        raise ValueError("Raw population accounting failed")
    for key, row in by_key.items():
        if (
            row["page_count"] != len(appearances[key])
            or row["mention_count"] != mentions[key]
        ):
            raise ValueError("Entity count differs from original rows")
    if digest(source) != manifest["input"]["sha256"]:
        raise ValueError("Input changed during verification")
    return dict(
        status="PASS",
        raw_rows_verified=total,
        date_rows_verified=dates,
        exact_entities_verified=len(entities),
        distinct_memberships_verified=sum(map(len, appearances.values())),
        input_sha256=manifest["input"]["sha256"],
        prepared_manifest_sha256=digest(prepared / "manifest.json"),
    )


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError(args.report)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    result = verify_raw_rows(args.prepared)
    write_object(args.report, result)
    LOG.info("Finished: %s", result)


if __name__ == "__main__":
    main()
