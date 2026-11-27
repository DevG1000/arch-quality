# -*- coding: utf-8 -*-
print('===== output_level 体系 =====')
print()
table = [
    ('规则', '条件', 'output_level'),
    ('TPL-002', '无豁免', 'WARNING'),
    ('TPL-002', '@template_specialization_required', 'INFO'),
    ('TPL-002', 'extern template + 冗余<50', 'INFO'),
    ('TPL-005', '完整4字段豁免', 'INFO'),
    ('TPL-005', '不完整豁免', 'WARNING'),
    ('TPL-006', '@reserved_for_future_extension', 'INFO'),
    ('TPL-010', '任意', 'ERROR (固定)'),
    ('TPL-012', '无C++20 Modules', 'ERROR'),
    ('TPL-012', '有C++20 Modules接口', 'LOW'),
)
for row in table:
    print('  %-8s | %-35s | %s' % row)
