# 数值算法正确性与精度保障评估技能

本技能提供数值算法正确性与精度保障评估的领域知识，包括 6 个评估维度定义、评分算法、12 条 NVR 规则、基线校准方法和豁免验证框架。

> **版本绑定**
> - 对应《数值算法正确性与精度保障评估指南》**1.8 版**
> - 对应实现：`arch_metrics_numerical_accuracy.py`
> - 技能版本：**1.6**（`SKILL_VERSION = "1.6"`，对齐指南 1.8）
> - 如需升级指南版本，需同步更新本 skill 和实现代码
> - **三方一致性**：指南 §2.6 ↔ Skill §2.6 ↔ Tool `calc_numerical_debt()` 的评分算法应保持一致。修改任一方时需同步其他两方。

## 引用文档

| 文档 | 版本 | 角色 |
|:-----|:----:|:-----|
| 《数值算法正确性与精度保障评估指南》 | 1.8 | 领域知识：维度定义、规则说明、评级标准 |
| 《数值算法正确性与精度保障评估验证案例集》 | 1.1 | 验证数据：各 NVR 规则的阴性/阳性案例 |
| 《MMS 测试技能定义》 | — | 验证执行：MMS Testing Skill 的输出反馈到 NVR-005/NVR-006 |

---

## 一、权重分配

与指南 §1 一致：

| 维度 | 权重 | 对应指南章节 |
|:-----|:----:|:-------------|
| 数值稳定性保障 | 25% | §2.1 |
| 舍入误差与数值敏感度控制 | 20% | §2.2 |
| 验证完备性 | 20% | §2.3 |
| 误差估计与控制 | 15% | §2.4 |
| 数值回归测试覆盖 | 10% | §2.5 |
| 数值债务密度 | 10% | §2.6 |

综合评分：`S = Σ(维度得分 × 权重)`，见指南 §3。

---

## 二、维度定义与评分算法

每个维度包含：代码坏味道名称、检测方法、评分算法。评分算法从指南的文字描述中提取为可执行的分段函数。

### 2.1 数值稳定性保障（25%）

**代码坏味道：** "CFL 条件裸奔"——未检测到 CFL 稳定性措施或时间步控制，显式格式在病态条件下可能发散。

**检测方法：**
- 扫描 `fvSchemes` 中 `ddtSchemes` 的类型（`Euler` 一阶、`CrankNicolson` 二阶有界、`steadyState` 无条件稳定）
- 扫描控制文件中是否有 `maxCo`、`maxDeltaT` 等 CFL 控制参数
- 检测时域积分方法是隐式还是显式
- 统计显式格式文件占比（`cfl_ratio = 显式格式文件数 / 求解器文件总数`）
- **迎风格式**：`upwind`、`linearUpwind`、`bounded`
- **限制器/人工粘性**：`limiter`、`slopeLimiter`、`artificial`、`artificialViscosity`
- **源项线性化**：`SuSp`、`SemiImplicitSource`、`sourceImplicit`
- **稳定性注解**：`stability_assured`
- **Fortran 支持**：检测 `subroutine`、`program` 关键词识别 Fortran 求解器代码
- **结构分析支持**：检测 `hourglass`、`penalty`、`stiffness` 等稳定性关键词

**评分算法：**

```
cfl_ratio = explicit_scheme_files / total_solver_files

if has_cfl_control and has_stability_measures:     score = 100
elif has_cfl_control:                               score = 80
elif has_stability_measures and cfl_ratio < 0.3:    score = 70
elif has_stability_measures:                        score = 50
elif cfl_ratio < 0.3:                               score = 30
else:                                                score = 10
```

> **关于 `cfl_ratio < 0.3` 的说明**：该阈值为工程经验值，当前无文献直接支撑。
> - 30% 的显式格式文件占比被视为"显式格式未泛滥"的经验界限
> - 适用范围：稳态 CFD 和结构分析代码，对纯显式求解器（如 rhoCentralFoam）可能需要调整
> - **校准状态**：待补充。当前基于经验设定，建议从验证案例集中选取 3-5 个项目做数据校准。
> - **可配置**：阈值可通过 `CFL_RATIO_THRESHOLD` 参数在运行时覆盖（参见 `arch_metrics_numerical_accuracy.py`）。

