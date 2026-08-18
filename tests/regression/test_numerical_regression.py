"""
数值精度评估外部验证回归测试

对本地可用的开源项目运行工具，将结果与已建立的基线 JSON 比对。
检测评分偏移、NVR 违规数量变化等回归问题。

性能说明：每个项目只运行一次评估，结果被缓存供所有测试方法复用。
deal.II 等大型项目（24k 文件）耗时约 800s，标注为 slow。
"""

import os, json, sys, functools
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from arch_quality.arch_metrics_numerical_accuracy import NumericalAccuracyMetrics

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), 'snapshots', 'numerical_baselines')

# 可用项目（路径与本机仓库位置绑定）
PROJECTS = {
    'MOOSE': r'D:\opensource\MOOSE',
    'deal.II': r'D:\opensource\dealii',
    'FreeFEM': r'D:\opensource\FreeFEM-sources',
    'MFEM': r'D:\opensource\mfem',
    'FEniCSx': r'D:\opensource\dolfinx',
}

# 大项目标记为 slow（单次运行 > 60s）
SLOW_PROJECTS = {'MOOSE', 'deal.II'}


def load_baseline(project_name):
    """加载已保存的基线 JSON"""
    path = os.path.join(SNAPSHOT_DIR, f'{project_name}.json')
    if not os.path.exists(path):
        pytest.skip(f'基线文件不存在: {path}')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


@functools.lru_cache(maxsize=None)
def run_assessment_cached(project_path):
    """运行工具并缓存结果（避免每个测试方法都重新运行）"""
    m = NumericalAccuracyMetrics(project_path)
    return m.all_metrics()


# ── Fixtures ──

@pytest.fixture(scope='module')
def baseline(request):
    """加载基线 JSON（模块级缓存）"""
    return load_baseline(request.param)


@pytest.fixture(scope='module')
def assessment(request):
    """运行评估并缓存结果（模块级缓存）"""
    return run_assessment_cached(request.param)


# ── 参数化数据 ──

def available_projects(include_slow=True):
    """返回可用的项目列表"""
    result = []
    for name, path in PROJECTS.items():
        if not os.path.isdir(path):
            continue
        if not include_slow and name in SLOW_PROJECTS:
            continue
        result.append((name, path))
    return result


# ── 测试类 ──

