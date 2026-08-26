"""
benchmark_h1_engines.py - H1 WP-0 分引擎耗时定位

单进程内依次对 5 个指标引擎 init + all_metrics 计时，
输出 JSON，用于定位 FreeCAD src 4h 热点在哪个引擎。

用法:
    python scripts/benchmark_h1_engines.py D:\\OPENSOURCE\\FreeCAD\\src --tag hot
"""

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arch_quality.arch_metrics_standard import StandardMetrics
from arch_quality.arch_metrics_multilang import MultilangMetrics
from arch_quality.arch_metrics_template import TemplateMetaprogrammingMetrics
from arch_quality.arch_metrics_numerical_accuracy import NumericalAccuracyMetrics
from arch_quality.arch_metrics_solver_physics import SolverPhysicsMetrics


def _machine_info() -> dict:
    info = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor() or "unknown",
        "machine": platform.machine(),
    }
    try:
        import psutil
        info["cpu_physical"] = psutil.cpu_count(logical=False)
        info["cpu_logical"] = psutil.cpu_count(logical=True)
        info["mem_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        pass
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="项目根路径")
    ap.add_argument("--tag", default="engines")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    engines = [
        ("standard", StandardMetrics),
        ("multilang", MultilangMetrics),
        ("template", TemplateMetaprogrammingMetrics),
        ("numerical", NumericalAccuracyMetrics),
        ("solver_physics", SolverPhysicsMetrics),
    ]

    result = {"slug": Path(args.root.rstrip("\\/")).name, "root": args.root,
              "tag": args.tag, "engines": {}, "machine": _machine_info(),
              "measured_at": datetime.now().isoformat(timespec="seconds")}
    for name, cls in engines:
        print(f"[{name}] init ...", flush=True)
        t0 = time.perf_counter()
        m = cls(args.root)
        t_init = time.perf_counter() - t0
        print(f"[{name}] generate ...", flush=True)
        t0 = time.perf_counter()
        d = m.all_metrics()
        t_gen = time.perf_counter() - t0
        flags = {k: d.get(k) for k in
                 ("is_single_language", "is_cpp_project", "is_numerical", "is_multiphysics")}
        result["engines"][name] = {
            "init_s": round(t_init, 2),
            "generate_s": round(t_gen, 2),
            "total_s": round(t_init + t_gen, 2),
            "flags": flags,
            "file_count": d.get("files", {}).get("total"),
        }
        print(f"  {name}: init={t_init:.1f}s generate={t_gen:.1f}s flags={flags}", flush=True)

    result["total_s"] = round(sum(e["total_s"] for e in result["engines"].values()), 2)
    print(f"TOTAL {result['total_s']}s")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    out_dir = Path(__file__).resolve().parent.parent / "docs" / "zh" / "计划" / "baseline_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{args.tag}_{result['slug'].lower()}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入: {path}")


if __name__ == "__main__":
    main()