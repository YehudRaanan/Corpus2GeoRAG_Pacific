# Daniel input to final graph JSON review

Review date: 19 October 2026. This is the consolidated discussion list for the full pipeline. It records agreed rules, decisions still needed, implementation checks, and deferred improvements. It does not approve new rules or start a data run.

The open items below are specification or integration gaps. Conditional cases have not been counted in a newly populated model. Before resolving a data-dependent case, show its actual IDs, source values and affected counts; do not assume every possible exception occurs.

## Full pipeline

| Step | Input and action | Output and agreed boundary |
|---|---|---|
| 1. Receive Daniel input | Verify the pinned file and preserve its original mention rows and extraction fields. | Exactly the original mention population. No new entity extraction, splitting or combining. No paragraph object or paragraph-level processing. |
| 2. Resolve source pages | Use supplied verified site/article IDs when available; currently use saved source lookup and redirects. Include retrieved Japanese counterparts. | Wiki Pages and mention page keys. Missing lookups remain explicit. Numeric page IDs require wiki site; Daniel Index is not a page ID. |
| 3. Match identities | Reuse the completed run: bilingual page/direct-name candidates, then the frozen already-matched pool, then the saved fresh-WWII pool. Highest trigram Dice score >=0.80 with agreed type checks and saved seeded ties. | Existing matched Wikidata QIDs. Date parsing is separate. No matching changes in this review. |
| 4. Preserve unresolved mentions | Keep each saved unresolved mention and its existing separate synthetic ID, reason, original type, attempts and evidence. | No synthetic merging, guessed QID or invented entity. Successful normalized dates remain structured mention data with null entity FK. |
| 5. Populate identities and evidence | Populate Entities, Mentions and Wiki Pages. Name priority is English Wikidata label, Japanese label, then Daniel name. | One entity per QID or existing synthetic ID. Full evidence stays in the model/supporting artifacts. Canonical type/name exceptions are visible. |
| 6. Retrieve Wikidata facts and events | Reuse full saved records; obtain missing relevant assertions in bulk. Discover native event instances under Q140451665 through P31/P279. Check direct connections in either direction to Daniel's matched QIDs. | All native event types are eligible. Include an event only with at least two distinct matched Daniel QIDs. No indirect participant paths or recursive entity expansion. WarSampo/EventKG facts stay outside this workflow. |
| 7. Populate Relations and Events | Keep Wikidata assertions between matched Daniel QIDs and included-event/Daniel links. Apply exact exclusions and relation-map-v2.1.0 once from original source orientation. | One base row per source assertion; native event QIDs and values. Unknown mappings/conflicting values are reported. Reverse graph views are not new evidence. |
| 8. Assign geography | Use the existing OHM -> OSM priority, restricted WHG reconciliation and supported name/context fallback including GeoNames. Apply the existing date, identity, representation and validation rules. | At most one accepted Shapely object per confirmed place QID, persisted as WKB in GeoParquet, plus complete audit. No guessed shapes or Wikidata geometry promotion. |
| 9. Export graph | Apply the separate model-to-graph S2T. Export the selected entity/event nodes, mapped base/reverse edges and catalog. | One graph JSON with metadata, relation_catalog, nodes and edges. Geometry is an object pointer. No page/mention/paragraph nodes, node text or node/edge provenance payloads. |
| 10. Verify Agent handoff | Check IDs, endpoints, predicates, dates, reverse evidence identity and geometry-pointer loading. | Acceptance requires the actual Agent integration to work; a valid JSON file alone is insufficient. |

## Decisions still needed

The first five items affect identity or event values. Item P06 affects relation meaning. P07, P08 and P12 apply only when those cases occur. P09-P11 define the required geometry interface.

