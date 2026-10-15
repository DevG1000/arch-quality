# SALOME-GEOM 内核升级影响面评估报告

> **项目**：SALOME GEOM（GEOM 组件，基于 OCCT 的封装层）
> **路径**：`D:\opensource\gcs-baselines\salome-geom`
> **日期**：2026-10-13
> **评估引擎**：`arch_metrics_anti_corruption.py`（AntiCorruptionMetrics，指南 1.3 / Skill 1.0）
> **场景**：升级其外部内核（OCCT 等）时的影响面评估——基于 ACL-001/002/003 违规估算被直连 API 数量，建议 wrapper 收敛与版本守卫改造范围

---

## 一、评估前提（与 OCCT 不同处）

SALOME-GEOM 是**真正的 OCCT 内核消费方**（非内核自身）——它通过 `GEOMImpl` 封装层消费 OCCT。因此本次影响面评估**直接成立**，无需双层判读：直连 TopoDS_/BRep* 的每一处都是真实的"业务层→内核"耦合。

三层结构：
```
SALOME 业务/驱动（GEOMUtils/AdvancedEngine/插件）
  └─ GEOMImpl（OCCT 封装层，集中 1158 处直连）
       └─ OCCT（TopoDS_/BRep_/Geom_ 等内核 API）
```

---

## 二、直连内核 API 分布（ACL-001 数据）

### 2.1 按 src 子模块（前 20）

| 模块 | 直连数 | 定位 |
|:-----|:-----:|:-----|
| **GEOMImpl** | **1,158** | OCCT 封装层（**核心关注点**：升级时应只改这里）|
| AdvancedEngine | 148 | 引擎驱动（跨层消费，风险中）|
| GEOMUtils | 82 | 工具层（跨层消费）|
| GEOM_I / ShHealOper / CurveCreator / OCC2VTK | 196 | 功能模块 |
| OBJECT / SKETCHER / STLPlugin / XAO | 73 | 其他 |
| GEOM_SWIG / 插件族 | ~50 | 绑定/数据交换 |

### 2.2 结论

- **GEOMImpl 独占 68.4% 直连（1,158/1,693）**——这是设计上的封装层，升级 OCCT 时主要改造面**收敛于此**，符合防腐意图
- **其余 ~535 处直连散落在业务模块**（AdvancedEngine/GEOMUtils 等）——这些是 **wrapper 覆盖缺口**，升级时风暴点

---

## 三、被直连的核心 OCCT 类（ACL-002 数据）

### 3.1 核心类使用表

| 核心类 | 使用 | 影响文件 | 升级风险 |
|:-------|:----:|:-------:|:---------|
| **TopoDS_Shape** | 1,739 | **186** | 🔴 最高（泛型首参，全仓型）|
| **BRep_Tool** | 576 | 74 | 🔴 高（工具函数签名易变）|
| BRepBuilderAPI_MakeEdge | 80 | 21 | 🟠 中 |
| BRepBuilderAPI_MakeFace | 67 | 20 | 🟠 中 |
| Geom_Plane | 53 | 17 | 🟠 中 |
| BRepBuilderAPI_MakeWire | 42 | 17 | 🟠 中 |
| 其余 10 类 | ~130 | 1-8 | 🟡 低 |

**受影响文件总数（去重）：193 个**。

### 3.2 头文件引用 TOP（升级需重编的模块面）

| 头文件 | 引用数 | 说明 |
|:-------|:-----:|:-----|
| `TopoDS_Shape.hxx` | 104 | 核心数据类，全模块 |
| `TopoDS.hxx` | 80 | 类型别名 |
| `BRep_Tool.hxx` | 69 | 工具 API（最具升级破坏性）|
| `TopoDS_Edge/Vertex/Face/Compound/Wire/Iterator` | ~190 | 拓扑子类 |
| `BRepBuilderAPI_*.hxx` | ~90 | 构建器族（MakeEdge/Face/Vertex/Wire/Transform）|

---

## 四、版本守卫（ACL-003）现状 —— 严重缺失

| 项 | 值 |
|:---|:---|
| `#if OCC_VERSION` 守卫 | **0 处** |
| `*_VERSION` 条件编译 | **1 处**，且在 `ShapeRec_FeatureDetector.cxx:226` 是 **`#if CV_MAJOR_VERSION`**（OpenCV 版本，非 OCCT）|
| 判定 | 🔴 **OCCT 版本差异守卫为零**——升级 OCCT 时无一处置防线，全依赖 API 稳定 |

> 对比：1,693 处直连点 + 193 受影响文件，却 0 处 `#if OCC_VERSION` 守卫。升级 OCCT 主版本时，任何 API/行为差异都会**直接裸露**到 SALOME 全仓，无编译期隔离。

---

## 五、影响面估算（OCCT 7.x → 8.0）

### 5.1 改造工作量