class TestNumericalRegression:
    """数值精度评估外部验证回归测试"""

    @pytest.mark.parametrize('project_name,project_path',
                             available_projects(include_slow=True),
                             ids=lambda p: p[0] if isinstance(p, tuple) else p)
    def test_overall_score_stable(self, project_name, project_path):
        """综合评分不应偏离基线超过 ±2.0"""
        baseline = load_baseline(project_name)
        result = run_assessment_cached(project_path)
        expected = baseline['overall']
        actual = result['overall']
        diff = abs(actual - expected)
        assert diff <= 2.0, (
            f'{project_name}: 综合评分偏移 {diff:.2f} '
            f'(基线={expected}, 当前={actual})'
        )

    @pytest.mark.parametrize('project_name,project_path',
                             available_projects(include_slow=True),
                             ids=lambda p: p[0] if isinstance(p, tuple) else p)
    def test_nvr_count_stable(self, project_name, project_path):
        """NVR 违规数量不应变化"""
        baseline = load_baseline(project_name)
        result = run_assessment_cached(project_path)
        expected = len(baseline.get('nvr_violations', []))
        actual = len(result.get('nvr_violations', []))
        assert actual == expected, (
            f'{project_name}: NVR 违规数量变化 '
            f'(基线={expected}, 当前={actual})'
        )

    @pytest.mark.parametrize('project_name,project_path',
                             available_projects(include_slow=True),
                             ids=lambda p: p[0] if isinstance(p, tuple) else p)
    def test_nvr_rules_unchanged(self, project_name, project_path):
        """NVR 违规的规则列表不应变化"""
        baseline = load_baseline(project_name)
        result = run_assessment_cached(project_path)
        expected_rules = sorted(v['rule'] for v in baseline.get('nvr_violations', []))
        actual_rules = sorted(v['rule'] for v in result.get('nvr_violations', []))
        assert actual_rules == expected_rules, (
            f'{project_name}: NVR 违规规则变化\n'
            f'  基线: {expected_rules}\n'
            f'  当前: {actual_rules}'
        )

    # 维度评分检测仅对小型项目运行（不含 MOOSE/deal.II）
    @pytest.mark.parametrize('project_name,project_path',
                             available_projects(include_slow=False),
                             ids=lambda p: p[0] if isinstance(p, tuple) else p)
    @pytest.mark.parametrize('dim_name', [
        'numerical_stability', 'roundoff_sensitivity',
        'mms_verification', 'error_estimation',
        'regression_coverage', 'numerical_debt',
    ])
    def test_dimension_score_stable(self, project_name, project_path, dim_name):
        """各维度评分不应偏离基线超过 ±5.0（仅小项目）"""
        baseline = load_baseline(project_name)
        result = run_assessment_cached(project_path)
        b_dim = baseline.get('dimensions', {}).get(dim_name, {})
        r_dim = result.get('dimensions', {}).get(dim_name, {})
        expected = b_dim.get('score')
        actual = r_dim.get('score')

        if expected is None and actual is None:
            return
        if expected is None or actual is None:
            pytest.fail(f'{project_name}/{dim_name}: score 从 {expected} 变为 {actual}')

        diff = abs(actual - expected)
        assert diff <= 5.0, (
            f'{project_name}/{dim_name}: 评分偏移 {diff:.1f} '
            f'(基线={expected}, 当前={actual})'
        )

    @pytest.mark.parametrize('project_name,project_path',
                             available_projects(include_slow=True),
                             ids=lambda p: p[0] if isinstance(p, tuple) else p)
    def test_nvr_severity_not_increased(self, project_name, project_path):
        """NVR 违规的 output_level 不应升级（如 WARNING→ERROR）"""
        baseline = load_baseline(project_name)
        result = run_assessment_cached(project_path)

        baseline_map = {v['rule']: v['output_level']
                        for v in baseline.get('nvr_violations', [])}
        result_map = {v['rule']: v['output_level']
                      for v in result.get('nvr_violations', [])}

        severity_order = {'INFO': 0, 'WARNING': 1, 'ERROR': 2}
        for rule, new_level in result_map.items():
            old_level = baseline_map.get(rule)
            if old_level and severity_order.get(new_level, 0) > severity_order.get(old_level, 0):
                pytest.fail(
                    f'{project_name}/{rule}: output_level 升级 '
                    f'({old_level} → {new_level}), 需要审查'
                )

    @pytest.mark.parametrize('project_name,project_path',
                             available_projects(include_slow=True),
                             ids=lambda p: p[0] if isinstance(p, tuple) else p)
    def test_cancellation_count_monitor(self, project_name, project_path):
        """NVR-003 相消数量变化超过 20% 时告警（非阻断）"""
        baseline = load_baseline(project_name)
        result = run_assessment_cached(project_path)

        b_nvr = {v['rule']: v for v in baseline.get('nvr_violations', [])}
        r_nvr = {v['rule']: v for v in result.get('nvr_violations', [])}

        if 'NVR-003' not in b_nvr and 'NVR-003' not in r_nvr:
            return

        b_cnt = b_nvr.get('NVR-003', {}).get('count', 0)
        r_cnt = r_nvr.get('NVR-003', {}).get('count', 0)

        if b_cnt > 0 and r_cnt > 0:
            change = abs(r_cnt - b_cnt) / max(b_cnt, 1)
            if change > 0.2:
                import warnings
                warnings.warn(UserWarning(
                    f'{project_name}: NVR-003 相消数量变化 {change:.0%} '
                    f'(基线={b_cnt}, 当前={r_cnt})'
                ))

