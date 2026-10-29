# Source-preserving text cleaner implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Parallel workers have exclusive file ownership. Track tasks below.

**Goal:** Add one separate cleaning step and test three saved Wikipedia pages, preserving every Daniel input row and original value.

**Architecture:** Work from Daniel's original `Text` plus the saved historical revision. Reuse the installed wikitext parser and source-component rules. Keep an explicit source-to-clean span map when removing markup or expanding supported templates. Unknown transformations remain marked for review. This is a small local cleaner informed by the reviewed extraction rules, not a full FineWiki HTML deployment.

**Tech Stack:** Python 3.12, installed mwparserfromhell, PyArrow, pytest; existing task-local environment.

**Spec:** User requests in this chat: one meaningful code file, cleaned text in a new field, original entity retained, before/after positions, small-page test, parallel tasks.

## Global constraints

- Preserve original `Text`, `start`, `end`, row identifier, QIDs and all original rows. Preserve the earliest `word_original` value.
- Add `Text_clean`, `clean_start`, `clean_end`, `clean_status`, and an evidence/reason field. Positions use Python character offsets, end exclusive.
- Update the working entity text only when its source occurrence has a supported unique mapping. Keep excluded or uncertain rows with null clean offsets and explicit reasons.
- Clean each distinct page/revision/passage once, then join the result to its mention rows.
- No inference, training, paid queries, cloud work, collection, new packages, or changes to existing assignment outputs.
- All experiment outputs go into a new ignored local directory. Do not overwrite previous runs or unrelated Git changes.
- Do not copy the full FineWiki extraction framework. Reuse local helpers and dependencies first.

## Review focus

- Repeated names/passages must not be located by an arbitrary first string match.
- A removed citation must not reappear through a fallback text path.
- Unknown or generated template text must not receive invented precise offsets.
- Unicode, escaped characters and replacements must preserve correct character coordinates.
- Excluded components must not remove adjacent article text or silently delete mention rows.

## Execution and estimate

Estimate version 1: **45–90 minutes total elapsed execution**, including preflight, excluding approval/environment waits. Model-derived estimate, not empirical calibration. Epoch PERT feedback reference: `dfec64eb-0c6b-45d2-8e5b-db2bef78c06c`; optimistic/likely/pessimistic 0.75/1/1.5 hours. Superpowers task breakdown below uses the same scope, dependencies and elapsed-time basis. No unresolved estimate conflict; no claim that Epoch measured active work.

Duration approval received in chat on 2026-10-29; execution completed locally. First execution checkpoint: ten minutes after approval. Record observed timestamps, issues and waits in the report; unmeasured active work remains unknown.

### Task 1 — implementation (parent, exclusive code owner)

Create `GG_Data/entity_resolution/hundred_page_pilot/clean_source_text.py`.

- [x] Inspect local source/filter/name helpers and select three saved pages covering prose, templates and tables/references.
- [x] Define a small `clean_text` result with cleaned text, source span mapping and unsupported spans; expose a file-based CLI using existing input conventions.
- [x] Implement only supported transformations and explicit excluded/uncertain outcomes. Avoid fuzzy position matching.
- [x] Add row-preserving Parquet output and a compact run summary.

Estimated task range: 20–40 minutes; dependent on interface agreement with Task 2.

### Task 2 — tests (parallel worker, exclusive test owner)

Create `GG_Data/entity_resolution/hundred_page_pilot/test_clean_source_text.py`.

- [x] Agree exact function signatures with the implementation owner before writing tests.
- [x] Test literal/link/template transformations, citations, repeated strings, unsupported templates, Unicode, partial spans and row preservation.
- [x] Run tests before implementation to confirm a meaningful failure; rerun after implementation.

Estimated task range: 15–30 minutes, parallel with Task 1 after interface agreement.

### Task 3 — saved-source audit (parallel worker, read-only)

- [x] Inspect the selected saved pages and Daniel passages independently.
- [x] Identify concrete before/after examples and source boundaries that require review.
- [x] Report exact evidence and limitations; no code edits, collection or model decisions.

Estimated task range: 10–20 minutes, parallel with Tasks 1–2.

### Task 4 — pilot and review (parent; independent review worker after code is ready)

- [x] Run the cleaner on the selected three pages into a new output directory.
- [x] Verify input/output row identifiers and all protected original columns are identical.
- [x] Check every mapped entity equals its clean-text slice; summarize excluded and uncertain cases separately.
- [x] Run focused pytest and applicable lint/format checks. Review against the five failure modes above.
- [x] Update the local README and write a short report with counts, examples, issues, timings and limitations. Record a scoped local Git checkpoint; do not push without authorization.

Estimated task range: 15–30 minutes after Tasks 1–3; overlap independent review with pilot checks. Combined critical-path elapsed range remains 45–90 minutes.

## Execution result

Final artifact: `Data/external/hundred_page_pilot_20261028/source_text_cleaner_pilot_20261029/run_3/`. Three pages use eight revisions; 8,350 rows preserved. 3,647 mapped, 4,440 excluded, 263 uncertain. 70 focused tests, Ruff and Black checks passed. Detailed report: `docs/reports/2026-10-29-source-preserving-text-cleaner.md`. Independent bounded review fixes verified; no model/cloud/network run. Code/report remain on the current branch with a scoped local checkpoint, no push. Ignored data remains local.
