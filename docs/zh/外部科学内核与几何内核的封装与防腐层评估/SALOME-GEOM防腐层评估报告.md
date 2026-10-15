# SALOME-GEOM 外部内核防腐层评估报告

> **项目**：SALOME GEOM（GEOM 组件，基于 OCCT 封装）
> **路径**：`D:\opensource\gcs-baselines\salome-geom`
> **日期**：2026-10-13
> **评估引擎**：`arch_metrics_anti_corruption.py`（AntiCorruptionMetrics，指南 1.3 / Skill 1.0）
> **执行流程**：对齐《外部科学内核与几何内核的封装与防腐层评估用户交互提示词模板》7 项任务

---

## 任务一：基础评估（4 维得分 + ACL 违规清单）

### 1.1 总体情况

| 指标 | 值 |
|:-----|:---|
| 防腐层项目（is_acl）| ✅ 是 |
| **综合得分** | **26.5 / 100** |
| ACL 违规规则数 | 7 条 |
| 豁免告警 | 无（boundary_dir_exclusion 0%）|

### 1.2 维度得分

| 维度 | 权重 | 得分 | 关键违规 |
|:-----|:----:|:----:|:---------|
| 外部内核访问防腐 | 30% | **30** | 直连 1,693、失败检查 60 处缺失 |
| Wrapper 覆盖与演进守卫 | 15% | **50** | 覆盖度 0%、版本守卫 1 处 |
| 数据交换防腐 | 30% | **0** | 散落 40、错误 3、直连密度 100% |
| 保真度与标准一致性 | 25% | **40** | round-trip ✅、单位/公差 ✅、**无 AP 守卫 → 0 分**，递进折半 |

> 递进扣分：基础层 2.1=30、2.3=0 均 <60 → 增强层 2.4 从原 80 折半为 40。

### 1.3 ACL 违规清单

| 规则 | severity | output_level | 计数 | 说明 |
|:-----|:--------:|:------------:|:----:|:-----|
| **ACL-001** | HIGH | **ERROR** | **1,693** | 白名单外直连内核符号 |
| ACL-002 | LOW | INFO | 15 | 核心 API 覆盖度 0% |
| ACL-005 | MEDIUM | WARNING | 60 | 内核调用点失败未检查 |
| **ACL-007** | HIGH | **ERROR** | **40** | STEP/IGES 符号散落 4 文件 |
| ACL-010 | LOW | INFO | 0 | 无 AP 版本声明 |
| ACL-011 | MEDIUM | WARNING | 3 | reader 无错误码检查 |
| ACL-012 | MEDIUM | WARNING | 4 | 格式符号直连密度 **100%** |

---

## 任务二：单维度分析（external_access）

### 2.1 直连内核 API 分布

直连 1,693 处集中在一级目录 `src/`，按功能模块细分（OCCT 消费方视角，SALOME 是**真内核消费方**，非内核自身）：

| 模块 | 特点 |
|:-----|:-----|
| `src/AdvancedEngine` | 大量 `BRepBuilderAPI_Transform`/`MakeVertex`（见 ACL-005 样例）|
| `src/STEPPlugin` / `IGESPlugin` | 数据交换插件（同时触发 ACL-007）|
| `src/ShapeRecognition` 等 | 几何操作消费方 |

### 2.2 类型泄漏

**leak_count = 0** —— SALOME 通过 `GEOM_Object`/`GEOM_BaseObject` 自有类型隔离 `TopoDS_Shape`，接口层无明显内核类型透出（与 OCCT 不同，SALOME 的封装相对完整）。该项 30/30，是 4 个子项中唯一健康项。

### 2.3 失败检查缺失（ACL-005，60 处样例）

| 模式 | 文件 | 特点 |
|:-----|:-----|:-----|
| `BRepBuilderAPI_Transform xform(...)` 后无验证 | `AdvancedEngine_DividedDiskDriver.cxx:196/346/484` | 几何变换未验证 |
| `BRepBuilderAPI_MakeVertex` 连续构造 | `AdvancedEngine_IOperations.cxx:456-497` | 点构造未检查 |

> 60 处全部集中在 `AdvancedEngine`（网格驱动/操作引擎），是 SALOME **真实质量缺口**——失败静默会产出坏网格。

---

## 任务三：ACL-007 规则排查（STEP/IGES 散落）

散落 40 处仅 4 文件，全部为**SALOME 的数据交换插件本身**：

