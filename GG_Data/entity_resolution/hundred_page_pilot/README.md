# 100-page entity-linking pilot

This folder runs the approved pilot on the new Daniel Parquet. It keeps the
original rows and records each page, revision, candidate and model decision.
The full corpus is not rerun. All paths below are relative to the project root.

## Code map

| File | What it reads and does | Main result |
|---|---|---|
| `prepare_pages.py` | Selects source titles and checks raw revision evidence for an initial pilot. `adapt_frozen_input(...)` reuses a verified frozen selection for the new Source-QID input. | Original rows with global row indices, page/revision IDs, source hashes and explicit unresolved reasons. |
| `collect_entities.py` | Reads only the used revisions. Extracts direct article links, including links inside the supplied references, tables and template arguments. Reuses local metadata, accepts a selected-QID BigQuery export, then fills API gaps. | Linked QIDs, page's own QID, official English labels, aliases, descriptions, native P31 types and provenance. |
| `recover_page_qids.py` | Replays the original three-page recovery, or reads an explicit pilot manifest with `--all-pilot`. Checks supported ship-template targets and raw links, using cache-first bounded title/QID lookups. | A new candidate inventory, source spans and current lookup evidence; no mention assignments. |
| `prepare_mentions.py` | Reads the original rows, exact raw revisions and recovered targets. Uses visible name fields, link anchors and same-revision QID names to recover complete names. Keeps competing or weak source evidence under review. | Row-preserving corrected `word`, `word_original`, recovered spans, a mention/span bridge and repair reasons. |
| `filter_source_content.py` | Locates original spans in the exact saved revision and applies source-content rules. | All original rows plus KEEP/EXCLUDE/REVIEW, reason, source ranges, revision hash, policy version and cleaned matching context. |
| `clean_source_text.py` | Cleans saved raw source, projects each Daniel passage through its character-origin map, then maps each original mention. | All input rows, unchanged original text/offsets, separate `Text_clean`, clean offsets and explicit mapped/excluded/uncertain reasons. |
| `match_exact.py` | Applies the literal unique-name/type/QID rule to eligible groups, separately from model preparation. | Auditable groups, exact pairs and input hashes. |
| `prepare_candidates.py` | Groups eligible names and Daniel types, validates supplied exact-stage pairs, ranks residual local alternatives with trigram and retains source-supported candidates. Does not load the model. | Ranked jobs, occurrence groups and workload counts. |
| `resolve_entities.py` | Checks readiness, loads the canonical decision model only for inference, then selects and removes alternatives until stop wins. | Restartable scores, model pairs and complete local decision traces. |
| `run_model.py` | Inspects the fixed checkpoint, executes a real CUDA restore/scoring check, and launches one approved 3/10/100-page scope through `resolve_entities.infer`. | New readiness evidence, scope-bound experimental approval and inference outputs. |
| `readiness.py` | Checks checkpoint, training inputs/code and evaluation evidence before inference. | Explicit technical and quality gates; historical evidence is not rewritten by this refactor. |
| `report.py` | Freezes positive source evidence and exports original-row results. `compare_exports(...)` retains strict model-comparison rules; `compare_workflows(...)` separately checks old/new workflow lineage and outcomes. | Parquet exports or all-row CSV/JSONL workflow cases with explicit eligibility denominators; no unsupported accuracy claim. |
| `test_pipeline.py`, `test_pipeline_layout.py` | Small CPU regression tests for identity, unrestricted many-to-many decisions, loss, restart safety, source preservation and separate lazy CLIs. | Reproducible checks without GPU access. |

These are ordinary functions and command-line scripts, not a new execution
framework. Pure trigram retrieval is shared with training through
`../trigram.py`; JSONL and hash helpers come from `luke_pilot.data`.
Training and the canonical scorer live in
[`../decision_model/`](../decision_model/README.md): `prepare_training.py`,
`model.py` and `train.py`. There are no forwarding wrappers for the removed
combined `match.py` or relocated training modules.

## Revised Source-QID run — 30 October 2026

New artifacts belong under `Data/external/revised_pipeline_20261030/`. Earlier
pilot, training and inference artifacts remain unchanged. The interfaces below
describe the workflow; they do not establish completed execution or final counts.
See the [approved revised plan](../../../docs/superpowers/plans/2026-10-30-revised-pipeline-new-daniel-input.md).

