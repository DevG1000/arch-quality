# -*- coding: utf-8 -*-
"""通用一致性检查脚本（多引擎）

验证 Guide <-> Skill <-> Tool 在命名、评分算法、版本号、规则 ID 等方面的一致性。

引擎：standard / multilang / template / numerical / solver_physics
配置驱动：每个引擎定义指南、Skill、工具、案例集路径 + 规则前缀 + 版本绑定。

用法：
    python scripts/consistency_check.py [--engine all|standard|multilang|template|numerical|solver_physics]

退出码：0=全一致, 1=存在不一致
"""

import os
import re
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ENGINES = {
    "standard": {
        "guide": "docs/zh/架构质量标准/软件架构质量评估指南（2.3版）.md",
        "skill": "src/arch_quality/skills/arch-quality.md",
        "tool": "src/arch_quality/arch_metrics_standard.py",
        "case": "docs/zh/架构质量标准/软件架构质量评估验证案例集（1.3).md",
        "rule_prefix": "SAR",
        "rule_count": 12,
        "version_pairs": [],
        "dimensions": ["结构质量", "设计质量", "文档质量", "演进质量"],
        "weights": [],
        "case_keywords": ["A类", "B类", "OpenFOAM", "FreeCAD"],
    },
    "multilang": {
        "guide": "docs/zh/多语言混合依赖评估指南.md",
        "skill": "src/arch_quality/skills/multilang-dependency.md",
        "tool": "src/arch_quality/arch_metrics_multilang.py",
        "case": "docs/zh/多语言混合依赖验证案例库.md",
        "rule_prefix": "MLR",
        "rule_count": 12,
        "version_pairs": [],
        "dimensions": ["跨语言调用强度", "跨语言影响半径", "跨语言回调深度"],
        "weights": [],
        "case_keywords": ["MLR", "pybind11"],
    },
    "template": {
        "guide": "docs/zh/模板元编程与编译时依赖膨胀评估指南.md",
        "skill": "src/arch_quality/skills/template-metaprogramming.md",
        "tool": "src/arch_quality/arch_metrics_template.py",
        "case": "docs/zh/模板元编程与编译时依赖膨胀验证案例库.md",
        "rule_prefix": "MLR",
        "rule_count": 12,
        "start_id": 13,
        "version_pairs": [],
        "dimensions": ["编译时扇入", "模板实例化重复率", "头文件影响半径"],
        "weights": [],
        "case_keywords": ["MLR-013", "extern template"],
    },
    "numerical": {
        "guide": "docs/zh/数值算法正确性与精度保障评估指南.md",
        "skill": "src/arch_quality/skills/numerical-accuracy.md",
        "tool": "src/arch_quality/arch_metrics_numerical_accuracy.py",
        "case": "docs/zh/数值算法正确性与精度保障评估验证案例集.md",
        "rule_prefix": "NVR",
        "rule_count": 12,
        "version_pairs": [("GUIDE_VERSION", "1.8"), ("SKILL_VERSION", "1.6")],
        "dimensions": ["数值稳定性保障", "舍入误差与数值敏感度控制", "验证完备性"],
        "weights": [],
        "case_keywords": ["NVR", "MMS", "OpenFOAM"],
    },
    "solver_physics": {
        "guide": "docs/zh/求解器和物理场模块化架构模式识别评估/求解器与物理场模块化架构模式识别评估指南.md",
        "skill": "src/arch_quality/skills/solver-physics-architecture.md",
        "tool": "src/arch_quality/arch_metrics_solver_physics.py",
        "case": "docs/zh/求解器和物理场模块化架构模式识别评估/求解器与物理场模块化架构模式识别评估验证案例集.md",
        "rule_prefix": "MPR",
        "rule_count": 12,
        "version_pairs": [("GUIDE_VERSION", "1.3"), ("SKILL_VERSION", "1.0")],
        "dimensions": ["物理场模块边界完整性", "多物理场耦合架构合理性", "插件式扩展架构支持度"],
        "dimension_aliases": {
            "物理场模块边界完整性": ["物理场模块边界清晰度"],
            "多物理场耦合架构合理性": ["求解器耦合架构合理性"],
            "插件式扩展架构支持度": ["插件扩展架构完整性"],
        },
        "weights": [],
        "case_keywords": ["MPR", "Kratos", "preCICE"],
    },
}

RULE_ID_VALIDATION_PENDING = True
# 已知规则空洞（WP-7.1 重编号/补齐后应消除）
KNOWN_HOLES = {"NVR-009", "MPR-011"}


def read(path):
    """智能读取：优先 UTF-8-sig，回退 GBK/GB18030/Latin-1"""
    with open(path, "rb") as f:
        b = f.read()
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030", "latin-1"):
        try:
            return b.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return b.decode("latin-1", errors="replace")


def extract_rule_ids(text, prefix):
    """提取指定前缀的规则 ID（含变体）"""
    ids = set()
    pat = re.compile(r"\b" + prefix + r"-\d{3}[a-z]?\b")
    for m in pat.finditer(text):
        ids.add(m.group(0))
    return ids


