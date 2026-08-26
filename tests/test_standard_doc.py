"""
test_standard_doc.py — 标准架构质量 · 文档质量维度单元测试

对照指南 2.3 §5.1-5.7 算法，验证 6 子维度检测：
1. README 完整性（7 项章节关键词）
2. CHANGELOG 完整性（版本号/日期/变更分类）
3. ADR 覆盖率（模板存在 + 记录数）
4. 代码注释密度（15-25% 健康区间）
5. JSDoc 覆盖率（公共 API 文档）
6. 架构文档完整性（6 项章节）

key 契约：readme/changelog/adr/comments/jsdoc/arch_doc（锁定）
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


class TestDocQuality(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = self.tmp
        self.m = StandardMetrics(self.root)

    def _mk(self, rel, content=""):
        _write(os.path.join(self.tmp, rel), content)

    def _recalc(self):
        self.m = StandardMetrics(self.root)
        return self.m.calc_doc_score()

    # 1. README 完整性
    def test_readme_missing(self):
        score, detail = self.m.calc_readme_score()
        self.assertEqual(score, 0)
        self.assertFalse(detail["exists"])

    def test_readme_full_sections(self):
        self._mk("README.md", "# Proj\n## 安装\n## 使用\n## 功能\n## 配置\n## 贡献\n## 简介\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_readme_score()
        self.assertEqual(score, 100)
        self.assertEqual(len(detail["sections"]), 6)

    def test_readme_partial(self):
        self._mk("README.md", "# Proj\n### 安装\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_readme_score()
        self.assertEqual(score, 35)  # 存在20 + 安装15

    # 2. CHANGELOG 完整性
    def test_changelog_missing(self):
        score, detail = self.m.calc_changelog_score()
        self.assertEqual(score, 0)
        self.assertFalse(detail["exists"])

    def test_changelog_complete(self):
        self._mk("CHANGELOG.md",
                 "# Changelog\n## [1.0.0] - 2026-08-21\n### Added\n- feature\n")
        score, detail = self.m.calc_changelog_score()
        self.assertEqual(score, 100)  # 存在30 + 版本20 + 日期20 + 分类30
        self.assertTrue(detail["has_version"])
        self.assertTrue(detail["has_date"])
        self.assertIn("Added", detail["categories"])

    # 3. ADR 覆盖率
    def test_adr_none(self):
        score, detail = self.m.calc_adr_score()
        self.assertEqual(score, 0)
        self.assertFalse(detail["has_template"])
        self.assertEqual(detail["adr_count"], 0)

    def test_adr_with_records(self):
        for i in range(3):
            self._mk(f"docs/adr/00{i}-decision.md", "# ADR-00%d\n" % i)
        score, detail = self.m.calc_adr_score()
        self.assertEqual(detail["adr_count"], 3)
        self.assertGreater(score, 40)  # 无模板但记录>0 → 覆盖分

    def test_adr_with_template(self):
        self._mk(".opencode/templates/adr.md", "# ADR Template\n")
        score, detail = self.m.calc_adr_score()
        self.assertTrue(detail["has_template"])
        self.assertGreaterEqual(score, 40)

    # 4. 注释密度（依赖 FileIndex，需重建）
    def test_comment_density_ideal(self):
        # 20 行代码，4 行注释 = 20% (健康区间)
        code = "\n".join(f"int f{i}() {{ return {i}; }}" for i in range(16))
        comments = "\n".join(f"// comment {i}" for i in range(4))
        self._mk("src/main.c", code + "\n" + comments + "\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_comment_density()
        self.assertEqual(score, 100)
        self.assertGreaterEqual(detail["ratio"], 0.15)
        self.assertLessEqual(detail["ratio"], 0.25)

    def test_comment_density_none(self):
        self._mk("src/main.c", "\n".join("int x%d;" % i for i in range(20)))
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_comment_density()
        self.assertLess(score, 60)

    # 5. JSDoc 覆盖率（依赖 FileIndex，需重建）
    def test_jsdoc_no_public_api(self):
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_jsdoc_score()
        self.assertEqual(score, 100)
        self.assertTrue(detail["no_public_api"])

    def test_jsdoc_full_coverage(self):
        self._mk("src/index.ts",
                 "/** docs */\nexport function a() {}\n"
                 "/** docs */\nexport const b = 1;\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_jsdoc_score()
        self.assertEqual(score, 100)
        self.assertEqual(detail["public_api"], 2)
        self.assertEqual(detail["documented"], 2)

    def test_jsdoc_partial(self):
        self._mk("src/index.ts",
                 "/** docs */\nexport function a() {}\n"
                 "export const b = 1;\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_jsdoc_score()
        self.assertEqual(detail["ratio"], 0.5)
        self.assertEqual(score, 40)

    # 6. 架构文档完整性
    def test_arch_doc_missing(self):
        score, detail = self.m.calc_arch_doc_score()
        self.assertEqual(score, 0)
        self.assertFalse(detail["exists"])

    def test_arch_doc_complete(self):
        self._mk("docs/architecture.md",
                 "# Arch\n## 目录结构\n## 模块职责\n## 数据流\n## 依赖关系\n## 设计决策\n")
        score, detail = self.m.calc_arch_doc_score()
        self.assertEqual(score, 100)
        self.assertEqual(len(detail["sections"]), 5)

    # 综合分
    def test_doc_overall_keys(self):
        self._mk("README.md", "# P\n## 安装\n## 使用\n")
        self._mk("src/main.c", "int main(){return 0;}\n")
        self.m = StandardMetrics(self.root)
        score, detail = self.m.calc_doc_score()
        # key 契约锁定
        for k in ["readme", "changelog", "adr", "comments", "jsdoc", "arch_doc"]:
            self.assertIn(k, detail)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


if __name__ == "__main__":
    unittest.main()