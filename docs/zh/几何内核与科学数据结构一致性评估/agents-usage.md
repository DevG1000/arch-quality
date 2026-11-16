# 评估文档 PR 闭环：Proposer / Reviewer Agent 使用说明

> **版本**：1.0（2026-11-16）
> **适用**：`assessment-proposer` / `assessment-reviewer`（OpenCode primary agents）
> **配套工具**：`scripts/doc_lint.py`、`scripts/pr_state.py`、`scripts/run_doc_pr.py`、`scripts/seeded_defects.py`、`scripts/compare_reviewers.py`

本文说明两个 Agent 的定位、安装、三种调用方式、输入输出契约、权限边界与常见问题。

---

## 1. 两个 Agent 是什么

| | `assessment-proposer` | `assessment-reviewer` |
|---|---|---|
| 角色 | 出 PR：检索已有知识 → 产出**尽可能小的 diff** + PR 文件 | 审 PR：只读证据与 diff → 输出结构化 review JSON |
| 权限 | `edit/write: allow`（只能写工作区，不能合并） | `edit/write: deny`（完全不能改文件） |
| bash | 仅 `doc_lint` / `pr_state` / `git status·diff·log` / 只读命令 | 仅 `doc_lint`（含 `--review`）/ `pr_state status` / 只读 git |
| 输出 | 改动文件 + `pr-*.md`（front-matter） | 符合 `scripts/review_schema.json` 的 JSON |
| 建议模型 | `opencode-go/deepseek-v4.1-flash` 或 `opencode-go/kimi-k3` | `opencode-go/deepseek-v4.1-flash`（同召回，额度成本约 1/130） |

定义源文件在 `opencode-harness/agents/{proposer,reviewer}.md`（入库、可评审）；运行时安装到 `.opencode/agents/assessment-*.md`（该目录被 `.gitignore` 忽略，仅本地生效）。

---

## 2. 安装与确认

```powershell
cd D:\opensource\arch-quality
powershell -ExecutionPolicy Bypass -File scripts\install_doc_agents.ps1
opencode agent list | Select-String assessment
```

应看到：

```
assessment-proposer (primary)
assessment-reviewer (primary)
```

> 两个 Agent 必须是 **primary**：`opencode run --agent` 只接受 primary；若改回 `subagent`，无头调用会被静默降级为默认 agent。

---

## 3. 三种调用方式

### 3.1 TUI 交互（人工探索）

```powershell
opencode --agent assessment-proposer
opencode --agent assessment-reviewer
```

进入后直接对话，例如让 Reviewer 审核某个 PR：

> 审核 `docs/zh/几何内核与科学数据结构一致性评估/pr-p2-followup.md`，按你的检查清单输出 review JSON。

### 3.2 无头单次（脚本 / CI）

```powershell
# Proposer：给任务，它自己检索、改文件、写 PR
opencode run --agent assessment-proposer -m opencode-go/deepseek-v4.1-flash `
  "修复 GCS 文档包的版本声明不一致，只改版本绑定，不改正文；完成后运行 doc_lint 并写 PR 文件"

# Reviewer：审一个 seeded 任务
opencode run --agent assessment-reviewer -m opencode-go/deepseek-v4.1-flash `
  "审核 .arch-reports/seeded-defects/S1/review_task.json，只输出符合 review_schema.json 的 JSON"
```

### 3.3 编排器（推荐）

```powershell
# 只审已有 PR（不跑 Proposer）
python scripts\run_doc_pr.py --pr-id PR-X `
  --pr-file "docs/zh/几何内核与科学数据结构一致性评估/pr-errata-version.md" `
  --skip-proposer --reviewer-model opencode-go/deepseek-v4.1-flash

# 让 Proposer 先产出/修订，Reviewer 自动审；changes_requested 时带反馈回到 Proposer（最多 3 轮）
python scripts\run_doc_pr.py --pr-id PR-X --task "<任务描述>" `
  --proposer-model opencode-go/deepseek-v4.1-flash `
  --reviewer-model opencode-go/deepseek-v4.1-flash
```

编排器依次执行 `start → selfcheck → Reviewer → review`；只有提供 `--human-decision <HD-id> --by <姓名>` 才会继续 `signoff → merge → reeval`，否则停在 `review_approved` 并打印下一步命令。

> 注意：同一个 `--pr-id` 重跑会**重置**该 PR 的状态目录（`.doc-pr/<pr_id>/`）。

---

## 4. 输入 / 输出契约

### 4.1 Proposer 产出的 PR 文件

参考 `docs/zh/几何内核与科学数据结构一致性评估/pr-template.md`：

```yaml
pr_type: errata            # guide | rationale | cases | tooling | errata
kb_version: 1.8 -> 1.9
guide_version: 1.8
evidence: [EV-REPO-..., EV-CODE-..., EV-TEST-...]
changes:
  files: [...]
  rules_added: []
  weights_changed: []      # 非空 ⇒ human_decisions 必填
  thresholds_changed: []
  severity_changed: []
human_decisions: []
review: { verdict: changes_requested, p0: 0 }
```

