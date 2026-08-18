# 求解器和物理场模块化架构模式评估 OpenCode Skill — 完整开发方案

---

## 第一章：概述

### 1.1 背景

求解器和物理场模块化架构模式评估是 arch-quality 体系中规划的第 4 个结构质量增强维度。当前已有三个增强维度（多语言混合依赖、模板元编程、数值算法精度）均已实现并集成到 `ComprehensiveReport`。

该 Skill 针对工业软件（CAD/CAE/CAx/CFD）中多物理场耦合系统的模块化架构质量进行评估，覆盖物理场模块边界、耦合架构、扩展机制和数据传递四个核心维度。

**已有文档基础**（已完稿，待实现）：
- `docs/zh/求解器和物理场模块化架构模式识别评估/求解器与物理场模块化架构模式识别评估指南（1.3版）.md`
- `docs/zh/求解器和物理场模块化架构模式识别评估/求解器与物理场模块化架构模式识别评估的设计依据（1.4版）.md`
- `docs/zh/求解器和物理场模块化架构模式识别评估/求解器与物理场模块化架构模式识别评估验证案例集（1.4版）.md`
- `docs/zh/求解器和物理场模块化架构模式识别评估/求解器与物理场模块化架构模式识别评估可参考工具库简介与推荐理由.md`

### 1.2 定位

| 属性 | 值 |
|:-----|:------|
| 层级 | 第 3 层（Prompt + Skills + Commands） |
| 在结构质量中的角色 | 增强维度，在多物理场项目自动启用 |
| 基准权重（默认产品类型） | 占结构质量 15% |
| 启用条件 | 目录结构含多物理场特征（同时存在 structural/thermal/fluid 求解器目录，或目录名含 multiphysics）|
| 遵循的 SKILL 开发指南 | `docs/zh/基于OPENCODE的架构质量评估SKILL开发指南.md` |

### 1.3 参考实例

以 `numerical-accuracy` Skill 的开发实践为模板（详见开发指南 §1.4）：

| 参数 | numerical-accuracy | solver-physics（本方案） |
|:-----|:------------------|:------------------------|
| 评估维度 | 6 | 4 |
| 规则数 | 12 NVR | 12 MPR |
| 指南版本 | 1.8 | 1.3 |
| 工具代码估算 | 890 行 | ~600-800 行 |
| 验证项目 | 10 个开源项目 | 5 个开源项目 |
| 测试用例 | 22 单元 + 6 变异 + 38 回归 + k-fold | 30 单元 + 10 变异 + 回归 + k-fold |

---

## 第二章：三方制品体系

遵循开发指南 §2 的三方派生关系：

```
+---------------------------+
| 指南（已完稿）              |  docs/zh/求解器和物理场模块化架构模式识别评估指南.md
| 定义: 4 维度 + 12 MPR 规则 |
+-----------+---------------+
            | 翻译为 skill .md
            v
+---------------------------+
| Skill 文件（需新增 2 个）    |
| (A) src/arch_quality/skills/solver-physics-architecture.md
|     — 权重表 + 评分算法（方案D 运行时解析）
| (B) .opencode/skills/solver-physics-architecture/SKILL.md
|     — Front matter + 摘要（供 skill 工具加载）
+-----------+---------------+
            | 实现为 Python
            v
+---------------------------+
| 评估工具（需新增）          |
| src/arch_quality/arch_metrics_solver_physics.py
| SolverPhysicsMetrics 类
| 4 个 calc_xxx() + check_mpr_rules()
+---------------------------+
```

---

## 第三章：用户 — 架构质量评估智能体交互流程

本 Skill 的开发遵循 17 步提示词交互流程（A1~C4，含 A3.5 质量门禁、B2.5 集成&E2E 测试、B2.6 Agent Harness 验证和 B3.5 开源项目验证），每一步对应一个具体的提示词模板。用户向 `architecture-quality` 智能体发送提示词，智能体生成产物并逐步推进开发。

```
交互流程总览：

  阶段 A — 开发
   A1 初始化结构  →  A2 定义维度  →  A3 定义规则
                                      ↓
                               A3.5 SKILL 文件质量审查
                                      ↓
                                    A4 实现工具

  阶段 B — 测试
   B1 单元测试  →  B2 变异测试  →  B2.5 集成 & 端到端测试
                                      ↓
                              B3 外部基线  →  B3.5 开源项目验证
                                      ↓
                                    B4 一致性检查

  阶段 C — 部署
   C1 注册智能体  →  C2 CI/CD    →  C3 用户提示词 →  C4 报告模板
```

### 3.1 A1 初始化 Skill 结构

| 字段 | 值 |
|:-----|:------|
| **调用时机** | 开始编写新 Skill 时，生成文件骨架 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 你是一个架构质量评估技能开发助手。  
> 请帮我为一个新的评估领域生成 Skill 文件的标准骨架。  
>
> **领域信息**：
> - 技能名称：solver-physics-architecture
> - 评估维度数：4
> - 每个维度名称：物理场模块边界完整性、多物理场耦合架构合理性、插件式扩展架构支持度、跨场数据传递规范性
> - 对应指南版本：1.3
>
> **要求**：
> 1. 生成符合 src/arch_quality/skills/ 目录规范的 .md 文件骨架
> 2. 包含版本绑定头、权重表、各维度方法签名占位
> 3. 包含 MPR 规则表占位（12 条）
> 4. 包含版本历史

**用户输入表**：

