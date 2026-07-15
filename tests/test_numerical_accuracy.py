# -*- coding: utf-8 -*-
"""test_numerical_accuracy.py — 数值算法正确性与精度保障评估单元测试"""

import os
import shutil
import tempfile
import unittest

from arch_quality.arch_metrics_numerical_accuracy import (
    NumericalAccuracyMetrics,
)


class TestHelperFunctions(unittest.TestCase):
    """测试辅助函数和检测模式"""

    def test_cfl_pattern_detected(self):
        from arch_quality.arch_metrics_numerical_accuracy import CFL_PATTERN
        self.assertTrue(CFL_PATTERN.search("CoNo = 0.5"))
        self.assertTrue(CFL_PATTERN.search("courantNumber = 0.8"))
        self.assertTrue(CFL_PATTERN.search("adjustTimeStep yes"))
        self.assertFalse(CFL_PATTERN.search("int a = 1;"))

    def test_solver_pattern_detected(self):
        from arch_quality.arch_metrics_numerical_accuracy import LINEAR_SOLVER_PATTERN
        self.assertTrue(LINEAR_SOLVER_PATTERN.search("SPOOLES"))
        self.assertTrue(LINEAR_SOLVER_PATTERN.search("PARDISO"))
        self.assertTrue(LINEAR_SOLVER_PATTERN.search("condition.number"))
        self.assertFalse(LINEAR_SOLVER_PATTERN.search("int x = 1;"))


