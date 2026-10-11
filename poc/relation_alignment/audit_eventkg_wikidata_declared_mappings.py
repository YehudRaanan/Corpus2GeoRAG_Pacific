"""Audit EventKG predicates without pair overlap against published mappings."""

from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = HERE / "unresolved_relation_eda" / "unresolved_relation_summary.csv"
WIKIDATA_METADATA = (
    HERE / "relation_catalog_eda" / "wikidata_property_metadata.json"
)
OUT = HERE / "eventkg_wikidata_declared_mapping_audit"
REPORT = HERE / "EVENTKG_WIKIDATA_DECLARED_MAPPING_AUDIT_2026-10-11.md"

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
DBPEDIA_SPARQL = "https://dbpedia.org/sparql"
EVENTKG_SUBLOCATIONS = (
    "https://raw.githubusercontent.com/sgottsch/eventkg/"
    "0face5765ffc3e16a8746f9ed98877dc86de2bef/"
    "src/resource/meta_data/wikidata/properties_sublocations.tsv"
)
PARIS_ARCHIVE = (
    "https://github.com/dig-team/PARIS/raw/main/data/"
    "yago-dbpedia-relations-result.zip"
)

OWL_EQUIVALENT = "http://www.w3.org/2002/07/owl#equivalentProperty"
RDFS_SUBPROPERTY = "http://www.w3.org/2000/01/rdf-schema#subPropertyOf"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def request_bytes(
    url: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
    accept: str = "*/*",
) -> bytes:
    headers = {
        "User-Agent": "Corpus2GeoRAG-Pacific/1.0 relation-mapping-audit",
        "Accept": accept,
    }
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def sparql_json(endpoint: str, query: str) -> dict:
    if endpoint == WIKIDATA_SPARQL:
        data = query.encode("utf-8")
        content_type = "application/sparql-query"
    else:
        data = urllib.parse.urlencode(
            {"query": query, "format": "application/sparql-results+json"}
        ).encode("utf-8")
        content_type = "application/x-www-form-urlencoded"
    return json.loads(
        request_bytes(
            endpoint,
            data=data,
            content_type=content_type,
            accept="application/sparql-results+json",
        )
    )


def normalize_uri(uri: str) -> str:
    return uri.replace("https://", "http://").rstrip("/")