| 参数 | 值 |
|:-----|:------|
| 技能名称 | solver-physics-architecture |
| 评估维度数 | 4 |
| 维度名称 | 物理场模块边界完整性 / 多物理场耦合架构合理性 / 插件式扩展架构支持度 / 跨场数据传递规范性 |
| 维度权重 | 25%, 30%, 25%, 20% |
| 前置检测 | `_detect_multiphysics()` — 目录结构含多物理场特征 |

**智能体产出**：
- `src/arch_quality/skills/solver-physics-architecture.md` 骨架
- `.opencode/skills/solver-physics-architecture/SKILL.md` 骨架

### 3.2 A2 定义评估维度与评分算法

| 字段 | 值 |
|:-----|:------|
| **调用时机** | 已有指南公式后，翻译为 Skill 可执行算法 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 我需要将指南中的评分公式翻译为 Skill 中的可执行算法。  
>
> **输入**：
> - 维度名称：物理场模块边界完整性
> - 权重：25%
> - 指南原文公式：边界完整性得分 = 独立编译单元(20分) + API精简度(20分) + MMS验证基准(30分) + 内部封装性(30分) + FMI加分(+10分)
> - 可用的检测手段：目录结构扫描、符号表统计、MMS 目录 glob、跨模块访问模式匹配、FMI 接口检测
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

对 4 个维度依次执行上述流程。

**智能体产出**：
- `src/arch_quality/skills/solver-physics-architecture.md` 各维度评分算法完善

### 3.3 A3 定义 MPR 规则

| 字段 | 值 |
|:-----|:------|
| **调用时机** | 4 维度定义完成后 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 我需要为评估维度中的问题定义 MPR 规则。  
>
> **输入**：
> - 所属维度：物理场模块边界完整性
> - 规则数量：4 条（MPR-001 至 MPR-003 + MPR-010 部分）
>
> **规则设计原则**：
> 1. 每条规则对应一个可自动检测的代码坏味道
> 2. output_level 与 severity 解耦
> 3. 高置信度规则使用 ERROR 级别
> 4. 中低置信度规则使用 WARNING 或 INFO
> 5. 每条规则必须有明确的触发条件和豁免可能性
>
> **输出格式**：规则总览表 + 逐条详细描述

**规则设计矩阵**：

| output_level | HIGH severity | MEDIUM | LOW |
|:------------:|:-------------:|:------:|:---:|
| ERROR | MPR-001(高置信度) MPR-003(中置信度) MPR-008(高置信度) | — | — |
| WARNING | MPR-005(高置信度) MPR-007(高置信度) | MPR-002(高置信度) MPR-004(中低置信度) MPR-006(中置信度) MPR-009(中置信度) MPR-010(中置信度) | — |
| INFO | — | — | MPR-012(低置信度) |

**智能体产出**：
- 每个 MPR 规则的详细定义写入 skill .md

### 3.4 A3.5 SKILL 文件质量审查

| 字段 | 值 |
|:-----|:------|
| **调用时机** | A3 规则定义完成后，A4 工具实现之前 |
| **发送给** | `skill-audit` 智能体 |

**用户提示词**：

> 请对这份 SKILL 文件进行质量审查，检查以下 6 个维度：
>
> **1. 结构完整性** — 版本绑定头、权重表方案D可解析、维度完整结构、规则完整字段
> **2. §2 评分算法 ↔ §5 规则一致性** — 对应子项引用、触发条件与评分档位对齐、非有意设计的松紧差异
> **3. 设计合理性** — 跨维度重复计分、递进扣分实证、阈值明确性
> **4. 可执行性** — 静态分析可行性、关键词误报风险
> **5. 完整性** — 覆盖所有得分为 0 的子项、启用条件定义
> **6. 跨规则协调** — 关联规则依赖、与本体系其他 Skill 的边界
>
> **判定标准**：
> - PASS：全部 6 项无 FAIL → 进入 A4
> - WARNING：仅 4-5 项有 WARNING → 修复后进入 A4
> - FAIL：任一项有 FAIL 或 ≥2 项 WARNING → 修复后才能进入 A4

**智能体产出**：
- 审查报告（PASS/WARNING/FAIL）
- 修复建议（P0/P1/P2 分级）

> **参考**：《基于 OPENCODE 的架构质量评估 SKILL 开发指南》§A3.5，
> 审查智能体 `.opencode/skills/skill-audit/SKILL.md`

### 3.5 A4 实现评估工具

| 字段 | 值 |
|:-----|:------|
| **调用时机** | A3.5 质量审查通过后 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 请根据 Skill 文件中的评分算法定义，生成评估工具的 Python 代码。  
>
> **输入**：
> - Skill 文件路径：src/arch_quality/skills/solver-physics-architecture.md
> - 工具类名：SolverPhysicsMetrics
> - 使用的检测方法：目录结构扫描、符号表统计、MMS glob、跨模块访问模式匹配、AST 调用图、依赖图分析、FMI 接口检测、@deprecated 注解检测
>
> **代码生成规范**：
> 1. 每个 calc_xxx() 方法返回 (score, detail_dict)
> 2. 正则模式定义在文件顶部常量区
> 3. 检测关键词定义在文件顶部常量区
> 4. 调用 FileIndex 扫描文件，_has_keyword 检查内容
> 5. 无匹配时返回 (None, {}) 而非 0 分
> 6. 包含命令行入口 main() 函数

**智能体产出**：
- `src/arch_quality/arch_metrics_solver_physics.py` 完整实现
- **`docs/zh/求解器和物理场模块化架构模式识别评估/求解器和物理场模块化架构模式评估工具设计文档.md`**（工具设计文档：指南算法 → 工具实现映射，检测正则级，含工程化偏差与设计决策）

