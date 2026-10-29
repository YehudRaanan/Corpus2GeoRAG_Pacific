# Recover missing page QIDs for unresolved mentions

**Status:** OWNER approved execution; started 12:41:38 on 29 October 2026,
Asia/Jerusalem (UTC+02). First execution checkpoint 12:52.

**Goal:** Add source-supported QID candidates to a new inventory for the three
saved revisions behind the 369 unresolved mentions. Do not assign mentions.

**Approved design:** Read the same saved revisions, recover targets encoded in
templates and failed ordinary article links, use caches before public lookups,
and keep historical source evidence separate from current identity mappings.

**Architecture:** One pipeline stage, `recover_page_qids.py`, importing revision
validation, cached request handling, title resolution and metadata helpers from
`collect_entities.py`. One focused test file. Separate versioned data outputs;
no rewrite of the existing collector, inventories or matching outputs.

**Technology:** Existing Python, requests, pyarrow and pytest. No installation.

**Spec and evidence:** User-approved recovery steps in this conversation;
`docs/reports/2026-10-29-unresolved-causal-audit.md`; canonical audit outputs in
`Data/external/hundred_page_pilot_20261028/audit_deep_20261029/final/`.

## Verified inputs and limits

- All three source files passed saved SHA-256 and page/revision binding checks.
- Page/revision pairs: 781032/1379821139, 23680822/1375594940,
  29607850/1323366204. Do not substitute the older Nishimura revision.
- In these scopes, 169 saved link occurrences include 34 without QIDs. Two are
  ordinary article targets: Akiji Tagami and Sueo Obayashi (macron in source).
  The other 32 point to categories or files; they are not missing article QIDs.
- The raw revisions contain 36 Ship template occurrences. Other template
  families require an explicit, verified target rule; arbitrary parameters are
  not entity links. No current navigation-box expansion is permitted.
- Reuse saved title lookup responses from the MISC audit, retaining redirect
  chains, request identity and retrieval times. Preserve explicit ship years.
- Ambiguous spellings, namesakes, type conflicts and failed lookups remain
  review cases. Do not turn audit hypotheses into confirmed identities.

## Tasks and ownership

| Task | Owner | Dependencies and exclusive resource | Measurable exit check |
|---|---|---|---|
| 1. Fix recovery contract | root | Existing collector, three raw revisions, cached lookups | Exact source scopes, supported template rules and output fields documented. |
| 2. Implement stage | root | Task 1; owns stage file and all API/output writes | Candidates contain source offsets, raw hash, revision, lookup status and mapping provenance. |
| 3. Independent tests/review | review agent | Task 1; owns only focused test file; read-only source access | Wrong-year, protected text, duplicate, nonarticle and changed-source cases checked. |
| 4. Run bounded recovery | root | Tasks 2-3 pass; owns new output directory and public API session | New evidence and inventory written; unresolved denominator preserved. |
| 5. Independent result check | review agent | Task 4; read-only artifacts | No unsupported promotion, duplicate keys or changed baseline hashes. |
| 6. Report and checkpoint | root | Tasks 4-5 | Counts, examples, unknowns, runtime, cost and backup status reported. |

Tasks 2 and 3 can overlap after the shared contract. No concurrent writes to
shared files, API evidence or output tables. Reuse the current worktree.

## Output contract and verification

- New source-target evidence with `(page_id, revision_id)`, template/link origin,
  exact raw text and offsets, raw file/hash, target title and lookup outcome.
- New QID metadata and a merged inventory for these three scopes, using the
  existing entity schema; unique `(page_id, revision_id, qid)` keys.
- New case-level report for all 369 original unresolved rows, distinguishing
  candidate availability from a resolved mention. DATE and unlinked names stay
  outside this linked-target recovery.
- Public lookups: at most 20 new requests and five minutes for the lookup phase;
  explicit failures recorded, no hidden retries or overwritten failed evidence.
- Compare against the 142 frozen baseline hashes. Run focused pytest checks
  and available project lint checks on the new files.
