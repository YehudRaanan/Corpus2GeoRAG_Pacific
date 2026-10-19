# Source-to-target: six-table model to final Agent graph JSON

Specification date: 19 October 2026. Status: agreed scope documented; identified compatibility and field-selection gaps remain explicit. This is a design specification, not an executed export or a production acceptance claim.

Geometry decision corrected on 19 October 2026: graph JSON contains a pointer to the stored geometry object. The Agent uses a function to load and use it as a Shapely object. Inline GeoJSON export is superseded. The exact pointer field/schema and loader interface are not yet agreed; no replacement schema or function is invented here.

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

The separate [sources-to-model population S2T](SOURCES_TO_ENTITY_DATA_MODEL_S2T.md) defines the preceding phase, including the approved Wikidata event root Q140451665, name priority, and Wikidata-only assertion scope. WarSampo and EventKG facts are not added by that phase.

The [full pipeline review](DANIEL_TO_GRAPH_PIPELINE_REVIEW.md) collects all remaining decisions and checks across both S2T phases without changing the agreed export rules.

Type decision, 19 October 2026: the source Entities key is `(entity_id, type)`. Different types for the same QID coexist; no canonical type is selected, and MISC is not an open classification question. Relations remains at QID level. The inspected Agent indexes nodes by `id` and has a scalar `type`; repeating a QID would overwrite a node. Its contract must preserve all types and QID-level links before export. No type-suffixed IDs, chosen winner, repeated-QID overwrite, or assertion expansion is approved here.

## 1. Confirmed scope

- Daniel's input supplies entity mentions only. Reuse existing entity assignments, original QIDs and separate unresolved synthetic IDs. Do not derive events from Daniel's mentions or from MISC.
- Events come separately from Wikidata, use their original QIDs and supplied values, and enter the graph only if directly connected to **at least two distinct matched Daniel entity QIDs**.
- For this event test, any mapped Wikidata relation can connect the event and the Daniel entity, in either direction. Repeated mentions count once. Multiple assertions and forward/reverse copies count once per connected entity. Indirect paths do not count. The test uses the whole input dataset, not one Wikipedia page at a time.
- Include retained mapped Wikidata assertions between Daniel's matched QIDs and included-event/Daniel links. Require both endpoints in included nodes; do not expand to arbitrary event/event assertions. Deliver both directions through relation-map-v2.1.0. Preserve different predicates and different source assertions rather than reducing an entity pair to a single relation.
- Omit node/edge `sources` from this export for now. Supporting provenance remains in the source model and audit artifacts. This omission does not remove edge endpoint `source` or the required reverse-view link `source_edge_id`.
- Do not create page nodes, mention nodes, paragraph objects or paragraph relations. Omit node `text`; do not assemble or process paragraph text. Do not export paragraph indexes, extraction spans or raw matching attempts.
- No internal event classification, inferred event level, date ranking or conflict resolution is authorized. Use Wikidata values as supplied. Highlight incompatible/multiple values before changing or choosing them.
- No Entity Participants or other seventh business table is required.

## 2. Source populations, joins and filters

The following names describe sets/views used for this export; they are not new stored business objects.

