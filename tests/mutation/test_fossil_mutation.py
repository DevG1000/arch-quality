# -*- coding: utf-8 -*-
"""化石规则变异测试：最小改动应使规则翻转。"""

import os
import tempfile
import unittest

from arch_quality.arch_metrics_fossil_code import FossilCodeMetrics


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _rules(files):
    with tempfile.TemporaryDirectory() as d:
        for rel, text in files.items():
            _write(d, rel, text)
        return {v["rule"] for v in FossilCodeMetrics(d).check_fossil_rules()}


FOSSIL = "#include <memory>\nvoid f(){std::auto_ptr<int> p(new int(1));}\n"
CLONE = """double flux_a(double u, double v) {
  double a = u * v;
  double b = 0.5 * (u - v);
  double c = a + b;
  double d = c * c;
  double e = d + a;
  double f = e + b;
  double g = f * c;
  return g;
}
"""

CASES = [
    ("FOS-001-fixed-form", "FOS-001",
     {"a.f90": "program m\n  implicit none\nend program m\n"},
     {"a.f": "      PROGRAM L\n      IMPLICIT REAL*8 (A-H,O-Z)\n      END\n"}),
    ("FOS-002-deprecated", "FOS-002",
     {"a.cpp": "#include <memory>\nvoid f(){auto p=std::make_unique<int>(1);}\n"},
     {"a.cpp": FOSSIL}),
    ("FOS-004-unused", "FOS-004",
     {"a.cpp": FOSSIL + "static void legacy_init(){}\nint main(){legacy_init();}\n"},
     {"a.cpp": FOSSIL + "static void legacy_init(){}\n"}),
    ("FOS-005-unreachable", "FOS-005",
     {"a.cpp": FOSSIL + "void g(int m){if(m){work();}}\n"},
     {"a.cpp": FOSSIL + "#if 0\nold();\n#endif\n"}),
    ("FOS-007-clone", "FOS-007",
     {"a.cpp": FOSSIL + CLONE,
      "b.cpp": "double other(double a){return a*2.0;}\n"},
     {"a.cpp": FOSSIL + CLONE,
      "b.cpp": CLONE.replace("flux_a", "flux_b")}),
    ("FOS-010-todo", "FOS-010",
     {"a.cpp": FOSSIL},
     {"a.cpp": FOSSIL + "".join("// TODO x%d\n" % i for i in range(8))}),
]


class TestFossilMutation(unittest.TestCase):
    def test_rule_flips_on_mutation(self):
        for cid, rule, before, after in CASES:
            with self.subTest(case=cid):
                self.assertNotIn(rule, _rules(before), "%s: 改前不应触发" % cid)
                self.assertIn(rule, _rules(after), "%s: 改后应触发" % cid)


if __name__ == "__main__":
    unittest.main()
