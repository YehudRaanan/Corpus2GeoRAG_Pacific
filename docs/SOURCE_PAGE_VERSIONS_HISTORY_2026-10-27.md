# Incremental Wikipedia revision recovery — 27 October 2026

V3 is complete for the approved bounded search. It contains source-page and matching-revision metadata for **309,319 of 309,864 rows (99.824116%)**. This continuation added **5,377 rows / 356 Source/Text pairs**. **545 rows / 58 pairs / 25 source labels remain unresolved**, with explicit statuses and null page/revision metadata.

Only V2's **414 unresolved Source/Text pairs / 5,922 raw rows** were searched. No entity extraction or previously accepted passage matching was repeated. All **303,942 accepted V2 rows**, including every metadata field, remain identical. Full-row reads/copies were used only for export, aggregate counts, and integrity comparisons.

## Local files

| Version | Page IDs | Complete revision metadata | File |
|---|---:|---:|---|
| V1: saved historical pilot recovery only | 303,942 | 2,707 | [V1 Parquet](../Data/external/source_page_versions_staged_20261027/georag_selected_v2_full_n36335_r345732948_20261024_v1_historical_recovery.parquet) |
| V2: saved baseline metadata added | 303,942 | 303,942 | [V2 Parquet](../Data/external/source_page_versions_staged_20261027/georag_selected_v2_full_n36335_r345732948_20261024_v2_revision_metadata.parquet) |
| V3: remaining historical search | 309,319 | 309,319 | [V3 Parquet](../Data/external/source_page_versions_history_20261027/georag_selected_v2_full_n36335_r345732948_20261024_v3_historical_continuation.parquet) |

All three files contain all 309,864 original rows. V1 and V2 were not overwritten. V3 is 11,046,980 bytes and has the same 19-column schema as V2.

The output directory contains [README](../Data/external/source_page_versions_history_20261027/README.md), [summary](../Data/external/source_page_versions_history_20261027/summary.json), [verification](../Data/external/source_page_versions_history_20261027/verification.json), [unresolved rows](../Data/external/source_page_versions_history_20261027/unresolved_rows.csv), [remaining diagnostics](../Data/external/source_page_versions_history_20261027/remaining_diagnostics.json), [statistics](../Data/external/source_page_versions_history_20261027/additional_statistics.json), and [manifest](../Data/external/source_page_versions_history_20261027/manifest.json). Raw row indices in sidecars are zero-based.

## Revision meaning

`wiki_page_id` identifies the source article containing the copied `Text`. Each accepted row has canonical title, revision ID, UTC revision timestamp, permanent oldid URL, match method, status, saved evidence references, copied-text SHA-256, and the unchanged baseline status.

There are **425 source articles and 571 accepted revision IDs**. **124 articles have multiple matched revisions** across passages. Revision metadata is per row/passage; no common article-wide revision was imposed. Previously accepted versions were retained.

Each new acceptance requires the **complete copied passage** in saved rendered text after NFC/whitespace normalization only, plus page/revision/namespace/timestamp identity checks. The selected version is the newest matching revision among those checked for that passage. A matching revision does not establish the original extraction revision or extraction date. Oldid rendering uses templates available at retrieval time; saved HTML and wikitext preserve the evidence used.

## Search and results

Collection traversed eight initial dates and sixteen refinement dates from January 2018 through October 2026. Contexts with no eligible pending passages were skipped. Previously saved baseline, pilot, and staged evidence was reused. No failed request was automatically retried.

- 876 dated article checks; 1,590 new saved API responses; zero request/evidence failures.
- 93,796,529 bytes of new compressed request evidence.
- Collection/export ended 27/10/2026 23:30:46 Asia/Jerusalem UTC+02.
- Retrieval elapsed 3,382.812 seconds; summed new HTTP request time 2,936.272 seconds.
- The 2,200-call, 120-minute, and 3-GiB ceilings were not reached. All approved sample dates were traversed.
- The 356 new accepted pairs use 144 matching revisions, dated 30/12/2024 through 24/10/2026 UTC.

Rows grouped by the date used to query their final selected revision: 24/10/2026:407; 01/10/2026:1,356; 01/09/2026:652; 01/08/2026:34; 01/07/2026:2,923; 01/01/2025:5. Query dates are sampling bounds; the actual revision timestamps are stored in the Parquet.

Final row statuses:

