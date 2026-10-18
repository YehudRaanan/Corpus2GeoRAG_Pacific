"""Use the GCP BigQuery CLI for Wikidata; retain the accepted matching rules.

Wikipedia supplies page revisions and direct links only. No article name
extraction. Query results, SQL, job statistics and metadata persist on C:.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from bilingual_page_pilot import LiveData, article, digest, read
from direct_wikidata_pilot import BASE, clean_name
from full_direct_wikidata import DEFAULT_OUTPUT, input_rows, run, save

LOG = logging.getLogger(__name__)
STORE = Path.home() / ".cache/geoai_bigquery_20261018"
OUTPUT = Path.home() / ".cache/geoai_full_daniel_bigquery_20261018"
TABLE = "bigquery-public-data.wikipedia.wikidata"
MAX_BYTES = 2 * 1024**4


def project_entity(row: dict) -> dict:
    """Same en/ja name and nondeprecated P31/P279 projection as the API path."""
    labels = {n["language"]: n["value"] for n in row.get("labels", [])}
    sitelinks = {s["site"]: {"title": s["title"]} for s in row.get("sitelinks", [])}
    properties = {}
    for name in ("p31", "p279"):
        values = []
        for raw in row.get(name) or []:
            claim = json.loads(raw) if isinstance(raw, str) else raw
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if claim.get("rank") != "deprecated" and isinstance(value, dict):
                if qid := value.get("id"):
                    values.append(qid)
        properties[name] = sorted(set(values))
    return {
        "id": row["id"],
        "label": labels.get("en", ""),
        "labels": labels,
        "aliases": sorted(
            set(labels.values())
            | {n["value"] for n in row.get("aliases", [])}
            | {s["title"] for s in sitelinks.values()}
        ),
        "sitelinks": sitelinks,
        "direct_types": properties["p31"],
        "parents": properties["p279"],
        "revision": int(row["revision"]) if row.get("revision") else None,
        "modified": row.get("modified"),
        "missing": False,
        "reference_source": "BIGQUERY",
    }


class BigQueryData(LiveData):
    def __init__(self, project: str, store: Path) -> None:
        super().__init__(Path.home() / ".cache/geoai_bilingual_pilot_20261018")
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
            raise ValueError("Invalid GCP project ID")
        self.project, self.store = project, store
        store.mkdir(parents=True, exist_ok=True)
        self.bq = shutil.which("bq.cmd")
        if not self.bq:
            raise RuntimeError("Install the GCP CLI bq component first")
        snapshot = store / "table_snapshot.json"
        if not snapshot.exists():
            metadata = json.loads(self.cli(["show", TABLE.replace(".", ":", 1)]))
            save(
                snapshot,
                {
                    "snapshot_at": datetime.now(timezone.utc).isoformat(),
                    "table": metadata,
                },
            )
        self.snapshot = read(snapshot)
        self.source = f"`{TABLE}` AS w FOR SYSTEM_TIME AS OF TIMESTAMP '{self.snapshot['snapshot_at']}'"
        self.metadata_path = store / "entity_metadata.json.gz"
        self.entities = read(self.metadata_path) if self.metadata_path.exists() else {}

    def cli(self, args: list[str], sql: str | None = None) -> str:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["CLOUDSDK_ENCODING"] = "utf-8"
        bundled = Path(self.bq).parent.parent / "platform/bundledpython/python.exe"
        env["CLOUDSDK_PYTHON"] = str(bundled)
        result = subprocess.run(
            [
                self.bq,
                f"--project_id={self.project}",
                "--location=US",
                "--format=json",
                *args,
            ],
            input=sql,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        if result.returncode:
            raise RuntimeError(
                f"bq failed ({result.returncode}): {result.stderr}\n{result.stdout}"
            )
        return result.stdout

    def query(self, sql: str) -> list[dict]:
        key = hashlib.sha256(sql.encode()).hexdigest()
        path = self.store / (key + ".json.gz")
        if path.exists():
            saved = read(path)
            self.requests.append({k: v for k, v in saved.items() if k != "rows"})
            return saved["rows"]
        (self.store / (key + ".sql")).write_text(sql, encoding="utf-8")
        dry = self.cli(["query", "--use_legacy_sql=false", "--dry_run"], sql)
        (self.store / (key + ".dry_run.txt")).write_text(dry, encoding="utf-8")
        LOG.info("BigQuery dry run: %s", dry.strip())
        job = "geoai_" + key[:32]
        rows = json.loads(
            self.cli(
                [
                    "query",
                    "--use_legacy_sql=false",
                    f"--maximum_bytes_billed={MAX_BYTES}",
                    "--max_rows=3000000",
                    f"--job_id={job}",
                ],
                sql,
            )
        )
        stats = json.loads(self.cli(["show", "--job=true", job]))
        destination = stats["configuration"]["query"]["destinationTable"]
        result_table = f"{destination['projectId']}:{destination['datasetId']}.{destination['tableId']}"
        result_info = json.loads(self.cli(["show", result_table]))
        if int(result_info["numRows"]) != len(rows):
            raise ValueError("BigQuery result was truncated")
        saved = {
            "job_id": job,
            "billing_project": self.project,
            "job_reference": stats.get("jobReference"),
            "sql_sha256": key,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "statistics": stats.get("statistics", {}),
            "rows": rows,
        }
        save(path, saved)
        self.requests.append({k: v for k, v in saved.items() if k != "rows"})
        LOG.info("BigQuery job %s saved %d rows", job, len(rows))
        return rows

    def entities_for(self, qids: set[str]) -> None:
        todo = sorted(q for q in qids if q not in self.entities)
        if not todo:
            return
        if any(not re.fullmatch(r"Q[1-9]\d*", q) for q in todo):
            raise ValueError("Invalid Wikidata entity ID")
        numbers = ",".join(q[1:] for q in todo)
        selected = numbers
        if len(numbers) > 700000:
            table = self.upload_values(todo, "id")
            selected = f"SELECT CAST(SUBSTR(id,2) AS INT64) FROM `{table}`"
        # Numeric-ID clustering restricts the blocks read for selected records.
        sql = f"""SELECT id,
 ARRAY(SELECT AS STRUCT language,value FROM UNNEST(labels) WHERE language IN ('en','ja')) labels,
 ARRAY(SELECT AS STRUCT language,value FROM UNNEST(aliases) WHERE language IN ('en','ja')) aliases,
 ARRAY(SELECT AS STRUCT site,title FROM UNNEST(sitelinks) WHERE site IN ('enwiki','jawiki')) sitelinks,
 JSON_QUERY_ARRAY(RTRIM(item, ',\\n\\r '), '$.claims.P31') p31,
 JSON_QUERY_ARRAY(RTRIM(item, ',\\n\\r '), '$.claims.P279') p279,
 JSON_VALUE(item, '$.lastrevid') revision, JSON_VALUE(item, '$.modified') modified
 FROM {self.source} WHERE numeric_id IN ({selected}) AND STARTS_WITH(id,'Q')"""
        for row in self.query(sql):
            self.entities[row["id"]] = project_entity(row)
        for qid in todo:
            self.entities.setdefault(
                qid,
                {
                    "id": qid,
                    "label": "",
                    "labels": {},
                    "aliases": [],
                    "sitelinks": {},
                    "direct_types": [],
                    "parents": [],
                    "missing": True,
                    "reference_source": "BIGQUERY",
                },
            )
        save(self.metadata_path, self.entities)

    def hierarchy(self, ids: set[str]) -> None:
        self.entities_for(ids)
        frontier = {t for q in ids for t in self.entities[q]["direct_types"]}
        seen = set()
        while frontier:
            self.entities_for(frontier)
            seen.update(frontier)
            frontier = {p for q in frontier for p in self.entities[q]["parents"]} - seen

    def upload_values(self, values: list[str], field: str) -> str:
        signature = hashlib.sha256(
            json.dumps([field, values], ensure_ascii=False).encode()
        ).hexdigest()[:16]
        dataset = "geoai_resolution_20261018"
        table = f"{self.project}.{dataset}.terms_{signature}"
        terms = self.store / (signature + ".ndjson")
        receipt = self.store / (signature + ".load.json")
        if receipt.exists():
            return read(receipt)["table"]
        if not receipt.exists():
            with terms.open("w", encoding="utf-8") as stream:
                for value in values:
                    stream.write(json.dumps({field: value}, ensure_ascii=False) + "\n")
            try:
                self.cli(["show", f"{self.project}:{dataset}"])
            except RuntimeError:
                self.cli(
                    [
                        "mk",
                        "--dataset",
                        "--default_table_expiration=604800",
                        f"{self.project}:{dataset}",
                    ]
                )
            self.cli(
                [
                    "load",
                    "--source_format=NEWLINE_DELIMITED_JSON",
                    "--replace",
                    table.replace(".", ":", 1),
                    str(terms),
                    f"{field}:STRING",
                ]
            )
            save(
                receipt, {"table": table, "rows": len(values), "sha256": digest(terms)}
            )
        return table

    def name_lookups(self, names: list[str]) -> list[dict]:
        table = self.upload_values(names, "name")
        return self.query(f"""SELECT DISTINCT w.id AS qid,n.value AS daniel_name_variant
 FROM {self.source},
 UNNEST(ARRAY_CONCAT(w.labels,w.aliases)) AS n
 JOIN `{table}` AS t ON n.value=t.name
 WHERE n.language IN ('en','ja') AND STARTS_WITH(w.id,'Q')""")


def collect_page(source: str, output: Path) -> dict:
    path = output / "pages" / (hashlib.sha256(source.encode()).hexdigest() + ".json.gz")
    if path.exists():
        return read(path)
    old = DEFAULT_OUTPUT / "pages" / path.name
    if old.exists():
        saved = read(old)
        save(path, saved)
        return saved
    api = LiveData(Path.home() / ".cache/geoai_bilingual_pilot_20261018")
    try:
        english = article(api, "en", source)
    except ValueError as exc:
        if not str(exc).startswith("Missing article:"):
            raise
        saved = {
            "source": source,
            "status": "MISSING_ENGLISH_PAGE",
            "articles": [],
            "error": str(exc),
        }
    else:
        language = api.wiki(
            "en",
            action="query",
            pageids=str(english["pageid"]),
            prop="langlinks",
            lllang="ja",
            lllimit=500,
        )
        links = language["query"]["pages"][0].get("langlinks", [])
        title = next((x["title"] for x in links if x["lang"] == "ja"), None)
        english["japanese_counterpart"] = title
        articles = [english]
        if title:
            japanese = article(api, "ja", title)
            if english["qid"] and japanese["qid"] != english["qid"]:
                raise ValueError(f"Language counterpart QIDs differ: {source}")
            articles.append(japanese)
        saved = {
            "source": source,
            "status": "RESOLVED" if english["qid"] else "NO_PAGE_QID",
            "articles": articles,
        }
    save(path, saved)
    return saved


def execute(project: str, store: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    (output / "pages").mkdir(exist_ok=True)
    rows = input_rows()
    names = defaultdict(set)
    sources = sorted({r["raw"]["Source"] for r in rows})

    def progress(stage: str, **counts: object) -> None:
        save(
            output / "progress.json",
            {
                "stage": stage,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                **counts,
            },
        )
        LOG.info("%s %s", stage, counts)

    for row in rows:
        raw = row["raw"]
        if raw["entity_group"] != "DATE":
            for name in {raw["word"].strip(), clean_name(raw["word"])}:
                for variant in {name, name.casefold(), name.title()} - {""}:
                    names[variant].add(raw["Source"])
    api = BigQueryData(project, store)
    progress("BIGQUERY_DANIEL_NAME_LOOKUPS", distinct_name_variants=len(names))
    lookup = api.name_lookups(sorted(names))
    save(output / "daniel_name_lookups.json.gz", lookup)
    old_world = BASE / "fresh_wwii_names.json.gz"
    assert (
        digest(old_world) == read(BASE / "run_manifest.json")["outputs"][old_world.name]
    )
    world_ids = set(read(old_world))
    progress(
        "COLLECT_WIKIPEDIA_PAGES",
        completed=0,
        total=len(sources),
        name_lookup_hits=len(lookup),
    )
    pages = {}
    # Three independent Wikipedia clients; Wikidata APIs are never called here.
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {
            pool.submit(collect_page, source, output): source for source in sources
        }
        known_ids = {hit["qid"] for hit in lookup} | world_ids
        progress("BIGQUERY_REFERENCE_EXPORT", candidate_qids=len(known_ids))
        api.entities_for(known_ids)
        for future in as_completed(pending):
            source = pending[future]
            pages[source] = future.result()
            progress(
                "COLLECT_WIKIPEDIA_PAGES", completed=len(pages), total=len(sources)
            )
    pools = {
        s: {a["qid"] for a in pages[s]["articles"] if a["qid"]}
        | {link["qid"] for a in pages[s]["articles"] for link in a["links"]}
        for s in sources
    }
    for hit in lookup:
        for source in names[hit["daniel_name_variant"]]:
            pools[source].add(hit["qid"])
    save(
        output / "candidate_evidence.json.gz",
        {
            "page_pools": {s: sorted(ids) for s, ids in pools.items()},
            "daniel_name_lookups": lookup,
        },
    )
    needed = set().union(*pools.values()) | world_ids
    progress("BIGQUERY_CANDIDATE_METADATA", candidate_qids=len(needed))
    api.entities_for(needed)
    progress("BIGQUERY_TYPE_HIERARCHY", candidate_qids=len(needed))
    api.hierarchy(needed)
    save(output / "entity_metadata.json.gz", api.entities)
    world = {
        q: api.entities[q]
        for q in sorted(world_ids)
        if not api.entities[q].get("missing")
    }
    save(output / "world.json.gz", world)
    save(
        output / "reference_manifest.json",
        {
            "provider": "BIGQUERY_GCP_CLI",
            "store": str(store),
            "runner_sha256": digest(Path(__file__)),
            "project": project,
            "table": TABLE,
            "table_snapshot": api.snapshot,
            "scope_source": str(old_world),
            "scope_sha256": digest(old_world),
            "wwii_scope_ids": len(world_ids),
            "wwii_ids_available": len(world),
            "missing_qids": sorted(q for q in needed if api.entities[q].get("missing")),
            "world_sha256": digest(output / "world.json.gz"),
            "request_evidence": api.requests,
            "max_bytes_billed_per_query": MAX_BYTES,
        },
    )
    return run(output, api=api)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--store", type=Path, default=STORE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        summary = execute(args.project, args.store, args.output)
    except Exception as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        save(
            args.output / "failure.json",
            {"error": str(exc), "at": datetime.now(timezone.utc).isoformat()},
        )
        LOG.exception("BigQuery run stopped; completed data remains saved")
        raise
    print(json.dumps(summary, indent=2))
