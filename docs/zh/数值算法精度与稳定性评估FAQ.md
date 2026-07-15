# 数值算法精度与稳定性评估 FAQ

> 针对 `arch-quality` 项目中数值算法精度与稳定性保障评估的常见问题解答。
> 对应评估指南（1.5版）、验证案例集（1.1版）和 skill 定义。

---

## 一、MMS 验证基础

### Q1: MMS 测试是什么？工作原理是什么？

MMS（Method of Manufactured Solutions，制造解法）是一种系统验证 PDE 离散精度的标准方法。它将验证问题转化为自洽的数学闭环：

```
Step 1  选解：选一个光滑函数 u*，满足边界条件
Step 2  推导源项：将 u* 代入 PDE，解析推导出 S = L(u*)
Step 3  数值求解：求解器计算 L(u_num) = S
Step 4  多套网格：在 h, h/2, h/4 等多套网格上求解
Step 5  判定：计算 L2 误差和收敛阶 p_obs，判定 |p_obs - p_theory| ≤ 0.1
```

详细文档：`docs/zh/mms/MMS 科普.md`

### Q2: L2 误差怎么算的？

```python
L2 = sqrt( mean( (T_num - T_exact)² ) )
    = sqrt( Σ(T_num - T_exact)² / N )
```

其中 T_exact 取制造解在**单元中心**的值，N 为总单元数。

### Q3: 收敛阶 p_obs 怎么算的？

```
p = log(E₂/E₁) / log(h₂/h₁)

对三套网格：
  p₁ = log(E₂/E₁) / log(h₂/h₁)    粗 → 中
  p₂ = log(E₃/E₂) / log(h₃/h₂)    中 → 细
  平均 = (p₁ + p₂) / 2
```

### Q4: scalarTransportFoam 和 scalarCodedSource 分别是什么？

| 组件 | 类型 | 说明 |
|:-----|:-----|:------|
| `scalarTransportFoam` | 求解器 | 解标量输运方程，设 U=0 退化为纯扩散 |
| `scalarCodedSource` | 源项插件 | 运行时编译 C++ 代码生成空间变化源项 |

---

## 二、已完成的 MMS 验证

### Q5: 哪些求解器通过了 MMS 验证？

| 求解器 | PDE | 制造解 | p_obs | 网格 | 状态 |
|:-------|:-----|:-------|:-----:|:----:|:----:|
| `scalarTransportFoam` | `-∇·(D∇T)=S` | sin(πx)·sin(πy) | **2.001** | 20/40/80 | ✅ |
| `simpleFoam` | 不可压 NS | 无散度速度场 | **1.919** | 10/20/40 | ✅ |

### Q6: simpleFoam 的 MMS 速度平均收敛阶 1.919 是如何计算的？

```
网格 10×10: L₂(U) = 4.44e-03
网格 20×20: L₂(U) = 1.21e-03
网格 40×40: L₂(U) = 3.11e-04

p₁ = log(1.21e-3 / 4.44e-3) / log(0.05 / 0.1) = 1.874
p₂ = log(3.11e-4 / 1.21e-3) / log(0.025 / 0.05) = 1.963
平均 = (1.874 + 1.963) / 2 = 1.919
```

### Q7: 为什么 simpleFoam 速度收敛阶是 1.919 而不是完美的 2.0？

SIMPLE 算法在 collocated grid 上使用 Rhie-Chow 插值，速度收敛阶天然在 1.8-2.0 之间。这不是实现 Bug，而是算法的固有特征。

### Q8: 压力的收敛阶为什么是 1.127？

压力通过连续性方程间接求解（压力泊松方程），不直接受源项驱动。SIMPLE 算法中压力的观测收敛阶通常在 1.0-1.5，这不反映代码实现缺陷。

### Q9: 为什么不做 rhoPimpleFoam 的 MMS 验证？

已尝试三次独立方案，均因同一根因而失败：

```
动量源 → U 变化 → K(½|U|²) 变化 → fvc::ddt(rho,K) 显式项滞后
  → 内能/焓失衡 → T < T_ref → Negative temperature → 崩溃
```

能量方程的显式 K 项（`fvc::ddt(rho,K) + fvc::div(phi,K)`）无法与隐式动量源项平衡。这是可压缩 NS 方程 MMS 验证的已知难度。当前标记为 **P3（研究级）**。

### Q10: 为什么不做 solidDisplacementFoam 的 MMS 验证？

`solidDisplacementFoam` 不支持 `fvOptions`。尝试添加时出现量纲不匹配：

```
d2dt2(D) [m/s²] + laplacian(2μ+λ, D) + divSigmaExp + fvOptions(D) [m]
  → Incompatible dimensions
```

