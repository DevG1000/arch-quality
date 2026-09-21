"""
test_ui.py — arch-quality Web 操作界面（Flask）单元测试

覆盖：
1. commands_meta：7 个入口的参数完整性、命令拼接、互斥校验
2. runner：命令构造（参数 → argv）正确性
3. server：Flask 路由（/api/commands、历史 CRUD、/api/run 校验、/api/browse）

使用 unittest 风格，Flask test_client 验证，不触发真实长评估。
"""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from arch_quality.ui import commands_meta
from arch_quality.ui.commands_meta import (
    COMMANDS, COMMAND_ORDER, get_command, check_mutex, build_argv,
    build_command_string,
)


class TestCommandsMeta(unittest.TestCase):
    """7 个入口的参数元数据完整性。"""

    def test_all_entries_present(self):
        expected = {"comprehensive", "standard", "multilang", "template",
                    "numerical", "solver", "geometry"}
        self.assertEqual(set(COMMANDS.keys()), expected)

    def test_all_entries_in_order(self):
        self.assertEqual(set(COMMAND_ORDER), set(COMMANDS.keys()))

    def test_every_command_has_entry_and_params(self):
        for cid, cmd in COMMANDS.items():
            self.assertIn("entry", cmd, cid)
            self.assertIn("label", cmd, cid)
            self.assertGreaterEqual(len(cmd["params"]), 1, cid)
            # 每个参数有 name/type
            for p in cmd["params"]:
                self.assertIn("name", p, cid)
                self.assertIn("type", p, cid)
                self.assertIn(p["type"], ("path", "str", "choice", "bool", "multi", "multicheck"), cid)

    def test_required_root_present(self):
        for cid in COMMANDS:
            params = COMMANDS[cid]["params"]
            roots = [p for p in params if p["name"] == "root"]
            self.assertEqual(len(roots), 1, cid)
            self.assertTrue(roots[0]["required"], cid)


class TestBuildArgv(unittest.TestCase):
    """参数 → argv 命令拼接。"""

    def test_comprehensive_defaults(self):
        argv = build_argv("comprehensive", {})
        # 仅 root 默认 "."（位置参数），无任何 flag
        self.assertEqual(argv, ["."])

    def test_comprehensive_flags(self):
        argv = build_argv("comprehensive", {
            "root": "C:/proj",
            "report_mode": "central",
            "json": True,
        })
        self.assertEqual(argv, ["C:/proj", "--report-mode", "central", "--json"])

    def test_project_name_only_visible_when_central(self):
        # project_name 是联动字段，但拼接逻辑本身只按值处理
        argv = build_argv("comprehensive", {
            "root": "P", "report_mode": "local", "project_name": "X",
        })
        self.assertNotIn("--project-name", argv)
        argv2 = build_argv("comprehensive", {
            "root": "P", "report_mode": "central", "project_name": "X",
        })
        self.assertIn("--project-name", argv2)

    def test_multi_test_dirs(self):
        argv = build_argv("comprehensive", {
            "root": "P", "test_dirs": "tutorials tests-external",
        })
        self.assertIn("--test-dirs", argv)
        self.assertIn("tutorials", argv)
        self.assertIn("tests-external", argv)

    def test_multicheck_profile(self):
        # 多选 profile：每个选中项追加一次 --profile <value>
        argv = build_argv("comprehensive", {
            "root": "P", "profile": ["numerical", "template"],
        })
        self.assertEqual(argv.count("--profile"), 2)
        self.assertIn("numerical", argv)
        self.assertIn("template", argv)
        self.assertEqual(
            [argv[i+1] for i, a in enumerate(argv) if a == "--profile"],
            ["numerical", "template"])

    def test_multicheck_profile_empty(self):
        argv = build_argv("comprehensive", {"root": "P", "profile": []})
        self.assertNotIn("--profile", argv)

    def test_multilang_mutex_violation(self):
        violations = check_mutex("multilang", {"full": True, "mlr_only": True})
        self.assertEqual(len(violations), 1)

    def test_multilang_mutex_ok(self):
        violations = check_mutex("multilang", {"full": True, "mlr_only": False})
        self.assertEqual(violations, [])

    def test_command_string(self):
        s = build_command_string("standard", {"root": "P", "metrics": True})
        self.assertTrue(s.startswith("python -m arch_quality"))
        self.assertIn("--metrics", s)