| Status | Rows |
|---|---:|
| VERIFIED_BASELINE_SAVED_EVIDENCE | 301,235 |
| VERIFIED_HISTORICAL_SAVED_EVIDENCE | 2,707 |
| VERIFIED_HISTORICAL_NEW_EVIDENCE | 5,377 |
| UNRESOLVED_NO_FULL_MATCH_IN_CHECKED_REVISIONS | 476 |
| INSUFFICIENT_TEXT_FOR_GLOBAL_RECOVERY | 69 |
| Total | 309,864 |

The 476 unresolved rows lack a complete match in the sampled rendered revisions. This is not proof that the text never appeared on Wikipedia. The 69 short-text rows use alternate-source candidates and do not meet the established minimum of 50 normalized characters and eight words. Their page/revision values remain null.

Earlier comparisons of the remaining rows suggest 283 near-wording/extraction cases, 119 punctuation/case/word-boundary cases, 74 partial passages, and 69 short-text cases. These are diagnostic leads, not proven causes. The largest remaining source groups are Indonesian National Revolution:51, Tōseiha:49, Oceania:47, Boeing B-29 Superfortress:44, and BUROGU:43. No Roosevelt alias remains in the unresolved set.

## Verification

The full new-match audit passed. It checked all 356 new pairs against saved complete-text and revision metadata evidence, then reconciled each of the 5,377 new rows to the correct original row indices. No earlier accepted passage was rematched.

Preservation checks passed for all original values, row order, raw schema metadata, every accepted V2 row, copied-text hashes, baseline statuses, metadata types/null rules, and the complete unresolved CSV. All baseline (2,138), pilot (38), and staged (17) manifest entries passed again. A fresh SHA-256 check of the original downloaded Parquet also matched.

An independent read-only review found no material issue. It separately compared all raw and accepted rows, new assignments, metadata/evidence references, pending and unresolved indices, and eight saved parse/revision evidence samples. Fifteen focused/regression tests passed. Ruff, Black, isort, and Git whitespace checks passed for the new code. Entity-type serialization in the audit report uses a deterministic key order; its values were checked unchanged.

Unique `(word, entity_group)` counts remain unchanged:

| Type | Unique name/type pairs |
|---|---:|
| DATE | 8,348 |
| LOC | 14,661 |
| MISC | 14,476 |
| ORG | 16,849 |
| PER | 20,005 |
| Total | 74,339 |

## Hashes and reproduction

| File | SHA-256 |
|---|---|
| Original downloaded Parquet | `dcd51dfa237b63378279ced4f9739a45d8cf8ce3991579f20848295448f83f16` |
| Original attribution baseline | `0b34290f0f74cc060dad325ca5fe32a9505acfe2ae84cca3dd0768ad2ec48cd1` |
| V1 | `4052c27dabfb53530a4a861a4319a915da5e43d6f2bc84cf3312856b80e28f30` |
| V2 | `d511db45ae67f257ceb03fd87143b3d45f944d6085b15e438a06ed9b0ad2e20a` |
| V3 | `5378e8124979f04be6eca62a62a7f104fb2fdb88d5c0ba378ebf8d3db86f5bb7` |

Collector: [recover_wiki_history.py](../GG_Data/entity_resolution/recover_wiki_history.py). Audit: [verify_wiki_history.py](../GG_Data/entity_resolution/verify_wiki_history.py). Tests: [test_recover_wiki_history.py](../GG_Data/entity_resolution/test_recover_wiki_history.py).

Run the audit from the isolated project root with `python GG_Data/entity_resolution/verify_wiki_history.py --root Data/external`. It updates `verification.json`. The collector refuses an existing output/progress state; do not start it again on this completed directory. Evidence references contain absolute local paths, so retain those paths or translate references when relocating the data.

## Scope, timing, and protection

OWNER approved this 60–150 elapsed-minute continuation. Start:27/10/2026 22:29:30 Asia/Jerusalem UTC+02. Epoch estimate:`a5dc98a4-0388-4d62-927e-fe524192d542`; model-derived, not calibrated P80. Final elapsed measurement and checkpoint are recorded in the [execution plan](superpowers/plans/2026-10-27-full-wiki-revision-metadata.md). Focused active work, approval wait before this phase, and total environment wait were not separately measured; HTTP durations above are measured and are not a substitute for focused effort.

Code/docs: **Local checkpoint only**. Ignored Parquet/evidence files: **Unprotected** on GitHub. No push, paid model/cloud run, installation, graph/identity changes, deletion, or extraction rerun was performed. Any further search would be a new bounded phase; this report does not claim exhaustive historical absence or complete metadata for the 545 unverified rows.
