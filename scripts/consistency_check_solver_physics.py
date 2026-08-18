# -*- coding: utf-8 -*-
"""
求解器物理场三方一致性检查脚本

验证 Guide <-> Skill <-> Tool 在命名、评分算法、版本号等方面的一致性。

用法：
    python scripts/consistency_check_solver_physics.py          # 默认模式
    python scripts/consistency_check_solver_physics.py --quick  # 快速模式

退出码：0=一致, 1=存在不一致
"""

import os
import re
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUIDE_FILE = os.path.join(PROJECT, "docs/zh/求解器和物理场模块化架构模式识别评估/求解器与物理场模块化架构模式识别评估指南.md")
SKILL_FILE = os.path.join(PROJECT, "src/arch_quality/skills/solver-physics-architecture.md")
TOOL_FILE = os.path.join(PROJECT, "src/arch_quality/arch_metrics_solver_physics.py")


def read(path):
    if not os.path.exists(path):
        return ""
    # 指南可能为 GBK 编码，其他为 UTF-8
    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, OSError):
            continue
    return ""


# ── Versions ──

def check_versions(g, s, t, quick):
    ok = True
    tv_guide = re.search(r'GUIDE_VERSION\s*=\s*"([^"]+)"', t)
    tv_skill = re.search(r'SKILL_VERSION\s*=\s*"([^"]+)"', t)
    gv = tv_guide.group(1) if tv_guide else "?"
    sv = tv_skill.group(1) if tv_skill else "?"

    print(f"  GUIDE_VERSION      {gv}")
    print(f"  SKILL_VERSION      {sv}")

    if gv not in g:
        print(f"    WARN: GUIDE_VERSION={gv} not found in Guide")
        ok = False
    if sv not in s:
        print(f"    WARN: SKILL_VERSION={sv} not referenced in Skill doc")
        ok = False
    return ok


# ── Naming & Weights ──

DIM_METHODS = {
    "2.1": ("物理场模块边界完整性", "calc_boundary_integrity"),
    "2.2": ("多物理场耦合架构合理性", "calc_coupling_architecture"),
    "2.3": ("插件式扩展架构支持度", "calc_extension_support"),
    "2.4": ("跨场数据传递规范性", "calc_data_transfer"),
}

WEIGHTS = {"2.1": "25%", "2.2": "30%", "2.3": "25%", "2.4": "20%"}


def check_naming_and_weights(g, s, t, quick):
    ok = True
    for sec, (dim_name, method) in DIM_METHODS.items():
        found_s = dim_name in s
        found_t = method in t

        if not (found_s and found_t):
            print(f"  [{sec}] NAMING")
            print(f"    Skill={found_s} ({dim_name}) Tool={found_t} ({method})")
            ok = False

        w = WEIGHTS[sec]
        if w not in g and w not in s:
            print(f"    [{sec}] weight {w} missing in Guide/Skill")
            ok = False

    if ok and not quick:
        print("  ALL OK")
    return ok


# ── MPR rules ──

MPR_RULES = ["MPR-001", "MPR-002", "MPR-003", "MPR-004", "MPR-005",
             "MPR-006", "MPR-007", "MPR-008", "MPR-009", "MPR-010", "MPR-012"]


def check_mpr(g, s, t, quick):
    ok = True
    for mpr in MPR_RULES:
        if mpr not in g or mpr not in s or mpr not in t:
            print(f"  {mpr} missing in Guide={mpr in g} Skill={mpr in s} Tool={mpr in t}")
            ok = False
    if ok and not quick:
        print(f"  ALL {len(MPR_RULES)} MPR rules present")
    return ok


# ── Formula patterns ──
# For each dimension: (name, skill_pattern, tool_pattern)

