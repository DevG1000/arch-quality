# -*- coding: utf-8 -*-
"""HPC 引擎回归测试（W4）

- 5 个基线：OpenFOAM / deal.II / MFEM / SU2 + 非 HPC 负样本
- 快照只保留稳定字段（无时间戳/绝对路径）
- ARCH_REGRESSION_UPDATE=1 时，**先过程序化取值校验才允许写快照**
- 同一输入连续两次结果必须一致（确定性）
"""

import json
import os
from pathlib import Path

import pytest

from arch_quality.arch_metrics_hpc import HpcArchitectureMetrics

SNAP_DIR = Path(__file__).parent / "snapshots"
REPO = Path(__file__).resolve().parents[2]

PROJECTS = {
    "openfoam_v2512": {
        "path": r"D:\OPENSOURCE\OpenFOAM-v2512",
        "is_hpc": True, "min_overall": 90,
        "must_not": ["HPC-005", "HPC-011"],
    },
    "dealii": {
        "path": r"D:\OPENSOURCE\dealii",
        "is_hpc": True, "min_overall": 95,
        "must_not": ["HPC-008"],
    },
    "mfem": {
        "path": r"D:\OPENSOURCE\mfem",
        "is_hpc": True, "min_overall": 80,
        "must_include": ["HPC-006"],   # hypre.cpp 真阳性
    },
    "su2": {
        "path": r"D:\OPENSOURCE\SU2",
        "is_hpc": True, "min_overall": 95,
        "must_not": ["HPC-010"],
    },
    "non_hpc_project": {
        "path": str(REPO / "tests" / "mutation" / "projects" / "non_hpc_project"),
        "is_hpc": False,
    },
}

DIMS = ["backend_consistency", "mpi_halo", "load_topology", "hybrid_parallel"]
VALID_LEVEL = {"ERROR", "WARNING", "INFO"}
VALID_SEV = {"HIGH", "MEDIUM", "LOW"}
VALID_GATE = {"PASS", "WARN", "BLOCK"}


def _stable(r: dict) -> dict:
    """剔除易变字段，保留可比对结构。"""
    w = r.get("waiver_audit") or {}
    viol = sorted(
        [{
            "rule": v["rule"], "count": v["count"],
            "output_level": v["output_level"],
            "candidate": bool(v.get("candidate")),
            "confirmed": bool(v.get("confirmed")),
        } for v in r.get("hpc_violations", [])],
        key=lambda x: x["rule"],
    )
    return {
        "is_hpc": r["is_hpc"],
        "overall": r["overall"],
        "applicability_set": sorted(r.get("applicability_set", [])),
        "score_scope": r["score_scope"],
        "gate_status": r["gate_status"],
        "dimensions": {
            k: {"score": v.get("score"), "applicable": v.get("applicable")}
            for k, v in sorted(r.get("dimensions", {}).items())
        },
        "violations": viol,
        "waiver_counts": {
            k: int((w.get(k) or {}).get("count", 0))
            for k in ("benchmark_ok", "deferred", "gpu_only")
        },
        "version_info": r.get("version_info", {}),
    }


