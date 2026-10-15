# -*- coding: utf-8 -*-
"""
arch_metrics_anti_corruption.py — 外部科学内核与几何内核的封装与防腐层评估

实现《外部科学内核与几何内核的封装与防腐层评估指南（1.3版）》定义的 4 维评分模型
和 12 条 ACL 规则（ACL-001~012）的静态分析检测。

版本绑定：
  - 指南版本：1.3
  - Skill 版本：1.0
"""

import os
import re
import json
import argparse
from pathlib import Path

from arch_quality.arch_core import (
    FileIndex,
    load_weights_from_skill, ensure_output_dir, write_report,
    read_text_smart,
)

SKILL_PATH = str(Path(__file__).parent / "skills" / "anti-corruption.md")

GUIDE_VERSION = "1.3"
SKILL_VERSION = "1.0"

# ── 常量定义 ──
CPP_EXTS = {".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".txx", ".h", ".c", ".ixx", ".cppm"}
PY_EXTS = {".py"}
ALL_ACL_EXTS = CPP_EXTS | PY_EXTS

# 外部内核/数据交换信号（启用检测）
KERNEL_SIGNAL_RE = re.compile(
    r"\b(TopoDS_|Handle_|BRep[A-Z_]|Geom_[A-Z_]|CGAL|NCollection_)\w*",
    re.MULTILINE)
DEXCH_SIGNAL_RE = re.compile(
    r"\b(STEPControl_|IGESControl_|IFC|IFSelect_|AP203|AP214|AP242|OCC_VERSION)\w*",
    re.MULTILINE)

# ── 外部符号清单（对齐 Skill §6 / 指南 §7.1）──
# 内核符号集（仅 ACL-001/004/005）
KERNEL_SYMBOL_RE = re.compile(
    r"\b(TopoDS_[A-Za-z_]+|BRep[A-Za-z_]+|Handle[A-Za-z_]*|CGAL)\b")
# 格式符号集（仅 ACL-007/011/012）
FORMAT_SYMBOL_RE = re.compile(
    r"\b(STEPControl_[A-Za-z_]+|IGESControl_[A-Za-z_]+|IFSelect_[A-Za-z_]+|IFC[A-Za-z_]*)\b")

# ACL-001 直连内核 API：wrapper 白名单外引用内核符号
# 内核符号捕获含 Handle(TopoDS_Shape) 形态
RAW_KERNEL_USE_RE = re.compile(
    r"\b(TopoDS_|BRep[A-Za-z_]*|Handle\s*\([^)]+\)|CGAL)\b")

# ACL-004 内核类型泄漏：wrapper 公开头文件签名出现外部类型
# public/protected 方法签名中返回或入参 TopoDS_/Handle_
TYPE_LEAK_RE = re.compile(
    r"(?:public|protected)\s*:\s*[^;{}]*?\b(?:TopoDS_[A-Za-z_]+|Handle\s*\([^)]+\))\s*(\*|\s+\w+\s*\()",
    re.MULTILINE | re.DOTALL)
# 更宽的签名泄漏：返回类型捕获（TopoDS_Shape f( / Handle(Geom_Surface) f( ）
PUBLIC_SIG_LEAK_RE = re.compile(
    r"^\s*(?:virtual\s+|inline\s+|explicit\s+|static\s+)*(?:TopoDS_[A-Za-z_]+|Handle\s*\([^)]+\))\s+[A-Za-z_]\w*\s*\(",
    re.MULTILINE)

# ACL-005 错误处理封装：内核调用点紧邻失败检查
# 状态码型内核（OCCT）+ 异常型内核
KERNEL_CALL_STMT_RE = re.compile(
    r"\b(BRepAlgoAPI_[A-Za-z_]+|BRepBuilderAPI_[A-Za-z_]+|BRepPrimAPI_[A-Za-z_]+)\s+(\w+)\s*\([^;]*\);",
    re.MULTILINE)
ERROR_CHECK_RE = re.compile(
    r"\.IsDone\s*\(|\.IsValid\s*\(|catch\s*\(|IFSelect_ReturnStatus|!=?\s*IFSelect_RetDone|\berror\b|\bcatch\s*\([^)]*\)")
# 例外：格式读写调用点明确排除（归 ACL-011）
FORMAT_CALL_RE = re.compile(
    r"\b(STEPControl_Reader|STEPControl_Writer|IGESControl_Reader|IGESControl_Writer|IFC[A-Za-z_]*)\b")

# ACL-002 核心 API wrapper 覆盖度
# 可枚举核心内核类清单（OCCT 高频建模/布尔操作类）
CORE_KERNEL_CLASS_RE = re.compile(
    r"\b(BRepAlgoAPI_Fuse|BRepAlgoAPI_Cut|BRepAlgoAPI_Common|BRepAlgoAPI_BooleanOperation"
    r"|BRepBuilderAPI_MakeEdge|BRepBuilderAPI_MakeFace|BRepBuilderAPI_MakeWire"
    r"|BRepPrimAPI_MakeBox|BRepPrimAPI_MakeCylinder|BRepFilletAPI_MakeFillet|BRepFilletAPI_MakeChamfer"
    r"|BRep_Tool|BRepCheck_Analyzer|Geom_Plane|Geom_CylindricalSurface|TopoDS_Shape)\b")
# wrapper 目录中出现的核心类声明（Wrapper 封装了该类）
CORE_KERNEL_DECL_RE = re.compile(
    r"\b(BRepAlgoAPI_Fuse|BRepBuilderAPI_MakeFace|BRepPrimAPI_MakeBox|BRep_Tool|BRepCheck_Analyzer"
    r"|Geom_Plane|TopoDS_Shape)\b")

# ACL-003 内核版本守卫
VERSION_GUARD_RE = re.compile(r"\b#if\s+(?:defined\s*\(\s*)?OCC_VERSION\b|#\s*if\s+OCC_VERSION", re.MULTILINE)
GENERIC_VERSION_GUARD_RE = re.compile(
    r"#\s*if\s+(?:defined\s*\(\s*)?(?:[A-Z_]+_VERSION|OCC_VERSION)\b", re.MULTILINE)

# ACL-006 round-trip 往返保真度测试存在性（加分项）
ROUND_TRIP_RE = re.compile(
    r"\b(round_trip|roundtrip|round.?trip|write_and_read|write.read|export_import_test)\w*\b",
    re.IGNORECASE)
WRITE_READ_ASSERT_RE = re.compile(
    r"(?:writer|export).{0,80}(?:reader|import).{0,120}(?:assert|EXPECT_|ALWAYS|IsDone|ASSERT_)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE)

# ACL-007 STEP/IGES/IFC 读写防腐：格式符号在 import/export 模块白名单外
# 复用 FORMAT_SYMBOL_RE

# ACL-008 单位换算魔法因子（数据交换上下文）
EXCH_UNIT_FACTOR_RE = re.compile(r"\b(25\.4|0\.0254|3\.28084|0\.3048|2\.54|1\.60934|0\.0393701)\b")
EXCH_UNIT_FUNC_RE = re.compile(
    r"\b(convert|unit::|UnitsMethods|to_mm|to_inch|to_meter|SetUnit|SetCVal|write\.step\.unit)\w*")

# ACL-009 公差换算魔法因子
TOL_FACTOR_RE = re.compile(r"\b(0\.0254|0\.001|0\.0001|1e-\s?[0-9]+)\b")
TOL_FUNC_RE = re.compile(r"\b(tol|tolerance|SetTolerance|convert_tol|Tolerance)\w*")

# ACL-010 标准版本守卫（AP203/214/242）
AP_VERSION_RE = re.compile(r"\bAP-?(203|214|242)\b")
STEP_PROFILE_SET_RE = re.compile(
    r"\bSetProfile|SetSchema|SetCVal\s*\(\s*[\"'](?:write\.step|read\.step)[\"']|SUPPORT_AP\d{3}\b",
    re.MULTILINE)

# ACL-011 导入导出错误处理
READER_OBJ_RE = re.compile(
    r"\b(STEPControl_Reader|IGESControl_Reader|IFSelect_)\w*\s+(\w+)\s*(?:;|,|\()")
WRITER_OBJ_RE = re.compile(
    r"\b(STEPControl_Writer|IGESControl_Writer)\w*\s+(\w+)\s*(?:;|,|\()")
READFUNC_ERR_RE = re.compile(
    r"\.ReadFile\s*\([^;]*\)|\.TransferRoots\s*\([^;]*\)|\.Write\s*\([^;]*\)")
RET_STATUS_CHECK_RE = re.compile(
    r"IFSelect_ReturnStatus\b|IFSelect_RetDone\b|\.IsDone\s*\(|catch\s*\(")

# ACL-012 格式直连密度：格式符号在专用模块外引用（密度阈值）
FORMAT_USE_RE = re.compile(
    r"\b(STEPControl_|IGESControl_|IFSelect_|IFC)\w*\b")

# ── 防腐边界目录（wrapper / import-export 模块白名单）──
WRAPPER_DIR_NAMES = {
    "wrapper", "wrappers", "adaptor", "adaptors", "facade", "adapter", "adapters",
    "cad_ops", "geom_ops", "geometry_wrapper", "api",
}
IMPORT_EXPORT_DIR_NAMES = {
    "importexport", "import_export", "io", "exch", "exchange", "dataexchange",
    "step", "iges", "ifc", "data_exchange", "inout", "serialization",
}
# 被评估对象本身即外部内核（vendored 内核源码）目录
THIRD_PARTY_DIR_NAMES = {
    "third_party", "thirdparty", "3rdparty", "external", "vendor",
    "deps", "dependencies", "libs", "external_libs",
}

# ── 豁免注解（对齐 Skill §8）──
ACL_EXEMPT_RE = re.compile(r"/\*\s*@acl_exempt\s*:\s*(?P<reason>\S[^*\n]*?)\s*\*/")
ACL_EXEMPT_INVALID_RE = re.compile(r"/\*\s*@acl_exempt\s*(?::\s*)?\*/")
ACL_WAIVER_RE = re.compile(r"//\s*@acl_waiver\s*:\s*(?P<reason>\S[^\n]*?)\s*$", re.MULTILINE)
ACL_WAIVER_INVALID_RE = re.compile(r"//\s*@acl_waiver\s*(?::\s*)?$", re.MULTILINE)

WAIVER_ABUSE_RATIO_LIMIT = 0.30

# ACL-012 直连密度阈值（WP-4 校准，默认 0.30）
FORMAT_DIRECT_DENSITY_LIMIT = 0.30


def _strip_comments(content: str) -> str:
    """剥离 C/C++ 行注释 // 与块注释 /* */"""
    content = re.sub(r"//[^\n]*", "", content)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    return content


def _scope_until_brace(text: str, max_chars: int = 800) -> str:
    """截取当前函数体范围：从调用点后到叶级 }（括号深度回到 0）或文件尾。

    用于 ACL-005 错误检查窗口——限定在调用点所属函数体内，
    避免跨函数同名变量（如 do_cut 的 op）造成的误判（变异测试 MUT-ACL-005 暴露）。
    """
    depth = 0
    for i, ch in enumerate(text[:max_chars]):
        if ch == "{":
            depth += 1
        elif ch == "}":
            if depth == 0:
                return text[:i]   # 到达调用点所在函数/语句块的闭合
            depth -= 1
    return text[:max_chars]


def _is_occt_exception_type(error_check_found: bool) -> bool:
    """占位：异常型内核策略标记（当前通过 ERROR_CHECK_RE 通用覆盖）"""
    return error_check_found


def _detect_acl(root: str, index: FileIndex) -> bool:
    """启用检测：源码含外部内核或数据交换标准信号"""
    source_files = [f for f in index.files if f["ext"] in ALL_ACL_EXTS]
    for f in source_files[:300]:
        try:
            content = _strip_comments(read_text_smart(f["abs_path"]))
        except Exception:
            continue
        if KERNEL_SIGNAL_RE.search(content) or DEXCH_SIGNAL_RE.search(content):
            return True
    return False


class AntiCorruptionMetrics:
    """外部科学内核与几何内核的封装与防腐层评估"""

    def __init__(self, root: str, wrapper_dirs: list = None,
                 import_export_dirs: list = None):
        self.root = root
        self.index = FileIndex(root)
        self.weights = {}
        self._all_contents = {}        # abs_path → content（已剥离注释）
        self._acl_exempt = {}          # rel_path → reason（@acl_exempt，12 规则全排除）
        self._acl_waiver = {}          # rel_path → reason（@acl_waiver，仅 ACL-001/012）
        self._invalid_waivers = []
        self._is_acl = False
        self._dims_cache = {}
        # 防腐边界目录白名单（可配置，默认识别常见目录名）
        self._wrapper_dirs = set(wrapper_dirs or WRAPPER_DIR_NAMES) | {
            d.lower() for d in (wrapper_dirs or [])}
        self._import_export_dirs = set(import_export_dirs or IMPORT_EXPORT_DIR_NAMES)
        self._init_weights()
        self._is_acl = _detect_acl(root, self.index)
        if self._is_acl:
            self._scan_files()

    def _init_weights(self):
        _DIM_KEYS = {"外部内核访问防腐", "Wrapper 覆盖度与演进守卫",
                     "数据交换防腐", "保真度与外部标准一致性"}
        try:
            raw = load_weights_from_skill(SKILL_PATH)
            self.weights = {k: v for k, v in raw.items() if k in _DIM_KEYS}
            if len(self.weights) != 4:
                raise ValueError(f"只解析到 {len(self.weights)} 个维度权重")
        except Exception:
            self.weights = {
                "外部内核访问防腐": 0.30,
                "Wrapper 覆盖度与演进守卫": 0.15,
                "数据交换防腐": 0.30,
                "保真度与外部标准一致性": 0.25,
            }

    def _rel_path(self, abs_path: str) -> str:
        try:
            return os.path.relpath(abs_path, self.root).replace("\\", "/")
        except ValueError:
            return str(abs_path).replace("\\", "/")

    def _scan_files(self):
        for f in self.index.files:
            if f["ext"] not in ALL_ACL_EXTS:
                continue
            try:
                raw = read_text_smart(f["abs_path"])
            except Exception:
                continue
            rel = self._rel_path(f["abs_path"])
            m = ACL_EXEMPT_RE.search(raw)
            if m:
                self._acl_exempt[rel] = m.group("reason").strip()
            elif ACL_EXEMPT_INVALID_RE.search(raw):
                self._invalid_waivers.append(
                    {"file": rel, "annotation": "@acl_exempt",
                     "issue": "缺少 reason，豁免无效"})
            wm = ACL_WAIVER_RE.search(raw)
            if wm:
                self._acl_waiver[rel] = wm.group("reason").strip()
            elif ACL_WAIVER_INVALID_RE.search(raw):
                self._invalid_waivers.append(
                    {"file": rel, "annotation": "@acl_waiver",
                     "issue": "缺少 reason，豁免无效"})
            self._all_contents[f["abs_path"]] = _strip_comments(raw)

    def _in_wrapper_dir(self, abs_path: str) -> bool:
        try:
            rel = os.path.relpath(abs_path, self.root)
        except ValueError:
            return False
        return any(p.lower() in self._wrapper_dirs for p in Path(rel).parts)

    def _in_import_export_dir(self, abs_path: str) -> bool:
        try:
            rel = os.path.relpath(abs_path, self.root)
        except ValueError:
            return False
        parts = Path(rel).parts
        return any(p.lower() in self._import_export_dirs for p in parts)

    def _is_third_party(self, abs_path: str) -> bool:
        try:
            rel = os.path.relpath(abs_path, self.root)
        except ValueError:
            return False
        parts = Path(rel).parts
        return any(p.lower() in THIRD_PARTY_DIR_NAMES for p in parts)

    def _is_test_file(self, abs_path: str) -> bool:
        try:
            rel = os.path.relpath(abs_path, self.root)
        except ValueError:
            return False
        low = rel.lower().replace("\\", "/")
        return any(k in part for part in low.split("/")
                   for k in ("test", "qa", "sample", "example", "demo"))

    def _skip(self, abs_path: str, exclude_test: bool = False) -> bool:
        """统一排除判定（对齐 GCS _skip）：
        第三方面目录 > @acl_exempt 注解 > 测试/QA（可选）
        """
        if self._is_third_party(abs_path):
            return True
        if self._rel_path(abs_path) in self._acl_exempt:
            return True
        if exclude_test and self._is_test_file(abs_path):
            return True
        return False

    def _waiver_audit(self) -> dict:
        total = max(1, len(self._all_contents))
        ae_count = len(self._acl_exempt)
        aw_count = len(self._acl_waiver)
        ae_ratio = round(ae_count / total, 4)
        aw_ratio = round(aw_count / total, 4)
        # 防腐边界目录覆盖（wrapper + import/export 目录文件占比）
        bd_files = [p for p in self._all_contents
                    if self._in_wrapper_dir(p) or self._in_import_export_dir(p)]
        bd_ratio = round(len(bd_files) / total, 4) if total else 0.0
        limit = WAIVER_ABUSE_RATIO_LIMIT
        warnings = []
        if ae_ratio > limit:
            warnings.append(
                f"@acl_exempt 排除占比 {ae_ratio:.1%} 超过上限 {limit:.0%}，"
                f"12 条规则覆盖度可能失真，请复核豁免必要性")
        if aw_ratio > limit:
            warnings.append(
                f"@acl_waiver 排除占比 {aw_ratio:.1%} 超过上限 {limit:.0%}，"
                f"ACL-001/012 计数可能被豁免抬高，请复核受控直连声明")
        if bd_ratio > limit:
            warnings.append(
                f"防腐边界目录覆盖占比 {bd_ratio:.1%} 超过上限 {limit:.0%}，"
                f"项目大比例被声明为 wrapper/import-export，防腐评估可能失真")
        return {
            "acl_exempt": {
                "count": ae_count, "ratio": ae_ratio,
                "scope": "全部 12 条规则",
                "files": sorted(self._acl_exempt)[:20],
            },
            "acl_waiver": {
                "count": aw_count, "ratio": aw_ratio,
                "scope": "仅 ACL-001/012（直连/散落计数剔除）",
                "files": sorted(self._acl_waiver)[:20],
            },
            "boundary_dir_exclusion": {
                "count": len(bd_files), "ratio": bd_ratio,
                "scope": "wrapper/import-export 模块目录",
                "wrapper_dirs": sorted(self._wrapper_dirs),
                "import_export_dirs": sorted(self._import_export_dirs),
            },
            "invalid_waivers": self._invalid_waivers[:20],
            "invalid_count": len(self._invalid_waivers),
            "abuse_limit": limit,
            "abuse_warning": "；".join(warnings) if warnings else None,
        }

    def _count(self, pattern: re.Pattern) -> int:
        total = 0
        for abs_path, content in self._all_contents.items():
            if self._skip(abs_path):
                continue
            total += len(pattern.findall(content))
        return total

    def _any(self, pattern: re.Pattern, exclude_test: bool = False) -> bool:
        for abs_path, content in self._all_contents.items():
            if self._skip(abs_path, exclude_test=exclude_test):
                continue
            if pattern.search(content):
                return True
        return False

    def _calc_cached(self, name, fn):
        if name not in self._dims_cache:
            self._dims_cache[name] = fn()
        return self._dims_cache[name]

    # ── 维度 1：外部内核访问防腐（30%）──

    def calc_external_access(self) -> tuple:
        def _impl():
            if not self._is_acl:
                return None, {}
            score = 0
            detail = {}

            # ACL-001：直连内核 API（wrapper 白名单外引用内核符号）
            direct = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path):
                    continue
                if self._in_wrapper_dir(abs_path):
                    continue
                direct += len(RAW_KERNEL_USE_RE.findall(content))
            if direct == 0:
                score += 40
            detail["direct_access"] = {"score": 40 if direct == 0 else 0,
                                       "direct_count": direct}

            # ACL-004：内核类型泄漏（wrapper 公开头文件签名）
            # 仅评估 wrapper 目录内头文件；公开签名出现 TopoDS_/Handle_
            leak = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path):
                    continue
                if not self._in_wrapper_dir(abs_path):
                    continue
                if abs_path.endswith((".h", ".hpp", ".hxx", ".hh")):
                    leak += len(PUBLIC_SIG_LEAK_RE.findall(content)) \
                        + len(TYPE_LEAK_RE.findall(content))
            if leak == 0:
                score += 30
            detail["type_leak"] = {"score": 30 if leak == 0 else 0,
                                   "leak_count": leak}

            # ACL-005：错误处理封装（内核调用点紧邻失败检查；格式读写排除）
            # 窗口范围：当前函数体（到下一个叶级 }，含嵌套平衡），避免跨函数同名变量误判
            missing = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path, exclude_test=True):
                    continue
                for m in KERNEL_CALL_STMT_RE.finditer(content):
                    call_blob = m.group(0)
                    if FORMAT_CALL_RE.search(call_blob):
                        continue  # 格式读写调用点归 ACL-011，明确排除
                    var = m.group(2)
                    rest = content[m.end():]
                    # 截取到当前函数体结束（叶级 } 或文件尾，最多 800 字符）
                    # 状态码型内核的检查需引用同一变量（var.IsDone）或通用失败模式
                    scope_end = _scope_until_brace(rest)
                    check_pat = re.compile(
                        r"(?:IFSelect_ReturnStatus|IFSelect_RetDone)\b|"
                        r"\b" + re.escape(var) + r"\s*\.\s*(?:IsDone|IsValid)\s*\(|"
                        r"catch\s*\(")
                    if check_pat.search(scope_end):
                        continue
                    missing += 1
            if missing == 0:
                score += 30
            detail["error_handling"] = {"score": 30 if missing == 0 else 0,
                                        "missing_check_count": missing}

            final = min(score, 100)
            detail["score"] = final
            return final, detail
        return self._calc_cached("ext_access", _impl)

    # ── 维度 2：Wrapper 覆盖度与演进守卫（15%）──

    def calc_wrapper_coverage(self) -> tuple:
        def _impl():
            if not self._is_acl:
                return None, {}
            score = 0
            detail = {}

            # ACL-002：核心 API wrapper 覆盖度
            core_used = set()
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path):
                    continue
                core_used.update(CORE_KERNEL_CLASS_RE.findall(content))
            wrapper_decl = set()
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path):
                    continue
                if not self._in_wrapper_dir(abs_path):
                    continue
                wrapper_decl.update(CORE_KERNEL_DECL_RE.findall(content))
            uncovered = sorted(core_used - wrapper_decl)
            coverage = round(len(wrapper_decl & core_used) / max(1, len(core_used)), 3)
            if coverage >= 0.6:
                score += 50
            detail["coverage"] = {"score": 50 if coverage >= 0.6 else 0,
                                  "coverage": coverage,
                                  "core_used": sorted(core_used)[:30],
                                  "wrapper_decl": sorted(wrapper_decl)[:30],
                                  "uncovered": uncovered[:30]}

            # ACL-003：内核版本守卫存在性
            guard_cnt = self._count(GENERIC_VERSION_GUARD_RE)
            if guard_cnt > 0:
                score += 50
            detail["version_guard"] = {"score": 50 if guard_cnt > 0 else 0,
                                       "guard_count": guard_cnt}

            final = min(score, 100)
            detail["score"] = final
            return final, detail
        return self._calc_cached("wrap_cov", _impl)

    # ── 维度 3：数据交换防腐（30%）──

    def calc_data_exchange(self) -> tuple:
        def _impl():
            if not self._is_acl:
                return None, {}
            score = 0
            detail = {}

            # ACL-007：格式符号白名单外散落（import/export 模块外引用）
            scatter = 0
            implementation_count = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path):
                    continue
                if self._in_import_export_dir(abs_path):
                    continue
                n = len(FORMAT_SYMBOL_RE.findall(content))
                scatter += n
                if n > 0:
                    implementation_count += 1
            if scatter == 0:
                score += 45
            detail["exchange_anti_corruption"] = {
                "score": 45 if scatter == 0 else 0,
                "scatter_count": scatter, "scattered_files": implementation_count}

            # ACL-011：导入导出错误处理
            # reader/writer 对象构造后，其 ReadFile/TransferRoots/Write 调用
            # 若无紧邻错误检查（IFSelect_ReturnStatus/RetDone/catch）→ WARNING
            bad_read = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path, exclude_test=True):
                    continue
                for m in READER_OBJ_RE.finditer(content):
                    obj = m.group(2)
                    # 找该对象的读写调用后续上下文（ReadFile/TransferRoots）
                    rest = content[m.end():]
                    err_pat = re.compile(
                        r"(?:IFSelect_ReturnStatus|IFSelect_RetDone)\b|"
                        r"\b" + re.escape(obj) + r"\s*\.\s*IsDone\s*\(|catch\s*\(")
                    if err_pat.search(rest[:800]):
                        continue
                    bad_read += 1
                for m in WRITER_OBJ_RE.finditer(content):
                    obj = m.group(2)
                    rest = content[m.end():]
                    err_pat = re.compile(
                        r"(?:IFSelect_ReturnStatus|IFSelect_RetDone)\b|catch\s*\(")
                    if err_pat.search(rest[:800]):
                        continue
                    bad_read += 1
            if bad_read == 0:
                score += 30
            detail["exch_error_handling"] = {"score": 30 if bad_read == 0 else 0,
                                             "bad_read_count": bad_read}

            # ACL-012：格式直连密度
            format_files = 0
            outside_files = 0
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path):
                    continue
                if FORMAT_USE_RE.search(content):
                    format_files += 1
                    if not self._in_import_export_dir(abs_path):
                        outside_files += 1
            density = round(outside_files / max(1, format_files), 3)
            if format_files == 0 or density <= FORMAT_DIRECT_DENSITY_LIMIT:
                score += 25
            detail["format_direct"] = {"score": 25 if (format_files == 0
                                        or density <= FORMAT_DIRECT_DENSITY_LIMIT) else 0,
                                       "density": density,
                                       "format_files": format_files,
                                       "outside_files": outside_files}

            final = min(score, 100)
            detail["score"] = final
            return final, detail
        return self._calc_cached("data_exch", _impl)

    # ── 维度 4：保真度与外部标准一致性（25%）──

    def calc_fidelity(self) -> tuple:
        def _impl():
            if not self._is_acl:
                return None, {}
            score = 0
            detail = {}

            # ACL-006：round-trip 测试存在（加分项）
            has_rt = self._any(ROUND_TRIP_RE, exclude_test=False) or \
                self._any(WRITE_READ_ASSERT_RE, exclude_test=False)
            if has_rt:
                score += 40
            detail["round_trip"] = {"score": 40 if has_rt else 0, "has": has_rt}

            # ACL-008：单位换算魔法因子（数据交换上下文）
            unit_factors = 0
            unit_func = False
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path):
                    continue
                unit_factors += len(EXCH_UNIT_FACTOR_RE.findall(content))
                if EXCH_UNIT_FUNC_RE.search(content):
                    unit_func = True
            if unit_factors == 0 or unit_func:
                score += 20
            detail["unit_factor"] = {"score": 20 if (unit_factors == 0 or unit_func) else 0,
                                     "factor_count": unit_factors, "has_unit_func": unit_func}

            # ACL-009：公差换算魔法因子
            tol_factors = 0
            tol_func = False
            for abs_path, content in self._all_contents.items():
                if self._skip(abs_path):
                    continue
                tol_factors += len(TOL_FACTOR_RE.findall(content))
                if TOL_FUNC_RE.search(content):
                    tol_func = True
            if tol_factors == 0 or tol_func:
                score += 20
            detail["tol_factor"] = {"score": 20 if (tol_factors == 0 or tol_func) else 0,
                                    "factor_count": tol_factors, "has_tol_func": tol_func}

            # ACL-010：标准版本守卫
            ap_decl = self._any(AP_VERSION_RE) or self._any(STEP_PROFILE_SET_RE)
            if ap_decl:
                score += 20
            detail["std_version_guard"] = {"score": 20 if ap_decl else 0,
                                           "has_version_guard": ap_decl}

            # 递进扣分：任一基础层 < 60 → 本维度折半
            d1, _ = self.calc_external_access()
            d3, _ = self.calc_data_exchange()
            if (d1 is not None and d1 < 60) or (d3 is not None and d3 < 60):
                original = score
                score = int(score * 0.5)
                detail["progressive_deduction"] = {
                    "applied": True, "original": original, "deducted": score,
                    "reason": "任一基础层（2.1 或 2.3）< 60，增强层折半"}
            else:
                detail["progressive_deduction"] = {"applied": False}

            final = min(score, 100)
            detail["score"] = final
            return final, detail
        return self._calc_cached("fidelity", _impl)

    # ── 综合评分 ──

    def calc_overall(self) -> float:
        dims = [
            (self.calc_external_access(), self.weights.get("外部内核访问防腐", 0.30)),
            (self.calc_wrapper_coverage(), self.weights.get("Wrapper 覆盖度与演进守卫", 0.15)),
            (self.calc_data_exchange(), self.weights.get("数据交换防腐", 0.30)),
            (self.calc_fidelity(), self.weights.get("保真度与外部标准一致性", 0.25)),
        ]
        total_w = 0
        weighted = 0
        for (score, _), w in dims:
            if score is not None:
                weighted += score * w
                total_w += w
        return round(weighted / max(total_w, 0.01), 2) if total_w > 0 else 0.0

    # ── ACL 规则检查 ──

    def check_acl_rules(self) -> list:
        if not self._is_acl:
            return []
        results = []
        d1, d1d = self.calc_external_access() or (0, {})
        d2, d2d = self.calc_wrapper_coverage() or (0, {})
        d3, d3d = self.calc_data_exchange() or (0, {})
        d4, d4d = self.calc_fidelity() or (0, {})

        # ACL-001
        if d1d.get("direct_access", {}).get("direct_count", 0) > 0:
            results.append({
                "rule": "ACL-001", "name": "直连内核 API",
                "severity": "HIGH", "output_level": "ERROR",
                "count": d1d["direct_access"]["direct_count"],
                "detail": "wrapper 目录白名单外引用外部内核符号，建议收敛到防腐边界内",
            })
        # ACL-002
        if d2d.get("coverage", {}).get("coverage", 1) < 0.6:
            results.append({
                "rule": "ACL-002", "name": "核心 API wrapper 覆盖度",
                "severity": "LOW", "output_level": "INFO",
                "count": len(d2d.get("coverage", {}).get("uncovered", [])),
                "detail": "核心内核 API 覆盖度不足，业务层可能被迫直连",
            })
        # ACL-003
        if d2d.get("version_guard", {}).get("guard_count", 0) == 0:
            results.append({
                "rule": "ACL-003", "name": "内核版本守卫",
                "severity": "LOW", "output_level": "INFO",
                "count": 0,
                "detail": "未检测到 #if OCC_VERSION 版本守卫，升级影响面无法隔离",
            })
        # ACL-004
        if d1d.get("type_leak", {}).get("leak_count", 0) > 0:
            results.append({
                "rule": "ACL-004", "name": "内核类型泄漏",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": d1d["type_leak"]["leak_count"],
                "detail": "wrapper 公开头文件签名出现外部内核类型，建议自有类型映射",
            })
        # ACL-005
        if d1d.get("error_handling", {}).get("missing_check_count", 0) > 0:
            results.append({
                "rule": "ACL-005", "name": "错误处理封装",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": d1d["error_handling"]["missing_check_count"],
                "detail": "内核调用点紧邻未检查失败状态，建议统一封装",
            })
        # ACL-006
        if not d4d.get("round_trip", {}).get("has", False):
            results.append({
                "rule": "ACL-006", "name": "数据交换往返保真度测试存在性（加分项）",
                "severity": "LOW", "output_level": "INFO",
                "count": 0, "detail": "未检测到数据交换 round-trip 保真度测试，建议补充",
            })
        # ACL-007
        if d3d.get("exchange_anti_corruption", {}).get("scatter_count", 0) > 0:
            results.append({
                "rule": "ACL-007", "name": "STEP/IGES/IFC 读写防腐",
                "severity": "HIGH", "output_level": "ERROR",
                "count": d3d["exchange_anti_corruption"]["scatter_count"],
                "detail": "格式符号出现在 import/export 模块白名单外，建议收敛到集中模块",
            })
        # ACL-008
        if d4d.get("unit_factor", {}).get("factor_count", 0) > 0 \
                and not d4d["unit_factor"].get("has_unit_func", False):
            results.append({
                "rule": "ACL-008", "name": "单位换算魔法因子",
                "severity": "LOW", "output_level": "INFO",
                "count": d4d["unit_factor"]["factor_count"],
                "detail": "数据交换上下文检测到单位换算魔法因子，建议统一换算函数",
            })
        # ACL-009
        if d4d.get("tol_factor", {}).get("factor_count", 0) > 0 \
                and not d4d["tol_factor"].get("has_tol_func", False):
            results.append({
                "rule": "ACL-009", "name": "公差换算魔法因子",
                "severity": "LOW", "output_level": "INFO",
                "count": d4d["tol_factor"]["factor_count"],
                "detail": "数据交换上下文检测到公差换算魔法因子，建议统一管理",
            })
        # ACL-010
        if not d4d.get("std_version_guard", {}).get("has_version_guard", False):
            results.append({
                "rule": "ACL-010", "name": "标准版本守卫",
                "severity": "LOW", "output_level": "INFO",
                "count": 0, "detail": "未检测到外部标准版本（AP203/214/242）声明/守卫",
            })
        # ACL-011
        if d3d.get("exch_error_handling", {}).get("bad_read_count", 0) > 0:
            results.append({
                "rule": "ACL-011", "name": "导入导出错误处理",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": d3d["exch_error_handling"]["bad_read_count"],
                "detail": "reader/writer 调用点未检查 IFSelect_ReturnStatus/异常",
            })
        # ACL-012
        dd = d3d.get("format_direct", {})
        if dd.get("format_files", 0) > 0 and dd.get("density", 0) > FORMAT_DIRECT_DENSITY_LIMIT:
            results.append({
                "rule": "ACL-012", "name": "格式直连检测",
                "severity": "MEDIUM", "output_level": "WARNING",
                "count": dd.get("outside_files", 0),
                "detail": "格式符号在专用模块外引用密度超阈值（仅 ACL-007 散落场景叠加）",
            })
        return results

    def all_metrics(self) -> dict:
        if not self._is_acl:
            return {
                "overall": None,
                "is_acl": False,
                "dimensions": {
                    "external_access": {"score": None, "detail": {}},
                    "wrapper_coverage": {"score": None, "detail": {}},
                    "data_exchange": {"score": None, "detail": {}},
                    "fidelity": {"score": None, "detail": {}},
                },
                "acl_violations": [],
                "waiver_audit": {},
            }

        d1, dd1 = self.calc_external_access()
        d2, dd2 = self.calc_wrapper_coverage()
        d3, dd3 = self.calc_data_exchange()
        d4, dd4 = self.calc_fidelity()

        weights_order = [
            self.weights.get("外部内核访问防腐", 0.30),
            self.weights.get("Wrapper 覆盖度与演进守卫", 0.15),
            self.weights.get("数据交换防腐", 0.30),
            self.weights.get("保真度与外部标准一致性", 0.25),
        ]
        scores = [d1 or 0, d2 or 0, d3 or 0, d4 or 0]
        total_w = sum(weights_order)
        overall = sum(s * w for s, w in zip(scores, weights_order)) / max(total_w, 0.01)

        return {
            "overall": round(overall, 2),
            "is_acl": True,
            "dimensions": {
                "external_access": {"score": d1, "detail": dd1},
                "wrapper_coverage": {"score": d2, "detail": dd2},
                "data_exchange": {"score": d3, "detail": dd3},
                "fidelity": {"score": d4, "detail": dd4},
            },
            "acl_violations": self.check_acl_rules(),
            "waiver_audit": self._waiver_audit(),
            "version_info": {
                "guide_version": GUIDE_VERSION,
                "skill_version": SKILL_VERSION,
            },
        }


