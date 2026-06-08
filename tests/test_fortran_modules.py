"""
test_fortran_modules.py — Fortran 模块名→文件路径映射 单元测试

测试场景:
1. module XXX 与文件名匹配 → 正确映射
2. module XXX 与文件名不同 → 映射到实际文件
3. 多模块文件 → 全部映射到同一文件
4. module procedure 被排除
5. end module 被排除
6. use 语句通过模块映射表解析
7. use 语句回退到文件名匹配
8. subroutine 提取和 call 解析
9. 同语言循环检测（模块名≠文件名）
10. 映射命中率统计
"""

import os
import tempfile
import shutil
import unittest

from arch_quality.arch_metrics_multilang import MultilangMetrics, _MODULE_DECL_RE, _SUBROUTINE_DECL_RE


class TestFortranModuleMapRegex(unittest.TestCase):
    """测试模块声明正则表达式"""

    def test_module_decl_matches(self):
        content = "module HeatSolve\nend module HeatSolve"
        matches = _MODULE_DECL_RE.findall(content)
        self.assertIn("heatsolve", [m.lower() for m in matches])

    def test_module_procedure_excluded(self):
        content = "module procedure solve_heat"
        matches = _MODULE_DECL_RE.findall(content)
        self.assertEqual(len(matches), 0)

    def test_end_module_not_matched(self):
        content = "end module HeatSolve"
        matches = _MODULE_DECL_RE.findall(content)
        self.assertNotIn("HeatSolve", matches)

    def test_multiple_modules_in_file(self):
        content = (
            "module CircuitUtils\n"
            "  ...\n"
            "end module CircuitUtils\n"
            "module CircuitsMod\n"
            "  ...\n"
            "end module CircuitsMod\n"
        )
        matches = _MODULE_DECL_RE.findall(content)
        self.assertEqual(len(matches), 2)

    def test_module_with_intrinsic(self):
        content = "use, intrinsic :: iso_fortran_env"
        matches = _MODULE_DECL_RE.findall(content)
        self.assertEqual(len(matches), 0)


class TestFortranSubroutineMapRegex(unittest.TestCase):
    """测试子程序声明正则表达式"""

    def test_subroutine_decl(self):
        content = "subroutine HeatSolver_init(Model, Solver, dt, Transient)"
        matches = _SUBROUTINE_DECL_RE.findall(content)
        self.assertIn("HeatSolver_init", matches)

    def test_function_decl(self):
        content = "real function CalculateStress(x, y)"
        matches = _SUBROUTINE_DECL_RE.findall(content)
        self.assertIn("CalculateStress", matches)

    def test_recursive_subroutine(self):
        content = "recursive subroutine TraverseTree(node)"
        matches = _SUBROUTINE_DECL_RE.findall(content)
        self.assertIn("TraverseTree", matches)

    def test_pure_function(self):
        content = "pure function add(a, b) result(c)"
        matches = _SUBROUTINE_DECL_RE.findall(content)
        self.assertIn("add", matches)

    def test_end_subroutine_excluded(self):
        content = "end subroutine Heatsolver_init"
        matches = _SUBROUTINE_DECL_RE.findall(content)
        self.assertNotIn("Heatsolver_init", matches)


