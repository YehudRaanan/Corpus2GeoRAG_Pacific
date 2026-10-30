"""Canonical joint Laya questions, strict encoding and chunk-local removal.

Use the pinned upstream Laya package on PYTHONPATH. This module does not load
weights, install packages, retrieve candidates, or assign production identities.
"""

from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from typing import Any

STOP_KEY = "STOP"
STOP_TEXT = {
    "forward": "None of the remaining mention groups refers to this entity.",
    "reverse": "This mention does not refer to any of the remaining entities.",
}
SOURCE_REVISION = "9afa7f3d4af18f8fa0c25517a440a05d10395b99"
CHECKPOINT_REVISION = "7b928d828b7b0e022f929d9bd2e44165aa270148"


def _option_key(identity: str) -> str:
    # Opaque keys expose no QID/title and remain stable after reorder/removal.
    return "c" + hashlib.sha256(identity.encode()).hexdigest()[:8]


def _validate_record(record: dict, direction: str) -> list[str]:
    if direction not in STOP_TEXT or record.get("direction", direction) != direction:
        raise ValueError("Invalid or inconsistent direction")
    if (
        not isinstance(record.get("entity"), dict)
        or not isinstance(record["entity"].get("name"), str)
        or not record["entity"]["name"].strip()
    ):
        raise ValueError("Query entity requires a name")
    ids = [c.get("id") for c in record["candidates"]]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Candidate identities must be distinct nonempty strings")
    if any(
        not isinstance(c.get("name"), str) or not c["name"].strip()
        for c in record["candidates"]
    ):
        raise ValueError("Every candidate requires its original name")
    if len({_option_key(i) for i in ids}) != len(ids):
        raise ValueError("Stable option-key collision")
    if "positive_ids" in record:
        positives = record["positive_ids"]
        if len(set(positives)) != len(positives) or not set(positives).issubset(ids):
            raise ValueError(
                "Positive identities are duplicated or missing from candidates"
            )
        if "target_probabilities" in record:
            expected = [
                float(i in positives) / len(positives) if positives else 0.0
                for i in ids
            ] + [float(not positives)]
            target = record["target_probabilities"]
            if len(target) != len(expected) or any(
                not math.isfinite(float(p)) or abs(float(p) - q) > 1e-8
                for p, q in zip(target, expected)
            ):
                raise ValueError(
                    "Invalid gold probabilities or changed positive target set"
                )
    return ids


def _evidence(item: dict) -> str:
    return "\n".join(
        f"{field.capitalize()}: {item[field]}"
        for field in ("description", "type", "context")
        if item.get(field)
    )


def make_question(record: dict, direction: str) -> dict:
    """Format one complete decision; missing positive_ids means unlabelled input.

    Metadata retains identities/provenance but only state/questions enter inference.
    Names, descriptions and types are never shortened. Any context shortening is
    explicit in the raw chunk and in this row's metadata.
    """
    ids = _validate_record(record, direction)
    criteria = {_option_key(c["id"]): c["name"] for c in record["candidates"]}
    criteria[STOP_KEY] = STOP_TEXT[direction]
    option_ids = {_option_key(identity): identity for identity in ids}
    option_ids[STOP_KEY] = None
    entity = record["entity"]
    state = f"Query {'entity' if direction == 'forward' else 'mention'}: {entity['name']}\n{_evidence(entity)}"
    for candidate in record["candidates"]:
        evidence = _evidence(candidate)
        if evidence:
            state += f"\nEvidence for {_option_key(candidate['id'])}:\n{evidence}"
    noun = "mention group" if direction == "forward" else "entity"
    row = {
        "state": state,
        "questions": {
            "match": {
                "type": "choice",
                "instructions": f"Choose a {noun} that refers to the query. Otherwise choose STOP.",
                "criteria": criteria,
            }
        },
        "metadata": {
            **{
                k: deepcopy(v)
                for k, v in record.items()
                if k not in {"entity", "candidates", "target_probabilities"}
            },
            "option_ids": option_ids,
            "direction": direction,
        },
    }
    if "positive_ids" in record:
        positive = set(record["positive_ids"])
        row["gold"] = {
            "match": {
                "probabilities": {
                    key: (
                        float(identity in positive) / len(positive)
                        if positive
                        else float(key == STOP_KEY)
                    )
                    for key, identity in option_ids.items()
                }
            }
        }
    return row


