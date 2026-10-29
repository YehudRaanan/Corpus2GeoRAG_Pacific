# Source-content filter: verified 100-page preparation

Date: 29 October 2026. Worktree: `D:\Projects\GeoAI-luke-pilot-20261028`.
Policy: `article-source-v1`. This delivery prepares later matching runs. It does not run the model or create new identity assignments.

## Result

| Saved scope | Original rows | KEEP | EXCLUDE | REVIEW |
|---|---:|---:|---:|---:|
| 3 pages / 4 revisions | 535 | 255 | 236 | 44 |
| 10 pages | 3,785 | 2,427 | 1,030 | 328 |
| 100 pages / 132 revisions | 40,070 | 23,910 | 12,272 | 3,888 |

All original rows and columns are unchanged. New columns contain the source decision, reason, raw positions, section path, evidence, revision hash, policy and masked matching context. KEEP is source eligibility, not proof of correct entity extraction.

Of 23,910 KEEP rows, 4,004 are DATE and remain outside QID matching under the existing policy. The remaining 19,906 rows form 11,699 page/revision/name/type groups. Candidate preparation produced 2,213 exact group–QID pairs and 13,441 model jobs. No job was sent to the model. The QID inventory is unchanged, so jobs can still exist for inventory entities without eligible mention evidence.

## What happens to the previous unresolved result?

The table below crosses the unchanged historical export with the new source decisions. These are not results from a new matching run.

| Source decision | Previously matched | Previously unresolved | Previously DATE-excluded |
|---|---:|---:|---:|
| KEEP | 10,862 | 9,044 | 4,004 |
| EXCLUDE | 2,672 | 6,811 | 2,789 |
| REVIEW | 1,054 | 2,255 | 579 |
| Total | 14,588 | 18,110 | 7,372 |

Of the former 18,110 unresolved mentions, 9,044 remain matching cases in selected source content. The other 6,811 are excluded by source rules; 2,255 need source review. Neither group has gained a QID. The 2,672 previously matched EXCLUDE rows also leave the new matching scope: source policy applies equally to successful and unsuccessful matches. Historical outputs remain unchanged.

## Code walkthrough

