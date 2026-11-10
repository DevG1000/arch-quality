# H3 WP-0 基线实测量化方案

**版本**：v1.0
**日期**：2026-10-20
**归属**：`H3全维化执行计划v2.md` → WP-0（前置，W1–W2）
**状态**：实施中。含 **G0 门禁**（运行时 CI 可行性），B2/B3/B5 归属由实测数据决定（决策 4：先做 T0.6 再定）

---

## 一、目标与验收

| 项 | 内容 |
|:---|:-----|
| **目标** | 产出 H3 全部工作包依赖的**可复现"归一化前"基线**；对**运行时检测 CI 可行性**（决策 3 前置）给出明确结论 |
| **产出** | `docs/zh/计划/H3基线实测报告.md` + 归档 JSON |
| **验收** | ① 7 引擎 × 7 项目基线可复现（同 commit + 样本 ref 重复跑一致）；② 冻结"归一化前"各维分数（供 WP-1 delta 表，决策 5）；③ **G0 可行性结论 + 回退预案** |

---

## 二、前置条件（已核实，2026-10-20）

| 项 | 值 |
|:---|:---|
| 机器 | Windows-10-10.0.18363-SP0 / AMD64 |
| Python（本地）| **3.14.3**（CI 矩阵为 3.10/3.11/3.12，构成跨环境数据点）|
| git HEAD | `54ba911` |
| arch_quality | 可导入（editable，`D:\opensource\arch-quality\src\arch_quality`）|
| 本地 cmake | **未安装**（T0.6 的本地试构受限，以 CI 评估为准）|
| 样本 | FreeCAD/BRL-CAD/ElmerFEM/OpenFOAM-v2512/Eigen/dealii 在 `D:\OPENSOURCE\`；**OCCT/salome-geom 在 `D:\OPENSOURCE\gcs-baselines\{occt,salome-geom}`** |
| 可复用工具 | `benchmark_h1_baseline.py`（ComprehensiveReport 计时+冷缓存+P90）、`benchmark_h1_engines.py`（分引擎）、`fetch_project.py`（校验和）、`tests/regression/snapshots/*.json` |

---

## 三、任务分解

| 任务 | 内容 | 复用/新工具 | 产出 |
|:-----|:-----|:-----------|:-----|
| **T0.1 环境与样本冻结** | 记录 machine/commit；`fetch_project.py --check-all` 校验 occt/salome | `fetch_project.py` | 环境快照段 |
| **T0.6 运行时 CI 可行性（Gate G0）** | 评估 ubuntu-latest 构建 OCCT：apt 预编译 vs CMake 源码 vs 自托管；实测/估算耗时；回退矩阵 | CI + 证据 | G0 结论 + 回退预案 |
| **T0.2 归一化前语义基线（核心）** | 7 项目 × 全 7 引擎 `python -m arch_quality <path> --json`，记 overall + 各维 + 各引擎 overall + 违规计数；**冻结归档** | `arch_quality` CLI | `baseline_data/h3_pre_norm_<slug>.json` ×7 |
| **T0.3 multilang 性能基线** | 复现 FreeCAD src 262.9s；分引擎计时含 GCS/ACL；冷/热缓存 P50/P90 | `benchmark_h1_engines.py`（扩 7 引擎）| per-engine timing JSON |
| **T0.4 ACL CAD 直连计数基线（G4）** | FreeCAD import 模块 + salome-geom STEPPlugin/IGESPlugin/BREPPlugin 的 ACL-001/007 目录级计数 | ACL 引擎 + 快照 | ACL CAD 计数表 |
| **T0.5 语义级语料基线（B1/B4）** | OCCT GCS-003（快照=39 vs 待办=40，核对）BRepFeat/BRepFill/CheckAndLoad 分布；deal.II MLR-018 隐式实例化计数 | 快照 | 语料基线表 |
| **T0.7 跨环境铺垫** | 记录 OS/Python；复用 CI 3.10/3.11/3.12 matrix | — | 环境矩阵记录 |

---

## 四、Gate G0 — 运行时 CI 可行性（决策 4：先做再定）

**背景**：决策 3 要求实施 B2/B3/B5（欧拉公式 / B-Rep 闭合 / ACL 内核升级兼容），均需**构建并运行 OCCT 内核**。CI 为 ubuntu-latest。

**候选方案**

| 方案 | 做法 | 关注点 |
|:-----|:-----|:-------|
| A. apt 预编译 | `libocct-*`（Ubuntu 仓库）| **版本可能非 V8.0.1** → B2/B3 语义保真风险 |
| B. CMake 源码构建 | 构建 OCCT V8.0.1（对齐样本 ref）| 耗时可能 30–90 min，需缓存 |
| C. 自托管/缓存 | 预构建 artifact 缓存或 self-hosted runner | 成本/维护 |

**判定规则**

```
T0.6 可行（构建 ≤ 阈值 且 版本可对齐） → 按决策 3 实施 B2/B3/B5（WP-5 动态子包）
T0.6 不可行                            → 触发回退重决：① 永久 KNOWN_HOLES ② 自托管专用 job ③ 仅静态子集
```

**产出**：可行性结论 + 实测/估算构建耗时 + 回退矩阵 + **G0 建议**。

---

## 五、需要的工具改造（WP-0 范围内）

1. **`benchmark_h1_engines.py` 扩 5→7 引擎**：加 `GeometryConsistencyMetrics`、`AntiCorruptionMetrics`。
2. **`benchmark_h1_baseline.py` 去硬编码**：`DEFAULT_PROJECTS` 的 `D:\OPENSOURCE\...` 绝对路径 → 改为 CLI/`projects.yaml` 驱动，保证跨机可复现。
3. （可选）新增 `scripts/h3_baseline.py`：一条命令产出 T0.2 + T0.3 聚合基线。

---

## 六、交付物

- `docs/zh/计划/H3基线实测报告.md`（对齐 `H1基线实测报告.md` 格式，含 G0 结论章节）
- `docs/zh/计划/baseline_data/h3_pre_norm_<slug>.json`（7 项目，冻结）
- per-engine timing JSON（含 GCS/ACL）
- ACL CAD 计数基线表 / 语义语料基线表（B1/B4）
- G0 可行性结论 + 回退矩阵 + 建议
- 工具改造提交

---

## 七、排期（2 周）

| 周 | 任务 |
|:---|:-----|
| W1 | T0.1 冻结 → **T0.6（G0，最先）** → T0.2 语义基线 → T0.3 性能基线（含脚本扩 7 引擎）|
| W2 | T0.4 ACL 计数 → T0.5 语料 → T0.7 → 报告 + G0 结论 |

---

## 八、风险与开放点

| 风险 | 缓解 |
|:-----|:-----|
| **OCCT 在 CI 构建不可行**（决策 3 关键）| T0.6 给三方案 + 回退矩阵；不可行时触发重决（选项 1/2/3）|
| benchmark 脚本硬编码（5 引擎 / Windows 绝对路径）| 纳入 WP-0 工具改造 |
| 冷缓存模拟 `_evict_file_cache` 为 Windows ctypes，Linux CI 不适用 | 跨平台分支 / 仅本地冷缓存基线 |
| OCCT/SALOME 路径在 `gcs-baselines\` 而非 `D:\OPENSOURCE` 根 | 报告明确路径约定，`fetch_project.py --dest` 对齐 |
| GCS-003 OCCT 快照=39 vs 待办=40 | T0.5 以实测为准并登记差异 |
| 本地 Python 3.14 vs CI 3.10–3.12 | 记录为跨环境数据点（供 WP-11）|

---

## 九、对下游的联动

- **WP-5**：动态子包（B2/B3/B5）计划保留但标记"G0 门控"；G0 未定前不动工动态部分，B1/B4/B6/B7 可先做。
- **H3 计划 v2**：G0 若回退 → 追加决策记录 + KPI3 改写 → 升 **v2.1**。
- **缓冲 W17–W20**：G0 回退时省下的运行时工作量优先补给 WP-4。

---

*本方案由 H3 全维化执行计划 v2 §三 WP-0 展开，决策 4（先做 T0.6 再定）已固化。*