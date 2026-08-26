"""
test_standard_regression.py - StandardMetrics 外部验证回归测试

对本地可用的真实项目运行标准架构质量评估，将结果与已建立的基线 JSON 比对。
检测评分偏移、SAR 违规数量变化等回归问题。

项目：
  - arch-quality: 本仓库（Python 为主）
  - BRL-CAD: C++/C/Tcl/Fortran/Python/SWIG
  - FreeCAD-CAM: C++/Python/C
  - OpenFOAM-apps: C++/C（applications 子目录）
  - ElmerFEM: Fortran/C++/C/Lua/Python/Tcl

快照更新：ARCH_REGRESSION_UPDATE=1
"""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from arch_quality.arch_metrics_standard import StandardMetrics

SNAP_DIR = Path(__file__).resolve().parent / "snapshots"
UPDATE_SNAPSHOTS = os.environ.get("ARCH_REGRESSION_UPDATE", "") == "1"

TOLERANCE_OVERALL = 2.0
TOLERANCE_DIMENSION = 5.0
TOLERANCE_FILE_COUNT_PCT = 0.02


def _load_snapshot(name):
    path = SNAP_DIR / f"{name}.json"
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _save_snapshot(name, data):
    path = SNAP_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _compute_actual(root_path):
    m = StandardMetrics(root_path)
    result = m.all_metrics()

    dimensions = {}
    for k, v in result.get("dimensions", {}).items():
        dimensions[k] = v.get("score", 0) if isinstance(v, dict) else v

    sar_violations = {}
    for v in result.get("sar_violations", []):
        key = v["rule"]
        sar_violations[key] = sar_violations.get(key, 0) + v.get("count", 1)

    return {
        "standard_overall": result["overall"],
        "dimensions": dimensions,
        "file_count": result["files"]["total"],
        "sar_violations": sar_violations,
    }


def _make_project_class(project_name, snap_name, root_path):
    class_name = f"Test{project_name.replace('-', '').replace(' ', '')}"

    @unittest.skipUnless(
        Path(root_path).exists(),
        f"Project directory not found: {root_path}",
    )
    class TestCase(unittest.TestCase):
        snap_name_local = snap_name
        root_path_local = root_path
        project_name_local = project_name

        @classmethod
        def setUpClass(cls):
            cls._actual = _compute_actual(cls.root_path_local)
            if UPDATE_SNAPSHOTS:
                snap = _load_snapshot(cls.snap_name_local)
                snap.update(cls._actual)
                snap["snapshot_date"] = "2026-08-21"
                snap["root_path"] = cls.root_path_local
                _save_snapshot(cls.snap_name_local, snap)

        def test_overall_score(self):
            snap = _load_snapshot(self.snap_name_local)
            expected = snap["standard_overall"]
            actual = self._actual["standard_overall"]
            if UPDATE_SNAPSHOTS:
                return
            self.assertAlmostEqual(
                actual, expected, delta=TOLERANCE_OVERALL,
                msg=(f"{self.project_name_local}: overall {actual} "
                     f"differs from snapshot {expected} "
                     f"(tolerance +/-{TOLERANCE_OVERALL})"),
            )

        def test_dimension_scores(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS:
                return
            for dim_name, expected in snap["dimensions"].items():
                actual = self._actual["dimensions"].get(dim_name)
                if actual is None:
                    self.fail(f"{self.project_name_local}: dimension "
                              f"'{dim_name}' missing")
                self.assertAlmostEqual(
                    actual, expected, delta=TOLERANCE_DIMENSION,
                    msg=(f"{self.project_name_local}: {dim_name}={actual} "
                         f"differs from snapshot {expected}"),
                )

        def test_sar_violation_counts(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS:
                return
            expected_rules = snap["sar_violations"]
            actual_rules = self._actual["sar_violations"]
            all_keys = sorted(set(list(expected_rules.keys()) +
                                  list(actual_rules.keys())))
            for key in all_keys:
                exp = expected_rules.get(key, 0)
                act = actual_rules.get(key, 0)
                if exp == 0 and act > 0:
                    self.fail(f"{self.project_name_local}: NEW SAR {key}={act} "
                              f"(not in snapshot). Update snapshot if expected.")
                if exp > 0 and act == 0:
                    self.fail(f"{self.project_name_local}: MISSING SAR {key} "
                              f"(snapshot={exp}, actual=0). Rule regressed.")

        def test_file_count(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS:
                return
            expected = snap["file_count"]
            actual = self._actual["file_count"]
            tol = max(1, int(expected * TOLERANCE_FILE_COUNT_PCT))
            self.assertLessEqual(
                abs(actual - expected), tol,
                f"{self.project_name_local}: file count "
                f"snapshot={expected}, actual={actual}",
            )

    TestCase.__name__ = class_name
    TestCase.__qualname__ = class_name
    return TestCase


TestArchQuality = _make_project_class(
    "arch-quality", "standard_arch_quality",
    r"D:\opensource\arch-quality",
)

TestBrlCadStandard = _make_project_class(
    "BRL-CAD", "standard_brl_cad",
    r"D:\OPENSOURCE\BRL-CAD",
)

TestFreeCadCamStandard = _make_project_class(
    "FreeCAD-CAM", "standard_freecad_cam",
    r"D:\OPENSOURCE\FreeCAD\src\Mod\CAM",
)

TestOpenFoamAppsStandard = _make_project_class(
    "OpenFOAM-apps", "standard_openfoam_apps",
    r"D:\OPENSOURCE\OpenFOAM-v2512\applications",
)

TestElmerFemStandard = _make_project_class(
    "ElmerFEM", "standard_elmerfem",
    r"D:\OPENSOURCE\ElmerFEM",
)


if __name__ == "__main__":
    unittest.main()