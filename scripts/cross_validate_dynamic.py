"""
Verrou/Valgrind 动态工具输出交叉验证

将动态工具的运行结果与静态分析工具的检测结果进行比对，
量化静态检测的准确率（误报/漏报率）。

工作流程：
  1. 在项目上运行 Valgrind/Verrou，生成动态分析报告
  2. 将动态报告转换为标准 JSON 格式（本文定义的格式）
  3. 运行本脚本，对比静态与动态结果
  4. 输出一致率、误报率、漏报率

支持的动态工具：
  - Verrou: 浮点运算插桩，检测相消损失。输出 SQLite 数据库
  - Valgrind: 通用插桩框架。输出 XML 文本报告
  - CADNA: 源代码级插桩。输出文本报告
"""

import os, sys, json, glob, re, time
from pathlib import Path


# ═══════════════════════════════════════════════════════
# 标准中间格式定义
# ═══════════════════════════════════════════════════════
#
# 所有动态工具的输出都转换为以下 JSON 格式：
#
# {
#   "tool": "verrou|valgrind|cadna",
#   "project": "MOOSE",
#   "date": "2026-07-14",
#   "results": {
#     "floating_point_exceptions": [
#       {"file": "src/solver.C", "line": 120, "type": "INVALID|DIVBYZERO|OVERFLOW",
#        "operation": "a - b", "description": "..."}
#     ],
#     "cancellation_sites": [
#       {"file": "src/solver.C", "line": 85, "severity": "high|medium|low",
#        "operands": ["1.23456789012345", "1.23456789012344"],
#        "significant_bits_lost": 12}
#     ],
#     "accumulation_errors": [
#       {"file": "src/accum.C", "line": 200, "loop_size": 10000,
#        "error_estimate": 1.2e-8}
#     ],
#     "tolerance_violations": [
#       {"file": "src/control.C", "line": 50, "tolerance": 1e-6,
#        "actual_residual": 1.2e-5}
#     ]
#   }
# }
# ═══════════════════════════════════════════════════════


