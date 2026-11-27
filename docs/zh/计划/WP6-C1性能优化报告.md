# WP-6 C1：multilang 性能优化报告

> **版本**：1.0
> **日期**：2026-11-24
> **目标**：FreeCAD `src/` multilang 单引擎 262.9s → ≤120s
> **结果**：**P50 80.7s / P90 81.0s，达标**

## 1. 基准与结果

环境：2C/4T，Python 3.14.3，FreeCAD `src/`。

| 项 | 优化前 | 优化后 |
|:--|--:|--:|
| multilang total | 264.1s | **80.7s（P50）** |
| P90 | — | **81.0s** |
| 目标 | ≤120s | ✅ |

3 次实测：80.7s / 78.0s / 81.0s。

## 2. cProfile 热点（优化前）

cProfile 总耗时 319s（含 profiler 开销）：

| 热点 | 累计耗时 | 根因 |
|:--|--:|:--|
| `calc_call_depth` | 120s / 2 次 | `all_metrics` 与 `check_mlr_rules` 重复计算 |
| `_build_cross_lang_graph` | 100s | 全量文件重复读取、线性匹配 |
| `read_text_smart` | 96s / 187k 次 | 每次 stat + 读取 |
| `check_mlr_rules` | 90s | 多轮全文件扫描 |
| `is_single_language` | 25s / 1703 次 | 每次遍历全部节点 |
| `cross_successors` | 27s / 41k 次 | 每次线性扫描 cross_edges |
| `bfs_reachable` | 18s / 15k 次 | 每次线性扫描 edges |
| `_py_imports_cpp` | 51s / 119k 次 | 重复解析 Python import |

## 3. 已实施优化

### C1.2 `DepGraph` 邻接索引

`src/arch_quality/arch_core.py`：

- `add_edge` 同步维护 `_succ/_pred/_cross_succ/_cross_pred`；
- `successors/predecessors/cross_*` 从 O(E) 降为 O(1)；
- `is_single_language` / `languages` 增加缓存，`add_node` 时失效；
- `bfs_reachable` 使用邻接表 + `deque`。

### C1.3 维度 memoize

`src/arch_quality/arch_metrics_multilang.py`：

- 新增 `_calc_cached(name, fn)`；
- `all_metrics` 的 6 个维度全部走缓存；
- `check_mlr_rules` 复用 `call_depth` / `coupling` / `impact`，消除重复计算。

### C1.6 回调深度 BFS 剪枝

- 只从跨语言边端点出发，不再遍历所有节点；
- 使用 predecessor 记录路径，避免每次入队复制 `path` 列表；
- 最大深度与路径语义保持不变。

### C1.1 文件快照缓存

- `MultilangMetrics._read_text()` 单次评估内按绝对路径缓存；
- 替换类内所有 `read_text_smart` 调用；
- 避免 187k 次重复 stat/read。

### C1.5 索引化匹配

- Fortran basename 索引（first-wins，保持旧顺序）；
- C++ basename 索引；
- Tcl `package require` 直接查表；
- `_py_imports_cpp` 按 Python 文件缓存结果。

> C1.4“MLR 单次扫描 FileFacts”未实施：快速项已达到 80.7s，继续改造收益低且风险高，留作后续可选优化。

## 4. 正确性验证

| 验证 | 结果 |
|:--|:--|
| 多语言单元测试 | 136 passed, 1 skipped |
| standard/绑定/功能测试 | 114 passed |
| multilang 回归（5 项目） | 26 passed, 4 skipped |
| FreeCAD overall | 58.25（与优化前一致） |

未修改任何规则、权重、阈值或快照。

## 5. 风险与回退

| 风险 | 缓解 |
|:--|:--|
| 文件缓存跨运行脏数据 | 仅进程内，不持久化 |
| 图索引与 `edges` 不一致 | `add_edge` 单点维护；回归覆盖 |
| BFS 剪枝改变路径 | 回归/输出对比；最大深度保持一致 |
| basename 重复 | Fortran 使用 first-wins，保持旧遍历顺序 |
| 后续规则新增依赖全量扫描 | 再评估 C1.4 |

## 6. 结论

C1 达标：**264.1s → 80.7s（P50），下降约 69%**，且 5 项目回归与 FreeCAD 总分不变。