def check_rule_ids(cfg, g, s, t):
    """规则 ID 三方一致（指南/Skill/工具）"""
    ok = True
    prefix, expected = cfg["rule_prefix"], cfg["rule_count"]
    start = cfg.get("start_id", 1)
    end = start + expected - 1
    g_ids = extract_rule_ids(g, prefix)
    s_ids = extract_rule_ids(s, prefix)
    t_ids = extract_rule_ids(t, prefix)
    t_ids |= extract_rule_ids(re.sub(prefix + "_", prefix + "-", t), prefix)
    expected_ids = {f"{prefix}-{i:03d}" for i in range(start, end + 1)}
    for label, ids in [("Guide", g_ids), ("Skill", s_ids), ("Tool", t_ids)]:
        missing = expected_ids - ids
        known = missing & KNOWN_HOLES
        unexpected = missing - known
        if known:
            print(f"  INFO: {label} 已知空洞 {sorted(known)}（WP-7.1 补齐）")
        if unexpected:
            print(f"  WARN: {label} 缺少规则 {sorted(unexpected)}")
            ok = False
    # Skill/Tool 集合差异（排除已知空洞）
    holes = KNOWN_HOLES
    s_only = {i for i in (s_ids - t_ids) if i not in holes}
    t_only = {i for i in (t_ids - s_ids) if i not in holes}
    if s_only or t_only:
        print(f"  WARN: Skill/Tool 规则集不一致 Skill独有={sorted(s_only)} Tool独有={sorted(t_only)}")
        ok = False
    if ok:
        print(f"  RULES {prefix}-{start:03d}~{end:03d} 三方一致: OK")
    return ok


def check_versions(cfg, g, s, t):
    """版本绑定一致（skill 声明到工具常量）"""
    if not cfg.get("version_pairs"):
        return True
    ok = True
    for const, ver in cfg["version_pairs"]:
        pat = re.compile(re.escape(const) + r"\s*=\s*\"([^\"]+)\"")
        m = pat.search(t)
        if not m:
            print(f"  WARN: 工具缺少常量 {const}")
            ok = False
            continue
        if m.group(1) != ver:
            print(f"  WARN: 工具 {const}={m.group(1)} 期望 {ver}")
            ok = False
        if ver not in s:
            print(f"  WARN: Skill 未声明版本 {ver}（{const}）")
            ok = False
    if ok:
        print("  VERSIONS 一致: OK")
    return ok


def check_weights(cfg, g, s, t):
    """权重一致（Skill 维度权重表，可选）"""
    ok = True
    for pat, label in cfg.get("weights", []):
        if not re.search(pat, s):
            print(f"  WARN: Skill 权重 {label} 未找到")
            ok = False
    if ok:
        print(f"  WEIGHTS {len(cfg.get('weights', []))} 项对齐: OK")
    return ok


def check_dimensions(cfg, g, s, t):
    """维度命名一致（Guide/Skill，支持别名）"""
    ok = True
    aliases = cfg.get("dimension_aliases", {})
    for dim in cfg.get("dimensions", []):
        alt_names = [dim] + list(aliases.get(dim, []))
        if not any(n in g for n in alt_names):
            print(f"  WARN: 指南缺失维度 {dim}（别名 {alt_names[1:]}）")
            ok = False
        if dim not in s:
            print(f"  WARN: Skill 缺失维度 {dim}")
            ok = False
    if ok:
        print(f"  DIMENSIONS {len(cfg.get('dimensions', []))} 维度命名一致: OK")
    return ok


def check_caseset(cfg, g, s, c):
    """案例集完整性（按引擎关键词）"""
    ok = True
    for kw in cfg.get("case_keywords", []):
        if kw not in c:
            print(f"  WARN: 案例集缺关键词 {kw}")
            ok = False
    if ok:
        print(f"  CASESET {len(cfg.get('case_keywords', []))} 关键词: OK")
    return ok


def run_engine(name, cfg):
    """运行单引擎一致性检查"""
    print(f"\n=== {name} 三方一致性检查 ===")
    missing = []
    for key in ("guide", "skill", "tool", "case"):
        path = cfg.get(key, "")
        if path and not os.path.exists(os.path.join(PROJECT, path)):
            missing.append(path)
    if missing:
        for p in missing:
            print(f"  WARN: 文件缺失 {p}")
        return False

    g = read(os.path.join(PROJECT, cfg["guide"]))
    s = read(os.path.join(PROJECT, cfg["skill"]))
    t = read(os.path.join(PROJECT, cfg["tool"]))
    c = read(os.path.join(PROJECT, cfg["case"])) if cfg.get("case") else ""

    results = []
    results.append(("规则ID", check_rule_ids(cfg, g, s, t)))
    results.append(("版本", check_versions(cfg, g, s, t)))
    results.append(("权重", check_weights(cfg, g, s, t)))
    results.append(("维度命名", check_dimensions(cfg, g, s, t)))
    results.append(("案例集", check_caseset(cfg, g, s, c)))

    print("---")
    all_ok = True
    for nm, ok in results:
        print(f"  {nm}: {'PASS' if ok else 'FAIL'}")
        all_ok = all_ok and ok
    print(f"  => {name}: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


def main():
    import argparse
    ap = argparse.ArgumentParser(description="通用一致性检查（多引擎）")
    ap.add_argument("--engine", default="all", choices=["all"] + list(ENGINES.keys()))
    args = ap.parse_args()

    print("=== 通用一致性检查 ===")
    if RULE_ID_VALIDATION_PENDING:
        print("  [INFO] 规则编号统一校验接口预留（依赖 WP-7.1）")

    selected = list(ENGINES.keys()) if args.engine == "all" else [args.engine]
    all_ok = True
    for name in selected:
        ok = run_engine(name, ENGINES[name])
        all_ok = all_ok and ok

    print(f"\n结果: {'PASS - 全部一致' if all_ok else 'FAIL - 存在不一致'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
