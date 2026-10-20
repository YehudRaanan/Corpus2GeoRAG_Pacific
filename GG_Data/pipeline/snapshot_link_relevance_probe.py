"""Test actual page-link relevance, without using Daniel's entity assignments.

Approved 20 October 2026: both counts use the saved Wikipedia snapshot;
Daniel supplies the full source-page scope only. Four missing source titles
remain explicit incomplete coverage. This diagnostic changes no model rows,
matching decisions, Event rules, or filters. Earlier mention-based ratios do
not test this measure. Population S2T sections 4/5 remain unchanged.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from GG_Data.pipeline.poc import ROOT, digest, read_json

CACHE = Path.home() / ".cache/geoai_wikipedia_dump_20261018"
SNAPSHOT = Path.home() / ".cache/geoai_full_daniel_dump_bigquery_20261018"
BASE = ROOT / "GG_Data/pipeline/outputs"


def sql_string(value: str) -> bytes:
    """Encode the saved MySQL dump's quoted title representation."""
    escapes = {
        "\\": "\\\\",
        "'": "\\'",
        "\0": "\\0",
        "\n": "\\n",
        "\r": "\\r",
        "\x1a": "\\Z",
    }
    return ("'" + "".join(escapes.get(c, c) for c in value) + "'").encode()


def aliases(cache: Path, date: str, qids: set[str]) -> dict[str, str]:
    """Follow the saved resolver's namespace-0 redirect paths, in reverse.

    Include every alias, not only aliases seen in Daniel's scoped links. This
    prevents undercounting the global denominator. No name similarity is used.
    """

    def parquet(table: str) -> Path:
        paths = list(cache.glob(f"enwiki-{date}-{table}.sql.gz.*.parquet"))
        if len(paths) != 1:
            raise ValueError(f"Expected one saved {table} table")
        path = paths[0]
        if digest(path) != read_json(path.with_suffix(".json"))["sha256"]:
            raise ValueError(f"Changed saved {table} table")
        return path

    props, pages, redirects = (parquet(t) for t in ("page_props", "page", "redirect"))
    identities = pq.read_table(props, filters=[("qid", "in", sorted(qids))]).to_pylist()
    if {r["qid"] for r in identities} != qids:
        raise ValueError("A selected QID has no English snapshot page")
    ids = {r["pageid"]: r["qid"] for r in identities}
    canonical = pq.read_table(pages, filters=[("pageid", "in", list(ids))]).to_pylist()
    if len(canonical) != len(ids) or any(r["is_redirect"] for r in canonical):
        raise ValueError("Selected QID page is missing or a redirect")
    result = {r["title"]: ids[r["pageid"]] for r in canonical}
    frontier = dict(result)
    for _ in range(20):  # Same maximum path length as resolve_sql().
        rows = pq.read_table(
            redirects, filters=[("title", "in", list(frontier))]
        ).to_pylist()
        if not rows:
            return result
        target = {r["pageid"]: frontier[r["title"]] for r in rows}
        sources = pq.read_table(
            pages, filters=[("pageid", "in", list(target))]
        ).to_pylist()
        # Same namespace-0 source JOIN as resolve_sql(). The redirect table
        # filters target namespace and can also contain non-article sources.
        if any(not r["is_redirect"] for r in sources):
            raise ValueError("Redirect source differs from saved page table")
        next_frontier = {}
        for row in sources:
            title, qid = row["title"], target[row["pageid"]]
            if title in result and result[title] != qid:
                raise ValueError("Redirect alias has conflicting QIDs")
            if title not in result:
                next_frontier[title] = qid
        result.update(next_frontier)
        if not next_frontier:
            return result
        frontier = next_frontier
    raise ValueError("Redirect path reaches the saved resolver's depth limit")


