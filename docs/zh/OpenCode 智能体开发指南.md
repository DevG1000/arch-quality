# OpenCode 智能体开发指南

---

## 一、什么是 OpenCode 智能体

OpenCode 智能体是专门化的 AI 助手，通过自定义 prompt、模型和工具权限来聚焦特定任务和工作流。

### 两种类型

| 类型 | 说明 | 切换方式 | 内置示例 |
|------|------|---------|---------|
| **Primary**（主智能体） | 直接交互的主要助手，全工具访问 | Tab 键循环切换 | `build`, `plan` |
| **Subagent**（子智能体） | 专门化助手，由主智能体或 @ 调用 | `@agent-name` 提及 | `general`, `explore`, `scout` |

### 内置智能体一览

| 名称 | 类型 | 用途 |
|------|------|------|
| **build** | primary | 默认智能体，所有工具可用，用于开发工作 |
| **plan** | primary | 受限智能体，只读分析+规划，不能修改代码 |
| **general** | subagent | 通用任务，可读写，用于并行执行多步骤工作 |
| **explore** | subagent | 快速只读探索代码库，不能修改文件 |
| **scout** | subagent | 只读，用于外部文档和依赖研究 |
| **compaction** | primary(hidden) | 压缩长上下文为简要摘要，自动运行 |
| **title** | primary(hidden) | 生成简短会话标题，自动运行 |
| **summary** | primary(hidden) | 创建会话摘要，自动运行 |

---

## 二、智能体能力分层

智能体从简单到复杂分为 4 层：

| 层 | 名称 | 组成 | 外部依赖 | 适用场景 |
|:-:|------|------|---------|---------|
| 1 | 纯 Prompt | `.md` 文件 | 无 | 代码审查、文档编写、技术咨询 |
| 2 | + Skills | `.md` + skill 文件 | 无 | 按规范评审、定量评估 |
| 3 | + Commands | `.md` + skill + 脚本 | Python/Node 等运行时 | 精确分析、依赖图扫描、指标计算 |
| 4 | + MCP | `.md` + skill + MCP Server | MCP 服务器 | 复杂工作流、API 集成、数据库查询 |

### 第 1 层：纯 Prompt 智能体

仅一个 `.md` 文件，完全依赖 LLM 固有知识。

```markdown
---
description: Reviews code for quality and best practices
mode: subagent
permission:
  edit: deny
  bash: deny
---
You are in code review mode. Focus on:
- Code quality and best practices
- Potential bugs and edge cases
- Performance implications
```

**优点**：零依赖，快速创建
**缺点**：所有判断基于 LLM 训练数据，无精确量化能力

### 第 2 层：Prompt + Skills

Skill 文件在智能体启动时注入上下文，提供 LLM 本身不具备的领域知识。

**注册方式**（`opencode.json`）：

```json
{
  "skills": {
    "paths": [".opencode/skills/"]
  }
}
```

**Skill 文件示例**（`.opencode/skills/评分规则.md`）：

```markdown
## 评分公式

| 维度 | 权重 |
|------|------|
| 可维护性 | 40% |
| 可扩展性 | 30% |
| 可测试性 | 30% |
```

**与第 1 层的区别**：

| | 第 1 层 | 第 2 层 |
|--|---------|---------|
| 知识来源 | LLM 训练数据 | LLM + 注入的 Skill 文件 |
| 可定制性 | 低 | 高（skill 可随时更新） |
| 量化能力 | 无 | 弱（LLM 按 skill 公式估算） |

### 第 3 层：Prompt + Skills + Commands

智能体通过 `bash` permission 执行外部命令，获取结构化数据后基于 skill 知识分析。

```
用户: @my-agent 分析项目
  │
  ▼
智能体接收 prompt，知道有 my-tool 命令
  │
  ▼
智能体调用 bash: my-tool scan .
（外部脚本独立执行分析）
  │
  ▼
智能体接收结构化结果
参考 skills/*.md 中的规则
  │
  ▼
智能体输出人类可读报告
```

**原理**：Command 是"执行器"，Skill 是"解释器"
- Command 负责精确计算（代码实现）
- Skill 提供评估规则（让 LLM 理解计算结果的含义）

### 第 4 层：Prompt + Skills + MCP Server

通过 MCP（Model Context Protocol）服务器注册动态工具集。工具可以是任何能力（数据库查询、API 调用等），返回值直接注入 LLM 上下文。

**注册方式**（`opencode.json`）：

