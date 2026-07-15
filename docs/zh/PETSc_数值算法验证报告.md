# PETSc 数值算法精度与稳定性验证报告

> 对照《数值算法正确性与精度保障评估验证案例集（1.1版）》执行验证

**验证日期**：2026-07-13  
**被测系统**：PETSc（Portable, Extensible Toolkit for Scientific Computation）  
**源码版本**：`git master`（2026-07-13 克隆，深度 1）  
**源码路径**：`/tmp/petsc_src/`  
**评估工具**：`arch_metrics_numerical_accuracy`（含 Fortran 支持改造）

---

## 一、项目概况

PETSc 是阿贡国家实验室开发的可移植可扩展科学计算工具包，提供大规模线性方程组、非线性方程组和常/偏微分方程的求解框架。它不是一个独立的求解器，而是一个**数值算法库**——提供基础构建块（KSP 线性求解器、SNES 非线性求解器、TS 时间推进器），被广泛集成到 MOOSE、deal.II、OpenFOAM（通过 PETSc4FOAM）等框架中。

| 项目 | 数据 |
|:-----|:------|
| 源码规模 | 11,386 个文件 |
| 数值相关文件 | 3,266 个（含 `.c`, `.h`, `.f90`, `.f`）|
| 语言构成 | C 为主，少量 Fortran |
| 类型 | 数值算法库（非求解器）|

---

## 二、验证总览

| 项目 | 结果 |
|:-----|:------|
| 综合评分 | **92.0 / 100** |
| 数值密集型判定 | ✅ 是（3,266 个数值文件）|
| 触发 NVR 规则 | **1 条**（NVR-003）—— output_level 为 **WARNING**（有动态工具，降级）|
| 不触发规则 | 11 条 |

---

## 三、评分明细

| 维度 | 权重 | 得分 | 评级 |
|:-----|:----:|:----:|:-----|
| 数值稳定性保障 | 25% | **100.0** | ✅ 优秀 |
| 舍入误差与敏感度控制 | 20% | **80** | ✅ 良好 |
| 验证完备性 | 20% | **100.0** | ✅ 优秀 |
| 误差估计与控制 | 15% | **100** | ✅ 优秀 |
| 数值回归测试覆盖 | 10% | **60.0** | ⚠️ 需改进 |
| 数值债务密度 | 10% | **100.0** | ✅ 低债务 |
| **综合评分** | **100%** | **92.0** | **优秀** |

---

## 四、各维度详细分析

### 4.1 数值稳定性保障（100 分）

| 检测项 | 值 | 说明 |
|:-------|:---|:------|
| total_solver_files | 1,394 | `KSPCreate`、`SNESCreate` 等求解器构造调用 |
| explicit_scheme_files | 119 | 含 `rk4`、`forwardEuler` 等显式时间推进 |
| cfl_ratio | **8.5%** | 显式格式文件占比较低 |
| has_cfl_control | ✅ True | `CFL`、`Courant`、`TSAdapt` 时间步自适应 |
| has_stability_measures | ✅ True | 数值稳定化措施（人工扩散等）|

**评分路径**：`has_cfl_control AND has_stability_measures → 100 分`。

### 4.2 舍入误差与敏感度控制（80 分）

| 检测项 | 值 | 说明 |
|:-------|:---|:------|
| cancellation_sites | **314** | 大量变量相减模式（梯度、残差、增量）|
| has_kahan_summation | ✅ **True** | 使用了 Kahan 求和补偿 |
| has_dynamic_tool | ✅ **True** | **检测到 Valgrind** 等动态分析工具 |

**评分路径**：

```
base = 100
cancellation > 0 → 扣 20 → 80
cancellation > 5 AND has_dynamic_tool → 不扣（动态工具可作为 mitigate）
has_kahan → 不扣
score = 80
```

**output_level 为 WARNING 而非 ERROR 的原因**：检测到 `Valgrind` 等动态分析工具，表明项目对浮点精度问题有系统性质量控制手段。

### 4.3 验证完备性（100 分）

| 检测项 | 值 |
|:-------|:---|
| mms_file_count | **144**（所有项目中最高）|
| has_accuracy_order | ✅ True |

PETSc 的 `src/` 下包含大量 MMS 测试用例和 `p` 阶收敛性验证（`pgold`、`ptest` 等）。评分路径：`mms ≥ 3 AND has_accuracy_order → 100 分`。

### 4.4 误差估计与控制（100 分）

