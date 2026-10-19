"""Current Wikidata acquisition: population S2T sections 1 and 7.

This adapter only retrieves source evidence. It never extracts Daniel mentions,
changes matching, or declares candidate events included in the data model.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.relations import SourceException

EVENT_ROOT = "Q140451665"
QUERY_URL = "https://query.wikidata.org/sparql"
SCHOLARLY_QUERY_URL = "https://query-scholarly.wikidata.org/sparql"
USER_AGENT = "GeoAI-Daniel-POC/1.0 (https://github.com/EtzionR/Corpus2GeoRAG_Pacific)"


def cached_json(store: Path, url: str, params: dict) -> tuple[dict, dict]:
    """Cache untouched responses and request evidence before interpreting them.

    Current Wikidata was approved on 20 October 2026 for Events/direct links.
    Cache hits are checksum checked. A failed request stops; it is not retried,
    overwritten, or silently replaced by another endpoint/snapshot.
    """
    request = {"url": url, "params": params}
    key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    directory = store / key
    metadata = directory / "request.json"
    body = directory / "response.json"
    if directory.exists():
        if not metadata.exists() or not body.exists():
            raise SourceException(
                "Incomplete current Wikidata cache", cache=str(directory)
            )
        evidence = read_json(metadata)
        if evidence["request"] != request or digest(body) != evidence["sha256"]:
            raise SourceException(
                "Current Wikidata cache mismatch", cache=str(directory)
            )
        if evidence["status"] != "OK":
            raise SourceException(
                "Cached request failed; no automatic retry", **evidence
            )
        return read_json(body), evidence

    directory.mkdir(parents=True)
    evidence = {
        "request": request,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAILED",
        "cache": str(directory),
    }
    try:
        # Single polite reader; no concurrency or automatic retry (S2T stop rule).
        time.sleep(1.1)
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=45,
            allow_redirects=False,
        )
        body.write_bytes(response.content)
        evidence.update(
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            http_status=response.status_code,
            response_headers=dict(response.headers),
            sha256=digest(body),
        )
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError("Unexpected source redirect")
        data = response.json()
        if not isinstance(data, dict) or "error" in data or "errors" in data:
            raise ValueError("Unexpected Wikidata JSON or API error")
        evidence["status"] = "OK"
    except (requests.RequestException, ValueError) as exc:
        evidence["error"] = str(exc)
        raise SourceException("Current Wikidata request failed", **evidence) from exc
    finally:
        metadata.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return data, evidence


def incoming_query(qid: str) -> str:
    """Approved smaller requests: retrieve incoming links for one Daniel QID.

    S2T 7 still requires both directions and all ranks. Outgoing links come from
    the complete native record; incoming links use full statements, without a
    hierarchy join or LIMIT. Neither step establishes Event membership.
    """
    if not re.fullmatch(r"Q[1-9]\d*", qid):
        raise ValueError("Expected a native Daniel QID")
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT DISTINCT ?subject ?statement ?property ?rank WHERE {{
  ?statement ?statementProperty wd:{qid} .
  ?property wikibase:claim ?claim ;
            wikibase:statementProperty ?statementProperty .
  ?subject ?claim ?statement .
  ?statement wikibase:rank ?rank .
  FILTER(STRSTARTS(STR(?subject), "http://www.wikidata.org/entity/Q"))
}}
"""


def current_record(store: Path, qid: str) -> tuple[dict, dict]:
    """Retrieve the complete native JSON; never redirect or project claims."""
    if not re.fullmatch(r"Q[1-9]\d*", qid):
        raise ValueError("Expected a native QID")
    data, evidence = cached_json(
        store, f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json", {}
    )
    record = data.get("entities", {}).get(qid, {})
    if (
        record.get("id") != qid
        or record.get("type") != "item"
        or "missing" in record
        or not isinstance(record.get("claims"), dict)
        or not isinstance(record.get("lastrevid"), int)
        or not record.get("modified")
    ):
        raise SourceException(
            "Unexpected current native record", qid=qid, source=evidence
        )
    return record, evidence


def item_links(record: dict) -> list[dict]:
    """S2T 7/8: native item-valued main statements only, preserving all ranks.

    Non-item, unknown-value and no-value claims remain in the full cached JSON.
    They do not generate a candidate identity or an Event participation link.
    """
    links = []
    for prop, statements in record["claims"].items():
        for statement in statements:
            snak = statement.get("mainsnak", {})
            value = snak.get("datavalue", {}).get("value")
            if not isinstance(value, dict) or value.get("entity-type") != "item":
                continue
            if (
                not re.fullmatch(r"Q[1-9]\d*", value.get("id", ""))
                or snak.get("property") != prop
                or snak.get("datatype") != "wikibase-item"
                or not statement.get("id")
                or statement.get("rank") not in {"normal", "preferred", "deprecated"}
            ):
                raise SourceException(
                    "Unexpected current item statement",
                    qid=record["id"],
                    statement=statement,
                )
            links.append(
                dict(
                    subject_qid=record["id"],
                    object_qid=value["id"],
                    source_predicate=f"wd:{prop}",
                    source_record_id=statement["id"],
                    raw_statement=statement,
                )
            )
    return links


def class_edges_query(qids: list[str], prop: str) -> str:
    """Retrieve one hierarchy hop for at most ten reference QIDs (S2T 7).

    The approved split avoids server-side recursive joins. Local traversal uses
    these direct P31/P279 statements, including deprecated rank, without a depth
    cutoff or added classification rule. Empty parent lists remain explicit.
    """
    if (
        not 1 <= len(qids) <= 10
        or len(qids) != len(set(qids))
        or any(not re.fullmatch(r"Q[1-9]\d*", qid) for qid in qids)
        or prop not in {"P31", "P279"}
    ):
        raise ValueError("Expected up to ten distinct hierarchy QIDs and P31/P279")
    values = " ".join(f"wd:{qid}" for qid in qids)
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?item ?present ?statement ?parent ?rank WHERE {{
  VALUES ?item {{ {values} }}
  BIND(EXISTS {{ ?item ?predicate ?value }} AS ?present)
  OPTIONAL {{
    ?item p:{prop} ?statement .
    ?statement ps:{prop} ?parent ; wikibase:rank ?rank .
    FILTER(STRSTARTS(STR(?parent), "http://www.wikidata.org/entity/Q"))
  }}
}}
"""


def hierarchy_path(qid: str, parents: dict[str, list[dict]]) -> list[dict] | None:
    """Cycle-safe native P279 traversal; no guessed class or depth limit.

    A missing fetched node is incomplete acquisition, not a negative result.
    A path is supporting evidence only; it does not add a business entity.
    """
    pending = [(qid, [])]
    visited = set()
    while pending:
        current, path = pending.pop()
        if current == EVENT_ROOT:
            return path
        if current in visited:
            continue
        visited.add(current)
        if current not in parents:
            raise SourceException("Incomplete Event hierarchy", qid=current)
        pending.extend((edge["parent"], path + [edge]) for edge in parents[current])
    return None
