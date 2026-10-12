# Final relation mapping catalog

Date: 2026-10-12

## Result

The catalog contains **1,520 source relation rows** grouped under
**1,051 final Level 2 IDs**. It preserves the original source
predicates and direction.

The final audit decisions cover **217 EventKG relations**:

- 43 public declared exact mappings
- 6 reviewed scoped, conflict, or combined mappings
- 4 automatic mappings kept as provisional
- 164 source relations kept as independent Level 2 relations

## Cross-source decisions added by the final audit

| EventKG source predicate | Final Level 2 ID | Decision | Status |
|---|---|---|---|
| `http://dbpedia.org/ontology/affiliation` | `wd:P1416` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/anthem` | `wd:P85` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/architecturalStyle` | `wd:P149` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/artist` | `wd:P175` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/basedOn` | `wd:P144` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/capital` | `wd:P36` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/colour` | `wd:P462` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/composer` | `wd:P86` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/computingPlatform` | `wd:P400` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/creator` | `wd:P170` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/crewMember` | `wd:P1029` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/crosses` | `wd:P177` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/curator` | `wd:P1640` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/currency` | `wd:P38` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/developer` | `wd:P178` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/diocese` | `wd:P708` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/discipline` | `wd:P101` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/district` | `wd:P131` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/editor` | `wd:P98` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/era` | `wd:P2348` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/homeport` | `wd:P504` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/ideology` | `wd:P1142` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/industry` | `wd:P452` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/inflow` | `wd:P200` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/instrument` | `wd:P1303` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/language` | `wd:P407` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/locatedInArea` | `wd:P131` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/locationCity` | `P276+OBJECT_TYPE_CITY` | ACCEPT_SCOPED_BROADER | ACCEPTED |
| `http://dbpedia.org/ontology/locationCountry` | `P276+OBJECT_TYPE_COUNTRY` | ACCEPT_SCOPED_BROADER | ACCEPTED |
| `http://dbpedia.org/ontology/manager` | `wd:P286` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/material` | `wd:P186` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/mother` | `wd:P25` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/movement` | `wd:P135` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/nextEvent` | `P156+EVENT_TO_EVENT` | ACCEPT_SCOPED_BROADER | ACCEPTED |
| `http://dbpedia.org/ontology/outflow` | `wd:P201` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/owningOrganisation` | `wd:P1830` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/picture` | `wd:P18` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/placeOfBurial` | `wd:P119` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/position` | `wd:P413` | ACCEPT_ONE_REJECT_ONE | ACCEPTED |
| `http://dbpedia.org/ontology/primeMinister` | `wd:P6` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/profession` | `wd:P512` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/province` | `wd:P131` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/recordLabel` | `wd:P264` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/religion` | `wd:P140` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/subsidiary` | `wd:P355` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/team` | `wd:P54` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/translator` | `wd:P655` | PUBLIC_DECLARED_EXACT | ACCEPTED |
| `http://dbpedia.org/ontology/voice` | `wd:P725` | ACCEPT_ONE_REJECT_ONE | ACCEPTED |
| `http://schema.org/containedInPlace` | `COMBINED[P17|P131|P706|P1376|P3018|REV(P36)|REV(P150)|REV(P1383)]` | ACCEPT_COMBINED | ACCEPTED |
| `http://yago-knowledge.org/resource/graduatedFrom` | `wd:P69` | AUTOMATIC_ALIGNMENT | PROVISIONAL |
| `http://yago-knowledge.org/resource/hasCapital` | `wd:P36` | AUTOMATIC_ALIGNMENT | PROVISIONAL |
| `http://yago-knowledge.org/resource/hasCurrency` | `wd:P38` | AUTOMATIC_ALIGNMENT | PROVISIONAL |
| `http://yago-knowledge.org/resource/hasOfficialLanguage` | `wd:P407` | AUTOMATIC_ALIGNMENT | PROVISIONAL |

## Independent relations

The 164 relations with no declared public mapping keep their source predicate
URI as the final Level 2 ID. Their examples and coverage remain in
`unresolved_relation_examples/`.

## Files

- `final_relation_map/final_relation_source_map.csv`: every source relation,
  selection priority, time join rule, evidence policy, conflict policy, and map
  version
- `final_relation_map/final_relation_groups.csv`: one row per final Level 2 ID
- `final_relation_map/audited_eventkg_decisions.csv`: the 217 final audit decisions
- `final_relation_map/summary.json`: validation counts

The source data was not changed.
