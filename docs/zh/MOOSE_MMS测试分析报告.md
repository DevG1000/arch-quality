# MOOSE MMS（制造解法）测试体系深度分析

> 基于 MOOSE 源码（`git master`）的 MMS 测试基础设施、用例分布与收敛阶验证结果分析

**分析日期**：2026-07-14  
**源码路径**：`D:\opensource\MOOSE`  
**分析范围**：`python/mms/` 核心包 + 各模块 MMS 测试用例

---

## 一、MMS 测试基础设施架构

MOOSE 拥有业界领先的 MMS 测试基础设施，核心为 `python/mms/` 包，基于 **SymPy** 符号计算引擎构建。

### 1.1 核心组件

| 组件 | 文件 | 行数 | 职责 |
|:-----|:------|:---:|:------|
| **`evaluate()`** | `python/mms/evaluate.py` | 184 | 符号化 PDE 求值：输入 PDE 表达式 + 制造解 → 输出解析源项 |
| **`fparser`** | `python/mms/fparser.py` | 238 | 将 SymPy 表达式编译为 MOOSE `ParsedFunction` 格式 |
| **`run_spatial()`** | `python/mms/runner.py` | 147 | 自动执行多套网格的空间收敛研究 |
| **`run_temporal()`** | `python/mms/runner.py` | 同上 | 自动执行多套时间步的时间收敛研究 |
| **`ConvergencePlot`** | `python/mms/ConvergencePlot.py` | 142 | 对数坐标系拟合，计算观察阶 p_obs |

### 1.2 MMS 工作流

```
Step 1: 选解
  选择光滑函数 u*(x, y, z, t)
  例: u* = t*sin(πx)*sin(5πy)

Step 2: 推导源项（符号计算）
  f = mms.evaluate("rho*cp*diff(T,t) - div(k*grad(T)) - S", "t*sin(pi*x)*sin(5*pi*y)", ...)
  → mms.print_hit(f, "mms_force")   // 自动生成 ParsedFunction 输入块

Step 3: 数值求解
  在 h, h/2, h/4, h/8, h/16 五套网格上求解
  → 收集 L2 误差

Step 4: 收敛阶计算
  p_obs = log(L2_i / L2_{i+1}) / log(h_i / h_{i+1})

Step 5: 自动判定
  assert p_obs >= p_theory - tolerance
```

### 1.3 与 MMS Testing Skill 的对比

| 对比项 | MOOSE `python/mms/` | 本项目 MMS Testing Skill |
|:-------|:-------------------|:------------------------|
| 符号引擎 | SymPy | SymPy |
| 源项推导 | `mms.evaluate()` 自动推导 | `derive_source()` 自动推导 |
| 收敛阶计算 | `ConvergencePlot._fit()`（线性拟合） | `calc_observed_order()`（逐阶 EOC） |
| 断言标准 | `p_obs >= p_theory - 0.05` | `|p_obs - p_theory| <= 0.1` |
| 代码生成 | 生成 `ParsedFunction` 输入块 | 生成完整求解器输入文件 |
| 坐标系统 | 直角 + 柱坐标 | 直角坐标 |
| MPI 支持 | 内置 `mpi=N` 参数 | 无 |

---

## 二、MMS 用例分布

### 2.1 按模块统计

| 模块 | 文件数 | 测试类型 | 物理模型 |
|:------|:-----:|:---------|:---------|
| **test（FV 核心）** | 26 | 空间收敛 | 扩散、对流-扩散、有限体积格式 |
| **level_set** | 17 | 时空收敛 | 水平集对流方程 |
| **phase_field** | 14 | 空间收敛 | Allen-Cahn、Cahn-Hilliard |
| **navier_stokes** | 9 | 空间收敛 | 不可压 NS、对流-扩散 |
| **electromagnetics** | 8 | 空间收敛 | 标量复 Helmholtz 方程 |
| **tutorials** | 8 | 时空收敛 | 教程：热传导 MMS |
| **solid_mechanics** | 4 | 空间收敛 | 显式动力学 MMS |
| **thermal_hydraulics** | 4 | 空间收敛 | 单相流 1D MMS |
| **heat_transfer** | 2 | 解析解比照 | 3 种坐标系的稳态热传导 |
| **总的 MMS 文件** | **92** | — | 10 个物理模块 |

