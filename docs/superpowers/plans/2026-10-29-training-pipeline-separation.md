# Training and data pipeline separation

> Status: OWNER approved the refactor and audit on 29 October 2026; implementation and verification complete. No model, labels, data tables or saved receipts changed.
> Execution: root integration with independent read-only audits; reuse the current worktree and existing tests.

**Goal:** Separate training from data processing, make each active pipeline entry a meaningful step, and explain unresolved cases from saved evidence.

**Architecture:** Move real implementations rather than add forwarding wrappers or a second framework. Keep the trained checkpoint format and matching rules. Share only the small pure trigram functions needed by training and inference.

**Tech stack:** Existing Python, PyTorch, PyArrow and pytest; existing local environment; no installation or paid operation.

**Spec:** OWNER's 29 October request and six annotations following the code walkthrough; existing 100-page delivery plan remains authoritative for identity, quality and source preservation.

## Implemented file responsibilities

Model training: `GG_Data/entity_resolution/decision_model/`

| File | Responsibility |
|---|---|
| `prepare_training.py` | Public training/validation/test questions and their manifests. |
| `model.py` | Canonical LUKE scoring head, option text, checkpoint loading and scoring. Data processing imports inference functions only. |
| `train.py` | Frozen warmup, encoder tuning, validation and saved checkpoints. |

Data preparation and matching: `GG_Data/entity_resolution/hundred_page_pilot/`

| File | Responsibility |
|---|---|
| `prepare_pages.py` | Daniel rows and historical Wikipedia revision evidence; existing implementation retained. |
| `collect_entities.py` | Linked QID collection and metadata; existing implementation retained. |
| `prepare_candidates.py` | Literal grouping, strict exact pairs, trigram-ranked local candidate jobs. Split from `match.py`. |
| `resolve_entities.py` | Readiness-checked model scoring and repeated select/remove/stop decisions. Split from `match.py`. |
| `readiness.py` | Model quality/evidence gate; update canonical module paths without weakening evidence checks. |
| `report.py` | Preserve original rows and export accepted/unresolved assignments; existing implementation retained. |

Shared pure retrieval: `GG_Data/entity_resolution/trigram.py`; move existing trigram/Dice ranking without changing scores. Training must not import pipeline orchestration.

Table population: keep meaningful `post_qid_pages.py`, `post_qid_entities.py`, `post_qid_mentions.py`, `post_qid_relations.py`, `post_qid_eda.py` and `post_qid_run.py`. Split acquisition/consolidation into `post_qid_native.py` and Event eligibility/article filtering into `post_qid_events.py`, replacing the mixed `post_qid_enrich.py` entry. Review source-validation helpers before moving them; avoid duplicate implementations.

Earlier `luke_pilot` experiments remain historical. Do not modify the pre-existing unstaged `luke_pilot/evaluate.py` change. The active model should not depend on the old experimental scorer implementation; preserve parameter names and checkpoint compatibility when relocating it.

## Global constraints

- No training, inference, collection, full-corpus rerun, threshold change, identity change, gold edit, geometry change, network request or new cloud spend.
- Keep all saved source files, output versions, checksums, code archives and failed acquisition evidence intact.
- Saved results remain bound to archived source bytes. A refactor does not establish that old weights were trained with new code. Do not rewrite historical evidence to pass the current gate.
- Same-page/revision scope; many-to-many matches; exact-match uniqueness; stop wins ties; provisional `(literal name, Daniel type)` identities retained.
- No two-QID limit: the observed one-mention/two-QID result is a count, not a schema constraint.
- Native assertions and derived reverse rows stay separate from page co-occurrence weights.

## Tasks, owners and verification

1. Root: map imports, CLI callers and readiness paths. Independent audit A: explain the 369 unresolved original mentions using saved candidates, scores and scope. Independent audit B: audit public labels and Daniel positive-only references. Exit: evidence-backed findings; unsupported identity judgments remain unknown.
2. Root: relocate training code and extract pure shared retrieval. Update imports, commands, tests and code map. Exit: training modules import without loading weights or starting a run; existing scoring/checkpoint contract tests pass.
3. Root: split candidate preparation from model decisions and separate native consolidation from Event population. Update all actual callers and focused tests. Exit: step CLIs work, old combined active entries removed, source/identity/readiness tests pass.
4. Root: verify focused suites, lint/format changed files, review diff and make a local checkpoint. Do not stage unrelated changes or push. Exit: exact test counts, current file map and audit report; original output receipts unchanged.

## Review focus

- Readiness currently assumes training and inference files share one directory; real module paths must replace this assumption.
- Checkpoint parameter names and tensor structure must remain compatible with existing trained weights.
- Restart logs and archived decision verification must retain their old input/checkpoint bindings.
- Source/version hashes cannot be bypassed when consolidation and Event code move.
- Candidate absence, truncation, model stop and incorrect labels are different explanations; do not infer one from another.

## Estimate and checkpoints

Whole-task elapsed estimate: 45-120 minutes including preflight, excluding OWNER approval and unavailable-environment waits. Most likely 75 minutes. Parallel audits overlap root inspection; writes and integration have one owner. Active work and waits are unmeasured until recorded; wall-clock elapsed is not active work.

Epoch raw PERT O/M/P = 0.75/1.25/2.00 hours; expected 1.29 hours, standard deviation 0.21 hours; feedback reference `6df45663-ec47-4e14-9b3b-8791c1479db9`. Model-derived, not empirically calibrated; ignore display-only correction. Superpowers tasks and Epoch use the same complete scope and elapsed-hour basis. No unresolved estimate/scope conflict.

Preflight began 29 October 2026 11:27:03 Asia/Jerusalem (UTC+02). OWNER approval arrived after preflight; the exact approval timestamp was not measured. First execution checkpoint was 11:42; the next was 11:52. Execution finished earlier than the initial model-derived range. Elapsed time and unknown wait decomposition are recorded in the task ledger; elapsed time is not measured active work.

## Verified delivery

- Real training implementations now live in `decision_model/`. Active pipeline preparation and decisions use separate modules; native consolidation and Event population are separate. No forwarding wrappers or new execution framework were added.
- 171 relevant CPU tests passed in 19.74 seconds. After final import formatting, 57 affected readiness, export and core-run tests passed again in 10.15 seconds. Black, isort and Ruff passed on all 19 changed Python files. Four new entry points returned successful `--help` results without loading weights.
- The immutable historical gate remains usable through a temporary archived-module import. Current code requires current restore evidence; no historical receipt was rewritten or newly qualified.
- All seven final table/EDA files match the saved receipt hashes. The independent audit and root reproduction both found 369 unresolved rows, with same-page/revision candidate exposure 37 none / 122 some / 210 all; all 142 read data inputs retained their hashes.
- Detailed label limits, typed-entity counts, relation directions and suggested controlled experiments are in `docs/reports/2026-10-29-matching-label-audit.md`.
- Independent read-only review found no new blocking defect. The unrelated `luke_pilot/evaluate.py` edit remains outside this change. Geography, full identity gold, and the model quality disposition before 10/100-page inference remain pending.

## Protection

Worktree: `D:/Projects/GeoAI-luke-pilot-20261028`, branch `experiment/luke-decision-pilot-20261028`. About86 GiB free at preflight. Existing modified `luke_pilot/evaluate.py` stays untouched. No push is authorised. Code commits are local checkpoints; ignored data and weights are not protected on GitHub.
