# Unresolved EventKG relation examples

This dataset covers the 164 EventKG predicates whose public-mapping audit has
status `NO_DECLARED_MAPPING_FOUND`.

## Mapping decision

Each unresolved predicate stays as an independent, source-native Level 2
relation. Its Level 2 ID is its EventKG predicate URI. The process does not
force it into a Wikidata relation.

- `unresolved_relation_examples.csv`: up to three local EventKG records for
  each predicate. It includes source graph, endpoint URIs, QIDs, labels, and
  English DBpedia or YAGO links when available.
- `relation_example_coverage.csv`: one row per predicate, with its expected and
  saved example counts.
- `summary.json`: dataset totals and the selection rule.

The examples are evidence for later review or classification. They are not
accepted relation mappings. Source records are unchanged.
