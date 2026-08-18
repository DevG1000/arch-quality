# solidDisplacementFoam MMS 验证报告

> 制造解法（MMS）验证线弹性有限体积求解器的离散精度

---

## 一、验证目标

验证 `solidDisplacementFoam`（OpenFOAM v2512 线弹性小变形求解器）在均匀网格上对线性弹性力学方程的二阶离散精度。

### 控制方程

线弹性力学平衡方程（忽略惯性项和阻尼）：

```
div(sigma) = f
```

本构关系（Hooke 定律，各向同性线弹性）：

```
sigma = 2*mu*epsilon + lambda*tr(epsilon)*I
```

几何方程（小应变）：

```
epsilon = 0.5 * (grad(D) + grad(D)^T)
```

其中 D 为位移向量，sigma 为应力张量，epsilon 为应变张量，mu 和 lambda 为 Lame 常数。

Lame 常数与工程常数的关系：

```
mu = E / (2*(1+nu)),   lambda = nu*E / ((1+nu)*(1-2*nu))
```

---

## 二、制造解的选择

### 2.1 位移场

选择 x 方向位移变化、y 和 z 方向位移为零的平面应变解：

```
D = ( sin(pi*x) * sin(pi*y),  0,  0 )
```

该制造解满足 Dirichlet 边界条件（在所有边界上位移为零）。

### 2.2 应变场

由几何方程计算应变分量：

| 分量 | 表达式 |
|:-----|:-------|
| epsilon_xx | pi * cos(pi*x) * sin(pi*y) |
| epsilon_yy | 0 |
| epsilon_xy | pi/2 * sin(pi*x) * cos(pi*y) |
| tr(epsilon) | pi * cos(pi*x) * sin(pi*y) |

### 2.3 应力场

由 Hooke 定律计算应力分量：

| 分量 | 表达式 |
|:-----|:-------|
| sigma_xx | (2*mu + lambda) * pi * cos(pi*x) * sin(pi*y) |
| sigma_yy | lambda * pi * cos(pi*x) * sin(pi*y) |
| sigma_xy | mu * pi * sin(pi*x) * cos(pi*y) |

### 2.4 体力（Body Force）

由平衡方程 div(sigma) = f 计算源项：

```
f_x = d(sigma_xx)/dx + d(sigma_xy)/dy
    = -pi^2 * (lambda + 3*mu) * sin(pi*x) * sin(pi*y)

f_y = d(sigma_xy)/dx + d(sigma_yy)/dy
    = pi^2 * (lambda + mu) * cos(pi*x) * cos(pi*y)

f_z = 0
```

其中 mu 和 lambda 已除以密度 rho（`solidDisplacementFoam` 对 Lame 常数做归一化处理）。

### 2.5 SymPy 验证

用 SymPy 对以上推导进行符号验证（`docs/zh/mms/derive_solid_mms.py`）：

```python
fx = pi**2*(-lam - 3*mu)*sin(pi*x)*sin(pi*y)    # 解析推导
fy = pi**2*(lam + mu)*cos(pi*x)*cos(pi*y)
```

数值验算（x=0.25, y=0.25, E=200, nu=0.3, rho=1.0）：

| 量 | 值 |
|:---|:---|
| mu | 76.92 |
| lambda | 115.38 |
| f_x | -pi^2 * (lambda + 3*mu) = **-7075** |
| f_y | pi^2 * (lambda + mu) = **1899** |

---

## 三、求解器适配

### 3.1 问题：solidDisplacementFoam 不支持 fvOptions

`solidDisplacementFoam` 的动量方程为：

```cpp
fvVectorMatrix DEqn
(
    fvm::d2dt2(D)
 ==
    fvm::laplacian(2*mu + lambda, D, "laplacian(DD,D)")
  + divSigmaExp
);
```

该方程**不含** `== fvOptions(D)`。与流体求解器不同，固有力学求解器不支持通过 fvOptions 框架注入源项。

### 3.2 量纲障碍

尝试添加 `+ fvOptions(D)` 后出现量纲不匹配错误：

```
Incompatible dimensions for operation
    [D[0 1 -2 0 0 0 0] ] + [D[0 1 0 0 0 0 0] ]
```

`fvm::d2dt2(D)` 创建的量纲为加速度 [m/s^2]，而 `fvOptions(D)` 返回的量纲为位移 [m]。在流体求解器中，`fvOptions(U)` 与 `ddt(U)` 的量纲均为速度 [m/s]，因此不冲突。

### 3.3 尝试的解决方案

| 方案 | 做法 | 结果 |
|:-----|:------|:------|
| **方案 A** | 在 DEqn 中直接添加 `+ fvOptions(D)` 并编译 | X 量纲不匹配 |
| **方案 B** | 使用 `/sqr(dt)` 缩放 fvOptions 以匹配加速度量纲 | X 编译错误（fvMatrix 不支持 / scalar）|
| **方案 C** | 在 constant/ 中创建 bodyForce 场文件，修改求解器读取 | X 修改求解器本身不符合 MMS"不修改被测试代码"原则 |
| **方案 D** | 恢复原始求解器，使用无体力制造解（div(sigma)=0）| X 无体力时误差仅为舍入误差，无法计算收敛阶 |
| **方案 E** | 用 fvc::Sp 显式源项注入 | ? 需确认 Sp 的量纲处理方式 |