def property_id(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


def no_overlap_eventkg_rows() -> list[dict[str, str]]:
    return [
        row
        for row in read_csv(INPUT)
        if row["source"] == "EventKG"
        and row["eda_status"] == "NO_QID_PAIR_OVERLAP"
    ]


def load_wikidata_external_mappings() -> list[dict[str, str]]:
    query = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
SELECT ?wdp ?kind ?external WHERE {
  VALUES ?kind { wdt:P1628 wdt:P2235 wdt:P2236 }
  ?wdp ?kind ?external .
}
"""
    bindings = sparql_json(WIKIDATA_SPARQL, query)["results"]["bindings"]
    return [
        {
            "wikidata_property": property_id(row["wdp"]["value"]),
            "mapping_property": property_id(row["kind"]["value"]),
            "external_uri": row["external"]["value"],
        }
        for row in bindings
    ]


def load_dbpedia_paths(dbpedia_predicates: list[str]) -> list[dict[str, str]]:
    values = " ".join(f"<{uri}>" for uri in dbpedia_predicates)
    query = f"""
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?p ?kind ?target WHERE {{
  VALUES ?p {{ {values} }}
  {{ ?p owl:equivalentProperty ?target .
     BIND(owl:equivalentProperty AS ?kind) }}
  UNION
  {{ ?p rdfs:subPropertyOf+ ?parent .
     ?parent owl:equivalentProperty ?target .
     BIND(?parent AS ?kind) }}
}}
"""
    bindings = sparql_json(DBPEDIA_SPARQL, query)["results"]["bindings"]
    return [
        {
            "predicate": row["p"]["value"],
            "kind": row["kind"]["value"],
            "target": row["target"]["value"],
        }
        for row in bindings
    ]


def load_eventkg_sublocations() -> list[tuple[str, str, str]]:
    text = request_bytes(EVENTKG_SUBLOCATIONS).decode("utf-8-sig")
    return [tuple(line.split("\t")) for line in text.splitlines() if line.strip()]


def load_eventkg_paris_links() -> dict[str, set[tuple[str, float]]]:
    archive = zipfile.ZipFile(io.BytesIO(request_bytes(PARIS_ARCHIVE)))
    links: dict[str, set[tuple[str, float]]] = defaultdict(set)
    for name in (
        "relations_dbpedia_sub_yago.tsv",
        "relations_yago_sub_dbpedia.tsv",
    ):
        for line in archive.read(name).decode("utf-8").splitlines():
            first, second, confidence_text = line.split("\t")
            confidence = float(confidence_text)
            if confidence < 0.51 or "goldenRaspberryAward" in line:
                continue
            if name.startswith("relations_dbpedia"):
                dbpedia_value, yago_value = first, second
            else:
                yago_value, dbpedia_value = first, second
            if (
                not yago_value.startswith("y:")
                or yago_value.endswith("-")
                or not dbpedia_value.startswith("dbp:ontology/")
                or dbpedia_value.endswith("-")
            ):
                continue
            yago_uri = "http://yago-knowledge.org/resource/" + yago_value[2:]
            dbpedia_uri = "http://dbpedia.org/ontology/" + dbpedia_value[13:]
            links[yago_uri].add((dbpedia_uri, confidence))
    return links


def add_candidate(
    candidates: set[tuple[str, ...]],
    predicate: str,
    wd_property: str,
    relation: str,
    direction: str,
    path: str,
    evidence_type: str,
    evidence_url: str,
    note: str = "",
) -> None:
    candidates.add(
        (
            predicate,
            wd_property,
            relation,
            direction,
            path,
            evidence_type,
            evidence_url,
            note,
        )
    )


def build_candidates(
    source_rows: list[dict[str, str]],
    wd_external: list[dict[str, str]],
    dbpedia_paths: list[dict[str, str]],
    sublocations: list[tuple[str, str, str]],
    paris_links: dict[str, set[tuple[str, float]]],
    paris_dbpedia_paths: list[dict[str, str]],
) -> list[dict[str, str]]:
    candidates: set[tuple[str, ...]] = set()
    source_by_normalized = {
        normalize_uri(row["source_predicate"]): row for row in source_rows
    }
    wd_by_external: dict[str, list[dict[str, str]]] = defaultdict(list)
    for mapping in wd_external:
        wd_by_external[normalize_uri(mapping["external_uri"])].append(mapping)

    for normalized, row in source_by_normalized.items():
        for mapping in wd_by_external.get(normalized, []):
            kind = mapping["mapping_property"]
            relation = {
                "P1628": "EXACT",
                "P2235": "EVENTKG_BROADER_THAN_WIKIDATA",
                "P2236": "EVENTKG_NARROWER_THAN_WIKIDATA",
            }[kind]
            add_candidate(
                candidates,
                row["source_predicate"],
                mapping["wikidata_property"],
                relation,
                "same",
                f"EventKG predicate <- Wikidata {kind}",
                "WIKIDATA_EXTERNAL_MAPPING",
                f"https://www.wikidata.org/wiki/Property:{mapping['wikidata_property']}",
            )

    for path in dbpedia_paths:
        predicate = path["predicate"]
        target = path["target"]
        is_direct = path["kind"] == OWL_EQUIVALENT
        if "wikidata.org" in target and property_id(target).startswith("P"):
            add_candidate(
                candidates,
                predicate,
                property_id(target),
                "EXACT" if is_direct else "EVENTKG_NARROWER_THAN_WIKIDATA",
                "same",
                (
                    "DBpedia owl:equivalentProperty"
                    if is_direct
                    else f"DBpedia rdfs:subPropertyOf+ {path['kind']} then owl:equivalentProperty"
                ),
                "DBPEDIA_ONTOLOGY",
                predicate,
            )
            continue
        for mapping in wd_by_external.get(normalize_uri(target), []):
            wd_kind = mapping["mapping_property"]
            if is_direct and wd_kind == "P1628":
                relation = "EXACT_CHAIN"
            elif wd_kind in {"P1628", "P2236"}:
                relation = "EVENTKG_NARROWER_THAN_WIKIDATA"
            else:
                relation = "RELATED_VIA_SHARED_SUPERPROPERTY"
            add_candidate(
                candidates,
                predicate,
                mapping["wikidata_property"],
                relation,
                "same",
                f"DBpedia path via {target} then Wikidata {wd_kind}",
                "CROSS_ONTOLOGY_CHAIN",
                f"https://www.wikidata.org/wiki/Property:{mapping['wikidata_property']}",
            )

    contained = "http://schema.org/containedInPlace"
    if normalize_uri(contained) in source_by_normalized:
        for wd_property, label, symbol in sublocations:
            add_candidate(
                candidates,
                source_by_normalized[normalize_uri(contained)]["source_predicate"],
                wd_property,
                "EVENTKG_NORMALIZATION_OPTION",
                "same" if symbol == "s" else "reverse",
                f"EventKG normalizes Wikidata {wd_property} to schema:containedInPlace",
                "EVENTKG_MANUAL_MAPPING",
                EVENTKG_SUBLOCATIONS,
                label,
            )

    paris_exact: dict[str, set[str]] = defaultdict(set)
    for path in paris_dbpedia_paths:
        if (
            path["kind"] == OWL_EQUIVALENT
            and "wikidata.org" in path["target"]
            and property_id(path["target"]).startswith("P")
        ):
            paris_exact[path["predicate"]].add(property_id(path["target"]))
        if path["kind"] == OWL_EQUIVALENT:
            for mapping in wd_by_external.get(normalize_uri(path["target"]), []):
                if mapping["mapping_property"] == "P1628":
                    paris_exact[path["predicate"]].add(mapping["wikidata_property"])

    source_predicates = {row["source_predicate"] for row in source_rows}
    for yago_uri, links in paris_links.items():
        if yago_uri not in source_predicates:
            continue
        for dbpedia_uri, confidence in links:
            for wd_property in paris_exact.get(dbpedia_uri, set()):
                add_candidate(
                    candidates,
                    yago_uri,
                    wd_property,
                    "AUTOMATIC_ALIGNMENT_CANDIDATE",
                    "same",
                    f"YAGO -> DBpedia PARIS {confidence:.6f} -> Wikidata equivalent",
                    "EVENTKG_PARIS_ALIGNMENT",
                    PARIS_ARCHIVE,
                    "EventKG accepts PARIS scores >= 0.51, but PARIS marks them as possibly inaccurate.",
                )

    labels = {
        key: value.get("label", "")
        for key, value in json.loads(WIKIDATA_METADATA.read_text(encoding="utf-8"))[
            "properties"
        ].items()
    }
    source_lookup = {row["source_predicate"]: row for row in source_rows}
    output = []
    for item in sorted(candidates):
        (
            predicate,
            wd_property,
            relation,
            direction,
            path,
            evidence_type,
            evidence_url,
            note,
        ) = item
        source = source_lookup[predicate]
        output.append(
            {
                "eventkg_predicate": predicate,
                "eventkg_label": source["source_label"],
                "source_occurrence_count": source["source_occurrence_count"],
                "wikidata_property": wd_property,
                "wikidata_label": labels.get(wd_property, ""),
                "mapping_relation": relation,
                "direction": direction,
                "mapping_path": path,
                "evidence_type": evidence_type,
                "evidence_url": evidence_url,
                "note": note,
            }
        )
    return output


def classify_predicates(
    source_rows: list[dict[str, str]], candidates: list[dict[str, str]]
) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate["eventkg_predicate"]].append(candidate)
    output = []
    for source in source_rows:
        rows = grouped.get(source["source_predicate"], [])
        exact = {
            row["wikidata_property"]
            for row in rows
            if row["mapping_relation"] in {"EXACT", "EXACT_CHAIN"}
        }
        group = {
            row["wikidata_property"]
            for row in rows
            if row["mapping_relation"] == "EVENTKG_NORMALIZATION_OPTION"
        }
        automatic = {
            row["wikidata_property"]
            for row in rows
            if row["mapping_relation"] == "AUTOMATIC_ALIGNMENT_CANDIDATE"
        }
        broader = {
            row["wikidata_property"]
            for row in rows
            if row["mapping_relation"]
            in {
                "EVENTKG_BROADER_THAN_WIKIDATA",
                "EVENTKG_NARROWER_THAN_WIKIDATA",
                "RELATED_VIA_SHARED_SUPERPROPERTY",
            }
        }
        if len(exact) == 1:
            status = "DECLARED_EXACT_SINGLE"
        elif len(exact) > 1:
            status = "DECLARED_EXACT_CONFLICT"
        elif group:
            status = "NORMALIZED_MULTI_OPTION"
        elif automatic:
            status = "AUTOMATIC_ALIGNMENT_CANDIDATE"
        elif broader:
            status = "BROADER_OR_NARROWER_ONLY"
        else:
            status = "NO_DECLARED_MAPPING_FOUND"
        output.append(
            {
                "eventkg_predicate": source["source_predicate"],
                "eventkg_label": source["source_label"],
                "source_occurrence_count": source["source_occurrence_count"],
                "audit_status": status,
                "exact_wikidata_options": "|".join(sorted(exact)),
                "normalization_options": "|".join(sorted(group)),
                "automatic_options": "|".join(sorted(automatic)),
                "broader_narrower_options": "|".join(sorted(broader)),
                "candidate_row_count": str(len(rows)),
            }
        )
    return sorted(output, key=lambda row: row["eventkg_predicate"])


def make_summary(audit_rows: list[dict[str, str]]) -> dict:
    status = Counter(row["audit_status"] for row in audit_rows)
    occurrences = Counter()
    for row in audit_rows:
        occurrences[row["audit_status"]] += int(row["source_occurrence_count"] or 0)
    mapped_statuses = set(status) - {"NO_DECLARED_MAPPING_FOUND"}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "EventKG NO_QID_PAIR_OVERLAP predicates",
        "predicate_count": len(audit_rows),
        "occurrence_count": sum(int(row["source_occurrence_count"] or 0) for row in audit_rows),
        "predicates_with_any_declared_or_candidate_mapping": sum(
            status[name] for name in mapped_statuses
        ),
        "occurrences_with_any_declared_or_candidate_mapping": sum(
            occurrences[name] for name in mapped_statuses
        ),
        "status_counts": dict(sorted(status.items())),
        "status_occurrence_counts": dict(sorted(occurrences.items())),
        "eventkg_repository_commit": "0face5765ffc3e16a8746f9ed98877dc86de2bef",
        "eventkg_v3_2_wikidata_snapshot": "2023-02-27",
        "eventkg_v3_2_dbpedia_snapshot": "2022-12-01",
    }


def render_report(
    audit_rows: list[dict[str, str]],
    candidates: list[dict[str, str]],
    summary: dict,
) -> str:
    mapped = [row for row in audit_rows if row["audit_status"] != "NO_DECLARED_MAPPING_FOUND"]
    top = sorted(mapped, key=lambda row: int(row["source_occurrence_count"]), reverse=True)[:20]
    table = "\n".join(
        "| {label} | {count} | {status} | {options} |".format(
            label=row["eventkg_label"].replace("|", "\\|"),
            count=row["source_occurrence_count"],
            status=row["audit_status"],
            options=(
                row["exact_wikidata_options"]
                or row["normalization_options"]
                or row["automatic_options"]
                or row["broader_narrower_options"]
            ).replace("|", ", "),
        )
        for row in top
    )
    conflict_rows = [
        row for row in audit_rows if row["audit_status"] == "DECLARED_EXACT_CONFLICT"
    ]
    conflicts = "\n".join(
        f"- `{row['eventkg_predicate']}` has exact targets "
        f"`{row['exact_wikidata_options'].replace('|', '`, `')}`. Keep it unresolved."
        for row in conflict_rows
    ) or "- None."
    return f"""# EventKG-Wikidata declared mapping audit

## Result

The pair-overlap test missed published schema mappings.

- Scope: **{summary['predicate_count']}** EventKG Level 2 predicates with no local QID-pair overlap, covering **{summary['occurrence_count']:,}** observations.
- A published exact, grouped, broader/narrower, or automatic candidate exists for **{summary['predicates_with_any_declared_or_candidate_mapping']}** predicates and **{summary['occurrences_with_any_declared_or_candidate_mapping']:,}** observations.
- **{summary['status_counts'].get('DECLARED_EXACT_SINGLE', 0)}** predicates have one declared exact Wikidata target.
- **{summary['status_counts'].get('DECLARED_EXACT_CONFLICT', 0)}** predicates have conflicting exact targets.
- **{summary['status_counts'].get('NORMALIZED_MULTI_OPTION', 0)}** EventKG predicates combine several Wikidata source properties.
- **{summary['status_counts'].get('AUTOMATIC_ALIGNMENT_CANDIDATE', 0)}** predicates have only an EventKG-used PARIS candidate.
- **{summary['status_counts'].get('BROADER_OR_NARROWER_ONLY', 0)}** predicates have only a broader or narrower ontology path.
- **{summary['status_counts'].get('NO_DECLARED_MAPPING_FOUND', 0)}** predicates still have no published mapping found by this audit.

Do not merge all candidates as exact mappings. Add the single exact mappings to the review queue. Keep conflicts, grouped mappings, and broader mappings as allowed options.

## Highest-volume recovered cases

| EventKG Level 2 | Observations | Result | Wikidata option(s) |
| --- | ---: | --- | --- |
{table}

`schema:containedInPlace` is a special case. EventKG creates it from eight Wikidata properties. Five keep direction (`P131`, `P706`, `P17`, `P1376`, `P3018`). Three reverse direction (`P150`, `P36`, `P1383`). The final EventKG base triple does not keep the original property ID. The endpoint types and text must select the source meaning.

## Conflicts

{conflicts}

## Evidence paths checked

1. Wikidata `P1628`, `P2235`, and `P2236` external property mappings.
2. DBpedia `owl:equivalentProperty` declarations to Wikidata.
3. DBpedia equivalence to another public ontology, followed by a Wikidata mapping to that ontology.
4. DBpedia `rdfs:subPropertyOf` paths to a property mapped to Wikidata.
5. EventKG's manual Wikidata-to-`schema:containedInPlace` mapping.
6. The YAGO-DBpedia PARIS mappings that EventKG accepts at score 0.51 or higher.

Time mappings were not added. Dates are relation attributes in this project.

## Version limit

The local EventKG V3.2 data uses Wikidata **2023-02-27** and DBpedia **2022-12-01** snapshots. The Wikidata and DBpedia ontology services were queried when this report was generated. A current declaration can postdate the EventKG snapshot. Keep the source URL and retrieval time with every accepted mapping.

## Files

- `eventkg_wikidata_declared_mapping_audit/predicate_audit.csv`: one row per audited EventKG predicate.
- `eventkg_wikidata_declared_mapping_audit/mapping_candidates.csv`: every declared mapping path and direction.
- `eventkg_wikidata_declared_mapping_audit/summary.json`: counts and source versions.
"""


def main() -> None:
    source_rows = no_overlap_eventkg_rows()
    wd_external = load_wikidata_external_mappings()
    dbpedia_predicates = [
        row["source_predicate"]
        for row in source_rows
        if row["source_predicate"].startswith("http://dbpedia.org/ontology/")
    ]
    dbpedia_paths = load_dbpedia_paths(dbpedia_predicates)
    paris_links = load_eventkg_paris_links()
    paris_dbpedia = sorted(
        {dbpedia for links in paris_links.values() for dbpedia, _ in links}
    )
    paris_dbpedia_paths = load_dbpedia_paths(paris_dbpedia)
    candidates = build_candidates(
        source_rows,
        wd_external,
        dbpedia_paths,
        load_eventkg_sublocations(),
        paris_links,
        paris_dbpedia_paths,
    )
    audit_rows = classify_predicates(source_rows, candidates)
    summary = make_summary(audit_rows)

    write_csv(
        OUT / "mapping_candidates.csv",
        candidates,
        [
            "eventkg_predicate",
            "eventkg_label",
            "source_occurrence_count",
            "wikidata_property",
            "wikidata_label",
            "mapping_relation",
            "direction",
            "mapping_path",
            "evidence_type",
            "evidence_url",
            "note",
        ],
    )
    write_csv(
        OUT / "predicate_audit.csv",
        audit_rows,
        [
            "eventkg_predicate",
            "eventkg_label",
            "source_occurrence_count",
            "audit_status",
            "exact_wikidata_options",
            "normalization_options",
            "automatic_options",
            "broader_narrower_options",
            "candidate_row_count",
        ],
    )
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    REPORT.write_text(render_report(audit_rows, candidates, summary), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
