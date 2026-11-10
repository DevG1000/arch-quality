# HPC 评估方法论与知识速览

> **版本**：1.0
> **日期**：2026-10-21
> **读者**：新入职工程师、外部参考者、方法复用者
> **性质**：方法论沉淀 + HPC/GPU 入门速览
> **工程实例**：见 `docs/zh/计划/H3阶段进展与决策记录.md`（下称"工程纪要"）
> **证据口径**：标 **【已验证】** 者为本仓库实测/源码 `rg` 核验；标 **【建议】** 者为设计建议，尚未经生产验证。

---

## 0 阅读指南

| 你的目标 | 看哪节 |
|:--|:--|
| 避免回归测试"把缺陷当正确答案" | §1.1 |
| 用源码核验 AI 写的案例是否杜撰 | §1.2 |
| 给规则做正/负样本标定 | §1.3 |
| 决定某个权重取值 | §1.4 |
| 理解本项目评分语义 | §1.5 |
| 判断该不该用 LLM 替代启发式 | §1.6 / §1.7 |
| 学 HPC 基础（域分解/MPI/OpenMP/GPU）| §2 |

---

## 1 方法论沉淀

### 1.1 回归基线"祝福"教训与程序化校验

**问题**：回归基线 = 期望值；`ARCH_REGRESSION_UPDATE=1` 会用引擎当前输出覆盖基线。若引擎此刻有 bug，bug 产物就被写成"正确答案"——即**把故障"祝福（bless）"进基线**，此后测试永远通过、缺陷隐身。

**真实案例**（H2 回归修复记录）：
- 第 1 项「10 个 `tpl_*.json` 是空占位（`overall=null`）」看似最无害；若直接盲刷，会同时重写 tpl/standard 快照，从而**掩盖**第 6 项（`MLR-024` 环计数随 `PYTHONHASHSEED` 波动 9/33/20）与第 7 项（`GitHistory` 超时静默返回 ""→当作 0 提交→`avg_commit_size=0`→"无膨胀"满分，超时反而提分）。

**纪律**：重生成基线前，用**与被测引擎解耦的不变量**校验，不满足则拒绝写入：
- **分数区间**：`[0,100]`、overall 与各维自洽；
- **维度键集合**：等于期望集合（拦"读错键导致空转通过"）；
- **计数类型**：非 `null`/字符串、非负；
- 附加：**确定性**（跨 `PYTHONHASHSEED` 重跑一致）、**语义不变量**（有提交时 `avg_commit_size` 不应为 0）。

> 本仓库实践：WP-9 G4 改 ACL 后，先备份 → 重生成 → 逐项 diff 校验（区间/无 null/仅预期变化）→ 再跑测试。见工程纪要 §2.4。

### 1.2 专家校对"实证法"：用源码核验案例归属

**原则**：AI 生成的行业案例常"看起来对、实则张冠李戴"。按编制指南"证据须可核实"，**每个案例主张都要落到 `repo 路径 + 类/文件 + 检索计数`**。

**真实教训（本项目）**：

| 主张 | 源码实证 | 结论 |
|:--|:--|:--|
| SU2 有 CUDA/GPU 后端 | 全仓 `__CUDACC__/ENABLE_CUDA/cudaMemcpy/hipMalloc` **唯一命中 `externals/catch2/catch.hpp`** | ❌ **杜撰**：无真实 GPU 代码 |
| deal.II 是 "MPI×OpenMP" | `#pragma omp` 31 文件，但主并行是 **TBB/`Threads::Task`** | ⚠️ 归属不准：MPI + TBB 线程（局部 OpenMP） |
| OpenFOAM 是混合并行 | `#pragma omp` 仅 **2** 文件 | ⚠️ **≈纯 MPI** |
| MFEM 有 GPU 后端 | `MFEM_USE_CUDA/HIP` **63**、`MFEM_HOST_DEVICE` **191**、`.cu/.hip` **0** | ✅ 真实（统一单源内核）|

**方法**：写案例 → `rg -l/-n` 计数 → 填锚点表 → 复核。**无锚点不采信**。

### 1.3 正样本 vs 负样本校准原则

一条规则要有**两侧样本**才能真正校准：

