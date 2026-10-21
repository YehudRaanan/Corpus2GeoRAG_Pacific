# Source-to-target: approved sources to the six-table data model

Specification date: 19 October 2026. Status: approved source scope and rules documented; required implementation exceptions remain explicit. This document does not execute acquisition, matching, table population, geocoding, or graph export.

**Target:** [Entities, Mentions, Wiki Pages, Geography, Events, Relations](ENTITY_DATA_MODEL_ERD.md). This is the population S2T. The separate [model-to-Agent graph JSON S2T](ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md) starts after these tables. The ERD dictionaries and exact contract inventories form part of this specification; every input field and nested evidence payload must remain recoverable.

The [full pipeline review](DANIEL_TO_GRAPH_PIPELINE_REVIEW.md) collects open decisions, implementation checks, documentation alignment and deferred improvements from Daniel input through final JSON. It does not change these population rules.

## Current stop — direct BigQuery root-edge query, 21 October 2026

At the user's request, the native P279 query ran directly in
`bigquery-public-data.wikipedia.wikidata`, using the agreed source snapshot
`2026-10-18T18:45:19.304197+00:00`. No Wikidata dump or full records were
downloaded. The query returned only native child/parent QIDs, statement IDs and
ranks whose parent is the approved Event root Q140451665. It preserved all ranks;
normal/preferred would be required for classification. This checks incoming root
references directly; absence of the root item alone was not treated as proof.

**Verified cloud result:** 90,722,347 source records scanned, **zero P279 links**
to Q140451665 at any rank. BigQuery execution took **11.986 seconds**;
client execution, including CLI dry-run/result verification, took **37.1015
seconds**. Bytes processed: 1,561,204,455,825; bytes billed: 1,561,204,883,456,
within the existing 2 TiB cap. The result table's complete row count was verified.
Job: `geoai_212ecea6bc0d93fcc59f8c40219a0485` (US).

The cloud query succeeded, but this table cannot supply a nontrivial hierarchy
below the approved root. No root-only parameter table was published, no candidate
was rejected, and the 2,680-candidate filter did not start. This result concerns
this source snapshot, not the existence of Events in Wikidata. Retrieval stopped
under the POC consultation rule; changing the root or source needs agreement.

Evidence: `GG_Data/pipeline/outputs/event_hierarchy_bigquery_root_edges_20261021/`
contains the SQL, dry run, table metadata, empty result, source/job statistics,
measured report and verification. The existing BigQuery query cache also retains
the SQL and complete result/receipt. Outputs are ignored and local only.

## Historical stop — root-scoped Event hierarchy query, 21 October 2026

The user approved limiting acquisition to Q140451665 and its native subclass
hierarchy, for reuse with wider Pacific War inputs. The tested
`event_hierarchy_parameters.event_scope_query()` uses native
`(^ps:P279/^p:P279)*` traversal from that root and returns only child/parent
QIDs, the P279 property, statement IDs and ranks. It has no global sort, COUNT,
LIMIT, labels or Event-instance population. All returned ranks would remain
evidence; only the existing local normal/preferred closure could accept types.
The traversal's unfiltered paths are a retrieval superset, not permission to
accept deprecated ancestry. A result from one service alone would not prove
cross-service completeness.

**Verified result:** the first main-service request reached its 45-second read
timeout. Total wall time was **50.4147 seconds**, including the approved
five-second request pause. There was one attempt; read timeouts are not covered
by the existing retry allowance. No hierarchy rows were accepted, the scholarly
service was not queried, no usable parameter tables were produced and the Event
filter did not start. The probe ended with exit code 1. No acquisition workaround
was started after this stop; the user's POC consultation rule applies.

Query, code/commit hashes, source request receipt and measured result:
`GG_Data/pipeline/outputs/event_hierarchy_scope_probe_20261021/`.
The source receipt is retained in the existing bulk cache. Twelve focused tests,
Black and focused Ruff passed before the probe. The previous ordered-export
failure below remains historical evidence, not a running worker.

## Historical stop — Event hierarchy parameter tables and timed filter

The user approved a P279-only bulk export, followed by another run of the Event
filter with measured runtime. `event_hierarchy_parameters.py` exports native
P279 statements in ordered 1,000-statement pages from both current Wikidata
query services. It saves every response, cursor and source receipt through the
existing cache/retry policy. The failed global COUNT is not repeated. A short
terminal page from **both** services is required; a failed request or partial
export cannot establish a negative classification. This is a live retrieval
window with timestamps, not an atomic dated dump snapshot.

Outputs are versioned under
`GG_Data/pipeline/outputs/event_hierarchy_parameters_20261020/`:

| Parameter/evidence object | Columns and use |
|---|---|
| `hierarchy.sqlite`, `hierarchy_edges` | Native statement key, child QID, parent QID, rank, original statement ID, source service and retrieval timestamp. All ranks remain evidence, including deprecated. Incomplete exports are not usable Event parameters. |
| `event_hierarchy_mapping.csv` | `root_qid`, `child_type_qid`, `parent_type_qid`, `source_statement_id`, `statement_rank`, `source_service`, `retrieved_at_utc`. Only normal/preferred links within the complete Event-root closure. |
| `event_types.csv` | `root_qid`, `subtype_qid`. Includes Q140451665 itself and its complete non-deprecated subclass closure; no internal Event levels or categories. |
| `report.json` | Parameter version, retrieval window, per-page evidence/timing, completed services, code/output hashes, `parameter_table_usable` and hierarchy elapsed seconds. Usability requires complete successful retrieval and closure checks. |

Only after usable parameters exist, the controller reruns the unchanged
2,680-candidate sample from 48 retained Daniel QIDs. It replays the verified
candidate restriction, reuses accepted complete P31 answers and retrieves only
missing P31 evidence with the existing adapter. Non-deprecated P31 values are
tested against the saved subtype table; no repeated ancestor requests occur.
`filter/report.json` and `filter/classifications.jsonl` record decisions, source
receipts and filter elapsed seconds separately from hierarchy acquisition.
The 15 unknown-score sample endpoints remain held; no full-10K unknown policy
is inferred. This hierarchy filter does not populate Events: native assertion
mapping/exclusions and the two-distinct-Daniel-QID gate still apply.

Before the paged export: **11 focused tests**, Black and focused Ruff passed.
Read the run report for live or terminal state; no success is inferred from
this launch description. **Verified terminal result:** the first ordered page
failed after the approved three attempts (HTTP 502, HTTP 502, read timeout).
Elapsed wall time was **145.4167 seconds** including pauses/retry waits. Zero
hierarchy pages/rows were accepted; `parameter_table_usable=false` and
`filter_started=false`. The SQLite schema exists but is empty; no usable CSV
parameters or filter runtime exist. `verification.json` checks source attempt
receipts, code/output hashes, empty database integrity and the absent filter.
The worker has ended. Further acquisition changes require consultation.
The unordered 1,000-row transport probe succeeded in
about seven seconds, but the subsequent global COUNT timed out after 45 seconds.
Those earlier responses remain in `outputs/event_hierarchy_bulk_probe_20261020`
and `outputs/wikidata_event_hierarchy_bulk_cache`; they are not complete coverage.
The full-dump checksum request had returned HTTP 403 before any dump transfer.

## Historical continuation — checking all filtered sample candidates

The user approved completing all **2,680 preliminary candidates** from the
unchanged 100-mention sample. `event_on_demand.py --filtered-sample` verifies
the saved restriction and replays its complete candidate inventory before
classification. It reuses complete accepted P31/P279 answers and the existing
request cache; missing hierarchy evidence follows the already-approved current
Wikidata rules, deprecated-link exclusion and persistent retry limits. There
is no 165/200-item cap and no new Daniel seed or matching assignment.

Progress and per-candidate decisions are saved under
`GG_Data/pipeline/outputs/poc_10k_event_filtered_all_candidates_20261020/`.
That worker was deliberately stopped at 90/2,680 candidates for the approved
bulk hierarchy switch. Its cache, decisions and stop receipt are preserved;
it is not running and its partial classifications are not a complete filter.
This is the 48-retained-QID sample, not full 10K Event discovery. The 15
unknown-score seeds remain held separately as in the approved bounded test.
Classification alone does not populate Events: positive candidates still need
snapshot native assertions, mapping/exclusions and two distinct retained
Daniel endpoints. No Event table or final graph is declared complete by a
running classification report. Before launch: 20 focused tests, Black and
focused Ruff passed. Read `report.json` for current or terminal status.

## Previous verified result — maximum language score and bounded Event test

The approved maximum-language rule in section 6.1 was applied to all **1,312**
resolved MISC QIDs in the frozen 10K model: **66 pass**, **627 are below 5%**,
and **619 have no score in either language**. Both language scores are retained;
the highest available fraction supplies the decision, with exactly 5% passing.
All original QIDs and model rows remain unchanged. Exact fractions, input/output
hashes, complete CSV coverage and the original population were verified.
Evidence: `GG_Data/pipeline/outputs/poc_10k_scope_concentration_maximum_language_5pct_20261020/`.

