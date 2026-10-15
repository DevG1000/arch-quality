# -*- coding: utf-8 -*-
"""
arch_metrics_geometry_consistency.py — 几何内核与科学数据结构一致性评估

实现《几何内核与科学数据结构一致性评估指南（1.7版）》定义的 4 维评分模型
和 12 条 GCS 规则（GCS-001~012）的静态分析检测。

版本绑定：
  - 指南版本：1.7
  - Skill 版本：1.1
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

SKILL_PATH = str(Path(__file__).parent / "skills" / "geometry-consistency.md")

GUIDE_VERSION = "1.7"
SKILL_VERSION = "1.1"

# ── 常量定义 ──
CPP_EXTS = {".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".txx", ".h", ".c", ".ixx", ".cppm"}
PY_EXTS = {".py"}
ALL_GCS_EXTS = CPP_EXTS | PY_EXTS

# 几何内核信号（启用检测）
KERNEL_SIGNAL_RE = re.compile(
    r"\b(TopoDS_|Handle_|BRep[A-Z_]|Geom_[A-Z_]|NCollection_|BOPCheck|BRepCheck)\w*",
    re.MULTILINE)
SCIDATA_SIGNAL_RE = re.compile(
    r"\b(vtk[A-Z]|fvMesh|gmsh|CGAL|MeshField|FieldData)\w*",
    re.MULTILINE)

# 内核类型清单（GCS-002/004）
KERNEL_TYPE_RE = re.compile(r"\b(TopoDS_[A-Za-z]+|Handle\([A-Za-z_]+\)|BRep[A-Za-z_]*|Geom_[A-Za-z_]+)\b")

# GCS-001 闭合性校验引用
CLOSURE_CHECK_RE = re.compile(
    r"\b(BRepCheck_Analyzer\s*\w*\s*\(|BRepCheck_[A-Za-z_]+\s+\w+\s*\(|BOPCheck\w*\s*\w*\s*\(|CheckShape\s*\(|IsClosed\s*\(\))", re.MULTILINE)

# GCS-002 裸 new 内核对象 + 跨作用域穿越（return 裸指针 / 参数传递）
BARE_NEW_KERNEL_RE = re.compile(
    r"return\s+new\s+(?:TopoDS_[A-Za-z]+|BRep[A-Za-z]*|Geom_[A-Za-z_]+)\b", re.MULTILINE)
# 函数返回"裸内核指针"签名（Geom_Plane* f( 而非 Handle(Geom_Plane) f(）
RAW_KERNEL_PTR_FUNC_RE = re.compile(
    r"(?:TopoDS_[A-Za-z]+|BRep[A-Za-z_]*|Geom_[A-Za-z_]+)\s*\*\s*[A-Za-z_]\w*\s*\(", re.MULTILINE)
RETURN_BARE_PTR_RE = re.compile(
    r"return\s+(?:[A-Za-z_]\w*\s*->\s*)?[A-Za-z_]\w*\s*;")

# GCS-003 内核调用点失败状态检查（紧邻同语句块窄化）
BOOL_CALL_RE = re.compile(
    r"\bBRepAlgoAPI_[A-Za-z_]+\s+(\w+)\s*\(", re.MULTILINE)

KERNEL_CALL_RE = re.compile(
    r"(BRepAlgoAPI_[A-Za-z_]+|BRepBuilderAPI_[A-Za-z_]+|BRepPrimAPI_[A-Za-z_]+)\s+\w+\s*\([^;]*\);")
DONE_CHECK_RE = re.compile(
    r"\.IsDone\s*\(|catch\s*\(")

# GCS-004 同作用域 new/delete 内核类型
SCOPE_NEW_DELETE_RE = re.compile(
    r"(?:new\s+(?:TopoDS_[A-Za-z]+|BRep[A-Za-z]*|Geom_[A-Za-z_]+)\b.*?\bdelete\s+\w+|delete\s+\w+\s*;.*?\bnew\s+(?:TopoDS_[A-Za-z]+|BRep[A-Za-z]*|Geom_[A-Za-z_]+)\b)",
    re.MULTILINE | re.DOTALL)

# GCS-005 硬编码精度/容差魔法数字
PRECISION_LITERAL_RE = re.compile(r"1e-\s?\d+|[<>]=?\s*0\.0+[1-9]")
NAMED_PRECISION_RE = re.compile(r"(?:^|_)(?:TOL|TOLERANCE|PRECISION|CONFUSION|EPSILON)\b", re.MULTILINE)

# GCS-006 单位换算魔法因子
UNIT_FACTOR_RE = re.compile(r"\b(25\.4|3\.28084|0\.0254|0\.3048|2\.54|1\.60934)\b")
UNIT_FUNC_RE = re.compile(r"\b(convert|unit::|UnitsMethods|to_mm|to_inch|to_meter)\w*")

# GCS-007 网格类型引用 + 交叉索引
GRID_TYPE_RE = re.compile(r"\b(vtkUnstructuredGrid|vtkPolyData|gmsh::|fvMesh|volScalarField|GModel)\b")
CROSS_INDEX_RE = re.compile(
    r"(?:gmsh::model::\w+\s*\(|fvMesh\w*\s*\([^)]*vtk|vtk\w*\s*\([^)]*fvMesh)",
    re.MULTILINE)

# GCS-008 场量命名一致性
FIELD_NAME_RE = re.compile(r"\b(pointData|cellData|cellField|pointField|Field|fieldData)\b")
FIELD_INCONSISTENT_RE = re.compile(
    r"\b(pointData|cellData)\b[^\n]*\b(cellField|pointField)\b|\b(cellField|pointField)\b[^\n]*\b(pointData|cellData)\b",
    re.MULTILINE)

# GCS-009 维度因子 vs 命名分量常量
DIM_FACTOR_RE = re.compile(r"new\s+(?:double|float)\s*\w*\s*\[\s*\w+\s*\*\s*(\d+)\s*\]")
COMPONENT_CONST_RE = re.compile(r"constexpr\s+int\s+(\w*(?:COMPONENT|DIM|COMPONENTS|DIMENSION)S?)\s*=\s*(\d+)")

# GCS-010 裸数组声明
BARE_ARRAY_RE = re.compile(r"\b(?:double|float)\s*\*\s*\w+|new\s+(?:double|float)\s*\w+\s*\[")
SCIDATA_REF_RE = re.compile(r"\b(vtkSmartPointer|vtkPoints|vtkUnstructuredGrid|fvMesh|MeshField)\b")

# GCS-011 浅拷贝共享底层缓冲
SHALLOW_COPY_RE = re.compile(
    r"(?:class|struct)\s+(\w+)\s*\{[^}]*?(?:vtkSmartPointer<[^>]+>|(?:double|float)\s*\*)\s*\w+_[^}]*?\b\1\s*\([^)]*\)\s*:\s*\w+_\s*\([^)]*\)\s*\{",
    re.MULTILINE | re.DOTALL)

# GCS-012 直接成员访问（复用 DIRECT_MEMBER_ACCESS 模式）
DIRECT_MEMBER_ACCESS_RE = re.compile(
    r"\w+\s*->\s*(?:data_|internal_|private_|coords|vertices_)\w*(?:\[[^\]]*\])?\s*[=;]",
    re.MULTILINE)

# 白名单：内核自身目录名（12 条规则全规则路径级排除）
# 强名：内核发行版/内核模块专有目录名，命中即判定为内核自身
KERNEL_SELF_DIRS = {"occt", "opencascade", "cascade", "tkg3d", "tktop", "tkbool"}
# 弱名：通用几何词，可能同时是应用层目录名（如 SALOME 的 src/GEOM 为其封装层）。
# 保留以维持基线校准，但纳入过度排除守卫（ratio > 30% 告警）以便人工复核。
WEAK_KERNEL_SELF_DIRS = {"geom", "brep", "geometric_engine"}
KERNEL_SELF_DIRS = KERNEL_SELF_DIRS | WEAK_KERNEL_SELF_DIRS

# ── 豁免注解（WP-2.5）──
# @kernel_exempt：文件级，从全部 12 条规则统计中剔除（路径级排除的细粒度补充）
# 合法格式：/* @kernel_exempt: reason */   reason 必填且非空
KERNEL_EXEMPT_RE = re.compile(r"/\*\s*@kernel_exempt\s*:\s*(?P<reason>\S[^*\n]*?)\s*\*/")
# 非法形式 → 豁免无效，仅记录告警（缺 reason / 空 reason）
KERNEL_EXEMPT_INVALID_RE = re.compile(
    r"/\*\s*@kernel_exempt\s*(?::\s*)?\*/")

# @gcs_waiver：行尾注释，声明受控裸数组（性能热路径）
# 合法格式：// @gcs_waiver: reason   reason 必填且非空
# 语义：GCS-010 密度统计的分子与分母同时剔除该文件（影响 scoring）
GCS_WAIVER_RE = re.compile(r"//\s*@gcs_waiver\s*:\s*(?P<reason>\S[^\n]*?)\s*$", re.MULTILINE)
GCS_WAIVER_INVALID_RE = re.compile(r"//\s*@gcs_waiver\s*(?::\s*)?$", re.MULTILINE)

# 反滥用守卫：各排除通道的排除文件数占已扫描文件数上限（超过则输出告警，
# 防止"全项目标注豁免/大批目录被排除"使 GCS 退化为空评估）
WAIVER_ABUSE_RATIO_LIMIT = 0.30

THIRD_PARTY_DIR_NAMES = {
    "third_party", "thirdparty", "3rdparty", "external", "vendor",
    "deps", "dependencies", "libs", "external_libs",
}


def _strip_comments(content: str) -> str:
    """剥离 C/C++ 行注释 // 与块注释 /* */（避免注释/字符串提及关键词造成误报）"""
    content = re.sub(r"//[^\n]*", "", content)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    return content


