"""Build and audit a deterministic Level 2 relation mapping registry.

Only explicit identifiers and source-declared mapping statements can change a
Level 2 identifier or its direction. Labels, descriptions, and observations are
written as validation evidence. They never create a mapping.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph, Literal, RDF, RDFS, URIRef
from rdflib.namespace import OWL

HERE = Path(__file__).resolve().parent
INVENTORY = HERE / "relation_catalog_eda" / "source_predicate_inventory.csv"
CURRENT_MAP = HERE / "final_relation_map" / "final_relation_source_map.csv"
GRAPH = (
    HERE.parent.parent
    / "GG_Data"
    / "agent_export"
    / "outputs"
    / "wwii_agent_graph_draft_v0.1.0.json"
)
WARSA_SCHEMA = (
    HERE.parent.parent
    / "Data"
    / "external"
    / "warsampo"
    / "full"
    / "Warsampo-schema"
    / "warsampo-schema.ttl"
)
WARSA_MANIFEST = HERE.parent.parent / "Data" / "external" / "warsampo" / "manifest.json"
OUT = HERE / "deterministic_level2_mapping"

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
DBPEDIA_SPARQL = "https://dbpedia.org/sparql"
CIDOC_OWL = "https://cidoc-crm.org/owl/7.1.3/CIDOC_CRM_v7.1.3.owl"
EVENTKG_REPO = "https://github.com/sgottsch/eventkg"
EVENTKG_COMMIT = "0face5765ffc3e16a8746f9ed98877dc86de2bef"
EVENTKG_RAW = f"https://raw.githubusercontent.com/sgottsch/eventkg/{EVENTKG_COMMIT}"
EVENTKG_FILES = {
    "locations": (
        EVENTKG_RAW + "/src/resource/meta_data/wikidata/property_names_locations.tsv"
    ),
    "sublocations": (
        EVENTKG_RAW + "/src/resource/meta_data/wikidata/properties_sublocations.tsv"
    ),
    "dbpedia_part_of": (
        EVENTKG_RAW + "/src/resource/meta_data/dbpedia/part_of_properties.tsv"
    ),
}

WD_CLAIM_TO_RELATION = {
    "P1628": "EQUIVALENT",
    "P1696": "INVERSE",
    "P1647": "SUBPROPERTY_OF",
    "P2235": "SUBPROPERTY_OF_EXTERNAL_SUPERPROPERTY",
    "P2236": "SUPERPROPERTY_OF_EXTERNAL_SUBPROPERTY",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def request_bytes(url: str, *, attempts: int = 4) -> bytes:
    headers = {
        "User-Agent": "Corpus2GeoRAG-deterministic-relation-audit/1.0",
        "Accept": "application/json, application/rdf+xml, text/turtle, */*;q=0.1",
    }
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=75) as response:
                return response.read()
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(2**attempt)
    raise RuntimeError(f"Could not fetch {url}")


def request_json(url: str) -> dict:
    return json.loads(request_bytes(url))


def request_wikidata_json(url: str, *, attempts: int = 6) -> dict:
    for attempt in range(attempts):
        payload = request_json(url)
        error = payload.get("error")
        if not error:
            return payload
        if error.get("code") != "maxlag" or attempt + 1 == attempts:
            raise RuntimeError(error)
        time.sleep(min(max(float(error.get("lag", 0)), 2**attempt), 20))
    raise RuntimeError("Wikidata maxlag retry limit reached")


def sparql(query: str) -> list[dict[str, dict[str, str]]]:
    url = (
        DBPEDIA_SPARQL
        + "?"
        + urllib.parse.urlencode(
            {"query": query, "format": "application/sparql-results+json"}
        )
    )
    return request_json(url)["results"]["bindings"]


def normalize_uri(value: str) -> str:
    value = value.strip().strip("<>")
    if re.fullmatch(r"P\d+", value):
        return "wd:" + value
    match = re.search(r"(?:wd:|wikidata\.org/(?:entity|prop/direct)/)(P\d+)$", value)
    if match:
        return "wd:" + match.group(1)
    value = value.replace("https://schema.org/", "http://schema.org/")
    value = value.replace(
        "https://dbpedia.org/ontology/", "http://dbpedia.org/ontology/"
    )
    value = value.replace(
        "https://d-nb.info/standards/elementset/gnd#",
        "http://d-nb.info/standards/elementset/gnd#",
    )
    value = value.replace(
        "http://cidoc-crm.org/cidoc-crm/", "http://www.cidoc-crm.org/cidoc-crm/"
    )
    return value


def wd_id(value: str) -> str:
    normalized = normalize_uri(value)
    return normalized[3:] if normalized.startswith("wd:P") else ""


def clean_text(value: str) -> str:
    return " ".join(value.split())


def english_literal(values: list[Literal]) -> str:
    english = [clean_text(str(value)) for value in values if value.language == "en"]
    plain = [clean_text(str(value)) for value in values if not value.language]
    return (english or plain or [""])[0]


def evidence_row(
    left: str,
    right: str,
    relation: str,
    source: str,
    evidence_url: str,
    source_version: str,
    statement_id: str = "",
    note: str = "",
    declared_direction: str = "",
) -> dict[str, str]:
    normalized_left = normalize_uri(left)
    normalized_right = normalize_uri(right)
    if relation == "INVERSE" and normalized_left == normalized_right:
        relation = "SYMMETRIC"
    action = {
        "EQUIVALENT": "MERGE_SAME_DIRECTION",
        "INVERSE": "MERGE_REVERSE_DIRECTION",
        "SUBPROPERTY_OF": "KEEP_SEPARATE_CHILD_TO_PARENT",
        "SUBPROPERTY_OF_EXTERNAL_SUPERPROPERTY": "KEEP_SEPARATE_CHILD_TO_PARENT",
        "SUPERPROPERTY_OF_EXTERNAL_SUBPROPERTY": "KEEP_SEPARATE_PARENT_TO_CHILD",
        "SYMMETRIC": "ALLOW_REVERSE_TRAVERSAL_SAME_RELATION",
        "EVENTKG_NORMALIZES_TO": "KEEP_SOURCE_LEVEL2_AND_ADD_BROADER_VIEW",
    }[relation]
    return {
        "left_relation": normalized_left,
        "right_relation": normalized_right,
        "formal_relation": relation,
        "deterministic_action": action,
        "declared_direction": declared_direction
        or ("reverse" if relation == "INVERSE" else "same"),
        "evidence_source": source,
        "evidence_url": evidence_url,
        "source_version": source_version,
        "statement_id": statement_id,
        "note": note,
    }


def load_wikidata(
    property_ids: set[str],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]], dict[str, str]]:
    evidence: list[dict[str, str]] = []
    metadata: dict[str, dict[str, str]] = {}
    revisions: dict[str, str] = {}
    cache_path = OUT / "wikidata_mapping_source_cache.json"
    cached_entities: dict[str, dict] = {}
    if cache_path.exists():
        cached_entities = json.loads(cache_path.read_text(encoding="utf-8")).get(
            "entities", {}
        )
    ordered = sorted(property_ids, key=lambda value: int(value[1:]))
    for offset in range(0, len(ordered), 30):
        batch = [
            value
            for value in ordered[offset : offset + 30]
            if value not in cached_entities
        ]
        if not batch:
            continue
        url = (
            WIKIDATA_API
            + "?"
            + urllib.parse.urlencode(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "claims|labels|descriptions",
                    "languages": "en",
                    "format": "json",
                    "formatversion": "2",
                    "maxlag": "30",
                }
            )
        )
        payload = request_wikidata_json(url)
        cached_entities.update(payload["entities"])
        OUT.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "entities": cached_entities,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        time.sleep(2.0)
    missing = property_ids - set(cached_entities)
    if missing:
        raise RuntimeError(f"Wikidata source cache missing {sorted(missing)[:10]}")
    for property_id in ordered:
        entity = cached_entities[property_id]
        uri = "wd:" + property_id
        metadata[uri] = {
            "label": entity.get("labels", {}).get("en", {}).get("value", ""),
            "description": entity.get("descriptions", {})
            .get("en", {})
            .get("value", ""),
        }
        revisions[property_id] = str(entity.get("lastrevid", ""))
        for claim_id, formal_relation in WD_CLAIM_TO_RELATION.items():
            for claim in entity.get("claims", {}).get(claim_id, []):
                if claim.get("rank") == "deprecated":
                    continue
                value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(value, dict):
                    target = value.get("id", "")
                    target = "wd:" + target if target else ""
                else:
                    target = value if isinstance(value, str) else ""
                if not target:
                    continue
                evidence.append(
                    evidence_row(
                        uri,
                        target,
                        formal_relation,
                        "Wikidata",
                        f"https://www.wikidata.org/wiki/Property:{property_id}",
                        (
                            "live property revision " + revisions[property_id]
                            if revisions[property_id]
                            else "live property entity"
                        ),
                        claim.get("id", ""),
                        f"Wikidata {claim_id}",
                    )
                )
    return evidence, metadata, revisions


def load_dbpedia(
    uris: set[str],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    evidence: list[dict[str, str]] = []
    metadata: dict[str, dict[str, str]] = defaultdict(dict)
    predicates = {
        str(OWL.equivalentProperty): "EQUIVALENT",
        str(OWL.inverseOf): "INVERSE",
        str(RDFS.subPropertyOf): "SUBPROPERTY_OF",
    }
    pending = set(uris)
    queried: set[str] = set()
    for _ in range(4):
        frontier = sorted(pending - queried)
        if not frontier:
            break
        queried.update(frontier)
        for offset in range(0, len(frontier), 80):
            batch = frontier[offset : offset + 80]
            values = " ".join(f"<{uri}>" for uri in batch)
            query = f"""
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?p ?kind ?target WHERE {{
  VALUES ?p {{ {values} }}
  VALUES ?kind {{ owl:equivalentProperty owl:inverseOf rdfs:subPropertyOf }}
  ?p ?kind ?target . FILTER(isIRI(?target))
}}
"""
            for row in sparql(query):
                item = evidence_row(
                    row["p"]["value"],
                    row["target"]["value"],
                    predicates[row["kind"]["value"]],
                    "DBpedia Ontology",
                    row["p"]["value"],
                    "DBpedia endpoint latest-snapshot",
                )
                evidence.append(item)
                target = item["right_relation"]
                if target.startswith("http://dbpedia.org/ontology/"):
                    pending.add(target)

    ordered = sorted(queried)
    for offset in range(0, len(ordered), 80):
        batch = ordered[offset : offset + 80]
        values = " ".join(f"<{uri}>" for uri in batch)
        metadata_query = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?p ?kind ?value WHERE {{
  VALUES ?p {{ {values} }}
  VALUES ?kind {{ rdfs:label rdfs:comment }}
  ?p ?kind ?value . FILTER(lang(?value) = 'en' || lang(?value) = '')
}}
"""
        for row in sparql(metadata_query):
            field = (
                "label" if row["kind"]["value"] == str(RDFS.label) else "description"
            )
            metadata[normalize_uri(row["p"]["value"])].setdefault(
                field, clean_text(row["value"]["value"])
            )
    return evidence, dict(metadata)


