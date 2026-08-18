# 架构质量评估工具 HANDOFF v1.8

**日期**: 2026-06-09
**版本**: fc337b9 → v1.8+
**仓库**: https://github.com/DevG1000/arch-quality

---

## 一、项目状态总览

### 1.1 核心模块

| 文件 | 用途 | 行数 | 状态 |
|------|------|------|------|
| `src/arch_quality/arch_core.py` | 文件索引、依赖图、Git历史 | ~508 | 稳定 |
| `src/arch_quality/arch_metrics_multilang.py` | 多语言混合依赖6维+12条MLR规则 | ~1833 | 活跃（v1.8） |
| `src/arch_quality/arch_metrics_standard.py` | 标准架构质量4维评分 | ~271 | **待升级（P0）** |
| `src/arch_quality/arch_python_ast.py` | Python AST解析、pybind11/SWIG/ctypes检测 | ~400+ | 稳定 |
| `src/arch_quality/arch_report.py` | 综合报告入口 | ~175 | 稳定 |
| `src/arch_quality/arch_report_generator.py` | Markdown/JSON报告生成 | ~648 | 稳定 |
| `src/arch_quality/arch_bindings_parser.py` | pybind11绑定AST解析 | ~200+ | 稳定 |
| `src/arch_quality/arch_multilang_matcher.py` | 跨语言依赖匹配 | ~200+ | 稳定 |
| `src/arch_quality/skills/arch-quality.md` | 标准质量权重定义 | ~87 | **待更新（P0）** |
| `src/arch_quality/skills/multilang-dependency.md` | 多语言权重+MLR规则定义 | ~134 | 稳定 |

### 1.2 测试文件

| 文件 | 类数 | 用例数 | 覆盖范围 |
|------|------|--------|---------|
| `tests/test_python_ast.py` | 12 | 60 | pybind11/SWIG/MLR/回调/C文件malloc |
| `tests/test_bindings_parser.py` | 1 | 8 | BindingParser AST |
| `tests/test_build_dir.py` | 4 | 24 | build_dir扫描/MLR-002/003 |
| `tests/test_fortran_modules.py` | 6 | 33 | 模块映射/子程序映射/依赖解析/统计 |
| `tests/test_tcl_deps.py` | 8 | 17 | source/package/namespace/cross-lang/std_imports |
| `tests/regression/test_regression.py` | 5 | 30 | 5项目回归（详见下文） |
| **合计** | **36** | **172** | **137 passed, 1 skipped + 26 passed, 4 skipped** |

---

## 二、回归测试框架

### 2.1 文件结构

```
tests/regression/
├── __init__.py
├── test_regression.py            # 5类×6方法=30用例
└── snapshots/
    ├── openfoam_v2512.json        # OpenFOAM基线（无MLR违规）
    ├── brl_cad.json               # BRL-CAD（MLR-004/010/012）
    ├── freecad_cam.json           # FreeCAD-CAM（MLR-001/003/006/008）
    ├── freecad_fem.json           # FreeCAD-Fem（MLR-005/006）
    └── elmerfem.json              # ElmerFEM（MLR-008/010/012 + Fortran映射）
```

### 2.2 基线分数

| 项目 | overall | coupling | impact | call_depth | binding | script | cycles | 评估耗时 |
|------|---------|----------|--------|------------|---------|--------|--------|---------|
| OpenFOAM-v2512 | 79.5 | 100 | 100 | 100 | 30 | 80 | 100 | ~107s |
| BRL-CAD | 82.21 | 99.98 | 99.99 | 100 | 30 | 98.07 | 100 | ~50s |
| FreeCAD-CAM | 65.39 | 98.18 | 99.5 | 100 | 23.06 | 0 | 100 | ~22s |
| FreeCAD-Fem | 62.38 | 99.39 | 99.84 | 50 | 30 | 0 | 100 | ~52s |
| ElmerFEM | 67.5 | 100 | 100 | 100 | 30 | 0 | 100 | ~35s |

### 2.3 MLR规则覆盖矩阵

