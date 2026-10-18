# Daniel source-page lookup — 2026-10-18

**Subsequent matching run:** [completed rerun and comparison](RESOLVED_PAGES_RUN_REPORT_2026-10-18.md).
The counts below describe the page lookup itself.

## Result

Wikipedia's official title lookup resolved **424 of 428 source titles** to a
Wikipedia page ID and Wikidata ID. The previous exact-title join resolved 239.
All 239 previous Wikidata matches agree with the live lookup. The new map adds
185 source titles covering 116,876 raw mentions. Four titles, covering 768
mentions, remain unresolved.

| Measure | Result |
|---|---:|
| Daniel raw mentions | 309,864 |
| Source titles checked | 428 |
| Resolved source titles | 424 |
| Mentions with resolved source-page identity | 309,096 |
| Newly resolved titles | 185 |
| Newly resolved titles with direct neighbours in the saved graph | 114 |
| Newly resolved titles without direct neighbours in the saved graph | 71 |
| All resolved titles without direct neighbours in the saved graph | 77 |

These counts measure source-page identity coverage, not entity-match accuracy.
The completed entity-matching output and its 301,826 unresolved mentions have
not been changed or rerun.

## Real examples

| Daniel Source | Canonical page | Wikipedia page ID | Wikidata ID | Direct graph neighbours |
|---|---|---:|---|---:|
| Franklin Roosevelt | Franklin D. Roosevelt | 10979 | Q8007 | 109 |
| Franklin Delano Roosevelt | Franklin D. Roosevelt | 10979 | Q8007 | 109 |
| Oceania | Oceania | 22621 | Q55643 | 0 |
| Vichy France | Vichy France | 20599016 | Q69808 | 27 |

The lookup resolved both alternate titles and exact titles absent from the
category-derived reference table. Of the 185 new source matches, only 39 QIDs
are in the saved Wikidata population; 146 are absent. A QID can still occur as
an endpoint of a saved assertion, as Vichy France does. A graph neighbour does
not prove that names, types, or enough context exist for useful matching.

## Remaining source titles

Wikipedia returned a missing-page result for these exact titles at lookup time:

| Source | Mentions |
|---|---:|
| BUROGU | 144 |
| Conscription in Japan | 283 |
| Gabriel Maurício Teixeira | 293 |
| Two Lords Incident | 48 |

No substitute was guessed. This does not prove that Daniel's original page
never existed. Its URL, language, or extraction revision is not supplied.

## Method and evidence

`resolve_source_pages.py` reads the actual `Source` values from Daniel's pinned
parquet, makes nine requests through the existing Wikipedia API helper, and
follows server-reported normalization and redirects. It checks missing,
disambiguation, and non-article pages, redirect cycles, absent Wikidata IDs,
and disagreements with saved page identities. It uses no fuzzy title search,
manual overrides, model calls, or new entity creation.

Output directory: `runs/source_pages_v0.1.0_20261018/`.

- `page_map.json`: all 428 original source titles, returned identities,
  canonical URLs, redirect evidence, timestamps, mention counts, old identities,
  and separate snapshot/graph coverage checks.
- `api_responses.jsonl`: complete responses, request parameters, and timestamps.
- `summary.json`: full denominators and remaining source titles.
- `run_manifest.json`: input, code, and output hashes; completion marker.

Input hashes are checked against the frozen runs and checked again at the end.
All source titles and raw mention counts are accounted for. The offline test
covers title normalization followed by a redirect, a missing page, a
disambiguation page, a missing Wikidata ID, and a redirect cycle.

Official reference: [MediaWiki title and redirect lookup](https://www.mediawiki.org/wiki/API:Query#Resolving_redirects).
This lookup reflects Wikipedia at retrieval time. It does not identify the
exact revision used by Daniel for extraction.

## Open follow-up with Daniel

Ask Daniel later to include **source URL, Wikipedia page ID, language/site,
and revision ID or permanent revision URL** in future extraction exports.
Preserve the readable source title and paragraph index. This follow-up is
recorded; no message has been sent.

## Next step and backup

Use the saved page map as an explicit input to a separate matching run after
checking missing entity metadata and graph context. Do not reinterpret source
page resolution as successful mention-level entity matching.

Backup status: **Local checkpoint only** after the accompanying commit.
The original raw/cache inputs remain under ignored `Data/external/` paths.