def token_diagnostics(
    tokenizer: Any, row: dict, max_len: int, head_max_len: int
) -> dict:
    """Compare the upstream encoded head/state with the complete rendered input."""
    from laya.common import build_head, build_sequence, encode_text, render_options
    from laya.train import to_internal

    q = to_internal("match", row["questions"]["match"])
    head, markers, stats = build_head(tokenizer, q, head_max_len)
    ends = markers[1:] + [len(head) - 1]
    spans = [head[start + 1 : end] for start, end in zip(markers, ends)]
    expected = [
        encode_text(
            tokenizer,
            " " + option.replace(tokenizer.mask_token, " "),
            add_special_tokens=False,
        )["input_ids"]
        for option in render_options(q)
    ]
    full_options = len(spans) == len(expected) and all(
        a == b for a, b in zip(spans, expected)
    )
    sequence, surviving, _, truncation = build_sequence(
        tokenizer,
        row["state"],
        q,
        max_len,
        head_max_len,
        return_stats=True,
        return_truncation_stats=True,
    )
    full_instruction = encode_text(
        tokenizer,
        f"choice question: {q['ins']}".replace(tokenizer.mask_token, " "),
        add_special_tokens=False,
    )["input_ids"]
    full_instruction_retained = head[1 : markers[0] - 1] == full_instruction
    fits = (
        full_options
        and full_instruction_retained
        and len(surviving) == len(expected)
        and not truncation["truncated"]
        and stats["options_distinct"] == stats["options"]
    )
    return {
        **stats,
        **truncation,
        "sequence_tokens": len(sequence),
        "head_tokens": len(head),
        "full_option_text_retained": full_options,
        "full_instruction_retained": full_instruction_retained,
        "fits": fits,
    }


def _chunk(record: dict, candidates: list[dict]) -> dict:
    result = {**record, "candidates": candidates}
    result.pop("target_probabilities", None)
    if "positive_ids" in record:
        pool = {candidate["id"] for candidate in candidates}
        result["positive_ids"] = [
            identity for identity in record["positive_ids"] if identity in pool
        ]
        result["synthetic_stop"] = not result["positive_ids"]
    return result


