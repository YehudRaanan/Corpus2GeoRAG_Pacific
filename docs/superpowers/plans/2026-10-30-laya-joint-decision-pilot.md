# Laya Joint Decision Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task. Preserve completed work and record checks below.

**Goal:** Train a real Laya joint-option model using existing public training data, then compare it with the saved LUKE results on the same 3/10/100-page pilot.

**Architecture:** Reuse the upstream Laya encoder, joint option markers, Transformer decision head and RLCD training functions. Add thin data, training and inference adapters; keep training separate from the data pipeline. Train one model on explicitly identified forward and reverse questions, with frozen encoder warmup followed by encoder tuning.

**Tech Stack:** Existing Python environment patterns, PyTorch, upstream Laya, saved ZELDA JSONL, existing Parquet/pipeline helpers and pytest.

**Spec:** This document, Approved design and Global constraints below; user request of 2026-10-30 to reuse existing training code and data.

## Approved design

- Laya sees the question, context and all options in a decision together. It is not the old independent LUKE pair scorer.
- Retain original source text and identity metadata. QIDs are metadata; model options contain entity names and evidence.
- Forward: QID entity chooses a Daniel group; remove its selected group and ask again. Stop text: `None of the remaining mention groups refers to this entity.`
- Reverse: a Daniel group chooses a QID entity; remove its selected entity and ask again. Stop text: `This mention does not refer to any of the remaining entities.`
- Recompute joint scores after every removal. A group can match several QIDs; a QID can match several groups. Do not impose one-to-one matching.
- Retain the exact-name/unique-QID/single-Daniel-type exact-match rule and all current page/revision, source and type filters. REVIEW stays eligible; DATE stays deferred.
- For the reverse diagnostic, include already assigned eligible groups when testing QIDs not covered by the forward pass. This tests coverage beyond orphan mentions.
- Results are separate experimental proposals. Do not replace saved assignments or promote a model because its unresolved count is lower.

## Global constraints

- Worktree: `D:/Projects/GeoAI-luke-pilot-20261028`; preserve existing modified/untracked files.
- Reuse `training_k80_v2`: 5,060 train, 607 validation, 608 public-test states; retain page-disjoint membership, source exclusions and immutable original hashes.
- The public test is a held-out subset of cached ZELDA data, not an official benchmark. Public annotations are incomplete. Synthetic stop means no annotated positive remains, not verified exhaustive negative truth.
- Pilot inputs: saved 100 pages with their 132 revision scopes. No new corpus download, paid BigQuery, Geography or full-corpus matching.
- Old LUKE weights are not compatible Laya weights. Preserve LUKE code, checkpoints and reports as the comparison baseline.
- Upstream source pin: `NandhaKishorM/laya` commit `9afa7f3d4af18f8fa0c25517a440a05d10395b99`.
- Base checkpoint pin: `convaiinnovations/laya` revision `7b928d828b7b0e022f929d9bd2e44165aa270148`, English root checkpoint. Verify licenses, requirements and weight hashes before loading.
- Existing aggregate budget is US$10. No installation, GPU start or training is authorized by this planning document alone.
- Current live VM is TERMINATED: `geoai-luke-pilot-20261028`, `geo-hagai-ndvi`, `us-central1-c`, g2-standard-4/L4. No new VM or resource deletion is included.

## Review focus

1. Token limits must not silently remove, merge or truncate distinct option identities.
2. Multi-positive public labels must not become false single-answer errors or false negatives.
3. Validation/calibration must not share pages with training or test; upstream random state splitting is insufficient.
4. Frozen-to-full training must explicitly re-enable encoder gradients; a second upstream call alone does not do that.
5. STOP for one candidate chunk is local to that chunk, not proof that all candidates were considered.

## Reuse and files

Reuse existing JSONL/hash utilities, source exclusions, ZELDA cache, trigram, exact matching, QID filters, grouping and resource guards. Do not refactor those components for this experiment.

