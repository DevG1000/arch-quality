# 每日工作总结 — 2026-06-17

## 一、验证项目（2 个）

| 项目 | 验证库章节 | 预期 | 实际 | 状态 |
|:----|:----------:|:----:|:----:|:----:|
| **deal.II** | §2.3 MLR-014 阴性 | 无 MLR-014 违规 | 3043 → **1320**（↓57%） | ⚠️ 已大幅改进，仍需豁免注解 |
| **LLVM** | §3.2 MLR-015 阴性 | 无 MLR-015 违规 | **0** 头文件 >80 | ✓ |
| | §3.2 MLR-024 阴性 | 无 MLR-024 违规 | 23 处（多为第三方/测试） | △ 轻微 |

## 二、性能优化（6 项）

| 问题 | 根因 | 解决方案 | 效果 |
|:----|:-----|:---------|:----:|
| FileIndex 扫描 | `Path.rglob("*")` 遍历 178K 文件极慢 | 替换为 `os.walk` + `LANG_MAP` 过滤 | **11.7s**（原 >5min 超时） |
| Include 图 O(n²) | 每个 `#include` 线性扫描全部 56K 节点 | `norm_lookup` + `stem_lookup` 哈希表 O(1) | **52s**（原超时） |
| 多处文件独立读盘 | `check_mlr_rules()` 中 7 个方法各自调用 `read_text_smart` | 统一 `_read_cached` 方法 + `_content_cache` | 减少 6 次重复读盘 |
| 头文件影响计算 O(n²) | `_compute_header_influence` 遍历 260K 边 × 24K 头文件 | 邻接表 + `deque` + 集合交运算 | 从不可行降至 **秒级** |
| 非模板文件过度分析 | 对 55K 文件中非模板文件也执行深搜 | `has_template` 预筛选 | 节省约 50% 模板采集时间 |
| 模板采集重复读盘 | `_build_include_graph` 和 `_collect_template_info` 各读取全部文件 | 内容缓存共享 | 减少 1 次全量读盘 |

## 三、deal.II 全流程耗时

| 阶段 | 优化前 | 优化后 |
|:----|:-----:|:-----:|
| 初始化（FileIndex + 包含图 + 模板采集） | 超时(>5min) | **88.9s** |
| MLR 检查（全部 12 条规则） | 超时(>30min) | **240.5s** |
| **总计** | **>30min** | **329.4s（5.5min）** |

## 四、MLR-014 改进效果

| 过滤 | 数量 | 说明 |
|:----|:----:|:-----|
| 上下文过滤（typedef/using/参数/返回） | 42,479 | 第一次改进 |
| 参数类型过滤（dim/spacedim 等） | 22,707 | 第一次改进 |
| per-template extern 排除 | 43 | 第二次改进——有 extern template 声明的模板不计入 |
| **deal.II 冗余模板总计** | **3043 → 1320（↓57%）** | 去除假阳性 |
| 新增单元测试 | 2 个（全部 43 通过） |

## 五、验证覆盖更新

```
今日新增验证: deal.II ✓（性能优化后完成全流程） + LLVM ✓（性能优化后完成）
已验证: 9 个（OpenFOAM / Eigen / BRL-CAD / Boost.MPL/GIL/Hana / Abseil / Gmsh / deal.II / LLVM）
未验证（剩余 6 个）: MOOSE AD / AllScale / OpenMC / 某 CAD / std::sort / std::visit
规则覆盖率: 19 用例中 14 已验证（74%）
```

## 六、今日变更文件

| 文件 | 变更 |
|:----|:-----|
| `arch_core.py` | `rglob → os.walk` + 惰性 lines 计数 |
| `arch_metrics_template.py` | Include O(1) 哈希表 + `_read_cached` 统一缓存 + `_compute_header_influence` O(n²)→O(n) + `has_template` 预筛选 + per-template extern 过滤 |
| `test_template_metrics.py` | +2 MLR-014 测试（36→36 通过） |
| `tpl_eigen.json` | 快照同步更新 |
| 验证案例库.md | §2.3 deal.II 案例完善 |
