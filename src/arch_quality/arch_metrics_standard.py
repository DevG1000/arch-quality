"""
arch_metrics_standard.py — 标准架构质量指标

实现 SOFTWARE_ARCHITECTURE_QUALITY_GUIDE.md 中的 4 大分类评分。
权重从 skills/arch-quality.md 动态解析。
"""

import os
import re
import json
import argparse
from pathlib import Path
from collections import defaultdict

# 确保可以引用 arch_core.py
from arch_quality.arch_core import (
    FileIndex, DepGraph, GitHistory,
    load_weights_from_skill, ensure_output_dir, write_report,
    read_text_smart, write_text_utf8
)

SKILL_PATH = str(Path(__file__).parent / "skills" / "arch-quality.md")


def _resolve_weights():
    """解析 arch-quality.md 中的权重

    从 skill 文件解析所有 | name | N% | 行，按已知键名分组到各层级。
    每层独立验证权重和是否为 100%。
    """
    raw = load_weights_from_skill(SKILL_PATH)

    weights = {
        "main": {},
        "structural": {},
        "design": {},
        "doc": {},
        "evolution": {},
    }

    layers = {
        "main": ["结构质量", "设计质量", "文档质量", "演进质量"],
        "structural": ["模块化", "耦合度", "内聚度", "复杂度", "可测试性"],
        "design": ["SOLID原则", "设计模式", "架构风格", "反模式"],
        "doc": ["README完整性", "CHANGELOG完整性", "ADR覆盖率",
                "代码注释密度", "JSDoc覆盖率", "架构文档完整性"],
        "evolution": ["历史可追溯性", "技术债务趋势", "依赖过时程度",
                      "废弃代码比例", "增量质量", "问题扣分"],
    }

    for layer, keys in layers.items():
        for k in keys:
            if k in raw:
                weights[layer][k] = raw[k]
        total = sum(weights[layer].values())
        if abs(total - 1.0) > 0.01 and weights[layer]:
            raise ValueError(
                f"Weights in {SKILL_PATH} for layer '{layer}' sum to "
                f"{total*100:.0f}%, expected 100%."
            )

    return weights


