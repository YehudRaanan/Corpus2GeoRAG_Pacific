# 100-page entity-linking pilot

This folder runs the approved pilot on the new Daniel Parquet. It keeps the
original rows and records each page, revision, candidate and model decision.
The full corpus is not rerun. All paths below are relative to the project root.

## Code map

| File | What it reads and does | Main result |
|---|---|---|
| `prepare_pages.py` | Selects 100 source titles, reuses exact local passage evidence, checks dated raw Wikipedia revisions until each copied passage matches or the recovery limit is reached. | Original rows with page/revision IDs; raw text, API evidence, hashes and explicit unresolved reasons. |
| `collect_entities.py` | Reads only the used revisions. Extracts direct article links, including links inside the supplied references, tables and template arguments. Reuses local metadata, accepts a selected-QID BigQuery export, then fills API gaps. | Linked QIDs, page's own QID, official English labels, aliases, descriptions, native P31 types and provenance. |
| `prepare_training.py` | Reads cached ZELDA. Excludes pilot pages and detectable copied passages, splits by source page, builds reverse questions and variable candidate pools. | Frozen train/validation/diagnostic JSONL with removal and singleton-positive states. |
| `model.py` | Reuses the existing LUKE scorer. Converts an official entity and each mention alternative into a text pair. | One shared scalar score per option, including the stop sentence. |
| `train.py` | Checks input hashes; benchmarks real optimizer memory; trains the head with a frozen encoder until stable, then tunes encoder and head. | Restartable checkpoints, validation history, public diagnostic results and timing. |
| `match.py` | Groups literal names and Daniel types; accepts strict exact pairs; ranks remaining local alternatives by trigram; scores and removes alternatives until stop wins. | Exact pairs, ranked jobs, scores and the complete local decision trace. |
| `report.py` | Freezes source-link positive evidence before predictions. Checks input lineage, exports all matches back to the original rows and calculates supported metrics. | Matched/unresolved Parquet and a results summary. |
| `test_pipeline.py` | Small CPU regression tests for identity, many-to-many decisions, loss, restart safety and source preservation. | Reproducible checks without GPU access. |

These are ordinary functions and command-line scripts, not a new execution
framework. Shared helpers come from the existing `luke_pilot` package.

## Identity and matching rules

Daniel groups use the literal `(word, entity_group)` on each page and revision.
Repeated occurrences remain in `source_row_indices`; they are never discarded.
An exact pair needs the identical official English label, exactly one Daniel
type for that name, and exactly one QID with that label in that page/revision.
Aliases and case folding help trigram retrieval only. Native Wikidata P31
types are retained separately; they are not guessed into PER/ORG/LOC/DATE/MISC.

Every remaining QID asks which local Daniel groups refer to it. The model picks
one option, records the pair, removes that option for this QID only, and repeats.
A group can therefore match several QIDs, and a QID can match several groups.
The final entity key is `(QID, Daniel entity_group)`.

The stop option is exactly:

> None of the remaining mention groups refers to this entity.

Stop wins equal scores. An accepted pair stays accepted after the final stop.
Since each query/option pair is independent of the other alternatives, unchanged
scores are computed once and reused in the loop. Candidate count is variable;
there is no fixed architectural maximum. A truncated pool's stop applies only
to the evaluated pool. `excluded_count` records candidates that were not tested.

## Training

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

## Saved pilot data

Base directory: `Data/external/hundred_page_pilot_20261028`.

- `selection.json`: frozen page selection and original input hash.
- `selected_mentions.parquet`, `passages.parquet`, `revisions.parquet`: selected
  original rows and used historical text evidence. `checked_revisions.parquet`
  also includes recovery attempts that were not used.
- `collection_v2/`: corrected linked-entity collection and native metadata.
- `training_k80_v2/`: corrected public training data and hash manifest.
- `source_link_reference_v2.jsonl`: prediction-independent, positive-only checks.
- `matching_k80_v2/`: grouped rows, exact pairs, candidates and workload counts.
- `runtime_cost_ledger.jsonl`: operation, delay and estimated cost records.

Earlier outputs remain for audit. They are not silently overwritten by V2.
Wikipedia text is historical; QID sitelinks and metadata may be current or cached.
Each source and retrieval time is retained. Raw containment shows that a passage
exists in a saved revision; it does not prove this was the original extraction
revision. Expanded template content is outside the direct raw-link collection.
Unlinked names and dates are not added in this approved linked-QID pilot.

## Commands

Run from the project root. Use a new output directory for a new run. For example:

```powershell
python -m pytest GG_Data/entity_resolution/hundred_page_pilot/test_pipeline.py -q
python -m GG_Data.entity_resolution.hundred_page_pilot.match --mentions Data/external/hundred_page_pilot_20261028/selected_mentions.parquet --entities Data/external/hundred_page_pilot_20261028/collection_v2/entities.parquet --output NEW_MATCHING_DIR --candidates 80
```

On the approved GPU, with the saved public inputs copied into the same package
layout and the existing Hugging Face cache available:

```bash
python -m GG_Data.entity_resolution.hundred_page_pilot.train benchmark --inputs INPUTS --output NEW_BENCHMARK_DIR --max-hours .25 --pair-batch-size 8
python -m GG_Data.entity_resolution.hundred_page_pilot.train train --inputs INPUTS --output NEW_TRAIN_DIR --max-hours REMAINING_ALLOWANCE --pair-batch-size 8 --full-epochs 2 --checkpoint-steps 500
python -m GG_Data.entity_resolution.hundred_page_pilot.match --jobs JOBS --checkpoint CHECKPOINT --output NEW_INFERENCE_DIR --device cuda --max-hours REMAINING_ALLOWANCE
```

The operator must subtract setup, benchmark and earlier GPU runs from the
six-hour aggregate allowance. A per-command limit does not replace that ledger.
Training resumes with `--resume PATH_TO_LATEST_PT`; inputs and training config
must match. Inference resumes from completed score records in its output folder.
A torn final score record is preserved as evidence before prefix recovery.

## Evaluation and limits

Report selection accuracy, stop metrics and pair metrics on the held-out public
diagnostic, with exact denominators and the incomplete-label caveat. Candidate
coverage is a retrieval result, not model accuracy. Daniel has type labels and
raw markup that public training does not fully reproduce; this is a domain gap.

The 100-page source-link reference includes only complete matching link-anchor
spans at unique raw passage placements. It can measure recovery of these supported
positive pairs. It cannot establish overall precision or stop precision. Other
predictions remain unverified, not automatically false. The 90% targets cannot
be claimed for the full pilot from this positive-only reference.

Budget: US$10 for the new task, at most six new GPU hours. Keep an estimated
cost reserve and verify the VM stops. Forecasts are not a billing-account cap.
Local commits protect code history only. Ignored data and checkpoints are local;
no GitHub push is authorised for this pilot.