| New file | One responsibility |
|---|---|
| `GG_Data/entity_resolution/laya_model/prepare_training.py` | Convert cached labelled decisions, preserving split/positive/removal provenance; build reverse examples from cached full annotations. |
| `GG_Data/entity_resolution/laya_model/model.py` | One canonical Laya question formatter and token-safe decision/removal interface for training and inference. |
| `GG_Data/entity_resolution/laya_model/train.py` | Thin upstream training wrapper: frozen warmup, encoder tuning, budget guards and checkpoint receipts. |
| `GG_Data/entity_resolution/laya_model/evaluate.py` | Label-aware metrics, candidate/order diagnostics and comparison report. |
| `GG_Data/entity_resolution/hundred_page_pilot/run_laya.py` | Read saved pilot artifacts, call matching stages, save proposals and complete accounting. |
| `GG_Data/entity_resolution/laya_model/test_contract.py` | Focused format, split, label, gradient, removal and guard tests using small fixtures. |
| `GG_Data/entity_resolution/laya_model/README.md` | Input/output fields, commands, one short explanation per file and limits. |

No new orchestration framework. Root owns integration/GPU; independent adapter and read-only review work can run in parallel with disjoint file ownership. The GPU has one owner.

## Tasks and checks

### 1. Convert existing data (local data owner; no GPU)

**Depends on:** none. **Output:** new JSONL plus provenance/count/hash manifest.

- [ ] Add failing tests for preserved page splits, multi-positive targets, true terminal states and stop wording.
- [ ] Implement `prepare_records(source: Path, output: Path, direction: str) -> dict` using the saved data and cached full annotation relation.
- [ ] Do not infer reverse negatives from absence in a truncated forward top-80 pool. Retain full positive IDs and report incomplete supervision.
- [ ] Preserve multi-positive probabilities with equal mass over known valid options; report any target-set changes. Evaluate success as membership in the valid set, not upstream argmax-of-gold.
- [ ] Build removal/singleton/stop states with no test data entering training. Split validation pages deterministically into tuning and calibration, and publish membership.
- [ ] Run focused tests and compare every source/output row count. Training expansion counts are measured, not assumed to equal the original 5,060.

### 2. Canonical joint formatting and capacity (model owner)

**Depends on:** task 1 schema; fixture work can start in parallel. **Output:** `make_question(record: dict, direction: str) -> dict` and `choose_remaining(agent, record: dict, direction: str) -> list[dict]`.

- [ ] Add tests for STOP wording, stable candidate IDs, option reordering, duplicate names with distinct identities, removal and empty pools.
- [ ] Reuse upstream question validation/encoding. Use the same formatter in training and inference.
- [ ] Dry-run token checks for 5/10/15/20 options and checkpoint budgets; test up to max_len 1024/head_max_len 256 only if token evidence requires it. Record context/name retention and all rejected inputs.
- [ ] Choose capacity from these measured checks; no fixed top-80 assumption. Partition a retained ranked pool into fitting chunks when required, using the same chunk/removal semantics during training.
- [ ] STOP exhausts one chunk only; continue all retained chunks. Record original pool coverage, retrieval misses and chunk count. Do not claim global inventory coverage for top-K retrieval.
- [ ] Reject empty/invalid gold mass, collapsed options or lost target identities instead of upstream uniform fallback or silent item loss.

### 3. Training wrapper and local verification (training owner)

**Depends on:** tasks 1 and 2. **Output:** training commands, tested guards and new checkpoint directory.

- [ ] Reuse upstream `items_from_rows`, `train_model`, RLCD loss and checkpoint format; use external page-disjoint calibration rather than the default random item split.
- [ ] Test frozen encoder evaluation mode, no encoder gradients, and actual nonzero encoder update after explicit unfreezing.
- [ ] Preserve the existing warmup rule: at least four validation observations and three successive relative loss changes <=1%, at most 40 warmup epochs. No full tuning if stability is not reached; report incomplete training.
- [ ] Train the head first, then explicitly set encoder parameters trainable and tune all weights. Shuffle option order with target permutation; do not change labels or thresholds based on the public test.
- [ ] Checkpoint each bounded training unit and write stage, updates, hashes, timings, cost estimate and exit reason. Do not claim exact optimizer resume unless optimizer/scheduler/RNG states are saved.
- [ ] Run `python -m pytest GG_Data/entity_resolution/laya_model/test_contract.py -q` and existing relevant filter/training contract tests; record exact counts and unrun GPU checks.

### 4. GPU benchmark, warmup and tuning (root only)

**Depends on:** tasks 1-3 and explicit duration/resource approval. **Output:** benchmark receipt, frozen/full checkpoints and validation results.

