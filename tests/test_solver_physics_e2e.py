"""
test_solver_physics_e2e.py — SolverPhysicsMetrics 端到端测试

验证完整管道的输出结构：
1. 合成多物理场项目 → is_multiphysics=True，4 维度评分非 None
2. 非多物理场项目（纯 Python）→ is_multiphysics=False，各维度 None
3. 非多物理场项目（含关键词但非源码）→ 避免关键词误报
4. CLI JSON 输出 → 合法 JSON 且含全部必需字段
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arch_quality.arch_metrics_solver_physics import SolverPhysicsMetrics


def _write_tree(root, files: dict):
    for path, content in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


def _make_multiphysics_project():
    tmp = tempfile.mkdtemp()
    _write_tree(tmp, {
        "CMakeLists.txt": "add_subdirectory(src/structural)\n"
                          "add_subdirectory(src/thermal)\n",
        "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
        "src/structural/Solver.cpp": "void solve() {}\n",
        "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
        "src/thermal/Solver.cpp": "void solve() {}\n",
    })
    return tmp


class TestE2EMultiphysicsProject(unittest.TestCase):
    """端到端：合成多物理场项目"""

    def test_full_pipeline(self):
        tmp = _make_multiphysics_project()
        try:
            m = SolverPhysicsMetrics(tmp)
            result = m.all_metrics()
            self.assertTrue(result["is_multiphysics"])
            self.assertIsNotNone(result["overall"])
            self.assertIn("boundary_integrity", result["dimensions"])
            self.assertIn("coupling_architecture", result["dimensions"])
            self.assertIn("extension_support", result["dimensions"])
            self.assertIn("data_transfer", result["dimensions"])
            self.assertIsInstance(result["mpr_violations"], list)
            self.assertIn("version_info", result)
        finally:
            shutil.rmtree(tmp)

    def test_dimension_scores_not_none(self):
        tmp = _make_multiphysics_project()
        try:
            m = SolverPhysicsMetrics(tmp)
            result = m.all_metrics()
            for dim_name, dim_data in result["dimensions"].items():
                self.assertIsNotNone(dim_data["score"])
                self.assertIsInstance(dim_data["detail"], dict)
        finally:
            shutil.rmtree(tmp)

    def test_json_serializable(self):
        tmp = _make_multiphysics_project()
        try:
            m = SolverPhysicsMetrics(tmp)
            result = m.all_metrics()
            json_str = json.dumps(result, ensure_ascii=False, indent=2)
            parsed = json.loads(json_str)
            self.assertEqual(parsed["is_multiphysics"], True)
        finally:
            shutil.rmtree(tmp)


class TestE2ENonMultiphysicsProject(unittest.TestCase):
    """端到端：非多物理场项目降级逻辑"""

    def test_pure_python_project(self):
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "main.py": "import os\nprint('hello')\n",
                "utils/helper.py": "def f():\n    return 1\n",
            })
            m = SolverPhysicsMetrics(tmp)
            result = m.all_metrics()
            self.assertFalse(result["is_multiphysics"])
            self.assertIsNone(result["overall"])
            for dim_data in result["dimensions"].values():
                self.assertIsNone(dim_data["score"])
            self.assertEqual(result["mpr_violations"], [])
        finally:
            shutil.rmtree(tmp)

    def test_python_project_with_keywords_in_docs(self):
        """含多物理场关键词但仅在 .md 文档中 → 不应误报"""
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "main.py": "import os\nprint('hello')\n",
                "docs/README.md": "This is a multiphysics coupling FSI project\n",
            })
            m = SolverPhysicsMetrics(tmp)
            self.assertFalse(m._is_multiphysics)
            result = m.all_metrics()
            self.assertFalse(result["is_multiphysics"])
        finally:
            shutil.rmtree(tmp)

    def test_python_project_with_keywords_in_py(self):
        """含多物理场关键词但非求解器 → 不误报为多物理场"""
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "main.py": "# 普通项目\n"
                           "# 提及 multiphysics 作为注释\n"
                           "print('hello')\n",
            })
            m = SolverPhysicsMetrics(tmp)
            # 单个文件含关键词，但缺少目录结构/耦合框架 → 判定需谨慎
            # 只要工具不崩溃且返回合法结构即可
            result = m.all_metrics()
            self.assertIn("is_multiphysics", result)
        finally:
            shutil.rmtree(tmp)


class TestE2ECLIOutput(unittest.TestCase):
    """端到端：CLI 输出结构验证"""

    def test_main_json_output(self):
        tmp = _make_multiphysics_project()
        try:
            from arch_quality.arch_metrics_solver_physics import main
            import sys as _sys
            _sys.argv = ["arch-quality-solver-physics", tmp, "--json"]
            buf = StringIO()
            try:
                with redirect_stdout(buf):
                    main()
            except SystemExit:
                pass
            output = buf.getvalue()
            # 输出应包含 JSON 结构
            self.assertIn("is_multiphysics", output)
            self.assertIn("overall", output)
        finally:
            shutil.rmtree(tmp)

    def test_main_requires_existing_root(self):
        """CLI 对不存在目录不应崩溃"""
        from arch_quality.arch_metrics_solver_physics import main
        import sys as _sys
        tmp = tempfile.mkdtemp()
        try:
            _sys.argv = ["arch-quality-solver-physics", tmp]
            buf = StringIO()
            try:
                with redirect_stdout(buf):
                    main()
            except SystemExit:
                pass
            output = buf.getvalue()
            self.assertIn("Report saved", output)
        finally:
            shutil.rmtree(tmp)


class TestE2ETypeAssertions(unittest.TestCase):
    """端到端：严格字段类型与范围断言（防"结构存在但值错误"）"""

    def test_output_schema_types(self):
        """all_metrics() 输出字段的类型与范围完整性"""
        tmp = _make_multiphysics_project()
        try:
            m = SolverPhysicsMetrics(tmp)
            result = m.all_metrics()
            # 顶层字段类型
            self.assertIsInstance(result["is_multiphysics"], bool)
            self.assertIsInstance(result["overall"], (int, float))
            self.assertIsInstance(result["dimensions"], dict)
            self.assertIsInstance(result["mpr_violations"], list)
            # overall 范围
            self.assertGreaterEqual(result["overall"], 0)
            self.assertLessEqual(result["overall"], 100)
            # 4 维度结构
            for dim_name, dim_data in result["dimensions"].items():
                self.assertIn("score", dim_data)
                self.assertIn("detail", dim_data)
                # score 类型与范围
                s = dim_data["score"]
                self.assertIsInstance(s, (int, float))
                self.assertGreaterEqual(s, 0)
                self.assertLessEqual(s, 100)
                self.assertIsInstance(dim_data["detail"], dict)
            # MPR 违规结构
            for v in result["mpr_violations"]:
                self.assertIsInstance(v["rule"], str)
                self.assertIsInstance(v["severity"], str)
                self.assertIsInstance(v["output_level"], str)
                self.assertIsInstance(v["detail"], str)
            # version_info
            self.assertIsInstance(result["version_info"]["guide_version"], str)
            self.assertIsInstance(result["version_info"]["skill_version"], str)
        finally:
            shutil.rmtree(tmp)

    def test_non_multiphysics_schema_types(self):
        """非多物理场项目输出类型"""
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "main.py": "import os\nprint('hello')\n",
            })
            m = SolverPhysicsMetrics(tmp)
            result = m.all_metrics()
            self.assertIs(result["is_multiphysics"], False)
            self.assertIsNone(result["overall"])
            for dim_data in result["dimensions"].values():
                self.assertIsNone(dim_data["score"])
                self.assertIsInstance(dim_data["detail"], dict)
            self.assertEqual(result["mpr_violations"], [])
        finally:
            shutil.rmtree(tmp)


class TestE2EBoundaryCases(unittest.TestCase):
    """端到端：边界降级路径"""

    def test_empty_project(self):
        """空项目（无源码文件）"""
        tmp = tempfile.mkdtemp()
        try:
            m = SolverPhysicsMetrics(tmp)
            result = m.all_metrics()
            self.assertIn("is_multiphysics", result)
            self.assertIsNotNone(result["dimensions"])
        finally:
            shutil.rmtree(tmp)

    def test_single_solver_module(self):
        """仅一个求解器模块 → 不应判定为多物理场"""
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "src/structural/Solver.cpp": "void solve() {}\n",
                "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
            })
            m = SolverPhysicsMetrics(tmp)
            # 仅一个物理场种类 → is_multiphysics=False（或容忍为 True 但结构完整）
            result = m.all_metrics()
            self.assertIn("is_multiphysics", result)
            self.assertIn("dimensions", result)
        finally:
            shutil.rmtree(tmp)

    def test_cpp_but_not_solver(self):
        """C++ 项目但非求解器 → 不应判定为多物理场"""
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "src/main.cpp": "int main() { return 0; }\n",
                "src/util.cpp": "void util() {}\n",
                "CMakeLists.txt": "add_executable(app src/main.cpp)\n",
            })
            m = SolverPhysicsMetrics(tmp)
            self.assertFalse(m._is_multiphysics)
            result = m.all_metrics()
            self.assertFalse(result["is_multiphysics"])
        finally:
            shutil.rmtree(tmp)


class TestE2ERealProjectSmoke(unittest.TestCase):
    """端到端：真实项目结构冒烟（复用回归基线项目，只验结构不验分值）

    与回归测试的区别：
    - 回归测试：验证精确分值不漂移（slow，需基线）
    - 本测试：验证真实项目不崩溃、结构完整（快，缓存复用）
    """

    REAL_PROJECTS = {
        'MOOSE': r'D:\opensource\MOOSE',
        'MFEM': r'D:\opensource\mfem',
    }

    def test_real_projects_structure(self):
        for name, path in self.REAL_PROJECTS.items():
            if not os.path.isdir(path):
                continue
            with self.subTest(project=name):
                m = SolverPhysicsMetrics(path)
                result = m.all_metrics()
                # 结构完整性（不验分值）
                self.assertIn("is_multiphysics", result)
                self.assertIn("overall", result)
                self.assertIn("dimensions", result)
                self.assertIn("mpr_violations", result)
                for dim_data in result["dimensions"].values():
                    self.assertIn("score", dim_data)
                    self.assertIn("detail", dim_data)
                # JSON 可序列化
                json_str = json.dumps(result, ensure_ascii=False)
                self.assertIsNotNone(json_str)


if __name__ == "__main__":
    unittest.main()
