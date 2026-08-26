"""
benchmark_h1_baseline.py - H1 WP-0 性能基线实测脚本

对指定项目运行 ComprehensiveReport（综合 5 维度引擎）并计时。
输出 JSON（含机器信息、缓存状态、分位数 P50/P90），供 H1基线实测报告引用。

用法:
    python scripts/benchmark_h1_baseline.py --project D:\\OPENSOURCE\\FreeCAD\\src --runs 3 --tag cold
    python scripts/benchmark_h1_baseline.py --project D:\\OPENSOURCE\\OpenFOAM-v2512 --runs 3 --tag hot
    python scripts/benchmark_h1_baseline.py --all --runs 3 --tag hot

输出:
    默认写入 docs/zh/计划/baseline_data/<tag>_<slug>.json
    也可 --json 直接打印结果
"""

import argparse
import gc
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arch_quality.arch_report import ComprehensiveReport

DEFAULT_PROJECTS = [
    ("freecad_src", r"D:\OPENSOURCE\FreeCAD\src"),
    ("openfoam_v2512", r"D:\OPENSOURCE\OpenFOAM-v2512"),
    ("brl_cad", r"D:\OPENSOURCE\BRL-CAD"),
    ("freecad_cam", r"D:\OPENSOURCE\FreeCAD\src\Mod\CAM"),
    ("freecad_fem", r"D:\OPENSOURCE\FreeCAD\src\Mod\Fem"),
    ("elmerfem", r"D:\OPENSOURCE\ElmerFEM"),
]


def _machine_info() -> dict:
    info = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor() or "unknown",
        "machine": platform.machine(),
        "node": platform.node(),
    }
    try:
        import psutil
        info["cpu_physical"] = psutil.cpu_count(logical=False)
        info["cpu_logical"] = psutil.cpu_count(logical=True)
        info["mem_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        vm = psutil.virtual_memory()
        info["mem_available_gb"] = round(vm.available / (1024**3), 1)
        info["cpu_freq_mhz"] = psutil.cpu_freq().current if psutil.cpu_freq() else None
    except ImportError:
        info["note"] = "psutil not installed; cpu/mem details omitted"
    return info


def _run_once(root: str) -> dict:
    t0 = time.perf_counter()
    reporter = ComprehensiveReport(root, build_dir="")
    t_init = time.perf_counter() - t0
    t0 = time.perf_counter()
    data = reporter.generate()
    t_generate = time.perf_counter() - t0
    return {
        "init_s": round(t_init, 2),
        "generate_s": round(t_generate, 2),
        "total_s": round(t_init + t_generate, 2),
        "file_count": data.get("files", {}).get("total"),
        "overall": data.get("overall_score"),
    }


def _percentile(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(s):
        return s[-1]
    return s[f] + (s[c] - s[f]) * (k - f)


def _evict_file_cache():
    """通过内存压力强制换出 OS 待机文件缓存（模拟冷缓存）.

    无管理员权限时无法使用 EmptyStandbyList / RAMMap，
    改用大块内存分配触发 standby list 回收。
    """
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        for proc in __import__("psutil").process_iter(["pid"]):
            try:
                kernel32.EmptyWorkingSet(kernel32.OpenProcess(0x1FFF, False, proc.pid))
            except Exception:
                pass
    except Exception:
        pass
    bufs = []
    total_mb = 0
    try:
        for _ in range(300):
            bufs.append(bytearray(32 * 1024 * 1024))
            total_mb += 32
    except MemoryError:
        pass
    del bufs
    gc.collect()
    time.sleep(2)
    return total_mb


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default=None, help="单项目根路径")
    ap.add_argument("--slug", default=None, help="项目短名（默认取路径末段）")
    ap.add_argument("--all", action="store_true", help="跑默认 6 个项目（FreeCAD src + 5 回归）")
    ap.add_argument("--exclude", default="", help="排除的 slug 逗号分隔（配合 --all）")
    ap.add_argument("--runs", type=int, default=3, help="每个项目运行轮数（默认 3）")
    ap.add_argument("--tag", default="baseline", help="缓存状态标签: cold/hot/baseline")
    ap.add_argument("--evict", action="store_true", help="每轮前强制换出文件缓存（模拟冷缓存）")
    ap.add_argument("--json", action="store_true", help="仅打印 JSON，不写文件")
    args = ap.parse_args()

    if args.all:
        projects = DEFAULT_PROJECTS
        if args.exclude:
            excluded = set(s.strip() for s in args.exclude.split(","))
            projects = [p for p in projects if p[0] not in excluded]
    elif args.project:
        slug = args.slug or Path(args.project.rstrip("\\/")).name.lower().replace(" ", "_")
        projects = [(slug, args.project)]
    else:
        ap.error("需要 --project 或 --all")

    results = {}
    for slug, root in projects:
        if not os.path.isdir(root):
            print(f"SKIP {slug}: 目录不存在 {root}")
            continue
        print(f"[{slug}] 开始 {args.runs} 轮计时...")
        runs = []
        for i in range(args.runs):
            if args.evict:
                mb = _evict_file_cache()
                print(f"  缓存已换出 (释放 {mb}MB 压力)")
            print(f"  run {i+1}/{args.runs} ...", flush=True)
            t0 = time.perf_counter()
            r = _run_once(root)
            r["wall_s"] = round(time.perf_counter() - t0, 2)
            runs.append(r)
            print(f"    total={r['total_s']}s wall={r['wall_s']}s files={r['file_count']}")

        totals = [r["total_s"] for r in runs]
        result = {
            "slug": slug,
            "root": root,
            "tag": args.tag,
            "runs": runs,
            "p50_total_s": round(_percentile(totals, 50), 2),
            "p90_total_s": round(_percentile(totals, 90), 2),
            "min_total_s": round(min(totals), 2),
            "max_total_s": round(max(totals), 2),
            "mean_total_s": round(statistics.mean(totals), 2),
            "machine": _machine_info(),
            "measured_at": datetime.now().isoformat(timespec="seconds"),
        }
        results[slug] = result

    out = {
        "generated_by": "scripts/benchmark_h1_baseline.py",
        "tool_version": "1.0.0",
        "commit": os.popen("git -C %s rev-parse --short HEAD" % Path(__file__).resolve().parent.parent)
            .read().strip() or "unknown",
        "projects": results,
    }

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    out_dir = Path(__file__).resolve().parent.parent / "docs" / "zh" / "计划" / "baseline_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug, r in results.items():
        path = out_dir / f"{args.tag}_{slug}.json"
        path.write_text(
            json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"已写入: {path}")


if __name__ == "__main__":
    main()