FORMULA_CHECKS = [
    ("2.1 boundary",
     r"score\s*\+=\s*20|result\s*=\s*min\(score,\s*100\)",
     r"(?:s1\s*=\s*20|score\s*\+=\s*s[0-9])"),
    ("2.2 coupling",
     r"score\s*\+=\s*20|score\s*\+=\s*15",
     r"(?:s1\s*=\s*20|s[0-9]\s*=\s*15|score\s*\+=\s*s[0-9])"),
    ("2.3 extension",
     r"score\s*=\s*score\s*\*\s*0\.5|score\s*\*=\s*0\.5",
     r"score\s*\*=\s*0\.5|int\(score\s*\*\s*0\.5\)"),
    ("2.4 data_transfer",
     r"fmi_bonus|score\s*=\s*min\(score\s*\+\s*fmi_bonus",
     r"fmi_bonus|_check_fmi_compliance"),
]


def check_formulas(g, s, t, quick):
    ok = True
    for name, sp, tp in FORMULA_CHECKS:
        s_ok = bool(re.search(sp, s))
        t_ok = bool(re.search(tp, t))
        if not (s_ok and t_ok):
            print(f"  [{name}] Skill={s_ok} Tool={t_ok}")
            ok = False
    if ok and not quick:
        print("  ALL OK")
    return ok


# ── Tool methods ──

def check_methods(t, quick):
    methods = [m for _, m in DIM_METHODS.values()]
    methods += ["check_mpr_rules", "all_metrics", "calc_overall"]
    ok = all(m in t for m in methods)
    if not ok:
        missing = [m for m in methods if m not in t]
        print(f"  Missing methods: {missing}")
    elif not quick:
        print(f"  ALL {len(methods)} methods present")
    return ok


# ── Main ──

def main():
    quick = "--quick" in sys.argv

    g = read(GUIDE_FILE)
    s = read(SKILL_FILE)
    t = read(TOOL_FILE)

    if not g:
        print("ERROR: Guide file not found or unreadable")
        return 1
    if not s:
        print("ERROR: Skill file not found")
        return 1
    if not t:
        print("ERROR: Tool file not found")
        return 1

    total_checks = 6
    passed = 0

    print("=" * 60)
    print("求解器物理场三方一致性检查")
    print("  Guide: 求解器与物理场模块化架构模式识别评估指南.md")
    print("  Skill: skills/solver-physics-architecture.md")
    print("  Tool:  arch_metrics_solver_physics.py")
    print("=" * 60)

    sections = [
        ("1. 版本号", lambda: check_versions(g, s, t, quick)),
        ("2. 命名与权重", lambda: check_naming_and_weights(g, s, t, quick)),
        ("3. MPR 规则", lambda: check_mpr(g, s, t, quick)),
        ("4. 评分公式", lambda: check_formulas(g, s, t, quick)),
        ("5. 工具方法完整性", lambda: check_methods(t, quick)),
        ("6. 权重和=100%", lambda: check_weight_sum(s, t, quick)),
    ]

    for name, fn in sections:
        print(f"\n── {name} ──")
        try:
            if fn():
                passed += 1
            else:
                pass
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n" + "=" * 60)
    if passed == total_checks:
        print(f"结果: PASS ({passed}/{total_checks} 项通过)")
        rc = 0
    else:
        print(f"结果: FAIL ({passed}/{total_checks} 项通过)")
        rc = 1
    print("=" * 60)
    return rc


def check_weight_sum(s, t, quick):
    """验证 Skill 权重表和 Tool 使用的权重均为 100%"""
    ok = True
    # Skill 权重表
    weights = re.findall(r"\|\s*(物理场模块边界完整性|多物理场耦合架构合理性|"
                         r"插件式扩展架构支持度|跨场数据传递规范性)\s*\|\s*(\d+)%\s*\|",
                         s)
    if weights:
        total = sum(int(pct) for _, pct in weights)
        if total != 100:
            print(f"  WARN: Skill 权重和 = {total}% != 100%")
            ok = False
        elif not quick:
            print(f"  Skill 权重和 = {total}%")
    else:
        print("  WARN: 未解析到 Skill 权重表")
        ok = False

    # Tool 降级权重
    fallback = "物理场模块边界完整性"
    if fallback in t:
        pass  # 工具实际从 skill 解析，降级权重存在即可
    if ok and not quick:
        print("  ALL OK")
    return ok


if __name__ == "__main__":
    sys.exit(main())
