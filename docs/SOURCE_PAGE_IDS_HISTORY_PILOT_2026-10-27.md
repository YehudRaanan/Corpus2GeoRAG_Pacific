# Historical Wikipedia source-page pilot — 27/10/2026

Older article revisions verify **2,707 of 3,584 previously unresolved raw rows (75.53%)** in this two-article pilot. These are **107 Source/Text pairs and 71 distinct text strings**. Every accepted match requires the complete copied passage in rendered revision text, with only NFC and whitespace normalization. No punctuation removal, case folding, fuzzy acceptance, or ID update was applied.

| Source label | Matched pairs | Matched raw rows |
|---|---:|---:|
| Franklin D. Roosevelt | 18 | 469 |
| Franklin Delano Roosevelt | 18 | 469 |
| Franklin Roosevelt | 18 | 469 |
| Oceania | 53 | 1,300 |
| Total | 107 | 2,707 |

Roosevelt aliases preserve separate input rows; they do not represent three different Wikipedia articles. This denominator includes all 158 unresolved Source/Text pairs and 3,584 raw rows for these labels, not only the two illustrative paragraphs. The remaining 877 rows did not match the sampled revisions. This does not prove absence from all historical versions. Relative to the complete baseline's 8,629 unresolved rows, the pilot provides matches for 31.37%; the rest of the corpus was not searched.

## Verified examples

- The complete 201-word Roosevelt passage containing `The Roosevelt administration` occurs in [revision 1361441288](https://en.wikipedia.org/w/index.php?oldid=1361441288), timestamp **27/06/2026 22:55:02 UTC**. The saved October snapshot instead contains `Roosevelt's cabinet`. The passage accounts for 40 raw rows per alias, 120 total. The older revision's saved raw wikitext also contains the original phrase.
- The complete 409-word Oceania passage containing `regional organization` and `categorized` occurs in [revision 1360646982](https://en.wikipedia.org/w/index.php?oldid=1360646982), timestamp **22/06/2026 19:26:31 UTC**, and [revision 1329489223](https://en.wikipedia.org/w/index.php?oldid=1329489223), timestamp **26/12/2025 09:29:47 UTC**. It accounts for 80 raw rows. The raw wikitext preserves `regional organization`.

These examples show that Wikipedia revision differences can explain the current-page failures. They do not identify the original extraction revision or extraction date. Several revisions can contain the same passage. Old-revision rendering is produced by the API now; it is not a saved historical screenshot or a guarantee of historical template state.

## Bounds and provenance

Checked **16 distinct revisions: eight per article**. At each target date, requested the latest revision at or before 23:59:59 UTC: 24/10/2026, 01/07/2026, 01/01/2026, 01/07/2025, 01/01/2025, 01/07/2024, 01/01/2024, 01/01/2023. The last target can select a December 2022 revision. Dates are sampling choices; the Parquet filename is not treated as an extraction timestamp. No intervening revisions were enumerated or searched.

Used the official [revision query API](https://www.mediawiki.org/wiki/API:Revisions) and [oldid parsing API](https://www.mediawiki.org/wiki/API:Parsing_wikitext). All 32 requests succeeded. Summed request time was 108.595 seconds; the bounded retrieval/matching process took 130.890 seconds. No failed-call retries or dependency installs occurred.

Saved evidence directory: `Data/external/source_page_ids_history_pilot_20261027/`.

- `requests/*.json.gz`: request parameters, retrieval time, HTTP result, complete metadata and parsed HTML/wikitext response.
- `results.json`: all 16 revision identities, timestamps, permanent URLs and accepted full passages.
- `matched_raw_rows.csv`: all 2,707 zero-based original raw row indices with page/revision evidence.
- `pilot.py`, `verify.py`: reproducible collection and separate reconciliation.
- `verification.json`: verified denominators, example revisions and preservation checks.
- `manifest.json`: hashes for this pilot's files, excluding the manifest itself.

Verification reconciles complete matches to original raw row counts, checks each accepted row was null in the baseline, checks page/revision identities against both API responses, and confirms accepted passages fail the same full-text rule on saved current snapshots. Both article IDs remain distinct; independent review found no material issues and confirmed all 16 snapshots and the 2,707-row union.

The original input hash and all **2,138** baseline manifest files are unchanged. The existing enriched Parquet retains SHA-256 `0b34290f0f74cc060dad325ca5fe32a9505acfe2ae84cca3dd0768ad2ec48cd1`. No new Parquet was produced and no IDs were filled. This pilot supports a separate historical recovery pass with explicit revision provenance; it does not establish a complete recovery rate for other articles.

## Task record

Scope: authorized two-article historical pilot, owned by root in the existing isolated worktree. Exclusions: baseline mutation, full-corpus historical run, graph or identity changes, installation, remote push and cleanup. The `what_happened_at` issue remains open and was not evaluated.

Estimate v1: model-derived 10–18 elapsed minutes, Epoch reference `9408820b-dccb-40d7-9091-2d033184bdbc`; not an empirically calibrated interval. First clock record: 27/10/2026 08:13:25 Asia/Jerusalem UTC+02. A later user continuation and clock check occurred after a substantial interruption: the next checked clock was 09:12:17. The earlier 08:23 checkpoint had passed, reported at that boundary; checkpoints were revised to 09:16 and 09:18. Active work, user/interruption wait, and environment wait were not separately measured; wall-clock elapsed must not be reported as focused effort. The API process duration above is independently measured. No long operation remains pending at handoff.

Protection: report and plan **Local checkpoint only**. Ignored pilot evidence and scripts **Unprotected** local files. No off-device backup was made or verified.
