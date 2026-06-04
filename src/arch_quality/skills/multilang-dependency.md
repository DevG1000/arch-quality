# 多语言混合依赖评估技能

本技能提供多语言混合依赖评估的领域知识，包括 6 个评估维度定义、评分算法和 12 条 MLR 规则。

## 权重分配

| 维度 | 权重 |
|------|------|
| 跨语言调用强度 | 15% |
| 跨语言影响半径 | 20% |
| 跨语言回调深度 | 10% |
| 绑定层接口一致性 | 25% |
| 脚本越界访问 | 15% |
| 跨语言循环依赖 | 15% |

## 维度定义

### 1. 跨语言调用强度

衡量模块被其他语言调用的频率。高频跨语言节点是系统的关键依赖点。

评分算法（Python 实现见 `arch_metrics_multilang.py::calc_coupling_intensity()`）：

```
L = 模块的跨语言边数（入边+出边）
L == 0  → 100
L <= 2  → 80
L <= 5  → 60 - (L-3)*5
L <= 10 → 40 - (L-6)*4
L > 10  → max(0, 20 - (L-11)*2)
```

### 2. 跨语言影响半径

修改一个模块时，通过跨语言依赖图可能影响的模块总数。BFS 遍历跨语言边，最大深度 5。

评分算法：

```
R = 从该模块经跨语言边可达的模块数（BFS，深度≤5）
R == 0   → 100
R <= 3   → 90
R <= 7   → 70
R <= 15  → 40
R > 15   → max(0, 30 - (R-15)*2)
```

### 3. 跨语言回调深度

跨语言调用链的最大深度。深度越大，调试和资源管理越困难。

评分算法：

```
D_max = 跨语言调用链的最大深度（仅计跨语言边）
D_max <= 1 → 100
D_max == 2 → 80
D_max == 3 → 50
D_max > 3  → 20
```

### 4. 绑定层接口一致性

C++/Fortran 原语接口与绑定层（pybind11/SWIG/ctypes）暴露接口的匹配程度。

评分算法：

```
total_exports = 原语公共接口总数
bound_exports = 绑定层注册的接口数
matched_sigs  = 签名完全匹配的接口数

ratio_bound = bound_exports / total_exports
ratio_match = matched_sigs / bound_exports

score = (ratio_bound * 100 + ratio_match * 100) / 2
```

扣分：每使用 `void*`/`any` 等通用类型，扣 5 分，上限 20 分。

### 5. 脚本越界访问

脚本层（Python/Tcl/Lua）越过 API 边界直接访问内部实现的程度。

评分算法：

```
total_calls = 脚本层外部调用总数
direct_access = 直接访问内部符号的次数
violation_ratio = direct_access / total_calls
score = max(0, 100 - violation_ratio * 200)
```

### 6. 跨语言循环依赖

依赖图中涉及两种及以上语言的循环依赖。

评分算法：

```
cycles = 跨语言循环依赖数量
cycle_length_sum = 所有循环的节点数之和
severity = min(100, cycles * 10 + cycle_length_sum * 2)
score = max(0, 100 - severity)
```

## 综合评分

```
多语言依赖综合分 = 
    调用强度 × 15% +
    影响半径 × 20% +
    回调深度 × 10% +
    绑定一致性 × 25% +
    脚本越界 × 15% +
    循环依赖 × 15%
```

## MLR 规则清单

| 规则ID | 名称 | 严重级别 |
|--------|------|---------|
| MLR-001 | 跨语言循环依赖检测 | HIGH |
| MLR-002 | 绑定层接口缺失 | HIGH |
| MLR-003 | 绑定层签名不匹配 | HIGH |
| MLR-004 | 脚本直接访问内部 | HIGH |
| MLR-005 | 跨语言回调深度超标 | MEDIUM |
| MLR-006 | 热点模块（高频调用） | MEDIUM |
| MLR-007 | TNT模块（影响半径超标） | MEDIUM |
| MLR-008 | GIL死锁风险 | HIGH |
| MLR-009 | 绑定层使用通用类型 | MEDIUM |
| MLR-010 | FFI内存所有权混乱 | HIGH |
| MLR-011 | 小数据频繁跨语言传输 | LOW |
| MLR-012 | Fortran缺少ISO_C_BINDING | MEDIUM |
