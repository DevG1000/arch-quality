"""h3_baseline.py - H3 WP-0 归一化前语义基线采集（T0.2）

对每个项目跑 ComprehensiveReport（全 8 引擎），把完整结果冻结归档到
docs/zh/计划/baseline_data/h3_pre_norm_<slug>.json，并打印一行摘要。

用途：H3 WP-1 激活子集全局归一化（决策 5：语义变更重设基线）的迁移前 diff 基准。

用法:
    python scripts/h3_baseline.py --list
    python scripts/h3_baseline.py --all
    python scripts/h3_baseline.py --project freecad_src="D:\\OPENSOURCE\\FreeCAD\\src"
    python scripts/h3_baseline.py --project occt="D:\\OPENSOURCE\\gcs-baselines\\occt\\src" --json
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

from arch_quality.arch_report import ComprehensiveReport

DEFAULT_BASE = os.environ.get("ARCH_OPENSOURCE", r"D:\OPENSOURCE")
DEFAULT_PROJECTS_REL = [
    ("freecad_src", "FreeCAD/src"),
    ("openfoam_v2512", "OpenFOAM-v2512"),
    ("brl_cad", "BRL-CAD"),
    ("elmerfem", "ElmerFEM"),
    ("occt", "gcs-baselines/occt/src"),
    ("salome_geom", "gcs-baselines/salome-geom/src"),
    ("eigen", "Eigen"),
]


def _default_projects(base: str = None):
    base = base or DEFAULT_BASE
    return [(slug, os.path.join(base, *rel.split("/"))) for slug, rel in DEFAULT_PROJECTS_REL]


def _machine_info() -> dict:
    info = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
    }
    try:
        import psutil
        info["cpu_physical"] = psutil.cpu_count(logical=False)
        info["cpu_logical"] = psutil.cpu_count(logical=True)
        info["mem_gb"] = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except ImportError:
        pass
    return info


def _run(root: str) -> dict:
    t0 = time.perf_counter()
    reporter = ComprehensiveReport(root, build_dir="")
    data = reporter.generate()
    return {"data": data, "elapsed_s": round(time.perf_counter() - t0, 2)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", action="append", default=[], help="slug=path，可重复")
    ap.add_argument("--all", action="store_true", help="跑默认 7 项目")
    ap.add_argument("--list", action="store_true", help="仅列出默认项目")
    ap.add_argument("--base", default=None, help="样本根目录（默认 $ARCH_OPENSOURCE 或 D:\\OPENSOURCE）")
    ap.add_argument("--json", action="store_true", help="仅打印 JSON 摘要，不写文件")
    args = ap.parse_args()

    if args.list:
        for slug, path in _default_projects(args.base):
            print("%-16s %s" % (slug, path))
        return

    projects = []
    for spec in args.project:
        if "=" not in spec:
            ap.error("--project 需要 slug=path 形式: %r" % spec)
        slug, path = spec.split("=", 1)
        projects.append((slug, path))
    if args.all:
        projects += _default_projects(args.base)
    if not projects:
        ap.error("需要 --project slug=path 或 --all（或 --list）")

    out_dir = Path(__file__).resolve().parent.parent / "docs" / "zh" / "计划" / "baseline_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries = {}
    for slug, root in projects:
        if not os.path.isdir(root):
            print("SKIP %s: 目录不存在 %s" % (slug, root))
            continue
        print("[%s] 评估中 ..." % slug, flush=True)
        try:
            r = _run(root)
        except Exception as e:  # noqa: BLE001
            print("FAIL %s: %s" % (slug, e), flush=True)
            continue
        data = r["data"]
        rec = {
            "slug": slug,
            "root": root,
            "measured_at": datetime.now().isoformat(timespec="seconds"),
            "elapsed_s": r["elapsed_s"],
            "overall": data.get("overall_score"),
            "dimensions": {k: v.get("score") for k, v in (data.get("dimensions") or {}).items()},
            "output_level_summary": data.get("output_level_summary"),
            "files": data.get("files"),
            "machine": _machine_info(),
            "raw": data,
        }
        summaries[slug] = {k: rec[k] for k in ("overall", "dimensions", "elapsed_s", "output_level_summary", "files")}
        print("  overall=%s dims=%s (%.1fs)" % (rec["overall"], rec["dimensions"], rec["elapsed_s"]), flush=True)
        if not args.json:
            path = out_dir / ("h3_pre_norm_%s.json" % slug)
            path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            print("  已写入: %s" % path, flush=True)

    if args.json:
        print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()