- [ ] Refresh VM status, aggregate runtime/cost ledger and shutdown guard before start. Use the existing L4 only.
- [ ] Install pinned dependencies in a task-local environment; verify architecture/weight load and measure a short real training/inference batch.
- [ ] Re-estimate remaining runtime from measured throughput. Reserve transfer/shutdown time; do not start a stage that cannot fit the approved limit.
- [ ] Record pre-training validation, frozen warmup and full tuning results for both directions. No unbounded seed/epoch/model search.
- [ ] Stop and save partial results on insufficient capacity, failed stability, budget exhaustion or numerical/architecture failure; do not represent partial work as a completed 100-page result.

### 5. Held-out evaluation, then 3/10/100 pages (root; independent evidence reviewer)

**Depends on:** task 4. **Output:** immutable proposals, score traces and baseline comparison.

- [ ] Evaluate the untouched public test once after validation-based selection. Report candidate coverage, valid-set selection accuracy, stop precision/recall, denominators and incomplete-label limits, separately by direction.
- [ ] Retain pilot targets of >=90% selection accuracy and >=90% stop precision. Report confidence intervals; 100-page predictions are not verified gold.
- [ ] Run 3 pages first, check identity/row/provenance conservation, then 10 and 100 only if checks and resource allowance pass. Below-target quality is labelled experimental; no production promotion.
- [ ] Reuse cleaned mentions, exact matches and filtered same-page/revision QIDs. Run forward first; apply reverse diagnostic to uncovered QIDs against all eligible groups, including groups with prior assignments.
- [ ] Report assigned mentions, covered QIDs, multi-matches, unresolved, excluded, DATE-deferred, not-presented and not-run separately. Show added/lost/changed proposals against the saved LUKE baseline with evidence examples.
- [ ] Transfer and hash-check artifacts before stopping the VM; verify TERMINATED. Preserve all prior artifacts and resource disks.
- [ ] Commit only new/relevant code and docs after staged review. Do not include ignored datasets or secrets. Report local checkpoint/GitHub protection accurately.

## Estimate and approval state

- Estimate v1, 2026-10-30: **4-8 hours elapsed execution**, mode 6 hours, including preflight; approval_wait and GPU-capacity/environment waits excluded and tracked separately. This is a model-derived planning range, not a measured guarantee.
- Task basis: local conversion/formatting 1-2h; wrapper/tests/integration 1.5-3h with independent work overlapped; GPU setup/train/test/transfer at most 2h if approved; evidence/report/checkpoint 0.5-1h. Reuse limits coding; training convergence and inference throughput remain unknown.
- Epoch PERT inputs: O=4, M=6, P=8 hours, expected=6h; feedbackRef `a5187f1f-cad1-46a8-86cc-af37350fa0e9`. Superpowers tasks and Epoch use the same end-to-end scope/time basis. Generic reference-class estimates omit this bounded GPU experiment and are not used to shorten the range.
- Measured active_work is unknown; preflight wall time starts 2026-10-30 05:34:40 Asia/Jerusalem. Do not label wall time active work. Record future phase start/end and waits explicitly.
- Saved ledger, corroborated by live VM timestamps: aggregate runtime **5.2422h**, estimated aggregate spend **US$7.3422**, actual billing unavailable. Existing runtime cap **6h** leaves **45.47 minutes**.
- Requested resource exception: **at most 2 new VM-running hours**, raising aggregate cap to **7h15m**, while retaining aggregate **US$10**. At the existing conservative US$1/h compute allowance this gives **US$9.34**, before any unaccounted storage/transfer charges; verify/reserve those costs before starting. This is an estimate, not billing or a guaranteed spend cap.
- OWNER approved the complete plan and runtime exception in this conversation. Execution began at 05:43:22 on 30 October 2026, Asia/Jerusalem. The SDD progress ledger records implementation, checks, resource gates and pending work.
- Execution checkpoints: first ten minutes after approval, then every 5-10 minutes with finished work, next step, blockers and resource usage; report earlier when a limit or changed assumption blocks work.

## State

- [x] Inspect current training/pipeline contracts and saved data schema.
- [x] Verify current VM is stopped with a live read; verify remaining ledger allowance.
- [x] Inspect upstream training/format APIs and pin source/checkpoint revisions without installing or downloading weights.
- [x] Coordinate Superpowers task scope and Epoch estimate; self-review interfaces, coverage and resource limits.
- [x] OWNER duration/resource approval.
- [x] Implement adapters, pipeline integration and local tests.
- [x] Verify inputs and complete a bounded GPU benchmark; retain failed diagnostics.
- [x] Stop the existing VM, verify transferred diagnostics and record actual runtime.
- [ ] Frozen warmup/full tuning, held-out evaluation and 3/10/100-page predictions: blocked by measured throughput under the approved resource cap.
- [x] Finish and verify local forward cache; report the resource blocker and save a local code checkpoint.

