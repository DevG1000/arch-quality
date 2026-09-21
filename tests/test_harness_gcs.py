"""
test_harness_gcs.py — H2 WP-2 B2.6 Agent Harness 交付物验证

覆盖：
1. GCS 3 个 case 文件（case-4/5/6）格式完整、project_dir 存在
2. rules.json 含 gcs_dimension_fields / single_engine_prefixes（v1.1）
3. 断言器对 GCS 汇报文本的正确判定（good/bad/非几何）
4. bad_project_gcs 合成项目触发 GCS-001/002 违规（引擎实测）
"""

import json
import os
import sys
import unittest

HARNESS = os.path.join(os.path.dirname(__file__), "..", "opencode-harness")
PROJ = os.path.join(os.path.dirname(__file__), "..", "tests", "mutation", "projects")
sys.path.insert(0, HARNESS)


def load_case(cid: str) -> dict:
    p = os.path.join(HARNESS, "cases", cid + ".json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class TestGCSCases(unittest.TestCase):
    """3 个 GCS case 文件格式与路径有效性。"""

    def test_case_files_exist_and_valid(self):
        for cid in ["case-4-gcs-good", "case-5-gcs-flawed", "case-6-gcs-non-geometry"]:
            c = load_case(cid)
            for k in ["id", "name", "description", "project_dir", "prompt", "expect"]:
                self.assertIn(k, c, f"{cid} 缺 {k}")
            self.assertEqual(c["id"], cid)

    def test_case_project_dirs_exist(self):
        for cid in ["case-4-gcs-good", "case-5-gcs-flawed"]:
            c = load_case(cid)
            self.assertTrue(os.path.isdir(c["project_dir"]), c["project_dir"])
        c6 = load_case("case-6-gcs-non-geometry")
        self.assertTrue(os.path.isdir(c6["project_dir"]))

    def test_gcs_expect_fields(self):
        c4 = load_case("case-4-gcs-good")
        self.assertTrue(c4["expect"]["is_geometry"])
        self.assertEqual(c4["expect"]["overall_range"], [80, 100])
        self.assertEqual(len(c4["expect"]["dimension_fields"]), 4)
        c6 = load_case("case-6-gcs-non-geometry")
        self.assertFalse(c6["expect"]["is_geometry"])
        self.assertIsNone(c6["expect"]["overall_range"])


class TestRulesUpdate(unittest.TestCase):
    """rules.json v1.1 更新。"""

    def test_rules_has_gcs_fields(self):
        rules = json.load(open(os.path.join(HARNESS, "rules.json"), encoding="utf-8"))
        self.assertEqual(rules["version"], "1.1")
        self.assertEqual(len(rules.get("gcs_dimension_fields", [])), 4)
        self.assertIn("geometry_kernel_consistency", rules["gcs_dimension_fields"])
        self.assertGreaterEqual(len(rules.get("single_engine_prefixes", [])), 6)

    def test_python_defaults_synced(self):
        from assertors._rules import load_rules
        r = load_rules()
        self.assertEqual(len(r.get("gcs_dimension_fields", [])), 4)
        self.assertIn("python -m arch_quality.arch_metrics_geometry_consistency",
                      r.get("single_engine_prefixes", []))


class TestGCSSyntheticProject(unittest.TestCase):
    """bad_project_gcs 触发 GCS 违规（引擎实测）。"""

    def test_bad_project_triggers_violations(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from arch_quality.arch_metrics_geometry_consistency import GeometryConsistencyMetrics
        m = GeometryConsistencyMetrics(os.path.join(PROJ, "bad_project_gcs"))
        r = m.all_metrics()
        rules = {v["rule"] for v in r.get("gcs_violations", [])}
        self.assertIn("GCS-001", rules)
        self.assertIn("GCS-002", rules)
        self.assertLess(r["overall"], 90)

    def test_good_project_clean(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from arch_quality.arch_metrics_geometry_consistency import GeometryConsistencyMetrics
        m = GeometryConsistencyMetrics(os.path.join(PROJ, "good_project_gcs"))
        r = m.all_metrics()
        self.assertEqual(r["overall"], 100.0)
        self.assertEqual(len(r.get("gcs_violations", [])), 0)


class TestGCSAssertionFlow(unittest.TestCase):
    """断言器对 GCS 汇报文本的正确判定（模拟 agent 输出）。"""

    def _assert_case(self, cid: str, text: str):
        from assertors import output_schema
        c = load_case(cid)
        errs = output_schema.assert_all(text, c["expect"])
        self.assertEqual(errs, [], f"{cid} 断言失败: {errs}")

    def test_good_report_passes(self):
        self._assert_case("case-4-gcs-good",
            "评估完成：overall: 100.0, is_geometry: True, "
            "geometry_kernel_consistency=100 precision_unit_consistency=100 "
            "scidata_organization=100 data_access_norm=100, GCS 违规 0")

    def test_bad_report_passes(self):
        self._assert_case("case-5-gcs-flawed",
            "评估完成：overall: 71.0, is_geometry: True, "
            "geometry_kernel_consistency=45 precision_unit_consistency=100 "
            "scidata_organization=100 data_access_norm=50, "
            "GCS 违规: GCS-001(LOW) GCS-002(MEDIUM)")

    def test_non_geometry_report_passes(self):
        self._assert_case("case-6-gcs-non-geometry",
            "评估完成：is_geometry: False，该目录为纯 Markdown 知识库，无几何内核特征，不适用")

    def test_good_report_missing_fields_fails(self):
        from assertors import output_schema
        c = load_case("case-4-gcs-good")
        errs = output_schema.assert_all("评估完成：overall 90", c["expect"])
        self.assertNotEqual(errs, [])


if __name__ == "__main__":
    unittest.main()