class StandardMetrics:
    """标准架构质量指标计算"""

    def __init__(self, root: str):
        self.root = root
        self.weights = _resolve_weights()
        self.index = FileIndex(root)
        self.graph = DepGraph()
        self._build_graph()
        self.git = GitHistory(root)

    def _build_graph(self):
        """构建简化依赖图（基于 import/include 语句）"""
        for f in self.index.files:
            node_id = f["path"]
            self.graph.add_node(node_id, f["lang"], f["path"])
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                content = ""

            # Python imports
            if f["ext"] == ".py":
                for m in re.finditer(r"^(?:from|import)\s+(\S+)", content, re.MULTILINE):
                    target = m.group(1).split(".")[0]
                    if target != os.path.splitext(os.path.basename(f["path"]))[0]:
                        self.graph.add_edge(node_id, target)

            # C++ includes
            elif f["ext"] in (".cpp", ".hpp", ".h", ".c"):
                for m in re.finditer(r'#include\s+[<"](.+?)[>"]', content):
                    target = os.path.basename(m.group(1))
                    self.graph.add_edge(node_id, target)

    def calc_modularity(self):
        """模块化：平均每目录文件数，理想值 5"""
        if not self.index.files:
            return 0
        dirs = set()
        for f in self.index.files:
            d = os.path.dirname(f["path"])
            if d:
                dirs.add(d)
        num_dirs = len(dirs) or 1
        avg = self.index.total_files() / num_dirs
        score = 100 - abs(avg - 5) * 10
        return max(0, min(100, score))

    def calc_coupling(self):
        """耦合度：平均导入数"""
        if not self.graph.nodes:
            return 100
        num_files = len(self.graph.nodes)
        num_edges = len(self.graph.edges)
        avg = num_edges / num_files if num_files > 0 else 0
        score = 100 - avg * 10
        return max(0, min(100, score))

    def calc_cohesion(self):
        """内聚度：超大文件（>1000行）比例"""
        if not self.index.files:
            return 100
        xlarge = sum(1 for f in self.index.files if f["lines"] > 1000)
        ratio = xlarge / self.index.total_files()
        score = 100 - ratio * 200
        return max(0, min(100, score))

    def calc_complexity(self):
        """复杂度：大文件（>200行）比例"""
        if not self.index.files:
            return 100
        large = sum(1 for f in self.index.files if f["lines"] > 200)
        ratio = large / self.index.total_files()
        score = 100 - ratio * 300
        return max(0, min(100, score))

    def calc_testability(self):
        """可测试性：测试文件占比"""
        test_files = sum(1 for f in self.index.files
                         if "test" in f["path"].lower() or "spec" in f["path"].lower())
        total = self.index.total_files()
        ratio = test_files / total if total > 0 else 0
        score = ratio * 200
        return max(0, min(100, score))

    def calc_structural_score(self):
        """结构质量综合分"""
        w = self.weights["structural"]
        scores = {
            "modularity": self.calc_modularity(),
            "coupling": self.calc_coupling(),
            "cohesion": self.calc_cohesion(),
            "complexity": self.calc_complexity(),
            "testability": self.calc_testability(),
        }
        total = 0
        for key, score in scores.items():
            weight_key = {"modularity": "模块化", "coupling": "耦合度",
                          "cohesion": "内聚度", "complexity": "复杂度",
                          "testability": "可测试性"}[key]
            total += score * w.get(weight_key, 0.2)
        return total, scores

    def calc_design_score(self):
        """设计质量综合分（简化实现，返回占位值）"""
        return 70.0, {"solid": 70, "patterns": 65, "style": 75, "anti_patterns": 80}

    def calc_doc_score(self):
        """文档质量综合分（简化实现）"""
        has_readme = os.path.exists(os.path.join(self.root, "README.md"))
        has_changelog = os.path.exists(os.path.join(self.root, "CHANGELOG.md"))
        readme_score = 40 + (20 if has_readme else 0)
        changelog_score = 30 + (30 if has_changelog else 0)
        return (readme_score + changelog_score) / 2, {
            "readme": readme_score, "changelog": changelog_score,
            "adr": 0, "comments": 0, "jsdoc": 0, "arch_doc": 0,
        }

    def calc_evolution_score(self):
        """演进质量综合分（简化实现）"""
        git_score = 20
        if self.git.has_git():
            git_score += 20 if self.git.recent_commits(3) > 0 else 0
            git_score += 20 if self.git.recent_commits(1) > 0 else 0
            git_score += 10 if self.git.contributors_count() > 1 else 0
        return float(git_score), {
            "git_activity": git_score, "debt_trend": 0,
            "dep_outdated": 0, "dead_code": 0,
            "incremental": 0, "problems": 0,
        }

    def all_metrics(self):
        """计算所有指标，返回结构化结果"""
        struct_score, struct_details = self.calc_structural_score()
        design_score, design_details = self.calc_design_score()
        doc_score, doc_details = self.calc_doc_score()
        evolution_score, evo_details = self.calc_evolution_score()

        w = self.weights["main"]
        overall = (
            struct_score * w.get("结构质量", 0.30) +
            design_score * w.get("设计质量", 0.25) +
            doc_score * w.get("文档质量", 0.20) +
            evolution_score * w.get("演进质量", 0.25)
        )

        return {
            "overall": round(overall, 2),
            "structural": {
                "score": round(struct_score, 2),
                "details": struct_details,
                "weight": w.get("结构质量", 0.30),
            },
            "design": {
                "score": round(design_score, 2),
                "details": design_details,
                "weight": w.get("设计质量", 0.25),
            },
            "documentation": {
                "score": round(doc_score, 2),
                "details": doc_details,
                "weight": w.get("文档质量", 0.20),
            },
            "evolution": {
                "score": round(evolution_score, 2),
                "details": evo_details,
                "weight": w.get("演进质量", 0.25),
            },
            "files": {
                "total": self.index.total_files(),
                "by_lang": dict(
                    sorted(
                        ((lang, len(self.index.by_lang(lang)))
                         for lang in set(f["lang"] for f in self.index.files)),
                        key=lambda x: -x[1]
                    )
                ),
                "total_lines": self.index.total_lines(),
                "files_detail": [
                    {"path": f["path"], "lines": f["lines"], "lang": f["lang"]}
                    for f in self.index.files
                ],
            },
            "weights_source": SKILL_PATH,
        }


def main():
    parser = argparse.ArgumentParser(description="标准架构质量指标")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--scan", action="store_true", help="全面扫描")
    parser.add_argument("--metrics", action="store_true", help="计算指标")

    args = parser.parse_args()

    metrics = StandardMetrics(args.root)
    result = metrics.all_metrics()

    out_dir = ensure_output_dir(args.root)
    report_path = write_report(out_dir, "standard-metrics.json", result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
