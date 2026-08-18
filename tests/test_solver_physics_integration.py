"""
test_solver_physics_integration.py — SolverPhysicsMetrics 集成测试

验证组件间交互：
1. 权重解析集成 — load_weights_from_skill() 与 all_metrics() 的权重一致性
2. 报告合并集成 — ComprehensiveReport 正确合并 solver_physics 评分
3. MPR 合并集成 — MPR 规则正确追加到 mlr_violations
4. 权重归一化 — 多增强同时激活时权重和 = 100%

使用合成项目，不依赖外部仓库。
"""

import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arch_quality.arch_core import load_weights_from_skill
from arch_quality.arch_report import ComprehensiveReport
from arch_quality.arch_metrics_solver_physics import SolverPhysicsMetrics

SKILL_SP = os.path.join(os.path.dirname(__file__), '..', 'src',
                        'arch_quality', 'skills',
                        'solver-physics-architecture.md')


def _write_tree(root, files: dict):
    for path, content in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


def _make_multiphysics_project():
    """创建多物理场合成项目"""
    tmp = tempfile.mkdtemp()
    _write_tree(tmp, {
        "CMakeLists.txt": "add_subdirectory(src/structural)\n"
                          "add_subdirectory(src/thermal)\n",
        "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
        "src/structural/Solver.cpp": "void solve() {}\n",
        "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
        "src/thermal/Solver.cpp": "void solve() {}\n",
        "tests/structural_mms.cpp": "// MMS verification\n",
        "tests/thermal_mms.cpp": "// MMS verification\n",
        "coupling/CouplingLayer.cpp": "class Field { double* data; };\n"
                                      "void exchangeField() {}\n",
        "plugin/Registry.cpp": "void registerPlugin() {}\n"
                               "class MyModule : public Module { };\n",
    })
    return tmp


class TestWeightParsingIntegration(unittest.TestCase):
    """权重解析集成"""

    def test_skill_weights_parsed(self):
        weights = load_weights_from_skill(SKILL_SP)
        self.assertIn("物理场模块边界完整性", weights)
        self.assertIn("多物理场耦合架构合理性", weights)
        self.assertIn("插件式扩展架构支持度", weights)
        self.assertIn("跨场数据传递规范性", weights)

    def test_metrics_uses_skill_weights(self):
        tmp = _make_multiphysics_project()
        try:
            m = SolverPhysicsMetrics(tmp)
            skill_weights = load_weights_from_skill(SKILL_SP)
            for dim_key, metric_weight in m.weights.items():
                self.assertIn(dim_key, skill_weights)
                self.assertAlmostEqual(metric_weight, skill_weights[dim_key])
        finally:
            shutil.rmtree(tmp)

    def test_weights_sum_to_one(self):
        tmp = _make_multiphysics_project()
        try:
            m = SolverPhysicsMetrics(tmp)
            total = sum(m.weights.values())
            self.assertAlmostEqual(total, 1.0, places=4)
        finally:
            shutil.rmtree(tmp)


class TestReportMergeIntegration(unittest.TestCase):
    """ComprehensiveReport 报告合并集成"""

    def test_solver_physics_enhancement_merged(self):
        tmp = _make_multiphysics_project()
        try:
            report = ComprehensiveReport(tmp)
            data = report.generate()
            structural = data["dimensions"]["structural"]
            self.assertIn("solver_physics_enhancement", structural)
            sp_enh = structural["solver_physics_enhancement"]
            self.assertIn("score", sp_enh)
            self.assertIn("weight_applied", sp_enh)
            self.assertIn("details", sp_enh)
        finally:
            shutil.rmtree(tmp)

    def test_structural_score_calculated(self):
        tmp = _make_multiphysics_project()
        try:
            report = ComprehensiveReport(tmp)
            data = report.generate()
            structural = data["dimensions"]["structural"]
            self.assertGreater(structural["score"], 0)
            self.assertLessEqual(structural["score"], 100)
        finally:
            shutil.rmtree(tmp)

    def test_overall_score_present(self):
        tmp = _make_multiphysics_project()
        try:
            report = ComprehensiveReport(tmp)
            data = report.generate()
            self.assertIn("overall_score", data)
            self.assertGreater(data["overall_score"], 0)
        finally:
            shutil.rmtree(tmp)


