"""
arch_report.py — 综合架构质量报告生成

合并标准架构质量指标和多语言混合依赖指标，按权重计算最终评分。
两份指南的权重均从对应 skill 文件动态解析。
报告格式按《架构质量评估报告-temp》模板的 16 个章节输出。
"""

import os
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

from arch_quality.arch_core import (
    FileIndex, DepGraph, GitHistory,
    load_weights_from_skill, ensure_output_dir,
    load_history, save_history,
    get_report_base,
    write_report, write_markdown,
    load_profile_config, resolve_enabled_engines,
    PROFILE_ENGINE_MAP, ENHANCEMENT_ENGINES,
)

from arch_quality.arch_metrics_standard import StandardMetrics
from arch_quality.arch_metrics_multilang import MultilangMetrics
from arch_quality.arch_metrics_template import TemplateMetaprogrammingMetrics
from arch_quality.arch_metrics_numerical_accuracy import NumericalAccuracyMetrics
from arch_quality.arch_metrics_solver_physics import SolverPhysicsMetrics
from arch_quality.arch_metrics_geometry_consistency import GeometryConsistencyMetrics
from arch_quality.arch_metrics_anti_corruption import AntiCorruptionMetrics
from arch_quality.arch_report_generator import ReportGenerator

SKILL_QUALITY = str(Path(__file__).parent / "skills" / "arch-quality.md")
SKILL_MULTILANG = str(Path(__file__).parent / "skills" / "multilang-dependency.md")
SKILL_TEMPLATE = str(Path(__file__).parent / "skills" / "template-metaprogramming.md")
SKILL_SOLVER_PHYSICS = str(Path(__file__).parent / "skills" / "solver-physics-architecture.md")


