"""Train joint-option Laya using the existing public data and upstream RLCD loop.

Preparation and CPU tests need no weights. CUDA runs use a forward hook to check
the time/STOP boundary before each batch. Warmup must stabilise before encoder
tuning; saved summaries distinguish a complete run from a resource-limited run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path

from GG_Data.entity_resolution.luke_pilot.data import sha256, stable_head

LOG = logging.getLogger(__name__)


class BudgetStop(RuntimeError):
    """The approved worker allowance ended; save an incomplete result."""


class StageComplete(Exception):
    """A stable head can now enter the separately configured full stage."""


class RunGuard:
    def __init__(self, deadline: float, stop_file: Path):
        self.deadline, self.stop_file = deadline, stop_file

    def check(self, *_args) -> None:
        if self.stop_file.exists():
            raise BudgetStop("STOP file requested")
        if time.monotonic() >= self.deadline:
            raise BudgetStop("worker deadline reached")


def freeze_encoder(model, frozen: bool) -> None:
    """Upstream freezes parameters but does not re-enable them on a second call."""
    for parameter in model.encoder.parameters():
        parameter.requires_grad_(not frozen)
    model.encoder.train(not frozen)


def validate_split_pages(splits: dict[str, list[dict]]) -> None:
    pages = {}
    for name, rows in splits.items():
        if not rows or len({r["id"] for r in rows}) != len(rows):
            raise ValueError(f"Empty or duplicate-ID split: {name}")
        pages[name] = {r["source_page_id"] for r in rows}
    for a in pages:
        for b in pages:
            if a < b and pages[a] & pages[b]:
                raise ValueError(f"Source pages overlap: {a}, {b}")


def select_records(path: Path, bases_per_direction: int = 0) -> tuple[list[dict], dict]:
    """Scan large JSONL first, then retain complete, deterministically ranked pools.

    Sampling individual removal states breaks fixed candidate chunks. The optional
    budget subset therefore keeps every state of each selected original question.
    """
    bases, pages, ids = {}, set(), set()
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            if record["id"] in ids:
                raise ValueError(f"Duplicate state: {record['id']}")
            ids.add(record["id"])
            pages.add(record["source_page_id"])
            bases[(record["direction"], record["base_id"])] = None
    selected = set(bases)
    if bases_per_direction:
        selected = set()
        for direction in ("forward", "reverse"):
            candidates = [key for key in bases if key[0] == direction]
            candidates.sort(
                key=lambda key: hashlib.sha256(
                    f"20261030:{key[0]}:{key[1]}".encode()
                ).hexdigest()
            )
            selected.update(candidates[:bases_per_direction])
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            if (record["direction"], record["base_id"]) in selected:
                rows.append(record)
    return rows, {
        "available_states": len(ids),
        "available_bases": len(bases),
        "selected_states": len(rows),
        "selected_bases": len(selected),
        "source_pages": sorted(pages),
        "base_keys": sorted(selected),
    }


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def save_model(upstream, model, tok, cfg: dict, output: Path) -> None:
    """Write to scratch first; move weights before the final config/receipt."""
    scratch = output.parent / (output.name + "_writing")
    upstream.save_checkpoint(model, tok, cfg, str(scratch))
    output.mkdir(parents=True, exist_ok=True)
    paths = sorted(scratch.rglob("*"), key=lambda p: p.name == "rl_agent_config.json")
    for path in paths:
        if path.is_file():
            destination = output / path.relative_to(scratch)
            destination.parent.mkdir(parents=True, exist_ok=True)
            path.replace(destination)


def token_binding(base: Path, args) -> dict:
    """Prepared tensors are valid only for this tokenizer and these budgets."""
    return {
        "max_len": args.max_len,
        "head_max_len": args.head_max_len,
        "max_options": args.max_options,
        "tokenizer": {
            str(p.relative_to(base)): sha256(p)
            for p in sorted((base / "tokenizer").rglob("*"))
            if p.is_file()
        },
    }


def build_items(rows: list[dict], tokenizer, args) -> tuple[list[dict], list[dict]]:
    from GG_Data.entity_resolution.laya_model.model import (
        make_question, partition_removal_states, strict_items_from_rows)

    raw_chunks = partition_removal_states(
        rows,
        tokenizer=tokenizer,
        max_len=args.max_len,
        head_max_len=args.head_max_len,
        max_options=args.max_options,
    )
    formatted = [make_question(chunk, chunk["direction"]) for chunk in raw_chunks]
    items = strict_items_from_rows(
        tokenizer, formatted, args.max_len, args.head_max_len
    )
    if len(items) != len(raw_chunks):
        raise ValueError("One training item is required per recorded candidate chunk")
    return items, raw_chunks


def validation(upstream, model, tok, items, device, args) -> dict:
    records = upstream.calibration_records(
        model,
        tok,
        items,
        device,
        args.max_len,
        args.head_max_len,
        batch_size=args.micro_batch,
    )
    result = validation_metrics(records)
    result["by_direction"] = {
        direction: validation_metrics(
            [
                record
                for item, record in zip(items, records, strict=True)
                if item["q"]["crit"]["STOP"] == stop_text
            ]
        )
        for direction, stop_text in (
            ("forward", "None of the remaining mention groups refers to this entity."),
            (
                "reverse",
                "This mention does not refer to any of the remaining entities.",
            ),
        )
    }
    return result


def validation_metrics(records) -> dict:
    """Report positive decisions separately: abundant STOP chunks can hide failure."""
    losses, right, stopped, correct_stop, gold_stop = [], 0, 0, 0, 0
    positive_right = 0
    for _qtype, logits, target, _k in records:
        import numpy as np

        logits, target = np.asarray(logits), np.asarray(target)
        choice = int(logits.argmax())
        logp = logits - np.logaddexp.reduce(logits)
        losses.append(float(-(target * logp).sum()))
        right += bool(target[choice] > 0)
        # Canonical formatter always puts STOP last; verify in build_items tests.
        is_stop = choice == len(target) - 1
        true_stop = target[-1] > 0
        positive_right += bool(not true_stop and target[choice] > 0)
        stopped += is_stop
        correct_stop += bool(is_stop and true_stop)
        gold_stop += bool(true_stop)
    return {
        "items": len(records),
        "loss": sum(losses) / len(losses) if losses else None,
        "valid_set_accuracy": right / len(records) if records else None,
        "positive_items": len(records) - gold_stop,
        "positive_correct": positive_right,
        "positive_selection_accuracy": (
            positive_right / (len(records) - gold_stop)
            if len(records) > gold_stop
            else None
        ),
        "stop_selected": stopped,
        "correct_stop": correct_stop,
        "gold_stop": gold_stop,
        "stop_precision": correct_stop / stopped if stopped else None,
        "stop_recall": correct_stop / gold_stop if gold_stop else None,
        "incomplete_public_annotations": True,
    }


def run(args) -> dict:
    import torch
    from laya import train as upstream

    if not 0 < args.max_seconds <= 7200:
        raise ValueError("Worker allowance must be positive and <=2 hours")
    if args.output.exists():
        raise FileExistsError("Use a new output directory; old results are immutable")
    args.output.mkdir(parents=True)
    started = time.monotonic()
    guard = RunGuard(started + args.max_seconds, args.output / "STOP")
    splits, membership = {}, {}
    if args.prepared_items:
        receipt = json.loads(
            (args.prepared_items / "training_membership.json").read_text()
        )
        hashes, membership = receipt["input_sha256"], receipt["membership"]
        cache_summary = json.loads((args.prepared_items / "summary.json").read_text())
        if cache_summary["token_binding"] != token_binding(args.base, args):
            raise ValueError("Prepared tokenizer/token budgets differ from this run")
        for name, digest in cache_summary["item_sha256"].items():
            if sha256(args.prepared_items / f"{name}_items.pt") != digest:
                raise ValueError(f"Prepared item hash mismatch: {name}")
        selected = []
    else:
        for name in ("train", "validation", "calibration"):
            splits[name], membership[name] = select_records(
                args.inputs / f"{name}.jsonl",
                args.train_bases_per_direction if name == "train" else 0,
            )
        # Test bytes and source membership are recorded, but its examples do not enter
        # fitting, warmup stability, hyperparameter choice or calibration.
        test_pages = set()
        with (args.inputs / "public_test.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                test_pages.add(json.loads(line)["source_page_id"])
        page_sets = {
            name: set(info["source_pages"]) for name, info in membership.items()
        }
        page_sets["public_test"] = test_pages
        for a, pages in page_sets.items():
            for b, others in page_sets.items():
                if a < b and pages & others:
                    raise ValueError(f"Source pages overlap: {a}, {b}")
        hashes = {name: sha256(args.inputs / f"{name}.jsonl") for name in page_sets}
        selected = splits["train"]
    write_json(
        args.output / "training_membership.json",
        {
            "input_sha256": hashes,
            "ids": (
                receipt["ids"] if args.prepared_items else [r["id"] for r in selected]
            ),
            "membership": membership,
            "available_train_states": membership["train"]["available_states"],
            "selected_train_states": membership["train"]["selected_states"],
        },
    )
    if args.mode == "prepare":
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(str(args.base / "tokenizer"))
        counts, item_hashes = {}, {}
        for name, rows in splits.items():
            items, chunks = build_items(rows, tokenizer, args)
            torch.save(items, args.output / f"{name}_items.pt")
            item_hashes[name] = sha256(args.output / f"{name}_items.pt")
            counts[name] = {"states": len(rows), "chunks": len(chunks)}
            del items, chunks
        result = {
            "status": "PREPARED",
            "splits": counts,
            "item_sha256": item_hashes,
            "token_binding": token_binding(args.base, args),
            "elapsed_seconds": time.monotonic() - started,
        }
        write_json(args.output / "summary.json", result)
        return result
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required for benchmark/training; CPU is for checks")
    torch.set_num_threads(4)
    model, tok, cfg = upstream.load_checkpoint(str(args.base))
    cfg = dict(cfg, max_len=args.max_len, head_max_len=args.head_max_len)
    model.to("cuda")
    hook = model.register_forward_pre_hook(guard.check)
    device = torch.device("cuda")
    history, result = [], {
        "status": "STARTED",
        "stage": "load",
        "head_stable": False,
        "encoder_tuned": False,
        "input_sha256": hashes,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "max_seconds": args.max_seconds,
        "active_work_seconds": None,
        "approval_wait_seconds": None,
        "environment_wait_seconds": None,
        "exact_optimizer_resume_supported": False,
    }
    try:
        if args.prepared_items:
            train_items = torch.load(
                args.prepared_items / "train_items.pt", weights_only=False
            )
            val_items = torch.load(
                args.prepared_items / "validation_items.pt", weights_only=False
            )
        else:
            train_items, _ = build_items(selected, tok, args)
            val_items, _ = build_items(splits["validation"], tok, args)
        result.update(
            training_states=membership["train"]["selected_states"],
            training_chunks=len(train_items),
        )
        config = upstream.TrainConfig(
            epochs=40,
            micro_batch=args.micro_batch,
            grad_accum=args.grad_accum,
            loss="rlcd",
            shuffle_options=("choice",),
            freeze_encoder=True,
            encoder_lr=1e-5,
            head_lr=1e-4,
            max_len=args.max_len,
            head_max_len=args.head_max_len,
            seed=20261030,
            log_every=50,
        )
        if args.mode == "benchmark":
            config.epochs = 1
            # Timing uses discarded head updates; encoder remains frozen until
            # the separately measured warmup has passed its stability rule.
            freeze_encoder(model, True)
            sample = train_items[:32]
            begin = time.monotonic()
            upstream.train_model(
                model, tok, sample, config, device, args.max_len, args.head_max_len
            )
            torch.cuda.synchronize()
            seconds = time.monotonic() - begin
            guard.check()
            result.update(
                status="BENCHMARK_COMPLETE",
                benchmark_items=len(sample),
                benchmark_seconds=seconds,
                items_per_second=len(sample) / seconds,
                benchmark_stage="frozen_head_only",
                peak_cuda_bytes=torch.cuda.max_memory_allocated(),
            )
        else:
            result["before_validation"] = validation(
                upstream, model, tok, val_items, device, args
            )
            losses = []
            result["stage"] = "frozen"
            freeze_encoder(model, True)

            def observe(epoch: int, train_loss: float) -> None:
                metrics = validation(upstream, model, tok, val_items, device, args)
                if not math.isfinite(metrics["loss"]):
                    raise ValueError("Non-finite validation loss")
                losses.append(metrics["loss"])
                history.append(
                    {
                        "stage": result["stage"],
                        "epoch": epoch + 1,
                        "training_loss": train_loss,
                        "validation": metrics,
                        "elapsed_seconds": time.monotonic() - started,
                    }
                )
                write_json(args.output / "history.json", {"observations": history})
                save_model(upstream, model, tok, cfg, args.output / "latest")
                if result["stage"] == "frozen" and stable_head(losses):
                    result["head_stable"] = True
                    raise StageComplete()
                # calibration_records switches to eval; the next epoch needs train mode.
                model.train()
                if config.freeze_encoder:
                    model.encoder.eval()

            try:
                upstream.train_model(
                    model,
                    tok,
                    train_items,
                    config,
                    device,
                    args.max_len,
                    args.head_max_len,
                    on_epoch_end=observe,
                )
            except StageComplete:
                pass
            if not result["head_stable"]:
                result["status"] = "WARMUP_NOT_STABLE"
            else:
                guard.check()
                save_model(upstream, model, tok, cfg, args.output / "frozen")
                result["stage"] = "full"
                config.freeze_encoder = False
                config.epochs = args.full_epochs
                freeze_encoder(model, False)
                before = next(model.encoder.parameters()).detach().clone()
                upstream.train_model(
                    model,
                    tok,
                    train_items,
                    config,
                    device,
                    args.max_len,
                    args.head_max_len,
                    on_epoch_end=observe,
                )
                result["encoder_tuned"] = not torch.equal(
                    before, next(model.encoder.parameters()).detach()
                )
                if not result["encoder_tuned"]:
                    raise ValueError("Full stage did not change the encoder")
                result["after_validation"] = validation(
                    upstream, model, tok, val_items, device, args
                )
                if args.prepared_items:
                    calibration = torch.load(
                        args.prepared_items / "calibration_items.pt", weights_only=False
                    )
                else:
                    calibration, _ = build_items(splits["calibration"], tok, args)
                records = upstream.calibration_records(
                    model,
                    tok,
                    calibration,
                    device,
                    args.max_len,
                    args.head_max_len,
                    batch_size=args.micro_batch,
                )
                guard.check()
                fitted = upstream.fit_temperature_map(records)
                cfg.update(fitted)
                result["calibration"] = upstream.calibration_report(
                    records, fitted["temperature"]
                )
                # Upstream argmax(target) is invalid for multiple correct options.
                result["calibration"]["choice"]["accuracy"] = sum(
                    target[int(logits.argmax())] > 0 for _, logits, target, _ in records
                ) / len(records)
                result["calibration"]["choice"][
                    "accuracy_basis"
                ] = "membership in valid set"
                import numpy as np
                from laya.common import temp_bucket

                confidence = []
                for qtype, logits, _, options in records:
                    temperature = fitted.get("temperature_by_options", {}).get(
                        temp_bucket(qtype, options), fitted["temperature"][qtype]
                    )
                    probabilities = np.exp((logits - logits.max()) / temperature)
                    confidence.append(float(probabilities.max() / probabilities.sum()))
                result["calibration"]["choice"]["mean_confidence"] = sum(
                    confidence
                ) / len(confidence)
                result["calibration"]["choice"][
                    "confidence_basis"
                ] = "runtime option-bucket temperature"
                save_model(upstream, model, tok, cfg, args.output / "full")
                guard.check()
                result["status"] = "TRAINING_COMPLETE"
    except BudgetStop as error:
        result.update(status="RESOURCE_LIMIT", reason=str(error))
        save_model(upstream, model, tok, cfg, args.output / "interrupted")
    except Exception as error:
        result.update(status="FAILED", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        hook.remove()
        result.update(
            finished_utc=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic() - started,
        )
        write_json(args.output / "summary.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "benchmark", "train"))
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--prepared-items", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-seconds", type=float, default=3600)
    parser.add_argument("--train-bases-per-direction", type=int, default=0)
    parser.add_argument("--max-options", type=int, default=20)
    parser.add_argument("--max-len", type=int, default=1024)
    parser.add_argument("--head-max-len", type=int, default=256)
    parser.add_argument("--micro-batch", type=int, default=4)
    parser.add_argument("--grad-accum", type=int, default=16)
    parser.add_argument("--full-epochs", type=int, default=2)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    LOG.info("Result: %s", json.dumps(run(args)))


if __name__ == "__main__":
    main()
