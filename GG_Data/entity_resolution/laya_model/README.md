# Joint Laya pilot

This experiment uses the pinned upstream Laya encoder, joint option head and RLCD training code. LUKE weights and saved assignments are unchanged. QIDs and group IDs remain metadata; names, types, descriptions and context form the model input. All outputs are experimental proposals.

## Files and contracts

- `prepare_training.py`: preserve cached public-data splits and full annotation provenance; create forward/reverse and removal states.
- `model.py`: `make_question(record, direction)` is the single formatter; `partition_record` retains every candidate in token-safe chunks. `choose_remaining` recomputes joint scores after each removal and ends each chunk with STOP.
- `train.py`: local preparation, bounded GPU benchmark, frozen warmup, explicit encoder unfreeze and tuning. Root owns cloud execution and resource guards.
- `evaluate.py`: `evaluate_records` accepts `{id, direction, candidates, positive_ids, full_positive_ids?, removed_ids?, remaining_full_positive_ids?}` and predictions `{id, candidate_id}`; `None` is STOP. `evaluate_agent` uses `partition_removal_states` with each base's fixed initial token-safe chunks, scores one decision per labelled state/chunk, saves each result, and resumes without repeating completed decisions. Input must include the initial state (`removal_index=0`) of every base.
- `../hundred_page_pilot/run_laya.py`: CPU preparation from all saved cleaned occurrences, strict exact pairs, shared QID/source/type filters and retained trigram pools; separate bounded inference on the frozen 3/10/100 scopes.
- `test_contract.py`, `test_prepare_training.py`, `test_train.py`, `test_run_laya.py`: focused offline contracts. Model/token tests need the saved upstream source and tokenizer, with no weight download.

A raw record contains `id`, `entity` (`name`, optional context/description/type), stable-ID `candidates`, and explicit `direction`. Labelled records add `positive_ids`; equal mass over all valid remaining positives is preserved. `full_positive_ids` is immutable original gold; use `remaining_full_positive_ids`, or subtract `removed_ids`, for remaining-state coverage. Never infer reverse negatives from a truncated forward pool.

## CPU pilot preparation

Training preparation is separate from the article pipeline. `train prepare` runs
tokenisation locally and writes hashed tensors; the GPU consumes those tensors.
An optional `--train-bases-per-direction N` selects complete source questions by
a fixed hash, including every removal state. It does not sample validation or
calibration. The receipt lists every selected ID. Large pools produce many local
STOP chunks, so reports include positive-only accuracy and results by direction.

```powershell
python -m GG_Data.entity_resolution.laya_model.train prepare --inputs PREPARED_RECORDS --base BASE_CHECKPOINT --output PREPARED_ITEMS --train-bases-per-direction 128
python -m GG_Data.entity_resolution.laya_model.train benchmark --inputs PREPARED_RECORDS --prepared-items PREPARED_ITEMS --base BASE_CHECKPOINT --output BENCHMARK --max-seconds 300
python -m GG_Data.entity_resolution.laya_model.train train --inputs PREPARED_RECORDS --prepared-items PREPARED_ITEMS --base BASE_CHECKPOINT --output NEW_TRAINING_RUN --max-seconds 3600
```

The benchmark updates a discarded head with the encoder frozen. It does not
measure full encoder training speed or memory. Warmup requires four validation
observations and three consecutive relative loss changes within 1%, with at most
40 epochs. Full tuning starts only after that check. Checkpoints preserve model
weights; exact optimizer resume is not supported.

The benchmark also times a separate FP32 validation sample. Its projection counts
all full validation passes; it excludes training, calibration and file transfer.
Do not start a stage whose measured workload cannot fit the approved allowance.
Saving a checkpoint retains the original tokenizer files only after checking
that its vocabulary, backend and active settings did not change. This keeps CPU
cache hashes valid and avoids a loader metadata rewrite.

Use the existing project environment with PyArrow and source-parser dependencies. Preparation does not import Laya or load weights. Use a new output directory.

```powershell
.venv-template-pilot/Scripts/python.exe -m GG_Data.entity_resolution.hundred_page_pilot.run_laya prepare --mentions Data/external/review_advisory_v1_20261030/input/cleaned/mentions.parquet --entities Data/external/filtered_matching_20261030/qid_filter/entities.parquet --scopes Data/external/review_advisory_v1_20261030/scopes/scope_manifest.json --output Data/external/laya_pilot_20261030/pilot_input --candidate-count 80
```

The copied Parquet inputs and all derived files are hashed in `manifest.json`. Full inputs contain 40,070 occurrences, 100 pages and 132 revision scopes. Preparation reuses the existing exact-name/unique-QID/single-Daniel-type rule, grouping, REVIEW eligibility, EXCLUDE rejection, DATE deferral, source-protected candidates and review-coverage additions. A retained top-K pool is retrieval coverage, not complete inventory coverage. `--candidate-count 0` retains all local candidates; it does not bypass token-safe chunking during inference.

