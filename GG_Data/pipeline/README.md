# Daniel pipeline POC

## Actual Wikipedia page-link relevance test — 20 October 2026

The approved corrected numerator counts **actual Wikipedia links to each QID**
within **all Daniel source pages**, once per QID/source-page ID. Daniel's
mention-to-QID assignments do not supply this count. The denominator counts all
distinct source article pages linking to that QID, using the same language,
snapshot, redirect resolution and namespace rules. The earlier mention-based
ratio below is retained as historical evidence and does **not** test this measure.

`snapshot_link_relevance_probe.py` runs the English diagnostic for the same 19
QIDs with saved English probe pages. Both sides use the saved Wikipedia dump
date from the source-page snapshot manifest. It scans the complete saved raw
linktarget/pagelinks files, resolves all target aliases, and deduplicates source
page IDs across aliases. Links from templates/navigation remain included, as
in the existing dump-backed resolver. No source download or API request is
needed. The installed `rg` tool filters the pagelinks stream with the same
integer-only regex used by Python; only selected rows go to a temporary file.
The raw dump SHA1, gzip integrity, completion footer and complete row
counts must pass before scores are published. Scoped counts must also agree
with the independently saved per-page link resolution.

The user approved incomplete scope coverage: 428 Daniel source titles, 424
resolved titles, **413 distinct resolved article pages**, and four missing
titles (`Conscription in Japan`, `Two Lords Incident`, `BUROGU`, and
`Gabriel Maurício Teixeira`). Missing pages remain unknown; they are not zero
observations. The score measures link concentration, not matching confidence.
No filtering threshold, matching change or Event restart is approved.

Current run: **scanning saved files; no final scores yet**. Evidence:
`outputs/poc_10k_misc_snapshot_link_relevance_20261020/progress.json`.
An initial implementation check incorrectly required non-article redirect
sources to occur in the article-only page table. It was corrected to use the
existing resolver's namespace-0 join rule; the failed preflight is retained in
`outputs/poc_10k_misc_snapshot_link_relevance_20261020_preflight`.
The slower Python-filter attempt was stopped for a local performance change
and retained in `outputs/poc_10k_misc_snapshot_link_relevance_20261020_python_scan`.

## Offline relevance ratio test — 20 October 2026

`misc_relevance_probe.py` uses the saved English count response only; no new
source requests or matching changes. Score = distinct English Daniel page IDs
in the frozen 10K sample / current English incoming-link count. All mentions of
the same QID count toward the numerator, without counting repeated mentions or
types twice on one page. This is a diagnostic score, not a confidence or a true
share of Wikipedia backlinks: Daniel mentions and actual hyperlinks differ.

**18 QIDs scored; one missing count remains unknown.** The result does not
support automatic filtering: `British` matched to `Britannicus (play)/Q1196012`
ranks first at **19 / 82 = 0.231707**, while World War II/Q362 ranks last among
measured items at **23 / 217,991 = 0.000105509**. M4 Sherman/Q191643 scores
**1 / 1,362 = 0.000734214**; Japanese language/Q5287 scores
**28 / 39,178 = 0.000714687**. A small denominator can promote a wrong match.
Existing mistaken QID assignments also contaminate the numerator. No cutoff,
identity correction, or changed scoring formula was selected. Further changes
require discussion under the user's POC rule. Evidence:
`outputs/poc_10k_misc_relevance_probe_20261020/report.json` and `scores.csv`.

## Stopped diagnostic — Wikipedia incoming-link counts, 20 October 2026

`incoming_links_probe.py` tests precomputed CirrusSearch counts without changing
matching, model rows, or Event runs. The diagnostic selects two known problem
QIDs, six frequent eligible MISC QIDs, and twelve random eligible MISC QIDs
(seed 20261020). Of 1,182 matched MISC QIDs in the frozen 10K input, 633 have a
saved English or Japanese sitelink; 549 do not. This is a selected diagnostic,
not an accuracy estimate or a representative full-population distribution.

The English response returned 19 pages: **18 supplied a count**, while
`O (2022 film)/Q129084702` omitted the field. The strict parser stopped; the
Japanese request was not sent. Missing counts remain unknown, not zero.
Saved-response analysis found Japanese language/Q5287: **39,178**, Brazilian
Portuguese/Q750553: **1,613**, M4 Sherman/Q191643: **1,362**, and World War II/Q362:
**217,991**. A high-count cutoff misses the Brazilian-language example; a low
cutoff can remove useful matches. No threshold was selected or applied.

These are **current, per-wiki index counts**, not all-language totals or values
from the agreed historical snapshot. Index article timestamps do not establish
the measurement time of the incoming-link count. The debug API has no stable
schema guarantee. Evidence is in ignored local outputs
`outputs/poc_10k_misc_incoming_links_probe_20261020`: raw response, request URL,
retrieval time, checksums, `partial_analysis.json`, and `partial_counts.csv`.
Continuation requires discussion under the user's POC stop rule.

## Stopped for analysis — larger Event timing sample, 20 October 2026

`event_timing_sample.py` draws 100 original frozen Daniel mentions (seed 20261020), including 71 distinct matched QIDs. Unrestricted snapshot discovery returned 16,097 incoming candidates; combining both native directions and requiring two distinct Daniel endpoints left **15,550 candidates**. The full inventory is retained. A separate uniform sample of **200 candidate QIDs** measures latest-hierarchy classification and link qualification; it is a timing experiment, not an Event population cap. No untested candidate is rejected and no model Event or graph is written.

The discovery query took **76.008 seconds** on BigQuery and billed 1,561,930,498,048 bytes. Later benchmark attempts reuse its saved result. The user stopped the benchmark at **14:04:37 Jerusalem, 20 October 2026**, after **660.701 seconds**: **69/200** classifications, **67 negative**, **2 hierarchy-positive**, **98 successful source-answer receipts**. Link qualification had not started; no Event rows or graph were written. The worker is stopped. Evidence: `outputs/poc_10k_event_timing_100_mentions_200_candidates_20261020/stop_analysis.json`; the original worker report is preserved separately.

Analysis found **12,316/15,550 candidates (79.2%)** connected to exactly the same two saved Daniel QIDs: Japanese language/Q5287 and Brazilian Portuguese/Q750553. The sampled source contexts are “Japanese military” and “Brazilian Navy”; their frozen upstream name matches selected language identities. This is a contextual identity problem requiring review, not a new name-matching step in Event retrieval. Assignments remain unchanged. Completed batches varied from **11.335 to 322.088 seconds**, including an HTTP 429 retry with a 120-second cooldown. All 69 decisions were replayed offline and all 98 raw-response hashes verified. No reliable full-run ETA is established. No new source calls were made during analysis. The original full run remains stopped.

The initial benchmark adapter compared native rank names with saved SPARQL rank URLs incorrectly and produced invalid country classifications. It was stopped before any import. `native_rank_answers` now adapts verified rank URLs to native names; the existing deprecated-ancestry rule and raw source caches are unchanged. A regression test checks this exact failure. Both interrupted attempts and their code/response evidence are retained. A verified empty folder left by the interruption was preserved separately before repeating that request under the existing recovery approval. Checks: **32 tests passed**, Black and focused Ruff passed. Cache/output evidence is local and ignored by Git.

## Previous result — small Daniel-first query test, 20 October 2026

`event_sample_query.py` tested five Daniel QIDs selected with seed 20261020 and two separate positive controls already present in Daniel: Hitler/Q352 and Roosevelt/Q8007. It reused the accepted 165-candidate hierarchy probe, queried native assertions from the agreed BigQuery snapshot, counted distinct Daniel endpoints and checked mapping/exclusions before the final decision. Result: **World War II/Q362, two distinct Daniel QIDs, five native assertions**, with both native directions represented. Statement identities matched an independent check of the complete saved records exactly. Repeated links to Hitler did not count as additional entities. SQL, response, source/job evidence and decisions are in `outputs/poc_10k_event_sample_query_20261020`; all recorded input/output checksums passed. BigQuery execution was 1.975 seconds; billed bytes were 68,943,872,000. No live Wikidata request was needed.

