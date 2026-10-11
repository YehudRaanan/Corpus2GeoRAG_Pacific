# Non-text relation candidate manual review

Date: 2026-10-11

## Scope

- 26 fixed cases selected across the main infobox patterns.
- All three cases without an empirical field mapping.
- Both qualifier-only cases.
- All four cases recovered from nested ship infoboxes.
- This is a stratified diagnostic sample, not a random accuracy sample.

## Review rule

- Compare the highest-ranked relation with the source field, entity type, and Wikidata property definition.
- `ACCEPTED` means the highest-ranked relation fits the evidence.
- `REJECTED` means another relation fits better or the allowed list omitted it.
- `UNRESOLVED` means the evidence does not prove a direct relation.

## Results

- Accepted: **13**
- Rejected: **7**
- Unresolved: **6**
- Cases with a ranked top candidate: **21**
- Accepted top candidates: **13 of 21**
- Do not treat this ratio as corpus accuracy because the sample is stratified.

## What worked

- Ship `country` with only `P8047` available: four recovered cases accepted.
- `allegiance` with `P945` available: four reviewed cases accepted.
- Military-unit `country` with only `P17` available: three reviewed cases accepted.

## Failure patterns

- Global field counts rank `P495` above `P8047` for some ships. The ship context supports `P8047`.
- Sparse type-pair seeds can remove `P945` even when the field is explicitly `allegiance`.
- A country name inside `garrison`, `builder`, `fate`, or `captured` can describe a nested fact instead of the direct relation.
- A Wikidata qualifier target is not the direct value of the main property.

## Required next logic

1. Rank with the infobox field and subject type together.
2. Keep the field-semantic relation available even when type-pair seeds are sparse.
3. Treat nested fields and qualifier paths as separate relation structures.
4. Allow `UNRESOLVED`.

## File

- `non_text_manual_review/review_cases.csv`
