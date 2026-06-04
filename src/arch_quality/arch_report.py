"""
arch_report.py — 综合架构质量报告生成

合并标准架构质量指标和多语言混合依赖指标，按权重计算最终评分。
两份指南的权重均从对应 skill 文件动态解析。
报告格式按《架构质量评估报告-temp》模板的 16 个章节输出。
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime

from arch_quality.arch_core import (
    FileIndex, DepGraph, GitHistory,
    load_weights_from_skill, ensure_output_dir,
    load_history, save_history,
    get_report_base,
    write_report, write_markdown
)

from arch_quality.arch_metrics_standard import StandardMetrics
from arch_quality.arch_metrics_multilang import MultilangMetrics
from arch_quality.arch_report_generator import ReportGenerator

SKILL_QUALITY = str(Path(__file__).parent / "skills" / "arch-quality.md")
SKILL_MULTILANG = str(Path(__file__).parent / "skills" / "multilang-dependency.md")


class ComprehensiveReport:
    """综合报告数据生成器"""

    def __init__(self, root: str):
        self.root = root
        self.quality_weights = load_weights_from_skill(SKILL_QUALITY)
        self.multilang_weights = load_weights_from_skill(SKILL_MULTILANG)

        self.standard = StandardMetrics(root)
        self.multilang = MultilangMetrics(root)

    def generate(self) -> dict:
        std_result = self.standard.all_metrics()
        ml_result = self.multilang.all_metrics()

        struct_score = std_result["structural"]["score"]

        is_single = ml_result.get("is_single_language", False)

        if is_single:
            merged_structural = struct_score
            ml_weight_applied = 0.0
        else:
            ml_overall = ml_result["overall"]
            merged_structural = struct_score * 0.85 + ml_overall * 0.15
            ml_weight_applied = 0.15

        w = {k: v for k, v in self.quality_weights.items()}
        overall = (
            merged_structural * w.get("结构质量", 0.30) +
            std_result["design"]["score"] * w.get("设计质量", 0.25) +
            std_result["documentation"]["score"] * w.get("文档质量", 0.20) +
            std_result["evolution"]["score"] * w.get("演进质量", 0.25)
        )

        result = {
            "project": os.path.basename(self.root),
            "assessment_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "overall_score": round(overall, 2),
            "is_single_language": is_single,
            "project_languages": ml_result.get("languages", []),
            "weights_source_standard": SKILL_QUALITY,
            "weights_source_multilang": SKILL_MULTILANG,
            "dimensions": {
                "structural": {
                    "score": round(merged_structural, 2),
                    "weight": w.get("结构质量", 0.30),
                    "sub_scores": std_result["structural"]["details"],
                },
                "design": {
                    "score": std_result["design"]["score"],
                    "weight": w.get("设计质量", 0.25),
                    "details": std_result["design"]["details"],
                },
                "documentation": {
                    "score": std_result["documentation"]["score"],
                    "weight": w.get("文档质量", 0.20),
                    "details": std_result["documentation"]["details"],
                },
                "evolution": {
                    "score": std_result["evolution"]["score"],
                    "weight": w.get("演进质量", 0.25),
                    "details": std_result["evolution"]["details"],
                },
            },
            "mlr_violations": ml_result["mlr_violations"],
            "files": std_result["files"],
            "score_breakdown": {
                "formula": "overall = structural*30% + design*25% + doc*20% + evolution*25%",
                "structural_note": (
                    "structural = base_structural*85% + multilang*15%"
                    if not is_single
                    else "structural = base_structural*100% (single-language project, multilang skipped)"
                ),
                "calculated": {
                    "merged_structural": round(merged_structural, 2),
                    "design": std_result["design"]["score"],
                    "documentation": std_result["documentation"]["score"],
                    "evolution": std_result["evolution"]["score"],
                    "weighted_sum": round(overall, 2),
                },
            },
        }

        if not is_single:
            result["dimensions"]["structural"]["multilang_enhancement"] = {
                "score": ml_result["overall"],
                "weight_applied": ml_weight_applied,
                "details": ml_result["dimensions"],
            }

        return result


def main():
    parser = argparse.ArgumentParser(description="架构质量综合评估报告")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON")
    parser.add_argument("--md", action="store_true", help="仅输出 Markdown")
    parser.add_argument("--report-mode", choices=["local", "central"], default="central",
                        help="报告存储模式: local=项目内 .opencode/, central=用户配置目录集中存储")
    parser.add_argument("--project-name", default=None,
                        help="集中模式下的项目名 (默认从根目录推断)")

    args = parser.parse_args()

    reporter = ComprehensiveReport(args.root)
    data = reporter.generate()

    # 加载历史
    history = load_history(args.root, mode=args.report_mode, project_name=args.project_name)

    # 按模板格式生成报告
    generator = ReportGenerator(args.root, data, history)
    markdown = generator.generate()

    # 保存历史快照
    history_entry = {
        "date": data["assessment_date"],
        "overall_score": data["overall_score"],
        "god_files": {},
    }
    for key in ["structural", "design", "documentation", "evolution"]:
        d = data["dimensions"].get(key, {})
        history_entry[key] = d.get("score", 0)
    save_history(args.root, history_entry, mode=args.report_mode, project_name=args.project_name)

    out_dir = ensure_output_dir(args.root, mode=args.report_mode, project_name=args.project_name)
    base = get_report_base(args.root, mode=args.report_mode, project_name=args.project_name)

    if not args.md:
        json_path = write_report(out_dir, "comprehensive-report.json", data)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"\nJSON report: {json_path}")
        print(f"Storage mode: {args.report_mode}, base: {base}")

    if not args.json:
        md_path = write_markdown(out_dir, "comprehensive-report.md", markdown)
        print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
