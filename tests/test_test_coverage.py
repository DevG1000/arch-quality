"""
test_test_coverage.py — 测试覆盖度（test_coverage）4 层评分单元测试

覆盖 6 个用例：
1. 无测试文件 → score=0, binding_score=0
2. 全覆盖（每语言+每目录+文件比达标）→ score 高
3. 部分语言覆盖（C++ 有测试、Python 无测试）→ L2 语言覆盖 < 100%
4. 绑定层覆盖（pybind11 .def() 绑定有对应测试）→ L4 > 0
5. out-of-tree 测试根目录配置 → 声明的外置 tests 树计入测试
6. 单语言项目 → L4 权重按比例并入 L1-L3

验证 StandardMetrics.calc_test_coverage() 返回的 (score, detail)。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from arch_quality.arch_metrics_standard import StandardMetrics


def _write(path, content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class TestTestCoverage(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = self.tmp

    def _mk(self, rel, content=""):
        _write(os.path.join(self.tmp, rel), content)

    def _score(self, **kw):
        m = StandardMetrics(self.tmp, **kw)
        return m.calc_test_coverage()

    # 1. 无测试文件
    def test_no_test_files(self):
        self._mk("src/main.c", "int main() { return 0; }\n")
        self._mk("src/util.c", "int util() { return 1; }\n")
        score, detail = self._score()
        self.assertEqual(score, 0)
        self.assertEqual(detail["binding_score"], 0)
        self.assertEqual(detail["test_files_by_lang"], {})

    # 2. 全覆盖：每目录、文件比达标（单语言，L4 权重并入 L1-L3 → 可接近满分）
    def test_full_coverage(self):
        self._mk("src/main.c", "int main(){}\n")
        self._mk("src/util.c", "int u(){}\n")
        self._mk("src/mod.c", "int f(){}\n")
        self._mk("tests/test_main.c", "void t(){}\n")
        self._mk("tests/test_mod.c", "void t(){}\n")
        # 使文件比达标: 测试文件数 >= ceil(3*0.3)=1，已有 2 个 → 达标
        score, detail = self._score()
        self.assertGreater(score, 80)
        self.assertEqual(detail["lang_coverage"], 1.0)
        self.assertEqual(detail["dir_coverage"], 1.0)

    # 3. 部分语言覆盖：C++ 有测试，Python 无测试
    def test_partial_language_coverage(self):
        self._mk("src/a.cpp", "int a(){}\n")
        self._mk("src/b.py", "def b(): pass\n")
        self._mk("tests/test_a.cpp", "void t(){}\n")
        score, detail = self._score()
        # 2 语言，仅 1 语言有测试
        self.assertEqual(detail["lang_coverage"], 0.5)
        self.assertEqual(detail["lang_score"], 50.0)

    # 4. 绑定层覆盖：pybind11 .def() 绑定有对应测试
    def test_binding_test_coverage(self):
        self._mk("src/mod.cpp",
                 '#include <pybind11/pybind11.h>\n'
                 'PYBIND11_MODULE(mymod, m) {\n'
                 '  m.def("Add", &add);\n'
                 '  m.def("Mul", &mul);\n'
                 '}\n')
        self._mk("src/helper.py", "def x(): pass\n")
        # 测试文件引用 "Add" 但不引用 "Mul"
        self._mk("tests/test_mod.py", "import mymod\nmymod.Add(1,2)\n")
        score, detail = self._score()
        self.assertTrue(detail["is_multilang"])
        self.assertGreater(detail["binding_score"], 0)
        self.assertLess(detail["binding_coverage"], 1.0)

    # 5. out-of-tree 测试根目录配置
    def test_out_of_tree_test_dirs(self):
        self._mk("src/main.c", "int main(){}\n")
        self._mk("src/util.c", "int u(){}\n")
        # 未配置 test_dirs 时，外置 tests 树不计入测试
        score0, detail0 = self._score()
        self.assertEqual(score0, 0)
        # 配置 test_dirs=["tutorials"] 后，tutorials/ 下文件计入测试
        self._mk("tutorials/ex1.c", "int e1(){}\n")
        score1, detail1 = self._score(test_dirs=["tutorials"])
        self.assertGreater(score1, score0)
        self.assertIn("c", detail1["test_files_by_lang"])

    # 6. 单语言项目：L4 权重并入 L1-L3
    def test_single_language_redistribution(self):
        self._mk("src/main.c", "int main(){}\n")
        self._mk("src/util.c", "int u(){}\n")
        self._mk("src/mod.c", "int m(){}\n")
        self._mk("tests/test_main.c", "void t(){}\n")
        score, detail = self._score()
        self.assertFalse(detail["is_multilang"])
        self.assertEqual(detail["binding_score"], 0)
        # 单语言总分应按 L1×0.375 + L2×0.3125 + L3×0.3125
        expected = (detail["dir_score"] * 0.375
                    + detail["lang_score"] * 0.3125
                    + detail["file_score"] * 0.3125)
        self.assertAlmostEqual(score, expected, places=1)



    # 7. 模块级部分覆盖（对齐案例集1.3版 1.5 案例：20源码目录仅9有对应测试 → L1=45%）
    def test_module_level_partial_dir_coverage(self):
        for i in range(20):
            self._mk(f"src/mod{i}/file{i}.c", "int f(){ return 0; }\n")
        for i in range(9):
            self._mk(f"tests/mod{i}/test_mod{i}.c", "void t(){}\n")
        score, detail = self._score()
        self.assertAlmostEqual(detail["dir_coverage"], 0.45, places=2)
        # 多语言项目（单语言 c）按单语言权重
        self.assertFalse(detail["is_multilang"])

    # 8. 模块级全覆盖（对齐案例集1.3版 1.7 案例：所有源码目录有对应测试 → 无告警）
    def test_module_level_full_dir_coverage(self):
        for i in range(10):
            self._mk(f"src/mod{i}/file{i}.c", "int f(){ return 0; }\n")
            self._mk(f"tests/mod{i}/test_mod{i}.c", "void t(){}\n")
        score, detail = self._score()
        self.assertEqual(detail["dir_coverage"], 1.0)
        self.assertGreater(score, 90)


if __name__ == "__main__":
    unittest.main()