def dump_blocks(path: Path, table: str, update, block_size: int = 8 * 1024 * 1024):
    """Stream verified dump bytes; never unpack the full link file to disk.

    Non-selected rows need no SQL tokenization: the full compressed-file SHA1,
    gzip CRC, schema, completed footer and independently saved row count are
    checked before any result is published. Blocks end at a line boundary.
    """
    receipt = read_json(path.with_name(path.name + ".verified.json"))
    if path.stat().st_size != receipt["size"]:
        raise ValueError("Raw dump size changed")
    carry, rows, last_update = b"", 0, time.monotonic()
    tail = b""
    with path.open("rb") as raw, gzip.GzipFile(fileobj=raw) as stream:
        header = stream.peek(4096)
        if f"CREATE TABLE `{table}` (".encode() not in header:
            raise ValueError("Unexpected dump header")
        while chunk := stream.read(block_size):
            data = carry + chunk
            cut = data.rfind(b"\n") + 1
            block, carry = data[:cut], data[cut:]
            rows += block.count(b"\n(") + int(block.startswith(b"("))
            tail = (tail + block)[-4096:]
            yield block
            if time.monotonic() - last_update >= 15:
                update(
                    compressed_bytes=raw.tell(),
                    compressed_total=receipt["size"],
                    scanned_rows=rows,
                )
                last_update = time.monotonic()
        if carry.strip() or b"-- Dump completed on " not in tail:
            raise ValueError("Incomplete SQL dump")
    with path.open("rb") as raw:
        if hashlib.file_digest(raw, "sha1").hexdigest() != receipt["sha1"]:
            raise ValueError("Raw dump checksum changed")
    converted = list(path.parent.glob(path.name + ".*.json"))
    counts = [
        read_json(p)["scanned_rows"]
        for p in converted
        if "scanned_rows" in read_json(p)
    ]
    if not counts or any(expected != rows for expected in counts):
        raise ValueError(f"Dump row coverage differs: {rows} versus {counts}")
    update(
        compressed_bytes=receipt["size"],
        compressed_total=receipt["size"],
        scanned_rows=rows,
        verified=True,
    )


def link_targets(blocks, title_qids: dict[str, str]) -> dict[int, str]:
    encoded = {sql_string(title): qid for title, qid in title_qids.items()}
    result = {}
    for block in blocks:
        for line in block.splitlines():
            if not line.startswith(b"("):
                continue
            target, namespace, title = line[1:-2].split(b",", 2)
            if namespace == b"0" and title in encoded:
                result[int(target)] = encoded[title]
    return result


def linked_pages(blocks, targets: dict[int, str]) -> dict[str, set[int]]:
    """Union canonical and redirect targets, counting each source page once."""
    if not targets:
        raise ValueError("No selected link target IDs")
    pattern = re.compile(
        rb"^\((\d+),0,("
        + b"|".join(str(t).encode() for t in sorted(targets))
        + rb")\)[,;]$",
        re.MULTILINE,
    )
    pages = defaultdict(set)
    for block in blocks:
        for match in pattern.finditer(block):
            pages[targets[int(match[2])]].add(int(match[1]))
    return pages


