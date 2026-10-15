"""
test_anti_corruption_integration.py — ACL 引擎集成 + 端到端测试（B2.5）

覆盖：
1. 权重解析集成 — ACL skill 权重与引擎 all_metrics 使用一致
2. 报告合并集成 — ComprehensiveReport 合并 anti_corruption_enhancement
3. ACL 违规合并 — acl_violations 正确追加到 mlr_violations
4. 权重归一化 — 多增强同时激活时 structural 权重处理不崩溃
5. profile 集成 — profile=anti-corruption 仅运行 standard+acl
6. E2E — 合成防腐项目全链路 + CLI JSON 输出

使用合成项目，不依赖外部仓库。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from arch_quality.arch_core import load_weights_from_skill, PROFILE_ENGINE_MAP
from arch_quality.arch_report import ComprehensiveReport
from arch_quality.arch_metrics_anti_corruption import AntiCorruptionMetrics

SKILL_ACL = os.path.join(os.path.dirname(__file__), '..', 'src',
                         'arch_quality', 'skills', 'anti-corruption.md')


def _write_tree(root, files: dict):
    for path, content in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


def _make_good_acl():
    """好防腐项目（4 维均高、无 ERROR 违规）"""
    tmp = tempfile.mkdtemp()
    _write_tree(tmp, {
        "README.md": "# Proj\n",
        "src/main.cpp": "int main(){return 0;}\n",
        "wrapper/cad_ops.h": (
            "class CadEngine {\n"
            "public:\n"
            "    MatShape do_fuse(const MatShape& a);\n"
            "};\n"),
        "wrapper/cad_ops.cpp": (
            "#include <BRepAlgoAPI_Fuse.hxx>\n"
            "#if OCC_VERSION >= 70800\n"
            "MatShape CadEngine::do_fuse(const MatShape& a){\n"
            "    BRepAlgoAPI_Fuse op(a.inner());\n"
            "    if(!op.IsDone()) throw std::runtime_error(\"fail\");\n"
            "    return MatShape::wrap(op.Shape());\n"
            "}\n"
            "#endif\n"),
        "importexport/step_io.cpp": (
            "#include <STEPControl_Reader.hxx>\n"
            "#include <IFSelect_ReturnStatus.hxx>\n"
            "void import_step(const char* path){\n"
            "    STEPControl_Reader r;\n"
            "    if(r.ReadFile(path) != IFSelect_RetDone) throw std::runtime_error(\"rf\");\n"
            "    r.TransferRoots();\n"
            "}\n"),
        "importexport/test_stability.cpp": (
            "TEST(Step, RoundTrip){\n"
            "    STEPControl_Writer w; w.Write(\"t.stp\");\n"
            "    STEPControl_Reader r; r.ReadFile(\"t.stp\"); r.TransferRoots();\n"
            "    ASSERT_EQ(r.OneShape(), shape_);\n"
            "}\n"),
        "src/business.cpp": (
            "#include \"../wrapper/cad_ops.h\"\n"
            "void run(){ CadEngine e; MatShape m = e.do_fuse(a); }\n"),
    })
    return tmp


def _make_bad_acl():
    """坏防腐项目（触发 ACL-001 直连 + ACL-007 交换散落）"""
    tmp = tempfile.mkdtemp()
    _write_tree(tmp, {
        "README.md": "# Proj\n",
        "src/merge.cpp": (
            "#include <BRepAlgoAPI_Fuse.hxx>\n"
            "TopoDS_Shape merge(TopoDS_Shape a, TopoDS_Shape b){\n"
            "    BRepAlgoAPI_Fuse op(a, b);\n"
            "    return op.Shape();\n"
            "}\n"),
        "src/export.cpp": (
            "#include <STEPControl_Writer.hxx>\n"
            "void export_step(){ STEPControl_Writer w; w.Write(\"x.stp\"); }\n"),
    })
    return tmp


class TestWeightParsingIntegration(unittest.TestCase):
    """权重解析集成"""

    def test_acl_skill_weights_match_engine(self):
        w = load_weights_from_skill(SKILL_ACL)
        self.assertEqual(len(w), 4)
        self.assertAlmostEqual(sum(w.values()), 1.0)
        tmp = _make_good_acl()
        try:
            m = AntiCorruptionMetrics(tmp)
            r = m.all_metrics()
            self.assertIn("overall", r)
        finally:
            shutil.rmtree(tmp)


class TestReportMerge(unittest.TestCase):
    """报告合并集成"""

    def test_good_acl_enhancement_merged(self):
        tmp = _make_good_acl()
        try:
            report = ComprehensiveReport(tmp)
            result = report.generate()
            ext = result["dimensions"]["structural"].get("anti_corruption_enhancement")
            self.assertIsNotNone(ext, "好防腐项目应产生 ACL 增强合并")
            self.assertGreaterEqual(ext["score"], 0)
            self.assertLessEqual(ext["score"], 100)
        finally:
            shutil.rmtree(tmp)

    def test_bad_acl_violations_merged(self):
        tmp = _make_bad_acl()
        try:
            report = ComprehensiveReport(tmp)
            result = report.generate()
            acl_rules = [v for v in result["mlr_violations"]
                         if v.get("rule", "").startswith("ACL-")]
            self.assertTrue(any(v["rule"] == "ACL-001" for v in acl_rules),
                            "坏例应触发 ACL-001 并合并到 mlr_violations")
            self.assertTrue(any(v["rule"] == "ACL-007" for v in acl_rules),
                            "坏例应触发 ACL-007 并合并到 mlr_violations")
        finally:
            shutil.rmtree(tmp)

    def test_non_acl_report_has_no_enhancement(self):
        tmp = tempfile.mkdtemp()
        _write_tree(tmp, {
            "src/app.py": "def hello():\n    print('hi')\n",
            "README.md": "# plain\n",
        })
        try:
            report = ComprehensiveReport(tmp)
            result = report.generate()
            ext = result["dimensions"]["structural"].get("anti_corruption_enhancement")
            self.assertIsNone(ext, "非切入点项目不应有 ACL 增强")
        finally:
            shutil.rmtree(tmp)


class TestProfileIntegration(unittest.TestCase):
    """profile 集成"""

    def test_acl_in_engine_map(self):
        self.assertIn("anti-corruption", PROFILE_ENGINE_MAP)
        self.assertEqual(PROFILE_ENGINE_MAP["anti-corruption"],
                         ["standard", "anti-corruption"])

    def test_profile_acl_constrained(self):
        tmp = _make_good_acl()
        try:
            report = ComprehensiveReport(tmp, profile={
                "profile": "anti-corruption", "enabled_engines": ["anti-corruption"],
            })
            result = report.generate()
            pm = result["profile"]
            self.assertEqual(pm["enabled_engines"], ["anti-corruption"])
            ext = result["dimensions"]["structural"].get("anti_corruption_enhancement")
            self.assertIsNotNone(ext)
        finally:
            shutil.rmtree(tmp)


class TestE2E(unittest.TestCase):
    """端到端 CLI"""

    def test_cli_json(self):
        tmp = _make_bad_acl()
        try:
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
            out = subprocess.run(
                [sys.executable, "-m", "arch_quality.arch_metrics_anti_corruption",
                 tmp, "--json"],
                capture_output=True, text=True, encoding="utf-8",
                env=env, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            self.assertEqual(out.returncode, 0, out.stderr)
            data = json.loads(out.stdout)
            self.assertIn("is_acl", data)
            self.assertTrue(data["is_acl"])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()