The earlier random 100-mention Event sample was reused without replacements or
added controls. Its 71 matched QIDs give **48 usable endpoints**, **8 below the
threshold**, and **15 unknown endpoints held outside this bounded test**. This
hold is not a full-run exclusion decision. The unchanged complete cached native
links yield **2,680 preliminary candidates**, down from 15,550; restricting the
previous candidate endpoint inventory independently gives the same set. No new
discovery scan was needed.

The existing Daniel-first query was tested for those 48 endpoints against the
**165 candidates with previously accepted hierarchy evidence**. **World War
II/Q362** qualified through **5 distinct Daniel entities**, with **6 native
assertions**. The returned assertion identities match the complete cached
native records after the approved mapping/exclusions. Snapshot query execution
was **2.790 seconds**, with **84,299,218,944 billed bytes**. Fifteen focused
tests, Black and focused Ruff passed. Query, source result, decisions, candidate
restriction and hash verification are saved under
`GG_Data/pipeline/outputs/poc_10k_event_filtered_sample_query_20261020/`.

This verifies a bounded query, not all 2,680 classifications or complete 10K
Event discovery. No model Event rows, final graph, new Daniel entities or
matching changes were written by that test. The subsequent all-candidate
sample continuation is recorded above. Unknown-score handling beyond the bounded
test still requires consultation; unknowns were not changed to zero or rejected.

## Historical stop for analysis — larger Event timing sample, 20 October 2026

The timing experiment used 100 frozen Daniel mentions (seed 20261020), containing 71 distinct matched QIDs, and discovered 15,550 preliminary candidates. The user stopped it at **14:04:37 Jerusalem, 20 October 2026**, after **660.701 seconds**: **69/200** sampled candidates classified, **67 negative**, **2 hierarchy-positive**, **98 successful source-answer receipts**. Link qualification had not started. No Event rows or graph were written; both this worker and the original full run are stopped. BigQuery discovery took 76.008 seconds and is cached. Evidence: `GG_Data/pipeline/outputs/poc_10k_event_timing_100_mentions_200_candidates_20261020/stop_analysis.json`; the worker report before the stop annotation is preserved.

The saved upstream identity assignments need review: “Japanese” in “Japanese military” resolves to Japanese language/Q5287, and “Brazilian” in “Brazilian Navy” resolves to Brazilian Portuguese/Q750553. Exactly this pair accounts for **12,316 candidates (79.2%)**. Event retrieval performs no name matching; it reuses these frozen IDs. No assignment, threshold, source, or population rule was changed. All 69 completed classifications were replayed offline and 98 source-response hashes verified. Serial hierarchy requests and a 120-second HTTP 429 cooldown make timing variable; this interrupted sample does not establish a reliable full-run ETA. Analysis made no new source requests.

The benchmark's rank-URL adapter was corrected to apply the already-approved exclusion of deprecated ancestry. The raw cache and source/rule selections remain unchanged. Invalid interrupted benchmark classifications were not imported and are retained as failed-test evidence. Regression checks: 32 tests passed, with Black and focused Ruff.

## Previous result — small Daniel-first query test, 20 October 2026

The bounded `event_sample_query.py` test used five random Daniel QIDs (seed 20261020), two separate positive controls already in Daniel, and the accepted 165-candidate hierarchy probe. The agreed BigQuery snapshot supplied assertions. The query returned only World War II/Q362: five native assertions connecting two distinct Daniel QIDs, Hitler/Q352 and Roosevelt/Q8007. Both native directions were covered; mapping/exclusions were checked and assertion identities matched the complete cached records exactly. Repeated links did not increase the distinct-entity count. Evidence: `GG_Data/pipeline/outputs/poc_10k_event_sample_query_20261020`. All input/output checksums passed. Query execution: 1.975 seconds; billed bytes: 68,943,872,000.

This validates a bounded join and qualification test against previously classified candidates, not complete Event discovery. No model Event or final graph was written. The preceding worker is stopped after a read timeout at 17/2,218,368 classified candidates, 568 source answers and 282 fetched classes. Its launch evidence below is historical; no full run was restarted. Source and inclusion rules are unchanged.

## Historical run — candidate-only classification, approved 20 October 2026

The user stopped the full-hierarchy approach and approved checking only our candidates, fetching class paths when needed and caching answers. The full P279 catalog process and its queued global-instance controller are stopped. Their accepted cache remains intact. The terminal catalog status is `STOPPED_FOR_USER_APPROVED_ON_DEMAND_SWITCH` (13,990 classes found, 1,599 fully checked); these are reference classes, not included Events. The switch receipt is `outputs/poc_10k_event_on_demand_switch_20261020.json`. This supersedes the historical full-catalog continuation below.

`event_on_demand.py` reuses the verified snapshot candidate universe: **2,218,368 distinct IDs** after unioning the 2,209,613 incoming candidates with the 44,714 outgoing reference QIDs. The input is unchanged; overlap is counted once. It reads current native P31 in batches of up to ten IDs across both official query services. Only a class needed by a candidate triggers an upward P279 lookup. Complete class answers are reused across candidates; saved non-deprecated root paths from the stopped catalog can prove positives without new class requests. Missing paths in that partial catalog never prove negatives. Cycles terminate, deprecated links are retained as evidence but ignored for Event classification, and no depth cutoff is used. An item absent from both query services requires the already-approved current native-record check; source failure or missing native data stops the run rather than becoming a negative classification.

Current run: `outputs/poc_10k_event_on_demand_connection_retry_20261020/report.json`. The user approved extending the existing persistent three-attempt budget to connection failures, with waits of 10/30 seconds. The saved failed request remains attempt 1; its original metadata are unchanged. An append-only checksum-bound annotation identifies this pre-policy connection failure. The new worker (PID 23932) was launched independently of the interactive shell, passed frozen-input verification and reached `CLASSIFYING_CANDIDATES_ON_DEMAND`. The failed exact request succeeded on attempt 2; the response checksum passed. At the launch check it had 51 valid source answers, 24 class nodes and 0 completed candidate classifications. Live counts are in the run report; launch evidence is `outputs/poc_10k_event_on_demand_connection_retry_launch_20261020.json`. Prior output remains stopped at 45 valid source answers, 21 class nodes and zero completed candidates. Approval and executed-code checksums are in `outputs/poc_10k_event_on_demand_connection_retry_approval_20261020.json`. No Event rows or final graph have been written. Successful response caches and all prior stopped outputs remain intact. In this method, complete source receipts and candidate decisions are appended to separate JSONL files, with needed class answers checkpointed locally. Request caching and the POC stop rule remain unchanged; only the approved connection-failure retry extension is added. No global subclass or instance enumeration is running. This method has no verified full-population speed advantage; it avoids the unneeded global hierarchy preparation. It creates classification evidence only, not new Daniel entities or model Event rows. Positive candidates still require snapshot-first assertion records and the approved two-distinct-Daniel-QID gate before Event inclusion. No full-record worker or model-population controller is started by this classifier. Checks before launch: **74 pipeline tests passed**, Black and focused Ruff passed.

## Historical full-catalog run — stopped, 20 October 2026

The user approved continuing beyond the 165-item test. `event_candidate_ids.py` changes only the verified measurement SQL's final projection: it retrieves native candidate IDs, without downloading their full records. The completed file contains exactly **2,209,613 distinct QIDs**, uses **5,588,999 compressed bytes**, and passed count, source snapshot, unchanged-filter, code and output checksum checks. Verification: `outputs/poc_10k_event_candidate_ids_20261020/verification.json`, status `VERIFIED_SNAPSHOT_CANDIDATE_IDS_ONLY`. Query `geoai_8c8ff2e40a166a4eeb2a4e5365f215c5` billed 1,561,930,498,048 bytes; SQL, result and job evidence remain in `outputs/wikidata_event_snapshot_discovery_cache`. This is an ID inventory, not 2.21 million Events.

`event_class_catalog.py` previously ran against both current Wikidata query services; it is now stopped. It walks native P279 statements backwards from Q140451665, retaining raw evidence of every rank but expanding only through non-deprecated statements. It follows paths across the two services, without a depth or class-count cutoff. Each batch requires every ordered 5,000-statement page, its short terminal page and both services before it is complete. It reuses the existing request cache and approved limited retries; other source/data errors stop. Live status: `outputs/poc_10k_current_event_class_catalog_20261020/report.json`. Classes are reference classification data, not new Daniel entities or included Events.

After the class catalog completes, `event_instance_candidates.py` reads current native P31 statements to those classes on both services, with the same page and rank rules. It intersects current instance IDs with the verified incoming candidate inventory **and** the 44,714 outgoing reference QIDs reconstructed from the unchanged Daniel snapshot records. Omitting that outgoing-only inventory would miss eligible direct links in the other direction. Only relevant positive class evidence is copied to its output; untouched complete pages remain cached. No negative classification is inferred from a partial page chain or an incomplete query-service index.

