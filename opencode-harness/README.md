# opencode-harness — architecture-quality 智能体验证基架

用 opencode 官方能力为 `architecture-quality` 智能体搭建的生产级验证基架。核心公式：

```
Agent = Model + [上下文 + 工具 + 约束 + 验证 + 纠正]
                  └───────── Harness ─────────┘
```

本 harness 落实其中 **约束**（opencode permissions）、**验证**（断言器）、**纠正**（超时重试）三层。

## 与现有测试的关系

| 测试 | 验证对象 | 技术 |
|:-----|:---------|:-----|
| `tests/test_solver_physics.py` 等（92+28+6）| **Python 工具**（评分算法正确性）| pytest |
| **本 harness** | **agent 行为**（LLM 编排工具是否正确）| opencode run + 断言 |

两者互补：pytest 保证工具算得对，harness 保证 agent 用得好。

## 架构

```
opencode-harness/
  harness_runner.py          # 主 runner：子进程调 opencode run，解析事件流，跑断言，重试
  assertors/
    tool_usage.py            # 工具选择/越权/doom_loop 断言
    output_schema.py         # 输出结构/幻觉/overall 断言
    score_sanity.py          # 评分区间/权重和断言
  cases/                     # 测试用例（JSON）
  reports/                   # 每次运行结果（JSON）
scripts/run_agent_harness.py # CLI 入口
```

## 依赖

- `opencode` CLI（`opencode run --agent architecture-quality --format json`）
- LLM provider 已配置（opencode 认证）
- `architecture-quality` agent 注册为 `mode: primary`（已配好，见全局 `~/.config/opencode/opencode.jsonc`）

## 用法

```powershell
# 运行全部用例
python scripts\run_agent_harness.py

# 单用例
python scripts\run_agent_harness.py --case case-1-multiphysics

# 自定义超时（秒）
python scripts\run_agent_harness.py --timeout 600

# 显示 agent 输出
python scripts\run_agent_harness.py --verbose
```

## 用例

| 用例 | 目标项目 | 期望 |
|:-----|:---------|:-----|
| case-1-multiphysics | `tests/mutation/projects/good_multiphysics` | is_mp=True, overall∈[60,95] |
| case-2-single-solver | `tests/mutation/projects/good_project` | is_mp=False |
| case-3-pure-markdown | `D:/opensource/knowledge-base` | is_mp=False |

## 约束层（opencode.json 中已生效）

`architecture-quality` agent 权限：
- `bash`: `*`=ask，仅 `arch-quality*`/`python -m arch_quality*` allow
- `edit`/`write`: deny（评估只读）
- `read`/`glob`/`grep`/`skill`/`task`: allow

LLM 不可感知这些规则，由 opencode 强制——非交互 harness 中未授权命令自动拒绝。

## 验证的脆弱点

| 脆弱点 | 断言器 | 观察到的行为 |
|:-------|:-------|:------------|
| 幻觉（编造工具/参数）| tool_usage.assert_tool_choice | 命令需命中白名单 |
| 选错工具 | tool_usage.assert_tool_choice | agent 先 skill→glob/read→bash 评估 |
| 越权（写操作）| tool_usage.assert_no_forbidden_write | edit/write deny |
| 无法自愈（死循环）| tool_usage.assert_no_doom_loop | 相同调用≥3 次报警 |
| 输出缺字段 | output_schema.assert_report_structure | 维度字段存在性 |
| 评分越界 | score_sanity.assert_score_ranges | ∈[0,100] |

## 已知限制

- 每次运行消耗 LLM token（约 1-5 分钟/用例）
- `--json` 模式下 CLI 的 JSON 输出可能混入报告进度日志（`arch_report.py` 已知），harness 从事件流的 text 部分提取而非直接解析 stdout
- case-2 验证中发现并修复了 `arch_report.py` 缺 `ReportGenerator` 导入的 bug

## 纠正层

超时（默认 600s）后自动重试，最多 `expect.max_retries` 次（默认 2）。每次尝试独立会话。
