# -*- coding: utf-8 -*-
"""H3 WP-9 (H2 遗留 G1~G4) 回归测试。

G1: GCS 启用条件路径判定
G3: @kernel_exempt / @acl_exempt reason 允许含 '*'
G4: ACL import/export 插件目录识别 + 内核自身排除
"""
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from arch_quality.arch_core import FileIndex
from arch_quality.arch_metrics_geometry_consistency import (
    _detect_geometry, GeometryConsistencyMetrics,
)
from arch_quality.arch_metrics_anti_corruption import AntiCorruptionMetrics


def _write_tree(root, files):
    for rel, content in files.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


class TestG1PathDetection(unittest.TestCase):
    def test_path_keyword_enables(self):
        tmp = tempfile.mkdtemp(prefix="brep_tool_")
        try:
            _write_tree(tmp, {"a.cpp": "int x = 1;\n"})
            self.assertTrue(_detect_geometry(tmp, FileIndex(tmp)))
        finally:
            shutil.rmtree(tmp)

    def test_plain_path_disabled(self):
        tmp = tempfile.mkdtemp(prefix="plainproj_")
        try:
            _write_tree(tmp, {"a.cpp": "int x = 1;\n"})
            self.assertFalse(_detect_geometry(tmp, FileIndex(tmp)))
        finally:
            shutil.rmtree(tmp)

    def test_subdir_keyword_enables(self):
        tmp = tempfile.mkdtemp(prefix="app_")
        try:
            _write_tree(tmp, {"src/brep/ops.cpp": "int x = 1;\n"})
            self.assertTrue(_detect_geometry(tmp, FileIndex(tmp)))
        finally:
            shutil.rmtree(tmp)


class TestG3ExemptStar(unittest.TestCase):
    def test_kernel_exempt_reason_with_star(self):
        tmp = tempfile.mkdtemp(prefix="geomproj_")
        try:
            _write_tree(tmp, {
                "src/a.cpp": "/* @kernel_exempt: fix * legacy * path */\nTopoDS_Shape s;\n",
            })
            m = GeometryConsistencyMetrics(tmp)
            self.assertTrue(m._is_geometry)
            self.assertTrue(any("fix * legacy * path" in r for r in m._kernel_exempt.values()))
        finally:
            shutil.rmtree(tmp)

    def test_acl_exempt_reason_with_star(self):
        tmp = tempfile.mkdtemp(prefix="aclproj_")
        try:
            _write_tree(tmp, {
                "src/a.cpp": "/* @acl_exempt: vendored *occt* sdk */\nTopoDS_Shape s;\n",
            })
            m = AntiCorruptionMetrics(tmp)
            self.assertTrue(m._is_acl)
            self.assertTrue(any("vendored *occt* sdk" in r for r in m._acl_exempt.values()))
        finally:
            shutil.rmtree(tmp)


class TestG4AclCalibration(unittest.TestCase):
    def test_import_export_plugin_dirs(self):
        tmp = tempfile.mkdtemp(prefix="cadproj_")
        try:
            _write_tree(tmp, {
                "src/kernel_user.cpp": "TopoDS_Shape s;\n",
                "src/STEPPlugin/reader.cpp": "STEPControl_Reader r;\n",
                "src/IGESPlugin/writer.cpp": "IGESControl_Writer w;\n",
            })
            m = AntiCorruptionMetrics(tmp)
            step = os.path.join(tmp, "src", "STEPPlugin", "reader.cpp")
            iges = os.path.join(tmp, "src", "IGESPlugin", "writer.cpp")
            self.assertTrue(m._in_import_export_dir(step))
            self.assertTrue(m._in_import_export_dir(iges))
            # ACL-007 不应统计 import/export 插件目录内的格式调用
            r = m.all_metrics()
            acl007 = next((v for v in r.get("acl_violations", []) if v["rule"] == "ACL-007"), None)
            self.assertTrue(acl007 is None or acl007["count"] == 0)
        finally:
            shutil.rmtree(tmp)

    def test_kernel_self_excluded(self):
        tmp = tempfile.mkdtemp(prefix="consumer_")
        try:
            _write_tree(tmp, {
                "src/app.cpp": "TopoDS_Shape s;\n",
                "vendor/occt/kernel.cpp": "TopoDS_Shape t;\n",
            })
            m = AntiCorruptionMetrics(tmp)
            kp = os.path.join(tmp, "vendor", "occt", "kernel.cpp")
            self.assertTrue(m._is_kernel_self(kp))
            self.assertTrue(m._skip(kp))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()