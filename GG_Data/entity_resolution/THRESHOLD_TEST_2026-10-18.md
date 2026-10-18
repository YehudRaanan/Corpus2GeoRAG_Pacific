# Quick page-matching threshold test

Recommendation: keep the working threshold at 80% for now. This small sensitivity
test does not establish an optimal threshold or measure overall accuracy.

## Scope and controls

All 324 original non-date mentions from the same three-page, 362-row pilot.
The 38 DATE mentions are excluded because they use calendar validation.
Same saved candidate IDs, bilingual names, type policy, page-only cleanup, and
seed at every threshold. No new mentions, article extraction, Wikidata requests,
manual match overrides, or canonical graph changes. The 80% test reproduces all
324 saved page-stage decisions exactly, including failures.

Only page matching is tested. These are not full-workflow totals: already-matched
and WWII fallback stages are not rerun. New lower-scoring WWII candidates would
need additional type metadata; treating missing metadata as a rejection would
make a lower-threshold comparison incomplete.

## Results

| Minimum similarity | Page assignments | Added versus 80% | Lost versus 80% |
|---|---:|---:|---:|
| 70% | 277 | 14 | 0 |
| 75% | 270 | 7 | 0 |
| 80% | 263 | 0 | 0 |
| 85% | 260 | 0 | 3 |
| 90% | 258 | 0 | 5 |
| 95% | 249 | 0 | 14 |

These are mention assignments, not distinct entities or verified correct matches.
No threshold changed the selected QID of a mention that remained assigned at both
that threshold and 80%; the differences here are additions and removals.

## Checked examples

The following diagnoses use original context, saved page links, and saved
Wikidata names/sitelinks. They are examples, not a labelled evaluation set.

| Change | Original mention | Selected record | Score | Observation |
|---|---|---|---:|---|
| Added at 75% | General Claude Auchinleck | Claude Auchinleck, Q312685 | 78.9% | Correct person; target is linked from the source. |
| Added at 75% | 23rd Indian Brigade | 23rd Indian Infantry Brigade, Q4631637 | 76.2% | Supported by the source's renumbering account and brigade link. |
| Added at 75% | Indian Infantry Divisional Signals | 14th Indian Infantry Division, Q4550030 | 77.2% | Wrong: the signals unit is not the entire division. |
| Lost at 90% | Franklin Roosevelt | Franklin D. Roosevelt, Q8007 | 88.2% | A correct match is lost. |
| Still assigned at 95% | Winston Churchill, row 508 | Winston Churchill (Cavalier), Q2916076 | 100% | Wrong person for the 1943 conference; the saved Japanese sitelink identifies the 1620–1688 person. |

Lower thresholds can recover abbreviated or titled names and can also merge
different units. Higher thresholds can remove correct names and leave exact-name
homonyms. At 80%, 164 of the 263 page assignments have multiple equally scoring
eligible QIDs; at 95%, 163 of 249 still do. This does not mean all ties are wrong,
but threshold changes cannot separate equal scores. The agreed random tie rule
was retained in the test.

Keep 80% as the provisional working setting. Use page-link evidence and a labelled
sample to evaluate any later threshold change. No global change to 75% or 90%
is justified by this test alone. The current 269 full-workflow QID assignments,
37 calendar dates, and 56 synthetic IDs remain unchanged.

## Reproduce and inspect

```powershell
python GG_Data/entity_resolution/threshold_sensitivity.py --output <new-output-directory>
```

[All 1,944 threshold/mention comparisons](runs/threshold_sensitivity_20261018/comparison.csv) ·
[Summary](runs/threshold_sensitivity_20261018/summary.json) ·
[Decision evidence](runs/threshold_sensitivity_20261018/decisions.json.gz) ·
[Hashes and limits](runs/threshold_sensitivity_20261018/manifest.json)

Verification: original-row references, source/artifact hashes, exact reproduction
of every 80% page decision, unchanged 80% default, Ruff, and six unit checks.
Backup: Local checkpoint only.