| 文件 | 散落数 | 说明 |
|:-----|:-----:|:-----|
| `src/STEPPlugin/STEPPlugin_ImportDriver.cxx` | 14 | STEP 导入驱动 |
| `src/STEPPlugin/STEPPlugin_ExportDriver.cxx` | 10 | STEP 导出驱动 |
| `src/IGESPlugin/IGESPlugin_ImportDriver.cxx` | 12 | IGES 导入驱动 |
| `src/IGESPlugin/IGESPlugin_ExportDriver.cxx` | 4 | IGES 导出驱动 |

**影响范围**：这 4 个文件是 SALOME 的标准数据交换插件（对标 OCCT DataExchange），**格式读写本来就应集中在这里**。引擎判定"散落"是因为插件目录名 `STEPPlugin`/`IGESPlugin` 未被识别进 `import_export_dirs` 白名单（当前白名单含 `step`/`iges`，但插件目录是冠以 `Module` 后缀的 `*Plugin`）。

> ⚠️ **判定失真**：ACL-007 的 40×（ERROR）+ ACL-012 100% 密度，**源于白名单目录名启发式未覆盖 `*Plugin` 形态**——并非 SALOME 真把格式读写散落到业务层。这是 WP-7 需校准的目录白名单扩展点（`STEPPlugin`/`IGESPlugin` 应视为 import/export 模块）。

---

## 任务四：改进建议（P0/P1/P2，含得分预估）

基于当前 26.5，按可落地性分级：

### P0（20 分空间）

| # | 建议 | 增量子维度 | overall 预估 |
|:--|:-----|:-----------|:------------|
| **P0-1** | `AdvancedEngine` 60 处 `Transform`/`MakeVertex` 补 `IsDone()` 检查（失败静默 → 坏网格）| external_access 30→60 | **+9.0** |
| **P0-2** | 3 处 reader/writer 补 `IFSelect_RetDone`（导入失败静默 → 坏几何）| data_exchange 0→30 | **+9.0** |

> P0 两项 → **26.5 → 44.5**。递进扣分仍未解除（2.3=30 仍 <60）。

### P1（27.5 分空间）

| # | 建议 | 增量子维度 | overall 预估 |
|:--|:-----|:-----------|:------------|
| **P1-1** | **白名单扩展**：把 `STEPPlugin`/`IGESPlugin`/`*Plugin` 注册为 import/export 模块 → ACL-007(40)+ACL-012 反转为 0（判据校正，非改代码）| data_exchange 30→? | 校正后降 ERROR |
| **P1-2** | 补 `#if OCC_VERSION` 守卫族 + AP203/214/242 声明（当前各 1/0）| fidelity 40→100（解锁折半）| **+15.0** |

> P1 完成后 → **59.5~**（若 P1-1 使 2.3 ≥60 解除折半则更高）。

### P2（语义校正）

| # | 建议 | 影响 |
|:--|:-----|:-----|
| P2-1 | `ShapeRecognition` 的唯一 1 处 `#if OCC_VERSION` 扩展为守卫族 | 维护性 |
| P2-2 | 建议对 `GEOMImpl` 封装补充核心 API 覆盖度声明（当前 `wrapper_decl=[]`）| 消除 ACL-002 失真 |

---

## 任务五：历史对比（与回归基线）

| 指标 | 基线 | 当前 | 偏移 | 容差 | 判定 |
|:-----|:----:|:----:|:----:|:----:|:----:|
| overall | 26.5 | 26.5 | 0.0 | ±2.0 | ✅ PASS |
| external_access | 30 | 30 | 0 | ±5 | ✅ |
| wrapper_coverage | 50 | 50 | 0 | ±5 | ✅ |
| data_exchange | 0 | 0 | 0 | ±5 | ✅ |
| fidelity | 40 | 40 | 0 | ±5 | ✅ |

| 规则 | 基线 | 当前 | 偏移 | 判定 |
|:-----|:----:|:----:|:----:|:----:|
| ACL-001 | 1,693 | 1,693 | +0 | ✅ |
| ACL-005 | 60 | 60 | +0 | ✅ |
| ACL-007 | 40 | 40 | +0 | ✅ |
| ACL-010 | 0 | 0 | +0 | ✅ |
| ACL-012 | 4 | 4 | +0 | ✅ |

**结论：零退化。** 评分、4 维、违规计数与基线（2026-10-12 固化）完全一致，全部落在容差内，无等级升级。

---

## 任务六：外部内核防腐专项审查（5 项）

