# H3 WP-5 语义级检测补齐报告

> **版本**：1.0（收口）
> **日期**：2026-11-24
> **关联**：`H3-WP5语义级检测补齐方案.md`、`H3-WP5运行时检测报告.md`
> **结论**：按 D1~D5 口径收口通过；B1/B4 以 candidate 交付，B5 按 D4 标记 SKIPPED，残余增强已列明。

## 1. 结论摘要

| 项 | 状态 | 交付/证据 |
|:--|:--|:--|
| B1 跨 TU 实例化 | ✅ candidate 收口 | compile DB 解析 + TU/编译参数 + 跨 TU 模板使用候选；不进入评分 |
| B2 Euler 运行时 | ✅ PASS | CI `euler=PASS`（8/12/6→2） |
| B3 B-Rep 闭合运行时 | ✅ PASS | CI `closure=PASS`；`BRepCheck_Analyzer` |
| B4 跨函数/builder 委托 | ✅ candidate 收口 | `gcs_candidates` 独立通道 + `file:line`；不改变 GCS-003 违规计数 |
| B5 ACL 跨版本兼容 | ⚠️ SKIPPED | D4：单 OCCT 安装；`api_compat=SKIPPED` + 理由 |
| B6 NVR-009/MPR-011 | ✅ 实现并修复死代码 | NVR-009 INFO；MPR-011 candidate WARNING；已移出 KNOWN_HOLES |
| B7 GCS-013/014、ACL-013 | ✅ 裁决完成 | 保持 KNOWN_HOLES；`known_holes_audit` 文档化“静态不可判” |

## 2. 逐项交付

### B1 跨 TU 实例化（candidate）

实现：

- 读取 `compile_commands.json`；
- 解析 `arguments` / `command`，提取 `-I`、`-D` 与真实 TU；
- 按 `file` 去重 TU；
- 提取项目内模板名，检测模板在多个 TU 中的使用；
- 有显式实例化或 `extern template` 时抑制；
- 无足够证据时只输出 `TPL-006` candidate，不改变模板评分。

测试：

- `TestB1CompileDB.test_b1_cross_tu_template_candidate`
- `TestB1CompileDB.test_b1_silent_with_extern_template`

边界：尚未接入 clang AST；跨头文件实例化仍可能漏检，保留 candidate 口径。

### B2/B3 运行时内核

CI run `45102267162`：

```text
OCCT 8.0.1: euler=PASS closure=PASS api_compat=SKIPPED
```

- Euler：去重后 8 顶点 / 12 边 / 6 面，`8-12+6=2`；
- Closure：`BRepCheck_Analyzer.IsValid()=true`，faces=6；
- 冷构建约 33 min，缓存命中后约 11 s。

### B4 跨函数/builder 委托（candidate）

实现：

- 识别 `BRepFeat/BRepFill/CheckAndLoad/Perform/Build/Make*`；
- 文件内无 `IsDone()/IsValid()` 时生成 candidate；
- 输出 `locations`（`file:line`）；
- 结果进入独立 `gcs_candidates`，不进入 `gcs_violations`，避免改变基线计数。

测试：

- `TestB4BuilderDelegate.test_b4_candidate_when_builder_without_status_check`
- `TestB4BuilderDelegate.test_b4_silent_when_status_check_present`

边界：当前为文件级，不是完整函数调用图；跨函数路径仍由后续 AST/调用图增强。

### B5 ACL 跨版本兼容

按 D4 收口：

```json
{"check":"api_compat","status":"SKIPPED",
 "reason":"cross-version build comparison requires two OCCT installs"}
```

不伪造双版本结果；待建立 baseline/target 两套 OCCT 缓存后启用。

### B6 NVR-009 / MPR-011

修复内容：

- NVR-009 从 `return results` 之后移到返回前；
- MPR-011 从 `return results` 之后移到返回前；
- MPR-011 改为“不同物理场种类”计数，避免同一词重复触发。

规则口径：

| 规则 | 级别 | 评分 | 触发 |
|:--|:--|:--|:--|
| NVR-009 确认绝热等级 | LOW / INFO | 不评分 | 时间步信号 + 无热模型信号 |
| MPR-011 跨场时域同步 | MEDIUM / WARNING | candidate | ≥2 物理场 + 无同步/preCICE 信号 |

测试：

- `TestNVR009`（正向/反向）
- `TestMPR011`（正向/反向）

### B7 KNOWN_HOLES 裁决

- `GCS-013/014`、`ACL-013` 保持 KNOWN_HOLES；
- 报告输出 `known_holes_audit`；
- 不新增编号，覆盖率保持 108/108；
- 理由：静态不可判，需运行时/人工裁决。

## 3. 验证证据

| 验证 | 结果 |
|:--|:--|
| WP-5 定向单测 | **166 passed** |
| 模板回归 | **84 passed** |
| 几何 GCS 回归 | **12 passed** |
| 求解器/物理场回归（非 slow） | **28 passed, 3 skipped** |
| 数值回归（MFEM + FEniCSx） | **22 passed** |
| `validate_meta_model.py` | PASS |
| `consistency_check --engine all` | PASS |
| 覆盖率矩阵 | **108/108** |
| runtime-kernel CI | `45102267162` success |

说明：MOOSE/deal.II/FreeFEM 数值回归未在本轮跑完（单项目耗时较长）；MFEM/FEniCSx 已覆盖 B6 新增规则影响。

## 4. KPI3 对照

| KPI3 要求 | 结果 |
|:--|:--|
| 静态项 B6 清零 | ✅ NVR-009/MPR-011 实现并移出 KNOWN_HOLES |
| B2/B3/B5 运行时实施 | ✅ B2/B3 通过；B5 按 D4 SKIPPED |
| B7 保持 KNOWN_HOLES 并文档化 | ✅ |
| B1/B4 假阳性不劣化 | ✅ B1/B4 仅 candidate；GCS 回归 12/12、模板回归 84/84 |

## 5. 残余项

1. **B1**：接入 clang AST，补头文件闭包与特化级跨 TU 追踪；
2. **B4**：从文件级升级为函数级调用图，补跨函数路径与逐点去重；
3. **B5**：建立两套 OCCT 缓存，启用真实编译/链接/运行对比；
4. **CI**：unit/perf job 仍受 `pyyaml`/`flask`/`.opencode` 环境影响，另行修复。

---

*WP-5 按当前决策口径收口；上述残余项为增强项，不阻塞 WP-5 验收。*
