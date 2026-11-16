# Proposer & Reviewer Agent QA 集

> **版本**：1.0（2026-11-16）
> **配套**：`agents-usage.md`（使用说明）、`pr-template.md`（PR 模板）、`scripts/review_schema.json`（review 契约）
> **本文**：以一次真实的 errata PR（`HD-2026-11-13-01`）为例，按 Q&A 形式说明两个 Agent 怎么用。

---

## 0. 前置条件

```powershell
cd D:\opensource\arch-quality
powershell -ExecutionPolicy Bypass -File scripts\install_doc_agents.ps1
opencode agent list | Select-String assessment
# assessment-proposer (primary)
# assessment-reviewer (primary)
```

模型建议：`opencode-go/deepseek-v4.1-flash`（Reviewer 默认；召回与 kimi-k3 相同，额度成本约 1/130）。

---

## Q1. 这个示例解决什么问题？

`python scripts/doc_lint.py --dimension gcs` 报出 4 条版本相关告警：

```
G0-version-drift   案例集绑定指南 1.5，当前 1.6
G0-version-drift   设计依据绑定指南 1.2，当前 1.6
G0-version-history 指南标题 1.6 与版本历史最新 1.8 不一致
G0-meta-guide      指南引用《编制指南 1.7》，当前 1.8
```

目标：把文档包的**当前版本/绑定**统一到版本历史中的真实最新版 **1.8**，不改规则、权重、评分算法。

成功标准：

- `doc_lint --strict-versions` = 0 error / 0 warning；
- Reviewer 给出 `approved`（P0=0）；
- 有人类 `HD-` 批准记录；
- 合并后 `reeval` 通过。

---

## Q2. 需要做哪些准备？

```powershell
# 1) 切工作分支（Proposer 只写工作分支）
git switch -c doc-pr/gcs-errata-demo

# 2) 确认干净状态（无关的未提交修改会让 Reviewer 误判范围）
git status --porcelain
```

> 如果工作区有与本次无关的未提交修改，Reviewer 的 `git diff` 会看到它们。编排器的 prompt 已限定 `changes.files`，但仍建议在干净分支上操作。

---

## Q3. 如何让 Proposer 产出 PR？

```powershell
opencode run --agent assessment-proposer -m opencode-go/deepseek-v4.1-flash `
  "任务：修复 GCS 文档包的版本声明不一致。只改版本声明/绑定，不改正文语义、规则、权重、阈值、severity，不改版本历史中的历史行。
   事实：指南标题/头部是 1.6，但版本历史最新是 1.8；案例集绑定 1.5、设计依据绑定 1.2；指南引用《编制指南 1.7》，当前 1.8；两份 Skill 绑定 1.6。
   要求：把当前版本/绑定统一到 1.8；运行 python scripts/doc_lint.py --dimension gcs 确保 0 error；写 PR 文件 docs/zh/几何内核与科学数据结构一致性评估/pr-errata-version.md（用 pr-template.md 的 front-matter 格式，pr_type=errata，evidence 至少含 EV-REPO-version-history-1.8 与 EV-LINT-doc-lint-g0）；不要 git commit / 不要合并。"
```

Proposer 会依次：

```
grep/read  指南、案例集、设计依据、两份 Skill
edit/write 5 个文件的版本声明
bash       python scripts/doc_lint.py --dimension gcs
write      pr-errata-version.md
```

真实产出：

| 文件 | 变更 |
|---|---|
| `docs/zh/.../指南.md` | 标题 1.6→1.8；头部版本行 + 括号说明；编制指南 1.7→1.8；文末声明 |
| `docs/zh/.../验证案例集.md` | 绑定 1.5→1.8；编制指南 1.7→1.8 |
| `docs/zh/.../设计依据.md` | 绑定 1.2→1.8；编制指南 1.7→1.8 |
| `src/arch_quality/skills/geometry-consistency.md` | 当前绑定 1.6→1.8 |
| `.opencode/skills/.../SKILL.md` | 当前绑定 1.6→1.8（本地，gitignored） |
| `docs/zh/.../pr-errata-version.md` | 新增 PR 文件 |

PR front-matter（节选）：

```yaml
pr_type: errata
kb_version: 1.8
guide_version: 1.8
evidence:
  - EV-REPO-version-history-1.8
  - EV-LINT-doc-lint-g0
changes:
  files: [...]
  weights_changed: []
  thresholds_changed: []
  severity_changed: []