# ── 函数入口 ──

def main():
    parser = argparse.ArgumentParser(description="外部科学内核与几何内核的封装与防腐层评估")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--acl-only", action="store_true", help="仅检测 ACL 规则")
    args = parser.parse_args()

    metrics = AntiCorruptionMetrics(args.root)
    if args.acl_only:
        result = {"acl_violations": metrics.check_acl_rules()}
    else:
        result = metrics.all_metrics()

    out_dir = ensure_output_dir(args.root)
    report_path = write_report(out_dir, "anti-corruption-metrics.json", result)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        vi = result.get("version_info", {})
        print("外部科学内核与几何内核的封装与防腐层评估")
        print("=" * 50)
        print(f"  Guide version: {vi.get('guide_version', '?')}")
        print(f"  Skill version: {vi.get('skill_version', '?')}")
        print(f"  Is ACL project: {result.get('is_acl', False)}")
        if result.get("is_acl", False):
            print(f"  Overall score: {result.get('overall', 'N/A')}")
            dims = result.get("dimensions", {})
            for dk, dv in dims.items():
                print(f"    {dk}: {dv.get('score', 'N/A')}")
            print(f"\n  ACL violations: {len(result.get('acl_violations', []))}")
            wa = result.get("waiver_audit", {})
            if wa:
                print(f"  Waivers: @acl_exempt {wa['acl_exempt']['count']}"
                      f" / @acl_waiver {wa['acl_waiver']['count']}")
                if wa.get("invalid_count"):
                    print(f"  [豁免语法缺失] {wa['invalid_count']} 处（缺 reason，豁免无效）")
                if wa.get("abuse_warning"):
                    print(f"  [豁免滥用告警] {wa['abuse_warning']}")
        print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()