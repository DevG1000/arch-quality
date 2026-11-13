# -*- coding: utf-8 -*-
"""doc_lint.py 的单元测试（门禁 G0/G1/G3 + Review/PR 契约）。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import doc_lint  # noqa: E402

GUIDE = """# 示例评估指南（1.0版）

## 概述
示例维度。

## 置信度说明
| 置信度 | 含义 |
|:--:|:--|
| 高 | 精确匹配 |

## 一、子维度与权重分配
| 子维度 | 权重（默认） | 覆盖规则 | 置信度 |
|:--|:--:|:--:|:--:|
| 维度甲 | 60% | SXX-001~002 | 中 |
| 维度乙 | 40% | SXX-003 | 中 |

## 二、子维度定义与评分算法
略。

## 五、内置规则
| 规则 | 名称 | severity | output_level | 置信度 | 所属子维度 |
|:--|:--|:--|:--|:--|:--|
| SXX-001 | 规则一 | HIGH | ERROR | 中 | 2.1 |
| SXX-002 | 规则二 | MEDIUM | WARNING | 中 | 2.1 |
| SXX-003 | 规则三 | LOW | INFO | 低 | 2.2 |

#### SXX-001：规则一
检测：正则精确匹配。

#### SXX-002：规则二
检测：结构检查。

#### SXX-003：规则三
检测：启发式推断。

## 七、实施建议
见上。

## 版本历史
- 1.0 初稿
"""

SKILL = """# 示例评估技能

> 对应《示例评估指南》**1.0 版**

## 一、权重分配
| 维度 | 权重 | 对应指南章节 |
|:--|:--:|:--|
| 维度甲 | 60% | §2.1 |
| 维度乙 | 40% | §2.2 |

## 五、规则
| 规则 | 名称 | severity | output_level | 置信度 | 所属维度 |
|:--|:--|:--|:--|:--|:--|
| SXX-001 | 规则一 | HIGH | ERROR | 中 | 2.1 |
| SXX-002 | 规则二 | MEDIUM | WARNING | 中 | 2.1 |
| SXX-003 | 规则三 | LOW | INFO | 低 | 2.2 |

#### SXX-001：规则一
#### SXX-002：规则二
#### SXX-003：规则三
"""

OPENCODE_SKILL = """# 示例技能

> 指南版本：1.0

## 4 维度评分模型
| 维度 | 权重 | 说明 |
|:--|:--:|:--|
| 维度甲 | 60% | 甲 |
| 维度乙 | 40% | 乙 |

## 规则
| 规则 | 名称 | output_level | 说明 |
|:--|:--|:--|:--|
| SXX-001 | 规则一 | **ERROR** | 甲 |
| SXX-002 | 规则二 | **WARNING** | 乙 |
| SXX-003 | 规则三 | **INFO** | 丙 |
"""

CASES = """# 示例验证案例集

