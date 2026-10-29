"""Apply public Event eligibility and exact-revision article boundaries.

Native acquisition and source-bound consolidation live in post_qid_native.
Public discovery records an observation, never a common source snapshot.
"""

from __future__ import annotations

import csv
import re
from copy import deepcopy
from pathlib import Path

from GG_Data.pipeline.entities import native_record
from GG_Data.pipeline.event_model import event_rows
from GG_Data.pipeline.events import item_links
from GG_Data.pipeline.poc import digest, read_json
from GG_Data.pipeline.post_qid_native import (
    _consolidated_stage,
    _manifest_hash,
    _pin,
    _stage,
    _write_stage,
)
from GG_Data.pipeline.post_qid_relations import (
    build_relations,
    export_stored_relations,
    select_events,
)
from GG_Data.pipeline.relations import SourceException


def _bounded_scope(core: dict, pages: list[dict] | None = None) -> str:
    scope = core.get("scope")
    if scope not in {"3", "10", "100"}:
        raise ValueError("Expected manifest-bounded scope 3, 10 or 100")
    ids = core.get("page_ids")
    if ids is None:
        # Archived three-page fixtures predate explicit page membership.
        if scope != "3":
            raise ValueError("Expanded scope requires manifest page_ids")
        if pages is not None and not 0 < len({p["wiki_page_id"] for p in pages}) <= 3:
            raise ValueError("Article pages exceed bounded scope")
    elif (
        not isinstance(ids, list)
        or len(ids) != int(scope)
        or len(set(ids)) != len(ids)
        or any(type(p) is not int or p <= 0 for p in ids)
        or (pages is not None and {p["wiki_page_id"] for p in pages} != set(ids))
    ):
        raise ValueError("Article pages differ from manifest-bounded scope")
    return scope


def _occurrence_types(
    hierarchy: Path, approval_sha256: str
) -> tuple[set[str], list[Path]]:
    approval_path = hierarchy / "recognition_approval.json"
    _pin(approval_path, approval_sha256)
    approval = read_json(approval_path)
    if (
        approval["status"] != "RECOGNITION_RULE_ACCEPTED"
        or approval["root_qid"] != "Q1190554"
    ):
        raise ValueError("Expected pinned accepted occurrence recognition")
    type_path = hierarchy / "parameters/event_types.csv"
    _pin(type_path, _manifest_hash(approval, "parameter_hashes", "event_types.csv"))
    with type_path.open(encoding="utf-8-sig", newline="") as stream:
        types = {r["subtype_qid"] for r in csv.DictReader(stream)}
    if not types or any(not re.fullmatch(r"Q[1-9]\d*", q) for q in types):
        raise ValueError("Invalid pinned occurrence types")
    return types, [approval_path, type_path]


