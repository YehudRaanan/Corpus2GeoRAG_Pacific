# Source ontology Level 1 to Level 2 map

Date: 2026-10-11

## Result

This run uses only parent relations declared by the public source ontologies and
EventKG's published mapping files. It does not use the earlier project-made 14
families and it does not run a classifier.

The input contains **1,520 source Level 2 rows**. Public ontology or
EventKG mapping evidence supplies at least one Level 1 parent for
**870 rows**. **650 rows** have
no published parent in the checked ontology. **144 rows** have more
than one valid direct parent; these parents remain separate.
The map contains **313 source-specific Level 1 options**
and **204 unique Level 1 parent URIs**.

## Coverage by source

| Source | Level 2 rows | With parent | No parent | Multiple parents | Coverage |
|---|---:|---:|---:|---:|---:|
| EventKG | 808 | 537 | 271 | 74 | 66.46% |
| WarSampo | 111 | 39 | 72 | 5 | 35.14% |
| Wikidata | 601 | 294 | 307 | 65 | 48.92% |

## Evidence types

| Mapping basis | Output edges or unresolved rows |
|---|---:|
| EVENTKG_MANUAL_MAPPING | 20 |
| NO_DECLARED_PARENT | 650 |
| RDFS_SUBPROPERTY | 356 |
| WIKIDATA_P1647 | 558 |
| WIKIDATA_P2235_EXTERNAL | 121 |

## Interpretation

- `WIKIDATA_P1647` is Wikidata's native property hierarchy.
- `WIKIDATA_P2235_EXTERNAL` is an explicit Wikidata link to an external
  superproperty.
- `RDFS_SUBPROPERTY` is a parent declared in DBpedia, YAGO, SEM, WarSampo,
  CIDOC CRM, SKOS, DCMI, Schema.org, OWL, RDFS, or Muninn.
- `EVENTKG_MANUAL_MAPPING` is EventKG's published normalization rule. It is
  separate from a native `rdfs:subPropertyOf` assertion.
- `NO_DECLARED_PARENT` means that the checked public model gives domain/range
  information at most. No Level 1 meaning was invented from the field name.

## Files

- `source_ontology_level1_level2.csv`: one row per declared parent edge, or one
  unresolved row when no parent exists.
- `source_ontology_statistics.csv`: coverage by source.
- `level1_parent_statistics.csv`: each Level 1 option and its Level 2 count.
- `summary.json`: machine-readable totals.

## Next gate

Review this EDA before any classifier is used. The classifier should see only
the `NO_DECLARED_PARENT` population. It must not replace or merge declared
source parents.
