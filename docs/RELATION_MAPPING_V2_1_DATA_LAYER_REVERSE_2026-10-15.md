# Relation Mapping v2.1: Data-Layer Reverse Relations

**Date:** 2026-10-15

**Version:** `relation-map-v2.1.0`

**Scope:** Deterministic reverse-direction delivery for all effective Level 2 relations

## Decision

The Agent does not calculate an inverse relation and does not interpret a reverse formula.

The data layer returns a complete directional assertion with:

- the resolved subject;
- an explicit relation ID;
- an explicit relation label;
- the resolved object;
- the original assertion and provenance.

The formula used to validate the relation catalog remains an audit rule. It is not an Agent instruction.

## Outputs

| File | Purpose |
|---|---|
| `GG_Data/mapping/RELATION_MAPPING_TABLE_v2.1.0.csv` | Source-to-Level-2 mapping plus the complete reverse output contract |
| `GG_Data/mapping/RELATION_DIRECTION_CATALOG_v2.1.0.csv` | One reverse-direction decision for each effective Level 2 relation |
| `GG_Data/mapping/RELATION_MAPPING_V2_1_SUMMARY.json` | Counts and acceptance results |
| `poc/relation_alignment/build_relation_mapping_v2_1.py` | Reproducible standard-library builder and assertions |

The v2.0 artifacts remain unchanged.

## Results

The input mapping has 1,520 source-relation rows, 1,009 effective Level 2 relations, and 5,617,651 source occurrences.

Every effective Level 2 relation now has a non-empty reverse relation ID and label.

| Reverse resolution | Level 2 relations | Source occurrences |
|---|---:|---:|
| Formal named inverse | 83 | 2,741,980 |
| Formal symmetric relation | 9 | 13,775 |
| Synthetic inverse | 917 | 2,861,896 |
| **Total** | **1,009** | **5,617,651** |

The 917 synthetic inverses contain two different evidence states:

| State | Relations | Action |
|---|---:|---|
| More than one formal named inverse candidate | 11 | Block the named choice and return a synthetic inverse |
| No available formal named inverse | 906 | Return a synthetic inverse |

For the 92 safe formal relations, v2.1:

- preserves 50 relations already handled in v2.0;
- activates 42 formal relations missed by v2.0.

## Deterministic resolution rules

The builder uses the validated formal relation graph. It does not use relation-name similarity, descriptions, embeddings, a classifier, or a language model to select a reverse relation.

### 1. Unique formal named inverse

If the formal relation graph supplies one inverse and the pair is involutive, the data layer uses that exact relation ID.

Example:

```text
forward: wd:P1365  "replaces"
reverse: wd:P1366  "replaced by"
```

### 2. Formal symmetric relation

If the relation is formally symmetric, the reverse ID and label are the same as the forward ID and label. The endpoints are still swapped in the returned assertion.

Example:

```text
forward: wd:P47  "shares border with"
reverse: wd:P47  "shares border with"
```

### 3. Ambiguous formal named inverse

If the formal source supplies more than one inverse candidate, v2.1 does not choose one.

Example:

```text
forward:    wd:P1344          "participant in"
candidates: wd:P1923 | wd:P710
reverse:    inverse:wd:P1344  "inverse of participant in"
```

The candidates remain in `formal_reverse_candidate_ids` for audit. They are not active reverse mappings.

### 4. No formal named inverse

If no formal named inverse is available, v2.1 creates a deterministic synthetic ID and label.

Example:

```text
forward: wd:P607          "conflict"
reverse: inverse:wd:P607  "inverse of conflict"
```

The synthetic relation preserves the exact direction without claiming equivalence to a relation from another ontology.

## Data-layer sequence

The data layer must perform two separate operations.

### A. Normalize a source assertion

Use the source row in `RELATION_MAPPING_TABLE_v2.1.0.csv`.

- If `direction_to_level2=same`, retain the source and target order.
- If `direction_to_level2=reverse`, swap the source and target while translating to `level2_relation_id`.

This operation makes the stored Level 2 assertion semantically consistent.

### B. Return the reverse directional view

Use the associated `direction_pair_id` and the row in `RELATION_DIRECTION_CATALOG_v2.1.0.csv`.

- Swap the normalized source and target.
- Set the relation ID to `reverse_relation_id`.
- Set the relation label to `reverse_relation_label`.
- Preserve the original source assertion ID, evidence, dates, count, and provenance.
- Mark the result as a derived directional view.

The data layer can create this view during graph export or query execution. It does not need to store a duplicate source assertion.

## Agent-facing record

For a stored normalized assertion:

```json
{
  "source": "entity:A",
  "type": "wd:P1365",
  "relation_label": "replaces",
  "target": "entity:B",
  "edge_id": "edge:123"
}
```

the data layer returns this record for reverse traversal:

```json
{
  "source": "entity:B",
  "type": "wd:P1366",
  "relation_label": "replaced by",
  "target": "entity:A",
  "direction_pair_id": "direction-pair-da1e809aab6b",
  "base_level2_relation_id": "wd:P1365",
  "derived_direction": "REVERSE",
  "derived": true,
  "source_edge_id": "edge:123"
}
```

The Agent receives this resolved record. It receives no formula and makes no inverse-relation decision.

## New mapping fields

| Field | Meaning |
|---|---|
| `level2_relation_label` | Data-layer display label for the normalized Level 2 relation |
| `direction_pair_id` | Stable identifier for the forward/reverse contract |
| `reverse_relation_id` | Relation ID returned for reverse traversal |
| `reverse_relation_label` | Relation label returned for reverse traversal |
| `reverse_resolution_type` | `NAMED_INVERSE`, `SYMMETRIC`, or `SYNTHETIC_INVERSE` |
| `reverse_status` | Formal or synthetic activation state |
| `reverse_label_source` | Catalog label, same relation label, or deterministic derived label |
| `reverse_v2_1_change` | Preserved, newly activated, or synthetic action compared with v2.0 |
| `level2_formal_reverse_candidate_ids` | Formal candidates retained for audit |
| `reverse_formal_sources` | Formal source names |
| `reverse_formal_bases` | Formal mapping mechanisms |
| `reverse_evidence_urls` | Formal evidence URLs |
| `reverse_endpoint_action` | Always `SWAP_SOURCE_TARGET` |
| `reverse_of_reverse_relation_id` | Explicit return relation for the second reversal |
| `reverse_data_layer_delivery` | `QUERY_OR_EXPORT_DIRECTIONAL_VIEW` |
| `reverse_agent_action_required` | Always `NONE` |

## Acceptance checks

The builder stops if any of these checks fail:

1. The mapping does not contain exactly 1,520 source rows.
2. The direction catalog does not contain exactly 1,009 effective Level 2 relations.
3. A relation has no reverse ID or no reverse label.
4. Any row requires an Agent action.
5. A symmetric relation uses a different reverse relation ID.
6. A synthetic inverse does not use the `inverse:` namespace.
7. A named inverse uses the `inverse:` namespace.
8. `reverse_of_reverse_relation_id` does not return the original Level 2 relation.

The builder, Ruff, Python compilation, CSV checks, and JSON checks passed on 2026-10-15.

## Boundary of this delivery

This delivery defines and validates the GG data-layer contract. The current Agent graph loader does not consume this catalog yet. The exporter or query layer must use the v2.1 fields before the Agent can receive the resolved reverse records.

The next implementation step is to apply this contract in the exporter and test the three outputs that the Agent can receive: named inverse, symmetric relation, and synthetic inverse.
