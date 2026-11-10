# H3 WP-3 W4 回归基线说明（HPC）

> 版本：0.1 ｜ 日期：2026-10-21 ｜ 归属：WP-3 阶段 B W4
> 测试：`tests/regression/test_hpc_regression.py`
> 快照：`tests/regression/snapshots/hpc_*.json`

## 一、基线清单（5 个）

| 基线 | 样本 | overall | gate | 违规 | 说明 |
|:--|:--|--:|:--:|:--|:--|
| `openfoam_v2512` | OpenFOAM-v2512 | **100** | PASS | 无 | 纯 MPI + Pstream 流抽象（HPC-005 边界）|
| `dealii` | deal.II | **100** | PASS | 无 | MPI + p4est 加权分区（HPC-008 正样本）+ Kokkos |
| `mfem` | MFEM | **86.5** | PASS | HPC-006（真阳性）、HPC-007 INFO | `hypre.cpp` 在 `numBlocks` 循环内 `MPI_Allgather`，源码注释自述扩展性受限 |
| `su2` | SU2 | **100** | PASS | 无 | MPI + 线程（FUNNELED/MULTIPLE）|
| `non_hpc_project` | 合成非 HPC | **None** | PASS | 无 | 负样本，保护"不激活"路径 |

## 二、程序化取值校验（写快照前必过）

`validate_snapshot()` 检查：

1. **is_hpc 与预期一致**；
2. **分数区间**：`0 ≤ overall ≤ 100`，且满足样本下限（OpenFOAM/deal.II/SU2 ≥95，MFEM ≥80）；
3. **维度键集合**：恰为 `backend_consistency/mpi_halo/load_topology/hybrid_parallel`；
4. **计数/类型**：`count` 为正整数、规则 ID ∈ HPC-001~012、severity/output_level 合法、candidate/confirmed 为 bool、同规则不重复；
5. **自洽**：`applicability_set ⊆ 维度键`、`score_scope ∈ {subset,none}`、`gate ∈ {PASS,WARN,BLOCK}`；非 HPC 项目 overall 必须为 None；
6. **语义锚点**：`must_include/must_not`（如 MFEM 必须命中 HPC-006、SU2 不得命中 HPC-010）。

另加**确定性**：同一输入连续两次 `_stable()` 结果必须完全相等。

## 三、更新策略（禁止盲刷）

```powershell
# 仅在"已确认是预期改进"时使用；测试内部仍会先校验
$env:ARCH_REGRESSION_UPDATE = "1"
python -m pytest tests/regression/test_hpc_regression.py -q
```

`UPDATE=1` 不是"无条件覆盖"：测试会先跑 `validate_snapshot()`，**任一失败即拒绝写入**，避免把误报/漏报祝福进基线。

## 四、运行

```powershell
python -m pytest tests/regression/test_hpc_regression.py -q
```

耗时约 6–8 分钟（含确定性双跑与两个大样本扫描）。

## 五、当前结论

- 4 个健康正样本全部 **PASS**；
- MFEM 的 HPC-006 为**真阳性**（非误报），作为"候选规则可检出真实问题"的锚点；
- 非 HPC 负样本正确返回 `is_hpc=False`；
- 规则覆盖矩阵：**HPC 12/12 覆盖**；整体 71/72（`MLR-004` 为既有缺口，与本维度无关）。
