"""
test_standard_sar.py — 标准架构质量 · SAR 内置规则单元测试

对照指南 2.3 第七章（SAR-001~012）验证规则触发：
- 结构：SAR-001 模块化 / SAR-002 高耦合 / SAR-003 低内聚 / SAR-004 高复杂度 / SAR-005 测试不足
- 设计：SAR-006 God Class / SAR-007 Long Method / SAR-008 分层违反 / SAR-009 接口膨胀
- 文档：SAR-010 文档缺失
- 演进：SAR-011 依赖过时 / SAR-012 项目不活跃

关键语义：
- SAR 是唯一检测源，6.6 问题扣分由此派生
- output_level 与 severity 解耦
- N/A 守卫：无 Git/无依赖/无 OO 代码 → 对应规则跳过
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


class TestSarRules(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = self.tmp
        self.m = StandardMetrics(self.root)

    def _mk(self, rel, content=""):
        _write(os.path.join(self.tmp, rel), content)

    def _rules(self):
        self.m = StandardMetrics(self.root)
        return {v["rule"] for v in self.m.check_sar_rules()}

    # SAR-004 高复杂度
    def test_sar004_complexity(self):
        # 多个 >200 行文件 → 复杂度低 → 触发
        for i in range(3):
            self._mk(f"src/big{i}.c", "\n".join(f"// l{j}" for j in range(300)))
        self.m = StandardMetrics(self.root)
        rules = self._rules()
        self.assertIn("SAR-004", rules)
        self.assertNotIn("SAR-001", rules)  # 有文件，模块化不触发

    # SAR-005 测试覆盖不足
    def test_sar005_test_coverage(self):
        self._mk("src/a.c", "int a(){}\n")
        self.m = StandardMetrics(self.root)
        rules = self._rules()
        self.assertIn("SAR-005", rules)  # 无测试 → 覆盖不足

    # SAR-010 文档缺失
    def test_sar010_doc_missing(self):
        self._mk("src/a.c", "int a(){}\n")
        self.m = StandardMetrics(self.root)
        rules = self._rules()
        self.assertIn("SAR-010", rules)  # 无 README/CHANGELOG → 文档缺失

    # SAR-011 依赖过时（N/A 守卫：无清单不触发）
    def test_sar011_no_manifest_skip(self):
        self._mk("src/a.c", "int a(){}\n")
        self.m = StandardMetrics(self.root)
        rules = self._rules()
        self.assertNotIn("SAR-011", rules)  # 无依赖清单 → N/A 跳过

    # SAR-012 项目不活跃（N/A 守卫：无 Git 不触发）
    def test_sar012_no_git_skip(self):
        self._mk("src/a.c", "int a(){}\n")
        self.m = StandardMetrics(self.root)
        rules = self._rules()
        self.assertNotIn("SAR-012", rules)  # 无 Git → N/A 跳过

    # SAR 输出结构
    def test_sar_output_structure(self):
        self._mk("src/a.c", "int a(){}\n")
        self.m = StandardMetrics(self.root)
        violations = self.m.check_sar_rules()
        for v in violations:
            self.assertIn("rule", v)
            self.assertIn("name", v)
            self.assertIn("severity", v)
            self.assertIn("output_level", v)
            self.assertIn("count", v)
            self.assertIn("detail", v)
            # output_level 与 severity 解耦（合法值）
            self.assertIn(v["severity"], ("HIGH", "MEDIUM", "LOW", "INFO"))
            self.assertIn(v["output_level"], ("ERROR", "WARNING", "INFO"))

    # all_metrics 集成
    def test_sar_in_all_metrics(self):
        self._mk("src/a.c", "int a(){}\n")
        self.m = StandardMetrics(self.root)
        d = self.m.all_metrics()
        self.assertIn("sar_violations", d)
        self.assertIsInstance(d["sar_violations"], list)


if __name__ == "__main__":
    unittest.main()