class TestMPRMergeIntegration(unittest.TestCase):
    """MPR 规则合并集成"""

    def test_mpr_merged_into_mlr_violations(self):
        # 构造一个会触发 MPR 的项目（无 MMS、无 Field 结构）
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "CMakeLists.txt": "add_subdirectory(src/structural)\n"
                                  "add_subdirectory(src/thermal)\n",
                "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
                "src/structural/Solver.cpp": "void solve() {}\n",
                "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
                "src/thermal/Solver.cpp": "void solve() {}\n",
            })
            report = ComprehensiveReport(tmp)
            data = report.generate()
            mpr_rules = [v for v in data["mlr_violations"]
                         if v.get("rule", "").startswith("MPR-")]
            # 无 MMS 应触发 MPR-003
            self.assertTrue(any(v["rule"] == "MPR-003" for v in mpr_rules))
        finally:
            shutil.rmtree(tmp)

    def test_mpr_violation_structure(self):
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "CMakeLists.txt": "add_subdirectory(src/structural)\n"
                                  "add_subdirectory(src/thermal)\n",
                "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
                "src/structural/Solver.cpp": "void solve() {}\n",
                "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
                "src/thermal/Solver.cpp": "void solve() {}\n",
            })
            report = ComprehensiveReport(tmp)
            data = report.generate()
            mpr_rules = [v for v in data["mlr_violations"]
                         if v.get("rule", "").startswith("MPR-")]
            for v in mpr_rules:
                self.assertIn("rule", v)
                self.assertIn("severity", v)
                self.assertIn("output_level", v)
                self.assertIn("detail", v)
        finally:
            shutil.rmtree(tmp)


class TestWeightNormalizationIntegration(unittest.TestCase):
    """多增强同时激活时的权重归一化（精确值断言，防弱断言掩盖合并错误）"""

    def test_solver_physics_alone_precise_value(self):
        """仅多物理场增强激活 → sp_w 精确等于 0.15，base 0.85"""
        tmp = _make_multiphysics_project()
        try:
            report = ComprehensiveReport(tmp)
            data = report.generate()
            structural = data["dimensions"]["structural"]
            sp_w = structural.get("solver_physics_enhancement", {}).get("weight_applied", 0)
            # 精确值断言：单独激活时权重未归一化，sp 应为 0.15
            self.assertAlmostEqual(sp_w, 0.15, places=4)
            # base = 1 - sp
            base_w = 1 - sp_w
            self.assertAlmostEqual(base_w, 0.85, places=4)
        finally:
            shutil.rmtree(tmp)

    def test_four_enhancements_precise_values(self):
        """四种增强同时激活 → 归一化后各权重精确值

        原始: base 55% + ml 15% + tpl 15% + nvr 10% + sp 15% = 110%
        归一化: 各权重 / 1.10
          base = 55/110 = 50.00%
          ml   = 15/110 = 13.64%
          tpl  = 15/110 = 13.64%
          nvr  = 10/110 =  9.09%
          sp   = 15/110 = 13.64%
        """
        tmp = tempfile.mkdtemp()
        try:
            # 构造同时触发多语言 + C++ + 数值 + 多物理场的项目
            _write_tree(tmp, {
                "CMakeLists.txt": "add_subdirectory(src/structural)\n"
                                  "add_subdirectory(src/thermal)\n",
                "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
                "src/structural/Solver.cpp": "void solve() {}\n"
                                             "double residual = 1e-8;\n",
                "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
                "src/thermal/Solver.cpp": "void solve() {}\n"
                                          "double residual = 1e-8;\n",
                "python_bridge.py": "import structural_module\n"
                                    "s = structural_module.solve()\n",
                "tests/structural_mms.cpp": "// MMS verification\n",
            })
            report = ComprehensiveReport(tmp)
            data = report.generate()
            structural = data["dimensions"]["structural"]

            ml_w = structural.get("multilang_enhancement", {}).get("weight_applied", 0)
            tpl_w = structural.get("template_enhancement", {}).get("weight_applied", 0)
            nvr_w = structural.get("numerical_enhancement", {}).get("weight_applied", 0)
            sp_w = structural.get("solver_physics_enhancement", {}).get("weight_applied", 0)
            base_w = 1 - (ml_w + tpl_w + nvr_w + sp_w)

            # 精确值断言（防归一化公式回归）
            self.assertAlmostEqual(base_w, 0.5000, places=4)
            self.assertAlmostEqual(ml_w, 0.1364, places=4)
            self.assertAlmostEqual(tpl_w, 0.1364, places=4)
            self.assertAlmostEqual(nvr_w, 0.0909, places=4)
            self.assertAlmostEqual(sp_w, 0.1364, places=4)

            # 总和恒为 1
            self.assertAlmostEqual(base_w + ml_w + tpl_w + nvr_w + sp_w, 1.0, places=4)
        finally:
            shutil.rmtree(tmp)


