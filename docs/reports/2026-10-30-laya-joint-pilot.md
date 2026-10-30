# Laya joint-decision pilot

Status at 07:30 on 30 October 2026, Asia/Jerusalem: local implementation, training inputs and the full forward cache are verified. The existing L4 completed a bounded benchmark, but the measured resource gate failed. At 5.41 validation items/second, the seven required full validation passes project **9.88 hours**, before training, calibration, held-out evaluation or page inference. This cannot fit the approved two new VM hours. The VM is verified **TERMINATED**. No fitted checkpoint, held-out quality result or new 3/10/100-page matching result was produced. The default GPU trainer still needs a tested runtime configuration; the working configuration was diagnostic only. This is an incomplete pilot with a measured resource blocker.

## What changed

The new adapter uses the pinned upstream Laya encoder and joint Transformer decision head. The question, evidence and answer options are processed together. After each selected option is removed, the model computes a new decision. This differs from the saved independent LUKE pair scorer. One model has separate, explicit forward and reverse instructions.

Training is separate from the article pipeline. Code and commands: [Laya README](../../GG_Data/entity_resolution/laya_model/README.md). Earlier code checkpoints are `ae9bc83` and `d4d0c55`; neither was pushed. Existing LUKE weights, original mentions, labels and assignments were preserved.

Source pins:

