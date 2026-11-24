# H3 WP-5 语义级检测补齐方案

> **版本**：1.0（已收口）
> **日期**：2026-11-24
> **归属**：`H3全维化执行计划v2.md` §三 WP-5（B1~B7）
> **上游**：`H3待办清单.md` B1~B7、`H3-G0运行时内核CI方案.md`、`规则统一编码方案WP7-1.md`
> **目标**：按决策 3 实施 B2/B3/B5 运行时检测；按决策 6 保持 B7 为 KNOWN_HOLES 并文档化；清理 B6 静态空洞；提升 B1/B4 语义检测准确性且不劣化假阳性

---

## 0. 任务边界

WP-5 承接 7 项遗留：

| 项 | 名称 | 类型 | 决策/口径 |
|:--|:--|:--|:--|
| B1 | 隐式实例化全语义（真实调用图 / 跨 TU 实例化追踪）| 静态增强 | 实施；不得劣化现有模板维度假阳性 |
| B2 | GCS 欧拉公式约束（V−E+F 拓扑不变量）| 运行时 | 实施；挂 `runtime-kernel` 非阻塞 job |
| B3 | B-Rep 闭合性运行时判定 | 运行时 | 实施；挂 `runtime-kernel` 非阻塞 job |
| B4 | GCS-003 跨函数失败传递 + builder 委托（OCCT 40 处）| 静态增强 | 实施；语义级/调用图 |
| B5 | ACL 内核升级 API 影响面兼容测试 | 运行时 | 实施；跨版本构建对比 |
| B6 | NVR-009 / MPR-011 规则实现 | 静态补位 | 实施；规则 ID 已存在于 registry，需实现检测并移出 KNOWN_HOLES |
| B7 | GCS-013/014、ACL-013 | 静态/裁决 | **保持 KNOWN_HOLES**（决策 6），文档化“静态不可判” |

> HPC-013/014、FOS-013/014 不在本 WP 范围，保持各自 KNOWN_HOLES。

---

## 1. 总体技术路线

两条轨道：

### 轨道 A：静态增强（B1/B4/B6/B7）

- 不改现有维度权重/规则数量；
- 扩展已有引擎的检测逻辑、证据字段与 candidate 判定；
- 以“不得劣化假阳性”为硬约束，新规则默认 candidate/INFO，人工确认后才进入门禁；
- B7 不改代码，只补报告与文档中的 KNOWN_HOLES 审计展示。

### 轨道 B：运行时检测（B2/B3/B5）

依托 G0 已落地的基础设施：`scripts/ci/build_occt.sh`、`scripts/ci/run_kernel_smoke.sh`、`scripts/ci/kernel_smoke.cpp`、`.github/workflows/arch-quality-ci.yml` 的 `runtime-kernel` job（schedule + workflow_dispatch，非阻塞）。

G0 结论：**方法 C（预构建缓存）+ 专用 job**；本地 Windows 无 cmake，实际构建须在 CI 验证。

---

## 2. 分阶段实施

### 阶段 0：G0 运行时底座实测（前置）

| 动作 | 内容 |
|:--|:--|
| 触发 CI | `workflow_dispatch` 运行 `runtime-kernel` job |
| 验证点 | OCCT 版本 = 8.0.1；box valid=true faces=6；缓存命中后耗时 |
| 产出 | CI 运行日志链接 + 构建耗时记录 |
| 风险回退 | 若构建失败/超时，按 G0 方案回退为“静态子集 + KNOWN_HOLES 明确归属”，并升 H3 计划 v2.1 |

> 阶段 0 是 B2/B3/B5 的前置；B1/B4/B6/B7 不依赖它，可并行启动。

### 阶段 1：静态增强与补位（B1/B4/B6/B7）

#### B1 隐式实例化全语义

- 现状：模板维度 TPL-006（原 MLR-018）当前为窄定义“虚泛型”检测；本项扩展到真实调用图/跨 TU。
- 方案：读取 `compile_commands.json`（若存在）获取 TU 与编译参数；用 clang AST 提取模板实例化、specialization、实例化上下文；无 compile DB 时回退现有静态信号并输出 `candidate=true`；与 TPL-006 合并去重；对 12 个模板回归项目做假阳性对比。
- 验收：至少 1 个“跨 TU 实例化”合成用例；TPL 回归 84 tests 不劣化。

#### B4 GCS-003 跨函数失败传递 + builder 委托

