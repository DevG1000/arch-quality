# 化石代码与技术债评估 Skill

提供 F77/固定格式 Fortran、废弃 C++ API、K&R C、死代码/克隆、技术债密度的静态检测知识：4 个子维度、12 条 FOS 规则（FOS-001~012）、评分与豁免体系。

> **版本信息**
> - 对应指南：`化石代码与技术债评估指南.md` **v0.3**
> - 对应实现：`arch_metrics_fossil_code.py`
> - 技能版本：**1.0**
> - 一致性约束：指南 §2.x ↔ Skill §x ↔ Tool `_rule_xxx()` 的规则/分值必须一致；修改一处时同步其余两处。

## 权重分配

| 子维度 | 权重 |
|:--|:-:|
| 历史遗留 API 与语言方言 | 30% |
| 死代码与不可达逻辑 | 20% |
| 重复代码与重复实现 | 20% |
| 技术债密度与可维护性 | 30% |

> 权重和 = 100%，由 `arch_core.load_weights_from_skill()` 解析；**不在代码中硬编码权重**。

---

## 一、评分模型

4 个子维度加权合成化石维度总分，+ 12 条规则（按子维分配赋分）：

| 子维 | 权重 | 规则 | 赋分（子维内） |
|:--|:--:|:--|:--|
| 历史遗留 API 与语言方言 | 30% | FOS-001/002/003 | 40/40/20 |
| 死代码与不可达逻辑 | 20% | FOS-004/005/006 | 50/30/20 |
| 重复代码与重复实现 | 20% | FOS-007/008/009 | 50/20/30 |
| 技术债密度与可维护性 | 30% | FOS-010/011/012 | 25/50/25 |

- 子维得分 = max(0, 100 − Σ(该子维命中规则赋分))；
- 化石维度总分 = Σ(子维得分 × 权重)；
- 同一规则在一个项目内只扣一次赋分，出现次数写入明细。

## 二、适用性

`is_fossil=True`（任一）：遗留语言/API 信号；`TODO/FIXME/HACK` 密度 >5/KLOC；死代码/克隆超阈值。  
`is_fossil=False`：维度不适用，`overall=None`，不参与总分。

## 三、12 条规则

| 规则 | 名称 | severity | output_level | 置信度 | 子维 |
|:--|:--|:--:|:--:|:--:|:--|
| FOS-001 | F77 固定格式/`COMMON`/`IMPLICIT` | HIGH | WARNING | 高 | 2.1 |
| FOS-002 | 废弃 C++ API | MEDIUM | WARNING | 高 | 2.1 |
| FOS-003 | K&R C/非标准方言 | MEDIUM | WARNING | 中 | 2.1 |
| FOS-004 | 未引用函数/变量/文件 | MEDIUM | WARNING | 中低 | 2.2 |
| FOS-005 | 不可达分支 | MEDIUM | WARNING | 中 | 2.2 |
| FOS-006 | 成块注释代码 | LOW | INFO/WARNING（>10 行） | 中低 | 2.2 |
| FOS-007 | 函数/文件级克隆 | MEDIUM | WARNING | 中低 | 2.3 |
| FOS-008 | 跨文件重复常量 | LOW | INFO | 中低 | 2.3 |
| FOS-009 | 同一算法多份实现 | MEDIUM | WARNING | 中低 | 2.3 |
| FOS-010 | 债务标记密度 | LOW | INFO | 中 | 2.4 |
| FOS-011 | SQALE 修复成本比率 | MEDIUM | WARNING | 中低 | 2.4 |
| FOS-012 | 遗留模块无测试 | MEDIUM | WARNING | 中低 | 2.4 |

> FOS-013/014 为 KNOWN_HOLES，不计分，不进入规则表。

## 四、豁免体系

| 注解 | 用途 | 影响 |
|:--|:--|:--|
| `@fossil_legacy_ok` | ABI/兼容性保留旧 API | FOS-001/002/003 不计数（影响 scoring） |
| `@fossil_deferred` | 已排期债务 | 仅降一级 output_level |
| `@fossil_not_dead` | 动态引用/FFI/插件 | FOS-004 不计数（影响 scoring） |

- 格式：`/* @fossil_legacy_ok: reason */`；reason 必填，缺失 → 无效。
- 豁免文件占比 >30% → `waiver_audit.abuse_warning`。

## 五、KNOWN_HOLES

- **FOS-013**：跨语言死代码（Fortran/C 符号映射），静态难判。
- **FOS-014**：语义级重复（不同写法同一算法），需 AST/PDG。

## 六、实施映射

| 指南 §2.x | Skill §x | Tool |
|:--|:--|:--|
| §2.1 历史遗留 API | §三 | `_rule_001`/`_rule_002`/`_rule_003` |
| §2.2 死代码 | §三 | `_rule_004`/`_rule_005`/`_rule_006` |
| §2.3 重复 | §三 | `_rule_007`/`_rule_008`/`_rule_009` |
| §2.4 技术债 | §三 | `_rule_010`/`_rule_011`/`_rule_012` |

## 版本历史

| 版本 | 日期 | 变更 |
|:--|:--|:--|
| 1.0 | 2026-11-05 | 首版：4 子维权重、12 规则、适用性、豁免、KNOWN_HOLES、实施映射 |
