"""
test_build_dir.py — build_dir 参数功能单元测试

测试场景:
1. FileIndex 在指定 build_dir 时能扫描 _wrap.cxx/.i/.pyi 文件
2. FileIndex 不指定 build_dir 时行为不变
3. MultilangMetrics 接受 build_dir 参数
4. _wrap.cxx 文件中的 .def() 和 PyInit_ 正确提取
5. build_dir 中的 .i 文件绑定正确纳入统计
6. MLR-002/003 对 build_dir 绑定的检测
7. ComprehensiveReport 接受 build_dir 参数
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from arch_quality.arch_core import FileIndex
from arch_quality.arch_metrics_multilang import MultilangMetrics


class TestFileIndexBuildDir(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.builddir = tempfile.mkdtemp()
        self._create_source_files()

    def _create_source_files(self):
        hdr = os.path.join(self.tmpdir, "board.h")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write("class BOARD {\n  void Add();\n  void Remove();\n};\n")

        cpp = os.path.join(self.tmpdir, "main.cpp")
        with open(cpp, "w", encoding="utf-8") as f:
            f.write('#include "board.h"\nint main() { return 0; }\n')

    def _create_wrap_file(self):
        wrap_path = os.path.join(self.builddir, "pcbnewPYTHON_wrap.cxx")
        with open(wrap_path, "w", encoding="utf-8") as f:
            f.write(
                '#include "board.h"\n'
                'PyInit_pcbnew() {\n'
                '  m.def("Add", &BOARD::Add);\n'
                '  m.def("Remove", &BOARD::Remove);\n'
                '  m.def("GetNetItems", &CONNECTIVITY_DATA::GetNetItems);\n'
                '}\n'
            )
        return wrap_path

    def _create_swig_i_file(self):
        swig_path = os.path.join(self.builddir, "pcbnew.i")
        with open(swig_path, "w", encoding="utf-8") as f:
            f.write(
                '%module pcbnew\n'
                '%include "board.h"\n'
                '%extend CONNECTIVITY_DATA {\n'
                '  std::vector<ITEM*> GetNetItems(int aNetCode) {\n'
                '    return $self->GetNetItems(aNetCode);\n'
                '  }\n'
                '};\n'
            )
        return swig_path

    def _create_pyi_file(self):
        pyi_path = os.path.join(self.builddir, "pcbnew.pyi")
        with open(pyi_path, "w", encoding="utf-8") as f:
            f.write(
                'from typing import List\n\n'
                'class BOARD:\n'
                '    def Add(self) -> None: ...\n'
                '    def Remove(self) -> None: ...\n'
                'class CONNECTIVITY_DATA:\n'
                '    def GetNetItems(self, aNetCode: int) -> List[ITEM]: ...\n'
            )
        return pyi_path

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.builddir, ignore_errors=True)

    def test_no_build_dir_backward_compat(self):
        idx = FileIndex(self.tmpdir)
        self.assertTrue(len(idx.files) >= 2)
        langs = set(f["lang"] for f in idx.files)
        self.assertIn("cpp", langs)
        self.assertIn("c", langs)
        swig_files = idx.by_lang("swig")
        self.assertEqual(len(swig_files), 0)

    def test_build_dir_scans_wrap_cxx(self):
        self._create_wrap_file()
        idx = FileIndex(self.tmpdir, build_dir=self.builddir)
        wrap_files = [f for f in idx.files if f.get("is_swig_wrap")]
        self.assertEqual(len(wrap_files), 1)
        self.assertIn("pcbnewPYTHON_wrap", wrap_files[0]["path"])

    def test_build_dir_scans_swig_i(self):
        self._create_swig_i_file()
        idx = FileIndex(self.tmpdir, build_dir=self.builddir)
        swig_files = idx.by_lang("swig")
        build_swig = [f for f in swig_files if f.get("is_build_swig")]
        self.assertTrue(len(build_swig) >= 1)
        self.assertTrue(any("pcbnew.i" in f["path"] for f in build_swig))

    def test_build_dir_scans_pyi(self):
        self._create_pyi_file()
        idx = FileIndex(self.tmpdir, build_dir=self.builddir)
        pyi_files = [f for f in idx.files if f.get("is_pyi_stub")]
        self.assertTrue(len(pyi_files) >= 1)
        self.assertTrue(any("pcbnew.pyi" in f["path"] for f in pyi_files))

    def test_build_dir_nonexistent_path(self):
        idx = FileIndex(self.tmpdir, build_dir="/nonexistent/path")
        self.assertTrue(len(idx.files) >= 2)

    def test_build_dir_empty_path(self):
        idx = FileIndex(self.tmpdir, build_dir="")
        self.assertTrue(len(idx.files) >= 2)
        wrap_files = [f for f in idx.files if f.get("is_swig_wrap")]
        self.assertEqual(len(wrap_files), 0)

    def test_build_dir_does_not_duplicate_source_files(self):
        idx = FileIndex(self.tmpdir, build_dir=self.builddir)
        paths = [f["path"] for f in idx.files]
        self.assertEqual(len(paths), len(set(paths)))

    def test_build_dir_excludes_general_cpp(self):
        gen_cpp = os.path.join(self.builddir, "utils.cpp")
        with open(gen_cpp, "w", encoding="utf-8") as f:
            f.write("void helper() {}\n")
        idx = FileIndex(self.tmpdir, build_dir=self.builddir)
        build_cpp = [f for f in idx.files if f.get("from_build_dir") and f["ext"] == ".cpp" and not f.get("is_swig_wrap")]
        self.assertEqual(len(build_cpp), 0)

    def test_build_dir_includes_headers(self):
        hdr = os.path.join(self.builddir, "generated_board.h")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write("class GenBoard { void Run(); };\n")
        idx = FileIndex(self.tmpdir, build_dir=self.builddir)
        build_hdrs = [f for f in idx.files if f.get("from_build_dir") and f["ext"] == ".h"]
        self.assertTrue(len(build_hdrs) >= 1)
        self.assertTrue(any("generated_board.h" in f["path"] for f in build_hdrs))


class TestMultilangMetricsBuildDir(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.builddir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.builddir, ignore_errors=True)

    def test_metrics_accepts_build_dir(self):
        hdr = os.path.join(self.tmpdir, "board.h")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write("class BOARD { void Add(); void Remove(); };\n")
        metrics = MultilangMetrics(self.tmpdir, build_dir=self.builddir)
        self.assertEqual(metrics.build_dir, self.builddir)
        self.assertIsInstance(metrics._build_files, dict)

    def test_collect_build_bindings_empty(self):
        metrics = MultilangMetrics(self.tmpdir, build_dir=self.builddir)
        bf = metrics._build_files
        self.assertEqual(bf["wrap_files"], [])
        self.assertEqual(bf["swig_files"], [])
        self.assertEqual(bf["pyi_files"], [])

    def test_collect_build_bindings_wrap_file(self):
        wrap_path = os.path.join(self.builddir, "pcbnewPYTHON_wrap.cxx")
        with open(wrap_path, "w", encoding="utf-8") as f:
            f.write(
                '#include "board.h"\n'
                'PyInit_pcbnew() {\n'
                '  m.def("Add", &BOARD::Add);\n'
                '  m.def("GetNetItems", &CONNECTIVITY_DATA::GetNetItems);\n'
                '}\n'
            )

        hdr = os.path.join(self.tmpdir, "board.h")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write("class BOARD { void Add(); };\n")

        metrics = MultilangMetrics(self.tmpdir, build_dir=self.builddir)
        bf = metrics._build_files
        self.assertEqual(len(bf["wrap_files"]), 1)
        wrap = bf["wrap_files"][0]
        self.assertEqual(wrap["module_name"], "pcbnew")
        self.assertIn("Add", wrap["bound_funcs"])
        self.assertIn("GetNetItems", wrap["bound_funcs"])

    def test_collect_build_bindings_swig_file(self):
        swig_path = os.path.join(self.builddir, "pcbnew.i")
        with open(swig_path, "w", encoding="utf-8") as f:
            f.write(
                '%module pcbnew\n'
                '%include "board.h"\n'
                '%extend BOARD {\n'
                '  void Add() { $self->Add(); }\n'
                '};\n'
            )

        hdr = os.path.join(self.tmpdir, "board.h")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write("class BOARD { void Add(); };\n")

        metrics = MultilangMetrics(self.tmpdir, build_dir=self.builddir)
        bf = metrics._build_files
        self.assertEqual(len(bf["swig_files"]), 1)
        sb = bf["swig_files"][0]["bindings"]
        self.assertIn("pcbnew", sb["modules"])
        self.assertIn("Add", sb["extended_funcs"])

    def test_collect_build_bindings_pyi_file(self):
        pyi_path = os.path.join(self.builddir, "pcbnew.pyi")
        with open(pyi_path, "w", encoding="utf-8") as f:
            f.write(
                'class BOARD:\n'
                '    def Add(self) -> None: ...\n'
                '    def GetNetItems(self, code: int) -> list: ...\n'
            )

        hdr = os.path.join(self.tmpdir, "board.h")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write("class BOARD { void Add(); };\n")

        metrics = MultilangMetrics(self.tmpdir, build_dir=self.builddir)
        bf = metrics._build_files
        self.assertEqual(len(bf["pyi_files"]), 1)
        self.assertIn("Add", bf["pyi_files"][0]["functions"])
        self.assertIn("GetNetItems", bf["pyi_files"][0]["functions"])

    def test_binding_consistency_with_build_dir(self):
        wrap_path = os.path.join(self.builddir, "mylibPYTHON_wrap.cxx")
        with open(wrap_path, "w", encoding="utf-8") as f:
            f.write(
                '#include "mylib.h"\n'
                'PyInit_mylib() {\n'
                '  m.def("Init", &MyLib::Init);\n'
                '  m.def("Process", &MyLib::Process);\n'
                '}\n'
            )

        hdr = os.path.join(self.tmpdir, "mylib.h")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write("class MyLib { void Init(); void Process(); void Cleanup(); };\n")

        metrics = MultilangMetrics(self.tmpdir, build_dir=self.builddir)
        score, detail = metrics.calc_binding_consistency()
        self.assertTrue(detail["build_dir_used"])
        self.assertEqual(detail["build_wrap_count"], 1)

    def test_build_dir_cross_lang_edges(self):
        wrap_path = os.path.join(self.builddir, "testlibPYTHON_wrap.cxx")
        with open(wrap_path, "w", encoding="utf-8") as f:
            f.write(
                '#include "testlib.h"\n'
                'PyInit_testlib() {\n'
                '  m.def("Run", &TestLib::Run);\n'
                '}\n'
            )

        hdr = os.path.join(self.tmpdir, "testlib.h")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write("class TestLib { void Run(); };\n")

        metrics = MultilangMetrics(self.tmpdir, build_dir=self.builddir)
        has_wrap_node = any(
            n for n in metrics.graph.nodes
            if "wrap" in n.lower()
        )
        self.assertTrue(has_wrap_node)

    def test_mlr_003_wrap_signature_mismatch(self):
        wrap_path = os.path.join(self.builddir, "kicadPYTHON_wrap.cxx")
        with open(wrap_path, "w", encoding="utf-8") as f:
            f.write(
                '#include "connectivity.h"\n'
                'PyInit_kicad() {\n'
                '  m.def("GetNetItems", &CONNECTIVITY_DATA::GetNetItems);\n'
                '  m.def("InvalidFunc", &UnknownClass::Nonexistent);\n'
                '}\n'
            )

        hdr = os.path.join(self.tmpdir, "connectivity.h")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write("class CONNECTIVITY_DATA { void GetNetItems(); };\n")

        metrics = MultilangMetrics(self.tmpdir, build_dir=self.builddir)
        violations = metrics.check_mlr_rules()
        mlr_003 = [v for v in violations if v["rule"] == "MLR-003"]
        has_wrap_mismatch = any(
            "wrap" in v.get("detail", "").lower() or "build_dir" in v.get("name", "").lower()
            for v in mlr_003
        )
        self.assertTrue(has_wrap_mismatch, f"Expected MLR-003 build_dir wrap mismatch, got: {mlr_003}")

    def test_mlr_002_build_dir_binding_detected(self):
        hdrs = os.path.join(self.tmpdir, "headers")
        os.makedirs(hdrs, exist_ok=True)
        for i in range(5):
            with open(os.path.join(hdrs, f"hdr{i}.hpp"), "w", encoding="utf-8") as f:
                f.write(f"class Module{i} {{ void func{i}(); }};\n")

        wrap_path = os.path.join(self.builddir, "mylibPYTHON_wrap.cxx")
        with open(wrap_path, "w", encoding="utf-8") as f:
            f.write('PyInit_mylib() { m.def("func0", &Module0::func0); }\n')

        metrics = MultilangMetrics(self.tmpdir, build_dir=self.builddir)
        violations = metrics.check_mlr_rules()
        mlr_002 = [v for v in violations if v["rule"] == "MLR-002"]
        has_build_dir_note = any(
            "build_dir" in v.get("name", "") or "build_dir" in v.get("detail", "") or "_wrap" in v.get("detail", "")
            for v in mlr_002
        )
        self.assertTrue(has_build_dir_note, f"Expected MLR-002 build_dir note, got: {mlr_002}")

    def test_kicad_simulation(self):
        hdr = os.path.join(self.tmpdir, "connectivity_data.h")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write(
                "class CONNECTIVITY_DATA {\n"
                "  void Add();\n"
                "  void Remove();\n"
                "  std::vector<BOARD_CONNECTED_ITEM*> GetNetItems(int aNetCode, int aNetFilter=0);\n"
                "};\n"
            )

        swig_path = os.path.join(self.builddir, "pcbnew.i")
        with open(swig_path, "w", encoding="utf-8") as f:
            f.write(
                '%module pcbnew\n'
                '%include "connectivity_data.h"\n'
                '%extend CONNECTIVITY_DATA {\n'
                '  std::vector<BOARD_CONNECTED_ITEM*> GetNetItems(int aNetCode, ...) {\n'
                '    return $self->GetNetItems(aNetCode);\n'
                '  }\n'
                '};\n'
            )

        wrap_path = os.path.join(self.builddir, "pcbnewPYTHON_wrap.cxx")
        with open(wrap_path, "w", encoding="utf-8") as f:
            f.write(
                '#include "connectivity_data.h"\n'
                'PyInit_pcbnew() {\n'
                '  m.def("GetNetItems", &CONNECTIVITY_DATA::GetNetItems);\n'
                '}\n'
            )

        metrics = MultilangMetrics(self.tmpdir, build_dir=self.builddir)
        bf = metrics._build_files
        self.assertEqual(len(bf["wrap_files"]), 1)
        self.assertEqual(len(bf["swig_files"]), 1)
        self.assertIn("GetNetItems", bf["wrap_files"][0]["bound_funcs"])

        sb = bf["swig_files"][0]["bindings"]
        self.assertIn("GetNetItems", sb["extended_funcs"])

        score, detail = metrics.calc_binding_consistency()
        self.assertTrue(detail["build_dir_used"])
        self.assertEqual(detail["build_wrap_count"], 1)
        self.assertEqual(detail["build_swig_count"], 1)


class TestComprehensiveReportBuildDir(unittest.TestCase):

    def test_report_accepts_build_dir(self):
        from arch_quality.arch_report import ComprehensiveReport
        self.assertTrue(hasattr(ComprehensiveReport, '__init__'))
        import inspect
        sig = inspect.signature(ComprehensiveReport.__init__)
        self.assertIn('build_dir', sig.parameters)


class TestFileIndexBuildDirEdgeCases(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.builddir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.builddir, ignore_errors=True)

    def test_build_dir_no_wrap_extension(self):
        idx = FileIndex(self.tmpdir, build_dir=self.builddir)
        all_files_without_ext = [f for f in idx.files if f.get("from_build_dir")]
        self.assertEqual(len(all_files_without_ext), 0)

    def test_source_tree_not_duplicated(self):
        hdr = os.path.join(self.tmpdir, "base.h")
        with open(hdr, "w", encoding="utf-8") as f:
            f.write("void base_func();\n")

        same_name_file = os.path.join(self.builddir, "base.h")
        with open(same_name_file, "w", encoding="utf-8") as f:
            f.write("void base_func_build();\n")

        idx = FileIndex(self.tmpdir, build_dir=self.builddir)
        base_h_files = [f for f in idx.files if "base.h" in f["path"]]
        self.assertEqual(len(base_h_files), 2)

    def test_wrap_cpp_extension(self):
        wrap_path = os.path.join(self.builddir, "mylib_wrap.cpp")
        with open(wrap_path, "w", encoding="utf-8") as f:
            f.write('PyInit_mylib() { m.def("Test", &Test::Run); }\n')

        idx = FileIndex(self.tmpdir, build_dir=self.builddir)
        wrap_files = [f for f in idx.files if f.get("is_swig_wrap")]
        self.assertEqual(len(wrap_files), 1)

    def test_nested_build_dir(self):
        nested = os.path.join(self.builddir, "subdir", "nested")
        os.makedirs(nested, exist_ok=True)
        swig_path = os.path.join(nested, "module.i")
        with open(swig_path, "w", encoding="utf-8") as f:
            f.write('%module nested_mod\n')

        idx = FileIndex(self.tmpdir, build_dir=self.builddir)
        build_swig = [f for f in idx.files if f.get("from_build_dir") and f.get("is_build_swig")]
        self.assertTrue(len(build_swig) >= 1)


if __name__ == "__main__":
    unittest.main()