The full-catalog continuation controller was stopped before its global instance-classification stage began. Its terminal state is `SUPERSEDED_BY_USER_APPROVED_ON_DEMAND_CLASSIFICATION` in `outputs/poc_10k_event_classification_continuation_20261020.json`. No global instance worker was started. The candidate-only continuation above is the current run.

This changes acquisition order only. Latest hierarchy data supplies classification; full assertion records still use the agreed snapshot first and the approved same-QID missing-input fallback. Positive classification alone does not include an Event. Full records, exact mapping/exclusions and the union of direct links to at least two distinct original matched Daniel QIDs are still required. No Event rows, capped Relations or graph JSON have been written by these stages. The full pipeline is not complete. Code checks before continuation: **69 pipeline tests passed**, with Black and focused Ruff checks.

## Source rule for every Daniel data version — snapshot first

For each new Daniel input version, create and retain a separate reference snapshot at the data datetime selected for that version's initial entity/reference retrieval. Record its input version/hash, matching run ID, table/version and exact UTC snapshot datetime together. Read `reference_manifest.table_snapshot.snapshot_at` for downstream retrieval; never hardcode one datetime for future versions. A timestamp alone is not retained data: persistent snapshot creation/retention remains an implementation requirement.

**Latest user approval, 20 October 2026:** use the agreed Wikidata snapshot directly. Do not compare archived versions, create version-difference reports, or stop merely because labels, classes or statements differ between versions. This supersedes the earlier per-case class approvals, newer-label ranking, older-English exceptions and snapshot-only fallback prohibition. Keep the saved matched QIDs, broad entity types, mention assignments and importance scores. Use English, then Japanese, then the existing Daniel-name fallback from the selected source record.

When needed entity input is unavailable in that snapshot, use the latest available complete Wikidata record for the same QID. Among validated available versions, choose the highest item revision; do not change the QID or invent an entity. Keep the selected record's ordinary source/revision/timestamp metadata, without an archived-versus-snapshot comparison log. Reference-only items, including the approved Event root/hierarchy, follow the same source priority and never expand Daniel's entity population. A snapshot lookup miss does not mean the entity is absent from current Wikidata. A service failure or unqueried QID does not establish a snapshot miss; existing source-error and integrity checks still apply. If neither source provides the required input, stop and show the case.

Current-version lineage only: `bigquery-public-data.wikipedia.wikidata` at `2026-10-18T18:45:19.304197+00:00`, with Wikipedia dump `20261001`. The Event root Q140451665 was absent from this snapshot; the latest-available-record fallback is now allowed, but Event discovery/classification is not complete. The existing Event hierarchy, two-distinct-Daniel-entity gate and relation cap rules remain unchanged. Earlier missing-reference audits and source-stop outputs are historical, not active version-comparison requirements. No rematching, source-page re-extraction, geometry policy change, new Event root or new classification is authorized.

Current Entities output: `GG_Data/pipeline/outputs/poc_10k_entities_snapshot_first_20261020`, status `ENTITIES_SNAPSHOT_FIRST`. All 6,077 typed Entity rows remain, covering 4,712 QIDs and 1,356 unchanged synthetic identities. All 4,712 full QID records come from the agreed snapshot, including the 506 cached replacements; zero fallbacks were needed and no new query ran. IDs, broad types, saved matching evidence and importance remain unchanged. No new version-difference report is written. Events, the Relations rebuild/selection, Geography, graph JSON and Agent integration remain pending.

## 1. Approved sources and saved inputs

| Source / artifact | Approved use | Boundary |
|---|---|---|
| Daniel input, `Data/external/daniel_20261017.parquet` | Original mention population and unchanged extraction fields. | No new mentions, splitting, combining, or independent text extraction. |
| Completed matching run, `C:\Users\User\.cache\geoai_full_daniel_dump_bigquery_parallel_20261019` | Reuse assignments, attempts, dates, type decisions, page lookups, reference evidence and manifests. | Population does not rerun or revise matching. |
| Saved Wikidata references; approved BigQuery table `bigquery-public-data.wikipedia.wikidata` | Labels, aliases, native types/hierarchy, full statements, events and provenance for relevant QIDs. Reuse saved results before retrieving missing data. | Compact matching metadata is not a complete assertion/date store. Full `item` JSON or full saved entity records are needed for claims, ranks, qualifiers and references. |
| Historical live Wikidata native JSON and official query-service results | Preserve evidence from earlier approved Event retrieval attempts. | Use only when the required same-QID record is unavailable in the agreed snapshot, under the latest snapshot-first/last-available fallback rule above. Retain ordinary source lineage. |
| Official English/Japanese Wikimedia dumps and saved page resolution | Article page IDs, redirects, subject QIDs, sitelinks and page/link evidence. | Dump links may include templates/navigation. They are not proof of a particular Daniel extraction revision or all entities in prose. |
| Versioned relation catalogs and exact assertion exclusions | Current catalog: relation-map-v2.1.1; preserve v2.1 direction/time rules and the 14 exclusions. | Missing native Wikidata source keys follow the approved rule in section 8. No other fact source or semantic translation is authorized. |
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
3. Populate Entities for distinct `(assigned QID/SYN ID, resolved type)` combinations. Multiple types for one QID coexist. Successfully normalized dates stay structured in Mentions, with null entity FK.
   Before new relation retrieval, populate Entities.importance from the declared Daniel Mentions population and retain its page/mention factors and input checksum in attributes.importance_basis.
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
| `entity_type` | Saved `type_metadata.resolved_type`, paired with `entity_id` as the Entities foreign key. For synthetic rows whose saved resolved type is null, use Daniel's original `entity_group` (explicitly approved 19 October 2026); retain the original null in saved metadata. Null when `entity_id` is null. No new type inference. |
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
| `entity_id` | Saved QID/SYN assignment or included event QID, unchanged. Entities is unique on `(entity_id, type)`, not QID alone. Candidate/hierarchy QIDs used only as reference evidence do not become entity rows. |
| `name` | First available Wikidata English label, then Japanese label, then Daniel's original name. A synthetic row uses its own mention's original name. Record the chosen source/language and fallback evidence in `attributes`/raw provenance. |
| `type` | Reuse saved matching `resolved_type`; for synthetic identities with null resolved type, retain Daniel's original `entity_group` under the approved fallback. Each distinct `(entity_id, type)` is a separate entity, including LOC and ORG for the same QID. No canonical entity/winner. Preserve original type and override evidence. Included event role comes from Events membership, never Daniel MISC. |
| `labels`, `descriptions`, `sitelinks` | All available original language-keyed Wikidata values, including English/Japanese; do not translate or synthesize. |
| `aliases`, `alias_details` | Supplied labels/aliases and original mention forms with their actual provider, record ID, kind and known language. No generated nicknames, romanization or combined names. |
| `identity_status`, `review_status` | Distinguish saved QID assignment from synthetic unresolved identity and actual review evidence. An automatic match is not a manual verification. |
| `importance` | User-approved Daniel-population measure: distinct original `raw.Source` pages times original mention count, grouped by assigned QID or existing synthetic ID. Copy the QID value onto every existing type row without adding mentions or entities. Each separate per-mention synthetic identity scores 1 (one page times one mention), including synthetic DATE errors; successful normalized dates have no Entity row. Events.importance remains governed by its separate native-source rule. |
| `attributes.importance_basis` | Policy, frozen Mentions SHA-256, distinct source-page count, total mention count and `SCORED` status for QID and synthetic rows alike. Unresolved identity status does not prevent calculating this input-based score. Full original source-page lists remain in the supporting score artifact. |
| `direct_types`, `parents` | Saved P31/P279 evidence, retaining its version/provenance. Hierarchy traversal does not imply an entity population expansion. |
| `revision`, `modified`, `missing`, `reference_source` | Saved reference version/state/provider; `missing` means retrieval missing, not proof of Wikidata absence. |
| `sources`, `raw_reference` | Complete original metadata/entity envelope or immutable artifact reference, including requested QID, full claims, ranks, qualifiers, references and unknown fields. |
| `attributes` | Only supplied values/evidence: kind/country/scale, P879 hull numbers, P729/P730 commissioning/decommissioning dates, and other already-supplied attributes. No new inferred values. |
| `text`, `embedding` | Optional existing fields only; current population adds no paragraph-derived text or embedding generation. |

The approved name order supersedes a simple copy of the compact metadata's selected `label`. If English and Japanese labels are absent and one QID has different Daniel names, show the exact names/QID before choosing a canonical fallback. An event without an English/Japanese label and without a Daniel mention has no approved final fallback. Do not invent a QID-as-name or select a first/most-frequent name silently.

**Display-name source decision, 20 October 2026 (latest approval):** use the selected snapshot record directly, with English then Japanese then the existing Daniel-name fallback. Use the latest available complete same-QID record only when the needed snapshot record is unavailable. This replaces newer-label ranking and per-case older-English exceptions. No archived-versus-snapshot name/class difference report is required. Saved IDs, matching decisions and broad types stay unchanged. Ambiguous Daniel fallback names or no available source record still require consultation.

