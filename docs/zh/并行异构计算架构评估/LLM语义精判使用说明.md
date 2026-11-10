# HPC 候选规则 LLM 语义精判（可选层，§7.7）

> **版本**：1.0 ｜ **日期**：2026-11-05
> **脚本**：`scripts/llm_refine_hpc.py`
> **定位**：正则/静态分析产出 candidate；LLM 只做候选级语义复核。

---

## 一、为什么需要

正则/静态分析能发现"模式"，但无法判断语义，例如：

- `MPI_Isend` 后是否真的缺 `Wait`（跨函数/RAII/异步）？
- `omp parallel` 内调 MPI 是否真的非线程安全？
- 无权重分区是否真的对应非均匀负载？

这些需要结合代码上下文做**语义判断**。LLM 适合做这一层；但必须受约束。

---

## 二、约束（重要）

| 约束 | 说明 |
|:--|:--|
| 只判风险 | LLM 只判"语义风险是否成立"，**不判实测事实**（失衡/扩展曲线交 TAU/人工）|
| 不改评分 | `overall`、`dimensions`、`hpc_violations[].count` 不变 |
| 不改门禁 | `gate_status`、`confirmed`、等级封顶不变 |
| 不自动 BLOCK | LLM 的 confirm 仅为候选级证据，最终由 MUST/TAU/人工裁定 |
| 证据锚定 | 输出必须含 `file:line + 理由`；缺失证据 → `uncertain` |
| 温度 0 | OpenAI 后端 `temperature=0` |
| 版本固定 | `llm_model`、`llm_prompt_version` 写入结果 |
| 缓存 | 按 `(rule,file,line,snippet,model,prompt)` 缓存，避免重复调用 |
| 离线可选 | CI 默认不联网；`mock` 后端可冒烟 |

---

## 三、后端

| 后端 | 条件 | 说明 |
|:--|:--|:--|
| `openai` | `OPENAI_API_KEY`（可选 `OPENAI_BASE_URL`、`LLM_MODEL`）| OpenAI 兼容 `/chat/completions`，`temperature=0` |
| `opencode` | 本地 `opencode` CLI | 调用 `opencode run --format json`，解析最终文本 |
| `mock` | 无 | 返回 `uncertain`，用于测试/离线冒烟 |
| `auto` | 自动 | 有 key → openai；否则有 opencode → opencode；否则 mock |

---

## 四、用法

```powershell
# 自动选择后端
python scripts/llm_refine_hpc.py D:\OPENSOURCE\OpenFOAM-v2512

# 指定 OpenAI 兼容后端
$env:OPENAI_API_KEY="..."
$env:LLM_MODEL="your-model"
python scripts/llm_refine_hpc.py D:\OPENSOURCE\OpenFOAM-v2512 --backend openai --model your-model

# 本地 opencode
python scripts/llm_refine_hpc.py tests\mutation\projects\bad_project_hpc --backend opencode --max-items 1

# 离线冒烟
python scripts/llm_refine_hpc.py tests\mutation\projects\bad_project_hpc --backend mock --out out.json
```

参数：`--max-items` 控制最多复核多少候选（默认 20）；`--cache` 指定缓存路径。

---

## 五、输出

在 `hpc_violations[]` 的 candidate 条目上增加：

```json
{
  "llm_review": "confirm|reject|uncertain",
  "llm_evidence": "src/halo.cpp:5 — ...",
  "llm_confidence": "high|medium|low",
  "llm_model": "...",
  "llm_prompt_version": "hpc-llm-refine-v1"
}
```

并在顶层增加：

```json
"llm_meta": {
  "backend": "opencode",
  "model": "default",
  "prompt_version": "hpc-llm-refine-v1",
  "temperature": 0,
  "reviewed": 1,
  "calls": 1,
  "cached": 0,
  "note": "llm_review is candidate-level evidence only; does not change score/gate/confirmed"
}
```

---

## 六、实跑示例（OpenFOAM 缺陷 fixture）

```text
HPC-005 review= confirm conf= high
  evidence= src/halo.cpp:5 — 该函数内 MPI_Isend 使用的局部 MPI_Request req
            在函数返回前未见 Wait/Test，request 随栈销毁，发送无法被正确完成/回收，
            非阻塞发送配对缺失，片段自身即可证明 HPC-005 风险
```

结果：`overall=58.5`、`gate=WARN`、`HPC-002 confirmed` 均不变；仅新增 `llm_review`。

---

## 七、与 §7.7 的对应

```text
静态候选（candidate）
   → LLM 语义精判（confirm/reject/uncertain + file:line）
   → MUST/TSan/TAU 实测（事实）
   → 人工裁定（是否 confirmed / 是否需修）
```

---

## 八、限制

- LLM 有随机性；固定温度/版本/缓存只能降低，不能消除；
- 不替代 TAU/MUST/TSan；
- 合成/片段不足时可能返回 `uncertain`；
- 不做评分/门禁决策。
