"""
test_tcl_deps.py — Tcl 依赖解析和 DepGraph 集成测试

测试场景:
1. source 命令解析
2. package require 命令解析
3. namespace eval 和 ::ns::proc 跨文件依赖
4. Tcl→C++ 跨语言边
5. _collect_std_imports 包含 Tcl 边
6. calc_impact_radius 包含 Tcl 节点
7. MLR-004b Tcl 命名空间违规检测
8. 空项目/纯 Tcl 项目回退
"""

import unittest
import os
import tempfile
import shutil

from arch_quality.arch_core import FileIndex, DepGraph
from arch_quality.arch_metrics_multilang import MultilangMetrics, _collect_std_imports


class TestTclSourceParsing(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_source_literal_path(self):
        tcl_a = os.path.join(self.tmpdir, "main.tcl")
        tcl_b = os.path.join(self.tmpdir, "utils.tcl")
        with open(tcl_a, "w") as f:
            f.write('source "utils.tcl"\nputs "hello"\n')
        with open(tcl_b, "w") as f:
            f.write('proc utils_help {} { puts "help" }\n')
        m = MultilangMetrics(self.tmpdir)
        edges = [(s, d) for s, d in m.graph.edges
                 if "main.tcl" in s or "main.tcl" in d]
        self.assertTrue(len(edges) > 0, f"Expected edge from main.tcl, got edges: {m.graph.edges}")

    def test_source_variable_path_not_matched(self):
        tcl_a = os.path.join(self.tmpdir, "main.tcl")
        tcl_b = os.path.join(self.tmpdir, "utils.tcl")
        with open(tcl_a, "w") as f:
            f.write('source $script_dir/utils.tcl\nputs "hello"\n')
        with open(tcl_b, "w") as f:
            f.write('proc utils_help {} { puts "help" }\n')
        m = MultilangMetrics(self.tmpdir)
        source_edges = [(s, d) for s, d in m.graph.edges
                        if s.endswith("main.tcl") and d.endswith("utils.tcl")]
        self.assertEqual(len(source_edges), 0,
                         "Variable source paths should not resolve to file edges")

    def test_source_no_self_loop(self):
        tcl_a = os.path.join(self.tmpdir, "selfref.tcl")
        with open(tcl_a, "w") as f:
            f.write('source "selfref.tcl"\n')
        m = MultilangMetrics(self.tmpdir)
        for s, d in m.graph.edges:
            if s.endswith("selfref.tcl") and d.endswith("selfref.tcl"):
                self.fail("Self-loop detected for tcl file")


class TestTclPackageRequire(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_package_require_simple(self):
        tcl_a = os.path.join(self.tmpdir, "app.tcl")
        tcl_b = os.path.join(self.tmpdir, "cadwidgets.tcl")
        with open(tcl_a, "w") as f:
            f.write('package require cadwidgets\n')
        with open(tcl_b, "w") as f:
            f.write('package provide cadwidgets 1.0\n')
        m = MultilangMetrics(self.tmpdir)
        edges = [(s, d) for s, d in m.graph.edges
                 if s.endswith("app.tcl") and d.endswith("cadwidgets.tcl")]
        self.assertTrue(len(edges) > 0, f"Expected app→cadwidgets edge, got: {m.graph.edges}")

    def test_package_require_namespaced(self):
        tcl_a = os.path.join(self.tmpdir, "gui.tcl")
        tcl_b = os.path.join(self.tmpdir, "GeometryIO.tcl")
        with open(tcl_a, "w") as f:
            f.write('package require cadwidgets::GeometryIO\n')
        with open(tcl_b, "w") as f:
            f.write('package provide cadwidgets::GeometryIO 1.0\n')
        m = MultilangMetrics(self.tmpdir)
        edges = [(s, d) for s, d in m.graph.edges
                 if s.endswith("gui.tcl") and d.endswith("GeometryIO.tcl")]
        self.assertTrue(len(edges) > 0, f"Expected gui→GeometryIO edge, got: {m.graph.edges}")

    def test_package_require_no_self_loop(self):
        tcl_a = os.path.join(self.tmpdir, "selfpkg.tcl")
        with open(tcl_a, "w") as f:
            f.write('package require selfpkg\n')
        m = MultilangMetrics(self.tmpdir)
        for s, d in m.graph.edges:
            if s.endswith("selfpkg.tcl") and d.endswith("selfpkg.tcl"):
                self.fail("Self-loop detected for package require")


class TestTclNamespaceDeps(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_namespace_eval_creates_edge(self):
        tcl_a = os.path.join(self.tmpdir, "caller.tcl")
        tcl_b = os.path.join(self.tmpdir, "isst.tcl")
        with open(tcl_a, "w") as f:
            f.write('namespace eval ::isst {\n    source "isst.tcl"\n}\n')
        with open(tcl_b, "w") as f:
            f.write('proc ::isst::setup {} { }\n')
        m = MultilangMetrics(self.tmpdir)
        edges = [(s, d) for s, d in m.graph.edges
                 if s.endswith("caller.tcl") and d.endswith("isst.tcl")]
        self.assertTrue(len(edges) > 0, f"Expected caller→isst edge, got: {m.graph.edges}")

    def test_double_colon_proc_call(self):
        tcl_a = os.path.join(self.tmpdir, "caller.tcl")
        tcl_b = os.path.join(self.tmpdir, "isst.tcl")
        with open(tcl_a, "w") as f:
            f.write('::isst::setup\n::isst::geomlist $filename\n')
        with open(tcl_b, "w") as f:
            f.write('proc ::isst::setup {} { }\nproc ::isst::geomlist {filename} { }\n')
        m = MultilangMetrics(self.tmpdir)
        edges = [(s, d) for s, d in m.graph.edges
                 if s.endswith("caller.tcl") and d.endswith("isst.tcl")]
        self.assertTrue(len(edges) > 0, f"Expected caller→isst edge, got: {m.graph.edges}")


class TestTclCrossLangEdge(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_tcl_to_cpp_edge(self):
        tcl = os.path.join(self.tmpdir, "app.tcl")
        cpp = os.path.join(self.tmpdir, "Bu.cpp")
        with open(tcl, "w") as f:
            f.write('package require Bu\n')
        with open(cpp, "w") as f:
            f.write('// Bu C library\n')
        m = MultilangMetrics(self.tmpdir)
        cross = [(s, d) for s, d in m.graph.cross_edges
                 if s.endswith("app.tcl") and d.endswith("Bu.cpp")]
        self.assertTrue(len(cross) > 0,
                        f"Expected cross-lang Tcl→C++ edge, got cross_edges: {m.graph.cross_edges}")


class TestCollectStdImportsTcl(unittest.TestCase):

    def test_tcl_source_in_std_imports(self):
        tmpdir = tempfile.mkdtemp()
        tcl_a = os.path.join(tmpdir, "main.tcl")
        tcl_b = os.path.join(tmpdir, "utils.tcl")
        with open(tcl_a, "w") as f:
            f.write('source "utils.tcl"\n')
        with open(tcl_b, "w") as f:
            f.write('proc utils_help {} { }\n')
        try:
            idx = FileIndex(tmpdir)
            edges = _collect_std_imports(idx)
            tcl_edges = [(s, d) for s, d in edges
                         if s.endswith("main.tcl") and d.endswith("utils.tcl")]
            self.assertTrue(len(tcl_edges) > 0, f"Expected Tcl source edge in std imports, got: {edges}")
        finally:
            shutil.rmtree(tmpdir)

    def test_tcl_package_require_in_std_imports(self):
        tmpdir = tempfile.mkdtemp()
        tcl_a = os.path.join(tmpdir, "app.tcl")
        tcl_b = os.path.join(tmpdir, "cadwidgets.tcl")
        with open(tcl_a, "w") as f:
            f.write('package require cadwidgets\n')
        with open(tcl_b, "w") as f:
            f.write('package provide cadwidgets 1.0\n')
        try:
            idx = FileIndex(tmpdir)
            edges = _collect_std_imports(idx)
            tcl_edges = [(s, d) for s, d in edges
                         if s.endswith("app.tcl") and d.endswith("cadwidgets.tcl")]
            self.assertTrue(len(tcl_edges) > 0, f"Expected Tcl package edge in std imports, got: {edges}")
        finally:
            shutil.rmtree(tmpdir)


class TestTclImpactRadius(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_tcl_impact_radius_single_lang(self):
        for i in range(3):
            tcl = os.path.join(self.tmpdir, f"mod{i}.tcl")
            with open(tcl, "w") as f:
                if i > 0:
                    f.write(f'source "mod0.tcl"\n')
                f.write(f'proc mod{i}_run {{}} {{ }}\n')
        m = MultilangMetrics(self.tmpdir)
        score, radii = m.calc_impact_radius()
        tcl_radii = {k: v for k, v in radii.items() if k.endswith(".tcl")}
        mod0_radius = [v["radius"] for k, v in tcl_radii.items() if "mod0" in k]
        self.assertTrue(len(mod0_radius) > 0, f"No radius for mod0.tcl, radii: {tcl_radii}")
        self.assertGreater(mod0_radius[0], 0,
                           f"mod0.tcl should have reachable neighbors, got radius {mod0_radius[0]}")

    def test_tcl_impact_radius_multilang(self):
        tcl = os.path.join(self.tmpdir, "gui.tcl")
        cpp = os.path.join(self.tmpdir, "engine.cpp")
        py = os.path.join(self.tmpdir, "bridge.py")
        with open(tcl, "w") as f:
            f.write('package require Engine\n')
        with open(cpp, "w") as f:
            f.write('#include "engine.h"\n')
        with open(py, "w") as f:
            f.write('import engine\n')
        m = MultilangMetrics(self.tmpdir)
        cross_count = len(m.graph.cross_edges)
        self.assertGreater(cross_count, 0,
                           f"Expected cross-lang edges with Tcl→C++, got: {m.graph.cross_edges}")


class TestTclMLR004(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_tcl_namespace_violation_detected(self):
        tcl = os.path.join(self.tmpdir, "test.tcl")
        with open(tcl, "w") as f:
            f.write('::engine::internal_var set 42\n::myapp::data_handler process\n')
        m = MultilangMetrics(self.tmpdir)
        results = m.check_mlr_rules()
        mlr004 = [r for r in results if r["rule"] == "MLR-004"]
        tcl_violations = [r for r in mlr004 if "Tcl" in r.get("name", "")]
        self.assertTrue(len(tcl_violations) > 0,
                        f"Expected MLR-004 Tcl violation, got: {mlr004}")

    def test_tcl_allowed_namespace_not_flagged(self):
        tcl = os.path.join(self.tmpdir, "test.tcl")
        with open(tcl, "w") as f:
            f.write('::string::length $var\n::tk::button .b\n')
        m = MultilangMetrics(self.tmpdir)
        results = m.check_mlr_rules()
        mlr004 = [r for r in results if r["rule"] == "MLR-004"]
        tcl_violations = [r for r in mlr004 if "Tcl" in r.get("name", "")]
        self.assertEqual(len(tcl_violations), 0,
                         f"Standard Tcl namespaces should not be flagged, got: {tcl_violations}")


class TestTclEmptyProject(unittest.TestCase):

    def test_empty_tcl_project(self):
        tmpdir = tempfile.mkdtemp()
        try:
            m = MultilangMetrics(tmpdir)
            score, radii = m.calc_impact_radius()
            self.assertEqual(score, 100.0)
            self.assertEqual(len(radii), 0)
        finally:
            shutil.rmtree(tmpdir)

    def test_single_tcl_file(self):
        tmpdir = tempfile.mkdtemp()
        tcl = os.path.join(tmpdir, "standalone.tcl")
        with open(tcl, "w") as f:
            f.write('puts "hello"\n')
        try:
            m = MultilangMetrics(tmpdir)
            score, radii = m.calc_impact_radius()
            self.assertEqual(score, 100.0)
        finally:
            shutil.rmtree(tmpdir)


if __name__ == "__main__":
    unittest.main()