| ID | Stage and open question | Existing boundary and decision needed | Evidence |
|---|---|---|---|
| P01 | Entity types: what graph type represents MISC or another unmatched type? | PER -> person, ORG -> org and LOC -> location are agreed. MISC is not event. A general fallback or extra Agent type has not been approved. Show affected entities before choosing. | Graph S2T, node type mapping and visible exceptions. |
| P02 | One QID has different resolved mention types, or is both a Daniel identity and an included event. Which canonical type/role is exported? | Reuse saved per-mention decisions and one QID identity. Do not vote, take the first type or let event membership overwrite another type silently. This needs the actual conflict cases and a canonical rule. | Population S2T Entities/Events; graph S2T included nodes. |
| P03 | Both English and Japanese labels are absent. Which name is used when Daniel has several different names, or an added event has no Daniel mention? | The agreed fallback reaches Daniel's name, but does not select among different names or define a final fallback for an unlabeled extra event. Do not invent a QID-as-name or generated name. | Population S2T Entities. |
| P04 | How does native Wikidata event classification fit the Agent kind field? | Keep native class values and multiple classifications. No battle/campaign/war conversion or internal level is approved. Agree a lossless target representation when a QID/list cannot fit the target scalar. | Population S2T Events; graph S2T attributes.kind. |
| P05 | How do multiple, partial or incompatible Wikidata dates fit graph scalar date fields? | Preserve source values, precision, calendars and all claims. No date ranking, range invention or conflict selection. Inspect exact cases and agree representation/Agent support, rather than selecting silently. | ERD Events/Relations; graph S2T temporal fields and visible exceptions. |
| P06 | What happens for a fresh predicate without one mapping, conflicting catalog labels/families, or a reverse relation lacking its catalog direction/family definition? | Use exact versioned keys. Unknown/ambiguous mappings and conflicting semantics must be shown before adding or changing a mapping. Existing historical catalog coverage does not prove coverage of fresh facts. | Population S2T Relations; graph S2T relation catalog and reverse edge mapping. |
| P07 | If a future Daniel-supplied page ID conflicts with saved lookup, which source controls the key? | Current lookup and null-on-failure behavior are agreed. Preserve both pieces of evidence and show the conflict. No future override rule is approved. | Population S2T Mentions and explicit exceptions. |
| P08 | How is a geometry selection date set when only partial or conflicting related dates are usable? | The approved rule is the earliest related date inside 1941-12-07..1945-09-02, else 1941-12-07. It does not authorize inventing a day or choosing a conflict. Agree only the missing interpretation after seeing cases. | Population S2T Geography; geocoding selection-date policy. |
| P09 | What exactly is the graph geometry pointer, and how does the Agent load it? | Agree JSON field/structure, object identifier, storage location, artifact/version binding and loading function inputs/return. The return is Shapely. No inline GeoJSON or memory address. | Both S2Ts and geocoding production limits. |
| P10 | What CRS and spatial behavior does the Agent require? | Preserve known source CRS in storage. Agree loading/spatial-function CRS, any required transformation, and behavior at the antimeridian. A missing CRS is not guessed. | Graph S2T geometry interface; geocoding production limits. |
| P11 | How does graph JSON and the Agent represent absent geometry versus a broken pointer or invalid object? | A valid identity may lack geometry. Unresolved/rejected geometry gets no fabricated object. Agree omitted/null representation and missing/broken/invalid loading behavior separately. | Graph S2T geometry field and visible exceptions. |
| P12 | If approved geography sources cannot resolve a place, is a specific specialist source or manual construction needed? | Leave it unresolved under the current policy. A generic specialist/manual fallback does not approve a concrete new dataset or construction method. Discuss a named source and rule only for an actual remaining case. | Population S2T Geography; geocoding source order. |

No item in this list authorizes a new classifier, matching threshold, source, inferred event or geometry. A case report is required before a new data-dependent rule; routine implementation of an existing rule is not a new permission request.

## Implementation and verification work

These are checks or changes required to implement agreed behavior, not questions that reopen that behavior.

