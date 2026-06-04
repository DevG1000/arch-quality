# arch-quality

软件架构质量评估引擎 — 系统性分析、评估和改进软件系统架构质量，支持多语言混合依赖评估。

## 快速开始

### 安装

```bash
git clone https://github.com/<your-org>/arch-quality.git
cd arch-quality
pip install -e .
```

> Windows 用户如遇 `arch-quality` 命令找不到，请将 Python Scripts 目录加入 PATH，
> 或使用 `python -m arch_quality` 替代。详见 [安装部署指南](docs/zh/安装部署指南.md)。

### 命令行使用

```bash
# 完整评估（生成 JSON + Markdown 报告）
arch-quality [项目路径]

# 指定报告存储模式
arch-quality --report-mode central [项目路径]
arch-quality --report-mode local [项目路径]

# 仅输出 JSON / Markdown
arch-quality --json [项目路径]
arch-quality --md [项目路径]

# Python 模块方式运行
python -m arch_quality [项目路径]

# 子命令
arch-quality-standard --metrics [项目路径]   # 仅标准 4 维指标
arch-quality-multilang --full [项目路径]     # 仅多语言 6 维 + MLR
```

### 作为库使用

```python
from arch_quality.arch_report import ComprehensiveReport
from arch_quality.arch_core import load_history, save_history

reporter = ComprehensiveReport("/path/to/project")
data = reporter.generate()
```

### OpenCode 智能体集成

需要两步：复制智能体定义 + 配置 `opencode.jsonc`。

**步骤 1**：复制智能体定义到 OpenCode 全局 agents 目录：

```bash
# Windows
copy integrations\opencode\architecture-quality.md %USERPROFILE%\.config\opencode\agents\

# Linux/macOS
cp integrations/opencode/architecture-quality.md ~/.config/opencode/agents/
```

**步骤 2**：在 `~/.config/opencode/opencode.jsonc` 中注册智能体：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "architecture-quality": {
      "description": "架构质量评估智能体 — 系统性分析、评估和改进软件系统架构质量，支持多语言混合依赖评估",
      "prompt_file": "~/.config/opencode/agents/architecture-quality.md",
      "mode": "subagent",
      "permission": {
        "read": "allow",
        "bash": {
          "*": "ask",
          "arch-quality*": "allow",
          "arch-quality *": "allow",
          "python -m arch_quality*": "allow"
        },
        "edit": "deny",
        "task": "allow",
        "skill": "allow"
      }
    }
  }
}
```

修改后**重启 OpenCode** 生效。详见 [安装部署指南](docs/zh/安装部署指南.md)。

## 评估维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 结构质量 | 30% | 模块化、耦合度、内聚度、复杂度、可测试性 |
| 设计质量 | 25% | SOLID 原则、设计模式、架构风格、反模式 |
| 文档质量 | 20% | README、CHANGELOG、ADR、注释、架构文档 |
| 演进质量 | 25% | 历史追溯、债务趋势、依赖过时、废弃代码 |

多语言混合依赖评估（结构质量内部增强）：
- 跨语言调用强度、影响半径、回调深度、绑定一致性、脚本越界、循环依赖

## 报告存储

| 模式 | 路径 | 适用场景 |
|------|------|---------|
| `local` | `<项目根>/.opencode/arch-reports/YYYY-MM-DD/` | 单项目本地保存 |
| `central`（默认） | `~/.config/opencode/arch-reports/<project-slug>/YYYY-MM-DD/` | 多项目集中管理 |

## 项目结构

```
arch-quality/
├── src/arch_quality/          # 核心包
│   ├── arch_core.py           # 核心引擎（文件索引、依赖图、Git历史）
│   ├── arch_metrics_standard.py   # 标准 4 维指标
│   ├── arch_metrics_multilang.py  # 多语言 6 维指标 + MLR 规则
│   ├── arch_report.py         # 综合报告生成
│   ├── arch_report_generator.py   # Markdown 报告模板
│   ├── arch_bindings_parser.py    # pybind11 绑定解析器
│   ├── arch_python_ast.py     # Python AST 调用提取
│   ├── arch_multilang_matcher.py  # 混合匹配器
│   └── skills/                # 权重定义
│       ├── arch-quality.md
│       └── multilang-dependency.md
├── tests/                     # 单元测试
├── docs/zh/                   # 中文指南
├── integrations/opencode/     # OpenCode 智能体定义
└── scripts/                   # 启动脚本
```

## 文档

| 文档 | 说明 |
|------|------|
| [安装部署指南](docs/zh/安装部署指南.md) | 新机器安装、PATH 配置、故障排除 |
| [架构质量标准指南](docs/zh/架构质量标准指南.md) | 4 大维度评分标准与算法 |
| [多语言混合依赖评估指南](docs/zh/多语言混合依赖评估指南.md) | 6 维指标 + 12 条 MLR 规则 |
| [多语言混合依赖验证案例库](docs/zh/多语言混合依赖验证案例库.md) | 测试场景与验证方法 |
| [OpenCode 智能体开发指南](docs/zh/OpenCode%20智能体开发指南.md) | 智能体开发与集成 |

## 许可证

MIT License