def run() -> dict:
    output = BASE / "poc_10k_misc_snapshot_link_relevance_20261020"
    if output.exists():
        raise ValueError("Keep existing diagnostic outputs unchanged")
    manifest_path = SNAPSHOT / "page_snapshot_manifest.json"
    manifest = read_json(manifest_path)
    date = manifest["dump_date"]  # Version lineage, not a new hardcoded source date.
    source_path = CACHE / "english_sources.json.gz"
    links_path = CACHE / "en_link_resolution.json.gz"
    selection_path = (
        BASE / "poc_10k_misc_incoming_links_probe_20261020/partial_analysis.json"
    )
    # The original manifest pins article files and inventory counts, rather
    # than checksums of these two intermediate caches. Verify its coverage;
    # this diagnostic records the exact intermediate-file hashes below.
    if (
        dict(Counter(r["status"] for r in read_json(links_path)))
        != manifest["link_inventory"]["en"]["resolution_counts"]
    ):
        raise ValueError("Saved source-page link coverage changed")
    if (
        digest(selection_path)
        != read_json(selection_path.parent / "report.json")["outputs"][
            selection_path.name
        ]
    ):
        raise ValueError("Saved diagnostic QID selection changed")
    selection = read_json(selection_path)["counts"]  # QIDs only; discard old counts.
    sources = read_json(source_path)
    missing = [r["source"] for r in sources if r["status"] != "RESOLVED"]
    scope = {int(r["pageid"]) for r in sources if r["status"] == "RESOLVED"}
    if len(sources) != 428 or len(missing) != 4:
        raise ValueError("Approved source coverage changed")
    output.mkdir()
    started = time.monotonic()

    def update(stage: str, **values) -> None:
        progress = {
            "stage": stage,
            "pid": os.getpid(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - started, 1),
            **values,
        }
        (output / "progress.json").write_text(
            json.dumps(progress, indent=2), encoding="utf-8"
        )
        print(json.dumps(progress), flush=True)

    try:
        update("RESOLVING_SNAPSHOT_ALIASES", selected_qids=len(selection))
        names = aliases(CACHE, date, {r["qid"] for r in selection})
        (output / "aliases.json").write_text(
            json.dumps(names, indent=2), encoding="utf-8"
        )
        update("SCANNING_LINKTARGET", alias_titles=len(names))
        targets = link_targets(
            dump_blocks(
                CACHE / f"enwiki-{date}-linktarget.sql.gz",
                "linktarget",
                lambda **v: update("SCANNING_LINKTARGET", **v),
            ),
            names,
        )
        if set(targets.values()) != {r["qid"] for r in selection}:
            raise ValueError("A selected QID has no dumped link target")
        (output / "targets.json").write_text(
            json.dumps(targets, indent=2), encoding="utf-8"
        )
        update("SCANNING_GLOBAL_PAGELINKS", selected_target_ids=len(targets))
        pages = linked_pages(
            dump_blocks(
                CACHE / f"enwiki-{date}-pagelinks.sql.gz",
                "pagelinks",
                lambda **v: update("SCANNING_GLOBAL_PAGELINKS", **v),
            ),
            targets,
        )
        # Independent agreement with the saved scoped resolver is mandatory.
        reference = defaultdict(set)
        for row in read_json(links_path):
            if row["status"] == "RESOLVED" and row["qid"] in set(targets.values()):
                reference[row["qid"]].add(int(row["source"]))
        rows = []
        for row in selection:
            qid = row["qid"]
            numerator_pages = pages[qid] & scope
            if numerator_pages != reference[qid]:
                raise ValueError(
                    f"Actual scoped links disagree with saved resolution: {qid}"
                )
            numerator, denominator = len(numerator_pages), len(pages[qid])
            if denominator == 0 or numerator > denominator:
                raise ValueError(f"Invalid subset count: {qid}")
            rows.append(
                {
                    "qid": qid,
                    "name": row["title"],
                    "scope_linking_pages": numerator,
                    "all_linking_pages": denominator,
                    "relevance": numerator / denominator,
                    "scope_page_ids": sorted(numerator_pages),
                }
            )
        rows.sort(key=lambda r: (-r["relevance"], r["qid"]))
        with (output / "scores.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        with gzip.open(
            output / "linking_page_ids.json.gz", "wt", encoding="utf-8"
        ) as stream:
            json.dump({qid: sorted(ids) for qid, ids in pages.items()}, stream)
        report = {
            "status": "COMPLETE_DIAGNOSTIC_INCOMPLETE_SOURCE_COVERAGE",
            "dump_date": date,
            "wiki": "enwiki",
            "formula": "distinct actual linking pages within Daniel full source-page scope / all distinct actual linking pages",
            "link_rules": "namespace-0 source and target pages, including template/navigation links; target redirects resolved; source page IDs counted once per QID",
            "source_titles": len(sources),
            "resolved_source_titles": len(sources) - len(missing),
            "distinct_resolved_source_pages": len(scope),
            "missing_source_titles": missing,
            "selected_qids": len(selection),
            "rows": rows,
            "matches_changed": False,
            "filter_applied": False,
            "network_requests": 0,
            "verified_dumps": {
                table: read_json(CACHE / f"enwiki-{date}-{table}.sql.gz.verified.json")
                for table in ("linktarget", "pagelinks")
            },
            "limits": [
                "English diagnostic sample only, not an all-language measure.",
                "Four missing source titles make the scoped numerator incomplete.",
                "Page-link concentration is not identity-match confidence; no cutoff is approved.",
            ],
            "inputs": {
                str(p): digest(p)
                for p in (
                    manifest_path,
                    source_path,
                    links_path,
                    selection_path,
                    Path(__file__),
                )
            },
            "outputs": {
                p.name: digest(p) for p in output.iterdir() if p.name != "progress.json"
            },
        }
        (output / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        update("COMPLETE", scored_qids=len(rows), report=str(output / "report.json"))
        return report
    except Exception as exc:
        update("STOPPED_FOR_CONSULTATION", error=f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    run()