### 3.6 B1 生成单元测试

| 字段 | 值 |
|:-----|:------|
| **调用时机** | 评估工具实现完成后 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 请为评估工具生成 pytest 单元测试用例。  
>
> **输入**：
> - 工具文件：src/arch_quality/arch_metrics_solver_physics.py
> - 维度数：4
> - 支持的检测模式：目录结构扫描、关键词匹配、正则、图分析
>
> **测试覆盖要求**：
> - 每个 calc_xxx() 至少 2 个测试：正常检测 + 未命中检测
> - 每条 MPR 规则至少 1 个测试：触发条件验证
> - 1 个综合测试：all_metrics() 返回格式正确
> - 1 个非多物理场项目测试：_detect 返回 False 时所有评分 None

**智能体产出**：
- `tests/test_solver_physics.py`（~30 个测试用例）

### 3.7 B2 生成变异测试

| 字段 | 值 |
|:-----|:------|
| **调用时机** | 单元测试完成后 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 请为评估工具生成变异测试用例。变异测试通过在好代码中故意引入缺陷，验证工具能检出这些缺陷。  
>
> **输入**：
> - 工具文件：src/arch_quality/arch_metrics_solver_physics.py
> - 需要变异的维度：边界完整性、耦合架构、扩展架构、数据传递
> - 需要变异的规则：MPR-001~MPR-010、MPR-012

**变异测试类型**（10 个）：
- MUT-SP-001: 合并求解器到同一 .cpp → MPR-001 触发
- MUT-SP-002: 暴露内部数据结构 → MPR-002 触发
- MUT-SP-003: 删除 MMS 目录 → MPR-003 触发
- MUT-SP-004: 强耦合→松散文件 → MPR-004 触发
- MUT-SP-005: 耦合逻辑散布 → MPR-005 触发
- MUT-SP-006: 删除收敛参数 → MPR-006 触发
- MUT-SP-007: 删除插件注册 → MPR-007 触发
- MUT-SP-008: 创建循环 #include → MPR-008 触发
- MUT-SP-009: 删除 FMI 接口实现 → MPR-010 触发
- MUT-SP-010: 格式转换函数散布 → MPR-012 触发

**智能体产出**：
- `tests/mutation/projects/good_multiphysics/` 良好项目源码
- `tests/mutation/mutation_cases_sp.json` 变异案例定义
- `tests/mutation/test_solver_physics_mutation.py` 变异测试执行器

### 3.8 B2.5 生成集成测试与端到端测试

| 字段 | 值 |
|:-----|:------|
| **调用时机** | 变异测试通过后，外部验证基线之前 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 请为评估工具生成集成测试与端到端测试用例。
>
> **输入**：
> - 工具文件：src/arch_quality/arch_metrics_solver_physics.py
> - 报告集成文件：src/arch_quality/arch_report.py
>
> **集成测试覆盖要求**：
> | 集成点 | 验证内容 |
> |:-------|:---------|
> | 权重解析集成 | `load_weights_from_skill()` 权重与 `all_metrics()` 一致 |
> | 报告合并集成 | 新维度评分正确合并到 `dimensions.structural` |
> | MPR 合并集成 | MPR 规则正确追加到 `mlr_violations` |
> | 权重归一化 | 多增强同时激活时权重和 = 100% |
>
> **端到端测试覆盖要求**：
> | 场景 | 验证重点 |
> |:-----|:---------|
> | 合成多物理场项目 | `is_multiphysics=True`，4 维度评分非 None |
> | 非多物理场项目（纯 Python）| `is_multiphysics=False`，各维度 None |
> | 非多物理场项目（含关键词）| 避免关键词误报 |
> | CLI JSON 输出 | 合法 JSON，含全部必需字段 |

**智能体产出**：
- `tests/test_solver_physics_integration.py`（~6 个集成测试）
- `tests/test_solver_physics_e2e.py`（~4 个端到端测试）

**测试代码质量要求**（防"测试自圆其说"与"弱断言掩盖错误"）：

| 类型 | 要求 |
|:-----|:-----|
| 集成测试 | 权重归一化用**精确值断言**（如 sp_w≈0.1364），装配层用 mock 输入区分"组件错/装配错" |
| 端到端测试 | 结构断言含**字段类型+范围**检查；复用回归基线项目做真实项目结构冒烟 |
| 期望值来源 | 单元←skill 算法；集成←合并公式；E2E←输出 schema；禁止从实现反推 |
| 边界覆盖 | 集成：0/1/2/3/4 增强组合（含"3 增强但 ml 不激活"）；E2E：空项目/单求解器/C++ 非求解器 |

> **已知教训**：精确断言暴露了 `arch_report.py` 的 3 增强组合 bug（`enhancement_raw[3]` 预设组合不含 sp，导致 sp 权重被忽略），弱断言无法捕获。

> **参考**：《基于 OPENCODE 的架构质量评估 SKILL 开发指南》§B2.5

### 3.9 B3 生成外部验证基线

| 字段 | 值 |
|:-----|:------|
| **调用时机** | 单元测试和变异测试通过后（初始基线建立） |
| **发送给** | `architecture-quality` 智能体 |

**回归测试的持续调用时机**（B3 建立基线后的动态守护）：

