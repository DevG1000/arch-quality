# -*- coding: utf-8 -*-
"""步骤 2: 豁免注解体系"""
print('===== 三种豁免类型 =====')
print()
types = [
    ('@template_specialization_required', 'MLR-014', '多精度/多维度模板特化豁免'),
    ('@allow_binary_bloat', 'MLR-017', '性能优化导致的模板膨胀豁免 (4字段必填)'),
    ('@reserved_for_future_extension', 'MLR-018', '预留将来扩展的模板豁免'),
]
for name, rule, desc in types:
    print('  %-40s %-10s %s' % (name, rule, desc))
print()
print('===== @allow_binary_bloat 完整格式 =====')
print()
print('  // @allow_binary_bloat: SIMD vectorization;')
print('  //    performance_gain: 40%;')
print('  //    compile_time_increase: 2.1s;')
print('  //    benchmark_script: ci/benchmarks/matrix_bench.cpp;')
print('  //    threshold: gain>=30% and increase<=5s')
print()
print('===== output_level 对比 =====')
print()
print('  状态                     | output_level')
print('  -------------------------|-------------')
print('  无注解                   | WARNING')
print('  有注解但缺必填字段       | WARNING (提示缺字段)')
print('  完整4字段注解            | INFO')
