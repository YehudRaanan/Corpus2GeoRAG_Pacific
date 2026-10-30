"""Compare existing weights on source-labelled pairs in both input orders.

This separate diagnostic does not modify the production matching process.
Cases must be frozen before inference. Each case has one reviewed gold QID
and same-page distractors. Removed-gold controls reuse independent pair scores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
from transformers import AutoConfig, AutoModel, AutoTokenizer

from .model import MODEL, REVISION, CandidateScorer, pair_texts

REVERSE_STOP = "This mention does not refer to any of the remaining entities."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    started = time.perf_counter()
    cases_bytes = args.cases.read_bytes()
    cases = json.loads(cases_bytes)
    for case in cases:
        ids = [entity["qid"] for entity in case["entities"]]
        if len(ids) != len(set(ids)) or case["gold_qid"] not in ids:
            raise ValueError("Each reviewed gold must occur once in its pool")
    torch.set_num_threads(4)
    # The full checkpoint includes the encoder. Do not download base weights.
    saved = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    if saved["model_id"] != MODEL or saved["revision"] != REVISION:
        raise ValueError("Unexpected encoder identity")
    if saved.get("head_only"):
        raise ValueError("This diagnostic requires the full trained checkpoint")
    config = AutoConfig.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
    model = CandidateScorer(AutoModel.from_config(config))
    model.load_state_dict(saved["model"], strict=True)
    del saved
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL, revision=REVISION, local_files_only=True
    )
    restored = time.perf_counter()
    print(json.dumps({"stage": "restored", "seconds": restored - started}), flush=True)
    results = []
    with torch.inference_mode():
        for case in cases:
            queries, options, layout = [], [], []
            for entity in case["entities"]:
                first, second, _ = pair_texts(
                    {"entity": entity, "candidates": [case["mention"]]}
                )
                # Canonical entity->mention and entity->trained stop.
                queries.extend(first)
                options.extend(second)
                layout.extend(
                    [(entity["qid"], "forward"), (entity["qid"], "forward_stop")]
                )
                # Actual reversal: mention/context first, entity text second.
                queries.append(second[0])
                options.append(first[0])
                layout.append((entity["qid"], "reverse"))
            queries.append(queries[2])
            options.append(REVERSE_STOP)
            layout.append(("STOP", "reverse_stop"))
            logits = []
            for start in range(0, len(options), 4):
                encoded = tokenizer(
                    queries[start : start + 4],
                    options[start : start + 4],
                    padding=True,
                    truncation=True,
                    max_length=256,
                    return_tensors="pt",
                )
                logits.extend(model(**encoded).tolist())
            scores = {entity["qid"]: {} for entity in case["entities"]}
            for (qid, mode), value in zip(layout, logits):
                scores.setdefault(qid, {})[mode] = value
            stop = scores.pop("STOP")["reverse_stop"]
            ranked = sorted(
                scores, key=lambda qid: scores[qid]["reverse"], reverse=True
            )
            winner = ranked[0] if scores[ranked[0]]["reverse"] > stop else None
            # All pairs score independently: deleting gold needs no new forward pass.
            remaining = [qid for qid in ranked if qid != case["gold_qid"]]
            control = remaining[0] if scores[remaining[0]]["reverse"] > stop else None
            forward_rank = sorted(
                scores, key=lambda qid: scores[qid]["forward"], reverse=True
            )
            result = {
                "id": case["id"],
                "mention": case["mention"]["name"],
                "gold_qid": case["gold_qid"],
                "scores": scores,
                "reverse_stop": stop,
                "reverse_candidate_ranking": ranked,
                "reverse_selected": winner,
                "forward_raw_top": forward_rank[0],
                "forward_accepted": [
                    qid
                    for qid in scores
                    if scores[qid]["forward"] > scores[qid]["forward_stop"]
                ],
                "removed_gold_selected": control,
            }
            results.append(result)
            print(
                json.dumps(
                    {
                        "stage": "case",
                        "id": case["id"],
                        "selected": winner,
                        "gold": case["gold_qid"],
                        "elapsed_seconds": time.perf_counter() - started,
                    }
                ),
                flush=True,
            )
    report = {
        "case_sha256": hashlib.sha256(cases_bytes).hexdigest(),
        "checkpoint_sha256": hashlib.file_digest(
            args.checkpoint.open("rb"), "sha256"
        ).hexdigest(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "model_id": MODEL,
        "revision": REVISION,
        "dtype": "float32",
        "device": "cpu",
        "max_length": 256,
        "pair_batch_size": 4,
        "threads": 4,
        "reverse_stop_sentence": REVERSE_STOP,
        "reverse_stop_was_trained": False,
        "summary": {
            "cases": len(results),
            "reverse_candidate_top_correct": sum(
                r["reverse_candidate_ranking"][0] == r["gold_qid"] for r in results
            ),
            "reverse_selection_correct": sum(
                r["reverse_selected"] == r["gold_qid"] for r in results
            ),
            "reverse_stopped_with_gold_present": sum(
                r["reverse_selected"] is None for r in results
            ),
            "removed_gold_stop_correct": sum(
                r["removed_gold_selected"] is None for r in results
            ),
            "forward_raw_top_correct": sum(
                r["forward_raw_top"] == r["gold_qid"] for r in results
            ),
            "forward_gold_accepted": sum(
                r["gold_qid"] in r["forward_accepted"] for r in results
            ),
        },
        "runtime_seconds": time.perf_counter() - started,
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report["summary"]), flush=True)


if __name__ == "__main__":
    main()
