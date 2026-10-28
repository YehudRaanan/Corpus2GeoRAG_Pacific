"""Prepare public training examples and the unchanged ten-page inference pool."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import pickle
import random
import zipfile
from pathlib import Path

import pyarrow.parquet as pq

from data import candidates_unique, normalized, sha256, write_jsonl

LOG = logging.getLogger(__name__)


class DataOnlyUnpickler(pickle.Unpickler):
    """The public candidate artifact contains primitive dictionaries only."""
    def find_class(self, module, name):
        raise ValueError(f"Refuse executable pickle global {module}.{name}")


def context_window(text: str, start: int, end: int) -> str:
    return text[max(0, start-400):start] + " [MENTION] " + text[start:end] + " [/MENTION] " + text[end:end+400]


def prepare_sample(source: Path, out: Path) -> set[int]:
    b = pq.read_table(source / "selected_b_mentions.parquet").to_pandas()
    an = pq.read_table(source / "graph_a_qid/nodes.parquet").to_pandas()
    ap = pq.read_table(source / "graph_a_qid/node_page_presence.parquet").to_pandas().merge(an, on="node_id")
    metadata = json.loads((source / "selected_wikidata_metadata.json").read_text(encoding="utf-8"))
    occ = pq.read_table(source / "qid_occurrence_evidence.parquet").to_pandas()
    rows, refs = [], []
    for (page, word, kind), group in b.groupby(["wiki_page_id", "word", "entity_group"], sort=True):
        candidates = []
        for a in ap.loc[ap.wiki_page_id.eq(page)].sort_values("qid").itertuples():
            md = metadata[a.qid]
            aliases = sorted(set([md.get("label", ""), *md.get("aliases", []), *a.native_names]))
            # Descriptions absent in saved source: do not invent or fetch newer text.
            candidates.append({"id": a.qid, "name": a.name,
                               "description": "Also known as: " + "; ".join(x for x in aliases if x and x != a.name)[:220]})
        contexts = list(dict.fromkeys(context_window(r.Text, int(r.start), int(r.end)) for r in group.itertuples()))
        row_id = f"{int(page)}:{int(group.wiki_revision_id.iloc[0])}:{kind}:{word}"
        row = {"id": row_id, "document_id": str(int(page)), "wiki_page_id": int(page),
               "wiki_revision_id": int(group.wiki_revision_id.iloc[0]),
               "source_title": group.Source.iloc[0], "mention": word, "type": kind,
               "context": " Alternative context: ".join(contexts)[:1900],
               "contexts": contexts, "candidates": candidates_unique(candidates)}
        rows.append(row)
        linked = occ.loc[occ.wiki_page_id.eq(page) & occ.anchor_text.map(normalized).eq(normalized(word))]
        qids = sorted(set(linked.qid))
        refs.append({"id": row_id, "target": None, "verified": False,
                     "proposed_direct_anchor_qids": qids,
                     "reference_method": "AWAITING_CONTEXT_REVIEW",
                     "labelled_before_predictions": True})
    assert len(rows) == 642 and len(b) == 882 and b.wiki_page_id.nunique() == 10
    write_jsonl(out / "sample.jsonl", rows)
    write_jsonl(out / "reference_proposals.jsonl", refs)
    # Compact, prediction-free review file with every pool and source context.
    with (out / "reference_review.txt").open("x", encoding="utf-8") as stream:
        for page in sorted(b.wiki_page_id.unique()):
            subset = [r for r in rows if r["wiki_page_id"] == page]
            stream.write(f"\nPAGE {page} {subset[0]['source_title']}\n")
            stream.write("POOL " + json.dumps(subset[0]["candidates"], ensure_ascii=False) + "\n")
            for row in subset:
                ref = next(x for x in refs if x["id"] == row["id"])
                stream.write(json.dumps({"id": row["id"], "word": row["mention"], "type": row["type"],
                    "anchor_qids": ref["proposed_direct_anchor_qids"], "context": row["context"]}, ensure_ascii=False) + "\n")
    files = ["selected_b_mentions.parquet", "selected_revisions.parquet", "selected_wikidata_metadata.json",
             "qid_occurrence_evidence.parquet", "graph_a_qid/nodes.parquet", "graph_a_qid/node_page_presence.parquet"]
    manifest = {"source_root": str(source), "files": {n: sha256(source/n) for n in files},
                "test_records": len(rows), "original_mentions": len(b), "source_pages": 10,
                "full_corpus_rerun": False, "unresolved_pages_unchanged": 545}
    (out / "sample_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return set(int(p) for p in b.wiki_page_id)


def prepare_public(archive: Path, out: Path, excluded_pages: set[int], train_limit: int, val_limit: int) -> None:
    rng = random.Random(20261028)
    with zipfile.ZipFile(archive) as z:
        LOG.info("Loading data-only public candidate dictionary")
        counter = DataOnlyUnpickler(z.open("zelda/other/zelda_mention_entities_counter.pickle")).load()
        LOG.info("Public mention keys: %s", len(counter))
        docs = []
        with z.open("zelda/train_data/zelda_train.jsonl") as stream:
            for line in stream:
                d = json.loads(line)
                page = int(d["page_id"])
                # Deterministic source-page sampling and source-page-disjoint validation.
                if page in excluded_pages:
                    continue
                rank = int(hashlib.sha256(str(page).encode()).hexdigest()[:8], 16)
                if rank % 100 < 12:
                    docs.append(d)
        rng.shuffle(docs)
        output = {"train": [], "validation": [], "public_test": []}
        limits = {"train": train_limit, "validation": val_limit, "public_test": 900}
        split_docs = {k: set() for k in output}
        needed = set()
        fallback = ["United States", "World War II", "Paris", "Apple Inc.", "George Washington", "Japan", "London", "Football"]

        def make(d: dict, split: str, document_id: str) -> None:
            indices = list(range(len(d["index"])))
            rng.shuffle(indices)
            for i in indices[:12]:
                if len(output[split]) >= limits[split]:
                    break
                start, end = d["index"][i]
                mention = d["text"][start:end]
                gold = d["wikipedia_titles"][i].replace("_", " ")
                if not mention.strip() or not gold or gold.startswith("--"):
                    continue
                raw = counter.get(mention) or counter.get(mention.lower()) or {}
                if not isinstance(raw, dict):
                    raise ValueError("Unexpected public candidate artifact structure")
                ranked = [k.replace("_", " ") for k in sorted(raw, key=lambda k: (-raw[k], k))]
                count = rng.randint(2, 8)
                # Explicit candidate-removal examples train the NONE decision.
                synthetic_none = rng.random() < .30
                if split == "train" and not synthetic_none and gold not in ranked[:count]:
                    ranked = [gold] + ranked
                names = list(dict.fromkeys(n for n in ranked if n != gold or not synthetic_none))
                names += [n for n in fallback if n not in names and (n != gold or not synthetic_none)]
                names = names[:count]
                rng.shuffle(names)
                target = gold if gold in names else None
                section_hash = hashlib.sha256(d["text"].encode()).hexdigest()[:12]
                record = {"id": f"{split}:{document_id}:{section_hash}:{i}", "document_id": document_id,
                          "mention": mention, "context": context_window(d["text"], start, end),
                          "candidates": [{"id": n, "name": n} for n in names],
                          "target": target, "gold_entity_name": gold, "verified": True,
                          "synthetic_none": synthetic_none, "candidate_source": "ZELDA_PUBLIC_COUNTER"}
                # Record injection against the actual popularity-ranked public pool.
                natural = sorted(raw, key=lambda k: (-raw[k], k))[:count]
                record["gold_injected"] = split == "train" and not synthetic_none and gold not in [n.replace('_',' ') for n in natural]
                output[split].append(record)
                split_docs[split].add(document_id)
                needed.update(names)

        for d in docs:
            page = int(d["page_id"])
            split = "validation" if int(hashlib.sha256(str(page).encode()).hexdigest()[:8], 16) % 10 == 0 else "train"
            make(d, split, f"wiki:{page}")
            if len(output["train"]) >= train_limit and len(output["validation"]) >= val_limit:
                break
        for name in sorted(z.namelist()):
            if "/test_data/jsonl/" in name and name.endswith(".jsonl"):
                limits["public_test"] = len(output["public_test"]) + 100
                with z.open(name) as stream:
                    # A bounded diagnostic sample across all nine public splits.
                    for j, line in enumerate(stream):
                        if j >= 12:
                            break
                        d = json.loads(line)
                        make(d, "public_test", f"{Path(name).stem}:{d['id']}")
        counter.clear()
        docs.clear()
        LOG.info("Reading descriptions for %s selected entity names", len(needed))
        descriptions = {}
        with z.open("zelda/other/entity_descriptions.jsonl") as stream:
            for line in stream:
                d = json.loads(line)
                name = d["wikipedia_title"].replace("_", " ")
                if name in needed:
                    descriptions[name] = d.get("description", "")[:600]
        for split, records in output.items():
            for row in records:
                for c in row["candidates"]:
                    c["description"] = descriptions.get(c["name"], "")
            write_jsonl(out / f"{split}.jsonl", records)
        assert not split_docs["train"] & split_docs["validation"]
        manifest = {"archive_sha256": sha256(archive), "seed": 20261028,
                    "test_source_page_ids_excluded": sorted(excluded_pages),
                    "train_validation_source_pages_disjoint": True,
                    "public_test_is_bounded_diagnostic_not_full_ZELDA_benchmark": True,
                    "counts": {k: len(v) for k,v in output.items()},
                    "synthetic_none": {k: sum(r["synthetic_none"] for r in v) for k,v in output.items()},
                    "candidate_count_range": [2, 8], "training_same_page_restriction": False,
                    "files": {f"{k}.jsonl": sha256(out/f"{k}.jsonl") for k in output}}
        (out / "public_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        LOG.info("Prepared %s", manifest["counts"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--train-limit", type=int, default=30000)
    p.add_argument("--val-limit", type=int, default=1200)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    pages = prepare_sample(a.source, a.out)
    prepare_public(a.archive, a.out, pages, a.train_limit, a.val_limit)
