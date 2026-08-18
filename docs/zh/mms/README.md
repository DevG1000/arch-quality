# OpenFOAM MMS 验证测试方案

## 概述

本方案为 OpenFOAM `laplacianFoam`（稳态扩散求解器）设计了一套完整的制造解（MMS）验证测试，用于系统性验证其空间离散的二阶精度。

## 制造解

```
u(x,y) = sin(πx) · sin(πy)
```

| 属性 | 值 |
|:-----|:----|
| PDE | `-∇·(D∇u) = S` |
| 源项 S | `2π² · D · sin(πx) · sin(πy)` |
| 扩散系数 D | 1.0 |
| 理论精度阶 | **2**（二阶中心差分，均匀网格） |
| 边界条件 | u = 0（四边 Dirichlet） |

## 网格层级

| 层级 | 网格 | h | 预期 L2 误差 |
|:----:|:----:|:-:|:-----------:|
| 粗 | 20×20 | 0.050 | ~1.2e-2 |
| 中 | 40×40 | 0.025 | ~3.0e-3 |
| 细 | 80×80 | 0.0125 | ~7.5e-4 |

## 运行方式

```bash
# 前提：安装 OpenFOAM-v2512 并配置环境变量
cd docs/zh/mms
python openfoam_laplacian_mms.py
```

## 预期输出

```
MMS Verification Result
============================================================
  Manufactured solution: u = sin(pi*x) * sin(pi*y)
  PDE: -laplacian(D*u) = S
  Expected order: 2 (2nd order central difference)

  coarse -> medium: p_obs = 2.003 (expected 2.0) [PASS]
  medium -> fine:   p_obs = 1.998 (expected 2.0) [PASS]

  Average observed order: 2.001
  Overall result: [PASS]

  => The code is verified at 2nd order accuracy.
```

## 文件清单

| 文件 | 说明 |
|:-----|:------|
| `openfoam_laplacian_mms.py` | MMS 验证脚本（创建 case + 运行 + 误差计算） |
| `README.md` | 本说明文件 |

## 验证案例库对照

对应《数值算法正确性与精度保障评估验证案例集（1.1版）》中的 ABAQUS MMS 验证正例（NVR-005, NVR-006 阴性）。当 OpenFOAM 通过此 MMS 测试后，可视为 NVR-005 和 NVR-006 的阴性验证。
