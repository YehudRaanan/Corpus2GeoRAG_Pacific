# Fixed 10K POC completion: consultation checkpoint

Updated: 24 October 2026. Status: **STOPPED_AT_OWNER_REQUEST**.

## Final saved checkpoint: 24 October

The owner declined the proposed 25–40-minute extension and directed saving this
checkpoint. No recovery worker is running and no new run was started.
All 1,272 inputs were ranked: 1,246 geometry proposals and 26 unresolved rows.
The worker exited during its protected-input hash check; the incomplete traceback
does not establish an exit cause. Final ranking audit/verification, populated
Geography and final spatial integration remain incomplete. Both saved candidate
files match the original SHA-256 baseline. D: had 1.28 GB free at that check.
The proposed 21:10 target was not approved; no completion deadline is active.
See [the final recovery record](POC_RECOVERY_CHECKPOINT_2026-10-24.md) for exact
files, counts, uncertainty, storage operations and continuation requirements.
Protection: **Local checkpoint only**; ignored outputs are not backed up on
GitHub. The running-status entries below are retained as historical evidence.

## 20:15 checkpoint: disk space recovered, same worker resumed

The current worker was suspended before D: filled during candidate serialization.
No process was terminated and no file was deleted. Lossless NTFS compression of
the 2,597 saved v3 JSON receipt files reduced physical storage from
6,363,675,860 logical bytes to 1,457,011,420 stored bytes. This changes storage
attributes, not JSON content, request parameters or source dates. The running
worker's protected-input SHA-256 checks remain the final content verification.

The same PID 7312 resumed at 20:15:03 with 5,107,908,608 bytes free on D:.
Evidence: `recovery_20261024_workflow_v2/storage_recovery.json`. Candidate writing,
ranking and final model/spatial integration continue. Scope unchanged; estimated
remaining 25–40 minutes, target 21:00 on 24 October, Asia/Jerusalem (UTC+03),
next checkpoint 20:30. The previous v3 content and all stopped-run evidence
remain preserved; its receipt files now have compressed storage attributes.

## Current local-write recovery: 24 October, 20:04 Asia/Jerusalem

The 19:59 worker stopped after 71 cached inputs on `WinError 5` while atomically
replacing its local `progress.json`. No source acquisition or ranking decision
failed. The file ACL allows modification; a native Windows probe reproduced
the same error with an ordinary reader holding the destination open and
confirmed success after that reader closed. The exact original lock owner is
not known. No permission or access-control setting was changed.

Local checkpoint `36f3069` bounds retries of only Windows local replacement
errors 5/32/33 to three attempts, with 0.05/0.1-second waits. Persistent failure
still raises and retains the original destination. The source HTTP retry policy
is unchanged. Validation: 47 focused tests, 222 wider tests passed with the same
three expected failures, and Ruff passed. Native probe evidence is retained.

The new offline worker started at 20:04:03 under
`recovery_20261024_workflow_v2/geography_ranked_v6/`. All preceding attempts are
preserved. It uses the same v3 saved responses and blocked-network contract.
The 21:00 target and 20:15 checkpoint remain unchanged; final outputs are pending.

## Workflow reconciliation and restart: 24 October, 19:59 Asia/Jerusalem

The owner directed use of the already documented workflow. Review confirmed
that population S2T section 9.7 and the current geocoding policy supersede the
older source-date veto: uncertain dates stay in metadata and cannot stop
selection of available valid geometry. Asking for a new policy decision was
incorrect. The selection-date/calendar safeguards for upstream Event/Relation
evidence are separate and remain unchanged.

Code checkpoint `34d394b` corrects the ranking caller: retain raw unreadable
source bounds with `UNSUPPORTED_SOURCE_DATE`, keep comparing readable bounds,
and award no unsupported historical evidence points. No new parser, inferred
date, source, identity assignment or selection threshold is introduced. The
focused suite passed 44 tests; the wider suite passed 219 with three existing
expected failures. Ruff passed.

The offline worker restarted at 19:59:40 in
`recovery_20261024_workflow/geography_ranked_v5` under the same run bundle,
reusing v3 exact request receipts with network connections blocked. All prior
outputs and failure receipts remain unchanged. Remaining estimate at restart:
35–60 minutes, target 21:00 on 24 October, Asia/Jerusalem (UTC+03), next status
checkpoint 20:15. Final model and spatial integration are still pending.

## Superseded safe pause: 24 October, 19:51 Asia/Jerusalem (UTC+03)

The owner approved a 45–90 minute offline recovery on 24 October. The previous
worker had acquired all 1,272 inputs but failed while serializing candidate
evidence with a `MemoryError`; this was not a completed Geography ranking run.
The recovery uses streaming atomic JSON writes and exact saved-response reuse,
with network connections blocked. The original `geography_ranked_v3` is unchanged.

