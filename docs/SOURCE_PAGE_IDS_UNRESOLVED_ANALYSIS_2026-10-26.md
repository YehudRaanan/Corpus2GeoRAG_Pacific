# Why source-page IDs remain unresolved — 26/10/2026

Most null IDs do **not** mean that the page lacks the information. The first pass required the **entire copied passage** to match exactly, apart from NFC and whitespace normalization. A one-word edit, a different dash, or a changed word boundary could reject a long paragraph. Every entity row linked to that paragraph then received a null ID.

The status `TEXT_NOT_FOUND` was too broad: it means **no full passage match under that rule**, not that the text or topic is absent from Wikipedia.

## Complete denominator

Analysed all **8,629 null-ID rows**, representing **521 distinct `(Source, Text)` pairs**, **449 distinct text strings**, and **137 source labels**. All earlier Parquet and evidence files were preserved. No IDs or matching rules were changed.

| Diagnostic result | Raw rows | Source/text pairs |
|---|---:|---:|
| Close passage match, at least 90% token similarity | 5,304 | 263 |
| Same continuous letters/digits after punctuation, case, and whitespace removal | 1,220 | 72 |
| Partial passage overlap on the expected/candidate page | 1,807 | 110 |
| No substantial overlap found by this diagnostic | 162 | 21 |
| Short text blocked by the attribution policy | 127 | 54 |
| Full text matches multiple collected pages | 9 | 1 |
| **Total** | **8,629** | **521** |

The close-match and punctuation/case/spacing groups account for **6,524 rows (75.61% of unresolved rows)**. These counts are diagnostic evidence, not newly accepted source assignments. Another 1,807 rows have an exact sequence of at least eight words within the contextual page, but a weaker complete-passage alignment.

## Verified examples

| Source | Raw Parquet wording | Saved page wording | Effect |
|---|---|---|---|
| Franklin D. Roosevelt | `The Roosevelt administration` | `Roosevelt's cabinet` | The rest of this 201-word passage matches; one phrase caused 40 entity rows per source alias to remain null. |
| Oceania | `organization`, `categorized` | `organisation`, `categorised` | Spelling and punctuation differences reject the full passage; this example affects 80 rows. |
| Remilitarisation of the Rhineland | `Italian Army` | `Royal Italian Army` | One added word in a 286-word passage affects 56 rows. |
| Boeing B-29 Superfortress | `WWII.` | `the war.` | A small wording difference affects 44 rows. |
| 58th Operations Group | `F-16 A/B` | `F-16A/B` | Word spacing affects 13 rows. Collapsing existing whitespace does not remove this boundary difference. |

