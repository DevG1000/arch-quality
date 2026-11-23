# H3 WP-5 运行时检测报告（阶段 0/2）

> **版本**：0.2
> **日期**：2026-11-23
> **关联**：`H3-WP5语义级检测补齐方案.md` B2/B3/B5

## 1. 阶段 0：G0 底座 CI 实测

| 项 | 结果 |
|:--|:--|
| 触发 | `gh workflow run "Architecture Quality CI" --ref doc-pr/xxx` |
| 最终 Run ID | `45101707990` |
| job | `Runtime Kernel (OCCT V8.0.1)` |
| 结果 | ✅ **success**（OCCT 构建 + smoke probe 全部通过） |
| OCCT | V8.0.1，缓存 key `occt-v8.0.1-Linux-2dd4...` |
| 运行时结果 | `euler=PASS closure=PASS api_compat=SKIPPED` |

### 修复链

| Run | 失败点 | 修复 |
|:--|:--|:--|
| `44491233807` | `X11/Xlib.h` 缺失 | workflow 增加 `libx11-dev libxext-dev` 安装（不 apt 安装 OCCT） |
| `45093710334` | smoke 链接缺 `TKGeomBase/TKGeomAlgo` 等 | `run_kernel_smoke.sh` 补齐 OCCT 几何库 |
| `45098217279` | Euler 探针重复计数（48/24/6→30）、shell BOM | 改用索引映射去重；去除 `.sh` BOM |
| `45101707990` | — | `euler=PASS`（8/12/6→2）、closure PASS |

> 同一 workflow 的 unit/perf job 失败为既有 CI 环境/依赖问题（缺 `pyyaml`/`flask`/`.opencode` 等），非本 WP 范围。

## 2. B2/B3/B5 运行时脚本落地

| 文件 | 内容 |
|:--|:--|
| `scripts/ci/runtime_checks.cpp` | 输出 JSON：Euler V−E+F、B-Rep 闭合性/valid、api_compat=SKIPPED |
| `scripts/aggregate_runtime_checks.py` | 非阻塞汇总，WARN 明细输出 |
| `scripts/ci/run_kernel_smoke.sh` | 编译并运行 `runtime_checks.cpp`，生成 `runtime_checks.json` 后调用汇总脚本 |

## 3. 当前判定

- **B2 Euler**：CI 实测 `PASS`（去重后 8 顶点/12 边/6 面，Euler=2）；
- **B3 B-Rep 闭合**：CI 实测 `PASS`（`BRepCheck_Analyzer.IsValid()=true`，faces=6）；
- **B5 API 兼容**：`api_compat=SKIPPED`，理由“跨版本构建需两套 OCCT 安装”；符合 D4 非阻塞口径；
- 运行时 job 已具备可复现的 **JSON 证据**，D4 回退条件未触发。

## 4. 下一步

1. B2/B3 结果接入 WP-5 收口报告；
2. B5 保持 SKIPPED，待双版本 OCCT 矩阵建立后再启用；
3. 提交本轮文档与探针修复。
