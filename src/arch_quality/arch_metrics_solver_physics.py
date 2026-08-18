# -*- coding: utf-8 -*-
"""
arch_metrics_solver_physics.py — 求解器和物理场模块化架构模式识别评估

实现《求解器与物理场模块化架构模式识别评估指南（1.3版）》定义的 4 维评分模型
和 11 条 MPR 规则（MPR-001~MPR-010、MPR-012）的静态分析检测。

版本绑定：
  - 指南版本：1.3（2026-07-23）
  - Skill 版本：1.0
  - 实现版本：1.0 对齐
"""

import os
import re
import json
import argparse
from collections import defaultdict
from pathlib import Path

from arch_quality.arch_core import (
    FileIndex, DepGraph,
    load_weights_from_skill, ensure_output_dir, write_report,
    read_text_smart,
)

SKILL_PATH = str(Path(__file__).parent / "skills" / "solver-physics-architecture.md")

GUIDE_VERSION = "1.3"
SKILL_VERSION = "1.0"

# ── 常量定义 ──
CPP_EXTS = {".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".txx"}
C_EXTS = {".c", ".h"}
FORTRAN_EXTS = {".f90", ".f", ".f03", ".f08"}
ALL_SOLVER_EXTS = CPP_EXTS | C_EXTS | FORTRAN_EXTS | {".py"}

# 多物理场检测关键词
MULTIPHYSICS_DIR_KEYWORDS = {"structural", "thermal", "fluid", "solid", "heat",
                             "structure", "mechanics", "electromagnetics"}
MULTIPHYSICS_FILE_KEYWORDS = {"multiphysics", "multi_physics", "fsi", "fluid-structure",
                               "coupled", "coupling", "co_simulation", "cosimulation"}
COUPLING_FRAMEWORKS = {"precice", "mui", "opencascade", "kratos", "moose"}

# 内部数据访问检测
INTERNAL_ACCESS_PATTERN = re.compile(
    r'(?:\w+)\s*\.\s*(?:data_|internal_|private_)\w+\s*[=;]',
    re.MULTILINE
)
# 跨模块直接成员访问（非接口调用）
DIRECT_MEMBER_ACCESS = re.compile(
    r'(?:\w+)\s*->\s*(?:[a-z]\w*)\s*[=;]',
    re.MULTILINE
)

# FMI 接口检测
FMI_FUNCTIONS_PATTERN = re.compile(
    r'\b(fmi2DoStep|fmi2Get(Real|Integer|Boolean|String)|'
    r'fmi2Set(Real|Integer|Boolean|String)|fmi2Instantiate|'
    r'fmi2FreeInstance|fmi2SetupExperiment)\s*\(',
    re.MULTILINE
)
FMU_XML_PATTERN = re.compile(r'modelDescription\.xml', re.MULTILINE | re.IGNORECASE)

# 求解器接口多态性检测
ABSTRACT_SOLVER_PATTERN = re.compile(
    r'(?:class\s+\w+\s*\{[^}]*\bvirtual\b[^}]*\bsolve\s*\([^)]*\)\s*=\s*0)',
    re.MULTILINE | re.DOTALL
)
# B3.5 SU2 漏报探查修复：SU2 CIteration 用大写 Solve()，
# 原 \bsolve\b 大小写敏感且 .* 跨方法误匹配/漏匹配。
# 精确模式限定同一声明（[^;(] 排除方法结束 ; 与参数列表 (），兼容 Solve/solve。
VIRTUAL_SOLVE_PATTERN = re.compile(
    r'\bvirtual\b[^;(]*?[sS]olve\s*\(', re.MULTILINE
)

# 收敛控制参数
CONVERGENCE_PATTERN = re.compile(
    r'\b(residual|tolerance|relativeTolerance|absoluteTolerance|'
    r'convergenceCriterion|maxIter|nIter)\b',
    re.MULTILINE | re.IGNORECASE
)
ITERATION_LIMIT_PATTERN = re.compile(
    r'\b(maxIter|nIter|maxIterations|iterMax)\s*[=:]\s*(\d+)',
    re.MULTILINE | re.IGNORECASE
)

# OpenFOAM 配置字典中的耦合求解收敛控制标记
# residualControl 出现在 fvSolution 的 SIMPLE/PIMPLE/PISO（流-压力耦合求解）块，
# 属耦合收敛控制，计入耦合收敛稳定性（B3.5 边界 3 修复）。
RESIDUAL_CONTROL_PATTERN = re.compile(
    r'\bresidualControl\b', re.MULTILINE | re.IGNORECASE
)

# 耦合上下文关键词：收敛控制必须与耦合语义同现，才算"耦合收敛稳定性"
# （排除单求解器内部离散残差/线性迭代容差）
COUPLING_CONTEXT_PATTERN = re.compile(
    r'\b(coupl|fsi|transfer|exchange|multi.?app|sub.?app|'
    r'fixed[_ -]?point|picard|staggered|iterative)\b',
    re.IGNORECASE
)

# 第三方依赖目录名（不参与模块级检测）
# 第三方库（如 UMFPACK 直接求解器）的头文件互引用会被误判为项目模块循环依赖。
# B3.5 验证 ElmerFEM 时发现：31 个循环 100% 来自根目录 umfpack 依赖。
THIRD_PARTY_DIR_NAMES = {
    "umfpack", "contrib", "third_party", "thirdparty", "3rdparty",
    "external", "vendor", "deps", "dependencies", "libs", "external_libs",
    "external_libraries",
}

# MMS 验证文件
MMS_PATTERN = re.compile(
    r'\b(mms|manufactured.solution|verification|order.of.accuracy)\b',
    re.MULTILINE | re.IGNORECASE
)
MMS_DIR_KEYWORDS = {"mms", "manufactured", "verification"}

# 系统级验证
V_AND_V_PATTERN = re.compile(
    r'\b(v.and.v|v\s*&\s*v|verification.*validation|system.*test|integration.*test)\b',
    re.MULTILINE | re.IGNORECASE
)

# 插件机制
PLUGIN_PATTERN = re.compile(
    r'\b(register|plugin|factory|loadLibrary|dlsym|GetProcAddress|'
    r'application\s*::\s*create|import\s+module)\b',
    re.MULTILINE
)

# 统一接口基类名（可扩展列表，供 _detect_unified_interface 生成正则）
# 通过 B3.5 LLM 漏报探查发现的新框架命名模式，经人工审查后追加到此列表
INTERFACE_BASE_CLASSES = [
    "Plugin", "Module", "Application", "Solver",
    "MooseObject",          # MOOSE（B3.5 探查发现，实测 196 个继承）
    "KratosApplication",    # Kratos（B3.5 探查发现，实测 10 个继承 + Register 注册）
    "Process",              # Kratos（B3.5 探查发现，实测 202 继承，抽样内 26 命中）
]


def _build_unified_interface_pattern():
    """根据 INTERFACE_BASE_CLASSES 生成统一接口检测正则"""
    names = "|".join(re.escape(n) for n in INTERFACE_BASE_CLASSES)
    return re.compile(
        r'(?:class|struct)\s+\w+\s*:\s*(?:public\s+)?(?:' + names + r')\b',
        re.MULTILINE
    )


UNIFIED_INTERFACE_PATTERN = _build_unified_interface_pattern()

# Fortran 插件机制检测（动态加载求解器过程）
# ElmerFEM 用 GetProcAddr + ExecSimulationProc 运行时加载求解器（B3.5 探查发现）
# Fortran 项目用过程指针而非 C++ 类继承，需独立的插件机制检测
FORTRAN_GET_PROC_ADDR = re.compile(
    r'\b(?:GetProcAddr|GetProcAddress|dlsym|dlopen|LoadLibrary|'
    r'LoadSharedLibrary)\b', re.IGNORECASE
)
FORTRAN_PROC_POINTER = re.compile(
    r'\b(?:ExecSimulationProc|CallProc|CallFunctionPointer|'
    r'call\s+\w+Proc)\b', re.IGNORECASE
)
FORTRAN_ISO_C = re.compile(
    r'\b(?:c_funloc|c_f_procpointer|C_F_PROCPOINTER|C_FUNLOC|'
    r'iso_c_binding)\b', re.IGNORECASE
)

# 废弃标注
DEPRECATED_PATTERN = re.compile(
    r'@(?:deprecated|Deprecated)\b', re.MULTILINE
)
VERSION_PATTERN = re.compile(
    r'\bversion\s*[=:]\s*["\'"]?(\d+\.\d+(?:\.\d+)?)["\'"]?',
    re.MULTILINE | re.IGNORECASE
)

# 统一数据结构
FIELD_DATA_PATTERN = re.compile(
    r'\b(Field|Data|FieldBase|DataContainer|VariableBase)\b',
    re.MULTILINE
)

# 时间同步与步协调
TIME_SYNC_PATTERN = re.compile(
    r'\b(timeStep|time_step|timestep|subCycle|sub_cycle|'
    r'unified.*step|coordinate.*step|sync.*time)\b',
    re.MULTILINE | re.IGNORECASE
)

# 空间映射
SPATIAL_MAP_PATTERN = re.compile(
    r'\b(map|mapping|interpolat|transfer|project)\w*'
    r'\s*(?:field|data|mesh|grid)',
    re.MULTILINE | re.IGNORECASE
)

# 数据格式转换
FORMAT_CONVERT_PATTERN = re.compile(
    r'\b(convert|to_|from_|cast|transform|parse)\w*'
    r'\s*(?:mesh|field|data|format)',
    re.MULTILINE | re.IGNORECASE
)

# 依赖声明
DEPENDENCY_PATTERN = re.compile(
    r'\b(target_link_libraries|find_package|add_dependencies|'
    r'requires|import\s+\w+\.\w+)\b',
    re.MULTILINE
)


def _has_keyword(content: str, keywords: set) -> bool:
    """检查文件内容是否包含任一关键词"""
    lower = content.lower()
    return any(kw.lower() in lower for kw in keywords)


def _count_occurrences(content: str, pattern: re.Pattern) -> int:
    """统计正则匹配次数"""
    return len(pattern.findall(content))


def _grep_files(file_index: FileIndex, ext_filter: set) -> list:
    """过滤指定扩展名的文件"""
    return [f for f in file_index.files if f["ext"] in ext_filter]


class SolverPhysicsMetrics:
    """求解器和物理场模块化架构模式识别评估

    提供 4 维评分和 11 条 MPR 规则的静态分析检测。
    """

    def __init__(self, root: str):
        self.root = root
        self.index = FileIndex(root)
        self.weights = {}
        self._all_contents = {}          # abs_path → content
        self._config_contents = {}       # abs_path → content（OpenFOAM 配置字典等无扩展名配置文件）
        self._solver_dirs = set()        # 识别出的求解器目录名
        self._module_dirs = {}           # 模块名 → 文件列表
        self._is_multiphysics = False
        self._cache = {}                 # 维度结果缓存: name → (score, detail)
        self._sample_ratio = 1.0         # 抽样比例: 扫描文件数/全量源文件数（抽样质量保证）
        self._total_source_count = 0     # 全量源文件数
        self._init_weights()
        self._detect_multiphysics()
        if self._is_multiphysics:
            self._scan_files()
            self._scan_config_dictionaries()

    def _cached(self, name: str, fn):
        """维度结果缓存，避免重复计算（check_mpr_rules 会多次调用 calc_xxx）"""
        if name not in self._cache:
            self._cache[name] = fn()
        return self._cache[name]

    def _any_match(self, pattern: re.Pattern) -> bool:
        """缓存任意文件内容匹配正则的结果，避免重复扫描全部文件"""
        key = f"match:{id(pattern)}"
        if key not in self._cache:
            self._cache[key] = any(pattern.search(c)
                                   for c in self._all_contents.values())
        return self._cache[key]

    def _coupling_convergence_stats(self) -> dict:
        """耦合收敛控制检测（区分单求解器内部收敛 vs 多物理场耦合收敛）

        收敛控制关键词（residual/tolerance/maxIter）在单求解器内部普遍存在
        （FEM 单元残差、线性迭代容差），不属于耦合架构评估范畴。

        区分策略（文件级）：
        - 文件同时含收敛关键词 + 耦合关键词（coupling/fsi/transfer/multi-app/picard）
          → 判定为耦合收敛控制
        - 文件仅含收敛关键词 → 判定为单求解器内部收敛（不计入耦合收敛）

        Returns:
            {"has_coupling_convergence": bool,
             "convergence_hits": int,        # 命中收敛关键词的文件数
             "coupling_ctx_hits": int,       # 同时含耦合关键词的文件数
             "solver_internal_hits": int}    # 仅收敛关键词（单求解器内部）
        """
        if "coupling_convergence" in self._cache:
            return self._cache["coupling_convergence"]
        convergence_hits = 0
        coupling_ctx_hits = 0
        solver_internal_hits = 0
        # 合并源码内容与 OpenFOAM 配置字典（residualControl 属耦合求解收敛控制）
        for content in self._all_contents.values():
            if not CONVERGENCE_PATTERN.search(content):
                continue
            convergence_hits += 1
            if COUPLING_CONTEXT_PATTERN.search(content):
                coupling_ctx_hits += 1
            else:
                solver_internal_hits += 1
        # OpenFOAM 配置字典：residualControl（SIMPLE/PIMPLE/PISO 流-压力耦合收敛）
        # 直接计入耦合收敛，无需耦合上下文关键词（耦合语义隐含于 fvSolution）。
        # residualControl 本身即收敛控制的明确标记，无需再匹配 CONVERGENCE_PATTERN。
        for content in self._config_contents.values():
            if RESIDUAL_CONTROL_PATTERN.search(content):
                convergence_hits += 1
                coupling_ctx_hits += 1
            elif CONVERGENCE_PATTERN.search(content):
                convergence_hits += 1
                if COUPLING_CONTEXT_PATTERN.search(content):
                    coupling_ctx_hits += 1
                else:
                    solver_internal_hits += 1
        result = {
            "has_coupling_convergence": coupling_ctx_hits > 0,
            "convergence_hits": convergence_hits,
            "coupling_ctx_hits": coupling_ctx_hits,
            "solver_internal_hits": solver_internal_hits,
        }
        self._cache["coupling_convergence"] = result
        return result

    def _sum_matches(self, pattern: re.Pattern) -> int:
        """缓存全文件正则匹配总数"""
        key = f"sum:{id(pattern)}"
        if key not in self._cache:
            total = 0
            for c in self._all_contents.values():
                total += len(pattern.findall(c))
            self._cache[key] = total
        return self._cache[key]

    def _sum_matches_extrapolated(self, pattern: re.Pattern) -> int:
        """计数型检测的全量估计（按抽样比例外推）

        抽样只扫描部分文件时，计数型检测（如内部访问数、转换点数）会严重低估。
        通过 1/sample_ratio 外推得到全量估计值。
        返回值附注：detail 中可标注 estimated=True 表示外推值。
        """
        raw = self._sum_matches(pattern)
        if self._sample_ratio and self._sample_ratio < 1.0:
            return int(raw / self._sample_ratio)
        return raw

    def _init_weights(self):
        """从 skill .md 解析权重，仅保留 4 个评估维度的权重"""
        _DIM_KEYS = {"物理场模块边界完整性", "多物理场耦合架构合理性",
                     "插件式扩展架构支持度", "跨场数据传递规范性"}
        try:
            raw = load_weights_from_skill(SKILL_PATH)
            self.weights = {k: v for k, v in raw.items() if k in _DIM_KEYS}
            if len(self.weights) != 4:
                raise ValueError(f"只解析到 {len(self.weights)} 个维度权重")
        except Exception:
            self.weights = {
                "物理场模块边界完整性": 0.25,
                "多物理场耦合架构合理性": 0.30,
                "插件式扩展架构支持度": 0.25,
                "跨场数据传递规范性": 0.20,
            }

    def _is_cpp_file(self, f: dict) -> bool:
        return f["ext"] in CPP_EXTS or f["ext"] in C_EXTS

    def _is_source_file(self, f: dict) -> bool:
        return f["ext"] in ALL_SOLVER_EXTS

    def _is_project_file(self, f: dict) -> bool:
        """判断文件是否属于项目自身（排除第三方依赖目录）

        第三方库（如 UMFPACK）的头文件互引用会被误判为项目模块循环依赖，
        B3.5 验证 ElmerFEM 时发现 31 个循环 100% 来自 umfpack。
        """
        parts = Path(f["path"]).parts
        return not any(p in THIRD_PARTY_DIR_NAMES for p in parts)

    def _is_project_abs_path(self, abs_path: str) -> bool:
        """判断绝对路径是否属于项目自身（排除第三方依赖目录）

        与 _is_project_file 等价，但接收绝对路径（用于 _all_contents 遍历）。
        """
        try:
            rel = os.path.relpath(abs_path, self.root)
        except ValueError:
            return False
        parts = Path(rel).parts
        return not any(p in THIRD_PARTY_DIR_NAMES for p in parts)

    def _detect_fortran_plugin(self) -> dict:
        """检测 Fortran 插件机制（动态加载求解器过程）

        Fortran 项目用过程指针 + 运行时加载（GetProcAddr）实现插件机制，
        而非 C++ 类继承。B3.5 探查 ElmerFEM 发现 GetProcAddr + ExecSimulationProc。

        **语言限定**：仅扫描 Fortran 文件（.f90/.f/.f03/.f08），
        排除 C/C++ 的 GetProcAddr（如 POSIX 系统接口，B3.5 验证 OpenFOAM 误报）。

        判定规则（防误报）：
          ① GetProcAddr 类命中 ≥3 文件 → True（单一机制多次使用，确属插件）
          ② get_proc_addr ≥1 且 proc_pointer ≥1 → True（双特征佐证）
          ③ iso_c ≥1 且 get_proc_addr ≥1 → True（ISO C 互操作佐证）
        """
        if "fortran_plugin" in self._cache:
            return self._cache["fortran_plugin"]
        get_proc = 0
        proc_ptr = 0
        iso_c = 0
        for abs_path, content in self._all_contents.items():
            if not abs_path.lower().endswith((".f90", ".f", ".f03", ".f08", ".f95")):
                continue
            if FORTRAN_GET_PROC_ADDR.search(content):
                get_proc += 1
            if FORTRAN_PROC_POINTER.search(content):
                proc_ptr += 1
            if FORTRAN_ISO_C.search(content):
                iso_c += 1

        if get_proc >= 3:
            has = True
        elif get_proc >= 1 and proc_ptr >= 1:
            has = True
        elif iso_c >= 1 and get_proc >= 1:
            has = True
        else:
            has = False
        result = {"has_fortran_plugin": has, "get_proc_files": get_proc,
                  "proc_pointer_files": proc_ptr, "iso_c_files": iso_c}
        self._cache["fortran_plugin"] = result
        return result

    def _scan_build_config_files(self) -> bool:
        """扫描构建配置文件，返回是否含独立模块编译目标

        判定标准（识别多种构建体系）：
        1. CMakeLists.txt 含 add_subdirectory（模块子目录）
        2. 或同一 CMakeLists.txt 中 ≥2 个 add_library（独立库目标）
        3. Makefile 体系：存在多个模块目录的 Makefile（如 MOOSE modules/*/Makefile），
           或 Makefile 中包含对子模块的引用（MOOSE 的 ALL_MODULES 机制）
        4. 仅单一 add_executable 不视为独立模块（可能为单一应用）

        结果缓存，避免多维度重复扫描。
        """
        if "build_config" in self._cache:
            return self._cache["build_config"]
        found = False
        try:
            cmake_subdirs = 0
            makefile_count = 0
            for dirpath, dirnames, filenames in os.walk(self.root):
                if any(x in dirpath for x in (".git", "__pycache__", ".opencode")):
                    continue
                has_cmake = "CMakeLists.txt" in filenames
                has_make = "Makefile" in filenames or "makefile" in filenames

                if has_cmake:
                    try:
                        content = read_text_smart(os.path.join(dirpath, "CMakeLists.txt"))
                        cmake_subdirs += content.count("add_subdirectory")
                        # add_library 需同一文件内 ≥2 个（同一构建文件定义多个库目标）
                        if content.count("add_library") >= 2:
                            found = True
                            break
                    except Exception:
                        pass

                if has_make:
                    # Makefile 体系：统计存在 Makefile 的子目录数（每个独立编译目标）
                    makefile_count += 1
                    try:
                        content = read_text_smart(os.path.join(dirpath, "Makefile"))
                        # MOOSE 风格：模块根 Makefile 引用 ALL_MODULES 子模块
                        if ("modules" in content.lower()
                                or "APPLICATION_NAME" in content
                                or "libmesh" in content):
                            # 该 Makefile 属于多模块应用构建，标记为独立目标
                            makefile_count += 2
                    except Exception:
                        pass

                if cmake_subdirs >= 1:
                    found = True
                    break

            # Makefile 体系：≥2 个子目录有 Makefile（对应多个独立编译目标）
            if not found and makefile_count >= 2:
                found = True
        except Exception:
            pass
        self._cache["build_config"] = found
        return found

    def _detect_multiphysics(self):
        """检测项目是否为多物理场项目

        判定条件（满足任一）：
        1. 目录名含 ≥ 2 种物理场关键字（structural/thermal/fluid 等）
        2. 源代码含 "multiphysics" / "FSI" 等关键词（仅扫描 .py/.cpp/.c/.h/.f90 等源码）
        3. 引用耦合框架（preCICE、Kratos、MOOSE 等）
        """
        _source_exts = ALL_SOLVER_EXTS
        # 排除工具自身目录（自测时避免误检）
        _excl_dirs_lower = {os.path.normpath(p).lower()
                            for p in [os.path.join(self.root, "src", "arch_quality"),
                                      os.path.join(self.root, "src", "arch_quality", "skills"),
                                      os.path.join(self.root, "scripts"),
                                      os.path.join(self.root, "tests"),
                                      os.path.join(self.root, ".opencode")]}
        _source_files = []
        for f in self.index.files:
            if f["ext"] not in _source_exts:
                continue
            fdir = os.path.dirname(os.path.normpath(f["abs_path"])).lower()
            if any(fdir.startswith(sd) for sd in _excl_dirs_lower):
                continue
            _source_files.append(f)

        # 条件 1：目录名检测（仅检测源码目录，排除 docs/）
        found_dirs = set()
        for f in _source_files:
            parts = Path(f["path"]).parts
            for part in parts:
                part_lower = part.lower()
                for kw in MULTIPHYSICS_DIR_KEYWORDS:
                    if kw in part_lower:
                        found_dirs.add(kw)
                        self._solver_dirs.add(part)

        dir_hit = len(found_dirs) >= 2

        # 条件 2：源码关键词检测（仅扫描源代码文件，排除 .md/.txt 文档）
        file_hit = False
        for f in _source_files[:200]:
            try:
                content = read_text_smart(f["abs_path"])
                if _has_keyword(content, {"multiphysics", "multi_physics", "fsi",
                                          "fluid_structure", "co_simulation"}):
                    file_hit = True
                    break
            except Exception:
                continue

        # 条件 3：耦合框架引用（仅检测源文件内容 + 源码目录名）
        framework_hit = False
        for f in _source_files:
            for fw in COUPLING_FRAMEWORKS:
                if fw in f["path"].lower():
                    framework_hit = True
                    break
            if framework_hit:
                break
        if not framework_hit:
            for f in _source_files[:100]:
                try:
                    content = read_text_smart(f["abs_path"])
                    if _has_keyword(content, COUPLING_FRAMEWORKS):
                        framework_hit = True
                        break
                except Exception:
                    continue

        self._is_multiphysics = dir_hit or file_hit or framework_hit

        # 求解器模块目录回填（B3.5 FreeFEM 探查修复）：
        # FreeFEM 等用功能名命名求解器模块（src/fflib、src/femlib、src/bamg），
        # 不含物理场关键词（structural/thermal/fluid），导致 _solver_dirs 为空、
        # independent_units 漏检。当项目判为多物理场但目录检测未命中时，
        # 补充识别项目自身 src/ 下的二级代码子目录作为求解器模块目录。
        if self._is_multiphysics and not self._solver_dirs:
            for dirpath, dirnames, filenames in os.walk(self.root):
                # 排除第三方依赖目录（3rdparty/dissection/src 等）
                if any(p in THIRD_PARTY_DIR_NAMES for p in Path(dirpath).parts):
                    dirnames[:] = []
                    continue
                parts = Path(dirpath).parts
                if len(parts) < 2:
                    continue
                parent = parts[-2].lower()
                if parent == "src":
                    n_src = sum(1 for fn in filenames
                                if os.path.splitext(fn)[1].lower() in ALL_SOLVER_EXTS)
                    if n_src >= 2:
                        self._solver_dirs.add(parts[-1])

    def _scan_files(self):
        """预读求解器相关文件内容

        为控制大型项目（>5000 文件）的扫描耗时，最多读取
        _MAX_SCAN_FILES 个文件，按模块均匀抽样。
        """
        _MAX_SCAN_FILES = 2000
        source_files = [f for f in self.index.files if self._is_source_file(f)]
        total = len(source_files)
        self._total_source_count = total

        # 按模块分组后均匀抽样，保证各模块都有代表性文件被扫描
        if total > _MAX_SCAN_FILES:
            by_mod = {}
            for f in source_files:
                p = Path(f["path"])
                mod = p.parts[0] if len(p.parts) >= 1 else "."
                by_mod.setdefault(mod, []).append(f)
            per_mod = max(1, _MAX_SCAN_FILES // len(by_mod))
            sampled = []
            for mod_files in by_mod.values():
                sampled.extend(mod_files[:per_mod])
            source_files = sampled

        self._sample_ratio = len(source_files) / max(1, total)

        for f in source_files:
            try:
                content = read_text_smart(f["abs_path"])
                self._all_contents[f["abs_path"]] = content
            except Exception:
                pass

        # 构建模块目录映射：优先使用识别出的求解器目录（src/structural 等），
        # 否则按第一级目录分组
        if self._solver_dirs:
            for f in self.index.files:
                p = Path(f["path"])
                matched = None
                for part in p.parts[:-1]:
                    if part in self._solver_dirs:
                        matched = part
                        break
                if matched is None:
                    matched = p.parts[0] if len(p.parts) >= 1 else "."
                if matched not in self._module_dirs:
                    self._module_dirs[matched] = []
                self._module_dirs[matched].append(f)
        else:
            for f in self.index.files:
                p = Path(f["path"])
                if len(p.parts) >= 2:
                    mod = p.parts[0]
                else:
                    mod = "."
                if mod not in self._module_dirs:
                    self._module_dirs[mod] = []
                self._module_dirs[mod].append(f)

    def _scan_config_dictionaries(self):
        """扫描 OpenFOAM 配置字典（无源码扩展名的收敛控制配置）

        OpenFOAM 的耦合收敛控制（residualControl）写在 system/fvSolution、
        controlDict 等字典文件中（无 .h/.cpp 扩展名），FileIndex 会排除它们，
        导致 MPR-006 误报"缺少收敛控制参数"（B3.5 已知边界 3）。

        仅纳入 `_config_contents` 供收敛检测使用，不参与模块/文件计数，
        避免污染其他指标。配置字典中的 residualControl 属耦合求解算法
        （SIMPLE/PIMPLE/PISO）的收敛控制，应计入耦合收敛稳定性。
        """
        if self._config_contents:
            return
        config_names = {"fvSolution", "controlDict", "fvSchemes", "fvOptions"}
        for dirpath, dirnames, filenames in os.walk(self.root):
            for fn in filenames:
                if fn in config_names:
                    abs_path = os.path.join(dirpath, fn)
                    try:
                        content = read_text_smart(abs_path)
                        if content.strip():
                            self._config_contents[abs_path] = content
                    except Exception:
                        pass

    # ── 维度 1：物理场模块边界完整性（25%）──

    def calc_boundary_integrity(self) -> tuple:
        """2.1 物理场模块边界完整性 (25%)

        5 个子项 + 1 项 FMI 加分。
        """
        return self._cached("boundary_integrity", self._calc_boundary_integrity_impl)

    def _calc_boundary_integrity_impl(self) -> tuple:
        if not self._is_multiphysics:
            return None, {}

        score = 0
        detail = {}

        # ── 子项 1：独立编译单元检测（20 分）──
        has_independent_units = False
        if len(self._module_dirs) >= 2:
            has_build_files = self._scan_build_config_files()
            has_independent_units = has_build_files and len(self._solver_dirs) >= 2

        s1 = 20 if has_independent_units else 0
        score += s1
        detail["independent_units"] = {"score": s1, "has_independent": has_independent_units}

        # ── 子项 2：公开 API 精简度（20 分）──
        total_api = 0
        module_count = 0
        for mod, files in self._module_dirs.items():
            for f in files:
                if f["ext"] in (".h", ".hpp"):
                    # 仅统计已缓存的头文件（受 _MAX_SCAN_FILES 抽样限制），
                    # 避免读取全部头文件导致大型项目扫描过慢
                    content = self._all_contents.get(f["abs_path"], "")
                    if not content:
                        continue
                    try:
                        funcs = re.findall(
                            r'(?:virtual\s+)?(?:void|int|double|float|bool|'
                            r'std::\w+(?:<[^>]*>)?|const\s+\w+(?:\s*&)?)\s+'
                            r'(\w+)\s*\(',
                            content
                        )
                        total_api += len(funcs)
                        module_count += 1
                    except Exception:
                        pass

        avg_api = total_api / max(1, module_count)
        if avg_api <= 50:
            s2 = 20
        elif avg_api <= 100:
            s2 = 10
        else:
            s2 = 5
        score += s2
        detail["api_compactness"] = {"score": s2, "avg_api_count": round(avg_api, 1)}

        # ── 子项 3：MMS 验证基准存在性（30 分）──
        mms_modules = set()
        abs_to_mod = {}
        for mod, files in self._module_dirs.items():
            for f in files:
                abs_to_mod[f["abs_path"]] = mod
        for abs_path, content in self._all_contents.items():
            if MMS_PATTERN.search(content):
                mod = abs_to_mod.get(abs_path)
                if mod:
                    mms_modules.add(mod)

        # 目录级检测
        mms_dirs = []
        try:
            for dirpath, dirnames, _ in os.walk(self.root):
                depth = dirpath.replace(self.root, "").count(os.sep)
                if depth > 8:
                    continue
                for d in dirnames:
                    if any(kw in d.lower() for kw in MMS_DIR_KEYWORDS):
                        mms_dirs.append(os.path.join(dirpath, d))
        except Exception:
            pass

        all_mods = set(self._module_dirs.keys())
        mms_coverage = len(mms_modules) / max(1, len(all_mods))
        if mms_coverage >= 0.8 or len(mms_dirs) >= 2:
            s3 = 30
        elif mms_coverage > 0 or mms_dirs:
            s3 = 15
        else:
            s3 = 0
        score += s3
        detail["mms_readiness"] = {"score": s3, "modules_with_mms": len(mms_modules),
                                   "mms_dirs": len(mms_dirs),
                                   "coverage": round(mms_coverage, 2)}

        # ── 子项 4：内部数据结构封装性（30 分）──
        # 抽样质量保证：计数型检测按抽样比例外推，避免抽样低估导致得分虚高
        internal_access_count = self._sum_matches_extrapolated(DIRECT_MEMBER_ACCESS)
        internal_access_count += self._sum_matches_extrapolated(INTERNAL_ACCESS_PATTERN)
        detail["_sampled"] = {"sample_ratio": self._sample_ratio,
                              "estimated": self._sample_ratio < 1.0}

        if internal_access_count == 0:
            s4 = 30
        elif internal_access_count <= 3:
            s4 = 20
        elif internal_access_count <= 10:
            s4 = 10
        else:
            s4 = 0
        score += s4
        detail["encapsulation"] = {"score": s4,
                                   "internal_access_count": internal_access_count}

        # ── 子项 5：FMI 模型交换模式加分（+10）──
        has_fmi = self._any_match(FMI_FUNCTIONS_PATTERN)
        if has_fmi:
            fmi_bonus = 10
            score = min(score + fmi_bonus, 110)
        else:
            fmi_bonus = 0
        detail["fmi_support"] = {"bonus": fmi_bonus, "has_fmi": has_fmi}

        final_score = min(score, 100)
        detail["score"] = final_score
        return final_score, detail

    # ── 维度 2：多物理场耦合架构合理性（30%）──

    def calc_coupling_architecture(self) -> tuple:
        """2.2 多物理场耦合架构合理性 (30%)

        6 个子项评分。
        """
        return self._cached("coupling_architecture", self._calc_coupling_architecture_impl)

    def _calc_coupling_architecture_impl(self) -> tuple:
        if not self._is_multiphysics:
            return None, {}

        score = 0
        detail = {}

        # ── 子项 1：耦合架构与耦合强度匹配度（20 分）──
        coupling_strength = self._judge_coupling_strength()
        arch_type = self._detect_coupling_architecture()
        matches = self._matches_architecture(coupling_strength, arch_type)

        s1 = 20 if matches else (10 if coupling_strength != "unknown" else 0)
        score += s1
        detail["architecture_match"] = {"score": s1,
                                        "coupling_strength": coupling_strength,
                                        "architecture_type": arch_type,
                                        "matches": matches}

        # ── 子项 2：耦合逻辑集中度（20 分）──
        coupling_files = self._find_coupling_files()
        total_source = max(1, len([f for f in self.index.files
                                   if self._is_source_file(f)]))
        # 抽样质量保证：耦合文件数按抽样比例外推，分母用全量源文件数
        coupling_file_count = len(coupling_files)
        if self._sample_ratio and self._sample_ratio < 1.0:
            coupling_file_count = int(coupling_file_count / self._sample_ratio)
        coupling_ratio = coupling_file_count / total_source

        if coupling_ratio < 0.1 and coupling_file_count >= 1:
            s2 = 20
        elif coupling_ratio < 0.3:
            s2 = 10
        else:
            s2 = 0
        score += s2
        detail["coupling_concentration"] = {"score": s2,
                                            "coupling_file_count": coupling_file_count,
                                            "coupling_files_sampled": len(coupling_files),
                                            "coupling_ratio": round(coupling_ratio, 3)}

        # ── 子项 3：求解算法可替换性（15 分）──
        has_abstract = self._any_match(ABSTRACT_SOLVER_PATTERN)
        has_virtual = self._any_match(VIRTUAL_SOLVE_PATTERN)

        s3 = 15 if has_abstract else (10 if has_virtual else 0)
        score += s3
        detail["solver_replaceability"] = {"score": s3,
                                           "has_abstract_solver": has_abstract,
                                           "has_virtual_solve": has_virtual}

        # ── 子项 4：迭代收敛稳定性（15 分）──
        # 区分"耦合层收敛控制"与"单求解器内部收敛"（FEM 残差/线性迭代容差）
        conv_stats = self._coupling_convergence_stats()
        has_coupling_convergence = conv_stats["has_coupling_convergence"]
        if has_coupling_convergence:
            s4 = 15
        elif conv_stats["convergence_hits"] > 0:
            # 仅有单求解器内部收敛控制（非耦合层），给部分分
            s4 = 5
        else:
            s4 = 0
        score += s4
        detail["convergence_stability"] = {
            "score": s4,
            "has_convergence_control": has_coupling_convergence,
            "has_coupling_convergence": has_coupling_convergence,
            "convergence_hits": conv_stats["convergence_hits"],
            "coupling_ctx_hits": conv_stats["coupling_ctx_hits"],
            "solver_internal_hits": conv_stats["solver_internal_hits"],
        }

        # ── 子项 5：标准耦合接口支持度（15 分）──
        has_fmi_coupling = self._any_match(FMI_FUNCTIONS_PATTERN)
        s5 = 15 if has_fmi_coupling else 0
        score += s5
        detail["standard_coupling_interface"] = {"score": s5,
                                                 "has_fmi_coupling": has_fmi_coupling}

        # ── 子项 6：系统层级验证完整性（15 分）──
        has_vandv = self._any_match(V_AND_V_PATTERN)
        s6 = 15 if has_vandv else 0
        score += s6
        detail["system_verification"] = {"score": s6, "has_system_vv": has_vandv}

        final_score = min(score, 100)
        detail["score"] = final_score
        return final_score, detail

    def _judge_coupling_strength(self) -> str:
        """判断耦合强度（strong/medium/weak）

        基于 4 维度投票：
        1. 数据交换频率 — 每时间步多次 vs 一次
        2. 数据交换方向 — 双向 vs 单向
        3. 收敛反馈效应 — 内迭代 vs 顺序执行
        4. 耦合矩阵结构 — 全局非对称 Jacobian vs 显式传递

        结果缓存，避免重复扫描全部文件。
        """
        if "coupling_strength" in self._cache:
            return self._cache["coupling_strength"]
        strong_votes = 0
        weak_votes = 0

        for content in self._all_contents.values():
            # 内迭代检测（转义 . 避免误匹配 fixed-point/fixed point，补下划线变体）
            # 注意：fixed_point（Picard 定点迭代）属于 partitioned_iterative 架构，
            # 不计入强耦合投票，避免与架构判定重复/矛盾
            inner_iter = bool(re.search(
                r'(?:while|for)\s*\([^)]*[0-9]+\s*<[^)]*\w*[Cc]oupling\w*|'
                r'[Ss]taggered|strong[_ -]?coupling|inner[_ -]?iter\b',
                content
            ))
            if inner_iter:
                strong_votes += 1

            # 双向数据交换检测（要求交换语义 + 双向标记，
            # 排除 MPI 并行基础设施如 "sends both"/"received buffers. Works with both"）
            bi_dir = bool(re.search(
                r'(?:exchange|transfer|coupl(?:e|ing))[^;\n]{0,60}'
                r'(?:both|two[- ]way|bi[- ]directional|mutual|reciprocal)',
                content, re.IGNORECASE
            ))
            if bi_dir:
                strong_votes += 1

            # 非对称矩阵检测
            asym = bool(re.search(
                r'(?:asymmetric|non[- ]symmetric|unsymmetric)\s*(?:matrix|jacobian|system)',
                content, re.IGNORECASE
            ))
            if asym:
                strong_votes += 1

            # 单向耦合检测（要求明确耦合语义，排除自然语言 "one way"）
            one_way = bool(re.search(
                r'one[- ]way.{0,30}coupl|uni[- ]directional.{0,30}coupl|'
                r'sequential.{0,20}coupl|loose.{0,20}coupl',
                content, re.IGNORECASE
            ))
            if one_way:
                weak_votes += 1

            # 单次交换检测（要求耦合/数据交换语义，排除 MPI 通信注释）
            single_exchange = bool(re.search(
                r'(?:once|single)[^;\n]{0,40}(?:exchange|transfer).{0,20}(?:field|data|coupl)'
                r'|(?:exchange|transfer)[^;\n]{0,40}once',
                content, re.IGNORECASE
            ))
            if single_exchange:
                weak_votes += 1

        if strong_votes > weak_votes:
            result = "strong"
        elif weak_votes > strong_votes:
            result = "weak"
        elif strong_votes > 0:
            result = "medium"
        else:
            result = "unknown"
        self._cache["coupling_strength"] = result
        return result

    def _detect_coupling_architecture(self) -> str:
        """检测耦合架构类型（结果缓存）

        注意：正则需精确匹配架构模式，避免误匹配注释/标识符。
        例：'file.*based' 过宽（匹配 'file-names based'），改为明确耦合语义。

        **多模式库处理**（B3.5 preCICE 探查）：
        通用耦合库（如 preCICE）同时支持 explicit（loose）与 implicit/iterative
        两种耦合方案。explicit 常出现于接口文档（"supports explicit coupling"），
        不代表架构选择。用"两阶段信号检测"避免遍历顺序依赖：
        1. 先全量扫描高置信度核心求解语义词（staggered/fixed_point/picard/
           iterative coupling/monolithic）→ 判对应架构
        2. 无核心语义时才扫描 low-confidence 的 explicit/loose → partitioned_loose
        这样 preCICE 的 staggered（SerialCouplingScheme 核心注释）优先于
        explicit（BaseCouplingScheme 接口文档）被识别。
        """
        if "coupling_architecture_type" in self._cache:
            return self._cache["coupling_architecture_type"]

        def _scan(pat):
            for content in self._all_contents.values():
                if pat.search(content):
                    return True
            return False

        # 第 1 阶段：高置信度核心求解语义（跨全部文件，独立于遍历顺序）
        if _scan(re.compile(r'\bmonolithic\b|monolith\b', re.IGNORECASE)):
            result = "monolithic"
        elif _scan(re.compile(
                r'\b(partitioned.{0,20}iterative|iterative.{0,20}coupling|'
                r'staggered|fixed[_ -]?point|picard)\b', re.IGNORECASE)):
            result = "partitioned_iterative"
        # 第 2 阶段：低置信度 loose/explicit（可选弱耦合模式）
        elif _scan(re.compile(
                r'\b(partitioned.{0,20}loose|loose.{0,20}coupling|'
                r'explicit.{0,20}coupling)\b', re.IGNORECASE)):
            result = "partitioned_loose"
        elif _scan(re.compile(
                r'\b(fully[- ]loose|file[- ]based.{0,20}coupl|'
                r'external.{0,20}coupl)\b', re.IGNORECASE)):
            result = "fully_loose"
        else:
            result = "unknown"
        self._cache["coupling_architecture_type"] = result
        return result

    def _matches_architecture(self, strength: str, arch: str) -> bool:
        """判断耦合架构是否与强度匹配"""
        if strength == "strong" and arch in ("monolithic", "partitioned_iterative"):
            return True
        if strength == "weak" and arch in ("partitioned_loose", "fully_loose"):
            return True
        if strength == "medium" and arch in ("partitioned_iterative",
                                              "partitioned_loose"):
            return True
        return False

    def _find_coupling_files(self) -> list:
        """查找耦合相关文件（仅扫描已缓存内容，受抽样限制）"""
        coupling_files = []
        for abs_path, content in self._all_contents.items():
            path_lower = os.path.basename(abs_path).lower()
            if any(kw in path_lower for kw in ("coupling", "fsi", "interface",
                                                "cosimulation", "co_simulation")):
                coupling_files.append(abs_path)
                continue
            if _has_keyword(content, {"coupling", "fsi", "interface",
                                       "transfer", "exchange"}):
                coupling_files.append(abs_path)
        return coupling_files

    # ── 维度 3：插件式扩展架构支持度（25%）──

    def calc_extension_support(self) -> tuple:
        """2.3 插件式扩展架构支持度 (25%)

        4 个子项 + 递进扣分。
        """
        return self._cached("extension_support", self._calc_extension_support_impl)

    def _calc_extension_support_impl(self) -> tuple:
        if not self._is_multiphysics:
            return None, {}

        score = 0
        detail = {}

        # ── 子项 1：标准接口动态加载（30 分）──
        has_plugin = self._any_match(PLUGIN_PATTERN)
        has_interface = self._any_match(UNIFIED_INTERFACE_PATTERN)
        # Fortran 插件机制：作为 C++ 统一接口的等价替代（不叠加）
        # Fortran 项目用过程指针动态加载（GetProcAddr），无 C++ 类继承
        fp = self._detect_fortran_plugin()
        has_fortran_plugin = fp["has_fortran_plugin"]
        has_effective_interface = has_interface or has_fortran_plugin

        s1 = 30 if (has_plugin and has_effective_interface) else (15 if has_plugin else 0)
        score += s1
        detail["dynamic_loading"] = {"score": s1, "has_plugin": has_plugin,
                                     "has_unified_interface": has_interface,
                                     "has_fortran_plugin": has_fortran_plugin}

        # ── 子项 2：依赖关系形式化（25 分）──
        has_dep_decl = self._any_match(DEPENDENCY_PATTERN)
        if not has_dep_decl:
            has_dep_decl = self._scan_build_config_files()
        s2 = 25 if has_dep_decl else 0
        score += s2
        detail["dependency_formalization"] = {"score": s2,
                                              "has_dependency_decl": has_dep_decl}

        # ── 子项 3：无循环依赖（25 分）──
        graph = DepGraph()
        node_by_basename = defaultdict(list)
        # 仅使用项目自身文件（排除第三方依赖目录，如 umfpack）
        project_files = [f for f in self.index.files if self._is_project_file(f)]
        for f in project_files:
            graph.add_node(f["path"], f["lang"])
            node_by_basename[os.path.basename(f["path"])].append(f["path"])
        for abs_path, content in self._all_contents.items():
            for f in project_files:
                if f["abs_path"] == abs_path:
                    node_id = f["path"]
                    break
            else:
                continue
            for m in re.finditer(r'#include\s+[<"](.+?)[>"]', content):
                inc_base = os.path.basename(m.group(1))
                candidates = node_by_basename.get(inc_base, [])
                for target in candidates:
                    if target != node_id:
                        graph.add_edge(node_id, target)
                        break
            for m in re.finditer(r'from\s+(\S+)\s+import', content):
                import_base = m.group(1).split(".")[0]
                candidates = node_by_basename.get(import_base, [])
                for target in candidates:
                    if target != node_id:
                        graph.add_edge(node_id, target)
                        break

        cycles = graph.detect_same_lang_cycles()
        if len(cycles) == 0:
            s3 = 25
        elif len(cycles) <= 2:
            s3 = 10
        else:
            s3 = 0
        score += s3
        detail["no_cycles"] = {"score": s3, "cycle_count": len(cycles)}

        # ── 子项 4：接口版本管理（20 分）──
        has_deprecated = self._any_match(DEPRECATED_PATTERN)
        has_version = self._any_match(VERSION_PATTERN)
        if has_deprecated and has_version:
            s4 = 20
        elif has_version:
            s4 = 10
        else:
            s4 = 0
        score += s4
        detail["version_management"] = {"score": s4, "has_deprecated": has_deprecated,
                                        "has_versioning": has_version}

        # ── 递进扣分 ──
        bound_score, _ = self.calc_boundary_integrity()
        if bound_score is not None and bound_score < 60:
            deduction_applied = True
            original = score
            score = int(score * 0.5)
            detail["progressive_deduction"] = {
                "applied": True,
                "original_score": original,
                "deducted_score": score,
                "reason": "边界完整性得分 < 60，扩展架构得分自动折半",
            }
        else:
            detail["progressive_deduction"] = {"applied": False}

        final_score = min(score, 100)
        detail["score"] = final_score
        return final_score, detail

    # ── 维度 4：跨场数据传递规范性（20%）──

    def calc_data_transfer(self) -> tuple:
        """2.4 跨场数据传递规范性 (20%)

        6 个子项 + FMI 合规加分。
        """
        return self._cached("data_transfer", self._calc_data_transfer_impl)

    def _calc_data_transfer_impl(self) -> tuple:
        if not self._is_multiphysics:
            return None, {}

        score = 0
        detail = {}

        # ── 子项 1：标准化数据结构（20 分）──
        has_field_data = self._any_match(FIELD_DATA_PATTERN)
        s1 = 20 if has_field_data else 0
        score += s1
        detail["standardized_data_structure"] = {"score": s1,
                                                  "has_field_data": has_field_data}

        # ── 子项 2：FMI 协同仿真数据传递（15 分）──
        has_fmi_co_sim = self._any_match(FMI_FUNCTIONS_PATTERN)
        s2 = 15 if has_fmi_co_sim else 0
        score += s2
        detail["fmi_co_simulation"] = {"score": s2, "has_fmi_co_sim": has_fmi_co_sim}

        # ── 子项 3：数据格式转换统一性（20 分）──
        convert_sites = []
        for abs_path, content in self._all_contents.items():
            # 排除第三方依赖目录（如 vexcl/pybind11 的 transform 词误命中）
            if not self._is_project_abs_path(abs_path):
                continue
            count = len(FORMAT_CONVERT_PATTERN.findall(content))
            if count > 0:
                convert_sites.append((abs_path, count))

        # 抽样质量保证：转换站点数按抽样比例外推
        convert_site_count = len(convert_sites)
        if self._sample_ratio and self._sample_ratio < 1.0:
            convert_site_count = int(convert_site_count / self._sample_ratio)

        if convert_site_count <= 1:
            s3 = 20
        elif convert_site_count <= 3:
            s3 = 10
        else:
            s3 = 0
        score += s3
        detail["format_conversion"] = {"score": s3,
                                       "convert_site_count": convert_site_count,
                                       "convert_sites_sampled": len(convert_sites)}

        # ── 子项 4：时间同步机制规范性（15 分）──
        has_time_sync = self._any_match(TIME_SYNC_PATTERN)
        s4 = 15 if has_time_sync else 0
        score += s4
        detail["time_synchronization"] = {"score": s4, "has_time_sync": has_time_sync}

        # ── 子项 5：空间映射架构独立性（15 分）──
        has_spatial_map = self._any_match(SPATIAL_MAP_PATTERN)
        s5 = 15 if has_spatial_map else 0
        score += s5
        detail["spatial_mapping"] = {"score": s5, "has_spatial_map": has_spatial_map}

        # ── 子项 6：时间步协调策略合理性（15 分）──
        _TIME_COORD_PATTERN = re.compile(
            r'(sub.cycle|adapt.*step|multi.*rate|coordinate.*time|sync.*step)',
            re.IGNORECASE
        )
        has_time_coord = self._any_match(_TIME_COORD_PATTERN)
        s6 = 15 if has_time_coord else 0
        score += s6
        detail["time_step_coordination"] = {"score": s6,
                                            "has_time_coord": has_time_coord}

        # ── FMI 合规加分（最多 +5）──
        fmi_bonus = self._check_fmi_compliance()
        score = min(score + fmi_bonus, 105)
        detail["fmi_compliance_bonus"] = {"bonus": fmi_bonus}

        final_score = min(score, 100)
        detail["score"] = final_score
        return final_score, detail

    def _check_fmi_compliance(self) -> int:
        """FMI 合规性检查：+2 +2 +1 = 最多 +5"""
        bonus = 0
        for content in self._all_contents.values():
            if FMU_XML_PATTERN.search(content):
                bonus += 2
                break

        fmi_funcs = set()
        for content in self._all_contents.values():
            for m in FMI_FUNCTIONS_PATTERN.finditer(content):
                fmi_funcs.add(m.group(1))
        required = {"fmi2DoStep", "fmi2GetReal", "fmi2SetReal"}
        if required.intersection(fmi_funcs):
            bonus += 2

        return min(bonus, 5)
    # ── 综合评分 ──

    def calc_overall(self) -> float:
        """4 维度加权平均"""
        dims = [
            (self.calc_boundary_integrity(), self.weights.get("物理场模块边界完整性", 0.25)),
            (self.calc_coupling_architecture(), self.weights.get("多物理场耦合架构合理性", 0.30)),
            (self.calc_extension_support(), self.weights.get("插件式扩展架构支持度", 0.25)),
            (self.calc_data_transfer(), self.weights.get("跨场数据传递规范性", 0.20)),
        ]
        total_weight = 0
        weighted_sum = 0
        for (score, _), weight in dims:
            if score is not None:
                weighted_sum += score * weight
                total_weight += weight
        return round(weighted_sum / max(total_weight, 0.01), 2) if total_weight > 0 else 0.0

    # ── MPR 规则检查 ──

    def check_mpr_rules(self) -> list:
        """执行全部 11 条 MPR 规则检测"""
        if not self._is_multiphysics:
            return []

        results = []
        d1, d1d = self.calc_boundary_integrity() or (0, {})
        d2, d2d = self.calc_coupling_architecture() or (0, {})

        # MPR-001: 物理场模块边界识别
        if not d1d.get("independent_units", {}).get("has_independent", True):
            results.append({
                "rule": "MPR-001", "name": "物理场模块边界识别",
                "severity": "HIGH", "output_level": "ERROR",
                "count": 1,
                "detail": "多个物理场求解器未以独立编译单元形式存在",
            })

        # MPR-002: 模块公开接口精简度
        avg_api = d1d.get("api_compactness", {}).get("avg_api_count", 0)
        if avg_api > 50:
            results.append({
                "rule": "MPR-002", "name": "模块公开接口精简度",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": int(avg_api),
                "detail": f"模块平均公开 API 数量 {avg_api:.1f}，超过 50 阈值",
            })

        # MPR-003: 模块数值验证基准完备性
        mms_cov = d1d.get("mms_readiness", {}).get("coverage", 0)
        if mms_cov == 0:
            results.append({
                "rule": "MPR-003", "name": "模块数值验证基准完备性",
                "severity": "HIGH", "output_level": "ERROR",
                "count": 1,
                "detail": "未检测到 MMS 验证文件，各模块缺乏独立数值验证基准",
            })

        # MPR-004: 耦合架构模式判定
        arch_match = d2d.get("architecture_match", {})
        if arch_match.get("coupling_strength") != "unknown" and not arch_match.get("matches", True):
            results.append({
                "rule": "MPR-004", "name": "耦合架构模式判定",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": 1,
                "detail": (f"耦合强度为 {arch_match.get('coupling_strength')}，"
                           f"架构类型为 {arch_match.get('architecture_type')}，"
                           f"两者不匹配，需人工确认"),
            })

        # MPR-005: 耦合逻辑集中度
        coupling_ratio = d2d.get("coupling_concentration", {}).get("coupling_ratio", 0)
        if coupling_ratio > 0.3:
            coupling_count = d2d.get("coupling_concentration", {}).get("coupling_file_count", 0)
            results.append({
                "rule": "MPR-005", "name": "耦合逻辑集中度",
                "severity": "HIGH", "output_level": "WARNING",
                "count": coupling_count,
                "detail": f"耦合逻辑散布在 {coupling_count} 个文件中，占比 {coupling_ratio:.1%}",
                "cross_dimension": {"coupling_architecture": 0.5, "data_transfer": 0.5},
            })

        # MPR-006: 迭代收敛稳定性与误差累积
        if not d2d.get("convergence_stability", {}).get("has_convergence_control", False):
            max_iter = 0
            lowest_prec = 1.0
            for content in self._all_contents.values():
                for m in ITERATION_LIMIT_PATTERN.finditer(content):
                    try:
                        max_iter = max(max_iter, int(m.group(2)))
                    except ValueError:
                        pass
            has_risk = max_iter > 100
            results.append({
                "rule": "MPR-006", "name": "迭代收敛稳定性与误差累积",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": 1,
                "detail": ("缺少收敛控制参数" + (
                    f"，且最大迭代次数 {max_iter} > 100 存在误差累积风险" if has_risk else "")),
            })

        # MPR-007: 插件扩展完整性
        ext_detail = (self.calc_extension_support() or ({}, {}))[1]
        dyn_load = ext_detail.get("dynamic_loading", {})
        if not dyn_load.get("has_plugin", True):
            results.append({
                "rule": "MPR-007", "name": "插件扩展完整性",
                "severity": "HIGH", "output_level": "WARNING",
                "count": 1,
                "detail": "未检测到统一插件注册机制或接口定义",
            })

        # MPR-008: 跨模块依赖关系
        cycle_count = ext_detail.get("no_cycles", {}).get("cycle_count", 0)
        if cycle_count > 0:
            results.append({
                "rule": "MPR-008", "name": "跨模块依赖关系",
                "severity": "MEDIUM", "output_level": "ERROR",
                "count": cycle_count,
                "detail": f"模块依赖图中发现 {cycle_count} 个循环依赖",
            })

        # MPR-009: 接口版本管理
        ver_mgmt = ext_detail.get("version_management", {})
        has_ver = ver_mgmt.get("has_versioning", False)
        has_dep = ver_mgmt.get("has_deprecated", False)
        if not has_ver or not has_dep:
            results.append({
                "rule": "MPR-009", "name": "接口版本管理",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": 1,
                "detail": (f"{'未检测到版本号规范; ' if not has_ver else ''}"
                           f"{'未检测到 @deprecated 注解' if not has_dep else ''}"),
            })

        # MPR-010: 跨场数据传递标准化
        dt_detail = (self.calc_data_transfer() or ({}, {}))[1]
        if not dt_detail.get("standardized_data_structure", {}).get("has_field_data", True):
            results.append({
                "rule": "MPR-010", "name": "跨场数据传递标准化",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": 1,
                "detail": "未检测到统一 Field/Data 数据结构，各模块可能使用自定义数据格式",
            })

        # MPR-012: 数据格式转换统一性
        convert_count = dt_detail.get("format_conversion", {}).get("convert_site_count", 0)
        if convert_count > 3:
            results.append({
                "rule": "MPR-012", "name": "数据格式转换统一性",
                "severity": "LOW", "output_level": "INFO",
                "count": convert_count,
                "detail": f"数据格式转换函数分散在 {convert_count} 个位置，建议集中管理",
            })

        return results

    def all_metrics(self) -> dict:
        """返回完整的 4 维评分 + MPR 规则检查结果"""
        if not self._is_multiphysics:
            return {
                "overall": None,
                "is_multiphysics": False,
                "dimensions": {
                    "boundary_integrity": {"score": None, "detail": {}},
                    "coupling_architecture": {"score": None, "detail": {}},
                    "extension_support": {"score": None, "detail": {}},
                    "data_transfer": {"score": None, "detail": {}},
                },
                "mpr_violations": [],
            }

        dim1, d1 = self.calc_boundary_integrity()
        dim2, d2 = self.calc_coupling_architecture()
        dim3, d3 = self.calc_extension_support()
        dim4, d4 = self.calc_data_transfer()

        weights_order = [
            self.weights.get("物理场模块边界完整性", 0.25),
            self.weights.get("多物理场耦合架构合理性", 0.30),
            self.weights.get("插件式扩展架构支持度", 0.25),
            self.weights.get("跨场数据传递规范性", 0.20),
        ]
        scores = [dim1 or 0, dim2 or 0, dim3 or 0, dim4 or 0]
        total_w = sum(weights_order)
        overall = sum(s * w for s, w in zip(scores, weights_order)) / max(total_w, 0.01)

        mpr = self.check_mpr_rules()

        return {
            "overall": round(overall, 2),
            "is_multiphysics": True,
            "dimensions": {
                "boundary_integrity": {"score": dim1, "detail": d1},
                "coupling_architecture": {"score": dim2, "detail": d2},
                "extension_support": {"score": dim3, "detail": d3},
                "data_transfer": {"score": dim4, "detail": d4},
            },
            "mpr_violations": mpr,
            "version_info": {
                "guide_version": GUIDE_VERSION,
                "skill_version": SKILL_VERSION,
            },
        }


def main():
    parser = argparse.ArgumentParser(
        description="求解器和物理场模块化架构模式识别评估")
    parser.add_argument("root", nargs="?", default=".",
                        help="项目根目录")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 格式")
    parser.add_argument("--mpr-only", action="store_true",
                        help="仅检测 MPR 规则")

    args = parser.parse_args()

    metrics = SolverPhysicsMetrics(args.root)

    if args.mpr_only:
        result = {"mpr_violations": metrics.check_mpr_rules()}
    else:
        result = metrics.all_metrics()

    out_dir = ensure_output_dir(args.root)
    report_path = write_report(out_dir, "solver-physics-metrics.json", result)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        vi = result.get("version_info", {})
        is_sp = result.get("is_multiphysics", False)
        print("求解器和物理场模块化架构模式识别评估")
        print("=" * 50)
        print(f"  Guide version: {vi.get('guide_version', '?')}")
        print(f"  Skill version: {vi.get('skill_version', '?')}")
        print(f"  Is multiphysics: {is_sp}")
        if is_sp:
            print(f"  Overall score: {result.get('overall', 'N/A')}")
            dims = result.get("dimensions", {})
            for dk, dv in dims.items():
                print(f"    {dk}: {dv.get('score', 'N/A')}")
            print(f"\n  MPR violations: {len(result.get('mpr_violations', []))}")
        print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