| 类型 | 作用 | 例子 |
|:--|:--|:--|
| **正样本（健康）** | 校准"不应触发"（防误报）| MFEM（统一内核→不应触发双实现分歧）、OpenFOAM（成对通信→不应触发未配对）|
| **负样本（缺陷）** | 校准"应触发"（防漏报）| **C 类合成**：未配对 `Send/Recv`、硬编码 `blockDim`、双实现归约分歧、非 `THREAD_MULTIPLE` 多线程 MPI |

**易错点**：把健康样本当"缺陷样板"。例如 MFEM 用 `MFEM_HOST_DEVICE` **统一内核**（CPU/GPU 同一份源码）——它是"避免分歧"的**正样本**，不是"双实现分歧"的阳性；OpenFOAM/SU2 同理。**阴性（缺陷）样本必须单独合成。**

### 1.4 敏感性分析：为什么、怎么做

**为什么**：权重是主观先验、没有唯一"正确值"。不要试图"拟合权重"（无 ground truth），而要检验**结论对权重是否稳健**。LOOCV 测的是"泛化"，**不能用来定权**（评审意见 14）。

**怎么做（OAT 网格扫描）**：
1. 取冻结的各维客观得分（与权重无关，故改权重只需重算 overall，**零成本**）；
2. 一次只动一个维度权重，走过网格 `{0.05..0.20}`；
3. 指标：`max|Δoverall|`、**Kendall τ**（排名是否变）、**等级变化数**；
4. **稳定区间** = τ=1 且等级不变的网格点；
5. 结论：区间内取值不改变结论 → 专家在区间内定值。

**真实结果**（本项目 6 增强维）：numerical 最敏感（0.10→0.15 致 2 项等级变化）；template/anticorruption 全区间稳定 → 非关键；现行值均落稳定区间 → 维持。详见工程纪要 §2.3。

### 1.5 激活子集全局归一化（评分语义）

**公理**：任一项目**激活维度权重之和 = 1**。

```
候选集 D（10 维，registry 单一事实源）
激活集 A ⊆ D（标准 4 维恒激活 + 检测/声明激活的增强维）
归一化：w'_d = w_d / Σ_{d∈A} w_d
综合分：overall = Σ_{d∈A} score_d · w'_d
```

**对比旧模型**：旧"4 维基座 + 增强折叠"用 `base_map={1:0.85,…}` 分档 + 折进 structural，非单调、口径散落 5 处；新模型统一、单调、可扩展。

| 激活集 | Σ原始 | structural | design | doc | evolution | 增强维 |
|:--|:--:|:--:|:--:|:--:|:--:|:--|
| 标准 4 维 | 1.00 | .300 | .250 | .200 | .250 | — |
| +数值 | 1.10 | .273 | .227 | .182 | .227 | numerical .091 |
| 全 6 增强 | 1.85 | .162 | .135 | .108 | .135 | ml/tpl/sp/gcs/acl .081，nvr .054 |

> `nvr=.054` 因数值原始权重 0.10（其余增强 0.15）：`0.10/1.85`。语义变更导致总分整体 +3~+8（迁移 delta 见工程纪要 §2.2），故需"语义变更重设基线"。

### 1.6 启发式 vs LLM：能替代吗？

**结论【建议】**：**不替代，分层混合**。

| 环节 | 谁做 | 理由 |
|:--|:--|:--|
| 计数/门禁/复杂度/事实存在性 | **确定性启发式** | 必须可复现、可 diff、可门禁 |
| 语义级/跨函数/意图（候选精判）| **LLM** | 正则跨不了函数/宏，LLM 能读上下文 |
| 报告叙述/排序/建议 | **LLM** | 不碰分数 |

**LLM 精判 = 在启发式候选上做"确认/否决/降级/存疑"**（提高精度、减少误报），不是从头扫代码、不是打分。

**LLM 风险**：非确定性、幻觉（如把 SU2 说成有 GPU）、不可审计、成本/规模、模型漂移、可被"粉饰"。**约束**：证据锚定 `file:line`、无证据不采信、低置信降级 INFO、温度 0 + 固定模型/提示词版本、纳入回归。

**证明"更准"**：必须建**人工标注金标准** → 对比 纯启发式/纯 LLM/混合 的 P/R/F1（对齐 H1 KPI5 假阳性≤10%、H2 KPI4 一致率≥90%）。没有数据，不得声称更准。

