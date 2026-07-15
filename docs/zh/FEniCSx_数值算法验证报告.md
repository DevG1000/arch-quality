# FEniCSx（dolfinx）数值算法精度与稳定性验证报告

> 对照《数值算法正确性与精度保障评估验证案例集（1.1版）》执行验证

**验证日期**：2026-07-14  
**被测系统**：FEniCSx（dolfinx — 下一代 FEniCS 有限元求解环境）  
**源码版本**：`git master`（`--depth 1`）  
**源码路径**：`D:\opensource\dolfinx`  
**评估工具**：`arch_metrics_numerical_accuracy`（指南 1.7 / Skill 1.5）

---

## 一、项目概况

FEniCSx 是经典 FEniCS 项目的下一代版本，主要使用 C++ 编写，提供统一的高阶有限元求解环境，以 UFL 形式编译器和 DOLFINx 运行时库为核心。

| 项目 | 数据 |
|:-----|:------|
| 源码规模 | 504 个索引文件 |
| 数值相关文件 | 195 个（含 `.h`, `.cpp`, `.c`）|
| 语言构成 | C++ 为主 |
| 类型 | FEM 求解框架（形式编译 + 运行时） |

---

## 二、验证总览

| 项目 | 结果 |
|:-----|:------|
| 综合评分 | **46.33 / 100** |
| 数值密集型判定 | 是（195 个数值文件）|
| 触发 NVR 规则 | **6 条**（NVR-001、NVR-003、NVR-005、NVR-007、NVR-008、NVR-012）|
| 不触发规则 | 6 条 |

---

## 三、评分明细

| 维度 | 权重 | 得分 | 评级 |
|:-----|:----:|:----:|:-----|
| 数值稳定性保障 | 25% | **70.0** | 良好 |
| 舍入误差与敏感度控制 | 20% | **55** | 需改进 |
| 验证完备性 | 20% | **0.0** | 缺失 |
| 误差估计与控制 | 15% | **30** | 不足 |
| 数值回归测试覆盖 | 10% | **100.0** | 优秀 |
| 数值债务密度 | 10% | **33.33** | 中债务 |
| **综合评分** | **100%** | **46.33** | **需改进** |

---

## 四、各维度详细分析

### 4.1 数值稳定性保障（70 分）

| 检测项 | 值 | 说明 |
|:-------|:---|:------|
| total_solver_files | 27 | 求解器相关文件 |
| explicit_scheme_files | 3 | 含显式时间推进格式 |
| cfl_ratio | **11.1%** | 显式格式占比不高 |
| has_cfl_control | False | **未检测到 CFL 控制** |
| has_stability_measures | True | 有稳定化措施 |

评分路径：`has_stability_measures AND cfl_ratio < 0.3 → 70 分`。

### 4.2 舍入误差与敏感度控制（55 分）

| 检测项 | 值 | 说明 |
|:-------|:---|:------|
| cancellation_sites | 6 | 变量相减模式 |
| has_kahan_summation | **True** | Kahan 求和补偿 |
| has_dynamic_tool | **False** | 未检测到动态精度分析工具 |

评分路径：
```
base = 100
cancellation = 6 > 5 → 扣 20 → 80
has_kahan               → 不扣（已补偿）
no dynamic tool         → 额外扣 25 → 55
score = 55
```

### 4.3 验证完备性（0 分）

| 检测项 | 值 |
|:-------|:---|
| mms_file_count | **0** |
| mms_directory_count | **0** |
| has_accuracy_order | True（但非 MMS 上下文）|

FEniCSx 未发现 MMS 相关文件或目录，**MMS 验证完全缺失**。

### 4.4 误差估计与控制（30 分）

| 检测项 | 值 |
|:-------|:---|
| mesh_convergence_count | **0**（修复前误报 66 处，原因为 `richardson` 匹配开发者姓名、`element.size` 匹配注释）|
| dir_refine_count | **0**（修复前误报 3 处，原因为 `refinement` 目录名含子串 `fine`）|
| has_residual_control | True |
| has_reasonable_tolerance | **False** |

评分路径：
```
mesh_convergence = False → +0 → 0
has_residual_control     → +30 → 30
no reasonable tolerance  → +0 → 30
score = 30
```