| Set / join | Definition | Result and validation |
|---|---|---|
| Daniel entity IDs | Distinct non-null `Mentions.entity_id` from original non-DATE mentions, joined to `Entities.entity_id`. Include existing QIDs and unresolved synthetic IDs. | One graph node per assigned ID, even if it has many mentions. No normalized DATE node is produced. |
| Matched Daniel QIDs | Daniel entity IDs that are existing accepted QID assignments, rather than synthetic IDs. | The only IDs that can satisfy the event threshold. A match is an existing decision, not a new accuracy certification. |
| Event candidates | `Events.event_id`, with its corresponding `Entities.entity_id`. Events is the authoritative Wikidata-only event population supplied to this S2T. | Do not classify new events by name, MISC or a new P31 hierarchy in this phase. |
| Event connections | Direct retained Wikidata source assertions, after approved exclusions and relation mapping, with event QID at one endpoint and a matched Daniel QID at the other. Use original provider evidence in Relations, not the omitted target `sources`. | Both directions and any mapped predicate qualify. Candidate completeness depends on the supplied Wikidata event/assertion population; do not claim complete Wikidata coverage without acquisition evidence. |
| Included events | Event candidates with at least two distinct connected matched Daniel QIDs. | Keep their original event QIDs. Record the distinct entity list and count in the supporting event-selection report. |
| Included nodes | Union of Daniel entity QIDs/SYN IDs and included event QIDs, with every associated Entities type. | Preserve all distinct `(entity_id, type)` combinations in the agreed Agent representation. Exact multi-type encoding requires contract alignment; do not overwrite duplicate QIDs, choose a type or invent new IDs. Do not add unrelated cached candidate QIDs. |
| Included base relations | Retained Wikidata Relations rows between matched Daniel QIDs, or between an included event and a matched Daniel QID, with both item endpoints in included nodes. | Keep each `observation_id`. Arbitrary event/event assertions do not enter merely because both nodes exist. No transitive relation creation or synthetic endpoint claims. |
| Node geography | Left join included nodes to `Geography.place_id = Entities.entity_id`. | At most one accepted stored geometry object. Export a pointer to that object, not its coordinates. Count missing geometries visibly; their JSON representation awaits the pointer contract. No geometry retrieval or selection is performed by the S2T. |
| Wiki Pages / Mentions | Mentions links to Wiki Pages by `(wiki_site, wiki_page_id)` for source-model traceability. | No independent target collection or page/paragraph traversal. Missing page IDs remain visible in source quality results. |

Event membership can be expressed without any ranking:

```text
connected_entities(event) = distinct matched Daniel QIDs
    with a direct retained mapped Wikidata assertion to/from that event

include(event) = count(connected_entities(event)) >= 2
```

The rule is evaluated on base assertions. Reversing an assertion does not create a second qualifying entity. An event with one entity mentioned 100 times fails; an event connected directly to two distinct matched entities passes. Do not run a recursive traversal.

Successfully normalized DATE mentions stay in the source temporal data. Existing synthetic DATE errors also remain there; this S2T does not turn extraction date strings into events or inferred event dates.

## 3. Top-level target fields

| Target JSON path | Source | Transformation / condition |
|---|---|---|
| `metadata.schema_version` | Approved graph release manifest | Copy the graph schema version. Do not substitute the S2T document date/version. Highlight a missing release value before publication. |
| `metadata.relation_map_version` | Applied mapping version | `relation-map-v2.1.0`; validate against every exported assertion and catalog artifact. Existing v1 exports must not be relabeled as v2.1. |
| `metadata.release_status` | Approved release manifest | Copy the actual release state. Structural validation alone cannot assign production status. |
| `metadata.scope` | Approved release scope | State the actual Daniel entity population and included Wikidata event scope. No automatic Pacific-only claim. Retain the >=2 rule and input/reference versions in the supporting manifest; do not invent a new scope schema here. |
| `relation_catalog` | Current versioned mapping and direction catalog | Use the Agent-compatible catalog structure and field rules below. |
| `nodes` | Included nodes, Events extension and Geography join | Preserve original assigned IDs and all coexisting types. Final encoding requires the Agent multi-type contract. |
| `edges` | Included base relations plus exact reverse delivery | One base view per assertion, plus its reverse for non-self assertions. |

Release metadata is a supporting input artifact already defined in the model. No new business table is needed. Exact release values are supplied at release time, not guessed in this specification.

## 4. Node S2T

Paths refer to `nodes[]`.