1. [`filter_source_content.py`](../../GG_Data/entity_resolution/hundred_page_pilot/filter_source_content.py) is the new pipeline step. It verifies the saved revision against its hash and saved page/revision response, finds each original passage and mention span, classifies that span, and appends evidence. It writes a new Parquet file and summary. Missing, repeated or nonexact placement stays REVIEW. No fallback guesses a position.
2. [`prepare_candidates.py`](../../GG_Data/entity_resolution/hundred_page_pilot/prepare_candidates.py) validates the policy and groups KEEP rows only. Excluded/review rows cannot change type uniqueness, exact pairs, protected candidates or matching contexts. Existing identity, trigram, candidate-limit and DATE rules remain in effect.
3. [`report.py`](../../GG_Data/entity_resolution/hundred_page_pilot/report.py) checks that groups and contexts match eligible inputs. A later authorised inference export will retain every row and separate EXCLUDED_SOURCE, REVIEW_SOURCE, EXCLUDED_DATE and genuine unresolved statuses. Frozen reference bytes remain unchanged; only eligible reference anchors enter filtered checks. Different source policies cannot be compared as a model-only change.
4. Colocated tests cover source roles, row preservation and integration. The [pipeline README](../../GG_Data/entity_resolution/hundred_page_pilot/README.md#source-filter-for-subsequent-runs) gives the execution order and commands. Training code is not changed.

## Rules checked on saved examples

| Example | Decision | Reason |
|---|---|---|
| Greenwood Press, row 6075 | EXCLUDE | Citation publisher |
| Australian War Memorial, row 38129 | EXCLUDE | Citation publisher, even though historically matched |
| Tenaru River, row 114184 | KEEP | Substantive quotation |
| Albert Schmid, row 114189 | EXCLUDE | Nested citation inside a quotation |
| Naha, row 6171 | KEEP | Displayed thumbnail caption |
| Japanese, row 312957 | EXCLUDE | Hidden prefix in a supported ship display mode |
| Japan, row 1259644 | KEEP | Displayed flag-template name |
| Flag variant 1912, row 312936 | EXCLUDE | Template control |

Unknown nested templates do not inherit KEEP from an enclosing infobox. Explanatory reference notes, ambiguous inline media labels, galleries and malformed constructs stay REVIEW. A citation inside any otherwise eligible construct remains excluded. Raw Text is preserved; a separate context masks excluded and uncertain spans to prevent nearby citation/control content entering inference.

The final reason counts include 8,566 citation occurrences, 623 bibliographic-section occurrences and 577 related/external-link-section occurrences. REVIEW includes 1,487 explanatory-reference occurrences, 1,099 unknown-template occurrences, 805 partial-boundary overlaps and 295 ambiguous/nonexact placements. These reasons describe source content, not entity truth.

## Difference from the earlier proposed audit

The earlier audit proposed 23,485 KEEP, 11,684 EXCLUDE and 4,901 REVIEW rows. The tested rules now produce 23,910 / 12,272 / 3,888. All 11,684 prior exclusions remain excluded. Of prior KEEP rows, 128 move to EXCLUDE and 939 to REVIEW. Of prior REVIEW rows, 1,492 become KEEP and 460 become EXCLUDE; 2,949 remain REVIEW.

The changes come from tested display parameters and captions, hidden ship prefixes and flag variants, maintenance dates, image fields, tag syntax, unknown nested templates and malformed/boundary syntax. The earlier proposal was not an active production filter. Detailed transitions are saved with the validation evidence.

## Verification and outputs

- Full pilot suite: **197 passed in 20.17 seconds**.
- Ruff and Black checks: all seven changed Python files passed.
- Parallel read-only source review: 23 bounded source checks passed. A separate integration review checked malformed syntax, media/flag fields and empty-input handling. These checks are not a labelled accuracy benchmark.
- Staged validation: 3, then 10, then 100 saved pages; completed in **136.672 seconds**, including filtering and candidate preparation. The 100-page filter itself took **55.359 seconds**; its summary timing ends before final output writes.
- Verified unique row identities, exact equality of all original columns, exact eligible-group coverage, masked candidate contexts, unchanged five source/input files and unchanged raw revision hashes. The saved filter-code hash equals the final production module hash.
- No training, model inference, collection, cloud start, paid query, Geography or graph rebuild. Incremental cloud cost: **US$0**.

Final local output root:
`Data/external/hundred_page_pilot_20261028/template_name_pilot_20261029/source_scope_filter_20261029/verified_v2/`

- `scope_100/filtered/mentions.parquet`: 40,070 annotated rows.
- `scope_100/filtered/summary.json`: policy, counts, evidence hashes and runtime.
- `scope_100/matching/`: eligible groups, exact pairs, candidate jobs and summary; **no model predictions**.
- `validation.json`: staged checks, unchanged input hashes and historical cross-tabs.
- `review_and_completion.json`: checks, proposal transitions and issue log.
- Equivalent `scope_3/` and `scope_10/` outputs are retained. Earlier preliminary outputs are retained separately and are not the final version.

## Runtime, issues and remaining limits

Estimate v1: 45–90 elapsed execution minutes including preflight, excluding approval/environment waits; Epoch reference `6895d880-505d-4fd8-a4f0-ded9cca5eb8e`. First verified preflight clock: 17:24:11; post-approval execution clock: 17:34:39; final verification and local checkpoint times are recorded in the completion evidence. All clocks use 29 October 2026, Asia/Jerusalem (UTC+02). Active work and the exact approval-wait interval were not separately measured; they must not be inferred from elapsed wall time.

A validation-only progress-print error was corrected without changing source data; existing completed output was preserved. Repeated set construction in that local script was replaced with a single precomputed scope set. Source-review edge cases led to regression tests and a fresh `verified_v2` run. No output from the preliminary run is presented as final.

This is a bounded raw-source classifier, not a historical template renderer. REVIEW content needs a later policy or source check. The linked-QID inventory has not been filtered or recollected. Model quality, stop precision and matching accuracy have not been remeasured. A later inference run can change assignments or unresolved totals after candidate/context filtering; this delivery does not predict that result. The separate `what_happened_at` spatial date-filter issue remains open and untouched.

Backup status: **Local checkpoint only** after the task commit. No remote push is authorised by this delivery. Ignored Parquet files and local evidence are not protected on GitHub.