class TestAssemblyMergeIntegration(unittest.TestCase):
    """装配层验证：用固定 mock 输入区分"组件错"与"装配错"

    组件输出固定为已知值，若合并后分数 ≠ 手工计算值，
    则问题必然出在 ComprehensiveReport 的合并逻辑，而非组件本身。
    """

    def _mock_metrics_outputs(self):
        """构造固定已知的各组件输出"""
        std = {
            "structural": {
                "score": 60.0,
                "details": {"modularity": 60, "coupling": 60, "cohesion": 60,
                            "complexity": 60, "testability": 60},
            },
            "design": {"score": 70.0, "details": {"solid": 70, "patterns": 70,
                                                  "style": 70, "anti_patterns": 70}},
            "documentation": {"score": 50.0, "details": {"readme": 50, "changelog": 50,
                                                         "adr": 50, "comments": 50,
                                                         "jsdoc": 50, "arch_doc": 50}},
            "evolution": {"score": 40.0, "details": {"git_activity": 40, "debt_trend": 40,
                                                     "dep_outdated": 40, "dead_code": 40,
                                                     "incremental": 40, "problems": 40}},
            "files": {"total": 10, "by_lang": {"cpp": 10}, "total_lines": 100,
                      "files_detail": []},
        }
        ml = {
            "overall": None,
            "is_single_language": True,
            "languages": ["cpp"],
            "mlr_violations": [],
            "dimensions": {},
        }
        tpl = {
            "overall": None,
            "is_cpp_project": False,
            "mlr_violations": [],
            "dimensions": {},
        }
        nvr = {
            "overall": None,
            "is_numerical": False,
            "nvr_violations": [],
            "dimensions": {},
        }
        sp = {
            "overall": 80.0,
            "is_multiphysics": True,
            "dimensions": {},
            "mpr_violations": [],
        }
        return std, ml, tpl, nvr, sp

    def test_sp_alone_assembly_formula(self):
        """仅 sp 增强激活时的装配公式验证

        合并公式: merged = (base*struct + sp*sp_score) / (base + sp)
        base=0.85, sp=0.15, struct=60, sp_score=80
        merged = (0.85*60 + 0.15*80) / 1.0 = 51 + 12 = 63.0
        """
        import unittest.mock as mock

        tmp = _make_multiphysics_project()
        try:
            std, ml, tpl, nvr, sp = self._mock_metrics_outputs()

            # 直接构造报告对象，绕过真实组件初始化
            report = object.__new__(ComprehensiveReport)
            report.root = tmp
            report.standard = mock.Mock()
            report.standard.all_metrics.return_value = std
            report.multilang = mock.Mock()
            report.multilang.all_metrics.return_value = ml
            report.template = mock.Mock()
            report.template.all_metrics.return_value = tpl
            report.numerical = mock.Mock()
            report.numerical.all_metrics.return_value = nvr
            report.solver_physics = mock.Mock()
            report.solver_physics.all_metrics.return_value = sp
            report.quality_weights = {"结构质量": 0.30, "设计质量": 0.25,
                                      "文档质量": 0.20, "演进质量": 0.25}

            data = report.generate()
            merged = data["dimensions"]["structural"]["score"]
            # 手工计算: (0.85*60 + 0.15*80) / 1.0 = 63.0
            self.assertAlmostEqual(merged, 63.0, places=2)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