**POC naming decision, approved 20 October 2026:** retain the older English labels for Q132537 (`Robert Oppenheimer`, revision 2380462137; newer full revision 2555601950 has Japanese `ロバート・オッペンハイマー` and no English) and Q1771928 (`Why We Fight`, revision 2286990634; newer full revision 2506639226 has Japanese `我々はなぜ戦うのか` and no English). Record this approval in each affected row's `attributes.name_selection`; retain both raw versions. This closes the reported language/version hold for these two pinned cases. Other cases in which a newer record lacks a label supplied by an older record still require discussion. The first attempt remains `DRAFT_NOT_ACCEPTED`, with its historical blocked manifest retained. Rerun into a new output directory using the complete saved cache; no new query is needed. No ID, type or matching decision changes.

### 6.1 Scope-concentration measure: approved purpose and synthetic exclusion

**User decision, 20 October 2026:** use this measure to identify broad or
unrelated MISC entities before Event retrieval, using their concentration in
Daniel's WWII/Pacific page scope. It does not require a constructed graph and
does not measure historical importance. The user subsequently approved a
**provisional 5% threshold**: exclude measured MISC QIDs with score **<0.05**
from Event retrieval and keep scores **>=0.05**, including exactly 5%.
Synthetic IDs remain excluded. Missing global denominators remain unknown and
must not silently become zero scores or exclusion decisions. **Language
clarification, 20 October:** calculate English and Japanese independently,
using the same formula and 5% threshold in each. Key scores and decisions by
`(wiki, QID)`; never pool languages or reuse page IDs/counts across them.
A missing article in one language does not block calculation in the other.
Use the full saved Daniel source-page scope for that language, including
retrieved Japanese counterparts. An unavailable language score has no filter
decision; it is not a failed 5% test. **Combined-language rule, approved
20 October 2026:** use the highest available percentage across English and
Japanese as the QID-level Event retrieval score. Keep the QID when this maximum
is >=0.05; exclude it from Event retrieval when the maximum is <0.05. If only
one language has a score, use that score. If neither has a score, the combined
score and decision remain unknown and require consultation. Do not treat a
missing score as zero or pool language counts. Preserve both language scores
as supporting evidence. This decision is closed and implemented; the verified
combined 10K result and bounded Event test are recorded at the top of this S2T.
Preserve all
original model rows and matching assignments. This threshold does not change
the matching similarity threshold, Event hierarchy or two-entity inclusion rule.

For each eligible matched Wikidata QID:

**Scope concentration = distinct Wikipedia source pages linking to the QID
within Daniel's full source-page scope / all distinct Wikipedia source pages
linking to that QID.**

Daniel supplies the source-page scope from the full input version, not the
mention-to-QID assignments used in the earlier, superseded numerator. Count
actual Wikipedia links once per `(QID, source page ID)`, across target aliases
and redirects. Use the same language, Wikipedia snapshot and namespace rules
for both counts. The saved resolver includes template/navigation links.
**Redirect clarification, 20 October:** count a redirect and its destination
as **one final page**, independently in each language. Union incoming links
to that page and all its redirect aliases; count each source page once.
If the final page carries a different QID, use that page for both counts and
record its page ID, title and QID as measurement metadata. Preserve the
original entity QID and its separate model row; this is not a new match.
Several selected QIDs may share one measurement page without duplicating
the underlying page counts. Keep the stopped Japanese attempt unchanged and
write the approved continuation to a new output directory.
Bind the measure to the input version/hash and page snapshot manifest; do not
hardcode this run's snapshot date for later Daniel versions.

**Synthetic IDs are excluded from this measure.** A Daniel source-page
relationship alone does not supply a matched QID or a global linking-page
denominator. Do not add synthetic page counts to QID numerators, create QIDs,
merge unresolved mentions, or delete their existing model records. Their
original Daniel page relationships remain preserved. This exclusion does not
change the separate `Entities.importance` rule above or its synthetic score of
1; scope concentration is not the top-20 relation importance measure.

The existing supporting diagnostic report/CSV supplies these fields; no new
business table or populated model column is claimed by this specification:

| Supporting field | Source and calculation |
|---|---|
| `qid`, `name` | Selected existing matched QID and saved diagnostic display name; no new matching or identity creation. |
| `measurement_page_id`, `measurement_page_title`, `measurement_page_qid`, `redirect_depth` | Final namespace-0 page after redirects and its optional QID; measurement evidence only. The original `qid` stays unchanged. Both counts use this single page and its aliases. |
| `wiki`, `score_status`, `keep_for_event_retrieval` | Separate English/Japanese measurements. A known positive denominator permits the 5% decision; no snapshot article or no incoming links leaves counts, score and decision null, with an explicit unavailable status. |
| `scope_linking_pages` | Cardinality of the intersection of actual linking-page IDs and the distinct resolved page IDs in Daniel's full source-page scope. |
| `all_linking_pages` | All distinct source article page IDs linking to the QID under the same snapshot/language/redirect rules. |
| `scope_page_ids` | Exact deduplicated page IDs supporting the numerator, retained in the report. |
| `relevance` | `scope_linking_pages / all_linking_pages` when the global denominator is known and positive. An unavailable denominator is unknown, not zero. |
| Snapshot, coverage and hashes | Full Daniel source-title scope, missing titles, distinct resolved page count, dump date, language, link rules, input/output hashes and dump-verification receipts. |

**Verified diagnostic:** the 19 selected English QIDs use snapshot `20261001`
for both counts. Daniel's 428 source titles resolve to 424 titles and 413
distinct article page IDs; four titles remain missing. Twelve QIDs have
positive observed scope counts and seven have zero. Zero means no link in
the checked pages, not proven absence from the four missing pages. Missing
source pages remain explicit incomplete coverage. The 19-QID test does not
establish full-population measurement.

**Provisional 5% test:** apply the approved threshold to those same 19 scored
QIDs using [scope_concentration_filter.py](../GG_Data/pipeline/scope_concentration_filter.py).
Keep two: Battle of Kiev (1941)/Q162284 (7.9612%) and Continuation War/Q122100
(5.1468%). Seventeen fall below 5%, including World War II/Q362 (0.1408%).
No exception is added for a low-scoring relevant subject. Decisions use full
counts without rounding; original scores remain unchanged. The bounded test
records all keep/exclude decisions in
`GG_Data/pipeline/outputs/poc_10k_scope_concentration_5pct_20261020/selection.csv`
and `report.json`. This is a 19-QID test, not a completed filter of the full
10K population; it makes no new request and does not restart Event acquisition.

Historical 19-QID evidence:
`GG_Data/pipeline/outputs/poc_10k_misc_snapshot_link_relevance_20261020/report.json`
and `scores.csv`; implementation:
[snapshot_link_relevance_probe.py](../GG_Data/pipeline/snapshot_link_relevance_probe.py).
The later 153-row synthetic extension under
`outputs/missing_pages_synthetic_numerators_20261020/` is superseded historical
evidence only; its code was removed. No original matching decision, model row,
Event rule or relation-importance score was changed.

**Verified frozen-10K population measurements, 20 October:** both language
runs now cover the same **1,312** existing resolved MISC QIDs independently.
English: **670 scored**, comprising **41 >=5%** and **629 <5%**; **642 unknown**
(639 without a snapshot article, three without incoming links). Japanese:
**391 scored**, comprising **45 >=5%** and **346 <5%**; **921 unknown**
(920 without a snapshot article, one without incoming links). Scoped page
counts are 413 English and 296 Japanese. The four known missing English source
titles remain incomplete scope coverage. All original QIDs/model rows remain
unchanged; 34 English and 12 Japanese redirect cases use one final page each.
These are separate language decisions, with no combined Event retrieval rule
inferred and no Event acquisition restarted. Input/output hashes, full dump
coverage and saved scoped-link agreement passed; all 19 earlier English
measurements are unchanged.

Current population evidence under `GG_Data/pipeline/outputs/`:

- `poc_10k_misc_snapshot_link_relevance_enwiki_patternfile_20261020/report.json`
- `poc_10k_scope_concentration_enwiki_patternfile_5pct_20261020/report.json`
- `poc_10k_misc_snapshot_link_relevance_jawiki_redirects_20261020/report.json`
- `poc_10k_scope_concentration_jawiki_redirects_5pct_20261020/report.json`

## 7. Events: discovery, inclusion and fields

**Latest approved source exception, 20 October 2026:** Event classification uses the latest available Wikidata P31/P279 hierarchy, with verified cache reuse first, even if the agreed snapshot contains an older class record. This supersedes snapshot-first priority for classification evidence only. Entities, Event assertion records and Relations retain the agreed snapshot-first source rule and latest-available same-QID fallback when required input is absent. Root Q140451665, non-deprecated classification, all statement ranks in Relations, and the two-distinct-Daniel-QID gate are unchanged. No version-difference report is required.

