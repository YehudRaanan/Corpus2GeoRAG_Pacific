# Full Daniel direct-Wikidata run — 18 October 2026

Status: **RUNNING**. Final counts are not available yet.

At 21:25 Israel time, collection had completed 1/428 source pages and Wikidata
was returning `maxlag` (temporary server replication delay). Automatic retry
from the saved checkpoint was verified. This is a running job, not a completed
full-data result; check `progress.json` for the current stage.

The user retained the 80% threshold and requested all Daniel data. The pinned
Parquet contains **309,864 mentions across 428 distinct source titles**:
89,846 LOC, 85,676 MISC, 48,230 PER, 47,680 ORG, and 38,432 DATE.

The full runner reproduces every page-pass decision of the accepted three-page
pilot (263 assignments among 324 non-date mentions). The original Parquet
confidence values are preserved at full precision; the pilot had serialized
them with ten decimal places.

## Rules retained

1. Collect the source English page and its Japanese counterpart when available.
2. Candidates are direct page hyperlinks and direct Wikidata label/alias
   lookups of Daniel's original names and the accepted case/space/symbol variants.
   There is no article phrase extraction and no splitting or adding mentions.
3. Use the highest trigram Dice score at least 0.80, compatible types first,
   followed by the approved single-type correction with row metadata. Equal
   highest QID scores use seeded random selection, seed 20261018.
4. Freeze all QIDs assigned in the page pass. Match unresolved mentions to that
   frozen set; then use the verified same-day 103,235-QID WWII query snapshot.
5. Each remaining unresolved mention receives its own synthetic ID. Type
   conflicts and unknown types retain separate reasons and prefixes. DATE
   mentions use the unchanged calendar parser and validation.

The run writes separate outputs and leaves the canonical graph unchanged.
The prior accuracy limitations and the agreed WWII query scope still apply.

## Run files

Code: [full_direct_wikidata.py](full_direct_wikidata.py).

The run uses `C:\Users\User\.cache\geoai_full_daniel_20261018` because D:
had only approximately 40 MiB free at startup. This folder contains:

- `progress.json`: current stage and completed counts.
- `pages/`: resumable English/Japanese page evidence with revisions and IDs.
- `entity_metadata.json.gz`: candidate names, types, and inheritance evidence.
- On completion: `matches.json.gz`, `matches.csv.gz`, `summary.json`, candidate
  evidence, request evidence, and a hash manifest.

Process ID is saved in `process_id.txt`. Logs are alongside the run directory:
`C:\Users\User\.cache\geoai_full_daniel_20261018.resume.stderr.log` and
`C:\Users\User\.cache\geoai_full_daniel_20261018.resume.stdout.log`.
The initial attempt's logs without `.resume` are preserved separately.
The hidden process continues independently of the chat. Public request retries
and saved page checkpoints prevent a transient failure from discarding completed
collection. Temporary public-service failures trigger up to 20 automatic resume
attempts with increasing delays of up to five minutes. Input or decision
validation failures stop the run. Rerun the command to resume if necessary.

```powershell
python -u GG_Data/entity_resolution/full_direct_wikidata.py
```

## Saved reference data and reuse

Successful public responses are compressed JSON files in
`C:\Users\User\.cache\geoai_bilingual_pilot_20261018`. The runner reads an
existing response before making a request. The key includes the URL, exact
parameters, and GET/POST method; there is no automatic expiry. Retain this path
between runs. Different requests can still require network access. Service
errors are not saved as successful data.

On 18 October, **303 saved responses** were replayed with network access blocked:
all passed, with **zero network requests**. The saved data includes English and
Japanese page responses, Wikidata records, and SPARQL results. A SHA-256 inventory
was saved as `saved_data_manifest_20261018.json` in that cache directory. It
records 305 files totaling 18,491,639 compressed bytes: the 303 responses, the
WWII ID query snapshot, and the separately stored WWII name snapshot. This is a
point-in-time inventory; new successful responses continue to accumulate.

The 103,235-QID name snapshot remains in
`runs/bilingual_pilot_20261018_v1/fresh_wwii_names.json.gz`; its original manifest
hash was verified. The full run also reuses completed `pages/` files and its
`entity_metadata.json.gz` checkpoint from the run directory above. These saved
files are reference data, not new Daniel mentions. Matching rules are unchanged.
No new cloud query, paid retrieval, or full matching run was started for this
storage check. Completed matching output is reusable after its manifest exists
and its output hashes pass verification.

Verification before launch: pilot-equivalence integration check and six existing
matching/date/type checks passed; Ruff passed. Completion checks require every
raw row to be preserved, all original mention IDs to agree, every remaining
non-date unresolved row to have passed all three stages, every QID score to meet
0.80, and every synthetic ID to be unique.

Backup: **Local checkpoint only** for committed code and this report. Large run
files on C: are **Unprotected** until an off-device copy is verified.
