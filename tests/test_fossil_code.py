# -*- coding: utf-8 -*-
"""化石代码维度单元测试：12 规则 + 检测/评分/豁免/非适用。"""

import os
import tempfile
import unittest

from arch_quality.arch_core import load_weights_from_skill
from arch_quality.arch_metrics_fossil_code import (
    FossilCodeMetrics, SKILL_PATH, DIMENSIONS,
)


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _rules(files):
    with tempfile.TemporaryDirectory() as d:
        for rel, text in files.items():
            _write(d, rel, text)
        m = FossilCodeMetrics(d)
        return {v["rule"] for v in m.check_fossil_rules()}


FOSSIL = "#include <memory>\nvoid f(){std::auto_ptr<int> p(new int(1));}\n"
CLONE_BODY = """double flux_a(double u, double v) {
  double a = u * v;
  double b = 0.5 * (u - v);
  double c = a + b;
  double d = c * c;
  double e = d + a;
  return e;
}
"""


class TestSkillWeights(unittest.TestCase):
    def test_weights_sum_100(self):
        w = load_weights_from_skill(SKILL_PATH)
        self.assertEqual(len(w), 4)
        self.assertAlmostEqual(sum(w.values()), 1.0, places=9)


class TestDetection(unittest.TestCase):
    def test_non_fossil(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "main.cpp", "int main(){return 0;}\n")
            m = FossilCodeMetrics(d)
            self.assertFalse(m._is_fossil)
            r = m.all_metrics()
            self.assertFalse(r["is_fossil"])
            self.assertIsNone(r["overall"])

    def test_legacy_fortran(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "legacy.f",
                   "      PROGRAM L\n"
                   "      IMPLICIT REAL*8 (A-H,O-Z)\n"
                   "      END\n")
            m = FossilCodeMetrics(d)
            self.assertTrue(m._is_fossil)
            self.assertIn("FOS-001", {v["rule"] for v in m.check_fossil_rules()})

    def test_deprecated_cpp(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "old.cpp", FOSSIL)
            m = FossilCodeMetrics(d)
            self.assertTrue(m._is_fossil)
            self.assertIn("FOS-002", {v["rule"] for v in m.check_fossil_rules()})


