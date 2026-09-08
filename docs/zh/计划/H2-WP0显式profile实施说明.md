# H2 WP-0 显式 Profile 实施说明

> **版本**：v1.0
> **日期**：2026-09-07
> **归属**：H2 扩展化执行计划 v2 → WP-0 显式 profile 实施（W1-W2）
> **状态**：实施完成，本文件含过渡口径说明 + 时预算算术表（KPI5 X 定值）

---

## 一、交付内容

| 交付物 | 状态 | 说明 |
|:-------|:----:|:-----|
| `arch-quality.yaml` 解析 + schema 校验 | ✅ | `arch_core.py:load_profile_config`，支持 `pyproject.toml [tool.arch-quality]` 兜底 |
| `ComprehensiveReport` 引擎选择（profile 优先）| ✅ | `arch_report.py:generate`，仅运行启用引擎 |
| CLI `--profile`（覆盖配置文件）| ✅ | `arch_report.py:main`，优先级 `--profile` > 配置文件 |
| 回归测试（各 profile 组合 + 配置缺失兜底）| ✅ | `tests/test_profile.py`（26 用例）|
| 过渡口径说明 | ✅ | 本文件 §三 |
| 时预算算术表（KPI5，X 定值）| ✅ | 本文件 §四 |

---

## 二、配置语义

### 2.1 配置文件

```yaml
# arch-quality.yaml（项目根目录）
profile: numerical              # standard / multilang / numerical / template / solver-physics
enable_engines:                 # 显式启用引擎（未列出的跳过；standard 自动补齐）
  - standard
  - numerical
skip_engines:                   # 显式排除（不可排除 standard）
  - solver-physics
test_dirs:                      # out-of-tree 测试目录（等价 CLI --test-dirs）
  - tutorials
```

或 `pyproject.toml`：

```toml
[tool.arch-quality]
profile = "template"
skip_engines = ["solver-physics"]
```

优先级：`arch-quality.yaml` > `pyproject.toml [tool.arch-quality]`。

### 2.2 引擎解析优先级

```
profile > enable_engines > skip_engines > 全量
```

- `profile` 声明 → 该 profile 的引擎集（standard + 对应增强引擎）
- 否则 `enable_engines` → standard + 显式列表
- 否则 `skip_engines` → 全量减排除集
- 均未声明 → 全量
- `skip_engines` 在任意路径上做减法；`standard` 始终强制（schema 校验拒绝排除）

### 2.3 无配置文件 → 启发式兜底

无配置文件时保持既有行为（向后兼容）：运行全部引擎，由检测信号（单语言/C++/数值/多物理场）决定各增强引擎是否参与评分。

### 2.4 schema 校验

- `profile` 枚举校验；`enable_engines`/`skip_engines` 引擎名校验
- 排除 `standard` → 拒绝
- 未知配置键 → 拒绝
- 非法配置 → `ValueError`，CLI 退出码 1

---

## 三、过渡口径（决策 8b）

激活子集全局归一化实施归 H3（`权重归一化模型重做方案.md`）。H2 内采用**过渡口径**：

1. **子集评分标注**：profile 激活且跳过 ≥1 增强引擎时，报告标注 `subset_scoring: true`，`note` 声明"profile 子集评分仅基于已启用引擎"。
2. **并列展示**：报告 `dimensions.structural.skipped_enhancements` 列出被跳过引擎及其状态 `not_evaluated`，与已评估维度并列，不隐去。
3. **禁止混合计分**：子集 structural 分仅由启用引擎权重合成；`structural_note` 附加 `[profile 子集评分：启用 X，跳过 Y]` 标注，提示与全引擎评分不可直接比较。
4. 全引擎模式（无 profile / profile 覆盖全部引擎）→ `subset_scoring: false`，为正常全量评分。

报告 `profile` 元数据结构：

```json
{
  "active": true,
  "config_source": ".../arch-quality.yaml",
  "profile": "numerical",
  "enable_engines": null,
  "skip_engines": null,
  "enabled_engines": ["numerical", "standard"],
  "skipped_engines": ["multilang", "template", "solver-physics"],
  "subset_scoring": true,
  "note": "过渡口径（H2 WP-0，决策 8b）：profile 子集评分仅基于已启用引擎，与全引擎评分并列展示、禁止混合计分；激活子集全局归一化实施归 H3。"
}
```