Primary references: [Laya fine-tuning guide](https://github.com/NandhaKishorM/laya/blob/9afa7f3d4af18f8fa0c25517a440a05d10395b99/docs/finetune.md), [upstream trainer](https://github.com/NandhaKishorM/laya/blob/9afa7f3d4af18f8fa0c25517a440a05d10395b99/laya/train.py), [checkpoint](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148).

## Conditional capacity exception, proposed 06:59 on 30 October Asia/Jerusalem

Not approved and not started. Three failed requests left the existing VM TERMINATED; the last GCP response named us-central1-a as available. Read-only checks found no machine image or disk with the proposed names.

Ponytail full: reuse the stopped VM environment through one native machine image; do not rebuild dependencies or create an orchestration layer. Superpowers affected task breakdown: root exclusively creates image -> creates one guarded temporary VM -> verifies copied environment and payload hashes -> runs the existing benchmark gate. The existing training and 3/10/100 tasks are unchanged. After verified local result transfer, delete only the approved temporary VM/boot disk and image. Original VM/disk remain stopped and retained. Independent local input diagnosis can continue in parallel.

Exact proposed resources: machine image `geoai-laya-pilot-20261030-image`, VM and boot disk `geoai-laya-pilot-20261030`, zone `us-central1-a`, same g2-standard-4/L4/100GiB. No simultaneous running GPU. Maximum aggregate new running time remains7200seconds; aggregate26100seconds and US$10 unchanged. Configure7200second STOP guard before use and set a shorter remaining-time deadline if any previous successful new interval exists.

Bounded incremental storage allowance US$0.23 for at most8h: 100GiB balanced disk at0.000136986/GiB-hour plus a conservative100GiB machine-image allowance at0.00014/GiB-hour =US$0.2216, rounded upward toUS$0.23. Require total conservative estimate <=US$9.58 before creation, leavingUS$0.42 belowbudget. Same-region copy; existing transfer reserve retained; billing is unknown. Fail closed if the image/disk/transfer estimate cannot fit.

Epoch affected setup scope O0.16/M0.25/P0.42hours, rawexpected0.26h (10–25minutes), feedbackRef827adc91-f2f1-4ba4-bf21-77ebf9ab8b65. Same Superpowers dependencies, elapsed execution basis, excludes approval/capacity waits; overall4–8h unchanged. No unresolved planning disagreement. Estimated remaining3–7h execution; if approved07:05, completion10:05–14:05 on30October Asia/Jerusalem, excluding further waits. First checkpoint10min after approval. The approved plan's existing-VM-only restriction requires OWNER approval for this exception.


### Capacity update, 07:00 on 30 October Asia/Jerusalem
The fourth start of the approved existing VM succeeded. The temporary-resource exception above is withdrawn and must not be executed. No alternative resources were created. The original7200second STOP guard remains active; outer working deadline08:59local, including transfer and shutdown.

### Measured stop, 07:23 on 30 October Asia/Jerusalem

The bounded FP32 diagnostic passed only with native AMP/checkpointing disabled, Math SDPA and MHA fastpath disabled. Frozen sample32items7.093s; validation64items batch4=11.520s, batch16=11.827s. Seven unchanged full validation passes project9.88h atbatch16, excluding all training/calibration/evaluation/pageinference. Original4–8h planning estimate did not establish resource feasibility. The resource admission gate failed; do not start training or silently reduce validation/stability requirements. Full-encoder capacity remains unmeasured.

Existing VM verified TERMINATED, successful interval07:00:02.855–07:21:31.396Asia/Jerusalem,1288.541s. Aggregate runtime20160.485s; conservative aggregate estimateUS$7.7001347 including prior reserve, not billing. Root transferred24diagnostics and hash-verified all files. No alternate resources or new fitted predictions. Local CPU cache and verification finish without cloud cost. Final report: docs/reports/2026-10-30-laya-joint-pilot.md. A reduced experiment or additional resources require a new concrete, measured plan; neither is authorized by this status note.
