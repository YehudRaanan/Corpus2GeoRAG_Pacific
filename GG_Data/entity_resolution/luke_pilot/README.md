# LUKE candidate decision pilot

This development experiment tests 642 Daniel entity-page records from ten saved
Wikipedia revisions. It does not change the original Parquet, rebuild graphs,
rerun the corpus, or change the 545 unresolved source pages.

## Model and training

`studio-ousia/luke-base` is loaded at revision
`7438924defd9f3c2018d63c16073bf4bcb6a70aa`. The encoder receives a text pair:
the mention with marked source context, and one candidate name with description
or saved aliases. Its first token representation feeds a shared
LayerNorm → Linear → GELU → Linear scalar head. Each option, including NONE,
uses the same encoder and head. Grouped cross-entropy compares the option scores.
The number of options can vary. QID values do not enter the model text.

This is a JEV-style per-option decision model. It is not a reproduction of JEV
or Laya's joint marker architecture. LUKE is used as a **text-only encoder**;
its entity vocabulary and entity span inputs are not used.

The public ZELDA archive supplies 30,000 training and 1,200 validation records.
They are disjoint by source page. Candidate pools contain 2–8 names, with public
mention-frequency negatives and 30% probabilistic removal of the gold entity to
create explicitly marked synthetic NONE cases. Gold injection is allowed only
for non-NONE training records and is recorded. Training does not require that
all candidates occur on the same page. A separate 408-record public test is a
bounded diagnostic, not the full ZELDA benchmark.

All encoder parameters are initially frozen; cached deterministic representations
train only the new head. Stability requires three consecutive validation-loss
changes of at most 1%, with at least four observations. After at most 40 head
epochs, full tuning is allowed only when stability holds and either validation
selection accuracy or NONE precision is below 90%. The full stage uses lower
encoder learning rate and at most two epochs. Checkpoint selection uses validation
loss only. Test labels and test predictions never select a checkpoint or trigger
further training.

Ten-page source IDs are excluded from training. A text-overlap check found no
matches between 79 long saved source blocks and the prepared training contexts.
This does not prove absence of paraphrase overlap or pretraining contamination.
LUKE and ZELDA predate the saved Wikipedia revisions. Public candidate descriptions
also differ from the saved test metadata, where only labels and aliases exist.

## Ten-page evaluation

The test contains all 642 unique page + Daniel name + native type records,
covering 882 original mentions. Every candidate is a QID in graph A on the same
saved page and revision. The entire pool is scored, rather than a fixed top five.
Graph connection scores and trigram scores are not model inputs.

Reference identities were reviewed from saved text, link evidence and metadata
before any model predictions. The reference file is hash-frozen:

`87f5e1c74b2c89bd17a4f3a3c70c0a21d8441abb11c0cf2bce52a42f82caff72`

Of 642 records, 551 are verified by assistant source review: 217 linked identities
and 334 NONE. The remaining 91 are unverified and excluded from accuracy. This
review is independent of predictions, **not independent human annotation**.
No result on 551 references is presented as accuracy on all 642 records.

NONE means that the same entity is absent from the saved same-page candidate
pool. It does not mean that Wikidata has no such entity. Generic terms, invalid
spans and dates without a candidate are retained with explicit reference methods.
Candidate-reference counts therefore do not measure global Wikidata recall.

The evaluation compares the frozen head, the selected final checkpoint, and the
previously saved trigram results. Two baseline policies are shown: always choose
the saved top result, or retain the previous exact/strong lexical acceptance rule
and use NONE otherwise. Baseline thresholds are not tuned. Saved top-result ties
keep their old order. Accuracy, linked-only accuracy, NONE precision/recall,
counts, and type/page breakdowns are reported. Wilson intervals are descriptive:
these ten pages were selected, and records within a page are not independent.

## Run and artifacts

The approved run uses one L4 in project `geo-hagai-ndvi`, at most eight GPU hours,
with automatic VM STOP. The worker has a shorter time guard and a conservative
cost forecast. These controls are not a billing-account spending cap. STOP ends
compute charges; its persistent disk still has a storage charge.

```powershell
python -m pytest GG_Data/entity_resolution/luke_pilot/test_pilot.py -q
python GG_Data/entity_resolution/luke_pilot/train.py train --inputs INPUTS --output OUTPUTS --max-hours 7
python GG_Data/entity_resolution/luke_pilot/train.py infer --inputs INPUTS --output OUTPUTS --max-hours 1
python GG_Data/entity_resolution/luke_pilot/evaluate.py --inputs INPUTS --outputs OUTPUTS --baseline SAVED_TRIGRAM_CSV --destination NEW_EVALUATION_DIRECTORY
```

Training and inference require CUDA. CPU is used only for small contract tests.
Use a new output directory for a new experiment: prediction JSONL writes are
exclusive. Inputs, checkpoints and logs are stored under the ignored
`Data/external/luke_decision_pilot_20261028` directory. The frozen checkpoint stores
the trained head plus the original encoder ID/revision; a full checkpoint stores
both head and encoder weights. The delivered decision table includes names,
QIDs, references, predictions, page IDs and exact revision IDs.

Source datasets and design references:

- https://github.com/flairNLP/zelda
- https://nlp.informatik.hu-berlin.de/resources/datasets/zelda/zelda_full.zip
- https://huggingface.co/studio-ousia/luke-base
- https://github.com/he-jev/laya/blob/main/rl_common.py
- https://cloud.google.com/products/compute/pricing/accelerator-optimized
