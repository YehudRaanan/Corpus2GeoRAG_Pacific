"""Build a source-derived relation catalog and stop before text classification."""

from __future__ import annotations

import csv
import gzip
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from run_mapping_discovery import QUAD, part_lines, reified_groups, resource_qids, short

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "Data/external/wwii_task_force"
EK = BASE / "eventkg_v3_2"
WAR = ROOT / "Data/external/warsampo/full"
AUDIT = Path(__file__).resolve().parent / "audit_2026-10-11"
OUT = Path(__file__).resolve().parent / "relation_catalog_eda"
WD_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = (
    "Corpus2GeoRAG relation catalog EDA/0.1 (github.com/EtzionR/Corpus2GeoRAG_Pacific)"
)

ROLE = "http://semanticweb.cs.vu.nl/2009/11/sem/roleType"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
STRUCTURAL = {
    RDF_TYPE,
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#subject",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#predicate",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#object",
    ROLE,
    "http://www.w3.org/2000/01/rdf-schema#subClassOf",
    "http://www.w3.org/2000/01/rdf-schema#subPropertyOf",
    "http://www.w3.org/2000/01/rdf-schema#domain",
    "http://www.w3.org/2000/01/rdf-schema#range",
    "http://www.w3.org/2000/01/rdf-schema#label",
    "http://www.w3.org/2000/01/rdf-schema#comment",
    "http://www.w3.org/2000/01/rdf-schema#isDefinedBy",
    "http://www.w3.org/2004/02/skos/core#prefLabel",
    "http://www.w3.org/2004/02/skos/core#altLabel",
    "http://www.w3.org/2004/02/skos/core#hiddenLabel",
    "http://www.w3.org/2004/02/skos/core#definition",
    "http://www.w3.org/2004/02/skos/core#note",
    "http://www.w3.org/2004/02/skos/core#scopeNote",
    "http://www.w3.org/2004/02/skos/core#example",
    "http://www.w3.org/2004/02/skos/core#inScheme",
    "https://eventkg.l3s.uni-hannover.de/schema/startUnitType",
    "https://eventkg.l3s.uni-hannover.de/schema/endUnitType",
}
IDENTITY = {
    "http://www.w3.org/2002/07/owl#sameAs",
    "http://www.w3.org/2002/07/owl#differentFrom",
    "http://www.w3.org/2004/02/skos/core#exactMatch",
    "http://www.w3.org/2004/02/skos/core#closeMatch",
    "wd:P1889",
    "wd:P2959",
    "wd:P460",
}
TYPE_IDS = {"wd:P31", "wd:P279"}

# Accepted only with the stated endpoint scope. Similar labels are not enough.
EASY_MAPS = {
    "http://ldf.fi/schema/warsa/actors/hasConflict": (
        "wd:P607",
        "EXACT",
        "same",
        "military unit or person -> conflict",
    ),
    "http://www.cidoc-crm.org/cidoc-crm/P11_had_participant": (
        "wd:P710",
        "EXACT",
        "same",
        "event -> participant",
    ),
    "http://www.cidoc-crm.org/cidoc-crm/P7_took_place_at": (
        "wd:P276",
        "EXACT",
        "same",
        "event -> place",
    ),
    "http://www.cidoc-crm.org/cidoc-crm/P10_falls_within": (
        "wd:P361",
        "EXACT",
        "same",
        "event or period -> containing event or period",
    ),
    "http://semanticweb.cs.vu.nl/2009/11/sem/hasActor": (
        "wd:P710",
        "EXACT",
        "same",
        "event -> actor",
    ),
    "http://semanticweb.cs.vu.nl/2009/11/sem/hasPlace": (
        "wd:P276",
        "EXACT",
        "same",
        "event -> place",
    ),
    "http://semanticweb.cs.vu.nl/2009/11/sem/subEventOf": (
        "wd:P361",
        "EXACT",
        "same",
        "event -> containing event",
    ),
    "http://semanticweb.cs.vu.nl/2009/11/sem/hasSubEvent": (
        "wd:P527",
        "EXACT",
        "same",
        "event -> component event",
    ),
}
DATA_SUPPORTED_MAPS: dict[str, tuple[str, str, str, str]] = {}
MAPPING_EVIDENCE: dict[str, str] = {}