| # | 调用时机 | 触发场景 | 频率 |
|:-:|:---------|:---------|:----:|
| 1 | 初始基线建立 | 单元+变异测试通过后，首次真实项目运行 | 一次性 |
| 2 | 工具代码修改后 | 修改 `arch_metrics_solver_physics.py` | 每次改动 |
| 3 | Skill 权重/阈值调整后 | 修改 `skills/solver-physics-architecture.md` | 每次改动 |
| 4 | 指南版本升级后 | 指南升版导致评分算法变化 | 版本发布时 |
| 5 | CI/CD 流水线 | 每次 commit/PR | 持续 |
| 6 | 发布前最终验证 | 版本发版前 | 发版时 |
| 7 | 基线更新 | 项目演进导致预期变化，`ARCH_REGRESSION_UPDATE=1` 重建 | 按需 |

**基线更新规范**：仅"预期行为变化"可更新基线（评分算法改进/阈值校准）；禁止用更新基线掩盖工具 bug 或误报；每次更新需记录变更原因。

**用户提示词**：

> 请在本地可用的真实开源项目上运行工具，建立外部验证基线。  
>
> **输入**：
> - 工具代码：src/arch_quality/arch_metrics_solver_physics.py
> - 基线保存目录：tests/regression/snapshots/
> - 可用的外部项目列表：
>   - Kratos: D:\opensource\Kratos
>   - OpenFOAM: D:\opensource\OpenFOAM-v2512
>   - MOOSE: D:\opensource\MOOSE
>   - SU2: D:\opensource\SU2
>   - preCICE: D:\opensource\preCICE
>
> **基线建立流程**：
> 1. 对每个项目运行 all_metrics()
> 2. 保存 overall、dimension、mpr_violations 到 JSON
> 3. 输出基线汇总表

**智能体产出**：
- `tests/regression/snapshots/sp_kratos.json` 等 5 份基线
- `tests/regression/test_solver_physics_regression.py` 回归测试

### 3.9 B4 运行三方一致性检查

| 字段 | 值 |
|:-----|:------|
| **调用时机** | 所有测试通过后，发布前 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 请检查指南、Skill 文件、评估工具三方的评分算法是否一致。  
>
> **检查项**：
> 1. 工具的版本声明：GUIDE_VERSION、SKILL_VERSION
> 2. Skill 文件中的评分算法是否与工具实现匹配
> 3. 指南中的评分公式是否与 Skill 描述一致
>
> **输出格式**：一致性检查报告

**智能体产出**：
- 一致性检查报告 + 可能的修复项

### 3.10 B3.5 开源项目验证

| 字段 | 值 |
|:-----|:------|
| **调用时机** | 外部验证基线建立后，三方一致性检查之前 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 请对照验证案例集，在指定的开源项目上验证工具检测正确性。  
>
> **输入**：
> - 工具代码：src/arch_quality/arch_metrics_solver_physics.py
> - 验证案例集：docs/zh/求解器与物理场模块化架构模式识别评估验证案例集.md
> - 案例集指定的开源项目列表：
>   - Kratos Multiphysics (v9.0) → 预期 MPR-001/002/003 低违规范
>   - SU2 FSI (v7.5) → 预期触发 MPR-004
>   - preCICE (v3.0) → 预期 MPR-006
>   - MOOSE MultiApp → 预期 MPR-005/006 架构合理
>   - OpenFOAM multiRegionFoam → 预期 MPR-004/010 架构合理
>
> **验证流程**：
> 1. 从案例集提取 A 类"可复现"开源项目及预期表现
> 2. 对每个项目运行 all_metrics()
> 3. 对比实际结果与案例集预期（阳性→低违规范/高评分；阴性→触发对应 MPR）
> 4. 不一致项归因：误报 / 漏报 / 案例集预期过时

**差异归因策略**：
- 工具漏报 → 修复检测逻辑（禁改案例集）
- 工具误报 → 修复检测逻辑
- 案例集过时 → 更新案例集预期（需标注原因）

**证据使用原则**（防"凭常识断言"）：判定误报/漏报必须引用可核实证据——仓库文档（案例集预期）或本地实测（目录/构建/代码）。LLM 领域知识仅可作假设、标注"待验证"，不可作依据。领域知识提示怀疑方向，最终判定落到文档或实测证据。

> **参考**：MOOSE 验证中"模块化优秀"论断应拆分为可核实证据（案例集阳性预期 + modules/ 实测 20+ 模块），而非笼统的"公认"。

**LLM 漏报探查**（防"静态正则盲区"）：工具正则无法穷举所有框架命名惯例（如 MOOSE 用 `MooseObject` 而非 `Plugin/Module/Application/Solver`）。对低分项/工具未命中项，LLM 提出候选命名模式 → 实测归因（grep 继承统计 ≥ 阈值）→ 人工审查 → 固化到 `INTERFACE_BASE_CLASSES` 可扩展列表 → 防误报验证（deal.II/MFEM 无此继承）→ 回归测试。

> **参考**：MOOSE 统一接口盲区——工具原漏报 `MooseObject`，LLM 探查提出候选 → 实测 196 个继承 → 人工审查固化 → 已验证 deal.II/MFEM 无误报。

**智能体产出**：
- 开源项目验证报告（对照案例集预期）
- 误报/漏报分析 + 修复项 + LLM 漏报探查结果（候选模式 → 实测 → 固化记录）

> **参考**：《基于 OPENCODE 的架构质量评估 SKILL 开发指南》§B3.5

### 3.11 C1 注册 OpenCode 智能体

