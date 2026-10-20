"""Measure actual page-link concentration separately for English and Japanese.

Approved 20 October 2026: both counts use the saved Wikipedia snapshot;
Daniel supplies the full source-page scope only. Four missing source titles
remain explicit incomplete coverage. This diagnostic changes no model rows,
matching decisions, Event rules, or filters. Earlier mention-based ratios do
not test this measure. Population S2T sections 4/5 remain unchanged.
Synthetic IDs are excluded: this scope-concentration measure uses QIDs only.
Purpose: identify broad/unrelated MISC entities before Event retrieval.
Language clarification: a missing page in one wiki never blocks measurement
in the other; unavailable counts remain null, not a zero score. No combined
cross-language decision is inferred. The original 19-QID diagnostic is kept.
The separate scope_concentration_filter.py applies the provisional 5% cutoff;
this acquisition diagnostic does not perform the top-20 relation ranking.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
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


def saved_table(cache: Path, date: str, table: str, wiki: str) -> Path:
    paths = list(cache.glob(f"{wiki}-{date}-{table}.sql.gz.*.parquet"))
    if len(paths) != 1:
        raise ValueError(f"Expected one saved {wiki} {table} table")
    path = paths[0]
    if digest(path) != read_json(path.with_suffix(".json"))["sha256"]:
        raise ValueError(f"Changed saved {wiki} {table} table")
    return path


def measurement_pages(
    cache: Path, date: str, qids: set[str], wiki: str
) -> dict[str, dict]:
    """S2T 6.1: count one final page; never change the assigned entity QID.

    Follow the saved resolver's namespace-0 paths, cycle guard and 20-hop
    limit. A redirect's destination may carry a different QID. That QID is
    measurement metadata only; counts are keyed by the final page ID.
    """
    props, pages, redirects = (
        saved_table(cache, date, t, wiki) for t in ("page_props", "page", "redirect")
    )
    identities = pq.read_table(props, filters=[("qid", "in", sorted(qids))]).to_pylist()
    by_id = {
        r["pageid"]: r
        for r in pq.read_table(
            pages, filters=[("pageid", "in", [r["pageid"] for r in identities])]
        ).to_pylist()
    }
    result = {}
    for identity in identities:
        if identity["pageid"] not in by_id:  # Non-article page properties.
            continue
        qid = identity["qid"]
        if qid in result:
            raise ValueError(f"Multiple snapshot articles for {qid}")
        result[qid] = {**by_id[identity["pageid"]], "redirect_depth": 0}
    seen = {qid: {row["pageid"]} for qid, row in result.items()}
    for depth in range(21):
        pending = {qid: r for qid, r in result.items() if r["is_redirect"]}
        if not pending:
            break
        if depth == 20:
            raise ValueError("Redirect path reaches the saved resolver's depth limit")
        destinations = {
            r["pageid"]: r["title"]
            for r in pq.read_table(
                redirects,
                filters=[("pageid", "in", [r["pageid"] for r in pending.values()])],
            ).to_pylist()
        }
        by_title = {
            r["title"]: r
            for r in pq.read_table(
                pages, filters=[("title", "in", list(destinations.values()))]
            ).to_pylist()
        }
        for qid, row in pending.items():
            target = by_title.get(destinations.get(row["pageid"]))
            if target is None or target["pageid"] in seen[qid]:
                raise ValueError(f"Missing or cyclic redirect destination: {qid}")
            seen[qid].add(target["pageid"])
            result[qid] = {**target, "redirect_depth": depth + 1}
    final_qids = {
        r["pageid"]: r["qid"]
        for r in pq.read_table(
            props, filters=[("pageid", "in", [r["pageid"] for r in result.values()])]
        ).to_pylist()
    }
    for row in result.values():
        row["qid"] = final_qids.get(row["pageid"])
    return result


def aliases(
    cache: Path, date: str, canonical: dict[str, str], wiki: str = "enwiki"
) -> dict[str, str]:
    """Follow the saved resolver's namespace-0 redirect paths, in reverse.

    Include every alias, not only aliases seen in Daniel's scoped links. This
    prevents undercounting the global denominator. No name similarity is used.
    """

    pages, redirects = (saved_table(cache, date, t, wiki) for t in ("page", "redirect"))
    result = dict(canonical)
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
    # The installed native search tool applies the identical regex much faster
    # than Python over 1.67 billion rows. Python still verifies the entire dump
    # and owns QID/source-page deduplication. Only selected rows go to temp disk.
    rg = shutil.which("rg")
    if rg is None:
        raise ValueError("The installed rg file-search tool is required")
    pages = defaultdict(set)
    with (
        tempfile.TemporaryDirectory() as pattern_dir,
        tempfile.TemporaryFile() as selected,
        tempfile.TemporaryFile() as errors,
    ):
        # Pass the identical expression by file: the English population exceeds
        # Windows' command-line limit. Counts and S2T 6.1 rules stay unchanged.
        pattern_path = Path(pattern_dir) / "targets.regex"
        pattern_path.write_bytes(pattern.pattern + b"\n")
        with subprocess.Popen(
            [
                rg,
                "--no-config",
                "--text",
                "--no-unicode",
                "--no-line-number",
                "--no-heading",
                "--no-filename",
                "--color",
                "never",
                "--file",
                str(pattern_path),
                "--",
                "-",
            ],
            stdin=subprocess.PIPE,
            stdout=selected,
            stderr=errors,
        ) as process:
            try:
                for block in blocks:
                    process.stdin.write(block)
                process.stdin.close()
                if process.wait() not in (0, 1):
                    errors.seek(0)
                    raise ValueError(
                        f"Native file filter failed: {errors.read(4096)!r}"
                    )
            except BaseException:
                process.kill()
                raise
        selected.seek(0)
        for line in selected:
            match = pattern.fullmatch(line.rstrip(b"\n"))
            if match is None:
                raise ValueError("Native file filter returned an unexpected row")
            pages[targets[int(match[2])]].add(int(match[1]))
    return pages


def run(
    wiki: str = "enwiki", population: bool = False, output: Path | None = None
) -> dict:
    if wiki not in ("enwiki", "jawiki") or (wiki != "enwiki" and not population):
        raise ValueError("Use --population for separate EN/JA population scores")
    lang = wiki[:2]
    output = output or BASE / (
        f"poc_10k_misc_snapshot_link_relevance_{wiki}_20261020"
        if population
        else "poc_10k_misc_snapshot_link_relevance_20261020"
    )
    if output.exists():
        raise ValueError("Keep existing diagnostic outputs unchanged")
    manifest_path = SNAPSHOT / "page_snapshot_manifest.json"
    manifest = read_json(manifest_path)
    date = manifest["dump_date"]  # Version lineage, not a new hardcoded source date.
    source_path = CACHE / f"{'english' if lang == 'en' else 'japanese'}_sources.json.gz"
    links_path = CACHE / f"{lang}_link_resolution.json.gz"
    selection_path = (
        BASE / "poc_10k_entities_snapshot_first_20261020/entities.json.gz"
        if population
        else BASE / "poc_10k_misc_incoming_links_probe_20261020/partial_analysis.json"
    )
    # The original manifest pins article files and inventory counts, rather
    # than checksums of these two intermediate caches. Verify its coverage;
    # this diagnostic records the exact intermediate-file hashes below.
    if (
        dict(Counter(r["status"] for r in read_json(links_path)))
        != manifest["link_inventory"][lang]["resolution_counts"]
    ):
        raise ValueError("Saved source-page link coverage changed")
    selection_manifest = selection_path.parent / (
        "manifest.json" if population else "report.json"
    )
    if (
        digest(selection_path)
        != read_json(selection_manifest)["outputs"][selection_path.name]
    ):
        raise ValueError("Saved diagnostic QID selection changed")
    if population:
        # S2T 6.1: existing resolved MISC identities only; synthetic IDs never
        # acquire a QID, denominator or score through this measurement.
        selection = [
            {"qid": r["entity_id"], "title": r["name"]}
            for r in read_json(selection_path)
            if r["type"] == "MISC" and re.fullmatch(r"Q\d+", r["entity_id"])
        ]
    else:
        selection = read_json(selection_path)["counts"]  # Discard old counts.
    if len({r["qid"] for r in selection}) != len(selection):
        raise ValueError("Duplicate MISC QID in selected population")
    sources = read_json(source_path)
    # The JA inventory contains only retrieved counterpart pages; EN includes
    # unresolved source titles. Never mix numeric page IDs between languages.
    missing = [
        r["source"] for r in sources if r.get("status", "RESOLVED") != "RESOLVED"
    ]
    scope = {
        int(r["pageid"]) for r in sources if r.get("status", "RESOLVED") == "RESOLVED"
    }
    expected = manifest["source_pages"] if lang == "en" else manifest["japanese_pages"]
    if (
        len(sources) != expected
        or len(scope) != manifest["link_inventory"][lang]["source_pages"]
    ):
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
        selected_qids = {r["qid"] for r in selection}
        props = saved_table(CACHE, date, "page_props", wiki)
        page_table = saved_table(CACHE, date, "page", wiki)
        basis = measurement_pages(CACHE, date, selected_qids, wiki)
        canonical = {r["title"]: str(r["pageid"]) for r in basis.values()}
        names = aliases(CACHE, date, canonical, wiki)
        (output / "measurement_pages.json").write_text(
            json.dumps(basis, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (output / "aliases.json").write_text(
            json.dumps(names, indent=2), encoding="utf-8"
        )
        update("SCANNING_LINKTARGET", alias_titles=len(names))
        targets = link_targets(
            dump_blocks(
                CACHE / f"{wiki}-{date}-linktarget.sql.gz",
                "linktarget",
                lambda **v: update("SCANNING_LINKTARGET", **v),
            ),
            names,
        )
        if not set(targets.values()) <= set(canonical.values()):
            raise ValueError("Unexpected measurement page in dumped link targets")
        (output / "targets.json").write_text(
            json.dumps(targets, indent=2), encoding="utf-8"
        )
        update("SCANNING_GLOBAL_PAGELINKS", selected_target_ids=len(targets))
        pages = linked_pages(
            dump_blocks(
                CACHE / f"{wiki}-{date}-pagelinks.sql.gz",
                "pagelinks",
                lambda **v: update("SCANNING_GLOBAL_PAGELINKS", **v),
            ),
            targets,
        )
        # Independent agreement with the saved scoped resolver is mandatory.
        reference = defaultdict(set)
        target_pages = set(targets.values())
        for row in read_json(links_path):
            page_id = str(row.get("pageid"))
            if row["status"] in ("RESOLVED", "NO_PAGE_QID") and page_id in target_pages:
                reference[page_id].add(int(row["source"]))
        rows = []
        for row in selection:
            qid = row["qid"]
            measured = basis.get(qid, {})
            page_id = str(measured.get("pageid"))
            linking_pages = pages.get(page_id, set())
            numerator_pages = linking_pages & scope
            if numerator_pages != reference[page_id]:
                raise ValueError(
                    f"Actual scoped links disagree with saved resolution: {qid}"
                )
            numerator, denominator = len(numerator_pages), len(linking_pages)
            if numerator > denominator:
                raise ValueError(f"Invalid subset count: {qid}")
            rows.append(
                {
                    "qid": qid,
                    "wiki": wiki,
                    "name": row["title"],
                    "measurement_page_id": measured.get("pageid"),
                    "measurement_page_title": measured.get("title"),
                    "measurement_page_qid": measured.get("qid"),
                    "redirect_depth": measured.get("redirect_depth"),
                    "score_status": (
                        "SCORED"
                        if denominator
                        else (
                            "UNAVAILABLE_SNAPSHOT_PAGE"
                            if qid not in basis
                            else "UNAVAILABLE_NO_INCOMING_LINKS"
                        )
                    ),
                    "scope_linking_pages": numerator if denominator else None,
                    "all_linking_pages": denominator or None,
                    "relevance": numerator / denominator if denominator else None,
                    "scope_page_ids": sorted(numerator_pages),
                }
            )
        rows.sort(
            key=lambda r: (r["relevance"] is None, -(r["relevance"] or 0), r["qid"])
        )
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
            "wiki": wiki,
            "population": (
                "RESOLVED_MISC_QIDS_IN_FROZEN_10K"
                if population
                else "ORIGINAL_19_QID_DIAGNOSTIC"
            ),
            "scored_qids": sum(r["score_status"] == "SCORED" for r in rows),
            "unavailable_qids": sum(r["score_status"] != "SCORED" for r in rows),
            "scope_policy": "full Daniel source-page inventory in this language, including saved counterparts; no cross-language pooling",
            "formula": "distinct actual linking pages within Daniel full source-page scope / all distinct actual linking pages",
            "link_rules": "namespace-0 source and target pages, including template/navigation links; redirect and destination count as one final page; source page IDs counted once across its aliases",
            "measurement_policy": "original entity QID unchanged; final destination page supplies both counts, even if its QID differs; linking_page_ids is keyed by final page ID",
            "redirected_qids": sum(r["redirect_depth"] > 0 for r in basis.values()),
            "distinct_measurement_pages": len(canonical),
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
                table: read_json(CACHE / f"{wiki}-{date}-{table}.sql.gz.verified.json")
                for table in ("linktarget", "pagelinks")
            },
            "limits": [
                "Separate per-language measure; no combined QID-level decision is inferred.",
                "Only resolved source pages/counterparts contribute; unavailable page counts remain unknown.",
                "Page-link concentration is not identity-match confidence; this acquisition diagnostic does not apply the separate 5% filter.",
            ],
            "inputs": {
                str(p): digest(p)
                for p in (
                    manifest_path,
                    source_path,
                    links_path,
                    selection_path,
                    selection_manifest,
                    props,
                    page_table,
                    saved_table(CACHE, date, "redirect", wiki),
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
        update(
            "COMPLETE",
            scored_qids=report["scored_qids"],
            unavailable_qids=report["unavailable_qids"],
            report=str(output / "report.json"),
        )
        return report
    except Exception as exc:
        update("STOPPED_FOR_CONSULTATION", error=f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki", choices=("enwiki", "jawiki"), default="enwiki")
    parser.add_argument("--population", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run(args.wiki, args.population, args.output)
