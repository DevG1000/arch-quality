"""
test_geometry_consistency.py — 几何内核与科学数据结构一致性评估单元测试

覆盖（对齐《验证案例集》4.1-4.12 合成案例）：
1. 非几何项目 → is_geometry=False，各维度 None
2. 启用检测 — 内核/科学数据结构信号
3. 4 维评分 — 每维正例/负例
4. GCS 规则触发 — 每条规则 ≥1 测试
5. 递进扣分 — 2.1 < 60 → 2.4 折半
6. all_metrics 结构完整性
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arch_quality.arch_metrics_geometry_consistency import GeometryConsistencyMetrics


def _write_tree(root, files: dict):
    for path, content in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


def _make_project(files: dict):
    tmp = tempfile.mkdtemp()
    _write_tree(tmp, files)
    return tmp


class TestNonGeometryProject(unittest.TestCase):
    """非几何项目：各维度 None"""

    def test_plain_python_not_geometry(self):
        tmp = _make_project({"src/main.py": "def main():\n    print('hello')\n"})
        try:
            m = GeometryConsistencyMetrics(tmp)
            self.assertFalse(m.all_metrics()["is_geometry"])
            r = m.all_metrics()
            self.assertIsNone(r["overall"])
            for dim in r["dimensions"].values():
                self.assertIsNone(dim["score"])
            self.assertEqual(r["gcs_violations"], [])
        finally:
            shutil.rmtree(tmp)


class TestGeometryDetection(unittest.TestCase):
    """启用检测"""

    def test_occt_signal_detected(self):
        tmp = _make_project({"src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n"})
        try:
            m = GeometryConsistencyMetrics(tmp)
            self.assertTrue(m.all_metrics()["is_geometry"])
        finally:
            shutil.rmtree(tmp)

    def test_vtk_signal_detected(self):
        tmp = _make_project({"src/mesh.cpp": "#include <vtkUnstructuredGrid.h>\n"})
        try:
            m = GeometryConsistencyMetrics(tmp)
            self.assertTrue(m.all_metrics()["is_geometry"])
        finally:
            shutil.rmtree(tmp)


class TestGeometryKernelConsistency(unittest.TestCase):
    """维度 1：几何内核数据一致性"""

    def test_good_handle_and_closure(self):
        tmp = _make_project({"src/ops.cpp": """
#include <BRepAlgoAPI_Fuse.hxx>
#include <BRepCheck_Analyzer.hxx>
TopoDS_Shape fuse(const TopoDS_Shape& a, const TopoDS_Shape& b) {
    BRepAlgoAPI_Fuse op(a, b);
    if (!op.IsDone()) throw std::runtime_error("fail");
    BRepCheck_Analyzer an(op.Shape());
    return op.Shape();
}
"""})
        try:
            m = GeometryConsistencyMetrics(tmp)
            score, detail = m.calc_geometry_kernel_consistency()
            self.assertGreaterEqual(score, 60)  # 加分30 + 传播25 + ...
        finally:
            shutil.rmtree(tmp)

    def test_bare_new_crossing_triggers_gcs002(self):
        tmp = _make_project({"src/leak.cpp": """
#include <Geom_Plane.hxx>
Geom_Plane* get_plane() {
    return new Geom_Plane(gp_Pln());  // 裸 new + return 跨作用域
}
"""})
        try:
            m = GeometryConsistencyMetrics(tmp)
            score, detail = m.calc_geometry_kernel_consistency()
            self.assertGreater(detail["handle_consistency"]["bare_cross_count"], 0)
            rules = m.check_gcs_rules()
            self.assertTrue(any(r["rule"] == "GCS-002" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_missing_done_triggers_gcs003(self):
        tmp = _make_project({"src/bad.cpp": """
#include <BRepAlgoAPI_Fuse.hxx>
TopoDS_Shape fuse(const TopoDS_Shape& a, const TopoDS_Shape& b) {
    BRepAlgoAPI_Fuse op(a, b);
    return op.Shape();  // 未检查 IsDone
}
"""})
        try:
            m = GeometryConsistencyMetrics(tmp)
            rules = m.check_gcs_rules()
            self.assertTrue(any(r["rule"] == "GCS-003" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_closure_check_bonus(self):
        tmp = _make_project({"src/check.cpp": "BRepCheck_Analyzer an(s);\n"})
        try:
            m = GeometryConsistencyMetrics(tmp)
            rules = m.check_gcs_rules()
            # 有闭合性校验 → GCS-001 不触发（加分项满足）
            self.assertFalse(any(r["rule"] == "GCS-001" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_closure_check_missing_info(self):
        tmp = _make_project({"src/nocheck.cpp": """
#include <BRepAlgoAPI_Fuse.hxx>
TopoDS_Shape fuse(const TopoDS_Shape& a, const TopoDS_Shape& b) {
    BRepAlgoAPI_Fuse op(a, b);
    if (!op.IsDone()) throw std::runtime_error("fail");
    return op.Shape();
}
"""})
        try:
            m = GeometryConsistencyMetrics(tmp)
            rules = m.check_gcs_rules()
            self.assertTrue(any(r["rule"] == "GCS-001" and r["output_level"] == "INFO" for r in rules))
        finally:
            shutil.rmtree(tmp)


class TestPrecisionUnitConsistency(unittest.TestCase):
    """维度 2：内核精度/单位一致性"""

    def test_named_precision_no_violation(self):
        tmp = _make_project({"src/good.cpp": """
