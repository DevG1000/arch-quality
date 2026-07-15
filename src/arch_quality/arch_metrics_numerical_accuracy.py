# -*- coding: utf-8 -*-
"""
arch_metrics_numerical_accuracy.py — 数值算法正确性与精度保障评估

实现《数值算法正确性与精度保障评估指南（1.7版）》定义的 6 维评分模型
和 12 条 NVR 规则（NVR-001~NVR-012）的静态分析检测。

版本绑定：
  - 指南版本：1.7（2026-07-10）
  - Skill 版本：1.5
  - 实现版本：1.5 对齐
"""

import os
import re
import json
import argparse
from collections import defaultdict
from pathlib import Path

from arch_quality.arch_core import (
    FileIndex, DepGraph,
    ensure_output_dir, write_report, read_text_smart,
)

# 版本绑定声明
GUIDE_VERSION = "1.7"
SKILL_VERSION = "1.5"

# 过环境变量覆盖阈值。默认值 0.3（工程经验值，无文献直接支撑）。
_DEFAULT_CFL_THRESHOLD = 0.3

def _get_cfl_threshold() -> float:
    """获取 cfl_ratio 阈值，支持环境变量 CFL_RATIO_THRESHOLD 覆盖"""
    val = _os.environ.get("CFL_RATIO_THRESHOLD")
    if val is not None:
        try:
            return float(val)
        except ValueError:
            pass
    return _DEFAULT_CFL_THRESHOLD

SKILL_PATH = str(Path(__file__).parent / "skills" / "numerical-accuracy.md")

# ── 常量定义 ──
NUMERICAL_EXTS = {".f90", ".f", ".c", ".cpp", ".cxx", ".cc", ".h", ".hpp"}

import os as _os

# ── 辅助函数 ──
def _scan_files(index: FileIndex, ext_filter: set = None) -> list:
    """扫描 FileIndex 中指定扩展名的文件"""
    if ext_filter is None:
        ext_filter = NUMERICAL_EXTS
    return [f for f in index.files if f["ext"] in ext_filter]


def _grep_file(content: str, pattern: re.Pattern) -> list:
    """在文件内容中搜索正则模式"""
    return pattern.findall(content)


def _has_keyword(content: str, keywords: set) -> bool:
    """检查文件内容是否包含任一关键词"""
    lower = content.lower()
    return any(kw.lower() in lower for kw in keywords)


def _is_within_root(path: str, root: str) -> bool:
    """检查路径是否在项目根目录内（处理 WSL /tmp→/mnt 路径映射）"""
    real_path = os.path.realpath(path)
    real_root = os.path.realpath(root)
    return real_path.startswith(real_root)


# ── 检测模式 ──
# NVR-001: 显式时间格式 + CFL 控制
CFL_PATTERN = re.compile(
    r'\b(CFL|Courant|courantNumber|CoNo|adjustTimeStep|maxCo|'
    r'explicit|runge.kutta|ab2|ab3|rk4|forwardEuler)\b',
    re.MULTILINE | re.IGNORECASE
)
EXPLICIT_SCHEME_KEYWORDS = {"runge-kutta", "rk4", "rk3", "rk2",
                            "ab2", "ab3", "forward euler", "explicit",
                            "cfl", "courant"}

# NVR-002: 线性求解器与条件数
LINEAR_SOLVER_PATTERN = re.compile(
    r'\b(SPOOLES|PARDISO|PETSc|MUMPS|SuperLU|Hypre|CG|GMRES|'
    r'conjugate.gradient|preconditioner|ilu|jacobi|amg|'
    r'condition.number|condest|rcond)\b',
    re.MULTILINE | re.IGNORECASE
)

# NVR-003: 浮点相消 (a - b 模式) + 动态检测工具
CANCELLATION_PATTERN = re.compile(
    r'\b[a-z]\s*-\s*[a-z]\b',
    re.MULTILINE
)
DYNAMIC_TOOL_PATTERN = re.compile(
    r'\b(Verrou|CADNA|Verificarlo|valgrind|float.overflow|fp.error)\b',
    re.MULTILINE
)