已尝试 5 种方案（直接添加、/sqr(dt)、bodyForce 场、fvc::Sp、无源项），均因求解器架构限制而阻塞。标记为 **P2**。详见 `docs/zh/mms/solidDisplacementFoam_MMS验证报告.md`。

---

## 三、fvOptions 与源项注入

### Q11: `scalarCodedSource` / `vectorCodedSource` 的符号约定是什么？

在所有已验证的求解器中，源项符号一致：

```cpp
// 正确的符号（所有通过验证的求解器均使用）
eqn.source()[cellI] -= S_value * V[cellI];
```

`eqn.source()` 是方程矩阵 A·x = b 中的右端项 b，`-=` 意味着 S 被加到右端项正方向。

### Q12: `codeAddSup` 和 `codeAddSupRho` 有什么区别？

| 钩子 | 调用方式 | 适用场景 |
|:-----|:---------|:---------|
| `codeAddSup` | `fvOptions(U)` | 不可压（simpleFoam）|
| `codeAddSupRho` | `fvOptions(rho, U)` | **可压缩**（rhoPimpleFoam, buoyantPimpleFoam）|

如果求解器调用 `fvOptions(rho, U)` 但只实现了 `codeAddSup`，会报 "Not implemented" 错误。

### Q13: 对于不支持 fvOptions 的求解器，如何进行 MMS 验证？

有 4 种路径：

| 路径 | 适用场景 | 局限 |
|:-----|:---------|:-----|
| **A. 修改求解器** | 源码可编译 | 修改了源项接口，但非离散格式 |
| **B. 利用现有机制** | 求解器有等效源项（如热应力 `fvc::grad(T)`）| 源项形式受限 |
| **C. 换求解器** | 存在等价的 fvOptions 求解器 | PDE 实现细节可能不同 |
| **D. 无源项** | 精度要求不高的场景 | 无法验证体载荷项 |

---

## 四、求解器配置与线性代数

### Q14: fvSchemes 中的离散格式怎么配置？

```cpp
divSchemes
{
    div(phi,U)  Gauss linearUpwind grad(U);   // 对流：二阶有界
    // div(phi,U)  Gauss linear;               // 对流：二阶中心（可能振荡）
    // div(phi,U)  Gauss upwind;               // 对流：一阶（扩散大）
}
laplacianSchemes
{
    default     Gauss linear corrected;        // 扩散：二阶 + 非正交修正
}
```

### Q15: 线性求解器和算法控制有什么区别？

```
线性求解器：解 A·x = b        → 关心"解多准"
算法控制：  外层迭代回路       → 关心"迭代多少次"
```

fvSolution 示例：

```cpp
solvers                          // ← 线性求解器
{
    U  { solver PBiCG; preconditioner DILU; tolerance 1e-10; }
    p  { solver PCG;  preconditioner GAMG;  tolerance 1e-8;  }
}
SIMPLE                           // ← 算法控制
{
    nNonOrthogonalCorrectors 0;
    residualControl { U 1e-6; p 1e-6; }
}
```

### Q16: MMS 验证中线性求解器容差为什么要设到 1e-10？

线性求解器误差必须**远小于**离散误差（网格细化误差），否则会污染收敛阶。对于二阶格式，离散误差在 h=0.1 时约为 1e-3，到 h=0.0125 时约为 2e-5。求解器容差 1e-6 足够捕捉这个量级，设到 1e-10 是保守操作。

### Q17: 什么是网格条件数？为什么超过 1e6 需要注意？

条件数 κ(A) = ||A||·||A⁻¹||，是输入误差的放大倍数：

```
如果 b 有 1e-8 的舍入误差，κ(A) = 1e6：
  解的相对误差 ≤ 1e-8 × 1e-6 = 1e-2 = 1%
```

| κ(A) | 影响 |
|:----:|:-----|
| 10 | 几乎无影响 |
| 10³ | 可接受 |
| **10⁶** | **只剩 2-3 位有效数字** |
| 10⁹ | 解完全不可信 |

### Q18: OpenFOAM 会不会计算条件数并根据条件数选择求解器？

**不会**。OpenFOAM 的策略与条件数监控完全不同：

```
传统方法（PETSc/LAPACK）：
  condest(A) → κ ≈ 10⁶ → 需要预条件 → 选择求解器

OpenFOAM 的策略：
  用户在 fvSolution 中指定 GAMG → GAMG 通过多层次网格
  隐式降低有效条件数 → 不需要知道 κ(A) 的值
```

GAMG 的多层次网格机制：

```
原始矩阵 κ ≈ 10⁶
  → Level 0: A₀ = A,        κ ≈ 10⁶
  → Level 1: A₁ = R·A₀·P,   κ ≈ 10⁴
  → Level 2: A₂ = R·A₁·P,   κ ≈ 10²
  → Level 3: A₃ = R·A₂·P,   κ ≈ 10   → 直接求解
```

