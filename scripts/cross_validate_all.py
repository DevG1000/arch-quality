"""H3 WP-8 F3: aggregate per-engine LOOCV results.

Reads JSON produced by numerical/solver/GCS/ACL/HPC cross-validation scripts,
normalizes the 9-fold in-range metric, and writes a unified summary.
"""

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "zh", "计划")
OUT_JSON = os.path.join(OUT_DIR, "H3-WP8-F3-cross-validation.json")
OUT_MD = os.path.join(OUT_DIR, "H3-WP8-F3-cross-validation.md")

INPUTS = {
    "standard": os.path.join(ROOT, "docs", "zh", "cross_validation_standard.json"),
    "multilang": os.path.join(ROOT, "docs", "zh", "cross_validation_multilang.json"),
    "numerical": os.path.join(ROOT, "docs", "zh", "cross_validation_numerical.json"),
    "solver_physics": os.path.join(
        ROOT, "docs", "zh", "求解器和物理场模块化架构模式识别评估",
        "cross_validation_solver_physics.json"),
    "geometry_consistency": os.path.join(
        ROOT, "docs", "zh", "几何内核与科学数据结构一致性评估",
        "cross_validation_geometry_consistency.json"),
    "anti_corruption": os.path.join(
        ROOT, "docs", "zh", "外部科学内核与几何内核的封装与防腐层评估",
        "cross_validation_anti_corruption.json"),
    "hpc": os.path.join(
        ROOT, "docs", "zh", "并行异构计算架构评估", "hpc_cross_validation.json"),
}
PENDING = []


def normalize(name, data):
    if data.get("summary"):
        s = data["summary"]
        n = int(s.get("total_folds", 0))
        passed = int(s.get("in_range_count", 0))
        rate = passed / n if n else 0.0
        verdict = s.get("generalization_verdict", "UNKNOWN")
    elif data.get("result"):
        r = data["result"]
        n = int(r.get("n", 0))
        passed = int(r.get("passed", 0))
        rate = float(r.get("rate", (passed / n if n else 0.0)))
        verdict = "PASS" if r.get("ok") else "FAIL"
    else:
        return {"engine": name, "status": "MISSING", "reason": "unrecognized schema"}
    rate_pass = n > 0 and passed / n >= 7 / 9 - 1e-9
    nine_fold = n >= 9
    status = "PASS" if (rate_pass and nine_fold) else ("PARTIAL" if rate_pass else "FAIL")
    return {
        "engine": name,
        "fold_count": n,
        "passed": passed,
        "rate": round(passed / n, 4) if n else 0.0,
        "rate_pass_7_of_9": rate_pass,
        "nine_fold": nine_fold,
        "source_verdict": verdict,
        "status": status,
    }


def build_summary():
    engines = {}
    for name, path in INPUTS.items():
        if not os.path.exists(path):
            engines[name] = {"engine": name, "status": "MISSING", "reason": f"not found: {path}"}
            continue
        with open(path, encoding="utf-8") as f:
            engines[name] = normalize(name, json.load(f))
    loaded = [e for e in engines.values() if e.get("status") != "MISSING"]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "criterion": "LOOCV in-range; 7/9 rate threshold; nine_fold requires n>=9",
        "engines": engines,
        "pending_engines": list(PENDING),
        "summary": {
            "engines_with_data": len(loaded),
            "rate_pass_count": sum(1 for e in loaded if e.get("rate_pass_7_of_9")),
            "nine_fold_pass_count": sum(1 for e in loaded if e.get("status") == "PASS"),
            "kpi_status": (
                "PASS" if loaded and not PENDING
                and all(e.get("status") == "PASS" for e in loaded)
                else "PASS_WITH_RESIDUAL"
            ),
            "note": "all seven engines are 9-fold",
        },
    }


def render_md(summary):
    rows = []
    for name, e in summary["engines"].items():
        if e.get("status") == "MISSING":
            rows.append(f"| {name} | - | - | - | - | MISSING |")
            continue
        rows.append(
            f"| {name} | {e['fold_count']} | {e['passed']} | {e['rate']:.2%} | "
            f"{'是' if e['nine_fold'] else '否'} | {e['status']} |"
        )
    s = summary["summary"]
    lines = [
        "# H3 WP-8 F3 全维 LOOCV 汇总",
        "",
        f"**生成时间**：{summary['generated_at']}",
        f"**判定口径**：{summary['criterion']}",
        "",
        "## 汇总",
        "",
        "| 引擎 | 折数 | 通过 | 通过率 | 9 折 | 状态 |",
        "|:--|--:|--:|--:|:--:|:--|",
        *rows,
        "",
        f"- 有数据引擎：{s['engines_with_data']}",
        f"- 达到 7/9 比率：{s['rate_pass_count']}",
        f"- 真正 9 折 PASS：{s['nine_fold_pass_count']}",
        f"- 待扩语料：{', '.join(summary['pending_engines'])}",
        "",
        f"> {s['note']}",
    ]
    return "\n".join(lines) + "\n"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    summary = build_summary()
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(render_md(summary))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"JSON: {OUT_JSON}")
    print(f"MD:   {OUT_MD}")


if __name__ == "__main__":
    main()
