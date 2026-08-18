# Opencode Skill 编写指南

**版本**: 1.0  
**日期**: 2026-06-25  
**来源**: opencode 内置 `customize-opencode` skill

---

## 一、什么是 Skill

Skill 是 opencode 中的领域知识包，为模型提供特定任务的指令、模板和约束。当用户请求匹配 Skill 的 `description` 时，模型会自动加载并执行该 Skill。

---

## 二、文件结构

```
.opencode/skills/<skill-name>/SKILL.md
```

| 元素 | 要求 |
|:-----|:------|
| 文件名 | 必须是 **`SKILL.md`**（大小写敏感） |
| 目录名 | 小写字母+连字符，与 `name` 字段一致 |

示例：

```
.opencode/skills/
├── knowledge-base-management/
│   └── SKILL.md
└── code-review/
    └── SKILL.md
```

---

## 三、Frontmatter

每个 `SKILL.md` 文件必须以 `---` 包裹的 YAML frontmatter 开头。

```markdown
---
name: my-skill
description: Use when the user asks to do X, Y, or Z. Front-load trigger keywords.
license: MIT
compatibility: opencode >= 1.0
metadata:
  key: value
---

# 正文内容
```

### 字段说明

| 字段 | 必填 | 类型 | 说明 |
|:-----|:----:|:-----|:------|
| `name` | ✅ | string | 小写+连字符，≤64 字符，与目录名一致 |
| `description` | 有效必填 | string | 覆盖"做什么"和"何时使用"。**用第三人称**（"Use when..."），前置触发关键词。用 "Use ONLY when..." 限定范围 |
| `license` | ❌ | string | 许可证 |
| `compatibility` | ❌ | string | 兼容性说明 |
| `metadata` | ❌ | dict | 自定义键值对 |

### description 编写要点

`description` 是 Skill 最关键的部分——模型根据它决定是否加载 Skill。

**正确示例：**
```yaml
description: >
  管理 arch-quality 项目的每日工作总结和知识沉淀。Use when the user asks to create a daily report,
  write daily highlight, extract knowledge, update knowledge base, or manage documentation.
  All dates use China Standard Time (UTC+8).
```

- ✅ 前置触发关键词（daily report, highlight, knowledge base）
- ✅ 用第三人称
- ✅ 覆盖"做什么"和"何时触发"

**错误示例：**
```yaml
description: 知识库管理技能
```

- ❌ 太简短，模型无法判断何时触发
- ❌ 没有触发关键词
- ❌ 没有说明使用条件

---

## 四、正文编写建议

### 推荐结构

```markdown
## 使用场景

列出 Skill 适用的具体场景。

## 流程

分步骤说明执行过程，可包含：
- 命令示例
- 代码模板
- 注意事项

## 相关文件

列出与此 Skill 相关的文件路径。
```

### 模板示例

```markdown
## 流程

### 1. 创建文件

```bash
touch file.txt
```

### 2. 运行脚本

```bash
python script.py
```
```

---

## 五、注册方式

### 方式一：路径扫描（推荐）

在 `opencode.json` 中指定扫描目录：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "skills": {
    "paths": [".opencode/skills"]
  }
}
```

opencode 会自动递归扫描 `paths` 下所有 `**/SKILL.md` 文件。

### 方式二：URL 远程加载

```json
{
  "skills": {
    "urls": ["https://example.com/.well-known/skills/"]
  }
}
```

---

## 六、生效方式

Skill 文件保存后，**退出并重启 opencode** 才能生效。运行中的会话不会热加载已更改的配置。

---

## 七、完整示例

```markdown
---
name: knowledge-base-management
description: >
  管理 arch-quality 项目的每日工作总结和知识沉淀。Use when the user asks to create
  a daily report, write daily highlight, extract knowledge, update knowledge base,
  or manage documentation. All dates use China Standard Time (UTC+8).
---

# 知识库与日报管理技能

管理 arch-quality 项目的每日工作总结和知识沉淀。

## 使用场景

- 撰写每日工作总结
- 提取知识库亮点
- 创建技术卡片

## 流程

### 1. 创建日报

```bash
# 日报存放于 daily report/dailyreportYYYY-MM-DD.md
```
```

---

## 八、注意事项

| 注意点 | 说明 |
|:-------|:------|
| **文件名大小写** | 必须是 `SKILL.md`，不能是 `skill.md` 或 `SKILL.MD` |
| **审核机制** | Skill 文件由人工审核，确保准确性和安全性 |
| **重启生效** | 修改后必须重启 opencode |
| **description 是关键** | 模型根据 description 决定是否加载，务必写清楚触发条件 |
| **不要内联注册** | 用 `skills.paths` 自动扫描，不要在 `opencode.json` 中内联定义 |