> **关联**：《示例评估指南（1.0版）》
"""


class LintFixture:
    def __init__(self, tmp: Path):
        self.dir = tmp
        self.guide = tmp / "指南.md"
        # 注意：Windows 路径大小写不敏感，"skill.md" 与 "SKILL.md" 会落到同一文件
        self.skill = tmp / "skill-src.md"
        self.opencode_skill = tmp / "skill-opencode.md"
        self.cases = tmp / "案例集.md"
        self.rationale = tmp / "设计依据.md"
        self.write()

    def write(self, guide=GUIDE, skill=SKILL, opencode=OPENCODE_SKILL,
              cases=CASES, rationale=CASES):
        self.guide.write_text(guide, encoding="utf-8")
        self.skill.write_text(skill, encoding="utf-8")
        self.opencode_skill.write_text(opencode, encoding="utf-8")
        self.cases.write_text(cases, encoding="utf-8")
        self.rationale.write_text(rationale, encoding="utf-8")

    def lint(self, **kw):
        return doc_lint.lint_paths(
            guide=self.guide, skill=self.skill, opencode_skill=self.opencode_skill,
            cases=self.cases, rationale=self.rationale, **kw)


def codes(report):
    return [f["code"] for f in report.findings]


class TestStructure(unittest.TestCase):
    def test_clean_fixture_passes(self):
        with tempfile.TemporaryDirectory() as d:
            fx = LintFixture(Path(d))
            rep = fx.lint()
            self.assertEqual([f for f in rep.findings if f["level"] == "ERROR"], [])

    def test_missing_section(self):
        with tempfile.TemporaryDirectory() as d:
            fx = LintFixture(Path(d))
            fx.write(guide=GUIDE.replace("## 七、实施建议", ""))
            self.assertIn("G0-section", codes(fx.lint()))

    def test_missing_rule_detail(self):
        with tempfile.TemporaryDirectory() as d:
            fx = LintFixture(Path(d))
            fx.write(guide=GUIDE.replace("#### SXX-003：规则三\n检测：启发式推断。", ""))
            self.assertIn("G0-rule-detail", codes(fx.lint()))

    def test_broken_relative_link(self):
        with tempfile.TemporaryDirectory() as d:
            fx = LintFixture(Path(d))
            fx.write(cases=CASES + "\n[坏链接](missing.md)\n")
            self.assertIn("G0-link", codes(fx.lint()))

    def test_version_drift_is_warning_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            fx = LintFixture(Path(d))
            fx.write(cases="# 案例集\n\n> **关联**：《示例评估指南（0.9版）》\n")
            rep = fx.lint()
            drift = [f for f in rep.findings if f["code"] == "G0-version-drift"]
            self.assertTrue(drift)
            self.assertEqual(drift[0]["level"], "WARNING")
            rep2 = fx.lint(strict_versions=True)
            self.assertIn("G0-version-drift",
                          [f["code"] for f in rep2.findings if f["level"] == "ERROR"])


class TestWeights(unittest.TestCase):
    def test_sum_not_100(self):
        with tempfile.TemporaryDirectory() as d:
            fx = LintFixture(Path(d))
            fx.write(guide=GUIDE.replace("| 维度乙 | 40%", "| 维度乙 | 45%"))
            self.assertIn("G1-sum", codes(fx.lint()))

    def test_cross_doc_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            fx = LintFixture(Path(d))
            fx.write(skill=SKILL.replace("| 维度乙 | 40%", "| 维度乙 | 35%"))
            self.assertIn("G1-cross", codes(fx.lint()))


class TestRules(unittest.TestCase):
    def test_low_confidence_must_not_be_error(self):
        with tempfile.TemporaryDirectory() as d:
            fx = LintFixture(Path(d))
            fx.write(guide=GUIDE.replace(
                "| SXX-003 | 规则三 | LOW | INFO | 低 | 2.2 |",
                "| SXX-003 | 规则三 | HIGH | ERROR | 低 | 2.2 |"))
            self.assertIn("G3-low-conf-error", codes(fx.lint()))

    def test_cross_doc_severity_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            fx = LintFixture(Path(d))
            fx.write(skill=SKILL.replace(
                "| SXX-001 | 规则一 | HIGH | ERROR | 中 | 2.1 |",
                "| SXX-001 | 规则一 | MEDIUM | ERROR | 中 | 2.1 |"))
            self.assertIn("G3-cross", codes(fx.lint()))

    def test_high_confidence_with_heuristic_hint(self):
        with tempfile.TemporaryDirectory() as d:
            fx = LintFixture(Path(d))
            fx.write(
                guide=GUIDE.replace(
                    "| SXX-003 | 规则三 | LOW | INFO | 低 | 2.2 |",
                    "| SXX-003 | 规则三 | LOW | INFO | 高 | 2.2 |"),
                skill=SKILL.replace(
                    "| SXX-003 | 规则三 | LOW | INFO | 低 | 2.2 |",
                    "| SXX-003 | 规则三 | LOW | INFO | 高 | 2.2 |"),
            )
            rep = fx.lint()
            self.assertIn("G3-high-heuristic",
                          [f["code"] for f in rep.findings if f["level"] == "WARNING"])


class TestReviewContract(unittest.TestCase):
    def _write(self, d, data):
        p = Path(d) / "review.json"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return p

    def _valid(self):
        return {
            "pr_id": "PR-1",
            "reviewer": {"model": "kimi-k3", "provider": "opencode-go", "role": "reviewer"},
            "verdict": "changes_requested",
            "p0": 1, "p1": 0, "p2": 0,
            "comments": [{
                "file": "docs/zh/x/指南.md", "line": 57,
                "severity": "P0", "evidence": "EV-TEST-abc12345",
                "message": "子维度权重和在 1.6 版中为 105%",
                "suggestion": "将维度乙改为 20%",
            }],
        }

    def test_valid_review(self):
        with tempfile.TemporaryDirectory() as d:
            rep = doc_lint.lint_review_file(self._write(d, self._valid()))
            self.assertFalse(rep.has_error())

    def test_comment_needs_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            data = self._valid()
            data["comments"][0]["evidence"] = ""
            rep = doc_lint.lint_review_file(self._write(d, data))
            self.assertIn("R-schema", codes(rep))

    def test_approve_with_p0_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            data = self._valid()
            data["verdict"] = "approved"
            rep = doc_lint.lint_review_file(self._write(d, data))
            self.assertIn("R-approve-with-p0", codes(rep))


class TestPrContract(unittest.TestCase):
    PR = """---
pr_type: guide
kb_version: 1.6 -> 1.7
guide_version: 1.6
evidence: [EV-TEST-abc12345]
changes:
  files: [docs/zh/x/指南.md]
  severity_changed:
    - {rule: GCS-004, from: HIGH, to: MEDIUM}
human_decisions: []
review:
  verdict: changes_requested
  p0: 1
---
正文
"""

    def test_risky_change_needs_human_approval(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pr.md"
            p.write_text(self.PR, encoding="utf-8")
            rep = doc_lint.lint_pr_file(p)
            self.assertIn("PR-human-approval", codes(rep))

    def test_approved_with_p0_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pr.md"
            p.write_text(self.PR.replace("verdict: changes_requested", "verdict: approved"),
                         encoding="utf-8")
            self.assertIn("PR-approve-with-p0", codes(doc_lint.lint_pr_file(p)))


class TestRealRepo(unittest.TestCase):
    def test_gcs_dimension_has_no_error(self):
        rep = doc_lint.lint_dimension("gcs")
        errors = [f for f in rep.findings if f["level"] == "ERROR"]
        self.assertEqual(errors, [], errors)


if __name__ == "__main__":
    unittest.main()
