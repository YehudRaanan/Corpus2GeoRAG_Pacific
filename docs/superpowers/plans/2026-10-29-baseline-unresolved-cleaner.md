# Original unresolved cleaner test

Goal: apply the existing source-preserving cleaner to the original 100-page
baseline unresolved export, before template/name repairs. Do not rerun matching.

Scope: local data test only. No production code changes, cloud, collection,
inference, training, assignment changes, or source overwrites.

Ponytail full: reuse clean_source_text.clean_mentions and existing Parquet data.
Superpowers breakdown and Epoch estimate v1 agree on the same local scope:
10–18 minutes total elapsed, including preflight; model-derived estimate,
not a guaranteed or calibrated deadline. Epoch reference
9649b6f0-2b58-44f0-9ce2-7355d0749231, O/M/P 0.12/0.20/0.30 hours.
Observed start 2026-10-29 23:09:39 Asia/Jerusalem (+02:00).
Checkpoint 23:19; upper completion 23:27:39. Active work and waits are not
separately measured and must not be inferred from elapsed time.

- [x] Root: verify original baseline: 19,071 UNRESOLVED_ENTITY and 7,372 DATE.
- [x] Root: run existing cleaner on the original unresolved export in a fresh directory.
- [x] Root: verify row preservation, original columns, mapped slices and hashes;
  produce counts by type/status, reasons, examples, and prior-filter comparison.
- [x] baseline_cleaner_check: independent read-only denominator/result review;
  no shared writes. Depends on cleaner outputs.
- [x] Root: report source cleaning benefit separately from QID resolution.

Exclusive write owner: root. Reviewer reads only. Outputs remain ignored local
data; report/plan can receive a local Git checkpoint. No remote push authorized.

Completed before the 23:19 checkpoint. Verification: all 26,443 rows preserved,
70 existing tests passed, independent review complete. Script elapsed times:
cleaner 13.297 seconds; source filter 20.532 seconds. Observed session interval
23:09:39–23:16 Asia/Jerusalem, approximately six minutes; active_work and wait
durations unknown, so no focused-effort actual is submitted to Epoch.

Finding: run is experimental and ready_for_matching=false. Sixteen factual
ship-class mentions are incorrectly removed; Japanese-template and quotation
attribution cases also require protection/review. No production code changed.
Next implementation is not silently added to this local run scope.

## User-requested follow-up: class exception

Scope: narrow ship-template exception, regression tests, fresh local cleaner
run and Japanese-name collection check; no model/cloud/network use.
Ponytail reuses the existing template branch. Superpowers breakdown: reproduce
the defect in tests -> fix exact template -> run tests and same baseline ->
verify all rows and the 16 known spans -> report Japanese-name limitation.
Owner root, sequential shared code/output writes. Epoch v1 reference
bf77b046-0642-43d7-95c5-af7ee5bde6ed, O/M/P0.10/0.16/0.25hours; same scope
and elapsed-time basis, model-derived estimate. Announced6–15minutes including
inspection; observed start23:19:06, checkpoint23:29 on29October2026
Asia/JerusalemUTC+02. No approval/environment wait observed; focused active
work is unmeasured. All steps complete:74tests passed; 16knownclassspans restored;
run_2 preserves26,443rows. Japanese/quotation rules remain open and no new QID
matches are claimed. Script elapsed13.125seconds, not session active work.
