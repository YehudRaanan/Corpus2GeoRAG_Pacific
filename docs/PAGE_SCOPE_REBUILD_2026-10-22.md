# Page-scoped matching correction and downstream rebuild

## Approved scope

The owner approved a 2–4 hour correction on 22 October 2026, including a
specific check of the London example. Recalculate all 309,864 original Daniel
rows, then rebuild the same frozen 10K POC and the previous ten-input Geography
sample. Preserve previous artifacts. Stop for consultation on new source-data
or business-rule problems. Full Geography import, final graph export and Agent
acceptance are outside this correction's completed-stage boundary.

## Defect and correction

The first-stage candidate pool wrongly included global name-search results.
It must contain only the English source article, its Japanese counterpart,
and their directly linked Wikidata QIDs. Global name hits cannot be attributed
to an article merely because Daniel used the same text there.

`SOURCE_PAGE_EN_JA_LINKS_ONLY_V1` now identifies the corrected scope in run
manifests. Old matching manifests are rejected by the POC importer. All three
matching stages were recomputed: page-only candidates, the newly matched-ID
pool, then the existing saved WWII reference. The approved similarity,
type, seeded tie and synthetic-per-mention rules were retained. Source caches
are reusable; old decisions and population-dependent aggregates are not.

Implementation and contracts:

- [Population S2T](SOURCES_TO_ENTITY_DATA_MODEL_S2T.md), section 3.
- [Page-scoped rebuild](../GG_Data/entity_resolution/rebuild_page_scoped.py).
- [Explicit downstream stage inputs](../GG_Data/pipeline/rebuild_poc.py).

## Verified matching result

Output bundle: `GG_Data/pipeline/outputs/rebuild_page_scope_20261022/`.

| Stage | Original mention rows |
|---|---:|
| Page-scoped Wikidata | 134,406 |
| Newly matched-ID pool | 60,787 |
| Saved WWII reference | 5,717 |
| Normalized dates | 29,969 |
| Synthetic unresolved | 78,985 |
| **Total** | **309,864** |

All original mention IDs, raw rows and their order match the previous run.
The new run has 200,910 QID-matched mentions and 21,273 distinct matched QIDs.
These are coverage counts, not estimates of identity accuracy.

Evidence under the output bundle:
`matching/manifest.json`, `matching/summary.json`,
`matching/london_validation.json`, `matching_correction_audit.json`.

## London regression

Original mention: London in a Faber and Faber publication reference on
the source page *Battle of the Mediterranean*. The previous assignment was
Q1001456 (London, Ohio).

The actual article candidate pool has 721 QIDs and contains neither Q84 nor
Q1001456. The corrected page stage leaves the mention unmatched. The second
stage automatically chooses **Q84 (London, United Kingdom)**, similarity 1.0,
with no other QID tied for highest score. The validation does not override
the assignment.

The same previous Geography mention for Java now matches Q3757 (Java,
Indonesia), replacing the Scottish hamlet assignment. Hoosick Falls, Tinian
Town and Sunharon Bay remain synthetic under the unchanged matching rules.
Geography must use those new identities; it cannot restore the old QIDs.

## Downstream checkpoint

Verified at 07:23, 22 October 2026, Asia/Jerusalem (UTC+03):

- The exact original 10K sampled input positions were imported again.
- Entity population completed: 5,210 typed rows, including 2,683 distinct
  Wikidata IDs and 2,503 separate synthetic mentions.
- Entity full records use the agreed Wikidata snapshot. Importance was
  recalculated from the corrected 10K mention-to-ID assignments. No synthetic
  row has a null importance score.
- English/Japanese relevance recalculation is running from the saved full
  page-link sources. Events, Relations and Geography continuation are pending.
- The previous populated model and Geography outputs remain historical
  artifacts and are not valid corrected outputs.

Code has local Git checkpoints. Generated artifacts are ignored by Git and
are not protected on GitHub. No final graph has been written.
