# 几何内核与科学数据结构一致性评估验证案例集

> **版本**：1.2（案例集专家校对 5 项修订）
> **日期**：2026-09-08
> **归属**：H2 WP-1 维度④ 标准文档包 — 验证案例集
> **关联**：《几何内核与科学数据结构一致性评估指南（1.5版）》
> **分类规范**（对齐《AI 架构评估文档编制指南 1.7》§4）：A 类可复现开源项目 / B 类参考 / C 类 Validation / 合成正负例

---

## 一、A 类：可复现开源项目案例

> A 类案例通过 `scripts/fetch_project.py` 获取固定 ref，可复现。预期结果为**手工语义预期**，供 WP-2 B3.5 对照验证（防误报/漏报）。

### A-1：OCCT（Open CASCADE Technology）— 几何内核正样本

- **获取方式**：`python scripts/fetch_project.py occt --dest <dir>`（tag V8.0.1，commit `b8f597c6`）
- **架构分析**：
  - 使用 `Handle_*`/`TopoDS_*` 智能指针（GCS-002 良好实践）
  - `BRepCheck_Analyzer`/`BRepCheck_*` 闭合性校验工具存在（GCS-001 命中）
  - `DataExchange/TKDEIGES`、`TKDESTEP` 数据交换模块（GCS-007/008 样本）
- **预期结果（阳性，B3.5 实测校准）**：
  - GCS-002（Handle 一致性）→ **低违规范**（OCCT 自身全程智能指针）
  - GCS-003（异常传播）→ **中违规范**（B3.5 实测：生产代码布尔操作 40 处"直接提取结果"模式——失败检查委托给封装级 builder（BRepFeat/BRepFill）的 `IsDone()`，静态不可判，属 KNOWN_HOLES；助手委托 CheckAndLoad/显式 Build 已识别不计）
  - GCS-012（数据访问封装）→ 低违规范
  - GCS-005/006（魔法因子）→ **中低违规范**（OCCT 精度多用命名常量如 `Precision::Confusion()`，单位制由 `UnitsMethods` 管理，作校准基准）

### A-2：SALOME GEOM — 科学数据结构/内核封装样本

- **获取方式**：`python scripts/fetch_project.py salome-geom --dest <dir>`（commit `3f85d2e2`）
- **架构分析**：
  - `GEOMImpl` 封装 OCCT 操作（GCS-002/004）
  - `STEPPlugin`/`IGESPlugin`/`BREPPlugin` 数据交换插件（属维度⑧ ACL 防腐范畴，非 GCS-007 网格语义）
- **预期结果**：
  - GCS-002（Handle 一致性）→ 低违规范
  - GCS-004（生命周期）→ 低违规范（Handle 封装）
  - GCS-012（数据访问封装）→ 低违规范（模块化良好）
  - GCS-007/008 → **不适用**（STEP/IGES 为外部数据交换，归 ACL；GCS-007/008 覆盖由合成样本 4.7 承担）

> **样本调整说明（专家校对 P1-5 修订）**：SALOME GEOM 的 STEP/IGES 插件为**外部标准数据交换**（维度⑧ ACL 范畴），非"VTK/OpenFOAM 网格语义混用"（GCS-007 本意）。故 A-2 不再声称覆盖 GCS-007/008，改由新增合成样本（4.7 VTK+OpenFOAM 混用）承担。

### A-3：FreeCAD（兜底）— 内核封装正样本

- **获取方式**：已在 `projects.yaml`（`fetch.repo: FreeCAD`）
- **预期结果**：GCS-002（Handle 一致性）低违规范、GCS-005 中违规范

### A-4：BRL-CAD（兜底）— 实体建模样本

- **获取方式**：已在 `projects.yaml`
- **预期结果**：几何内核使用相关规则触发情况待实测

> **兜底说明**：若 OCCT/SALOME 获取失败（网络/授权），GCS 回归用 FreeCAD/BRL-CAD 兜底（H2 决策 4）。

---

## 二、B 类：参考案例（不可本地复现）

| 案例 | 描述 | 预期 |
|:-----|:-----|:-----|
| ANSYS 几何平台（闭源）| 商业几何内核封装，Handle 智能指针统一管理 | GCS-002/004 低违规范（良好实践参考）|
| CGAL 网格处理 | 无 B-Rep 闭合概念，但有精确/近似内核精度关切 | GCS-005/006 为校准关注点 |

---

## 三、C 类：Validation 案例（6 要素）

### C-1：CAD 几何布尔运算数据一致性（首期）

