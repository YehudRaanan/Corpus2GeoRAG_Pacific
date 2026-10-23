# Matching penalties: frozen 30-case review, 23 October 2026

Status: **FULL MATCHING VERIFIED; FIXED 10K REBUILD RUNNING**. On 23 October the owner answered “Continue with the approved formula”. The four known wrong diagnostic cases remain recorded. No manual identity correction or temporal matching rule is added. The original preliminary automated report remains unchanged; `evaluation/reviewed_report.json` closes the gate after checksummed source review and this owner decision. Full matching is complete; the downstream 10K rebuild is not complete.

At 08:10 Asia/Jerusalem (UTC+03) on 23 October, PID 24288 was suspended under the POC consultation rule. Candidate selection completed: 28,402 possible QIDs, including 23,111 page-stage name candidates. Relevance reuses 2,683 measured QIDs and measures 25,719 more. Both English SQL scans and checksums passed; the selected-page aggregation is incomplete. The per-row Python validator contains 150,650 target alternatives. A bounded check of 100 late-target rows took 0.05127 seconds, which makes aggregation of the 575,639,992-byte selected-row file unnecessarily slow. The proposed change is fixed-format validation plus exact membership in the same target dictionary, preserving native filtering, input checksums, coverage checks, redirect rules and all counts. No implementation change to that running measurement was made. Owner approval was requested before replacing the validator and repeating this stage. See the new bundle's `measurement_pause.json`. The approved overall completion target remains 12:10; no new completion result is claimed. The Geography population adapter and cache reuse checks passed 51 focused tests; no new model or Geography assignment has run.

At 08:49 Asia/Jerusalem (UTC+03), the owner approved fixed-format row validation plus exact target-ID lookup. The suspended read-only worker was stopped; its partial output is preserved. The replacement keeps native filtering and all source/checksum/coverage/deduplication rules. Nine focused tests passed, including old/new expression equivalence and rejection of zero-padded or unselected target IDs. A check with the real 150,650 selected target IDs gave identical page sets; 100,000 selected rows took 0.151 seconds including dictionary construction. The repeated measurement uses the separate `full_candidate_relevance_fast/` directory, not the partial result. No matching rules changed. The next checkpoint is 09:05 on 23 October; the overall completion target remains 12:10.

At 08:59:21 Asia/Jerusalem (UTC+03), the repeated English measurement stopped at the independent scoped-link agreement check for Q1081449, Medal “For the Victory over Japan”. All 131,511,582 linktarget rows and 1,669,535,683 pagelinks rows passed checksum and coverage checks. The faster validator completed aggregation; this is a separate source-title lookup defect. The raw saved SQL row for target 1412570 escapes the title’s double quotes with backslashes, but `sql_string()` does not. Only redirect target 32760777 was selected. The saved resolver supplies the canonical title from Georgy Zhukov (page 38888) and List of military awards and decorations of World War II (page 1404204). No source, count or identity was repaired. The process exited; matching and the downstream rebuild did not start. At 09:02, owner approval was requested for the encoding fix, regression test and repeated measurement, estimated 15–25 minutes. See `title_encoding_consultation.json` in the new bundle.

At 09:12 Asia/Jerusalem (UTC+03), following owner approval, `sql_string()` was corrected to encode double quotation marks exactly as the saved MySQL dump. Ten focused tests passed. The new regression replays the actual Q1081449 dump row and both known source-page links, without altering identities or counts manually. The repeated measurement writes only to `full_candidate_relevance_quoted/`; previous attempts remain preserved. The next checkpoint is 09:30 on 23 October and the overall target remains 12:10. Full matching and the model rebuild are still pending.

The owner approved type/relevance penalties, model relevance columns, a 20–30-case comparison and continuation only without degradation. The earlier POC instruction requires consultation for new unexpected cases. The test preserved every previously correct match, but review of two changed QIDs exposed a new wrong historical identity for Malaya. No new temporal matching rule or manual QID correction has been applied.

At 09:20 Asia/Jerusalem (UTC+03) on 23 October, the corrected relevance measurement completed for all 28,402 candidate QIDs: 2,683 reused and 25,719 newly measured. Both language dump checks and scoped-link agreement checks passed, with zero network requests. The quoted-title canonical target 1412570 is present. The checksum-verified result is `full_candidate_relevance_quoted/report.json`; its matching relevance file has SHA-256 `1ab23d27ec33f5ee7186631a57fbb7b97dfacd5ea7a24089ba17341b6a315e84`. A new full matching run started at 09:20 for all 309,864 original mentions, with fresh decisions and the approved scoring formula. The downstream fixed 10K model remains pending. The next checkpoint remains 09:30 and the overall target remains 12:10.

At 09:34 Asia/Jerusalem (UTC+03) on 23 October, independent readback verified all 309,864 matching rows and 13 output-file checksums. The full run reproduced all 30 reviewed diagnostic assignments without change. London is Q84 through the already-matched stage; the page stage made no unsupported global-name match. Counts are 130,579 page matches, 58,510 already-matched matches, 4,711 fresh-WWII matches, 29,969 normalized dates and 86,095 unresolved mentions. These counts are not a population accuracy estimate. Evidence: `full_matching_verification.json`, `matching/manifest.json`, `matching/summary.json` and `matching/london_validation.json`. The same fixed 10K sample rebuild has started. The overall target remains 12:10; the next checkpoint is 10:00 on 23 October.

## Results

| Outcome | Before | After source review |
|---|---:|---:|
| Correct QID | 17 | 18 |
| Wrong QID | 13 | 4 |
| Unresolved synthetic identity | 0 | 8 |
| Previously correct cases lost | — | 0 |

