"""Import a pinned Wikimedia link snapshot, then run the accepted matcher.

No article phrase extraction. Large downloads, Parquet and results stay on C:.
The deliberately narrow SQL reader accepts the verified 20261001 dump format
(one tuple per line) and rejects a different format rather than dropping rows.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import requests

from bigquery_direct_wikidata import BigQueryData, STORE, execute
from bilingual_page_pilot import digest, read
from full_direct_wikidata import INPUT_SHA256, input_rows, save

DATE = "20261001"
CACHE = Path.home() / ".cache/geoai_wikipedia_dump_20261018"
OUTPUT = Path.home() / ".cache/geoai_full_daniel_dump_bigquery_20261018"
DATASET = "geoai_wikipedia_dump_20261018"
UA = "Corpus2GeoRAG/0.1 (https://github.com/EtzionR/Corpus2GeoRAG_Pacific; research page-link import)"
TABLES = {
    "page": "pagetable",
    "redirect": "redirecttable",
    "page_props": "pagepropstable",
    "pagelinks": "pagelinkstable",
    "linktarget": "linktargettable",
}
LOG = logging.getLogger(__name__)
LOCK = threading.Lock()
TOKEN = re.compile(r"'(?:[^'\\]|\\.|'')*'|NULL|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?")
ESCAPES = {"0": "\0", "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a"}
SCHEMAS = {
    "page": pa.schema(
        [
            ("pageid", pa.int64()),
            ("title", pa.string()),
            ("revision", pa.int64()),
            ("is_redirect", pa.bool_()),
            ("links_updated", pa.string()),
        ]
    ),
    "redirect": pa.schema([("pageid", pa.int64()), ("title", pa.string())]),
    "page_props": pa.schema([("pageid", pa.int64()), ("qid", pa.string())]),
    "pagelinks": pa.schema([("pageid", pa.int64()), ("target_id", pa.int64())]),
    "linktarget": pa.schema(
        [
            ("target_id", pa.int64()),
            ("target_namespace", pa.int64()),
            ("title", pa.string()),
        ]
    ),
}


def progress(
    cache: Path, stage: str, *, worker: str | None = None, **values: object
) -> None:
    with LOCK:
        save(
            cache / (f"progress_{worker}.json" if worker else "progress.json"),
            {
                "stage": stage,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(),
                **values,
            },
        )
    LOG.info("%s %s", stage, values)


def download_plan(cache: Path) -> dict:
    path = cache / "downloads.json"
    if path.exists():
        return read(path)
    files = {}
    for lang in ("en", "ja"):
        url = f"https://dumps.wikimedia.org/{lang}wiki/{DATE}/dumpstatus.json"
        response = requests.get(url, headers={"User-Agent": UA}, timeout=90)
        response.raise_for_status()
        status = response.json()
        save(cache / f"{lang}_dumpstatus.json", status)
        for table, job in TABLES.items():
            entry = status["jobs"][job]
            if entry["status"] != "done" or len(entry["files"]) != 1:
                raise ValueError(f"Incomplete dump: {lang} {table}")
            name, info = next(iter(entry["files"].items()))
            expected = f"{lang}wiki-{DATE}-{table}.sql.gz"
            if name != expected or info["url"] != f"/{lang}wiki/{DATE}/{name}":
                raise ValueError("Unexpected dump path")
            files[name] = {
                **info,
                "language": lang,
                "table": table,
                "url": "https://dumps.wikimedia.org" + info["url"],
            }
    save(path, files)
    return files


def download(cache: Path, name: str, info: dict) -> None:
    path = cache / name
    receipt = cache / (name + ".verified.json")
    partial = path.with_name(name + ".part")
    if not path.exists():
        progress(cache, "DOWNLOAD", file=name, expected_bytes=info["size"])
        subprocess.run(
            [
                "curl.exe",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "--retry",
                "5",
                "--retry-delay",
                "10",
                "--connect-timeout",
                "60",
                "--speed-limit",
                "1024",
                "--speed-time",
                "120",
                "--continue-at",
                "-",
                "--user-agent",
                UA,
                "--output",
                str(partial),
                info["url"],
            ],
            check=True,
        )
        if partial.stat().st_size != info["size"]:
            raise ValueError(f"Wrong download length: {name}")
        partial.replace(path)
    sha1 = hashlib.sha1()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            sha1.update(block)
    if path.stat().st_size != info["size"] or sha1.hexdigest() != info["sha1"]:
        raise ValueError(f"Dump checksum failed: {name}; file retained for inspection")
    save(receipt, {"sha1": sha1.hexdigest(), "size": info["size"], "url": info["url"]})
    LOG.info("Verified %s", name)


def parse_tuple(line: str) -> list[str | None]:
    """Read scalar dump values without executing SQL or Python from the dump."""
    text = line.rstrip("\r\n")
    if not text.startswith("(") or text[-2:] not in ("),", ");"):
        raise ValueError("Expected one complete SQL tuple per line")
    text = text[1:-2]
    values = []
    position = 0
    while position < len(text):
        match = TOKEN.match(text, position)
        if not match:
            raise ValueError(f"Unsupported SQL value at offset {position}")
        token = match.group()
        value = None if token == "NULL" else token
        if token.startswith("'"):
            value = re.sub(
                r"\\(.)|''",
                lambda m: ESCAPES.get(m[1], m[1]) if m[1] else "'",
                token[1:-1],
            )
        values.append(value)
        position = match.end()
        if position < len(text):
            if text[position] != ",":
                raise ValueError("Expected SQL field separator")
            position += 1
            if position == len(text):
                raise ValueError("Missing SQL field")
    return values


def convert(
    path: Path, table: str, selected: set[int] | None = None
) -> tuple[Path, int]:
    """Read every input byte; retain only the reference scope needed for matching."""
    signature = hashlib.sha256(
        json.dumps(sorted(selected) if selected is not None else None).encode()
    ).hexdigest()[:16]
    output = path.with_name(path.name + "." + signature + ".parquet")
    receipt = output.with_suffix(".json")
    if receipt.exists() and output.exists():
        saved = read(receipt)
        if saved["sha256"] != digest(output):
            raise ValueError("Changed cached Parquet")
        return output, saved["rows"]
    partial = output.with_suffix(".partial.parquet")
    fields, batch, count, scanned = [], [], 0, 0
    in_create = in_insert = completed = False
    with pq.ParquetWriter(partial, SCHEMAS[table], compression="zstd") as writer:
        with gzip.open(path, "rb") as stream:
            for raw_line in stream:
                # Unused page properties can contain compressed binary blobs.
                # Filter them before decoding; retained QID rows remain strict UTF-8.
                if (
                    table == "page_props"
                    and in_insert
                    and raw_line.startswith(b"(")
                    and not re.match(rb"^\(\d+,'wikibase_item',", raw_line)
                ):
                    scanned += 1
                    if raw_line.rstrip().endswith(b");"):
                        in_insert = False
                    continue
                line = raw_line.decode("utf-8", errors="strict")
                if line.startswith(f"CREATE TABLE `{table}` ("):
                    in_create = True
                elif in_create and line.startswith("  `"):
                    fields.append(line.split("`", 2)[1])
                elif in_create and line.startswith(")"):
                    in_create = False
                elif line.startswith("INSERT INTO "):
                    if line.strip() != f"INSERT INTO `{table}` VALUES":
                        raise ValueError(
                            "Unsupported INSERT format; no partial import accepted"
                        )
                    in_insert = True
                elif in_insert:
                    if not line.startswith("("):
                        raise ValueError("Unexpected line inside SQL values")
                    scanned += 1
                    if line.rstrip().endswith(");"):
                        in_insert = False
                    # The huge integer-only link table is filtered before tokenization.
                    if table in {"pagelinks", "linktarget"} and selected is not None:
                        if int(line[1 : line.index(",")]) not in selected:
                            continue
                    if table in {"page", "redirect"} and line.split(",", 2)[1] != "0":
                        continue
                    values = parse_tuple(line)
                    if len(values) != len(fields):
                        raise ValueError(f"SQL field count differs: {table}")
                    row = dict(zip(fields, values))
                    record = project_row(table, row)
                    if record is not None:
                        batch.append(record)
                    if len(batch) >= 50000:
                        writer.write_table(
                            pa.Table.from_pylist(batch, schema=SCHEMAS[table])
                        )
                        count += len(batch)
                        batch.clear()
                elif line.startswith("-- Dump completed on "):
                    completed = True
            if in_insert or not completed or not fields or scanned == 0:
                raise ValueError(f"Incomplete SQL dump: {path}")
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMAS[table]))
            count += len(batch)
    partial.replace(output)
    save(
        receipt,
        {
            "rows": count,
            "scanned_rows": scanned,
            "sha256": digest(output),
            "columns": fields,
            "scope_signature": signature,
        },
    )
    LOG.info("Converted %s: %d retained / %d scanned", path.name, count, scanned)
    return output, count


def project_row(table: str, r: dict) -> dict | None:
    if table == "page" and r["page_namespace"] == "0":
        return {
            "pageid": int(r["page_id"]),
            "title": r["page_title"],
            "revision": int(r["page_latest"]),
            "is_redirect": r["page_is_redirect"] == "1",
            "links_updated": r["page_links_updated"],
        }
    if table == "redirect" and r["rd_namespace"] == "0" and not r["rd_interwiki"]:
        return {"pageid": int(r["rd_from"]), "title": r["rd_title"]}
    if table == "page_props" and r["pp_propname"] == "wikibase_item":
        if not re.fullmatch(r"Q[1-9]\d*", r["pp_value"]):
            raise ValueError("Invalid dumped Wikidata ID")
        return {"pageid": int(r["pp_page"]), "qid": r["pp_value"]}
    if table == "pagelinks" and r["pl_from_namespace"] == "0":
        return {"pageid": int(r["pl_from"]), "target_id": int(r["pl_target_id"])}
    if table == "linktarget":
        return {
            "target_id": int(r["lt_id"]),
            "target_namespace": int(r["lt_namespace"]),
            "title": r["lt_title"],
        }
    return None


def prepare_metadata(cache: Path, lang: str) -> str:
    """One process owns all conversion files for this language."""
    for table in ("page", "redirect", "page_props"):
        progress(cache, "CONVERT", worker=lang, language=lang, table=table)
        convert(cache / f"{lang}wiki-{DATE}-{table}.sql.gz", table)
    progress(cache, "METADATA_FILES_READY", worker=lang, language=lang)
    return lang


def prepare_links(cache: Path, lang: str, selected: set[int]) -> tuple:
    progress(cache, "CONVERT_LINKS", worker=lang, language=lang, table="pagelinks")
    parquet, _ = convert(
        cache / f"{lang}wiki-{DATE}-pagelinks.sql.gz", "pagelinks", selected
    )
    target_ids = set(
        pq.read_table(parquet, columns=["target_id"])["target_id"].to_pylist()
    )
    progress(cache, "CONVERT_LINKS", worker=lang, language=lang, table="linktarget")
    target_parquet, _ = convert(
        cache / f"{lang}wiki-{DATE}-linktarget.sql.gz", "linktarget", target_ids
    )
    target_rows = pq.read_table(target_parquet).to_pylist()
    inventory = {
        "source_pages": len(selected),
        "distinct_link_targets": len(target_ids),
        "target_namespace_counts": dict(
            Counter(r["target_namespace"] for r in target_rows)
        ),
        "missing_target_ids": sorted(
            target_ids - {r["target_id"] for r in target_rows}
        ),
    }
    progress(cache, "LINK_FILES_READY", worker=lang, language=lang)
    return lang, target_ids, inventory


def table_id(api: BigQueryData, lang: str, table: str) -> str:
    return f"{api.project}.{DATASET}.{lang}_{table}_{DATE}"


def load_table(
    api: BigQueryData,
    cache: Path,
    lang: str,
    table: str,
    selected: set[int] | None = None,
) -> dict:
    source = cache / f"{lang}wiki-{DATE}-{table}.sql.gz"
    progress(cache, "CONVERT", language=lang, table=table)
    parquet, count = convert(source, table, selected)
    destination = table_id(api, lang, table)
    receipt = cache / f"{lang}_{table}.load.json"
    sha = digest(parquet)
    if receipt.exists():
        saved = read(receipt)
        if saved["sha256"] != sha or saved["table"] != destination:
            raise ValueError("Existing import receipt has a different source or scope")
        metadata = json.loads(api.cli(["show", destination.replace(".", ":", 1)]))
        if int(metadata["numRows"]) != count:
            raise ValueError("Saved BigQuery import row count changed")
        return saved
    progress(cache, "BIGQUERY_LOAD", language=lang, table=table, rows=count)
    args = ["load", "--source_format=PARQUET", "--replace"]
    if table in {"page", "redirect", "linktarget"}:
        args.append("--clustering_fields=title")
    else:
        args.append("--clustering_fields=pageid")
    api.cli([*args, destination.replace(".", ":", 1), str(parquet)])
    metadata = json.loads(api.cli(["show", destination.replace(".", ":", 1)]))
    if int(metadata["numRows"]) != count:
        raise ValueError("BigQuery load row count differs")
    saved = {
        "table": destination,
        "rows": count,
        "sha256": sha,
        "source": str(source),
        "parquet": str(parquet),
        "metadata": metadata,
    }
    save(receipt, saved)
    return saved


def resolve_sql(api: BigQueryData, lang: str, seed: str) -> str:
    page = table_id(api, lang, "page")
    props = table_id(api, lang, "page_props")
    redirect = table_id(api, lang, "redirect")
    return f"""WITH RECURSIVE seeds AS ({seed}),
 walk AS (
 SELECT s.*,0 AS depth,IF(p.pageid IS NULL,ARRAY<INT64>[],[p.pageid]) AS path,
 p.pageid,p.title,p.revision,p.is_redirect,p.links_updated,q.qid,r.title AS redirect_title
 FROM seeds s LEFT JOIN `{page}` p ON p.title=s.requested_title
 LEFT JOIN `{props}` q USING(pageid) LEFT JOIN `{redirect}` r USING(pageid)
 UNION ALL
 SELECT w.seed_id,w.source,w.requested_title,w.depth+1,ARRAY_CONCAT(w.path,[p.pageid]),
 p.pageid,p.title,p.revision,p.is_redirect,p.links_updated,q.qid,r.title
 FROM walk w JOIN `{page}` p ON p.title=w.redirect_title
 LEFT JOIN `{props}` q ON q.pageid=p.pageid LEFT JOIN `{redirect}` r ON r.pageid=p.pageid
 WHERE w.is_redirect AND w.depth<20 AND p.pageid NOT IN UNNEST(w.path)
 ) SELECT *, CASE WHEN requested_title IS NULL THEN 'MISSING_LINK_TARGET'
 WHEN pageid IS NULL THEN 'MISSING_PAGE'
 WHEN is_redirect THEN 'REDIRECT_UNRESOLVED' WHEN qid IS NULL THEN 'NO_PAGE_QID'
 ELSE 'RESOLVED' END AS status FROM walk
 QUALIFY ROW_NUMBER() OVER(PARTITION BY seed_id ORDER BY depth DESC)=1"""


def build_pages(
    api: BigQueryData, cache: Path, output: Path, workers: ProcessPoolExecutor
) -> dict:
    rows = input_rows()
    sources = sorted({r["raw"]["Source"] for r in rows})
    inputs = api.upload_values(sources, "source")
    receipts = []
    try:
        api.cli(["show", f"{api.project}:{DATASET}"])
    except RuntimeError:
        api.cli(["mk", "--dataset", f"{api.project}:{DATASET}"])
    progress(cache, "PREPARE_METADATA", workers=2)
    prepared = [workers.submit(prepare_metadata, cache, lang) for lang in ("en", "ja")]
    for future in as_completed(prepared):
        lang = future.result()
        for table in ("page", "redirect", "page_props"):
            receipts.append(load_table(api, cache, lang, table))
    progress(cache, "RESOLVE_SOURCE_PAGES", sources=len(sources))
    english = api.query(
        resolve_sql(
            api,
            "en",
            f"""SELECT source AS seed_id,source,
 REPLACE(CONCAT(UPPER(SUBSTR(source,1,1)),SUBSTR(source,2)),' ','_') AS requested_title
 FROM `{inputs}`""",
        )
    )
    if {r["source"] for r in english} != set(sources) or len(english) != len(sources):
        raise ValueError("Source page query did not preserve all source titles")
    save(cache / "english_sources.json.gz", english)
    qids = sorted({r["qid"] for r in english if r.get("qid") and not r["is_redirect"]})
    if not qids:
        raise ValueError("No source-page identities found")
    ids = api.upload_values(qids, "id")
    japanese = api.query(f"""SELECT p.*,q.qid FROM `{table_id(api, "ja", "page")}` p
 JOIN `{table_id(api, "ja", "page_props")}` q USING(pageid) JOIN `{ids}` i ON i.id=q.qid
 WHERE NOT p.is_redirect""")
    if len({r["qid"] for r in japanese}) != len(japanese):
        raise ValueError("Multiple Japanese canonical pages for a source QID")
    save(cache / "japanese_sources.json.gz", japanese)
    language_rows = {
        "en": [r for r in english if r["pageid"] is not None and not r["is_redirect"]],
        "ja": japanese,
    }
    link_rows = {}
    link_inventory = {}
    progress(cache, "PREPARE_LINKS", workers=2)
    prepared = [
        workers.submit(
            prepare_links, cache, lang, {int(r["pageid"]) for r in language_rows[lang]}
        )
        for lang in ("en", "ja")
    ]
    for future in as_completed(prepared):
        lang, target_ids, inventory = future.result()
        link_inventory[lang] = inventory
        selected = {int(r["pageid"]) for r in language_rows[lang]}
        receipts.append(load_table(api, cache, lang, "pagelinks", selected))
        receipts.append(load_table(api, cache, lang, "linktarget", target_ids))
        progress(cache, "RESOLVE_LINKS", language=lang, source_pages=len(selected))
        seed = f"""SELECT FORMAT('%d:%d',l.pageid,l.target_id) AS seed_id,
 CAST(l.pageid AS STRING) AS source,t.title AS requested_title
 FROM `{table_id(api, lang, "pagelinks")}` l LEFT JOIN `{table_id(api, lang, "linktarget")}` t USING(target_id)
 WHERE t.target_namespace=0 OR t.target_id IS NULL"""
        link_rows[lang] = api.query(resolve_sql(api, lang, seed))
        link_inventory[lang]["resolution_counts"] = dict(
            Counter(r["status"] for r in link_rows[lang])
        )
        save(cache / f"{lang}_link_resolution.json.gz", link_rows[lang])
    links = {lang: defaultdict(list) for lang in ("en", "ja")}
    for lang, records in link_rows.items():
        for r in records:
            if r["status"] == "RESOLVED":
                links[lang][int(r["source"])].append(
                    {
                        "qid": r["qid"],
                        "title": r["title"].replace("_", " "),
                        "pageid": int(r["pageid"]),
                        "requested_title": r["requested_title"],
                    }
                )

    def article(lang: str, r: dict) -> dict:
        return {
            "language": lang,
            "title": r["title"].replace("_", " "),
            "pageid": int(r["pageid"]),
            "qid": r.get("qid"),
            "revision": {"revid": int(r["revision"]), "timestamp": None},
            "url": f"https://{lang}.wikipedia.org/w/index.php?oldid={r['revision']}",
            "links": links[lang][int(r["pageid"])],
            "html": "",
            "text": "",
            "anchor_names": [],
            "redirects": {},
            "evidence_source": "WIKIMEDIA_SQL_DUMP_BIGQUERY",
            "dump_date": DATE,
            "links_updated": r.get("links_updated"),
            "link_scope": "database internal links, including transcluded navigation; not revision-pinned HTML",
        }

    japanese_by_qid = {r["qid"]: r for r in japanese}
    directory = output / "pages"
    directory.mkdir(parents=True, exist_ok=True)
    files = {}
    statuses = defaultdict(int)
    for r in english:
        articles = []
        if r["pageid"] is not None and not r["is_redirect"]:
            a = article("en", r)
            ja = japanese_by_qid.get(r.get("qid"))
            a["japanese_counterpart"] = ja["title"].replace("_", " ") if ja else None
            articles.append(a)
            if ja:
                articles.append(article("ja", ja))
        status = r["status"]
        statuses[status] += 1
        filename = hashlib.sha256(r["source"].encode()).hexdigest() + ".json.gz"
        save(
            directory / filename,
            {
                "source": r["source"],
                "status": status,
                "articles": articles,
                "evidence_source": "WIKIMEDIA_SQL_DUMP_BIGQUERY",
                "source_resolution": r,
            },
        )
        files[filename] = digest(directory / filename)
    manifest = {
        "input_sha256": INPUT_SHA256,
        "source_pages": len(sources),
        "dump_date": DATE,
        "page_status_counts": dict(statuses),
        "japanese_pages": len(japanese),
        "files": files,
        "imports": receipts,
        "link_inventory": link_inventory,
        "downloads": read(cache / "downloads.json"),
        "link_scope": "database internal pagelinks includes templates/navigation; no anchor aliases or phrase extraction",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save(output / "page_snapshot_manifest.json", manifest)
    progress(
        cache,
        "PAGE_SNAPSHOT_READY",
        **{
            k: manifest[k]
            for k in ("source_pages", "japanese_pages", "page_status_counts")
        },
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--cache", type=Path, default=CACHE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        plan = download_plan(args.cache)
        remaining = sum(
            r["size"] for name, r in plan.items() if not (args.cache / name).exists()
        )
        if shutil.disk_usage(args.cache).free < remaining + 15 * 1024**3:
            raise OSError("Insufficient cache space for downloads and conversion")
        # Two bulk connections, not one request per article or entity.
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda pair: download(args.cache, *pair), plan.items()))
        progress(args.cache, "DOWNLOADS_VERIFIED", files=len(plan))
        if args.download_only:
            return
        api = BigQueryData(args.project, STORE)
        # Separate processes allow both CPU-bound languages to make progress.
        # Only the parent submits BigQuery jobs or writes the shared manifest.
        with ProcessPoolExecutor(max_workers=2) as workers:
            build_pages(api, args.cache, args.output, workers)
        execute(args.project, STORE, args.output, page_snapshot=args.output, api=api)
        progress(args.cache, "COMPLETE", output=str(args.output))
    except Exception as exc:
        save(
            args.cache / "failure.json",
            {"error": str(exc), "at": datetime.now(timezone.utc).isoformat()},
        )
        LOG.exception(
            "Snapshot run stopped; completed downloads and imports are retained"
        )
        raise


if __name__ == "__main__":
    main()
