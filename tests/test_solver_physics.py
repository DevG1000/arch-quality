"""
test_solver_physics.py — arch_metrics_solver_physics.py 单元测试

测试场景:
1. 辅助函数（检测模式正则、关键词匹配、文件过滤）
2. 非多物理场项目返回 is_multiphysics=False，各维度为 None
3. 多物理场项目基础检测
4. 物理场模块边界完整性评分（维度1）
5. 多物理场耦合架构合理性评分（维度2）
6. 插件式扩展架构支持度评分（维度3，含递进扣分）
7. 跨场数据传递规范性评分（维度4，含 FMI 加分）
8. MPR 规则触发条件
9. 综合评分权重计算
"""

import os
import re
import shutil
import tempfile
import unittest

from arch_quality.arch_metrics_solver_physics import (
    SolverPhysicsMetrics,
    _has_keyword,
    _count_occurrences,
    _grep_files,
    FMI_FUNCTIONS_PATTERN,
    MMS_PATTERN,
    CONVERGENCE_PATTERN,
    DIRECT_MEMBER_ACCESS,
)
from arch_quality.arch_core import FileIndex


def _write_tree(root, files: dict):
    """创建测试项目文件树"""
    for path, content in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


class TestHelperFunctions(unittest.TestCase):
    """辅助函数和检测模式测试"""

    def test_has_keyword(self):
        self.assertTrue(_has_keyword("multiphysics coupling", {"multiphysics"}))
        self.assertTrue(_has_keyword("FSI solver", {"fsi"}))
        self.assertFalse(_has_keyword("hello world", {"coupling"}))

    def test_has_keyword_case_insensitive(self):
        self.assertTrue(_has_keyword("MultiPhysics", {"multiphysics"}))
        self.assertTrue(_has_keyword("Co_Simulation", {"co_simulation"}))
        self.assertTrue(_has_keyword("FSI Solver", {"fsi"}))

    def test_count_occurrences(self):
        content = "foo bar foo baz foo"
        self.assertEqual(_count_occurrences(content, re.compile(r"foo")), 3)
        self.assertEqual(_count_occurrences("nothing here", re.compile(r"foo")), 0)

    def test_grep_files(self):
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "src/a.py": "",
                "src/b.cpp": "",
                "src/c.f90": "",
                "docs/readme.md": "",
            })
            idx = FileIndex(tmp)
            py_files = _grep_files(idx, {".py"})
            self.assertEqual(len(py_files), 1)
            cpp_files = _grep_files(idx, {".cpp"})
            self.assertEqual(len(cpp_files), 1)
        finally:
            shutil.rmtree(tmp)

    def test_fmi_pattern(self):
        self.assertTrue(FMI_FUNCTIONS_PATTERN.search("fmi2DoStep(t, x);"))
        self.assertTrue(FMI_FUNCTIONS_PATTERN.search("fmi2GetReal(v);"))
        self.assertFalse(FMI_FUNCTIONS_PATTERN.search("int x = 1;"))

    def test_mms_pattern(self):
        self.assertTrue(MMS_PATTERN.search("MMS verification"))
        self.assertTrue(MMS_PATTERN.search("method of manufactured solution"))
        self.assertTrue(MMS_PATTERN.search("order of accuracy"))
        self.assertFalse(MMS_PATTERN.search("int a = 1;"))

    def test_convergence_pattern(self):
        self.assertTrue(CONVERGENCE_PATTERN.search("residual = 1e-8"))
        self.assertTrue(CONVERGENCE_PATTERN.search("tolerance = 1e-6"))
        self.assertFalse(CONVERGENCE_PATTERN.search("int x = 1;"))

    def test_direct_member_access(self):
        self.assertTrue(DIRECT_MEMBER_ACCESS.search("solver->internal_data = x;"))
        self.assertFalse(DIRECT_MEMBER_ACCESS.search("solver->solve(x);"))


