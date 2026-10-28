# LUKE Decision Pilot Implementation Plan

> For agentic workers: execute with superpowers:executing-plans; preserve this plan and its progress ledger.

**Goal:** Train a variable-candidate entity-name decision model and test all 642 entity-page records on the saved ten Wikipedia revisions, within US$20.

**Architecture:** LUKE-base encodes one mention/context and candidate-name pair per forward pass. A shared LayerNorm/MLP scalar head, following the scorer pattern in he-jev/laya, scores every candidate and an explicit NONE option. Grouped cross-entropy supports variable candidate counts. Freeze the entire encoder first; unfreeze all encoder parameters only after head stability and inadequate held-out validation. This is a JEV-style adaptation, not a reproduction of the proprietary JEV model.

**Tech Stack:** Python, PyTorch, Transformers, PyArrow, pytest; GCP CLI and one L4 VM.

**Spec:** The OWNER-approved request in this conversation: ZELDA public training data; no same-page constraint for training; same-page candidates on the saved ten-page test; 90% correct selections and 90% NONE precision pilot targets; encoder frozen initially; optional full fine-tuning; US$20 total; maximum eight GPU hours and automatic shutdown. Training labels are entity names/identities, not predicted QID strings.

## Global Constraints

- Owner root; exclusive ownership of this worktree and newly created experiment VM. Existing files and cloud resources remain untouched.
- Worktree D:/Projects/GeoAI-luke-pilot-20261028; input artifacts read-only at D:/Projects/GeoAI-source-page-ids-20261026/Data/external/ten_page_structure_alignment_20261028.
- Preserve 545 unresolved source pages and all original 309K mentions; do not rerun the corpus.
- Model studio-ousia/luke-base revision 7438924defd9f3c2018d63c16073bf4bcb6a70aa.
- ZELDA public train JSONL; document-disjoint validation and held-out public evaluation. Exclude saved ten-page titles/text and detectable overlaps from training. Never train or tune on ten-page references or predictions.
- Synthetic NONE by removal of a known correct candidate is labelled synthetic and reported separately from natural test NONE.
- Test reference labels are fixed from context/link/metadata evidence before predictions. Ambiguous cases remain unverified; independent means independent of predictions, not an independent human annotator. No accuracy claim on unverified records.
- Training candidate count varies; test candidate pool is all A QIDs on the same saved page, with top-five retrieval reported separately if used. No fixed five-class output, no QID token target, no trigram/graph weighted blend.
- Runtime ceiling 8 GPU hours; VM automatic STOP; local worker time limits; cost forecast stop threshold US$15; total budget US$20. No paid model APIs.
- Proposed machine g2-standard-4 in us-central1, 1 L4, 4 vCPU, 16 GiB RAM; published rate US$0.706832276/hour excludes disk/network. Eight hours compute US$5.6547. Reserve US$2 for task disk/IP/transfer; retain remaining budget for uncertainty, not extra experiments.
- Approval arrived 2026-10-28 20:47 Asia/Jerusalem. Model-derived total elapsed estimate 4-8 hours including ~8 minutes preflight, excluding ~2 hours approval wait and unavailable-GPU waits. Next checkpoint 20:55; finish window 2026-10-29 00:50-04:50 Asia/Jerusalem. Active work unmeasured. No calibrated P80 claim.
- Epoch estimate feedbackRef 8a871a2c-4694-4874-a208-839dd8465e30; same scope/dependencies/units/time basis as this breakdown. PERT 4/6/8 hours. Superpowers decomposition and Epoch scope agree; generic statistical correction is not pilot calibration.

## Review Focus

- Correct entity absent from candidate pool: NONE, not a forced best candidate.
- Duplicate aliases/QID names: one candidate per identity; alternative true identities recorded, not arbitrarily collapsed.
- Candidate order/count changes: scores follow candidate identity and padding cannot win.
- Frozen warmup: encoder unchanged, no unfreezing before head stability; test set never controls training.
- VM/SSH failure or elapsed limit: no duplicate paid jobs, persistent logs/checkpoints, automatic stop.

## Tasks and State

### Task 1: Reproducible data and reference preparation

Owner root. Inputs saved revisions and public ZELDA ZIP; produces train.jsonl, validation.jsonl, public_test.jsonl, sample.jsonl, references.jsonl, manifests. No model predictions read during labelling. Estimate 1-2 hours elapsed.

