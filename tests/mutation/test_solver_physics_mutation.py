"""
求解器和物理场模块化架构评估变异测试（Mutation Testing）

通过故意在良好多物理场项目中引入缺陷，验证工具能否正确检出。

每个变异案例在合成项目上执行以下流程：
  1. 复制 good_multiphysics 到临时目录
  2. 运行工具 → 记录基线评分
  3. 应用变异（修改/删除/新增文件）
  4. 运行工具 → 记录变异后评分
  5. 清理临时目录
  6. 断言评分下降 / MPR 触发
"""

import os
import sys
import json
import shutil
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from arch_quality.arch_metrics_solver_physics import SolverPhysicsMetrics

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
GOOD_PROJECT = os.path.join(TEST_DIR, 'projects', 'good_multiphysics')
CASES_FILE = os.path.join(TEST_DIR, 'mutation_cases_sp.json')


def load_cases():
    with open(CASES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_tool(project_root):
    """在指定项目上运行求解器物理场评估工具"""
    m = SolverPhysicsMetrics(project_root)
    return m.all_metrics()


def apply_mutation(project_dir, case):
    """对项目目录中的目标文件应用变异"""
    for mutation in case['mutations']:
        action = mutation.get('action', 'replace')
        original = mutation.get('original', '')
        mutated = mutation.get('mutated', '')

        if action == 'delete_file':
            # 删除指定文件
            target_rel = original
            target_abs = os.path.join(project_dir, target_rel)
            if os.path.exists(target_abs):
                os.remove(target_abs)
            else:
                # 尝试查找匹配文件
                for root, dirs, files in os.walk(project_dir):
                    if original in files:
                        os.remove(os.path.join(root, original))
                        break
                else:
                    raise AssertionError(
                        f'变异失败 [delete_file]: 找不到文件 {target_rel}'
                    )
            continue

        if action == 'delete_dir':
            # 删除整个目录
            target_abs = os.path.join(project_dir, original)
            if os.path.isdir(target_abs):
                shutil.rmtree(target_abs)
            else:
                raise AssertionError(
                    f'变异失败 [delete_dir]: 找不到目录 {original}'
                )
            continue

        if action == 'add_file':
            # 新增文件：mutated 格式为 "路径:内容"
            path, _, content = mutated.partition(':')
            full = os.path.join(project_dir, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'w', encoding='utf-8') as f:
                f.write(content)
            continue

        if action == 'delete_block':
            # 删除文本块
            target_rel = mutation.get('target_file', case['target_file'])
            target_abs = os.path.join(project_dir, target_rel)
            if not os.path.exists(target_abs):
                raise AssertionError(f'目标文件不存在: {target_rel}')
            with open(target_abs, 'r', encoding='utf-8') as f:
                content = f.read()
            if original not in content:
                raise AssertionError(
                    f'变异失败 [delete_block]: 找不到文本块\n'
                    f'  文件: {target_rel}\n'
                    f'  块前40字: {original[:40]}'
                )
            content = content.replace(original, '', 1)
            with open(target_abs, 'w', encoding='utf-8') as f:
                f.write(content)
            continue

        if action == 'replace_block':
            # 替换整个文本块
            target_rel = mutation.get('target_file', case['target_file'])
            target_abs = os.path.join(project_dir, target_rel)
            if not os.path.exists(target_abs):
                raise AssertionError(f'目标文件不存在: {target_rel}')
            with open(target_abs, 'r', encoding='utf-8') as f:
                content = f.read()
            if original not in content:
                raise AssertionError(
                    f'变异失败 [replace_block]: 找不到文本块\n'
                    f'  文件: {target_rel}\n'
                    f'  块前40字: {original[:40]}'
                )
            content = content.replace(original, mutated, 1)
            with open(target_abs, 'w', encoding='utf-8') as f:
                f.write(content)
            continue

        raise AssertionError(f'未知变异操作: {action}')


def load_expected(case):
    """加载预期结果，合并默认值"""
    exp = dict(case.get('expected', {}))
    exp.setdefault('mpr_rules_changed', [])
    exp.setdefault('overall_change', None)
    return exp


@pytest.mark.parametrize(
    'case',
    load_cases(),
    ids=[c['id'] + '-' + c['name'] for c in load_cases()]
)
def test_mutation(case):
    """变异测试：在良好项目上引入缺陷，验证工具能检出"""
    # ── 1. 复制 good_multiphysics 到临时目录 ──
    tmp_dir = tempfile.mkdtemp(prefix=f'mutsp_{case["id"]}_')
    try:
        shutil.copytree(GOOD_PROJECT, tmp_dir, dirs_exist_ok=True)

        # ── 2. 运行工具 → 基线评分 ──
        baseline = run_tool(tmp_dir)

        # ── 3. 应用变异 ──
        apply_mutation(tmp_dir, case)

        # ── 4. 运行工具 → 变异后评分 ──
        mutated = run_tool(tmp_dir)

        # ── 5. 清理 ──
        shutil.rmtree(tmp_dir, ignore_errors=True)

        # ── 6. 断言 ──
        expected = load_expected(case)

        # 6a. 综合评分变化
        if expected.get('overall_change') and expected['overall_change'] != 'no_assert':
            assert mutated['overall'] < baseline['overall'], (
                f'{case["id"]}: 综合评分未下降 '
                f'(基线={baseline["overall"]:.2f}, 变异后={mutated["overall"]:.2f})'
            )

        # 6b. MPR 违规变化
        baseline_rules = set(v['rule'] for v in baseline.get('mpr_violations', []))
        mutated_rules = set(v['rule'] for v in mutated.get('mpr_violations', []))
        new_rules = mutated_rules - baseline_rules

        expected_new = set(expected.get('mpr_rules_changed', []))
        for rule in expected_new:
            assert rule in new_rules or rule in mutated_rules, (
                f'{case["id"]}: 预期 MPR {rule} 应触发或新增，但未检测到\n'
                f'  基线规则: {baseline_rules}\n'
                f'  变异后规则: {mutated_rules}'
            )

        # 6c. 维度评分变化
        dim_change = expected.get('dimension_change', {})
        for dim, change_type in dim_change.items():
            b_score = baseline.get('dimensions', {}).get(dim, {}).get('score')
            m_score = mutated.get('dimensions', {}).get(dim, {}).get('score')
            if change_type == 'drop_to_zero':
                assert b_score is not None and b_score > 0, (
                    f'{case["id"]}/{dim}: 基线评分应 > 0, 实际={b_score}'
                )
                assert m_score is not None and m_score < b_score, (
                    f'{case["id"]}/{dim}: 变异后评分应下降, '
                    f'(基线={b_score}, 变异后={m_score})'
                )
            elif change_type == 'decrease':
                assert b_score is not None and m_score is not None, (
                    f'{case["id"]}/{dim}: 评分不应为 None '
                    f'(基线={b_score}, 变异后={m_score})'
                )
                assert m_score < b_score, (
                    f'{case["id"]}/{dim}: 变异后评分应下降, '
                    f'(基线={b_score}, 变异后={m_score})'
                )

        # 输出摘要
        print(f'  {case["id"]}: 基线={baseline["overall"]:.2f} → '
              f'变异后={mutated["overall"]:.2f} '
              f'规则: {baseline_rules} → {mutated_rules} ✅', flush=True)

    except Exception as e:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        raise e
