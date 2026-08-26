"""
test_standard_design.py — 标准架构质量 · 设计质量维度单元测试

对照指南 2.3 §4.1-4.5 算法，验证 4 子维度检测：
1. SOLID 原则（S/O/L/I/D 五原则，置信度：中）
2. 设计模式（12 种正则模式，置信度：低）
3. 架构风格（6 种风格目录 + 依赖方向，置信度：中）
4. 反模式（God Class/Long Method/硬编码，从 100 扣）

key 契约：solid/patterns/style/anti_patterns（锁定）
关键语义：测试文件不计反模式；God Class 针对类而非文件
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


class TestDesignQuality(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = self.tmp
        self.m = StandardMetrics(self.root)

    def _mk(self, rel, content=""):
        _write(os.path.join(self.tmp, rel), content)

    # 1. SOLID
    def test_solid_no_oo(self):
        self._mk("src/main.c", "int main(){return 0;}\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_solid_score()
        self.assertIsNone(score)  # 无 OO 代码 → None
        self.assertEqual(detail["confidence"], "中")

    def test_solid_clean_class(self):
        self._mk("src/ok.py",
                 "class Service:\n"
                 "    def __init__(self, repo):\n"
                 "        self.repo = repo\n"
                 "    def run(self):\n"
                 "        return self.repo.get()\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_solid_score()
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_solid_keys(self):
        self._mk("src/a.py", "class A:\n    def __init__(self):\n        pass\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_solid_score()
        for k in ["s", "o", "l", "i", "d", "confidence"]:
            self.assertIn(k, detail)

    # 2. 设计模式
    def test_patterns_none(self):
        self._mk("src/a.c", "int a(){return 0;}\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_pattern_score()
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertEqual(detail["confidence"], "低")

    def test_patterns_singleton(self):
        self._mk("src/sing.py",
                 "class S:\n"
                 "    _instance = None\n"
                 "    def getInstance():\n"
                 "        return S._instance\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_pattern_score()
        self.assertIn("Singleton", detail["patterns"])

    # 3. 架构风格
    def test_style_none(self):
        self._mk("src/a.c", "int a(){return 0;}\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_style_score()
        self.assertGreaterEqual(score, 0)
        self.assertIn("confidence", detail)

    def test_style_layered(self):
        self._mk("src/controller/api.py", "def h():\n    pass\n")
        self._mk("src/service/biz.py", "def s():\n    pass\n")
        self._mk("src/repository/data.py", "def r():\n    pass\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_style_score()
        self.assertEqual(detail["style"], "layered")
        self.assertGreaterEqual(score, 60)

    # 4. 反模式
    def test_antipattern_clean(self):
        self._mk("src/a.py", "class A:\n    def f(self):\n        return 1\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_anti_pattern_score()
        self.assertEqual(score, 100)
        self.assertEqual(detail["god_class"], 0)

    def test_antipattern_test_file_excluded(self):
        # 测试文件即使很大也不计反模式
        body = "\n".join(f"    def test_{i}(self):\n        pass\n" for i in range(50))
        self._mk("tests/test_big.py",
                 f"class TestBig:\n{body}")
        self._mk("src/a.py", "class A:\n    def f(self):\n        return 1\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_anti_pattern_score()
        self.assertEqual(score, 100)
        self.assertEqual(detail["god_class"], 0)

    def test_antipattern_hardcode(self):
        self._mk("src/db.py",
                 'class DB:\n'
                 '    def conn(self):\n'
                 '        return "postgres://user:password@1.2.3.4:5432/db"\n')
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_anti_pattern_score()
        self.assertGreaterEqual(detail["hardcode"], 1)
        self.assertLess(score, 100)

    # 综合分 + key 契约
    def test_design_overall_keys(self):
        self._mk("src/a.py", "class A:\n    def f(self):\n        return 1\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_design_score()
        self.assertIsNotNone(score)
        for k in ["solid", "patterns", "style", "anti_patterns"]:
            self.assertIn(k, detail)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


if __name__ == "__main__":
    unittest.main()