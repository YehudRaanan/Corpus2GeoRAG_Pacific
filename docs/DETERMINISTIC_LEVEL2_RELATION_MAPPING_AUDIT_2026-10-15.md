# Deterministic Level 2 Relation Mapping Audit

**Date:** 2026-10-15

**Scope:** GeoAI relation inventory and the current final relation map

**Sources reviewed:** Wikidata, CIDOC CRM, DBpedia Ontology, EventKG, and WarSampo

## Decision

Level 2 relation translation must use only explicit identifiers and formal mapping values from the five reviewed sources.

Relation names, descriptions, graph observations, text similarity, and model judgment must not create a Level 2 mapping. They are validation evidence only. If this validation contradicts a formal mapping, the formal mapping is recorded but blocked from automatic activation.

The current map has 1,520 relation rows:

- 1,449 rows retain the same normalized identifier.
- 71 rows translate, combine, or generalize a relation.
- Of these 71 rows, 48 have an exact or inverse formal path.
- Only 34 of the 48 have no detected semantic or formal-component problem and no contradictory sampled values.
- One additional translation, `dbo:discipline -> wd:P101`, has a plausible formal translation but contradictory assertion values. It needs assertion QA.
- Nine formal mappings lose scope and must remain separate Level 2 relations. They can support an optional broader search view.
- One formal mapping contradicts the relation meaning: `dbo:profession -> wd:P512`.
- Three mappings are inside unsafe formal equivalence components.
- Four mappings have only hierarchy or EventKG broader-view evidence. They are not exact Level 2 translations.
- Nineteen mappings have no deterministic evidence in the five reviewed sources.

No direction conflict was found in the 48 current rows with exact or inverse formal paths. This does not mean that all sources store both directions. The graph normally stores one assertion direction. An inverse declaration can support query rewriting without creating a second stored edge.

## 1. Deterministic mapping contract

The mapping procedure applies these rules in this order.

| Formal value | Level 2 action | Direction |
|---|---|---|
| Same normalized URI or code | Use one identifier | Same |
| `owl:equivalentProperty` or Wikidata `P1628` | Candidate exact translation | Same |
| `owl:inverseOf`, a CIDOC inverse, or Wikidata `P1696` | Candidate exact translation | Reverse |
| Declared symmetric property | Retain one relation and allow reverse traversal | Both |
| `rdfs:subPropertyOf`, Wikidata `P1647`, `P2235`, or `P2236` | Keep both Level 2 identifiers | Parent or child view only |
| EventKG location, containment, or event-part configuration | Keep the source Level 2 identifier | Optional broader view, with the declared direction |
| No formal value | Keep the source Level 2 identifier | No translation |

The procedure does not use:

- relation name similarity;
- relation descriptions;
- shared subject-object pairs;
- observed endpoint types;
- embedding similarity;
- PARIS scores;
- a model-selected category;
- the existing mapping as proof of itself.

Names, descriptions, and assertions are reviewed only after a deterministic candidate exists.

## 2. Source results

The audit collected 1,508 formal evidence rows.

| Source | Version or snapshot | Evidence rows | Evidence found | Level 2 use |
|---|---|---:|---|---|
| Wikidata | Live property entities retrieved 2026-10-15; statement IDs saved | 961 | 392 equivalent, 96 inverse, 328 subproperty, 140 external hierarchy, 5 symmetric | Exact or inverse candidates and separate hierarchy views |
| CIDOC CRM | 7.1.3; downloaded OWL hash saved | 34 | 19 inverse, 15 subproperty | One observed CIDOC inverse connection; no reviewed CIDOC-to-Wikidata exact translation |
| DBpedia Ontology | Public endpoint latest snapshot | 435 | 120 equivalent, 315 subproperty | Exact candidates and separate hierarchy views |
| EventKG | Commit `0face5765ffc3e16a8746f9ed98877dc86de2bef` | 61 | Manual location, containment, and event-part normalization | Broader search views only |
| WarSampo | 2.1.0 archive and schema | 17 | 17 subproperty statements | Separation evidence; no observed exact cross-source translation |

### Source conclusions

