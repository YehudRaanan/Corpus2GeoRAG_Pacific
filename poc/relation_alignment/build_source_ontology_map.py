"""Build a source-declared Level 1 -> Level 2 relation map."""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = HERE / "relation_catalog_eda" / "source_predicate_inventory.csv"
OUT = HERE / "source_ontology_map"
REPORT = HERE / "SOURCE_ONTOLOGY_LEVEL1_LEVEL2_2026-10-11.md"
WARSA_SCHEMA = (
    HERE.parent.parent
    / "Data"
    / "external"
    / "warsampo"
    / "full"
    / "Warsampo-schema"
    / "warsampo-schema.ttl"
)

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
SEM = "http://semanticweb.cs.vu.nl/2009/11/sem/"
SCHEMA = "http://schema.org/"

SOURCES = {
    "WIKIDATA": "https://www.wikidata.org/wiki/Help:Data_model",
    "DBPEDIA": "https://www.dbpedia.org/resources/ontology/",
    "YAGO3": "https://yago-knowledge.org/data/yago3/tmp/yagoSchema.ttl",
    "WARSAMPO": "https://github.com/SemanticComputing/Warsampo-schema/blob/master/warsampo-schema.ttl",
    "CIDOC": "https://cidoc-crm.org/rdfs/7.1.3/CIDOC_CRM_v7.1.3.rdfs",
    "SEM": "https://semanticweb.cs.vu.nl/2009/11/sem/",
    "DCTERMS": "https://www.dublincore.org/specifications/dublin-core/dcmi-terms/dublin_core_terms.rdf",
    "SKOS": "https://www.w3.org/2009/08/skos-reference/skos.rdf",
    "RDFS": "https://www.w3.org/2000/01/rdf-schema.rdf",
    "OWL": "https://www.w3.org/2002/07/owl.rdf",
    "MUNINN": "https://rdf.muninn-project.org/ontologies/organization",
    "SCHEMAORG": "https://schema.org/version/latest/schemaorg-current-https.jsonld",
    "GEOSPARQL": "https://www.ogc.org/standards/geosparql/",
    "EVENTKG": "https://github.com/sgottsch/eventkg/blob/master/README.md#manual-configuration",
}

EVENTKG_FILES = {
    "locations": "https://raw.githubusercontent.com/sgottsch/eventkg/master/src/resource/meta_data/wikidata/property_names_locations.tsv",
    "sublocations": "https://raw.githubusercontent.com/sgottsch/eventkg/master/src/resource/meta_data/wikidata/properties_sublocations.tsv",
    "dbpedia_part_of": "https://raw.githubusercontent.com/sgottsch/eventkg/master/src/resource/meta_data/dbpedia/part_of_properties.tsv",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def request_bytes(
    url: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
    attempts: int = 5,
) -> bytes:
    headers = {
        "User-Agent": "Corpus2GeoRAG-source-ontology-audit/1.0",
        "Accept": "application/json, application/rdf+xml, text/turtle;q=0.9, */*;q=0.1",
    }
    if content_type:
        headers["Content-Type"] = content_type
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, data=data, headers=headers), timeout=45
            ) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt + 1 == attempts:
                raise
            delay = int(error.headers.get("Retry-After", 0) or 0) or 2 ** attempt
            time.sleep(min(delay, 20))
        except (TimeoutError, urllib.error.URLError):
            if attempt + 1 == attempts:
                raise
            time.sleep(2**attempt)
    raise RuntimeError(f"Unable to read {url}")


def request_text(url: str) -> str:
    return request_bytes(url).decode("utf-8-sig")


def request_json(url: str, *, data: bytes | None = None) -> dict:
    content_type = "application/x-www-form-urlencoded" if data else None
    return json.loads(request_bytes(url, data=data, content_type=content_type))