### 2.2 按收敛验证类型

| 类型 | 用例数 | 典型应用 |
|:-----|:------:|:---------|
| **空间收敛**（`run_spatial`） | ~35 | FV 扩散、NS、电磁、相场 |
| **时间收敛**（`run_temporal`） | ~3 | 教程热传导、水平集 |
| **解析解比照** | ~5 | 热传导 code_verification |
| **限制器收敛验证** | ~12 | upwind/vanLeer/min_mod/QUICK/SOU |

---

## 三、典型 MMS 测试解析

### 3.1 有限体积扩散（`test/tests/fvkernels/mms/diffusion.i`）

**制造解**：`u = 3x² + 2x + 1`

**PDE**：`-∇·(∇u) = f`

**解析源项**：`f = -6`（对 u 求二次导数）

**预期收敛阶**：二阶（FVDiffusion 使用线性逼近）

```python
df1 = mms.run_spatial("diffusion.i", 4)  
# 4 层细化: h=0.5, 0.25, 0.125, 0.0625
# → quadfit 后 3 个点拟合 p_obs
```

### 3.2 有限体积对流-扩散（`test/tests/fvkernels/mms/advection-diffusion.i`）

**制造解**：`u = 3x² + 2x + 1`

**PDE**：`-ν∇²u + a·∇u = f`

**解析源项**：`f = -1.1×6 + 1.1×(6x+2) = -6.6 + 6.6x + 2.2 = 6.6x - 4.4`

**预期收敛阶**：
- `advected_interp_method='average'` → 二阶
- `advected_interp_method='upwind'` → 一阶

### 3.3 教程热传导 MMS（`tutorials/tutorial03_verification/step04_mms/`）

**完整 PDE**（带太阳辐射源项）：

```
ρ·cp·∂T/∂t - ∇·(k·∇T) - S·sin(0.5πx)·e^{κy}·sin(πt/(3600·hours)) = 0
```

**空间制造解**：`T = t·sin(πx)·sin(5πy)`

**时间制造解**：`T = x·y·e^{-t/32400}`

**收敛阶验证**：
- 一阶单元（线性）→ p_obs ≈ 2.0
- 二阶单元（二次）→ p_obs ≈ 3.0
- BDF1 时间格式 → p_obs ≈ 1.0
- BDF2 时间格式 → p_obs ≈ 2.0

### 3.4 水平集 MMS（`modules/level_set/1d_level_set_mms/`）

**制造解**：`φ = a·e^{1/(10t)}·sin(2πx/b) + 1`

**PDE**：`∂φ/∂t + v·∂φ/∂x = f`

**源项**（手工推导或自动生成）：

```
f = -a·e^{1/(10t)}·sin(2πx/b) / (10t²) + 2π·a·e^{1/(10t)}·cos(2πx/b) / b
```

**验证方式**：Jupyter Notebook（`LevelsetMMS.ipynb`）+ Python 收敛脚本

### 3.5 电磁学 MMS（`modules/electromagnetics/`）

使用自定义 C++ 类 `MMSTestFunc`（`test/include/functions/MMSTestFunc.h`）实现解析解和源项，验证复 Helmholtz 方程的高阶收敛性。

---

## 四、收敛阶自动验证体系

### 4.1 断言方法

MOOSE 使用 `unittest.TestCase` + `ConvergencePlot` 实现自动化收敛阶断言：

```python
class TestOutflow(unittest.TestCase):
    def test(self):
        df1 = mms.run_spatial("advection-outflow.i", 7, y_pp=["L2u", "L2v"])
        fig = mms.ConvergencePlot(...)
        fig.plot(df1, label=["L2u", "L2v"], ...)
        for label, value in fig.label_to_slope.items():
            if label == "L2u":
                self.assertTrue(value > 1.0 - 0.05)  # p_obs >= 0.95
            else:
                self.assertTrue(value > 2.0 - 0.05)  # p_obs >= 1.95
```

### 4.2 收敛阶标准