def _detect_geometry(root: str, index: FileIndex) -> bool:
    """启用检测：源码含几何内核或科学数据结构信号"""
    source_files = [f for f in index.files if f["ext"] in ALL_GCS_EXTS]
    for f in source_files[:300]:
        try:
            content = _strip_comments(read_text_smart(f["abs_path"]))
        except Exception:
            continue
        if KERNEL_SIGNAL_RE.search(content) or SCIDATA_SIGNAL_RE.search(content):
            return True
    return False


class GeometryConsistencyMetrics:
    """几何内核与科学数据结构一致性评估"""

    def __init__(self, root: str):
        self.root = root
        self.index = FileIndex(root)
        self.weights = {}
        self._all_contents = {}        # abs_path → content（已剥离注释）
        self._kernel_exempt = {}       # rel_path → reason（@kernel_exempt，12 规则全排除）
        self._gcs_waiver = {}          # rel_path → reason（@gcs_waiver，仅 GCS-010 密度）
        self._invalid_waivers = []     # 缺 reason 的非法豁免注解（告警留痕）
        self._is_geometry = False
        self._dims_cache = {}
        self._init_weights()
        self._is_geometry = _detect_geometry(root, self.index)
        if self._is_geometry:
            self._scan_files()

    def _init_weights(self):
        _DIM_KEYS = {"几何内核数据一致性", "内核精度/单位一致性",
                     "科学数据结构组织一致性", "数据表示与访问规范性"}
        try:
            raw = load_weights_from_skill(SKILL_PATH)
            self.weights = {k: v for k, v in raw.items() if k in _DIM_KEYS}
            if len(self.weights) != 4:
                raise ValueError(f"只解析到 {len(self.weights)} 个维度权重")
        except Exception:
            self.weights = {
                "几何内核数据一致性": 0.30,
                "内核精度/单位一致性": 0.20,
                "科学数据结构组织一致性": 0.25,
                "数据表示与访问规范性": 0.25,
            }

    def _rel_path(self, abs_path: str) -> str:
        """统一为相对 root 的正斜杠路径（豁免字典的键）"""
        try:
            return os.path.relpath(abs_path, self.root).replace("\\", "/")
        except ValueError:
            return str(abs_path).replace("\\", "/")

    def _scan_files(self):
        for f in self.index.files:
            if f["ext"] not in ALL_GCS_EXTS:
                continue
            try:
                raw = read_text_smart(f["abs_path"])
            except Exception:
                continue
            rel = self._rel_path(f["abs_path"])
            # 豁免注解必须从原始内容采集（_strip_comments 会剥离注释）
            m = KERNEL_EXEMPT_RE.search(raw)
            if m:
                self._kernel_exempt[rel] = m.group("reason").strip()
            elif KERNEL_EXEMPT_INVALID_RE.search(raw):
                self._invalid_waivers.append(
                    {"file": rel, "annotation": "@kernel_exempt",
                     "issue": "缺少 reason，豁免无效"})
            wm = GCS_WAIVER_RE.search(raw)
            if wm:
                self._gcs_waiver[rel] = wm.group("reason").strip()
            elif GCS_WAIVER_INVALID_RE.search(raw):
                self._invalid_waivers.append(
                    {"file": rel, "annotation": "@gcs_waiver",
                     "issue": "缺少 reason，豁免无效"})
            self._all_contents[f["abs_path"]] = _strip_comments(raw)

    def _is_kernel_self(self, abs_path: str) -> bool:
        """判断是否内核自身目录（路径级排除，覆盖全部 12 条规则）"""
        try:
            rel = os.path.relpath(abs_path, self.root)
        except ValueError:
            return False
        parts = Path(rel).parts
        return any(p.lower() in KERNEL_SELF_DIRS for p in parts)

    def _is_test_file(self, abs_path: str) -> bool:
        """跳过测试/QA/Draw/示例代码（OCCT QABugs 等非生产代码）"""
        try:
            rel = os.path.relpath(abs_path, self.root)
        except ValueError:
            return False
        low = rel.lower().replace("\\", "/")
        return any(k in part for part in low.split("/")
                   for k in ("test", "qa", "draw", "sample", "example", "demo"))

    def _is_third_party(self, abs_path: str) -> bool:
        try:
            rel = os.path.relpath(abs_path, self.root)
        except ValueError:
            return False
        parts = Path(rel).parts
        return any(p.lower() in THIRD_PARTY_DIR_NAMES for p in parts)

    def _skip(self, abs_path: str, exclude_kernel_self: bool = True,
              exclude_test: bool = False) -> bool:
        """统一排除判定（WP-2.5）

        优先级：第三方目录 > 测试/QA/Draw > @kernel_exempt 注解 > 内核目录（路径级）
        - @kernel_exempt 对全部 12 条规则生效（文件级）
        - exclude_kernel_self 控制路径级内核目录排除（GCS-001 经 _any 显式传 True）
        """
        if self._is_third_party(abs_path):
            return True
        if exclude_test and self._is_test_file(abs_path):
            return True
        if self._rel_path(abs_path) in self._kernel_exempt:
            return True
        if exclude_kernel_self and self._is_kernel_self(abs_path):
            return True
        return False

    def _waiver_audit(self) -> dict:
        """豁免审计（反滥用守卫）

        三条排除通道：内核目录（路径级）/ @kernel_exempt（12 规则）/ @gcs_waiver（仅 GCS-010）。
        任一通道排除占比超 WAIVER_ABUSE_RATIO_LIMIT 即告警，防止
        "全项目标注豁免"或"通用目录名（geom/brep）误伤应用层代码"
        导致 12 条规则退化为空评估。
        """
        total = max(1, len(self._all_contents))
        ke_count = len(self._kernel_exempt)
        gw_count = len(self._gcs_waiver)
        ke_ratio = round(ke_count / total, 4)
        gw_ratio = round(gw_count / total, 4)
        kd_files = [p for p in self._all_contents if self._is_kernel_self(p)]
        kd_ratio = round(len(kd_files) / total, 4)
        limit = WAIVER_ABUSE_RATIO_LIMIT
        warnings = []
        if ke_ratio > limit:
            warnings.append(
                f"@kernel_exempt 排除占比 {ke_ratio:.1%} 超过上限 {limit:.0%}，"
                f"12 条规则覆盖度可能失真，请复核豁免必要性")
        if gw_ratio > limit:
            warnings.append(
                f"@gcs_waiver 排除占比 {gw_ratio:.1%} 超过上限 {limit:.0%}，"
                f"GCS-010 密度可能被豁免抬高，请复核受控裸数组声明")
        if kd_ratio > limit:
            warnings.append(
                f"内核目录排除占比 {kd_ratio:.1%} 超过上限 {limit:.0%}，"
                f"通用目录名（{'/'.join(sorted(WEAK_KERNEL_SELF_DIRS))}）可能误伤应用层代码，"
                f"请确认这些目录确为内核自身实现")
        return {
            "kernel_exempt": {
                "count": ke_count,
                "ratio": ke_ratio,
                "scope": "全部 12 条规则",
                "files": sorted(self._kernel_exempt)[:20],
            },
            "gcs_waiver": {
                "count": gw_count,
                "ratio": gw_ratio,
                "scope": "仅 GCS-010 密度（分子分母同时剔除）",
                "files": sorted(self._gcs_waiver)[:20],
            },
            "kernel_dir_exclusion": {
                "count": len(kd_files),
                "ratio": kd_ratio,
                "scope": "全部 12 条规则（路径级）",
                "strong_names": sorted(KERNEL_SELF_DIRS - WEAK_KERNEL_SELF_DIRS),
                "weak_names": sorted(WEAK_KERNEL_SELF_DIRS),
            },
            "invalid_waivers": self._invalid_waivers[:20],
            "invalid_count": len(self._invalid_waivers),
            "abuse_limit": limit,
            "abuse_warning": "；".join(warnings) if warnings else None,
        }

    def _count(self, pattern: re.Pattern) -> int:
        """按文件计数匹配次数（排除第三方/豁免/内核目录；测试文件保持原口径计入）"""
        total = 0
        for abs_path, content in self._all_contents.items():
            if self._skip(abs_path, exclude_kernel_self=True):
                continue
            total += len(pattern.findall(content))
        return total

    def _any(self, pattern: re.Pattern, exclude_kernel_self: bool = False) -> bool:
        for abs_path, content in self._all_contents.items():
            if self._skip(abs_path, exclude_kernel_self=exclude_kernel_self):
                continue
            if pattern.search(content):
                return True
        return False

    def _calc_cached(self, name, fn):
        if name not in self._dims_cache:
            self._dims_cache[name] = fn()
        return self._dims_cache[name]

    # ── 维度 1：几何内核数据一致性（30%）──

    def calc_geometry_kernel_consistency(self) -> tuple:
        def _impl():
            if not self._is_geometry:
                return None, {}
            score = 0
            detail = {}

            # 检查项 1：闭合性校验测试存在（GCS-001 加分项）
            has_closure = self._any(CLOSURE_CHECK_RE, exclude_kernel_self=True)
            if has_closure:
                score += 30
            detail["closure_check"] = {"score": 30 if has_closure else 0, "has": has_closure}

            # 检查项 2：Handle 一致（无跨作用域裸指针穿越）（GCS-002）
            bare_new_cross = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path, exclude_kernel_self=True):
                    continue
                if BARE_NEW_KERNEL_RE.search(content) and RAW_KERNEL_PTR_FUNC_RE.search(content):
                    bare_new_cross += 1
            if bare_new_cross == 0:
                score += 25
            detail["handle_consistency"] = {"score": 25 if bare_new_cross == 0 else 0,
                                            "bare_cross_count": bare_new_cross}

            # 检查项 3：异常/失败状态传播（GCS-003，B3.5 校准）
            # 仅判定高风险布尔操作（BRepAlgoAPI_*）；跳过测试/QA/Draw；
            # 文件级识别 IsDone/IsValid/助手委托(CheckAndLoad)/显式 Build；
            # 跨函数/封装级(builder IsDone)检查静态不可判 → KNOWN_HOLES
            missing_done = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path, exclude_kernel_self=True, exclude_test=True):
                    continue
                for m in BOOL_CALL_RE.finditer(content):
                    var = m.group(1)
                    rest = content[m.end():]
                    if re.search(r"\b" + re.escape(var) + r"\s*\.\s*IsDone\s*\(", rest):
                        continue
                    if re.search(r"\b" + re.escape(var) + r"\s*\.\s*IsValid\s*\(", rest):
                        continue
                    if re.search(r"\bCheckAndLoad\s*\(\s*" + re.escape(var) + r"\b", rest):
                        continue
                    if re.search(r"\b" + re.escape(var) + r"\s*\.\s*Build\s*\(", rest):
                        continue
                    missing_done += 1
            if missing_done == 0:
                score += 25
            detail["error_propagation"] = {"score": 25 if missing_done == 0 else 0,
                                           "missing_check_count": missing_done}

            # 检查项 4：生命周期受管理（GCS-004）
            scope_manual = self._count(SCOPE_NEW_DELETE_RE)
            if scope_manual == 0:
                score += 20
            detail["lifetime_management"] = {"score": 20 if scope_manual == 0 else 0,
                                             "manual_scope_count": scope_manual}

            final = min(score, 100)
            detail["score"] = final
            return final, detail
        return self._calc_cached("geom_kernel", _impl)

    # ── 维度 2：内核精度/单位一致性（20%）──

    def calc_precision_unit_consistency(self) -> tuple:
        def _impl():
            if not self._is_geometry:
                return None, {}
            score = 0
            detail = {}

            # GCS-005：硬编码精度魔法数字（文件级：同文件有字面量且无命名常量）
            prec_bad = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path, exclude_kernel_self=True):
                    continue
                if NAMED_PRECISION_RE.search(content):
                    continue
                prec_bad += len(PRECISION_LITERAL_RE.findall(content))
            if prec_bad == 0:
                score += 50
            detail["precision_magic"] = {"score": 50 if prec_bad == 0 else 0,
                                         "literal_count": prec_bad}

            # GCS-006：单位换算魔法因子
            unit_factors = 0
            unit_func = False
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path, exclude_kernel_self=True):
                    continue
                unit_factors += len(UNIT_FACTOR_RE.findall(content))
                if UNIT_FUNC_RE.search(content):
                    unit_func = True
            if unit_factors == 0 or unit_func:
                score += 50
            detail["unit_factor"] = {"score": 50 if (unit_factors == 0 or unit_func) else 0,
                                     "factor_count": unit_factors, "has_unit_func": unit_func}

            final = min(score, 100)
            detail["score"] = final
            return final, detail
        return self._calc_cached("precision_unit", _impl)

    # ── 维度 3：科学数据结构组织一致性（25%）──

    def calc_scidata_organization(self) -> tuple:
        def _impl():
            if not self._is_geometry:
                return None, {}
            score = 0
            detail = {}

            # GCS-007：网格语义混用（≥2 类型 + 交叉索引，窄化）
            mixed = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path, exclude_kernel_self=True):
                    continue
                types = set(GRID_TYPE_RE.findall(content))
                if len(types) >= 2 and CROSS_INDEX_RE.search(content):
                    mixed += 1
            if mixed == 0:
                score += 40
            detail["mesh_semantics"] = {"score": 40 if mixed == 0 else 0, "mixed_count": mixed}

            # GCS-008：场量命名一致性
            inconsistent = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path, exclude_kernel_self=True):
                    continue
                if FIELD_INCONSISTENT_RE.search(content):
                    inconsistent += 1
            if inconsistent == 0:
                score += 35
            detail["field_organization"] = {"score": 35 if inconsistent == 0 else 0,
                                            "inconsistent_count": inconsistent}

            # GCS-009：维度匹配（命名分量常量 vs 硬编码因子）
            mismatch = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path, exclude_kernel_self=True):
                    continue
                consts = dict((m.group(1), int(m.group(2)))
                              for m in COMPONENT_CONST_RE.finditer(content))
                if not consts:
                    continue
                for m in DIM_FACTOR_RE.finditer(content):
                    factor = int(m.group(1))
                    if factor not in consts.values():
                        mismatch += 1
            if mismatch == 0:
                score += 25
            detail["dimension_match"] = {"score": 25 if mismatch == 0 else 0,
                                         "mismatch_count": mismatch}

            final = min(score, 100)
            detail["score"] = final
            return final, detail
        return self._calc_cached("scidata_org", _impl)

    # ── 维度 4：数据表示与访问规范性（25%）──

    def calc_data_access_norm(self) -> tuple:
        def _impl():
            if not self._is_geometry:
                return None, {}
            score = 0
            detail = {}

            # GCS-010：裸数组密度阈值（默认 50%）
            # @gcs_waiver（受控裸数组/性能热路径）→ 该文件从分子与分母同时剔除
            bare_files = 0
            scidata_files = 0
            waived_files = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path, exclude_kernel_self=True):
                    continue
                if self._rel_path(abs_path) in self._gcs_waiver:
                    waived_files += 1
                    continue
                has_bare = bool(BARE_ARRAY_RE.search(content))
                has_sci = bool(SCIDATA_REF_RE.search(content))
                if has_sci and has_bare:
                    bare_files += 1
                if has_sci:
                    scidata_files += 1
            density = bare_files / max(1, scidata_files)
            if density <= 0.5:
                score += 35
            # 分母被 @gcs_waiver 全部豁免清空 → 密度恒为 0，GCS-010 满分不可解读
            density_undefined = waived_files > 0 and scidata_files == 0
            detail["bare_array"] = {"score": 35 if density <= 0.5 else 0,
                                    "density": round(density, 3), "bare_files": bare_files,
                                    "scidata_files": scidata_files,
                                    "waived_files": waived_files,
                                    "density_undefined": density_undefined,
                                    "caveat": ("科学数据文件被 @gcs_waiver 全部豁免，"
                                               "密度恒为 0，本项得分不具参考意义"
                                               if density_undefined else None)}

            # GCS-011：深/浅拷贝
            shallow = self._count(SHALLOW_COPY_RE)
            if shallow == 0:
                score += 30
            detail["copy_semantics"] = {"score": 30 if shallow == 0 else 0, "shallow_count": shallow}

            # GCS-012：数据访问封装
            direct_access = self._count(DIRECT_MEMBER_ACCESS_RE)
            if direct_access == 0:
                score += 35
            detail["access_encapsulation"] = {"score": 35 if direct_access == 0 else 0,
                                              "direct_access_count": direct_access}

            # 递进扣分：2.1 < 60 → 本维度折半
            d1, _ = self.calc_geometry_kernel_consistency()
            if d1 is not None and d1 < 60:
                original = score
                score = int(score * 0.5)
                detail["progressive_deduction"] = {"applied": True, "original": original,
                                                   "deducted": score,
                                                   "reason": "2.1 < 60，增强层折半"}
            else:
                detail["progressive_deduction"] = {"applied": False}

            final = min(score, 100)
            detail["score"] = final
            return final, detail
        return self._calc_cached("data_access", _impl)

    # ── 综合评分 ──

    def calc_overall(self) -> float:
        dims = [
            (self.calc_geometry_kernel_consistency(), self.weights.get("几何内核数据一致性", 0.30)),
            (self.calc_precision_unit_consistency(), self.weights.get("内核精度/单位一致性", 0.20)),
            (self.calc_scidata_organization(), self.weights.get("科学数据结构组织一致性", 0.25)),
            (self.calc_data_access_norm(), self.weights.get("数据表示与访问规范性", 0.25)),
        ]
        total_w = 0
        weighted = 0
        for (score, _), w in dims:
            if score is not None:
                weighted += score * w
                total_w += w
        return round(weighted / max(total_w, 0.01), 2) if total_w > 0 else 0.0

    # ── GCS 规则检查 ──

    def check_gcs_rules(self) -> list:
        if not self._is_geometry:
            return []
        results = []
        d1, d1d = self.calc_geometry_kernel_consistency() or (0, {})

        # GCS-001 加分项缺失提示（INFO，非违规）
        if not d1d.get("closure_check", {}).get("has", True):
            results.append({
                "rule": "GCS-001", "name": "内核闭合性校验测试存在性（加分项）",
                "severity": "LOW", "output_level": "INFO",
                "count": 1, "detail": "未检测到 B-Rep 闭合性校验测试（BRepCheck/BOPCheck），建议补充",
            })

        # GCS-002
        if d1d.get("handle_consistency", {}).get("bare_cross_count", 0) > 0:
            results.append({
                "rule": "GCS-002", "name": "Handle 智能指针一致性",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": d1d["handle_consistency"]["bare_cross_count"],
                "detail": "存在裸 new 内核对象跨作用域穿越，建议 Handle 封装",
            })

        # GCS-003
        if d1d.get("error_propagation", {}).get("missing_check_count", 0) > 0:
            results.append({
                "rule": "GCS-003", "name": "内核异常/失败状态传播",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": d1d["error_propagation"]["missing_check_count"],
                "detail": "内核调用点紧邻未检查 IsDone()/IsValid()，失败可能被静默吞没",
            })

        # GCS-004
        if d1d.get("lifetime_management", {}).get("manual_scope_count", 0) > 0:
            results.append({
                "rule": "GCS-004", "name": "内核对象生命周期",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": d1d["lifetime_management"]["manual_scope_count"],
                "detail": "同作用域手动 new/delete 内核对象，建议 Handle 自动管理",
            })

        d2, d2d = self.calc_precision_unit_consistency() or (0, {})
        # GCS-005
        if d2d.get("precision_magic", {}).get("literal_count", 0) > 0:
            results.append({
                "rule": "GCS-005", "name": "硬编码精度/容差魔法数字",
                "severity": "LOW", "output_level": "INFO",
                "count": d2d["precision_magic"]["literal_count"],
                "detail": "检测到硬编码精度/容差魔法数字，建议集中为命名常量",
            })

        # GCS-006
        if d2d.get("unit_factor", {}).get("factor_count", 0) > 0 and not d2d["unit_factor"].get("has_unit_func", False):
            results.append({
                "rule": "GCS-006", "name": "单位换算魔法因子",
                "severity": "LOW", "output_level": "INFO",
                "count": d2d["unit_factor"]["factor_count"],
                "detail": "检测到单位换算魔法因子，建议统一工具函数",
            })

        d3, d3d = self.calc_scidata_organization() or (0, {})
        # GCS-007
        if d3d.get("mesh_semantics", {}).get("mixed_count", 0) > 0:
            results.append({
                "rule": "GCS-007", "name": "网格单元类型一致性",
                "severity": "HIGH", "output_level": "ERROR",
                "count": d3d["mesh_semantics"]["mixed_count"],
                "detail": "检测到同一数据跨网格语义混用（≥2 类型 + 交叉索引）",
            })

        # GCS-008
        if d3d.get("field_organization", {}).get("inconsistent_count", 0) > 0:
            results.append({
                "rule": "GCS-008", "name": "场量组织一致性",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": d3d["field_organization"]["inconsistent_count"],
                "detail": "场量命名体系混用（pointData vs cellField），建议统一规范",
            })

        # GCS-009
        if d3d.get("dimension_match", {}).get("mismatch_count", 0) > 0:
            results.append({
                "rule": "GCS-009", "name": "网格/场量维度匹配",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": d3d["dimension_match"]["mismatch_count"],
                "detail": "数组维度因子与命名分量常量不一致",
            })

        d4, d4d = self.calc_data_access_norm() or (0, {})
        # GCS-010
        if d4d.get("bare_array", {}).get("density", 0) > 0.5:
            results.append({
                "rule": "GCS-010", "name": "裸数组替代科学数据结构",
                "severity": "LOW", "output_level": "INFO",
                "count": d4d["bare_array"].get("bare_files", 0),
                "detail": "裸数组密度超阈值，建议科学数据结构封装",
            })

        # GCS-011
        if d4d.get("copy_semantics", {}).get("shallow_count", 0) > 0:
            results.append({
                "rule": "GCS-011", "name": "深拷贝 vs 浅拷贝",
                "severity": "LOW", "output_level": "INFO",
                "count": d4d["copy_semantics"]["shallow_count"],
                "detail": "检测到共享底层缓冲的浅拷贝模式",
            })

        # GCS-012
        if d4d.get("access_encapsulation", {}).get("direct_access_count", 0) > 0:
            results.append({
                "rule": "GCS-012", "name": "数据访问封装性",
                "severity": "HIGH", "output_level": "ERROR",
                "count": d4d["access_encapsulation"]["direct_access_count"],
                "detail": "跨模块直接访问内部数据成员",
            })

        return results

    def all_metrics(self) -> dict:
        if not self._is_geometry:
            return {
                "overall": None,
                "is_geometry": False,
                "dimensions": {
                    "geometry_kernel_consistency": {"score": None, "detail": {}},
                    "precision_unit_consistency": {"score": None, "detail": {}},
                    "scidata_organization": {"score": None, "detail": {}},
                    "data_access_norm": {"score": None, "detail": {}},
                },
                "gcs_violations": [],
                "waiver_audit": {},
            }

        d1, dd1 = self.calc_geometry_kernel_consistency()
        d2, dd2 = self.calc_precision_unit_consistency()
        d3, dd3 = self.calc_scidata_organization()
        d4, dd4 = self.calc_data_access_norm()

        weights_order = [
            self.weights.get("几何内核数据一致性", 0.30),
            self.weights.get("内核精度/单位一致性", 0.20),
            self.weights.get("科学数据结构组织一致性", 0.25),
            self.weights.get("数据表示与访问规范性", 0.25),
        ]
        scores = [d1 or 0, d2 or 0, d3 or 0, d4 or 0]
        total_w = sum(weights_order)
        overall = sum(s * w for s, w in zip(scores, weights_order)) / max(total_w, 0.01)

        return {
            "overall": round(overall, 2),
            "is_geometry": True,
            "dimensions": {
                "geometry_kernel_consistency": {"score": d1, "detail": dd1},
                "precision_unit_consistency": {"score": d2, "detail": dd2},
                "scidata_organization": {"score": d3, "detail": dd3},
                "data_access_norm": {"score": d4, "detail": dd4},
            },
            "gcs_violations": self.check_gcs_rules(),
            "waiver_audit": self._waiver_audit(),
            "version_info": {
                "guide_version": GUIDE_VERSION,
                "skill_version": SKILL_VERSION,
            },
        }


