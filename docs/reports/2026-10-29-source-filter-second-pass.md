# Source filter: second local pass

Date: 29 October 2026. Worktree: `D:\Projects\GeoAI-luke-pilot-20261028`.

The saved 100-page pilot now has 832 fewer source-review occurrences. Of these,
225 are useful displayed content and 607 are citation, navigation, filename or
control content. All previous KEEP and EXCLUDE decisions are unchanged. All
40,070 original rows and columns, saved source files and historical QID
assignments are unchanged. These are source decisions, not new entity matches.

## Result

| Source decision | Previous v1 | New v2 | Change |
|---|---:|---:|---:|
| KEEP: eligible for matching | 23,910 | 24,135 | +225 |
| EXCLUDE: outside selected article scope | 12,272 | 12,879 | +607 |
| REVIEW: insufficient source evidence | 3,888 | 3,056 | -832 |
| All original occurrences | 40,070 | 40,070 | 0 |

The newly kept content contains 159 displayed template values and 66 image or
gallery caption occurrences. Examples include the organization text in a quote
box, military-unit lists in infoboxes, `Soemu Toyoda` in a multiple-image caption,
and `Chinle` in a caption followed by an image alignment option.

The newly excluded content contains 165 citation occurrences, 154 navigation
occurrences, 200 page controls, 43 template controls and 45 image filenames.
For example, `Hallis (2007), p. 15` is a complete short citation; the occurrence
of `Medal of Honor` inside a ribbon filename is a control value. The separate
article occurrences of the same names are not removed.

The historical 18,110 unresolved occurrences split as follows. This only joins
the unchanged old matching status to the new source decision.

| Source decision | Before | After |
|---|---:|---:|
| KEEP | 9,044 | 9,139 |
| EXCLUDE | 6,811 | 7,139 |
| REVIEW | 2,255 | 1,832 |

Thus 95 previously reviewed unresolved occurrences become eligible, 328 become
excluded, and 1,832 still need source review. None is newly assigned a QID.

## Small changes to the existing pipeline step

- `filter_source_content.py`: retain the existing parser and interfaces. Add
  whole-body short-citation rules, two observed citation-template forms, known
  navigation/control templates, and explicit displayed fields for quote boxes,
  lists, colored text, multiple images and galleries. A caption remains visible
  when an image option follows it. Gallery captions need local parsing because
  the outer parser treats the extension body as opaque text; nested source
  ranges are rebased to the original revision.
- `prepare_candidates.py`: accept an explicit, uniform v1 or v2 policy. Mixed,
  partial and unsupported policy annotations still fail. New filtering writes
  `article-source-v2`; saved v1 data remains readable.
- `test_filter_source_content.py`: add positive and negative source cases and
  policy compatibility checks. No new dependency, pipeline framework, name
  repair, model or training code.
- `README.md`: document the new policy and next-run commands.

Unknown syntax remains REVIEW. A short citation must match the complete ref
body; an author/year inside explanatory or mixed prose is not enough. Quote
attribution/source fields remain REVIEW. Filenames, hidden link targets,
gallery `alt`/`link` options and ignored extra plain-list parameters cannot
become displayed content. Nested citation and control text remains masked.

## Completeness checks and remaining uncertainty

Every old/new decision was compared by original row ID. There are no
KEEP-to-EXCLUDE, EXCLUDE-to-KEEP or other changes to previous KEEP/EXCLUDE rows.
Each of the 832 changed rows retains an exact original source span. Each newly
kept original mention is present in its cleaned context. Each newly excluded
row has an empty matching context. Every distinct changed rule family was
inspected through its saved source evidence; this is not independent human
labeling of every occurrence or a proof of historical template rendering.

All original columns compare equal, with 40,070 unique source IDs. Hash checks
cover the five frozen pilot inputs and all 132 used revision-text files. All
eligible non-DATE row IDs occur exactly once in candidate groups; excluded and
reviewed rows do not enter those groups. Candidate contexts equal the cleaned
source contexts. The final filter code hash agrees with the saved data manifest.