**注意**：修复前误报为 70 分。`MESH_CONVERGENCE_PATTERN` 中 `richardson` 改为 `richardson_extrap`（避免匹开发者姓名 Chris Richardson）、`MESH_REFINE_PATTERN` 增加 `\b` 词边界（避免 `refinement` 中子串 `fine`）后，误报清零。

### 4.5 数值回归测试覆盖（100 分）

| 检测项 | 值 |
|:-------|:---|
| test_file_count | **40** |
| test_ratio | **20.5%** |
| has_assertions | True |
| N_critical | 3 |
| N_tested | 7 |

评分路径：`N_tested >= N_critical → 100 分`。

### 4.6 数值债务密度（33.33 分）

| 检测项 | 值 |
|:-------|:---|
| debt_ratio | **33.3%** |
| low_score_dimensions | 2（MMS 维度 0 分 + 误差估计 30 分 < 50）|

两个维度低于 50 分，债务比 33.3% 超过 30% 警戒线，触发 NVR-012。

---

## 五、NVR 违规详情

| 规则 | output_level | severity | 数量 | 说明 |
|:-----|:------------:|:--------:|:----:|:------|
| **NVR-001** | **ERROR** | HIGH | 3 | 3 个显式格式文件，未配置 CFL 控制 |
| **NVR-003** | **ERROR** | HIGH | 6 | 6 处相消模式，无动态工具 |
| **NVR-005** | **ERROR** | HIGH | 1 | MMS 验证完全缺失 |
| **NVR-007** | **WARNING** | MEDIUM | 1 | 无网格收敛性研究（离散误差未控）|
| **NVR-008** | **WARNING** | MEDIUM | 1 | 未检测到合理的迭代容差（tolerance < 1e-4）|
| **NVR-012** | **INFO** | LOW | 1 | 数值债务密度 33.3%，超过 30% 警戒线 |

---

## 六、未触发的规则

| 规则 | 未触发原因 |
|:-----|:-----------|
| NVR-002 条件数超限 | 预处理器已使用 |
| NVR-004 累积误差失控 | Kahan 求和已实现 |
| NVR-006 观察阶偏差 | NVR-005 触发→NVR-006 自动跳过（无 MMS 则无可用的观察阶）|
| NVR-010 回归测试缺失 | N_tested=7 >= N_critical=3 |
| NVR-011 回归断言缺失 | 测试中有断言 |

---

## 七、与已验证项目的对比

| 项目 | 类型 | 综合评分 | NVR 违规 | 最强维度 | 最弱维度 |
|:-----|:------|:--------:|:--------:|:---------|:---------|
| **MOOSE** | 多物理场 FEM | **96.0** | 1 | 5 维满分 | 舍入误差 80 |
| **deal.II** | FEM 库 | **96.0** | 1 | 5 维满分 | 舍入误差 80 |
| PETSc | 数值算法库 | 92.0 | 1 | MMS 144 | 回归测试 60 |
| Elmer | FEM 多物理场 | 91.0 | 1 | 验证/误差/回归 全100 | 舍入误差 55 |
| SU2 | CFD 求解器 | 85.67 | 1 | 稳定性/验证/误差 100 | 回归测试 30 |
| OpenFOAM | CFD 求解器 | 80.67 | 2 | 稳定性/验证/误差 100 | 回归测试 30 |
| CalculiX | FEM 求解器 | 76.67 | 1 | 稳定性 100 | MMS 0 |
| **FEniCSx** | FEM 框架 | **46.33** | **6** | 回归测试 100 | MMS 0、误差估计 30 |

FEniCSx 综合评分 **46.33**，在所有已验证项目中排名垫底。主要短板为 MMS 验证缺失（0 分）、舍入误差控制不足（55 分）和误差估计与控制（30 分）。

### 改进建议

| 建议 | 优先级 | 预期提分 |
|:-----|:------:|:--------:|
| 引入 MMS 测试体系（如 MOOSE `python/mms/` 的符号化工作流）| **P0** | 0 → 100（验证维度）|
| 配置 CFL 稳定性控制参数 | **P1** | 70 → 80~100（稳定性维度）|
| 补充网格收敛性研究框架 | **P1** | 30 → 70（误差估计维度）|
| 引入 Verrou/CADNA/Valgrind 动态精度分析工具 | P2 | 55 → 80（舍入误差维度）|
| 补充合理的迭代容差设置（tolerance < 1e-4）| P2 | 30 → 60（误差估计维度）|
