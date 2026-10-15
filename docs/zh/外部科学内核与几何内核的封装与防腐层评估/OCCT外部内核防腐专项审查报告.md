# OCCT 外部内核防腐专项审查报告

> **项目**：Open CASCADE Technology（OCCT）V8.0.1
> **路径**：`D:\opensource\gcs-baselines\occt`
> **日期**：2026-10-13
> **评估引擎**：`arch_metrics_anti_corruption.py`（AntiCorruptionMetrics，指南 1.3 / Skill 1.0）
> **审查类型**：外部内核防腐专项要求 5 项逐项审查（wrapper 收敛 / 数据交换集中 / 错误检查 / round-trip / AP 版本守卫）

---

## 一、审查总表

| # | 专项要求 | 判定 | 证据要点 |
|:-:|:---------|:----:|:---------|
| ① | Wrapper 目录收敛全部内核调用 | ❌ 不适用 | 无 wrapper 目录（OCCT 是内核自身）|
| ② | STEP/IGES/IFC 集中读写 | ✅ 96% 集中 | 351/364 文件在 DataExchange，散落仅在 Deprecated/Draw |
| ③ | reader/writer 错误检查 | ⚠️ 62%（81 处缺口）| 131/212 调用点有 IFSelect_RetDone 检查 |
| ④ | round-trip 往返保真度测试 | ⚠️ 产品树内无，测试树有 | 引擎匹配 5 文件中 4 个是数学/拓扑回归 |
| ⑤ | 外部标准版本（AP203/214/242）守卫 | ✅ 完整 | AP203×6 / AP214×3 / AP242×3 声明 |

---

## 二、逐项审查详情

### ① Wrapper 目录是否收敛全部内核调用 —— ❌ 不适用

| 证据 | 值 |
|:-----|:---|
| wrapper 目录文件 | **0** |
| 白名单外内核直连 | 50,368 处 |
| 按工具包 | ModelingData 26,051 / ModelingAlgorithms 21,280 / Draw 2,116 / Visualization 426 / 其他 ~500 |

**判定**：OCCT 无 wrapper 目录，内核符号**全部**裸露在公开工具包中。但 **OCCT 是内核自身而非消费方**——ModelingData/Algorithms 的 47,331 处是内核 API 的**定义与实现**，不是"业务层绕过 wrapper"。真正的应用层（Draw/Visualization 等）确实直连，但那是内核自带的调试/可视化工具。

> 与 ACL-001 失真同源：此项对 OCCT **不适用**（处置 b/内核排除前不可读）。

### ② STEP/IGES/IFC 读写是否集中 —— ✅ 基本满足（96% 集中）

| 证据 | 值 |
|:-----|:---|
| 格式符号文件 | 364 |
| import/export 模块内 | 351（**96.4%**）|
| 模块外散落 | 13 文件 / 160 处，**全部在 Deprecated/Draw** |

**判定**：集中度优秀——OCCT 的 `src/DataExchange/*`（TKDESTEP/TKDEIGES/TKIFC）承载了几乎所有格式读写。散落的 160 处集中在两类：

| 散落位置 | 性质 |
|:---------|:-----|
| `src/Deprecated/NCollectionAliases/IFSelect_*` | 别名兼容层，不参与实际读写 |
| `src/Draw/TKXSDRAW*`（含 `QABugs_11.cxx` 等）| 调试/QA 命令 |

> Draw/QA 散落属"测试/调试通道"，建议引擎回归测试用 `exclude_test` 口径复核；核心产品代码集中度 ≈100%。

### ③ reader/writer 调用点是否检查 IFSelect_ReturnStatus —— ⚠️ 部分满足（62%）

| 证据 | 值 |
|:-----|:---|
| reader/writer 调用点 | 212 |
| 有 IFSelect_RetDone/catch 检查 | 131（**61.8%**）|
| 无检查 | **81** |