def request_wikidata_json(url: str, attempts: int = 5) -> dict:
    for attempt in range(attempts):
        response = request_json(url)
        error = response.get("error")
        if not error:
            return response
        if error.get("code") != "maxlag" or attempt + 1 == attempts:
            raise RuntimeError(error)
        delay = max(float(error.get("lag", 0)), 2**attempt)
        time.sleep(min(delay, 20))
    raise RuntimeError("Wikidata maxlag retry limit reached")


def record(metadata: dict, uri: str) -> dict:
    return metadata.setdefault(
        uri,
        {"parents": {}, "domains": set(), "ranges": set(), "types": set()},
    )


def add_parent(
    metadata: dict,
    child: str,
    parent: str,
    basis: str,
    evidence_url: str,
    *,
    direction: str = "same",
    scope: str = "",
) -> None:
    if child and parent:
        record(metadata, child)["parents"][
            (parent, basis, evidence_url, direction, scope)
        ] = None


def add_schema_fact(metadata: dict, subject: str, predicate: str, obj: str) -> None:
    if not subject or not obj:
        return
    item = record(metadata, subject)
    if predicate == RDFS + "domain":
        item["domains"].add(obj)
    elif predicate == RDFS + "range":
        item["ranges"].add(obj)
    elif predicate == RDF + "type":
        item["types"].add(obj)


def expand_token(token: str, prefixes: dict[str, str], base: str = "") -> str:
    token = token.strip().rstrip(";,.")
    if token == "a":
        return RDF + "type"
    if token.startswith("<") and token.endswith(">"):
        value = token[1:-1]
        return value if "://" in value else base + value
    if ":" in token:
        prefix, local = token.split(":", 1)
        if prefix in prefixes:
            return prefixes[prefix] + local
    return ""


def parse_line_turtle(text: str, metadata: dict, evidence_url: str) -> None:
    prefixes: dict[str, str] = {}
    base = ""
    current_subject = ""
    for raw_line in text.splitlines():
        prefix_match = re.match(r"@prefix\s+([^:]*):\s*<([^>]+)>", raw_line.strip())
        if prefix_match:
            prefixes[prefix_match.group(1)] = prefix_match.group(2)
            continue
        base_match = re.match(r"@base\s+<([^>]+)>", raw_line.strip())
        if base_match:
            base = base_match.group(1)
            continue
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if not raw_line[0].isspace():
            current_subject = expand_token(raw_line.split()[0], prefixes, base)
        if not current_subject:
            continue
        for marker, predicate in (
            ("rdfs:subPropertyOf", RDFS + "subPropertyOf"),
            ("rdfs:domain", RDFS + "domain"),
            ("rdfs:range", RDFS + "range"),
        ):
            match = re.search(rf"(?:^|\s){re.escape(marker)}\s+([^\s;,]+)", raw_line)
            if not match:
                continue
            obj = expand_token(match.group(1), prefixes, base)
            if predicate == RDFS + "subPropertyOf":
                add_parent(metadata, current_subject, obj, "RDFS_SUBPROPERTY", evidence_url)
            else:
                add_schema_fact(metadata, current_subject, predicate, obj)


def parse_rdf_xml(data: bytes, metadata: dict, evidence_url: str) -> None:
    rdf_about = "{" + RDF + "}about"
    rdf_resource = "{" + RDF + "}resource"
    root = ET.fromstring(data)
    xml_base = root.attrib.get("{http://www.w3.org/XML/1998/namespace}base", evidence_url)

    def absolute(uri: str) -> str:
        return urllib.parse.urljoin(xml_base, uri) if uri else ""

    for element in root.iter():
        subject = absolute(element.attrib.get(rdf_about, ""))
        if not subject:
            continue
        for child in element:
            obj = absolute(child.attrib.get(rdf_resource, ""))
            if child.tag == "{" + RDFS + "}subPropertyOf":
                add_parent(metadata, subject, obj, "RDFS_SUBPROPERTY", evidence_url)
            elif child.tag == "{" + RDFS + "}domain":
                add_schema_fact(metadata, subject, RDFS + "domain", obj)
            elif child.tag == "{" + RDFS + "}range":
                add_schema_fact(metadata, subject, RDFS + "range", obj)
            elif child.tag == "{" + RDF + "}type":
                add_schema_fact(metadata, subject, RDF + "type", obj)


