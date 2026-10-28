# 100-page entity decision pilot: design and implementation plan

> For agentic workers: implement with Superpowers after the OWNER duration approval. Use parallel workers only for independent files and read-only inputs. Root alone owns the GPU, cloud commands, integration and cost ledger.

**Goal:** Run the new Daniel data through revision matching, same-page QID collection, exact matching, trigram retrieval and iterative learned selection for about 100 Wikipedia pages, within US$10.

**Architecture:** Reuse the existing raw-data, revision-cache and LUKE scalar-scoring code. Train a shared per-option decision head over LUKE CLS representations, first with the encoder frozen and then with encoder tuning. For each QID/page/revision, select Daniel name/type groups individually until the full stop sentence wins.

**Tech stack:** Existing Python, PyArrow, PyTorch, Transformers and pytest; existing GCP CLI, one L4 GPU at most. No new framework or service.

## Verified starting point

- Worktree: `D:/Projects/GeoAI-luke-pilot-20261028`; branch `experiment/luke-decision-pilot-20261028`. Preserve the pre-existing uncommitted `luke_pilot/evaluate.py` change and all original worktrees.
- New input: `Data/external/hundred_page_pilot_20261028/georag_selected_v2.parquet`, downloaded and SHA-256 verified: `eb99863511b68c79aca37a6ef16e1b53fdb5c48a9fbd8d602db43b6a638f1deb`.
- 2,235,432 rows, 7,363 row groups, 5,693 distinct Source strings. Nine columns: entity_group, score, word, start, end, Source, Index, Text, subtype. The five entity_group values are PER, ORG, LOC, DATE, MISC; subtype is a separate source field.
- Text contains raw Wikipedia markup, including templates, references and tables. Existing rendered-text matching is insufficient.
- Old cache: 425 pages / 571 revisions, HTML and linked-QID metadata. Only 146 of these revision responses contain raw wikitext; 425 are HTML-only. Only 104 new Source labels overlap old labels. These counts do not establish raw-revision coverage of the selected sample.
- Previous L4 VM `geoai-luke-pilot-20261028`, project `geo-hagai-ndvi`, zone `us-central1-c`, freshly verified TERMINATED. No training or sample inference was resumed.
- Prior frozen and partly tuned checkpoints are a different query direction. Preserve them; do not call them trained reverse-loop models.

## Scope and decisions

- Pilot only: select 100 Source strings before looking at predictions, using stable SHA-256 order with seed 20261028. Include the previous ten titles if present, then fill from the remaining order. Record selection and any redirect collisions; do not silently replace unresolved pages to improve results. The delivered number of distinct resolved Wiki pages can be below 100.
- Scan the new file for inventory and selection; process only selected sources thereafter. Preserve all selected rows and stable original row indices. No re-extraction or old 309K rematching.
- Each passage may match a different revision. Keep `(page_id, revision_id)` throughout; never group revisions and take the first revision ID.
- Revision evidence means a revision whose raw content contains the copied text. It is not proof of the precise revision used by the original extraction.
- Compare original raw text and offsets before normalisation. Reuse full-text equality/containment evidence with explicitly recorded NFC/whitespace normalisation if needed. Do not strip markup then reuse raw offsets.
- Some new passages contain U+FFFD replacement characters. Preserve them and their offsets, flag them explicitly, and never silently repair them. Failed containment with damaged source text does not prove a wrong revision.
- Preserve every source section represented in Daniel's selected input, including templates, references and navigation. Do not apply the old article-body-only scope silently.
- QID collection can enumerate Wikipedia links and the page's own QID. This is not exhaustive recognition of unlinked entity mentions. An extra unlinked-entity extraction/linking stage is not included without a scope decision.
- Enumerate direct links in revision-pinned raw wikitext separately from rendered/transcluded HTML links. Only add rendered links with an explicit matching source-section basis; preserve their origin and retrieval date. Do not claim revision-pinned template contents from contemporary rendering alone.
- Use existing local data first. Use BigQuery for supported missing sitelink/QID/metadata data after a dry run and byte cap. Do not assume BigQuery has arbitrary historical article text; fill revision-content gaps from Wikimedia APIs, and entity metadata gaps from Wikidata.
- Historical Wikipedia text and current/cached Wikidata metadata are different timestamps. Save both revision provenance and metadata retrieval/snapshot time; do not label QID/types historical without evidence.
- Daniel identity remains literal `(word, entity_group)`. Occurrence context is retained separately. A group may link to several QIDs, and one QID may link to several groups. No global one-to-one constraint.
- Exact acceptance requires identical name AND comparable identical entity type AND exactly one distinct QID on the same page/revision. Aliases, case folding, substring similarity and ambiguous identities do not count as this exact rule.
- Native Wikidata P31 classes do not literally equal Daniel's five NER types. Pending OWNER decision: retain native types and skip exact acceptance when type equality cannot be established, or approve a separate mapping before automatic exact matching. Do not silently reuse an old mapping or inherit Daniel's type onto a candidate to manufacture equality.
- Exclude an accepted exact pair only from that QID's later decisions. Keep the group available to other QIDs, and other groups available to the same QID.
- Final identity key: `(QID, Daniel entity_group)`, retaining source group and occurrence lineage. A group unresolved on one page may be resolved on another.