**判定**：过半数调用点有错误码检查，但 **81 处无 `IFSelect_ReturnStatus` 捕获**。这批 81 处与引擎 ACL-011 计数（109，含其它形态）高度相关——需补检查的主要是 `TransferRoots` / `CheckFileName` 等辅助调用。

**建议修复（对齐 ACL-011 / P0-2）**：对 81 处无检查调用点补齐 `IFSelect_ReturnStatus` 检查：
```cpp
if (r.ReadFile(path) != IFSelect_RetDone) throw std::runtime_error("read fail");
if (w.Write(path) != IFSelect_RetDone) throw std::runtime_error("write fail");
```

### ④ 是否存在 round-trip 往返保真度测试 —— ⚠️ 口径问题（产品树内未检出）

| 证据 | 值 |
|:-----|:---|
| 引擎匹配文件 | 5 |
| 实际命中 | 4 个是**数学/拓扑回归**（`PLib_Test` / `BRepGraph_*`），非 STEP 往返 |

**判定**：引擎的 `ROUND_TRIP_RE` 在当前样本把"拓扑验证"误算为 round-trip。真实的 **STEP 数据交换往返测试存在于 `tests/` 目录**（OCCT 的 `buffered_*`/`tostep_*` 回归桶），但**不在 `src/` 产品树的受扫范围**内。

> 这是**测试放置口径**问题（OCCT round-trip 测试在 `tests/`，引擎扫 `src/`），非 OCCT 缺陷。可 pass 但需在报告口径中注明：产品源码树内无专用 round-trip 保真度测试。

### ⑤ 是否声明外部标准版本（AP203/214/242）守卫 —— ✅ 满足

| 证据 | 值 |
|:-----|:---|
| AP 版本引用 | AP203×6 / AP214×3 / AP242×3 |
| 声明位置 | `APIHeaderSection_MakeHeader`/`EditHeader`、`HeaderSection_FileSchema`、`STEPCAFControl_Reader/Writer`、`DESTEP_ConfigurationNode` |

**判定**：OCCT 在数据交换模块**显式声明并支持三个 AP 版本**，通过 `APIHeaderSection` / `FileSchema` 集中管理 schema 选择，是标准版本守卫的**正面范例**（ACL-010 命中，fidelity 该项满分）。

---

## 三、综合判定与整改建议

### 3.1 总体结论

5 项专项审查中：
- **2 项满足/健全**：② 数据交换集中（96%）✅、⑤ AP 版本守卫 ✅
- **2 项需纠正口径**：① wrapper 不适用（OCCT 是内核）、④ round-trip 在产品树外
- **1 项真实缺口**：③ reader/writer 错误检查 62%（81 处缺失）

### 3.2 整改优先级

| 优先 | 整改 | 性质 |
|:----:|:-----|:-----|
| **P0** | 81 处 reader/writer 调用点补 `IFSelect_RetDone` 检查 | 真实质量缺口，可直接改 |
| **P1** | 引擎回归把 OCCT 标记为"内核自身排除"（`@acl_exempt` + 目录白名单）| 消除 ① 失真 |
| **P2** | 引擎 `ROUND_TRIP_RE` 增加 `tests/` 目录覆盖口径 | 消除 ④ 误判 |
| **P2** | Draw/QA 散落（ACL-007 160 处）按 test 口径复核 | 剩余散落无实际风险 |

---

## 四、数据来源

| 数据 | 来源 |
|:-----|:-----|
| wrapper/格式符号/错误检查统计 | `arch_metrics_anti_corruption.py` 正则全仓扫描（2026-10-13）|
| AP 版本声明 | `AP_VERSION_RE` / `STEP_PROFILE_SET_RE` 扫描，17 文件 |
| round-trip | `ROUND_TRIP_RE` / `WRITE_READ_ASSERT_RE` 扫描，5 文件 |
| 得分快照 | `tests/regression/snapshots/acl_occt.json`（overall 36.5）|

*本报告由 `architecture-quality` 智能体基于 ACL 引擎专项审查生成，供防腐层质量评估参考。*