"""Save source-field evidence for the eight reviewed Wikidata succession self-links.

Uses pinned Russian Wikipedia revisions where the saved statement provides one.
The unpinned case and target page resolution are explicitly marked as current.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "self_link_review_2026-10-15"
API = "https://ru.wikipedia.org/w/api.php"
FIELD_PATTERN = re.compile(
    r"(?mi)^[ \t]*\|[ \t]*(предшественник|преемник)[ \t]*=[ \t]*(.*?)(?=\n[ \t]*\||\n\}\}|\Z)",
    flags=re.DOTALL,
)


def query(session: requests.Session, **params: str) -> dict:
    response = session.get(
        API, params={"action": "query", "format": "json", **params}, timeout=30
    )
    response.raise_for_status()
    result = response.json()
    if "error" in result:
        raise ValueError(result["error"])
    return {"request_url": response.url, "result": result}


def main() -> None:
    entities = {
        e["id"]: e
        for e in json.loads(
            (OUT / "succession_entities.json").read_text(encoding="utf-8")
        )
    }
    evidence = json.loads((OUT / "source_evidence.json").read_text(encoding="utf-8"))
    session = requests.Session()
    session.headers["User-Agent"] = "GeoAI-SourceAudit/1.0"
    pages: dict[str, dict] = {}
    links: set[str] = set()
    for row in evidence["wikidata"]:
        if row["property"] not in {"P1365", "P1366"}:
            continue
        qid = row["entity_id"]
        if qid in pages:
            continue
        references = row["statement"].get("references", [])
        urls = [
            s["datavalue"]["value"]
            for ref in references
            for p, snaks in ref.get("snaks", {}).items()
            if p in {"P854", "P4656"}
            for s in snaks
            if "datavalue" in s
        ]
        revision = next(
            (m.group(1) for u in urls if (m := re.search(r"oldid=(\d+)", u))), None
        )
        title = entities[qid]["sitelinks"]["ruwiki"]["title"]
        try:
            response = query(
                session,
                prop="revisions",
                rvprop="ids|timestamp|content",
                rvslots="main",
                **({"revids": revision} if revision else {"titles": title}),
            )
            if not response["result"].get("query", {}).get("pages"):
                raise ValueError(response)
        except (requests.RequestException, ValueError) as error:
            pages[qid] = {
                "label": row["label"],
                "reference_urls": urls,
                "error": str(error),
            }
            continue
        page = next(iter(response["result"]["query"]["pages"].values()))
        rev = page["revisions"][0]
        text = rev["slots"]["main"]["*"]
        fields = []
        for match in FIELD_PATTERN.finditer(text):
            value = match.group(2).strip()
            targets = [
                m.group(1).split("#", 1)[0].strip()
                for m in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", value)
            ]
            links.update(targets)
            fields.append(
                {
                    "field": match.group(1),
                    "value": value,
                    "line": text.count("\n", 0, match.start()) + 1,
                    "link_targets": targets,
                }
            )
        pages[qid] = {
            "label": row["label"],
            "evidence_scope": (
                "PINNED_REFERENCE_REVISION"
                if revision
                else "CURRENT_UNPINNED_CONTEXT_ONLY"
            ),
            "reference_urls": urls,
            "request_url": response["request_url"],
            "title": page["title"],
            "pageid": page["pageid"],
            "revid": rev["revid"],
            "timestamp": rev["timestamp"],
            "fields": fields,
            "source_url": f"https://ru.wikipedia.org/w/index.php?oldid={rev['revid']}",
        }
    resolution = query(
        session,
        titles="|".join(sorted(links)),
        redirects="1",
        prop="pageprops|info",
        ppprop="wikibase_item",
    )
    payload = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "pages": pages,
        "target_resolution_scope": "CURRENT_AT_RETRIEVAL_NOT_IMPORT_TIME",
        "target_resolution": resolution,
    }
    (OUT / "succession_source_trace.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for qid, page in pages.items():
        print(json.dumps({"qid": qid, **page}, ensure_ascii=False))
    print(json.dumps(resolution["result"], ensure_ascii=False))


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    main()
