"""
test_template_regression.py - Template metaprogramming regression test framework

Validates that TemplateMetaprogrammingMetrics produces stable, predictable results
against benchmark C++ projects covering 12 MLR rules (MLR-013 through MLR-024).

Projects (3 tiers):
  Tier 1 (smoke - always available):
    - Eigen: header-only template library, deep nesting + redundancy
    - Boost.MPL: template metaprogramming, deep nesting + SFINAE
  Tier 2 (full - large open-source C++):
    - OpenFOAM-v2512: C++/C/Python, moderate template usage
    - BRL-CAD: C++/C/Tcl/Fortran/Python, MLR-013/015/024
    - FreeCAD: C++/Python, heavy template + header coupling
  Tier 3 (specialized):
    - ElmerFEM: Fortran/C++/C, light template usage
    - Boost.GIL: image processing templates, moderate bloat
    - Folly: Facebook C++ library, heavy template + extern template
    - Abseil: Google C++ library, C++20 modules transition
    - Range-v3: concept-heavy templates, modern C++
    - Hana: heterogeneous sequences, extreme compile-time computation

Snapshot update: set environment variable ARCH_REGRESSION_UPDATE=1

MLR rule coverage:
  MLR-013  compile-time coupling      -> OpenFOAM, BRL-CAD, FreeCAD
  MLR-014  redundant instantiation    -> Eigen, Boost.MPL, Folly
  MLR-015  header influence radius    -> OpenFOAM, BRL-CAD, FreeCAD
  MLR-016  deep nesting depth         -> Eigen, Boost.MPL, Hana
  MLR-017  binary bloat ratio        -> Eigen, Boost.GIL, Range-v3
  MLR-018  unnecessary templating      -> OpenFOAM, FreeCAD
  MLR-019  missing extern template    -> Folly, Abseil
  MLR-020  concept overloading         -> Range-v3
  MLR-021  SFINAE complexity           -> Boost.MPL, Hana
  MLR-022  ADL ambiguity              -> Folly, Abseil
  MLR-023  duplicated instantiation   -> Eigen, Folly (merged with MLR-014)
  MLR-024  header cycle dependency    -> BRL-CAD, FreeCAD

NOT covered by project regression (unit tests only):
  MLR-014 waiver (@template_specialization_required)
  MLR-017 waiver (@allow_binary_bloat)
  MLR-018 waiver (@reserved_for_future_extension)
  MLR-024 C++20 modules downgrade (.ixx/.cppm/.mpp)
"""

import json
import os
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from arch_quality.arch_metrics_template import TemplateMetaprogrammingMetrics

SNAP_DIR = Path(__file__).resolve().parent / "snapshots"
UPDATE_SNAPSHOTS = os.environ.get("ARCH_REGRESSION_UPDATE", "") == "1"

TOLERANCE_OVERALL = 0.5
TOLERANCE_DIMENSION = 1.0
TOLERANCE_FILE_COUNT_PCT = 0.02


def _load_snapshot(name):
    path = SNAP_DIR / f"{name}.json"
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _save_snapshot(name, data):
    path = SNAP_DIR / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _compute_actual(root_path):
    m = TemplateMetaprogrammingMetrics(root_path)
    result = m.all_metrics()

    c = Counter()
    for v in result.get("mlr_violations", []):
        key = v["rule"]
        if v.get("merge_to"):
            key += f"+merge_to_{v['merge_to']}"
        ol = v.get("output_level", v.get("severity", "WARNING"))
        c[(key, v["severity"], ol)] += v["count"]
    mlr_violations = {}
    for (r, s, ol), cnt in sorted(c.items()):
        mlr_violations[f"{r}|{s}|{ol}"] = cnt

    dimensions = {}
    for k, v in result.get("dimensions", {}).items():
        dimensions[k] = v.get("score", 0) if isinstance(v, dict) else v

    return {
        "template_overall": result["overall"],
        "is_cpp_project": result["is_cpp_project"],
        "cpp_file_count": result.get("cpp_file_count", 0),
        "file_count": result["files"]["total"],
        "dimensions": dimensions,
        "mlr_violations": mlr_violations,
    }


