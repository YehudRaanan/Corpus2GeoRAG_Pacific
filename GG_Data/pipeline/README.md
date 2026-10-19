# Daniel pipeline POC

Contract order: [population S2T](../../docs/SOURCES_TO_ENTITY_DATA_MODEL_S2T.md),
[ERD](../../docs/ENTITY_DATA_MODEL_ERD.md), then
[model-to-graph S2T](../../docs/ENTITY_MODEL_TO_AGENT_GRAPH_S2T.md).

## Implemented first step

`poc.py` selects 10,000 original row positions without replacement (fixed seed
20261018), verifies pinned input and matching artifacts, and copies unchanged
saved matching decisions into Mentions. It retains resolved English/Japanese
Wiki Pages and failed page requests. Original text is evidence only; no text
extraction, rematching, splitting, combining, network request, or new identity
is performed. Synthetic rows retain their original IDs and use Daniel's type
when the saved resolved type is null. Saved type metadata stays unchanged.

Any unexpected count, field, source hash, ID, score, page conflict or missing
artifact raises an error. Stop and discuss the exact case with the user before
changing a rule. No automatic repair or retry is implemented.

**Execution is on hold until the user approves POC data output on D:.** More
free space is not approval. The command below is for use only after approval:

```powershell
C:\Users\User\anaconda3\python.exe -B -m GG_Data.pipeline.poc --output D:\Projects\GeoAI\GG_Data\pipeline\outputs\poc_10k --output-approved
```

The output directory must be new; existing output is never overwritten. The
manifest marks only `STEP_1_ONLY`. Partial files without that manifest are not
a completed step. Entities, Events, Relations, Geography, final graph export
and Agent integration remain pending. Wiki Pages `about_entity_id` is populated
only after the later Entities stage establishes membership. This is not a
six-table release, a fresh matching run or a completed 10K POC.

## Approved graph interfaces

`graph_contract.py` provides small interface helpers:

- Distinct QID/type nodes use `QID::type`, keeping `wikidata_id` separately.
  Existing per-mention synthetic IDs stay unchanged.
- A QID endpoint index returns all its separate typed node IDs. Relations and
  source assertion counts are not expanded across these nodes.
- `geometry_ref` is null or `{file, place_id, sha256}`. The referenced GeoParquet
  must contain exactly one valid nonempty geometry for the place and known CRS.
  `load_geometry(pointer, artifact_root)` returns its Shapely object. Broken
  pointers fail explicitly. No GeoJSON conversion or CRS transformation occurs.

These helpers are not yet connected to the current Agent engine. Its full query
path and spatial CRS requirements must be verified before graph acceptance.

Run the in-memory checks (no Daniel data output):

```powershell
C:\Users\User\anaconda3\python.exe -B -m pytest -q -p no:cacheprovider GG_Data/pipeline/test_pipeline.py
```