| 规则 | OpenFOAM | BRL-CAD | FreeCAD-CAM | FreeCAD-Fem | ElmerFEM | 单元测试 |
|------|:--------:|:-------:|:-----------:|:-----------:|:--------:|:-------:|
| MLR-001 跨语言循环 | | | ✅ | | | — |
| MLR-003 绑定签名不一致 | | | ✅ | | | ✅ |
| MLR-004 Tcl越界 | | ✅ | | | | ✅ |
| MLR-005 回调深度 | | | | ✅ | | ✅ |
| MLR-006 热点模块 | | | ✅ | ✅ | | ✅ |
| MLR-008 GIL死锁 | | | ✅ | | ✅ | ✅ |
| MLR-010 FFI内存 | | ✅ | | | ✅ | ✅ |
| MLR-012 ISO_C_BINDING | | ✅ | | | ✅ | ✅ |
| **MLR-002 绑定层缺失** | — | — | — | — | — | **❌** |
| **MLR-007 TNT模块** | — | — | — | — | — | **❌** |
| **MLR-009 通用类型绑定** | — | — | — | — | — | **❌** |

### 2.4 运行方式

```bash
# 快速回归（OpenFOAM + BRL-CAD，~3分钟）
pytest tests/regression/ -k "openfoam or brl_cad"

# 标准回归（3项目，~7分钟）
pytest tests/regression/ -k "not elmerfem"

# 完整回归（5项目，~4分钟）
pytest tests/regression/

# 单项目
pytest tests/regression/ -k "openfoam"

# 更新快照
$env:ARCH_REGRESSION_UPDATE=1; pytest tests/regression/

# 项目不存在时自动 @skipUnless 跳过
```

### 2.5 容差规则

| 指标 | 小值 (≤10) | 大值 (>10) |
|------|-----------|-----------|
| overall score | ±0.5 | ±0.5 |
| dimension score | ±1.0 | ±1.0 |
| MLR violation count | 精确匹配 | ±5% |
| file count | ±2% | ±2% |
| Fortran hit_rate | ±0.05 | ±0.05 |

---

## 三、P0任务：可测试性 → 测试覆盖度升级

### 3.1 当前实现问题

`arch_metrics_standard.py:calc_testability()` 仅统计文件路径中含"test"或"spec"的文件数占比：

```python
def calc_testability(self):
    """可测试性：测试文件占比"""
    test_files = sum(1 for f in self.index.files
                     if "test" in f["path"].lower() or "spec" in f["path"].lower())
    total = self.index.total_files()
    ratio = test_files / total if total > 0 else 0
    score = ratio * 200
    return max(0, min(100, score))
```

**问题**：

| 问题 | 数据证据 | 影响 |
|------|---------|------|
| 只看文件路径，不看内容 | OpenFOAM: 450测试文件含207个`.c`文件 | 可能是编译配置而非测试 |
| 没有语言维度覆盖 | OpenFOAM: C覆盖率2.1%, C++覆盖率36.6%, Python 0% | 掩盖关键语言无测试 |
| 没有目录维度覆盖 | OpenFOAM: `src/`3308目录仅362对应test目录 | 核心库测试盲区 |
| 评分尺度偏松 | `ratio * 200` → 50%测试比=100分 | 实际项目几乎无法达到 |
| 不区分绑定层 | 多语言项目的绑定无测试覆盖 | 跨语言接口风险不可见 |

### 3.2 升级方案

**重命名**: `calc_testability()` → `calc_test_coverage()`
**子维度名**: "可测试性" → "测试覆盖度"
**权重键名**: `"可测试性"` → `"测试覆盖度"`（`skills/arch-quality.md` 第22行同步修改）

**评分公式**:

```
测试覆盖度 = L1目录覆盖(30%) + L2语言覆盖(25%) + L3文件比(25%) + L4绑定层覆盖(20%)
```

| 层 | 指标 | 算法 | 满分条件 |
|----|------|------|---------|
| L1 目录覆盖 | 有测试的源码目录占比 | `test_dirs / src_dirs`，忽略`applications/`/`test/`等非源码目录 | 所有源码顶层目录下都有test子目录 |
| L2 语言覆盖 | 有测试文件的语言占比 | `langs_with_test / langs_total` | 每种语言至少有1个测试文件 |
| L3 文件比 | 测试文件与源码文件比 | `min(1.0, test_files / (source_files * 0.3))` | 测试文件达源码30% |
| L4 绑定层覆盖 | 仅多语言项目 | 有测试的绑定函数占比，单语言项目该项=0分（权重重分配到L1-L3） | pybind11 .def()函数有对应测试 |