| 字段 | 值 |
|:-----|:------|
| **调用时机** | Skill 开发测试完成 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 请为新 Skill 生成 OpenCode 智能体注册文件。  
>
> **输入**：
> - 技能名称：solver-physics-architecture
> - 技能文件路径：.opencode/skills/solver-physics-architecture/SKILL.md
> - 评估命令：python -m arch_quality
> - 所需权限：read=allow, bash=ask, edit=deny, task=allow, skill=allow

**智能体产出**：
- `opencode1.json` 中的 agent 注册条目
- `opencode.json` 中的 skill 注册条目

### 3.12 C2 配置 CI/CD 门禁

| 字段 | 值 |
|:-----|:------|
| **调用时机** | 智能体注册完成后 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 请为评估工具生成 CI/CD 集成配置，在每轮提交中自动运行评估。  
>
> **输入**：
> - 评估命令：python -m arch_quality . --json
> - 阻断条件：MPR ERROR 触发时阻断
> - 报告存储路径：.opencode/arch-reports/

当前项目无 CI（无 `.github/workflows/`），生成脚本式门禁：

```bash
# CI 门禁脚本（可手动执行）
python -m pytest tests/test_solver_physics.py && \
python -m pytest tests/mutation/test_solver_physics_mutation.py && \
python -m pytest tests/regression/test_solver_physics_regression.py
```

### 3.13 C3 生成用户交互提示词

| 字段 | 值 |
|:-----|:------|
| **调用时机** | CI/CD 配置完成后 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 请生成面向最终用户的 OpenCode 交互提示词模板，方便用户调用此 Skill。  
>
> **输入**：
> - 技能名称：solver-physics-architecture
> - 评估命令：python -m arch_quality [项目路径] --json --md
> - 典型使用场景：多物理场项目架构评估、耦合逻辑分析、插件机制检查、数据传递规范性检查

**智能体产出**：

```
# 完整评估
请对当前项目运行求解器和物理场模块化架构模式识别评估，
输出 4 维评分和 MPR 违规详情

# 单维度分析
请分析当前项目的多物理场耦合架构合理性，
检查耦合逻辑是否集中、求解算法是否可替换

# MPR 解读
请解释 MPR-005（耦合逻辑集中度）在当前项目中的具体情况

# 改进建议
根据最近一次的评估结果，给出耦合架构方面的改进建议，
按 P0/P1/P2 分级
```

### 3.14 C4 生成评估报告模板

| 字段 | 值 |
|:-----|:------|
| **调用时机** | 用户交互提示词生成后 |
| **发送给** | `architecture-quality` 智能体 |

**用户提示词**：

> 请为评估结果生成 Markdown 报告模板。  
>
> **输出格式**：
> - 第一段：综合评分概览
> - 第二段：各维度评分表格
> - 第三段：MPR 违规列表（含置信度标注）
> - 第四段：改进建议

**智能体产出**报告模板：

```markdown
# 求解器和物理场模块化架构模式识别评估报告

**项目**：[项目名]
**日期**：[日期]
**综合评分**：[评分] / 100

## 维度评分

| 维度 | 权重 | 得分 | 评级 |
|:-----|:----:|:----:|:-----|
| 物理场模块边界完整性 | 25% | [分] | [评级] |
| 多物理场耦合架构合理性 | 30% | [分] | [评级] |
| 插件式扩展架构支持度 | 25% | [分] | [评级] |
| 跨场数据传递规范性 | 20% | [分] | [评级] |

## MPR 违规

| 规则 | severity | output_level | 置信度 | 详情 |
|:-----|:--------:|:------------:|:------:|:-----|

## 改进建议

| 优先级 | 建议 | 预期提分 |
|:------:|:-----|:--------:|
```

---

## 第四章：文件清单与类设计

### 4.1 文件清单

```
新增：
  src/arch_quality/skills/solver-physics-architecture.md            # 权重+评分算法(方案D解析)
  src/arch_quality/arch_metrics_solver_physics.py                   # SolverPhysicsMetrics 主类
  .opencode/skills/solver-physics-architecture/SKILL.md             # OpenCode Skill 入口
  tests/test_solver_physics.py                                      # 单元测试 (~30)
  tests/regression/test_solver_physics_regression.py                # 回归测试 (snapshot)
  tests/mutation/projects/good_multiphysics/...                     # 变异测试良好项目
  tests/mutation/mutation_cases_sp.json                             # 变异案例定义
  tests/mutation/test_solver_physics_mutation.py                    # 变异测试
  scripts/cross_validate_solver_physics.py                          # k-fold 交叉验证
  scripts/consistency_check_solver_physics.py                       # 三方一致性检查
  scripts/run_agent_harness.py                                      # agent harness 入口
  opencode-harness/                                                 # agent harness（runner+断言器+用例+rules.json）
  .opencode/plugins/agent-assert.js                                 # 框架级自动断言插件

修改：
  src/arch_quality/arch_report.py             # ComprehensiveReport 集成
  src/arch_quality/arch_report_generator.py   # 新增报告章节
```

**B3.5 增强修复**（均已实现）：
- `_scan_config_dictionaries`（arch_metrics_solver_physics.py）：扫描 OpenFOAM `fvSolution`/`controlDict` 配置字典，`residualControl` 计入耦合收敛（消除 MPR-006 误报）
- `_detect_coupling_architecture` 两阶段信号检测：多模式库（preCICE）核心求解语义优先于接口文档（消除 MPR-004 误报）
- `_detect_multiphysics` 求解器目录回填：识别 FreeFEM 风格 `src/fflib` 等功能名模块目录（消除 MPR-001 误报）

### 4.2 类设计

