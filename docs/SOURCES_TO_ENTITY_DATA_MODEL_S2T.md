# Source-to-target: approved sources to the six-table data model

Specification date: 19 October 2026. Status: approved source scope and rules documented; required implementation exceptions remain explicit. This document does not execute acquisition, matching, table population, geocoding, or graph export.

**Target:** [Entities, Mentions, Wiki Pages, Geography, Events, Relations](ENTITY_DATA_MODEL_ERD.md). This is the population S2T. The separate [model-to-Agent graph JSON S2T](ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md) starts after these tables. The ERD dictionaries and exact contract inventories form part of this specification; every input field and nested evidence payload must remain recoverable.

## 1. Approved sources and saved inputs

| Source / artifact | Approved use | Boundary |
|---|---|---|
| Daniel input, `Data/external/daniel_20261017.parquet` | Original mention population and unchanged extraction fields. | No new mentions, splitting, combining, or independent text extraction. |
| Completed matching run, `C:\Users\User\.cache\geoai_full_daniel_dump_bigquery_parallel_20261019` | Reuse assignments, attempts, dates, type decisions, page lookups, reference evidence and manifests. | Population does not rerun or revise matching. |
| Saved Wikidata references; approved BigQuery table `bigquery-public-data.wikipedia.wikidata` | Labels, aliases, native types/hierarchy, full statements, events and provenance for relevant QIDs. Reuse saved results before retrieving missing data. | Compact matching metadata is not a complete assertion/date store. Full `item` JSON or full saved entity records are needed for claims, ranks, qualifiers and references. |
| Official English/Japanese Wikimedia dumps and saved page resolution | Article page IDs, redirects, subject QIDs, sitelinks and page/link evidence. | Dump links may include templates/navigation. They are not proof of a particular Daniel extraction revision or all entities in prose. |
| Versioned relation catalogs and exact assertion exclusions | Reuse relation-map-v2.1.0 semantics, direction and temporal mappings. | Catalog coverage does not authorize new fact sources or resolve unknown predicates. |
| OHM, OSM, WHG and GeoNames under `geo-object-selection-v0.5.0` | Geometry acquisition and identity evidence under the existing source/selection policy. | Wikidata is identity/context only, not a selected geometry source. WHG has a restricted reconciliation role. |

WarSampo is excluded from this workflow by the user's latest instruction. EventKG is not an approved event/assertion acquisition source for this population phase. Catalog rows mentioning either provider remain mapping definitions; they do not authorize importing their facts. Do not import all nodes/events from an older graph merely because they are cached.

### Pinned lineage and known coverage

- Daniel source commit: `43e35453421b032fc67d426d7d16fe436574b0fa`; file `Data/georag_selected_v2_full_n36335_r482092353_20261016.parquet` in the shared repository. Saved input SHA-256: `dcd51dfa237b63378279ced4f9739a45d8cf8ce3991579f20848295448f83f16`.
- Matching reference manifest: provider `BIGQUERY_GCP_CLI`, Wikidata snapshot acquisition recorded at `2026-10-18T18:45:19.304197+00:00`, page dump `20261001`. Retain the full manifest, actual table metadata, request/job evidence and hashes; an acquisition timestamp is not an item's modification time.
- Original input columns: `entity_group, score, word, start, end, Source, Index, Text, subtype`.
- Saved run summary: **309,864 mentions**, **238,789 QID assignments**, **29,969 normalized dates**, **41,106 unresolved synthetic assignments**, **56,631 distinct matched QIDs**. These are saved matching counts, not counts of physical model tables.
- Stages: `PAGE_DIRECT_WIKIDATA=230492`, `ALREADY_MATCHED=6892`, `FRESH_WWII=1405`, `DATE_NORMALIZED=29969`, `SYNTHETIC=41106`.
- Unresolved reasons: `NO_NAME_ABOVE_THRESHOLD=25524`, `TYPE_MISMATCH=5064`, `TYPE_UNKNOWN=2055`, `INVALID_OR_UNSUPPORTED_DATE=8463`. Preserve each reason for later analysis; synthetic does not mean absent from Wikidata.
- Source page requests: 428; saved summary resolves 424 and reports four missing. Keep counterpart and article counts under their original manifest/summary definitions; request counts are not a deduplicated Wiki Pages row count.
- The previous fresh-WWII matching scope requested 103,235 QIDs, with 82,100 available in the reference and 21,135 missing. Preserve that limitation. It is not a restriction on the newly approved event hierarchy or permission to substitute another matching population.