class TestFortranModuleMap(unittest.TestCase):
    """测试 _build_fortran_module_map() 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_module_name_matches_filename(self):
        fpath = os.path.join(self.tmpdir, "HeatSolve.F90")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("module HeatSolve\nend module HeatSolve\n")
        metrics = MultilangMetrics(self.tmpdir)
        mmap = metrics._build_fortran_module_map()
        self.assertIn("heatsolve", mmap)
        self.assertEqual(mmap["heatsolve"], "HeatSolve.F90")

    def test_module_name_differs_from_filename(self):
        fpath = os.path.join(self.tmpdir, "Feti.F90")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("module FetiSolve\nend module FetiSolve\n")
        metrics = MultilangMetrics(self.tmpdir)
        mmap = metrics._build_fortran_module_map()
        self.assertIn("fetisolve", mmap)
        self.assertEqual(mmap["fetisolve"], "Feti.F90")

    def test_multi_module_file(self):
        fpath = os.path.join(self.tmpdir, "CircuitUtils.F90")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(
                "module CircuitUtils\nend module CircuitUtils\n"
                "module CircuitsMod\nend module CircuitsMod\n"
                "module CircMatInitMod\nend module CircMatInitMod\n"
            )
        metrics = MultilangMetrics(self.tmpdir)
        mmap = metrics._build_fortran_module_map()
        self.assertEqual(mmap["circuitutils"], "CircuitUtils.F90")
        self.assertEqual(mmap["circuitsmod"], "CircuitUtils.F90")
        self.assertEqual(mmap["circmatinitmod"], "CircuitUtils.F90")

    def test_module_procedure_excluded(self):
        fpath = os.path.join(self.tmpdir, "Interface.F90")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(
                "module MyModule\n"
                "  interface foo\n"
                "    module procedure sub_foo\n"
                "    module procedure func_foo\n"
                "  end interface\n"
                "end module MyModule\n"
            )
        metrics = MultilangMetrics(self.tmpdir)
        mmap = metrics._build_fortran_module_map()
        self.assertIn("mymodule", mmap)
        self.assertNotIn("procedure", mmap)

    def test_empty_directory(self):
        metrics = MultilangMetrics(self.tmpdir)
        mmap = metrics._build_fortran_module_map()
        self.assertEqual(len(mmap), 0)

    def test_case_insensitive_module(self):
        fpath = os.path.join(self.tmpdir, "DefUtils.F90")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("MODULE DefUtils\nEND MODULE DefUtils\n")
        metrics = MultilangMetrics(self.tmpdir)
        mmap = metrics._build_fortran_module_map()
        self.assertIn("defutils", mmap)

    def test_only_f90_scanned_not_f77(self):
        f90_path = os.path.join(self.tmpdir, "Solver.F90")
        with open(f90_path, "w", encoding="utf-8") as f:
            f.write("module Solver\nend module Solver\n")
        f77_path = os.path.join(self.tmpdir, "legacy.f")
        with open(f77_path, "w", encoding="utf-8") as f:
            f.write("      SUBROUTINE OLDSTYLE\n      END\n")
        metrics = MultilangMetrics(self.tmpdir)
        mmap = metrics._build_fortran_module_map()
        self.assertIn("solver", mmap)
        modules_from_f = [k for k, v in mmap.items() if v == "legacy.f"]
        self.assertEqual(len(modules_from_f), 0)


class TestFortranSubroutineMap(unittest.TestCase):
    """测试 _build_fortran_subroutine_map() 方法"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_subroutine_extraction_f90(self):
        fpath = os.path.join(self.tmpdir, "HeatSolve.F90")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("subroutine HeatSolver_init(Model, Solver, dt, Transient)\nend subroutine\n")
        metrics = MultilangMetrics(self.tmpdir)
        smap = metrics._build_fortran_subroutine_map()
        self.assertIn("heatsolver_init", smap)
        self.assertEqual(smap["heatsolver_init"], "HeatSolve.F90")

    def test_function_extraction(self):
        fpath = os.path.join(self.tmpdir, "Stress.F90")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("function CalculateStress(x, y) result(stress)\nend function\n")
        metrics = MultilangMetrics(self.tmpdir)
        smap = metrics._build_fortran_subroutine_map()
        self.assertIn("calculatestress", smap)

    def test_subroutine_in_f77(self):
        fpath = os.path.join(self.tmpdir, "solver.f")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("      SUBROUTINE SOLVE\n      END\n")
        metrics = MultilangMetrics(self.tmpdir)
        smap = metrics._build_fortran_subroutine_map()
        self.assertIn("solve", smap)
        self.assertEqual(smap["solve"], "solver.f")

    def test_recursive_pure_prefix(self):
        fpath = os.path.join(self.tmpdir, "Tree.F90")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(
                "recursive subroutine TraverseTree(node)\n"
                "end subroutine\n"
                "pure function add(a, b) result(c)\n"
                "end function\n"
            )
        metrics = MultilangMetrics(self.tmpdir)
        smap = metrics._build_fortran_subroutine_map()
        self.assertIn("traversetree", smap)
        self.assertIn("add", smap)

    def test_first_definition_wins(self):
        f1 = os.path.join(self.tmpdir, "Alpha.F90")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("subroutine init()\nend subroutine\n")
        f2 = os.path.join(self.tmpdir, "Beta.F90")
        with open(f2, "w", encoding="utf-8") as f:
            f.write("subroutine init()\nend subroutine\n")
        metrics = MultilangMetrics(self.tmpdir)
        smap = metrics._build_fortran_subroutine_map()
        self.assertIn("init", smap)
        self.assertIn(smap["init"], ["Alpha.F90", "Beta.F90"])


