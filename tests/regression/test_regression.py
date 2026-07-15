"""
test_regression.py - Multilang dependency regression test framework

Validates that MultilangMetrics produces stable, predictable results
against 5 benchmark projects covering 12+ MLR rules.

Projects:
  - OpenFOAM-v2512: C++/C/Python, baseline regression (no MLR violations)
  - BRL-CAD: C++/C/Tcl/Fortran/Python/SWIG, MLR-004/010/012
  - FreeCAD-CAM: C++/Python/TypeScript/C, MLR-001/003/006/008
  - FreeCAD-Fem: C++/Python/C/TypeScript, MLR-005/006
  - ElmerFEM: Fortran/C++/C/Lua/Python/Tcl, MLR-008/010/012

Snapshot update: set environment variable ARCH_REGRESSION_UPDATE=1

MLR rule coverage:
  MLR-001  cross-language cycles    -> FreeCAD-CAM
  MLR-001b same-language cycles     -> ElmerFEM (Fortran use/call)
  MLR-003  binding inconsistency    -> FreeCAD-CAM (pybind11 .def())
  MLR-004  script boundary          -> BRL-CAD (Tcl namespace)
  MLR-005  callback depth          -> FreeCAD-Fem (depth-2/3)
  MLR-006  hot module               -> OpenFOAM, BRL-CAD, FreeCAD
  MLR-008  GIL deadlock risk        -> FreeCAD-CAM, ElmerFEM
  MLR-010  FFI memory ownership    -> BRL-CAD (C malloc), ElmerFEM
  MLR-012  missing ISO_C_BINDING   -> OpenFOAM, BRL-CAD, ElmerFEM

NOT covered by project regression (unit tests only):
  MLR-002  binding layer missing   -> all 5 projects have bindings, condition never met
  MLR-007  TNT module (impact radius) -> all 5 projects have radius <= threshold
  MLR-009  generic type in binding  -> all 5 projects use pybind11/SWIG, not ctypes
"""

import json
import os
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from arch_quality.arch_metrics_multilang import MultilangMetrics

SNAP_DIR = Path(__file__).resolve().parent / "snapshots"
UPDATE_SNAPSHOTS = os.environ.get("ARCH_REGRESSION_UPDATE", "") == "1"

TOLERANCE_OVERALL = 0.5
TOLERANCE_DIMENSION = 1.0
TOLERANCE_FILE_COUNT_PCT = 0.02
TOLERANCE_FORTRAN_HIT_RATE = 0.05


