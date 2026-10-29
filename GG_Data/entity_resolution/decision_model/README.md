# Entity decision model

This package owns public training preparation, the canonical LUKE scalar scorer,
and training/restart logic. Data processing calls its inference functions.
Training does not import the `hundred_page_pilot` pipeline or the historical
`luke_pilot.model`. Small JSONL, hashing and stability helpers remain shared
from `luke_pilot.data`; pure trigram retrieval comes from `../trigram.py`.

| File | Responsibility |
|---|---|
| `prepare_training.py` | Cached ZELDA exclusions, page-disjoint splits, reverse questions, removal/singleton states and frozen manifests. |
| `model.py` | Canonical `CandidateScorer`, text options, marginal set loss, checkpoint loading and option scoring. |
| `train.py` | Cached frozen-head warmup, encoder tuning, validation, checkpoint selection and exact restart state. |
| `test_training_contract.py` | CPU import independence, checkpoint parameter names, encoder freeze behavior and shared retrieval checks. |

## Training contract

Encoder: `studio-ousia/luke-base`, pinned revision
`7438924defd9f3c2018d63c16073bf4bcb6a70aa`.
The CLS vector enters LayerNorm, Linear, GELU and a shared scalar Linear head.
This is a JEV-inspired independent decision scorer, not a reproduction of a
proprietary JEV model. QID strings are metadata, not answer tokens.

The frozen encoder stays in evaluation mode. Its deterministic features are
cached once. The head must have at least four validation observations and three
successive relative loss changes no greater than 1%, within 40 warmup epochs.
Then the encoder is tuned at learning rate 1e-5 and the head at 1e-4. The planned
run uses two full epochs. If stability or budget limits prevent this transition,
the output must report that the requested training is incomplete.

Marginal set loss allows any remaining labelled positive to win a single
decision. Additional singleton-positive states teach every known positive to
beat stop; a fixed removal order alone does not ensure this. Public annotations
are incomplete. A synthetic terminal state means no labelled positive remains,
which is weaker than exhaustive negative truth.

## Commands

Run from the project root. Imports and `--help` do not load model weights or
start training. Data preparation requires the already cached approved inputs
and a new, empty output directory:

```powershell
python -m pytest GG_Data/entity_resolution/decision_model/test_training_contract.py -q
python -m GG_Data.entity_resolution.decision_model.prepare_training --archive ARCHIVE --selection SELECTION --passages PASSAGES --page-ids PAGE_IDS --out NEW_TRAINING_INPUTS --candidate-count 80
```

On the approved GPU, use the frozen public inputs and existing model cache:

```bash
python -m GG_Data.entity_resolution.decision_model.train benchmark --inputs INPUTS --output NEW_BENCHMARK_DIR --max-hours .25 --pair-batch-size 8
python -m GG_Data.entity_resolution.decision_model.train train --inputs INPUTS --output NEW_TRAIN_DIR --max-hours REMAINING_ALLOWANCE --pair-batch-size 8 --full-epochs 2 --checkpoint-steps 500
```

Resume with `--resume PATH_TO_LATEST_PT`; input and training configuration hashes
must match. Preserve prior output directories. Subtract setup, benchmark and
previous GPU work from the approved aggregate allowance before execution.
These commands document the interface; the separation refactor authorizes no run.

The head keeps the same `scorer.*` parameter names and the encoder retains
`encoder.*`. Head-only checkpoints still contain the head state dictionary;
full-stage checkpoints contain both encoder and head. Existing archived code,
input manifests and receipts remain the evidence for prior runs. Relocation
does not claim that saved weights were trained with this new source layout.
