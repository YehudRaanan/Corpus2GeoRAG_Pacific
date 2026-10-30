"""Separate full-population exact-name/type Agent export.

Source keys define the pinned page scope. Internal page indices are not
Wikipedia page IDs. No entity matching, decision model or geocoding runs here.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pyarrow.parquet as pq

from GG_Data.pipeline.poc import RAW_COLUMNS, ROOT, digest

LOG = logging.getLogger(__name__)
INPUT_SHA256 = "47141678ff0f67ef16c070b4beb58bb8b1273a1635d25fea875e241e48bdd006"


def native_graph():
    # Reuse the script module's existing sibling import convention.
    sys.path.insert(0, str(ROOT / "GG_Data/entity_resolution"))
    try:
        from GG_Data.entity_resolution import native_corpus_graphs

        return native_corpus_graphs
    finally:
        sys.path.pop(0)


def entity_id(name: str, kind: str) -> str:
    key = json.dumps([name, kind], ensure_ascii=False, separators=(",", ":"))
    return "ent:" + hashlib.sha256(key.encode("utf-8")).hexdigest()


def write_array(path: Path, rows: Iterable[dict]) -> int:
    """Stream one immutable JSON array; interrupted writes keep their .part file."""
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_name(path.name + ".part")
    opener = gzip.open if path.suffix == ".gz" else open
    kwargs = {"compresslevel": 1} if path.suffix == ".gz" else {}
    count = 0
    with opener(temporary, "xt", encoding="utf-8", **kwargs) as stream:
        stream.write("[")
        for row in rows:
            if count:
                stream.write(",")
            stream.write(
                json.dumps(
                    row, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                )
            )
            count += 1
        stream.write("]\n")
    temporary.replace(path)
    return count


def write_object(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_name(path.name + ".part")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    temporary.replace(path)


def prepare(
    input_path: Path, output: Path, *, expected_sha256: str = INPUT_SHA256
) -> dict:
    """Preserve every raw row and build exact identities plus binary membership."""
    if output.exists():
        raise FileExistsError(f"Preserve existing output: {output}")
    actual = digest(input_path)
    if actual != expected_sha256:
        raise ValueError(f"Input SHA256 mismatch: {actual}")
    parquet = pq.ParquetFile(input_path)
    if set(parquet.schema_arrow.names) != set(RAW_COLUMNS):
        raise ValueError("Unexpected raw input schema")
    compact = parquet.read(columns=["word", "entity_group", "Source"]).to_pandas()
    if compact.isna().any().any() or any(
        not isinstance(x, str) or not x
        for name in compact
        for x in compact[name].unique()
    ):
        raise ValueError("Every identity and source key needs a nonempty string")
    source_keys = sorted(compact.Source.unique())
    page_indices = {key: i for i, key in enumerate(source_keys)}
    scope_id = (
        "pages:"
        + hashlib.sha256(
            json.dumps(source_keys, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
    )
    keep = compact.entity_group.ne("DATE")
    rows = compact.loc[keep].rename(columns={"word": "name", "entity_group": "type"})
    rows["wiki_page_id"] = rows.Source.map(page_indices)
    rows["wiki_revision_id"] = None
    nodes, memberships, _ = native_graph().memberships(rows)
    mentions_per_key = rows.groupby(["name", "type"]).size().to_dict()
    entities = [
        dict(
            node_index=int(r.node_id),
            entity_id=entity_id(r.name, r.type),
            name=r.name,
            type=r.type,
            page_count=int(r.page_count),
            mention_count=int(mentions_per_key[(r.name, r.type)]),
        )
        for r in nodes.itertuples(index=False)
    ]
    by_key = {(r["name"], r["type"]): r["entity_id"] for r in entities}
    if len({r["entity_id"] for r in entities}) != len(entities):
        raise ValueError("Entity identity hash collision")
    if (
        shutil.disk_usage(
            output.parent if output.parent.exists() else input_path.parent
        ).free
        < 15 * 1024**3
    ):
        raise RuntimeError("Disk reserve below 15 GiB")
    output.mkdir(parents=True)
    LOG.info(
        "Prepared %s exact entities and %s memberships", len(nodes), len(memberships)
    )
    write_array(output / "entities.json.gz", entities)
    page_rows = [
        dict(
            page_index=page_indices[key],
            source_key=key,
            source_subject_qid=key if re.fullmatch(r"Q[1-9]\d*", key) else None,
            source_title=key if not re.fullmatch(r"Q[1-9]\d*", key) else None,
            wiki_page_id=None,
            revision_id=None,
            provenance_status="INPUT_SOURCE_KEY_ONLY_EXACT_REVISION_UNKNOWN",
            raw_mention_count=int(count),
        )
        for key, count in sorted(Counter(compact.Source).items())
    ]
    write_array(output / "wiki_pages.json.gz", page_rows)
    node_to_id = [r["entity_id"] for r in entities]
    write_array(
        output / "memberships.json.gz",
        (
            dict(
                entity_id=node_to_id[int(r.node_id)],
                node_index=int(r.node_id),
                page_index=int(r.wiki_page_id),
                presence_method="DANIEL_EXTRACTED_MENTION",
            )
            for r in memberships.itertuples(index=False)
        ),
    )
    membership_frame = memberships.rename(
        columns={"wiki_page_id": "page_index", "node_id": "node_index"}
    )
    native_graph().export_frame(membership_frame, output / "memberships.parquet")
    row_count = 0

    def preserved_mentions():
        nonlocal row_count
        for batch in parquet.iter_batches(batch_size=8192):
            for raw in batch.to_pylist():
                excluded = raw["entity_group"] == "DATE"
                yield dict(
                    mention_id=f"mention:{row_count}",
                    source_row_index=row_count,
                    entity_id=(
                        None if excluded else by_key[(raw["word"], raw["entity_group"])]
                    ),
                    page_index=page_indices[raw["Source"]],
                    raw=raw,
                    exclusion_reason="DATE_EXCLUDED" if excluded else None,
                )
                row_count += 1
            if row_count % 131072 == 0:
                LOG.info(
                    "Preserved %s/%s raw rows", row_count, parquet.metadata.num_rows
                )

    write_array(output / "mentions.json.gz", preserved_mentions())
    if row_count != parquet.metadata.num_rows or digest(input_path) != actual:
        raise ValueError("Raw row accounting or input SHA256 changed")
    counts = dict(
        raw_rows=row_count,
        excluded_date_rows=int((~keep).sum()),
        entities=len(entities),
        pages=len(page_rows),
        memberships=len(memberships),
    )
    manifest = dict(
        schema_version="simplified-agent-v1",
        stage="PREPARED",
        created_utc=datetime.now(timezone.utc).isoformat(),
        input=dict(
            path=str(input_path.resolve()),
            sha256=actual,
            columns=parquet.schema_arrow.names,
        ),
        page_scope_id=scope_id,
        counts=counts,
        relation_rule=dict(
            numerator="distinct_shared_source_pages",
            denominator="distinct_source_pages_containing_source",
        ),
        geography_status="PENDING_LAST_STAGE",
        outputs={p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()},
    )
    write_object(output / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("stage", choices=["prepare"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    LOG.info("Finished: %s", prepare(args.input, args.output)["counts"])


if __name__ == "__main__":
    main()
