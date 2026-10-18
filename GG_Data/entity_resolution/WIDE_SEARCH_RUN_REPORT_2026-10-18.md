# Full-reference, eligible-first matching trial

Completed **18 October 2026, 17:07 Asia/Jerusalem**. Run ID:
`matching-fa75bfff681bfb1f7ea9`.

All **309,864 raw mentions**, **428 source titles**, **34,893 paragraphs**, and
all five extraction types were processed automatically. The trial produced
**63,922 suggestions** and **245,942 unresolved results**. Candidate coverage
increased, and several previously demonstrated failures now produce the expected
IDs. Clear wrong suggestions also remain. **This is not an accuracy result or an
approved production matcher.** No suggestions were promoted into the canonical
graph, and no unknown entities were created.

## Comparison with the resolved-page baseline

Both runs use exactly the same raw rows, source-page identities, saved reference
snapshot, mapped assertions, and relation-map-v2.1.0. Counts below are repeated
text mentions, not distinct entities.

| Measure | Resolved-page baseline | Wider-search trial |
|---|---:|---:|
| Input and output mentions | 309,864 | 309,864 |
| Mentions with a candidate passing the same 0.80 name threshold and current type policy | 11,936 | 69,581 |
| Automatic suggestions | 9,555 | 63,922 |
| Unresolved mentions | 300,309 | 245,942 |

The baseline also retrieved weaker candidates at 0.35; its 59,660 mentions with
any candidate must not be compared directly with the trial's eligible-only
candidate count.

| Decision transition | Mentions |
|---|---:|
| Previously unresolved, now suggested | 54,724 |
| Same suggested ID in both runs | 8,745 |
| Suggested in both runs, but ID changed | 453 |
| Previous suggestion removed | 357 |
| Unresolved in both runs | 245,585 |
| **Total** | **309,864** |

The net suggestion increase is **54,367**. Added, changed, and removed
suggestions have not been classified as correct or incorrect by a gold standard.

| Type | Raw mentions | Previous suggestions | Trial suggestions | Trial unresolved |
|---|---:|---:|---:|---:|
| PER | 48,230 | 1,703 | 7,065 | 41,165 |
| LOC | 89,846 | 3,021 | 21,480 | 68,366 |
| ORG | 47,680 | 1,863 | 15,563 | 32,117 |
| MISC | 85,676 | 2,925 | 17,171 | 68,505 |
| DATE | 38,432 | 43 | 2,643 | 35,789 |
| **Total** | **309,864** | **9,555** | **63,922** | **245,942** |

## The two tested changes

1. Search all English labels and aliases in the same saved Wikidata snapshot,
   using the existing trigram index. The page and its direct neighbours no
   longer form a hard candidate boundary. A known page remains a paragraph
   graph seed; a missing page identity does not block global name search.
2. Apply the existing **0.80** acceptance-name threshold and existing person
   type check **before constructing and ranking the paragraph graph**. Weak
   names cannot win graph ranking and then cause a stronger candidate to be
   rejected. This changes candidate eligibility, not the numeric acceptance
   threshold.

The existing Unicode normalization, trigram Dice score, 20 HITS rounds, outgoing
graph depth 1, and positive relative authority gap of at least 0.20 for multiple
candidates remain unchanged. A single eligible candidate is still suggested
even with zero authority, as in the notebook. There is no candidate cap.

**Type scope remains unchanged:** PER requires explicit saved P31=Q5. LOC, ORG,
MISC, and DATE compatibility is assumed; no new type classifier or hierarchy
was introduced. There is no date parser, title-prefix removal, numeric-identity
guard, model call, training label, threshold tuning, live lookup, or manual
override. The original notebook and default batch mode remain available.

## Real examples: repaired and remaining failures

Paragraph numbers below are Daniel's unchanged `Index` values.

| Source / paragraph | Extracted text | Baseline result | Trial result |
|---|---|---|---|
| 14th Indian Infantry Division / 0 | Burma Campaign | No candidate in the page pool | Q221519, Burma Campaign; name 1.00; outside the old page pool |
| 14th Indian Infantry Division / 3 | British Indian Army | Rejected after British Empire won graph ranking | Q642932, British Indian Army; name 1.00 |
| Attack on Pearl Harbor / 13 | Pearl Harbor, in “left port for Pearl Harbor” | Rejected after the attack won graph ranking | Q127091, Pearl Harbor, the place; name 1.00 |
| 1st Mobile Fleet (Imperial Japanese Navy) / 0 | 1st Mobile Fleet | Rejected after 1st Fleet won graph ranking | Q4596490, 1st Mobile Fleet; name 1.00 |
| 14th Indian Infantry Division / 1 | Major General Wilfrid Lewis Lloyd | Unresolved; name 0.71 | Still unresolved; title prefix is not normalized |
| 14th Indian Infantry Division / 0 | 1942–43 | Unresolved | Still unresolved; no date-range normalization |

