# H3 WP-8 F3 全维 LOOCV 汇总

**生成时间**：2026-11-25 14:33:52
**判定口径**：LOOCV in-range; 7/9 rate threshold; nine_fold requires n>=9

## 汇总

| 引擎 | 折数 | 通过 | 通过率 | 9 折 | 状态 |
|:--|--:|--:|--:|:--:|:--|
| numerical | 5 | 4 | 80.00% | 否 | PARTIAL |
| solver_physics | 9 | 7 | 77.78% | 是 | PASS |
| geometry_consistency | 9 | 8 | 88.89% | 是 | PASS |
| anti_corruption | 9 | 7 | 77.78% | 是 | PASS |
| hpc | 9 | 8 | 88.89% | 是 | PASS |

- 有数据引擎：5
- 达到 7/9 比率：5
- 真正 9 折 PASS：4
- 待扩语料：standard, multilang

> numerical currently 5-fold; standard/multilang LOOCV corpus pending