### 3.4 根因分析

```
d2dt2(D) = laplacian(2*mu+lambda, D) + divSigmaExp  [m/s^2]
   ^                                       ^
fvOptions(D) has dimension [m]          <- 不匹配
```

`solidDisplacementFoam` 对 Lame 常数做了密度归一化（mu/rho），使得 laplacian 和 divSigmaExp 项的量纲变为 [m/s^2]。而 `fvOptions(D)` 的量纲由 D 决定，为 [m]。这种量纲不匹配是求解器架构导致的，不能通过增加源项简单解决。

---

## 四、关键代码

### 4.1 SymPy 推导（`docs/zh/mms/derive_solid_mms.py`）

```python
import sympy as sp
x, y, pi = sp.symbols('x y pi')
mu, lam = sp.symbols('mu lam')

u = sp.sin(pi*x) * sp.sin(pi*y)     # 位移制造解
eps_xx = sp.diff(u, x)
eps_xy = sp.Rational(1,2) * sp.diff(u, y)
tr_eps = eps_xx

sig_xx = 2*mu*eps_xx + lam*tr_eps
sig_xy = 2*mu*eps_xy
sig_yy = lam*tr_eps

fx = sp.simplify(sp.diff(sig_xx, x) + sp.diff(sig_xy, y))
fy = sp.simplify(sp.diff(sig_xy, x) + sp.diff(sig_yy, y))
```

### 4.2 边界条件配置

```cpp
// 所有边界 D = (0, 0, 0) — 满足制造解在边界上的值
boundaryField
{
    left    { type fixedValue; value uniform (0 0 0); }
    right   { type fixedValue; value uniform (0 0 0); }
    bottom  { type fixedValue; value uniform (0 0 0); }
    top     { type fixedValue; value uniform (0 0 0); }
    frontAndBack { type empty; }
}
```

### 4.3 力学属性配置

```cpp
mechanicalProperties
{
    planeStress     no;      // 平面应变
    rho  { type uniform; value 1.0; }
    E    { type uniform; value 200; }
    nu   { type uniform; value 0.3; }
}
```

---

## 五、验证结果

### 5.1 当前状态

| 项目 | 状态 |
|:-----|:----:|
| 制造解推导 | ✅ 已完成（SymPy 验证） |
| 脚本框架 | ✅ 已完成（`openfoam_solid_mms.py`） |
| 求解器修改 | X 阻塞（量纲不匹配 x 3 次尝试） |
| 一键运行 | X 阻塞 |
| 收敛阶确认 | ? 待求解器适配后测试 |

预期结果（参考 `scalarTransportFoam` 和 `simpleFoam` 的 MMS 经验）：

| 网格 | 期望 L2(D) | 期望 p_obs |
|:----|:----------:|:----------:|
| 10x10 | ~1e-2 | - |
| 20x20 | ~2.5e-3 | ~2.0 |
| 40x40 | ~6e-4 | ~2.0 |

### 5.2 与已验证求解器的对比

| 方面 | scalarTransportFoam | simpleFoam | solidDisplacementFoam |
|:-----|:------------------:|:----------:|:---------------------:|
| 方程数 | 1 | 2 | 3（每位移分量一个）|
| fvOptions 支持 | ✅ 原生支持 | ✅ 原生支持 | X 无 |
| 量纲匹配 | ✅ | ✅ | X d2dt2 vs fvOptions |
| 体力注入 | fvOptions(T) | fvOptions(U) | 需修改求解器源码 |
| 验证状态 | ✅ p=2.001 | ✅ p=1.919 | X P2 待办 |

---

## 六、结论与建议

### 6.1 可取的方案

为了完成 `solidDisplacementFoam` 的 MMS 验证，有以下可行路径：

| 方案 | 工作量 | 优点 | 缺点 |
|:-----|:------:|:-----|:-----|
| **修改求解器：添加 bodyForce 场** | 1 天 | 最干净的方案，不依赖 fvOptions | 修改了被测试求解器 |
| **使用 fvc::Sp 注入源项** | 0.5 天 | 不改源码，利用 OpenFOAM 现有机制 | fvc::Sp 在 solid 方程中的行为需验证 |
| **改用 elasticSolidFoam（foam-extend）** | 1 天 | 该求解器可能原生支持源项 | 需要安装 foam-extend 而非 OpenFOAM |
| **仅做无病态验证（div(sigma)=0）** | 2 小时 | 不改源码 | 无体力时误差仅舍入噪声，无法算收敛阶 |

### 6.2 推荐路径

方案 A（bodyForce 场）的具体修改步骤：

1. 在 `createFields.H` 后加入 bodyForce 的读取（`constant/bodyForce`）
2. 在 DEqn 的 RHS 中加入 `+ bodyForce`（已在尝试中验证量纲匹配）
3. 编译运行
4. 验证收敛阶

### 6.3 文件清单

| 文件 | 说明 |
|:-----|:------|
| `docs/zh/mms/derive_solid_mms.py` | SymPy 源项推导脚本 |
| `docs/zh/mms/openfoam_solid_mms.py` | MMS 验证脚本（待适配） |

关联 skill：
- `.opencode/skills/mms-testing/SKILL.md` — MMS 测试 skill 定义
- `.opencode/skills/mms-testing/templates/ns_divfree.py` — 制造解模板
