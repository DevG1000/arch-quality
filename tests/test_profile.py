"""
test_profile.py — H2 WP-0 显式 profile 测试

覆盖：
1. 配置解析 — arch-quality.yaml / pyproject.toml [tool.arch-quality] / 无配置兜底
2. schema 校验 — 非法 profile / 未知引擎 / skip standard / 未知键
3. 引擎解析优先级 — profile > enable_engines > skip_engines > 全量
4. ComprehensiveReport — profile 子集评分（过渡口径 8b）、跳过引擎并列展示、禁止混合计分
5. 引擎选择 — 仅运行启用引擎（未启用引擎不执行）
6. CLI — --profile 覆盖配置文件、配置文件自动加载

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

from arch_quality.arch_core import (
    load_profile_config, resolve_enabled_engines, PROFILE_ENGINE_MAP,
    ALL_ENGINES, ENHANCEMENT_ENGINES,
)
from arch_quality.arch_report import ComprehensiveReport


def _write_tree(root, files: dict):
    for path, content in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


def _make_numerical_project():
    """创建数值项目（触发 numerical 检测，支持 .f90 + solver 关键词）"""
    tmp = tempfile.mkdtemp()
    _write_tree(tmp, {
        "README.md": "# Proj\n## 安装\n## 使用\n## 功能\n",
        "CHANGELOG.md": "# Changelog\n## [1.0.0] - 2026-08-21\n### Added\n- x\n",
        "docs/architecture.md": "# Arch\n## 目录结构\n## 模块职责\n## 数据流\n## 依赖关系\n## 设计决策\n",
        "src/solver.f90": (
            "program solve\n"
            "  implicit none\n"
            "  real*8 :: x, cfl\n"
            "  cfl = 0.5d0\n"
            "  x = 1.0d0 + cfl\n"
            "end program solve\n"),
    })
    return tmp


def _make_plain_project():
    """创建无增强引擎项目（单语言 Python，无数值/多物理场信号）"""
    tmp = tempfile.mkdtemp()
    _write_tree(tmp, {
        "README.md": "# Proj\n## 安装\n## 使用\n## 功能\n",
        "src/main.py": "def main():\n    print('hello')\n",
    })
    return tmp


class TestConfigParsing(unittest.TestCase):
    """配置解析与 schema 校验"""

    def test_no_config_returns_empty(self):
        tmp = _make_plain_project()
        try:
            self.assertEqual(load_profile_config(tmp), {})
        finally:
            shutil.rmtree(tmp)

    def test_yaml_profile(self):
        tmp = _make_plain_project()
        try:
            _write_tree(tmp, {"arch-quality.yaml": "profile: numerical\n"})
            cfg = load_profile_config(tmp)
            self.assertEqual(cfg["profile"], "numerical")
            self.assertEqual(cfg["enabled_engines"], ["standard", "numerical"])
            self.assertTrue(cfg["config_source"].endswith("arch-quality.yaml"))
        finally:
            shutil.rmtree(tmp)

    def test_yaml_test_dirs(self):
        tmp = _make_plain_project()
        try:
            _write_tree(tmp, {
                "arch-quality.yaml": "test_dirs:\n  - tutorials\n  - tests-external\n"})
            cfg = load_profile_config(tmp)
            self.assertEqual(cfg["test_dirs"], ["tutorials", "tests-external"])
            # 无 profile/enable/skip → 全量引擎
            self.assertEqual(set(cfg["enabled_engines"]), set(ALL_ENGINES))
        finally:
            shutil.rmtree(tmp)

    def test_toml_profile(self):
        tmp = _make_plain_project()
        try:
            _write_tree(tmp, {
                "pyproject.toml": (
                    "[tool.arch-quality]\n"
                    'profile = "template"\n'
                    'skip_engines = ["solver-physics"]\n')})
            cfg = load_profile_config(tmp)
            self.assertEqual(cfg["profile"], "template")
            self.assertEqual(set(cfg["enabled_engines"]), {"standard", "template"})
        finally:
            shutil.rmtree(tmp)

    def test_yaml_precedes_toml(self):
        tmp = _make_plain_project()
        try:
            _write_tree(tmp, {
                "arch-quality.yaml": "profile: numerical\n",
                "pyproject.toml": (
                    "[tool.arch-quality]\nprofile = \"multilang\"\n")})
            cfg = load_profile_config(tmp)
            self.assertEqual(cfg["profile"], "numerical")
            self.assertTrue(cfg["config_source"].endswith("arch-quality.yaml"))
        finally:
            shutil.rmtree(tmp)

    def test_invalid_profile_value(self):
        tmp = _make_plain_project()
        try:
            _write_tree(tmp, {"arch-quality.yaml": "profile: bogus\n"})
            with self.assertRaises(ValueError):
                load_profile_config(tmp)
        finally:
            shutil.rmtree(tmp)

    def test_unknown_engine(self):
        tmp = _make_plain_project()
        try:
            _write_tree(tmp, {"arch-quality.yaml": "enable_engines: [bogus_engine]\n"})
            with self.assertRaises(ValueError):
                load_profile_config(tmp)
        finally:
            shutil.rmtree(tmp)

    def test_skip_standard_rejected(self):
        tmp = _make_plain_project()
        try:
            _write_tree(tmp, {"arch-quality.yaml": "skip_engines: [standard]\n"})
            with self.assertRaises(ValueError):
                load_profile_config(tmp)
        finally:
            shutil.rmtree(tmp)

    def test_unknown_key_rejected(self):
        tmp = _make_plain_project()
        try:
            _write_tree(tmp, {"arch-quality.yaml": "unknown_key: 1\n"})
            with self.assertRaises(ValueError):
                load_profile_config(tmp)
        finally:
            shutil.rmtree(tmp)


class TestEngineResolution(unittest.TestCase):
    """引擎解析优先级：profile > enable_engines > skip_engines > 全量"""

    def test_profile_map(self):
        for profile, expected in PROFILE_ENGINE_MAP.items():
            self.assertEqual(resolve_enabled_engines(profile, None, None), expected)

    def test_enable_engines_auto_adds_standard(self):
        self.assertEqual(
            resolve_enabled_engines(None, ["numerical", "template"], None),
            ["standard", "numerical", "template"])

    def test_skip_engines_from_full(self):
        self.assertEqual(
            set(resolve_enabled_engines(None, None, ["multilang", "solver-physics"])),
            {"standard", "template", "numerical", "geometry-consistency",
             "anti-corruption"})

    def test_profile_precedence_over_enable(self):
        # profile 声明优先于 enable_engines
        self.assertEqual(
            resolve_enabled_engines("numerical", ["template"], None),
            ["standard", "numerical"])

    def test_skip_applies_on_profile(self):
        self.assertEqual(
            resolve_enabled_engines("numerical", None, ["numerical"]),
            ["standard"])

    def test_standard_never_dropped(self):
        for engines in ([], None):
            result = resolve_enabled_engines(None, engines, [])
            self.assertIn("standard", result)

    def test_multiple_profiles_union(self):
        # 多 profile（list）：引擎集取并集，standard 保留且不重复
        result = resolve_enabled_engines(["numerical", "template"], None, None)
        self.assertEqual(result, ["standard", "numerical", "template"])

    def test_multiple_profiles_dedupe(self):
        # 重复 profile 不重复加引擎
        result = resolve_enabled_engines(["numerical", "numerical"], None, None)
        self.assertEqual(result, ["standard", "numerical"])

    def test_multiple_profiles_with_skip(self):
        result = resolve_enabled_engines(
            ["numerical", "template"], None, ["numerical"])
        self.assertEqual(result, ["standard", "template"])


class TestComprehensiveReportProfile(unittest.TestCase):
    """ComprehensiveReport profile 子集评分（过渡口径 8b）"""

    def test_heuristic_default_not_subset(self):
        tmp = _make_numerical_project()
        try:
            data = ComprehensiveReport(tmp).generate()
            self.assertFalse(data["profile"]["active"])
            self.assertFalse(data["profile"]["subset_scoring"])
            # 启发式：数值项目应激活 numerical
            self.assertIn("numerical_enhancement", data["dimensions"]["structural"])
        finally:
            shutil.rmtree(tmp)

    def test_numerical_profile_subset(self):
        tmp = _make_numerical_project()
        try:
            profile = {"profile": "numerical", "enabled_engines": ["standard", "numerical"]}
            data = ComprehensiveReport(tmp, profile=profile).generate()
            self.assertTrue(data["profile"]["active"])
            self.assertTrue(data["profile"]["subset_scoring"])
            self.assertEqual(data["profile"]["enabled_engines"], ["numerical", "standard"])
            skipped = data["profile"]["skipped_engines"]
            self.assertIn("multilang", skipped)
            self.assertIn("template", skipped)
            self.assertIn("solver-physics", skipped)
            # 跳过引擎并列展示（未评估标注）
            sk = {s["engine"] for s in data["dimensions"]["structural"]["skipped_enhancements"]}
            self.assertEqual(sk, set(skipped))
            # 数值增强已评估
            self.assertIn("numerical_enhancement", data["dimensions"]["structural"])
            # 过渡口径标注
            self.assertIn("禁止混合计分", data["profile"]["note"])
        finally:
            shutil.rmtree(tmp)

    def test_standard_profile_no_enhancement(self):
        tmp = _make_numerical_project()
        try:
            profile = {"profile": "standard", "enabled_engines": ["standard"]}
            data = ComprehensiveReport(tmp, profile=profile).generate()
            self.assertTrue(data["profile"]["subset_scoring"])
            self.assertEqual(len(data["profile"]["skipped_engines"]), 6)
            self.assertNotIn("numerical_enhancement", data["dimensions"]["structural"])
        finally:
            shutil.rmtree(tmp)

    def test_full_engine_profile_not_subset(self):
        tmp = _make_numerical_project()
        try:
            profile = {"enabled_engines": list(ALL_ENGINES)}
            data = ComprehensiveReport(tmp, profile=profile).generate()
            self.assertTrue(data["profile"]["active"])
            self.assertFalse(data["profile"]["subset_scoring"])
            self.assertEqual(data["profile"]["skipped_engines"], [])
            self.assertNotIn("skipped_enhancements", data["dimensions"]["structural"])
        finally:
            shutil.rmtree(tmp)

    def test_skipped_engine_violations_not_merged(self):
        # 跳过 multilang → 报告不含其违规；启发式下可能含
        tmp = _make_numerical_project()
        try:
            profile = {"profile": "numerical", "enabled_engines": ["standard", "numerical"]}
            data = ComprehensiveReport(tmp, profile=profile).generate()
            for v in data["mlr_violations"]:
                self.assertNotIn("MLR-", v.get("rule", ""))
        finally:
            shutil.rmtree(tmp)

    def test_profile_scores_are_subset_labeled(self):
        # structural_note 标注子集评分
        tmp = _make_numerical_project()
        try:
            profile = {"profile": "numerical", "enabled_engines": ["standard", "numerical"]}
            data = ComprehensiveReport(tmp, profile=profile).generate()
            self.assertIn("profile 子集评分", data["score_breakdown"]["structural_note"])
        finally:
            shutil.rmtree(tmp)


class TestEngineSkipExecution(unittest.TestCase):
    """profile 模式下仅运行启用引擎（未启用引擎不执行 all_metrics）"""

    def test_disabled_engines_not_executed(self):
        tmp = _make_numerical_project()
        try:
            reporter = ComprehensiveReport(tmp, profile={
                "profile": "numerical", "enabled_engines": ["standard", "numerical"]})
            calls = []
            for name in ("multilang", "template", "solver_physics"):
                engine = getattr(reporter, name)
                orig = engine.all_metrics
                calls.append(name)
                engine.all_metrics = lambda o=orig, n=name: (_ for _ in ()).throw(
                    AssertionError(f"engine {n} 不应被执行"))
            # 若被跳过引擎被执行，lambda 抛出 AssertionError
            data = reporter.generate()
            self.assertTrue(data["profile"]["active"])
            self.assertTrue(calls)  # 三个跳过引擎的调用点均已打桩
        finally:
            shutil.rmtree(tmp)


class TestProfileCLI(unittest.TestCase):
    """CLI --profile 与配置文件自动加载"""

    def _run_cli(self, root, extra=()):
        return subprocess.run(
            [sys.executable, "-m", "arch_quality", root, "--json", *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=os.path.join(os.path.dirname(__file__), '..'),
            timeout=120,
        )

    def test_cli_profile_flag(self):
        tmp = _make_numerical_project()
        try:
            result = self._run_cli(tmp, ("--profile", "numerical"))
            out = result.stdout
            json_start = out.find("{")
            data = json.loads(out[json_start:out.rfind("}") + 1])
            self.assertTrue(data["profile"]["active"])
            self.assertEqual(data["profile"]["profile"], "numerical")
            self.assertTrue(data["profile"]["subset_scoring"])
        finally:
            shutil.rmtree(tmp)

    def test_cli_multiple_profiles_union(self):
        # 重复 --profile flag（action=append）：引擎集取并集
        tmp = _make_numerical_project()
        try:
            result = self._run_cli(tmp, ("--profile", "numerical", "--profile", "template"))
            out = result.stdout
            json_start = out.find("{")
            data = json.loads(out[json_start:out.rfind("}") + 1])
            self.assertTrue(data["profile"]["active"])
            self.assertEqual(
                set(data["profile"]["enabled_engines"]),
                {"standard", "numerical", "template"})
            self.assertIn("numerical_enhancement",
                          data["dimensions"]["structural"])
            # template 引擎是否产出取决于项目语言（合成项目为 fortran，
            # 无 C++ 时引擎可能不产出指标）——只验证并集语义，不强制键存在
        finally:
            shutil.rmtree(tmp)

    def test_cli_single_profile_kept_as_string(self):
        # 单 profile 归一为字符串（历史语义）
        tmp = _make_numerical_project()
        try:
            result = self._run_cli(tmp, ("--profile", "numerical"))
            out = result.stdout
            json_start = out.find("{")
            data = json.loads(out[json_start:out.rfind("}") + 1])
            self.assertEqual(data["profile"]["profile"], "numerical")
        finally:
            shutil.rmtree(tmp)

    def test_config_file_auto_loaded(self):
        tmp = _make_numerical_project()
        try:
            _write_tree(tmp, {"arch-quality.yaml": "profile: standard\n"})
            result = self._run_cli(tmp)
            out = result.stdout
            json_start = out.find("{")
            data = json.loads(out[json_start:out.rfind("}") + 1])
            self.assertTrue(data["profile"]["active"])
            self.assertEqual(data["profile"]["profile"], "standard")
            self.assertTrue(data["profile"]["config_source"].endswith("arch-quality.yaml"))
        finally:
            shutil.rmtree(tmp)

    def test_cli_profile_overrides_config(self):
        tmp = _make_numerical_project()
        try:
            _write_tree(tmp, {"arch-quality.yaml": "profile: standard\n"})
            result = self._run_cli(tmp, ("--profile", "numerical"))
            out = result.stdout
            json_start = out.find("{")
            data = json.loads(out[json_start:out.rfind("}") + 1])
            self.assertEqual(data["profile"]["profile"], "numerical")
            self.assertIn("numerical", data["profile"]["enabled_engines"])
        finally:
            shutil.rmtree(tmp)

    def test_invalid_config_exit_code(self):
        tmp = _make_numerical_project()
        try:
            _write_tree(tmp, {"arch-quality.yaml": "profile: bogus\n"})
            result = self._run_cli(tmp)
            self.assertEqual(result.returncode, 1)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()