# -*- coding: utf-8 -*-
"""
test_wp6_origin_annotation.py — WP-6 违规来源标注（[third-party] / [test]）单元测试

覆盖：
1. 来源分类器 arch_origin.classify_path / classify_paths / origin_tag
2. template MLR-024 origin_counts（第三方/测试/自有循环分类）
3. ReportGenerator 渲染（[third-party×N] / [test×N] 标记 + 来源汇总）
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arch_quality.arch_origin import (
    classify_path, classify_paths, origin_tag, is_third_party_path, is_test_path,
)
from arch_quality.arch_metrics_template import TemplateMetaprogrammingMetrics
from arch_quality.arch_report_generator import ReportGenerator


def _write_tree(root, files):
    for path, content in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


def _make_project(files):
    tmp = tempfile.mkdtemp()
    _write_tree(tmp, files)
    return tmp


class TestClassifyPath(unittest.TestCase):
    def test_first_party(self):
        self.assertEqual(classify_path("src/geom/foo.cpp"), "first_party")

    def test_third_party_dirs(self):
        for p in ("third_party/eigen/E.h", "third-party/lib/a.h", "vendor/occt/X.cxx",
                  "external/foo/b.cc", "deps/abseil/a.cc", "contrib/x/y.cpp"):
            self.assertEqual(classify_path(p), "third_party", p)

    def test_test_dirs_and_names(self):
        for p in ("tests/test_foo.cpp", "src/foo_test.cpp", "test/bar.py",
                  "gtests/x_test.cc", "examples/demo.py"):
            self.assertEqual(classify_path(p), "test", p)

    def test_third_party_priority_over_test(self):
        # 第三方目录下的测试文件仍归第三方
        self.assertEqual(classify_path("third-party/benchmark/tests/x.cc"), "third_party")

    def test_classify_paths_most_severe(self):
        self.assertEqual(classify_paths(["src/a.cpp", "third-party/x.h"]), "third_party")
        self.assertEqual(classify_paths(["src/a.cpp", "tests/t.cpp"]), "test")
        self.assertEqual(classify_paths(["src/a.cpp", "src/b.cpp"]), "first_party")

    def test_origin_tag(self):
        self.assertEqual(origin_tag("third_party"), "[third-party]")
        self.assertEqual(origin_tag("test"), "[test]")
        self.assertEqual(origin_tag("first_party"), "")

    def test_backward_compat_helpers(self):
        self.assertTrue(is_third_party_path("third-party/x.h"))
        self.assertTrue(is_test_path("tests/x.cpp"))


class TestMLR024OriginCounts(unittest.TestCase):
    def test_mixed_cycles_classified(self):
        tmp = _make_project({
            "third-party/lib/a.h": '#pragma once\n#include "b.h"\nstruct A {};\n',
            "third-party/lib/b.h": '#pragma once\n#include "a.h"\nstruct B {};\n',
            "tests/helpers/x.h": '#pragma once\n#include "y.h"\nstruct X {};\n',
            "tests/helpers/y.h": '#pragma once\n#include "x.h"\nstruct Y {};\n',
            "src/foo.h": '#pragma once\n#include "bar.h"\nstruct Foo {};\n',
            "src/bar.h": '#pragma once\n#include "foo.h"\nstruct Bar {};\n',
            "src/main.cpp": "int main(){return 0;}\n",
        })
        try:
            m = TemplateMetaprogrammingMetrics(tmp)
            viol = [v for v in m.all_metrics().get("mlr_violations", [])
                    if v["rule"] == "MLR-024"]
            self.assertEqual(len(viol), 1)
            oc = viol[0].get("origin_counts", {})
            self.assertEqual(oc.get("third_party"), 1)
            self.assertEqual(oc.get("test"), 1)
            self.assertEqual(oc.get("first_party"), 1)
            self.assertEqual(viol[0]["count"], 3)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestReportRendering(unittest.TestCase):
    def _render(self, violations):
        tmp = tempfile.mkdtemp()
        try:
            gen = ReportGenerator(tmp, {"dimensions": {"structural": {"score": 50}},
                                        "mlr_violations": violations}, [])
            return gen._mlr_violations()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_origin_counts_tag(self):
        md = self._render([{
            "rule": "MLR-024", "name": "头文件包含循环依赖", "severity": "HIGH",
            "output_level": "ERROR", "count": 3,
            "origin_counts": {"third_party": 1, "test": 1, "first_party": 1},
            "detail": "x",
        }])
        self.assertIn("[third-party×1]", md)
        self.assertIn("[test×1]", md)
        self.assertIn("来源标注（WP-6）", md)

    def test_single_origin_tag(self):
        md = self._render([{
            "rule": "MLR-001", "name": "第三方循环", "severity": "INFO",
            "output_level": "INFO", "count": 2, "origin": "third_party", "detail": "x",
        }])
        self.assertIn("[third-party]", md)

    def test_first_party_no_tag(self):
        md = self._render([{
            "rule": "MLR-014", "name": "重复实例化", "severity": "HIGH",
            "output_level": "WARNING", "count": 1, "detail": "x",
        }])
        self.assertNotIn("[third-party", md)
        self.assertNotIn("[test", md)


if __name__ == "__main__":
    unittest.main()