## Minimal file structure

New stage files under `GG_Data/entity_resolution/hundred_page_pilot/`; keep the old pilot outputs immutable. Reuse existing helpers rather than duplicate their implementations. Each file starts with a plain-language explanation of inputs, outputs and its algorithm. Use normal names, type hints and only necessary comments. No line-count target that hides validation or makes code hard to read.

| File | One responsibility |
|---|---|
| `prepare_pages.py` | Select sources, preserve rows, reuse exact passage evidence, recover raw historical revisions, export metadata |
| `collect_entities.py` | Collect revision-scoped linked QIDs, names, aliases and native types, with provenance and completeness flags |
| `prepare_training.py` | Adapt cached ZELDA annotations into entity-question / mention-option pools and removal states |
| `model.py` | Reuse LUKE CLS/scalar head; define reverse text pairs and the training loss |
| `train.py` | Frozen warmup, definite encoder tuning, checkpoints, runtime and GPU/cost guards |
| `match.py` | Strict exact pairs, trigram rankings, candidate-size experiments and iterative selection traces |
| `report.py` | Coverage, independently supported evaluation, stage runtime, problems, adaptations and cost report |
| `test_pipeline.py` | Compact contract/regression checks covering the risks below |
| `README.md` | One command per stage and a readable explanation of the full flow |

## Training and decisions

- Use cached public ZELDA data, not predictions or old Daniel matching output as gold. Exclude selected source page IDs/titles and detectable copied text from public training. Split by source document before group/state construction.
- Question text contains the official entity name, aliases and available description; QID is metadata. Alternatives are Daniel-style mention strings with contexts. Public ZELDA does not provide Daniel's native type labels; do not invent them.
- Retain all known valid mention-group IDs. At a removal state, train on total probability assigned to remaining valid choices; once none remains, train on the stop sentence. The output remains a single selected alternative per forward decision.
- Exact stop sentence for this direction: `None of the remaining mention groups refers to this entity.` No plain NONE token as the sole semantic alternative.
- Public annotations are incomplete: a terminal training label means no remaining *labelled* positive in that option pool. Report this limitation and synthetic-stop examples separately.
- Warmup: original pinned LUKE base encoder frozen and in eval mode; train only the shared head. Reuse deterministic encoded features. Stability: at least four validation observations, with three consecutive relative validation-loss changes <=1%; maximum 40 head epochs. If this is not achieved, report the condition rather than silently unfreeze.
- Once stable, train encoder weights as requested, at a lower encoder LR than head LR. Initial settings reuse prior encoder 1e-5 / head 1e-4 and up to two full epochs. Select checkpoints with validation only. Save optimizer, RNG and progress for restart.
- The original 90% selection / 90% stop precision are evaluation targets, not guaranteed outcomes. The reverse many-to-many task also requires pair precision/recall and stopping error counts.
- Candidate list experiments: K=10,20,40,80 and all available if feasible. Measure validation candidate recall, decisions, memory, pair count and throughput. Choose the largest within measured limits and budget; do not tune K on final 100-page labels. Do not claim an architectural fixed maximum K.
- Within each question, sort the selected candidate pool by trigram, score each option and stop sentence, choose the highest remaining option, record its accepted pair, remove it locally and repeat. Stop wins ties. No selection is revoked by the terminal stop.
- Because this model scores independent pairs and the query stays unchanged, scores can be cached once. Preserve the requested loop and its trace without re-encoding the unchanged remaining options. Changes to pool-conditioned inputs would require new scoring and are outside this model.
- If the initial list is truncated, the stop means no additional match among the evaluated alternatives. Export excluded candidate counts; do not call them proven irrelevant. Prefer all local candidates when the measured cost permits.

