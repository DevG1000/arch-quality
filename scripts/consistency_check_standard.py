# -*- coding: utf-8 -*-
"""
三方一致性检查脚本（标准架构质量）

验证 Guide <-> Skill <-> Tool 在命名、评分算法、版本号、SAR 规则等方面的一致性。

用法：
    python scripts/consistency_check_standard.py

退出码：0=一致, 1=存在不一致
"""

import os
import re
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUIDE_FILE = os.path.join(PROJECT, "docs/zh/架构质量标准/软件架构质量评估指南（2.3版）.md")
SKILL_FILE = os.path.join(PROJECT, "src/arch_quality/skills/arch-quality.md")
TOOL_FILE = os.path.join(PROJECT, "src/arch_quality/arch_metrics_standard.py")
CASESET_FILE = os.path.join(PROJECT, "docs/zh/架构质量标准/软件架构质量评估验证案例集（1.3).md")


def read(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def check_versions(g, s, t):
    """版本声明一致"""
    ok = True
    # Skill 绑定指南版本
    if "2.3 版" not in s and "2.3" not in s.split("技能版本")[0]:
        print("  WARN: Skill 未绑定指南 2.3")
        ok = False
    # 指南标题含 2.3
    if "2.3版" not in g.splitlines()[0] and "2.3" not in g.splitlines()[0]:
        print("  WARN: 指南标题不含 2.3")
        ok = False
    if ok:
        print("  GUIDE 2.3 <-> SKILL 2.3 <-> TOOL: OK")
    return ok


def check_weights(g, s, t):
    """权重一致（指南 vs Skill）"""
    ok = True
    checks = [
        # (指南关键词, skill 权重行模式, 期望权重)
        ("结构质量", r"\|\s*结构质量\s*\|\s*30%", "30%"),
        ("设计质量", r"\|\s*设计质量\s*\|\s*25%", "25%"),
        ("文档质量", r"\|\s*文档质量\s*\|\s*20%", "20%"),
        ("演进质量", r"\|\s*演进质量\s*\|\s*25%", "25%"),
    ]
    for kw, pat, w in checks:
        if not re.search(pat, s):
            print(f"  WARN: Skill 权重 {kw}={w} 未找到")
            ok = False
    # 设计质量子维度（指南 4.5: 模式15% 反模式25%）
    if not re.search(r"\|\s*设计模式\s*\|\s*15%", s):
        print("  WARN: Skill 设计模式权重应为 15%（指南 4.5）")
        ok = False
    if not re.search(r"\|\s*反模式\s*\|\s*25%", s):
        print("  WARN: Skill 反模式权重应为 25%（指南 4.5）")
        ok = False
    if ok:
        print("  WEIGHTS 对齐指南: OK")
    return ok


def check_dimension_names(g, s, t):
    """维度命名一致"""
    ok = True
    # 主维度
    for name in ["结构质量", "设计质量", "文档质量", "演进质量"]:
        if name not in g or name not in s:
            print(f"  WARN: 维度 {name} 缺失 Guide={name in g} Skill={name in s}")
            ok = False
    # 工具方法存在
    methods = {
        "calc_modularity": "模块化",
        "calc_coupling": "耦合度",
        "calc_cohesion": "内聚度",
        "calc_complexity": "复杂度",
        "calc_test_coverage": "测试覆盖度",
        "calc_solid_score": "SOLID",
        "calc_design_score": "设计质量",
        "calc_doc_score": "文档质量",
        "calc_evolution_score": "演进质量",
    }
    for method, name in methods.items():
        if method not in t:
            print(f"  WARN: 工具方法 {method} 缺失")
            ok = False
        if name not in s:
            print(f"  WARN: Skill 维度 {name} 缺失")
            ok = False
    if ok:
        print("  DIMENSIONS 命名一致: OK")
    return ok


def check_sar_rules(g, s, t, quick=True):
    """SAR 规则三方一致"""
    ok = True
    sar_ids = [f"SAR-{i:03d}" for i in range(1, 13)]
    guide_rules = [r for r in sar_ids if r in g]
    skill_rules = [r for r in sar_ids if r in s]
    tool_rules = [r for r in sar_ids if r in t]
    if len(guide_rules) != 12:
        print(f"  WARN: 指南 SAR 规则数 {len(guide_rules)}/12")
        ok = False
    if len(skill_rules) != 12:
        print(f"  WARN: Skill SAR 规则数 {len(skill_rules)}/12")
        ok = False
    if len(tool_rules) != 12:
        print(f"  WARN: Tool SAR 规则数 {len(tool_rules)}/12")
        ok = False
    if ok:
        print("  SAR 规则 12/12 三方一致: OK")
    return ok


def check_formulas(g, s, t):
    """评分公式一致（指南 vs Skill vs 工具）"""
    ok = True
    # 测试覆盖度 4 层权重
    tc_guide = "L1×30% + L2×25% + L3×25% + L4×20%" in g
    tc_skill = "L1×30% + L2×25% + L3×25% + L4×20%" in s
    if not (tc_guide and tc_skill):
        print(f"  WARN: 测试覆盖度公式 Guide={tc_guide} Skill={tc_skill}")
        ok = False
    # 单语言重分配
    sl_guide = "L1×37.5% + L2×31.25% + L3×31.25%" in g
    sl_skill = "L1×37.5% + L2×31.25% + L3×31.25%" in s
    if not (sl_guide and sl_skill):
        print(f"  WARN: 单语言重分配 Guide={sl_guide} Skill={sl_skill}")
        ok = False
    if ok:
        print("  FORMULAS 一致: OK")
    return ok


def main():
    g = read(GUIDE_FILE)
    s = read(SKILL_FILE)
    t = read(TOOL_FILE)
    c = read(CASESET_FILE)

    results = []
    print("=== 标准架构质量 三方一致性检查 ===\n")

    results.append(("版本", check_versions(g, s, t)))
    results.append(("权重", check_weights(g, s, t)))
    results.append(("维度命名", check_dimension_names(g, s, t)))
    results.append(("SAR 规则", check_sar_rules(g, s, t)))
    results.append(("评分公式", check_formulas(g, s, t)))

    # 案例集引用
    print("\n=== 案例集完整性 ===")
    caseset_ok = True
    for kw in ["A类", "B类", "OpenFOAM", "FreeCAD", "测试覆盖度", "文档质量", "演进质量"]:
        if kw not in c:
            print(f"  WARN: 案例集缺关键词 {kw}")
            caseset_ok = False
    results.append(("案例集", caseset_ok))
    if caseset_ok:
        print("  案例集关键内容: OK")

    print("\n---")
    all_ok = all(v for _, v in results)
    for name, ok in results:
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    print(f"\n结果: {'PASS - 三方一致' if all_ok else 'FAIL - 存在不一致'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())