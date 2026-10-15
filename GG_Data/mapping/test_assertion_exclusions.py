"""Run: Agent/.venv/Scripts/python.exe GG_Data/mapping/test_assertion_exclusions.py"""

import csv
import io
import json
import runpy
import unittest
from collections import Counter
from pathlib import Path
from typing import Any

from assertion_exclusions import exclusion_reason, load_exclusions

HERE = Path(__file__).resolve().parent


class ExclusionChecks(unittest.TestCase):
    def test_exact_records_only_and_changed_content_stops(self) -> None:
        rules = load_exclusions()
        self.assertEqual(len(rules), 3)
        for rule in rules.values():
            record = {
                "source_record_id": rule["source_record_id"],
                "predicate": rule["source_predicate"],
                "subject_qid": rule["subject_qid"],
                "object_qid": rule["object_qid"],
            }
            self.assertTrue(exclusion_reason(rule["source"], record, rules))
            self.assertIsNone(exclusion_reason("Wikidata", record, rules))
            changed_id = dict(record, source_record_id="unreviewed-record")
            self.assertIsNone(exclusion_reason(rule["source"], changed_id, rules))
            with self.assertRaisesRegex(ValueError, "changed"):
                exclusion_reason(rule["source"], dict(record, object_qid="Q1"), rules)

    def test_notebook_shared_mapping_gate_prevents_output(self) -> None:
        notebook = json.loads(
            (HERE / "RELATION_MAPPING_ALL_ITEMS_v1.0.0.ipynb").read_text(
                encoding="utf-8"
            )
        )
        source = next(
            "".join(c["source"])
            for c in notebook["cells"]
            if "def map_relation(" in "".join(c.get("source", []))
        )
        namespace = {
            "ROOT": HERE.parents[1],
            "Path": Path,
            "runpy": runpy,
            "Counter": Counter,
            "Any": Any,
            "csv": csv,
            "Iterable": __import__("typing").Iterable,
            "Iterator": __import__("typing").Iterator,
            "re": __import__("re"),
            "SAMPLE_LIMIT": None,
            "SAMPLE_MODE": False,
        }
        exec(compile(source, "mapping_notebook_cell", "exec"), namespace)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=namespace["OUTPUT_COLUMNS"])
        records = [
            {
                "source_record_id": r["source_record_id"],
                "predicate": r["source_predicate"],
                "subject_qid": r["subject_qid"],
                "object_qid": r["object_qid"],
            }
            for r in load_exclusions().values()
        ]
        namespace["write_source"](writer, "EventKG", iter(records))
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(namespace["stats"]["EventKG.excluded_reviewed_input"], 3)
        self.assertNotIn("EventKG.written", namespace["stats"])


if __name__ == "__main__":
    unittest.main()
