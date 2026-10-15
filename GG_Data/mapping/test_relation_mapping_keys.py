"""Regression checks for the delivered relation mapping source identities.

Run: Agent/.venv/Scripts/python.exe GG_Data/mapping/test_relation_mapping_keys.py
"""

import csv
import unittest
from pathlib import Path

from run_relation_mapping_sanity import original_endpoints

HERE = Path(__file__).resolve().parent


def read_csv(name: str) -> list[dict[str, str]]:
    with (HERE / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class SourcePredicateRegression(unittest.TestCase):
    def test_replay_restores_source_orientation_before_a_new_mapping(self) -> None:
        # v1 normalized Ship --operator--> Navy to Navy --operates--> Ship.
        legacy = {"subject_qid": "Navy", "object_qid": "Ship", "direction": "reverse"}
        source_subject, source_object = original_endpoints(legacy)
        self.assertEqual((source_subject, source_object), ("Ship", "Navy"))
        # v2.1 applies its reverse once to the restored source assertion.
        self.assertEqual((source_object, source_subject), ("Navy", "Ship"))

    def test_original_source_ids_and_metadata_are_preserved(self) -> None:
        original = {
            (row["source"], row["source_predicate"]): row
            for row in read_csv("RELATION_MAPPING_TABLE_v1.0.0.csv")
        }
        additional = {
            (row["source"], row["source_predicate"]): row
            for row in read_csv("ADDITIONAL_RELATION_RULES_2026-10-15.csv")
        }
        self.assertEqual(len(additional), 75)
        self.assertFalse(original.keys() & additional.keys())
        for version in ("2.0.0", "2.1.0"):
            with self.subTest(version=version):
                rows = read_csv(f"RELATION_MAPPING_TABLE_v{version}.csv")
                keys = [(row["source"], row["source_predicate"]) for row in rows]
                self.assertEqual(len(keys), len(set(keys)), "Ambiguous source key")
                self.assertEqual(
                    set(keys),
                    original.keys() | additional.keys(),
                    "Source predicate lost",
                )
                for row in rows:
                    if (row["source"], row["source_predicate"]) in additional:
                        continue
                    prior = original[(row["source"], row["source_predicate"])]
                    for field in (
                        "source_occurrence_count",
                        "time_from_input",
                        "time_to_input",
                        "time_point_input",
                        "time_join_rule",
                        "evidence_requirements",
                        "evidence_policy",
                        "time_conflict_policy",
                    ):
                        self.assertEqual(
                            row[field], prior[field], (row["source_predicate"], field)
                        )

    def test_additional_rules_preserve_exact_codes_or_saved_formal_values(self) -> None:
        rules = read_csv("ADDITIONAL_RELATION_RULES_2026-10-15.csv")
        mapping = {
            (row["source"], row["source_predicate"]): row
            for row in read_csv("RELATION_MAPPING_TABLE_v2.1.0.csv")
        }
        for rule in rules:
            row = mapping[(rule["source"], rule["source_predicate"])]
            for field in (
                "level2_relation_id",
                "direction_to_level2",
                "normalized_relation_id",
            ):
                self.assertEqual(row[field], rule[field])
            if rule["level2_mapping_basis"] == "IDENTICAL_IDENTIFIER":
                self.assertEqual(
                    row["normalized_relation_id"], row["level2_relation_id"]
                )
                self.assertEqual(row["direction_to_level2"], "same")
            else:
                self.assertTrue(rule["statement_ids"])
            self.assertNotEqual(
                rule["assertion_review_status"], "PENDING_SAMPLE_REVIEW"
            )

    def test_unsafe_named_inverses_remain_separate(self) -> None:
        catalog = {
            row["level2_relation_id"]: row
            for row in read_csv("RELATION_DIRECTION_CATALOG_v2.1.0.csv")
        }
        for relation in ("wd:P1343", "wd:P6803"):
            self.assertEqual(
                catalog[relation]["reverse_relation_id"], f"inverse:{relation}"
            )
            self.assertEqual(
                catalog[relation]["reverse_status"],
                "ACTIVE_SYNTHETIC_BLOCKED_FORMAL_REVERSE",
            )
        for relation in ("wd:P1889", "wd:P460", "wd:P2959", "wd:P5278"):
            self.assertEqual(catalog[relation]["reverse_relation_id"], relation)

    def test_warsampo_unit_subschemas_stay_separate(self) -> None:
        rows = {
            row["source_predicate"]: row
            for row in read_csv("RELATION_MAPPING_TABLE_v2.1.0.csv")
            if row["source"] == "WarSampo"
        }
        self.assertEqual(len(rows), 111)
        for scope in ("articles/", "casualties/", "prisoners/", ""):
            uri = f"http://ldf.fi/schema/warsa/{scope}unit"
            self.assertIn(uri, rows)
            self.assertEqual(rows[uri]["normalized_relation_id"], uri)
            self.assertEqual(rows[uri]["level2_relation_id"], uri)

    def test_reverse_lookup_is_complete_and_returns_to_original(self) -> None:
        rows = read_csv("RELATION_DIRECTION_LOOKUP_v2.1.0.csv")
        lookup = {row["input_relation_id"]: row for row in rows}
        self.assertEqual(len(rows), len(lookup))
        for mapping in read_csv("RELATION_MAPPING_TABLE_v2.1.0.csv"):
            forward = mapping["level2_relation_id"]
            reverse = mapping["reverse_relation_id"]
            self.assertEqual(lookup[forward]["output_reverse_relation_id"], reverse)
            self.assertEqual(lookup[reverse]["output_reverse_relation_id"], forward)


if __name__ == "__main__":
    unittest.main()