```json
{
  "mcp": {
    "my-server": {
      "type": "local",
      "command": ["node", "server.js"]
    }
  }
}
```

**与第 3 层的区别**：

| | 第 3 层 Commands | 第 4 层 MCP |
|--|-----------------|-------------|
| 调用方式 | bash permission 执行命令 | 标准协议注册 tool |
| 返回值处理 | LLM 读取 stdout | 直接注入上下文 |
| 工具发现 | 无（需 prompt 中说明） | 自动注册到 tool list |
| 状态管理 | 无状态 | 可以有状态 |
| 部署复杂度 | 低 | 高 |

### 选择建议

```
项目刚起步         → 第 1 层（快速验证）
需要遵循规范      → 第 2 层（加 skill）
需要精确数据      → 第 3 层（加 commands）
需要企业集成      → 第 4 层（加 MCP）
```

---

## 三、开发智能体的三种方式

### 方式 1：`opencode agent create`（推荐）

交互式命令行，自动生成 `.md` 文件：

```bash
opencode agent create
```

交互步骤：
1. 选择保存位置（全局 `~/.config/opencode/agents/` 或项目 `.opencode/agents/`）
2. 输入描述
3. 自动生成 system prompt 和标识符
4. 选择权限
5. 生成 `.md` 文件，文件名即智能体名称

### 方式 2：手动编写 Markdown 文件

在以下任意目录创建 `.md` 文件：
- **全局**：`~/.config/opencode/agents/`（所有项目可用）
- **项目**：`.opencode/agents/`（仅当前项目）

完整格式见下一节。

### 方式 3：JSON 配置注册

在 `opencode.json` 中直接注册：

```json
{
  "agent": {
    "my-agent": {
      "description": "我的自定义智能体",
      "mode": "subagent",
      "permission": {
        "read": "allow",
        "edit": "deny"
      },
      "prompt": "{file:./prompts/my-agent.txt}"
    }
  }
}
```

`prompt` 字段支持 `{file:}` 和 `{env:}` 变量引用外部内容。

### 对比

| | 方式 1 | 方式 2 | 方式 3 |
|--|--------|--------|--------|
| 上手速度 | 最快 | 手动 | 手动 |
| 灵活性 | 中 | 高 | 高 |
| 跨项目共享 | 可选 | 控制位置 | 仅 opencode.json 所在项目 |
| 版本控制 | 可 | 可 | 可 |

---

## 四、Markdown 智能体文件格式详解

### 完整骨架

```markdown
---
description: 必填。描述智能体做什么，用于 @ 匹配
mode: subagent              # primary | subagent | all（默认 all）
model: anthropic/claude-xxx # 可选，覆盖全局模型
temperature: 0.1            # 可选，0.0-1.0
steps: 10                   # 可选，最大迭代次数
color: "#ff6b6b"            # 可选，UI 颜色
hidden: false               # 可选，是否从 @ 菜单隐藏
permission:
  read: allow
  edit: deny
  bash:
    "*": ask
    "git *": allow
    "python script.py": allow
  task: allow
  skill: allow
---
# 智能体名称

## 使命
在此定义智能体的核心职责。

## 工作流程
1. 步骤一
2. 步骤二
...

## 命令说明
- `/command-name` — 命令说明
```

### YAML 字段详解

**`description`**（必填）
决定智能体何时被主智能体自动调度。应简洁准确。

**`mode`**
- `primary` — Tab 键可切换为主智能体
- `subagent` — 通过 `@` 调用
- `all` — 两者都可（默认）

**`permission`** — 控制智能体可用工具

| 权限键 | 控制的工具 |
|--------|-----------|
| `read` | `read` |
| `edit` | `write`, `edit`, `apply_patch` |
| `glob` | `glob` |
| `grep` | `grep` |
| `bash` | `bash` |
| `task` | `task` |
| `webfetch` | `webfetch` |
| `websearch` | `websearch` |
| `skill` | `skill` |
| `question` | `question` |

每个键可设 `allow` / `ask` / `deny`。`bash` 支持 glob 模式细分：

```yaml
permission:
  bash:
    "*": ask
    "python *": allow
    "git push": deny
```

**`hidden`**
设为 `true` 在 `@` 菜单中隐藏，仅通过 `task` 工具调用。

**`color`**
UI 颜色，支持 hex（`#FF5733`）或主题色（`accent`, `warning` 等）。

### Prompt 主体写法建议

```markdown
## 使命
清晰说明智能体的核心职责。

## 核心能力
列出该智能体能够处理的分析维度。

## 工作流程
分阶段描述执行步骤。

## 输出格式
说明报告的结构和内容。

## 约束
列出该智能体不应该做的事情。
```

