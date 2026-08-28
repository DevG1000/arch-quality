# arch-quality

软件架构质量评估引擎 — 系统性分析、评估和改进软件系统架构质量。支持标准架构评估、多语言混合依赖评估、C++ 模板元编程专项分析、数值算法精度保障评估、求解器/物理场模块化架构评估。

## 核心能力

5 个评估引擎，共 60 条规则（每条规则对应一个可机检的架构反模式/质量缺陷）：

| 引擎 | 模块 | CLI 入口 | 维度 | 规则 |
|------|------|----------|------|------|
| 标准架构 | arch_metrics_standard | arch-quality-standard | 4 维（结构/设计/文档/演进）× 16 子维 | SAR-001~012 |
| 多语言混合依赖 | arch_metrics_multilang | arch-quality-multilang | 6 维 | MLR-001~012 |
| 模板元编程 | arch_metrics_template | arch-quality-template | 6 维 | TPL（MLR-013~024） |
| 数值算法精度 | arch_metrics_numerical_accuracy | python -m arch_quality.arch_metrics_numerical_accuracy | 6 维 | NVR-001~012 |
| 求解器/物理场 | arch_metrics_solver_physics | python -m arch_quality.arch_metrics_solver_physics | 4 维 | MPR-001~012 |

综合入口 `arch-quality` 自动探测项目语言构成，按需启用多语言/模板/数值/求解器物理增强，合并生成 JSON + Markdown 报告。

维度与权重定义全部从 `src/arch_quality/skills/*.md` 运行时解析（合计必须 100%）。

## 快速开始

### 安装

```bash
git clone https://github.com/DevG1000/arch-quality.git
cd arch-quality
pip install -e .
```

> Windows 用户若 `arch-quality` 命令找不到，请将 Python Scripts 目录加入 PATH，或用 `python -m arch_quality` 替代。详见 [安装部署指南](docs/zh/安装部署指南.md)。

### 命令行使用

```bash
# 完整评估（自动探测引擎，生成 JSON + Markdown）
arch-quality [项目路径]

# 报告存储模式
arch-quality --report-mode central [项目路径]   # 默认：~/.config/opencode/arch-reports/<slug>/YYYY-MM-DD/
arch-quality --report-mode local [项目路径]     # 项目本地

# 仅 JSON / Markdown
arch-quality --json [项目路径]
arch-quality --md [项目路径]

# 单引擎
arch-quality-standard [项目路径]
arch-quality-multilang --full [项目路径]
arch-quality-template [项目路径]
python -m arch_quality.arch_metrics_numerical_accuracy [项目路径]
python -m arch_quality.arch_metrics_solver_physics [项目路径]

# 模块方式
python -m arch_quality [项目路径]
```

### 作为库使用

```python
from arch_quality.arch_report import ComprehensiveReport

reporter = ComprehensiveReport("/path/to/project")
data = reporter.generate()   # 返回综合评估 dict（overall_score / dimensions / mlr_violations ...）
```

### OpenCode 智能体集成

两步：复制智能体定义 + 注册 `opencode.jsonc`。

**步骤 1**：复制 `integrations/opencode/architecture-quality.md` 到全局 agents 目录：

```bash
# Windows
copy integrations\opencode\architecture-quality.md %USERPROFILE%\.config\opencode\agents\

# Linux/macOS
cp integrations/opencode/architecture-quality.md ~/.config/opencode/agents/
```