- No inference, retraining, assignment/type/threshold/gold changes, full-corpus
  rerun, BigQuery, GPU, paid cloud work or push. New cloud cost: zero.

## Estimate and checkpoints

Whole-task model-derived elapsed range: **30-60 minutes**, including preflight
from 12:34:32 on 29 October 2026, Asia/Jerusalem (UTC+02), excluding approval and
environment waits. Epoch O/M/P: 0.50/0.75/1.00 hours; raw expected 0.75 hours;
feedback reference `8406b035-8faf-46fb-ad65-1b8f061c811f`.

Ponytail full reuses the collector rather than rerunning or rebuilding it.
Superpowers tasks and Epoch share the same scope, dependencies, units and
elapsed-time basis; no unresolved conflict. Display corrections are not used;
the range is not empirically calibrated. Active work and unmeasured waits are
unknown, not inferred from wall-clock time.

Preflight status checkpoint: 12:44 on 29 October 2026, Asia/Jerusalem. Execution
checkpoints: ten minutes after approval, then every 5-10 minutes. These are
reporting commitments, not mechanically enforced timers. Duration approval is
required by the user-provided AGENTS.md before implementation begins.

**Protection:** Existing worktree has an unrelated `luke_pilot/evaluate.py`
change. Preserve it. Data outputs are ignored local files and are not backed up
on GitHub. No push permission is assumed.

## Execution record

| Contract / task check | Finding / ruling |
|---|---|
| 1 -> 2 source scopes | All three hash/revision bindings pass; no scope conflict. |
| 2 <-> 3 parser interface | `template_targets(text)` returns literal offsets, raw text, target or explicit review status. Tests own a separate file. |
| 2 -> 4 cached mapping | Cached responses omit disambiguation pageprops. Use a bounded explicit title check before promoting a new target; retain both cache and verification evidence. |
| 4 -> 5 output contract | New tables only, one page/revision/QID row; no assignments. Reviewer reads only after writes finish. |
| 5 -> 6 completion | Candidate availability must never be called mention resolution. Baseline hashes and all 369 report rows required. |
| Each task versus exclusions | No task requires inference, paid resources or edits to original data. |

- [x] Task 1: source census and contract; independent identity review completed.
- [x] Task 3 initial RED: 12 missing-module failures, one existing hash guard pass.
- [x] Task 2: stage implementation and GREEN; 25 recovery tests pass.
- [x] Task 4: bounded recovery; two public requests, final offline replay.
- [x] Task 5: independent result review; 53 assertions and 154 hashes pass.
- [x] Task 6: report completed; local checkpoint prepared.

Ruling: support flat `Ship` calls only for this census; parameterless `IJN` is
navigation, not an individual ship. Other template families remain outside the
implemented target rules and are reported as such. No generic current expansion.
Ruling: do not repair Yugiri spelling or Yura type automatically, and do not copy
the year from a later Kiku occurrence into an earlier unqualified occurrence.

## Completion evidence

Final reviewed folder: `Data/external/hundred_page_pilot_20261028/qid_recovery_20261029_v2/`.
23 added QIDs, 112 -> 135 scoped inventory rows, all additions on the exact
Nishimura revision. 26 original unresolved mentions have a pre-existing audit
hypothesis newly available; no identities were assigned. All 369 case rows and
154 protected inputs are unchanged. DATE remains a separate route.

The first run took 7.84 seconds and made two requests. Its 24 additions included
Asagumo (1938 -> 1937), excluded after independent review. The final replay took
2.78 seconds and used saved evidence only: zero new requests. Both versions are
preserved. Corrected per-title redirect chains, metadata stub validation and
display/year guards have focused tests. Whole verification: 31 tests pass,
black/isort/ruff pass. No inference, paid resources or push.

Elapsed planning/coding/review time and script runtime are recorded separately
in the recovery completion file; active work and exact waits remain unknown.
Epoch wait-excluded actual is not submitted because that basis is unmeasured.
