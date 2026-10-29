"""Train the reverse LUKE scorer with cached warmup and definite encoder tuning.

Read hash-frozen public JSONL, cache each independent pair once, train the head
until the approved validation stability condition, then tune all encoder/head
weights. Save optimizer, RNG, data hashes and exact next-step progress for restart.
CUDA execution belongs to the root operator; CPU imports support contract tests.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from GG_Data.entity_resolution.decision_model.model import (
    MODEL,
    QUERY_ALIASES_CHARACTERS,
    QUERY_ALIASES_MAX,
    QUERY_DESCRIPTION_CHARACTERS,
    REVISION,
    CandidateScorer,
    marginal_set_loss,
    pair_texts,
)
from GG_Data.entity_resolution.luke_pilot.data import read_jsonl, sha256, stable_head

LOG = logging.getLogger(__name__)


def atomic_torch_save(value, path: Path) -> None:
    """Keep the prior artifact valid until the replacement is fully written."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(value, temporary)
    temporary.replace(path)


def rng_state() -> dict:
    return {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch": torch.get_rng_state(),
        "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
    }


def restore_rng(state: dict) -> None:
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"].cpu())
    if state["cuda"] and torch.cuda.is_available():
        torch.cuda.set_rng_state_all([item.cpu() for item in state["cuda"]])


def checkpoint_payload(
    model: CandidateScorer, optimizer, progress: dict, input_hashes: dict
) -> dict:
    # Frozen checkpoints reconstruct the unchanged encoder from its pinned base.
    # Full-stage checkpoints include every encoder and head weight.
    return {
        "model": model.scorer.state_dict() if model.frozen else model.state_dict(),
        "head_only": model.frozen,
        "model_id": MODEL,
        "revision": REVISION,
        "optimizer": optimizer.state_dict(),
        "progress": progress,
        "rng": rng_state(),
        "input_hashes": input_hashes,
        "encoder_frozen": model.frozen,
    }


def restore_checkpoint(
    saved: dict, model: CandidateScorer, optimizer, input_hashes: dict
) -> dict:
    if saved["model_id"] != MODEL or saved["revision"] != REVISION:
        raise ValueError("Checkpoint encoder differs from pinned LUKE base")
    if saved["input_hashes"] != input_hashes:
        raise ValueError("Resume input/config hashes differ from saved run")
    (model.scorer if saved.get("head_only") else model).load_state_dict(saved["model"])
    model.freeze_encoder(saved["encoder_frozen"])
    optimizer.load_state_dict(saved["optimizer"])
    restore_rng(saved["rng"])
    return saved["progress"]


def candidate_recall(rows: list[dict], counts=(10, 20, 40, 80, 0)) -> dict:
    """Validation-only trigram retrieval coverage over initial labelled pools."""
    from GG_Data.entity_resolution.trigram import rank_candidates

    initial = [row for row in rows if row["removal_index"] == 0]
    results = {}
    for count in counts:
        recovered, total, all_hit, pairs = 0, 0, 0, 0
        for row in initial:
            if "candidate_trials" in row:
                trial = row["candidate_trials"][str(count) if count else "all"]
                recovered += trial["retrieved"]
                total += trial["positive_count"]
                all_hit += trial["retrieved"] == trial["positive_count"]
                pairs += trial["candidate_count"] + 1
                continue
            # rank_candidates also enforces page/revision scope. Public pools
            # have a synthetic shared scope solely for this retrieval diagnostic.
            scoped = [
                {**candidate, "page_id": 0, "revision_id": 0}
                for candidate in row["candidates"]
            ]
            ranked = rank_candidates(
                {"label": row["entity"]["name"], "page_id": 0, "revision_id": 0},
                scoped,
                count=count,
            )
            chosen = {candidate["id"] for candidate in ranked}
            positives = set(row["positive_ids"])
            recovered += len(positives & chosen)
            total += len(positives)
            all_hit += positives.issubset(chosen)
            pairs += len(ranked) + 1
        results[str(count) if count else "all"] = {
            "questions": len(initial),
            "labelled_positive_groups": total,
            "retrieved_labelled_positive_groups": recovered,
            "candidate_recall": recovered / total if total else None,
            "all_positives_retrieved_questions": all_hit,
            "unique_query_pairs": pairs,
            "incomplete_public_annotations": True,
        }
    return results