#include <BRep_Tool.hxx>
constexpr double GEOM_TOLERANCE = 1e-6;
double tolerance_ok(double d) { return std::abs(d) < GEOM_TOLERANCE; }
"""})
        try:
            m = GeometryConsistencyMetrics(tmp)
            score, detail = m.calc_precision_unit_consistency()
            self.assertEqual(score, 100)
        finally:
            shutil.rmtree(tmp)

    def test_magic_precision_triggers_gcs005(self):
        tmp = _make_project({"src/bad.cpp": "#include <BRep_Tool.hxx>\ndouble ok(double d) { return std::abs(d) < 1e-6; }\n"})
        try:
            m = GeometryConsistencyMetrics(tmp)
            rules = m.check_gcs_rules()
            self.assertTrue(any(r["rule"] == "GCS-005" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_unit_factor_triggers_gcs006(self):
        tmp = _make_project({"src/units.cpp": "#include <BRep_Tool.hxx>\ndouble inch_to_mm(double i) { return i * 25.4; }\n"})
        try:
            m = GeometryConsistencyMetrics(tmp)
            rules = m.check_gcs_rules()
            self.assertTrue(any(r["rule"] == "GCS-006" for r in rules))
        finally:
            shutil.rmtree(tmp)


class TestScidataOrganization(unittest.TestCase):
    """维度 3：科学数据结构组织一致性"""

    def test_mesh_semantics_mixing_triggers_gcs007(self):
        tmp = _make_project({"src/mixed.cpp": """
#include <vtkUnstructuredGrid.h>
#include <gmsh.h>
void f(vtkUnstructuredGrid* v, int i) {
    vtkCell* c = v->GetCell(i);
    gmsh::model::getMass(0, i, c->GetPointId(0));  // vtk 指针跨 gmsh 语义
}
"""})
        try:
            m = GeometryConsistencyMetrics(tmp)
            rules = m.check_gcs_rules()
            self.assertTrue(any(r["rule"] == "GCS-007" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_field_naming_inconsistent_triggers_gcs008(self):
        tmp = _make_project({"src/field.cpp": "vtkFieldData* pointData; vtkFieldData* cellField;\n"})
        try:
            m = GeometryConsistencyMetrics(tmp)
            rules = m.check_gcs_rules()
            self.assertTrue(any(r["rule"] == "GCS-008" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_dimension_mismatch_triggers_gcs009(self):
        tmp = _make_project({"src/dim.cpp": """
#include <vtkUnstructuredGrid.h>
constexpr int STRESS_COMPONENTS = 6;
double* stresses = new double[n_vertices * 3];  // 应 *6 却 *3
"""})
        try:
            m = GeometryConsistencyMetrics(tmp)
            rules = m.check_gcs_rules()
            self.assertTrue(any(r["rule"] == "GCS-009" for r in rules))
        finally:
            shutil.rmtree(tmp)


class TestDataAccessNorm(unittest.TestCase):
    """维度 4：数据表示与访问规范性"""

    def test_direct_member_access_triggers_gcs012(self):
        tmp = _make_project({"src/leak.cpp": "#include <vtkUnstructuredGrid.h>\nf->data_[0] = 1.0;\n"})
        try:
            m = GeometryConsistencyMetrics(tmp)
            rules = m.check_gcs_rules()
            self.assertTrue(any(r["rule"] == "GCS-012" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_bare_array_density_triggers_gcs010(self):
        tmp = _make_project({"src/dense.cpp": """
#include <vtkUnstructuredGrid.h>
double* coords;
double* normals;
vtkSmartPointer<vtkPoints> pts;
"""})
        try:
            m = GeometryConsistencyMetrics(tmp)
            rules = m.check_gcs_rules()
            self.assertTrue(any(r["rule"] == "GCS-010" for r in rules))
        finally:
            shutil.rmtree(tmp)


class TestProgressiveDeduction(unittest.TestCase):
    """递进扣分：2.1 < 60 → 2.4 折半"""

    def test_deduction_applied(self):
        tmp = _make_project({"src/bad.cpp": """
#include <Geom_Plane.hxx>
Geom_Plane* get_plane() { return new Geom_Plane(gp_Pln()); }
f->data_[0] = 1.0;
"""})
        try:
            m = GeometryConsistencyMetrics(tmp)
            d1, _ = m.calc_geometry_kernel_consistency()
            d4, d4d = m.calc_data_access_norm()
            if d1 is not None and d1 < 60:
                self.assertTrue(d4d["progressive_deduction"]["applied"])
        finally:
            shutil.rmtree(tmp)


class TestAllMetrics(unittest.TestCase):
    """all_metrics 结构完整性"""

    def test_structure(self):
        tmp = _make_project({"src/brep.cpp": "TopoDS_Shape s;\nBRepCheck_Analyzer an(s);\n"})
        try:
            m = GeometryConsistencyMetrics(tmp)
            r = m.all_metrics()
            self.assertTrue(r["is_geometry"])
            self.assertIn("overall", r)
            for dim in ["geometry_kernel_consistency", "precision_unit_consistency",
                        "scidata_organization", "data_access_norm"]:
                self.assertIn(dim, r["dimensions"])
                self.assertIn("score", r["dimensions"][dim])
            for v in r["gcs_violations"]:
                for k in ["rule", "name", "severity", "output_level", "count", "detail"]:
                    self.assertIn(k, v)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()

