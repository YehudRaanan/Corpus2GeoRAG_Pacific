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
- [ ] Commit only this task's code and plan after reviewing the diff.

## Task 2: Full run and validation
Depends on Task 1. Output under ignored `Data/external/source_page_ids_20261026/`.
- [ ] Retrieve all 428 source titles, preserving page/revision IDs and request evidence.
- [ ] Check all 34,775 distinct `(Source, Text)` pairs, map results to all raw rows.
- [ ] If titles are missing, use copied-text search for candidate discovery; accept only verified full passages, otherwise leave null.
- [ ] Save Parquet, passage decisions, row-level unresolved report, source summary, manifest, and readable run report.
- [ ] Read output again: original table equals projected output including metadata; IDs reconcile with evidence; input hash unchanged.
- [ ] Review final code and counts; commit reproducibility files and report local-only artifact protection.

## Estimate and status
- Estimate v1 / Epoch feedbackRef: 10267e18-cf72-42b5-9a04-be148d22704e.
- Model-derived elapsed estimate: 30–60 minutes, point estimate 45 minutes. Assumes fewer than 1,000 current-page requests and no provider outage. Not empirically calibrated.
- Execution start: 2026-10-26 19:51:05 Asia/Jerusalem (UTC+02:00).
- First status checkpoint: 2026-10-26 19:59; latest target: 20:50, same zone.
- Active work: unknown/unmeasured. Approval wait excluded from execution elapsed. Environment waits measured by request logs where possible.
- Completed: source/schema/input hash verified; API available; isolated worktree created.
- Pending: tasks 1–2.
- Ruling: implement inline without additional approval prompts; the user approved this concrete local run. No new platform or dependencies.
- 19:59 checkpoint: 94/428 sources checked, no request failures. Retrieval continues; deadline unchanged.
- Task 1 verification: 6 new focused tests plus 1 existing title-resolution test passed; Ruff passed. Text-search ambiguity test observed failing before implementation and then passing.
- Current exclusive resource owner: collection process 5186 owns the run directory until it exits. Code/test/plan edits do not write its cache.
- Ruling: current revision IDs are recorded to bind rendering to the current page fetched in this run; this is reproducibility, not a historical revision search.
- Ruling: text-search candidate discovery for missing source titles uses the two longest eligible passages and up to five results per phrase; full copied text must match exactly or after NFC/whitespace normalization. Short/common text cannot establish a new source page. This bounded discovery may leave valid cases unresolved.