1. **Wikidata provides many deterministic values, but some values are too loose for unrestricted transitive merging.** `P1696` can list more than one inverse with different scope. `P1628` can also connect two relations through an overly broad external property.
2. **CIDOC CRM provides a clear internal inverse and hierarchy structure.** It does not provide the current cross-source translations from CIDOC `P10`, `P11`, or `P7` to Wikidata.
3. **DBpedia provides useful exact declarations.** Some declarations remove domain or object-class scope. Formal presence alone is therefore not enough for automatic activation.
4. **EventKG provides deterministic normalization rules.** These rules intentionally combine narrower relations into broad views. They must not replace the original Level 2 meaning.
5. **WarSampo provides internal hierarchy evidence.** The reviewed schema does not provide formal evidence for the current WarSampo-to-Wikidata translations.

The input releases and the mapping sources are not fully time-aligned. The EventKG configuration is pinned to a commit, CIDOC and WarSampo are pinned releases, but Wikidata and DBpedia were read from current services. Production use needs a versioned snapshot tied to the input data release.

## 3. Full deterministic connection result

The 1,520 inventory rows produced 828 source-row connections. After duplicate source-row combinations were removed, there are 589 unique relation-pair connections:

- 403 use the same normalized identifier.
- 186 connect different identifiers through an explicit equivalent or inverse path.
- Of the 186 cross-identifier connections, 113 use the same direction and 73 use reverse direction.

The 403 same-identifier connections received a separate full validation. All are EventKG-to-Wikidata pairs with the same `wd:Pxx` property ID. They need no cross-identifier translation rule. EventKG has no description for these rows. Of their labels, 381 match exactly, 9 are wording variants, and 13 omit or change part of the current Wikidata scope. The review inspected 3,228 assertions and found at least one clear assertion contradiction for 24 relations. These are assertion-quality failures and do not invalidate the shared property identity. See `docs/SAME_IDENTIFIER_RELATION_VALIDATION_2026-10-15.md` and the four `same_identifier_*` evidence files.

The semantic validation of the 186 cross-identifier connections found:

| Name and description result | Unique connections |
|---|---:|
| No contradiction found | 126 |
| Partial scope; not exact | 30 |
| Contradicts exact translation | 20 |
| Pair looks valid, but its formal component is unsafe | 10 |

Some rows overlap in the final activation result because an unsafe component can contain both valid and invalid pairs. The activation result is:

| Activation result | Unique connections |
|---|---:|
| Ready deterministic translation | 513, including same-identifier connections |
| Translation valid; assertion QA required | 2 |
| Keep separate; optional broader view | 21 |
| Blocked by formal component conflict | 49 |
| Blocked by semantic contradiction | 4 |

Descriptions are sparse. For the 186 cross-identifier connections, both descriptions exist for 3 connections, one description exists for 19, and neither description exists for 164. The review therefore relies mainly on relation names and the formal source statement. This limit is recorded in the connection table.

## 4. Current mapping audit

### 4.1 Formal translation with no detected mapping problem

Thirty-four current cross-identifier mappings can remain deterministic translations. The complete evidence path and example result are in `current_mapping_audit.csv`.

`affiliation`, `anthem`, `architecturalStyle`, `author`, `award`, `basedOn`, `capital`, `colour`, `composer`, `computingPlatform`, `crewMember`, `crosses`, `curator`, `currency`, `developer`, `diocese`, `editor`, `homeport`, `ideology`, `industry`, `inflow`, `instrument`, `material`, `mother`, `movement`, `outflow`, `owningOrganisation`, `placeOfBurial`, `position`, `recordLabel`, `religion`, `subsidiary`, `team`, and `translator` have formal paths to their current Wikidata targets.

Only `author -> P50` and `award -> P166` also had an expected counterpart pair in the sampled graph assertions. For 15 mappings, examples existed but no cross-source counterpart pair occurred. For 17 mappings, no graph example was available. Missing counterpart assertions do not contradict a formal mapping because the sources have incomplete and different coverage.

### 4.2 Translation valid, assertion values need QA