class TestNonMultiphysicsProject(unittest.TestCase):
    """非多物理场项目应返回 None"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _write_tree(self.tmp, {
            "main.py": "import os\nprint('hello')\n",
            "utils/helper.py": "def f():\n    return 1\n",
        })

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_is_not_multiphysics(self):
        m = SolverPhysicsMetrics(self.tmp)
        self.assertFalse(m._is_multiphysics)

    def test_all_metrics_returns_none(self):
        m = SolverPhysicsMetrics(self.tmp)
        r = m.all_metrics()
        self.assertFalse(r["is_multiphysics"])
        self.assertIsNone(r["overall"])
        for dim in r["dimensions"].values():
            self.assertIsNone(dim["score"])

    def test_no_mpr_violations(self):
        m = SolverPhysicsMetrics(self.tmp)
        violations = m.check_mpr_rules()
        self.assertEqual(violations, [])


class TestMultiphysicsProjectBasic(unittest.TestCase):
    """多物理场项目基础检测"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _write_tree(self.tmp, {
            "CMakeLists.txt": "add_subdirectory(src/structural)\nadd_subdirectory(src/thermal)\n",
            "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
            "src/structural/Structural.cpp": "class StructuralSolver {\n    void solve() {}\n};\n",
            "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
            "src/thermal/Thermal.cpp": "class ThermalSolver {\n    void solve() {}\n};\n",
            "coupling/CouplingLayer.cpp": "void exchangeField() {}\n",
        })

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_detected_as_multiphysics(self):
        m = SolverPhysicsMetrics(self.tmp)
        self.assertTrue(m._is_multiphysics)

    def test_all_metrics_structure(self):
        m = SolverPhysicsMetrics(self.tmp)
        r = m.all_metrics()
        self.assertTrue(r["is_multiphysics"])
        self.assertIsNotNone(r["overall"])
        self.assertIn("boundary_integrity", r["dimensions"])
        self.assertIn("coupling_architecture", r["dimensions"])
        self.assertIn("extension_support", r["dimensions"])
        self.assertIn("data_transfer", r["dimensions"])

    def test_version_info(self):
        m = SolverPhysicsMetrics(self.tmp)
        r = m.all_metrics()
        vi = r["version_info"]
        self.assertEqual(vi["guide_version"], "1.3")
        self.assertEqual(vi["skill_version"], "1.0")


