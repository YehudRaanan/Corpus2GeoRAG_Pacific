"""Validate core population and count coverage; these counts are not accuracy.

Optional page co-occurrence uses typed identities, including DATE and provisional
identities. Its shared-page weights are not native Wikidata relation weights.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from GG_Data.pipeline.poc import digest, read_json

CORE_TABLES = ("wiki_pages", "entities", "mentions", "mention_entity_links")


def summarize(
    tables: dict[str, list[dict]],
    manifest: dict | None = None,
    *,
    include_cooccurrence: bool = False,
) -> dict:
    """Fail on broken source preservation, keys, typed FKs or importance factors."""
    if not set(CORE_TABLES) <= tables.keys():
        raise ValueError("All four core tables are required")
    manifest = manifest or {}
    entities, pages, mentions, links = (
        tables[n]
        for n in ("entities", "wiki_pages", "mentions", "mention_entity_links")
    )
    entities_by_key = {(e["entity_id"], e["type"]): e for e in entities}
    page_keys = {(p["wiki_site"], p["wiki_page_id"], p["revision_id"]) for p in pages}
    mentions_by_id = {m["mention_id"]: m for m in mentions}
    indices = {m["source_row_index"] for m in mentions}
    if (
        len(entities_by_key) != len(entities)
        or len(page_keys) != len(pages)
        or len(mentions_by_id) != len(mentions)
        or len(indices) != len(mentions)
    ):
        raise ValueError("Duplicate core primary key or original row index")
    used_pages = set()
    for mention in mentions:
        raw = mention.get("raw")
        key = (mention["wiki_site"], mention["wiki_page_id"], mention["revision_id"])
        if (
            not isinstance(raw, dict)
            or not {
                "source_row_index",
                "page_id",
                "revision_id",
                "word",
                "entity_group",
                "Source",
                "Text",
                "start",
                "end",
            }
            <= raw.keys()
            or any(k not in mention or mention[k] != value for k, value in raw.items())
            or mention["wiki_site"] != "enwiki"
            or key not in page_keys
            or mention.get("page_id") != mention["wiki_page_id"]
        ):
            raise ValueError("Original mention fields or revision FK changed")
        if (
            type(mention["source_row_index"]) is not int
            or mention["source_row_index"] < 0
            or not isinstance(raw.get("Source"), str)
            or not raw["Source"]
        ):
            raise ValueError("Original row identity/source title is missing")
        used_pages.add(key)
    if used_pages != page_keys:
        raise ValueError("Wiki Pages contains unused or missing revision rows")
    linked_mentions, link_keys = set(), set()
    identity_mentions, identity_sources = defaultdict(set), defaultdict(set)
    page_entities, mention_qids, qid_names = (
        defaultdict(set),
        defaultdict(set),
        defaultdict(set),
    )
    method_links, method_mentions = Counter(), defaultdict(set)
    linked_entities = set()
    for link in links:
        mid, eid, typ = link["mention_id"], link["entity_id"], link["entity_type"]
        key = mid, eid, typ
        if (
            key in link_keys
            or mid not in mentions_by_id
            or (eid, typ) not in entities_by_key
            or typ != mentions_by_id[mid]["entity_group"]
        ):
            raise ValueError("Duplicate bridge key or broken typed mention/entity FK")
        mention = mentions_by_id[mid]
        methods = link.get("methods", [link["method"]])
        if (
            link.get("method") not in {"exact", "model", "unresolved"}
            or not methods
            or not set(methods) <= {"exact", "model", "unresolved"}
            or link["method"] not in methods
            or len(methods) != len(set(methods))
            or eid.startswith("PROV_") != (methods == ["unresolved"])
        ):
            raise ValueError("Unknown matching method")
        link_keys.add(key)
        linked_mentions.add(mid)
        linked_entities.add((eid, typ))
        identity_mentions[eid].add(mid)
        identity_sources[eid].add(mention["raw"]["Source"])
        page_entities[mention["wiki_site"], mention["wiki_page_id"]].add((eid, typ))
        method_links[link["method"]] += 1
        for method in methods:
            method_mentions[method].add(mid)
        if eid.startswith("Q"):
            mention_qids[mid].add(eid)
            qid_names[eid].add(mention["word"])
    unlinked = entities_by_key.keys() - linked_entities
    if linked_mentions != mentions_by_id.keys() or any(
        typ not in {"event", "EVENT"} for _, typ in unlinked
    ):
        raise ValueError("Every original mention and core Entity must have a bridge")
    for entity in entities:
        eid = entity["entity_id"]
        if (eid, entity["type"]) in unlinked:
            continue
        count, source_count = len(identity_mentions[eid]), len(identity_sources[eid])
        basis = entity.get("attributes", {}).get("importance_basis", {})
        attributes = entity.get("attributes", {})
        if (
            entity.get("importance") != count * source_count
            or entity.get("unique_original_mention_count") != count
            or entity.get("distinct_source_page_count") != source_count
            or basis.get("total_mentions") != count
            or basis.get("distinct_source_pages") != source_count
            or attributes.get("normalized_mention_frequency_denominator")
            != len(mentions)
            or not isinstance(
                attributes.get("normalized_mention_frequency"), (int, float)
            )
            or not math.isclose(
                attributes["normalized_mention_frequency"], count / len(mentions)
            )
        ):
            raise ValueError(
                f"Importance factors or population denominator differ: {eid}"
            )
    for name, count in manifest.get("counts", {}).items():
        if name in tables and count != len(tables[name]):
            raise ValueError(f"Manifest table count differs: {name}")
    source_page_keys = {(p["wiki_site"], p["wiki_page_id"]) for p in pages}
    if "page_ids" in manifest and set(manifest["page_ids"]) != {
        key[1] for key in source_page_keys
    }:
        raise ValueError("Manifest page membership differs")
    qid_rows = [e for e in entities if e["entity_id"].startswith("Q")]
    corpus_qid_rows = [
        e for e in qid_rows if (e["entity_id"], e["type"]) not in unlinked
    ]
    provisional_rows = [e for e in entities if e["entity_id"].startswith("PROV_")]
    if len(qid_rows) + len(provisional_rows) != len(entities):
        raise ValueError("Unknown core Entity identity namespace")
    report = {
        "status": "CORE_CONTROLS_PASSED_OPTIONAL_TABLES_NOT_EVALUATED",
        "denominators": dict(
            original_mentions=len(mentions),
            source_pages=len(source_page_keys),
            used_revisions=len(pages),
            bridge_rows=len(links),
        ),
        "table_counts": {name: len(rows) for name, rows in tables.items()},
        "types": {
            "original_mentions": dict(
                sorted(Counter(m["entity_group"] for m in mentions).items())
            ),
            "typed_entities": dict(
                sorted(Counter(e["type"] for e in entities).items())
            ),
        },
        "identities": dict(
            qid_typed_rows=len(qid_rows),
            qid_distinct=len({e["entity_id"] for e in qid_rows}),
            provisional_typed_rows=len(provisional_rows),
            provisional_distinct=len({e["entity_id"] for e in provisional_rows}),
        ),
        "many_to_many": {
            "mentions_with_multiple_qids": sum(
                len(qids) > 1 for qids in mention_qids.values()
            ),
            "qid_count_per_original_mention": dict(
                sorted(
                    Counter(len(mention_qids[mid]) for mid in mentions_by_id).items()
                )
            ),
            "qids_with_multiple_daniel_names": sum(
                len(names) > 1 for names in qid_names.values()
            ),
            "multiple_names": {
                qid: sorted(names)
                for qid, names in sorted(qid_names.items())
                if len(names) > 1
            },
        },
        "methods": {
            "bridge_rows": dict(sorted(method_links.items())),
            "unique_original_mentions": {
                method: len(mids) for method, mids in sorted(method_mentions.items())
            },
            "note": "A mention can have several methods; method counts need not sum to original mentions",
        },
        "native_records": {
            "statuses_typed_rows": dict(
                sorted(
                    Counter(
                        e.get("native_record_status", "UNKNOWN")
                        for e in entities
                        if (e["entity_id"], e["type"]) not in unlinked
                    ).items()
                )
            ),
            "missing_qid_typed_rows": sum(
                e.get("native_record_status") != "AVAILABLE" for e in corpus_qid_rows
            ),
            "blank_english_label_qid_typed_rows": sum(
                not (e.get("labels", {}).get("en", {}).get("value") or "").strip()
                for e in corpus_qid_rows
            ),
            "event_only_source_coverage": {
                "status": "NOT_EVALUATED_EVENT_SOURCE",
                "typed_rows": len(unlinked),
            },
        },
        "importance": {
            "verified_typed_rows": len(entities) - len(unlinked),
            "event_only_typed_rows": len(unlinked),
            "event_only_importance_status": "NOT_EVALUATED_EVENT_SOURCE",
            "original_population_denominator": len(mentions),
            "formula": "unique original mention IDs per identity * distinct original raw.Source pages",
            "typed_qid_fanout_counted_once": True,
        },
        "optional_tables": {
            name: (
                {"status": "PRESENT_NOT_EVALUATED", "row_count": len(tables[name])}
                if name in tables
                else {"status": "NOT_EVALUATED", "row_count": None}
            )
            for name in ("events", "relations", "geography")
        },
        "quality_status": manifest.get("quality_status", "NOT_EVALUATED"),
        "accuracy_status": "NOT_EVALUATED_POSITIVE_ONLY_REFERENCE",
        "accuracy_note": "Population completeness and matching-method counts do not establish precision or stop precision",
        "page_cooccurrence": {"status": "NOT_EVALUATED"},
    }
    report["coverage_by_page"] = [
        dict(
            wiki_site=site,
            wiki_page_id=page,
            original_mentions=sum(
                m["wiki_site"] == site and m["wiki_page_id"] == page for m in mentions
            ),
            used_revisions=sum(p[0] == site and p[1] == page for p in page_keys),
            typed_entities=len(page_entities[site, page]),
        )
        for site, page in sorted(source_page_keys)
    ]
    report["coverage_by_revision"] = [
        dict(
            wiki_site=site,
            wiki_page_id=page,
            revision_id=revision,
            original_mentions=sum(
                (m["wiki_site"], m["wiki_page_id"], m["revision_id"])
                == (site, page, revision)
                for m in mentions
            ),
        )
        for site, page, revision in sorted(page_keys)
    ]
    if include_cooccurrence:
        weights, neighbours = Counter(), defaultdict(set)
        for present in page_entities.values():
            for left, right in itertools.combinations(sorted(present), 2):
                weights[left, right] += 1
                neighbours[left].add(right)
                neighbours[right].add(left)
        report["page_cooccurrence"] = {
            "status": "PAGE_COOCCURRENCE_NOT_NATIVE_RELATIONS",
            "page_denominator": len(source_page_keys),
            "identity_basis": "typed identities, including DATE and provisional identities",
            "nodes": [
                dict(entity_id=eid, entity_type=typ, degree=len(neighbours[eid, typ]))
                for eid, typ in sorted(entities_by_key)
            ],
            "edges": [
                dict(
                    source_entity_id=left[0],
                    source_entity_type=left[1],
                    target_entity_id=right[0],
                    target_entity_type=right[1],
                    shared_page_count=count,
                )
                for (left, right), count in sorted(weights.items())
            ],
        }
    return report


def run(core_dir: Path, output: Path, *, include_cooccurrence: bool = False) -> dict:
    paths = {name: core_dir / f"{name}.json.gz" for name in CORE_TABLES}
    for name in ("events", "relations", "geography"):
        path = core_dir / f"{name}.json.gz"
        if path.is_file():
            paths[name] = path
    manifest_path = core_dir / "manifest.json"
    manifest = read_json(manifest_path)
    if not set(CORE_TABLES) <= manifest.get("counts", {}).keys():
        raise ValueError("Manifest must state all core table counts")
    for name, expected in manifest.get("outputs", {}).items():
        path = core_dir / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"Core output hash differs: {name}")
    report = summarize(
        {name: read_json(path) for name, path in paths.items()},
        manifest,
        include_cooccurrence=include_cooccurrence,
    )
    report["inputs"] = {
        str(path.resolve()): digest(path) for path in (*paths.values(), manifest_path)
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "eda.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cooccurrence", action="store_true")
    args = parser.parse_args()
    run(args.core_dir, args.output, include_cooccurrence=args.cooccurrence)


if __name__ == "__main__":
    main()