| 要素 | 内容 |
|:-----|:-----|
| **前情背景** | 某 CAD 平台基于 OCCT 做布尔运算，团队新增多物理场网格导出功能 |
| **关键数据** | 指南输出 GCS-003（异常传播 WARNING）+ GCS-007（网格语义混用 ERROR）告警，维度④ 综合分 55 |
| **用户行为** | 架构师针对 **ERROR 级 GCS-007**（网格语义混用）整改：统一网格封装层，消除跨语义直接索引；对 **WARNING 级 GCS-003** 人工确认并补充关键路径 `IsDone()` 检查 |
| **工具响应** | 复评后 GCS-007 清零、GCS-003 违规范下降，综合分 55 → 72 |
| **业务价值** | 网格语义混用消除、布尔运算失败不再静默，网格导出正确率提升，规避现场崩溃 |
| **推广复制** | 形成"内核调用点失败状态检查 + 网格语义统一"清单，推广到全部几何操作模块 |

---

## 四、合成正负例

> 每个 🟢 规则（GCS-003/007/012）含 1 正例 + 1 负例；每个 🟡 规则含 ≥1 INFO 用例；GCS-001/004/006/011 补 4.9-4.12 合成用例。合成代码片段 50-300 行。

### 4.1 GCS-003 异常/失败状态传播

**负例（触发 GCS-003）**：
```cpp
// bad_boolean.cpp
#include <BRepAlgoAPI_BooleanOperation.hxx>
TopoDS_Shape do_boolean(const TopoDS_Shape& a, const TopoDS_Shape& b) {
    BRepAlgoAPI_BooleanOperation op(a, b);
    return op.Shape();  // 未检查 op.IsDone() → GCS-003 触发
}
```

**正例（不触发）**：
```cpp
// good_boolean.cpp
#include <BRepAlgoAPI_BooleanOperation.hxx>
TopoDS_Shape do_boolean(const TopoDS_Shape& a, const TopoDS_Shape& b) {
    BRepAlgoAPI_BooleanOperation op(a, b);
    if (!op.IsDone())
        throw std::runtime_error("Boolean operation failed");
    return op.Shape();
}
```

### 4.2 GCS-007 网格单元类型一致性

**负例（触发 GCS-007）**：
```cpp
// mixed_semantics.cpp
#include <vtkUnstructuredGrid.h>
#include <gmsh.h>  // gmsh 网格语义引用
class MeshField {
    vtkSmartPointer<vtkUnstructuredGrid> vtk_;
public:
    double cellVolume(int i) {
        // 同一 vtk 数据被直接按 gmsh 单元节点顺序解释，无封装转换 → GCS-007
        vtkCell* cell = vtk_->GetCell(i);
        const double* p0 = vtk_->GetPoint(cell->GetPointId(0));
        return gmsh::model::getMass(0, i, p0);  // 同一数据跨语义直接索引
    }
};
```

**正例（不触发）**：
```cpp
// unified_mesh.cpp
#include <vtkUnstructuredGrid.h>
class MeshAdapter {
    vtkSmartPointer<vtkUnstructuredGrid> vtk_;
public:
    vtkUnstructuredGrid* getVTK() { return vtk_; }  // 统一单语义封装，不直接混用
    // 跨格式转换通过独立转换器（convertToFvMesh 等）完成，归 ACL/MPR-012，GCS-007 豁免
};
```

> **边界说明（专家校对 P0-4 修订）**：GCS-007 仅触发**同一数据表示内的多语义混用**（无转换意图、直接跨语义索引同一数据）。**跨格式转换适配器**（显式函数输入/输出两种网格格式，如 VTK→OpenFOAM 转换器）属维度⑧ ACL 防腐 / MPR-012 格式转换统一性，GCS-007 **豁免**，避免双重计分。

### 4.3 GCS-012 数据访问封装性

**负例（触发 GCS-012）**：
```cpp
// leak.cpp
struct MeshField {
    double* data_;   // 跨模块直接访问内部数据
    int size_;
};
void process(MeshField* f) {
    f->data_[0] = 1.0;  // 直接成员访问 → GCS-012 触发
}
```

**正例（不触发）**：
```cpp
// encapsulated.cpp
class MeshField {
    std::vector<double> data_;
public:
    double at(size_t i) const { return data_.at(i); }
    void set(size_t i, double v) { data_.at(i) = v; }
};
```

### 4.4 GCS-002 Handle 智能指针一致性（🟡 INFO 用例）

