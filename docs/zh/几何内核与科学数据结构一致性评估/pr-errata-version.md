---
# PR front-matter —— doc_lint.py 的机器可判输入，请逐项如实填写
pr_type: errata              # guide | rationale | cases | tooling | errata
kb_version: 1.8
guide_version: 1.8
evidence:                    # 每条断言都要能回溯到下面某个证据
  - EV-REPO-version-history-1.8   # 指南 §版本历史 最新条目 1.8（2026-10-21）
  - EV-LINT-doc-lint-g0           # doc_lint --dimension gcs 的 G0 版本门禁结果
changes:
  files:
    - docs/zh/几何内核与科学数据结构一致性评估/几何内核与科学数据结构一致性评估指南.md
    - docs/zh/几何内核与科学数据结构一致性评估/几何内核与科学数据结构一致性评估验证案例集.md
    - docs/zh/几何内核与科学数据结构一致性评估/几何内核与科学数据结构一致性评估的设计依据.md
    - src/arch_quality/skills/geometry-consistency.md
    - .opencode/skills/geometry-consistency/SKILL.md
  rules_added: []
  rules_removed: []
  weights_changed: []
  thresholds_changed: []
  severity_changed: []
human_decisions: []          # 本次为版本声明勘误，不涉及权重/阈值/severity
review:
  reviewer_model: <reviewer-model>
  verdict: changes_requested
  p0: 0
  iterations: 1
index_rebuild: [gcs]
---

# 勘误：GCS 文档包当前版本声明与绑定统一到 1.8

## 1. 变更意图

指南“版本历史”最新条目已是 1.8（2026-10-21），但文档包各处的“当前版本/当前绑定”仍停留在旧值，导致同一文档包内版本口径分裂：

- 指南标题与头部版本行写 1.6，头部括号内的变更说明也是 1.6 的描述；
- 指南文末版本声明仍写“1.7 版”；
- 验证案例集绑定指南 1.5，设计依据绑定指南 1.2；
- 指南/案例集/设计依据三份文档引用的《AI 架构评估文档编制指南》为 1.7；
- 两份 Skill 的“指南版本”绑定仍为 1.6。

本 PR 只修正**当前版本号/当前绑定**，使其与 1.8 一致；不改正文语义、不改规则表/权重/评分算法/案例正文，不改版本历史表格中的历史行（1.0–1.7 原样保留）。

## 2. 证据

| 证据 ID | 类型 | 位置 | 摘要 |
|---|---|---|---|
| EV-REPO-version-history-1.8 | 仓库事实 | `docs/zh/几何内核与科学数据结构一致性评估/几何内核与科学数据结构一致性评估指南.md#L582` | 版本历史最新条目为 `1.8 | 2026-10-21 | H3 G1 路径判定实现（H2-002 闭环）；G2 GCS-003 检测方法表述与实现对齐（IsDone/try-catch）` |
| EV-LINT-doc-lint-g0 | 文档门禁 | `python scripts/doc_lint.py --dimension gcs` | 修复前 0 error / 3 warning：`G0-version-history`（指南标题/头部 1.6 ≠ 历史最新 1.8）、`G0-version-drift`（案例集绑定 1.5、设计依据绑定 1.2）；修复后 0 error / 0 warning / 0 info |

## 3. 影响面

- 受影响规则：无（未改规则表、规则详情小节、评分算法）。
- 受影响子维度/权重/阈值/severity：无。
- 受影响 Skill / 工具 / 回归基线：仅两份 Skill 的“指南版本”绑定元数据（`src/arch_quality/skills/geometry-consistency.md`、`.opencode/skills/geometry-consistency/SKILL.md`）；未改 `SKILL_VERSION`、未改检测实现、无回归基线漂移。
- 版本历史表格：未修改任何历史行（1.0–1.7 保持原样）。
- 索引：需由合并后的 CI 重建（`index_rebuild: [gcs]`）。

逐文件变更（均为版本声明/绑定字段，未触碰正文语义）：

| 文件 | 变更 |
|---|---|
| 指南 | 标题 `（1.6版）`→`（1.8版）`；头部版本行改为 1.8 并替换为与 1.8 一致的变更说明；`编制指南 1.7`→`1.8`；文末 `1.7 版待第二轮专家校对定稿`→`1.8 版待复核定稿` |
| 验证案例集 | `指南（1.5版）`→`指南（1.8版）`；`编制指南 1.7`→`1.8`（案例集自身版本 1.2 不变） |
| 设计依据 | `指南（1.2版）`→`指南（1.8版）`；`编制指南 1.7`→`1.8`（设计依据自身版本 1.1 不变） |
| `src/arch_quality/skills/geometry-consistency.md` | 指南绑定 `1.6 版`→`1.8 版`；`对齐指南 1.6`→`对齐指南 1.8`；引用文档表指南版本 `1.6`→`1.8`（历史行保留） |
| `.opencode/skills/geometry-consistency/SKILL.md` | `指南版本：1.6`→`指南版本：1.8` |

## 4. 自检（提交前）

- [x] `python scripts/doc_lint.py --dimension gcs` 无 ERROR（0 error / 0 warning / 0 info）
- [ ] `python -m pytest tests/` 通过（本工作区无 `tests/` 目录，该项不适用）
- [x] 回归快照无未解释漂移（本次未改检测实现，不涉及基线）
- [x] 新增断言均有证据 ID（本次无新增断言，仅版本口径修正）

## 5. 审核意见（Reviewer 填写，JSON 见 `scripts/review_schema.json`）

```json
{
  "pr_id": "<PR-ID>",
  "reviewer": {"model": "<model>", "provider": "<provider>", "role": "reviewer"},
  "verdict": "changes_requested",
  "p0": 0,
  "p1": 0,
  "p2": 0,
  "comments": []
}
```

## 6. 人工决策（Human Approver 填写）

| 决策编号 | 决策内容 | 决策人 | 日期 |
|---|---|---|---|
| — | 本次 errata 不涉及权重/阈值/severity，无需人工决策 | — | — |
