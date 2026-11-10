# H3 WP-3 阶段 B 实现方案 · 专家校对报告

> **评审对象**：`H3-WP3阶段B实现方案.md`（v0.1）
> **评审视角**：工业软件并行/异构架构专家 + 引擎实现评审
> **依据**：指南 v0.8、案例集 v0.3、GCS 引擎接口（`arch_metrics_geometry_consistency.py`）、deal.II/Kokkos 源码事实
> **结论**：**有条件通过**（P1×4）→ **v0.2 定向确认：P1×4 + P2×5 均闭环，转为通过**

---

## 一、总体评价

方案对齐 GCS 引擎结构与指南 4 子维/12 规则/适用性/豁免体系，输出结构与集成点清单较完整。主要缺口：**封顶落点未定**、**Kokkos GPU 检测信号不可靠**、**skill 前置格式未定义**、**两条规则的可实现静态信号缺失**。

---

## 二、问题清单

### P1（须修/说明）

**P1-1 等级封顶"作用对象 + 集成点"未定义**
- **问题**：方案 §七称"等级封顶在报告层"，但未说明封顶的是**HPC 维度分等级**还是**项目总分等级**（指南 §四原文为"总分等级封顶"）；也未指明由 `arch_report.py` 还是 `arch_report_generator.py` 实施、如何与 8 引擎合并后的 overall 交互。
- **证据**：指南 v0.8 §四"任一已确认 ERROR/HIGH → 等级封顶'需改进'"措辞为"总分"；而 HPC 只是 8 引擎之一并入总分（WP-1 归一化），若按"总分"封顶，则 HPC 单引擎 ERROR 会压制全项目总分等级，需显式裁决。
- **修订**：① 明确封顶对象（建议：**HPC 维度子分等级**封顶 + 报告层并列展示"项目总分（受 HPC 封顶提示）"）；② 指明实施文件（`arch_report_generator.py` 的 HPC 段/总分段）；③ 与 WP-1 归一化后的总分关系写清。

**P1-2 Kokkos GPU 信号不可靠，会"漏判/误判"**
- **问题**：§3.1 以 `KOKKOS_ENABLE_CUDA/HIP/SYCL` 为 GPU 信号，但这些是**构建期宏**（多在生成的 `config.h`/CMake 缓存），**用户源码里通常不出现**；仅扫源码会**漏判**真实 Kokkos-GPU 项目。同时 `DEAL_II_WITH_KOKKOS` **恒为真**（deal.II 强制），若纳入 GPU 信号会把默认 CPU 构建的 deal.II **误判 GPU**。
- **证据**：`cmake/configure/configure_30_kokkos.cmake:17 realON`；`include/deal.II/base/config.h.in:102 #cmakedefine DEAL_II_WITH_KOKKOS`；`examples/step-64` 用 `Kokkos::parallel_for` 但不含 `KOKKOS_ENABLE_CUDA` 字面量。
- **修订**：GPU 检测应**同时扫构建文件**（`CMakeLists.txt`/`*.cmake`/`config.h(.in)`）中的 `KOKKOS_ENABLE_CUDA|HIP|SYCL`；Kokkos 源码信号用 `Kokkos::Cuda|HIP|SYCL`/`cudaSpace|hipSpace`；**`DEAL_II_WITH_KOKKOS` 单独不得作为 GPU 证据**。并在报告中标注 GPU 子维"capability vs 实际后端"。

**P1-3 `skills/hpc-architecture.md` 为前置依赖，但格式未定义**
- **问题**：§二依赖 `load_weights_from_skill(SKILL_PATH)` 解析 4 维权重，§八却仅写"**新建**"，未定义必须含 `## 权重分配` 标题与 `| 子维度 | 30% |` 表格（`arch_core.load_weights_from_skill` 的正则依赖该标题；缺失时回退全文匹配，易误抓其他百分号表格）。
- **修订**：明确 skill 文件结构（8-9 章 + `## 权重分配`：backend 30 / mpi_halo 30 / load_topology 20 / hybrid 20，和=100），并作为 W1 首个交付物。