These are 30 deliberately selected diagnostic cases, not a random population accuracy estimate. All 13 wrong identities from the existing 100-case review were included, with 17 supported good matches. Four good fuzzy matches at or near 80% were included. All 30 baseline assignments were reproduced before applying the formula. Both formulas used the same verified source-page and global reference pools; a subsequent production rebuild must create a fresh already-matched pool from all new page-stage decisions.

Formula: raw trigram Dice × 0.90 for a known conflicting type × 0.95 when the highest available English/Japanese page relevance is below 1%. Other factors are 1. Acceptance remains adjusted similarity >=0.80. Existing type compatibility/override rules, dates, stage order and seeded ties remain unchanged.

The 50 candidate QIDs had complete measurement processing: 42 reused verified counts; eight were measured from the saved Wikipedia dumps. No network request was made. A measurement can explicitly be unavailable in a language; this is different from missing processing. All candidate measurements identify the same snapshot and full Daniel page scope.

## Changed QIDs reviewed against saved records

| Case | Text and old assignment | New automatic assignment | Source-based assessment |
|---|---|---|---|
| 55, Malaya | December 1941 invasion targets on `China Burma India theater`; old Q5451 is the Himalayas. | Q1479726, Federation of Malaya; exact alias `Malaya`, adjusted score 1.0. | **Still wrong identity.** Saved Wikidata revision 2378411198 describes 1948–1963 and P571 supplies 1948. The rejection of the Himalayas improved the geography association but did not establish the intended 1941 identity. No automatic date/context rejection rule is approved for this matching step. |
| 94, Dutch East Indies | The 1942 invasion/surrender on `Dutch East Indies`; old Q5317276 identifies earlier company rule. | Q188161, Dutch East Indies; exact label, adjusted score 1.0. | **Correct.** Saved revision 2368162297 describes the Dutch colony 1800–1949, with P571 1800 and P576 values in 1945/1949. Its source-page subject and period fit the text. |

The other wrong QIDs retained by the test are China → Okinawa (Q766445), Nikolaevsk → Mykolaiv (Q41572), and Fort Randall Army → Fort Randall, South Dakota (Q3077995). They remain diagnostic failures; no IDs were manually repaired.

The eight formerly wrong assignments now unresolved are Moore, Kaigun, Building, Manchester, `'s Islands`, Kingdom of, Yuehan Railway and Waco. Their separate synthetic IDs are generated from the original mention IDs under the existing rule.

## Documents, code and actual model migration

ERD, sources-to-model S2T, model-to-graph S2T and Geography workflow now describe the new fields and the current selection policy. Scoring parameters are in `GG_Data/entity_resolution/matching_scoring.py`. New rebuild preflight requires a passed test gate and checksummed candidate relevance. A scoring receipt prevents resuming an old page checkpoint with new scoring inputs. Historical pilot replay remains unpenalized.

The new model version is `GG_Data/pipeline/outputs/matching_penalty_poc_20261023/model_relevance_baseline/`. It contains all 7,995 existing typed Entity rows, with four new relevance columns and `attributes.relevance_basis`. Independent read-back comparison verified that every original value is unchanged; all six copied/written model output-file checksums passed. Mentions and Wiki Pages remain pinned supporting-stage inputs; Geography is not populated by this migration.

| Relevance status | Typed rows |
|---|---:|
| SCORED | 2,771 |
| UNAVAILABLE_BOTH_LANGUAGES | 23 |
| NOT_APPLICABLE_SYNTHETIC | 2,503 |
| UNMEASURED | 2,698 |

All 2,698 unmeasured rows are Event-only type rows. They have explicit nulls; they do not borrow a linked entity's relevance. This baseline migration is not the recalculated pipeline population. Synthetic importance remains separate and unchanged. Geography input preparation now exposes saved text/offsets, type evidence, native coordinates, parent claims and source identifiers from the model; no new geometry is assigned in this step.

Verification: **49 tests passed** across scoring, baseline replay, page scope, model population, Geography inputs and Event population. Ruff passed. The code tests do not establish population matching precision. The full 309,864 matching run and downstream 10K rebuild remain pending.

## Evidence

- Frozen cases and baseline receipt: `GG_Data/pipeline/outputs/matching_penalty_poc_20261023/evaluation/manifest.json`, `cases.json`, `selection.json`, `metadata.json.gz`.
- Automatic attempts, penalties and preliminary hold: `evaluation/report.json` in that bundle.
- Two changed-QID source assessments and the reviewed counts: `evaluation/case_review.json`; this does not change assignments or promote the automated gate.
- Measurement receipt: `candidate_relevance/report.json`; full language evidence is referenced in `matching_relevance.json.gz`.
- Saved records used for the two changed-QID checks: `GG_Data/pipeline/outputs/rebuild_page_scope_20261022/entities/full_records.json.gz` (SHA-256 `d2e7387545dbe47152330a65951f7d95c00b7dfa753ad223ac74425b734722e8`). Input context comes unchanged from the frozen cases and the prior 100-case review.
- Migrated model receipt and independent table checks: `model_relevance_baseline/manifest.json` and `verification.json` in the new bundle.

Owner decision received: **continue with the current formula**, retaining the four known diagnostic failures for later work. No temporal entity-matching rule is implemented. The measurement selection is a superset of raw >=80% candidates over all Daniel inputs, before penalties. It includes page candidates, possible already-matched candidates and WWII candidates; it makes no identity assignment and does not broaden the actual first-stage page pool. Every candidate used by matching must have a completed relevance measurement, including explicit unavailable results.
