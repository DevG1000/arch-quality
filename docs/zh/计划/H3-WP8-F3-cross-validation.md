# H3 WP-8 F3 全维 LOOCV 汇总

**生成时间**：2026-11-25 16:16:40
**判定口径**：LOOCV in-range; 7/9 rate threshold; nine_fold requires n>=9

## 汇总

| 引擎 | 折数 | 通过 | 通过率 | 9 折 | 状态 |
|:--|--:|--:|--:|:--:|:--|
| standard | 9 | 7 | 77.78% | 是 | PASS |
| numerical | 9 | 8 | 88.89% | 是 | PASS |
| solver_physics | 9 | 7 | 77.78% | 是 | PASS |
| geometry_consistency | 9 | 8 | 88.89% | 是 | PASS |
| anti_corruption | 9 | 7 | 77.78% | 是 | PASS |
| hpc | 9 | 8 | 88.89% | 是 | PASS |

- 有数据引擎：6
- 达到 7/9 比率：6
- 真正 9 折 PASS：6
- 待扩语料：multilang

> standard/numerical are 9-fold; multilang LOOCV corpus pending
