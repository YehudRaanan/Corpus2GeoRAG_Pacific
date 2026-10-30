# Review flags no longer block the revised matching pipeline

OWNER approved a local code change and preparation on the saved 100 pages.
This delivery does not include a model run, new collection or cloud cost.

## Change

The revised pipeline admits all 7,692 previously reviewed non-DATE mentions.
Review flags remain in the data as evidence. They do not decide whether a
mention identifies a QID. The 226 reviewed DATE mentions remain deferred.

`prepare_candidates.py` supplies one context decision for grouping, the mention
writer and EDA. It prefers a verified clean span. Otherwise it uses Daniel's
original text and original offsets, checked against the original word, even
when the working name was repaired. It never invents clean offsets. A row with
neither valid context remains a data-validation failure.

`post_qid_mentions.py` no longer classifies an eligible mention as audit-only
because of a review flag. It records `matching_context_basis` as `clean` or
`original`. `post_qid_eda.py` checks that same decision and retains the raw-value,
revision, typed-entity and many-to-many bridge checks.

The existing top-80 and source-supported candidate pools remain. A reviewed
group omitted from every pool receives its highest-trigram same-revision
pairing. This added 64 pairings. Inclusion proves exposure, not correct identity
or the presence of the correct QID. A zero trigram score can still be the best
available score. The model must make the decision in a separate approved run.

Raw-only legacy calls retain their old source policy for baseline compatibility.
The revised pipeline must run the cleaning stage before candidate preparation.
The revised matching receipt is identified by `review-advisory-v1`.

## Saved 100-page preparation

Final artifact root: `Data/external/review_advisory_v1_20261030/`.
The previous `Data/external/revised_pipeline_20261030/` is unchanged.

| Population | Previous run | New preparation |
|---|---:|---:|
| Original mentions | 40,070 | 40,070 |
| Matching eligible | 13,239 | 20,931 |
| Review withheld | 7,918 | 0 |
| DATE deferred | 3,933 | 4,159 |
| Explicit source exclusions | 14,980 | 14,980 |

The same 100 pages and 132 historical revisions remain. Original source values,
occurrence identities, cleaned text, offsets and review evidence are preserved.
For all eligible mentions, 18,906 contexts use clean text and 2,025 use original
text. Among the 7,692 newly admitted mentions, these counts are 5,667 and 2,025.

The newly admitted mentions occur in 5,871 page/revision/name/type groups.
All have an exact match or a model candidate job. No such group lacks a named
same-revision inventory. Some groups have both an exact pair and candidate jobs
for other QIDs; those categories overlap and must not be added.

There are 12,557 total eligible groups, 2,223 exact pairs and 13,441 QID jobs.
The candidate workload is 770,508 query/option pairs including stop options.
This is a workload count, not a model result.

Exact groups decreased from 2,310 to 2,223: 300 old groups move to model
consideration and 213 newly eligible groups receive an exact match. Of the
300, 290 now share a group with repaired/review evidence, and ten now have
multiple Daniel types for the same name. Existing strict exact rules were kept.

The expanded top-80 pools still omit 138 groups (192 mentions) from the previously
eligible population. The approved coverage protection applies to newly admitted review
groups. The remaining older-population omissions are recorded separately; this
delivery does not claim complete model exposure for every eligible group.

## Outputs and verification

- `input/cleaned/mentions.parquet`: all rows with refreshed eligibility.
- `input/exact/`: strict exact groups and accepted pairs.
- `input/matching/`: groups, model jobs and matching receipt.
- `scopes/`: frozen nested scopes and jobs, based on the same saved selection.
- `tables_pending_100/` and `tables_exact_100/`: local table snapshots before
  model execution. They are not final model or graph tables.
- `verification.json`: source and code hashes, coverage checks and stage times.

The pending snapshot contains 20,931 pending mentions. The exact snapshot
contains 3,304 exact-matched mentions, 17,627 pending mentions, 1,316 typed
entities and 3,304 mention/entity links. Both snapshots retain all 40,070 rows
and pass EDA and stored-output hash checks. Review-withheld status is zero.

826 regression tests passed using `--import-mode=importlib`; the default combined
collection found two existing files named `test_pipeline.py`. Importlib resolved
collection without deleting caches or changing code. Ruff and diff checks passed.
The final focused regression run passed 95 tests after the last receipt-count
change; these overlap the broader tests and are not an additional denominator.
An independent consumer review and local fallback probe found no blocker.

Tests cover advisory review, clean/original context, invalid contexts,
DATE/source exclusion, page/revision identity, exact matching, candidate
coverage and typed bridges. These are processing checks, not accuracy labels.

No new model decisions or unresolved-rate result exists. Old model scores must
not be reused with changed jobs. An unresolved result in the previous run does
not prove that a relevant QID was absent: retrieval limits and model rejection
are also possible causes.

## Execution record

Three workers handled independent code changes and review; root owned
integration, artifacts and Git. The preliminary preparation took 176.86 seconds.
It preceded final compatibility/receipt edits, so a fresh final version was
prepared rather than overwriting it. Final preparation took 126.25 seconds.
Final per-stage elapsed times are in
`verification.json`; exact active-work and approval-wait durations are unknown.
No cloud resource was started and no paid service was called.
Epoch v1 estimated 30–60 elapsed minutes including preflight and excluding
approval/environment wait. The full same-basis actual remains unknown because
the approval wait and exact preflight start were not measured. No partial stage
duration was submitted to Epoch as a whole-task actual.

Backup status: **Local checkpoint only** after the task commit. No push is
authorized. Ignored datasets and local preparation artifacts are not protected
on GitHub. Unrelated existing changes are outside the commit.