**P1-4 HPC-001 与 HPC-008 的"静态信号"未具体化，不可实现/高误报**
- **问题**：HPC-001 要求"同名/对应算子 CPU 与 GPU 两套实现"——如何识别"对应算子"未定义；HPC-008 "非均匀迹象（AMR/多材料/非均匀场）"未给可检符号。
- **修订**：HPC-001 定义信号（如 `#ifdef __CUDACC__`/`USE_CUDA` 同函数双分支、`_cpu`/`_gpu` 命名对、同文件两套 `forall` 循环）；HPC-008 定义信号（`refine`/`coarsen`/`p4est_refine`、`multiRegion`/`multiMaterial` 关键词、`adapt`/`AMR` 标识），无法静态判定的记 candidate。

### P2（精化）

- **P2-1 测试/基准目录排除与 `@hpc_benchmark_ok` 关系**：§3.2"测试/示例（可选）"与 §六 benchmark 豁免重叠；应明确"测试/基准默认排除 或 计入并靠注解豁免"，避免口径冲突。
- **P2-2 违规 count 口径**：按"出现次数"还是"文件数"未定义（GCS 用次数）；建议统一为出现次数并注明。
- **P2-3 registry 权重值**：`dim.hpc_gpu` 候选权重未给具体值（应为 0.15，与 Q4 一致）与 `scope`。
- **P2-4 CI 门禁脚本**：§八未列 `scripts/ci_gate_hpc.bat`（GCS/ACL 均有）。
- **P2-5 双重归一化说明**：HPC 子维归一化（subset）与 WP-1 顶层激活归一化叠加，需在报告注明"`score_scope=subset`，不与全引擎 HPC 分混比"。

---

## 三、可保留的正面项

- 输出结构（overall/dimensions/applicability_set/hpc_violations/gate_status/waiver_audit）设计与指南一致。
- 适用性门控 + 归一化、三注解 + 30% 反滥用、candidate/confirmed 区分，均正确。
- 集成点清单覆盖 registry/schema/validator/profile/report/generator/consistency/benchmark，较完整。
- 风险表已识别 Kokkos/HPC-005/HPC-010/HPC-008/性能/确定性。

---

## 四、修订要求 / 门槛

1. **P1-1~P1-4 必清**（封顶落点、Kokkos 检测、skill 格式、两条规则信号）。
2. P2 逐条处理或说明。
3. 修订后做一次定向确认，方可实施；实施后按 §十 用案例集校准。

---

*本报告依据方案 v0.1 原文 + GCS 引擎接口 + deal.II/Kokkos 源码事实核验。*

---

## 五、定向确认（方案 v0.2）

| 编号 | 修订落点（v0.2） | 状态 |
|:--|:--|:--:|
| P1-1 | §七：封顶对象=**HPC 维度子分等级**（非项目总分），实现于 `arch_report_generator.py` HPC 段，不回写总分数值 | 闭环 |
| P1-2 | §3.1：GPU 证据含**构建文件** `KOKKOS_ENABLE_CUDA/HIP/SYCL`；`DEAL_II_WITH_KOKKOS` 单独不计 | 闭环 |
| P1-3 | §2.2：新增 skill 格式（`## 权重分配` + 4 行 30/30/20/20，和=100） | 闭环 |
| P1-4 | §五：HPC-001 信号（`#ifdef __CUDACC__`/`USE_CUDA` 双分支、`_cpu`/`_gpu`、双 `forall`）；HPC-008 信号（`refine`/`coarsen`/`p4est_refine`、`multiRegion`/`multiMaterial`、`AMR`/`adapt`）| 闭环 |
| P2-1 | §3.2：测试/基准**计入**规则扫描，靠 `@hpc_benchmark_ok` 豁免 | 闭环 |
| P2-2 | §五：count=**出现次数** | 闭环 |
| P2-3 | §八：`dim.hpc_gpu` weight **0.15**、scope project | 闭环 |
| P2-4 | §八：新增 `scripts/ci_gate_hpc.bat` | 闭环 |
| P2-5 | §4.1：新增双重归一化说明（`score_scope=subset`）| 闭环 |

**结论**：方案 v0.2 满足实施条件，可进入阶段 B 编码。

---

*定向确认依据方案 v0.2 原文逐条断言核验（13/13 PASS）。*