**参考：** 指南 §2.1，案例集 §1。

### 2.2 舍入误差与数值敏感度控制（20%）

**代码坏味道：** "浮点相消陷阱"——浮点数量级相差悬殊的加减运算导致有效数字丢失，累积误差未被控制。

**检测方法：**
- 扫描源码中是否使用 `Kahan`、`compensated`、`high_precision` 等补偿求和关键词
- 检测大规模累加循环中是否使用 `double`（建议）还是 `float`（警告）
- 检测 `volScalarField` 等场量的精度声明

**评分算法：**

```
base = 100
if 存在浮点相消模式（cancellation_sites > 0）:   base -= 20
if 无动态工具(Verrou/CADNA)且相消模式较多(>5):   base -= 25
if 无 Kahan 求和补偿:                            base -= 15
score = max(0, base)
```

> 与指南 §2.2 的对应：`D(灾难性抵消)→ cancellation_sites > 0`，`S(敏感度评分)→ 无动态工具 + 相消>5`，`A(累加控制)→ 无Kahan`。与工具 `calc_roundoff_sensitivity()` 一致。

**参考：** 指南 §2.2，案例集 §3。

### 2.3 验证完备性（20%）

**代码坏味道：** "MMS 缺失"——数值算法模块缺少方法制解验证，离散实现正确性未经过系统验证。

**检测方法：**
- 检测项目中是否存在 MMS 相关文件（`*mms*`、`*manufactured*`、`*verification*`）
- 检测 `MMS Testing Skill` 的输出（`.opencode/skills/mms-testing/`）
- 检测收敛阶记录（`p_obs` 值）

**评分算法：**

```
p_obs = 从 MMS Testing Skill 获取（若无则为 None）

if p_obs is None:
  score = 0       # 无 MMS 验证
elif |p_obs - p_theory| <= 0.1:
  score = 100     # MMS 验证通过
elif |p_obs - p_theory| <= 0.2:
  score = 50      # 观察阶偏差可接受
else:
  score = 20      # 观察阶严重偏离
```

**参考：** 指南 §2.3，案例集 §5-§6，MMS Testing Skill。

### 2.4 误差估计与控制（15%）

**代码坏味道：** "残差盲飞"——离散误差和迭代误差未被估计或控制，数值解精度未知。

**检测方法：**
- 检测 `fvSolution` 中是否有 `tolerance`、`relTol` 设置
- 检测 `residualControl` 是否配置
- 检测是否进行网格收敛性研究（`h` 变化时误差对比）
- 扫描目录命名中是否包含 `Coarse`、`Medium`、`Fine`、`Refined`、`Level[0-9]` 等细化模式（使用 `\b` 词边界避免子串误报如 `refinement`）
- 内容关键词：`mesh_convergence`、`grid_convergence`、`refinement_study`、`richardson_extrap`（带后缀以区分开发者姓名）、`element_size`
- 解析 `tolerance` 值是否在合理范围（1e-4 ~ 1e-12），支持 Fortran `D` 格式（如 `1.0D-8`）

**评分算法：**

```
has_solver_code = 检测项目是否包含求解器代码

if not has_solver_code:
  score = None  # 无求解器，不评分（与稳定性维度一致）

score = 0
if 有网格收敛性研究 OR 有细化目录模式:     score += 40
if 有残差/容差关键词:                      score += 30
if tolerance 值在 1e-4 ~ 1e-12 范围内:     score += 30
```

**参考：** 指南 §2.4，案例集 §7-§8。

### 2.5 数值回归测试覆盖（10%）

**代码坏味道：** "回归裸奔"——关键数值模块缺少回归测试保护，代码修改可能引入精度退化而不自知。

**检测方法：**
- 识别关键数值模块：触发 NVR-001/002/005 规则的模块
- 统计关键模块的回归测试覆盖率：`coverage = N_tested / N_critical × 100`
- 检测回归测试中是否设定了精度断言（`assert`/`check`/`tolerance`）
- 检测快照基线文件（`.json` 中包含 `baseline`/`snapshot`/`golden`）
- CI 配置仅作为辅助信息，不影响评分

**评分算法：**