- 现状：GCS-003 检测 `IsDone` 缺失等失败状态传播；跨函数/封装/委托漏报（OCCT 40 处 BRepFeat/BRepFill/CheckAndLoad）。
- 方案：构建轻量调用图（定义 → 调用点 → 返回值/状态检查）；识别 builder/delegate 模式（`Perform`/`Build`/`CheckAndLoad` + `IsDone()`）；跨函数路径无状态检查则输出 candidate + `file:line` 调用链；与现有 GCS-003 合并避免双扣。
- 验收：OCCT 样本抽检至少识别已知模式子集；GCS 回归不劣化。

#### B6 NVR-009 / MPR-011 规则实现

| 规则 | registry 现状 | 实现方案 |
|:--|:--|:--|
| NVR-009「确认绝热等级」 | LOW / INFO / waivable=false | 静态检测求解器配置中时间积分/热平衡配置；无证据时输出 INFO 提示“需运行时/配置确认”，不参与评分；从 KNOWN_HOLES 移出但保留 INFO 语义 |
| MPR-011「跨场时域同步规范」 | MEDIUM / WARNING / waivable=false | 检测多物理场模块中时间步长/时间步循环/同步点：多场共存且无同步/对齐信号 → candidate WARNING；阈值阶段内校准 |

同步更新：数值/物理场引擎、指南、Skill、案例集、快照、`consistency_check.py` KNOWN_HOLES；coverage matrix 仍 108/108（ID 已存在）。

#### B7 KNOWN_HOLES 文档化

- GCS-013/014、ACL-013 保持 KNOWN_HOLES（决策 6）；
- 报告输出 `known_holes_audit` 或等价字段，说明“静态不可判/需运行时/需外部标准”；
- 更新 GCS/ACL 指南与 Skill 的 KNOWN_HOLES 段落；registry 保留条目；consistency_check 保留 KNOWN_HOLES。

### 阶段 3：验证与收口

| 验证项 | 标准 |
|:--|:--|
| 静态 | B1/B4/B6 有单元/变异用例；B7 有 KNOWN_HOLES 审计输出 |
| 运行时 | B2/B3 至少 1 次 CI 实测；B5 跨版本对比或 `skipped_reason` |
| 一致性 | `validate_meta_model.py`、`consistency_check --engine all` PASS |
| 覆盖 | 108/108 不变 |
| 回归 | 模板/GCS/数值/物理场/ACL 回归不劣化 |
| 文档 | `H3closeout报告.md` 汇总 KPI3 证据 |

---

## 3. 交付物清单

| 文件 | 归属 |
|:--|:--|
| `scripts/ci/runtime_checks.cpp` / `scripts/aggregate_runtime_checks.py` | 运行时底座 |
| `docs/zh/计划/H3-WP5运行时检测报告.md` | B2/B3/B5 证据 |
| `src/arch_quality/arch_metrics_template.py` 扩展 | B1 |
| `src/arch_quality/arch_metrics_geometry_consistency.py` 扩展 | B4 |
| `src/arch_quality/arch_metrics_numerical_accuracy.py` / `arch_metrics_solver_physics.py` | B6 |
| 对应指南/Skill/案例集/快照 | B1/B4/B6/B7 |
| `scripts/consistency_check.py` | B6 KNOWN_HOLES 清理 |
| `docs/zh/计划/H3-WP5语义级检测补齐报告.md` | 总报告 |

---

## 4. 决策点（D1~D5 已确认）

| # | 决策 | 建议 |
|:-:|:--|:--|
| D1 | NVR-009 是否仅 INFO 不评分？ | 是；保持 registry severity LOW / INFO，只做提示 |
| D2 | MPR-011 candidate WARNING 阈值？ | 多场共存且无同步信号即触发；阶段内校准 |
| D3 | B1 无 compile DB 时是否只输出 candidate？ | 是；不劣化假阳性 |
| D4 | B2/B3/B5 CI 构建失败时回退？ | 采用 G0 回退：静态子集 + KNOWN_HOLES 文档化，升 H3 计划 v2.1 |
| D5 | B7 是否保持 KNOWN_HOLES？ | 是（决策 6 已定） |

---

## 5. 风险与缓解

| 风险 | 缓解 |
|:--|:--|
| 跨 TU AST 成本高/compile DB 缺失 | 回退静态信号 + candidate；只增量分析 |
| GCS-003 调用图误报 | 限定 builder 模式 + 证据链；candidate 不直接 ERROR |
| OCCT CI 构建失败 | G0 回退选项；非阻塞 job |
| 跨版本构建不可用 | B5 输出 skipped_reason，不阻断 |
| NVR-009/MPR-011 新规则误报 | INFO/candidate 先行；回归校准 |
| 108/108 被破坏 | 使用现有 ID，不新增编号；validator 强制校验 |

---

## 6. 建议执行顺序