def graph_evidence(
    graph: Graph,
    source: str,
    evidence_url: str,
    source_version: str,
    relevant_subjects: set[str],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    evidence: list[dict[str, str]] = []
    metadata: dict[str, dict[str, str]] = {}
    relations = {
        OWL.equivalentProperty: "EQUIVALENT",
        OWL.inverseOf: "INVERSE",
        RDFS.subPropertyOf: "SUBPROPERTY_OF",
    }
    for subject_text in sorted(relevant_subjects):
        subject = URIRef(subject_text)
        labels = list(graph.objects(subject, RDFS.label))
        comments = list(graph.objects(subject, RDFS.comment))
        if labels or comments:
            metadata[normalize_uri(subject_text)] = {
                "label": english_literal(labels),
                "description": english_literal(comments),
            }
        for predicate, formal_relation in relations.items():
            for target in graph.objects(subject, predicate):
                if isinstance(target, URIRef):
                    evidence.append(
                        evidence_row(
                            subject_text,
                            str(target),
                            formal_relation,
                            source,
                            evidence_url,
                            source_version,
                        )
                    )
        if (subject, RDF.type, OWL.SymmetricProperty) in graph:
            evidence.append(
                evidence_row(
                    subject_text,
                    subject_text,
                    "SYMMETRIC",
                    source,
                    evidence_url,
                    source_version,
                )
            )
    return evidence, metadata


def load_cidoc(
    relevant_subjects: set[str],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]], str]:
    data = request_bytes(CIDOC_OWL)
    graph = Graph()
    graph.parse(source=io.BytesIO(data), format="xml")
    evidence, metadata = graph_evidence(
        graph,
        "CIDOC CRM",
        CIDOC_OWL,
        "7.1.3",
        relevant_subjects,
    )
    return evidence, metadata, hashlib.sha256(data).hexdigest()


def load_warsampo(
    relevant_subjects: set[str],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]], dict]:
    manifest = json.loads(WARSA_MANIFEST.read_text(encoding="utf-8"))
    graph = Graph()
    graph.parse(WARSA_SCHEMA, format="turtle")
    evidence, metadata = graph_evidence(
        graph,
        "WarSampo schema",
        manifest["source"],
        manifest["version"],
        relevant_subjects,
    )
    return evidence, metadata, manifest


