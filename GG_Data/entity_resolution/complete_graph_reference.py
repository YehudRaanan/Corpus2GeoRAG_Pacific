"""Fetch a resumable, compact Wikidata name/type supplement for graph IDs.

Preserves the frozen reference and graph. Each saved batch records API response
hashes, request IDs, retrieval times, and projected fields with entity revisions.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from generate_candidates import write_json, write_line
from prepare_examples import ROOT, sha256

sys.path.insert(0, str(ROOT / "scripts"))
import requests  # noqa: E402
from fetch_wwii_task_force import USER_AGENT, WIKIDATA_API  # noqa: E402

LOG = logging.getLogger(__name__)
PREVIOUS = ROOT / "GG_Data/entity_resolution/runs/all_types_wide_search_v0.2.0_20261018"
API_PARAMETERS = {
    "action": "wbgetentities",
    "props": "info|labels|aliases|claims",
    "languages": "en",
    "redirects": "yes",
}


def read_lines(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def ids_hash(ids: set[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def project_entity(qid: str, entity: dict) -> dict:
    if "missing" in entity:
        return {"entity_id": qid, "metadata_status": "MISSING"}
    if not entity.get("id") or not isinstance(entity.get("lastrevid"), int):
        raise ValueError(f"Invalid API entity: {qid}")
    label = entity.get("labels", {}).get("en", {}).get("value", "")
    aliases = sorted({a["value"] for a in entity.get("aliases", {}).get("en", [])})
    types = []
    for claim in entity.get("claims", {}).get("P31", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict) and value.get("id"):
            types.append(value["id"])
    return dict(
        entity_id=qid,
        canonical_wikidata_id=entity["id"],
        metadata_status="AVAILABLE" if label or aliases else "NO_ENGLISH_NAME",
        label=label,
        aliases=aliases,
        direct_types=sorted(set(types)),
        wikidata_revision=entity["lastrevid"],
        name_source="Wikidata",
        name_language="en",
    )


def fetch_batch(qids: list[str]) -> dict:
    records, evidence = {}, []
    pending = list(qids)
    with requests.Session() as client:
        client.headers.update({"User-Agent": USER_AGENT})
        while pending:
            for attempt in range(6):
                try:
                    response = client.get(
                        WIKIDATA_API,
                        params={
                            "format": "json",
                            "formatversion": 2,
                            "maxlag": 15,
                            **API_PARAMETERS,
                            "ids": "|".join(pending),
                        },
                        timeout=90,
                    )
                    response.raise_for_status()
                    data = response.json()
                    error = data.get("error", {})
                    if error and error.get("code") != "no-such-entity":
                        raise RuntimeError(str(error))
                    break
                except (requests.RequestException, RuntimeError) as exc:
                    if attempt == 5:
                        raise
                    delay = 2**attempt
                    retry_after = getattr(exc, "response", None)
                    if retry_after is not None:
                        retry_after = retry_after.headers.get("Retry-After", "")
                        if retry_after.isdecimal():
                            delay = max(delay, int(retry_after))
                    LOG.warning("API retry in %ds: %s", delay, exc)
                    time.sleep(delay)
            evidence.append(
                dict(
                    requested_ids=list(pending),
                    retrieved_utc=datetime.now(timezone.utc).isoformat(),
                    response_sha256=hashlib.sha256(response.content).hexdigest(),
                    response_bytes=len(response.content),
                    error=data.get("error"),
                )
            )
            # A missing ID can reject the whole API request. Record that ID,
            # then request the remaining IDs without hiding the missing record.
            if error.get("code") == "no-such-entity":
                missing = error.get("id")
                if missing not in pending:
                    raise ValueError(f"Unexpected missing entity error: {data}")
                records[missing] = project_entity(missing, {"missing": True})
                pending.remove(missing)
                continue
            entities = data.get("entities", {})
            redirects = {r["from"]: r["to"] for r in data.get("redirects", [])}
            for qid in pending:
                canonical = qid
                visited = set()
                while canonical in redirects:
                    if canonical in visited:
                        raise ValueError("Cyclic API redirect")
                    visited.add(canonical)
                    canonical = redirects[canonical]
                entity = entities.get(qid, entities.get(canonical))
                if entity is None:
                    raise ValueError(f"API omitted requested ID: {qid}")
                records[qid] = project_entity(qid, entity)
            pending = []
    return dict(requested_ids=qids, requests=evidence, records=list(records.values()))


def run(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    if (output / "run_manifest.json").exists():
        raise ValueError("Completed supplement already exists; use a new directory")
    inputs = {
        p.relative_to(ROOT).as_posix(): sha256(p)
        for p in [
            PREVIOUS / "run_manifest.json",
            PREVIOUS / "mapped_graph.jsonl.gz",
            PREVIOUS / "entity_metadata.jsonl.gz",
            Path(__file__).resolve(),
        ]
    }
    previous = json.loads((PREVIOUS / "run_manifest.json").read_text())
    for name in ("mapped_graph.jsonl.gz", "entity_metadata.jsonl.gz"):
        if sha256(PREVIOUS / name) != previous["outputs"][name]["sha256"]:
            raise ValueError(f"Changed previous output: {name}")
    graph_ids = set()
    for row in read_lines(PREVIOUS / "mapped_graph.jsonl.gz"):
        graph_ids.update((row["subject"], row["object"]))
    if not all(re.fullmatch(r"Q[1-9][0-9]*", q) for q in graph_ids):
        raise ValueError("Unexpected non-Wikidata graph ID")
    old = {r["entity_id"]: r for r in read_lines(PREVIOUS / "entity_metadata.jsonl.gz")}
    targets = sorted(q for q in graph_ids if not old.get(q, {}).get("label"))
    state = dict(
        inputs_sha256=inputs, target_ids=targets, api_parameters=API_PARAMETERS
    )
    state_path = output / "request_plan.json"
    if state_path.exists() and json.loads(state_path.read_text()) != state:
        raise ValueError("Resume plan changed")
    write_json(state_path, state)
    batch_dir = output / "batches"
    batch_dir.mkdir(exist_ok=True)
    batches = [targets[i : i + 50] for i in range(0, len(targets), 50)]

    def save_batch(number: int, batch: list[str]) -> None:
        path = batch_dir / f"batch_{number:05d}.json.gz"
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                saved = json.load(stream)
            if saved["requested_ids"] != batch:
                raise ValueError("Saved batch IDs changed")
            return
        result = fetch_batch(batch)
        if {r["entity_id"] for r in result["records"]} != set(batch):
            raise ValueError("Batch coverage mismatch")
        temp = path.with_suffix(".tmp")
        with gzip.open(temp, "wt", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False)
        temp.replace(path)

    LOG.info(
        "Graph %d IDs; %d targets; %d batches",
        len(graph_ids),
        len(targets),
        len(batches),
    )
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(save_batch, i, batch) for i, batch in enumerate(batches)
        ]
        for n, future in enumerate(as_completed(futures), 1):
            future.result()
            if n % 20 == 0 or n == len(batches):
                LOG.info("Batches %d/%d", n, len(batches))
    records = {}
    for path in sorted(batch_dir.glob("*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for row in json.load(stream)["records"]:
                qid = row["entity_id"]
                if qid in records:
                    raise ValueError("Duplicate supplement ID")
                records[qid] = row
    if set(records) != set(targets) or not graph_ids <= old.keys() | records.keys():
        raise ValueError("Incomplete graph reference coverage")
    with gzip.open(
        output / "entity_metadata.jsonl.gz", "wt", encoding="utf-8"
    ) as stream:
        for qid in sorted(records):
            write_line(stream, records[qid])
    merged = {**old, **records}
    summary = dict(
        graph_ids=len(graph_ids),
        graph_entity_ids_sha256=ids_hash(graph_ids),
        targets=len(targets),
        graph_ids_without_metadata_before=sum(
            old.get(q, {}).get("metadata_status") == "MISSING" or q not in old
            for q in graph_ids
        ),
        graph_ids_without_english_names_before=sum(
            not (old.get(q, {}).get("label") or old.get(q, {}).get("aliases"))
            for q in graph_ids
        ),
        graph_ids_without_english_names_after=sum(
            not (merged[q].get("label") or merged[q].get("aliases")) for q in graph_ids
        ),
        statuses=dict(Counter(r["metadata_status"] for r in records.values())),
        missing_ids=sorted(
            q for q, r in records.items() if r["metadata_status"] == "MISSING"
        ),
        no_english_name_ids=sorted(
            q for q, r in records.items() if r["metadata_status"] == "NO_ENGLISH_NAME"
        ),
    )
    write_json(output / "summary.json", summary)
    for name, expected in inputs.items():
        if sha256(ROOT / name) != expected:
            raise ValueError(f"Input changed: {name}")
    write_json(
        output / "run_manifest.json",
        dict(
            status="COMPLETED",
            completed_utc=datetime.now(timezone.utc).isoformat(),
            inputs_sha256=inputs,
            api_url=WIKIDATA_API,
            api_parameters=API_PARAMETERS,
            graph_entity_ids_sha256=ids_hash(graph_ids),
            coverage_verified=True,
            response_storage="projected fields, revision IDs and original response hashes",
            outputs={
                p.relative_to(output).as_posix(): dict(
                    sha256=sha256(p), bytes=p.stat().st_size
                )
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
        ),
    )
    LOG.info("COMPLETED: %s", json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    run(args.output.resolve())
