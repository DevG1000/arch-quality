"""
arch_metrics_standard.py — 标准架构质量指标

实现 SOFTWARE_ARCHITECTURE_QUALITY_GUIDE.md 中的 4 大分类评分。
权重从 skills/arch-quality.md 动态解析。
"""

import os
import re
import json
import argparse
from pathlib import Path
from collections import defaultdict

# 确保可以引用 arch_core.py
from arch_quality.arch_core import (
    FileIndex, DepGraph, GitHistory,
    load_weights_from_skill, ensure_output_dir, write_report,
    read_text_smart, write_text_utf8, load_history
)

SKILL_PATH = str(Path(__file__).parent / "skills" / "arch-quality.md")


def _lang_count(files) -> dict:
    """按语言统计文件数"""
    counts = defaultdict(int)
    for f in files:
        counts[f["lang"]] += 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def _resolve_weights():
    """解析 arch-quality.md 中的权重

    从 skill 文件解析所有 | name | N% | 行，按已知键名分组到各层级。
    每层独立验证权重和是否为 100%。
    """
    raw = load_weights_from_skill(SKILL_PATH)

    weights = {
        "main": {},
        "structural": {},
        "design": {},
        "doc": {},
        "evolution": {},
    }

    # 兼容新/旧子维度键名："测试覆盖度"(新) 与 "可测试性"(旧)。清理期后移除旧键。
    _STRUCTURAL_KEY_ALIAS = {"可测试性": "测试覆盖度"}

    layers = {
        "main": ["结构质量", "设计质量", "文档质量", "演进质量"],
        "structural": ["模块化", "耦合度", "内聚度", "复杂度", "测试覆盖度"],
        "design": ["SOLID原则", "设计模式", "架构风格", "反模式"],
        "doc": ["README完整性", "CHANGELOG完整性", "ADR覆盖率",
                "代码注释密度", "JSDoc覆盖率", "架构文档完整性"],
        "evolution": ["历史可追溯性", "技术债务趋势", "依赖过时程度",
                      "废弃代码比例", "增量质量", "问题扣分"],
    }

    for layer, keys in layers.items():
        for k in keys:
            if k in raw:
                weights[layer][k] = raw[k]
        # 仅结构质量层做新旧键名兼容（"可测试性"→"测试覆盖度"）
        if layer == "structural":
            for old_key, new_key in _STRUCTURAL_KEY_ALIAS.items():
                if old_key in raw and new_key not in weights[layer]:
                    weights[layer][new_key] = raw[old_key]
        total = sum(weights[layer].values())
        if abs(total - 1.0) > 0.01 and weights[layer]:
            raise ValueError(
                f"Weights in {SKILL_PATH} for layer '{layer}' sum to "
                f"{total*100:.0f}%, expected 100%."
            )

    return weights


