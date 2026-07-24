"""
数值精度评估变异测试（Mutation Testing）

通过故意在好的代码中引入缺陷，验证工具能否正确检测出这些缺陷。
每个变异案例在合成项目上执行以下流程：

  1. 复制 good_project 到临时目录
  2. 运行工具 → 记录基线评分
  3. 应用变异（修改/删除文件）
  4. 运行工具 → 记录变异后评分
  5. 清理临时目录
  6. 断言评分下降 / NVR 触发
"""

import os, sys, json, shutil, tempfile, copy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from arch_quality.arch_metrics_numerical_accuracy import NumericalAccuracyMetrics

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
GOOD_PROJECT = os.path.join(TEST_DIR, 'projects', 'good_project')
CASES_FILE = os.path.join(TEST_DIR, 'mutation_cases.json')


def load_cases():
    with open(CASES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_tool(project_root):
    """在指定项目上运行数值精度评估工具"""
    m = NumericalAccuracyMetrics(project_root)
    return m.all_metrics()


def apply_mutation(project_dir, case):
    """对项目目录中的目标文件应用变异"""
    target_rel = case['target_file']
    target_abs = os.path.join(project_dir, target_rel)

    if not os.path.exists(target_abs):
        raise FileNotFoundError(f'目标文件不存在: {target_abs}')

    for mutation in case['mutations']:
        action = mutation.get('action', 'replace')

        if action == 'delete_file':
            os.remove(target_abs)
            continue

        with open(target_abs, 'r', encoding='utf-8') as f:
            content = f.read()

        original = mutation['original']
        mutated = mutation['mutated']

        if action == 'delete_line':
            # 删除整行（含换行符）
            line_to_delete = original
            if line_to_delete in content:
                # 尝试匹配整行（可能前有空格，后有换行）
                import re
                # 转义并匹配整行
                escaped = re.escape(line_to_delete)
                content = re.sub(escaped + r'\s*\n', '', content, count=1)
                with open(target_abs, 'w', encoding='utf-8') as f:
                    f.write(content)
                continue
            else:
                raise AssertionError(
                    f'变异失败 [delete_line]: 找不到行\n'
                    f'  文件: {target_rel}\n'
                    f'  行: {line_to_delete[:60]}'
                )

        elif action == 'replace_block':
            # 替换整个代码块
            if original in content:
                content = content.replace(original, mutated, 1)
                with open(target_abs, 'w', encoding='utf-8') as f:
                    f.write(content)
                continue
            else:
                raise AssertionError(
                    f'变异失败 [replace_block]: 找不到原文块\n'
                    f'  文件: {target_rel}\n'
                    f'  原文块前50字: {original[:50]}'
                )

        elif action == 'replace_line':
            # 替换单行
            if original in content:
                content = content.replace(original, mutated, 1)
                with open(target_abs, 'w', encoding='utf-8') as f:
                    f.write(content)
                continue
            else:
                raise AssertionError(
                    f'变异失败 [replace_line]: 找不到原文\n'
                    f'  文件: {target_rel}\n'
                    f'  原文: {original[:60]}'
                )

        # 默认 replace 操作
        count = content.count(original)
        if count == 0:
            raise AssertionError(
                f'变异失败: 找不到原文\n'
                f'  文件: {target_rel}\n'
                f'  原文: {original[:60]}...'
            )
        content = content.replace(original, mutated, 1)
        with open(target_abs, 'w', encoding='utf-8') as f:
            f.write(content)


def load_expected(case):
    """加载预期结果，合并默认值"""
    exp = copy.deepcopy(case.get('expected', {}))
    exp.setdefault('nvr_rules_changed', [])
    exp.setdefault('overall_change',None)
    return exp


@pytest.mark.parametrize(
    'case',
    load_cases(),
    ids=[c['id'] + '-' + c['name'] for c in load_cases()]
)
def test_mutation(case):
    """变异测试：在好代码上引入缺陷，验证工具能检出"""
    # ── 1. 复制 good_project 到临时目录 ──
    tmp_dir = tempfile.mkdtemp(prefix=f'mut_{case["id"]}_')
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

        # 6b. NVR 违规变化
        baseline_rules = set(v['rule'] for v in baseline.get('nvr_violations', []))
        mutated_rules = set(v['rule'] for v in mutated.get('nvr_violations', []))
        new_rules = mutated_rules - baseline_rules

        expected_new = set(expected.get('nvr_rules_changed', []))
        for rule in expected_new:
            assert rule in new_rules or rule in mutated_rules, (
                f'{case["id"]}: 预期 NVR {rule} 应触发或新增，但未检测到\n'
                f'  基线规则: {baseline_rules}\n'
                f'  变异后规则: {mutated_rules}'
            )

        # 6c. 维度评分变化
        for dim, max_score in expected.get('dimension_before_max', {}).items():
            dim_before = baseline.get('dimensions', {}).get(dim, {}).get('score')
            if dim_before is not None:
                assert dim_before >= max_score, (
                    f'{case["id"]}/{dim}: 基线评分应 >= {max_score}, 实际={dim_before}'
                )

        for dim, min_score in expected.get('dimension_after_min', {}).items():
            dim_after = mutated.get('dimensions', {}).get(dim, {}).get('score')
            if dim_after is not None:
                assert dim_after <= min_score, (
                    f'{case["id"]}/{dim}: 变异后评分应 <= {min_score}, 实际={dim_after}'
                )

        # 6d. 相消计数增加（MUT-006 专用）
        if expected.get('cancellation_count_increase'):
            def get_nvr003_count(result):
                for v in result.get('nvr_violations', []):
                    if v['rule'] == 'NVR-003':
                        return v.get('count', 0)
                return 0
            b_cnt = get_nvr003_count(baseline)
            m_cnt = get_nvr003_count(mutated)
            assert m_cnt > b_cnt, (
                f'{case["id"]}: 相消计数应增加 '
                f'(基线={b_cnt}, 变异后={m_cnt})'
            )

        # 6e. 维度变化（如 "drop_to_zero"）
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

        # 输出摘要
        print(f'  {case["id"]}: 基线={baseline["overall"]:.2f} → 变异后={mutated["overall"]:.2f} '
              f'规则: {baseline_rules} → {mutated_rules} ✅', flush=True)

    except Exception as e:
        # 确保清理
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        raise e