Incoming acquisition may first measure a superset of the existing inclusion gate in BigQuery: retain subjects with two or more distinct Daniel main-item targets, plus subjects with one such target that are also targets of a saved Daniel outgoing assertion. Outgoing-only neighbors remain in the local outgoing inventory. Mapping/exclusion checks and the distinct union of both directions still apply before inclusion. This query is a retrieval optimization, not a new relevance rule, assertion cap or claim of complete Event coverage. `event_snapshot_discovery.py` performs this measurement with the existing pinned CLI/cache/dry-run/billing controls and stops on an unapproved source or data failure.

**Verified acquisition measurement, 20 October 2026:** the saved BigQuery query found 2,209,613 incoming candidates before Event classification: 2,189,157 with at least two distinct Daniel targets and 20,456 with one incoming target plus an outgoing Daniel link. Their full native records total 37,433,814,344 bytes (37.4 GB). These are candidate items, not included Events. D: had about 17.1 GB free, so acquisition stopped before any full-record download under the POC consultation rule. The query result, source hashes and SQL receipt are verified in `GG_Data/pipeline/outputs/poc_10k_event_snapshot_measurement_20261020/verification.json`; no Event rows or final graph were written. The user subsequently approved classification-first acquisition; the active wider continuation is recorded above.

**Classification-first test approved and verified, 20 October 2026:** `event_classification_first.py` classified the existing 165-candidate probe using the verified latest-available cached hierarchy before requesting full assertion records. Seven candidates passed ancestry; only their seven QIDs were requested from BigQuery, returning 407,843 bytes of native records, all from the agreed snapshot. No fallback or new Wikidata request was needed. One new BigQuery query ran for the initial test; the checked replay reused it. Output: `GG_Data/pipeline/outputs/poc_10k_event_classification_first_checked_20261020`, status `VERIFIED_CLASSIFICATION_FIRST_BOUNDED_TEST`. This confirms retrieval order only: it does not classify the wider 2,209,613 incoming candidates, project savings to that population, or establish the two-distinct-Daniel-QID inclusion gate. No model Event rows or final graph were created. A compact latest-available classification index for the wider candidate population is still needed before full-record acquisition.

### Native hierarchy and inclusion

**Source approval, 20 October 2026:** use current Wikidata for Events and their
direct links to Daniel QIDs, and cache every retrieval. The approved root is
absent from the pinned public BigQuery copy; current table metadata is unchanged.
Live native record evidence confirms Q140451665, revision 2557731706, in
`outputs/poc_10k_event_root_live_check_20261020`. This changes only Event
acquisition; accepted matching, Entities and Daniel/Daniel Relations files stay
unchanged. Record endpoint/query scope, request times, untouched responses,
checksums and native entity revisions. A live acquisition window is not an
atomic snapshot. Query-service discovery must report its graph coverage; full
native records supply ranks, qualifiers and references. A small probe or one
incomplete endpoint cannot establish a complete Event population. Failed
requests stop without source substitution. The user approved three total
attempts per exact request for connection failures and HTTP 429/502/503/504,
shared across failure types and restarts. Wait at least 10/30 seconds before attempts 2/3 and respect
a later `Retry-After` deadline (seconds from response receipt or absolute HTTP
date). New network requests pause five seconds. Preserve every attempt;
previous failures count toward the same persistent budget. Reuse checksum-
verified successful responses without network calls. Exhausted retries and all
other failures, including timeouts, other HTTP/API errors, malformed data and
data/business exceptions, still stop with visible evidence. No automatic source or business-rule change is allowed.

After the five-QID combined-query timeout, the user approved smaller requests:
retrieve direct links first, then check the same hierarchy separately. Outgoing
links use full native records; incoming queries use one Daniel QID per request.
Both directions and all ranks remain required. Intermediate neighboring QIDs
are reference candidates only, never additional Daniel entities or included
Events until the agreed hierarchy and two-distinct-Daniel-QID gates pass.

Direct hierarchy acquisition uses batches of at most ten reference QIDs per
P31/P279 query, followed by cycle-safe local traversal of supplied statements.
There is no depth cutoff, truthy-rank restriction or local class mapping.
Missing query-graph records can be checked through the approved current native
JSON source; preserve that source evidence rather than treating a missing graph
record as proof of no Event ancestry.

**Rank rule approved, 20 October 2026:** Event classification excludes
deprecated P31 and P279 statements. Filter a separate view of complete saved
evidence and traverse it again, preserving alternative valid paths and explicit
empty parent lists. This filter does not apply to Relations or raw acquisition.

The complete five-QID source probe previously found Event
ancestry for countries through a deprecated native P279 statement. Population
stopped before writing Events. The user approved a diagnostic-only comparison
without deprecated P31/P279: 117 positives became 7 across 165 candidates.
The user subsequently approved this as the Event classification rule. Relations
and complete raw acquisition still retain all ranks. Evidence is saved under
`GG_Data/pipeline/outputs/poc_10k_current_event_rate_limit_retry_20261020` and
`GG_Data/pipeline/outputs/poc_10k_event_rank_test_20261020`.

**Historical exception after approval:** the native inspection stopped after four
of seven candidate records were saved. Q16743064 is labelled "Call of Duty:
Advanced Warfare" and described by Wikidata as a 2014 first-person shooter video
game. Its supplied P31/P279 path to the approved root has normal ranks throughout,
so the approved filter retains it. No ad hoc exclusion, replacement event root,
or new type rule was introduced. See
`outputs/poc_10k_event_seven_native_check_20261020/report.json` and
`source_surprise.json`. Completing the seven-candidate link gate or narrowing
scope was referred for consultation. No Event row or Event relation was written.

**Continuation approved:** finish all seven checks under the same rules; do not
add a video-game/type/date exclusion. Seven native records were subsequently
checked. Outgoing assertions are counted against all 4,712 distinct matched
Daniel QIDs in the frozen sample, after the 14 exact exclusions and catalog
v2.1.2. Three candidates already prove at least two distinct direct Daniel QIDs.
The remaining four are pending incoming coverage, not negative classifications.
The incoming World War II request returned HTTP 200 with 34,406,400 bytes of
incomplete JSON. The pipeline stopped without accepting partial rows or retrying
malformed data. Evidence: `outputs/poc_10k_event_seven_eligibility_resumed_20261020`.
Smaller incoming queries restricted to the approved populations were proposed
for consultation; the user selected "Discuss first". No new request design
has been executed. Full incoming
statement materialization and Event/Relations population remain pending.

**Bounded incoming retrieval subsequently approved:** use up to 250 frozen
Daniel subject QIDs and all seven candidate targets per request, covering both
official query graphs. For the 4,712-QID sample this is 19 batches per graph,
38 requests total. Retrieve full p/ps statement identities and all ranks;
do not add LIMIT, truthy-only filtering, hierarchy joins, or extra endpoints.
Validate every returned subject/target against the requested batch. Deduplicate
by native statement identity across the graphs and native outgoing evidence,
never by endpoint/predicate alone. The older malformed response is retained.

The first approved bounded request then reached a 45-second read timeout.
`outputs/poc_10k_event_seven_bounded_20261020/report.json` records the stop;
zero incoming requests completed, and no automatic timeout retry was allowed.
**Native API acquisition subsequently approved:** retrieve the fixed Daniel QIDs
through `wbgetentities`, in batches of up to 50, then inspect direct statements
locally. Reuse verified current single-record caches. Request complete native
records without redirects, claim/rank projection or language filtering. Require
every requested ID and revision before accepting a batch. This covers native
statements directly, without requiring query-graph search for this check.

The first run, `outputs/poc_10k_event_seven_native_batches_20261020`, reused
seven candidate records and six Daniel records. The first new batch returned
42 of 50 IDs and a result-truncation warning (stated API limit 12,582,912 bytes).
The original HTTP-200 body and metadata were cached, but the partial batch was
not accepted. Acquisition stopped immediately. Incoming coverage, complete
eligibility results and Event/Relations population remain pending. A proposal
to halve truncated batches, stopping if one ID still fails, requires discussion;
no such fallback was approved at that stop. See `acquisition_stop.json` and
`verification.json`; all accepted upstream output hashes remain unchanged.

**Response-size split subsequently approved:** halve only batches with the
explicit API result-size truncation warning; repeat until each child response
is complete. Do not accept partial parents. Preserve all responses and record
parent cache/checksum lineage on successful children. Stop if one ID still
truncates, or on another warning, changed/missing ID or unapproved failure.
This changes acquisition size only, without reducing full native evidence.
Continuation: `outputs/poc_10k_event_seven_native_split_20261020`; its final
report/verification determines coverage and seven-candidate eligibility.

**Current source exception after the size split:** acquisition stopped at
3,406/4,712 checked Daniel QIDs because the current API marks Q31545924 missing.
The rejected 50-ID batch is fully cached. The frozen sample's Clark Airbase LOC
mention on Manila retains this QID; the accepted saved native record is revision
1021165461, modified 2019-09-27T16:40:15Z. No rematching, replacement ID, partial
batch acceptance or Event population is authorized by this exception. Current
missing does not establish a reason. The proposed saved-native-record fallback
for missing current IDs requires consultation; stop if no saved record exists.
Coverage and final eligibility remain pending. See `source_exception.json` and
`verification.json` in the split run; accepted upstream hashes are unchanged.

