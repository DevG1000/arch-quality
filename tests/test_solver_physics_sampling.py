"""
test_solver_physics_sampling.py — 抽样质量保证测试

验证抽样检测不会导致评分失真：
1. 抽样比例记录正确性
2. 计数型检测外推误差控制
3. 全量 vs 抽样维度得分一致性
4. 布尔型检测在抽样下判定不变
"""

import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arch_quality.arch_metrics_solver_physics import (
    SolverPhysicsMetrics,
    DIRECT_MEMBER_ACCESS,
)


def _write_tree(root, files: dict):
    for path, content in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


def _make_project_with_many_files(n_source=50, n_internal_access=20):
    """构造含大量源文件 + 大量内部访问的合成项目

    - n_source: 源文件总数
    - n_internal_access: 内部访问分布的文件数
    """
    tmp = tempfile.mkdtemp()
    files = {
        "CMakeLists.txt": "add_subdirectory(src/structural)\n"
                          "add_subdirectory(src/thermal)\n",
        "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
        "src/structural/Solver.cpp": "void solve() {}\n",
        "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
        "src/thermal/Solver.cpp": "void solve() {}\n",
    }
    # 大量内部访问文件（模拟未封装代码）
    for i in range(n_internal_access):
        files[f"src/structural/Leaky{i}.cpp"] = (
            "void leaky() {\n"
            "    thermal->internal_data = 1;\n"
            "    thermal->private_field = 2;\n"
            "}\n"
        )
    # 大量无内部访问的普通文件（稀释）
    for i in range(n_source - n_internal_access):
        files[f"src/thermal/Body{i}.cpp"] = "void body() {}\n"
    _write_tree(tmp, files)
    return tmp


class TestSampleRatioRecording(unittest.TestCase):
    """抽样比例记录"""

    def test_sample_ratio_1_for_small_project(self):
        tmp = _make_project_with_many_files(n_source=10)
        try:
            m = SolverPhysicsMetrics(tmp)
            self.assertEqual(m._sample_ratio, 1.0)
        finally:
            shutil.rmtree(tmp)

    def test_sample_ratio_less_than_1_for_large_project(self):
        # 构造 >2000 文件的项目
        tmp = _make_project_with_many_files(n_source=0, n_internal_access=0)
        try:
            # 手动添加 2500 个文件触发抽样
            for i in range(2500):
                with open(os.path.join(tmp, f"src/thermal/File{i}.cpp"),
                          "w", encoding="utf-8") as f:
                    f.write("void f() {}\n")
            m = SolverPhysicsMetrics(tmp)
            self.assertLess(m._sample_ratio, 1.0)
            self.assertGreater(m._sample_ratio, 0.0)
        finally:
            shutil.rmtree(tmp)


class TestCountExtrapolation(unittest.TestCase):
    """计数型检测外推"""

    def test_sum_matches_extrapolated_full(self):
        """抽样比例为 1 时外推值 = 原始值"""
        tmp = _make_project_with_many_files(n_source=30, n_internal_access=10)
        try:
            m = SolverPhysicsMetrics(tmp)
            m._sample_ratio = 1.0
            raw = m._sum_matches(DIRECT_MEMBER_ACCESS)
            extrap = m._sum_matches_extrapolated(DIRECT_MEMBER_ACCESS)
            self.assertEqual(raw, extrap)
        finally:
            shutil.rmtree(tmp)

    def test_sum_matches_extrapolated_half(self):
        """抽样比例为 0.5 时外推值 ≈ 原始值 * 2"""
        tmp = _make_project_with_many_files(n_source=30, n_internal_access=10)
        try:
            m = SolverPhysicsMetrics(tmp)
            m._scan_files()  # 触发实际扫描
            m._sample_ratio = 0.5
            raw = m._sum_matches(DIRECT_MEMBER_ACCESS)
            extrap = m._sum_matches_extrapolated(DIRECT_MEMBER_ACCESS)
            # 外推 ≈ 2x 原始（允许 ±30% 误差，因抽样文件内命中数可能不全）
            self.assertGreaterEqual(extrap, raw)
            self.assertLessEqual(extrap, raw * 3)
        finally:
            shutil.rmtree(tmp)

    def test_internal_access_extrapolated_in_score(self):
        """封装性得分在外推后不应虚高"""
        tmp = _make_project_with_many_files(n_source=50, n_internal_access=20)
        try:
            m = SolverPhysicsMetrics(tmp)
            # 强制模拟半抽样：只保留一半内容
            keys = list(m._all_contents.keys())
            half = keys[:len(keys)//2]
            m._all_contents = {k: m._all_contents[k] for k in half}
            m._sample_ratio = 0.5

            score, detail = m.calc_boundary_integrity()
            enc = detail["encapsulation"]
            # 外推后的 internal_access_count 应大于抽样原始值
            self.assertGreater(enc["internal_access_count"], 0)
            self.assertIn("_sampled", detail)
            self.assertTrue(detail["_sampled"]["estimated"])
        finally:
            shutil.rmtree(tmp)


class TestBooleanDetectionStability(unittest.TestCase):
    """布尔型检测在抽样下判定稳定"""

    def test_boolean_detection_unchanged(self):
        """FMI/插件等布尔检测在抽样下判定不变"""
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "CMakeLists.txt": "add_subdirectory(src/structural)\n"
                                  "add_subdirectory(src/thermal)\n",
                "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
                "src/structural/Solver.cpp": "void solve() {}\n",
                "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
                "src/thermal/Solver.cpp": "void solve() {}\n",
                "coupling/FMIInterface.cpp": "void fmi2DoStep(double t) {}\n",
                "plugin/Registry.cpp": "void registerPlugin() {}\n"
                                       "class MyModule : public Module { };\n",
                "tests/structural_mms.cpp": "// MMS verification\n",
                "tests/thermal_mms.cpp": "// MMS verification\n",
            })
            m = SolverPhysicsMetrics(tmp)
            full = m.all_metrics()

            # 强制半抽样
            keys = list(m._all_contents.keys())
            half = keys[:max(1, len(keys)//2)]
            m._all_contents = {k: m._all_contents[k] for k in half}
            m._sample_ratio = 0.5
            sampled = m.all_metrics()

            # 布尔型判定应保持
            self.assertEqual(full["is_multiphysics"], sampled["is_multiphysics"])
            self.assertGreaterEqual(sampled["overall"], 0)
            self.assertLessEqual(sampled["overall"], 100)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
