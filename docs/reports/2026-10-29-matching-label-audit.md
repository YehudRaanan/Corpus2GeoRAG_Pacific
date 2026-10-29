# Matching and label audit — 29 October 2026

The saved results support a bounded public-label diagnostic and a three-page matching inspection. They do not establish complete identity precision, complete negative truth, or native-corpus stop accuracy. No model, threshold, source label, reference pair, or saved pipeline output was changed for this audit.

## Scope and evidence

Worktree: `D:\Projects\GeoAI-luke-pilot-20261028`.

Artifact root: `Data/external/hundred_page_pilot_20261028/`.

Authoritative new audit outputs:

- `audit_20261029/results_final/unresolved_mentions.csv`: one row per unresolved original mention, with page/revision, candidate exposure, score margins, source-link support, and explicit unknown identity status.
- `audit_20261029/results_final/summary.json`: counts and SHA-256 hashes for all 142 data files read by the reproducible audit; each hash was checked again before completion.
- `audit_20261029/audit.py`: standard-library-only audit of saved files. It does not load model weights or use a network service. Use `--output NEW_DIRECTORY` to reproduce it without replacing outputs.
- `audit_20261029/verification.json`: hashes for the cached public archive and the final mention/link files; confirms archive identity, unchanged mention/link content, final type counts, and observed mention/QID multiplicity.

The ignored `results/` and `results_verified/` folders are retained intermediate audit outputs. Use `results_final/` only. The first intermediate summary had a supported-group counting error caused by inserting missing dictionary keys; the final audit reports the independently checked 4,283 supported groups.

These audit artifacts are ignored by Git and are local only. The report is included in the local code checkpoint. The audit script and CSV remain ignored local artifacts.

## Findings, ordered by consequence

### 1. Exact source links are not independent identity gold

`GG_Data/entity_resolution/hundred_page_pilot/report.py:24–68` requires a unique exact passage placement and a complete direct Wikipedia link anchor. Every one of the 4,301 reference rows passed a fresh raw-span/name check. Every referenced mapping evidence path exists. This checks evidence preservation, not the semantic correctness of the entity assignment.

The source itself demonstrates why that distinction matters:

| Reference JSONL line | Literal and Daniel type | Saved source link | Consequence |
|---|---|---|---|
| 1392 | Iceland, LOC | `[[Invasion of Iceland|Iceland]]` → Q65088915 | An event link destination is not independent proof of a location identity. Line 1391 separately links Iceland to Q189. |
| 76–77 | Taytay, LOC | Municipality Q111730 and Apostolic Vicariate Q620439 | The same name/type group contains different source meanings. |
| 2834–2835 | 1939, DATE | Football All-America team Q16949071 and All-Big-Ten team Q19863574 | A date-shaped anchor can link to an organization or team article. |

Reference file: `source_link_reference_v2.jsonl`. The reference has 4,301 positive pairs for 4,283 of 24,408 Daniel groups across 100 pages. It contains no complete negative labels. `report.py:76–89` correctly leaves precision and stop precision unset. The audit does not declare all reference pairs wrong, nor does it change them.

### 2. Group-level evidence cannot verify each occurrence

`hundred_page_pilot/prepare_candidates.py:28–60` groups by page, revision, literal string, and Daniel type. It retains all source rows but uses only the first three distinct contexts. `hundred_page_pilot/report.py:211–220` applies each accepted group QID to all original rows in that group.

The reference contains 18 groups with two QIDs. These groups contain 142 original rows. For example, Taytay has 13 rows and 12 contexts; Iceland has five rows and five contexts. This is evidence of a granularity limit. A group can support “at least one occurrence refers to this entity”; it cannot prove that every occurrence has that identity.

The audit CSV distinguishes reference support for a group from evidence on the exact source row. This distinction matters for Southern Force below.

### 3. Public annotations have a different label contract

`decision_model/prepare_training.py:71–109` uses public annotated spans, merges identical literal strings, and assigns positives from public target titles. It does not supply native Daniel types. Candidate pools contain public annotated groups, rather than every native mention. Lines 112–165 remove labelled positives and add singleton-positive states. A synthetic stop therefore means “no labelled positive remains.” It does not prove that every remaining option is semantically negative.

