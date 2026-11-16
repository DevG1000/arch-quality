---
pr_type: errata
kb_version: 1.8 -> 1.9
guide_version: 1.8
evidence:
  - EV-REPO-skill-history-1.2
  - EV-REPO-meta-guide-1.8
  - EV-CODE-skill-version-1.2
  - EV-CODE-guide-version-1.8
  - EV-CODE-consistency-check-1.8
  - EV-REPO-version-history-1.8
  - EV-REPO-guide-title-1.8
  - EV-REPO-guide-gcs003-severity
  - EV-TEST-geometry-47
changes:
  files:
    - src/arch_quality/arch_metrics_geometry_consistency.py
    - scripts/consistency_check.py
    - src/arch_quality/skills/geometry-consistency.md
    - docs/zh/几何内核与科学数据结构一致性评估/几何内核与科学数据结构一致性评估的设计依据.md
    - .opencode/skills/geometry-consistency/SKILL.md
  rules_added: []
  rules_removed: []
  weights_changed: []
  thresholds_changed: []
  severity_changed: []
human_decisions: []
review:
  reviewer_model: <reviewer-model>
  verdict: changes_requested
  p0: 0
  iterations: 1
index_rebuild: [gcs]
---

# 勘误：处理 GCS 文档包 P2 并补齐代码侧版本口径

## 1. 变更意图

上一轮 errata PR（HD-2026-11-13-01）合并后，Reviewer 留下 4 条 P2；本轮复核又发现代码 `GUIDE_VERSION` 仍为 1.7（P1）。本 PR 一并处理，不改规则、权重、阈值与评分算法。

| # | 意见 | 处理 |
|---|---|---|
| P1 | `GUIDE_VERSION` 仍为 1.7，与指南 1.8 冲突 | 改为 1.8；docstring 同步 |
| P2-1 | Skill 头部写 1.0，与版本历史最新 1.2 矛盾 | 头部与 `SKILL_VERSION` 统一为 1.2 |
| P2-2 | `.opencode/.../SKILL.md` 版本不一致 | 本地镜像同步 1.2（gitignored，不入库） |
| P2-3 | 设计依据称 GCS-003 为“ERROR 可阻断” | 改为“GCS-003，MEDIUM/WARNING，需人工复核” |
| P2-4 | 上一 PR 缺《编制指南》1.8 证据 | 本 PR 增加 `EV-REPO-meta-guide-1.8` 并给出行号 |
| P1-2 | `scripts/consistency_check.py` 的 GCS 版本对仍是 1.7/1.1 | 更新为 1.8/1.2，并补齐第 4 个维度名 |

**范围声明**：本 PR 涉及 `changes.files` 列出的 4 个跟踪文件 + 1 个本地镜像（`.opencode/.../SKILL.md`，gitignored，不入库）。工作区中 `docs/zh/计划/H3阶段进展与决策记录.md` 的未提交修改是本次之前既有的，与本 PR 无关，不在审核范围内。

## 2. 证据

| 证据 ID | 类型 | 位置 | 摘要 |
|---|---|---|---|
| EV-REPO-skill-history-1.2 | 仓库原文 | `src/arch_quality/skills/geometry-consistency.md#L327-L333` | 版本历史最新条目为 1.2（2026-10-21） |
| EV-REPO-meta-guide-1.8 | 仓库原文 | `docs/zh/AI 架构评估文档编制指南.md#L1` | 标题为《AI 架构评估文档编制指南（1.8版）》 |
| EV-CODE-skill-version-1.2 | 代码 | `src/arch_quality/arch_metrics_geometry_consistency.py#L29` | `SKILL_VERSION = "1.2"` |
| EV-CODE-guide-version-1.8 | 代码 | `src/arch_quality/arch_metrics_geometry_consistency.py#L28` | `GUIDE_VERSION = "1.8"` |
| EV-CODE-consistency-check-1.8 | 代码 | `scripts/consistency_check.py#L102` | GCS 版本对更新为 1.8/1.2，维度列表补第 4 项 |
| EV-REPO-version-history-1.8 | 仓库原文 | `...指南.md#L582` | 版本历史最新条目为 1.8（2026-10-21） |
| EV-REPO-guide-title-1.8 | 仓库原文 | `...指南.md#L1` | 标题为（1.8版） |
| EV-REPO-guide-gcs003-severity | 仓库原文 | `...指南.md#L281`、`#L471` | GCS-003 为 MEDIUM/WARNING，§7.2 要求人工复核 |
| EV-TEST-geometry-47 | 实测 | `python -m pytest tests/test_geometry_consistency.py tests/test_geometry_integration.py -q` | 47 passed |

## 3. 影响面

- 受影响规则：无（GCS-003 级别未变，仅修正设计依据表述）
- 受影响权重/阈值/severity：无
- 受影响工具：`SKILL_VERSION` 1.1→1.2、`GUIDE_VERSION` 1.7→1.8；GCS 回归快照不记录这两个字段，无基线漂移

## 4. 自检

- [x] `python scripts/doc_lint.py --dimension gcs --strict-versions` → 0 error / 0 warning
- [x] `python -m pytest tests/test_geometry_consistency.py tests/test_geometry_integration.py -q` → 47 passed
- [x] `python scripts/consistency_check.py --engine geometry_consistency` → PASS
- [x] 每条新增断言均有 evidence ID
