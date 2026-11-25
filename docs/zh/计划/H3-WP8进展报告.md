# H3 WP-8 进展报告

> **版本**：0.1
> **日期**：2026-11-24
> **状态**：WP-8 已启动，F2 完成

## 1. 工作包状态

| 项 | 状态 | 说明 |
|:--|:--|:--|
| E1 ACL 科学内核扩展 | ⏳ | PETSc/deal.II/VTK 扩展后续 |
| F1 元模型 §5.2 参考案例回填 | ⏳ | 9 案例结构回填后续 |
| **F2 18 项目 fetch.ref + 严格校验** | ✅ | 本次完成 |
| F3 全维度 9 折 LOOCV | ⏳ | 现有 numerical/solver/GCS/ACL/HPC 脚本，需统一汇总 |
| F4 Agent Harness GCS/ACL 端到端 | ⏳ | GCS 已有 case 4~6；ACL cases 待补 |

## 2. F2 实施内容

### 2.1 固定 ref

为 18 个 H1 项目及可获取的 H2 样本补齐 `fetch.ref`：

- openfoam / brl-cad / freecad / elmerfem
- moose / dealii / freefem / mfem / fenicsx / kratos / su2 / precice
- eigen / boost / folly / abseil / range-v3
- code_aster / kicad

`arch-quality`、`wp7_corpus` 为本地样本，标记 `method: local`。

### 2.2 checksums

`projects.yaml` 的 `checksums` 段新增对应：

```yaml
git_ref:<repo>: <40-hex-commit>
```

### 2.3 强制门禁

`scripts/fetch_project.py --check-all`：

- 18 个 H1 项目缺 `fetch.ref` 或 checksum → `[FAIL]`，退出码 1；
- 非 H1 项目（如 gmsh 网络不可达）暂保留 `[WARN]`；
- 当前运行结果：**exit 0**，所有 H1 项目 `[OK]`。

## 3. 验证

```text
python scripts/fetch_project.py --check-all   → exit 0
tests/test_fetch_project.py                   → 3 passed
```

## 3.1 F4 实施内容

新增 ACL Harness 三例：

| case | 项目 | 结果 |
|:--|:--|:--|
| case-13-acl-good | good_project_acl | **PASS**，overall 92.5 |
| case-14-acl-flawed | bad_project_acl | **PASS**，overall 14.0 |
| case-15-acl-non | good_project_standard | **PASS**，is_acl=false |

配套：

- `rules.json` v1.3 新增 `acl_dimension_fields`；
- `single_engine_prefixes` 加入 anti-corruption 引擎；
- `assert_not_applicable` 支持 `is_acl=false`；
- 新增 `tests/test_harness_acl.py`；
- 新增合成 `bad_project_acl`（直接 OCCT 调用 + STEP 直连）。

验证：

```text
tests/test_agent_assert.py + test_harness_acl.py + test_harness_gcs.py + test_fetch_project.py
→ 46 passed
python scripts/run_agent_harness.py --case case-13-acl-good/14/15
→ 3/3 PASS
```

## 3.2 F3 实施内容

新增 `scripts/cross_validate_all.py`：

- 读取 numerical / solver / GCS / ACL / HPC 的 JSON 结果；
- 统一为 LOOCV in-range 口径；
- 7/9 比率阈值 + `nine_fold` 标记；
- 输出 `H3-WP8-F3-cross-validation.json` / `.md`。

当前汇总：

| 引擎 | 折数 | 通过 | 9 折 | 状态 |
|:--|--:|--:|:--:|:--|
| numerical | 5 | 4 | 否 | PARTIAL |
| solver_physics | 9 | 7 | 是 | PASS |
| geometry_consistency | 9 | 8 | 是 | PASS |
| anti_corruption | 9 | 7 | 是 | PASS |
| hpc | 9 | 8 | 是 | PASS |

总计：**5 引擎有数据，4 项真正 9 折 PASS**；standard/multilang 语料待扩。

验证：

```text
tests/test_cross_validate_all.py → 5 passed
```

## 4. 下一步

1. F4：补 ACL Agent Harness cases（good/flawed/non-ACL）与 `acl_dimension_fields`；
2. F3：✅ 聚合层完成；standard/multilang 9 折语料待扩；
3. F1：按元模型 §5.2 回填标准/多语言/数值/物理场 9 案例；
4. E1：ACL 科学内核扩展。
