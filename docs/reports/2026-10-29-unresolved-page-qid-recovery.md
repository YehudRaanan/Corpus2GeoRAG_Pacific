# Missing page-QID recovery: three saved revisions

The reviewed inventory adds **23 QIDs**, all supported by Ship-template targets
in the saved Shōji Nishimura revision. The three-page inventory grows from 112
to 135 unique `(page_id, revision_id, qid)` rows. **No mention was resolved or
reassigned.** All 369 original unresolved mentions remain unchanged.

## What ran

One new pipeline stage, `recover_page_qids.py`, reuses the collector's revision
validation, title resolution, API evidence cache and native metadata conversion.
Training code and the inference pipeline were not changed.

| Input / result | Count |
|---|---:|
| Exact historical page revisions | 3 |
| Original unresolved mentions / groups | 369 / 253 |
| Ship template occurrences checked | 36 |
| Failed ordinary article links checked | 2 |
| Category/file occurrences excluded | 32 |
| Distinct target titles checked | 32 |
| Supported target occurrences | 30 |
| Target occurrences retained for review or without a QID | 8 |
| Added page/revision/QID rows / distinct QIDs | 23 / 23 |
| Final inventory rows | 135 |
| New public API requests, whole task | 2 |
| New public API requests, final replay | 0 |
| New paid cloud cost | US$0 |

Exact scopes: Nishimura `781032/1379821139`, Fort Stevens
`23680822/1375594940`, and 1st Mobile Fleet `29607850/1323366204`.
No new QIDs were added for the latter two revisions.

The first version contained 24 additions. Independent review found that the
source's Asagumo `(1938)` redirects to `(1937)`. That candidate was excluded
from the final automatic inventory. The first version and its responses remain
unchanged. The final version was rebuilt from those responses without network
access. Use **`qid_recovery_20261029_v2`** as the reviewed output.

## Effect on unresolved cases

**26 mentions in 26 groups** now have at least one previously documented audit
hypothesis available in their page inventory. These remain hypotheses, not
independent identity gold or successful model decisions.

Examples of newly available candidates:

| Original Daniel name / type | Source-supported QID candidate | Important limit |
|---|---|---|
| Haruna / MISC and Haruna / LOC | Q1066681, Japanese battleship Haruna | Original Daniel types are unchanged. |
| Urakaze / ORG and Urakaze / MISC | Q11558386, Urakaze (1915) | The source's explicit 1915 qualifier is retained. |
| Kawakaze\|1917 / MISC | Q26723632, Kawakaze (1917) | The Daniel span contains markup; it was not repaired or assigned. |
| Yamato\|\|2 / MISC | Q866039, Japanese corvette Yamato | This is not the battleship with the same name. |

The report also records **53 mentions within recovered template source spans**.
That broader count includes 29 occurrences of `Japanese` and one display
parameter `2`; it must not be reported as 53 plausible identity matches.
These are contextual/source-enclosure candidates only. Of the 26 audit-supported
mentions, 23 also have source enclosure evidence and three have audit evidence
without a literal enclosing-template match in their original passage.

The mutually exclusive case statuses cover all 369 rows:

| Status | Mentions |
|---|---:|
| New source-enclosure candidate, not identity proof | 53 |
| Audit hypothesis newly available without source enclosure | 3 |
| No case-specific new support from this recovery | 223 |
| DATE, outside this QID recovery | 90 |

Thus, 56 rows have some new case-level evidence, but **26** is the narrower count
with a pre-existing audit hypothesis now available. Neither number is resolution
accuracy. Matching, type compatibility and independent identity review remain
separate steps.

## Cases deliberately left out

- **Yugiri (1899):** the exact source title is missing; the proposed Yūgiri spelling
  was not substituted automatically.
- **Yura:** the source says destroyer, while the proposed Q4385050 is a cruiser.
- **Asagumo:** source year 1938 differs from the current redirect's 1937; Q2991436
  is retained as `verified_qid` in review evidence, not added to the inventory.
- **Wakatake:** two source occurrences still lack an exact target mapping.
- **Sunosaki, Akiji Tagami and Sueo Ōbayashi:** exact queried titles remain missing
  in the saved public response. This does not prove no relevant Wikidata item exists.
- Unlinked names, dates and template families without an implemented target rule
  were not searched as new entities. Parameterless `IJN` is navigation.

Unqualified Kiku and explicit Kiku `(1920)` retain separate source occurrences.
The former has an explicit current redirect to the latter; the exact qualified
source occurrence independently supports the same candidate Q22093779.

## Provenance and checks

Historical source text is bound to the exact page/revision and SHA-256. Each
target retains its literal raw span, offsets, title and evidence path. Current
title lookup responses separately retain retrieval time, redirect chain, target
page ID, QID and evidence hash. Native metadata retains its own source and
revision information. Four added records reuse existing selected BigQuery
metadata; 19 use saved Wikidata API metadata. **No BigQuery query was executed.**

The Ship target rule reconstructs prefix, name and identifier from raw parameters;
display options do not change the target year. This follows the documented
[Ship template rule](https://en.wikipedia.org/wiki/Template:Ship/doc#Basic_usage).
It is not a historical snapshot of the transcluded template implementation.
No current navigation-box expansion was imported.

Focused tests cover source offsets/protected text, ship years, unsafe parameters,
disambiguation, unrelated batch redirects, section redirects and invalid metadata.
Final verification also checks all 369 report rows, unchanged original inventory
records, unique merged keys, raw target spans and protected baseline hashes.
The final command passed **31 tests** (25 recovery tests and six existing
collector tests). Black, isort and ruff passed for both new Python files.
Independent output review passed 53 assertions and verified 154 protected hashes.

## Files

Final local folder:
`Data/external/hundred_page_pilot_20261028/qid_recovery_20261029_v2/`

| File | Purpose |
|---|---|
| `entities.parquet` | Original three-scope inventory plus the 23 supported additions. |
| `added_entities.parquet` | Only those 23 additions, using the existing entity schema. |
| `target_evidence.parquet` | All 38 inspected occurrences, including failures and review cases. |
| `native_metadata.parquet` | Native metadata for the 23 added QIDs. |
| `unresolved_case_report.parquet` and `.csv` | All original 369 audit rows with separate recovery evidence fields. |
| `summary.json` | Counts, runtime, hashes, exclusions and current-versus-historical limits. |

Original requests remain in `qid_recovery_20261029/requests/`. Independent review
evidence is in `qid_recovery_20261029_review/`. No matching jobs, model/reference
labels, original Parquet, final tables or graph weights were changed.
The existing `what_happened_at` spatial date-filter issue remains open;
this recovery does not change Geography or broader acceptance status.

## Timing and adjustments

Preflight began 12:34:32; execution approval was received before execution started
at 12:41:38, all on 29 October 2026, Asia/Jerusalem (UTC+02). The approved whole-task
estimate was 30–60 minutes, including preflight and excluding approval/environment
waits. Exact active-work and wait durations are not measured and remain unknown.

The first data run took 7.84 seconds; the final offline replay took 2.78 seconds.
These script runtimes exclude planning, coding, tests and review. Issues found
and fixed during review: missing/invalid entity stubs, section redirects, redirects
from unrelated titles in the same batch, invalid display options, and ship-year
changes. The original run's redirect response had no section redirects, so the
batch guard did not change its counts; its final evidence chains were still
corrected in the offline replay. Unicode inspection used `python -X utf8`.

**Local checkpoint only:** code commit `9db419a`. Ignored data and cached
responses remain local and are not backed up on GitHub. No push is authorized.