The wider search also exposes incorrect automatic decisions:

| Source / paragraph | Extracted text | Trial suggestion | Problem |
|---|---|---|---|
| 14th Indian Infantry Division / 3 | 14th Division | Q709183, 5th Division; name 0.86 | Conflicting division number; graph ranking overrides exact-name alternatives |
| 14th Indian Infantry Division / 1 | Western Desert, tagged LOC | Q4019174, Western Desert Force; name 0.80 | A location is linked to a military formation |
| 14th Indian Infantry Division / 2 | Allied, in “Allied military occupation” | Q23681360, Allied | An adjective is linked to a film with an exact name |
| 1939–1940 Winter Offensive / 7 | 1938, in “into the Muslim region in 1938” | Q2629571, 76 mm mountain gun M1938 | A year is linked to a gun |
| Air raids on Darwin, 19 February 1942 / 33 | 2000, in “In 2000, Darwin historian…” | Q663695, R-2000 Twin Wasp | A year is linked to an engine |

The older wrong “14th Indian Infantry Division” to “26th Indian Infantry
Division” suggestion on the 26th Division page, paragraph 3, is now unresolved.
The older film match for “1941” on the Pearl Harbor page, paragraph 10, is also
now unresolved. These isolated observations do not establish overall accuracy.

## What the full output shows

- **53,689 suggestions** use IDs outside the former page pool. Wider retrieval
  has a large effect, but outside-pool status does not validate a suggestion.
- **43,865 suggestions** have an exact normalized name match. The “Allied” film
  example shows why exact names alone do not establish identity.
- **49,241 suggestions** have only one eligible candidate; **23,183** have zero
  HITS authority. Graph evidence is therefore not required for every suggestion.
- **240,283 unresolved mentions** have no candidate passing the current name/type
  rules; **5,659** fail the remaining graph separation rules. Neither count
  proves a defect in extraction or that an entity is unknown.
- Diagnostic flags include **197 DATE**, **513 LOC**, and **713 ORG** suggestions
  whose target has explicit film type Q11424. **2,532 ORG** suggestions have
  different digit sequences between the mention and matched reference name.
  These are audit flags, not an accuracy estimate or a complete error inventory.

The saved reference cache also lacks entity metadata for **Q30 United States,
Q17 Japan, Q183 Germany, and Q145 United Kingdom**. Their saved records here are
explicit `MISSING` markers. Wider retrieval cannot supply names/types for these
IDs. Other historical entities or aliases can still match some country words.
This is a reference-cache gap, separate from Daniel's raw extraction and source
page resolution.

The next work should complete missing reference metadata and add automatic
type/number safeguards before accepting wider-search results. Dates need their
own normalization step. No such changes were added after inspecting this trial.
Unknown-entity handling remains an open issue.

## Reproduce and inspect

```powershell
python GG_Data/entity_resolution/run_notebook_matching.py --wide-search --page-map GG_Data/entity_resolution/runs/source_pages_v0.1.0_20261018/page_map.json --output GG_Data/entity_resolution/runs/all_types_wide_search_v0.2.0_20261018
```

Use a new output directory to rerun; the completed directory is preserved.

[Comparison and raw examples](WIDE_SEARCH_COMPARISON_2026-10-18.json) ·
[Run manifest](runs/all_types_wide_search_v0.2.0_20261018/run_manifest.json) ·
[Full summary](runs/all_types_wide_search_v0.2.0_20261018/summary.json).

The new directory saves every raw row and candidate in `mention_matches.jsonl.gz`,
paragraph graph evidence in `graph_contexts.jsonl.gz`, the full reference metadata
in `entity_metadata.jsonl.gz`, page evidence in `page_context.jsonl.gz`, and mapped
assertions in `mapped_graph.jsonl.gz`. For candidates outside the page pool,
`in_page_pool` is false and `page_context_id` is null. Join their name/type
evidence through `entity_id`, and graph evidence through `graph_context_id`.

Eight focused tests passed. Black, isort with the Black profile, Ruff, and
`git diff --check` passed. The batch reread every saved row and rechecked raw
data, mention IDs, names, scores, person types, context membership, automatic
decisions, counts, and unchanged frozen inputs. A separate comparison checked
all 309,864 raw rows/IDs/source identities and both runs' output hashes. The
decompressed mapped graph is identical, SHA-256
`7c341f00bdb11f64fc00034b5bef7856ea15c7a5d24a58b352c98dc17eef8a88`.
These checks establish reproducibility and rule compliance, not matching accuracy.

Backup status: **Local checkpoint only** after the accompanying commit. Frozen
inputs under `Data/external/` remain ignored; no GitHub push was made.
