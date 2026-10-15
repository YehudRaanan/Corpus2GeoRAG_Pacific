# Reverse Relation Formula Validation

**Date:** 2026-10-15

**Mapping version reviewed:** `relation-map-v2.0.0`

**Graph reviewed:** `wwii-agent-draft-v0.1.0`

## Decision

Use this deterministic reverse rule:

```text
A --P--> B  entails  B --REV(P)--> A
REV(REV(P)) = P
```

The rule is valid for every binary relation when `REV(P)` is an inverse relation expression. It does not require a separately stored reverse edge.

Replace `REV(P)` with a named relation `Q` only when a formal source establishes a single, involutive inverse contract:

```text
REV(P) = Q
REV(Q) = P
```

For a formally symmetric relation:

```text
REV(P) = P
```

Do not select one named reverse when a relation has several non-equivalent inverse targets. Keep the exact `REV(P)` expression until a narrower rule identifies the required target.

## Main result

The validation found 141 normalized relation codes in the v2 catalog that participate in a known formal inverse or symmetry declaration.

| Result at normalized source-code level | Relation codes | Source occurrences |
|---|---:|---:|
| Safe named inverse or symmetric reverse | 130 | 2,753,819 |
| Ambiguous named reverse | 11 | 18,206 |
| **Total** | **141** | **2,772,025** |

After the current v2 translations are applied, these become 103 effective Level 2 relations.

| Result at effective Level 2 | Relations | Source occurrences |
|---|---:|---:|
| Safe named inverse or symmetric reverse | 92 | 2,755,755 |
| Ambiguous named reverse | 11 | 18,206 |
| **Total** | **103** | **2,773,961** |

The effective count is smaller because v2 combines some source identifiers. Its occurrence total is slightly larger because an affected Level 2 component can also contain equivalent source identifiers that do not carry the inverse declaration directly.

The preliminary count of 97 effective relations is superseded by this result. That count treated some multi-target Wikidata inverse declarations as directly usable. The involution check shows that 11 relation codes in three components cannot use one deterministic named reverse.

## Formal evidence reviewed

The test used 131 distinct formal declarations. They mention 172 relation codes in total; 141 of those codes occur in the current catalog.

| Formal source | Catalog relation codes | Catalog occurrences | Formal mechanism |
|---|---:|---:|---|
| CIDOC CRM 7.1.3 | 19 | 2,573,758 | `owl:inverseOf` |
| Wikidata pinned property records | 108 | 150,685 | inverse property `P1696` or `P31=Q18647518` |
| W3C SKOS | 8 | 8,956 | `owl:inverseOf` or `owl:SymmetricProperty` |
| Simple Event Model | 2 | 4,353 | `owl:inverseOf` |
| Schema.org | 1 | 3,122 | `inverseOf` |
| OGC GeoSPARQL 1.1 | 1 | 30,906 | normative `sfWithin`/`sfContains` definitions |
| YAGO3 | 1 | 203 | `owl:SymmetricProperty` |
| Muninn Organization ontology | 1 | 42 | `owl:inverseOf` |
| **Total** | **141** | **2,772,025** | |

The Wikidata test is reproducible against the local cache retrieved at `2026-10-15T06:53:32.197660+00:00`. It does not mix later live Wikidata changes into these results.

Primary definitions:

- [OWL 2 inverse object properties](https://www.w3.org/TR/owl2-syntax/#Inverse_Object_Properties)
- [SPARQL inverse property paths](https://www.w3.org/TR/sparql11-query/#propertypaths)
- [Wikidata data model: inverse property P1696](https://www.wikidata.org/wiki/Help:Data_model)
- [Wikidata symmetric property Q18647518](https://www.wikidata.org/wiki/Q18647518)
- [CIDOC CRM 7.1.3 OWL](https://cidoc-crm.org/owl/7.1.3/CIDOC_CRM_v7.1.3.owl)
- [W3C SKOS rules S8, S23, S25, S43, and S44](https://www.w3.org/TR/skos-reference/)
- [Simple Event Model](https://semanticweb.cs.vu.nl/2009/11/sem/)
- [Schema.org containedInPlace](https://schema.org/containedInPlace)
- [OGC GeoSPARQL 1.1](https://docs.ogc.org/is/22-047r1/22-047r1.html)
- [YAGO3 relation schema](https://raw.githubusercontent.com/yago-naga/yago3/master/schema/relations.ttl)
- [Muninn Organization ontology](https://rdf.muninn-project.org/ontologies/organization.owl)

## Algebraic validation

Define the extension of `REV(P)` as:

```text
REV(P) = {(b, a) | (a, b) is in P}
```

Applying the operation twice gives:

```text
REV(REV(P)) = {(a, b) | (b, a) is in REV(P)} = P
```

The implementation test applied two additional requirements before accepting a named reverse:

1. `P` has exactly one formal reverse candidate `Q`.
2. `Q` has exactly one formal reverse candidate, and it is `P`.

All 130 safe catalog codes passed both checks. The 11 blocked codes failed because their formal component is not single-valued.

## The three ambiguous Wikidata components

### 1. Participant relations

```text
P1344 participant in
  inverse candidates: P710 participant, P1923 participating team
```

`P710` and `P1923` have different scopes. One covers a general participant; the other is specific to teams. A single rule such as `REV(P1344)=P710` would lose valid team meaning. A union would also hide the distinction.

### 2. Creator relations

```text
P170 creator
  inverse candidates: P800 notable work, P3342 significant person
```

The two targets do not have the same meaning. `P800` is a notable work of a person or organization. `P3342` is a significant person connected to an item. Neither is a complete general inverse name for `creator`.

### 3. Facet relations

```text
P1269 facet of
  inverse candidates: P2184 history of topic
                      P2633 geography of topic
                      P8744 economy of topic
                      P9241 demographics of topic
```

These targets describe different kinds of facets. `REV(P1269)` is valid as an expression, but no one target code covers all four meanings.

The 11 codes in these components carry 18,206 source occurrences. V2 currently marks all 11 as having a formal inverse available. That policy is too broad. They need the generic `REV(P)` expression or a scoped rule that uses the exact asserted relation.

## Validation against stored graph assertions

The graph test used `attributes.source_predicate`, not the draft edge family. This avoids the known Level 1 family errors.

For each safe assertion `(A, P, B)`, the test looked for an explicit stored counterpart `(B, REV(P), A)`.

| Graph result | Assertions | Share |
|---|---:|---:|
| Explicit reverse assertion found | 19,174 | 21.82% |
| No explicit reverse assertion stored | 68,701 | 78.18% |
| **Safe assertions tested** | **87,875** | **100.00%** |

The 68,701 missing stored counterparts do not invalidate the formula. The source data often stores only one direction. A query-time reverse view must derive the counterpart from the original assertion.

The test found graph examples for 110 of the 141 catalog relation codes:

| Example coverage | Relation codes |
|---|---:|
| 10 deterministic examples | 78 |
| 1 to 9 examples | 32 |
| No graph example | 31 |
| **Total** | **141** |

The example file records the entity IDs, names, types, graph edge ID, source dataset, and source record ID. Relations with fewer than ten available examples are marked as such.

## Same-direction inverse assertions

The graph contains 24 distinct entity pairs where both a relation and its named inverse are asserted in the same endpoint direction. They account for 50 directed assertion observations. One pair is a self-loop.

| Relation pair | Distinct entity pairs |
|---|---:|
| `sem:hasSubEvent` / `sem:subEventOf` | 2 |
| `P1365` replaces / `P1366` replaced by | 12 |
| `P1542` has effect / `P828` has cause | 2 |
| `P155` follows / `P156` followed by | 6 |
| `P3919` contributed to work / `P767` contributor to work | 2 |
| **Total** | **24** |

Examples include:

- `Operation Weserübung` has both `hasSubEvent` and `subEventOf` to `Norwegian Campaign`, while the graph also carries the opposite endpoint direction.
- `New Mexico-class battleship` has both `follows` and `followed by` to `Nevada-class battleship` in the same direction.
- `Peter-Erich Cremer` has both `contributed to creative work` and `contributor to the creative work` to `The World at War` in the same direction.

These are data-direction review candidates. They are not failures of the reverse formula. Formal inverse logic permits cycles, so endpoint shape alone does not prove a logical contradiction. The relation meaning makes these examples suspicious, and their exact source statement IDs are preserved in `same_orientation_inverse_candidates.csv` for source QA.

## Effect on mapping v2

Of the 92 safe effective Level 2 relations:

| Current v2 handling | Relations | Source occurrences |
|---|---:|---:|
| Formal reverse or symmetric query policy already present | 50 | 1,139,970 |
| Safe formal reverse missing from v2 policy | 42 | 1,615,785 |
| **Total** | **92** | **2,755,755** |

The 42 missing safe relations are:

- 17 CIDOC CRM relations;
- 11 Wikidata relations;
- 8 SKOS relations;
- 2 Simple Event Model relations;
- one each from Schema.org, GeoSPARQL, YAGO3, and Muninn.

The detailed CSV gives every relation, named reverse, formal source, evidence URL, occurrence count, v2 policy, graph coverage, and example coverage.

## Required deterministic query behavior

For every stored assertion, preserve the original subject, relation, object, source record, and direction.

When a query starts from the object side:

1. Read the formal reverse contract for `P`.
2. If the contract is safe and named, return `(B, Q, A)` where `Q=REV(P)`.
3. If `P` is symmetric, return `(B, P, A)`.
4. If the named reverse is ambiguous or absent, return `(B, REV(P), A)` as an explicit inverse expression.
5. Point the derived view to the original assertion and its provenance.
6. Do not ask the Agent or a language model to invent a reverse label.
7. Do not require a second stored edge.

This query view can be implemented with an OWL inverse expression or the SPARQL path `^P`. Materializing reverse edges is optional and would require duplicate-control and provenance rules.

## Artifacts

- `poc/relation_alignment/validate_reverse_formula.py`: reproducible validator.
- `poc/relation_alignment/reverse_formula_validation/summary.json`: aggregate results.
- `poc/relation_alignment/reverse_formula_validation/reverse_contract_validation.csv`: one row per formal relation code.
- `poc/relation_alignment/reverse_formula_validation/reverse_example_validation.csv`: up to ten deterministic graph examples per relation.
- `poc/relation_alignment/reverse_formula_validation/same_orientation_inverse_candidates.csv`: all same-direction inverse review candidates with provenance.

Run from the repository root:

```powershell
python poc/relation_alignment/validate_reverse_formula.py
```

The script checks that explicit-reverse and missing-reverse counts sum to the tested safe assertion count.

## Limits

- The graph is the draft mechanism-QA graph and does not use the Pacific corpus.
- Graph examples validate stored endpoint behavior. They do not prove that every source assertion is factually correct.
- A missing explicit counterpart is expected in one-direction source data.
- Wikidata rules are pinned to the saved cache. A later live Wikidata state can differ.
- The analysis does not use Level 1 families to decide Level 2 meaning.