| # | 专项要求 | 判定 | 证据要点 |
|:-:|:---------|:----:|:---------|
| ① | Wrapper 目录收敛全部内核调用 | ❌ 未满足 | 无 wrapper 白名单命中，直连 1,693 |
| ② | STEP/IGES/IFC 读写集中 | ⚠️ 已集中但白名单漏识别 | 散落 40 处全在 `STEPPlugin`/`IGESPlugin`（实为 import/export 模块）|
| ③ | reader/writer 错误检查 | ⚠️ 62%→85%（3/212 单站）| SALOME 3 处无 `IFSelect_RetDone` |
| ④ | round-trip 往返保真度测试 | ✅ 存在 | `src/XAO/tests/ImportExportTest.cxx` |
| ⑤ | AP203/214/242 版本守卫 | ❌ 缺失 | AP 引用 `{}` → ACL-010 0 分 |

**实质结论**：
- ② 是**白名单配置缺陷**而非代码缺陷（修正白名单后 40 处反转为 0）
- ⑤ 真实缺失：SALOME STEP/IGES 插件未声明支持 AP 版本——建议在插件层声明 AP203/214/242
- ④ round-trip 测试存在但仅覆盖 XAO 数据交换，STEP/IGES 路径建议补

---

## 任务七：内核升级影响面评估（OCCT 升级）

### 7.1 被直连核心 API 分布

| 核心类 | 使用 | 影响文件 | 升级风险 |
|:-------|:----:|:-------:|:---------|
| **TopoDS_Shape** | 1,739 | **186** | 🔴 最高 |
| **BRep_Tool** | 576 | 74 | 🔴 高 |
| BRepBuilderAPI_MakeEdge | 80 | 21 | 🟠 中 |
| BRepBuilderAPI_MakeFace | 67 | 20 | 🟠 中 |
| Geom_Plane | 53 | 17 | 🟠 中 |
| BRepBuilderAPI_MakeWire | 42 | 17 | 🟠 中 |
| 其余 10 类 | ~130 | 1-8 | 🟡 低 |

**受影响文件总数（去重）：193 个**。

### 7.2 版本守卫现状

| 项 | 值 |
|:---|:---|
| `#if OCC_VERSION` | 全仓 **1 处**（`src/ShapeRecognition/ShapeRec_FeatureDetector.cxx:226`）|
| 判定 | 🔴 升级 OCC 时 193 个直连文件的版本差异点无防线 |

### 7.3 影响面估算（OCCT 7.x → 8.0）

| 口径 | 影响 |
|:-----|:-----|
| 无 wrapper 现状 | `TopoDS_Shape` 186 文件 + `BRep_Tool` 74 = **约 260 处直接文件需审改** |
| 加 wrapper + 守卫后 | 收敛到 GEOMImpl 封装层，消费方文件 0 改动 |

### 7.4 改造建议

1. **P0**：`GEOMImpl` 补 `TopoDS_Shape`/`BRep_Tool` 封装（消费方经 `GEOM_Object` 已隔离大部分，补剩余直连点）
2. **P1**：wrapper 内建 `#if OCC_VERSION` 守卫族（先覆盖 `BRep_Tool` 行为差异 + STEP 插件版本分支）
3. **P2**：`AdvancedEngine` 的 `MakeVertex`/`Transform` 收敛到统一 facade

---

## 综合结论

SALOME-GEOM 防腐层**基础形态良好但存在失真与真实缺口的混合状态**：

| 类别 | 内容 |
|:-----|:-----|
| ✅ 健康 | 类型封装（`GEOM_Object` 隔离 0 泄漏）、round-trip 测试存在、数据交换已集中 |
| ⚠️ 失真（判据问题）| ACL-007/012 的 `STEPPlugin` 白名单漏识别（40 处误判）；ACL-002 覆盖度因无 wrapper 声明失真 |
| 🔴 真实缺口 | `AdvancedEngine` 60 处失败未检查；无 AP 版本守卫；`#if OCC_VERSION` 仅 1 处 |

**得分预期**：修正白名单（失真归零）+ 补 60 处失败检查 + AP 守卫 → 26.5 → **≈60**；再做 wrapper 收敛与守卫族 → 70+。

---

## 附：数据来源

| 数据 | 来源 |
|:-----|:-----|
| 得分/违规 | `tests/regression/snapshots/acl_salome_geom.json` + 引擎实测（2026-10-13）|
| 直连/失败/散落明细 | `arch_metrics_anti_corruption.py` 正则全仓扫描 |
| 核心类统计 | `CORE_KERNEL_CLASS_RE` 全仓扫描（193 文件去重）|
| round-trip | `ROUND_TRIP_RE` 扫描 → `XAO/tests/ImportExportTest.cxx` |
| AP 版本 | `AP_VERSION_RE` / `STEP_PROFILE_SET_RE` → 无命中 |

*本报告由 `architecture-quality` 智能体按《外部内核防腐层评估用户交互提示词模板》7 项任务执行生成。*