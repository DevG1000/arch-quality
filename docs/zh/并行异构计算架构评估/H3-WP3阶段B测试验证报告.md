# H3 WP-3 阶段 B 测试与验证报告

> **版本**：1.2（补拓扑与亲和性 advisory）
> **日期**：2026-11-05
> **范围**：WP-3 阶段 B（W1–W4）+ B3 / B3.5 / B3.7 + Harness + CI 门禁
> **结论**：**全部通过**（单元 20 / 组合 28 / 回归 5 / CV 8/9 / 门禁 PASS）

---

## 0. 摘要

| 验证项 | 结果 |
|:--|:--|
| 单元测试 `test_hpc_architecture.py` | **20 passed** |
| 变异测试 `test_hpc_mutation.py` | **1 test / 6 变异子例** |
| 集成/E2E `test_hpc_integration.py` | **3 passed** |
| 交叉验证逻辑 `test_cross_validate_hpc.py` | **4 passed** |
| 上述组合 | **28 passed**（4.74s）|
| 回归基线（B3，5 项目）| **5 passed**（约 5 分钟）|
| 开源验证（B3.5，A 类）| 4 样本，无假阳性；MFEM HPC-006 为真阳性 |
| 交叉验证（B3.7，9 折 LOOCV）| **8/9 PASS**（门槛 7/9）|
| Agent Harness | case-7/8/9 **PASS** |
| CI 门禁 `ci_gate_hpc.bat` | **GATE PASS**（5 步）|
| 注册表校验 `validate_meta_model.py` | **PASS** |
| LLM 语义精判（可选层）| **9 tests passed**；opencode 实跑 HPC-005 → confirm/high |
| 拓扑与亲和性 advisory | **不计分**；3 单测 + 1 集成；OpenFOAM multi_level=present、binding=absent |
| 三方一致性 `consistency_check --engine hpc` | **PASS** |

---

## 1. 环境与样本

| 项 | 值 |
|:--|:--|
| OS / Python | Windows 10 / Python 3.14.3 |
| CPU | 2 physical / 4 logical |
| 样本 | OpenFOAM-v2512、deal.II、MFEM、SU2、合成项目 |
| 引擎 | `src/arch_quality/arch_metrics_hpc.py` |
| 规则 | HPC-001~012 |
| 注册表 | v1.4，8 引擎 / 11 维 / 96 规则 |

---

## 2. 单元测试（20 passed）

文件：`tests/test_hpc_architecture.py`

| 覆盖 | 内容 |
|:--|:--|
| 权重 | skill 权重和 = 100% |
| 启用检测 | MPI / OpenMP / CUDA / Kokkos 后端 / 非 HPC |
| 适用性 | MPI 子维、GPU 子维、纯 Kokkos、非 HPC |
| 豁免 | `@hpc_benchmark_ok` / `@hpc_deferred` / `@hpc_gpu_only`、非法豁免、30% 反滥用 |
| 输出结构 | 4 维、`applicability_set`、`score_scope`、`gate_status` |
| 12 规则正/负例 | 表驱动 12 组 |
| HPC-010 线程级别 | 条件 MULTIPLE、字面 MULTIPLE、FUNNELED、Query、parallel-for、master 保护、parallel-for 假阳性回归 |

---

## 3. 变异测试（6 变异子例）

文件：`tests/mutation/test_hpc_mutation.py`

| 用例 | 规则 | 基线 → 注入缺陷 |
|:--|:--|:--|
| 守卫移除 | HPC-002 | 有 `#ifdef USE_CUDA` → 移除后触发 |
| launch 字面量 | HPC-003 | `num_teams(T)` → `num_teams(1024)` |
| Wait 移除 | HPC-005 | 成对 Isend/Wait → 移除 Wait |
| master 移除 | HPC-010 | `omp master` 包裹 MPI → 移除后触发 |
| reduction 移除 | HPC-011 | `reduction(+:s)` → 移除后触发 |
| 嵌套 omp | HPC-012 | 单并行域 → 嵌套后触发 |

---

## 4. 集成/E2E（3 passed）

文件：`tests/test_hpc_integration.py`

| 用例 | 验证 |
|:--|:--|
| 报告合并 + 归一化 | `ComprehensiveReport` 含 `dimensions.hpc`、`hpc_applicability_set`、`hpc_waiver_audit`；归一化权重 Σ=1；HPC 违规合并 |
| 封顶展示 | 注入 `confirmed_max_severity=HIGH`、score=90 → Markdown 出现“受封顶/需改进”，数值仍 90.0 |
| 非 HPC | 不渲染 HPC 维度；`gate=PASS` |

---

## 5. 回归基线（B3，5 passed）

文件：`tests/regression/test_hpc_regression.py`  
快照：`tests/regression/snapshots/hpc_*.json`

