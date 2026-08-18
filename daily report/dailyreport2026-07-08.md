# 每日工作总结 — 2026-07-08

## 一、工作项（7 个）

| 项目/任务 | 说明 | 状态 |
|:---------|:-----|:----:|
| MMS 科普 PPT 中文版 | 29 页 PPT，文本与生成代码分离 | ✅ 完成 |
| MMS 科普材料整合 | 新摘要 + 原详解合并为 461 行完整文档 | ✅ 完成 |
| simpleFoam MMS 验证 | 无散度制造解，p_obs=1.919（SIMPLE 限制下合理） | ✅ 完成 |
| compressible NS MMS | rhoPimpleFoam 编译 + 三次独立尝试均因能量方程显式 K 项不稳定 | ❌ 停止（P1→P3）|
| MMS Testing Skill | 技能定义 + 3 个制造解模板 | ✅ 完成 |
| 阈值偏差工程依据 | 三层偏差来源定量分析 | ✅ 完成 |
| 概念介绍 PPT | PDE 求解器 → 收敛阶 → V&V 区分的 5 页概念页 | ✅ 完成 |

## 二、修复的问题

| 问题 | 原因 | 修复 |
|:-----|:------|:------|
| `sensibleInternalEnergy` 负内能 | T < T_ref 时 e=Cv(T-T_ref) < 0 | 基温从 300K 提高到 500K |
| `fvOptions` `#{}#` 语法 | 单行 `{ }` 被 OpenFOAM 词典解析器误读 | 改为多行 `#{ }#` 格式 |
| `codeAddSupRho` 未实现 | buoyantPimpleFoam 使用 `fvOptions(rho, U)` 需要密度加权版本 | 添加 `codeAddSupRho` 钩子 |
| 能量源项梯度抵消 | sin·sin 温度场导致 U·∇(ρh) = 0 | T 改为线性 500+20x |
| 动态编译库未加载 | 旧缓存库与新 fvOptions 文件不匹配 | `rm -rf dynamicCode/` 强制重编译 |
| rhoPimpleFoam 未编译 | OpenFOAM 安装未包含此求解器 | 从源码用 wmake 编译 |

## 三、技术数据

### MMS 验证结果

| 求解器 | 方程 | 网格 | p_obs | 状态 |
|:-------|:-----|:----:|:-----:|:----:|
| scalarTransportFoam | 稳态扩散 | 20/40/80 | **2.001** | ✅ |
| simpleFoam | 不可压 NS | 10/20/40 | **1.919** | ✅ |
| buoyantPimpleFoam | 可压缩 NS | — | — | ❌ P3 |

### 偏差阈值依据（新增概念）

| 来源 | 偏差范围 | 依据 |
|:-----|:--------:|:------|
| 高阶项污染 | ±0.01 | SAND2000-1444: p_obs = 2 + O(h²) |
| 网格畸变误差 | ±0.05~0.15 | Diskin & Thomas, AIAA 2011 |
| 非结构统计波动 | ±0.2~0.3 | Venkatakrishnan, AIAA 1995 |

### compressible MMS 失败根因

```
动量源 → U变化 → K(=½|U|²)变化 → fvc::ddt(rho,K)显式项滞后 
  → 内能/焓失衡 → T < T_ref → Negative temperature → 崩溃
```

三次独立尝试（buoyantPimpleFoam瞬态、rhoSimpleFoam稳态、buoyantPimpleFoam steadyState）均无法解决。

## 四、变更文件

| 文件 | 变更 |
|:-----|:------|
| `docs/zh/mms/MMS 科普.md` | 整合更新（461 行） |
| `docs/zh/mms/MMS.pptx` | 29 页中文版 |
| `docs/zh/mms/openfoam_simplefoam_mms.py` | 新增（simpleFoam MMS 自动验证）|
| `docs/zh/mms/openfoam_rhopimple_mms.py` | 重构（压缩 NS 框架） |
| `docs/zh/mms/mms_ppt_data.json` | 新增（PPT 文本数据） |
| `docs/zh/mms/generate_mms_ppt.py` | 新增（PPT 生成脚本） |
| `docs/zh/mms/derive_rhopimple_mms_t500.py` | 新增（T0=500K 源项推导） |
| `.opencode/skills/mms-testing/SKILL.md` | 新增（MMS testing skill） |
| `.opencode/skills/mms-testing/templates/sinusoidal.py` | 新增（扩散制造解模板） |
| `.opencode/skills/mms-testing/templates/ns_divfree.py` | 新增（NS 制造解模板） |
| `.opencode/skills/mms-testing/templates/compressible_euler.py` | 新增（可压缩模板，研究级） |

## 五、明日计划

| 优先级 | 事项 |
|:------:|:-----|
| P0 | 无（当前 P0 已全部完成）|
| P1 | 无（compressible NS MMS 已重新评估为 P3）|
| P2 | CI/CD 集成：将 MMS 测试纳入流水线 |
| P3 | 扩展 solidDisplacementFoam MMS |
