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




class TestCrossValidation(unittest.TestCase):
    """GCS k-fold 交叉验证（3-fold LOOCV）。"""

    def test_cross_validate_script_exists(self):
        p = os.path.join(os.path.dirname(__file__), "..", "scripts",
                         "cross_validate_geometry_consistency.py")
        self.assertTrue(os.path.exists(p))

    def test_cross_validate_report_generated(self):
        p = os.path.join(os.path.dirname(__file__), "..", "docs", "zh",
                         "几何内核与科学数据结构一致性评估",
                         "交叉验证报告_geometry_consistency.md")
        self.assertTrue(os.path.exists(p), "交叉验证报告缺失")
        with open(p, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Leave-One-Out (3-fold)", content)
        self.assertIn("gcs_occt", content)
        self.assertIn("gcs_salome_geom", content)
        self.assertIn("gcs_freecad", content)

    def test_cross_validate_baselines_used(self):
        # 3 个基线快照被交叉验证使用
        for name in ["gcs_occt.json", "gcs_salome_geom.json", "gcs_freecad.json"]:
            p = os.path.join(os.path.dirname(__file__), "..", "tests",
                             "regression", "snapshots", name)
            self.assertTrue(os.path.exists(p), f"{name} 缺失")

    def test_cross_validate_run(self):
        # 实际运行脚本（快速，使用缓存基线）
        import subprocess
        script = os.path.join(os.path.dirname(__file__), "..", "scripts",
                              "cross_validate_geometry_consistency.py")
        r = subprocess.run(
            [sys.executable, script], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(r.returncode, 0, f"脚本失败: {r.stderr[:300]}")
        self.assertIn("WARNING", r.stdout)


if __name__ == "__main__":
    unittest.main()