Forward token-safe partitions can be prepared on CPU before paid inference. This
loads a local tokenizer only, streams all forward jobs, and reports progress each
100 jobs. Use the tokenizer directory from the exact inference checkpoint and
the same token/option budgets. Use a new cache directory; preparation does not
change the pilot input manifest.

```powershell
python -m GG_Data.entity_resolution.hundred_page_pilot.run_laya prepare-chunks --input-dir PILOT_INPUT --tokenizer CHECKPOINT/full/tokenizer --output FORWARD_CHUNK_CACHE --max-options 20 --max-len 1024 --head-max-len 256
```

The cache has one `forward_chunks.jsonl` row per forward job and a manifest bound
to the original input manifest, exact `model.py` hash, tokenizer file hashes,
budgets, cache hash and complete job/chunk/candidate counts. Supply
`--chunk-cache FORWARD_CHUNK_CACHE` to `score`. Inference validates the cache once,
keeps the selected scope's chunks, and checks each chunk's evidence and fit.
Cached and uncached forward questions and decisions are identical. Reverse
questions remain dynamic and uncached. Tokenizer/model/input/budget changes
require a new cache. A failed or interrupted preparation has no complete cache
manifest and cannot be used for inference.

## Held-out evaluation and pilot inference

Use the pinned upstream source on `PYTHONPATH` and an approved environment. These commands load a complete local **Laya** checkpoint (`model.safetensors`, `rl_agent_config.json`, encoder and tokenizer). The loader hashes artifacts before loading, detects byte changes, and rejects device fallback. Cloud start, dependency installation and GPU resource approval are separate root tasks.

```powershell
python -m GG_Data.entity_resolution.laya_model.evaluate --records Data/external/laya_pilot_20261030/training/public_test.jsonl --checkpoint CHECKPOINT/full --output EVALUATION_DIR --device cuda --max-seconds 600
python -m GG_Data.entity_resolution.hundred_page_pilot.run_laya score --input-dir PILOT_INPUT --checkpoint CHECKPOINT/full --output SCOPE_3_OUTPUT --scope 3 --device cuda --max-seconds 600
```

Run 3, then 10, then 100 only after identity/conservation and resource checks pass. The `--max-options`, `--max-len` and `--head-max-len` settings must match the measured capacity. A `STOP` file in the output directory prevents the next joint model call. `--baseline-pairs` accepts saved baseline pair JSONL for added/lost/changed comparisons; baseline values do not affect selection.

Forward inference first applies exact pairs and Laya to retained same-page/revision/type-compatible pools. Reverse diagnostics then ask **all eligible Daniel groups**, including assigned groups, about only QIDs still uncovered on that revision. Selection remains many-to-many. Each question saves full joint removal traces, local chunk STOP, probabilities, token/context diagnostics and pool coverage. Model proposals retain source-row/occurrence IDs, cleaned/raw context provenance and QID metadata. Original inputs and baseline assignments are never replaced.

## Outputs and limits

Evaluation saves `inputs.json`, `chunk_records.jsonl`, `predictions.jsonl`, and `report.json`. It reports chunk valid-set accuracy, non-STOP precision, STOP precision/recall, original candidate-pool coverage, Wilson 95% intervals, complete denominators and explicit source/chunk not-run IDs. Per-source-state recovery means at least one selected first choice is a known positive; terminal success requires every chunk to STOP. These are conditional labelled-state results, not complete model rollout accuracy. Extra unannotated selections are reported separately, including success without such extra selections. Chunk decision accuracy is not directly comparable with the old LUKE whole-pool 551/608 result.

Pilot outputs include bound inputs, resumable forward/reverse traces, separate pair proposals, dynamic reverse jobs, progress and final accounting. Counts include assigned/unresolved occurrences, excluded/DATE-deferred rows, not-presented groups/occurrences, covered/uncovered QID-revision rows, retrieval-omitted pairs, REVIEW/previously eligible groups and many-to-many pairs. A budget stop preserves completed question traces, reports remaining IDs, and raises `TimeoutError`; it is not a complete scope result. A completed scope has `summary.json` with `status=complete`.

Public annotations are incomplete. An unannotated selection is not verified false; synthetic STOP means no annotated positive remains. Intervals are state-level Wilson intervals, not page-cluster-adjusted intervals. Pilot proposals have no verified gold. Lower unresolved counts do not establish improved accuracy or authorize production promotion. Real CUDA restore, throughput, warmup stability, tuning and complete 3/10/100 outputs require separate measured execution.
