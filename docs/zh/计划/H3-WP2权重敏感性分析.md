# H3 WP-2 权重敏感性分析

**版本**：v1.0
**日期**：2026-10-21
**归属**：`H3全维化执行计划v2.md` → WP-2；方法依评审意见 14（敏感性分析 + 专家定案，非 LOOCV）
**状态**：完成（供决策门使用）

---

## 一、方法

- **OAT（one-at-a-time）网格扫描**：6 个增强维权重逐个取网格 `{0.05, 0.08, 0.10, 0.12, 0.15, 0.20}`，标准 4 维冻结。
- **数据**：WP-0 冻结基线 `h3_pre_norm_*.json`（7 项目 per-dim 得分）。per-dim 与权重无关 → 零成本重算综合分。
- **指标**：`max|Δoverall|`、排名 Kendall τ（vs 基线）、等级变化数（阈值 85/70/50）、**稳定区间**（τ=1 且等级不变）。
- 脚本：`scripts/weight_sensitivity.py` → `baseline_data/h3_wp2_sensitivity.json`。

## 二、基线（当前 registry 权重）

| 项目 | overall | 等级 | 激活增强 |
|:-----|:------:|:--:|:---|
| openfoam_v2512 | 49.51 | D | ml,tpl,nvr,sp,gcs |
| elmerfem | 48.92 | D | ml,tpl,nvr,sp,gcs,acl |
| occt | 48.51 | D | ml,tpl,nvr,sp,gcs,acl |
| eigen | 47.10 | D | ml,tpl,nvr,sp |
| brl_cad | 46.38 | D | ml,tpl,nvr,sp |
| salome_geom | 45.11 | D | ml,tpl,nvr,sp,gcs,acl |
| freecad_src | 44.58 | D | ml,tpl,nvr,sp,gcs,acl |

> 7 项目整体聚在 44.6~49.5（等级 D），语料同质（CAE），**区分度有限** → 敏感性结论作参考，专家主导。

## 三、逐维敏感性

| 维度 | 现行 | 稳定区间 | 0.05 | 0.08 | 0.10 | 0.12 | 0.15 | 0.20 | 关键性 |
|:-----|:---:|:---:|:--:|:--:|:--:|:--:|:--:|:--:|:--|
| multilang | 0.15 | **[0.08,0.15]** | τ.91 | ✅ | ✅ | ✅ | ✅ | gΔ1 | 中（极值敏感）|
| template | 0.15 | **[0.08,0.20]** | τ.71 | ✅ | ✅ | ✅ | ✅ | ✅ | 低（0.05 外）|
| **numerical** | **0.10** | **[0.08,0.10]** | τ.91 | ✅ | ✅ | **gΔ1** | **gΔ2** | **gΔ3** | **高** |
| solver_physics | 0.15 | **[0.12,0.20]** | gΔ1 | τ.91 | τ.91 | ✅ | ✅ | ✅ | 中 |
| geometry_consistency | 0.15 | **[0.08,0.15]** | τ.91 | ✅ | ✅ | ✅ | ✅ | gΔ1 | 中 |
| anti_corruption | 0.15 | **[0.05,0.20]** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **低（非关键）**|

（✅=稳定；τ=Kendall 相关系数；gΔ=等级变化项目数；max|Δoverall| 见 JSON）

## 四、结论

1. **numerical 最敏感**：0.10→0.15 致 2 个项目等级变化、→0.20 致 3 个；**上调 destabilizes**。现行 **0.10 位于稳定区间上界**，维持更稳。
2. **template / anti_corruption 非关键**：全网格结论不变 → 取值自由度大。
3. **multilang / solver / geometry 中等**：仅极值敏感（ml 0.05、sp 0.05、gcs 0.20）。
4. **现行 6 值全部落在各自稳定区间内** → 数据支持**维持现行权重**（不因数据证据要求上调/下调）。
5. 语料区分度低（全 D 级）→ 权重对"结论"影响有限；定案应以**先例一致性 + 专家判断**为主。

---

*数据：`baseline_data/h3_wp2_sensitivity.json`；脚本：`scripts/weight_sensitivity.py`。*