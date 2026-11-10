# H3 WP-9 遗留缺陷修复（H2 遗留 G1~G4）

**版本**：v1.0
**日期**：2026-10-21
**归属**：`H3全维化执行计划v2.md` → WP-9（H2 遗留缺陷）
**状态**：实施完成，测试通过

---

## 一、G1 — GCS 启用条件"路径/项目描述"判定（H2-002）

**问题**：`_detect_geometry()` 仅查源码内容，纯路径命名的几何项目不会自动启用。

**修复**（`arch_metrics_geometry_consistency.py`）：
- 新增 `GEOMETRY_PATH_KEYWORDS = ("occt","opencascade","open_cascade","cascade","brep")` 与 `_path_geometry_signal()`。
- `_detect_geometry()` 改为 **路径信号 OR 内容信号**：根路径/相对目录名含关键词即启用。

**文档**：GCS Skill §9 与指南 §八 "实现现状" 更新为"已实现（H3 G1）"，H2-002 闭环。

## 二、G2 — GCS §2.1 表述与实现对齐（H2-003）

**问题**：Skill §2.1 / 指南 §2.1 声称检测 `IsDone()/IsNull()/!IsValid()`，实现 `DONE_CHECK_RE` 仅覆盖 `IsDone()` + `catch`。

**修复**：文档对齐实现 —— 检测表述改为 `IsDone()` 或 try/catch；建议修复改为"检查 `IsDone()`"。无代码/评分变更。

## 三、G3 — `@kernel_exempt` / `@acl_exempt` reason 含 `*` 静默失效（P2-1）

**问题**：`KERNEL_EXEMPT_RE` 的 `\S[^*\n]*?` 遇 `*` 终止 → `/* @kernel_exempt: fix * bug */` 既不匹配合法式、也不匹配非法式 → **静默失效**（无豁免、无告警）。

**修复**：reason 捕获改为 `\S(?:[^*]|\*(?!/))*`，允许内部 `*`（仅在 `*/` 处终止）。同步修复 ACL 的 `@acl_exempt`。空 reason 仍判非法（回归测试覆盖）。

## 四、G4 — ACL 白名单/词典校准（CAD 直连计数）

**问题**：SALOME 的 `STEPPlugin/IGESPlugin/BREPPlugin` 等数据交换插件目录未被识别为 import/export → ACL-007/012 把封装良好的格式调用误计为"边界外直连"；且消费项目中 vendored 内核源码未排除。

**修复**（`arch_metrics_anti_corruption.py`）：
- `IMPORT_EXPORT_DIR_NAMES` 扩展 `stepplugin/igesplugin/brepplugin/stlplugin/xaoplugin/...`；`_in_import_export_dir()` 增"`*plugin` 后缀 + 格式前缀"识别。
- 新增 `ACL_KERNEL_SELF_DIRS`（强名）+ `_is_kernel_self()`，纳入 `_skip()`（vendored 内核子目录排除）。

**实测影响**（重生成 3 个受门禁快照，带范围校验）：

| 项目 | overall | ACL-001 | ACL-007 | ACL-012 |
|:-----|:------:|:------:|:------:|:------:|
| salome_geom | 26.5 → **47.5** | 1693（不变）| 40 → **0** | 4 → **0** |
| occt | 36.5（不变）| 51137 → 47695 | 160 → 156 | — |
| freecad | 38.0（不变）| 3422（不变）| 3759（不变）| — |

> salome 的格式 I/O 已收敛在插件目录内 → ACL-007/012 归零，评分回落到真实耦合水平（G4 目标达成）。

## 五、测试与验证

| 项 | 结果 |
|:---|:-----|
| 新增 `tests/test_wp9_legacy_fixes.py`（G1 路径/子目录、G3 kernel/acl `*`、G4 插件目录/内核自身）| **7 passed** |
| ACL 回归（occt/salome/freecad） | **12 passed**（快照重生成后）|
| 快照范围校验 | 各维 0~100、无 null ✅ |

## 六、遗留 / 后续

| 项 | 归属 |
|:---|:-----|
| WP7 语料（`WP7语料清单.json`）salome ACL overall 26.5→47.5；⑧ LOOCV 需重算 | **WP-8**（语料/交叉验证刷新）|
| 元模型 §5.2 参考样本表同步 | WP-8 |
| 更细的 CAD 直连词典（import/export 目录通用化）| 后续按需 |

---

*H2-002 / H2-003 / P2-1 已在本次 WP-9 闭环；H2 待办清单状态已同步。*