class TestServer(unittest.TestCase):
    """Flask 路由验证（test_client）。"""

    @classmethod
    def setUpClass(cls):
        from arch_quality.ui import server
        cls.server = server
        server.app.config["TESTING"] = True
        cls.client = server.app.test_client()
        # 隔离历史文件
        cls._orig_history_file = server.HISTORY_FILE
        server.HISTORY_FILE = server.HISTORY_DIR / "ui-history-test.json"
        if server.HISTORY_FILE.exists():
            server.HISTORY_FILE.unlink()

    @classmethod
    def tearDownClass(cls):
        if cls.server.HISTORY_FILE.exists():
            cls.server.HISTORY_FILE.unlink()
        cls.server.HISTORY_FILE = cls._orig_history_file

    def test_index_serves_html(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"arch-quality", res.data)

    def test_api_commands(self):
        res = self.client.get("/api/commands")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("order", data)
        self.assertIn("commands", data)
        self.assertIn("comprehensive", data["commands"])

    def test_history_crud(self):
        # 初始为空
        res = self.client.get("/api/history")
        self.assertEqual(res.get_json(), [])

        # 保存
        res = self.client.post("/api/history", json={
            "command": "comprehensive", "values": {"root": "D:/proj", "json": True},
            "name": "测试组合",
        })
        self.assertEqual(res.status_code, 200)
        hid = res.get_json()["id"]

        # 列表
        res = self.client.get("/api/history")
        items = res.get_json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["label"], "测试组合")
        self.assertEqual(items[0]["values"]["root"], "D:/proj")

        # 删除
        res = self.client.delete(f"/api/history/{hid}")
        self.assertEqual(res.status_code, 200)
        res = self.client.get("/api/history")
        self.assertEqual(res.get_json(), [])

    def test_history_unknown_command_rejected(self):
        res = self.client.post("/api/history", json={
            "command": "bogus", "values": {}, "name": "x",
        })
        self.assertEqual(res.status_code, 400)

    def test_run_requires_valid_root(self):
        res = self.client.post("/api/run", json={
            "command": "comprehensive", "values": {"root": "C:/definitely-not-exist-xyz"},
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.get_json())

    def test_run_mutex_rejected(self):
        res = self.client.post("/api/run", json={
            "command": "multilang", "values": {"root": ".", "full": True, "mlr_only": True},
        })
        self.assertEqual(res.status_code, 400)

    def test_run_unknown_command(self):
        res = self.client.post("/api/run", json={"command": "nope", "values": {}})
        self.assertEqual(res.status_code, 400)

    def test_run_starts_and_reports_status(self):
        # 用 standard + --metrics 对仓库自身做轻量验证（根目录存在）
        root = os.path.join(os.path.dirname(__file__), "..")
        with mock.patch.object(self.server.runner, "start") as m_start:
            m_start.return_value = "testrun123"
            res = self.client.post("/api/run", json={
                "command": "standard",
                "values": {"root": os.path.abspath(root), "metrics": True},
            })
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.get_json()["run_id"], "testrun123")
            # 验证构造的命令含 python -m 与 --metrics
            cmd = res.get_json()["command"]
            self.assertIn("arch_metrics_standard", cmd)
            self.assertIn("--metrics", cmd)

    def test_run_status_unknown(self):
        res = self.client.get("/api/runs/nonexistent")
        self.assertEqual(res.status_code, 404)

    def test_browse_existing_dir(self):
        res = self.client.post("/api/browse", json={"path": os.path.dirname(__file__)})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("entries", data)

    def test_browse_returns_absolute_paths(self):
        # 相对路径 "." 应规范化为绝对路径，条目路径也应绝对
        res = self.client.post("/api/browse", json={"path": "."})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(os.path.isabs(data["path"]), f"path 应为绝对路径: {data['path']}")
        for e in data["entries"]:
            self.assertTrue(os.path.isabs(e["path"]), f"entry path 应为绝对路径: {e['path']}")

    def test_browse_missing_dir(self):
        res = self.client.post("/api/browse", json={"path": "C:/nope-xyz"})
        self.assertEqual(res.status_code, 400)


