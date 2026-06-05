"""
arch_metrics_multilang.py — 多语言混合依赖评估指标

实现 多语言混合依赖评估指南.md 中的 6 个评估维度和 12 条 MLR 规则。
权重从 skills/multilang-dependency.md 动态解析。
"""

import os
import re
import json
import argparse
from pathlib import Path
from collections import defaultdict

from arch_quality.arch_core import (
    FileIndex, DepGraph, GitHistory,
    load_weights_from_skill, ensure_output_dir,
    write_report, write_text_utf8,
    read_text_smart
)

SKILL_PATH = str(Path(__file__).parent / "skills" / "multilang-dependency.md")


def _collect_std_imports(index):
    """Collect Python import statements and resolve them to project-internal targets.

    Returns a set of (source_file, target_file) pairs where both ends are project files.
    Uses the same import-to-target resolution logic as StandardMetrics._build_graph.
    """
    internal_edges = set()
    node_lookup = {}
    for f in index.files:
        basename = os.path.splitext(os.path.basename(f["path"]))[0]
        node_lookup[basename] = f["path"]
    for f in index.files:
        if f["ext"] != ".py":
            continue
        try:
            content = read_text_smart(f["abs_path"])
        except Exception:
            continue
        for m in re.finditer(r"^(?:from|import)\s+(\S+)", content, re.MULTILINE):
            root = m.group(1).split(".")[0]
            src_basename = os.path.splitext(os.path.basename(f["path"]))[0]
            if root != src_basename and root in node_lookup:
                internal_edges.add((f["path"], node_lookup[root]))
    return internal_edges

# ──────────────────────────────────────────────
# 权重解析（方案D：运行时从skill Markdown解析）
# ──────────────────────────────────────────────

def _load_weights() -> dict:
    """从 multilang-dependency.md 中解析 6 个维度的权重并验证"""
    raw = load_weights_from_skill(SKILL_PATH)
    total = sum(raw.values())
    if abs(total - 1.0) > 0.01:
        raise ValueError(
            f"Multilang weights sum to {total*100:.0f}%, expected 100%."
        )
    return raw


