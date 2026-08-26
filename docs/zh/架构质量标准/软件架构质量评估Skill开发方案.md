# 软件架构质量评估 Skill 开发方案

**版本**：v1.0（含 20 年架构经验专家校对意见）
**日期**：2026-08-21
**依据**：《基于 OPENCODE 的架构质量评估 SKILL 开发指南》六阶段方法论
**状态**：专家校对通过，编写者确认全部修订意见

---

## 一、目标与范围

将软件架构质量评估从"结构质量完整、其余占位"升级为三方制品齐备的成熟 Skill：
- 指南 2.3 ↔ Skill ↔ 工具 三方一致
- 设计/文档/演进 3 维度（占 70% 权重）从占位实现补全为真实检测
- 新增 SAR-001~012 内置规则检测（对齐指南新增章节）
- 独立于 H1 工作包推进

## 二、现状盘点

| 制品 | 现状 | 缺口 |
|---|---|---|
| 指南 2.3 | 完整（含 SAR 规则），UTF-8 BOM | 缺置信度标注、基线校准章节 |
| 案例集 1.3 | 25 案例 A/B 类，**GBK 编码** | 需转 UTF-8 |
| Skill arch-quality.md | 89 行（仅权重+公式） | 缺检测方法/豁免/规则表/校准/启用条件 |
| 工具 arch_metrics_standard.py | 结构质量完整；设计/文档/演进为占位 | 3 维度占位→完整 + check_sar_rules() |
| 测试 | 仅 test_test_coverage.py | 缺单元/变异/集成/E2E/回归/一致性/harness |
| 智能体 | 无 standard-quality Skill | 未注册 |

## 三、专家校对意见（已确认）

| # | 意见 | 核实依据 | 结论 | 修订动作 |
|---|---|---|---|---|
| 1 | SAR 与 6.6 问题扣分检测条件重复，双重计分 | 指南 6.6(919-922)↔SAR 表(985-993) 逐字相同 | 接受 | SAR 为唯一检测层，6.6 派生扣分 |
| 2 | 设计质量置信度低(中/低)，应最后实现 | 指南 4.1/4.2/4.3 置信度标注 | 接受 | 重排：文档→演进→设计 |
| 3 | 案例集 A 类项目本机无 DBCP/JDK/Spring checkout | D:\OPENSOURCE 盘点 | 接受 | 可用真实验证+不可用合成复现 |
| 4 | check_sar_rules() 须守卫 calc_xxx() 返回 None | 指南 6.1/6.3 N/A 语义；数值 Skill 决策5 | 接受 | N/A 守卫 + 权重再分配组合测试 |
| 5 | 报告生成器 key 契约硬编码 | arch_report_generator.py:258-261 | 接受 | 锁定 solid/patterns/style/anti_patterns |
| 6 | CI 门禁应维度级而非规则级 | 指南 9.2(1052-1054)、4.2(403) | 接受 | C2 对齐 9.2 维度级门禁 |

## 四、执行阶段

### 阶段 0 前置整理（已完成）
- 案例集 1.3 → UTF-8 BOM（已转换，37650→50148 字节）
- 指南 2.3 置信度标注核查（已确认 18 个子维度算法章节全部完整，无需补充）
- 基线校准章节移至阶段 B（Skill 重构时编写，参照数值 Skill §三；数值实践为基线校准属 Skill 而非指南）

### 阶段 A1 文档质量（1-1.5d）
- README(25%)/CHANGELOG(15%)/ADR(20%)/注释密度(15%)/JSDoc(15%)/架构文档(10%)
- 确定性正则检测，key 契约：readme/changelog/adr/comments/jsdoc/arch_doc

### 阶段 A2 演进质量（1-1.5d）
- 历史追溯(16%)/债务趋势(20%)/依赖过时(16%)/废弃代码(12%)/增量质量(16%)/问题扣分(20%)
- GitHistory 扩展 + load_history 复用；无 Git/package.json 返回 None
- key 契约：git_activity/debt_trend/dep_outdated/dead_code/incremental/problems

### 阶段 A3 设计质量（2.5-3d，最后）
- SOLID(40%)/设计模式(25%)/架构风格(20%)/反模式(15%)
- 启发式正则 + GitHistory，低置信度标注；不引入完整 AST
- key 契约：solid/patterns/style/anti_patterns（硬约束）

### 阶段 A4 check_sar_rules()（0.5d）
- 对齐 SAR-001~012；output_level/severity 解耦
- **SAR 为唯一检测源**，6.6 问题扣分从违规派生（映射表）
- 每个 calc 维度 None 守卫

### 阶段 B Skill 重构（1.5d）
- arch-quality.md 89→~300 行：版本绑定/权重/维度算法/基线校准/豁免/SAR 表/跨规则协调/引用/启用条件
- skill-audit 过 A3.5 门禁

### 阶段 C 测试（3-4d）
- test_standard_metrics.py（3 维度 ≥2 用例/维度 + SAR 触发）
- tests/mutation/test_standard_mutation.py + good_project
- test_standard_integration.py + e2e（权重归一化精确断言、key 集断言、0/1/2/3 N/A 组合）
- tests/regression/test_standard_regression.py（5 回归项目）
- 案例验证：OpenFOAM(耦合)/FreeCAD(内聚)/合成(DBCP God Class、JDK 接口、Spring 文档)
- consistency_check.py 追加标准质量检查块
- harness 新增 standard-quality 用例

### 阶段 D 部署（1d）
- .opencode/skills/standard-quality/SKILL.md + opencode.jsonc
- CI 门禁对齐指南 9.2 维度级（结构<60 阻断/跨包循环阻断/设计<50 警告）
- 用户提示词模板 + 报告模板

## 五、硬约束（源自专家校对）

1. SAR 与 6.6 单一事实源
2. 报告生成器 key 契约锁定
3. check_sar_rules() N/A 守卫
4. CI 门禁对齐 9.2 维度级

## 六、验收标准

- 三方一致性 PASS
- 单元/变异/集成/E2E 100%
- 案例集验证无系统性误报
- python -m arch_quality 输出 4 维度真实评分 + sar_violations

---

## 七、执行状态（2026-08-21 全部完成）

| 阶段 | 交付物 | 状态 |
|:-----|:-------|:-----|
| 0 | 案例集转码 / 置信度核查 | ✅ |
| A1 | 文档质量实现 + 16 测试 | ✅ |
| A2 | 演进质量实现 + 14 测试（含 GitHistory 编码修复）| ✅ |
| A3 | 设计质量实现 + 11 测试（含 God Class 类级检测）| ✅ |
| A4 | check_sar_rules() + 7 测试（含惰性 lines 修复）| ✅ |
| B | Skill 重构（9 章）+ skill-audit PASS | ✅ |
| C1 | 变异测试 6 用例（含 God Class Python 支持）| ✅ |
| C2 | 集成/E2E 12 用例（权重/key/N-A/CLI）| ✅ |
| C3 | 回归测试 20 用例 + 5 项目基线 | ✅ |
| C4 | 案例集验证 2 用例 + 一致性检查 PASS | ✅ |
| D | SKILL 注册 + CI 门禁 + 提示词 + 报告模板 | ✅ |

**验收结果**：
- 三方一致性 PASS（scripts/consistency_check_standard.py）
- 全量测试 418 passed
- 案例集 A 类验证通过（FreeCAD Document.cpp / OpenFOAM Tensor.H）
- 综合报告输出 4 维度真实评分 + sar_violations