Concrete training examples:

- `training_k80_v2/train.jsonl:4171`: the query Human intelligence treats literal “human intelligence” as negative in a context about the distribution of intelligence across human populations. The cached public source annotation targets Intelligence. This is a strong potential false negative for semantic identity; target equivalence was not independently established.
- Lines 1133 and 1139: the same Dune literal group is positive for the 1984 and 2021 films, with both contexts merged.
- Lines 1619, 1623, and 1625: the same income literal group is positive for Income, Income distribution, and Income inequality metrics.

Three multiple-target literal groups were found among retained training questions, and none among retained validation/test questions. These examples do not directly explain the held-out errors. A check of the cached source annotations found no retained positive target absent from the first three public contexts. Name equality alone is not a safe repair: a validation Anna Karenina film mention is correctly negative for the novel query.

### 4. The public test is bounded and its individual errors are not saved

`training_k80_v2/public_test.jsonl` has 296 initial questions from 33 held-out source pages, expanded into 608 related removal/singleton states. The pages are held out from the sampled ZELDA training archive; this is not the official benchmark test. Selected native source IDs/titles and detectable copied passages were excluded before public state construction. No claim is made that pretrained-model exposure was excluded.

Saved `train_20261029/final_public_test_metrics.json`:

| Measure | Saved result | Interpretation |
|---|---:|---|
| Correct state choices | 551/608 = 90.625% | Choice agrees with remaining public labels. States from one question are related. |
| Stop precision | 278/311 = 89.389% | Agreement with synthetic public stop labels. |
| Early / late stops | 33 / 18 | Defined relative to those public labels. |
| Complete labelled pair sets | 245/296 = 82.770% | Entire recovered set equals the labelled set for the initial pool. |
| Label-false / missed within-pool pairs | 20 / 36 | Unlabelled predictions are not independently proven false identities. |
| Retrieval-excluded labelled positives | 0 | Retrieval expansion cannot recover additional labelled positives in this test. |

`decision_model/train.py:398–463` computes these measures and preserves the annotation-incompleteness caveat. There are 57 incorrect state choices in aggregate; 51 are early/late stop states. No per-state predictions or logits are present in the inspected local `train_20261029/` artifact inventory. Thus, listing or semantically auditing those 57 individual errors is blocked by missing saved predictions. Obtaining them would require an additional approved scoring run or an available saved prediction artifact; neither was performed here.

## All unresolved mentions in the saved three-page run

Inputs: `post_qid_20261029/core_3/`, `jobs_3.jsonl`, and `post_qid_3_20261029/{scores,decisions,model_pairs}.jsonl`.

All 535 original mention rows are preserved. Of these, 369 have no QID link. They produce 246 provisional entity rows, because repeated mentions can share an identity group. This is not evidence that source rows were lost.

| Exposure to saved QID questions | Original unresolved mentions |
|---|---:|
| In no candidate pool | 37 |
| In some pools on the same page and revision | 122 |
| In all pools on the same page and revision | 210 |
| Total | 369 |

The denominator is QID jobs for the mention's exact `(page_id, revision_id)`, not all jobs from every revision of its page. Page 781032 has two used revisions, each with 45 jobs. The other scopes have 45 and 22 jobs. Every one of the 332 exposed unresolved mentions has saved candidate scores at or below stop in all exposed questions. Stop wins score ties.

Types: DATE 90, MISC 131, LOC 51, ORG 49, PER 48.

Candidate exposure does not establish that the correct identity was present. Conversely, no exposure does not prove that the correct identity was absent from the source inventory. The CSV marks actual correct-identity presence and absence unknown for every unresolved mention because no complete identity gold exists.

Four original unresolved rows have group-level reference support and were exposed to the reference QID:

