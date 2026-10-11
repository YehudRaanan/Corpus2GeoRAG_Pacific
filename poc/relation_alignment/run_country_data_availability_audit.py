"""Audit whether unresolved country pairs lack relations or accessible evidence."""

from __future__ import annotations

import gzip
import html
import json
import re
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import build_country_reference_dataset as reference

HERE = Path(__file__).resolve().parent
INPUT = HERE / "country_reference_eda/unresolved_relations.csv"
OUT = HERE / "country_data_availability_audit"
WIKIDATA_CACHE = (
    reference.discovery.BASE / "wikidata_country_unresolved_current.jsonl.gz"
)
WIKITEXT_CACHE = (
    reference.discovery.BASE / "wikipedia_country_unresolved_wikitext.jsonl.gz"
)
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
ITEM_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
REF = re.compile(r"<ref\b[^>]*>.*?</ref\s*>|<ref\b[^>]*/\s*>", re.I | re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)
HTML_TAG = re.compile(r"<[^>]+>")
EXTERNAL_LINK = re.compile(r"\[(?:https?://|//)[^\s\]]+(?:\s+([^\]]+))?\]")
TABLE = re.compile(r"\{\|.*?\|\}", re.S)
NON_ARTICLE_TAIL = re.compile(
    r"^==+\s*(?:see also|notes|references|sources|bibliography|further reading|external links)\s*==+\s*$",
    re.I | re.M,
)
TARGETS = {"P17", "P8047"}


def fetch_json(url: str, params: dict) -> dict:
    request = Request(
        f"{url}?{urlencode(params)}", headers={"User-Agent": reference.USER_AGENT}
    )
    for attempt in range(5):
        try:
            with urlopen(request, timeout=90) as response:
                data = json.load(response)
            if error := data.get("error"):
                raise RuntimeError(
                    f"API error {error.get('code', 'unknown')}: "
                    f"{error.get('info', 'no details')}"
                )
            return data
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 4:
                raise
            wait = min(int(error.headers.get("Retry-After", 10 * (attempt + 1))), 30)
            print(f"HTTP {error.code}; waiting {wait}s", flush=True)
            time.sleep(wait)
        except URLError:
            if attempt == 4:
                raise
            time.sleep(2)
    raise RuntimeError("API request failed")


def load_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return {row["id"]: row for row in map(json.loads, stream)}


