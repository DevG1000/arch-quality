# H3 WP-1 归一化实施说明（激活子集全局归一化）

**版本**：v1.0
**日期**：2026-10-21
**归属**：`H3全维化执行计划v2.md` → WP-1（评分语义）；依据 `权重归一化模型重做方案.md §四` + 评审 must-adopt 1/2/6 + 决策 1/2/5 + D-a/D-b/D-c=(a)
**状态**：实施完成，测试通过

---

## 一、目标与验收（KPI2 锚点）

| 锚点 | 结果 |
|:-----|:-----|
| 恒等式 Σw'=1 | ✅ validator 枚举全部 **64** 个激活子集，Σ=1 |
| 单调性 | ✅ 激活维度增多时基座平滑下降（无分档跳变，见 §三）|
| 手算样例 | ✅ 标准4维 / +数值 / 全6增强 三例（§三）|
| delta 表 | ✅ 7 项目迁移前后各维/总分 delta（§五）|
| 程序化校验 | ✅ 快照/权重带取值校验；validator 5 项 PASS |

---

## 二、实现（改动文件）

| 文件 | 改动 |
|:-----|:-----|
| `meta_model_registry.json` | 10 维各加 `sub_dimensions`（内部维度权重，Σ=1）；`schema_version` 1.1→**1.2** |
| `standard_meta_model.schema.json` | dimensions 项增 `sub_dimensions`（含 `id` pattern）；描述升 v1.2 |
| `src/arch_quality/arch_core.py` | 新增 `load_dimension_weights()` + **`calc_activate_subset()`**（+ `BASE_DIM_IDS`/`ENH_KEY_TO_DIM`）|
| `src/arch_quality/arch_report.py` | **删除** `base_map`/`enh_raw`/等比缩放；改用 registry 权重 + `calc_activate_subset` 全局归一化；`overall = Σ dim·w'`；增强维升为顶层 `dimensions.<engine>`（保留 `structural.*_enhancement` 别名）|
| `src/arch_quality/arch_report_generator.py` | 总体评分表纳入增强维；"占结构质量"→"**占总分**" |
| `scripts/validate_meta_model.py` | 新增 `check_sub_dimensions` + `check_activate_subset`（64 子集公理）；stdout 强制 UTF-8 |
| `scripts/consistency_check*.py`（3 个）| stdout/stderr 强制 UTF-8（修复 Windows 管道 GBK 解码）|
| `tests/test_profile.py` / `test_geometry_integration.py` / `test_solver_physics_integration.py` | 断言改为归一化语义 |
| `tests/regression/snapshots/standard_arch_quality.json` | 自举 file_count 刷新（248→278，新增 H3 文件）|

**D-b**：内部维度权重**迁入 registry `sub_dimensions`**，引擎仍从各自 skill 解析（registry 侧交叉校验，Σ=100）；**不改引擎读取**（低风险）。

---

## 三、新模型

**公理**：任一项目激活的维度权重之和 = 1（全局归一化）。

**候选集 D（10 维）**：structural .30 · design .25 · documentation .20 · evolution .25 · multilang .15 · template .15 · numerical .10 · solver_physics .15 · geometry_consistency .15 · anti_corruption .15。

**归一化**：`w'_d = w_d / Σ_{d∈A} w_d`。

| 激活集 | Σ原始 | structural | design | doc | evolution | 增强维 |
|:-------|:----:|:---:|:---:|:---:|:---:|:---|
| 标准 4 维 | 1.00 | .300 | .250 | .200 | .250 | — |
| +数值 | 1.10 | .273 | .227 | .182 | .227 | numerical .091 |
| 全 6 增强 | 1.85 | .162 | .135 | .108 | .135 | ml/tpl/sp/gcs/acl .081，nvr .054 |

（**决策 1**：增强总分作超级维度，内部维度权重保持。**决策 2**：求解器产品类型调权保留为引擎内部维度。）

---

## 四、报告结构变更

