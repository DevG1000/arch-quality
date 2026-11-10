# H3 WP-3 阶段 B 实现方案（HPC 引擎）

> **版本**：0.2（经专家校对 P1×4 / P2×5 修订）
> **日期**：2026-10-21
> **归属**：H3 WP-3 维度⑥ 标准文档包 — 阶段 B（引擎/Skill/测试/部署）
> **依据**：`并行异构计算架构评估指南.md` v0.8 + 验证案例集 v0.3 + 设计依据 v0.4
> **状态**：方案（待专家校对后实施）

---

## 一、目标与验收

实现 `src/arch_quality/arch_metrics_hpc.py`（`HpcArchitectureMetrics`），覆盖 4 子维 + 12 规则 + 适用性门控 + 豁免体系，并与综合报告/registry/CI 集成。

| 验收项 | 口径 |
|:--|:--|
| 规则覆盖 | 12 条各 ≥1 用例（案例集 v0.3 校准）|
| 子维 | 4 子维得分 + 适用性归一化 + `applicability_set` |
| 豁免 | 3 注解 + 30% 反滥用 + `waiver_audit` |
| 集成 | registry v1.4 / schema / validator / profile / 报告 / 一致性 / harness / CI |
| 回归 | ≥5 项目基线（OpenFOAM/deal.II/MFEM/SU2 + 1）|
| 测试 | 单元 + 变异 + 集成/E2E + harness |

---

## 二、模块与接口（`arch_metrics_hpc.py`）

对齐 GCS 引擎结构：

```python
SKILL_PATH = .../skills/hpc-architecture.md          # 4 子维权重解析
GUIDE_VERSION = "0.8"; SKILL_VERSION = "1.0"

class HpcArchitectureMetrics:
    def __init__(self, root): index; weights; _all_contents; _waivers; _is_hpc
    def _init_weights(self):            # 从 skill 解析 4 维权重（sum=1）
    def _scan_files(self):              # 采集豁免注解 + 内容（剥离注释）
    def _skip(self, abs_path, exclude_test=False):   # 第三方/测试/豁免
    def _waiver_audit(self):            # 三通道 count/ratio + 30% abuse_warning
    def calc_backend_consistency(self): # 2.1 → (score, detail)
    def calc_mpi_halo(self):            # 2.2
    def calc_load_topology(self):       # 2.3
    def calc_hybrid_parallel(self):     # 2.4
    def check_hpc_rules(self):          # 12 规则 violation 列表（含 candidate/confirmed）
    def _applicability(self):           # {S1:bool,S2:bool,S3:bool,S4:bool}
    def all_metrics(self):              # 见 §二.1
def main(): ...
```

### 2.1 `all_metrics()` 输出结构

```json
{
  "overall": 81.2,
  "is_hpc": true,
  "applicability_set": ["S2","S3","S4"],
  "score_scope": "subset",
  "dimensions": {
    "backend_consistency": {"score": null, "applicable": false, "detail": {}},
    "mpi_halo":            {"score": 90,   "applicable": true,  "detail": {}},
    "load_topology":       {"score": 95,   "applicable": true,  "detail": {}},
    "hybrid_parallel":     {"score": 62,   "applicable": true,  "detail": {}}
  },
  "hpc_violations": [{"rule":"HPC-010","severity":"HIGH","output_level":"WARNING","count":2,"candidate":false,"confirmed":true,"detail":"..."}],
  "gate_status": "WARN",
  "confirmed_max_severity": "HIGH",
  "waiver_audit": {"benchmark_ok":{...},"deferred":{...},"gpu_only":{...},"invalid_waivers":[...],"abuse_limit":0.30,"abuse_warning":null},
  "version_info": {"guide_version":"0.8","skill_version":"1.0"}
}
```

- `is_hpc=False` → 4 维 score=None、overall=None、violations=[]。
- `score_scope=subset` 当存在不适用子维。

### 2.2 skill 文件格式（前置，W1 首交付）

`skills/hpc-architecture.md` 须含 `## 权重分配` 段落，表格 4 行（供 `load_weights_from_skill` 解析，和=100%）：

