"""POC step 1: copy a reproducible 10K sample into Mentions and Wiki Pages.

Contract: docs/SOURCES_TO_ENTITY_DATA_MODEL_S2T.md sections 1-5, 10.
This module has no network client, extractor, matcher, or entity generator.
Later population stages must consume these preserved decisions.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import random
from collections import Counter
from pathlib import Path
from typing import Any

import ijson
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
# Shared manifest interface with the legacy script entry point; avoid importing
# its CLI-only sibling imports into the population package.
PAGE_CANDIDATE_SCOPE = "SOURCE_PAGE_EN_JA_LINKS_ONLY_V1"
INPUT_SHA256 = "dcd51dfa237b63378279ced4f9739a45d8cf8ce3991579f20848295448f83f16"
INPUT_COUNT = 309_864
SAMPLE_COUNT = 10_000
SEED = 20261018
RAW_COLUMNS = (
    "entity_group",
    "score",
    "word",
    "start",
    "end",
    "Source",
    "Index",
    "Text",
    "subtype",
)
STAGES = {
    "PAGE_DIRECT_WIKIDATA",
    "ALREADY_MATCHED",
    "FRESH_WWII",
    "DATE_NORMALIZED",
    "SYNTHETIC",
}
LOG = logging.getLogger(__name__)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def sample_indices(total: int, count: int = SAMPLE_COUNT) -> list[int]:
    """Sample original row positions without replacement, then keep source order."""
    return sorted(random.Random(SEED).sample(range(total), count))


def mention_from_match(row: dict, raw: dict, run_id: str) -> dict:
    """Copy saved decisions; fail on drift rather than repairing an input row."""
    number = row["input_row_number"]
    identity = [
        number,
        *[raw[k] for k in ("Source", "Index", "start", "end", "entity_group")],
    ]
    expected_id = (
        "mention-"
        + hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
    )
    if row["raw"] != raw or row["mention_id"] != expected_id:
        raise ValueError(f"Input/matching identity differs at original row {number}")
    if raw["Text"][raw["start"] : raw["end"]] != raw["word"]:
        raise ValueError(f"Extraction span differs at original row {number}")
    stage, assigned = row["matched_stage"], row["assigned_id"]
    if stage not in STAGES:
        raise ValueError(f"Unexpected matching stage at row {number}: {stage}")
    normalized_date = stage == "DATE_NORMALIZED"
    synthetic = stage == "SYNTHETIC"
    if synthetic and (
        not assigned.startswith("SYN_") or not row.get("unresolved_reason")
    ):
        raise ValueError(f"Synthetic identity/reason differs at row {number}")
    if normalized_date and (not assigned.startswith("DATE:") or not row.get("date")):
        raise ValueError(f"Normalized date differs at row {number}")
    if not normalized_date and not synthetic:
        if (
            not assigned.startswith("Q")
            or not assigned[1:].isdigit()
            or row["score"] < 0.8
        ):
            raise ValueError(f"Saved QID/threshold differs at row {number}")
    # Approved synthetic rule: retain Daniel's type if saved resolved_type is null.
    # This changes the model FK only; saved type_metadata remains untouched.
    saved_type = row["type_metadata"].get("resolved_type")
    entity_type = None if normalized_date else saved_type
    if synthetic and entity_type is None:
        entity_type = raw["entity_group"]
    if not normalized_date and not entity_type:
        raise ValueError(f"No entity type at original row {number}")
    # Preserve unknown/nested saved fields as well as the nine original columns.
    return {
        **row,
        **{k: v for k, v in raw.items() if k != "score"},
        "ner_score": raw["score"],
        "match_score": row.get("score"),
        "entity_id": None if normalized_date else assigned,
        "entity_type": entity_type,
        "resolution_run_id": run_id,
    }


def page_key(article: dict) -> tuple[str, int]:
    language, page_id = article["language"], article["pageid"]
    if language not in {"en", "ja"} or type(page_id) is not int or page_id <= 0:
        raise ValueError(f"Unexpected saved article key: {language}, {page_id}")
    return language + "wiki", page_id


def attach_pages(mentions: list[dict], payloads: dict[str, dict]) -> list[dict]:
    """S2T section 5: retain EN/JA pages, original requests and complete evidence."""
    pages: dict[tuple[str, int], dict] = {}
    for mention in mentions:
        source = mention["raw"]["Source"]
        payload = payloads[source]
        articles = payload.get("articles", [])
        if payload.get("source") != source:
            raise ValueError(f"Page cache source differs: {source}")
        if payload["status"] == "RESOLVED" and not articles:
            raise ValueError(f"Resolved request has no article: {source}")
        if payload["status"] != "RESOLVED" and articles:
            raise ValueError(f"Failed request contains articles: {source}")
        keys = [page_key(a) for a in articles]
        if len(articles) > 2 or len(set(keys)) != len(keys):
            raise ValueError(f"Duplicate article within saved request: {source}")
        # The saved producer places the resolved source article first, then JA.
        key = keys[0] if keys else (None, None)
        mention.update(
            wiki_site=key[0],
            wiki_page_id=key[1],
            page_id_source="LOOKUP",
            # Full payload is stored once per request, not once per mention.
            # The output manifest binds that evidence artifact by SHA-256.
            page_resolution={
                **{k: v for k, v in payload.items() if k != "articles"},
                "reference": {"file": "page_evidence.json.gz", "record": source},
            },
        )
        supplied = (mention["raw"].get("wiki_site"), mention["raw"].get("wiki_page_id"))
        if supplied != (None, None) and supplied != key:
            raise ValueError(
                f"Input/lookup page conflict: {source}: {supplied} != {key}"
            )
        for index, article in enumerate(articles):
            key = keys[index]
            counterpart = keys[1 - index] if len(keys) == 2 else (None, None)
            record = {
                "wiki_site": key[0],
                "wiki_page_id": key[1],
                "language": article["language"],
                "title": article["title"],
                "url": article.get("url"),
                "wikidata_qid": article.get("qid"),
                # Entity membership is checked in the later Entities stage.
                "about_entity_id": None,
                "revision_id": article.get("revision", {}).get("revid"),
                "revision_timestamp": article.get("revision", {}).get("timestamp"),
                "revision_url": article.get("url"),
                "counterpart_site": counterpart[0],
                "counterpart_page_id": counterpart[1],
                **{
                    k: article.get(k)
                    for k in (
                        "evidence_source",
                        "dump_date",
                        "links_updated",
                        "link_scope",
                    )
                },
                "reference_payload": article,
            }
            previous = pages.setdefault(
                key, {**record, "requested_titles": [], "lookup_evidence": []}
            )
            if any(previous[k] != v for k, v in record.items()):
                raise ValueError(
                    f"Conflicting cached page records: {key}; source={source}"
                )
            if source not in previous["requested_titles"]:
                previous["requested_titles"].append(source)
                previous["lookup_evidence"].append(mention["page_resolution"])
    return [pages[k] for k in sorted(pages)]


def prepare(input_path: Path, cache: Path) -> dict:
    """Read-only preparation. No result is written if any contract check fails."""
    if digest(input_path) != INPUT_SHA256:
        raise ValueError("Daniel input hash differs from the pinned S2T input")
    manifest_path = cache / "manifest.json"
    manifest = read_json(manifest_path)
    # Population S2T 3: old global-name page pools invalidate every later stage.
    if manifest.get("page_candidate_scope") != PAGE_CANDIDATE_SCOPE:
        raise ValueError("Matching run does not enforce source-page candidate scope")
    if (manifest["input_sha256"], manifest["threshold"], manifest["seed"]) != (
        INPUT_SHA256,
        0.8,
        SEED,
    ):
        raise ValueError("Saved matching manifest differs from the S2T")
    if "matches.json.gz" not in manifest["outputs"]:
        raise ValueError("Saved manifest does not bind the matching decisions")
    for name, expected in manifest["outputs"].items():
        path = (cache / name).resolve()
        if not path.is_relative_to(cache.resolve()) or digest(path) != expected:
            raise ValueError(f"Saved matching artifact/hash differs: {name}")
    frame = pd.read_parquet(input_path)
    if len(frame) != INPUT_COUNT or not set(RAW_COLUMNS) <= set(frame.columns):
        raise ValueError("Daniel row count/columns differ from the pinned contract")
    indices = sample_indices(len(frame))
    originals = dict(zip(indices, frame.iloc[indices].to_dict("records")))
    mentions = []
    total = 0
    run_id = digest(manifest_path)
    with gzip.open(cache / "matches.json.gz", "rb") as stream:
        for number, row in enumerate(ijson.items(stream, "item", use_float=True)):
            if row["input_row_number"] != number:
                raise ValueError(f"Matching row order differs at position {number}")
            if number in originals:
                mentions.append(mention_from_match(row, originals[number], run_id))
            total += 1
    if total != INPUT_COUNT or len(mentions) != SAMPLE_COUNT:
        raise ValueError(f"Matching/sample counts differ: {total}, {len(mentions)}")
    if len({m["mention_id"] for m in mentions}) != SAMPLE_COUNT:
        raise ValueError("Duplicate selected mention IDs")
    synthetic_ids = [
        m["assigned_id"] for m in mentions if m["matched_stage"] == "SYNTHETIC"
    ]
    if len(synthetic_ids) != len(set(synthetic_ids)):
        raise ValueError("Synthetic identity reused across original mentions")
    payloads = {}
    for source in sorted({m["raw"]["Source"] for m in mentions}):
        name = hashlib.sha256(source.encode()).hexdigest() + ".json.gz"
        path = cache / "pages" / name
        if digest(path) != manifest["page_evidence"][name]:
            raise ValueError(f"Saved page hash differs: {source}")
        payloads[source] = read_json(path)
    pages = attach_pages(mentions, payloads)
    return {
        "mentions": mentions,
        "wiki_pages": pages,
        "page_evidence": payloads,
        "manifest": {
            "status": "STEP_1_ONLY",
            "input_sha256": INPUT_SHA256,
            "resolution_run_id": run_id,
            "page_candidate_scope": PAGE_CANDIDATE_SCOPE,
            "seed": SEED,
            "sample_indices": indices,
            "sample_count": len(mentions),
            "wiki_page_count": len(pages),
            "stages": dict(Counter(m["matched_stage"] for m in mentions)),
            "unresolved_reasons": dict(
                Counter(
                    m.get("unresolved_reason")
                    for m in mentions
                    if m["matched_stage"] == "SYNTHETIC"
                )
            ),
            "pending_stages": [
                "Entities",
                "Events",
                "Relations",
                "Geography",
                "graph",
                "Agent",
            ],
        },
    }


def run(input_path: Path, cache: Path, output: Path, *, output_approved: bool) -> None:
    # User's explicit hold applies even if free space has increased. Check BEFORE IO.
    if not output_approved:
        raise PermissionError("Wait for user approval for POC data output on D:")
    if output.resolve().drive.upper() != "D:":
        raise ValueError("This POC is approved only for the D: workspace")
    if not output.resolve().is_relative_to(ROOT.resolve()) or output.exists():
        raise ValueError("Use a new output directory within this project")
    result = prepare(
        input_path, cache
    )  # Any exception stops; no silent retries/fallbacks.
    output.mkdir(parents=True, exist_ok=False)
    for name in ("mentions", "wiki_pages", "page_evidence"):
        with gzip.open(output / f"{name}.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(result[name], stream, ensure_ascii=False, allow_nan=False)
    # Manifest is the completion marker for STEP 1, never for the whole pipeline.
    result["manifest"]["outputs"] = {
        p.name: digest(p) for p in output.glob("*.json.gz")
    }
    (output / "manifest.json").write_text(
        json.dumps(result["manifest"], indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    LOG.info("Step 1 complete: %s mentions; later stages pending", SAMPLE_COUNT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=ROOT / "Data/external/daniel_20261017.parquet"
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path.home()
        / ".cache/geoai_full_daniel_dump_bigquery_parallel_20261019",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--output-approved",
        action="store_true",
        help="Use only after explicit user approval for D: data output",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(args.input, args.cache, args.output, output_approved=args.output_approved)


if __name__ == "__main__":
    main()