Relevant matching artifacts are `matches.json.gz`, `matches.csv.gz`, `entity_metadata.json.gz`, `page_matches.json.gz`, `page_status.json`, `pages/`, `candidate_evidence.json.gz`, `daniel_name_lookups.json.gz`, `world.json.gz`, `reference_manifest.json`, `request_evidence.json.gz`, `summary.json`, and `manifest.json`. Full saved entity envelopes such as `Data/external/wwii_task_force/wikidata_entities.jsonl.gz` can supply relevant QIDs if their evidence/version is verified; unrelated old records do not enter the population.

## 2. Population sequence and identity limits

1. Verify the pinned input and completed matching manifest/output hashes. Preserve original rows and saved decisions.
2. Populate Mentions and resolved Wiki Pages from those artifacts. Missing lookups remain explicit; no fabricated page rows.
3. Populate Entities for existing mention QIDs and existing per-mention synthetic IDs. Successfully normalized dates stay structured in Mentions, with null entity FK.
4. Reuse or acquire complete Wikidata statements and metadata. Collect both outgoing and incoming item-valued assertions relevant to Daniel's matched QIDs; outgoing-only retrieval cannot establish event coverage. Save snapshots, query scope, results and misses for reuse.
5. Discover event items through Wikidata's approved native hierarchy, then retain events with direct mapped links to at least two distinct matched Daniel QIDs. Add their original QIDs to Entities and Events.
6. Populate Relations with Wikidata assertions between matched Daniel QIDs and the included-event/Daniel links. Apply approved exclusions and versioned mappings. Keep every eligible source statement, rather than one predicate per entity pair.
7. Apply the existing geometry selection policy to confirmed place QIDs in the included identity population. Save accepted Shapely geometry and all attempts/evidence.
8. Verify table keys, source-field coverage, population accounting and visible exceptions before any model-to-graph export.

Let **D** be the distinct existing matched Wikidata QIDs from Daniel's original non-DATE mentions. Let **E** be qualifying Wikidata event QIDs. Adding E does not expand D, trigger recursive event discovery through other events, or create extra Daniel mentions. Synthetic IDs cannot satisfy event inclusion or acquire Wikidata statements through a guessed QID. Unresolved DATE placeholders retain their existing synthetic identity and reason in the model; temporal-only records are not the graph's Daniel entity population.

## 3. Reused matching logic: no new matching run

The saved run already applies the agreed stages:

1. Resolve each source page and retrieve its Japanese counterpart where available. Use page-linked Wikidata names plus the saved exact label/alias lookup for Daniel names. The first pool is not strictly page-only.
2. Choose the highest character-trigram Dice similarity at **>=0.80**, with compatible types. Reuse the saved single-type override rule and its metadata when applicable. Ties reuse the recorded seeded random choice (`20261018`), not a new choice at population time.
3. After all page passes, freeze their matched QID pool. Match remaining mentions against that already-matched pool; then use the saved fresh-WWII reference pool under the same threshold/type rules.
4. Retain an existing separate synthetic ID for every still-unresolved mention, including the distinct type/date failure prefixes. Repeated unresolved names do not merge their synthetic IDs.
5. Reuse the saved DATE parser result and precision/error, not fuzzy name matching. Leading/trailing space and symbol normalization remains a comparison-only operation within the page stage; preserve the original word. Do not introduce title stripping or cross-stage cleanup that changes saved assignments.

