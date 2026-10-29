# Japanese-name and quotation preservation

Goal: preserve displayed Japanese name variants and quotation attribution in
cleaned pilot text, with original rows/text and exact character provenance.
Scope: existing cleaner and source-filter rules, regression tests, full100-page
rerun and comparison of original pre-template unresolved rows. No inference,
training, collection, cloud cost, Geography, or assignment changes.

Ponytail full: extend existing template rules; reuse installed parser and runner.
Superpowers task breakdown and Epoch v1 share this scope/dependencies/time basis:
O/M/P0.15/0.23/0.33hours, reference3c64d735-55a3-42d3-bae8-5864fe860b23.
Model-derived total estimate10–20minutes including preflight. Observed start
23:30:56 on29October2026 Asia/JerusalemUTC+02. Checkpoint23:40; upper23:50:56.
Active_work is unmeasured; elapsed time must not be reported as active work.

- [x] Root: reproduce lost Japanese/romanized names and quote attribution in tests.
- [x] template_field_review: primary-source parameter semantics, read-only;
  independent of root tests. Root is exclusive write/resource owner.
- [x] Root: extend shared field rules and keep unsupported inputs literal+review.
  No bibliography unmasking; keep nihongo2 distinct from nihongo.
- [x] Root: pass cleaner/filter tests and lint; run full100 and baseline unresolved
  into fresh outputs, verify all rows/offsets/hashes and changed decisions.
- [x] Reviewer: check final focused diff; root records report and local checkpoint.

Deliverables: code/test updates in existing step files; new local Parquets and
comparison JSON; short report with counts and limits. Unknown template semantics
must remain review rather than guessed displayed fields.

Completion evidence: 12 initial regressions failed before the rules and passed
afterward. Independent review identified two additional narrow cases; both were
reproduced failing then fixed in the same pass. Final193cleaner/filtertests and
16pipeline/layoutchecks pass; Ruff/Black pass. Final full40,070rows and baseline
26,443rows passed root+independent verification. All16prior ship cases preserved.
No QID changes;16nonDATE and10DATE spans restored,3nonDATE nowuncertain.
Current source order is intentional for monotonic offsets; ambiguous alias
combinations and cquote stay literal/review, not guessed rendering.
Observed execution from23:30:56 toapproximately23:39 Asia/Jerusalem;
elapsed time only, active_work unknown. No approval/environment wait observed.
Final scripts13.625s(full) and16.031s(subset); no cloud cost. Earlier runoutputs
preserved. Focused-effort actual not submitted toEpoch becauseunmeasured.