| 基线 | overall | gate | 违规 |
|:--|--:|:--:|:--|
| OpenFOAM-v2512 | 100 | PASS | 无 |
| deal.II | 100 | PASS | 无 |
| MFEM | 86.5 | PASS | HPC-006（真阳性）、HPC-007 INFO |
| SU2 | 100 | PASS | 无 |
| non_hpc_project | None | PASS | 无（负样本）|

- 带 `ARCH_REGRESSION_UPDATE=1` 时先过程序化校验（分数区间/维度键/计数/确定性）；
- 不带 UPDATE 比对 **5 passed**；
- 确定性双跑一致。

---

## 6. 开源项目验证（B3.5）

| 样本 | overall | 结论 |
|:--|--:|:--|
| OpenFOAM | 100 | 无假阳性 |
| deal.II | 100 | 无假阳性 |
| SU2 | 100 | 无假阳性 |
| MFEM | 86.5 | HPC-006 真阳性（`hypre.cpp` 循环内 `MPI_Allgather`）|

- 非 HPC 负样本正确返回 `is_hpc=False`；
- 12 规则另有合成正/负例（单元测试）。

---

## 7. 交叉验证（B3.7，8/9 PASS）

脚本：`scripts/cross_validate_hpc.py`  
语料：`tests/regression/snapshots/hpc_cv/`（5 健康 + 4 不健康）

| 样本 | 标签 | overall |
|:--|:--:|--:|
| healthy_openfoam | healthy | 100 |
| healthy_dealii | healthy | 100 |
| healthy_mfem | healthy | 86.5 |
| healthy_su2 | healthy | 100 |
| healthy_good_project | healthy | 100 |
| unhealthy_bad_project | unhealthy | 58.5 |
| unhealthy_halo | unhealthy | 67 |
| unhealthy_load | unhealthy | 62 |
| unhealthy_nested | unhealthy | 75 |

- 判据：留出样本 overall 是否落在其余 8 个 `[min,max]`；
- 结果：**8/9**（唯一离群 `unhealthy_bad_project 58.5 < 62`）；
- 门槛 7/9 → **PASS**；
- 报告：`docs/zh/并行异构计算架构评估/hpc_cross_validation_report.md` / `.json`。

---

## 8. Agent Harness

| 用例 | 结果 | 说明 |
|:--|:--:|:--|
| case-7-hpc-good | **PASS** | 1 次通过、0 重试；工具调用正确 |
| case-8-hpc-flawed | **PASS** | overall 58.5、WARN、命中 HPC-002/005/009/010/011 |
| case-9-hpc-non | **PASS** | 正确判定 `is_hpc=false` |

---

## 9. CI 门禁（GATE PASS）

`scripts/ci_gate_hpc.bat`：

| 步骤 | 结果 |
|:--|:--|
| [1/5] 单元测试 | PASS |
| [2/5] 三方一致性 | PASS |
| [3/5] 回归基线 | PASS（5/5）|
| [4/5] 交叉验证（B3.7）| PASS（8/9）|
| [5/5] Agent Harness | 可选（`RUN_HARNESS=1`）|

---

## 10. 注册表与一致性

| 检查 | 结果 |
|:--|:--|
| `validate_meta_model.py` | 6 项 PASS（8 引擎 / 11 维 / 96 规则）|
| `consistency_check.py --engine hpc` | PASS（规则 ID / 版本 / 维度 / 案例集）|
| 覆盖矩阵 | **72/72（KPI1 100%）** |

---

## 11. HPC-010 专项（OpenFOAM）

| 项 | 结果 |
|:--|:--|
| OpenFOAM 真实 HPC-010 违规 | **0** |
| 线程级别 | `UNKNOWN`（`needsThread ? MULTIPLE : SINGLE`）|
| 修复 | 取消“整项目跳过”；按实际/条件线程级别逐作用域判断；覆盖 `parallel for` |
| 新增测试 | 6 组（条件 MULTIPLE、字面 MULTIPLE、FUNNELED、Query、parallel-for、master 保护）+ 1 假阳性回归 |
| 报告 | `HPC-010-OpenFOAM检查与规则修复.md` |

---


## 12. 已知限制与未验证项

| 项 | 说明 |
|:--|:--|
| B3.7 合成不健康样本 | 4 个不健康样本含合成项目，可能高估泛化；建议后续用真实 held-out 项目复核 |
| HPC-010 级别 | 仍为**首期 WARNING**；升 ERROR 需 ≥10 工业样本 + MUST/TAU |
| GPU/异构 | OpenFOAM 当前无 GPU 信号；GPU/异构节点未实测 |
| `runtime-kernel` CI | 仅静态校验（YAML/job/脚本/`bash -n`）；未实际 GitHub Actions 运行 |
| 全量套件 | 全量 `pytest tests/` 含慢回归，未整体重跑；本报告为 HPC 目标子集 |
| 快照路径 | 回归基线使用本地 `D:\OPENSOURCE\...` 路径；跨机需固定 ref/样本 |