**负例（触发 GCS-002）**：
```cpp
#include <Geom_Plane.hxx>
Geom_Plane* get_plane() {
    return new Geom_Plane(gp_Pln());  // 裸 new 内核对象 + return 跨作用域穿越，未用 Handle → GCS-002
}
```

**正例（不触发）**：
```cpp
#include <Geom_Plane.hxx>
Handle(Geom_Plane) get_plane() {
    return new Geom_Plane(gp_Pln());  // Handle 封装（gp_Pln 为合法构造参数）
}
```

### 4.5 GCS-005 硬编码精度/容差魔法数字（🟡 INFO 用例）

**负例（触发 GCS-005）**：
```cpp
#include <BRep_Tool.hxx>
double tolerance_ok(double d) {
    return std::abs(d) < 1e-6;  // 硬编码容差魔法数字 → GCS-005 (INFO)
}
```

**正例（不触发）**：
```cpp
#include <BRep_Tool.hxx>
constexpr double GEOM_TOLERANCE = 1e-6;
double tolerance_ok(double d) {
    return std::abs(d) < GEOM_TOLERANCE;  // 命名常量
}
```

### 4.6 GCS-010 裸数组替代科学数据结构（🟡 INFO 用例）

**负例（触发 GCS-010，密度阈值内）**：
```cpp
#include <vtkUnstructuredGrid.h>
#include <vector>
// 科学数据结构与裸数组并存，裸数组占比 > 阈值 → GCS-010
double* coords;                       // 裸数组（核心数据容器）
std::vector<int> cell_ids;            // 科学数据结构引用
double* normals;                      // 另一处裸数组
// 文件内裸数组声明占比过高 → 触发 GCS-010 (INFO)
```

**正例（不触发）**：
```cpp
#include <vtkUnstructuredGrid.h>
vtkSmartPointer<vtkPoints> coords;   // 用科学数据结构封装核心数据
// 纯裸数组场景（无科学数据结构引用）亦不触发（不评判选型）
```

### 4.7 GCS-008 场量组织一致性（🟡 INFO 用例）

**负例（触发 GCS-008）**：
```cpp
#include <vtkUnstructuredGrid.h>
// 按点/按单元场量命名混用 → GCS-008
vtkFieldData* pointData;   // 按点场量
vtkFieldData* cellField;   // 按单元场量（命名与 pointData 体系不一致）
double* cellFieldData;     // 场量容器命名漂移
```

**正例（不触发）**：
```cpp
#include <vtkUnstructuredGrid.h>
// 命名规则一致：pointData/cellData 统一前缀
vtkFieldData* pointData;   // 按点
vtkFieldData* cellData;    // 按单元
```

### 4.8 GCS-009 网格/场量维度匹配（🟡 INFO 用例）

**负例（触发 GCS-009）**：
```cpp
#include <vtkUnstructuredGrid.h>
constexpr int STRESS_COMPONENTS = 6;   // 文件内命名分量常量（可检信号）
size_t n_vertices = grid->GetNumberOfPoints();
double* coords   = new double[n_vertices * 3];          // 坐标 3 分量，正确
double* stresses = new double[n_vertices * 3];          // 应力应 * STRESS_COMPONENTS(6) 却 *3 → 维度因子与命名常量不一致
// 启发式：裸数组维度魔法因子（3）与同文件命名分量常量（6）不一致 → GCS-009 (WARNING, 低置信度)
```

**正例（不触发）**：
```cpp
#include <vtkUnstructuredGrid.h>
constexpr int STRESS_COMPONENTS = 6;
size_t n_vertices = grid->GetNumberOfPoints();
double* stresses = new double[n_vertices * STRESS_COMPONENTS];  // 维度因子与命名常量一致
// 或直接用带维度的科学数据结构（vtkDataArray 自带分量数）
```

### 4.9 GCS-001 内核闭合性校验测试存在性（加分项）

**负例（缺失 → INFO 提示）**：
```cpp
// no_closure_check.cpp
#include <BRepAlgoAPI_Fuse.hxx>
TopoDS_Shape fuse(const TopoDS_Shape& a, const TopoDS_Shape& b) {
    BRepAlgoAPI_Fuse op(a, b);
    if (!op.IsDone())
        throw std::runtime_error("Fuse failed");
    return op.Shape();   // 无 BRepCheck_Analyzer 闭合性校验测试 → GCS-001 缺失提示 (INFO)
}
```

