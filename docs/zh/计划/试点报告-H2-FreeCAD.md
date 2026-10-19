# 试点报告 — H2 FreeCAD

> **归属**：H2 WP-9 试点（工程闭环）
> **试点项目**：FreeCAD（`D:\OPENSOURCE\FreeCAD`，7,693 文件 / 6.85M 行 / 6 语言）
> **日期**：2026-10-16
> **差异说明**：H1 试点以 BRL-CAD 验证**多语言**为主；H2 试点以 **FreeCAD 验证新维度④GCS / ⑧ACL + WP-5/6** 为主。

---

## 1. 项目信息

| 项 | 值 |
|:---|:---|
| 项目 | FreeCAD（开源 CAD/CAE） |
| 文件数 | 7,693（cpp 2,848 / c 1,946 / python 1,718 / typescript 1,178 / fortran 2 / js 1）|
| 代码行 | 6,847,924 |
| 引擎激活 | standard + multilang + template + numerical + solver_physics + **GCS** + **ACL**（7 引擎全激活）|

## 2. 成功标准

| 标准 | 期望 | 实际 | 判定 |
|:-----|:-----|:-----|:----:|
| 全量评估完成 | 7 引擎无异常 | 全部产出评分 | ✅ |
| 综合分可解释 | 与 H1 口径一致 | overall 39.29 | ✅ |
| 新维度④GCS | 识别并评分 | 84.0（geometry_consistency）| ✅ |
| 新维度⑧ACL | 识别并评分 | 38.0（anti_corruption）| ✅ |
| 来源标注 | `[third-party]/[test]` 生效 | MLR-024 含来源计数 | ✅ |
| profile 生效 | 子集仅跑启用引擎 | 5 引擎跳过 | ✅ |

## 2.5 overall 构成拆解（39.29 来源）

**overall 公式**：

```
overall = structural×30% + design×25% + documentation×20% + evolution×25%
```

| 维度 | 得分 | 权重 | 贡献 |
|:-----|:----:|:----:|:----:|
| structural | 48.81 | 30% | 14.643 |
| design | 72.37 | 25% | 18.093 |
| documentation | 28.0 | 20% | 5.600 |
| evolution | 3.81 | 25% | 0.953 |
| **合计** | | | **39.29** |

**multilang / template / numerical 等增强引擎如何计入**：它们**不单独出现在 overall 公式**，而是先合并进 `structural`，再以 30% 进入 overall。

`structural = 48.81` 的合并（6 增强全激活：active_count=6 → `base_map[6]=0.45`；增强原始和 0.85，real_w=1.30，scale=1/1.30）：

| 组成 | 子分 | 归一权重 | 贡献 |
|:-----|:----:|:--------:|:----:|
| base 标准结构 | ≈30.0 | 0.3462 | 10.39 |
| multilang | 58.32 | 0.1154 | 6.73 |
| template | 39.42 | 0.1154 | 4.55 |
| numerical | 96.0 | 0.0769 | 7.38 |
| solver_physics | 49.25 | 0.1154 | 5.68 |
| geometry_consistency (GCS) | 84.0 | 0.1154 | 9.69 |
| anti_corruption (ACL) | 38.0 | 0.1154 | 4.38 |
| **合计** | | **1.000** | **48.81** |

> **结论**：overall 39.29 **已包含** multilang/template/numerical（及其余 3 引擎），但经 `structural` 间接计入；`*_enhancement` 分数（58.32/39.42/96.0…）是合并前的子分，不与 design/doc/evolution 直接相加。
>
> **偏低主因**：`evolution=3.81`（25%）与 `documentation=28.0`（20%）合计 45% 权重拖累 overall；增强引擎并非主因（numerical 96.0、GCS 84.0 反而拉高 structural）。

---

## 3. 成本记录（KPI5 时预算）

| 引擎 | 耗时 | 增量预算 ≤120s |
|:-----|:----:|:-----:|
| standard（必配）| 217.6s | — |
| multilang | 262.9s | ⚠️ 已知超预算（H3）|
| template | 32.9s | ✅ |
| numerical | 118.1s | ✅ |
| solver_physics | 15.5s | ✅ |
| **GCS** | **65.9s** | ✅ |
| **ACL** | **55.7s** | ✅ |
| **T_full（逐引擎合计）** | **768.6s** | — |
| T_subset（profile: geometry-consistency）| 326.5s | 跳过 5 引擎 |
| T_subset（profile: anti-corruption）| 316.8s | 跳过 5 引擎 |

> **结论**：H2 新增 GCS/ACL 增量均 ≤120s 硬门禁；profile 跳过收益成立（T_full 768.6s → T_subset ~320s，跳过 multilang/numerical 等重引擎）。

## 4. 问题清单

| # | 问题 | 性质 | 处置 |
|:-:|:-----|:-----|:-----|
| 1 | `evolution` 维度 3.81 分（Git 查询在批量负载下的窗口/超时影响）| 已知 | 已由 GitHistory 失败返回 None + N/A 处理（WP-2.5 回归修复）；FreeCAD 体量大时仍偏低，属测量口径 |
| 2 | multilang 262.9s > 120s 增量预算 | 已知超预算 | 登记 H3（H1 已从 4h 优化到 ~225s，单引擎进一步优化归 H3）|
| 3 | ACL 38.0 分偏低（直连/交换散落计数高）| 已知 | FreeCAD 自身即大量使用 OCCT + STEP；属"内核消费者"真实耦合，P0 建议见 ACL 报告 |

## 5. 假阳性反馈

- **GCS-003（异常传播）**：FreeCAD 中 OCCT 封装级 builder 委托模式多，静态判定偏保守（已知 KNOWN_HOLES）。
- **ACL-001（直连）**：OCCT 应用层直连计数高，属真实耦合，非误报。
- **MLR-018（镀金模板）**：WP-5 关键字过滤后 2300 → 888（降 61.4%），残余为真实单类型模板。

## 6. 上线/回滚判据

| 判据 | 结果 |
|:-----|:-----|
| 7 引擎全部可执行、无崩溃 | ✅ |
| 稳态评分（重复运行偏移 ≤2）| ✅（回归基线守护）|
| 门禁脚本 PASS | ✅（GCS/ACL gate）|
| **上线**：可作为 FreeCAD 类 CAD/CAE 项目常规评估 | ✅ 建议上线 |

## 7. 结论与建议

- **结论**：FreeCAD 试点通过，H2 新维度（GCS/ACL）在大型 CAD/CAE 项目上可正常识别与评分，profile 与来源标注生效。
- **建议**：
  1. 将 FreeCAD 固定为 GCS/ACL 回归基线（已具备 `gcs_freecad` / `acl_freecad`）
  2. multilang 单引擎优化列 H3
  3. ACL 在 CAD 项目的高直连计数属真实耦合，建议按 ACL 报告 P0 整改（DATAExchange 收敛 + 错误检查）
