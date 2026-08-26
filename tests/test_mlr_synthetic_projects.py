"""
test_mlr_synthetic_projects.py — WP-2 规则回归补全：合成项目单元测试

验证 3 个此前无真实项目覆盖的 MLR 规则：
- MLR-002 绑定层接口缺失（mlr002_no_binding 正例 / mlr002_with_binding 负例）
- MLR-007 TNT 模块（影响半径超标，mlr007_tnt）
- MLR-009 绑定层使用通用类型（mlr009_generic）

对齐 H1 计划 WP-2：合成项目内置正/负例，真实优先、合成兜底。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from arch_quality.arch_metrics_multilang import MultilangMetrics
from arch_quality.arch_metrics_solver_physics import SolverPhysicsMetrics

PROJECTS = os.path.join(os.path.dirname(__file__), "mutation", "projects")


class TestMlr002BindingMissing(unittest.TestCase):
    """MLR-002 绑定层接口缺失"""

    def test_no_binding_triggers(self):
        m = MultilangMetrics(os.path.join(PROJECTS, "mlr002_no_binding"))
        d = m.all_metrics()
        mlr002 = [v for v in d["mlr_violations"] if v["rule"] == "MLR-002"]
        self.assertEqual(len(mlr002), 1)
        self.assertEqual(mlr002[0]["severity"], "HIGH")
        self.assertGreaterEqual(mlr002[0]["count"], 2)

    def test_with_binding_no_trigger(self):
        m = MultilangMetrics(os.path.join(PROJECTS, "mlr002_with_binding"))
        d = m.all_metrics()
        mlr002 = [v for v in d["mlr_violations"] if v["rule"] == "MLR-002"]
        self.assertEqual(len(mlr002), 0)


class TestMlr007TntModule(unittest.TestCase):
    """MLR-007 TNT 模块（影响半径超标）"""

    def test_deep_chain_triggers(self):
        m = MultilangMetrics(os.path.join(PROJECTS, "mlr007_tnt"))
        d = m.all_metrics()
        mlr007 = [v for v in d["mlr_violations"] if v["rule"] == "MLR-007"]
        self.assertEqual(len(mlr007), 1)
        self.assertEqual(mlr007[0]["severity"], "MEDIUM")
        # 影响半径详情应含 radius > 30 的模块
        radii = d["dimensions"].get("impact_radius", {}).get("detail", {})
        big = [v for v in radii.values()
               if isinstance(v, dict) and v.get("radius", 0) > 30]
        self.assertGreaterEqual(len(big), 1)


class TestMlr009GenericBinding(unittest.TestCase):
    """MLR-009 绑定层使用通用类型"""

    def test_ctypes_generic_triggers(self):
        m = MultilangMetrics(os.path.join(PROJECTS, "mlr009_generic"))
        d = m.all_metrics()
        mlr009 = [v for v in d["mlr_violations"] if v["rule"] == "MLR-009"]
        self.assertGreaterEqual(len(mlr009), 1)
        for v in mlr009:
            self.assertIn("c_void_p", v["detail"])


class TestMpr004ArchitectureMismatch(unittest.TestCase):
    """MPR-004 耦合架构模式判定（此前完全未覆盖）"""

    def test_strong_loose_mismatch_triggers(self):
        m = SolverPhysicsMetrics(os.path.join(PROJECTS, "mpr004_mismatch"))
        d = m.all_metrics()
        mpr004 = [v for v in d.get("mpr_violations", []) if v["rule"] == "MPR-004"]
        self.assertEqual(len(mpr004), 1)
        self.assertEqual(mpr004[0]["severity"], "MEDIUM")
        self.assertIn("不匹配", mpr004[0]["detail"])


class TestMlr011LoopCalls(unittest.TestCase):
    """MLR-011 小数据频繁跨语言传输（循环内 ctypes 调用）"""

    def test_loop_ctypes_triggers(self):
        m = MultilangMetrics(os.path.join(PROJECTS, "mlr011_loop_calls"))
        d = m.all_metrics()
        mlr011 = [v for v in d["mlr_violations"] if v["rule"] == "MLR-011"]
        self.assertGreaterEqual(len(mlr011), 1)
        self.assertEqual(mlr011[0]["severity"], "LOW")
        self.assertIn("循环内", mlr011[0]["detail"])


if __name__ == "__main__":
    unittest.main()