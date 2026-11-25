"""H3 WP-8 F4: ACL Agent Harness offline validation."""

import json
import os
import sys
import unittest

HARNESS = os.path.join(os.path.dirname(__file__), "..", "opencode-harness")
PROJ = os.path.join(os.path.dirname(__file__), "..", "tests", "mutation", "projects")
sys.path.insert(0, HARNESS)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def load_case(cid: str) -> dict:
    with open(os.path.join(HARNESS, "cases", cid + ".json"), encoding="utf-8") as f:
        return json.load(f)


class TestACLCases(unittest.TestCase):
    def test_case_files_exist_and_valid(self):
        for cid in ["case-13-acl-good", "case-14-acl-flawed", "case-15-acl-non"]:
            c = load_case(cid)
            for k in ["id", "name", "description", "project_dir", "prompt", "expect"]:
                self.assertIn(k, c, f"{cid} missing {k}")
            self.assertEqual(c["id"], cid)

    def test_case_project_dirs_exist(self):
        for cid in ["case-13-acl-good", "case-14-acl-flawed", "case-15-acl-non"]:
            self.assertTrue(os.path.isdir(load_case(cid)["project_dir"]))

    def test_acl_expect_fields(self):
        good = load_case("case-13-acl-good")
        self.assertTrue(good["expect"]["is_acl"])
        self.assertEqual(len(good["expect"]["dimension_fields"]), 4)
        bad = load_case("case-14-acl-flawed")
        self.assertEqual(bad["expect"]["overall_range"], [0, 50])
        non = load_case("case-15-acl-non")
        self.assertFalse(non["expect"]["is_acl"])
        self.assertIsNone(non["expect"]["overall_range"])


class TestACLRules(unittest.TestCase):
    def test_rules_has_acl_fields(self):
        rules = json.load(open(os.path.join(HARNESS, "rules.json"), encoding="utf-8"))
        self.assertEqual(len(rules.get("acl_dimension_fields", [])), 4)
        self.assertIn("external_access", rules["acl_dimension_fields"])
        self.assertIn("python -m arch_quality.arch_metrics_anti_corruption",
                      rules.get("single_engine_prefixes", []))

    def test_python_defaults_synced(self):
        from assertors._rules import load_rules
        r = load_rules()
        self.assertEqual(len(r.get("acl_dimension_fields", [])), 4)
        self.assertIn("python -m arch_quality.arch_metrics_anti_corruption",
                      r.get("single_engine_prefixes", []))


class TestACLSyntheticProjects(unittest.TestCase):
    def test_bad_project_triggers_acl(self):
        from arch_quality.arch_metrics_anti_corruption import AntiCorruptionMetrics
        m = AntiCorruptionMetrics(os.path.join(PROJ, "bad_project_acl"))
        r = m.all_metrics()
        self.assertTrue(r["is_acl"])
        self.assertLess(r["overall"], 50)
        rules = {v["rule"] for v in r.get("acl_violations", [])}
        self.assertIn("ACL-001", rules)

    def test_good_project_healthy(self):
        from arch_quality.arch_metrics_anti_corruption import AntiCorruptionMetrics
        m = AntiCorruptionMetrics(os.path.join(PROJ, "good_project_acl"))
        r = m.all_metrics()
        self.assertTrue(r["is_acl"])
        self.assertGreaterEqual(r["overall"], 80)

    def test_non_acl_project(self):
        from arch_quality.arch_metrics_anti_corruption import AntiCorruptionMetrics
        m = AntiCorruptionMetrics(os.path.join(PROJ, "good_project_standard"))
        r = m.all_metrics()
        self.assertFalse(r["is_acl"])


class TestACLAssertionFlow(unittest.TestCase):
    def _assert_case(self, cid: str, text: str):
        from assertors import output_schema
        c = load_case(cid)
        errs = output_schema.assert_all(text, c["expect"])
        self.assertEqual(errs, [], f"{cid} 断言失败: {errs}")

    def test_good_report_passes(self):
        self._assert_case("case-13-acl-good",
            "评估完成：overall: 92.5, is_acl: True, "
            "external_access=100 wrapper_coverage=100 data_exchange=100 fidelity=100")

    def test_bad_report_passes(self):
        self._assert_case("case-14-acl-flawed",
            "评估完成：overall: 14.0, is_acl: True, "
            "external_access=0 wrapper_coverage=40 data_exchange=0 fidelity=20, "
            "ACL 违规: ACL-001 ACL-002 ACL-007")

    def test_non_acl_report_passes(self):
        self._assert_case("case-15-acl-non",
            "评估完成：is_acl: False，无外部内核信号，非 ACL 项目")

    def test_good_report_missing_fields_fails(self):
        from assertors import output_schema
        c = load_case("case-13-acl-good")
        errs = output_schema.assert_all("overall: 92.5, is_acl: True", c["expect"])
        self.assertTrue(errs)


if __name__ == "__main__":
    unittest.main()