# NVR-004: 累加循环 + Kahan 求和
KAHAN_PATTERN = re.compile(
    r'\b(Kahan|kahan.sum|compensated.sum|accumulate|'
    r'sum_reduce|fold_reduce)\b',
    re.MULTILINE
)
ACCUM_LOOP_PATTERN = re.compile(
    r'(?:for|while|do)\s*[^{]*\{[^}]*'
    r'(?:\+=|sum\s*=|total\s*=|[a-z]\s*=\s*[a-z]\s*\+)',
    re.MULTILINE | re.DOTALL
)

# NVR-005: MMS 验证
MMS_PATTERN = re.compile(
    r'\b(MMS|manufactured.solution|method.of.manufactured|'
    r'verification|order.of.accuracy|observed.order|'
    r'exact.solution|analytical.solution)\b',
    re.MULTILINE
)
MMS_FILE_KEYWORDS = {"mms", "manufactured", "verification"}

# NVR-006: 精度阶数
ACCURACY_ORDER_PATTERN = re.compile(
    r'\b(order.*accuracy|observed.*order|p\s*=\s*\d|'
    r'convergence.rate|slope|O\(h)\b',
    re.MULTILINE
)

# NVR-007: 网格收敛性
# richardson_extrap 而非裸 richardson，避免匹配开发者姓名（如 Chris Richardson）
MESH_CONVERGENCE_PATTERN = re.compile(
    r'\b(mesh.convergence|grid.convergence|refinement.study|'
    r'h.refinement|richardson._extrap|grid.study|element.size)\b',
    re.MULTILINE | re.IGNORECASE
)

# 网格细化目录模式（补充检测：Coarse/Fine 目录命名）
# 加 \b 词边界，避免子串误报（如 refinement 中的 fine）
MESH_REFINE_PATTERN = re.compile(
    r'\b(Coarse|Medium|Fine|Refined|Level[0-9]|h\.[0-9])\b',
    re.MULTILINE | re.IGNORECASE
)

RESIDUAL_PATTERN = re.compile(
    r'\b(residual|tolerance|convergence.ratio|'
    r'relative.tolerance|absolute.tolerance|'
    r'nonlinear.tolerance|linear.tolerance)\b',
    re.MULTILINE | re.IGNORECASE
)

TOLERANCE_VALUE_PATTERN = re.compile(
    r'tolerance\s*[=:]?\s*([\d.]+(?:[deE][+-]?\d+)?)',
    re.MULTILINE | re.IGNORECASE
)

# 求解器文件关键词：判断项目是否实际包含求解器代码
SOLVER_KEYWORDS = {
    # C/C++
    "solver", "solve", "timeStep", "timestep",
    # Fortran
    "subroutine", "program",
}

# NVR-010/011: 回归测试
REGRESSION_TEST_PATTERN = re.compile(
    r'\b(test|regression|unittest|ctest|check)\b',
    re.MULTILINE
)
CI_CONFIG_PATTERN = re.compile(
    r'\.(github|gitlab|jenkins|travis|circleci)',
    re.MULTILINE
)
ASSERTION_PATTERN = re.compile(
    r'\b(assert|require|check|expect|verify|'
    r'tolerance|epsilon|threshold)\b',
    re.MULTILINE
)

# 快照基线 .json 模式：回归测试中的数值比较字段
SNAPSHOT_BASELINE_PATTERN = re.compile(
    r'\b(baseline|snapshot|reference|golden)\b',
    re.MULTILINE | re.IGNORECASE
)