| Target field | Source column(s) | Rule |
|---|---|---|
| `id` | `Entities.entity_id` | Copy unchanged. An included event uses `Events.event_id`, equal to the Entities QID. Preserve existing synthetic IDs; never mint replacements here. |
| `name` | `Entities.name` | Copy the existing display name. No new English/Japanese precedence rule or name synthesis. Missing/empty values are reported because the Agent requires a name. |
| Type representation — Daniel entity | Every `Entities.type` for the QID/SYN ID; saved `Mentions.type_metadata` as evidence | Preserve every distinct saved type. Approved mechanical spellings remain PER -> person, ORG -> org, LOC -> location. Do not rerun inference, select a winner or reopen MISC classification. The exact multi-type Agent field/encoding requires contract alignment. |
| Type representation — included Wikidata event | Membership in authoritative Events table | Preserve `event` alongside any other existing types for the same QID. This labels an existing event input; it is not a classifier over Daniel entities. |
| `aliases` | `Entities.aliases` | Copy existing supplied strings. No generated nicknames, romanizations or combined names. Missing aliases may remain an empty array. |
| Geometry pointer — exact JSON field/schema pending agreement | Accepted Geography row and its stored object | Export only a reference to the existing object. The Agent loads it through a function that returns a Shapely geometry. Do not export inline GeoJSON, WKB bytes or an in-memory address. Missing-object representation and exact reference fields need agreement before implementation. |
| `attributes.start_date` | `Events.start_date` | Copy the supplied single target-compatible Wikidata value; preserve precision. Null/absent source -> omit. Multiple or incompatible values -> highlight before export, without selecting one. |
| `attributes.end_date` | `Events.end_date` | Same rule as start_date. |
| `attributes.point_date` | `Events.point_date` | Same rule as start_date; do not manufacture an interval or infer a point from another value. |
| `attributes.kind` | `Events.kind` | Copy only an existing source-supplied, target-compatible value. Do not infer battle/campaign/war from names or a new mapping. A Wikidata class QID is not silently translated into a kind label. |

Event values can be kept as full raw statements in the source model even when they do not fit a scalar target field. That preservation does not authorize silently omitting a conflict from the export report or treating it as resolved. Event level, importance, country, scale, aliases with added meanings, hull numbers and other optional enrichments have no new derivation rule in this S2T; do not generate them.

Omitted node fields: `sources`, `text`, `embedding`, `alias_details`, raw labels/descriptions/claims, mention lists, page references, spans, matching scores/attempts and geometry audit payloads. They remain source/supporting information where supplied. Their absence limits the Agent's citation, text search and some enrichment features; no paragraph work is added to compensate.

### Geometry object reference and loading

- The geocoding contract produces a validated Shapely geometry object. Geography persists it as WKB in GeoParquet and restores it as Shapely when loaded.
- Graph JSON contains only a pointer to the stored object. The Agent resolves that pointer through a function and uses the returned Shapely object. The graph exporter does not convert the object to GeoJSON.
- The pointer must identify the selected stored object reliably. Its JSON field name, value structure, storage location/version binding, and loader inputs/outputs are open interface details. Do not invent a URI convention, function name, or missing-object behavior without agreement.
- Preserve source CRS in Geography metadata. The Agent's object-loading/spatial-function CRS and antimeridian requirements need interface confirmation; the earlier inline-GeoJSON representation does not establish this new interface. Do not infer or transform coordinates in the exporter.
- The loader must retrieve the accepted geometry for the referenced place. Do not replace a polygon with its centroid or copy a related place geometry onto an event.
- Use only geometries accepted under the existing geography policy. No Wikidata coordinate/shape promotion, inferred event geometry or new non-place geometry policy.

The previously inspected Agent README/loader describes inline GeoJSON. This differs from the newly confirmed pointer contract. Agent integration must be updated and verified before export acceptance; generic extra-field acceptance does not establish pointer resolution or Shapely use. This documentation change does not implement that integration.

## 5. Base edge S2T

Paths refer to the base direction in `edges[]`. Source Relations has normalized endpoints and the original source-oriented assertion preserved separately.

Relations and graph edges remain at QID level. Do not join a source assertion to every endpoint type combination or duplicate its evidence because a QID has several types. The Agent type representation must preserve these QID-level endpoint links.

