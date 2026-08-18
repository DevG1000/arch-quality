"""
求解器物理场评估外部验证回归测试

对本地可用的开源多物理场项目运行工具，将结果与已建立的基线 JSON 比对。
检测评分偏移、MPR 违规数量变化等回归问题。

性能说明：每个项目只运行一次评估，结果被缓存供所有测试方法复用。
MOOSE 等大型项目（20k+ 文件）耗时约 40s，标注为 slow。

快照更新：设置环境变量 ARCH_REGRESSION_UPDATE=1
"""

import os
import json
import sys
import functools
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from arch_quality.arch_metrics_solver_physics import SolverPhysicsMetrics

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), 'snapshots')
UPDATE_SNAPSHOTS = os.environ.get("ARCH_REGRESSION_UPDATE", "") == "1"

# 可用项目（路径与本机仓库位置绑定）
PROJECTS = {
    'MOOSE': r'D:\opensource\MOOSE',
    'OpenFOAM': r'D:\opensource\OpenFOAM-v2512',
    'deal.II': r'D:\opensource\dealii',
    'MFEM': r'D:\opensource\mfem',
    'FEniCSx': r'D:\opensource\dolfinx',
    'ElmerFEM': r'D:\opensource\ElmerFEM',
    'Kratos': r'D:\opensource\Kratos',
    'FreeFEM': r'D:\opensource\FreeFEM-sources',
    'SU2': r'D:\opensource\SU2',
    'preCICE': r'D:\opensource\preCICE',
}

# 大项目标记为 slow（单次运行 > 30s）
SLOW_PROJECTS = {'MOOSE', 'OpenFOAM', 'deal.II', 'ElmerFEM', 'Kratos'}

TOLERANCE_OVERALL = 2.0
TOLERANCE_DIMENSION = 5.0


def _snapshot_name(project_name):
    return f"sp_{project_name.lower().replace('.', '').replace(' ', '_')}.json"


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
        'is_multiphysics': result.get('is_multiphysics'),
        'dimensions': {k: v.get('score') for k, v in result.get('dimensions', {}).items()},
        'mpr_violations': result.get('mpr_violations', []),
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    print(f'  快照已更新: {path}')


@functools.lru_cache(maxsize=None)
def run_assessment_cached(project_path):
    m = SolverPhysicsMetrics(project_path)
    return m.all_metrics()


@pytest.fixture(scope='module')
def baseline(request):
    return load_baseline(request.param)


@pytest.fixture(scope='module')
def assessment(request):
    # request.param 是项目名，需映射到实际目录
    path = PROJECTS[request.param]
    return run_assessment_cached(path)


def _make_test_class(project_name):
    """为单个项目生成参数化测试类"""

    @pytest.mark.parametrize('baseline,assessment',
                             [(project_name, project_name)],
                             indirect=True,
                             scope='module')
    class TestProjectAssessment:
        @pytest.mark.skipif(project_name == 'FEniCSx',
                            reason='FEniCSx 被识别为非多物理场项目')
        def test_overall_score(self, baseline, assessment):
            if baseline.get('is_multiphysics'):
                assert assessment.get('is_multiphysics'), f'{project_name} 应识别为多物理场项目'
                assert assessment['overall'] is not None
                assert abs(assessment['overall'] - baseline['overall']) <= TOLERANCE_OVERALL, (
                    f'{project_name}: 综合评分偏移超限 '
                    f'(基线={baseline["overall"]}, 当前={assessment["overall"]})'
                )

        @pytest.mark.skipif(project_name == 'FEniCSx',
                            reason='FEniCSx 被识别为非多物理场项目')
        def test_dimension_scores(self, baseline, assessment):
            if not baseline.get('is_multiphysics'):
                return
            for dim_name in ['boundary_integrity', 'coupling_architecture',
                             'extension_support', 'data_transfer']:
                b_score = baseline['dimensions'].get(dim_name)
                a_score = assessment['dimensions'].get(dim_name, {}).get('score')
                if b_score is not None:
                    assert a_score is not None, f'{project_name}/{dim_name}: 当前评分为 None'
                    assert abs(a_score - b_score) <= TOLERANCE_DIMENSION, (
                        f'{project_name}/{dim_name}: 维度评分偏移超限 '
                        f'(基线={b_score}, 当前={a_score})'
                    )

        @pytest.mark.skipif(project_name == 'FEniCSx',
                            reason='FEniCSx 被识别为非多物理场项目')
        def test_mpr_rule_count(self, baseline, assessment):
            if not baseline.get('is_multiphysics'):
                return
            b_rules = [v.get('rule') for v in baseline.get('mpr_violations', [])]
            a_rules = [v.get('rule') for v in assessment.get('mpr_violations', [])]
            # MPR 规则集合应保持一致（允许顺序变化）
            assert set(a_rules) == set(b_rules), (
                f'{project_name}: MPR 规则集合变化\n'
                f'  基线: {sorted(b_rules)}\n'
                f'  当前: {sorted(a_rules)}'
            )

    TestProjectAssessment.__name__ = f'Test{project_name}Assessment'
    return TestProjectAssessment


for proj in PROJECTS:
    cls = _make_test_class(proj)
    globals()[cls.__name__] = cls


def test_fenicsx_not_multiphysics():
    """FEniCSx 应被识别为非多物理场（基于当前检测规则）"""
    path = PROJECTS['FEniCSx']
    if not os.path.isdir(path):
        pytest.skip('FEniCSx 目录不存在')
    m = SolverPhysicsMetrics(path)
    result = m.all_metrics()
    assert not result['is_multiphysics']
    assert result['overall'] is None
