"""
test_anti_corruption.py — 外部科学内核与几何内核的封装与防腐层评估单元测试

覆盖（对齐《验证案例集》4.1-4.12 合成案例）：
1. 非 ACL 项目 → is_acl=False，各维度 None
2. 启用检测 — 内核/数据交换信号
3. 4 维评分 — 每维正例/负例
4. ACL 规则触发 — 每条规则 ≥1 测试
5. 递进扣分 — 任一基础层 < 60 → 2.4 折半
6. all_metrics 结构完整性 + 豁免
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arch_quality.arch_metrics_anti_corruption import AntiCorruptionMetrics


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


class TestNonAclProject(unittest.TestCase):
    """非 ACL 项目：各维度 None"""

    def test_plain_python_not_acl(self):
        tmp = _make_project({"src/main.py": "def main():\n    print('hello')\n"})
        try:
            m = AntiCorruptionMetrics(tmp)
            r = m.all_metrics()
            self.assertFalse(r["is_acl"])
            self.assertIsNone(r["overall"])
            for dim in r["dimensions"].values():
                self.assertIsNone(dim["score"])
            self.assertEqual(r["acl_violations"], [])
        finally:
            shutil.rmtree(tmp)


class TestAclDetection(unittest.TestCase):
    """启用检测"""

    def test_occt_kernel_signal_detected(self):
        tmp = _make_project({"src/brep.cpp": "#include <BRep_Tool.hxx>\nTopoDS_Shape s;\n"})
        try:
            m = AntiCorruptionMetrics(tmp)
            self.assertTrue(m.all_metrics()["is_acl"])
        finally:
            shutil.rmtree(tmp)

    def test_step_signal_detected(self):
        tmp = _make_project({"src/io.cpp": "#include <STEPControl_Writer.hxx>\n"})
        try:
            m = AntiCorruptionMetrics(tmp)
            self.assertTrue(m.all_metrics()["is_acl"])
        finally:
            shutil.rmtree(tmp)


class TestExternalAccess(unittest.TestCase):
    """维度 1：外部内核访问防腐"""

    def test_good_wrapper_no_direct(self):
        tmp = _make_project({
            "wrapper/cad_ops.h": "class CadEngine {\npublic:\n    MatShape do_fuse(const MatShape& a);\n};\n",
            "wrapper/cad_ops.cpp": (
                "#include <BRepAlgoAPI_Fuse.hxx>\n"
                "MatShape CadEngine::do_fuse(const MatShape& a){\n"
                "    BRepAlgoAPI_Fuse op(a.inner());\n"
                "    if(!op.IsDone()) throw std::runtime_error(\"fail\");\n"
                "    return MatShape::wrap(op.Shape());\n"
                "}\n"),
        })
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_external_access()
            self.assertEqual(detail["direct_access"]["direct_count"], 0)
            self.assertGreaterEqual(score, 90)
        finally:
            shutil.rmtree(tmp)

    def test_direct_access_triggers_acl001(self):
        tmp = _make_project({"src/business.cpp": (
            "#include <BRepAlgoAPI_Fuse.hxx>\n"
            "TopoDS_Shape merge(TopoDS_Shape a, TopoDS_Shape b){\n"
            "    BRepAlgoAPI_Fuse op(a, b);\n"
            "    return op.Shape();\n"
            "}\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_external_access()
            self.assertGreater(detail["direct_access"]["direct_count"], 0)
            rules = m.check_acl_rules()
            self.assertTrue(any(r["rule"] == "ACL-001" and r["output_level"] == "ERROR"
                                for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_type_leak_triggers_acl004(self):
        tmp = _make_project({
            "wrapper/cad_ops.h": (
                "#include <TopoDS_Shape.hxx>\n"
                "class CadEngine {\n"
                "public:\n"
                "    TopoDS_Shape do_fuse(const TopoDS_Shape& a);\n"
                "};\n"),
            "wrapper/cad_ops.cpp": "TopoDS_Shape CadEngine::do_fuse(const TopoDS_Shape& a){return a;}\n",
        })
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_external_access()
            self.assertGreater(detail["type_leak"]["leak_count"], 0)
            rules = m.check_acl_rules()
            self.assertTrue(any(r["rule"] == "ACL-004" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_no_error_check_triggers_acl005(self):
        tmp = _make_project({"src/bad.cpp": (
            "#include <BRepAlgoAPI_Fuse.hxx>\n"
            "TopoDS_Shape fuse(const TopoDS_Shape& a, const TopoDS_Shape& b){\n"
            "    BRepAlgoAPI_Fuse op(a, b);\n"
            "    return op.Shape();\n"
            "}\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_external_access()
            self.assertGreater(detail["error_handling"]["missing_check_count"], 0)
            rules = m.check_acl_rules()
            self.assertTrue(any(r["rule"] == "ACL-005" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_format_call_excluded_from_acl005(self):
        """专家校对 P1-2：格式读写调用点归 ACL-011，ACL-005 不重复"""
        tmp = _make_project({"importexport/step_io.cpp": (
            "#include <STEPControl_Writer.hxx>\n"
            "void export_step(){ STEPControl_Writer w; w.Write(\"x.stp\"); }\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_external_access()
            self.assertEqual(detail["error_handling"]["missing_check_count"], 0)
        finally:
            shutil.rmtree(tmp)


class TestWrapperCoverage(unittest.TestCase):
    """维度 2：Wrapper 覆盖度与演进守卫"""

    def test_no_wrapper_triggers_acl002(self):
        tmp = _make_project({"src/no_wrapper.cpp": (
            "#include <BRepAlgoAPI_Fuse.hxx>\nTopoDS_Shape f(){return TopoDS_Shape();}\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_wrapper_coverage()
            rules = m.check_acl_rules()
            self.assertTrue(rules and any(r["rule"] == "ACL-002" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_version_guard_present_scores(self):
        tmp = _make_project({"wrapper/a.cpp": "#if OCC_VERSION >= 70800\nint x;\n#endif\n"})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_wrapper_coverage()
            self.assertGreater(detail["version_guard"]["guard_count"], 0)
            rules = m.check_acl_rules()
            self.assertFalse(any(r["rule"] == "ACL-003" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_no_version_guard_triggers_acl003(self):
        tmp = _make_project({"wrapper/a.cpp": (
            "#include <BRep_Tool.hxx>\n"
            "int x;\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            rules = m.check_acl_rules()
            self.assertTrue(any(r["rule"] == "ACL-003" for r in rules))
        finally:
            shutil.rmtree(tmp)


class TestDataExchange(unittest.TestCase):
    """维度 3：数据交换防腐"""

    def test_scattered_step_triggers_acl007(self):
        tmp = _make_project({"src/business.cpp": (
            "#include <STEPControl_Writer.hxx>\n"
            "void export_part(){ STEPControl_Writer w; w.Write(\"part.stp\"); }\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_data_exchange()
            self.assertGreater(detail["exchange_anti_corruption"]["scatter_count"], 0)
            rules = m.check_acl_rules()
            self.assertTrue(any(r["rule"] == "ACL-007" and r["output_level"] == "ERROR"
                                for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_concentrated_io_no_acl007(self):
        tmp = _make_project({"importexport/step_io.cpp": (
            "#include <STEPControl_Writer.hxx>\n"
            "void export_step(){ STEPControl_Writer w; w.Write(\"x.stp\"); }\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_data_exchange()
            self.assertEqual(detail["exchange_anti_corruption"]["scatter_count"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_no_ret_check_triggers_acl011(self):
        tmp = _make_project({"importexport/step_io.cpp": (
            "#include <STEPControl_Reader.hxx>\n"
            "void import_step(const char* path){\n"
            "    STEPControl_Reader r;\n"
            "    r.ReadFile(path);\n"
            "    r.TransferRoots();\n"
            "    use(r.OneShape());\n"
            "}\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_data_exchange()
            self.assertGreater(detail["exch_error_handling"]["bad_read_count"], 0)
            rules = m.check_acl_rules()
            self.assertTrue(any(r["rule"] == "ACL-011" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_ret_check_ok(self):
        tmp = _make_project({"importexport/step_io.cpp": (
            "#include <STEPControl_Reader.hxx>\n"
            "#include <IFSelect_ReturnStatus.hxx>\n"
            "void import_step(const char* path){\n"
            "    STEPControl_Reader r;\n"
            "    if(r.ReadFile(path) != IFSelect_RetDone) throw std::runtime_error(\"rf\");\n"
            "    r.TransferRoots();\n"
            "}\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_data_exchange()
            self.assertEqual(detail["exch_error_handling"]["bad_read_count"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_format_density_triggers_acl012(self):
        tmp = _make_project({"src/view.cpp": (
            "#include <IGESControl_Reader.hxx>\n"
            "class GeoView { IGESControl_Reader r_;\n"
            "  TopoDS_Shape load(){ return r_.OneShape(); } };\n"),
            "src/other.cpp": (
            "#include <IGESControl_Reader.hxx>\n"
            "IGESControl_Reader make(){ return IGESControl_Reader(); }\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_data_exchange()
            self.assertGreater(detail["format_direct"]["density"], 0)
            rules = m.check_acl_rules()
            self.assertTrue(any(r["rule"] == "ACL-012" for r in rules))
        finally:
            shutil.rmtree(tmp)


class TestFidelity(unittest.TestCase):
    """维度 4：保真度与外部标准一致性"""

    def test_round_trip_present_bonus(self):
        tmp = _make_project({"importexport/test_stability.cpp": (
            "TEST(Step, RoundTrip){\n"
            "    STEPControl_Writer w; w.Write(\"t.stp\");\n"
            "    STEPControl_Reader r; r.ReadFile(\"t.stp\"); r.TransferRoots();\n"
            "    ASSERT_EQ(r.OneShape(), shape_);\n"
            "}\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_fidelity()
            self.assertTrue(detail["round_trip"]["has"])
            self.assertGreaterEqual(detail["round_trip"]["score"], 40)
        finally:
            shutil.rmtree(tmp)

    def test_missing_round_trip_info(self):
        tmp = _make_project({"importexport/step_io.cpp": (
            "#include <STEPControl_Writer.hxx>\nvoid export_step(){ STEPControl_Writer w; w.Write(\"x\"); }\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            rules = m.check_acl_rules()
            self.assertTrue(any(r["rule"] == "ACL-006" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_unit_magic_factor_triggers_acl008(self):
        tmp = _make_project({"importexport/io.cpp": (
            "#include <STEPControl_Writer.hxx>\n"
            "double export_len(const double v){ return v * 25.4; }\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_fidelity()
            self.assertGreater(detail["unit_factor"]["factor_count"], 0)
            rules = m.check_acl_rules()
            self.assertTrue(any(r["rule"] == "ACL-008" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_unit_func_exempts_acl008(self):
        tmp = _make_project({"importexport/io.cpp": (
            "double export_len(const double v){ return unit::convert(v, unit::INCH, unit::MM); }\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            rules = m.check_acl_rules()
            self.assertFalse(any(r["rule"] == "ACL-008" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_tol_magic_factor_triggers_acl009(self):
        tmp = _make_project({"importexport/io.cpp": (
            "#include <STEPControl_Writer.hxx>\n"
            "double export_tol(double t){ return t * 0.0254; }\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            rules = m.check_acl_rules()
            self.assertTrue(any(r["rule"] == "ACL-009" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_ap_version_guard(self):
        tmp = _make_project({"importexport/io.cpp": (
            "#include <STEPControl_Writer.hxx>\n"
            "#if SUPPORT_AP242\n"
            "int x;\n"
            "#endif\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            score, detail = m.calc_fidelity()
            self.assertTrue(detail["std_version_guard"]["has_version_guard"])
            rules = m.check_acl_rules()
            self.assertFalse(any(r["rule"] == "ACL-010" for r in rules))
        finally:
            shutil.rmtree(tmp)

    def test_missing_ap_version_triggers_acl010(self):
        tmp = _make_project({"importexport/io.cpp": (
            "#include <STEPControl_Writer.hxx>\nvoid export_step(){}\n")})
        try:
            m = AntiCorruptionMetrics(tmp)
            rules = m.check_acl_rules()
            self.assertTrue(any(r["rule"] == "ACL-010" for r in rules))
        finally:
            shutil.rmtree(tmp)


class TestProgressiveDeduction(unittest.TestCase):
    """递进扣分：任一基础层 < 60 → 2.4 折半"""

    def test_base_failure_halves_fidelity(self):
        # 基础层 2.1 全失败（直连 + 无错误检查），2.3 失败（散落）
        tmp = _make_project({
            "src/mix.cpp": (
                "#include <BRepAlgoAPI_Fuse.hxx>\n"
                "TopoDS_Shape m(TopoDS_Shape a, TopoDS_Shape b){\n"
                "    BRepAlgoAPI_Fuse op(a, b);\n"
                "    return op.Shape();\n"
                "}\n"
                "#include <STEPControl_Writer.hxx>\n"
                "void ex(){ STEPControl_Writer w; w.Write(\"x\"); }\n"),
        })
        try:
            m = AntiCorruptionMetrics(tmp)
            d1, _ = m.calc_external_access()
            d3, _ = m.calc_data_exchange()
            base_bad = (d1 < 60) or (d3 < 60)
            self.assertTrue(base_bad)
            score, detail = m.calc_fidelity()
            self.assertTrue(detail["progressive_deduction"]["applied"])
        finally:
            shutil.rmtree(tmp)


class TestWaivers(unittest.TestCase):
    """豁免注解体系"""

    def test_acl_exempt_removes_file(self):
        tmp = _make_project({
            "src/leak.cpp": (
                "/* @acl_exempt: vendored kernel source */\n"
                "#include <BRepAlgoAPI_Fuse.hxx>\n"
                "TopoDS_Shape m(TopoDS_Shape a){ BRepAlgoAPI_Fuse op(a); return op.Shape(); }\n"),
            "src/ok.cpp": "int main(){return 0;}\n",
            "src/use.cpp": "TopoDS_Shape s;\n",
            "src/use2.cpp": "BRep_Tool t;\n",
        })
        try:
            m = AntiCorruptionMetrics(tmp)
            r = m.all_metrics()
            wa = r["waiver_audit"]
            self.assertEqual(wa["acl_exempt"]["count"], 1)
            self.assertIsNone(wa.get("abuse_warning"))
        finally:
            shutil.rmtree(tmp)

    def test_invalid_waiver_recorded(self):
        tmp = _make_project({
            "src/a.cpp": "/* @acl_exempt */\n#include <BRep_Tool.hxx>\nint x;\n",
        })
        try:
            m = AntiCorruptionMetrics(tmp)
            wa = m.all_metrics()["waiver_audit"]
            self.assertEqual(wa["invalid_count"], 1)
            self.assertEqual(wa["invalid_waivers"][0]["annotation"], "@acl_exempt")
        finally:
            shutil.rmtree(tmp)

    def test_abuse_warning_over_30pct(self):
        files = {}
        for i in range(5):
            files[f"src/f{i}.cpp"] = '/* @acl_exempt: reason %d */\n#include <BRep_Tool.hxx>\nint x;\n' % i
        files["src/ok.cpp"] = "int main(){return 0;}\n"
        files["src/use.cpp"] = "TopoDS_Shape s;\n"
        tmp = _make_project(files)
        try:
            m = AntiCorruptionMetrics(tmp)
            wa = m.all_metrics()["waiver_audit"]
            self.assertIsNotNone(wa.get("abuse_warning"))
        finally:
            shutil.rmtree(tmp)


class TestAllMetrics(unittest.TestCase):
    """all_metrics 结构完整性"""

    def test_structure(self):
        tmp = _make_project({"src/io.cpp": "#include <STEPControl_Writer.hxx>\nvoid e(){}\n"})
        try:
            m = AntiCorruptionMetrics(tmp)
            r = m.all_metrics()
            self.assertTrue(r["is_acl"])
            self.assertIn("overall", r)
            self.assertEqual(len(r["dimensions"]), 4)
            self.assertIn("acl_violations", r)
            self.assertIn("waiver_audit", r)
            vi = r["version_info"]
            self.assertEqual(vi["guide_version"], "1.3")
            self.assertEqual(vi["skill_version"], "1.0")
            # overall 必在 0-100
            self.assertGreaterEqual(r["overall"], 0)
            self.assertLessEqual(r["overall"], 100)
        finally:
            shutil.rmtree(tmp)

    def test_json_serializable(self):
        tmp = _make_project({"src/io.cpp": "#include <BRep_Tool.hxx>\nvoid e(){}\n"})
        try:
            m = AntiCorruptionMetrics(tmp)
            r = m.all_metrics()
            json.dumps(r, ensure_ascii=False)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()