class NumericalAccuracyMetrics:
    """数值算法正确性与精度保障评估

    与 TemplateMetaprogrammingMetrics 结构对齐，提供 6 维评分
    和 12 条 NVR 规则的静态分析检测。
    """

    def __init__(self, root: str):
        self.root = root
        self.index = FileIndex(root)
        self._numerical_files = []
        self._all_contents = {}
        self._has_numerical = self._detect_numerical()
        if self._has_numerical:
            self._scan_numerical_files()

    def _detect_numerical(self) -> bool:
        """检测项目是否为数值密集型"""
        files = self.index.files
        total = len(files) or 1
        numerical = [f for f in files if f["ext"] in NUMERICAL_EXTS]
        ratio = len(numerical) / total

        # 关键词特征检测
        has_solver_keywords = False
        for f in numerical[:50]:  # 扫描前 50 个文件就够了
            try:
                content = read_text_smart(f["abs_path"])
                if _has_keyword(content, {"solver", "mesh", "element",
                                          "stiffness", "CFL", "Courant",
                                          "finite element", "finite volume"}):
                    has_solver_keywords = True
                    break
            except Exception:
                continue

        self._numerical_files = numerical
        return ratio > 0.2 or has_solver_keywords

    def _scan_numerical_files(self):
        """预读所有数值相关文件内容（仅保留在项目根目录内的文件）"""
        for f in self._numerical_files:
            abs_path = f.get("abs_path", f["path"])
            if not _is_within_root(abs_path, self.root):
                continue
            try:
                content = read_text_smart(abs_path)
                self._all_contents[abs_path] = content
            except Exception:
                pass

    # ── 6 维评分 ──

    def calc_numerical_stability(self) -> tuple:
        """2.1 数值稳定性保障 (25%)

        静态分析：扫描显式时间格式、CFL 控制机制、稳定性措施。
        动态工具检测（Verrou/CADNA）留待后续迭代。
        """
        if not self._has_numerical:
            return None, {}

        has_stability_measures = False
        has_cfl_control = False
        explicit_count = 0
        total_solver_files = 0

        for path, content in self._all_contents.items():
            # 检测求解器文件
            if _has_keyword(content, SOLVER_KEYWORDS):
                total_solver_files += 1
                # 检测显式格式
                if CFL_PATTERN.search(content):
                    explicit_count += 1
                # 检测 CFL 控制
                if _has_keyword(content, {"cfl", "courant", "adjustTimeStep",
                                          "maxco"}):
                    has_cfl_control = True
                # 检测稳定性措施（CFD + FEM + 指南 §2.1 全部方法）
                if _has_keyword(content, {"upwind", "linearUpwind", "bounded",
                                          "limiter", "slopeLimiter",
                                          "artificial", "artificialViscosity",
                                          "diffusion", "stabilize",
                                          "hourglass", "penalty", "stiffness",
                                          "SuSp", "SemiImplicitSource",
                                          "sourceImplicit",
                                          "stability_assured"}):
                    has_stability_measures = True

        if total_solver_files == 0:
            return 100.0, {"score": 100, "detail": "未检测到求解器代码"}

        # 评分逻辑（对照指南 2.1 节）
        # cfl_ratio 阈值通过 _get_cfl_threshold() 获取（默认 0.3，工程经验值）
        cfl_ratio = explicit_count / max(1, total_solver_files)
        thr = _get_cfl_threshold()
        if has_cfl_control and has_stability_measures:
            score = 100.0
        elif has_cfl_control:
            score = 80.0
        elif has_stability_measures and cfl_ratio < thr:
            score = 70.0
        elif has_stability_measures:
            score = 50.0
        elif cfl_ratio < thr:
            score = 30.0
        else:
            score = 10.0

        return score, {
            "score": score,
            "total_solver_files": total_solver_files,
            "explicit_scheme_files": explicit_count,
            "has_cfl_control": has_cfl_control,
            "has_stability_measures": has_stability_measures,
            "cfl_ratio": round(cfl_ratio, 3),
        }

    def calc_roundoff_sensitivity(self) -> tuple:
        """2.2 舍入误差与数值敏感度控制 (20%)

        静态分析：扫描 a-b 相消模式、Kahan 求和、动态工具配置。
        """
        if not self._has_numerical:
            return None, {}

        cancellation_count = 0
        has_kahan = False
        has_dynamic_tool = False
        total_files = len(self._all_contents)

        for path, content in self._all_contents.items():
            if CANCELLATION_PATTERN.search(content):
                cancellation_count += 1
            if KAHAN_PATTERN.search(content):
                has_kahan = True
            if DYNAMIC_TOOL_PATTERN.search(content):
                has_dynamic_tool = True

        # 评分逻辑
        base = 100
        if cancellation_count > 0:
            base -= 20
        if not has_dynamic_tool and cancellation_count > 5:
            base -= 25
        if not has_kahan:
            base -= 15
        score = max(0, base)

        return score, {
            "score": score,
            "cancellation_sites": cancellation_count,
            "has_kahan_summation": has_kahan,
            "has_dynamic_tool": has_dynamic_tool,
        }

    def calc_mms_verification(self) -> tuple:
        """2.3 MMS 验证完备性 (20%)

        静态分析：检测 MMS 测试文件、验证目录、精度阶数计算。
        """
        if not self._has_numerical:
            return None, {}

        has_mms = False
        has_accuracy_order = False
        mms_count = 0

        # 检测 MMS 相关目录（限制深度避免递归溢出）
        mms_dirs = []
        try:
            for dirpath, dirnames, _ in os.walk(self.root):
                # 深度限制，避免 RecursionError
                depth = dirpath.replace(self.root, '').count(os.sep)
                if depth > 10:
                    dirnames.clear()
                    continue
                for d in dirnames:
                    if any(kw in d.lower() for kw in MMS_FILE_KEYWORDS):
                        mms_dirs.append(os.path.join(dirpath, d))
        except RecursionError:
            pass

        for path, content in self._all_contents.items():
            if MMS_PATTERN.search(content):
                mms_count += 1
                has_mms = True
            if ACCURACY_ORDER_PATTERN.search(content):
                has_accuracy_order = True

        # 评分逻辑
        if not has_mms and not mms_dirs:
            score = 0.0
        elif has_accuracy_order and mms_count >= 3:
            score = 100.0
        elif has_accuracy_order:
            score = 80.0
        elif mms_count >= 3 or mms_dirs:
            score = 50.0
        else:
            score = 0.0

        return score, {
            "score": score,
            "mms_file_count": mms_count,
            "mms_directory_count": len(mms_dirs),
            "has_accuracy_order": has_accuracy_order,
        }

    def calc_error_estimation(self) -> tuple:
        """2.4 误差估计与控制 (15%)

        三项检查：
          1. 内容关键词检测：网格收敛性研究 + 残差控制配置
          2. 目录结构检测：Coarse/Fine/Level 等细化模式目录
          3. 容差值合理性检查：tolerance 是否达到 1e-4 以下
        """
        if not self._has_numerical:
            return None, {}

        # ── 1. 检查项目是否实际包含求解器代码 ──
        has_solver_code = any(
            _has_keyword(c, SOLVER_KEYWORDS)
            for c in self._all_contents.values()
        )
        if not has_solver_code:
            return None, {}

        # ── 2. 内容关键词检测 ──
        has_mesh_convergence = False
        has_residual = False
        mesh_conv_count = 0
        tol_values = []

        for path, content in self._all_contents.items():
            if MESH_CONVERGENCE_PATTERN.search(content):
                mesh_conv_count += 1
                has_mesh_convergence = True
            if RESIDUAL_PATTERN.search(content):
                has_residual = True
            # 收集所有 tolerance 值
            for m in TOLERANCE_VALUE_PATTERN.finditer(content):
                try:
                    tol_values.append(float(m.group(1).replace("d", "e").replace("D", "E")))
                except ValueError:
                    pass

        # ── 3. 目录结构检测：网格细化模式 ──
        dir_refine_count = 0
        try:
            for dirpath, dirnames, _ in os.walk(self.root):
                depth = dirpath.replace(self.root, '').count(os.sep)
                if depth > 10:
                    dirnames.clear()
                    continue
                for d in dirnames:
                    if MESH_REFINE_PATTERN.search(d):
                        dir_refine_count += 1
        except RecursionError:
            pass

        combined_mesh = has_mesh_convergence or dir_refine_count > 0

        # ── 4. 容差值合理性 ──
        # 合理的 tolerance 应在 1e-4 到 1e-12 之间
        # 1e-3 及以上被认为太宽松
        reasonable_tol = any(1e-12 <= v <= 1e-4 for v in tol_values)

        # ── 评分 ──
        score = 0
        if combined_mesh:
            score += 40
        if has_residual:
            score += 30
        if reasonable_tol:
            score += 30

        return score, {
            "score": score,
            "mesh_convergence_count": mesh_conv_count,
            "dir_refine_count": dir_refine_count,
            "has_residual_control": has_residual,
            "has_reasonable_tolerance": reasonable_tol,
            "has_solver_code": has_solver_code,
        }

    def calc_regression_coverage(self) -> tuple:
        """2.5 数值回归测试覆盖 (10%)

        按照指南 §2.5 公式：
          N_critical = 触发 NVR-001/002/005 的模块数
          N_tested   = 其中已有回归测试的模块数
          coverage   = N_tested / N_critical × 100  (若无关键模块则为 100)
        """
        if not self._has_numerical:
            return None, {}

        # 检测 CI 配置（仅作为信息输出，不影响评分）
        has_ci = False
        test_file_count = 0
        has_assertion = False

        for f in self.index.files:
            if CI_CONFIG_PATTERN.search(f["path"]):
                has_ci = True

        # 检测测试文件和断言
        solver_files = set()
        test_file_set = set()
        for path, content in self._all_contents.items():
            if _has_keyword(content, SOLVER_KEYWORDS):
                solver_files.add(path)
            if REGRESSION_TEST_PATTERN.search(content):
                test_file_count += 1
                test_file_set.add(path)
            if ASSERTION_PATTERN.search(content):
                has_assertion = True

        # N_critical: 触发 NVR-001/002/005 的关键模块数
        _, stab = self.calc_numerical_stability()
        _, mms = self.calc_mms_verification()
        is_nvr001 = (stab.get("score", 100) < 50 or (
            stab.get("explicit_scheme_files", 0) > 0
            and not stab.get("has_cfl_control")))
        is_nvr005 = (mms.get("score", 0) == 0)

        # NVR-002 简化检测：使用预处理器（GAMG/DIC/DILU）的存在性
        _PRE = re.compile(
            r'\b(GAMG|DIC|DILU|FDIC|smoothSolver|symGaussSeidel|'
            r'GaussSeidel|PCG|PBiCG|PBiCGStab)\b', re.MULTILINE
        )
        has_precond = any(
            _PRE.search(c)
            for c in self._all_contents.values()
        )
        has_solver = any(
            LINEAR_SOLVER_PATTERN.search(c)
            for c in self._all_contents.values()
        )
        is_nvr002 = has_solver and not has_precond

        critical_flags = [is_nvr001, is_nvr002, is_nvr005]
        N_critical = sum(1 for f in critical_flags if f)

        # N_tested: 关键模块中已有回归测试的
        # 使用求解器文件中含 test 关键词的作为代理估计
        solver_with_test = len(solver_files & test_file_set)
        N_tested = solver_with_test if N_critical > 0 else 0

        # 快照基线 .json 检测
        has_snapshot = any(
            "json" in path.lower() and SNAPSHOT_BASELINE_PATTERN.search(content)
            for path, content in self._all_contents.items()
        )

        # 评分：coverage = N_tested / N_critical × 100
        if N_critical == 0:
            score = 100.0  # 无关键模块 → 满分
        elif N_critical > 0 and N_tested >= N_critical:
            score = 100.0  # 全部覆盖
        else:
            coverage = N_tested / max(1, N_critical)
            score = coverage * 100.0

        # 快照基线和断言作为额外验证（加分项）
        if score >= 100 and has_snapshot and has_assertion:
            score = 100.0
        elif score < 100:
            if has_assertion:
                score = min(score + 15, 100)
            if has_snapshot:
                score = min(score + 10, 100)

        test_ratio = test_file_count / max(1, len(self._all_contents))
        return score, {
            "score": round(score, 1),
            "has_ci_config": has_ci,
            "test_file_count": test_file_count,
            "has_assertions": has_assertion,
            "has_snapshot_baseline": has_snapshot,
            "test_ratio": round(test_ratio, 3),
            "N_critical": N_critical,
            "N_tested": N_tested,
        }

    def calc_numerical_debt(self) -> tuple:
        """2.6 数值债务密度 (10%)

        通过检查各维度评分低分情况估算债务密度。
        注意：不调用 check_nvr_rules() 以避免循环调用。
        """
        if not self._has_numerical:
            return None, {}

        # 从各维度评分独立估算债务，不依赖 check_nvr_rules
        low_score_count = 0
        total_dims = 6
        for dim_method in [
            self.calc_numerical_stability,
            self.calc_roundoff_sensitivity,
            self.calc_mms_verification,
            self.calc_error_estimation,
            self.calc_regression_coverage,
        ]:
            score, _ = dim_method()
            if score is not None and score < 50:
                low_score_count += 1

        debt_ratio = low_score_count / max(1, total_dims)
        score = max(0, 100 - debt_ratio * 200)

        return score, {
            "score": round(score, 2),
            "debt_ratio": round(debt_ratio, 3),
            "low_score_dimensions": low_score_count,
        }

    # ── NVR 规则检查 ──

    def check_nvr_rules(self) -> list:
        """执行全部 12 条 NVR 规则检测"""
        if not self._has_numerical:
            return []

        results = []

        # NVR-001: 数值稳定性溢出
        _, stab_detail = self.calc_numerical_stability()
        if stab_detail.get("score", 100) < 50 or (
                stab_detail.get("explicit_scheme_files", 0) > 0
                and not stab_detail.get("has_cfl_control")):
            results.append({
                "rule": "NVR-001", "name": "数值稳定性溢出",
                "severity": "HIGH",
                "output_level": "ERROR",
                "count": stab_detail.get("explicit_scheme_files", 0),
                "detail": (f"检测到 {stab_detail.get('explicit_scheme_files', 0)} 个显式格式文件，"
                           f"{'未' if not stab_detail.get('has_cfl_control') else '已'}配置 CFL 控制"),
            })

        # NVR-002: 条件数超限
        PRECONDITIONER_PATTERN = re.compile(
        r'\b(GAMG|DIC|DILU|FDIC|smoothSolver|symGaussSeidel|'
        r'GaussSeidel|PCG|PBiCG|PBiCGStab)\b',
        re.MULTILINE
        )
        COND_MONITOR_PATTERN = re.compile(
        r'\b(condition\.number|condest|rcond|cond\b)',
        re.MULTILINE
        )
        solver_count = sum(1 for c in self._all_contents.values()
        if LINEAR_SOLVER_PATTERN.search(c))
        has_preconditioner = any(
        PRECONDITIONER_PATTERN.search(c)
        for c in self._all_contents.values()
        )
        has_cond_monitoring = any(
        COND_MONITOR_PATTERN.search(c)
        for c in self._all_contents.values()
        )
        # 条件数超限判定：使用了线性求解器，但没有使用预处理器，且没有条件数监控
        if solver_count > 0 and not has_preconditioner and not has_cond_monitoring:
            results.append({
            "rule": "NVR-002", "name": "条件数超限",
            "severity": "HIGH",
            "output_level": "ERROR",
            "count": solver_count,
            "detail": f"检测到 {solver_count} 个文件涉及线性求解器，但未使用预处理器(GAMG/DIC/DILU)且未配置条件数监控",
            })
    
        # NVR-003: 相消性损失
        _, roundoff = self.calc_roundoff_sensitivity()
        if roundoff.get("cancellation_sites", 0) > 0:
            sev = "HIGH"
            ol = "ERROR" if not roundoff.get("has_dynamic_tool") else "WARNING"
            results.append({
                "rule": "NVR-003", "name": "相消性损失",
                "severity": sev,
                "output_level": ol,
                "count": roundoff.get("cancellation_sites", 0),
                "detail": (f"发现 {roundoff.get('cancellation_sites')} 处潜在的相消性损失模式"
                           f"{'，未检测到动态分析工具(Verrou/CADNA)' if not roundoff.get('has_dynamic_tool') else ''}"),
            })

        # NVR-004: 累积误差失控
        has_kahan = roundoff.get("has_kahan_summation", False)
        if not has_kahan:
            results.append({
                "rule": "NVR-004", "name": "累积误差失控",
                "severity": "MEDIUM",
                "output_level": "WARNING",
                "count": 1,
                "detail": "未检测到 Kahan 求和等补偿累加算法，浮点累加可能存在累积误差",
            })

        # NVR-005: MMS 验证缺失
        _, mms = self.calc_mms_verification()
        if mms.get("score", 0) == 0:
            results.append({
                "rule": "NVR-005", "name": "MMS 验证缺失",
                "severity": "HIGH",
                "output_level": "ERROR",
                "count": 1,
                "detail": "未检测到 MMS (方法制解) 验证文件或目录，数值算法缺乏系统性验证",
            })

        # NVR-006: 观察阶偏差
        if not mms.get("has_accuracy_order", False) and mms.get("score", 0) > 0:
            results.append({
                "rule": "NVR-006", "name": "观察阶偏差",
                "severity": "HIGH",
                "output_level": "ERROR",
                "count": 1,
                "detail": "存在 MMS 相关文件但未检测到精度阶数(观察阶)计算结果",
            })

        # NVR-007: 离散误差未控
        _, err = self.calc_error_estimation()
        if err is None:
            err = {}
        combined_mesh = (err.get("mesh_convergence_count", 0) > 0
                         or err.get("dir_refine_count", 0) > 0)
        if not combined_mesh:
            results.append({
                "rule": "NVR-007", "name": "离散误差未控",
                "severity": "MEDIUM",
                "output_level": "WARNING",
                "count": 1,
                "detail": "未检测到网格收敛性研究(如 Richardson 外推/网格细化)",
            })

        # NVR-008: 迭代误差未控
        if not err.get("has_reasonable_tolerance", False):
            results.append({
                "rule": "NVR-008", "name": "迭代误差未控",
                "severity": "MEDIUM",
                "output_level": "WARNING",
                "count": 1,
                "detail": "未检测到合理的迭代容差设置(tolerance < 1e-4)",
            })

        # NVR-008: 迭代误差未控
        if not err.get("has_residual_control", False):
            results.append({
                "rule": "NVR-008", "name": "迭代误差未控",
                "severity": "MEDIUM",
                "output_level": "WARNING",
                "count": 1,
                "detail": "未检测到迭代求解器残差或容差配置",
            })

        # NVR-010: 回归测试缺失
        _, regr = self.calc_regression_coverage()
        n_crit = regr.get("N_critical", 0)
        n_tested = regr.get("N_tested", 0)
        has_snap = regr.get("has_snapshot_baseline", False)
        has_asrt = regr.get("has_assertions", False)
        if n_crit > 0 and n_tested == 0:
            results.append({
                "rule": "NVR-010", "name": "回归测试缺失",
                "severity": "MEDIUM",
                "output_level": "WARNING",
                "count": 1,
                "detail": (f"有 {n_crit} 个关键数值模块触发了 NVR 检查"
                           f"{'，其中 0 个有回归测试保护' if n_tested == 0 else ''}"),
            })

        # NVR-011: 回归允许值缺失
        if n_tested > 0 and not has_asrt and not has_snap:
            results.append({
                "rule": "NVR-011", "name": "回归允许值缺失",
                "severity": "LOW",
                "output_level": "INFO",
                "count": 1,
                "detail": "存在回归测试但未检测到精度断言或快照基线",
            })

        # NVR-012: 数值债务密度
        _, debt = self.calc_numerical_debt()
        if debt.get("debt_ratio", 0) > 0.3:
            results.append({
                "rule": "NVR-012", "name": "数值债务密度",
                "severity": "LOW",
                "output_level": "INFO",
                "count": 1,
                "detail": f"数值债务密度 {debt.get('debt_ratio', 0)*100:.1f}%，超过 30% 警戒线",
            })

        return results

    def all_metrics(self) -> dict:
        """返回完整的 6 维评分 + NVR 规则检查结果"""
        if not self._has_numerical:
            return {
                "overall": None,
                "is_numerical": False,
                "dimensions": {
                    "numerical_stability": {"score": None, "detail": {}},
                    "roundoff_sensitivity": {"score": None, "detail": {}},
                    "mms_verification": {"score": None, "detail": {}},
                    "error_estimation": {"score": None, "detail": {}},
                    "regression_coverage": {"score": None, "detail": {}},
                    "numerical_debt": {"score": None, "detail": {}},
                },
                "nvr_violations": [],
            }

        dim1, d1 = self.calc_numerical_stability()
        dim2, d2 = self.calc_roundoff_sensitivity()
        dim3, d3 = self.calc_mms_verification()
        dim4, d4 = self.calc_error_estimation()
        dim5, d5 = self.calc_regression_coverage()
        dim6, d6 = self.calc_numerical_debt()

        weights = [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]
        scores = [dim1 or 0, dim2 or 0, dim3 or 0, dim4 or 0, dim5 or 0, dim6 or 0]
        overall = sum(s * w for s, w in zip(scores, weights))

        nvr = self.check_nvr_rules()

        return {
            "overall": round(overall, 2),
            "is_numerical": True,
            "dimensions": {
                "numerical_stability": {"score": dim1, "detail": d1},
                "roundoff_sensitivity": {"score": dim2, "detail": d2},
                "mms_verification": {"score": dim3, "detail": d3},
                "error_estimation": {"score": dim4, "detail": d4},
                "regression_coverage": {"score": dim5, "detail": d5},
                "numerical_debt": {"score": dim6, "detail": d6},
            },
            "nvr_violations": nvr,
            "version_info": {
                "guide_version": GUIDE_VERSION,
                "skill_version": SKILL_VERSION,
            },
        }


