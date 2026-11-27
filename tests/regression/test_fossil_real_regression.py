# -*- coding: utf-8 -*-
"""化石代码真实项目回归（可选，RUN_FOSSIL_REAL=1）。

默认跳过以保持 CI 快速；真实项目快照：Code_Aster / BRL-CAD / OpenFOAM。
"""

import json
import os
from pathlib import Path

import pytest

from arch_quality.arch_metrics_fossil_code import FossilCodeMetrics

SNAP_DIR = Path(__file__).parent / "snapshots"
RUN_REAL = os.getenv("RUN_FOSSIL_REAL") == "1"

PROJECTS = {
    "code_aster": r"D:\OPENSOURCE\code_aster",
    "brl_cad": r"D:\OPENSOURCE\brl-cad",
    "openfoam": r"D:\OPENSOURCE\OpenFOAM-v2512",
}


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


@pytest.mark.skipif(not RUN_REAL, reason="set RUN_FOSSIL_REAL=1 to run real baselines")
@pytest.mark.parametrize("name", list(PROJECTS))
def test_fossil_real_regression(name):
    root = Path(PROJECTS[name])
    assert root.exists(), "缺少真实样本 %s" % root
    r = FossilCodeMetrics(str(root)).all_metrics()
    stable = _stable(r)
    snap = SNAP_DIR / ("fossil_%s.json" % name)
    assert snap.exists(), "缺少快照 %s" % snap
    expected = json.loads(snap.read_text(encoding="utf-8-sig"))
    assert stable == expected, "真实基线漂移: %s" % name
