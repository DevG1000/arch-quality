# -*- coding: utf-8 -*-
"""arch_metrics_fossil_code.py — 化石代码与技术债（维度⑦）评估

实现《化石代码与技术债评估指南》v0.2 的 4 子维、12 条 FOS 规则
（FOS-001~012）静态检测。

版本绑定：
  - 指南版本：0.2
  - Skill 版本：1.0
"""

import os
import re
import sys
import json
import argparse
from collections import Counter
from pathlib import Path

from arch_quality.arch_core import (
    FileIndex, load_weights_from_skill, ensure_output_dir, write_report,
    read_text_smart,
)

SKILL_PATH = str(Path(__file__).parent / "skills" / "fossil-code-debt.md")
GUIDE_VERSION = "0.2"
SKILL_VERSION = "1.0"

CPP_EXTS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx",
            ".txx", ".ixx", ".cppm", ".mpp"}
C_EXTS = {".c", ".h"}
FORTRAN_EXTS = {".f", ".f77", ".for", ".f90", ".f95", ".f03", ".f08"}
SOURCE_EXTS = CPP_EXTS | FORTRAN_EXTS

DIMENSIONS = ["legacy", "dead", "clone", "debt"]
DIM_LABEL = {
    "legacy": "历史遗留 API 与语言方言",
    "dead": "死代码与不可达逻辑",
    "clone": "重复代码与重复实现",
    "debt": "技术债密度与可维护性",
}
DIMENSION_RULES = {
    "legacy": {"FOS-001": 40, "FOS-002": 40, "FOS-003": 20},
    "dead": {"FOS-004": 50, "FOS-005": 30, "FOS-006": 20},
    "clone": {"FOS-007": 50, "FOS-008": 20, "FOS-009": 30},
    "debt": {"FOS-010": 25, "FOS-011": 50, "FOS-012": 25},
}

RULE_META = {
    "FOS-001": {"name": "F77 固定格式/COMMON/IMPLICIT", "dimension": "legacy",
                "severity": "HIGH", "output_level": "WARNING", "score": 40,
                "confidence": "高", "confirmed": True},
    "FOS-002": {"name": "废弃 C++ API", "dimension": "legacy",
                "severity": "MEDIUM", "output_level": "WARNING", "score": 40,
                "confidence": "高", "confirmed": True},
    "FOS-003": {"name": "K&R C/非标准方言", "dimension": "legacy",
                "severity": "MEDIUM", "output_level": "WARNING", "score": 20,
                "confidence": "中", "confirmed": False},
    "FOS-004": {"name": "未引用函数/变量/文件", "dimension": "dead",
                "severity": "MEDIUM", "output_level": "WARNING", "score": 50,
                "confidence": "中低", "confirmed": False},
    "FOS-005": {"name": "不可达分支", "dimension": "dead",
                "severity": "MEDIUM", "output_level": "WARNING", "score": 30,
                "confidence": "中", "confirmed": False},
    "FOS-006": {"name": "成块注释代码", "dimension": "dead",
                "severity": "LOW", "output_level": "INFO", "score": 20,
                "confidence": "中低", "confirmed": False},
    "FOS-007": {"name": "函数/文件级克隆", "dimension": "clone",
                "severity": "MEDIUM", "output_level": "WARNING", "score": 50,
                "confidence": "中低", "confirmed": False},
    "FOS-008": {"name": "跨文件重复常量", "dimension": "clone",
                "severity": "LOW", "output_level": "INFO", "score": 20,
                "confidence": "中低", "confirmed": False},
    "FOS-009": {"name": "同一算法多份实现", "dimension": "clone",
                "severity": "MEDIUM", "output_level": "WARNING", "score": 30,
                "confidence": "中低", "confirmed": False},
    "FOS-010": {"name": "债务标记密度", "dimension": "debt",
                "severity": "LOW", "output_level": "INFO", "score": 25,
                "confidence": "中", "confirmed": False},
    "FOS-011": {"name": "SQALE 修复成本比率", "dimension": "debt",
                "severity": "MEDIUM", "output_level": "WARNING", "score": 50,
                "confidence": "中低", "confirmed": False},
    "FOS-012": {"name": "遗留模块无测试", "dimension": "debt",
                "severity": "MEDIUM", "output_level": "WARNING", "score": 25,
                "confidence": "中低", "confirmed": False},
}

