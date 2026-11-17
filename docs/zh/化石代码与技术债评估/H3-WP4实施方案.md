# H3 WP-4 实施方案（维度⑦ 化石代码与技术债）

> **版本**：0.1（方案，待阶段 A 定案）
> **日期**：2026-11-05
> **归属**：H3 全维化 — WP-4（维度⑦）
> **依据**：`H3全维化执行计划v2.md` §三 WP-4；`维度完备性证明与边界裁决.md` §3.4/§五
> **状态**：方案稿；先做阶段 A（设计依据），再进入 B/C

---

## 一、目标与验收

在现有 8 引擎/11 维/96 规则基础上，新增 **维度⑦ 化石代码与技术债**：

| 项 | 目标 |
|:--|:--|
| 子维 | 4 个 |
| 规则 | **FOS-001~012**（12 条）|
| 引擎 | `arch_metrics_fossil_code.py`（`FossilCodeMetrics`）|
| 权重源 | `skills/fossil-code-debt.md` |
| 注册表 | 9 引擎 / 12 维 / **108 规则**；schema 1.5 |
| 覆盖 | 矩阵 **108/108** |
| 回归 | ≥5 项目基线 |
| 三方一致 | `consistency_check --engine fossil` PASS |
| Harness | 1 good + 1 flawed + 1 non-fossil |

**验收口径**：与 WP-3 相同——12 条规则各 ≥1 用例；回归 ≥5；三方一致 PASS；文档包齐备。

---

## 二、与现有维度的边界（P0，必须先定）

依据 `维度完备性证明与边界裁决.md §3.4`：

> ⑦ 与标准结构维度·演进质量：演进质量管"历史趋势/债务曲线"，⑦ 管"特定历史遗留形态检测"（F77 变体、`auto_ptr`、废弃 API）；**同一文件同一形态只由 ⑦ 计分**，演进质量仅统计趋势不重复扣分。

### 2.1 需要裁决的 3 个重叠点

| # | 重叠 | 现行演进/标准维度 | ⑦ 候选规则 | 建议裁决 |
|:-:|:--|:--|:--|:--|
| D1 | 注释代码/备份文件 | 演进 `废弃代码比例`（backup + commented blocks）| FOS-006 大块注释代码 | **FOS-006 只计 >N 行（建议 10）的成块注释代码；演进 `废弃代码比例` 只计备份文件与短注释**，或标准引擎对 FOS-006 命中文件豁免 |
| D2 | 硬编码魔法数/密钥 | 标准 `anti_patterns.hardcode`：**仅 IP/密钥**（`1.2.3.4`/`8.8.8.8`/`password=`/`api_key=`）| FOS-008 重复常量 | **按形态互斥**：标准保留 IP/密钥；FOS-008 只计跨文件数字/字符串常量（≥2 文件、≥3 处），排除 IP/密钥/URL → 无重叠，无需改标准 |
| D3 | 测试覆盖 | 标准 `test_coverage`（整体覆盖率）| FOS-012 遗留模块无测试 | **FOS-012 只计"年龄 > 阈值（建议 5 年）且无任何测试"的遗留模块**；整体覆盖率仍归标准 |

> D1~D3 需在阶段 A 与标准/演进维度负责人确认，并写入边界矩阵；未定前不实现 FOS-006/008/012 的计分。

### 2.2 边界原则

- ⑦ 是**形态检测**（静态、点状），演进是**趋势统计**（时间序列）；
- 同一文件同一形态**只由 ⑦ 计分**；
- 共享文件按"主关切"归属，扣分后对方豁免；
- 生成文件/third_party 全维度过滤。

---

## 三、评估模型

### 3.1 4 子维（建议权重，阶段 A 定案）

| 子维 | 权重 | 说明 |
|:--|:--:|:--|
| 历史遗留 API 与语言方言 | 30% | F77、`auto_ptr`/废弃 API、非标准方言 |
| 死代码与不可达逻辑 | 20% | 未引用符号、不可达分支、大块注释代码 |
| 重复代码与重复实现 | 20% | 克隆、重复常量、同一算法多份 |
| 技术债密度与可维护性 | 30% | TODO/FIXME 密度、SQALE 修复成本、遗留模块无测试 |

### 3.2 12 条规则（建议赋分）

