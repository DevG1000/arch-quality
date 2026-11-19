# -*- coding: utf-8 -*-
"""化石代码回归测试（5 基线）。

- 基线：good/legacy_fortran/legacy_cpp/clone/debt
- 只比较稳定字段；ARCH_REGRESSION_UPDATE=1 时先校验再写快照
- 同一项目连续两次结果一致（确定性）
"""

import json
import os
from pathlib import Path

import pytest

from arch_quality.arch_metrics_fossil_code import FossilCodeMetrics

SNAP_DIR = Path(__file__).parent / "snapshots"
PROJECTS_DIR = Path(__file__).resolve().parents[1] / "mutation" / "projects"

PROJECTS = {
    "good_project_fossil": {"path": PROJECTS_DIR / "good_project_fossil", "is_fossil": False},
    "legacy_fortran_fossil": {"path": PROJECTS_DIR / "legacy_fortran_fossil", "is_fossil": True},
    "legacy_cpp_fossil": {"path": PROJECTS_DIR / "legacy_cpp_fossil", "is_fossil": True},
    "clone_fossil": {"path": PROJECTS_DIR / "clone_fossil", "is_fossil": True},
    "debt_fossil": {"path": PROJECTS_DIR / "debt_fossil", "is_fossil": True},
}

DIMS = ["legacy", "dead", "clone", "debt"]
VALID_LEVEL = {"ERROR", "WARNING", "INFO"}
VALID_SEV = {"HIGH", "MEDIUM", "LOW"}
VALID_GATE = {"PASS", "WARN", "BLOCK"}


def _stable(r: dict) -> dict:
    return {
        "is_fossil": r["is_fossil"],
        "overall": r["overall"],
        "applicability_set": sorted(r.get("applicability_set", [])),
        "score_scope": r["score_scope"],
        "gate_status": r["gate_status"],
        "dimensions": {
            k: {"score": v.get("score"), "applicable": v.get("applicable")}
            for k, v in sorted(r.get("dimensions", {}).items())
        },
        "violations": sorted(
            [{
                "rule": v["rule"], "count": v["count"],
                "output_level": v["output_level"],
                "candidate": bool(v.get("candidate")),
                "confirmed": bool(v.get("confirmed")),
            } for v in r.get("fossil_violations", [])],
            key=lambda x: x["rule"],
        ),
        "version_info": r.get("version_info", {}),
    }


def validate_snapshot(r: dict, name: str) -> list:
    errs = []
    spec = PROJECTS[name]
    if not isinstance(r.get("is_fossil"), bool):
        return ["is_fossil 非 bool"]
    if r["is_fossil"] != spec["is_fossil"]:
        errs.append("is_fossil 与预期不符")
    if not r["is_fossil"]:
        if r.get("overall") is not None:
            errs.append("非化石项目 overall 应为 None")
        if r.get("fossil_violations"):
            errs.append("非化石项目不应有违规")
        if r.get("applicability_set"):
            errs.append("非化石项目 applicability_set 应为空")
        if r.get("gate_status") != "PASS":
            errs.append("非化石项目 gate 应为 PASS")
        if set(r.get("dimensions", {})) != set(DIMS):
            errs.append("维度集不完整")
        return errs

    ov = r.get("overall")
    if not (isinstance(ov, (int, float)) and 0 <= ov <= 100):
        errs.append("overall 越界: %r" % (ov,))
    if set(r.get("dimensions", {})) != set(DIMS):
        errs.append("维度集不完整")
    for d in DIMS:
        v = r["dimensions"][d]
        s = v.get("score")
        if not (isinstance(s, (int, float)) and 0 <= s <= 100):
            errs.append("%s.score 越界: %r" % (d, s))
        if not isinstance(v.get("applicable"), bool):
            errs.append("%s.applicable 非 bool" % d)
    if r.get("score_scope") != "project":
        errs.append("score_scope 应为 project")
    if r.get("gate_status") not in VALID_GATE:
        errs.append("gate_status 非法")
    seen = set()
    for v in r.get("fossil_violations", []):
        rid = v.get("rule")
        if rid in seen:
            errs.append("规则重复 %s" % rid)
        seen.add(rid)
        if not (isinstance(rid, str) and rid.startswith("FOS-") and rid[4:].isdigit()
                and 1 <= int(rid[4:]) <= 12):
            errs.append("规则 ID 非法 %r" % (rid,))
        if not (isinstance(v.get("count"), int) and v["count"] >= 1):
            errs.append("%s.count 非法" % rid)
        if v.get("output_level") not in VALID_LEVEL:
            errs.append("%s.output_level 非法" % rid)
        if v.get("severity") not in VALID_SEV:
            errs.append("%s.severity 非法" % rid)
        if not isinstance(v.get("candidate"), bool) or not isinstance(v.get("confirmed"), bool):
            errs.append("%s candidate/confirmed 非 bool" % rid)
    return errs


@pytest.mark.parametrize("name", list(PROJECTS))
def test_fossil_regression(name):
    spec = PROJECTS[name]
    assert Path(spec["path"]).exists(), "缺少样本 %s" % spec["path"]
    r = FossilCodeMetrics(str(spec["path"])).all_metrics()
    errs = validate_snapshot(r, name)
    assert not errs, errs

    snap_path = SNAP_DIR / ("fossil_%s.json" % name)
    stable = _stable(r)
    if os.getenv("ARCH_REGRESSION_UPDATE") == "1":
        snap_path.write_text(json.dumps(stable, ensure_ascii=False, indent=2), encoding="utf-8")
    assert snap_path.exists(), "缺少快照 %s" % snap_path
    expected = json.loads(snap_path.read_text(encoding="utf-8-sig"))
    assert stable == expected, "快照漂移: %s" % name


@pytest.mark.parametrize("name", [n for n in PROJECTS if PROJECTS[n]["is_fossil"]])
def test_fossil_deterministic(name):
    root = str(PROJECTS[name]["path"])
    a = _stable(FossilCodeMetrics(root).all_metrics())
    b = _stable(FossilCodeMetrics(root).all_metrics())
    assert a == b
