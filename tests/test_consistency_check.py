# -*- coding: utf-8 -*-
"""WP-6 通用一致性检查器测试"""

import os
import subprocess
import sys
import unittest

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(PROJECT, "scripts", "consistency_check.py")


def run_check(engine="all"):
    cmd = [sys.executable, SCRIPT]
    if engine != "all":
        cmd += ["--engine", engine]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return r


class TestConsistencyCheck(unittest.TestCase):
    def test_all_engines_pass(self):
        """5 引擎全 PASS，退出码 0"""
        r = run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for eng in ["standard", "multilang", "template", "numerical", "solver_physics"]:
            self.assertIn(f"=> {eng}: PASS", r.stdout)

    def test_engine_filter(self):
        """--engine 过滤器只检查指定引擎"""
        r = run_check("numerical")
        self.assertEqual(r.returncode, 0)
        self.assertIn("=> numerical: PASS", r.stdout)
        self.assertNotIn("=> standard: PASS", r.stdout)

    def test_known_holes_info(self):
        """已知空洞（NVR-009/MPR-011）为 INFO 不 FAIL"""
        r = run_check()
        self.assertIn("NVR-009", r.stdout)
        self.assertIn("MPR-011", r.stdout)
        self.assertIn("WP-7.1", r.stdout)

    def test_rule_id_extract(self):
        """规则 ID 提取支持变体与编号"""
        import importlib.util
        spec = importlib.util.spec_from_file_location("cc", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ids = mod.extract_rule_ids("SAR-001 与 SAR-002b 和 MLR-013", "SAR")
        self.assertIn("SAR-001", ids)
        self.assertIn("SAR-002b", ids)
        self.assertNotIn("MLR-013", ids)

    def test_engines_config_complete(self):
        """5 引擎配置完整（指南/skill/tool/case 文件均存在）"""
        import importlib.util
        spec = importlib.util.spec_from_file_location("cc", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name, cfg in mod.ENGINES.items():
            for key in ("guide", "skill", "tool", "case"):
                path = cfg.get(key, "")
                if path:
                    self.assertTrue(os.path.exists(os.path.join(PROJECT, path)),
                                    f"{name}.{key} 缺失 {path}")


if __name__ == "__main__":
    unittest.main()