def save_cache(path: Path, rows: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for key in sorted(rows):
            stream.write(json.dumps(rows[key], ensure_ascii=False) + "\n")


def fetch_current_wikidata(qids: set[str]) -> dict[str, dict]:
    cached = load_cache(WIKIDATA_CACHE)
    pending = [qid for qid in sorted(qids) if qid not in cached]
    for offset in range(0, len(pending), 50):
        batch = pending[offset : offset + 50]
        data = fetch_json(
            WIKIDATA_API,
            {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "claims|labels|sitelinks|info",
                "languages": "en",
                "sitefilter": "enwiki",
                "format": "json",
                "formatversion": 2,
            },
        )
        for qid in batch:
            entity = data.get("entities", {}).get(qid, {"id": qid, "missing": True})
            cached[qid] = {"id": qid, "entity": entity}
        save_cache(WIKIDATA_CACHE, cached)
        print(f"Current Wikidata: {min(offset + 50, len(pending))}/{len(pending)}", flush=True)
        time.sleep(1)
    return {qid: row["entity"] for qid, row in cached.items() if qid in qids}


def fetch_wikitext(subjects: dict[str, str]) -> dict[str, dict]:
    cached = load_cache(WIKITEXT_CACHE)
    pending = [qid for qid in sorted(subjects) if qid not in cached]
    for offset in range(0, len(pending), 20):
        qids = pending[offset : offset + 20]
        titles = [subjects[qid] for qid in qids]
        data = fetch_json(
            WIKIPEDIA_API,
            {
                "action": "query",
                "prop": "revisions",
                "titles": "|".join(titles),
                "rvprop": "ids|content",
                "rvslots": "main",
                "redirects": 1,
                "format": "json",
                "formatversion": 2,
            },
        )
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
            revision = (page.get("revisions") or [{}])[0]
            cached[qid] = {
                "id": qid,
                "requested_title": title,
                "page_title": page.get("title", ""),
                "page_id": page.get("pageid", ""),
                "revision_id": revision.get("revid", ""),
                "wikitext": revision.get("slots", {}).get("main", {}).get("content", ""),
                "missing": bool(page.get("missing", False) or not page),
            }
        save_cache(WIKITEXT_CACHE, cached)
        print(f"Full wikitext: {min(offset + 20, len(pending))}/{len(pending)}", flush=True)
        time.sleep(2)
    return {qid: row for qid, row in cached.items() if qid in subjects}


def item_value(statement: dict) -> str:
    value = statement.get("mainsnak", {}).get("datavalue", {}).get("value")
    return value.get("id", "") if isinstance(value, dict) else ""


def relation_paths(entity: dict, target: str) -> tuple[set[str], set[str]]:
    direct, qualifier = set(), set()
    for prop, statements in entity.get("claims", {}).items():
        for statement in statements:
            if statement.get("rank") == "deprecated":
                continue
            if item_value(statement) == target:
                direct.add(prop)
            for qualifier_prop, values in statement.get("qualifiers", {}).items():
                for value in values:
                    item = value.get("datavalue", {}).get("value")
                    if isinstance(item, dict) and item.get("id") == target:
                        qualifier.add(f"{prop}/{qualifier_prop}")
    return direct, qualifier


def normalized_title(value: str) -> str:
    return " ".join(value.replace("_", " ").split()).casefold()


def linked_anchors(wikitext: str, target_title: str) -> list[str]:
    expected = normalized_title(target_title)
    anchors = set()
    for target, anchor in ITEM_LINK.findall(wikitext):
        if normalized_title(target) == expected:
            anchors.add(" ".join((anchor or target).split()))
    return sorted(anchors, key=lambda value: (-len(value), value.casefold()))


def balanced_template(text: str, name: str = "infobox") -> str:
    templates = balanced_templates(text, name)
    return templates[0] if templates else ""


def balanced_templates(text: str, name: str = "infobox") -> list[str]:
    """Return every named template, including nested ship infobox sections."""
    templates = []
    matches = re.finditer(rf"\{{\{{\s*{re.escape(name)}\b", text, re.I)
    for match in matches:
        depth = 0
        index = match.start()
        while index < len(text) - 1:
            token = text[index : index + 2]
            if token == "{{":
                depth += 1
                index += 2
                continue
            if token == "}}":
                depth -= 1
                index += 2
                if depth == 0:
                    templates.append(text[match.start() : index])
                    break
                continue
            index += 1
    return templates


def infobox_field_matches(
    wikitext: str, target_title: str, object_aliases: list[str]
) -> dict[str, str]:
    matches = {}
    for template in balanced_templates(wikitext):
        matches.update(
            field_matches(template_fields(template), target_title, object_aliases)
        )
    return matches


def remove_templates(text: str) -> str:
    result, index, depth = [], 0, 0
    while index < len(text):
        token = text[index : index + 2]
        if token == "{{":
            depth += 1
            index += 2
        elif token == "}}" and depth:
            depth -= 1
            index += 2
        else:
            if depth == 0:
                result.append(text[index])
            index += 1
    return "".join(result)


def template_fields(template: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current = ""
    parts: list[str] = []
    body = template[:-2] if template.endswith("}}") else template
    for line in body.splitlines()[1:]:
        match = re.match(r"\s*\|\s*([^=]+?)\s*=\s*(.*)$", line)
        if match:
            if current:
                fields[current] = "\n".join(parts).strip()
            current = " ".join(match.group(1).split()).casefold()
            parts = [match.group(2)]
        elif current:
            parts.append(line)
    if current:
        fields[current] = "\n".join(parts).strip()
    return fields


def plain_wikitext(wikitext: str) -> str:
    text = COMMENT.sub("", wikitext)
    text = REF.sub("", text)
    text = TABLE.sub("\n\n", text)
    text = re.sub(r"^={2,}.*?={2,}\s*$", "\n\n", text, flags=re.M)
    text = remove_templates(text)

    def link_text(match: re.Match) -> str:
        target, anchor = match.groups()
        if target.casefold().startswith(("file:", "image:", "category:")):
            return ""
        return anchor or target

    text = ITEM_LINK.sub(link_text, text)
    text = EXTERNAL_LINK.sub(lambda match: match.group(1) or "", text)
    text = HTML_TAG.sub("", text)
    text = html.unescape(text.replace("'''", "").replace("''", ""))
    text = re.sub(r"^[*#:;]+\s*", "", text, flags=re.M)
    return text


def article_body_wikitext(wikitext: str, infobox: str) -> str:
    body = wikitext.replace(infobox, "", 1) if infobox else wikitext
    tail = NON_ARTICLE_TAIL.search(body)
    return body[: tail.start()] if tail else body


def object_spans(text: str, object_aliases: list[str]) -> list[dict]:
    """Return body sentences that identify the object; the page identifies the subject."""
    spans = []
    seen = set()
    for paragraph_index, paragraph in enumerate(reference.split_paragraphs(text)):
        sentences = [part.strip() for part in reference.SENTENCE_BOUNDARY.split(paragraph)]
        for sentence_index, sentence in enumerate(part for part in sentences if part):
            match = reference.matching_alias(sentence, object_aliases)
            if not match or sentence in seen:
                continue
            seen.add(sentence)
            spans.append(
                {
                    "paragraph_index": paragraph_index,
                    "sentence_start": sentence_index,
                    "sentence_end": sentence_index,
                    "span_level": "sentence",
                    "object_match": match,
                    "evidence_text": sentence,
                }
            )
    return spans


def field_matches(
    fields: dict[str, str], target_title: str, object_aliases: list[str]
) -> dict[str, str]:
    result = {}
    for name, value in fields.items():
        if linked_anchors(value, target_title) or reference.matching_alias(
            plain_wikitext(value), object_aliases
        ):
            result[name] = " ".join(plain_wikitext(value).split())[:1000]
    return result


def availability_status(row: dict) -> str:
    if row["current_target_relations"]:
        return "CURRENT_WIKIDATA_TARGET_RELATION_OBSERVED"
    if row["alternative_forward_properties"] or row["alternative_inverse_properties"]:
        return "ALTERNATIVE_WIKIDATA_RELATION_OBSERVED"
    if row["qualifier_relation_paths"]:
        return "WIKIDATA_QUALIFIER_RELATION_OBSERVED"
    if row["page_anchored_evidence_text"]:
        return "PAGE_ANCHORED_BODY_TEXT_EVIDENCE_OBSERVED"
    if row["infobox_matching_fields"]:
        return "INFOBOX_ENTITY_EVIDENCE_OBSERVED"
    if row["full_article_object_link_anchors"]:
        return "FULL_ARTICLE_ENTITY_LINK_OBSERVED"
    if row["full_article_evidence_text"]:
        return "FULL_ARTICLE_TEXT_COOCCURRENCE_OBSERVED"
    if row["lead_evidence_status"] == "COOCCURRENCE_IN_LEAD_ONLY":
        return "LEAD_TEXT_COOCCURRENCE_OBSERVED"
    return "DATA_NOT_OBSERVED_IN_CHECKED_SOURCES"


def property_labels(properties: set[str]) -> dict[str, str]:
    labels = {}
    ordered = sorted(properties)
    for offset in range(0, len(ordered), 50):
        data = fetch_json(
            WIKIDATA_API,
            {
                "action": "wbgetentities",
                "ids": "|".join(ordered[offset : offset + 50]),
                "props": "labels",
                "languages": "en",
                "format": "json",
                "formatversion": 2,
            },
        )
        labels.update(
            {
                prop: entity.get("labels", {}).get("en", {}).get("value", "")
                for prop, entity in data.get("entities", {}).items()
            }
        )
        time.sleep(1)
    return labels


def audit_rows(rows: list[dict[str, str]]) -> tuple[list[dict], dict[str, str]]:
    local = reference.load_wikidata(
        {row[key] for row in rows for key in ("subject_qid", "object_qid")}
    )
    current = fetch_current_wikidata(set(local))
    subjects = {row["subject_qid"]: row["page_title"] for row in rows}
    wikitexts = fetch_wikitext(subjects)
    output = []
    found_properties = set()
    for source in rows:
        subject, target = source["subject_qid"], source["object_qid"]
        forward, forward_qualifiers = relation_paths(current[subject], target)
        inverse, inverse_qualifiers = relation_paths(current[target], subject)
        current_targets = forward & TARGETS
        alternatives = forward - TARGETS
        found_properties.update(alternatives | inverse)
        target_title = local[target]["enwiki_title"]
        object_aliases = reference.aliases(local[target])
        subject_aliases = reference.aliases(local[subject])
        page = wikitexts[subject]
        wikitext = page.get("wikitext", "")
        infobox = balanced_template(wikitext)
        fields = infobox_field_matches(wikitext, target_title, object_aliases)
        anchors = linked_anchors(wikitext, target_title)
        body_wikitext = article_body_wikitext(wikitext, infobox)
        body_anchors = linked_anchors(body_wikitext, target_title)
        body_text = plain_wikitext(body_wikitext)
        spans = reference.minimal_spans(
            body_text, subject_aliases, sorted(set(object_aliases + body_anchors))
        )
        span = min(
            spans,
            key=lambda value: (
                value["sentence_end"] - value["sentence_start"],
                len(value["evidence_text"]),
            ),
        ) if spans else {}
        page_spans = object_spans(
            body_text, sorted(set(object_aliases + body_anchors))
        )
        page_span = min(
            page_spans, key=lambda value: len(value["evidence_text"])
        ) if page_spans else {}
        result = {
            "subject_qid": subject,
            "subject_label": source["subject_label"],
            "object_qid": target,
            "object_label": source["object_label"],
            "source_predicate": source["source_predicate"],
            "allowed_level2_relations": source["allowed_level2_relations"],
            "context_suggestion": source["context_suggestion"],
            "local_snapshot_relation_status": "RELATION_NOT_OBSERVED_IN_LOCAL_SNAPSHOT",
            "current_wikidata_revision": current[subject].get("lastrevid", ""),
            "current_target_relations": "|".join(sorted(current_targets)),
            "alternative_forward_properties": "|".join(sorted(alternatives)),
            "alternative_inverse_properties": "|".join(sorted(inverse)),
            "qualifier_relation_paths": "|".join(
                sorted(forward_qualifiers | {f"INVERSE:{x}" for x in inverse_qualifiers})
            ),
            "page_title": page.get("page_title", ""),
            "wikipedia_revision_id": page.get("revision_id", ""),
            "infobox_matching_fields": "|".join(sorted(fields)),
            "infobox_matching_values": json.dumps(fields, ensure_ascii=False),
            "full_article_object_link_anchors": "|".join(anchors),
            "body_object_link_anchors": "|".join(body_anchors),
            "full_article_span_level": span.get("span_level", ""),
            "full_article_subject_match": span.get("subject_match", ""),
            "full_article_object_match": span.get("object_match", ""),
            "full_article_evidence_text": span.get("evidence_text", ""),
            "page_anchored_span_level": page_span.get("span_level", ""),
            "page_anchored_object_match": page_span.get("object_match", ""),
            "page_anchored_evidence_text": page_span.get("evidence_text", ""),
            "lead_evidence_status": source["evidence_status"],
            "lead_evidence_text": source["evidence_text"],
        }
        result["availability_status"] = availability_status(result)
        if current_targets:
            result["relation_resolution_status"] = (
                "RESOLVED_BY_CURRENT_WIKIDATA_TARGET"
            )
        elif alternatives or inverse:
            result["relation_resolution_status"] = (
                "RESOLVED_BY_ALTERNATIVE_WIKIDATA_PROPERTY"
            )
        else:
            result["relation_resolution_status"] = "RELATION_SEMANTICS_UNRESOLVED"
        output.append(result)
    return output, property_labels(found_properties)


def make_summary(rows: list[dict], labels: dict[str, str]) -> dict:
    statuses = Counter(row["availability_status"] for row in rows)
    forward = Counter(
        prop
        for row in rows
        for prop in row["alternative_forward_properties"].split("|")
        if prop
    )
    inverse = Counter(
        prop
        for row in rows
        for prop in row["alternative_inverse_properties"].split("|")
        if prop
    )
    fields = Counter(
        field
        for row in rows
        for field in row["infobox_matching_fields"].split("|")
        if field
    )
    return {
        "pairs": len(rows),
        "status_counts": dict(statuses),
        "current_wikidata_target_relation_pairs": sum(
            bool(row["current_target_relations"]) for row in rows
        ),
        "alternative_forward_relation_pairs": sum(
            bool(row["alternative_forward_properties"]) for row in rows
        ),
        "alternative_inverse_relation_pairs": sum(
            bool(row["alternative_inverse_properties"]) for row in rows
        ),
        "qualifier_relation_pairs": sum(
            bool(row["qualifier_relation_paths"]) for row in rows
        ),
        "infobox_entity_evidence_pairs": sum(
            bool(row["infobox_matching_fields"]) for row in rows
        ),
        "full_article_object_link_pairs": sum(
            bool(row["full_article_object_link_anchors"]) for row in rows
        ),
        "full_article_complete_span_pairs": sum(
            bool(row["full_article_evidence_text"]) for row in rows
        ),
        "page_anchored_body_span_pairs": sum(
            bool(row["page_anchored_evidence_text"]) for row in rows
        ),
        "lead_complete_span_pairs": sum(
            row["lead_evidence_status"] == "COOCCURRENCE_IN_LEAD_ONLY"
            for row in rows
        ),
        "relation_semantics_unresolved_pairs": sum(
            row["relation_resolution_status"] == "RELATION_SEMANTICS_UNRESOLVED"
            for row in rows
        ),
        "resolved_by_structured_wikidata_pairs": sum(
            row["relation_resolution_status"]
            != "RELATION_SEMANTICS_UNRESOLVED"
            for row in rows
        ),
        "unresolved_with_checked_evidence_pairs": sum(
            row["relation_resolution_status"] == "RELATION_SEMANTICS_UNRESOLVED"
            and row["availability_status"]
            != "DATA_NOT_OBSERVED_IN_CHECKED_SOURCES"
            for row in rows
        ),
        "unresolved_without_checked_evidence_pairs": sum(
            row["relation_resolution_status"] == "RELATION_SEMANTICS_UNRESOLVED"
            and row["availability_status"]
            == "DATA_NOT_OBSERVED_IN_CHECKED_SOURCES"
            for row in rows
        ),
        "top_forward_properties": [
            {"property": prop, "label": labels.get(prop, ""), "pairs": count}
            for prop, count in forward.most_common(15)
        ],
        "top_inverse_properties": [
            {"property": prop, "label": labels.get(prop, ""), "pairs": count}
            for prop, count in inverse.most_common(15)
        ],
        "top_qualifier_paths": [
            {"path": path, "pairs": count}
            for path, count in Counter(
                path
                for row in rows
                for path in row["qualifier_relation_paths"].split("|")
                if path
            ).most_common(15)
        ],
        "top_infobox_fields": [
            {"field": field, "pairs": count} for field, count in fields.most_common(15)
        ],
        "classifier_run": False,
        "interpretation": (
            "An absent relation or text span means not observed in the checked source, "
            "not a negative fact."
        ),
    }


def write_report(summary: dict, rows: list[dict]) -> None:
    lines = [
        "# Country relation data-availability audit",
        "",
        "Date: 2026-10-11",
        "",
        "## Question",
        "",
        "Do the 600 unresolved pairs lack a relation, or did the earlier run lack",
        "the data needed to observe it?",
        "",
        "## Results",
        "",
        f"- Current Wikidata now has `P17` or `P8047` for **{summary['current_wikidata_target_relation_pairs']:,}** pairs.",
        f"- Another forward Wikidata property connects the same QIDs for **{summary['alternative_forward_relation_pairs']:,}** pairs.",
        f"- An inverse Wikidata property connects the same QIDs for **{summary['alternative_inverse_relation_pairs']:,}** pairs.",
        f"- A Wikidata qualifier path connects the same QIDs for **{summary['qualifier_relation_pairs']:,}** pairs.",
        f"- A Wikipedia infobox field contains the object identity for **{summary['infobox_entity_evidence_pairs']:,}** pairs.",
        f"- The complete article links to the object identity for **{summary['full_article_object_link_pairs']:,}** pairs.",
        f"- The complete article has a minimal sentence-to-paragraph span for **{summary['full_article_complete_span_pairs']:,}** pairs.",
        f"- With the page QID as the subject anchor, the article body has an object sentence for **{summary['page_anchored_body_span_pairs']:,}** pairs.",
        f"- The earlier lead-only run had such a span for **{summary['lead_complete_span_pairs']:,}** pairs.",
        f"- A known structured Wikidata property resolves **{summary['resolved_by_structured_wikidata_pairs']:,}** pairs.",
        f"- **{summary['unresolved_with_checked_evidence_pairs']:,}** unresolved pairs have evidence for later classification.",
        f"- **{summary['unresolved_without_checked_evidence_pairs']:,}** unresolved pairs have no evidence in the checked sources.",
        "",
        "These groups overlap. They are evidence-availability checks, not relation",
        "labels. A direct Wikidata property resolves its own typed relation. Infobox",
        "fields, links, qualifier paths, and text still need semantic classification.",
        "The page-anchored rule treats the article QID as the subject and requires the",
        "object identity in the body sentence.",
        "",
        "## Primary availability status",
        "",
        "| Status | Pairs |",
        "|---|---:|",
        *[
            f"| `{status}` | {count:,} |"
            for status, count in sorted(summary["status_counts"].items())
        ],
        "",
        "## Common alternative Wikidata properties",
        "",
        "| Property | Label | Pairs |",
        "|---|---|---:|",
        *[
            f"| `{row['property']}` | {row['label']} | {row['pairs']:,} |"
            for row in summary["top_forward_properties"]
        ],
        "",
        "## Common matching infobox fields",
        "",
        "| Field | Pairs |",
        "|---|---:|",
        *[
            f"| `{row['field']}` | {row['pairs']:,} |"
            for row in summary["top_infobox_fields"]
        ],
        "",
        "## Common Wikidata qualifier paths",
        "",
        "| Path | Pairs |",
        "|---|---:|",
        *[
            f"| `{row['path']}` | {row['pairs']:,} |"
            for row in summary["top_qualifier_paths"]
        ],
        "",
        "## Interpretation",
        "",
        "`RELATION_NOT_OBSERVED_IN_LOCAL_SNAPSHOT` replaces any claim that a relation",
        "is missing. A direct alternative Wikidata property keeps its exact property",
        "type and is resolved. `RELATION_SEMANTICS_UNRESOLVED` means that no direct",
        "structured relation was observed. Qualifier paths, infobox fields, entity",
        "links, and text spans are candidates for later semantic classification.",
        "",
        "The classifier was not run.",
        "",
        "## Examples",
        "",
    ]
    examples = [
        row
        for row in rows
        if row["availability_status"] != "DATA_NOT_OBSERVED_IN_CHECKED_SOURCES"
    ][:8]
    for row in examples:
        evidence = (
            row["current_target_relations"]
            or row["alternative_forward_properties"]
            or row["infobox_matching_fields"]
            or row["page_anchored_evidence_text"]
            or row["full_article_object_link_anchors"]
            or row["full_article_evidence_text"]
        )
        lines.append(
            f"- **{row['subject_label']} -> {row['object_label']}**: "
            f"`{row['availability_status']}`; {evidence}"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `country_data_availability_audit/pair_audit.csv`",
            "- `country_data_availability_audit/summary.json`",
            "",
        ]
    )
    (HERE / "COUNTRY_DATA_AVAILABILITY_AUDIT_2026-10-11.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    source_rows = reference.read_csv(INPUT)
    rows, labels = audit_rows(source_rows)
    summary = make_summary(rows, labels)
    OUT.mkdir(parents=True, exist_ok=True)
    reference.write_csv(OUT / "pair_audit.csv", rows, list(rows[0]))
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_report(summary, rows)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