| 规则 | 名称 | 子维 | severity | output_level | 赋分 | 置信度 |
|:--|:--|:--|:--:|:--:|:--:|:--:|
| FOS-001 | F77 固定格式/隐式类型/COMMON | 历史遗留 | HIGH | WARNING | 40 | 高 |
| FOS-002 | 废弃 C++ API（auto_ptr/register/throw()/strstream）| 历史遗留 | MEDIUM | WARNING | 40 | 高 |
| FOS-003 | 非标准/废弃语言方言（K&R C/GNU 扩展）| 历史遗留 | MEDIUM | WARNING | 20 | 中 |
| FOS-004 | 未引用函数/变量/文件（dead symbols）| 死代码 | MEDIUM | WARNING | 50 | 中低 |
| FOS-005 | 不可达分支（#if 0/return 后/恒假）| 死代码 | MEDIUM | WARNING | 30 | 中 |
| FOS-006 | 大块注释掉的代码 | 死代码 | LOW | INFO | 20 | 中低 |
| FOS-007 | 复制粘贴克隆（函数/文件级）| 重复 | MEDIUM | WARNING | 50 | 中低 |
| FOS-008 | 重复常量/魔法数（跨文件）| 重复 | LOW | INFO | 20 | 中低 |
| FOS-009 | 同一算法多份实现 | 重复 | MEDIUM | WARNING | 30 | 中低 |
| FOS-010 | 债务标记密度（TODO/FIXME/HACK/KLOC）| 技术债 | LOW | INFO | 25 | 中 |
| FOS-011 | 修复成本比率（SQALE）| 技术债 | MEDIUM | WARNING | 50 | 中低 |
| FOS-012 | 遗留模块无测试/长期未维护 | 技术债 | MEDIUM | WARNING | 25 | 中低 |

- 子维得分 = 100 − Σ(触发规则赋分)；
- overall = Σ(子维得分 × 权重)；
- 候选/确认：FOS-001/002 可直接 confirmed（高置信）；其余 candidate，经 LLM/人工复核。

### 3.3 适用性

`is_fossil=True` 条件（任一）：
- 存在 F77/固定格式 Fortran、`auto_ptr`/废弃 API、K&R C；
- 存在死代码/大块注释代码；
- 存在跨文件重复常量/克隆；
- 存在 TODO/FIXME 密度超阈值。

无化石信号 → `is_fossil=False`，维度不适用（不打分）。

### 3.4 门禁与封顶

- confirmed ERROR/HIGH → `gate=WARN/BLOCK`；
- 已确认 HIGH → ⑦ 维度子分等级封顶"需改进"，不回写总分；
- INFO 规则不触发门禁。

### 3.5 豁免体系（建议）

| 注解 | 作用 |
|:--|:--|
| `@fossil_legacy_ok` | 保留遗留 API（如 ABI 兼容）|
| `@fossil_deferred` | 已知债务，降一级 |
| `@fossil_not_dead` | 反射/FFI/插件动态引用，避免死代码误报 |

- reason 必填；合计 >30% → `abuse_warning`。

### 3.6 KNOWN_HOLES

- **FOS-013**：跨语言死代码（Fortran/C 符号映射）——静态难判；
- **FOS-014**：语义级重复（不同写法同一算法）——需 AST/语义。

---

## 四、检测信号（静态）

| 子维 | 信号 | 说明 |
|:--|:--|:--|
| 历史遗留 | `.f/.f77/.for`、固定格式列、`COMMON`/`IMPLICIT`/`EQUIVALENCE`、`auto_ptr`、`register`、`throw()`、`strstream`、`bind1st`、K&R 函数定义 | 正则 + 扩展名 |
| 死代码 | 无引用符号（ctags/引用图）、`#if 0`、`return` 后语句、`if (false)`、连续 `//` 块 >10 行 | 符号表 + 轻量调用图 |
| 重复 | 函数/文件 token 哈希（winnowing/SimHash）、重复常量表、同名算法多实现 | token 化 + 哈希 |
| 技术债 | `TODO/FIXME/HACK/XXX` 计数、SQALE 修复成本代理、模块年龄 + 无测试 | 计数 + 代理模型 |

**过滤**：third_party/generated/build/examples/tests（按规则需要）；大仓库分片/采样，避免 O(n²)。

---

## 五、集成点