### 1.7 Agent 处理"低分"的红线

**前提**：分数由确定性引擎产出；评估 agent `edit/write=deny`（改不了代码/快照）。低分是**信号**，不是**错误**。

**流程**：① 复核输入（子模块/`--build-dir`/profile/`--test-dirs`/Git 可得性）→ ② 拆解维度定位 → ③ 归因：
- **真低分** → 不调分，报告 Top 问题 + 建议 + 下钻；
- **工具误判** → 走校准（登记→对抗性验证→修引擎→带校验重设基线）；
- **语义/权重问题** → 敏感性 + 专家定案 / 决策 5 基线重设。

**红线**：不调阈值/不换权重/不跳过规则/不忽略 ERROR/不手改快照/不为"好看"对齐他项。

---

## 2 附录 · HPC/GPU 知识速览

### 2.1 域分解（Domain Decomposition）

把大计算域切成子域，每子域交给一个 MPI 进程并行求解（内存/算力/扩展三收益）。

- 流程：全域网格 → **分区** → 每子域绑定 rank → 建 **halo/ghost** 层 → 迭代交换。
- 关键：**halo 宽度 ≥ stencil 阶数**；**界面越小通信越轻**；**负载要均衡**。
- 分区算法：几何法 / 图法（**METIS/Scotch**）/ 空间填充曲线（**p4est**）。
- 分类：非重叠（子结构，halo 交换）vs 重叠（Schwarz）；区别于**功能分解**（按物理场分进程）。
- 实例：OpenFOAM `decomposePar`（`decomposeParDict` + `processor*` patch）；deal.II `p4est`/`partition_triangulation`（支持 `PartitionWeights` 加权）。
- 映射规则：HPC-005（halo 配对）、HPC-007（重叠）、HPC-008（负载）。

### 2.2 MPI（Message Passing Interface）

分布式内存并行标准：进程独立地址空间，显式消息通信。

- 概念：`rank`（编号）/`size`（总数）/`communicator`（通信子，如 `MPI_COMM_WORLD`）/`tag`/`datatype`/SPMD。
- 点对点：`Send/Recv`、`Sendrecv`（防死锁）、`Isend/Irecv`+`Wait/Test`（重叠）。
- 集合：`Bcast/Scatter/Gather/Allgather/Reduce/Allreduce/Alltoall/Barrier`。
- 陷阱：阻塞 Send 不成对→死锁；Isend 不 Wait→缓冲复用竞态；热循环集合通信→扩展性差；多线程无 `THREAD_MULTIPLE`→未定义行为。
- 线程级（自 **MPI-2.0**）：SINGLE/FUNNELED/SERIALIZED/MULTIPLE（`MPI_Init_thread`）。
- 进阶：`Comm_split`（分组）、`Cart_create`（拓扑）、CUDA-aware MPI（GPU 缓冲直传）、RMA（MPI-3）。
- 实现：OpenMPI/MPICH/Intel MPI/MVAPICH；工具 MUST/MPI-Checker、TAU/Score-P。
- 映射规则：HPC-005/006/007/010（+009 窄化 INFO）。

### 2.3 OpenMP（共享内存多线程）

`#pragma omp` 把循环/代码块分给多线程，跑单节点共享内存；常与 MPI 组混合并行。

- 概念：线程、并行域、fork-join、工作共享（for/sections/single）、**数据作用域**（shared/private/firstprivate/reduction）、同步（barrier/critical/atomic）、调度（static/dynamic/guided）。
- 常用：`parallel for`、`reduction(+:s)`、`critical`/`atomic`、`task`、`collapse`、`nowait`。
- **最大坑：数据作用域**——共享变量多线程写 → 竞态；缺 `reduction`。
- 其他坑：假共享、并行域嵌套、并行区调非线程安全函数（`rand`、非 MULTIPLE 的 MPI）、浮点归约顺序不确定。
- 混合：节点间 MPI + 节点内 OpenMP；常用 `FUNNELED`（主线程碰 MPI）最安全（SU2 默认）。
- 对比：TBB/Taskflow（deal.II 主力）、Kokkos/RAJA（性能可移植）。
- 映射规则：HPC-011（共享变量）、HPC-012（并行域嵌套）、HPC-010（线程安全 MPI）。

