"""Compare frozen/final decisions with the saved trigram baseline, without tuning."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

from data import metric_summary, read_jsonl, sha256, write_jsonl


def wilson(hits: int, total: int) -> list[float] | None:
    """Descriptive 95% Wilson interval; records are not independent page samples."""
    if not total:
        return None
    z = 1.959963984540054
    p = hits / total
    denominator = 1 + z*z/total
    centre = (p + z*z/(2*total)) / denominator
    radius = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denominator
    return [max(0., centre-radius), min(1., centre+radius)]


def baseline_predictions(sample: list[dict], records: list[dict]) -> tuple[list[dict], list[dict]]:
    def key(row, baseline=False):
        return (int(row["wiki_page_id"]), int(row["wiki_revision_id"]),
                row["source_name" if baseline else "mention"], row["source_type" if baseline else "type"])
    index = {key(r, True): r for r in records}
    if len(index) != len(records) or set(index) != {key(r) for r in sample}:
        raise ValueError("Baseline must contain exactly the same unique page/revision/name/type records")
    forced, accepted = [], []
    for row in sample:
        b = index[key(row)]
        target = b["target_qid"] or None
        if target not in {c["id"] for c in row["candidates"]}:
            raise ValueError("Baseline target outside saved same-page pool")
        p = {"id": row["id"], "prediction": target, "score": float(b["top_score"]),
             "ranking": [{"id": target}], "ranking_complete": False, "baseline_status": b["status"]}
        forced.append(p)
        accepted.append({**p, "prediction": target if b["status"] in
                         {"exact_name_unique", "strong_lexical_candidate"} else None})
    return forced, accepted


def ranked_metrics(refs: list[dict], preds: list[dict]) -> dict:
    result = metric_summary(refs, preds)
    index = {p["id"]: p for p in preds}
    ranks = []
    for r in refs:
        if not r.get("verified", True) or r["target"] is None:
            continue
        targets = r.get("acceptable_targets", [r["target"]])
        ranking = [c["id"] for c in index[r["id"]].get("ranking", []) if c["id"] is not None]
        positions = [ranking.index(t)+1 for t in targets if t in ranking]
        ranks.append(min(positions) if positions else None)
    result["candidate_mrr_linked"] = sum(1/r if r else 0 for r in ranks)/len(ranks) if ranks else None
    result["candidate_recall_at_5_linked"] = sum(r is not None and r <= 5 for r in ranks)/len(ranks) if ranks else None
    if any(not p.get("ranking_complete", True) for p in preds):
        result["candidate_mrr_linked"] = None
        result["candidate_recall_at_5_linked"] = None
    result["accuracy_wilson95_descriptive"] = wilson(result["correct"], result["verified"])
    result["none_precision_wilson95_descriptive"] = wilson(result["correct_none"], result["predicted_none"])
    return result


def compare_systems(sample: list[dict], refs: list[dict], systems: dict[str, list[dict]]) -> dict:
    sample_index = {r["id"]: r for r in sample}
    if len(sample_index) != len(sample) or {r["id"] for r in refs} != set(sample_index):
        raise ValueError("Sample/reference IDs differ")
    for r in refs:
        if r.get("verified", True) and r["target"] is not None:
            if r["target"] not in {c["id"] for c in sample_index[r["id"]]["candidates"]}:
                raise ValueError("Linked reference outside candidate pool")
    result = {"candidate_reference_counts": {
        "total": len(sample),
        "verified_linked_in_pool": sum(r.get("verified", True) and r["target"] is not None for r in refs),
        "verified_none": sum(r.get("verified", True) and r["target"] is None for r in refs),
        "unverified": sum(not r.get("verified", True) for r in refs)}, "systems": {}}
    for name, predictions in systems.items():
        overall = ranked_metrics(refs, predictions)
        pi = {p["id"]: p for p in predictions}
        groups = {}
        for field in ("type", "wiki_page_id"):
            groups["by_type" if field == "type" else "by_page"] = {}
            for value in sorted({r[field] for r in sample}, key=str):
                subset = [r for r in refs if sample_index[r["id"]][field] == value]
                groups["by_type" if field == "type" else "by_page"][str(value)] = ranked_metrics(subset, [pi[r["id"]] for r in subset])
        result["systems"][name] = {"overall": overall, **groups}
    return result


def run(inputs: Path, outputs: Path, baseline: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    sample = read_jsonl(inputs/"sample.jsonl")
    refs = read_jsonl(inputs/"references.jsonl")
    freeze = json.loads((inputs/"reference_freeze.json").read_text())
    if sha256(inputs/"references.jsonl") != freeze["sha256"]:
        raise ValueError("Frozen reference hash mismatch")
    with baseline.open(encoding="utf-8-sig", newline="") as stream:
        forced, accepted = baseline_predictions(sample, list(csv.DictReader(stream)))
    systems = {"frozen_head": read_jsonl(outputs/"frozen_sample_predictions.jsonl"),
               "selected_final": read_jsonl(outputs/"sample_predictions.jsonl"),
               "saved_trigram_forced_top1": forced, "saved_trigram_original_acceptance_or_none": accepted}
    result = compare_systems(sample, refs, systems)
    result["reference_sha256"] = freeze["sha256"]
    result["reference_methods"] = dict(Counter(r["reference_method"] for r in refs))
    result["limits"] = ["Assistant source review, not independent human annotation",
        "91 unverified cases excluded from accuracy; all 642 receive decisions",
        "Ten selected pages, not a random corpus sample; Wilson intervals are descriptive",
        "NONE means no identical entity in the saved same-page pool",
        "Forced baseline ties retain the previously saved top result",
        "Saved baseline ranking metrics are omitted because only its top identity is imported",
        "Candidate reference counts do not measure recall against all Wikidata entities"]
    index = {r["id"]: r for r in refs}
    pi = {name: {p["id"]: p for p in preds} for name, preds in systems.items()}
    decisions = []
    for s in sample:
        r = index[s["id"]]
        names = {c["id"]: c["name"] for c in s["candidates"]}
        row = {k: s[k] for k in ("id", "wiki_page_id", "wiki_revision_id", "source_title", "mention", "type", "context")}
        row.update({"verified": r["verified"], "reference_qid": r["target"],
                    "reference_name": names.get(r["target"]), "reference_method": r["reference_method"],
                    "reference_notes": r.get("reference_notes", ""), "candidate_count": len(names)})
        for name in systems:
            p = pi[name][s["id"]]
            row[name+"_qid"] = p["prediction"]
            row[name+"_name"] = names.get(p["prediction"])
            row[name+"_correct"] = (p["prediction"] in r.get("acceptable_targets", [r["target"]])) if r["verified"] else None
        decisions.append(row)
    write_jsonl(destination/"decisions.jsonl", decisions)
    import pyarrow as pa
    import pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pylist(decisions), destination/"decisions.parquet")
    with (destination/"decisions.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(decisions[0]))
        writer.writeheader()
        writer.writerows(decisions)
    (destination/"comparison.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for arg in ("inputs", "outputs", "baseline", "destination"):
        parser.add_argument("--"+arg, type=Path, required=True)
    args = parser.parse_args()
    run(args.inputs, args.outputs, args.baseline, args.destination)