### 4.2 Reviewer 输出的 review JSON

```json
{
  "pr_id": "PR-X",
  "reviewer": {"model": "deepseek-v4.1-flash", "provider": "opencode-go", "role": "reviewer"},
  "verdict": "approved | changes_requested",
  "p0": 0, "p1": 0, "p2": 0,
  "comments": [
    {"file": "docs/zh/.../指南.md", "line": 123, "severity": "P1",
     "evidence": "EV-REPO-...", "message": "...", "suggestion": "..."}
  ]
}
```

硬规则（由 `scripts/doc_lint.py --review` 校验）：

- `p0/p1/p2` 必须与 comments 中对应 severity 的条数一致；
- 存在 P0 时不得 `approved`；
- `changes_requested` 必须至少 1 条 comment（没有问题就判 `approved`）；
- 每条意见必须有 `file`、`line`、`evidence`。

---

## 5. 权限边界（设计如此）

- **Proposer 不能**：merge、push 主分支、修改线上索引、自行决定权重/阈值/severity（必须引用人类 `HD-` 批准）。
- **Reviewer 不能**：修改任何文件，只能提交 review。
- **合并只能**由 `pr_state merge` 在 `signed_off` 状态执行；缺少人工批准时直接拒绝。

---

## 6. 典型工作流

1. 从 `main` 切工作分支；
2. Proposer 产出 PR 文件与最小 diff；
3. `python scripts\run_doc_pr.py --skip-proposer --pr-file ...` 跑门禁与 Reviewer；
4. 若 `changes_requested`，修订后重新 selfcheck + review（最多 3 轮，超限转 `needs_human`）；
5. 人类给 `HD-` 编号后执行 `signoff → merge → reeval`；
6. 把 PR 文件与改动提交到分支，合回 `main`。

手工控制状态时使用：

```powershell
python scripts\pr_state.py status  --pr-id PR-X
python scripts\pr_state.py signoff --pr-id PR-X --decision HD-... --by <姓名> --what "..."
python scripts\pr_state.py merge   --pr-id PR-X
python scripts\pr_state.py reeval  --pr-id PR-X
```

---

## 7. 模型选择与成本

| 模型 | 检测 S1–S4 | 干净对照 | 平均延迟 | 平均 allowance/次 |
|---|---|---|---|---|
| `kimi-k3` | 4/4 | 通过 | ~34s | ~$0.53 |
| `deepseek-v4.1-flash` | 4/4 | 通过（偶发 token 耗尽，需重试） | ~41s | ~$0.004 |

结论：Reviewer 默认用 `deepseek-v4.1-flash`；`kimi-k3` 可作争议条目的第二意见。对比方法见 `scripts/compare_reviewers.py` 与 `.arch-reports/seeded-defects/COMPARISON.md`。

---

## 8. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `agent "..." is a subagent, not a primary agent` | `mode` 被改回 subagent；改回 `primary` 并重新安装 |
| 工具调用被 auto-reject | 无头模式下 `"*": ask` 会被自动拒绝；权限应为 `deny` + 显式白名单（当前已如此） |
| Reviewer 输出空内容 / `finish_reason=length` | 推理模型 token 耗尽；重试、调大 `max_tokens`，或 `--effort low` |
| 输出不是合法 JSON | 重跑；用 `python scripts\doc_lint.py --review <file>` 校验契约 |
| 找不到 agent | 未安装或工作目录不含 `.opencode/agents`；运行安装脚本并用 `--dir` 指向正确目录 |
| 审核范围出现无关文件 | 在 prompt 中限定 `changes.files`；编排器已内置该约束 |

---

## 9. 修改 / 升级 Agent

1. 修改 `opencode-harness/agents/*.md`（入库、可评审）；
2. 运行 `scripts/install_doc_agents.ps1` 同步到 `.opencode/agents/`；
3. 重开 opencode 会话（agent 定义在会话启动时加载）；
4. 跑 `python scripts\seeded_defects.py run` 与 `python scripts\compare_reviewers.py --model <m>`，确认召回未退化。

---

## 10. 相关文件

- Agent 定义：`opencode-harness/agents/proposer.md`、`opencode-harness/agents/reviewer.md`
- 安装脚本：`scripts/install_doc_agents.ps1`
- 文档门禁：`scripts/doc_lint.py`（G0/G1/G3 + Review/PR 契约）
- 状态机：`scripts/pr_state.py`
- 编排器：`scripts/run_doc_pr.py`
- 植入缺陷集：`scripts/seeded_defects.py`（基线冻结于 `opencode-harness/seeded/baseline/`）
- 模型对比：`scripts/compare_reviewers.py`
- PR 模板：`docs/zh/几何内核与科学数据结构一致性评估/pr-template.md`
- 实战示例 / QA：`docs/zh/几何内核与科学数据结构一致性评估/Proposer&Reviewer Agent QA集.md`
