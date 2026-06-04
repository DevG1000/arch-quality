"""
arch_multilang_matcher.py — 混合匹配器（pybind11 优先 + ctypes 兜底）

将 Python 端 AST 调用与 C++ 端 pybind11 绑定匹配，生成跨语言边。
未命中 pybind11 时回退到 ctypes 正则（决策 4：保留现有 ctypes 兜底）。

使用示例:
    from arch_core import FileIndex
    from arch_bindings_parser import BindingMap
    from arch_python_ast import extract_pybind11_calls
    from arch_multilang_matcher import build_cross_lang_edges

    idx = FileIndex(root)
    bmap = BindingMap(idx).parse()
    py_calls = [c for f in idx.by_lang("python") for c in extract_pybind11_calls(f["abs_path"])]
    edges = build_cross_lang_edges(idx, bmap, py_calls)
    # → [("scripts/run.py", "src/fvMatrix.cpp"), ...]
"""

import re
from collections import defaultdict
from pathlib import Path



def build_cross_lang_edges(file_index, binding_map, py_calls) -> list:
    """构建跨语言边

    优先级:
    1. pybind11 调用（AST + BindingMap 匹配）
    2. ctypes.CDLL 直接调用（正则兜底）

    返回:
        [(python_file_path, cpp_file_path), ...]  # 已去重
    """
    edges = []

    # 1. pybind11 路径
    for call in py_calls:
        cpp_path = binding_map.lookup(call["module"], call["class"], call["method"])
        if cpp_path is None:
            continue
        # 调用方的 Python 文件路径（用 BindingMap 的 file_index 里的相对路径）
        py_path = _normalize_path(call["file"], file_index)
        cpp_norm = _normalize_path(cpp_path, file_index)
        if py_path and cpp_norm:
            edges.append((py_path, cpp_norm))

    # 2. ctypes 兜底
    ctypes_edges = _build_ctype_edges(file_index)
    edges.extend(ctypes_edges)

    # 3. 去重
    return list(set(edges))


def _normalize_path(path: str, file_index) -> str | None:
    """将绝对或相对路径标准化为 file_index 中的相对路径"""
    if not path:
        return None
    p = Path(path)

    # 1) 如果是绝对路径，且在 file_index.root 下，转相对
    try:
        if p.is_absolute():
            try:
                rel = p.relative_to(file_index.root)
                return str(rel).replace("/", "\\")
            except ValueError:
                # 不在 root 下，尝试按 basename 匹配
                for f in file_index.files:
                    if f["abs_path"] == str(p):
                        return f["path"]
                return None
        # 2) 相对路径：直接使用（已含反斜杠或正斜杠）
        s = str(p)
        # 优先使用 file_index 中已有的等价路径
        for f in file_index.files:
            if f["path"] == s or f["path"] == s.replace("/", "\\"):
                return f["path"]
        # 找不到，标准化返回
        return s.replace("/", "\\")
    except Exception:
        return None


# ctypes 调用正则（保留原 arch_metrics_multilang.py 的检测）
CTYPES_ASSIGN_RE = re.compile(
    r"(\w+)\s*=\s*ctypes\.(?:CDLL|WinDLL|cdll|windll|Library)\("
)
CTYPES_INLINE_RE = re.compile(
    r"ctypes\.(?:CDLL|WinDLL|cdll|windll|Library)\([^)]+\)\s*\.\s*(\w+)"
)
CTYPES_VAR_RE = re.compile(
    r"(\w+)\.(\w+)\s*\("
)
FROM_IMPORT_RE = re.compile(
    r"from\s+(\S+)\s+import\s+(\w+)"
)


def _build_ctype_edges(file_index) -> list:
    """ctypes 调用兜底（保留 arch_metrics_multilang.py 原有逻辑）"""
    edges = []

    # 预扫描所有 C/C++ 头文件函数名
    header_funcs = defaultdict(set)  # {cpp_file: {func_names}}
    for f in file_index.files:
        if f["ext"] not in (".h", ".hpp", ".c", ".cpp", ".cxx", ".cc"):
            continue
        try:
            from arch_quality.arch_core import read_text_smart
            content = read_text_smart(f["abs_path"])
        except Exception:
            continue
        for m in re.finditer(
            r"(?:virtual\s+)?(?:void|int|double|float|bool|char|long|short|unsigned|signed|"
            r"size_t|std::\w+(?:<[^>]*>)?|const\s+\w+)\s+"
            r"(\w+)\s*\(",
            content
        ):
            func = m.group(1)
            if func.startswith("_") or func in ("if", "for", "while", "switch"):
                continue
            header_funcs[f["path"]].add(func)

    # 扫描 Python 文件
    for f in file_index.files:
        if f["lang"] != "python":
            continue
        try:
            from arch_quality.arch_core import read_text_smart
            content = read_text_smart(f["abs_path"])
        except Exception:
            continue

        py_path = f["path"]
        called_funcs = set()

        # 模式 1: ctypes.CDLL("lib").funcName
        for m in CTYPES_INLINE_RE.finditer(content):
            called_funcs.add(m.group(1))

        # 模式 2: lib = ctypes.CDLL(...); lib.funcName
        dll_vars = set()
        for m in CTYPES_ASSIGN_RE.finditer(content):
            dll_vars.add(m.group(1))
        for var in dll_vars:
            for m in re.finditer(rf"\b{re.escape(var)}\.(\w+)\s*\(", content):
                called_funcs.add(m.group(1))

        # 模式 3: from _lib import funcName
        for m in FROM_IMPORT_RE.finditer(content):
            called_funcs.add(m.group(2))

        # 关联到 C 头
        for func in called_funcs:
            for cpp_file, funcs in header_funcs.items():
                if func in funcs:
                    edges.append((py_path, cpp_file))
                    break

    return edges


def summarize_edges(edges: list) -> dict:
    """汇总跨语言边的统计信息"""
    py_to_cpp = defaultdict(set)
    cpp_to_py = defaultdict(set)
    for py, cpp in edges:
        py_to_cpp[py].add(cpp)
        cpp_to_py[cpp].add(py)

    return {
        "total_edges": len(edges),
        "python_files": len(py_to_cpp),
        "cpp_files": len(cpp_to_py),
        "top_cpp_targets": sorted(
            [(cpp, len(pys)) for cpp, pys in cpp_to_py.items()],
            key=lambda x: -x[1]
        )[:10]
    }