- [Laya source](https://github.com/NandhaKishorM/laya/tree/9afa7f3d4af18f8fa0c25517a440a05d10395b99).
- [English checkpoint](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148), 421,293,827 parameters. Weight SHA256 `891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c`.

The real checkpoint passed a finite CPU forward. Hashes before and after loading were unchanged. No new GPU result is implied by this CPU check.

## Training data

Cached ZELDA source annotations were reused. Original page splits and source hashes were retained. Validation pages were split into tuning and calibration; public-test pages enter neither fitting nor calibration.

| Split | Canonical states | Source pages | Prepared joint items |
|---|---:|---:|---:|
| Train, all available | 39,338 | 260 | Not all tokenized for this bounded pilot |
| Train, deterministic budget subset | 514 | Within train pages | 5,836 |
| Validation | 2,259 | 16 | 27,490 |
| Calibration | 1,978 | 16 | 12,208 |
| Held-out public test | 3,512 | 33 | GPU evaluation not run |

The training subset retains 128 complete base questions in each direction, selected by a fixed hash. Every removal state of a selected base remains. Validation and calibration were not sampled. Full reverse pools can contain 848 candidates; token-safe partitioning retains them in several local decisions. STOP ends one chunk, not the whole original pool.

All 45,534 prepared train/validation/calibration items passed shape, target and hash checks. Preparation took 2,306.672 seconds locally. Of 5,836 train items, 5,578 (95.58%) are STOP-labelled. Reports must therefore show positive-only accuracy; overall accuracy alone could hide an always-STOP model.

Public annotations are incomplete. STOP means no annotated positive remains, not verified absence of every real match. A source-grounded sample audit and automated integrity checks do not establish exhaustive gold accuracy.

## Training and resource gate

The encoder stays frozen until at least four full validation observations show three successive relative loss changes within 1%. Full tuning explicitly re-enables encoder gradients. The test suite verifies a real upstream joint head updates while its encoder is frozen, then verifies an encoder update after unfreezing. It does not prove real-data convergence.

The shortest complete path has 239,654 model item forwards, about 220.38 million unpadded input tokens and 552 attempted optimizer updates, before benchmark, held-out evaluation or pilot inference. Seven full validation passes are needed; the final full-epoch observation is reused instead of running the same validation again. Validation/calibration use a separate batch size of 16, while training stays at 4.

The bounded benchmark measures discarded frozen-head updates and FP32 validation at batch sizes 4 and 16 on the same validation sample. It reports finite logits, changes in selected choices, logit differences, memory and throughput. Full encoder memory/speed remain unknown until stable warmup permits that stage. Do not start a stage whose measured work cannot fit the remaining allowance.

Limits: existing VM only; at most 7,200 new VM-running seconds; aggregate cap 26,100 seconds and US$10. Prior verified runtime is 18,871.944 seconds. Conservative aggregate estimate with all new allowance is US$9.3422, including the previous US$2 storage/transfer reserve. This is not actual billing or a guaranteed hard spend cap. The existing disk persists while the VM is stopped.

The server-side 7,200-second STOP setting was updated and verified. Failed provisioning changes GCP's `lastStopTimestamp` without changing its previous successful `lastStartTimestamp`; subtracting those values would invent runtime. New runtime must use a new successful interval, plus the preserved prior ledger.

### Measured GPU outcome

The existing VM started on the fourth request at **07:00:02.855** and stopped at **07:21:31.396**, 30 October Asia/Jerusalem. No alternative VM, disk or machine image was created. The temporary-resource proposal was withdrawn when the existing VM became available.

| Diagnostic | Observed outcome |
|---|---|
| Original AMP training / FP32 validation benchmark | CUDA illegal-address error |
| Blocking CUDA diagnostic | Frozen training completed; validation hung; root stopped only its own process |
| Math attention, default fused MHA | CUDA illegal-address error |
| Math attention, fused MHA disabled, AMP training | CUDA illegal-address error |
| Full precision, checkpointing disabled, Math attention, fused MHA disabled | Complete finite benchmark |

The last configuration uses native runtime options and the same inputs and initial weights. Its updates were discarded. This establishes one working benchmark configuration, not a proven exact cause of the earlier CUDA errors or a validated full-tuning configuration.

| Successful benchmark work | Measurement |
|---|---:|
| Frozen-head training, 32 items | 7.093 seconds; 4.511 items/second |
| FP32 validation, 64 items, batch 4 | 11.520 seconds; 5.556 items/second |
| FP32 validation, same 64 items, batch 16 | 11.827 seconds; 5.411 items/second |
| Choices changed between validation batch sizes | 0 / 64 |
| Maximum absolute logit difference | 0.0000174642 |
| Peak CUDA allocation, batch 16 | 4,816,892,416 bytes |
| Seven full validations at measured batch-16 rate | 35,560.5 seconds; 9.88 hours |

These are small-sample timing projections, not guaranteed lower bounds. They exclude training and all downstream work. A smaller training subset alone cannot fix the resource gap because the unchanged validation workload already exceeds the allowance. Benchmark selection/STOP scores are not reported as trained-model accuracy.

**New VM time:** 1,288.541 seconds, or 21 minutes 28.541 seconds. **Aggregate VM time:** 20,160.485 seconds, or 5.6001 hours. **Conservative aggregate estimate:** US$7.7001, including the existing reserve; actual billing is unavailable. `budget_after.json` contains exact timestamps and assumptions. The existing stopped disk remains and can still incur storage cost.

All 24 diagnostic files were transferred and individually hash-verified. Archive SHA256: `463652d54ef55c5cd9bdb6720433691a402a5a6b3e3ac753926a63dcc6ff4326`. No new trained weights or assignments were accepted. No further GPU run is pending.

## Pilot comparison inputs

The same 100 saved pages and 132 revision scopes contain 40,070 original rows: 20,931 eligible, 14,980 source-excluded and 4,159 DATE-deferred. REVIEW remains eligible. There are 12,557 groups, 12,871 page/revision/QID inventory rows and 2,173 current exact group pairs. Forward pools reuse existing trigram and protected candidates. Reverse diagnostics test uncovered QIDs against all eligible groups on the same page/revision, including assigned groups. Results will remain separate proposals.

The correct LUKE reference combines old saved occurrence links, current exact links and the later forward/reverse additions. Group pairs must not be expanded to every current occurrence: doing so invents 1,276 unsaved links and 58 assigned occurrences.

| Scope | Eligible occurrences | Assigned under current filters | Unresolved | Covered QID/revision rows |
|---|---:|---:|---:|---:|
| 3 pages | 239 | 202 | 37 | 65 / 196 |
| 10 pages | 2,025 | 1,781 | 244 | 482 / 1,057 |
| 100 pages | 20,931 | 17,936 | 2,995 | 5,301 / 12,871 |

The raw old composite has 21,238 occurrence/QID links. Of these, 19,749 pass current source/type filters; 1,489 fail them. Filter removals are not model differences. Raw and policy-compliant references are saved separately, with exact occurrence bridges and input/output hashes.

The pinned upstream formatter caps each rendered option at 48 tokens. Two rendered options containing original Daniel names require 53/54 tokens (the raw names alone each use 47), affecting 99 forward questions on two page/revision scopes, all outside the 3/10-page subsets. Increasing the overall context budget cannot remove that per-option cap. These whole questions remain in the inventory with **NOT_RUN_INPUT_CAPACITY**, their original candidates and an explicit reason. They produce no model call, STOP decision, prediction or pair. Source names were not silently truncated or repaired. Cache schema 2 records these failures; a complete cache is not a completed matching run.

At 07:29 the complete local cache passed input/code/tokenizer/hash/order/count checks and candidate-identity conservation for every successful question. It accounts for **12,871 jobs**, with **12,772 representable jobs**, **99 explicit failures**, **68,470 chunks**, and **554,200 retained candidate slots** in the original inputs (549,256 in representable jobs). Scope 3 contains196jobs/4,284slots; scope10 contains1,057jobs/45,605slots; neither has a capacity failure. Slots are repeated job-candidate entries, not unique entities. Cache SHA256: `d4f3cb4146d5a01fdc515df75ca97dc7a41b3c9d10b4863e9124fd4745ce3c03`. The incomplete v2 prefix was reused only after explicit retrospective provenance and chunk verification; original files were preserved.

## Evidence and pending work

- `Data/external/laya_pilot_20261030/prepared/`: immutable canonical records and audit.
- `Data/external/laya_pilot_20261030/items_v1/`: verified CPU training inputs. The original completion receipt is preserved; portable token binding was added with an explicit audit note after checking canonical formatter functions were unchanged.
- `.superpowers/sdd/2026-10-30-laya-joint-decision-pilot/baseline_reference/`: complete 3/10/100 occurrence-level references.
- `.superpowers/sdd/2026-10-30-laya-joint-decision-pilot/resource-review.md`: measured sizes, labels, lengths and symbolic workload.
- `Data/external/laya_pilot_20261030/gpu_capacity_attempts.json`: start outcomes.
- `Data/external/laya_pilot_20261030/diagnostics/`: 24 verified GPU diagnostic files and manifest.
- `Data/external/laya_pilot_20261030/budget_after.json` and `final_vm_state.json`: final cost/runtime estimate and stopped VM evidence.
- `Data/external/laya_pilot_20261030/forward_cache_v3/` and `forward_cache_v3_audit.json`: complete, hash-bound local forward input cache and scope-level conservation checks.
- `.superpowers/sdd/2026-10-30-laya-joint-decision-pilot/progress.md`: work state, estimates, checkpoints and waits.

Verification: **78 Laya tests pass**, plus **60 pipeline/filter/shared tests** in a separate run. These are separate suites, not a claim of 138 unique tests. Ruff and compilation checks passed before the final documentation update. Independent reviews checked data provenance, pipeline timeout/resume, fixed held-out partitions, cache equivalence and explicit capacity failures. The finite GPU benchmark passed only with the diagnostic configuration above; full tuning and real inference remain unrun.

Pending: warmup, full tuning, held-out evaluation and 3/10/100-page inference are blocked by measured throughput. The initial elapsed/resource estimate was too low for the full validation workload. No accuracy or unresolved improvement is claimed.

The next experiment must change a concrete constraint: either use a smaller fixed training/monitoring set and first demonstrate three pages, or authorize a larger measured resource allowance. Neither change has been applied. A revised design must count training, validation, calibration and iterative inference together before asking for approval; it must retain independent held-out evaluation and disclose reduced evaluation coverage. This report does not claim that a smaller three-page proposal already fits the remaining budget.

Backup: code has **Local checkpoint only** status. Ignored data artifacts are **Unprotected**; a Git commit is not their backup.