def _make_project_class(project_name, snap_name, root_path):
    class_name = f"TestTemplate{project_name.replace('-', '').replace(' ', '').replace('.', '')}"

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
                snap["snapshot_date"] = "2026-06-11"
                snap["root_path"] = cls.root_path_local
                _save_snapshot(cls.snap_name_local, snap)

        def test_is_cpp_project(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS:
                return
            expected = snap["is_cpp_project"]
            actual = self._actual["is_cpp_project"]
            self.assertEqual(
                actual,
                expected,
                f"{self.project_name_local}: is_cpp_project={actual}, expected={expected}",
            )

        def test_overall_score(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS:
                return
            if snap.get("is_cpp_project") is False:
                self.skipTest("Non-C++ project, no template score")
            expected = snap["template_overall"]
            actual = self._actual["template_overall"]
            if actual is None:
                self.skipTest("Non-C++ project, no template score")
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
            if UPDATE_SNAPSHOTS:
                return
            if snap.get("is_cpp_project") is False:
                self.skipTest("Non-C++ project, no dimensions")
            for dim_name, expected in snap["dimensions"].items():
                actual = self._actual["dimensions"].get(dim_name)
                if actual is None:
                    self.fail(
                        f"{self.project_name_local}: dimension '{dim_name}' "
                        f"missing from actual results"
                    )
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
            if UPDATE_SNAPSHOTS:
                return

            expected_rules = snap["mlr_violations"]
            actual_rules = self._actual["mlr_violations"]

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

        def test_cpp_file_count(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS:
                return
            expected = snap["cpp_file_count"]
            actual = self._actual["cpp_file_count"]
            if expected > 0:
                tol = max(1, int(expected * TOLERANCE_FILE_COUNT_PCT))
                if abs(actual - expected) > tol:
                    self.fail(
                        f"{self.project_name_local}: cpp_file_count "
                        f"snapshot={expected}, actual={actual} "
                        f"(tolerance +/-{tol})"
                    )

        def test_covered_rules_present(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS:
                return

            required = snap.get("required_mlr_rules", [])
            actual_rules = self._actual["mlr_violations"]

            for rule in required:
                found = any(k.startswith(rule + "|") for k in actual_rules) or \
                         any(k.startswith(rule + "+") for k in actual_rules)
                self.assertTrue(
                    found,
                    f"{self.project_name_local}: required rule {rule} "
                    f"not found in violations. "
                    f"Available: {list(actual_rules.keys())}",
                )

        def test_merge_flags(self):
            snap = _load_snapshot(self.snap_name_local)
            if UPDATE_SNAPSHOTS:
                return
            forced_merges = snap.get("forced_merge_rules", [])
            actual_rules = self._actual["mlr_violations"]
            for merge_key in forced_merges:
                found = any(merge_key in k.split("|")[0] for k in actual_rules)
                self.assertTrue(
                    found,
                    f"{self.project_name_local}: forced merge rule {merge_key} "
                    f"not found in violations.",
                )

    TestCase.__name__ = class_name
    TestCase.__qualname__ = class_name
    return TestCase


TestTemplateEigen = _make_project_class(
    "Eigen",
    "tpl_eigen",
    r"D:\OPENSOURCE\Eigen",
)

TestTemplateBoostMpl = _make_project_class(
    "Boost.MPL",
    "tpl_boost_mpl",
    r"D:\OPENSOURCE\boost\libs\mpl",
)

TestTemplateOpenFOAM = _make_project_class(
    "OpenFOAM-v2512",
    "tpl_openfoam_v2512",
    r"D:\OPENSOURCE\OpenFOAM-v2512",
)

TestTemplateBrlCad = _make_project_class(
    "BRL-CAD",
    "tpl_brl_cad",
    r"D:\OPENSOURCE\BRL-CAD",
)

TestTemplateFreeCad = _make_project_class(
    "FreeCAD",
    "tpl_freecad",
    r"D:\OPENSOURCE\FreeCAD",
)

TestTemplateElmerFem = _make_project_class(
    "ElmerFEM",
    "tpl_elmerfem",
    r"D:\OPENSOURCE\ElmerFEM",
)

TestTemplateBoostGil = _make_project_class(
    "Boost.GIL",
    "tpl_boost_gil",
    r"D:\OPENSOURCE\boost\libs\gil",
)

TestTemplateFolly = _make_project_class(
    "Folly",
    "tpl_folly",
    r"D:\OPENSOURCE\folly",
)

TestTemplateAbseil = _make_project_class(
    "Abseil",
    "tpl_abseil",
    r"D:\OPENSOURCE\abseil-cpp",
)

TestTemplateRangeV3 = _make_project_class(
    "Range-v3",
    "tpl_range_v3",
    r"D:\OPENSOURCE\range-v3",
)

TestTemplateHana = _make_project_class(
    "Hana",
    "tpl_hana",
    r"D:\OPENSOURCE\boost\libs\hana",
)

if __name__ == "__main__":
    unittest.main()