---
# PR front-matter —— doc_lint.py 的机器可判输入，请逐项如实填写
pr_type: guide              # guide | rationale | cases | tooling | errata
kb_version: 1.6 -> 1.7
guide_version: 1.6
evidence:                   # 每条断言都要能回溯到下面某个证据
  - EV-TEST-<sha8>          # arch-quality 实测 / 回归快照
  - EV-EXPERT-<date>-<n>    # 专家校对确认记录
changes:
  files:
    - docs/zh/几何内核与科学数据结构一致性评估/几何内核与科学数据结构一致性评估指南.md
  rules_added: []
  rules_removed: []
  weights_changed: []       # 非空 ⇒ human_decisions 必填
  thresholds_changed: []
  severity_changed: []      # 形如 {rule: GCS-004, from: HIGH, to: MEDIUM, approval: HD-...}
human_decisions: []         # 形如 HD-2026-11-12-01；权重/阈值/severity 变更必须登记
review:
  reviewer_model: <reviewer-model>
  verdict: changes_requested
  p0: 0
  iterations: 1
index_rebuild: [gcs]
---

# <PR 标题：一句话说明本次知识变更>

## 1. 变更意图

为什么改、对应哪条证据、解决哪个 P0/P1 问题。

## 2. 证据

| 证据 ID | 类型 | 位置 | 摘要 |
|---|---|---|---|
| EV-TEST-xxxxxxxx | 实测 | `validation/.../evidence.json` | … |
| EV-EXPERT-2026-11-03-02 | 专家校对 | `docs/zh/.../指南专家校对确认记录.md#L12` | … |

## 3. 影响面

- 受影响规则：`GCS-xxx`
- 受影响子维度/权重：无 / 有（须附 `HD-` 编号）
- 受影响 Skill / 工具 / 回归基线：…

## 4. 自检（提交前）

- [ ] `python scripts/doc_lint.py --dimension <dim>` 无 ERROR
- [ ] `python -m pytest tests/` 通过
- [ ] 回归快照无未解释漂移
- [ ] 新增断言均有证据 ID

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
| HD-YYYY-MM-DD-NN | … | … | … |