### 2.4 OpenMP target 异构 offload

`#pragma omp target` 把代码卸载到设备（GPU），一次编写 CPU/GPU 都能跑（性能可移植）。

- 执行：host → target region（设备）→ `teams`（grid/block）→ `distribute` → `parallel for`（线程）→ `simd`。
- 数据：`map(to/from/tofrom/alloc)`；`target data` 区让数据常驻设备（少搬运）。
- 配置：`num_teams(T) thread_limit(B)`（≈ gridDim/blockDim）。
- 守卫：`omp_get_num_devices()`、**`omp_is_initial_device()`**（判断是否真在设备上跑；否则可能静默回退主机）。
- 编译：Clang `-fopenmp-targets=nvptx64-nvidia-cuda|amdgcn-amd-amdhsa`；Intel `-fopenmp-targets=spir64`；GCC `-foffload=nvptx-none|amdgcn-amd-amdhsa`；NVHPC `-mp=gpu`。
- 运行时：`libomptarget`（Clang）/`libgomp` 插件；设备代码经厂商驱动加载。
- 映射规则：HPC-001（双实现分歧）、HPC-002（守卫/回退）、HPC-003（launch 配置）、HPC-004（数据搬运）。

### 2.5 PTX / AMDGCN / SPIR-V

三者是"源码 → 机器码"之间的中间层，层级不同：

```
源码 → 编译器IR → [虚拟ISA/便携IR] → [本机ISA]
CUDA   → NVVM    → PTX            → SASS      (NVIDIA)
HIP    → LLVM IR → AMDGCN(LLVM)   → HSACO     (AMD)
SYCL/OpenCL/OpenMP → SPIR-V       → Gen/Xe ISA (Intel 等)
```

| | PTX（NVIDIA）| AMDGCN（AMD）| SPIR-V（Khronos）|
|:--|:--|:--|:--|
| 本质 | **虚拟 ISA** | **本机 ISA** | **便携二进制 IR** |
| 最终码 | SASS | AMDGCN 机器码（HSACO）| Gen/Xe ISA 等 |
| 可移植 | 跨架构版本**向前兼容** | 按 `gfx` 架构，通常需重编 | **跨厂商** |
| 文本/二进制 | 文本 | 二进制 | 二进制 |
| 目标例 | `sm_90`/`sm_100` | `gfx90a`/`gfx942` | `spir64` |

> 对评估的意义：不同 ISA/编译路径的 FMA 收缩、归约顺序、精度不同 → **CPU/GPU（甚至跨厂商）结果有微小差异**（HPC-001）；PTX 向前兼容 vs AMDGCN 需重编 vs SPIR-V 依赖驱动 → 影响**设备/版本守卫**（HPC-002）。

### 2.6 HPC-001~012 与证据锚点

| ID | 规则 | 参照/样本（实证）|
|:--|:--|:--|
| HPC-001 | CPU/GPU 双实现一致性 | MFEM **正样本**（统一 `MFEM_HOST_DEVICE`）；缺陷需 C 类合成分歧 |
| HPC-002 | 设备可用性守卫 | MFEM **正样本**（`Device::Allows`/`Configure`/`#ifdef`）|
| HPC-003 | launch 配置硬编码 | MFEM **正样本**（`MFEM_FORALL` 抽象，`<<<>>>` 集中在 `general/forall.hpp`）；缺陷需合成 |
| HPC-004 | H2D/D2H 冗余搬运 | 合成样本（循环内 `map`/`cudaMemcpy`）|
| HPC-005 | halo 交换配对 | OpenFOAM **正样本**（`processorPolyPatch.C` 成对 `UOPstream`/`UIPstream`）；缺陷需合成未配对 |
| HPC-006 | 热循环集合通信 | SU2 常规每步残差 `Allreduce`（非必然缺陷）；缺陷=不可局部化高频集合通信 |
| HPC-007 | 通信/计算重叠 | OpenFOAM **正样本**（`initInterfaceMatrixUpdate`）|
| HPC-008 | 负载划分加权 | deal.II **正样本**（`PartitionWeights`/`get_cell_weights`，p4est 权重）|
| HPC-009 | 拓扑/通信子（窄化 INFO）| 仅"多通信域混用未隔离"；未用 `comm_split` 不判罚 |
| HPC-010 | 线程安全 MPI | SU2 **正样本**（`MPI_Init_thread` 默认 `FUNNELED`、`--thread_multiple` 启 `MULTIPLE`）|
| HPC-011 | OpenMP 共享变量 | 合成样本（缺 `private`/`reduction`）|
| HPC-012 | 并行域嵌套 | 合成样本（`parallel` 内再 `parallel` / `omp` 内 MPI）|
| HPC-013/014 | 扩展性/负载不均衡 | KNOWN_HOLES（需运行测量）|

