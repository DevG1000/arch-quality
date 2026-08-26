# 显式 Profile 方案评估（WP-3f 交付物）

> **版本**：v1.0
> **日期**：2026-08-25
> **归属**：H1 v3 → WP-3 性能优化 + profile 方案评估
> **结论**：推荐"显式 profile 声明 + 启发式兜底"双轨方案，H2 实施

---

## 一、背景与问题

当前工具通过**文件扩展名启发式**自动判定项目 profile：

| 判定 | 信号（arch_report.py） |
|:-----|:----------------------|
| `is_single_language` | 依赖图语言集 ≤1 |
| `has_cpp` | 模板引擎检测 C++ 文件 |
| `has_numerical` | 数值引擎检测数值关键词 |
| `has_multiphysics` | 物理场引擎检测多物理场信号 |

**问题**（WP-3 调研确认）：

1. **误判风险**：启发式基于扩展名/关键词，可能误触发不需要的引擎（如含少量 `.cpp` 的脚本项目被当成 C++ 项目，跑慢的模板引擎）
2. **性能浪费**：每个项目全跑 5 个引擎，即使仅适用 1-2 个；FreeCAD src 的 4h 中非适用引擎也参与
3. **不可解释**：用户无法声明"这是纯数值项目，跳过多语言/模板"，评估范围不可控

## 二、现状启发式成本

FreeCAD src（7590 索引文件）优化前各引擎耗时（WP-0 实测）：

| 引擎 | 耗时 | 适用性 |
|:-----|:----:|:------:|
| multilang | ~4h（优化前）| 适用（多语言）|
| standard | ~14s | 始终适用 |
| numerical | ~253s | 含数值代码 |
| template | ~52s | C++ 项目适用 |
| solver_physics | ~37s | 多物理场适用 |

→ 若显式声明 profile 仅启用适用引擎，可跳过不需要的引擎，叠加性能优化收益。

## 三、方案设计

### 3.1 显式 profile 声明

新增 `arch-quality.yaml`（或 `pyproject.toml [tool.arch-quality]`）配置文件：

```yaml
# arch-quality.yaml
profile: numerical          # 可选: standard / multilang / numerical / template / solver-physics
enable_engines:             # 显式控制引擎（未列出的跳过）
  - standard
  - numerical
skip_engines:               # 显式排除
  - solver-physics
test_dirs:                  # 复用 WP-1 out-of-tree 配置
  - tutorials
```

优先级：`profile` > `enable_engines` > `skip_engines` > 启发式兜底。

### 3.2 启发式兜底

无配置文件时，保留现有扩展名启发式（默认行为，向后兼容）：

```
检测到的 profile → 仅启用对应引擎 + standard（基础维度）
```

### 3.3 判定逻辑（推荐）

```
if 配置文件存在:
    engines = 按 profile / enable_engines / skip_engines 决定
else:
    engines = {standard} ∪ {启发式检测到的增强引擎}
```

## 四、收益分析

| 场景 | 当前 | 显式 profile 后 |
|:-----|:-----|:---------------|
| 纯数值项目 | 全 5 引擎（含模板/多语言）| standard + numerical（跳过 3 个）|
| 多物理场项目 | 全 5 引擎 | standard + solver_physics + multilang |
| 单语言 C 项目 | 全 5 引擎 | standard（跳过 4 个）|

**预期**：非适用引擎全部跳过，配合 WP-3b/c 的 O(n²)→O(1) 优化，FreeCAD 级项目从 4h → 分钟级。

## 五、实施计划（H2）

| 步骤 | 内容 | 涉及 |
|:-----|:-----|:-----|
| 1 | `arch-quality.yaml` 解析器 + schema 校验 | arch_core.py |
| 2 | `ComprehensiveReport` 引擎选择逻辑（profile 优先）| arch_report.py |
| 3 | CLI `--profile` 参数（覆盖配置文件）| arch_report.py |
| 4 | 回归测试：各 profile 组合 + 配置缺失兜底 | test_standard_integration.py |
| 5 | 文档：指南 §2.6 补充 profile 声明说明 | 指南 2.3 |

## 六、风险与缓解

| 风险 | 缓解 |
|:-----|:-----|
| 用户显式声明错误（漏引擎）| `enable_engines` 需含 standard（强制基础维度）|
| 配置文件漂移 | schema 校验 + 示例模板 |
| 与 WP-7 元模型冲突 | profile 声明纳入元模型"验证资产"元素 |

---

*本方案评估完成，H2 按 §五 实施。WP-3 范围内仅评估产出，不改代码（避免与 WP-1 权重解析耦合）。*