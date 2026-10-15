# Relation Mapping Table v2

**Date:** 2026-10-15

**Version:** `relation-map-v2.0.0`

## Decision

Mapping Table v2 covers all 1,520 eligible source-relation rows.

- A Level 2 identity or translation uses only the same normalized code or an explicit formal mapping path.
- Level 1 is an optional search view. A ranked model candidate is never promoted to an active family.
- An opposite direction is a query rewrite rule. The graph stores one source assertion and does not create a duplicate reverse edge.

The v2 output has two main tables:

1. `RELATION_MAPPING_TABLE_v2.0.0.csv` has one row for every source relation and its assertion count.
2. `RELATION_CONNECTIONS_v2.0.0.csv` has one row for each of the 589 deterministic relation connections.

## 1. The 589 deterministic connections

| Connection type | Connections | Source logic |
|---|---:|---|
| Same normalized code | 403 | Both source rows use the same normalized Wikidata property ID |
| Formal cross-identifier connection | 186 | An explicit equivalence or inverse path connects different identifiers |
| **Total** | **589** | |

Every connection row records:

- both relation identifiers, labels, and source datasets;
- source-relation and assertion counts on both sides;
- the deterministic source logic;
- the formal path, evidence source, and evidence URL;
- the direction;
- the proposed canonical Level 2 relation;
- the accepted, blocked, or keep-separate decision;
- the Level 1 search view status;
- the reverse-query policy.

### Same-code decisions

All 403 same-code connections retain the shared property ID. Fourteen of these properties are inside unsafe wider formal components. Their same-code identity remains valid, while the unsafe transitive connections remain blocked.

### Cross-identifier decisions

The 186 cross-identifier connections are not all accepted translations.

| Decision | Connections |
|---|---:|
| Accept formal translation | 124 |
| Accept translation; assertion QA required | 2 |
| Keep separate; optional Level 1 search view | 21 |
| Block because the formal component is unsafe | 35 |
| Block because the meanings contradict | 4 |
| **Total** | **186** |

Of the 186 connections, 113 have the same direction and 73 have reverse direction.

## 2. Coverage of all 1,520 source relations

The 589 connection rows involve 918 distinct source-relation rows. The other 602 source-relation rows do not connect to another relation in the current inventory.

| Coverage type | Source-relation rows | Source assertions |
|---|---:|---:|
| Same-code connection only | 528 | 342,887 |
| Same-code and formal connections | 278 | 910,814 |
| Formal connection only | 112 | 1,144,587 |
| Formal target exists outside the inventory | 1 | 319 |
| No connection; retain source identifier | 601 | 3,219,044 |
| **Total** | **1,520** | **5,617,651** |

