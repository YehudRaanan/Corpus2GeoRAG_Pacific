"""Label-aware held-out metrics and immutable-pair comparison for Laya."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
from pathlib import Path

from GG_Data.entity_resolution.luke_pilot.data import read_jsonl, sha256

LIMITATION = (
    "Cached public annotations are incomplete. An unannotated selection is not "
    "verified false; synthetic STOP means no annotated positive remains. "
    "Wilson 95% intervals describe observed states, which can share a page. "
    "Pilot proposals have no verified gold and are not an accuracy estimate."
)


def ratio(numerator: int, denominator: int) -> dict:
    """Include the complete denominator and a Wilson binomial interval."""
    if denominator == 0:
        return dict(numerator=numerator, denominator=0, value=None, ci95=None)
    p, z = numerator / denominator, 1.959963984540054
    scale = 1 + z * z / denominator
    center = (p + z * z / (2 * denominator)) / scale
    radius = (
        z * math.sqrt(p * (1 - p) / denominator + z * z / (4 * denominator**2)) / scale
    )
    return dict(
        numerator=numerator,
        denominator=denominator,
        value=p,
        ci95=[max(0.0, center - radius), min(1.0, center + radius)],
    )


def evaluate_records(records: list[dict], predictions: list[dict]) -> dict:
    """Evaluate one held-out decision per record using valid-set membership.

    Predictions use {id, candidate_id}; None denotes STOP. Full positive IDs,
    when present, expose retrieval misses instead of treating them as negatives.
    Missing predictions remain in not_run, not in the accuracy denominator.
    """
    source = {r["id"]: r for r in records}
    predicted = {r["id"]: r for r in predictions}
    if len(source) != len(records) or len(predicted) != len(predictions):
        raise ValueError("Duplicate evaluation record identities")
    if not predicted.keys() <= source.keys():
        raise ValueError("Predictions contain unknown evaluation records")
    directions = {}
    for direction in sorted({r["direction"] for r in records}):
        selected = [r for r in records if r["direction"] == direction]
        correct = stop_tp = stop_pred = stop_gold = ran = 0
        covered = positive_records = positive_ids_covered = positive_ids_total = 0
        non_stop_correct = non_stop_pred = 0
        for record in selected:
            candidates = {c["id"] for c in record["candidates"]}
            positives = set(record["positive_ids"])
            full = set(
                record.get(
                    "remaining_full_positive_ids",
                    set(record.get("full_positive_ids", positives))
                    - set(record.get("removed_ids", [])),
                )
            )
            if (
                len(candidates) != len(record["candidates"])
                or not positives <= candidates
                or not positives <= full
            ):
                raise ValueError("Invalid candidate or positive identities")
            positive_records += bool(full)
            covered += bool(candidates & full)
            positive_ids_covered += len(candidates & full)
            positive_ids_total += len(full)
            if record["id"] not in predicted:
                continue
            choice = predicted[record["id"]]["candidate_id"]
            if choice is not None and choice not in candidates:
                raise ValueError("Predicted candidate is absent from this record")
            ran += 1
            is_stop, gold_stop = choice is None, not full
            correct += (choice in positives) if not is_stop else gold_stop
            stop_pred += is_stop
            stop_gold += gold_stop
            stop_tp += is_stop and gold_stop
            non_stop_pred += not is_stop
            non_stop_correct += choice in positives if not is_stop else False
        directions[direction] = dict(
            records=len(selected),
            run=ran,
            not_run=len(selected) - ran,
            valid_set_accuracy=ratio(correct, ran),
            non_stop_selection_precision=ratio(non_stop_correct, non_stop_pred),
            stop_precision=ratio(stop_tp, stop_pred),
            stop_recall=ratio(stop_tp, stop_gold),
            candidate_coverage=ratio(covered, positive_records),
            positive_id_coverage=ratio(positive_ids_covered, positive_ids_total),
            quality_targets=dict(valid_set_accuracy=0.90, stop_precision=0.90),
        )
    return dict(
        records=len(records),
        predictions=len(predictions),
        directions=directions,
        limitation=LIMITATION,
        interval_method="Wilson 95%, state-level, not page-cluster adjusted",
    )


def pair_key(row: dict) -> tuple:
    return tuple(row[k] for k in ("page_id", "revision_id", "group_id", "qid"))


def is_max_choice(probabilities: dict, key: str) -> bool:
    """Upstream chooses argmax before rounding probabilities to four decimals."""
    return math.isclose(
        float(probabilities[key]),
        max(map(float, probabilities.values())),
        rel_tol=0,
        abs_tol=0.0001,
    )


def compare_pairs(proposals: list[dict], baseline: list[dict]) -> dict:
    """Compare pair sets without imposing one-to-one identities."""
    new = {pair_key(p): p for p in proposals}
    old = {pair_key(p): p for p in baseline}
    by_new, by_old = defaultdict(set), defaultdict(set)
    for key in new:
        by_new[key[:3]].add(key[3])
    for key in old:
        by_old[key[:3]].add(key[3])
    added, lost = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    return dict(
        proposal_pairs=len(new),
        baseline_pairs=len(old),
        unchanged_pairs=len(new.keys() & old.keys()),
        added_pairs=len(added),
        lost_pairs=len(lost),
        changed_groups=sum(
            by_new[g] != by_old[g] for g in by_new.keys() | by_old.keys()
        ),
        added_examples=[new[k] for k in added[:20]],
        lost_examples=[old[k] for k in lost[:20]],
    )


def evaluate_agent(
    agent,
    records: list[dict],
    output: Path,
    *,
    max_seconds: float,
    checkpoint_binding: dict,
    max_options: int = 20,
    max_len: int = 1024,
    head_max_len: int = 256,
) -> dict:
    """Score one first decision per token-safe held-out chunk, saving each result.

    Complete source states and local chunk decisions have separate denominators.
    A completed chunk is not scored again on resume. No labels enter the agent.
    """
    import hashlib
    from GG_Data.entity_resolution.laya_model.model import (
        make_question,
        partition_removal_states,
    )
    from GG_Data.entity_resolution.hundred_page_pilot.resolve_entities import (
        read_score_records,
    )

    if not math.isfinite(max_seconds) or max_seconds <= 0:
        raise ValueError("Evaluation allowance must be positive")
    if len({r["id"] for r in records}) != len(records):
        raise ValueError("Duplicate source-state IDs")
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=True)
    binding = dict(
        records_sha256=hashlib.sha256(
            json.dumps(records, sort_keys=True).encode()
        ).hexdigest(),
        checkpoint_binding=checkpoint_binding,
        max_options=max_options,
        max_len=max_len,
        head_max_len=head_max_len,
        code_sha256=sha256(Path(__file__)),
        model_code_sha256=sha256(Path(__file__).with_name("model.py")),
    )
    binding_path = output / "inputs.json"
    if binding_path.exists():
        if json.loads(binding_path.read_text(encoding="utf-8")) != binding:
            raise ValueError("Evaluation resume binding differs")
    elif any(
        (output / name).exists()
        for name in ("chunk_records.jsonl", "predictions.jsonl")
    ):
        raise ValueError("Evaluation records have no original binding")
    else:
        with binding_path.open("x", encoding="utf-8") as stream:
            json.dump(binding, stream, indent=2)
    chunk_path, prediction_path = (
        output / "chunk_records.jsonl",
        output / "predictions.jsonl",
    )
    chunk_rows, score_rows = read_score_records(chunk_path), read_score_records(
        prediction_path
    )
    chunks = {r["id"]: r for r in chunk_rows}
    predictions = {r["id"]: r for r in score_rows}
    if len(chunks) != len(chunk_rows) or len(predictions) != len(score_rows):
        raise ValueError("Duplicate saved evaluation IDs")
    if any(
        c["source_record_id"] not in {r["id"] for r in records} for c in chunks.values()
    ):
        raise ValueError("Saved chunks contain unknown source-state IDs")
    if not predictions.keys() <= chunks.keys():
        raise ValueError("Evaluation predictions have no matching chunk")
    status = "complete"
    base_records = defaultdict(list)
    for record in records:
        base_records[record["direction"], record.get("base_id", record["id"])].append(
            record
        )
    last_base, fixed_layout = None, {}
    expected_chunk_ids = set()
    try:
        with chunk_path.open(
            "a", encoding="utf-8"
        ) as chunk_stream, prediction_path.open("a", encoding="utf-8") as score_stream:
            for record in records:
                if (
                    output / "STOP"
                ).exists() or time.monotonic() - started >= max_seconds:
                    raise TimeoutError
                base_key = record["direction"], record.get("base_id", record["id"])
                if base_key != last_base:
                    fixed_layout = defaultdict(list)
                    for raw in partition_removal_states(
                        base_records[base_key],
                        tokenizer=agent.tok,
                        max_options=max_options,
                        max_len=max_len,
                        head_max_len=head_max_len,
                    ):
                        fixed_layout[raw["id"]].append(raw)
                    last_base = base_key
                raw_chunks = fixed_layout[record["id"]]
                for raw in raw_chunks:
                    item = dict(
                        raw,
                        id=f"{record['id']}:chunk:{raw['chunk_index']}",
                        source_record_id=record["id"],
                        remaining_full_positive_ids=list(raw["positive_ids"]),
                        original_remaining_full_positive_ids=sorted(
                            record.get(
                                "remaining_full_positive_ids",
                                set(
                                    record.get(
                                        "full_positive_ids", record["positive_ids"]
                                    )
                                )
                                - set(record.get("removed_ids", [])),
                            )
                        ),
                    )
                    expected_chunk_ids.add(item["id"])
                    if item["id"] in chunks:
                        if chunks[item["id"]] != item:
                            raise ValueError("Saved evaluation chunk changed")
                    else:
                        chunk_stream.write(json.dumps(item, ensure_ascii=False) + "\n")
                        chunk_stream.flush()
                        chunks[item["id"]] = item
                    if item["id"] in predictions:
                        saved = predictions[item["id"]]
                        question = make_question(raw, record["direction"])
                        ids = question["metadata"]["option_ids"]
                        probabilities = saved["probabilities"]
                        if (
                            saved["option_ids"] != ids
                            or saved["candidate_id"] not in ids.values()
                            or probabilities.keys() != ids.keys()
                            or any(
                                not math.isfinite(float(p)) or not 0 <= float(p) <= 1
                                for p in probabilities.values()
                            )
                            or sum(probabilities.values()) <= 0
                            or not is_max_choice(
                                probabilities,
                                next(
                                    k
                                    for k, identity in ids.items()
                                    if identity == saved["candidate_id"]
                                ),
                            )
                            or saved.get("usage", {}).get("truncated")
                            or saved.get("usage", {}).get("options")
                        ):
                            raise ValueError(
                                "Invalid saved prediction option probabilities"
                            )
                        continue
                    if (
                        output / "STOP"
                    ).exists() or time.monotonic() - started >= max_seconds:
                        raise TimeoutError
                    question = make_question(raw, record["direction"])
                    result = agent.system_one(
                        question["state"],
                        question["questions"],
                        max_len=max_len,
                        head_max_len=head_max_len,
                    )
                    answer = result["answers"]["match"]
                    ids = question["metadata"]["option_ids"]
                    probs = answer["probabilities"]
                    if (
                        answer["choice"] not in ids
                        or set(probs) != set(ids)
                        or any(
                            not math.isfinite(float(p)) or not 0 <= float(p) <= 1
                            for p in probs.values()
                        )
                        or sum(probs.values()) <= 0
                        or not is_max_choice(probs, answer["choice"])
                    ):
                        raise ValueError("Invalid joint evaluation answer")
                    if result.get("usage", {}).get("truncated") or result.get(
                        "usage", {}
                    ).get("options"):
                        raise ValueError("Runtime truncated evaluation evidence")
                    prediction = dict(
                        id=item["id"],
                        candidate_id=ids[answer["choice"]],
                        probabilities=probs,
                        option_ids=ids,
                        usage=result.get("usage", {}),
                    )
                    score_stream.write(
                        json.dumps(prediction, ensure_ascii=False) + "\n"
                    )
                    score_stream.flush()
                    predictions[item["id"]] = prediction
    except TimeoutError:
        status = "resource_limit"
    if status == "complete" and chunks.keys() != expected_chunk_ids:
        raise ValueError(
            "Saved evaluation chunk identities differ from regenerated layout"
        )
    chunk_metrics = evaluate_records(
        [c for key, c in chunks.items() if key in expected_chunk_ids],
        [p for key, p in predictions.items() if key in expected_chunk_ids],
    )
    source_metrics, not_run, unverified = {}, [], []
    for direction in sorted({r["direction"] for r in records}):
        selected_records = [r for r in records if r["direction"] == direction]
        full_run = recovered = positive_states = terminal_right = terminals = exact = (
            unknown
        ) = known = 0
        direction_not_run = direction_unverified = 0
        for record in selected_records:
            local = [
                c for c in chunks.values() if c["source_record_id"] == record["id"]
            ]
            if (
                not local
                or len(local) != local[0]["chunk_count"]
                or any(c["id"] not in predictions for c in local)
            ):
                not_run.append(record["id"])
                direction_not_run += 1
                continue
            if any(c["id"] not in expected_chunk_ids for c in local):
                unverified.append(record["id"])
                direction_unverified += 1
                continue
            full_run += 1
            selected_ids = [
                predictions[c["id"]]["candidate_id"]
                for c in local
                if predictions[c["id"]]["candidate_id"] is not None
            ]
            gold = set(
                record.get(
                    "remaining_full_positive_ids",
                    set(record.get("full_positive_ids", record["positive_ids"]))
                    - set(record.get("removed_ids", [])),
                )
            )
            right = bool(set(selected_ids) & gold)
            extra = len(set(selected_ids) - gold)
            unknown += extra
            known += len(set(selected_ids) & gold)
            positive_states += bool(gold)
            recovered += bool(gold) and right
            terminals += not gold
            terminal_right += not gold and not selected_ids
            exact += (right and not extra) if gold else not selected_ids
        source_metrics[direction] = dict(
            records=len(selected_records),
            fully_run=full_run,
            not_run=direction_not_run,
            unverified_saved_states=direction_unverified,
            positive_state_recovery=ratio(recovered, positive_states),
            terminal_all_chunks_stop=ratio(terminal_right, terminals),
            success_without_unannotated_selection=ratio(exact, full_run),
            selected_known_positive_candidates=known,
            selected_unannotated_candidates=unknown,
        )
    pool_coverage = evaluate_records(records, [])
    report = dict(
        status=status,
        source_records=len(records),
        chunk_records=len(chunks),
        predictions=len(predictions),
        source_not_run_ids=not_run,
        source_unverified_saved_ids=unverified,
        unverified_saved_chunk_ids=sorted(chunks.keys() - expected_chunk_ids),
        chunk_not_run_ids=sorted(chunks.keys() - predictions.keys()),
        chunk_metrics=chunk_metrics,
        source_state_metrics=source_metrics,
        original_pool_coverage={
            d: {k: v[k] for k in ("candidate_coverage", "positive_id_coverage")}
            for d, v in pool_coverage["directions"].items()
        },
        comparison_limit="Chunk accuracy has a different decision/candidate denominator from the saved whole-pool LUKE result (551/608). Source-state recovery can include additional unannotated selections; these are reported separately.",
        limitation=LIMITATION,
        partition_policy="fixed_initial_partition_removal_states; source metrics are conditional labelled states, not complete rollout accuracy",
    )
    destination = output / "report.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def load_local_agent(checkpoint: Path, device: str):
    """Load only a complete local Laya checkpoint, bound to all artifact hashes."""
    from laya import Agent

    checkpoint = checkpoint.resolve(strict=True)
    if not checkpoint.is_dir():
        raise ValueError("Expected a local Laya checkpoint directory")
    for name in (
        "model.safetensors",
        "rl_agent_config.json",
        "tokenizer/tokenizer_config.json",
        "encoder/config.json",
    ):
        if not (checkpoint / name).is_file():
            raise FileNotFoundError(checkpoint / name)
    hashes = {
        p.relative_to(checkpoint).as_posix(): sha256(p)
        for p in checkpoint.rglob("*")
        if p.is_file()
    }
    agent = Agent(str(checkpoint), device=device, expected_sha256=hashes)
    if any(sha256(checkpoint / name) != digest for name, digest in hashes.items()):
        raise ValueError("Checkpoint artifact changed while loading")
    if str(agent.device) != device:
        raise ValueError(
            f"Laya device fallback: requested {device}, actual {agent.device}"
        )
    return agent, dict(checkpoint_files=hashes, device=device)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--predictions", type=Path)
    mode.add_argument(
        "--checkpoint", type=Path, help="Score raw held-out states once per safe chunk"
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-seconds", type=float, default=600)
    parser.add_argument("--max-options", type=int, default=20)
    parser.add_argument("--max-len", type=int, default=1024)
    parser.add_argument("--head-max-len", type=int, default=256)
    args = parser.parse_args()
    if args.checkpoint:
        agent, binding = load_local_agent(args.checkpoint, args.device)
        evaluate_agent(
            agent,
            read_jsonl(args.records),
            args.output,
            max_seconds=args.max_seconds,
            checkpoint_binding=binding,
            max_options=args.max_options,
            max_len=args.max_len,
            head_max_len=args.head_max_len,
        )
        return
    result = evaluate_records(read_jsonl(args.records), read_jsonl(args.predictions))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