This is a bounded query test using previously classified references, not validation of complete Event discovery or full-scale performance. It writes no model Events or graph JSON and does not restart the full run. The preceding on-demand worker stopped on a read timeout: **17/2,218,368 candidates classified, 568 source answers, 282 fetched class nodes, zero Event rows**. Its launch details below are historical. The full run remains stopped.

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

**Latest Event-classification exception, approved 20 October 2026:** use the latest available Wikidata P31/P279 hierarchy, reusing verified cached evidence first, even when an older class record exists in the agreed snapshot. This exception applies to Event classification only. Keep Q140451665, the non-deprecated ancestry rule and the two-distinct-Daniel-QID gate. Entities and Relations retain snapshot-first priority and same-QID missing-record fallback. Do not replace snapshot assertions with classification evidence or create version-difference reports.

`event_snapshot_discovery.py` verifies the accepted Entities, frozen Mentions and cached current hierarchy. It measures the incoming candidate superset in the agreed BigQuery snapshot through the existing CLI, dry run, billing cap and saved-query cache. A candidate with at least two incoming Daniel targets remains eligible; a candidate with one incoming target and a Daniel outgoing link is also retained for later union checking. Outgoing-only candidates are already in the local inventory. This acquisition measurement is not Event inclusion or complete discovery. No model Event, selected Relation or final graph is written by this step.

**Verified acquisition measurement, 20 October 2026:** the saved BigQuery query found 2,209,613 incoming candidates before Event classification: 2,189,157 with at least two distinct Daniel targets and 20,456 with one incoming target plus an outgoing Daniel link. Their full native records total 37,433,814,344 bytes (37.4 GB). These are candidate items, not included Events. D: had about 17.1 GB free, so acquisition stopped before any full-record download under the POC consultation rule. The query result, source hashes and SQL receipt are verified in `GG_Data/pipeline/outputs/poc_10k_event_snapshot_measurement_20261020/verification.json`; no Event rows or final graph were written. The user subsequently approved classification-first acquisition; the active wider continuation is recorded above.

**Classification-first test approved and verified, 20 October 2026:** `event_classification_first.py` classified the existing 165-candidate probe using the verified latest-available cached hierarchy before requesting full assertion records. Seven candidates passed ancestry; only their seven QIDs were requested from BigQuery, returning 407,843 bytes of native records, all from the agreed snapshot. No fallback or new Wikidata request was needed. One new BigQuery query ran for the initial test; the checked replay reused it. Output: `GG_Data/pipeline/outputs/poc_10k_event_classification_first_checked_20261020`, status `VERIFIED_CLASSIFICATION_FIRST_BOUNDED_TEST`. This confirms retrieval order only: it does not classify the wider 2,209,613 incoming candidates, project savings to that population, or establish the two-distinct-Daniel-QID inclusion gate. No model Event rows or final graph were created. A compact latest-available classification index for the wider candidate population is still needed before full-record acquisition.

For each new Daniel input version, create and retain a separate reference snapshot at the data datetime selected for that version's initial entity/reference retrieval. Record its input version/hash, matching run ID, table/version and exact UTC snapshot datetime together. Read `reference_manifest.table_snapshot.snapshot_at` for downstream retrieval; never hardcode one datetime for future versions. A timestamp alone is not retained data: persistent snapshot creation/retention remains an implementation requirement.

**Latest user approval, 20 October 2026:** use the agreed Wikidata snapshot directly. Do not compare archived versions, create version-difference reports, or stop merely because labels, classes or statements differ between versions. This supersedes the earlier per-case class approvals, newer-label ranking, older-English exceptions and snapshot-only fallback prohibition. Keep the saved matched QIDs, broad entity types, mention assignments and importance scores. Use English, then Japanese, then the existing Daniel-name fallback from the selected source record.

When needed entity input is unavailable in that snapshot, use the latest available complete Wikidata record for the same QID. Among validated available versions, choose the highest item revision; do not change the QID or invent an entity. Keep the selected record's ordinary source/revision/timestamp metadata, without an archived-versus-snapshot comparison log. Reference-only items, including the approved Event root/hierarchy, follow the same source priority and never expand Daniel's entity population. A snapshot lookup miss does not mean the entity is absent from current Wikidata. A service failure or unqueried QID does not establish a snapshot miss; existing source-error and integrity checks still apply. If neither source provides the required input, stop and show the case.

Current-version lineage only: `bigquery-public-data.wikipedia.wikidata` at `2026-10-18T18:45:19.304197+00:00`, with Wikipedia dump `20261001`. The Event root Q140451665 was absent from this snapshot; the latest-available-record fallback is now allowed, but Event discovery/classification is not complete. The existing Event hierarchy, two-distinct-Daniel-entity gate and relation cap rules remain unchanged. Earlier missing-reference audits and source-stop outputs are historical, not active version-comparison requirements. No rematching, source-page re-extraction, geometry policy change, new Event root or new classification is authorized.

Current Entities output: `GG_Data/pipeline/outputs/poc_10k_entities_snapshot_first_20261020`, status `ENTITIES_SNAPSHOT_FIRST`. All 6,077 typed Entity rows remain, covering 4,712 QIDs and 1,356 unchanged synthetic identities. All 4,712 full QID records come from the agreed snapshot, including the 506 cached replacements; zero fallbacks were needed and no new query ran. IDs, broad types, saved matching evidence and importance remain unchanged. No new version-difference report is written. Events, the Relations rebuild/selection, Geography, graph JSON and Agent integration remain pending.

## Latest retrieval test — stopped, 20 October 2026

The user approved the one-property retrieval test. Canada/Q16 with P17 (country), on the main Wikidata query graph, also reached the 45-second read timeout. No response body or property page was accepted; no timeout retry ran. `outputs/poc_10k_event_property_probe_20261020/verification.json` records `VERIFIED_PROPERTY_RETRIEVAL_SOURCE_STOP_ONLY`: the failure receipt, code hashes and five upstream output hashes were checked. The existing importance and paged discovery outputs are unchanged. Accepted full incoming coverage remains 2/9,424 graph/QID requests. Zero new Event rows, capped Relations or final graph were written. The process has ended; further retrieval changes require consultation under the user's stop rule.

`event_property_probe.py` performs this diagnostic only; it does not implement complete property-partition discovery. It verifies the latest scored Entities and prior stop artifacts before requesting data, preserves cache evidence and rejects wrong-property responses. All ranks and inclusion rules are unchanged. Before launch, 57 pipeline tests and Ruff passed. The earlier proposal status below is historical and is superseded by this approved test and verified stop.

## Approved selection rule: Event links uncapped, other links mutual top 20

The user approved direct included-Event/included-Event and Event/Daniel links without a count limit. Each Event must still independently pass the existing two-distinct-Daniel-QID inclusion gate. For non-event/non-event assertions, rank the connected QID by **distinct Daniel source pages times total original Daniel mentions**. Keep an assertion only if it belongs to the top 20 at both endpoints; reverse views share its slot. Some QIDs can retain fewer than 20. Counts and budgets are QID-level, without duplication across types.