def _shorten_contexts(record: dict, tokenizer: Any, limit: int) -> dict:
    result = deepcopy(record)
    changes = list(result.get("context_shortening", []))
    for label, item in [("query", result["entity"])] + [
        (candidate["id"], candidate) for candidate in result["candidates"]
    ]:
        context = item.get("context", "")
        tokens = tokenizer(context, add_special_tokens=False)["input_ids"]
        if len(tokens) > limit:
            # Keep both ends; the separately retained name still identifies the query.
            kept = tokens[: (limit + 1) // 2] + (
                tokens[-(limit // 2) :] if limit // 2 else []
            )
            item["context"] = (
                tokenizer.decode(kept, skip_special_tokens=False) if kept else ""
            )
            changes.append(
                {
                    "identity": label,
                    "original_tokens": len(tokens),
                    "retained_tokens": len(kept),
                    "policy": "context_head_tail",
                }
            )
    result["context_shortening"] = changes
    return result


def partition_record(
    record: dict,
    direction: str,
    *,
    tokenizer: Any,
    max_len: int = 1024,
    head_max_len: int = 256,
    max_options: int = 20,
) -> list[dict]:
    """Partition every retained candidate without upstream truncation or loss.

    Full evidence is preferred. A singleton that still cannot fit gets an
    explicit context-only reduction, or raises. This never discards identities,
    names, descriptions or types. max_options excludes the additional STOP.
    """
    ids = _validate_record(record, direction)
    if max_options < 1 or head_max_len < 32 or max_len <= head_max_len:
        raise ValueError("Invalid decision token/option budgets")
    chunks, pending = [], []

    def fit(raw: dict) -> bool:
        return token_diagnostics(
            tokenizer, make_question(raw, direction), max_len, head_max_len
        )["fits"]

    for candidate in record["candidates"]:
        trial = _chunk(record, pending + [candidate])
        if len(pending) < max_options and fit(trial):
            pending.append(candidate)
            continue
        if pending:
            chunks.append(_chunk(record, pending))
            pending = []
        single = _chunk(record, [candidate])
        if fit(single):
            pending = [candidate]
            continue
        for limit in (128, 64, 32, 16, 8, 0):
            shortened = _shorten_contexts(single, tokenizer, limit)
            if fit(shortened):
                chunks.append(shortened)
                break
        else:
            raise ValueError(
                f"Candidate {candidate['id']!r} cannot fit without losing option name, instruction or non-context evidence"
            )
    if pending or not chunks:
        chunks.append(_chunk(record, pending))
    if [c["id"] for chunk in chunks for c in chunk["candidates"]] != ids:
        raise ValueError("Partition lost or reordered candidate identities")
    full_positive = record.get(
        "remaining_full_positive_ids",
        set(record.get("full_positive_ids", record.get("positive_ids", [])))
        - set(record.get("removed_ids", [])),
    )
    for index, chunk in enumerate(chunks):
        if not fit(chunk):
            raise ValueError("Empty decision/query cannot fit token budget")
        chunk.update(
            chunk_index=index,
            chunk_count=len(chunks),
            original_candidate_ids=ids,
            original_positive_ids=record.get("positive_ids"),
            retrieval_missing_positive_ids=sorted(set(full_positive) - set(ids)),
        )
        chunk["token_diagnostics"] = token_diagnostics(
            tokenizer, make_question(chunk, direction), max_len, head_max_len
        )
    return chunks


def partition_removal_states(
    records: list[dict],
    *,
    tokenizer: Any,
    max_len: int = 1024,
    head_max_len: int = 256,
    max_options: int = 20,
) -> list[dict]:
    """Use each base's initial partition for all labelled removal states.

    Include the initial state for every base. Empty intersections remain local
    STOP examples, exactly as inference still asks STOP after the final removal.
    This helper never re-packs a later state into different candidate chunks.
    """
    initials = {}
    for record in records:
        if record.get("removal_index") == 0:
            key = (record["direction"], record.get("base_id", record["id"]))
            if key in initials:
                raise ValueError("Duplicate initial state for removal base")
            initials[key] = record
    layouts = {}
    output = []
    for record in records:
        direction = record["direction"]
        key = (direction, record.get("base_id", record["id"]))
        if key not in initials:
            raise ValueError("Removal states require their original initial pool")
        if key not in layouts:
            layouts[key] = partition_record(
                initials[key],
                direction,
                tokenizer=tokenizer,
                max_len=max_len,
                head_max_len=head_max_len,
                max_options=max_options,
            )
        ids = _validate_record(record, direction)
        allowed = set(layouts[key][0]["original_candidate_ids"])
        if not set(ids).issubset(allowed):
            raise ValueError("Removal state added identities outside initial pool")
        original = initials[key]
        original_candidates = {c["id"]: c for c in original["candidates"]}
        if record["entity"] != original["entity"] or any(
            c != original_candidates[c["id"]] for c in record["candidates"]
        ):
            raise ValueError("Removal state changed original query/candidate evidence")
        for initial_chunk in layouts[key]:
            chunk = _chunk(
                record,
                [
                    candidate
                    for candidate in initial_chunk["candidates"]
                    if candidate["id"] in ids
                ],
            )
            # A context-reduced singleton keeps the exact evidence used initially.
            chunk["entity"] = initial_chunk["entity"]
            for field in (
                "chunk_index",
                "chunk_count",
                "original_candidate_ids",
                "context_shortening",
            ):
                if field in initial_chunk:
                    chunk[field] = initial_chunk[field]
            full_positive = set(
                record.get(
                    "remaining_full_positive_ids",
                    record.get("full_positive_ids", record.get("positive_ids", [])),
                )
            ) - set(record.get("removed_ids", []))
            chunk["retrieval_missing_positive_ids"] = sorted(full_positive - set(ids))
            chunk["token_diagnostics"] = token_diagnostics(
                tokenizer, make_question(chunk, direction), max_len, head_max_len
            )
            if not chunk["token_diagnostics"]["fits"]:
                raise ValueError(
                    "Fixed removal chunk no longer fits initial token budget"
                )
            output.append(chunk)
    return output


def strict_items_from_rows(
    tokenizer: Any, rows: list[dict], max_len: int, head_max_len: int
) -> list[dict]:
    """Reuse upstream preprocessing, failing instead of skipping or uniform gold."""
    from laya.train import items_from_rows

    for index, row in enumerate(rows):
        criteria = row["questions"]["match"]["criteria"]
        gold = row.get("gold", {}).get("match", {}).get("probabilities", {})
        if (
            set(gold) != set(criteria)
            or any(not math.isfinite(float(p)) or float(p) < 0 for p in gold.values())
            or not math.isclose(sum(gold.values()), 1.0, abs_tol=1e-8)
        ):
            raise ValueError(f"Row {index} has invalid or empty gold mass")
        if not token_diagnostics(tokenizer, row, max_len, head_max_len)["fits"]:
            raise ValueError(f"Row {index} loses option/instruction/context tokens")
    items, skipped = items_from_rows(
        tokenizer, rows, max_len, head_max_len, label_smoothing=0.0
    )
    if skipped or len(items) != len(rows):
        raise ValueError(
            f"Upstream preprocessing dropped labelled questions: {skipped}"
        )
    return items


def validate_prepared_chunks(
    record: dict,
    direction: str,
    chunks: list[dict],
    *,
    tokenizer: Any,
    max_options: int = 20,
    max_len: int = 1024,
    head_max_len: int = 256,
) -> None:
    """Validate cached forward partitions against the complete current job.

    Token diagnostics stored in a cache are never trusted. The inference loop
    checks the actual encoded input again before every model call.
    """
    if direction != "forward":
        raise ValueError("Prepared chunks are supported only for forward jobs")
    ids = _validate_record(record, direction)
    if max_options < 1 or head_max_len < 32 or max_len <= head_max_len:
        raise ValueError("Invalid decision token/option budgets")
    if (
        not isinstance(chunks, list)
        or not chunks
        or any(
            not isinstance(chunk, dict)
            or not isinstance(chunk.get("candidates"), list)
            or any(not isinstance(c, dict) for c in chunk["candidates"])
            for chunk in chunks
        )
    ):
        raise ValueError("Invalid prepared chunk cache")
    if [c.get("id") for chunk in chunks for c in chunk["candidates"]] != ids:
        raise ValueError("Prepared chunk cache lost or reordered candidate identities")
    original = {candidate["id"]: candidate for candidate in record["candidates"]}
    full_positive = record.get(
        "remaining_full_positive_ids",
        set(record.get("full_positive_ids", record.get("positive_ids", [])))
        - set(record.get("removed_ids", [])),
    )
    for index, chunk in enumerate(chunks):
        candidates = chunk["candidates"]
        if len(candidates) > max_options or (not candidates and ids):
            raise ValueError("Prepared chunk cache violates option coverage/budget")
        if not ids and len(chunks) != 1:
            raise ValueError("Empty job requires exactly one prepared STOP chunk")
        expected = _chunk(record, [original[c["id"]] for c in candidates])
        if chunk.get("context_shortening") != expected.get("context_shortening"):
            # Only the existing singleton context policy may change evidence.
            if len(candidates) != 1:
                raise ValueError("Prepared chunk cache changed original evidence")
            for limit in (128, 64, 32, 16, 8, 0):
                shortened = _shorten_contexts(expected, tokenizer, limit)
                if all(
                    chunk.get(field) == shortened.get(field)
                    for field in ("entity", "candidates", "context_shortening")
                ):
                    expected = shortened
                    break
            else:
                raise ValueError("Prepared chunk cache has invalid context shortening")
        expected.update(
            chunk_index=index,
            chunk_count=len(chunks),
            original_candidate_ids=ids,
            original_positive_ids=record.get("positive_ids"),
            retrieval_missing_positive_ids=sorted(set(full_positive) - set(ids)),
        )
        # Bind provenance, labels and all evidence, not just displayed names.
        if {k: v for k, v in chunk.items() if k != "token_diagnostics"} != {
            k: v for k, v in expected.items() if k != "token_diagnostics"
        }:
            raise ValueError("Prepared chunk cache does not match current job/evidence")
        _validate_record(chunk, direction)


def choose_remaining(
    agent: Any,
    record: dict,
    direction: str,
    *,
    max_options: int = 20,
    max_len: int = 1024,
    head_max_len: int = 256,
    prepared_chunks: list[dict] | None = None,
) -> list[dict]:
    """Rescore after each removal; a STOP ends its chunk and all chunks run."""
    if prepared_chunks is None:
        chunks = partition_record(
            record,
            direction,
            tokenizer=agent.tok,
            max_len=max_len,
            head_max_len=head_max_len,
            max_options=max_options,
        )
    else:
        validate_prepared_chunks(
            record,
            direction,
            prepared_chunks,
            tokenizer=agent.tok,
            max_options=max_options,
            max_len=max_len,
            head_max_len=head_max_len,
        )
        chunks = prepared_chunks
    traces = []
    total = len(record["candidates"])
    presented = set()
    for chunk in chunks:
        current = chunk
        while True:
            row = make_question(current, direction)
            diag = token_diagnostics(agent.tok, row, max_len, head_max_len)
            if not diag["fits"]:
                raise ValueError("Removal decision would silently truncate input")
            remaining = [candidate["id"] for candidate in current["candidates"]]
            presented.update(remaining)
            # Gold and metadata are never arguments to the inference runtime.
            result = agent.system_one(
                row["state"],
                row["questions"],
                max_len=max_len,
                head_max_len=head_max_len,
            )
            answer = result["answers"]["match"]
            key = answer["choice"]
            probabilities = answer["probabilities"]
            option_ids = row["metadata"]["option_ids"]
            if (
                key not in option_ids
                or set(probabilities) != set(option_ids)
                or any(
                    not math.isfinite(float(p)) or not 0 <= float(p) <= 1
                    for p in probabilities.values()
                )
                or sum(probabilities.values()) <= 0
            ):
                raise ValueError("Invalid runtime choice/probabilities")
            usage = result.get("usage", {})
            if usage.get("truncated") or usage.get("options"):
                raise ValueError(
                    "Runtime reports truncated context or collapsed options"
                )
            identity = option_ids[key]
            traces.append(
                {
                    "record_id": record.get("id"),
                    "direction": direction,
                    "candidate_id": identity,
                    "choice": key,
                    "stop": key == STOP_KEY,
                    "chunk_index": chunk["chunk_index"],
                    "chunk_count": len(chunks),
                    "remaining_ids": remaining,
                    "option_ids": option_ids,
                    "probabilities": probabilities,
                    "usage": usage,
                    "token_diagnostics": diag,
                    "context_shortening": chunk.get("context_shortening", []),
                    "coverage": {
                        "original_candidate_count": total,
                        "presented_candidate_count": len(presented),
                        "retrieval_missing_positive_ids": chunk[
                            "retrieval_missing_positive_ids"
                        ],
                        "inventory_coverage": "retained_pool_only",
                    },
                }
            )
            if key == STOP_KEY:
                break
            current = _chunk(
                current,
                [
                    candidate
                    for candidate in current["candidates"]
                    if candidate["id"] != identity
                ],
            )
    return traces
