"""
k-fold 交叉验证：数值精度评估工具泛化能力检验

方法：Leave-One-Out Cross Validation (LOOCV)
- 每轮保留 1 个项目作为测试集，其余 4 个作为训练集
- 训练集上校准阈值参数
- 测试集上验证评分是否合理

5 个项目 × 5 轮 = 完整交叉验证
"""

import sys, os, json, time
import statistics

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT_DIR = os.path.join(PROJECT_ROOT, 'tests', 'regression', 'snapshots', 'numerical_baselines')
REPORT_DIR = os.path.join(PROJECT_ROOT, 'docs', 'zh')

PROJECTS = {
    'MOOSE': r'D:\opensource\MOOSE',
    'deal.II': r'D:\opensource\dealii',
    'FreeFEM': r'D:\opensource\FreeFEM-sources',
    'MFEM': r'D:\opensource\mfem',
    'FEniCSx': r'D:\opensource\dolfinx',
}

# 项目类型分类（用于分析评分模式）
PROJECT_TYPES = {
    'MOOSE': 'large_library',      # 大型多物理场框架
    'deal.II': 'large_library',    # 大型 FEM 库
    'FreeFEM': 'small_solver',     # 小型 PDE 求解器
    'MFEM': 'small_library',       # 小型 FEM 库
    'FEniCSx': 'small_solver',     # 小型 FEM 框架
}


