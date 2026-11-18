---
pr_type: tooling
kb_version: 0.3
guide_version: 0.3
evidence:
  - EV-TEST-2026-11-17-fossil
  - EV-REAL-2026-11-17
  - EV-EXPERT-2026-11-05-01
  - EV-SAMPLE-2026-11-17
changes:
  files:
    - src/arch_quality/arch_metrics_fossil_code.py
    - src/arch_quality/skills/fossil-code-debt.md
    - .opencode/skills/fossil-code-debt/SKILL.md
    - meta_model_registry.json
    - standard_meta_model.schema.json
    - src/arch_quality/arch_core.py
    - src/arch_quality/arch_report.py
    - src/arch_quality/arch_report_generator.py
    - src/arch_quality/arch_metrics_standard.py
    - src/arch_quality/ui/commands_meta.py
    - scripts/consistency_check.py
    - scripts/validate_meta_model.py
    - scripts/gen_rule_coverage_matrix.py
    - scripts/benchmark_h1_engines.py
    - scripts/ci_gate_fossil.bat
    - scripts/doc_lint.py
    - scripts/run_doc_pr.py
    - tests/test_fossil_code.py
    - tests/test_fossil_integration.py
    - tests/mutation/test_fossil_mutation.py
    - tests/regression/test_fossil_regression.py
    - tests/regression/test_fossil_real_regression.py
    - docs/zh/化石代码与技术债评估/阶段C-FOS007009抽样.md
    - docs/zh/化石代码与技术债评估/化石代码与技术债评估指南.md
    - docs/zh/化石代码与技术债评估/化石代码与技术债评估设计依据.md
    - docs/zh/化石代码与技术债评估/化石代码与技术债评估验证案例集.md
  rules_added: ["FOS-001~012"]
  rules_removed: []
  weights_changed: []
  thresholds_changed:
    - {rule: FOS-001, change: "固定格式本身触发"}
    - {rule: FOS-006, change: "代码行≥50%；>10 行 WARNING"}
    - {rule: FOS-007, change: "min 40 token / max 200 pairs / 排除入口"}
    - {rule: FOS-009, change: "同名+签名 / max 200 pairs / 索引对齐"}
    - {rule: FOS-011, change: "KLOC=max(实际,1.0)"}
  severity_changed: []
human_decisions:
  - HD-2026-11-17-01
review:
  reviewer_model: opencode-go/deepseek-v4.1-flash
  verdict: approved
  p0: 0
  iterations: 1
index_rebuild: [fossil]
---

# 化石代码 Stage C：引擎、真实基线与校准

## 1. 变更意图

把维度⑦ 化石代码从设计依据/指南/案例集推进到可运行引擎：4 子维、FOS-001~012、注册表 1.5（9 引擎/12 维/108 规则）、D1/D3 边界、5 合成 + 3 真实基线、CI 与 Harness。

## 2. 证据

| 证据 ID | 类型 | 位置 | 摘要 |
|---|---|---|---|
| EV-TEST-2026-11-17-fossil | 测试 | 三文件定向：`tests/test_fossil_code.py` 20 + `test_fossil_integration.py` 6 + `mutation/test_fossil_mutation.py` 1（6 subTest）= 27 passed；全量关键批次 161 passed / 1 skipped |
| EV-REAL-2026-11-17 | 真实基线 | `tests/regression/snapshots/fossil_*.json` | Code_Aster/BRL-CAD/OpenFOAM 3 passed |
| EV-EXPERT-2026-11-05-01 | 专家校对 | `设计依据专家校对报告_定向确认.md` | P1×5 / P2×8 闭环 |
| EV-SAMPLE-2026-11-17 | 抽样 | `阶段C-FOS007009抽样.md` | FOS-007/009 实际 pair 清单 |

## 3. 影响面

- 规则：FOS-001~012；FOS-013/014 仍为 KNOWN_HOLES。
- 权重：不变（30/20/20/30）；severity：不变。
- 阈值：见 front-matter；需 `HD-2026-11-17-01`。
- D1：标准 `calc_dead_code` 注释归 FOS-006。
- D3：标准 `test_coverage` 剔除 `legacy_untested_modules`；无源码 → N/A。
- 工具链：`doc_lint.py` 支持 fossil 维度、中低置信词表、复合 output_level（INFO/WARNING）。

## 4. 自检

- [x] `python scripts/doc_lint.py --dimension fossil` → 0 error / 1 warning（FOS-001 首期映射）
- [x] `python scripts/consistency_check.py --engine fossil` → PASS
- [x] `python scripts/validate_meta_model.py` → PASS
- [x] `python scripts/gen_rule_coverage_matrix.py --check` → 108/108
- [x] `python -m pytest -q ...` → 161 passed
- [x] `RUN_FOSSIL_REAL=1` → 3 passed
- [x] Harness case-10/11/12 → PASS

## 5. Reviewer 结论（Reviewer 填写）

实际 Reviewer 输出见 `.doc-pr/PR-FOSSIL-STAGE-C/review_1.json`。
首轮：`changes_requested`，P0=0 / P1=2 / P2=5；本文件已按意见修订。

## 6. 人工决策

| 决策编号 | 决策人 | 日期 | 结论 |
|---|---|---|---|
| HD-2026-11-17-01 | 用户 | 2026-11-17 | 批准（阈值校准） |

---

*本 PR 为 Stage C 文档/工具链收口；HD-2026-11-17-01 已批准，进入 Reviewer 复评。*
