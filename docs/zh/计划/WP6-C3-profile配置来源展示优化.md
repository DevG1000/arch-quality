# WP-6 C3：profile `config_source` 展示优化报告

> **版本**：1.0
> **日期**：2026-11-24
> **目标**：让报告准确、可移植地展示 profile 配置来源，区分文件配置与 CLI 覆盖

## 1. 原问题

| 问题 | 现状 |
|:--|:--|
| 绝对路径 | `profile.config_source` 直接输出本机绝对路径 |
| Markdown 缺失 | 报告正文没有 profile 配置来源章节 |
| CLI 覆盖误标 | `--profile` 覆盖配置文件时，`config_source` 仍指向文件，无法看出 profile 值来自 CLI |
| 无可移植展示 | 报告迁移到其他机器后路径不可读 |

## 2. 实施内容

### 2.1 provenance 字段

`profile` 元数据新增：

```json
{
  "config_source": "D:/proj/arch-quality.yaml",
  "config_source_display": "arch-quality.yaml",
  "config_source_kind": "arch-quality.yaml",
  "profile_source": "cli",
  "cli_override": true
}
```

| 字段 | 含义 |
|:--|:--|
| `config_source` | 原始来源（兼容旧字段） |
| `config_source_display` | 报告安全展示：项目内相对路径 / 文件名 / `<CLI --profile>` |
| `config_source_kind` | `arch-quality.yaml` / `pyproject.toml` / `cli` / `none` |
| `profile_source` | profile 值实际来源：配置文件或 `cli` |
| `cli_override` | CLI 是否覆盖了配置文件中的 profile |

### 2.2 CLI 覆盖标注

- 仅 `--profile`、无配置文件：
  - `config_source = "<CLI --profile>"`
  - `config_source_kind = "cli"`
  - `profile_source = "cli"`
- 有配置文件 + `--profile`：
  - `config_source` 保留文件路径；
  - `profile_source = "cli"`；
  - `cli_override = true`。

### 2.3 Markdown 展示

新增 `## Profile 配置来源` 章节：

```text
| Profile | numerical |
| 配置来源 | arch-quality.yaml |
| 来源类型 | arch-quality.yaml |
| Profile 来源 | CLI --profile（覆盖配置文件） |
| 启用引擎 | standard, numerical |
| 跳过引擎 | ... |
| 子集评分 | 是 |
```

不再输出本机绝对路径。

## 3. 验证

```text
tests/test_profile.py    35 passed
```

覆盖：

- YAML 配置来源相对路径；
- `pyproject.toml` 来源类型；
- CLI-only profile；
- CLI 覆盖配置文件；
- Markdown 包含来源章节且不含绝对路径。

## 4. 影响

- 无评分/权重/规则变化；
- 完全向后兼容：保留 `config_source` 原字段；
- 仅增强报告可读性与 provenance 准确性。
