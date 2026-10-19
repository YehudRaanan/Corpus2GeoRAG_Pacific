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


def discovery_query(qids: list[str]) -> str:
    """S2T 7: direct links in both directions, native P31/P279, all ranks.

    Full p:/ps: statements avoid the truthy wdt: projection, which can omit
    deprecated/normal-rank evidence. No LIMIT, local event class/date filter,
    inferred participation, or recursive population expansion is introduced.
    Returned candidates still require full records and the two-Daniel-QID gate.
    """
    if (
        not qids
        or len(qids) != len(set(qids))
        or any(not re.fullmatch(r"Q[1-9]\d*", qid) for qid in qids)
    ):
        raise ValueError("Expected distinct native Daniel QIDs")
    values = " ".join(f"wd:{qid}" for qid in qids)
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT DISTINCT ?event ?entity ?statement ?property ?direction WHERE {{
  VALUES ?entity {{ {values} }}
  {{
    ?entity ?claim ?statement .
    ?statement ?statementProperty ?event .
    BIND("D_TO_E" AS ?direction)
  }} UNION {{
    ?event ?claim ?statement .
    ?statement ?statementProperty ?entity .
    BIND("E_TO_D" AS ?direction)
  }}
  ?property wikibase:claim ?claim ;
            wikibase:statementProperty ?statementProperty .
  ?event p:P31/ps:P31/(p:P279/ps:P279)* wd:{EVENT_ROOT} .
}}
"""