---

## 13. 结论

- WP-3 阶段 B 的**单元 / 变异 / 集成 / 回归 / B3.5 / B3.7 / Harness / CI** 全部通过；
- HPC 维度达到 **8/9 LOOCV**、**72/72 规则覆盖**、**5 基线回归**；
- HPC-010 检测器缺陷已修复并补回归；
- 唯一保留：HPC-010 升级、真实 GPU/异构样本、`runtime-kernel` 实跑。

---

## 14. LLM 语义精判（可选层，§7.7）

- **脚本**：`scripts/llm_refine_hpc.py`；后端 `openai` / `opencode` / `mock` / `auto`。
- **约束**：温度 0、版本固定、缓存、证据锚定；**不改变评分/门禁/confirmed**；不自动 BLOCK。
- **测试**：`tests/test_llm_refine_hpc.py` **9 passed**（解析、证据校验、缓存、max-items、无文件、snippet、mock）。
- **实跑**：`--backend opencode` 对 `bad_project_hpc` 的 HPC-005 →
  `confirm / high`，证据 `src/halo.cpp:5`；`overall=58.5`、`gate=WARN`、confirmed 不变。
- **文档**：`LLM语义精判使用说明.md`。

---

---

## 15. 拓扑与亲和性 advisory（不计分）

- **背景**：12 条 HPC 规则未覆盖 Node → CPU/socket → core → GPU 的多级计算结构；按方案 A 以 **advisory** 输出，不改变评分/门禁。
- **引擎输出**：`topology_advisory`（`scored=false`），检查：
  - `multi_level_decomposition`（`multiLevel`/`multiLevelCoeffs`）
  - `weighted_partition`（`weightField`/`processorWeights`/`loadDistribution`）
  - `cpu_binding`（`--cpu-bind`/`taskset`/`numactl`）
  - `gpu_binding`（`CUDA_VISIBLE_DEVICES`/`--gpus-per-task`/`--gpu-bind`）
  - `numa_affinity`、`gpu_backend`
- **信号来源**：`decomposeParDict`、`.slurm/.sh/.bat/.ps1/.yaml/.yml`、Makefile/CMake。
- **报告**：`arch_report_generator` 新增“拓扑与亲和性建议（advisory）”一节。
- **测试**：3 单测 + 1 集成；OpenFOAM 结果 `multi_level=present`（annotated dict）、`binding=absent`；`overall=100`、`gate=PASS` 不变。
- **限制**：仅提示可见配置，不判实际拓扑正确性；最终以启动器/TAU 为准。

---

## 附录 A：主要产物

| 类别 | 文件 |
|:--|:--|
| 引擎 | `src/arch_quality/arch_metrics_hpc.py` |
| 权重源 | `src/arch_quality/skills/hpc-architecture.md` |
| opencode skill | `.opencode/skills/hpc-gpu-architecture/SKILL.md` |
| 单元 | `tests/test_hpc_architecture.py` |
| 变异 | `tests/mutation/test_hpc_mutation.py` |
| 集成 | `tests/test_hpc_integration.py` |
| 交叉验证逻辑 | `tests/test_cross_validate_hpc.py` |
| 回归 | `tests/regression/test_hpc_regression.py` + `snapshots/hpc_*.json` |
| CV 语料 | `tests/regression/snapshots/hpc_cv/hpc_cv_*.json` |
| CV 脚本 | `scripts/cross_validate_hpc.py` |
| CV 报告 | `hpc_cross_validation_report.md` / `.json` |
| CI 门禁 | `scripts/ci_gate_hpc.bat` |
| 专项报告 | `H3-WP3-W4回归基线说明.md`、`H3-WP3-W4校准结论.md`、`HPC-010-OpenFOAM检查与规则修复.md`、`H3-WP3-P3-SKILL审查报告.md` |
| LLM 语义精判 | `scripts/llm_refine_hpc.py`、`tests/test_llm_refine_hpc.py`、`LLM语义精判使用说明.md` |

---

## 附录 B：复现命令

```powershell
# 单元 + 变异 + 集成 + CV 逻辑
python -m pytest tests/test_hpc_architecture.py tests/mutation/test_hpc_mutation.py tests/test_hpc_integration.py tests/test_cross_validate_hpc.py -q

# 回归（5 基线）
python -m pytest tests/regression/test_hpc_regression.py -q

# B3.7 交叉验证
python scripts/cross_validate_hpc.py

# 注册表 / 一致性
python scripts/validate_meta_model.py
python scripts/consistency_check.py --engine hpc

# CI 门禁（含以上步骤）
python scripts/ci_gate_hpc.bat
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|:--|:--|:--|
| 1.0 | 2026-11-05 | 首版：汇总 WP-3 阶段 B 单元/变异/集成/回归/B3.5/B3.7/Harness/CI 结果 |