| Current mapping | Formal result | Example result | Action |
|---|---|---|---|
| `dbo:discipline -> wd:P101` | DBpedia declares equivalence | Sampled people point to `Schutzstaffel` or `World War II` as their discipline or field of work | Keep the translation; quarantine or correct the bad assertions |

This is an assertion-value problem. It is not evidence against the relation translation.

### 4.3 Formal mapping exists, but exact meaning is narrower or broader

These nine current mappings have formal evidence, but the names or scope show that exact Level 2 replacement loses meaning.

| Current mapping | Semantic problem | Action |
|---|---|---|
| `dbo:artist -> wd:P175` | Artist is broader than performer | Keep separate; add broader view if useful |
| `dbo:battle -> wd:P607` | Battle is narrower than conflict | Keep separate; add broader view |
| `dbo:district -> wd:P131` | District adds an administrative class restriction | Keep separate |
| `dbo:era -> wd:P2348` | Era is narrower than general time period | Keep separate |
| `dbo:language -> wd:P407` | `P407` is limited to language of a work or name | Keep separate; sampled values also contain countries or regimes |
| `dbo:locatedInArea -> wd:P131` | The DBpedia relation and Wikidata administrative relation do not have identical scope | Keep separate |
| `dbo:manager -> wd:P286` | Manager can be broader than head coach | Keep separate |
| `dbo:primeMinister -> wd:P6` | Prime minister is a subtype of head of government | Keep separate |
| `dbo:province -> wd:P131` | Province adds an administrative class restriction | Keep separate |

These cases show an agreement between the formal merge evidence and a broader search concept, but a contradiction with the requirement that Level 2 preserve exact meaning.

### 4.4 Formal mapping and semantic contradiction

| Current mapping | Formal path | Contradiction | Example result | Action |
|---|---|---|---|---|
| `dbo:profession -> wd:P512` | DBpedia links `profession` through GND `academicDegree`; Wikidata maps `P512` to that value | Profession and academic degree are different concepts | Sampled values are organizations instead of professions or degrees | Block the translation and keep `dbo:profession` |

The deterministic source path is real. The path is not a valid exact semantic translation. The audit records the path and blocks its activation. It does not select a replacement from names or examples.

### 4.5 Unsafe formal equivalence components

Six formal components contain distinct Wikidata relations on the same side of an equivalence or inverse chain. There is no parity contradiction. The problem is semantic: transitive closure merges different meanings.

| Component | Formal cause | Result |
|---|---|---|
| `P710` participant | `P1344` declares both `P710` and narrower `P1923` as inverse | `participant` and `participating team` become equal |
| `P170` creator | `P170` declares both `P800` and `P3342` as inverse | `notable work` and `significant person` become equal |
| `P1269` facet of | Economy, geography, demographics, and history each declare `P1269` as inverse | Four distinct topic facets become equal |
| `P725` voice actor | DBpedia `voice` links to `P990`; Wikidata `P725` also links to DBpedia `voice` | `P725` and `P990` become equal |
| `P176` manufacturer | `P176` and `P195` both declare `schema:provider` as equivalent | Manufacturer and collection become equal |
| `P53` family | `P463` and `P53` both declare vCard `org` as equivalent | Organization membership and family become equal |

Three current mappings are inside these components:

- `dbo:creator -> wd:P170`
- `dbo:manufacturer -> wd:P176`
- `dbo:voice -> wd:P725`

Each direct pair can look reasonable. Automatic transitive component merging is unsafe. These mappings must remain blocked until the mapping engine can use reviewed direct links without inheriting unrelated links through a shared external property or a non-exclusive inverse value.

### 4.6 Hierarchy or broader-view evidence only

Four current mappings agree with a broader view but do not support exact Level 2 replacement:

| Source relation | Current target | Evidence | Action |
|---|---|---|---|
| `dbo:locationCity` | `P276 + city constraint` | DBpedia subproperty path to general location and Wikidata location | Preserve `locationCity`; derive a `P276` search view |
| `dbo:locationCountry` | `P276 + country constraint` | DBpedia subproperty path to general location and Wikidata location | Preserve `locationCountry`; derive a `P276` search view |
| `dbo:nextEvent` | `P156 + event constraint` | DBpedia hierarchy to followed-by | Preserve `nextEvent`; derive a broader sequence view |
| `sem:hasPlace` | `wd:P276` | EventKG broad location normalization | Preserve `sem:hasPlace`; use `P276` only as an optional view |

