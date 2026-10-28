"""Budget-bounded frozen-head training, conditional full fine-tuning, inference."""

from __future__ import annotations

import argparse
import json
import logging
import random
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from data import metric_summary, read_jsonl, runtime_allowed, sha256, stable_head, write_jsonl
from model import CandidateScorer, grouped_loss, pair_texts

LOG = logging.getLogger(__name__)
MODEL = "studio-ousia/luke-base"
REVISION = "7438924defd9f3c2018d63c16073bf4bcb6a70aa"


class Runner:
    def __init__(self, args):
        self.args = args
        self.start = time.monotonic()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if self.device.type != "cuda":
            raise RuntimeError("Full pilot requires CUDA; CPU is reserved for contract tests")
        torch.manual_seed(20261028)
        np.random.seed(20261028)
        random.seed(20261028)
        torch.set_num_threads(4)
        args.output.mkdir(parents=True, exist_ok=True)
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
        self.model = CandidateScorer(AutoModel.from_pretrained(MODEL, revision=REVISION)).to(self.device)
        self.encoder_pristine = True
        self.history = []
        self.save_json("hardware.json", {"torch": torch.__version__, "cuda": torch.version.cuda,
            "device": torch.cuda.get_device_name(), "gpu_memory": torch.cuda.get_device_properties(0).total_memory,
            "model": MODEL, "revision": REVISION,
            "encoder_parameters": sum(p.numel() for p in self.model.encoder.parameters()),
            "head_parameters": sum(p.numel() for p in self.model.scorer.parameters()),
            "entity_inputs": "text-only CLS pair encoder; no QID input or entity-vocabulary ID input"})

    def guard(self):
        if not runtime_allowed(self.start, time.monotonic(), self.args.max_hours, .73, 2., 15.):
            raise TimeoutError("Worker time/cost guard reached; preserve checkpoints and stop")

    def amp(self):
        return torch.autocast("cuda", dtype=torch.bfloat16)

    def save_json(self, name, value):
        (self.args.output/name).write_text(json.dumps(value, indent=2), encoding="utf-8")

    def inputs(self, rows):
        first, second, sizes, targets = [], [], [], []
        for row in rows:
            a, b, target = pair_texts(row)
            first.extend(a)
            # Keep candidate text bounded so query-only truncation always has room.
            second.extend(s[:650] for s in b)
            sizes.append(len(a))
            targets.append(target)
        encoded = self.tokenizer(first, second, padding=True, truncation=True,
                                 max_length=self.args.max_length, return_tensors="pt")
        return {k: v.to(self.device) for k,v in encoded.items()}, sizes, targets

    def cache(self, rows, name):
        self.model.freeze_encoder(True)
        features, sizes, targets = [], [], []
        # Tokenise one question at a time but encode a bounded number of pairs.
        for i in range(0, len(rows), 8):
            self.guard()
            encoded, n, t = self.inputs(rows[i:i+8])
            with torch.no_grad(), self.amp():
                f = self.model.encode(**encoded)
            features.append(f.detach().half().cpu())
            sizes.extend(n)
            targets.extend(t)
            if i % 1000 == 0:
                LOG.info("Encoding %s: %s/%s questions", name, i, len(rows))
        cached = {"features": torch.cat(features), "sizes": sizes, "targets": targets,
                  "offsets": np.r_[0, np.cumsum(sizes)].tolist()}
        torch.save(cached, self.args.output/f"{name}_features.pt")
        return cached

    def cache_batch(self, cache, indices):
        offsets = cache["offsets"]
        features = torch.cat([cache["features"][offsets[i]:offsets[i+1]] for i in indices]).to(self.device).float()
        return features, [cache["sizes"][i] for i in indices], [cache["targets"][i] for i in indices]

    def evaluate(self, rows, cache=None):
        self.model.eval()
        predictions, losses = [], []
        for i in range(0, len(rows), 32 if cache else 4):
            self.guard()
            indices = list(range(i, min(i+(32 if cache else 4), len(rows))))
            with torch.no_grad():
                if cache:
                    f, sizes, targets = self.cache_batch(cache, indices)
                    logits = self.model.scorer(f).squeeze(-1)
                else:
                    encoded, sizes, targets = self.inputs([rows[j] for j in indices])
                    with self.amp():
                        logits = self.model(**encoded)
                losses.append((float(grouped_loss(logits.float(), sizes, targets)), len(indices)))
            for j, group in zip(indices, logits.float().split(sizes)):
                ids = [x["id"] for x in rows[j]["candidates"]] + [None]
                probs = group.softmax(-1).cpu().tolist()
                chosen = int(group.argmax())
                order = sorted(range(len(ids)), key=lambda k: -probs[k])
                predictions.append({"id": rows[j]["id"], "prediction": ids[chosen],
                    "confidence": probs[chosen], "none_probability": probs[-1],
                    "candidate_count": len(ids)-1,
                    "ranking": [{"id": ids[k], "probability": probs[k]} for k in order]})
        metrics = metric_summary(rows, predictions) if all("target" in r for r in rows) else {"total": len(rows)}
        metrics["loss"] = sum(x*n for x,n in losses)/sum(n for _,n in losses)
        return metrics, predictions

    def checkpoint(self, name):
        # The frozen encoder is exactly the pinned public checkpoint.
        state = self.model.scorer.state_dict() if name.startswith("frozen") else self.model.state_dict()
        torch.save({"model": state, "head_only": name.startswith("frozen"), "model_id": MODEL, "revision": REVISION},
                   self.args.output/f"{name}.pt")

    def load(self, name):
        ck = torch.load(self.args.output/f"{name}.pt", map_location=self.device, weights_only=True)
        if ck["head_only"]:
            if not self.encoder_pristine:
                # Restore the original encoder if a full-stage run did not improve.
                original = AutoModel.from_pretrained(MODEL, revision=REVISION)
                self.model.encoder.load_state_dict(original.state_dict())
                del original
                self.encoder_pristine = True
            self.model.scorer.load_state_dict(ck["model"])
        else:
            self.model.load_state_dict(ck["model"])
            self.encoder_pristine = False

    def train(self):
        train = read_jsonl(self.args.inputs/"train.jsonl")
        val = read_jsonl(self.args.inputs/"validation.jsonl")
        assert not {r["document_id"] for r in train} & {r["document_id"] for r in val}
        for rows in (train, val):
            assert len({r["id"] for r in rows}) == len(rows)
        tc, vc = self.cache(train, "train"), self.cache(val, "validation")
        opt = torch.optim.AdamW(self.model.scorer.parameters(), lr=5e-4, weight_decay=.01)
        best, val_losses = float("inf"), []
        head_stable = False
        for epoch in range(40):
            self.model.train()
            order = np.random.permutation(len(train))
            training_losses = []
            for i in range(0, len(order), 64):
                self.guard()
                f, sizes, targets = self.cache_batch(tc, order[i:i+64])
                opt.zero_grad(set_to_none=True)
                loss = grouped_loss(self.model.scorer(f).squeeze(-1), sizes, targets)
                if not torch.isfinite(loss):
                    raise RuntimeError("Non-finite head loss")
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.scorer.parameters(), 1.)
                opt.step()
                training_losses.append(float(loss.detach()))
            metrics, _ = self.evaluate(val, vc)
            val_losses.append(metrics["loss"])
            head_stable = stable_head(val_losses)
            event = {"stage": "frozen", "epoch": epoch+1, "train_loss": float(np.mean(training_losses)),
                     "encoder_trainable": False, "head_stable": head_stable, **metrics}
            self.history.append(event)
            self.save_json("training_history.json", self.history)
            LOG.info("VALIDATION %s", json.dumps(event))
            if metrics["loss"] < best:
                best = metrics["loss"]
                self.checkpoint("frozen_best")
            if head_stable:
                break
            # Reduce new-layer LR after initial fitting to permit a stable plateau.
            if epoch in (7, 15, 23, 31):
                for g in opt.param_groups:
                    g["lr"] *= .5
        self.load("frozen_best")
        frozen_metrics, frozen_predictions = self.evaluate(val, vc)
        self.save_json("frozen_validation.json", frozen_metrics)
        write_jsonl(self.args.output/"frozen_validation_predictions.jsonl", frozen_predictions)
        needs_full = not ((frozen_metrics["accuracy"] or 0) >= .9 and (frozen_metrics["none_precision"] or 0) >= .9)
        decision = {"head_stable": head_stable, "frozen_targets_met": not needs_full,
                    "unfreeze_authorised": needs_full and head_stable,
                    "reason": "validation only; ten-page references/predictions not consulted"}
        self.save_json("unfreeze_decision.json", decision)
        final = "frozen_best"
        if needs_full and head_stable:
            del tc, vc
            torch.cuda.empty_cache()
            self.model.freeze_encoder(False)
            self.encoder_pristine = False
            self.model.encoder.gradient_checkpointing_enable()
            opt = torch.optim.AdamW([
                {"params": self.model.encoder.parameters(), "lr": 1e-5},
                {"params": self.model.scorer.parameters(), "lr": 1e-4}], weight_decay=.01)
            full_best = best
            for epoch in range(2):
                self.model.train()
                order = np.random.permutation(len(train))
                opt.zero_grad(set_to_none=True)
                losses = []
                for step, i in enumerate(range(0, len(order), 4)):
                    self.guard()
                    rows = [train[j] for j in order[i:i+4]]
                    encoded, sizes, targets = self.inputs(rows)
                    with self.amp():
                        loss = grouped_loss(self.model(**encoded).float(), sizes, targets)
                    if not torch.isfinite(loss):
                        raise RuntimeError("Non-finite full fine-tuning loss")
                    (loss/8).backward()
                    losses.append(float(loss.detach()))
                    if (step+1) % 8 == 0 or i+4 >= len(order):
                        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.)
                        opt.step()
                        opt.zero_grad(set_to_none=True)
                    if (step+1) % 100 == 0:
                        LOG.info("Full epoch %s batch %s/%s loss %.4f", epoch+1, step+1, len(order)//4, np.mean(losses[-100:]))
                    if (step+1) % 1500 == 0 or i+4 >= len(order):
                        metrics, _ = self.evaluate(val)
                        event = {"stage": "full", "epoch": epoch+1, "batch": step+1,
                                 "encoder_trainable": True, "train_loss": float(np.mean(losses[-1500:])), **metrics}
                        self.history.append(event)
                        self.save_json("training_history.json", self.history)
                        LOG.info("VALIDATION %s", json.dumps(event))
                        if metrics["loss"] < full_best:
                            full_best = metrics["loss"]
                            self.checkpoint("full_best")
                            final = "full_best"
                        self.model.train()
            self.load(final)
        elif needs_full:
            LOG.warning("Head did not reach stability: encoder remains frozen")
        self.model.freeze_encoder(True)
        for split in ["validation", "public_test"]:
            rows = read_jsonl(self.args.inputs/f"{split}.jsonl")
            metrics, predictions = self.evaluate(rows)
            write_jsonl(self.args.output/f"final_{split}_predictions.jsonl", predictions)
            self.save_json(f"final_{split}_metrics.json", metrics)
        self.save_json("training_complete.json", {"final_checkpoint": final, "head_stable": head_stable,
            "elapsed_worker_seconds": time.monotonic()-self.start,
            "inputs_manifest_sha256": sha256(self.args.inputs/"public_manifest.json"),
            "test_not_used_for_training_or_selection": True})

    def infer(self):
        complete = json.loads((self.args.output/"training_complete.json").read_text())
        references_path = self.args.inputs/"references.jsonl"
        frozen = json.loads((self.args.inputs/"reference_freeze.json").read_text())
        if sha256(references_path) != frozen["sha256"]:
            raise ValueError("Reference labels changed after freeze")
        rows = read_jsonl(self.args.inputs/"sample.jsonl")
        self.model.freeze_encoder(True)
        self.load("frozen_best")
        _, frozen_predictions = self.evaluate(rows)
        write_jsonl(self.args.output/"frozen_sample_predictions.jsonl", frozen_predictions)
        refs = read_jsonl(references_path)
        self.save_json("frozen_sample_metrics.json", metric_summary(refs, frozen_predictions))
        self.load(complete["final_checkpoint"])
        metrics, predictions = self.evaluate(rows)
        write_jsonl(self.args.output/"sample_predictions.jsonl", predictions)
        result = metric_summary(refs, predictions)
        result["reference_sha256"] = frozen["sha256"]
        result["test_records"] = len(rows)
        self.save_json("sample_metrics.json", result)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["train", "infer"])
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-hours", type=float, default=7.)
    p.add_argument("--max-length", type=int, default=256)
    args = p.parse_args()
    run = Runner(args)
    getattr(run, args.mode)()
