"""weight_sensitivity.py - H3 WP-2 维度权重敏感性分析（OAT 网格扫描）

对 6 个增强维权重逐个做 one-at-a-time 网格扫描，用 WP-0 冻结基线（h3_pre_norm_*.json，
含各项目各维度得分）零成本重算综合分，输出：
  - 每个权重的 overall 变化量、排名（Kendall τ）、等级变化
  - 稳定区间（该区间内无排名/等级变化）

标准 4 维冻结；数据：7 个综合基线项目。
用法：
    python scripts/weight_sensitivity.py
    python scripts/weight_sensitivity.py --json
"""

import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arch_quality.arch_core import (  # noqa: E402
    calc_activate_subset, ENH_KEY_TO_DIM, load_dimension_weights,
)

PROJECT = Path(__file__).resolve().parent.parent
BASE_DIR = PROJECT / "docs" / "zh" / "计划" / "baseline_data"
ENH_KEYS = ["ml", "tpl", "nvr", "sp", "gcs", "acl", "hpc"]
GRID = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
ENG2KEY = {
    "multilang": "ml", "template": "tpl", "numerical": "nvr",
    "solver_physics": "sp", "geometry_consistency": "gcs", "anti_corruption": "acl",
    "hpc": "hpc",
}
DIM_CN = {
    "dim.multilang": "多语言", "dim.template": "模板", "dim.numerical": "数值",
    "dim.solver_physics": "物理场", "dim.geometry_consistency": "几何", "dim.anti_corruption": "防腐",
    "dim.hpc": "HPC",
}


def grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def kendall_tau(a, b) -> float:
    n = len(a)
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = (a[i] - a[j]) * (b[i] - b[j])
            if s > 0:
                conc += 1
            elif s < 0:
                disc += 1
    tot = conc + disc
    return (conc - disc) / tot if tot else 1.0


def load_projects():
    """从 WP-0 冻结基线恢复各项目各维度得分（纯分）。"""
    projects = []
    for f in sorted(glob.glob(str(BASE_DIR / "h3_pre_norm_*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        dims = d["raw"]["dimensions"]
        merged = dims["structural"]["score"]
        scores = {
            "dim.structural": None,  # 稍后反解
            "dim.design": dims["design"]["score"],
            "dim.documentation": dims["documentation"]["score"],
            "dim.evolution": dims["evolution"]["score"],
        }
        enh = {}
        for eng, key in ENG2KEY.items():
            e = dims["structural"].get(eng + "_enhancement")
            if e:
                enh[key] = (e["score"], e.get("weight_applied", 0.0))
        base_w = 1.0 - sum(w for _, w in enh.values())
        pure = (merged - sum(s * w for s, w in enh.values())) / base_w
        scores["dim.structural"] = pure
        for key in enh:
            scores[ENH_KEY_TO_DIM[key]] = enh[key][0]
        active = ["dim.structural", "dim.design", "dim.documentation", "dim.evolution"] + \
                 [ENH_KEY_TO_DIM[k] for k in enh]
        projects.append({"slug": d["slug"], "scores": scores, "active_keys": list(enh.keys())})
    return projects


def overall(proj, weights) -> float:
    norm = calc_activate_subset(proj["active_keys"], weights=weights)
    return sum(proj["scores"][d] * norm[d] for d in norm)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    weights = load_dimension_weights()
    projects = load_projects()
    base_vals = {p["slug"]: round(overall(p, weights), 2) for p in projects}
    base_vec = [base_vals[p["slug"]] for p in projects]
    base_grades = {p["slug"]: grade(base_vals[p["slug"]]) for p in projects}

    result = {
        "grid": GRID,
        "baseline_weights": {ENH_KEY_TO_DIM[k]: weights[ENH_KEY_TO_DIM[k]] for k in ENH_KEYS},
        "projects": {p["slug"]: {"baseline_overall": base_vals[p["slug"]],
                                 "grade": base_grades[p["slug"]],
                                 "active_enh": p["active_keys"]} for p in projects},
        "sensitivity": {},
    }

    print("基线（当前 registry 权重）：")
    for p in projects:
        print("  %-16s %.2f  %s  active=%s" % (p["slug"], base_vals[p["slug"]],
                                               base_grades[p["slug"]], ",".join(p["active_keys"])))
    print()

    for key in ENH_KEYS:
        dim = ENH_KEY_TO_DIM[key]
        row = []
        for w in GRID:
            w2 = dict(weights)
            w2[dim] = w
            vec = [round(overall(p, w2), 2) for p in projects]
            dmax = max(abs(v - b) for v, b in zip(vec, base_vec))
            tau = kendall_tau(base_vec, vec)
            gchg = sum(1 for p, v in zip(projects, vec) if grade(v) != base_grades[p["slug"]])
            row.append({"w": w, "max_abs_delta": round(dmax, 2), "kendall_tau": round(tau, 3),
                        "grade_changes": gchg})
        stable = [r["w"] for r in row if abs(r["kendall_tau"] - 1.0) < 1e-9 and r["grade_changes"] == 0]
        result["sensitivity"][dim] = {
            "current": weights[dim],
            "rows": row,
            "stable_values": stable,
            "critical": not (len(stable) == len(GRID)),
        }
        print("── %s（%s，现行 %.2f）──" % (dim, DIM_CN.get(dim, dim), weights[dim]))
        for r in row:
            mark = " 稳定" if r["w"] in stable else ""
            print("   w=%.2f  max|Δoverall|=%.2f  τ=%+.2f  gradeΔ=%d%s" %
                  (r["w"], r["max_abs_delta"], r["kendall_tau"], r["grade_changes"], mark))
        print()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    out = BASE_DIR / "h3_wp2_sensitivity.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("已写入: %s" % out)


if __name__ == "__main__":
    main()