This finding also addresses the possible geo problem. A country-scale `P276` value can be a valid broad location assertion, but it is not an exact answer to a specific place question. The source relation, object scale, and more specific relation must remain available.

### 4.7 No deterministic mapping evidence

Nineteen current mappings have no exact, inverse, hierarchy, or applicable EventKG mapping value that supports the current replacement. Under the deterministic rule, each source identifier must remain separate.

**DBpedia to Wikidata:**

- `militaryBranch -> P241`
- `nonFictionSubject -> P921`
- `operator -> P137`
- `origin -> P495`
- `picture -> P18`
- `restingPlace -> P119`
- `usedInWar -> P607`

**EventKG combined or SEM relations:**

- `schema:containedInPlace -> COMBINED[P17|P131|P706|P1376|P3018|REV(P36)|REV(P150)|REV(P1383)]`
- `sem:hasSubEvent -> P527`
- `sem:subEventOf -> P361`

**YAGO relations:**

- `graduatedFrom -> P69`
- `hasCapital -> P36`
- `hasCurrency -> P38`
- `hasOfficialLanguage -> P407`
- `hasWonPrize -> P166`

The prior PARIS scores and observed overlap are not deterministic mapping values.

**WarSampo and CIDOC relations:**

- `warsa:hasConflict -> P607`
- `CIDOC P10 falls within -> P361`
- `CIDOC P11 had participant -> P710`
- `CIDOC P7 took place at -> P276`

The relation names can appear compatible. The reviewed formal files do not declare these cross-source translations. Name compatibility is not enough to merge them.

## 5. Ten-example validation

### Method

For every deterministic connection between two different identifiers, the audit selected up to ten distinct graph assertions. Selection is stable and reproducible from a SHA-256 ordering of:

- connection ID;
- relation side;
- source entity ID;
- target entity ID.

Duplicate copies of the same source-relation-subject-object fact are counted once. A sample can come from either side of the proposed mapping.

For each sampled assertion, the audit checks whether the other relation contains:

- the same subject-object pair for a same-direction mapping; or
- the reversed object-subject pair for an inverse mapping.

It also records endpoint names and types for semantic inspection. The graph does not contain the source sentence for these assertions. Therefore, names and broad entity types can expose clear errors, but they cannot prove every assertion correct.

### Coverage

For the 186 unique cross-identifier connections:

- 100 connections have ten distinct examples.
- 86 connections have fewer than ten examples.
- Of those 86, 43 have no examples.
- 38 connections have at least one expected counterpart pair in the sample.
- 96 have examples but no counterpart pair.
- 43 have no examples.
- 9 have a clear contradiction in sampled values.

The 186 unique cross-identifier connections use 1,179 representative sample rows. `connection_examples.csv` has 6,697 rows across all source-row connections, including 3,469 cross-identifier rows. Source-row connections can repeat a relation pair across inventory rows.

### Important example findings

| Connection | What the examples show | Interpretation |
|---|---|---|
| `dbo:author -> P50` | Expected pairs occur on both relations | Mapping agreement |
| `dbo:award -> P166` | Expected pairs occur on both relations | Mapping agreement |
| `P361 <-> P527` | Many reversed counterpart pairs occur | Inverse direction works |
| `dbo:discipline -> P101` | People point to `Schutzstaffel` or `World War II` | Translation can be valid while assertion values are bad |
| `dbo:language -> P407` | Works point to `Nazi Germany` or `Empire of Japan` rather than language entities | Bad assertion values and scope loss |
| `dbo:genre -> P136` | People point to `World War II` as genre | Bad assertion values |
| `dbo:profession -> P512` | People point to organizations; the relation names also disagree | Mapping and assertion contradiction |
| `P195 collection` with `P176 manufacturer` | Collection examples point to museums; manufacturer examples point to builders | Formal component merge is wrong |
| `P463 member of` with `P53 family` | Membership examples point to the Schutzstaffel | Formal component merge is wrong |

