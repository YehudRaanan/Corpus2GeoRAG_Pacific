# Source Wikipedia Page IDs Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. Execute in this session.

**Goal:** Add a nullable numeric `wiki_page_id` to every original raw Parquet row.
**Architecture:** Read the pinned original file with Arrow. Retrieve current English Wikipedia pages using source titles and server redirects; verify each distinct copied passage in extracted or rendered page text. Preserve all original fields and row order. Export unresolved cases and request evidence separately.
**Tech Stack:** Existing Python, requests, BeautifulSoup, pandas, PyArrow, pytest.
**Spec:** User approval in this conversation, 2026-10-26, for current English pages, blank unverified IDs, local output, 30–60 minutes.

## Global Constraints
- Original input SHA-256: dcd51dfa237b63378279ced4f9739a45d8cf8ce3991579f20848295448f83f16.
- All 309,864 input rows and original columns remain unchanged and ordered.
- Match full copied text exactly, or after NFC and whitespace normalization only. No fuzzy matching.
- Exclude historical revision searches, entity identity matching, graph edits, deployment, and remote push.
- A title match alone cannot populate an ID. Non-articles and disambiguation pages cannot populate IDs.
- Cache requests, preserve errors, do not retry failed requests automatically.
- One owner: root agent. This worktree and its run directory have no other writers.

## Review Focus
- Missing or disambiguation pages stay unresolved.
- Short passages are checked only within their title-resolved source page; global text search must not infer identity from a short common string.
- Whitespace normalization must not alter raw text or remove punctuation/case distinctions.
- Duplicate rows, null IDs, original schema metadata, and row ordering survive the export.
- Interrupted retrieval is resumable from evidence without silently repeating failed calls.

## Task 1: Verified matching and export
Files: create `GG_Data/entity_resolution/attach_source_page_ids.py` and `test_attach_source_page_ids.py`.
Interfaces: `normalize(text)`, `resolve_page(source, response)`, `match_text(text, page)`, `append_ids(table, decisions)`; decisions keyed by `(Source, Text)`.
- [x] Write focused tests, observe failures, implement minimum functions, pass tests.
- [x] Add cached current-page retrieval and audit reports; first live source verified 65/65 passages before the full run continued.
- [x] Commit only this task's code and plan after reviewing the diff: 588f7b3.

## Task 2: Full run and validation
Depends on Task 1. Output under ignored `Data/external/source_page_ids_20261026/`.
- [x] Retrieve all 428 source titles, preserving page/revision IDs and request evidence. No request failures.
- [x] Check all 34,775 distinct `(Source, Text)` pairs, map results to all raw rows.
- [x] If titles are missing, use copied-text search for candidate discovery; accept only verified full passages, otherwise leave null. Four titles yielded 699 verified raw rows by copied text.
- [x] Reuse all fetched page text, then search all remaining eligible distinct passages (408 long texts after the first pass). Recheck ambiguity against the final collected candidate corpus. Short unverified passages remain null.
- [x] Save Parquet, passage decisions, row-level unresolved report, source summary, manifest, and readable run report.
- [x] Read output again: original table equals projected output including metadata; IDs reconcile with evidence; input hash unchanged.
- [x] Review final code and counts; checkpoint reproducibility files and report local-only artifact protection.

## Estimate and status
- Estimate v1 / Epoch feedbackRef: 10267e18-cf72-42b5-9a04-be148d22704e.
- Model-derived elapsed estimate: 30–60 minutes, point estimate 45 minutes. Assumes fewer than 1,000 current-page requests and no provider outage. Not empirically calibrated.
- Execution start: 2026-10-26 19:51:05 Asia/Jerusalem (UTC+02:00).
- First status checkpoint: 2026-10-26 19:59; latest target: 20:50, same zone.
- Active work: unknown/unmeasured. Approval wait excluded from execution elapsed. Environment waits measured by request logs where possible.
- Completed: source/schema/input hash verified; API available; isolated worktree created.
- Task 1: complete (commit 588f7b3; 7 focused/regression tests and Ruff passed).
- Task 2: complete. All 309,864 rows preserved; 301,235 verified IDs and 8,629 null IDs. Independent evidence verification passed at 20:26:01. Final manifest verification passed for 2,138 files.
- Ruling: implement inline without additional approval prompts; the user approved this concrete local run. No new platform or dependencies.
- 19:59 checkpoint: 94/428 sources checked, no request failures. Retrieval continues; deadline unchanged.
- Task 1 verification: 6 new focused tests plus 1 existing title-resolution test passed; Ruff passed. Text-search ambiguity test observed failing before implementation and then passing.
- Current exclusive resource owner: root agent. All retrieval, export, and verification processes exited successfully; no operation remains pending.
- Ruling: current revision IDs are recorded to bind rendering to the current page fetched in this run; this is reproducibility, not a historical revision search.
- Ruling: text-search candidate discovery for missing source titles uses the two longest eligible passages and up to five results per phrase; full copied text must match exactly or after NFC/whitespace normalization. Short/common text cannot establish a new source page. This bounded discovery may leave valid cases unresolved.
- Evidence update at approximately 20:06: all 428 titles completed; 301,119 rows verified and 8,745 unverified, representing 534 distinct Source/Text pairs and 408 distinct eligible long texts. Missing source labels can differ from actual matching article titles, so finish text search on the remaining eligible passages. This implements the original text-based attribution scope, not a new dataset or revision policy.
- Affected Task 2 estimate: 10–25 minutes remaining (model-derived, not empirically calibrated), including implementation, cached-text reuse, up to 408 search queries plus candidate fetches, export, review, and all-row verification. Expected completion by approximately 20:31; approved upper bound 20:50 unchanged. Next checkpoint 20:09.
- Replanning cycle: 1 for Task 2 based on measured residual text count. Reuse existing cached pages before any more network requests.
- 20:09 checkpoint: collection and missing-title recovery complete; remaining copied-text search and exact evidence selection in progress.
- 20:19 checkpoint: 407/462 residual distinct texts processed; no request errors. Final search and ambiguity recheck subsequently completed.
- Export completed at 20:22:07 Asia/Jerusalem (UTC+02): all 309,864 original rows, all 9 original columns, values, ordering, and schema metadata survived the round trip. Output SHA-256: 0b34290f0f74cc060dad325ca5fe32a9505acfe2ae84cca3dd0768ad2ec48cd1.
- Fresh read-only review found an ambiguity-check gap for previously recovered source titles. Added a failing fixture, fixed final global-candidate recheck, then passed all 9 focused/regression tests and Ruff. Reviewer confirmed the fix and reported no remaining material findings; final export verification remains root-owned.
- Final verification: all original raw values, order, fields, and metadata equal; all 34,775 source/text decisions checked against row assignments; every non-null decision has full-passage evidence and matching page/revision/title; all unresolved CSV indices reconcile. 1,071 saved requests, zero failures, 572.211 summed seconds of request wall time. Unique exact raw name/type pairs: 74,339.
- Final deliverable report: `docs/SOURCE_PAGE_IDS_RUN_2026-10-26.md`. Data validation elapsed from approval/execution start: 34 minutes 56 seconds. Active work and approval wait remain unmeasured. Final elapsed time is recorded against both Epoch estimate IDs at handoff using auto_wallclock provenance.
- Integration ruling: the user requested a local data copy, so keep this isolated local branch/worktree and its artifacts in place; no merge, remote push, or cleanup. Code/report protection: Local checkpoint only. Ignored data/evidence protection: Unprotected.
