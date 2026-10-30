"""Run the approved remaining-mention experiment without changing old assignments.

Prepare freezes two occurrence cohorts. Run scores newly admitted rows forward,
then scores prior unresolved rows and new forward failures in reverse. Each
decision is saved immediately. Report needs no model and can run locally.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import math
import time
import uuid
from collections import Counter, defaultdict
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from GG_Data.entity_resolution.hundred_page_pilot.filter_qid_inventory import compatible
from GG_Data.entity_resolution.hundred_page_pilot.prepare_candidates import (
    group_mentions,
    prepare,
)
from GG_Data.entity_resolution.hundred_page_pilot.resolve_entities import (
    read_score_records,
    select_loop,
)
from GG_Data.entity_resolution.luke_pilot.data import read_jsonl, sha256, write_jsonl

LOG = logging.getLogger(__name__)
REVERSE_STOP = "This mention does not refer to any of the remaining entities."


def split_population(rows, remaining_groups, statuses):
    """Select occurrences, not every occurrence sharing a saved group ID."""
    remaining = [i for g in remaining_groups for i in g["source_row_indices"]]
    if len(remaining) != len(set(remaining)):
        raise ValueError("Remaining occurrence indices must be unique")
    selected = set(remaining)
    forward, previous = [], []
    for row in rows:
        index = row["source_row_index"]
        if index not in selected:
            continue
        status = statuses[index]
        if status not in {"SOURCE_REVIEW", "ENTITY_UNRESOLVED"}:
            raise ValueError(
                "Remaining population contains an assigned or excluded row"
            )
        (forward if status == "SOURCE_REVIEW" else previous).append(row)
    if len(forward) + len(previous) != len(remaining):
        raise ValueError("Some remaining occurrences were not found")
    return forward, previous


def unresolved_rows(forward, previous, forward_groups, selected_ids):
    accepted = {
        i
        for g in forward_groups
        if g["id"] in selected_ids
        for i in g["source_row_indices"]
    }
    return previous + [r for r in forward if r["source_row_index"] not in accepted]


def model_entity(entity):
    """A linked-title fallback is model text, never an official exact-match label."""
    name = entity.get("model_name") or entity.get("label")
    if not name:
        raise ValueError("Retained QID has no available model name")
    return dict(
        qid=entity["qid"],
        name=name,
        aliases=entity.get("model_aliases", entity.get("aliases")) or [],
        description=entity.get("description") or "",
    )


def reverse_jobs(groups, entities):
    by_page = defaultdict(list)
    for entity in entities:
        by_page[entity["page_id"], entity["revision_id"]].append(entity)
    return [
        dict(
            id=g["id"],
            page_id=g["page_id"],
            revision_id=g["revision_id"],
            mention=g,
            entities=[
                model_entity(e)
                for e in by_page[g["page_id"], g["revision_id"]]
                if compatible(e, g["type"])
            ],
        )
        for g in groups
    ]


def choose_reverse(scores, stop):
    if not all(math.isfinite(v) for v in [*scores.values(), stop]):
        raise ValueError("Scores must be finite")
    winner = min(scores, key=lambda q: (-scores[q], q)) if scores else None
    return winner if winner is not None and scores[winner] > stop else None


def option_scores(row: dict, expected: set) -> dict:
    """Reject damaged or stale saved options before either decision."""
    options = row["options"]
    scores = {r["id"]: r["score"] for r in options}
    if len(scores) != len(options) or set(scores) != expected:
        raise ValueError("Saved option identities differ")
    if not all(math.isfinite(v) for v in scores.values()):
        raise ValueError("Scores must be finite")
    return scores


def save_json(path, value):
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) == value:
        return
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def save_rows(path, rows):
    """On resume, keep an identical result and reject changed derived records."""
    if path.exists():
        if read_jsonl(path) != rows:
            raise ValueError("Derived result differs from the saved records")
    else:
        write_jsonl(path, rows)


def scoped_rows(rows, scopes, scope):
    allowed = {tuple(pair) for pair in scopes[str(scope)]["used_revisions"]}
    return [r for r in rows if (r["page_id"], r["revision_id"]) in allowed]


def bind_resume(receipt, binding, score_paths):
    """A score file is usable only with its original, identical receipt."""
    if receipt.exists():
        if json.loads(receipt.read_text(encoding="utf-8")) != binding:
            raise ValueError("Resume signature differs")
    elif any(p.exists() and p.stat().st_size for p in score_paths):
        raise ValueError("Saved scores have no original resume receipt")
    save_json(receipt, binding)


def prepare_run(ready_path, inventory_path, scopes_path, output):
    if output.exists():
        raise FileExistsError(output)
    ready = json.loads(ready_path.read_text(encoding="utf-8"))
    remaining_path = ready_path.parent / "remaining_groups.jsonl"
    if sha256(remaining_path) != ready["remaining_groups_sha256"]:
        raise ValueError("Frozen remaining groups changed")
    for role in (
        "old_mentions",
        "current_mentions",
        "old_links",
        "current_exact_links",
    ):
        if sha256(Path(ready["source_paths"][role])) != ready["source_sha256"][role]:
            raise ValueError(f"Frozen source changed: {role}")
    rows_table = pq.read_table(ready["source_paths"]["current_mentions"])
    with gzip.open(
        ready["source_paths"]["old_mentions"], "rt", encoding="utf-8"
    ) as stream:
        statuses = {
            r["source_row_index"]: r["processing_status"] for r in json.load(stream)
        }
    forward, previous = split_population(
        rows_table.to_pylist(), read_jsonl(remaining_path), statuses
    )
    if (len(forward), len(previous)) != (7277, 5852):
        raise ValueError("Approved cohort counts changed")
    entities = pq.read_table(inventory_path).to_pylist()
    for e in entities:
        if not all(
            k in e for k in ("qid_source_status", "type_categories", "type_unknown")
        ):
            raise ValueError("Use the shared enriched QID filter output")
        titles = e.get("linked_titles") or []
        e["model_name"] = e.get("label") or (titles[0] if titles else None)
        e["model_aliases"] = e.get("aliases") or titles[1:]
        e["model_name_basis"] = (
            "wikidata_label" if e.get("label") else "saved_linked_title_fallback"
        )
    output.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist(entities), output / "entities.parquet")
    for name, cohort in (("forward", forward), ("previous", previous)):
        pq.write_table(
            pa.Table.from_pylist(cohort, schema=rows_table.schema),
            output / f"{name}_mentions.parquet",
        )
    summary = prepare(
        output / "forward_mentions.parquet",
        output / "entities.parquet",
        output / "forward",
        80,
        exclude_date=True,
    )
    scopes = json.loads(scopes_path.read_text(encoding="utf-8"))["scopes"]
    save_json(output / "scopes.json", scopes)
    manifest = dict(
        created_utc=datetime.now(timezone.utc).isoformat(),
        forward_occurrences=len(forward),
        previous_unresolved_occurrences=len(previous),
        checkpoint_sha256=ready["source_sha256"]["checkpoint"],
        source_ready_sha256=sha256(ready_path),
        inventory_source_sha256=sha256(inventory_path),
        forward_preparation=summary,
        reverse_stop=REVERSE_STOP,
        reverse_stop_was_trained=False,
        sequence="7277 forward; reverse 5852 plus only forward failures",
        assignments_changed=False,
        active_work_seconds=None,
    )
    manifest["files"] = {
        str(p.relative_to(output)): sha256(p) for p in output.rglob("*") if p.is_file()
    }
    save_json(output / "manifest.json", manifest)
    return manifest


def run(input_dir, output, checkpoint, max_seconds, device, batch_size, scope=100):
    """One model restore; resumable per-question scores, with an execution cap."""
    import torch
    import transformers
    from transformers import AutoConfig, AutoModel, AutoTokenizer

    from GG_Data.entity_resolution.decision_model import model as model_module
    from GG_Data.entity_resolution.decision_model.model import (
        MODEL,
        REVISION,
        CandidateScorer,
        pair_texts,
    )

    started = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    if not 0 < max_seconds <= 4800:
        raise ValueError("Run cap must be positive and at most 4800 seconds")
    manifest_path = input_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if sha256(input_dir / name.replace("\\", "/")) != expected:
            raise ValueError(f"Prepared input changed: {name}")
    if sha256(checkpoint) != manifest["checkpoint_sha256"]:
        raise ValueError("Checkpoint differs from approved weights")
    output.mkdir(parents=True, exist_ok=True)
    config = AutoConfig.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL, revision=REVISION, local_files_only=True
    )
    assets = dict(
        vocabulary=tokenizer.get_vocab(),
        special_tokens=tokenizer.special_tokens_map,
        tokenizer=tokenizer.init_kwargs,
        config=config.to_dict(),
        encoding=(
            tokenizer.backend_tokenizer.to_str()
            if tokenizer.is_fast
            else sorted(
                (list(pair), rank) for pair, rank in tokenizer.bpe_ranks.items()
            )
        ),
    )
    binding = dict(
        input_sha256=sha256(manifest_path),
        checkpoint_sha256=sha256(checkpoint),
        code_sha256=sha256(Path(__file__)),
        helper_sha256={
            p.name: sha256(p)
            for p in [
                Path(model_module.__file__),
                Path(__file__).with_name("prepare_candidates.py"),
                Path(__file__).with_name("filter_qid_inventory.py"),
                Path(__file__).with_name("resolve_entities.py"),
            ]
        },
        tokenizer_config_sha256=hashlib.sha256(
            json.dumps(assets, sort_keys=True, default=str).encode()
        ).hexdigest(),
        torch_version=torch.__version__,
        transformers_version=transformers.__version__,
        scope=scope,
        device=device,
        batch_size=batch_size,
        max_length=256,
        dtype="bfloat16_autocast" if device == "cuda" else "float32",
    )
    receipt = output / "inputs.json"
    bind_resume(receipt, binding, list(output.glob("*_scores.jsonl")))
    torch.set_num_threads(4)
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if (
        saved["model_id"] != MODEL
        or saved["revision"] != REVISION
        or saved.get("head_only")
    ):
        raise ValueError("Expected the full tuned LUKE checkpoint")
    model = CandidateScorer(AutoModel.from_config(config))
    model.load_state_dict(saved["model"], strict=True)
    del saved
    model.to(device).eval()
    scopes = json.loads((input_dir / "scopes.json").read_text())

    def tier(job):
        return (
            (
                0
                if job["page_id"] in scopes["3"]["page_ids"]
                else 1 if job["page_id"] in scopes["10"]["page_ids"] else 2
            ),
            job["page_id"],
            job["id"],
        )

    def score(queries, options):
        values = []
        with torch.inference_mode():
            for i in range(0, len(options), batch_size):
                if time.monotonic() - started >= max_seconds:
                    raise TimeoutError(
                        "Execution limit reached; completed questions are saved"
                    )
                encoded = tokenizer(
                    queries[i : i + batch_size],
                    options[i : i + batch_size],
                    padding=True,
                    truncation=True,
                    max_length=256,
                    return_tensors="pt",
                )
                precision = (
                    torch.autocast("cuda", dtype=torch.bfloat16)
                    if device == "cuda"
                    else nullcontext()
                )
                with precision:
                    logits = model(**{k: v.to(device) for k, v in encoded.items()})
                values.extend(logits.float().cpu().tolist())
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Nonfinite model score")
        return values

    def evaluate(jobs, direction):
        # Reverse texts depend on forward decisions; bind the complete derived
        # jobs before resume, not only their names and IDs.
        signature = dict(
            jobs_sha256=hashlib.sha256(
                json.dumps(jobs, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest(),
            **binding,
        )
        direction_path = output / f"{direction}_inputs.json"
        path = output / f"{direction}_scores.jsonl"
        bind_resume(direction_path, signature, [path])
        prior = read_score_records(path)
        cached = {r["id"]: r for r in prior}
        if len(cached) != len(prior) or not set(cached) <= {j["id"] for j in jobs}:
            raise ValueError("Saved score identities differ from current jobs")
        with path.open("a", encoding="utf-8") as stream:
            for index, job in enumerate(sorted(jobs, key=tier)):
                if job["id"] in cached:
                    continue
                if direction == "forward":
                    queries, options, _ = pair_texts(job)
                    ids = [c["id"] for c in job["candidates"]]
                else:
                    _, mention_texts, _ = pair_texts(
                        dict(
                            entity=dict(name="", aliases=[], description=""),
                            candidates=[job["mention"]],
                        )
                    )
                    options = [
                        pair_texts(dict(entity=e, candidates=[]))[0][0]
                        for e in job["entities"]
                    ]
                    options.append(REVERSE_STOP)
                    queries = [mention_texts[0]] * len(options)
                    ids = [e["qid"] for e in job["entities"]]
                values = score(queries, options)
                row = dict(
                    id=job["id"],
                    options=[dict(id=k, score=v) for k, v in zip([*ids, None], values)],
                )
                stream.write(json.dumps(row) + "\n")
                stream.flush()
                cached[row["id"]] = row
                if index % 50 == 0:
                    LOG.info(
                        json.dumps(
                            dict(
                                direction=direction,
                                completed=len(cached),
                                total=len(jobs),
                                tier=tier(job)[0],
                                elapsed_seconds=time.monotonic() - started,
                            )
                        )
                    )
        return cached

    status = "FAILED"
    try:
        forward_jobs = [
            j
            for j in scoped_rows(
                read_jsonl(input_dir / "forward/jobs.jsonl"), scopes, scope
            )
            if j["candidates"]
        ]
        forward_scores = evaluate(forward_jobs, "forward")
        forward_pairs = []
        for job in forward_jobs:
            scores = option_scores(
                forward_scores[job["id"]], {c["id"] for c in job["candidates"]} | {None}
            )
            selected, _ = select_loop(
                {k: v for k, v in scores.items() if k is not None}, scores[None]
            )
            forward_pairs.extend(
                dict(
                    page_id=job["page_id"],
                    revision_id=job["revision_id"],
                    qid=job["qid"],
                    group_id=g,
                    method="experimental_forward",
                )
                for g in selected
            )
        forward_pairs.extend(
            scoped_rows(
                pq.read_table(input_dir / "forward/exact_pairs.parquet").to_pylist(),
                scopes,
                scope,
            )
        )
        save_rows(output / "forward_pairs.jsonl", forward_pairs)
        forward_groups = scoped_rows(
            read_jsonl(input_dir / "forward/groups.jsonl"), scopes, scope
        )
        rows = unresolved_rows(
            scoped_rows(
                pq.read_table(input_dir / "forward_mentions.parquet").to_pylist(),
                scopes,
                scope,
            ),
            scoped_rows(
                pq.read_table(input_dir / "previous_mentions.parquet").to_pylist(),
                scopes,
                scope,
            ),
            forward_groups,
            {p["group_id"] for p in forward_pairs},
        )
        groups = group_mentions(rows, exclude_date=True)
        jobs = reverse_jobs(
            groups, pq.read_table(input_dir / "entities.parquet").to_pylist()
        )
        save_rows(output / "reverse_groups.jsonl", groups)
        save_rows(output / "reverse_jobs.jsonl", jobs)
        LOG.info(
            "Forward complete; reverse occurrences=%d groups=%d pair+stop=%d",
            len(rows),
            len(groups),
            sum(len(j["entities"]) + 1 for j in jobs),
        )
        reverse_scores = evaluate(jobs, "reverse")
        reverse_pairs = []
        for job in jobs:
            scores = option_scores(
                reverse_scores[job["id"]], {e["qid"] for e in job["entities"]} | {None}
            )
            winner = choose_reverse(
                {k: v for k, v in scores.items() if k is not None}, scores[None]
            )
            if winner:
                reverse_pairs.append(
                    dict(
                        group_id=job["id"],
                        page_id=job["page_id"],
                        revision_id=job["revision_id"],
                        qid=winner,
                        method="experimental_reverse",
                    )
                )
        save_rows(output / "reverse_pairs.jsonl", reverse_pairs)
        status = "COMPLETED"
    finally:
        runtime = dict(
            run_id=uuid.uuid4().hex,
            started_utc=started_utc,
            finished_utc=datetime.now(timezone.utc).isoformat(),
            cap_seconds=max_seconds,
            status=status,
            elapsed_seconds=time.monotonic() - started,
            active_work_seconds=None,
            model=MODEL,
            revision=REVISION,
            **binding,
        )
        with (output / "runtime_history.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(runtime) + "\n")
        save_json(output / "runtime.json", runtime)
    return report(input_dir, output)


def report(input_dir, output):
    binding = json.loads((output / "inputs.json").read_text())
    manifest_path = input_dir / "manifest.json"
    if sha256(manifest_path) != binding["input_sha256"]:
        raise ValueError("Reporting input manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if sha256(input_dir / name.replace("\\", "/")) != expected:
            raise ValueError(f"Reporting input changed: {name}")
    scope = binding["scope"]
    scopes = json.loads((input_dir / "scopes.json").read_text())
    forward_groups = scoped_rows(
        read_jsonl(input_dir / "forward/groups.jsonl"), scopes, scope
    )
    forward_count = len(
        scoped_rows(
            pq.read_table(input_dir / "forward_mentions.parquet").to_pylist(),
            scopes,
            scope,
        )
    )
    previous_count = len(
        scoped_rows(
            pq.read_table(input_dir / "previous_mentions.parquet").to_pylist(),
            scopes,
            scope,
        )
    )
    reverse_groups = read_jsonl(output / "reverse_groups.jsonl")
    forward_pairs = read_jsonl(output / "forward_pairs.jsonl")
    reverse_pairs = read_jsonl(output / "reverse_pairs.jsonl")
    entities = {
        (e["page_id"], e["revision_id"], e["qid"]): e
        for e in pq.read_table(input_dir / "entities.parquet").to_pylist()
    }
    proposals = []
    for direction, groups, pairs in (
        ("forward", forward_groups, forward_pairs),
        ("reverse", reverse_groups, reverse_pairs),
    ):
        by_id = {g["id"]: g for g in groups}
        for pair in pairs:
            group = by_id[pair["group_id"]]
            entity = entities[pair["page_id"], pair["revision_id"], pair["qid"]]
            if (group["page_id"], group["revision_id"]) != (
                pair["page_id"],
                pair["revision_id"],
            ) or not compatible(entity, group["type"]):
                raise ValueError("Proposal bypassed the shared source/type/page filter")
            proposals.extend(
                dict(
                    source_row_index=i,
                    group_id=group["id"],
                    name=group["name"],
                    type=group["type"],
                    page_id=group["page_id"],
                    revision_id=group["revision_id"],
                    qid=pair["qid"],
                    qid_name=entity["model_name"],
                    direction=direction,
                    experimental=True,
                )
                for i in group["source_row_indices"]
            )
    save_rows(output / "occurrence_proposals.jsonl", proposals)
    forward_ids = {
        r["source_row_index"] for r in proposals if r["direction"] == "forward"
    }
    reverse_ids = {
        r["source_row_index"] for r in proposals if r["direction"] == "reverse"
    }
    if forward_ids & reverse_ids:
        raise ValueError("Forward successes were incorrectly admitted to reverse")
    reverse_jobs_saved = read_jsonl(output / "reverse_jobs.jsonl")
    empty_reverse = {j["id"] for j in reverse_jobs_saved if not j["entities"]}
    empty_count = sum(
        len(g["source_row_indices"]) for g in reverse_groups if g["id"] in empty_reverse
    )
    summary = dict(
        status="COMPLETED_EXPERIMENTAL",
        scope=scope,
        forward_input_occurrences=forward_count,
        previous_unresolved_occurrences=previous_count,
        forward_selected_occurrences=len(forward_ids),
        forward_selected_pairs=len(forward_pairs),
        new_forward_failures=forward_count - len(forward_ids),
        reverse_input_occurrences=sum(
            len(g["source_row_indices"]) for g in reverse_groups
        ),
        reverse_selected_occurrences=len(reverse_ids),
        reverse_selected_pairs=len(reverse_pairs),
        reverse_no_compatible_qid_groups=len(empty_reverse),
        reverse_no_compatible_qid_occurrences=empty_count,
        reverse_stop_occurrences=sum(
            len(g["source_row_indices"]) for g in reverse_groups
        )
        - len(reverse_ids)
        - empty_count,
        remaining_occurrences=forward_count
        + previous_count
        - len(forward_ids)
        - len(reverse_ids),
        proposal_occurrences_by_type=dict(Counter(r["type"] for r in proposals)),
        assignments_changed=False,
        measured_accuracy=None,
        reverse_stop_was_trained=False,
    )
    save_json(output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "report"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--entities", type=Path)
    parser.add_argument("--scopes", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--max-seconds", type=float, default=4800)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--scope", type=int, choices=(3, 10, 100), default=100)
    args = parser.parse_args()
    if args.max_seconds <= 0 or args.batch_size <= 0:
        parser.error("Positive resource limits required")
    if args.action == "prepare":
        if not args.entities or not args.scopes:
            parser.error("Prepare requires --entities and --scopes")
        result = prepare_run(args.input, args.entities, args.scopes, args.output)
    elif args.action == "run":
        if not args.checkpoint:
            parser.error("Run requires --checkpoint")
        result = run(
            args.input,
            args.output,
            args.checkpoint,
            args.max_seconds,
            args.device,
            args.batch_size,
            args.scope,
        )
    else:
        result = report(args.input, args.output)
    LOG.info(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
