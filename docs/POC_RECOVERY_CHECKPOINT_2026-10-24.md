# Fixed 10K POC recovery: 24 October 2026

Status: **RUNNING_DOCUMENTED_GEOGRAPHY_WORKFLOW**. The offline worker restarted
at 19:59:40 on 24 October, Asia/Jerusalem (UTC+03). This is not completion of
Geography or final spatial integration. The original 23 October 17:30 target
was missed in the locked session. The stopped-worker evidence below is retained.

## Correction of the consultation request

The owner directed use of the existing agreed workflow. The current geocoding
policy explicitly supersedes historical date rejection gates, and population
S2T section 9.7 says an uncertain date cannot leave an available geometry
unresolved. The old sample helper's exception was an implementation mismatch,
not a new business-policy decision. The earlier consultation request was
incorrect. Upstream selection-date precision and calendar safeguards remain
separate and unchanged.

Local commit `34d394b` aligns the ranking caller with that rule. Original source
dates stay unchanged in `supplied_dates` and `tags`; unreadable bounds are also
recorded in `unsupported_source_dates` with `UNSUPPORTED_SOURCE_DATE`. Readable
bounds still supply the existing outside-period warning. Unknown temporal
evidence supplies no historical bonus, and all other score weights, tie rules
and geometry-availability rules remain unchanged. No new date interpretation
or normalization is performed.

Verification: 44 focused tests passed; 219 wider tests passed with the same
three expected failures; Ruff passed. A regression reproduced the original
`~1571` failure before the correction and now covers every observed date form,
mixed readable/unreadable bounds, readable outside dates, raw evidence
preservation and continued selection. No dependencies were installed.

New isolated worker and evidence: `recovery_20261024_workflow/` within the
original bundle. Ranking output: `recovery_20261024_workflow/geography_ranked_v5/`.
The v3 and v4 output directories and their launch/failure evidence are preserved.
The new parent directory uses lossless NTFS compression from the start. Network
connections remain blocked; exact saved request receipts are reused in place.
Remaining estimate at restart: 35–60 minutes, target 21:00 on 24 October,
Asia/Jerusalem; next checkpoint 20:15. Final model and spatial checks are pending.

## Scope and authorization

The owner approved offline recovery of the existing 1,272-location run on
24 October, with 45–90 minutes remaining, a 21:00 target, and intermediate
checkpoints. Preserve entity identities, matching, ranking, source selection,
and old outputs. No new source requests, experiments, or dependencies were
authorized. A new data/rule problem requires consultation under the existing
[approved continuation](POC_COMPLETION_STOP_2026-10-23.md).

## Verified recovery

- Original bundle: `GG_Data/pipeline/outputs/matching_penalty_poc_20261023/`.
- The original `geography_ranked_v3/progress.json` reached 1,272/1,272 acquisition
  inputs and 2,694 request lookups, then failed with `MemoryError` while writing
  candidate JSON. Its `candidates.json` is zero bytes; final ranking was absent.
- Local code checkpoint `c83ca2e` streams JSON into a temporary file and replaces
  the destination only on success. A cache-only mode requires exact URL/parameter
  receipts, uses the saved files in place, and fails before a request on a miss.
- The recovery worker blocked `socket.connect` and reused all 2,694 lookups from
  saved responses. No network source acquisition was performed. Old files were
  not replaced or removed.
- New output: `geography_ranked_v4/`. It contains a complete candidate JSON of
  2,122,100,302 bytes, plus input, evidence and coordinate files. The candidate
  file and new directory use lossless NTFS compression to reduce disk use.
- Ranking completed 37/1,272 inputs, then stopped on the next input. There is no
  completed ranking audit, GeoParquet, final Geography model, or final integration
  report. `recovery_20261024/complete_worker.py` is prepared but was not launched.
- Focused tests: 22 passed. Wider Agent, model-date, pipeline, export and Geography
  suite: 197 passed, three existing expected failures. The expected failures
  concern composite point-query date filtering. Ruff passed. No packages were
  installed. Evidence: `recovery_20261024/test_results.json`.

## Exact blocking record

Input: Psel river, `Q1133871`; selection date `1941-12-07`.

One saved Nominatim reverse candidate is Kremenchuk (raw name `Кременчук`),
OSM node `265058149`, candidate QID `Q156724`, with `start_date="~1571"`.
The candidate remains evidence, not an accepted Psel identity. Receipt:
`geography_ranked_v3/sources/2b493d03ab95e62db72f8e083fb94084493db757d702fa9e7fd1d43c5ccd3fab.json`.

`geography_local_polygon_sample.date_eligible` accepts only numeric
`YYYY`, `YYYY-MM`, or `YYYY-MM-DD` strings. `score()` evaluates temporal data
before selection, so this candidate stops the run even though it has another
QID. Failure evidence is `recovery_20261024/rank_failure.json`; last progress is
`geography_ranked_v4/progress.json`. The worker exited and was not restarted.

At the initial pause a new owner decision was requested. That request is
superseded by the workflow reconciliation above. Do not remove `~`, replace
the raw date or drop the candidate. Preserve its receipt and uncertainty under
the existing approved rule.

A read-only scan of `start_date` and `end_date` in all saved v3 receipt responses
found 20 unsupported field occurrences. This counts receipt fields, not unique
places, affected inputs, or candidates that will reach scoring. It does not
establish that every occurrence blocks this population.

| Raw field/value | Receipt occurrences |
|---|---:|
| start `985` | 1 |
| start `~1571` | 1 |
| start `-2000` | 2 |
| start `-0600` | 1 |
| start `-0106` | 1 |
| end `-0106` | 1 |
| start `-3200` | 1 |
| start `482` | 1 |
| start `-0320` | 1 |
| end `-0064` | 1 |
| start `-0063` | 1 |
| start `887` | 1 |
| start `2022-04-21 00:00:00` | 1 |
| start `~65500000 BC` | 1 |
| start `~1600` | 1 |
| start `Y-75E7S3` | 1 |
| start `2021-01-01 00:00:03` | 1 |
| start `January 9th, 1788` | 1 |
| start `756` | 1 |

No new date-format parser was authorized or needed. Unreadable temporal values
remain evidence with uncertainty under the current geometry-selection rule.

## Remaining work and protection

Finish ranking without source requests, populate model Geography, and run full graph,
date-join and spatial checks. The previously verified graph has 7,710 nodes,
16,466 assertions and 32,899 directional views, SHA-256
`70be8618fbb7a5333af15564032f02c3977cc97fd02aa4271a64a0fe47316bc4`.
This prior graph check does not prove final model Geography integration.

The denominator remains all 1,272 LOC rows (925 QID and 347 synthetic identities)
within the fixed original 10,000 mention positions. Existing Tunis/Brisbane POC
limitations remain accepted, not corrected. Structural and spatial consistency
checks cannot prove historical identity or boundary accuracy.

Protection: **Local checkpoint only**. No push was made. The branch is divergent
from its upstream; generated ignored outputs and source caches are not protected
on GitHub. Existing unrelated user changes remain outside recovery commits.
