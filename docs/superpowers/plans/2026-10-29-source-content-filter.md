# Source-content filter implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement the integration. Independent source and test reviews may run in parallel, with separate file ownership.

**Goal:** Verify the source-content rules and prepare a safe filter step for later pilot matching runs.

**Architecture:** Put source classification in one pipeline module. Preserve every input row and original column; append an occurrence-level KEEP, EXCLUDE or REVIEW decision with evidence. Candidate preparation uses KEEP rows only when this policy is selected; reporting preserves all rows and separates source exclusions and reviews from genuine matching failures.

**Tech stack:** Existing Python environment, PyArrow, mwparserfromhell and pytest. No new dependencies.

**Spec:** User request in this chat and `docs/reports/2026-10-29-pilot-source-content-scope.md`. The report contains proposed rules, not an already active production filter.

## Scope and constraints

- Use the saved 100-page pilot: 40,070 mentions and 132 article revisions. Validate a small subset before the full local check.
- Reuse source parsing and position helpers. One new meaningful pipeline file; narrow changes to candidate preparation, reporting and their tests.
- Preserve original text, word_original, offsets, row identities, QID assignments and historical outputs. Source classification uses original offsets and text, not repaired-name offsets.
- Exclude citation and bibliographic metadata, hidden categories, filenames, maintenance material, navigation and external-link metadata when source evidence is clear.
- Retain article prose, factual infobox fields, tables, displayed captions, displayed entity names and substantive quotations. Nested citations remain excluded.
- Ambiguous placement, unsupported template rendering and explanatory reference notes remain REVIEW unless a tested source rule establishes their role. Do not guess positions or treat an unknown template name as a visible entity.
- Apply decisions to occurrences, not entire paragraphs or identical names on other parts of a page.
- Keep DATE linking policy unchanged. Do not change identity rules, candidate ranking, model scores, thresholds or labels.
- No inference, training, network collection, paid queries, cloud starts, Geography, graph rebuild or full-corpus rerun.
- Existing unrelated changes, including `luke_pilot/evaluate.py`, stay untouched. Outputs use a new directory.

## Review focus

1. Citation nested inside an otherwise eligible infobox or quotation: exclude only citation occurrences.
2. Visible caption or escaped category label versus hidden file/category target: classify the actual span.
3. Repaired names and repeated passages: use original placement; uncertain spans go to REVIEW.
4. Explanatory references versus source citations: do not exclude every ref tag.
5. Pipeline leakage: excluded/review occurrences must not enter groups, exact matches, trigram context or unresolved denominators; all original rows remain exportable.

## Files and interfaces

- Create `GG_Data/entity_resolution/hundred_page_pilot/filter_source_content.py`: reusable source-span classification and CLI that writes annotated mentions plus summary/evidence. Accept mentions, revisions and a fresh output directory. Reuse installed parsing libraries and existing placement helpers; no dependency on ignored audit scripts.
- Create `GG_Data/entity_resolution/hundred_page_pilot/test_filter_source_content.py`: source fixtures and preservation checks.
- Modify `prepare_candidates.py` and focused tests: validate selected scope policy and consume KEEP occurrences only. Preserve explicitly selected legacy behavior for old saved runs; do not silently mix policies.
- Modify `report.py` and focused tests: preserve source columns and all original rows, validate group coverage against eligibility, report excluded/review rows separately from matching failures. Scope evidence takes precedence over new matching eligibility, without rewriting saved assignments.
- Update `README.md`: step order, commands, policy/denominator meaning and known limitations.
- Add a short verification report and timing/issue ledger. Use the existing project documentation and output layout.

## Tasks and owners

### 1. Fix source-rule tests and implement the standalone step

Owner: main agent. Dependency: duration approval. Exclusive ownership: new production module and integration files.

- [x] Write tests for the five review classes, ship/country display helpers, URL/parameter syntax, maintenance dates, table service dates, comments and malformed offsets.
- [x] Run the new tests and confirm failures before implementation.
- [x] Extract and simplify the audited parser into the pipeline module; add explicit input validation, provenance, policy version and a fresh-output guard.
- [x] Run source tests and verify that original columns and unique row identities survive unchanged.

Outcome: a locally tested source-classification CLI; uncertainty stays visible.

### 2. Gate matching and reporting

Owner: main agent. Dependency: task 1 interfaces. Independent reviewer may inspect existing report fixtures without editing shared files.

- [x] Add tests that a kept occurrence remains usable while an excluded identical-name occurrence cannot affect candidates or contexts.
- [x] Add tests for all-row exports, REVIEW handling, source-policy validation and unresolved counts.
- [x] Add minimal eligibility checks to candidate preparation and reporting; maintain explicit legacy compatibility.
- [x] Run the affected pipeline tests and verify unchanged exact-match and model-decision policies.

Outcome: no source-excluded occurrence leaks into a new filtered matching run.

### 3. Validate real saved data and document readiness

Owner: main agent for execution. Parallel source reviewer: read-only spot checks. Parallel regression reviewer: read-only code/test review. No shared output ownership.

- [x] Run the filter on a small saved page set, verify examples, then run on all 100 saved pages.
- [x] Verify 40,070 unique rows, original-column equality, input hashes and mutually exclusive scope counts. Explain changes from the provisional audit counts.
- [x] Prepare candidates locally without inference and verify excluded/review row IDs cannot enter groups or contexts.
- [x] Run focused pytest, Ruff and formatting checks. Fix only task-related failures.
- [x] Update README and write a concise report: verified counts, examples, unresolved risks, next-run commands and elapsed timings.
- [x] Review the task diff. If a local checkpoint is made, stage only task files. No push without established permission; report actual backup status.

Outcome: verified filter, saved local evidence and clear instructions for the next model run; no claim of new matching accuracy.

## Estimate, coordination and checkpoint

Estimate version 1: **45–90 minutes total elapsed execution**, including preflight already completed; approval and environment waits excluded. This is a model-derived planning range, not an empirical percentile. Active work is not separately measured unless recorded.

Breakdown: source tests/module 15–25 minutes; integration 15–30 minutes; real-data verification/review/documentation 15–25 minutes; overlap independent source/review work where useful. Input readiness is verified before each run. Main-agent integration and each output directory have one owner.

Ponytail full: reuse the existing parser and helpers; no new framework, dependency or training changes. Superpowers tasks and Epoch estimate use the same scope, dependencies, units and elapsed-execution basis. Epoch estimate reference: `6895d880-505d-4fd8-a4f0-ded9cca5eb8e`; optimistic 0.75, most likely 1.0833333333, pessimistic 1.5 hours. No second planning iteration is needed while this scope remains unchanged.

First execution checkpoint: 10 minutes after approval; continue updates at useful boundaries. Absolute completion window will be stated with the approval request using the verified Asia/Jerusalem clock. Record waits separately and record Epoch actuals in hours. Checkpoints are reporting obligations, not a mechanical background timer.

**State:** OWNER duration approval received. Implementation, integration, staged local validation, code reviews and documentation are complete. Final task-only checkpoint review is in progress. No inference or paid action was performed. Test layout follows existing colocated test files.
