# HPC-010 OpenFOAM 检查与规则修复报告

> 版本：1.0 ｜ 日期：2026-11-05
> 对象：`D:\OPENSOURCE\OpenFOAM-v2512`
> 规则：HPC-010 非线程安全 MPI 调用
> 结论：**OpenFOAM 无真实违规**；原检测器存在**整项目跳过**缺陷，已修复并补测试。

---

## 一、规则定义

`omp parallel` 作用域内直接调用 `MPI_*`，且不在 `omp master/single` 内，且 `MPI_Init_thread` 级别 < `MPI_THREAD_MULTIPLE`。

---

## 二、OpenFOAM 检查结果

| 项 | 结果 |
|:--|:--|
| `is_hpc` | True |
| HPC-010 违规 | **0** |
| `omp parallel`（块形式）| **0** |
| 含 MPI 的 omp 作用域 | **0** |
| `MPI_THREAD_MULTIPLE` 出现文件 | `src/Pstream/mpi/UPstream.C` |

### 源码事实

```cpp
// UPstream.C:235-249
int required_thread_support =
(
    needsThread
  ? MPI_THREAD_MULTIPLE
  : MPI_THREAD_SINGLE
);
MPI_Init_thread(&argc, &argv, required_thread_support, &provided_thread_support);
```

- 默认（不加 `-mpi-threads`）请求 `MPI_THREAD_SINGLE`；
- 加 `-mpi-threads` 才请求 `MULTIPLE`；
- 实际以 `provided_thread_support` 为准（`:354-361`、`:375`）。

唯一 OpenMP 使用：

```cpp
// src/meshTools/PatchFunction1/MappedFile/MappedFileFilterFieldTemplates.C:103-125
#pragma omp parallel for if (nPoints > 1000)
for (label pointi = 0; pointi < nPoints; ++pointi)
{
    ... // 仅局部插值，无 MPI 调用
}
```

结论：**没有"omp 作用域内调 MPI"的真实违规**。

---

## 三、原检测器缺陷（根因）

```python
# 修复前
if any("MPI_THREAD_MULTIPLE" in c for _p, c in self._iter_cxx_production()):
    return []      # ← 整项目跳过
```

问题：
1. 任意文件出现 `MPI_THREAD_MULTIPLE`（条件请求/比较/字符串）→ 整项目跳过；
2. 不区分"请求 MULTIPLE"与"实际 provided MULTIPLE"；
3. 只覆盖块形式 `omp parallel`，**漏掉 `omp parallel for`**；
4. OpenFOAM 的 `needsThread ? MULTIPLE : SINGLE` 触发跳过 → 假阴性。

---

## 四、修复方案

`_rule_010` / 新增辅助：

- `_thread_support_level()`：
  - `MULTIPLE`：显式**无条件** `MPI_Init_thread(..., MPI_THREAD_MULTIPLE, ...)`；
  - `UNKNOWN`：条件请求（同时出现 MULTIPLE 与 SINGLE/FUNNELED/SERIALIZED）或仅 `MPI_Query_thread`；
  - `LT_MULTIPLE`：未请求 MULTIPLE（默认 SINGLE）。
- `_omp_mpi_scopes()`：同时覆盖块形式 `omp parallel { ... }` 与语句形式 `omp parallel for` 的循环体。
- `_rule_010()`：仅 `MULTIPLE` 跳过；`UNKNOWN`/`LT_MULTIPLE` 均检查作用域。
- 继续使用 `omp master/single/critical/atomic` 保护判定。

修复后：

| 场景 | 行为 |
|:--|:--|
| 无条件 `MPI_Init_thread(MULTIPLE)` | 跳过（安全）|
| 条件 `needsThread ? MULTIPLE : SINGLE` | 检查（不静默跳过）|
| `MPI_Init_thread(FUNNELED/SERIALIZED/SINGLE)` | 检查 |
| 仅 `MPI_Query_thread` | 检查（级别未知）|
| 无线程声明（默认 SINGLE）| 检查 |
| `omp parallel for` 内 MPI | 触发 |

---

## 五、测试

新增 `TestHpc010ThreadSupport`（6 组）：

| 用例 | 期望 |
|:--|:--|
| 条件 MULTIPLE + 未保护块 | 触发 |
| 字面 MULTIPLE + 未保护块 | 不触发 |
| FUNNELED + 未保护块 | 触发 |
| Query_thread only + 未保护块 | 触发 |
| `parallel for` 内 MPI | 触发 |
| `omp master` 保护 | 不触发 |

验证：

| 套件 | 结果 |
|:--|:--|
| `tests/test_hpc_architecture.py` | **19 passed** |
| HPC 单测+变异+集成 | **23 passed** |
| HPC 5 基线回归 | **5 passed**（5:50）|
| OpenFOAM 复检 | `thread level=UNKNOWN`、HPC-010 **0** |
| `bad_project_hpc` | `overall=58.5`、HPC-010 仍命中 |

---

## 六、建议

1. **OpenFOAM 代码无需为 HPC-010 修改**；使用 `-mpi-threads` 时确保 MPI 库实际提供 `MULTIPLE`，并保持 MPI 调用在 `master/single` 内。
2. 后续可进一步**精确解析 `MPI_Init_thread` 参数**与 `provided` 分支，而不只依赖 token 组合。
3. 将"条件 MULTIPLE + 未保护块"纳入变异/回归，防止回退。
