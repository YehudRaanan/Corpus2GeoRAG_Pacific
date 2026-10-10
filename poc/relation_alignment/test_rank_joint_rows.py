"""Small check for empirical relation-type ranking."""

import unittest

from poc.relation_alignment.run_two_source_audit import rank_joint_rows


class RankJointRowsTest(unittest.TestCase):
    def test_direction_and_shared_pair_denominators(self) -> None:
        rows = [
            {
                "war_subject_qid": "Q1", "war_object_qid": "Q2", "war_predicate": "W1",
                "wd_subject_qid": "Q1", "wd_object_qid": "Q2", "wd_property": "P1", "direction": "same",
            },
            {
                "war_subject_qid": "Q1", "war_object_qid": "Q2", "war_predicate": "W1",
                "wd_subject_qid": "Q2", "wd_object_qid": "Q1", "wd_property": "P2", "direction": "reverse",
            },
            {
                "war_subject_qid": "Q3", "war_object_qid": "Q4", "war_predicate": "W2",
                "wd_subject_qid": "Q3", "wd_object_qid": "Q4", "wd_property": "P1", "direction": "same",
            },
        ]
        ranked = {
            (r["war_predicate"], r["wd_property"]): r
            for r in rank_joint_rows(rows + rows[:1])
        }
        self.assertEqual(ranked["W1", "P1"]["shared_pairs"], 1)
        self.assertEqual(ranked["W1", "P1"]["wd_co_connected_pairs"], 2)
        self.assertEqual(ranked["W1", "P1"]["pct_of_wd_co_connected"], 50.0)
        self.assertEqual(ranked["W1", "P2"]["direction"], "reverse")
        self.assertEqual(ranked["W1", "P2"]["pct_of_war_co_connected"], 100.0)


if __name__ == "__main__":
    unittest.main()
