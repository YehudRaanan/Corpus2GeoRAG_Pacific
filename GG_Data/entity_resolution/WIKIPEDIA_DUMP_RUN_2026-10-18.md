# English/Japanese Wikipedia dump import — 18 October 2026

Current checkpoint: restarted on **19 October 2026, 08:59 Israel time** after
fixing a source-page selection error. All six metadata tables are imported.
Matching has not started; no final matching results exist. The continuation
prepares page links and then runs all **309,864 original Daniel mentions /
428 source titles** without another confirmation.

## Source-page selection fix — 19 October 2026

The source query returned **424 resolved source titles and four missing titles**.
These correspond to **413 distinct Wikidata QIDs**; multiple titles can resolve
to the same page. The coordinator then stopped with `No source-page identities
found`: the BigQuery CLI returned `is_redirect` as the string `"false"`, which
Python incorrectly treated as true. All three page-selection sites now share
an explicit check accepting native false or CLI `"false"`, while excluding
redirects and missing pages. Daniel's input and matching rules are unchanged.

The fix passed **23 targeted tests**, Ruff, and replay of the actual 428-row
cached query, retaining all 424 canonical-page records. Imported row counts:
English pages 19,315,587; redirects 12,457,004; page properties 10,355,689;
Japanese pages 2,477,261; redirects 954,569; page properties 1,877,400.

The restarted coordinator is PID **29560**. Logs use the dump cache path plus
`.boolean_fix_20261019.stdout.log` / `.boolean_fix_20261019.stderr.log`.
The stopped attempt is preserved in
`failure_20261019_before_cli_boolean_fix.json`. Saved downloads, converted files,
imports and query results are reused. Check live progress before treating this
launch checkpoint as current. Code backup: **Local checkpoint only**; large
local cache files remain unprotected off-device.

## Parallel preparation — 19 October 2026

The user approved two preparation workers. English and Japanese metadata
conversion now runs in separate processes. Once source page IDs are resolved,
their link conversion also runs in two processes. Within each language,
pagelinks finish before linktarget selection starts. The coordinator alone
submits BigQuery jobs and writes shared evidence. Matching waits for the full
page snapshot, then keeps the agreed three-pass order and the 80% rule.

Before switching, English page properties completed: **10,355,689 QID rows /
46,114,565 scanned property rows**. Four tables are imported. The earlier worker
was stopped during local Japanese page conversion, with no active BigQuery
child job. Its unfinished conversion restarts; completed files and imports are
reused. No new downloads or changes to candidate rules are required.

Current coordinator PID and logs are in `process_id.txt` and
`C:\Users\User\.cache\geoai_wikipedia_dump_20261018.parallel_20261019.stdout.log`
and `.parallel_20261019.stderr.log`. Each language writes its own
`progress_en.json` / `progress_ja.json` in the dump cache, including worker PID,
stage, and table. The coordinator's `progress.json` remains separate.

Eighteen targeted tests and Ruff passed. The added real-process check verifies
both languages, selected source-page links, target namespaces, missing targets,
and separate worker progress files. No final matching counts are available.

## Recovery checkpoint — 19 October 2026

All ten downloads completed and passed checksum verification. Three tables are
imported: English pages (19,315,587 rows), English redirects (12,457,004 rows),
and Japanese redirects (954,569 rows). Full matching has not started.

The first continuation stopped while converting English `page_props`: an unused
`templatedata` property contains a compressed binary value. The reader incorrectly
decoded all properties as UTF-8 before filtering them. It now filters unused
binary properties before decoding and still rejects invalid UTF-8 in retained
QID records. No replacement characters or dropped QID records are permitted.
Seventeen targeted tests and Ruff passed, including binary-property exclusion
and strict QID decoding.
The fix also passed a replay using the actual binary template record and an
actual QID record from the failed dump.

The run resumed as PID 29380. Completed downloads and the three imported tables
are reused; matching rules and Daniel's input are unchanged. Current logs are
`C:\Users\User\.cache\geoai_wikipedia_dump_20261018.resume_20261019.stdout.log`
and `.resume_20261019.stderr.log`. The earlier error is retained in
`failure_20261019_before_binary_property_fix.json` inside the dump cache.
Use `process_id.txt` and current progress rather than the historical launch PIDs
below. A later `failure.json` indicates a new stopped attempt.

## Data and evidence

The official **20261001** English and Japanese `page`, `redirect`, `page_props`,
`pagelinks`, and `linktarget` SQL dumps total **12,905,954,998 bytes**. Download
URLs, published SHA1 checksums, file sizes, and original job metadata are saved
in the cache. Downloads resume from partial files. Complete files are checked
against the published SHA1; conversion reads the entire gzip stream and requires
the dump footer. Parquet outputs have SHA256 receipts.

