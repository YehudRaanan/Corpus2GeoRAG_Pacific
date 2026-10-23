# Fixed 10K POC completion: consultation checkpoint

Date: 23 October 2026. Status: **GEOGRAPHY_RUNNING_GRAPH_WRITTEN_AGENT_CHECK_PENDING**.

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
