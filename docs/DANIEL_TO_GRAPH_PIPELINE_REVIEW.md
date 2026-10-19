# Daniel input to final graph JSON review

Review date: 19 October 2026. This is the consolidated discussion list for the full pipeline. It records agreed rules, decisions still needed, implementation checks, and deferred improvements. It does not approve new rules or start a data run.

The earlier list overstated the open business decisions. Settled rules, conditional exceptions and technical interfaces are separated below. The user confirmed that distinct `(Wikidata QID, type)` combinations coexist and Relations remains at QID level. MISC is not an open issue. Before adding a data-dependent rule, show actual IDs, source values and affected counts.

## Full pipeline

| Step | Input and action | Output and agreed boundary |
|---|---|---|
| 1. Receive Daniel input | Verify the pinned file and preserve its original mention rows and extraction fields. | Exactly the original mention population. No new entity extraction, splitting or combining. No paragraph object or paragraph-level processing. |
| 2. Resolve source pages | Use supplied verified site/article IDs when available; currently use saved source lookup and redirects. Include retrieved Japanese counterparts. | Wiki Pages and mention page keys. Missing lookups remain explicit. Numeric page IDs require wiki site; Daniel Index is not a page ID. |
| 3. Match identities | Reuse the completed run: bilingual page/direct-name candidates, then the frozen already-matched pool, then the saved fresh-WWII pool. Highest trigram Dice score >=0.80 with agreed type checks and saved seeded ties. | Existing matched Wikidata QIDs. Date parsing is separate. No matching changes in this review. |
| 4. Preserve unresolved mentions | Keep each saved unresolved mention and its existing separate synthetic ID, reason, original type, attempts and evidence. | No synthetic merging, guessed QID or invented entity. Successful normalized dates remain structured mention data with null entity FK. |
| 5. Populate identities and evidence | Populate Entities, Mentions and Wiki Pages. Name priority is English Wikidata label, Japanese label, then Daniel name. | One Entities row per distinct `(entity_id, type)` combination. Multiple types coexist; QIDs/SYN IDs remain unchanged. Mentions uses the composite key. Full evidence stays in the model/supporting artifacts. |
| 6. Retrieve Wikidata facts and events | Reuse full saved records; obtain missing relevant assertions in bulk. Discover native event instances under Q140451665 through P31/P279. Check direct connections in either direction to Daniel's matched QIDs. | All native event types are eligible. Include an event only with at least two distinct matched Daniel QIDs. No indirect participant paths or recursive entity expansion. WarSampo/EventKG facts stay outside this workflow. |
| 7. Populate Relations and Events | Keep QID-level Wikidata assertions between matched Daniel QIDs and included-event/Daniel links. Apply exact exclusions and the pinned mapping version (currently v2.1.1) once from original source orientation. | One base row per source assertion, without expansion across endpoint types; native event QIDs and values. Missing native source keys follow the approved parameter-addition rule; conflicts are reported. Reverse graph views are not new evidence. |
| 8. Assign geography | Use the existing OHM -> OSM priority, restricted WHG reconciliation and supported name/context fallback including GeoNames. Apply the existing date, identity, representation and validation rules. | At most one accepted Shapely object per confirmed place QID, persisted as WKB in GeoParquet, plus complete audit. No guessed shapes or Wikidata geometry promotion. |
| 9. Export graph | Apply the separate model-to-graph S2T. Export the selected entity/event nodes, mapped base/reverse edges and catalog. | One graph JSON with metadata, relation_catalog, nodes and edges. Geometry is an object pointer. No page/mention/paragraph nodes, node text or node/edge provenance payloads. |
| 10. Verify Agent handoff | Check IDs, endpoints, predicates, dates, reverse evidence identity and geometry-pointer loading. | Acceptance requires the actual Agent integration to work; a valid JSON file alone is insufficient. |

## Decision and interface status

P01 and P02 are closed business questions. P03-P08 are settled rules with implementation checks or conditional exceptions, not requests to decide hypothetical cases. P09-P11 are one geometry interface. P12 already has an unresolved-result rule. Agent support for coexisting QID types is technical integration work.