FAMILY_RULES = (
    (
        "ORGANIZATION_HIERARCHY",
        r"\b(parent (company|organi[sz]ation)|child organi[sz]ation|subsidiar|upper unit|command structure|organi[sz]ational unit)\b",
    ),
    (
        "AFFILIATION_STATUS",
        r"\b(citizenship|nationality|allegiance|political party|religion|language|diplomatic relation|affiliation|ethnic group)\b",
    ),
    (
        "CONFLICT_AFFILIATION",
        r"\b(conflict|battle|war|military branch|theatre|theater|campaign)\b",
    ),
    (
        "PARTICIPATION_ROLE",
        r"\b(particip|actor|commander|commanded|carried out|served in|service entry|unit|rank|occupation|employer|member of|office held|role)\b",
    ),
    (
        "PART_WHOLE_HIERARCHY",
        r"\b(part of|has part|subevent|sub-event|falls within|upper unit|parent organi|subsidiar|broader|narrower)\b",
    ),
    (
        "SPATIAL",
        r"\b(place|location|located|country|territor|municipalit|headquarter|residen|burial|birthplace|death place|capture place|within|capital)\b",
    ),
    (
        "TEMPORAL_SUCCESSION",
        r"\b(replace|replaced|follows|followed|preced|successor|predecessor)\b",
    ),
    ("CAUSAL", r"\b(cause|caused|effect|consequence|resulted|killed by|perpetrator)\b"),
    (
        "FORMATION_DISSOLUTION",
        r"\b(formed|formation|dissolv|created|brought into life|joined|separated)\b",
    ),
    (
        "FAMILY_PERSONAL",
        r"\b(spouse|father|mother|child|sibling|relative|family relation)\b",
    ),
    ("OWNERSHIP_CONTROL", r"\b(owner|owned|operator|controlled|occupier|possess)\b"),
    ("AWARD_RECOGNITION", r"\b(award|medal|honou?r|decorat|nominated)\b"),
    (
        "EDUCATION_EMPLOYMENT",
        r"\b(educated|student|academic advisor|work location|employ|occupation)\b",
    ),
    (
        "CREATION_AUTHORSHIP",
        r"\b(author|creator|manufacturer|produced|designed|architect)\b",
    ),
)

REIFIED = (
    "relations_events_other",
    "relations_entities_temporal",
    "relations_entities_other",
    "relations_events_literals",
)
DIRECT = ("events", "relations_events_base", "entities", "relations_entities_base")


def local_label(uri: str) -> str:
    value = short(uri).replace("_", " ").replace("-", " ")
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    value = re.sub(r"^P\d+\s*", "", value)
    return re.sub(r"\s+", " ", value).strip()


def normalized_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def qid_from_value(value: object) -> str | None:
    if not isinstance(value, dict) or value.get("entity-type") != "item":
        return None
    return value.get("id")


def read_wikidata() -> tuple[dict[str, dict], dict[str, set[str]], dict]:
    logging.info("Scan Wikidata records")
    population = set(
        (BASE / "wikidata_qids.txt").read_text(encoding="utf-8").splitlines()
    )
    qid_types: dict[str, set[str]] = {}
    records: list[tuple[str, dict]] = []
    path = BASE / "wikidata_entities.jsonl.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            qid = record["requested_qid"]
            entity = record.get("entity", {})
            if entity.get("id") != qid:
                continue
            claims = entity.get("claims", {})
            qid_types[qid] = {
                target
                for statement in claims.get("P31", [])
                if statement.get("rank") != "deprecated"
                for target in [
                    qid_from_value(
                        statement.get("mainsnak", {}).get("datavalue", {}).get("value")
                    )
                ]
                if target
            }
            records.append((qid, claims))

    stats: dict[str, dict] = defaultdict(
        lambda: {
            "occurrence_count": 0,
            "subject_count": 0,
            "qualified_count": 0,
            "internal_target_count": 0,
            "external_target_count": 0,
            "targets": set(),
            "external_targets": set(),
            "subject_types": Counter(),
            "object_types": Counter(),
        }
    )
    for subject, claims in records:
        for prop, statements in claims.items():
            seen = False
            for statement in statements:
                if statement.get("rank") == "deprecated":
                    continue
                target = qid_from_value(
                    statement.get("mainsnak", {}).get("datavalue", {}).get("value")
                )
                if not target:
                    continue
                seen = True
                item = stats[prop]
                item["occurrence_count"] += 1
                item["targets"].add(target)
                item["qualified_count"] += int(bool(statement.get("qualifiers")))
                if target in population:
                    item["internal_target_count"] += 1
                else:
                    item["external_target_count"] += 1
                    item["external_targets"].add(target)
                item["subject_types"].update(qid_types.get(subject) or {"UNTYPED"})
                item["object_types"].update(qid_types.get(target) or {"TYPE_NOT_LOCAL"})
            if seen:
                stats[prop]["subject_count"] += 1
    return (
        stats,
        qid_types,
        {"population_qids": len(population), "records": len(records)},
    )


