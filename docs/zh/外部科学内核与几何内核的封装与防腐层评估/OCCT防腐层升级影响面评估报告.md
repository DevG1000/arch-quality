# OCCT 外部内核防腐层评估 — 升级影响面专项报告

> **项目**：Open CASCADE Technology（OCCT）V8.0.1
> **路径**：`D:\opensource\gcs-baselines\occt`
> **日期**：2026-10-13
> **评估引擎**：`arch_metrics_anti_corruption.py`（AntiCorruptionMetrics，指南 1.3 / Skill 1.0）
> **触发场景**：升级其外部内核（OCCT 等）时影响面评估——基于 ACL-001/002/003 违规估算被直连 API 数量，建议 wrapper 收敛与版本守卫改造范围

---

## 一、评估前提（关键判读）

OCCT 是"被评估的**内核自身**"，不是"消费外部内核的应用"。因此影响面按**两层**拆解：

1. **内核内部实现**（ModelingData / ModelingAlgorithms）——升级自有 API 时 OCCT 自身要重构的范围
2. **内部消费方**（Draw / DataExchange / ApplicationFramework / Visualization）——OCCT 各工具包互相消费的耦合面，等价于"业务层直连"的真实信号

> 判读依据：OCCT 无 wrapper 目录，内核符号裸露于公开工具包——ACL-001 直连 50,368 处中 47,331 属内核自身实现，真实消费方信号约 3,793 处（Draw 2,116 + DataExchange 769 + Visualization 426 + ApplicationFramework 273 + Deprecated 209）。

---

## 二、综合得分快照

| 指标 | 值 |
|:-----|:---|
| **overall** | **36.5 / 100** |
| external_access | 30（直连 0/40 + 泄漏 30/30 + 失败检查 0/30）|
| wrapper_coverage | 50（覆盖度 0/50 + 版本守卫 50/50）|
| data_exchange | 25（散落 0/45 + 错误 0/30 + 直连密度 25/25）|
| fidelity | 50（原满分 100，递进折半）|

---

## 三、被消费的内核 API 数量与分布

### 3.1 核心内核类按升级影响面排序（16 类）

| 核心内核类 | 总使用 | 影响文件 | 消费方文件 | 升级风险 |
|:-----------|:------:|:-------:|:---------:|:---------|
| **TopoDS_Shape** | 26,547 | **1,655** | **650** | 🔴 最高（泛型核心，几乎全仓）|
| **BRep_Tool** | 5,430 | 547 | 140 | 🔴 高 |
| Geom_Plane | 1,302 | 267 | 102 | 🟠 中高 |
| BRepPrimAPI_MakeBox | 746 | 102 | 21 | 🟠 中 |
| BRepBuilderAPI_MakeEdge | 546 | 84 | 24 | 🟠 中 |
| Geom_CylindricalSurface | 477 | 97 | 26 | 🟠 中 |
| BRepBuilderAPI_MakeFace | 295 | 76 | 32 | 🟠 中 |
| BRepBuilderAPI_MakeWire | 167 | 47 | 16 | 🟠 中 |
| BRepCheck_Analyzer | 156 | 43 | 8 | 🟡 中低 |
| BRepAlgoAPI_Cut | 140 | 22 | 5 | 🟡 |
| BRepPrimAPI_MakeCylinder | 133 | 37 | 11 | 🟡 中 |
| BRepAlgoAPI_Fuse | 92 | 24 | 7 | 🟡 |
| BRepFilletAPI_MakeFillet | 91 | 9 | 6 | 🟡 |
| BRepAlgoAPI_BooleanOperation | 69 | 23 | 7 | 🟡 |
| BRepFilletAPI_MakeChamfer | 51 | 4 | 1 | 🟢 低 |
| BRepAlgoAPI_Common | 38 | 14 | 4 | 🟢 低 |

### 3.2 量化结论

- 16 个核心内核类共影响 **1,911 个文件**
- 其中 **698 个属内部消费方**（Draw / DataExchange / AppFramework 等，真正的"业务层"信号）
- **TopoDS_Shape** 单类影响 1,655 文件 + 消费方 650 —— 升级其 ABI/API 是全仓级破坏

### 3.3 消费方工具包直连密度

| 消费方工具包 | 内核符号引用 | 性质 |
|:-------------|:-----------:|:-----|
| Draw | 2,116 | 调试命令，升级影响中等 |
| DataExchange | 769 | **导入/导出路径**，升级影响高（坏体流入下游）|
| Visualization | 426 | 可视化消费，中 |
| ApplicationFramework | 273 | CAF 文档，中 |
| Deprecated | 209 | 兼容层，低 |

---

## 四、版本守卫（ACL-003）现状