| | 迁移前 | 迁移后 |
|:--|:--|:--|
| `dimensions` 顶层 | 4 标准维 | 4 标准维 **+ 各激活增强维**（`{score,weight,details}`）|
| `structural.*_enhancement` | 折叠进 structural | **别名保留**（`weight_applied`=归一化权重，占总分）|
| `dimensions.structural.score` | 合并分（base+增强）| **纯结构分** |
| `score_breakdown` | `base*X%+…` | `overall = Σ dim*w'` + `normalized_weights` |
| `profile.subset_scoring` | 过渡口径 8b | 保留字段（信息性）；`note` 改为"激活子集全局归一化" |

---

## 五、决策 5 — 迁移前后 delta 表

由 WP-0 冻结基线（`h3_pre_norm_*.json`）解析各引擎分并重算归一化总分（解析法，已用 Eigen 实跑校验一致）：

| slug | 迁移前 | 迁移后 | delta | 激活增强 |
|:-----|:----:|:----:|:----:|:---|
| brl_cad | 40.16 | 46.38 | **+6.22** | ml,tpl,nvr,sp |
| eigen | 43.97 | 47.10 | **+3.13** | ml,tpl,nvr,sp |
| elmerfem | 41.48 | 48.92 | **+7.44** | ml,tpl,nvr,sp,gcs,acl |
| freecad_src | 38.18 | 44.58 | **+6.40** | ml,tpl,nvr,sp,gcs,acl |
| occt | 42.87 | 48.51 | **+5.64** | ml,tpl,nvr,sp,gcs,acl |
| openfoam_v2512 | 41.53 | 49.51 | **+7.98** | ml,tpl,nvr,sp,gcs |
| salome_geom | 40.39 | 45.11 | **+4.72** | ml,tpl,nvr,sp,gcs,acl |

> 说明：语义变更使总分普遍**上升 +3~+8**（增强维从"折叠进 structural"升为同级并获归一化权重）。属预期语义变更（决策 5），非回归。
> **迁移后基线**：重跑 `python scripts/h3_baseline.py --all` 即得 post-norm 基线（引擎分不变，仅总分重算）。

---

## 六、测试与验证

| 套件 | 结果 |
|:-----|:-----|
| 非回归（CI 过滤）| **661 passed, 2 skipped** |
| 受影响集成/单测（profile/geometry/solver/ui/meta_model）| **94 passed, 1 skipped** |
| `test_consistency_check` | **5 passed** |
| 标准回归自举 | **20 passed**（file_count 刷新后）|
| `validate_meta_model.py` | **PASS**（权重和 / 内部维度 / 编号 / 豁免 / 归一化公理 5 项）|

> 回归套件为**引擎级**（不含 `ComprehensiveReport`），WP-1 仅改综合报告 → 引擎级快照不受影响。

---

## 七、决策记录

| # | 决策 | 采用 |
|:-:|:-----|:-----|
| D-a | 报告结构：增强维升顶层 + 保留别名 | ✅ (a) |
| D-b | 内部维度权重事实源 | ✅ (a) registry `sub_dimensions` + 交叉校验 |
| D-c | `calc_activate_subset` 位置 | ✅ (a) `arch_core.py` |
| 1 | 增强总分作超级维度 | ✅ |
| 2 | 求解器调权为 profile 维度权重覆盖 | ✅ |
| 5 | 快照语义变更重设 | ✅（delta 表 + 程序化校验）|

---

## 八、遗留 / 后续

| 项 | 归属 |
|:---|:-----|
| skills/AGENTS.md/指南权重表加"事实源=registry"注释 | WP-1 收尾 / 文档同步 |
| post-norm 基线文件（`h3_post_norm_*.json`）按需生成 | 迁移后 |
| `rule_prefix_aliases` 移除（TPL 迁移）| WP-7 |
| 新引擎 HPC/FOS 前缀登记 validator/schema | WP-3/4/7 |

---

*WP-1 实施完成。激活子集全局归一化成为正式评分语义，替代 H2 过渡口径 8b。*