| Target field | Source column(s) | Rule |
|---|---|---|
| `id` | `Relations.observation_id` | Copy unchanged; require uniqueness for base assertions. |
| `source` | `Relations.subject_entity_id` | Copy the already normalized endpoint. This is an endpoint ID, not provenance. |
| `target` | `Relations.object_entity_id` | Copy the normalized item endpoint. Require both endpoints in nodes. Literal/somevalue/novalue records remain source data, not fake graph nodes. |
| `type` | `Relations.level2_relation` | Exact case-preserving mapped ID. No uppercasing or semantic replacement. |
| `relation_family` | `Relations.level1_relation` and mapping catalog | Copy the applied version's agreed family. Highlight a row/catalog conflict rather than selecting an alternative family. |
| `count` | `Relations.count` | One per current source assertion. Never use repeated Daniel mentions or the reverse copy to increase this count. |
| `start_date` | `Relations.time_from` | Copy the existing target-compatible mapped value or null; no new temporal inference. |
| `end_date` | `Relations.time_to` | Same rule as start_date. |
| `point_date` | `Relations.time_point` | Same rule as start_date. Preserve the point field; Agent date-filter behavior is its existing responsibility. |

Omit edge `sources`, `embedding` and optional source/audit attributes. Retain source records, ranks, qualifiers, reviews and evidence in Relations and its raw artifacts. If an optional sourced role such as attacker/defender needs to be exported later, add its explicit S2T rule before doing so; do not infer it now.

Before normalization, apply the existing 14 exact exclusions using original source records/endpoints. This is the previously approved gate, not a blanket ban on self-relations. Do not apply v2.1 swaps again to endpoints already transformed under v1; the integration must restore the original orientation before applying the selected mapping once. The S2T consumes the resulting normalized Relations view.

## 6. Reverse edge S2T

Join the base `type` plus mapping version to `RELATION_DIRECTION_LOOKUP_v2.1.0.csv`. The existing direction mapping supplies the meaning; neither exporter nor Agent invents an inverse.

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
| `relation_family` | The versioned family's explicit reverse definition where provided. No family is inferred from a reverse name; a missing/conflicting definition is highlighted. |

For a non-self assertion, deliver both directions. For a symmetric relation, swap endpoints and retain the lookup's same predicate. For a self-loop, keep one view. Different base assertions between the same two nodes stay separate, including when their directional outputs happen to have equal endpoints/predicates.

The currently inspected Agent groups identical `(source, target, type, dates)` and does not explicitly identify reverse views through `source_edge_id`. Its generic extra-field acceptance does not prove shared-evidence counting or reverse role traversal. Keep this as an explicit compatibility check before declaring the final graph accepted. Do not alter Agent code or remove an agreed direction without reporting the issue first.

## 7. Relation catalog S2T

The Agent reads a relation definition's label, family, source predicate, direction and mapping status. Reuse its existing catalog adapter shape rather than defining a new business ontology.

| Target path in `relation_catalog[relation_id]` | Source / rule |
|---|---|
| `id` | Exact exported base or reverse predicate ID; also the catalog dictionary key. |
| `labels` | Existing label strings from applied `level2_relation_label`, or the lookup's exact reverse label. Highlight conflicting meanings rather than relying on the loader's first-label selection. |
| `level1_families` | Existing applied `level1_family` values; consistency with relation rows must be checked. Conflicting families need a decision before export. |
| `source_predicates[].source` | Existing mapping `source`. Retain supplied source mappings. |
| `source_predicates[].predicate` | Existing mapping `source_predicate`. |
| `source_predicates[].direction` | Existing `direction_to_level2` for the base predicate. A reverse predicate needs an explicit catalog definition; do not copy a base direction or invent a conversion. |
| `review_statuses` | Existing catalog review/status values, if supplied; otherwise omit this optional field. No new review decision is made by export. |
| Direction-pair audit fields | Retain `direction_pair_id`, `reverse_resolution_type` and endpoint action in supporting direction artifacts. The current Agent catalog adapter does not consume them; reverse edges carry their defined view fields. |

Every exported base or reverse predicate must be present in the exported catalog. If several source mapping rows disagree on one relation's family/meaning, highlight the exact rows. Do not solve that disagreement through a new aggregation or a label guess. Catalog inclusion does not create entity nodes or source assertions.

## 8. Visible exceptions and release checks

An export report is a supporting release artifact, not a seventh business table. It must show affected IDs, source values, target fields, counts, reason and the decision needed. Do not present conflicts as a hidden unresolved bucket or silently drop affected records.

