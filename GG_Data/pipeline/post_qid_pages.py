"""Import only the frozen used Wikipedia revisions; no recovery or network work."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from GG_Data.pipeline.poc import digest


def populate(
    revisions: list[dict], page_ids: set[int] | None = None, wiki_site: str = "enwiki"
) -> list[dict]:
    rows, seen = [], set()
    if wiki_site != "enwiki":
        raise ValueError("The frozen pilot contains enwiki revisions only")
    for revision in revisions:
        page_id, revision_id = revision["page_id"], revision["revision_id"]
        if page_ids is not None and page_id not in page_ids:
            continue
        if (
            type(page_id) is not int
            or type(revision_id) is not int
            or min(page_id, revision_id) <= 0
        ):
            raise ValueError("Invalid Wikipedia page/revision identity")
        key = wiki_site, page_id, revision_id
        if key in seen:
            raise ValueError(f"Duplicate used revision: {key}")
        seen.add(key)
        rows.append(
            dict(
                wiki_site=wiki_site,
                wiki_page_id=page_id,
                revision_id=revision_id,
                title=revision.get("wiki_title"),
                language="en",
                revision_timestamp=revision.get("revision_timestamp"),
                revision_url=f"https://en.wikipedia.org/w/index.php?oldid={revision_id}",
                content_sha256=revision.get("sha256"),
                retrieval_utc=revision.get("retrieval_utc"),
                revision_metadata_status=revision.get(
                    "revision_metadata_status", "NOT_PROVIDED"
                ),
                about_entity_id=None,
                raw_reference=dict(revision),
                sources=[
                    dict(
                        provider="WIKIPEDIA",
                        file=revision.get("evidence_path"),
                        metadata_file=revision.get("metadata_evidence_path"),
                    )
                ],
            )
        )
    if page_ids is not None and page_ids != {r["wiki_page_id"] for r in rows}:
        raise ValueError("Selected page has no used revision")
    return sorted(
        rows, key=lambda r: (r["wiki_site"], r["wiki_page_id"], r["revision_id"])
    )


def run(input_dir: Path, output: Path, page_ids: set[int] | None = None) -> dict:
    import pyarrow.parquet as pq

    source = input_dir / "revisions.parquet"
    rows = populate(pq.read_table(source).to_pylist(), page_ids)
    for row in rows:
        raw = row["raw_reference"]
        for field in ("wikitext_path", "evidence_path", "metadata_evidence_path"):
            if raw.get(field):
                path = Path(raw[field])
                if not path.is_file():
                    raise ValueError(f"Missing saved revision evidence: {path}")
                actual = digest(path)
                if field == "wikitext_path" and raw.get("sha256") != actual:
                    raise ValueError(f"Wikitext hash differs: {path}")
                row["sources"].append(dict(file=str(path), sha256=actual, role=field))
    output.mkdir(parents=True, exist_ok=False)
    with gzip.open(output / "wiki_pages.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(rows, stream, ensure_ascii=False)
    manifest = dict(
        input_sha256=digest(source),
        row_count=len(rows),
        page_count=len({r["wiki_page_id"] for r in rows}),
        outputs={"wiki_pages.json.gz": digest(output / "wiki_pages.json.gz")},
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-ids", type=int, nargs="+")
    args = parser.parse_args()
    run(args.input_dir, args.output, set(args.page_ids) if args.page_ids else None)


if __name__ == "__main__":
    main()