```python
class SolverPhysicsMetrics:
    """求解器和物理场模块化架构模式评估"""

    def __init__(self, root: str, build_dir: str = ""):
        self.root = root
        self.weights = _load_weights()           # 从 skill .md 解析
        self.index = FileIndex(root)
        self.graph = DepGraph()
        self._is_multiphysics = self._detect_multiphysics()
        self._solver_dirs = []
        self._header_functions = {}

    def _detect_multiphysics(self) -> bool:
        """自动检测是否为多物理场项目"""

    def calc_boundary_integrity(self) -> tuple[float, dict]:     # 25%
    def calc_coupling_architecture(self) -> tuple[float, dict]:  # 30%
    def calc_extension_support(self) -> tuple[float, dict]:      # 25%
    def calc_data_transfer(self) -> tuple[float, dict]:          # 20%
    def check_mpr_rules(self) -> list[dict]:                     # 12 条 MPR
    def calc_overall(self) -> float:                             # 综合评分
    def all_metrics(self) -> dict:                               # 完整结果
```

### 4.3 检测手段对照表

| 检测目标 | 技术手段 | 置信度 |
|:---------|:---------|:------:|
| 独立编译单元 | CMake/Makefile 分析 + 目录结构扫描 | 高 |
| API 精简度 | 符号表提取（正则从 .h 提取公开函数） | 高 |
| MMS 基准存在性 | `glob *_mms* *_verification*` | 中 |
| 内部数据访问 | AST/正则跨模块直接成员访问模式匹配 | 低 |
| 耦合架构模式 | 迭代模式识别 + 耦合强度判定矩阵 | 中低 |
| 耦合逻辑集中度 | AST 调用图分析跨文件耦合分布 | 高 |
| 求解算法可替换性 | 抽象基类 + 多实现检测 | 高 |
| 收敛稳定性 | 收敛控制参数扫描 | 中 |
| 标准耦合接口 | FMI 必须函数存在性检测 | 高 |
| 插件机制 | 目录结构 + 统一基类检测 | 高 |
| 循环依赖 | NetworkX 强连通分量检测 | 高 |
| 接口版本管理 | @deprecated 正则匹配 | 中 |
| Field/Data 模式 | 统一 Data/Field 基类使用检测 | 中 |
| FMI 合规性 | zipfile 解包 + XML 验证 | 高 |
| 数据格式转换 | 转换函数分散程度统计 | 低 |

---

## 第五章：4 维度评分算法

### 5.1 维度 1：物理场模块边界完整性（25%）

| 子项 | 分值 | 检测方法 | 置信度 |
|:-----|:----:|----------|:------:|
| 独立编译单元检测 | 20 | CMake `add_subdirectory` / 独立源目录 | 高 |
| 公开 API 精简度（≤50 阈值） | 20 | 符号表统计 | 高 |
| MMS 验证基准存在性 | 30 | `glob *_mms* *_verification*` | 中 |
| 内部数据结构封装性 | 30 | 跨模块直接成员访问模式匹配 | 低 |
| FMI 模型交换模式支持 | +10 | FMI/FMU 接口实现检测 | 高 |

```
score = sum(子项得分)
if 检测到 FMI/FMU 接口实现:
    score = min(score + 10, 110)
result = min(score, 100)
```

### 5.2 维度 2：多物理场耦合架构合理性（30%）

| 子项 | 分值 | 置信度 |
|:-----|:----:|:------:|
| 耦合架构与耦合强度匹配度 | 20 | 中 |
| 耦合逻辑集中度 | 20 | 高 |
| 求解算法可替换性 | 15 | 高 |
| 迭代收敛稳定性 | 15 | 中 |
| 标准耦合接口支持度 | 15 | 高 |
| 系统层级验证完整性（ASME V&V 10） | 15 | 中 |

### 5.3 维度 3：插件式扩展架构支持度（25%）

| 子项 | 分值 | 置信度 |
|:-----|:----:|:------:|
| 标准接口动态加载 | 30 | 高 |
| 依赖关系形式化 | 25 | 高 |
| 无循环依赖 | 25 | 高 |
| 接口版本管理 | 20 | 中 |

**递进扣分规则**（指南 §2.3）：若维度 1 得分 < 60，本维度得分自动折半。

### 5.4 维度 4：跨场数据传递规范性（20%）

| 子项 | 分值 | 置信度 |
|:-----|:----:|:------:|
| 标准化数据结构（Field/Data） | 20 | 高 |
| FMI 协同仿真数据传递 | 15 | 高 |
| 数据格式转换统一性 | 20 | 低 |
| 时间同步机制规范性 | 15 | 中 |
| 空间映射架构独立性 | 15 | 中 |
| 时间步协调策略合理性 | 15 | 中 |

**FMI 合规加分**（最多 +5，不超 100）：
- FMU `modelDescription.xml` 存在性（+2）
- 必要函数实现（fmi2DoStep 等）（+2）
- 多 FMU 接口一致性（+1）

---

## 第六章：12 条 MPR 规则

