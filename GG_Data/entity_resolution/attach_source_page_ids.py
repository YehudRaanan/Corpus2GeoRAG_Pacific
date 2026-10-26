"""Attach text-verified source Wikipedia page IDs without altering raw rows."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import logging
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from bs4 import BeautifulSoup

API = "https://en.wikipedia.org/w/api.php"
INPUT_SHA256 = "dcd51dfa237b63378279ced4f9739a45d8cf8ce3991579f20848295448f83f16"
USER_AGENT = "Corpus2GeoRAG-Pacific-source-verification/0.1 (https://github.com/EtzionR/Corpus2GeoRAG_Pacific)"
LOG = logging.getLogger(__name__)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def resolve_page(source: str, response: dict[str, Any]) -> dict[str, Any]:
    query = response.get("query", {})
    aliases = {
        item["from"]: item["to"]
        for group in ("normalized", "redirects")
        for item in query.get(group, [])
    }
    title, seen = source, set()
    while title in aliases:
        if title in seen:
            return {"status": "REDIRECT_CYCLE", "Source": source}
        seen.add(title)
        title = aliases[title]
    page = next((p for p in query.get("pages", []) if p.get("title") == title), {})
    if "missing" in page or "invalid" in page:
        status = "MISSING_PAGE"
    elif not page:
        status = "NO_PAGE_RETURNED"
    elif page.get("ns") != 0:
        status = "NON_ARTICLE"
    elif "disambiguation" in page.get("pageprops", {}):
        status = "DISAMBIGUATION"
    elif type(page.get("pageid")) is not int or page["pageid"] <= 0:
        status = "INVALID_PAGE_ID"
    else:
        status = "ARTICLE"
    return {**page, "Source": source, "status": status, "aliases": aliases}


def render_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select(
        "script, style, sup.reference, .mw-editsection, .mw-cite-backlink"
    ):
        tag.decompose()
    for tag in soup.find_all(
        ["p", "li", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6"]
    ):
        tag.append("\n")
    for tag in soup.find_all("br"):
        tag.replace_with("\n")
    return soup.get_text()


def match_text(text: str, page: dict[str, Any]) -> tuple[int | None, str]:
    if page.get("status") != "ARTICLE":
        return None, page.get("status", "NO_PAGE_EVIDENCE")
    needle = normalize(text)
    if not needle:
        return None, "EMPTY_TEXT"
    extract = page.get("extract", "")
    if text in extract:
        return page["pageid"], "VERIFIED_EXACT"
    normalized_extract = page.get("_normalized_extract") or normalize(extract)
    if needle in normalized_extract:
        return page["pageid"], "VERIFIED_NORMALIZED"
    rendered = page.get("_normalized_rendered") or normalize(page.get("rendered", ""))
    if needle in rendered:
        return page["pageid"], "VERIFIED_RENDERED"
    return None, "TEXT_NOT_FOUND"


def append_ids(table: pa.Table, decisions: dict[tuple[str, str], dict]) -> pa.Table:
    if "wiki_page_id" in table.column_names:
        raise ValueError("Input already contains wiki_page_id")
    ids = [
        decisions[(source, text)]["wiki_page_id"]
        for source, text in zip(table["Source"].to_pylist(), table["Text"].to_pylist())
    ]
    if any(
        value is not None and (type(value) is not int or value <= 0) for value in ids
    ):
        raise ValueError("Page IDs must be positive integers or null")
    return table.append_column("wiki_page_id", pa.array(ids, type=pa.int64()))


def search_decision(text: str, pages: list[dict]) -> tuple[int | None, str]:
    if len(normalize(text)) < 50 or len(text.split()) < 8:
        return None, "INSUFFICIENT_TEXT_FOR_SEARCH"
    matches = {}
    for page in pages:
        pageid, status = match_text(text, page)
        if pageid is not None:
            matches[pageid] = "VERIFIED_SEARCH_" + status.removeprefix("VERIFIED_")
    if len(matches) > 1:
        return None, "AMBIGUOUS_TEXT_MATCH"
    if matches:
        return next(iter(matches.items()))
    return None, "TEXT_NOT_FOUND"


def save_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    if path.suffix == ".gz":
        with gzip.open(temporary, "wt", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
    else:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), "utf-8")
    temporary.replace(path)


def read_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text("utf-8"))


class WikiClient:
    """One request owner, persistent evidence, and no automatic failed-call retries."""

    def __init__(self, output: Path):
        self.cache = output / "requests"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def query(self, params: dict[str, Any]) -> tuple[dict, str]:
        params = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
        key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
        path = self.cache / f"{key}.json.gz"
        if path.exists():
            record = read_json(path)
        else:
            start = time.monotonic()
            record = {
                "endpoint": API,
                "params": params,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            }
            try:
                response = self.session.get(API, params=params, timeout=30)
                record.update(
                    http_status=response.status_code, response_text=response.text
                )
                response.raise_for_status()
                data = response.json()
                if "error" in data:
                    raise RuntimeError(str(data["error"]))
                record["ok"] = True
            except (requests.RequestException, ValueError, RuntimeError) as error:
                record.update(ok=False, error=f"{type(error).__name__}: {error}")
            record["elapsed_seconds"] = round(time.monotonic() - start, 6)
            save_json(path, record)
            time.sleep(0.1)
        if not record["ok"]:
            raise RuntimeError(
                f"Saved request failed (no retry): {record['error']}; evidence={path.name}"
            )
        return json.loads(record["response_text"]), path.name


def fetch_page(client: WikiClient, source: str, texts: list[str], path: Path) -> dict:
    if path.exists():
        page = read_json(path)
    else:
        response, evidence = client.query(
            {
                "action": "query",
                "titles": source,
                "redirects": 1,
                "prop": "extracts|info|pageprops",
                "explaintext": 1,
                "inprop": "url",
            }
        )
        page = resolve_page(source, response)
        page["request_evidence"] = [evidence]
        page["_normalized_extract"] = normalize(page.get("extract", ""))
    if (
        page["status"] == "ARTICLE"
        and not page.get("rendered")
        and not page.get("render_error")
        and any(match_text(text, page)[0] is None for text in texts)
    ):
        try:
            rendered, evidence = client.query(
                {
                    "action": "parse",
                    "oldid": page["lastrevid"],
                    "prop": "text",
                    "disableeditsection": 1,
                }
            )
            if rendered.get("parse", {}).get("pageid") != page["pageid"]:
                raise ValueError("Rendered page ID disagrees with title lookup")
            page["rendered"] = render_text(rendered["parse"]["text"])
            page["_normalized_rendered"] = normalize(page["rendered"])
            page["request_evidence"].append(evidence)
        except (RuntimeError, ValueError) as error:
            page["render_error"] = str(error)
            LOG.warning("Render failed for %s: %s", source, error)
    save_json(path, page)
    return page


def collect(frame: pd.DataFrame, output: Path, limit: int | None) -> None:
    client = WikiClient(output)
    pages_dir = output / "pages"
    pages_dir.mkdir(exist_ok=True)
    sources = sorted(frame.Source.unique())
    selected = sources[:limit] if limit else sources
    failures = []
    for number, source in enumerate(selected, 1):
        path = pages_dir / (hashlib.sha256(source.encode()).hexdigest() + ".json.gz")
        texts = frame.loc[frame.Source.eq(source), "Text"].unique().tolist()
        try:
            page = fetch_page(client, source, texts, path)
            verified = sum(match_text(text, page)[0] is not None for text in texts)
            LOG.info(
                "%d/%d source=%s status=%s passages=%d/%d",
                number,
                len(selected),
                source,
                page["status"],
                verified,
                len(texts),
            )
        except RuntimeError as error:
            failures.append({"Source": source, "error": str(error)})
            LOG.error("%d/%d source=%s error=%s", number, len(selected), source, error)
        save_json(
            output / "progress.json",
            {
                "phase": "collect",
                "completed_sources": number,
                "total_sources": len(sources),
                "selected_sources": len(selected),
                "failures": failures,
                "updated_utc": datetime.now(timezone.utc).isoformat(),
            },
        )


def recover_missing(frame: pd.DataFrame, output: Path) -> None:
    """Discover candidates from copied text for missing source titles only."""
    client = WikiClient(output)
    candidate_dir = output / "candidate_pages"
    candidate_dir.mkdir(exist_ok=True)
    search_dir = output / "search_candidates"
    search_dir.mkdir(exist_ok=True)
    for source in sorted(frame.Source.unique()):
        key = hashlib.sha256(source.encode()).hexdigest()
        source_path = output / "pages" / f"{key}.json.gz"
        if not source_path.exists():
            continue
        original = read_json(source_path)
        if original["status"] not in {"MISSING_PAGE", "NO_PAGE_RETURNED"}:
            continue
        record_path = search_dir / f"{key}.json"
        if record_path.exists():
            continue
        texts = frame.loc[frame.Source.eq(source), "Text"].unique().tolist()
        anchors = sorted(
            (
                text
                for text in texts
                if len(normalize(text)) >= 50 and len(text.split()) >= 8
            ),
            key=lambda text: (-len(text), text),
        )[:2]
        record = {
            "Source": source,
            "anchors": anchors,
            "search_evidence": [],
            "candidate_pages": [],
            "errors": [],
        }
        titles = set()
        for text in anchors:
            phrase = " ".join(text.split()[:12]).replace('"', " ")
            try:
                response, evidence = client.query(
                    {
                        "action": "query",
                        "list": "search",
                        "srsearch": f'"{phrase}"',
                        "srnamespace": 0,
                        "srlimit": 5,
                    }
                )
                record["search_evidence"].append(evidence)
                titles.update(
                    item["title"]
                    for item in response.get("query", {}).get("search", [])
                )
            except RuntimeError as error:
                record["errors"].append(str(error))
        pages = []
        for title in sorted(titles):
            path = candidate_dir / (
                hashlib.sha256(title.encode()).hexdigest() + ".json.gz"
            )
            try:
                page = fetch_page(client, title, texts, path)
                pages.append(page)
                record["candidate_pages"].append(str(path.relative_to(output)))
            except RuntimeError as error:
                record["errors"].append(str(error))
        record["verified_passages"] = sum(
            search_decision(text, pages)[0] is not None for text in texts
        )
        save_json(record_path, record)
        LOG.info(
            "Text search source=%s candidates=%d verified_passages=%d/%d",
            source,
            len(pages),
            record["verified_passages"],
            len(texts),
        )


def make_decisions(
    frame: pd.DataFrame, output: Path, include_text_search: bool = True
) -> dict:
    decisions = {}
    for source in sorted(frame.Source.unique()):
        path = (
            output
            / "pages"
            / (hashlib.sha256(source.encode()).hexdigest() + ".json.gz")
        )
        page = read_json(path) if path.exists() else {"status": "REQUEST_FAILED"}
        search_path = (
            output
            / "search_candidates"
            / (hashlib.sha256(source.encode()).hexdigest() + ".json")
        )
        search_record = read_json(search_path) if search_path.exists() else {}
        candidates_by_path = {
            name: read_json(output / name)
            for name in search_record.get("candidate_pages", [])
        }
        for text in frame.loc[frame.Source.eq(source), "Text"].unique():
            pageid, status = match_text(text, page)
            evidence_page = page
            evidence_path = str(path.relative_to(output)) if path.exists() else None
            if pageid is None and search_record:
                pageid, status = search_decision(
                    text, list(candidates_by_path.values())
                )
                if pageid is not None:
                    evidence_path, evidence_page = next(
                        (name, candidate)
                        for name, candidate in candidates_by_path.items()
                        if candidate.get("pageid") == pageid
                        and match_text(text, candidate)[0] == pageid
                    )
            decisions[(source, text)] = {
                "wiki_page_id": pageid,
                "status": status,
                "candidate_page_id": evidence_page.get("pageid"),
                "canonical_title": evidence_page.get("title"),
                "revision_id": evidence_page.get("lastrevid"),
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "page_evidence": (evidence_path),
                "search_evidence": (
                    str(search_path.relative_to(output)) if search_record else None
                ),
            }
            text_search_path = (
                output
                / "text_search"
                / (hashlib.sha256(text.encode()).hexdigest() + ".json")
            )
            if include_text_search and pageid is None and text_search_path.exists():
                result = read_json(text_search_path)
                decisions[(source, text)].update(
                    {
                        k: result.get(k)
                        for k in [
                            "wiki_page_id",
                            "status",
                            "page_evidence",
                            "canonical_title",
                            "revision_id",
                        ]
                    }
                )
                decisions[(source, text)]["search_evidence"] = str(
                    text_search_path.relative_to(output)
                )
    if include_text_search:
        pages = {
            str(path.relative_to(output)): read_json(path)
            for base in ["pages", "candidate_pages"]
            for path in sorted((output / base).glob("*.json.gz"))
        }
        for (_, text), decision in decisions.items():
            if decision["status"].startswith("VERIFIED_SEARCH_"):
                decision.update(choose_evidence(text, pages))
                decision["candidate_page_id"] = decision["wiki_page_id"]
    return decisions


def choose_evidence(text: str, pages: dict[str, dict]) -> dict:
    pageid, status = search_decision(text, list(pages.values()))
    result = {
        "wiki_page_id": pageid,
        "status": status,
        "page_evidence": None,
        "canonical_title": None,
        "revision_id": None,
    }
    if pageid is not None:
        name, page = next(
            (name, p)
            for name, p in pages.items()
            if p.get("pageid") == pageid and match_text(text, p)[0] == pageid
        )
        result.update(
            page_evidence=name,
            canonical_title=page.get("title"),
            revision_id=page.get("lastrevid"),
        )
    return result


def search_remaining(frame: pd.DataFrame, output: Path) -> None:
    decisions = make_decisions(frame, output, include_text_search=False)
    pending = sorted(
        {
            text
            for (_, text), result in decisions.items()
            if result["wiki_page_id"] is None
        }
    )
    directory = output / "text_search"
    directory.mkdir(exist_ok=True)
    candidate_dir = output / "candidate_pages"
    candidate_dir.mkdir(exist_ok=True)
    pages = {
        str(path.relative_to(output)): read_json(path)
        for base in ["pages", "candidate_pages"]
        for path in sorted((output / base).glob("*.json.gz"))
    }
    client = WikiClient(output)
    for number, text in enumerate(pending, 1):
        key = hashlib.sha256(text.encode()).hexdigest()
        path = directory / f"{key}.json"
        if path.exists():
            continue
        record = {
            "text_sha256": key,
            "Text": text,
            "search_evidence": [],
            "candidate_pages": [],
            "errors": [],
        }
        result = choose_evidence(text, pages)
        if result["status"] == "TEXT_NOT_FOUND":
            phrase = " ".join(text.split()[:12]).replace('"', " ")
            try:
                response, evidence = client.query(
                    {
                        "action": "query",
                        "list": "search",
                        "srsearch": f'"{phrase}"',
                        "srnamespace": 0,
                        "srlimit": 5,
                    }
                )
                record["search_evidence"].append(evidence)
                for item in response.get("query", {}).get("search", []):
                    title = item["title"]
                    page_path = candidate_dir / (
                        hashlib.sha256(title.encode()).hexdigest() + ".json.gz"
                    )
                    try:
                        page = fetch_page(client, title, [text], page_path)
                        name = str(page_path.relative_to(output))
                        pages[name] = page
                        record["candidate_pages"].append(name)
                    except RuntimeError as error:
                        record["errors"].append(str(error))
            except RuntimeError as error:
                record["errors"].append(str(error))
            result = choose_evidence(text, pages)
        record.update(result)
        save_json(path, record)
        LOG.info(
            "Passage search %d/%d status=%s pageid=%s",
            number,
            len(pending),
            result["status"],
            result["wiki_page_id"],
        )
        save_json(
            output / "text_search_progress.json",
            {
                "completed_texts": number,
                "total_texts": len(pending),
                "updated_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
    # Recheck against the final pool so later candidates cannot conceal ambiguity.
    for text in pending:
        path = directory / (hashlib.sha256(text.encode()).hexdigest() + ".json")
        record = read_json(path)
        record.update(choose_evidence(text, pages))
        save_json(path, record)


def export(input_path: Path, output: Path) -> dict:
    target = output / (input_path.stem + "_with_wiki_page_id.parquet")
    if target.exists():
        raise FileExistsError(f"Preserve existing output: {target}")
    table = pq.read_table(input_path)
    frame = table.select(["Source", "Text"]).to_pandas()
    decisions = make_decisions(frame, output)
    enriched = append_ids(table, decisions)
    temporary = target.with_suffix(".parquet.tmp")
    pq.write_table(enriched, temporary, compression="zstd")
    restored = pq.read_table(temporary)
    assert restored.select(table.column_names).equals(
        table, check_metadata=True
    ), "Raw input changed"
    assert restored["wiki_page_id"].equals(enriched["wiki_page_id"])
    assert sha256(input_path) == INPUT_SHA256, "Input file changed"
    temporary.replace(target)
    statuses = Counter()
    source_counts = {}
    with (output / "unresolved_rows.csv").open(
        "x", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "row_index",
                "Source",
                "Index",
                "word",
                "entity_group",
                "status",
                "Text",
            ],
        )
        writer.writeheader()
        for row_index, row in enumerate(table.to_pylist()):
            decision = decisions[(row["Source"], row["Text"])]
            statuses[decision["status"]] += 1
            counts = source_counts.setdefault(row["Source"], {"rows": 0, "verified": 0})
            counts["rows"] += 1
            counts["verified"] += decision["wiki_page_id"] is not None
            if decision["wiki_page_id"] is None:
                writer.writerow(
                    {
                        "row_index": row_index,
                        **{
                            k: row[k]
                            for k in ["Source", "Index", "word", "entity_group", "Text"]
                        },
                        "status": decision["status"],
                    }
                )
    with gzip.open(
        output / "passage_decisions.jsonl.gz", "xt", encoding="utf-8"
    ) as stream:
        for (source, text), decision in decisions.items():
            stream.write(
                json.dumps(
                    {"Source": source, "Text": text, **decision}, ensure_ascii=False
                )
                + "\n"
            )
    save_json(output / "source_summary.json", source_counts)
    summary = {
        "status": "COMPLETED",
        "input_rows": table.num_rows,
        "output_rows": restored.num_rows,
        "source_titles": len(source_counts),
        "distinct_source_text_pairs": len(decisions),
        "verified_rows": table.num_rows - restored["wiki_page_id"].null_count,
        "unresolved_rows": restored["wiki_page_id"].null_count,
        "row_statuses": dict(statuses),
        "passage_statuses": dict(Counter(d["status"] for d in decisions.values())),
        "output_file": str(target),
        "original_columns_and_order_preserved": True,
        "original_schema_metadata_preserved": True,
        "input_sha256": INPUT_SHA256,
        "output_sha256": sha256(target),
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Current English Wikipedia pages; exact full passage or NFC/whitespace-normalized match; no historical revision search; no entity resolution.",
    }
    save_json(output / "summary.json", summary)
    manifest = {
        "input": str(input_path),
        "input_sha256": INPUT_SHA256,
        "script_sha256": sha256(Path(__file__)),
        "files_sha256": {
            str(p.relative_to(output)): sha256(p)
            for p in sorted(output.rglob("*"))
            if p.is_file() and p.name not in {"manifest.json", "run.log"}
        },
    }
    save_json(output / "manifest.json", manifest)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--phase", required=True, choices=["collect", "recover", "search", "export"]
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if sha256(args.input) != INPUT_SHA256:
        raise ValueError("Original input checksum does not match pinned source")
    args.output.mkdir(parents=True, exist_ok=True)
    logging.getLogger().addHandler(
        logging.FileHandler(args.output / "run.log", encoding="utf-8")
    )
    if args.phase in {"collect", "recover", "search"}:
        frame = pd.read_parquet(args.input, columns=["Source", "Text"])
        if args.phase == "collect":
            collect(frame, args.output, args.limit)
        elif args.phase == "recover":
            recover_missing(frame, args.output)
        else:
            search_remaining(frame, args.output)
    else:
        LOG.info("%s", json.dumps(export(args.input, args.output)))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    main()