class TestBoundaryIntegrity(unittest.TestCase):
    """维度1：物理场模块边界完整性评分"""

    def test_independent_units_boost_score(self):
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "CMakeLists.txt": "add_subdirectory(src/structural)\nadd_subdirectory(src/thermal)\n",
                "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
                "src/structural/Solver.cpp": "class StructuralSolver { void solve() {} };\n",
                "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
                "src/thermal/Solver.cpp": "class ThermalSolver { void solve() {} };\n",
                "src/structural/Solver.h": "void solve();\n",
                "src/thermal/Solver.h": "void solve();\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_boundary_integrity()
            self.assertIsNotNone(score)
            self.assertEqual(detail["independent_units"]["score"], 20)
        finally:
            shutil.rmtree(tmp)

    def test_freefem_style_src_subdir_solver_units(self):
        # B3.5 FreeFEM 探查修复：功能名命名的 src/ 二级子目录（fflib/femlib/bamg）
        # 不含物理场关键词，应被回填识别为独立求解器模块。
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "CMakeLists.txt": "add_subdirectory(src/fflib)\n"
                                  "add_subdirectory(src/femlib)\n"
                                  "add_subdirectory(src/bamg)\n",
                "src/fflib/FreeFem.cpp": "class FreeFemCore {};\n"
                                          "void fflib_solve() {}\n",
                "src/fflib/FFLib.h": "void fflib_solve();\n",
                "src/femlib/FemLib.cpp": "class FemLib {};\n"
                                          "void femlib_solve() {}\n",
                "src/femlib/FemLib.h": "void femlib_solve();\n",
                "src/bamg/Bamg.cpp": "class BamgMesh {};\n"
                                      "void bamg_mesh() {}\n",
                "src/bamg/Bamg.h": "void bamg_mesh();\n",
                # 触发多物理场判定（含耦合关键词的源码）
                "src/fflib/FSI.cpp": "// fsi coupling\nvoid fsi_solve() {}\n",
            })
            m = SolverPhysicsMetrics(tmp)
            self.assertTrue(m._is_multiphysics)
            # 回填应识别 src/ 下的 fflib/femlib/bamg 为求解器模块
            self.assertGreaterEqual(len(m._solver_dirs), 2,
                                    "FreeFEM 风格 src 子目录应被回填为求解器模块")
            score, detail = m.calc_boundary_integrity()
            self.assertEqual(detail["independent_units"]["score"], 20)
        finally:
            shutil.rmtree(tmp)

    def test_api_count_scoring(self):
        tmp = tempfile.mkdtemp()
        try:
            api_headers = "".join(
                f"double function_{i}(double x);\n" for i in range(60)
            )
            _write_tree(tmp, {
                "CMakeLists.txt": "add_subdirectory(src/structural)\nadd_subdirectory(src/thermal)\n",
                "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
                "src/structural/Solver.cpp": "void solve() {}\n",
                "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
                "src/thermal/Solver.cpp": "void solve() {}\n",
                "src/structural/Solver.h": api_headers,
                "src/thermal/Solver.h": "void solve();\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_boundary_integrity()
            self.assertIsNotNone(score)
            # avg_api = (60 + 1) / 2 = 30.5 <= 50 → 20 分
            self.assertEqual(detail["api_compactness"]["score"], 20)
        finally:
            shutil.rmtree(tmp)

    def test_mms_readiness_detection(self):
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "CMakeLists.txt": "add_subdirectory(src/structural)\nadd_subdirectory(src/thermal)\n",
                "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
                "src/structural/Solver.cpp": "void solve() {}\n",
                "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
                "src/thermal/Solver.cpp": "void solve() {}\n",
                "tests/structural_mms.cpp": "// MMS verification\n",
                "tests/thermal_mms.cpp": "// method of manufactured solutions\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_boundary_integrity()
            self.assertIsNotNone(score)
            self.assertGreater(detail["mms_readiness"]["score"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_encapsulation_detection(self):
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "CMakeLists.txt": "add_subdirectory(src/structural)\nadd_subdirectory(src/thermal)\n",
                "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
                "src/structural/Solver.cpp": "void solve() {}\n",
                "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
                "src/thermal/Solver.cpp": "void solve() {}\n",
                "src/structural/bad.cpp": "thermal->internal_data = 1;\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_boundary_integrity()
            self.assertIsNotNone(score)
            self.assertGreater(detail["encapsulation"]["internal_access_count"], 0)
        finally:
            shutil.rmtree(tmp)


class TestCouplingArchitecture(unittest.TestCase):
    """维度2：多物理场耦合架构合理性评分"""

    def _make_base_project(self):
        tmp = tempfile.mkdtemp()
        _write_tree(tmp, {
            "CMakeLists.txt": "add_subdirectory(src/structural)\nadd_subdirectory(src/thermal)\n",
            "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
            "src/structural/Solver.cpp": "class StructuralSolver { void solve() {} };\n",
            "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
            "src/thermal/Solver.cpp": "class ThermalSolver { void solve() {} };\n",
        })
        return tmp

    def test_coupling_concentration_score(self):
        tmp = self._make_base_project()
        try:
            # 添加更多非耦合源文件，降低耦合文件占比
            _write_tree(tmp, {
                "coupling/CouplingLayer.cpp": "void exchange() {}\nvoid transfer() {}\n",
                "src/structural/Material.cpp": "void materialModel() {}\n",
                "src/structural/Mesh.cpp": "void buildMesh() {}\n",
                "src/thermal/Convection.cpp": "void solveConvection() {}\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_coupling_architecture()
            self.assertIsNotNone(score)
            # 1 耦合文件 / 6 源文件 ≈ 16.7% < 30% → 应得 10 分
            self.assertGreater(detail["coupling_concentration"]["score"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_convergence_control_detection(self):
        """耦合层收敛控制：收敛关键词 + 耦合上下文同现 → 命中"""
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "coupling/CouplingLayer.cpp": "void exchange() {\n"
                                              "    double residual = 1e-8;\n"
                                              "    double tolerance = 1e-6;\n"
                                              "}\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_coupling_architecture()
            self.assertTrue(detail["convergence_stability"]["has_coupling_convergence"])
        finally:
            shutil.rmtree(tmp)

    def test_solver_internal_convergence_not_coupling(self):
        """单求解器内部收敛（无耦合上下文）不应判为耦合收敛控制"""
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "src/structural/Solver.cpp": "double residual = 1e-8;\n"
                                             "double tolerance = 1e-6;\n"
                                             "void solve() {}\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_coupling_architecture()
            # 纯求解器内部收敛 → 部分分（5），非耦合收敛（15）
            self.assertFalse(detail["convergence_stability"]["has_coupling_convergence"])
            self.assertEqual(detail["convergence_stability"]["score"], 5)
        finally:
            shutil.rmtree(tmp)

    def test_virtual_solve_detection(self):
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "src/structural/Solver.h": "class Solver {\npublic:\n    virtual void solve() = 0;\n};\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_coupling_architecture()
            self.assertTrue(detail["solver_replaceability"]["has_abstract_solver"] or
                            detail["solver_replaceability"]["has_virtual_solve"])
        finally:
            shutil.rmtree(tmp)

    def test_openfoam_fvSolution_residualControl_coupling(self):
        # B3.5 边界 3 修复：OpenFOAM fvSolution 字典（无源码扩展名）的
        # residualControl 属耦合求解收敛控制，应计入耦合收敛稳定性。
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "system/fvSolution": "SIMPLE\n{\n"
                                     "    residualControl\n"
                                     "    {\n"
                                     "        p  1e-4;\n"
                                     "        U  1e-4;\n"
                                     "    }\n"
                                     "    nCorrectors 2;\n"
                                     "}\n",
            })
            m = SolverPhysicsMetrics(tmp)
            # 配置字典应被扫描进 _config_contents
            self.assertTrue(m._config_contents,
                            "OpenFOAM 配置字典应被扫描进 _config_contents")
            score, detail = m.calc_coupling_architecture()
            self.assertTrue(detail["convergence_stability"]["has_coupling_convergence"],
                            "fvSolution 的 residualControl 应判为耦合收敛控制")
            self.assertEqual(detail["convergence_stability"]["score"], 15)
        finally:
            shutil.rmtree(tmp)

    def test_non_openfoam_config_ignored(self):
        # 非 OpenFOAM 配置文件名不应被扫描（避免污染其他项目）
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "config/settings.ini": "tolerance=1e-6\nresidual=0.1\n",
            })
            m = SolverPhysicsMetrics(tmp)
            self.assertEqual(len(m._config_contents), 0,
                             "非 OpenFOAM 配置文件名不应被扫描")
        finally:
            shutil.rmtree(tmp)

    def test_virtual_solve_uppercase_detection(self):
        # B3.5 SU2 漏报探查修复：SU2 CIteration 用大写 Solve()，原模式大小写敏感漏报
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "src/structural/Solver.h": "class Solver {\npublic:\n    virtual void Solve() = 0;\n};\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_coupling_architecture()
            self.assertTrue(detail["solver_replaceability"]["has_virtual_solve"],
                            "大写 Solve() 应被 VIRTUAL_SOLVE_PATTERN 识别")
        finally:
            shutil.rmtree(tmp)

    def test_virtual_solve_same_declaration_only(self):
        # B3.5 修复：避免跨方法误匹配（virtual 后到 solve( 之间不得跨越 ; ）
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "src/structural/Solver.h":
                    "class Solver {\n"
                    "public:\n"
                    "    virtual void PrintMathematica();\n"
                    "    virtual void GetInverseMatrix() { Factors::solve(); }\n"
                    "};\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_coupling_architecture()
            self.assertFalse(detail["solver_replaceability"]["has_virtual_solve"],
                            "跨方法误匹配（GetInverseMatrix 内调用 solve）不应被识别")
        finally:
            shutil.rmtree(tmp)

    def test_coupling_strength_judgment(self):
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "coupling/fsi.cpp": "// strong coupling with inner iteration\n"
                                    "while (converged < 0) {\n    // iterative exchange\n}\n"
                                    "// bidirectional transfer\n",
            })
            m = SolverPhysicsMetrics(tmp)
            strength = m._judge_coupling_strength()
            self.assertIn(strength, ("strong", "medium", "weak", "unknown"))
        finally:
            shutil.rmtree(tmp)

    def test_multimode_library_arch_prefers_iterative(self):
        # B3.5 preCICE 探查修复：通用耦合库同时支持 explicit(loose) 与
        # implicit/iterative。explicit 常出现在接口文档（字典序早于核心文件），
        # 两阶段检测应让 staggered 等核心求解语义优先，判 partitioned_iterative。
        tmp = self._make_base_project()
        try:
            # BaseCouplingScheme.hpp（explicit 接口文档）字典序早于 SerialCouplingScheme.hpp（staggered 核心）
            _write_tree(tmp, {
                "coupling/BaseCouplingScheme.hpp":
                    "// whether coupling scheme is an explicit coupling scheme\n"
                    "bool isExplicit() { return true; }\n",
                "coupling/SerialCouplingScheme.hpp":
                    "// Coupling scheme for serial coupling, i.e. staggered execution\n"
                    "class SerialCouplingScheme {};\n",
            })
            m = SolverPhysicsMetrics(tmp)
            arch = m._detect_coupling_architecture()
            self.assertEqual(arch, "partitioned_iterative",
                             "多模式库应优先识别核心 staggered 语义，而非接口文档的 explicit")
        finally:
            shutil.rmtree(tmp)

    def test_loose_only_arch_still_detected(self):
        # 仅含 loose/explicit 语义（无核心 iterative）仍应判 partitioned_loose
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "coupling/ExplicitScheme.hpp":
                    "// explicit coupling scheme\n"
                    "void explicitCoupling();\n",
            })
            m = SolverPhysicsMetrics(tmp)
            arch = m._detect_coupling_architecture()
            self.assertEqual(arch, "partitioned_loose")
        finally:
            shutil.rmtree(tmp)