class StandardMetrics:
    """标准架构质量指标计算"""

    def __init__(self, root: str, build_dir: str = "", test_dirs: list = None):
        self.root = root
        self.test_dirs = test_dirs or []
        self.weights = _resolve_weights()
        self.index = FileIndex(root, build_dir=build_dir)
        self.graph = DepGraph()
        self._build_graph()
        self._dim_cache = {}
        self.git = GitHistory(root)

    # ── 测试覆盖度辅助 ──
    def _is_test_file(self, f) -> bool:
        """判断文件是否属于测试文件（路径含 test/spec/tests 目录或文件名含 test/spec）"""
        path_l = f["path"].lower().replace("\\", "/")
        name = os.path.basename(path_l)
        if "/test" in path_l or path_l.startswith("test/") \
                or path_l.startswith("tests/") or "/tests/" in path_l:
            return True
        if "/spec" in path_l or path_l.startswith("spec/"):
            return True
        return "test_" in name or "_test" in name or name.endswith("_spec.py") \
            or name.startswith("test_") or ".test." in name

    def _test_and_source_files(self):
        """将 index.files 分为测试文件与源码文件；返回 (test_files, source_files)"""
        test_files = [f for f in self.index.files if self._is_test_file(f)]
        indexed_paths = {f["path"].lower().replace("\\", "/") for f in self.index.files}
        source_files = [f for f in self.index.files if not self._is_test_file(f)]

        # out-of-tree 测试根目录：声明在 test_dirs 下的文件计入测试文件
        for td in self.test_dirs:
            td_norm = td.replace("\\", "/").strip("/")
            for f in self.index.files:
                p = f["path"].lower().replace("\\", "/")
                if p.startswith(td_norm + "/"):
                    if f not in test_files:
                        test_files.append(f)
                        if f in source_files:
                            source_files.remove(f)
        return test_files, source_files

    def _has_binding_layer(self) -> bool:
        """检测项目是否存在绑定层（pybind11 .def / SWIG）"""
        for f in self.index.files:
            if self._is_test_file(f):
                continue  # 排除测试/合成项目文件
            ext = f["ext"]
            if ext in (".i", ".swg"):
                return True
            if ext == ".cpp":
                try:
                    content = read_text_smart(f["abs_path"])
                except Exception:
                    content = ""
                if ".def(" in content or "py::" in content:
                    return True
        return False

    def calc_test_coverage(self):
        """测试覆盖度：4 层评分（目录/语言/文件比/绑定层）

        多语言项目: L1×30% + L2×25% + L3×25% + L4×20%
        单语言项目: L4 权重按比例并入 L1-L3 → L1×37.5% + L2×31.25% + L3×31.25%
        """
        test_files, source_files = self._test_and_source_files()
        total = self.index.total_files()
        if total == 0:
            return 0.0, {"dir_coverage": 0, "lang_coverage": 0, "file_ratio": 0,
                         "binding_coverage": 0, "dir_score": 0, "lang_score": 0,
                         "file_score": 0, "binding_score": 0}

        # L1 目录覆盖：有测试的源码目录占比（模块级一一对应语义）
        # 对齐《软件架构质量评估验证案例集（1.3版)》1.5 案例：
        #   20 个源码目录仅 9 个有对应测试目录 → L1=45%。
        # 对应关系识别（满足其一即覆盖）:
        #   a) colocated: 源码目录下存在 test/tests 子目录（src/modX/test）
        #   b) mirrored 模块: 测试目录与源码目录按模块名对应（src/modX ↔ tests/modX）
        #   c) 平铺根: 顶层 src/ 单层源码目录 + 顶层 tests/（src ↔ tests 平铺布局）
        test_dirs = set()
        source_dirs = set()
        for f in test_files:
            d = os.path.dirname(f["path"]).replace("\\", "/")
            test_dirs.add(d)
        for f in source_files:
            d = os.path.dirname(f["path"]).replace("\\", "/")
            if d and not self._is_test_file(f):
                source_dirs.add(d)
        # 忽略非源码测试目录自身（如顶层 tests/、test/）
        ignored = {"tests", "test", "spec", "tutorials"}
        source_dirs = {d for d in source_dirs if d.split("/")[0] not in ignored}

        _TEST_ROOTS = {"tests", "test", "spec"}

        def _dir_covered(sd: str, tdirs: set) -> bool:
            parts = sd.split("/")
            sbase = parts[-1]
            for td in tdirs:
                # a) colocated: src/modX/test(s)[/...]
                if (td == sd + "/test" or td == sd + "/tests"
                        or td.startswith(sd + "/test/")
                        or td.startswith(sd + "/tests/")):
                    return True
            for td in tdirs:
                tparts = td.split("/")
                # b) mirrored 模块: 测试目录与源码目录 basename 一致
                #    src/modX ↔ tests/modX ; 也支持 modX ↔ tests/modX
                if tparts[0] in _TEST_ROOTS and tparts[-1] == sbase:
                    # 平铺根特例不在此处理（见 c）
                    if len(parts) >= 2 or len(tparts) == 1:
                        return True
                # 尾部路径对齐: src/modX ↔ tests/modX (src 根被剥除)
                if (tparts[0] in _TEST_ROOTS and len(parts) >= 2
                        and len(tparts) >= 2 and parts[1:] == tparts[1:]):
                    return True
            # c) 平铺根: 单层源码目录（src）+ 顶层测试根（tests）→ 覆盖
            if len(parts) == 1 and any(td in _TEST_ROOTS for td in tdirs):
                return True
            return False

        covered_src_dirs = set(sd for sd in source_dirs if _dir_covered(sd, test_dirs))
        dir_coverage = len(covered_src_dirs) / len(source_dirs) if source_dirs else 0

        # L2 语言覆盖：有测试文件的语言占比
        test_langs = {f["lang"] for f in test_files}
        all_langs = {f["lang"] for f in self.index.files}
        lang_coverage = len(test_langs) / len(all_langs) if all_langs else 0

        # L3 文件比：测试文件 / (源码文件 × 0.3)
        if source_files:
            file_ratio = len(test_files) / (len(source_files) * 0.3)
        else:
            file_ratio = 1.0
        file_ratio = min(1.0, file_ratio)

        # L4 绑定层覆盖：多语言项目，有测试的绑定函数占比
        binding_score = 0.0
        binding_coverage = 0.0
        is_multilang = len(all_langs) > 1
        if is_multilang and self._has_binding_layer():
            bound_names = self._collect_bound_names()
            if bound_names:
                tested = sum(1 for b in bound_names if self._bound_name_tested(b, test_files))
                binding_coverage = tested / len(bound_names)
                binding_score = binding_coverage * 100

        dir_score = dir_coverage * 100
        lang_score = lang_coverage * 100
        file_score = file_ratio * 100

        if is_multilang:
            score = (dir_score * 0.30 + lang_score * 0.25 + file_score * 0.25
                     + binding_score * 0.20)
        else:
            score = (dir_score * 0.375 + lang_score * 0.3125 + file_score * 0.3125)

        detail = {
            "dir_coverage": round(dir_coverage, 4),
            "lang_coverage": round(lang_coverage, 4),
            "file_ratio": round(file_ratio, 4),
            "binding_coverage": round(binding_coverage, 4),
            "dir_score": round(dir_score, 2),
            "lang_score": round(lang_score, 2),
            "file_score": round(file_score, 2),
            "binding_score": round(binding_score, 2),
            "test_files_by_lang": dict(_lang_count(test_files)),
            "source_files_by_lang": dict(_lang_count(source_files)),
            "is_multilang": is_multilang,
        }
        return max(0, min(100, score)), detail

    def _collect_bound_names(self):
        """收集绑定层导出的函数名（pybind11 .def() 与 SWIG %extend/%inline）"""
        bound = set()
        for f in self.index.files:
            if self._is_test_file(f):
                continue  # 排除测试/合成项目文件（避免污染绑定层检测）
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                content = ""
            if f["ext"] == ".cpp":
                for m in re.finditer(r'\.def\s*\(\s*["\'](\w+)["\']', content):
                    bound.add(m.group(1))
            elif f["ext"] in (".i", ".swg"):
                for m in re.finditer(r'%\s*(?:extend|inline)\s+[\w:<>,*&\s]+?\s*\{?', content):
                    pass
                for m in re.finditer(r'%\s*extend\s+\S+\s*\{\s*([^}]*)\}', content, re.DOTALL):
                    for n in re.finditer(r'(\w+)\s*\(', m.group(1)):
                        if n.group(1) not in ("if", "for", "while", "return"):
                            bound.add(n.group(1))
                for m in re.finditer(r'%\s*inline\s+[^\{]*\{([^}]*)\}', content, re.DOTALL):
                    for n in re.finditer(r'(\w+)\s*\(', m.group(1)):
                        if n.group(1) not in ("if", "for", "while", "return"):
                            bound.add(n.group(1))
        return bound

    def _bound_name_tested(self, bound_name: str, test_files) -> bool:
        """判断绑定函数名是否出现在任一测试文件中"""
        for tf in test_files:
            try:
                content = read_text_smart(tf["abs_path"])
            except Exception:
                continue
            if re.search(r'\b' + re.escape(bound_name) + r'\b', content):
                return True
        return False

    def _build_graph(self):
        """构建简化依赖图（基于 import/include 语句）"""
        for f in self.index.files:
            node_id = f["path"]
            self.graph.add_node(node_id, f["lang"], f["path"])
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                content = ""

            # Python imports
            if f["ext"] == ".py":
                for m in re.finditer(r"^(?:from|import)\s+(\S+)", content, re.MULTILINE):
                    target = m.group(1).split(".")[0]
                    if target != os.path.splitext(os.path.basename(f["path"]))[0]:
                        self.graph.add_edge(node_id, target)

            # C++ includes
            elif f["ext"] in (".cpp", ".hpp", ".h", ".c"):
                for m in re.finditer(r'#include\s+[<"](.+?)[>"]', content):
                    target = os.path.basename(m.group(1))
                    self.graph.add_edge(node_id, target)

    def calc_modularity(self):
        """模块化：平均每目录文件数，理想值 5"""
        if not self.index.files:
            return 0
        dirs = set()
        for f in self.index.files:
            d = os.path.dirname(f["path"])
            if d:
                dirs.add(d)
        num_dirs = len(dirs) or 1
        avg = self.index.total_files() / num_dirs
        score = 100 - abs(avg - 5) * 10
        return max(0, min(100, score))

    def calc_coupling(self):
        """耦合度：平均导入数"""
        if not self.graph.nodes:
            return 100
        num_files = len(self.graph.nodes)
        num_edges = len(self.graph.edges)
        avg = num_edges / num_files if num_files > 0 else 0
        score = 100 - avg * 10
        return max(0, min(100, score))

    def calc_cohesion(self):
        """内聚度：超大文件（>1000行）比例"""
        if not self.index.files:
            return 100
        self.index.total_lines()  # 填充惰性 lines（依赖真实行数）
        xlarge = sum(1 for f in self.index.files if f["lines"] > 1000)
        ratio = xlarge / self.index.total_files()
        score = 100 - ratio * 200
        return max(0, min(100, score))

    def calc_complexity(self):
        """复杂度：大文件（>200行）比例"""
        if not self.index.files:
            return 100
        self.index.total_lines()  # 填充惰性 lines（依赖真实行数）
        large = sum(1 for f in self.index.files if f["lines"] > 200)
        ratio = large / self.index.total_files()
        score = 100 - ratio * 300
        return max(0, min(100, score))

    def calc_structural_score(self):
        """结构质量综合分"""
        w = self.weights["structural"]
        tc_score, tc_detail = self.calc_test_coverage()
        scores = {
            "modularity": self.calc_modularity(),
            "coupling": self.calc_coupling(),
            "cohesion": self.calc_cohesion(),
            "complexity": self.calc_complexity(),
            "test_coverage": tc_score,
            "test_coverage_detail": tc_detail,
        }
        total = 0
        score_keys = ["modularity", "coupling", "cohesion", "complexity", "test_coverage"]
        for key in score_keys:
            weight_key = {"modularity": "模块化", "coupling": "耦合度",
                          "cohesion": "内聚度", "complexity": "复杂度",
                          "test_coverage": "测试覆盖度"}[key]
            total += scores[key] * w.get(weight_key, 0.2)
        return total, scores

    # ── 设计质量辅助 ──
    _DESIGN_PATTERNS = [
        ("Singleton", r"private\s+constructor.*static.*instance.*getInstance|getInstance\s*\(\s*\)"),
        ("Observer", r"addListener|removeListener|forEach.*listener"),
        ("Strategy", r"function\s*\[|Map<.*Function>|dict.*callable"),
        ("Factory", r"(?:switch|if)\s*\([^)]*\)[^;]*new\s+\w+"),
        ("Command", r"command\s*\[|CommandMap|commandMap"),
        ("TemplateMethod", r"this\.\w+\(\);\s*this\.\w+\(\);"),
        ("Adapter", r"implements\s+\w+.*wrap|class\s+\w+Adapter"),
        ("Facade", r"facade|Facade"),
        ("Decorator", r"@\w+\(|@Override|decorator"),
        ("Cache", r"cache\s*=\s*new|Cache<|Map<.*cache|_cache"),
        ("Retry", r"retry|backoff|Math\.min\s*\(.*Math\.pow"),
        ("CallbackInjection", r"__init__\s*\(\s*self,\s*\w+\s*[:=]?\s*\w+\s*\)|constructor\s*\([^)]*Function"),
    ]
    _STYLE_DIRS = {
        "layered": {"controller", "service", "repository", "dao", "handler"},
        "mvc": {"model", "view", "controller"},
        "modular": {"module", "modules", "feature", "features"},
        "event": {"events", "event", "listeners", "subscribers"},
        "plugin": {"plugin", "plugins", "extensions", "addons"},
    }

    def calc_solid_score(self):
        """SOLID 原则：S/O/L/I/D 五原则启发式检测（置信度：中）"""
        if not self.index.files:
            return 0, {"s": 0, "o": 0, "l": 100, "i": 100, "d": 0,
                       "confidence": "中", "n_files": 0}
        # 统计面向对象语言文件（cpp/hpp/py/java）
        oo_files = [f for f in self.index.files
                    if f["lang"] in ("cpp", "python", "java") or f["ext"] in (".hpp", ".h")]
        if not oo_files:
            return None, {"confidence": "中", "reason": "无面向对象代码"}

        s_violations = 0      # 职责过多（大文件+多函数启发式）
        o_uses_interface = 0  # 使用接口/抽象（O 正面）
        o_modifies_new = 0    # new 具体类（O 反面）
        l_override_no_super = 0  # override 不调 super（L 违反）
        i_interface_methods = [] # 接口方法数（I）
        d_constructor_di = 0   # 构造注入（D 正面）
        d_new_concrete = 0     # new 具体类（D 反面，Factory 例外）

        for f in oo_files:
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            lines = content.splitlines()
            if len(lines) > 400:
                s_violations += 1  # 超大文件疑似多职责
            if re.search(r"interface\s+\w+|abstract\s+class|ABC\b|Protocol\b", content):
                o_uses_interface += 1
            if re.search(r"\bnew\s+\w+\s*\(|\bnew\s+[A-Z]\w+", content):
                o_modifies_new += 1
            if re.search(r"def\s+\w+\([^)]*super\([^)]*\)\)|super\(\)\.\w+", content):
                l_override_no_super += 1
            if re.search(r"class\s+\w+(?:implements|extends)\s+\w+", content):
                for m in re.finditer(r"def\s+(\w+)\s*\(", content):
                    pass
            # D: 构造注入（__init__ 或 constructor 有参数）
            if re.search(r"__init__\s*\(\s*self,\s*\w+", content) \
                    or re.search(r"constructor\s*\([^)]*\w+", content):
                d_constructor_di += 1
            if re.search(r"\bnew\s+[A-Z]\w+\s*\(", content):
                # Factory 例外：方法名含 create/make/build/factory
                if not re.search(r"def\s+(?:create|make|build|factory)\w*", content):
                    d_new_concrete += 1

        n = len(oo_files)
        # S: 职责（100 - (职责数-1)*25），以超大文件比例代理
        s_ratio = s_violations / n
        s = max(0, 100 - s_ratio * 200)
        # O: 100 + 接口使用加分 - new 扣分
        o = min(100, 60 + (o_uses_interface / n) * 40 - (o_modifies_new / n) * 40)
        o = max(0, o)
        # L: 100 - override 不调 super 比例*33
        l = max(0, 100 - (l_override_no_super / n) * 33)
        # I: 100（无精确接口方法数时给默认，接口膨胀在反模式/规则层检测）
        i = 100
        # D: constructor_di 加分 - new_concrete 扣分
        d = max(0, min(100, (d_constructor_di / n) * 50 - (d_new_concrete / n) * 50 + 50))
        if n == 0:
            s = o = l = i = d = 0

        score = (s + o + l + i + d) / 5
        return round(score, 2), {
            "s": round(s, 2), "o": round(o, 2), "l": round(l, 2),
            "i": round(i, 2), "d": round(d, 2),
            "confidence": "中", "oo_files": n,
            "s_violations": s_violations, "d_new_concrete": d_new_concrete,
        }

    def calc_pattern_score(self):
        """设计模式：12 种模式多样性 + 正确性（置信度：低）"""
        if not self.index.files:
            return 0, {"patterns": [], "confidence": "低"}
        found = []
        for name, pat in self._DESIGN_PATTERNS:
            for f in self.index.files:
                try:
                    content = read_text_smart(f["abs_path"])
                except Exception:
                    continue
                if re.search(pat, content):
                    found.append(name)
                    break
        pattern_count = min(8, len(found))
        diversity = pattern_count * 10
        # 正确性：以"模式出现的文件数/总文件数"代理（简单实现）
        correctness = min(20, pattern_count * 2)
        score = diversity + correctness
        return min(100, score), {"patterns": found, "pattern_count": pattern_count,
                                 "confidence": "低"}

    def calc_style_score(self):
        """架构风格：6 种风格目录模式 + 依赖方向（置信度：中）"""
        if not self.index.files:
            return 0, {"style": None, "confidence": "中"}
        # 统计各风格目录关键词出现频率
        style_hits = {}
        for f in self.index.files:
            path_l = f["path"].lower().replace("\\", "/")
            parts = set(path_l.split("/"))
            for style, dirs in self._STYLE_DIRS.items():
                if parts & dirs:
                    style_hits[style] = style_hits.get(style, 0) + 1
        if not style_hits:
            return 50, {"style": None, "confidence": "中", "note": "未识别显著架构风格"}
        dominant = max(style_hits, key=style_hits.get)
        hits = style_hits[dominant]
        # 基准 60 分（识别出主导风格），每命中 1% 文件 +0.4，封顶 100
        score = min(100, 60 + hits / max(1, len(self.index.files)) * 40)
        # 依赖方向违反（分层架构：repository→controller 反向）启发式扣分
        deduction = 0
        if dominant == "layered":
            for f in self.index.files:
                path_l = f["path"].lower().replace("\\", "/")
                if "repository" in path_l:
                    try:
                        content = read_text_smart(f["abs_path"])
                    except Exception:
                        continue
                    if re.search(r"controller|service", content, re.IGNORECASE):
                        deduction += 5
        return max(0, score - deduction), {"style": dominant,
                                           "style_hits": style_hits,
                                           "confidence": "中"}

    def calc_anti_pattern_score(self):
        """反模式：God Class/Long Method/硬编码/霰弹修改（从 100 扣，上限 30）"""
        deduction = 0
        detail = {"god_class": 0, "long_method": 0, "hardcode": 0, "shotgun": 0}
        for f in self.index.files:
            if self._is_test_file(f):
                continue  # 测试文件多函数为正常设计，不计反模式
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            lines = content.splitlines()
            # God Class: 针对类的检测（类块内 >300 行且方法 >10，支持 C++/Java/Python）
            god_found = False
            # 匹配 class 定义（花括号 C++/Java 或冒号 Python）
            class_pat = re.compile(
                r"(?m)^\s*(?:public\s+|private\s+|protected\s+|final\s+|abstract\s+)?class\s+\w+[^:{]*[\:{]"
            )
            cls_matches = list(class_pat.finditer(content))
            for ci, cm in enumerate(cls_matches):
                cls_start = cm.start()
                # 类块结束：下一个顶层 class 或文件尾
                cls_end = cls_matches[ci + 1].start() if ci + 1 < len(cls_matches) else len(content)
                cls_body = content[cls_start:cls_end]
                cls_lines = cls_body.splitlines()
                if len(cls_lines) > 300:
                    cls_methods = len(re.findall(
                        r"(?m)^\s*(?:public|private|protected|static|def|void|int|str|bool|double|float|auto|\w+\s+\w+\s*\()",
                        cls_body,
                    ))
                    if cls_methods > 10:
                        god_found = True
                        break
            if god_found:
                deduction += 10
                detail["god_class"] += 1
            # Long Method: 单个函数体 >100 行（启发式：连续缩进块 >100 行）
            if self._has_long_method(lines):
                deduction += 5
                detail["long_method"] += 1
            # 硬编码：疑似应配置化的魔法值（IP/密钥）
            if re.search(r"\b(?:1\.2\.3\.4|8\.8\.8\.8|password\s*=\s*[\"x]\w+|api[_-]?key\s*=\s*[\"x]\w+)", content, re.IGNORECASE):
                deduction += 5
                detail["hardcode"] += 1
        # 霰弹修改：启发式（多文件引用同一常量模块）
        detail["shotgun"] = 0
        deduction = min(30, deduction)
        score = max(0, 100 - deduction)
        return score, detail

    def _has_long_method(self, lines) -> bool:
        """启发式：文件中存在 >100 行的连续缩进块（疑似长函数）"""
        run = 0
        prev_indent = None
        for line in lines:
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if prev_indent is None:
                run = 1
            elif indent == prev_indent:
                run += 1
                if run > 100:  # 提前返回，避免全量遍历
                    return True
            else:
                run = 1
            prev_indent = indent
        return False

    def calc_design_score(self):
        """设计质量综合分（4 子维度加权合成）"""
        solid, solid_d = self.calc_solid_score()
        patterns, patterns_d = self.calc_pattern_score()
        style, style_d = self.calc_style_score()
        anti, anti_d = self.calc_anti_pattern_score()

        w = self.weights["design"]
        details = {
            "solid": solid, "patterns": patterns, "style": style,
            "anti_patterns": anti,
        }
        # 处理 None（无面向对象代码 → SOLID None）
        scored = []
        for name, s in [("solid", solid), ("patterns", patterns),
                        ("style", style), ("anti_patterns", anti)]:
            if s is not None:
                scored.append((name, s))
        if not scored:
            return None, {"scores": {}, "all_na": True}

        total_w = sum({"solid": w.get("SOLID原则", 0.40),
                       "patterns": w.get("设计模式", 0.15),
                       "style": w.get("架构风格", 0.20),
                       "anti_patterns": w.get("反模式", 0.25)}[n] for n, _ in scored)
        score = sum(s * {"solid": w.get("SOLID原则", 0.40),
                         "patterns": w.get("设计模式", 0.15),
                         "style": w.get("架构风格", 0.20),
                         "anti_patterns": w.get("反模式", 0.25)}[n]
                    for n, s in scored) / total_w

        detail = {
            **details,
            "detail_solid": solid_d,
            "detail_patterns": patterns_d,
            "detail_style": style_d,
            "detail_anti_patterns": anti_d,
        }
        return round(score, 2), detail

    # ── 文档质量辅助 ──
    _README_KEYWORDS = [
        ("简介", 15),
        ("安装", 15),
        ("使用", 15),
        ("功能", 15),
        ("配置", 10),
        ("贡献", 10),
    ]
    _CHANGELOG_CATEGORIES = ["Added", "Changed", "Deprecated", "Removed",
                             "Fixed", "Security"]

    def _read_root_file(self, name):
        """读取项目根目录下的文档文件（UTF-8 智能解码）"""
        p = os.path.join(self.root, name)
        if not os.path.exists(p):
            return None
        try:
            return read_text_smart(p)
        except Exception:
            return ""

    def calc_readme_score(self):
        """README 完整性：7 项章节关键词匹配"""
        content = self._read_root_file("README.md")
        if content is None:
            return 0, {"exists": False, "sections": []}
        found = []
        for kw, _pts in self._README_KEYWORDS:
            # 匹配 "#+ 安装" 等任意级章节标题（忽略大小写）
            if re.search(rf"(?mi)^\s*#+\s+{re.escape(kw)}", content):
                found.append(kw)
        score = 20 + sum(pts for kw, pts in self._README_KEYWORDS if kw in found)
        return min(100, score), {"exists": True, "sections": found}

    def calc_changelog_score(self):
        """CHANGELOG 完整性：存在+版本号+日期+变更分类"""
        content = self._read_root_file("CHANGELOG.md")
        if content is None:
            return 0, {"exists": False}
        score = 30
        detail = {"exists": True, "has_version": False, "has_date": False,
                  "categories": []}
        # 版本号: ## [1.0.0] 或 ## 1.0.0
        if re.search(r"(?mi)^\s*#+\s*\[?\d+\.\d+", content):
            score += 20
            detail["has_version"] = True
        # 日期: 2026-08-21 或 2026/08/21 或 08-21-2026
        if re.search(r"(?m)\d{4}[-/]\d{1,2}[-/]\d{1,2}", content):
            score += 20
            detail["has_date"] = True
        # 变更分类: Added/Changed/Fixed 等
        cats = [c for c in self._CHANGELOG_CATEGORIES
                if re.search(rf"(?m)\b{re.escape(c)}\b", content)]
        if cats:
            score += 30
            detail["categories"] = cats
        return min(100, score), detail

    def calc_adr_score(self):
        """ADR 覆盖率：模板存在性 + docs/adr 目录计数"""
        has_template = False
        tpl_path = os.path.join(self.root, ".opencode", "templates")
        for tpl_dir in [tpl_path, os.path.join(self.root, ".opencode")]:
            if os.path.isdir(tpl_dir):
                for fn in os.listdir(tpl_dir):
                    if "adr" in fn.lower():
                        has_template = True
                        break
            if has_template:
                break
        detail = {"has_template": has_template, "adr_count": 0}
        for adr_dir in ["docs/adr", "adr", "docs/architecture/adr"]:
            d = os.path.join(self.root, adr_dir.replace("/", os.sep))
            if os.path.isdir(d):
                count = sum(1 for fn in os.listdir(d)
                            if fn.lower().endswith(".md"))
                detail["adr_count"] += count
        # 指南 5.3: 无模板且无 ADR 记录 → 0 分；无模板但有记录 → 覆盖分
        if detail["adr_count"] == 0:
            score = 40 if has_template else 0
        else:
            expected = min(5, max(1, self.index.total_files() // 200))
            coverage = min(1.0, detail["adr_count"] / expected) if expected else 0
            score = 40 + (100 - 40) * coverage
        return min(100, round(score, 2)), detail

    def calc_comment_density(self):
        """代码注释密度：注释行数 / 代码总行数"""
        total_lines = 0
        comment_lines = 0
        # 只统计代码文件（源码），跳过测试与文档
        for f in self.index.files:
            if self._is_test_file(f):
                continue
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            lines = content.splitlines()
            total_lines += len(lines)
            comment_lines += sum(1 for ln in lines if self._is_comment_line(ln))
        if total_lines == 0:
            return 0, {"ratio": 0, "comment_lines": 0, "total_lines": 0}
        ratio = comment_lines / total_lines
        if ratio < 0.05:      score = 20
        elif ratio < 0.10:    score = 40
        elif ratio < 0.15:    score = 60
        elif ratio <= 0.25:   score = 100
        elif ratio < 0.40:    score = 80
        else:                 score = 40
        return score, {"ratio": round(ratio, 4), "comment_lines": comment_lines,
                       "total_lines": total_lines}

    def _is_comment_line(self, line: str) -> bool:
        """判断单行是否为注释行（// 或 # 开头；/* 或 * 开头的块注释）"""
        s = line.strip()
        if not s:
            return False
        if s.startswith("//") or s.startswith("#") or s.startswith("/*") \
                or s.startswith("*") or s.startswith("--"):
            return True
        if s.startswith("(*") or s.startswith("%"):  # Pascal / Fortran/LaTeX
            return True
        return False

    def calc_jsdoc_score(self):
        """JSDoc 覆盖率：公共 API 的文档注释覆盖"""
        public_api = 0
        documented = 0
        # 统计 TypeScript/JavaScript 导出声明上方是否有 /** 注释
        for f in self.index.files:
            if f["ext"] not in (".ts", ".tsx", ".js", ".mjs"):
                continue
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            lines = content.splitlines()
            for i, ln in enumerate(lines):
                if re.search(r"(?m)^\s*export\s+(?:function|const|class|interface|type|default)\b", ln):
                    public_api += 1
                    # 向上看是否有 /** 块
                    has_doc = False
                    for j in range(i - 1, max(-1, i - 5), -1):
                        if "*/" in lines[j] or "/**" in lines[j]:
                            has_doc = True
                            break
                        if lines[j].strip() and not lines[j].strip().startswith("*"):
                            break
                    if has_doc:
                        documented += 1
        if public_api == 0:
            return 100, {"public_api": 0, "documented": 0, "ratio": 1.0,
                         "no_public_api": True}
        ratio = documented / public_api
        if ratio >= 0.80:   score = 100
        elif ratio >= 0.60: score = 70
        elif ratio >= 0.40: score = 40
        elif ratio >= 0.20: score = 20
        else:               score = 0
        return score, {"public_api": public_api, "documented": documented,
                       "ratio": round(ratio, 4)}

    def calc_arch_doc_score(self):
        """架构文档完整性：docs/ 下 Markdown 的 6 项章节检测"""
        arch_md = []
        for sub in ["docs", "architecture", ".opencode"]:
            d = os.path.join(self.root, sub)
            if os.path.isdir(d):
                for dirpath, dirnames, files in os.walk(d):
                    if any(x in dirpath for x in ("node_modules", ".git")):
                        continue
                    for fn in files:
                        if fn.lower().endswith((".md", ".markdown")):
                            arch_md.append(os.path.join(dirpath, fn))
        if not arch_md:
            return 0, {"exists": False, "sections": []}
        joined = "\n".join(self._safe_read_md(p) for p in arch_md)
        sections = []
        checks = [
            ("目录结构", r"(?im)^\s*#+\s*(目录结构|项目结构|directory structure|tree)", 15),
            ("模块职责", r"(?im)^\s*#+\s*(模块职责|模块说明|module)", 15),
            ("数据流", r"(?im)^\s*#+\s*(数据流|data flow|流程)", 15),
            ("依赖关系", r"(?im)^\s*#+\s*(依赖关系|dependencies)", 15),
            ("设计决策", r"(?im)^\s*#+\s*(设计决策|architecture decision|ADR|设计说明)", 20),
        ]
        score = 20  # 架构文档存在
        for name, pat, pts in checks:
            if re.search(pat, joined):
                sections.append(name)
                score += pts
        return min(100, score), {"exists": True, "sections": sections}

    def _safe_read_md(self, path):
        try:
            return read_text_smart(path)
        except Exception:
            return ""

    def calc_doc_score(self):
        """文档质量综合分（6 子维度加权合成）"""
        readme, readme_d = self.calc_readme_score()
        changelog, changelog_d = self.calc_changelog_score()
        adr, adr_d = self.calc_adr_score()
        comments, comments_d = self.calc_comment_density()
        jsdoc, jsdoc_d = self.calc_jsdoc_score()
        arch_doc, arch_doc_d = self.calc_arch_doc_score()

        w = self.weights["doc"]
        details = {
            "readme": readme, "changelog": changelog, "adr": adr,
            "comments": comments, "jsdoc": jsdoc, "arch_doc": arch_doc,
        }
        score = (
            readme * w.get("README完整性", 0.25)
            + changelog * w.get("CHANGELOG完整性", 0.15)
            + adr * w.get("ADR覆盖率", 0.20)
            + comments * w.get("代码注释密度", 0.15)
            + jsdoc * w.get("JSDoc覆盖率", 0.15)
            + arch_doc * w.get("架构文档完整性", 0.10)
        )
        detail = {
            **details,
            "detail_readme": readme_d,
            "detail_changelog": changelog_d,
            "detail_adr": adr_d,
            "detail_comments": comments_d,
            "detail_jsdoc": jsdoc_d,
            "detail_arch_doc": arch_doc_d,
        }
        return round(score, 2), detail

    # ── 演进质量辅助 ──
    _DEAD_BACKUP_EXTS = (".bak", ".old", "~", ".orig", ".rej")
    _COMMENTED_CODE_RE = re.compile(
        r"/\*[^*]*\*[^/]*\*/|^\s*//.*(?:\bif\b|\bfor\b|\breturn\b|\bclass\b|\bfunction\b).*$",
        re.MULTILINE,
    )

    def calc_git_activity(self):
        """历史可追溯性：Git 活跃度（提交频率+团队协作+分支健康）"""
        if not self.git.has_git():
            return None, {"has_git": False, "reason": "无 Git 仓库"}
        score = 20  # 有 Git 仓库
        detail = {"has_git": True}
        if self.git.recent_commits(3) > 0:
            score += 20
        else:
            detail["no_commit_3m"] = True
        if self.git.recent_commits(1) > 0:
            score += 20
        else:
            detail["no_commit_1m"] = True
        if self.git.recent_days_commits(7) > 0:  # 近 7 天
            score += 20
        else:
            detail["no_commit_7d"] = True
        contributors = self.git.contributors_count()
        if contributors > 1:
            score += 10
            detail["contributors"] = contributors
        return min(100, score), detail

    def calc_debt_trend(self):
        """技术债务趋势：对比历史债务点数"""
        history = load_history(self.root, mode="local") or load_history(self.root, mode="central")
        if not history:
            return 20, {"has_baseline": False, "reason": "无历史数据"}
        # 取最近一次历史的结构质量分作为债务代理
        last = history[-1]
        prev_score = last.get("structural", 0)
        current = self.calc_structural_score()[0]
        detail = {"has_baseline": True, "prev_structural": prev_score,
                  "cur_structural": current}
        score = 20  # 有基线
        if current > prev_score:
            score += 40
            detail["trend"] = "improving"
        elif current == prev_score:
            score += 10
            detail["trend"] = "stable"
        else:
            score -= 20
            detail["trend"] = "declining"
        return max(0, score), detail

    _LOCK_FILES = ["package-lock.json", "yarn.lock", "pnpm-lock.yaml",
                   "Pipfile.lock", "poetry.lock", "uv.lock"]

    def _parse_pyproject_deps(self, pyproject_path):
        """解析 pyproject.toml 的 [project.dependencies] / [project.optional-dependencies]"""
        deps = []
        content = read_text_smart(pyproject_path)
        import tomllib
        try:
            data = tomllib.loads(content)
        except Exception:
            return deps
        project = data.get("project", {})
        for d in project.get("dependencies", []) or []:
            deps.append(d.split("[")[0].split("=")[0].split("<")[0].split(">")[0]
                        .split("~")[0].split("^")[0].strip())
        opt = project.get("optional-dependencies", {}) or {}
        for group in opt.values():
            for d in group:
                deps.append(d.split("[")[0].split("=")[0].split("<")[0].split(">")[0]
                            .split("~")[0].split("^")[0].strip())
        # 去重保序
        seen = set()
        return [d for d in deps if not (d in seen or seen.add(d))]

    def calc_dep_outdated(self):
        """依赖过时程度：静态解析 package.json / requirements.txt / pyproject.toml"""
        pkg_json = os.path.join(self.root, "package.json")
        req_txt = os.path.join(self.root, "requirements.txt")
        pyproject = os.path.join(self.root, "pyproject.toml")
        if not (os.path.exists(pkg_json) or os.path.exists(req_txt)
                or os.path.exists(pyproject)):
            return None, {"has_manifest": False, "reason": "无依赖清单"}
        deps = []
        manifest_type = None
        if os.path.exists(pkg_json):
            try:
                import json as _json
                data = _json.loads(read_text_smart(pkg_json))
                deps = list((data.get("dependencies") or {}).keys())
                manifest_type = "package.json"
            except Exception:
                pass
        elif os.path.exists(pyproject):
            deps = self._parse_pyproject_deps(pyproject)
            manifest_type = "pyproject.toml"
        elif os.path.exists(req_txt):
            deps = [l.split("==")[0].strip() for l in
                    read_text_smart(req_txt).splitlines()
                    if l.strip() and not l.strip().startswith("#")]
            manifest_type = "requirements.txt"
        total = len(deps)
        if total == 0:
            return 100, {"has_manifest": True, "dep_total": 0,
                         "manifest_type": manifest_type}
        # 无网络/审计工具时，以"存在 lock 文件"作为依赖已固定的代理；
        # 过时判定留待 npm outdated/audit 集成（标记为需外部工具）
        has_lock = any(os.path.exists(os.path.join(self.root, f))
                       for f in self._LOCK_FILES)
        detail = {"has_manifest": True, "dep_total": total,
                  "manifest_type": manifest_type,
                  "has_lock": has_lock, "needs_external_tool": True}
        # 无 lock 文件视为依赖版本未锁定（过时风险），降分
        if not has_lock:
            score = 60
            detail["risk"] = "no_lock_file"
        else:
            score = 80
        return score, detail

    def calc_dead_code(self):
        """废弃代码比例：从 100 起扣（备份文件/注释代码块）"""
        score = 100
        detail = {"backup_files": 0, "commented_blocks": 0}
        # 备份/重复文件
        for f in self.index.files:
            lower = f["path"].lower()
            if any(lower.endswith(ext) for ext in self._DEAD_BACKUP_EXTS):
                detail["backup_files"] += 1
                score -= 10
        # 根目录下散落的备份文件
        if os.path.isdir(self.root):
            for fn in os.listdir(self.root):
                if fn.lower().endswith(self._DEAD_BACKUP_EXTS):
                    detail["backup_files"] += 1
                    score -= 10
        # 被注释的大段代码（启发式）
        for f in self.index.files:
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            blocks = re.findall(r"/\*[^*]*(?:\bif\b|\bfor\b|\bclass\b|\breturn\b)[^*]*\*/", content)
            if blocks:
                detail["commented_blocks"] += len(blocks)
                score -= 5 * min(3, len(blocks))
        score = max(0, score)
        return score, detail

    def calc_incremental_quality(self):
        """增量质量：最近 30 次提交的平均变更行数"""
        if not self.git.has_git():
            return None, {"has_git": False}
        avg = self.git.avg_commit_size(30)
        if avg is None:
            return None, {"has_git": True, "no_commits": True}
        detail = {"avg_commit_size": round(avg, 1)}
        if avg < 50:      score = 100
        elif avg < 100:   score = 80
        elif avg < 300:   score = 60
        elif avg < 500:   score = 30
        else:             score = 0
        return score, detail

    def calc_problem_deduction(self):
        """问题扣分：从 SAR/结构检测派生（单一事实源，见 A4）"""
        # 注意：完整派生逻辑在 check_sar_rules() 中计算后回填。
        # 此处先基于结构子维度做基础扣分（避免与 SAR 双重计分）。
        if "structural" in self._dim_cache:
            struct_detail = self._dim_cache["structural"][1]
        else:
            struct_detail = self.calc_structural_score()[1]
        score = 100
        detail = {"high_issues": 0, "medium_issues": 0}
        if struct_detail.get("coupling", 100) < 60:
            score -= 3
            detail["medium_issues"] += 1
            detail["high_coupling"] = True
        if struct_detail.get("cohesion", 100) < 60:
            score -= 3
            detail["medium_issues"] += 1
            detail["low_cohesion"] = True
        if struct_detail.get("test_coverage", 100) < 50:
            score -= 3
            detail["medium_issues"] += 1
            detail["low_test_coverage"] = True
        # God Object（>1000 行文件）
        self.index.total_lines()  # 填充惰性 lines
        god_files = [f for f in self.index.files if f["lines"] > 1000]
        if god_files:
            score -= 5 * len(god_files)
            detail["high_issues"] += len(god_files)
            detail["god_files"] = [f["path"] for f in god_files[:5]]
        return max(0, score), detail

    def calc_evolution_score(self):
        """演进质量综合分（6 子维度加权合成）"""
        activity, activity_d = self.calc_git_activity()
        debt, debt_d = self.calc_debt_trend()
        dep, dep_d = self.calc_dep_outdated()
        dead, dead_d = self.calc_dead_code()
        incremental, incr_d = self.calc_incremental_quality()
        problems, prob_d = self.calc_problem_deduction()

        w = self.weights["evolution"]
        # 收集非 None 维度与权重，按比例重分配
        scored = []
        for name, score, weight_key, wv in [
            ("git_activity", activity, "历史可追溯性", 0.16),
            ("debt_trend", debt, "技术债务趋势", 0.20),
            ("dep_outdated", dep, "依赖过时程度", 0.16),
            ("dead_code", dead, "废弃代码比例", 0.12),
            ("incremental", incremental, "增量质量", 0.16),
            ("problems", problems, "问题扣分", 0.20),
        ]:
            if score is not None:
                scored.append((name, score, wv))
        if not scored:
            return None, {"scores": {}, "all_na": True}

        total_w = sum(wv for _, _, wv in scored)
        overall = sum(s * wv for _, s, wv in scored) / total_w

        detail = {
            "scores": {
                "git_activity": activity, "debt_trend": debt,
                "dep_outdated": dep, "dead_code": dead,
                "incremental": incremental, "problems": problems,
            },
            "detail_git_activity": activity_d,
            "detail_debt_trend": debt_d,
            "detail_dep_outdated": dep_d,
            "detail_dead_code": dead_d,
            "detail_incremental": incr_d,
            "detail_problems": prob_d,
        }
        return round(overall, 2), detail

    def check_sar_rules(self) -> list:
        """检测 12 条 SAR 规则（对齐指南第七章内置规则）

        单一事实源：SAR 规则是唯一检测层，6.6 问题扣分由此派生（calc_problem_deduction）。
        output_level 与 severity 解耦。
        N/A 守卫：calc_xxx() 返回 None 的维度（无 Git/无依赖清单/无 OO 代码）跳过对应规则。
        """
        violations = []
        # 复用 all_metrics 已算的结构质量结果（避免重复计算）
        if "structural" in self._dim_cache:
            struct_detail = self._dim_cache["structural"][1]
        else:
            struct_detail = self.calc_structural_score()[1]

        def _add(rule, name, severity, output_level, count, detail):
            violations.append({
                "rule": rule, "name": name,
                "severity": severity, "output_level": output_level,
                "count": count, "detail": detail,
            })

        # ── SAR-001 模块化失衡（结构）──
        modularity = struct_detail.get("modularity")
        if modularity is not None:
            if modularity < 30:
                _add("SAR-001", "模块化失衡", "MEDIUM", "WARNING", 1,
                     f"平均每目录文件数偏离理想值 5 过远（模块化得分 {modularity:.1f}）")

        # ── SAR-002 高耦合（结构）──
        coupling = struct_detail.get("coupling")
        if coupling is not None and coupling < 60:
            _add("SAR-002", "高耦合", "MEDIUM", "WARNING", 1,
                 f"耦合度得分 {coupling:.1f} < 60（平均导入数超标）")

        # ── SAR-003 低内聚（结构）──
        cohesion = struct_detail.get("cohesion")
        if cohesion is not None and cohesion < 60:
            _add("SAR-003", "低内聚", "MEDIUM", "WARNING", 1,
                 f"内聚度得分 {cohesion:.1f} < 60（超大文件占比过高）")

        # ── SAR-004 高复杂度（结构）──
        complexity = struct_detail.get("complexity")
        if complexity is not None and complexity < 40:
            _add("SAR-004", "高复杂度", "HIGH", "WARNING", 1,
                 f"复杂度得分 {complexity:.1f}（超过 200 行文件占比高）")

        # ── SAR-005 测试覆盖不足（结构）──
        tc_score = struct_detail.get("test_coverage")
        if tc_score is not None and tc_score < 50:
            _add("SAR-005", "测试覆盖不足", "MEDIUM", "WARNING", 1,
                 f"测试覆盖度得分 {tc_score:.1f} < 50（L1/L2/L3/L4 四层综合）")

        # ── SAR-006/007 God Class / Long Method（设计，复用缓存）──
        if "design" in self._dim_cache:
            _design_detail = self._dim_cache["design"][1]
            anti_d = _design_detail.get("detail_anti_patterns", {})
        else:
            _anti, anti_d = self.calc_anti_pattern_score()
        if anti_d.get("god_class", 0) > 0:
            _add("SAR-006", "God Class / God Object", "HIGH", "WARNING",
                 anti_d["god_class"], f"检测到 {anti_d['god_class']} 个 God Class")
        if anti_d.get("long_method", 0) > 0:
            _add("SAR-007", "Long Method", "MEDIUM", "WARNING",
                 anti_d["long_method"], f"检测到 {anti_d['long_method']} 个过长方法")

        # ── SAR-008 分层依赖方向违反（设计，复用缓存）──
        if "design" in self._dim_cache:
            _design_detail = self._dim_cache["design"][1]
            style = _design_detail.get("style")
            _style_d = _design_detail.get("detail_style", {})
        else:
            style, _style_d = self.calc_style_score()
        if style is not None and _style_d.get("style") == "layered" and style < 60:
            _add("SAR-008", "分层依赖方向违反", "MEDIUM", "WARNING", 1,
                 f"分层架构依赖方向违反（风格得分 {style:.1f}）")

        # ── SAR-009 接口膨胀（设计，复用缓存）──
        if "design" in self._dim_cache:
            _design_detail = self._dim_cache["design"][1]
            solid = _design_detail.get("solid")
            _solid_d = _design_detail.get("detail_solid", {})
        else:
            solid, _solid_d = self.calc_solid_score()
        if solid is not None and _solid_d.get("i", 100) < 80:
            _add("SAR-009", "接口膨胀", "LOW", "INFO", 1,
                 "接口方法数 > 5（接口隔离原则阈值）")

        # ── SAR-010 文档缺失（文档）──
        if "doc" in self._dim_cache:
            doc, doc_d = self._dim_cache["doc"]
        else:
            doc, doc_d = self.calc_doc_score()
        if doc is not None and doc < 50:
            _add("SAR-010", "文档缺失", "HIGH", "WARNING", 1,
                 f"文档质量得分 {doc:.1f} < 50（README/CHANGELOG/ADR 缺失组合）")

        # ── SAR-011 依赖严重过时（演进）──
        dep, dep_d = self.calc_dep_outdated()
        if dep is not None and dep < 40:
            _add("SAR-011", "依赖严重过时", "HIGH", "ERROR", 1,
                 f"依赖过时程度得分 {dep:.1f} < 40（依赖过时程度 ≥ 25%）")

        # ── SAR-012 项目不活跃（演进）──
        activity, activity_d = self.calc_git_activity()
        if activity is not None and activity_d.get("no_commit_3m", False):
            _add("SAR-012", "项目不活跃", "HIGH", "ERROR", 1,
                 "近 3 个月无 Git 提交（SAR 检测阈值较 6.1 略宽以适配 CI）")

        return violations

    def all_metrics(self):
        """计算所有指标，返回结构化结果"""
        struct_score, struct_details = self.calc_structural_score()
        # 立即缓存结构质量（calc_evolution_score→calc_problem_deduction 需复用）
        self._dim_cache["structural"] = (struct_score, struct_details)
        design_score, design_details = self.calc_design_score()
        doc_score, doc_details = self.calc_doc_score()
        evolution_score, evo_details = self.calc_evolution_score()
        # 缓存其余维度结果供 check_sar_rules 复用（避免重复计算，性能关键）
        self._dim_cache["design"] = (design_score, design_details)
        self._dim_cache["doc"] = (doc_score, doc_details)
        self._dim_cache["evolution"] = (evolution_score, evo_details)

        w = self.weights["main"]
        overall = (
            struct_score * w.get("结构质量", 0.30) +
            design_score * w.get("设计质量", 0.25) +
            doc_score * w.get("文档质量", 0.20) +
            evolution_score * w.get("演进质量", 0.25)
        )

        return {
            "overall": round(overall, 2),
            "structural": {
                "score": round(struct_score, 2),
                "details": struct_details,
                "weight": w.get("结构质量", 0.30),
            },
            "design": {
                "score": round(design_score, 2),
                "details": design_details,
                "weight": w.get("设计质量", 0.25),
            },
            "documentation": {
                "score": round(doc_score, 2),
                "details": doc_details,
                "weight": w.get("文档质量", 0.20),
            },
            "evolution": {
                "score": round(evolution_score, 2),
                "details": evo_details,
                "weight": w.get("演进质量", 0.25),
            },
            "files": {
                "total": self.index.total_files(),
                "by_lang": dict(
                    sorted(
                        ((lang, len(self.index.by_lang(lang)))
                         for lang in set(f["lang"] for f in self.index.files)),
                        key=lambda x: -x[1]
                    )
                ),
                "total_lines": self.index.total_lines(),
                "files_detail": [
                    {"path": f["path"], "lines": f["lines"], "lang": f["lang"]}
                    for f in self.index.files
                ],
            },
            "weights_source": SKILL_PATH,
            "sar_violations": self.check_sar_rules(),
        }


def main():
    parser = argparse.ArgumentParser(description="标准架构质量指标")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--scan", action="store_true", help="全面扫描")
    parser.add_argument("--metrics", action="store_true", help="计算指标")

    args = parser.parse_args()

    metrics = StandardMetrics(args.root)
    result = metrics.all_metrics()

    out_dir = ensure_output_dir(args.root)
    report_path = write_report(out_dir, "standard-metrics.json", result)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
