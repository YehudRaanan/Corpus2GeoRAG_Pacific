# QID-overlap Level 1 inheritance POC

Date: 2026-10-11

## Method

This POC starts with the **650 relations** that have no declared
ontology parent. It matches repeated QID endpoint pairs to Wikidata predicates,
tests same and reverse directions, and then reads the matched Wikidata
predicate's declared parent. It does not change a source relation or accept a
mapping from names alone.

EventKG uses graph, endpoint kind, and relation format as separate contexts.
Its existing name-blind score tests pair coverage, target stability, held-out
stability, and support. WarSampo uses the screened identity overlap and accepts
only at least 20 shared pairs with at least 90% WarSampo and 80% Wikidata
co-connected coverage.

## Result

- EventKG overlap reaches **20 of 271**
  unresolved EventKG relations in **27 contexts**.
- WarSampo overlap reaches **2 of 72** unresolved WarSampo
  relations.
- The run creates **179 inherited Level 1 candidate rows**.
- Only **1 candidate row** for
  **1 relation** passes the automatic
  evidence gate.

The accepted POC case is WarSampo `hasConflict` -> Wikidata `P607` in the same
direction, based on 115 shared pairs. Wikidata declares `P607` under `P1344`
(`participant in`), so `P1344` is a provisional inherited Level 1 value.

EventKG `hasWonPrize` strongly matches `P166` (`award received`) on 409 pairs,
but Wikidata does not declare a parent for `P166`. This produces a strong Level
2 alignment but no inherited Level 1 value.

WarSampo `hasUpperUnit` has three shared pairs with `P361` in the same direction
and `P527` in reverse. Both offer parent candidates, but three pairs are below
the evidence gate. They remain review candidates.

## Coverage result

| Result | Relations |
|---|---:|
| LEVEL1_REVIEW_CANDIDATE | 20 |
| LEVEL2_ONLY_NO_WIKIDATA_PARENT | 1 |
| NO_AVAILABLE_QID_PAIR_OVERLAP | 321 |
| PROVISIONAL_LEVEL1 | 1 |
| REFERENCE_SOURCE_NOT_EVALUATED | 307 |

Wikidata's 307 unresolved properties are marked as the reference source. This
one-way POC cannot create a Wikidata parent when Wikidata itself declares none.

## Limits

- Missing overlap is not evidence that relations differ.
- EventKG facts copied from Wikidata were excluded from the overlap votes.
- WarSampo coverage is limited to identities that passed the earlier QID
  screening.
- An inherited Level 1 is a provisional cross-source mapping. It is not a new
  source ontology assertion.

## Files

- `eventkg_overlap_rankings.csv`: every observed EventKG-Wikidata candidate.
- `eventkg_group_decisions.csv`: the top result for each EventKG context.
- `warsampo_overlap_rankings.csv`: screened WarSampo-Wikidata candidates.
- `level1_candidates.csv`: inherited Wikidata parent options.
- `unresolved_relation_coverage.csv`: one result for each unresolved relation.
- `summary.json`: machine-readable totals.
