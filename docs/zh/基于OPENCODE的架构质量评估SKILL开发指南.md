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

整个开发流程分为 6 个阶段，对应 12 个 OpenCode 交互提示词：

```
阶段 A：开发 -------------------------------------------------
  A1 初始化结构 --> A2 定义维度 --> A3 定义规则 --> A4 实现工具
                                                    |
阶段 B：测试 -------------------------------------------------
  B1 单元测试 <-- B2 变异测试 <-- B3 外部基线 <-- B4 一致性
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

---

## 第四章：阶段 B — 测试（Testing）

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

### 提示词 B3：生成外部验证基线

**适用阶段**：测试  
**调用时机**：单元测试和变异测试通过后  
**发送给**：architecture-quality 智能体

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

### 6.2 测试通过检查项

| # | 检查项 | 验证方式 |
|:-:|:-------|:---------|
| 7 | 单元测试通过率 100% | pytest |
| 8 | 每个维度至少 2 个测试用例 | pytest --coverage |
| 9 | 每条 NVR/MLR 规则至少 1 个测试 | pytest -k NVR- |
| 10 | 变异测试通过率 100% | pytest tests/mutation/ |
| 11 | 外部验证基线回归测试通过率 100% | pytest tests/regression/ |
| 12 | 三方一致性检查 PASS | scripts/consistency_check.py |

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
   第 4 周     P2: 人工评审框架                     3 模板 + 比对脚本
               P3: k-fold 交叉验证                  5 折 LOOCV: 4/5 泛化
               三方一致性修复                       指南1.8/Skill1.6/工具
               Valgrind 交叉验证                    端到端实验完成
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
