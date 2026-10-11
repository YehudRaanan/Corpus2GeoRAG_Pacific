# Incremental grouping POC for `hasPlace`

## Question

Can adding context fields to one unresolved source predicate produce reusable
groups with one recorded Wikidata relation-code set? This tests the proposed
"add fields until distinct" logic, not relation meaning or Pacific graph data.

## Input and rule

Reuse the 317 EventKG `hasPlace` event–entity QID pairs with a YAGO or DBpedia
English named-graph record from the [context POC](CONTEXT_SPLIT_POC_2026-10-11.md).
Of these, 101 have at least one same-pair Wikidata `P17`, `P276`, or `P710`
record. The other 216 are **unrecorded**, not negative examples, and are not
used to judge code consistency. Keep all recorded codes on a pair as one set.

Group the 101 coded pairs by successively adding the object's direct `P31`
type set, the non-Wikidata EventKG source-graph set, and the event's direct
`P31` type set. Do not include the EventKG Wikidata graph as an independent
source. Require at least three examples with the **same full code set** before
calling a group a candidate rule. As a diagnostic, add both QIDs at the end:
identifiers can make every case distinct without yielding a rule.

For each stage, test candidate rules with five folds that keep every object
QID entirely in either training or test. A rule applies to a test pair only
when its exact group key appeared at least three times in training, all with
the same recorded code set. This is a deliberately strict test of exact
grouping, not a search over all possible features or generalization methods.

## Result

| Fields added | Groups | Single-pair groups | Pairs in mixed groups | Pairs in consistent groups with 3+ examples | Rule applications to held-out objects |
| --- | ---: | ---: | ---: | ---: | ---: |
| None | 1 | 0 | 101 | 0 | 0 |
| Object types | 38 | 27 | 62 | 4 | 0 |
| + source | 48 | 35 | 56 | 0 | 0 |
| + event types | 82 | 72 | 15 | 6 | 0 |
| + event and object QIDs | 101 | 101 | 0 | 0 | 0 |

The four consistent object-type cases all concern Kharkiv (`Q42308`) and
have `P276`. The six consistent cases in the third context stage all concern
the Empire of Japan (`Q188712`) and have `P710`. **None of these groups spans
two different object QIDs.** The five held-out folds therefore apply no
three-example rule to a new object. Zero applications means predictive
accuracy is *undefined*, not zero percent.

## Decision

The proposed grouping is useful to find ambiguous cases. It does not yet
yield a transferable relation-mapping rule. The last row makes all 101 cases
unique by using IDs, but every group is a singleton. More exact fields can
hide ambiguity instead of resolving it. Source overlap also does not prove
that `hasPlace` means `P710`: EventKG defines `hasPlace` as location, and a
pair can have both place and participant relations. A recorded Wikidata code
set is an observation, not a semantic truth label.

The next test should use broader, role-relevant fields (for example, event
role or a sourced text statement), require support across different objects,
and keep an unresolved outcome. It must separately verify the original
`hasPlace` source claim before accepting a location relation.

Run `python poc/relation_alignment/run_incremental_distinct_poc.py` to
reproduce the [machine-readable summary](incremental_distinct_summary.json).