1. **Bind the input.** `prepare_pages.adapt_frozen_input(input_path, frozen_root,
   output, receipt_path=None)` verifies the new input hash, original values and
   global `source_row_index`, then reuses the saved page/revision evidence.
   The adapted rows and revisions go to `input/`. New `Source` is the supplied
   **article QID**, not a numeric Wikipedia page ID or a mention assignment.
   `source_title` keeps the readable title; `source_page_qid` keeps its QID.
2. **Prepare and clean.** Existing name preparation and source filtering write
   `input/prepared/` and `input/filtered/`. `clean_source_text.clean_mentions(...)`
   writes every row to `input/cleaned/mentions.parquet`. Shared
   `prepare_candidates.matching_eligibility(...)` supplies
   `matching_eligible` and `matching_eligibility_reason`.
3. **Save exact decisions.** `match_exact.prepare(mentions, entities, output, ...)`
   writes `input/exact/`. Candidate `prepare(..., exact_path=...)` checks those
   exact pairs against the current groups and writes `input/matching/`.
   Exact matching needs the identical official name, one Daniel type and one QID
   for that label on that revision. Repaired names cannot supply exact proof.
4. **Run fixed-model decisions.** `run_model.setup(...)` creates actual restore
   evidence in `model_readiness/`; `run_model.run_scope(...)` reads
   `scopes/jobs_3.jsonl`, `jobs_10.jsonl` or `jobs_100.jsonl`. It saves each
   `scope_N/experimental_approval.json` and `scope_N/inference/`. The existing
   stop rule and per-QID removal preserve many-to-many matches.
5. **Close matching.** `post_qid_run.build_core(..., stage="final")` validates
   frozen inputs, approval, complete scores and native records. Only this closed
   stage creates provisional identities for eligible unmatched groups.
6. **Add article-bound enrichment.** `post_qid_native.py` validates full native
   records and provenance. `post_qid_events.apply_cached_events(...)` requires
   retained direct links in the exact used revisions for added Events and
   reports cache gaps. `post_qid_relations.py` keeps native directed assertions
   and explicit inverse provenance. `post_qid_run.assemble(...)` checks the exact
   final core manifest, typed endpoints and table controls before saving a new
   local snapshot. Geography and database loading remain outside this run.

The nine Daniel fields remain in each revised mention's `raw` dictionary:
`entity_group`, `score`, `word`, `start`, `end`, `Source`, `Index`, `Text`, `subtype`.
`raw_original_word` preserves the new input word; `word_original` retains the
earliest original word through preparation. Working `word` and clean offsets
address `Text_clean`; raw `start`/`end` still address raw `Text`.
`occurrence_id` equals the existing `mention_id(input_sha256, source_row_index)`
and stays fixed across stages. Across different input hashes, compare the
verified source row lineage, not equal mention IDs.

Eligibility requires verified page/revision evidence, accepted source scope and
a usable mapped clean span. A mapped mention in a passage with
`clean_text_needs_review=True` remains `SOURCE_REVIEW`. Excluded, review,
`PAGE_REVISION_UNRESOLVED` and `DEFERRED_DATE` rows remain in the audit denominator
and receive no entity bridge. Pending eligible rows use `PENDING_MATCHING`.
`post_qid_run.write_stage(..., stage="pending")` saves rows before matching;
`stage="exact"` saves accepted exact entities and links together. A model-stage
core can save accepted decisions without provisional identities. Final matching
uses `stage="final"`; resolved entities remain keyed by QID plus Daniel type.

Prepare the immutable scope manifest with the actual cleaned/matching paths:

```powershell
$pilotPython = ".\.venv-template-pilot\Scripts\python.exe"
$runRoot = "Data/external/revised_pipeline_20261030"
& $pilotPython -m GG_Data.pipeline.post_qid_run --input-dir "$runRoot/input" --matching-subdir matching --mentions-name cleaned/mentions.parquet --output "$runRoot/scopes"
& $pilotPython -m GG_Data.pipeline.post_qid_run --input-dir "$runRoot/input" --scope-dir "$runRoot/scopes" --scope 3 --stage pending --output "$runRoot/pending_3"
```

