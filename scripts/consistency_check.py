# -*- coding: utf-8 -*-
"""
三方一致性检查脚本

验证 Guide <-> Skill <-> Tool 在命名、评分算法、版本号等方面的一致性。

用法：
    python scripts/consistency_check.py          # 默认模式（检查全部）
    python scripts/consistency_check.py --quick  # 快速模式（只检查版本号和评分公式）

退出码：0=一致, 1=存在不一致
"""

import os
import re
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUIDE_FILE = os.path.join(PROJECT, "docs/zh/数值算法正确性与精度保障评估指南.md")
SKILL_FILE = os.path.join(PROJECT, "src/arch_quality/skills/numerical-accuracy.md")
TOOL_FILE = os.path.join(PROJECT, "src/arch_quality/arch_metrics_numerical_accuracy.py")


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


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
        print(f"    WARN: GUIDE_VERSION={gv} not found in Guide title")
        ok = False
    if f"v{sv}" not in s and f"v{sv}" not in s:
        if sv not in s:
            print(f"    WARN: SKILL_VERSION={sv} not referenced in Skill doc")
            ok = False
    return ok


# ── Naming ──

DIM_NAMES = {
    "2.1": ["数值稳定性保障"],
    "2.2": ["舍入误差", "舍入误差与数值敏感度控制"],
    "2.3": ["代码验证完备性", "验证完备性"],
    "2.4": ["解验证与误差量化", "误差估计与控制"],
    "2.5": ["数值回归测试覆盖"],
    "2.6": ["数值债务密度"],
}

WEIGHTS = {"2.1": "25%", "2.2": "20%", "2.3": "20%", "2.4": "15%", "2.5": "10%", "2.6": "10%"}


def check_naming_and_weights(g, s, t, quick):
    ok = True
    for sec, names in DIM_NAMES.items():
        found_g = any(n in g for n in names)
        found_s = any(n in s for n in names)
        found_t_method = sec in {
            "2.1": "calc_numerical_stability",
            "2.2": "calc_roundoff_sensitivity",
            "2.3": "calc_mms_verification",
            "2.4": "calc_error_estimation",
            "2.5": "calc_regression_coverage",
            "2.6": "calc_numerical_debt",
        }.keys()

        method = {
            "2.1": "calc_numerical_stability",
            "2.2": "calc_roundoff_sensitivity",
            "2.3": "calc_mms_verification",
            "2.4": "calc_error_estimation",
            "2.5": "calc_regression_coverage",
            "2.6": "calc_numerical_debt",
        }[sec]
        found_t = method in t

        if not (found_g and found_s and found_t):
            print(f"  [{sec}] NAMING")
            print(f"    Guide={found_g} ({names}) Skill={found_s} Tool={found_t} ({method})")
            ok = False

        # Weight
        w = WEIGHTS[sec]
        if w not in g and w not in s:
            print(f"    [{sec}] weight {w} missing in Guide/Skill")
            ok = False

    if ok and not quick:
        print("  ALL OK")
    return ok


# ── NVR rules ──

NVR_RULES = ["NVR-001", "NVR-002", "NVR-003", "NVR-004", "NVR-005",
             "NVR-006", "NVR-007", "NVR-008", "NVR-010", "NVR-011", "NVR-012"]


def check_nvr(g, s, t, quick):
    ok = True
    for nvr in NVR_RULES:
        if nvr not in g or nvr not in s or nvr not in t:
            print(f"  {nvr} missing in Guide={nvr in g} Skill={nvr in s} Tool={nvr in t}")
            ok = False
    if ok and not quick:
        print("  ALL 11 NVR rules present")
    return ok


# ── Formula patterns ──

