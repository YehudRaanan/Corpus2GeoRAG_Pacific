# Direct Daniel-to-Wikidata small rerun

Completed 18 October 2026. No notebook, article phrase extraction, trained model,
manual match selection, or canonical graph update.

The same three pages and all 362 original Daniel mention rows were retained.
Candidate names come from Wikidata English/Japanese labels, aliases and sitelinks.
Source-page references and direct article hyperlinks were reused from the saved
English/Japanese snapshot. Additional Wikidata lookups use only Daniel's mention
names and their case/space/symbol variants, within each mention's source page.
The former article `extracted_names`, phrase searches and phrase-derived pools
are not used. Daniel's original mention `word` and context `Text` remain separate.

| Result | Mentions |
|---|---:|
| Page-context Wikidata matches | 254 |
| Already-matched fallback | 0 |
| Saved fresh-WWII Wikidata fallback | 4 |
| Normalized calendar dates | 37 |
| Unresolved, separate synthetic mention IDs | 67 |
| Total | 362 |

All 38 DATE mentions bypass name matching. Dates preserve day/month/year/range
precision and explicit qualifiers. No missing year or day is inferred.
`29 February 1943` is invalid and remains unresolved; it occurs in both Daniel's
context and the saved source article. Calendar values such as `DATE:1942-03` are
not Wikidata QIDs or claims of new real-world entities.

Entity matching retains highest compatible trigram Dice score >= 0.80 and seeded
random QID ties. Space/symbol cleanup and joining separated single-letter
initials apply only to page-context comparison. Titles are not removed. Fallback
matching uses the original name normalization. The verified same-day 103,235-ID
WWII snapshot is reused; no new WWII collection was needed for this small rerun.

Examples: `US` now matches Q30 at 1.0; `1st Mobile Fleet` matches Q4596490 at 1.0;
`December` becomes `DATE:--12` with month-of-year precision.

Remaining unresolved: 46 have no name above threshold, 17 have type rejections,
3 lack accepted type evidence, and 1 is an invalid/unsupported date.
`Yale University` now retrieves the correct Q49112 at 1.0, but the existing type
filter rejects it. Its saved class graph reaches both organization and the
Wikimedia-list exclusion through Q1188663 -> Q80096233 -> Q13406463. This is a
remaining type-filter defect, not evidence that Yale is absent from Wikidata.
The New York Times and titled personal names also remain unresolved under the
unchanged type and name rules. Wrong accepted names such as Mayforce -> Layforce
and Alfred Curtis -> Wilfred Curtis remain. Match counts are not accuracy.

[All result rows](runs/direct_wikidata_small_20261018/matches.csv) ·
[Summary](runs/direct_wikidata_small_20261018/summary.json) ·
[Manifest and hashes](runs/direct_wikidata_small_20261018/manifest.json)

Verification: exact raw-row preservation; 362 CSV/result rows; distinct synthetic
IDs; date precision/invalid-date checks; compatible types, threshold and stage
pool membership; Daniel-only lookup terms; artifact/code hashes; Ruff and four
unit checks. Backup: Local checkpoint only.