| 文件 | 改动 |
|:--|:--|
| `skills/fossil-code-debt.md` | 新建（4 子维权重 30/20/20/30）|
| `src/arch_quality/arch_metrics_fossil_code.py` | 新建 `FossilCodeMetrics` |
| `meta_model_registry.json` | engines 加 `fossil`；`dim.fossil`（0.15、project、4 sub_dims）；FOS-001~012；schema 1.5 |
| `standard_meta_model.schema.json` | rule pattern 加 `FOS` |
| `scripts/validate_meta_model.py` | `RULE_ID_RE` 加 `FOS` |
| `arch_core.py` | `PROFILE_ENGINE_MAP["fossil"]`、`ENHANCEMENT_ENGINES`、`ENH_KEY_TO_DIM["fos"]` |
| `arch_report.py` | 实例化/激活/合并、FOS violations |
| `arch_report_generator.py` | 维度标签、章节、封顶展示 |
| `scripts/consistency_check.py` | `ENGINES["fossil"]` |
| `benchmark_h1_engines.py` / `h3_baseline.py` / `weight_sensitivity.py` | 引擎 9 |
| `gen_rule_coverage_matrix.py` | 96→108 |
| `opencode-harness/rules.json` | fossil 维度字段/断言 |
| `projects.yaml` | BRL-CAD/Code_Aster/OpenFOAM 遗留 API |
| `scripts/ci_gate_fossil.bat` | CI 门禁（单元/回归/一致性/可选 harness）|

---

## 六、测试方案

| 类型 | 内容 |
|:--|:--|
| 单元 | `tests/test_fossil_code.py`：12 规则正/负、适用性、豁免、门禁、封顶 |
| 变异 | `tests/mutation/test_fossil_mutation.py`：≥4（遗留 API、死符号、克隆、债务）|
| 集成/E2E | `ComprehensiveReport` 合并 + 归一化 + 报告生成 |
| 回归 | `tests/regression/test_fossil_regression.py` + ≥5 基线 |
| 开源验证 | B3.5：BRL-CAD / Code_Aster / OpenFOAM 遗留 API |
| 交叉验证 | B3.7（可后置到 WP-8）：9 样本 LOOCV ≥7/9 |
| Harness | good / flawed / non-fossil 三例 |

**样本**：BRL-CAD（F77/C 混编）、Code_Aster（Fortran）、OpenFOAM 遗留 API；合成正/负例。

---

## 七、阶段与排期（6 周）

| 阶段 | 周 | 交付 |
|:--|:--:|:--|
| **A 设计依据** | W1–W2 | 设计依据（四层催化/边界/可行性分级）、4 子维/12 规则定义、案例锚点、专家校对 |
| **B 指南+案例集** | W2–W4 | 指南 v0.1、验证案例集 v0.1、两轮专家校对 |
| **C 引擎+集成** | W4–W6 | skill + `arch_metrics_fossil_code.py` + 12 规则 + 测试 + 回归 + CI + registry/report 集成 |
| **校准** | W6 | B3.5 A 类、规则赋分、误报率、覆盖矩阵 108/108 |

---

## 八、风险与开放问题

| 风险 | 缓解 |
|:--|:--|
| D1~D3 与演进/标准重复计分 | 阶段 A 先定边界矩阵；未定不实现计分 |
| Fortran 解析能力 | 固定格式正则 + 扩展名；语义级交 KNOWN_HOLES |
| 死代码误报（反射/FFI/插件）| `@fossil_not_dead`、引用图 + 白名单 |
| 克隆检测 O(n²) | token 哈希/winnowing + 分片 |
| SQALE 无真实修复成本 | 代理模型 + 置信度中低 + 阶段 4 校准 |
| 跨语言符号 | FOS-013 KNOWN_HOLES |
| 大仓库性能 | 采样/缓存/排除目录 |
| 既有基线不受影响 | 新维度独立；不改标准/演进分数（除 D1~D3 裁决）|

---

## 九、验收清单

- [ ] 4 子维 + 12 规则，每条 ≥1 用例
- [ ] FOS-001~012 三方一致（指南/Skill/工具）
- [ ] 9 引擎 / 12 维 / 108 规则；validator PASS
- [ ] 覆盖矩阵 108/108
- [ ] 回归 ≥5 基线（含 BRL-CAD/Code_Aster/OpenFOAM）
- [ ] Harness 三例
- [ ] CI gate PASS
- [ ] 边界矩阵 D1~D3 定案并记录

---

## 十、首个动作

**阶段 A**：编写
`docs/zh/化石代码与技术债评估/化石代码与技术债评估设计依据.md`
（必要性/定义/工程作用/设计逻辑四层 + 12 规则 + 可行性分级 + D1~D3 边界），然后专家校对。

---

## 版本历史

| 版本 | 日期 | 变更 |
|:--|:--|:--|
| 0.1 | 2026-11-05 | 首版：目标/验收、边界 D1~D3、4 子维/12 规则、检测信号、集成/测试/排期/风险 |
