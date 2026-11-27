# H3 G0 运行时内核 CI 方案（方法 C + 专用 job）

**版本**：v1.0
**日期**：2026-10-21
**归属**：`H3-WP0基线实测方案.md` → T0.6（Gate G0）；承载 `H3全维化执行计划v2.md` → WP-5 的 B2/B3/B5
**状态**：基础设施已落地；**首次 CI 运行失败（缺 X11 头），已修复待复跑**
**G0 结论**：条件可行 → **采用方法 C（预构建 OCCT V8.0.1 缓存）+ 专用 job（回退选项 2）**

---

## 一、决策与依据

| 方法 | 结论 | 理由 |
|:-----|:-----|:-----|
| A. apt（`libocct-*`）| ❌ 否决 | ubuntu-latest = OCCT **7.6.3**，样本 ref = **V8.0.1** → 版本漂移；运行内核 ≠ 静态基线内核，B2/B3/B5 不可比 |
| B. 源码构建 V8.0.1 | ⚠️ 可用但重 | ~15–30 min / ~5 GB，不宜每 PR |
| **C. 预构建缓存 + 专用 job** | ✅ **采用** | 构建一次、缓存复用；专用 job 不阻塞 PR |

详见 `H3基线实测报告.md` §二（G0）。

---

## 二、基础设施（已落地）

| 文件 | 作用 |
|:-----|:-----|
| `scripts/ci/build_occt.sh` | 按 `OCCT_REF` 浅克隆 + CMake 构建 + 安装到 `.occt-cache/install`（幂等：已装则跳过）|
| `scripts/ci/run_kernel_smoke.sh` | 编译并运行内核探针（链接已构建 OCCT）|
| `scripts/ci/kernel_smoke.cpp` | 最小探针：构造 `BRepPrimAPI_MakeBox` + `BRepCheck_Analyzer` 校验 + 面数断言 |
| `.github/workflows/arch-quality-ci.yml` → `runtime-kernel` job | schedule（周一 03:00）+ `workflow_dispatch`；`actions/cache` 缓存 `.occt-cache/install` |

**版本对齐**：`OCCT_REF = b8f597c677811d1f9f4d8a97f5ae2825c0353a42`（= `projects.yaml` 的 occt 样本 ref V8.0.1），确保运行内核与 GCS/ACL 静态基线同源。

**缓存键**：`occt-v8.0.1-${runner.os}-${hashFiles('scripts/ci/build_occt.sh')}` —— 构建脚本变更即失效重建。

**非阻塞**：`if: schedule || workflow_dispatch` → 仅定时/手动触发，PR 主门禁（`unit`/`gate`）不受影响。

---

## 三、B2/B3/B5 接入点（WP-5）

`runtime-kernel` job 是运行时检测的**底座**。WP-5 实施时按下列方式扩展（不改本 job 骨架）：

| 规则 | 接入方式 |
|:-----|:---------|
| **B2 欧拉公式约束** | 扩展 `kernel_smoke.cpp`（或新增 `runtime_checks.cpp`）：对形状求 V−E+F 拓扑不变量并与期望比对 |
| **B3 B-Rep 闭合性运行时判定** | 在探针中对目标形状跑 `BRepCheck_Analyzer` / `ShapeAnalysis_Shell`，输出 `IsValid` + 失败明细 |
| **B5 ACL 内核升级兼容** | 对同一源码分别以 V8.0.1 与"上一版本"构建，比较 API 使用面（编译期差异）|

**建议**：WP-5 将 `kernel_smoke.cpp` 泛化为 `scripts/ci/runtime_checks.cpp`，接受形状输入 + 检查清单，输出 JSON 供 Python 侧汇总。

---

## 四、使用方式

**CI**：GitHub Actions → 手动 `Run workflow`，或每周一定时；产物/日志含 `OCCT version: <ver>` 与 `box valid=true faces=6`。

**本地（有 cmake 的 Linux/macOS）**：
```bash
export OCCT_CACHE="$PWD/.occt-cache"
bash scripts/ci/build_occt.sh        # 首次 ~15–30 min；命中安装则秒退
bash scripts/ci/run_kernel_smoke.sh  # 预期：OCCT version: 8.0.1 / box valid=true faces=6
```

**本地（Windows，无 cmake）**：跳过构建，仅审阅脚本；实际验证在 CI。

---

## 五、验证状态与风险

| 项 | 状态 |
|:---|:-----|
| 脚本/工作流落地 | ✅ 已提交 |
| **CI 实测通过** | ✅ run `45102267162`：`runtime-kernel` success；`euler=PASS closure=PASS api_compat=SKIPPED` |
| 构建耗时实测 | ✅ 冷构建约 33 min；缓存命中后 smoke 约 5 s |

**风险**

| 风险 | 缓解 |
|:-----|:-----|
| 首次构建超 CI 时限（默认 6h，通常足够）| 精简模块（关 Visualization/Draw/AppFramework）；必要时进一步减模块 |
| CMake 模块开关名与 8.0 不符 | 首次 CI 失败时按日志调整 `BUILD_MODULE_*` |
| 缓存失效频繁 | 缓存键含构建脚本 hash，仅脚本变更时重建 |
| 缓存方案不成立 | 触发回退：选项 ①（永久 KNOWN_HOLES）或 ③（仅静态子集），并升 H3 计划 v2.1 |

---

## 六、对下游

- **决策 3 维持**：B2/B3/B5 实施，由本底座承载。
- **H3 计划 v2**：不需回退；G0 已验证，记录见本文件 + `H3-WP5运行时检测报告.md`。
- **WP-5**：B1/B4/B6/B7 可先做；B2/B3/B5 依赖本 job 的缓存就绪。

---

*G0 基础设施已验证：run `45102267162` 的 `Runtime Kernel (OCCT V8.0.1)` job success。*