| ID | Required work | Completion evidence |
|---|---|---|
| T01 | Verify the input/run manifest and populate every original mention with stable IDs, separate NER/matching scores and full decisions. Check page key uniqueness/FKs and accepted supplied-page or lookup origin. | Hash and row accounting; no added/changed mentions; every nullable key justified. |
| T02 | Reuse cached data and retrieve complete needed Wikidata records. Keep snapshot, query, request/job evidence, checksums and missing-QID lists. | Full claims/ranks/qualifiers/references available where needed; compact matching metadata is not presented as complete facts. |
| T03 | Verify native event hierarchy coverage and both incoming/outgoing direct assertions. Do not count shared class ancestry, repeated mentions or reverse copies toward the two-entity minimum. | Event selection report with QIDs, hierarchy evidence, qualifying statement IDs and distinct Daniel QIDs/counts. |
| T04 | Align the relation producer with current source scope, all eligible assertions/ranks, exact exclusions and v2.1 mapping. The legacy producer skips deprecated statements; that skip cannot silently remove facts under the latest scope. Restore original orientation before replaying v1 records. | Eligible statement accounting, exclusions, unmapped cases, applied catalog hashes and no double swaps. |
| T05 | Verify reverse navigation and shared evidence identity in the Agent. The inspected implementation groups endpoint/predicate/date equivalents and has not proved explicit source_edge_id handling. | Both directions searchable; exact reverse IDs; distinct native assertions preserved; generated reverse views do not double support. |
| T06 | Verify the actual Agent contract/version against the new graph, including case-preserving predicates, relation families/catalog, point dates, valid node types and object pointers. Local Agent code is older than the version cited by the graph S2T. | Pinned Agent revision and behavior tests. Old draft compatibility findings are not assumed to describe the current implementation. |
| T07 | Implement the approved geography policy and verify selected object identity, nonempty valid Shapely/WKB round trip, provenance, source dates and CRS. Once P09-P11 are defined, check pointer loading against the same accepted stored object. | Geometry audit and integration results; first-50 POC results do not count as a full-Daniel geometry run. |
| T08 | Populate and check all six physical tables, then generate and validate the final graph. Supply real schema/release/scope metadata, hashes and complete exception accounting. | All required fields and endpoints present; no extra identities; exact base/reverse counts; graph and referenced geometry artifacts recoverable together. |

These documents define the target. They do not establish that the six tables, new full statement/event acquisition, full geography run or new final graph are complete.

## Documentation points to align

| ID | Point | Required clarification or correction |
|---|---|---|
| C01 | Entity-resolution README still says final matching counts are unavailable. | Its current-run status is stale relative to the saved completed run and population S2T. Update from verified summary/manifest, while preserving historical run descriptions. |
| C02 | The ERD and population S2T retain Text/Index as legacy raw fields, while the user excludes paragraph data/management. | The original input can be preserved as source evidence without creating a paragraph object. Confirm whether legacy Text/Index remain only in the original artifact or also in active Mentions/raw payload. Align the table contract before physical population; do not reintroduce paragraph processing. |
| C03 | Older contract/request and geometry POC documents describe wider providers, older graph counts or an export-conversion gate. | Latest population scope is Wikidata facts/events only; latest geometry interface is an object pointer loaded as Shapely. Mark historical terms/figures as superseded where they could be mistaken for current rules. No WarSampo import or inline GeoJSON conversion follows from older documents. |
| C04 | ERD closing text calls event mapping version an unresolved prerequisite. | The latest event rule adds no internal mapping catalog: event_map_version is reserved/null. Native root and snapshot belong in lineage. This is settled, not another business-rule question. |

C02 is the one storage-contract clarification in this section. The other entries concern stale wording or already superseded requirements.

## Deferred analysis and upstream follow up

