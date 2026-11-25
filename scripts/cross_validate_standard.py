"""H3 WP-8 F3: standard LOOCV over 9 project snapshots."""

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(ROOT, "tests", "regression", "snapshots")
OUT_JSON = os.path.join(ROOT, "docs", "zh", "cross_validation_standard.json")
OUT_MD = os.path.join(ROOT, "docs", "zh", "标准架构质量评估交叉验证报告.md")

PROJECTS = {
    "arch-quality": "standard_arch_quality",
    "brl-cad": "standard_brl_cad",
    "freecad-cam": "standard_freecad_cam",
    "openfoam-apps": "standard_openfoam_apps",
    "elmerfem": "standard_elmerfem",
    "mfem": "standard_mfem",
    "kratos": "standard_kratos",
    "su2": "standard_su2",
    "precice": "standard_precice",
}


def load_scores():
    scores = {}
    for name, snap in PROJECTS.items():
        path = os.path.join(SNAP_DIR, snap + ".json")
        if not os.path.exists(path):
            print(f"[SKIP] {name}: {path}")
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        score = data.get("standard_overall")
        if score is not None:
            scores[name] = float(score)
    return scores


def run_loocv(scores):
    folds = []
    for holdout, test in scores.items():
        train = [v for k, v in scores.items() if k != holdout]
        lo, hi = min(train), max(train)
        in_range = lo <= test <= hi
        distance = 0.0 if in_range else (lo - test if test < lo else test - hi)
        folds.append({
            "fold": holdout,
            "test_overall": test,
            "train_min": lo,
            "train_max": hi,
            "in_range": in_range,
            "outlier_distance": round(distance, 2),
        })
    passed = sum(1 for f in folds if f["in_range"])
    return folds, passed


def render_md(report):
    lines = [
        "# 标准架构质量评估 LOOCV 报告",
        "",
        f"**方法**：Leave-One-Out ({report['summary']['total_folds']}-fold)",
        f"**项目**：{', '.join(report['projects'])}",
        f"**日期**：{time.strftime('%Y-%m-%d')}",
        "",
        "## 汇总",
        "",
        "| 指标 | 数值 |",
        "|:--|--:|",
        f"| 总轮数 | {report['summary']['total_folds']} |",
        f"| 测试分在训练范围内 | {report['summary']['in_range_count']}/{report['summary']['total_folds']} |",
        f"| 判定 | {report['summary']['generalization_verdict']} |",
        "",
        "## 逐轮结果",
        "",
        "| 轮次 | 测试分 | 训练范围 | 范围内 | 离群距离 |",
        "|:--|--:|:--:|:--:|--:|",
    ]
    for f in report["folds"]:
        lines.append(
            f"| {f['fold']} | {f['test_overall']:.2f} | "
            f"{f['train_min']:.2f} ~ {f['train_max']:.2f} | "
            f"{'是' if f['in_range'] else '否'} | {f['outlier_distance']:.2f} |"
        )
    return "\n".join(lines) + "\n"


def main():
    scores = load_scores()
    folds, passed = run_loocv(scores)
    n = len(folds)
    report = {
        "dimension": "standard",
        "method": f"Leave-One-Out Cross Validation ({n}-fold)",
        "criterion": "LOOCV overall in [train_min, train_max]",
        "projects": list(scores.keys()),
        "folds": folds,
        "summary": {
            "total_folds": n,
            "in_range_count": passed,
            "generalization_rate": f"{passed}/{n}",
            "generalization_verdict": "PASS" if passed >= 7 else "FAIL",
        },
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(render_md(report))
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"JSON: {OUT_JSON}")
    print(f"MD:   {OUT_MD}")


if __name__ == "__main__":
    main()
