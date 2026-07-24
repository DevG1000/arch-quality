# 数值精度评估工具 — 人工评审指南

## 目的

对照工具自动评分，获取 3 个代表性项目的**人工独立评分**，量化工具的误报/漏报率。

## 选择项目

| 项目 | 类型 | 当前工具评分 | 选择理由 |
|:-----|:------|:----------:|:---------|
| **MOOSE** | 多物理场 FEM | 96.0（最高分）| 验证工具是否漏报缺陷（高分项目可能隐藏漏报）|
| **FreeFEM** | FEM 求解器 | 96.0（高分）| 中等规模，验证工具评分与人工是否一致 |
| **FEniCSx** | FEM 框架 | 46.33（最低分）| 验证工具是否误报缺陷（低分项目可能被不公正扣分）|

## 评审流程

```
Step 1: 阅读项目文档（README、示例代码）
Step 2: 浏览关键文件结构
Step 3: 按 6 个维度逐一填写评审表
Step 4: 记录人工评分（0-100）
Step 5: 查看工具评分（从 baseline JSON 获取）
Step 6: 记录差异 > 10 分的原因
Step 7: 标注发现的误报和漏报
```

## 各维度评审要点

### 1. 数值稳定性保障

**评分参考**：
- 检查求解器配置：`fvSchemes` 中的 `ddtSchemes`（隐式/显式）
- 检查控制文件：`maxCo`、`CFL`、`adjustTimeStep`
- 检查数值格式：`upwind`、`linearUpwind`、`bounded`、`limiter`

**常见误报**：
- 注释中出现的 CFL/upwind 关键词（工具会误认为代码在用）
- 仅单文件有配置但未全局生效

### 2. 舍入误差控制

**评分参考**：
- 搜索 `Kahan`、`compensation`、`compensated` 等关键词
- 检查是否存在 `Verrou`、`CADNA`、`Valgrind` 配置或文档
- 检查 `double` vs `float` 的使用比重

**常见误报**：
- `a - b` 相消模式可能在整数运算中（非浮点，无实际风险）
- 变量相减但值不在同一数量级（不会发生有效数字丢失）

### 3. MMS 验证

**评分参考**：
- 搜索 `*mms*`、`*manufactured*`、`*verification*` 文件
- 检查测试目录结构
- 检查是否有收敛阶计算代码

**常见误报**：
- `verification` 目录可能是接触问题验证（contact verification）而非 MMS
- `order_of_accuracy` 可能是文档中的引用而非实际计算

### 4. 误差估计与控制

**评分参考**：
- 搜索 `mesh_convergence`、`grid_study`、`richardson`、`refinement_study`
- 检查 `tolerance`、`residualControl`、`relTol` 配置
- 检查 `Coarse/Fine` 等目录命名

**常见误报**：
- `richardson` 可能是开发者姓名（如 Chris Richardson）而非算法
- `refinement` 目录可能是细化算法实现而非收敛性研究

### 5. 回归测试覆盖

**评分参考**：
- 检查 `test/`、`tests/` 目录
- 检查测试中的 `assert`、`check`、`verify` 等断言
- 检查 CI 配置（`.github/workflows`、`.gitlab-ci.yml`）

### 6. 数值债务密度

**评分参考**：
- 综合前 5 个维度的评分
- 低分维度占比 = 低分数量 / 6

## 评分校准建议

| 人工感觉 | 建议评分 |
|:---------|:--------|
| 做得非常好，无可挑剔 | 95-100 |
| 有完善的实践，但少数地方可以改进 | 80-94 |
| 基本做法到位，有明显改进空间 | 60-79 |
| 少量实践，大量缺失 | 40-59 |
| 几乎没有任何数值精度实践 | 0-39 |

## 填写完成后

1. 将填好的评审表保存为 `scripts/reviews/{project}_{reviewer}_{date}.md`
2. 运行对比脚本：
   ```
   python scripts/compare_review.py --tool-score 96.0 --manual-score 95 --project MOOSE --reviewer "张三"
   ```
3. 或批量对比：
   ```
   python scripts/compare_review.py --batch reviews/*.md
   ```
