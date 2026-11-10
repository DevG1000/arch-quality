# OpenCode 技术问答集（详细版）

> **日期**：2026-09-28（中国时间 UTC+8）
> **范围**：本次会话中关于 OpenCode 能力、架构、生态与 Agent 持续进化的问答整理
> **说明**：结论结合 `arch-quality` 仓库实证；三方项目信息来自调研，可能随版本变动，以官方为准。

---

## 目录

1. [OpenCode 是否 sessionless？](#q1-opencode-是否-sessionless)
2. [OpenCode 能否自举（bootstrap）？](#q2-opencode-能否自举bootstrap)
3. [OpenCode 原生支持语义代码搜索吗？](#q3-opencode-原生支持语义代码搜索吗)
4. [三方语义搜索方案有哪些？](#q4-三方语义搜索方案有哪些)
5. [语义搜索如何与 arch-quality 的 FileIndex/DepGraph 结合？](#q5-语义搜索如何与-arch-quality-的-fileindexdepgraph-结合)
6. [什么是上下文注入（context injection）？](#q6-什么是上下文注入context-injection)
7. [DeepSeek 的上下文窗口有多大？](#q7-deepseek-的上下文窗口有多大)
8. [big-pickle 的上下文窗口与底层模型？](#q8-big-pickle-的上下文窗口与底层模型)
9. [UI 如何与 LLM 注入配合？](#q9-ui-如何与-llm-注入配合)
10. [LLM 在 arch-quality 运行中如何参与？](#q10-llm-在-arch-quality-运行中如何参与)
11. [预注入点在 arch-quality 流程的哪个环节？](#q11-预注入点在-arch-quality-流程的哪个环节)
12. [FileIndex 在哪里、怎么产生？](#q12-fileindex-在哪里怎么产生)
13. [首次运行时 FileIndex 如何产生？](#q13-首次运行时-fileindex-如何产生)
14. [OpenCode 为 Agent 持续进化提供哪些方案/支持？](#q14-opencode-为-agent-持续进化提供哪些方案支持)
15. [sidecar 是什么意思？](#q15-sidecar-是什么意思)
16. [OpenCode 有遥测吗？如何关闭？](#q16-opencode-有遥测吗如何关闭)

---

## Q1 OpenCode 是否 sessionless？

**结论：不是。OpenCode 采用「有状态会话 + 本地持久化」的混合模式。**

### 详细说明

- **会话是持久的**：每次对话是一个 session，消息历史、工具调用与返回、文件改动记录都保存在本地存储中。
- **可续接**：支持 `--continue`（续上一个）、`--session <id>`（指定会话）、`--resume` 等，重启后仍能继续。
- **上下文受限**：虽然会话持久化，但单次推理能看到的仍是**上下文窗口内**的内容；超出窗口需要压缩/摘要（compaction），历史不会自动全部进入 prompt。

### 为什么容易误解

TUI 每次打开看起来像"重新开始"，但底层 session 存储一直在；无头模式 `opencode run` 默认是一次性执行，容易让人觉得"无状态"。

### 对工程的影响

- 长任务可分段续接 ✅
- 但**跨会话记忆不自动继承**，关键规则要写进 `AGENTS.md` / skills / 记忆文件，而不是指望模型"记得"。

---

## Q2 OpenCode 能否自举（bootstrap）？

**结论：不能完全自举（不会自动改自己的源码或模型权重），但支持「狗粮式」自我使用与自我改进的前提条件。**

### 能做什么

- OpenCode 可以读取自己的配置（`opencode.json`、`AGENTS.md`、`.opencode/`）、skills、plugins，并在权限允许时修改它们。
- 它可以**用自己来开发自己**（dogfooding）——本仓库就是例子：`architecture-quality` Agent 可以评估 `arch-quality` 项目本身（自评估得分 55.4）。

### 不能做什么

- ❌ 不会自动训练/微调模型（无权重更新）
- ❌ 不会在无人工确认下安全地改自身核心代码（改配置容易，改运行时难）
- ❌ 不会自我评估并自动上线（需 harness + 人工 review）

### 正确的"自举"姿势

```
改 Skill / rules / plugin
   → opencode-harness 回归验证行为
   → 人工 review diff
   → git 版本化
   → 下一轮迭代
```

即：**自举 = 可自我修改的工具链 + 外部验证闸门**，不是"自我意识式进化"。

---

## Q3 OpenCode 原生支持语义代码搜索吗？

**结论：否。原生检索基于文本/正则/文件名，不是语义检索。**

### 原生能力

| 工具 | 机制 | 特点 |
|:-----|:-----|:-----|
| `grep` | ripgrep 正则 | 精确、快、可解释；不懂"意思" |
| `glob` | 文件名模式 | 找文件，不找内容语义 |

例如搜"哪里处理了用户鉴权"，原生 grep 只能匹配字面词（auth、login、permission…），无法理解"鉴权"与 `checkCredentials()` 的语义关联。

### 语义搜索需要外挂

见 Q4。

---

## Q4 三方语义搜索方案有哪些？

调研到的社区/三方方案（非 OpenCode 官方内置）：

| 方案 | 形态 | 技术栈 | 特点 |
|:-----|:-----|:-------|:-----|
| **sema** | MCP Server | 向量检索 | 通过 MCP 接入，可被 OpenCode 调用 |
| **open-codebase-index** | OpenCode Plugin | Rust + tree-sitter，SQLite + usearch + BM25 | 本地索引、混合检索（向量 + 关键词，RRF 融合），带符号级切分 |
| **opencode-semantic-search** | 轻量插件 | 语义路由 + grep | 先用语义判断方向，再回退到 grep，成本低 |

### 选型要点

- **索引维护成本**：代码频繁变更时，增量索引是否跟得上
- **离线/隐私**：embedding 是本地模型还是云 API
- **可解释性**：能否给出命中文件+行，便于审计
- **与现有工作流集成**：MCP vs Plugin，权限与生命周期不同

### 共同局限

语义检索是"召回"而非"证明"：可能漏（假阴性）也可能引入噪声（假阳性），**不能替代精确规则**。

---

## Q5 语义搜索如何与 arch-quality 的 FileIndex/DepGraph 结合？

这是本次调研的**方向 2**：把语义层作为"候选路由层"，叠加在现有确定性分析之上。

### 分层设计（推荐）

```
┌─────────────────────────────────────────────┐
│ L3 语义层（embedding / 语义召回）             │  ← 新增，可选、可关闭
├─────────────────────────────────────────────┤
│ L2 依赖层（DepGraph: include/import/use 边）  │  ← 已有
├─────────────────────────────────────────────┤
│ L1 文件层（FileIndex: 语言/文件/行数/哈希）   │  ← 已有
└─────────────────────────────────────────────┘
```

### 三个落地用途

1. **缩小 MLR 规则扫描范围**
   - 例：语义召回"疑似模板实例化/跨语言绑定"的候选文件，再交给确定性规则精确判定。
2. **发现隐式跨语言绑定**
   - 语法层看不到的调用（字符串反射、配置驱动、SWIG 生成），语义层可提示候选，再由人工/规则确认。
3. **为报告生成"证据候选"**
   - 给 LLM 编排层提供"相关代码片段"，提升解释质量，但**不参与打分**。

### 硬约束（防止破坏可复现性）

- ✅ 语义层**只做召回/路由**，评分仍由 `arch_metrics_*.py` 确定性引擎产出
- ✅ 可一键关闭（无 embedding 也能跑全量规则）
- ✅ 结果可解释（给出文件+行+相似度，可追溯到原文）
- ✅ 索引可缓存、可失效（mtime/commit hash）

> **一句话**：语义搜索是"导航仪"，不是"裁判"。裁判永远是确定性规则引擎。

---

## Q6 什么是上下文注入（context injection）？

**定义**：在调用 LLM 之前，把外部信息拼进 prompt / 上下文窗口，让模型"看到"它训练时不知道的项目知识。

### 注入来源

| 类型 | 例子 |
|:-----|:-----|
| 静态规则 | `AGENTS.md`、`SKILL.md`、系统提示词 |
| 动态检索 | grep/glob 结果、语义检索片段、FileIndex 摘要 |
| 工具返回 | 命令输出、文件内容、报告 JSON |
| 会话历史 | 之前的消息与工具调用 |

### 目的

弥补模型的知识盲区（项目私有约定、最新代码、运行结果）。

### 风险

- **噪声**：注入越多，信噪比越低
- **成本**：token 消耗随注入量线性上升
- **注入攻击**：不可信内容（如被分析项目里的恶意注释）可能影响模型行为
- **过时**：缓存/索引未更新导致注入陈旧信息

---

## Q7 DeepSeek 的上下文窗口有多大？

截至调研时点（以官方为准）：

| 模型 | 上下文窗口 | 备注 |
|:-----|:----------|:-----|
| DeepSeek-V4 | **1M tokens** | 长上下文旗舰 |
| DeepSeek-V3.2 | 128K | 通用 |
| DeepSeek-R1 | 128K（开源权重）/ 64K（API） | 推理模型 |

> 注意：**标称窗口 ≠ 有效推理质量**。超长上下文存在"中间遗忘"（lost in the middle）现象，关键信息应放在开头/结尾。

---

## Q8 big-pickle 的上下文窗口与底层模型？

- **模型 ID**：`opencode/big-pickle`
- **官方标称上下文**：**200K tokens**
- **底层模型**：DeepSeek-V4-Flash（据 OpenCode Zen 提供方说明）
- **获取方式**：OpenCode Zen 上免费提供

### 实践建议

- 200K 适合"读大文件 + 多轮工具调用"，但**不要塞满**；留出工具输出空间。
- 长任务优先"分层摘要 + 按需检索"，而非一次性灌入全部上下文。

---

## Q9 UI 如何与 LLM 注入配合？

- **UI（TUI / Web 面板）负责**：展示会话、选择模型、触发命令、审阅 diff、管理权限。
- **真正的注入由 agent runtime 完成**：UI 不直接改写模型上下文；它通过"发送用户消息/执行命令/调用工具"间接影响注入。
- **本仓库的 Web 面板**（`arch_quality.ui.server`）是**操作面板**：把 CLI 入口包装成浏览器可点的按钮，本质仍是调用同一套 Python 引擎，不改变 LLM 上下文机制。

> 结论：UI 是"驾驶舱"，注入是"油门/供油系统"，两者解耦。

---

## Q10 LLM 在 arch-quality 运行中如何参与？

**核心结论：引擎是确定性的，LLM 只做编排与解释。**

### 实证

- `src/arch_quality/` 下**没有任何 LLM API 调用**（grep `openai`/`anthropic`/`api_key`/`requests.post` 无命中；仅 `arch_metrics_multilang.py` 里 tcl 关键字列表含 "http"，属误报）。
- 所有评分（结构/多语言/模板/数值/求解器物理场/几何/ACL）由纯 Python 计算。

### 分层职责

| 层 | 主体 | 职责 |
|:---|:-----|:-----|
| T1 规划 | LLM | 理解需求，决定跑哪个引擎、哪些参数 |
| T2 工具调用 | LLM | 调用 CLI/脚本，读取报告 |
| T3 计算 | 确定性引擎 | 建图、算分、跑 MLR 规则、出 JSON |
| T4 解释/建议 | LLM | 解读报告、生成 Markdown、给改进建议 |

> 好处：**可复现、可回归、可审计**；LLM 的不确定性被隔离在"解释层"。

---

## Q11 预注入点在 arch-quality 流程的哪个环节？

预注入（把项目信息提前放入上下文）主要发生在：

1. **T1 规划阶段**：注入"项目地图"——语言构成、目录结构、`build_dir`、已有报告/基线，帮助 LLM 选对引擎与参数。
2. **T4 解释阶段**：注入"证据候选"——违规片段、依赖路径、规则命中详情，提升解释准确性。

### 不放注入的环节

- **T3 计算阶段不做 LLM 注入**：保持确定性，避免模型影响评分。
- 注入内容来自 **FileIndex / DepGraph / 规则命中结果**，而非 LLM 生成，保证可追溯。

---

## Q12 FileIndex 在哪里、怎么产生？

### 位置

- **类定义**：`src/arch_quality/arch_core.py:124`（`class FileIndex`）
- **构造**：`src/arch_quality/arch_core.py:179`（`__init__(self, root, build_dir="", cache_file="")`）
- **语言映射**：`arch_core.py:127` 的 `LANG_MAP`

### 产生方式

1. 接收项目根目录 `root`（可选 `build_dir`、`cache_file`）。
2. 用 `os.walk` 遍历（配合 `LANG_MAP` 与排除规则），构建**内存索引**：文件路径、语言、行数、大小、哈希等。
3. 若传入 `cache_file`，则读写缓存（按 mtime 失效）；**默认不传 → 不落盘**。
4. 进程结束，内存索引释放。

### 谁在用它

- 标准评估、多语言、模板、数值、求解器物理场、几何、ACL 各引擎共享同一个 `FileIndex`。
- 报告 JSON 里的 `files.total` / `cpp_files` 等只是**汇总投影**，不是完整索引。

---

## Q13 首次运行时 FileIndex 如何产生？

**首次运行 = 现场扫描，不依赖预生成文件。**

```
python -m arch_quality <项目路径>
   → FileIndex(root) 扫描磁盘
   → 内存构建索引
   → (可选) 若指定 cache_file 则写缓存
   → 各引擎消费索引 → 产出报告 JSON/Markdown
```

### 常见误解澄清

- ❌ 以为"Disk 上一定有 FileIndex 文件"——没有，默认是内存结构。
- ✅ 报告 JSON 是**结果投影**，可落盘；FileIndex 本体不落盘（除非显式传 cache_file）。
- ⚠️ 大项目（10K+ 文件）首次扫描较慢，后续若用缓存可加速；本仓库已做 `os.walk` + 惰性行数等优化。

---

## Q14 OpenCode 为 Agent 持续进化提供哪些方案/支持？

OpenCode 不提供"模型自我进化"，而是提供**让 Agent 行为可持续迭代的工程化插槽**。按闭环分层：

### 1) 能力注入层

| 机制 | 作用 | 本仓库实例 |
|:-----|:-----|:-----------|
| **Skill（SKILL.md）** | 按需注入的模块化能力包 | `src/arch_quality/skills/*.md`（8 个）、`.opencode/skills/`（11 个） |
| **Agent 定义** | `mode: primary/subagent`、模型、权限、prompt | `opencode.json` 的 `architecture-quality`（primary） |
| **Command** | 可复用 `/命令` 工作流 | 可扩展 |
| **MCP Server** | 挂接外部工具/数据源 | 可扩展 |

### 2) 约束层

- `permission` 三态（allow / ask / deny），可细到命令前缀
- 本仓库 `architecture-quality` 为**只读评估者**：`edit: deny`、`write: deny`、`bash` 白名单
- 配置层级：全局 `~/.config/opencode/opencode.jsonc` 覆盖项目 `opencode.json`

### 3) 反馈层

- Plugin 钩子：`tool.execute.before/after`、`event`、`chat.message`、`permission.ask`
- 本仓库 `.opencode/plugins/agent-assert.js` 在评估命令后自动断言
- `opencode run --format json` 无头结构化输出，供外部消费
- Session：`--continue` / `--session` 保持连续性

### 4) 验证层（本仓库特色）

- `opencode-harness/`：case JSON → `opencode run` → assertors（tool_usage / output_schema / score_sanity）→ reports → 失败重试
- `rules.json` 单一事实源，Python assertor 与 JS 插件共享
- 与 pytest 互补：pytest 验工具，harness 验 Agent 行为

### 5) 沉淀层

- `AGENTS.md`（常驻规则）
- `skills/*.md` + `.opencode/skills/`
- `opencode-harness/rules.json`
- Obsidian 知识库（35+ 技术卡片 + 每日亮点）
- 回归快照 `tests/regression/snapshots/`

### 6) 版本化

- 配置、skills、rules、harness cases 全部进 git：可 diff、可回滚、可 review

### 局限

- ❌ 不会自动从对话学习/微调
- ❌ 无内置 Agent 评估基准（需自建 harness）
- ❌ 无自动回归守护（需自己实现）

> **一句话**：OpenCode 提供闭环所需的全部"插槽"，闭环逻辑（改 Skill → harness 验证 → 沉淀 → 版本化）要自己拼。本仓库的 `opencode-harness + agent-assert.js + knowledge-base` 就是落地范例。

---

## Q15 sidecar 是什么意思？

"sidecar"（边车）有两类常见含义：

### 1) 架构边车模式（Sidecar Pattern）

一个**辅助进程/容器紧挨着主应用运行**，共享生命周期，通过 localhost 通信。

```
┌─────────────────────────┐
│  主应用 (main app)       │
│  ┌─────────┐  ┌────────┐│
│  │ 业务逻辑 │  │ sidecar││
│  └─────────┘  └────────┘│
│      ↕ 本地通信           │
└─────────────────────────┘
```

- 典型：Envoy 代理边车、日志采集边车、密钥同步边车
- 特征：同生命周期、同节点、对主应用透明
- 价值：把日志/监控/代理/鉴权等横切关注点从业务代码剥离

### 2) Sidecar 文件

主文件旁伴生的辅助文件，同名不同后缀：

```
main.py
main.py.sidecar.json   ← 元数据
photo.jpg
photo.jpg.md           ← 说明
movie.mp4
movie.srt              ← 字幕
```

### 与 arch-quality 的类比

| 主件 | 类似 sidecar 的伴生物 |
|:-----|:---------------------|
| 评估引擎 | `skills/*.md`（权重/规则定义，运行时解析） |
| 报告输出 | `tests/regression/snapshots/*.json`（回归基线） |

## Q16 OpenCode 有遥测吗？如何关闭？

> **来源说明**：本节为事后调研补充（原会话中的遥测问答未进入整理上下文）。结论综合维护者声明、官方文档与社区审计，**存在版本差异和争议**，请以你所用版本实测为准。

### 分层结论

1. **核心 CLI 默认没有"主动上报到 OpenCode 自家服务器"的遥测 SDK** —— 维护者声明 + 两次独立审计支持这一点。
2. 但**默认存在后台网络请求**：`models.dev`（拉取模型列表）、版本更新检查（可关）。
3. **OpenTelemetry 是 opt-in**：默认关闭，且只导出到**你自己指定的 collector**，不存在 OpenCode 官方默认采集端。
4. 以下功能会外发数据，但属于**按需/显式启用**：session 分享、websearch（Exa）、使用 opencode/Zen provider（prompt 可能服务端留存）。
5. **争议点**：有第三方文章称存在无条件 Sentry 上报、41 个 `OPENCODE_DISABLE_*` 开关无一涉及遥测；这与维护者/审计结论矛盾，可能针对特定版本或发行渠道，**需按版本核实**。

### 默认网络行为

| 目的地 | 内容 | 性质 |
|:-------|:-----|:-----|
| `models.dev` | 模型列表 | 后台请求，非遥测 |
| 更新检查 | 版本信息 | 可 `autoupdate: false` 关闭 |
| 你配置的 LLM provider | prompt / response | 业务必需 |
| OpenCode 自有服务 | 仅当使用其账号 / Zen | 见下 |

### 可能外发的"非默认"路径

| 路径 | 触发条件 | 关闭方式 |
|:-----|:---------|:---------|
| Session 分享 | `share` 非 disabled | `"share": "disabled"` |
| Websearch（Exa） | 使用 websearch 工具 | `"tools": {"websearch": false}` + `disabled_providers: ["exa"]` |
| OpenTelemetry | 显式开启 | 不设 endpoint / `experimental.openTelemetry: false` |
| Zen provider | 使用 `opencode.ai` token | 改用自有 API key 直连 provider |

### 关闭清单（建议）

环境变量（第三方加固脚本常用组合）：

```sh
OPENCODE_DISABLE_TELEMETRY=1
DO_NOT_TRACK=1
DISABLE_TELEMETRY=1
DISABLE_ERROR_REPORTING=1
SENTRY_DSN=""
OTEL_EXPORTER_OTLP_ENDPOINT=""
OTEL_EXPORTER_OTLP_HEADERS=""
```

配置：

```jsonc
{
  "share": "disabled",
  "autoupdate": false,
  "experimental": { "openTelemetry": false },
  "tools": { "websearch": false },
  "disabled_providers": ["exa"]
}
```

> ⚠️ `OPENCODE_DISABLE_TELEMETRY` 等开关的**有效性随版本变化**，部分来自第三方加固脚本而非官方文档；v2 迁移文档称 `openTelemetry` 配置字段已不再支持。请以对应版本文档与本机抓包实测为准。

### 与 Agent 持续进化的关系

- **可观测性 ≠ 遥测外发**：OpenTelemetry 的 spans（token、耗时、工具调用）可用于本地评估 Agent 行为，但应导出到**自建 collector**。
- 本仓库 harness 走**本地/离线**验证（`opencode run --format json` + assertors），不依赖外部遥测，符合"可复现、可审计"原则。
- 若要在 CI 观测 Agent，建议 `OPENCODE_TRACEPARENT` + 自建 OTLP collector，而非依赖厂商侧遥测。
- 插件生态另有各自的遥测（如 opencode-plugin-otel 为 opt-in；oh-my-opencode 是独立产品、自带 PostHog 遥测），需分别确认。

### 参考来源

- 维护者声明：GitHub issue #5554 / #459（"there isnt any telemetry"；后台请求为 models.dev）
- 官方配置文档：<https://opencode.ai/docs/config/>
- 隐私政策：<https://opencode.ai/legal/privacy-policy>（面向网站/账号/服务）
- 独立审计：zenn 审计（默认无隐藏遥测通道）、SPERIXLABS（本地 Ollama 场景零外发）
- 争议/第三方：stridenote.net 文章（Sentry 无条件上报之说）、corporate-launcher 的 kill switches
- OpenTelemetry 插件：`DEVtheOPS/opencode-plugin-otel`（opt-in，默认不启用）

---

---

## 附录：仓库实证索引

| 事实 | 证据位置 |
|:-----|:---------|
| Agent 定义与权限 | `opencode.json`（`architecture-quality`, mode primary, edit/write deny） |
| FileIndex 定义/构造 | `src/arch_quality/arch_core.py:124` / `:179` |
| LANG_MAP | `src/arch_quality/arch_core.py:127` |
| src 无 LLM API 调用 | grep `openai`/`anthropic`/`api_key`/`requests.post` 无命中 |
| 引擎 skill 清单 | `src/arch_quality/skills/`（8 个 .md） |
| opencode skill 清单 | `.opencode/skills/`（11 个） |
| Harness | `opencode-harness/harness_runner.py` + `assertors/` + `cases/` |
| 自动断言插件 | `.opencode/plugins/agent-assert.js` |
| 共享规则 | `opencode-harness/rules.json` |
| 遥测调研来源 | 见 Q16「参考来源」（维护者声明 / 官方文档 / 独立审计 / 争议文章） |

---

*本文档由 2026-09-28 会话整理，供知识库沉淀与后续参考。*