Use new output directories. Before GPU execution, the run owner supplies
`input_manifest.json`, the archived code, fixed checkpoint and hash-bound
approval evidence. The manifest binds the frozen scope, original input/row file,
source reference, allowed page/revisions and checkpoint. Revised schema 2 also
binds each `scope_jobs[N]` file hash and exact frozen page membership; editing a
question or selecting a different same-sized scope is rejected. On the approved GPU:

```bash
python -m GG_Data.entity_resolution.hundred_page_pilot.run_model --run-root Data/external/revised_pipeline_20261030 --scope-dir Data/external/revised_pipeline_20261030/scopes --training-root Data/external/hundred_page_pilot_20261028/training_k80_v2 --model-dir outputs/train_20261029 --setup
python -m GG_Data.entity_resolution.hundred_page_pilot.run_model --run-root Data/external/revised_pipeline_20261030 --scope-dir Data/external/revised_pipeline_20261030/scopes --training-root Data/external/hundred_page_pilot_20261028/training_k80_v2 --model-dir outputs/train_20261029 --scope 3 --max-hours 1.2
```

Proceed to 10 and 100 only after the preceding scope checks pass. Pair batch size
is 16; each inference call permits at most 1.2 hours. The approved revised run
permits at most 90 new GPU minutes within the existing aggregate US$10 and
six-hour limits, including setup time. Per-call limits do not replace that ledger.
The fixed model's held-out stop precision is 278/311, below 90%. Actual technical
restore evidence and an exact run-bound experimental exception do not create a
quality pass or Daniel accuracy result.

`report.compare_workflows(previous_export, current_core, output)` compares the
old baseline or corrected export with the new local tables by source row index.
It requires equal original values except the intentional Source title-to-QID
change. It reports all-row status/QID transitions, separate eligibility/review/
exclusion/DATE denominators and eligible gains/losses. Candidate and model truth
remain unknown. This is separate from the strict model comparator.

## Complete pipeline

1. `prepare_pages.py` preserves original Daniel rows and binds passages to saved
   historical Wikipedia page/revision evidence.
2. `collect_entities.py` reads those revisions and collects linked QIDs and native
   metadata. `report.py --freeze-reference` freezes supported source-link positive
   evidence before any predictions.
3. Separately, `decision_model.prepare_training` freezes public inputs;
   `decision_model.train` trains and evaluates the canonical model. `readiness.py`
   checks the saved evidence. Candidate preparation does not require this model.
4. After optional name preparation, `filter_source_content.py` records source
   eligibility without deleting rows. `prepare_candidates.py` writes eligible
   literal groups, strict exact pairs and local
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

### Separate text-cleaning pilot

`clean_source_text.py` is an independent local step. It reads the original
page-attached Daniel rows and the saved revision ledger. It does not run the
model, collect QIDs, or change previous assignments. It uses installed
`mwparserfromhell` and existing source rules, rather than the full FineWiki
HTML/dataset framework.

The original `Text`, `start`, `end`, row ID and type remain unchanged.
`word_original` retains Daniel's original entity text. A supported mapping
updates working `word` and writes `clean_start`/`clean_end` into `Text_clean`.
Removed citations and other excluded spans remain as rows with null clean
offsets. Captions and notes are omitted in this pilot, as agreed. Unsupported
syntax can remain in `Text_clean`; `clean_text_needs_review` flags affected
passages even when the mention itself maps. Repeated or nonexact
revision placements remain uncertain. This is not a historical template
renderer or a new entity-identity decision.

```powershell
.\.venv-template-pilot\Scripts\python.exe -m GG_Data.entity_resolution.hundred_page_pilot.clean_source_text --mentions Data/external/hundred_page_pilot_20261028/selected_mentions.parquet --revisions Data/external/hundred_page_pilot_20261028/revisions.parquet --page-id 1120226 --page-id 1365545 --page-id 240395 --output Data/external/hundred_page_pilot_20261028/source_text_cleaner_pilot_20261029/NEW_RUN
```

Use a new output directory for each run. Historical cleaner artifacts remain
separate. Revised candidate preparation explicitly consumes `Text_clean`, clean
offsets and shared eligibility when clean annotations are present; it rejects
mixed raw/clean input. The cleaner's status describes text/source mapping, not
whether an entity has a QID.