**步骤 2**：在 `~/.config/opencode/opencode.jsonc` 注册：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "architecture-quality": {
      "description": "架构质量评估智能体",
      "prompt_file": "~/.config/opencode/agents/architecture-quality.md",
      "mode": "subagent",
      "permission": {
        "read": "allow",
        "bash": { "*": "ask", "arch-quality*": "allow", "python -m arch_quality*": "allow" },
        "edit": "deny",
        "task": "allow",
        "skill": "allow"
      }
    }
  }
}
```

重启 OpenCode 生效。详见 [安装部署指南](docs/zh/安装部署指南.md) 与 [OpenCode 智能体开发指南](docs/zh/OpenCode 智能体开发指南.md)。

## 评估维度与规则

### 标准架构（SAR-001~012）
结构质量 30%（模块化/耦合度/内聚度/复杂度/测试覆盖度 16 子维）+ 设计质量 25% + 文档质量 20% + 演进质量 25%。

### 多语言混合依赖（MLR-001~012）
跨语言调用强度、影响半径、回调深度、绑定层接口一致性、脚本越界访问、跨语言循环依赖。

### 模板元编程与编译时依赖膨胀（TPL / MLR-013~024）
编译时扇入、模板实例化重复率、头文件影响半径、模板嵌套深度、二进制膨胀率、不必要的模板化。

### 数值算法正确性与精度保障（NVR-001~012）
数值稳定性保障、舍入误差与敏感度控制、验证完备性（MMS）、误差估计与控制、数值回归覆盖、数值债务密度。

### 求解器/物理场模块化架构（MPR-001~012）
多物理场耦合架构、求解器模块化、插件扩展机制、跨场数据传输。

> 规则覆盖矩阵（KPI1）：`scripts/gen_rule_coverage_matrix.py --check` 校验 60/60 = 100% 覆盖。

## 报告存储

| 模式 | 路径 | 适用 |
|------|------|------|
| local | 项目本地（按项目配置） | 单项目 |
| central（默认） | `~/.config/opencode/arch-reports/<project-slug>/YYYY-MM-DD/` | 多项目集中 |

## 测试与 CI

- **单元测试**：`python -m pytest tests/`（426 用例）
- **回归快照**：`tests/regression/`，基线存于 `tests/regression/snapshots/`（自举 + 5 个外部项目）
- **三方一致性**：`scripts/consistency_check_standard.py`（指南 ↔ Skill ↔ 工具 版本/权重/命名/SAR 规则）
- **规则覆盖矩阵**：`scripts/gen_rule_coverage_matrix.py --check`
- **性能基线**：`scripts/benchmark_h1_baseline.py`（KPI2：FreeCAD src 全量 < 10 min）

### CI 门禁

- 本地：`scripts/ci_gate_roadmap.bat [--quick] [--project ROOT]`，5 项门禁（单元/一致性/覆盖矩阵/快照/性能），全过 exit 0
- GitHub Actions：`.github/workflows/arch-quality-ci.yml` — 单元矩阵（py3.10/3.11/3.12）+ 门禁 job + 性能基线 job
- 项目清单：`projects.yaml`（18 个回归项目，可复现获取与校验）
- 治理准则：`docs/zh/计划/门禁治理准则.md`

## 项目结构

```
arch-quality/
├── src/arch_quality/
│   ├── arch_core.py                  # 文件索引、依赖图、Git 历史（共享）
│   ├── arch_metrics_standard.py      # 标准 4 维 + SAR-012
│   ├── arch_metrics_multilang.py     # 多语言 6 维 + MLR-001~012
│   ├── arch_metrics_template.py      # 模板元编程 6 维 + TPL（MLR-013~024）
│   ├── arch_metrics_numerical_accuracy.py  # 数值精度 6 维 + NVR-012
│   ├── arch_metrics_solver_physics.py      # 求解器/物理场 4 维 + MPR-012
│   ├── arch_report.py                # 综合报告（合并 5 引擎）
│   ├── arch_report_generator.py      # Markdown 报告模板
│   ├── arch_bindings_parser.py       # pybind11 绑定解析
│   ├── arch_python_ast.py            # Python AST 调用提取
│   ├── arch_multilang_matcher.py     # 跨语言边构建
│   └── skills/                       # 权重/维度定义（运行时解析）
│       ├── arch-quality.md
│       ├── multilang-dependency.md
│       ├── numerical-accuracy.md
│       ├── template-metaprogramming.md
│       └── solver-physics-architecture.md
├── tests/                            # 单元 + 回归（snapshots/）
├── scripts/                          # 一致性检查 / 覆盖矩阵 / 性能基线 / CI 门禁
├── docs/zh/                          # 中文指南与验证案例库
├── integrations/opencode/            # OpenCode 智能体定义
├── .github/workflows/               # CI
└── projects.yaml                     # 回归项目清单
```

## 文档

| 文档 | 说明 |
|------|------|
| [安装部署指南](docs/zh/安装部署指南.md) | 安装、PATH、故障排除 |
| [架构质量标准指南](docs/zh/架构质量标准指南.md) | 标准 4 维评分标准与算法 |
| [多语言混合依赖评估指南](docs/zh/多语言混合依赖评估指南.md) | 6 维 + MLR-001~012 |
| [多语言混合依赖验证案例库](docs/zh/多语言混合依赖验证案例库.md) | 测试场景 |
| [数值算法正确性与精度保障评估指南](docs/zh/数值算法正确性与精度保障评估指南.md) | 6 维 + NVR-001~012 |
| [数值算法正确性与精度保障评估验证案例集](docs/zh/数值算法正确性与精度保障评估验证案例集.md) | 数值验证场景 |
| [模板元编程与编译时依赖膨胀评估指南](docs/zh/模板元编程与编译时依赖膨胀评估指南.md) | 6 维 + TPL |
| [模板元编程与编译时依赖膨胀验证案例库](docs/zh/模板元编程与编译时依赖膨胀验证案例库.md) | 模板验证场景 |
| [求解器和物理场模块化架构模式识别评估指南](docs/zh/求解器和物理场模块化架构模式识别评估/求解器与物理场模块化架构模式识别评估指南.md) | MPR-001~012 |
| [OpenCode 智能体开发指南](docs/zh/OpenCode 智能体开发指南.md) | 智能体集成 |
| [门禁治理准则](docs/zh/计划/门禁治理准则.md) | CI 升级/回滚/豁免 |

## 许可证

MIT License