```
N_critical = 触发 NVR-001/002/005 的模块数
N_tested   = 其中有关键回归测试的模块数

if N_critical == 0:           score = 100  （无关键模块）
elif N_tested >= N_critical:  score = 100  （全部覆盖）
else:                         score = N_tested / N_critical × 100

# 断言和快照作为加分项
if has_assertion:             score = min(score + 15, 100)
if has_snapshot_baseline:     score = min(score + 10, 100)
```

**参考：** 指南 §2.5，案例集 §9-§10。

### 2.6 数值债务密度（10%）

**代码坏味道：** "数值维度塌方"——多个评估维度得分低于 50，系统性的数值精度缺陷尚未清理。

**检测方法：**
- 统计 6 个评估维度中得分低于 50 的维度个数（`low_score_count`）
- 低分维度比例 = low_score_count / 6
- 评分算法不需要独立扫描源码，而是聚合其他 5 个维度的评估结果

**评分算法：**

```
debt_ratio = low_score_count / 6
score = max(0, 100 - debt_ratio * 200)
```

**评分示例：**

| low_score_count | debt_ratio | score | 评级 |
|:---------------:|:----------:|:-----:|:-----|
| 0 | 0.0% | 100 | ? 低债务 |
| 1 | 16.7% | 66.67 | ??? 中债务 |
| 2 | 33.3% | 33.33 | ??? 高债务（触发 NVR-012）|
| 3+ | ≥50% | 0 | ??? 极高债务 |

> **说明**：本维度的评分算法与其他 5 个维度不同——它不是直接扫描源码，而是聚合其他维度的评分结果。因此不需要独立的源码检测模式，但前提是其他 5 个维度的评分准确可靠。

**参考：** 指南 §2.6，案例集 §11。评分算法与指南 §2.6 和工具 `calc_numerical_debt()` 一致。

---

## 三、基线校准

评分阈值根据验证案例集的实测数据校准。校准方法参照指南 §3 和 §7。

### 校准数据来源

| 数据源 | 类型 | 用途 |
|:-------|:-----|:------|
| OpenFOAM 案例（案例集 §1.1）| CFL 违规 | 校准 NVR-001 阈值 |
| CalculiX 静态分析（案例集 §2.1）| 条件数 | 校准 NVR-002 阈值 |
| SU2 相消性损失（案例集 §3.1）| 浮点相消 | 校准 NVR-003 阈值 |
| code_aster 累积误差（案例集 §4.1）| 累积误差 | 校准 NVR-004 阈值 |
| 某开源 FEM 缺少 MMS（案例集 §5.1）| MMS 缺失 | 校准 NVR-005 阈值 |
| ABAQUS/SU2 MMS（案例集 §6.1-6.3）| 观察阶 | 校准 NVR-006 阈值 |
| MOOSE 误差研究（案例集 §7.1）| 离散误差 | 校准 NVR-007 阈值 |
| PETSc 残差控制（案例集 §8.1）| 迭代误差 | 校准 NVR-008 阈值 |
| INL BISON 回归（案例集 §9.1）| 回归缺失 | 校准 NVR-010 阈值 |

### 校准方法

与模板元编程 skill §8.1 一致的统计校准流程：

```
1. 收集案例集的阳性案例（通过）的评分数据
2. 收集阴性案例（违规）的评分数据
3. 计算阳性案例评分分布的 5% 分位数作为及格线
4. 计算阳性案例评分分布的均值作为基准分
5. 验证阴性案例的评分是否全部低于及格线
```

---

## 四、豁免注解体系

### 4.1 注解类型

参照模板元编程 skill 的 `@template_specialization_required`、`@allow_binary_bloat`、`@reserved_for_future_extension` 设计，数值精度评估定义以下豁免注解：

| 注解 | 适用规则 | 必填字段 | 说明 |
|:-----|:--------|:---------|:------|
| `@mms_exempt` | NVR-005 | `reason`, `verification_method`, `test_script`, `threshold` | 无法执行 MMS 时的替代验证方案 |
| `@order_deviation_allowed` | NVR-006 | `reason`, `expected_order`, `observed_order`, `benchmark_case` | 观察阶偏差在特定场景下可接受 |

### 4.2 `@mms_exempt` 格式

