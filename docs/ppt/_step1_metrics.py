# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from arch_quality.arch_metrics_template import TemplateMetaprogrammingMetrics
m = TemplateMetaprogrammingMetrics(r'D:\OPENSOURCE\Eigen')
r = m.all_metrics()
print('整体评分: %s' % r['overall'])
print('维度:')
for k, v in r['dimensions'].items():
    if isinstance(v, dict):
        print('  %s: %s' % (k, v.get('score')))
print()
print('MLR违规: %d条' % len(r.get('mlr_violations', [])))
for x in r.get('mlr_violations', [])[:5]:
    print('  %s | ol=%s' % (x['rule'], x.get('output_level','')))
