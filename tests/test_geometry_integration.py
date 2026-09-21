"""
test_geometry_integration.py — GCS 引擎集成 + 端到端测试（B2.5）

覆盖：
1. 权重解析集成 — GCS skill 权重与引擎 all_metrics 使用一致
2. 报告合并集成 — ComprehensiveReport 合并 geometry_consistency_enhancement
3. GCS 违规合并 — gcs_violations 正确追加到 mlr_violations
4. 权重归一化 — 多增强同时激活时 structural 权重和 = 1.0
5. profile 集成 — profile=geometry-consistency 仅运行 standard+gcs
6. E2E — 合成几何项目全链路 + CLI JSON 输出

使用合成项目，不依赖外部仓库。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arch_quality.arch_core import load_weights_from_skill, PROFILE_ENGINE_MAP
from arch_quality.arch_report import ComprehensiveReport
from arch_quality.arch_metrics_geometry_consistency import GeometryConsistencyMetrics

SKILL_GCS = os.path.join(os.path.dirname(__file__), '..', 'src',
                         'arch_quality', 'skills', 'geometry-consistency.md')


def _write_tree(root, files: dict):
    for path, content in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


def _make_good_geometry():
    """好几何项目（4 维均高、无违规）"""
    tmp = tempfile.mkdtemp()
    _write_tree(tmp, {
        "README.md": "# Proj\n",
        "src/ops.cpp": (
            "#include <BRepAlgoAPI_Fuse.hxx>\n"
            "#include <BRepCheck_Analyzer.hxx>\n"
            "#include <stdexcept>\n"
            "TopoDS_Shape fuse(const TopoDS_Shape& a, const TopoDS_Shape& b) {\n"
            "    BRepAlgoAPI_Fuse op(a, b);\n"
            "    if (!op.IsDone()) throw std::runtime_error(\"f\");\n"
            "    BRepCheck_Analyzer an(op.Shape());\n"
            "    if (!an.IsValid()) throw std::runtime_error(\"v\");\n"
            "    return op.Shape();\n"
            "}\n"),
        "src/precision.h": "constexpr double GEOM_TOLERANCE = 1e-6;\n",
    })
    return tmp


def _make_bad_geometry():
    """坏几何项目（触发 GCS-002 裸指针穿越 + GCS-005 精度魔法数字）"""
    tmp = tempfile.mkdtemp()
    _write_tree(tmp, {
        "README.md": "# Proj\n",
        "src/leak.cpp": (
            "#include <Geom_Plane.hxx>\n"
            "Geom_Plane* get_plane() {\n"
            "    return new Geom_Plane(gp_Pln());\n"
            "}\n"),
        "src/units.cpp": "double t = 1e-8;\n",
    })
    return tmp


class TestWeightParsingIntegration(unittest.TestCase):
    """权重解析集成"""

    def test_gcs_skill_weights_match_engine(self):
        tmp = _make_good_geometry()
        try:
            skill_w = load_weights_from_skill(SKILL_GCS)
            m = GeometryConsistencyMetrics(tmp)
            for dim, w in m.weights.items():
                self.assertIn(dim, skill_w)
                self.assertAlmostEqual(w, skill_w[dim])
            self.assertAlmostEqual(sum(m.weights.values()), 1.0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestReportMergeIntegration(unittest.TestCase):
    """报告合并集成"""

    def test_gcs_enhancement_merged(self):
        tmp = _make_good_geometry()
        try:
            data = ComprehensiveReport(tmp).generate()
            s = data["dimensions"]["structural"]
            self.assertIn("geometry_consistency_enhancement", s)
            gcs = s["geometry_consistency_enhancement"]
            self.assertIsInstance(gcs["score"], (int, float))
            self.assertIn("weight_applied", gcs)
            self.assertIn("details", gcs)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_gcs_violations_merged(self):
        tmp = _make_bad_geometry()
        try:
            data = ComprehensiveReport(tmp).generate()
            gcs_rules = [v["rule"] for v in data["mlr_violations"]
                         if v["rule"].startswith("GCS")]
            self.assertIn("GCS-002", gcs_rules)
            self.assertIn("GCS-005", gcs_rules)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_structural_weights_normalize_to_100(self):
        """好几何项目确定性触发 3 增强（template/numerical/gcs）→ base 0.60 + 0.15/0.10/0.15 = 1.0"""
        tmp = _make_good_geometry()
        try:
            data = ComprehensiveReport(tmp).generate()
            s = data["dimensions"]["structural"]
            ml_w = s.get("multilang_enhancement", {}).get("weight_applied", 0)
            tpl_w = s.get("template_enhancement", {}).get("weight_applied", 0)
            nvr_w = s.get("numerical_enhancement", {}).get("weight_applied", 0)
            sp_w = s.get("solver_physics_enhancement", {}).get("weight_applied", 0)
            gcs_w = s.get("geometry_consistency_enhancement", {}).get("weight_applied", 0)
            base_w = 1 - (ml_w + tpl_w + nvr_w + sp_w + gcs_w)
            # 精确值断言（防归一化公式回归）：4 增强（ml/tpl/nvr/gcs）→ base 0.50, 0.1364×3, 0.0909
            self.assertAlmostEqual(base_w, 0.50, places=4)
            self.assertAlmostEqual(ml_w, 0.1364, places=4)
            self.assertAlmostEqual(tpl_w, 0.1364, places=4)
            self.assertAlmostEqual(nvr_w, 0.0909, places=4)
            self.assertAlmostEqual(gcs_w, 0.1364, places=4)
            self.assertEqual(sp_w, 0.0)
            # 总和恒为 1
            self.assertAlmostEqual(base_w + ml_w + tpl_w + nvr_w + sp_w + gcs_w, 1.0, places=4)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_profile_schema_includes_gcs(self):
        self.assertIn("geometry-consistency", PROFILE_ENGINE_MAP)
        self.assertEqual(PROFILE_ENGINE_MAP["geometry-consistency"],
                         ["standard", "geometry-consistency"])


class TestProfileIntegration(unittest.TestCase):
    """profile 集成"""

    def test_geometry_profile_runs_only_gcs(self):
        tmp = _make_good_geometry()
        try:
            data = ComprehensiveReport(tmp, profile={
                "enabled_engines": ["standard", "geometry-consistency"],
                "profile": "geometry-consistency"}).generate()
            self.assertTrue(data["profile"]["active"])
            self.assertEqual(data["profile"]["enabled_engines"],
                             ["geometry-consistency", "standard"])
            s = data["dimensions"]["structural"]
            self.assertIn("geometry_consistency_enhancement", s)
            self.assertNotIn("template_enhancement", s)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestE2E(unittest.TestCase):
    """端到端"""

    def test_non_geometry_project_downgrade(self):
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {"src/main.py": "def main():\n    print(1)\n"})
            data = ComprehensiveReport(tmp).generate()
            self.assertNotIn("geometry_consistency_enhancement",
                             data["dimensions"]["structural"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_cli_json_output(self):
        tmp = _make_good_geometry()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "arch_quality", tmp, "--json",
                 "--profile", "geometry-consistency"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=os.path.join(os.path.dirname(__file__), '..'),
                timeout=120,
            )
            out = result.stdout
            json_start = out.find("{")
            self.assertNotEqual(json_start, -1)
            data = json.loads(out[json_start:out.rfind("}") + 1])
            self.assertIn("overall_score", data)
            self.assertTrue(data["profile"]["active"])
            self.assertIn("geometry_consistency_enhancement",
                          data["dimensions"]["structural"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_empty_project_downgrade(self):
        """空项目（无源码）→ 非几何，无 enhancement"""
        tmp = tempfile.mkdtemp()
        try:
            data = ComprehensiveReport(tmp).generate()
            self.assertNotIn("geometry_consistency_enhancement",
                             data["dimensions"]["structural"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_keyword_in_comment_not_geometry(self):
        """边界误报：注释提及 vtk/Handle 但无实际几何信号 → 不触发（引擎已剥离注释）"""
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {"src/util.cpp": (
                "// 本项目不使用 vtkUnstructuredGrid 或 Handle_，仅为字符串工具库\n"
                "// TODO: 未来可能接入 gmsh 网格\n"
                "#include <string>\n"
                "std::string upper(std::string s) { return s; }\n")})
            data = ComprehensiveReport(tmp).generate()
            self.assertNotIn("geometry_consistency_enhancement",
                             data["dimensions"]["structural"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_all_metrics_field_types(self):
        """字段类型断言：overall 数值且 0-100，各维 score int/float 或 None"""
        tmp = _make_good_geometry()
        try:
            m = GeometryConsistencyMetrics(tmp)
            r = m.all_metrics()
            # 顶层字段类型
            self.assertTrue(r["is_geometry"])
            self.assertIsInstance(r["overall"], (int, float))
            self.assertTrue(0 <= r["overall"] <= 100)
            # 各维 score 类型与范围
            for dim, info in r["dimensions"].items():
                s = info["score"]
                if s is not None:
                    self.assertIsInstance(s, (int, float))
                    self.assertTrue(0 <= s <= 100)
                self.assertIsInstance(info["detail"], dict)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_gcs_violation_field_types(self):
        """gcs_violations 结构断言：rule/name/severity/output_level/count/detail 字段类型"""
        tmp = _make_bad_geometry()
        try:
            m = GeometryConsistencyMetrics(tmp)
            r = m.all_metrics()
            self.assertTrue(r["gcs_violations"])
            for v in r["gcs_violations"]:
                self.assertIsInstance(v["rule"], str)
                self.assertIn(v["severity"], ("HIGH", "MEDIUM", "LOW"))
                self.assertIn(v["output_level"], ("ERROR", "WARNING", "INFO"))
                self.assertIsInstance(v["count"], int)
                self.assertIsInstance(v["detail"], str)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()