# -*- coding: utf-8 -*-
"""HPC 维度 9 折留一交叉验证（B3.7 / KPI5）

语料：tests/regression/snapshots/hpc_cv/hpc_cv_*.json
      = 5 健康 + 4 不健康（含合成）
判定：每折留 1 个，其余 8 个的 overall [min,max] 是否包含测试样本
门槛：>= 7/9

用法：
    python scripts/cross_validate_hpc.py
"""

import io
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(PROJECT_ROOT, "tests", "regression", "snapshots", "hpc_cv")
OUT_DIR = os.path.join(PROJECT_ROOT, "docs", "zh", "并行异构计算架构评估")
OUT_JSON = os.path.join(OUT_DIR, "hpc_cross_validation.json")
OUT_MD = os.path.join(OUT_DIR, "hpc_cross_validation_report.md")

THRESHOLD = 7


def load_samples():
    """加载 hpc_cv 语料，返回 {key: snapshot}。"""
    samples = {}
    if not os.path.isdir(SNAP_DIR):
        return samples
    for fn in sorted(os.listdir(SNAP_DIR)):
        if not (fn.startswith("hpc_cv_") and fn.endswith(".json")):
            continue
        path = os.path.join(SNAP_DIR, fn)
        with io.open(path, encoding="utf-8") as f:
            snap = json.load(f)
        key = snap.get("project") or fn[len("hpc_cv_"):-len(".json")]
        samples[key] = snap
    return samples


def _metrics(scores):
    if not scores:
        return {}
    mean = sum(scores) / len(scores)
    return {
        "count": len(scores),
        "mean": round(mean, 2),
        "min": min(scores),
        "max": max(scores),
    }


def run_loocv(samples):
    """9 折 LOOCV：测试样本 overall 是否落在训练集 [min,max]。"""
    keys = [k for k, v in samples.items() if v.get("overall") is not None]
    folds = []
    passed = 0
    for key in keys:
        test = samples[key]
        train = [samples[k]["overall"] for k in keys if k != key]
        lo, hi = min(train), max(train)
        ok = lo <= test["overall"] <= hi
        passed += int(ok)
        folds.append({
            "fold": key,
            "label": test.get("label", "unknown"),
            "overall": test["overall"],
            "train_min": lo,
            "train_max": hi,
            "in_range": ok,
        })
    n = len(keys)
    return {
        "n": n,
        "passed": passed,
        "rate": round(passed / n, 4) if n else 0.0,
        "threshold": THRESHOLD,
        "ok": passed >= THRESHOLD,
        "folds": folds,
    }


def _write_outputs(samples, result):
    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {
        "dimension": "hpc",
        "criterion": "LOOCV in-range (train min..max)",
        "labels": {k: samples[k].get("label") for k in sorted(samples)},
        "scores": {k: samples[k].get("overall") for k in sorted(samples)},
        "result": result,
    }
    with io.open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    lines = [
        "# HPC 维度 9 折交叉验证报告（B3.7 / KPI5）",
        "",
        "> 语料：`tests/regression/snapshots/hpc_cv/`（5 健康 + 4 不健康）",
        "> 判定：测试样本 overall 是否落在其余 8 个的 [min,max]",
        "> 门槛：>= 7/9",
        "",
        "## 语料",
        "",
        "| 样本 | 标签 | overall |",
        "|:--|:--:|--:|",
    ]
    for k in sorted(samples):
        lines.append(f"| {k} | {samples[k].get('label','?')} | {samples[k].get('overall')} |")
    lines += [
        "",
        "## LOOCV 结果",
        "",
        "| 留出样本 | 标签 | overall | 训练 min | 训练 max | 在内 |",
        "|:--|:--:|--:|--:|--:|:--:|",
    ]
    for f in result["folds"]:
        lines.append(
            f"| {f['fold']} | {f['label']} | {f['overall']} | "
            f"{f['train_min']} | {f['train_max']} | {'是' if f['in_range'] else '否'} |"
        )
    lines += [
        "",
        "## 汇总",
        "",
        f"- 通过：**{result['passed']}/{result['n']}**（{result['rate']:.1%}）",
        f"- 门槛：{result['threshold']}/9 → **{'PASS' if result['ok'] else 'FAIL'}**",
        "",
        "> 说明：不健康样本含合成项目，可能高估泛化；建议后续用真实 held-out 项目复核。",
        "",
    ]
    with io.open(OUT_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    samples = load_samples()
    print(f"=== HPC LOOCV: {len(samples)} samples ===")
    for k in sorted(samples):
        print(f"  {k:28s} {samples[k].get('label','?'):10s} overall={samples[k].get('overall')}")
    if len(samples) < 2:
        print("[ERROR] 语料不足（<2）")
        return 1
    result = run_loocv(samples)
    print("\n=== folds ===")
    for f in result["folds"]:
        mark = "OK " if f["in_range"] else "OUT"
        print(f"  {mark} {f['fold']:28s} {f['overall']} in [{f['train_min']},{f['train_max']}]")
    print(f"\npassed: {result['passed']}/{result['n']} (threshold {result['threshold']}) -> "
          f"{'PASS' if result['ok'] else 'FAIL'}")
    _write_outputs(samples, result)
    print("json:", OUT_JSON)
    print("md  :", OUT_MD)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