class TestFortranDependencyResolution(unittest.TestCase):
    """测试 Fortran 依赖边构建"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_use_resolved_to_module_map(self):
        feti = os.path.join(self.tmpdir, "Feti.F90")
        with open(feti, "w", encoding="utf-8") as f:
            f.write("module FetiSolve\nend module\n")
        solver = os.path.join(self.tmpdir, "Solver.F90")
        with open(solver, "w", encoding="utf-8") as f:
            f.write("module Solver\nuse FetiSolve\nend module\n")
        metrics = MultilangMetrics(self.tmpdir)
        has_edge = any(
            d == "Feti.F90" for s, d in metrics.graph.edges
            if s == "Solver.F90"
        )
        self.assertTrue(has_edge, "use FetiSolve should resolve to Feti.F90")

    def test_use_resolved_to_subroutine_map(self):
        heatsolve = os.path.join(self.tmpdir, "HeatSolve.F90")
        with open(heatsolve, "w", encoding="utf-8") as f:
            f.write("subroutine HeatSolver_init()\nend subroutine\n")
        caller = os.path.join(self.tmpdir, "Caller.F90")
        with open(caller, "w", encoding="utf-8") as f:
            f.write("module CallerMod\nuse HeatSolver_init\nend module\n")
        metrics = MultilangMetrics(self.tmpdir)
        smap = metrics._fortran_subroutine_map
        self.assertIn("heatsolver_init", smap)

    def test_call_resolved_to_subroutine_map(self):
        solver = os.path.join(self.tmpdir, "solver.f")
        with open(solver, "w", encoding="utf-8") as f:
            f.write("      SUBROUTINE SOLVE\n      END\n")
        caller = os.path.join(self.tmpdir, "main.f")
        with open(caller, "w", encoding="utf-8") as f:
            f.write("      CALL SOLVE\n      END\n")
        metrics = MultilangMetrics(self.tmpdir)
        has_edge = any(
            d == "solver.f" for s, d in metrics.graph.edges
            if s == "main.f"
        )
        self.assertTrue(has_edge, "call SOLVE should resolve to solver.f")

    def test_fallback_to_filename_match(self):
        defUtils = os.path.join(self.tmpdir, "DefUtils.F90")
        with open(defUtils, "w", encoding="utf-8") as f:
            f.write("module DefUtils\nend module\n")
        user = os.path.join(self.tmpdir, "User.F90")
        with open(user, "w", encoding="utf-8") as f:
            f.write("module UserMod\nuse DefUtils\nend module\n")
        metrics = MultilangMetrics(self.tmpdir)
        has_edge = any(
            d == "DefUtils.F90" for s, d in metrics.graph.edges
            if s == "User.F90"
        )
        self.assertTrue(has_edge, "use DefUtils should resolve to DefUtils.F90")

    def test_no_self_loop(self):
        defUtils = os.path.join(self.tmpdir, "DefUtils.F90")
        with open(defUtils, "w", encoding="utf-8") as f:
            f.write("module DefUtils\nuse DefUtils\nend module\n")
        metrics = MultilangMetrics(self.tmpdir)
        self_edges = [(s, d) for s, d in metrics.graph.edges if s == d]
        self.assertEqual(len(self_edges), 0, "use DefUtils in DefUtils.F90 should not create self-loop")

    def test_same_lang_cycle_with_mismatched_names(self):
        feti = os.path.join(self.tmpdir, "Feti.F90")
        with open(feti, "w", encoding="utf-8") as f:
            f.write("module FetiSolve\nuse SolverUtils\nend module\n")
        solver = os.path.join(self.tmpdir, "SolverUtils.F90")
        with open(solver, "w", encoding="utf-8") as f:
            f.write("module SolverUtils\nuse FetiSolve\nend module\n")
        metrics = MultilangMetrics(self.tmpdir)
        cycles = metrics.graph.detect_same_lang_cycles("fortran")
        self.assertTrue(len(cycles) > 0, "Should detect same-lang cycle between FetiSolve and SolverUtils")


class TestFortranMappingStats(unittest.TestCase):
    """测试映射命中率统计"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_mapping_hit_rate_in_result(self):
        defUtils = os.path.join(self.tmpdir, "DefUtils.F90")
        with open(defUtils, "w", encoding="utf-8") as f:
            f.write("module DefUtils\nend module\n")
        user = os.path.join(self.tmpdir, "User.F90")
        with open(user, "w", encoding="utf-8") as f:
            f.write("module UserMod\nuse DefUtils\nend module\n")
        metrics = MultilangMetrics(self.tmpdir)
        result = metrics.all_metrics()
        fm = result.get("fortran_mapping", {})
        self.assertEqual(fm["module_map_size"], 2)
        self.assertEqual(fm["use_total"], 1)
        self.assertEqual(fm["use_resolved"], 1)
        self.assertEqual(fm["use_hit_rate"], 1.0)

    def test_mapping_hit_rate_with_mismatch(self):
        feti = os.path.join(self.tmpdir, "Feti.F90")
        with open(feti, "w", encoding="utf-8") as f:
            f.write("module FetiSolve\nend module\n")
        user = os.path.join(self.tmpdir, "User.F90")
        with open(user, "w", encoding="utf-8") as f:
            f.write("module UserMod\nuse FetiSolve\nuse NonExistent\nend module\n")
        metrics = MultilangMetrics(self.tmpdir)
        fm = metrics.all_metrics().get("fortran_mapping", {})
        self.assertEqual(fm["use_total"], 2)
        self.assertEqual(fm["use_resolved"], 1)
        self.assertAlmostEqual(fm["use_hit_rate"], 0.5)

    def test_call_hit_rate_in_result(self):
        solver = os.path.join(self.tmpdir, "solver.f")
        with open(solver, "w", encoding="utf-8") as f:
            f.write("      SUBROUTINE SOLVE\n      END\n")
        caller = os.path.join(self.tmpdir, "main.f")
        with open(caller, "w", encoding="utf-8") as f:
            f.write("      CALL SOLVE\n      CALL UNKNOWN_SUB\n      END\n")
        metrics = MultilangMetrics(self.tmpdir)
        fm = metrics.all_metrics().get("fortran_mapping", {})
        self.assertEqual(fm["call_total"], 2)
        self.assertEqual(fm["call_resolved"], 1)
        self.assertAlmostEqual(fm["call_hit_rate"], 0.5)

    def test_no_fortran_files_default(self):
        hdr = os.path.join(self.tmpdir, "main.cpp")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write("int main() { return 0; }\n")
        metrics = MultilangMetrics(self.tmpdir)
        fm = metrics.all_metrics().get("fortran_mapping", {})
        self.assertEqual(fm["module_map_size"], 0)
        self.assertEqual(fm["use_total"], 0)
        self.assertEqual(fm["use_hit_rate"], 1.0)

    def test_elmerfem_mismatch_simulation(self):
        stress = os.path.join(self.tmpdir, "Stress.F90")
        with open(stress, "w", encoding="utf-8") as f:
            f.write("module StressLocal\nend module\n")
        feti = os.path.join(self.tmpdir, "Feti.F90")
        with open(feti, "w", encoding="utf-8") as f:
            f.write("module FetiSolve\nuse StressLocal\nend module\n")
        caller = os.path.join(self.tmpdir, "Caller.F90")
        with open(caller, "w", encoding="utf-8") as f:
            f.write("module CallerMod\nuse FetiSolve\nuse StressLocal\nend module\n")
        metrics = MultilangMetrics(self.tmpdir)
        mmap = metrics._fortran_module_map
        self.assertIn("fetisolve", mmap)
        self.assertEqual(mmap["fetisolve"], "Feti.F90")
        self.assertIn("stresslocal", mmap)
        self.assertEqual(mmap["stresslocal"], "Stress.F90")
        fm = metrics.all_metrics().get("fortran_mapping", {})
        self.assertEqual(fm["use_total"], 3)
        self.assertEqual(fm["use_resolved"], 3)
        self.assertEqual(fm["use_hit_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()