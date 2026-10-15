"""Apply approved, record-specific exclusions before relation mapping/reverse views.

Raw records and historical EDA remain intact. A changed source statement fails
the content guard so an old decision cannot silently suppress corrected data.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping

HERE = Path(__file__).resolve().parent
Exclusions = dict[tuple[str, str], dict[str, str]]


def load_exclusions(path: Path = HERE / "ASSERTION_EXCLUSIONS.csv") -> Exclusions:
    exclusions: Exclusions = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row["source"], row["source_record_id"])
            required = (
                "source",
                "source_record_id",
                "source_predicate",
                "subject_qid",
                "object_qid",
                "reason",
                "evidence_file",
                "approved_date",
            )
            if (
                any(not row[field] for field in required)
                or row["decision"] != "EXCLUDE"
            ):
                raise ValueError(f"Incomplete or unsupported exclusion: {key}")
            if key in exclusions:
                raise ValueError(f"Duplicate assertion exclusion: {key}")
            exclusions[key] = row
    return exclusions


def exclusion_reason(
    source: str, record: Mapping[str, object], exclusions: Exclusions
) -> str | None:
    """Accept source-oriented reader records, before any endpoint translation."""
    rule = exclusions.get((source, str(record["source_record_id"])))
    if rule is None:
        return None
    expected = (rule["source_predicate"], rule["subject_qid"], rule["object_qid"])
    actual = (record["predicate"], record["subject_qid"], record["object_qid"])
    if actual != expected:
        raise ValueError(
            f"Excluded source record changed; review required: {rule['source_record_id']}"
        )
    return rule["reason"]
