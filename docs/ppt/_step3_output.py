# -*- coding: utf-8 -*-
"""步骤 3: output_level 体系"""
print('===== output_level 完整映射 =====')
print()
table = [
    ('TPL-002', '无豁免', 'WARNING'),
    ('TPL-002', '@template_specialization_required', 'INFO'),
    ('TPL-002', 'extern template + 冗余<50', 'INFO'),
    ('TPL-005', '完整4字段豁免', 'INFO'),
    ('TPL-005', '不完整豁免 / 无豁免', 'WARNING'),
    ('TPL-006', '@reserved_for_future_extension', 'INFO'),
    ('TPL-010', '任意情况', 'ERROR (固定)'),
    ('TPL-012', '无 C++20 Modules', 'ERROR'),
    ('TPL-012', '有 C++20 Modules 接口', 'LOW'),
]
for rule, cond, ol in table:
    print('  %-8s | %-35s | %s' % (rule, cond, ol))
print()
print('概念: severity 表示理论严重度 (始终不变)')
print('      output_level 表示实际输出行为 (按条件变化)')
