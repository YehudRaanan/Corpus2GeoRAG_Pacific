# Source-to-target: approved sources to the six-table data model

**Synthetic LOC approval - 21 October 2026:** all existing LOC identities enter Geography, including unresolved SYN IDs. QIDs use exact-ID lookup first; SYN IDs use the existing name/alias/date/type/context fallback and keep their original IDs. Supported geometry does not create a Wikidata match. Ambiguous candidates remain unresolved. `Geography.geometry_ref.place_id` can therefore be an existing QID or SYN ID; the reference stays in the model, not graph JSON. This extends target coverage under the existing source and acceptance policy.

**Geometry pointer correction - 21 October 2026:** `Geography.geometry_ref` belongs to the data model, not final graph JSON. It retains the approved `{file, place_id, sha256}` format and identifies the saved Shapely/WKB object. The existing loader can read this model reference; Agent access to the model still requires integration verification. Earlier graph-node pointer instructions are superseded. No pointer or inline GeoJSON is exported in graph JSON.

Specification date: 19 October 2026. Status: approved source scope and rules documented; required implementation exceptions remain explicit. This document does not execute acquisition, matching, table population, geocoding, or graph export.

**Target:** [Entities, Mentions, Wiki Pages, Geography, Events, Relations](ENTITY_DATA_MODEL_ERD.md). This is the population S2T. The separate [model-to-Agent graph JSON S2T](ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md) starts after these tables. The ERD dictionaries and exact contract inventories form part of this specification; every input field and nested evidence payload must remain recoverable.

The [full pipeline review](DANIEL_TO_GRAPH_PIPELINE_REVIEW.md) collects open decisions, implementation checks, documentation alignment and deferred improvements from Daniel input through final JSON. It does not change these population rules.

## Current Event rule - maximum restored 21 October 2026

After native recognition and approved assertion mapping/exclusions, include an
Event when it connects directly to at least **two distinct retained Daniel QIDs**
and the **maximum linked-entity relevance is >=2%**, including exactly 2%.
This uses maximum rather than average or minimum across all qualifying linked
entities; it does not restrict an Event to three entities. Each entity still
uses its highest available EN/JA scope-concentration score.

**Missing relevance contributes 0 to this selection.** Preserve its original
missing status and evidence in supporting records; a missing score record is
still an integrity error. All-missing endpoints give an Event score of 0 and
fail. Missing scores do not grant an inclusion exception. The known-score mean
may remain as a diagnostic only. Keep the separate 5% MISC filter, retained
population, source snapshot, hierarchy, assignments and assertion rules fixed.

**Inclusive/wide assumption, subject to improvement:** one highly relevant
linked entity can admit a weakly related Event. The accepted broad hierarchy
and unrestricted mapped predicates can also admit items that are not historical
events. Review of the average-selected output found scientific articles,
Netflix, black hair, modern military exercises and other unrelated items.
Maximum does not solve those problems and can admit more of them. This rule
favours coverage; it does not establish semantic relevance or battle completeness.
Any narrower hierarchy, predicate/date constraint or other improvement requires
separate agreement. No such extra filter is introduced here.

The maximum rule supersedes the average rule and historical missing-score
bypass. The earlier 775-Event average result below is preserved as test evidence,
not the current selection. The new saved-data continuation is
`GG_Data/pipeline/outputs/poc_10k_events_maximum_missing_zero_20261021/`.
No Event model import or final graph export is part of this rule change.

### Verified maximum-rule continuation - 21 October 2026

The retained 10K scope completed in **94.986 seconds**, reusing saved source
records and completed cloud-query results. **2,135 of 21,797 candidates pass**;
**19,662 fail** the maximum threshold. This retains all 775 average-selected
Events and adds 1,360. Of the selected Events, **1,454 have exactly two distinct
retained linked QIDs** and 681 have three or more. Their supporting links contain
**7,286 unique native assertions**. No new source query was needed.

Independent exact-fraction replay reproduced all decisions, endpoint counts,
assertion identities and input/output checksums. The connected selection/query
checks passed **19 tests**, Black, focused Ruff and `git diff --check`.
The 15 saved Pacific battle checks retain **13**: Manila remains below 2%, and
Bismarck Sea still has only one retained qualifying linked entity. This is a
15-case coverage check, not proof that all Pacific battles were acquired.
The deliberately broad assumption and unwanted examples above remain relevant.

Current evidence: `GG_Data/pipeline/outputs/poc_10k_events_maximum_missing_zero_20261021/`:
`report.json`, `decisions.json`, `selected_links.json`, source/mapping records,
`verification.json`, `independent_verification.json`, and `pacific_battles.json`.
That selection-only run wrote no Event model rows or final graph. The later
verified stable-tie population below completes Events and Relations. Code/docs receive a local Git checkpoint;
generated artifacts remain local and ignored by Git.

### Derived range from point dates - approved 21 October 2026

When multiple distinct P585 point dates are supplied and explicit P580/P582
start/end dates are absent, derive start = earliest point date and end = latest
point date. Keep one source assertion and all original point dates, snaks,
precision, calendars and source evidence. Mark both bounds as derived from
P585; the range covers recorded dates and does not assert continuous activity.
Do not overwrite explicit start/end dates. Do not apply the relation 1900 start
floor to this point-derived range. Different calendars, unsupported formats or
other unresolved date conflicts still require consultation. A single point
date stays a point date. This rule applies to Events and Relations; native
Event dates remain lossless lists, with derived bounds marked separately.

For Enola Gay -> significant event -> atomic bombings of Hiroshima and
Nagasaki, the derived range is 6-9 August 1945. This approval resolves the
point-range issue in the historical preflight stop below. Resume with the
same snapshot, selected Event IDs and source assertions. No new matching,
source substitution or Event filter is authorized.

### Non-event period selection - approved 21 October 2026

For the non-event cap, the relevant period is **7 December 1941 through
2 September 1945, inclusive**. At each endpoint, select relations whose dated
interval overlaps this period first, ranked by the existing other-entity
importance. Fill unused slots with completely undated relations, ranked by the
same score, up to **20 total**. A missing interval bound is open at that end;
a point date remains a point. Dated relations outside the period are omitted
from this selection, while source evidence and prior uncapped outputs remain
preserved. No source date is changed by selection.

Keep the existing mutual-endpoint intersection, with no refill afterwards.
Event/Event and Event/other links bypass the date filter and cap. Count base
assertions, not reverse views. Equal scores within one temporal group use
ascending native Wikidata source assertion ID (`source_record_id`), as approved
on 21 October. This stable order is independent of input and observation-ID order. Compare partial dates only at their
supplied precision and include possible overlap for partial dates. Calendar
conversion or combined point/interval interpretation still stop for consultation.
Do not invent exact days.

Implementation: `relation_selection.py`, policy
`daniel-mutual-top-20-period-first-v1.1.4`. The first continuation used
`outputs/poc_10k_event_model_period_first_20261021/` and reuses the previous
verified native mapping extensions. Require its final status before claiming
model population. This rule supersedes ranking all dates together below.

The first period-filter run stopped after **32.983 seconds** on native statement
`Q10905632$d37d0b33-4b2d-545f-40a1-9a8a7e814b71`: Huaxia (ethnicity)
(Q10905632) -> P1366 replaced by -> Han Chinese (Q42740), point year **-207**,
year precision, Julian calendar (Q1985786). The calendar guard stops before
interpreting non-Gregorian dates. No Entity/Event/Relation model output was
written and no source requests ran; all pinned input checksums were verified.
Evidence: `report.json`, `calendar_case.json`, `stop_verification.json` in the
fresh continuation directory. The existing source scan still covers 18,349
in-scope assertions and the selected 2,135 Events remain unchanged.

Approved after this stop: compare Julian dates whose supplied year is outside
1941-1945 by year without converting the day. Apply the existing point/interval
overlap logic: an old start with an open end is not automatically excluded.
Julian dates within 1941-1945 still stop for calendar interpretation. Original
dates and calendars remain unchanged. Resume in the fresh directory
`outputs/poc_10k_event_model_period_julian_year_20261021/`; its report determines
completion. Other unexpected data still stop under the POC consultation rule.

