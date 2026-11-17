# 化石代码与技术债评估 阶段 C 实现与验证报告

> **版本**：0.1（阶段 C 首轮）
> **日期**：2026-11-05
> **对象**：维度⑦ 化石代码与技术债（FOS-001~012）
> **依据**：设计依据 v0.3、指南 v0.2、验证案例集 v0.2、阶段 B 专家校对报告

---

## 一、交付物

| 文件 | 说明 |
|:--|:--|
| `src/arch_quality/skills/fossil-code-debt.md` | Skill：4 子维权重、12 规则、豁免、KNOWN_HOLES |
| `src/arch_quality/arch_metrics_fossil_code.py` | `FossilCodeMetrics`：检测/12 规则/评分/门禁/豁免/CLI |
| `meta_model_registry.json` | schema **1.5**；**9 引擎 / 12 维 / 108 规则** |
| `arch_core.py` / `arch_report.py` / `arch_report_generator.py` | profile、归一化、报告章节与封顶展示 |
| `ui/commands_meta.py` | Web 面板新增“化石代码评估” |
| `scripts/ci_gate_fossil.bat` | CI gate（单测/一致性/回归/覆盖） |
| `opencode-harness/cases/case-10/11/12` | good/flawed/non 三例 |
| `tests/test_fossil_code.py` | 20 单测 |
| `tests/test_fossil_integration.py` | 4 集成 |
| `tests/mutation/test_fossil_mutation.py` | 6 组规则翻转 |
| `tests/regression/test_fossil_regression.py` + 5 快照 | 5 合成基线 + 确定性 |
| `tests/regression/test_fossil_real_regression.py` + 3 快照 | Code_Aster / BRL-CAD / OpenFOAM 真实基线（`RUN_FOSSIL_REAL=1`） |

## 二、验证结果

| 项 | 结果 |
|:--|:--|
| FOS 单测 | **20 passed** |
| FOS 集成 | **4 passed** |
| FOS 变异 | **6 组翻转，1 passed** |
| FOS 合成回归 | **9 passed（5 基线 + 4 确定性）** |
| FOS 真实回归 | **3 passed**（`RUN_FOSSIL_REAL=1`，约 2m21s） |
| profile/meta/ui | **104 passed, 1 skipped** |
| 三方一致 | `consistency_check --engine fossil` **PASS** |
| 注册表 | `validate_meta_model.py` **PASS**（9/12/108） |
| 覆盖矩阵 | **108/108（KPI1 100%）** |
| Harness | **3 passed**（case-10/11/12） |
| CI gate | **PASS**（不含 LLM Harness） |

## 三、真实样本结果

| 样本 | overall | gate | 触发规则 | 耗时 |
|:--|:-:|:--:|:--|:-:|
| Code_Aster | 60.5 | WARN | FOS-001/007/008/009/012 | ~62s |
| BRL-CAD | 30.0 | WARN | FOS-001/002/003/004/005/006/007/008/009 | ~35s |
| OpenFOAM | 54.0 | PASS | FOS-003/004/005/006/007/008/009 | ~54s |

> 真实基线已快照并接入 `RUN_FOSSIL_REAL=1`；校准细节见 `阶段C校准记录.md`。

## 四、D1/D3 边界落地

| 裁决 | 状态 |
|:--|:--|
| **D1** 标准 `calc_dead_code` 只保留备份文件，注释代码归 FOS-006 | **已实现**；`commented_blocks=0`、`delegated_to=FOS-006`；17 standard 单测 PASS |
| **D2** 标准 `hardcode` 只抓 IP/密钥；FOS-008 只抓跨文件常量 | 设计已定；无需改标准 |
| **D3** FOS-012 输出 `legacy_untested_modules`；标准 `test_coverage` 豁免 | **已实现**：剔除分母；无剩余源码 → `test_coverage=N/A`；根目录源码视作 `.`；`excluded_legacy_modules` 留痕 |

## 五、已知限制（P2 残留）

1. FOS-004 仅检测 **static** 函数，全局未引用函数可能漏报（降误报的取舍）。
2. FOS-009 以“同名函数跨文件”近似“同一算法多实现”，可能误报/漏报。
3. FOS-012 以目录名 `legacy/old/deprecated/fossil` + 无测试近似，未接 git 年龄。
4. FOS-011 以 `max(KLOC,1.0)` 计算，极小项目不触发；阈值 8h/KLOC 待校准。
5. FOS-007 克隆相似度 0.80、FOS-010 5/KLOC、FOS-012 5 年均为候选阈值。
6. FOS-007/009 在大型项目中触发较多（OpenFOAM FOS-007 462、FOS-009 200 上限），需抽样复核。

## 六、下一步

1. 对 FOS-007/009 抽样评估误报率；
2. 阶段 C 复核 + 版本收口。

---

*本报告为阶段 C 首轮；P2 项在阶段 C 收尾/校准中处理。*
