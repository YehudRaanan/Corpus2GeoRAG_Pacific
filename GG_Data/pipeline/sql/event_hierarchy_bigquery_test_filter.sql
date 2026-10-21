-- Population S2T section 7; same-source Q1190554 test, not Event population.
-- Reuse the unchanged, verified Daniel-first sample's candidate QIDs.
-- Both P31 evidence and the completed class list stay in BigQuery for matching.
WITH targets AS (
  SELECT qid FROM UNNEST([{{target_qids}}]) AS qid
), records AS (
  SELECT w.id,
    JSON_QUERY_ARRAY(RTRIM(w.item, ',\n\r '), '$.claims.P31') AS p31
  FROM {{source}}
  WHERE numeric_id IN ({{numeric_ids}}) AND STARTS_WITH(w.id, 'Q')
), classes AS (
  SELECT child_qid AS qid FROM {{cloud_hierarchy_result}}
  WHERE record_kind = 'type'
)
SELECT t.qid, r.id IS NOT NULL AS record_present, r.p31,
  IF(r.id IS NULL, NULL, EXISTS (
    SELECT 1 FROM UNNEST(r.p31) AS s
    JOIN classes c ON JSON_VALUE(s, '$.mainsnak.datavalue.value.id') = c.qid
    WHERE JSON_VALUE(s, '$.rank') IN ('normal', 'preferred')
  )) AS event_hierarchy_match
FROM targets t LEFT JOIN records r ON r.id = t.qid;
