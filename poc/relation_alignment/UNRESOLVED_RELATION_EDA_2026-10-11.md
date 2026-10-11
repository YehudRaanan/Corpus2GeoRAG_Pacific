# EDA of unresolved common relations

Date: 2026-10-11

## Result

The common map has **435 source predicate rows** without an
accepted cross-source Level 2 mapping. This EDA uses their saved QID-pair
overlap and stops before text classification.

| EDA status | Source predicates | Source occurrence sum |
|---|---:|---:|
| DIRECTION_AMBIGUITY | 3 | 1,922 |
| LOW_SUPPORT_ONLY | 62 | 7,870 |
| MULTIPLE_TARGETS | 28 | 106,836 |
| NO_QID_PAIR_OVERLAP | 323 | 3,714,068 |
| SINGLE_TARGET_BELOW_MERGE_GATE | 19 | 12,085 |

`Source occurrence sum` counts source records. It is not a count of unique
facts or entities.

**50 predicates** have at least
one supported target option.

## Coverage by source

| Source | No overlap | Low support | One target below gate | Multiple targets | Direction ambiguity |
|---|---:|---:|---:|---:|---:|
| EventKG | 217 | 61 | 19 | 28 | 3 |
| WarSampo | 106 | 1 | 0 | 0 | 0 |

## Option tiers

| Evidence tier | Candidate rows |
|---|---:|
| SINGLE_PAIR_ONLY | 274 |
| SUPPORTED_REVIEW_OPTION | 137 |
| WEAK_REPEATED_OPTION | 140 |

- `SUPPORTED_REVIEW_OPTION`: at least five repeated QID endpoint pairs.
- `WEAK_REPEATED_OPTION`: two to four pairs.
- `SINGLE_PAIR_ONLY`: one pair.
- `MERGE_GATE_WINNER`: passes the complete automatic merge gate.

## Status meaning

- `NO_QID_PAIR_OVERLAP`: the local data has no shared QID endpoint pair for
  this source predicate.
- `LOW_SUPPORT_ONLY`: overlap exists, but every option has fewer than five
  repeated pairs.
- `SINGLE_TARGET_BELOW_MERGE_GATE`: one supported target exists, but it does
  not pass the complete automatic gate.
- `MULTIPLE_TARGETS`: at least two supported Wikidata relation targets exist.
- `DIRECTION_AMBIGUITY`: one target is observed in both directions with at
  least five pairs.
- `READY_SINGLE_TARGET`: one target and direction pass the merge gate.

## Next decision

Review the supported options. Use them as the first classifier choice list only
after confirming that the list has acceptable coverage. Keep weak options as
diagnostic evidence. Predicates with no overlap need more linked data or a
different candidate source.

## Files

- `unresolved_relation_summary.csv`: one row per unresolved source predicate.
- `supported_candidate_options.csv`: repeated options for review.
- `observed_candidate_options.csv`: every observed option, including weak ones.
- `summary.json`: counts and validation flags.