| 规则 | 名称 | output_level | severity | 置信度 | 维度 | 检测方法 | 优先 |
|:-----|:------|:------------:|:--------:|:------:|:----:|----------|:----:|
| MPR-001 | 物理场模块边界识别 | **ERROR** | HIGH | 高 | 边界完整性 | CMake 目标 + 目录结构 | **P0** |
| MPR-002 | 模块公开接口精简度 | **WARNING** | MEDIUM | 高 | 边界完整性 | 符号表统计 > 50 | **P0** |
| MPR-003 | 模块数值验证基准完备性 | **ERROR** | HIGH | 中 | 边界完整性 | MMS 目录 glob 未命中 | P1 |
| MPR-004 | 耦合架构模式判定 | **WARNING** | MEDIUM | 中低 | 耦合架构 | 迭代模式启发式识别 | P2 |
| MPR-005 | 耦合逻辑集中度 | **WARNING** | HIGH | 高 | 耦合架构/数据传递 | AST 跨文件调用分析 | P1 |
| MPR-006 | 迭代收敛稳定性 | **WARNING** | MEDIUM | 中 | 耦合架构 | 收敛参数 + 迭代计数 | P3 |
| MPR-007 | 插件扩展完整性 | **WARNING** | HIGH | 高 | 扩展架构 | 注册模式 + 统一接口 | P1 |
| MPR-008 | 跨模块依赖关系 | **ERROR** | MEDIUM | 高 | 扩展架构 | 依赖图 + NetworkX 循环检测 | **P0** |
| MPR-009 | 接口版本管理 | **WARNING** | MEDIUM | 中 | 扩展架构 | @deprecated 注解 + 版本号 | P2 |
| MPR-010 | 跨场数据传递标准化 | **WARNING** | MEDIUM | 中 | 数据传递 | Field/Data + FMI 接口 | **P0** |
| MPR-012 | 数据格式转换统一性 | **INFO** | LOW | 低 | 数据传递 | 转换函数分布分析 | P2 |
| MPR-FMI | FMI 合规性 | **BONUS** | — | 高 | 边界/数据 | zipfile + XML + 函数签名 | P3 |

---

## 第七章：报告集成与权重归一化

### 7.1 集成到 ComprehensiveReport

```python
from arch_quality.arch_metrics_solver_physics import SolverPhysicsMetrics

class ComprehensiveReport:
    def __init__(self, root: str, build_dir: str = ""):
        # ... 现有初始化
        self.solver_physics = SolverPhysicsMetrics(root, build_dir=build_dir)

    def generate(self) -> dict:
        std_result = self.standard.all_metrics()
        ml_result = self.multilang.all_metrics()
        tpl_result = self.template.all_metrics()
        nvr_result = self.numerical.all_metrics()
        sp_result = self.solver_physics.all_metrics()

        is_multiphysics = sp_result.get("is_multiphysics", False)
        # 权重归一化逻辑扩展
```

### 7.2 权重归一化方案

当 4 种增强同时激活时：

```
原始权重和:  55%(基础) + 15%(multilang) + 15%(template) + 10%(numerical) + 15%(solver-physics) = 110%

归一化公式:  normalized_w = raw_w / sum(raw_w)

结果:
  基础结构质量   = 55/110 = 50.00%
  multilang      = 15/110 = 13.64%
  template       = 15/110 = 13.64%
  numerical      = 10/110 =  9.09%
  solver-physics = 15/110 = 13.64%
  合计           = 100.00%
```

### 7.3 报告章节

在 `arch_report_generator.py` 中新增章节：

```
## 七、求解器和物理场模块化架构模式识别评估
  7.1 综合得分表
  7.2 4 维度明细
  7.3 MPR 规则违反列表（带置信度标注）
  7.4 改进建议（Top 3）
```

---

## 第八章：测试框架

### 8.1 B1 单元测试（`tests/test_solver_physics.py`）

| 分组 | 数量 | 内容 |
|:-----|:----:|------|
| 辅助函数 | 5 | `_detect_multiphysics()`、检测模式正则、权重解析 |
| 非多物理场项目 | 2 | 纯 Python → `is_multiphysics=False`，各维度 None |
| 多物理场项目基础 | 3 | 合成项目评分、权重和 100% |
| 边界完整性维度 | 4 | 各子项评分逻辑 |
| 耦合架构维度 | 4 | 各子项评分逻辑 |
| 扩展架构维度 | 2 | 含递进扣分 |
| 数据传递维度 | 3 | 含 FMI 加分 |
| MPR 规则 | 5 | MPR-001/002/005/008/010 |
| 权重解析 | 2 | 和=100% 验证、解析错误 |

### 8.2 B2 变异测试

**良好项目结构**：

```
good_multiphysics/
├── CMakeLists.txt              # 3 个 add_subdirectory
├── src/
│   ├── structural/Solver.h/Solver.cpp
│   ├── thermal/Solver.h/Solver.cpp
│   └── fluid/Solver.h/Solver.cpp
├── coupling/
│   ├── CouplingLayer.h/cpp
│   └── FMIInterface.cpp
├── plugin/
│   └── PluginRegistry.cpp
└── tests/
    └── mms_verification/
        ├── structural_mms.cpp
        └── thermal_mms.cpp
```

**10 个变异案例**：

| ID | 变异 | 预期 MPR |
|:---|:-----|:--------:|
| MUT-SP-001 | 合并求解器到同一 .cpp | MPR-001 |
| MUT-SP-002 | 暴露内部数据结构为公开 API | MPR-002 |
| MUT-SP-003 | 删除 mms_verification/ | MPR-003 |
| MUT-SP-004 | 强耦合→松散文件 | MPR-004 |
| MUT-SP-005 | 耦合逻辑散布到求解器 | MPR-005 |
| MUT-SP-006 | 删除收敛控制参数 | MPR-006 |
| MUT-SP-007 | 删除 PluginRegistry.cpp | MPR-007 |
| MUT-SP-008 | 头文件循环 #include | MPR-008 |
| MUT-SP-009 | 删除 fmi2DoStep | MPR-010 |
| MUT-SP-010 | 格式转换函数散布 | MPR-012 |

