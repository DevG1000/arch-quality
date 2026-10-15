# WP-5 实例化意图推断 — 假阳性对比报告

> **归属**：H2 WP-5 语义分析（产品层）— 假阳性对比报告（交付物）
> **日期**：2026-10-13
> **基线**：`docs/zh/计划/WP5假阳性基线.json`（引擎升级前）
> **对象规则**：MLR-018（虚泛型 / 镀金模板）
> **验收口径（KPI3）**：模板实例化假阳性降 ≥50%（相对 H1 收尾日 deal.II 基线）；回归评分劣化 ≤20%

---

## 一、目标与范围（H2 v2 钉死）

| 项 | 内容 |
|:---|:-----|
| 主目标 | 模板引擎从"语法扫描"升级为"实例化意图推断"，过滤镀金模板误报 |
| 范围 | ✅ P3 窄定义「类型形参全 + 已用 extern template → 默认豁免」+ MLR-018 单规则升级 |
| 超出范围 | ❌ 隐式实例化全语义（真实调用图推断）→ 列 H3 |

---

## 二、引擎变更（`arch_metrics_template.py` `calc_unnecessary_templating`）

### 2.1 修复模板名关键字误报

`template_decl_pattern` 原以 `template\s*<[^>]*>\s*(?:class|struct|inline)?\s*(\w+)` 提取模板名，对**函数模板**（`template<typename T> void foo()`）会把返回类型关键字误当模板名。

| 误报项 | FreeCAD 计数 |
|:-------|:-----------:|
| `void` | 544 |
| `bool` | 253 |
| `const` | 196 |
| `static` | 124 |
| `auto` | 79 |
| 其他关键字 | ~125 |
| **合计** | **~1,321 / 3,080（43%）** |

**修复**：新增 `cpp_keywords` 集合（60+ C++ 关键字/基本类型），提取模板名时排除；并要求模板名首字符为合法标识符。

### 2.2 窄定义意图推断（P3）

新增 `type_only_names` + `extern_tpl_names` 收集：

```
if 模板参数全为 class/typename（无非类型参数 int N，无默认值）
   AND 模板名 ∈ extern template 声明名:
    → 默认豁免（发布库显式实例化管理，不判镀金）
```

新增 detail 字段 `exempted_by_intent`（豁免计数）。

---

## 三、假阳性对比（MLR-018 计数）

| 项目 | 升级前 | 升级后 | 降幅 |
|:-----|:------:|:------:|:----:|
| **deal.II（KPI3 基线）** | **102,308** | **47,636** | **53.4%** ✅ |
| Eigen | 12,901 | 9,050 | 29.9% |
| OpenFOAM-v2512 | 8,327 | 4,259 | 48.9% |
| Folly | 7,037 | 2,844 | 59.6% |
| Boost.MPL | 4,151 | 4,109 | 1.0% |
| Range-v3 | 2,461 | 1,451 | 41.0% |
| Abseil | 2,581 | 951 | 63.2% |
| FreeCAD | 2,300 | 888 | 61.4% |
| Hana | 2,230 | 501 | 77.5% |
| Boost.GIL | 1,326 | 384 | 71.0% |
| BRL-CAD | 1,041 | 567 | 45.5% |
| ElmerFEM | 185 | 49 | 73.5% |
| **合计** | **146,848** | **72,689** | **50.5%** |

### 判定

- **KPI3 达标**：deal.II 基线降幅 **53.4% ≥ 50%** ✅
- **聚合降幅 50.5%**（12 项目合计）亦达标
- **Boost.MPL 仅 1.0%**：其为模板元编程库，模板名几乎全是真模板（`mpl_::...`），关键字误报本就少——符合预期（该库是模板正样本，非误报高发区）

---

## 四、可靠性验证

| 测试 | 结果 |
|:-----|:-----|
| `tests/test_template_metrics.py`（+4 WP-5 用例）| 40 passed |
| `tests/regression/test_template_regression.py`（12 项目，含新增 deal.II）| **84 passed** |
| 全量非回归 `tests/` | 665 passed（1 transient temp-dir race，单独复跑通过）|
| `consistency_check.py --engine template` | PASS（规则 ID/版本/维度/案例集）|

### 新增单元测试

- `test_keyword_not_counted_as_template_name`：`void`/`bool`/`const` 不作模板名
- `test_extern_template_type_only_exempted`：`template<class T> class Foo; extern template class Foo<int>;` → 豁免
- `test_type_only_without_extern_not_exempted`：对照，无 extern template 不豁免
- `test_non_type_param_not_type_only`：含 `int N` 非类型形参不豁免

---

## 五、回归评分劣化核查（≤20%）

| 项目 | 升级前 overall | 升级后 overall | 劣化 |
|:-----|:-------------:|:-------------:|:----:|
| deal.II | 29.35 | 29.35 | 0% |

> deal.II 的 `unnecessary_templating` 维度前后均因 ratio 过高被 clamp 到 0（得分公式 `100 - ratio*150` 上限扣 100），故 overall 不变。**无劣化**，满足 ≤20% 要求。

---

## 六、文档同步

| 文档 | 变更 |
|:-----|:-----|
| `src/arch_quality/skills/template-metaprogramming.md` | §6 MLR-018 补"实例化意图推断"（关键字过滤 + 窄定义） + 版本历史 4.1 |
| `docs/zh/模板元编程与编译时依赖膨胀评估指南.md` | §2.6 补 WP-5 说明 + 版本历史 2.1（GBK→UTF-8 化）|

---

## 七、遗留（列 H3）

- **隐式实例化全语义**：真实调用图推断（跨 TU 实例化追踪）超出 WP-5 窄定义范围 → H3
- **评分公式未随 FP 调整**：MLR-018 维度分仍 `100 - ratio*150`，deal.II 等大项目恒 clamp 0（FP 降 53% 未体现为分数）——属另一议题，未在本 WP 调整
- **Boost.MPL 类纯模板库**：关键字过滤几乎无效（模板名本就真实），此类库应靠窄定义或人工基线，非误报修复目标

---

*本报告为 H2 WP-5 交付物，对齐《H2扩展化执行计划v2》WP-5 验收口径（KPI3）。*