```
@mms_exempt(
    reason = "解析解已知，不需 MMS",              # 必填：豁免理由
    verification_method = "解析解对比",            # 必填：替代验证方法
    test_script = "tests/analytical/compare.py",   # 必填：验证脚本路径
    threshold = "L2_error < 1e-8"                  # 必填：精度阈值
)
```

### 4.3 `@order_deviation_allowed` 格式

```
@order_deviation_allowed(
    reason = "SIMPLE 算法在 collocated grid 上天然约 1.9",  # 必填
    expected_order = 2.0,                                      # 必填
    observed_order = 1.91,                                     # 必填
    benchmark_case = "lid_driven_cavity_Re100"                 # 必填
)
```

### 4.4 验证规则

- 豁免注解必须包含所有必填字段，缺失任一字段 → `output_level` 不降级（等价于模板 MLR-017 的验证规则）
- 字段值为空 → 视为缺失
- 豁免注解仅在同文件内生效，跨文件引用不作用

---

## 五、12 条 NVR 规则

每条规则包含：编号、名称、`output_level`、`severity`、代码坏味道描述、检测方法、豁免可能性。详细定义见指南 §5 和案例集对应章节。

| 规则 | 名称 | output_level | severity | 代码坏味道 | 豁免 | 指南§ | 案例集§ |
|:-----|:------|:------------:|:--------:|:-----------|:----:|:-----:|:-------:|
| NVR-001 | 数值稳定性溢出 | **ERROR** | HIGH | 无 CFL 控制、无时间步限制 | 否 | §5.1 | §1 |
| NVR-002 | 条件数超限 | **ERROR** | HIGH | 线性系统条件数 > 1e6 未检测 | 否 | §5.2 | §2 |
| NVR-003 | 相消性损失 | **ERROR** | HIGH | 浮点相消模式未受控 | 否 | §5.3 | §3 |
| NVR-004 | 累积误差失控 | **WARNING** | MEDIUM | 浮点累加未使用补偿算法 | 否 | §5.4 | §4 |
| NVR-005 | MMS 验证缺失 | **ERROR** | HIGH | 数值算法模块缺少 MMS | 是(@mms_exempt) | §5.5 | §5 |
| NVR-006 | 观察阶偏差 | **ERROR** | HIGH | 观察阶与理论阶偏差 > 0.2 | 是(@order_deviation_allowed) | §5.6 | §6 |
| NVR-007 | 离散误差未控 | **WARNING** | MEDIUM | 网格收敛性研究缺失 | 否 | §5.7 | §7 |
| NVR-008 | 迭代误差未控 | **WARNING** | MEDIUM | 残差控制缺失 | 否 | §5.8 | §8 |
| NVR-010 | 回归测试缺失 | **WARNING** | MEDIUM | 关键数值模块缺少回归测试 | 否 | §5.10 | §9 |
| NVR-011 | 回归允许值缺失 | **INFO** | LOW | 回归测试未设精度断言阈值 | 否 | §5.11 | §10 |
| NVR-012 | 数值债务密度 | **INFO** | LOW | 数值技术债密度 > 30% | 否 | §5.12 | §11 |

**注意**：`output_level` 与 `severity` 解耦（与模板 MLR 体系一致）。豁免注解可将 `output_level` 从 ERROR 降为 INFO，但不改变 `severity`。

---

## 六、跨规则协调

### 6.1 NVR-005 + NVR-006 关联检测

MMS 验证缺失（NVR-005）和观察阶偏差（NVR-006）在逻辑上关联：

- 若 NVR-005 触发（无 MMS）→ NVR-006 自动跳过（无可用的 p_obs）
- 若 NVR-006 触发（p_obs 偏差）→ NVR-005 自动通过（MMS 存在）
- 若同时检测到 `@mms_exempt` 和 `@order_deviation_allowed` → 检查两个豁免的 `reason` 字段是否矛盾

实现方式（参照模板 MLR-014 + MLR-017 的协调检测）：

```python
if nvr005_triggered:
    nvr006_skip = True    # 无 MMS → 无可用的观察阶
if nvr006_triggered:
    nvr005_exempt = True  # 有 MMS → 验证存在
```

### 6.2 NVR-007 + NVR-008 关联检测

离散误差和迭代误差的估计与控制应同时检查：