| 格式类型 | 预期阶 | 容差 | 验证方法 |
|:---------|:------:|:----:|:---------|
| FV - 中心差分（扩散） | 2.0 | ±0.05 | `num_fitted_points=3` |
| FV - 迎风（对流） | 1.0 | ±0.05 | 同上 |
| FV - vanLeer 限制器 | 2.0 | ±0.05 | 同上 |
| FV - min_mod 限制器 | 2.0 | ±0.05 | 同上 |
| FV - QUICK 限制器 | 2.0 | ±0.05 | `num_fitted_points=3` |
| FV - KT vanLeer | 2.5 | ±0.05 | 同上 |
| FE - 一阶单元 | 2.0 | ±0.05 | 3 点拟合 |
| FE - 二阶单元 | 3.0 | ±0.05 | 3 点拟合 |
| 时间 - BDF1（Euler） | 1.0 | ±0.05 | 时间步细化 |
| 时间 - BDF2 | 2.0 | ±0.05 | 时间步细化 |

### 4.3 拟合算法

```python
# ConvergencePlot._fit()
coefficients = np.polyfit(np.log10(x), np.log10(y), 1)
# 返回 [slope, intercept]
# 默认仅使用最后 num_fitted_points 个点拟合（避开预渐近区）
```

---

## 五、MOOSE MMS 的优势与特点

### 5.1 核心优势

| 特点 | 说明 |
|:-----|:------|
| **符号化工作流** | 用户只需写 PDE 和制造解，`mms.evaluate()` 自动推导源项，零手工推导错误 |
| **自动代码生成** | `print_hit()` 输出可直接粘贴到 MOOSE 输入文件的 ParsedFunction 块 |
| **全自动化收敛研究** | `run_spatial(N)` 自动执行 N 层网格细化并收集数据 |
| **内置断言** | 收敛阶低于阈值时自动测试失败 |
| **多物理场覆盖** | 10 个物理模块各自有 MMS 验证 |
| **限制器验证** | 对手写限制器（vanLeer、min_mod、QUICK 等）逐个验证收敛阶 |

### 5.2 与 arch-quality MMS Testing Skill 的差异

| 差异 | MOOSE | MMS Testing Skill |
|:-----|:------|:------------------|
| 集成度 | MMS 测试作为单元测试在 CI 中自动运行 | 独立的验证脚本 |
| 收敛判定 | `p_obs >= p_theory - 0.05`（单边下限） | `|p_obs - p_theory| <= 0.1`（双边） |
| 网格细化 | 自动 adaptive refine（Mesh/uniform_refine） | 手动指定多套网格 |
| 断言粒度 | 逐限制器、逐格式验证 | 仅验证整体收敛 |
| 输出 | 收敛图 + 测试 PASS/FAIL | 结构化 JSON 报告 |

---

## 六、改进建议

| 建议 | 优先级 | 说明 |
|:-----|:------:|:------|
| 为 `mms_slope` 后处理器补充完整的断言回归 | P2 | 当前仅 FV MMS 有自动断言，其他模块缺少自动化 |
| 统一各模块的收敛阶容差标准 | P2 | 有的用 ±0.05，有的用 ±0.1，不统一 |
| 增加时间收敛测试覆盖 | P3 | 当前仅 3 个时间收敛测试 |
| 增加 MMS 测试结果的结构化输出 | P3 | 便于与其他工具互操作 |

---

## 七、结论

MOOSE 的 MMS 测试体系是当前开源 FEM 框架中最完善的之一。其核心优势在于：

1. **符号化推导** — 消除手工推导源项的错误
2. **代码生成** — 源项自动格式化为 MOOSE 输入文件
3. **自动化收敛研究** — 一行代码执行完整收敛分析
4. **多物理场覆盖** — 10 个模块、92 个 MMS 文件、覆盖扩散/对流/NS/相场/电磁/水平集

在 arch-quality 的 NVR-005（MMS 验证缺失）和 NVR-006（观察阶偏差）评估中，MOOSE 均得满分。

参考资源：
- `python/mms/evaluate.py` — `mms.evaluate()` 函数
- `python/mms/runner.py` — `run_spatial()` / `run_temporal()`
- `python/mms/ConvergencePlot.py` — 收敛阶计算 `_fit()`
- `tutorials/tutorial03_verification/step04_mms/` — 完整 MMS 教程
- `test/tests/fvkernels/mms/advective-outflow/test.py` — FV 限制器收敛断言