class ComprehensiveReport:
    """综合报告数据生成器"""

    def __init__(self, root: str, build_dir: str = "", test_dirs: list = None,
                 profile: dict = None):
        self.root = root
        self.build_dir = build_dir
        self.test_dirs = test_dirs or []
        # profile: load_profile_config 返回的配置 dict（含 enabled_engines）或 None
        self.profile = profile
        self.quality_weights = load_weights_from_skill(SKILL_QUALITY)
        self.multilang_weights = load_weights_from_skill(SKILL_MULTILANG)
        self.template_weights = load_weights_from_skill(SKILL_TEMPLATE)

        self.standard = StandardMetrics(root, build_dir=build_dir, test_dirs=self.test_dirs)
        self.multilang = MultilangMetrics(root, build_dir=build_dir)
        self.template = TemplateMetaprogrammingMetrics(root, build_dir=build_dir)
        self.numerical = NumericalAccuracyMetrics(root)
        self.solver_physics = SolverPhysicsMetrics(root)
        self.geometry = GeometryConsistencyMetrics(root)
        self.anti_corruption = AntiCorruptionMetrics(root)

    def _enabled_enhancement_keys(self) -> set:
        """显式 profile 模式下的启用增强引擎键集；启发式模式返回全量（由检测决定）"""
        if getattr(self, "profile", None) is not None:
            return set(self.profile["enabled_engines"])
        return set(ENHANCEMENT_ENGINES)

    def generate(self) -> dict:
        std_result = self.standard.all_metrics()

        # 引擎选择：显式 profile 优先（仅运行启用引擎）；否则启发式兜底（运行全部）
        enabled = self._enabled_enhancement_keys()
        profile_active = getattr(self, "profile", None) is not None

        ml_result = self.multilang.all_metrics() if ("multilang" in enabled or not profile_active) else None
        tpl_result = self.template.all_metrics() if ("template" in enabled or not profile_active) else None
        nvr_result = self.numerical.all_metrics() if ("numerical" in enabled or not profile_active) else None
        sp_result = self.solver_physics.all_metrics() if ("solver-physics" in enabled or not profile_active) else None
        gcs_result = (getattr(self, "geometry", None).all_metrics()
                     if ("geometry-consistency" in enabled or not profile_active) else None) if getattr(self, "geometry", None) else None
        acl_result = (getattr(self, "anti_corruption", None).all_metrics()
                     if ("anti-corruption" in enabled or not profile_active) else None) if getattr(self, "anti_corruption", None) else None

        struct_score = std_result["structural"]["score"]

        is_single = ml_result.get("is_single_language", False) if ml_result else False
        has_cpp = tpl_result.get("is_cpp_project", False) if tpl_result else False
        has_numerical = nvr_result.get("is_numerical", False) if nvr_result else False
        has_multiphysics = sp_result.get("is_multiphysics", False) if sp_result else False
        has_geometry = gcs_result.get("is_geometry", False) if gcs_result else False
        has_acl = acl_result.get("is_acl", False) if acl_result else False

        # 激活增强引擎列表：[(key, base_weight, result)]
        # 启发式模式由检测信号决定；显式 profile 模式由声明引擎集 + 引擎实际产出（overall 非 None）决定
        enh = []
        if profile_active:
            for key, engine, w, result in [
                ("ml", "multilang", 0.15, ml_result),
                ("tpl", "template", 0.15, tpl_result),
                ("nvr", "numerical", 0.10, nvr_result),
                ("sp", "solver-physics", 0.15, sp_result),
                ("gcs", "geometry-consistency", 0.15, gcs_result),
                ("acl", "anti-corruption", 0.15, acl_result),
            ]:
                if engine in enabled and result is not None and result.get("overall") is not None:
                    enh.append((key, w, result))
        else:
            if not is_single and ml_result is not None and ml_result.get("overall") is not None:
                enh.append(("ml", 0.15, ml_result))
            if has_cpp and tpl_result is not None and tpl_result.get("overall") is not None:
                enh.append(("tpl", 0.15, tpl_result))
            if has_numerical and nvr_result is not None and nvr_result.get("overall") is not None:
                enh.append(("nvr", 0.10, nvr_result))
            if has_multiphysics and sp_result is not None and sp_result.get("overall") is not None:
                enh.append(("sp", 0.15, sp_result))
            if has_geometry and gcs_result is not None and gcs_result.get("overall") is not None:
                enh.append(("gcs", 0.15, gcs_result))
            if has_acl and acl_result is not None and acl_result.get("overall") is not None:
                enh.append(("acl", 0.15, acl_result))

        ml_weight_applied = 0.0
        tpl_weight_applied = 0.0
        nvr_weight_applied = 0.0
        sp_weight_applied = 0.0
        gcs_weight_applied = 0.0
        acl_weight_applied = 0.0

        active_count = len(enh)
        if active_count == 0:
            merged_structural = struct_score
        else:
            # 基础权重按激活数分档（与既有规则一致）
            base_map = {1: 0.85, 2: 0.70, 3: 0.60, 4: 0.55, 5: 0.50, 6: 0.45}
            base_w = base_map.get(active_count, 0.45)
            enh_raw = dict((k, w) for k, w, _ in enh)

            # 归一化：当基础+增强权重和 > 1 时等比缩放（如 4 增强 110% → 100%）
            real_w = base_w + sum(enh_raw.values())
            if active_count >= 3 and real_w > 1.0:
                scale = 1.0 / real_w
                base_w *= scale
                enh_raw = {k: v * scale for k, v in enh_raw.items()}

            ml_weight_applied = enh_raw.get("ml", 0.0)
            tpl_weight_applied = enh_raw.get("tpl", 0.0)
            nvr_weight_applied = enh_raw.get("nvr", 0.0)
            sp_weight_applied = enh_raw.get("sp", 0.0)
            gcs_weight_applied = enh_raw.get("gcs", 0.0)
            acl_weight_applied = enh_raw.get("acl", 0.0)

            enh_overall = {k: r["overall"] for k, _, r in enh}
            merged_structural = (
                struct_score * base_w +
                enh_overall.get("ml", 0) * ml_weight_applied +
                enh_overall.get("tpl", 0) * tpl_weight_applied +
                enh_overall.get("nvr", 0) * nvr_weight_applied +
                enh_overall.get("sp", 0) * sp_weight_applied +
                enh_overall.get("gcs", 0) * gcs_weight_applied +
                enh_overall.get("acl", 0) * acl_weight_applied
            ) / max(base_w + ml_weight_applied + tpl_weight_applied
                    + nvr_weight_applied + sp_weight_applied
                    + gcs_weight_applied + acl_weight_applied, 0.01)

        w = {k: v for k, v in self.quality_weights.items()}
        overall = (
            merged_structural * w.get("结构质量", 0.30) +
            std_result["design"]["score"] * w.get("设计质量", 0.25) +
            std_result["documentation"]["score"] * w.get("文档质量", 0.20) +
            std_result["evolution"]["score"] * w.get("演进质量", 0.25)
        )

        # 过渡口径（H2 WP-0，决策 8b）：profile 子集评分标注，与全引擎评分并列展示、禁止混合计分
        skipped_engines = [e for e in ENHANCEMENT_ENGINES if e not in enabled] if profile_active else []
        subset_scoring = profile_active and bool(skipped_engines)
        profile_meta = {
            "active": profile_active,
            "config_source": self.profile.get("config_source", "") if profile_active else "",
            "profile": self.profile.get("profile") if profile_active else None,
            "enable_engines": self.profile.get("enable_engines") if profile_active else None,
            "skip_engines": self.profile.get("skip_engines") if profile_active else None,
            "enabled_engines": sorted(enabled),
            "skipped_engines": skipped_engines,
            "subset_scoring": subset_scoring,
            "note": (
                "过渡口径（H2 WP-0，决策 8b）：profile 子集评分仅基于已启用引擎，"
                "与全引擎评分并列展示、禁止混合计分；激活子集全局归一化实施归 H3。"
                if subset_scoring else "全引擎评分"
            ),
        }

        result = {
            "project": os.path.basename(self.root),
            "assessment_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "overall_score": round(overall, 2),
            "is_single_language": is_single,
            "project_languages": ml_result.get("languages", []) if ml_result else [],
            "profile": profile_meta,
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
            "mlr_violations": list(ml_result.get("mlr_violations", [])) if ml_result else [],
            "files": std_result["files"],
            "score_breakdown": {
                "formula": "overall = structural*30% + design*25% + doc*20% + evolution*25%",
                "structural_note": (
                    f"structural = base*{int((1-ml_weight_applied-tpl_weight_applied-nvr_weight_applied-sp_weight_applied-gcs_weight_applied-acl_weight_applied)*100)}%"
                    f" + multilang*{int(ml_weight_applied*100)}%"
                    f" + template*{int(tpl_weight_applied*100)}%"
                    f" + numerical*{int(nvr_weight_applied*100)}%"
                    f" + solver_physics*{int(sp_weight_applied*100)}%"
                    f" + geometry_consistency*{int(gcs_weight_applied*100)}%"
                    f" + anti_corruption*{int(acl_weight_applied*100)}%"
                    + (f" [profile 子集评分：启用 {sorted(enabled)}，跳过 {skipped_engines}]" if subset_scoring else "")
                    if active_count > 0
                    else "structural = base_structural*100% (no enhancement engine active)"
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

        if ml_result is not None and ("ml" in (k for k, _, _ in enh)):
            result["dimensions"]["structural"]["multilang_enhancement"] = {
                "score": ml_result["overall"],
                "weight_applied": ml_weight_applied,
                "details": ml_result["dimensions"],
            }

        if tpl_result is not None and ("tpl" in (k for k, _, _ in enh)):
            result["dimensions"]["structural"]["template_enhancement"] = {
                "score": tpl_result["overall"],
                "weight_applied": tpl_weight_applied,
                "details": tpl_result["dimensions"],
            }

        if nvr_result is not None and ("nvr" in (k for k, _, _ in enh)):
            result["dimensions"]["structural"]["numerical_enhancement"] = {
                "score": nvr_result["overall"],
                "weight_applied": nvr_weight_applied,
                "details": nvr_result["dimensions"],
            }

        if sp_result is not None and ("sp" in (k for k, _, _ in enh)):
            result["dimensions"]["structural"]["solver_physics_enhancement"] = {
                "score": sp_result["overall"],
                "weight_applied": sp_weight_applied,
                "details": sp_result["dimensions"],
            }

        if gcs_result is not None and ("gcs" in (k for k, _, _ in enh)):
            result["dimensions"]["structural"]["geometry_consistency_enhancement"] = {
                "score": gcs_result["overall"],
                "weight_applied": gcs_weight_applied,
                "details": gcs_result["dimensions"],
            }

        if acl_result is not None and ("acl" in (k for k, _, _ in enh)):
            result["dimensions"]["structural"]["anti_corruption_enhancement"] = {
                "score": acl_result["overall"],
                "weight_applied": acl_weight_applied,
                "details": acl_result["dimensions"],
            }

        # 跳过引擎并列展示（profile 子集模式）：标注未评估维度，禁止与全引擎评分混合
        if profile_active and skipped_engines:
            skipped_labels = {
                "multilang": "跨语言混合依赖（MLR）",
                "template": "模板元编程（TPL）",
                "numerical": "数值算法正确性（NVR）",
                "solver-physics": "求解器物理场（MPR）",
                "geometry-consistency": "几何内核一致性（GCS）",
                "anti-corruption": "外部内核防腐层（ACL）",
            }
            result["dimensions"]["structural"]["skipped_enhancements"] = [
                {"engine": e, "label": skipped_labels.get(e, e),
                 "status": "not_evaluated",
                 "reason": f"profile 未启用 {e}（声明引擎集 {sorted(enabled)}）"}
                for e in skipped_engines
            ]

        if tpl_result is not None:
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

        # 合并 solver-physics MPR 违规到报告
        if sp_result is not None:
            for v in sp_result.get("mpr_violations", []):
                result["mlr_violations"].append(v)

        # 合并 NVR 违规到报告
        if nvr_result is not None:
            for v in nvr_result.get("nvr_violations", []):
                result["mlr_violations"].append(v)

        if gcs_result is not None:
            for v in gcs_result.get("gcs_violations", []):
                result["mlr_violations"].append(v)

        # 合并 ACL 防腐层违规到报告
        if acl_result is not None:
            for v in acl_result.get("acl_violations", []):
                result["mlr_violations"].append(v)

        # 合并标准架构质量 SAR 违规到报告
        sar_violations = std_result.get("sar_violations", [])
        for v in sar_violations:
            result["mlr_violations"].append(v)

        return result


def main():
    # 强制 UTF-8 输出（Windows 控制台默认 GBK，管道/重定向时子进程解码需一致）
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="架构质量综合评估报告")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--build-dir", default="", help="构建目录（包含 SWIG 生成文件的目录，如 build/）")
    parser.add_argument("--test-dirs", default="", nargs="*",
                        help="out-of-tree 测试根目录（相对于项目根，如 tutorials tests-external）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式报告")
    parser.add_argument("--md", action="store_true", help="输出 Markdown 格式报告")
    parser.add_argument("--report-mode", choices=["local", "central"], default="central",
                        help="报告存储模式: local=项目内 .opencode/, central=用户配置目录集中存储")
    parser.add_argument("--project-name", default=None,
                        help="集中模式下的项目名 (默认从根目录推断)")
    parser.add_argument("--profile", default=None, action="append",
                        choices=list(PROFILE_ENGINE_MAP.keys()),
                        help="显式 profile（可重复指定多个，引擎集取并集；覆盖配置文件 arch-quality.yaml 的 profile 字段）")

    args = parser.parse_args()

    # 显式 profile 配置：配置文件优先，CLI --profile 覆盖 profile 字段，CLI --test-dirs 覆盖 test_dirs
    try:
        cfg = load_profile_config(args.root)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    if args.profile:
        cfg = dict(cfg)
        # 单 profile 归一为字符串（保持历史报告语义），多 profile 保留 list
        cfg["profile"] = args.profile if len(args.profile) > 1 else args.profile[0]
    if args.profile or cfg:
        cfg = dict(cfg)
        cfg["enabled_engines"] = resolve_enabled_engines(
            cfg.get("profile"), cfg.get("enable_engines"), cfg.get("skip_engines"))

    test_dirs = list(args.test_dirs) if args.test_dirs else list(cfg.get("test_dirs", []))
    profile = cfg if (args.profile or cfg) else None
    reporter = ComprehensiveReport(args.root, build_dir=args.build_dir, test_dirs=test_dirs,
                                   profile=profile)
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
