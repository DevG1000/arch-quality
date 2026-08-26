# -*- coding: utf-8 -*-
"""
gen_rule_coverage_matrix.py — 规则覆盖矩阵自动生成器（WP-2）

从回归快照、合成项目、单元/变异测试自动提取规则覆盖状态，
生成 JSON 覆盖矩阵（可 diff 校验），并可选生成 Markdown 摘要。

用法：
    python scripts/gen_rule_coverage_matrix.py            # 生成 JSON
    python scripts/gen_rule_coverage_matrix.py --check    # 校验（exit 1 若未覆盖）

输出：
    docs/zh/计划/rule_coverage_matrix.json   (JSON，可 diff)
"""

import json
import os
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SNAP_DIR = PROJECT / "tests" / "regression" / "snapshots"
TESTS_DIR = PROJECT / "tests"
OUT_JSON = PROJECT / "docs" / "zh" / "计划" / "rule_coverage_matrix.json"

ALL_RULES = [
    # 多语言（14）
    "MLR-001", "MLR-001b", "MLR-002", "MLR-003", "MLR-004", "MLR-004b",
    "MLR-005", "MLR-006", "MLR-007", "MLR-008", "MLR-009", "MLR-010",
    "MLR-011", "MLR-012",
    # 数值（11，NVR-009 空洞）
    "NVR-001", "NVR-002", "NVR-003", "NVR-004", "NVR-005", "NVR-006",
    "NVR-007", "NVR-008", "NVR-010", "NVR-011", "NVR-012",
    # 物理场（11，MPR-011 空洞）
    "MPR-001", "MPR-002", "MPR-003", "MPR-004", "MPR-005", "MPR-006",
    "MPR-007", "MPR-008", "MPR-009", "MPR-010", "MPR-012",
    # 模板（12，当前 MLR-013~024，WP-7 将改 TPL）
    "MLR-013", "MLR-014", "MLR-015", "MLR-016", "MLR-017", "MLR-018",
    "MLR-019", "MLR-020", "MLR-021", "MLR-022", "MLR-023", "MLR-024",
    # 标准（12）
    "SAR-001", "SAR-002", "SAR-003", "SAR-004", "SAR-005", "SAR-006",
    "SAR-007", "SAR-008", "SAR-009", "SAR-010", "SAR-011", "SAR-012",
]

RULE_PAT = re.compile(r"\b(MLR|NVR|MPR|TPL|SAR)-(\d+)([a-z]?)\b")

# 合成项目 → 触发规则映射（WP-2 新增）
SYNTHETIC_MAP = {
    "mlr002_no_binding": ["MLR-002"],
    "mlr002_with_binding": [],
    "mlr007_tnt": ["MLR-007"],
    "mlr009_generic": ["MLR-009"],
    "mlr011_loop_calls": ["MLR-011"],
    "mpr004_mismatch": ["MPR-004"],
}


def _extract_rules_from_text(text):
    return set(m.group(0) for m in RULE_PAT.finditer(text))


def _extract_regression_rules():
    """从回归快照提取规则"""
    rules = set()
    for fn in os.listdir(SNAP_DIR):
        if not fn.endswith(".json"):
            continue
        try:
            d = json.load(open(SNAP_DIR / fn, encoding="utf-8-sig"))
        except Exception:
            continue
        rules.update(d.get("required_mlr_rules", []))
        # violations 可能是 dict（key 含 |）或 list（rule 字段）
        for key in ("mlr_violations", "mpr_violations", "nvr_violations",
                    "sar_violations"):
            v = d.get(key, {}) or {}
            if isinstance(v, dict):
                for k in v.keys():
                    rules.update(m.group(0) for m in RULE_PAT.finditer(k))
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        rid = item.get("rule", "")
                        if RULE_PAT.match(rid):
                            rules.add(rid)
    # numerical_baselines 子目录
    nb = SNAP_DIR / "numerical_baselines"
    if nb.is_dir():
        for fn in os.listdir(nb):
            if not fn.endswith(".json"):
                continue
            try:
                d = json.load(open(nb / fn, encoding="utf-8-sig"))
            except Exception:
                continue
            for v in d.get("nvr_violations", []) or []:
                rid = v.get("rule", "") if isinstance(v, dict) else ""
                if RULE_PAT.match(rid):
                    rules.add(rid)
    return rules


def _extract_unit_rules():
    """从单元测试 + 变异测试 + mutation cases 提取规则"""
    rules = set()
    for fn in os.listdir(TESTS_DIR):
        if fn.startswith("test_") and fn.endswith(".py"):
            rules |= _extract_rules_from_text((TESTS_DIR / fn).read_text(
                encoding="utf-8-sig"))
    mut_dir = TESTS_DIR / "mutation"
    if mut_dir.is_dir():
        for fn in os.listdir(mut_dir):
            if fn.endswith(".py"):
                rules |= _extract_rules_from_text((mut_dir / fn).read_text(
                    encoding="utf-8-sig"))
            elif fn.endswith(".json"):
                try:
                    cases = json.load(open(mut_dir / fn, encoding="utf-8-sig"))
                except Exception:
                    continue
                for c in cases:
                    exp = c.get("expected", {})
                    for key in ("sar_rules_changed", "nvr_rules_changed",
                                "mpr_rules_changed", "rules_changed"):
                        for r in exp.get(key, []) or []:
                            rules.add(r)
    return rules


def _extract_synthetic_rules():
    """从合成项目目录名映射规则"""
    rules = set()
    proj_dir = TESTS_DIR / "mutation" / "projects"
    if not proj_dir.is_dir():
        return rules
    for d in os.listdir(proj_dir):
        rules.update(SYNTHETIC_MAP.get(d, []))
    return rules


def build_matrix():
    reg = _extract_regression_rules()
    unit = _extract_unit_rules()
    syn = _extract_synthetic_rules()

    matrix = {}
    for rule in ALL_RULES:
        covered_reg = rule in reg
        covered_syn = rule in syn
        covered_unit = rule in unit
        # MLR-001b 输出 rule=MLR-001（引擎设计），由 MLR-001 回归覆盖
        if rule == "MLR-001b" and "MLR-001" in reg:
            covered_reg = True
        matrix[rule] = {
            "回归覆盖": covered_reg,
            "合成覆盖": covered_syn,
            "单元覆盖": covered_unit,
            "覆盖来源": ("回归" if covered_reg else
                       ("合成" if covered_syn else
                        ("单元" if covered_unit else "未覆盖"))),
        }
    return matrix


def main():
    matrix = build_matrix()
    covered = sum(1 for v in matrix.values() if v["覆盖来源"] != "未覆盖")
    uncovered = [k for k, v in matrix.items() if v["覆盖来源"] == "未覆盖"]

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    print(f"JSON: {OUT_JSON}")
    print(f"覆盖率: {covered}/{len(matrix)}")

    if uncovered:
        print(f"未覆盖: {uncovered}")
    else:
        print("KPI1: 覆盖矩阵 100%")

    if "--check" in sys.argv:
        return 1 if uncovered else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())