"""
几何内核一致性评估变异测试（Mutation Testing，B2）

通过故意在好的几何项目（good_project_gcs）中引入缺陷，验证 GCS 引擎能检出。
每个变异案例流程：复制好项目 → 基线评分 → 应用变异 → 变异后评分 → 断言。

覆盖规则：GCS-001（闭合性缺失）/ GCS-002（裸指针穿越）/ GCS-003（IsDone 缺失）/
GCS-005（精度魔法数字）/ GCS-007（网格语义混用）/ GCS-010（裸数组密度）/ GCS-012（直接成员访问）
"""

import os, sys, json, shutil, tempfile, copy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from arch_quality.arch_metrics_geometry_consistency import GeometryConsistencyMetrics

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
GOOD_PROJECT = os.path.join(TEST_DIR, 'projects', 'good_project_gcs')
CASES_FILE = os.path.join(TEST_DIR, 'mutation_cases_gcs.json')


def load_cases():
    with open(CASES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_tool(project_root):
    m = GeometryConsistencyMetrics(project_root)
    return m.all_metrics()


def apply_mutation(project_dir, case):
    target_rel = case['target_file']
    target_abs = os.path.join(project_dir, target_rel)
    if not os.path.exists(target_abs):
        raise FileNotFoundError(f'目标文件不存在: {target_abs}')
    with open(target_abs, 'r', encoding='utf-8') as f:
        content = f.read()
    for mutation in case['mutations']:
        original = mutation['original']
        mutated = mutation['mutated']
        if original not in content:
            raise AssertionError(
                f'变异失败: 找不到原文\n  文件: {target_rel}\n  原文: {original[:60]}')
        content = content.replace(original, mutated, 1)
    with open(target_abs, 'w', encoding='utf-8') as f:
        f.write(content)


def load_expected(case):
    exp = copy.deepcopy(case.get('expected', {}))
    exp.setdefault('nvr_rules_changed', [])
    exp.setdefault('overall_change', None)
    return exp


@pytest.mark.parametrize(
    'case',
    load_cases(),
    ids=[c['id'] + '-' + c['name'] for c in load_cases()]
)
def test_mutation(case):
    tmp_dir = tempfile.mkdtemp(prefix=f'mut_{case["id"]}_')
    try:
        shutil.copytree(GOOD_PROJECT, tmp_dir, dirs_exist_ok=True)

        baseline = run_tool(tmp_dir)
        apply_mutation(tmp_dir, case)
        mutated = run_tool(tmp_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)

        expected = load_expected(case)

        # 6a. 综合评分下降
        if expected.get('overall_change') == 'drop':
            assert mutated['overall'] < baseline['overall'], (
                f'{case["id"]}: 综合评分未下降 '
                f'(基线={baseline["overall"]:.2f}, 变异后={mutated["overall"]:.2f})')

        # 6b. GCS 违规新增
        baseline_rules = set(v['rule'] for v in baseline.get('gcs_violations', []))
        mutated_rules = set(v['rule'] for v in mutated.get('gcs_violations', []))
        for rule in expected.get('nvr_rules_changed', []):
            assert rule in mutated_rules, (
                f'{case["id"]}: 预期 GCS {rule} 应触发\n'
                f'  基线规则: {baseline_rules}\n  变异后规则: {mutated_rules}')

        # 6c. 基线维度评分上界
        for dim, max_score in expected.get('dimension_before_max', {}).items():
            b = baseline.get('dimensions', {}).get(dim, {}).get('score')
            if b is not None:
                assert b >= max_score, f'{case["id"]}/{dim}: 基线应 >= {max_score}, 实际={b}'

        # 6d. 变异后维度评分下界
        for dim, min_score in expected.get('dimension_after_min', {}).items():
            m2 = mutated.get('dimensions', {}).get(dim, {}).get('score')
            if m2 is not None:
                assert m2 <= min_score, f'{case["id"]}/{dim}: 变异后应 <= {min_score}, 实际={m2}'

        print(f'  {case["id"]}: 基线={baseline["overall"]:.2f} → 变异后={mutated["overall"]:.2f} '
              f'规则: {baseline_rules} → {mutated_rules} ✅', flush=True)

    except Exception as e:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        raise e