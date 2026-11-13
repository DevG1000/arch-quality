---
name: geometry-consistency
description: >
  几何内核与科学数据结构一致性评估。Use when the user asks to evaluate
  geometry kernel data consistency (B-Rep closure, Handle smart pointers),
  mesh/field semantic consistency, unit/precision magic numbers, or data
  access encapsulation. Covers 4 dimensions and 12 GCS rules (GCS-001
  through GCS-012).
---

# 几何内核与科学数据结构一致性评估技能

评估工业软件中几何内核（OCCT 等）与科学数据结构（VTK/gmsh/OpenFOAM 网格、场量）的一致性质量。作为结构质量增强维度，权重候选 10%~15%（H2 归一化定案），在检测到几何内核/科学数据结构引用时自动启用。

> **版本绑定**：详细 skill 见 `src/arch_quality/skills/geometry-consistency.md`
> - 指南版本：1.6
> - Skill 版本：1.0
> - 实现：`arch_metrics_geometry_consistency.py`（`SKILL_VERSION="1.0"`）

## 4 维度评分模型

| 维度 | 权重 | 说明 |
|:-----|:----:|:------|
| 几何内核数据一致性 | 30% | 闭合性校验/Handle 智能指针/失败状态传播/生命周期 |
| 内核精度/单位一致性 | 20% | 精度容差魔法数字/单位换算因子 |
| 科学数据结构组织一致性 | 25% | 网格语义混用/场量命名/维度匹配 |
| 数据表示与访问规范性 | 25% | 裸数组密度/深浅拷贝/访问封装（2.1<60 递进折半）|

评分算法见 `src/arch_quality/skills/geometry-consistency.md`。

## 12 条 GCS 规则

| 规则 | 名称 | output_level | 说明 |
|:-----|:------|:------------:|:------|
| GCS-001 | 闭合性校验测试存在性（加分项）| **INFO** | 缺失仅提示，非违规扣分 |
| GCS-002 | Handle 智能指针一致性 | **WARNING** | 裸指针跨作用域穿越 |
| GCS-003 | 内核异常/失败状态传播 | **WARNING** | 布尔操作直接提取结果无检查 |
| GCS-004 | 内核对象生命周期 | **WARNING** | 同作用域手动 new/delete |
| GCS-005 | 硬编码精度/容差魔法数字 | **INFO** | 文件级字面量无命名常量 |
| GCS-006 | 单位换算魔法因子 | **INFO** | 魔法因子无统一函数 |
| GCS-007 | 网格单元类型一致性 | **ERROR** | 多网格类型交叉索引（转换器豁免）|
| GCS-008 | 场量组织一致性 | **WARNING** | pointData/cellData 命名混用 |
| GCS-009 | 网格/场量维度匹配 | **WARNING** | 维度因子与命名常量不一致 |
| GCS-010 | 裸数组替代科学数据结构 | **INFO** | 密度阈值超限 |
| GCS-011 | 深拷贝 vs 浅拷贝 | **INFO** | 拷贝构造函数共享缓冲 |
| GCS-012 | 数据访问封装性 | **ERROR** | 直接成员访问 |

## 使用场景

- 评估 CAD/CAE 平台几何内核（OCCT/FreeCAD/SALOME）的数据一致性
- 检查 B-Rep 闭合性校验、Handle 生命周期、异常传播实践
- 检查网格/场量语义混用与数据访问封装

## 相关文件

- 详细 skill 定义：`src/arch_quality/skills/geometry-consistency.md`
- 评估指南：`docs/zh/几何内核与科学数据结构一致性评估/几何内核与科学数据结构一致性评估指南.md`
- 验证案例集：`docs/zh/几何内核与科学数据结构一致性评估/几何内核与科学数据结构一致性评估验证案例集.md`
- 实现模块：`src/arch_quality/arch_metrics_geometry_consistency.py`