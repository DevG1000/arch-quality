# -*- coding: utf-8 -*-
"""test_numerical_regression.py — 数值算法精度回归测试框架"""

import json
import os
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from arch_quality.arch_metrics_numerical_accuracy import NumericalAccuracyMetrics

SNAP_DIR = Path(__file__).resolve().parent / "snapshots"
UPDATE_SNAPSHOTS = os.environ.get("ARCH_REGRESSION_UPDATE", "") == "1"

TOLERANCE_OVERALL = 1.0
TOLERANCE_DIMENSION = 2.0


def _load_snapshot(name):
    path = SNAP_DIR / f"nvr_{name}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _save_snapshot(name, data):
    path = SNAP_DIR / f"nvr_{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _compute_actual(root_path):
    m = NumericalAccuracyMetrics(root_path)
    result = m.all_metrics()

    c = Counter()
    for v in result.get("nvr_violations", []):
        c[(v["rule"], v["severity"], v.get("output_level", ""))] += v.get("count", 1)
    nvr_violations = {}
    for (r, s, ol), cnt in sorted(c.items()):
        nvr_violations[f"{r}|{s}|{ol}"] = cnt

    dimensions = {}
    for k, v in result.get("dimensions", {}).items():
        dimensions[k] = v.get("score", 0) if isinstance(v, dict) else v

    return {
        "nvr_overall": result["overall"],
        "is_numerical": result["is_numerical"],
        "dimensions": dimensions,
        "nvr_violations": nvr_violations,
    }


def _make_project_class(project_name, snap_name, root_path):
    class_name = f"TestNumeric{project_name.replace('-', '').replace(' ', '')}"

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
                snap = _load_snapshot(cls.snap_name_local) or {}
                snap.update(cls._actual)
                snap["snapshot_date"] = "2026-06-25"
                snap["root_path"] = cls.root_path_local
                _save_snapshot(cls.snap_name_local, snap)

        def test_is_numerical(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS or not snap:
                return
            self.assertEqual(
                self._actual["is_numerical"],
                snap["is_numerical"],
                f"{self.project_name_local}: is_numerical mismatch",
            )

        def test_overall_score(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS or not snap:
                return
            if not self._actual["is_numerical"]:
                self.skipTest("Non-numerical project, skipping")
            expected = snap["nvr_overall"]
            actual = self._actual["nvr_overall"]
            if actual is None:
                self.skipTest("No numerical score")
            self.assertAlmostEqual(
                actual, expected, delta=TOLERANCE_OVERALL,
                msg=f"{self.project_name_local}: overall {actual} != {expected}",
            )

        def test_dimension_scores(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS or not snap:
                return
            if not self._actual["is_numerical"]:
                self.skipTest("Non-numerical project")
            for dim_name, expected in snap["dimensions"].items():
                actual = self._actual["dimensions"].get(dim_name)
                if actual is None:
                    self.fail(f"{self.project_name_local}: missing dimension '{dim_name}'")
                self.assertAlmostEqual(
                    actual, expected, delta=TOLERANCE_DIMENSION,
                    msg=f"{self.project_name_local}: {dim_name}={actual} != {expected}",
                )

        def test_nvr_violation_counts(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS or not snap:
                return
            expected_rules = snap["nvr_violations"]
            actual_rules = self._actual["nvr_violations"]
            all_keys = sorted(set(list(expected_rules.keys()) + list(actual_rules.keys())))
            for key in all_keys:
                exp = expected_rules.get(key, 0)
                act = actual_rules.get(key, 0)
                if exp > 0 and act == 0:
                    self.fail(f"{self.project_name_local}: MISSING {key} (expected {exp})")
                if exp > 0 and act > 0:
                    tolerance = max(1, int(exp * 0.2))
                    if abs(act - exp) > max(tolerance, 2):
                        self.fail(f"{self.project_name_local}: {key} changed: {exp} -> {act}")

    TestCase.__name__ = class_name
    TestCase.__qualname__ = class_name
    return TestCase


TestNumericOpenFOAM = _make_project_class(
    "OpenFOAM-v2512",
    "openfoam",
    r"D:\OPENSOURCE\OpenFOAM-v2512",
)

TestNumericCalculiX = _make_project_class(
    "CalculiX (ccx_2.23)",
    "calculix",
    r"D:\OPENSOURCE\CalculiX\CalculiX\ccx_2.23",
)

TestNumericMOOSE = _make_project_class(
    "MOOSE",
    "moose",
    r"D:\OPENSOURCE\moose",
)

if __name__ == "__main__":
    unittest.main()
