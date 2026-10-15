# 外部内核防腐层评估工具 k-fold 交叉验证报告

**方法**：Leave-One-Out (9-fold)
**项目**：acl_salome_geom, acl_gmsh, acl_freecad, acl_elmerfem, acl_synth_healthy, acl_occt, acl_kicad, acl_synth_direct, acl_synth_scatter
**日期**：2026-10-15

## 汇总
| 指标 | 数值 |
|:-----|:----:|
| 总轮数 | 9 |
| 测试集评分在训练集范围内 | 7/9 |
| 判定 | PASS |

## 逐轮结果
| 测试集 | 类型 | 训练集评分范围 | 测试集评分 | 范围内? | 离群距离 | 新增ACL | 缺失ACL |
|:-------|:----|:--------------:|:---------:|:-------:|:--------:|:--------|:--------|
| acl_salome_geom | kernel_wrap | 24.0 ~ 87.5 | 26.5 | ✅ | 16.31 | — | ACL-003, ACL-004, ACL-006 |
| acl_gmsh | mesh_tool | 26.5 ~ 87.5 | 24.0 | ❌ | 19.12 | — | ACL-003, ACL-004, ACL-010 |
| acl_freecad | kernel_app | 24.0 ~ 87.5 | 38.0 | ✅ | 3.38 | — | ACL-003, ACL-004, ACL-006, ACL-010, ACL-011 |
| acl_elmerfem | fem_suite | 24.0 ~ 87.5 | 39.5 | ✅ | 1.69 | — | ACL-003, ACL-004, ACL-005, ACL-011 |
| acl_synth_healthy | synthetic_good | 24.0 ~ 47.0 | 87.5 | ❌ | 52.31 | — | ACL-001, ACL-002, ACL-004, ACL-005, ACL-006, ACL-007, ACL-011, ACL-012 |
| acl_occt | kernel | 24.0 ~ 87.5 | 36.5 | ✅ | 5.06 | — | ACL-003, ACL-004, ACL-006, ACL-010, ACL-012 |
| acl_kicad | eda | 24.0 ~ 87.5 | 47.0 | ✅ | 6.75 | — | ACL-003, ACL-004, ACL-005, ACL-006, ACL-010, ACL-011 |
| acl_synth_direct | synthetic_bad | 24.0 ~ 87.5 | 35.0 | ✅ | 6.75 | ACL-004 | ACL-007, ACL-011, ACL-012 |
| acl_synth_scatter | synthetic_bad | 24.0 ~ 87.5 | 35.0 | ✅ | 6.75 | — | ACL-001, ACL-004, ACL-005 |

## ACL 规则泛化分析
| 规则 | 出现轮数 | 在测试集中首次出现? |
|:-----|:--------:|:------------------:|
| ACL-001 | 7/9 | PASS - 在训练集中已出现 |
| ACL-002 | 8/9 | PASS - 在训练集中已出现 |
| ACL-003 | 3/9 | PASS - 在训练集中已出现 |
| ACL-004 | 1/9 | WARNING - 在测试集中首次出现 |
| ACL-005 | 5/9 | PASS - 在训练集中已出现 |
| ACL-006 | 4/9 | PASS - 在训练集中已出现 |
| ACL-007 | 7/9 | PASS - 在训练集中已出现 |
| ACL-010 | 5/9 | PASS - 在训练集中已出现 |
| ACL-011 | 4/9 | PASS - 在训练集中已出现 |
| ACL-012 | 6/9 | PASS - 在训练集中已出现 |

## 维度评分分布
| 项目 | 外部内核访问防腐 | Wrapper 覆盖与演进守卫 | 数据交换防腐 | 保真度与标准一致性 | 综合 |
|:-----|:---:|:---:|:---:|:---:|:---:|
| acl_salome_geom | 30 | 50 | 0 | 40 | 26.5 |
| acl_gmsh | 30 | 50 | 0 | 30 | 24.0 |
| acl_freecad | 30 | 50 | 30 | 50 | 38.0 |
| acl_elmerfem | 60 | 50 | 30 | 20 | 39.5 |
| acl_synth_healthy | 100 | 50 | 100 | 80 | 87.5 |
| acl_occt | 30 | 50 | 25 | 50 | 36.5 |
| acl_kicad | 60 | 50 | 30 | 50 | 47.0 |
| acl_synth_direct | 0 | 0 | 100 | 20 | 35.0 |
| acl_synth_scatter | 100 | 0 | 0 | 20 | 35.0 |

## 结论

**PASS: 泛化 7/9 ≥ KPI2 阈值 7/9**

- 绝大多数项目的综合评分落在其余项目的评分范围内（离群项见逐轮结果）
- 违规模式总体稳定
- 4 维度评分分布一致
- 当前阈值设置对现有项目类型均适用


---
*生成时间：2026-10-15 17:10:07*