WAIVER_ABUSE_RATIO_LIMIT = 0.30
TODO_DENSITY_LIMIT = 5.0
SQALE_RATIO_LIMIT = 8.0
CLONE_THRESHOLD = 0.80
MIN_CLONE_TOKENS = 40
CLONE_K = 5
MAX_CLONE_PAIRS = 200

EXTRA_EXCLUDE_DIRS = {
    "externals", "external", "extern", "third_party", "thirdparty", "3rdparty",
    "vendor", "deps", "dependencies", "examples", "example", "tests", "test",
    "miniapps", "benchmarks", "benchmark", "tutorials", "tutorial",
    "subprojects", "bundled", "bundle", "contrib",
}

ENTRY_NAMES = {"main", "wmain", "WinMain", "DllMain", "JNI_OnLoad"}


def _rel(root, p):
    try:
        return os.path.relpath(p, root).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _is_excluded_path(abs_path, root):
    try:
        rel = os.path.relpath(abs_path, root)
    except ValueError:
        rel = abs_path
    parts = [x.lower() for x in Path(rel).parts]
    return any(x in FileIndex.EXCLUDE_DIRS or x in EXTRA_EXCLUDE_DIRS for x in parts)


def _strip_literals(content):
    content = re.sub(r'"(?:\\.|[^"\\])*"', '""', content)
    content = re.sub(r"'(?:\\.|[^'\\])*'", "''", content)
    return content


def _strip_comments(content):
    content = re.sub(r"//[^\n]*", "", content)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    return content


def _strip_fortran_comments(content):
    out = []
    for line in content.splitlines():
        if line[:1] in ("C", "c", "*", "!"):
            out.append("")
            continue
        out.append(re.sub(r"!.*$", "", line))
    return "\n".join(out)


def _waiver_re(name):
    return re.compile(r"/\*\s*@" + re.escape(name) + r"\s*:\s*(.*?)\*/", re.S)


def _waiver_invalid_re(name):
    return re.compile(r"/\*\s*@" + re.escape(name) + r"\s*\*/", re.S)