class TestEnhancementSections(unittest.TestCase):
    """ReportGenerator 增强引擎章节渲染（profile 子集正确性）。"""

    def _make_data(self, active_enh: dict):
        """构造只含给定增强引擎的综合报告数据。"""
        struct = {
            "score": 60.0,
            "weight": 0.3,
            "sub_scores": {"modularity": 60.0, "coupling": 60.0},
        }
        for key, details in active_enh.items():
            struct[key] = {"score": 80.0, "weight_applied": 0.10, "details": details}
        return {
            "project": "t",
            "overall_score": 60.0,
            "dimensions": {
                "structural": struct,
                "design": {"score": 60.0},
                "documentation": {"score": 60.0},
                "evolution": {"score": 60.0},
            },
            "is_single_language": True,
            "project_languages": ["python"],
            "mlr_violations": [],
        }

    def _render(self, data):
        from arch_quality.arch_report_generator import ReportGenerator
        gen = ReportGenerator.__new__(ReportGenerator)  # 绕过 __init__
        gen.m = data
        return gen._enhancement_sections()

    def test_numerical_only(self):
        data = self._make_data({
            "numerical_enhancement": {
                "numerical_stability": {"score": 100.0, "detail": {}},
                "roundoff_sensitivity": {"score": 80.0, "detail": {}},
                "mms_verification": {"score": 90.0, "detail": {}},
                "error_estimation": {"score": 85.0, "detail": {}},
                "regression_coverage": {"score": 70.0, "detail": {}},
                "numerical_debt": {"score": 95.0, "detail": {}},
            },
        })
        md = self._render(data)
        self.assertIn("数值精度增强评估", md)
        self.assertIn("数值稳定性保障", md)
        self.assertIn("数值债务密度", md)
        self.assertNotIn("模板元编程增强评估", md)
        self.assertNotIn("求解器物理场增强评估", md)
        self.assertNotIn("几何一致性增强评估", md)

    def test_missing_details_skipped(self):
        # 增强引擎无 details（未激活）时应跳过
        data = self._make_data({})
        md = self._render(data)
        self.assertEqual(md.strip(), "")

    def test_all_enhancement_titles(self):
        data = self._make_data({
            "numerical_enhancement": {"mms_verification": {"score": 90.0, "detail": {}}},
            "template_enhancement": {"compile_time_fanin": {"score": 90.0, "detail": {}}},
            "solver_physics_enhancement": {"boundary_integrity": {"score": 90.0, "detail": {}}},
            "geometry_consistency_enhancement": {"geometry_kernel_consistency": {"score": 90.0, "detail": {}}},
        })
        md = self._render(data)
        self.assertIn("数值精度增强评估", md)
        self.assertIn("模板元编程增强评估", md)
        self.assertIn("求解器物理场增强评估", md)
        self.assertIn("几何一致性增强评估", md)


class TestRuleCoverageMatrix(unittest.TestCase):
    """规则覆盖矩阵的语义定位（方案 B：自评正文 / 他评附录）。"""

    def _render(self, root):
        from arch_quality.arch_report_generator import ReportGenerator
        data = {
            "project": "x", "overall_score": 60.0,
            "dimensions": {
                "structural": {"score": 60.0, "sub_scores": {}},
                "design": {"score": 60.0}, "documentation": {"score": 60.0},
                "evolution": {"score": 60.0},
            },
            "is_single_language": True, "project_languages": ["python"],
            "mlr_violations": [], "files": {"files_detail": []},
        }
        gen = ReportGenerator.__new__(ReportGenerator)
        gen.m = data
        gen.root = root
        gen._god_files = {}
        gen._god_files_prev = {}
        return gen

    def test_self_assessment_keeps_body_title(self):
        from arch_quality.arch_report_generator import ReportGenerator
        tool_root = ReportGenerator._tool_repo_root()
        gen = self._render(tool_root)
        md = gen._rule_coverage_matrix()
        self.assertTrue(gen._is_self_assessment())
        self.assertTrue(md.startswith("## 规则覆盖矩阵"))
        self.assertNotIn("工具声明", md)

    def test_third_party_moves_to_appendix(self):
        gen = self._render("D:/some-unrelated-project")
        md = gen._rule_coverage_matrix()
        self.assertFalse(gen._is_self_assessment())
        self.assertTrue(md.startswith("## 附录：工具规则覆盖声明"))
        self.assertIn("工具声明", md)
        self.assertIn("与本次评估对象", md)
        self.assertIn("无关", md)

    def test_self_detection(self):
        from arch_quality.arch_report_generator import ReportGenerator
        gen = ReportGenerator.__new__(ReportGenerator)
        gen.root = ReportGenerator._tool_repo_root()
        self.assertTrue(gen._is_self_assessment())
        gen.root = "D:/elsewhere"
        self.assertFalse(gen._is_self_assessment())


if __name__ == "__main__":
    unittest.main()