The year-check continuation stopped after **23.908 seconds** on a different
case: Republic of China (Q13426199) -> P1365 replaces -> Manchukuo (Q30623),
statement `Q13426199$6355b014-40c1-bf12-4a3e-66e5aab2182e`, with a Gregorian
P585 point date supplied only as **1945**, precision 9. Its position relative
to 2 September cannot be established. No month/day was invented. No model rows
were written, no source requests ran, and all pinned inputs were verified
unchanged. Evidence: `partial_date_case.json`, `report.json`,
`stop_verification.json` in the year-check continuation directory. Eleven
focused relation/model tests passed; Ruff and Black passed. The selected
2,135 Events were unchanged.

The user then approved **possible overlap for partial dates**, preserving the
source date and precision. Compare year/month/day prefixes only at the supplied
precision: 1945 or September 1945 can overlap the period; October 1945 cannot.
The same rule applies to interval bounds. This changes selection eligibility,
not the source date, and does not assert a specific day or certain overlap.
Other calendar safeguards remain in force; the later approval
below extends supported precision to decades, centuries and millennia.
Fresh continuation: `outputs/poc_10k_event_model_possible_overlap_20261021/`.
Its final report is required before claiming population completion.

The possible-overlap continuation stopped after **30.569 seconds** on Germany
(Q183) -> P530 diplomatic relations -> Tunisia (Q948), statement
`Q183$fc5817e6-485b-8f61-78ea-42000433e85c`. The native start is
`+1950-00-00T00:00:00Z` with **precision 8 (decade)**, not year precision.
[Wikidata's date model](https://www.wikidata.org/wiki/Help:Dates#Precision)
defines this as the 1950s. At this stop, precision below year required
consultation. No model rows were written and no
source requests ran. All pinned input hashes were verified unchanged;
`coarse_date_case.json` and `stop_verification.json` preserve the case and
receipt. Eleven focused relation/model tests, Ruff and Black pass. The selected
2,135 Events remain unchanged. Population remains incomplete.

The user approved Wikidata precision ranges for selection: decade precision 8
uses x0-x9 (1950-1959); century precision 7 uses x01-x00 (1901-2000);
millennium precision 6 uses x001-x000 (1001-2000). Interpret the supplied year
within its native bucket, including values such as 2000 at century precision.
Use possible overlap for points and interval bounds, with comparison-only
range limits; preserve the native timestamp, precision and raw qualifiers.
The Germany/Tunisia 1950s start is outside the period. For Julian coarse dates,
the whole precision range must be outside 1941-1945 to bypass conversion;
otherwise stop. Unhandled precision and non-positive coarse years still stop
for interpretation. Fresh continuation:
`outputs/poc_10k_event_model_precision_ranges_20261021/`. Its report determines
completion. All other matching, Event and relation-cap rules stay unchanged.

The precision-range continuation passed all date checks, then stopped after
**21.486 seconds** at the still-unapproved cutoff tie. Madagascar (Q1019) has
34 eligible non-event assertions; 17 undated assertions tie at importance 1
across the cutoff. Their endpoints include Africa, Russia, Mozambique Channel,
East Africa, Maevatanana, Antananarivo, Turkey and the Kingdom of Denmark.
`report.json` preserves every tied observation ID and endpoint.
`stop_verification.json` confirms all pinned inputs unchanged, zero model rows
written and zero source requests. The scan preserves 18,349 source assertions
across 6,796 QIDs and the selected 2,135 Events remain unchanged. Twelve focused
relation/model tests, Ruff and Black passed at that stop. The user subsequently
approved ascending native source assertion-ID ordering for equal scores within
a temporal group. The fresh continuation is
`outputs/poc_10k_event_model_stable_ties_20261021/`; its final report determines
completion. Missing or repeated source assertion IDs still stop. No other
ranking, date, importance or Event rule changes.

### Verified model population - stable ties, 21 October 2026

The approved native source assertion-ID tie-break completed the frozen 10K
Events/Relations population in **122.285 seconds** without new source requests.
Output: `GG_Data/pipeline/outputs/poc_10k_event_model_stable_ties_20261021/`.
Status: **EVENTS_AND_RELATIONS_POPULATED**. Tables contain **8,212 typed Entity
rows** (all **6,077 original rows unchanged**, plus 2,135 separate event-typed
rows), **2,135 Events**, and **11,409 retained base Relations**.

All **8,861 Event-linked assertions** bypassed date filtering and the cap.
The non-event selection retains **304 overlapping dated** and **2,244 undated**
assertions; its maximum incident assertion count is **20**. Of 18,349 scanned
in-scope source assertions, 767 are dated outside the period and 6,173 other
assertions fail mutual top-20 selection. Their full source evidence is preserved;
this selection does not delete original dates or older outputs. Madagascar
selects 20 assertions locally and retains six after mutual intersection, with
no refill. Each assertion remains distinct; reverse views are not counted.

Independent verification reproduced every endpoint ranking from native IDs,
importance and temporal groups, checked all Event exemptions and foreign keys,
verified all output hashes and original Entity contents, and confirmed unchanged
pinned inputs. Evidence: `report.json`, `manifest.json`, `verification.json`,
`independent_verification.json`, and all six model/audit gzip files.
Report SHA-256: `8cde86c52285958f197c27166b53652181efac2233d05afd8bafbc33ba956357`.
Twelve focused tests, Ruff and Black passed. `population_s2t_at_run.md` preserves
the exact S2T revision pinned during execution; this results update was added
after the run. Geography, final graph JSON and Agent integration remain pending.
Code/docs receive a local Git checkpoint; generated outputs remain local and
ignored by Git.

### Historical model population continuation - cutoff before period filtering

`event_model.py` resumed using the approved point-date range. The full source
scan completed: **6,796 distinct QIDs**, **246,936 native claims** and **18,349
in-scope assertions**, including all 34 historical relations with original
pre-1900 dates. The Enola Gay assertion now has the verified derived range
6-9 August 1945, with both source points preserved. The saved 2,135-Event
selection and original typed Entities remain unchanged.

The existing native-property rule added P2567 (amended by), P2715 (elected in),
P3833 (diaspora), and P6477 (does not have characteristic) to this continuation's
mapping parameters. Their names were retrieved together from the agreed
BigQuery snapshot and cached. IDs and native direction are retained; no Level 1
category was assigned. Earlier mapping files were not overwritten.

The run stopped at the non-event top-20 gate after **46.187 seconds**:
United Nations (Q1065) has 101 incident non-event assertions, with three
Indonesia (Q252) assertions tied at the cutoff at importance 28. No tie rule
is approved. Fixed ordering by the existing assertion ID has been proposed,
but is not implemented. Event links remain exempt from this cap.

No Entity, Event or Relation model output was written. Supporting mapping and
stop records are in `GG_Data/pipeline/outputs/poc_10k_event_model_point_ranges_20261021/`:
`report.json`, `stop_verification.json`, and `mapping/`. Focused date, model,
selection and population tests pass (25 tests); focused Ruff and Black pass.
The next step requires agreement on the cutoff tie rule, then a fresh run
that reuses saved source records and property names. Geography, graph export
and Agent integration remain pending.

### Historical model population preflight stop - resolved 21 October 2026

The approved continuation stopped before any model rows were written. The
snapshot assertion `Q204424$4c059d94-49a4-80c6-8ff6-19af6b801cfd` is
**Enola Gay (Q204424) -> P793 significant event -> atomic bombings of Hiroshima
and Nagasaki (Q488)**. It supplies two P585 point-date qualifiers:
**6 August 1945** and **9 August 1945**. Existing relation start/end selection
rules do not define selection between multiple point dates. `relations.scan`
correctly stopped under the POC consultation rule; the complete relation scan
and model population remain pending. The verified 2,135-Event selection is
unchanged. No new source requests ran.

At that historical stop, the unapproved proposal was to preserve one source assertion with both original
point dates, leave its scalar selected point date empty, and expose the case in
the temporal report. Do not choose a date, split the source assertion, or apply
start/end rules to P585 without agreement. The approved derived-range rule above
now supersedes that proposal. Historical stop receipt:
`GG_Data/pipeline/outputs/poc_10k_event_model_population_stop_20261021/report.json`.

## Historical Event rule - average test, superseded 21 October 2026

Require accepted native recognition and direct mapped, non-excluded assertions
connecting an Event to at least **two distinct retained Daniel QIDs**. Include
it only when the **arithmetic mean of known linked-entity scores is >=2%**,
including exactly 2%. Each distinct QID supplies one score: its highest
available English/Japanese scope concentration, using exact page-count ratios.
Do not pool page counts or weight scores by mentions, predicates or typed rows.

**Missing scores enter neither sum nor divisor. They are not zero and no longer
provide an inclusion exception.** All-unscored Events fail relevance visibly
(`NO_KNOWN_SCORES`); a missing score record is still an integrity error.
Explicitly unscored QIDs can satisfy the two-entity count, but not the mean.
Thus two linked QIDs, one scored 3% and one unscored, pass; 3% and 0% fail.

This approval supersedes maximum aggregation and the missing-score bypass.
The separate 5% MISC scope filter, 3,466 retained QIDs, matching assignments,
native hierarchy, assertion mapping/exclusions and all original data stay fixed.
The saved scores contain 2,446 known and 1,020 explicitly unscored QIDs.
`event_selection.select_events()` records the average, scored/total counts,
missing QIDs and an explicit decision reason. Maximum is diagnostic only.

The retrieval controller reuses the verified >=3-endpoint partition. For new
exactly-two retrievals, one known score >=2% is a necessary source prefilter,
not the final decision. Mapping/exclusions precede the local mean; filtering by
the preliminary average could incorrectly lose Events after exclusions.

The completed cloud job `geoai_044494de23c55237ae5f174ae918ddb3` was recovered
on 21 October, with its exact SQL, destination row count and all **1,773 rows**
verified and cached. Its older prefilter (known >=2% OR unscored endpoint) is a
safe candidate superset, not an inclusion rule. Every recovered candidate was
rechecked with the current average rule. No duplicate Event discovery query
was submitted. The original stopped attempt remains intact. Earlier maximum
and missing-score-exception selections below are historical.

### Completed retained-scope eligibility check - 21 October 2026

The frozen 10K POC's retained **3,466 Daniel QIDs** were checked using **20,024**
cached >=3-endpoint candidates and **1,773** recovered exactly-two candidates:

| Result | Count |
|---|---:|
| Candidates checked | 21,797 |
| Events passing current rules | 775 |
| Passing with exactly two retained linked QIDs | 536 |
| Passing with three or more retained linked QIDs | 239 |
| Rejected: known-score average below 2% | 21,021 |
| Rejected: no known linked-entity scores | 1 |
| Unique native assertions supporting selected Events | 3,025 |

Independent exact-fraction arithmetic reproduced all 21,797 decisions and
checked input/output hashes, distinct endpoints and assertion identities.
Completed-job recovery and connected query/selection checks passed **19 tests**,
Black and focused Ruff; `git diff --check` passed. The
239 selected cached candidates exactly match the earlier partial replay.
The continuation took **119.039 seconds**, including an approved BigQuery
lookup/cache of nine missing property names; Event discovery reused completed
results. The recovered original Event query took **376.464 seconds** when it
ran. These timings are not a full-300K estimate.

Evidence: `GG_Data/pipeline/outputs/poc_10k_events_average_2pct_completed_job_20261021/`,
including `report.json`, `decisions.json`, `selected_links.json`, source records,
mapping additions, `verification.json` and `independent_verification.json`.
The controller's `--recovered-two-query` option requires the exact expected
snapshot/scope SQL and a complete, matching completed-job cache.

This completes eligibility for the retained 10K scope, not all Wikidata or all
Daniel data. The separate MISC filter/hold remains unchanged. **No Event model
rows or final graph were written.** Model population is the next phase.
Code/docs have a local Git checkpoint; generated artifacts remain ignored.

### Earlier partial saved-data replay - 21 October 2026

The average selector passed **53 focused tests**, Black and focused Ruff.
A saved-only replay retained **239 of 20,024** cached candidates; **19,785**
failed the known-score average threshold. Independent exact-fraction arithmetic
reproduced every decision. The 15 Pacific battle examples retain **10**, matching
the earlier diagnostic comparison. No source requests were made.

This earlier replay was **not the full 10K Event result**: it checked only the
>=3 preliminary-endpoint partition. The complete retained-scope eligibility
check above now includes exactly-two candidates. No Event model rows or final
graph were written. Earlier replay evidence, input/output hashes and code:
`GG_Data/pipeline/outputs/poc_10k_event_average_2pct_replay_20261021/`.
Code/docs receive a local Git checkpoint; generated output remains ignored.

## Historical Event relevance tests and measurement stops

**Historical maximum-rule 2% tests, superseded by the average rule above.** After
recognition and the two-distinct-Daniel-entity gate, use the maximum linked
entity score and keep Events with a known score **>=0.02**, including exactly
2%. The separate **5% MISC entity-retrieval filter remains unchanged**. The
15-battle test, findings and limits are recorded in section 6.1. Earlier 5%
Event results below are historical diagnostics, not the current Event cutoff.
This document update does not implement or run the new cutoff.

**10K continuation approval and stop, 21 October 2026:** the user approved
holding the **619 unknown MISC QIDs** aside for the full 10K POC, reporting
them separately without deleting model rows. The frozen 4,712 matched QIDs
therefore split into **3,466 retained**, **627 below the 5% MISC retrieval
cutoff**, and **619 held unknown**. This approval covers the retrieval scope;
it does not treat unknown scores as zero or waive consultation for unknown
linked-entity Event aggregates.

The reusable `GG_Data/pipeline/event_selection.py` selector implements the
maximum linked-entity **>=2%** comparison with exact fractions. Five focused
tests passed, including exactly 2%, below 2%, repeated endpoint deduplication
and an explicit unknown decision. Full-POC relevance acquisition started, but
stopped during English reverse-redirect validation before either language's
new scores or any Event query/import completed. In the saved 20261001 dump,
page **78426011 / State_of_the_Turks** is marked **not a redirect** in the page
table, while the redirect table links it to **Turkey**, affecting the alias
inventory for **Q43**. Both saved table hashes validate. The user subsequently
approved: **"Use the redirect always"**. Saved redirect rows therefore take
precedence over conflicting page-table redirect flags, both when resolving a
measurement page and when collecting its reverse aliases. Keep the original
entity QID, count the final destination page once, and retain the existing
namespace, missing-destination, cycle and 20-hop checks. This approval changes
redirect handling only; source dates, matching assignments and thresholds stay
unchanged. Preserve this stopped attempt and use a new continuation directory.

Evidence: `../GG_Data/pipeline/outputs/poc_10k_event_selection_2pct_20261021/`
contains `retrieval_scope.json`, the pinned selection/manifest, the stopped
`report.json`, `enwiki/progress.json` and `redirect_conflict.json`. Zero Event
rows, graph outputs or new cloud requests were produced. This is a stopped
attempt, not a completed 10K Event selection or a replacement for prior tests.

**Redirect-priority continuation result, 21 October 2026:** both saved-dump
language measurements completed in **419.082 seconds**, with no source network
requests. English has **2,351 scored / 1,115 unavailable**; Japanese has **1,333
scored / 2,133 unavailable**. The highest available language produces **2,446
scored / 1,020 unavailable** among the 3,466 retained QIDs. Of those 1,020,
**1,018 have no saved article page in either language**; two have no English
article and no incoming Japanese links. These are non-MISC QIDs, separate from
the already held 619 MISC QIDs. Their model rows and identities remain intact;
unavailable is not zero and does not establish absence from Wikidata. Under
the POC stop rule, continuation pauses for consultation before Event discovery
or import; unknown linked-entity Event aggregates remain undecided. This is
completed measurement, not completed Event selection.

Evidence: `../GG_Data/pipeline/outputs/poc_10k_event_selection_2pct_redirect_priority_20261021/`
contains the complete EN/JA reports, combined `entity_scores.json`, a separate
`unavailable_entity_scores.json` list, approval/code evidence and
`verification.json`. Output hashes, retained-QID coverage and exact language
maxima passed verification. Zero Event rows or graph outputs were written.

## Approved Event recognition rule — 21 October 2026

The user accepted the tested recognition rule after the 375-record audit:
"This is good enough for events recognition". Use the complete native P279
descendant list of **Q1190554 (occurrence)** from the agreed BigQuery snapshot.
A candidate passes recognition when at least one normal or preferred P31 value
is in that list. Normal and preferred P279 statements confer membership at
every hierarchy step; deprecated statements remain evidence only. Reuse the
locally saved, checksum-verified query results and parameter tables.

This supersedes Q140451665 and the latest-available live-hierarchy requirement
for this recognition method. It does not introduce another source, root,
manual exception, local type category, or name-based recognition. For each new
Daniel data version, bind the parameters to that version's agreed source
snapshot; the POC timestamp below is evidence for this run, not a fixed future
pipeline date. Assertion acquisition and matching source rules are unchanged.

**Accepted limit:** a negative means "not recognized by the approved hierarchy",
not "confirmed not an Event". The 2,680-record test has 1,414 recognition
positives and 1,266 negatives. The negatives include 891 records with human as
an active P31 type and the audited 375: 367 with other active P31 types and
8 with no P31 statements. All 375 candidate records and all 295 direct type
records were found in the same source (665 distinct QIDs after overlap).
Missing P31 is not a missing source record. The audit identified Cyclone Kyrill
(Q939336), typed European windstorm (Q148942), outside the approved descendant
list. The user accepts this recognition limit; do not add an exception for it.
The audit does not certify every other negative as a non-Event.

Recognition and inclusion are separate gates. A recognized candidate must still
have approved direct mapped assertions to/from at least **two distinct matched
Daniel QIDs** before Event import. This approval does not waive that gate or
assert complete Event population, and it changes no existing match assignment.

**Verified two-entity gate, 21 October 2026:** all **1,414 recognized
candidates** passed against the unchanged **48 retained matched Daniel QIDs**
in this bounded sample. Native assertions came from the same agreed BigQuery
snapshot. The existing mapping and exact assertion exclusions were applied:
**2,889 unique native assertions**, no missing property mappings, and no
excluded assertions. Both directions were checked (2,872 Event-to-Daniel;
17 Daniel-to-Event). Counts use distinct Daniel QIDs, not mentions, predicates,
typed rows, or reverse views: **1,398 candidates have two**, **14 have three**,
**one has four**, and **one has five**. All assertion ranks remain eligible
under the existing rule (2,887 normal; two deprecated); the ancestry-only rank
filter was not applied to Relations. Independent replay matched the saved
preliminary endpoint inventory and the post-exclusion endpoint counts.

Evidence: `../GG_Data/pipeline/outputs/event_hierarchy_bigquery_occurrence_test_20261021/two_entity_gate/`
contains the native query/result, full decisions, `decisions.csv`, source/job
receipt, checksums, and `verification.json`. Client query time was 30.785
seconds. This verifies the gate for this sample only; it does not verify the
full 10K population. No Event rows or final graph were written.

Saved evidence: `../GG_Data/pipeline/outputs/event_hierarchy_bigquery_occurrence_test_20261021/`
contains `recognition_approval.json`, complete query results and parameter CSVs;
`audit_375/REPORT.md`, `records_375.csv`, `types_295.csv` and `report.json` contain
the audit, original type evidence, source/job receipt and checksums. These are
local, ignored artifacts. **Implementation status:** this S2T records the
approved rule; the production root constant and parameter-loading integration
have not yet been changed. No Event rows or final graph were created.

## Verified test — BigQuery occurrence root, 21 October 2026

The user approved a **test** of Q1190554 (occurrence) in the same public
BigQuery source on 21 October. `sql/event_hierarchy_bigquery_test.sql` uses native
P279 statements from the agreed source snapshot, builds the complete descendant
closure in cloud temporary tables, and returns only that closure with original
statement IDs/ranks. The frontier contains each QID once, so cycles terminate
without a depth limit. Normal and preferred ranks confer membership at each hop;
deprecated statements remain evidence only. No production root constant, Entity
row, Event row or graph export is changed by this test.

A cloud fixture verified cycle termination, coexisting normal/preferred links,
and exclusion of a deprecated-only branch and its descendants. BigQuery script
messages and final rows are decoded separately; the saved result is checked
against both its window count and the actual destination table row count. The
initial fixture reader error and its original response remain saved. No source
request was repeated to correct the reader.

Test evidence and measurements:
`GG_Data/pipeline/outputs/event_hierarchy_bigquery_occurrence_test_20261021/`.
**Verified result:** the same-source cloud query found **103,893 types** and
117,093 nondeprecated hierarchy statements after 18 frontier iterations. Another
110 deprecated statements remain in the raw evidence. War, battle and World War
II passed the controls; human, country, organization and city classes were not
in the descendant list. The two test-only parameter tables are saved under
`parameters/event_types.csv` and `parameters/event_hierarchy_mapping.csv`.
These are the occurrence hierarchy, not a population of WWII Event records.

The unchanged Daniel-first sample contained **2,680 preliminary candidates**
from 48 retained Daniel QIDs. A second query joined their native, nondeprecated
P31 values to the completed hierarchy **inside BigQuery**: **1,414 passed**,
**1,266 did not pass**, and **zero source records were missing**. The sample's
relevance threshold and candidate population were unchanged. A positive result
establishes hierarchy membership only; it does not replace the existing
minimum-two-distinct-Daniel-entities rule, relation mapping checks, or final
Event inclusion. This bounded sample is not the complete 10K Event population.

| Measurement | Cloud execution | Client execution, including checks |
| --- | ---: | ---: |
| Complete hierarchy | 125.148 seconds | 208.435 seconds |
| 2,680-candidate classification | 1.727 seconds | 29.014 seconds |

The hierarchy job billed 1,564,857,073,664 bytes under the existing 2 TiB cap.
Only 221,097 completed result rows (14,961,458 logical bytes), not the full
Wikidata source records, were returned for the hierarchy. The sample query
returned only candidate IDs, P31 evidence and classification flags. Both source
queries used `bigquery-public-data.wikipedia.wikidata` at the agreed snapshot
`2026-10-18T18:45:19.304197+00:00`.

The sample reader initially expected Boolean objects; the CLI supplied the
literal strings `"true"` and `"false"`. The reader now accepts only the explicit
Boolean literals or null, and was checked against the saved P31 evidence. The
original failed validation report is retained. Neither source query was repeated
to fix a reader. `verification.json` verifies hashes, complete row counts,
unique native statement IDs, parameter counts, the 2,680-row partition and the
unchanged production root. No Event rows or final graph JSON were created.
The test root and parameter tables have **not** been promoted to production.

## Historical stop — direct BigQuery root-edge query, 21 October 2026

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

**Follow-up diagnostic, same source:** a separate cloud query verified native
P31/P279 parsing and found World War II (Q362), war (Q198), battle (Q178561),
occurrence (Q1190554) and event (Q1656682). The snapshot explicitly contains
normal-rank `war -> occurrence` and `event -> occurrence` subclass statements.
Evidence: `GG_Data/pipeline/outputs/event_hierarchy_bigquery_controls_20261021/`.
The zero result for Q140451665 does not establish that this data version is
unsuitable for Event acquisition. The root assumption must be validated against
the source's own hierarchy before proposing a source-version change. No alternate
root has been applied; a Q1190554 root test is a proposed classification-rule
change that requires agreement under the user's POC rule.

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
| OHM, OSM, WHG and GeoNames under `geo-object-selection-v0.5.0`, plus the approved Wikidata coordinate extension in section 9.3 | Geometry acquisition and identity evidence under the existing policy and dated approvals. | Wikidata coordinates also support retrieval and last-resort Point geometry under section 9.3; Wikidata shapes remain excluded. WHG has a restricted reconciliation role. |

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

## 3. Matching logic and page-scope correction (22 October 2026)

The historical run incorrectly mixed global exact-name lookup hits into its
page candidate pool. The user requires a rebuild from matching onward. Its
matching decisions and all dependent POC outputs are historical evidence, not
validated inputs for the corrected pipeline. Reuse source records only after
checksum/version/scope checks; preserve the old artifacts without overwriting.
The same original 10K row sample is retained downstream. Rebuild all 309,864
matching rows first because the already-matched pool depends on all page passes.

1. Resolve each source page and retrieve its Japanese counterpart where available. The first-stage candidate QIDs are only the QIDs of those source articles and their saved direct links. Compare Daniel's original names with those candidates' English/Japanese labels and aliases. A global exact-name lookup must never add a candidate to this stage. Reconstruct pools from source-page evidence; do not reuse the old candidate pools or old page matches. Record scope `SOURCE_PAGE_EN_JA_LINKS_ONLY_V1`. The saved SQL-dump links include transcluded navigation; they are not revision-pinned article-body-only links, and this existing evidence limitation remains explicit.
2. Choose the highest character-trigram Dice similarity at **>=0.80**, with compatible types. Reuse the saved single-type override rule and its metadata when applicable. Ties reuse the recorded seeded random choice (`20261018`), not a new choice at population time.
3. After every corrected page pass completes, create a new frozen matched-QID pool. Match remaining mentions against that newly matched pool; then use the saved fresh-WWII reference pool under the same threshold/type rules. Never reuse the historical frozen pool or historical fallback decisions. These two fallback stages are wider than the source page, as previously agreed; the page-only constraint applies to the first stage.
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

The approved name order supersedes a simple copy of the compact metadata's selected `label`. If English and Japanese labels are absent and one QID has different Daniel names, show the exact names/QID before choosing a canonical fallback. **Event-only fallback, approved 22 October 2026:** when an Event has no English/Japanese label and no Daniel name, use its existing Wikidata QID as the display name. Record `attributes.name_selection.source=wikidata_id_fallback` and `language=null`; preserve all original labels. This is a display placeholder, not a new label, translation, identity or Event selection rule. Other missing/ambiguous Daniel-name cases still require consultation.

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
the matching similarity threshold or Event hierarchy. The current Event minimum is two distinct retained Daniel QIDs, plus maximum linked-entity score >=2%, with missing scores contributing zero and no bypass.

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

**Event relevance diagnostic, clarified 21 October 2026:** measure the
**linked Daniel entities**, not the Event candidate itself. First calculate
each linked QID's scope concentration independently in English and Japanese,
then use its highest available language score as specified above. For each
recognized Event passing the two-distinct-entity gate, calculate the arithmetic
mean, minimum and maximum of its distinct linked Daniel QID scores. Each QID
counts once, regardless of mentions, typed rows, predicates or reverse views.
Do not pool entities' page counts or weight their scores by assertion counts.
Keep missing scores explicit; if any linked entity is unmeasurable, the complete
Event statistics remain unknown, with scored/total counts and missing QIDs shown.
The initial run was a diagnostic comparison only; historical maximum-score
decisions are recorded below. The current rule above averages only known scores. No Event import changes were made by that test.
The existing 5% entity-retrieval rule remains unchanged. The reproducible
diagnostic is [event_linked_entity_relevance_probe.py](../GG_Data/pipeline/event_linked_entity_relevance_probe.py).

**Verified linked-entity test, 21 October 2026:** the same 1,414 candidates
link to 13 distinct Daniel QIDs in the bounded 48-QID sample. English scores
are available for all 13; Japanese scores for 12. The per-entity maximum
therefore supplies complete mean/minimum/maximum statistics for all 1,414
Events, with no unknown aggregates. This does not establish full-10K coverage.
At a diagnostic 5% cutoff, mean and minimum would each retain zero Events;
maximum would retain only World War II/Q362. All 1,282 clinical trials share
Hungary/Q28 and Netherlands/Q55: minimum **0.0880%**, mean **0.2410%**, maximum
**0.3939%**. Pacific War/Q184425 has minimum **0.3939%**, mean **0.4317%**,
maximum **0.4696%**; World War II/Q362 has minimum **0.4696%**, mean **2.5454%**,
maximum **6.1385%**. Thus the tested cutoff also rejects a central Pacific
War example. At the time of the test no aggregate filter or new threshold was
selected; no recognition or matching rule changed, and no Event rows were
imported. Full entity counts,
per-language evidence, all Event statistics, hashes and independent replay
are in `../GG_Data/pipeline/outputs/event_hierarchy_bigquery_occurrence_test_20261021/linked_entity_relevance_test/`.

**Earlier user decision after the test, 21 October 2026:** use **maximum**, not mean
or minimum, across the distinct linked Daniel entity scores. Each entity score
continues to use the highest available English/Japanese percentage. With the
existing 5% cutoff, the saved bounded sample includes only World War II/Q362
(6.1385%) and excludes 1,413 candidates. Excluded WWII examples include Pacific
War, Normandy landings, Eastern Front, Eastern European theatre of World War II,
Battle of Stalingrad and Battle of Debrecen; their actual scores remain in the
saved diagnostic. This records the selected aggregate, not completion of the
production filter or Event import. No new threshold, historical exception,
entity match or recognition rule is introduced. Future cases with unavailable
scores still require consultation before an exclusion decision.

**Historical Pacific battle test and threshold approval, 21 October 2026 (maximum aggregation since superseded):**
the user approved lowering the **Event relevance cutoff from 5% to 2%** after
reviewing 15 specific Pacific WWII battles against the existing 10K POC data.
The aggregate remains the maximum of distinct qualifying linked Daniel QID
scores; each QID score remains its highest available English/Japanese scope
concentration. A known maximum **>=0.02** passes, including exactly 2%; a known
maximum **<0.02** fails Event relevance. Missing scores remain explicit and
require consultation under the existing rule. Recognition, direct-link mapping,
the two-distinct-entity gate, identity assignments and the **5% MISC retrieval
filter** are unchanged. This is not a lower entity-name matching threshold.

All 15 targets occur in the earlier wider candidate pool, but none occur in
the latest bounded 2,680-candidate test drawn from 48 retained Daniel QIDs.
Their absence from that small test therefore did not establish rejection.
All 15 pass the approved native Event recognition rule and have at least two
directly linked QIDs in the original 4,712-QID Daniel population. After the
existing MISC retrieval filter, 14 retain at least two qualifying QIDs. All
target aggregates are measurable; there are no unknown Event scores.

Replaying the saved scores at 2% gives **13 passes, one relevance failure and
one two-entity-gate failure**, compared with **nine passes, five relevance
failures and one two-entity-gate failure at 5%**. Percentages below are rounded
for display; comparisons use the unrounded saved fractions.

| Battle Event | Wikidata ID | Qualifying linked Daniel QIDs after MISC filter | Maximum linked-entity score | At 5% | At approved 2% |
|---|---|---:|---:|---|---|
| Pearl Harbor | Q52418 | 5 | 9.230769% | Pass | Pass |
| Wake Island | Q1141380 | 4 | 6.441224% | Pass | Pass |
| Coral Sea | Q207165 | 4 | 2.702703% | Relevance failure | Pass |
| Midway | Q173034 | 4 | 6.601467% | Pass | Pass |
| Naval Battle of Guadalcanal | Q696438 | 4 | 3.369390% | Relevance failure | Pass |
| Attu | Q700572 | 3 | 3.369390% | Relevance failure | Pass |
| Tarawa | Q250309 | 2 | 14.285714% | Pass | Pass |
| Bismarck Sea | Q1753578 | 1 | 3.369390% | Two-entity failure | Two-entity failure |
| Philippine Sea | Q504347 | 5 | 28.571429% | Pass | Pass |
| Leyte Gulf | Q308999 | 4 | 3.369390% | Relevance failure | Pass |
| Saipan | Q700705 | 4 | 11.764706% | Pass | Pass |
| Guam | Q696900 | 4 | 6.250000% | Pass | Pass |
| Manila | Q696931 | 3 | 0.683631% | Relevance failure | Relevance failure |
| Iwo Jima | Q180182 | 4 | 6.250000% | Pass | Pass |
| Okinawa | Q192660 | 7 | 17.777778% | Pass | Pass |

**Finding:** the 2% cutoff recovers Coral Sea, Naval Guadalcanal, Attu and
Leyte Gulf. Manila remains below the Event cutoff. These relevance failures
apply to the battle Events, not deletion of their linked entity rows.
Bismarck Sea is a separate retrieval issue: its two original linked QIDs are
World War II/Q362 and Pacific War/Q184425. Q362's entity score is 0.464266%,
so the unchanged 5% MISC filter removes it from retrieval, leaving only
Q184425. Lowering Event relevance alone does not restore the second endpoint;
both original entity records remain in the model. No exception is approved.

**Limits and implementation status:** this is a targeted battle diagnostic,
not a representative estimate of unrelated Events admitted at 2%, complete
10K Event coverage, or a completed production rerun. No Event rows or final
graph were written. The original saved 5% diagnostic artifacts remain unchanged;
the 2% comparison above is a replay of their recorded scores and gates.

Evidence: [15-battle decisions CSV](../GG_Data/pipeline/outputs/event_pacific_targets_trace_20261021/decisions.csv),
[final report](../GG_Data/pipeline/outputs/event_pacific_targets_trace_20261021/final_report.json),
and [verification](../GG_Data/pipeline/outputs/event_pacific_targets_trace_20261021/verification.json).
The same directory contains the native assertion trace, source receipts and
per-language scores. The verified report SHA-256 is
`01c8232ac645cd7e47fe9db49bd5df65cfcf0732c3442ca9359f89d82aba23f9`;
the decisions CSV SHA-256 is
`4dce5e5339970918e9055303fbf09d44cbaa0c34bb61fe45d3c45fcb6f12eea6`.
These evidence files are local ignored outputs, not an off-device backup.

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

**Current recognition rule, 21 October 2026:** use the approved same-snapshot
BigQuery Q1190554/P279 parameter list and normal/preferred P31 recognition
specified above. Recognition negatives receive no manual exceptions; they are
not proof of non-Event status. The two-distinct-Daniel-QID inclusion gate remains
mandatory. Production integration is pending; this specification does not claim
it has run.

**Historical source exception, 20 October 2026 (superseded for classification by the 21 October rule above):** Event classification uses the latest available Wikidata P31/P279 hierarchy, with verified cache reuse first, even if the agreed snapshot contains an older class record. This supersedes snapshot-first priority for classification evidence only. Entities, Event assertion records and Relations retain the agreed snapshot-first source rule and latest-available same-QID fallback when required input is absent. Root Q140451665, non-deprecated classification, all statement ranks in Relations, and the two-distinct-Daniel-QID gate are unchanged. No version-difference report is required.

Incoming acquisition may first measure a superset of the existing inclusion gate in BigQuery: retain subjects with two or more distinct Daniel main-item targets, plus subjects with one such target that are also targets of a saved Daniel outgoing assertion. Outgoing-only neighbors remain in the local outgoing inventory. Mapping/exclusion checks and the distinct union of both directions still apply before inclusion. This query is a retrieval optimization, not a new relevance rule, assertion cap or claim of complete Event coverage. `event_snapshot_discovery.py` performs this measurement with the existing pinned CLI/cache/dry-run/billing controls and stops on an unapproved source or data failure.

**Verified acquisition measurement, 20 October 2026:** the saved BigQuery query found 2,209,613 incoming candidates before Event classification: 2,189,157 with at least two distinct Daniel targets and 20,456 with one incoming target plus an outgoing Daniel link. Their full native records total 37,433,814,344 bytes (37.4 GB). These are candidate items, not included Events. D: had about 17.1 GB free, so acquisition stopped before any full-record download under the POC consultation rule. The query result, source hashes and SQL receipt are verified in `GG_Data/pipeline/outputs/poc_10k_event_snapshot_measurement_20261020/verification.json`; no Event rows or final graph were written. The user subsequently approved classification-first acquisition; the active wider continuation is recorded above.

**Classification-first test approved and verified, 20 October 2026:** `event_classification_first.py` classified the existing 165-candidate probe using the verified latest-available cached hierarchy before requesting full assertion records. Seven candidates passed ancestry; only their seven QIDs were requested from BigQuery, returning 407,843 bytes of native records, all from the agreed snapshot. No fallback or new Wikidata request was needed. One new BigQuery query ran for the initial test; the checked replay reused it. Output: `GG_Data/pipeline/outputs/poc_10k_event_classification_first_checked_20261020`, status `VERIFIED_CLASSIFICATION_FIRST_BOUNDED_TEST`. This confirms retrieval order only: it does not classify the wider 2,209,613 incoming candidates, project savings to that population, or establish the two-distinct-Daniel-QID inclusion gate. No model Event rows or final graph were created. A compact latest-available classification index for the wider candidate population is still needed before full-record acquisition.

### Native hierarchy and inclusion

**Historical source approval, 20 October 2026 (classification is superseded by the 21 October rule above):** use current Wikidata for Events and their
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

The approved recognition root is **Q1190554 (occurrence)**, including its complete normal/preferred native P279 descendant list from the agreed BigQuery snapshot. Identify candidate instances through normal/preferred P31 values in that list. Record root QID, source snapshot, native class IDs and statement evidence. Reuse the verified local parameter tables. Do not add another root, a local event-type whitelist, manual exceptions, or invented war/campaign/battle levels. A failed recognition test is not proof that an item is not an Event; the accepted coverage limit is documented above.

For each discovered event QID, use its direct mapped Wikidata assertions to/from **D**. Include it only if at least two distinct retained Daniel QIDs qualify and the maximum linked-entity relevance is >=2%. Each QID uses its highest available EN/JA score. Missing relevance contributes zero to selection, with the missing evidence preserved. An all-unscored Event has score zero and fails. This inclusive rule may admit unrelated items and may need improvement; see the current-rule limitation above. Repeated mentions, several predicates for one entity, duplicate retrievals and generated reverse views do not increase this count. Classification hierarchy paths identify an event; they do not count as indirect participant paths. Do not count mere shared class ancestry or article co-mentions as an event/entity connection.

Use all event types under the root. No additional date, geography or old-reference-pool filter is introduced. Do not promote an event class into an occurrence merely because it is a class in the hierarchy. Save candidate QIDs, classification evidence, direct qualifying statement IDs, distinct connected Daniel QIDs/count, inclusion decision and acquisition coverage in a supporting report. No seventh participant table is needed.

| Target column(s) | Source and population rule |
|---|---|
| `event_id` | Included native Wikidata QID; same key as its Entities row. |
| `kind` | Native supplied classification values/QIDs with evidence. No internal category/level conversion. Preserve multiple values; report scalar-target incompatibility. |
| `start_date`, `end_date`, `point_date` | Supplied Wikidata P580, P582, P585 values respectively. Retain all values, precision/calendar and evidence; do not select a preferred date. The approved P585-derived range is the sole fallback when explicit start/end are absent; preserve and mark its derivation. |
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

- Event/Event and Event/other-entity assertions are uncapped. Keep every eligible assertion under the existing source, mapping and exact-exclusion rules. All Events still require the agreed two-distinct-retained-Daniel-QID inclusion gate and maximum linked-entity score >=2%, with missing scores contributing zero and no bypass, evaluated before selection. A QID present in included Events receives the Event exemption even when it also has other entity types.
- For assertions with two non-event endpoints, the maximum is **20 base relations incident on each QID**, across both native directions. Separate typed rows do not get separate budgets. Reverse delivery views share the original assertion's slot; they do not consume additional slots.
- Score each existing Daniel Entity identity using **distinct Daniel source-page count multiplied by total original Daniel mention count**, aggregated by assigned QID or existing synthetic ID, without duplicating mentions across typed Entities rows or counting retrieved Japanese counterparts as Daniel source appearances. Each separate synthetic ID has one page and one mention, hence importance 1; no QID is required to count it. Count Daniel's original `raw.Source` values for source-page appearances, without inventing page IDs or processing paragraph text. Pin the input population: this POC uses its frozen 10K mentions, not an unstated whole-corpus frequency. No graph centrality, BM25, new extraction or rematching is approved.
- Each endpoint ranks dated assertions overlapping 7 December 1941 through 2 September 1945 first, then fills remaining slots with undated assertions, up to 20 total; use the other endpoint's score within each group. Dated assertions outside the period are omitted from selection while preserving source evidence. Keep an assertion only if it is in the top 20 at **both endpoints**. Intersect these selections; do not refill rejected slots. Some entities can therefore retain fewer than 20 relations.
- Preserve all acquired source evidence and previous outputs. Persist the approved score as Entities.importance and the factors/lineage as attributes.importance_basis. Supporting selection evidence must pin the Daniel input population/checksums, page and mention counts, score, both endpoint decisions and retained/omitted counts. This score is not a Wikidata-supplied Event `importance` value and must not overwrite that field.
- Equal scores within the same temporal group use ascending native source assertion ID (`source_record_id`), approved 21 October 2026. Keep dated-first ranking, descending importance, mutual intersection, no refill and Event exemptions. Missing/repeated source IDs or unsupported source population/page identity stop for discussion. No missing-value substitution or score-population change is approved.

Complete Event membership is required before applying the exemption. After approving this rule, the user instructed implementation and continued execution. The continuation uses the proposed incoming pages of at most 5,000 statements, with a strict native-statement-URI cursor, both graphs and the complete page chain. Existing complete unpaged responses are reused; malformed unpaged responses remain untouched. Page ordering, uniqueness and cursor progress are checked before accepting data; a short terminal page is required. No new Event count limit or relevance filter is authorized, and the existing retry/stop rules remain in force. Run: `outputs/poc_10k_event_full_discovery_paged_20261020`; live status belongs in its report, not an assumed completion. Tests before launch: 55 passed. Applying the selector and producing a fresh versioned Relations output remain pending; historical full D/D outputs are not relabeled as capped.

That continuation stopped on the first new Canada/Q16 page: a 45-second read timeout with no response body. No new paged response, partial result or automatic timeout retry was accepted. Its verification status is `VERIFIED_PAGED_DISCOVERY_SOURCE_STOP_ONLY`; 105 saved response checksums, 14 upstream hashes and 17 preceding candidate output hashes passed. Scores are verified separately in `outputs/poc_10k_relation_importance_20261020/verification.json`. Event membership and cap application remain pending. A more specific incoming query by individual Wikidata property was proposed as a test; the user requested an explanation, not execution. No property filter/test is approved or applied by that discussion.

**Subsequent approved diagnostic, 20 October:** the user then approved the one-property retrieval test. `event_property_probe.py` requests Canada/Q16, P17 (country), on the main Wikidata query graph with the same 5,000-statement page chain, ranks, cache and stop rules. This diagnostic is not a property whitelist or complete discovery implementation. It verifies the corrected scored Entities and previous stop artifacts before the request. The request timed out after 45 seconds with no response body; zero property pages/statements were accepted and no timeout retry ran. Evidence: `outputs/poc_10k_event_property_probe_20261020`, verification `VERIFIED_PROPERTY_RETRIEVAL_SOURCE_STOP_ONLY`. All five upstream output hashes checked unchanged; the failure receipt and code hashes are recorded. Full incoming coverage remains 2/9,424 graph/QID requests, with zero new Event rows, capped Relations or final graph. The process has ended. Before launch, 57 tests and Ruff passed. Further retrieval changes require consultation; no Event, identity, mapping or relevance rule changed.

### Relations date policy — approved 20 October 2026

`relation-date-selection-v1.1.0` applies to Relations only; it does not select Event dates. The user correction supersedes the earlier pre-1900-end exclusion: these statements remain in Relations with their original dates.

- Historical exception first: if the latest supplied P582 end year is before 1900, retain the relation with its supplied start and end dates, precision and calendar. Do not apply a 1900 floor or exclude it on this basis. A missing start remains missing. If multiple dates are supplied, preserve every value; select the earliest original start and latest end under the existing conflict rule. Mark `attributes.time_selection.original_pre_1900_end=true`.
- Other relations: select the earliest supplied P580 value whose year is at least 1900. If all supplied starts precede 1900, use derived year 1900 with year precision (9), without inventing a month/day. Select the latest supplied P582 end. Missing dates stay missing. The 14 exact assertion exclusions still apply before date selection; no date-only exclusion is authorized.
- Keep every original value, snak, precision and calendar. Store selection rules, selected precision and the derived flag in `attributes.time_selection`; preserve the same evidence in `input_assertion`. Multiple supplied start/end values remain visible as `MULTIPLE`, even when this approved rule selects a value.
- Different calendars within a date field, unsupported date formats, a remaining start-after-end interval, or multiple point dates accompanied by explicit bounds require consultation. Multiple P585 dates without explicit bounds use the approved derived minimum/maximum range above; do not select a single point date.

One source assertion produces one base row. Bidirectional graph navigation is supplied by the separate exporter using the [direction lookup](../GG_Data/mapping/RELATION_DIRECTION_LOOKUP_v2.1.1.csv) and `source_edge_id`. A generated reverse view is not a second independent assertion. Two genuinely separate Wikidata statements in opposite directions retain their own identities. No fixed assumption of exactly two assertions per entity pair is valid.

## 9. Geography: existing policy and fields

Follow the complete [geocoding policy](GEOCODING_HIGH_LEVEL_PROCESS.md), version `geo-object-selection-v0.5.0`; this S2T does not replace its place-type/representation table or acceptance rules.

1. Target every existing `Entities.type=LOC` identity: matched QIDs and unresolved synthetic IDs. Approved extension, 21 October 2026: synthetic LOC rows enter the existing name/alias/date/type/context fallback; they must not be excluded because they lack a QID. Preserve each original `SYN_...` ID separately, even when names repeat. A supported source-object geometry does not establish a Wikidata match: leave entity IDs, types, matching decisions and identity status unchanged. Non-place events are not name-geocoding targets.
2. Set selection date to the earliest supported related event/relation date inside `1941-12-07` through `1945-09-02`, else `1941-12-07`. Approval, 21 October: retain a year-only date as `YYYY` and a month-only date as `YYYY-MM`; compare source date-range bounds at that same precision. Do not add a month/day or derive a first day. Use the existing precision-aware possible-overlap test against the project period. For overlapping supplied prefixes, retain the shorter/coarser earliest prefix. Decade/century/millennium values keep their native year plus `selection_precision` in the selection audit; compare with the already approved Wikidata precision ranges, never interpret that year as an exact day. Preserve all original dates, precision and calendars. Unsupported representations or calendar cases still require consultation.
3. For matched QIDs, search OHM and OSM exact QID candidates, preferring OHM then OSM after identity/date/meaning/geometry checks. WHG reconciliation is used only when their combined exact-QID candidate count is zero or greater than one. Synthetic IDs have no exact-QID query: send them directly to the existing fallback in step 4, never as `wikidata=SYN_...`. WHG unions are not selected geometries.
4. Apply the existing OHM/OSM/GeoNames name/alias/context fallback with added identity evidence. A high name score alone is insufficient. Use original linked-source geometry, not a guessed shape.
5. Use the existing preferred representation and stable source-object-ID tie rule. Do not union, buffer, simplify, construct or replace with a centroid automatically. The explicitly approved source-coordinate-to-Point conversion in section 9.3 is permitted; no new area is constructed.
6. Validate a nonempty Shapely geometry; persist WKB in GeoParquet with CRS metadata. Record provenance, selection date and every failed/rejected/unselected attempt. Older OSM snapshot age is accepted; historical suitability still needs the existing checks.

Reuse approved saved snapshots/bulk retrieval first. The approved plan allows OHM snapshots, OSM BigQuery or Geofabrik files, GeoNames downloads and cached WHG reconciliation under existing limits. A specialist dataset or manual geometry needs a specific source/rule discussion before use; the generic fallback label does not approve a new dataset. The first-50 geocoding POC is evidence of that test only, not a full-Daniel accepted output.

| Target column(s) | Source and population rule |
|---|---|
| `place_id`, `name`, `place_type` | Existing LOC entity ID (QID or unchanged per-mention SYN ID), name and existing context/type evidence. One accepted geometry per existing place ID at most. |
| `source_dataset`, `source_object_id`, `source_url` | Selected original source object, snapshot/version and link. For the section 9.3 last-resort Point, identify Wikidata and its original item/coordinate statement; no Wikidata shape promotion. |
| `match_method`, `selection_policy_version` | Actual evidence method and applied version. |
| `retrieved_at`, `review_status`, `decision_reason` | Real retrieval and acceptance decision; selected rows require `ACCEPTED_AUTO` or `ACCEPTED_REVIEWED` evidence. |
| `geometry` | Validated Shapely object, persisted as WKB; load as Shapely. No inline GeoJSON export. |
| `audit` | Full original input, candidates, dates, source attempts, WHG evidence, validation and decisions, including `selection_date`. Retain the complete audit or immutable reference. |

`UNRESOLVED` and `REJECTED_NOT_PLACE` remain audit results without selected Geography rows. Preserve the ERD's exact 13-column geometry compatibility view; `selection_date` projects from audit, not link validity. Geometry type comes from the object. Store `geometry_ref={file,place_id,sha256}` in Geography model records separately from the referenced geometry artifact; the compatibility view stays at 13 columns. Do not export this pointer in graph JSON. The loader helper exists; Agent access to Geography remains an integration check.

For synthetic targets, reuse Daniel's original name, type/subtype and source-page references from the checksum-pinned Mentions artifact, together with any already-supported date evidence. A page title is context, not proof of a parent area. Do not extract new entities, infer dates from paragraph text, or fabricate place classes or parents. The existing default selection date still applies when no supported related date exists. Name and date alone do not remove identity ambiguity: retain the existing additional identity-evidence checks. Insufficient evidence remains visibly unresolved. This is the `geo-object-selection-v0.5.0` policy with the approved synthetic-LOC population extension; no source or acceptance threshold is added.

### 9.1 Candidate comparison checkpoint — 22 October 2026

The approved 40-input diagnostic preserves the original ten and adds 15 random
QID and 15 random synthetic LOC targets. WHG native country/no-date queries
increased first-ten reference-ID coverage from 10/17 to 13/17 QIDs and first-hit
agreement from 5/17 to 8/17. This is retrieval agreement, not independent
identity accuracy or accepted geometry coverage. Both query arms returned
candidates for all 38 searchable names; two punctuation inputs were retained
without searching. Four requests completed in 66.103 seconds and were cached.

Country scoping improved Java but lost Bora Bora because saved France evidence
yielded `FR` while the expected gazetteer record uses `PF`. Fourteen additional
searchable synthetic inputs are blocked by the existing feature parser, which
does not cover classes such as mountain ranges, hills and cemeteries. Candidate
coverage and parser limitations must not be reported as absence from Wikidata
or absence of a real place. No country conversion, feature class, acceptance
threshold, date rule, new entity or geometry assignment was promoted. The
original two accepted/eight unresolved decisions and main model are unchanged.

See [complete test, per-input results and limitations](GEOGRAPHY_CANDIDATE_COMPARISON_40_2026-10-22.md).
The additional 30 inputs have candidate diagnostics only; nine have eligible
exact-QID tag candidates whose full geometry was not tested. Production rules
above remain in force. General structured context and country-code handling
still require discussion before implementation.

### 9.2 Approved broader-polygon preference — 22 October 2026

The user prefers a supported broader local polygon over unresolved geography when a precise location cannot be established. Country-wide and larger fallback approximations are excluded. This does not exclude the exact boundary of an entity that is itself a country.

Follow the [broader-polygon preference](GEOCODING_HIGH_LEVEL_PROCESS.md#approved-broader-polygon-preference--22-october-2026): make approximation explicit, retain the source object and supporting evidence, and preserve the original entity ID and identity-matching status. A supported broader area does not prove the exact place identity or footprint. Do not introduce guessed shapes, buffers, unions, or new sources.

This is an approved preference, not an implemented selector change. Maximum extent, broader-area selection, and machine-readable approximation metadata require agreement before implementation. No new field, status, area threshold, or parent-selection algorithm is specified here. Existing model outputs and the 40-input diagnostic remain unchanged.

Subsequent approval applies to the **ten-example test only**: choose the smallest supported existing local polygon covering the plausible locations; mark it approximate and exclude country-wide and larger approximations. The [verified cached test](GEOGRAPHY_LOCAL_POLYGON_10_2026-10-22.md) retained two accepted geometries, added the Hoosick Falls village polygon (3.847 km²), and retained seven unresolved inputs. Its experimental approximation metadata stays in the sample audit; no production schema or model is changed. Identity/name/context requirements remain in force. A numerical extent limit and general production metadata still require agreement.

### 9.3 Wikidata coordinate uses — approval, 22 October 2026

The owner approved available Wikidata coordinates (`P625`) for (1) Nominatim retrieval context, (2) stronger supporting context for unresolved locations, and (3) an unchanged last-resort Shapely Point when no other supported geometry is available after the approved source attempts. This supersedes earlier identity/context-only restrictions for coordinates, not for Wikidata shapes. Follow the [complete coordinate rule](GEOCODING_HIGH_LEVEL_PROCESS.md#wikidata-coordinate-approval--22-october-2026).

Keep existing IDs and matching status. The owner's subsequent correction removes the extra confirmed-input identity gate for the final coordinate fallback: an available saved exact-name/alias-linked Wikidata candidate coordinate can supply a synthetic input's Point. Record its source QID, candidate-only identity status and uncertainty; do not assign that QID to the input. A candidate's own coordinate is not independent proof of identity. Do not choose conflicting candidates/coordinates, impose a new distance/radius threshold, or accept a nearest result silently. Preserve source coordinate values and precision; convert to `Point(longitude, latitude)` without moving, buffering or averaging. Store original statements, globe/CRS, dates/qualifiers, snapshot/retrieval evidence and the fallback reason in the existing audit and source fields. The 13-column compatibility view and model-only geometry pointer remain unchanged.

Use the agreed snapshot-first source priority and cached evidence. The [corrected ten-example coordinate test](GEOGRAPHY_COORDINATE_10_2026-10-22.md) retained three geometries and added the unchanged Wikidata Points for Tinian Town and Sunharon Bay: five with geometry and five unresolved, with zero new requests and four cached responses reused. Nine focused tests passed. Both inputs retain synthetic IDs and candidate-only uncertainty in the audit. This supersedes the initial three/seven result blocked by the extra identity gate. Production model/selection, IDs and prior local-polygon outputs remain unchanged.

## 10. Evidence, required checks and explicit exceptions

Supporting manifests, catalogs, page/checkpoint files, query evidence, event-selection reports and geocoding audits are not new business tables. Each release must retain URI/path, checksum, schema/media version and record locator where a row uses an immutable reference. A local cache path alone is not a recoverable off-device artifact. Do not truncate unknown source fields or replace native statement evidence with just a QID pair.

Before an implementation can claim completion:

| Check | Required result |
|---|---|
| Input and decision accounting | Exactly 309,864 Mentions for the pinned input, unchanged original fields/order/IDs, complete stage/reason accounting and separate NER/matching scores. |
| Identity and page keys | Unique `(entity_id, type)` pairs and valid composite mention FKs; QID-level references exist without multiplying assertions; page-key pairs complete; no talk IDs, Index-as-page-ID, cache-only entity expansion or extra Daniel mentions. |
| Scope-concentration measure, when supplied | Matched QIDs only; exclude synthetic IDs. Both page counts use the same snapshot/language/link rules, with source-page deduplication and full Daniel page scope. Report missing coverage and unknown denominators. Apply the provisional 5% rule to measured MISC QIDs: exclude <0.05 from Event retrieval, keep >=0.05; retain model records. Keep this measure separate from `Entities.importance`. |
| Events | Native root/snapshot/path evidence; original QIDs; all approved event types; at least two distinct direct retained Daniel QIDs after the existing MISC retrieval filter; maximum linked-entity score >=2%, missing contributes zero with missing evidence preserved, no missing-score bypass; incoming/outgoing acquisition coverage reported. The separate MISC retrieval cutoff remains 5%. |
| Assertions | Reconcile retrieved eligible statements = retained mapped base rows + exact exclusions + explicitly reported unmapped/ambiguous/blocked cases, deduplicated by source statement. Report all categories and ranks. No silent loss through join/mapping/rank filters. |
| Geometry | At most one accepted object per place; failed attempts retained; source and CRS known; valid nonempty Shapely/WKB round trip before delivery. |
| Contract coverage | All ERD fields, nine Daniel fields, 16 matching CSV fields, 26 legacy assertion fields, full nested reference/attempt payloads, geometry compatibility fields and versioned catalog columns retained or explicitly unavailable. |
| Reuse and release | Pinned hashes and request scope; existing verified artifacts reused; missing references/counts visible. No cloud/data/Agent completion claim based only on this document. |

Different resolved types for one QID are not an unresolved conflict: keep distinct `(entity_id, type)` combinations. Event membership coexists with other types. MISC classification is not an open decision. Relations stays at QID level, with one base row per source assertion.

The following cases must be brought back with exact IDs, values and counts before adding logic: differing Daniel fallback names when both Wikidata labels are missing; ambiguous/conflicting mappings or unsupported non-native predicate semantics; incompatible multivalued event dates/classifications; source-page input/lookup conflicts; partial-date interpretation required for geometry selection; or a concrete specialist geometry source. Events without English/Japanese or Daniel names use the approved QID display fallback in section 6. Preserve raw evidence while a required decision is pending, and report the affected population explicitly.

Downstream interfaces approved on 19 October 2026: separate graph entities use `QID::type` with original `wikidata_id`; relations keep QID endpoints, resolved to the separate typed entities without copying assertions. `Geography.geometry_ref` is null or `{file,place_id,sha256}` identifying GeoParquet/file/place/checksum; it is not exported in graph JSON; the loader returns Shapely and errors on broken references. Agent integration, spatial CRS compatibility and reverse-view evidence checks remain implementation work. These interfaces do not change source population or matching. Final graph sources remain omitted; provenance stays in this model and supporting artifacts.

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

Latest user decisions govern name priority, Wikidata-only assertions, included event links in Relations, recognition through the approved Q1190554 hierarchy with its accepted limits and no manual exceptions, two-distinct-retained-Daniel-QID event minimum with maximum linked-entity score >=2%, missing contributes zero with missing evidence preserved, no missing-score bypass, per-mention synthetic IDs, no new Daniel entities, and Shapely objects with Geography model pointers, omitted from graph JSON. No physical model tables or new production outputs are created by this specification.

### Correction: retain historical relations

The user withdrew the pre-1900-end exclusion after reviewing the 34 excluded statements. Current policy v1.1.0 retains these statements with original dates and no 1900 start floor. Earlier run directories and their manifests remain immutable historical records, not the corrected current population. The new replay is `GG_Data/pipeline/outputs/poc_10k_relations_original_historical_dates_20261020`; require its successful manifest before use. No event-root/source decision is changed by this correction.