def load_eventkg() -> tuple[list[dict[str, str]], dict[str, str]]:
    evidence: list[dict[str, str]] = []
    hashes: dict[str, str] = {}
    for key, url in EVENTKG_FILES.items():
        data = request_bytes(url)
        hashes[key] = hashlib.sha256(data).hexdigest()
        lines = data.decode("utf-8-sig").splitlines()
        for line in lines:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t")
            if key == "locations":
                source_uri = "wd:" + parts[0].strip()
                target_uri = "http://semanticweb.cs.vu.nl/2009/11/sem/hasPlace"
                note = "EventKG location normalization; broader than most source properties"
                declared_direction = "same"
            elif key == "sublocations":
                source_uri = "wd:" + parts[0].strip()
                target_uri = "http://schema.org/containedInPlace"
                note = (
                    "EventKG containment normalization; same direction"
                    if parts[-1].strip() == "s"
                    else "EventKG containment normalization; reverse direction"
                )
                declared_direction = "same" if parts[-1].strip() == "s" else "reverse"
            else:
                source_uri = parts[0].strip().strip("<>")
                target_uri = "http://semanticweb.cs.vu.nl/2009/11/sem/subEventOf"
                note = "EventKG maps this property only when both endpoints are events"
                declared_direction = "same"
            evidence.append(
                evidence_row(
                    source_uri,
                    target_uri,
                    "EVENTKG_NORMALIZES_TO",
                    "EventKG manual configuration",
                    url,
                    EVENTKG_COMMIT,
                    note=note,
                    declared_direction=declared_direction,
                )
            )
    return evidence, hashes


class ParityDsu:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self.parity: dict[str, int] = {}
        self.conflicts: set[str] = set()

    def add(self, value: str) -> None:
        if value not in self.parent:
            self.parent[value] = value
            self.parity[value] = 0

    def find(self, value: str) -> tuple[str, int]:
        self.add(value)
        parent = self.parent[value]
        if parent != value:
            root, parent_parity = self.find(parent)
            self.parity[value] ^= parent_parity
            self.parent[value] = root
        return self.parent[value], self.parity[value]

    def union(self, left: str, right: str, expected_parity: int) -> None:
        left_root, left_parity = self.find(left)
        right_root, right_parity = self.find(right)
        if left_root == right_root:
            if left_parity ^ right_parity != expected_parity:
                self.conflicts.add(left_root)
            return
        self.parent[right_root] = left_root
        self.parity[right_root] = left_parity ^ right_parity ^ expected_parity
        if right_root in self.conflicts:
            self.conflicts.add(left_root)


def shortest_path(
    adjacency: dict[str, list[tuple[str, int, int]]], left: str, right: str
) -> list[int]:
    queue = deque([(left, [])])
    visited = {left}
    while queue:
        node, path = queue.popleft()
        if node == right:
            return path
        for neighbor, _, evidence_index in adjacency.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [evidence_index]))
    return []