The new `geography_ranked_v4` saved the complete candidate JSON, then stopped
after 37/1,272 ranked inputs. The next input is Psel (`Q1133871`), selection date
`1941-12-07`. One retrieved reverse-geocoding candidate is Kremenchuk, OSM node
`265058149`, QID `Q156724`, with raw `start_date="~1571"`. The existing temporal
validator raises `ValueError: Unsupported source date: ~1571`. No interpretation,
candidate exclusion, rule change, retry, or new request was made after this stop.

Final ranking, model Geography population and complete spatial integration are
still pending. The prepared final integration worker was not launched. Recovery
code passed 197 tests, with three existing expected failures. Code checkpoint:
`c83ca2e` (local only). See [the recovery record](POC_RECOVERY_CHECKPOINT_2026-10-24.md)
for evidence and the subsequent reconciliation with the already approved rule.

The earlier 23 October checkpoints below are historical.

## Approved continuation: 15:36 Asia/Jerusalem

The owner approved Nominatim connection retries and the revised 90–120 minute
remaining estimate. Approval was received after the earlier proposed checkpoint;
the verified continuation clock was 15:28 on 23 October. The updated target is
17:30, with the next status checkpoint at 15:45, Asia/Jerusalem (UTC+03).

`geography_ranked_v3` started at 15:36, reusing the exact URL/parameter receipts
from `geography_ranked_v2`. The older output and failure evidence are unchanged.
Retry attempts are saved before each request; connection failures alone allow
three total attempts with 10/30-second waits. The earlier pre-policy connection
failure counts conservatively against the first uncached request during replay,
because that older stop did not record its exact parameters. A timeout, HTTP
error, invalid data or interrupted attempt still requires consultation. Nine
focused tests and Ruff passed before launch. No identity or ranking rule changed.
Final Geography/model population and spatial checks remain pending.

At the 15:45 checkpoint, the live worker had completed 276/1,272 inputs and
556 request lookups (including cached replay). No new failure was recorded.
Free D: space was 9,559,719,936 bytes. The combined Agent/pipeline/export/
Geography suite passed 192 tests with three existing expected failures.
Implementation and approval notes are in local commit `e3c5a83`; no push was
made. Final outputs remain pending, with the 17:30 target unchanged and the
next checkpoint at 16:15, Asia/Jerusalem.

## Latest safe pause: 14:14 Asia/Jerusalem

The Geography worker exited with code 1 during a Nominatim reverse lookup:
`urllib.error.URLError: <urlopen error [WinError 10065] A socket operation was
attempted to an unreachable host>`. The last completed-input checkpoint is
162/1,272; 327 response files remain saved. This Nominatim code path does not
apply the existing connection retry policy. No retry or replacement-source
request was started after this stop. Evidence is in
`geography_ranked_v2/failure.json` and `geography_ranking_v2.log` under the run.

No data/ranking exception was established. Final Geography/model population and
full spatial integration remain pending. The graph and model-date Agent checks
below are complete. Revised continuation estimate: 90–120 minutes remaining,
approximately three hours total for this completion task; proposed completion
23 October at 16:15 Asia/Jerusalem, next checkpoint 14:45. Owner approval is
required for the revised estimate before continuation.

## Current continuation checkpoint

Verified on 23 October at 14:01 Asia/Jerusalem:

- All 391 candidate coordinate records are cached; no identity was added.
- Owner approval excludes only explicit non-Earth P625 coordinates from Earth
  geometry candidates and search anchors. Original statements remain in evidence
  with reason `NON_EARTH_COORDINATE`; IDs and ranking weights are unchanged.
- Geography ranking restarted in `geography_ranked_v2`, preserving the earlier
  stopped directory. All 1,272 inputs remain in scope. Final Geography population
  has not completed.
- Draft graph `graph_export_20261023/graph.json` has 7,710 nodes, 16,466 source
  assertions and 32,899 directional views. Readback verification passed. Its
  SHA-256 is `70be8618fbb7a5333af15564032f02c3977cc97fd02aa4271a64a0fe47316bc4`.
- Events Q115861680 and Q17193309 retain explicit earliest-start/latest-end
  bounds and omit the optional scalar point date, as approved. All original
  point dates remain in the model. No new range is inferred from them.
- Existing catalog serialization keeps both an assigned category and the
  `UNRESOLVED` state when directional views share a predicate. Each assertion
  retains its original category. No Level 1 category is inferred.
- Focused verification: 11 Geography tests and 17 graph-export tests pass.
  Agent validation against the actual draft graph and model dates has passed.
  Full model-backed Geography integration remains pending.
- The final Geography package now retains the existing generated `mapping/`
  files byte for byte and records their relative file hashes. This fixes a
  packaging omission; it does not regenerate mappings or change graph content.
  The combined Agent, pipeline, Geography and export suite passed 187 tests,
  with three existing expected failures, at 14:07 Asia/Jerusalem. The command
  uses Anaconda Python with the existing Agent `.venv/Lib/site-packages`
  appended to `sys.path`; no dependencies were installed.

These are intermediate results, not completion of the fixed 10K POC. The
sections below preserve the earlier consultation context.