1. **用户确认 D1~D5**；
2. 阶段 0：触发 `runtime-kernel` CI，验证 G0 底座；
3. 阶段 1：B6 → B7 → B4 → B1（静态优先）；
4. 阶段 2：B2/B3/B5（依赖 CI 结果）；
5. 阶段 3：全量验证 + 报告 + 提交。

---

## 7. 一句话总结

**WP-5 的路线是“静态 B1/B4/B6 先做、B7 保持 KNOWN_HOLES、运行时 B2/B3/B5 依托 G0 缓存 CI 非阻塞实施”，在不破坏 108/108 与假阳性基线的前提下完成 H3 KPI3。**

---

## 8. 术语说明：跨场时域同步规范

### 8.1 是什么

**跨场时域同步规范**指多物理场耦合中，不同物理场（流体、结构、热、网格、电磁等）在时间推进与数据交换时必须遵守的同步约定。它规定：

- 各场的时间步（`dt`）如何取值；
- 什么时候交换耦合数据；
- 数据与哪个物理时刻对应；
- 不同时间尺度如何对齐（共享时间步、子循环、插值、耦合迭代）。

它关注的是**时域语义是否正确**，不是数值算法的精度或稳定性（后者归 NVR③）。

### 8.2 为什么需要

多物理场往往有不同时间尺度：

| 场 | 典型时间步 | 原因 |
|:--|:--|:--|
| 流体 CFD | 10⁻³–10⁻⁵ s | CFL 限制、快速流动 |
| 结构动力学 | 10⁻²–10⁻⁴ s | 波速/网格尺度不同 |
| 热传导 | 10⁻¹–1 s | 慢过程 |
| 网格变形 | 与流体/结构同步 | 依赖界面位移 |

若各场各推各的、在各自循环末尾随意交换数据，耦合界面使用的可能是**不同物理时刻的值**，会造成虚假能量注入、振荡或错误瞬态响应。

### 8.3 常见规范形态

| 形态 | 说明 | 静态信号 |
|:--|:--|:--|
| 共享全局时间步 | 所有场使用同一 `dt`，每步同步交换 | 全局 `dt`/`timeStep` + 统一时间循环 |
| 主从子循环（subcycling） | 一个场为主，其他场按整数比例子循环 | `subCycle`、`dtFluid = 2*dtSolid`、比例常量 |
| 时间插值 | 在场 A 与 B 的时间节点间插值交换 | `interpolateInTime`、`temporalInterpolation` |
| 耦合迭代 | 同一耦合时刻反复迭代至收敛 | `couplingIteration`、`maxCouplingIter`、`conv` |
| 外部耦合库 | 由 preCICE 等管理时间步与同步 | `precice::`、`initialize()`、`advance()` |

### 8.4 失败模式

- 多个场有不同 `dt`，但没有比例/对齐声明；
- 耦合数据交换写在各场自己的时间循环内，没有全局同步点；
- 一个场使用上一时刻的耦合量，另一个场使用当前时刻；
- 自适应时间步改变后没有重新同步；
- 强耦合没有收敛检查就开始下一步。

### 8.5 示例

**反例（不同步）**：

```cpp
for (int i = 0; i < nFluid; i++) {   // dt = 0.01
    solveFluid();
    writeInterface();               // 自己循环末尾就写
}
for (int i = 0; i < nSolid; i++) {   // dt = 0.02
    solveSolid();
    writeInterface();               // 没有全局同步点
}
```

**正例（子循环 + 同步）**：

```cpp
for (int step = 0; step < N; step++) {
    t = step * dtSolid;              // 主时间步
    for (int sub = 0; sub < 2; sub++)
        solveFluid(t + sub * dtFluid);  // 流体子循环
    interpolateInTime(fluid, solid, t); // 对齐到同一物理时刻
    solveSolid(t);
    if (couplingConverged()) advance(t);
}
```

### 8.6 与 MPR-011 的关系

MPR-011 只做**静态信号检查**：多场共存且找不到同步/对齐/插值/耦合迭代信号 → candidate WARNING。它**不证明运行时真的不同步**，也不判数值稳定性；外部配置、preCICE、调度器驱动的同步可能识别不到，因此规则默认 candidate，需人工/LLM 复核。


---

## 9. 收口结论

WP-5 按 D1~D5 口径收口：

- B1/B4 以 candidate 交付，保留独立候选通道，不改变既有评分/基线；
- B2/B3 runtime-kernel CI 已取得 `euler=PASS closure=PASS`；
- B5 按 D4 输出 `api_compat=SKIPPED`，不伪造跨版本结果；
- B6 已修复死代码并补正/反向测试；
- B7 保持 KNOWN_HOLES 并输出 `known_holes_audit`。

总报告见 `H3-WP5语义级检测补齐报告.md`。
