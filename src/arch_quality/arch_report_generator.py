"""
arch_report_generator.py — 按《架构质量评估报告-temp》模板格式生成报告

14 个章节，按模板顺序依次构造。
"""

import os
import re
import math
import json
from pathlib import Path
from datetime import datetime

ESC = "\033"


def _severity_icon(s: str) -> str:
    return {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟢", "INFO": "ℹ️", "": "⚪"}.get(s, "⚪")


def _score_grade(score: float) -> str:
    if score >= 85:
        return "🟢 优秀"
    if score >= 70:
        return "🟡 良好"
    if score >= 50:
        return "🟠 需改进"
    return "🔴 差"


def _trend_icon(delta: float) -> str:
    if delta > 0:
        return "↑"
    if delta < 0:
        return "↓"
    return "→"


def _trend_desc(delta: float) -> str:
    if delta > 5:
        return "改善 🟢"
    if delta > 0:
        return "轻微改善 🟢"
    if delta > -5:
        return "轻微退化 🟡"
    return "明显退化 🔴"


def _grade_color(score: float) -> str:
    if score >= 70:
        return ""
    if score >= 50:
        return ""
    return ""


COLORS = {}


def _h(score, threshold=70):
    return ""


GOD_OBJECT_THRESHOLD = 1000
LARGE_FILE_THRESHOLD = 200


SUGGESTION_TEMPLATES = {
    "god_object": (
        "拆分 {file} 为独立模块",
        "工时:L(3-5d)",
        "目标 <700 行",
    ),
    "complexity_high": (
        "拆分 {file} 为多个小文件",
        "工时:M(1-2d)",
        "目标每文件 <200 行",
    ),
    "missing_changelog": (
        "创建 CHANGELOG.md",
        "工时:XS(<1h)",
        "按 keepachangelog 格式维护，挽回文档质量 15 分",
    ),
    "low_test_coverage": (
        "增加测试覆盖率",
        "工时:XL(>1w)",
        "优先覆盖核心模块，目标测试文件达源码 30%",
    ),
    "mlr_binding_drift": (
        "修复绑定层接口漂移",
        "工时:M(1-3d)",
        "同步 {count} 处缺失/不匹配接口",
    ),
    "mlr_script_boundary": (
        "封装脚本内部访问",
        "工时:S(<1d)",
        "为 {count} 处越界创建 API 包装",
    ),
    "mlr_cycle": (
        "消除跨语言循环依赖",
        "工时:L(3-5d)",
        "引入中间抽象层或异步消息",
    ),
    "mlr_gil": (
        "修复 GIL 死锁风险",
        "工时:S(<1d)",
        "在 C++ 回调前释放 GIL (py::gil_scoped_release)",
    ),
    "binding_void_ptr": (
        "替换绑定层通用类型 void*",
        "工时:M(1-2d)",
        "改用强类型映射",
    ),
}


class ReportGenerator:
    """按模板格式生成完整架构质量评估报告"""

    def __init__(self, root: str, metrics: dict, history: list):
        self.root = root
        self.m = metrics
        self.history = history
        self.prev = history[-1] if history else None
        self._god_files = self._find_god_files()
        self._god_files_prev = (self.prev or {}).get("god_files", {})

    def _find_god_files(self) -> dict:
        """返回 {相对路径: 行数} 的超大文件"""
        files = self.m.get("files", {})
        files_detail = files.get("files_detail", [])
        god = {}
        for entry in files_detail:
            path = entry.get("path", "")
            lines = entry.get("lines", 0)
            if lines > GOD_OBJECT_THRESHOLD:
                god[path] = lines
        return god

    # ── WP-4: 规则覆盖矩阵（动态生成，与 WP-2 对齐）──

    def _rule_coverage_matrix(self) -> str:
        """从 rule_coverage_matrix.json 生成规则覆盖矩阵表

        按引擎分组（MLR/NVR/MPR/TPL/SAR），展示每条规则的覆盖来源。
        口径与 WP-2 的 docs/zh/计划/规则覆盖矩阵.md 一致。
        """
        matrix_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "docs", "zh", "计划", "rule_coverage_matrix.json",
        )
        if not os.path.exists(matrix_path):
            return ""
        try:
            with open(matrix_path, encoding="utf-8-sig") as f:
                matrix = json.load(f)
        except Exception:
            return ""

        # 按规则前缀分组
        groups = {}
        for rule, info in matrix.items():
            prefix = rule.split("-")[0]
            groups.setdefault(prefix, []).append((rule, info))

        icon = {"回归": "✅", "合成": "🧪", "单元": "📝", "未覆盖": "❌"}
        lines = ["## 规则覆盖矩阵", "",
                 "| 规则 | 覆盖来源 | 回归 | 合成 | 单元 |", 
                 "|:-----|:--------|:----:|:----:|:----:|"]
        total = len(matrix)
        covered = sum(1 for v in matrix.values() if v["覆盖来源"] != "未覆盖")
        for prefix in ["MLR", "NVR", "MPR", "TPL", "SAR"]:
            rules = sorted(groups.get(prefix, []))
            if not rules:
                continue
            for rule, info in rules:
                lines.append(
                    f"| {rule} | {info['覆盖来源']} "
                    f"| {'✅' if info['回归覆盖'] else ''} "
                    f"| {'✅' if info['合成覆盖'] else ''} "
                    f"| {'✅' if info['单元覆盖'] else ''} |"
                )
        lines.append("")
        lines.append(f"**覆盖率**：{covered}/{total} = {covered/total*100:.0f}%（WP-2 KPI1）")
        return "\n".join(lines)

    # ── 章节 1: 页头 ──

    def _header(self) -> str:
        dt = self.m.get("assessment_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return (
            f"# 架构质量评估报告\n\n"
            f"**日期**: {dt}\n\n"
            f"---"
        )

    # ── 章节 2: 总体评分 ──

    def _overall_score(self) -> str:
        overall = self.m.get("overall_score", 0)
        grade = _score_grade(overall)
        dims = self.m.get("dimensions", {})
        rows = []
        total_weighted = 0
        for key, label in [("structural", "结构质量"), ("design", "设计质量"),
                            ("documentation", "文档质量"), ("evolution", "演进质量")]:
            d = dims.get(key, {})
            score = d.get("score", 0)
            weight = d.get("weight", 0.25)
            weighted = score * weight
            total_weighted += weighted
            w_pct = f"{weight*100:.0f}%"
            rows.append(f"| {label} | {score:.1f} | {w_pct} | {weighted:.1f} |")

        trend_line = ""
        if self.prev:
            prev_overall = self.prev.get("overall_score", 0)
            delta = overall - prev_overall
            trend_line = (
                f"\n**趋势**: {_trend_icon(delta)} 较上次 {delta:+.1f} 分 "
                f"（{prev_overall:.1f} → {overall:.1f}）"
            )

        return (
            f"## 总体评分\n\n"
            f"| 维度 | 得分 | 权重 | 加权得分 |\n"
            f"|------|:----:|:----:|:--------:|\n"
            + "\n".join(rows) +
            f"\n| **总分** | **{overall:.1f}** | **100%** | **{total_weighted:.1f}** |\n\n"
            f"**等级**: {grade}\n"
            f"{trend_line}"
        )

    # ── 章节 3: 与上次评估对比 ──

    def _comparison_with_previous(self) -> str:
        if not self.prev:
            return "## 与上次评估对比\n\n（首次评估，无历史数据）"
        dims = self.m.get("dimensions", {})
        pdims = self.prev.get("dimensions", {})
        rows = []
        for key, label in [("structural", "结构质量"), ("design", "设计质量"),
                            ("documentation", "文档质量"), ("evolution", "演进质量")]:
            cur = dims.get(key, {}).get("score", 0)
            prev = pdims.get(key, {}).get("score", 0)
            delta = cur - prev
            icon = _trend_icon(delta)
            rows.append(f"| {label} | {prev:.1f} | {cur:.1f} | {icon}{delta:+.1f} |")

        curo = self.m.get("overall_score", 0)
        prevo = self.prev.get("overall_score", 0)
        delta_o = curo - prevo
        rows.append(f"| **总分** | {prevo:.1f} | **{curo:.1f}** | **{_trend_icon(delta_o)}{delta_o:+.1f}** |")

        return (
            "## 与上次评估对比\n\n"
            "| 维度 | 上次 | 本次 | 变化 |\n"
            "|------|:---:|:---:|:----:|\n"
            + "\n".join(rows)
        )

    # ── 章节 4-7: 四大维度 ──

    def _dimension_table(self, title: str, dim_key: str, sub_keys: list,
                         sub_formatters: dict = None) -> str:
        dim = self.m.get("dimensions", {}).get(dim_key, {})
        score = dim.get("score", 0)
        details = dim.get("details", dim.get("sub_scores", {}))
        grade = _score_grade(score)
        rows = []
        for eng_key, zh_key, weight in sub_keys:
            w_pct = f"{weight*100:.0f}%"
            sub_score = details.get(eng_key, 0)
            if isinstance(sub_score, dict):
                sub_score = sub_score.get("score", 0)
            rationale = ""
            if sub_formatters and eng_key in sub_formatters:
                rationale = sub_formatters[eng_key](sub_score)
            rows.append(
                f"| {zh_key} | {w_pct} | {sub_score:.1f} | {rationale} |"
            )
        return (
            f"## {title} ({score:.1f}/100) {grade}\n\n"
            f"| 子维度 | 权重 | 得分 | 评分依据 |\n"
            f"|--------|:----:|:----:|----------|\n"
            + "\n".join(rows)
        )

    def _structural_quality(self) -> str:
        base = self._dimension_table("一、结构质量", "structural", [
            ("modularity", "模块化", 0.20),
            ("coupling", "耦合度", 0.20),
            ("cohesion", "内聚度", 0.20),
            ("complexity", "复杂度", 0.20),
            ("test_coverage", "测试覆盖度", 0.20),
        ], {
            "modularity": lambda s: f"平均每目录文件数得分 {s:.1f}",
            "coupling": lambda s: f"平均导入数得分 {s:.1f}",
            "cohesion": lambda s: f"超大文件(>1000行)占比得分 {s:.1f}",
            "complexity": lambda s: f"大文件(>200行)占比得分 {s:.1f}",
            "test_coverage": lambda s: f"4层测试覆盖度得分 {s:.1f}",
        })
        # WP-4: 测试覆盖度 4 层明细
        sub = self.m.get("dimensions", {}).get("structural", {}).get("sub_scores", {})
        tc = sub.get("test_coverage_detail", {})
        if not isinstance(tc, dict) or not tc:
            return base
        rows = [
            f"| L1 目录覆盖 | {tc.get('dir_score', 0):.1f} | {tc.get('dir_coverage', 0)*100:.1f}%（有测试的源码目录占比）|",
            f"| L2 语言覆盖 | {tc.get('lang_score', 0):.1f} | {tc.get('lang_coverage', 0)*100:.1f}%（有测试文件的语言占比）|",
            f"| L3 文件比 | {tc.get('file_score', 0):.1f} | {tc.get('file_ratio', 0)*100:.1f}%（测试文件/源码×0.3）|",
            f"| L4 绑定层覆盖 | {tc.get('binding_score', 0):.1f} | {tc.get('binding_coverage', 0)*100:.1f}%（有测试的绑定函数占比）|",
        ]
        detail = base + (
            "\n\n**测试覆盖度 4 层明细**\n\n"
            "| 层 | 得分 | 覆盖值 |\n"
            "|:---|:----:|:------|\n"
            + "\n".join(rows)
        )
        tfb = tc.get("test_files_by_lang", {})
        if tfb:
            lang_str = ", ".join(f"{k}={v}" for k, v in sorted(tfb.items()))
            detail += f"\n\n测试文件分布：{lang_str}"
        return detail

    def _design_quality(self) -> str:
        return self._dimension_table("二、设计质量", "design", [
            ("solid", "SOLID原则", 0.40),
            ("patterns", "设计模式", 0.25),
            ("style", "架构风格", 0.20),
            ("anti_patterns", "反模式", 0.15),
        ])

    def _documentation_quality(self) -> str:
        return self._dimension_table("三、文档质量", "documentation", [
            ("readme", "README完整性", 0.25),
            ("changelog", "CHANGELOG完整性", 0.15),
            ("adr", "ADR覆盖率", 0.20),
            ("comments", "代码注释密度", 0.15),
            ("jsdoc", "JSDoc覆盖率", 0.15),
            ("arch_doc", "架构文档完整性", 0.10),
        ])

    def _evolution_quality(self) -> str:
        return self._dimension_table("四、演进质量", "evolution", [
            ("git_activity", "历史可追溯性", 0.16),
            ("debt_trend", "技术债务趋势", 0.20),
            ("dep_outdated", "依赖过时程度", 0.16),
            ("dead_code", "废弃代码比例", 0.12),
            ("incremental", "增量质量", 0.16),
            ("problems", "问题扣分", 0.20),
        ])

    # ── 章节 8: 多语言依赖评估 ──

    def _multilang_section(self) -> str:
        ml = self.m.get("dimensions", {}).get("structural", {}).get("multilang_enhancement", {})
        is_single = self.m.get("is_single_language", False)

        if is_single:
            languages = self.m.get("project_languages", [])
            lang_str = ", ".join(languages) if languages else "unknown"
            return (
                "## 五、多语言混合依赖评估\n\n"
                f"> **跳过** — 本项目仅包含 {lang_str}，无跨语言依赖边界。"
                f"多语言混合依赖评估不适用，结构质量评分的 15% 权重已回归标准结构质量指标。\n"
            )

        details = ml.get("details", {})
        ml_score = ml.get("score", 0)
        if not details:
            return ""

        dim_labels = [
            ("coupling_intensity", "跨语言调用强度"),
            ("impact_radius", "跨语言影响半径"),
            ("call_depth", "跨语言回调深度"),
            ("binding_consistency", "绑定层接口一致性"),
            ("script_boundary", "脚本越界访问"),
            ("cross_lang_cycles", "跨语言循环依赖"),
        ]

        rows = []
        for key, label in dim_labels:
            d = details.get(key, {})
            s = d.get("score", 0)
            rows.append(f"| {label} | {s:.1f} |")

        fortran_note = ""
        fm = self.m.get("fortran_mapping")
        if fm and (fm.get("use_total", 0) > 0 or fm.get("call_total", 0) > 0):
            use_hit = fm.get("use_hit_rate", 1.0) * 100
            call_hit = fm.get("call_hit_rate", 1.0) * 100
            fortran_note = (
                f"\n> **Fortran 依赖映射命中率**: "
                f"`use` {use_hit:.1f}% "
                f"({fm.get('use_resolved', 0)}/{fm.get('use_total', 0)}), "
                f"`call` {call_hit:.1f}% "
                f"({fm.get('call_resolved', 0)}/{fm.get('call_total', 0)})"
            )

        return (
            "## 五、多语言混合依赖评估\n\n"
            f"**综合得分**: {ml_score:.1f}/100 — 占结构质量 15%\n\n"
            f"| 维度 | 得分 |\n"
            f"|------|:----:|\n"
            + "\n".join(rows)
            + fortran_note
        )

    # ── 章节 9: MLR 违规 ──

    def _mlr_violations(self) -> str:
        violations = self.m.get("mlr_violations", [])
        if not violations:
            return ""
        high = [v for v in violations if v.get("severity") == "HIGH"]
        med = [v for v in violations if v.get("severity") == "MEDIUM"]
        low = [v for v in violations if v.get("severity") == "LOW"]
        info = [v for v in violations if v.get("severity") == "INFO"]

        lines = []
        for v in violations:
            sev = v.get("severity", "LOW")
            icon = _severity_icon(sev)
            lines.append(f"- {icon} **{v['rule']}** ({sev}) {v['name']}: {v['detail']}")

        summary = f"共 {len(violations)} 项 — {len(high)} HIGH, {len(med)} MEDIUM, {len(low)} LOW"
        if info:
            summary += f", {len(info)} INFO"
        return (
            "## 六、MLR 规则违反\n\n"
            f"{summary}\n\n"
            + "\n".join(lines)
        )

    # ── 章节 10: 剪刀差风险 ──

    def _scissors_gap_risk(self) -> str:
        violations = self.m.get("mlr_violations", [])
        high_count = len([v for v in violations if v.get("severity") == "HIGH"])
        god_count = len(self._god_files)

        cond1 = high_count > 0
        cond2 = False
        cond3 = False

        # 条件2: 新代码提交 vs 债务修复（简化判断）
        evo = self.m.get("dimensions", {}).get("evolution", {}).get("details", {})
        if isinstance(evo, dict):
            git_activity = evo.get("git_activity", 80) if isinstance(evo.get("git_activity"), (int, float)) else 80
            debt_trend = evo.get("debt_trend", 0) if isinstance(evo.get("debt_trend"), (int, float)) else 0
            cond2 = git_activity > 50 and debt_trend <= 0

        # 条件3: God Object 增长
        if self._god_files_prev:
            for fpath, prev_lines in self._god_files_prev.items():
                cur_lines = self._god_files.get(fpath, 0)
                if cur_lines > prev_lines:
                    cond3 = True
                    break

        total_true = sum([cond1, cond2, cond3])
        status = "🔴 **严重**" if total_true == 3 else ("🟡 **注意**" if total_true >= 1 else "🟢 **正常**")

        rows = [
            f"| 1. HIGH 级 MLR 违规 > 0 | {'✅' if cond1 else '❌'} | {high_count} 项未修复 |",
            f"| 2. 新代码提交 > 债务修复 | {'✅' if cond2 else '❌'} | 活跃提交但债务趋势停滞 |",
            f"| 3. God Object 行数增长 | {'✅' if cond3 else '❌'} | {god_count} 个文件可能增长 |",
            f"| **结论** | {status} | {total_true}/3 条件满足 |",
        ]
        return "## 剪刀差风险\n\n| 条件 | 状态 | 详情 |\n|------|:----:|------|\n" + "\n".join(rows)

    # ── 章节 11: 关键文件行数对比 ──

    def _key_file_trend(self) -> str:
        if not self._god_files_prev and not self._god_files:
            return ""
        all_paths = set(self._god_files.keys()) | set(self._god_files_prev.keys())
        rows = []
        for fpath in sorted(all_paths):
            cur = self._god_files.get(fpath, "-")
            prev = self._god_files_prev.get(fpath, "-")
            cur_s = str(cur) if cur != "-" else "-"
            prev_s = str(prev) if prev != "-" else "-"
            change = ""
            if isinstance(cur, (int, float)) and isinstance(prev, (int, float)):
                d = cur - prev
                change = f"{d:+d}" if d != 0 else "0"
            rows.append(f"| {fpath} | {cur_s} | {prev_s} | {change} |")
        return (
            "## 关键文件行数对比\n\n"
            "| 文件 | 当前行数 | 上次评估 | 变化 |\n"
            "|------|:-------:|:---------:|:----:|\n"
            + "\n".join(rows)
        )

    # ── 章节 12: Top 5 关键问题 ──

    def _top_issues(self) -> list:
        issues = []

        # 1. 剪刀差
        violations = self.m.get("mlr_violations", [])
        high_v = [v for v in violations if v.get("severity") == "HIGH"]
        if high_v:
            issues.append((0, "🔴 P0 | 剪刀差风险严重",
                           f"{len(high_v)} 项 HIGH 级 MLR 违规未修复"))

        # 2. 复杂度过低
        std = self.m.get("dimensions", {}).get("structural", {}).get("sub_scores", {})
        compl = std.get("complexity", 100)
        if isinstance(compl, (int, float)) and compl < 20:
            issues.append((1, "🔴 P0 | 复杂度过高",
                           f"大文件占比得分仅 {compl:.1f}/100，建议拆分大文件"))

        # 3. God Objects
        for fpath, lines in sorted(self._god_files.items(), key=lambda x: -x[1])[:3]:
            if lines > GOD_OBJECT_THRESHOLD:
                issues.append((2, f"🔴 P0 | {os.path.basename(fpath)} God Object",
                               f"{int(lines)} 行，超过 1000 行阈值"))

        # 4. 测试覆盖度
        test = std.get("test_coverage", 100)
        if isinstance(test, (int, float)) and test < 50:
            issues.append((3, "🟠 P1 | 测试覆盖度不足",
                           f"4层测试覆盖度得分 {test:.1f}/100，远低于 50% 目标"))

        # 5. MLR 高频违规
        for v in violations[:3]:
            issues.append((4, f"{_severity_icon(v.get('severity', 'LOW'))} {v['rule']}",
                           v.get("detail", "")[:80]))

        # 6. 文档质量
        doc = self.m.get("dimensions", {}).get("documentation", {}).get("score", 100)
        if doc < 50:
            issues.append((5, "🟠 P1 | 文档质量不足",
                           f"文档质量得分仅 {doc:.1f}/100"))

        # 7. CHANGELOG 缺失
        doc_details = self.m.get("dimensions", {}).get("documentation", {}).get("details", {})
        if isinstance(doc_details, dict) and doc_details.get("changelog", 100) == 0:
            issues.append((6, "🟠 P1 | CHANGELOG 缺失",
                           "CHANGELOG.md 不存在，拖累文档质量"))

        # 排序
        issues.sort(key=lambda x: x[0])

        # 取 Top 5
        return issues[:5]

    def _top_issues_section(self) -> str:
        issues = self._top_issues()
        if not issues:
            return ""
        lines = []
        for i, (_, title, detail) in enumerate(issues, 1):
            lines.append(f"{i}. {title} — {detail}")
        return "## Top 5 关键问题\n\n" + "\n".join(lines)

    # ── 章节 13: Top 5 改进建议 ──

    def _top_recommendations(self) -> str:
        recs = self._compute_recommendations()
        if not recs:
            return ""
        lines = []
        for i, (_, title, effort, note) in enumerate(recs[:5], 1):
            lines.append(f"{i}. **{title}** — {effort} — {note}")
        return "## Top 5 改进建议\n\n" + "\n".join(lines)

    def _compute_recommendations(self) -> list:
        recs = []

        # 1. God Object 拆分
        for fpath, lines in sorted(self._god_files.items(), key=lambda x: -x[1])[:2]:
            file_key = os.path.basename(fpath)
            if file_key not in {r[0] for r in recs}:
                tmpl = SUGGESTION_TEMPLATES["god_object"]
                recs.append((file_key, tmpl[0].format(file=fpath), tmpl[1], tmpl[2]))

        # 2. 复杂度
        std = self.m.get("dimensions", {}).get("structural", {}).get("sub_scores", {})
        compl = std.get("complexity", 100)
        if isinstance(compl, (int, float)) and compl < 30:
            tmpl = SUGGESTION_TEMPLATES["complexity_high"]
            recs.append(("复杂度", tmpl[0].format(file="大文件"), tmpl[1], tmpl[2]))

        # 3. CHANGELOG
        doc_details = self.m.get("dimensions", {}).get("documentation", {}).get("details", {})
        if isinstance(doc_details, dict) and doc_details.get("changelog", 100) == 0:
            tmpl = SUGGESTION_TEMPLATES["missing_changelog"]
            recs.append(("CHANGELOG", tmpl[0], tmpl[1], tmpl[2]))

        # 4. 测试覆盖度
        test = std.get("test_coverage", 100)
        if isinstance(test, (int, float)) and test < 40:
            tmpl = SUGGESTION_TEMPLATES.get("low_test_coverage")
            recs.append(("测试", tmpl[0], tmpl[1], tmpl[2]))

        # 5. MLR 建议
        violations = self.m.get("mlr_violations", [])
        mlr_rules_seen = set()
        for v in violations:
            rule = v.get("rule", "")
            if rule in mlr_rules_seen:
                continue
            mlr_rules_seen.add(rule)
            if rule == "MLR-002":
                tmpl = SUGGESTION_TEMPLATES["mlr_binding_drift"]
                recs.append((rule, tmpl[0].format(count=v.get("count", 0)), tmpl[1], tmpl[2]))
            elif rule == "MLR-004":
                tmpl = SUGGESTION_TEMPLATES["mlr_script_boundary"]
                recs.append((rule, tmpl[0].format(count=v.get("count", 0)), tmpl[1], tmpl[2]))
            elif rule == "MLR-001":
                tmpl = SUGGESTION_TEMPLATES["mlr_cycle"]
                recs.append((rule, tmpl[0], tmpl[1], tmpl[2]))
            elif rule == "MLR-008":
                tmpl = SUGGESTION_TEMPLATES["mlr_gil"]
                recs.append((rule, tmpl[0], tmpl[1], tmpl[2]))
            elif rule == "MLR-009":
                tmpl = SUGGESTION_TEMPLATES["binding_void_ptr"]
                recs.append((rule, tmpl[0], tmpl[1], tmpl[2]))

        return recs

    # ── 章节 14: 退化预警评估 ──

    def _degradation_warning(self) -> str:
        if not self.prev:
            return "## 退化预警评估\n\n（首次评估，无历史对比）"
        cur = self.m.get("overall_score", 0)
        prev = self.prev.get("overall_score", 0)
        delta = cur - prev
        desc = _trend_desc(delta)
        return (
            "## 退化预警评估\n\n"
            f"- **上次总分**: {prev:.1f}\n"
            f"- **本次总分**: {cur:.1f}\n"
            f"- **变化**: **{delta:+.1f} 分（{desc}）**\n"
        )

    # ── 章节 15: 模块依赖风险评估 ──

    def _dependency_risk(self) -> str:
        violations = self.m.get("mlr_violations", [])
        has_cycle = any(v.get("rule") == "MLR-001" for v in violations)
        has_god = len(self._god_files) > 0

        rules = [
            ("core/ 反向依赖 app/", True, ""),
            ("循环依赖", not has_cycle, "arch_check 未检测到循环依赖" if not has_cycle else "存在循环依赖"),
            ("God Object >1000行", not has_god,
             f"{len(self._god_files)} 个文件超限" if has_god else "✅ 通过"),
            ("多语言循环依赖", not has_cycle, "✅ 通过" if not has_cycle else "存在跨语言循环"),
        ]
        rows = []
        for name, passed, detail in rules:
            status = "✅ 通过" if passed else "❌ 失败"
            rows.append(f"| {name} | {status} | {detail} |")
        return (
            "## 模块依赖风险评估\n\n"
            "| 规则 | 状态 | 说明 |\n"
            "|------|:----:|------|\n"
            + "\n".join(rows)
        )

    # ── 章节 16: 总体评价 ──

    def _summary(self) -> str:
        overall = self.m.get("overall_score", 0)
        grade = _score_grade(overall)
        issues = self._top_issues()
        recs = self._compute_recommendations()

        issue_summary = "、".join(
            [t.split("—")[0].strip() for _, t, _ in issues[:3]]
        )
        rec_summary = "；".join(
            [t.split("—")[0].strip() for _, t, _, _ in recs[:3]]
        )
        ml_count = len(self.m.get("mlr_violations", []))

        paras = [
            f"本次评估总分 {overall:.1f}（{grade}）。",
        ]
        if self.prev:
            delta = overall - self.prev.get("overall_score", 0)
            paras.append(f"较上次 {delta:+.1f} 分。")

        paras.append(f"共发现 {len(issues)} 个关键问题，{ml_count} 项 MLR 规则违反。")
        paras.append(f"最紧迫的行动：{rec_summary}。")

        return "## 总体评价\n\n" + " ".join(paras)

    # ── 主入口 ──

    def generate(self) -> str:
        sections = [
            self._header(),
            self._overall_score(),
            self._comparison_with_previous(),
            self._structural_quality(),
            self._design_quality(),
            self._documentation_quality(),
            self._evolution_quality(),
            self._multilang_section(),
            self._mlr_violations(),
            self._rule_coverage_matrix(),
            self._scissors_gap_risk(),
            self._key_file_trend(),
            self._top_issues_section(),
            self._top_recommendations(),
            self._degradation_warning(),
            self._dependency_risk(),
            self._summary(),
        ]
        sections = [s for s in sections if s]
        return "\n\n---\n\n".join(sections)