class TestRules(unittest.TestCase):
    def test_fos001_fixed_fortran(self):
        self.assertIn("FOS-001", _rules({
            "a.f": "      PROGRAM L\n      IMPLICIT REAL*8 (A-H,O-Z)\n      END\n"}))
        self.assertNotIn("FOS-001", _rules({
            "a.f90": "program m\n  implicit none\nend program m\n"}))

    def test_fos002_deprecated_api(self):
        self.assertIn("FOS-002", _rules({"a.cpp": FOSSIL}))
        self.assertNotIn("FOS-002", _rules({
            "a.cpp": "#include <memory>\nvoid f(){auto p=std::make_unique<int>(1);}\n"}))

    def test_fos003_kr_c(self):
        self.assertIn("FOS-003", _rules({
            "a.c": "int add(a,b)\nint a;\nint b;\n{return a+b;}\n"}))
        self.assertNotIn("FOS-003", _rules({
            "a.c": "int add(int a,int b){return a+b;}\n"}))

    def test_fos004_unused_static(self):
        self.assertIn("FOS-004", _rules({
            "a.cpp": FOSSIL + "static void legacy_init(){}\n"}))
        self.assertNotIn("FOS-004", _rules({
            "a.cpp": FOSSIL + "static void legacy_init(){}\n"
                     "int main(){legacy_init();return 0;}\n"}))

    def test_fos005_unreachable(self):
        self.assertIn("FOS-005", _rules({
            "a.cpp": FOSSIL + "#if 0\nold();\n#endif\n"}))
        self.assertNotIn("FOS-005", _rules({
            "a.cpp": FOSSIL + "void g(int mode){if(mode){work();}}\n"}))

    def test_fos006_block_comment(self):
        self.assertIn("FOS-006", _rules({
            "a.cpp": FOSSIL + "/*\nif (x) {\n old();\n}\n*/\n"}))
        self.assertNotIn("FOS-006", _rules({
            "a.cpp": FOSSIL + "/* Compute flux. */\n"}))

    def test_fos007_clone(self):
        body2 = CLONE_BODY.replace("flux_a", "flux_b").replace(
            "double u", "double x").replace("double v", "double y").replace(
            "u * v", "x * y").replace("(u - v)", "(x - y)")
        self.assertIn("FOS-007", _rules({
            "a.cpp": FOSSIL + CLONE_BODY,
            "b.cpp": body2}))
        self.assertNotIn("FOS-007", _rules({
            "a.cpp": FOSSIL + CLONE_BODY,
            "b.cpp": "double other(double a){return a*2.0;}\n"}))

    def test_fos008_duplicate_constant(self):
        self.assertIn("FOS-008", _rules({
            "a.cpp": FOSSIL + "const double K=0.85;\n",
            "b.cpp": "const double K=0.85;\n",
            "c.cpp": "const double K=0.85;\n"}))
        self.assertNotIn("FOS-008", _rules({
            "a.cpp": FOSSIL + "const double K=0.85;\n"}))

    def test_fos009_same_algorithm(self):
        body_a = ("void rk4(){ double a=1; double b=2; double c=a+b; "
                  "double d=c*c; double e=d+a; double f=e+b; return f; }\n")
        body_b = ("void rk4(){ double a=1; double b=2; double c=a-b; "
                  "if(a>b){c=c+a;} for(int i=0;i<3;i++){c=c+i;} "
                  "double d=c+c; double e=d-a; double f=e-b; return f; }\n")
        self.assertIn("FOS-009", _rules({
            "a.cpp": FOSSIL + body_a, "b.cpp": body_b}))
        self.assertNotIn("FOS-009", _rules({
            "a.cpp": FOSSIL + body_a.replace("rk4", "rk4_a"),
            "b.cpp": body_b.replace("rk4", "rk4_b")}))

    def test_fos010_todo_density(self):
        todos = "".join("// TODO item %d\n" % i for i in range(8))
        self.assertIn("FOS-010", _rules({"a.cpp": FOSSIL + todos}))
        self.assertNotIn("FOS-010", _rules({"a.cpp": FOSSIL}))

    def test_fos011_sqale_proxy(self):
        files = {"a.cpp": FOSSIL}
        for i in range(5):
            files["c%d.f" % i] = ("      PROGRAM L\n"
                                  "      IMPLICIT REAL*8 (A-H,O-Z)\n"
                                  "      END\n")
        self.assertIn("FOS-011", _rules(files))
        self.assertNotIn("FOS-011", _rules({"a.cpp": FOSSIL}))

    def test_fos012_legacy_untested(self):
        self.assertIn("FOS-012", _rules({
            "a.cpp": FOSSIL,
            "legacy/solver.cpp": "void solve(){}\n"}))
        self.assertNotIn("FOS-012", _rules({
            "a.cpp": FOSSIL,
            "modern/solver.cpp": "void solve(){}\n"}))


class TestScoringAndWaivers(unittest.TestCase):
    def test_score_legacy_only(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "legacy.f",
                   "      PROGRAM L\n"
                   "      IMPLICIT REAL*8 (A-H,O-Z)\n"
                   "      END\n")
            _write(d, "old.cpp", FOSSIL)
            r = FossilCodeMetrics(d).all_metrics()
            self.assertTrue(r["is_fossil"])
            self.assertEqual(r["dimensions"]["legacy"]["score"], 20)
            self.assertEqual(r["overall"], 76.0)
            self.assertEqual(r["gate_status"], "WARN")
            self.assertEqual(set(r["applicability_set"]), set(DIMENSIONS))

    def test_legacy_ok_waiver(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "old.cpp",
                   "/* @fossil_legacy_ok: ABI */\n" + FOSSIL)
            r = FossilCodeMetrics(d).all_metrics()
            self.assertNotIn("FOS-002", {v["rule"] for v in r["fossil_violations"]})
            self.assertEqual(r["waiver_audit"]["legacy_ok"]["count"], 1)

    def test_not_dead_waiver(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.cpp",
                   "/* @fossil_not_dead: FFI */\n" + FOSSIL +
                   "static void legacy_init(){}\n")
            r = FossilCodeMetrics(d).all_metrics()
            self.assertNotIn("FOS-004", {v["rule"] for v in r["fossil_violations"]})
            self.assertEqual(r["waiver_audit"]["not_dead"]["count"], 1)

    def test_invalid_waiver(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "old.cpp", "/* @fossil_legacy_ok */\n" + FOSSIL)
            r = FossilCodeMetrics(d).all_metrics()
            self.assertEqual(len(r["waiver_audit"]["invalid_waivers"]), 1)


if __name__ == "__main__":
    unittest.main()