The metadata tables retain namespace-zero pages, same-wiki redirects, and
page-to-QID references. The two large link tables are scanned locally, but only
links from Daniel's source pages and their Japanese counterparts, and their
referenced link targets, are loaded into BigQuery. Other target namespaces,
missing target IDs, missing pages, redirect failures, and pages without QIDs
are counted separately. Page checkpoints preserve every source title.

The production dataset is `geo-hagai-ndvi.geoai_wikipedia_dump_20261018`, location
US. Its reference tables have no default expiry, so later retrieval can reuse
them. Existing load receipts and BigQuery row counts are checked before reuse.
The first real table is loaded and verified:
`ja_redirect_20261001`, **954,569 retained rows / 1,034,207 scanned rows**.

These dumps are database link inventories, including transcluded templates and
navigation boxes. They are **not the same evidence as cleaned article HTML**.
The individual tables were exported at different times; the nominal dump date
does not establish a transactionally consistent or exact-revision link snapshot.
Page revision IDs and link-update fields are retained without claiming the
links belong to that exact revision. This run has a separate output directory.

## Matching rules

The accepted 80% highest trigram Dice threshold, compatible types, recorded
single-type correction, seeded random ties, date validation, frozen
already-matched second pass, and distinct synthetic IDs remain unchanged.
The final pass uses the existing fresh 103,235-QID WWII population, with the
recorded BigQuery name/type snapshot. No new article phrases are extracted and
no Daniel mention is split or merged. The canonical graph is unchanged.

The matcher checks the input hash, all 428 checkpoint filenames, each file hash,
and each original source title before it uses the dump snapshot. This route
does not fall back to Wikipedia article requests if the snapshot is incomplete.
The existing saved Wikidata name lookup and 461,094-QID reference export are
reused; only additional page candidates and required type ancestors need more
reference retrieval.

## Active jobs, saved data, and resume

All large files are on C: because D: has little free space.

- Dump cache and import progress:
  `C:\Users\User\.cache\geoai_wikipedia_dump_20261018\progress.json`.
- Download logs: the cache-directory path plus `.download.stdout.log` and
  `.download.stderr.log`.
- Full continuation logs: the cache-directory path plus `.full.stdout.log` and
  `.full.stderr.log`.
- New matching output:
  `C:\Users\User\.cache\geoai_full_daniel_dump_bigquery_20261018`.
  Its `progress.json` starts when matching starts; final results require
  `summary.json` and the validated output manifest.
- Reused Wikidata reference store:
  `C:\Users\User\.cache\geoai_bigquery_20261018`.

At launch, downloader PID 5544 runs two bulk download connections. Hidden
continuation PID 29628 waits for it and then runs the full importer and matcher.
The waiting process ID is saved in the dump cache's `process_id.txt`.
Process IDs are launch evidence, not permanent status indicators.

The former Wikipedia API worker was stopped. Its **69 saved page checkpoints**
remain in `C:\Users\User\.cache\geoai_full_daniel_bigquery_20261018`; its
`superseded.json` points to this replacement. Do not use that directory's stale
progress file as the current run status.

After confirming no current downloader or continuation remains active, resume
from `D:\Projects\GeoAI` with:

```powershell
python -u GG_Data/entity_resolution/wikipedia_dump_bigquery.py --project geo-hagai-ndvi
```

Do not launch a duplicate while the current jobs are active. Successful dump,
Parquet, query, and load artifacts are retained. Failures stop the run and write
`failure.json`; they are not reported as completed matching. Query dry runs and
the existing two-TiB maximum billed bytes per query remain in force. This is a
per-query limit, not a total budget. Actual BigQuery job statistics are saved.

## Verification and protection

Fifteen targeted offline tests passed. Ruff passed for the changed Python files.
A separate live BigQuery fixture passed Japanese-title lookup, multi-step
redirects, redirect cycles, broken redirects, and missing pages. Its dataset has
a seven-day default expiry; fixture records are not matching candidates.
The real Japanese redirect import also passed published checksum verification,
full gzip parsing, Parquet conversion, and the BigQuery row-count check.

Code/docs backup: **Local checkpoint only** after commit. Local downloads and
matching outputs: **Unprotected** until an off-device backup is verified.
BigQuery reference tables are cloud copies of reference data, not a backup of
the complete run.

Sources: [English dump metadata](https://dumps.wikimedia.org/enwiki/20261001/dumpstatus.json),
[Japanese dump metadata](https://dumps.wikimedia.org/jawiki/20261001/dumpstatus.json),
[Wikimedia dump inventory](https://meta.wikimedia.org/wiki/Data_dumps/What%27s_available_for_download),
[pagelinks schema](https://www.mediawiki.org/wiki/Manual:Pagelinks_table), and
[linktarget schema](https://www.mediawiki.org/wiki/Manual:Linktarget_table).
