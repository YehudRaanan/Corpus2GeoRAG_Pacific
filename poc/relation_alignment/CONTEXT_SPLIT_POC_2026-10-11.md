# Context split POC for an unresolved relation group

**Question.** Can graph context separate Wikidata relation codes found on
the same QID pairs as EventKG `hasPlace`? This is a method test on the WWII
task-force population. It does not accept a relation mapping or import data
into the Pacific graph. We chose `hasPlace` because it has many ambiguous
overlaps. The previous WarSampo–EventKG audit had only eight screened
non-Wikidata shared pairs, too few for a data-driven split.

## Data and source check

The completed EventKG `relations_events_base` file has 462 `hasPlace`
event→entity QID pairs in its fused `event_kg` graph. We kept the native
EventKG IDs and the named graphs for each pair. **145/462 have no YAGO or
DBpedia English `hasPlace` record**; only EventKG's Wikidata named graph
supports them. Of those 145, 138 already have a same-pair Wikidata `P17`,
`P276`, or `P710` record. Counting these as independent alignment evidence
would repeat Wikidata data. We exclude the 145 from the main test. A YAGO or
DBpedia named graph is a separate record in EventKG; full independence from
Wikidata's underlying sources is not established.

The main group has 317 pairs and 74 distinct objects. For each pair, the
existing same-direction Wikidata codes are recorded: `P17` (country),
`P276` (location), and `P710` (participant). Nine pairs have more than one
of these codes. Another 216 have none recorded; that means **unknown**, not
false. Only the 101 pairs with at least one recorded code enter the tree
check. The complete case list keeps all 317 pairs.

## Test

1. Make context features from direct Wikidata `P31` types of both objects
   and the EventKG YAGO/DBpedia graph indicators. Exclude the EventKG
   Wikidata graph indicator. Keep features seen on at least 10 pairs: 31
   remain. No same-pair Wikidata relation code is a feature.
2. Cluster all 317 pairs into three groups using these features **without**
   the `P17`/`P276`/`P710` codes.
3. Fit a depth-two tree on the 101 coded pairs to predict the **set of
   recorded codes**. This step is *self-supervised*, since the outcomes are
   existing Wikidata codes. Test with five folds that hold out whole object
   QIDs. Compare with a train-fold most-common-code baseline, then repeat
   with type-only and source-only features.
4. Repeat the tree check on all 462 fused pairs as a source-reuse control.

## Result

| Main test on pairs with a non-Wikidata EventKG graph | Result |
| --- | ---: |
| Pairs / distinct objects | 317 / 74 |
| Pairs with at least one selected Wikidata code | 101 |
| Pairs with no selected code recorded | 216 |
| Pairs with two or three selected codes | 9 |
| Largest object group: [Nazi Germany Q7318](https://www.wikidata.org/wiki/Q7318) | 56/317 pairs |
| Objects typed [historical country Q3024240](https://www.wikidata.org/wiki/Q3024240) | 217/317 pairs |
| Five-fold exact match for recorded code set, tree | 48/101 = 47.5% |
| Same check, type features only | 49.5% |
| Same check, source indicators only | 34.7% |
| Same check, train-fold most common code set | 28.7% |
| Control with all fused pairs, including Wikidata-only links | 189/239 = 79.1% |

The unsupervised clusters are still mixed. The largest contains 230 pairs:
39 `P276`, 20 `P710`, 10 `P17`, some multi-code pairs, and 156 with no
selected code recorded. Clustering alone did not resolve the relation types.

The tree's first split is whether the object has type `Q3024240`, **historical
country**. It then uses a DBpedia English source flag. On the 101 coded
pairs, the five held-out folds range from **0% to 73.7%** exact match. One
fold holds out 23 coded pairs for the Empire of Japan and gets **0/23**. The
tree does not transfer reliably to that unseen object. Type-only features
slightly outperform all features, so the source flag is not a dependable
improvement here.

The tree makes **53 errors** and predicts **no multi-code set**. For example,
[Winter War Q134949](https://www.wikidata.org/wiki/Q134949) →
[Soviet Union Q15180](https://www.wikidata.org/wiki/Q15180) has both `P17`
and `P710` recorded, while the out-of-fold tree predicts only `P710`.
One pair can carry several valid relations. A forced single code loses them.

## Decision

Context features show a real pattern, especially the historical-country
type, but this POC does **not** solve the mapping. The apparent 79.1% result
on all fused pairs is strongly affected by source reuse. The main 47.5%
result measures prediction of **recorded Wikidata code sets**, not semantic
equivalence. Missing codes are not negatives, the largest countries dominate
the pair counts, and a YAGO/DBpedia named graph is not guaranteed to be
independent at its root.

The next method test should focus on the 53 errors, the nine multi-code
pairs, and the 216 uncoded pairs. It needs event roles, relation definitions,
and independent text or source evidence. Its output must permit several
relations or abstention. We should not compile `hasPlace` into an Agent
relation rule from this test.

Run `python poc/relation_alignment/run_context_split_poc.py` for the main
cohort, or add `--include-wikidata-only` for the source-reuse control. Inputs
are the local Wikidata JSONL and completed EventKG V3.2 `events`, `entities`,
and `relations_events_base` files. Outputs are
[`summary.json`](context_split_poc/summary.json),
[`cases.csv`](context_split_poc/cases.csv), and the corresponding
`all_sources_*` control files. The source archive under `Data/external` is
ignored by Git.
