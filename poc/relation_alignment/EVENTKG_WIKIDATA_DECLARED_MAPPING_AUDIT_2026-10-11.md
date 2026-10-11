# EventKG-Wikidata declared mapping audit

## Result

The pair-overlap test missed published schema mappings.

- Scope: **217** EventKG Level 2 predicates with no local QID-pair overlap, covering **9,207** observations.
- A published exact, grouped, broader/narrower, or automatic candidate exists for **53** predicates and **5,359** observations.
- **43** predicates have one declared exact Wikidata target.
- **2** predicates have conflicting exact targets.
- **1** EventKG predicates combine several Wikidata source properties.
- **4** predicates have only an EventKG-used PARIS candidate.
- **3** predicates have only a broader or narrower ontology path.
- **164** predicates still have no published mapping found by this audit.

Do not merge all candidates as exact mappings. Add the single exact mappings to the review queue. Keep conflicts, grouped mappings, and broader mappings as allowed options.

## Highest-volume recovered cases

| EventKG Level 2 | Observations | Result | Wikidata option(s) |
| --- | ---: | --- | --- |
| contained In Place | 3122 | NORMALIZED_MULTI_OPTION | P131, P1376, P1383, P150, P17, P3018, P36, P706 |
| graduated From | 355 | AUTOMATIC_ALIGNMENT_CANDIDATE | P69 |
| ideology | 323 | DECLARED_EXACT_SINGLE | P1142 |
| homeport | 234 | DECLARED_EXACT_SINGLE | P504 |
| language | 148 | DECLARED_EXACT_SINGLE | P407 |
| team | 141 | DECLARED_EXACT_SINGLE | P54 |
| creator | 122 | DECLARED_EXACT_SINGLE | P170 |
| profession | 83 | DECLARED_EXACT_SINGLE | P512 |
| voice | 58 | DECLARED_EXACT_CONFLICT | P725, P990 |
| industry | 52 | DECLARED_EXACT_SINGLE | P452 |
| capital | 47 | DECLARED_EXACT_SINGLE | P36 |
| affiliation | 46 | DECLARED_EXACT_SINGLE | P1416 |
| colour | 41 | DECLARED_EXACT_SINGLE | P462 |
| composer | 40 | DECLARED_EXACT_SINGLE | P86 |
| religion | 33 | DECLARED_EXACT_SINGLE | P140 |
| currency | 30 | DECLARED_EXACT_SINGLE | P38 |
| position | 30 | DECLARED_EXACT_CONFLICT | P1545, P413 |
| location City | 29 | BROADER_OR_NARROWER_ONLY | P276 |
| has Official Language | 29 | AUTOMATIC_ALIGNMENT_CANDIDATE | P407 |
| movement | 28 | DECLARED_EXACT_SINGLE | P135 |

`schema:containedInPlace` is a special case. EventKG creates it from eight Wikidata properties. Five keep direction (`P131`, `P706`, `P17`, `P1376`, `P3018`). Three reverse direction (`P150`, `P36`, `P1383`). The final EventKG base triple does not keep the original property ID. The endpoint types and text must select the source meaning.

## Conflicts

- `http://dbpedia.org/ontology/position` has exact targets `P1545`, `P413`. Keep it unresolved.
- `http://dbpedia.org/ontology/voice` has exact targets `P725`, `P990`. Keep it unresolved.

## Evidence paths checked

1. Wikidata `P1628`, `P2235`, and `P2236` external property mappings.
2. DBpedia `owl:equivalentProperty` declarations to Wikidata.
3. DBpedia equivalence to another public ontology, followed by a Wikidata mapping to that ontology.
4. DBpedia `rdfs:subPropertyOf` paths to a property mapped to Wikidata.
5. EventKG's manual Wikidata-to-`schema:containedInPlace` mapping.
6. The YAGO-DBpedia PARIS mappings that EventKG accepts at score 0.51 or higher.

Time mappings were not added. Dates are relation attributes in this project.

## Version limit

The local EventKG V3.2 data uses Wikidata **2023-02-27** and DBpedia **2022-12-01** snapshots. The Wikidata and DBpedia ontology services were queried when this report was generated. A current declaration can postdate the EventKG snapshot. Keep the source URL and retrieval time with every accepted mapping.

## Files

- `eventkg_wikidata_declared_mapping_audit/predicate_audit.csv`: one row per audited EventKG predicate.
- `eventkg_wikidata_declared_mapping_audit/mapping_candidates.csv`: every declared mapping path and direction.
- `eventkg_wikidata_declared_mapping_audit/summary.json`: counts and source versions.