| Original row | Mention | Reference QID | Reference candidate score minus stop | Evidence limit |
|---|---|---|---:|---|
| 312944 | Pacific Theater | Q184425 | -1.875 | Exact anchor `[[Pacific War|Pacific Theater]]`; source-link support. |
| 313018 | Bombardment of Orleans | Q543110 | -5.5 | Exact direct source link. |
| 1470392 | Southern Force | Q308999 | -10.0 | Group support comes from another source row. |
| 1470498 | Southern Force | Q308999 | -10.0 | Exact link anchor, but saved query identity is Battle of Leyte Gulf. This is not independent force-identity gold. |

The two Southern Force rows share a group and its score. The direct reference evidence is on row 1470498 (`source_link_reference_v2.jsonl:400`), not row 1470392. These four rows are useful audit leads; they are not four proven model identity errors.

## Entity and relation count reconciliation

| Saved table | Entity rows | Typed QID rows | Distinct QIDs | Provisional rows |
|---|---:|---:|---:|---:|
| `post_qid_20261029/core_3/entities.json.gz` | 306 | 60 | 54 | 246 |
| `post_qid_20261029/tables_3_article_scope_before_geography/entities.json.gz` | 317 | 71 | 56 | 246 |

The filtered event stage adds 11 event rows. Nine event QIDs already occur in the core; two are new to the core: Q217145 and Q263142. Entity/type rows and distinct QIDs are different denominators. The unfiltered `tables_3_before_geography/` table has a broader population and is not the 317-row final article-scope table. The unused `tables_3_article_scope/` folder was not populated.

Final entity rows by type, including provisional rows: DATE 63, LOC 50, MISC 92, ORG 58, PER 43, and `event` 11. These sum to 317; they are not counts of distinct QIDs.

The saved core links contain 165 mentions with one QID and one mention with two QIDs. One observed two-QID mention is a result of this run, not a system limit. The list-based group/link representation supports many-to-many assignments without a two-QID cap; this audit does not impose a cardinality cap or establish that each observed assignment is correct.

`events_relations_3_article_scope/relations.json.gz` contains 120 base assertion IDs and 239 direction rows: 119 base assertions have a forward and reverse row; one has a single self row, Q928 → Q928 with source predicate `wd:P17`. There are 120 FORWARD and 119 REVERSE rows. This reconciles the count; it does not establish that the source self relation is semantically correct. No assertion was removed or modified.

## Recommended next experiments, in priority order

1. Establish a small, independently checked identity/stop reference with complete eligible candidates, explicit negative labels, type rules, occurrence-versus-group rules, and separate source-link evidence. Start with the demonstrated source/identity conflicts and reference-supported unresolved cases. Do not automatically relabel them.
2. Save per-state and per-pair predictions for future diagnostics. Audit the actual public errors before choosing a loss, stop rule, model, or threshold change. Existing aggregate metrics cannot identify their semantic causes.
3. Test training examples closer to the native input: Daniel types, raw-context format, unlinked mention groups, and ambiguous repeated names. Compare on fixed complete identity labels. The current public/native differences make this plausible, not proven.
4. Test occurrence-level scoring or a stated “any occurrence” group contract before assigning all group QIDs to each original row. Preserve original rows and evidence throughout.

Candidate expansion is a lower priority for the current public diagnostic because all labelled positives survived retrieval. Native candidate coverage remains a separate question: the CSV measures exposure only. No improvement, label correction, or production promotion is claimed without a new controlled experiment.

## Reproduction and limits

From the worktree, run:

```powershell
python Data/external/hundred_page_pilot_20261028/audit_20261029/audit.py --output Data/external/hundred_page_pilot_20261028/audit_20261029/NEW_RESULTS
```

The output path must not exist. The script checks the counts, verifies raw reference spans, hashes all data files it reads, checks those hashes again, and records its own SHA-256. The final CSV contains 369 data rows. It uses only saved JSON/JSONL/gzip/text evidence and the Python standard library. Mapping evidence paths were checked for existence; their mapping contents were not independently revalidated. The public archive title examples above were inspected directly in the cached archive. A separate full-file SHA-256 check matched the frozen archive hash; that check and the final mention/link checks are recorded in `verification.json`.

No network request, paid query, training, inference, threshold change, reference edit, source-data write, or saved pipeline-output replacement was performed for this audit. Geography remains outside this matching audit; the separate open `what_happened_at` spatial date-filter issue remains open.
