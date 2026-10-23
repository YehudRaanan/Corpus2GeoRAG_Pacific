# Matching penalties: frozen 30-case review, 23 October 2026

Status: **PAUSED FOR OWNER CONSULTATION**. No full matching run, new 10K identity population, or new Geography assignment was started. The preliminary automated gate remains `STOPPED_FOR_CONSULTATION`; its original report is preserved.

The owner approved type/relevance penalties, model relevance columns, a 20–30-case comparison and continuation only without degradation. The earlier POC instruction requires consultation for new unexpected cases. The test preserved every previously correct match, but review of two changed QIDs exposed a new wrong historical identity for Malaya. No new temporal matching rule or manual QID correction has been applied.

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

Pending owner decision: continue with the current formula and retain these known diagnostic failures for later work, or discuss the new Malaya period mismatch before continuation. No temporal entity-matching rule is implemented or proposed as an automatic change.
