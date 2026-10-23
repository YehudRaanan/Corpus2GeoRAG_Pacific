# Source-to-target: six-table model to final Agent graph JSON

**23 October 2026 point-date approval:** when an Event has explicit start/end
bounds and several distinct point dates, export the approved selected bounds
and omit the optional scalar `attributes.point_date`. Keep every point date
and its precision/calendar in the model and show the omission in the export
report. Do not derive a replacement interval from these points. First cases:
Q115861680 and Q17193309. Multiple point dates without explicit bounds still
use only the already-approved derived-range rule.

**23 October 2026 reconciliation:** the v2.1 reverse-direction contract is
already approved. A reverse view preserves the original assertion and its
existing Level 1 category; it does not require a newly classified inverse
category. An unassigned category remains unassigned. The exact reverse ID and
label come from the pinned direction lookup. Source-mapping entries are copied
only where explicitly supplied; a lookup-only inverse can have an empty
`source_predicates` list, without a fabricated direction mapping.

The owner approved earliest supplied Event start and latest supplied Event end
for graph export, without a 1900 floor, on 23 October. All source dates remain
in the model. This supersedes the earlier instruction below to stop merely
because explicit Event bounds have several values. It does not authorize a
calendar conversion. Partial and coarse date comparison rules already exist
in population S2T section 8; their original precision/calendar must remain
recoverable. The Agent representation adapter remains implementation work;
no new JSON date-object interface or general calendar conversion was approved
by the subsequent consultation questions.

**23 October 2026 model support fields:** Entity language relevance columns and Mentions raw/adjusted matching scores and penalty evidence remain in the data model/supporting files. They do not add graph JSON fields or change the Agent contract. Geography references also remain in the model; the graph JSON contains neither the geometry pointer nor inline GeoJSON. The latest approved Geography ranking selects a usable retrieved geometry whenever one is available and retains uncertainty; historical ambiguity rejection statements below are superseded.

**Synthetic LOC approval - 21 October 2026:** all existing LOC identities enter Geography, including unresolved SYN IDs. QIDs use exact-ID lookup first; SYN IDs use the existing name/alias/date/type/context fallback and keep their original IDs. Supported geometry does not create a Wikidata match. Ambiguous candidates remain unresolved. `Geography.geometry_ref.place_id` can therefore be an existing QID or SYN ID; the reference stays in the model, not graph JSON. This extends target coverage under the existing source and acceptance policy.

**Geometry pointer correction - 21 October 2026:** `Geography.geometry_ref` belongs to the data model, not final graph JSON. It retains the approved `{file, place_id, sha256}` format and identifies the saved Shapely/WKB object. The existing loader can read this model reference; Agent access to the model still requires integration verification. Earlier graph-node pointer instructions are superseded. No pointer or inline GeoJSON is exported in graph JSON.

Implementation status, 21 October 2026: maximum linked-entity relevance >=2%, with missing scores contributing zero, supersedes the verified 775-Event average test. This inclusive assumption can admit unrelated items and may need improvement; no extra filter is approved. The maximum-rule replay selected 2,135 of 21,797 candidates; all decisions were independently verified. No Event model rows or final graph were written. Evidence and acquisition details are in the [population S2T](SOURCES_TO_ENTITY_DATA_MODEL_S2T.md).

Specification date: 19 October 2026. Status: agreed scope documented; identified compatibility and field-selection gaps remain explicit. This is a design specification, not an executed export or a production acceptance claim.

Geometry interface approved on 19 October 2026, with storage location corrected on 21 October: model `Geography.geometry_ref` is null or `{file, place_id, sha256}`, identifying the GeoParquet file, existing LOC identity (QID or SYN ID) and file checksum. The Agent loads the selected object as Shapely. A broken reference is an explicit error. Inline GeoJSON export is superseded. Preserve stored CRS; spatial-function compatibility still requires verification.

**Source:** [Entities, Mentions, Wiki Pages, Geography, Events, Relations](ENTITY_DATA_MODEL_ERD.md), with the existing versioned relation catalogs and release manifest.

