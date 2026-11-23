# H3 WP-5 运行时检测报告（阶段 0/2）

> **版本**：0.1
> **日期**：2026-11-17
> **关联**：`H3-WP5语义级检测补齐方案.md` B2/B3/B5

## 1. 阶段 0：G0 底座 CI 实测

| 项 | 结果 |
|:--|:--|
| 触发 | `gh workflow run "Architecture Quality CI" --ref doc-pr/xxx` |
| Run ID | `44491233807` |
| job | `Runtime Kernel (OCCT V8.0.1)` |
| 结果 | ❌ 首次失败（Build OCCT V8.0.1，3m25s） |
| 根因 | `Aspect_DisplayConnection.cxx:20: fatal error: X11/Xlib.h: No such file or directory` |
| 修复 | `scripts/ci/build_occt.sh` 在 apt runner 安装 `libx11-dev libxext-dev` |
| 状态 | **本地修复完成，待提交后复跑 CI** |

> 同一 workflow 的 unit/gate job 失败原因为 CI 环境缺 `pyyaml`/`flask`/`.opencode`（非本 WP 范围，另行登记）。

## 2. B2/B3/B5 运行时脚本落地

| 文件 | 内容 |
|:--|:--|
| `scripts/ci/runtime_checks.cpp` | 输出 JSON：Euler V−E+F、B-Rep 闭合性/valid、api_compat=SKIPPED |
| `scripts/aggregate_runtime_checks.py` | 非阻塞汇总，WARN 明细输出 |
| `scripts/ci/run_kernel_smoke.sh` | 编译并运行 `runtime_checks.cpp`，生成 `runtime_checks.json` 后调用汇总脚本 |

## 3. 当前判定

- B2/B3：脚本已就绪，**待 CI 复跑取得 JSON 证据**；
- B5：当前探针输出 `api_compat=SKIPPED`，理由“跨版本构建需两套 OCCT 安装”；符合 D4 非阻塞口径；
- 若 CI 复跑仍失败，按 D4 回退：静态子集 + KNOWN_HOLES 文档化，升 H3 计划 v2.1。

## 4. 下一步

1. 提交本轮 WP-5 改动并推送；
2. 再次触发 `workflow_dispatch`；
3. 将成功日志/JSON 回填本报告；
4. 若失败，执行 D4 回退。