- 若检测到 `residualControl` 但无网格收敛研究 → NVR-007 触发（离散误差未控）
- 若检测到网格收敛性研究但无残差控制 → NVR-008 触发（迭代误差未控）
- 两者同时通过 → 误差估计与控制维度得分较高

### 6.3 与 MMS Testing Skill 的接口

MMS 测试 skill（`.opencode/skills/mms-testing/`）的输出反馈到 NVR-005 和 NVR-006：

```
MMS Testing Skill 输出                          →   NVR 规则
─────────────────────                                ─────────
mms_demo.py: p_obs = 2.001, PASS                    NVR-005: 未触发
openfoam_simplefoam_mms.py: p_obs = 1.919, CLOSE    NVR-006: WARNING（偏差 0.08 < 0.1）
无 MMS 脚本                                          NVR-005: ERROR
```

---

## 七、引用关系总表

| 技能章节 | 引用指南 | 引用案例集 | 备注 |
|:---------|:---------|:-----------|:------|
| §1 权重 | §1 | — | 无 |
| §2.1 数值稳定性 | §2.1 | §1 | 评分算法为独立编写 |
| §2.2 舍入误差 | §2.2 | §3 | 评分算法为独立编写 |
| §2.3 验证完备性 | §2.3 | §5-§6 | 与 MMS Testing Skill 联动 |
| §2.4 误差估计 | §2.4 | §7-§8 | 评分算法为独立编写 |
| §2.5 数值回归 | §2.5 | §9-§10 | 评分算法为独立编写 |
| §2.6 数值债务 | §2.6 | §11 | 评分算法为独立编写 |
| §3 基线校准 | §3, §7 | 全部 | 校准方法参照模板 skill |
| §4 豁免注解 | — | — | 独立编写，参照模板体系 |
| §5 NVR 规则 | §5 | 各对应 § | 规则描述引用指南 |
| §6.1-6.2 跨规则协调 | — | — | 独立编写 |
| §6.3 MMS 接口 | — | — | 独立编写，定义 skill 间调用关系 |

---

## 八、启用条件

数值算法精度增强维度在检测到数值密集型项目时自动启用，权重占结构质量的 10%。

**数值密集型项目判定标准**（满足任一）：

| 判定条件 | 检测方式 | 阈值 |
|:---------|:---------|:-----|
| 求解器关键词 | 文件名/目录名包含 `solver`、`cfd`、`fem`、`fvm`、`pde` | ≥ 1 个 |
| 数学库引用 | 依赖 `Eigen`、`PETSc`、`trilinos`、`OpenFOAM`、`deal.II` | ≥ 1 个 |
| 计算域代码占比 | `float`/`double`/`vector`/`matrix` 关键词出现频率 | > 20% 文件 |

**三者同时启用时的权重调整**（与模板元编程体系一致）：

| 维度 | 权重 |
|:-----|:----:|
| 基础结构质量 | 60% |
| 多语言增强 | 15% |
| 模板增强 | 15% |
| 数值算法精度增强 | **10%** |

---

## 九、版本历史

| 版本 | 日期 | 变更 |
|:-----|:-----|:------|
| 1.0 | — | 初始版本，对齐评估指南 1.0 |
| 1.5 | — | 对齐评估指南 1.5 版，新增豁免注解体系、跨规则协调、MMS Testing Skill 接口 |
| **1.6** | **2026-07-14** | **对齐修正版**：§2.6 数值债务密度从"注释扫描法"改为"维度低分统计法"，与指南 1.8 和工具实现一致；版本声明同步更新 |

**参考：**
- 《数值算法正确性与精度保障评估指南（1.8版）》— `docs/zh/数值算法正确性与精度保障评估指南.md`
- 《数值算法正确性与精度保障评估验证案例集（1.1版）》— `docs/zh/数值算法正确性与精度保障评估验证案例集.md`
- MMS Testing Skill — `.opencode/skills/mms-testing/SKILL.md`
- 模板元编程与编译时依赖膨胀评估技能 — `src/arch_quality/skills/template-metaprogramming.md`

> **三方一致性说明**（自 2026-07-14）：本指南、skill 和工具的评分算法已经过全面校对。后续修改任一方时，需同步更新其他两方。可通过 `scripts/consistency_check.py` 自动验证。