**Missing-current fallback subsequently approved:** for an explicit missing
marker from current Wikidata, use the accepted saved native record for the same
QID. Verify the pinned Entities manifest and file checksum. Preserve original
QIDs, native revisions/dates and raw missing-current responses. Report every
fallback visibly in source lineage and on any affected qualifying link. Stop
if no saved native record exists or saved records conflict. An omitted ID or
redirect does not qualify. This does not authorize rematching or adding an
entity. Continuation: `outputs/poc_10k_event_seven_saved_fallback_20261020`.

**Seven-candidate verification completed, 20 October 2026:** that continuation
checked all 4,712 frozen Daniel QIDs: 4,705 current native records plus 7 approved
saved records for explicit current missing markers. `saved_fallback_audit.json`
records every original QID, older revision/full timestamp, source checksum and
affected mention count; affected link evidence carries the fallback lineage.
`verification.json` records `VERIFIED_SEVEN_CANDIDATE_ELIGIBILITY_ONLY`, 109
source-response checksum checks and 14 unchanged upstream output hashes.

World War II (363 distinct Daniel QIDs), Call of Duty: Advanced Warfare (7),
Raid on Santorini (2) and WikiProject Kerala (4) pass. Minoan eruption,
DTIS 2014 and the 2025 Santorini earthquakes each have one and do not pass.
The existing broad Event hierarchy and direct-link rules apply without a new
historical/type/date restriction. The 414 qualifying native assertions retain
all ranks (412 normal, 1 preferred, 1 deprecated), with zero exact-exclusion
hits and no mapping changes. Both native directions were reconstructed and
statement identities deduplicated; generated reverse views do not add counts.

This verifies only seven candidates from the earlier five-seed probe, not full
10K discovery. No Event model rows were written. Event discovery/population,
addition of Event links to the populated Relations model, Geography and final
graph/Agent integration remain pending. Tests: 48 passed. See the pipeline
README for the complete results and visible seven-record fallback list.

**Full-population continuation approved, 20 October 2026:** extend the same
direct-candidate discovery to all 4,712 matched Daniel QIDs. The implementation
`GG_Data.pipeline.event_discovery` verifies accepted upstream checksums, reuses
the full native outgoing cache and issues the existing single-QID incoming query
to both official Wikidata graphs. All ranks and both directions remain required.
The same source adapters, approved retries/size split/saved-native fallback and
first-exception stop rule apply. No new classification or matching rule is added.
`outputs/poc_10k_event_full_discovery_20261020` records progress and candidate
reference QIDs; these are not additional Daniel entities or included Events.
Outgoing cache coverage is 4,712 records, 87,694 item-valued statements and
46,094 distinct targets. Complete incoming acquisition, approved hierarchy and
inclusion gates, and model population remain separate required steps.

**Full-discovery source exception:** both Africa/Q15 incoming graph searches
completed, but the main-graph Canada/Q16 response returned HTTP 200 with
352,032,025 bytes ending in an embedded server `TimeoutException`. The original
body/checksum remains cached; malformed JSON was rejected without using partial
rows or retrying. The run stopped at 2/9,424 incoming graph/QID requests, with
29,923 incoming statements and 75,655 partial reference QIDs in the union.
`verification.json` has status `VERIFIED_FULL_DISCOVERY_SOURCE_STOP_ONLY`;
105 response checks, 17 prior candidate output hashes and 14 upstream hashes
passed. No Event rows or complete discovery result exist. Proposed smaller
incoming pages (at most 5,000 statements with a native identity cursor and
complete coverage across both graphs) were brought back to the user before
implementation or another source request. Approval is pending; source and
business rules are unchanged.

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

- Current fact provider is **Wikidata**. Eligible item-to-item source assertions connect D/D, included-event/D, or two included Events, in either source direction. Apply the non-event selection rule below after Event inclusion is established.
- Include every available predicate, subject to the existing exact exclusions and versioned mapping. Do not restrict to the earlier saved assertion file. An actual native Wikidata property without a source mapping follows the approved native-preservation rule below; ambiguous or conflicting mappings still require discussion.
- All retrieved ranks, qualifiers, references, literals, somevalue and novalue remain raw evidence. The latest "any assertion" scope does not authorize the legacy producer's silent deprecated-rank skip. Do not select only a preferred statement as a substitute for preserving all eligible assertions.
- Non-item values cannot satisfy the two-entity relation filter or event threshold; keep them in raw claims/audit without manufacturing entity rows. The nullable object fields remain available in the model contract.
- Direct assertions between two included Events are eligible under the 20 October user correction. Both Events must independently pass the existing inclusion gate against D; an event/event link cannot satisfy that gate. No other endpoint expansion, transitive relation, or synthetic participation is allowed.
- Apply the 14 approved exact source-record/predicate/original-endpoint exclusions before mapping; retain excluded records and reasons. Do not blanket-remove self-links.

Resolve the mapping by exact source/predicate key and version in [RELATION_MAPPING_TABLE_v2.1.1.csv](../GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.1.csv). `direction_to_level2` supplies same/reverse endpoint normalization, once. For a legacy v1 row, reconstruct source orientation before v2.1 normalization. Do not transform an already transformed pair twice. Ambiguous keys, unsupported sources and proposed semantic translations require a visible case report and discussion. Missing exact native Wikidata keys follow the approved rule below.

**Native Wikidata mapping rule, approved 20 October 2026:** if no usable relation/mapping exists for the two in-scope endpoints, look for an actual direct Wikidata item-to-item statement between those same IDs. Use existing eligible mappings first. If its exact `(Wikidata, wd:P...)` key is absent, add a source-specific parameter row that preserves the native property as Level 2 and keeps its original direction. Reuse any existing identical Level 2 definition and reverse contract. Leave Level 1 `UNRESOLVED` with `level1_assignment_status=NOT_ASSIGNED`; do not infer a family. If the exact source key already exists but conflicts or is ambiguous, stop rather than override it.

The added entry must retain native statement IDs, original endpoints, property label/source evidence and the observed count scope. Keep ranks/qualifiers/references unchanged; apply the existing exclusions first. If no Wikidata statement exists, create no relation. Do not infer links from names, co-occurrence, similarity, indirect paths or a shared class. Add no endpoint entities. A reverse view follows the existing v2.1 contract and shares the same assertion identity; it is not a newly discovered Wikidata statement.

Persist native additions in a supplemental parameters CSV and build a new versioned mapping/direction catalog. Pin its checksums in the run lineage; do not modify a historical version in place. Missing native source keys covered by this rule no longer require individual business approval. Unknown non-native semantics, conflicts and incompatible source values still require consultation.

**Existing reverse labels, confirmed 20 October:** preserve the prior direction catalog's exact labels and label source when adding native keys. In particular, keep P8138's reverse label `inverse of located in the statistical territorial entity`; store the retrieved P10888 name `contains the statistical territorial entity` in property evidence/parameters without replacing that display definition. Keep relation IDs, endpoint direction and family decisions unchanged. A new source key may extend source-policy provenance/counts, not alter settled semantics.

**Property-name cache, approved after the P10888 stop on 20 October:** reuse existing native property labels first. Missing names may be retrieved as property (`P...`) records from the agreed Wikidata BigQuery table at the pinned snapshot, using the existing GCP CLI, dry run, billing cap and query cache. Preserve raw records, query/job evidence and checksums under `GG_Data/pipeline/outputs/wikidata_property_cache`. These records populate mapping parameters only; they do not create Entities. A missing/invalid property record or absent English label remains an explicit stop, with no provider or label substitution.

The first applied entry is `(Wikidata, wd:P2341)` in `ADDITIONAL_NATIVE_RELATION_RULES_2026-10-20.csv`, with evidence in `NATIVE_RELATION_EVIDENCE_2026-10-20.json`. P2341 already had an EventKG source entry and a Level 2/reverse definition; only the native Wikidata source key was missing. `relation-map-v2.1.1` adds that key and reuses the existing definition. This imports no EventKG assertion. The recorded count of one is the observed first-exception statement, not a full-sample P2341 total.

