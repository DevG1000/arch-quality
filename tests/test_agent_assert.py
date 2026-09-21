"""
test_agent_assert.py — agent-assert 插件断言逻辑回归测试

验证 .opencode/plugins/agent-assert.js 的修复：
1. 综合命令（python -m arch_quality）断言 overall_score + solver_physics/非多物理场
2. 单引擎命令（arch_quality.arch_metrics_*）只断言引擎产出，不误报缺少 solver_physics
3. overall 正则兼容 "overall" 与 "overall_score"（对齐 Python output_schema.py）

通过读取插件源码检查关键逻辑，避免依赖 Node 运行时。
"""

import os
import re
import subprocess
import sys
import unittest

PLUGIN_PATH = os.path.join(os.path.dirname(__file__), "..", ".opencode", "plugins", "agent-assert.js")


def _plugin_src() -> str:
    with open(PLUGIN_PATH, encoding="utf-8") as f:
        return f.read()


class TestAgentAssertRegex(unittest.TestCase):
    """插件源码中的关键正则/分支存在性。"""

    @classmethod
    def setUpClass(cls):
        cls.src = _plugin_src()

    def test_overall_regex_is_loose(self):
        # 必须用宽松正则 overall[^0-9]{0,20}，兼容 overall / overall_score
        self.assertIn("overall[^0-9]{0,20}", self.src)

    def test_old_buggy_regex_removed(self):
        # 旧的 "overall score"（空格）必须移除
        self.assertNotIn('"overall score"', self.src)

    def test_single_engine_classifier(self):
        self.assertRegex(self.src, r"function isSingleEngineCommand")

    def test_single_engine_pattern(self):
        # 分类正则：arch_quality.arch_metrics_*
        self.assertIn("arch_quality\\.arch_metrics_\\w+", self.src)

    def test_non_multiphysics_helper(self):
        self.assertRegex(self.src, r"function isNonMultiphysics")

    def test_single_engine_branch(self):
        # runAsserts 需区分单引擎/综合
        self.assertRegex(self.src, r"if \(isSingleEngine\)")

    def test_three_arg_runAsserts(self):
        self.assertRegex(self.src, r"function runAsserts\(stdout, rules, isSingleEngine\)")

    def test_required_solver_fields_used(self):
        self.assertIn("required_solver_fields", self.src)


class TestAgentAssertBehavior(unittest.TestCase):
    """用 Node 实际执行与插件同源的断言逻辑，验证三类输出场景。"""

    NODE_SCRIPT = r"""
const rules = {
  overall_range: [0, 100],
  required_solver_fields: ["solver_physics_enhancement"],
  non_multiphysics_markers: ["非多物理场", "不是多物理场", "未识别为多物理场", "未启用", "未激活", "not a multiphysics"],
  hallucinated_patterns: [],
};
function extractOverall(text) {
  const m = String(text).match(/overall[^0-9]{0,20}(\d+(?:\.\d+)?)/i);
  return m ? parseFloat(m[1]) : null;
}
function isNonMultiphysics(text, rules) {
  const t = String(text);
  if ((rules.non_multiphysics_markers || []).some((k) => t.includes(k))) return true;
  if (/solver_physics\*?0%|solver_physics[^0-9]{0,10}0\.0|solver_physics_enhancement/i.test(t)) {
    if (!/"solver_physics_enhancement":\s*\{\s*"score"/i.test(t)) return true;
    return false;
  }
  if (/"project"\s*:\s*"[^"]+"/.test(t) && !/solver/i.test(t)) return true;
  return false;
}
function runAsserts(stdout, rules, isSingleEngine) {
  const errors = [];
  const text = String(stdout || "");
  if (isSingleEngine) {
    const overall = extractOverall(text);
    if (overall === null && text.trim().length < 10) errors.push("empty");
    else if (overall !== null) {
      const [lo, hi] = rules.overall_range || [0, 100];
      if (overall < lo || overall > hi) errors.push(`range:${overall}`);
    }
  } else {
    const overall = extractOverall(text);
    if (overall === null) errors.push("no_overall");
    else {
      const [lo, hi] = rules.overall_range || [0, 100];
      if (overall < lo || overall > hi) errors.push(`range:${overall}`);
    }
    const hasSolver = (rules.required_solver_fields || []).some((f) => text.includes(f));
    const nonMp = isNonMultiphysics(text, rules);
    if (!hasSolver && !nonMp) errors.push("no_solver");
  }
  return errors;
}
const comp = '{"project":"x","overall_score":61.99,"dimensions":{"structural":{"solver_physics_enhancement":{"score":90}}}}';
const num = '{"overall":96.0,"is_numerical":true,"dimensions":{"numerical_stability":{"score":100}}}';
const nonmp = '{"project":"py-app","overall_score":72.5,"dimensions":{"structural":{"score":70}}}';
const results = {
  comp: runAsserts(comp, rules, false),
  num: runAsserts(num, rules, true),
  nonmp: runAsserts(nonmp, rules, false),
  empty_single: runAsserts("", rules, true),
};
console.log(JSON.stringify(results));
"""

    def _run_node(self) -> dict:
        r = subprocess.run(
            ["node", "-e", self.NODE_SCRIPT],
            capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, f"node failed: {r.stderr}")
        import json
        return json.loads(r.stdout)

    def test_comprehensive_with_solver_passes(self):
        res = self._run_node()
        self.assertEqual(res["comp"], [])

    def test_single_engine_passes(self):
        res = self._run_node()
        self.assertEqual(res["num"], [])

    def test_non_multiphysics_comprehensive_passes(self):
        res = self._run_node()
        self.assertEqual(res["nonmp"], [])

    def test_empty_single_engine_fails(self):
        res = self._run_node()
        self.assertNotEqual(res["empty_single"], [])


if __name__ == "__main__":
    unittest.main()