class Runner:
    def __init__(self, args):
        self.args = args
        self.started = time.monotonic()
        self.started_utc = datetime.now(timezone.utc).isoformat()
        self.stop_requested = False
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA required for execution; CPU is for contract tests only"
            )
        if args.max_hours <= 0 or args.max_hours > 6 or args.pair_batch_size < 1:
            raise ValueError(
                "Runtime must be positive and <=6h; pair batch size must be positive"
            )
        from transformers import AutoModel, AutoTokenizer

        self.device = torch.device("cuda")
        torch.set_num_threads(4)
        random.seed(20261028)
        np.random.seed(20261028)
        torch.manual_seed(20261028)
        args.output.mkdir(parents=True, exist_ok=True)
        if args.resume is None and (args.output / "latest.pt").exists():
            raise FileExistsError(
                "Use --resume or a new output directory; checkpoint exists"
            )
        self.rows = {
            split: read_jsonl(args.inputs / f"{split}.jsonl")
            for split in ("train", "validation", "public_test")
        }
        manifest = json.loads(
            (args.inputs / "public_manifest.json").read_text(encoding="utf-8")
        )
        self.hashes = {name: sha256(args.inputs / name) for name in manifest["files"]}
        if self.hashes != manifest["files"]:
            raise ValueError("Training files differ from frozen public manifest")
        self.hashes["public_manifest.json"] = sha256(
            args.inputs / "public_manifest.json"
        )
        # Configuration changes can alter an exact restart and must be explicit.
        self.hashes["training_config"] = json.dumps(
            {
                "max_length": args.max_length,
                "pair_batch_size": args.pair_batch_size,
                "accumulate": args.accumulate,
                "head_batch_size": args.head_batch_size,
                "full_epochs": args.full_epochs,
            },
            sort_keys=True,
        )
        documents = {
            split: {row["document_id"] for row in rows}
            for split, rows in self.rows.items()
        }
        if any(
            documents[a] & documents[b] for a in documents for b in documents if a != b
        ):
            raise ValueError(
                "Public source pages overlap across training/validation/test"
            )
        for rows in self.rows.values():
            if not rows or len({row["id"] for row in rows}) != len(rows):
                raise ValueError(
                    "Each split requires nonempty, uniquely identified states"
                )
            for row in rows:
                pair_texts(row)
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
        self.model = CandidateScorer(
            AutoModel.from_pretrained(MODEL, revision=REVISION)
        ).to(self.device)
        self.progress = {
            "stage": "frozen",
            "epoch": 0,
            "cursor": 0,
            "order": [],
            "history": [],
            "validation_losses": [],
            "head_stable": False,
            "frozen_best_loss": float("inf"),
            "full_best_loss": float("inf"),
            "optimizer_steps": 0,
            "encoder_optimizer_steps": 0,
            "accumulated_worker_seconds": 0.0,
            "interrupted": False,
        }
        if args.resume:
            saved = torch.load(args.resume, map_location="cpu", weights_only=False)
            self.model.freeze_encoder(saved["encoder_frozen"])
            self.optimizer = self.make_optimizer(saved["progress"]["stage"])
            self.progress = restore_checkpoint(
                saved, self.model, self.optimizer, self.hashes
            )
            self.progress["interrupted"] = False
        else:
            self.model.freeze_encoder(True)
            self.optimizer = self.make_optimizer("frozen")
        self.prior_seconds = self.progress["accumulated_worker_seconds"]
        if args.resume is None and args.mode == "train":
            self.save()
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)
        self.save_json(
            "hardware.json",
            {
                "torch": torch.__version__,
                "cuda": torch.version.cuda,
                "gpu": torch.cuda.get_device_name(),
                "gpu_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
                "model_id": MODEL,
                "revision": REVISION,
                "pairs_are_text_only": True,
                "query_text_limits": {
                    "aliases": QUERY_ALIASES_MAX,
                    "alias_characters": QUERY_ALIASES_CHARACTERS,
                    "description_characters": QUERY_DESCRIPTION_CHARACTERS,
                },
                "encoder_parameters": sum(
                    p.numel() for p in self.model.encoder.parameters()
                ),
                "head_parameters": sum(
                    p.numel() for p in self.model.scorer.parameters()
                ),
            },
        )

    def request_stop(self, *_):
        self.stop_requested = True

    def guard(self):
        if (
            self.stop_requested
            or time.monotonic() - self.started >= self.args.max_hours * 3600
        ):
            raise TimeoutError(
                "Runtime/stop guard reached; resume from latest optimizer boundary"
            )

    def make_optimizer(self, stage: str):
        if stage == "frozen":
            return torch.optim.AdamW(
                self.model.scorer.parameters(), lr=5e-4, weight_decay=0.01
            )
        return torch.optim.AdamW(
            [
                {"params": self.model.encoder.parameters(), "lr": 1e-5},
                {"params": self.model.scorer.parameters(), "lr": 1e-4},
            ],
            weight_decay=0.01,
        )

    def save_json(self, name: str, data) -> None:
        (self.args.output / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def save(self, name="latest.pt") -> None:
        self.progress["accumulated_worker_seconds"] = (
            self.prior_seconds + time.monotonic() - self.started
        )
        payload = checkpoint_payload(
            self.model, self.optimizer, self.progress, self.hashes
        )
        atomic_torch_save(payload, self.args.output / name)

    def tokens(self, first, second):
        encoded = self.tokenizer(
            first,
            second,
            padding=True,
            truncation=True,
            max_length=self.args.max_length,
            return_tensors="pt",
        )
        return {key: value.to(self.device) for key, value in encoded.items()}

    def encode_pairs(self, first, second, features=False):
        results = []
        for start in range(0, len(first), self.args.pair_batch_size):
            self.guard()
            with torch.autocast("cuda", dtype=torch.bfloat16):
                inputs = self.tokens(
                    first[start : start + self.args.pair_batch_size],
                    second[start : start + self.args.pair_batch_size],
                )
                result = (
                    self.model.encode(**inputs) if features else self.model(**inputs)
                )
            results.append(result)
        return torch.cat(results)

    def cache(self, split: str):
        path = self.args.output / f"{split}_features.pt"
        fingerprint = {
            "input": self.hashes[f"{split}.jsonl"],
            "model_id": MODEL,
            "revision": REVISION,
            "max_length": self.args.max_length,
            "pair_batch_size": self.args.pair_batch_size,
        }
        if path.exists():
            cached = torch.load(path, map_location="cpu", weights_only=False)
            if cached["fingerprint"] != fingerprint:
                raise ValueError("Feature cache fingerprint differs from frozen run")
            return cached
        self.model.freeze_encoder(True)
        first, second, keys, indices, targets = [], [], {}, [], []
        for row in self.rows[split]:
            queries, options, positive = pair_texts(row)
            layout = []
            for query, option in zip(queries, options):
                key = (query, option)
                if key not in keys:
                    keys[key] = len(first)
                    first.append(query)
                    second.append(option)
                layout.append(keys[key])
            indices.append(layout)
            targets.append(positive)
        features = []
        started = time.monotonic()
        with torch.no_grad():
            for start in range(0, len(first), self.args.pair_batch_size):
                features.append(
                    self.encode_pairs(
                        first[start : start + self.args.pair_batch_size],
                        second[start : start + self.args.pair_batch_size],
                        features=True,
                    )
                    .half()
                    .cpu()
                )
                if start % (self.args.pair_batch_size * 100) == 0:
                    LOG.info(
                        "Frozen cache %s: %s/%s unique pairs", split, start, len(first)
                    )
        cached = {
            "features": torch.cat(features),
            "indices": indices,
            "targets": targets,
            "fingerprint": fingerprint,
            "elapsed_seconds": time.monotonic() - started,
        }
        atomic_torch_save(cached, path)
        return cached

    def cached_batch(self, cache, indices):
        layouts = [cache["indices"][int(index)] for index in indices]
        features = (
            cache["features"][[j for layout in layouts for j in layout]]
            .to(self.device)
            .float()
        )
        return (
            features,
            [len(layout) for layout in layouts],
            [cache["targets"][int(i)] for i in indices],
        )

    def evaluate(self, rows, cache=None):
        self.model.eval()
        loss_sum, correct, stops, true_stops, correct_stops = 0.0, 0, 0, 0, 0
        pair_true, pair_false, pair_missed, pair_gold, pair_predictions = 0, 0, 0, 0, 0
        initial_pools, complete_pools, retrieval_missed = 0, 0, 0
        for index, row in enumerate(rows):
            self.guard()
            with torch.no_grad():
                if cache is not None:
                    features, sizes, targets = self.cached_batch(cache, [index])
                    logits = self.model.scorer(features).squeeze(-1)
                else:
                    first, second, target = pair_texts(row)
                    logits = self.encode_pairs(first, second).float()
                    sizes, targets = [len(first)], [target]
                loss_sum += float(marginal_set_loss(logits.float(), sizes, targets))
                # Stop wins ties, as it does during the requested removal loop.
                chosen = (
                    len(logits) - 1
                    if bool(logits[-1] >= logits.max())
                    else int(logits.argmax())
                )
            gold_stop = not row["positive_ids"]
            predicted_stop = chosen == len(row["candidates"])
            correct += chosen in targets[0]
            stops += predicted_stop
            true_stops += gold_stop
            correct_stops += predicted_stop and gold_stop
            if row["removal_index"] == 0:
                initial_pools += 1
                selected = {
                    candidate["id"]
                    for candidate, score in zip(row["candidates"], logits[:-1])
                    if bool(score > logits[-1])
                }
                gold = set(row["positive_ids"])
                pair_true += len(selected & gold)
                pair_false += len(selected - gold)
                pair_missed += len(gold - selected)
                pair_gold += len(gold)
                pair_predictions += len(selected)
                complete_pools += selected == gold
                retrieval_missed += len(set(row.get("full_positive_ids", gold)) - gold)
        total = len(rows)
        return {
            "states": total,
            "loss": loss_sum / total,
            "set_choice_accuracy": correct / total,
            "predicted_stops": stops,
            "gold_synthetic_stops": true_stops,
            "correct_stops": correct_stops,
            "early_stops": stops - correct_stops,
            "late_stops": true_stops - correct_stops,
            "stop_precision": correct_stops / stops if stops else None,
            "stop_recall": correct_stops / true_stops if true_stops else None,
            "initial_pools": initial_pools,
            "complete_labelled_pair_sets": complete_pools,
            "pair_true_positive": pair_true,
            "pair_false_positive": pair_false,
            "pair_false_negative_within_pool": pair_missed,
            "pair_precision": (
                pair_true / pair_predictions if pair_predictions else None
            ),
            "pair_recall_within_pool": pair_true / pair_gold if pair_gold else None,
            "retrieval_excluded_labelled_positive_groups": retrieval_missed,
            "public_label_incompleteness_caveat": True,
        }

    def validation(self, cache=None):
        metrics = self.evaluate(self.rows["validation"], cache)
        event = {
            "stage": self.progress["stage"],
            "epoch": self.progress["epoch"],
            "cursor": self.progress["cursor"],
            "optimizer_steps": self.progress["optimizer_steps"],
            "encoder_trainable": not self.model.frozen,
            **metrics,
        }
        self.progress["history"].append(event)
        stage = self.progress["stage"]
        if metrics["loss"] < self.progress[f"{stage}_best_loss"]:
            self.progress[f"{stage}_best_loss"] = metrics["loss"]
            self.save(f"{stage}_best.pt")
        self.save_json("training_history.json", self.progress["history"])
        LOG.info("VALIDATION %s", json.dumps(event))
        return metrics

    def benchmark(self):
        self.guard()
        row = self.rows["train"][0]
        first, second, _ = pair_texts(row)
        first, second = (
            first[: self.args.pair_batch_size],
            second[: self.args.pair_batch_size],
        )
        # This command has an isolated model and saves no trained checkpoint.
        # Allocate real full-stage AdamW moments before any memory measurement.
        self.model.freeze_encoder(False)
        self.model.encoder.gradient_checkpointing_enable()
        self.model.train()
        benchmark_optimizer = self.make_optimizer("full")
        warmup_logits = self.encode_pairs(first, second).float()
        warmup_logits.square().mean().backward()
        benchmark_optimizer.step()
        benchmark_optimizer.zero_grad(set_to_none=True)
        torch.cuda.synchronize()
        optimizer_state_bytes = sum(
            value.numel() * value.element_size()
            for state in benchmark_optimizer.state.values()
            for value in state.values()
            if isinstance(value, torch.Tensor)
        )
        if not optimizer_state_bytes:
            raise RuntimeError("Full-stage benchmark did not allocate AdamW state")
        del warmup_logits
        timings = {}
        for frozen in (True, False):
            self.model.freeze_encoder(frozen)
            if not frozen:
                self.model.encoder.gradient_checkpointing_enable()
            self.model.train()
            elapsed = []
            for index in range(3):
                torch.cuda.synchronize()
                started = time.monotonic()
                logits = self.encode_pairs(first, second).float()
                logits.square().mean().backward()
                self.model.zero_grad(set_to_none=True)
                torch.cuda.synchronize()
                if index:
                    elapsed.append(time.monotonic() - started)
            timings["frozen" if frozen else "full"] = {
                "pairs": len(first),
                "seconds_per_batch": elapsed,
                "pairs_per_second": len(first) / float(np.median(elapsed)),
            }
        # A whole pool retains the graphs needed by one marginal set loss.
        # This exposes memory limits hidden by timing a single pair chunk.
        largest = max(self.rows["train"], key=lambda item: len(item["candidates"]))
        full_first, full_second, targets = pair_texts(largest)
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        started = time.monotonic()
        logits = self.encode_pairs(full_first, full_second).float()
        marginal_set_loss(logits, [len(logits)], [targets]).backward()
        self.model.zero_grad(set_to_none=True)
        torch.cuda.synchronize()
        timings["largest_pool"] = {
            "pairs": len(full_first),
            "seconds": time.monotonic() - started,
            "peak_gpu_bytes": torch.cuda.max_memory_allocated(),
        }
        train_pairs = sum(len(row["candidates"]) + 1 for row in self.rows["train"])
        timings["forecast"] = {
            "full_training_pairs": train_pairs * self.args.full_epochs,
            "full_training_seconds_at_chunk_throughput": train_pairs
            * self.args.full_epochs
            / timings["full"]["pairs_per_second"],
            "excludes": "feature cache, warmup epochs, validation, optimizer updates, checkpoints, inference and setup",
        }
        self.model.freeze_encoder(True)
        self.save_json(
            "benchmark.json",
            {
                "timings": timings,
                "peak_gpu_bytes": torch.cuda.max_memory_allocated(),
                "optimizer_state_bytes": optimizer_state_bytes,
                "full_optimizer_steps_before_measurement": 1,
                "benchmark_weights_are_discarded": True,
                "basis": "two measured batches after one warmup; throughput forecast, not complete training time",
            },
        )
        return timings

    def train(self):
        validation_rows = self.rows["validation"]
        self.save_json(
            "validation_candidate_recall.json", candidate_recall(validation_rows)
        )
        if self.progress["stage"] == "frozen":
            train_cache, val_cache = self.cache("train"), self.cache("validation")
            while self.progress["epoch"] < 40 and not self.progress["head_stable"]:
                self.guard()
                self.model.train()
                if not self.progress["order"]:
                    self.progress["order"] = np.random.permutation(
                        len(self.rows["train"])
                    ).tolist()
                order = self.progress["order"]
                while self.progress["cursor"] < len(order):
                    self.guard()
                    start = self.progress["cursor"]
                    indices = order[start : start + self.args.head_batch_size]
                    features, sizes, targets = self.cached_batch(train_cache, indices)
                    self.optimizer.zero_grad(set_to_none=True)
                    loss = marginal_set_loss(
                        self.model.scorer(features).squeeze(-1), sizes, targets
                    )
                    if not torch.isfinite(loss):
                        raise RuntimeError("Non-finite frozen head loss")
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(self.model.scorer.parameters(), 1.0)
                    self.optimizer.step()
                    self.progress["cursor"] += len(indices)
                    self.progress["optimizer_steps"] += 1
                self.progress["epoch"] += 1
                metrics = self.validation(val_cache)
                self.progress["validation_losses"].append(metrics["loss"])
                self.progress["head_stable"] = stable_head(
                    self.progress["validation_losses"]
                )
                self.progress["order"], self.progress["cursor"] = [], 0
                if self.progress["epoch"] in (8, 16, 24, 32):
                    for group in self.optimizer.param_groups:
                        group["lr"] *= 0.5
                self.save()
            self.save_json(
                "unfreeze_decision.json",
                {
                    "head_stable": self.progress["head_stable"],
                    "validation_observations": len(self.progress["validation_losses"]),
                    "required_observations": 4,
                    "consecutive_relative_changes_max": 0.01,
                    "definite_encoder_tuning_after_stability": True,
                    "accuracy_targets_do_not_gate_encoder_tuning": True,
                },
            )
            if not self.progress["head_stable"]:
                self.save_json(
                    "training_summary.json", self.summary("blocked_head_not_stable")
                )
                return
            saved = torch.load(
                self.args.output / "frozen_best.pt",
                map_location="cpu",
                weights_only=False,
            )
            self.model.scorer.load_state_dict(saved["model"])
            del train_cache, val_cache, saved
            self.model.freeze_encoder(False)
            self.model.encoder.gradient_checkpointing_enable()
            self.optimizer = self.make_optimizer("full")
            self.progress.update(stage="full", epoch=0, cursor=0, order=[])
            self.save()
        if self.progress["stage"] == "full":
            self.model.freeze_encoder(False)
            self.model.encoder.gradient_checkpointing_enable()
            while self.progress["epoch"] < self.args.full_epochs:
                self.guard()
                self.model.train()
                if not self.progress["order"]:
                    self.progress["order"] = np.random.permutation(
                        len(self.rows["train"])
                    ).tolist()
                order = self.progress["order"]
                while self.progress["cursor"] < len(order):
                    self.guard()
                    start = self.progress["cursor"]
                    indices = order[start : start + self.args.accumulate]
                    self.optimizer.zero_grad(set_to_none=True)
                    for index in indices:
                        first, second, positive = pair_texts(self.rows["train"][index])
                        logits = self.encode_pairs(first, second).float()
                        loss = marginal_set_loss(logits, [len(first)], [positive])
                        if not torch.isfinite(loss):
                            raise RuntimeError("Non-finite encoder tuning loss")
                        (loss / len(indices)).backward()
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                    self.optimizer.step()
                    self.progress["cursor"] += len(indices)
                    self.progress["optimizer_steps"] += 1
                    self.progress["encoder_optimizer_steps"] += 1
                    if (
                        self.progress["encoder_optimizer_steps"]
                        % self.args.checkpoint_steps
                        == 0
                    ):
                        self.validation()
                        self.save()
                        self.model.train()
                    if self.progress["encoder_optimizer_steps"] % 25 == 0:
                        LOG.info(
                            "Full epoch %s states %s/%s optimizer_steps=%s loss=%.5f",
                            self.progress["epoch"] + 1,
                            self.progress["cursor"],
                            len(order),
                            self.progress["encoder_optimizer_steps"],
                            float(loss.detach()),
                        )
                self.progress["epoch"] += 1
                self.validation()
                self.progress["order"], self.progress["cursor"] = [], 0
                self.save()
            self.progress["stage"] = "complete"
            self.save()
        final = (
            "full_best.pt"
            if self.progress["full_best_loss"] <= self.progress["frozen_best_loss"]
            else "frozen_best.pt"
        )
        selection = {
            "final_checkpoint": final,
            "selection_basis": "validation marginal set loss only",
            "public_test_not_used_for_selection": True,
        }
        self.save_json("training_selection.json", selection)
        # Only evaluate held-out diagnostic data after final checkpoint selection.
        selected = torch.load(
            self.args.output / final, map_location="cpu", weights_only=False
        )
        if selected["head_only"]:
            from transformers import AutoModel

            self.model.encoder.load_state_dict(
                AutoModel.from_pretrained(MODEL, revision=REVISION).state_dict()
            )
            self.model.scorer.load_state_dict(selected["model"])
        else:
            self.model.load_state_dict(selected["model"])
        self.model.freeze_encoder(True)
        for split in ("validation", "public_test"):
            self.save_json(
                f"final_{split}_metrics.json", self.evaluate(self.rows[split])
            )
        self.save_json(
            "training_complete.json", {**self.summary("complete"), **selection}
        )
        self.save_json("training_summary.json", self.summary("complete"))

    def summary(self, status: str):
        return {
            "stage": "train",
            "owner": "root_gpu_operator",
            "status": status,
            "started_utc": self.started_utc,
            "ended_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": time.monotonic() - self.started,
            "active_work": "unknown",
            "approval_wait": "unknown",
            "environment_wait": "unknown",
            "worker_seconds_across_restarts": self.prior_seconds
            + time.monotonic()
            - self.started,
            "gpu_seconds": "root_aggregate_ledger",
            "input_hashes": self.hashes,
            "model_id": MODEL,
            "revision": REVISION,
            "head_stable": self.progress["head_stable"],
            "encoder_optimizer_steps": self.progress["encoder_optimizer_steps"],
            "best_frozen_validation_loss": self.progress["frozen_best_loss"],
            "best_full_validation_loss": self.progress["full_best_loss"],
            "api_requests": 0,
            "estimated_cost_usd": "root_aggregate_ledger",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("train", "benchmark"))
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--max-hours", type=float, default=4.0)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--pair-batch-size", type=int, default=8)
    parser.add_argument("--head-batch-size", type=int, default=64)
    parser.add_argument("--accumulate", type=int, default=8)
    parser.add_argument("--full-epochs", type=int, choices=(1, 2), default=2)
    parser.add_argument("--checkpoint-steps", type=int, default=250)
    args = parser.parse_args()
    if (
        min(
            args.accumulate,
            args.head_batch_size,
            args.checkpoint_steps,
            args.max_length,
        )
        < 1
    ):
        parser.error("Batch, checkpoint and token limits must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    runner = Runner(args)
    try:
        getattr(runner, args.mode)()
    except (TimeoutError, KeyboardInterrupt) as error:
        # The latest saved cursor always follows a completed optimizer update.
        # Do not save partially accumulated gradients as resumable progress.
        runner.save_json(
            "interrupted_summary.json",
            {
                **runner.summary("interrupted"),
                "reason": str(error),
                "resume_checkpoint": "latest.pt",
                "unsaved_updates_may_be_replayed": True,
            },
        )
        raise


if __name__ == "__main__":
    main()