| ID | Stage and open question | Existing boundary and decision needed | Evidence |
|---|---|---|---|
| P01 | Closed: MISC classification is not relevant to the open issues. | Keep existing classifications. No new category, event inference or type choice is required by this item. | User annotation; graph S2T. |
| P02 | Closed: different types for one QID coexist. | Preserve distinct `(entity_id, type)` rows, including LOC and ORG. The saved audit found 692 such QIDs across 15,882 mentions. No canonical winner. Relations remains at QID level; no assertion expansion across type combinations. Event membership does not erase another type. | User annotations and QID-level Relations confirmation; ERD and both S2Ts. |
| P03 | Settled naming rule; only actual missing fallback cases need review. | English -> Japanese -> Daniel. The saved matched population has 21 QIDs without English/Japanese labels, each with one distinct Daniel name; no fallback-name choice is needed there. An unlabeled added event or genuinely differing fallback names is conditional, not an observed current blocker. | Read-only matching CSV/metadata audit; population S2T Entities. |
| P04 | Technical check: native event classification representation. | Use Wikidata values as supplied. No internal categories or levels. Show an actual target incompatibility before changing representation or requesting a new rule. | Population S2T Events; graph S2T attributes.kind. |
| P05 | Technical check: native date representation. | Preserve supplied values, precision, calendars and claims. Event dates unchanged; Relations use the approved population S2T section 8 date policy. Show exact source/target incompatibilities if found. | ERD Events/Relations; graph S2T temporal fields. |
| P06 | Settled native fallback rule; conflicting mappings remain conditional. | Use existing exact mappings first. An actual direct Wikidata statement with a missing native source key can add its original property/direction at Level 2, leaving Level 1 unassigned. Reuse any existing identical definition/reverse contract. No native statement means no relation. Ambiguous/conflicting mappings still stop. | User approval 20 October; population S2T section 8; current catalog v2.1.1. |
| P07 | Conditional future page-ID conflict, not a current blocker. | Current lookup/null-on-failure rules stand. Show an actual future input/lookup conflict before choosing an override. | Population S2T Mentions. |
| P08 | Conditional geometry-date exception. | Earliest supported related date inside 1941-12-07..1945-09-02, else 1941-12-07. Do not invent a day; show actual values only if the existing policy cannot handle them. | Population S2T Geography; selection-date policy. |
| P09 | Closed: file/place/checksum geometry pointer approved. | `geometry_ref={file,place_id,sha256}` references GeoParquet and its place QID. `load_geometry(pointer, artifact_root)` returns Shapely. Helper implemented; Agent integration pending. No inline GeoJSON or memory address. | User approval; both S2Ts; `GG_Data/pipeline/graph_contract.py`. |
| P10 | What CRS and spatial behavior does the Agent require? | Preserve known source CRS in storage. Agree loading/spatial-function CRS, any required transformation, and behavior at the antimeridian. A missing CRS is not guessed. | Graph S2T geometry interface; geocoding production limits. |
| P11 | Closed: absent geometry is null; broken reference is an error. | No accepted object -> null. Missing/corrupt artifact, checksum mismatch, duplicate/missing place, invalid/empty object or unknown CRS -> explicit error. No fabricated replacement. | User approval; graph S2T and interface helper. |
| P12 | Settled: failure of approved geography sources leaves an unresolved result. | No new source or construction is needed to continue under the agreed policy. Discuss a named additional source only if later proposed for an actual case. | Population S2T Geography; geocoding source order. |

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
| T06 | Implement the approved Agent interface: separate `QID::type` entities with original `wikidata_id`; QID relation endpoints resolve to those entities without copying assertions. Interface helpers have fixture checks; the current Agent engine is not integrated. Verify case-preserving predicates, catalog, dates and object pointers. | Pinned Agent revision and end-to-end query checks; no node overwrite or assertion multiplication. Local Agent is older than the cited remote version; verify the integration revision. |
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
- Preserve distinct `(Wikidata QID, type)` combinations. Multiple types coexist, including an independently included event role. Relations remains at QID level; neither a canonical type selector nor an expansion across type combinations is used. MISC is not an open issue.
- Keep successful DATE results as structured mention data; do not create events from date strings or MISC.
- Name order is English Wikidata, Japanese Wikidata, Daniel name, subject to P03's remaining fallback cases.
- Wikidata supplies current assertions and events. WarSampo is ignored; EventKG facts are outside current acquisition scope.
- Use all event types under native root Q140451665; include an event at two distinct matched Daniel QIDs through direct mapped connections in either direction.
- Relations contains Daniel-QID/Daniel-QID assertions and included-event/Daniel links. No arbitrary event/event expansion or seventh participant table.
- Apply exact approved exclusions and the pinned current mapping version (v2.1.1 for the native P2341 addition). Reverse views share base evidence; genuinely separate source statements remain separate.
- Geography uses approved sources and policy. Older OSM snapshot age is accepted; historical identity/meaning checks remain.
- Geometry is Shapely, persisted as WKB; graph JSON references the stored object. No inline GeoJSON conversion.
- Omit node/edge sources and node text from the graph for now. Preserve source provenance in the model/supporting artifacts; omit page/mention/paragraph graph nodes.
- Do not invent event categories, levels, preferred dates, participant roles, importance scores, embeddings or geometry.

## Discussion order

Do not reopen P01/P02/P09/P11. Typed entity IDs, QID endpoints and geometry pointers are approved. Implement Agent integration under T06 and verify spatial CRS requirements under P10. D: output was approved on 20 October 2026. The first population step completed for 10,000 original mentions and 691 resolved Wiki Pages; exact source rows, saved decisions, output hashes and keys passed verification. Counts and the known missing-page outcomes are in `GG_Data/pipeline/README.md`. The separate Entities step subsequently passed in `poc_10k_entities_approved` with 6,077 rows and unchanged first-step artifacts. Its status is `ENTITIES_STEP_ONLY`; Events, Relations, Geography, graph export and Agent integration remain pending. The first relation check stopped on the P2341 native source-key gap below. The user then approved native property preservation; v2.1.1 now includes that key. Missing native keys covered by this rule do not need individual approval. The later Daniel/Daniel replay passed; see the checkpoint below. Bring actual exceptions back before changing logic; retain D01-D05 as deferred work.