# For each dimension: (section, guide_pattern, skill_pattern, tool_docstring_pattern)
FORMULA_CHECKS = [
    ("2.1 stability",
     r"(PASS|FAIL|WARNING|隐式格式|CFL)",
     r"(score\s*=\s*100|score\s*=\s*80|score\s*=\s*70|score\s*=\s*50|score\s*=\s*30|score\s*=\s*10)",
     r"calc_numerical_stability"),
    ("2.2 roundoff",
     r"基础分\s*=\s*100",
     r"base\s*=\s*100",
     r"calc_roundoff_sensitivity"),
    ("2.3 mms",
     r"if\s+V\s*==\s*FALSE.*score\s*=\s*0",
     r"score\s*=\s*0",
     r"calc_mms_verification"),
    ("2.4 error",
     r"score\s*=\s*\(E_d\s*\*\s*50\)\s*\+\s*\(E_i\s*\*\s*50\)",
     r"score\s*\+?=\s*40",
     r"calc_error_estimation"),
    ("2.5 regression",
     r"coverage\s*=\s*N_tested\s*/\s*N_critical",
     r"N_tested\s*/\s*N_critical",
     r"calc_regression_coverage"),
    ("2.6 debt",
     r"debt_ratio\s*=\s*low_score_count\s*/\s*6",
     r"debt_ratio\s*=\s*low_score_count\s*/\s*6",
     r"debt_ratio\s*=\s*low_score_count\s*/\s*max"),
]


def check_formulas(g, s, t, quick):
    ok = True
    for name, gp, sp, tp in FORMULA_CHECKS:
        g_ok = bool(re.search(gp, g))
        s_ok = bool(re.search(sp, s))
        t_ok = bool(re.search(tp, t))
        if not (g_ok and s_ok and t_ok):
            print(f"  [{name}] Guide={g_ok} Skill={s_ok} Tool={t_ok}")
            ok = False
    if ok and not quick:
        print("  ALL OK")
    return ok


# ── Confidence annotations ──

CONFIDENCE_DIMS = {
    "2.1": ("中", "中"),
    "2.2": ("中低", "中低"),
    "2.3": ("中", "中"),
    "2.4": ("中", "中"),
    "2.5": ("高", "高"),
    "2.6": ("高", "高"),
}


def check_confidence(g, s, quick):
    ok = True
    for sec, (guide_conf, skill_conf) in CONFIDENCE_DIMS.items():
        g_ok = guide_conf in g  # rough check
        if not g_ok and not quick:
            print(f"  [{sec}] Guide confidence '{guide_conf}' not found")
            ok = False
    if ok and not quick:
        print("  ALL OK")
    return ok


# ── Main ──

def main():
    quick = "--quick" in sys.argv

    g = read(GUIDE_FILE)
    s = read(SKILL_FILE)
    t = read(TOOL_FILE)

    total_checks = 6
    passed = 0

    print("=" * 60)
    print("三方一致性检查")
    print("  Guide: 数值算法正确性与精度保障评估指南.md")
    print("  Skill: skills/numerical-accuracy.md")
    print("  Tool:  arch_metrics_numerical_accuracy.py")
    print("=" * 60)

    sections = [
        ("1. 版本号", lambda: check_versions(g, s, t, quick)),
        ("2. 命名与权重", lambda: check_naming_and_weights(g, s, t, quick)),
        ("3. NVR 规则", lambda: check_nvr(g, s, t, quick)),
        ("4. 评分公式", lambda: check_formulas(g, s, t, quick)),
        ("5. 置信度标注", lambda: check_confidence(g, s, quick)),
        ("6. 工具方法完整性", lambda: check_methods(t, quick)),
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


def check_methods(t, quick):
    methods = ["calc_numerical_stability", "calc_roundoff_sensitivity",
               "calc_mms_verification", "calc_error_estimation",
               "calc_regression_coverage", "calc_numerical_debt"]
    ok = all(m in t for m in methods)
    if not ok:
        missing = [m for m in methods if m not in t]
        print(f"  Missing methods: {missing}")
    elif not quick:
        print(f"  ALL {len(methods)} methods present")
    return ok


if __name__ == "__main__":
    sys.exit(main())
