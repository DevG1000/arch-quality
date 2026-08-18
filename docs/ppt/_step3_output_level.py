# -*- coding: utf-8 -*-
print('===== output_level 体系 =====')
print()
table = [
    ('规则', '条件', 'output_level'),
    ('MLR-014', '无豁免', 'WARNING'),
    ('MLR-014', '@template_specialization_required', 'INFO'),
    ('MLR-014', 'extern template + 冗余<50', 'INFO'),
    ('MLR-017', '完整4字段豁免', 'INFO'),
    ('MLR-017', '不完整豁免', 'WARNING'),
    ('MLR-018', '@reserved_for_future_extension', 'INFO'),
    ('MLR-022', '任意', 'ERROR (固定)'),
    ('MLR-024', '无C++20 Modules', 'ERROR'),
    ('MLR-024', '有C++20 Modules接口', 'LOW'),
)
for row in table:
    print('  %-8s | %-35s | %s' % row)