## Task ownership, dependencies and verification

1. **Input worker — prepare_pages.py.** Depends on approved sample policy. Freeze selection, read selected rows, join old evidence by exact Source/Text/hash, then recover missing raw revisions iteratively. Preserve attempted dates, API requests, IDs, timestamps, URLs, match method, hashes, section scope and explicit failure reason. Start with one 20-minute evidence check on three selected pages, inside this task's 2h elapsed cap. Stop new recovery requests at the cap, preserve explicit pending/unresolved outcomes and report a revised plan if more work is needed. Do not silently extend the overall window. Test raw markup offsets, damaged text, two revisions per page and unresolved preservation. Deliver pages/mentions/revision manifest. Model-derived stage estimate 1–2h elapsed including the evidence check and external recovery; exhaustive history is not promised.
2. **Collection worker — collect_entities.py.** Depends on selected revision inventory. Reuse local HTML/wikitext, QIDs and metadata, then supported BQ gaps and API fallback. Extract links from the source material actually present, retaining section evidence. Mark API/page failures and unlinked-entity limits. Test exact revision binding, missing QID/P31 and link-scope parity. Deliver entity occurrence and native metadata tables. Estimate 0.5–1.5h elapsed after inventory.
3. **Model worker — prepare_training.py, model.py, train.py.** May start after selected source exclusion inventory is frozen; independent of collection. Build variable-size pools and multiple-positive removal states. Test set-valued loss, source split, stop states, freeze/unfreeze and complete checkpoint restoration. Deliver hash-frozen training inputs, tested code and workload forecast. Estimate 0.75–1.75h local elapsed; root alone starts GPU after local checks.
4. **Matching worker — match.py.** Develop against the table contract in parallel; actual data run follows tasks 1/2 and checkpoint availability. Test strict exact name/type uniqueness, local pair removal, many-to-many links, stop ties, no duplicate selection and cached/repeated-score equivalence. Record ranked candidates and every choice/stop. Estimate 0.5–1h code elapsed plus 5–30min typical GPU inference, workload dependent.
5. **Root — train and integrate.** Exclusive GPU ownership; frozen warmup then full tuning. Benchmark a small batch before committing the remaining compute. Keep frozen/full validation and checkpoints. Candidate-size trials use validation only. Provisional 1.5–3h GPU at the previous workload; hard aggregate new-run GPU ceiling 6h, including setup, tests and inference.
6. **Root + fresh reviewer — report and verify.** Freeze a prediction-independent reference sample spanning the selected pages, or mark unsupported cases unverified. Do not infer complete reverse gold by blindly inverting old single-target labels. Report coverage over all selected data, and accuracy only over verified labels with explicit denominators. Report pair precision/recall, stop precision/recall, early/late stops, exact/model/unresolved counts, type/page breakdown, examples, runtime/cost and outstanding gaps. Verify original bytes/row preservation, output references, stopped VM and all hashes. Estimate 0.5–1.5h elapsed.

Parallel workers own separate files; root owns the shared test file and integration, preventing concurrent edits. Collection, public training preparation and matching development overlap when dependencies permit. Do not launch multiple GPU trainers for speed: quota, budget and one-machine ownership govern execution.

## Cost, time and operation controls