def _load_snapshot(name):
    path = SNAP_DIR / f"{name}.json"
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _save_snapshot(name, data):
    path = SNAP_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _compute_actual(root_path):
    m = MultilangMetrics(root_path)
    result = m.all_metrics()

    c = Counter()
    for v in result.get("mlr_violations", []):
        c[(v["rule"], v["severity"])] += v["count"]
    mlr_violations = {}
    for (r, s), cnt in sorted(c.items()):
        mlr_violations[f"{r}|{s}"] = cnt

    dimensions = {}
    for k, v in result.get("dimensions", {}).items():
        dimensions[k] = v.get("score", 0) if isinstance(v, dict) else v

    return {
        "multilang_overall": result["overall"],
        "is_single_language": result["is_single_language"],
        "languages": result["languages"],
        "file_count": result["files"]["total"],
        "files_by_lang": result["files"]["by_lang"],
        "dimensions": dimensions,
        "mlr_violations": mlr_violations,
        "fortran_mapping": result.get("fortran_mapping", {}),
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
                snap["snapshot_date"] = "2026-06-08"
                snap["root_path"] = cls.root_path_local
                _save_snapshot(cls.snap_name_local, snap)

        def test_overall_score(self):
            snap = _load_snapshot(self.snap_name_local)
            expected = snap["multilang_overall"]
            actual = self._actual["multilang_overall"]
            if UPDATE_SNAPSHOTS:
                return
            self.assertAlmostEqual(
                actual,
                expected,
                delta=TOLERANCE_OVERALL,
                msg=(
                    f"{self.project_name_local}: overall score {actual} "
                    f"differs from snapshot {expected} "
                    f"(tolerance +/-{TOLERANCE_OVERALL})"
                ),
            )

        def test_dimension_scores(self):
            snap = _load_snapshot(self.snap_name_local)
            for dim_name, expected in snap["dimensions"].items():
                actual = self._actual["dimensions"].get(dim_name)
                if actual is None:
                    self.fail(
                        f"{self.project_name_local}: dimension '{dim_name}' "
                        f"missing from actual results"
                    )
                if UPDATE_SNAPSHOTS:
                    continue
                self.assertAlmostEqual(
                    actual,
                    expected,
                    delta=TOLERANCE_DIMENSION,
                    msg=(
                        f"{self.project_name_local}: {dim_name}={actual} "
                        f"differs from snapshot {expected} "
                        f"(tolerance +/-{TOLERANCE_DIMENSION})"
                    ),
                )

        def test_mlr_violation_counts(self):
            snap = _load_snapshot(self.snap_name_local)
            expected_rules = snap["mlr_violations"]
            actual_rules = self._actual["mlr_violations"]

            if UPDATE_SNAPSHOTS:
                return

            all_keys = sorted(set(list(expected_rules.keys()) + list(actual_rules.keys())))

            for key in all_keys:
                exp = expected_rules.get(key, 0)
                act = actual_rules.get(key, 0)

                if exp == 0 and act > 0:
                    parts = key.split("|")
                    rule = parts[0] if parts else key
                    if rule not in snap.get("required_mlr_rules", []):
                        self.fail(
                            f"{self.project_name_local}: NEW violation {key}={act} "
                            f"(not in snapshot). Update snapshot if expected."
                        )

                if exp > 0 and act == 0:
                    self.fail(
                        f"{self.project_name_local}: MISSING violation {key} "
                        f"(snapshot={exp}, actual=0). Rule may have regressed."
                    )

                if exp > 0 and act > 0:
                    tolerance = max(1, int(exp * 0.05))
                    if abs(act - exp) > max(tolerance, 5):
                        self.fail(
                            f"{self.project_name_local}: {key} count shifted: "
                            f"snapshot={exp}, actual={act} "
                            f"(tolerance +/-{max(tolerance, 5)})"
                        )

        def test_language_composition(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS:
                return

            expected_langs = set(snap["languages"])
            actual_langs = set(self._actual["languages"])
            self.assertEqual(
                expected_langs,
                actual_langs,
                f"{self.project_name_local}: language set changed. "
                f"Expected {sorted(expected_langs)}, got {sorted(actual_langs)}",
            )

            expected_counts = snap["files_by_lang"]
            actual_counts = self._actual["files_by_lang"]
            for lang in expected_langs:
                exp = expected_counts.get(lang, 0)
                act = actual_counts.get(lang, 0)
                if exp > 0:
                    tol = max(1, int(exp * TOLERANCE_FILE_COUNT_PCT))
                    if abs(act - exp) > tol:
                        self.fail(
                            f"{self.project_name_local}: {lang} file count "
                            f"snapshot={exp}, actual={act} "
                            f"(tolerance +/-{tol})"
                        )

        def test_covered_rules_present(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS:
                return

            required = snap.get("required_mlr_rules", [])
            actual_rules = self._actual["mlr_violations"]

            for rule in required:
                found = any(k.startswith(rule + "|") for k in actual_rules)
                self.assertTrue(
                    found,
                    f"{self.project_name_local}: required rule {rule} "
                    f"not found in violations. "
                    f"Available: {list(actual_rules.keys())}",
                )

        def test_fortran_mapping(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS:
                return

            expected_fm = snap.get("fortran_mapping", {})
            if expected_fm.get("module_map_size", 0) == 0:
                self.skipTest("No Fortran modules in this project")

            actual_fm = self._actual.get("fortran_mapping", {})

            use_hit = actual_fm.get("use_hit_rate", 1.0)
            expected_use_hit = expected_fm.get("use_hit_rate", 1.0)
            self.assertAlmostEqual(
                use_hit,
                expected_use_hit,
                delta=TOLERANCE_FORTRAN_HIT_RATE,
                msg=(
                    f"{self.project_name_local}: Fortran use_hit_rate "
                    f"{use_hit} differs from snapshot {expected_use_hit} "
                    f"(tolerance +/-{TOLERANCE_FORTRAN_HIT_RATE})"
                ),
            )

            call_hit = actual_fm.get("call_hit_rate", 1.0)
            expected_call_hit = expected_fm.get("call_hit_rate", 1.0)
            self.assertAlmostEqual(
                call_hit,
                expected_call_hit,
                delta=TOLERANCE_FORTRAN_HIT_RATE,
                msg=(
                    f"{self.project_name_local}: Fortran call_hit_rate "
                    f"{call_hit} differs from snapshot {expected_call_hit} "
                    f"(tolerance +/-{TOLERANCE_FORTRAN_HIT_RATE})"
                ),
            )

    TestCase.__name__ = class_name
    TestCase.__qualname__ = class_name
    return TestCase


TestOpenFOAM = _make_project_class(
    "OpenFOAM-v2512",
    "openfoam_v2512",
    r"D:\OPENSOURCE\OpenFOAM-v2512",
)

TestBrlCad = _make_project_class(
    "BRL-CAD",
    "brl_cad",
    r"D:\OPENSOURCE\BRL-CAD",
)

TestFreeCadCam = _make_project_class(
    "FreeCAD-CAM",
    "freecad_cam",
    r"D:\OPENSOURCE\FreeCAD\src\Mod\CAM",
)

TestFreeCadFem = _make_project_class(
    "FreeCAD-Fem",
    "freecad_fem",
    r"D:\OPENSOURCE\FreeCAD\src\Mod\Fem",
)

TestElmerFem = _make_project_class(
    "ElmerFEM",
    "elmerfem",
    r"D:\OPENSOURCE\ElmerFEM",
)

if __name__ == "__main__":
    unittest.main()