---

## 五、Skills 的使用

### 什么是 Skill

Skill 是注入智能体上下文的领域知识文本文件（Markdown），提供 LLM 本身不具备的专业知识。

### 注册方式

在 `opencode.json` 中配置：

```json
{
  "skills": {
    "paths": [".opencode/skills/", "~/.config/opencode/skills/"]
  }
}
```

`paths` 是一个数组，可指定多个 skill 目录。

### 引用方式

Skill 通过 `skill` 关键词在会话中加载。在智能体 prompt 中说明：

```markdown
执行评估时，加载 skills/arch-quality.md 中的评分公式。
```

### Skill 文件格式

Skill 是纯 Markdown，没有特殊语法要求。但为了配合方案 D（Python 运行时解析权重），建议权重表格格式统一：

```markdown
| 维度 | 权重 |
|------|------|
| 维度一 | 30% |
| 维度二 | 25% |

## 评分算法

### 维度一
```
score = ...
```
```

---

## 六、Commands 与外部工具

### bash permission 配置

允许智能体执行外部命令：

```yaml
permission:
  bash:
    "*": ask
    "my-tool *": allow
    "python *": allow
```

### 脚本的可发现性问题

脚本文件（如 `.py`）没有全局注册机制。智能体需要知道脚本的精确路径或在 PATH 中。

### 解决方式

| 方式 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| 项目内脚本 | `.opencode/scripts/*.py` | 零配置 | 仅当前项目可用 |
| 全局 CLI 工具 | `pip install` 安装为系统命令 | 跨项目，版本管理 | 需要 `pip install` |
| npx/直接执行 | `python3 path/to/script.py` | 简单 | 路径依赖 |

### 数据流动模式

```
Command 输出 JSON 结构化数据
         │
         ▼
LLM 读取 stdout，按 skill 规则分析
         │
         ▼
LLM 输出人类可读报告
```

---

## 七、完整示例：架构质量评估智能体

该智能体属于**第 3 层**（Prompt + Skills + Commands），用于系统性分析软件架构质量。

### 文件结构

```
.opencode/
├── agents/
│   └── architecture-quality.md    ← 智能体定义
├── skills/
│   ├── arch-quality.md            ← 通用架构质量评估知识
│   └── multilang-dependency.md    ← 多语言依赖评估知识
└── scripts/
    ├── arch_core.py               ← 核心引擎
    ├── arch_metrics_standard.py   ← 标准指标
    ├── arch_metrics_multilang.py  ← 多语言指标
    ├── arch_report.py             ← 综合报告生成
    └── arch_report_generator.py   ← 报告格式模板
```

### 智能体文件

```markdown
---
description: 架构质量评估 — 系统性分析、评估和改进软件系统架构质量
mode: subagent
permission:
  read: allow
  bash:
    "*": ask
    "python .opencode/scripts/arch_scan*": allow
    "python .opencode/scripts/arch_report*": allow
  edit: deny
  task: allow
  skill: allow
---
```

### 权重同步机制（方案 D）

Python 命令启动时从 skill Markdown 表格中解析权重，保证权重与文档同步，无需额外配置文件。

```python
def load_weights_from_skill(skill_path: str) -> dict:
    pattern = r"^\|\s*(.+?)\s*\|\s*(\d+)%\s*\|"
    matches = re.findall(pattern, text, re.MULTILINE)
    return {name.strip(): int(pct) / 100 for name, pct in matches}
```

权重表格式被破坏时抛出 `ValueError`，防止静默漂移。

---

## 八、跨项目部署

### 方式 A：全局 agents 目录

将 `.md` 文件放入 `~/.config/opencode/agents/`，即可在所有项目中通过 `@` 调用。

```bash
cp .opencode/agents/my-agent.md ~/.config/opencode/agents/
```

### 方式 B：全局 Python 包

将脚本打包为 pip 安装的 CLI 工具：

```
site-packages/my_tool/
├── __init__.py
├── core.py
├── metrics.py
└── report.py
```

在智能体的 bash permission 中允许执行全局命令：

```yaml
permission:
  bash:
    "my-tool *": allow
```

### 注意事项

- 第 1、2 层智能体（纯 prompt / +skills）最易于跨项目部署，只需复制 `.md` 文件
- 第 3、4 层智能体需要额外处理外部命令或 MCP 服务器的安装
- Skill 文件需要一并复制到全局位置并注册 `skills.paths`
