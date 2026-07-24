"""
数值精度评估工具 人工评审 vs 工具评分比对脚本

用法：
    # 单条对比
    python scripts/compare_review.py \
        --project MOOSE --tool-score 96.0 --manual-score 95 --reviewer "张三"

    # 批量对比（从评审文件读取）
    python scripts/compare_review.py --batch scripts/reviews/*.md

    # 查看汇总报告
    python scripts/compare_review.py --summary
"""

import os, sys, json, re, glob
import argparse
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SNAPSHOT_DIR = os.path.join(PROJECT_ROOT, 'tests', 'regression', 'snapshots', 'numerical_baselines')
REVIEWS_DIR = os.path.join(SCRIPT_DIR, 'reviews')
SUMMARY_FILE = os.path.join(SCRIPT_DIR, 'review_summary.json')


def get_tool_score(project_name):
    """从基线 JSON 获取工具评分"""
    snap_path = os.path.join(SNAPSHOT_DIR, f'{project_name}.json')
    if not os.path.exists(snap_path):
        return None, f'基线文件不存在: {snap_path}'
    with open(snap_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data, None


def extract_manual_score(review_path):
    """从评审 Markdown 文件中提取人工评分"""
    with open(review_path, 'r', encoding='utf-8') as f:
        content = f.read()

    result = {
        'file': review_path,
        'project': None,
        'reviewer': None,
        'date': None,
        'dimensions': {},
        'overall': None,
    }

    # 提取项目名（从文件名或第一行）
    basename = os.path.basename(review_path).replace('.md', '')
    parts = basename.split('_')
    if len(parts) >= 1:
        result['project'] = parts[0]

    # 提取各维度评分
    dim_patterns = {
        'numerical_stability': r'## 一、[^\n]*\n.*?\*\*人工评分\*\*[：:]\s*(\d+)\s*/\s*100',
        'roundoff_sensitivity': r'## 二、[^\n]*\n.*?\*\*人工评分\*\*[：:]\s*(\d+)\s*/\s*100',
        'mms_verification': r'## 三、[^\n]*\n.*?\*\*人工评分\*\*[：:]\s*(\d+)\s*/\s*100',
        'error_estimation': r'## 四、[^\n]*\n.*?\*\*人工评分\*\*[：:]\s*(\d+)\s*/\s*100',
        'regression_coverage': r'## 五、[^\n]*\n.*?\*\*人工评分\*\*[：:]\s*(\d+)\s*/\s*100',
        'numerical_debt': r'## 六、[^\n]*\n.*?\*\*人工评分\*\*[：:]\s*(\d+)\s*/\s*100',
    }

    for dim, pattern in dim_patterns.items():
        m = re.search(pattern, content, re.DOTALL)
        if m:
            result['dimensions'][dim] = int(m.group(1))

    # 提取综合评分
    overall_pattern = r'综合评分[（(]加权[）)]\s*[：:]\s*人工\s*(\d+)\s*\|?\s*工具\s*(\d+)'
    m = re.search(overall_pattern, content)
    if m:
        result['overall'] = int(m.group(1))

    return result


def compare_single(project, tool_overall, manual_overall, dims_tool, dims_manual, reviewer='?'):
    """对比单个项目的工具评分和人工评分"""
    result = {
        'project': project,
        'reviewer': reviewer,
        'tool_overall': tool_overall,
        'manual_overall': manual_overall,
        'overall_diff': round(abs(tool_overall - manual_overall), 2) if tool_overall and manual_overall else None,
        'dimensions': {},
        'false_positives': [],
        'false_negatives': [],
        'accuracy': None,
    }

    # 各维度对比
    all_dims = ['numerical_stability', 'roundoff_sensitivity', 'mms_verification',
                'error_estimation', 'regression_coverage', 'numerical_debt']
    weights = [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]

    total_diff = 0
    dim_count = 0
    for dim in all_dims:
        t = dims_tool.get(dim, {}).get('score') if isinstance(dims_tool.get(dim), dict) else dims_tool.get(dim)
        m = dims_manual.get(dim)
        if t is not None and m is not None:
            diff = abs(t - m)
            total_diff += diff
            dim_count += 1
            result['dimensions'][dim] = {
                'tool': t,
                'manual': m,
                'diff': diff,
                'weight': weights[all_dims.index(dim)],
            }

    # 综合准确度评估
    if dim_count > 0:
        avg_diff = total_diff / dim_count
        if avg_diff <= 5:
            result['accuracy'] = '非常准确'
        elif avg_diff <= 10:
            result['accuracy'] = '较准确'
        elif avg_diff <= 20:
            result['accuracy'] = '一般'
        else:
            result['accuracy'] = '不准确'

    return result


def generate_report(results):
    """生成汇总报告"""
    lines = []
    lines.append('# 数值精度评估工具 人工评审汇总报告')
    lines.append(f'\n## 汇总信息')
    lines.append(f'| 指标 | 数值 |')
    lines.append(f'|:-----|:----:|')
    lines.append(f'| 评审项目数 | {len(results)} |')

    all_diffs = []
    for r in results:
        if r.get('overall_diff') is not None:
            all_diffs.append(r['overall_diff'])

    if all_diffs:
        lines.append(f'| 综合评分平均差异 | {sum(all_diffs)/len(all_diffs):.1f} 分 |')
        lines.append(f'| 综合评分最大差异 | {max(all_diffs):.1f} 分 |')

    lines.append(f'\n## 逐项目对比')
    lines.append(f'| 项目 | 评审者 | 工具评分 | 人工评分 | 差异 | 准确度 |')
    lines.append(f'|:-----|:------|:--------:|:--------:|:----:|:------:|')

    for r in results:
        lines.append(
            f'| {r["project"]} | {r["reviewer"]} | '
            f'{r["tool_overall"] or "-"} | {r["manual_overall"] or "-"} | '
            f'{r["overall_diff"] or "-"} | {r["accuracy"] or "-"} |'
        )

    lines.append(f'\n## 维度级差异分析')
    dim_names_cn = {
        'numerical_stability': '数值稳定性',
        'roundoff_sensitivity': '舍入误差',
        'mms_verification': 'MMS验证',
        'error_estimation': '误差估计',
        'regression_coverage': '回归覆盖',
        'numerical_debt': '债务密度',
    }
    lines.append(f'| 维度 | 项目 | 工具 | 人工 | 差异 |')
    lines.append(f'|:-----|:----|:----:|:----:|:----:|')
    for r in results:
        for dim, d in r.get('dimensions', {}).items():
            cn = dim_names_cn.get(dim, dim)
            lines.append(f'| {cn} | {r["project"]} | {d["tool"]} | {d["manual"]} | {d["diff"]} |')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='数值精度评估 人工评分 vs 工具评分比对')
    parser.add_argument('--project', help='项目名')
    parser.add_argument('--tool-score', type=float, help='工具综合评分')
    parser.add_argument('--manual-score', type=float, help='人工综合评分')
    parser.add_argument('--reviewer', default='?', help='评审者')
    parser.add_argument('--batch', help='批量评审文件 glob 模式，如 reviews/*.md')
    parser.add_argument('--summary', action='store_true', help='显示汇总报告')
    args = parser.parse_args()

    if args.batch:
        # 批量模式
        files = glob.glob(args.batch)
        if not files:
            print(f'未找到匹配文件: {args.batch}')
            return

        results = []
        for fp in files:
            review = extract_manual_score(fp)
            if not review['project']:
                continue

            tool_data, err = get_tool_score(review['project'])
            if err:
                print(f'[SKIP] {review["project"]}: {err}')
                continue

            tool_dims = tool_data.get('dimensions', {})
            result = compare_single(
                review['project'],
                tool_data.get('overall'),
                review['overall'],
                tool_dims,
                review['dimensions'],
                review.get('reviewer', '?')
            )
            results.append(result)

        # 生成报告
        report = generate_report(results)
        print(report)

        # 保存汇总
        with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
            json.dump({'results': results, 'report': report}, f,
                      ensure_ascii=False, indent=2)
        print(f'\n汇总已保存: {SUMMARY_FILE}')

    elif args.project and args.tool_score is not None and args.manual_score is not None:
        # 单条模式
        tool_data, err = get_tool_score(args.project)
        if err:
            print(f'错误: {err}')
            return

        result = compare_single(
            args.project,
            tool_data.get('overall'),
            args.manual_score,
            tool_data.get('dimensions', {}),
            {},  # 单条模式未提供维度人工评分
            args.reviewer
        )
        result['tool_overall'] = args.tool_score
        result['manual_overall'] = args.manual_score

        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.summary:
        if os.path.exists(SUMMARY_FILE):
            with open(SUMMARY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(data.get('report', '无报告数据'))
        else:
            print(f'汇总文件不存在: {SUMMARY_FILE}')
            print('请先运行 --batch 生成汇总')

    else:
        parser.print_help()
        print('\n示例:')
        print('  python scripts/compare_review.py --project MOOSE --tool-score 96.0 --manual-score 95 --reviewer "张三"')
        print('  python scripts/compare_review.py --batch scripts/reviews/*.md')
        print('  python scripts/compare_review.py --summary')


if __name__ == '__main__':
    main()