The existing code and saved attempts are the implementation evidence: [bilingual matching](../GG_Data/entity_resolution/bilingual_page_pilot.py), [direct matching](../GG_Data/entity_resolution/direct_wikidata_pilot.py). No candidate name becomes a new Daniel mention.

## 4. Mentions: source-to-column mapping

Join original rows to saved matching rows by the existing `input_row_number` and validate the saved `mention_id` and raw input. Do not join by name alone.

| Target column(s) | Source and population rule |
|---|---|
| `mention_id`, `input_row_number` | Exact saved stable identifier and original row position. Preserve one row per input row. |
| `word`, `entity_group`, `subtype`, `start`, `end`, `Source`, `Index`, `Text` | Exact original Daniel values. `Index`/`Text` are legacy raw fields only; no paragraph object, join, assembly or processing is added. |
| `ner_score` | Daniel input `score`. Never replace it with matching similarity. |
| `raw` | Entire original row, including all nine original columns and any future supplied page fields, under their original names. |
| `assigned_id` | Saved matching decision, including QID, existing `SYN_...`, or `DATE:...`. |
| `entity_id` | QID/SYN assignment; null for successful `DATE_NORMALIZED`. An unresolved DATE retains its existing SYN placeholder. |
| `matched_stage`, `matched_name`, `match_score` | Saved matching fields; `match_score` is output `score`. |
| `type_metadata` | Complete saved `original_type`, `resolved_type`, `type_changed`, `type_source`, `wikidata_mapped_types`, `wikidata_direct_types` and extra fields. |
| `attempts`, `unresolved_reason`, `date` | Full nested attempts/rejections/ties, exact reason, and structured date `{value, precision, qualifier, error}`. Retain explicit nulls and unknown fields. |
| `wiki_site`, `wiki_page_id` | Future supplied page key when verified; current run uses saved article lookup. Both present or both null. |
| `page_id_source`, `page_resolution` | `INPUT` or `LOOKUP` according to actual origin; retain source resolution, redirects, status, failures and lookup version. Do not silently resolve a future input/lookup conflict. |
| `resolution_run_id` | Reference to the pinned manifest containing decision parameters, code hashes and snapshots. |

All existing nested attempt fields and the exact 16-column matching CSV compatibility view in the ERD remain covered. No name/type correction is applied during this copy.

## 5. Wiki Pages: source-to-column mapping

| Target column(s) | Source and population rule |
|---|---|
| `wiki_site`, `wiki_page_id` | Saved article `pageid`/`article_pageid`, scoped to enwiki/jawiki. Composite PK. Talk-page IDs and Daniel `Index` are not article IDs. |
| `language`, `title`, `url` | Saved resolved article values and site identity. |
| `requested_titles` | Retain all original request variants associated with that resolved key. Several requests may share one row. |
| `wikidata_qid` | Saved subject QID, separate from the numeric page ID. It does not identify all entities mentioned on the page. |
| `about_entity_id` | Subject QID only if already in Entities; otherwise null. Do not add an entity merely because it is a page subject. |
| `revision_id`, `revision_timestamp`, `revision_url` | Saved verified revision evidence only; absent values stay null. Dump date does not establish revision or Daniel extraction version. |
| `counterpart_site`, `counterpart_page_id` | Verified retrieved counterpart key; not the English page's numeric ID reused for Japanese. |
| `evidence_source`, `dump_date`, `links_updated`, `link_scope` | Exact saved retrieval/link evidence. Preserve the SQL-dump coverage limitations. |
| `reference_payload`, `lookup_evidence` | Full page payload and full `source_resolution`, redirects, legacy talk/article lookup fields and checkpoints, or immutable references with record locators. No new text extraction. |

Retain retrieved Japanese pages even without Daniel mentions. A missing source page creates no Wiki Pages row; the mention retains its original Source and explicit failure. Request diagnostics and unresolved requests remain supporting evidence. Future Daniel input should supply `wiki_site` and article `wiki_page_id`; more specific URL/revision evidence is a recorded upstream follow-up, not an instruction to contact Daniel.

