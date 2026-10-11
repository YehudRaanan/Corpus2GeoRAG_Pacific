# Adaptive minimal-split POC for `hasPlace`

## Question

Can we start with all pairs for one source relation code and add, at each step,
the field that creates the **fewest new distinct cases**? Stop when another
field adds no useful separation. This replaces the previous fixed field order.
It tests discovery logic, not semantic equivalence or Pacific graph content.

## Input and selection rule

Reuse 317 EventKG `hasPlace` event–entity pairs with a YAGO or DBpedia English
named-graph record. Of these, 101 have at least one same-pair Wikidata `P17`,
`P276`, or `P710` code. The 216 other pairs have no selected code recorded;
they are **unknown**, not negative examples. Keep each pair's full code set,
including multi-code sets.

Available fields are binary presence indicators for each direct event or
object `P31` type and each non-Wikidata EventKG source graph. QIDs of the event
and object are excluded as features. At each step:

1. Try every unused field against the current groups of coded pairs.
2. Keep a field only if it creates at least one new group, **every resulting
   group has at least three pairs from at least two different object QIDs**,
   and fewer pairs remain in groups with mixed recorded code sets.
3. Choose the valid field that adds the **fewest groups**. Break a tie by the
   larger reduction in mixed pairs, then by field name.
4. Repeat until no field meets these conditions.

This support rule makes "adds value" concrete for the small POC. It excludes
splits that merely isolate one event or object. It can also stop before a
different, more complex feature combination becomes useful.

## Result on the 101 coded pairs

| Step | Field selected | New groups | Total groups | Pairs still in mixed groups |
| --- | --- | ---: | ---: | ---: |
| Start | None | — | 1 | 101 |
| 1 | Event is an [invasion (`Q467011`)](https://www.wikidata.org/wiki/Q467011) | 1 | 2 | 96 |
| 2 | Object is an [island (`Q23442`)](https://www.wikidata.org/wiki/Q23442) | 1 | 3 | 93 |
| 3 | Event is a [bombardment (`Q678146`)](https://www.wikidata.org/wiki/Q678146) | 1 | 4 | 90 |

No remaining field meets all three conditions. Eleven coded pairs lie in
consistent, supported groups; **90/101 remain mixed**. The output records the
field choice and reduction at each step in
[`incremental_distinct_summary.json`](incremental_distinct_summary.json).

## New-object check

Five folds hold out whole object QIDs. **Field selection is repeated inside
each training fold**. A rule is applied to a test pair only when its training
group has three or more pairs, two or more object QIDs, and one recorded code
set. The process applied a rule to **8/101** held-out pairs; **7/8** matched
their recorded Wikidata code set. It abstained on **93/101**. One of the eight
applications was wrong. The selected fields differed across folds.

This is a small test of predicting *recorded codes*, not proof that EventKG
`hasPlace` means `P710`, `P17`, or `P276`. EventKG defines `hasPlace` as an
event-location link. Same-pair overlap can include a separate participant
relation. The next method test needs original source statements or cited text
to verify the role of each relation, and must retain the abstain outcome.

Run `python poc/relation_alignment/run_incremental_distinct_poc.py` to
reproduce the result from the saved local pair file.
