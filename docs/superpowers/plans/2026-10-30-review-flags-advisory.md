# Review flags are advisory: implementation plan

> **For agentic workers:** Use Superpowers executing-plans or the existing parallel workers. Do not start implementation before OWNER duration approval.

**Goal:** Let source-review mentions proceed to QID decisions; preserve uncertainty as metadata rather than an eligibility veto.

**Architecture:** Change the existing shared matching eligibility/context logic and its table/EDA consumers. Reuse existing grouping, exact matching, trigram and scorer; add no framework or dependency. A missing clean span requires an explicit original-text context fallback, never invented clean offsets.

**Tech stack:** Existing Python 3.12 environment, PyArrow, pytest and current stage functions.

**Spec:** OWNER request in this chat on 30 October: all review mentions must enter matching; preprocessing must not reject identities because it has doubts. Existing input/revision/exclusion/DATE agreements remain except where OWNER resolves the DATE overlap below.

## Constraints and approved decision

- Saved run `Data/external/revised_pipeline_20261030/` is immutable comparison evidence. Use a new output root for local preparation; never reuse old model scores for changed inputs.
- Preserve all 40,070 original rows and nine raw fields, occurrence IDs, page/revision identity, cleaned text, clean offsets, source evidence and every review flag.
- `SOURCE_REVIEW`, repair/context review and uncertain clean placement must no longer block model preparation. Do not change the 14,980 explicit source exclusions or invent page/QID identities.
- OWNER approved retaining DATE deferral: admit the 7,692 non-DATE review rows and defer the other 226. Expected eligible count is 20,931; total deferred DATE is 4,159. Explicit source exclusions remain 14,980.
- Prefer clean context only with a verified mapped span. Otherwise use original `Text` and valid original offsets; validate the original slice against `raw_original_word`/raw word, not a repaired working name. Label the context basis explicitly. Never relabel fallback context as clean text or relocate a name by string search.
- Preserve strict exact-name/type/QID rules and their repaired-name restrictions. Review metadata alone must not veto residual model eligibility.
- Keep the existing per-QID top-80 and source-supported candidates. Check that every newly admitted group appears in a model job unless already fully handled by exact matching; if omitted by every top-80 pool, add its highest-trigram same-page QID pairing as coverage protection. Do not fabricate a pairing when no named QID exists on that revision.
- No inference, GPU start, API collection, paid query, retraining, database loading or Geography in this code/preparation task. An actual new model run is a separate scope/budget check.

## Tasks and ownership

### 1. Shared eligibility and model context — Worker A

**Files:** `GG_Data/entity_resolution/hundred_page_pilot/prepare_candidates.py`, `test_revised_input_candidates.py`; necessary narrow cleaner annotation adapter only.

**Interface:** Existing `matching_eligibility(...)` and `group_mentions(...)`; a small shared context helper returns text and its source basis for the group/writer checks.

- [ ] Add failing cases for mapped context-review, repair review, uncertain/null clean offsets, raw fallback, explicit source exclusions and the chosen DATE rule.
- [ ] Remove review-only vetoes, retain original-data validation, and choose an explicit valid context without `int(None)` or fabricated clean positions.
- [ ] Preserve flags on rows/groups. Add coverage-protected same-page candidates only where the ordinary candidate union misses a newly eligible group.
- [ ] Verify every formerly reviewed group is exact-handled, offered to the model, or explicitly lacks a usable page inventory. Report the old eligible groups separately. A passing eligibility flag alone is not proof of model exposure.

Estimate: 10–20 elapsed minutes, model-derived; one writer per file.

### 2. Writer and EDA consistency — Worker B, parallel after context contract

**Files:** `GG_Data/pipeline/post_qid_mentions.py`, `post_qid_eda.py`; corresponding existing tests. If OWNER includes the 226 review DATE rows, also narrowly update the unconditional DATE rejection in `post_qid_entities.py` and its tests.

- [ ] Add failing tests that review metadata survives accepted/model/unresolved outcomes and no longer forces audit-only status.
- [ ] Make writer classification use the same eligibility decision. Validate clean and raw-fallback context by their actual basis; keep raw values, page/revision foreign keys and typed bridge checks strict.
- [ ] Keep genuine source exclusions and unapproved dates outside identity creation. Do not manufacture a clean span for an admitted review mention.
- [ ] If review DATE rows are included, admit only those 226 using explicit original-review provenance. Do not set `exclude_date=False` globally or admit other previously deferred dates.
- [ ] Run focused writer/EDA tests and check the shared contract against Task 1.

Estimate: 8–15 elapsed minutes, model-derived; exclusive writer of these files.

### 3. Integration and local 100-page preparation — Root

**Depends on:** Tasks 1–2 and the DATE answer.

**Files:** Existing `post_qid_run.py`/workflow report only if demonstrated consumers require changes; README and final task report.

- [ ] Prepare a new version from saved inputs using existing stages. Keep the old outputs unchanged.
- [ ] Verify all 40,070 raw rows/IDs, same 100 pages/132 revisions, exclusions, DATE policy, context basis and candidate exposure of all formerly reviewed mentions.
- [ ] Report exact/model-ready counts, fallback counts, top-80 coverage additions and any page with no usable QID. These are preparation results, not new model matches.
- [ ] Run the affected regression suite and lint, review the minimal diff, then create a local Git checkpoint. No push authorization is inferred.

Estimate: 10–15 elapsed minutes after dependencies, model-derived.

## Estimate, gate and checkpoints

Whole task, including preflight and documentation: **30–60 elapsed minutes**, excluding approval/environment wait. Active work and waits must be recorded separately or marked unknown. Parallel tasks share files only through the agreed context interface; root owns integration and Git. First execution checkpoint ten minutes after approval, then every 5–10 minutes.

Epoch v1 O/M/P 0.5/0.75/1.0 hours, raw expected 0.75 hours; feedback `cc7f80a5-0ba1-4b24-828e-62d0f870099c`. This is a model-derived range, not empirical workflow calibration. Superpowers review must use the same scope, dependencies and elapsed-hour basis; at most two iterations.

Independent Superpowers worker review agreed in iteration 1 with the same scope/dependencies/30–60 elapsed-minute basis. It verified all 7,918 original raw slices are valid; 533 differ from the repaired working word and must not be rejected for that difference. The selective DATE consumer gap is covered above. No estimate conflict remains; DATE is a pending product decision, not a hidden estimating assumption.

OWNER approved implementation and the local test on 30 October 2026, about 02:01 Asia/Jerusalem (UTC+02). The same approval explicitly retains DATE deferral. No model or cloud execution is included.