The single external-target case is `wd:P1424` (*topic has template*). Wikidata formally declares it inverse to `wd:P1423` (*template's main topic*). `P1423` is not an observed source relation in this inventory, but the formal inverse rule is recorded in v2.

The 602 rows outside the 589 connection set carry 3,219,363 source assertions. Their source distribution is:

| Source | Relation rows | Source assertions |
|---|---:|---:|
| EventKG | 311 | 118,856 |
| WarSampo | 108 | 3,095,528 |
| Wikidata | 183 | 4,979 |
| **Total** | **602** | **3,219,363** |

`source_occurrence_count` in the v2 table gives the count for every individual relation row. These are source assertion counts. They are not deduplicated facts across datasets.

## 3. Level 1 connection

Level 1 can be connected as an optional broad search view. It must remain separate from the deterministic Level 2 decision.

After accepted Level 2 mappings and keep-separate decisions are applied, v2 contains 1,009 effective Level 2 relations:

| Level 1 status | Effective Level 2 relations |
|---|---:|
| One non-conflicting existing catalog family | 215 |
| Unresolved; ranked candidates require review | 794 |
| **Total** | **1,009** |

The v2 fields are:

- `level1_family`: active only when one existing catalog family is available without conflict;
- `level1_assignment_status`: distinguishes an existing assignment from review-required output;
- `level1_candidates`: preserves candidate families without activating them;
- `level1_use`: always `OPTIONAL_SEARCH_VIEW_ONLY`.

This design permits a search for broad concepts such as spatial, participation, or organization hierarchy while preserving the exact Level 2 property used by the source.

### Level 1 view for the 602 relations outside the connection set

| Active Level 1 family | Relation rows | Source assertions |
|---|---:|---:|
| AFFILIATION_STATUS | 9 | 190,096 |
| AWARD_RECOGNITION | 2 | 10,370 |
| CAUSAL | 1 | 6 |
| CONFLICT_AFFILIATION | 3 | 19,104 |
| CREATION_AUTHORSHIP | 5 | 3,745 |
| EDUCATION_EMPLOYMENT | 4 | 530 |
| FAMILY_PERSONAL | 5 | 530 |
| FORMATION_DISSOLUTION | 8 | 491,355 |
| ORGANIZATION_HIERARCHY | 5 | 3,664 |
| OWNERSHIP_CONTROL | 1 | 927 |
| PARTICIPATION_ROLE | 28 | 759,227 |
| PART_WHOLE_HIERARCHY | 7 | 38,112 |
| SPATIAL | 29 | 353,747 |
| TEMPORAL_SUCCESSION | 2 | 674 |
| UNRESOLVED | 493 | 1,347,276 |
| **Total** | **602** | **3,219,363** |

The 493 unresolved rows have ranked candidates in the table, but these candidates are not active Level 1 mappings.

## 4. Opposite direction

V2 uses three deterministic policies.

### Formal inverse

When a formal inverse is accepted, the query layer swaps subject and object and uses the mapped Level 2 relation. V2 records:

- `direction_to_level2=reverse`;
- the inverse relation ID;
- the formal evidence path;
- `reverse_query_policy=QUERY_REWRITE_TO_LEVEL2_AND_SWAP_ENDPOINTS`.

There are 71 accepted reverse source-relation rows. The 73 reverse cross-identifier connections include 52 accepted inverse connections and 21 connections that remain blocked or separate.

### Symmetric property

For the five symmetric Wikidata properties, a query can traverse the same relation in either direction. V2 records `ALLOW_SAME_RELATION_REVERSE_SYMMETRIC`.

### No formal opposite relation

For other directional relations, the system can search incoming edges, but it must retain the original predicate and direction. It must not present the incoming edge as a formally defined inverse relation.

No reverse edge is materialized. This avoids duplicate assertions and preserves source provenance.

## 5. Effective Level 2 rule

V2 applies the formal canonical Level 2 identifier only when the translation is accepted.

- Accepted exact or inverse mapping: use the deterministic canonical ID and direction.
- Assertion QA required: use the mapping, but flag its assertions for QA.
- Partial scope: keep both Level 2 identifiers and allow only an optional Level 1 view.
- Formal component conflict: retain the source identifier.
- Semantic contradiction: retain the source identifier.
- No connection: retain the source identifier.

This rule produces 1,009 effective Level 2 relations. It prevents blocked formal paths from silently changing a source relation.

## 6. Files

| File | Purpose |
|---|---|
| `GG_Data/mapping/RELATION_MAPPING_TABLE_v2.0.0.csv` | All 1,520 source-relation rows, counts, decisions, Level 1 status, and reverse policy |
| `GG_Data/mapping/RELATION_CONNECTIONS_v2.0.0.csv` | All 403 same-code and 186 cross-identifier connections with their source logic |
| `GG_Data/mapping/RELATION_MAPPING_COVERAGE_v2.0.0.csv` | Coverage categories and assertion totals |
| `GG_Data/mapping/RELATION_MAPPING_V2_SUMMARY.json` | Machine-readable counts and policies |

The reproducible builder is `poc/relation_alignment/build_relation_mapping_v2.py`.