| Target column(s) | Source and population rule |
|---|---|
| `observation_id` | Existing assertion ID where present. Fresh assertions reuse the established relation producer's stable source-statement identity recipe; do not derive identity from endpoints/predicate alone. Repeated retrieval of the same statement is not new evidence. |
| `subject_entity_id`, `object_entity_id` | Source QIDs normalized once by the versioned direction mapping, after scope/exclusion checks. Require at least one existing Entities row per endpoint QID. Relations remains at QID level; do not choose a type or expand an assertion across typed entity combinations. |
| `object_value` | Original non-item/somevalue/novalue payload when retained as supporting assertion evidence, never a fabricated QID. |
| `level2_relation`, `level2_label` | Catalog `level2_relation_id` and exact label, preserving case. |
| `level1_relation`, `level1_assignment_status` | Exact versioned family and assignment status; no family inference. |
| `selection_priority`, `selection_status`, `direction` | Existing catalog/producer outputs, with original values retained. Do not claim a review for newly retrieved statements. |
| `time_from`, `time_to`, `time_point`, `time_precision`, `time_status` | Use the approved Relations date policy below. Preserve all original P580/P582/P585 qualifiers, precision and calendars; record the selected values and policy separately from raw evidence. |
| `selected_source`, `selected_source_predicate` | Wikidata provider key and original Wikidata property, not a generated reverse predicate. |
| `source_record_id`, `source_graph`, `source_reference` | Native statement ID and actual saved source graph/reference. Absent optional provenance stays absent; do not invent a source graph. |
| `source_support`, `evidence_references`, `sources` | All supporting statements, original endpoints, references, qualifiers, ranks and retrieval evidence. Only verified page citations are used; no paragraph citations are generated. |
| `final_review_status`, `final_mapping_class`, `mapping_origin` | Actual existing mapping/review evidence. Prior catalog review is not review of a new statement or its historical truth. |
| `relation_map_version` | Applied `relation-map-v2.1.1` for the current native extension, tied to catalog hashes. Future additions require a new pinned version. Old outputs are not relabeled without replay. |
| `input_assertion` | Preserve all 26 legacy assertion columns and complete raw statement/envelope, or an immutable artifact reference. New-source fields absent from a legacy producer remain explicit, not fabricated. |
| `count` | 1 per retained base source assertion, not mention frequency. |
| `attributes`, `embedding` | Supplied qualifier/side/extra payload and existing embedding only. Do not invent participant roles or compute embeddings. |

### Non-event relation selection — approved 20 October 2026

**Current corrected Entity score output:** `outputs/poc_10k_entities_importance_synthetic_scored_20261020`, policy v1.0.1, verification `VERIFIED_ENTITIES_IMPORTANCE_INCLUDING_SYNTHETICS`. All 6,077 existing Entity rows are scored: 4,721 QID/type rows plus 1,356 synthetic rows at exactly 1. Zero null scores; 6,068 distinct scored identities from 9,048 original mentions. Previous QID scores, original fields and source evidence are unchanged; hashes pass and 56 tests pass. Synthetic DATE errors also score 1; successful normalized dates have no Entity row. No source query or selected Relations output was added. Events remain incomplete.

**Execution order:** calculate and verify importance for the declared Daniel input population before new relation retrieval. Reuse that saved score artifact when retrieving and selecting Relations. Establish complete Event membership before applying the non-event cap, so all eligible Event links remain exempt. Importance itself requires no graph or Wikidata relation query.

Status: score and selector implemented in `GG_Data/pipeline/relation_selection.py`; application to a complete Event/Relations population remains pending. The frozen 10K score preparation covers 4,712 QIDs and 7,692 matched non-DATE mentions. It has status `IMPORTANCE_ONLY_EVENTS_PENDING`; no capped output has been written.

Historical Entity-attribute run, 20 October (superseded): `outputs/poc_10k_entities_importance_20261020` retained all 6,077 existing Entity rows but left 1,356 synthetic nulls. Its historical `VERIFIED_ENTITIES_IMPORTANCE_ONLY` check verified that implementation, not the corrected rule. The user clarified that each per-mention synthetic ID has one mention on one page and therefore must score 1. Prior output files remain unchanged; complete Events, capped Relations and final graph remain pending.

- Event/Event and Event/other-entity assertions are uncapped. Keep every eligible assertion under the existing source, mapping and exact-exclusion rules. All Events still require the agreed two-distinct-Daniel-QID inclusion gate, evaluated before selection. A QID present in included Events receives the Event exemption even when it also has other entity types.
- For assertions with two non-event endpoints, the maximum is **20 base relations incident on each QID**, across both native directions. Separate typed rows do not get separate budgets. Reverse delivery views share the original assertion's slot; they do not consume additional slots.
- Score each existing Daniel Entity identity using **distinct Daniel source-page count multiplied by total original Daniel mention count**, aggregated by assigned QID or existing synthetic ID, without duplicating mentions across typed Entities rows or counting retrieved Japanese counterparts as Daniel source appearances. Each separate synthetic ID has one page and one mention, hence importance 1; no QID is required to count it. Count Daniel's original `raw.Source` values for source-page appearances, without inventing page IDs or processing paragraph text. Pin the input population: this POC uses its frozen 10K mentions, not an unstated whole-corpus frequency. No graph centrality, BM25, new extraction or rematching is approved.
- Each endpoint ranks its eligible non-event assertions by the other endpoint's score. Keep an assertion only if it is in the top 20 at **both endpoints**. Intersect these selections; do not refill rejected slots. Some entities can therefore retain fewer than 20 relations.
- Preserve all acquired source evidence and previous outputs. Persist the approved score as Entities.importance and the factors/lineage as attributes.importance_basis. Supporting selection evidence must pin the Daniel input population/checksums, page and mention counts, score, both endpoint decisions and retained/omitted counts. This score is not a Wikidata-supplied Event `importance` value and must not overwrite that field.
- If equal scores cross the cutoff, or the declared source population/page identity cannot support the calculation, stop with the concrete cases for discussion. No new tie-break, missing-value substitution or score-population change is approved by this rule.

Complete Event membership is required before applying the exemption. After approving this rule, the user instructed implementation and continued execution. The continuation uses the proposed incoming pages of at most 5,000 statements, with a strict native-statement-URI cursor, both graphs and the complete page chain. Existing complete unpaged responses are reused; malformed unpaged responses remain untouched. Page ordering, uniqueness and cursor progress are checked before accepting data; a short terminal page is required. No new Event count limit or relevance filter is authorized, and the existing retry/stop rules remain in force. Run: `outputs/poc_10k_event_full_discovery_paged_20261020`; live status belongs in its report, not an assumed completion. Tests before launch: 55 passed. Applying the selector and producing a fresh versioned Relations output remain pending; historical full D/D outputs are not relabeled as capped.

That continuation stopped on the first new Canada/Q16 page: a 45-second read timeout with no response body. No new paged response, partial result or automatic timeout retry was accepted. Its verification status is `VERIFIED_PAGED_DISCOVERY_SOURCE_STOP_ONLY`; 105 saved response checksums, 14 upstream hashes and 17 preceding candidate output hashes passed. Scores are verified separately in `outputs/poc_10k_relation_importance_20261020/verification.json`. Event membership and cap application remain pending. A more specific incoming query by individual Wikidata property was proposed as a test; the user requested an explanation, not execution. No property filter/test is approved or applied by that discussion.

**Subsequent approved diagnostic, 20 October:** the user then approved the one-property retrieval test. `event_property_probe.py` requests Canada/Q16, P17 (country), on the main Wikidata query graph with the same 5,000-statement page chain, ranks, cache and stop rules. This diagnostic is not a property whitelist or complete discovery implementation. It verifies the corrected scored Entities and previous stop artifacts before the request. The request timed out after 45 seconds with no response body; zero property pages/statements were accepted and no timeout retry ran. Evidence: `outputs/poc_10k_event_property_probe_20261020`, verification `VERIFIED_PROPERTY_RETRIEVAL_SOURCE_STOP_ONLY`. All five upstream output hashes checked unchanged; the failure receipt and code hashes are recorded. Full incoming coverage remains 2/9,424 graph/QID requests, with zero new Event rows, capped Relations or final graph. The process has ended. Before launch, 57 tests and Ruff passed. Further retrieval changes require consultation; no Event, identity, mapping or relevance rule changed.

### Relations date policy — approved 20 October 2026

`relation-date-selection-v1.1.0` applies to Relations only; it does not select Event dates. The user correction supersedes the earlier pre-1900-end exclusion: these statements remain in Relations with their original dates.

- Historical exception first: if the latest supplied P582 end year is before 1900, retain the relation with its supplied start and end dates, precision and calendar. Do not apply a 1900 floor or exclude it on this basis. A missing start remains missing. If multiple dates are supplied, preserve every value; select the earliest original start and latest end under the existing conflict rule. Mark `attributes.time_selection.original_pre_1900_end=true`.
- Other relations: select the earliest supplied P580 value whose year is at least 1900. If all supplied starts precede 1900, use derived year 1900 with year precision (9), without inventing a month/day. Select the latest supplied P582 end. Missing dates stay missing. The 14 exact assertion exclusions still apply before date selection; no date-only exclusion is authorized.
- Keep every original value, snak, precision and calendar. Store selection rules, selected precision and the derived flag in `attributes.time_selection`; preserve the same evidence in `input_assertion`. Multiple supplied start/end values remain visible as `MULTIPLE`, even when this approved rule selects a value.
- Different calendars within a date field, multiple distinct point dates, unsupported date formats, or a remaining start-after-end interval require consultation. No silent repair or point-date selection is approved.