| 子维度 | 权重 |
|:--|:--:|
| 后端接口一致性 | 30% |
| MPI 域分解与 halo 交换 | 30% |
| 负载均衡与进程拓扑 | 20% |
| 混合并行（MPI×OpenMP）冲突 | 20% |

> 缺 `## 权重分配` 时 `load_weights_from_skill` 回退全文匹配，易误抓其他百分号表格 → **必须含该标题**。

---

## 三、检测信号定义

### 3.1 `_detect_hpc`（启用判定）
任一类信号即 `is_hpc=True`：
- MPI：`MPI_`、`mpi.h`、`mpif.h`
- OpenMP/线程：`#pragma omp`、`omp_get_`、`pthread_`、`std::thread`、`tbb::`
- GPU：`cuda`/`cudaMemcpy`/`<<<`、`hip`、`cl::`、`#pragma omp target`
- **Kokkos（区分 CPU/GPU 后端）**：GPU 证据 = 源码 `Kokkos::Cuda`/`Kokkos::HIP`/`Kokkos::SYCL`/`CudaSpace`/`HIPSpace`，**或构建文件**（`CMakeLists.txt`/`*.cmake`/`config.h(.in)`）中的 `KOKKOS_ENABLE_CUDA`/`KOKKOS_ENABLE_HIP`/`KOKKOS_ENABLE_SYCL`；**`DEAL_II_WITH_KOKKOS` 单独（恒真）不计为 GPU**，仅 `Kokkos::`（CPU 后端 Serial/OpenMP）也不计。

### 3.2 文件范围
`.c/.cc/.cpp/.cxx/.h/.hpp/.hxx/.cu/.hip`；构建文件 `CMakeLists.txt`/`*.cmake`/`config.h(.in)`（**仅用于 GPU/Kokkos 后端判定，不计入规则扫描**）。排除 `third_party/vendor/external/deps`；**测试/基准默认计入规则扫描**（写死 launch 等由 `@hpc_benchmark_ok` 豁免，而非目录排除）；按路径排序保证确定性。

---

## 四、4 子维与评分

| 子维 | 权重 | 规则赋分 |
|:--|:--:|:--|
| backend_consistency | 30% | HPC-001 30 / HPC-002 30 / HPC-003 10 / HPC-004 30 |
| mpi_halo | 30% | HPC-005 55 / HPC-006 35 / HPC-007 10 |
| load_topology | 20% | HPC-008 95 / HPC-009 5 |
| hybrid_parallel | 20% | HPC-010 40 / HPC-011 35 / HPC-012 25 |

**子维得分** = Σ(未触发规则的赋分)；满分 100。

### 4.1 适用性门控与归一化

| 子维 | 适用条件 |
|:--|:--|
| S1 backend | 有 GPU 信号（含 Kokkos GPU 后端）|
| S2 mpi_halo | 有 MPI |
| S3 load_topology | 有 MPI |
| S4 hybrid | 有 OpenMP/线程（omp/pthread/std::thread/tbb）|

- 不适用子维剔除 → 剩余权重归一化（Σ=1）；全不适用 → `is_hpc=False`。
- `overall = Σ_{适用} score×归一权重`。
> **双重归一化说明**：本引擎归一化仅作用于 HPC 内部子维；HPC 的 `overall` 作为单个维度分再参与 WP-1 顶层激活子集归一化。报告须标 `score_scope=subset`，HPC 子集分不与"全引擎 HPC 分"混比。

---

## 五、12 规则检测实现

