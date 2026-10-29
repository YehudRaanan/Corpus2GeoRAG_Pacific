# 100-page entity-linking pilot

This folder runs the approved pilot on the new Daniel Parquet. It keeps the
original rows and records each page, revision, candidate and model decision.
The full corpus is not rerun. All paths below are relative to the project root.

## Code map

| File | What it reads and does | Main result |
|---|---|---|
| `prepare_pages.py` | Selects 100 source titles, reuses exact local passage evidence, checks dated raw Wikipedia revisions until each copied passage matches or the recovery limit is reached. | Original rows with page/revision IDs; raw text, API evidence, hashes and explicit unresolved reasons. |
| `collect_entities.py` | Reads only the used revisions. Extracts direct article links, including links inside the supplied references, tables and template arguments. Reuses local metadata, accepts a selected-QID BigQuery export, then fills API gaps. | Linked QIDs, page's own QID, official English labels, aliases, descriptions, native P31 types and provenance. |
| `recover_page_qids.py` | Checks the three saved unresolved revisions; reconstructs flat Ship-template targets, checks failed article links and preserves current lookup evidence separately. | A separate expanded candidate inventory and all 369 case reports; no mention assignments. |
| `prepare_candidates.py` | Groups literal names and Daniel types; accepts strict exact pairs; ranks remaining local alternatives with shared trigram retrieval. Does not load the model. | Exact pairs, ranked jobs, source row groups and workload counts. |
| `resolve_entities.py` | Checks readiness, loads the canonical decision model only for inference, then selects and removes alternatives until stop wins. | Restartable scores, model pairs and complete local decision traces. |
| `readiness.py` | Checks checkpoint, training inputs/code and evaluation evidence before inference. | Explicit technical and quality gates; historical evidence is not rewritten by this refactor. |
| `report.py` | Freezes source-link positive evidence before predictions. Checks input lineage, exports all matches back to the original rows and calculates supported metrics. | Matched/unresolved Parquet and a results summary. |
| `test_pipeline.py`, `test_pipeline_layout.py` | Small CPU regression tests for identity, unrestricted many-to-many decisions, loss, restart safety, source preservation and separate lazy CLIs. | Reproducible checks without GPU access. |

These are ordinary functions and command-line scripts, not a new execution
framework. Pure trigram retrieval is shared with training through
`../trigram.py`; JSONL and hash helpers come from `luke_pilot.data`.
Training and the canonical scorer live in
[`../decision_model/`](../decision_model/README.md): `prepare_training.py`,
`model.py` and `train.py`. There are no forwarding wrappers for the removed
combined `match.py` or relocated training modules.

## Complete pipeline

1. `prepare_pages.py` preserves original Daniel rows and binds passages to saved
   historical Wikipedia page/revision evidence.
2. `collect_entities.py` reads those revisions and collects linked QIDs and native
   metadata. `report.py --freeze-reference` freezes supported source-link positive
   evidence before any predictions.
3. Separately, `decision_model.prepare_training` freezes public inputs;
   `decision_model.train` trains and evaluates the canonical model. `readiness.py`
   checks the saved evidence. Candidate preparation does not require this model.
4. `prepare_candidates.py` writes literal groups, strict exact pairs and local
   candidate jobs. `resolve_entities.py` reads jobs and the readiness-bound
   checkpoint, then writes scores, selected pairs and stop decisions.
5. `report.py` joins exact and model pairs to every original row and exports
   matched/unresolved mentions with source lineage and positive-only metrics.
6. `GG_Data/pipeline/post_qid_run.py` freezes page scopes or builds core tables
   from verified saved decisions. It uses `post_qid_pages.py`,
   `post_qid_entities.py` and `post_qid_mentions.py` for used revisions, typed
   entities, original mentions and their many-to-many bridge.
7. `post_qid_native.py` owns full native-record acquisition/reuse and source-bound
   consolidation. `post_qid_events.py` applies Event eligibility and exact-revision
   article boundaries. `post_qid_relations.py` preserves native assertions and
   explicitly derived reverse rows. `post_qid_eda.py` checks coverage and optional
   page co-occurrence separately from native relation weights.

Core population does not imply Events, Relations, Geography or seven-table
acceptance. Geography remains pending. The open `what_happened_at` spatial
date-filter issue remains a separate acceptance concern. This refactor does not
rerun data collection, training, inference or table population.

## Identity and matching rules

### Optional missing-QID recovery

