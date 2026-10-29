# Cleaner on the original 100-page unresolved baseline

## Result

The cleaner ran on the original, pre-template-repair export. It helps separate
source material and prepares cleaner context. It has **not produced new QID
matches**. The output is experimental: inspection found valid content removed
by some template rules. Do not promote these exclusions into matching.

## Population

Original baseline: 40,070 mentions; 13,627 matched, 19,071 unresolved non-DATE,
and 7,372 DATE excluded from matching. The later 18,110 unresolved count belongs
to the repaired experiment, not this baseline.

The cleaner input is the baseline unresolved export: 26,443 rows, all 100 pages,
130 historical revisions. The full sample has 132 revisions; only 130 occur in
this unresolved subset. No repaired words or recovered QID inventory were used.

## Cleaning outcomes

| Original unresolved non-DATE | Rows | Share |
|---|---:|---:|
| Mention retained with valid cleaned offsets | 9,522 | 49.9% |
| Mention removed from cleaned text by current rules | 8,335 | 43.7% |
| Placement or source transformation still uncertain | 1,214 | 6.4% |
| Total | 19,071 | 100% |

These are source-text outcomes, not identity decisions. All original rows remain.
Of the 9,522 retained mentions, 8,016 have no context-review flag; 1,506 have
surrounding syntax that still needs review. A clear context does not prove a QID.

| Type | Retained | Removed | Uncertain | Total |
|---|---:|---:|---:|---:|
| LOC | 3,394 | 1,653 | 286 | 5,333 |
| MISC | 2,794 | 2,383 | 397 | 5,574 |
| ORG | 2,200 | 2,176 | 272 | 4,648 |
| PER | 1,134 | 2,123 | 259 | 3,516 |

Of the removed mentions, source rules identify 5,286 in citations, 893 in
reference notes, and 405 in bibliographic sections: 6,584 in these categories.
Other removals include captions (230), category metadata (390), navigation (98),
external/related sections (245), file names and template/control material.
This is rule-based classification, not a manually verified set of safe removals.

The 1,214 uncertain mentions comprise 643 partially removed spans, 399 overlaps
with uncertain source structures, 109 repeated passage placements, and 63
passages without an exact raw placement.

DATE stays separate: 3,921 retained, 3,202 removed, 249 uncertain. No date linking
or semantic date interpretation was attempted.

## Examples and limits

- Row 147283, Archibald Vincent Arnold: `Arnold married Margaret Treat Arnold.{{citation needed|date=November 2018}}`
  becomes `Arnold married Margaret Treat Arnold.`; the mention `Margaret` survives.
- Row 173778, Attack on Yokosuka: `Task Force&nbsp;38` becomes `Task Force 38`.
  The old value is retained. There are only 28 working-name changes among the
  19,071 unresolved non-DATE rows; cleaning mainly changes context and scope.
- Row 5964, 15th Antiaircraft Artillery Battalion: citation author `Rottman`
  is removed from the cleaned text.
- Rows 5979 and 5980: `Corps` and `Air Station` remain fragments of
  `Marine Corps Air Station New River`. This cleaner does not expand or identify them.
- Row 21578 contains `Rear-Admiral|| [[Keizō Komura`. The mention crosses table
  and link syntax, so it remains uncertain rather than receiving guessed offsets.

### Content-loss findings: do not promote this run

1. **Factual ship-class fields:** 16 non-DATE mentions on 12 pages were KEEP
   under the source filter but removed by the cleaner, excluding captions.
   All 16 are ship-class infobox values. For example row 1618251 loses
   `Charles Lawrence` from `|class={{sclass|Charles Lawrence|transport|1}}`.
   The cleaner subtracts `class` as a formatting key from infobox values
   (`clean_source_text.py`, infobox branch near line 139).
2. **Japanese names:** the `nihongo` handling retains only the first parameter;
   Japanese and romanized variants can be lost even when displayed in the article.
3. **Quotation attribution:** author/source parameters can be discarded,
   including person or organization names. These are not necessarily citations.

The 16 ship-class rows are explicitly listed in `analysis.json`. In the inspected
small transition groups, 17 Japanese-template rows and seven quotation
attribution/title rows also require protection or review. Some are damaged spans
or meanings, so these 40 flagged rows are not 40 verified entity losses.
The extent outside these transition groups is not yet measured. Their discovery means that the
8,335 removals must not be reported as 8,335 confirmed irrelevant mentions.
No production rule was changed during this test.

## Verification and reproducibility

- 70 existing cleaner tests passed in this session. The new findings expose
  cases those tests do not yet protect.
- Both root and an independent read-only reviewer checked all 26,443 unique rows.
- All original input columns except working `word` are unchanged; `word_original`
  equals the original word column. Original Text/start/end and QID assignments stay unchanged.
- Every mapped slice equals its working word; all nonmapped cleaned offsets are null.
- Input and raw historical-revision hashes passed verification.
- Cleaner runtime: 13.297 seconds; source-classification check: 20.532 seconds.
  These are script elapsed times, not total active work. Cloud cost: US$0.
- Cleaner output SHA256: `0240b2aa5994302a8e3726e82f7a9dadb7633b3a361a21d4229b6f16535a73ed`.

Artifacts are under
`Data/external/hundred_page_pilot_20261028/source_text_cleaner_baseline_unresolved_20261029/`:

- `run_1/mentions.parquet`: all 26,443 baseline unresolved/DATE rows plus clean fields.
- `run_1/summary.json` and `used_revisions.parquet`: provenance and runtime.
- `source_filter/`: independent source-role annotations on the same original rows.
- `analyse.py`: repeatable local integrity checks and analysis; run as
  `python -m Data.external.hundred_page_pilot_20261028.source_text_cleaner_baseline_unresolved_20261029.analyse`.
- `analysis.json`: counts, warning IDs, output hash, `ready_for_matching=false`.
- `examples.json`: traceable source-row examples and original windows.

## Next action

First protect ship-class values, Japanese name variants, and quotation
attributions with focused regression tests. Then rerun cleaning and assess
partially contaminated mention spans. Only after that should candidate/model
matching be rerun with cleaned text and cleaned offsets. Its benefit must be
measured against this fixed original baseline; fewer in-scope rows are not
newly resolved QIDs.

Backup status: local report checkpoint only; ignored experiment data remains local
and is not protected on GitHub.
