# HPC 维度 9 折交叉验证报告（B3.7 / KPI5）

> 语料：`tests/regression/snapshots/hpc_cv/`（5 健康 + 4 不健康）
> 判定：测试样本 overall 是否落在其余 8 个的 [min,max]
> 门槛：>= 7/9

## 语料

| 样本 | 标签 | overall |
|:--|:--:|--:|
| healthy_dealii | healthy | 100.0 |
| healthy_good_project | healthy | 100.0 |
| healthy_mfem | healthy | 86.5 |
| healthy_openfoam | healthy | 100.0 |
| healthy_su2 | healthy | 100.0 |
| unhealthy_bad_project | unhealthy | 58.5 |
| unhealthy_halo | unhealthy | 67.0 |
| unhealthy_load | unhealthy | 62.0 |
| unhealthy_nested | unhealthy | 75.0 |

## LOOCV 结果

| 留出样本 | 标签 | overall | 训练 min | 训练 max | 在内 |
|:--|:--:|--:|--:|--:|:--:|
| healthy_dealii | healthy | 100.0 | 58.5 | 100.0 | 是 |
| healthy_good_project | healthy | 100.0 | 58.5 | 100.0 | 是 |
| healthy_mfem | healthy | 86.5 | 58.5 | 100.0 | 是 |
| healthy_openfoam | healthy | 100.0 | 58.5 | 100.0 | 是 |
| healthy_su2 | healthy | 100.0 | 58.5 | 100.0 | 是 |
| unhealthy_bad_project | unhealthy | 58.5 | 62.0 | 100.0 | 否 |
| unhealthy_halo | unhealthy | 67.0 | 58.5 | 100.0 | 是 |
| unhealthy_load | unhealthy | 62.0 | 58.5 | 100.0 | 是 |
| unhealthy_nested | unhealthy | 75.0 | 58.5 | 100.0 | 是 |

## 汇总

- 通过：**8/9**（88.9%）
- 门槛：7/9 → **PASS**

> 说明：不健康样本含合成项目，可能高估泛化；建议后续用真实 held-out 项目复核。