**Target:** one final graph JSON file, read by the Agent through `GRAPH_PATH`:

```text
{
  "metadata": { ... },
  "relation_catalog": { ... },
  "nodes": [ ... ],
  "edges": [ ... ]
}
```

This S2T starts at the data model. It does not redo Daniel extraction, entity matching, Wikipedia acquisition, Wikidata event acquisition or geometry selection. No missing data or unresolved business rule is supplied by an invented entity, relation, value or classifier.

The separate [sources-to-model population S2T](SOURCES_TO_ENTITY_DATA_MODEL_S2T.md) defines the preceding phase, including the accepted snapshot-native Q1190554 occurrence hierarchy, name priority, and Wikidata-only assertion scope. WarSampo and EventKG facts are not added by that phase.

The [full pipeline review](DANIEL_TO_GRAPH_PIPELINE_REVIEW.md) collects all remaining decisions and checks across both S2T phases without changing the agreed export rules.

Type interface approved on 19 October 2026: the source Entities key is `(entity_id, type)`. Different types are entirely separate entities. A QID row exports as `QID::type` using the exact stored type, with its original QID in `wikidata_id`. Synthetic IDs remain unchanged. Relations keeps QID endpoints. The Agent must resolve each endpoint to its separate typed entities without copying assertions or selecting a canonical entity. No merged node/types array is used. The current Agent still requires integration; approval of the interface is not proof that its queries support it.

## 1. Confirmed scope

- Daniel's input supplies entity mentions only. Reuse existing entity assignments, original QIDs and separate unresolved synthetic IDs. Do not derive events from Daniel's mentions or from MISC.
- Events come separately from Wikidata, use their original QIDs and supplied values, and enter the graph only if directly connected to **at least two distinct retained matched Daniel entity QIDs, with maximum linked-entity relevance >=2%**. Missing scores contribute zero to selection, with missing evidence preserved; they do not bypass the threshold. All-missing scores yield zero and fail.
- For this event test, any mapped Wikidata relation can connect the event and the Daniel entity, in either direction. Repeated mentions count once. Multiple assertions and forward/reverse copies count once per connected entity. Indirect paths do not count. The test uses the whole input dataset, not one Wikipedia page at a time.
- Include retained mapped Wikidata assertions between Daniel's matched QIDs, included-event/Daniel links and direct links between included Events. Require both endpoints in included nodes. Event links are uncapped; non-event assertions follow the approved mutual-top-20 selection in population S2T section 8. Deliver both directions through the pinned mapping version (currently v2.1.1, preserving the v2.1 direction contract). Preserve different predicates and source assertions as distinct selection units.
- Omit node/edge `sources` from this export for now. Supporting provenance remains in the source model and audit artifacts. This omission does not remove edge endpoint `source` or the required reverse-view link `source_edge_id`.
- Do not create page nodes, mention nodes, paragraph objects or paragraph relations. Omit node `text`; do not assemble or process paragraph text. Do not export paragraph indexes, extraction spans or raw matching attempts.
- No internal event classification or inferred event level is authorized. For graph Event bounds, use the earliest supplied start and latest supplied end, without a 1900 floor (owner approval, 23 October). Preserve original values, precision and calendar in the model. Do not add calendar conversion or a new date-object JSON interface.
- No Entity Participants or other seventh business table is required.

## 2. Source populations, joins and filters

The following names describe sets/views used for this export; they are not new stored business objects.