**单语言项目权重重分配**: L1=37.5%, L2=31.25%, L3=31.25%（L4的20%按比例分配）

### 3.3 返回结构新格式

```python
scores = {
    "test_coverage": 42.7,  # 总分（替代 "testability"）
    "test_coverage_detail": {
        "dir_coverage": 0.12,    # 目录覆盖比例
        "lang_coverage": 0.67,   # 语言覆盖比例
        "file_ratio": 0.077,     # 测试文件比
        "binding_coverage": 0,   # 绑定层覆盖（单语言=0）
        "dir_score": 12.0,
        "lang_score": 66.7,
        "file_score": 25.3,
        "binding_score": 0,
        "test_files_by_lang": {"cpp": 142, "c": 207},
        "source_files_by_lang": {"c": 9735, "cpp": 246},
    },
}
```

### 3.4 需要修改的文件

| # | 文件 | 修改内容 | 影响范围 |
|---|------|---------|---------|
| 1 | `src/arch_quality/arch_metrics_standard.py` | `calc_testability()` → `calc_test_coverage()`，5层评分算法，返回detail dict | 核心 |
| 2 | `src/arch_quality/skills/arch-quality.md` | 第22行 `"可测试性"` → `"测试覆盖度"` | 权重 |
| 3 | `src/arch_quality/arch_report_generator.py` | 5处引用 `testability` → `test_coverage`，模板 `low_testability` → `low_test_coverage` | 报告 |
| 4 | `src/arch_quality/arch_report.py` | `std_result["structural"]["details"]["testability"]` → `"test_coverage"` | 兼容 |
| 5 | 新增 `tests/test_test_coverage.py` | 4个合成测试用例 | 测试 |

### 3.5 向后兼容策略

| 策略 | 详情 |
|------|------|
| **硬切换** | 权重文件和返回键名只使用新名称 `test_coverage`/`测试覆盖度`，旧快照需手动更新 |
| `_resolve_weights()` | 同时接受 `"可测试性"` 和 `"测试覆盖度"`，清理期后移除旧键 |
| 报告模板 | `low_testability` → `low_test_coverage`，旧键名 fallback 1个版本后移除 |

### 3.6 单元测试用例

| 用例名 | 场景 | 验证 |
|--------|------|------|
| `test_no_test_files` | 纯C项目无测试文件 | score=0, binding_score=0 |
| `test_python_full_coverage` | Python项目100%测试比 | score>80 |
| `test_multilang_partial_coverage` | C++(有测试)+Python(无测试) | L2语言覆盖<100% |
| `test_binding_test_coverage` | pybind11项目，有.def()绑定 | L4>0 |

---

## 四、技术债清单

| 编号 | 描述 | 优先级 | 说明 |
|------|------|--------|------|
| DEBT-1 | Fortran内容SyntaxWarning | 低 | ElmerFEM的.f文件含LaTeX公式（`\sigma`等），被regex引擎编译时触发。不影响正确性，可加 `warnings.filterwarnings('ignore', ...)` 或预处理content |
| DEBT-2 | FreeCAD全项目评估超时 | 低 | `src/`全目录7588文件`all_metrics()`超10分钟，当前仅用Mod/CAM和Mod/Fem子目录 |
| DEBT-3 | BRL-CAD Tcl内部库路径降级 | 中 | `src/tclscripts/`等目录可通过 `is_third_party_path()` 降级为INFO |
| DEBT-4 | MLR-002/007/009项目层回归缺口 | 高 | 5个回归项目均不触发，需合成测试用例 |
| DEBT-5 | KiCad `--build-dir` 验证 | 低 | SWIG绑定由CMake在构建时生成，需本地构建产物 |
| DEBT-6 | `import X` basename匹配 | 低 | 仅匹配项目内源码，不支持pip install路径 |

---

## 五、P0/P1/P2任务清单

### P0：代码质量（当前Session）

| 任务 | 文件 | 改动量 | 详情 |
|------|------|--------|------|
| 可测试性→测试覆盖度升级 | `arch_metrics_standard.py` | ~60行 | 5层评分算法，替换单一比率 |
| 权重键名更新 | `arch-quality.md` | 1行 | `"可测试性"` → `"测试覆盖度"` |
| 报告生成器同步 | `arch_report_generator.py` | ~10行 | 5处引用同步 |
| 综合报告键名同步 | `arch_report.py` | ~3行 | `"testability"` → `"test_coverage"` |
| 单元测试 | `tests/test_test_coverage.py` | ~100行 | 4个合成测试用例 |
| 回归快照更新 | `tests/regression/snapshots/*.json` | — | 重新生成含test_coverage的快照 |