The Roosevelt and Oceania examples were also checked against the live public pages: [Franklin D. Roosevelt, Pearl Harbor section](https://en.wikipedia.org/wiki/Franklin_D._Roosevelt#Pearl_Harbor_and_declarations_of_war), [Oceania, definitions](https://en.wikipedia.org/wiki/Oceania#Definition). The saved revision evidence remains the basis for the full diagnostic counts.

These examples demonstrate a text difference. They do **not** establish whether Wikipedia changed after extraction or whether the upstream extraction/export changed the wording. The original nine-column Parquet has no source revision ID, revision timestamp, or source revision URL. No historical revisions were searched, so the timing and origin of these differences remain unverified. A filename date is not proof of an extraction revision.

## Formatting and policy details

The 1,220 punctuation/case/spacing rows divide into:

- 93: whitespace/word-boundary differences only.
- 188: case differences only.
- 116: standard typographic punctuation and/or whitespace boundaries.
- 823: other punctuation/case differences under the broader letters/digits comparison.

Removing punctuation can erase meaningful distinctions. It was used only to explain why the strict comparison failed, and did not populate an ID.

Of the 127 short-policy rows, **69 already match a recovered candidate page in full**. They remained null because the original source label did not resolve and the individual short passage did not meet the global attribution threshold: 50 normalized characters and eight words. A source-context propagation rule could treat these differently, but no such rule was applied here. The remaining 58 short-policy rows do not have a full match in their checked source/candidate context.

The nine ambiguous rows all come from one book citation under `Tōseiha`. Its full text occurs on three distinct collected articles: `Gunbatsu` (2912039), `Shūmei Ōkawa` (3650982), and `Kanji Ishiwara` (340377). A reused bibliography entry cannot independently identify the extraction page.

The remaining 162 rows are **not confirmed deleted text**. They include bibliography entries, table/list material, and sentences for which this contextual comparison found no run of eight identical whitespace-separated words. A different page, altered rendering, a rewritten passage, or upstream text changes remain possible. The diagnostic search is not exhaustive and does not establish absence from Wikipedia.

## Why the raw count is large

There are three source labels for Roosevelt: `Franklin D. Roosevelt`, `Franklin Delano Roosevelt`, and `Franklin Roosevelt`. Each contains the same **739 unresolved entity records across 33 passages**, after excluding the source label and raw row index. This was verified by complete record comparison.

Together these aliases contribute **2,217 rows, or 25.69% of all unresolved rows**. These are repeated inputs preserved from the raw file, not 2,217 independent missing paragraphs. Rows were not deduplicated because the task required preserving all raw rows.

## Diagnostic method and verification

The audit reused saved API responses and page snapshots. It checked the page resolved from `Source`; for the four missing source labels, it also checked the candidates previously discovered from that source's long copied passages. It did not run a new fuzzy search across all Wikipedia pages.

The close-match diagnostic uses the Python standard library `difflib`. It finds the longest exact word sequence on a contextual page, aligns a bounded surrounding window, trims unmatched outer context, and calculates token sequence similarity as `2 * matching_tokens / (query_tokens + reference_tokens)`. Close-match classification requires similarity at least 0.90 and a longest exact sequence of at least eight words. Scores are **not probabilities or calibrated confidence**. Exact-case whitespace-separated token comparisons can also be affected by punctuation and inline-text extraction. Diagnostic categories describe observed overlap, not a proven historical cause or a final identity decision.

Four small checks verified the comparison functions, including an exact passage, an inserted word, unrelated text, and a punctuation/case/spacing example. All 521 pairs and 8,629 rows reconcile with the baseline. All **2,138** files in the previous run manifest still match their recorded hashes.

The enriched Parquet SHA-256 remains `0b34290f0f74cc060dad325ca5fe32a9505acfe2ae84cca3dd0768ad2ec48cd1`.

Detailed artifacts: `Data/external/source_page_ids_unresolved_analysis_20261026/` contains `analyse.py`, `diagnostics.json`, `diagnostics.csv`, `summary.json`, `additional_checks.json`, and `verification.json`. The JSON records reference page evidence, aligned token positions, edit spans, and similarity measures; the CSV provides all 521 raw source/text pairs and row counts. These diagnostic outputs do not alter the original attribution manifest.

## Implication

The strict full-passage rule explains most nulls. A separate second-pass policy could verify the article using source context and multiple unchanged anchors, then check the local text around each entity and retain explicit evidence for differences. That policy would require its own verification before any IDs were changed. To distinguish later Wikipedia edits from upstream export changes, obtain the extraction revision IDs or conduct an explicitly scoped historical comparison.

## Task record and protection

Root agent owned this analysis. Dependencies: the completed local attribution run and its immutable evidence. No other writer used these analysis files; no process remains pending at handoff. Scope excludes ID changes, historical revision search, graph changes, remote push, and dependency installation.

Started 26/10/2026 at 22:21:47 Asia/Jerusalem (UTC+02:00). Model-derived estimate: 8–18 elapsed minutes, point approximately 12 minutes; Epoch feedback reference `7358dfc5-a1e2-4ef9-b5dd-dd72bba1664c`. Basis: all 521 unresolved pairs, local cached comparisons, and a small live example check. This is not an empirically calibrated range. First checkpoint was 22:31; final elapsed actual is recorded in Epoch at handoff. Active work, approval wait, and environment wait were not separately measured.

Protection: this report receives a **Local checkpoint only**. The ignored analysis artifacts remain **Unprotected** local files. No remote backup was performed or verified. The existing `what_happened_at` issue remains open and was not evaluated by this analysis.