- [ ] Test candidate identity deduplication, variable counts, absent-gold NONE and split disjointness.
- [ ] Inspect archive members; read JSONL without executing pickle. Reuse public candidate data only through safe parsing if possible; otherwise document a transparent candidate derivation from public labelled training examples.
- [ ] Prepare bounded public training sample with hard negatives and synthetic NONE. Record all sampling, exclusions and hashes.
- [ ] Prepare all 642 test records and source-linked reference evidence. Mark ambiguous/unverified cases explicitly.
- [ ] Freeze reference hashes before inference. Verify exact ten revision IDs and input hashes.

### Task 2: Shared candidate model and training gates

Owner root; depends on Task 1 schemas. Files GG_Data/entity_resolution/luke_pilot/{data.py,model.py,train.py,test_pilot.py}. Produces tested model, training logs, frozen/full checkpoints. Local preparation estimate 1-1.5 hours; cloud execution 1.5-3 hours included in total 4-8 hours.

- [ ] Write and run failing tests for variable-option grouped loss, permutation equivariance, encoder freeze/update, NONE metric denominators, stability and budget guards.
- [ ] Implement shared CLS scalar scoring with candidate names and marked mention context, explicit NONE, grouped cross entropy and dynamic padding.
- [ ] Run a tiny randomly initialised LUKE CPU smoke test; no full-model CPU training.
- [ ] Freeze encoder; cache deterministic representations where practical. Minimum three validation checkpoints; stability requires finite losses and validation loss relative change <=1% for three consecutive checks after minimum warmup. Bound warmup and report if not stable.
- [ ] If stable and either validation target <90%, unfreeze all encoder parameters with lower learning rate; preserve frozen checkpoint. If stable and targets met, skip full tuning. If instability or budget prevents continuation, report it; do not silently change models or targets.

### Task 3: Controlled cloud execution

Owner root; depends on tested local code and ready data. Resource geoai-luke-pilot-20261028 in project geo-hagai-ndvi, only one zone/instance active. Produces hardware/version evidence, runtime ledger, checkpoints and outputs.

- [ ] Validate CLI leaf syntax with installed help; check exact project, zone, machine, image, resource absence, quota and price. Read-only commands have no dry-run flag; creation has no dry-run flag, so review arguments before run.
- [ ] Create only after data/code readiness; no service-account credentials needed by training worker. Set eight-hour maximum run duration, termination STOP, no restart, and no broad new firewall rules.
- [ ] Transfer only experiment inputs/code. Verify hashes and nvidia-smi; run small GPU batch before full training. Record billable time including environment setup.
- [ ] Train frozen stage then conditional full stage; evaluate disjoint public data without using final ten-page labels for selection.
- [ ] Infer all 642 saved entity-page records; download verified outputs before shutdown. Stop VM; preserve task-owned disk until exact cleanup is authorised if deletion approval is absent.

### Task 4: Evaluation, review and delivery

Owner root; depends on frozen references and predictions. Produces prediction/evidence CSV and Parquet, model/checkpoint, reproducible scripts, metrics/cost report. Estimate 0.5-1.5 hours, included in total.

- [ ] Report known-label selection accuracy, NONE precision/recall/counts, candidate coverage, unverified denominator, type/page breakdowns, frozen versus full results and examples. Include uncertainty and distinguish synthetic/public from real sample labels.
- [ ] Compare against saved trigram baseline as a baseline only, never as truth.
- [ ] Verify original input hashes, exact row coverage, no full corpus work, budget ledger and stopped resource state.
- [ ] Request one fresh final code review under executing-plans; fix material findings with focused tests. Create local Git checkpoint. Ask before any first push; report backup status accurately.

## Sources

- https://github.com/flairNLP/zelda
- https://nlp.informatik.hu-berlin.de/resources/datasets/zelda/zelda_full.zip (HEAD 477139364 bytes)
- https://huggingface.co/studio-ousia/luke-base
- https://github.com/he-jev/laya/blob/main/rl_common.py (shared scorer pattern; our per-pair CLS adaptation differs from Laya's joint option markers)
- https://cloud.google.com/products/compute/pricing/accelerator-optimized?hl=en (Iowa L4 g2-standard-4 price verified from official table)
