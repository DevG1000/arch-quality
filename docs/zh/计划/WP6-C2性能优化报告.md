# WP-6 C2：standard SOLID / anti-pattern 性能优化报告

> **版本**：1.0
> **日期**：2026-11-24
> **目标**：standard design 路径降低 ≥10s；主目标 P50 ≤30s
> **结果**：**P50 27.2s / P90 31.8s；design 分数 72.33 不变**

## 1. 基准与结果

FreeCAD `src/`，2C/4T，Python 3.14.3：

| 项 | 优化前 | 优化后 |
|:--|--:|--:|
| `calc_design_score` | **63.9s** | **27.2s（P50）** |
| P90 | — | **31.8s** |
| 3 次实测 | — | 27.2s / 31.8s / 26.3s |
| design 分数 | 72.33 | **72.33** |
| 收益 | — | **−36.7s（约 −57%）** |

cProfile 下 design 80.0s → 42.8s；profiler 有额外开销，占比可参考。

## 2. 优化前热点

| 热点 | 累计耗时 | 根因 |
|:--|--:|:--|
| `calc_anti_pattern_score` | 48.6s | 全文件扫描 + 大量正则 + Long Method |
| `_has_long_method` | 17.9s | 短文件也逐行 `strip/lstrip` |
| `calc_pattern_score` | 18.6s | 12 模式 × 全文件，每模式重复 `lower()` |
| `read_text_smart` | 14.9s / 41k 次 | 重复 stat/read |
| `calc_solid_score` | 12.7s | 每 OO 文件多正则 |

## 3. 已实施优化

### C2.1 Standard 内容快照

- `StandardMetrics._read_text()` 单次评估内按绝对路径缓存；
- 类内 design/doc/evolution 的 `read_text_smart` 统一走快照。

### C2.2 `_has_long_method` 快速路径

- `len(lines) <= 100` 直接返回 False；
- 空行用 `line.isspace()` 快速跳过；
- 保留原有“连续同缩进 >100 行”语义。

### C2.3 anti-pattern 热点改造

- `class` / 方法计数 / 硬编码正则提升为模块级 `re.compile`；
- God Class 先判断文件是否含 `class`，避免无类文件进入 class 扫描；
- 类行数用换行计数，避免重复 `splitlines()`；
- 硬编码先做 `password` / `api_key` / IP 子串预筛。

### C2.4 pattern 单文件共享扫描

- 从“每个模式遍历全文件”改为“每个文件只 lower 一次，匹配 12 个模式”；
- 每个模式增加廉价关键字预筛，最终仍用原正则；
- 保持 `patterns` 输出顺序与旧逻辑一致。

### C2.5 SOLID 预编译/预筛

- 7 个 SOLID 正则提升为模块级常量；
- 使用内容小写缓存，避免每文件重复 `lower()`；
- 移除原 `class implements/extends` 分支中的空 `finditer` 循环（无副作用）。

### C2.6 共享 lower 缓存

- `_lower_cache` 按文件缓存小写内容；
- SOLID / pattern / anti-pattern 共用，减少 36k 次 `content.lower()`。

## 4. 正确性验证

| 验证 | 结果 |
|:--|:--|
| standard 单测 | **65 passed** |
| FreeCAD design 分数 | 72.33（与优化前一致） |
| BRL-CAD design | 66.80 vs 快照 66.80 |
| FreeCAD-CAM design | 67.20 vs 快照 67.20 |
| OpenFOAM design | 61.37 vs 快照 61.37 |
| ElmerFEM design | 69.30 vs 快照 69.30 |

> standard 全量回归中 evolution 维度与 arch-quality 文件数仍会因 Git 时间窗口/仓库新增文件漂移；本次 C2 的 design 维度在 4 个快照项目上 delta=0.0，未引入语义变化。

## 5. 风险与回退

| 风险 | 缓解 |
|:--|:--|
| 预筛漏模式 | 预筛只做加速，最终仍跑原正则；快照 delta=0 |
| 长方法快速路径改变语义 | 仅跳过 ≤100 行文件，数学等价 |
| lower 缓存脏数据 | 单次评估进程内缓存 |
| pattern 顺序变化 | 最终按 `_DESIGN_PATTERNS` 原顺序输出 |

## 6. 结论

C2 达到最低目标并超过主目标 P50：

- design **63.9s → 27.2s（P50）**；
- P90 31.8s，接近 30s 目标；
- 4 个 standard design 快照项目分数完全一致。
