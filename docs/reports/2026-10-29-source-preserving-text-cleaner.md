# Three-page source-preserving text cleaner

The separate code step is `GG_Data/entity_resolution/hundred_page_pilot/clean_source_text.py`.
It ran locally on **8,350 original Daniel rows, three pages and eight saved historical revisions**.
All original rows, text, offsets, IDs and types were preserved. The original entity text is in
`word_original`; only two working words changed, through HTML-entity decoding.

## Final output

`Data/external/hundred_page_pilot_20261028/source_text_cleaner_pilot_20261029/run_3/`

| File | Content |
|---|---|
| `mentions.parquet` | All 8,350 rows, originals plus cleaned text, entity offsets and statuses. |
| `used_revisions.parquet` | The eight exact page/revision records used. |
| `summary.json` | Counts, code/input/raw hashes and measured run duration. |
| `verification.json` | Row/column preservation, offset checks, page counts and prior-filter comparison. |
| `examples.json` | Thirteen full before/after examples with original and new offsets. |

Runs 1 and 2 are retained as intermediate evidence. Run 3 is the final artifact.
No existing assignment output, production table or model checkpoint was changed.

## What the code does

1. Read original page-attached Daniel rows and the saved revision ledger; reject duplicate IDs,
   missing required columns and an existing output directory.
2. Validate saved raw source against its hash and saved page/revision response.
3. Parse each used full revision once. Reuse the local source rules to omit citations,
   bibliography, notes, controls and media captions. Retain article prose, factual table
   headers/cells and supported infobox/template values.
4. Keep each visible character's original source span. Generated separators have a zero-length
   insertion anchor and provide no original mention evidence.
5. Project each unique literal Daniel passage through that page map. This handles lines cut
   from the middle of a table, infobox or reference without guessing their missing wrapper.
6. Map each original mention by its exact character spans. Write a new Parquet; retain excluded
   and uncertain rows with null clean offsets.

The file contains the parser, position mapping, Parquet wrapper and CLI for this one step.
Its test file is `test_clean_source_text.py`; the README contains the command.
Code, tests and source checks were developed in parallel with exclusive file owners.

## Results

| Page | Rows | Revisions | Mapped to clean text | Excluded from clean text | Uncertain |
|---|---:|---:|---:|---:|---:|
| Japanese war crimes | 5,949 | 5 | 2,389 | 3,448 | 112 |
| Palawan | 1,835 | 2 | 916 | 797 | 122 |
| Robert L. Ghormley | 566 | 1 | 342 | 195 | 29 |
| **Total** | **8,350** | **8** | **3,647** | **4,440** | **263** |

These are text/source-mapping outcomes, **not QID matches or measured entity-linking accuracy**.
There are 884 distinct page/revision/passages. Cleaned text differs from original text on
8,235 rows. All input rows remain in the output.

The 263 uncertain rows comprise:

- 111 overlapping unsupported/review source components;
- 88 spans crossing removed syntax or separate visible components;
- 49 passages with multiple exact source placements;
- 15 passages without an exact literal placement in the saved revision.

`clean_text_needs_review` is true on 735 rows. Of these, 292 have a valid mapped entity span
but unsupported markup elsewhere in their context. A valid entity offset does not prove
that the whole passage has been fully cleaned.

Compared with the latest second-pass source filter, 145 formerly KEEP rows are now excluded:
144 image-caption mentions and one hidden `data-sort-value` attribute. Caption omission was
allowed by the user. No other formerly KEEP mention was silently excluded in this comparison.
Ten formerly KEEP rows remain uncertain rather than receiving an unsafe partial-span mapping.
Three previously excluded image-field rows are now uncertain inside unsupported image syntax.

## Examples

| Original source / entity | New result |
|---|---|
| `! colspan="10"\| Japanese overseas assets in 1945`, entity `Japanese` | Header syntax removed; `Japanese` maps to `[1:9]`. |
| `'''Palawan'''`, entity `Palawan` | Bold syntax removed; entity maps to `[0:7]` in the cleaned lead. Unsupported pronunciation templates elsewhere stay flagged. |
| Citation author `Frank`, row 900716 | Reference removed from clean text; original row/text/word retained, clean offsets null. |
| `14th Naval District]]<br />[[South Pacific`, row 1386514 | Article labels and line breaks retained; original mention crosses separate links, so it stays uncertain. |
| `Agutaya`, row 1284193 | Local text is readable, but repeated source placement is not guessed; uncertain. |
| `Philippine&ndash;American War`, row 1386523 | Working word becomes `Philippine–American War`; original stays in `word_original`. |
| `June&nbsp;11,&nbsp;1978`, row 1284949 | Working word uses decoded nonbreaking spaces; no date relationship or QID is inferred. |

## Verification and issues fixed

- **70 focused tests passed**, including row preservation, repeated names, Unicode/entity spans,
  inherited bibliography sections, cut-out table/reference lines and source-order checks.
- Ruff passed; Black checked the two new Python files.
- Independent read-only review found and verified fixes for prose punctuation stripped at parser
  node boundaries, escaped category/file links, merged block text, unsupported syntax damage
  and overbroad behavior-switch deletion.
- Ship insertion anchors were corrected after the first real run exposed source-order problems.
- A Windows test-fixture newline mismatch was fixed by writing exact raw bytes; production hash
  checks were retained.
- Every final mapped slice equals its working entity word. All other clean offsets are null.
- Original columns except working `word` compare equal, and original words compare equal to
  `word_original`. Input, raw-source and final code hashes were checked again after the run.

## Boundaries and decisions

- Use original `selected_mentions.parquet`, not previously repaired words. This prevents a
  text cleaner from silently reversing earlier name repairs. Other input columns remain intact.
- Keep repeated/nonexact source placements uncertain. Local readability is not proof of the
  original occurrence. This can retain more review cases but avoids false positions.
- Keep factual table header text because headers can name entities. Only syntax and attributes
  are removed.
- This reuses the installed raw-wikitext parser and project rules; it does not deploy FineWiki's
  full HTML/S3/Slurm stack or copy its full extraction code.
- It is not historical template rendering. Infobox values are extracted from raw fields; their
  inclusion does not prove that a particular template revision displays them.
- Unsupported constructs can remain partly raw. Their original `Text` is always preserved, and
  affected contexts/mentions are flagged. Do not treat all `Text_clean` values as fully rendered.
- This step does not expand a name fragment into a new identity, select a QID, retrain or run
  the model. Matching code still needs an explicit future change to consume the clean fields.

## Time, cost and protection

The approved estimate was 45–90 minutes total elapsed execution, model-derived, including
preflight and excluding approval/environment waits. Preflight began at 22:45:45 on 29 October
2026, Asia/Jerusalem (UTC+02). The final data run began at 23:03:41 and took **5.515 seconds**
inside the script (about seven seconds including process startup). Earlier successful data runs
took 5.562 and 5.609 seconds. The initial blocked run wrote no completed dataset.

Active development time and approval wait were not separately measured; they remain unknown.
No environment wait, network collection, installation, GPU, training, inference or paid query
was used. Added cloud cost: **US$0**.

Protection: **Local checkpoint only**. The branch and worktree are retained; no push or merge
was requested. The ignored local Parquet outputs are not protected on GitHub. The final
completion timestamp is recorded in the plan ledger and final handoff.
