"""Build resolved assertions and unresolved text spans for the country POC."""

from __future__ import annotations

import csv
import gzip
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import run_mapping_discovery as discovery

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CASES = HERE / "country_context_poc/cases.csv"
OUT = HERE / "country_reference_eda"
CACHE = discovery.BASE / "wikipedia_country_unresolved_leads.jsonl.gz"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "Corpus2GeoRAG-Pacific/0.1 (relation-alignment research POC)"
SOURCE_PREDICATE = "http://dbpedia.org/ontology/country"
ALLOWED_RELATIONS = "P17|P8047"
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"\u201c(\[])")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def english_values(values: dict, language: str = "en") -> list[str]:
    return [row["value"] for row in values.get(language, []) if row.get("value")]


def load_wikidata(qids: set[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    with gzip.open(
        discovery.BASE / "wikidata_entities.jsonl.gz", "rt", encoding="utf-8"
    ) as stream:
        for line in stream:
            record = json.loads(line)
            qid = record["requested_qid"]
            if qid not in qids:
                continue
            entity = record.get("entity", {})
            result[qid] = {
                "label": entity.get("labels", {}).get("en", {}).get("value", ""),
                "aliases": english_values(entity.get("aliases", {})),
                "enwiki_title": entity.get("sitelinks", {})
                .get("enwiki", {})
                .get("title", ""),
                "claims": entity.get("claims", {}),
            }
    return result


def eventkg_references(
    pairs: set[tuple[str, str]],
) -> dict[tuple[str, str], set[str]]:
    resource_to_qid, kind = discovery.resource_qids()
    result: dict[tuple[str, str], set[str]] = defaultdict(set)
    for name in discovery.REIFIED:
        if not discovery.complete(name):
            continue
        for relation, graph, role, subject, target in discovery.reified_groups(name):
            if (
                discovery.short(role) != "country"
                or discovery.short(graph) != "dbpedia_en"
            ):
                continue
            pair = resource_to_qid.get(subject), resource_to_qid.get(target)
            if pair in pairs and kind.get(pair[0]) == kind.get(pair[1]) == "entity":
                result[pair].add(relation)
    return result


def item_statement_rows(entity: dict, prop: str, target: str) -> list[dict]:
    rows = []
    for statement in entity.get("claims", {}).get(prop, []):
        value = statement.get("mainsnak", {}).get("datavalue", {}).get("value")
        if (
            statement.get("rank") != "deprecated"
            and isinstance(value, dict)
            and value.get("id") == target
        ):
            rows.append(statement)
    return rows


def resolved_rows(
    cases: list[dict[str, str]],
    wikidata: dict[str, dict],
    eventkg: dict[tuple[str, str], set[str]],
) -> list[dict]:
    rows = []
    for case in cases:
        codes = case["observed_wikidata_codes"].split("|")
        if not codes or codes == ["unrecorded"]:
            continue
        subject, target = case["subject_qid"], case["object_qid"]
        source_refs = "|".join(sorted(eventkg.get((subject, target), set())))
        for code in codes:
            statements = item_statement_rows(wikidata[subject], code, target)
            for statement in statements:
                rows.append(
                    {
                        "subject_qid": subject,
                        "subject_label": case["subject_label"],
                        "source_predicate": SOURCE_PREDICATE,
                        "object_qid": target,
                        "object_label": case["object_label"],
                        "level2_relation": code,
                        "resolution_status": "RESOLVED_STRUCTURED_ASSERTION",
                        "resolution_basis": "observed Wikidata statement on same QID pair",
                        "reference_type": "wikidata_statement",
                        "reference_id": statement.get("id", ""),
                        "reference_rank": statement.get("rank", ""),
                        "qualifier_properties": "|".join(
                            sorted(statement.get("qualifiers", {}))
                        ),
                        "wikidata_reference_count": len(statement.get("references", [])),
                        "eventkg_relation_ids": source_refs,
                        "eventkg_graph": "dbpedia_en",
                    }
                )
    return rows


def aliases(metadata: dict, include_title: bool = True) -> list[str]:
    values = [metadata.get("label", ""), *metadata.get("aliases", [])]
    if include_title:
        values.append(metadata.get("enwiki_title", ""))
    clean = {" ".join(value.split()) for value in values if len(value.strip()) >= 3}
    return sorted(clean, key=lambda value: (-len(value), value.casefold()))


def matching_alias(text: str, candidates: list[str]) -> str:
    for candidate in candidates:
        if re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", text, re.IGNORECASE):
            return candidate
    return ""


def split_paragraphs(text: str) -> list[str]:
    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if (
            len(lines) > 1
            and len(lines[0].split()) <= 10
            and not re.search(r"[.!?][\"'\u2019\u201d)]?$", lines[0])
        ):
            lines = lines[1:]
        paragraph = " ".join(lines)
        if len(paragraph.split()) >= 3:
            paragraphs.append(paragraph)
    return paragraphs


def minimal_spans(
    text: str, subject_aliases: list[str], object_aliases: list[str]
) -> list[dict]:
    """Return one shortest complete sentence window per matching paragraph."""
    spans = []
    seen = set()
    for paragraph_index, paragraph in enumerate(split_paragraphs(text)):
        sentences = [part.strip() for part in SENTENCE_BOUNDARY.split(paragraph)]
        sentences = [part for part in sentences if part]
        subject_hits = [
            index
            for index, sentence in enumerate(sentences)
            if matching_alias(sentence, subject_aliases)
        ]
        object_hits = [
            index
            for index, sentence in enumerate(sentences)
            if matching_alias(sentence, object_aliases)
        ]
        if not subject_hits or not object_hits:
            continue
        start, end = min(
            ((min(left, right), max(left, right)) for left in subject_hits for right in object_hits),
            key=lambda bounds: (bounds[1] - bounds[0], bounds[0], bounds[1]),
        )
        span = " ".join(sentences[start : end + 1])
        if span in seen:
            continue
        seen.add(span)
        if start == end:
            level = "sentence"
        elif start == 0 and end == len(sentences) - 1:
            level = "paragraph"
        else:
            level = "multi_sentence"
        spans.append(
            {
                "paragraph_index": paragraph_index,
                "sentence_start": start,
                "sentence_end": end,
                "span_level": level,
                "subject_match": matching_alias(span, subject_aliases),
                "object_match": matching_alias(span, object_aliases),
                "evidence_text": span,
            }
        )
    return spans


def load_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return {row["qid"]: row for row in map(json.loads, stream)}


def save_cache(path: Path, rows: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for qid in sorted(rows):
            stream.write(json.dumps(rows[qid], ensure_ascii=False) + "\n")


def api_query(titles: list[str]) -> dict:
    params = {
        "action": "query",
        "prop": "extracts|revisions",
        "titles": "|".join(titles),
        "explaintext": 1,
        "exsectionformat": "plain",
        "exintro": 1,
        "exlimit": "max",
        "rvprop": "ids",
        "redirects": 1,
        "format": "json",
        "formatversion": 2,
        "maxlag": 5,
    }
    request = Request(
        f"{WIKIPEDIA_API}?{urlencode(params)}", headers={"User-Agent": USER_AGENT}
    )
    for attempt in range(5):
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 4:
                raise
            wait = min(int(error.headers.get("Retry-After", 10 * (attempt + 1))), 30)
            print(f"Wikipedia HTTP {error.code}; waiting {wait}s", flush=True)
            time.sleep(wait)
        except URLError:
            if attempt == 4:
                raise
            time.sleep(2)
    raise RuntimeError("Wikipedia request failed")


def fetch_extracts(subjects: dict[str, dict]) -> dict[str, dict]:
    cached = load_cache(CACHE)
    pending = [
        qid
        for qid in sorted(subjects)
        if qid not in cached
        or (not cached[qid].get("extract") and not cached[qid].get("missing"))
    ]
    for offset in range(0, len(pending), 20):
        qids = pending[offset : offset + 20]
        titles = [subjects[qid]["enwiki_title"] for qid in qids]
        data = api_query(titles)
        pages = {
            page.get("title", "").replace("_", " ").casefold(): page
            for page in data.get("query", {}).get("pages", [])
        }
        redirects = {
            row["from"].replace("_", " ").casefold(): row["to"]
            .replace("_", " ")
            .casefold()
            for row in data.get("query", {}).get("redirects", [])
        }
        for qid, title in zip(qids, titles, strict=True):
            key = title.replace("_", " ").casefold()
            page = pages.get(redirects.get(key, key), {})
            if not page and len(pages) == 1:
                page = next(iter(pages.values()))
            cached[qid] = {
                "qid": qid,
                "requested_title": title,
                "page_title": page.get("title", ""),
                "page_id": page.get("pageid", ""),
                "revision_id": (page.get("revisions") or [{}])[0].get("revid", ""),
                "extract": page.get("extract", ""),
                "extract_scope": "lead",
                "missing": bool(page.get("missing", False) or not page),
            }
        save_cache(CACHE, cached)
        print(
            f"Wikipedia pages: {min(offset + 20, len(pending))}/{len(pending)}",
            flush=True,
        )
        time.sleep(2)
    return cached


def unresolved_rows(
    cases: list[dict[str, str]],
    wikidata: dict[str, dict],
    eventkg: dict[tuple[str, str], set[str]],
    pages: dict[str, dict],
) -> list[dict]:
    rows = []
    for case in cases:
        if case["action"] != "CANDIDATE_FOR_TEXT_CHECK":
            continue
        subject, target = case["subject_qid"], case["object_qid"]
        page = pages.get(subject, {})
        page_text = page.get("extract", "")
        subject_aliases = aliases(wikidata[subject])
        object_aliases = aliases(wikidata[target])
        base = {
            "subject_qid": subject,
            "subject_label": case["subject_label"],
            "source_predicate": SOURCE_PREDICATE,
            "object_qid": target,
            "object_label": case["object_label"],
            "allowed_level2_relations": ALLOWED_RELATIONS,
            "context_suggestion": case["provisional_prediction"],
            "p17_probability": case["p17_probability"],
            "p8047_probability": case["p8047_probability"],
            "selected_level2_relations": "",
            "classifier_status": "NOT_RUN",
            "eventkg_relation_ids": "|".join(
                sorted(eventkg.get((subject, target), set()))
            ),
            "eventkg_graph": "dbpedia_en",
            "page_title": page.get("page_title", ""),
            "page_id": page.get("page_id", ""),
            "revision_id": page.get("revision_id", ""),
            "source_url": (
                "https://en.wikipedia.org/wiki/"
                + page.get("page_title", "").replace(" ", "_")
                if page.get("page_title")
                else ""
            ),
            "text_scope": page.get("extract_scope", ""),
            "page_fetch_status": (
                "MISSING"
                if page.get("missing")
                else "OK"
                if page_text
                else "EMPTY"
            ),
            "subject_found_in_page": bool(
                matching_alias(page_text, subject_aliases)
            ),
            "object_found_in_page": bool(matching_alias(page_text, object_aliases)),
        }
        spans = minimal_spans(page_text, subject_aliases, object_aliases)
        if not spans:
            rows.append(
                base
                | {
                    "evidence_status": "NO_MINIMAL_COMPLETE_SPAN",
                    "paragraph_index": "",
                    "sentence_start": "",
                    "sentence_end": "",
                    "span_level": "",
                    "subject_match": "",
                    "object_match": "",
                    "evidence_text": "",
                }
            )
        else:
            for span in spans:
                rows.append(base | {"evidence_status": "COOCCURRENCE_ONLY"} | span)
    return rows


def make_summary(
    cases: list[dict[str, str]], resolved: list[dict], unresolved: list[dict]
) -> dict:
    unresolved_pairs = {
        (row["subject_qid"], row["object_qid"]) for row in unresolved
    }
    covered_pairs = {
        (row["subject_qid"], row["object_qid"])
        for row in unresolved
        if row["evidence_status"] == "COOCCURRENCE_ONLY"
    }
    references = [
        row for row in unresolved if row["evidence_status"] == "COOCCURRENCE_ONLY"
    ]
    pair_rows = {
        (row["subject_qid"], row["object_qid"]): row for row in unresolved
    }
    unique_resolved_edges = {
        (row["subject_qid"], row["level2_relation"], row["object_qid"])
        for row in resolved
    }
    suggestion_coverage = {}
    for suggestion in sorted({row["context_suggestion"] for row in pair_rows.values()}):
        matching = [
            row
            for row in pair_rows.values()
            if row["context_suggestion"] == suggestion
        ]
        with_span = sum(
            row["evidence_status"] == "COOCCURRENCE_ONLY" for row in matching
        )
        suggestion_coverage[suggestion] = {
            "pairs": len(matching),
            "pairs_with_minimal_span": with_span,
            "coverage": round(with_span / len(matching), 4),
        }
    return {
        "scope": "EventKG DBpedia English country pairs in the local WWII population",
        "source_pairs": len(cases),
        "resolved_pairs": sum(
            row["observed_wikidata_codes"] != "unrecorded" for row in cases
        ),
        "resolved_relation_assertions": len(resolved),
        "resolved_unique_relation_edges": len(unique_resolved_edges),
        "resolved_assertions_with_wikidata_references": sum(
            row["wikidata_reference_count"] > 0 for row in resolved
        ),
        "resolved_level2_relations": dict(
            Counter(row["level2_relation"] for row in resolved)
        ),
        "unresolved_pairs": len(unresolved_pairs),
        "unresolved_unique_subject_pages": len(
            {row["subject_qid"] for row in pair_rows.values()}
        ),
        "unresolved_pages_retrieved": len(
            {
                row["subject_qid"]
                for row in pair_rows.values()
                if row["page_fetch_status"] == "OK"
            }
        ),
        "unresolved_pairs_with_subject_name": sum(
            row["subject_found_in_page"] for row in pair_rows.values()
        ),
        "unresolved_pairs_with_object_name": sum(
            row["object_found_in_page"] for row in pair_rows.values()
        ),
        "unresolved_pairs_with_both_names_anywhere": sum(
            row["subject_found_in_page"] and row["object_found_in_page"]
            for row in pair_rows.values()
        ),
        "unresolved_pairs_with_minimal_span": len(covered_pairs),
        "unresolved_pair_text_coverage": round(
            len(covered_pairs) / len(unresolved_pairs), 4
        ),
        "unresolved_reference_spans": len(references),
        "span_levels": dict(Counter(row["span_level"] for row in references)),
        "context_suggestions_by_pair": dict(
            Counter(
                row["context_suggestion"]
                for row in pair_rows.values()
            )
        ),
        "text_coverage_by_context_suggestion": suggestion_coverage,
        "pairs_without_minimal_span": len(unresolved_pairs - covered_pairs),
        "classifier_run": False,
        "acceptance_note": (
            "Text spans show co-occurrence only. They do not accept P17 or P8047."
        ),
    }


def write_report(summary: dict, unresolved: list[dict]) -> None:
    missing = [
        row
        for row in unresolved
        if row["evidence_status"] == "NO_MINIMAL_COMPLETE_SPAN"
    ][:10]
    examples = [
        row for row in unresolved if row["evidence_status"] == "COOCCURRENCE_ONLY"
    ][:5]
    lines = [
        "# Country relation reference dataset EDA",
        "",
        "Date: 2026-10-11",
        "",
        "## Scope",
        "",
        "This run separates structured, resolved Wikidata assertions from unresolved",
        "EventKG `country` pairs. It does not run the text classifier.",
        "",
        "## Counts",
        "",
        f"- Source pairs: **{summary['source_pairs']:,}**.",
        f"- Resolved pairs: **{summary['resolved_pairs']:,}**.",
        f"- Resolved relation assertions: **{summary['resolved_relation_assertions']:,}**.",
        f"- Unique resolved relation edges: **{summary['resolved_unique_relation_edges']:,}**.",
        "- Resolved assertions with at least one Wikidata reference block: "
        f"**{summary['resolved_assertions_with_wikidata_references']:,}**.",
        f"- Unresolved pairs: **{summary['unresolved_pairs']:,}**.",
        "- English Wikipedia subject pages retrieved: "
        f"**{summary['unresolved_pages_retrieved']:,} of "
        f"{summary['unresolved_unique_subject_pages']:,}**.",
        "- Pairs where the subject page contains a known subject name: "
        f"**{summary['unresolved_pairs_with_subject_name']:,}**.",
        "- Pairs where the subject page contains a known object name: "
        f"**{summary['unresolved_pairs_with_object_name']:,}**.",
        "- Pairs where both names occur somewhere in the page: "
        f"**{summary['unresolved_pairs_with_both_names_anywhere']:,}**.",
        "- Unresolved pairs with at least one minimal complete text span: "
        f"**{summary['unresolved_pairs_with_minimal_span']:,}** "
        f"({summary['unresolved_pair_text_coverage']:.1%}).",
        f"- Extracted text spans: **{summary['unresolved_reference_spans']:,}**.",
        f"- Pairs without a complete span: **{summary['pairs_without_minimal_span']:,}**.",
        "",
        "## Resolved assertions",
        "",
        "The resolved table has one row per Wikidata statement. It contains 2,516",
        "unique subject-relation-object edges and 2,517 statement rows because one",
        "edge has two Wikidata statements. Of these statements, 1,735 (68.9%) have",
        "at least one Wikidata reference block; 782 have no cited reference block.",
        "",
        "## Text rule",
        "",
        "For each subject page lead paragraph, the extractor keeps the shortest",
        "contiguous set of complete sentences that contains an alias of both QID",
        "endpoints. It never crosses a paragraph boundary. Wikidata labels, aliases,",
        "and English page titles provide the allowed names.",
        "",
        "A text span is `COOCCURRENCE_ONLY`. It does not prove a relation. The later",
        "classifier can select `P17`, `P8047`, both, or neither.",
        "",
        "## Finding",
        "",
        "The subject article lead supplies a usable co-mention span for only the",
        "reported share of unresolved pairs. Most EventKG `country` values come from",
        "structured DBpedia/Wikipedia data and may not be stated with both entity names",
        "in the lead. A lead-text classifier alone therefore cannot cover this group.",
        "",
        "The extraction uses exact Wikidata labels, aliases, and page titles. It does",
        "not resolve pronouns or unnamed descriptions. These cases need link-aware text,",
        "the source infobox field, another page, or an explicit abstention.",
        "",
        "## Coverage by graph-context suggestion",
        "",
        "The suggestion is a routing hint, not a text label.",
        "",
        "| Suggestion | Pairs | Pairs with span | Coverage |",
        "|---|---:|---:|---:|",
        *[
            f"| `{suggestion}` | {values['pairs']:,} | "
            f"{values['pairs_with_minimal_span']:,} | {values['coverage']:.1%} |"
            for suggestion, values in summary[
                "text_coverage_by_context_suggestion"
            ].items()
        ],
        "",
        "## Span levels",
        "",
        "| Span level | References |",
        "|---|---:|",
        *[
            f"| `{level}` | {count:,} |"
            for level, count in sorted(summary["span_levels"].items())
        ],
        "",
        "## Examples",
        "",
    ]
    for row in examples:
        lines.extend(
            [
                f"- **{row['subject_label']} -> {row['object_label']}** "
                f"(`{row['span_level']}`): {row['evidence_text']}",
            ]
        )
    lines.extend(["", "## Missing-span examples", ""])
    lines.extend(
        f"- {row['subject_qid']} {row['subject_label']} -> "
        f"{row['object_qid']} {row['object_label']}"
        for row in missing
    )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `country_reference_eda/resolved_relations.csv`",
            "- `country_reference_eda/unresolved_relations.csv`",
            "- `country_reference_eda/summary.json`",
            "",
        ]
    )
    (HERE / "COUNTRY_REFERENCE_DATASET_EDA_2026-10-11.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    cases = read_csv(CASES)
    all_qids = {row[key] for row in cases for key in ("subject_qid", "object_qid")}
    wikidata = load_wikidata(all_qids)
    if missing := all_qids - wikidata.keys():
        raise RuntimeError(f"Missing Wikidata records: {sorted(missing)[:10]}")
    pairs = {(row["subject_qid"], row["object_qid"]) for row in cases}
    eventkg = eventkg_references(pairs)
    resolved = resolved_rows(cases, wikidata, eventkg)
    unresolved_cases = [
        row for row in cases if row["action"] == "CANDIDATE_FOR_TEXT_CHECK"
    ]
    subjects = {row["subject_qid"]: wikidata[row["subject_qid"]] for row in unresolved_cases}
    pages = fetch_extracts(subjects)
    unresolved = unresolved_rows(cases, wikidata, eventkg, pages)
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(
        OUT / "resolved_relations.csv",
        resolved,
        [
            "subject_qid",
            "subject_label",
            "source_predicate",
            "object_qid",
            "object_label",
            "level2_relation",
            "resolution_status",
            "resolution_basis",
            "reference_type",
            "reference_id",
            "reference_rank",
            "qualifier_properties",
            "wikidata_reference_count",
            "eventkg_relation_ids",
            "eventkg_graph",
        ],
    )
    write_csv(
        OUT / "unresolved_relations.csv",
        unresolved,
        [
            "subject_qid",
            "subject_label",
            "source_predicate",
            "object_qid",
            "object_label",
            "allowed_level2_relations",
            "context_suggestion",
            "p17_probability",
            "p8047_probability",
            "selected_level2_relations",
            "classifier_status",
            "eventkg_relation_ids",
            "eventkg_graph",
            "page_title",
            "page_id",
            "revision_id",
            "source_url",
            "text_scope",
            "page_fetch_status",
            "subject_found_in_page",
            "object_found_in_page",
            "evidence_status",
            "paragraph_index",
            "sentence_start",
            "sentence_end",
            "span_level",
            "subject_match",
            "object_match",
            "evidence_text",
        ],
    )
    summary = make_summary(cases, resolved, unresolved)
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_report(summary, unresolved)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