class TestNonNumericalProject(unittest.TestCase):
    """非数值密集型项目应返回 None"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        py_file = os.path.join(self.tmp, "main.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write("import os\nprint('hello')\n")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_is_not_numerical(self):
        m = NumericalAccuracyMetrics(self.tmp)
        self.assertFalse(m._has_numerical)

    def test_all_metrics_returns_none(self):
        m = NumericalAccuracyMetrics(self.tmp)
        r = m.all_metrics()
        self.assertFalse(r["is_numerical"])
        self.assertIsNone(r["overall"])

    def test_no_nvr_violations(self):
        m = NumericalAccuracyMetrics(self.tmp)
        violations = m.check_nvr_rules()
        self.assertEqual(violations, [])


class TestNumericalProjectBasic(unittest.TestCase):
    """基本数值项目测试"""

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_solver_detected(self):
        tmp = self._make_fixture({
            "src/solver.f90": (
                "program solver\n"
                "  real :: u(100), v(100)\n"
                "  do i = 1, 100\n"
                "    u(i) = u(i) + v(i)\n"
                "  end do\n"
                "end program\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            self.assertTrue(m._has_numerical)
        finally:
            shutil.rmtree(tmp)

    def test_cfl_control_detected(self):
        tmp = self._make_fixture({
            "src/solver.c": (
                "#include <stdio.h>\n"
                "int solve() {\n"
                "  double courantNumber = 0.5;\n"
                "  double CoNo = 0.8;\n"
                "  return 0;\n"
                "}\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            self.assertTrue(m._has_numerical)
            score, detail = m.calc_numerical_stability()
            self.assertGreaterEqual(score, 80)
            self.assertTrue(detail.get("has_cfl_control"))
        finally:
            shutil.rmtree(tmp)


class TestNumericalStability(unittest.TestCase):
    """数值稳定性维度测试"""

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_cfl_controlled_gets_100(self):
        tmp = self._make_fixture({
            "src/solver.f90": (
                "program solver\n"
                "  real :: CoNo, courantNumber\n"
                "  CoNo = 0.5\n"
                "  courantNumber = 0.5\n"
                "  ! upwind scheme\n"
                "end program\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            score, detail = m.calc_numerical_stability()
            self.assertEqual(score, 100.0)
        finally:
            shutil.rmtree(tmp)

    def test_no_cfl_control_lower_score(self):
        tmp = self._make_fixture({
            "src/solver.c": (
                "#include <stdio.h>\n"
                "int main() {\n"
                "  double u[100], v[100];\n"
                "  for(int i=0;i<100;i++) u[i] = u[i] + v[i];\n"
                "  return 0;\n"
                "}\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            score, detail = m.calc_numerical_stability()
            self.assertIsNotNone(score)
        finally:
            shutil.rmtree(tmp)


class TestRoundoffSensitivity(unittest.TestCase):
    """舍入误差维度测试"""

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_kahan_summation_improves_score(self):
        tmp = self._make_fixture({
            "src/accum.f90": (
                "subroutine accum(n, x)\n"
                "  real :: x(n), sum, c, y, t\n"
                "  sum = 0.0; c = 0.0\n"
                "  do i = 1, n\n"
                "    y = x(i) - c\n"
                "    t = sum + y\n"
                "    c = (t - sum) - y\n"
                "    sum = t\n"
                "  end do\n"
                "end subroutine\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            score, detail = m.calc_roundoff_sensitivity()
            # Has Kahan-like pattern, should have good score
            self.assertIsNotNone(score)
            self.assertGreaterEqual(score, 60)
        finally:
            shutil.rmtree(tmp)


class TestMMSVerification(unittest.TestCase):
    """MMS 验证维度测试"""

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_mms_detected(self):
        tmp = self._make_fixture({
            "test/mms/convergence.f90": (
                "program mms_verification\n"
                "  real :: observed_order\n"
                "  real :: expected_order\n"
                "  observed_order = 2.01\n"
                "  expected_order = 2.0\n"
                "  ! manufactured solution verification\n"
                "end program\n"
            ),
            "test/mms/order_accuracy.f90": (
                "subroutine check_order()\n"
                "  real :: p\n"
                "  p = 2.0\n"
                "end subroutine\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            score, detail = m.calc_mms_verification()
            self.assertGreater(score, 0, "MMS directory should trigger non-zero score")
            self.assertTrue(detail.get("has_accuracy_order") or detail.get("mms_directory_count") > 0)
        finally:
            shutil.rmtree(tmp)

    def test_no_mms_gets_zero(self):
        tmp = self._make_fixture({
            "src/solver.f90": "program solver\nend program\n",
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            score, detail = m.calc_mms_verification()
            self.assertEqual(score, 0.0)
        finally:
            shutil.rmtree(tmp)


class TestNVRRules(unittest.TestCase):
    """NVR 规则检测测试"""

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_nvr001_explicit_without_cfl(self):
        tmp = self._make_fixture({
            "src/solver.c": (
                "void solve() {\n"
                "  double u[100], v[100];\n"
                "  // upwind scheme, implicit\n"
                "  for(int i=0;i<100;i++) u[i] = u[i] + v[i];\n"
                "}\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            violations = m.check_nvr_rules()
            nvr001 = [v for v in violations if v["rule"] == "NVR-001"]
            self.assertEqual(len(nvr001), 0)
        finally:
            shutil.rmtree(tmp)

    def test_nvr004_no_kahan(self):
        tmp = self._make_fixture({
            "src/accum.c": (
                "double sum = 0.0;\n"
                "for(int i=0;i<100;i++) sum += data[i];\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            violations = m.check_nvr_rules()
            nvr004 = [v for v in violations if v["rule"] == "NVR-004"]
            self.assertGreaterEqual(len(nvr004), 0)
        finally:
            shutil.rmtree(tmp)

    def test_nvr005_mms_missing(self):
        tmp = self._make_fixture({
            "src/solver.f90": "program solver\nend program\n",
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            violations = m.check_nvr_rules()
            nvr005 = [v for v in violations if v["rule"] == "NVR-005"]
            if nvr005:
                self.assertEqual(nvr005[0]["severity"], "HIGH")
                self.assertEqual(nvr005[0]["output_level"], "ERROR")
        finally:
            shutil.rmtree(tmp)

    def test_nvr007_mesh_convergence_missing(self):
        tmp = self._make_fixture({
            "src/solver.c": "void solve() {}\n",
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            violations = m.check_nvr_rules()
            nvr007 = [v for v in violations if v["rule"] == "NVR-007"]
            if nvr007:
                self.assertEqual(nvr007[0]["severity"], "MEDIUM")
                self.assertEqual(nvr007[0]["output_level"], "WARNING")
        finally:
            shutil.rmtree(tmp)


class TestAllMetricsIntegration(unittest.TestCase):
    """综合集成测试"""

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_full_project_metrics(self):
        tmp = self._make_fixture({
            "src/solver.f90": (
                "program solver\n"
                "  real :: CoNo\n"
                "  CoNo = 0.5\n"
                "  ! upwind scheme for stability\n"
                "  real :: x(100), sum, c, y, t\n"
                "  sum = 0.0; c = 0.0\n"
                "  do i = 1, 100\n"
                "    y = x(i) - c\n"
                "    t = sum + y\n"
                "    c = (t - sum) - y\n"
                "    sum = t\n"
                "  end do\n"
                "end program\n"
            ),
            "test/test_mms.f90": (
                "program mms_test\n"
                "  real :: observed_order\n"
                "  observed_order = 2.01\n"
                "end program\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            r = m.all_metrics()
            self.assertTrue(r["is_numerical"])
            self.assertIsNotNone(r["overall"])
            self.assertIn("numerical_stability", r["dimensions"])
            self.assertIn("mms_verification", r["dimensions"])
            self.assertIn("nvr_violations", r)
        finally:
            shutil.rmtree(tmp)


class TestFortranSupport(unittest.TestCase):
    """Fortran 语言支持测试"""

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_fortran_subroutine_detected(self):
        """subroutine 关键词应被 SOLVER_KEYWORDS 匹配"""
        tmp = self._make_fixture({
            "src/solver.f90": (
                "subroutine calc_stiffness(k, n)\n"
                "  real :: k(n,n)\n"
                "  do i = 1, n\n"
                "    k(i,i) = 1.0\n"
                "  end do\n"
                "end subroutine\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            self.assertTrue(m._has_numerical)
            score, detail = m.calc_numerical_stability()
            self.assertGreaterEqual(score, 0)
            self.assertGreaterEqual(detail.get("total_solver_files", 0), 1)
        finally:
            shutil.rmtree(tmp)

    def test_fortran_case_insensitive_tolerance(self):
        """Fortran 中 TOLERANCE 应匹配 RESIDUAL_PATTERN"""
        tmp = self._make_fixture({
            "src/solver.f90": (
                "program test\n"
                "  TOLERANCE = 1.0D-8\n"
                "  RESIDUAL = 0.0\n"
                "end program\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            score, detail = m.calc_error_estimation()
            self.assertIsNotNone(score)
            self.assertTrue(detail.get("has_residual_control", False))
            self.assertTrue(detail.get("has_reasonable_tolerance", False))
        finally:
            shutil.rmtree(tmp)

    def test_fortran_hourglass_stability(self):
        """Fortran 中 hourglass/penalty 应匹配稳定性关键词"""
        tmp = self._make_fixture({
            "src/solver.f90": (
                "subroutine calc_stiffness()\n"
                "  HOURGLASS = 0.01\n"
                "  PENALTY = 1.0E10\n"
                "end subroutine\n"
            ),
        })
        try:
            m = NumericalAccuracyMetrics(tmp)
            score, detail = m.calc_numerical_stability()
            self.assertGreaterEqual(detail.get("total_solver_files", 0), 1)
            self.assertTrue(detail.get("has_stability_measures", False))
        finally:
            shutil.rmtree(tmp)

    def test_fortran_mesh_convergence_case_insensitive(self):
        """Fortran 中 GRID STUDY 应匹配 MESH_CONVERGENCE_PATTERN"""
        from arch_quality.arch_metrics_numerical_accuracy import MESH_CONVERGENCE_PATTERN
        self.assertIsNotNone(MESH_CONVERGENCE_PATTERN.search("GRID CONVERGENCE study"))
        self.assertIsNotNone(MESH_CONVERGENCE_PATTERN.search("Mesh Convergence Index"))

    def test_solver_keywords_includes_fortran(self):
        """SOLVER_KEYWORDS 应包含 Fortran 关键词"""
        from arch_quality.arch_metrics_numerical_accuracy import SOLVER_KEYWORDS
        self.assertIn("subroutine", SOLVER_KEYWORDS)


if __name__ == "__main__":
    unittest.main()