class MultilangMetrics:
    """多语言混合依赖 6 维指标 + 12 MLR 规则检测"""

    def __init__(self, root: str):
        self.root = root
        self.weights = _load_weights()
        self.index = FileIndex(root)
        self.graph = DepGraph()
        self._swig_bindings = {}
        self._build_cross_lang_graph()
        self.git = GitHistory(root)

    def _build_cross_lang_graph(self):
        """构建包含语言标签的依赖图

        新增 4 层增强:
        1. C/C++ 头文件函数声明提取, 作为反向匹配目标节点
        2. Python ctypes 调用解析, 提取被调 C 符号名并关联头文件
        3. pybind11 .def() 关联到头文件声明节点
        4. ★ pybind11 跨语言边（AST + BindingMap 匹配），ctypes 兜底
        """
        self.mlr_hits = defaultdict(list)

        # ── 第 0 步: 先收集所有头文件中声明的函数名 (供后续反向匹配) ──
        header_functions = defaultdict(set)  # {basename: {func1, func2, ...}}

        for f in self.index.files:
            if f["ext"] not in (".h", ".hpp", ".c", ".cpp"):
                continue
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                content = ""
            # 匹配 C/C++ 函数声明: 返回类型 函数名(参数...)
            for m in re.finditer(
                r"(?:virtual\s+)?(?:void|int|double|float|bool|char|long|short|unsigned|signed|"
                r"size_t|std::\w+(?:<[^>]*>)?|const\s+\w+)\s+"
                r"(\w+)\s*\(",
                content
            ):
                func_name = m.group(1)
                if func_name.startswith("_") or func_name in ("if", "for", "while", "switch"):
                    continue
                header_functions[f["path"]].add(func_name)

        # ── 第 1 步: 构建依赖图节点和边 ──
        for f in self.index.files:
            node_id = f["path"]
            self.graph.add_node(node_id, f["lang"], f["path"])
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                content = ""

            # ── Python: import / from + ctypes 调用解析 ──
            if f["ext"] == ".py":
                for m in re.finditer(r"^(?:from|import)\s+(\S+)", content, re.MULTILINE):
                    self.graph.add_edge(node_id, m.group(1))

                # 增强: 解析 ctypes.CDLL("lib").funcName(...) 调用
                dll_assignments = {}
                for m in re.finditer(
                    r"(\w+)\s*=\s*ctypes\.(?:CDLL|WinDLL|cdll|windll|Library)\(",
                    content
                ):
                    dll_assignments[m.group(1)] = True
                for m in re.finditer(
                    r"ctypes\.(?:CDLL|WinDLL|cdll|windll|Library)\([^)]+\)\s*\.\s*(\w+)",
                    content
                ):
                    c_func = m.group(1)
                    for hdr_path, funcs in header_functions.items():
                        if c_func in funcs:
                            self.graph.add_edge(node_id, hdr_path)
                            break

                # 增强: 解析 dll_var.funcName(...) 调用 (前一行的 CDLL 赋值)
                for var_name, _ in dll_assignments.items():
                    for m in re.finditer(rf"{re.escape(var_name)}\.(\w+)\s*\(", content):
                        c_func = m.group(1)
                        for hdr_path, funcs in header_functions.items():
                            if c_func in funcs:
                                self.graph.add_edge(node_id, hdr_path)
                                break

                # 增强: 解析 from _lib import funcName (ctypes 风格的函数导入)
                for m in re.finditer(r"from\s+(\S+)\s+import\s+(\w+)", content):
                    imported = m.group(2)
                    for hdr_path, funcs in header_functions.items():
                        if imported in funcs:
                            self.graph.add_edge(node_id, hdr_path)
                            break

                # ctypes.CDLL / ctypes.c_void_p (原有 MLR 标记)
                if re.search(r"ctypes\.(CDLL|c_void_p|c_char_p)", content):
                    self.mlr_hits.setdefault("MLR-004", []).append(f["path"])
                    self.mlr_hits.setdefault("MLR-009", []).append(f["path"])

            # ── C++: #include + pybind11 .def ──
            elif f["ext"] in (".cpp", ".hpp"):
                for m in re.finditer(r'#include\s+[<"](.+?)[>"]', content):
                    target = os.path.basename(m.group(1))
                    if target in self.graph.nodes:
                        self.graph.add_edge(node_id, target)
                # pybind11 .def(...) 检测
                if re.search(r"\.def\s*\(", content):
                    for m in re.finditer(r'\.def\s*\(\s*["\x27](.+?)["\x27]', content):
                        bound_func = m.group(1)
                        # 增强: 将 .def("name") 关联到头文件中同名函数声明
                        matched = False
                        for hdr_path, funcs in header_functions.items():
                            if bound_func in funcs:
                                self.graph.add_edge(node_id, hdr_path)
                                matched = True
                                break
                        if not matched:
                            self.graph.add_edge(node_id, f"pybind:{bound_func}")

            # ── C: #include ──
            elif f["ext"] in (".c", ".h"):
                for m in re.finditer(r'#include\s+[<"](.+?)[>"]', content):
                    target = os.path.basename(m.group(1))
                    if target in self.graph.nodes:
                        self.graph.add_edge(node_id, target)

            # ── Fortran: use module ──
            elif f["ext"] in (".f90", ".f95", ".f03", ".f08"):
                for m in re.finditer(r'^\s*use\s+(?:,\s*intrinsic\s*::\s*)?(\w+)', content, re.MULTILINE):
                    mod_name = m.group(1).lower()
                    for other in self.index.by_lang("fortran"):
                        other_base = os.path.splitext(os.path.basename(other["path"]))[0].lower()
                        if other_base == mod_name:
                            self.graph.add_edge(node_id, other["path"])
                            break
            elif f["ext"] == ".f":
                # F77 has no module system; track via common blocks and subprogram calls
                for m in re.finditer(r'^\s*call\s+(\w+)', content, re.MULTILINE):
                    called_name = m.group(1).lower()
                    for other in self.index.by_lang("fortran"):
                        other_base = os.path.splitext(os.path.basename(other["path"]))[0].lower()
                        if other_base == called_name:
                            self.graph.add_edge(node_id, other["path"])
                            break

            # ── SWIG: %include → C++ 头文件 ──
            elif f["lang"] == "swig":
                for m in re.finditer(r'%include\s+[<"](.+?)[>"]', content):
                    target = os.path.basename(m.group(1))
                    if target in self.graph.nodes:
                        self.graph.add_edge(node_id, target)

        # ── 第 4 步: ★ pybind11 跨语言边（AST + BindingMap + ctypes 兜底）──
        try:
            from arch_quality.arch_bindings_parser import BindingMap
            from arch_quality.arch_python_ast import extract_pybind11_calls
            from arch_quality.arch_multilang_matcher import build_cross_lang_edges

            bmap = BindingMap(self.index)
            bmap.parse()

            py_calls = []
            for pf in self.index.by_lang("python"):
                try:
                    py_calls.extend(extract_pybind11_calls(pf["abs_path"]))
                except Exception:
                    pass

            cross_edges = build_cross_lang_edges(self.index, bmap, py_calls)
            for py_path, cpp_path in cross_edges:
                if py_path in self.graph.nodes and cpp_path in self.graph.nodes:
                    self.graph.add_edge(py_path, cpp_path)
        except Exception as e:
            # pybind11 检测失败时不影响主流程
            pass

        # ── 第 5 步: ★ SWIG 绑定跨语言边 ──
        try:
            from arch_quality.arch_python_ast import extract_swig_bindings
            swig_files = self.index.by_lang("swig")
            for sf in swig_files:
                try:
                    sb = extract_swig_bindings(sf["abs_path"])
                except Exception:
                    continue

                # SWIG %module → Python 模块名（跨语言边: .i → Python）
                for mod_name in sb.get("modules", []):
                    for pf in self.index.by_lang("python"):
                        if mod_name in pf["path"] or mod_name in read_text_smart(pf["abs_path"]):
                            self.graph.add_edge(pf["path"], sf["path"])

                # SWIG %include "header.h" → C++ 头文件（跨语言边: .i → .h）
                for inc_path in sb.get("includes", []):
                    inc_basename = os.path.basename(inc_path)
                    if inc_basename in self.graph.nodes:
                        self.graph.add_edge(sf["path"], inc_basename)
                    else:
                        for hf in self.index.files:
                            if hf["ext"] in (".h", ".hpp") and hf["path"].endswith(inc_basename):
                                self.graph.add_edge(sf["path"], hf["path"])
                                break

                # SWIG %extend 函数名 → 头文件同名声明（跨语言边: .i → .h）
                for func_name in sb.get("extended_funcs", []):
                    for hdr_path, funcs in header_functions.items():
                        if func_name in funcs:
                            self.graph.add_edge(sf["path"], hdr_path)
                            break

                # 保存 SWIG 绑定信息供 MLR-003 使用
                self._swig_bindings[sf["path"]] = sb

        except Exception:
            pass

    # ── 6 个评估维度 ──

    def calc_coupling_intensity(self) -> tuple:
        """维度1: 跨语言调用强度

        算法见 skill: multilang-dependency.md → 跨语言调用强度

        纯语言项目回退: 当项目仅包含单一语言时，无真正的跨语言调用，
        使用项目内模块依赖数替代跨语言边数来评估耦合度。
        """
        if not self.graph.nodes:
            return 100.0, {}

        # 纯语言项目回退: 用项目内依赖数替代跨语言边数
        if self.graph.is_single_language:
            internal_edges = _collect_std_imports(self.index)
            node_targets = set(self.graph.nodes.keys())
            scores = {}
            for node_id in self.graph.nodes:
                internal_deps = 0
                for s, d in internal_edges:
                    if s == node_id or d == node_id:
                        internal_deps += 1
                L = internal_deps
                if L == 0:
                    s = 100
                elif L <= 2:
                    s = 80
                elif L <= 5:
                    s = 60 - (L - 3) * 5
                elif L <= 10:
                    s = 40 - (L - 6) * 4
                else:
                    s = max(0, 20 - (L - 11) * 2)
                scores[node_id] = s
            avg_score = sum(scores.values()) / len(scores) if scores else 100
            return round(avg_score, 2), scores

        scores = {}
        for node_id in self.graph.nodes:
            cross_edges = (
                len(self.graph.cross_predecessors(node_id)) +
                len(self.graph.cross_successors(node_id))
            )
            L = cross_edges
            if L == 0:
                s = 100
            elif L <= 2:
                s = 80
            elif L <= 5:
                s = 60 - (L - 3) * 5
            elif L <= 10:
                s = 40 - (L - 6) * 4
            else:
                s = max(0, 20 - (L - 11) * 2)
            scores[node_id] = s

        avg_score = sum(scores.values()) / len(scores) if scores else 100
        return round(avg_score, 2), scores

    def calc_impact_radius(self) -> tuple:
        """维度2: 跨语言影响半径

        算法见 skill: multilang-dependency.md → 跨语言影响半径

        纯语言项目回退: 使用项目内依赖图（全部边）计算影响半径。
        """
        if not self.graph.nodes:
            return 100.0, {}

        if self.graph.is_single_language:
            internal_edges = _collect_std_imports(self.index)
            adj = defaultdict(set)
            for s, d in internal_edges:
                adj[s].add(d)
                adj[d].add(s)
            radii = {}
            for node_id in self.graph.nodes:
                visited = {node_id}
                queue = [(node_id, 0)]
                while queue:
                    node, depth = queue.pop(0)
                    if depth >= 5:
                        continue
                    for neighbor in adj.get(node, set()):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append((neighbor, depth + 1))
                R = len(visited) - 1
                # Relaxed scoring for single-language projects:
                # internal module dependencies are denser than cross-language calls
                if R == 0:
                    s = 100
                elif R <= 5:
                    s = 90
                elif R <= 15:
                    s = 70
                elif R <= 30:
                    s = 55
                elif R <= 60:
                    s = 40
                else:
                    s = max(0, 30 - (R - 60) * 1)
                radii[node_id] = {"radius": R, "score": s}
                radii[node_id] = {"radius": R, "score": s}
            avg_score = sum(v["score"] for v in radii.values()) / len(radii) if radii else 100
            return round(avg_score, 2), radii

        radii = {}
        for node_id in self.graph.nodes:
            reachable = self.graph.bfs_reachable(node_id, max_depth=5, cross_only=True)
            R = len(reachable) - 1  # 排除自身
            if R == 0:
                s = 100
            elif R <= 3:
                s = 90
            elif R <= 7:
                s = 70
            elif R <= 15:
                s = 40
            else:
                s = max(0, 30 - (R - 15) * 2)
            radii[node_id] = {"radius": R, "score": s}

        avg_score = sum(v["score"] for v in radii.values()) / len(radii) if radii else 100
        return round(avg_score, 2), radii

    def calc_call_depth(self) -> tuple:
        """维度3: 跨语言回调深度

        通过三条路径检测回调深度:
        1. 跨语言边BFS最大深度（原有逻辑）
        2. 静态回调链检测: Py→C++→Py→C++ 模式
        3. pybind11回调注册检测: .def(py::init, py::callback) 模式

        返回 (score, {"max_depth": D, "callback_chains": [...], "max_depth_path": [...]})
        """
        if not self.graph.cross_edges:
            return 100.0, {"max_depth": 0, "callback_chains": [], "max_depth_path": []}

        # ── 路径 1: BFS 跨语言最大深度 ──
        max_depth = 0
        max_depth_path = []
        for node_id in self.graph.nodes:
            visited = {node_id}
            queue = [(node_id, 0, [node_id])]
            while queue:
                node, depth, path = queue.pop(0)
                if depth > max_depth:
                    max_depth = depth
                    max_depth_path = path[:]
                for neighbor in self.graph.cross_successors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1, path + [neighbor]))

        # ── 路径 2: 静态回调链检测 (Py→C++→Py→C++) ──
        callback_chains = []
        py_files = {f["path"]: f for f in self.index.by_lang("python")}
        cpp_files = {f["path"]: f for f in self.index.files if f["ext"] in (".cpp", ".cxx", ".cc")}

        for py_path, py_info in py_files.items():
            try:
                py_content = read_text_smart(py_info["abs_path"])
            except Exception:
                continue

            # 检测回调注册模式: set_callback, register_callback, etc.
            callback_reg_patterns = [
                r'set(?:_?)(?:callback|handler|listener|delegate|slot|notify)',
                r'register(?:_?)(?:callback|handler|listener)',
                r'\.connect\s*\(',
                r'signal\s*\.\s*connect\s*\(',
                r'py::init\s*<',
                r'subprocess\.(?:run|call|Popen|check_output)',
            ]
            has_callback_reg = any(re.search(p, py_content) for p in callback_reg_patterns)
            if not has_callback_reg:
                continue

            # 找到此 Python 文件的跨语言后继（C++ 文件）
            cpp_targets = self.graph.cross_successors(py_path)
            for cpp_path in cpp_targets:
                if cpp_path not in cpp_files:
                    continue
                # 检查 C++ 文件是否回调 Python
                try:
                    cpp_content = read_text_smart(cpp_files[cpp_path]["abs_path"])
                except Exception:
                    continue

                cpp_cbs_python = bool(re.search(
                    r'Py(?:thon)?_(?:Run|Call|Eval|Eval_Call|Object)|'
                    r'py::(?:call|cast|function)|'
                    r'PyErr_|PyImport_|PyObject_Call|'
                    r'PyGILState_|Py_BEGIN_ALLOW_THREADS',
                    cpp_content
                ))
                if not cpp_cbs_python:
                    continue

                # 找到 C++ 文件回调的 Python 文件
                py_targets = self.graph.cross_successors(cpp_path)
                chain_depth_3_paths = []
                for py2_path in py_targets:
                    if py2_path in py_files and py2_path != py_path:
                        chain_depth_3_paths.append(py2_path)

                if cpp_cbs_python:
                    chain = f"{py_path} [Py] → {cpp_path} [C++]"
                    if chain_depth_3_paths:
                        for py2 in chain_depth_3_paths[:3]:
                            full_chain = chain + f" → {py2} [Py]"
                            callback_chains.append(full_chain)
                            max_depth = max(max_depth, 3)
                    else:
                        callback_chains.append(chain + " → [callback to Py]")
                        max_depth = max(max_depth, 2)

        # ── 路径 3: pybind11 回调检测 ──
        for f in self.index.files:
            if f["ext"] not in (".cpp", ".cxx", ".cc"):
                continue
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            has_pybind_callback = bool(re.search(
                r'py::(?:function|override|cast)|'
                r'PyEval_CallObject|PyObject_CallObject|'
                r'PyRun_SimpleString|PyRun_String|'
                r'PyGILState_Ensure|Py_BEGIN_ALLOW_THREADS',
                content
            ))
            if has_pybind_callback:
                has_gil_release = bool(re.search(
                    r'py::gil_scoped_release|gil_scoped_release|Py_BEGIN_ALLOW_THREADS',
                    content
                ))
                if not has_gil_release:
                    py_succs = self.graph.cross_predecessors(f["path"])
                    py_succs = [p for p in py_succs if p in py_files]
                    if py_succs:
                        chain = f"{py_succs[0]} [Py] → {f['path']} [C++] → [callback to Py]"
                        if chain not in callback_chains:
                            callback_chains.append(chain)
                            max_depth = max(max_depth, 2)

        D = max_depth
        if D <= 1:
            score = 100
        elif D == 2:
            score = 80
        elif D == 3:
            score = 50
        else:
            score = 20
        return round(score, 2), {
            "max_depth": D,
            "callback_chains": callback_chains[:10],
            "max_depth_path": max_depth_path[:10] if max_depth_path else [],
        }

    def _build_header_functions(self):
        """构建头文件函数声明索引，供绑定一致性和MLR-003共用。"""
        if hasattr(self, '_header_functions') and self._header_functions:
            return self._header_functions
        header_functions = {}
        for f in self.index.files:
            if f["ext"] in (".h", ".hpp"):
                try:
                    content = read_text_smart(f["abs_path"])
                except Exception:
                    continue
                funcs = set()
                for m in re.finditer(
                    r"(?:virtual\s+)?(?:void|int|double|float|bool|std::\w+)\s+(\w+)\s*\(",
                    content
                ):
                    funcs.add(m.group(1))
                if funcs:
                    header_functions[f["path"]] = funcs
        self._header_functions = header_functions
        return header_functions

    def calc_binding_consistency(self) -> tuple:
        """维度4: 绑定层接口一致性

        算法见 skill: multilang-dependency.md → 绑定层接口一致性
        
        增强支持: pybind11 .def() 和 SWIG %extend/%inline 绑定均纳入统计。
        """
        cpp_exports = 0
        bound_exports = 0
        matched = 0
        swig_bound = 0
        swig_matched = 0

        for f in self.index.files:
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                content = ""

            if f["ext"] in (".hpp", ".h"):
                cpp_exports += len(re.findall(
                    r"(?:virtual\s+)?(?:void|int|double|float|bool|std::\w+)\s+\w+\s*\(",
                    content
                ))
            if f["ext"] == ".cpp":
                bound_exports += len(re.findall(r'\.def\s*\(', content))
                matched += len(re.findall(r'\.def\s*\(\s*["\x27](\w+)["\x27]', content))

        # SWIG 绑定统计
        from arch_quality.arch_python_ast import extract_swig_bindings
        header_functions = self._build_header_functions()
        for sf in self.index.by_lang("swig"):
            try:
                sb = extract_swig_bindings(sf["abs_path"])
            except Exception:
                continue
            swig_ext_funcs = sb.get("extended_funcs", [])
            swig_inline_funcs = sb.get("inline_funcs", [])
            swig_includes = sb.get("includes", [])
            swig_renames = sb.get("renames", [])
            swig_bound += len(swig_ext_funcs) + len(swig_inline_funcs)
            for func_name in swig_ext_funcs + swig_inline_funcs:
                for hdr_path, funcs in header_functions.items():
                    if func_name in funcs:
                        swig_matched += 1
                        break
            for inc_path in swig_includes:
                inc_base = os.path.basename(inc_path)
                for hdr_path in header_functions:
                    if hdr_path.replace("\\", "/").endswith(inc_base):
                        swig_matched += 1
                        break
            self._swig_bindings[sf["path"]] = sb

        total_bound = bound_exports + swig_bound
        total_matched = matched + swig_matched

        if cpp_exports == 0:
            ratio_bound = 1.0
        else:
            ratio_bound = total_bound / cpp_exports if cpp_exports > 0 else 0

        if total_bound == 0:
            ratio_match = 1.0
        else:
            ratio_match = total_matched / total_bound if total_bound > 0 else 0

        score = (ratio_bound * 100 + ratio_match * 100) / 2
        deductions = 0
        for f in self.index.files:
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            if "void*" in content or "c_void_p" in content:
                deductions += 5
        deductions = min(deductions, 20)
        score -= deductions

        return max(0, round(score, 2)), {
            "cpp_exports": cpp_exports,
            "bound_exports": bound_exports,
            "matched": matched,
            "swig_bound": swig_bound,
            "swig_matched": swig_matched,
            "deductions": deductions,
        }

    def calc_script_boundary(self) -> tuple:
        """维度5: 脚本越界访问

        算法见 skill: multilang-dependency.md → 脚本越界访问

        纯语言项目回退: 仅统计跨模块直接访问内部符号（以 _ 开头）的次数，
        不将标准库和第三方库导入计入越界。
        """
        total_calls = 0
        direct_access = 0

        project_modules = set()
        for f in self.index.files:
            if f["ext"] == ".py":
                parts = f["path"].replace("\\", "/").replace("/", ".").split(".")
                if parts and parts[-1] == "py":
                    parts = parts[:-1]
                project_modules.add(".".join(parts))

        for f in self.index.files:
            if f["lang"] not in ("python", "tcl", "lua", "javascript"):
                continue
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue

            if f["ext"] == ".py":
                if self.graph.is_single_language:
                    for m in re.finditer(r"^(?:from|import)\s+(\S+)", content, re.MULTILINE):
                        mod_name = m.group(1).split(".")[0]
                        total_calls += 1
                        from_private = re.match(r"from\s+(_\S+)\s+import", m.group(0))
                        import_private = mod_name.startswith("_") and not mod_name.startswith("__")
                        if from_private or import_private:
                            direct_access += 1
                else:
                    total_calls += len(re.findall(r"(?:CDLL|Library|import|from)\s", content))
                    direct_access += len(re.findall(r"_[_a-z]+|ctypes\.c_void_p", content))
            elif f["ext"] == ".tcl":
                total_calls += len(re.findall(r"::\w+", content))
                direct_access += len(re.findall(r"::engine::|::internal::", content))

        if total_calls == 0:
            return 100.0, {"total_calls": 0, "direct_access": 0, "violation_ratio": 0}

        violation_ratio = direct_access / total_calls
        score = max(0, 100 - violation_ratio * 200)
        return round(score, 2), {
            "total_calls": total_calls,
            "direct_access": direct_access,
            "violation_ratio": round(violation_ratio, 4),
        }

    def calc_cross_lang_cycles(self) -> tuple:
        """维度6: 跨语言循环依赖

        算法见 skill: multilang-dependency.md → 跨语言循环依赖
        """
        cycles = self.graph.detect_cross_lang_cycles()
        unique_cycles = []
        seen = set()
        for c in cycles:
            key = "->".join(c)
            if key not in seen:
                seen.add(key)
                unique_cycles.append(c)

        num_cycles = len(unique_cycles)
        cycle_length = sum(len(c) for c in unique_cycles)
        severity = min(100, num_cycles * 10 + cycle_length * 2)
        score = max(0, 100 - severity)

        return round(score, 2), {
            "cycles_count": num_cycles,
            "total_length": cycle_length,
            "severity": severity,
            "cycles": [{"path": " -> ".join(c), "languages": list(set(
                self.graph.nodes.get(n, {}).get("lang", "?") for n in c
            ))} for c in unique_cycles],
        }

    def check_mlr_rules(self) -> list:
        """检测 12 条 MLR 规则，返回违反列表"""

        mlr_results = []
        self.mlr_hits = defaultdict(list)

        # MLR-001: 跨语言循环依赖检测
        cycles = self.graph.detect_cross_lang_cycles()
        if cycles:
            mlr_results.append({
                "rule": "MLR-001", "name": "跨语言循环依赖检测",
                "severity": "HIGH",
                "count": len(cycles),
                "detail": f"发现 {len(cycles)} 个跨语言循环依赖",
            })

        # MLR-001b: 同语言模块级循环依赖检测
        from arch_quality.arch_python_ast import is_third_party_path
        for lang in self.graph.languages:
            same_lang_cycles = self.graph.detect_same_lang_cycles(lang=lang)
            if not same_lang_cycles:
                continue
            non_tp_cycles = []
            tp_cycles = 0
            for cycle in same_lang_cycles:
                if any(is_third_party_path(n) for n in cycle):
                    tp_cycles += 1
                else:
                    non_tp_cycles.append(cycle)
            if tp_cycles:
                mlr_results.append({
                    "rule": "MLR-001", "name": f"{lang}模块级循环依赖（第三方，已豁免）",
                    "severity": "INFO",
                    "count": tp_cycles,
                    "detail": f"发现 {tp_cycles} 个 {lang} 模块级循环依赖（第三方代码，已豁免）",
                })
            if non_tp_cycles:
                cycle_samples = [" → ".join(c[:5]) for c in non_tp_cycles[:3]]
                mlr_results.append({
                    "rule": "MLR-001", "name": f"{lang}模块级循环依赖",
                    "severity": "MEDIUM",
                    "count": len(non_tp_cycles),
                    "detail": f"发现 {len(non_tp_cycles)} 个 {lang} 模块级循环依赖: {cycle_samples}",
                })

        # MLR-002: 绑定层接口缺失
        if self.index.by_lang("cpp"):
            cpp_files = self.index.by_lang("cpp")
            total_h = sum(1 for f in cpp_files if f["ext"] in (".hpp", ".h"))
            bound = sum(1 for f in cpp_files if f["ext"] == ".cpp")
            swig_count = len(self.index.by_lang("swig"))
            has_binding = bound > 0 or swig_count > 0
            if total_h > bound + 2 and not has_binding:
                mlr_results.append({
                    "rule": "MLR-002", "name": "绑定层接口缺失",
                    "severity": "HIGH",
                    "count": total_h - bound,
                    "detail": f"头文件数 ({total_h}) >> 绑定cpp数 ({bound})，可能存在未注册接口",
                })
            elif total_h > bound + 2 and swig_count > 0 and bound == 0:
                mlr_results.append({
                    "rule": "MLR-002", "name": "绑定层接口缺失（SWIG项目）",
                    "severity": "MEDIUM",
                    "count": total_h - bound,
                    "detail": f"头文件数 ({total_h}) >> 绑定cpp数 ({bound})，但有 {swig_count} 个 SWIG 绑定文件",
                })

        # MLR-003: 绑定层签名不匹配（pybind11 + SWIG）
        # pybind11 .def() 签名检测
        for f in self.index.files:
            if f["ext"] != ".cpp":
                continue
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            missing_defaults = re.findall(r"\.def\s*\(\s*[\"'\x60](\w+)[\"'\x60]\s*,\s*&\w+\s*\)", content)
            if missing_defaults:
                mlr_results.append({
                    "rule": "MLR-003", "name": "绑定层签名不匹配",
                    "severity": "HIGH",
                    "count": len(missing_defaults),
                    "detail": f"{f['path']}: {len(missing_defaults)} 处 .def() 可能缺少默认参数定义: {missing_defaults[:5]}",
                })

        # SWIG 绑定签名检测
        from arch_quality.arch_python_ast import extract_swig_bindings, match_swig_to_headers
        header_functions_cache = self._build_header_functions()

        for sf in self.index.by_lang("swig"):
            try:
                sb = extract_swig_bindings(sf["abs_path"])
            except Exception:
                continue
            unmatched = []
            for func_name in sb.get("extended_funcs", []):
                found = False
                for hdr_path, funcs in header_functions_cache.items():
                    if func_name in funcs:
                        found = True
                        break
                if not found:
                    unmatched.append(func_name)
            if unmatched:
                from arch_quality.arch_python_ast import is_third_party_path
                is_tp = is_third_party_path(sf["path"])
                mlr_results.append({
                    "rule": "MLR-003", "name": "SWIG绑定签名不匹配",
                    "severity": "INFO" if is_tp else "MEDIUM",
                    "count": len(unmatched),
                    "detail": f"{sf['path']}: {len(unmatched)} 处 %extend 函数未在头文件中找到声明: {unmatched[:5]}" + ("（第三方代码，建议豁免）" if is_tp else ""),
                })

        # MLR-004: 脚本直接访问内部（在 _build_cross_lang_graph 中收集）
        for fpath in self.mlr_hits.get("MLR-004", []):
            mlr_results.append({
                "rule": "MLR-004", "name": "脚本直接访问内部",
                "severity": "HIGH",
                "count": 1,
                "detail": f"{fpath}: 使用了 ctypes.CDLL 直接访问内部符号",
            })

        # MLR-004b: Tcl 命名空间直接访问内部变量
        _TCL_ALLOWED_NS = frozenset([
            "tcl", "tk", "msgcat", "http", "cookie", "ftp", "smtp",
            "string", "list", "array", "dict", "file", "chan", "clock",
            "info", "interp", "namespace", "package", "platform", "registry",
            "socket", "console", "dde", "regexp", "pid",
        ])
        _TCL_INTERNAL_RE = re.compile(r'(::[a-z_]\w*)::([$\w]+)', re.MULTILINE)
        for f in self.index.files:
            if f["lang"] != "tcl":
                continue
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            violations = []
            for m in _TCL_INTERNAL_RE.finditer(content):
                ns = m.group(1).lstrip(":")
                if ns not in _TCL_ALLOWED_NS and not ns.startswith("tk"):
                    var = m.group(2)
                    if not var.startswith("__") and var not in ("create", "delete", "eval", "origin", "parent", "qualifiers", "tail", "which", "current", "ensemble", "export", "forget", "import", "inscope", "unknown"):
                        line_num = content[:m.start()].count('\n') + 1
                        violations.append((ns, var, line_num))
            if violations:
                from arch_quality.arch_python_ast import is_third_party_path
                is_tp = is_third_party_path(f["path"])
                unique_ns = list(dict.fromkeys(ns for ns, _, _ in violations))[:5]
                mlr_results.append({
                    "rule": "MLR-004", "name": "Tcl脚本直接访问内部",
                    "severity": "INFO" if is_tp else "MEDIUM",
                    "count": len(violations),
                    "detail": f"{f['path']}: {len(violations)} 处直接访问 Tcl 命名空间内部变量: {unique_ns}",
                })

        # MLR-005: 跨语言回调深度超标
        depth_score, depth_info = self.calc_call_depth()
        if depth_info.get("max_depth", 0) >= 3:
            chains = depth_info.get("callback_chains", [])
            detail = f"最大跨语言回调深度 = {depth_info['max_depth']}，建议 ≤ 2"
            if chains:
                detail += "；回调链: " + "; ".join(chains[:5])
            mlr_results.append({
                "rule": "MLR-005", "name": "跨语言回调深度超标",
                "severity": "MEDIUM",
                "count": len(chains) if chains else 1,
                "detail": detail,
            })
        elif depth_info.get("max_depth", 0) == 2 and depth_info.get("callback_chains"):
            chains = depth_info.get("callback_chains", [])
            mlr_results.append({
                "rule": "MLR-005", "name": "跨语言回调深度警告",
                "severity": "LOW",
                "count": len(chains),
                "detail": f"存在 {len(chains)} 条深度 2 回调链: " + "; ".join(chains[:5]),
            })

        # MLR-006: 热点模块
        from arch_quality.arch_python_ast import is_third_party_path
        intensity_score, intensity_scores = self.calc_coupling_intensity()
        hotspots_all = [n for n, s in intensity_scores.items() if s < 60]
        hotspots_tp = [n for n in hotspots_all if is_third_party_path(n)]
        hotspots = [n for n in hotspots_all if not is_third_party_path(n)]
        if hotspots_tp:
            mlr_results.append({
                "rule": "MLR-006", "name": "热点模块（第三方，已豁免）",
                "severity": "INFO",
                "count": len(hotspots_tp),
                "detail": f"{len(hotspots_tp)} 个第三方模块跨语言调用强度得分 < 60（已豁免）",
            })
        if hotspots:
            is_single = self.graph.is_single_language
            rule_name = "高耦合模块（模块依赖过多）" if is_single else "热点模块（高频跨语言调用）"
            mlr_results.append({
                "rule": "MLR-006", "name": rule_name,
                "severity": "MEDIUM",
                "count": len(hotspots),
                "detail": f"{len(hotspots)} 个模块{'耦合强度' if is_single else '跨语言调用强度'}得分 < 60: {hotspots[:10]}",
            })

        # MLR-007: TNT模块
        radius_score, radii = self.calc_impact_radius()
        is_single = self.graph.is_single_language
        radius_threshold = 30 if is_single else 10
        tnt_modules = [n for n, v in radii.items() if isinstance(v, dict) and v.get("radius", 0) > radius_threshold]
        if tnt_modules:
            rule_name = "广影响模块（影响半径超标）" if is_single else "TNT模块（影响半径超标）"
            mlr_results.append({
                "rule": "MLR-007", "name": rule_name,
                "severity": "MEDIUM",
                "count": len(tnt_modules),
                "detail": f"{len(tnt_modules)} 个模块影响半径 > {radius_threshold}: {tnt_modules[:10]}",
            })

        # MLR-008: GIL死锁风险 (v2 — 增加 pybind11/CPython 上下文前置条件)
        from arch_quality.arch_python_ast import has_pybind11_context
        for f in self.index.files:
            if f["ext"] not in (".cpp", ".cxx", ".cc", ".h", ".hpp"):
                continue
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            if not has_pybind11_context(content):
                continue
            if "py::gil_scoped_release" in content or "gil_scoped_release" in content:
                continue
            if re.search(r"py::object|\.attr\(|\.call\(", content):
                mlr_results.append({
                    "rule": "MLR-008", "name": "GIL死锁风险",
                    "severity": "HIGH",
                    "count": 1,
                    "detail": f"{f['path']}: C++ 代码调用 Python 回调但未显式释放 GIL",
                })
                break

        # MLR-009: 绑定层使用通用类型（在 _build_cross_lang_graph 中收集）
        for fpath in self.mlr_hits.get("MLR-009", []):
            mlr_results.append({
                "rule": "MLR-009", "name": "绑定层使用通用类型",
                "severity": "MEDIUM",
                "count": 1,
                "detail": f"{fpath}: 使用了 ctypes.c_void_p 等通用类型",
            })

        # MLR-010: FFI内存所有权混乱 (v2 — 5层过滤 + 3级严重度)
        from arch_quality.arch_python_ast import (
            find_malloc_tokens_in_py, is_codegen_template,
            has_ffi_context, check_paired_free, _MALLOC_CALL_RE,
        )
        for f in self.index.files:
            if f["ext"] not in (".c", ".cpp", ".py"):
                continue
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue

            if f["ext"] == ".py":
                # L5: 代码生成模板 → 跳过（如 gmsh/api/GenApi.py）
                if is_codegen_template(content):
                    continue

                # L1: tokenize 精确提取（排除字符串/注释中的匹配）
                hits = find_malloc_tokens_in_py(content)

                if not hits:
                    continue

                # L2: FFI 上下文检测
                has_ffi = has_ffi_context(content)

                # L3+L4: 确认是函数调用形式 + 收集命中
                real_hits = []
                lines = content.splitlines()
                for line_no, tok in hits:
                    if line_no <= len(lines):
                        line = lines[line_no - 1]
                        if _MALLOC_CALL_RE.search(line) or has_ffi:
                            real_hits.append((line_no, tok))

                if not real_hits:
                    continue

                # L4: 配对释放检测
                paired_free = check_paired_free(content)

                if has_ffi and not paired_free:
                    severity = "HIGH"
                    detail_suffix = "且无配对 free，内存所有权不清晰"
                elif has_ffi and paired_free:
                    severity = "MEDIUM"
                    detail_suffix = "有配对 free，但建议使用封装 API"
                else:
                    severity = "LOW"
                    detail_suffix = "非 FFI 上下文中的 malloc/calloc/realloc 引用"

                mlr_results.append({
                    "rule": "MLR-010", "name": "FFI内存所有权混乱",
                    "severity": severity,
                    "count": len(real_hits),
                    "detail": (f"{f['path']}: {len(real_hits)} 处 "
                               f"malloc/calloc/realloc，{detail_suffix}"),
                })

        # MLR-011: 小数据频繁跨语言传输
        for f in self.index.files:
            if f["ext"] != ".py":
                continue
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            loop_calls = len(re.findall(r"for.*\n.*(?:CDLL|ctypes|c_void_p)", content))
            if loop_calls > 0:
                mlr_results.append({
                    "rule": "MLR-011", "name": "小数据频繁跨语言传输",
                    "severity": "LOW",
                    "count": loop_calls,
                    "detail": f"{f['path']}: 循环内存在约 {loop_calls} 处跨语言调用，建议批量化",
                })

        # MLR-012: Fortran缺少ISO_C_BINDING (v3 — 第三方/固定格式/同语言降级)
        from arch_quality.arch_python_ast import is_third_party_path
        fortran_files = self.index.by_lang("fortran")
        for f in fortran_files:
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            if "iso_c_binding" not in content.lower() and re.search(r"subroutine|function", content):
                is_tp = is_third_party_path(f["path"])
                is_f77 = f["ext"] == ".f"
                has_cross_lang_edge = (
                    any(f["path"] == s for s, d in self.graph.cross_edges) or
                    any(f["path"] == d for s, d in self.graph.cross_edges)
                )
                if is_tp:
                    severity = "INFO"
                    detail_suffix = "第三方代码，建议标注 @third_party 豁免"
                elif is_f77:
                    severity = "INFO"
                    detail_suffix = "Fortran 77 固定格式不支持 iso_c_binding，确认未被 C 直接调用后可豁免"
                elif not has_cross_lang_edge:
                    severity = "INFO"
                    detail_suffix = "同语言内部调用，不需要 iso_c_binding"
                else:
                    severity = "MEDIUM"
                    detail_suffix = "被 C/C++ 直接调用，跨语言接口可能不稳定"
                mlr_results.append({
                    "rule": "MLR-012", "name": "Fortran缺少ISO_C_BINDING",
                    "severity": severity,
                    "count": 1,
                    "detail": f"{f['path']}: Fortran 代码未使用 ISO_C_BINDING，{detail_suffix}",
                })

        return mlr_results

    def all_metrics(self) -> dict:
        """计算所有 6 维指标 + MLR 规则，返回结构化结果

        纯语言项目回退: 调整维度名称和描述，使其语义准确。
        """
        weights = self.weights
        is_single = self.graph.is_single_language

        dim1, dim1_detail = self.calc_coupling_intensity()
        dim2, dim2_detail = self.calc_impact_radius()
        dim3, dim3_detail = self.calc_call_depth()
        dim4, dim4_detail = self.calc_binding_consistency()
        dim5, dim5_detail = self.calc_script_boundary()
        dim6, dim6_detail = self.calc_cross_lang_cycles()

        mlr_violations = self.check_mlr_rules()

        if is_single:
            dim_names = {
                "coupling_intensity": "模块耦合强度",
                "impact_radius": "模块影响半径",
                "call_depth": "依赖深度",
                "binding_consistency": "绑定层接口一致性",
                "script_boundary": "内部封装越界",
                "cross_lang_cycles": "跨模块循环依赖",
            }
        else:
            dim_names = {
                "coupling_intensity": "跨语言调用强度",
                "impact_radius": "跨语言影响半径",
                "call_depth": "跨语言回调深度",
                "binding_consistency": "绑定层接口一致性",
                "script_boundary": "脚本越界访问",
                "cross_lang_cycles": "跨语言循环依赖",
            }

        dim_scores = {}
        dim_values = {
            "coupling_intensity": dim1,
            "impact_radius": dim2,
            "call_depth": dim3,
            "binding_consistency": dim4,
            "script_boundary": dim5,
            "cross_lang_cycles": dim6,
        }
        for k in dim_values:
            dim_scores[dim_names[k]] = dim_values[k]

        dim_weights = [
            (dim_names["coupling_intensity"], 0.15),
            (dim_names["impact_radius"], 0.20),
            (dim_names["call_depth"], 0.10),
            (dim_names["binding_consistency"], 0.25),
            (dim_names["script_boundary"], 0.15),
            (dim_names["cross_lang_cycles"], 0.15),
        ]
        overall = sum(
            dim_scores.get(k, 0) * w
            for k, w in dim_weights
        )

        return {
            "overall": round(overall, 2),
            "weights_source": SKILL_PATH,
            "weights_applied": weights,
            "is_single_language": is_single,
            "languages": list(self.graph.languages) if self.graph.languages else ["unknown"],
            "dimensions": {
                "coupling_intensity":      {"score": dim1, "detail": dim1_detail},
                "impact_radius":           {"score": dim2, "detail": dim2_detail},
                "call_depth":              {"score": dim3, "detail": dim3_detail},
                "binding_consistency":     {"score": dim4, "detail": dim4_detail},
                "script_boundary":         {"score": dim5, "detail": dim5_detail},
                "cross_lang_cycles":       {"score": dim6, "detail": dim6_detail},
            },
            "dim_names": dim_names,
            "mlr_violations": mlr_violations,
            "files": {
                "total": self.index.total_files(),
                "by_lang": dict(sorted(
                    ((lang, len(self.index.by_lang(lang)))
                     for lang in set(f["lang"] for f in self.index.files)),
                    key=lambda x: -x[1]
                )),
            },
        }


def main():
    parser = argparse.ArgumentParser(description="多语言混合依赖评估")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--full", action="store_true", help="完整评估（6维 + MLR）")
    parser.add_argument("--scan", action="store_true", help="扫描并输出结果")
    parser.add_argument("--mlr-only", action="store_true", help="仅检测 MLR 规则")

    args = parser.parse_args()

    metrics = MultilangMetrics(args.root)

    if args.mlr_only:
        result = {"mlr_violations": metrics.check_mlr_rules()}
    else:
        result = metrics.all_metrics()

    out_dir = ensure_output_dir(args.root)
    report_path = write_report(out_dir, "multilang-metrics.json", result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
