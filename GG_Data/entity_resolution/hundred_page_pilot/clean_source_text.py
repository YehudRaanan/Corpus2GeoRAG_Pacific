"""Clean saved wikitext with character origins, without rendering arbitrary HTML.

Origins are Python character offsets, end-exclusive. A zero-length origin is
an inserted separator, never raw-source evidence. Unknown syntax stays literal
and requires review; no mention is relocated by searching for its text.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
import time
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import mwparserfromhell as mw
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from GG_Data.entity_resolution.hundred_page_pilot.collect_entities import utc_now, validate_revision
from GG_Data.entity_resolution.hundred_page_pilot.filter_source_content import (
    BACK,
    CITATION,
    CONTROL,
    DISPLAY_STYLES,
    EXCLUDE_ROLES,
    IMAGE_KEYS,
    LIST_TEMPLATES,
    NAVIGATION,
    NOTES,
    RELATED,
    REVIEW_ROLES,
    TEMPLATE_TEXT_GROUPS,
    normal,
    section_path,
    source_intervals,
    template_text_fields,
)
from GG_Data.entity_resolution.hundred_page_pilot.prepare_mentions import positions
from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
    PREFIXES,
    template_targets,
)
from GG_Data.entity_resolution.luke_pilot.data import sha256

LOG = logging.getLogger(__name__)
POLICY_VERSION = "source-text-v3"


@dataclass
class CleanText:
    text: str
    origins: list[tuple[int, int]]
    review_spans: list[tuple[int, int]]
    removed_spans: list[tuple[int, int]]
    source_length: int


def _intervals(spans: list[tuple[int, int]], length: int) -> list[tuple[int, int]]:
    for start, end in spans:
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= length:
            raise ValueError("Invalid end-exclusive source interval")
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def clean_text(
    text: str,
    excluded: list[tuple[int, int]] | None = None,
    uncertain: list[tuple[int, int]] | None = None,
) -> CleanText:
    """Keep supported visible values and their exact source character spans."""
    excluded = _intervals(excluded or [], len(text))
    reviews = _intervals(uncertain or [], len(text))
    hidden = bytearray(len(text))
    for start, end in excluded:
        hidden[start:end] = b"\1" * (end - start)
    chars: list[str] = []
    origins: list[tuple[int, int]] = []

    def emit(value: str, start: int, end: int | None = None) -> None:
        if end is not None:
            if any(hidden[start:end]):
                return
            chars.extend(value)
            origins.extend([(start, end)] * len(value))
        else:
            for i, char in enumerate(value, start):
                if not hidden[i]:
                    chars.append(char)
                    origins.append((i, i + 1))

    def separator(anchor: int) -> None:
        if chars and not chars[-1].isspace():
            emit("\n", anchor, anchor)

    def unknown(literal: str, start: int) -> None:
        emit(literal, start)
        reviews.append((start, start + len(literal)))

    def parameters(node: object, start: int) -> list[tuple[str, str, int]]:
        result = []
        cursor = start + 2 + len(str(node.name))
        for param in node.params:
            value = str(param.value)
            left = cursor + 1 + len(str(param)) - len(value)
            result.append((normal(param.name), value, left))
            cursor += 1 + len(str(param))
        return result

    def template(node: object, start: int) -> None:
        literal, family = str(node), normal(node.name)
        params = parameters(node, start)
        keys = [key for key, _, _ in params]
        if (
            family.startswith("cite ")
            or family in CITATION | CONTROL | NAVIGATION
            or family.startswith(("navbox", "sidebar", "defaultsort:"))
            or family.endswith("-stub")
        ):
            return
        if family in {"efn", "efn-lr", "refn", "note", "notetag"}:
            return
        if len(set(keys)) != len(keys):
            unknown(literal, start)
            return
        display: set[str] | None = None
        allowed: set[str] = set(keys)
        if family.startswith("infobox"):
            display = set(keys) - IMAGE_KEYS - DISPLAY_STYLES
            # In this ship template, class names the vessel class, not CSS styling.
            if family == "infobox ship/characteristics":
                display.add("class")
        elif family in {"nowrap", "nobr", "nobreak", "small", "big", "lang"}:
            display = {"2"} if family == "lang" else {"1"}
            allowed = {"1", "2", "3", "4", "5", "help", "lead", "extra", "extra2"}
        elif family in LIST_TEMPLATES:
            display = {key for key in keys if key.isdigit()}
            allowed = display | DISPLAY_STYLES | {"start", "type", "horizontal"}
        elif family in TEMPLATE_TEXT_GROUPS:
            selection = template_text_fields(node)
            if selection is None:
                unknown(literal, start)
                return
            display, controls = selection
            allowed = display | controls
        elif family == "font color":
            display = {"3"} if "3" in keys else {"2"}
            allowed = {"1", "2", "3"}
        if display is not None and display & set(keys) and not set(keys) - allowed:
            for key, value, left in params:
                if key in display:
                    if (
                        family.startswith("infobox")
                        or family in LIST_TEMPLATES
                        or family in TEMPLATE_TEXT_GROUPS
                    ):
                        separator(left)
                    visit(value, left)
            return
        # Reuse documented ship rules. Generated prefixes/punctuation use insertion
        # anchors; displayed parameter text retains its own literal source span.
        rules = template_targets(literal)
        rule = next(
            (r for r in rules if r["raw_start"] == 0 and r["raw_end"] == len(literal)), None
        )
        if rule and rule["template_status"] == "SUPPORTED_DOCUMENTED_SHIP_TARGET":
            values = {
                key: (value.strip(), left + len(value) - len(value.lstrip()))
                for key, value, left in params
            }

            def generated(value: str) -> tuple[str, int, int]:
                return value, start, start

            def field(key: str) -> tuple[str, int, int | None]:
                value, left = values.get(key, ("", start))
                return value, left, None

            name = field("2" if family == "ship" else "1")
            if family.startswith("sclass"):
                mode = values.get("3", ("", start))[0]
                pieces = [name]
                if mode != "5":
                    pieces.append(generated(" class" if mode == "4" else "-class"))
                if mode in {"", "0", "1", "2", "3"}:
                    pieces.extend([generated(" "), field("2")])
            else:
                prefix = field("1") if family == "ship" else generated(PREFIXES[family])
                identifier = field("3" if family == "ship" else "2")
                mode = values.get("4" if family == "ship" else "3", ("", start))[0]
                suffix = [generated(" ("), identifier, generated(")")] if identifier[0] else []
                pieces = {
                    "": [prefix, generated(" ") if prefix[0] else generated(""), name, *suffix],
                    "1": [identifier],
                    "2": [name],
                    "3": [name, *suffix],
                    "5": [
                        prefix,
                        generated(" ") if prefix[0] and identifier[0] else generated(""),
                        identifier,
                    ],
                    "6": [prefix, generated(" ") if prefix[0] else generated(""), name],
                }[mode]
            if "".join(p[0] for p in pieces) == rule["display_name"]:
                boundary = start
                for value, left, right in pieces:
                    if value and right is None:
                        if left < boundary:
                            # Reordered named parameters cannot preserve source order.
                            unknown(literal, start)
                            return
                        boundary = left + len(value)
                boundary = start
                for value, left, right in pieces:
                    if right is None:
                        emit(value, left)
                        if value:
                            boundary = left + len(value)
                    elif not any(hidden[start : start + len(literal)]):
                        emit(value, boundary, boundary)
                return
        unknown(literal, start)

    def visit(value: object, offset: int) -> None:
        cursor = offset
        code = value if isinstance(value, mw.wikicode.Wikicode) else mw.parse(str(value))
        for node in code.nodes:
            literal, kind = str(node), type(node).__name__
            end = cursor + len(literal)
            if kind == "Text":
                # The parser leaves malformed constructs as text. Keep them for review.
                malformed = re.search(
                    r"\{\{|\[\[|\}\}|\]\]|<!--|</?(?:ref|references|gallery)\b", literal, re.I
                )
                if malformed:
                    reviews.append((cursor + malformed.start(), end))
                at = 0
                for match in re.finditer(r"(?m)^[*#:;]+[ \t]*|__[A-Z_]+__", literal):
                    point = cursor + match.start()
                    if match.group().startswith("__") and match.group() not in {
                        "__TOC__",
                        "__NOTOC__",
                        "__FORCETOC__",
                        "__NOEDITSECTION__",
                    }:
                        reviews.append((point, cursor + match.end()))
                        continue
                    # A Text node can begin after an inline link/tag, mid-sentence.
                    if (
                        not match.group().startswith("__")
                        and point
                        and text[point - 1] not in "\r\n"
                    ):
                        continue
                    emit(literal[at : match.start()], cursor + at)
                    at = match.end()
                emit(literal[at:], cursor + at)
            elif kind == "HTMLEntity":
                emit(html.unescape(literal), cursor, end)
            elif kind == "Wikilink":
                title = str(node.title).strip()
                # A leading colon turns a category/file instruction into a visible link.
                if title.startswith(":") or title.split(":", 1)[0].casefold() not in {
                    "file",
                    "image",
                    "category",
                }:
                    visible = node.text if node.text is not None else node.title
                    left = cursor + 2 + (len(str(node.title)) + 1 if node.text is not None else 0)
                    if node.text is None and title.startswith(":"):
                        skip = str(visible).index(":") + 1
                        visible, left = str(visible)[skip:], left + skip
                    visit(visible, left)
            elif kind == "Template":
                template(node, cursor)
            elif kind == "Heading":
                separator(cursor)
                visit(node.title, cursor + node.level)
                separator(end)
            elif kind == "ExternalLink":
                if node.title is not None:
                    left = cursor + 1 + len(str(node.url)) + (0 if node.suppress_space else 1)
                    visit(node.title, left)
            elif kind == "Tag":
                tag = normal(node.tag)
                if tag in {"ref", "references"}:
                    pass
                elif tag in {
                    "b",
                    "i",
                    "em",
                    "strong",
                    "span",
                    "small",
                    "big",
                    "sup",
                    "sub",
                    "p",
                    "div",
                    "blockquote",
                    "poem",
                    "table",
                    "tr",
                    "td",
                    "th",
                    "li",
                    "ul",
                    "ol",
                    "br",
                    "hr",
                }:
                    blocks = {"p", "div", "blockquote", "poem", "table", "tr", "li", "ul", "ol"}
                    if tag in blocks | {"td", "th", "br", "hr"}:
                        separator(cursor)
                    if not node.self_closing:
                        if node.wiki_markup:
                            opening = (
                                len(node.wiki_markup)
                                + sum(len(str(a)) for a in node.attributes)
                                + len(node.padding or "")
                                + len(node.wiki_style_separator or "")
                            )
                        else:
                            opening = (
                                1
                                + len(str(node.tag))
                                + sum(len(str(a)) for a in node.attributes)
                                + len(node.padding or "")
                                + 1
                            )
                        contents = str(node.contents)
                        if literal[opening : opening + len(contents)] != contents:
                            raise ValueError("Parser tag source offsets do not round-trip")
                        visit(node.contents, cursor + opening)
                    if tag in blocks:
                        separator(end)
                else:
                    unknown(literal, cursor)
            elif kind != "Comment":
                unknown(literal, cursor)
            cursor = end
        if cursor != offset + len(str(value)):
            raise ValueError("Parser source offsets do not round-trip")

    visit(text, 0)
    present = bytearray(len(text))
    for start, end in origins:
        present[start:end] = b"\1" * (end - start)
    removed = [(m.start(), m.end()) for m in re.finditer(b"\0+", present)]
    return CleanText("".join(chars), origins, _intervals(reviews, len(text)), removed, len(text))


def map_mention(cleaned: CleanText, start: int, end: int) -> dict:
    """Map one original occurrence, rejecting partial or uncertain coverage."""
    if (
        type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= cleaned.source_length
    ):
        raise ValueError("Invalid end-exclusive mention offsets")
    indices = [i for i, (left, right) in enumerate(cleaned.origins) if left < end and start < right]

    def result(status: str, reason: str, left: int | None = None, right: int | None = None) -> dict:
        return dict(status=status, start=left, end=right, reason=reason)

    if not indices:
        return result("excluded", "source_span_removed")
    if any(left < end and start < right for left, right in cleaned.review_spans):
        return result("uncertain", "source_review_overlap")
    if any(left < end and start < right for left, right in cleaned.removed_spans):
        return result("uncertain", "partial_source_removal")
    if any(not start <= cleaned.origins[i][0] < cleaned.origins[i][1] <= end for i in indices):
        return result("uncertain", "partial_decoded_character")
    first, last = indices[0], indices[-1] + 1
    if indices != list(range(first, last)):
        return result("uncertain", "noncontiguous_output")
    return result("mapped", "exact_source_coverage", first, last)


def _clean_page(raw: str) -> CleanText:
    """Reuse source policy, with notes omitted in this separate cleaning pilot."""
    spans, headings = source_intervals(raw)
    # The parser removes syntax itself. Masking syntax inside an unsupported
    # construct would corrupt the raw template that we deliberately keep for review.
    syntax = {
        "parameter_key",
        "template_control",
        "hidden_link_target",
        "tag_markup",
        "image_filename",
        "image_option",
    }
    hidden = [
        (a, b)
        for a, b, role, _ in spans
        if role in set(EXCLUDE_ROLES) - syntax or role == "reference_note"
    ]
    reviews = [
        (a, b) for a, b, role, _ in spans if role in REVIEW_ROLES and role != "reference_note"
    ]
    boundaries = [h[0] for h in headings] + [len(raw)]
    for i, (start, _, _) in enumerate(headings):
        if {normal(s) for s in section_path(headings, start)} & (BACK | RELATED | NOTES):
            hidden.append((start, boundaries[i + 1]))
    return clean_text(raw, hidden, reviews)


def _passage(cleaned: CleanText, starts: list[int], left: int, right: int) -> CleanText:
    """Project the page map, retaining parser context that a cut-out line lacks."""
    first, last = bisect_left(starts, left), bisect_left(starts, right)
    if first and cleaned.origins[first - 1][1] > left:
        first = bisect_left(starts, starts[first - 1])
    chars, origins, reviews = [], [], []
    for i in range(first, last):
        a, b = cleaned.origins[i]
        # Generated separators have no raw evidence. Include only interior anchors.
        if a == b or (a < right and left < b):
            chars.append(cleaned.text[i])
            origins.append((max(a, left) - left, min(b, right) - left))
            if a < left or b > right:
                reviews.append((max(a, left) - left, min(b, right) - left))

    def clipped(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
        return [
            (max(a, left) - left, min(b, right) - left) for a, b in spans if a < right and left < b
        ]

    return CleanText(
        "".join(chars),
        origins,
        reviews + clipped(cleaned.review_spans),
        clipped(cleaned.removed_spans),
        right - left,
    )


def clean_mentions(
    mentions_path: Path, revisions_path: Path, output: Path, page_ids: set[int] | None = None
) -> dict:
    """Write a new annotated Parquet. Original rows/text/positions never move."""
    started, utc = time.monotonic(), utc_now()
    if output.exists():
        raise FileExistsError(f"Preserve existing output: {output}")
    input_hashes = {str(p): sha256(p) for p in (mentions_path, revisions_path)}
    original = pq.read_table(mentions_path)
    required = {
        "source_row_index",
        "page_id",
        "revision_id",
        "Text",
        "word",
        "start",
        "end",
        "entity_group",
    }
    if not required <= set(original.column_names):
        raise ValueError(
            f"Missing mention columns: {sorted(required - set(original.column_names))}"
        )
    if any(name.startswith("clean_") or name == "Text_clean" for name in original.column_names):
        raise ValueError("Input already contains cleaning annotations")
    if page_ids is not None:
        original = original.filter(
            pc.is_in(original["page_id"], value_set=pa.array(sorted(page_ids)))
        )
        if set(original["page_id"].to_pylist()) != page_ids:
            raise ValueError("Requested page IDs are not all present")
    rows = original.to_pylist()
    if not rows or len({r["source_row_index"] for r in rows}) != len(rows):
        raise ValueError("Nonempty input with unique source row IDs required")
    revisions_table = pq.read_table(revisions_path)
    revisions = revisions_table.to_pylist()
    by_revision = {(r["page_id"], r["revision_id"]): r for r in revisions}
    if len(by_revision) != len(revisions):
        raise ValueError("Duplicate page/revision records")
    grouped = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[row["page_id"], row["revision_id"]].append((index, row))
    annotations, words, raw_hashes, used = (
        [None] * len(rows),
        list(original["word"].to_pylist()),
        {},
        [],
    )
    passage_count = 0
    for key, local in grouped.items():
        revision = by_revision.get(key)
        if revision is None and None not in key:
            raise ValueError(f"Missing saved page/revision: {key}")
        raw = validate_revision(revision) if revision else ""
        page = _clean_page(raw) if revision else None
        starts = [a for a, _ in page.origins] if page else []
        if starts != sorted(starts):
            raise ValueError("Page origins must stay in source order")
        if revision:
            used.append(revision)
            raw_hashes[revision["wikitext_path"]] = revision["sha256"]
        cache = {}
        for index, row in local:
            text = row["Text"]
            if text not in cache:
                places = positions(raw, text) if revision and isinstance(text, str) and text else []
                source_status = (
                    "unresolved_page_version"
                    if revision is None
                    else (
                        "unique_raw_placement"
                        if len(places) == 1
                        else "nonunique_raw_placement" if places else "nonexact_raw_placement"
                    )
                )
                cleaned = (
                    _passage(page, starts, places[0], places[0] + len(text))
                    if len(places) == 1
                    else clean_text(text) if isinstance(text, str) else None
                )
                needs_review = source_status != "unique_raw_placement" or bool(
                    cleaned
                    and any(
                        a < end and start < b
                        for a, b in cleaned.review_spans
                        for start, end in cleaned.origins
                    )
                )
                cache[text] = cleaned, source_status, needs_review
                passage_count += 1
            cleaned, source_status, needs_review = cache[text]
            start, end = row["start"], row["end"]
            original_word = row.get("word_original", row["word"])
            outcome = dict(
                status="uncertain", start=None, end=None, reason="invalid_original_offsets"
            )
            if (
                isinstance(text, str)
                and type(start) is int
                and type(end) is int
                and 0 <= start < end <= len(text)
                and text[start:end] == original_word
            ):
                projected_start, projected_end = start, end
                if row.get("repair_status") == "repaired":
                    projected_start, projected_end = row.get("repaired_start"), row.get("repaired_end")
                    if not (
                        type(projected_start) is int and type(projected_end) is int
                        and 0 <= projected_start < projected_end <= len(text)
                        and text[projected_start:projected_end] == row["word"]
                    ):
                        outcome = dict(status="uncertain", start=None, end=None, reason="unmapped_repaired_source_span")
                    else:
                        outcome = map_mention(cleaned, projected_start, projected_end)
                else:
                    outcome = map_mention(cleaned, projected_start, projected_end)
                if source_status != "unique_raw_placement":
                    outcome = dict(status="uncertain", start=None, end=None, reason=source_status)
            if outcome["status"] == "mapped":
                words[index] = cleaned.text[outcome["start"] : outcome["end"]]
            annotations[index] = dict(
                Text_clean=cleaned.text if cleaned else None,
                clean_start=outcome["start"],
                clean_end=outcome["end"],
                clean_status=outcome["status"],
                clean_reason=outcome["reason"],
                clean_source_status=source_status,
                clean_policy_version=POLICY_VERSION,
                clean_text_needs_review=needs_review,
                clean_revision_sha256=revision["sha256"] if revision else None,
            )
        LOG.info("Cleaned revision %s: %s mention rows", key, len(local))
    schema = pa.schema(
        [
            ("Text_clean", pa.string()),
            ("clean_start", pa.int64()),
            ("clean_end", pa.int64()),
            ("clean_status", pa.string()),
            ("clean_reason", pa.string()),
            ("clean_source_status", pa.string()),
            ("clean_policy_version", pa.string()),
            ("clean_text_needs_review", pa.bool_()),
            ("clean_revision_sha256", pa.string()),
        ]
    )
    enriched = original
    if "word_original" not in original.column_names:
        enriched = enriched.append_column("word_original", original["word"])
    else:
        # Keep the immediate input word too if another preparation step ran first.
        if "word_before_clean" in original.column_names:
            raise ValueError("Input already contains word_before_clean")
        enriched = enriched.append_column("word_before_clean", original["word"])
    enriched = enriched.set_column(
        enriched.schema.get_field_index("word"),
        "word",
        pa.array(words, type=original.schema.field("word").type),
    )
    extra = pa.Table.from_pylist(annotations, schema=schema)
    for column in extra.column_names:
        enriched = enriched.append_column(column, extra[column])
    from GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates import (
        matching_eligibility,
        validate_source_policy,
    )

    annotated_rows = enriched.to_pylist()
    policy = validate_source_policy(annotated_rows)
    eligibility = [matching_eligibility(row, policy) for row in annotated_rows]
    for column, values, dtype in (
        ("matching_eligible", [eligible for eligible, _ in eligibility], pa.bool_()),
        ("matching_eligibility_reason", [reason for _, reason in eligibility], pa.string()),
    ):
        if column in enriched.column_names:
            raise ValueError(f"Input already contains matching annotation: {column}")
        enriched = enriched.append_column(column, pa.array(values, type=dtype))
    protected = [name for name in original.column_names if name != "word"]
    if not enriched.select(protected).equals(original.select(protected)):
        raise ValueError("Original source columns changed")
    if any(sha256(Path(path)) != digest for path, digest in {**input_hashes, **raw_hashes}.items()):
        raise ValueError("Source input changed during cleaning")
    summary = dict(
        policy_version=POLICY_VERSION,
        rows=len(rows),
        pages=len({r["page_id"] for r in rows}),
        revisions=len(used),
        distinct_passages=passage_count,
        status_counts=dict(Counter(r["clean_status"] for r in annotations)),
        reason_counts=dict(Counter(r["clean_reason"] for r in annotations)),
        source_status_counts=dict(Counter(r["clean_source_status"] for r in annotations)),
        working_word_changes=sum(
            before != after for before, after in zip(original["word"].to_pylist(), words)
        ),
        context_review_rows=sum(r["clean_text_needs_review"] for r in annotations),
        mapped_context_review_rows=sum(r["clean_status"] == "mapped" and r["clean_text_needs_review"] for r in annotations),
        matching_eligible_rows=sum(eligible for eligible, _ in eligibility),
        matching_eligibility_reason_counts=dict(Counter(reason for _, reason in eligibility)),
        original_columns_preserved_except_working_word=True,
        original_words_preserved=True,
        input_sha256=input_hashes,
        raw_revision_sha256=raw_hashes,
        code_sha256=sha256(Path(__file__)),
        started_utc=utc,
        elapsed_seconds=time.monotonic() - started,
        active_work_seconds=None,
        limitation="Local raw-source cleaning, not historical template rendering, QID matching or accuracy. Unknown syntax remains literal and uncertain.",
    )
    output.mkdir(parents=True, exist_ok=False)
    pq.write_table(enriched, output / "mentions.parquet", compression="zstd")
    pq.write_table(
        pa.Table.from_pylist(used, schema=revisions_table.schema), output / "used_revisions.parquet"
    )
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mentions", type=Path, required=True)
    parser.add_argument("--revisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-id", type=int, action="append")
    args = parser.parse_args()
    summary = clean_mentions(
        args.mentions, args.revisions, args.output, set(args.page_id) if args.page_id else None
    )
    LOG.info(
        "Cleaner result: %s", {k: summary[k] for k in ("rows", "status_counts", "elapsed_seconds")}
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