class VerrouReportParser:
    """Verrou SQLite 报告解析器（需安装 Verrou 和 sqlite3）"""

    def __init__(self, db_path):
        self.db_path = db_path
        self.data = None

    def parse(self):
        """解析 Verrou SQLite 数据库"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Verrou 数据库结构因版本而异，以下是典型查询
            result = {
                'tool': 'verrou',
                'project': os.path.basename(os.path.dirname(self.db_path)),
                'date': time.strftime('%Y-%m-%d'),
                'results': {
                    'floating_point_exceptions': [],
                    'cancellation_sites': [],
                    'accumulation_errors': [],
                    'tolerance_violations': [],
                }
            }

            # 查询浮点异常
            try:
                cursor.execute("SELECT file, line, type, operation FROM exceptions")
                for row in cursor.fetchall():
                    result['results']['floating_point_exceptions'].append({
                        'file': row[0], 'line': row[1],
                        'type': row[2], 'operation': row[3]
                    })
            except sqlite3.OperationalError:
                pass  # 表可能不存在

            # 查询相消损失
            try:
                cursor.execute(
                    "SELECT file, line, severity, op1, op2, bits_lost "
                    "FROM cancellations"
                )
                for row in cursor.fetchall():
                    result['results']['cancellation_sites'].append({
                        'file': row[0], 'line': row[1],
                        'severity': row[2],
                        'operands': [row[3], row[4]],
                        'significant_bits_lost': row[5]
                    })
            except sqlite3.OperationalError:
                pass

            conn.close()
            self.data = result
            return result

        except ImportError:
            print('错误: 需要 sqlite3 模块来解析 Verrou 输出')
            return None
        except Exception as e:
            print(f'错误: 解析 Verrou 报告失败: {e}')
            return None


class ValgrindReportParser:
    """Valgrind XML 报告解析器"""

    def __init__(self, xml_path):
        self.xml_path = xml_path
        self.data = None

    def parse(self):
        """解析 Valgrind XML 报告"""
        try:
            import xml.etree.ElementTree as ET

            result = {
                'tool': 'valgrind',
                'project': os.path.basename(os.path.dirname(self.xml_path)),
                'date': time.strftime('%Y-%m-%d'),
                'results': {
                    'floating_point_exceptions': [],
                    'cancellation_sites': [],
                    'accumulation_errors': [],
                    'tolerance_violations': [],
                }
            }

            tree = ET.parse(self.xml_path)
            root = tree.getroot()

            # Valgrind XML 格式因 tool 而异
            for error in root.findall('.//error'):
                kind = error.find('kind')
                what = error.find('what')
                if kind is not None and what is not None:
                    ktext = kind.text or ''
                    wtext = what.text or ''
                    if 'Invalid' in ktext or 'uninitialised' in ktext:
                        # 提取文件和行号
                        stack = error.find('.//stack')
                        frame = stack.find('frame') if stack is not None else None
                        filename = ''
                        line = 0
                        if frame is not None:
                            fi = frame.find('file')
                            li = frame.find('line')
                            if fi is not None:
                                filename = fi.text or ''
                            if li is not None:
                                try:
                                    line = int(li.text or 0)
                                except ValueError:
                                    pass

                        result['results']['floating_point_exceptions'].append({
                            'file': filename, 'line': line,
                            'type': ktext, 'operation': wtext[:100]
                        })

            self.data = result
            return result

        except ImportError:
            print('错误: 需要 xml.etree.ElementTree 模块')
            return None
        except Exception as e:
            print(f'错误: 解析 Valgrind 报告失败: {e}')
            return None


class DynamicCrossValidator:
    """静态分析结果 vs 动态工具结果 交叉验证"""

    # 静态检测模式与动态检测项的映射关系
    MAPPING = {
        'NVR-001': {
            'name': '数值稳定性溢出',
            'dynamic_checks': ['floating_point_exceptions'],
            'match_by': 'file_and_type',
        },
        'NVR-003': {
            'name': '相消性损失',
            'dynamic_checks': ['cancellation_sites'],
            'match_by': 'file_and_severity',
        },
        'NVR-004': {
            'name': '累积误差失控',
            'dynamic_checks': ['accumulation_errors'],
            'match_by': 'file_and_loop',
        },
        'NVR-008': {
            'name': '迭代误差未控',
            'dynamic_checks': ['tolerance_violations'],
            'match_by': 'file_and_tolerance',
        },
    }

    def __init__(self, static_result, dynamic_result):
        """
        参数:
          static_result: arch_metrics_numerical_accuracy 的 all_metrics() 输出
          dynamic_result: Verrou/Valgrind 解析后的结果 dict
        """
        self.static = static_result
        self.dynamic = dynamic_result
        self.comparison = {}

    def compare(self):
        """执行交叉验证"""
        static_nvr = {v['rule']: v for v in self.static.get('nvr_violations', [])}
        dynamic = self.dynamic.get('results', {})

        for rule, mapping in self.MAPPING.items():
            static_triggered = rule in static_nvr
            static_detail = static_nvr.get(rule, {})

            # 动态工具检查
            dynamic_count = 0
            for check in mapping['dynamic_checks']:
                dynamic_count += len(dynamic.get(check, []))

            dynamic_triggered = dynamic_count > 0

            # 一致性判定
            if static_triggered and dynamic_triggered:
                consistency = '一致'
            elif not static_triggered and not dynamic_triggered:
                consistency = '一致'
            elif static_triggered and not dynamic_triggered:
                consistency = '误报'
            else:
                consistency = '漏报'

            self.comparison[rule] = {
                'rule_name': mapping['name'],
                'static_triggered': static_triggered,
                'dynamic_triggered': dynamic_triggered,
                'static_count': static_detail.get('count', 0),
                'dynamic_count': dynamic_count,
                'consistency': consistency,
            }

        return self.comparison

    def generate_report(self):
        """生成交叉验证报告"""
        lines = []
        lines.append('# 动态-静态交叉验证报告')
        lines.append(f'\n**项目**: {self.dynamic.get("project", "?")}')
        lines.append(f'**动态工具**: {self.dynamic.get("tool", "?")}')
        lines.append(f'**日期**: {self.dynamic.get("date", "?")}')
        lines.append('')

        total = len(self.comparison)
        consistent = sum(1 for v in self.comparison.values() if v['consistency'] == '一致')
        false_positives = sum(1 for v in self.comparison.values() if v['consistency'] == '误报')
        false_negatives = sum(1 for v in self.comparison.values() if v['consistency'] == '漏报')

        lines.append('## 汇总')
        lines.append(f'| 指标 | 数值 |')
        lines.append(f'|:-----|:----:|')
        lines.append(f'| 检查规则数 | {total} |')
        lines.append(f'| 一致 | {consistent} |')
        lines.append(f'| 误报 | {false_positives} |')
        lines.append(f'| 漏报 | {false_negatives} |')

        if total > 0:
            lines.append(f'| 一致率 | {consistent/total*100:.0f}% |')
            lines.append(f'| 误报率 | {false_positives/max(1,total)*100:.0f}% |')
            lines.append(f'| 漏报率 | {false_negatives/max(1,total)*100:.0f}% |')

        lines.append('')
        lines.append('## 逐规则对比')
        lines.append('| NVR | 名称 | 静态触发? | 动态触发? | 静态计数 | 动态计数 | 一致性 |')
        lines.append('|:----|:-----|:---------:|:---------:|:--------:|:--------:|:------:|')

        for rule, comp in sorted(self.comparison.items()):
            lines.append(
                f'| {rule} | {comp["rule_name"]} | '
                f'{comp["static_triggered"]} | {comp["dynamic_triggered"]} | '
                f'{comp["static_count"]} | {comp["dynamic_count"]} | '
                f'{comp["consistency"]} |'
            )

        lines.append('')
        if false_positives > 0:
            lines.append('### 误报分析（静态认为有问题，动态确认无问题）')
            for rule, comp in sorted(self.comparison.items()):
                if comp['consistency'] == '误报':
                    lines.append(f'- {rule} {comp["rule_name"]}: '
                                 f'静态检测到 {comp["static_count"]} 处，'
                                 f'动态工具验证均无实际风险')

        if false_negatives > 0:
            lines.append('### 漏报分析（静态未检出，动态发现问题）')
            for rule, comp in sorted(self.comparison.items()):
                if comp['consistency'] == '漏报':
                    lines.append(f'- {rule} {comp["rule_name"]}: '
                                 f'静态未触发，动态工具发现 {comp["dynamic_count"]} 处问题')

        lines.append(f'\n---\n*生成时间: {time.strftime("%Y-%m-%d %H:%M:%S")}*')
        return '\n'.join(lines)


def create_mock_report(project_name):
    """创建一个模拟的动态工具报告（用于演示和测试框架）"""
    mock_reports = {
        'FEniCSx': {
            'tool': 'verrou',
            'project': 'FEniCSx',
            'date': '2026-07-14',
            'results': {
                'floating_point_exceptions': [
                    {'file': 'cpp/dolfinx/common/IndexMap.cpp', 'line': 120,
                     'type': 'INVALID', 'operation': 'division by zero in index calculation'}
                ],
                'cancellation_sites': [
                    {'file': 'cpp/dolfinx/la/MatrixCSR.h', 'line': 85,
                     'severity': 'low',
                     'operands': ['1.000000000001', '1.000000000000'],
                     'significant_bits_lost': 3}
                ],
                'accumulation_errors': [],
                'tolerance_violations': [],
            }
        },
    }
    return mock_reports.get(project_name)


def compare_with_mock(project_name, static_result_path):
    """使用模拟报告对比（演示用法）"""
    mock = create_mock_report(project_name)
    if not mock:
        print(f'无 {project_name} 的模拟报告')
        return

    import json
    with open(static_result_path, 'r', encoding='utf-8') as f:
        static = json.load(f)

    validator = DynamicCrossValidator(static, mock)
    comparison = validator.compare()
    report = validator.generate_report()

    print(report)
    return comparison


def main():
    """命令行入口"""
    import argparse
    import time

    parser = argparse.ArgumentParser(
        description='Verrou/Valgrind 动态工具交叉验证'
    )
    parser.add_argument('--static', help='静态分析结果 JSON 路径')
    parser.add_argument('--dynamic', help='动态工具报告路径')
    parser.add_argument('--tool', choices=['verrou', 'valgrind', 'json'],
                        default='json', help='动态工具类型')
    parser.add_argument('--mock', metavar='PROJECT',
                        help='使用模拟报告演示（用于测试框架）')
    args = parser.parse_args()

    if args.mock:
        # 演示模式
        snap_dir = os.path.join(os.path.dirname(__file__), '..',
                                'tests', 'regression', 'snapshots', 'numerical_baselines')
        snap_path = os.path.join(snap_dir, f'{args.mock}.json')
        if os.path.exists(snap_path):
            compare_with_mock(args.mock, snap_path)
        else:
            print(f'基线文件不存在: {snap_path}')
            print('可用项目: MOOSE, deal.II, FreeFEM, MFEM, FEniCSx')
        return

    if not args.static or not args.dynamic:
        parser.print_help()
        print('\n示例:')
        print('  # 使用模拟数据演示')
        print('  python cross_validate_dynamic.py --mock FEniCSx')
        print('')
        print('  # 使用真实数据')
        print('  python cross_validate_dynamic.py \\')
        print('      --static path/to/static_results.json \\')
        print('      --dynamic path/to/verrou.sqlite --tool verrou')
        return

    # 读取静态结果
    import json
    with open(args.static, 'r', encoding='utf-8') as f:
        static = json.load(f)

    # 解析动态报告
    if args.tool == 'verrou':
        parser_obj = VerrouReportParser(args.dynamic)
    elif args.tool == 'valgrind':
        parser_obj = ValgrindReportParser(args.dynamic)
    else:
        with open(args.dynamic, 'r', encoding='utf-8') as f:
            dynamic = json.load(f)
        parser_obj = None

    if parser_obj:
        dynamic = parser_obj.parse()

    if not static or not dynamic:
        print('错误: 无法读取静态或动态结果')
        return

    validator = DynamicCrossValidator(static, dynamic)
    comparison = validator.compare()
    report = validator.generate_report()

    print(report)

    # 保存报告
    report_path = f'cross_validate_dynamic_report_{args.mock or "report"}.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'\n报告已保存: {report_path}')


if __name__ == '__main__':
    main()