---

## 五、评估维度与评分

### Q19: 6 个评估维度各自的权重和评分逻辑是什么？

| 维度 | 权重 | 核心检测 | 满分的条件 |
|:-----|:----:|:---------|:-----------|
| 数值稳定性保障 | 25% | CFL 控制 + 稳定性措施 | 有 CFL 控制 AND 有稳定性措施 |
| 舍入误差控制 | 20% | 相消模式 + Kahan + 动态工具 | 无相消模式 OR 有动态工具 |
| 验证完备性 | 20% | MMS 文件 + 收敛阶记录 | 有 MMS 文件 AND 有收敛阶记录 |
| 误差估计与控制 | 15% | 残差控制 + 网格收敛研究 | 有残差控制 AND 有网格研究 |
| 数值回归覆盖 | 10% | 测试文件 + CI + 断言 | CI 自动化 + 精度断言 |
| 数值债务密度 | 10% | 低分维度占比 | 债务比 ≤ 5% |

### Q20: 数值稳定性保障的完整评分过程是什么？

```python
cfl_ratio = explicit_scheme_files / total_solver_files

if total_solver_files == 0:           score = 100  # 无求解器
elif has_cfl_control and has_stability: score = 100  # 最优
elif has_cfl_control:                   score = 80
elif has_stability and cfl_ratio < 0.3: score = 70
elif has_stability:                     score = 50
elif cfl_ratio < 0.3:                   score = 30
else:                                    score = 10
```

其中 `cfl_ratio < 0.3` 为工程经验值（无文献支撑），可通过环境变量 `CFL_RATIO_THRESHOLD` 覆盖。

### Q21: 舍入误差与敏感度控制维度为什么 OpenFOAM 得了 55 分？

```
初始分: 100
  - 171 处相消模式 → 扣 20  → 80
  - 相消 >5 处且无动态工具 → 扣 25 → 55
  - 有 Kahan 求和 → 不扣分    → 55 最终
```

扣分原因：
- 171 处 `a - b` 模式的潜在相消性损失
- 缺少 Verrou/CADNA 等动态分析工具

### Q22: `cfl_ratio < 0.3` 的阈值依据是什么？

该阈值**没有文献依据**，是工程经验值。三位专家的评审结论：

| 专家 | 意见 |
|:-----|:------|
| 专家 A（数值算法开发） | ❌ 反对无依据值，建议改用 ASME V&V 20 映射 |
| 专家 B（CAE 测试） | ⚠️ 有条件支持，建议改为可配置参数 |
| 专家 C（架构管理） | ✅ 支持保留，补充注释即可 |

**最终决定**：保留 0.3，补充注释标注为工程经验值，并支持环境变量覆盖。

详见：`docs/zh/数值稳定性阈值评审意见书.md`

---

## 六、网格与文件结构

### Q23: OpenFOAM 网格数据存放在哪里？格式是什么？

```bash
constant/polyMesh/
├── points        # 顶点坐标（vectorField）
├── faces         # 面定义（faceList，每个面由顶点编号组成）
├── owner         # 面所属单元（labelList）
├── neighbour     # 面邻居单元（-1 = 边界）
└── boundary      # 边界映射（边界名 → 面编号范围）
```

### Q24: 前处理、求解器、后处理三个阶段在 OpenFOAM 中如何体现？

```
前处理：blockMesh → 写 constant/polyMesh/
        设置 0/U, 0/p 边界条件
        配置 system/controlDict, fvSchemes, fvSolution

求解器：simpleFoam → 读 system/ + constant/ → 写 1/U, 1/p

后处理：paraFoam 或 foamToVTK → 读 1/U, 1/p
```

---

## 七、精度监控

### Q25: 什么是 Verrou / CADNA？它们有什么用？

```
静态分析（当前评估）：
  "你这里有 171 处 a - b，可能有问题。"

动态精度监控（Verrou/CADNA）：
  "这 171 处中，有 12 处会在 0.1% 的舍入扰动下产生
  >1% 的结果差异。这 12 处需要重构。其他安全。"
```

| 工具 | 方法 | 适用阶段 |
|:-----|:------|:---------|
| Verrou | 随机舍入（CEA） | CI / 回归 |
| CADNA | 离散随机计算 | 研发阶段 |
| Valgrind | 指令级插桩 | 调试阶段 |
| Verificarlo | 蒙特卡洛舍入 | CI / 回归 |

### Q26: 没有精度监控会有什么风险？

精度退化不引发崩溃，用户无法感知，但决策数据错误：

```
求解器正常运行，残差收敛，云图看起来正确
  → 但升力系数误差达到 5%
  → 用户基于这个数据做工程决策
  → 精度退化被隐藏，无人知道
```

这是 CFD 中最危险的缺陷类型：**不崩溃、不可见、但数据错误**。