### Source-name experiment on the saved 100 pages

Training stays in `../decision_model/`. This experiment uses the fixed trained
checkpoint and does not change its input formatter or stop rule. Run both the
original and corrected arms with `--exclude-date --candidates 80`. DATE stays in
the output, with an explicit exclusion status. Changed names and groups with
source-review flags cannot supply automatic exact proof. An unchanged original
name can still use independent literal unique-name/type/QID proof, even when
QID-guided source evidence is also available.

`prepare_mentions.py` keeps every original row, type, text and offset. The old
offsets address `word_original`; separate repaired offsets address source
evidence. A reconstructed template title need not be a literal text substring.
The span ledger records this distinction. Unknown templates, competing names,
repeated passages and unverified normalized positions stay unchanged with a
reason. Full spans without an overlapping original mention remain separate
evidence and do not create Daniel rows.

The source parser is `mwparserfromhell==0.7.2`. The task-local environment is
`.venv-template-pilot`; the global environment is unchanged. Run each stage into
a new directory, in this order:

```powershell
$pilotPython = ".\.venv-template-pilot\Scripts\python.exe"
& $pilotPython -m GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids --all-pilot --mentions INPUT.parquet --revisions REVISIONS.parquet --collection COLLECTION_DIR --output RECOVERY_DIR
& $pilotPython -m GG_Data.entity_resolution.hundred_page_pilot.prepare_mentions --mentions INPUT.parquet --revisions REVISIONS.parquet --entities RECOVERY_DIR/entities.parquet --evidence RECOVERY_DIR/target_evidence.parquet --output PREPARED_DIR
& $pilotPython -m GG_Data.entity_resolution.hundred_page_pilot.filter_source_content --mentions PREPARED_DIR/mentions.parquet --revisions REVISIONS.parquet --output FILTERED_DIR
& $pilotPython -m GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates --mentions FILTERED_DIR/mentions.parquet --entities RECOVERY_DIR/entities.parquet --source-policy article-source-v2 --exclude-date --candidates 80 --output MATCHING_DIR
```

### Source filter for subsequent runs

`article-source-v2` checks each original occurrence, not an entire paragraph or
every use of the same name. Original `Text`, `word_original`, offsets, type and
row ID stay unchanged. The raw revision is checked against both its SHA-256 and
saved page/revision response. Only a unique literal passage placement can KEEP
an occurrence. Invalid, repeated or nonexact placements remain REVIEW.

KEEP covers article prose, factual infobox values, tables, supported displayed
names and framed image captions. EXCLUDE covers citations and bibliography,
hidden categories/link targets, filenames/image options, known navigation and
maintenance material, parameter keys and tag syntax. A citation inside an
infobox remains excluded. Known ship helpers reuse the documented recovery
rules, including hidden prefixes and display modes. Unknown nested templates,
explanatory notes, inline image labels, unsupported galleries and malformed markup remain
REVIEW. This is a bounded source parser, not a historical Wikipedia renderer or
a check that a mention names a real entity.

`mentions.parquet` contains **all** input rows. Its `source_scope_*` columns
store the decision, reason, policy, exact source evidence and cleaned context.
Only KEEP occurrences enter groups, type uniqueness, protected candidates,
trigram and model contexts. Citation/control/uncertain source spans are masked
in the separate context field; the original passage is not edited. DATE
exclusion applies after source eligibility. The linked-QID inventory is
unchanged; this stage does not rebuild graph inventories or collect new QIDs.

Second-pass rules recognise whole-body short citations, supported quote/list
fields, captions followed by image options, and explicitly structured gallery
filenames/captions. Gallery captions are parsed locally so nested citations and
hidden link targets remain excluded. Explanatory or mixed references stay
REVIEW. Plainlist uses content parameter 1 only; unknown extra parameters stay
REVIEW. Unknown quote attribution fields remain REVIEW.

Saved `article-source-v1` annotations remain readable, but a run must contain
one source policy. New filtering writes `article-source-v2`; old outputs are
not rewritten.

Candidate preparation detects annotations automatically, but the explicit
`--source-policy article-source-v2` flag above prevents accidental unfiltered
input. Unannotated historical inputs remain `LEGACY_UNFILTERED`; mixed,
unsupported or deliberately bypassed annotations are rejected. Every new
matching summary records its policy and counts. Use a new output directory.