### P1：报告增强

| 任务 | 文件 | 改动量 | 详情 |
|------|------|--------|------|
| 回归结果写入Markdown | `arch_report_generator.py` | ~40行 | 在结构质量章节中展示test_coverage_detail |
| MLR覆盖矩阵 | `arch_report_generator.py` | ~20行 | 12×5矩阵表格，标注✅/❌ |

### P2：性能优化

| 任务 | 文件 | 改动量 | 详情 |
|------|------|--------|------|
| SyntaxWarning抑制 | `arch_metrics_multilang.py` | ~3行 | Fortran文件扫描前加 `warnings.filterwarnings('ignore', ...)` |
| FileIndex缓存 | `arch_core.py` | ~30行 | 对重复读取同一文件内容的场景做缓存 |
| FreeCAD增量扫描 | `arch_core.py` | ~50行 | `FileIndex.__init__` 增加 `cache_file` 参数 |

---

## 六、新Session启动验证

```bash
# 1. 加载环境
cd D:\opensource\arch-quality

# 2. 验证回归测试基线（约4分钟）
python -m pytest tests/regression/test_regression.py -v --tb=short

# 3. 验证单元测试（约3秒）
python -m pytest tests/ -q --tb=short -k "not regression"

# 4. 确认BRL-CAD基线稳定
python -c "
import sys; sys.path.insert(0, 'src')
from arch_quality.arch_metrics_multilang import MultilangMetrics
m = MultilangMetrics(r'D:\OPENSOURCE\BRL-CAD')
r = m.all_metrics()
print('BRL-CAD overall:', r['overall'])
"

# 5. 确认OpenFOAM基线稳定
python -c "
import sys; sys.path.insert(0, 'src')
from arch_quality.arch_metrics_multilang import MultilangMetrics
m = MultilangMetrics(r'D:\OPENSOURCE\OpenFOAM-v2512')
r = m.all_metrics()
print('OpenFOAM overall:', r['overall'])
"
```

---

## 七、版本演进记录

| 版本 | 提交 | 功能 |
|------|------|------|
| v1.0 | `4b3b20f` | 6维评估引擎、12条MLR规则、项目级报告 |
| v1.1 | `41f6656` | MLR-008 pybind11上下文预检、MLR-012 v2（F77 + 第三方降级） |
| v1.2 | `303779e` | MLR-005回调链（路径1-3）、MLR-006第三方热点降级 |
| v1.3 | `e5a63aa` | SWIG %module/%extend/%inline解析、MLR-003 SWIG感知 |
| v1.4 | `bb394f5` | MLR-010 v2（5层过滤 + 3级严重度）、MLR-012 v3（跨语言边感知）、--build-dir |
| v1.5 | `ba6c106` | MLR-005 Path 4（PyImport_ImportModule）、import直连回退 |
| v1.6 | `63a2dfb` | Tcl source/package require/namespace边、_collect_std_imports Tcl支持 |
| v1.7 | `a21f43a` | MLR-012 @allowed_coupling注解降级 |
| v1.8 | `fc337b9` | MLR-010 C/C++ malloc/calloc/realloc检测 + SFREE宏识别 |
| v1.9 | **待实施** | 可测试性→测试覆盖度升级（P0任务） |

---

## 八、插件同步

开发完成后需同步到插件目录：

```powershell
$src = "D:\opensource\arch-quality\src"
$dst = "C:\Users\Guo\.config\opencode\opencode-arch-quality"

# 同步源码
Copy-Item -Path "$src\arch_quality\*" -Destination "$dst" -Recurse -Force

# 同步回归测试
Copy-Item -Path "D:\opensource\arch-quality\tests\regression\*" -Destination "$dst\tests\regression" -Recurse -Force

# 同步文档
Copy-Item -Path "D:\opensource\arch-quality\docs\zh\HANDOFF-v1.8.md" -Destination "$dst\docs\zh\HANDOFF-v1.8.md" -Force
```