def wikidata_id(uri: str) -> str:
    match = re.search(r"(?:wd:|/)(P\d+)$", uri)
    return match.group(1) if match else ""


def fetch_wikidata(ids: set[str], metadata: dict) -> dict[str, str]:
    endpoint = "https://www.wikidata.org/w/api.php"
    labels: dict[str, str] = {}
    entities: dict[str, dict] = {}
    ordered = sorted(ids, key=lambda value: int(value[1:]))
    for offset in range(0, len(ordered), 45):
        batch = ordered[offset : offset + 45]
        query = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "claims|labels",
                "languages": "en",
                "format": "json",
                "formatversion": "2",
                "maxlag": "10",
            }
        )
        response = request_wikidata_json(endpoint + "?" + query)
        entities.update(response["entities"])
        time.sleep(1.1)
    if set(entities) != ids:
        missing = sorted(ids - set(entities))
        raise RuntimeError(f"Wikidata returned {len(entities)}/{len(ids)} properties; missing {missing[:10]}")

    parent_ids: set[str] = set()
    for property_id, entity in entities.items():
        uri = "http://www.wikidata.org/prop/direct/" + property_id
        labels[property_id] = entity.get("labels", {}).get("en", {}).get("value", "")
        for claim in entity.get("claims", {}).get("P1647", []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            parent_id = value.get("id", "") if isinstance(value, dict) else ""
            if parent_id:
                parent_ids.add(parent_id)
                add_parent(
                    metadata,
                    uri,
                    "http://www.wikidata.org/prop/direct/" + parent_id,
                    "WIKIDATA_P1647",
                    SOURCES["WIKIDATA"],
                )
        for claim in entity.get("claims", {}).get("P2235", []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", "")
            if isinstance(value, str) and value.startswith("http"):
                add_parent(
                    metadata,
                    uri,
                    value,
                    "WIKIDATA_P2235_EXTERNAL",
                    SOURCES["WIKIDATA"],
                )

    missing_parent_labels = parent_ids - set(labels)
    if missing_parent_labels:
        ordered_parents = sorted(missing_parent_labels, key=lambda value: int(value[1:]))
        for offset in range(0, len(ordered_parents), 45):
            batch = ordered_parents[offset : offset + 45]
            query = urllib.parse.urlencode(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "labels",
                    "languages": "en",
                    "format": "json",
                    "formatversion": "2",
                    "maxlag": "10",
                }
            )
            response = request_wikidata_json(endpoint + "?" + query)
            for property_id, entity in response["entities"].items():
                labels[property_id] = entity.get("labels", {}).get("en", {}).get("value", "")
            time.sleep(1.1)
    return labels


def fetch_dbpedia(uris: set[str], metadata: dict) -> None:
    endpoint = "https://dbpedia.org/sparql"
    ordered = sorted(uris)
    for offset in range(0, len(ordered), 45):
        batch = ordered[offset : offset + 45]
        values = " ".join(f"<{uri}>" for uri in batch)
        query = f"""
SELECT DISTINCT ?p ?parent ?domain ?range WHERE {{
  VALUES ?p {{ {values} }}
  OPTIONAL {{ ?p <{RDFS}subPropertyOf> ?parent }}
  OPTIONAL {{ ?p <{RDFS}domain> ?domain }}
  OPTIONAL {{ ?p <{RDFS}range> ?range }}
}}
"""
        payload = urllib.parse.urlencode(
            {"query": query, "format": "application/sparql-results+json"}
        ).encode()
        response = request_json(endpoint, data=payload)
        returned: set[str] = set()
        for binding in response["results"]["bindings"]:
            uri = binding["p"]["value"]
            returned.add(uri)
            record(metadata, uri)
            if "parent" in binding:
                add_parent(
                    metadata,
                    uri,
                    binding["parent"]["value"],
                    "RDFS_SUBPROPERTY",
                    SOURCES["DBPEDIA"],
                )
            if "domain" in binding:
                record(metadata, uri)["domains"].add(binding["domain"]["value"])
            if "range" in binding:
                record(metadata, uri)["ranges"].add(binding["range"]["value"])
        if returned != set(batch):
            raise RuntimeError(f"DBpedia returned {len(returned)}/{len(batch)} requested predicates")


def parse_schema_org(metadata: dict) -> None:
    graph = request_json(SOURCES["SCHEMAORG"]).get("@graph", [])
    for item in graph:
        subject = item.get("@id", "")
        if not subject:
            continue
        subject = subject.replace("schema:", SCHEMA)
        for key, target in (
            ("rdfs:subPropertyOf", "parent"),
            ("schema:domainIncludes", "domain"),
            ("schema:rangeIncludes", "range"),
        ):
            values = item.get(key, [])
            if not isinstance(values, list):
                values = [values]
            for value in values:
                obj = value.get("@id", "") if isinstance(value, dict) else ""
                obj = obj.replace("schema:", SCHEMA)
                if target == "parent":
                    add_parent(metadata, subject, obj, "RDFS_SUBPROPERTY", SOURCES["SCHEMAORG"])
                elif obj:
                    record(metadata, subject)[target + "s"].add(obj)


def load_eventkg_mappings(metadata: dict) -> None:
    for raw_line in request_text(EVENTKG_FILES["locations"]).splitlines():
        if not raw_line.strip() or raw_line.startswith("#"):
            continue
        property_id = raw_line.split("\t", 1)[0].strip()
        add_parent(
            metadata,
            "http://www.wikidata.org/prop/direct/" + property_id,
            SEM + "hasPlace",
            "EVENTKG_MANUAL_MAPPING",
            EVENTKG_FILES["locations"],
            scope="EventKG event or entity location normalization",
        )
    for raw_line in request_text(EVENTKG_FILES["sublocations"]).splitlines():
        if not raw_line.strip() or raw_line.startswith("#"):
            continue
        parts = raw_line.split("\t")
        property_id, orientation = parts[0].strip(), parts[-1].strip()
        add_parent(
            metadata,
            "http://www.wikidata.org/prop/direct/" + property_id,
            SCHEMA + "containedInPlace",
            "EVENTKG_MANUAL_MAPPING",
            EVENTKG_FILES["sublocations"],
            direction="same" if orientation == "s" else "reverse",
            scope="EventKG place containment normalization",
        )
    for raw_line in request_text(EVENTKG_FILES["dbpedia_part_of"]).splitlines():
        uri = raw_line.strip().strip("<>")
        if uri:
            add_parent(
                metadata,
                uri,
                SEM + "subEventOf",
                "EVENTKG_MANUAL_MAPPING",
                EVENTKG_FILES["dbpedia_part_of"],
                scope="Only when both endpoints are events",
            )


def ontology_key(uri: str) -> str:
    if "wikidata.org" in uri or uri.startswith("wd:"):
        return "Wikidata"
    if "dbpedia.org/ontology" in uri:
        return "DBpedia"
    if "yago-knowledge.org" in uri:
        return "YAGO 3"
    if "semanticweb.cs.vu.nl/2009/11/sem" in uri:
        return "SEM"
    if "cidoc-crm.org" in uri:
        return "CIDOC CRM 7.1.3"
    if "ldf.fi/schema/warsa" in uri:
        return "WarSampo"
    if "purl.org/dc/terms" in uri:
        return "DCMI Terms"
    if "skos/core" in uri:
        return "SKOS"
    if "rdf.muninn-project.org" in uri:
        return "Muninn Organization"
    if "opengis.net/ont/geosparql" in uri:
        return "GeoSPARQL"
    if "schema.org" in uri:
        return "Schema.org"
    if "w3.org/2000/01/rdf-schema" in uri:
        return "RDFS"
    if "w3.org/1999/02/22-rdf-syntax" in uri:
        return "RDF"
    if "w3.org/2002/07/owl" in uri:
        return "OWL"
    return "Other public vocabulary"


def default_evidence(uri: str) -> str:
    name = ontology_key(uri)
    return {
        "Wikidata": SOURCES["WIKIDATA"],
        "DBpedia": SOURCES["DBPEDIA"],
        "YAGO 3": SOURCES["YAGO3"],
        "SEM": SOURCES["SEM"],
        "CIDOC CRM 7.1.3": SOURCES["CIDOC"],
        "WarSampo": SOURCES["WARSAMPO"],
        "DCMI Terms": SOURCES["DCTERMS"],
        "SKOS": SOURCES["SKOS"],
        "Muninn Organization": SOURCES["MUNINN"],
        "GeoSPARQL": SOURCES["GEOSPARQL"],
        "Schema.org": SOURCES["SCHEMAORG"],
        "RDFS": SOURCES["RDFS"],
        "RDF": SOURCES["RDFS"],
        "OWL": SOURCES["OWL"],
    }.get(name, "")


def display_label(uri: str, wikidata_labels: dict[str, str]) -> str:
    property_id = wikidata_id(uri)
    if property_id and wikidata_labels.get(property_id):
        return wikidata_labels[property_id]
    local = re.split(r"[/#]", uri.rstrip("/#"))[-1]
    local = re.sub(r"^P\d+_", "", local).replace("_", " ")
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", local).strip()


def build_rows(
    inventory: list[dict[str, str]],
    metadata: dict,
    wikidata_labels: dict[str, str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_row in inventory:
        raw_uri = source_row["predicate_uri"]
        property_id = wikidata_id(raw_uri)
        uri = "http://www.wikidata.org/prop/direct/" + property_id if property_id else raw_uri
        item = metadata.get(uri, {"parents": {}, "domains": set(), "ranges": set(), "types": set()})
        parents = list(item["parents"])
        if source_row["source"] != "EventKG":
            parents = [parent for parent in parents if parent[1] != "EVENTKG_MANUAL_MAPPING"]
        shared = {
            "source": source_row["source"],
            "source_predicate": source_row["source_predicate"],
            "level2_uri": raw_uri,
            "normalized_level2_uri": uri,
            "level2_label": source_row["label"],
            "occurrence_count": source_row["occurrence_count"],
            "ontology": ontology_key(uri),
            "domain_uris": "|".join(sorted(item["domains"])),
            "range_uris": "|".join(sorted(item["ranges"])),
            "ontology_type_uris": "|".join(sorted(item["types"])),
            "direct_parent_count": str(len(parents)),
        }
        if not parents:
            rows.append(
                shared
                | {
                    "level1_uri": "",
                    "level1_label": "",
                    "mapping_basis": "",
                    "direction": "",
                    "scope": "",
                    "resolution_status": "NO_DECLARED_PARENT",
                    "evidence_url": default_evidence(uri),
                }
            )
            continue
        for parent, basis, evidence_url, direction, scope in sorted(parents):
            rows.append(
                shared
                | {
                    "level1_uri": parent,
                    "level1_label": display_label(parent, wikidata_labels),
                    "mapping_basis": basis,
                    "direction": direction,
                    "scope": scope,
                    "resolution_status": "DECLARED_PARENT",
                    "evidence_url": evidence_url,
                }
            )
    return rows


def make_statistics(inventory: list[dict[str, str]], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    statistics = []
    for source in sorted({row["source"] for row in inventory}):
        source_inventory = [row for row in inventory if row["source"] == source]
        source_rows = [row for row in rows if row["source"] == source]
        keys_with_parent = {
            row["level2_uri"]
            for row in source_rows
            if row["resolution_status"] == "DECLARED_PARENT"
        }
        keys_multi = {
            row["level2_uri"]
            for row in source_rows
            if int(row["direct_parent_count"]) > 1
        }
        statistics.append(
            {
                "source": source,
                "eligible_level2_rows": str(len(source_inventory)),
                "level2_with_declared_parent": str(len(keys_with_parent)),
                "level2_without_declared_parent": str(len(source_inventory) - len(keys_with_parent)),
                "level2_with_multiple_parents": str(len(keys_multi)),
                "declared_parent_edges": str(
                    sum(row["resolution_status"] == "DECLARED_PARENT" for row in source_rows)
                ),
                "coverage_pct": f"{100 * len(keys_with_parent) / len(source_inventory):.2f}",
            }
        )
    return statistics


def make_level1_statistics(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        if row["resolution_status"] == "DECLARED_PARENT":
            groups.setdefault((row["source"], row["level1_uri"]), []).append(row)

    statistics = []
    for (source, level1_uri), group in groups.items():
        statistics.append(
            {
                "source": source,
                "level1_uri": level1_uri,
                "level1_label": group[0]["level1_label"],
                "level2_count": str(len({row["level2_uri"] for row in group})),
                "total_level2_occurrences": str(
                    sum(int(row["occurrence_count"] or 0) for row in group)
                ),
                "mapping_bases": "|".join(sorted({row["mapping_basis"] for row in group})),
            }
        )
    return sorted(
        statistics,
        key=lambda row: (row["source"], -int(row["level2_count"]), row["level1_uri"]),
    )


def build(
    input_path: Path = INPUT,
    output_dir: Path = OUT,
    report_path: Path = REPORT,
) -> dict:
    inventory = [row for row in read_csv(input_path) if row["eligibility"] == "LEVEL2_CANDIDATE"]
    metadata: dict = {}

    wikidata_ids = {wikidata_id(row["predicate_uri"]) for row in inventory}
    wikidata_ids.discard("")
    wikidata_labels = fetch_wikidata(wikidata_ids, metadata)

    dbpedia_uris = {
        row["predicate_uri"]
        for row in inventory
        if row["predicate_uri"].startswith("http://dbpedia.org/ontology/")
    }
    fetch_dbpedia(dbpedia_uris, metadata)

    parse_line_turtle(request_text(SOURCES["YAGO3"]), metadata, SOURCES["YAGO3"])
    parse_line_turtle(WARSA_SCHEMA.read_text(encoding="utf-8"), metadata, SOURCES["WARSAMPO"])
    for key in ("CIDOC", "DCTERMS", "SKOS", "RDFS", "OWL", "MUNINN"):
        parse_rdf_xml(request_bytes(SOURCES[key]), metadata, SOURCES[key])
    parse_schema_org(metadata)

    for relation in ("hasActor", "hasPlace", "hasSubEvent", "subEventOf", "hasTime"):
        add_parent(metadata, SEM + relation, SEM + "eventProperty", "RDFS_SUBPROPERTY", SOURCES["SEM"])
    for relation in ("hasBeginTimeStamp", "hasEndTimeStamp"):
        add_parent(metadata, SEM + relation, SEM + "hasTimeStamp", "RDFS_SUBPROPERTY", SOURCES["SEM"])

    geo = "http://www.opengis.net/ont/geosparql#sfWithin"
    record(metadata, geo)["domains"].add("http://www.opengis.net/ont/geosparql#SpatialObject")
    record(metadata, geo)["ranges"].add("http://www.opengis.net/ont/geosparql#SpatialObject")
    load_eventkg_mappings(metadata)

    rows = build_rows(inventory, metadata, wikidata_labels)
    rows.sort(key=lambda row: (row["source"], row["level2_uri"], row["level1_uri"], row["mapping_basis"]))
    statistics = make_statistics(inventory, rows)
    level1_statistics = make_level1_statistics(rows)
    basis_counts = Counter(row["mapping_basis"] or "NO_DECLARED_PARENT" for row in rows)
    with_parent = {
        (row["source"], row["level2_uri"])
        for row in rows
        if row["resolution_status"] == "DECLARED_PARENT"
    }
    multiple = {
        (row["source"], row["level2_uri"])
        for row in rows
        if int(row["direct_parent_count"]) > 1
    }
    summary = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "eligible_source_level2_rows": len(inventory),
        "source_level2_with_declared_parent": len(with_parent),
        "source_level2_without_declared_parent": len(inventory) - len(with_parent),
        "source_level2_with_multiple_parents": len(multiple),
        "declared_parent_edges": sum(row["resolution_status"] == "DECLARED_PARENT" for row in rows),
        "unique_level1_parent_uris": len({row["level1_uri"] for row in level1_statistics}),
        "source_level1_options": len(level1_statistics),
        "mapping_basis_counts": dict(sorted(basis_counts.items())),
        "classifier_run": False,
        "source_data_modified": False,
    }
    write_csv(output_dir / "source_ontology_level1_level2.csv", rows)
    write_csv(output_dir / "source_ontology_statistics.csv", statistics)
    write_csv(output_dir / "level1_parent_statistics.csv", level1_statistics)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    stats_table = "\n".join(
        f"| {row['source']} | {row['eligible_level2_rows']} | {row['level2_with_declared_parent']} | "
        f"{row['level2_without_declared_parent']} | {row['level2_with_multiple_parents']} | "
        f"{row['coverage_pct']}% |"
        for row in statistics
    )
    basis_table = "\n".join(f"| {basis} | {count} |" for basis, count in sorted(basis_counts.items()))
    report = f"""# Source ontology Level 1 to Level 2 map

Date: 2026-10-11

## Result

This run uses only parent relations declared by the public source ontologies and
EventKG's published mapping files. It does not use the earlier project-made 14
families and it does not run a classifier.

The input contains **{len(inventory):,} source Level 2 rows**. Public ontology or
EventKG mapping evidence supplies at least one Level 1 parent for
**{len(with_parent):,} rows**. **{len(inventory) - len(with_parent):,} rows** have
no published parent in the checked ontology. **{len(multiple):,} rows** have more
than one valid direct parent; these parents remain separate.
The map contains **{len(level1_statistics):,} source-specific Level 1 options**
and **{summary['unique_level1_parent_uris']:,} unique Level 1 parent URIs**.

## Coverage by source

| Source | Level 2 rows | With parent | No parent | Multiple parents | Coverage |
|---|---:|---:|---:|---:|---:|
{stats_table}

## Evidence types

| Mapping basis | Output edges or unresolved rows |
|---|---:|
{basis_table}

## Interpretation

- `WIKIDATA_P1647` is Wikidata's native property hierarchy.
- `WIKIDATA_P2235_EXTERNAL` is an explicit Wikidata link to an external
  superproperty.
- `RDFS_SUBPROPERTY` is a parent declared in DBpedia, YAGO, SEM, WarSampo,
  CIDOC CRM, SKOS, DCMI, Schema.org, OWL, RDFS, or Muninn.
- `EVENTKG_MANUAL_MAPPING` is EventKG's published normalization rule. It is
  separate from a native `rdfs:subPropertyOf` assertion.
- `NO_DECLARED_PARENT` means that the checked public model gives domain/range
  information at most. No Level 1 meaning was invented from the field name.

## Files

- `source_ontology_level1_level2.csv`: one row per declared parent edge, or one
  unresolved row when no parent exists.
- `source_ontology_statistics.csv`: coverage by source.
- `level1_parent_statistics.csv`: each Level 1 option and its Level 2 count.
- `summary.json`: machine-readable totals.

## Next gate

Review this EDA before any classifier is used. The classifier should see only
the `NO_DECLARED_PARENT` population. It must not replace or merge declared
source parents.
"""
    report_path.write_text(report, encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
