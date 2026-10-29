# Why the 100-page pilot still has unresolved mentions

**Status:** Complete on 29 October 2026. Independent output and report reviews
passed. No matching results have been changed.

## What was checked

All **18,110 unresolved original mention rows** were checked against saved
sources, inventories, candidate jobs and model scores. These are **11,712
page/revision/name/type groups**, or **8,495 distinct prepared name/type pairs**
across the pilot. They occur on all 100 pages, in 129 of the pilot's 132 revisions.
Repeated rows are not separate real-world entities.

The unresolved count is 55.4% of the 32,698 non-DATE input rows. The 7,372 DATE
rows remain excluded, as agreed. The original 40,070 rows remain unchanged.

This is a complete evidence inventory, **not a complete human identity review**.
Most cases still lack a verified expected identity. All reviews are explicitly
AI or deterministic checks; none are presented as human gold.

## The clearest result

The remaining cases do not have one cause. Improving the model alone, increasing
the trigram limit alone, or extending every fragment will not cover all cases.

Only **1,159 unresolved rows** have a positive in the incomplete frozen reference.
The other **16,951** have no expected QID established by that reference. This does
not prove that their QIDs are absent, or that the mentions cannot be resolved.

For the supported reference, the saved pipeline stages are:

| Stage | Reference mention/QID pairs | Meaning |
|---|---:|---|
| Candidate reached model, not selected | 1,073 | Stop scored at least as high as the candidate. |
| Candidate excluded by retrieval | 36 | Expected QID existed, but its job did not contain that mention group. |
| No usable English label/job | 62 | Expected QID existed, but no usable named job was made. |
| Expected QID absent from inventory | 0 | No such case in this limited reference; not a full inventory-coverage claim. |

There are 1,171 pairs on 1,159 rows, because more than one expected QID is allowed.
The disjoint row counts are: 1,061 model-only, 36 retrieval-only, 50 label/job-only,
12 with multiple supported stages, and 16,951 unknown-reference rows.

Of the 1,073 model-rejected pairs, 1,060 scored below stop and 13 tied stop.
Their median score-minus-stop was -5.125. These are raw scores, not probabilities.
Only 13 supported pairs tie stop; the effect of changing the tie rule on identity
quality is unmeasured. No threshold or decision rule was changed.

## The reference needs identity review too

All 1,171 supported unresolved pairs were joined back to their exact frozen raw
link anchors. **65 pairs on 65 rows / 50 groups need reference-quality review**:
44 redirect to a page section, 20 explicitly link to a page section, and one has
a changed current QID. These three groups do not overlap in this subset.

For example, row 73368 has the anchor `Sugar Loaf Hill`; its saved current/cached mapping resolves to
`Battle of Okinawa#Southern Okinawa` / Q192660. This links a named place to an
event section; the link alone does not prove that the place and event are the
same entity. The candidate was at trigram rank 95 and was not retained.
Historical source placement and current title-to-QID mapping have separate
provenance; the current mapping does not establish the historical QID mapping.

Of these 65 flagged pairs, 54 reached the model but were rejected, ten were
excluded by retrieval and one lacked a usable label/job. Rejection alone must
not be counted as a model error. Conversely, the other 1,106 pairs having no
saved conflict does not make them verified identity gold.

Also, 571 reference pairs inherit anchor evidence from another occurrence of the
same original literal name/type group. This is the saved evaluation expansion
rule, not a separate wrong-label count. It does not independently verify the
identity of every occurrence. Frozen labels were not changed.

## Practical groups that need different treatment

These evidence groups overlap; **do not add their counts**.

| Evidence group | Rows | Practical meaning |
|---|---:|---|
| Source-target candidates already available | 2,653 | Some useful QID evidence already exists; collecting more QIDs is not the only next step. Partial source spans still need interpretation. |
| No model exposure to any QID job | 914 | These mentions were not tested against any candidate QID. Every affected page had usable jobs; the top-80 retrieval limit excluded these groups from all those jobs. Only six rows here have a frozen positive. |
| Citation parameter values | 5,055 | Names appear in author, book-title, publisher or publication-location fields. They are different from ordinary article-text mentions. |
| Longer recovered source surface not used | 1,510 | There is a longer overlapping surface to inspect; it is not automatically the correct entity name. |
| Alias-only exact normalized name availability | 750 | A same-revision inventory alias equals the mention after case/Unicode/space normalization. Identity is not automatically proved. |
| Linked-title-only exact normalized availability | 359 | Similar opportunity using the linked Wikipedia title. |
| General word/descriptor screening flag | 2,011 | Examples include Japanese, Navy and Battle of. The explicit screening list is a heuristic, not a verified non-entity label. |
| Nonunique or normalized-only raw placement | 172 | Source anchoring needs review; no raw location was guessed. |

Within citation parameters, 2,440 rows occur in title/work fields, 1,471 in
author/editor fields, 624 in publisher fields and 319 in location fields. These
subsets can overlap and do not exhaust every citation field.

There are **56 unresolved rows with literal official-label equality**, each with
one candidate QID. None passes all current exact-match gates. The blocking gates
include source-review groups (35 rows), multiple Daniel types (19), and repaired
groups (2). Thus there is no demonstrated failure to accept a row that satisfies
the current strict exact rule. Casefolded equality produces 62 rows; it is a
different diagnostic, not the agreed literal matching rule.

## Templates: useful, but not the main explanation

6,948 rows overlap unsupported or review templates. Only 789 overlap their first
parameters. A template can contain a whole paragraph or bibliography, so the larger
number must not be called a QID-collection gap.