A missing counterpart pair is not a contradiction. It means that the second source did not assert the same fact in this graph. A contradiction is recorded only when the relation meaning or a sampled value conflicts with the proposed exact translation.

## 6. Direction and bidirectionality

The five sources do not require every entity pair to contain two stored assertions.

- Wikidata usually stores one statement. `P1696` can declare an inverse relation, but both statements do not need to exist for every entity pair.
- DBpedia can declare `owl:inverseOf`, but datasets can still materialize only one direction.
- CIDOC CRM defines inverse property names. An implementation can store one direction and infer or query the other.
- EventKG configuration includes explicit same or reverse normalization values. For containment, `P36`, `P150`, and `P1383` require reversal in the reviewed configuration.
- WarSampo uses RDF properties and hierarchy declarations. It does not guarantee paired reverse assertions.

The recommended graph rule is to store the source assertion once, preserve its source predicate and direction, and use the deterministic registry to rewrite a query. Materializing both directions would add duplicate facts and make provenance harder to follow.

## 7. Implementation conclusion

Use two separate layers:

1. **Level 2 source-preserving relation registry**
   - Preserve every source predicate.
   - Add a translated canonical relation only for an accepted exact or inverse formal path.
   - Store the evidence statement, source version, and direction.
   - Block unsafe components and semantic contradictions.

2. **Optional Level 1 search views**
   - Add broader location, containment, event-part, or relation-family views.
   - Keep the original Level 2 relation and constraints.
   - Do not use the broader view as the stored exact relation.

When no mapping value exists, the correct result is `unmapped`, not a model-selected translation. When formal merge evidence conflicts with semantics or examples, preserve both identifiers and record the conflict. When assertion values fail but the mapping is sound, keep the translation and quarantine the assertions.

## 8. Generated evidence files

All generated files are in `poc/relation_alignment/deterministic_level2_mapping/`.

| File | Purpose |
|---|---|
| `formal_mapping_evidence.csv` | Every collected formal statement, source, version, statement ID, action, and direction |
| `deterministic_connections.csv` | Every source-row connection, exact path, semantic review, example review, and activation result |
| `deterministic_relation_registry.csv` | Proposed deterministic Level 2 identifier and direction for each inventory row |
| `current_mapping_audit.csv` | Audit of all 1,520 current mapping rows |
| `separation_and_broader_view_evidence.csv` | Hierarchy and EventKG evidence that requires separation or an optional broad view |
| `formal_component_conflicts.csv` | The six unsafe formal equivalence components and their trigger statements |
| `connection_examples.csv` | Up to ten distinct graph examples for every source-row connection |
| `summary.json` | Counts, source versions, hashes, and method flags |
| `wikidata_mapping_source_cache.json` | Retrieved Wikidata entities used in this run |
| `same_identifier_pair_validation.csv` | Formal, text, and sample validation for all 403 same-identifier connections |
| `same_identifier_example_validation.csv` | All 3,228 resolved examples used in the same-identifier review |
| `same_identifier_entity_metadata.json` | Saved Wikidata labels and descriptions for 4,710 sampled endpoint QIDs |
| `same_identifier_validation_summary.json` | Counts, method, and limits for the same-identifier review |

The main builder is `poc/relation_alignment/build_deterministic_level2_mapping.py`. The same-identifier validator is `poc/relation_alignment/validate_same_identifier_connections.py`. They record that labels, descriptions, and observations were not used to create mappings.

## 9. Source references

- Wikidata mapping properties: `P1628`, `P1696`, `P1647`, `P2235`, and `P2236`
- DBpedia Ontology: <https://www.dbpedia.org/resources/ontology/>
- CIDOC CRM official releases: <https://cidoc-crm.org/get-last-official-release>
- EventKG source and configuration: <https://github.com/sgottsch/eventkg>
- WarSampo 2.1.0 source archive: <https://zenodo.org/records/3611322>