def _brace_end(content, start):
    depth = 0
    in_str = None
    i = start
    while i < len(content):
        ch = content[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch in ('"', "'"):
            in_str = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(content)


FUNC_DEF_RE = re.compile(
    r"(?m)^[ \t]*(?:(?:static|inline|extern|virtual|constexpr|explicit|friend)[ \t]+)*"
    r"(?:[A-Za-z_][\w:<>,\*&]*[ \t]+)+([A-Za-z_]\w*)[ \t]*\([^;{}]*\)"
    r"[ \t]*(?:const[ \t]*)?(?:noexcept[ \t]*)?(?:\r?\n[ \t]*)?\{"
)
CONTROL_NAMES = {"if", "for", "while", "switch", "catch", "return", "sizeof",
                 "new", "delete", "operator", "do", "else"}
FORTRAN_PROC_RE = re.compile(r"(?im)^\s*(?:subroutine|function)\s+([A-Za-z_]\w*)")
DEPRECATED_RE = re.compile(
    r"\b(auto_ptr|strstream|bind1st|bind2nd|random_shuffle|result_of)\b|"
    r"\bthrow\s*\("
)
REGISTER_RE = re.compile(r"\bregister\b")
GNU_RE = re.compile(r"\b(__attribute__|__typeof__|typeof|asm)\b")
KR_RE = re.compile(
    r"(?m)^[A-Za-z_]\w*[\* \t]+[A-Za-z_]\w*[ \t]*\([^;{}]*\)[ \t]*\r?\n"
    r"[ \t]*(?:int|char|float|double|long|short|unsigned|signed|struct[ \t]+\w+)[ \t]+\w+[ \t]*;"
)
IF0_RE = re.compile(r"(?m)^\s*#\s*if\s+0\b")
FALSE_RE = re.compile(r"\bif\s*\(\s*(?:false|0)\s*\)")
BLOCK_COMMENT_RE = re.compile(r"/\*([\s\S]*?)\*/")
CODE_LIKE_RE = re.compile(
    r"(?:#\s*(?:include|define)|\b(?:if|for|while|switch)\s*\(|"
    r"\b(?:return|break|continue)\b[^;\n]*;|^\s*(?:class|struct|void|int|"
    r"double|float|def|function|subroutine|program)\b[^\n]*[({:]|[{};]\s*$)",
    re.MULTILINE,
)


def _code_like_block(body: str) -> bool:
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    code_lines = [ln for ln in lines if CODE_LIKE_RE.search(ln)]
    # 文档/许可证头常含零星代码词；要求代码行占非空行一半以上。
    return len(code_lines) >= max(2, (len(lines) + 1) // 2)
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
CONST_RE = re.compile(
    r"(?m)\b(?:const|constexpr)\s+(?:unsigned\s+)?"
    r"(?:int|long|float|double|char|auto)\s+(\w+)\s*=\s*"
    r"([0-9]+(?:\.[0-9]+)?[fFlLuU]*)\s*;"
)
DEFINE_CONST_RE = re.compile(
    r"(?m)^\s*#\s*define\s+(\w+)\s+([0-9]+(?:\.[0-9]+)?[fFlLuU]*)\s*$"
)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SECRET_NAME_RE = re.compile(r"(?i)(ip|host|port|password|secret|token|key|url)")


class FossilCodeMetrics:
    """化石代码与技术债评估（维度⑦）"""

    def __init__(self, root: str):
        self.root = root
        self.weights = {}
        self._raw = {}
        self._code = {}
        self._rel_by_abs = {}
        self._legacy_ok = {}
        self._deferred = {}
        self._not_dead = {}
        self._invalid_waivers = []
        self._is_fossil = False
        self._clone_pairs = set()
        self._legacy_untested_modules = []
        self._defs_cache = None
        self._init_weights()
        self._scan()
        self._is_fossil = self._detect_fossil()

    def _init_weights(self):
        _keys = set(DIM_LABEL.values())
        try:
            raw = load_weights_from_skill(SKILL_PATH)
            self.weights = {k: v for k, v in raw.items() if k in _keys}
            if len(self.weights) != 4:
                raise ValueError("只解析到 %d 个维度权重" % len(self.weights))
        except Exception:
            self.weights = {
                "历史遗留 API 与语言方言": 0.30,
                "死代码与不可达逻辑": 0.20,
                "重复代码与重复实现": 0.20,
                "技术债密度与可维护性": 0.30,
            }

    def _scan(self):
        count = 0
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(
                d for d in dirnames
                if d.lower() not in FileIndex.EXCLUDE_DIRS
                and d.lower() not in EXTRA_EXCLUDE_DIRS
                and not d.startswith(".")
            )
            for fn in sorted(filenames):
                ext = os.path.splitext(fn.lower())[1]
                if ext not in SOURCE_EXTS:
                    continue
                abs_path = os.path.join(dirpath, fn)
                try:
                    raw = read_text_smart(abs_path)
                except Exception:
                    continue
                rel = _rel(self.root, abs_path)
                self._raw[abs_path] = raw
                self._rel_by_abs[abs_path] = rel
                if ext in FORTRAN_EXTS:
                    self._code[abs_path] = _strip_fortran_comments(raw)
                else:
                    self._code[abs_path] = _strip_comments(raw)
                self._consume_waivers(raw, rel)
                count += 1
                if count >= 20000:
                    return

    def _consume_waivers(self, raw, rel):
        for name, store in (("fossil_legacy_ok", self._legacy_ok),
                            ("fossil_deferred", self._deferred),
                            ("fossil_not_dead", self._not_dead)):
            m = _waiver_re(name).search(raw)
            if m:
                reason = m.group(1).strip()
                if reason:
                    store[rel] = reason
                else:
                    self._invalid_waivers.append(
                        {"file": rel, "annotation": "@" + name,
                         "issue": "缺少 reason，豁免无效"})
            elif _waiver_invalid_re(name).search(raw):
                self._invalid_waivers.append(
                    {"file": rel, "annotation": "@" + name,
                     "issue": "缺少 reason，豁免无效"})

    def _iter_production(self):
        for p, code in self._code.items():
            if not _is_excluded_path(p, self.root):
                yield p, code

    def _iter_cpp(self):
        for p, code in self._iter_production():
            if os.path.splitext(p)[1].lower() in CPP_EXTS:
                yield p, code

    def _iter_c(self):
        for p, code in self._iter_production():
            if os.path.splitext(p)[1].lower() in C_EXTS:
                yield p, code

    def _iter_fortran(self):
        for p, code in self._iter_production():
            if os.path.splitext(p)[1].lower() in FORTRAN_EXTS:
                yield p, code

    def _is_fixed_form(self, p, code):
        ext = os.path.splitext(p)[1].lower()
        if ext in {".f", ".f77", ".for"}:
            return True
        if ext in FORTRAN_EXTS and re.search(r"-ffixed-form\b", code, re.I):
            return True
        for line in code.splitlines()[:80]:
            if line[:1] in ("C", "c", "*"):
                return True
            if len(line) > 6 and line[5] not in (" ", "0") and line[:5].strip() == "":
                return True
        return False

    def _detect_fossil(self):
        legacy = False
        for p, code in self._iter_production():
            ext = os.path.splitext(p)[1].lower()
            if ext in FORTRAN_EXTS and self._is_fixed_form(p, code):
                legacy = True
                break
            if ext in CPP_EXTS:
                c2 = _strip_literals(code)
                if DEPRECATED_RE.search(c2) or REGISTER_RE.search(c2):
                    legacy = True
                    break
            if ext in C_EXTS and (KR_RE.search(code) or GNU_RE.search(code)):
                legacy = True
                break
        if legacy:
            return True
        return self._todo_density() > TODO_DENSITY_LIMIT

    def _todo_density(self):
        total_lines = sum(len(c.splitlines()) for c in self._raw.values())
        count = sum(len(TODO_RE.findall(c)) for c in self._raw.values())
        kloc = max(total_lines / 1000.0, 0.001)
        return count / kloc

    def _rule_001(self):
        out = []
        for p, code in self._iter_fortran():
            if not self._is_fixed_form(p, code):
                continue
            extra = "COMMON/IMPLICIT" if re.search(
                r"(?i)\b(COMMON|IMPLICIT(?!\s+NONE)|EQUIVALENCE)\b", code) else "固定格式"
            out.append({"rule": "FOS-001", "file": self._rel_by_abs[p],
                        "count": 1, "confirmed": True, "candidate": False,
                        "detail": "F77 %s" % extra})
        return out

    def _rule_002(self):
        out = []
        for p, code in self._iter_cpp():
            c2 = _strip_literals(code)
            ms = list(DEPRECATED_RE.finditer(c2))
            if REGISTER_RE.search(c2):
                ms.append(REGISTER_RE.search(c2))
            if ms:
                out.append({"rule": "FOS-002", "file": self._rel_by_abs[p],
                            "count": len(ms), "confirmed": True, "candidate": False,
                            "detail": "废弃 C++ API/关键字"})
        return out

    def _rule_003(self):
        out = []
        for p, code in self._iter_c():
            ms = list(KR_RE.finditer(code)) + list(GNU_RE.finditer(code))
            if ms:
                out.append({"rule": "FOS-003", "file": self._rel_by_abs[p],
                            "count": len(ms), "candidate": True,
                            "detail": "K&R C/GNU 扩展"})
        return out


    def _definitions(self):
        if self._defs_cache is not None:
            return self._defs_cache
        funcs = []
        for p, code in self._iter_production():
            ext = os.path.splitext(p)[1].lower()
            rel = self._rel_by_abs[p]
            if ext in CPP_EXTS:
                for m in FUNC_DEF_RE.finditer(code):
                    name = m.group(1)
                    if name in CONTROL_NAMES:
                        continue
                    end = _brace_end(code, m.end() - 1)
                    body = code[m.end() - 1:end]
                    funcs.append({"name": name, "file": rel, "body": body,
                                  "start": m.start(), "ext": ext,
                                  "is_static": bool(re.search(r'\bstatic\b', m.group(0)))})
            elif ext in FORTRAN_EXTS:
                for m in FORTRAN_PROC_RE.finditer(code):
                    funcs.append({"name": m.group(1), "file": rel,
                                  "body": code[m.start():m.start() + 2000],
                                  "start": m.start(), "ext": ext})
        self._defs_cache = funcs
        return funcs

    def _abs_by_rel(self, rel):
        for p, r in self._rel_by_abs.items():
            if r == rel:
                return p
        return ""

    def _rule_004(self):
        funcs = self._definitions()
        if not funcs:
            return []
        all_code = "\n".join(self._code[p] for p, _ in self._iter_production())
        ident_counts = Counter(re.findall(r"\b[A-Za-z_]\w*\b", all_code))
        not_dead_files = set(self._not_dead)
        out = []
        seen = set()
        for f in funcs:
            name = f["name"]
            if name in ENTRY_NAMES or name.startswith("PyInit_") or name.startswith("operator"):
                continue
            if not f.get("is_static"):
                continue
            if f["file"] in not_dead_files:
                continue
            raw = self._raw.get(self._abs_by_rel(f["file"]), "")
            if re.search(r'extern\s+"C"', raw) or re.search(r"dllexport|visibility", raw):
                continue
            if re.search(r"bind\s*\(\s*C", raw, re.I) or re.search(r"REGISTER_\w+", raw):
                continue
            refs = ident_counts.get(name, 0)
            if refs <= 1:
                key = (f["file"], name)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"rule": "FOS-004", "file": f["file"], "count": 1,
                            "candidate": True,
                            "detail": "函数 %s 无其他引用（候选）" % name})
        return out[:200]

    def _rule_005(self):
        out = []
        for p, code in self._iter_production():
            n = len(IF0_RE.findall(code)) + len(FALSE_RE.findall(code))
            if n:
                out.append({"rule": "FOS-005", "file": self._rel_by_abs[p],
                            "count": n, "candidate": True,
                            "detail": "#if 0/恒假条件"})
        return out

    def _rule_006(self):
        out = []
        for p, code in self._iter_production():
            raw = self._raw.get(p, "")
            hits = 0
            max_lines = 0
            for m in BLOCK_COMMENT_RE.finditer(raw):
                body = m.group(1)
                lines = body.splitlines()
                if _code_like_block(body):
                    hits += 1
                    max_lines = max(max_lines, len(lines))
            if hits:
                out.append({"rule": "FOS-006", "file": self._rel_by_abs[p],
                            "count": hits, "candidate": True,
                            "level_hint": "WARNING" if max_lines > 10 else "INFO",
                            "detail": "成块注释 %d 处，最长 %d 行" % (hits, max_lines)})
        return out

    def _tokenize(self, body):
        code = _strip_literals(_strip_comments(body))
        toks = re.findall(r"[A-Za-z_]\w*|\d+(?:\.\d+)?|==|!=|<=|>=|&&|\|\||\S", code)
        keep = {"if", "else", "for", "while", "return", "break", "continue",
                "switch", "case", "default", "class", "struct", "void", "int",
                "char", "float", "double", "long", "short", "unsigned", "signed",
                "const", "static", "inline", "virtual", "public", "private",
                "protected", "new", "delete", "true", "false", "nullptr",
                "subroutine", "function", "program", "end", "call"}
        norm = []
        for t in toks:
            if re.match(r"^[A-Za-z_]\w*$", t):
                norm.append(t if t in keep else "ID")
            elif re.match(r"^\d", t):
                norm.append("NUM")
            else:
                norm.append(t)
        return norm

    def _rule_007(self):
        funcs = []
        for f in self._definitions()[:3000]:
            toks = self._tokenize(f["body"])
            if len(toks) < MIN_CLONE_TOKENS:
                continue
            fps = {tuple(toks[i:i + CLONE_K])
                   for i in range(0, len(toks) - CLONE_K + 1)}
            if fps:
                funcs.append({"name": f["name"], "file": f["file"],
                              "toks": toks, "fps": fps})
        funcs = funcs[:3000]
        if len(funcs) < 2:
            return []
        index = {}
        for i, f in enumerate(funcs):
            for fp in sorted(f["fps"]):
                index.setdefault(fp, []).append(i)
        pairs = set()
        for fp in sorted(index):
            ids = index[fp]
            if len(ids) < 2:
                continue
            for a in range(len(ids)):
                for b in range(a + 1, len(ids)):
                    i, j = ids[a], ids[b]
                    if i == j:
                        continue
                    key = (min(i, j), max(i, j))
                    if key in pairs:
                        continue
                    inter = len(funcs[i]["fps"] & funcs[j]["fps"])
                    denom = min(len(funcs[i]["fps"]), len(funcs[j]["fps"]))
                    if denom and inter / denom >= CLONE_THRESHOLD:
                        pairs.add(key)
                        if len(pairs) >= MAX_CLONE_PAIRS:
                            break
                if len(pairs) >= MAX_CLONE_PAIRS:
                    break
            if len(pairs) >= MAX_CLONE_PAIRS:
                break
        if not pairs:
            return []
        self._clone_pairs = pairs
        files = sorted({funcs[i]["file"] for pair in pairs for i in pair})
        return [{"rule": "FOS-007", "file": files[0], "count": len(pairs),
                 "candidate": True,
                 "detail": "克隆对 %d 个（相似度≥%.2f）" % (len(pairs), CLONE_THRESHOLD)}]

    def _rule_008(self):
        values = {}
        for p, code in self._iter_production():
            rel = self._rel_by_abs[p]
            for m in list(CONST_RE.finditer(code)) + list(DEFINE_CONST_RE.finditer(code)):
                name, val = m.group(1), m.group(2).lower().rstrip("flu")
                if SECRET_NAME_RE.search(name) or IP_RE.search(val):
                    continue
                if val in {"0", "1", "2", "3", "0.0", "1.0", "2.0", "3.0",
                           "0.5", "10", "100"}:
                    continue
                values.setdefault(val, set()).add(rel)
        hits = {v: fs for v, fs in values.items() if len(fs) >= 2}
        total = sum(len(fs) for fs in hits.values())
        if hits and total >= 3:
            return [{"rule": "FOS-008", "file": sorted(hits)[0], "count": total,
                     "candidate": True,
                     "detail": "跨文件重复常量值 %d 个" % len(hits)}]
        return []

    def _rule_009(self):
        funcs = self._definitions()[:3000]
        common = {"main", "init", "run", "size", "begin", "end", "get", "set",
                  "operator", "data", "clone", "copy", "clear", "reset",
                  "read", "write", "update", "apply", "execute", "solve"}
        by_name = {}
        for i, f in enumerate(funcs):
            if f["name"] in common:
                continue
            by_name.setdefault(f["name"], []).append(i)
        hits = 0
        for name, ids in by_name.items():
            files = {funcs[i]["file"] for i in ids}
            if len(files) < 2:
                continue
            for a in range(len(ids)):
                for b in range(a + 1, len(ids)):
                    i, j = ids[a], ids[b]
                    key = (min(i, j), max(i, j))
                    if key in self._clone_pairs:
                        continue
                    if len(self._tokenize(funcs[i]["body"])) < MIN_CLONE_TOKENS:
                        continue
                    hits += 1
                    if hits >= MAX_CLONE_PAIRS:
                        break
                if hits >= MAX_CLONE_PAIRS:
                    break
            if hits >= MAX_CLONE_PAIRS:
                break
        if hits:
            return [{"rule": "FOS-009", "file": "", "count": hits,
                     "candidate": True,
                     "detail": "同名函数跨文件多实现 %d 对（已上限）" % hits}]
        return []

    def _rule_010(self):
        count = sum(len(TODO_RE.findall(c)) for c in self._raw.values())
        density = self._todo_density()
        if density > TODO_DENSITY_LIMIT:
            return [{"rule": "FOS-010", "file": "", "count": count,
                     "candidate": True,
                     "detail": "TODO/FIXME 密度 %.1f/KLOC > %.1f" %
                               (density, TODO_DENSITY_LIMIT)}]
        return []

    def _rule_011(self, base_raw):
        total_lines = sum(len(c.splitlines()) for c in self._raw.values())
        kloc = max(total_lines / 1000.0, 1.0)
        structural = [v for v in base_raw
                      if v.get("rule") not in {"FOS-010", "FOS-011", "FOS-012"}]
        cost = len(structural) * 2.0
        ratio = cost / kloc
        if ratio > SQALE_RATIO_LIMIT:
            return [{"rule": "FOS-011", "file": "", "count": int(cost),
                     "candidate": True,
                     "detail": "SQALE 代理比率 %.1fh/KLOC > %.1f" %
                               (ratio, SQALE_RATIO_LIMIT)}]
        return []

    def _rule_012(self):
        modules = set()
        test_rels = [r for r in self._rel_by_abs.values()
                     if "test" in r.lower() or "spec" in r.lower()]
        for p, _ in self._iter_production():
            rel = self._rel_by_abs[p]
            parts = rel.lower().split("/")
            if not any(x in {"legacy", "old", "deprecated", "fossil"} for x in parts[:-1]):
                continue
            parent = "/".join(rel.split("/")[:-1])
            has_test = any(r.startswith(parent + "/") for r in test_rels)
            if not has_test:
                modules.add(parent)
        self._legacy_untested_modules = sorted(modules)
        if modules:
            return [{"rule": "FOS-012", "file": sorted(modules)[0], "count": len(modules),
                     "candidate": True,
                     "detail": "遗留模块无测试 %d 个" % len(modules)}]
        return []

    def _aggregate(self, raw):
        out = {}
        for v in raw:
            rule = v["rule"]
            meta = RULE_META.get(rule)
            if not meta:
                continue
            if rule not in out:
                out[rule] = {"rule": rule, "name": meta["name"],
                             "dimension": meta["dimension"],
                             "severity": meta["severity"],
                             "output_level": v.get("level_hint", meta["output_level"]),
                             "count": 0, "candidate": False, "confirmed": False,
                             "files": [], "detail": ""}
            o = out[rule]
            o["count"] += int(v.get("count", 1))
            o["candidate"] = o["candidate"] or bool(v.get("candidate"))
            o["confirmed"] = o["confirmed"] or bool(v.get("confirmed"))
            f = v.get("file")
            if f and f not in o["files"] and len(o["files"]) < 5:
                o["files"].append(f)
            if v.get("detail"):
                o["detail"] = v["detail"]
            if v.get("level_hint") == "WARNING":
                o["output_level"] = "WARNING"
        downgrade = {"ERROR": "WARNING", "WARNING": "INFO", "INFO": "INFO"}
        dropped = []
        for rule, o in out.items():
            fs = set(o["files"])
            if rule in {"FOS-001", "FOS-002", "FOS-003"} and fs and fs <= set(self._legacy_ok):
                dropped.append(rule)
                continue
            if rule == "FOS-004" and fs and fs <= set(self._not_dead):
                dropped.append(rule)
                continue
            if fs and fs <= set(self._deferred):
                o["output_level"] = downgrade.get(o["output_level"], o["output_level"])
        for r in dropped:
            out.pop(r, None)
        return [out[k] for k in sorted(out)]

    def _gate(self, violations):
        rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        confirmed = [v for v in violations if v.get("confirmed")]
        if any(v.get("output_level") == "ERROR" for v in confirmed):
            status = "BLOCK"
        elif confirmed:
            status = "WARN"
        else:
            status = "PASS"
        max_sev = None
        if confirmed:
            max_sev = max(confirmed, key=lambda v: rank.get(v.get("severity"), 0))["severity"]
        return status, max_sev

    def legacy_untested_modules(self):
        """D3：返回 FOS-012 命中的遗留无测试模块（供标准 test_coverage 豁免）。"""
        if not self._is_fossil:
            return []
        if not self._legacy_untested_modules:
            self._rule_012()
        return list(self._legacy_untested_modules)

    def _waiver_audit(self):
        total = max(1, len(self._raw))
        combined = set(self._legacy_ok) | set(self._deferred) | set(self._not_dead)
        ratios = {
            "legacy_ok": round(len(self._legacy_ok) / total, 4),
            "deferred": round(len(self._deferred) / total, 4),
            "not_dead": round(len(self._not_dead) / total, 4),
            "combined": round(len(combined) / total, 4),
        }
        warning = None
        if ratios["combined"] > WAIVER_ABUSE_RATIO_LIMIT:
            warning = ("豁免注解合计占比 %.1f%% 超过上限 %.0f%%，覆盖度可能失真" %
                       (ratios["combined"] * 100, WAIVER_ABUSE_RATIO_LIMIT * 100))
        return {
            "legacy_ok": {"count": len(self._legacy_ok), "ratio": ratios["legacy_ok"],
                          "scope": "FOS-001/002/003 不计数（影响 scoring）",
                          "files": sorted(self._legacy_ok)[:20]},
            "deferred": {"count": len(self._deferred), "ratio": ratios["deferred"],
                         "scope": "降一级（仅 output_level）",
                         "files": sorted(self._deferred)[:20]},
            "not_dead": {"count": len(self._not_dead), "ratio": ratios["not_dead"],
                         "scope": "FOS-004 不计数（影响 scoring）",
                         "files": sorted(self._not_dead)[:20]},
            "invalid_waivers": list(self._invalid_waivers),
            "abuse_limit": WAIVER_ABUSE_RATIO_LIMIT,
            "abuse_warning": warning,
        }

    def _calc_dim(self, dim, triggered):
        penalty = sum(pts for rid, pts in DIMENSION_RULES[dim].items()
                      if rid in triggered)
        return max(0, 100 - penalty), {
            "triggered": sorted(rid for rid in DIMENSION_RULES[dim] if rid in triggered),
            "penalty": penalty,
        }

    def calc_legacy(self):
        return self._calc_dim_cached("legacy")

    def calc_dead(self):
        return self._calc_dim_cached("dead")

    def calc_clone(self):
        return self._calc_dim_cached("clone")

    def calc_debt(self):
        return self._calc_dim_cached("debt")

    def _calc_dim_cached(self, dim):
        if not hasattr(self, "_triggered_cache"):
            self._triggered_cache = {v["rule"] for v in self.check_fossil_rules()}
        return self._calc_dim(dim, self._triggered_cache)

    def check_fossil_rules(self):
        raw = []
        for fn in (self._rule_001, self._rule_002, self._rule_003,
                   self._rule_004, self._rule_005, self._rule_006,
                   self._rule_007, self._rule_008, self._rule_009,
                   self._rule_010):
            raw.extend(fn())
        raw.extend(self._rule_011(raw))
        raw.extend(self._rule_012())
        return self._aggregate(raw)

    def all_metrics(self):
        if not self._is_fossil:
            return {
                "overall": None,
                "is_fossil": False,
                "applicability_set": [],
                "score_scope": "none",
                "dimensions": {d: {"score": None, "applicable": False, "detail": {}}
                               for d in DIMENSIONS},
                "fossil_violations": [],
                "legacy_untested_modules": [],
                "gate_status": "PASS",
                "confirmed_max_severity": None,
                "waiver_audit": {},
                "version_info": {"guide_version": GUIDE_VERSION,
                                 "skill_version": SKILL_VERSION},
            }

        violations = self.check_fossil_rules()
        triggered = {v["rule"] for v in violations}
        dims = {}
        for d in DIMENSIONS:
            score, detail = self._calc_dim(d, triggered)
            dims[d] = {"score": score, "applicable": True, "detail": detail}
        overall = round(sum(dims[d]["score"] * self.weights[DIM_LABEL[d]]
                            for d in DIMENSIONS), 2)
        gate, max_sev = self._gate(violations)
        return {
            "overall": overall,
            "is_fossil": True,
            "applicability_set": list(DIMENSIONS),
            "score_scope": "project",
            "dimensions": dims,
            "fossil_violations": violations,
            "legacy_untested_modules": list(self._legacy_untested_modules),
            "gate_status": gate,
            "confirmed_max_severity": max_sev,
            "waiver_audit": self._waiver_audit(),
            "version_info": {"guide_version": GUIDE_VERSION,
                             "skill_version": SKILL_VERSION},
        }


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="化石代码与技术债评估")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--fossil-only", action="store_true", help="仅检测 FOS 规则")
    args = parser.parse_args()

    metrics = FossilCodeMetrics(args.root)
    result = ({"fossil_violations": metrics.check_fossil_rules()}
              if args.fossil_only else metrics.all_metrics())

    out_dir = ensure_output_dir(args.root)
    write_report(out_dir, "fossil-code-metrics.json", result)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        vi = result.get("version_info", {})
        print("化石代码与技术债评估")
        print("=" * 50)
        print("  Guide version: %s" % vi.get("guide_version", "?"))
        print("  Skill version: %s" % vi.get("skill_version", "?"))
        print("  Is fossil project: %s" % result.get("is_fossil", False))
        if result.get("is_fossil"):
            print("  Overall: %s" % result.get("overall"))
            print("  Gate: %s" % result.get("gate_status"))
            for d, v in result.get("dimensions", {}).items():
                print("  - %s: %s" % (d, v.get("score")))
        else:
            print("  (not a fossil project)")


if __name__ == "__main__":
    main()
