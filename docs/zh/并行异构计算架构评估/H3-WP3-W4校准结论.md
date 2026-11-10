# H3 WP-3 W4 校准结论（HPC）

> 版本：0.1 ｜ 日期：2026-10-21 ｜ 归属：WP-3 阶段 B W4
> 依据：5 个回归基线 + A 类样本 + 合成正负例

## 一、A 类实测（健康正样本）

| 样本 | overall | gate | 触发 | 判定 |
|:--|--:|:--:|:--|:--|
| OpenFOAM | 100 | PASS | 无 | 无假阳性 |
| deal.II | 100 | PASS | 无 | 无假阳性 |
| SU2 | 100 | PASS | 无 | 无假阳性 |
| MFEM | 86.5 | PASS | HPC-006（真阳性）、HPC-007 INFO | 真阳性，非误报 |

**结论**：4 个健康样本无规则误报；MFEM 的 HPC-006 命中 `linalg/hypre.cpp`（`numBlocks` 循环内 `MPI_Allgather`，源码注释自述扩展性受限），属**真实性能风险**。

## 二、HPC-010 误报率评估（首期 WARNING → ERROR？）

| 样本 | HPC-010 | 说明 |
|:--|:--:|:--|
| OpenFOAM | 未触发 | 无 `omp parallel` 内 MPI |
| deal.II | 未触发 | 无 `omp parallel` 作用域 |
| SU2 | 未触发 | 无 `omp parallel` 内 MPI |
| MFEM | 未触发 | — |
| 合成负例 | **触发** | `omp parallel` 内 `MPI_Allreduce` + FUNNELED |
| 合成正例 | 未触发 | `omp master` 包裹 |

- 实测 **0/4 假阳性**，负例可检出；
- 但样本量仅 4 个、无 TAU/MUST 运行时复核，**不足以支撑升 ERROR**；
- **裁决：HPC-010 保持首期 WARNING**（severity 仍 HIGH，封顶规则不变），待更多工业样本 + 运行时确认后再评估升级。

## 三、规则赋分校准

- 指南赋分（backend 30/30/10/30；mpi_halo 55/35/10；load 95/5；hybrid 40/35/25）**保持不变**；
- 依据：A 类无假阳性、MFEM 真阳性扣分合理（HPC-006 35 分 → mpi_halo 65）；
- INFO 规则（HPC-003/007/009）维持 10/10/5，未发现需要调整的证据。

## 四、限制

1. 样本以开源 CFD/FEM 为主，商业软件（ANSYS/COMSOL）未实测；
2. 未接入 TAU/MUST 实测，HPC-006/008 的"实际失衡"仍属风险信号；
3. 规则阈值/赋分为**首期校准值**，后续新增样本需复校。

## 五、后续

- **已完成**：`case-7-hpc-good` Harness **PASS**（1 次通过、0 重试）；
- 新增工业样本后，重跑 `test_hpc_regression.py` 并评估 HPC-010 升级。

## 六、HPC-010 升级复评（P3，2026-10-21）

- **现状**：4 个 A 类样本 **0 假阳性**；合成负例（`bad_project_hpc`）可稳定检出。
- **升级门槛（建议）**：
  1. ≥ 10 个工业样本；
  2. MUST/TAU 运行时确认“确实非线程安全”；
  3. 误报率 < 5%。
- **结论**：**维持首期 WARNING**（severity 仍 HIGH，封顶语义不变），暂不升 ERROR。

- **检测器修复（2026-11-05）**：取消 `MPI_THREAD_MULTIPLE` 整项目跳过，改为按实际/条件线程级别逐作用域判断，并覆盖 `omp parallel for`；OpenFOAM-v2512 复检无 HPC-010；规则仍维持首期 WARNING。

- **B3.7 交叉验证（2026-11-05）**：9 样本（5 健康 + 4 不健康）9 折 LOOCV **8/9 PASS**（门槛 7/9）；离群为 unhealthy_bad_project（58.5）。

- **LLM 语义精判（§7.7，2026-11-05）**：可选层 `scripts/llm_refine_hpc.py` 已实现；温度0/缓存/证据锚定；**不改确定性评分/门禁/confirmed**；opencode 实跑 HPC-005 → confirm/high（src/halo.cpp:5）。

- **拓扑与亲和性 advisory（方案 A，2026-11-05）**：新增 `topology_advisory`（多级分解/加权分区/CPU/GPU 绑定/NUMA/GPU 后端），**不计分**；OpenFOAM 100/PASS 不变。