| 规则 | 静态信号 | 判定 | 输出 |
|:--|:--|:--|:--|
| HPC-001 | 同函数 `#ifdef __CUDACC__`/`USE_CUDA` 双分支、`_cpu`/`_gpu` 命名对、同文件两套 `forall` 循环、签名/常量差异、无对照测试 | 存在双实现且签名/常量不一致或无对照 → 触发 | WARNING（中低）|
| HPC-002 | GPU 调用点无 `#ifdef`/`omp_get_num_devices`/`cudaGetDeviceCount`/回退 | 无守卫 → 触发 | WARNING（高）|
| HPC-003 | `num_teams(字面量)`/`thread_limit(字面量)`/`<<<N,M>>>` 且未由 N 推导 | 触发 | INFO（中）|
| HPC-004 | `map(`/`cudaMemcpy` 位于循环体；无 `target data`/`enter data` | 触发 | WARNING（中低）|
| HPC-005 | 同作用域 `Isend` 无 `Wait`、Send/Recv 不成对、halo 宽度<stencil | 同作用域缺失 → 触发；跨函数/RAII/异步 → **candidate** | WARNING（中低）|
| HPC-006 | 时间步/迭代循环体内 `Allreduce/Bcast` 且可局部化 | 触发（需复核）| WARNING（中低）|
| HPC-007 | 阻塞 `Send/Recv` 紧邻计算、无 `Isend/Irecv/Sendrecv` | 触发 | INFO（低）|
| HPC-008 | `refine`/`coarsen`/`p4est_refine`、`multiRegion`/`multiMaterial`、`AMR`/`adapt` 信号 + 无 weights 配置 | 无加权且**有上述非均匀信号** → 候选；无加权且无非均匀信号 → 合理等分分区不判 | WARNING（中低）|
| HPC-009 | 多通信域/库占用 `MPI_COMM_WORLD` 无 `Comm_split/Comm_dup` | 触发 | INFO（低）|
| HPC-010 | `omp parallel` 内**直接** `MPI_*`、非 `omp master/single`、`Init<MULTIPLE` | 触发；跨函数 → WARNING/候选 | WARNING（首期）/中 |
| HPC-011 | `omp parallel` 内共享变量写、无 `private/reduction/atomic/critical` | 触发 | WARNING（中低）|
| HPC-012 | `omp` 套 `omp`、并行区内 `std::thread/pthread`、`omp` 内 MPI 无线程守卫 | 触发 | WARNING（中）|

> `candidate` 字段：静态证据不足（跨函数/RAII/异步/非均匀）时为 true；`confirmed` 见 §七。
>
> **count 口径**：`hpc_violations[].count` 为**出现次数**（非文件数），与 GCS 一致。

---

## 六、豁免体系实现

| 通道 | 采集 | 作用 |
|:--|:--|:--|
| `@hpc_benchmark_ok` | 文件头 `/* ... */` | HPC-003 不计数（影响 scoring）|
| `@hpc_deferred` | 文件头 | 降一级（HIGH→WARNING，MEDIUM→INFO），仅 output_level |
| `@hpc_gpu_only` | 文件头 | HPC-002 降 INFO（仅 output_level）|

- reason 必填（首字符非空白）；缺失 → `invalid_waivers` 留痕、豁免无效。
- 同文件作用域；剥离注释前采集。
- 反滥用：三通道合计占比 >30% → `abuse_warning`。
- 降级不改 severity（HIGH 封顶不解除）。

---

## 七、封顶与门禁

- **confirmed 定义**：高置信规则（HPC-002）直接命中 → confirmed；其余命中默认 `candidate`，人工/复核确认后 `confirmed`。
- 引擎输出 `gate_status`：存在 confirmed ERROR → BLOCK；存在 HIGH/MEDIUM → WARN；否则 PASS。
- **封顶对象与落点（P1-1）**：封顶作用于 **HPC 维度子分等级**（**不是项目总分**）；实现在 `arch_report_generator.py` 的 HPC 维度段——`显示等级 = min(grade(HPC 子分), 封顶(confirmed ERROR/HIGH → 需改进))`，并并列提示"项目总分未变，但 HPC 维度受封顶"。
- **与 WP-1 总分关系**：HPC 子分按 WP-1 归一化并入总分；封顶**不回写总分数值**，仅影响 HPC 维度展示等级与门禁状态。
- **HPC-010 首期 WARNING**：gate 为 WARN（不 BLOCK），但 severity HIGH 仍触发 HPC 维度封顶。

---

## 八、集成点（逐文件）