| Set / join | Definition | Result and validation |
|---|---|---|
| Daniel entity IDs | Distinct non-null `Mentions.entity_id` from original non-DATE mentions, joined to Entities on `(entity_id, entity_type)`. Include existing QIDs and unresolved synthetic IDs. | One separate node per QID/type combination; existing per-mention synthetic IDs remain separate. No normalized DATE node is produced. |
| Matched Daniel QIDs | Daniel entity IDs that are existing accepted QID assignments, rather than synthetic IDs. | The only IDs that can satisfy the event threshold. A match is an existing decision, not a new accuracy certification. |
| Event candidates | `Events.event_id`, with its corresponding `Entities.entity_id`. Events is the authoritative Wikidata-only event population supplied to this S2T. | Do not classify new events by name, MISC or a new P31 hierarchy in this phase. |
| Event connections | Direct retained Wikidata source assertions, after approved exclusions and relation mapping, with event QID at one endpoint and a matched Daniel QID at the other. Use original provider evidence in Relations, not the omitted target `sources`. | Both directions and any mapped predicate qualify. Candidate completeness depends on the supplied Wikidata event/assertion population; do not claim complete Wikidata coverage without acquisition evidence. |
| Included events | Event candidates with at least two distinct connected retained matched Daniel QIDs and maximum linked-entity relevance >=2%. Missing contributes zero and provides no exception; all-unscored candidates fail relevance. | Keep their original event QIDs. Record distinct entity IDs, total/scored counts, missing QIDs and effective maximum in the supporting event-selection report. |
| Included nodes | Union of Daniel entity QIDs/SYN IDs and included event QIDs, with every associated Entities type. | Use separate `QID::type` nodes and original `wikidata_id`; preserve synthetic IDs. No canonical node, type winner or unrelated cached candidate QID. |
| Included base relations | Retained Wikidata Relations rows between matched Daniel QIDs, included-event/Daniel links, and direct included-event/included-event links, with both item endpoints in included nodes. | Event links are uncapped. For two non-event endpoints, require the assertion in both endpoint top-20 selections, ranked by the connected QID's distinct Daniel pages times original mention count. Keep each retained `observation_id`; reverse views use no extra slot. No transitive relation creation or synthetic endpoint claims. |
| Node geography | Left join included nodes to `Geography.place_id = Entities.entity_id`. | At most one accepted stored geometry object per existing LOC identity, including an unchanged SYN ID. Keep `geometry_ref={file,place_id,sha256}` in Geography only; omit it from graph JSON. Count missing geometries visibly. No retrieval or geometry selection in this S2T. |
| Wiki Pages / Mentions | Mentions links to Wiki Pages by `(wiki_site, wiki_page_id)` for source-model traceability. | No independent target collection or page/paragraph traversal. Missing page IDs remain visible in source quality results. |

Event membership can be expressed without any ranking:

```text
connected_entities(event) = distinct matched Daniel QIDs
    with a direct retained mapped Wikidata assertion to/from that event

include(event) = recognized(event) AND count(connected_entities(event)) >= 2
    AND max(score_or_zero(entity) for entity in connected_entities(event)) >= 0.02
# One score per distinct linked Daniel QID: its highest available EN/JA ratio.
# Missing scores contribute zero; keep their missing status in evidence.
# The upstream 5% MISC filter remains.
```

The rule is evaluated on base assertions before non-event capping. Reversing an assertion does not create a second qualifying entity. An event with one entity mentioned 100 times fails; two distinct matched entities satisfy the count gate but still require the maximum linked-entity score >=2% after recognition and source/mapping checks. An explicitly unscored QID counts toward the two-entity gate and contributes zero to the maximum. Direct links between included Events do not qualify another Event. Do not run a recursive traversal.