def _article_evidence(
    core_dir: Path, link_table: Path, collection_manifest: Path
) -> tuple:
    """Separate verified raw inventories from links that survive source cleaning."""
    import pyarrow.parquet as pq

    from GG_Data.entity_resolution.hundred_page_pilot.clean_source_text import (
        _clean_page,
        _passage,
        map_mention,
    )
    from GG_Data.entity_resolution.hundred_page_pilot.collect_entities import raw_links

    core = read_json(core_dir / "manifest.json")
    for name in ("entities.json.gz", "wiki_pages.json.gz"):
        _pin(core_dir / name, core["outputs"][name])
    page_rows = read_json(core_dir / "wiki_pages.json.gz")
    _bounded_scope(core, page_rows)
    entity_scope = [
        r
        for r in read_json(core_dir / "entities.json.gz")
        if re.fullmatch(r"Q[1-9]\d*", r["entity_id"])
    ]
    pages = {(r["wiki_page_id"], r["revision_id"]): r for r in page_rows}
    if len(pages) != len(page_rows):
        raise ValueError("Duplicate article revision identity")
    collection = read_json(collection_manifest)
    _pin(link_table, _manifest_hash(collection, "outputs", link_table.name))
    parsed, cleaned, starts, raw_inputs = {}, {}, {}, {}
    for key, page in pages.items():
        raw = page["raw_reference"]
        path = Path(raw["wikitext_path"])
        _pin(path, raw["sha256"])
        raw_inputs[str(path.resolve())] = raw["sha256"]
        text = path.read_text(encoding="utf-8")
        parsed[key] = {(r["raw_start"], r["raw_end"]): r for r in raw_links(text)}
        cleaned[key] = _clean_page(text)
        starts[key] = [a for a, _ in cleaned[key].origins]
    rows = pq.read_table(
        link_table, filters=[("page_id", "in", sorted({k[0] for k in pages}))]
    ).to_pylist()
    presence = []
    for row in rows:
        key = row["page_id"], row["revision_id"]
        if key not in pages or row["link_origin"] != "RAW_DIRECT_LINK":
            continue
        raw = pages[key]["raw_reference"]
        if (
            Path(row["raw_evidence_path"]).resolve()
            != Path(raw["wikitext_path"]).resolve()
            or row["raw_sha256"] != raw["sha256"]
        ):
            raise ValueError("Article raw link source differs from core revision")
        saved_link = parsed[key].get((row.get("raw_start"), row.get("raw_end")))
        if saved_link is None or any(
            row.get(field) != value for field, value in saved_link.items()
        ):
            raise ValueError("Saved raw link offsets/target metadata differ")
        if row.get("qid") and re.fullmatch(r"Q[1-9]\d*", row["qid"]):
            left, right = row["anchor_start"], row["anchor_end"]
            passage = _passage(cleaned[key], starts[key], left, right)
            span = map_mention(passage, 0, right - left)
            presence.append(
                dict(
                    row,
                    retained_content_link=span["status"] == "mapped",
                    clean_link_status=span["status"],
                    clean_link_reason=span["reason"],
                    clean_policy_version="source-text-v3",
                )
            )
    return core, entity_scope, presence, raw_inputs