## Source documents

20 October 2026 Entities checkpoint: full references for all 4,712 sample QIDs
are available (506 archive records and 4,206 cached full records). The user
approved older English labels for Q132537 and Q1771928. The separate approved
rerun passed with 6,077 Entities rows (4,721 QID/type pairs plus 1,356 unchanged
synthetic IDs), 691 Wiki Pages and 197 existing subjects. Zero CLI calls were
made; first-step hashes are unchanged. The first blocked attempt stays draft
for audit. See population S2T section 6 and the pipeline README.

Observed P06 exception: the first cache-only D/D mapping check stopped on
`wd:P2341`, Poles (`Q105969841`) -> Poland (`Q36`), native statement
`Q105969841$8D05BA41-C448-45B5-93EA-A37877F5140D`. There is no exact Wikidata
mapping key in v2.1.0. The check stopped after 191 eligible non-excluded
statements; total affected population is not yet known. No mapping, relation
row or event acquisition was added during that check. After discussion, the user
approved the general native-preservation rule: use actual Wikidata statements,
add missing native source keys, retain Level 2/direction and leave Level 1
unassigned. The new v2.1.1 table adds P2341's Wikidata key, reusing its existing
Level 2/reverse definition from the older catalog without importing EventKG
facts. Checks passed: 27 tests and 2 subtests; historical v2.1.0 CSVs rebuild
byte-for-byte. The general rule is now settled; other data surprises still
require consultation.

The Ribbentrop multiple-start case is resolved by the approved Relations date policy: earliest start from 1900; all starts earlier -> derived year 1900; latest end; exclude relations whose latest end precedes 1900. Preserve all source values and precision. Events do not inherit this selection rule. The Prague 1804-1867 statement is therefore excluded. Historical stop artifacts remain evidence. An overstrict P53 formal-conflict guard was corrected to respect the catalog's existing native-retention decision; no mapping decision changed.

The cache-only replay source gate passed: 4,712 QIDs, 213,277 raw claims, 10,501 in-scope statements, 34 pre-1900-end exclusions and 10,467 retained statements. Artifact: `outputs/poc_10k_relations_date_scope_check_20261020/source_check.json`. This check alone does not populate Relations or finish the automatic fallback, Events or graph.

Daniel/Daniel Relations then passed: 10,467 base statements, 34 pre-1900-end exclusions and 86 temporal-decision audit rows. POC v2.1.2 adds nine native source keys with Level 1 unassigned; prior decisions and reverse labels remain unchanged. Nine property records were retrieved/cached after user approval. Successful manifest: `outputs/poc_10k_relations_labels_preserved_20261020/manifest.json`; final replay location: `outputs/poc_10k_relations_final_20261020` (require its manifest before use). This is `DANIEL_RELATIONS_ONLY`, not event discovery, full Relations, Geography or graph completion.

The final Relations replay manifest and all recorded hashes subsequently passed; Relations/exclusions/temporal-audit contents are identical to the previous successful run. Event acquisition then stopped before discovery: the approved root Q140451665 is absent from the pinned BigQuery snapshot, confirmed by a zero-row query at `2026-10-18T18:45:19.304197+00:00` (job `geoai_6d050ce4cff5a35c6380e995468a4bfe`, zero bytes billed). Evidence: `outputs/poc_10k_event_root_check_20261020/root_check.json` and cached query artifacts in `outputs/wikidata_event_cache`. This does not establish that current Wikidata lacks the root or that the snapshot lacks events. No replacement root, snapshot or hierarchy logic was selected. Checking a newer Wikidata snapshot for the same approved hierarchy is pending user discussion. All completed upstream outputs remain unchanged.

- [Sources to model S2T](SOURCES_TO_ENTITY_DATA_MODEL_S2T.md), especially Entities, Events, Relations, Geography and explicit exceptions.
- [Six-table ERD](ENTITY_DATA_MODEL_ERD.md), including exact retained field inventories.
- [Model to final graph S2T](ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md), including node/edge/catalog mapping and visible exceptions.
- [Geocoding policy](GEOCODING_HIGH_LEVEL_PROCESS.md) and [geometry POC method](../GG_Data/geocoding/GEO_OBJECT_EXTRACTION_METHOD.md).
- [Entity-resolution README](../GG_Data/entity_resolution/README.md) and the pinned completed-run summary/manifest named by the population S2T.
- [Historical Agent contract update request](../GG_Data/agent_export/AGENT_CONTRACT_UPDATE_REQUEST.md); current user decisions and S2Ts take precedence.

Closing an item requires a recorded decision or verification result, its affected records where applicable, and a corresponding update to the governing S2T/contract. Listing a proposal here does not change the agreed pipeline.