class TestExtensionSupport(unittest.TestCase):
    """维度3：插件式扩展架构支持度评分"""

    def _make_base_project(self):
        tmp = tempfile.mkdtemp()
        _write_tree(tmp, {
            "CMakeLists.txt": "add_subdirectory(src/structural)\nadd_subdirectory(src/thermal)\n",
            "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
            "src/structural/Solver.cpp": "void solve() {}\n",
            "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
            "src/thermal/Solver.cpp": "void solve() {}\n",
        })
        return tmp

    def test_plugin_mechanism_detection(self):
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "plugin/Registry.cpp": "void registerPlugin(Module* m) {}\n"
                                       "// plugin registry\n"
                                       "class MyModule : public Module { };\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_extension_support()
            self.assertGreater(detail["dynamic_loading"]["score"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_dependency_declaration_detection(self):
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "CMakeLists.txt": "add_subdirectory(src/structural)\n"
                                  "add_subdirectory(src/thermal)\n"
                                  "target_link_libraries(structural thermal)\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_extension_support()
            self.assertTrue(detail["dependency_formalization"]["has_dependency_decl"])
        finally:
            shutil.rmtree(tmp)

    def test_version_management_detection(self):
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "src/structural/Solver.h": "// @deprecated use solve_v2\n"
                                           "version = \"1.2.0\"\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_extension_support()
            self.assertTrue(detail["version_management"]["has_deprecated"] or
                            detail["version_management"]["has_versioning"])
        finally:
            shutil.rmtree(tmp)

    def test_progressive_deduction(self):
        # 构造边界完整性得分极低的多物理场项目
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {
                "CMakeLists.txt": "add_subdirectory(src)\n",  # 单一模块，无独立单元
                "src/Solver.cpp": "void solve() {}\n",
                "src/Solver.h": "void solve();\n",
            })
            m = SolverPhysicsMetrics(tmp)
            ext_score, ext_detail = m.calc_extension_support()
            if ext_score is not None:
                deduction = ext_detail.get("progressive_deduction", {})
                self.assertIn("applied", deduction)
        finally:
            shutil.rmtree(tmp)

    def test_third_party_dir_excluded_from_cycles(self):
        """第三方依赖目录的循环不参与项目模块循环检测

        B3.5 验证 ElmerFEM 时发现：31 个循环 100% 来自根目录 umfpack 依赖。
        """
        tmp = self._make_base_project()
        try:
            # 构造第三方依赖目录中的头文件互引用循环
            _write_tree(tmp, {
                "umfpack/include/a.h": "#include \"b.h\"\n",
                "umfpack/include/b.h": "#include \"a.h\"\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_extension_support()
            # 第三方目录循环应被排除 → cycle_count 保持 0
            self.assertEqual(detail["no_cycles"]["cycle_count"], 0)
            self.assertEqual(detail["no_cycles"]["score"], 25)
        finally:
            shutil.rmtree(tmp)

    def test_project_module_cycle_still_detected(self):
        """项目自身模块的循环依赖仍应被检测"""
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "src/structural/a.h": "#include \"b.h\"\n",
                "src/structural/b.h": "#include \"a.h\"\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_extension_support()
            self.assertGreater(detail["no_cycles"]["cycle_count"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_fortran_plugin_detected(self):
        """Fortran GetProcAddr 命中 ≥3 文件 → 判定为插件机制"""
        tmp = self._make_base_project()
        try:
            for i in range(3):
                _write_tree(tmp, {
                    f"src/structural/proc{i}.f90": (
                        "subroutine load()\n"
                        "  addr = GetProcAddr('libSolver', 'Solve')\n"
                        "end subroutine\n"
                    ),
                })
            m = SolverPhysicsMetrics(tmp)
            fp = m._detect_fortran_plugin()
            self.assertTrue(fp["has_fortran_plugin"])
            self.assertGreaterEqual(fp["get_proc_files"], 3)
        finally:
            shutil.rmtree(tmp)

    def test_fortran_plugin_single_keyword(self):
        """仅 GetProcAddr 1 文件无佐证 → 不判定（防误报）"""
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "src/structural/proc.f90": (
                    "subroutine load()\n"
                    "  addr = GetProcAddr('libSolver', 'Solve')\n"
                    "end subroutine\n"
                ),
            })
            m = SolverPhysicsMetrics(tmp)
            fp = m._detect_fortran_plugin()
            self.assertFalse(fp["has_fortran_plugin"])
        finally:
            shutil.rmtree(tmp)

    def test_fortran_plugin_double_evidence(self):
        """GetProcAddr + 过程指针调用双特征 → 判定"""
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "src/structural/load.f90": (
                    "subroutine load()\n"
                    "  addr = GetProcAddr('libSolver', 'Solve')\n"
                    "end subroutine\n"
                ),
                "src/structural/exec.f90": (
                    "subroutine exec()\n"
                    "  CALL ExecSimulationProc(proc, model)\n"
                    "end subroutine\n"
                ),
            })
            m = SolverPhysicsMetrics(tmp)
            fp = m._detect_fortran_plugin()
            self.assertTrue(fp["has_fortran_plugin"])
        finally:
            shutil.rmtree(tmp)

    def test_fortran_plugin_iso_c_evidence(self):
        """ISO C 互操作 + GetProcAddr → 判定"""
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "src/structural/load.f90": (
                    "subroutine load()\n"
                    "  use iso_c_binding\n"
                    "  addr = GetProcAddr('libSolver', 'Solve')\n"
                    "end subroutine\n"
                ),
            })
            m = SolverPhysicsMetrics(tmp)
            fp = m._detect_fortran_plugin()
            self.assertTrue(fp["has_fortran_plugin"])
        finally:
            shutil.rmtree(tmp)

    def test_fortran_plugin_merge_no_double(self):
        """C++ 接口 + Fortran 插件同时存在 → 动态加载仍 30 分（不叠加）"""
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "src/structural/base.h": "class Solver {\n};\n"
                                         "class MySolver : public Solver {\n};\n"
                                         "// plugin registry\n"
                                         "void register() {}\n",
                "src/structural/load.f90": (
                    "subroutine load()\n"
                    "  addr = GetProcAddr('libSolver', 'Solve')\n"
                    "end subroutine\n"
                ),
                "src/structural/exec.f90": (
                    "subroutine exec()\n"
                    "  CALL ExecSimulationProc(proc, model)\n"
                    "end subroutine\n"
                ),
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_extension_support()
            dl = detail["dynamic_loading"]
            self.assertEqual(dl["score"], 30)  # 30 分上限，不因双机制叠加
        finally:
            shutil.rmtree(tmp)


