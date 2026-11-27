# 化石代码与技术债评估 阶段 C 校准记录

> **版本**：0.1
> **日期**：2026-11-05
> **对象**：FOS-001~012 真实样本校准
> **样本**：Code_Aster / BRL-CAD / OpenFOAM-v2512

---

## 一、真实基线结果

| 样本 | is_fossil | overall | gate | 触发规则 | 耗时 |
|:--|:--:|:-:|:--:|:--|:-:|
| Code_Aster | True | 60.5 | WARN | FOS-001/007/008/009/012 | ~62s |
| BRL-CAD | True | 30.0 | WARN | FOS-001/002/003/004/005/006/007/008/009 | ~35s |
| OpenFOAM | True | 54.0 | PASS | FOS-003/004/005/006/007/008/009 | ~54s |

> 均为候选/确认规则按指南口径；真实基线快照在 `tests/regression/snapshots/fossil_*.json`。

## 二、校准改动

| 规则 | 改动 | 原因 |
|:--|:--|:--|
| FOS-001 | 固定格式 Fortran **本身即触发**（不要求 `COMMON`/`IMPLICIT`） | BRL-CAD 自有固定格式 Fortran 无 `COMMON`，旧逻辑漏报 |
| FOS-006 | 代码块需 **代码行 ≥ 非空行 50%** | OpenFOAM 许可证头被误判为成块注释（927→56） |
| FOS-007 | 最小 **40 token**；最多 **200 对**；排除 `main/wmain/WinMain/DllMain`；fingerprint/index **排序** | 降低入口样板克隆误报；保证跨进程确定性 |
| FOS-008 | 排除 `0/1/0.0/1.0/0.5/10/100` 等平凡常量 | 减少跨文件重复常量的噪声 |
| FOS-009 | **同名 + 同参数签名** + ≥40 token + 排除 `main/init/run/...` 常见名 + 上限 200 | 抑制“同名不同签名”的误报 |
| FOS-011 | `KLOC = max(实际, 1.0)` | 极小项目避免比率失真 |
| D1 | 标准 `calc_dead_code` 注释块归 FOS-006 | 避免双扣 |
| D3 | 标准 `test_coverage` 读取 `legacy_untested_modules` 并剔除 | 避免 FOS-012 双扣 |

## 三、验证

| 项 | 结果 |
|:--|:--|
| FOS 单元 | 20 passed |
| FOS 集成 | 4 passed（含 D3） |
| FOS 变异 | 6 组翻转 |
| 合成回归 | 9 passed（5 基线 + 4 确定性） |
| 真实回归 | **3 passed**（`RUN_FOSSIL_REAL=1`） |
| 覆盖矩阵 | 108/108 |
| Harness | **3 passed**（case-10/11/12） |
| CI gate | PASS（真实回归可选） |

## 四、FOS-007/009 抽样复核

> **可审计明细**：`阶段C-FOS007009抽样.md`（实际 pair 清单 + OpenFOAM/BRL-CAD 计数）。

抽样 OpenFOAM 命中：

| 规则 | 抽样结果 | 判定 |
|:--|:--|:--|
| FOS-007 | 早期 12/12 为各 solver `main` 样板；排除入口后，样本转为 `writeSet`/`addPatch` 等 utility helper 克隆 | 多为真实 Type-1/2 克隆，但属工具样板，candidate 低风险 |
| FOS-009 | 12/12 为同名+同签名 helper（`writeSet`/`addPatch`/`printMesh` 等），部分为不同上下文实现 | 存在误报；已加签名过滤，BRL-CAD 160→35、OpenFOAM 200→54、Code_Aster 200→44 |

**校准决定**：

- FOS-007 排除 `main/wmain/WinMain/DllMain` 入口函数，避免 solver `main` 样板污染；
- FOS-009 按 **函数名 + 参数签名** 分组，减少同名不同签名误报；
- 两者仍为 **candidate**，不设 ERROR，不阻断门禁；保留抽样复核职责。

## 五、残留

1. FOS-007/009 仍可能包含样板/同名 helper 误报，但均为 candidate；已抽样并保留人工复核。
2. FOS-004 仅 static 函数，全局未引用函数可能漏报。
3. FOS-012 以目录名近似，未接 git 年龄。
4. FOS-008 平凡常量已排除，但仍可能包含合理物理常量。

## 六、下一步

1. 阶段 C 复核 + 版本收口。

---

*校准参数为阶段 C 工程默认值，后续可按项目类型分档。*
