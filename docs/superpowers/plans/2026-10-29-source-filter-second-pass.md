# Source-filter second pass implementation plan

> **For agentic workers:** Use superpowers:executing-plans. Parallel read-only reviews can inspect independent citation and display rules; one main owner edits the production module and writes each output directory.

**Goal:** Improve source classification on the saved 100 pages without discarding useful article content or changing original mentions and QID assignments.

**Architecture:** Extend the existing source-filter step with narrow, evidence-backed rules. Use policy `article-source-v2` for new outputs; preserve read compatibility for saved v1 annotations. Compare all changed rows and candidate contexts with the verified_v2 output, without running a model.

**Tech stack:** Existing Python, PyArrow, mwparserfromhell and pytest; no new dependency.

**Spec:** User request in this chat: another pass to improve filtering without damaging content completeness. Existing scope and row-preservation contract: `2026-10-29-source-content-filter.md` and its verification report.

## Choices and constraints

- Recommended approach: small parser-rule changes with source-backed positive and negative tests. Blanket exclusion of ref tags or all template content would lose useful text. A full historical renderer is outside this local task.
- Preserve all 40,070 original rows, columns, text, offsets, types and historical results. Keep previous outputs unchanged in a separate directory.
- Review all 3,888 source-review occurrences, including the 2,255 historically unresolved ones; also check changes to previous KEEP and EXCLUDE rows.
- Do not repair or replace extracted names in this task. A mention crossing prose and citation syntax stays REVIEW unless a source rule proves its existing full span is eligible.
- No training, inference, API calls, collection, cloud spend, Geography, graph rebuild, label changes or full-corpus rerun.
- Keep existing candidate identity, ranking, exact-match, DATE and model rules. Eligible source content and its masked context can change explicitly under v2.
- No target count for REVIEW reduction. Completeness and evidence take priority.

## Review focus

1. A ref containing only a short bibliographic citation can be excluded, but explanatory or mixed prose must not be excluded by a broad author/year pattern.
2. Quote/list templates can display useful content while hiding title/style/control parameters and nested citations.
3. Image caption visibility must not depend on whether an image option follows the caption. Multiple-image and gallery structures need explicit field rules; unsupported forms stay REVIEW.
4. Damaged boundary spans and repeated passages must not gain invented positions or silently changed source text.
5. Source eligibility and context masking must agree; no newly kept candidate may expose citation/control text through context.

## Task 1: Evidence and conservative source rules

Owner: main agent; optional read-only citation reviewer. Depends on duration approval. Exclusive write ownership: main agent.

Files: `GG_Data/entity_resolution/hundred_page_pilot/filter_source_content.py`, colocated `test_filter_source_content.py`.

Interfaces: retain `source_intervals(raw)`, `classify_span(left,right,spans,headings)`, `masked_source(raw,spans,headings)` and `filter_mentions(mentions_path,revisions_path,output)`.

- [x] Inventory actual ref bodies, unknown template families, caption fields and boundary/placement evidence from saved revisions. Record examples and unresolved assumptions. Bound exploration to 10 minutes; unsupported semantic cases remain REVIEW.
- [x] Write failing tests for short citation-only refs versus explanatory/mixed refs; displayed quote/list values versus hidden parameters and nested citations; captions followed by options versus filenames/alt text. Reuse real saved examples plus negative controls.
- [x] Add only rules supported by those examples and tests. Prefer existing parser structure and helpers. Do not infer visible text from unknown template names.
- [x] Assess boundary and repeated-placement cases separately. Record cases that cannot safely improve without span repair or more provenance; do not force their reclassification.
- [x] Run `python -m pytest GG_Data/entity_resolution/hundred_page_pilot/test_filter_source_content.py -q`; all tests must pass, including old preservation and ambiguity controls.

Outcome: precise rule changes with explicit retained uncertainty.

## Task 2: Policy and pipeline compatibility

Owner: main agent; optional read-only integration reviewer. Depends on task 1 rules/interface.

Files: existing `prepare_candidates.py`, `report.py` only if needed, and their colocated tests. No new pipeline step or training changes.

- [x] Add tests that v1 saved annotations remain readable, v2 is explicit, mixed versions fail, and unsupported policy bypass fails.
- [x] Keep a single declared source policy per matching run; update CLI policy choices with minimum changes.
- [x] Verify new KEEP contexts retain visible content and mask excluded/uncertain nested content. Both excluded and reviewed occurrences must remain outside groups and protected candidates.
- [x] Run affected integration tests; do not change identity decisions, candidate thresholds, labels or inference code.

Outcome: a versioned filter that cannot silently mix old and new scope.

## Task 3: Staged comparison and completeness checks

Owner: main agent; independent read-only reviews can overlap task 1/2 tests. Depends on completed source and integration checks.

Files: new ignored data output directory; update existing README and create concise `docs/reports/2026-10-29-source-filter-second-pass.md`.

- [x] Run fresh local 3-, 10- and 100-page source filtering and candidate preparation. Verify original-column equality, 40,070 unique IDs and unchanged input/raw hashes.
- [x] Save a row-level old/new decision and reason comparison. Inspect every distinct rule/structure causing KEEP-to-EXCLUDE or EXCLUDE-to-KEEP transitions, plus all rows of those transitions; preserve questionable cases as REVIEW.
- [x] Check original quotation, factual infobox, table and caption examples remain eligible. Ensure citations, hidden targets, controls and filenames cannot enter candidates or contexts. Distinguish a template-name/rule gap from unclear content.
- [x] Cross-tab the unchanged 18,110 historical unresolved cases against the new policy. Do not claim new QID matches or model accuracy.
- [x] Run full pilot pytest, Ruff and Black for changed Python files. Review only task-related diffs.
- [x] Report counts, recovered useful content, newly excluded metadata, remaining uncertainty, tests, runtime and issues. Make a task-only local checkpoint; no push without permission.

Outcome: verified local filter revision and a clear next-run dataset, with no hidden source loss or model run.

## Estimate and task state

Estimate v1: **45–90 minutes total elapsed execution including preflight**, excluding approval/environment waits; model-derived, not empirically calibrated. Source evidence/tests/rules 20–35 minutes; integration 10–20; staged validation/review/report 15–30. Source reviewers can run independently, but production files and output directories each have one owner. Start clock: 29 October 2026 18:00:14 Asia/Jerusalem (UTC+02). Active work is not separately measured.

Ponytail full: reuse one existing step, parser and tests; no framework, dependencies, renderer or span-repair subsystem. Superpowers tasks and Epoch use the same scope, dependencies and elapsed-execution basis. Epoch reference `7f3e83a1-2340-45d7-a8d2-390dbe046ec1`: optimistic 0.75, most likely 1.0, pessimistic 1.5 hours. No unresolved coordination conflict; no extra planning iteration needed.

First checkpoint: 10 minutes after approval; later checkpoints every 5–10 minutes. If approved near 18:03, expected completion 18:48–19:33 on 29 October 2026, Asia/Jerusalem. Checkpoints are reporting duties, not mechanically enforced timers.

State: OWNER approved. All three tasks completed. The final run_2 preserves all 40,070 original rows and every prior KEEP/EXCLUDE decision. It restores 225 review rows to KEEP, excludes 607 metadata rows, and leaves 3,056 under review. Full pilot suite: 248 passed; Ruff and Black passed. See docs/reports/2026-10-29-source-filter-second-pass.md and the local task ledger for verification, issues and actual timing. No model, collection or cloud run.