Remaining REVIEW reasons, across all 40,070 occurrences:

| Reason | Occurrences |
|---|---:|
| Explanatory, mixed or unsupported reference notes | 1,327 |
| Original span crosses source boundaries | 808 |
| Unsupported template or parameter | 539 |
| Repeated or non-exact raw placement | 295 |
| Notes section | 45 |
| Coordinates | 39 |
| Ambiguous media field | 2 |
| Template name | 1 |
| Total | 3,056 |

These cases were not forced into KEEP or EXCLUDE. In particular, damaged spans
and repeated passages need a separate evidence or span-repair decision. Keeping
all previous KEEP decisions proves preservation of the prior scope; it does
not prove that every prior decision was correct. Historical template rendering
and overall entity-match accuracy were not measured.

## Verification and runtime

| Stage | Original rows | KEEP | EXCLUDE | REVIEW | Candidate groups | Model jobs prepared |
|---|---:|---:|---:|---:|---:|---:|
| 3 pages | 535 | 255 | 236 | 44 | 141 | 203 |
| 10 pages | 3,785 | 2,427 | 1,090 | 268 | 1,050 | 1,078 |
| 100 pages | 40,070 | 24,135 | 12,879 | 3,056 | 11,810 | 13,441 |

Final local filtering and candidate preparation for all three stages took
80.719 seconds. Filter-only times were 0.281, 1.891 and 36.313 seconds. Prepared
model jobs were not executed. The 248-test pilot suite passed in 12.29 seconds;
Ruff passed and Black left the three changed Python files unchanged.

Two parallel read-only source reviews covered citation and displayed-content
rules. A separate final code review found two defects: gallery `alt`/`link`
values could enter captions, and ignored plain-list parameters could enter
displayed text. Failing tests demonstrated both defects before fixes. The
yearless short-citation rule was also tightened to require a comma before page
metadata. A guarded replacement script stopped before writing when an anchor
did not match; an exact patch was then used. No partial source-data update
occurred. A preliminary `run_1` is retained; only `run_2` is the final output.

Time basis: preflight 18:00:14–18:02:14, then execution from 18:33:48, on
29 October 2026, Asia/Jerusalem (UTC+02). The intervening approval/chat wait is
excluded. Active work was not separately measured. Estimate v1 was 45–90
minutes of elapsed execution including preflight; the exact completion clock
and actual are recorded in the local completion manifest and task ledger.
Epoch estimate: `7f3e83a1-2340-45d7-a8d2-390dbe046ec1`.

Cloud cost: US$0. No inference, training, collection, paid query, Geography,
graph rebuild or full-corpus run. The separate `what_happened_at` spatial
date-filter issue remains open and unchanged.

## Local outputs and next run

Final output root, relative to this worktree:

`Data/external/hundred_page_pilot_20261028/template_name_pilot_20261029/source_scope_filter_second_pass_20261029/run_2/`

- `scope_100/filtered/mentions.parquet`: all original rows plus v2 source fields.
- `scope_100/matching/`: eligible groups, exact pairs and prepared candidate jobs.
- `changed_source_decisions.parquet`: all 832 changed rows, previous decisions
  and source evidence, new decisions and raw excerpts.
- `comparison.json`: complete transition counts, examples and comparison hashes.
- `validation.json`: 3/10/100-page checks, input/code/revision hashes and runtime.
- `completion.json`: final verification, timing and local-checkpoint evidence.

Keep future inference in a new directory, explicitly bound to these v2 inputs
and the existing model-readiness/approval limits. Do not reuse the old inference
as if it were produced from this source policy. This task prepared inputs only.

Backup status: **Local checkpoint only**. Task code and documentation are
checkpointed locally; generated data remains ignored and local. No push is
authorized, and no GitHub protection is claimed. Unrelated working-tree changes
were preserved outside the task checkpoint.