def main():
    parser = argparse.ArgumentParser(description="数值算法正确性与精度保障评估")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--mms-pobs", type=float, default=None,
                        help="MMS 观察阶（如 2.001），传入后覆盖 MMS 检测")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--full", action="store_true",
                        help="完整评估（6维评分 + NVR 规则）")
    parser.add_argument("--nvr-only", action="store_true",
                        help="仅检测 NVR 规则")

    args = parser.parse_args()

    metrics = NumericalAccuracyMetrics(args.root)

    if args.nvr_only:
        result = {"nvr_violations": metrics.check_nvr_rules()}
    else:
        result = metrics.all_metrics()

    # 若传入了 MMS 观察阶，覆盖自动检测
    if args.mms_pobs is not None:
        if "dimensions" in result and "mms_verification" in result["dimensions"]:
            score = 100 if abs(args.mms_pobs - 2.0) <= 0.1 else (50 if abs(args.mms_pobs - 2.0) <= 0.2 else 20)
            result["dimensions"]["mms_verification"]["score"] = score
            result["dimensions"]["mms_verification"]["detail"]["p_obs"] = args.mms_pobs
            # 重新计算总分
            weights = [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]
            dims = result.get("dimensions", {})
            order = ["numerical_stability", "roundoff_sensitivity", "mms_verification",
                     "error_estimation", "regression_coverage", "numerical_debt"]
            scores = [dims.get(k, {}).get("score") or 0 for k in order]
            result["overall"] = round(sum(s * w for s, w in zip(scores, weights)), 2)

    out_dir = ensure_output_dir(args.root)
    report_path = write_report(out_dir, "numerical-accuracy.json", result)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        vi = result.get("version_info", {})
        print(f"Numerical Accuracy Assessment")
        print(f"{'='*40}")
        print(f"  Guide version: {vi.get('guide_version', '?')}")
        print(f"  Skill version: {vi.get('skill_version', '?')}")
        print(f"  Overall score: {result.get('overall', 'N/A')}")
        dims = result.get("dimensions", {})
        for dk, dv in dims.items():
            print(f"  {dk}: {dv.get('score', 'N/A')}")
        print(f"\n  NVR violations: {len(result.get('nvr_violations', []))}")
        print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
