# Daniel input to final graph JSON review

## Approved relation selection — 20 October 2026

Event/Event and Event/other-entity links are uncapped, after each Event independently passes the existing inclusion gate. Other entity/other entity links are capped at 20 incident base assertions per QID. Rank by the connected QID's distinct Daniel source-page count multiplied by its original Daniel mention count. Keep a non-event assertion only when it is in the top 20 at both endpoints; do not refill slots lost by this intersection. Reverse views spend no extra slot. Multiple types share the QID-level budget.

This supersedes the earlier prohibition on direct links between included Events. No new endpoint population, Event hierarchy, source, matching decision or date policy is approved. Selection evidence remains supporting data; acquired raw statements and historical outputs remain intact. Exact cutoff ties or unavailable score inputs require a concrete case discussion. The [population S2T](SOURCES_TO_ENTITY_DATA_MODEL_S2T.md#non-event-relation-selection--approved-20-october-2026) is the rule reference.

Status: selector implemented and tested; actual application awaits complete Event membership. `outputs/poc_10k_relation_importance_20261020` saves scores for 4,712 QIDs from the frozen sample's 7,692 matched non-DATE mentions, with original `raw.Source` page counts and checksum lineage. No capped Relations or graph is written. The user's subsequent instruction to implement and keep running starts the paged continuation below; the cap does not prove full Event coverage.

Latest approved Entity attribute run: `outputs/poc_10k_entities_importance_20261020` persists scalar `importance` plus `attributes.importance_basis` on the existing Entities table. Verified: 6,077 unchanged identities, 4,721 scored typed rows for 4,712 QIDs, 1,356 synthetic nulls, unchanged prior fields and source evidence, valid hashes, 56 tests passed. Scores use the frozen 10K population. Event importance is separate. No new service request ran; the Canada Event acquisition stop remains open.

## Current continuation: paged source acquisition

Verified status: **stopped, not running**. The first new Canada/Q16 page timed out after 45 seconds without a response body. No automatic timeout retry or smaller/new query was attempted. All 4,712 native records and the two complete Africa incoming responses were reused; accepted source coverage remains 2/9,424 graph/QID requests and 75,655 partial reference candidates. `verification.json` is `VERIFIED_PAGED_DISCOVERY_SOURCE_STOP_ONLY`, with 105 source-response hashes, 14 upstream hashes and 17 preceding candidate output hashes checked. The earlier failed body is unchanged. Zero Event rows, capped Relations or final graph are produced. The proposed one-property retrieval test is under discussion after the user asked for an explanation; it is not authorized or running.

Run: `GG_Data/pipeline/outputs/poc_10k_event_full_discovery_paged_20261020`. The continuation reuses complete native and incoming caches, then requests up to 5,000 incoming statements per ordered native-URI page on both official query graphs. It requires complete page coverage and a short terminal page, rejects unordered/overlapping results, preserves all original responses, and keeps the approved request pauses/retry budget and stop rule. Reference candidates remain distinct from included Events. No Event date/type/endpoint rule or Daniel matching decision changes. Read the current report/logs for stage and counts. Before launch: 55 tests and Ruff checks passed. The historical Canada response remains immutable.

## Previous: full discovery stopped at Canada source failure

The continuation reached complete outgoing coverage but stopped during incoming
acquisition, as required. Both Africa/Q15 graph searches completed (29,923
statements). The next main-graph Canada/Q16 response had HTTP 200 and
352,032,025 bytes, with a server `TimeoutException` appended inside unfinished
JSON. Its complete bytes/checksum remain cached. No partial rows, malformed-data
retry or independent retrieval change were accepted; the process has ended.

`verification.json` in the new run records
`VERIFIED_FULL_DISCOVERY_SOURCE_STOP_ONLY`: 4,712 native records checked,
2/9,424 incoming graph/QID requests complete, 75,655 partial reference candidates,
105 source-response checks, 17 unchanged preceding candidate output hashes and
14 unchanged upstream hashes. There are zero new Event rows. These reference
counts do not establish Event inclusion or full discovery.

User consultation is pending on smaller incoming pages (at most 5,000 native
statements, ordered identity cursor, both graphs and complete page chain).
No pagination logic or new data rule is approved/implemented at this checkpoint.
Tests: 50 passed before launch; the strengthened discovery test passed afterward.

## Full-population discovery authorization

The user approved discovery across all 4,712 matched Daniel QIDs, using the
existing approved sources/rules. `event_discovery.py` reads cached outgoing
native records and the existing incoming query on both Wikidata graphs. It
preserves the raw non-DATE population definition, all statement ranks and the
same seven explicit saved-native fallbacks. Sources, matching and IDs stay
unchanged; reference candidates never become Daniel entities.

Run: `GG_Data/pipeline/outputs/poc_10k_event_full_discovery_20261020`.
Outgoing coverage is complete: 4,712 records, 87,694 native item statements,
46,094 distinct reference targets. Incoming acquisition started; the exact
graph/QID requirement is 9,424 requests before cache reuse. Read `report.json`
for progress/first exception. This inventory still requires full acquisition,
Event hierarchy classification and the two-distinct-Daniel-QID gate. No Event
model rows are written. Tests: 50 passed before launch. Earlier results remain
immutable; no full-population completion is claimed.

## Previous: seven-candidate eligibility verified

The approved missing-record continuation completed at
`GG_Data/pipeline/outputs/poc_10k_event_seven_saved_fallback_20261020`.
`verification.json` has status `VERIFIED_SEVEN_CANDIDATE_ELIGIBILITY_ONLY`:
**4,712/4,712 Daniel QIDs checked**, comprising **4,705 current records and
7 approved saved native records** with original QIDs and explicit older
revisions/dates. `saved_fallback_audit.json` lists all seven; the original
current missing responses are preserved. No matching decisions changed.

Four candidates meet the approved two-distinct-Daniel-QID minimum:
World War II (363), Call of Duty: Advanced Warfare (7), Raid on Santorini (2)
and WikiProject Kerala (4). Minoan eruption, DTIS 2014 and the 2025 Santorini
earthquakes each connect to one and are below the minimum. The game and
WikiProject are retained by the approved broad-root rules; no new filter was
added. See the pipeline README for the full seven-row results and fallback list.

The check reconstructed 414 qualifying native assertions in both directions,
with all ranks retained (412 normal, 1 preferred, 1 deprecated), zero exact
exclusions and no mapping changes. All 109 source-response checksums and
14 accepted upstream output hashes passed; 48 pipeline tests passed. Zero
Event rows were written. This completes only the seven candidates from the
five-seed probe. Full 10K Event discovery, model Event/Relations population,
Geography and graph/Agent integration remain pending.

## Approved saved native records for missing current IDs

The user approved the saved-record fallback, preserving each original QID and
explicit older revision/date. Only an explicit current missing marker qualifies;
the accepted Entities manifest/file checksums must pass. No saved record or a
conflicting saved record still stops. Current missing responses remain intact.
Run: `outputs/poc_10k_event_seven_saved_fallback_20261020`. It reuses the cache
and checks the same seven candidates. Tests: 48 passed before launch. Final
coverage/eligibility is now verified as recorded above.

## Previous: missing current Wikidata record

The approved size split worked. The continuation stopped after **3,406/4,712**
Daniel native records when the next 50-ID response marked **Q31545924** missing.
The batch was rejected; no further requests, automatic ID change, rematching or
Event population followed. All seven candidate records remain checked; the
complete link gate is still pending, and zero Event rows were written.

The frozen input has one **Clark Airbase** LOC mention from **Manila** assigned
this QID. The accepted saved native record exists: revision **1021165461**,
modified **2019-09-27T16:40:15Z**. Current missing does not establish the cause.
All accepted upstream hashes passed. Evidence:
`outputs/poc_10k_event_seven_native_split_20261020/source_exception.json` and
`verification.json`. Proposed for consultation only: reuse saved native records
for current missing IDs with explicit older-revision/missing-current lineage;
preserve QIDs and stop if the saved record is absent. This was subsequently
approved as recorded above.

## Approved split of oversized native responses

The user approved halving only explicitly oversized API batches, repeating until
the complete requested population is present. A one-ID truncation still stops.
Original partial responses are preserved and never used as complete evidence;
successful children retain parent cache/checksum lineage. All other data/service
exceptions still stop under the agreed rule. Sources and data rules are unchanged.

The continuation is `outputs/poc_10k_event_seven_native_split_20261020`.
Read its report for progress and verification for final completion. The code
passed 47 tests before launch. Scope remains the same seven candidates against
all 4,712 frozen Daniel QIDs; full Event discovery/population is not claimed.

## Previous result: native batch stopped at API response-size limit

The user approved batched current Wikidata records instead of query-service
search. The implementation reuses successful native caches and requests up to
50 explicit IDs, full native records and no redirects. Tests: 46 passed.

`outputs/poc_10k_event_seven_native_batches_20261020` reused seven candidate
records and six of 4,712 Daniel records. The first new 50-ID request returned
42 records, with an explicit API result-truncation warning. The server reported
a 12,582,912-byte result limit; the received raw body is 28,842,454 bytes.
The requested/returned population guard stopped the run. The full response and
checksum are cached, but none of the partial batch was accepted. No retries,
smaller requests, Event rows or complete eligibility results followed.

Accepted upstream hashes remain unchanged. Evidence: `report.json`,
`acquisition_stop.json`, `verification.json`. Proposed for consultation only:
split a truncated batch into halves, retaining complete native records and
stopping if a single-ID request still exceeds the limit. No response-size
fallback was authorized at that stop. It was subsequently approved and implemented
as recorded above. Earlier query failures stay immutable.

## Previous result: bounded incoming request timed out

After discussion, the user agreed to 250-subject batches over the frozen
4,712 Daniel QIDs and all seven candidate targets. Both official query graphs
remain required (19 batches each; 38 requests total). The new run is
`outputs/poc_10k_event_seven_bounded_20261020`. Its final report/verification
establish completion; the earlier incomplete response and stop stay immutable.
The first bounded main-graph request timed out after 45 seconds, before any
incoming result completed. The pipeline stopped without retry or fallback.
All seven native records were reused; the earlier outgoing counts remain lower
bounds. No source, Event root, rank policy, type/date filter, or inclusion rule
changed. A batched native-record API approach was proposed for consultation:
up to 50 explicit Daniel QIDs per request, about 95 requests before cache reuse,
then direct statement checks locally. The user subsequently approved it; the
new API response-size stop is recorded above.

### Previous result: seven native records checked; incoming response incomplete

The user approved finishing the seven candidates under the current rules.
All seven native records and their saved P31 ancestry were checked. Outgoing
mapped statements connect World War II to 37 distinct Daniel QIDs, Minoan
eruption to 1, Call of Duty: Advanced Warfare to 7, Raid on Santorini to 2,
WikiProject Kerala to 0, DTIS 2014 to 1, and the 2025 Santorini earthquakes to 1.
These counts are lower bounds from outgoing statements only. Three already
prove the minimum; the other four remain pending rather than rejected.

The incoming World War II query returned HTTP 200 but incomplete JSON
(34,406,400 received bytes). The malformed-data guard stopped acquisition;
no partial query rows or automatic retry were accepted. No incoming query or
complete two-direction candidate check finished. Both main/scholarly graphs
remain required. The proposed recovery is 38 bounded requests, using batches of
up to 250 frozen Daniel QIDs and the seven candidate targets together, with
unchanged sources, rank handling and inclusion rules. The user selected
"Discuss first"; no bounded incoming query has been executed.

Evidence: `outputs/poc_10k_event_seven_eligibility_resumed_20261020`, especially
`outgoing_check.json`, `report.json`, and `verification.json`. All accepted
upstream output hashes passed. No Event rows, Event links in Relations, or
final graph were produced. This remains a seven-candidate check, not full 10K
discovery. See the pipeline README for exact candidate QIDs and cache recovery.

### Previous rank-rule approval and native inspection stop

On 20 October the user approved excluding deprecated P31/P279 statements for
Event classification only. The shared classifier applies this rule without
changing raw evidence, Relations ranks, or Daniel matching. Reclassification of
the saved 165 candidates retains the same seven diagnostic positives.

Native records were saved for World War II (Q362), Minoan eruption (Q1144693),
Call of Duty: Advanced Warfare (Q16743064), and Raid on Santorini (Q20981909).
The video game is an unexpected Event candidate: its native path uses normal
ranks throughout. Acquisition stopped when this was inspected. The fourth
record had already been saved by the running process. Three native candidate
records and the two-distinct-Daniel-QID checks remain pending. Evidence:
`outputs/poc_10k_event_seven_native_check_20261020`.

The user was asked whether to complete the seven link checks under the approved
rules or first discuss narrower scope. No extra type/date filter was applied.
No Event rows, Event relations, or final graph were produced. Accepted upstream
artifacts and the historical diagnostic outputs remain unchanged.

### Historical source probe and rank diagnostic

The approved 429 handling resumed successfully. The five-QID source probe
finished with 165 candidate P31 checks, 904 P279 class checks, 120 successful
hierarchy-stage requests and 132 verified source-body hashes. Upstream outputs
and old failed attempts are unchanged. No request is running.

The all-rank traversal marked 117 of 165 candidates as having Event ancestry.
This includes countries Q30, Q668 and Q41 through a deprecated P279 statement
on Q123349660 pointing to Q1190554. Event population stopped immediately.
Evidence: `outputs/poc_10k_current_event_rate_limit_retry_20261020/source_surprise.json`.

The user approved a diagnostic-only saved-data test excluding deprecated
P31/P279 links. The result is 7 positive candidates instead of 117, removing
110 flags including those three country examples. Evidence:
`outputs/poc_10k_event_rank_test_20261020/report.json`.
The rank rule was subsequently approved, as recorded above. Raw evidence and Relations
retain all ranks. No Event rows, new Daniel entities or final graph were created.
The two-Daniel-QID inclusion gate and full 10K discovery remain pending.

## Approved service-error handling — 20 October 2026

The user approved the general cache-first retrieval policy and the previously
proposed HTTP 429 handling. This supersedes the pending 429 decision in the
historical checkpoint below. Reuse verified saved data first; use agreed
BigQuery data where it supports the required scope, and approved current
Wikidata for Event data absent from that copy. No automatic source or business
rule substitution is introduced.

`events.cached_json` permits **three total attempts per exact request**, shared
across HTTP 429/502/503/504 and across restarts. Minimum backoff is 10 seconds
before attempt 2 and 30 seconds before attempt 3. Respect `Retry-After` seconds
from response receipt or an absolute HTTP date if later. A saved cooldown keeps
its original deadline. New network requests pause five seconds; retry waits
use short observable intervals. Original response bytes/metadata stay immutable;
new attempts append under the same request cache. Successful cache hits make
no network request. Exhaustion, timeouts, other HTTP/API errors, malformed data,
and data/business conflicts still stop with visible evidence.

The saved 429 response requested 120 seconds; that deadline had elapsed when
resuming. `event_hierarchy_probe.py` therefore reuses its original attempt 1 and
resumes attempt 2 under the approved policy. Current output:
`outputs/poc_10k_current_event_rate_limit_retry_20261020`. This remains the
five-QID source check, not a complete 10K Event population or final graph.


### Historical retry stop — superseded by 429 approval above

`outputs/poc_10k_current_event_hierarchy_retry_20261020/probe.json` reuses the
saved 58 successful hierarchy-stage requests and the original failed response.
Attempt 2 of the exact HTTP 502 query succeeded. The resumed run saved 35 more
successful requests, reaching 165 P31 candidate checks and 686 P279 class checks
(93 successful hierarchy-stage requests in total).

The next request returned HTTP 429 with `Retry-After: 120`. It was not retried:
the user approved only 502/503/504 retries. Status is `BLOCKED_HIERARCHY_PROBE`.
At that checkpoint the 429 wait/slower-request policy was not yet approved;
the user asked why BigQuery was not used. Acquisition stopped at that point.
The later approval and resumed run are recorded above.

The existing BigQuery snapshot returned zero rows for Q140451665 (saved job
`geoai_6d050ce4cff5a35c6380e995468a4bfe`); current table metadata was unchanged
at the saved check. This is why current Wikidata was approved for Events.
It does not establish that every BigQuery-hosted dataset lacks the hierarchy.
No newer BigQuery copy has been verified or substituted. Earlier pipeline
stages still use their agreed BigQuery records/caches.

`verification.json` verifies 105 source-body checksums, unchanged prior probe
files/failed attempt, and unchanged accepted Entities/Wiki Pages hashes.
No negative classifications, included Events, new Daniel entities or final graph
were produced from this partial hierarchy. Code validation: 34 pipeline tests,
Black and Ruff passed. Code/docs can be checkpointed locally; ignored outputs
and caches are not protected by Git.

**Current source decision, 20 October 2026:** the user approved current Wikidata
for Events and direct Daniel links, with retrieval caching. This supersedes the
pending-source statements in the historical checkpoints below. Keep Q140451665,
native P31/P279 and the two-distinct-Daniel-QID minimum unchanged. Preserve
per-request timestamps, revisions and raw responses; no atomic snapshot or
Event completion is claimed. Completed upstream outputs remain unchanged.

The approved current-source root check passed. The five-QID direct-link plus
hierarchy probe then reached a 45-second client read timeout and stopped,
without retry or Event population. The failed query/request is saved in
`outputs/poc_10k_current_event_probe_20261020` and the current Event cache.
This is a retrieval failure, not evidence of zero qualifying events. Proposed
next step for discussion: retrieve direct links in smaller requests, then check
the same hierarchy separately using cached native records. No rule/source change
has been applied and no Events release exists.

The user then approved the smaller requests. Implementation reads full native
outgoing records, incoming links one QID per request from both official query
graphs, and direct P31/P279 reference edges in batches of up to ten. Cycle-safe
local hierarchy traversal keeps all ranks and has no depth cutoff. No new
classifier, Event type, endpoint population or inclusion rule is introduced.
The five-QID source probe is separate from completion of the full 10K POC.

The smaller-request probe saved 53 outgoing and 146 main-graph incoming links,
with no additional scholarly incoming links, for 165 distinct reference
candidates. It then saved all 165 P31 checks and 344 P279 class checks before
Wikidata returned HTTP 502. Acquisition stopped without retries, status
`BLOCKED_HIERARCHY_PROBE`; raw requests/responses and partial hierarchy remain
cached in `outputs/poc_10k_current_event_hierarchy_probe_20261020` and the current
Event cache. This is a source-service failure, not a zero-Event result. No Event
model rows were added. The user then approved three total attempts for HTTP 502/503/504 only,
with waits of 10 and 30 seconds. `events.py` implements this persistent budget:
old failed responses count as attempts and remain immutable; successful cache
entries are reused. Timeouts, 429, API/data errors and business exceptions still
stop immediately. `event_hierarchy_probe.py` resumes into a new output directory;
no source, hierarchy, matching or Event-inclusion rule changes.

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
- Relations contains selected Daniel-QID/Daniel-QID assertions, uncapped included-event/Daniel links and uncapped direct included-event/included-event assertions. Non-event assertions use the approved mutual-top-20 rule above. No new endpoint entities or seventh participant table.
- Apply exact approved exclusions and the pinned current mapping version (v2.1.1 for the native P2341 addition). Reverse views share base evidence; genuinely separate source statements remain separate.
- Geography uses approved sources and policy. Older OSM snapshot age is accepted; historical identity/meaning checks remain.
- Geometry is Shapely, persisted as WKB; graph JSON references the stored object. No inline GeoJSON conversion.
- Omit node/edge sources and node text from the graph for now. Preserve source provenance in the model/supporting artifacts; omit page/mention/paragraph graph nodes.
- Do not invent event categories, levels, preferred dates, participant roles, Event importance scores, embeddings or geometry. The approved Daniel page-count times mention-count score is solely a non-event relation-selection measure.

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

Latest user correction: retain the 34 pre-1900-end statements with original dates. Policy v1.1.0 removes that date-only exclusion and bypasses the start-year floor for these historical relations. Earlier 10,467-row/34-exclusion outputs remain immutable history and are superseded for current use. New replay: `outputs/poc_10k_relations_original_historical_dates_20261020` (require its manifest). Events remain blocked; no alternate root or source is approved.

That corrected replay is verified: `DANIEL_RELATIONS_ONLY`, 10,501 base statements, all 34 historical statements restored with exact original date values and raw qualifiers, zero exclusions in this sample and 120 temporal audit rows. Original eligible population accounting and all manifest hashes passed; the previous 10,467 statements are unchanged except policy metadata. The 28 focused tests and Ruff passed. This corrects Relations only; the event-root source question remains pending.