human_decisions: []
review: { verdict: changes_requested, p0: 0 }
```

---

## Q4. 为什么先跑机器门禁？

```powershell
python scripts\doc_lint.py --dimension gcs --strict-versions
python scripts\doc_lint.py --pr "docs/zh/几何内核与科学数据结构一致性评估/pr-errata-version.md"
```

预期：

```
summary: 0 error / 0 warning / 0 info
```

机器能判的（G0/G1/G3、Review/PR 契约）不要交给 LLM；这一步失败就不用叫 Reviewer。

---

## Q5. 如何让 Reviewer 审核？

### 方式 A：编排器（推荐）

```powershell
python scripts\run_doc_pr.py --pr-id PR-DEMO-01 `
  --pr-file "docs/zh/几何内核与科学数据结构一致性评估/pr-errata-version.md" `
  --skip-proposer --reviewer-model opencode-go/deepseek-v4.1-flash
```

真实输出：

```
[start]      phase=draft
[selfcheck]  0 error / 0 warning
[reviewer#1] verdict=approved  P0=0 P1=0 P2=4
[review#1]   → review_approved
Review 已通过，等待人工批准。
```

### 方式 B：直接调 Reviewer Agent

```powershell
opencode run --agent assessment-reviewer -m opencode-go/deepseek-v4.1-flash `
  "审核 docs/zh/几何内核与科学数据结构一致性评估/pr-errata-version.md，按你的检查清单独立审核，只输出符合 scripts/review_schema.json 的 JSON"
```

Reviewer 会自己跑 `doc_lint`、读 diff 与文档，输出：

```json
{
  "pr_id": "PR-DEMO-01",
  "verdict": "approved",
  "p0": 0, "p1": 0, "p2": 4,
  "comments": [
    {"file": "docs/zh/.../pr-errata-version.md", "line": 72, "severity": "P2",
     "evidence": "tests/ 目录实际存在",
     "message": "§4 自检把 pytest 勾为不适用，但工作区存在 tests/…",
     "suggestion": "改为运行 pytest 并记录结果"}
  ]
}
```

> 硬规则：每条意见必须有 `file:line` + `evidence`；`approved` 必须 P0=0；`changes_requested` 必须至少 1 条意见。

---

## Q6. Reviewer 要求修改怎么办？

`run_doc_pr.py` 会自动走：`revise → Proposer 带反馈修订 → selfcheck → review`（最多 3 轮）。

真实案例（`PR-P2-FOLLOWUP-01`）：

```
review#1  changes_requested  P1: GUIDE_VERSION 仍是 1.7
review#2  changes_requested  P1: scripts/consistency_check.py 版本对过期
review#3  changes_requested  P1: 证据自证（引用本 PR 改后的代码行）
          → needs_human（第 3 轮上限，冻结，禁止自动放行）
```

人工决定开新 PR-02 → 第 2 轮 `approved 0/0/0`（`HD-2026-11-16-01`）。

手工控制：

```powershell
python scripts\pr_state.py revise    --pr-id PR-DEMO-01 --note "按 review 修订"
python scripts\pr_state.py selfcheck --pr-id PR-DEMO-01
python scripts\pr_state.py review    --pr-id PR-DEMO-01 --review .doc-pr\PR-DEMO-01\review_2.json
```

---

## Q7. 如何人工批准、合并、回评？

```powershell
python scripts\pr_state.py signoff --pr-id PR-DEMO-01 --decision HD-2026-11-13-01 `
  --by Guo --what "批准版本对齐勘误"
python scripts\pr_state.py merge   --pr-id PR-DEMO-01
python scripts\pr_state.py reeval  --pr-id PR-DEMO-01
python scripts\pr_state.py status  --pr-id PR-DEMO-01
```

- `merge` 会**重新跑门禁**，通过后写 `index_rebuild.json`（索引是派生物）；
- `reeval` 对应《编制指南》的“修订后回评”；
- 缺少 `signed_off` 时 `merge` 直接拒绝。

提交与合并：

```powershell
git add -- docs/zh/几何内核与科学数据结构一致性评估/指南.md ... pr-errata-version.md
git commit -m "docs(gcs): 文档包版本对齐 1.8（errata）"
git switch main
git merge --no-ff doc-pr/gcs-errata-demo
```

---

## Q8. 如何验证合并结果？

```powershell
python scripts\doc_lint.py --dimension gcs --strict-versions          # 0/0
python scripts\consistency_check.py --engine geometry_consistency     # PASS
python -m pytest tests/test_geometry_consistency.py tests/test_geometry_integration.py -q  # 47 passed
```

真实记录：5 文件 +105/−11；`kb_commit_sha256=666c7cac88055a15…`；`phase=closed`。

---

## Q9. 换成自己的任务怎么改？

**Proposer prompt 模板（四段式）**：

```
任务：<一句话目标>
事实：<lint 输出 / 证据 / 现状>
要求：<范围 + 必须同步的文件 + 必须运行的命令 + 产出 PR 文件路径>
禁止：<不许改的东西 / 不许 git commit / 不许合并>
```

**PR 模板**：`docs/zh/几何内核与科学数据结构一致性评估/pr-template.md`

**Reviewer 不需要额外 prompt**——检查清单写在 `opencode-harness/agents/reviewer.md`：证据支持、限定条件、跨文档口径、覆盖矩阵、过度修改、人类批准。

---

## Q10. 常见失败怎么处理？

| 现象 | 原因 / 处理 |
|---|---|
| Reviewer 输出空内容 / `finish_reason=length` | 推理 token 耗尽；重跑、调大 `max_tokens` 或 `--effort low` |
| `changes_requested` 但 0 条意见 | 契约违规，`doc_lint --review` 判 `R-verdict`；重跑 Reviewer |
| 审核意见涉及无关文件 | prompt 限定 `changes.files`；编排器已内置 |
| 第 3 轮仍不收敛 | `needs_human` 冻结；人工开新 PR 或缩小范围 |
| 找不到 agent | 未安装到 `.opencode/agents`，或 `--dir` 指错目录 |
| 同一 `--pr-id` 重跑 | 会重置 `.doc-pr/<pr_id>/`，历史 review 丢失 |

---

## Q11. 时间与成本（实测）

| 环节 | 耗时 | 额度成本 |
|---|---|---|
| Proposer（5 文件 + 自检） | 2–5 min | ~$0.01–0.05 |
| Reviewer（deepseek-v4.1-flash） | 30–90s | ~$0.004 |
| Reviewer（kimi-k3） | 25–85s | ~$0.5 |

---

## 附录 A：命令速查

```powershell
# 安装 / 查看
powershell -ExecutionPolicy Bypass -File scripts\install_doc_agents.ps1
opencode agent list | Select-String assessment

# Proposer
opencode run --agent assessment-proposer -m opencode-go/deepseek-v4.1-flash "<任务>"

# Reviewer
opencode run --agent assessment-reviewer -m opencode-go/deepseek-v4.1-flash "<审核任务>"

# 编排
python scripts\run_doc_pr.py --pr-id PR-X --pr-file <pr.md> --skip-proposer
python scripts\run_doc_pr.py --pr-id PR-X --task "<任务>"

# 状态机
python scripts\pr_state.py status|signoff|merge|reeval --pr-id PR-X
```

## 附录 B：文件清单

| 文件 | 作用 |
|---|---|
| `opencode-harness/agents/proposer.md` | Proposer 定义（入库） |
| `opencode-harness/agents/reviewer.md` | Reviewer 定义（入库） |
| `scripts/doc_lint.py` | G0/G1/G3 + Review/PR 契约 |
| `scripts/pr_state.py` | 状态机 |
| `scripts/run_doc_pr.py` | Agent 编排器 |
| `scripts/seeded_defects.py` | 植入缺陷集（回归） |
| `scripts/compare_reviewers.py` | 模型对比 |
| `scripts/review_schema.json` | review 输出契约 |
| `docs/zh/几何内核与科学数据结构一致性评估/pr-template.md` | PR 模板 |
| `docs/zh/几何内核与科学数据结构一致性评估/agents-usage.md` | 使用说明 |

## 附录 C：真实运行记录

| PR | 结果 |
|---|---|
| `PR-ERRATA-VERSION-01` | 3 轮告警→0；Reviewer approved（P0=0/P1=0/P2=4）；`HD-2026-11-13-01`；合并 5 文件 +105/−11 |
| `PR-P2-FOLLOWUP-01` | 3 轮 changes_requested → `needs_human`（迭代上限） |
| `PR-P2-FOLLOWUP-02` | approved 0/0/0；`HD-2026-11-16-01`；合并 5 文件 +92/−13 |
