"""
arch_metrics_template.py — 模板元编程与编译时依赖膨胀评估指标

实现 模板元编程与编译时依赖膨胀评估指南.md 中的 6 个评估维度和 12 条 MLR 规则。
权重从 skills/template-metaprogramming.md 动态解析。
非 C++ 项目直接跳过，不参与评分。
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
    write_report, read_text_smart
)

SKILL_PATH = str(Path(__file__).parent / "skills" / "template-metaprogramming.md")

CPP_EXTS = {".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".txx"}
CPP_HEADER_EXTS = {".hpp", ".h", ".hxx", ".txx"}
CPP_SOURCE_EXTS = {".cpp", ".cxx", ".cc"}
TEMPLATE_PATTERN = re.compile(r'template\s*<', re.MULTILINE)
EXTERN_TEMPLATE_PATTERN = re.compile(r'extern\s+template\s+class\s+', re.MULTILINE)
EXTERN_TEMPLATE_FUNC_PATTERN = re.compile(r'extern\s+template\s+\w+\s+\w+\s*\(', re.MULTILINE)
NESTED_ANGLE_PATTERN = re.compile(r'<(?:[^<>]|<(?:[^<>]|<[^<>]*>)*>)*>')
NAMESPACE_STD_HASH = re.compile(r'namespace\s+std\s*\{[^}]*hash', re.DOTALL)

WAIVER_ANNOTATION_SPECIALIZATION = re.compile(r'@template_specialization_required\b', re.MULTILINE)
WAIVER_ANNOTATION_BLOAT = re.compile(r'@allow_binary_bloat\b', re.MULTILINE)
WAIVER_ANNOTATION_BLOAT_FULL = re.compile(
    r'@allow_binary_bloat:\s*(?P<reason>[^;]+);\s*'
    r'performance_gain:\s*(?P<gain>\d+)%;\s*'
    r'compile_time_increase:\s*(?P<increase>[\d.]+)s;\s*'
    r'benchmark_script:\s*(?P<script>\S+);\s*'
    r'threshold:\s*(?P<threshold>.+)',
    re.MULTILINE,
)
WAIVER_ANNOTATION_RESERVED = re.compile(r'@reserved_for_future_extension\b', re.MULTILINE)

BLOAT_MANDATORY_FIELDS = ("gain", "increase", "script", "threshold")


def _load_weights() -> dict:
    raw = load_weights_from_skill(SKILL_PATH)
    total = sum(raw.values())
    if abs(total - 1.0) > 0.01:
        raise ValueError(
            f"Template metaprogramming weights sum to {total*100:.0f}%, expected 100%."
        )
    return raw


def _has_cpp_files(index: FileIndex) -> bool:
    for f in index.files:
        if f["ext"] in CPP_EXTS or f["ext"] == ".h":
            return True
    return False


class TemplateMetaprogrammingMetrics:
    def __init__(self, root: str, build_dir: str = ""):
        self.root = root
        self.build_dir = build_dir
        self.weights = _load_weights()
        self.index = FileIndex(root, build_dir=build_dir)
        self.is_cpp_project = _has_cpp_files(self.index)
        self.graph = DepGraph()
        self._include_graph = {}
        self._template_info = {}
        self._header_influence_cache = {}
        self._content_cache = {}
        if self.is_cpp_project:
            self._build_include_graph()
            self._collect_template_info()
        self.git = GitHistory(root)

    def _read_cached(self, f):
        path = f["path"]
        if path in self._content_cache:
            return self._content_cache[path]
        try:
            content = read_text_smart(f["abs_path"])
            self._content_cache[path] = content
            return content
        except Exception:
            return None

    def _build_include_graph(self):
        header_files = {}
        source_files = {}

        for f in self.index.files:
            if f["ext"] in CPP_HEADER_EXTS or f["ext"] == ".h":
                header_files[f["path"]] = f
                self.graph.add_node(f["path"], f["lang"], f["abs_path"])
            elif f["ext"] in CPP_SOURCE_EXTS:
                source_files[f["path"]] = f
                self.graph.add_node(f["path"], f["lang"], f["abs_path"])

        path_to_node = {}
        for node_id in self.graph.nodes:
            path_to_node[os.path.normpath(node_id)] = node_id

        norm_lookup = {}
        stem_lookup = {}
        for node_id in self.graph.nodes:
            nid_norm = os.path.normpath(node_id).lower()
            norm_lookup[nid_norm] = node_id
            stem = os.path.splitext(os.path.basename(node_id))[0].lower()
            stem_lookup.setdefault(stem, []).append(node_id)

        inc_re = re.compile(r'#include\s+[<"]([^>"]+)[>"]')

        for f in self.index.files:
            if f["ext"] not in CPP_EXTS and f["ext"] != ".h":
                continue
            node_id = f["path"]
            content = self._read_cached(f)
            if content is None:
                continue

            includes = []
            for m in inc_re.finditer(content):
                inc_path = m.group(1)
                inc_basename = os.path.basename(inc_path)
                includes.append((inc_path, inc_basename))

                matched_node = None

                inc_norm = os.path.normpath(inc_path).lower()
                # O(1) direct lookup by normalized path
                matched_node = norm_lookup.get(inc_norm)

                if matched_node is None:
                    # O(1) fallback: lookup by file stem
                    inc_stem = os.path.splitext(inc_basename)[0].lower()
                    candidates = stem_lookup.get(inc_stem, [])
                    if len(candidates) == 1:
                        matched_node = candidates[0]
                    elif len(candidates) > 1:
                        for c in candidates:
                            if os.path.normpath(c).lower().endswith(inc_norm):
                                matched_node = c
                                break
                        if matched_node is None:
                            matched_node = candidates[0]

                if matched_node is not None:
                    self.graph.add_edge(node_id, matched_node)

            self._include_graph[node_id] = includes

    def _collect_template_info(self):
        template_defs = []
        extern_template_decls = []

        for f in self.index.files:
            if f["ext"] not in CPP_EXTS and f["ext"] != ".h":
                continue
            node_id = f["path"]
            content = self._read_cached(f)
            if content is None:
                continue

            has_template = bool(TEMPLATE_PATTERN.search(content))
            extern_count = len(EXTERN_TEMPLATE_PATTERN.findall(content))
            extern_count += len(EXTERN_TEMPLATE_FUNC_PATTERN.findall(content))

            max_depth = 0
            if has_template:
                nesting_depths = []
                for m in NESTED_ANGLE_PATTERN.finditer(content):
                    depth = _count_angle_depth(m.group(0))
                    if depth > 1:
                        nesting_depths.append(depth)
                line_nesting = _max_line_angle_depth(content)
                if line_nesting > max(nesting_depths) if nesting_depths else 0:
                    nesting_depths.append(line_nesting)
                max_depth = max(nesting_depths) if nesting_depths else 0

            self._template_info[f["path"]] = {
                "has_template": has_template,
                "extern_template_count": extern_count,
                "max_nesting_depth": max_depth,
                "content_length": len(content),
                "lines": content.count("\n") + 1,
            }

            if has_template:
                template_defs.append(f["path"])

            for _ in range(extern_count):
                extern_template_decls.append(f["path"])

        self._template_info["_all_template_files"] = template_defs
        self._template_info["_extern_template_decls"] = extern_template_decls

    def calc_compile_time_coupling(self) -> tuple:
        if not self.is_cpp_project:
            return None, {}

        header_influence = self._compute_header_influence()
        if not header_influence:
            return 100.0, {"avg_influence": 0, "details": "no C/C++ headers found"}

        scores = []
        details = {}
        for hpath, influence_count in header_influence.items():
            I = influence_count
            if I == 0:
                s = 100
            elif I <= 10:
                s = 100 - I * 1.5
            elif I <= 50:
                s = 85 - (I - 10) * 0.7
            elif I <= 100:
                s = 57 - (I - 50) * 0.5
            else:
                s = max(0, 32 - (I - 100) * 0.3)
            scores.append(s)
            details[hpath] = {"influence": I, "score": round(s, 2)}

        avg_score = sum(scores) / len(scores) if scores else 100
        return round(avg_score, 2), {"avg_influence": round(sum(header_influence.values()) / len(header_influence), 2) if header_influence else 0, "details": details}

    def _compute_header_influence(self) -> dict:
        if self._header_influence_cache:
            return self._header_influence_cache

        header_nodes = set()
        source_nodes = set()
        for f in self.index.files:
            if f["ext"] in CPP_HEADER_EXTS or f["ext"] == ".h":
                header_nodes.add(f["path"])
            elif f["ext"] in CPP_SOURCE_EXTS:
                source_nodes.add(f["path"])

        if not header_nodes or not source_nodes:
            self._header_influence_cache = {}
            return self._header_influence_cache

        # Build adjacency dict once
        from collections import deque
        adj = defaultdict(set)
        for s, d in self.graph.edges:
            adj[s].add(d)

        header_influence = {h: set() for h in header_nodes}

        for src in source_nodes:
            visited = set()
            queue = deque([src])
            while queue:
                node = queue.popleft()
                if node in visited:
                    continue
                visited.add(node)
                for neighbor in adj.get(node, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)
            for h in (header_nodes & visited):
                header_influence[h].add(src)

        result = {h: len(sources) for h, sources in header_influence.items()}
        self._header_influence_cache = result
        return result

    def calc_template_redundancy(self) -> tuple:
        if not self.is_cpp_project:
            return None, {}

        template_usage = defaultdict(int)
        template_name_pattern = re.compile(
            r'template\s*<[^>]*>\s*(?:class|struct|typename)\s+(\w+)\s*(?:<[^>]*>)?\s*'
        )

        for f in self.index.files:
            if f["ext"] not in CPP_EXTS and f["ext"] != ".h":
                continue
            content = self._read_cached(f)
            if content is None:
                continue

            if not TEMPLATE_PATTERN.search(content):
                continue

            param_usage = defaultdict(int)

            specialized_patterns = re.findall(
                r'(\w+)\s*<\s*(?:\w+\s*::\s*)*\w+\s*>', content
            )
            for name in specialized_patterns:
                if name[0].isupper() or name in ('std', 'vector', 'map', 'set',
                                                  'list', 'deque', 'shared_ptr',
                                                  'unique_ptr', 'optional', 'variant'):
                    param_usage[name] += 1

            for name, count in param_usage.items():
                template_usage[name] += count

        if not template_usage:
            return 100.0, {"redundancy_ratio": 0, "total_instantiations": 0, "unique_instantiations": 0}

        total = sum(template_usage.values())
        unique = len(template_usage)
        redundancy_ratio = (total - unique) / total if total > 0 else 0

        if redundancy_ratio == 0:
            score = 100
        elif redundancy_ratio <= 0.1:
            score = 90
        elif redundancy_ratio <= 0.2:
            score = 80 - (redundancy_ratio - 0.1) * 100
        elif redundancy_ratio <= 0.4:
            score = 70 - (redundancy_ratio - 0.2) * 150
        else:
            score = max(0, 40 - (redundancy_ratio - 0.4) * 100)

        return round(max(0, score), 2), {
            "redundancy_ratio": round(redundancy_ratio, 4),
            "total_instantiations": total,
            "unique_instantiations": unique,
        }

    def calc_header_influence_radius(self) -> tuple:
        if not self.is_cpp_project:
            return None, {}

        source_nodes = set()
        for f in self.index.files:
            if f["ext"] in CPP_SOURCE_EXTS:
                source_nodes.add(f["path"])

        header_nodes = set()
        for f in self.index.files:
            if f["ext"] in CPP_HEADER_EXTS or f["ext"] == ".h":
                header_nodes.add(f["path"])

        if not header_nodes:
            return 100.0, {"avg_radius": 0, "details": {}}

        adj = defaultdict(set)
        radj = defaultdict(set)
        for s, d in self.graph.edges:
            adj[s].add(d)
            radj[d].add(s)

        radii = {}
        for h in header_nodes:
            visited = {h}
            queue = [(h, 0)]
            reachable_sources = set()
            while queue:
                node, depth = queue.pop(0)
                if depth > 10:
                    continue
                if node in source_nodes and node != h:
                    reachable_sources.add(node)
                for neighbor in radj.get(node, set()):
                    if neighbor not in visited and depth < 10:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))
            R = len(reachable_sources)
            if R == 0:
                s = 100
            elif R <= 10:
                s = 95
            elif R <= 30:
                s = 85 - (R - 10) * 0.5
            elif R <= 80:
                s = 75 - (R - 30) * 0.3
            elif R <= 150:
                s = 60 - (R - 80) * 0.2
            else:
                s = max(0, 46 - (R - 150) * 0.15)
            radii[h] = {"radius": R, "score": round(s, 2)}

        avg_score = sum(v["score"] for v in radii.values()) / len(radii) if radii else 100
        avg_radius = sum(v["radius"] for v in radii.values()) / len(radii) if radii else 0

        return round(avg_score, 2), {"avg_radius": round(avg_radius, 2), "details": radii}

    def calc_template_nesting_depth(self) -> tuple:
        if not self.is_cpp_project:
            return None, {}

        max_depth_global = 0
        details = {}

        for f in self.index.files:
            if f["ext"] not in CPP_EXTS and f["ext"] != ".h":
                continue
            info = self._template_info.get(f["path"], {})
            d = info.get("max_nesting_depth", 0)
            if d > 0:
                details[f["path"]] = {"max_depth": d}
            max_depth_global = max(max_depth_global, d)

        D_max = max_depth_global
        if D_max <= 3:
            score = 100
        elif D_max <= 6:
            score = 80 - (D_max - 3) * 5
        elif D_max <= 10:
            score = 65 - (D_max - 6) * 4
        else:
            score = max(0, 49 - (D_max - 10) * 3)

        return round(score, 2), {"max_depth": D_max, "details": details}

    def calc_binary_bloat_ratio(self) -> tuple:
        if not self.is_cpp_project:
            return None, {}

        template_file_count = 0
        non_template_file_count = 0
        template_lines = 0
        non_template_lines = 0
        extern_template_count = 0

        for f in self.index.files:
            if f["ext"] not in CPP_EXTS and f["ext"] != ".h":
                continue
            info = self._template_info.get(f["path"], {})
            if not info:
                continue
            if info.get("has_template", False):
                template_file_count += 1
                template_lines += info.get("lines", 0)
            else:
                non_template_file_count += 1
                non_template_lines += info.get("lines", 0)
            extern_template_count += info.get("extern_template_count", 0)

        total_lines = template_lines + non_template_lines
        if total_lines == 0:
            return 100.0, {"bloat_ratio": 0, "template_lines": 0, "total_lines": 0}

        bloat_ratio = template_lines / total_lines * 100
        mitigation_factor = min(1.0, extern_template_count / max(1, template_file_count)) if template_file_count > 0 else 0
        adjusted_ratio = bloat_ratio * (1 - mitigation_factor * 0.3)

        ratio = adjusted_ratio
        if ratio <= 10:
            score = 100
        elif ratio <= 20:
            score = 90 - (ratio - 10) * 1
        elif ratio <= 35:
            score = 80 - (ratio - 20) * 1.2
        elif ratio <= 50:
            score = 62 - (ratio - 35) * 1.5
        else:
            score = max(0, 39.5 - (ratio - 50) * 0.8)

        return round(max(0, score), 2), {
            "bloat_ratio": round(bloat_ratio, 2),
            "adjusted_ratio": round(adjusted_ratio, 2),
            "template_lines": template_lines,
            "non_template_lines": non_template_lines,
            "total_lines": total_lines,
            "extern_template_count": extern_template_count,
            "mitigation_factor": round(mitigation_factor, 4),
        }

    def calc_unnecessary_templating(self) -> tuple:
        if not self.is_cpp_project:
            return None, {}

        template_defs = []
        template_usage_types = defaultdict(set)

        template_decl_pattern = re.compile(
            r'template\s*<\s*[^>]*\s*>\s*(?:class|struct|inline\s+)?\s*(\w+)\s*(?:<[^>]*>)?\s*'
        )

        template_use_pattern = re.compile(
            r'(\w+)\s*<\s*([^>]+)\s*>',
        )

        std_templates = {'std', 'vector', 'map', 'set', 'string', 'list',
                         'deque', 'array', 'unordered_map', 'unordered_set',
                         'shared_ptr', 'unique_ptr', 'weak_ptr', 'optional',
                         'variant', 'pair', 'tuple', 'function'}

        for f in self.index.files:
            if f["ext"] not in CPP_EXTS and f["ext"] != ".h":
                continue
            content = self._read_cached(f)
            if content is None:
                continue

            if not TEMPLATE_PATTERN.search(content):
                continue

            for m in template_decl_pattern.finditer(content):
                name = m.group(1)
                if name in std_templates:
                    continue
                template_defs.append(name)

            for m in template_use_pattern.finditer(content):
                name = m.group(1)
                params = m.group(2).strip()
                if name in std_templates:
                    continue
                if name[0].isupper() or '_' in name:
                    param_types = [p.strip().split()[-1] for p in params.split(',') if p.strip()]
                    for pt in param_types:
                        template_usage_types[name].add(pt)

        total_templates = len(template_defs)
        if total_templates == 0:
            return 100.0, {
                "total_templates": 0,
                "unnecessary_templates": 0,
                "ratio": 0,
            }

        unnecessary = 0
        unnecessary_details = []
        for name in template_defs:
            types_used = template_usage_types.get(name, set())
            if len(types_used) <= 1:
                unnecessary += 1
                unnecessary_details.append({
                    "name": name,
                    "types_used": list(types_used) if types_used else [],
                    "issue": "only_one_type" if types_used else "never_instantiated",
                })

        ratio = unnecessary / total_templates if total_templates > 0 else 0
        score = 100 - ratio * 150
        for detail in unnecessary_details:
            if detail["issue"] == "never_instantiated":
                score -= 10

        return round(max(0, score), 2), {
            "total_templates": total_templates,
            "unnecessary_templates": unnecessary,
            "ratio": round(ratio, 4),
            "details": unnecessary_details[:20],
        }

    def _collect_waiver_annotations(self) -> dict:
        waiver_locations = {
            "specialization": [],
            "binary_bloat": [],
            "binary_bloat_full": [],
            "reserved_extension": [],
        }
        for f in self.index.files:
            if f["ext"] not in CPP_EXTS and f["ext"] != ".h":
                continue
            content = self._read_cached(f)
            if content is None:
                continue
            if WAIVER_ANNOTATION_SPECIALIZATION.search(content):
                waiver_locations["specialization"].append(f["path"])
            bloat_match = WAIVER_ANNOTATION_BLOAT_FULL.search(content)
            if bloat_match:
                full_info = {k: bloat_match.group(k) for k in BLOAT_MANDATORY_FIELDS if bloat_match.group(k)}
                missing = [k for k in BLOAT_MANDATORY_FIELDS if k not in full_info]
                full_info["_missing_fields"] = missing
                full_info["_file"] = f["path"]
                waiver_locations["binary_bloat_full"].append(full_info)
                waiver_locations["binary_bloat"].append(f["path"])
            elif WAIVER_ANNOTATION_BLOAT.search(content):
                waiver_locations["binary_bloat"].append(f["path"])
            if WAIVER_ANNOTATION_RESERVED.search(content):
                waiver_locations["reserved_extension"].append(f["path"])
        return waiver_locations

    def check_mlr_rules(self) -> list:
        mlr_results = []

        if not self.is_cpp_project:
            return mlr_results

        waiver_annotations = self._collect_waiver_annotations()

        header_influence = self._compute_header_influence()

        cpp_header_files = []
        for f in self.index.files:
            if f["ext"] in CPP_HEADER_EXTS or f["ext"] == ".h":
                cpp_header_files.append(f)

        source_count = sum(1 for f in self.index.files if f["ext"] in CPP_SOURCE_EXTS)

        # MLR-013: 热模板头文件
        hot_headers = []
        for hpath, influence in header_influence.items():
            if influence > 50:
                hot_headers.append((hpath, influence))
        if hot_headers:
            hot_headers.sort(key=lambda x: -x[1])
            mlr_results.append({
                "rule": "MLR-013", "name": "热模板头文件",
                "severity": "HIGH",
                "output_level": "WARNING",
                "count": len(hot_headers),
                "detail": f"{len(hot_headers)} 个头文件影响 >50 编译单元: " +
                          "; ".join(f"{h}({n})" for h, n in hot_headers[:10]),
            })

        # MLR-014: 模板重复实例化
        has_specialization_waiver = len(waiver_annotations["specialization"]) > 0
        # 收集所有显式 extern template 声明的模板名
        extern_tpl_names = set()
        ext_extern_re = re.compile(r'extern\s+template\s+(?:class|struct)\s+(\w+)\s*<', re.MULTILINE)
        for f in self.index.files:
            if f["ext"] not in CPP_EXTS and f["ext"] != ".h":
                continue
            content = self._read_cached(f)
            if content is None:
                continue
            for mt in ext_extern_re.finditer(content):
                extern_tpl_names.add(mt.group(1))
        # 过滤非实例化上下文: 排除函数参数、typedef、using、static_cast 等中的 <...> 匹配
        non_instantiation_before = re.compile(
            r'(?:typedef|using|return|new|throw|delete|sizeof|decltype)\s*$'
            r'|,\s*$'
            r'|\(\s*$'
            r'|<\s*$'
            r'|:\s*$'
            r'|=\s*$'
            r'|enum\s+(?:class\s+)?\w*\s*$',
            re.MULTILINE
        )
        template_dup = defaultdict(list)
        for f in self.index.files:
            if f["ext"] not in CPP_SOURCE_EXTS:
                continue
            content = self._read_cached(f)
            if content is None:
                continue
            for m in re.finditer(r'(\w+)\s*<\s*([^>]+)\s*>', content):
                name = m.group(1)
                params = m.group(2).strip()
                if not (name[0].isupper() or '_' in name):
                    continue
                # 检查前面上下文是否是非实例化场景
                before = content[max(0, m.start() - 40):m.start()]
                if non_instantiation_before.search(before):
                    continue
                # 排除常见的标准库/第三方命名空间前缀
                if params in ("dim", "spacedim", "number", "Scalar", "T") and len(params) <= 15:
                    continue
                # 排除已使用 extern template 显式声明的模板（显式实例化管理）
                if name in extern_tpl_names:
                    continue
                key = f"{name}<{params}>"
                template_dup[key].append(f["path"])

        redundant = {k: v for k, v in template_dup.items() if len(v) > 2}
        if redundant:
            redundant_count = len(redundant)
            redundant_details = [(k, len(v)) for k, v in sorted(redundant.items(), key=lambda x: -len(x[1]))[:10]]
            severity_014 = "HIGH"
            output_level_014 = "INFO" if has_specialization_waiver else "WARNING"
            waiver_note_014 = " (豁免: 检测到 @template_specialization_required 注解，降为 INFO/需审查)" if has_specialization_waiver else ""
            mlr_results.append({
                "rule": "MLR-014", "name": "模板重复实例化",
                "severity": severity_014,
                "output_level": output_level_014,
                "count": redundant_count,
                "detail": f"{redundant_count} 个模板被 >2 个编译单元重复实例化: " +
                          "; ".join(f"{k}×{n}" for k, n in redundant_details) +
                          waiver_note_014,
                "waivable": True,
            })

        # MLR-015: 头文件传染链过长
        adj = defaultdict(set)
        for s, d in self.graph.edges:
            adj[s].add(d)

        contagious_headers = []
        for hpath in header_influence:
            if not any(hpath.endswith(ext) for ext in CPP_HEADER_EXTS | {".h"}):
                continue
            visited = {hpath}
            queue = [(hpath, 0)]
            transitive_count = 0
            while queue:
                node, depth = queue.pop(0)
                if depth > 3:
                    continue
                for neighbor in adj.get(node, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        transitive_count += 1
                        queue.append((neighbor, depth + 1))
            if transitive_count > 20:
                contagious_headers.append((hpath, transitive_count))

        if contagious_headers:
            contagious_headers.sort(key=lambda x: -x[1])
            mlr_results.append({
                "rule": "MLR-015", "name": "头文件传染链过长",
                "severity": "MEDIUM",
                "output_level": "WARNING",
                "count": len(contagious_headers),
                "detail": f"{len(contagious_headers)} 个头文件存在 >3 层传播链 (影响 >20 文件): " +
                          "; ".join(f"{h}({n})" for h, n in contagious_headers[:10]),
            })

        # MLR-016: 模板嵌套深度过高
        max_depth = 0
        deep_files = []
        for f in self.index.files:
            if f["ext"] not in CPP_EXTS and f["ext"] != ".h":
                continue
            info = self._template_info.get(f["path"], {})
            d = info.get("max_nesting_depth", 0)
            if d > 6:
                deep_files.append((f["path"], d))
            max_depth = max(max_depth, d)

        if deep_files:
            mlr_results.append({
                "rule": "MLR-016", "name": "模板嵌套深度过高",
                "severity": "MEDIUM",
                "output_level": "WARNING",
                "count": len(deep_files),
                "detail": f"最大模板嵌套深度 {max_depth}，{len(deep_files)} 个文件嵌套 >6: " +
                          "; ".join(f"{p}(D={d})" for p, d in deep_files[:10]),
            })

        # MLR-017: 二进制膨胀超标
        bloat_score, bloat_detail = self.calc_binary_bloat_ratio()
        bloat_ratio = bloat_detail.get("bloat_ratio", 0)
        has_bloat_waiver = len(waiver_annotations["binary_bloat"]) > 0
        bloat_waiver_full = waiver_annotations.get("binary_bloat_full", [])
        has_complete_bloat_waiver = len(bloat_waiver_full) > 0 and all(
            len(info.get("_missing_fields", [])) == 0 for info in bloat_waiver_full
        )
        cross_rule_014_017 = (
            has_specialization_waiver and has_bloat_waiver
        )
        if bloat_ratio > 35:
            severity_017 = "MEDIUM"
            if has_complete_bloat_waiver:
                output_level_017 = "INFO"
                waiver_detail_017 = " (豁免: 检测到完整 @allow_binary_bloat 注解，需审查+性能验证)"
            elif has_bloat_waiver and not has_complete_bloat_waiver:
                output_level_017 = "WARNING"
                waiver_detail_017 = " (豁免语法缺失: 缺少 performance_gain/benchmark_script/threshold 等必填字段，维持 WARNING)"
            else:
                output_level_017 = "WARNING"
                waiver_detail_017 = ""
            if cross_rule_014_017:
                waiver_detail_017 += " [跨规则协调: MLR-014豁免已通过，但MLR-017仍需性能数据验证]"
            mlr_results.append({
                "rule": "MLR-017", "name": "二进制膨胀超标",
                "severity": severity_017,
                "output_level": output_level_017,
                "count": 1,
                "detail": f"模板代码占比 {bloat_ratio:.1f}%，超过 35% 警戒线" + waiver_detail_017,
                "waivable": True,
            })

        # MLR-018: 虚泛型（镀金模板）
        _, unnes_detail = self.calc_unnecessary_templating()
        unnecessary_count = unnes_detail.get("unnecessary_templates", 0)
        total_templates = unnes_detail.get("total_templates", 0)
        if total_templates > 0 and unnecessary_count > 0:
            never_instantiated = sum(
                1 for d in unnes_detail.get("details", [])
                if d.get("issue") == "never_instantiated"
            )
            has_reserved_waiver = len(waiver_annotations["reserved_extension"]) > 0
            severity_018 = "HIGH"
            output_level_018 = "INFO" if has_reserved_waiver else "WARNING"
            waiver_note = " (豁免: 检测到 @reserved_for_future_extension 注解)" if has_reserved_waiver else ""
            mlr_results.append({
                "rule": "MLR-018", "name": "虚泛型（镀金模板）",
                "severity": severity_018,
                "output_level": output_level_018,
                "count": unnecessary_count,
                "detail": f"{unnecessary_count}/{total_templates} 个模板仅使用一种类型或未实例化（未实例化: {never_instantiated}）{waiver_note}",
                "waivable": True,
            })

        # MLR-019: 未使用 extern template 优化
        has_many_instances = len(template_dup) > 5
        has_extern = any(
            self._template_info.get(f["path"], {}).get("extern_template_count", 0) > 0
            for f in self.index.files
            if f["ext"] in CPP_EXTS or f["ext"] == ".h"
        )
        if has_many_instances and not has_extern:
            mlr_results.append({
                "rule": "MLR-019", "name": "未使用 extern template 优化",
                "severity": "LOW",
                "output_level": "INFO",
                "count": 1,
                "detail": f"项目有 {len(template_dup)} 个模板实例化但未发现 extern template 声明",
            })

        # MLR-020: 头文件包含不必要模板定义
        for f in cpp_header_files:
            content = self._read_cached(f)
            if content is None:
                continue
            template_def_count = len(TEMPLATE_PATTERN.findall(content))
            if template_def_count > 5:
                has_inline = bool(re.search(r'\binline\b', content))
                has_impl = bool(re.search(r'(?:class|struct)\s+\w+\s*(?::\s*(?:public|private|protected)\s+\w+)*\s*\{', content))
                if has_impl and not has_inline and template_def_count > 3:
                    mlr_results.append({
                        "rule": "MLR-020", "name": "头文件包含不必要模板定义",
                        "severity": "MEDIUM",
                        "output_level": "WARNING",
                        "count": 1,
                        "detail": f"{f['path']}: {template_def_count} 处模板定义且非 inline，建议移至 .cpp 或使用显式实例化",
                    })

        # MLR-021: 模板特化放在错误命名空间
        for f in self.index.files:
            if f["ext"] not in CPP_EXTS and f["ext"] != ".h":
                continue
            content = self._read_cached(f)
            if content is None:
                continue
            if NAMESPACE_STD_HASH.search(content):
                mlr_results.append({
                    "rule": "MLR-021", "name": "模板特化放在错误命名空间",
                    "severity": "LOW",
                    "output_level": "INFO",
                    "count": 1,
                    "detail": f"{f['path']}: 发现 namespace std 中的 hash 特化，应使用命名空间注入",
                })

        # MLR-022: 递归模板导致实例化爆炸
        # 匹配模式: struct Name<...> : Name<...>
        # 使用 (?!\w) 确保类名完整，避免 \w+ 回溯产生的假阳性
        recursive_pattern = re.compile(
            r'(?:class|struct)\s+'
            r'(\w+)(?!\w)'                                   # capture full class name
            r'[^{]*?:\s*(?:public|private|protected\s+)?'    # optional base access
            r'\s*\1\s*<',                                     # same name followed by <
            re.MULTILINE
        )
        # 预处理：去掉行注释和块注释，避免在注释/字符串中误匹配
        comment_re = re.compile(r'//[^\n]*|/\*.*?\*/', re.DOTALL)
        for f in self.index.files:
            if f["ext"] not in CPP_EXTS and f["ext"] != ".h":
                continue
            content = self._read_cached(f)
            if content is None:
                continue
            clean = comment_re.sub('', content)
            if recursive_pattern.search(clean):
                info = self._template_info.get(f["path"], {})
                depth = info.get("max_nesting_depth", 0)
                mlr_results.append({
                    "rule": "MLR-022", "name": "递归模板导致实例化爆炸",
                    "severity": "HIGH",
                    "output_level": "ERROR",
                    "count": 1,
                    "detail": f"{f['path']}: 检测到递归模板模式，嵌套深度 {depth}",
                })

        # MLR-023: 同一模板在多处重复实例化（与 MLR-014 合并扣分）
        if redundant:
            total_instances_across_files = sum(len(v) for v in redundant.values())
            mlr_results.append({
                "rule": "MLR-023", "name": "同一模板在多处重复实例化",
                "severity": "MEDIUM",
                "output_level": "WARNING",
                "count": total_instances_across_files,
                "detail": f"{len(redundant)} 种模板在 >2 个编译单元中重复实例化，共 {total_instances_across_files} 处",
                "merge_to": "MLR-014",
            })

        # MLR-024: 头文件包含循环依赖
        cycle_detector = defaultdict(set)
        for s, d in self.graph.edges:
            if os.path.basename(s) != os.path.basename(d):
                cycle_detector[s].add(d)

        cycles_found = []
        visited = set()

        def _find_cycles(node, path, path_set):
            visited.add(node)
            for neighbor in cycle_detector.get(node, set()):
                if neighbor in path_set:
                    cycle_start = path.index(neighbor)
                    cycles_found.append(path[cycle_start:] + [neighbor])
                elif neighbor not in visited:
                    _find_cycles(neighbor, path + [neighbor], path_set | {neighbor})

        for node in list(cycle_detector.keys()):
            if node not in visited:
                _find_cycles(node, [node], {node})

        header_cycles = []
        for cycle in cycles_found:
            if all(any(n.endswith(ext) for ext in CPP_HEADER_EXTS | {".h"}) for n in cycle):
                header_cycles.append(cycle)

        if header_cycles:
            has_module_ifc = any(
                f["ext"] in (".ixx", ".cppm", ".mpp")
                for f in self.index.files
            )
            severity_024 = "LOW" if has_module_ifc else "HIGH"
            output_level_024 = "LOW" if has_module_ifc else "ERROR"
            mlr_results.append({
                "rule": "MLR-024", "name": "头文件包含循环依赖",
                "severity": severity_024,
                "output_level": output_level_024,
                "count": len(header_cycles),
                "detail": f"发现 {len(header_cycles)} 个头文件循环依赖: " +
                          "; ".join(" → ".join(c[:5]) for c in header_cycles[:5]) +
                          (" (检测到 C++20 Modules 接口文件，降级为 LOW)" if has_module_ifc else ""),
            })

        return mlr_results

    def all_metrics(self) -> dict:
        weights = self.weights

        if not self.is_cpp_project:
            return {
                "overall": None,
                "weights_source": SKILL_PATH,
                "weights_applied": weights,
                "is_cpp_project": False,
                "cpp_file_count": 0,
                "dimensions": {
                    "compile_time_fanin": {"score": None, "detail": None},
                    "template_redundancy": {"score": None, "detail": None},
                    "header_influence_radius": {"score": None, "detail": None},
                    "template_nesting_depth": {"score": None, "detail": None},
                    "binary_bloat_ratio": {"score": None, "detail": None},
                    "unnecessary_templating": {"score": None, "detail": None},
                },
                "mlr_violations": [],
                "files": {
                    "total": self.index.total_files(),
                    "cpp_files": 0,
                },
            }

        dim1, dim1_detail = self.calc_compile_time_coupling()
        dim2, dim2_detail = self.calc_template_redundancy()
        dim3, dim3_detail = self.calc_header_influence_radius()
        dim4, dim4_detail = self.calc_template_nesting_depth()
        dim5, dim5_detail = self.calc_binary_bloat_ratio()
        dim6, dim6_detail = self.calc_unnecessary_templating()

        mlr_violations = self.check_mlr_rules()

        dim_weights = [
            ("编译时扇入", weights.get("编译时扇入", 0.20)),
            ("模板实例化重复率", weights.get("模板实例化重复率", 0.20)),
            ("头文件影响半径", weights.get("头文件影响半径", 0.15)),
            ("模板嵌套深度", weights.get("模板嵌套深度", 0.10)),
            ("二进制膨胀率", weights.get("二进制膨胀率", 0.15)),
            ("不必要的模板化", weights.get("不必要的模板化", 0.20)),
        ]

        dim_scores = {
            "编译时扇入": dim1,
            "模板实例化重复率": dim2,
            "头文件影响半径": dim3,
            "模板嵌套深度": dim4,
            "二进制膨胀率": dim5,
            "不必要的模板化": dim6,
        }

        overall = sum(
            dim_scores.get(k, 0) * w
            for k, w in dim_weights
            if dim_scores.get(k) is not None
        )

        cpp_file_count = sum(
            1 for f in self.index.files
            if f["ext"] in CPP_EXTS or f["ext"] == ".h"
        )

        return {
            "overall": round(overall, 2),
            "weights_source": SKILL_PATH,
            "weights_applied": weights,
            "is_cpp_project": True,
            "cpp_file_count": cpp_file_count,
            "dimensions": {
                "compile_time_fanin": {"score": dim1, "detail": dim1_detail},
                "template_redundancy": {"score": dim2, "detail": dim2_detail},
                "header_influence_radius": {"score": dim3, "detail": dim3_detail},
                "template_nesting_depth": {"score": dim4, "detail": dim4_detail},
                "binary_bloat_ratio": {"score": dim5, "detail": dim5_detail},
                "unnecessary_templating": {"score": dim6, "detail": dim6_detail},
            },
            "dim_names": {k: k for k in dim_scores},
            "mlr_violations": mlr_violations,
            "files": {
                "total": self.index.total_files(),
                "cpp_files": cpp_file_count,
            },
        }


def _count_angle_depth(s: str) -> int:
    max_depth = 0
    current_depth = 0
    for ch in s:
        if ch == '<':
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif ch == '>':
            current_depth = max(0, current_depth - 1)
    return max_depth


def _max_line_angle_depth(content: str) -> int:
    max_depth_global = 0
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
            continue
        depth = 0
        max_depth_line = 0
        in_string = False
        in_char = False
        i = 0
        while i < len(stripped):
            ch = stripped[i]
            if ch == '"' and not in_char:
                in_string = not in_string
            elif ch == "'" and not in_string:
                if i + 2 < len(stripped) and stripped[i + 2] == "'":
                    in_char = not in_char
                    i += 2
            elif not in_string and not in_char:
                if ch == '<':
                    depth += 1
                    max_depth_line = max(max_depth_line, depth)
                elif ch == '>':
                    depth = max(0, depth - 1)
            i += 1
        if max_depth_line > 1:
            max_depth_global = max(max_depth_global, max_depth_line)
    return max_depth_global


import statistics


def calibrate_thresholds(sample_metrics: list) -> dict:
    """基于 8.1 节的基线校准统计方法，从模块采样指标计算项目专有阈值。

    Args:
        sample_metrics: 20-30 个模块的指标采样数据列表，
            每个元素为包含以下键的字典：
            - fan_in: 编译时扇入值
            - influence_radius: 影响半径值
            - redundancy_rate: 模板重复率 (0-1)
            - bloat_rate: 二进制膨胀率 (0-1)
            - nesting_depth: 模板嵌套深度

    Returns:
        dict: 校准后的阈值
    """
    if len(sample_metrics) < 5:
        return {
            "fan_in": 50,
            "influence_radius": 80,
            "redundancy_rate": 0.40,
            "bloat_rate": 0.35,
            "nesting_depth": 10,
        }

    def _percentile(data, p):
        s = sorted(data)
        idx = (p / 100) * (len(s) - 1)
        lo = int(idx)
        hi = min(lo + 1, len(s) - 1)
        frac = idx - lo
        return s[lo] * (1 - frac) + s[hi] * frac

    fan_ins = [m["fan_in"] for m in sample_metrics if "fan_in" in m]
    radii = [m["influence_radius"] for m in sample_metrics if "influence_radius" in m]
    redundancies = [m["redundancy_rate"] for m in sample_metrics if "redundancy_rate" in m]
    bloats = [m["bloat_rate"] for m in sample_metrics if "bloat_rate" in m]
    depths = [m["nesting_depth"] for m in sample_metrics if "nesting_depth" in m]

    result = {}

    if len(fan_ins) >= 5:
        q3 = _percentile(fan_ins, 75)
        q1 = _percentile(fan_ins, 25)
        iqr = q3 - q1
        result["fan_in"] = max(10, q3 + 1.5 * iqr)
    else:
        result["fan_in"] = 50

    if len(radii) >= 5:
        q3 = _percentile(radii, 75)
        q1 = _percentile(radii, 25)
        iqr = q3 - q1
        result["influence_radius"] = q3 + 1.5 * iqr
    else:
        result["influence_radius"] = 80

    if len(redundancies) >= 5:
        med = statistics.median(redundancies)
        mad = statistics.median([abs(x - med) for x in redundancies])
        result["redundancy_rate"] = min(1.0, med + 2 * mad)
    else:
        result["redundancy_rate"] = 0.40

    if len(bloats) >= 5:
        q3 = _percentile(bloats, 75)
        q1 = _percentile(bloats, 25)
        iqr = q3 - q1
        result["bloat_rate"] = min(0.60, q3 + 1.5 * iqr)
    else:
        result["bloat_rate"] = 0.35

    if len(depths) >= 5:
        q3 = _percentile(depths, 75)
        q1 = _percentile(depths, 25)
        iqr = q3 - q1
        result["nesting_depth"] = max(5, q3 + iqr)
    else:
        result["nesting_depth"] = 10

    return result


def main():
    parser = argparse.ArgumentParser(description="模板元编程与编译时依赖膨胀评估")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--build-dir", default="", help="构建目录")
    parser.add_argument("--full", action="store_true", help="完整评估（6维 + MLR）")
    parser.add_argument("--mlr-only", action="store_true", help="仅检测 MLR 规则")

    args = parser.parse_args()

    metrics = TemplateMetaprogrammingMetrics(args.root, build_dir=args.build_dir)

    if args.mlr_only:
        result = {"mlr_violations": metrics.check_mlr_rules()}
    else:
        result = metrics.all_metrics()

    out_dir = ensure_output_dir(args.root)
    report_path = write_report(out_dir, "template-metrics.json", result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()