| 检测项 | 值 |
|:-------|:---|
| mesh_convergence_count | **41**（网格收敛性研究）|
| dir_refine_count | **3**（细化目录模式）|
| has_residual_control | ✅ True（`KSPSetTolerances`、`SNESSetTolerances`）|
| has_reasonable_tolerance | ✅ True（`rtol=1e-8`、`atol=1e-12`）|

PETSc 的 KSP（线性求解器）和 SNES（非线性求解器）都通过参数接口显式配置残差容差：

```c
KSPSetTolerances(ksp, 1e-8, 1e-12, PETSC_DEFAULT, PETSC_DEFAULT);
SNESSetTolerances(snes, 1e-10, 1e-10, 1e-10, 100, 100);
```

### 4.5 数值回归测试覆盖（60 分）

| 检测项 | 值 |
|:-------|:---|
| test_file_count | **1,794** |
| test_ratio | **54.9%** |
| has_assertions | ✅ True（`PetscCall`、`assert`、`check`）|
| has_ci_config | ❌ **False** |

PETSc 有 1,794 个测试文件，占比 54.9%（代码库的一半是测试）。测试中使用 `PetscCall` 等断言宏检查返回值，但在 git 仓库根目录未检测到 `.github/workflows/` 等 CI 配置模板。

### 4.6 数值债务密度（100 分）

| 检测项 | 值 |
|:-------|:---|
| debt_ratio | **0.0%** |
| low_score_dimensions | 0 |

所有维度得分均不低于 50 分，无所处预警者。

---

## 五、NVR 违规详情

| 规则 | output_level | severity | 数量 | 说明 |
|:-----|:------------:|:--------:|:----:|:------|
| NVR-003 | 🟡 **WARNING** | HIGH | 314 | 314 处潜在相消性损失，但已有 Kahan 求和和动态分析工具，故降级为 WARNING |

**NVR-003 降级原因**：`has_dynamic_tool = True`（检测到 Valgrind），根据 skill 定义：

```python
ol = "ERROR" if not roundoff.get("has_dynamic_tool") else "WARNING"
```

---

## 六、未触发的规则

| 规则 | 未触发原因 |
|:-----|:-----------|
| NVR-001 稳定性溢出 | CFL 控制已配置（TS 自适应时间步）|
| NVR-002 条件数超限 | GAMG、DIC、ILU 等预处理器已使用 |
| NVR-004 累积误差失控 | Kahan 求和已实现 |
| NVR-005 MMS 缺失 | 144 个 MMS 文件 |
| NVR-006 观察阶偏差 | 有收敛阶记录 |
| NVR-007 离散误差未控 | 41 处网格收敛性研究 |
| NVR-008 迭代误差未控 | 残差控制已配置（`tol=1e-8`）|
| NVR-010 回归测试缺失 | 测试占比 54.9%，超过 10% 阈值 |
| NVR-011 回归断言缺失 | 测试中有断言（`PetscCall`）|
| NVR-012 债务密度超限 | 0.0% < 30% |

---

## 七、与已验证项目的对比

| 项目 | 类型 | 综合评分 | 最强维度 | 最弱维度 |
|:-----|:------|:--------:|:---------|:---------|
| **PETSc** | 数值算法库 | **92.0** | 验证完备性 144 MMS | 回归测试 60（无 CI）|
| OpenFOAM | CFD 求解器 | 80.67 | 稳定性/验证 100 | 回归测试 30（8.1%）|
| CalculiX | FEM 求解器 | 76.67 | 稳定性 100 | 验证完备性 0 |

PETSc 在验证完备性和数值债务维度上明显优于其他两个项目，反映其作为国家级实验室项目的质量控制标准。

## 八、验证结论

| 项目 | 结果 |
|:-----|:------|
| 案例集覆盖 | 与 OpenFOAM、CalculiX 共用同一套评估框架 |
| 预期一致 | 符合案例集 §8.1 中 PETSc 作为数值库的预期（有残差控制）|
| 实际触发规则 | 1 条（NVR-003，WARNING 级别）|
| **综合评分** | **92.0 / 100 — 优秀** |
| 验证数据存档 | `.opencode/arch-reports/petsc_validation.json` |

### 改进建议

| 建议 | 优先级 | 预期提分 |
|:-----|:------:|:--------:|
| 添加 CI 配置文件（GitHub Actions 等）| P2 | 60→80（回归测试维度）|
| 314 处相消模式中筛选高风险区域 | P3 | — |
