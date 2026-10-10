"""Collect a reproducible WarSampo–Wikidata predicate-overlap inventory.

The overlap is provisional until the identity and predicate reviews in the
accompanying report are complete. No instance facts are exported to the graph.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

HERE = Path(__file__).resolve().parent
OUT = HERE / "audit_2026-10-11"
CACHE = Path(tempfile.gettempdir()) / "geoai_relation_alignment_http_cache"
WAR = "https://ldf.fi/warsa/sparql"
WD = "https://www.wikidata.org/w/api.php"
SAME_AS = "http://www.w3.org/2002/07/owl#sameAs"
PREF_LABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"
USER_AGENT = "Corpus2GeoRAG relation mapping audit/0.1 (github.com/EtzionR/Corpus2GeoRAG_Pacific)"
PERIODS = {
    "http://ldf.fi/warsa/conflicts/WinterWar": "Q134949",
    "http://ldf.fi/warsa/conflicts/ContinuationWar": "Q122100",
    "http://ldf.fi/warsa/conflicts/LaplandWar": "Q154940",
    "http://ldf.fi/warsa/conflicts/SecondWorldWar": "Q362",
    "http://ldf.fi/warsa/conflicts/InterimPeace": "Q3098938",
}
UNIT_TYPES = {
    "Q176799",
    "Q52371",
    "Q6382533",
    "Q169534",
    "Q679165",
    "Q9248092",
    "Q188497",
    "Q1229765",
    "Q240313",
    "Q51977",
}
MANUAL_UNIT_IDS = {
    "http://ldf.fi/warsa/actors/actor_17387": "Q11894949",
    "http://ldf.fi/warsa/actors/actor_17451": "Q18693687",
}


def normalized_label(value: str) -> str:
    return re.sub(r"\s*\([^)]*\)$", "", value.strip()).casefold()


def identity_screen(
    uri: str,
    qid: str,
    war_labels: list[str],
    war_types: list[str],
    entity: dict,
    bases: set[str],
    ambiguous: bool,
) -> tuple[str, str]:
    p31 = set(item_values(entity, "P31"))
    if "Q4167836" in p31:
        return "rejected", "Wikimedia category is not a military unit"
    if "Q121289722" in p31:
        return "rejected", "boat class is not the named individual boat"
    if ambiguous:
        return "unresolved", "multiple Wikidata candidates for one WarSampo URI"
    if uri in PERIODS:
        return "reviewed", "historical name and date interval checked"
    fi_label = normalized_label(entity.get("labels", {}).get("fi", {}).get("value", ""))
    war_names = {normalized_label(label) for label in war_labels}
    if "http://ldf.fi/schema/warsa/Person" in war_types:
        wd_names = " ".join(
            entity.get("labels", {}).get(lang, {}).get("value", "")
            for lang in ("fi", "en")
        ).casefold()
        war_tokens = set(re.findall(r"\w+", " ".join(war_labels).casefold()))
        wd_tokens = set(re.findall(r"\w+", wd_names))
        if "owl:sameAs" in bases and "Q5" in p31 and war_tokens & wd_tokens:
            return "screened", "direct identity link, human type, and shared name token"
    if "http://ldf.fi/schema/warsa/MilitaryUnit" in war_types:
        if MANUAL_UNIT_IDS.get(uri) == qid:
            return "reviewed", "unit label, page, and upper-unit statement checked"
        if fi_label and fi_label in war_names and p31 & UNIT_TYPES:
            return (
                "screened",
                "linked page, matching Finnish name, and compatible unit type",
            )
    return "unresolved", "name, type, or historical stage needs manual review"


def get_json(url: str, params: dict[str, str]) -> dict:
    CACHE.mkdir(exist_ok=True)
    key = hashlib.sha256(
        (url + json.dumps(params, sort_keys=True)).encode()
    ).hexdigest()
    cache_path = CACHE / f"{key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    for attempt in range(5):
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=120,
        )
        if response.status_code == 429 and attempt < 4:
            delay = max(2, int(response.headers.get("Retry-After", "2"))) + 1
            print(f"Rate limit from {url}; waiting {delay}s", file=sys.stderr)
            time.sleep(delay)
            continue
        response.raise_for_status()
        data = response.json()
        cache_path.write_text(json.dumps(data), encoding="utf-8")
        return data
    raise RuntimeError(f"Rate limit persisted at {url}")


def sparql(query: str) -> list[dict[str, str]]:
    data = get_json(WAR, {"query": query, "format": "application/sparql-results+json"})
    return [
        {key: value["value"] for key, value in row.items()}
        for row in data["results"]["bindings"]
    ]


def chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[start : start + size] for start in range(0, len(items), size)]


def write_csv(name: str, fieldnames: list[str], rows: list[dict]) -> None:
    with (OUT / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def item_values(entity: dict, property_id: str) -> list[str]:
    values = []
    for statement in entity.get("claims", {}).get(property_id, []):
        snak = statement["mainsnak"]
        value = snak.get("datavalue", {}).get("value", {})
        if (
            snak.get("snaktype") == "value"
            and isinstance(value, dict)
            and value.get("entity-type") == "item"
        ):
            values.append(value["id"])
    return values


def rank_joint_rows(rows: list[dict]) -> list[dict]:
    """Rank predicate matches only where both graphs relate the same QID pair."""
    mappings: dict[tuple[str, str, str], set[tuple[str, str]]] = defaultdict(set)
    war_pairs: dict[str, set[tuple[str, str]]] = defaultdict(set)
    wd_pairs: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        pair = (row["war_subject_qid"], row["war_object_qid"])
        key = (row["war_predicate"], row["wd_property"], row["direction"])
        mappings[key].add(pair)
        war_pairs[row["war_predicate"]].add(pair)
        wd_pairs[row["wd_property"]].add((row["wd_subject_qid"], row["wd_object_qid"]))
    return [
        {
            "war_predicate": war_predicate,
            "wd_property": wd_property,
            "direction": direction,
            "shared_pairs": len(pairs),
            "war_co_connected_pairs": len(war_pairs[war_predicate]),
            "wd_co_connected_pairs": len(wd_pairs[wd_property]),
            "pct_of_war_co_connected": round(100 * len(pairs) / len(war_pairs[war_predicate]), 1),
            "pct_of_wd_co_connected": round(100 * len(pairs) / len(wd_pairs[wd_property]), 1),
        }
        for (war_predicate, wd_property, direction), pairs in sorted(mappings.items())
    ]


def wikipedia_unit_links() -> dict[str, set[str]]:
    rows = sparql(
        "SELECT DISTINCT ?s ?page WHERE { ?s a <http://ldf.fi/schema/warsa/MilitaryUnit> ; "
        "<http://xmlns.com/foaf/0.1/page> ?page . FILTER(isIRI(?page)) }"
    )
    by_host: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in rows:
        url = urlparse(row["page"])
        if url.netloc not in {
            "fi.wikipedia.org",
            "en.wikipedia.org",
        } or not url.path.startswith("/wiki/"):
            continue
        title = unquote(url.path.removeprefix("/wiki/")).replace("_", " ")
        by_host[url.netloc][title].add(row["s"])

    result: dict[str, set[str]] = defaultdict(set)
    for host, title_to_subjects in by_host.items():
        for group in chunks(sorted(title_to_subjects), 40):
            data = get_json(
                f"https://{host}/w/api.php",
                {
                    "action": "query",
                    "prop": "pageprops",
                    "ppprop": "wikibase_item",
                    "redirects": "1",
                    "titles": "|".join(group),
                    "format": "json",
                },
            )["query"]
            replacements = {
                row["from"]: row["to"]
                for category in ("normalized", "redirects")
                for row in data.get(category, [])
            }
            pages = {page["title"]: page for page in data["pages"].values()}
            for title in group:
                canonical = title
                seen = set()
                while canonical in replacements and canonical not in seen:
                    seen.add(canonical)
                    canonical = replacements[canonical]
                qid = pages.get(canonical, {}).get("pageprops", {}).get("wikibase_item")
                if qid:
                    for subject in title_to_subjects[title]:
                        result[subject].add(qid)
    return result


def main() -> None:
    OUT.mkdir(exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()

    event_coverage = {}
    for key, query in {
        "warsampo_event_resources": "SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s a <http://ldf.fi/schema/warsa/Event> }",
        "event_resources_with_wikidata_sameas": f'SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {{ ?s a <http://ldf.fi/schema/warsa/Event> ; <{SAME_AS}> ?w . FILTER(CONTAINS(STR(?w), "wikidata.org")) }}',
        "event_resources_with_wikipedia_page": 'SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s a <http://ldf.fi/schema/warsa/Event> ; <http://xmlns.com/foaf/0.1/page> ?page . FILTER(CONTAINS(STR(?page), "wikipedia.org")) }',
    }.items():
        event_coverage[key] = int(sparql(query)[0]["n"])

    property_rows = sparql(
        "SELECT ?p (COUNT(*) AS ?n) WHERE { ?s ?p ?o . "
        "FILTER(isIRI(?s) && isIRI(?o)) } GROUP BY ?p ORDER BY DESC(?n)"
    )
    write_csv(
        "warsampo_predicates.csv",
        ["predicate", "iri_triples", "review_status"],
        [
            {"predicate": row["p"], "iri_triples": row["n"], "review_status": "pending"}
            for row in property_rows
        ],
    )

    links = sparql(
        f"SELECT DISTINCT ?s ?target WHERE {{ ?s <{SAME_AS}> ?target . "
        "FILTER(isIRI(?target)) }"
    )
    candidates: dict[str, set[str]] = defaultdict(set)
    bases: dict[tuple[str, str], set[str]] = defaultdict(set)
    direct_subjects = set()
    for row in links:
        if "wikidata.org" not in row["target"].lower():
            continue
        match = re.search(r"(?:^|[/#:])(Q[1-9][0-9]*)(?:$|[?#])", row["target"])
        if match:
            qid = match.group(1)
            candidates[row["s"]].add(qid)
            bases[(row["s"], qid)].add("owl:sameAs")
            direct_subjects.add(row["s"])
    unit_page_links = wikipedia_unit_links()
    for uri, values in unit_page_links.items():
        for qid in values:
            candidates[uri].add(qid)
            bases[(uri, qid)].add("Wikipedia page sitelink")
    for uri, qid in PERIODS.items():
        candidates[uri].add(qid)
        bases[(uri, qid)].add("period label and date review")

    subjects = sorted(candidates)
    labels: dict[str, list[str]] = defaultdict(list)
    types: dict[str, list[str]] = defaultdict(list)
    for group in chunks(subjects, 25):
        values = " ".join(f"<{uri}>" for uri in group)
        rows = sparql(
            f"SELECT ?s ?p ?o WHERE {{ VALUES ?s {{ {values} }} ?s ?p ?o . "
            f"FILTER(?p IN (<{PREF_LABEL}>, "
            "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)) }"
        )
        for row in rows:
            (labels if row["p"] == PREF_LABEL else types)[row["s"]].append(row["o"])

    qids = sorted({qid for values in candidates.values() for qid in values})
    entities: dict[str, dict] = {}
    for group in chunks(qids, 50):
        result = get_json(
            WD,
            {
                "action": "wbgetentities",
                "ids": "|".join(group),
                "props": "info|labels|descriptions|claims|sitelinks",
                "languages": "en|fi",
                "format": "json",
            },
        )
        entities.update(result["entities"])

    identity_rows = []
    screened: dict[str, str] = {}
    for uri in subjects:
        for qid in sorted(candidates[uri]):
            entity = entities.get(qid, {})
            status, reason = identity_screen(
                uri,
                qid,
                labels[uri],
                types[uri],
                entity,
                bases[(uri, qid)],
                len(candidates[uri]) > 1,
            )
            if status in {"screened", "reviewed"}:
                screened[uri] = qid
            identity_rows.append(
                {
                    "warsampo_uri": uri,
                    "wikidata_qid": qid,
                    "link_basis": "; ".join(sorted(bases[(uri, qid)])),
                    "warsampo_types": "; ".join(sorted(set(types[uri]))),
                    "warsampo_labels": "; ".join(sorted(set(labels[uri]))),
                    "wikidata_label_en": entity.get("labels", {})
                    .get("en", {})
                    .get("value", ""),
                    "wikidata_label_fi": entity.get("labels", {})
                    .get("fi", {})
                    .get("value", ""),
                    "wikidata_description_en": entity.get("descriptions", {})
                    .get("en", {})
                    .get("value", ""),
                    "wikidata_p31": "; ".join(item_values(entity, "P31")),
                    "wikidata_revision": entity.get("lastrevid", ""),
                    "review_status": status,
                    "review_reason": reason,
                }
            )
    write_csv("identity_candidates.csv", list(identity_rows[0]), identity_rows)

    source_pairs: dict[tuple[str, str, str], int] = Counter()
    incident_counts: Counter[str] = Counter()
    for group in chunks(subjects, 25):
        values = " ".join(f"<{uri}>" for uri in group)
        rows = sparql(
            f"SELECT ?s ?p ?o WHERE {{ VALUES ?s {{ {values} }} "
            "?s ?p ?o . FILTER(isIRI(?o)) }"
        )
        for row in rows:
            incident_counts[row["p"]] += 1
            if row["o"] in candidates:
                source_pairs[(row["s"], row["p"], row["o"])] += 1

    wd_pairs: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    wd_property_counts: Counter[str] = Counter()
    qid_set = set(qids)
    for qid, entity in entities.items():
        for property_id, statements in entity.get("claims", {}).items():
            for statement in statements:
                snak = statement["mainsnak"]
                value = snak.get("datavalue", {}).get("value", {})
                if (
                    snak.get("snaktype") != "value"
                    or not isinstance(value, dict)
                    or value.get("entity-type") != "item"
                ):
                    continue
                wd_property_counts[property_id] += 1
                if value["id"] in qid_set:
                    wd_pairs[(qid, property_id, value["id"])].append(
                        {
                            "id": statement["id"],
                            "rank": statement["rank"],
                            "qualifiers": sorted(statement.get("qualifiers", {})),
                            "references": len(statement.get("references", [])),
                        }
                    )

    mapped_source_pairs: dict[tuple[str, str, str], list[tuple[str, str]]] = (
        defaultdict(list)
    )
    for s, predicate, o in source_pairs:
        if len(candidates[s]) != 1 or len(candidates[o]) != 1:
            continue  # Ambiguous identities cannot vote for a mapping.
        mapped_source_pairs[
            (next(iter(candidates[s])), predicate, next(iter(candidates[o])))
        ].append((s, o))

    screened_source_pairs: dict[tuple[str, str, str], list[tuple[str, str]]] = (
        defaultdict(list)
    )
    for s, predicate, o in source_pairs:
        if s in screened and o in screened:
            screened_source_pairs[(screened[s], predicate, screened[o])].append((s, o))

    summaries: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {"shared_pairs": set(), "examples": []}
    )
    for (
        subject_qid,
        war_predicate,
        object_qid,
    ), source_ids in mapped_source_pairs.items():
        for direction, left, right in (
            ("same", subject_qid, object_qid),
            ("reverse", object_qid, subject_qid),
        ):
            for (wd_subject, wd_property, wd_object), statements in wd_pairs.items():
                if wd_subject != left or wd_object != right:
                    continue
                entry = summaries[(war_predicate, wd_property, direction)]
                entry["shared_pairs"].add((subject_qid, object_qid))
                if len(entry["examples"]) < 5:
                    entry["examples"].append(
                        {
                            "war_subject": source_ids[0][0],
                            "war_object": source_ids[0][1],
                            "wd_subject": wd_subject,
                            "wd_object": wd_object,
                            "wd_statement": statements[0],
                        }
                    )

    overlap_rows = []
    for (war_predicate, wd_property, direction), entry in sorted(summaries.items()):
        war_denominator = len(
            {(s, o) for s, p, o in mapped_source_pairs if p == war_predicate}
        )
        wd_denominator = len({(s, o) for s, p, o in wd_pairs if p == wd_property})
        overlap_rows.append(
            {
                "war_predicate": war_predicate,
                "wd_property": wd_property,
                "direction": direction,
                "shared_pairs": len(entry["shared_pairs"]),
                "eligible_war_pairs": war_denominator,
                "eligible_wd_pairs": wd_denominator,
                "examples": json.dumps(entry["examples"], ensure_ascii=False),
                "review_status": "provisional_identity_and_semantics",
            }
        )
    write_csv(
        "provisional_overlap.csv",
        (
            list(overlap_rows[0])
            if overlap_rows
            else [
                "war_predicate",
                "wd_property",
                "direction",
                "shared_pairs",
                "eligible_war_pairs",
                "eligible_wd_pairs",
                "examples",
                "review_status",
            ]
        ),
        overlap_rows,
    )
    screened_rows = []
    joint_rows = []
    shared_endpoint_pairs: set[tuple[str, str]] = set()
    screened_qids = set(screened.values())
    for row in overlap_rows:
        predicate, property_id, direction = (
            row["war_predicate"],
            row["wd_property"],
            row["direction"],
        )
        matches = []
        qualifier_ids: set[str] = set()
        time_qualified_pairs = 0
        for (s, p, o), source_ids in screened_source_pairs.items():
            if p != predicate:
                continue
            wd_s, wd_o = (s, o) if direction == "same" else (o, s)
            statements = [
                statement
                for statement in wd_pairs.get((wd_s, property_id, wd_o), [])
                if statement["rank"] != "deprecated"
            ]
            if statements:
                shared_endpoint_pairs.add((s, o))
                joint_rows.append(
                    {
                        "war_subject_uri": source_ids[0][0],
                        "war_subject_qid": s,
                        "war_predicate": predicate,
                        "war_object_uri": source_ids[0][1],
                        "war_object_qid": o,
                        "wd_subject_qid": wd_s,
                        "wd_property": property_id,
                        "wd_object_qid": wd_o,
                        "direction": direction,
                        "wd_statement_id": statements[0]["id"],
                    }
                )
                qualifiers = {
                    key for statement in statements for key in statement["qualifiers"]
                }
                qualifier_ids.update(qualifiers)
                time_qualified_pairs += bool(qualifiers & {"P580", "P582", "P585"})
                matches.append(
                    {
                        "war_subject": source_ids[0][0],
                        "war_object": source_ids[0][1],
                        "wd_subject": wd_s,
                        "wd_object": wd_o,
                        "wd_statement": statements[0],
                    }
                )
        screened_rows.append(
            {
                "war_predicate": predicate,
                "wd_property": property_id,
                "direction": direction,
                "shared_pairs": len(matches),
                "eligible_war_pairs": sum(
                    p == predicate for _, p, _ in screened_source_pairs
                ),
                "eligible_wd_pairs": sum(
                    p == property_id
                    and s in screened_qids
                    and o in screened_qids
                    and any(
                        statement["rank"] != "deprecated" for statement in statements
                    )
                    for (s, p, o), statements in wd_pairs.items()
                ),
                "time_qualified_pairs": time_qualified_pairs,
                "qualifier_ids": "; ".join(sorted(qualifier_ids)),
                "examples": json.dumps(matches[:5], ensure_ascii=False),
            }
        )
    write_csv("screened_overlap.csv", list(screened_rows[0]), screened_rows)
    write_csv("joint_relation_pairs.csv", list(joint_rows[0]), joint_rows)
    ranked_rows = rank_joint_rows(joint_rows)
    write_csv("type_mapping_ranking.csv", list(ranked_rows[0]), ranked_rows)
    write_csv(
        "wikidata_predicates.csv",
        ["property", "outgoing_item_statements", "eligible_pair_count"],
        [
            {
                "property": property_id,
                "outgoing_item_statements": count,
                "eligible_pair_count": len(
                    {(s, o) for s, p, o in wd_pairs if p == property_id}
                ),
            }
            for property_id, count in sorted(wd_property_counts.items())
        ],
    )
    manifest = {
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "warsampo_endpoint": WAR,
        "wikidata_api": WD,
        "wikidata_revision_policy": "per-item lastrevid in identity_candidates.csv; not one atomic snapshot",
        "warsampo_iri_predicates": len(property_rows),
        "warsampo_direct_wikidata_subjects": len(direct_subjects),
        "war_unit_wikipedia_sitelink_subjects": len(unit_page_links),
        "war_period_bridges": len(PERIODS),
        **event_coverage,
        "identity_candidate_rows": len(identity_rows),
        "identity_review_statuses": dict(
            Counter(row["review_status"] for row in identity_rows)
        ),
        "ambiguous_warsampo_identities": sum(
            len(values) > 1 for values in candidates.values()
        ),
        "screened_warsampo_identities": len(screened),
        "screened_warsampo_relation_pairs": len(screened_source_pairs),
        "screened_shared_endpoint_pairs": len(shared_endpoint_pairs),
        "war_outgoing_incident_predicates": len(incident_counts),
        "war_pairs_with_both_endpoints_crosswalked": len(mapped_source_pairs),
        "wikidata_outgoing_item_predicates": len(wd_property_counts),
        "wikidata_pairs_with_both_endpoints_crosswalked": len(wd_pairs),
        "provisional_predicate_matches": len(overlap_rows),
        "query_scope_limit": "direct sameAs actors, Wikipedia-linked units, and five period candidates; Wikidata outgoing claims only",
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
