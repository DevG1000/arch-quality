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


class TestKernelSelfExclusion(unittest.TestCase):
    """T1：路径级内核目录排除扩展至全部 12 条规则"""

    def test_kernel_dir_excluded_from_gcs012(self):
        """内核目录下的直接成员访问不计入 GCS-012"""
        tmp = _make_project({
            "src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n",
            "src/occt/inner.cpp": "f->data_[0] = 1.0;\nf->internal_[1] = 2.0;\n",
        })
        try:
            m = GeometryConsistencyMetrics(tmp)
            _, d4d = m.calc_data_access_norm()
            self.assertEqual(d4d["access_encapsulation"]["direct_access_count"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_kernel_dir_excluded_from_gcs011(self):
        """内核目录下的浅拷贝不计入 GCS-011"""
        shallow = ("class Buf { vtkSmartPointer<vtkPoints> pts_;\n"
                   " public:\n Buf(const Buf& b) : pts_(b.pts_) {} };\n")
        tmp = _make_project({
            "src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n",
            "src/brep/inner.cpp": shallow,
        })
        try:
            m = GeometryConsistencyMetrics(tmp)
            _, d4d = m.calc_data_access_norm()
            self.assertEqual(d4d["copy_semantics"]["shallow_count"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_non_kernel_dir_still_counted(self):
        """非内核目录的同类违规仍应计入（防过度排除）"""
        tmp = _make_project({
            "src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n",
            "src/app/inner.cpp": "f->data_[0] = 1.0;\n",
        })
        try:
            m = GeometryConsistencyMetrics(tmp)
            _, d4d = m.calc_data_access_norm()
            self.assertGreater(d4d["access_encapsulation"]["direct_access_count"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_kernel_dir_excluded_from_gcs003(self):
        """内核目录下的 BRep 布尔操作不计入 GCS-003"""
        tmp = _make_project({
            "src/brep.cpp": "#include <BRepAlgoAPI_Fuse.hxx>\nTopoDS_Shape s;\n",
            "src/tkbool/inner.cpp": (
                "BRepAlgoAPI_Fuse *op = new BRepAlgoAPI_Fuse(a, b);\n"
                "op->Build();\nTopoDS_Shape r = op->Shape();\n"),
        })
        try:
            m = GeometryConsistencyMetrics(tmp)
            _, d1d = m.calc_geometry_kernel_consistency()
            self.assertEqual(d1d["error_propagation"]["missing_check_count"], 0)
        finally:
            shutil.rmtree(tmp)


class TestWaiverAnnotations(unittest.TestCase):
    """T2/T3：豁免注解 @kernel_exempt / @gcs_waiver"""

    def test_kernel_exempt_suppresses_gcs012(self):
        """@kernel_exempt：该文件从 12 条规则统计中剔除"""
        tmp = _make_project({
            "src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n",
            "src/hot.cpp": ("/* @kernel_exempt: 遗留适配层，待 2026-Q4 重构 */\n"
                            "f->data_[0] = 1.0;\nf->internal_[1] = 2.0;\n"),
        })
        try:
            m = GeometryConsistencyMetrics(tmp)
            _, d4d = m.calc_data_access_norm()
            self.assertEqual(d4d["access_encapsulation"]["direct_access_count"], 0)
            self.assertIn("src/hot.cpp", m._kernel_exempt)
        finally:
            shutil.rmtree(tmp)

    def test_kernel_exempt_without_reason_invalid(self):
        """@kernel_exempt 缺 reason → 豁免无效，仍触发"""
        tmp = _make_project({
            "src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n",
            "src/hot.cpp": "/* @kernel_exempt */\nf->data_[0] = 1.0;\n",
        })
        try:
            m = GeometryConsistencyMetrics(tmp)
            _, d4d = m.calc_data_access_norm()
            self.assertGreater(d4d["access_encapsulation"]["direct_access_count"], 0)
            self.assertEqual(m._kernel_exempt, {})
            self.assertEqual(m._invalid_waivers[0]["annotation"], "@kernel_exempt")
        finally:
            shutil.rmtree(tmp)

    def test_kernel_exempt_file_scoped_only(self):
        """@kernel_exempt 仅作用于本文件，同目录另一文件仍触发"""
        tmp = _make_project({
            "src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n",
            "src/a.cpp": "/* @kernel_exempt: 适配层 */\nf->data_[0] = 1.0;\n",
            "src/b.cpp": "f->data_[1] = 2.0;\n",
        })
        try:
            m = GeometryConsistencyMetrics(tmp)
            _, d4d = m.calc_data_access_norm()
            self.assertGreater(d4d["access_encapsulation"]["direct_access_count"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_gcs_waiver_lowers_density(self):
        """@gcs_waiver：受控裸数组文件从 GCS-010 分子分母同时剔除"""
        body = "vtkSmartPointer<vtkPoints> pts;\ndouble *buf = new double[3];\n"
        files = {"src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n"}
        # 3 个裸数组文件 + 1 个干净的科学数据文件 → 密度 0.75 超阈值
        for i in range(3):
            files[f"src/bare{i}.cpp"] = body
        files["src/clean.cpp"] = "vtkSmartPointer<vtkPoints> pts;\n"
        tmp = _make_project(files)
        try:
            m = GeometryConsistencyMetrics(tmp)
            _, d4d = m.calc_data_access_norm()
            self.assertGreater(d4d["bare_array"]["density"], 0.5)
            self.assertEqual(d4d["bare_array"]["score"], 0)

            # 豁免其中 2 个 → bare2 + clean 计入，密度 1/2 = 0.5 ≤ 阈值 → 得分恢复 35
            m2_files = dict(files)
            m2_files["src/bare0.cpp"] = body + "// @gcs_waiver: 求解器热路径，已测性能\n"
            m2_files["src/bare1.cpp"] = body + "// @gcs_waiver: 求解器热路径，已测性能\n"
            tmp2 = _make_project(m2_files)
            try:
                m2 = GeometryConsistencyMetrics(tmp2)
                _, d2d = m2.calc_data_access_norm()
                self.assertEqual(d2d["bare_array"]["waived_files"], 2)
                self.assertEqual(d2d["bare_array"]["density"], 0.5)
                self.assertEqual(d2d["bare_array"]["score"], 35)
            finally:
                shutil.rmtree(tmp2)
        finally:
            shutil.rmtree(tmp)

    def test_gcs_waiver_without_reason_invalid(self):
        """@gcs_waiver 缺 reason → 不生效，密度不变"""
        body = "vtkSmartPointer<vtkPoints> pts;\ndouble *buf = new double[3];\n"
        files = {"src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n"}
        for i in range(3):
            files[f"src/bare{i}.cpp"] = body
        files["src/clean.cpp"] = "vtkSmartPointer<vtkPoints> pts;\n"
        files["src/bare0.cpp"] = body + "// @gcs_waiver\n"
        tmp = _make_project(files)
        try:
            m = GeometryConsistencyMetrics(tmp)
            _, d4d = m.calc_data_access_norm()
            self.assertEqual(d4d["bare_array"]["waived_files"], 0)
            self.assertEqual(m._gcs_waiver, {})
            self.assertGreater(d4d["bare_array"]["density"], 0.5)
        finally:
            shutil.rmtree(tmp)

    def test_waiver_audit_output(self):
        """豁免审计输出结构 + 反滥用守卫（占比低于阈值时不告警）"""
        files = {
            "src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n",
            "src/a.cpp": "/* @kernel_exempt: 适配层 */\nf->data_[0] = 1.0;\n",
            "src/b.cpp": "vtkSmartPointer<vtkPoints> p;\ndouble *x = new double[2];"
                         "// @gcs_waiver: 热路径\n",
        }
        for i in range(4):
            files[f"src/filler{i}.cpp"] = "vtkSmartPointer<vtkPoints> p;\n"
        tmp = _make_project(files)
        try:
            m = GeometryConsistencyMetrics(tmp)
            r = m.all_metrics()
            wa = r["waiver_audit"]
            self.assertEqual(wa["kernel_exempt"]["count"], 1)
            self.assertEqual(wa["gcs_waiver"]["count"], 1)
            self.assertIn("全部 12 条规则", wa["kernel_exempt"]["scope"])
            self.assertIn("GCS-010", wa["gcs_waiver"]["scope"])
            self.assertIsNone(wa["abuse_warning"])
        finally:
            shutil.rmtree(tmp)

    def test_waiver_abuse_warning(self):
        """@kernel_exempt 占比超阈值 → 反滥用告警"""
        files = {"src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n"}
        for i in range(4):
            files[f"src/x{i}.cpp"] = ("/* @kernel_exempt: 批量标注 */\n"
                                      "f->data_[0] = 1.0;\n")
        tmp = _make_project(files)
        try:
            m = GeometryConsistencyMetrics(tmp)
            wa = m.all_metrics()["waiver_audit"]
            self.assertGreater(wa["kernel_exempt"]["ratio"], 0.30)
            self.assertIsNotNone(wa["abuse_warning"])
        finally:
            shutil.rmtree(tmp)

    def test_waiver_in_comment_stripped_content_not_matched(self):
        """豁免注解须在剥离注释前采集（防止注解被 _strip_comments 吞掉）"""
        tmp = _make_project({
            "src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n",
            "src/a.cpp": ("/* @kernel_exempt: 适配层 */\n"
                          "f->data_[0] = 1.0;\n"
                          "// @gcs_waiver: 热路径\n"),
        })
        try:
            m = GeometryConsistencyMetrics(tmp)
            self.assertEqual(len(m._kernel_exempt), 1)
            self.assertEqual(len(m._gcs_waiver), 1)
            _, d4d = m.calc_data_access_norm()
            self.assertEqual(d4d["access_encapsulation"]["direct_access_count"], 0)
        finally:
            shutil.rmtree(tmp)


class TestWaiverAbuseGuards(unittest.TestCase):
    """专家校对第二轮 P0-1/P0-2/P1-1 修复的回归测试"""

    def test_empty_reason_forms_rejected(self):
        """P0-2：空 reason 形式必须被拒（否则 reason 必填规则可被绕过）"""
        base = {"src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n"}
        cases = {
            "/* @kernel_exempt: */\nf->data_[0] = 1.0;\n": "kernel_exempt",
            "/* @kernel_exempt */\nf->data_[0] = 1.0;\n": "kernel_exempt",
            "vtkSmartPointer<vtkPoints> p;\ndouble *b = new double[3];\n"
            "// @gcs_waiver:\n": "gcs_waiver",
            "vtkSmartPointer<vtkPoints> p;\ndouble *b = new double[3];\n"
            "// @gcs_waiver\n": "gcs_waiver",
        }
        for content, kind in cases.items():
            tmp = _make_project(dict(base, **{"src/a.cpp": content}))
            try:
                m = GeometryConsistencyMetrics(tmp)
                self.assertEqual(m._kernel_exempt, {}, f"{kind} 空 reason 不应生效")
                self.assertEqual(m._gcs_waiver, {}, f"{kind} 空 reason 不应生效")
                self.assertEqual(len(m._invalid_waivers), 1)
                self.assertEqual(m._invalid_waivers[0]["annotation"], f"@{kind}")
            finally:
                shutil.rmtree(tmp)

    def test_gcs_waiver_ratio_guard(self):
        """P0-1：@gcs_waiver 占比超阈值须告警（否则可全量豁免刷满 GCS-010）"""
        body = "vtkSmartPointer<vtkPoints> p;\ndouble *b = new double[3];\n"
        files = {"src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n"}
        for i in range(4):
            files[f"src/x{i}.cpp"] = body + "// @gcs_waiver: 热路径\n"
        tmp = _make_project(files)
        try:
            m = GeometryConsistencyMetrics(tmp)
            wa = m.all_metrics()["waiver_audit"]
            self.assertGreater(wa["gcs_waiver"]["ratio"], 0.30)
            self.assertIn("@gcs_waiver", wa["abuse_warning"])
        finally:
            shutil.rmtree(tmp)

    def test_density_undefined_when_denominator_waived_away(self):
        """P0-1：分母被豁免清空时密度不可解读，须显式标记"""
        body = "vtkSmartPointer<vtkPoints> p;\ndouble *b = new double[3];\n"
        files = {"src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n"}
        for i in range(3):
            files[f"src/x{i}.cpp"] = body + "// @gcs_waiver: 热路径\n"
        tmp = _make_project(files)
        try:
            m = GeometryConsistencyMetrics(tmp)
            _, d4d = m.calc_data_access_norm()
            self.assertTrue(d4d["bare_array"]["density_undefined"])
            self.assertIsNotNone(d4d["bare_array"]["caveat"])
            self.assertEqual(d4d["bare_array"]["scidata_files"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_kernel_dir_over_exclusion_guard(self):
        """P1-1：内核目录排除占比过高须告警（通用目录名 geom/brep 误伤风险）"""
        files = {"src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n"}
        for i in range(4):
            files[f"src/geom/app{i}.cpp"] = "f->data_[0] = 1.0;\n"
        tmp = _make_project(files)
        try:
            m = GeometryConsistencyMetrics(tmp)
            wa = m.all_metrics()["waiver_audit"]
            kd = wa["kernel_dir_exclusion"]
            self.assertEqual(kd["count"], 4)
            self.assertGreater(kd["ratio"], 0.30)
            self.assertIn("内核目录排除占比", wa["abuse_warning"])
            self.assertIn("geom", kd["weak_names"])
            self.assertIn("tkbool", kd["strong_names"])
        finally:
            shutil.rmtree(tmp)

    def test_valid_reason_still_effective(self):
        """修复后合法注解不得被误伤（防过度收紧）"""
        tmp = _make_project({
            "src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n",
            "src/a.cpp": "/* @kernel_exempt: 遗留适配层，2026-Q4 重构 */\nf->data_[0] = 1.0;\n",
            "src/b.cpp": "vtkSmartPointer<vtkPoints> p;\ndouble *x = new double[2];"
                         "// @gcs_waiver: 求解器热路径，已测性能\n",
        })
        try:
            m = GeometryConsistencyMetrics(tmp)
            self.assertEqual(list(m._kernel_exempt), ["src/a.cpp"])
            self.assertEqual(list(m._gcs_waiver), ["src/b.cpp"])
            self.assertEqual(m._invalid_waivers, [])
            _, d4d = m.calc_data_access_norm()
            self.assertEqual(d4d["access_encapsulation"]["direct_access_count"], 0)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()