## 6. Entities: source-to-column mapping

| Target column(s) | Source and population rule |
|---|---|
| `entity_id` | Distinct saved QID/SYN assignments plus included event QIDs. Reuse original IDs. Candidate/hierarchy QIDs used only as reference evidence do not become entity rows. |
| `name` | First available Wikidata English label, then Japanese label, then Daniel's original name. A synthetic row uses its own mention's original name. Record the chosen source/language and fallback evidence in `attributes`/raw provenance. |
| `type` | Reuse the saved matching `resolved_type` when consistent for the QID. Preserve original Daniel type and Wikidata override evidence. Included event role comes from Events membership, never Daniel MISC. Conflicting canonical types require a visible exception before selection. |
| `labels`, `descriptions`, `sitelinks` | All available original language-keyed Wikidata values, including English/Japanese; do not translate or synthesize. |
| `aliases`, `alias_details` | Supplied labels/aliases and original mention forms with their actual provider, record ID, kind and known language. No generated nicknames, romanization or combined names. |
| `identity_status`, `review_status` | Distinguish saved QID assignment from synthetic unresolved identity and actual review evidence. An automatic match is not a manual verification. |
| `direct_types`, `parents` | Saved P31/P279 evidence, retaining its version/provenance. Hierarchy traversal does not imply an entity population expansion. |
| `revision`, `modified`, `missing`, `reference_source` | Saved reference version/state/provider; `missing` means retrieval missing, not proof of Wikidata absence. |
| `sources`, `raw_reference` | Complete original metadata/entity envelope or immutable artifact reference, including requested QID, full claims, ranks, qualifiers, references and unknown fields. |
| `attributes` | Only supplied values/evidence: kind/country/scale, P879 hull numbers, P729/P730 commissioning/decommissioning dates, and other already-supplied attributes. No new inferred values. |
| `text`, `embedding` | Optional existing fields only; current population adds no paragraph-derived text or embedding generation. |

The approved name order supersedes a simple copy of the compact metadata's selected `label`. If English and Japanese labels are absent and one QID has different Daniel names, show the exact names/QID before choosing a canonical fallback. An event without an English/Japanese label and without a Daniel mention has no approved final fallback. Do not invent a QID-as-name or select a first/most-frequent name silently.

## 7. Events: discovery, inclusion and fields

### Native hierarchy and inclusion

The approved root is Wikidata's broad [event, Q140451665](https://www.wikidata.org/wiki/Q140451665), including all classes below it through native [P279 subclass-of](https://www.wikidata.org/wiki/Property:P279) statements. Identify event instances through [P31 instance-of](https://www.wikidata.org/wiki/Property:P31) and those subclass paths. Record root QID, snapshot, native class IDs and path evidence. Do not replace it with the narrower organized-event root, add a local event-type whitelist, or invent war/campaign/battle levels.

For each discovered event QID, use its direct mapped Wikidata assertions to/from **D**. Include it only if at least two distinct Daniel QIDs qualify. Repeated mentions, several predicates for one entity, duplicate retrievals and generated reverse views do not increase this count. Classification hierarchy paths identify an event; they do not count as indirect participant paths. Do not count mere shared class ancestry or article co-mentions as an event/entity connection.

Use all event types under the root. No additional date, geography or old-reference-pool filter is introduced. Do not promote an event class into an occurrence merely because it is a class in the hierarchy. Save candidate QIDs, classification evidence, direct qualifying statement IDs, distinct connected Daniel QIDs/count, inclusion decision and acquisition coverage in a supporting report. No seventh participant table is needed.