See [population S2T section 8](../../docs/SOURCES_TO_ENTITY_DATA_MODEL_S2T.md#non-event-relation-selection--approved-20-october-2026) for evidence and stop requirements. `relation_selection.py` now implements the score and mutual-top-20 selector, with cutoff ties and incomplete Event membership as explicit stops. The existing `relations.py` preserves the historical full D/D source population. Complete Event membership must be established before applying exemptions; no capped output has been produced.

## Current continuation: saved scores and paged Event discovery

**Entity attribute, approved 20 October:** `relation_selection.py --entities <accepted-entities-directory>` also writes a new `entities.json.gz` table version with scalar `importance` and `attributes.importance_basis` (page count, mention count, policy, input SHA-256 and status). Each existing typed row gets its QID-level score. Each separate synthetic identity also scores 1, from one mention on one page; unresolved matching does not prevent counting it. No identity, name, source record or Event importance is changed. The source Entities manifest and all its outputs are verified before enrichment; the new manifest pins both input lineages and output checksums. Use a new output directory; prior tables are immutable.

**Current corrected run:** `outputs/poc_10k_entities_importance_synthetic_scored_20261020`, policy `daniel-mutual-top-20-v1.0.1`. Verification status `VERIFIED_ENTITIES_IMPORTANCE_INCLUDING_SYNTHETICS`: all **6,077 Entity rows scored**, including **1,356 synthetic rows at exactly 1**, zero null scores, 6,068 distinct identities and 9,048 counted mentions. All prior QID scores, original fields and source evidence remain unchanged; input/output hashes pass. The correction includes existing synthetic DATE-error identities, while normalized dates still have no Entity row. Reused synthetic IDs across mentions stop explicitly; similar strings are never merged. **56 tests passed**, Ruff passed. No network request or relation selection ran; Events remain blocked at Canada.

Previous run (superseded because synthetic nulls were incorrect): `outputs/poc_10k_entities_importance_20261020`, status `ENTITIES_IMPORTANCE_ONLY_EVENTS_PENDING`. All **6,077** Entity rows were retained: **4,721** scored typed rows for **4,712** QIDs, and **1,356** synthetic rows with null scores. Its historical `verification.json` is `VERIFIED_ENTITIES_IMPORTANCE_ONLY`; it checked the then-implemented null rule, not the corrected synthetic scoring below. The prior files remain immutable evidence. No network request or selected Relations output was made; the Canada Event-source stop remains open. This stage is not a complete model release or a replacement for hard-coded historical source manifests in existing consumers.

```powershell
python -m GG_Data.pipeline.relation_selection `
  --mentions GG_Data/pipeline/outputs/poc_10k/mentions.json.gz `
  --entities GG_Data/pipeline/outputs/poc_10k_entities_approved `
  --output GG_Data/pipeline/outputs/poc_10k_entities_importance_synthetic_scored_20261020
```

**Execution order, confirmed by the user:** calculate and verify the Daniel-population importance scores first; then retrieve Relations and Event links; then apply the non-event selection after complete Event membership is known. Reuse the saved scores for relation ranking. Scoring needs only Daniel's accepted mentions, not Wikidata relation retrieval. The frozen 10K scores below are complete; relation acquisition remains stopped at the recorded source failure.

**Verified stop:** the first new Canada/Q16 page request also reached the existing 45-second read timeout, before any response body. No paged result or partial data was accepted and no automatic timeout retry ran. The process ended. The two completed incoming result units are reused Africa responses, not successful new pages. Counts remain 4,712 native records, 87,694 outgoing statements, 29,923 cached incoming statements, 2/9,424 graph/QID requests and 75,655 partial reference candidates. Zero Event rows or capped Relations are written.

`verification.json` records `VERIFIED_PAGED_DISCOVERY_SOURCE_STOP_ONLY`: 105 source-body checksums, 14 upstream hashes and 17 preceding candidate output hashes passed; the old 352 MB failed body remains unchanged. The new failed request receipt and `source_exception.json` are saved. The score run has its own `verification.json`, which independently reconstructed all 4,712 scores. A one-property-at-a-time incoming query was proposed as a retrieval test; the user requested an explanation, so that test remains unapproved and unexecuted. Neither the 20-relation cap nor a 5,000-result page removes the server's need to search/sort eligible incoming candidates.

The user instructed implementation and continued execution after approving the two-endpoint rule. Scores were prepared from the verified frozen 10K Mentions input in `outputs/poc_10k_relation_importance_20261020`: **4,712 QIDs**, based on **7,692 original non-DATE matched mentions**. The distinct-page measure uses Daniel's original `raw.Source` page titles, not the separate EN/JA reference inventory. The saved score includes both factors and the original source-page list. `report.json` pins input, code and output hashes; status is `IMPORTANCE_ONLY_EVENTS_PENDING`, with zero capped Relations written. No complete Event population is assumed.

`event_discovery.py --incoming-page-size 5000` continues in `outputs/poc_10k_event_full_discovery_paged_20261020`. The previous complete incoming responses are reused; failed unpaged responses remain intact. New requests use at most 5,000 statements per page, ordered by the original statement URI and continued strictly after the last accepted URI. All pages and the short terminal page are required for each graph/QID; a response-size limit is not an Event count limit. Both official graphs, all direct ranks, the existing cache, five-second pauses and the approved HTTP retry budget remain in effect. Malformed responses, unsorted/overlapping pages, timeouts and other unapproved failures still stop. Consult the run's `report.json` and logs for live status; starting a process does not establish complete discovery.

Verification before launch: **55 pipeline tests passed**, Ruff checks passed, Black formatting applied. Tests cover page continuation/cache reuse/order errors, score counts, mutual endpoint rejection, no refill, uncapped Event/Event and Event/entity links, separate assertion slots, and explicit cutoff-tie/incomplete-Event stops. No new Daniel extraction, matching, entity identity, source or relevance filter was added. Event classification/population, actual capped Relations, Geography and final graph remain pending.

```powershell
python -m GG_Data.pipeline.relation_selection `
  --mentions GG_Data/pipeline/outputs/poc_10k/mentions.json.gz `
  --output GG_Data/pipeline/outputs/poc_10k_relation_importance_20261020

python -m GG_Data.pipeline.event_discovery `
  --source GG_Data/pipeline/outputs/poc_10k_event_seven_saved_fallback_20261020 `
  --mentions GG_Data/pipeline/outputs/poc_10k/mentions.json.gz `
  --saved-entities GG_Data/pipeline/outputs/poc_10k_entities_approved/entities.json.gz `
  --output GG_Data/pipeline/outputs/poc_10k_event_full_discovery_paged_20261020 `
  --store GG_Data/pipeline/outputs/wikidata_current_event_cache `
  --incoming-page-size 5000
```

These directories must be new. Reusing the same cache with a new output directory replays verified pages before requesting the next one; previous outputs are never overwritten.

## Previous: full discovery stopped on incomplete Canada response

The new run stopped under the user's first-exception rule. After both Q15
(Africa) incoming graph searches completed, the main-graph Q16 (Canada) request
returned HTTP 200 with **352,032,025 bytes**, ending inside a result with a
`java.util.concurrent.TimeoutException` stack trace. JSON parsing failed. The
entire original response/checksum is cached; no partial rows were accepted and
no automatic malformed-response retry or new query design was attempted.

Verified status: `VERIFIED_FULL_DISCOVERY_SOURCE_STOP_ONLY`. All 4,712 outgoing
records were reused (4,705 current and 7 approved saved records). Two of 9,424
required incoming graph/QID requests completed, containing 29,923 statements.
The partial union has 75,655 distinct reference QIDs; this is not an Event
count or complete candidate population. Source verification reconstructed that
union, checked 105 response receipts, all 17 preceding candidate output hashes
and all 14 upstream hashes. Zero Event rows were written; no process remains
running for this continuation.

Evidence: this run's `report.json`, `source_exception.json`,
`candidate_qids.json` and `verification.json`. The proposed recovery, awaiting
user approval, is incoming pages of at most 5,000 statements, ordered by native
statement identity and continued from the last identity. Both graphs and a
complete page chain remain required. No incomplete page would establish a
negative result. This changes retrieval size only and is not implemented or
approved at this checkpoint. The user was consulted before any new retrieval.

## Full-population direct-candidate acquisition

The user approved extending discovery to all 4,712 matched Daniel QIDs.
`event_discovery.py` reuses the accepted native records for outgoing statements
and the existing single-Daniel-QID incoming query on both official Wikidata
query graphs. Source adapters, five-second request spacing, persistent limited
HTTP retries, size splitting, saved-native fallback and stop rules are reused.
No Event/type/date filter, matching change or new Daniel identity is introduced.

Run: `outputs/poc_10k_event_full_discovery_20261020`. All 4,712 outgoing records
were read from the cache, including the same seven approved saved fallbacks:
87,694 item-valued statements lead to 46,094 distinct reference QIDs. Incoming
requests then started, with 9,424 graph/QID requests required before cache reuse.
`report.json` records live counts, source receipts and any first exception;
`candidate_qids.json` is a partial reference inventory, not included Events.
Complete acquisition must precede the non-deprecated Event hierarchy and the
two-distinct-Daniel-QID gate. No model Event rows have been written.

Tests: 50 passed before launch; the strengthened incoming-direction test also
passed after launch. The preceding seven-candidate outputs remain immutable.

```powershell
python -m GG_Data.pipeline.event_discovery `
  --source GG_Data/pipeline/outputs/poc_10k_event_seven_saved_fallback_20261020 `
  --mentions GG_Data/pipeline/outputs/poc_10k/mentions.json.gz `
  --saved-entities GG_Data/pipeline/outputs/poc_10k_entities_approved/entities.json.gz `
  --output GG_Data/pipeline/outputs/poc_10k_event_full_discovery_20261020 `
  --store GG_Data/pipeline/outputs/wikidata_current_event_cache
```

## Previous: seven-candidate eligibility check verified

`outputs/poc_10k_event_seven_saved_fallback_20261020/verification.json` records
`VERIFIED_SEVEN_CANDIDATE_ELIGIBILITY_ONLY`. All **4,712 Daniel QIDs** were
checked: **4,705 current native records and 7 approved saved native records**.
The check reconstructed both directions from cached full statements, verified
109 response checksums and all 14 accepted upstream output hashes, and found
414 qualifying native assertions with zero exact-exclusion hits. The assertion
ranks are 412 normal, 1 preferred and 1 deprecated; deprecated direct Relations
remain allowed. Only Event-classification P31/P279 traversal excludes deprecated
statements. No mapping changes or matching changes were made.

| Candidate | QID | Distinct Daniel QIDs | Qualifying assertions | Two-entity gate |
|---|---|---:|---:|---|
| World War II | Q362 | 363 | 398 | Pass |
| Minoan eruption | Q1144693 | 1 | 1 | Below minimum |
| Call of Duty: Advanced Warfare | Q16743064 | 7 | 7 | Pass |
| Raid on Santorini | Q20981909 | 2 | 2 | Pass |
| WikiProject Kerala | Q21830247 | 4 | 4 | Pass |
| DTIS 2014, Santorini | Q106336167 | 1 | 1 | Below minimum |
| 2025 Santorini earthquakes | Q132129067 | 1 | 1 | Below minimum |

These are the seven candidates from the earlier five-seed hierarchy probe,
not exhaustive Event discovery for the full 10K sample. The video game and
WikiProject pass the existing broad-root/direct-link rules; no unapproved
historical, military, date or type filter was applied. Zero Event rows were
written. Full Event discovery, Event/Relations population, Geography and final
graph/Agent integration remain pending.

The seven current-missing fallbacks are explicit in `saved_fallback_audit.json`:

| Original QID | Saved native label | Saved modification date (UTC) |
|---|---|---|
| Q31545924 | Clark Airbase | 2019-09-27 |
| Q66477411 | Italy | 2025-02-11 |
| Q108529126 | ArtStation Pro account | 2025-05-09 |
| Q109826916 | Daniel | 2025-03-31 |
| Q123304318 | First Sino-Japanese War | 2023-12-18 |
| Q126035783 | Elliott | 2025-02-05 |
| Q132201733 | Spartans | 2025-03-17 |

These labels describe already accepted saved records; they do not establish
matching accuracy or the reason for the current missing marker. Original QIDs
and Daniel assignments remain unchanged. The audit retains full timestamps,
native revisions, source checksums and affected frozen-mention counts. Raw
current missing responses and oversized parent responses remain intact.

Tests: **48 passed**. Code/docs are locally checkpointed; ignored caches and
outputs are not backed up on GitHub.

## Approved saved-record fallback for missing current IDs

The user approved using accepted saved native Wikidata records when the current
API explicitly marks the same QID missing. The original QID remains unchanged.
`events.saved_native_records` verifies the pinned Entities manifest and file
checksum, preserves the native revision/date, and stops if the saved record is
absent or conflicting. Omitted IDs, redirects and other malformed records still
stop. Raw missing-current responses remain cached. Source reports explicitly
identify every older fallback; any resulting link carries that lineage too.

Continuation: `outputs/poc_10k_event_seven_saved_fallback_20261020`, with
`--saved-entities outputs/poc_10k_entities_approved/entities.json.gz`. Tests:
48 passed before launch. Final coverage and eligibility are verified above.
This is still the seven-candidate check only.

## Previous: missing native QID stopped the split run

`outputs/poc_10k_event_seven_native_split_20261020` stopped after checking
**3,406 of 4,712 Daniel QIDs**. The next complete 50-ID response contains
`{"id":"Q31545924","missing":""}`. The current-record validation stopped the
batch; its other records were not accepted. This is not a size or retry error.
No further acquisition, rematching, ID replacement or Event population followed.

The frozen sample has one mention for this QID: **Clark Airbase**, LOC, source
page **Manila**. The accepted Entities output contains its older native Wikidata
record, revision **1021165461**, modified **2019-09-27T16:40:15Z**. Its supplied
claim properties are P2044, P1566, P625, P17, P31 and P131. The current API's
missing marker alone does not establish deletion, redirect or extraction error.

All seven candidate records remain checked, but complete incoming coverage and
final seven-candidate eligibility remain pending. Zero Event rows were written.
All accepted upstream output hashes remain unchanged. See `source_exception.json`
and `verification.json`. Proposed for discussion: when the current API marks an
ID missing, use its already accepted saved native record, retain its original
QID and record the old revision/date and missing-current evidence explicitly;
stop if no saved native record exists. This fallback is not yet approved or
implemented at that stop. It was subsequently approved as recorded above.
No replacement entity is proposed.

## Approved response-size splitting

The user approved splitting only oversized responses into halves until each
batch returns every requested record. `events._current_batch` recognizes the
explicit API size-truncation warning; all original responses remain cached.
Partial parents contribute no records. Successful children record their parent
cache keys/checksums. A one-ID truncation, any different warning, omitted ID,
redirect, malformed response or unapproved service failure still stops.
All source, rank, mapping and inclusion rules remain unchanged.

Run: `outputs/poc_10k_event_seven_native_split_20261020`. Its `report.json`
records progress; completion requires `verification.json` and the final status.
The split recovered the first 50-ID batch through two complete 25-ID responses;
the following batches were complete until the missing-QID stop above. Tests:
47 passed before launch. This checks the same seven candidates against
4,712 distinct Daniel QIDs, not full candidate discovery or Event population.

## Previous: approved native batch stopped at response-size limit

The user approved current Wikidata `wbgetentities` records in batches of up to
50 Daniel QIDs, followed by local direct-statement checks. The adapter reuses
verified single-record cache entries first, requests full native records with
`redirects=no`, and requires the exact requested population before accepting a
batch. It uses the existing cache and approved HTTP retry budget.

`outputs/poc_10k_event_seven_native_batches_20261020` reused all seven candidate
records and six Daniel records. Its first new 50-QID API request returned HTTP
200 with valid JSON, but only **42 of 50 records** and an explicit truncation
warning: the result exceeded the API's stated **12,582,912-byte limit**. The
received body is 28,842,454 bytes; its original bytes, checksum and request are
cached. Missing requested IDs: Q408, Q538, Q552, Q584, Q652, Q664, Q668, Q685.
No partial batch was accepted, no automatic retry or smaller batch was made,
and no complete incoming coverage or Event eligibility result is claimed.

The run stopped under the user's data/service exception rule. Six of 4,712
Daniel native records were checked; zero Event rows were written. Accepted
upstream outputs remain unchanged. See `acquisition_stop.json` and
`verification.json`. Proposed for consultation: split only truncated batches
into halves until each response is complete; stop if a one-QID request is still
truncated. Keep full records and the same source, ranks and inclusion rules.
This response-size handling was subsequently approved and implemented; see above.

## Previous: bounded incoming check stopped at query-service timeout

The user subsequently agreed to the smaller-query design. The same seven
native candidates are checked against all 4,712 distinct Daniel QIDs, with
19 subject batches of at most 250 and both official query graphs: 38 requests.
All source ranks, assertion exclusions, catalog mappings, and the two-distinct-
Daniel-QID minimum stay unchanged. The incomplete old response stays immutable.
The run `outputs/poc_10k_event_seven_bounded_20261020` stopped on its first main-
graph request after a 45-second read timeout. Seven native records were reused;
zero incoming requests completed. No automatic timeout retry or source change
was made. The failed request metadata and exact bounded query are preserved;
no response body was received. The previous outgoing lower bounds still apply.
This is still seven-candidate eligibility, not full discovery or populated Events.

The subsequent proposal was to retrieve Daniel's current native Wikidata records by
explicit QIDs through `wbgetentities`, at most 50 IDs per request (about 95
requests before cache reuse), then inspect complete direct statements locally.
This avoids query-service search and retains the same source, all ranks and
endpoint/inclusion rules. This method was then approved and run; see the current
response-size stop above.
Official limit: <https://www.wikidata.org/w/api.php?action=help&modules=wbgetentities>.

## Seven native candidates checked; incoming query stopped

The user approved finishing all seven checks under the current rules, including
the video-game candidate. No new type, date, or Event-root filter is authorized.
All seven native records and their supplied P31 paths were checked in
`outputs/poc_10k_event_seven_eligibility_resumed_20261020`. The direct-link
population is the frozen sample's **4,712 distinct matched Daniel QIDs**, based
on original non-DATE mentions; resolved type does not remove a matched QID.

Outgoing full-native statements passed exact exclusions and catalog v2.1.2.
These are lower bounds until incoming acquisition finishes:

| Candidate | QID | Distinct Daniel QIDs in outgoing statements |
|---|---|---:|
| World War II | Q362 | 37 |
| Minoan eruption | Q1144693 | 1 |
| Call of Duty: Advanced Warfare | Q16743064 | 7 |
| Raid on Santorini | Q20981909 | 2 |
| WikiProject Kerala | Q21830247 | 0 |
| DTIS 2014 conference, Santorini | Q106336167 | 1 |
| 2025 Santorini earthquakes | Q132129067 | 1 |

Three candidates already prove the minimum of two through outgoing assertions;
the other four are **pending**, not rejected. The World War II incoming request
returned HTTP 200 with **34,406,400 bytes of incomplete JSON**. The complete
received bytes, checksum, request and parse exception are cached; no partial
JSON rows were accepted. No automatic retry applies to malformed HTTP-200 data.
Acquisition stopped under the user's stop rule. Zero incoming queries completed
and zero complete two-direction link checks are claimed. Both query-service
graphs still require coverage. Full incoming native statements, Event model
rows, Event Relations, and final graph remain unpopulated.

Supporting files: `outgoing_check.json`, `report.json`, and `verification.json`.
All accepted upstream output hashes passed. The earlier local stop left one
verified empty cache directory; only that empty directory was removed, with
evidence in the first `poc_10k_event_seven_eligibility_20261020` run. No saved
response was deleted or overwritten. The user was asked to approve smaller
incoming queries with up to 250 Daniel subjects and all seven Event targets:
38 requests across the two graphs, without changing source or counting rules.
The user selected "Discuss first"; no bounded incoming query has been executed.

### Previous rank approval and native inspection stop

The user approved ignoring deprecated P31/P279 statements for Event
classification only. `events.classify_events` filters a separate view and
re-traverses it, so alternative normal/preferred paths remain available. Raw
acquisition and all Relations ranks are unchanged. Unknown hierarchy ranks
remain explicit source exceptions.

`outputs/poc_10k_event_seven_native_check_20261020` contains the new approved
classifications and four complete cached native records: Q362 (World War II),
Q1144693 (Minoan eruption), Q16743064 (Call of Duty: Advanced Warfare), and
Q20981909 (Raid on Santorini). The video game reaches the approved Event root
through normal-rank statements. Inspection therefore stopped for consultation;
the fourth response had already been saved. No special exclusion was applied.
Three native candidates and all seven two-distinct-Daniel-QID gates remain
pending. No Event rows, Event relations, or graph were created.

The user was asked whether to finish these checks under the approved rules or
discuss narrower scope first. Historical probes/diagnostics remain immutable.
Code/docs receive local checkpoints only; ignored outputs/cache are not backed
up by Git.

### Historical completed source probe and diagnostic

The 429 retry succeeded on attempt 2. The complete five-QID source traversal
saved 165 candidate P31 checks and 904 P279 class checks, with 120 successful
hierarchy-stage requests (27 added after the 429 stop). Verification checked
132 source-body hashes and unchanged upstream files/old failed attempts.
No request is running. This is not full 10K Event discovery.

The all-rank hierarchy returned 117 positive candidates and 48 negative ones.
Countries Q30 (United States), Q668 (India), and Q41 (Greece) reach the Event
root through a deprecated P279 statement on Q123349660 pointing to Q1190554.
Full paths and statement/rank evidence are saved in `source_surprise.json` in
`outputs/poc_10k_current_event_rate_limit_retry_20261020`.
Population stopped before writing Event rows; no country was accepted.

The user approved a diagnostic-only test without deprecated P31/P279 links.
`event_hierarchy_rank_test.py` reuses saved data with no network calls or source
mutations. `outputs/poc_10k_event_rank_test_20261020/report.json` records
117 all-rank positives versus 7 non-deprecated positives, removing 110 flags
including all three country examples. Remaining candidates: Q362, Q1144693,
Q16743064, Q20981909, Q21830247, Q106336167, Q132129067.

The user subsequently approved this Event classification filter. The seven candidates
still need the two-distinct-Daniel-QID gate and full native evidence. Relations
retains all ranks. Original sources/classifications, matching, Entities and Wiki
Pages remain unchanged. Zero Event rows or final graph were written.

## Approved service-error handling — 20 October 2026

The user approved the general cache-first retrieval policy and the previously
proposed HTTP 429 handling. This supersedes the pending 429 decision in the
historical checkpoint below. Reuse verified saved data first; use agreed
BigQuery data where it supports the required scope, and approved current
Wikidata for Event data absent from that copy. No automatic source or business
rule substitution is introduced.

`events.cached_json` permits **three total attempts per exact request**, shared
across connection failures, HTTP 429/502/503/504 and restarts. Minimum backoff is 10 seconds
before attempt 2 and 30 seconds before attempt 3. Respect `Retry-After` seconds
from response receipt or an absolute HTTP date if later. A saved cooldown keeps
its original deadline. New network requests pause five seconds; retry waits
use short observable intervals. Original response bytes/metadata stay immutable;
new attempts append under the same request cache. Successful cache hits make
no network request. Exhaustion, read/connect timeouts, TLS validation errors, other HTTP/API errors, malformed data,
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

## Current Events source approval — 20 October 2026

The user approved current Wikidata for Events and their direct Daniel links,
with retrieval caching. This resolves the source decision recorded in the
historical BigQuery-root stop below; it does not establish Event completion.
Live Q140451665 evidence and unchanged current BigQuery table metadata are in
`outputs/poc_10k_event_root_live_check_20261020`.

`events.py` provides a checksum-checked raw-response cache and a direct-link
discovery query. It preserves full-statement ranks in discovery (p:/ps:, not
truthy wdt:), both directions and the approved native hierarchy. Connection failures and HTTP 429/502/503/504 permit three total attempts under the cooldown and
five-second request policy above. Saved failures count toward the same budget;
other failures stop. This adapter does not select/populate Events, replace
upstream sources, or rematch Daniel mentions. Query-service graph scope and
full native-record evidence still need verification before Event completion.

The first live source check passed: WDQS returns the root's native P31 statement
and Q23958852 class. The next request, for five sample QIDs with direct links
and hierarchy in one query, reached the client's 45-second read timeout. The
run stopped immediately without retries. Evidence is in
`outputs/poc_10k_current_event_probe_20261020/probe.json`, status
`BLOCKED_CURRENT_EVENT_REQUEST`, and `outputs/wikidata_current_event_cache`.
The query file and failed request metadata are retained; there is no response
body to cache for a read timeout. Zero Event model rows were written; discovery
coverage has not been established. The five QIDs are Q1771928, Q10903802,
Q129296, Q58425060 and Q101206527, selected with seed 20261018 from the numerically
sorted 4,712 accepted QIDs. The next proposed implementation separates direct
link retrieval from cached hierarchy checks, retaining exactly the same rules;
discussion is required before another acquisition attempt under the user's
stop-on-problem instruction.

The user subsequently approved the smaller-request approach. The next probe
reads complete native records for outgoing links and requests incoming links
one Daniel QID at a time, before the separate unchanged hierarchy check.
`events.incoming_query` replaces the earlier combined-query builder; the failed
historical query file stays immutable. Candidate neighbors remain supporting
reference data, not new Daniel entities or accepted Event rows.

### Smaller-request probe: saved progress, then HTTP 502

`outputs/poc_10k_current_event_small_requests_20261020/probe.json` completed
the five-QID direct-link check: 53 outgoing and 146 incoming statements across
165 distinct candidate neighbors. The separate scholarly graph added no incoming
links for those five QIDs. Full current native records are cached for all five.
These are reference candidates only; no additional Daniel entities were created.

`outputs/poc_10k_current_event_hierarchy_probe_20261020/probe.json` then saved
P31 checks for all 165 candidates and P279 checks for 344 distinct classes.
The next ten-class request returned HTTP 502; status is
`BLOCKED_HIERARCHY_PROBE`. The run stopped without retry. Both successful JSON
responses and the failed HTML response/request metadata remain cached. The
partial hierarchy, query files and counts persist for reuse. No negative Event
classification, inclusion count or Event-model completion follows from this
partial traversal. No Event rows or final graph were written.

Initially the user approved limited retries on 20 October 2026: exactly three total
attempts for HTTP 502/503/504, with waits of 10 and 30 seconds. `events.py`
implements this policy. Existing failed responses count as attempts; retries
append `attempt_2`/`attempt_3` without overwriting the original evidence.
Successful cache entries are checksum checked and reused. Exhaustion persists
across restarts. Timeouts, 429, API errors, malformed data, redirects and
business/data exceptions still stop immediately. No source substitution occurs.

`event_hierarchy_probe.py` resumes the saved five-QID hierarchy check in a new
output directory, validates the old files/source checksums, and retries the exact
interrupted query first. The old run remains immutable. Its output is source
classification evidence only, not a complete 10K Events population.

Contract order: [population S2T](../../docs/SOURCES_TO_ENTITY_DATA_MODEL_S2T.md),
[ERD](../../docs/ENTITY_DATA_MODEL_ERD.md), then
[model-to-graph S2T](../../docs/ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md).

## Implemented first step

`poc.py` selects 10,000 original row positions without replacement (fixed seed
20261018), verifies pinned input and matching artifacts, and copies unchanged
saved matching decisions into Mentions. It retains resolved English/Japanese
Wiki Pages and failed page requests. Original text is evidence only; no text
extraction, rematching, splitting, combining, network request, or new identity
is performed. Synthetic rows retain their original IDs and use Daniel's type
when the saved resolved type is null. Saved type metadata stays unchanged.

Any unexpected count, field, source hash, ID, score, page conflict or missing
artifact raises an error. Stop and discuss the exact case with the user before
changing a rule. No automatic data repair is implemented. Only the approved
connection-failure and HTTP 429/502/503/504 retry policy above is an operational exception.

**Output on D: was approved on 20 October 2026.** Step 1 ran successfully in
`outputs/poc_10k`. Do not rerun into that directory; existing output is protected.
The original invocation was:

```powershell
C:\Users\User\anaconda3\python.exe -B -m GG_Data.pipeline.poc --output D:\Projects\GeoAI\GG_Data\pipeline\outputs\poc_10k --output-approved
```

The output directory must be new; existing output is never overwritten. The
manifest marks only `STEP_1_ONLY`. Partial files without that manifest are not
a completed step. Its marker covers Mentions and Wiki Pages only. The separate
Entities step establishes membership for Wiki Pages `about_entity_id`. Events,
Relations, Geography, final graph export and Agent integration remain pending.
This is not a six-table release, a fresh matching run or a completed 10K POC.

### Verified first-run results — 20 October 2026

The run reused the completed matching decisions; these are sample counts, not
new matches or an accuracy estimate. The 10,000 sampled source positions are
recorded in `outputs/poc_10k/manifest.json`.

| Saved outcome | Mentions |
|---|---:|
| Page/direct Wikidata match | 7,429 |
| Already-matched pool | 215 |
| Fresh WWII pool | 48 |
| Normalized date | 952 |
| Existing unresolved synthetic ID | 1,356 |
| **Total** | **10,000** |

There are 7,692 QID-assigned mentions covering 4,712 distinct QIDs. The 1,356
synthetic mentions comprise 813 name-threshold failures, 175 type mismatches,
78 unknown types and 290 invalid/unsupported date values. These are preserved
baseline outcomes, not new failures introduced by table population.

The sample covers 419 source requests: 415 resolved and the four already-known
missing requests. Those four account for 29 mentions with null page keys.
Resolved requests deduplicate to 691 Wiki Pages rows: 404 English and 287
Japanese. Request counts and distinct page counts have different denominators.

Verification passed: every output hash, exact original raw rows and sampled
positions, unique mention/page keys, page foreign keys, distinct per-mention
synthetic IDs and separate NER/match scores. Output size is 23,087,187 bytes.
No new input or matching exception was raised. The completion marker remains
`STEP_1_ONLY`; later stages above have not run.

Resolution-manifest SHA-256:
`86e60c17a99d1aaecbd87dbda7c7d69a0dee8c41cd15d30c3393b13d164d2db4`.
Outputs are ignored data artifacts on D:, not protected by a code commit.

## Entities step

`entities.py` consumes the completed first step, without changing its files.
It populates one row per existing `(entity_id, entity_type)` pair and connects
Wiki Pages subjects only where an entity already exists. Normalized dates stay
in Mentions. There is no new extraction, rematching or type inference.

The user approved **newer saved Wikidata names** on 20 October 2026. English
still precedes Japanese, then Daniel's name. When saved labels differ, revision
IDs determine the newer supplied label; both source versions remain in
`raw_reference`. This rule changes display names only. Equal-revision conflicts,
missing revision evidence needed for a choice, and ambiguous Daniel fallbacks
stop the run before model output. For the two pinned cases Q132537 and Q1771928,
the user also approved older English labels where newer full records contain
only Japanese. Each selected name records `2026-10-20_KEEP_OLDER_ENGLISH`. Other
such missing-label cases still stop for discussion (population S2T section 6).

Complete native envelopes are reused from the verified saved archive. Missing
full records are retrieved as the complete BigQuery `item` field through the
existing GCP CLI wrapper and pinned matching snapshot. SQL, dry-run evidence,
job statistics and untouched results are cached in `outputs/wikidata_full_cache`.
The compact matching metadata remains separate evidence; it is not a complete
claims source. Labels, descriptions, native claims and unknown fields are
retained. Compact search names have unknown original kind/language and are
marked `matching_reference_name`, rather than presented as native aliases.

```powershell
C:\Users\User\anaconda3\python.exe -B -m GG_Data.pipeline.entities --output D:\Projects\GeoAI\GG_Data\pipeline\outputs\poc_10k_entities_approved
```

The destination must be new. `ENTITIES_STEP_ONLY` is written last, after source
and population checks; it does not mark Events, Relations, Geography, graph
export or Agent integration complete. Failed runs can retain acquisition cache
files for reuse, but do not produce a completed Entities manifest.

### First Entities attempt — stopped in final validation

The attempt created 6,077 candidate rows: 4,721 QID/type pairs (4,712 distinct
QIDs) and the unchanged 1,356 synthetic identities. All full Wikidata records
are available: 506 reused envelopes and 4,206 complete `item` records acquired
from the pinned BigQuery snapshot. The CLI verified 4,206 returned rows; query
job `geoai_1c8841ce530789458d059e9f8b92254f` billed 1,561,930,498,048 bytes.
Its result is cached; correcting names does not require another query.

Output hashes, exact ID/type membership, raw reference IDs and source hashes,
mention foreign keys, synthetic names/types, and unchanged first-step files
passed checks. The copied Wiki Pages view has 197 existing entity subjects;
its other values are unchanged. This structural validation does not establish
identity accuracy or approval of every display-name choice.

Final inspection found two cases not covered by the approved version rule:
Q132537 (`Robert Oppenheimer`) and Q1771928 (`Why We Fight`) have older English
labels, but their newer full records have Japanese labels and no English label.
The attempt used older English. Work stopped for a user decision between older
English priority and newer-record Japanese fallback. The code raises on
unapproved cases instead of choosing. The user subsequently approved the older
English labels for these two exact saved name/revision combinations. See
population S2T section 6 for values and revisions.

`outputs/poc_10k_entities/manifest.json` is now
`BLOCKED_NAME_LANGUAGE_VERSION_RULE`, with `entity_output_state=DRAFT_NOT_ACCEPTED`.
The original attempt marker is retained as `attempt_manifest.json` for audit;
it is superseded by the current manifest and is not a release marker. No later
stage was included in that attempt. The first-step output remains valid and
unchanged. The blocked attempt is retained for audit; the approved rerun uses
a separate destination and reuses the full-record cache.

### Approved Entities rerun — 20 October 2026

The user approved the two older English names. The separate rerun in
`outputs/poc_10k_entities_approved` completed as `ENTITIES_STEP_ONLY` and passed
`validation_report.json`: **6,077 Entities rows**, comprising **4,721 QID/type
pairs across 4,712 QIDs**, plus **1,356 unchanged synthetic IDs**. All 691 Wiki
Pages remain; 197 subjects reference existing sample entities.

The run reused the 506 archive records and 4,206 cached BigQuery records.
The BigQuery CLI method was blocked during replay and its call count was zero;
no new query was made. Every first-step/output/source-file hash, entity key,
mention reference, native ID and preserved type passed checks. Relative to the
draft candidate rows, only approval metadata for the two name selections
changed. Q137378 still uses the newer `rōmusha` label. The in-memory suite has
19 passing tests; Ruff checks passed. Accepted manifest SHA-256:
`a4b967188c7247996309e53dba9851208d8d8e1e69c21d79f7afb1cc35c252e4`.

### Historical relation stop and approved native mapping rule

A cache-only check of Daniel-QID/Daniel-QID statements stopped at its first
missing mapping, after 191 eligible non-excluded statements had been checked.
This is a partial check, not a total of all sample assertions or missing keys.
The v2.1.0 catalog had no `(Wikidata, wd:P2341)` entry. The exact case is
`Q105969841` (Poles) -> `Q36` (Poland), statement
`Q105969841$8D05BA41-C448-45B5-93EA-A37877F5140D`, normal rank.
Wikidata names P2341 [indigenous to](https://www.wikidata.org/wiki/Property:P2341).

Evidence is in `outputs/poc_10k_relations_preflight/first_exception.json`, with
raw statement, record provenance and catalog/source checksums. Status is
`BLOCKED_RELATION_MAPPING`. This historical report remains unchanged. No
Relations/Events/Geography/graph output was generated by that check.

On 20 October 2026, the user approved the general rule in population S2T
section 8: existing mappings take priority. For a missing source mapping, use
an actual direct Wikidata statement between the same included QIDs. Add its
native property unchanged at Level 2 to the mapping parameters; leave Level 1
`UNRESOLVED` / `NOT_ASSIGNED`. Without a source statement, create no relation.
Conflicting mappings still require consultation. No entity extraction or
matching decision changes are authorized by this rule.

[Native parameters](../mapping/ADDITIONAL_NATIVE_RELATION_RULES_2026-10-20.csv)
and [source evidence](../mapping/NATIVE_RELATION_EVIDENCE_2026-10-20.json)
now supply P2341 to the existing catalog builder. The separate
[v2.1.1 mapping](../mapping/RELATION_MAPPING_TABLE_v2.1.1.csv) has 1,596 source
keys. It reuses the existing P2341 Level 2 and reverse definition, so the
1,064 Level 2 definitions and 2,097 direction lookup rows are unchanged in
count. Reusing the historical EventKG definition does not import EventKG facts.

`build_relation_mapping_v2_1.build(native_rules=..., version=..., output=...)`
accepts these supplemental parameters. Native additions require a new version;
use a separate output destination when rebuilding for review. All 27 tests and
2 subtests passed, including byte-for-byte reproduction of the historical
v2.1.0 CSVs. No new query was made. The later source gate and population replay are recorded below; v2.1.1 remains immutable.

### Relations source gate — historical stops resolved

`relations.py` implements the strict source gate for the next stage. It verifies
the accepted Entities manifest, output hashes, original sample lineage and
pinned mapping; it reads full records from Entities without retrieval. Typed
rows are checked once per QID. The 14 guarded exclusions precede mapping;
deprecated ranks remain eligible. After a successful gate, the stage discovers missing native source keys, writes cumulative parameters, builds a separate pinned catalog and populates Daniel/Daniel Relations.

The first real-data check stopped in
`outputs/poc_10k_relations_20261020/first_exception.json`:

- Subject: Joachim von Ribbentrop (`Q101886`).
- Relation: member of political party (`wd:P102`).
- Object: Nazi Party (`Q7320`).
- Statement: `Q101886$6AB5CB76-32AE-412D-A84C-F3B49B990BB6`, normal rank.
- Two P580 start qualifiers: `+1930-00-00T00:00:00Z` (year precision 9)
  and `+1932-05-01T00:00:00Z` (day precision 11).

This source cannot supply one selected start date without a choice. The gate
stopped at this case; it is not an all-sample conflict count. Both native snaks,
their calendars/precision and provenance are retained in the exception and
unchanged Entities. No relation table, new mapping parameters or completed
Relations manifest was written, and no query was made.

Historical policy (superseded for pre-1900-end relations by v1.1.0 below): the user approved `relation-date-selection-v1.0.0`: earliest supplied start from 1900; if all starts precede 1900, derived year 1900 (precision 9); latest end. Exclude a relation whose latest end precedes 1900, preserving the raw record and reason. Missing dates stay missing. Point-date conflicts and remaining reversed intervals still require consultation. This policy does not select Event dates. See population S2T section 8.

The next Prague source case (1804-1867) is resolved by the pre-1900 end exclusion. An overstrict P53 mapping guard was also corrected to honor the existing native-retention decision; no catalog rule changed. Historical exception directories remain unchanged.

Replay `outputs/poc_10k_relations_date_scope_check_20261020` passed the source gate: 4,712 QIDs; 213,277 raw claims; 10,501 in-scope statements; 34 pre-1900-end exclusions; 10,467 retained statements (10,053 normal, 363 preferred, 51 deprecated). Retained time statuses: 9,349 NONE, 662 PARTIAL, 451 DIRECT, 5 MULTIPLE. Status is `DANIEL_RELATIONS_SOURCE_CHECK_ONLY`. No populated Relations, event acquisition or graph exists from this check. No new query occurred.

Focused tests cover preserved raw statements, typed-row deduplication, all ranks, native-retention mapping guards, date selection/floor/precision, pre-1900-end exclusion (including negative years), latest-end and missing-end behavior.

### Daniel/Daniel Relations checkpoint — 20 October 2026

`outputs/poc_10k_relations_labels_preserved_20261020/manifest.json` passed with status `DANIEL_RELATIONS_ONLY`:

- 10,467 unique base statements between the 4,712 matched Daniel QIDs. All endpoints are existing QIDs; typed rows do not multiply statements. No mention, matching decision or entity ID changes.
- 34 statements excluded because their latest supplied end precedes 1900. Complete statements and reasons are saved in `excluded_relations.json.gz`. None of this sample's statements matched the 14 exact guarded exclusions.
- 86 visible temporal-decision audit rows: multiple supplied values and/or derived year-1900 starts. Every raw snak, precision/calendar and selected-value rule is retained.
- Nine missing native source keys: P500, P1533, P3113, P4777, P4913, P5236, P6271, P6875 and P10888. Native IDs/direction are kept; Level 1 remains unassigned. Cumulative parameters and mapping/direction CSVs are in the run's `mapping` directory.
- POC catalog `relation-map-v2.1.2`: 1,605 source mapping rows, 1,073 Level 2 definitions, 2,113 direction lookup rows. Historical v2.1.0/v2.1.1 catalogs stay unchanged. This POC version belongs to the pinned sample, not a full-data catalog promotion.
- Nine property records were retrieved and cached from the agreed BigQuery snapshot after explicit approval. Job `geoai_adeea068751b49a1e703140f545621af` billed 1,112,539,136 bytes. Cache: `outputs/wikidata_property_cache`; SQL, dry run, job statistics and full native records persist there. The successful replay reused this query cache.
- The builder initially proposed replacing P8138's reverse label with the newly available P10888 name. The user chose to keep the existing label. Catalog extensions now reuse the prior labels and label-source definitions. The native name remains evidence. Historical blocked outputs have no completed Relations manifest and are not releases.

`relations.json.gz` keeps all ERD Relations fields, 26 legacy compatibility fields, raw native statements, complete applied mapping and retrieval evidence. Unavailable legacy review/classification values are null; no truth review is claimed. Source graph is absent rather than invented from a provider URL. Stable assertion IDs reuse notebook Process 3 with original endpoints, statement ID and raw dates. Forward/reverse copies belong to graph export; this table has one base assertion row.

Verification includes original sample/Entities hashes, scope accounting, raw preservation, unique IDs, single direction normalization, reverse involution and JSON readback. Focused fixture checks cover native-label preservation and assertion identity across mapping changes. A final replay with current code/contracts uses a new directory `outputs/poc_10k_relations_final_20261020`; its manifest, when present, is the current checkpoint. No manifest means no completed replay.

This is the Daniel/Daniel part only. Event discovery, included-event links in Relations, Geography, final graph and Agent integration remain pending. No new entity is extracted, split, combined or inferred. Code/docs have local checkpoints only; ignored data and caches are not protected by Git.

Final replay verification passed on 20 October: `outputs/poc_10k_relations_final_20261020/manifest.json` has status `DANIEL_RELATIONS_ONLY`. All input, mapping and output hashes passed; the 10,467 Relations, 34 exclusions and 86 temporal audit rows have identical semantic content to the previous successful run. The property cache still contains one query; the replay made no property retrieval.

### Events stopped: approved root absent from the pinned source

Before event discovery, the approved root `Q140451665` was requested through the existing full-record adapter at the same BigQuery snapshot (`2026-10-18T18:45:19.304197+00:00`). Job `geoai_6d050ce4cff5a35c6380e995468a4bfe` returned zero rows and billed zero bytes. This establishes root absence from that snapshot, not absence of events or absence of the item from current Wikidata. No hierarchy traversal, event inclusion, source substitution or root substitution was performed.

The SQL, dry run, empty result and job statistics are cached in `outputs/wikidata_event_cache`. The explicit stop is `outputs/poc_10k_event_root_check_20261020/root_check.json`, status `BLOCKED_EVENT_ROOT_CHECK`. The user was asked whether to check a newer Wikidata snapshot for the same root/hierarchy. That decision remains pending; completed Relations and upstream outputs remain unchanged. No Events or final graph output exists from this check.

Reproduce with the existing saved sources and property cache:

```powershell
C:\Users\User\anaconda3\python.exe -B -m GG_Data.pipeline.relations --output D:\Projects\GeoAI\GG_Data\pipeline\outputs\new_relations_replay
```

## Approved graph interfaces

`graph_contract.py` provides small interface helpers:

- Distinct QID/type nodes use `QID::type`, keeping `wikidata_id` separately.
  Existing per-mention synthetic IDs stay unchanged.
- A QID endpoint index returns all its separate typed node IDs. Relations and
  source assertion counts are not expanded across these nodes.
- `geometry_ref` is null or `{file, place_id, sha256}`. The referenced GeoParquet
  must contain exactly one valid nonempty geometry for the place and known CRS.
  `load_geometry(pointer, artifact_root)` returns its Shapely object. Broken
  pointers fail explicitly. No GeoJSON conversion or CRS transformation occurs.

These helpers are not yet connected to the current Agent engine. Its full query
path and spatial CRS requirements must be verified before graph acceptance.

Run the in-memory checks (no Daniel data output):

```powershell
C:\Users\User\anaconda3\python.exe -B -m pytest -q -p no:cacheprovider GG_Data/pipeline/test_pipeline.py
```

## Current correction: retain original historical dates

The user correction supersedes the pre-1900-end exclusion. Policy `relation-date-selection-v1.1.0` retains relations whose latest end precedes 1900, with original supplied dates, precision/calendar and no start-year floor. Missing starts stay missing. Other Relations date rules and the 14 exact assertion exclusions remain unchanged; see population S2T section 8. The 34 earlier exclusions are historical output, not the current rule. A new immutable replay uses `outputs/poc_10k_relations_original_historical_dates_20261020`; only a successful manifest establishes completion. Events remain blocked at the previously recorded root check.

The corrected replay passed with status `DANIEL_RELATIONS_ONLY`: 10,501 base Relations, 34 historical statements retained with original dates, zero excluded statements in this sample, and 120 temporal audit rows. All 34 restored statement IDs, raw qualifiers, exact start/end values, precision and missing dates match their source evidence; none received a derived 1900 start. The earlier 10,467 rows are unchanged except explicit policy metadata. All recorded input/mapping/output hashes passed, as did 28 focused tests and Ruff. The property query cache remains one query; no new query or matching run was needed. Example: Prague statement `Q1085$0697567f-4a18-22cf-3118-7f7622ccf2f5` is retained with `+1804-08-11T00:00:00Z` through `+1867-03-29T00:00:00Z`.