Subsequent owner replies approved both proposals below: current Wikidata
fallback for missing candidate-coordinate records, and earliest Event start /
latest Event end without a 1900 floor. Two further questions were marked
"Discuss first". Audit then confirmed that reverse-view delivery/category
preservation and partial/coarse date selection were already defined; these
must not be reopened as new business decisions. The graph S2T has been
reconciled with the existing reverse contract. General calendar conversion
and a new JSON date-object interface were not approved. Existing native
calendar/precision preservation and limited Julian-year rules remain in force.

Saved candidate-record continuation code and the geometry batch-loader change
passed 24 focused existing/new tests; the candidate continuation also passed
Ruff. Candidate acquisition resumed on 23 October at 13:36 Asia/Jerusalem.
Agent integration continues independently. Full Geography ranking, final model
and graph/Agent integration have not completed at this checkpoint.

The implementation can retain scalar native time strings in the existing graph
fields and read precision/calendar from Events and Relations through the same
model directory used for Geography. This avoids a new JSON date-object format.
Event joins use the existing QID; relation joins use the assertion ID, including
`source_edge_id` for reverse views. Calendar-sensitive cases outside the approved
comparison rules must raise an explicit error rather than assume Gregorian dates.

The owner approved completion of Geography for all 1,272 LOC targets, model
verification, graph JSON export and Agent integration, with independent work in
parallel. Matching, source selection and ranking must remain unchanged. New data
or rule problems require consultation before continuation.

## Verified starting state

- Run: `GG_Data/pipeline/outputs/matching_penalty_poc_20261023/`.
- Model: 8,002 typed Entity rows, including 2,717 Events; 16,466 Relations.
- Geography target denominator: 1,272 (925 QID and 347 synthetic identities).
- All four prior Geography retrieval arms are cached. Final Geography ranking
  and population have not run for this denominator.
- At this starting checkpoint, graph JSON and Agent integration were pending.

## Geography stop

The existing candidate-record phase queried the agreed BigQuery snapshot and
checked the saved Wikidata archive. It stopped with:

```text
ValueError: No available Wikidata version: Q104598646
```

This is a **candidate-only** record for synthetic input
`SYN_b203142d3620582533d6bc27`, Daniel name `Kupiansk`, source page
`Battle of Stalingrad`. WHG supplies Q104598646 as a possible geographic
candidate. It is not an accepted entity identity and must not replace the SYN
ID. The failure does not establish that current Wikidata lacks the record.
The query response remains cached. No completed candidate-record artifact or
final Geography model was written.

Approved decision: use the agreed current Wikidata source for missing
candidate-only records, with cache reuse. If no record is available there,
record the missing coordinate evidence and continue with other retrieved
geometry candidates. Do not invent coordinates or change entity identities.

## Graph date stop

The Event model preserves raw Wikidata time values. The graph contract expects
scalar dates. Ten Events have conflicting explicit start/end bounds: four start
fields and seven end fields, with the Philippines Campaign in both groups.
All these values have day precision and the Gregorian calendar.

| Event QID | Field | Supplied values |
|---|---|---|
| Q23790563 | start | 1897-04-22; 1897-04-28 |
| Q45312128 | start | 2016-10-04; 2016-10-06 |
| Q46333 | start | 1934-10-15; 1934-10-16 |
| Q696462 | start | 1941-12-07; 1941-12-08 |
| Q155620 | end | 1942-05-18; 1942-05-29 |
| Q189266 | end | 1945-05-07; 1955-01-21 |
| Q2708093 | end | 1923-05-25; 1923-05-26 |
| Q4159143 | end | 1942-07-09; 1942-07-10 |
| Q45322684 | end | 2012-05-04; 2012-05-05 |
| Q696462 | end | 1942-05-08; 1942-05-10 |
| Q8641370 | end | 1944-08-25; 1944-08-30 |

Seven further Events have multiple point dates and already-approved derived
ranges. They do not require a new selection rule. The existing explicit-bound
minimum/maximum rule is documented for Relations, not Events. The population
S2T section 7 preserves Event dates without preferred-value selection; the graph
S2T requires consultation on incompatible or multiple values.

Approved decision: for graph Event bounds only, use earliest supplied start and
latest supplied end, without a 1900 floor. Preserve every original date and its
evidence in the model. For example, the Eastern Front graph end would be
1955-01-21 rather than 1945-05-07. This rule is now implemented in the draft
graph described in the current checkpoint above.

## Parallel Agent inspection

The current loader requires the already-approved QID-to-typed-node endpoint
index, model-backed Shapely access, exact native relation IDs and shared
assertion identity for reverse views. These interfaces are now implemented.
Validation against the draft graph and all model date joins passed: 7,710 nodes,
2,717 Events, 32,899 views and 16,466 distinct assertions, with zero failures.
The saved report is `graph_export_20261023/agent_integration_report_20261023.json`
under the run directory. Its focused suite passed 174 tests, with three existing
expected failures; this does not yet verify the unfinished Geography model.
Optional Event kind can be omitted under the existing graph contract.
Graph release metadata must be supplied explicitly when export is run.

Workers first reached a safe pause for consultation, then resumed under the
approved rules. No source IDs, matching assignments or ranking weights change.
