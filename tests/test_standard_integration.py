"""
test_standard_integration.py — StandardMetrics 集成 + E2E 测试

验证组件间交互（对齐开发指南 §B2.5）：
1. 权重解析集成 — skill 权重与 StandardMetrics 使用一致
2. 报告合并集成 — ComprehensiveReport 正确合并 4 维度评分
3. SAR 合并集成 — SAR 违规正确追加到 mlr_violations
4. N/A 权重重分配 — 无 Git/无依赖清单/无 OO 代码时各维度权重按比例重分配
5. key 契约 — solid/patterns/style/anti_patterns + doc + evo 各子维度 key 锁定
6. E2E — all_metrics() 输出结构完整、CLI JSON 可序列化

使用合成项目，不依赖外部仓库。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arch_quality.arch_core import load_weights_from_skill
from arch_quality.arch_report import ComprehensiveReport
from arch_quality.arch_metrics_standard import StandardMetrics

SKILL_FILE = os.path.join(os.path.dirname(__file__), '..', 'src',
                          'arch_quality', 'skills', 'arch-quality.md')


def _write_tree(root, files: dict):
    for path, content in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


def _make_standard_project():
    """创建标准质量合成项目（完整文档/测试/代码）"""
    tmp = tempfile.mkdtemp()
    _write_tree(tmp, {
        "README.md": "# Proj\n## 安装\n## 使用\n## 功能\n",
        "CHANGELOG.md": "# Changelog\n## [1.0.0] - 2026-08-21\n### Added\n- x\n",
        "docs/architecture.md": "# Arch\n## 目录结构\n## 模块职责\n## 数据流\n## 依赖关系\n## 设计决策\n",
        "src/service.py": "class Service:\n    def __init__(self, repo):\n        self.repo = repo\n    def get(self):\n        return self.repo.find()\n",
        "src/util.c": "int util(){return 0;}\n",
        "tests/test_service.py": "def test_get():\n    assert True\n",
        "tests/test_util.c": "void test() {}\n",
    })
    return tmp


class TestWeightParsingIntegration(unittest.TestCase):
    """权重解析集成"""

    def test_skill_weights_parsed(self):
        weights = load_weights_from_skill(SKILL_FILE)
        # 主权重
        self.assertIn("结构质量", weights)
        self.assertIn("设计质量", weights)
        self.assertIn("文档质量", weights)
        self.assertIn("演进质量", weights)
        # 设计质量权重对齐指南 4.5
        self.assertEqual(weights.get("设计模式"), 0.15)
        self.assertEqual(weights.get("反模式"), 0.25)

    def test_metrics_uses_skill_weights(self):
        tmp = _make_standard_project()
        try:
            m = StandardMetrics(tmp)
            skill_weights = load_weights_from_skill(SKILL_FILE)
            for dim_key, metric_weight in m.weights["main"].items():
                self.assertIn(dim_key, skill_weights)
                self.assertAlmostEqual(metric_weight, skill_weights[dim_key])
        finally:
            shutil.rmtree(tmp)

    def test_weights_sum_to_one(self):
        tmp = _make_standard_project()
        try:
            m = StandardMetrics(tmp)
            for layer in ["main", "structural", "design", "doc", "evolution"]:
                total = sum(m.weights[layer].values())
                self.assertAlmostEqual(total, 1.0, places=4,
                                       msg=f"layer {layer} 权重和 != 1.0")
        finally:
            shutil.rmtree(tmp)


class TestReportMergeIntegration(unittest.TestCase):
    """报告合并集成"""

    def test_comprehensive_report_4_dimensions(self):
        tmp = _make_standard_project()
        try:
            r = ComprehensiveReport(tmp)
            d = r.generate()
            dims = d["dimensions"]
            for key in ["structural", "design", "documentation", "evolution"]:
                self.assertIn(key, dims)
                self.assertIsNotNone(dims[key].get("score"))
        finally:
            shutil.rmtree(tmp)

    def test_sar_merged_to_violations(self):
        tmp = tempfile.mkdtemp()
        try:
            # 全新临时目录，只放一个无测试无文档的源码文件 → 触发 SAR-005/010
            _write_tree(tmp, {"src/a.c": "int a(){return 0;}\n"})
            r = ComprehensiveReport(tmp)
            d = r.generate()
            sar_in_report = [v for v in d["mlr_violations"]
                             if v["rule"].startswith("SAR")]
            self.assertGreaterEqual(len(sar_in_report), 1)
            for v in sar_in_report:
                self.assertIn("severity", v)
                self.assertIn("output_level", v)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestKeyContract(unittest.TestCase):
    """key 契约锁定（防报告静默 0 分）"""

    def test_design_keys(self):
        tmp = _make_standard_project()
        try:
            m = StandardMetrics(tmp)
            d = m.all_metrics()
            details = d["design"]["details"]
            for k in ["solid", "patterns", "style", "anti_patterns"]:
                self.assertIn(k, details)
        finally:
            shutil.rmtree(tmp)

    def test_doc_keys(self):
        tmp = _make_standard_project()
        try:
            m = StandardMetrics(tmp)
            d = m.all_metrics()
            details = d["documentation"]["details"]
            for k in ["readme", "changelog", "adr", "comments", "jsdoc", "arch_doc"]:
                self.assertIn(k, details)
        finally:
            shutil.rmtree(tmp)

    def test_evo_keys(self):
        tmp = _make_standard_project()
        try:
            m = StandardMetrics(tmp)
            d = m.all_metrics()
            scores = d["evolution"]["details"]["scores"]
            for k in ["git_activity", "debt_trend", "dep_outdated",
                      "dead_code", "incremental", "problems"]:
                self.assertIn(k, scores)
        finally:
            shutil.rmtree(tmp)


class TestNARedistribution(unittest.TestCase):
    """N/A 权重重分配（0/1/2/3 N/A 组合）"""

    def _score_only_na(self, files):
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, files)
            m = StandardMetrics(tmp)
            return m.calc_evolution_score(), m.calc_design_score()
        finally:
            shutil.rmtree(tmp)

    def test_all_na_evolution(self):
        # 纯 C 项目：无 Git/无依赖/无 OO → git/dep/incremental/solid 全 None
        evo, design = self._score_only_na({"src/a.c": "int a(){return 0;}\n"})
        evo_score, evo_detail = evo
        self.assertIsNotNone(evo_score)  # dead_code + problems 参与
        self.assertIsNone(evo_detail["scores"]["git_activity"])
        self.assertIsNone(evo_detail["scores"]["dep_outdated"])
        self.assertIsNone(evo_detail["scores"]["incremental"])

        design_score, design_detail = design
        # 纯 C → SOLID None（无 OO），但 patterns/style/anti 参与
        self.assertIsNotNone(design_score)
        self.assertIsNone(design_detail["solid"])

    def test_partial_na(self):
        # 有 Git 无依赖的项目（模拟有 git 的临时仓库）
        tmp = tempfile.mkdtemp()
        try:
            _write_tree(tmp, {"src/a.py": "class A:\n    pass\n"})
            subprocess.run(["git", "init", "-q"], cwd=tmp, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"],
                           cwd=tmp, capture_output=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=tmp, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=tmp, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=tmp, capture_output=True)
            m = StandardMetrics(tmp)
            evo = m.calc_evolution_score()
            # git_activity/incremental 参与，dep_outdated 仍 None
            self.assertIsNotNone(evo[1]["scores"]["git_activity"])
            self.assertIsNotNone(evo[1]["scores"]["incremental"])
            self.assertIsNone(evo[1]["scores"]["dep_outdated"])
        finally:
            # git 对象文件在 Windows 可能被锁，清理前先删 .git
            git_dir = os.path.join(tmp, ".git")
            if os.path.isdir(git_dir):
                shutil.rmtree(git_dir, ignore_errors=True)
            shutil.rmtree(tmp, ignore_errors=True)


class TestE2E(unittest.TestCase):
    """端到端：输出结构完整、CLI 可序列化"""

    def test_all_metrics_structure(self):
        tmp = _make_standard_project()
        try:
            m = StandardMetrics(tmp)
            d = m.all_metrics()
            # 顶层字段
            for key in ["overall", "structural", "design", "documentation",
                        "evolution", "files", "sar_violations"]:
                self.assertIn(key, d)
            # 评分范围
            self.assertIsInstance(d["overall"], (int, float))
            self.assertTrue(0 <= d["overall"] <= 100)
            # sar_violations 结构
            for v in d["sar_violations"]:
                for k in ["rule", "name", "severity", "output_level", "count", "detail"]:
                    self.assertIn(k, v)
        finally:
            shutil.rmtree(tmp)

    def test_cli_json_output(self):
        tmp = _make_standard_project()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "arch_quality", tmp, "--json"],
                capture_output=True, text=True, encoding="utf-8",
                cwd=os.path.join(os.path.dirname(__file__), '..'),
                timeout=120,
            )
            # CLI 可能输出 JSON + 报告路径，解析第一段 JSON
            out = result.stdout
            # 找到 JSON 起点
            json_start = out.find("{")
            self.assertNotEqual(json_start, -1)
            data = json.loads(out[json_start:out.rfind("}") + 1])
            self.assertIn("overall_score", data)
            self.assertIn("dimensions", data)
            for k in ["structural", "design", "documentation", "evolution"]:
                self.assertIn(k, data["dimensions"])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()