### 8.3 B3 外部验证基线

#### 回归测试

- 基线项目：3 个内部合成项目（good/bad/mixed）
- Snapshot：`tests/regression/snapshots/sp_good.json` 等
- tolerance：`overall=0.5`, `dimension=1.0`
- 更新：`$env:ARCH_REGRESSION_UPDATE=1`

#### 开源项目评估案例集验证

| 项目 | 预期表现 |
|:-----|:---------|
| Kratos Multiphysics (v9.0) | MPR-001/002/003/005/008 → 不触发或少量 |
| OpenFOAM multiRegionFoam | MPR-004/005 → 架构合理 |
| MOOSE MultiApp | MPR-004(sys)/005/006 → 良好 |
| SU2 FSI | MPR-004/006 → 可评估 |
| preCICE | MPR-006 → 耦合工具架构 |

### 8.4 B4 三方一致性检查

检查项：
- 维度数量一致（4）
- 权重和 = 100%（25+30+25+20）
- 评分分段函数阈值一致
- MPR 规则数量一致（12）
- severity/置信度一致

---

## 第九章：k-fold 交叉验证

**参照**：`scripts/cross_validate.py`（数值精度 LOOCV 模式）

**实现**：`scripts/cross_validate_solver_physics.py`（已实现，✅）

```
方法: Leave-One-Out (9-fold)
项目: sp_moose / sp_openfoam / sp_kratos / sp_dealii / sp_mfem /
      sp_elmerfem / sp_freefem / sp_su2 / sp_precice（9 项目基线）

每轮:
  1. 留 1 项目为测试集，其余 8 为训练集
  2. 计算训练集评分范围 [min, max]
  3. 判断测试集评分是否在范围内
  4. 对比 MPR 规则模式（训练集未见的新规则 → 标记为可能异常）

判定:
  9/9 在范围内 → PASS
  8/9         → WARNING
  ≤7/9        → FAIL（需校准阈值）

输出:
  docs/zh/求解器和物理场模块化架构模式识别评估/交叉验证报告_solver_physics.md
```

**实际结果**（2026-08-17）：7/9 泛化，WARNING。MOOSE(70.5) 偏高、OpenFOAM(38.0) 偏低为离群，反映不同架构类型（框架/库/求解器/耦合库）的评分极值差异，属真实特征。

---

## 第十章：验证里程碑时间线

| 优先 | 里程碑 | 证据 | 工作量 | 依赖 |
|:----:|:-------|:-----|:------:|:----:|
| **P0** | 外部验证基线（5 项目） | 基线快照 + 人工审查报告 | 0.5d | 阶段 A 完成 |
| **P1** | 10 个变异测试全部通过 | 变异测试报告 | 0.5d | P0 |
| **P2** | 人工评审框架 | 评审模板 + 数据比对脚本 | 0.2d | P1 |
| **P3** | 5-fold 交叉验证 ≥ 4/5 泛化 | 交叉验证报告 | 0.3d | P0（基线就绪） |

---

## 第十一章：总工作量估算

| 阶段 | 交互 | 内容 | 人日 |
|:-----|:----:|:-----|:----:|
| A1 A2 初始化+维度定义 | A1~A2 | skill .md 骨架 + 评分算法 | 0.6 |
| A3 定义规则 | A3 | 12 条 MPR 规则写入 skill .md | 0.2 |
| A3.5 质量审查 | A3.5 | 审查 SKILL 文件 6 维度、修复问题 | 0.2 |
| A4 实现工具 | A4 | `SolverPhysicsMetrics` 全类 + 报告集成 | 3.0 |
| A4 工具设计文档 | A4 | 指南→工具映射（检测正则级）+ 工程化偏差 | 0.5 |
| B1 单元测试 | B1 | 30 个测试用例 | 0.5 |
| B2 变异测试 | B2 | 良好项目 + 10 案例 | 0.5 |
| B2.5 集成 & E2E 测试 | B2.5 | 集成测试 + 端到端测试 | 0.3 |
| B3 外部基线 | B3 | 回归测试 + 基线快照 | 0.5 |
| B3.5 开源项目验证 | B3.5 | 对照案例集验证检测正确性 + 报告 | 0.3 |
| B4 一致性检查 | B4 | 脚本适配 + 验证 | 0.2 |
| C1~C4 部署 | C1~C4 | 智能体注册 + 提示词 + 报告模板 | 0.1 |
| k-fold 交叉验证 | — | 脚本 + 报告 | 0.3 |
| **合计** | **17 步** | | **7.2 人日** |

---

## 第十二章：关键设计决策

| 决策 | 选项 | 选型 | 理由 |
|:-----|:-----|:-----|:------|
| 独立 CLI 入口 | 设 / 不设 | **不设** | 仅作为结构质量增强集成在 ComprehensiveReport 中 |
| 权重归一化 | 等比 / 固定 | **等比归一化** | 4 增强同时激活时权重和 >100%，等比缩放保持比例 |
| MPR-004 置信度 | 接受启发式 / 要求精确 | **接受，标注"需人工确认"** | 耦合架构模式天然无法精确判定 |
| 检测手段 | 纯静态 / 混合 | **纯静态分析为主** | 零外部工具依赖 |
| FMI 检测 | Python zipfile / 外部工具 | **zipfile + XML + AST** | 零依赖 |
| 项目检测触发 | 目录名/文件名 / 人工标记 | **目录名+文件内容自动检测** | 与 numerical 自动启用一致 |
