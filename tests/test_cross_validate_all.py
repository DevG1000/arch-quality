"""H3 WP-8 F3: unified cross-validation aggregation tests."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import cross_validate_all


class TestNormalize(unittest.TestCase):
    def test_summary_schema(self):
        r = cross_validate_all.normalize("x", {
            "summary": {"total_folds": 9, "in_range_count": 7,
                        "generalization_verdict": "PASS"}})
        self.assertEqual(r["fold_count"], 9)
        self.assertEqual(r["passed"], 7)
        self.assertTrue(r["nine_fold"])
        self.assertEqual(r["status"], "PASS")

    def test_five_fold_is_partial(self):
        r = cross_validate_all.normalize("x", {
            "summary": {"total_folds": 5, "in_range_count": 4,
                        "generalization_verdict": "WARNING"}})
        self.assertFalse(r["nine_fold"])
        self.assertEqual(r["status"], "PARTIAL")

    def test_hpc_schema(self):
        r = cross_validate_all.normalize("hpc", {
            "result": {"n": 9, "passed": 8, "rate": 0.8889, "ok": True}})
        self.assertEqual(r["status"], "PASS")


class TestAggregate(unittest.TestCase):
    def test_current_summary(self):
        s = cross_validate_all.build_summary()
        self.assertEqual(s["summary"]["engines_with_data"], 7)
        self.assertEqual(s["summary"]["nine_fold_pass_count"], 7)
        self.assertNotIn("standard", s["pending_engines"])
        self.assertNotIn("multilang", s["pending_engines"])
        self.assertEqual(s["pending_engines"], [])
        self.assertEqual(s["engines"]["numerical"]["status"], "PASS")
        self.assertEqual(s["engines"]["standard"]["status"], "PASS")
        self.assertEqual(s["engines"]["multilang"]["status"], "PASS")

    def test_markdown_contains_table(self):
        md = cross_validate_all.render_md(cross_validate_all.build_summary())
        self.assertIn("全维 LOOCV", md)
        self.assertIn("| 引擎 |", md)


if __name__ == "__main__":
    unittest.main()
