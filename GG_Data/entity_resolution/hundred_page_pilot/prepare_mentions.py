"""Prepare source-backed names without changing Daniel rows or original offsets.

Only unique exact raw passage placements are used. QID labels/aliases provide
candidate evidence, never identity assignments or automatic exact-match proof.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import mwparserfromhell
import pyarrow as pa
import pyarrow.parquet as pq

from GG_Data.entity_resolution.attach_source_page_ids import (
    normalize,
    save_json,
    sha256,
)
from GG_Data.entity_resolution.hundred_page_pilot.collect_entities import (
    PROTECTED,
    raw_links,
    utc_now,
    validate_revision,
    write_table,
)
from GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids import (
    template_targets,
)

LOG = logging.getLogger(__name__)
NAME_FIELDS = {
    "name",
    "unit_name",
    "official_name",
    "ship_name",
    "birth_name",
    "full_name",
}
SPAN_SCHEMA = pa.schema(
    [
        ("occurrence_id", pa.string()),
        ("page_id", pa.int64()),
        ("revision_id", pa.int64()),
        ("passage_id", pa.string()),
        ("surface", pa.string()),
        ("method", pa.string()),
        ("source_role", pa.string()),
        ("qid", pa.string()),
        ("qid_guided", pa.bool_()),
        ("start", pa.int64()),
        ("end", pa.int64()),
        ("raw_start", pa.int64()),
        ("raw_end", pa.int64()),
        ("raw_text", pa.string()),
        ("target_title", pa.string()),
        ("support_spans_json", pa.string()),
        ("source_row_indices", pa.list_(pa.int64())),
        ("surface_is_literal", pa.bool_()),
        ("requires_review", pa.bool_()),
        ("context_review", pa.bool_()),
        ("source_rule", pa.string()),
        ("documented_display_name", pa.string()),
    ]
)
BRIDGE_SCHEMA = pa.schema(
    [
        ("source_row_index", pa.int64()),
        ("occurrence_id", pa.string()),
        ("page_id", pa.int64()),
        ("revision_id", pa.int64()),
        ("passage_id", pa.string()),
        ("surface", pa.string()),
        ("qid", pa.string()),
        ("method", pa.string()),
    ]
)


def positions(text: str, fragment: str) -> list[int]:
    """Keep every literal placement, including overlapping copies."""
    if not fragment:
        return []
    result, start = [], 0
    while (start := text.find(fragment, start)) >= 0:
        result.append(start)
        start += 1
    return result


def name_parts(code: Any, offset: int = 0) -> list[tuple[str, int, int]] | None:
    """Keep visible parser nodes and exact source coordinates, excluding syntax."""
    parts = []
    cursor = offset
    for node in mwparserfromhell.parse(str(code)).nodes:
        literal, kind = str(node), type(node).__name__
        if kind in {"Text", "HTMLEntity"}:
            parts.append((html.unescape(literal), cursor, cursor + len(literal)))
        elif kind == "Wikilink":
            value = node.text if node.text is not None else node.title
            start = (
                cursor + 2 + (len(str(node.title)) + 1 if node.text is not None else 0)
            )
            children = name_parts(value, start)
            if children is None:
                return None
            parts.extend(children)
        elif kind == "Template":
            name = str(node.name).strip().lower().replace("_", " ")
            parameter = "2" if name == "lang" else "1"
            if name not in {
                "nowrap",
                "nobr",
                "nobreak",
                "lang",
                "nihongo",
                "nihongo2",
            } or not node.has(parameter):
                return None
            matching = [p for p in node.params if str(p.name).strip() == parameter]
            if len(matching) != 1:
                return None
            start = cursor + 2 + len(str(node.name))
            for param in node.params:
                if param is matching[0]:
                    start += 1 + len(str(param)) - len(str(param.value))
                    break
                start += 1 + len(str(param))
            children = name_parts(matching[0].value, start)
            if children is None:
                return None
            parts.extend(children)
        elif kind != "Comment":
            return None
        cursor += len(literal)
    return parts


def readable_name(code: Any) -> str | None:
    """Render only literal text, links and known name-formatting wrappers."""
    parts = name_parts(code)
    if parts is None:
        return None
    value = " ".join(re.sub(r"'{2,5}", "", "".join(p[0] for p in parts)).split())
    if (
        not value
        or len(value) > 300
        or any(mark in value for mark in ("{{", "}}", "[[", "]]", "|", ";", "\u2022"))
    ):
        return None
    return value


def prose_mask(raw: str) -> str:
    """Keep literal article prose coordinates; hide templates and link targets."""
    visible = [" "] * len(raw)

    def visit(code: Any, offset: int) -> None:
        cursor = offset
        for node in mwparserfromhell.parse(str(code)).nodes:
            literal, kind = str(node), type(node).__name__
            if kind in {"Text", "HTMLEntity"}:
                visible[cursor : cursor + len(literal)] = literal
            elif kind == "Wikilink":
                # Non-article namespaces contain files/categories, not prose names.
                title = str(node.title).strip().lstrip(":")
                if ":" not in title:
                    value = node.text if node.text is not None else node.title
                    start = (
                        cursor
                        + 2
                        + (len(str(node.title)) + 1 if node.text is not None else 0)
                    )
                    visit(value, start)
            elif kind == "Tag" and str(node.tag).lower() in {
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
            }:
                # Only inline/prose wrappers are visible. References and code stay hidden.
                opening = (
                    len(node.wiki_markup)
                    if node.wiki_markup is not None
                    else literal.find(">") + 1
                )
                contents = str(node.contents)
                if opening and literal[opening : opening + len(contents)] == contents:
                    visit(node.contents, cursor + opening)
            cursor += len(literal)

    visit(raw, 0)
    return "".join(visible)


def cuts_lexical_token(row: dict, occurrence: dict) -> bool:
    """An ordinary source name can expand only an already cut word token."""
    text = row["Text"]
    left, right = row["start"], row["end"]
    return (
        occurrence["start"] < left
        and (text[left - 1].isalnum() or text[left - 1] == "-")
    ) or (right < occurrence["end"] and (text[right].isalnum() or text[right] == "-"))


def local_name_fields(raw: str) -> list[dict]:
    """Read supported name fields with parser-preserved parameter positions."""
    protected = [(m.start(), m.end()) for m in PROTECTED.finditer(raw)]
    result = []
    # Parser nodes round-trip to source bytes. Repeated nodes are all retained;
    # unique passage placement is checked separately before any repair.
    seen = set()
    for template in mwparserfromhell.parse(raw).filter_templates(recursive=True):
        rendered = str(template)
        if rendered in seen:
            continue
        seen.add(rendered)
        family = str(template.name).strip().lower().replace("_", " ")
        if not (
            family.startswith("infobox")
            or family.startswith("cite ")
            or family in {"citation", "nihongo", "nihongo2"}
        ):
            continue
        for base in positions(raw, rendered):
            if any(start <= base < end for start, end in protected):
                continue
            parameters = {}
            cursor = base + 2 + len(str(template.name))
            for parameter in template.params:
                value = str(parameter.value)
                start = cursor + 1 + len(str(parameter)) - len(value)
                end = start + len(value)
                if raw[start:end] != value:
                    raise ValueError("Parser parameter offsets do not round-trip")
                # Duplicate named parameters are ambiguous; never silently choose.
                key = str(parameter.name).strip().lower()
                parameters.setdefault(key, []).append((value, start, end))
                cursor += 1 + len(str(parameter))

            def add(surface, spans, role):
                if not surface:
                    return
                visible = []
                for start, end in spans:
                    parts = name_parts(raw[start:end], start)
                    if parts is None:
                        return
                    visible.extend((s, e) for value, s, e in parts if value.strip())
                if not visible:
                    return
                spans = visible
                result.append(
                    dict(
                        surface=surface,
                        spans=spans,
                        raw_start=min(s for s, _ in spans),
                        raw_end=max(e for _, e in spans),
                        method=role,
                        source_role=role,
                        qid=None,
                        qid_guided=False,
                        target_title=None,
                    )
                )

            if family in {"nihongo", "nihongo2"}:
                if len(parameters.get("1", [])) == 1:
                    value, start, end = parameters["1"][0]
                    add(readable_name(value), [(start, end)], "nihongo_name")
            elif family.startswith("infobox"):
                for key in NAME_FIELDS:
                    if len(parameters.get(key, [])) == 1:
                        value, start, end = parameters[key][0]
                        add(readable_name(value), [(start, end)], "infobox_name_field")
            else:
                for key, values in parameters.items():
                    match = re.fullmatch(r"last(\d*)", key)
                    if not match or len(values) != 1:
                        continue
                    firsts = parameters.get("first" + match[1], [])
                    if len(firsts) != 1:
                        continue
                    last, ls, le = values[0]
                    first, fs, fe = firsts[0]
                    first_name, last_name = readable_name(first), readable_name(last)
                    if first_name and last_name:
                        add(
                            f"{first_name} {last_name}",
                            [(fs, fe), (ls, le)],
                            "citation_author_fields",
                        )
    return result


def source_occurrences(
    raw: str, entities: list[dict], evidence: list[dict]
) -> list[dict]:
    """Collect independent source surfaces; never select shortest or longest."""
    result = local_name_fields(raw)
    masked = prose_mask(raw)
    by_location = defaultdict(list)
    for row in evidence:
        start, end = row.get("raw_start"), row.get("raw_end")
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or not 0 <= start < end <= len(raw)
        ):
            raise ValueError("Source target evidence has invalid raw offsets")
        if row.get("raw_text") is not None and raw[start:end] != row["raw_text"]:
            raise ValueError("Source target evidence raw text does not match revision")
        by_location[start, end, row.get("target_title")].append(row)
    for target in [*raw_links(raw), *template_targets(raw)]:
        evidence_rows = by_location[
            target["raw_start"], target["raw_end"], target.get("target_title")
        ]
        qids = {
            r["qid"]
            for r in evidence_rows
            if r.get("qid") and "REVIEW" not in str(r.get("recovery_status", ""))
        }
        requires_review = any(
            "REVIEW" in str(r.get("recovery_status", ""))
            or "REVIEW" in str(r.get("qid_status", ""))
            for r in evidence_rows
        )
        if target["link_origin"] == "RAW_DIRECT_LINK":
            start, end = target["anchor_start"], target["anchor_end"]
            surface = readable_name(target["anchor_text"])
            role = "ordinary_link_anchor"
            if masked[start:end] != raw[start:end]:
                # An exact visible link inside a verified name field can still
                # supply its QID, under that field's separate source role.
                fields = [
                    field
                    for field in result
                    if field["surface"] == surface
                    and any(s <= start < end <= e for s, e in field["spans"])
                ]
                for field in fields:
                    for qid in sorted(qids) or [None]:
                        result.append(
                            {**field, "qid": qid, "requires_review": requires_review}
                        )
                continue
        else:
            start, end = target.get("name_start"), target.get("name_end")
            surface = target.get("target_title")
            role = "documented_template_target"
            if start is None or end is None:
                # The legacy Ship helper has no proven name-field coordinates.
                continue
        if not surface or not target.get("target_title"):
            continue
        for qid in sorted(qids) or [None]:
            result.append(
                dict(
                    surface=surface,
                    spans=[(start, end)],
                    raw_start=start,
                    raw_end=end,
                    qid=qid,
                    qid_guided=False,
                    method=role,
                    source_role=role,
                    target_title=target.get("target_title"),
                    requires_review=requires_review,
                    source_rule=target.get("target_rule"),
                    documented_display_name=target.get("display_name"),
                )
            )
    for entity in entities:
        if not entity.get("qid"):
            continue
        names = {entity.get("label"), *(entity.get("aliases") or [])} - {None, ""}
        for name in sorted(names):
            for match in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", masked):
                before = re.search(r"([^\W\d]\w*)[ \t]+$", masked[: match.start()])
                after = re.match(r"[ \t]+([^\W\d]\w*)", masked[match.end() :])
                context_review = any(m and m[1][0].isupper() for m in (before, after))
                result.append(
                    dict(
                        context_review=context_review,
                        surface=name,
                        spans=[match.span()],
                        raw_start=match.start(),
                        raw_end=match.end(),
                        qid=entity["qid"],
                        qid_guided=True,
                        method="qid_label_or_alias_occurrence",
                        source_role="same_revision_inventory_name",
                        target_title=None,
                    )
                )
    # Remove only identical evidence, preserving distinct methods and QIDs.
    unique = {}
    for row in result:
        key = (row["surface"], tuple(row["spans"]), row["qid"], row["method"])
        row.setdefault("context_review", False)
        row.setdefault("requires_review", False)
        row.setdefault("source_rule", None)
        row.setdefault("documented_display_name", None)
        unique[key] = row
    return sorted(
        unique.values(),
        key=lambda r: (
            r["raw_start"],
            r["raw_end"],
            r["surface"],
            r["method"],
            r["qid"] or "",
        ),
    )


def prepare(
    mentions_path: Path,
    revisions_path: Path,
    entities_path: Path,
    evidence_path: Path | None,
    output: Path,
) -> dict:
    """Write row-preserving corrected mentions, recovered spans and their bridge."""
    started = time.monotonic()
    inputs = [mentions_path, revisions_path, entities_path] + (
        [evidence_path] if evidence_path else []
    )
    hashes = {str(p.resolve()): sha256(p) for p in inputs}
    if output.exists():
        raise FileExistsError(f"Use a new output directory: {output}")
    original = pq.read_table(mentions_path)
    rows = original.to_pylist()
    if len({r["source_row_index"] for r in rows}) != len(rows):
        raise ValueError("Original source_row_index values must be unique")
    revisions = pq.read_table(revisions_path).to_pylist()

    def scope(row: dict) -> tuple[int, int]:
        return row["page_id"], row["revision_id"]

    if len({scope(r) for r in revisions}) != len(revisions):
        raise ValueError("Duplicate raw revision scope")
    raw_by_scope = {scope(r): validate_revision(r) for r in revisions}
    if {scope(r) for r in rows} - raw_by_scope.keys():
        raise ValueError("Missing exact source revision for original mentions")
    entities, evidence = defaultdict(list), defaultdict(list)
    for row in pq.read_table(entities_path).to_pylist():
        entities[scope(row)].append(row)
    if evidence_path:
        for row in pq.read_table(evidence_path).to_pylist():
            if scope(row) not in raw_by_scope:
                raise ValueError("Target evidence uses a revision outside this input")
            evidence[scope(row)].append(row)
    occurrences = {
        key: source_occurrences(raw, entities[key], evidence[key])
        for key, raw in raw_by_scope.items()
    }
    passages = defaultdict(list)
    for row in rows:
        passages[(*scope(row), row["passage_id"], row["Text"])].append(row)
    repaired, ledger, bridge, placement_counts = {}, [], [], Counter()
    for (page, revision, passage_id, text), mentions in passages.items():
        raw = raw_by_scope[page, revision]
        placements = positions(raw, text or "")
        status = "unique_exact_raw_placement"
        if len(placements) > 1:
            status = "ambiguous_raw_placement"
        elif not placements:
            status = (
                "normalized_raw_placement_unrepaired"
                if normalize(text or "") in normalize(raw)
                else "raw_placement_unavailable"
            )
        placement_counts[status] += 1
        local = []
        if len(placements) == 1:
            base = placements[0]
            for occurrence in occurrences[page, revision]:
                if (
                    not base
                    <= occurrence["raw_start"]
                    < occurrence["raw_end"]
                    <= base + len(text)
                ):
                    continue
                item = {
                    **occurrence,
                    "page_id": page,
                    "revision_id": revision,
                    "passage_id": passage_id,
                    "start": occurrence["raw_start"] - base,
                    "end": occurrence["raw_end"] - base,
                    "raw_text": raw[occurrence["raw_start"] : occurrence["raw_end"]],
                    "source_row_indices": [],
                }
                item["surface_is_literal"] = (
                    text[item["start"] : item["end"]] == item["surface"]
                )
                item["support_spans_json"] = json.dumps(occurrence["spans"])
                item["occurrence_id"] = hashlib.sha256(
                    json.dumps(
                        [page, revision, passage_id, occurrence],
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode()
                ).hexdigest()
                local.append(item)
        for row in mentions:
            additions = dict(
                word_original=row["word"],
                repair_status="unchanged",
                repair_method=None,
                repair_qid_guided=False,
                source_candidate_qids=[],
                repaired_start=None,
                repaired_end=None,
                repair_alternatives=[],
                source_occurrence_ids=[],
                raw_placement_status=status,
                raw_placement_count=len(placements),
            )
            matches = []
            if row["entity_group"] == "DATE":
                additions["repair_status"] = "date_excluded"
            elif status != "unique_exact_raw_placement":
                additions["repair_status"] = status
            elif not (
                0 <= row["start"] < row["end"] <= len(text)
                and text[row["start"] : row["end"]] == row["word"]
            ):
                additions["repair_status"] = "invalid_original_offsets"
            else:
                matches = [
                    o
                    for o in local
                    if any(
                        s - base < row["end"] and row["start"] < e - base
                        for s, e in o["spans"]
                    )
                ]
                surfaces = sorted({o["surface"] for o in matches})
                additions.update(
                    source_candidate_qids=sorted(
                        {o["qid"] for o in matches if o["qid"]}
                    ),
                    source_occurrence_ids=[o["occurrence_id"] for o in matches],
                    repair_alternatives=surfaces,
                    repair_qid_guided=any(o["qid_guided"] for o in matches),
                )
                if (
                    row["entity_group"] != "PER"
                    and any(
                        o["source_role"] == "citation_author_fields" for o in matches
                    )
                ) or (
                    row["entity_group"] in {"PER", "LOC"}
                    and any(
                        o["source_role"] == "documented_template_target"
                        for o in matches
                    )
                ):
                    additions["repair_status"] = "source_type_review"
                elif any(o["requires_review"] for o in matches):
                    additions["repair_status"] = "source_target_review"
                elif len(surfaces) > 1:
                    additions["repair_status"] = "ambiguous_surface"
                elif len(surfaces) == 1 and not any(
                    s - base <= row["start"] and row["end"] <= e - base
                    for o in matches
                    for s, e in o["spans"]
                ):
                    additions["repair_status"] = "partial_source_overlap"
                elif any(o["context_review"] for o in matches) or (
                    len(surfaces) == 1
                    and surfaces[0] != row["word"]
                    and all(
                        o["source_role"]
                        in {"ordinary_link_anchor", "same_revision_inventory_name"}
                        for o in matches
                    )
                    and not any(cuts_lexical_token(row, o) for o in matches)
                ):
                    additions["repair_status"] = "source_context_review"
                elif len(surfaces) == 1:
                    additions["repair_status"] = (
                        "repaired"
                        if surfaces[0] != row["word"]
                        else "source_supported_unchanged"
                    )
                    additions["repair_method"] = ";".join(
                        sorted({o["method"] for o in matches})
                    )
                    locations = {(o["start"], o["end"]) for o in matches}
                    if len(locations) == 1:
                        additions["repaired_start"], additions["repaired_end"] = next(
                            iter(locations)
                        )
                    additions["word"] = surfaces[0]
                for occurrence in matches:
                    occurrence["source_row_indices"].append(row["source_row_index"])
                    bridge.append(
                        {
                            k: row[k]
                            for k in (
                                "source_row_index",
                                "page_id",
                                "revision_id",
                                "passage_id",
                            )
                        }
                        | {
                            k: occurrence[k]
                            for k in ("occurrence_id", "surface", "qid", "method")
                        }
                    )
            repaired[row["source_row_index"]] = additions
        ledger.extend(local)
    result = [repaired[r["source_row_index"]] for r in rows]
    table = original.set_column(
        original.schema.get_field_index("word"),
        original.schema.field("word"),
        pa.array(
            [a.get("word", r["word"]) for r, a in zip(rows, result)],
            type=original.schema.field("word").type,
        ),
    )
    added_types = {
        "word_original": pa.string(),
        "repair_status": pa.string(),
        "repair_method": pa.string(),
        "repair_qid_guided": pa.bool_(),
        "source_candidate_qids": pa.list_(pa.string()),
        "repaired_start": pa.int64(),
        "repaired_end": pa.int64(),
        "repair_alternatives": pa.list_(pa.string()),
        "source_occurrence_ids": pa.list_(pa.string()),
        "raw_placement_status": pa.string(),
        "raw_placement_count": pa.int64(),
    }
    if set(added_types) & set(original.column_names):
        raise ValueError(
            "Input is already prepared or uses reserved provenance columns"
        )
    for name, dtype in added_types.items():
        table = table.append_column(
            name, pa.array([r[name] for r in result], type=dtype)
        )
    if any(sha256(Path(path)) != digest for path, digest in hashes.items()):
        raise ValueError("Input changed during preparation")
    output.mkdir(parents=True, exist_ok=False)
    write_table(table.to_pylist(), output / "mentions.parquet", table.schema)
    write_table(ledger, output / "recovered_spans.parquet", SPAN_SCHEMA)
    write_table(bridge, output / "mention_span_bridge.parquet", BRIDGE_SCHEMA)
    summary = dict(
        status="COMPLETE_SOURCE_NAME_PREPARATION_NOT_IDENTITY_ASSIGNMENT",
        original_rows=len(rows),
        pages=len({r["page_id"] for r in rows}),
        revisions_validated=len(raw_by_scope),
        date_rows=sum(r["entity_group"] == "DATE" for r in rows),
        repair_statuses=dict(Counter(r["repair_status"] for r in result)),
        repaired_rows=sum(r["repair_status"] == "repaired" for r in result),
        recovered_spans=len(ledger),
        recovered_only_spans=sum(not r["source_row_indices"] for r in ledger),
        mention_span_bridge_rows=len(bridge),
        passage_placement_statuses=dict(placement_counts),
        input_sha256=hashes,
        original_columns_preserved_except_word=True,
        source_qid_support_is_identity_gold=False,
        type_validation="Citation authors require PER; ship targets with PER/LOC retain original word for review; no global native-type mapping",
        generic_source_roles="Article prose/visible link labels only, outside all templates, references, comments, hidden targets and non-article namespaces",
        generic_expansion="Only original lexical-token cuts expand; complete words/phrases retain alternatives and source QIDs for context review",
        normalized_or_repeated_passages="Unchanged; no guessed raw offset maps",
        context_guard_limitation="Adjacent capitalized words can cause false-negative reviews; lowercase longer names are not reliably detected",
        new_api_requests=0,
        completed_utc=utc_now(),
        elapsed_seconds=time.monotonic() - started,
        active_work_seconds=None,
        approval_wait_seconds=None,
        environment_wait_seconds=None,
        output_sha256={p.name: sha256(p) for p in output.glob("*.parquet")},
    )
    save_json(output / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("mentions", "revisions", "entities", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    summary = prepare(
        args.mentions, args.revisions, args.entities, args.evidence, args.output
    )
    LOG.info("Mention preparation: %s", summary)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