After a separately authorised model run, `report.py` preserves all input rows
and emits `EXCLUDED_SOURCE`, `REVIEW_SOURCE`, `EXCLUDED_DATE`, `MATCHED` or an
explicit unresolved status. `unresolved_mentions.parquet` contains only
`UNRESOLVED_ENTITY` and `UNRESOLVED_PAGE_VERSION`, including for newly exported
legacy runs; old export files stay unchanged. Source exclusions/reviews are not
matching failures. Existing result tables are not accepted as new export
inputs, to avoid overwriting historical assignments.

Frozen source-link reference bytes stay unchanged. Filtered metrics use only
KEEP evidence anchors and eligible original rows; they remain incomplete
positive-only checks. `--compare-baseline/--compare-corrected` requires the same
source policy, so changing source scope cannot silently appear as a model-only
effect. Filtering and local candidate preparation do not establish new model
accuracy or permission to run inference.

Verification report:
[`2026-10-29-source-content-filter.md`](../../../docs/reports/2026-10-29-source-content-filter.md).
Second-pass comparison:
[`2026-10-29-source-filter-second-pass.md`](../../../docs/reports/2026-10-29-source-filter-second-pass.md).

Recovery is offline unless `--allow-api` is supplied. The approved run limits
new requests to 200 and recovery time to 1,800 seconds. Current title/QID
metadata remains separate from historical article evidence. Japanese metadata
can corroborate an identity; it does not import more Japanese article entities.

Inference still requires actual restore evidence and a separate hash-bound
experimental approval for the exact jobs. This approval does not change the
model's failed held-out stop-precision gate. `report.py` refuses partial scores,
preserves all row-to-QID matches, and compares the two arms by original row IDs.
Use `--compare-baseline EXPORT_DIR --compare-corrected EXPORT_DIR --output DIR`.
The original frozen positive reference stays unchanged; it cannot establish
overall accuracy or precision.

Plan and execution record:
[`2026-10-29-template-name-pilot.md`](../../../docs/superpowers/plans/2026-10-29-template-name-pilot.md).

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
& .\.venv-template-pilot\Scripts\python.exe -m GG_Data.entity_resolution.hundred_page_pilot.recover_page_qids --output Data/external/hundred_page_pilot_20261028/qid_recovery_replay --request-cache Data/external/hundred_page_pilot_20261028/qid_recovery_20261029/requests
```

The stage refuses an existing output directory. `--allow-api` permits bounded
public lookups only when needed. Full evidence and limitations:
[`2026-10-29-unresolved-page-qid-recovery.md`](../../../docs/reports/2026-10-29-unresolved-page-qid-recovery.md).

Daniel groups use the literal `(word, entity_group)` on each page and revision.
Repeated occurrences remain in `source_row_indices`; they are never discarded.
An exact pair needs the identical official English label, exactly one Daniel
type for that name, and exactly one QID with that label in that page/revision.
Aliases and case folding help trigram retrieval. In the source-name experiment,
literal label/alias occurrences can also protect candidates and repair token
cuts; this source evidence does not establish exact identity. Native Wikidata P31
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

Budget: the existing US$10 aggregate ceiling includes earlier pilot spending.
The 29 October template/name experiment allows at most three additional GPU
hours within the six-hour aggregate allowance. Keep an estimated cost reserve
and verify the VM stops. Forecasts are not a billing-account cap.
Local commits protect code history only. Ignored data and checkpoints are local;
no GitHub push is authorised for this pilot.

## Advisory source review

Source-review flags are retained as evidence, but do not block non-DATE
mentions from candidate preparation. Explicit source exclusions and unverified
page/revision identities still block matching; DATE remains deferred.
The context helper uses a verified clean span when available. Otherwise it uses
the unchanged original text and offsets, checked against the original word.
It records `clean` or `original` as the context basis and never invents clean
positions. A row without either valid span remains a data-validation failure.

The ordinary per-QID top-80 and source-supported candidate pools remain in use.
If a reviewed group is absent from every pool and is not exact-matched, its best
same-page trigram pairing is added. A missing named QID inventory is reported
explicitly. Pool inclusion does not prove that the correct QID was collected.
Changed candidate jobs require new model scores; the previous run stays intact.
