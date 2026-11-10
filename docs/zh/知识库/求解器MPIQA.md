# 求解器 MPI / 域分解 / 并行架构 Q&A（详细版）

> **版本**：1.1（补评估解读与治理 Q18–Q29）
> **日期**：2026-11-05
> **范围**：MPI 通信域、OpenFOAM 域分解、`decomposeParDict`、`multiLevel`、节点/CPU/核/GPU 分层、PIMPLE、V&V 不确定度、评估治理/LLM/advisory/B3.7
> **源码基准**：OpenFOAM-v2512（本地 `D:\OPENSOURCE\OpenFOAM-v2512`）；结论以源码 `file:line` 为准
> **关联文档**：`MPI问答汇编.md`、`HPC评估方法论与知识速览.md`、`并行异构计算架构评估指南 v0.8`

---

## 目录

- [1. MPI 通信域基础](#1-mpi-通信域基础)
  - [Q1 communicator = 群 + 频道](#q1-communicator--群--频道)
  - [Q2 MPI_Comm_dup 与 --mpi-no-comm-dup](#q2-mpi_comm_dup-与---mpi-no-comm-dup)
  - [Q3 子域/临时域](#q3-子域临时域)
  - [Q4 群和频道有什么区别](#q4-群和频道有什么区别)
- [2. OpenFOAM 通信域与多区域](#2-openfoam-通信域与多区域)
  - [Q5 OpenFOAM 通信域是否隔离](#q5-openfoam-通信域是否隔离)
  - [Q6 区域是什么意思](#q6-区域是什么意思)
  - [Q7 多区域/多求解器](#q7-多区域多求解器)
- [3. 域分解 method](#3-域分解-method)
  - [Q8 method 是划分网格方法吗](#q8-method-是划分网格方法吗)
  - [Q9 decomposeParDict 的 regions 块](#q9-decomposepardict-的-regions-块)
  - [Q10 method 举例](#q10-method-举例)
  - [Q11 完整 4×4 域分解例子](#q11-完整-44-域分解例子)
  - [Q12 multiLevel：节点/CPU/核（16×16，32 rank）](#q12-multilevel节点cpu核161632-rank)
  - [Q13 multiLevel + GPU（64×64，64 rank）](#q13-multilevel--gpu646464-rank)
- [4. 负载加权](#4-负载加权)
  - [Q14 OpenFOAM 默认是否加权](#q14-openfoam-默认是否加权)
- [5. PIMPLE 外循环](#5-pimple-外循环)
  - [Q15 PIMPLE 外循环](#q15-pimple-外循环)
- [6. V&V 不确定度](#6-vv-不确定度)
  - [Q16 E/U_V 与 U_SN/U_input/U_D](#q16-eu_v-与-u_snu_inputu_d)
- [7. 异构节点](#7-异构节点)
  - [Q17 节点上 CPU/core/GPU 是否异构共存](#q17-节点上-cpucore-gpu-是否异构共存)
- [8. 评估解读与治理（Q18–Q29）](#8-评估解读与治理)
  - [Q18 100 分与建议](#q18-100-分与建议)
  - [Q19 建议是否计分](#q19-建议是否计分)
  - [Q20 多级计算结构](#q20-多级计算结构)
  - [Q21 拓扑 advisory](#q21-拓扑-advisory)
  - [Q22 LLM 语义精判](#q22-llm-语义精判)
  - [Q23 B3-B3.5-B3.7 验证链](#q23-b3-b35-b37-验证链)
  - [Q24 HPC-010 检查与修复](#q24-hpc-010-检查与修复)
  - [Q25 NeuralFoil 非 HPC](#q25-neuralfoil-非-hpc)
  - [Q26 静态评估的验证域](#q26-静态评估的验证域)
  - [Q27 HPC-001 与 Validation](#q27-hpc-001-与-validation)
  - [Q28 candidate 与 confirmed](#q28-candidate-与-confirmed)
  - [Q29 Kokkos GPU 子维](#q29-kokkos-gpu-子维)
- [附录 A：源码证据表](#附录-a源码证据表)
- [附录 B：常用命令](#附录-b常用命令)
- [版本历史](#版本历史)

---

## 1. MPI 通信域基础

### Q1 communicator = 群 + 频道

MPI 的 communicator 由两部分组成：

| 组成 | 含义 |
|:--|:--|
| **group（群）** | 哪些 rank 参与、rank 顺序 |
| **context（频道，类比）** | MPI 内部通信上下文 ID |

消息匹配规则：

```text
(context, source rank, tag)
```

- **群不同**：不在群里的 rank 不能参与该 communicator 的收发；
- **频道不同**：即使 source/tag 一样，消息也收不到。

> "频道"不是 MPI 官方术语，是对 **context** 的类比；官方说法是 communicator 的 context ID。

---

### Q2 MPI_Comm_dup 与 --mpi-no-comm-dup

`MPI_Comm_dup(MPI_COMM_WORLD, &newcomm)`：

- **group / rank 顺序不变**；
- 分配**新的 context**；
- 集体调用（communicator 内所有 rank 必须一起调）；
- 复制 communicator attributes。

作用：让 OpenFOAM 与其它同样使用 `MPI_COMM_WORLD` 的库（PETSc/HYPRE/插件）**不串台**。

OpenFOAM 选项：

```cpp
// src/OpenFOAM/global/argList/argList.C:136-141
"mpi-no-comm-dup", "Disable initial MPI_Comm_dup()"
```

| 模式 | `commGlobal()` | 隔离性 |
|:--|:--|:--|
| 默认 | `MPI_COMM_WORLD` 的 dup（新 context）| 与外部库隔离 |
| `--mpi-no-comm-dup` | 直接 `MPI_COMM_WORLD` | 无隔离，兼容性优先 |

代价：关闭后若 tag/通配接收重叠，可能串台。

---

### Q3 子域/临时域

#### 子域（持久子通信域）

OpenFOAM 的 RAII 类 `UPstream::communicator`：

```cpp
// UPstream.H:2084
static communicator split(parentComm, colour, two_step = true);
```

- `two_step=true`：`MPI_Allgather` + `MPI_Comm_create_group`；
- `two_step=false`：`MPI_Comm_split`（`UPstream.C:1023`）；
- `colour < 0` → 不参与（`MPI_UNDEFINED`）。

典型子域：

| 子域 | 位置 | 用途 |
|:--|:--|:--|
| `commLocalNode_` | `UPstream.C:1135-1139` | 节点内 rank（共享内存）|
| `commInterNode_` | 同上 | 节点间 leader |
| `-mpi-threads` appNum | `UPstream.C:543` | 按 MPI 应用号分组 |

#### 临时域（作用域切换）

```cpp
const label old = UPstream::commWorld(myComm);
...  // 这段代码走 myComm
UPstream::commWorld(old);
```

典型使用点：

| 位置 | 场景 |
|:--|:--|
| `fvMeshTools.C:973-990` | 并行网格操作 |
| `multiWorldConnectionsObject.C:232-281` | 多 world 连接 |
| `mappedPatchBase*.C` | mapped patch |
| `fieldsDistributor.txx:240-257` | 文件分发 |

风险：`commWorld` 是全局状态，**非线程安全**；异常/提前返回未恢复会污染后续调用。

---

### Q4 群和频道有什么区别

| | 群（group） | 频道（context） |
|:--|:--|:--|
| 回答 | 谁参与、rank 顺序 | 消息走哪条上下文 |
| 可见性 | 可查询（`MPI_Comm_group` 等）| 内部 ID |
| 改变它 | `MPI_Comm_split` / `create_group` | `MPI_Comm_dup` |
| 作用 | 能不能参与 | 会不会串台 |

三种操作：

| 操作 | 群 | 频道 | 用途 |
|:--|:--:|:--:|:--|
| `MPI_Comm_dup` | 不变 | 新建 | 同批人、独立通道 |
| `MPI_Comm_split` | 按 colour 拆子集 | 新建 | 子群通信 |
| `MPI_Comm_create_group` | 指定子集 | 新建 | 精确子群 |

**关键**：换群一定换频道；换频道不一定换群。

---

## 2. OpenFOAM 通信域与多区域

### Q5 OpenFOAM 通信域是否隔离

| 层面 | 是否隔离 | 证据 |
|:--|:--|:--|
| 与外部库 | ✅ 默认 `MPI_Comm_dup(MPI_COMM_WORLD)` | `argList.C:136-141`、`UPstream.C:164/198` |
| 串行/单进程 | ✅ `commSelf` | `UPstream.C:175-184/211-222` |
| 节点内/节点间 | ✅ `commLocalNode_` / `commInterNode_` | `UPstream.C:1135-1139` |
| 多 world 连接 | ✅ 成对 communicator | `multiWorldConnectionsObject.C:143-281` |
| **多区域/多求解器** | ❌ 默认共享 world | `regionProperties` 无 comm 操作 |
| **按区域永久独立域** | ❌ 需显式 `splitCommunicator`/`multiWorld` | — |

结论：有 dup/self/split/临时域，**不是完全未隔离**；但"每区域独立通信域"默认不提供。

---

### Q6 区域是什么意思

**区域（region）= 一个有名字、有独立网格/场/物性的求解子域**；运行期是一个 `fvMesh`。

| 组成 | 位置 |
|:--|:--|
| 名字 | `air`、`walls`、`solid1`… |
| 网格 | `constant/<region>/polyMesh/` |
| 场 | `0/<region>/` |
| 物性 | `constant/<region>/thermophysicalProperties` |
| 数值设置 | `system/<region>/fvSchemes`、`fvSolution` |

代码映射：

```cpp
// createMeshes.H
regionProperties rp(runTime);
#include "createFluidMeshes.H"
#include "createSolidMeshes.H"

// createFluidMeshes.H
const wordList fluidNames(rp["fluid"]);
PtrList<fvMesh> fluidRegions(fluidNames.size());
```

易混概念：

| 概念 | 是什么 | 例子 |
|:--|:--|:--|
| **Region（区域）** | 一整块独立网格 + 场 + 物性 | `air`、`walls` |
| **Patch（边界）** | 一块网格的边界 | `inlet`、`outlet`、`regionCoupled` |
| **CellZone（单元区）** | 同一网格内的一批单元 | 多孔区、MRF 区 |
| **Subdomain（子域）** | 同一区域网格按 MPI 切给各 rank 的部分 | rank0 的 1/4 |
| **World（世界）** | 独立 case/求解上下文 | `multiWorld` 的 `fluid/`、`solid/` |

---

### Q7 多区域/多求解器

`chtMultiRegionFoam` 例子（一个进程、一个 world、多个 `fvMesh`）：

```cpp
// chtMultiRegionFoam.C:87-130
while (runTime.run())
{
    for (int oCorr=0; oCorr<nOuterCorr; ++oCorr)
    {
        forAll(fluidRegions, i) { #include "solveFluid.H" }
        forAll(solidRegions, i) { #include "solveSolid.H" }
        if (coupled) { fvMatrixAssemblyPtr->solve(); ... }
    }
}
```

两种模式：

- **依次（segregated，`coupled=false`）**：每个区域各自 `hEqn.solve()`；外层 `energyCoupling` 迭代界面；
- **耦合（monolithic，`coupled=true`）**：每个区域只 `addFvMatrix`，统一 `fvMatrixAssemblyPtr->solve()`。

对比：

| 形态 | 可执行文件 | MPI world | 耦合方式 |
|:--|:--|:--|:--|
| 进程内多区域 | 1 个 | 共享 1 个 | 函数调用/统一矩阵/边界交换 |
| 外部多求解器 | 多个 | 各自独立 | socket/MPI 端口/耦合库 |

---

## 3. 域分解 method

### Q8 method 是划分网格方法吗

**是"分区"方法，但不是"画网格"方法。** 它决定"已有网格的每个单元分给哪个进程"。

输入：已有网格；输出：

```cpp
labelList cellToProc;   // 每个单元 → 一个 processor 编号
```

`decomposePar` 随后写出 `processorN/constant/polyMesh/`，并在子域边界登记 `processor` patches。

不是：

| 说法 | 实际 | method 关系 |
|:--|:--|:--|
| "画网格" | `blockMesh`/`snappyHexMesh` | ❌ 完全不同 |
| "加密/细化" | `refineMesh`/`dynamicRefineFvMesh` | ❌ 改变单元数 |
| "几何切割" | 切几何 | ❌ 只做单元归属 |
| "加权" | `weightField`/`processorWeights` | ❌ 权重是输入 |
| "子域数" | `numberOfSubdomains` | ❌ 决定切几份 |

---

### Q9 decomposeParDict 的 regions 块

顶层 vs 区域：

```cpp
numberOfSubdomains  2048;     // 必填（串行 MUST_READ；并行 LAZY）
method              metis;    // 全局默认

regions
{
    heater
    {
        numberOfSubdomains  2;
        method              hierarchical;
        coeffs { n (2 1 1); }
    }

    "*.solid"
    {
        numberOfSubdomains  16;
        method              scotch;
    }
}
```

规则（`decomposition.dox:157-161`）：

| 项 | 顶层 | 区域 |
|:--|:--|:--|
| `numberOfSubdomains` | 必填（全局域数）| 可选；不同才写 |
| `method` | 默认 | 可选；覆盖顶层 |
| `coeffs` | 可选 | 可选；区域专属 |
| 区域名 | — | 精确名或正则 |

代码：

- `optionalRegionDict`（`decompositionMethod.C:126-142`）从 `regions` 取区域字典；
- `nDomains`（`:82-123`）读取区域/顶层子域数；区域值必须在 `1..global`，否则警告并回退 global；
- `decompositionMethod::New(decompDict, regionName)` 选区域方法。

语义：

- 每区域独立分解；
- 子域数 ≤ global；少了则部分 rank 在该区域无单元（空闲/只耦合）；
- **不是**每区域独立通信域；仍共享 world。

---

### Q10 method 举例

| `method` | 类 | 类型 | 关键参数 |
|:--|:--|:--|:--|
| `none` | `noDecomp` | 不分解 | — |
| `simple` | `simpleGeomDecomp` | 几何 | `n (nx ny nz)` |
| `hierarchical` | `hierarchGeomDecomp` | 递归几何 | `n`、`order` |
| `scotch` | `scotchDecomp` | 图划分 | `processorWeights`、`strategy` |
| `metis` | `metisDecomp` | 图划分 | `method k-way`、`processorWeights` |
| `ptscotch` | `ptscotchDecomp` | 并行图划分 | 同 scotch |
| `kahip` | `kahipDecomp` | 图划分 | — |
| `manual` | `manualDecomp` | 手工 | `dataFile` |
| `multiLevel` | `multiLevelDecomp` | 多级组合 | `numberOfSubdomains` 子字典 |
| `structured` | `structuredDecomp` | 结构化 2D | `patches`、`method` |
| `random` | `randomDecomp` | 随机 | `agglom`（仅测试）|

示例：

```cpp
// simple
method simple;  coeffs { n (4 2 1); }

// hierarchical
method hierarchical;  coeffs { n (2 2 2); }

// scotch
method scotch;
scotchCoeffs { processorWeights (1 1 1 1); strategy "b"; }

// metis
method metis;
metisCoeffs { method k-way; processorWeights (1 1 1 1); }

// manual
method manual;  manualCoeffs { dataFile "decompositionData"; }

// multiLevel
method multiLevel;
multiLevelCoeffs
{
    nodes { numberOfSubdomains 4; method hierarchical; coeffs { n (2 2 1); } }
    cpus  { numberOfSubdomains 2; method scotch; }
}

// structured
method structured;
structuredCoeffs { patches (movingWall); method scotch; }

// none
method none;  // 通常 numberOfSubdomains 1
```

`manual` 的 `decompositionData` 是 `labelList`，每单元一个 processor 编号。

---

### Q11 完整 4×4 域分解例子

16 个单元、4 进程，`method simple; coeffs { n (2 2 1); }`。

网格：

```text
j=3 | 12 13 14 15
j=2 |  8  9 10 11
j=1 |  4  5  6  7
j=0 |  0  1  2  3
      i=0 1 2 3
```

归属（`proc = (j/2)*2 + (i/2)`）：

```text
j=3 | 2 2 3 3
j=2 | 2 2 3 3
j=1 | 0 0 1 1
j=0 | 0 0 1 1
```

`cellToProc`（row-major）：

```text
[0,0,1,1,  0,0,1,1,  2,2,3,3,  2,2,3,3]
```

进程间面：**8**（竖切 4 + 横切 4）；每进程 4 面。

对比按列条带 `n (4 1 1)`：

```text
j=3 | 0 1 2 3
...
```

进程间面 **12**；中间进程通信更重。这说明图划分（scotch/metis）倾向紧凑子域。

`manual` 数据：

```text
16
(
0 0 1 1
0 0 1 1
2 2 3 3
2 2 3 3
)
```

---

### Q12 multiLevel：节点/CPU/核（16×16，32 rank）

硬件：2 节点 × 4 CPU × 4 核 = 32 rank。

```cpp
numberOfSubdomains 32;
method multiLevel;

multiLevelCoeffs
{
    nodes { numberOfSubdomains 2; method hierarchical; coeffs { n (2 1 1); } }
    cpus  { numberOfSubdomains 4; method hierarchical; coeffs { n (2 2 1); } }
    cores { numberOfSubdomains 4; method hierarchical; coeffs { n (2 2 1); } }
}
```

乘积 2×4×4=32。

块表：

| node | CPU | x 范围 | y 范围 | rank |
|:--:|:--:|:--:|:--:|:--:|
| 0 | 0 | 0–3 | 0–7 | 0–3 |
| 0 | 1 | 4–7 | 0–7 | 4–7 |
| 0 | 2 | 0–3 | 8–15 | 8–11 |
| 0 | 3 | 4–7 | 8–15 | 12–15 |
| 1 | 0 | 8–11 | 0–7 | 16–19 |
| 1 | 1 | 12–15 | 0–7 | 20–23 |
| 1 | 2 | 8–11 | 8–15 | 24–27 |
| 1 | 3 | 12–15 | 8–15 | 28–31 |

rank 公式（混合进制）：

```text
rank = node*16 + cpu*4 + core
```

进程间面（16×16）：

| 层级 | 面数 |
|:--|:--:|
| 跨节点 | 16 |
| 跨 CPU（同节点）| 48 |
| 跨核（同 CPU）| 96 |
| 合计 | 160 |

`rank0` 邻居：`[1, 2]`（同 CPU core1/core2）。

---

### Q13 multiLevel + GPU（64×64，64 rank）

> **重要**：`decomposePar` 只把单元分给 **MPI rank**，**不直接分 GPU**；`gpus` 只是分解层级名，rank→GPU 绑定由启动器完成。

硬件：4 节点 × 2 socket × 2 GPU/socket × 4 rank/GPU = 64 rank。

```cpp
numberOfSubdomains 64;
method multiLevel;

multiLevelCoeffs
{
    nodes   { numberOfSubdomains 4; method hierarchical; coeffs { n (4 1 1); } }
    sockets { numberOfSubdomains 2; method hierarchical; coeffs { n (1 2 1); } }
    gpus    { numberOfSubdomains 2; method hierarchical; coeffs { n (2 1 1); } }
    cores   { numberOfSubdomains 4; method hierarchical; coeffs { n (2 2 1); } }
}
```

乘积 4×2×2×4=64。

rank 公式：

```text
rank = node*16 + socket*8 + gpu*4 + core
```

块表（节选）：

| node | socket | gpu | x 范围 | y 范围 | rank |
|:--:|:--:|:--:|:--:|:--:|:--:|
| 0 | 0 | 0 | 0–7 | 0–31 | 0–3 |
| 0 | 0 | 1 | 8–15 | 0–31 | 4–7 |
| 0 | 1 | 0 | 0–7 | 32–63 | 8–11 |
| 0 | 1 | 1 | 8–15 | 32–63 | 12–15 |
| 1 | 0 | 0 | 16–23 | 0–31 | 16–19 |
| … | … | … | … | … | … |
| 3 | 1 | 1 | 56–63 | 32–63 | 60–63 |

进程间面（64×64）：

| 层级 | 面数 | 介质 |
|:--|:--:|:--|
| 跨节点 | 192 | 网络 |
| 跨 socket | 64 | UPI/Infinity Fabric |
| 跨 GPU | 256 | NVLink/PCIe |
| 跨 core/rank | 640 | 共享内存 |
| 合计 | 1152 | — |

`rank0` 邻居：`[1, 2]`；`processor1` 16 面（右）、`processor2` 4 面（上）。

GPU 绑定（分解之外）：

```bash
srun --ntasks=64 --gpus-per-task=1 ...
# 或
CUDA_VISIBLE_DEVICES=0 mpirun -np 4 ...
```

> 4 rank/GPU 需 MPS/MIG；更常见的是 **1 rank/GPU**，核用 OpenMP 线程（3 级：node → socket → GPU）。

---

## 4. 负载加权

### Q14 OpenFOAM 默认是否加权

**支持加权，但默认不加权。**

- 默认 `method scotch` + 无 `weightField` → `scotchDecomp.C:270-278` 使用 **uniform weights（全 1）**；
- 加权入口：

| 机制 | 位置 | 说明 |
|:--|:--|:--|
| `weightField <volScalarField>` | `decomposeParDict:169-172`；`domainDecompositionDistribute.C:47-67` | 单元权重 |
| `scotchCoeffs.processorWeights` | `decomposeParDict:142-148` | 进程权重 |
| `simple/hierarchical` 的 `weights` | `simpleGeomDecomp.H:70` | 几何分解权重 |

实现链：

```text
weightField → cellWeights → decomposer.decompose(mesh, cellWeights)
           → scotchDecomp.C:235-268 转 vertex weights
```

对 HPC-008：

- 默认算例属"合理图均衡"；
- 非均匀算例（AMR/多材料/局部源）未配 `weightField` 才构成候选风险；
- **检测器缺口**：`WEIGHTS_RE` 尚未包含 `weightField`/`processorWeights`，建议补。

---

## 5. PIMPLE 外循环

### Q15 PIMPLE 外循环

**PIMPLE 外循环 = 每个时间步内、PISO 压力修正内循环之外的迭代层**，由 `nOuterCorrectors` 控制。

三层结构：

```text
时间步循环
  └─ PIMPLE 外循环 (oCorr = 0..nOuterCorrectors-1)
       ├─ 动量预测/区域求解
       └─ PISO 内循环 (corr = 0..nCorrectors-1) 压力修正
```

参数（`etc/templates/inflowOutflow/system/fvSolution:48-55`）：

```cpp
PIMPLE
{
    nOuterCorrectors         1;
    nCorrectors              2;
    nNonOrthogonalCorrectors 1;
}
```

作用：

- 重新耦合动量/压力，消除算子分裂滞后；
- 支持大 Courant 数（Co>1）；
- 多区域/多物理场外耦合（`energyCoupling`）。

`chtMultiRegionFoam.C:110`：

```cpp
for (int oCorr=0; oCorr<nOuterCorr; ++oCorr)
{
    forAll(fluidRegions, i) { #include "solveFluid.H" }
    forAll(solidRegions, i) { #include "solveSolid.H" }
    if (coupled) { fvMatrixAssemblyPtr->solve(); }
}
```

调参：

| 场景 | 建议 |
|:--|:--|
| 小 Co、弱耦合 | 1 |
| 大 Co、强浮力/旋转 | 2~5 |
| 强界面耦合 | 增大外循环或 `coupledEnergyField` |
| 稳态 | 用 SIMPLE + residualControl |

---

## 6. V&V 不确定度

### Q16 E/U_V 与 U_SN/U_input/U_D

```text
E = S − D
U_V = sqrt(U_SN² + U_input² + U_D²)
|E| ≤ U_V → 一致；否则模型可疑
```

| 量 | 含义 | 方法 |
|:--|:--|:--|
| **U_D** | 实验不确定度 | GUM：A/B 类 → u_c → U=k·u_c |
| **U_SN** | 仿真数值不确定度 | GCI + 迭代 + 时间步 RSS |
| **U_input** | 输入不确定度 | 灵敏度传播或蒙特卡洛 |
| **U_V** | 验证不确定度 | 同覆盖率合成 |

U_D：

```text
u_A = s/√n
u_B = a/√3（矩形）、a/√6（三角）、a/k（正态）
u_c = √(Σu_i² + 2Σρ_ij u_i u_j)
U_D = k·u_c   (k=2 ≈ 95%)
```

U_SN（GCI，三网格、r≥1.3、单调）：

```text
p       = ln((f3−f2)/(f2−f1)) / ln(r)
f_exact ≈ f1 + (f1−f2)/(r^p−1)
GCI     = Fs · |(f1−f2)/f1| / (r^p−1)
U_SN    = √(U_grid² + U_iter² + U_time² + …)
```

- `Fs=1.25`（三网格）、`3`（两网格）；
- 非单调收敛用稳健 GCI/包络。

U_input：

```text
U_input² = Σ (∂S/∂x_i)² u(x_i)²
         + 2Σ_{i<j} (∂S/∂x_i)(∂S/∂x_j) cov(x_i,x_j)
```

或蒙特卡洛：`u_S = √(Σ(S_k−S̄)²/(N−1))`。

覆盖率必须统一（k=2 / Fs=1.25 / ×1.96）。

算例：

```text
U_V = √(0.005² + 0.003² + 0.01²) ≈ 0.0116
|E| = |0.32−0.30| = 0.02 > 0.0116 → 不通过
```

验证域：记录 Re/Ma/几何/边界范围；域外为未验证外推。

与并行：并行不应改变 E/U_V；`U_SN` 需按并行配置重算；HPC-001 是 code-to-code Verification。

---

## 7. 异构节点

### Q17 节点上 CPU/core/GPU 是否异构共存

**有，且是常态。**

```text
Node
├── CPU socket 0 → core 0/1/... → SMT threads
├── CPU socket 1 → core ...
├── GPU 0 → SMs/CUs → CUDA cores/stream processors → HBM
├── GPU 1 → ...
└── 互连：UPI/Infinity Fabric、PCIe、NVLink
```

异构维度：

| 维度 | CPU core | GPU |
|:--|:--|:--|
| 执行模型 | MIMD | SIMT |
| 数量 | 几十~上百核/节点 | 几千~上万 lane |
| 内存 | DDR5 | HBM |
| 编程 | OpenMP/线程 | CUDA/HIP/SYCL/Kokkos |
| 互连 | UPI/Infinity Fabric | PCIe/NVLink |
| 适合 | 控制/分支/串行 | 规则并行/稠密 |

示例节点：

| 组件 | 配置 |
|:--|:--|
| CPU | 2 × Xeon 8480+（56 core/颗，112 core，224 线程）|
| GPU | 4 × H100（80GB HBM3，NVLink 4）|
| NUMA | 2 域；每 socket 2 GPU |
| 互连 | UPI、PCIe Gen5、NVLink |

对 OpenFOAM：

- `decomposePar` 只分 rank；CPU/core/GPU 异构不改变"单元→rank"；
- rank 绑 core（`numactl`/`taskset`）、绑 GPU（`CUDA_VISIBLE_DEVICES`/Slurm）；
- GPU 挂在某个 socket/NUMA 下，rank 应同 NUMA 绑定；
- `multiLevel` 的 `gpus` 层只是"再切子域"。

查看拓扑：

```bash
lscpu
numactl -H
nvidia-smi -L
nvidia-smi topo -m
```

---

## 8. 评估解读与治理（Q18–Q29）

### Q18 100 分与建议

**问题**：OpenFOAM 的 HPC 评估分数是 100，为什么还有那么多建议？

**回答**：100 分是"**12 条 HPC 规则没有命中**"的分数，不是"没有可优化空间"。

```text
子维得分 = 100 − Σ(该子维已触发规则的赋分)
overall  = Σ(适用子维得分 × 归一权重)
```

OpenFOAM 当前：适用 `mpi_halo / load_topology / hybrid_parallel`，触发规则 0，overall=100，gate=PASS。

建议分三类：

| 优先级 | 性质 | 例子 |
|:--|:--|:--|
| P0 | 护栏/预防（当前未违规）| 保持 halo 成对、谨慎 `-mpi-threads`、MPI 不进 `omp` |
| P1 | 特定工况的扩展性优化 | 非均匀算例加 `weightField`、多区域调子域数、`multiLevel` 拓扑绑定 |
| P2 | 性能调优（非缺陷）| PIMPLE 调参、OpenMP 阈值、通信重叠、GPU 绑定、并行 I/O |

**结论**：100 分回答"有没有已知缺陷"；建议回答"还能不能更好"。

---

### Q19 建议是否计分

**问题**：为什么不把建议也列为评估项？

**回答**：建议依赖工况/硬件，缺乏客观阈值；直接计分会破坏**可比性、可复现性与门禁语义**。

| 原因 | 说明 |
|:--|:--|
| 无客观阈值 | "用 `weightField`"只对非均匀负载有益 |
| 工况/硬件依赖 | `multiLevel`、NUMA/GPU 绑定、并行 I/O 收益取决于拓扑/规模 |
| 无法静态验证收益 | 扩展性/负载需 TAU/MUST 实测 |
| 会误伤健康项目 | 均匀算例默认 scotch 是合理的 |
| 破坏可比性 | 分数会随目标/进程数/硬件变化 |
| 门禁语义 | 门禁应回答"是否有已知缺陷" |

**已经是规则的"建议"**：HPC-008（未加权）、HPC-006（热循环集合通信）、HPC-003（launch 魔法数）、HPC-007（未重叠）、HPC-009（通信域未隔离）。

**不适合计分的**：`multiLevel`、PIMPLE 调参、rank/GPU 绑定、并行 I/O。

**三种落地方式**：

| 方案 | 做法 | 影响 |
|:--|:--|:--|
| A. Advisory（当前选择）| `topology_advisory` 等输出，不计分 | 不改变 100 分/回归/门禁 |
| B. 新增规则 | 可静态判定的建议升级为 candidate/INFO 规则 | 需重新分配赋分、更新指南/案例集 |
| C. 新增子维 | 独立"拓扑与亲和性"子维 | 改动最大 |

升级为规则的标准：静态可检、阈值明确、A 类低误报、不重复、可校准、修复动作明确。

---

### Q20 多级计算结构

**问题**：HPC 评估是否涉及多级计算结构（Node/CPU/core/GPU）？

**回答**：**当前没有作为一等评估项**。指南 §2.3 只有 HPC-008（加权分区）与 HPC-009（通信域/拓扑隔离）；不评估 `multiLevel`、rank→CPU/GPU 绑定、NUMA 亲和、GPU 拓扑。

原因：

| 原因 | 说明 |
|:--|:--|
| 静态源码不可见 | 多级分解/绑定在 `decomposeParDict`、Slurm 脚本、启动器 |
| "正确"依赖目标 | 单节点小算例不需要 `multiLevel` |
| 误报/可比性 | "未用 multiLevel"不是缺陷 |
| 运行时项 | 实际扩展/失衡已列入 KNOWN_HOLES HPC-013/014 |

可静态检的信号：

| 信号 | 位置 |
|:--|:--|
| `multiLevel` / `regions` / `weightField` / `processorWeights` | `decomposeParDict` |
| `--cpu-bind` / `--gpus-per-task` / `--gpu-bind` / `--map-by` | Slurm/mpirun |
| `numactl` / `taskset` | 启动脚本 |
| `CUDA_VISIBLE_DEVICES` / `KOKKOS_ENABLE_*` | 启动脚本/构建配置 |

---

### Q21 拓扑 advisory

**问题**：如何在不破坏 100 分语义的前提下补多级结构？

**回答**：采用**方案 A：advisory，不计分**。

引擎输出 `topology_advisory`：

```json
{
  "scored": false,
  "multi_level_decomposition": "present|absent|unknown",
  "weighted_partition": "...",
  "cpu_binding": "...",
  "gpu_binding": "...",
  "numa_affinity": "...",
  "gpu_backend": "...",
  "notes": ["advisory only: not scored; does not change overall/gate/confirmed"]
}
```

- 信号来源：`decomposeParDict`、`.slurm/.sh/.bat/.ps1/.yaml/.yml`、Makefile/CMake；
- 报告新增"拓扑与亲和性建议（advisory）"一节；
- **不改变** `overall`、`gate`、`confirmed`、回归快照。

OpenFOAM 实测：`multi_level=present`（`etc/caseDicts/annotated/decomposeParDict`）、`binding=absent`；overall 100/PASS 不变。

> 局限：只提示可见配置，不判实际拓扑最优；最终以启动器/TAU 为准。

---

### Q22 LLM 语义精判

**问题**：语义精判（LLM）应用到了吗？

**回答**：**已实现为可选层**（`scripts/llm_refine_hpc.py`），但不进入确定性评分主链路。

| 项 | 说明 |
|:--|:--|
| 输入 | candidate + `file:line` + 代码片段 |
| 输出 | `llm_review: confirm/reject/uncertain` + `llm_evidence` + `llm_confidence` |
| 后端 | `openai`（temperature=0）/ `opencode` / `mock` / `auto` |
| 缓存 | 按 `(rule,file,line,snippet,model,prompt)` |
| 约束 | 不改评分/门禁/confirmed；不自动 BLOCK；证据缺失 → uncertain |

实跑（opencode）`bad_project_hpc` 的 HPC-005：

```text
HPC-005 review= confirm conf= high
evidence= src/halo.cpp:5 — 局部 MPI_Request 在函数返回前未见 Wait/Test，
          request 随栈销毁，非阻塞发送配对缺失
```

结果：`overall=58.5`、`gate=WARN`、`HPC-002 confirmed` 不变。

**分工**：

```text
正则/静态 → candidate
LLM → confirm/reject/uncertain + file:line
MUST/TSan/TAU → 实测事实
人工 → 最终确认
```

---

### Q23 B3-B3.5-B3.7 验证链

**问题**：为什么没有外部验证基线（回归守护）→ B3.5 → B3.7？

**回答**：HPC **有 B3 和 B3.5**，真正缺的是 B3.7；现已补上。

| 阶段 | 定义 | HPC 现状 |
|:--|:--|:--|
| B3 外部验证基线 | 真实项目快照 + pytest，防分数漂移 | ✅ 5 基线（OpenFOAM/deal.II/MFEM/SU2/non-HPC）|
| B3.5 开源验证 | 对照案例集 A 类预期，查误报/漏报 | ✅ 4 A 类 + 12 规则正负例 + Harness |
| B3.7 交叉验证 | 9 折 LOOCV ≥7/9 | ✅ **8/9**（9 样本 = 5 健康 + 4 不健康）|

B3.7 之前缺失的原因：

1. 语料不足（HPC 只有 4 个健康 A 类）；
2. 不健康标签难定（需专家 + MUST/TSan/TAU）；
3. 归属 WP-8（F3）/KPI5，不在 WP-3 验收；
4. candidate/confirmed 语义使标签不稳定；
5. 运行成本高。

补法：9 样本语料 + `scripts/cross_validate_hpc.py` + 门槛 7/9；结果为 8/9，唯一离群 `unhealthy_bad_project 58.5`。

---

### Q24 HPC-010 检查与修复

**问题**：OpenFOAM 的 HPC-010 具体情况？为什么工具之前没发现？

**回答**：OpenFOAM **没有真实 HPC-010 违规**；原检测器存在"整项目跳过"缺陷。

源码事实：

- `UPstream.C:235-249`：`needsThread ? MPI_THREAD_MULTIPLE : MPI_THREAD_SINGLE`；
- 默认 SINGLE，`-mpi-threads` 才请求 MULTIPLE；
- 生产代码唯一 OpenMP 是 `MappedFileFilterFieldTemplates.C:103` 的 `parallel for`，**不含 MPI**。

原缺陷：

```python
if any("MPI_THREAD_MULTIPLE" in c for _p, c in self._iter_cxx_production()):
    return []   # 整项目跳过
```

修复：

- `_thread_support_level()`：`MULTIPLE / UNKNOWN / LT_MULTIPLE`；
- `_omp_mpi_scopes()`：覆盖块形式与 `parallel for`；
- `_loop_body_after()`：只取紧随循环体，避免误取后续循环的 `{`；
- 仅显式无条件 MULTIPLE 跳过，其余均检查。

结果：OpenFOAM `thread level=UNKNOWN`、HPC-010 **0**；`bad_project_hpc` 仍命中 HPC-010（58.5/WARN）。

---

### Q25 NeuralFoil 非 HPC

**问题**：NeuralFoil 的 HPC 评估结果？

**回答**：**`is_hpc=False`，HPC 维度不适用**（不是失败）。

- 仓库：`https://github.com/peterdsharpe/NeuralFoil`（HEAD `9877941`）；
- 源码扫描 **0 个 HPC 信号**（无 MPI/OpenMP/CUDA/HIP/Kokkos/线程）；
- 纯 Python 气动求解库（NeuralFoil 代理模型 + NumPy/Numba）；
- 输出：`overall=None`、`gate=PASS`、4 维 N/A、`topology_advisory={}`。

> 这是正确的 N/A，不是"HPC 100 分"。

---

### Q26 静态评估的验证域

**问题**：本次评估结论适用哪些 Re/Ma/网格规模/进程数？

**回答**：静态 HPC 评估**没有 Re/Ma 验证域**；它的"验证域"是代码版本 + 规则 + 配置。

| 维度 | 本次覆盖 |
|:--|:--|
| 代码版本 | OpenFOAM-v2512（ref v2512）|
| 代码范围 | 生产 C/C++（排除 externals/tests/examples/bundled/contrib）|
| 规则 | HPC-001~012 |
| 配置 | 默认 scotch、无 GPU、无 `-mpi-threads` |
| 环境 | 纯静态，不绑定 MPI 实现/机器/进程数 |

按 Re/Ma/网格/进程数：

- **Re/Ma**：静态规则与它们无关，**未验证**任何 Re/Ma 下的数值正确性；
- **网格规模**：静态结论与网格无关；HPC-006/008 风险随规模/非均匀性上升，未验证大规模/AMR；
- **进程数**：静态结论与 N 无关；HPC-008/006 风险随 N 上升，未验证高 rank/多节点。

**未验证外推**：具体 Re/Ma、非 v2512 版本、`-mpi-threads`、GPU offload、大规模/多节点/异构节点、AMR/多材料/粒子、多区域/多 world、外部库/插件、不同 MPI 实现。

验证方式：MUST/TSan/TAU + 强/弱扩展 + `decomposePar -cellDist`；数值可信度需另行做 E/U_V Validation。

---

### Q27 HPC-001 与 Validation

**问题**：HPC-001（CPU/GPU 双实现一致性）与 Validation（E/U_V）的区别？

**回答**：HPC-001 是 **code-to-code Verification**；Validation 是对实验（EFD）的 Validation。

| 维度 | HPC-001 | Validation（E/U_V）|
|:--|:--|:--|
| 问题 | 两套实现是否一致？ | 模型是否与实验一致？ |
| 参照 | 另一套实现 | EFD 实验数据 |
| 误差 | `|S_cpu − S_gpu|` | `E = S − D` |
| 不确定度 | 容差 | `U_V = √(U_SN²+U_input²+U_D²)` |
| 判据 | 差异 ≤ tol | `|E| ≤ U_V` |
| 归属 | Verification | Validation |

四种组合：

| HPC-001 | Validation | 含义 |
|:--:|:--:|:--|
| ✅ | ✅ | 实现一致且模型在 U_V 内 |
| ✅ | ❌ | 两实现一致但模型偏差（最危险）|
| ❌ | ✅ | 实现分歧但都在 U_V 内（仍需修实现）|
| ❌ | ❌ | 双重问题 |

例：CPU/GPU 都算 0.32（HPC-001 通过），实验 0.30、U_V=0.0116 → `|E|=0.02>U_V`，Validation 不通过。

---

### Q28 candidate 与 confirmed

**问题**：为什么某规则是 candidate 而不是 confirmed？

**回答**：candidate 是"静态风险信号"，confirmed 是"已确认事实"。

| 标记 | 含义 | 影响 |
|:--|:--|:--|
| candidate | 静态模式推断的风险 | 计入评分；不触发门禁/封顶 |
| confirmed | 高置信命中或经 LLM/TAU/人工确认 | 计入评分；触发门禁/封顶 |

当前仅 **HPC-002** 为 confirmed；其余为 candidate。

为什么需要 candidate：静态无法证明运行时事实（跨函数配对、实际失衡、线程级别、数据竞争），且要避免误杀健康项目。

确认链：

```text
静态 candidate → LLM 语义精判 → MUST/TSan/TAU → 人工裁定
```

---

### Q29 Kokkos GPU 子维

**问题**：为什么 Kokkos 项目 GPU 子维不适用？

**回答**：引擎只认 **GPU 后端证据**，不认泛用 `Kokkos::`。

| 信号 | GPU 子维适用 |
|:--|:--:|
| `Kokkos::parallel_for` / `Kokkos::View` | ❌（可移植 API，CPU 后端也用）|
| `KOKKOS_ENABLE_CUDA/HIP/SYCL` | ✅ |
| `Kokkos::Cuda/HIP/SYCL` / `CudaSpace/HIPSpace` | ✅ |
| `DEAL_II_WITH_KOKKOS`（单独）| ❌（deal.II 恒真）|

原因：

1. Kokkos 是性能可移植层，同一份代码可编到 CPU/GPU；
2. `DEAL_II_WITH_KOKKOS` 恒真，不能当 GPU 信号；
3. 避免对 CPU 构建误报 HPC-001~004。

纯 Kokkos CPU 项目：`is_hpc=True`、`backend_consistency=N/A`、`hybrid_parallel` 适用。

若仓库有 GPU 构建但无后端宏：静态 N/A（已知局限）；可用生成的 `config.h`/`CMakeCache` 或显式能力开关。

---

## 附录 A：源码证据表

| 主题 | 文件:行 |
|:--|:--|
| `--mpi-no-comm-dup` | `src/OpenFOAM/global/argList/argList.C:136-141` |
| commGlobal/commSelf 初始化 | `src/Pstream/mpi/UPstream.C:164-222` |
| `commSelf`/`commWorld` 定义 | `src/OpenFOAM/db/IOstreams/Pstreams/UPstream.H:853-865` |
| `splitCommunicator` / `MPI_Comm_split` | `src/Pstream/mpi/UPstream.C:944-1035` |
| 节点内/节点间子域 | `src/Pstream/mpi/UPstream.C:1135-1139` |
| 临时切换 `commWorld` | `fvMeshTools.C:973-990`、`multiWorldConnectionsObject.C:232-281`、`mappedPatchBase*.C` |
| `regionProperties` | `src/meshTools/regionModel/regionProperties/` |
| cht 主循环 | `applications/solvers/heatTransfer/chtMultiRegionFoam/chtMultiRegionFoam.C:87-217` |
| 耦合能量 | `chtMultiRegionFoam.C:132-136/196-209`、`include/createCoupledRegions.H` |
| `solveFluid/solveSolid` | `fluid/solveFluid.H`、`solid/solveSolid.H` |
| `decomposeParDict` multi-region | `etc/caseDicts/annotated/decomposeParDict:31-53` |
| `weightField` | `etc/caseDicts/annotated/decomposeParDict:169-172`；`domainDecompositionDistribute.C:47-67` |
| scotch 默认 uniform | `src/parallel/decompose/scotchDecomp/scotchDecomp.C:209-278` |
| `regions` 读取 | `decompositionMethod.C:126-142`、`:82-123` |
| multiLevel 组合 | `multiLevelDecomp.C:318-380`、`decomposition.dox:121-215` |
| `noDecomp`（none）| `noDecomp.C:67-107` |
| manual 数据格式 | `manualDecomp.C:65-115` |
| PIMPLE 参数 | `etc/templates/inflowOutflow/system/fvSolution:48-55` |

---

## 附录 B：常用命令

```bash
# 分解（可加 -cellDist 可视化）
decomposePar -case case -region fluid -cellDist

# 并行求解
mpirun -np 32 foamRun -parallel

# 合并
reconstructPar -case case

# 查看硬件拓扑
lscpu
numactl -H
nvidia-smi -L
nvidia-smi topo -m
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|:--|:--|:--|
| 1.0 | 2026-11-05 | 首版：MPI 通信域、OpenFOAM 通信域/多区域、域分解 method、regions、4×4 与 multiLevel（node/CPU/core/GPU）示例、负载加权、PIMPLE、V&V、异构节点 |
| 1.1 | 2026-11-05 | 追加 Q18–Q29：100 分与建议、建议是否计分、多级计算结构、拓扑 advisory、LLM 语义精判、B3/B3.5/B3.7、HPC-010 修复、NeuralFoil 非 HPC、静态验证域、HPC-001 vs Validation、candidate/confirmed、Kokkos GPU 子维 |