> **锚点（本地样本，rev 待验证案例集以 `fetch.ref` 固定）**：OpenFOAM `.../constraint/processor/processorPolyPatch.H`、`.../mapDistribute/mapDistributeBase.H`；deal.II `include/deal.II/distributed/p4est_wrappers.h`、`source/distributed/tria.cc`；MFEM `general/device.hpp`、`general/forall.hpp`、`config/config.hpp.in`；SU2 `SU2_CFD/include/solvers/CSolver.hpp`、`SU2_CFD/src/SU2_CFD.cpp`。

---

## 3 Do / Don't 清单

**Do**
- 基线更新前跑程序化校验（区间/维度键/计数类型/确定性）。
- 案例主张附 `repo + 类/文件 + rg 计数`。
- 每条规则配正样本（健康）+ C 类合成负样本（缺陷）。
- 定权重用敏感性分析（稳定区间），不用 LOOCV。
- LLM 只做语义候选精判，必须 `file:line` 证据、低置信降级。
- 低分先归因（真差/误判/语义），不粉饰。

**Don't**
- ❌ 盲刷 `ARCH_REGRESSION_UPDATE=1`（祝福缺陷）。
- ❌ 用"感觉"给项目调分 / 换权重 / 跳规则 / 忽略 ERROR。
- ❌ 把健康样本当缺陷阳性。
- ❌ 无证据断言（尤其 LLM 生成的事实）。
- ❌ 用 apt 的 OCCT 7.6.3 跑 V8.0.1 基线（版本漂移）。
- ❌ 让 LLM 直接产出分数或改基线。

---

## 4 术语表

| 术语 | 英文 | 简义 |
|:--|:--|:--|
| 域分解 | domain decomposition | 切分计算域到多进程 |
| halo/ghost | halo / ghost exchange | 相邻子域边界数据交换 |
| 通信子 | communicator | MPI 进程组+上下文 |
| 非阻塞通信 | non-blocking | `Isend/Irecv`，可与计算重叠 |
| 线程安全 MPI | thread-safe MPI | `MPI_THREAD_MULTIPLE` |
| target offload | device offload | 把计算卸载到 GPU |
| PTX/AMDGCN/SPIR-V | — | NVIDIA 虚拟 ISA / AMD 本机 ISA / Khronos 便携 IR |
| 强/弱扩展 | strong/weak scaling | 扩展性度量 |
| 激活子集归一化 | activation-subset normalization | Σw'=1 |
| LLM 精判 | LLM adjudication | 对候选做确认/否决/降级 |

---

## 5 参考

- 工程实例：`docs/zh/计划/H3阶段进展与决策记录.md`
- 归一化：`docs/zh/计划/H3-WP1归一化实施说明.md`、`权重归一化模型重做方案.md`
- 敏感性：`docs/zh/计划/H3-WP2权重敏感性分析.md`、`H3-WP2权重定案工作底稿.md`
- HPC 设计依据与校对：`docs/zh/并行异构计算架构评估/并行异构计算架构评估设计依据.md`、`设计依据专家校对报告.md`、`设计依据专家校对报告_第二轮.md`
- 基线纪律：`docs/zh/计划/H2待办清单.md`（回归套件修复记录）
- 编制方法：`docs/zh/AI 架构评估文档编制指南.md`、`.opencode/skills/assessment-doc-authoring/`

---

## 版本历史

| 版本 | 日期 | 变更 |
|:-----|:-----|:-----|
| 1.0 | 2026-10-21 | 首版：方法论（基线纪律/实证校对/正负样本/敏感性/归一化/LLM)+ HPC 知识速览 + Do/Don't |

---

*【已验证】= 本仓库实测/源码核验；【建议】= 设计建议，待生产验证。*