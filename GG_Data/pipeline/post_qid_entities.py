"""Typed identities from accepted occurrence groups, with no identity propagation."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from GG_Data.pipeline.entities import choose_name, native_record
from GG_Data.pipeline.poc import digest, read_json


def provisional_id(word: str, entity_group: str, dataset_namespace: str) -> str:
    if not all(
        isinstance(v, str) and v for v in (word, entity_group, dataset_namespace)
    ):
        raise ValueError("Literal, Daniel type and dataset namespace are required")
    value = json.dumps(
        [dataset_namespace, word, entity_group],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "PROV_" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def mention_id(input_sha256: str, row_index: int) -> str:
    if (
        not re.fullmatch("[0-9a-f]{64}", input_sha256)
        or type(row_index) is not int
        or row_index < 0
    ):
        raise ValueError(
            "Original input SHA256 and nonnegative original row index are required"
        )
    return (
        "mention-" + hashlib.sha256(f"{input_sha256}:{row_index}".encode()).hexdigest()
    )


def populate(
    groups: list[dict],
    accepted_pairs: list[dict],
    *,
    dataset_namespace: str,
    input_sha256: str,
    native_records: dict | None = None,
    metadata: dict | None = None,
    provenance: dict | None = None,
) -> list[dict]:
    native_records, metadata, provenance = (
        native_records or {},
        metadata or {},
        provenance or {},
    )
    by_group = {g["id"]: g for g in groups}
    if len(by_group) != len(groups):
        raise ValueError("Duplicate original group identity")
    seen_rows = set()
    for group in groups:
        indices = group["source_row_indices"]
        if (
            not indices
            or len(set(indices)) != len(indices)
            or seen_rows.intersection(indices)
        ):
            raise ValueError("Original row belongs to duplicate or conflicting groups")
        for index in indices:
            mention_id(input_sha256, index)
        provisional_id(group["name"], group["type"], dataset_namespace)
        seen_rows.update(indices)
    accepted = defaultdict(set)
    for pair in accepted_pairs:
        gid, qid = pair["group_id"], pair["qid"]
        if gid not in by_group or not re.fullmatch(r"Q[1-9]\d*", qid):
            raise ValueError("Unknown accepted group or invalid QID")
        group = by_group[gid]
        for field in ("page_id", "revision_id"):
            if field in pair and pair[field] != group[field]:
                raise ValueError("Accepted pair differs from group revision scope")
        accepted[gid].add(qid)
    identities = defaultdict(list)
    for group in groups:
        for qid in accepted[group["id"]] or {
            provisional_id(group["name"], group["type"], dataset_namespace)
        }:
            identities[qid, group["type"]].append(group)
    result = []
    by_identity = defaultdict(list)
    for (identity, _), occurrences in identities.items():
        by_identity[identity].extend(occurrences)
    for (identity, typ), occurrences in sorted(identities.items()):
        provisional = identity.startswith("PROV_")
        envelope = native_records.get(identity)
        if identity in native_records and not isinstance(envelope, dict):
            raise ValueError(f"Invalid supplied native envelope: {identity}")
        full = native_record(envelope, identity) if identity in native_records else {}
        matching = metadata.get(identity, {})
        names = sorted({g["name"] for g in occurrences})
        mids = [
            mention_id(input_sha256, i)
            for i in sorted({i for g in occurrences for i in g["source_row_indices"]})
        ]
        identity_occurrences = by_identity[identity]
        identity_names = sorted({g["name"] for g in identity_occurrences})
        if len(identity_names) > 1 and not any(
            full.get("labels", {}).get(lang, {}).get("value") for lang in ("en", "ja")
        ):
            name_selection = dict(
                value=None,
                language=None,
                source="Daniel",
                revision=None,
                status="AMBIGUOUS_DANIEL_FALLBACK",
                candidate_names=identity_names,
            )
        else:
            name_selection = choose_name(
                identity,
                full,
                matching,
                [dict(raw=dict(word=g["name"])) for g in identity_occurrences],
            )
        name = name_selection["value"]
        sources = [provenance[identity]] if identity in provenance else []
        if not provisional and not full:
            sources.append(
                dict(
                    provider="WIKIDATA",
                    record_id=identity,
                    status="MISSING_FULL_NATIVE_RECORD",
                )
            )
        elif full and not sources:
            sources.append(
                dict(
                    provider="WIKIDATA",
                    record_id=identity,
                    status="PROVENANCE_NOT_PROVIDED",
                )
            )
        native_types = sorted(
            {
                s.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
                for s in full.get("claims", {}).get("P31", [])
            }
            - {None}
        )
        details = [
            dict(
                label=g["name"],
                kind="mention",
                provider="Daniel",
                record_id=mention_id(input_sha256, i),
                language=None,
            )
            for g in occurrences
            for i in g["source_row_indices"]
        ]
        for language, label in full.get("labels", {}).items():
            details.append(
                dict(
                    label=label["value"],
                    kind="label",
                    provider="WIKIDATA",
                    record_id=identity,
                    language=language,
                )
            )
        for language, aliases in full.get("aliases", {}).items():
            details.extend(
                dict(
                    label=a["value"],
                    kind="alias",
                    provider="WIKIDATA",
                    record_id=identity,
                    language=language,
                )
                for a in aliases
            )
        result.append(
            dict(
                entity_id=identity,
                type=typ,
                name=name,
                observed_names=names,
                labels=full.get("labels", {}),
                descriptions=full.get("descriptions", {}),
                aliases=sorted({d["label"] for d in details}),
                alias_details=details,
                identity_status=(
                    "PROVISIONAL_UNRESOLVED" if provisional else "QID_MATCHED"
                ),
                native_record_status=(
                    "NOT_APPLICABLE"
                    if provisional
                    else ("AVAILABLE" if full else "MISSING")
                ),
                review_status="NOT_REVIEWED",
                sources=sources,
                text=None,
                embedding=None,
                importance=None,
                unique_original_mention_count=len(
                    {i for g in identity_occurrences for i in g["source_row_indices"]}
                ),
                distinct_source_page_count=len(
                    {g["page_id"] for g in identity_occurrences}
                ),
                direct_types=matching.get("direct_types", []),
                native_types=native_types,
                parents=matching.get("parents", []),
                sitelinks=full.get("sitelinks", {}),
                revision=full.get("lastrevid"),
                modified=full.get("modified"),
                missing=None if provisional else not bool(full),
                reference_source=(
                    "Daniel"
                    if provisional
                    else provenance.get(identity, {}).get("provider")
                ),
                raw_reference=dict(full=envelope, matching=matching),
                attributes=dict(
                    name_selection=name_selection,
                    mention_ids=mids,
                    group_ids=sorted(g["id"] for g in occurrences),
                    source_page_ids=sorted({g["page_id"] for g in occurrences}),
                    dataset_namespace=dataset_namespace,
                    supplied_property_claims={
                        p: full["claims"][p]
                        for p in ("P17", "P879", "P729", "P730")
                        if p in full.get("claims", {})
                    },
                ),
            )
        )
    return result


def run(
    groups_path: Path,
    pairs_path: Path,
    output: Path,
    *,
    dataset_namespace: str,
    input_sha256: str,
    native_path: Path | None = None,
    metadata_path: Path | None = None,
    provenance_path: Path | None = None,
    page_ids: set[int] | None = None,
) -> dict:
    import pyarrow.parquet as pq

    groups = [
        json.loads(line)
        for line in groups_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pairs = (
        pq.read_table(pairs_path).to_pylist()
        if pairs_path.suffix == ".parquet"
        else read_json(pairs_path)
    )
    if page_ids is not None:
        groups = [g for g in groups if g["page_id"] in page_ids]
        ids = {g["id"] for g in groups}
        pairs = [p for p in pairs if p["group_id"] in ids]
        if {g["page_id"] for g in groups} != page_ids:
            raise ValueError("Selected page has no original groups")
    rows = populate(
        groups,
        pairs,
        dataset_namespace=dataset_namespace,
        input_sha256=input_sha256,
        native_records=read_json(native_path) if native_path else None,
        metadata=read_json(metadata_path) if metadata_path else None,
        provenance=read_json(provenance_path) if provenance_path else None,
    )
    output.mkdir(parents=True, exist_ok=False)
    with gzip.open(output / "entities.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(rows, stream, ensure_ascii=False)
    manifest = dict(
        dataset_namespace=dataset_namespace,
        original_input_sha256=input_sha256,
        inputs={
            str(p): digest(p)
            for p in (
                groups_path,
                pairs_path,
                native_path,
                metadata_path,
                provenance_path,
            )
            if p
        },
        row_count=len(rows),
        outputs={"entities.json.gz": digest(output / "entities.json.gz")},
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("groups", "pairs", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("native", "metadata", "provenance"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--dataset-namespace", required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--page-ids", type=int, nargs="+")
    args = parser.parse_args()
    run(
        args.groups,
        args.pairs,
        args.output,
        dataset_namespace=args.dataset_namespace,
        input_sha256=args.input_sha256,
        native_path=args.native,
        metadata_path=args.metadata,
        provenance_path=args.provenance,
        page_ids=set(args.page_ids) if args.page_ids else None,
    )


if __name__ == "__main__":
    main()
