-- Population S2T section 7; approved Q1190554 test, 21 October 2026.
-- The caller renders native P279 evidence from the agreed BigQuery snapshot.
-- This test does not replace the production root or populate any graph nodes.
DECLARE iterations INT64 DEFAULT 0;
CREATE TEMP TABLE hierarchy_edges AS
{{edge_select}};

ASSERT NOT EXISTS (
  SELECT 1 FROM hierarchy_edges
  WHERE statement_rank IS NULL
    OR statement_rank NOT IN ('normal', 'preferred', 'deprecated')
    OR source_statement_id IS NULL
) AS 'Unexpected native hierarchy evidence';

CREATE TEMP TABLE classes AS SELECT @root_qid AS qid;
CREATE TEMP TABLE frontier AS SELECT qid FROM classes;
-- Each QID enters the frontier once. This stops cycles without a depth cap.
-- Both normal and preferred statements confer membership at every hop.
WHILE EXISTS (SELECT 1 FROM frontier) DO
  CREATE OR REPLACE TEMP TABLE next_frontier AS
  SELECT DISTINCT e.child_qid AS qid
  FROM hierarchy_edges e JOIN frontier f ON e.parent_qid = f.qid
  WHERE e.statement_rank IN ('normal', 'preferred')
    AND NOT EXISTS (SELECT 1 FROM classes c WHERE c.qid = e.child_qid);
  INSERT INTO classes SELECT qid FROM next_frontier;
  CREATE OR REPLACE TEMP TABLE frontier AS SELECT qid FROM next_frontier;
  SET iterations = iterations + 1;
END WHILE;

-- Only the completed root closure leaves BigQuery. Native ranks/IDs remain
-- evidence; deprecated edges between included types do not confer membership.
-- The meta row and window count detect even an empty or truncated transfer.
WITH result AS (
  SELECT 'meta' AS record_kind, @root_qid AS child_qid,
    CAST(NULL AS STRING) AS parent_qid,
    CAST(NULL AS STRING) AS source_statement_id,
    CAST(NULL AS STRING) AS statement_rank
  UNION ALL
  SELECT 'type', qid, NULL, NULL, NULL FROM classes
  UNION ALL
  SELECT 'edge', e.child_qid, e.parent_qid,
    e.source_statement_id, e.statement_rank
  FROM hierarchy_edges e
  JOIN classes c ON c.qid = e.child_qid
  JOIN classes p ON p.qid = e.parent_qid
)
SELECT *, COUNT(*) OVER () AS result_rows, iterations AS hierarchy_iterations
FROM result;
