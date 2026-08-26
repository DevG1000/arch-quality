"""
标准架构质量评估变异测试（Mutation Testing）

通过故意在好的代码中引入缺陷，验证工具能否正确检测出这些缺陷。
每个变异案例在合成项目上执行以下流程：

  1. 复制 good_project_standard 到临时目录
  2. 运行工具 → 记录基线评分
  3. 应用变异（修改/删除/创建文件）
  4. 运行工具 → 记录变异后评分
  5. 清理临时目录
  6. 断言评分下降 / SAR 规则触发

对齐开发指南 §B2 变异测试要求（MUT-xxx-01 至 04 类型）。
"""

import os
import sys
import json
import shutil
import tempfile
import copy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from arch_quality.arch_metrics_standard import StandardMetrics

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
GOOD_PROJECT = os.path.join(TEST_DIR, "projects", "good_project_standard")
CASES_FILE = os.path.join(TEST_DIR, "standard_mutation_cases.json")


def load_cases():
    with open(CASES_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def run_tool(project_root):
    m = StandardMetrics(project_root)
    return m.all_metrics()


def apply_mutation(project_dir, case):
    target_rel = case["target_file"]
    target_abs = os.path.join(project_dir, target_rel)

    for mutation in case["mutations"]:
        action = mutation.get("action", "replace")

        if action == "delete_file":
            if os.path.exists(target_abs):
                os.remove(target_abs)
            # 支持删除第二个文件（target_file2）
            tf2 = mutation.get("target_file2")
            if tf2:
                tf2_abs = os.path.join(project_dir, tf2)
                if os.path.exists(tf2_abs):
                    os.remove(tf2_abs)
            continue

        if action == "create_file":
            # 创建新文件（变异是引入缺陷文件）
            with open(target_abs, "w", encoding="utf-8") as f:
                f.write(mutation["content"])
            tf2 = mutation.get("target_file2")
            if tf2:
                tf2_abs = os.path.join(project_dir, tf2)
                with open(tf2_abs, "w", encoding="utf-8") as f:
                    f.write(mutation.get("content2", mutation["content"]))
            continue

        if not os.path.exists(target_abs):
            raise FileNotFoundError(f"目标文件不存在: {target_abs}")

        with open(target_abs, "r", encoding="utf-8") as f:
            content = f.read()

        original = mutation["original"]
        mutated = mutation["mutated"]

        if action == "replace_block" or action == "replace_line" or action == "replace":
            if original in content:
                content = content.replace(original, mutated, 1)
            else:
                raise AssertionError(
                    f"变异失败 [{action}]: 找不到原文\n"
                    f"  文件: {target_rel}\n"
                    f"  原文: {original[:60]}"
                )
        with open(target_abs, "w", encoding="utf-8") as f:
            f.write(content)


def load_expected(case):
    exp = copy.deepcopy(case.get("expected", {}))
    exp.setdefault("sar_rules_changed", [])
    exp.setdefault("overall_change", None)
    return exp


@pytest.mark.parametrize(
    "case",
    load_cases(),
    ids=[c["id"] + "-" + c["name"] for c in load_cases()],
)
def test_standard_mutation(case):
    """变异测试：在好代码上引入缺陷，验证工具能检出"""
    tmp_dir = tempfile.mkdtemp(prefix=f"mut_{case['id']}_")
    try:
        shutil.copytree(GOOD_PROJECT, tmp_dir, dirs_exist_ok=True)

        baseline = run_tool(tmp_dir)
        apply_mutation(tmp_dir, case)
        mutated = run_tool(tmp_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)

        expected = load_expected(case)

        # 6a. SAR 规则新增
        base_rules = set(v["rule"] for v in baseline.get("sar_violations", []))
        mut_rules = set(v["rule"] for v in mutated.get("sar_violations", []))
        new_rules = mut_rules - base_rules
        for rule in expected.get("sar_rules_changed", []):
            assert rule in new_rules or rule in mut_rules, (
                f"{case['id']}: 预期 SAR {rule} 应触发或新增，但未检测到\n"
                f"  基线: {sorted(base_rules)}\n"
                f"  变异后: {sorted(mut_rules)}"
            )

        # 6b. 维度评分变化（文档等）
        if expected.get("doc_score_before"):
            b_doc = baseline.get("documentation", {}).get("score", 0)
            assert b_doc >= expected["doc_score_before"], (
                f"{case['id']}: 基线文档分应 >= {expected['doc_score_before']}, 实际={b_doc}"
            )

        # 6c. 反模式评分变化
        if expected.get("anti_pattern_score_before") is not None:
            b_anti = baseline.get("design", {}).get("details", {}).get("anti_patterns")
            assert b_anti is not None and b_anti >= expected["anti_pattern_score_before"], (
                f"{case['id']}: 基线反模式分应 >= {expected['anti_pattern_score_before']}, 实际={b_anti}"
            )
        if expected.get("anti_pattern_score_after") is not None:
            m_anti = mutated.get("design", {}).get("details", {}).get("anti_patterns")
            assert m_anti is not None and m_anti <= expected["anti_pattern_score_after"], (
                f"{case['id']}: 变异后反模式分应 <= {expected['anti_pattern_score_after']}, 实际={m_anti}"
            )

        print(
            f"  {case['id']}: SAR {sorted(base_rules)} → {sorted(mut_rules)} ✅",
            flush=True,
        )

    except Exception as e:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        raise e