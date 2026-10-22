# Geography: 100 new inputs, 22 October 2026

## Verified status

Stopped for owner consultation during source retrieval. This is not a completed geometry run or an accuracy result. No main-model rows or input identities changed.

The sample is frozen at `GG_Data/pipeline/outputs/geography_ranking_100_new_20261022/sample.json`. It contains 100 distinct existing LOC inputs: 73 QID and 27 synthetic inputs, randomly sampled without replacement from 1,241 remaining LOC targets in the existing 10K POC. Seed: `20261022100`. Overlap with the previous twenty: zero. All selected source pages are English; this sample does not test Japanese-page coverage. The root `preflight.json` records protected input hashes and the sample hash.

Four inputs have multiple P625 statements: Omni Shoreham Hotel (Q7090343), Shanghai (Q8686), Aigun (Q404795) and Leśno (Q4977506). The owner approved keeping all non-deprecated coordinate statements as separate candidates, preserving native values and using the unchanged ranking/tie rule. Aigun's deprecated statement is excluded. No coordinate averaging, new entity, QID replacement or score change is introduced.

## Source request failure

At approximately 13:48 Asia/Jerusalem, the first WHG request contained 100 queries and returned HTTP 400. No source batch completed. The existing client did not retain the HTTP error body, so no body-level server diagnosis is available. The official [WHG batching documentation](https://docs.whgazetteer.org/content/technical/apis.html#batching-quotas-and-retries) states that batches above 50 queries are rejected with HTTP 400 and nothing is processed. This matches the submitted batch and observed status.

The owner-required stop-on-problem rule was applied. Proposed correction, awaiting approval: split the unchanged query sets into batches no larger than the service's published limit, cache each complete batch, and combine only after response-key completeness checks. Keep all 100 inputs, both saved query arms, source list, weights, coordinate policy and ranking unchanged. Do not treat the failure as zero candidates, discard inputs, or repeat the oversized request.

The failed run's status is in `comparison/progress.json`; the frozen query plan and input evidence are in `comparison/`. There are no final geometry outputs yet. Seven focused comparison/ranking tests and Ruff passed before retrieval. The multiple-coordinate test covers retaining normal/preferred statements, excluding deprecated statements, and preserving the input record.

## Reproduction after the retrieval correction is approved

Prepared input: `geography_comparison.prepare(base, comparison, frozen_sample=sample_path)`.

After complete retrieval, run `python -m GG_Data.pipeline.geography_ranking_sample --comparison <comparison-directory> --output <new-ranking-directory>` from `D:\Projects\GeoAI`. This reuses the existing ranking and source readers, while retaining the previous twenty-input driver as the default. Generated sources and experimental outputs are local ignored artifacts, not a remote backup.