def sparql_incoming_query(
    corpus_qids: set[str], *, live_hierarchy_prefilter: bool = False
) -> str:
    """Public live discovery only; raw mainsnaks, all factual assertion ranks.

    No hierarchy prefilter is complete with respect to the historical pinned
    class list. If the optional live filter is used, its output is an explicitly
    incomplete candidate set until its coverage is independently established.
    This function neither fetches nor claims source-snapshot consistency.
    """
    if not corpus_qids or any(not re.fullmatch(r"Q[1-9]\d*", q) for q in corpus_qids):
        raise ValueError("Expected corpus QIDs")
    recognition = (
        """
  ?event p:P31 ?classification .
  ?classification ps:P31 ?eventType ; wikibase:rank ?classificationRank .
  FILTER(?classificationRank IN (wikibase:NormalRank, wikibase:PreferredRank))
  ?eventType wdt:P279* wd:Q1190554 ."""
        if live_hierarchy_prefilter
        else ""
    )
    return f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT DISTINCT ?event ?corpus WHERE {{
  VALUES ?corpus {{ {" ".join("wd:" + q for q in sorted(corpus_qids))} }}
  ?property wikibase:claim ?claim ; wikibase:statementProperty ?valueProperty ;
            wikibase:propertyType wikibase:WikibaseItem .
  ?event ?claim ?statement .
  ?statement ?valueProperty ?corpus ; wikibase:rank ?rank .
  FILTER(STRSTARTS(STR(?event), 'http://www.wikidata.org/entity/Q')){recognition}
}}"""


def sparql_incoming_pairs(response: dict, corpus_qids: set[str]) -> list[dict]:
    """Validate loaded public query bindings; this does not prove completeness."""
    if "results" not in response or not isinstance(
        response["results"].get("bindings"), list
    ):
        raise ValueError("Expected SPARQL SELECT response")
    pairs = set()
    for binding in response["results"]["bindings"]:
        qids = []
        for name in ("event", "corpus"):
            node = binding.get(name, {})
            match = re.fullmatch(
                r"https?://www\.wikidata\.org/entity/(Q[1-9]\d*)", node.get("value", "")
            )
            if node.get("type") != "uri" or not match:
                raise ValueError("Invalid public discovery QID binding")
            qids.append(match[1])
        if qids[1] not in corpus_qids:
            raise ValueError("Public discovery binding outside corpus scope")
        pairs.add(tuple(qids))
    return [dict(event_qid=e, daniel_qid=d) for e, d in sorted(pairs)]


def _mapping(
    directory: Path, manifest_path: Path, expected_sha: str
) -> tuple[dict, dict]:
    _pin(manifest_path, expected_sha)
    manifest = read_json(manifest_path)
    if manifest["relation_map_version"] != "relation-map-v2.1.2":
        raise ValueError("Expected accepted mapping v2.1.2")
    exclusions = (
        Path(__file__).resolve().parents[1] / "mapping/ASSERTION_EXCLUSIONS.csv"
    )
    _pin(exclusions, _manifest_hash(manifest, "inputs", "ASSERTION_EXCLUSIONS.csv"))
    results = []
    for name, keys in (
        ("RELATION_MAPPING_TABLE_v2.1.2.csv", ("source", "source_predicate")),
        ("RELATION_DIRECTION_LOOKUP_v2.1.2.csv", ("input_relation_id",)),
    ):
        path = directory / name
        _pin(path, _manifest_hash(manifest, "mapping_artifacts", name))
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        result = {
            (tuple(row[k] for k in keys) if len(keys) > 1 else row[keys[0]]): row
            for row in rows
        }
        if len(result) != len(rows):
            raise ValueError("Duplicate mapping/direction keys")
        results.append(result)
    return tuple(results)


def _event_tables(record: dict, source: dict, decision: dict) -> tuple[dict, dict]:
    try:
        entity, event = event_rows(record, source, decision)
    except SourceException as error:
        # Legacy scalar date derivation can reject mixed calendars. Build the
        # ordinary shape, then restore all source evidence without scalar repair.
        stripped = deepcopy(record)
        for prop in ("P580", "P582", "P585"):
            stripped["claims"].pop(prop, None)
        entity, event = event_rows(stripped, source, decision)
        entity["raw_reference"]["full"]["entity"] = record
        temporal = {p: record["claims"].get(p, []) for p in ("P580", "P582", "P585")}
        for key, prop in (
            ("start_date", "P580"),
            ("end_date", "P582"),
            ("point_date", "P585"),
        ):
            event[key] = [
                s.get("mainsnak", {}).get("datavalue", {}).get("value")
                for s in temporal[prop]
            ]
        event["temporal_evidence"] = dict(
            claims=temporal,
            derived_range={},
            scalar_status="AMBIGUOUS",
            reason=error.case,
        )
    entity["reference_source"] = source.get("provider", "UNKNOWN")
    return entity, event


def apply_public_events(
    *,
    core_dir: Path,
    native_dir: Path,
    candidate_dir: Path,
    query: Path,
    query_sha256: str,
    response: Path,
    response_sha256: str,
    observed_at: str | None,
    hierarchy: Path,
    approval_sha256: str,
    mapping_dir: Path,
    mapping_manifest: Path,
    mapping_manifest_sha256: str,
    output: Path,
) -> dict:
    """Apply pinned public aggregate evidence and complete local outgoing union.

    The caller supplies the reviewed query hashes and actual observation time.
    Whole corpus versions take priority on overlap; no native fields are merged.
    Public discovery describes its observation, not a common or current snapshot.
    """
    if output.exists():
        raise FileExistsError(output)
    from datetime import datetime

    if (
        observed_at is not None
        and datetime.fromisoformat(observed_at.replace("Z", "+00:00")).tzinfo is None
    ):
        raise ValueError("SPARQL observation requires an explicit time zone")
    _pin(query, query_sha256)
    _pin(response, response_sha256)
    approval_path = hierarchy / "recognition_approval.json"
    _pin(approval_path, approval_sha256)
    approval = read_json(approval_path)
    if (
        approval["status"] != "RECOGNITION_RULE_ACCEPTED"
        or approval["root_qid"] != "Q1190554"
    ):
        raise ValueError("Expected pinned accepted occurrence recognition")
    type_path = hierarchy / "parameters/event_types.csv"
    _pin(type_path, _manifest_hash(approval, "parameter_hashes", "event_types.csv"))
    with type_path.open(encoding="utf-8-sig", newline="") as stream:
        types = {r["subtype_qid"] for r in csv.DictReader(stream)}
    if not types or any(not re.fullmatch(r"Q[1-9]\d*", q) for q in types):
        raise ValueError("Invalid pinned occurrence types")
    core = read_json(core_dir / "manifest.json")
    scope = _bounded_scope(core)
    _pin(core_dir / "entities.json.gz", core["outputs"]["entities.json.gz"])
    entity_scope = [
        r
        for r in read_json(core_dir / "entities.json.gz")
        if re.fullmatch(r"Q[1-9]\d*", r["entity_id"])
    ]
    qids = {r["entity_id"] for r in entity_scope}
    native, acquired = (
        _consolidated_stage(native_dir),
        _consolidated_stage(candidate_dir),
    )
    if native["counts"]["missing"] or acquired["counts"]["missing"]:
        raise ValueError("Missing full candidate or corpus records")
    envelopes = read_json(native_dir / "full_records.json.gz")
    sources = read_json(native_dir / "sources.json")
    candidates = read_json(candidate_dir / "full_records.json.gz")
    candidate_sources = read_json(candidate_dir / "sources.json")
    if set(envelopes) != qids or set(native["required_qids"]) != qids:
        raise ValueError("Core/native accepted QID scope differs")
    if (
        envelopes.keys() != sources.keys()
        or candidates.keys() != candidate_sources.keys()
    ):
        raise ValueError("Full record/provenance coverage differs")
    records = {q: native_record(e, q) for q, e in envelopes.items()}
    outgoing = {
        link["object_qid"] for record in records.values() for link in item_links(record)
    }
    sql = query.read_text(encoding="utf-8")
    corpus_match = re.findall(r"VALUES\s+\?corpus\s*\{([^}]+)\}", sql, re.I)
    outgoing_match = re.findall(r"\?event\s+IN\s*\(([^)]+)\)", sql, re.I)
    if (
        len(corpus_match) != 1
        or len(outgoing_match) != 1
        or set(re.findall(r"wd:(Q[1-9]\d*)", corpus_match[0])) != qids
        or set(re.findall(r"wd:(Q[1-9]\d*)", outgoing_match[0])) != outgoing
    ):
        raise ValueError("Reviewed query corpus/outgoing scope differs")
    saved = read_json(response)
    if set(saved.get("head", {}).get("vars", [])) != {
        "event",
        "corpus_values",
        "type_values",
    } or not isinstance(saved.get("results", {}).get("bindings"), list):
        raise ValueError("Expected complete SPARQL aggregate JSON")
    public_candidates, seen, observations = set(), set(), []

    def qid_uri(value: str) -> str:
        match = re.fullmatch(r"http://www\.wikidata\.org/entity/(Q[1-9]\d*)", value)
        if not match:
            raise ValueError("Invalid aggregate QID URI")
        return match[1]

    for row in saved["results"]["bindings"]:
        if row["event"].get("type") != "uri":
            raise ValueError("Invalid aggregate Event URI binding")
        qid = qid_uri(row["event"]["value"])
        neighbours = {qid_uri(v) for v in row["corpus_values"]["value"].split("|")}
        native_types = {qid_uri(v) for v in row["type_values"]["value"].split("|")}
        if (
            qid in seen
            or not neighbours <= qids
            or (len(neighbours) < 2 and qid not in outgoing)
        ):
            raise ValueError("Aggregate duplicate or out-of-scope binding")
        seen.add(qid)
        if native_types & types:
            public_candidates.add(qid)
            observations.append(
                dict(
                    qid=qid,
                    corpus_qids=sorted(neighbours),
                    observed_types=sorted(native_types),
                )
            )
    required = outgoing | public_candidates
    missing = required - candidates.keys() - envelopes.keys()
    if missing:
        raise ValueError(f"Missing full candidate records: {sorted(missing)}")
    overlaps = []
    for qid in sorted(required):
        if qid in candidates:
            native_record(candidates[qid], qid)
        if qid in envelopes:
            if qid in candidates and candidates[qid] != envelopes[qid]:
                overlaps.append(qid)
            continue
        envelopes[qid], sources[qid] = candidates[qid], candidate_sources[qid]
        records[qid] = native_record(envelopes[qid], qid)
    mapping, directions = _mapping(
        mapping_dir, mapping_manifest, mapping_manifest_sha256
    )
    selection = select_events(records, qids, types, mapping)
    selected = set(selection["selected_event_qids"])
    relations = build_relations(
        records,
        entity_scope + [dict(entity_id=q, type="event") for q in sorted(selected)],
        mapping,
        directions,
        sources={q: [s] for q, s in sources.items()},
    )
    decisions = {r["qid"]: r for r in selection["decisions"]}
    event_entities, events = [], []
    for qid in sorted(selected):
        entity, event = _event_tables(records[qid], sources[qid], decisions[qid])
        event_entities.append(entity)
        events.append(event)
    edges = export_stored_relations(relations["relations"])
    inputs = [
        core_dir / "manifest.json",
        native_dir / "receipt.json",
        candidate_dir / "receipt.json",
        query,
        response,
        approval_path,
        type_path,
        mapping_manifest,
    ]
    return _write_stage(
        output,
        {
            "full_records.json.gz": envelopes,
            "sources.json": sources,
            "event_decisions.json": selection["decisions"],
            "public_observations.json": observations,
            "events.json.gz": events,
            "event_entities.json.gz": event_entities,
            "relations.json.gz": relations["relations"],
            "excluded_relations.json.gz": relations["excluded"],
            "unknown_predicates.json.gz": relations["unknown_predicates"],
            "graph_edges.json.gz": edges,
        },
        dict(
            status="NATIVE_EVENT_RELATIONS_READY",
            phase="PUBLIC_APPLY",
            scope=scope,
            counts=dict(
                corpus_qids=len(qids),
                outgoing_targets=len(outgoing),
                aggregate_rows=len(seen),
                public_candidates=len(public_candidates),
                required_candidate_qids=len(required),
                events=len(events),
                relation_base_assertions=relations["counts"]["base_assertions"],
                stored_directed_rows=len(relations["relations"]),
                exported_edges=len(edges),
            ),
            inputs={str(p.resolve()): digest(p) for p in inputs},
            sparql_observed_at=observed_at,
            selection_policy="CORPUS_WHOLE_RECORD_PRIORITY",
            differing_overlap_qids=overlaps,
            temporal_basis="MIXED_WHOLE_RECORD_VERSIONS_NO_COMMON_SNAPSHOT",
            event_discovery_completeness="SPARQL_OBSERVATION_AND_LOCAL_OUTGOING_UNION_ONLY",
            relation_policy=relations["policy_version"],
            acquisition_executed=False,
        ),
    )


def apply_cached_events(
    *,
    core_dir: Path,
    native_dir: Path,
    link_table: Path,
    collection_manifest: Path,
    hierarchy: Path,
    approval_sha256: str,
    mapping_dir: Path,
    mapping_manifest: Path,
    mapping_manifest_sha256: str,
    output: Path,
) -> dict:
    """Build article-bound Events and closed native Relations without acquisition.

    Missing corpus or retained-link native records produce a blocked cache-gap
    receipt, never a complete snapshot. Whole records and historical provenance
    are reused unchanged from the validated consolidation.
    """
    if output.exists():
        raise FileExistsError(output)
    core, entity_scope, presence, raw_inputs = _article_evidence(
        core_dir, link_table, collection_manifest
    )
    scope = _bounded_scope(core)
    _consolidated_stage(native_dir)
    envelopes = read_json(native_dir / "full_records.json.gz")
    sources = read_json(native_dir / "sources.json")
    if envelopes.keys() != sources.keys():
        raise ValueError("Full record/provenance coverage differs")
    corpus = {r["entity_id"] for r in entity_scope}
    linked = {r["qid"] for r in presence if r["retained_content_link"]}
    missing_corpus = sorted(corpus - envelopes.keys())
    missing_article = sorted(linked - envelopes.keys())
    types, recognition_inputs = _occurrence_types(hierarchy, approval_sha256)
    mapping, directions = _mapping(
        mapping_dir, mapping_manifest, mapping_manifest_sha256
    )
    inputs = [
        core_dir / "manifest.json",
        native_dir / "receipt.json",
        link_table,
        collection_manifest,
        mapping_manifest,
        *recognition_inputs,
    ]
    receipt = dict(
        status="ARTICLE_NATIVE_CACHE_INCOMPLETE"
        if missing_corpus or missing_article
        else "NATIVE_EVENT_RELATIONS_READY",
        phase="CACHED_ARTICLE_EVENT_RELATIONS",
        scope=scope,
        missing_corpus_qids=missing_corpus,
        missing_article_qids=missing_article,
        inputs={**raw_inputs, **{str(p.resolve()): digest(p) for p in inputs}},
        article_policy="ACCEPTED_CORPUS_OR_RETAINED_DIRECT_LINK_IN_EXACT_USED_REVISIONS",
        qid_mapping_temporal_basis="SAVED_CACHED_OR_CURRENT_ASSIGNMENTS_NOT_HISTORICAL_IDENTITY_PROOF",
        temporal_basis="MIXED_WHOLE_RECORD_VERSIONS_NO_COMMON_SNAPSHOT",
        event_discovery_completeness="PROVIDED_CACHE_AND_RETAINED_ARTICLE_LINKS_ONLY",
        acquisition_executed=False,
    )
    values = {
        "article_presence_evidence.json": presence,
        "native_cache_gaps.json": dict(
            corpus=missing_corpus, retained_article=missing_article
        ),
    }
    if missing_corpus or missing_article:
        receipt["counts"] = dict(
            corpus_qids=len(corpus),
            retained_link_qids=len(linked),
            missing=len(set(missing_corpus + missing_article)),
        )
        return _write_stage(output, values, receipt)
    required = corpus | linked
    records = {q: native_record(envelopes[q], q) for q in sorted(required)}
    selection = select_events(records, corpus, types, mapping)
    event_entities, event_table = [], []
    for decision in selection["decisions"]:
        qid = decision["qid"]
        decision["native_neighbour_eligible"] = decision["keep_event"]
        # Accepted corpus identities already exist; added identities also need
        # both native eligibility and retained saved-revision article evidence.
        decision["keep_event"] = qid in corpus or (
            decision["keep_event"] and qid in linked
        )
        decision["article_presence_reason"] = (
            "ACCEPTED_CORPUS_QID"
            if qid in corpus
            else "RETAINED_DIRECT_LINK_IN_USED_REVISION"
        )
        if decision["keep_event"]:
            entity, event = _event_tables(records[qid], sources[qid], decision)
            entity["article_presence_source"] = (
                "accepted_corpus_qid" if qid in corpus else "retained_content_link"
            )
            event_entities.append(entity)
            event_table.append(event)
    selected = {e["event_id"] for e in event_table}
    relations = build_relations(
        records,
        entity_scope + [dict(entity_id=q, type="event") for q in sorted(selected)],
        mapping,
        directions,
        sources={q: [sources[q]] for q in records},
    )
    edges = export_stored_relations(relations["relations"])
    values.update(
        {
            "full_records.json.gz": {q: envelopes[q] for q in sorted(required)},
            "sources.json": {q: sources[q] for q in sorted(required)},
            "event_decisions.json": selection["decisions"],
            "events.json.gz": event_table,
            "event_entities.json.gz": event_entities,
            "relations.json.gz": relations["relations"],
            "excluded_relations.json.gz": relations["excluded"],
            "unknown_predicates.json.gz": relations["unknown_predicates"],
            "graph_edges.json.gz": edges,
        }
    )
    receipt.update(
        relation_policy=relations["policy_version"],
        counts=dict(
            corpus_qids=len(corpus),
            retained_link_qids=len(linked),
            verified_raw_link_rows=len(presence),
            retained_content_link_rows=sum(
                r["retained_content_link"] for r in presence
            ),
            events=len(selected),
            corpus_events=len(selected & corpus),
            added_events=len(selected - corpus),
            relation_base_assertions=relations["counts"]["base_assertions"],
            stored_directed_rows=len(relations["relations"]),
            exported_edges=len(edges),
        ),
    )
    return _write_stage(output, values, receipt)


def restrict_events_to_articles(
    core_dir: Path,
    event_dir: Path,
    link_table: Path,
    collection_manifest: Path,
    mapping_dir: Path,
    mapping_manifest: Path,
    mapping_manifest_sha256: str,
    output: Path,
) -> dict:
    """Keep accepted corpus Events and Events directly linked in used revisions.

    Raw revision presence is verified. Saved cached/current title-QID assignments
    remain observations; this does not establish historical title-QID identity.
    """
    if output.exists():
        raise FileExistsError(output)
    core, entity_scope, presence, raw_inputs = _article_evidence(
        core_dir, link_table, collection_manifest
    )
    broad = _stage(event_dir)
    scope = _bounded_scope(core)
    if broad["scope"] != scope:
        raise ValueError("Article and native Event scopes differ")
    for filename, expected in broad.get("inputs", {}).items():
        _pin(Path(filename), expected)
    corpus = {r["entity_id"] for r in entity_scope}
    linked = {r["qid"] for r in presence if r["retained_content_link"]}
    events = read_json(event_dir / "events.json.gz")
    broad_qids = {r["event_id"] for r in events}
    retained = broad_qids & (corpus | linked)
    decisions = []
    for original in read_json(event_dir / "event_decisions.json"):
        decision = dict(original)
        qid = decision["qid"]
        decision["broad_keep_event"] = original["keep_event"]
        decision["keep_event"] = qid in retained
        decision["article_presence_reason"] = (
            "ACCEPTED_CORPUS_QID"
            if qid in corpus
            else (
                "RETAINED_DIRECT_LINK_IN_USED_REVISION"
                if qid in linked
                else "NO_DIRECT_LINK_IN_USED_REVISIONS"
            )
        )
        decisions.append(decision)
    envelopes = read_json(event_dir / "full_records.json.gz")
    sources = read_json(event_dir / "sources.json")
    records = {q: native_record(value, q) for q, value in envelopes.items()}
    mapping, directions = _mapping(
        mapping_dir, mapping_manifest, mapping_manifest_sha256
    )
    relations = build_relations(
        records,
        entity_scope + [dict(entity_id=q, type="event") for q in sorted(retained)],
        mapping,
        directions,
        sources={q: [source] for q, source in sources.items()},
    )
    edges = export_stored_relations(relations["relations"])
    inputs = [
        core_dir / "manifest.json",
        event_dir / "receipt.json",
        link_table,
        collection_manifest,
        mapping_manifest,
    ]
    return _write_stage(
        output,
        {
            "full_records.json.gz": envelopes,
            "sources.json": sources,
            "article_presence_evidence.json": presence,
            "event_decisions.json": decisions,
            "events.json.gz": [e for e in events if e["event_id"] in retained],
            "event_entities.json.gz": [
                e
                for e in read_json(event_dir / "event_entities.json.gz")
                if e["entity_id"] in retained
            ],
            "relations.json.gz": relations["relations"],
            "excluded_relations.json.gz": relations["excluded"],
            "unknown_predicates.json.gz": relations["unknown_predicates"],
            "graph_edges.json.gz": edges,
        },
        dict(
            status="NATIVE_EVENT_RELATIONS_READY",
            phase="ARTICLE_EVENT_BOUNDARY",
            scope=scope,
            counts=dict(
                corpus_qids=len(corpus),
                broad_events=len(broad_qids),
                events=len(retained),
                corpus_events=len(retained & corpus),
                added_events=len(retained - corpus),
                excluded_broad_events=len(broad_qids - retained),
                verified_raw_link_rows=len(presence),
                retained_content_link_rows=sum(
                    r["retained_content_link"] for r in presence
                ),
                relation_base_assertions=relations["counts"]["base_assertions"],
                stored_directed_rows=len(relations["relations"]),
                exported_edges=len(edges),
            ),
            inputs={**raw_inputs, **{str(p.resolve()): digest(p) for p in inputs}},
            article_policy="ACCEPTED_CORPUS_OR_RETAINED_DIRECT_LINK_IN_EXACT_USED_REVISIONS",
            qid_mapping_temporal_basis="SAVED_CACHED_OR_CURRENT_ASSIGNMENTS_NOT_HISTORICAL_IDENTITY_PROOF",
            temporal_basis=broad["temporal_basis"],
            sparql_observed_at=broad.get("sparql_observed_at"),
            event_discovery_completeness="BROAD_NATIVE_ELIGIBILITY_RESTRICTED_TO_VERIFIED_ARTICLE_PRESENCE",
            relation_policy=relations["policy_version"],
            acquisition_executed=False,
        ),
    )
