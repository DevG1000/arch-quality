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
from arch_quality.arch_metrics_template import TemplateMetaprogrammingMetrics
from arch_quality.arch_report_generator import ReportGenerator

SKILL_QUALITY = str(Path(__file__).parent / "skills" / "arch-quality.md")
SKILL_MULTILANG = str(Path(__file__).parent / "skills" / "multilang-dependency.md")
SKILL_TEMPLATE = str(Path(__file__).parent / "skills" / "template-metaprogramming.md")


class ComprehensiveReport:
    """综合报告数据生成器"""

    def __init__(self, root: str, build_dir: str = ""):
        self.root = root
        self.build_dir = build_dir
        self.quality_weights = load_weights_from_skill(SKILL_QUALITY)
        self.multilang_weights = load_weights_from_skill(SKILL_MULTILANG)
        self.template_weights = load_weights_from_skill(SKILL_TEMPLATE)

        self.standard = StandardMetrics(root)
        self.multilang = MultilangMetrics(root, build_dir=build_dir)
        self.template = TemplateMetaprogrammingMetrics(root, build_dir=build_dir)

    def generate(self) -> dict:
        std_result = self.standard.all_metrics()
        ml_result = self.multilang.all_metrics()
        tpl_result = self.template.all_metrics()

        struct_score = std_result["structural"]["score"]

        is_single = ml_result.get("is_single_language", False)
        has_cpp = tpl_result.get("is_cpp_project", False)

        if is_single and not has_cpp:
            merged_structural = struct_score
            ml_weight_applied = 0.0
            tpl_weight_applied = 0.0
        elif not is_single and not has_cpp:
            ml_overall = ml_result["overall"]
            merged_structural = struct_score * 0.85 + ml_overall * 0.15
            ml_weight_applied = 0.15
            tpl_weight_applied = 0.0
        elif is_single and has_cpp:
            tpl_overall = tpl_result["overall"]
            merged_structural = struct_score * 0.85 + tpl_overall * 0.15
            ml_weight_applied = 0.0
            tpl_weight_applied = 0.15
        else:
            ml_overall = ml_result["overall"]
            tpl_overall = tpl_result["overall"]
            merged_structural = struct_score * 0.70 + ml_overall * 0.15 + tpl_overall * 0.15
            ml_weight_applied = 0.15
            tpl_weight_applied = 0.15

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
                    f"structural = base*{int((1-ml_weight_applied-tpl_weight_applied)*100)}%"
                    f" + multilang*{int(ml_weight_applied*100)}%"
                    f" + template*{int(tpl_weight_applied*100)}%"
                    if not is_single or has_cpp
                    else "structural = base_structural*100% (single-language project, no enhancement)"
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

        if has_cpp:
            result["dimensions"]["structural"]["template_enhancement"] = {
                "score": tpl_result["overall"],
                "weight_applied": tpl_weight_applied,
                "details": tpl_result["dimensions"],
            }

        tpl_violations = tpl_result.get("mlr_violations", [])
        if tpl_violations:
            merged_014_023 = False
            for v in tpl_violations:
                if v.get("merge_to") == "MLR-014":
                    for existing in result["mlr_violations"]:
                        if existing.get("rule") == "MLR-014":
                            existing["merged_with_023"] = True
                            existing["detail"] += f"; 另有 {v['count']} 处多处重复实例化（MLR-023 已合并）"
                            merged_014_023 = True
                            break
                    if not merged_014_023:
                        result["mlr_violations"].append({
                            "rule": "MLR-014", "name": v.get("name", ""),
                            "severity": v.get("severity", "MEDIUM"),
                            "output_level": v.get("output_level", "WARNING"),
                            "count": v.get("count", 0),
                            "detail": v.get("detail", ""),
                        })
                else:
                    result["mlr_violations"].append(v)

            sme_waiver_notes = []
            output_level_summary = {"ERROR": 0, "WARNING": 0, "INFO": 0}
            for v in result["mlr_violations"]:
                if v.get("rule", "").startswith("MLR-"):
                    ol = v.get("output_level", v.get("severity", "WARNING"))
                    if ol in output_level_summary:
                        output_level_summary[ol] += 1
                    if v.get("waivable"):
                        sme_waiver_notes.append(f"{v['rule']}: severity={v['severity']}, output_level={ol}")
            if any(v.get("rule") == "MLR-013" for v in tpl_violations) and any(v.get("rule") == "MLR-015" for v in tpl_violations):
                result["structural_note_cross_concern"] = "MLR-013(编译时扇入) 与 MLR-015(头文件传染链过长) 同时触发，保留独立评分但建议团队优先解决同时触犯两条规则的模块"
            if sme_waiver_notes:
                result["sme_waiver_summary"] = sme_waiver_notes
            result["output_level_summary"] = output_level_summary

        return result


def main():
    parser = argparse.ArgumentParser(description="架构质量综合评估报告")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--build-dir", default="", help="构建目录（包含 SWIG 生成文件的目录，如 build/）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式报告")
    parser.add_argument("--md", action="store_true", help="输出 Markdown 格式报告")
    parser.add_argument("--report-mode", choices=["local", "central"], default="central",
                        help="报告存储模式: local=项目内 .opencode/, central=用户配置目录集中存储")
    parser.add_argument("--project-name", default=None,
                        help="集中模式下的项目名 (默认从根目录推断)")

    args = parser.parse_args()

    reporter = ComprehensiveReport(args.root, build_dir=args.build_dir)
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

    output_json = args.json or not args.md
    output_md = args.md or not args.json

    if output_json:
        json_path = write_report(out_dir, "comprehensive-report.json", data)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"\nJSON report: {json_path}")
        print(f"Storage mode: {args.report_mode}, base: {base}")

    if output_md:
        md_path = write_markdown(out_dir, "comprehensive-report.md", markdown)
        print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