class TestDataTransfer(unittest.TestCase):
    """维度4：跨场数据传递规范性评分"""

    def _make_base_project(self):
        tmp = tempfile.mkdtemp()
        _write_tree(tmp, {
            "CMakeLists.txt": "add_subdirectory(src/structural)\nadd_subdirectory(src/thermal)\n",
            "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
            "src/structural/Solver.cpp": "void solve() {}\n",
            "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
            "src/thermal/Solver.cpp": "void solve() {}\n",
        })
        return tmp

    def test_standardized_data_structure(self):
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "coupling/Data.cpp": "class Field { double* data; };\n"
                                     "Field temperature;\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_data_transfer()
            self.assertTrue(detail["standardized_data_structure"]["has_field_data"])
        finally:
            shutil.rmtree(tmp)

    def test_time_sync_detection(self):
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "coupling/TimeSync.cpp": "void syncTimeStep() {}\nvoid subCycle() {}\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_data_transfer()
            self.assertTrue(detail["time_synchronization"]["has_time_sync"])
        finally:
            shutil.rmtree(tmp)

    def test_spatial_mapping_detection(self):
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "coupling/Map.cpp": "void mapField(mesh* m) {}\nvoid interpolateData() {}\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_data_transfer()
            self.assertTrue(detail["spatial_mapping"]["has_spatial_map"])
        finally:
            shutil.rmtree(tmp)

    def test_format_conversion_detection(self):
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "coupling/Convert.cpp": "void convertMesh() {}\nvoid transformData() {}\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_data_transfer()
            self.assertGreater(detail["format_conversion"]["convert_site_count"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_third_party_format_conversion_excluded(self):
        """第三方依赖目录的转换关键词不参与格式转换统计

        B3.5 验证 Kratos 时发现：vexcl 等第三方库的 transform 词被误计。
        """
        tmp = self._make_base_project()
        try:
            # 仅第三方目录含转换关键词 → 项目自身 0 命中 → 满分 20
            _write_tree(tmp, {
                "external_libraries/vexcl/fft.hpp": "// transform data\nvoid transform() {}\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_data_transfer()
            fc = detail["format_conversion"]
            self.assertEqual(fc["convert_sites_sampled"], 0)
            self.assertEqual(fc["score"], 20)
        finally:
            shutil.rmtree(tmp)

    def test_project_format_conversion_still_detected(self):
        """项目自身格式转换仍被统计"""
        tmp = self._make_base_project()
        try:
            _write_tree(tmp, {
                "coupling/Convert.cpp": "void convertMesh() {}\n",
                "src/structural/Convert2.cpp": "void transformData() {}\n",
            })
            m = SolverPhysicsMetrics(tmp)
            score, detail = m.calc_data_transfer()
            self.assertGreater(detail["format_conversion"]["convert_sites_sampled"], 0)
        finally:
            shutil.rmtree(tmp)


class TestMPRRules(unittest.TestCase):
    """MPR 规则触发条件测试"""

    def _make_multiphysics(self):
        tmp = tempfile.mkdtemp()
        _write_tree(tmp, {
            "CMakeLists.txt": "add_subdirectory(src/structural)\nadd_subdirectory(src/thermal)\n",
            "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
            "src/structural/Solver.cpp": "void solve() {}\n",
            "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
            "src/thermal/Solver.cpp": "void solve() {}\n",
        })
        return tmp

    def test_no_mpr_for_clean_project(self):
        tmp = self._make_multiphysics()
        try:
            _write_tree(tmp, {
                "tests/structural_mms.cpp": "// MMS verification\n",
                "tests/thermal_mms.cpp": "// MMS verification\n",
                "coupling/CouplingLayer.cpp": "void exchange() {}\n",
                "plugin/Registry.cpp": "void registerPlugin() {}\n"
                                       "class MyModule : public Module { };\n",
            })
            m = SolverPhysicsMetrics(tmp)
            rules = [v["rule"] for v in m.check_mpr_rules()]
            self.assertNotIn("MPR-001", rules)
        finally:
            shutil.rmtree(tmp)

    def test_mpr001_when_solvers_in_one_unit(self):
        tmp = self._make_multiphysics()
        try:
            # 覆盖原文件，删除独立 CMake 目标 → 独立单元检测失败
            _write_tree(tmp, {
                "CMakeLists.txt": "add_executable(app main.cpp)\n",
            })
            m = SolverPhysicsMetrics(tmp)
            rules = [v["rule"] for v in m.check_mpr_rules()]
            self.assertIn("MPR-001", rules)
        finally:
            shutil.rmtree(tmp)

    def test_mpr002_when_api_count_high(self):
        tmp = self._make_multiphysics()
        try:
            api_headers = "".join(
                f"double function_{i}(double x);\n" for i in range(80)
            )
            _write_tree(tmp, {
                "src/structural/Solver.h": api_headers,
            })
            m = SolverPhysicsMetrics(tmp)
            rules = [v["rule"] for v in m.check_mpr_rules()]
            self.assertIn("MPR-002", rules)
        finally:
            shutil.rmtree(tmp)

    def test_mpr003_when_no_mms(self):
        tmp = self._make_multiphysics()
        try:
            # 无 MMS 文件
            m = SolverPhysicsMetrics(tmp)
            rules = [v["rule"] for v in m.check_mpr_rules()]
            self.assertIn("MPR-003", rules)
        finally:
            shutil.rmtree(tmp)

    def test_mpr008_when_cycle_detected(self):
        tmp = self._make_multiphysics()
        try:
            _write_tree(tmp, {
                "src/structural/a.h": "#include \"b.h\"\n",
                "src/structural/b.h": "#include \"a.h\"\n",
            })
            m = SolverPhysicsMetrics(tmp)
            rules = [v["rule"] for v in m.check_mpr_rules()]
            self.assertIn("MPR-008", rules)
        finally:
            shutil.rmtree(tmp)

    def test_mpr010_when_no_field_data(self):
        tmp = self._make_multiphysics()
        try:
            m = SolverPhysicsMetrics(tmp)
            rules = [v["rule"] for v in m.check_mpr_rules()]
            self.assertIn("MPR-010", rules)
        finally:
            shutil.rmtree(tmp)


class TestAllMetricsIntegration(unittest.TestCase):
    """all_metrics() 返回格式和权重计算"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _write_tree(self.tmp, {
            "CMakeLists.txt": "add_subdirectory(src/structural)\nadd_subdirectory(src/thermal)\n",
            "src/structural/CMakeLists.txt": "add_library(structural STRUCTURAL.cpp)\n",
            "src/structural/Solver.cpp": "void solve() {}\n",
            "src/thermal/CMakeLists.txt": "add_library(thermal THERMAL.cpp)\n",
            "src/thermal/Solver.cpp": "void solve() {}\n",
            "tests/structural_mms.cpp": "// MMS verification\n",
            "tests/thermal_mms.cpp": "// MMS verification\n",
        })

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_all_metrics_full_structure(self):
        m = SolverPhysicsMetrics(self.tmp)
        r = m.all_metrics()
        self.assertTrue(r["is_multiphysics"])
        self.assertIsNotNone(r["overall"])
        self.assertEqual(len(r["dimensions"]), 4)
        for dim_name, dim_data in r["dimensions"].items():
            self.assertIn("score", dim_data)
            self.assertIn("detail", dim_data)
        for v in r["mpr_violations"]:
            self.assertIn("rule", v)
            self.assertIn("severity", v)
            self.assertIn("output_level", v)
            self.assertIn("detail", v)

    def test_overall_weighted_average(self):
        m = SolverPhysicsMetrics(self.tmp)
        d1, _ = m.calc_boundary_integrity()
        d2, _ = m.calc_coupling_architecture()
        d3, _ = m.calc_extension_support()
        d4, _ = m.calc_data_transfer()
        expected = (d1 * 0.25 + d2 * 0.30 + d3 * 0.25 + d4 * 0.20)
        actual = m.calc_overall()
        self.assertAlmostEqual(actual, expected, places=2)

    def test_weights_from_skill(self):
        m = SolverPhysicsMetrics(self.tmp)
        self.assertIn("物理场模块边界完整性", m.weights)
        self.assertIn("多物理场耦合架构合理性", m.weights)
        self.assertIn("插件式扩展架构支持度", m.weights)
        self.assertIn("跨场数据传递规范性", m.weights)
        total = sum(m.weights.values())
        self.assertAlmostEqual(total, 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