| Check | Required response |
|---|---|
| A QID has multiple saved types | Preserve every distinct QID/type pair. Verify Agent loading and type filters retain all types, with QID-level edges. This is an integration check, not a canonical-type decision. MISC is not an open classification question. |
| Wikidata event classification or dates cannot fit target scalar fields | Show the event QID, exact claims/values and target fields. No ranking, precision invention, label translation or conflict selection. |
| Missing names, endpoints, mapping definitions or direction keys | Show exact records and counts. Do not invent required values or rely on Agent endpoint dropping. |
| Missing geometry vs invalid geometry/unknown CRS | Report these separately. No missing or rejected object gets a fabricated pointer. Missing-object JSON behavior requires agreement; invalid supplied geometry/CRS must be highlighted before use. |
| Geometry pointer and Agent loader | Agree the exact pointer schema, object location/version binding, function interface, CRS handling and missing-object behavior before implementation. Verify each pointer resolves to the selected valid Shapely object; no inline GeoJSON geometry enters graph JSON. |
| Event inclusion evidence | Report candidate events, included/excluded event counts and each event's distinct qualifying Daniel QIDs. Check count >=2 independently of mentions, duplicate assertions and reverse views. |
| Reverse compatibility | Verify both-direction queries, exact inverse IDs, and one evidence identity/support count. Agent format acceptance alone is insufficient. |
| Intentional omissions | Confirm no node/edge `sources`, node `text`, paragraph objects, mention/page nodes or extraction audit payloads entered the graph. Supporting provenance remains recoverable separately. |
| Final graph integrity | Unique node/view IDs, every edge endpoint exists, correct event QIDs, full base-assertion accounting, exact mapping version and no unintended node expansion. |

Do not publish a final accepted graph while an unresolved required-field or semantic conflict is hidden. This specification records already identified gaps; it does not claim that those conditions have occurred in a newly executed export. No graph build or data-quality run was performed for this document.

## 9. Contract evidence and current limits

- [Agent README input contract](https://github.com/EtzionR/Corpus2GeoRAG_Pacific/blob/main/Agent/README.md#input-schema-for-the-knowledge-graph-builder), verified on 19 October 2026; Git blob `d6929c7e276c564cb7ef1cf219cb1b9414ce0f26`. The target is the graph input, not the Agent's answer JSON or UI result schema.
- [Agent loader and text search](https://github.com/EtzionR/Corpus2GeoRAG_Pacific/blob/main/Agent/geo_agent/graph_store.py), inspected Git blob `3d67affe310e0336c579adcf8dcc0362702100ba`. Remote Agent implementation is newer than the local checkout.
- [Relation-map-v2.1.0 delivery rules](RELATION_MAPPING_V2_1_DATA_LAYER_REVERSE_2026-10-15.md), [mapping table](../GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.0.csv), [direction lookup](../GG_Data/mapping/RELATION_DIRECTION_LOOKUP_v2.1.0.csv) and [direction catalog](../GG_Data/mapping/RELATION_DIRECTION_CATALOG_v2.1.0.csv).
- [Geography policy](GEOCODING_HIGH_LEVEL_PROCESS.md). Shapely is the geometry output; graph JSON holds an object pointer. The user's latest decision supersedes the inspected Agent inline-GeoJSON format for this interface. Source CRS metadata remains required; pointer loading and spatial-function compatibility remain open.
- [Existing matching type decisions](../GG_Data/entity_resolution/bilingual_page_pilot.py): `categories` / `choose` and saved `type_metadata` remain unchanged. The later population decision preserves distinct QID/type pairs and QID-level relations; no canonical type selector or new event classifier is introduced.

The source model is an agreed logical design with explicit implementation exceptions. Existing matching artifacts are saved outputs; the six physical tables and this exporter are not implemented by this S2T document. Remaining checks include Agent support for coexisting types with QID-level relations, source values that cannot fit the target, final release metadata, geometry pointer/function interface and recognition of explicit reverse views. New cases must be brought back to the user before adding logic.
