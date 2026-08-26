# WP-3 性能优化报告

> **版本**：v1.0
> **日期**：2026-08-25
> **归属**：H1 v3 → WP-3 性能优化 + profile 方案评估
> **对照**：WP-0 基线（`docs/zh/计划/H1基线实测报告.md`）

---

## 一、优化成果总览

| 指标 | WP-0 基线 | WP-3 优化后 | 提升 |
|:-----|:---------:|:-----------:|:----:|
| FreeCAD src multilang 引擎 | ~4h（14400s）| **578.6s** | **~25x** |
| FreeCAD src ComprehensiveReport 全量 | ~4h | **692s（11.5min）** | **~21x** |
| FreeCAD Fem multilang | 125s | **48.6s** | **2.6x** |
| OpenFOAM-apps multilang | ~31s | **19s** | **1.6x** |
| FreeCAD-CAM multilang | ~50s | **19s** | **2.6x** |

**评分一致性**：优化前后 overall 一致（FreeCAD src 58.25、FreeCAD Fem 62.13），无功能回归。

> **注**：全量从 v1 报告的 1030s 进一步降至 692s——因 WP-3i 定位并修复了标准引擎 `check_sar_rules()` 重复计算所有维度的缺陷（见 §五）。

## 二、优化内容

### 1. O(n²) → 哈希索引（核心，WP-3b/c）

WP-0 定位的 4 处超线性热点全部修复：

| 热点 | 原复杂度 | 修复 |
|:-----|:---------|:-----|
| `_py_imports_cpp`（calc_call_depth）| O(py_imports × cpp_files) | `cpp_base_lookup` 哈希索引 → O(1) |
| `_build_ctype_edges`（ctypes 匹配）| O(func × header_files) | `func_to_files` 反向索引 → O(1) |
| `_build_cross_lang_graph`（ctypes/.def/import）| 4 处 O(func × header) | `func_to_headers` 反向索引 → O(1) |
| `_resolve_pyimport_module`（PyImport 解析）| O(module × py_files × 读盘) | 路径哈希 + basename 索引 + 内容缓存 → O(1)+ |

### 2. 内容缓存（WP-3b 补充）

`read_text_smart(use_cache=True)` 新增进程内缓存（按 mtime 失效），消除多引擎/多规则重复读盘（OpenFOAM 2047 文件原读 15852 次）。

### 3. 过滤策略（WP-3d）

- **EXCLUDE_DIRS 扩展**：`third_party/thirdparty/vendor/extern/external/deps/dependencies`
- **生成文件过滤**：`_is_generated_file()`（flex `lex.yy.c`、bison `y.tab.c`、Qt `moc_*` 等）
- **Fortran SyntaxWarning 抑制**（DEBT-1）：`warnings.filterwarnings("ignore", SyntaxWarning)`
- **效果**：FreeCAD src 7590→7519 文件（排除 71 生成文件）；BRL-CAD 第三方 Fortran 排除

### 4. FileIndex 增量扫描（WP-3e）

`FileIndex(root, cache_file)` 支持：首次全量扫描写 JSON 缓存，目录未变时二次加载 O(0)（0.38s→0.00s）。

### 5. 标准引擎 SAR 重复计算修复（WP-3i）

**问题**：`all_metrics()` 算完 4 维度后，`check_sar_rules()` 又独立重复调用所有 `calc_*` 维度，导致 standard 引擎在 CAM（600 文件）耗时 88s。

**修复**：`all_metrics` 将维度结果存 `_dim_cache`，`check_sar_rules` 从缓存复用（structural 立即缓存供 `calc_problem_deduction` 用）。CAM standard 88s → 31.8s（-64%）。

## 三、回归验证（无副作用）

| 套件 | 结果 |
|:-----|:-----|
| 全量非回归 | **426 passed** |
| 多语言回归 | 30 passed（快照更新：BRL-CAD 第三方 Fortran 过滤）|
| 标准回归 | 20 passed |
| 合成项目测试 | 6 passed |

**基线更新说明**（合理行为变化）：
- BRL-CAD Fortran 4→2（排除第三方 liblbfgs 的 .f），MLR-012 覆盖改由 ElmerFEM 提供
- FreeCAD-Fem MLR-005 10→2（`_resolve_pyimport_module` 解析更精确）

## 四、KPI2 达标评估

**KPI2**：FreeCAD `src/` 全量（12417 文件），声明机型/冷缓存下 P90 < 10 分钟。

| 项 | 值 | 判定 |
|:---|:---|:-----|
| 全量 ComprehensiveReport | 692s（11.5min）| ⚠️ 接近但未达 P90<10min |
| 其中 multilang 引擎 | 578.6s（9.6min）| ✅ 单引擎已达标 |
| 其他 4 引擎合计 | ~250s（含 numerical 204s）| 需进一步优化 |

**结论**：KPI2 **接近达标**（4h → 11.5min，21x）。剩余 ~92s 瓶颈：multilang AST 解析 + numerical 204s。三增强引擎（numerical/template/solver_physics）在 FreeCAD src 均激活（无法跳过），需引擎内优化。

## 五、5 回归项目性能对比（WP-3h）

| 项目 | WP-0 基线 | WP-3 后 | 变化 | 劣化≤20% |
|:-----|:---------:|:-------:|:----:|:--------:|
| OpenFOAM-v2512 | 447.7s | 507.4s | +13.3% | ✅ |
| BRL-CAD | 259.6s | 285.8s | +10.1% | ✅ |
| FreeCAD-CAM | 56.3s | 72.2s | +28.3% | ❌ |
| FreeCAD-Fem | 133.6s | 108.9s | **-18.5%** | ✅ |
| ElmerFEM | 314.1s | 299.6s | **-4.6%** | ✅ |

**说明**：3/5 项目劣化在 20% 内，Fem/ElmerFEM 已快于基线。CAM +28% 超线——根因是 **WP-1/2 将 standard 引擎从占位实现为真实检测**（SOLID/文档/演进真实计算取代固定值），属功能增强带来的计算成本，非性能优化退化。CAM multilang 本身已 15s（优化前 ~50s）。

## 六、后续建议

- **multilang AST 解析优化**（FreeCAD src 578s 内）：`extract_pybind11_calls`/`find_malloc_tokens` 对每文件 AST 遍历 ~200s，可 AST 结果缓存或限制解析范围
- **numerical 204s**：扫描可复用 FileIndex 缓存 / 过滤
- **WP-5 门禁**：将 `gen_rule_coverage_matrix.py --check` + 回归快照校验纳入 CI
- **H2**：显式 profile（见 `docs/zh/计划/显式Profile方案评估.md`）——FreeCAD src 三增强引擎全激活无法跳过，但对多数项目可省非适用引擎

**预期**：AST 缓存 + numerical 优化后，全量可进 10min（KPI2 完全达标）。

---

*本报告基于 Windows（Intel i3-8130U 2C/4T，12GB RAM），与 WP-0 同机型，可直接对比。*