| ID | Item | Current treatment |
|---|---|---|
| D01 | Improve unresolved identity coverage. | The saved summary has 41,106 unresolved mentions: 25,524 name threshold, 5,064 type mismatch, 2,055 unknown type, 8,463 invalid/unsupported date. Keep distinct reasons/attempts and existing per-mention synthetic IDs. Improvement is later work; it does not block preserving/exporting agreed synthetic identities. |
| D02 | Four unresolved source-page requests. | Retain original Source and page failure evidence with null page keys. Investigate later; no fake page and no requirement to discard the mention. |
| D03 | 21,135 QIDs unavailable in the old fresh-WWII matching reference. | Preserve the known matching coverage limit. A later recovery or rerun requires its own scope; event acquisition is not restricted to that old fallback pool. |
| D04 | More specific references from Daniel. | Later ask Daniel for wiki site/article page ID and source URL; revision/permanent URL when available. No message has been sent or is authorized by this review. |
| D05 | Identity accuracy and candidate coverage. | Matching counts are not an accuracy estimate. Review saved false matches, source link/navigation coverage and broad type behavior later without silently changing assignments or inventing mentions. |

## Rules already settled

- Use all original Daniel mentions; no independent entity extraction, splitting or combining.
- Keep the existing >=0.80 trigram method, type handling, pass order and saved random tie decisions.
- Preserve one existing synthetic ID per unresolved mention. English/Japanese labels of the same item share one Wikidata QID.
- Keep successful DATE results as structured mention data; do not create events from date strings or MISC.
- Name order is English Wikidata, Japanese Wikidata, Daniel name, subject to P03's remaining fallback cases.
- Wikidata supplies current assertions and events. WarSampo is ignored; EventKG facts are outside current acquisition scope.
- Use all event types under native root Q140451665; include an event at two distinct matched Daniel QIDs through direct mapped connections in either direction.
- Relations contains Daniel-QID/Daniel-QID assertions and included-event/Daniel links. No arbitrary event/event expansion or seventh participant table.
- Apply exact approved exclusions and relation-map-v2.1.0. Reverse views share base evidence; genuinely separate source statements remain separate.
- Geography uses approved sources and policy. Older OSM snapshot age is accepted; historical identity/meaning checks remain.
- Geometry is Shapely, persisted as WKB; graph JSON references the stored object. No inline GeoJSON conversion.
- Omit node/edge sources and node text from the graph for now. Preserve source provenance in the model/supporting artifacts; omit page/mention/paragraph graph nodes.
- Do not invent event categories, levels, preferred dates, participant roles, importance scores, embeddings or geometry.

## Discussion order

Start with P01-P03 because every graph node needs a usable name/type. Then resolve P04-P06 for events and relation meaning. Define P09-P11 together as one geometry interface. Check C02 before materializing Mentions. Handle P07, P08 and P12 with actual cases if they occur. Perform T01-T08 and maintain D01-D05 as explicit later work; do not report them all as blocking business decisions.

## Source documents

- [Sources to model S2T](SOURCES_TO_ENTITY_DATA_MODEL_S2T.md), especially Entities, Events, Relations, Geography and explicit exceptions.
- [Six-table ERD](ENTITY_DATA_MODEL_ERD.md), including exact retained field inventories.
- [Model to final graph S2T](ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md), including node/edge/catalog mapping and visible exceptions.
- [Geocoding policy](GEOCODING_HIGH_LEVEL_PROCESS.md) and [geometry POC method](../GG_Data/geocoding/GEO_OBJECT_EXTRACTION_METHOD.md).
- [Entity-resolution README](../GG_Data/entity_resolution/README.md) and the pinned completed-run summary/manifest named by the population S2T.
- [Historical Agent contract update request](../GG_Data/agent_export/AGENT_CONTRACT_UPDATE_REQUEST.md); current user decisions and S2Ts take precedence.

Closing an item requires a recorded decision or verification result, its affected records where applicable, and a corresponding update to the governing S2T/contract. Listing a proposal here does not change the agreed pipeline.