One source assertion produces one base row. Bidirectional graph navigation is supplied by the separate exporter using the [direction lookup](../GG_Data/mapping/RELATION_DIRECTION_LOOKUP_v2.1.1.csv) and `source_edge_id`. A generated reverse view is not a second independent assertion. Two genuinely separate Wikidata statements in opposite directions retain their own identities. No fixed assumption of exactly two assertions per entity pair is valid.

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
| Identity and page keys | Unique `(entity_id, type)` pairs and valid composite mention FKs; QID-level references exist without multiplying assertions; page-key pairs complete; no talk IDs, Index-as-page-ID, cache-only entity expansion or extra Daniel mentions. |
| Scope-concentration measure, when supplied | Matched QIDs only; exclude synthetic IDs. Both page counts use the same snapshot/language/link rules, with source-page deduplication and full Daniel page scope. Report missing coverage and unknown denominators. Apply the provisional 5% rule to measured MISC QIDs: exclude <0.05 from Event retrieval, keep >=0.05; retain model records. Keep this measure separate from `Entities.importance`. |
| Events | Native root/snapshot/path evidence; original QIDs; all approved event types; at least two distinct direct Daniel QIDs; incoming/outgoing acquisition coverage reported. |
| Assertions | Reconcile retrieved eligible statements = retained mapped base rows + exact exclusions + explicitly reported unmapped/ambiguous/blocked cases, deduplicated by source statement. Report all categories and ranks. No silent loss through join/mapping/rank filters. |
| Geometry | At most one accepted object per place; failed attempts retained; source and CRS known; valid nonempty Shapely/WKB round trip before delivery. |
| Contract coverage | All ERD fields, nine Daniel fields, 16 matching CSV fields, 26 legacy assertion fields, full nested reference/attempt payloads, geometry compatibility fields and versioned catalog columns retained or explicitly unavailable. |
| Reuse and release | Pinned hashes and request scope; existing verified artifacts reused; missing references/counts visible. No cloud/data/Agent completion claim based only on this document. |

Different resolved types for one QID are not an unresolved conflict: keep distinct `(entity_id, type)` combinations. Event membership coexists with other types. MISC classification is not an open decision. Relations stays at QID level, with one base row per source assertion.

The following cases must be brought back with exact IDs, values and counts before adding logic: differing Daniel fallback names when both Wikidata labels are missing; unlabeled events without Daniel names; ambiguous/conflicting mappings or unsupported non-native predicate semantics; incompatible multivalued event dates/classifications; source-page input/lookup conflicts; partial-date interpretation required for geometry selection; or a concrete specialist geometry source. Preserve raw evidence while the required decision is pending, and report the affected population explicitly.

Downstream interfaces approved on 19 October 2026: separate graph entities use `QID::type` with original `wikidata_id`; relations keep QID endpoints, resolved to the separate typed entities without copying assertions. `geometry_ref` is null or `{file,place_id,sha256}` identifying GeoParquet/file/place/checksum; the loader returns Shapely and errors on broken references. Agent integration, spatial CRS compatibility and reverse-view evidence checks remain implementation work. These interfaces do not change source population or matching. Final graph sources remain omitted; provenance stays in this model and supporting artifacts.

### First implementation checkpoint

`GG_Data/pipeline/poc.py` implements the initial 10,000-row sample, input/matching hash checks, Mentions and resolved Wiki Pages copying. Complete request payloads are stored once in supporting `page_evidence.json.gz`; mention/page references include a record locator and the output manifest binds the file hash. No text extraction or rematching occurs. `graph_contract.py` implements the approved graph interface helpers; it is not yet integrated into the Agent.

On 20 October 2026 the user approved D: data output. Step 1 completed at `GG_Data/pipeline/outputs/poc_10k`: 10,000 unchanged original mentions, comprising 7,692 saved QID assignments, 952 normalized dates and 1,356 existing synthetic IDs. There are 691 distinct resolved EN/JA pages. The sample includes the four already-known missing requests, affecting 29 mentions. Output hashes, original rows, sampling positions, mention/page keys, page links and per-mention synthetic identities passed verification. See [detailed counts](../GG_Data/pipeline/README.md#verified-first-run-results--20-october-2026). Status is `STEP_1_ONLY`; later population stages and the final graph remain pending. This does not certify matching accuracy or a complete six-table POC.

### Entities implementation checkpoint — 20 October 2026

After the two pinned older-English cases in section 6 were approved, the new
`GG_Data/pipeline/outputs/poc_10k_entities_approved` run passed verification:
6,077 rows = 4,721 QID/type pairs over 4,712 QIDs + 1,356 unchanged synthetic
identities. All full records were reused from the archive/query cache; the CLI
was blocked and zero requests were made. Source/output/first-step hashes,
identity/type membership, raw native evidence, synthetic names and page subjects
passed checks. Only approval metadata for Q132537/Q1771928 differs from the
earlier draft. The 19-test suite and Ruff passed. The 691 Wiki Pages have 197
existing entity subjects. The manifest remains `ENTITIES_STEP_ONLY`; later
population stages and graph/Agent integration are not complete.

The following cache-only D/D relation check stopped at the first unknown mapping
as required by section 8: `(Wikidata, wd:P2341)`, statement
`Q105969841$8D05BA41-C448-45B5-93EA-A37877F5140D`,
Poles (`Q105969841`) -> Poland (`Q36`). No mapping was added. The partial check
had examined 191 eligible non-excluded statements when it stopped; this is not
a full-population missing-mapping count. Raw evidence and catalog checksums are
in `GG_Data/pipeline/outputs/poc_10k_relations_preflight/first_exception.json`.
The user subsequently approved the general native-preservation rule above.
P2341 is now present in `relation-map-v2.1.1`; the original exception report
remains historical evidence. The later source scan passed; population replay status is recorded below and in the pipeline README.

The earlier Ribbentrop multiple-start stop is resolved by the approved date policy: select 1930 and retain both original qualifiers. The later Prague statement `Q1085$0697567f-4a18-22cf-3118-7f7622ccf2f5` has source dates 1804-08-11 through 1867-03-29; it was excluded under the earlier rule. The latest user correction restores this relation with those original dates. Historical exception files remain unchanged; their exclusion rule is superseded.

The cache-only source gate then passed at `GG_Data/pipeline/outputs/poc_10k_relations_date_scope_check_20261020/source_check.json`: 4,712 source QIDs, 213,277 claims, 10,501 in-scope statements, 34 pre-1900-end exclusions and 10,467 retained statements. This is `DANIEL_RELATIONS_SOURCE_CHECK_ONLY`, not a populated Relations table or completed POC. No query or entity change occurred.

The subsequent Daniel/Daniel Relations population passed in `outputs/poc_10k_relations_labels_preserved_20261020`: 10,467 base statements, 34 pre-1900-end exclusions and 86 visible temporal-decision audit rows. Nine native keys were added to cumulative parameters and POC catalog v2.1.2 (1,605 source mapping rows, 1,073 Level 2 definitions, 2,113 direction lookup rows), without changing existing mapping semantics or approved labels. The nine missing property records are cached from the pinned BigQuery source; no entities were created. Status is `DANIEL_RELATIONS_ONLY`; event links, Events, Geography, graph and Agent integration remain pending. The final replay directory `outputs/poc_10k_relations_final_20261020` is accepted only if its manifest and checks pass. See the pipeline README for full lineage, historical stops and limits.

## 11. Contract references and precedence

- [Six-table ERD and exact column inventories](ENTITY_DATA_MODEL_ERD.md).
- [Separate model-to-graph JSON S2T](ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md).
- [v2.1 direction rules](RELATION_MAPPING_V2_1_DATA_LAYER_REVERSE_2026-10-15.md), [current mapping table](../GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.1.csv), [current direction catalog](../GG_Data/mapping/RELATION_DIRECTION_CATALOG_v2.1.1.csv), [exact exclusions](../GG_Data/mapping/ASSERTION_EXCLUSIONS.csv).
- Existing relation producer: `GG_Data/mapping/RELATION_MAPPING_ALL_ITEMS_v1.0.0.ipynb`; its historical output is an input/evidence contract, not proof of current scope, rank handling or v2.1 population completion.
- [Geometry source and selection policy](GEOCODING_HIGH_LEVEL_PROCESS.md) and [extraction method](../GG_Data/geocoding/GEO_OBJECT_EXTRACTION_METHOD.md).

Latest user decisions govern name priority, Wikidata-only assertions, included event links in Relations, all event types under Q140451665, two-entity event minimum, per-mention synthetic IDs, no new Daniel entities, and Shapely objects with downstream JSON pointers. No physical model tables or new production outputs are created by this specification.

### Correction: retain historical relations

The user withdrew the pre-1900-end exclusion after reviewing the 34 excluded statements. Current policy v1.1.0 retains these statements with original dates and no 1900 start floor. Earlier run directories and their manifests remain immutable historical records, not the corrected current population. The new replay is `GG_Data/pipeline/outputs/poc_10k_relations_original_historical_dates_20261020`; require its successful manifest before use. No event-root/source decision is changed by this correction.
