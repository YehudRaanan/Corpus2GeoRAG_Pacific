# Japanese names and quotation attribution: 100-page rerun

## Result

The cleaner now preserves Japanese name variants, romanized names, and displayed
quotation attributions. All 40,070 original rows across 100 pages and 132 saved
historical revisions were processed. Original source text, offsets and QID
assignments are unchanged. This run measures cleaning, not QID resolution.

## Changes

- `filter_source_content.py`: one shared set of supported template field groups
  and a selector used by both classification and cleaning; policy `article-source-v3`.
- `clean_source_text.py`: uses those rules and inserts source-anchored separators
  between fields; policy `source-text-v3`. The earlier ship-class exception remains.
- Existing test files: protect names, attribution, source order, separators,
  citations, conflicting aliases, unknown fields and malformed templates.

`nihongo` retains English, Japanese, romanization and supported extra display
fields. `nihongo2` has its own one-content-field rule. Blockquote/quote/quotation
retain body, author, title, source and supported speaker fields; Quote box retains
body, title, author and source. These are displayed source fields, not additional
QID entities. Fresh Wikidata language collection is unchanged.

Ambiguous alternative keys, unsupported fields or incomplete required content
remain literal with REVIEW status. We do not guess alias precedence. `cquote`
remains literal/review because its positional meanings vary; none occur in this
pilot. Fields stay in raw source order so character origins remain monotonic.
This is plain-text projection, not exact historical template rendering.

Nested `<ref>` and citation templates remain removed. Retaining a displayed
quotation author/title does not unmask the reference record that follows it.

## Full 100-page output

| Cleaning status | Rows |
|---|---:|
| Retained with valid cleaned positions | 23,239 |
| Removed from cleaned text under source policy | 14,884 |
| Still uncertain | 1,947 |
| Total | 40,070 |

Removed rows remain in the Parquet with original text and metadata. These are
rule outcomes, not a claim that every removal is manually verified irrelevant.

## Original unresolved baseline comparison

Fixed denominator: 19,071 original unresolved non-DATE mentions. Compare with
the previous `source-text-v2` run, which already fixed ship-class fields:

| Status | Previous | New |
|---|---:|---:|
| Retained with valid cleaned positions | 9,539 | 9,555 |
| Removed | 8,319 | 8,300 |
| Uncertain | 1,213 | 1,216 |

Sixteen previously removed non-DATE mentions now map to cleaned text; three
others now retain text but remain uncertain because their original spans cross
markup or template fields. There are no mapped-to-excluded changes in this
baseline subset. All 16 earlier ship-class cases remain mapped.

Examples:

- Row 73530: `James Forrestal` survives quotation attribution.
- Row 1574485: `William F. Halsey` survives; row 1574486 keeps `South Pacific Forces`.
- Row 1006323: `Kumaichi` survives the romanized name field in `nihongo`.
- Row 1463142: `片桐 茂|Katagiri` remains uncertain because the original mention
  crosses a template parameter boundary; no combined entity name is invented.
- Row 1470405: `Shōji|extra` remains uncertain; a parameter key is not a name.

Some restored spans are original fragments, translations or book titles, not
complete entity names. Their final identities still need the matching stage.

DATE stays separate: 3,933 retained, 3,190 removed, 249 uncertain. Ten additional
date spans survive cleaning; no temporal interpretation or date linking was done.

## Verification and artifacts

- 193 cleaner/source-filter tests pass; 16 pipeline/layout checks pass.
- Ruff and Black checks pass for changed code/tests.
- Every original row/column except working `word` is preserved; `word_original`
  exactly equals the original word. No QID assignment changes.
- Every mapped slice equals its working word; nonmapped clean offsets are null.
- All input and historical raw-revision hashes pass; full-run and unresolved
  subset produce identical cleaning fields for the same original source row.
- Final cleaner elapsed times: full sample 13.625 seconds; unresolved subset
  16.031 seconds. These are script times, not total active work. Cloud cost US$0.

Output directory:
`Data/external/hundred_page_pilot_20261028/source_text_cleaner_name_attribution_20261029/`

- `full_100_v2/mentions.parquet`: final full pilot output.
- `baseline_unresolved_v2/mentions.parquet`: same cleaning on the original
  26,443-row unresolved export (19,071 non-DATE plus 7,372 DATE).
- Each output has `summary.json` and `used_revisions.parquet` with provenance.
- `verification.json`, `changed_decisions.json`, and `analyse.py` provide counts,
  all changed baseline statuses, hashes and repeatable checks.
- Earlier non-v2 directories are intermediate runs retained for audit.

The full Parquet SHA256 is
`e1a152915ae751a3a310e3f261006a44990932e0a7538908b89a127af2139284`.
The unresolved subset SHA256 is
`b46807c3af9ecce7f3294e583b7149e01a10d7a61fc6e42fa72016fe84d3806c`.

## Sources and limits

Field rules were checked against official [Nihongo module](https://en.wikipedia.org/w/index.php?title=Module:Nihongo&action=raw),
[Nihongo2 source](https://en.wikipedia.org/w/index.php?title=Template:Nihongo2&action=raw),
[Blockquote source](https://en.wikipedia.org/w/index.php?title=Template:Blockquote&action=raw),
and [Quote box source](https://en.wikipedia.org/w/index.php?title=Template:Quote_box&action=raw).
These sources describe current rules; the test uses saved historical article text
and does not claim to reconstruct every historical template implementation.
Unknown cases stay reviewable. No model inference, collection or cloud work ran.

Backup: Local checkpoint only for code/report; ignored generated data remains
local and is not protected on GitHub.
