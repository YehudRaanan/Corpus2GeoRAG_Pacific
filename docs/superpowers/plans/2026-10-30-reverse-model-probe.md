# Reversed-input diagnostic

User approved an experiment without retraining. No production assignments change.

- Root: check local assets and freeze independently reviewed reference cases.
- Root: restore the full checkpoint; score original and reversed sequence order.
- Read-only reviewer: check source evidence and experiment limits in parallel.
- Root: report ranking, stop decisions, removed-gold controls, costs and runtime.

Dependencies: reference cases precede inference; report follows saved scores.
Resource owner: root owns files, Git and CPU model. Reviewer only reads data.
Scope excludes training, cloud machines, production changes and threshold tuning.
Tokenizer/configuration may be downloaded; full trained weights are already local.

Estimate: model-derived 10–20 elapsed minutes including preflight from
2026-10-30 02:29 Asia/Jerusalem (UTC+02). Status checkpoint: 02:39.
Epoch PERT reference: 37831179-863b-4f7e-b5d7-054306660c15.
Superpowers breakdown and independent review agree on scope and time basis.
Approval/environment waits are separate; active work is not measured precisely.
Raw scores are logits, not probabilities. This diagnostic is not an accuracy
estimate for the full corpus. New reversed stop wording is untrained.

Completed: 12 frozen reference cases, 12 removed-answer controls, both input
orders, independent read-only review, source/hash verification and saved report.
Results: correct candidate ranked first 12/12; reversed selection 9/12; three
false stops; controls stopped 12/12. Original-direction gold acceptance 11/12.
Black/Ruff passed; training-contract tests passed (3). No production edits.
Model restore/scoring/hash runtime: 43.31 seconds total, CPU only, cloud $0.
Elapsed through final verification at 02:36:22: 7m07s. Active work unknown;
download wait approximately 12.9s overlapped independent work, not additive.
No approval wait. Final Git checkpoint follows; no push is authorized.

Final checkpoint d68f940 completed at 02:36:36: total elapsed 7m21s (0.1225h).
Epoch actual recording issue: input 7.35 with unit minutes was returned as
7.35 hours. A correction to 0.1225 hours was rejected because an actual already
exists. Do not use that Epoch actual for calibration; this local timing is the
verified record. No further estimate/feedback loop was started.
