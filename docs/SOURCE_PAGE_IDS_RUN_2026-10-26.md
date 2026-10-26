# Source Wikipedia page IDs — 26/10/2026

## Verified result

Processed all **309,864 raw rows** from the original file. The local Parquet copy adds one nullable `int64` column, `wiki_page_id`, for the source English Wikipedia article. All nine original columns, values, duplicate rows, row order, and Arrow schema metadata are unchanged.

- Verified rows: **301,235 (97.2152%)**.
- Unresolved rows, with null page IDs: **8,629**.
- Distinct assigned Wikipedia page IDs: **425**.
- Source labels: 428; distinct `(Source, Text)` pairs: 34,775.
- Independent validation: **PASS**, completed 26/10/2026 20:26:01 Asia/Jerusalem (UTC+02:00).

The output is `D:\Projects\GeoAI-source-page-ids-20261026\Data\external\source_page_ids_20261026\georag_selected_v2_full_n36335_r345732948_20261024_with_wiki_page_id.parquet` (9,716,245 bytes).

## Original source and integrity

[Original GitHub file](https://github.com/EtzionR/Corpus2GeoRAG_Pacific/blob/92edb85ca0e1fc2511579dd18730de58aa591ba1/Data/georag_selected_v2_full_n36335_r345732948_20261024.parquet)

- Pinned commit: `92edb85ca0e1fc2511579dd18730de58aa591ba1`.
- Git blob: `dcf304ad0dd38ca9874f3172609eb0597aa4f285`.
- Original SHA-256: `dcd51dfa237b63378279ced4f9739a45d8cf8ce3991579f20848295448f83f16`.
- Output SHA-256: `0b34290f0f74cc060dad325ca5fe32a9505acfe2ae84cca3dd0768ad2ec48cd1`.

The original file was never written. Both export and independent validation read the saved output and compared the complete original table, including metadata, with the corresponding output columns. Every output ID was reconciled to its `(Source, Text)` decision. Every non-null decision was checked against the saved page ID, revision, title, and complete copied passage. Saved page text was also reconciled with the underlying API response. All 2,134 initial manifest entries passed SHA-256 validation.

## Method and limits

1. Resolve all 428 `Source` labels with the current English Wikipedia API, including server normalization and redirects. A title match alone cannot assign an ID.
2. Require the entire copied `Text` passage in that article's extracted text, exactly or after Unicode NFC and whitespace normalization. Case and punctuation remain significant. When needed, check rendered text for the current revision fetched in this run; remove citation markers and non-content scripts/styles for this comparison.
3. For missing source labels, discover candidates with quoted text from the two longest eligible passages. Also check all 462 remaining distinct texts against cached pages and search every eligible unresolved text. A query uses up to the first 12 words and retrieves up to five article results. Fetch candidate page content and verify the full copied passage, rather than the search snippet.
4. Global attribution requires at least 50 normalized characters and eight words. Reject matches on multiple distinct collected page IDs. Recheck all recovered assignments against the final collected page set.
5. Map each decision back to every corresponding raw row without filtering or deduplication.

This is source-page attribution, not entity identity resolution. A matching passage establishes that the saved article contains the text; it does not prove a unique historical origin. The candidate search is bounded and is not an exhaustive search of all Wikipedia pages. Null does not establish that no matching page exists. Only current English Wikipedia was used; there was no historical revision search. The revision IDs bind rendering to the current snapshots fetched during this run.

Four missing source labels yielded copied-text candidates: `BUROGU` → `Yui Mizuno`; `Conscription in Japan` → `Conscription in Taiwan`; `Gabriel Maurício Teixeira` → `Bombing of Macau (1945)`; `Two Lords Incident` → `Imperial crest of Japan`. Each assigned passage still had to match in full. The raw `Source` values remain unchanged.

| Row status | Rows |
|---|---:|
| VERIFIED_EXACT | 299,907 |
| VERIFIED_NORMALIZED | 491 |
| TEXT_NOT_FOUND | 8,493 |
| VERIFIED_SEARCH_EXACT | 808 |
| INSUFFICIENT_TEXT_FOR_SEARCH | 127 |
| VERIFIED_RENDERED | 22 |
| VERIFIED_SEARCH_RENDERED | 7 |
| AMBIGUOUS_TEXT_MATCH | 9 |

The 8,629 unresolved rows comprise 8,493 without a full match in collected current content, 127 with insufficient text for global attribution, and nine with ambiguous matches. `unresolved_rows.csv` contains every unresolved original row, its zero-based raw row index, source, paragraph index, entity name/type, status, and copied text.

## Unique entity names and types

Identity for this count is the exact raw pair **(`word`, `entity_group`)**. No spelling, whitespace, case, alias, or subtype normalization was applied. These are distinct name–type pairs, not resolved real-world identities.

Total: **74,339**.

| Entity type | Unique name–type pairs |
|---|---:|
| DATE | 8,348 |
| LOC | 14,661 |
| MISC | 14,476 |
| ORG | 16,849 |
| PER | 20,005 |

`unique_entity_counts.csv` also reports raw row counts by type. Subtype is not part of the requested two-field key.

## Evidence and reproducibility

All artifacts are under `Data/external/source_page_ids_20261026/` in the preserved isolated worktree:

- Parquet output, `summary.json`, `source_summary.json`.
- `passage_decisions.jsonl.gz`: all 34,775 source/text decisions and evidence paths.
- `unresolved_rows.csv`, `unique_entity_counts.csv`.
- `requests/`, `pages/`, `candidate_pages/`, `search_candidates/`, `text_search/`: saved responses and attribution evidence.
- `verification.py`, `verification.json`: the independent full-run audit and its result.
- `manifest_export.json`: original export manifest; `manifest.json`: final artifact hashes. The append-only `run.log` and the final manifest itself are excluded from its hash list.

The run recorded 1,071 API requests, zero failed requests, and 572.211 summed seconds of request wall time. Failed calls would be preserved and would not be retried automatically. Official API references: [Query and redirects](https://www.mediawiki.org/wiki/API:Query#Resolving_redirects), [Search](https://www.mediawiki.org/wiki/API:Search).

Implementation: `GG_Data/entity_resolution/attach_source_page_ids.py`; focused tests: `test_attach_source_page_ids.py`. Installed dependencies were reused. Nine focused/regression tests passed, and Ruff passed. The fresh read-only review found an ambiguity-check gap; a failing fixture reproduced it, the final global-candidate check fixed it, and the reviewer reported no remaining material findings. The independent audit additionally passed the complete output and evidence checks after retrieval ended.

## Scope, timing, and protection

User approval covered current English Wikipedia, null unverified IDs, a local output, and 30–60 elapsed minutes. Execution started 26/10/2026 19:51:05 Asia/Jerusalem (UTC+02:00); independent data verification completed at 20:26:01, after 34 minutes 56 seconds. Final reporting and the local checkpoint follow this data milestone. Active work and approval-wait durations were not measured; request wall time is reported separately and is not a measure of active work.

Epoch estimate v1: `10267e18-cf72-42b5-9a04-be148d22704e`, model-derived 30–60 minutes, point 45 minutes; not empirically calibrated. One affected-task replan at about 20:08 used 10–25 minutes remaining, estimate `eacd2e7d-224f-4669-a046-ad3b0855f24f`. The approved upper limit remained 20:50; the final working target was 20:31.

Worktree: `D:/Projects/GeoAI-source-page-ids-20261026`, branch `data/source-page-ids-20261026`, base `269ab29`. Existing changes in `D:/Projects/GeoAI` were not modified. The local-only task excludes integration, remote push, graph changes, and entity matching. The existing `what_happened_at` spatial date-filter issue remains open and was not evaluated here.

Protection: code and this report receive a **Local checkpoint only**. The ignored Parquet and evidence artifacts are **Unprotected** local files; remote/cloud backup was not performed or verified. The worktree and all artifacts remain in place.