def main():
    parser = argparse.ArgumentParser(description="几何内核与科学数据结构一致性评估")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--gcs-only", action="store_true", help="仅检测 GCS 规则")
    args = parser.parse_args()

    metrics = GeometryConsistencyMetrics(args.root)
    if args.gcs_only:
        result = {"gcs_violations": metrics.check_gcs_rules()}
    else:
        result = metrics.all_metrics()

    out_dir = ensure_output_dir(args.root)
    report_path = write_report(out_dir, "geometry-consistency-metrics.json", result)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        vi = result.get("version_info", {})
        print("几何内核与科学数据结构一致性评估")
        print("=" * 50)
        print(f"  Guide version: {vi.get('guide_version', '?')}")
        print(f"  Skill version: {vi.get('skill_version', '?')}")
        print(f"  Is geometry project: {result.get('is_geometry', False)}")
        if result.get("is_geometry", False):
            print(f"  Overall score: {result.get('overall', 'N/A')}")
            dims = result.get("dimensions", {})
            for dk, dv in dims.items():
                print(f"    {dk}: {dv.get('score', 'N/A')}")
            print(f"\n  GCS violations: {len(result.get('gcs_violations', []))}")
            wa = result.get("waiver_audit", {})
            if wa:
                print(f"  Waivers: @kernel_exempt {wa['kernel_exempt']['count']}"
                      f" / @gcs_waiver {wa['gcs_waiver']['count']}")
                if wa.get("invalid_count"):
                    print(f"  [豁免语法缺失] {wa['invalid_count']} 处（缺 reason，豁免无效）")
                if wa.get("abuse_warning"):
                    print(f"  [豁免滥用告警] {wa['abuse_warning']}")
        print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