The narrower flag/country-helper subset (`flag`, `flagicon`, `flagu`,
`flagcountry`, `flagdeco`, `flagd`) contains **95 rows**. For 82 of them, a
saved title mapping suggests a QID absent from that page inventory. This is a
bounded collection opportunity, not 82 verified new assignments. It accounts for
about 0.45% of all unresolved rows.

Nine other current mappings appeared to offer missing targets. All nine are
disambiguation items (`Q4167410`). Eight are absent from the inventory because the
recovery code correctly excludes them. They must not be added as ship identities.

174 rows overlap missing/invalid target-page lookups. This does not prove that
no QID exists. Five rows also expose a separate collection limitation: the colon
filter skips two apparent book/article titles along with non-article namespaces.

## Examples with saved source evidence

| Row | Original/prepared name | Saved source and interpretation |
|---:|---|---|
| 5943 | United States of America | `country={{flag\|United States of America}}`, 15th Antiaircraft Artillery Battalion, revision 1372151346. Saved title mapping suggests Q30, absent from that revision's inventory. A strong example for controlled flag-template support. |
| 313027 | Hackett → Bob Hackett | Citation `last1=Hackett`, `first1=Bob`, Bombardment of Fort Stevens, revision 1375594940. Reconstruction works, but a same-revision exact inventory name is unavailable. This is not proof that no QID exists. |
| 73789 | Naval Institute Press | Citation publisher, 6th Marine Division, revision 1381811777. Preserve its bibliographic role; do not assume an article-participant relationship. |
| 150513 | World War II | Part of the cited title *The Army Air Forces in World War II*, revision 1335836004. Book-title occurrence and historical-event occurrence need different context treatment. |
| 412499 | Task Unit Shufly | Complete link anchor for Operation Shufly/Q112649194, David M. Shoup revision 1379847160. Candidate ranked first; its score tied stop (-20), so stop won under the existing rule. |
| 846377 | I-22 | The source ship template lacks a disambiguating year. The current mapped QID is a disambiguation item. Do not force it into a specific submarine identity. |

The high-frequency group Japanese/MISC has 738 rows, including prose adjectives,
ship-template nationality prefixes, captions and citation titles. United States/LOC
has 248 rows, including country references and parts of longer organisation names.
A single name-level replacement would merge different meanings.

## Work queues for a later repair phase

The audit assigns each row to one queue using the stated priority below. These
are **work queues, not six proven causes**. Original overlapping evidence is kept.

| Priority queue | Rows |
|---|---:|
| Supported-reference stage review | 1,159 |
| Other accepted source-target candidate review | 2,007 |
| Other exact normalized inventory-name review | 485 |
| Other source-span screening/reconstruction review | 3,339 |
| Remaining cases with no model exposure | 271 |
| Other context/identity review | 10,849 |
| **Total** | **18,110** |

Recommended order, before another broad inference run:

1. **Review the evaluation reference.** A complete Wikipedia anchor proves a
   saved link target, not always identity equivalence. Keep source-derived positives
   separate from independently reviewed entity labels.
2. **Fix small deterministic gaps.** Provide a controlled alias/title fallback for
   missing labels; examine why supported candidates missed existing source protection;
   handle flag/country templates and article titles containing colons safely.
3. **Keep source roles and better local names.** Preserve author/publisher/title
   roles; reconstruct complete names only with local span evidence. Keep the original
   name and offsets. Do not convert every adjective or ship prefix into the whole ship.
4. **Evaluate the decision model on reviewed cases.** Separate valid rejection,
   retrieval failure and model error. Check the previously recorded training/inference
   formatting difference before deciding on retraining. Its effect is not measured here.

These are proposals, not implemented policy changes. No numerical recovery promise
is justified by this audit alone.

## Files and verification

All case evidence is local under
`Data/external/hundred_page_pilot_20261028/template_name_pilot_20261029/unresolved_audit_100/`.

- `audit.py`: one integration step; validates reviewer lineage, joins original IDs,
  separates reference stages from flags, and writes the audit tables.
- `test_audit.py`: six focused checks for duplicates, missing rows, unknown identities,
  overlapping stages, evidence separation and stale input hashes.
- `rows.parquet` / `rows.csv`: one row per unresolved original mention, with the
  three evidence records preserved separately.
- `groups.parquet` / `groups.csv`: the 11,712 saved scoped groups and all member IDs.
- `by_name_type.csv`: repeated-name counts, pages, groups and example contexts.
- `candidate_review/`: source-supported pair stages, all group/job exposures,
  saved score/stop evidence and independent integration/output checks.
- `source_review/`: targets, lookup states, inventory membership and metadata receipts.
  `reference_quality_pairs.*`, `reference_quality_review.json` and
  `reference_quality_verification.json` hold the strict-anchor reference supplement;
  it joins by original row and expected QID without changing the frozen reference.
- `span_review/rows_final.*`, `summary_final.json`, `verification_final.json`:
  final text/role/name-metadata evidence. Earlier intermediate files are superseded,
  not deleted.
- `summary.json`, `verification.json`: integrated counts and unchanged-input checks.

Independent output review passed: all 18,110 rows, all 11,712 groups, all 100 pages,
CSV/Parquet equality, exact reviewer joins and saved group membership. All 303 input
hash entries match; some relative/absolute entries refer to the same physical file.
No model, cloud, network collection, assignment, reference-label or DATE change occurred.

Six focused tests, Ruff and Black checks passed. The integration script took
14.093 seconds; reviewer scripts and development/review time are separate.
Runtime, issues and final protection status are recorded in `completion.json`.
No billed cloud action was performed. The observed execution interval is
recorded separately from unmeasured active work and preflight/approval waits;
no incompatible numeric actual is submitted to Epoch.

Protection: **Local checkpoint only** for this plan and report after the local
commit. Audit scripts, case data and receipts under the ignored Data directory
remain local and unprotected off-device. No push was made.