| Target column(s) | Source and population rule |
|---|---|
| `event_id` | Included native Wikidata QID; same key as its Entities row. |
| `kind` | Native supplied classification values/QIDs with evidence. No internal category/level conversion. Preserve multiple values; report scalar-target incompatibility. |
| `start_date`, `end_date`, `point_date` | Supplied Wikidata P580, P582, P585 values respectively. Retain all values, precision/calendar and evidence; do not select a preferred date or infer start/end from other properties. |
| `temporal_evidence` | Complete relevant claims, rank, qualifiers, references, precision, calendar and conflicts, including missing values. |
| `event_map_version` | Null/reserved; no internal event mapping catalog is approved. The native hierarchy root/snapshot belongs in supporting lineage. |
| `importance`, `attributes` | Supplied values with basis only; no invented ranking, role or event level. Missing optional values remain null. |

Native multivalued classifications/dates must fit a lossless model representation. The ERD's scalar diagram is an overview; required scalar Agent fields with incompatible values remain explicit integration exceptions. No ranking or flattening is approved.

## 8. Relations: scope, mapping and fields

### Eligible assertions

- Current fact provider is **Wikidata**. Retain item-to-item source assertions where both endpoints belong to D, plus direct included-event/D links in either source direction. Both event/entity and entity/event source statements are covered.
- Include every available predicate, subject to the existing exact exclusions and versioned mapping. Do not restrict to the earlier saved assertion file. Unknown mappings are reported, not silently dropped or assigned a guessed predicate.
- All retrieved ranks, qualifiers, references, literals, somevalue and novalue remain raw evidence. The latest "any assertion" scope does not authorize the legacy producer's silent deprecated-rank skip. Do not select only a preferred statement as a substitute for preserving all eligible assertions.
- Non-item values cannot satisfy the two-entity relation filter or event threshold; keep them in raw claims/audit without manufacturing entity rows. The nullable object fields remain available in the model contract.
- Event/event assertions are not added merely because both events were included. They qualify only if they independently meet the approved D/D or E/D endpoint rule. No other endpoint expansion, transitive relation, or synthetic participation is allowed.
- Apply the 14 approved exact source-record/predicate/original-endpoint exclusions before mapping; retain excluded records and reasons. Do not blanket-remove self-links.

Resolve the mapping by exact source/predicate key and version in [RELATION_MAPPING_TABLE_v2.1.0.csv](../GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.0.csv). `direction_to_level2` supplies same/reverse endpoint normalization, once. For a legacy v1 row, reconstruct source orientation before v2.1 normalization. Do not transform an already transformed pair twice. Unknown or ambiguous keys require a visible case report and discussion before a new mapping.

| Target column(s) | Source and population rule |
|---|---|
| `observation_id` | Existing assertion ID where present. Fresh assertions reuse the established relation producer's stable source-statement identity recipe; do not derive identity from endpoints/predicate alone. Repeated retrieval of the same statement is not new evidence. |
| `subject_entity_id`, `object_entity_id` | Source item IDs normalized once by the versioned direction mapping, after scope/exclusion checks. Require existing Entities endpoints. |
| `object_value` | Original non-item/somevalue/novalue payload when retained as supporting assertion evidence, never a fabricated QID. |
| `level2_relation`, `level2_label` | Catalog `level2_relation_id` and exact label, preserving case. |
| `level1_relation`, `level1_assignment_status` | Exact versioned family and assignment status; no family inference. |
| `selection_priority`, `selection_status`, `direction` | Existing catalog/producer outputs, with original values retained. Do not claim a review for newly retrieved statements. |
| `time_from`, `time_to`, `time_point`, `time_precision`, `time_status` | Existing producer and catalog `time_*_input`, `time_join_rule`, `time_conflict_policy` behavior. Preserve original qualifier P580/P582/P585 evidence and all conflicts. No new temporal ranking. |
| `selected_source`, `selected_source_predicate` | Wikidata provider key and original Wikidata property, not a generated reverse predicate. |
| `source_record_id`, `source_graph`, `source_reference` | Native statement ID and actual saved source graph/reference. Absent optional provenance stays absent; do not invent a source graph. |
| `source_support`, `evidence_references`, `sources` | All supporting statements, original endpoints, references, qualifiers, ranks and retrieval evidence. Only verified page citations are used; no paragraph citations are generated. |
| `final_review_status`, `final_mapping_class`, `mapping_origin` | Actual existing mapping/review evidence. Prior catalog review is not review of a new statement or its historical truth. |
| `relation_map_version` | Applied `relation-map-v2.1.0`, tied to catalog hashes. Old outputs are not relabeled without replay. |
| `input_assertion` | Preserve all 26 legacy assertion columns and complete raw statement/envelope, or an immutable artifact reference. New-source fields absent from a legacy producer remain explicit, not fabricated. |
| `count` | 1 per retained base source assertion, not mention frequency. |
| `attributes`, `embedding` | Supplied qualifier/side/extra payload and existing embedding only. Do not invent participant roles or compute embeddings. |