**正例（存在 → 加分）**：
```cpp
// with_closure_check.cpp
#include <BRepAlgoAPI_Fuse.hxx>
#include <BRepCheck_Analyzer.hxx>
bool is_valid_after_fuse(const TopoDS_Shape& s) {
    BRepCheck_Analyzer analyzer(s);   // 闭合性校验测试存在 → GCS-001 加分
    return analyzer.IsValid();
}
```

### 4.10 GCS-004 内核对象生命周期（同作用域 new/delete）

**负例（触发 GCS-004）**：
```cpp
// manual_lifetime.cpp
#include <Geom_Plane.hxx>
void use_plane() {
    Geom_Plane* plane = new Geom_Plane(gp_Pln());  // 同作用域手动 new
    // ... 使用 ...
    delete plane;   // 手动 delete → GCS-004 (WARNING)，未用 Handle 自动管理
}
```

**正例（不触发）**：
```cpp
#include <Geom_Plane.hxx>
void use_plane() {
    Handle(Geom_Plane) plane = new Geom_Plane(gp_Pln());  // Handle 自动管理生命周期
}
```

### 4.11 GCS-006 单位换算魔法因子（🟡 INFO 用例）

**负例（触发 GCS-006）**：
```cpp
// unit_factor.cpp
#include <BRep_Tool.hxx>
double inch_to_mm(double inches) {
    return inches * 25.4;   // 魔法因子，未调用统一换算函数 → GCS-006 (INFO)
}
```

**正例（不触发）**：
```cpp
double inch_to_mm(double inches) {
    return unit::convert(inches, unit::Inch, unit::MM);   // 统一换算工具函数
}
```

### 4.12 GCS-011 深拷贝 vs 浅拷贝（🟡 INFO 用例）

**负例（触发 GCS-011）**：
```cpp
// shallow_copy.cpp
#include <vtkUnstructuredGrid.h>
class MeshView {
    vtkSmartPointer<vtkUnstructuredGrid> grid_;   // 浅拷贝共享底层缓冲
public:
    MeshView(vtkUnstructuredGrid* g) : grid_(g) {}  // 共享同一网格，修改互相影响 → GCS-011 (INFO)
};
```

**正例（不触发）**：
```cpp
#include <vector>
class MeshField {
    std::vector<double> data_;
public:
    MeshField() = default;
    MeshField(const MeshField& other) : data_(other.data_) {}  // 显式深拷贝，独立数据
};

---

## 五、规则覆盖矩阵（KPI1 对齐）

| 规则 | A 类真实 | B 类 | C 类 | 合成正例 | 合成负例 | INFO 用例 |
|:----:|:--------:|:----:|:----:|:--------:|:--------:|:---------:|
| GCS-001 | ✅(occt) | | | ✅(4.9) | ✅(4.9) | |
| GCS-002 | ✅(occt) | | | ✅(4.4) | ✅(4.4) | ✅ |
| GCS-003 | ✅(occt) | | | ✅(4.1) | ✅(4.1) | |
| GCS-004 | ✅(occt) | | | ✅(4.10) | ✅(4.10) | |
| GCS-005 | ✅(occt) | ✅ | | ✅(4.5) | ✅(4.5) | ✅ |
| GCS-006 | ✅(occt) | ✅ | | ✅(4.11) | ✅(4.11) | ✅ |
| GCS-007 | | | | ✅(4.2) | ✅(4.2) | |
| GCS-008 | | | | ✅(4.7) | ✅(4.7) | ✅ |
| GCS-009 | | | | ✅(4.8) | ✅(4.8) | ✅ |
| GCS-010 | | | | ✅(4.6) | ✅(4.6) | ✅ |
| GCS-011 | | | | ✅(4.12) | ✅(4.12) | ✅ |
| GCS-012 | ✅(salome) | | | ✅ | ✅ | |

> **覆盖说明（专家校对 P1-5 修订）**：GCS-007/008/009/010 覆盖由**合成样本**承担（A 类中 salome-geom 的 STEP/IGES 为外部数据交换归 ACL，OCCT 不含网格语义混用场景）。GCS-012 由 salome-geom（模块化封装良好）覆盖。GCS-001/004/006/011 合成用例补全（4.9-4.12），**12 条规则均有 ≥1 验证用例**。

> 覆盖口径：12 条 GCS 每条 ≥1 验证用例（对齐 H2 KPI1）。KNOWN_HOLES 2（欧拉/闭合性运行时）注册进 consistency_check（WP-2 B4）。

---

*本案例集为维度④ 标准文档包组成部分，A 类对接 WP-0.5 `fetch_project.py` 固定 ref，供 WP-2 B3.5 对照验证。*
