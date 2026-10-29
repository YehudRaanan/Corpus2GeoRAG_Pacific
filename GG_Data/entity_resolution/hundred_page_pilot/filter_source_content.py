"""Classify original mention positions before matching; preserve every input row.

This is a local source filter, not an entity validator or Wikipedia renderer.
Known raw constructs have explicit rules; uncertain placements and templates
stay REVIEW. Historical QID assignments, text and offsets are never rewritten.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import mwparserfromhell as mw
import pyarrow as pa
import pyarrow.parquet as pq

from GG_Data.entity_resolution.hundred_page_pilot.collect_entities import (
    utc_now,
    validate_revision,
)
from GG_Data.entity_resolution.hundred_page_pilot.prepare_mentions import positions
from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
    PREFIXES,
    template_targets,
)
from GG_Data.entity_resolution.luke_pilot.data import sha256

LOG = logging.getLogger(__name__)
POLICY_VERSION = "article-source-v2"
SUPPORTED_POLICIES = ("article-source-v1", POLICY_VERSION)
LEGACY_POLICY = "LEGACY_UNFILTERED"
CITATION = {
    "citation",
    "sfn",
    "sfnm",
    "sfnp",
    "harv",
    "harvnb",
    "harvtxt",
    "harvcol",
    "harvcolnb",
    "harvp",
    "harvc",
}
BACK = {
    "references",
    "sources",
    "bibliography",
    "further reading",
    "works cited",
    "cited works",
    "citations",
}
RELATED = {"see also", "external links"}
NOTES = {"notes", "footnotes", "explanatory notes"}
CONTROL = {
    "authority control",
    "short description",
    "defaultsort",
    "reflist",
    "refbegin",
    "refend",
    "commons category",
    "commons",
    "wikiquote",
    "portal",
    "portal bar",
    "ribbon devices",
    "rp",
    "use dmy dates",
    "use mdy dates",
    "use british english",
    "use american english",
    "citation needed",
    "cn",
    "fact",
    "clarify",
    "clarification needed",
    "update inline",
    "update",
    "when",
    "who",
    "which",
    "dubious",
    "disputed inline",
}
NAVIGATION = {
    "main",
    "see also",
    "further",
    "australian commando units of the second world war",
    "australian commando raids of the second world war",
}
IMAGE_KEYS = {"image", "image name", "logo", "signature", "image seal"}
CAPTION_KEYS = {"caption", "image caption", "map caption", "logo caption"}
DISPLAY_STYLES = {
    "align",
    "salign",
    "width",
    "style",
    "class",
    "liststyle",
    "itemstyle",
    "indent",
    "fontsize",
    "bgcolor",
    "border",
    "padding",
    "color",
    "clear",
}
LIST_TEMPLATES = {
    "plainlist",
    "plain list",
    "hlist",
    "ubl",
    "unbulleted list",
    "bulleted list",
    "ordered list",
}
EXCLUDE_ROLES = (
    "comment",
    "category_metadata",
    "citation",
    "parameter_key",
    "image_filename",
    "image_field",
    "image_option",
    "template_control",
    "url",
    "navigation",
    "page_control",
    "hidden_link_target",
    "tag_markup",
)
REVIEW_ROLES = (
    "unparsed_markup",
    "protected_text",
    "unknown_template",
    "reference_note",
    "template_name",
    "gallery_review",
    "coordinates",
    "image_field_review",
    "media_review",
)
KEEP_ROLES = (
    "caption",
    "display_value",
    "infobox",
    "article_table",
    "article_list",
    "quotation",
    "heading",
)
BOUNDARY_ROLES = (
    "display_template",
    "display_value",
    "infobox",
    "caption",
    "link_construct",
    "gallery_construct",
)


def normal(value: object) -> str:
    return " ".join(str(value).replace("_", " ").split()).casefold()


def citation_only_ref(contents: object) -> bool:
    """Match a complete short citation, never author/year inside explanatory prose."""
    text = " ".join(str(contents).replace("''", "").split())
    return (
        re.fullmatch(
            r"[A-ZÀ-ÖØ-Þ][\w’'.-]*(?:\s+(?:[A-ZÀ-ÖØ-Þ][\w’'.-]*|&|and|et|al\.?))*"
            r"(?:\s*(?:\((?:18|19|20)\d{2}[a-z]?\)|(?:18|19|20)\d{2}[a-z]?),?\s*|\s*,\s*)(?:pp?\.|pages?)\s*"
            r"[0-9ivxlcdm]+(?:\s*[-–—,]\s*[0-9ivxlcdm]+)*\.?",
            text,
        )
        is not None
    )


def source_intervals(raw: str) -> tuple[list[tuple], list[tuple]]:
    """Map parser nodes to literal source ranges, including nested exceptions."""
    code = mw.parse(raw)
    ship_rules = {(r["raw_start"], r["raw_end"]): r for r in template_targets(raw)}
    spans, headings = [], []

    def add(left: int, right: int, role: str, detail: str = "") -> None:
        if right > left:
            spans.append((left, right, role, detail))

    def gallery_filename(value: str) -> bool:
        return (
            re.fullmatch(
                r"(?is)\s*(?:(?:file|image):)?[^|\n{}<>]+\.(?:jpe?g|png|svg|gif|webp|tiff?)\s*",
                value,
            )
            is not None
        )

    def check_unparsed(wikicode: object, offset: int) -> None:
        # Unclosed constructs become Text nodes; never treat their contents as prose.
        for child in wikicode.nodes:
            literal = str(child)
            if type(child).__name__ == "Text":
                match = re.search(
                    r"\{\{|\[\[|\}\}|\]\]|<!--|</?(?:ref|references|gallery)\b",
                    literal,
                    re.I,
                )
                if match:
                    add(
                        offset + match.start(), offset + len(literal), "unparsed_markup"
                    )
            offset += len(literal)

    check_unparsed(code, 0)

    cursor = 0
    for node in code.nodes:
        if type(node).__name__ == "Heading":
            headings.append((cursor, node.level, str(node.title).strip()))
        cursor += len(str(node))
    if cursor != len(raw):
        raise ValueError("Parser did not preserve raw source positions")

    for kind, nodes in [
        ("template", code.filter_templates()),
        ("tag", code.filter_tags()),
        ("link", code.filter_wikilinks()),
        ("external", code.filter_external_links()),
        ("comment", code.filter_comments()),
        ("heading", code.filter_headings()),
    ]:
        seen = set()
        for node in nodes:
            literal = str(node)
            if literal in seen:
                continue
            seen.add(literal)
            for start in positions(raw, literal):
                end = start + len(literal)
                if kind in {"comment", "heading"}:
                    add(start, end, kind)
                elif kind == "template":
                    family = normal(node.name)
                    if family.startswith("cite ") or family in CITATION:
                        role = "citation"
                    elif family in {"london gazette", "csr"} and all(
                        normal(p.name)
                        in (
                            {"issue", "date", "page", "pages", "supp"}
                            if family == "london gazette"
                            else {"register", "id", "shipname", "access-date"}
                        )
                        or not str(p.value).strip()
                        for p in node.params
                    ):
                        role = "citation"
                    elif family.startswith("infobox"):
                        role = "infobox"
                    elif (
                        family in CONTROL
                        or family.endswith("-stub")
                        or family.startswith("defaultsort:")
                    ):
                        role = "page_control"
                    elif family in NAVIGATION or family.startswith(
                        ("navbox", "sidebar")
                    ):
                        role = "navigation"
                    elif family in {"efn", "efn-lr", "refn", "note", "notetag"}:
                        role = "reference_note"
                    elif family == "coord":
                        role = "coordinates"
                    else:
                        role = "unknown_template"
                    # For supported helpers, only specified display parameters are eligible.
                    display = set()
                    controls = set()
                    if family in {"ship", "sclass", "sclass2"} | set(PREFIXES):
                        rule = ship_rules.get((start, end), {})
                        if (
                            rule.get("template_status")
                            == "SUPPORTED_DOCUMENTED_SHIP_TARGET"
                        ):
                            params = {
                                str(p.name).strip(): str(p.value).strip()
                                for p in node.params
                            }
                            if family.startswith("sclass"):
                                display = (
                                    {"1"}
                                    if params.get("3") in {"4", "5"}
                                    else {"1", "2"}
                                )
                            else:
                                prefix = {"1"} if family == "ship" else set()
                                name = {"2" if family == "ship" else "1"}
                                identifier = {"3" if family == "ship" else "2"}
                                mode = params.get("4" if family == "ship" else "3", "")
                                display = {
                                    "": prefix | name | identifier,
                                    "1": identifier,
                                    "2": name,
                                    "3": name | identifier,
                                    "5": prefix | identifier,
                                    "6": prefix | name,
                                }[mode]
                            controls = set(params) - display
                    elif family in {
                        "nowrap",
                        "nobr",
                        "nobreak",
                        "small",
                        "big",
                        "lang",
                        "nihongo",
                        "nihongo2",
                    }:
                        display = {"2"} if family == "lang" else {"1"}
                        controls = {"1"} if family == "lang" else set()
                    elif family in {"blockquote", "quote", "quotation", "cquote"}:
                        display = {"1", "text"}
                    elif family == "quote box":
                        display, controls = {"quote"}, DISPLAY_STYLES
                    elif family in LIST_TEMPLATES:
                        display = (
                            {"1"}
                            if family in {"plainlist", "plain list"}
                            else {
                                normal(p.name)
                                for p in node.params
                                if str(p.name).strip().isdigit()
                            }
                        )
                        controls = DISPLAY_STYLES | {"start", "type", "horizontal"}
                    elif family == "font color" and node.has("2"):
                        display = {"3"} if node.has("3") else {"2"}
                        controls = {"1", "2"} - display
                    elif family == "gallery":
                        positional = [
                            p for p in node.params if str(p.name).strip().isdigit()
                        ]
                        if (
                            positional
                            and len(positional) % 2 == 0
                            and all(
                                str(p.name).strip() == str(i + 1)
                                and (i % 2 or gallery_filename(str(p.value)))
                                for i, p in enumerate(positional)
                            )
                        ):
                            display = {str(p.name).strip() for p in positional[1::2]}
                            controls = (
                                {str(p.name).strip() for p in positional[::2]}
                                | DISPLAY_STYLES
                                | {"noborder", "mode", "height", "whitebg"}
                            )
                    elif family == "multiple image":
                        display = {
                            normal(p.name)
                            for p in node.params
                            if re.fullmatch(r"caption\d*|footer|header", normal(p.name))
                        }
                        controls = DISPLAY_STYLES | {
                            normal(p.name)
                            for p in node.params
                            if re.fullmatch(
                                r"(?:image|alt|width|height|link)\d*|direction|total width|perrow|image gap|caption align|footer align|header align",
                                normal(p.name),
                            )
                        }
                    elif family in {"flag", "flagcountry"}:
                        display = {"name"} if node.has("name") else {"1"}
                        controls = {"2", "size", "image", "variant"} | (
                            {"1"} if node.has("name") else set()
                        )
                    elif family in {"flagicon", "flagicon image", "usn flag"}:
                        role = "page_control"
                    if display:
                        role = "display_template"
                        keys = [normal(p.name) for p in node.params]
                        if len(keys) != len(set(keys)):
                            display, role = set(), "unknown_template"
                    add(start, end, role, family)
                    add(
                        start + 2,
                        start + 2 + len(str(node.name)),
                        "template_name",
                        family,
                    )
                    cursor = start + 2 + len(str(node.name))
                    for parameter in node.params:
                        value = str(parameter.value)
                        left = cursor + 1 + len(str(parameter)) - len(value)
                        right = left + len(value)
                        if raw[left:right] != value:
                            raise ValueError("Template parameter offset mismatch")
                        key = normal(parameter.name)
                        check_unparsed(parameter.value, left)
                        if parameter.showkey:
                            add(cursor + 1, left - 1, "parameter_key", key)
                        if display:
                            add(
                                left,
                                right,
                                (
                                    "display_value"
                                    if key in display
                                    else (
                                        "template_control"
                                        if key in controls
                                        else "unknown_template"
                                    )
                                ),
                                family + " / " + key,
                            )
                        if family.startswith("infobox") and (
                            key in IMAGE_KEYS
                            or key.startswith("image ")
                            and key not in CAPTION_KEYS
                            or key.endswith(" image")
                        ):
                            plain = (
                                "[[" not in value
                                and "{{" not in value
                                and re.search(
                                    r"\.(?:jpe?g|png|svg|gif|webp|tiff?|pdf)\b",
                                    value,
                                    re.I,
                                )
                            )
                            add(
                                left,
                                right,
                                "image_field" if plain else "image_field_review",
                                key,
                            )
                        if family.startswith("infobox") and key in CAPTION_KEYS:
                            add(left, right, "caption", key)
                        cursor += 1 + len(str(parameter))
                elif kind == "tag":
                    tag = normal(node.tag)
                    if (
                        node.contents is not None
                        and not node.wiki_markup
                        and tag != "gallery"
                    ):
                        content_start = literal.find(">") + 1
                        check_unparsed(node.contents, start + content_start)
                    if not node.wiki_markup and literal.startswith("<"):
                        # Tag attributes and closing tags are syntax, not displayed names.
                        add(start, start + literal.find(">") + 1, "tag_markup", tag)
                        closing = literal.rfind("</")
                        if closing >= 0:
                            add(start + closing, end, "tag_markup", tag)
                    role = {
                        "ref": "reference_note",
                        "references": "reference_note",
                        "table": "article_table",
                        "tr": "article_table",
                        "td": "article_table",
                        "th": "article_table",
                        "li": "article_list",
                        "ul": "article_list",
                        "ol": "article_list",
                        "blockquote": "quotation",
                        "gallery": "gallery_review",
                        "nowiki": "protected_text",
                        "pre": "protected_text",
                        "source": "protected_text",
                        "syntaxhighlight": "protected_text",
                        "math": "protected_text",
                    }.get(tag)
                    if tag == "gallery" and node.contents is not None:
                        # Gallery contents are opaque to the outer parser. Parse each
                        # supported caption locally and rebase every nested source range.
                        role = "gallery_construct"
                        line_start = start + literal.find(">") + 1
                        for line in str(node.contents).splitlines(keepends=True):
                            body = line.rstrip("\r\n")
                            filename, separator, caption = body.partition("|")
                            if not body.strip():
                                pass
                            elif gallery_filename(filename):
                                add(
                                    line_start,
                                    line_start + len(filename),
                                    "image_filename",
                                    filename.strip(),
                                )
                                if separator and caption:
                                    caption_start = line_start + len(filename) + 1
                                    fields = (
                                        mw.parse("{{media|" + caption + "}}")
                                        .filter_templates(recursive=False)[0]
                                        .params
                                    )
                                    add(
                                        caption_start,
                                        caption_start + len(caption),
                                        (
                                            "gallery_review"
                                            if len(fields) != 1
                                            else (
                                                "image_option"
                                                if re.match(
                                                    r"(?is)\s*(?:alt|link)\s*=", caption
                                                )
                                                else "caption"
                                            )
                                        ),
                                    )
                                    nested, _ = source_intervals(caption)
                                    for a, b, nested_role, detail in nested:
                                        add(
                                            caption_start + a,
                                            caption_start + b,
                                            nested_role,
                                            detail,
                                        )
                            else:
                                add(
                                    line_start, line_start + len(body), "gallery_review"
                                )
                            line_start += len(line)
                    if tag == "ref" and citation_only_ref(node.contents):
                        role = "citation"
                    if role:
                        add(start, end, role, tag)
                elif kind == "link":
                    add(start, end, "link_construct")
                    title = str(node.title).strip()
                    prefix = title.split(":", 1)[0].casefold()
                    if prefix == "category":
                        add(start, end, "category_metadata", title)
                    elif prefix in {"file", "image"}:
                        add(
                            start + 2,
                            start + 2 + len(str(node.title)),
                            "image_filename",
                            title,
                        )
                        if node.text is not None:
                            # Parse top-level pipe fields without splitting nested caption links.
                            fields = (
                                mw.parse("{{media|" + str(node.text) + "}}")
                                .filter_templates(recursive=False)[0]
                                .params
                            )
                            left = start + 3 + len(str(node.title))
                            framed = any(
                                str(p).strip().casefold()
                                in {"thumb", "thumbnail", "frame"}
                                for p in fields
                            )
                            visible_fields = []
                            for field in fields:
                                value = str(field)
                                option = re.fullmatch(
                                    r"(?is)(?:thumb(?:nail)?(?:=.*)?|frame(?:less)?|border|left|right|center|none|baseline|sub|super|top|text-top|middle|bottom|text-bottom|\d*(?:x\d+)?px|upright(?:=.*)?|(?:alt|link|page|class|lang)\s*=.*)",
                                    value.strip(),
                                )
                                add(
                                    left,
                                    left + len(value),
                                    "image_option" if option else "media_review",
                                    title,
                                )
                                if not option:
                                    visible_fields.append((left, left + len(value)))
                                left += len(value) + 1
                            # Image options may follow the caption. Require one visible field.
                            if framed and len(visible_fields) == 1:
                                caption_left, caption_right = visible_fields[0]
                                spans.remove(
                                    (caption_left, caption_right, "media_review", title)
                                )
                                add(caption_left, caption_right, "caption", title)
                    elif node.text is not None:
                        add(
                            start + 2,
                            start + 2 + len(str(node.title)),
                            "hidden_link_target",
                            title,
                        )
                elif kind == "external":
                    url = str(node.url)
                    left = start + literal.find(url)
                    add(left, left + len(url), "url", url[:120])
    return sorted(set(spans)), headings


def section_path(headings: list[tuple], point: int) -> list[str]:
    stack = []
    for start, level, title in headings:
        if start > point:
            break
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
    return [title for _, title in stack]


def classify_span(
    left: int, right: int, spans: list[tuple], headings: list[tuple]
) -> dict:
    evidence = [s for s in spans if s[0] <= left < right <= s[1]]
    roles = {s[2] for s in evidence}
    sections = section_path(headings, left)
    names = {normal(s) for s in sections}
    status, reason = "KEEP", "article_text"
    for role in EXCLUDE_ROLES:
        if role in roles:
            status, reason = "EXCLUDE", role
            break
    else:
        if names & BACK:
            status, reason = "EXCLUDE", "bibliographic_section"
        elif names & RELATED:
            status, reason = "EXCLUDE", "related_or_external_link_section"
        elif any(
            s[0] < right and left < s[1] and not (s[0] <= left < right <= s[1])
            for s in spans
            if s[2] in EXCLUDE_ROLES + REVIEW_ROLES + BOUNDARY_ROLES
        ):
            status, reason = "REVIEW", "partial_source_overlap"
        else:
            for role in REVIEW_ROLES:
                if role in roles:
                    status, reason = "REVIEW", role
                    break
            else:
                if names & NOTES:
                    status, reason = "REVIEW", "notes_section"
                else:
                    reason = next(
                        (role for role in KEEP_ROLES if role in roles), reason
                    )
    return dict(
        status=status,
        reason=reason,
        roles=sorted(roles),
        sections=sections,
        evidence=evidence,
    )


def source_policy(rows: list[dict], requested: str | None = None) -> str:
    """Reject partial/unknown policy annotations rather than silently bypassing them."""
    annotated = [any(k.startswith("source_scope_") for k in row) for row in rows]
    if any(annotated):
        policies = {row.get("source_scope_policy_version") for row in rows}
        if (
            not all(annotated)
            or len(policies) != 1
            or any(
                row.get("source_scope_policy_version") not in SUPPORTED_POLICIES
                or row.get("source_scope_status") not in {"KEEP", "EXCLUDE", "REVIEW"}
                or not isinstance(row.get("source_scope_context"), str)
                for row in rows
            )
        ):
            raise ValueError("Invalid or mixed source-scope annotations")
        policy = next(iter(policies))
    else:
        policy = LEGACY_POLICY
    if requested is not None and requested != policy:
        raise ValueError("Requested source policy does not match mention annotations")
    return policy


def is_eligible(row: dict, policy: str) -> bool:
    return policy == LEGACY_POLICY or row["source_scope_status"] == "KEEP"


def masked_source(raw: str, spans: list[tuple], headings: list[tuple]) -> str:
    """Remove excluded and uncertain constructs from future model contexts only."""
    hidden = [
        (left, right)
        for left, right, role, _ in spans
        if role in EXCLUDE_ROLES + REVIEW_ROLES
    ]
    boundaries = [h[0] for h in headings] + [len(raw)]
    for i, (start, _, _) in enumerate(headings):
        if {normal(s) for s in section_path(headings, start)} & (
            BACK | RELATED | NOTES
        ):
            hidden.append((start, boundaries[i + 1]))
    chars = list(raw)
    for left, right in hidden:
        chars[left:right] = [" "] * (right - left)
    return "".join(chars)


def filter_mentions(mentions_path: Path, revisions_path: Path, output: Path) -> dict:
    started, utc = time.monotonic(), utc_now()
    if output.exists():
        raise FileExistsError(f"Preserve existing output: {output}")
    input_hashes = {
        str(p): sha256(p) for p in (mentions_path, revisions_path) if p.exists()
    }
    original = pq.read_table(mentions_path)
    if not original.num_rows:
        raise ValueError("Source filtering requires non-empty mentions")
    required = {
        "source_row_index",
        "page_id",
        "revision_id",
        "word",
        "entity_group",
        "Text",
        "start",
        "end",
    }
    if not required <= set(original.column_names):
        raise ValueError(
            f"Missing mention columns: {sorted(required - set(original.column_names))}"
        )
    if any(name.startswith("source_scope_") for name in original.column_names):
        raise ValueError("Mentions already have source-scope annotations")
    rows = original.to_pylist()
    if len({r["source_row_index"] for r in rows}) != len(rows):
        raise ValueError("Duplicate source row indices")
    revisions = pq.read_table(revisions_path).to_pylist()
    by_revision = {(r["page_id"], r["revision_id"]): r for r in revisions}
    if len(by_revision) != len(revisions):
        raise ValueError("Duplicate page/revision records")
    grouped = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[row.get("page_id"), row.get("revision_id")].append((index, row))
    results = [None] * len(rows)
    raw_hashes = {}
    for key, local in grouped.items():
        revision = by_revision.get(key)
        if revision is None and None not in key:
            raise ValueError(f"Missing saved page/revision: {key}")
        raw = validate_revision(revision) if revision else ""
        spans, headings = source_intervals(raw)
        masked = masked_source(raw, spans, headings)
        if revision:
            raw_hashes[revision["wikitext_path"]] = revision["sha256"]
        cache = {}
        for index, row in local:
            text = row.get("Text") or ""
            word = row.get("word_original", row["word"])
            start, end = row.get("start"), row.get("end")
            left = right = None
            result = dict(
                status="REVIEW",
                reason="nonunique_or_nonexact_raw_placement",
                roles=[],
                sections=[],
                evidence=[],
            )
            if (
                type(start) is not int
                or type(end) is not int
                or not (0 <= start < end <= len(text))
                or text[start:end] != word
            ):
                result["reason"] = "invalid_original_offsets"
            elif revision is None:
                result["reason"] = "unresolved_page_version"
            else:
                if text not in cache:
                    cache[text] = positions(raw, text)
                places = cache[text]
                if len(places) == 1:
                    left, right = places[0] + start, places[0] + end
                    result = classify_span(left, right, spans, headings)
            results[index] = {
                "source_scope_status": result["status"],
                "source_scope_reason": result["reason"],
                "source_scope_policy_version": POLICY_VERSION,
                "source_scope_raw_start": left,
                "source_scope_raw_end": right,
                "source_scope_roles": result["roles"],
                "source_scope_sections": result["sections"],
                "source_scope_evidence_json": json.dumps(
                    result["evidence"], ensure_ascii=False
                ),
                "source_scope_revision_sha256": (
                    revision["sha256"] if revision else None
                ),
                "source_scope_context": (
                    " ".join(masked[max(0, left - 160) : right + 160].split())
                    if result["status"] == "KEEP"
                    else ""
                ),
            }
        LOG.info("Classified revision %s (%s rows)", key, len(local))
    schema = pa.schema(
        [
            ("source_scope_status", pa.string()),
            ("source_scope_reason", pa.string()),
            ("source_scope_policy_version", pa.string()),
            ("source_scope_raw_start", pa.int64()),
            ("source_scope_raw_end", pa.int64()),
            ("source_scope_roles", pa.list_(pa.string())),
            ("source_scope_sections", pa.list_(pa.string())),
            ("source_scope_evidence_json", pa.string()),
            ("source_scope_revision_sha256", pa.string()),
            ("source_scope_context", pa.string()),
        ]
    )
    annotations = pa.Table.from_pylist(results, schema=schema)
    enriched = original
    for column in annotations.column_names:
        enriched = enriched.append_column(column, annotations[column])
    if not enriched.select(original.column_names).equals(original):
        raise ValueError("Original source columns changed")
    source_policy(enriched.to_pylist(), POLICY_VERSION)
    if any(
        sha256(Path(path)) != digest
        for path, digest in {**input_hashes, **raw_hashes}.items()
    ):
        raise ValueError("Source input changed during filtering")
    summary = dict(
        policy_version=POLICY_VERSION,
        rows=len(rows),
        pages=len({r.get("page_id") for r in rows if r.get("page_id") is not None}),
        revisions=len(raw_hashes),
        status_counts=dict(Counter(r["source_scope_status"] for r in results)),
        reason_counts=dict(Counter(r["source_scope_reason"] for r in results)),
        original_columns_preserved=True,
        input_sha256=input_hashes,
        filter_code_sha256=sha256(Path(__file__)),
        raw_revision_sha256=raw_hashes,
        started_utc=utc,
        elapsed_seconds=time.monotonic() - started,
        active_work_seconds=None,
        limitation="Raw-source rules, not historical template rendering or entity-match accuracy. Unknown constructs remain REVIEW.",
    )
    output.mkdir(parents=True, exist_ok=False)
    pq.write_table(enriched, output / "mentions.parquet", compression="zstd")
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mentions", required=True, type=Path)
    parser.add_argument("--revisions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    summary = filter_mentions(args.mentions, args.revisions, args.output)
    LOG.info(
        "Source filter: %s",
        {k: summary[k] for k in ("rows", "status_counts", "elapsed_seconds")},
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
