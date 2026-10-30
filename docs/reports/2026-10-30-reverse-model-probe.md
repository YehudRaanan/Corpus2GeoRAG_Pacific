# Reversed-input test, without retraining

The existing model can rank the correct entity after reversing the inputs in
this small test. Its stop choice rejects some valid matches. These results do
not establish accuracy on unresolved mentions or on the full corpus.

## Method

- Same trained encoder and scoring head; no training, threshold changes, cloud
  machine, or production assignment changes.
- Twelve actual Daniel name/type groups from Homer N. Wallin, Wikipedia page
  200447, saved revision 1379810886. Eight identical names and four alternative
  names. Each group has five same-page, same-revision QID options.
- References were fixed before each inference batch. Eight exact pairs were
  checked against saved direct links. Four additional cases were checked against
  explicit pipe links or clear references to the article subject. References did
  not come from model predictions. A second reader checked the first eight cases.
- Actual reversal: the first tokenizer sequence contains the Daniel mention,
  type and context. The second contains the official entity name, aliases and
  description. QID strings stay in output metadata and are not model inputs.
- Reverse stop text: **This mention does not refer to any of the remaining
  entities.** This sentence and the reversed input format were not trained.
- Each entity option is scored separately. The highest score wins only if it
  exceeds stop; stop wins a tie. No candidate maxima tied in these results.
- Removed-answer controls delete the correct entity from each pool. They reuse
  independent pair scores; no new encoding is needed. These are artificial
  controls, not verified examples of naturally unresolved mentions.

## Results

| Measure | Identical names | Alternative names | Total |
|---|---:|---:|---:|
| Correct entity ranked first, ignoring stop | 8/8 | 4/4 | 12/12 |
| Correct entity selected, including stop | 6/8 | 3/4 | 9/12 |
| Stop selected despite correct option being available | 2/8 | 1/4 | 3/12 |
| Wrong QID selected | 0/8 | 0/4 | 0/12 |
| Stop selected after correct entity was removed | 8/8 | 4/4 | 12/12 |
| Original direction accepted the correct pair | 8/8 | 3/4 | 11/12 |

The original-direction measure uses each entity's own trained stop option.
It is not a five-choice QID classification score. Original raw cross-entity
ranking is saved only as an uncalibrated diagnostic. All tested original-direction
acceptances were correct; it rejected Rear Admiral Wallin.

| Daniel name | Reference QID and entity | Reversed decision |
|---|---|---|
| Seattle | Q5083 — Seattle | Stop |
| University of North Dakota | Q968559 — University of North Dakota | Correct |
| Puget Sound Naval Shipyard | Q1297188 — Puget Sound Naval Shipyard | Correct |
| Bureau of Construction and Repair | Q2906436 — Bureau of Construction and Repair | Correct |
| Norfolk Naval Shipyard | Q1999049 — Norfolk Naval Shipyard | Correct |
| United States Navy | Q11220 — United States Navy | Stop |
| Willamette National Cemetery | Q8003298 — Willamette National Cemetery | Correct |
| Massachusetts Institute of Technology | Q49108 — Massachusetts Institute of Technology | Correct |
| U.S. Naval Academy | Q559549 — United States Naval Academy | Stop |
| Mare Island | Q657784 — Mare Island Naval Shipyard | Correct |
| Wallin | Q5890160 — Homer N. Wallin | Correct |
| Rear Admiral Wallin | Q5890160 — Homer N. Wallin | Correct |

For Seattle, United States Navy and U.S. Naval Academy, the correct QID was the
highest entity candidate but scored below stop by 0.0739, 0.0373 and 1.1764 raw
logit units. Rear Admiral Wallin exceeded stop by only 0.0242. These values are
not probabilities or confidence percentages. They show why rankings alone are
not sufficient to judge the stop decision.

## Limits and next decision

This is a selected one-page test, with five entity options, not all page QIDs.
The cases have strong source evidence and most names are identical. It does not
measure performance on the 138 omitted groups, low-trigram fragments, missing
QIDs, other pages, or large option pools. The untrained reverse stop wording is
a further source of uncertainty. The two subject references share a QID.

The result supports a larger source-labelled diagnostic before choosing whether
to deploy or retrain. No production change is justified by these 12 cases alone.
No additional run is started by this report.

## Reproduction and verification

Code: `GG_Data/entity_resolution/decision_model/probe_reverse.py`.
Saved cases, source evidence and all scores:
`Data/external/reverse_model_probe_20261030/` (`cases.json`, `results.json`,
`alias_cases.json`, `alias_results.json`). These data files are ignored by Git.

Checkpoint: `Data/external/hundred_page_pilot_20261028/train_20261029/full_best.pt`.
SHA256: `51246b874d6346bf2769077e0067f99f20cb28f6c7a09a02ee78f1c30a2fad20`.
The full checkpoint loaded strictly into the existing scorer architecture.
Pinned encoder: `studio-ousia/luke-base`, revision
`7438924defd9f3c2018d63c16073bf4bcb6a70aa`.

CPU float32, four threads, pair batches of four, maximum 256 tokens. Small pinned
tokenizer/config files were downloaded; base encoder weights were not downloaded.
Model restore, scoring and checkpoint hashing took 27.11 + 16.20 = 43.31 seconds.
Cloud cost: $0. Local power cost was not measured.

Black and Ruff passed. Existing training-contract tests: 3 passed. Case and
checkpoint hashes, prompt configuration, raw scores and model-stage runtime are
saved in each result JSON. No original files or assignments were overwritten.

Timing: preflight began 2026-10-30 02:29:15 Asia/Jerusalem (UTC+02). Work completed
before the 02:39 checkpoint. Total elapsed time is recorded in the plan after
final verification; precise active-work time is unknown. No approval wait.
Code and documentation are a local Git checkpoint only; no push was authorized.