---

## 八、OpenFOAM 评估实例

### Q27: OpenFOAM v2512 的数值算法精度综合评分是多少？

**80.67 / 100**（良好）

| 维度 | 得分 | 关键数据 |
|:-----|:----:|:---------|
| 数值稳定性保障 | 100 | CFL 控制已配置，cfl_ratio=9.8% |
| 舍入误差控制 | 55 | 171 处相消，无动态工具 |
| 验证完备性 | 100 | 35 个 MMS 文件，有收敛阶记录 |
| 误差估计与控制 | 100 | 残差控制 + 网格收敛研究 |
| 回归测试覆盖 | 30 | 8.1% 测试占比，无 CI |
| 数值债务密度 | 66.7 | 1 个维度偏低 |

### Q28: NVR-002（条件数超限）在 OpenFOAM 中是否触发？

修正前：**触发（误报）**。检测到 120 个线性求解器相关文件 → ERROR。

修正后：**不触发**。检测到 GAMG/DIC/DILU 预处理器 → 条件数可控。

### Q29: 验证完备性维度为什么能得 100 分？

OpenFOAM 有 35 个 MMS 相关文件（目录包含 `*mms*`、`*manufactured*` 等关键词），检测到收敛阶记录。评分路径：有 MMS 文件 + 有收敛阶记录 → 100 分。

### Q30: 为什么 OpenFOAM 能得 100 分而我们自己的 arch-quality 项目只有 61.33 分？

主要差异在误差估计（100 vs 0）和 MMS 验证维度。

`arch-quality` 项目作为静态分析工具，没有网格收敛性研究（误差估计 = 0 分），也没有内置 MMS 验证文件（验证完备性低）。但两个项目的数值稳定性维度都得 100 分——它们都没有求解器代码，因此不扣分。

---

## 九、测试与工具

### Q31: 数值精度评估的单元测试覆盖哪些内容？

| 测试文件 | 测试数 | 覆盖内容 |
|:---------|:------:|:---------|
| `test_numerical_accuracy.py` | 17 | 实现代码：检测模式、评分函数、NVR 规则 |
| `test_numerical_accuracy_skill.py` | 61 | skill 定义：6 维度评分算法、豁免注解解析、跨规则协调、数值密集型判定 |

### Q32: 如何从命令行运行数值精度评估？

```bash
# 完整评估
python -m arch_quality.arch_metrics_numerical_accuracy <project>

# 仅 JSON 输出 + 指定 MMS 观察阶
python -m arch_quality.arch_metrics_numerical_accuracy <project> --json --mms-pobs 2.001

# 仅检测 NVR 规则
python -m arch_quality.arch_metrics_numerical_accuracy <project> --nvr-only

# 覆盖 CFL 阈值
set CFL_RATIO_THRESHOLD=0.5
python -m arch_quality.arch_metrics_numerical_accuracy <project>
```

### Q33: NVR-002 的修正逻辑是什么？

```
原逻辑（误报）：
  if 检测到线性求解器关键词 → 触发 NVR-002

修正后逻辑：
  if 检测到线性求解器 AND NOT 预处理器 AND NOT 条件数监控 → 触发
```

预处理器包括：GAMG、DIC、DILU、FDIC、smoothSolver、PCG、PBiCG 等。

---

## 十、相关文档索引

| 文档 | 路径 | 说明 |
|:-----|:------|:------|
| 评估指南（1.5版） | `docs/zh/数值算法正确性与精度保障评估指南.md` | 6 维度定义、12 条 NVR 规则 |
| 验证案例集（1.1版） | `docs/zh/数值算法正确性与精度保障评估验证案例集.md` | 22 个阴阳性案例 |
| Skill 定义 | `src/arch_quality/skills/numerical-accuracy.md` | 评分算法、豁免注解、校准方法 |
| MMS 科普 | `docs/zh/mms/MMS 科普.md` | MMS 验证方法论 |
| MMS Skill | `.opencode/skills/mms-testing/SKILL.md` | MMS 执行工作流 |
| 阈值评审 | `docs/zh/数值稳定性阈值评审意见书.md` | 三位专家对 0.3 阈值的评审 |
| 固体 MMS 报告 | `docs/zh/mms/solidDisplacementFoam_MMS验证报告.md` | 线弹性 MMS 验证障碍分析 |
| 实现代码 | `src/arch_quality/arch_metrics_numerical_accuracy.py` | 6 维度评分 + NVR 规则检测 |
| CLI 入口 | `python -m arch_quality.arch_metrics_numerical_accuracy` | 命令行评估工具 |
| 单元测试 | `tests/test_numerical_accuracy.py` | 17 个实现测试 |
| Skill 测试 | `tests/test_numerical_accuracy_skill.py` | 61 个 skill 一致性测试 |