The approved three-page recovery is a separate stage after collection. It does
not run the matcher or update existing tables. The final reviewed outputs are in
`Data/external/hundred_page_pilot_20261028/qid_recovery_20261029_v2/`; the earlier
directory retains the two original API responses. The final inventory has 135
page/revision/QID rows (112 original + 23 additions), all additions on Nishimura's
saved revision. Spellings, ship-type conflicts, changed years and missing pages
stay under review. Source enclosure is not a correct-identity label.

Replay the recovery into a new directory without network access:

```powershell
python -m GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids --output Data/external/hundred_page_pilot_20261028/qid_recovery_replay --request-cache Data/external/hundred_page_pilot_20261028/qid_recovery_20261029/requests
```

The stage refuses an existing output directory. `--allow-api` permits bounded
public lookups only when needed. Full evidence and limitations:
[`2026-10-29-unresolved-page-qid-recovery.md`](../../../docs/reports/2026-10-29-unresolved-page-qid-recovery.md).

Daniel groups use the literal `(word, entity_group)` on each page and revision.
Repeated occurrences remain in `source_row_indices`; they are never discarded.
An exact pair needs the identical official English label, exactly one Daniel
type for that name, and exactly one QID with that label in that page/revision.
Aliases and case folding help trigram retrieval only. Native Wikidata P31
types are retained separately; they are not guessed into PER/ORG/LOC/DATE/MISC.

Every remaining QID asks which local Daniel groups refer to it. The model picks
one option, records the pair, removes that option for this QID only, and repeats.
A group can therefore match any number of QIDs, and a QID can match any number
of groups. An observed two-QID result is not a schema or loop limit.
The final entity key is `(QID, Daniel entity_group)`.

The stop option is exactly:

> None of the remaining mention groups refers to this entity.

Stop wins equal scores. An accepted pair stays accepted after the final stop.
Since each query/option pair is independent of the other alternatives, unchanged
scores are computed once and reused in the loop. Candidate count is variable;
there is no fixed architectural maximum. A truncated pool's stop applies only
to the evaluated pool. `excluded_count` records candidates that were not tested.

## Training boundary

Training code and commands are in [`../decision_model/`](../decision_model/README.md).
The pipeline imports only its scoring functions for model decisions.

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
python -m pytest GG_Data/entity_resolution/hundred_page_pilot/test_pipeline.py GG_Data/entity_resolution/hundred_page_pilot/test_pipeline_layout.py -q
python -m GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates --mentions Data/external/hundred_page_pilot_20261028/selected_mentions.parquet --entities Data/external/hundred_page_pilot_20261028/collection_v2/entities.parquet --output NEW_MATCHING_DIR --candidates 80
```

On the approved GPU, with the saved public inputs copied into the same package
layout and the existing Hugging Face cache available:

```bash
python -m GG_Data.entity_resolution.hundred_page_pilot.resolve_entities --jobs JOBS --checkpoint CHECKPOINT --readiness READINESS_JSON --output NEW_INFERENCE_DIR --device cuda --max-hours REMAINING_ALLOWANCE
```

The readiness gate runs before output writes or model loading. Quality that
fails or is unknown requires the exact existing OWNER experimental disposition;
`--experimental-approval` supplies that evidence when applicable. The explicit
`--legacy-without-readiness` compatibility option is not for post-QID delivery.
Saved readiness manifests and archived source hashes can be stale after a code
move; a changed module path does not make an old checkpoint newly qualified.

For source reference and final exports, with frozen input paths:

```powershell
python -m GG_Data.entity_resolution.hundred_page_pilot.report --freeze-reference --mentions MENTIONS --revisions REVISIONS --links LINKS --output NEW_REFERENCE_JSONL
python -m GG_Data.entity_resolution.hundred_page_pilot.report --mentions MENTIONS --passages PASSAGES --matching MATCHING_DIR --inference INFERENCE_DIR --references REFERENCE_JSONL --output NEW_FINAL_DIR
python -m GG_Data.pipeline.post_qid_run --input-dir INPUT_DIR --output NEW_SCOPE_DIR
python -m GG_Data.pipeline.post_qid_run --input-dir INPUT_DIR --scope-dir SCOPE_DIR --inference-dir INFERENCE_DIR --native-dir NATIVE_DIR --model-dir MODEL_DIR --scope 3 --output NEW_CORE_DIR
```

The reference command belongs before inference. The post-QID core command checks
its frozen scopes, inputs and saved decision evidence; larger scopes retain their
existing acceptance gates. These examples document interfaces, not permission to
start a new run.

The operator must subtract setup, benchmark and earlier GPU runs from the
six-hour aggregate allowance. A per-command limit does not replace that ledger.
Training commands and restart rules are in the training README. Inference resumes
from completed score records in its output folder.
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
