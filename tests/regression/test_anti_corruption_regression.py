"""
外部科学内核与几何内核的封装与防腐层评估外部验证回归测试（B3）

对本地可用的开源 CAD/CAE 项目运行 ACL 引擎，与已建立的基线 JSON 比对。
检测评分偏移、ACL 违规数量变化等回归问题。

项目：occt / salome-geom / freecad（来自 projects.yaml 固定 ref）
快照更新：设置环境变量 ARCH_REGRESSION_UPDATE=1
"""

import os
import json
import sys
import functools
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from arch_quality.arch_metrics_anti_corruption import AntiCorruptionMetrics

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), 'snapshots')
UPDATE_SNAPSHOTS = os.environ.get("ARCH_REGRESSION_UPDATE", "") == "1"

PROJECTS = {
    'occt': r'D:\opensource\gcs-baselines\occt',
    'salome_geom': r'D:\opensource\gcs-baselines\salome-geom',
    'freecad': r'D:\OPENSOURCE\FreeCAD',
}

TOLERANCE_OVERALL = 2.0
TOLERANCE_DIMENSION = 5.0


def _snapshot_name(project_name):
    return f"acl_{project_name}.json"


def load_baseline(project_name):
    path = os.path.join(SNAPSHOT_DIR, _snapshot_name(project_name))
    if not os.path.exists(path):
        pytest.skip(f'基线文件不存在: {path}')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_baseline(project_name, result):
    path = os.path.join(SNAPSHOT_DIR, _snapshot_name(project_name))
    snap = {
        'project': project_name,
        'overall': result.get('overall'),
        'is_acl': result.get('is_acl'),
        'dimensions': {k: v.get('score') for k, v in result.get('dimensions', {}).items()},
        'acl_violations': result.get('acl_violations', []),
        'root_path': PROJECTS[project_name],
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    print(f'  快照已更新: {path}')


@functools.lru_cache(maxsize=None)
def run_assessment_cached(project_path):
    m = AntiCorruptionMetrics(project_path)
    return m.all_metrics()


@pytest.fixture(scope='module')
def baseline(request):
    return load_baseline(request.param)


@pytest.fixture(scope='module')
def assessment(request):
    path = PROJECTS[request.param]
    if not os.path.exists(path):
        pytest.skip(f'项目目录不存在: {path}')
    return run_assessment_cached(path)


def _make_test_class(project_name):
    @pytest.mark.parametrize('baseline,assessment',
                             [(project_name, project_name)],
                             indirect=True, scope='module')
    class TestProjectAssessment:
        def test_overall_score(self, baseline, assessment):
            if UPDATE_SNAPSHOTS:
                save_baseline(project_name, assessment)
                return
            assert assessment.get('is_acl') is True, f'{project_name} 应识别为防腐层项目'
            assert abs(assessment['overall'] - baseline['overall']) <= TOLERANCE_OVERALL, (
                f'{project_name}: 综合评分偏移超限 '
                f'(基线={baseline["overall"]}, 当前={assessment["overall"]})')

        def test_dimension_scores(self, baseline, assessment):
            if UPDATE_SNAPSHOTS:
                return
            for dim in ['external_access', 'wrapper_coverage',
                        'data_exchange', 'fidelity']:
                b_score = baseline['dimensions'].get(dim)
                a_score = assessment['dimensions'].get(dim, {}).get('score')
                if b_score is None:
                    assert a_score is None, f'{project_name}/{dim}: 基线 None 但当前 {a_score}'
                elif a_score is not None:
                    assert abs(a_score - b_score) <= TOLERANCE_DIMENSION, (
                        f'{project_name}/{dim}: 维度评分偏移超限 '
                        f'(基线={b_score}, 当前={a_score})')

        def test_acl_violation_counts(self, baseline, assessment):
            if UPDATE_SNAPSHOTS:
                return
            baseline_rules = {v['rule']: v['count'] for v in baseline.get('acl_violations', [])}
            actual_rules = {v['rule']: v['count'] for v in assessment.get('acl_violations', [])}
            for rule in set(baseline_rules) | set(actual_rules):
                b = baseline_rules.get(rule, 0)
                a = actual_rules.get(rule, 0)
                tol = max(5, int(b * 0.2))
                assert abs(a - b) <= tol, (
                    f'{project_name}/{rule}: 计数 {a} 偏离基线 {b} 超过容差 {tol}')

        def test_output_level_not_escalated(self, baseline, assessment):
            if UPDATE_SNAPSHOTS:
                return
            baseline_levels = {v['rule']: v['output_level'] for v in baseline.get('acl_violations', [])}
            for v in assessment.get('acl_violations', []):
                if v['rule'] in baseline_levels:
                    assert v['output_level'] == baseline_levels[v['rule']], (
                        f'{project_name}/{v["rule"]}: output_level 升级 '
                        f'{baseline_levels[v["rule"]]} → {v["output_level"]}')

    TestProjectAssessment.__name__ = f'TestACL{project_name.title().replace("_", "")}'
    TestProjectAssessment.__qualname__ = TestProjectAssessment.__name__
    return TestProjectAssessment


for _p in PROJECTS:
    globals()[f'TestACL{_p.title().replace("_", "")}'] = _make_test_class(_p)