One source assertion produces one base row. Bidirectional graph navigation is supplied by the separate exporter using the [direction lookup](../GG_Data/mapping/RELATION_DIRECTION_LOOKUP_v2.1.0.csv) and `source_edge_id`. A generated reverse view is not a second independent assertion. Two genuinely separate Wikidata statements in opposite directions retain their own identities. No fixed assumption of exactly two assertions per entity pair is valid.

## 9. Geography: existing policy and fields

Follow the complete [geocoding policy](GEOCODING_HIGH_LEVEL_PROCESS.md), version `geo-object-selection-v0.5.0`; this S2T does not replace its place-type/representation table or acceptance rules.

1. Target confirmed place QIDs only. No geocoding of synthetic unresolved identities or non-place events by name.
2. Set selection date to the earliest supported related event/relation date inside `1941-12-07` through `1945-09-02`, else `1941-12-07`. Do not invent exact days from partial dates; a policy input that cannot be used without a new interpretation must be reported.
3. Search OHM and OSM exact QID candidates, preferring OHM then OSM after identity/date/meaning/geometry checks. WHG reconciliation is used only when their combined exact-QID candidate count is zero or greater than one. WHG unions are not selected geometries.
4. Apply the existing OHM/OSM/GeoNames name/alias/context fallback with added identity evidence. A high name score alone is insufficient. Use original linked-source geometry, not a guessed shape.
5. Use the existing preferred representation and stable source-object-ID tie rule. Do not union, buffer, simplify, construct or replace with a centroid automatically.
6. Validate a nonempty Shapely geometry; persist WKB in GeoParquet with CRS metadata. Record provenance, selection date and every failed/rejected/unselected attempt. Older OSM snapshot age is accepted; historical suitability still needs the existing checks.

Reuse approved saved snapshots/bulk retrieval first. The approved plan allows OHM snapshots, OSM BigQuery or Geofabrik files, GeoNames downloads and cached WHG reconciliation under existing limits. A specialist dataset or manual geometry needs a specific source/rule discussion before use; the generic fallback label does not approve a new dataset. The first-50 geocoding POC is evidence of that test only, not a full-Daniel accepted output.

| Target column(s) | Source and population rule |
|---|---|
| `place_id`, `name`, `place_type` | Confirmed entity QID and existing selection context/type evidence. One accepted geometry per QID at most. |
| `source_dataset`, `source_object_id`, `source_url` | Selected original source object, snapshot/version and link; no Wikidata geometry. |
| `match_method`, `selection_policy_version` | Actual evidence method and applied version. |
| `retrieved_at`, `review_status`, `decision_reason` | Real retrieval and acceptance decision; selected rows require `ACCEPTED_AUTO` or `ACCEPTED_REVIEWED` evidence. |
| `geometry` | Validated Shapely object, persisted as WKB; load as Shapely. No inline GeoJSON export. |
| `audit` | Full original input, candidates, dates, source attempts, WHG evidence, validation and decisions, including `selection_date`. Retain the complete audit or immutable reference. |

