# H3 WP-2 权重定案工作底稿

**版本**：v1.0
**日期**：2026-10-21
**归属**：WP-2 → 决策门（step 4）
**状态**：**已确认（选项 1：维持现行 6 值 + scope 分配）**，step 5-6 已完成
**依据**：`H3-WP2权重敏感性分析.md`

---

## 一、定案范围

- **定案**：6 个增强维（multilang / template / numerical / solver_physics / geometry_consistency / anti_corruption）。
- **冻结**：标准 4 维（structural .30 / design .25 / documentation .20 / evolution .25），源自《架构质量评估指南 2.3》。

## 二、决策矩阵

| 维度 | 现行候选 | 稳定区间 | 敏感性 | H1/H2 先例 | **提议定值** | 理由 |
|:-----|:---:|:---:|:--:|:---|:---:|:---|
| multilang | 0.15 | [0.08,0.15] | 中 | 0.15 | **0.15** | 先例值在稳定区间；极值(<0.08/>0.15)才失稳 |
| template | 0.15 | [0.08,0.20] | 低 | 0.15 | **0.15** | 非关键，取先例 |
| numerical | 0.10 | [0.08,0.10] | 高 | 0.10 | **0.10** | 上调致等级变化，维持更稳 |
| solver_physics | 0.15 | [0.12,0.20] | 中 | 0.15 | **0.15** | 稳定区间内 |
| geometry_consistency | 0.15 | [0.08,0.15] | 中 | 候选 0.10~0.15 | **0.15** | 稳定区间上界；备选 0.12（留裕度，见 §三）|
| anti_corruption | 0.15 | [0.05,0.20] | 低 | 候选 0.10~0.15 | **0.15** | 非关键，取先例 |

> **总体提议**：**维持现行 6 值**（数据未要求调整）。定案价值在于：确认单一事实源 + 记录稳定区间 + 标注关键性。

## 三、备选（若专家偏好裕度）

| 维度 | 备选值 | 说明 |
|:-----|:---:|:---|
| geometry_consistency | 0.12 | 0.15 处稳定区间上界（0.20 失稳）；降到 0.12 留裕度（仍在 [0.08,0.15]）|
| numerical | 0.08 | 稳定区间下界，更保守 |

## 四、scope 字段分配（Q3=a）

按元模型 §2.3 `scope: global|project`：

| 维度 | scope | 含义 |
|:-----|:--:|:---|
| standard 4 维 | `global` | 常激活基础维度（指南固定分布）|
| 6 增强维 | `project` | 按项目激活（进入激活子集归一化）|

> 注：WP-1 后**所有**维度均参与激活子集全局归一化；scope 仅标注"权重角色"（基础 vs 激活）。

## 五、确认清单（专家拍板）

- [ ] 6 增强维提议定值 = **维持现行**（ml/tpl/sp/gcs/acl=0.15，nvr=0.10）？或采用 §三 备选？
- [ ] `scope` 分配（standard=global，增强=project）？
- [ ] `schema_version` 1.2→1.3 + registry 写入？

## 六、确认后将执行

1. 写回 `meta_model_registry.json`：6 维定值 + 全 10 维 `scope`；`schema_version`→1.3。
2. `standard_meta_model.schema.json` 增 `scope` 枚举；`validate_meta_model.py` 校验 scope。
3. 复跑 `validate_meta_model.py` + 非回归测试；若权重未变则基线不变。

---

*待确认后，WP-2 收尾（step 5-6）。*

---

## 七、确认与执行记录（2026-10-21）

**专家确认**：选项 1 —— 维持现行 6 个增强维权重（ml/tpl/sp/gcs/acl=0.15，nvr=0.10）+ scope 分配（standard=global，增强=project）。

**执行结果**

| 步骤 | 结果 |
|:-----|:-----|
| registry 写入 scope + `schema_version` 1.2→1.3 | ✅ 10 维 scope 落库，权重不变 |
| schema 增 `scope` 枚举（required）| ✅ `standard_meta_model.schema.json` v1.3 |
| `validate_meta_model.py` 增 `check_scope` | ✅ 6 项校验全 PASS |
| 非回归测试（CI 过滤）| ✅ **661 passed, 2 skipped**（权重未变 → 基线不变）|

**定案值**：multilang 0.15 · template 0.15 · numerical 0.10 · solver_physics 0.15 · geometry_consistency 0.15 · anti_corruption 0.15。

---

*WP-2 完成。权重收敛为单一事实源（registry v1.3），并登记稳定区间与关键性。*
