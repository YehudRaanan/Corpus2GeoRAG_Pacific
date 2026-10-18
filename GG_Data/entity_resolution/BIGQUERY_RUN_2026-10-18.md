# Full Daniel matching with BigQuery — 18 October 2026

Launch status: **RUNNING**. This is not a completed full-data result.
The current state is in the output directory's `progress.json`.

At 21:55 Israel time, the large reference query had completed on BigQuery and
its results were being downloaded and saved. It covers 461,094 candidate QIDs
(including the already cached records); its job scanned 1,589,961,031,680 billed
bytes. Fourteen of 428 page checkpoints were saved. Wikipedia returned HTTP 429
responses, so page collection was respecting the server's retry delays.

The user requested the GCP CLI path after the Wikidata API repeatedly returned
`maxlag`. The prior API worker was stopped; its saved data remains available.
The new worker uses `bq`, the BigQuery component of the Google Cloud CLI, in the
existing billing-enabled project `geo-hagai-ndvi`, location US. The default
`handover-480513` project has billing disabled: it completed the name lookup,
but rejected the larger raw-record query under its free-query quota. That
successful lookup is saved and reused across the project switch.

## Method

All 309,864 pinned Daniel mentions and all five types remain in scope. The
accepted 80% trigram rule, compatible types, single-type correction metadata,
seeded ties, frozen already-matched pass, date handling, and separate synthetic
IDs remain unchanged. No independent article-name extraction is performed.

Wikidata names, aliases, sitelinks, P31, and P279 come from
`bigquery-public-data.wikipedia.wikidata`. The initial table metadata reports
90,722,347 rows and a last modification on 7 October 2026. The run records the
table metadata and fixes a system-time snapshot at startup. That table time
does not establish the update date of every entity; entity modification times
are retained separately.

The existing fresh 103,235-QID WWII population defines membership in the final
pass. Names and types for those IDs now come from the BigQuery snapshot. IDs
absent from that snapshot are recorded explicitly. This changes the reference
source and version; it does not guarantee identical assignments to the API run.

Wikipedia still supplies source page IDs, revisions, direct hyperlinks, and
Japanese counterparts. Three independent page clients share a process-wide
request interval of at least 1.1 seconds and collect the English and
Japanese evidence. The Japanese article must share the source QID. No Wikidata
API or Wikidata SPARQL endpoint is used in the new collection path.

## Can BigQuery also replace Wikipedia page requests?

Checked with the GCP CLI on 18 October 2026:

- `bq ls bigquery-public-data:wikipedia` lists pageview tables, selected
  entity tables, and `wikidata`; it has no article-content or pagelink table.
- `bq show bigquery-public-data:samples.wikipedia` shows revision metadata
  (titles, page IDs, revision IDs, timestamps, comments, character counts),
  with no article text or outbound links. Google documents this sample as
  revision history only through April 2010. It cannot supply this run's
  English/Japanese article-link evidence.

The CLI metadata is saved in the reference store as `wikipedia_tables.json`
and `wikipedia_sample_table.json`. No article retrieval was switched to these
tables. At 21:59 Israel time, 17 page checkpoints were saved; the reference
export was still being downloaded.

Using BigQuery for this remaining step requires a separate import of official
English/Japanese Wikimedia snapshots: page IDs/revisions, pagelinks and
link targets, redirects, and page-to-QID references. The dump date and link
scope must be recorded; a database link inventory must not be represented as
the same evidence as links parsed from a particular saved article revision.
This import is not implemented. The current worker still uses Wikipedia for
page evidence, with cached successful responses and server retry delays.

Sources: [Google sample-table documentation](https://docs.cloud.google.com/bigquery/public-data),
[Wikimedia dump inventory](https://meta.wikimedia.org/wiki/Data_dumps/What%27s_available_for_download),
and [MediaWiki pagelinks schema](https://www.mediawiki.org/wiki/Manual:Pagelinks_table).

## Saved data and costs

Reference data and CLI evidence:
`C:\Users\User\.cache\geoai_bigquery_20261018`.

Full matching run and progress:
`C:\Users\User\.cache\geoai_full_daniel_bigquery_20261018`.

The large reference export runs alongside page collection. Remaining page-only
QIDs are fetched after those pages are complete. Successful query results are
saved as compressed JSON. SQL hashes identify
reusable queries. The store also retains SQL, dry-run estimates, job statistics,
projected entity records, and the original table snapshot metadata. Result row
counts must match the destination table before a query is accepted. A new
client reuses saved query results without submitting another job.

Daniel's exact name variants are loaded into an input table in the project's
`geoai_resolution_20261018` dataset. The saved name-input table remains in
`handover-480513`; subsequent larger input tables use `geo-hagai-ndvi`.
New tables have a seven-day default expiry.
Queries first run in dry-run mode and use a two-TiB maximum billed-byte limit
per job. Actual bytes billed are retained in job statistics. The limit is per
query, not a total-run budget. The 150,294 name variants are input search forms,
not new extracted entities.

Current run logs are next to the output directory with `.full.stdout.log` and
`.full.stderr.log` suffixes. Earlier attempt logs are preserved separately.
The process ID is in `process_id.txt`. Completed pages and successful
BigQuery results survive a stopped process. To resume:

```powershell
python -u GG_Data/entity_resolution/bigquery_direct_wikidata.py --project geo-hagai-ndvi
```

## Verification

Fourteen offline tests passed, including the accepted pilot's exact
page decisions, cross-client cache reuse, bilingual BigQuery projection,
deprecated-claim exclusion, explicit missing IDs, cross-project reuse, and
rejection of truncated BigQuery results. Ruff passed. Full-run
input preservation and assignment checks run before final output is accepted.

Live BigQuery validation completed the 150,294-variant name lookup and saved
373,048 name/QID pairs (362,264 distinct QIDs), scanning 25,893,535,744 billed
bytes. These are candidates, not accepted matches. A separate three-record
projection check retrieved English/Japanese names, sitelinks and nondeprecated
types for Q5, Q49112 and Q705319, with 1,000,341,504 billed bytes. The blocked
free-quota attempt produced no successful metadata export.

Backup: **Local checkpoint only** for code/docs after commit. Local reference
and run files are **Unprotected** until off-device backup is verified. Cloud
input tables are not a backup of local query results or matching output.