def fetch_wikidata_metadata(properties: list[str]) -> dict[str, dict]:
    cache = OUT / "wikidata_property_metadata.json"
    if cache.exists():
        saved = json.loads(cache.read_text(encoding="utf-8"))
        if set(properties) <= set(saved.get("properties", {})):
            logging.info("Use cached Wikidata property metadata")
            return saved["properties"]
    logging.info(
        "Fetch official metadata for %d Wikidata properties with SPARQL",
        len(properties),
    )
    result: dict[str, dict] = {}
    for start in range(0, len(properties), 100):
        ids = properties[start : start + 100]
        sparql = f"""SELECT ?property ?label ?description ?propertyType WHERE {{
  VALUES ?property {{ {' '.join(f'wd:{prop}' for prop in ids)} }}
  OPTIONAL {{ ?property rdfs:label ?label FILTER(LANG(?label) = "en") }}
  OPTIONAL {{ ?property schema:description ?description FILTER(LANG(?description) = "en") }}
  OPTIONAL {{ ?property wikibase:propertyType ?propertyType }}
}}"""
        request = Request(
            WD_SPARQL,
            data=urlencode({"query": sparql}).encode(),
            headers={
                "Accept": "application/sparql-results+json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        with urlopen(request, timeout=45) as response:
            payload = json.load(response)
        for binding in payload["results"]["bindings"]:
            prop = binding["property"]["value"].rsplit("/", 1)[-1]
            result[prop] = {
                "label": binding.get("label", {}).get("value", prop),
                "description": binding.get("description", {}).get("value", ""),
                "datatype": binding.get("propertyType", {}).get("value", ""),
                "metadata_source": WD_SPARQL,
            }
    missing = set(properties) - set(result)
    if missing:
        raise RuntimeError(
            f"Wikidata SPARQL metadata missing {len(missing)} properties"
        )
    cache.write_text(
        json.dumps(
            {
                "source": WD_SPARQL,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "properties": result,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return result


def eventkg_labels() -> dict[str, str]:
    labels: dict[str, str] = {}
    pattern = re.compile(r'^<([^>]+)> <[^>]*#label> "((?:\\.|[^"])*)"@en ')
    with (EK / "metadata/property_labels.nq").open(encoding="utf-8") as stream:
        for line in stream:
            match = pattern.match(line)
            if match:
                labels.setdefault(
                    match[1], bytes(match[2], "utf-8").decode("unicode_escape")
                )
    return labels


def read_eventkg() -> tuple[dict[str, dict], dict]:
    logging.info("Scan EventKG relation extracts")
    r2q, kind = resource_qids()
    stats: dict[str, dict] = defaultdict(
        lambda: {
            "occurrence_count": 0,
            "graphs": Counter(),
            "subject_kinds": Counter(),
            "object_kinds": Counter(),
        }
    )
    for name in REIFIED:
        for _, graph, role, subject, target in reified_groups(name):
            item = stats[role]
            item["occurrence_count"] += 1
            item["graphs"][short(graph)] += 1
            qs, qt = r2q.get(subject), r2q.get(target)
            item["subject_kinds"][kind.get(qs, "unknown")] += 1
            item["object_kinds"][kind.get(qt, "unknown")] += 1
    for name in DIRECT:
        for line in part_lines(name):
            match = QUAD.match(line.rstrip("\n"))
            if not match:
                continue
            subject, predicate, target, graph = match.groups()
            item = stats[predicate]
            item["occurrence_count"] += 1
            item["graphs"][short(graph or "source_unknown")] += 1
            qs, qt = r2q.get(subject), r2q.get(target)
            item["subject_kinds"][kind.get(qs, "unknown")] += 1
            item["object_kinds"][kind.get(qt, "unknown")] += 1
    return stats, {"mapped_qids": len(kind)}


def ttl_statements(text: str):
    start = 0
    quote = ""
    angle = False
    escape = False
    index = 0
    while index < len(text):
        if quote:
            if escape:
                escape = False
            elif text[index] == "\\":
                escape = True
            elif text.startswith(quote, index):
                index += len(quote) - 1
                quote = ""
        elif text.startswith('"""', index):
            quote = '"""'
            index += 2
        elif text[index] == '"':
            quote = '"'
        elif text[index] == "<":
            angle = True
        elif text[index] == ">":
            angle = False
        elif text[index] == "." and not angle:
            value = text[start:index].strip()
            if value:
                yield value
            start = index + 1
        index += 1


def expand(token: str, prefixes: dict[str, str]) -> str:
    token = token.strip().rstrip(";,.")
    if token.startswith("<") and token.endswith(">"):
        return token[1:-1]
    if ":" in token:
        prefix, value = token.split(":", 1)
        if prefix in prefixes:
            return prefixes[prefix] + value
    return token


def schema_metadata(paths: list[Path]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"(?m)^\s*#.*$", "", text)
        prefixes = {
            match[0]: match[1]
            for match in re.findall(r"@prefix\s+([\w-]*):\s+<([^>]+)>", text)
        }
        for statement in ttl_statements(text):
            if statement.startswith("@prefix") or not re.search(
                r"\b(?:owl:ObjectProperty|rdf:Property)\b", statement
            ):
                continue
            subject = statement.split(None, 1)[0]
            if not re.fullmatch(r"(?:<[^>]+>|[\w-]*:[^\s;,]+)", subject):
                continue
            uri = expand(subject, prefixes)
            labels = re.findall(
                r"(?:rdfs:label|skos:prefLabel)\s+\"((?:\\.|[^\"])*)\"@en",
                statement,
            )
            descriptions = re.findall(
                r"(?:rdfs:comment|dct:description|skos:definition)\s+\"(?:\"\")?((?:\\.|[^\"])*)",
                statement,
            )
            domain = re.search(r"rdfs:domain\s+([^\s;,]+)", statement)
            range_ = re.search(r"rdfs:range\s+([^\s;,]+)", statement)
            result[uri] = {
                "label": labels[0] if labels else local_label(uri),
                "description": descriptions[0] if descriptions else "",
                "domain": expand(domain.group(1), prefixes) if domain else "",
                "range": expand(range_.group(1), prefixes) if range_ else "",
                "schema_file": str(path.relative_to(ROOT)).replace("\\", "/"),
            }
    return result


def top(counter: Counter, limit: int = 5) -> str:
    return "|".join(f"{key}:{value}" for key, value in counter.most_common(limit))


def wd_id(uri: str) -> str | None:
    match = re.search(r"(?:^wd:|/prop/direct/)(P\d+)$", uri)
    return match.group(1) if match else None


def exclusion(canonical: str, uri: str, label: str, description: str) -> str:
    text = f"{label} {description}".casefold()
    if (
        uri in STRUCTURAL
        or canonical in TYPE_IDS
        or uri.startswith("http://www.w3.org/ns/sparql-service-description#")
        or uri.startswith("http://rdfs.org/ns/void#")
    ):
        return "TYPE_OR_SCHEMA"
    if uri in IDENTITY or canonical in IDENTITY:
        return "IDENTITY_LINK"
    if uri in {
        "http://purl.org/dc/terms/source",
        "http://purl.org/dc/terms/creator",
        "http://purl.org/dc/terms/publisher",
        "http://purl.org/dc/terms/license",
        "http://purl.org/dc/terms/rights",
        "http://purl.org/dc/terms/rightsHolder",
        "http://purl.org/dc/terms/hasFormat",
        "http://purl.org/dc/terms/subject",
        "http://schema.org/contentUrl",
        "http://xmlns.com/foaf/0.1/page",
        "http://xmlns.com/foaf/0.1/homepage",
        "https://eventkg.l3s.uni-hannover.de/schema/extractedFrom",
    } or re.search(
        r"\b(source|reference|documented|documentation|described by|main category|wikimedia|url|web ?site|image|media|license|rights|format|identifier|catalog|database|authority control|topic's main)\b",
        text,
    ):
        return "PROVENANCE_OR_DOCUMENT"
    if re.search(
        r"\b(date|time ?stamp|coordinate|latitude|longitude|quantity|number of|size|code|gender|sex or gender|marital status|mother tongue)\b",
        text,
    ):
        return "ATTRIBUTE"
    return ""


def family_for(canonical: str, label: str, description: str) -> str:
    fixed = {
        "wd:P607": "CONFLICT_AFFILIATION",
        "wd:P710": "PARTICIPATION_ROLE",
        "wd:P276": "SPATIAL",
        "wd:P361": "PART_WHOLE_HIERARCHY",
        "wd:P527": "PART_WHOLE_HIERARCHY",
    }
    if canonical in fixed:
        return fixed[canonical]
    # The label is the safe field shared by all three sources. Descriptions are
    # retained for review but can contain unrelated examples and constraints.
    text = label.casefold()
    for family, pattern in FAMILY_RULES:
        if re.search(pattern, text):
            return family
    return "UNASSIGNED_REVIEW"


def mapping(uri: str) -> tuple[str, str, str, str]:
    prop = wd_id(uri)
    if prop:
        return f"wd:{prop}", "EXACT", "same", "Wikidata property identity"
    if uri in EASY_MAPS:
        return EASY_MAPS[uri]
    if uri in DATA_SUPPORTED_MAPS:
        return DATA_SUPPORTED_MAPS[uri]
    return uri, "SOURCE_ONLY", "same", "No accepted cross-source mapping"


def load_data_supported_maps(
    ek_stats: dict[str, dict], ek_labels: dict[str, str], wd_meta: dict[str, dict]
) -> None:
    """Accept only strong same-label, same-direction endpoint overlap."""
    path = (
        Path(__file__).resolve().parent
        / "mapping_discovery/eventkg_wikidata_candidates.csv"
    )
    if not path.exists():
        return
    qualifying: dict[str, list[dict]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if (
                row["direction"] != "same"
                or int(row["shared_pairs"]) < 20
                or float(row["pct_of_ek_co_connected"]) < 90
                or float(row["after_largest_target_pct"]) < 80
            ):
                continue
            for uri, item in ek_stats.items():
                if (
                    short(uri) != row["ek_role"]
                    or row["ek_graph"] not in item["graphs"]
                ):
                    continue
                if normalized_label(
                    ek_labels.get(uri) or local_label(uri)
                ) != normalized_label(
                    wd_meta.get(row["wd_property"], {}).get("label", row["wd_property"])
                ):
                    continue
                qualifying[uri].append(row)
    for uri, rows in qualifying.items():
        properties = {row["wd_property"] for row in rows}
        if len(properties) != 1 or uri in EASY_MAPS:
            continue
        best = max(rows, key=lambda row: int(row["shared_pairs"]))
        prop = best["wd_property"]
        DATA_SUPPORTED_MAPS[uri] = (
            f"wd:{prop}",
            "EXACT_DATA_SUPPORTED",
            "same",
            f"{best['subject_kind']} -> {best['object_kind']}",
        )
        MAPPING_EVIDENCE[uri] = (
            f"{best['shared_pairs']} shared endpoint pairs; "
            f"{best['pct_of_ek_co_connected']}% of co-connected pairs; "
            f"{best['after_largest_target_pct']}% after largest target"
        )


def add_row(
    rows: list[dict],
    *,
    source: str,
    uri: str,
    label: str,
    description: str,
    count: int,
    observation_status: str,
    graphs: str = "",
    subjects: str = "",
    objects: str = "",
    defined: bool = False,
    metadata_source: str = "",
    evidence_kind: str = "primary",
    independent_occurrence_count: int | None = None,
    extra: dict | None = None,
) -> None:
    canonical, status, direction, scope = mapping(uri)
    excluded = exclusion(canonical, uri, label, description)
    family = "EXCLUDED" if excluded else family_for(canonical, label, description)
    row = {
        "source": source,
        "predicate_uri": uri,
        "source_predicate": f"wd:{wd_id(uri)}" if wd_id(uri) else short(uri),
        "label": label,
        "description": description,
        "defined_in_schema": defined,
        "observation_status": observation_status,
        "occurrence_count": count,
        "source_graphs": graphs,
        "subject_type_counts": subjects,
        "object_type_counts": objects,
        "eligibility": "EXCLUDED" if excluded else "LEVEL2_CANDIDATE",
        "exclusion_reason": excluded,
        "level1_family": family,
        "canonical_level2_id": canonical,
        "mapping_status": status,
        "direction": direction,
        "scope_constraint": scope,
        "metadata_source": metadata_source,
        "mapping_evidence": MAPPING_EVIDENCE.get(
            uri, "definition and scoped direction" if uri in EASY_MAPS else ""
        ),
        "evidence_kind": evidence_kind,
        "independent_occurrence_count": (
            count
            if independent_occurrence_count is None
            else independent_occurrence_count
        ),
    }
    if extra:
        row.update(extra)
    rows.append(row)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    OUT.mkdir(exist_ok=True)
    wd_stats, _, summary = read_wikidata()
    wd_meta = fetch_wikidata_metadata(sorted(wd_stats))
    ek_stats, ek_summary = read_eventkg()
    ek_labels = eventkg_labels()
    load_data_supported_maps(ek_stats, ek_labels, wd_meta)
    schema_paths = [
        WAR / "Warsampo-schema/warsampo-schema.ttl",
        WAR / "ammo-data/ammo_schema.ttl",
    ]
    war_meta = schema_metadata(schema_paths)
    ek_schema = schema_metadata([EK / "metadata/schema.ttl"])

    rows: list[dict] = []
    for prop, item in sorted(wd_stats.items()):
        meta = wd_meta.get(prop, {})
        add_row(
            rows,
            source="Wikidata",
            uri=f"wd:{prop}",
            label=meta.get("label", prop),
            description=meta.get("description", ""),
            count=item["occurrence_count"],
            observation_status="OBSERVED",
            subjects=top(item["subject_types"]),
            objects=top(item["object_types"]),
            defined=True,
            metadata_source=meta.get("metadata_source", WD_SPARQL),
            extra={
                "subject_count": item["subject_count"],
                "distinct_target_count": len(item["targets"]),
                "internal_target_count": item["internal_target_count"],
                "external_target_count": item["external_target_count"],
                "distinct_external_target_count": len(item["external_targets"]),
                "qualified_count": item["qualified_count"],
            },
        )

    for uri, item in sorted(ek_stats.items()):
        meta = ek_schema.get(uri, {})
        copied = item["graphs"].get("wikidata", 0)
        independent = item["occurrence_count"] - copied
        evidence_kind = (
            "copied_wikidata"
            if not independent
            else "mixed" if copied else "independent_source_graph"
        )
        add_row(
            rows,
            source="EventKG",
            uri=uri,
            label=ek_labels.get(uri) or meta.get("label") or local_label(uri),
            description=meta.get("description", ""),
            count=item["occurrence_count"],
            observation_status="OBSERVED",
            graphs=top(item["graphs"], 20),
            subjects=top(item["subject_kinds"]),
            objects=top(item["object_kinds"]),
            defined=uri in ek_schema,
            metadata_source="EventKG v3.2 local metadata",
            evidence_kind=evidence_kind,
            independent_occurrence_count=independent,
            extra={
                "subject_count": "",
                "distinct_target_count": "",
                "internal_target_count": "",
                "external_target_count": "",
                "distinct_external_target_count": "",
                "qualified_count": "",
            },
        )
    for uri, meta in sorted(ek_schema.items()):
        if uri not in ek_stats:
            add_row(
                rows,
                source="EventKG",
                uri=uri,
                label=meta["label"],
                description=meta["description"],
                count=0,
                observation_status="DEFINED_NOT_OBSERVED",
                defined=True,
                metadata_source=meta["schema_file"],
                extra={
                    key: ""
                    for key in (
                        "subject_count",
                        "distinct_target_count",
                        "internal_target_count",
                        "external_target_count",
                        "distinct_external_target_count",
                        "qualified_count",
                    )
                },
            )

    with (AUDIT / "warsampo_predicates.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        war_counts = {
            row["predicate"]: int(row["iri_triples"]) for row in csv.DictReader(stream)
        }
    for uri in sorted(set(war_counts) | set(war_meta)):
        meta = war_meta.get(uri, {})
        count = war_counts.get(uri, 0)
        add_row(
            rows,
            source="WarSampo",
            uri=uri,
            label=meta.get("label") or local_label(uri),
            description=meta.get("description", ""),
            count=count,
            observation_status="OBSERVED" if count else "DEFINED_NOT_OBSERVED",
            defined=uri in war_meta,
            metadata_source=meta.get("schema_file", "WarSampo v2.1.0 data"),
            extra={
                key: ""
                for key in (
                    "subject_count",
                    "distinct_target_count",
                    "internal_target_count",
                    "external_target_count",
                    "distinct_external_target_count",
                    "qualified_count",
                )
            },
        )

    # One canonical relation must have one family. Prefer its official
    # Wikidata definition when that relation has a Wikidata property ID.
    canonical_families = {
        row["canonical_level2_id"]: row["level1_family"]
        for row in rows
        if row["source"] == "Wikidata" and row["eligibility"] == "LEVEL2_CANDIDATE"
    }
    for row in rows:
        family = canonical_families.get(row["canonical_level2_id"])
        if family and row["eligibility"] == "LEVEL2_CANDIDATE":
            row["level1_family"] = family

    rows.sort(key=lambda row: (row["source"], row["predicate_uri"]))
    write_csv(OUT / "source_predicate_inventory.csv", rows)
    write_csv(
        OUT / "excluded_predicates.csv",
        [row for row in rows if row["eligibility"] == "EXCLUDED"],
    )

    alignments = [
        {
            "source": row["source"],
            "source_predicate": row["predicate_uri"],
            "canonical_level2_id": row["canonical_level2_id"],
            "mapping_status": row["mapping_status"],
            "direction": row["direction"],
            "scope_constraint": row["scope_constraint"],
            "level1_family": row["level1_family"],
            "occurrence_count": row["occurrence_count"],
        }
        for row in rows
        if row["eligibility"] == "LEVEL2_CANDIDATE"
    ]
    write_csv(OUT / "source_alignment.csv", alignments)
    write_csv(
        OUT / "accepted_easy_mappings.csv",
        [
            {
                "source": row["source"],
                "source_predicate": row["predicate_uri"],
                "source_label": row["label"],
                "source_description": row["description"],
                "canonical_level2_id": row["canonical_level2_id"],
                "mapping_status": row["mapping_status"],
                "direction": row["direction"],
                "scope_constraint": row["scope_constraint"],
                "level1_family": row["level1_family"],
                "occurrence_count": row["occurrence_count"],
                "mapping_evidence": row["mapping_evidence"],
            }
            for row in rows
            if row["mapping_status"] in {"EXACT", "EXACT_DATA_SUPPORTED"}
            and not wd_id(row["predicate_uri"])
        ],
    )

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        if row["eligibility"] == "LEVEL2_CANDIDATE":
            grouped[(row["level1_family"], row["canonical_level2_id"])].append(row)
    level2 = []
    for (family, canonical), members in sorted(grouped.items()):
        preferred = next(
            (row for row in members if row["source"] == "Wikidata"), members[0]
        )
        level2.append(
            {
                "level1_family": family,
                "canonical_level2_id": canonical,
                "label": preferred["label"],
                "description": preferred["description"],
                "sources": "|".join(sorted({row["source"] for row in members})),
                "source_predicates": "|".join(
                    sorted({row["predicate_uri"] for row in members})
                ),
                "source_occurrences_sum": sum(
                    int(row["occurrence_count"]) for row in members
                ),
                "independent_occurrences_sum": sum(
                    int(row["independent_occurrence_count"]) for row in members
                ),
                "mapping_statuses": "|".join(
                    sorted({row["mapping_status"] for row in members})
                ),
                "requires_review": family == "UNASSIGNED_REVIEW"
                or any(row["mapping_status"] == "SOURCE_ONLY" for row in members),
            }
        )
    write_csv(OUT / "level2_relations.csv", level2)

    families = []
    for family in sorted({row["level1_family"] for row in level2}):
        members = [row for row in level2 if row["level1_family"] == family]
        families.append(
            {
                "level1_family": family,
                "level2_relation_count": len(members),
                "source_occurrences_sum": sum(
                    row["source_occurrences_sum"] for row in members
                ),
                "independent_occurrences_sum": sum(
                    row["independent_occurrences_sum"] for row in members
                ),
                "level2_ids": "|".join(row["canonical_level2_id"] for row in members),
            }
        )
    write_csv(OUT / "level1_families.csv", families)

    # Label equality is useful EDA evidence, but it never creates an accepted mapping.
    by_label: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["eligibility"] == "LEVEL2_CANDIDATE":
            key = re.sub(r"[^a-z0-9]+", " ", row["label"].casefold()).strip()
            if key:
                by_label[key].append(row)
    candidates = []
    for label, members in sorted(by_label.items()):
        if (
            len({row["source"] for row in members}) < 2
            or len({row["canonical_level2_id"] for row in members}) < 2
        ):
            continue
        candidates.append(
            {
                "normalized_label": label,
                "sources": "|".join(sorted({row["source"] for row in members})),
                "predicates": "|".join(
                    sorted({row["predicate_uri"] for row in members})
                ),
                "candidate_status": "UNRESOLVED_LABEL_MATCH",
                "reason": "Same English label; meaning, direction, and endpoint scope still need review",
            }
        )
    candidates.extend(
        [
            {
                "normalized_label": "upper unit / part of",
                "sources": "WarSampo|Wikidata",
                "predicates": "http://ldf.fi/warsa/actors/hasUpperUnit|wd:P361|wd:P527",
                "candidate_status": "UNRESOLVED_SCOPE_AND_DIRECTION",
                "reason": "The local WarSampo predicate has no formal definition in the available schema; P361 and P527 are opposite directions",
            }
        ]
    )
    write_csv(OUT / "unresolved_mapping_candidates.csv", candidates)

    result = {
        **summary,
        "eventkg_mapped_qids": ek_summary["mapped_qids"],
        "source_predicates": dict(Counter(row["source"] for row in rows)),
        "observed_source_predicates": dict(
            Counter(
                row["source"] for row in rows if row["observation_status"] == "OBSERVED"
            )
        ),
        "defined_not_observed": dict(
            Counter(
                row["source"]
                for row in rows
                if row["observation_status"] == "DEFINED_NOT_OBSERVED"
            )
        ),
        "excluded_predicates": len(
            [row for row in rows if row["eligibility"] == "EXCLUDED"]
        ),
        "level1_families": len(families),
        "level2_relations": len(level2),
        "assigned_level2_relations": len(
            [row for row in level2 if row["level1_family"] != "UNASSIGNED_REVIEW"]
        ),
        "defined_not_observed_level2_relations": len(
            [
                row
                for row in rows
                if row["observation_status"] == "DEFINED_NOT_OBSERVED"
                and row["eligibility"] == "LEVEL2_CANDIDATE"
            ]
        ),
        "accepted_cross_vocabulary_rows": len(
            [
                row
                for row in rows
                if row["mapping_status"] in {"EXACT", "EXACT_DATA_SUPPORTED"}
                and not wd_id(row["predicate_uri"])
            ]
        ),
        "accepted_definition_mappings": len(
            [row for row in rows if row["predicate_uri"] in EASY_MAPS]
        ),
        "accepted_data_supported_mappings": len(DATA_SUPPORTED_MAPS),
        "eventkg_copied_only_predicates": len(
            [row for row in rows if row["evidence_kind"] == "copied_wikidata"]
        ),
        "unassigned_level2_relations": len(
            [row for row in level2 if row["level1_family"] == "UNASSIGNED_REVIEW"]
        ),
        "unresolved_label_candidates": len(candidates),
        "classifier_run": False,
        "source_data_modified": False,
    }
    (OUT / "summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    logging.info("Done: %s", json.dumps(result))


if __name__ == "__main__":
    main()