`UNRESOLVED` and `REJECTED_NOT_PLACE` remain audit results without selected Geography rows. Preserve the ERD's exact 13-column geometry compatibility view; `selection_date` projects from audit, not link validity. Geometry type comes from the object. Graph JSON's object pointer and Agent loading function are downstream interfaces, still requiring their exact contract before integration.

## 10. Evidence, required checks and explicit exceptions

Supporting manifests, catalogs, page/checkpoint files, query evidence, event-selection reports and geocoding audits are not new business tables. Each release must retain URI/path, checksum, schema/media version and record locator where a row uses an immutable reference. A local cache path alone is not a recoverable off-device artifact. Do not truncate unknown source fields or replace native statement evidence with just a QID pair.

Before an implementation can claim completion:

| Check | Required result |
|---|---|
| Input and decision accounting | Exactly 309,864 Mentions for the pinned input, unchanged original fields/order/IDs, complete stage/reason accounting and separate NER/matching scores. |
| Identity and page keys | Unique keys; every non-null FK exists; page-key pairs complete; no talk IDs, Index-as-page-ID, cache-only entity expansion or extra Daniel mentions. |
| Events | Native root/snapshot/path evidence; original QIDs; all approved event types; at least two distinct direct Daniel QIDs; incoming/outgoing acquisition coverage reported. |
| Assertions | Reconcile retrieved eligible statements = retained mapped base rows + exact exclusions + explicitly reported unmapped/ambiguous/blocked cases, deduplicated by source statement. Report all categories and ranks. No silent loss through join/mapping/rank filters. |
| Geometry | At most one accepted object per place; failed attempts retained; source and CRS known; valid nonempty Shapely/WKB round trip before delivery. |
| Contract coverage | All ERD fields, nine Daniel fields, 16 matching CSV fields, 26 legacy assertion fields, full nested reference/attempt payloads, geometry compatibility fields and versioned catalog columns retained or explicitly unavailable. |
| Reuse and release | Pinned hashes and request scope; existing verified artifacts reused; missing references/counts visible. No cloud/data/Agent completion claim based only on this document. |

The following cases must be brought back with exact IDs, values and counts before adding logic: conflicting per-QID canonical types; differing Daniel fallback names when both Wikidata labels are missing; unlabeled events without Daniel names; event/entity role conflicts; unknown/ambiguous predicate mappings; incompatible multivalued event dates/classifications; source-page input/lookup conflicts; partial-date interpretation required for geometry selection; or a concrete specialist geometry source. Preserve raw evidence while the required decision is pending, and report the affected population explicitly.

Downstream open interfaces remain the geometry pointer schema/storage binding/loading function/CRS behavior and Agent recognition of reverse views as shared evidence. They do not authorize changes to source population or matching. Final graph sources remain omitted for now; full provenance stays in this model and its supporting artifacts.

## 11. Contract references and precedence

- [Six-table ERD and exact column inventories](ENTITY_DATA_MODEL_ERD.md).
- [Separate model-to-graph JSON S2T](ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md).
- [v2.1 direction rules](RELATION_MAPPING_V2_1_DATA_LAYER_REVERSE_2026-10-15.md), [mapping table](../GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.0.csv), [direction catalog](../GG_Data/mapping/RELATION_DIRECTION_CATALOG_v2.1.0.csv), [exact exclusions](../GG_Data/mapping/ASSERTION_EXCLUSIONS.csv).
- Existing relation producer: `GG_Data/mapping/RELATION_MAPPING_ALL_ITEMS_v1.0.0.ipynb`; its historical output is an input/evidence contract, not proof of current scope, rank handling or v2.1 population completion.
- [Geometry source and selection policy](GEOCODING_HIGH_LEVEL_PROCESS.md) and [extraction method](../GG_Data/geocoding/GEO_OBJECT_EXTRACTION_METHOD.md).

Latest user decisions govern name priority, Wikidata-only assertions, included event links in Relations, all event types under Q140451665, two-entity event minimum, per-mention synthetic IDs, no new Daniel entities, and Shapely objects with downstream JSON pointers. No physical model tables or new production outputs are created by this specification.