The [approved non-event selection](SOURCES_TO_ENTITY_DATA_MODEL_S2T.md#non-event-relation-selection--approved-20-october-2026) must be evidenced in the source run before export; do not independently rerank or cap its reverse views here. The verified stable-tie model run applied the selector with complete Event membership: 11,409 base assertions, including all 8,861 Event-linked assertions; maximum non-event incident count 20. See the population S2T and `poc_10k_event_model_stable_ties_20261021` evidence. Previous uncapped outputs remain historical; equal-score ties within a temporal group use ascending native source assertion ID upstream (approved 21 October), without an exporter tie-break. This establishes the capped source model; final graph export and Agent integration remain pending.

Successfully normalized DATE mentions stay in the source temporal data. Existing synthetic DATE errors also remain there; this S2T does not turn extraction date strings into events or inferred event dates.

21 October population-selection update: for each non-event endpoint, dated
assertions overlapping 7 December 1941 through 2 September 1945 rank first;
undated assertions fill remaining slots, up to 20 total. Importance ranks within
each group, and mutual-endpoint intersection still applies without refill.
Event links bypass both period filtering and the cap. The exporter consumes
this selected population; it must not rerank relations or cap reverse views.
Outside-period evidence remains in supporting source records and prior outputs.
Partial dates qualify on possible overlap; their original precision remains
unchanged. Selection does not establish an exact day or certain overlap.
The population step also supports Wikidata decade/century/millennium ranges
for this comparison; export must retain their original precision.

## 3. Top-level target fields

| Target JSON path | Source | Transformation / condition |
|---|---|---|
| `metadata.schema_version` | Approved graph release manifest | Copy the graph schema version. Do not substitute the S2T document date/version. Highlight a missing release value before publication. |
| `metadata.relation_map_version` | Applied mapping version | `relation-map-v2.1.1` for the current native extension; validate the actual applied version and checksums against every exported assertion/catalog. Later native additions require a new pinned version. Existing v1 exports must not be relabeled as v2.1. |
| `metadata.release_status` | Approved release manifest | Copy the actual release state. Structural validation alone cannot assign production status. |
| `metadata.scope` | Approved release scope | State the actual Daniel entity population and included Wikidata event scope. No automatic Pacific-only claim. Retain the >=2 rule and input/reference versions in the supporting manifest; do not invent a new scope schema here. |
| `relation_catalog` | Current versioned mapping and direction catalog | Use the Agent-compatible catalog structure and field rules below. |
| `nodes` | Included nodes, Events extension and Geography join | Separate `QID::type` nodes, original QID in `wikidata_id`, existing synthetic IDs unchanged. |
| `edges` | Included base relations plus exact reverse delivery | One base view per assertion, plus its reverse for non-self assertions. |

Release metadata is a supporting input artifact already defined in the model. No new business table is needed. Exact release values are supplied at release time, not guessed in this specification.

## 4. Node S2T

Paths refer to `nodes[]`.

| Target field | Source column(s) | Rule |
|---|---|---|
| `id` | `Entities.entity_id`, `Entities.type` | QID rows use `QID::type` with the exact stored type token, e.g. `Q188712::LOC` and `Q188712::ORG`. Included event rows follow the same rule; their native QID is unchanged in the source model and `wikidata_id`. Existing synthetic IDs are copied unchanged. |
| `wikidata_id` | `Entities.entity_id` | Original QID for QID-backed nodes; null for synthetic identities. QID relation endpoints resolve through this field to all separate typed entities. |
| `name` | `Entities.name` | Copy the existing display name. No new English/Japanese precedence rule or name synthesis. Missing/empty values are reported because the Agent requires a name. |
| `type` — Daniel entity | This separate row's `Entities.type`; saved `Mentions.type_metadata` as evidence | Scalar type per separate node. Approved mechanical spellings remain PER -> person, ORG -> org, LOC -> location. The ID suffix uses the stored type, before these display spellings. No inference, winner or merged types list; MISC is not reopened. |
| Type representation — included Wikidata event | Membership in authoritative Events table | Preserve `event` alongside any other existing types for the same QID. This labels an existing event input; it is not a classifier over Daniel entities. |
| `aliases` | `Entities.aliases` | Copy existing supplied strings. No generated nicknames, romanizations or combined names. Missing aliases may remain an empty array. |
| Omitted: `geometry_ref` | Geography model reference only | `{file, place_id, sha256}`; file is the GeoParquet artifact, place_id the original place QID or SYN ID, sha256 the whole artifact checksum. This is a model-only field and is omitted from nodes. No accepted geometry -> no accepted Geography row; model reference lookup returns null. Broken reference, duplicate/missing place, invalid/empty geometry or missing CRS -> explicit error. No inline geometry. |
| `attributes.start_date` | `Events.start_date` | Earliest supplied start, without a 1900 floor. Preserve native precision/calendar in supporting model evidence; do not invent an exact day. Null/absent source -> omit. |
| `attributes.end_date` | `Events.end_date` | Latest supplied end, without a 1900 floor. Preserve native precision/calendar in supporting model evidence. Null/absent source -> omit. |
| `attributes.point_date` | `Events.point_date` | Copy a supplied target-compatible single point value. With several distinct points and explicit bounds, omit this optional graph field and keep the selected bounds; report the omission and retain all native points in the model (23 October approval). Without explicit bounds, reuse only the existing approved derived-range rule. Do not infer a point from a bound. |
| `attributes.kind` | `Events.kind` | Copy only an existing source-supplied, target-compatible value. Do not infer battle/campaign/war from names or a new mapping. A Wikidata class QID is not silently translated into a kind label. |

Event values can be kept as full raw statements in the source model even when they do not fit a scalar target field. That preservation does not authorize silently omitting a conflict from the export report or treating it as resolved. Event level, importance, country, scale, aliases with added meanings, hull numbers and other optional enrichments have no new derivation rule in this S2T; do not generate them.

Omitted node fields: `geometry_ref`, `sources`, `text`, `embedding`, `alias_details`, raw labels/descriptions/claims, mention lists, page references, spans, matching scores/attempts and geometry audit payloads. They remain source/supporting information where supplied. Their absence limits the Agent's citation, text search and some enrichment features; no paragraph work is added to compensate.

### Geometry object reference and loading

- The geocoding contract produces a validated Shapely geometry object. Geography persists it as WKB in GeoParquet and restores it as Shapely when loaded.
- Geography contains the pointer to the stored object. Graph JSON omits it. A consumer loads this model reference through a function and uses the returned Shapely object; the Agent-to-model access path remains to be integrated. The graph exporter does not convert the object to GeoJSON.
- The approved model pointer is `Geography.geometry_ref={file,place_id,sha256}` or null. `load_geometry(pointer, artifact_root)` in `GG_Data/pipeline/graph_contract.py` checks the artifact hash and unique place record, then returns its Shapely object. Paths resolve within the release artifact directory. Broken references fail explicitly; no fallback geometry is created.
- Preserve source CRS in Geography metadata. The Agent's object-loading/spatial-function CRS and antimeridian requirements need interface confirmation; the earlier inline-GeoJSON representation does not establish this new interface. Do not infer or transform coordinates in the exporter.
- The loader must retrieve the accepted geometry for the referenced place. Do not replace a polygon with its centroid or copy a related place geometry onto an event.
- Use only geometries accepted under the Geography policy and its dated approvals. The 22 October 2026 coordinate approval and owner correction permit an unchanged Wikidata coordinate as last-resort Shapely Point after approved source attempts, including saved exact-name/alias-linked candidate coordinates for synthetic inputs. Keep candidate uncertainty visible and input IDs unchanged; no extra confirmed-input identity gate blocks this fallback. See population S2T section 9.3. This S2T does not retrieve or select it. Wikidata shapes, inferred event geometry and new non-place geometry remain unapproved. Keep the pointer in Geography, not graph JSON.

The previously inspected Agent README/loader describes inline GeoJSON. Agent integration must be updated and verified before export acceptance. The new interface helper is implemented and tested with in-memory fixtures; it is not yet wired into the Agent query engine. Generic extra-field acceptance does not establish pointer resolution or Shapely use.

## 5. Base edge S2T

Paths refer to the base direction in `edges[]`. Source Relations has normalized endpoints and the original source-oriented assertion preserved separately.

Relations and graph edges remain at QID level. Do not join a source assertion to every endpoint type combination or duplicate its evidence because a QID has several types. The Agent type representation must preserve these QID-level endpoint links.

| Target field | Source column(s) | Rule |
|---|---|---|
| `id` | `Relations.observation_id` | Copy unchanged; require uniqueness for base assertions. |
| `source` | `Relations.subject_entity_id` | Copy the already normalized QID endpoint. Resolve through nodes' `wikidata_id`; do not rewrite it to a chosen typed node. This is an endpoint ID, not provenance. |
| `target` | `Relations.object_entity_id` | Copy the normalized item QID endpoint; require at least one separate typed node with this `wikidata_id`. No assertion fan-out. Literal/somevalue/novalue records remain source data. |
| `type` | `Relations.level2_relation` | Exact case-preserving mapped ID. No uppercasing or semantic replacement. |
| `relation_family` | `Relations.level1_relation` and mapping catalog | Copy the applied version's agreed family. Native fallback mappings keep Level 1 unassigned (`UNRESOLVED`), with no inferred family. Highlight a row/catalog conflict rather than selecting an alternative family. |
| `count` | `Relations.count` | One per current source assertion. Never use repeated Daniel mentions or the reverse copy to increase this count. |
| `start_date` | `Relations.time_from` | Copy the value selected by population S2T section 8, or null. No additional date selection in the exporter; preserve partial precision. |
| `end_date` | `Relations.time_to` | Same rule as start_date. |
| `point_date` | `Relations.time_point` | Same rule as start_date. Preserve the point field; Agent date-filter behavior is its existing responsibility. |

Omit edge `sources`, `embedding` and optional source/audit attributes. Retain source records, ranks, qualifiers, reviews and evidence in Relations and its raw artifacts. If an optional sourced role such as attacker/defender needs to be exported later, add its explicit S2T rule before doing so; do not infer it now.

Before normalization, apply the existing 14 exact exclusions using original source records/endpoints. This is the previously approved gate, not a blanket ban on self-relations. Do not apply v2.1 swaps again to endpoints already transformed under v1; the integration must restore the original orientation before applying the selected mapping once. The S2T consumes the resulting normalized Relations view.

## 6. Reverse edge S2T

Join the base `type` plus the actual mapping version to its matching direction lookup (currently `RELATION_DIRECTION_LOOKUP_v2.1.1.csv`). The existing direction mapping supplies the meaning; neither exporter nor Agent invents an inverse.

| Reverse target field | Source / rule |
|---|---|
| `id` | Unique directional view ID linked to the base `observation_id`. The exact string format is an implementation detail; it must be stable, collision-free and must not mint an entity ID. |
| `source` | Base `target`. |
| `target` | Base `source`. |
| `type` | Lookup `output_reverse_relation_id`, copied exactly. |
| `relation_label` | Lookup `output_reverse_relation_label`. |
| `direction_pair_id` | Lookup `direction_pair_id`. |
| `base_level2_relation_id` | Base `type`. |
| `derived` | true. |
| `derived_direction` | REVERSE. |
| `source_edge_id` | Base `id` / `observation_id`. |
| `count`, `start_date`, `end_date`, `point_date` | Same assertion's values, unchanged. The count is shared evidence, not independent support. |
| `relation_family` | Preserve the same assertion's existing applied Level 1 category, including its unassigned state. Reversing a view does not classify a new category. Highlight a conflict with an explicitly supplied catalog definition. |

For a non-self assertion, deliver both directions. For a symmetric relation, swap endpoints and retain the lookup's same predicate. For a self-loop, keep one view. Different base assertions between the same two nodes stay separate, including when their directional outputs happen to have equal endpoints/predicates.

The currently inspected Agent groups identical `(source, target, type, dates)` and does not explicitly identify reverse views through `source_edge_id`. Its generic extra-field acceptance does not prove shared-evidence counting or reverse role traversal. Keep this as an explicit compatibility check before declaring the final graph accepted. Do not alter Agent code or remove an agreed direction without reporting the issue first.

## 7. Relation catalog S2T

The Agent reads a relation definition's label, family, source predicate, direction and mapping status. Reuse its existing catalog adapter shape rather than defining a new business ontology.

| Target path in `relation_catalog[relation_id]` | Source / rule |
|---|---|
| `id` | Exact exported base or reverse predicate ID; also the catalog dictionary key. |
| `labels` | Existing label strings from applied `level2_relation_label`, or the lookup's exact reverse label. Highlight conflicting meanings rather than relying on the loader's first-label selection. |
| `level1_families` | Reuse the existing draft builder's sorted distinct-value list. Include the existing applied values from base/reverse views; native fallback entries remain unassigned (`UNRESOLVED`). An assigned value plus `UNRESOLVED` preserves classification and missing-classification evidence, without assigning that value to an unassigned edge. Competing assigned categories or conflicting labels still require discussion. |
| `source_predicates[].source` | Existing mapping `source`. Retain supplied source mappings. |
| `source_predicates[].predicate` | Existing mapping `source_predicate`. |
| `source_predicates[].direction` | Existing `direction_to_level2` for explicitly supplied source mappings. For a lookup-only reverse predicate, retain its exact ID/label and an empty source-mapping list; do not copy a base direction or invent a conversion. |
| `review_statuses` | Existing catalog review/status values, if supplied; otherwise omit this optional field. No new review decision is made by export. |
| Direction-pair audit fields | Retain `direction_pair_id`, `reverse_resolution_type` and endpoint action in supporting direction artifacts. The current Agent catalog adapter does not consume them; reverse edges carry their defined view fields. |

The population S2T section 8 now permits adding exact native Wikidata properties to a new mapping version when a source key is missing. This exporter consumes that pinned result; it does not discover or invent relations. Every exported base or reverse predicate must be present in the exported catalog. Reuse only the mapping keys applied to this Wikidata-only population; do not import an unused provider's classification. Highlight competing assigned categories or label meanings rather than resolving them through a new aggregation or guess. Catalog inclusion does not create entity nodes or source assertions.

23 October implementation reconciliation: the existing [draft builder](../GG_Data/agent_export/BUILD_WWII_AGENT_GRAPH_DRAFT.ipynb) already collects all nonempty supplied Level 1 values into a set and sorts it into `level1_families`. Applied P131/P150 views yield `SPATIAL` plus `UNRESOLVED`; no predicate has two competing assigned categories in the checked model. Preserve both supplied states in the catalog and each assertion's original family on its views. This is existing serialization, not a new classification rule. An unused EventKG P10661 category also does not replace the applied Wikidata `UNRESOLVED` value; list that unused definition in the supporting report.

## 8. Visible exceptions and release checks

An export report is a supporting release artifact, not a seventh business table. It must show affected IDs, source values, target fields, counts, reason and the decision needed. Do not present conflicts as a hidden unresolved bucket or silently drop affected records.

| Check | Required response |
|---|---|
| A QID has multiple saved types | Preserve every distinct QID/type pair. Verify Agent loading and type filters retain all types, with QID-level edges. This is an integration check, not a canonical-type decision. MISC is not an open classification question. |
| Wikidata event classification or dates cannot fit target scalar fields | Show the event QID, exact claims/values and target fields. Apply the approved earliest-start/latest-end rule; preserve original precision/calendar in the model. Do not invent precision, translate a class label, or add calendar conversion/new JSON date objects. |
| Missing names, endpoints, mapping definitions or direction keys | Show exact records and counts. Do not invent required values or rely on Agent endpoint dropping. |
| Missing geometry vs invalid geometry/unknown CRS | Report separately. No accepted geometry -> no accepted Geography row; lookup returns null. Broken model reference or invalid object/unknown CRS -> explicit error. No fabricated pointer or geometry. |
| Geometry pointer and Agent loader | Verify the approved file/place/checksum pointer resolves to the selected valid Shapely object. Verify Agent integration and spatial CRS compatibility. Neither the model pointer nor inline GeoJSON enters graph JSON. |
| Event inclusion evidence | Report candidate events, included/excluded event counts and each event's distinct qualifying Daniel QIDs. Check count >=2 independently of mentions, duplicate assertions and reverse views. |
| Reverse compatibility | Verify both-direction queries, exact inverse IDs, and one evidence identity/support count. Agent format acceptance alone is insufficient. |
| Intentional omissions | Confirm no node/edge `sources`, node `text`, paragraph objects, mention/page nodes or extraction audit payloads entered the graph. Supporting provenance remains recoverable separately. |
| Final graph integrity | Unique typed node/view IDs; each QID edge endpoint resolves via `wikidata_id`; correct native event QIDs, full base-assertion accounting, exact mapping version and no unintended population expansion. |

Do not publish a final accepted graph while an unresolved required-field or semantic conflict is hidden. This specification records already identified gaps; it does not claim that those conditions have occurred in a newly executed export. No graph build or data-quality run was performed for this document.

## 9. Contract evidence and current limits

- [Agent README input contract](https://github.com/EtzionR/Corpus2GeoRAG_Pacific/blob/main/Agent/README.md#input-schema-for-the-knowledge-graph-builder), verified on 19 October 2026; Git blob `d6929c7e276c564cb7ef1cf219cb1b9414ce0f26`. The target is the graph input, not the Agent's answer JSON or UI result schema.
- [Agent loader and text search](https://github.com/EtzionR/Corpus2GeoRAG_Pacific/blob/main/Agent/geo_agent/graph_store.py), inspected Git blob `3d67affe310e0336c579adcf8dcc0362702100ba`. Remote Agent implementation is newer than the local checkout.
- [Relation-map-v2.1.0 delivery rules](RELATION_MAPPING_V2_1_DATA_LAYER_REVERSE_2026-10-15.md), [current mapping table](../GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.1.csv), [direction lookup](../GG_Data/mapping/RELATION_DIRECTION_LOOKUP_v2.1.1.csv) and [direction catalog](../GG_Data/mapping/RELATION_DIRECTION_CATALOG_v2.1.1.csv).
- [Geography policy](GEOCODING_HIGH_LEVEL_PROCESS.md). Shapely is the geometry output; Geography holds the approved file/place/checksum pointer; graph JSON omits it. This supersedes the inspected Agent inline-GeoJSON format. The loader helper has fixture checks; Agent integration and spatial CRS compatibility remain pending.
- [Existing matching type decisions](../GG_Data/entity_resolution/bilingual_page_pilot.py): `categories` / `choose` and saved `type_metadata` remain unchanged. The later population decision preserves distinct QID/type pairs and QID-level relations; no canonical type selector or new event classifier is introduced.

The source model is an agreed logical design with explicit implementation exceptions. Following D: output approval on 20 October 2026, `GG_Data/pipeline` completed the first population step for 10,000 original mentions and 691 resolved Wiki Pages, with output/source/key verification. Its original manifest remains `STEP_1_ONLY`. The separate approved Entities step subsequently passed with 6,077 rows in `outputs/poc_10k_entities_approved`, status `ENTITIES_STEP_ONLY`; see the pipeline README. The P2341 source-key gap is covered by the approved native-property rule and mapping v2.1.1, and the Daniel/Daniel replay passed with 10,467 base statements and 34 pre-1900-end exclusions under POC v2.1.2; see the pipeline README. Included-event links remain pending. The graph interface helpers have in-memory checks; Events, Relations, Geography, final graph and Agent integration remain pending. Remaining work includes source/target compatibility, release metadata, spatial CRS compatibility and reverse-view evidence checks. New cases outside approved logic must be brought back before adding logic.

Population correction, 20 October: the user requires the 34 pre-1900-end relations to remain with original dates. Relation-date policy v1.1.0 supersedes the earlier exclusion; graph export must use the corrected population manifest in `outputs/poc_10k_relations_original_historical_dates_20261020`, once verified, and copy its selected original historical dates without a further 1900 floor or date-only filter. Earlier 10,467-row counts describe historical runs. No graph export has been run.