---

## 四、时预算算术表（KPI5）

### 4.1 基准（FreeCAD src，H1 收尾 560.0s < 600s，KPI2 达标）

| 引擎 | FreeCAD src 实测耗时 | 数据来源 |
|:-----|:----:|:---------|
| standard（必配）| ~145s | WP3 性能优化报告（standard src 147s，H1 收尾推算 ~145s）|
| multilang | ~225s（560 全量推算）| H1closeout（WP3 记录 336s，收尾后 ~225s）|
| numerical | 101s | H1closeout KPI2 收尾（166s → 101s，-39%）|
| template | ~52s | `显式Profile方案评估.md` §二 |
| solver-physics | ~37s | `显式Profile方案评估.md` §二 |
| GCS（H2 WP-2 新增）| 预算 ≤X | 待落地测量 |
| ACL（H2 WP-4 新增）| 预算 ≤X | 待落地测量 |

### 4.2 每引擎增量预算 X 定值

**X = 120 秒/引擎**（每启用一个增强引擎，相对 standard-only 基线的增量 ≤120s）。

推导依据：

1. H1 KPI2 全量预算 600s，引擎 5 个（含 standard）→ 600/5 ≈ 120s/引擎，取整为 120s。
2. H2 新增 GCS/ACL 后引擎数升至 7，全量预算若沿用 600s 算术上不可行（评审意见 7）；故以**单引擎增量预算**为门禁，全量预算不再作为单一口径（用户可用 profile 跳过非适用引擎控制全量耗时）。

### 4.3 算术验证

```
T_full(FreeCAD, 含 GCS/ACL) = T_standard + Σ(每引擎增量)
                            = 145s + 101s + 52s + 37s + 225s + X_gcs + X_acl
                            ≈ 560s + X_gcs + X_acl        （H1 收尾基线 560s）

每引擎增量预算：X_numerical=101s ≤120s ✅
                X_template=52s  ≤120s ✅
                X_solver-physics=37s ≤120s ✅
                X_multilang≈225s >120s ⚠️ 已知超预算引擎
                X_gcs ≤120s（WP-2 验收）   🔲
                X_acl ≤120s（WP-4 验收）   🔲
```

**multilang 说明（评审意见 7 落地）**：multilang 是 FreeCAD 级多语言项目最重引擎（4h 优化至 ~225s，22x）。其成本受 H1 KPI2 全量 600s 总预算约束（当前 560s 达标），单引擎增量超 120s 登记为**已知超预算引擎**，引擎级专项优化归 H3；H2 内不阻塞 KPI5（KPI5 门禁对象为 H2 新增引擎 GCS/ACL + profile 跳过收益）。

### 4.4 验收判据（WP-9 closeout 取证）

1. **profile 跳过收益单独测**：FreeCAD 基线（含 GCS/ACL）上测 `T_full` 与 `T_subset`（如 numerical-only profile），验证 `T_full - T_subset = Σ(被跳过引擎耗时)`，逐引擎独立测量（mock 禁用其他引擎）。
2. **每引擎增量预算**：GCS ≤120s（WP-2 收尾）、ACL ≤120s（WP-4 收尾）为硬门禁；既有引擎中 numerical/template/solver-physics 已达标，multilang 登记为已知超预算（H3）。
3. **纯数值项目**：`profile: numerical` 仅跑 standard+numerical（跳过 multilang/template/solver-physics），已在 `tests/test_profile.py` 验证引擎不执行。

---

## 五、遗留 / 后续

| 项 | 归属 |
|:---|:-----|
| 激活子集全局归一化（profile 子集评分语义定案）| H3 |
| multilang 单引擎增量优化（>120s）| H3 |
| GCS/ACL 引擎接入 profile（新增引擎名入 schema）| WP-2 / WP-4 |
| 参考 `config_source` 展示优化 | H3 |

---

*H2 WP-0 显式 profile 实施完成，可进入 WP-0.5/WP-1。*