def build_connections(
    inventory: list[dict[str, str]], evidence: list[dict[str, str]]
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    dsu = ParityDsu()
    adjacency: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for index, row in enumerate(evidence):
        if row["formal_relation"] not in {"EQUIVALENT", "INVERSE"}:
            continue
        parity = 1 if row["formal_relation"] == "INVERSE" else 0
        left, right = row["left_relation"], row["right_relation"]
        dsu.union(left, right, parity)
        adjacency[left].append((right, parity, index))
        adjacency[right].append((left, parity, index))

    observed: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in inventory:
        observed[normalize_uri(row["predicate_uri"])].append(row)

    components: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for uri in sorted(set(dsu.parent) | set(observed)):
        root, parity = dsu.find(uri)
        components[root].append((uri, parity))

    component_info: dict[str, dict[str, object]] = {}
    for root in sorted(components):
        members = sorted(components[root])
        wd_members = sorted(
            ((uri, parity) for uri, parity in members if uri.startswith("wd:P")),
            key=lambda item: int(item[0][4:]),
        )
        canonical, canonical_parity = wd_members[0] if wd_members else min(members)
        same_direction_wd = defaultdict(list)
        for uri, parity in wd_members:
            same_direction_wd[parity ^ canonical_parity].append(uri)
        semantic_conflict = any(
            len(values) > 1 for values in same_direction_wd.values()
        )
        component_info[root] = {
            "canonical": canonical,
            "canonical_parity": canonical_parity,
            "logical_conflict": root in dsu.conflicts,
            "multiple_same_direction_wikidata_ids": semantic_conflict,
            "members": members,
        }

    connections: list[dict[str, object]] = []
    for root in sorted(component_info):
        info = component_info[root]
        observed_members = [
            (uri, parity, source_row)
            for uri, parity in info["members"]
            for source_row in observed.get(uri, [])
        ]
        for left_index, (left_uri, left_parity, left_row) in enumerate(
            observed_members
        ):
            for right_uri, right_parity, right_row in observed_members[
                left_index + 1 :
            ]:
                if left_row["source"] == right_row["source"] and left_uri == right_uri:
                    continue
                path = (
                    shortest_path(adjacency, left_uri, right_uri)
                    if left_uri != right_uri
                    else []
                )
                evidence_sources = sorted(
                    {evidence[index]["evidence_source"] for index in path}
                )
                evidence_urls = sorted(
                    {evidence[index]["evidence_url"] for index in path}
                )
                connections.append(
                    {
                        "connection_id": hashlib.sha1(
                            (
                                left_row["source"]
                                + "|"
                                + left_uri
                                + "|"
                                + right_row["source"]
                                + "|"
                                + right_uri
                            ).encode()
                        ).hexdigest()[:12],
                        "left_source": left_row["source"],
                        "left_relation": left_uri,
                        "left_label": left_row["label"],
                        "left_description": left_row["description"],
                        "right_source": right_row["source"],
                        "right_relation": right_uri,
                        "right_label": right_row["label"],
                        "right_description": right_row["description"],
                        "direction": (
                            "reverse" if left_parity ^ right_parity else "same"
                        ),
                        "deterministic_basis": (
                            "IDENTICAL_NORMALIZED_IDENTIFIER"
                            if left_uri == right_uri
                            else "FORMAL_EQUIVALENCE_OR_INVERSE_PATH"
                        ),
                        "formal_path": " | ".join(
                            f"{evidence[index]['left_relation']} {evidence[index]['formal_relation']} {evidence[index]['right_relation']}"
                            for index in path
                        ),
                        "evidence_sources": "|".join(evidence_sources),
                        "evidence_urls": "|".join(evidence_urls),
                        "canonical_level2": info["canonical"],
                        "formal_component_conflict": bool(
                            info["logical_conflict"]
                            or info["multiple_same_direction_wikidata_ids"]
                        ),
                    }
                )
    return connections, component_info


def build_separation_evidence(
    inventory: list[dict[str, str]],
    evidence: list[dict[str, str]],
    dsu: ParityDsu,
) -> list[dict[str, object]]:
    """Return formal broader/narrower evidence that must not merge Level 2 IDs."""
    observed: dict[str, dict[str, str]] = {}
    for row in inventory:
        uri = normalize_uri(row["predicate_uri"])
        observed.setdefault(uri, row)

    selected: dict[tuple[str, str, str, str], tuple[int, dict[str, object]]] = {}
    for item in evidence:
        relation = item["formal_relation"]
        if relation not in {
            "SUBPROPERTY_OF",
            "SUBPROPERTY_OF_EXTERNAL_SUPERPROPERTY",
            "SUPERPROPERTY_OF_EXTERNAL_SUBPROPERTY",
            "EVENTKG_NORMALIZES_TO",
        }:
            continue
        left = item["left_relation"]
        right = item["right_relation"]
        if relation == "SUPERPROPERTY_OF_EXTERNAL_SUBPROPERTY":
            child, parent = right, left
        else:
            child, parent = left, right
        child_root, child_parity = dsu.find(child)
        parent_root, parent_parity = dsu.find(parent)
        observed_children = [uri for uri in observed if dsu.find(uri)[0] == child_root]
        observed_parents = [uri for uri in observed if dsu.find(uri)[0] == parent_root]
        if not observed_children:
            observed_children = [child]
        if not observed_parents:
            observed_parents = [parent]
        for observed_child in observed_children:
            for observed_parent in observed_parents:
                if observed_child == observed_parent:
                    continue
                key = (
                    observed_child,
                    observed_parent,
                    relation,
                    item["evidence_url"],
                )
                child_meta = observed.get(observed_child, {})
                parent_meta = observed.get(observed_parent, {})
                observed_child_parity = dsu.find(observed_child)[1]
                observed_parent_parity = dsu.find(observed_parent)[1]
                reverse = (
                    (item["declared_direction"] == "reverse")
                    ^ child_parity
                    ^ observed_child_parity
                    ^ parent_parity
                    ^ observed_parent_parity
                )
                output_row: dict[str, object] = {
                    "child_relation": observed_child,
                    "child_label": child_meta.get("label", ""),
                    "parent_or_view_relation": observed_parent,
                    "parent_or_view_label": parent_meta.get("label", ""),
                    "formal_relation": relation,
                    "effective_direction": "reverse" if reverse else "same",
                    "source_evidence_left": item["left_relation"],
                    "source_evidence_right": item["right_relation"],
                    "source_statement_direction": item["declared_direction"],
                    "deterministic_action": item["deterministic_action"],
                    "evidence_source": item["evidence_source"],
                    "evidence_url": item["evidence_url"],
                    "source_version": item["source_version"],
                    "statement_id": item["statement_id"],
                    "note": item["note"],
                }
                directness = int(observed_child != child) + int(
                    observed_parent != parent
                )
                previous = selected.get(key)
                if previous is None or directness < previous[0]:
                    selected[key] = (directness, output_row)
    rows = [row for _, row in selected.values()]
    return sorted(
        rows,
        key=lambda row: (
            str(row["child_relation"]),
            str(row["parent_or_view_relation"]),
            str(row["formal_relation"]),
        ),
    )


def relation_pair(left: str, right: str) -> frozenset[str]:
    return frozenset((left, right))


SEMANTIC_CONTRADICTIONS = {
    relation_pair("wd:P710", "wd:P1923"): (
        "participant includes people and organizations; participating team is limited to teams"
    ),
    relation_pair("wd:P800", "wd:P3342"): (
        "a notable work is a work; a significant person is a person"
    ),
    relation_pair("wd:P170", "wd:P3342"): (
        "creator and significant person are different roles"
    ),
    relation_pair(
        "http://dbpedia.org/ontology/creator", "wd:P3342"
    ): "creator and significant person are different roles",
    relation_pair(
        "http://dbpedia.org/ontology/notableWork", "wd:P3342"
    ): "a notable work is a work; a significant person is a person",
    relation_pair("wd:P8744", "wd:P2633"): "economy and geography are different facets",
    relation_pair("wd:P8744", "wd:P9241"): (
        "economy and demographics are different facets"
    ),
    relation_pair("wd:P8744", "wd:P2184"): "economy and history are different facets",
    relation_pair("wd:P2633", "wd:P9241"): (
        "geography and demographics are different facets"
    ),
    relation_pair("wd:P2633", "wd:P2184"): "geography and history are different facets",
    relation_pair("wd:P9241", "wd:P2184"): (
        "demographics and history are different facets"
    ),
    relation_pair("wd:P195", "wd:P1056"): (
        "collection membership and product produced are different relations"
    ),
    relation_pair("wd:P195", "wd:P176"): (
        "collection membership and manufacturer are different relations"
    ),
    relation_pair("wd:P195", "http://dbpedia.org/ontology/builder"): (
        "collection membership and builder are different relations"
    ),
    relation_pair("wd:P195", "http://dbpedia.org/ontology/manufacturer"): (
        "collection membership and manufacturer are different relations"
    ),
    relation_pair("wd:P463", "wd:P53"): (
        "membership in an organization and family membership are different relations"
    ),
    relation_pair("wd:P512", "http://dbpedia.org/ontology/profession"): (
        "an academic degree and a profession are different values"
    ),
    relation_pair(
        "http://dbpedia.org/ontology/district", "http://dbpedia.org/ontology/province"
    ): "district and province impose different place classes",
    relation_pair(
        "http://dbpedia.org/ontology/district", "http://dbpedia.org/ontology/city"
    ): "district and city impose different place classes",
    relation_pair(
        "http://dbpedia.org/ontology/province", "http://dbpedia.org/ontology/city"
    ): "province and city impose different place classes",
}

SEMANTIC_PARTIAL_SCOPE = {
    relation_pair("wd:P1344", "wd:P1923"): (
        "participating team is narrower than participant in"
    ),
    relation_pair("wd:P170", "wd:P800"): (
        "notable work is narrower than the full set of works made by a creator"
    ),
    relation_pair("wd:P170", "http://dbpedia.org/ontology/notableWork"): (
        "notable work is narrower than the full set of works made by a creator"
    ),
    relation_pair("wd:P800", "http://dbpedia.org/ontology/creator"): (
        "notable work is narrower than the full set of works made by a creator"
    ),
    relation_pair(
        "http://dbpedia.org/ontology/notableWork",
        "http://dbpedia.org/ontology/creator",
    ): "notable work is narrower than the full set of works made by a creator",
    relation_pair("wd:P8744", "wd:P1269"): "economy is one possible facet",
    relation_pair("wd:P2633", "wd:P1269"): "geography is one possible facet",
    relation_pair("wd:P9241", "wd:P1269"): "demographics is one possible facet",
    relation_pair("wd:P2184", "wd:P1269"): "history is one possible facet",
    relation_pair("wd:P286", "http://dbpedia.org/ontology/manager"): (
        "manager can be broader than head coach"
    ),
    relation_pair("wd:P407", "http://dbpedia.org/ontology/language"): (
        "the Wikidata relation is limited to a work or name"
    ),
    relation_pair("http://dbpedia.org/ontology/militaryBranch", "wd:P7779"): (
        "military branch and military unit are not exact synonyms"
    ),
    relation_pair("wd:P27", "http://dbpedia.org/ontology/nationality"): (
        "citizenship and nationality can differ"
    ),
    relation_pair(
        "http://dbpedia.org/ontology/nationality",
        "http://dbpedia.org/ontology/citizenship",
    ): "citizenship and nationality can differ",
    relation_pair("http://dbpedia.org/ontology/primeMinister", "wd:P6"): (
        "prime minister is a subtype of head of government"
    ),
    relation_pair("wd:P2348", "http://dbpedia.org/ontology/era"): (
        "era is narrower than the general time-period relation"
    ),
    relation_pair("wd:P607", "http://dbpedia.org/ontology/battle"): (
        "battle is narrower than conflict"
    ),
    relation_pair("http://dbpedia.org/ontology/artist", "wd:P175"): (
        "artist can be broader than performer"
    ),
}

ADMIN_SCOPE_RELATIONS = {
    "http://dbpedia.org/ontology/locatedInArea",
    "http://dbpedia.org/ontology/district",
    "http://dbpedia.org/ontology/province",
    "http://dbpedia.org/ontology/city",
    "wd:P131",
    "wd:P150",
}

EXAMPLE_CONTRADICTION_RELATIONS = {
    "http://dbpedia.org/ontology/genre": (
        "sampled people point to World War II as a genre"
    ),
    "http://dbpedia.org/ontology/language": (
        "sampled works point to countries or regimes instead of languages"
    ),
    "http://dbpedia.org/ontology/discipline": (
        "sampled people point to organizations or World War II as a discipline"
    ),
    "http://dbpedia.org/ontology/profession": (
        "sampled people point to organizations instead of professions"
    ),
}

FORMAL_COMPONENT_NOTES = {
    "wd:P710": (
        "P1344 declares both P710 and narrower P1923 as inverse, which makes P710 and P1923 equivalent by transitivity."
    ),
    "wd:P170": (
        "P170 declares both P800 and P3342 as inverse, although notable work and significant person are different relations."
    ),
    "wd:P1269": (
        "Several distinct topic facets declare P1269 as inverse, which would merge economy, geography, demographics, and history."
    ),
    "wd:P725": (
        "DBpedia voice links to P990 while Wikidata P725 links to the same DBpedia relation."
    ),
    "wd:P176": (
        "P176 and P195 both declare schema.org/provider as equivalent, which would merge manufacturer and collection."
    ),
    "wd:P53": (
        "P463 and P53 both declare vCard org as equivalent, which would merge organization membership and family."
    ),
}


def semantic_name_review(row: dict[str, object]) -> tuple[str, str]:
    left = str(row["left_relation"])
    right = str(row["right_relation"])
    if left == right:
        return "AGREES_SAME_IDENTIFIER", "The normalized relation identifier is equal."
    pair = relation_pair(left, right)
    if pair in SEMANTIC_CONTRADICTIONS:
        return "CONTRADICTS_EXACT_TRANSLATION", SEMANTIC_CONTRADICTIONS[pair]
    if pair in SEMANTIC_PARTIAL_SCOPE:
        return "PARTIAL_SCOPE_NOT_EXACT", SEMANTIC_PARTIAL_SCOPE[pair]
    if left in ADMIN_SCOPE_RELATIONS and right in ADMIN_SCOPE_RELATIONS:
        return (
            "PARTIAL_SCOPE_NOT_EXACT",
            "the labels encode different administrative place scopes",
        )
    if bool(row["formal_component_conflict"]):
        return (
            "AGREES_PAIR_BUT_COMPONENT_CONFLICT",
            "this pair is plausible, but another formal statement makes its full component unsafe",
        )
    return (
        "NO_NAME_DESCRIPTION_CONTRADICTION_FOUND",
        "The available English names and descriptions do not contradict the declared mapping.",
    )


def example_semantic_review(
    row: dict[str, object], examples: list[dict[str, object]]
) -> tuple[str, str]:
    if not examples:
        return "NO_EXAMPLES", "No graph assertion was available for this connection."
    relation_notes = {
        EXAMPLE_CONTRADICTION_RELATIONS[relation]
        for relation in (str(row["left_relation"]), str(row["right_relation"]))
        if relation in EXAMPLE_CONTRADICTION_RELATIONS
    }
    pair = relation_pair(str(row["left_relation"]), str(row["right_relation"]))
    if pair in {
        relation_pair("wd:P463", "wd:P53"),
        relation_pair("wd:P195", "wd:P1056"),
        relation_pair("wd:P195", "wd:P176"),
        relation_pair("wd:P195", "http://dbpedia.org/ontology/builder"),
        relation_pair("wd:P195", "http://dbpedia.org/ontology/manufacturer"),
    }:
        relation_notes.add(SEMANTIC_CONTRADICTIONS[pair])
    if relation_notes:
        return "CONTRADICTION_IN_SAMPLED_VALUES", "; ".join(sorted(relation_notes))
    counterpart_count = sum(
        str(example["expected_counterpart_pair_present"]) == "True"
        or example["expected_counterpart_pair_present"] is True
        for example in examples
    )
    if counterpart_count:
        return (
            "AGREEMENT_OBSERVED",
            f"{counterpart_count} of {len(examples)} sampled assertions have the expected counterpart pair.",
        )
    return (
        "NO_COUNTERPART_CONFIRMATION",
        "The endpoint names do not prove a contradiction, but no sampled pair occurs under both relations.",
    )


def relation_records(
    inventory: list[dict[str, str]],
    component_info: dict[str, dict[str, object]],
    dsu: ParityDsu,
) -> list[dict[str, object]]:
    output = []
    for row in inventory:
        uri = normalize_uri(row["predicate_uri"])
        root, parity = dsu.find(uri)
        info = component_info[root]
        canonical_parity = int(info["canonical_parity"])
        output.append(
            {
                "source": row["source"],
                "source_predicate": row["source_predicate"],
                "normalized_relation": uri,
                "label": row["label"],
                "description": row["description"],
                "occurrence_count": row["occurrence_count"],
                "deterministic_level2": info["canonical"],
                "direction_to_level2": (
                    "reverse" if parity ^ canonical_parity else "same"
                ),
                "mapping_basis": (
                    "IDENTICAL_IDENTIFIER"
                    if uri == info["canonical"]
                    else "FORMAL_EQUIVALENCE_OR_INVERSE"
                ),
                "formal_component_conflict": bool(
                    info["logical_conflict"]
                    or info["multiple_same_direction_wikidata_ids"]
                ),
            }
        )
    return output


def audit_current_map(
    current_rows: list[dict[str, str]],
    evidence: list[dict[str, str]],
    dsu: ParityDsu,
    component_info: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    hierarchy = defaultdict(set)
    eventkg = defaultdict(set)
    for row in evidence:
        left, right = row["left_relation"], row["right_relation"]
        left_root = dsu.find(left)[0]
        right_root = dsu.find(right)[0]
        if row["formal_relation"] in {
            "SUBPROPERTY_OF",
            "SUBPROPERTY_OF_EXTERNAL_SUPERPROPERTY",
        }:
            hierarchy[left_root].add(right_root)
        elif row["formal_relation"] == "SUPERPROPERTY_OF_EXTERNAL_SUBPROPERTY":
            hierarchy[right_root].add(left_root)
        elif row["formal_relation"] == "EVENTKG_NORMALIZES_TO":
            eventkg[left_root].add(right_root)

    def reaches(graph: dict[str, set[str]], start: str, target: str) -> bool:
        queue = deque([start])
        seen = {start}
        while queue:
            node = queue.popleft()
            for neighbor in graph.get(node, set()):
                if neighbor == target:
                    return True
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return False

    output = []
    for row in current_rows:
        source = normalize_uri(row["source_predicate"])
        target = normalize_uri(row["final_relation_id"])
        target_for_evidence = target
        scoped_match = re.match(r"^(?:wd:)?(P\d+)\+", target)
        if scoped_match:
            target_for_evidence = "wd:" + scoped_match.group(1)
        source_root, source_parity = dsu.find(source)
        target_root, target_parity = dsu.find(target_for_evidence)
        if source == target:
            status = "SUPPORTED_IDENTICAL_IDENTIFIER"
            expected_direction = "same"
        elif source_root == target_root:
            expected_direction = "reverse" if source_parity ^ target_parity else "same"
            info = component_info[source_root]
            status = (
                "FORMAL_MAPPING_CONFLICT_REVIEW"
                if info["logical_conflict"]
                or info["multiple_same_direction_wikidata_ids"]
                else "SUPPORTED_FORMAL_EQUIVALENCE_OR_INVERSE"
            )
        elif reaches(hierarchy, source_root, target_root) or reaches(
            hierarchy, target_root, source_root
        ):
            status = "FORMAL_HIERARCHY_SUPPORTS_BROADER_VIEW_KEEP_SEPARATE"
            expected_direction = "not_applicable"
        elif target_root in eventkg.get(
            source_root, set()
        ) or source_root in eventkg.get(target_root, set()):
            status = "EVENTKG_BROADER_NORMALIZATION_KEEP_SEPARATE"
            expected_direction = "not_applicable"
        else:
            status = "NO_DETERMINISTIC_MAPPING_EVIDENCE"
            expected_direction = "not_available"
        output.append(
            {
                "source": row["source"],
                "source_predicate": row["source_predicate"],
                "current_final_relation_id": row["final_relation_id"],
                "current_direction": row["direction_to_final"],
                "current_mapping_class": row["final_mapping_class"],
                "deterministic_audit_status": status,
                "deterministic_expected_direction": expected_direction,
                "direction_agreement": (
                    "YES"
                    if expected_direction in {"same", "reverse"}
                    and expected_direction == row["direction_to_final"]
                    else (
                        "NO"
                        if expected_direction in {"same", "reverse"}
                        else "NOT_APPLICABLE"
                    )
                ),
                "current_decision_evidence": row["decision_evidence"],
            }
        )
    return output


def sample_examples(
    connections: list[dict[str, object]], graph_path: Path
) -> tuple[list[dict[str, object]], dict[str, int]]:
    wanted: dict[tuple[str, str], set[str]] = defaultdict(set)
    connection_by_id = {str(row["connection_id"]): row for row in connections}
    for row in connections:
        wanted[(str(row["left_source"]), str(row["left_relation"]))].add(
            str(row["connection_id"])
        )
        wanted[(str(row["right_source"]), str(row["right_relation"]))].add(
            str(row["connection_id"])
        )
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = {
        node["id"]: (node.get("name", ""), node.get("type", ""))
        for node in payload["nodes"]
    }
    relation_edges: dict[tuple[str, str], list[dict]] = defaultdict(list)
    relation_pairs: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for edge in payload["edges"]:
        attributes = edge.get("attributes", {})
        key = (
            attributes.get("selected_source", ""),
            normalize_uri(attributes.get("source_predicate", "")),
        )
        if key not in wanted:
            continue
        relation_pairs[key].add((edge["source"], edge["target"]))
        relation_edges[key].append(edge)

    examples: list[dict[str, object]] = []
    coverage: dict[str, int] = {}
    for connection_id, connection in connection_by_id.items():
        left_key = (
            str(connection["left_source"]),
            str(connection["left_relation"]),
        )
        right_key = (
            str(connection["right_source"]),
            str(connection["right_relation"]),
        )
        candidate_by_fact: dict[tuple[str, str, str, str], tuple[str, dict]] = {}
        for side, key in (("left", left_key), ("right", right_key)):
            for edge in relation_edges.get(key, []):
                digest = hashlib.sha256(
                    f"{connection_id}|{side}|{edge['source']}|{edge['target']}".encode()
                ).hexdigest()
                fact_key = (side, key[1], edge["source"], edge["target"])
                candidate_by_fact.setdefault(
                    fact_key, (digest, {"side": side, "edge": edge, "key": key})
                )
        selected = [
            item
            for _, item in sorted(candidate_by_fact.values(), key=lambda item: item[0])[
                :10
            ]
        ]
        coverage[connection_id] = len(selected)
        for rank, item in enumerate(selected, start=1):
            edge = item["edge"]
            side = item["side"]
            other_key = right_key if side == "left" else left_key
            pair = (edge["source"], edge["target"])
            expected_pair = (
                (pair[1], pair[0]) if connection["direction"] == "reverse" else pair
            )
            counterpart = expected_pair in relation_pairs.get(other_key, set())
            source_name, source_type = nodes.get(edge["source"], ("", ""))
            target_name, target_type = nodes.get(edge["target"], ("", ""))
            examples.append(
                {
                    "connection_id": connection_id,
                    "sample_rank": rank,
                    "sample_side": side,
                    "sample_source_dataset": item["key"][0],
                    "sample_relation": item["key"][1],
                    "subject_id": edge["source"],
                    "subject_name": source_name,
                    "subject_type": source_type,
                    "object_id": edge["target"],
                    "object_name": target_name,
                    "object_type": target_type,
                    "expected_counterpart_pair_present": counterpart,
                    "example_evidence_result": (
                        "AGREES_PAIR_PRESENT"
                        if counterpart
                        else "NO_COUNTERPART_OBSERVATION"
                    ),
                }
            )
    return examples, coverage


def build() -> dict[str, object]:
    retrieved_at = datetime.now(timezone.utc).isoformat()
    inventory = [
        row for row in read_csv(INVENTORY) if row["eligibility"] == "LEVEL2_CANDIDATE"
    ]
    current_rows = read_csv(CURRENT_MAP)
    relevant = {normalize_uri(row["predicate_uri"]) for row in inventory}
    wikidata_ids = {wd_id(uri) for uri in relevant if wd_id(uri)}
    dbpedia_uris = {
        uri for uri in relevant if uri.startswith("http://dbpedia.org/ontology/")
    }
    cidoc_uris = {uri for uri in relevant if "cidoc-crm.org/cidoc-crm/" in uri}
    warsa_uris = {
        uri
        for uri in relevant
        if uri.startswith("http://ldf.fi/")
        or uri.startswith("http://www.cidoc-crm.org/cidoc-crm/")
    }

    wd_evidence, wd_metadata, wd_revisions = load_wikidata(wikidata_ids)
    dbpedia_evidence, dbpedia_metadata = load_dbpedia(dbpedia_uris)
    cidoc_evidence, cidoc_metadata, cidoc_sha256 = load_cidoc(cidoc_uris)
    warsa_evidence, warsa_metadata, warsa_manifest = load_warsampo(warsa_uris)
    eventkg_evidence, eventkg_hashes = load_eventkg()
    evidence = (
        wd_evidence
        + dbpedia_evidence
        + cidoc_evidence
        + warsa_evidence
        + eventkg_evidence
    )
    unique_evidence = {tuple(row.values()): row for row in evidence}
    evidence = sorted(
        unique_evidence.values(),
        key=lambda row: (
            row["left_relation"],
            row["formal_relation"],
            row["right_relation"],
            row["evidence_source"],
        ),
    )

    dsu = ParityDsu()
    for row in evidence:
        if row["formal_relation"] in {"EQUIVALENT", "INVERSE"}:
            dsu.union(
                row["left_relation"],
                row["right_relation"],
                1 if row["formal_relation"] == "INVERSE" else 0,
            )
    for uri in relevant:
        dsu.add(uri)
    connections, component_info = build_connections(inventory, evidence)
    separation_rows = build_separation_evidence(inventory, evidence, dsu)
    relation_rows = relation_records(inventory, component_info, dsu)
    current_audit = audit_current_map(current_rows, evidence, dsu, component_info)
    examples, example_coverage = sample_examples(connections, GRAPH)
    examples_by_connection: dict[str, list[dict[str, object]]] = defaultdict(list)
    for example in examples:
        examples_by_connection[str(example["connection_id"])].append(example)
    for row in connections:
        count = example_coverage[str(row["connection_id"])]
        row["example_count"] = count
        row["example_coverage_status"] = "TEN" if count == 10 else "FEWER_THAN_TEN"
        left_description = bool(str(row["left_description"]).strip())
        right_description = bool(str(row["right_description"]).strip())
        row["description_availability"] = (
            "BOTH"
            if left_description and right_description
            else "ONE" if left_description or right_description else "NONE"
        )
        name_status, name_note = semantic_name_review(row)
        example_status, example_note = example_semantic_review(
            row, examples_by_connection[str(row["connection_id"])]
        )
        row["name_description_review"] = name_status
        row["example_review"] = example_status
        row["review_note"] = name_note + " " + example_note
        if bool(row["formal_component_conflict"]):
            row["activation_status"] = "BLOCKED_FORMAL_COMPONENT_CONFLICT"
        elif name_status == "CONTRADICTS_EXACT_TRANSLATION":
            row["activation_status"] = "BLOCKED_SEMANTIC_CONTRADICTION"
        elif name_status == "PARTIAL_SCOPE_NOT_EXACT":
            row["activation_status"] = "KEEP_SEPARATE_OPTIONAL_BROADER_VIEW"
        elif example_status == "CONTRADICTION_IN_SAMPLED_VALUES":
            row["activation_status"] = "TRANSLATION_VALID_ASSERTION_QA_REQUIRED"
        else:
            row["activation_status"] = "READY_DETERMINISTIC_TRANSLATION"

    activation_priority = {
        "READY_DETERMINISTIC_TRANSLATION": 0,
        "TRANSLATION_VALID_ASSERTION_QA_REQUIRED": 1,
        "KEEP_SEPARATE_OPTIONAL_BROADER_VIEW": 2,
        "BLOCKED_SEMANTIC_CONTRADICTION": 3,
        "BLOCKED_FORMAL_COMPONENT_CONFLICT": 4,
    }
    component_activation: dict[str, str] = {}
    for row in connections:
        canonical = str(row["canonical_level2"])
        status = str(row["activation_status"])
        prior = component_activation.get(canonical, "READY_DETERMINISTIC_TRANSLATION")
        if activation_priority[status] > activation_priority[prior]:
            component_activation[canonical] = status
    for row in relation_rows:
        row["activation_status"] = component_activation.get(
            str(row["deterministic_level2"]), "READY_DETERMINISTIC_TRANSLATION"
        )

    conflict_rows: list[dict[str, object]] = []
    for root in sorted(component_info):
        info = component_info[root]
        if not (
            bool(info["logical_conflict"])
            or bool(info["multiple_same_direction_wikidata_ids"])
        ):
            continue
        members = sorted(str(uri) for uri, _ in info["members"])
        member_set = set(members)
        triggers = [
            item
            for item in evidence
            if item["formal_relation"] in {"EQUIVALENT", "INVERSE"}
            and item["left_relation"] in member_set
            and item["right_relation"] in member_set
        ]
        canonical = str(info["canonical"])
        conflict_rows.append(
            {
                "canonical_level2": canonical,
                "component_members": "|".join(members),
                "logical_parity_conflict": bool(info["logical_conflict"]),
                "multiple_same_direction_wikidata_ids": bool(
                    info["multiple_same_direction_wikidata_ids"]
                ),
                "semantic_problem": FORMAL_COMPONENT_NOTES.get(
                    canonical, "The formal component requires manual review."
                ),
                "formal_statements": " || ".join(
                    f"{item['left_relation']} {item['formal_relation']} {item['right_relation']}"
                    for item in triggers
                ),
                "evidence_urls": "|".join(
                    sorted({item["evidence_url"] for item in triggers})
                ),
            }
        )

    connection_lookup: dict[tuple[frozenset[str], str], dict[str, object]] = {}
    for row in connections:
        key = (
            relation_pair(str(row["left_relation"]), str(row["right_relation"])),
            str(row["direction"]),
        )
        connection_lookup.setdefault(key, row)
    for row in current_audit:
        status = str(row["deterministic_audit_status"])
        if status == "SUPPORTED_IDENTICAL_IDENTIFIER":
            row["semantic_validation"] = "AGREES_SAME_IDENTIFIER"
            row["example_validation"] = "NOT_REQUIRED_FOR_IDENTITY"
            row["recommended_action"] = "KEEP"
            continue
        if status in {
            "FORMAL_HIERARCHY_SUPPORTS_BROADER_VIEW_KEEP_SEPARATE",
            "EVENTKG_BROADER_NORMALIZATION_KEEP_SEPARATE",
        }:
            row["semantic_validation"] = "AGREES_AS_BROADER_VIEW_ONLY"
            row["example_validation"] = "NOT_AN_EXACT_TRANSLATION"
            row["recommended_action"] = "KEEP_SOURCE_LEVEL2_ADD_OPTIONAL_VIEW"
            continue
        if status == "NO_DETERMINISTIC_MAPPING_EVIDENCE":
            row["semantic_validation"] = "NOT_APPLICABLE_NO_MAPPING_EVIDENCE"
            row["example_validation"] = "NOT_APPLICABLE_NO_MAPPING_EVIDENCE"
            row["recommended_action"] = "KEEP_SOURCE_LEVEL2"
            continue
        source = normalize_uri(str(row["source_predicate"]))
        target = normalize_uri(str(row["current_final_relation_id"]))
        key = (
            relation_pair(source, target),
            str(row["deterministic_expected_direction"]),
        )
        connection = connection_lookup.get(key)
        if connection:
            row["semantic_validation"] = connection["name_description_review"]
            row["example_validation"] = connection["example_review"]
            row["recommended_action"] = connection["activation_status"]
        else:
            row["semantic_validation"] = "FORMAL_PATH_FOUND_REVIEW_NOT_LINKED"
            row["example_validation"] = "NO_LINKED_EXAMPLE_REVIEW"
            row["recommended_action"] = "REVIEW"

    evidence_fields = [
        "left_relation",
        "right_relation",
        "formal_relation",
        "deterministic_action",
        "declared_direction",
        "evidence_source",
        "evidence_url",
        "source_version",
        "statement_id",
        "note",
    ]
    connection_fields = [
        "connection_id",
        "left_source",
        "left_relation",
        "left_label",
        "left_description",
        "right_source",
        "right_relation",
        "right_label",
        "right_description",
        "direction",
        "deterministic_basis",
        "formal_path",
        "evidence_sources",
        "evidence_urls",
        "canonical_level2",
        "formal_component_conflict",
        "activation_status",
        "description_availability",
        "example_count",
        "example_coverage_status",
        "name_description_review",
        "example_review",
        "review_note",
    ]
    relation_fields = [
        "source",
        "source_predicate",
        "normalized_relation",
        "label",
        "description",
        "occurrence_count",
        "deterministic_level2",
        "direction_to_level2",
        "mapping_basis",
        "formal_component_conflict",
        "activation_status",
    ]
    audit_fields = [
        "source",
        "source_predicate",
        "current_final_relation_id",
        "current_direction",
        "current_mapping_class",
        "deterministic_audit_status",
        "deterministic_expected_direction",
        "direction_agreement",
        "semantic_validation",
        "example_validation",
        "recommended_action",
        "current_decision_evidence",
    ]
    example_fields = [
        "connection_id",
        "sample_rank",
        "sample_side",
        "sample_source_dataset",
        "sample_relation",
        "subject_id",
        "subject_name",
        "subject_type",
        "object_id",
        "object_name",
        "object_type",
        "expected_counterpart_pair_present",
        "example_evidence_result",
    ]
    write_csv(OUT / "formal_mapping_evidence.csv", evidence, evidence_fields)
    write_csv(OUT / "deterministic_connections.csv", connections, connection_fields)
    write_csv(
        OUT / "deterministic_relation_registry.csv", relation_rows, relation_fields
    )
    write_csv(OUT / "current_mapping_audit.csv", current_audit, audit_fields)
    write_csv(OUT / "connection_examples.csv", examples, example_fields)
    separation_fields = [
        "child_relation",
        "child_label",
        "parent_or_view_relation",
        "parent_or_view_label",
        "formal_relation",
        "effective_direction",
        "source_evidence_left",
        "source_evidence_right",
        "source_statement_direction",
        "deterministic_action",
        "evidence_source",
        "evidence_url",
        "source_version",
        "statement_id",
        "note",
    ]
    write_csv(
        OUT / "separation_and_broader_view_evidence.csv",
        separation_rows,
        separation_fields,
    )
    conflict_fields = [
        "canonical_level2",
        "component_members",
        "logical_parity_conflict",
        "multiple_same_direction_wikidata_ids",
        "semantic_problem",
        "formal_statements",
        "evidence_urls",
    ]
    write_csv(OUT / "formal_component_conflicts.csv", conflict_rows, conflict_fields)

    unique_connections: dict[tuple[frozenset[str], str], dict[str, object]] = {}
    for row in connections:
        key = (
            relation_pair(str(row["left_relation"]), str(row["right_relation"])),
            str(row["direction"]),
        )
        unique_connections.setdefault(key, row)
    unique_connection_rows = list(unique_connections.values())

    summary = {
        "retrieved_at_utc": retrieved_at,
        "method": "Explicit source identifiers and formal mapping values only",
        "inventory_relations": len(inventory),
        "formal_evidence_rows": len(evidence),
        "formal_evidence_by_source": dict(
            Counter(row["evidence_source"] for row in evidence)
        ),
        "formal_evidence_by_relation": dict(
            Counter(row["formal_relation"] for row in evidence)
        ),
        "deterministic_connections": len(connections),
        "unique_relation_pair_connections": len(unique_connection_rows),
        "unique_cross_identifier_connections": sum(
            row["deterministic_basis"] == "FORMAL_EQUIVALENCE_OR_INVERSE_PATH"
            for row in unique_connection_rows
        ),
        "connection_direction_counts": dict(
            Counter(str(row["direction"]) for row in connections)
        ),
        "connections_with_formal_component_conflict": sum(
            bool(row["formal_component_conflict"]) for row in connections
        ),
        "connections_with_ten_examples": sum(
            row["example_coverage_status"] == "TEN" for row in connections
        ),
        "connections_with_fewer_than_ten_examples": sum(
            row["example_coverage_status"] == "FEWER_THAN_TEN" for row in connections
        ),
        "example_rows": len(examples),
        "connection_name_description_review_counts": dict(
            Counter(str(row["name_description_review"]) for row in connections)
        ),
        "connection_description_availability_counts": dict(
            Counter(str(row["description_availability"]) for row in connections)
        ),
        "connection_example_review_counts": dict(
            Counter(str(row["example_review"]) for row in connections)
        ),
        "connection_activation_status_counts": dict(
            Counter(str(row["activation_status"]) for row in connections)
        ),
        "unique_connection_activation_status_counts": dict(
            Counter(str(row["activation_status"]) for row in unique_connection_rows)
        ),
        "separation_and_broader_view_evidence_rows": len(separation_rows),
        "formal_component_conflicts": len(conflict_rows),
        "current_mapping_audit_status_counts": dict(
            Counter(row["deterministic_audit_status"] for row in current_audit)
        ),
        "source_versions": {
            "Wikidata": {
                "mode": "live property entities",
                "property_count": len(wd_revisions),
                "entity_revision_ids_available": sum(
                    bool(value) for value in wd_revisions.values()
                ),
            },
            "DBpedia": "public SPARQL endpoint latest-snapshot",
            "CIDOC_CRM": {"version": "7.1.3", "sha256": cidoc_sha256},
            "EventKG": {"commit": EVENTKG_COMMIT, "file_sha256": eventkg_hashes},
            "WarSampo": warsa_manifest,
        },
        "metadata_rows": {
            "Wikidata": len(wd_metadata),
            "DBpedia": len(dbpedia_metadata),
            "CIDOC_CRM": len(cidoc_metadata),
            "WarSampo": len(warsa_metadata),
        },
        "labels_descriptions_used_for_mapping": False,
        "observations_used_for_mapping": False,
        "source_data_modified": False,
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def self_check() -> None:
    dsu = ParityDsu()
    dsu.union("a", "b", 0)
    dsu.union("b", "c", 1)
    assert dsu.find("a")[0] == dsu.find("c")[0]
    assert dsu.find("a")[1] ^ dsu.find("c")[1] == 1
    assert normalize_uri("http://www.wikidata.org/prop/direct/P276") == "wd:P276"
    assert normalize_uri("http://www.wikidata.org/entity/P276") == "wd:P276"


if __name__ == "__main__":
    self_check()
    print(json.dumps(build(), indent=2))
