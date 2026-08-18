# 基于 OPENCODE 的架构质量评估 SKILL 开发指南

> 从数值算法精度保障评估 Skill 的完整开发实践中提炼的可复用方法论
>
> **版本**：1.0  
> **适用范围**：为 arch-quality 体系创建新的评估维度/Skill  
> **前置条件**：熟悉 arch-quality 框架、OpenCode 智能体机制

---

## 目录

- [第一章：概述](#第一章概述)
- [第二章：三方制品规范](#第二章三方制品规范)
- [第三章：阶段 A — 开发（Development）](#第三章阶段-a--开发development)
- [第四章：阶段 B — 测试（Testing）](#第四章阶段-b--测试testing)
- [第五章：阶段 C — 部署（Deployment）](#第五章阶段-c--部署deployment)
- [第六章：质量保障检查清单](#第六章质量保障检查清单)
- [附录 A：数值精度 Skill 开发复盘](#附录-a数值精度-skill-开发复盘)
- [附录 B：opencode.jsonc 完整配置示例](#附录-bopencodejsonc-完整配置示例)
- [附录 C：参考资源与术语表](#附录-c参考资源与术语表)

---

## 第一章：概述

### 1.1 什么是架构质量评估 Skill

架构质量评估 Skill 是 **arch-quality** 体系中封装特定领域评估知识的可复用单元。一个 Skill 包含：

| 组件 | 形式 | 功能 |
|:-----|:-----|:------|
| **领域知识** | `src/arch_quality/skills/xxx.md` | 评分算法、检测方法、规则定义 |
| **评估引擎** | `src/arch_quality/arch_metrics_xxx.py` | 可执行的静态分析代码 |
| **标准定义** | `docs/zh/xxx评估指南.md` | 维度定义、评分标准、行业标准映射 |
| **验证数据** | `docs/zh/xxx验证案例集.md` | 阳/阴性案例，用于验证工具正确性 |
| **智能体文件** | `.opencode/skills/xxx/SKILL.md` | OpenCode 智能体注册入口 |

### 1.2 三方制品体系

每个 Skill 由三个层次的制品构成，它们之间存在严格的**派生与对齐关系**：

```
+------------------+    抽象层次最高
|  指南（Guide）    |    定义"应该评估什么"
|  文档 .md         |    评分公式（自然语言）
|                   |    NVR/MLR 规则定义
+--------+---------+    行业标准映射
         | 翻译与工程化
         v
+------------------+    中间层次
|  Skill 文件       |    定义"如何评估"
|  评分算法         |    评分算法（可执行伪代码）
|  检测方法         |    关键词列表、正则模式
|  豁免注解         |
+--------+---------+
         | 实现
         v
+------------------+    可执行层次
|  评估工具（Tool） |    定义"实际执行的代码"
|  .py 代码         |    calc_xxx() 方法
|                    |    check_nvr_rules()
+------------------+
```

**关键规则**：三者必须保持一致性。修改任一方时，必须同步更新其他两方。

### 1.3 Skill 全生命周期

整个开发流程分为 6 个阶段，对应 17 个 OpenCode 交互提示词：

```
阶段 A：开发 -------------------------------------------------
  A1 初始化结构 --> A2 定义维度 --> A3 定义规则
                                      ↓
                               A3.5 SKILL 文件质量审查 ← 门禁
                                      ↓
                                    A4 实现工具
                                                    |
阶段 B：测试 -------------------------------------------------
  B1 单元测试 --> B2 变异测试 --> B2.5 集成 & 端到端测试
                                       ↓
                                B2.6 Agent Harness 验证（agent行为）
                                       ↓
                                B3 外部验证基线（回归守护）
                                       ↓
                                B3.5 开源项目验证（正确性）← 新增
                                       ↓
                                     B4 一致性
                                                    |
阶段 C：部署 -------------------------------------------------
  C1 注册智能体 --> C2 CI/CD --> C3 用户提示词 --> C4 报告
```

### 1.4 参考实例概览

本指南全程以**数值算法正确性与精度保障评估 Skill** 的实践经验作为参考实例。该 Skill 的核心参数：

| 参数 | 值 |
|:-----|:------|
| 评估维度 | 6（数值稳定性/舍入误差/MMS/误差估计/回归/债务）|
| NVR 规则 | 12 条 |
| 指南版本 | 1.0 --> 1.8 |
| Skill 版本 | 1.0 --> 1.6 |
| 工具代码 | 890 行 |
| 验证项目 | 10 个开源项目 |
| 测试用例 | 22 单元 + 6 变异 + 38 回归 |
| 开发总周期 | ~4 周 |

---

## 第二章：三方制品规范

### 2.1 指南（Guide）文件模板

指南是 Skill 的最高层次标准定义，应由领域专家编写。

#### 标准结构

```
# [领域]评估指南（[版本号]版）

## 概述
   评估目标、适用范围、行业标准映射
   版本核心更新说明
## 置信度说明
   高/中/低三级置信度定义与使用建议
## 一、子维度与权重分配
   维度表格：名称 | 权重 | 风险类型 | 置信度
## 二、子维度定义与评分算法
   ### 2.1 [维度1名称]
       定义、置信度、评分算法（公式）、置信度说明
   ### 2.2 [维度2名称]
   ...
## 三、综合分计算
   S = sum(维度得分 x 权重)
## 四、分数分级
   优秀/良好/需改进/危险 四个等级
## 五、内置规则
   规则清单总览表
   各规则详细描述
## 六、与现有标准/指南的映射
## 七、实施建议
## 版本历史
```

#### 评分公式编写规范

- 公式使用伪代码格式，以 `let` 声明变量
- 评分区间固定为 0-100
- 每条公式必须附带置信度说明
- 公式中的阈值必须标注来源（文献/经验值/校准）

#### 参考实例

```
指南 x2.4 解验证与误差量化（v1.7）的评分公式：

let E_d = 离散化误差是否被估计（TRUE/FALSE）
    E_i = 迭代误差是否被估计（TRUE/FALSE）

score = (E_d x 50) + (E_i x 50)
```

### 2.2 Skill 文件模板

Skill 文件是介于指南和代码之间的工程翻译层，由评分算法设计者编写。

#### 标准结构

```
# [领域]评估技能

> 版本绑定
> - 对应指南：[版本]
> - 对应实现：[文件名]
> - 技能版本：[版本号]

## 一、权重分配
   与指南一致的维度权重表
## 二、维度定义与评分算法
   ### 2.1 [维度1]（权重%）
       代码坏味道名称、检测方法、评分算法（可执行伪代码）
   ### 2.2 [维度2]
   ...
## 三、基线校准
   校准数据来源表、校准方法（统计流程）
## 四、豁免注解体系
   注解类型表、格式定义、验证规则
## 五、NVR/MLR 规则
   规则总览表
## 六、跨规则协调
## 七、引用关系总表
## 八、启用条件
## 九、版本历史
```

#### 关键编写原则

1. **评分算法必须可执行**：Skill 中的伪代码应能直接翻译为 Python 代码
2. **检测方法必须可操作**：列出具体的关键词列表、正则模式、目录命名约定
3. **阈值必须标注来源**：区分"文献支撑""工程经验""校准待定"

#### 参考实例

数值精度 Skill x2.4 的翻译差异：
- 指南公式：`E_d x 50 + E_i x 50`（二值）
- Skill 公式：`mesh(40) + residual(30) + tol(30)`（多因子）
- 差异原因：指南公式不可直接执行（"离散化误差是否被估计"无法通过静态分析判定）
- 在 skill x7 引用表中标注为"评分算法为独立编写"

### 2.3 评估工具（Tool）类结构模板

工具代码遵循 `arch-core` 框架的标准模式。

#### 类结构

```python
class [Domain]Metrics:
    def __init__(self, root: str):
        self.root = root
        self.index = FileIndex(root)
        self._detect_[domain]()
        self._scan_[domain]_files()

    def calc_dimension_1(self) -> tuple:
        ...

    def check_rules(self) -> list:
        ...

    def all_metrics(self) -> dict:
        ...
```

#### 方法返回格式

每个 `calc_xxx()` 方法返回 `(score, detail_dict)` 元组：

| 字段 | 类型 | 说明 |
|:-----|:-----|:------|
| score | float 或 None | 0-100 的评分。None 表示该维度不适用 |
| detail | dict | 包含评分过程和中间值；key 必须与 Skill 文件中的检测项对应 |

---

## 第三章：阶段 A — 开发（Development）

### 提示词 A1：初始化 Skill 结构

**适用阶段**：开发  
**调用时机**：开始编写新 Skill 时，生成文件骨架  
**发送给**：architecture-quality 智能体

#### 提示词正文

> 你是一个架构质量评估技能开发助手。
> 请帮我为一个新的评估领域生成 Skill 文件的标准骨架。
>
> **领域信息**：
> - 技能名称：[待填充]
> - 评估维度数：[N]
> - 每个维度名称：[维度1]、[维度2]...
> - 对应指南版本：[v1.0]
>
> **要求**：
> 1. 生成符合 src/arch_quality/skills/ 目录规范的 .md 文件骨架
> 2. 包含版本绑定头、x1 权重表、x2 各维度方法签名占位
> 3. 包含 NVR/MLR 规则表占位（至少比维度数多 2 条）
> 4. 包含 x9 版本历史
>
> **输出格式**：完整的 .md 文件内容

#### 用户输入表

| 参数 | 示例值 | 说明 |
|:-----|:-------|:------|
| 技能名称 | numerical-accuracy | 作为文件名和代码中的标识符 |
| 评估维度数 | 6 | 建议 3-8 个维度 |
| 维度名称 | 数值稳定性保障 | 每个维度 4-12 字 |
| 维度权重 | 25%,20%,20%,15%,10%,10% | 总和 = 100% |
| 前置检测 | _detect_numerical() | 如何判断该领域是否适用 |

#### 参考实例

数值精度 Skill 的版本绑定头：

```
> **版本绑定**
> - 对应指南：**1.8 版**
> - 对应实现：arch_metrics_numerical_accuracy.py
> - 技能版本：**1.6**
```

---

### 提示词 A2：定义评估维度与评分算法

**适用阶段**：开发  
**调用时机**：已有指南公式后，将其翻译为 Skill 可执行算法  
**发送给**：architecture-quality 智能体

#### 提示词正文

> 我需要将指南中的评分公式翻译为 Skill 中的可执行算法。
>
> **输入**：
> - 维度名称：[名称]
> - 权重：[N%]
> - 指南原文公式：[自然语言描述]
> - 可用的检测手段：[关键词列表/正则模式/图分析/AST]
>
> **要求**：
> 1. 将指南的自然语言公式翻译为可执行的分段函数
> 2. 每个阈值标注来源
> 3. 输出格式为代码块
>
> **质量检查**：
> - 每条分支是否有明确条件
> - 极端输入是否合理
> - 评分区间是否严格 0-100

#### 决策树分析（指南到Skill 翻译）

| 指南公式类型 | Skill 翻译策略 |
|:-------------|:---------------|
| 二值判定 (TRUE/FALSE) | 分段函数 + 多因子细化 |
| 连续值公式 | 直接实现，注意边界条件 |
| 文本描述规则 | 分解为可检测的具体子项 |
| 聚合计算 | 明确聚合粒度和单位 |

#### 参考实例

数值精度 Skill 的决策 1：评分公式独立编写

```
指南 x2.4 原文：
  score = E_d x 50 + E_i x 50
  其中 E_d = 离散化误差是否被估计（TRUE/FALSE）
       E_i = 迭代误差是否被估计（TRUE/FALSE）

问题："是否被估计"无法通过静态分析判定

Skill 翻译结果：
  score = 0
  if 网格收敛性研究存在:   score += 40
  if 残差控制存在:          score += 30
  if 容差合理 (1e-4~1e-12): score += 30

决策类型：二值判定 --> 多因子细化
代价：与指南公式不一致
```

---

### 提示词 A3：定义 NVR/MLR 规则

**适用阶段**：开发  
**调用时机**：维度定义完成后，设计对应规则  
**发送给**：architecture-quality 智能体

#### 提示词正文

> 我需要为评估维度中的问题定义 NVR（或 MLR）规则。
>
> **输入**：
> - 所属维度：[名称]
> - 规则数量：[N] 条
>
> **规则设计原则**：
> 1. 每条规则对应一个可自动检测的代码坏味道
> 2. output_level 与 severity 解耦
> 3. 高置信度规则使用 ERROR 级别，可作 CI 阻断
> 4. 中低置信度规则使用 WARNING 或 INFO
> 5. 每条规则必须有明确的触发条件和豁免可能性
>
> **输出格式**：规则总览表 + 逐条详细描述

#### 规则设计矩阵

| 设计维度 | HIGH severity | MEDIUM severity | LOW severity |
|:---------|:-------------|:---------------|:-------------|
| ERROR | 阻断性问题 | — | — |
| WARNING | 需优先处理 | 需关注 | — |
| INFO | 参考信息 | 参考信息 | 低优先 |

#### 参考实例

数值精度 12 条 NVR 规则的 output_level 分布：

```
ERROR (4条): NVR-001 稳定性溢出, NVR-003 相消损失, NVR-005 MMS缺失, NVR-006 观察阶偏差
WARNING (5条): NVR-004 累积误差, NVR-007 离散误差, NVR-008 迭代误差, NVR-010 回归缺失
INFO (2条): NVR-011 回归断言, NVR-012 债务密度
```

---

### 提示词 A3.5：SKILL 文件质量审查

**适用阶段**：开发  
**调用时机**：A3 规则定义完成后，A4 工具实现之前  
**发送给**：skill-audit 智能体（需注册）

#### 问题背景

在求解器物理场模块化架构 SKILL 开发实践中，文档编写完成后发现了多类问题，包括：
- **§2↔§5 不一致**：MPR 规则的检测逻辑与对应 §2 子项的评分算法不匹配，同一条件同时出现"满分"和"告警"的矛盾
- **设计合理性**：同一特征在多个维度重复计分（如 FMI 跨 L1/L2/L3 三层）
- **可执行性**：关键词过于通用导致静态分析误报（如 `coupling` 匹配大量无关文件）
- **完整性**：使用了非法的 output_level/severity 值（如 `BONUS`）

为在开发的早期阶段拦截这类问题，在 A3 与 A4 之间引入质量门禁步骤。

#### 审查提示词正文

> 请对这份 SKILL 文件进行质量审查，检查以下 6 个维度：
>
> **项目信息**
> - SKILL 文件路径：[路径]
> - 评估维度数：[N]
> - MPR/NVR 规则数：[M]
>
> **审查清单**
>
> **1. 结构完整性**
> - [ ] 版本绑定头是否存在（GUIDE_VERSION、SKILL_VERSION 声明）
> - [ ] 权重表是否存在且格式可被方案D解析（`| 维度 | N% |`）
> - [ ] 权重和是否 = 100%
> - [ ] 每个维度是否包含：代码坏味道、检测方法、评分算法、置信度说明
> - [ ] 每条规则是否包含：output_level、severity、置信度、检测逻辑、改进建议
>
> **2. §2 评分算法 ↔ §5 规则一致性（高频问题区）**
> - [ ] 每条 MPR 规则是否有对应的 §2 子项引用
> - [ ] MPR 触发条件是否与对应子项的评分档位对齐（评分得满分时是否仍被规则触发？）
> - [ ] MPR 检测逻辑是否比对应子项的评分算法更严格或更宽松？若是，为有意设计还是遗漏？
> - [ ] 每个"二值判定"的子项：评分得 0 时是否对应 MPR 触发？
>
> **3. 设计合理性**
> - [ ] 是否存在同一特征在多个维度中重复计分？
> - [ ] 递进扣分规则是否有实证依据？
> - [ ] 阈值是否明确？是否存在"高度分散""合理范围"等模糊表述？
> - [ ] severity 与 output_level 的解耦是否正确？
>
> **4. 可执行性**
> - [ ] 每个检测方法是否可以通过静态代码分析实现？
> - [ ] 关键词检测是否存在过于通用导致误报的风险？（如 `coupling`）
> - [ ] 检测方法的置信度标注是否与实际情况匹配？
>
> **5. 完整性**
> - [ ] 是否存在缺失的检测项？（指南定义但 SKILL 未覆盖）
> - [ ] MPR 规则是否覆盖了所有 §2 中得分为 0 的子项？
> - [ ] 启用条件是否明确定义且可自动检测？
>
> **6. 跨规则协调**
> - [ ] 关联规则是否声明了依赖关系（如 MPR-001 ↔ MPR-003）
> - [ ] 跨维度扣分规则是否明确计算方法？
> - [ ] 与本体系其他 Skill 的边界是否划清（如 MPR-006 与数值精度 NVR-003/004）
>
> **判定标准**
>
> | 结果 | 条件 | 后续动作 |
> |:----:|:-----|:---------|
> | PASS | 全部 6 项无 FAIL | 进入 A4 工具实现 |
> | WARNING | 仅 4-5 项有 WARNING | 修复 WARNING 后进入 A4 |
> | FAIL | 任一项有 FAIL，或 ≥2 项 WARNING | 修复后才能进入 A4 |
>
> **输出格式**
>
> ```
> 审查结果：PASS / WARNING / FAIL
>
> 1. 结构完整性：[PASS/WARNING/FAIL]
>    [发现的问题列表]
>
> 2. §2↔§5 一致性：[PASS/WARNING/FAIL]
>    [发现的问题列表]
>
> ...
>
> 总体评价：[总结性意见]
>
> 修复建议（按优先级排列）
> - P0: [必须修复的问题]
> - P1: [建议修复的问题]
> - P2: [可选优化]
> ```

#### 审查智能体注册

审查智能体配置文件 `.opencode/skills/skill-audit/SKILL.md`：

```yaml
---
name: skill-audit
description: >
  架构质量评估 SKILL 文件质量控制审查。Use after writing a SKILL.md file
  to check for dimensional consistency, rule-scoring alignment, threshold
  completeness, and detection feasibility before proceeding to implementation.
  Covers 6 audit dimensions.
---
```

#### 审查记录规范

每次审查结果应写入开发日志，记录以下信息：

| 字段 | 示例 |
|:-----|:------|
| 审查日期 | 2026-07-30 |
| SKILL 文件 | solver-physics-architecture.md |
| 审查结果 | WARNING |
| 发现的问题 | MPR-006 检测逻辑比 §2.2 子项4 严格；MPR-008 阈值偏移 |
| 修复动作 | 调整 §2.2 子项4 评分算法为三档；MPR-008 分 1-2/≥3 循环两档 |
| 审查耗时 | 20 分钟 |

#### 参考实例

以下问题来自求解器物理场模块化架构 SKILL 的开发实践：

| 问题类型 | 实例 | 后果 |
|:---------|:-----|:------|
| §2↔§5 不一致 | MPR-006 检测逻辑含精度和迭代上限检查，但 §2.2 子项 4 只看"存在收敛参数"就给满分 | 出现"评分满分+规则触发"的矛盾 |
| §2↔§5 不一致 | MPR-008 只要有循环就 ERROR，但 §2.3 子项 3 对 ≤2 循环还给 10 分 | 评分与规则对"严重程度"判定不一致 |
| 设计合理性 | FMI 在维度 1（+10 加分）、维度 4（15 分评分项 +5 附加分）中重复计分 | 同一特征的权重被夸大 |
| 可执行性 | `coupling` 关键词匹配到 MLR 规则名、代码注释等无关上下文 | 多物理场项目检测误报 |
| 完整性 | MPR-FMI 使用了非法的 `BONUS` 级别（有效值：ERROR/WARNING/INFO） | 工具无法解析该规则 |

---

### 提示词 A4：实现评估工具

**适用阶段**：开发  
**调用时机**：Skill 文件编写完成后，生成评估工具的 Python 代码骨架  
**发送给**：architecture-quality 智能体

#### 提示词正文

> 请根据 Skill 文件中的评分算法定义，生成评估工具的 Python 代码。
>
> **输入**：
> - Skill 文件路径：[路径]
> - 工具类名：[类名]
> - 使用的检测方法：[关键词匹配/正则/图分析/AST]
>
> **代码生成规范**：
> 1. 每个 calc_xxx() 方法返回 (score, detail_dict)
> 2. 正则模式定义在文件顶部常量区
> 3. 检测关键词定义在文件顶部常量区
> 4. 调用 FileIndex 扫描文件，_has_keyword 检查内容
> 5. 无匹配时返回 (None, {}) 而非 0 分
> 6. 包含命令行入口 main() 函数

#### 返回格式规范

```python
# (score, detail) 返回格式
(70.0, {
    "score": 70.0,
    "key_finding_1": 42,
    "key_finding_2": True,
})
```

#### 参考实例

数值精度工具的 `calc_error_estimation()` 方法签名（仅保留架构）：

```python
def calc_error_estimation(self) -> tuple:
    """2.4 误差估计与控制 (15%)"""
    if not self._has_numerical:
        return None, {}
    # 检查项目是否实际包含求解器代码
    has_solver_code = any(...)
    if not has_solver_code:
        return None, {}
    # 三项检查：网格收敛性 + 残差控制 + 容差合理性
    ...
    score = 0
    if combined_mesh:    score += 40
    if has_residual:      score += 30
    if reasonable_tol:    score += 30
    return score, { "score": score, ... }
```

#### 交付物：工具设计文档

A4 实现工具代码后，应同步编写**工具设计文档**，将指南算法与工具实现显式映射。这是三方一致性的工程层文档，回答"工具如何实现指南算法、工程化偏差在哪、检测正则是如何设计的"。

**文档结构**（8 章）：

| 章节 | 内容 |
|:-----|:-----|
| 1. 设计概览 | 设计目标、架构定位、技术选型 |
| 2. 整体架构 | 类结构、缓存机制、数据流、性能优化 |
| 3-6. 四个维度 | 每个维度：指南算法原文 → 工具实现映射（检测正则级）→ 工程化偏差 |
| 7. MPR 映射 | 11 条 MPR → 对应子项、触发条件与评分档位对齐表 |
| 8. 映射总表 | 四维度分值映射总表 + 一致性检查方法 + 已知局限 |

**核心要求**：

- 映射粒度到**检测正则级别**（每条正则的来源、用途、误报教训）
- 记录**设计决策**（含 B 阶段验证中发现并修复的正则缺陷）
- 说明**工程化偏差**（指南算法 → 工具实现的转换及原因）

**参考实例**：求解器物理场工具设计文档记录了 B3.5 验证中的正则修复决策——`fixed_point` 从强耦合投票移入 partitioned_iterative 架构判定、排除 MPI 广播误匹配等。

**用户提示词**：

> 请为评估工具编写工具设计文档，将指南算法与工具实现显式映射。
>
> **输入**：
> - 指南文件：[docs/zh/xxx评估指南.md]
> - 工具代码：[arch_metrics_xxx.py]
> - Skill 文件：[skills/xxx.md]
>
> **要求**：
> 1. 覆盖 4 个维度，每个维度含：指南算法原文 → 工具实现映射（检测正则级）→ 工程化偏差
> 2. 映射粒度到检测正则级别，记录每条正则的来源和误报教训
> 3. 记录设计决策（含 B 阶段验证中发现的缺陷修复）
> 4. 输出格式：Markdown 文档，与指南放在同一目录

---

### 提示词 B1：生成单元测试

**适用阶段**：测试  
**调用时机**：评估工具实现完成后  
**发送给**：architecture-quality 智能体

#### 提示词正文

> 请为评估工具生成 pytest 单元测试用例。
>
> **输入**：
> - 工具文件：[路径]
> - 维度数：[N]
> - 支持的检测模式：[正则/关键词/图分析]
>
> **测试覆盖要求**：
> - 每个 calc_xxx() 至少 2 个测试：正常检测 + 未命中检测
> - 每个 NVR/MLR 规则至少 1 个测试：触发条件验证
> - 1 个综合测试：all_metrics() 返回格式正确
> - 1 个非数值项目测试：_detect 返回 False 时所有评分 None
> - **抽样一致性测试**（若工具含文件抽样）：全量 vs 强制抽样的维度得分偏差在阈值内、计数型检测外推误差受控、布尔型检测判定不变
>
> **测试结构**：
> ```python
> class Test[维度] (unittest.TestCase):
>     def test_[场景1](self): ...
>     def test_[场景2](self): ...
> ```

#### 参考实例

数值精度 22 个单元测试的类结构：

```
TestHelperFunctions          — 2 个测试：正则模式匹配检测
TestNonNumericalProject      — 3 个测试：非数值项目返回 None
TestNumericalProjectBasic    — 2 个测试：基础检测
TestNumericalStability       — 2 个测试：稳定性评分
TestRoundoffSensitivity      — 1 个测试：Kahan 求和
TestMMSVerification          — 2 个测试：MMS 检测
TestNVRRules                 — 4 个测试：NVR 触发条件
TestAllMetricsIntegration    — 1 个测试：综合评分
TestFortranSupport           — 5 个测试：Fortran 特殊处理
```

---

### 提示词 B2：生成变异测试

**适用阶段**：测试  
**调用时机**：单元测试完成后  
**发送给**：architecture-quality 智能体

#### 提示词正文

> 请为评估工具生成变异测试用例。变异测试通过在好代码中故意引入缺陷，验证工具能检出这些缺陷。
>
> **输入**：
> - 工具文件：[路径]
> - 已有单元测试：[路径]
> - 需要变异的维度：[列表]
> - 需要变异的规则：[列表]
>
> **每个变异测试包含**：
> 1. 一个合成测试项目（good_project）的源码框架
> 2. 对 good_project 运行工具，得到基线评分
> 3. 引入一个变异（删除关键词/修改配置/删除文件）
> 4. 再次运行工具，验证评分下降或 NVR 新增触发
> 5. 清理临时文件
>
> **变异测试类型**：
> - MUT-xxx-01: 删除关键词（如 CFL -> NVR-001）
> - MUT-xxx-02: 删除代码块（如 Kahan 函数 -> NVR-004）
> - MUT-xxx-03: 删除文件（如 MMS 文件 -> NVR-005）
> - MUT-xxx-04: 引入坏模式（如 a-b 语句 -> NVR-003）

#### 参考实例

数值精度 6 个变异测试的测试框架：

```
tests/mutation/
  __init__.py
  mutation_cases.json     — MUT-001 到 MUT-006 的定义
  projects/good_project/  — 合成测试项目
    src/solver.cpp        — 含 CFL/Kahan/残差等良好实践
    tests/mms_test.cpp    — MMS 验证文件
    tests/test_solver.cpp — 带断言的测试文件
  test_numerical_mutation.py — 变异测试执行器
```

---

### 提示词 B2.5：生成集成测试与端到端测试

**适用阶段**：测试  
**调用时机**：变异测试通过后，外部验证基线之前  
**发送给**：architecture-quality 智能体

#### 问题背景

数值精度和求解器物理场 SKILL 的开发实践中，以下问题在变异测试阶段无法发现：
- `ComprehensiveReport` 合并新维度评分时权重归一化逻辑出错
- MPR 违规列表合并到主报告时结构损坏
- 多个增强维度同时激活时权重和不为 100%
- CLI 输出 JSON 不符合预期 schema

这些问题涉及的是**组件间的交互**（集成测试）和**完整管道的输出**（端到端测试），需要专门的测试类型来覆盖。

#### 集成测试（Integration Tests）

测试组件间的交互，确保各部件组合后正常运行：

```python
# 示例：测试 SolverPhysicsMetrics 集成到 ComprehensiveReport
def test_integration_with_comprehensive_report():
    report = ComprehensiveReport(test_project)
    data = report.generate()
    # 验证新维度已合并到 structural 下
    assert "solver_physics_enhancement" in data["dimensions"]["structural"]
    # 验证 MPR 违规已合并到主列表
    assert any(v["rule"].startswith("MPR") for v in data["mlr_violations"])
    # 验证权重归一化后总和为 100%
    structural = data["dimensions"]["structural"]
    total_weight = (structural.get("weight", 0)
                    + structural.get("multilang_enhancement", {}).get("weight_applied", 0)
                    + structural.get("template_enhancement", {}).get("weight_applied", 0)
                    + structural.get("numerical_enhancement", {}).get("weight_applied", 0)
                    + structural.get("solver_physics_enhancement", {}).get("weight_applied", 0))
    assert abs(total_weight - 1.0) < 0.01
```

**需要测试的集成点**：

| 集成点 | 验证内容 | 示例错误场景 |
|:-------|:---------|:-------------|
| 权重解析集成 | `load_weights_from_skill()` 返回的权重与 `all_metrics()` 中使用的权重一致 | 权重表格式被破坏时未抛出 ValueError |
| 报告合并集成 | 新维度评分正确合并到 `dimensions.structural` 下 | 新增增强维度后 key 名冲突或覆盖 |
| MPR 合并集成 | 新维度的 MPR 规则正确追加到 `mlr_violations` 列表 | 重复归并或遗漏 |
| 权重归一化 | 多增强同时激活时归一化权重和 = 100% | 4 增强同时激活时和为 110% 未归一化 |

#### 端到端测试（End-to-End Tests）

测试完整 CLI 管道的输出，从入口到 JSON/报告：

```python
# 示例：验证 all_metrics() 的完整输出结构
def test_e2e_all_metrics_structure():
    m = SolverPhysicsMetrics(test_project)
    result = m.all_metrics()
    # 验证顶层字段
    assert "overall" in result
    assert "is_multiphysics" in result
    assert "dimensions" in result
    assert "mpr_violations" in result
    # 验证 4 维度完整
    for dim in ["boundary_integrity", "coupling_architecture",
                "extension_support", "data_transfer"]:
        assert dim in result["dimensions"]
        d = result["dimensions"][dim]
        assert "score" in d
        assert "detail" in d
    # 验证 MPR 违规结构
    for v in result["mpr_violations"]:
        assert "rule" in v
        assert "severity" in v
        assert "output_level" in v
        assert "detail" in v
```

**需要测试的场景**：

| 场景 | 预期输出 | 验证重点 |
|:-----|:---------|:---------|
| 合成多物理场项目 | `is_multiphysics=True`，4 维度评分非 None | 检测 + 评分 + 规则全链路 |
| 非多物理场项目（纯 Python）| `is_multiphysics=False`，各维度 None | 降级逻辑正确 |
| 非多物理场项目（但含关键词）| `is_multiphysics=False` | 避免关键词误报 |
| CLI JSON 输出 | 合法 JSON，含 all_metrics() 全部字段 | 序列化无异常 |

#### 用户提示词

> 请为评估工具生成集成测试与端到端测试用例。
>
> **输入**：
> - 工具文件：[路径]
> - 报告集成文件：arch_report.py
> - 权重解析文件：arch_core.py
>
> **集成测试覆盖要求**：
> - 每个集成点至少 1 个测试
> - 使用合成项目而非真实项目（避免外部依赖）
>
> **端到端测试覆盖要求**：
> - 多物理场项目场景
> - 非多物理场项目场景（含误报边界测试）
> - CLI 输出格式验证

#### 测试代码质量要求（集成与端到端）

测试代码本身也是代码，同样需要质量保证。以下要求用于防止"测试代码自圆其说"（期望值从实现反推）和"弱断言掩盖错误"。

**集成测试质量要求**：

| 要求 | 检查方式 |
|:-----|:---------|
| 每个集成点有**精确值断言**（≥L2），如权重归一化断言具体数值（0.1364）而非仅"和为1" | 代码审查 |
| 装配层测试用**固定 mock 输入**，区分"组件错"与"装配错" | mock 各组件 all_metrics() 返回已知值，验证合并公式 |
| 覆盖 **0/1/2/3/4 种增强组合**的合并语义（含"3 增强但 ml 不激活"的边界） | 参数化组合测试 |
| 每个集成点有阳性 + 阴性用例 | 审查 |

**端到端测试质量要求**：

| 要求 | 检查方式 |
|:-----|:---------|
| 结构断言含**字段类型检查**（不仅是 key 存在）：`assertIsInstance(score, (int, float))` + 范围检查 | 审查 |
| **复用回归基线项目做结构冒烟**（真实项目不崩溃），不验分值只验结构 | pytest，复用回归缓存 |
| 覆盖**多物理场/非多物理场/边界降级**三类路径（空项目、单求解器、C++ 非求解器）| 审查 |

**期望值来源审计**（防"自圆其说"）：
- 单元测试期望值 ← skill.md 评分算法
- 集成测试期望值 ← ComprehensiveReport 合并公式（可独立手算）
- 端到端测试期望值 ← all_metrics() 输出 schema

禁止从被测函数返回值反推期望值。

**参考实践**：求解器物理场 SKILL 开发中，精确断言暴露了 `arch_report.py` 的 3 增强组合 bug（`enhancement_raw[3]` 预设组合不含 sp，导致 sp 权重被忽略）。弱断言（仅查"和为1"）无法捕获此问题。

---

### 提示词 B2.6：Agent Harness 验证

**适用阶段**：测试  
**调用时机**：集成与端到端测试通过后，外部验证基线之前  
**发送给**：architecture-quality 智能体

#### 问题背景

B1-B2.5 的测试对象都是**工具代码**（评分算法、规则检测、报告合并），验证的是"工具算得对"。但架构质量评估的最终执行者是 **`architecture-quality` 智能体（agent）**——由 LLM 在 ReAct 循环中编排工具完成任务。LLM 存在三类脆弱点：

| 脆弱点 | 表现 |
|:-------|:-----|
| **幻觉** | 编造不存在的工具、参数，甚至编造执行结果 |
| **选错工具** | 该调评估命令时去读源码，该读文件时去跑命令 |
| **无法自愈** | 遇到错误反复重试同一步，陷入死循环 |

pytest 无法验证 agent 的编排行为（它不驱动 LLM）。**Agent Harness** 填补这一空白：验证"agent 用得好"。

**与 B2.5 的关系**：B2.5 验证工具集成到 `ComprehensiveReport` 的正确性（合成数据），B2.6 验证真实 agent 在这些工具上能否正确编排（LLM 驱动）。

#### 核心概念

```
Agent = Model + [上下文 + 工具 + 约束 + 验证 + 纠正]
                    └──────── Harness ────────┘
```

- **上下文 + 工具**：Agent 本身（LLM + 可调用工具集）
- **约束 / 验证 / 纠正**：Harness 保障层（工程外壳），分别防越界、查错误、救异常

**验证独立性原则**（最关键）：断言必须由"看得到事件流的一方"执行——框架插件 hook 或外部 runner。**不能交给 LLM 自证**（被验证者不能给自己的试卷打分，LLM 看不到完整工具调用序列）。

#### 提示词正文

> 请为评估工具搭建 Agent Harness 验证基架，验证 `architecture-quality` 智能体在真实项目上的编排行为。
>
> **输入**：
> - 目标 agent：`architecture-quality`（需注册为 `mode: primary`）
> - 验证对象：agent 是否正确编排工具（执行评估命令、无越权写、无死循环、输出结构正确）
> - 用例（合成项目）：
>   - 阳性：多物理场项目 → 期望触发评估、输出 4 维度评分
>   - 阴性：单求解器项目 → 期望判定非多物理场
>   - 阴性：纯 Markdown 项目 → 期望判定非多物理场
>
> **要求**：
> 1. 外部 runner：`opencode run --agent <name> --format json` 驱动 + 解析事件流 + 断言器
> 2. 规则单一事实源：`rules.json`（Python 断言器与 JS 插件 hook 共享，避免规则漂移）
> 3. 断言器至少覆盖：工具选择（是否执行评估命令）/ 越权写 / doom_loop / 输出结构 / 评分区间
> 4. 纠正：超时或断言失败自动重试（最多 2 次）
> 5. 验证：全部用例 PASS

#### 关键实现要点（实战经验）

| 要点 | 说明 |
|:-----|:-----|
| **agent 需 `mode: primary`** | 全局配置优先于项目配置；subagent 不能被 `--agent` 直接驱动（会 fallback）|
| **事件流结构** | `--format json` 输出 JSONL：`part.type=="tool"`、`part.tool`、`state.{status,input,output}` |
| **环境变量前缀** | `$env:PYTHONIOENCODING=...; python -m ...` 需剥离前缀再匹配白名单 |
| **SyntaxWarning 污染** | Python 3.12+ 对未加 r 前缀的正则字符串发警告，刷屏污染 stdout，提取报告时需剥离 |
| **评估结果位置** | agent 常把评估 JSON 放在 bash 工具 output（非 text 事件），提取报告需两者兼顾 |
| **LLM 随机性** | 同一 prompt 每次工具序列可能不同，需重试 + 断言兜底 |

**两层验证架构**（推荐）：
- **插件 hook**（`.opencode/plugins/agent-assert.js`）：进程内 `tool.execute.before/after` 自动断言，框架级兜底，任何 opencode 会话生效
- **外部 runner**（`opencode-harness/harness_runner.py`）：用例级端到端断言 + 报告落盘 + 重试管理

**与 B3.5 的区别**：

| | B2.6 Agent Harness | B3.5 开源项目验证 |
|:--|:-------------------|:------------------|
| 验证对象 | **agent 行为**（编排正确性）| **工具代码**（检测正确性）|
| 驱动 | `opencode run --agent`（LLM）| `all_metrics()`（无 LLM）|
| 断言内容 | 工具序列 / 越权 / 死循环 | 案例集预期匹配 |
| 发现的问题 | 幻觉 / 选错工具 / 无法自愈 | 误报 / 漏报 |

#### 参考实践

求解器物理场 SKILL 开发中，Agent Harness 验证 3 用例端到端 PASS，并额外发现 `arch_report.py` 缺 `ReportGenerator` 导入的真实 bug（NameError）——agent 正确识别了工具链缺陷，harness 验证了 agent 行为。详见《agent-harness 验证基架》知识卡片。

---

### 提示词 B3：生成外部验证基线

**适用阶段**：测试  
**调用时机**：单元测试和变异测试通过后（初始基线建立）  
**发送给**：architecture-quality 智能体

#### 问题背景

B3 的提示词描述的是**初始基线建立**这一一次性动作。但基准回归测试的真正价值在于**持续守护**——在后续开发维护中反复运行，防止评分漂移。单元/变异测试是静态守护（针对合成项目），回归测试是动态守护（针对真实项目基线），两者互补。

#### 回归测试的持续调用时机

| # | 调用时机 | 触发场景 | 目的 | 频率 |
|:-:|:---------|:---------|:-----|:----:|
| 1 | **初始基线建立**（本节） | 单元+变异测试通过后，首次在真实项目运行 | 建立基线快照 | 一次性 |
| 2 | **工具代码修改后** | 修改 `arch_metrics_xxx.py` 评分算法或检测逻辑 | 验证评分未漂移 | 每次改动 |
| 3 | **Skill 权重/阈值调整后** | 修改 `skills/*.md` 权重表或评分阈值 | 验证新权重不破坏旧基线 | 每次改动 |
| 4 | **指南版本升级后** | 指南升版导致评分算法变化 | 确认偏移在预期范围内 | 版本发布时 |
| 5 | **CI/CD 流水线** | 每次 commit/PR | 自动守护基线 | 持续 |
| 6 | **发布前最终验证** | 版本发版前 | 全量回归 | 发版时 |
| 7 | **基线更新** | 项目源码演进导致预期行为变化 | 用 `ARCH_REGRESSION_UPDATE=1` 重建基线 | 按需 |

**决策指引**：

```
工具代码修改时（时机2）：
  先跑单元测试 → 再跑变异测试 → 最后跑回归测试
  若回归测试失败 → 判断是代码 bug 还是预期行为变化
    预期变化 → ARCH_REGRESSION_UPDATE=1 更新基线
    非预期  → 修复代码，禁止更新基线掩盖问题

权重/阈值调整时（时机3）：
  必须同时更新 skill.md 与回归测试基线
  更新顺序: skill.md → ARCH_REGRESSION_UPDATE=1 → 人工审查新基线合理性
```

**基线更新规范**：

- 更新基线的**唯一合法理由**是"预期行为变化"（如评分算法改进、阈值校准）
- 禁止用更新基线掩盖工具 bug 或检测误报
- 每次基线更新需在开发日志中记录变更原因

#### 提示词正文

> 请在本地可用的真实开源项目上运行工具，建立外部验证基线。
>
> **输入**：
> - 工具代码：[路径]
> - 基线保存目录：tests/regression/snapshots/[domain]_baselines/
> - 可用的外部项目列表：[项目1:路径1, 项目2:路径2, ...]
>
> **基线建立流程**：
> 1. 对每个项目运行 all_metrics()
> 2. 保存 overall、dimension、nvr_violations 到 JSON
> 3. 输出基线汇总表
>
> **回归测试要求**：
> - 综合评分偏移不超过 +/-2.0
> - NVR 违规数量不变
> - 各维度评分偏移不超过 +/-5.0
> - NVR output_level 不应升级

#### 参考实例

数值精度 5 项目基线数据：

```
MOOSE:   96.0, NVR=1
deal.II: 96.0, NVR=1
FreeFEM: 96.0, NVR=1
MFEM:    96.0, NVR=1
FEniCSx: 46.33, NVR=6
```

---

### 提示词 B3.5：开源项目验证

**适用阶段**：测试  
**调用时机**：外部验证基线建立后，三方一致性检查之前  
**发送给**：architecture-quality 智能体

#### 问题背景

B3 建立基线解决了"评分不漂移"（回归守护），但未验证"检测是否正确"（正确性验证）。B3.5 对照《xxx验证案例集》中指定的 A 类可复现开源项目，校验工具检测结果是否符合案例集的阳性/阴性预期，防误报与漏报。

B3 与 B3.5 的区别：

| | B3 外部验证基线 | B3.5 开源项目验证 |
|:--|:--------------|:-----------------|
| 目的 | 回归守护（分数不漂移）| 正确性验证（检测对不对）|
| 对照 | 自建基线快照 | 验证案例集预期 |
| 项目来源 | 任意本地项目 | 案例集指定 A 类项目 |
| 输出 | 快照 JSON + 回归断言 | 验证报告 + 误报/漏报分析 |
| 失败处理 | 更新基线（预期变化）| 修复检测逻辑（误报/漏报）|

#### 提示词正文

> 请对照验证案例集，在指定的开源项目上验证工具检测正确性。
>
> **输入**：
> - 工具代码：[路径]
> - 验证案例集：[docs/zh/xxx验证案例集.md]
> - 案例集指定的开源项目列表：[项目: 路径: 预期表现]
>
> **验证流程**：
> 1. 从案例集中提取 A 类"可复现"开源项目及预期表现
> 2. 对每个项目运行 all_metrics()
> 3. 对比实际结果与案例集预期：
>    - 阳性案例（架构良好）→ 预期低违规范、高评分
>    - 阴性案例（架构缺陷）→ 预期触发对应 MPR
> 4. 对不一致项分析根因：误报 / 漏报 / 案例集预期需更新
>
> **验证报告**：
>
> | 项目 | 案例集预期 | 实际结果 | 一致? | 根因 |
> |:-----|:----------|:--------|:-----:|:-----|
> | Kratos | MPR-001/002 低违规范 | ... | ✅/❌ | ... |
> | SU2 FSI | 应触发 MPR-004 | ... | ✅/❌ | ... |

#### 差异归因策略

实际结果 ≠ 案例集预期时，先归因再处理：

```
工具漏报   → 检测逻辑缺失，修复工具（禁改案例集）
工具误报   → 检测模式过宽，修复工具
案例集过时 → 项目源码演进导致，更新案例集预期（需标注原因）
```

**优先级**：默认修复工具；仅当确认是案例集预期过时（有明确证据）才更新案例集。

#### LLM 漏报探查（防"静态正则盲区"）

**问题**：工具检测正则基于已知命名模式，无法穷举所有框架的命名惯例。如 MOOSE 用 `MooseObject` 作统一基类，但工具原正则只识别 `Plugin/Module/Application/Solver` → 漏报"MOOSE 有统一接口"。

**定位**：LLM 作为"第二道检查"，识别工具正则之外的等价机制。但 LLM 的探查结论**必须实测归因**，不得凭常识加分。

**流程**：

```
1. 工具运行 + 差异归因（现有）
2. 触发点：仅低分项 / 工具未命中项
   - 维度得分 < 60
   - 关键子项未命中（如 has_unified_interface=false）
   - MPR 误触发但案例集预期阳性
3. LLM 提出候选命名模式（假设）
4. 实测验证候选：
   - grep 统计 `class X : public <候选>` 的文件数（阈值 ≥ 10）
   - 定位基类定义文件（框架核心目录）
   - 注册/工厂机制佐证
5. 命中 → 记为"工具正则盲区"；未命中 → 放弃
6. 人工审查确认 → 固化为工具正则（增量）
7. 回归测试防误报 → 重新评估 + 更新基线
```

**LLM 探查提示词**：

> 请对以下低分项/未命中项，探查是否存在"工具正则之外的等价机制"。
>
> **项目**：[项目名]
> **低分/未命中项**：[如 extension_support.dynamic_loading.has_unified_interface=false]
> **工具检测**：[工具当前正则/逻辑]
>
> **探查步骤**：
> 1. 基于领域知识，提出该项目可能使用的"其他命名模式"候选
> 2. 用实测验证每个候选（grep 统计 + 基类定义定位）
> 3. 只有实测命中（文件数 ≥ 阈值）才记为"工具正则盲区"
> 4. 未命中 → 放弃该候选，不据此加分
>
> **输出**：
> | 候选模式 | 实测命中数 | 基类定义 | 结论（盲区/放弃）|

**人工审查固化规范**：

- 实测命中后，必须**人工审查**确认盲区真实，才固化为工具正则
- 固化方式：将命名模式追加到工具的**可扩展接口基类列表**（如 `INTERFACE_BASE_CLASSES`），由列表生成正则
- 固化后必须验证**其他项目不误报**（如 deal.II/MFEM 无 MooseObject 继承）
- 回归测试补充该模式用例

**参考实例**：MOOSE 插件架构评估中，工具原正则漏报 `MooseObject` 统一基类。LLM 探查提出候选 → 实测全库 196 个继承 `MooseObject` → 确认盲区。经人工审查后固化 `MooseObject` 到 `INTERFACE_BASE_CLASSES`，并实测 deal.II/MFEM 均无此继承（防误报）。

**语言盲区处理范式**（漏报的两类修复方式）：

| 盲区类型 | 特征 | 修复方式 | 实例 |
|:---------|:-----|:---------|:-----|
| **命名差异** | 同类机制，不同命名 | 追加到可扩展模式列表 | MooseObject → `INTERFACE_BASE_CLASSES` |
| **语言体系差异** | C++ 类继承 vs Fortran 过程指针 | 新增独立语言检测 | ElmerFEM → `_detect_fortran_plugin()` |

**语言盲区修复原则**：
- 新检测必须**限定语言**（如 Fortran 检测只扫 .f90/.f），避免跨语言误报
- 合并逻辑**不叠加**（Fortran 插件作为 C++ 接口的等价替代，不重复计分）
- 验证其他项目无回归（如 OpenFOAM 的 C++ GetProcAddr 不应误判为 Fortran 插件）

#### 证据使用原则（防"凭常识断言"）

判定工具误报/漏报时，必须引用**可核实证据**，禁止以 LLM 领域知识作为依据陈述：

| 证据类型 | 示例 | 性质 |
|:---------|:-----|:-----|
| **仓库文档** | 验证案例集将某项目列为阳性/阴性案例（§x.x）| 可核实 |
| **本地实测** | 目录结构、`modules/` 下模块数、构建文件语法 | 可复现 |
| **LLM 领域知识** | "该项目是公认的模块化优秀项目" | 仅可作**假设**，不可作**依据** |

**判定流程**：

```
可疑异常（工具判定与直觉冲突）
   ↓
收集证据：
  ① 查仓库文档（案例集预期）→ 项目本应如何
  ② 查本地实测（目录/构建/代码）→ 项目实际如何
  ③ 领域知识 → 仅作为"假设"，标注"待验证"
   ↓
证据①+② 矛盾 → 判定为工具误报（有据）
仅证据③ → 不据此下结论，先补充实测证据
```

**参考实例**：求解器物理场 B3.5 验证 MOOSE 时，MPR-001 触发与案例集阳性预期冲突。诊断中"MOOSE 模块化优秀"这一论断，应拆分为可核实证据（案例集列为阳性案例 + `modules/` 实测 20+ 模块），而非笼统的"公认"。LLM 领域知识可提示怀疑方向，但最终判定必须落到文档或实测证据上。

#### 参考实例

数值精度 Skill 开发中，开源项目验证发现并修复了 richardson 误报：裸 `richardson` 匹配到开发者姓名 Chris Richardson 的版权声明，94 处匹配 93 处误报。对照案例集验证后改为 `richardson_extrap`，FEniCSx 评分从 55.67 修正为 46.33。

---

### 提示词 B4：运行三方一致性检查

**适用阶段**：测试  
**调用时机**：所有测试通过后，发布前  
**发送给**：architecture-quality 智能体

#### 提示词正文

> 请检查指南、Skill 文件、评估工具三方的评分算法是否一致。
>
> **检查项**：
> 1. 工具的版本声明：GUIDE_VERSION、SKILL_VERSION
> 2. Skill 文件中的评分算法是否与工具实现匹配
> 3. 指南中的评分公式是否与 Skill 描述一致
>
> **输出格式**：一致性检查报告

#### 参考实例

`scripts/consistency_check.py` 的核心检查逻辑：

```
[TOOL] GUIDE_VERSION = 1.8
[TOOL] SKILL_VERSION = 1.6
[SKILL] debt_ratio = low_score_count / 6: OK
[SKILL] score = max(0, 100 - debt_ratio * 200): OK
[SKILL] NVR-012 trigger (33.3%): OK
[TOOL] code debt_ratio = low_score_count / total_dims: OK
[TOOL] code NVR-012 trigger (0.3): OK
-------------------------------------
结果: PASS - 三方一致
指南 v1.8 <- -> Skill v1.6 <- -> Tool
```

---

## 第五章：阶段 C — 部署（Deployment）

### 提示词 C1：注册 OpenCode 智能体

**适用阶段**：部署  
**调用时机**：Skill 开发测试完成，准备集成到 OpenCode  
**发送给**：architecture-quality 智能体

#### 提示词正文

> 请为新 Skill 生成 OpenCode 智能体注册文件。
>
> **输入**：
> - 技能名称：[名称]
> - 技能文件路径：[path]
> - 评估命令：[command]
> - 所需权限：[read/bash/edit/task/skill]
>
> **注册方式**（二选一）：
> 方式 A：全局安装 — 复制 skill 文件到 ~/.config/opencode/skills/
> 方式 B：项目级安装 — 放入 .opencode/skills/ 目录

#### 智能体配置文件模板

```yaml
---
description: [技能描述]
mode: subagent
permission:
  read: allow
  bash:
    "*": ask
    "[command]*": allow
  edit: deny
  task: allow
  skill: allow
---
```

#### opencode.jsonc 配置示例

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "my-skill": {
      "description": "我的新评估技能",
      "prompt_file": "~/.config/opencode/skills/my-skill.md",
      "mode": "subagent",
      "permission": {
        "read": "allow",
        "bash": { "*": "ask", "my-tool*": "allow" },
        "edit": "deny"
      }
    }
  },
  "skill": {
    "paths": [".opencode/skills"],
    "my-skill": {
      "enabled": true,
      "version": "1.0",
      "path": "~/.config/opencode/skills/my-skill.md"
    }
  }
}
```

---

### 提示词 C2：配置 CI/CD 门禁

**适用阶段**：部署  
**调用时机**：智能体注册完成后  
**发送给**：architecture-quality 智能体

#### 提示词正文

> 请为评估工具生成 CI/CD 集成配置，在每轮提交中自动运行评估。
>
> **输入**：
> - 评估命令：[command]
> - 阻断条件：[NVR-xxx ERROR 触发时阻断]
> - 报告存储路径：[path]

#### GitHub Actions 模板

```yaml
name: Architecture Quality Check
on: [push, pull_request]
jobs:
  assess:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run assessment
        run: |
          pip install arch-quality
          [command] . --json > report.json
      - name: Check NVR violations
        run: |
          python -c "
          import json
          r = json.load(open('report.json'))
          errors = [v for v in r.get('nvr_violations', [])
                   if v.get('output_level') == 'ERROR']
          if errors:
              print(f'BLOCKED: {len(errors)} ERROR violations')
              exit(1)
          print(f'PASS: Overall={r[\"overall\"]}')
          "
```

---

### 提示词 C3：生成用户交互提示词

**适用阶段**：部署  
**调用时机**：CI/CD 配置完成后  
**发送给**：architecture-quality 智能体

#### 提示词正文

> 请生成面向最终用户的 OpenCode 交互提示词模板，方便用户调用此 Skill。
>
> **输入**：
> - 技能名称：[名称]
> - 评估命令：[command]
> - 典型使用场景：[列表]

#### 参考实例

数值精度评估的用户提示词：

```
# 完整评估
请对当前项目运行数值算法精度评估，输出 6 维评分和 NVR 违规详情

# 单维度分析
请分析当前项目的 MMS 验证完备性，检查是否有制造解测试文件

# NVR 解读
请解释 NVR-003（相消性损失）在当前项目中的具体情况

# 改进建议
根据最近一次的数值精度评估结果，给出改进建议，按 P0/P1/P2 分级

# 版本对比
请对比当前项目最近两次数值精度评估结果，检测是否有退化
```

---

### 提示词 C4：生成评估报告模板

**适用阶段**：部署  
**调用时机**：用户交互提示词生成后  
**发送给**：architecture-quality 智能体

#### 提示词正文

> 请为评估结果生成 Markdown 报告模板。
>
> **输出格式**：
> - 第一段：综合评分概览
> - 第二段：各维度评分表格
> - 第三段：NVR/MLR 违规列表
> - 第四段：改进建议

#### 报告模板

```markdown
# [领域]评估报告

**项目**：[项目名]
**日期**：[日期]
**综合评分**：[评分] / 100

## 维度评分

| 维度 | 权重 | 得分 | 评级 |
|:-----|:----:|:----:|:-----|
| 维度1 | N% | [分] | [评级] |
| ...   | ... | ...  | ...   |

## NVR/MLR 违规

| 规则 | 级别 | 数量 | 说明 |
|:-----|:----:|:----:|:------|
| NVR-xxx | ERROR | N | [详情] |

## 改进建议

| 优先级 | 建议 | 预期提分 |
|:------:|:-----|:--------:|
| P0 | [建议] | [N] |
```

---

## 第六章：质量保障检查清单

### 6.1 开发完成检查项

| # | 检查项 | 验证方式 |
|:-:|:-------|:---------|
| 1 | 指南 x1 权重表与 Skill x1 权重表一致 | 人工比对 |
| 2 | 指南 x2.x 评分公式与 Skill x2.x 评分算法方向一致 | 人工比对 |
| 3 | Skill x5 规则表与工具 check_rules() 的规则数一致 | 人工比对 |
| 4 | 工具的 GUIDE_VERSION 与指南版本号一致 | grep 检查 |
| 5 | 工具的 SKILL_VERSION 与 Skill 版本号一致 | grep 检查 |
| 6 | 每个 calc_xxx() 返回 (score, detail) 元组 | 代码审查 |
| 6a | **工具设计文档已编写**（指南算法 → 工具实现映射，检测正则级）| 文档验收 |
| 6b | **设计文档覆盖 4 维度 + MPR 映射 + 工程化偏差** | 文档审查 |
| 6c | **LLM 漏报探查已执行**（低分项/未命中项，实测归因后固化）| 验证报告审查 |

### 6.2 测试通过检查项

| # | 检查项 | 验证方式 |
|:-:|:-------|:---------|
| 7 | 单元测试通过率 100% | pytest |
| 8 | 每个维度至少 2 个测试用例 | pytest --coverage |
| 9 | 每条 NVR/MLR 规则至少 1 个测试 | pytest -k NVR- |
| 10 | 变异测试通过率 100% | pytest tests/mutation/ |
| 10a | **集成测试通过率 100%** | **pytest tests/test_*_integration.py** |
| 10b | **端到端测试通过率 100%** | **pytest tests/test_*_e2e.py** |
| 10c | **集成测试有精确值断言（≥L2）**：权重归一化断言具体数值，装配层用 mock 输入区分组件错/装配错 | 代码审查 |
| 10d | **端到端测试复用真实项目基线做结构冒烟**，含字段类型断言 | pytest + 审查 |
| 10e | **三测试期望值来源独立审计**（单元/skill 算法、集成/合并公式、E2E/schema）| 人工审查 |
| 11 | 外部验证基线回归测试通过率 100% | pytest tests/regression/ |
| 11a | **工具代码修改后重跑回归测试** | 每次改动 arch_metrics_*.py 后执行 |
| 11b | **权重/阈值调整后同步更新基线** | skill.md 变更时执行 ARCH_REGRESSION_UPDATE=1 |
| 11c | **开源项目验证通过率 100%**（对照案例集预期）| pytest + 验证报告审查 |
| 12 | 三方一致性检查 PASS | scripts/consistency_check.py |
| 12a | **Agent Harness 验证通过率 100%**（agent 行为：执行评估命令、无越权写、无死循环）| `python scripts/run_agent_harness.py` |
| 12b | **Harness 断言规则与插件 hook 共享单一事实源**（rules.json）| 代码审查 |

### 6.3 部署就绪检查项

| # | 检查项 | 验证方式 |
|:-:|:-------|:---------|
| 13 | OpenCode 智能体配置文件正确 | opencode 可识别 |
| 14 | opencode.jsonc 中 agent 注册无误 | 配置验证 |
| 15 | CI/CD 配置已添加 | git diff |
| 16 | 用户交互提示词已生成 | 文档验收 |
| 17 | 报告模板可用 | 执行验收 |

---

## 附录 A：数值精度 Skill 开发复盘

### A.1 版本演进时间线

```
指南版本线:
  1.0 (6/26) -- 初始版本，定义 6 维评分和 12 条 NVR
  1.5 (6/26) -- 术语统一，专家评审通过
  1.6 (7/10) -- NVR-001/NVR-002 从运行时检测改为静态机制检查
  1.7 (7/10) -- 增加置信度标注（高/中/低三级）
  1.8 (7/14) -- 对齐修正：x2.6 公式改为维度级，命名统一

Skill 版本线:
  1.0       -- 初始版本，对齐指南 1.0
  1.5       -- 对齐指南 1.5，新增豁免注解体系
  1.6 (7/14) -- 对齐修正：x2.6 从注释扫描改为维度低分统计

工具版本线:
  初始开发  -- 实现 6 维评分 + 12 条 NVR + CLI
  1.5 对齐  -- 与 Skill 1.5 对齐
  1.6 对齐  -- 与 Skill 1.6 对齐，版本常量 GUIDE=1.8, SKILL=1.6
```

### A.2 关键决策树

#### 决策 1：评分公式独立编写

```
指南 x2.4 公式: score = E_d x 50 + E_i x 50
问题: "是否被估计"无法通过静态分析判定
选项:
  +-- 选项 A: 严格遵循指南公式
  |     需要人工审查误差量化报告，无法自动化
  |     后果: 该维度永远无法自动评分
  +-- 选项 B: 工程化改写 (选中)
  |     score = mesh(40) + residual(30) + tol(30)
  |     代价: 与指南公式不一致，产生三方差异
  |     缓解: 在 skill x7 引用表标注"独立编写"
  教训: 指南公式应从一开始就考虑可执行性
```

#### 决策 2：richardson 检测模式

```
问题: 使用裸 richardson 匹配开发者姓名 Chris Richardson
选项:
  +-- 选项 A: 保留裸 richardson (最初)
  |     94 处匹配，93 处为版权声明误报
  |     后果: FEniCSx 评分虚高 55.67 -> 应 46.33
  +-- 选项 B: 改为 richardson_extrap (选中)
  |     误报清零，只匹配实际算法引用
  |     代价: 可能漏掉部分不标准的写法
  教训: 关键词检测必须考虑自然语言的歧义性
```

#### 决策 3：债务密度粒度

```
指南 x2.6 公式: debt_ratio = N_debt / N_total
问题: "模块总数"无法精确定义
选项:
  +-- 选项 A: 模块级 (指南描述)
  |     N_total = "数值算法模块总数"
  |     困境: 什么是"一个模块"？无法在静态分析中定义
  +-- 选项 B: 维度级 (选中)
  |     debt_ratio = low_score_count / 6
  |     简单、可执行、已在 10 项目上验证
  |     代价: 比模块级粒度粗
  教训: 指南应避免使用无法操作的抽象概念
```

#### 决策 4：MMS 检测阈值

```
问题: 多少个 MMS 文件才算"有 MMS 验证"？
选项:
  +-- 选项 A: mms_count >= 1 -> 100 分
  |     太宽松，1 个文件可能是偶然提及
  +-- 选项 B: mms_count >= 3 -> 100 分 (选中)
  |     依据: MMS 需要在 >=3 套网格上执行才有意义
  |     验证: MOOSE(47) 100分, FreeFEM(13) 100分, FEniCSx(0) 0分
  教训: 阈值需要理论依据 + 实际项目验证
```

#### 决策 5：NVR-007/NVR-008 求解器过滤

```
问题: 无求解器代码的项目也触发 NVR-007/NVR-008
选项:
  +-- 选项 A: 不过滤 (最初)
  |     所有非求解器项目都误报
  |     后果: test_cancel.c 类型项目被扣分
  +-- 选项 B: 加 err_score is not None 守卫 (选中)
  |     无求解器代码时跳过 NVR-007/NVR-008
  |     验证: 非求解器数学库不再误报
  教训: check_nvr_rules() 必须考虑 calc_xxx() 返回 None 的情况
```

### A.3 验证里程碑

```
   日期         里程碑                             证据
   --------    ---------------------------------   -------------------------
   第 1 周     指南 1.0 + Skill 1.0 + 工具原型     4 项目验证
   第 2 周     22 个单元测试 + 10 项目验证         全部通过
   第 3 周     P0: 外部验证基线 (5 项目)            38 回归测试通过
               P1: 6 个变异测试                     6/6 通过
               richardson 误报修复                  FEniCSx 55.67->46.33
               B3.5 开源项目验证                   对照案例集预期校验通过
   第 4 周     P2: 人工评审框架                     3 模板 + 比对脚本
               P3: k-fold 交叉验证                  5 折 LOOCV: 4/5 泛化
               三方一致性修复                       指南1.8/Skill1.6/工具
               Valgrind 交叉验证                    端到端实验完成
```

### A.4 Agent Harness 开发复盘

在求解器物理场 SKILL 开发中，从零搭建了验证 agent 行为的 harness 基架，为后续 SKILL 提供可复用模板。

**版本演进时间线**：

```
外部 harness 初版      Python runner 子进程调 opencode run，3 合成用例
规则单一事实源          rules.json（Python 断言器 + JS 插件共享）
插件 hook 下沉          agent-assert.js 框架级自动断言（默认 log）
断言器缺陷修复          SyntaxWarning 剥离 + 非多物理场判据
AGENTS.md 同步          文档化 harness 定位与用法
```

**关键决策**：

| # | 决策 | 依据 |
|:-:|:-----|:-----|
| 1 | agent 注册 `mode: primary` | 全局配置优先于项目配置；subagent 不能被 `--agent` 直接驱动 |
| 2 | 两层验证架构（插件 hook + 外部 runner）| hook 框架级兜底、runner 用例级端到端，互补 |
| 3 | 规则抽 rules.json 单一事实源 | 避免 Python/JS 双份断言逻辑漂移 |
| 4 | 默认 log + 可配置 throw | 避免 hook 抛错阻断影响 agent 正常执行，需阻断时可切换 |

**验证里程碑**：

- 3 用例端到端 PASS（多物理场 / 单求解器 / 纯 Markdown）
- 发现真实 bug：`arch_report.py` 缺 `ReportGenerator` 导入（agent 正确识别工具链缺陷）
- 修复断言器缺陷：SyntaxWarning 污染剥离、非多物理场判据（JSON 无 solver 提及 → 非多物理场）

**经验教训**：

```
pytest 验证工具"算得对"，harness 验证 agent"用得好"——两者互补，缺一不可
验证独立性：断言由框架/外部执行，不能交给 LLM 自证
LLM 行为不稳定（同 prompt 不同工具序列），需重试 + 断言兜底
```

---

## 附录 B：opencode.jsonc 完整配置示例

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "architecture-quality": {
      "description": "架构质量评估智能体 — 系统性分析、评估和改进软件系统架构质量",
      "prompt_file": "~/.config/opencode/agents/architecture-quality.md",
      "mode": "subagent",
      "model": "deepseek/deepseek-v4-flash",
      "permission": {
        "read": "allow",
        "bash": {
          "*": "ask",
          "arch-quality*": "allow",
          "arch-quality *": "allow",
          "python -m arch_quality*": "allow"
        },
        "edit": "deny",
        "task": "allow",
        "skill": "allow"
      }
    },
    "numerical-accuracy": {
      "description": "数值算法精度评估智能体",
      "prompt_file": "~/.config/opencode/skills/numerical-accuracy/SKILL.md",
      "mode": "subagent",
      "subtask": true,
      "permission": {
        "read": "allow",
        "bash": { "*": "ask", "arch-quality*": "allow" },
        "edit": "deny"
      }
    },
    "template-metaprogramming": {
      "description": "模板元编程与编译时依赖膨胀评估",
      "prompt_file": "~/.config/opencode/skills/template-metaprogramming/SKILL.md",
      "mode": "subagent",
      "subtask": true,
      "permission": {
        "read": "allow",
        "bash": { "*": "ask", "arch-quality*": "allow" },
        "edit": "deny"
      }
    }
  },
  "skill": {
    "paths": [".opencode/skills"],
    "numerical-accuracy": {
      "enabled": true,
      "version": "1.6",
      "path": "~/.config/opencode/skills/numerical-accuracy/SKILL.md"
    },
    "template-metaprogramming": {
      "enabled": true,
      "version": "4.1",
      "path": "~/.config/opencode/skills/template-metaprogramming/SKILL.md"
    }
  },
  "command": {
    "assess": {
      "template": "请对当前项目运行完整架构质量评估，输出 JSON 格式报告",
      "agent": "architecture-quality",
      "description": "运行完整架构质量评估"
    },
    "assess-numerical": {
      "template": "请对当前项目运行数值算法精度评估，输出 6 维评分和 NVR 违规详情",
      "agent": "numerical-accuracy",
      "description": "运行数值算法精度评估"
    },
    "assess-template": {
      "template": "请对当前项目运行模板元编程评估，输出 6 维评分和 MLR 违规详情",
      "agent": "template-metaprogramming",
      "description": "运行模板元编程评估"
    }
  }
}
```

---

## 附录 C：参考资源与术语表

### 术语表

| 术语 | 英文 | 定义 |
|:-----|:------|:------|
| Skill | Skill | 封装特定评估领域知识的可复用单元 |
| 指南 | Guide | Skill 的最高层次标准定义文档 |
| 评估工具 | Tool | 执行评分和规则检测的 Python 代码 |
| NVR | Numerical Violation Rule | 数值精度领域的违规规则 |
| MLR | Multi-Language Rule | 多语言混合依赖领域的违规规则 |
| 三方一致性 | Three-way Consistency | 指南/Skill/工具的评分算法必须一致 |
| 置信度 | Confidence Level | 检测结果的可靠程度（高/中/低）|
| 变异测试 | Mutation Testing | 故意引入缺陷验证工具检出能力 |
| 外部验证基线 | External Validation Baseline | 在真实项目上建立的评分基准 |
| 交叉验证 | Cross Validation | 验证工具评分在不同项目上的泛化能力 |
| 豁免注解 | Waiver Annotation | 开发者在源码中声明的规则豁免声明 |
| 检测模式 | Detection Pattern | 用于发现代码坏味道的关键词或正则 |
| 质量门禁 | Quality Gate | 在 SKILL 文件编写完成后、代码实现前执行的质量审查步骤，见 §A3.5 |
| §2↔§5 一致性 | §2-§5 Consistency | 评分算法的检测方法与规则检测逻辑之间的对齐程度，§A3.5 审查清单第 2 项 |
| 审查智能体 | Audit Agent | 专门负责审查其他 SKILL 文件质量的 OpenCode 子智能体，见 §A3.5 |
| 集成测试 | Integration Test | 验证组件间交互正确性的测试，见 §B2.5 |
| 端到端测试 | End-to-End Test | 验证完整 CLI 管道输出结构和格式的正确性，见 §B2.5 |
| 回归测试调用时机 | Regression Trigger | 基准回归测试的持续守护场景（工具改动/权重调整/CI/发版等 7 种），见 §B3 |
| 开源项目验证 | Open Source Validation | 对照验证案例集预期，验证工具在真实开源项目上的检测正确性（防误报/漏报），见 §B3.5 |
| Agent Harness | Agent Harness | 验证 agent 编排工具行为的测试基架（约束/验证/纠正三层），区别于 pytest（验证工具代码），见 §B2.6 |
| LLM 编排工具 | LLM Orchestration Tool | 模型在 ReAct 循环中可选用的工具集；模型负责"选"，框架负责"跑+拦+纠" |
| 验证独立性 | Verification Independence | 断言必须由看得到事件流的一方（插件 hook/外部 runner）执行，不能交给 LLM 自证 |

### 参考资源

| 资源 | 路径 |
|:-----|:------|
| arch-quality 框架 | `https://github.com/DevG1000/arch-quality` |
| OpenCode 文档 | `https://opencode.ai/docs` |
| 数值精度 Skill | `src/arch_quality/skills/numerical-accuracy.md` |
| 数值精度工具 | `src/arch_quality/arch_metrics_numerical_accuracy.py` |
| 数值精度指南 | `docs/zh/数值算法正确性与精度保障评估指南.md` |
| 三方一致性脚本 | `scripts/consistency_check.py` |
| 数值精度验证报告 | `docs/zh/数值算法验证总结报告.md` |
| 交叉验证报告 | `docs/zh/交叉验证报告.md` |
| 动态工具交叉验证方案 | `docs/zh/动态工具交叉验证方案.md` |