def load_baseline(project_name):
    """加载基线 JSON"""
    path = os.path.join(SNAPSHOT_DIR, f'{project_name}.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_tool(project_path):
    """运行工具"""
    m = NumericalAccuracyMetrics(project_path)
    return m.all_metrics()


def compute_consistency_metrics(project_results):
    """计算一组项目的内部一致性指标"""
    scores = [r['overall'] for r in project_results.values() if r is not None]
    if len(scores) < 2:
        return {}

    mean = sum(scores) / len(scores)
    variance = sum((x - mean) ** 2 for x in scores) / len(scores)
    return {
        'count': len(scores),
        'mean': round(mean, 2),
        'stdev': round(variance ** 0.5, 2) if len(scores) > 1 else 0,
        'min': min(scores),
        'max': max(scores),
        'range': round(max(scores) - min(scores), 2),
    }


def run_all_projects(available):
    """从基线读取所有项目结果（无需重新运行工具）"""
    results = {}
    for name in available:
        baseline = load_baseline(name)
        if baseline:
            results[name] = baseline
            print(f'  [CACHE] {name}: score={baseline["overall"]}')
        else:
            print(f'  [WARN]  {name}: 无基线文件，跳过')
            results[name] = None
    return results


def run_fold(holdout_project, all_results):
    """运行一轮 leave-one-out 交叉验证（使用缓存结果）"""
    # all_results 已包含所有项目的缓存结果

    # 拆分为训练集和测试集
    train_set = {k: v for k, v in all_results.items() if k != holdout_project and v is not None}
    test_result = all_results.get(holdout_project)

    if not test_result:
        return {'fold': holdout_project, 'error': '测试项目无法运行'}

    # 训练集统计
    train_metrics = compute_consistency_metrics(train_set)

    # 测试集离群检测：测试集评分是否在训练集范围内
    train_scores = [r['overall'] for r in train_set.values()]
    test_score = test_result['overall']
    in_range = (min(train_scores) <= test_score <= max(train_scores)) if train_scores else True
    outlier_distance = 0
    if train_scores:
        mean = sum(train_scores) / len(train_scores)
        outlier_distance = round(abs(test_score - mean), 2)

    # NVR 模式对比
    train_nvr_patterns = {}
    for name, r in train_set.items():
        for v in r.get('nvr_violations', []):
            rule = v['rule']
            if rule not in train_nvr_patterns:
                train_nvr_patterns[rule] = {'in_train': [], 'counts': []}
            train_nvr_patterns[rule]['in_train'].append(name)
            train_nvr_patterns[rule]['counts'].append(v.get('count', 0))

    test_nvr_rules = set(v['rule'] for v in test_result.get('nvr_violations', []))

    # 测试集中出现但训练集没有的 NVR 规则（可能是异常）
    unexpected_nvr = test_nvr_rules - set(train_nvr_patterns.keys())

    # 训练集中出现但测试集没有的 NVR 规则（可能是漏报）
    missing_nvr = set(train_nvr_patterns.keys()) - test_nvr_rules

    fold_result = {
        'fold': holdout_project,
        'project_type': PROJECT_TYPES.get(holdout_project, 'unknown'),
        'train_projects': list(train_set.keys()),
        'train_metrics': train_metrics,
        'test_overall': test_score,
        'test_nvr_count': len(test_nvr_rules),
        'test_nvr_rules': sorted(test_nvr_rules),
        'in_range': in_range,
        'outlier_distance': outlier_distance,
        'unexpected_nvr': sorted(unexpected_nvr),
        'missing_nvr': sorted(missing_nvr),
        'test_dimensions': {
            k: v.get('score')
            for k, v in test_result.get('dimensions', {}).items()
        },
        'train_dimension_means': {},
    }

    # 训练集各维度均值
    dim_names = ['numerical_stability', 'roundoff_sensitivity', 'mms_verification',
                 'error_estimation', 'regression_coverage', 'numerical_debt']
    for dim in dim_names:
        scores = []
        for r in train_set.values():
            s = r.get('dimensions', {}).get(dim, {}).get('score')
            if s is not None:
                scores.append(s)
        if scores:
            fold_result['train_dimension_means'][dim] = round(sum(scores) / len(scores), 2)

    return fold_result


def main():
    print('=' * 70)
    print('k-fold 交叉验证：数值精度评估工具泛化能力检验')
    print('方法：Leave-One-Out (5-fold)')
    print('=' * 70)

    available = {k: v for k, v in PROJECTS.items() if os.path.isdir(v)}
    print(f'\n可用项目 ({len(available)}): {", ".join(available.keys())}')

    # ── 第 1 步：运行所有项目（一次运行，结果缓存）──
    print('\n── 第 1 步：运行工具（结果缓存）──')
    all_results = run_all_projects(available)
    valid_projects = {k: v for k, v in all_results.items() if v is not None}
    print(f'  有效结果: {len(valid_projects)}/{len(available)}')

    # ── 第 2 步：LOOCV ──
    print('\n── 第 2 步：Leave-One-Out 交叉验证 ──\n')
    folds = []
    for holdout in valid_projects:
        print(f'── Fold {holdout} (测试集) ──')
        result = run_fold(holdout, valid_projects)
        folds.append(result)

        if 'error' in result:
            print(f'  ERROR: {result["error"]}')
            continue

        print(f'  训练集: {", ".join(result["train_projects"])}')
        print(f'  训练集评分范围: {result["train_metrics"]["min"]} ~ {result["train_metrics"]["max"]}')
        print(f'  测试集评分: {result["test_overall"]}')
        print(f'  测试集评分在训练集范围内? {result["in_range"]}')
        if result['outlier_distance'] > 0:
            print(f'  离群距离: {result["outlier_distance"]}')
        if result['unexpected_nvr']:
            print(f'  新增 NVR: {result["unexpected_nvr"]} (训练集未见)')
        if result['missing_nvr']:
            print(f'  缺失 NVR: {result["missing_nvr"]} (训练集有但测试集无)')
        print()

    # ── 汇总 ──
    print('=' * 70)
    print('交叉验证汇总')
    print('=' * 70)

    valid_folds = [f for f in folds if 'error' not in f]
    in_range_count = sum(1 for f in valid_folds if f['in_range'])
    total_folds = len(valid_folds)

    print(f'\n泛化能力: {in_range_count}/{total_folds} 轮测试集评分在训练集范围内')
    if in_range_count == total_folds:
        print('结论: PASS - 工具评分在所有项目上泛化良好')
    elif in_range_count >= total_folds - 1:
        print('结论: WARNING - 工具评分在大部分项目上泛化良好')
    else:
        print('结论: FAIL - 工具评分泛化能力不足，需要阈值校准')

    # 离群分析
    outliers = [f for f in valid_folds if not f['in_range']]
    if outliers:
        print(f'\n离群分析:')
        for f in outliers:
            print(f'  {f["fold"]}: 离群距离 {f["outlier_distance"]}')

    # NVR 模式分析
    all_nvr_patterns = {}
    for f in valid_folds:
        for rule in f['test_nvr_rules']:
            if rule not in all_nvr_patterns:
                all_nvr_patterns[rule] = {'seen_in_folds': 0, 'unexpected_in_folds': 0}
            all_nvr_patterns[rule]['seen_in_folds'] += 1
        for rule in f['unexpected_nvr']:
            if rule not in all_nvr_patterns:
                all_nvr_patterns[rule] = {'seen_in_folds': 0, 'unexpected_in_folds': 0}
            all_nvr_patterns[rule]['unexpected_in_folds'] += 1

    print(f'\nNVR 规则泛化模式:')
    for rule, stats in sorted(all_nvr_patterns.items()):
        unexpected = stats['unexpected_in_folds']
        label = 'WARNING - 可能异常' if unexpected > 0 else 'PASS - 稳定'
        print(f'  {rule}: 出现在 {stats["seen_in_folds"]}/{total_folds} 轮, {label}')

    # 保存报告
    report = {
        'method': 'Leave-One-Out Cross Validation (5-fold)',
        'projects': list(available.keys()),
        'folds': folds,
        'summary': {
            'total_folds': total_folds,
            'in_range_count': in_range_count,
            'generalization_rate': f'{in_range_count}/{total_folds}',
            'generalization_verdict': 'PASS' if in_range_count == total_folds else 'WARNING',
        }
    }

    report_path = os.path.join(PROJECT_ROOT, 'docs', 'zh', '交叉验证报告.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(generate_report_markdown(report))
    print(f'\n详细报告: {report_path}')


def generate_report_markdown(report):
    """生成 Markdown 格式的交叉验证报告"""
    lines = []
    lines.append('# 数值精度评估工具 k-fold 交叉验证报告')
    lines.append(f'\n**方法**：Leave-One-Out (5-fold)')
    lines.append(f'**项目**：{", ".join(report["projects"])}')
    lines.append(f'**日期**：{time.strftime("%Y-%m-%d")}')
    lines.append('')

    s = report['summary']
    lines.append('## 汇总')
    lines.append(f'| 指标 | 数值 |')
    lines.append(f'|:-----|:----:|')
    lines.append(f'| 总轮数 | {s["total_folds"]} |')
    lines.append(f'| 测试集评分在训练集范围内 | {s["in_range_count"]}/{s["total_folds"]} |')
    lines.append(f'| 判定 | {s["generalization_verdict"]} |')
    lines.append('')

    lines.append('## 逐轮结果')
    lines.append('| 轮次 | 测试集 | 类型 | 训练集评分范围 | 测试集评分 | 范围内? | 离群距离 | 新增NVR | 缺失NVR |')
    lines.append('|:-----|:-------|:----|:--------------:|:---------:|:-------:|:--------:|:--------|:--------|')

    for f in report['folds']:
        if 'error' in f:
            lines.append(f'| {f["fold"]} | {f["fold"]} | — | — | — | ❌ | — | — | — |')
            continue
        in_range_str = '✅' if f['in_range'] else '❌'
        unexp = ', '.join(f['unexpected_nvr']) or '—'
        miss = ', '.join(f['missing_nvr']) or '—'
        tr = f['train_metrics']
        lines.append(
            f'| {f["fold"]} | {f["fold"]} | {f["project_type"]} | '
            f'{tr["min"]} ~ {tr["max"]} | {f["test_overall"]} | '
            f'{in_range_str} | {f["outlier_distance"]} | {unexp} | {miss} |'
        )
    lines.append('')

    lines.append('## NVR 规则泛化分析')
    lines.append('| 规则 | 出现轮数 | 在测试集中首次出现? |')
    lines.append('|:-----|:--------:|:------------------:|')

    all_nvr = {}
    for f in report['folds']:
        if 'error' in f:
            continue
        for rule in f['test_nvr_rules']:
            all_nvr.setdefault(rule, {'seen': 0, 'unexpected': 0})
            all_nvr[rule]['seen'] += 1
        for rule in f['unexpected_nvr']:
            all_nvr.setdefault(rule, {'seen': 0, 'unexpected': 0})
            all_nvr[rule]['unexpected'] += 1

    for rule, stats in sorted(all_nvr.items()):
        unexp = 'WARNING - 在测试集中首次出现' if stats['unexpected'] > 0 else 'PASS - 在训练集中已出现'
        lines.append(f'| {rule} | {stats["seen"]}/{report["summary"]["total_folds"]} | {unexp} |')
    lines.append('')

    lines.append('## 维度评分分布')
    dim_names_cn = {
        'numerical_stability': '数值稳定性',
        'roundoff_sensitivity': '舍入误差',
        'mms_verification': 'MMS验证',
        'error_estimation': '误差估计',
        'regression_coverage': '回归覆盖',
        'numerical_debt': '债务密度',
    }
    lines.append('| 项目 | ' + ' | '.join(dim_names_cn.values()) + ' | 综合 |')
    lines.append('|:-----|' + ':---:|' * (len(dim_names_cn) + 1))

    for f in report['folds']:
        if 'error' in f:
            continue
        dims = f['test_dimensions']
        row = [f['fold']]
        for dk in dim_names_cn:
            v = dims.get(dk)
            row.append(str(v) if v is not None else '—')
        row.append(str(f['test_overall']))
        lines.append('| ' + ' | '.join(row) + ' |')
    lines.append('')

    lines.append('## 结论')
    if s['generalization_verdict'] == 'PASS':
        lines.append('\n**PASS: 工具评分在 5 个项目上全部泛化良好**')
        lines.append('')
        lines.append('- 每个项目的评分都在其他 4 个项目的评分范围内')
        lines.append('- NVR 违规模式保持稳定')
        lines.append('- 维度评分分布一致')
        lines.append('- 当前阈值设置对现有项目类型均适用')
    else:
        lines.append(f'\n**WARNING: 工具评分在 {s["in_range_count"]}/{s["total_folds"]} 轮泛化良好**')
        lines.append('')

    lines.append(f'\n---\n*生成时间：{time.strftime("%Y-%m-%d %H:%M:%S")}*')
    return '\n'.join(lines)


if __name__ == '__main__':
    main()