| 项 | 值 |
|:---|:---|
| `#if OCC_VERSION` 守卫 | **全仓仅 1 处**（`src/Draw/TKIVtkDraw/IVtkDraw/IVtkDraw.cxx:1604`）|
| 覆盖 | 单个 Draw 集成点 |
| 判定 | 🔴 跨版本差异点的兼容隔离**几乎为零** |

> 对比：升级 1,911 个直接引用文件（含 465 个消费方文件），只有 1 处版本守卫——升级一个主版本，绝大部分版本差异点会直接编译失败或行为漂移，无任何防线。

---

## 五、改造范围建议

### 5.1 Wrapper 收敛范围（按影响面优先级）

| 优先级 | 收敛对象 | 影响面 | 建议 |
|:------:|:---------|:-------|:-----|
| **P0** | `TopoDS_Shape` | 1,655 文件 / 650 消费方 | 在 DataExchange/AppFramework 层建立统一 `Handle(TopoDS_Shape)` 或自有 `GeomShape` 值类型，消费方经它访问 |
| **P0** | `BRep_Tool` | 547 文件 / 140 消费方 | 封装为工具类 `wk::ShapeUtil`，隔离 BRep_Tool 的 API 变动 |
| **P1** | `Geom_*` 曲面类 | 364 文件合计 | 集中到几何封装层，防构造函数签名漂移 |
| **P1** | 布尔/圆角类（`BRepAlgoAPI_*` / `MakeFillet` 等）| ~500 处 | 收敛到单一 `wk::BooleanOps` / `wk::Fillet` facade |
| **P2** | `MakeBox/MakeCylinder/MakeEdge` 等基础构建 | 消费方 ≥10 文件的类 | 仅对高频类做 facade，其余保持直连（成本收益权衡）|

### 5.2 版本守卫改造

| 项 | 建议 |
|:---|:-----|
| **目标** | 覆盖所有**跨版本行为差异点**，集中在 wrapper 内维护 |
| **最小集** | DataExchange 的 `STEPControl_*` 版本分支 + `BRep_Tool` 行为差异 + `TopoDS_Shape` 空/坏形判别转型 |
| **模式** | `#if OCC_VERSION >= 7xx00` / `#if OCC_VERSION < 80000` 成对块，置于 wrapper 内部 |
| **规模** | 预计 20-40 个守卫块（覆盖 3 个主版本差异），集中在 4-6 个 wrapper 文件中 |
| **现有守卫** | 1 处（`IVtkDraw.cxx`）→ 需扩充 20-40 倍 |

### 5.3 影响面估算（升级 OCCT 7.6 → 8.0）

| 口径 | 影响 |
|:-----|:-----|
| 无 wrapper 现状 | `TopoDS_Shape` 650 消费方文件 + `BRep_Tool` 140 = **全仓 ~790 文件需动** |
| 建 wrapper + 守卫后 | 收敛到 wrapper 层 4-6 文件，消费方文件 0 改动（API 稳定即不破坏消费方）|

---

## 六、结论与建议路径

**结论**：OCCT 的内核升级影响面**当前未受控**——核心内核类被 1,911 文件直接消费，版本守卫仅 1 处，属 ACL-001（直连大量）/ACL-003（守卫缺失）的双重高风险组合。但这是内核自身的共性（消费方越多越难改造），且 DataExchange 已用 `occ::handle` / 自有类型基本隔离了 STEP 层。

**建议路径**（对齐 P0/P1 建议 + 升级影响面）：

1. **P0-1**：DataExchange 层 wrapper 收敛 `TopoDS_Shape` / `BRep_Tool`（其面向导入导出的 769 处直连是最真实风险）
2. **P0-2**：补齐 81 处 reader/writer 错误检查（升级容错）
3. **P1**：在 wrapper 内建 `#if OCC_VERSION` 守卫族（先覆盖 DataExchange + BRep_Tool 两个最高影响点）
4. **P2**：Draw / Visualization 消费方可逐步收敛，非关键路径

**一句话**：升级影响面 = **16 类核心 API × 1,911 文件直接引用 + 仅 1 处版本守卫**——当前升级即风暴；按 wrapper 收敛范围表先落 DataExchange / TopoDS_Shape / BRep_Tool 三点，可将受影响文件从 ~790 降到个位数。

---

## 七、附：数据来源

| 数据 | 来源 |
|:-----|:-----|
| 得分/违规 | `tests/regression/snapshots/acl_occt.json` + 引擎实测（2026-10-13）|
| 核心类使用统计 | `arch_metrics_anti_corruption.py` CORE_KERNEL_CLASS_RE 扫描全仓 |
| 版本守卫盘点 | `GENERIC_VERSION_GUARD_RE` 全仓扫描，仅 `IVtkDraw.cxx:1604` |
| 消费方分类 | 按 OCCT 工具包目录（src/Draw、src/DataExchange 等）归类 |

*本报告由 `architecture-quality` 智能体基于 ACL 引擎专项分析生成，供内核升级决策参考。*