| 文件 | 改动 |
|:--|:--|
| `skills/hpc-architecture.md` | **新建**（4 子维权重表，供 `load_weights_from_skill` 解析）|
| `meta_model_registry.json` | engines 加 `hpc`；加 `dim.hpc`（weight **0.15**、scope project、4 sub_dimensions）；HPC-001~012；schema_version→1.4 |
| `standard_meta_model.schema.json` | rule pattern 加 `HPC` |
| `scripts/validate_meta_model.py` | `RULE_ID_RE` 加 `HPC` |
| `arch_core.py` | `PROFILE_ENGINE_MAP["hpc"]`、`ENHANCEMENT_ENGINES`、`ENH_KEY_TO_DIM["hpc"]` |
| `arch_report.py` | 实例化 HPC、profile/启发式激活、enh 列表、nested+top-level、合并 `hpc_violations` |
| `arch_report_generator.py` | `label_map`/`_ENH_DIM_LABELS` 加 HPC（4 子维）、封顶展示 |
| `scripts/consistency_check.py` | `ENGINES["hpc"]` |
| `scripts/benchmark_h1_engines.py`、`h3_baseline.py`、`weight_sensitivity.py` | 引擎 7→8 |
| `scripts/gen_rule_coverage_matrix.py` | 84→96 |
| `opencode-harness/rules.json` | GPU 信号含 Kokkos 后端；HPC 断言 |
| `projects.yaml` | HPC 样本注册 |
| `scripts/ci_gate_hpc.bat` | CI 门禁脚本（新建）|

---

## 九、测试方案

| 类型 | 内容 |
|:--|:--|
| 单元 | `tests/test_hpc_architecture.py`（12 规则正/负、适用性、豁免、封顶）|
| 变异 | `tests/mutation/`（至少 4 变异：配对/守卫/嵌套/竞争）|
| 集成/E2E | `ComprehensiveReport` 合并 + 报告生成 + 权重归一化 |
| Harness | `opencode-harness` HPC 用例 |
| 回归 | `tests/regression/test_hpc_regression.py` + ≥5 基线（OpenFOAM/deal.II/MFEM/SU2 + 1）|

---

## 十、阶段 4 校准（引擎完成后）

1. 用案例集 A 类（正样本）验证"不应触发/低触发"，C 类负例验证"应触发"；
2. 校准规则赋分、INFO 权重；
3. 实测 HPC-010 误报率 → 决定升 ERROR；
4. 覆盖矩阵双向核对；清 P2（伪代码/商业断言/表述）。

---

## 十一、排期

| 周 | 事项 |
|:--|:--|
| W1 | skill + 引擎骨架 + `_detect_hpc` + 4 子维 + 豁免 |
| W2 | 12 规则检测 + 适用性 + 输出结构 + 单元测试 |
| W3 | 集成点（registry/schema/validator/report/generator/consistency）+ 变异 |
| W4 | 回归 ≥5 + CI + harness + 阶段 4 校准 + 收尾 |

---

## 十二、风险与开放问题

| 风险 | 缓解 |
|:--|:--|
| Kokkos CPU 后端被误判 GPU | 仅 `KOKKOS_ENABLE_CUDA/HIP/SYCL` 计 GPU 信号；`DEAL_II_WITH_KOKKOS` 单独不算 |
| HPC-005 跨函数误报 | 同作用域判违规、跨作用域 candidate |
| HPC-010 误报阻断 | 首期 WARNING；收窄条件 |
| HPC-008 "非均匀迹象"难判 | 仅静态信号 + candidate + TAU/人工 |
| 大仓库扫描性能 | 复用 `_read_cached`/排序/限制文件数 |
| 确定性 | 文件排序、无随机、固定阈值 |

---

*本方案待专家校对后实施；引擎须先建 `skills/hpc-architecture.md`（4 维权重）。*

---

## 版本历史

| 版本 | 日期 | 变更 |
|:-----|:-----|:-----|
| 0.1 | 2026-10-21 | 方案初稿 |
| 0.2 | 2026-10-21 | 专家校对 P1 修订：封顶对象=HPC 维度子分（报告层，不回写总分）；Kokkos 扫构建文件+排除恒真宏；skill 格式定义；HPC-001/008 信号具体化。P2：测试/基准计入+注解豁免、count=出现次数、registry 0.15、ci_gate_hpc.bat、双重归一化说明 |
| 0.3 | 2026-10-21 | HPC dimension id unified to `dim.hpc` (consistent with other dimensions) |