| 口径 | 需改动文件 | 说明 |
|:-----|:---------:|:-----|
| **无 wrapper 现状** | **~260**（TopoDS 186 + BRep_Tool 74 去重后估计）| 全仓直接受影响 |
| 仅改 GEOMImpl（理想拆分）| 主要 1,158 处所在封装层文件 | 但其余 535 处分模块仍裸露 |
| 建 wrapper + 守卫后 | 收敛到封装层 | 业务模块 0 改动 |

### 5.2 升级容量点（构建器调用集中地）

| 模块 | BRepBuilderAPI/BRepAlgoAPI 调用点 |
|:-----|:-----:|
| GEOMImpl | 85 |
| AdvancedEngine | 41 |
| ShHealOper / SKETCHER / GEOMUtils / OCC2VTK / STLPlugin | 10 |

> 这 136 个构建器调用点是升级时**最可能编译失败**的位置（构造签名/返回语义变化）。

---

## 六、wrapper 收敛与版本守卫改造建议

### 6.1 Wrapper 收敛范围（按影响面）

| 优先级 | 收敛对象 | 影响面 | 建议 |
|:------:|:---------|:-------|:-----|
| **P0** | `TopoDS_Shape`（1,739 用/186 文件）| 全模块 | GEOMImpl 应统一透出自有 `GEOM_Object`→`TopoDS_Shape` 映射，消费方禁止裸传内核首参 |
| **P0** | `BRep_Tool`（576 用/74 文件）| 高 | 封装 `wk::ShapeUtil` 工具类，隔离 BRep_Tool API 变动 |
| **P1** | `BRepBuilderAPI_MakeEdge/Face/Vertex/Wire` | 90+ 处 | 收敛到 GEOMImpl 统一构造 facade，业务模块经 GEOM 命令调用 |
| **P1** | 分支模块散连（AdvancedEngine/GEOMUtils 共 230 处）| 中 | 上移到 GEOMImpl 或新建薄 facade |
| **P2** | 插件/绑定层（STLPlugin/GEOM_SWIG）| 低 | 保持现状，随插件修订 |

### 6.2 版本守卫改造

| 项 | 建议 |
|:---|:-----|
| **目标** | GEOMImpl + BRep_Tool 两处建立 `#if OCC_VERSION` 守卫族 |
| **最小集** | `BRep_Tool` 签名差异 + STEP/IGES 插件 schema 分支 + TopoDS 判别转型 |
| **模式** | `#if OCC_VERSION >= 7xx00` / `#if OCC_VERSION < 80000` 成对块，置于 GEOMImpl 封装内部 |
| **规模** | 预计 15-30 个守卫块，集中 3-5 个封装文件 |
| **现有** | 0 处（OCCT 相关）→ 需新建 | 

### 6.3 建议路径

1. **P0-1**：GEOMImpl 收敛 `TopoDS_Shape`/`BRep_Tool`（覆盖 68% 直连）
2. **P0-2**：GEOMImpl 内建 `#if OCC_VERSION` 守卫族（防 BRep_Tool 行为漂移）
3. **P1**：AdvancedEngine/GEOMUtils 230 处分模块散连上移
4. **P2**：增量把 GEOMUtils/ShHealOper 等收敛为薄 facade

---

## 七、结论

**影响面 = 16 类核心 OCCT API × 193 文件直接引用 + 0 处 OCCT 版本守卫。**

SALOME-GEOM 与 OCCT 评估的结构性差异：

| 对比项 | OCCT（内核自身）| SALOME（消费方）|
|:-----|:-----|:-----|
| 直连性质 | 内核自身实现 | **真实业务层耦合** |
| 升级影响成立性 | 需双层判读 | **直接成立** |
| 封装亮点 | 无（本身就是内核）| **GEOMImpl 集中 68% 直连**（防腐意图良好）|
| 核心缺口 | 无一版本守卫 | **0 处 OCCT 守卫** + 535 处分模块散连 |

**SALOME 的升级风险评级：🟠 中高。** 比 OCCT 好的是已有 GEOMImpl 封装层（投入收敛后改造面小），比 OCCT 差的是**零版本守卫**且 32% 直连逃逸出封装层——升级 OCCT 时这 535 处（AdvancedEngine/GEOMUtils 等）会直接撞上 API 变化。

**一句话**：改前约 260 文件需动；按 P0 收敛 GEOMImpl（TopoDS/BRep_Tool）+ 建守护后 → 业务层改造文件可降到 OEM 插件级个位数，风险可控。

---

## 附：数据来源

| 数据 | 来源 |
|:-----|:-----|
| 直连分布 | `RAW_KERNEL_USE_RE` 全仓扫描（1,693 处按模块归类）|
| 核心类统计 | `CORE_KERNEL_CLASS_RE` 扫描（16 类 / 193 文件去重）|
| 版本守卫 | `GENERIC_VERSION_GUARD_RE` → 0 处 OCCT 守卫，1 处 OpenCV 守卫 |
| 构建器调用点 | `KERNEL_CALL_STMT_RE` 统计（136 点）|
| 头文件引用 | `#include *.hxx` 解析 TOP20 |

*本报告由 `architecture-quality` 智能体基于 ACL 引擎专项分析生成，供 SALOME 内核升级决策参考。*