def validate_snapshot(r: dict, name: str) -> list:
    """写入前的程序化取值校验（分数区间/维度键/计数/自洽）。"""
    errs = []
    spec = PROJECTS[name]
    is_hpc = r.get("is_hpc")

    if not isinstance(is_hpc, bool):
        return ["is_hpc 非 bool"]
    if is_hpc != spec["is_hpc"]:
        errs.append(f"is_hpc={is_hpc}，期望 {spec['is_hpc']}")

    if not is_hpc:
        if r.get("overall") is not None:
            errs.append("非 HPC 项目 overall 应为 None")
        if r.get("hpc_violations"):
            errs.append("非 HPC 项目不应有违规")
        if r.get("applicability_set"):
            errs.append("非 HPC 项目 applicability_set 应为空")
        if r.get("gate_status") != "PASS":
            errs.append("非 HPC 项目 gate 应为 PASS")
        if set(r.get("dimensions", {})) != set(DIMS):
            errs.append("维度键集合不符")
        return errs

    ov = r.get("overall")
    if not (isinstance(ov, (int, float)) and 0 <= ov <= 100):
        errs.append(f"overall 越界: {ov}")
    if "min_overall" in spec and isinstance(ov, (int, float)) and ov < spec["min_overall"]:
        errs.append(f"overall={ov} < 期望下限 {spec['min_overall']}")

    if set(r.get("dimensions", {})) != set(DIMS):
        errs.append("维度键集合不符")
    for d in DIMS:
        v = r["dimensions"][d]
        if not isinstance(v.get("applicable"), bool):
            errs.append(f"{d}.applicable 非 bool")
        s = v.get("score")
        if not (isinstance(s, (int, float)) and 0 <= s <= 100):
            errs.append(f"{d}.score 越界: {s}")

    app = set(r.get("applicability_set", []))
    if not app <= set(DIMS):
        errs.append("applicability_set 含未知维度")
    if r.get("score_scope") not in {"subset", "none"}:
        errs.append("score_scope 非法")
    if r.get("gate_status") not in VALID_GATE:
        errs.append("gate_status 非法")

    seen = set()
    rules = set()
    for v in r.get("hpc_violations", []):
        rid = v.get("rule")
        if rid in seen:
            errs.append(f"规则重复 {rid}")
        seen.add(rid)
        rules.add(rid)
        if not (rid and rid.startswith("HPC-") and rid[4:].isdigit() and 1 <= int(rid[4:]) <= 12):
            errs.append(f"规则 ID 非法 {rid}")
        c = v.get("count")
        if not (isinstance(c, int) and c >= 1):
            errs.append(f"{rid}.count 非正整数: {c}")
        if v.get("output_level") not in VALID_LEVEL:
            errs.append(f"{rid}.output_level 非法")
        if v.get("severity") not in VALID_SEV:
            errs.append(f"{rid}.severity 非法")
        if not isinstance(v.get("candidate"), bool) or not isinstance(v.get("confirmed"), bool):
            errs.append(f"{rid} candidate/confirmed 非 bool")

    for rid in spec.get("must_include", []):
        if rid not in rules:
            errs.append(f"缺少预期违规 {rid}")
    for rid in spec.get("must_not", []):
        if rid in rules:
            errs.append(f"出现预期外违规 {rid}")
    return errs


def _compare(expected: dict, actual: dict) -> list:
    errs = []
    if expected["is_hpc"] != actual["is_hpc"]:
        errs.append("is_hpc 变化")
    eo, ao = expected["overall"], actual["overall"]
    if eo is None or ao is None:
        if eo != ao:
            errs.append(f"overall {eo} -> {ao}")
    elif abs(eo - ao) > 0.5:
        errs.append(f"overall 偏差 {eo} -> {ao}")
    if expected["applicability_set"] != actual["applicability_set"]:
        errs.append(f"applicability {expected['applicability_set']} -> {actual['applicability_set']}")
    if expected["score_scope"] != actual["score_scope"]:
        errs.append("score_scope 变化")
    if expected["gate_status"] != actual["gate_status"]:
        errs.append(f"gate {expected['gate_status']} -> {actual['gate_status']}")
    if set(expected["dimensions"]) != set(actual["dimensions"]):
        errs.append("维度键变化")
    else:
        for d in expected["dimensions"]:
            ed, ad = expected["dimensions"][d], actual["dimensions"][d]
            if ed["applicable"] != ad["applicable"]:
                errs.append(f"{d}.applicable 变化")
            if ed["score"] is None or ad["score"] is None:
                if ed["score"] != ad["score"]:
                    errs.append(f"{d}.score 变化")
            elif abs(ed["score"] - ad["score"]) > 0.5:
                errs.append(f"{d}.score 偏差 {ed['score']} -> {ad['score']}")
    if expected["violations"] != actual["violations"]:
        errs.append(f"违规变化 {expected['violations']} -> {actual['violations']}")
    if expected["waiver_counts"] != actual["waiver_counts"]:
        errs.append("豁免计数变化")
    if expected["version_info"] != actual["version_info"]:
        errs.append("版本信息变化")
    return errs


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_hpc_baseline(name):
    spec = PROJECTS[name]
    root = spec["path"]
    if not os.path.isdir(root):
        pytest.skip(f"样本不存在: {root}")

    r1 = HpcArchitectureMetrics(root).all_metrics()
    r2 = HpcArchitectureMetrics(root).all_metrics()
    assert _stable(r1) == _stable(r2), "确定性失败：两次结果不一致"

    errs = validate_snapshot(r1, name)
    assert not errs, "程序化取值校验失败: " + "; ".join(errs)

    snap_path = SNAP_DIR / f"hpc_{name}.json"
    actual = {"project": name, **_stable(r1)}

    if os.environ.get("ARCH_REGRESSION_UPDATE") == "1":
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        snap_path.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        return

    assert snap_path.exists(), f"缺少基线 {snap_path.name}；请先带 ARCH_REGRESSION_UPDATE=1 生成"
    expected = json.loads(snap_path.read_text(encoding="utf-8"))
    diffs = _compare(expected, actual)
    assert not diffs, "回归偏差: " + "; ".join(diffs)