- New authorisation: US$10 total for this pilot; old US$20 approval is not an extra allowance. No paid LLM APIs. Include incremental retained-disk time, IP, network, BQ and GPU setup in the forecast.
- Official g2-standard-4/L4 listed rate freshly read: $0.706832276/hour. Six compute hours ~= $4.24. Reserve at least $2 for disk/IP/transfers; BQ scan allowance <=$0.50 with dry-run byte estimates and maximum_bytes_billed. Plan to stop below $8 forecast total, preserving $2 uncertainty margin. Forecast guards are not a billing-account hard cap.
- Existing VM is stopped. Reuse its installed environment only after duration approval; reset task max runtime for this approved run and verify shutdown controls. Retain old data/checkpoints and use a new output directory. No disk deletion, IAM/API enable, new credentials or repo push.
- Cloud command sequence: (1) syntax validation with `gcloud help <leaf_command>`; (2) parameter verification including supported dry-run/validate-only flags; (3) dry run when supported; (4) execute only within approved project/action scope. One root-owned command at a time; no duplicate uncertain operation.
- Superpowers breakdown and Epoch first coordination agree: optimistic/most likely/pessimistic total elapsed 5/8/12h, excluding approval and unavailable-GPU waits; preflight is included. Model-derived, not pilot-calibrated. Epoch PERT raw expected 8.17h, estimate ID `3e400b0c-a5c0-46d0-9798-6845b4035317`. Do not describe the service's generic confidence interval as calibrated for this pilot.
- Planning began 2026-10-28 23:00:54 Asia/Jerusalem UTC+02. Preflight checkpoint 23:15. If approved near 23:15, finish estimate 2026-10-29 04:15–11:15; next status checkpoint <=10min after execution approval. Recompute clock times at actual approval; do not promise a past timestamp.
- Per-stage JSONL ledger: stage, owner, input/output hashes, UTC start/end, elapsed seconds, measured active_work or unknown, approval_wait, environment_wait, GPU seconds, attempted requests/BQ bytes, estimated cost, failure and adaptation. Do not equate wall time with focused work. Use monotonic timing for process durations.
- Checkpoint every 5–10min, plus shorter user-facing updates during active work. If scope/budget/time ceases to fit, stop starting work, preserve outputs and report the exact blocker; do not increase spend or substitute a model silently.

## Review focus and completion

- Raw markup vs rendered text: templates/ref/table mentions must retain their source scope and correct offsets (task 1/2 tests).
- Native types vs NER types: no exact acceptance from incompatible labels or a guessed type (task 4 test).
- Multiple revisions and many-to-many links: no first-revision shortcut or global candidate removal (task 1/4 tests).
- Stop calibration with larger pools: no training/test leakage, incomplete-label caveat and early/late-stop counts (task 3/6 tests).
- Cloud failure/budget: no duplicate jobs; complete checkpoint and automatic STOP verified (task 3/5 tests).

Completion artifacts: enriched selected-input Parquet; page/revision and QID metadata; exact-pair audit; trigram candidates; model checkpoints; every model selection/stop; matched/unresolved Parquet; prediction-independent evaluation; README/code map; runtime/problem/cost report. Unresolved source passages remain explicit; never invent a matching version to reach 100%.

Backup state: local planning files and ignored input only; no GitHub push approved. Create reviewed local commits at implementation milestones. Report `Local checkpoint only` after a commit, and disclose ignored datasets/checkpoints separately.

## Pending OWNER decisions

1. Approve the 5–12h total elapsed execution window within the already approved US$10 ceiling.
2. For exact name+type acceptance: approve a Wikidata-to-NER mapping, or retain native types and send cases lacking comparable type evidence to the model. Recommended for this first pilot: retain native types, with no guessed automatic exact match.
3. Confirm whether linked QID entities are the requested collection scope, as in the saved graph work. Exhaustive unlinked entity recognition would require an added extraction/linking stage and a revised plan.

## Primary sources

- New input manifest: https://github.com/EtzionR/Corpus2GeoRAG_Pacific/blob/main/Data/georag_selected_v2.run.json
- ZELDA: https://github.com/flairNLP/zelda
- LUKE: https://huggingface.co/studio-ousia/luke-base
- Shared-scorer inspiration (not proprietary JEV reproduction): https://github.com/he-jev/laya/blob/main/rl_common.py
- Compute price: https://cloud.google.com/products/compute/pricing/accelerator-optimized
