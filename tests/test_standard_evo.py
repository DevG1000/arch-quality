"""
test_standard_evo.py — 标准架构质量 · 演进质量维度单元测试

对照指南 2.3 §6.1-6.7 算法，验证 6 子维度检测：
1. 历史可追溯性（Git 活跃度）
2. 技术债务趋势（历史对比）
3. 依赖过时程度（package.json / requirements.txt）
4. 废弃代码比例（备份文件/注释代码块）
5. 增量质量（平均提交大小）
6. 问题扣分（从结构/SAR 派生）

key 契约：git_activity/debt_trend/dep_outdated/dead_code/incremental/problems
N/A 语义：无 Git → None；无依赖清单 → None（权重按比例重分配）
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


class TestEvoQuality(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = self.tmp
        self.m = StandardMetrics(self.root)

    def _mk(self, rel, content=""):
        _write(os.path.join(self.tmp, rel), content)

    # 1. 历史可追溯性
    def test_git_activity_no_git(self):
        score, detail = self.m.calc_git_activity()
        self.assertIsNone(score)
        self.assertFalse(detail["has_git"])

    def test_git_activity_has_git(self):
        # 在临时目录初始化 git
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=self.tmp, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=self.tmp, capture_output=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=self.tmp, capture_output=True)
        self._mk("f.txt", "x\n")
        subprocess.run(["git", "add", "."], cwd=self.tmp, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.tmp, capture_output=True)
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_git_activity()
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 20)  # 至少"有 Git 仓库"基础分

    # 2. 技术债务趋势
    def test_debt_trend_no_baseline(self):
        score, detail = self.m.calc_debt_trend()
        self.assertEqual(score, 20)  # 无历史数据 → 仅基础分
        self.assertFalse(detail["has_baseline"])

    def test_debt_trend_with_baseline(self):
        # 写入 history.json 模拟历史数据
        import json
        hist_dir = os.path.join(self.tmp, ".opencode", "arch-reports")
        os.makedirs(hist_dir, exist_ok=True)
        _write(os.path.join(hist_dir, "history.json"),
               json.dumps([{"structural": 50, "date": "2026-08-01"}], ensure_ascii=False))
        # 当前项目得分 > 50 → improving
        self._mk("src/a.c", "int a(){return 0;}\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_debt_trend()
        self.assertTrue(detail["has_baseline"])
        self.assertIn("trend", detail)

    # 3. 依赖过时程度
    def test_dep_outdated_no_manifest(self):
        score, detail = self.m.calc_dep_outdated()
        self.assertIsNone(score)
        self.assertFalse(detail["has_manifest"])

    def test_dep_outdated_with_lock(self):
        self._mk("package.json", '{"dependencies": {"lodash": "^4.17.0"}}')
        self._mk("package-lock.json", "{}")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_dep_outdated()
        self.assertIsNotNone(score)
        self.assertTrue(detail["has_lock"])

    def test_dep_outdated_no_lock(self):
        self._mk("package.json", '{"dependencies": {"lodash": "^4.17.0"}}')
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_dep_outdated()
        self.assertIsNotNone(score)
        self.assertFalse(detail["has_lock"])
        self.assertLess(score, 100)  # 无 lock → 版本未锁定风险

    def test_dep_outdated_pyproject(self):
        # pyproject.toml 支持：识别 [project.dependencies] 与 optional-dependencies
        self._mk("pyproject.toml",
                 "[build-system]\n"
                 'requires = ["setuptools>=68"]\n'
                 "[project]\n"
                 "dependencies = [\"numpy>=1.20\", \"scipy<2.0\"]\n"
                 "[project.optional-dependencies]\n"
                 'dev = ["pytest>=7.0"]\n')
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_dep_outdated()
        self.assertIsNotNone(score)
        self.assertEqual(detail["manifest_type"], "pyproject.toml")
        self.assertGreaterEqual(detail["dep_total"], 3)  # numpy/scipy/pytest
        # 无 lock → 60 分
        self.assertEqual(score, 60)

    def test_dep_outdated_pyproject_with_uv_lock(self):
        self._mk("pyproject.toml",
                 "[project]\n"
                 "dependencies = [\"numpy>=1.20\"]\n")
        self._mk("uv.lock", "")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_dep_outdated()
        self.assertTrue(detail["has_lock"])
        self.assertEqual(score, 80)  # 有 lock → 版本固定

    # 4. 废弃代码
    def test_dead_code_clean(self):
        self._mk("src/a.c", "int a(){return 0;}\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_dead_code()
        self.assertEqual(score, 100)
        self.assertEqual(detail["backup_files"], 0)

    def test_dead_code_backup(self):
        self._mk("src/a.c", "int a(){return 0;}\n")
        self._mk("config.old.bak", "old config\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_dead_code()
        self.assertGreaterEqual(detail["backup_files"], 1)
        self.assertLess(score, 100)

    # 5. 增量质量
    def test_incremental_no_git(self):
        score, detail = self.m.calc_incremental_quality()
        self.assertIsNone(score)
        self.assertFalse(detail["has_git"])

    # 6. 问题扣分
    def test_problems_clean(self):
        self._mk("src/a.c", "int a(){return 0;}\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_problem_deduction()
        self.assertGreaterEqual(score, 90)

    def test_problems_low_test_coverage(self):
        self._mk("src/a.c", "int a(){return 0;}\n")
        self._mk("src/b.c", "int b(){return 1;}\n")
        self._mk("src/c.c", "int c(){return 2;}\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_problem_deduction()
        self.assertLess(score, 100)

    # 综合分 + N/A 重分配
    def test_evo_overall_all_na(self):
        # 无 Git、无依赖 → 仅 dead_code/problems 参与
        self._mk("src/a.c", "int a(){return 0;}\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_evolution_score()
        self.assertIsNotNone(score)
        self.assertIn("scores", detail)
        self.assertIsNone(detail["scores"]["git_activity"])
        self.assertIsNone(detail["scores"]["dep_outdated"])
        self.assertIsNone(detail["scores"]["incremental"])

    def test_evo_overall_keys(self):
        self._mk("src/a.c", "int a(){return 0;}\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_evolution_score()
        for k in ["git_activity", "debt_trend", "dep_outdated",
                  "dead_code", "incremental", "problems"]:
            self.assertIn(k, detail["scores"])


if __name__ == "__main__":
    unittest.main()