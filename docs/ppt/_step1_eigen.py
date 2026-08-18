# -*- coding: utf-8 -*-
"""步骤 1: Eigen 项目评估演示"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from arch_quality.arch_metrics_template import TemplateMetaprogrammingMetrics

m = TemplateMetaprogrammingMetrics(r'D:\OPENSOURCE\Eigen')
r = m.all_metrics()
print('项目: Eigen (线性代数库)')
print('C++ 文件数: %d' % r['cpp_file_count'])
print()
print('6 维评分:')
for k, v in r['dimensions'].items():
    if isinstance(v, dict):
        score = v.get('score')
        bar = '#' * int(score / 5) if score else ''
        print('  %-30s %5s  %s' % (k + ':', score, bar))
print()
mlr = r.get('mlr_violations', [])
print('MLR 违规: %d 条' % len(mlr))
for x in mlr:
    print('  %-8s | %-5s | %-7s | %s' % (
        x['rule'], x.get('severity',''), x.get('output_level',''), x.get('detail','')[:80]))
