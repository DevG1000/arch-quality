# -*- coding: utf-8 -*-
"""化石维度集成/E2E：ComprehensiveReport 合并、归一化、报告章节、封顶。"""

import copy
import os
import tempfile
import unittest

from arch_quality.arch_report import ComprehensiveReport
from arch_quality.arch_report_generator import ReportGenerator


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class TestFossilIntegration(unittest.TestCase):
    def _project(self, d):
        _write(d, "legacy.f",
               "      PROGRAM L\n"
               "      IMPLICIT REAL*8 (A-H,O-Z)\n"
               "      END\n")
        _write(d, "old.cpp",
               "#include <memory>\n"
               "void f(){std::auto_ptr<int> p(new int(1));}\n")

    def test_report_merge_and_normalization(self):
        with tempfile.TemporaryDirectory() as d:
            self._project(d)
            r = ComprehensiveReport(d).generate()

            self.assertIn("fossil", r["dimensions"])
            self.assertIsNotNone(r["dimensions"]["fossil"]["score"])
            self.assertEqual(r["fossil_score_scope"], "project")
            self.assertEqual(set(r["fossil_applicability_set"]),
                             {"legacy", "dead", "clone", "debt"})
            self.assertIn(r["fossil_gate_status"], {"PASS", "WARN", "BLOCK"})
            self.assertIn("fossil_version_info", r)

            weights = r["score_breakdown"]["normalized_weights"]
            self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)
            self.assertIn("dim.fossil", weights)

            fos_rules = [v["rule"] for v in r["mlr_violations"]
                         if str(v.get("rule", "")).startswith("FOS")]
            self.assertTrue(fos_rules)

            md = ReportGenerator(d, r, []).generate()
            self.assertIn("化石代码与技术债增强评估", md)
            self.assertIn("**门禁**", md)
            self.assertIn("**适用集**", md)

    def test_cap_display(self):
        with tempfile.TemporaryDirectory() as d:
            self._project(d)
            r = copy.deepcopy(ComprehensiveReport(d).generate())
            r["fossil_confirmed_max_severity"] = "HIGH"
            r["fossil_gate_status"] = "WARN"
            r["dimensions"]["fossil"]["score"] = 90.0
            r["dimensions"]["structural"]["fossil_enhancement"]["score"] = 90.0
            md = ReportGenerator(d, r, []).generate()
            self.assertIn("受封顶", md)
            self.assertIn("90.0/100", md)

    def test_d3_legacy_untested_excluded_from_test_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "old.cpp",
                   "#include <memory>\n"
                   "void f(){std::auto_ptr<int> p(new int(1));}\n")
            _write(d, "legacy/solver.cpp", "void solve(){}\n")
            _write(d, "modern/mod.cpp", "void mod(){}\n")
            _write(d, "tests/test_mod.py", "def test_mod(): assert True\n")
            r = ComprehensiveReport(d).generate()
            self.assertEqual(r["legacy_untested_modules"], ["legacy"])
            detail = r["dimensions"]["structural"]["sub_scores"]["test_coverage_detail"]
            self.assertIn("legacy", detail["excluded_legacy_modules"])

    def test_d3_all_source_excluded_test_coverage_not_applicable(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "legacy/old.cpp",
                   "#include <memory>\n"
                   "void f(){std::auto_ptr<int> p(new int(1));}\n")
            _write(d, "legacy/solver.cpp", "void solve(){}\n")
            r = ComprehensiveReport(d).generate()
            detail = r["dimensions"]["structural"]["sub_scores"]["test_coverage_detail"]
            self.assertEqual(detail["excluded_legacy_modules"], ["legacy"])
            self.assertIsNone(r["dimensions"]["structural"]["sub_scores"]["test_coverage"])
            self.assertFalse(detail["applicable"])

    def test_root_only_source_is_not_no_source(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "main.cpp", "int main(){return 0;}\n")
            r = ComprehensiveReport(d).generate()
            detail = r["dimensions"]["structural"]["sub_scores"]["test_coverage_detail"]
            self.assertIsNotNone(detail.get("dir_coverage"))
            self.assertNotEqual(detail.get("applicable"), False)

    def test_non_fossil_project(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "main.cpp", "int add(int a,int b){return a+b;}\n")
            r = ComprehensiveReport(d).generate()
            self.assertNotIn("fossil", r["dimensions"])
            self.assertEqual(r["fossil_applicability_set"], [])
            self.assertEqual(r["fossil_gate_status"], "PASS")


if __name__ == "__main__":
    unittest.main()
