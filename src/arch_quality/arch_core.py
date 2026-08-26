"""
arch_core.py — 架构评估核心引擎

提供统一的文件扫描、依赖图构建、Git历史提取功能。
所有 metrics 模块均依赖此核心模块。
"""

import os
import re
import json
import hashlib
import subprocess
from pathlib import Path
from collections import defaultdict
from datetime import datetime


# 读取源文件时尝试的编码顺序（中文 Windows 上 PowerShell 经常保存为 GBK）
_READ_ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "gb18030", "latin-1")

# 进程内内容缓存：{abs_path: (mtime, content)}，避免多引擎/多规则重复读盘
_CONTENT_CACHE = {}


def read_text_smart(path, use_cache=True):
    """智能读取文本：自动尝试 UTF-8 (BOM) / UTF-8 / GBK / GB18030 / Latin-1

    返回解码后的字符串，所有非法字节替换为 \\ufffd。
    use_cache=True 时启用进程内内容缓存（按 mtime 失效），显著降低重复读盘。
    """
    p = Path(path)
    if use_cache:
        key = str(p)
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = -1
        cached = _CONTENT_CACHE.get(key)
        if cached and cached[0] == mtime:
            return cached[1]
    with open(p, "rb") as f:
        raw = f.read()
    for enc in _READ_ENCODINGS:
        try:
            content = raw.decode(enc)
            if use_cache:
                _CONTENT_CACHE[key] = (mtime, content)
            return content
        except UnicodeDecodeError:
            continue
    content = raw.decode("utf-8", errors="replace")
    if use_cache:
        _CONTENT_CACHE[key] = (mtime, content)
    return content


def write_text_utf8(path, content):
    """写入 UTF-8 文本（带 BOM，Windows / PowerShell 友好）

    适用于 .md / .json / .txt 报告，确保 PowerShell 5.1 控制台显示中文不乱码。
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        content = content.encode("utf-8-sig", errors="replace")
    with open(p, "wb") as f:
        f.write(content)


class FileIndex:
    """文件索引：路径、语言、行数、扩展名"""

    LANG_MAP = {
        ".py": "python",
        ".pyw": "python",
        ".cpp": "cpp",
        ".cxx": "cpp",
        ".cc": "cpp",
        ".hpp": "cpp",
        ".hxx": "cpp",
        ".txx": "cpp",
        ".c": "c",
        ".h": "c",
        ".ixx": "cpp",
        ".cppm": "cpp",
        ".mpp": "cpp",
        ".f90": "fortran",
        ".f": "fortran",
        ".f03": "fortran",
        ".f08": "fortran",
        ".for": "fortran",
        ".tcl": "tcl",
        ".lua": "lua",
        ".js": "javascript",
        ".mjs": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".rs": "rust",
        ".go": "go",
        ".i": "swig",
        ".swg": "swig",
    }

    EXCLUDE_DIRS = {"node_modules", ".opencode", ".git", "__pycache__",
                    "build", "dist", ".vscode", ".idea", "platforms",
                    "third_party", "thirdparty", "vendor", "extern",
                    "external", "deps", "dependencies"}

    # 生成文件（flex/bison/moc/autogen 等），扫描时跳过
    GENERATED_FILE_PATTERNS = (
        ("lex.", ".yy.c"),       # flex 输出 lex.yy.c
        ("y.tab.", ".y.tab.c"),  # bison 输出 y.tab.c
        ("moc_", ".moc"),        # Qt moc 生成
        ("qrc_", ".qrc"),
        ("ui_", ".ui.h"),
        (".g.cs", ".g.cs"),      # gRPC/生成 C#
        (".generated.", ".generated."),
        ("_generated", "_generated"),
    )

    BINDING_EXTENSIONS = {".i", ".swg", "_wrap.cxx", "_wrap.cpp"}

    def __init__(self, root: str, build_dir: str = "", cache_file: str = ""):
        self.root = Path(root)
        self.build_dir = Path(build_dir) if build_dir else None
        self.cache_file = Path(cache_file) if cache_file else None
        self.files = []
        self._cached_load()

    def _cached_load(self):
        """增量扫描：若 cache_file 存在且目录 mtime 未变则加载缓存，否则全量扫描

        适用于"跑两遍"场景（首次全量 + 后续增量），避免重复遍历大目录。
        缓存仅存文件清单（不含 lines，行数需真实时重新计算）。
        """
        if self.cache_file and self.cache_file.exists():
            try:
                import json as _json
                data = _json.loads(self.cache_file.read_text(encoding="utf-8"))
                if data.get("root") == str(self.root):
                    self.files = data.get("files", [])
                    return
            except Exception:
                pass
        self._scan()
        if self.cache_file:
            try:
                import json as _json
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                self.cache_file.write_text(
                    _json.dumps({"root": str(self.root), "files": self.files},
                                ensure_ascii=False),
                    encoding="utf-8")
            except Exception:
                pass

    def _is_generated_file(self, fn: str) -> bool:
        """判断文件是否为生成文件（flex/bison/moc 等）"""
        fn_l = fn.lower()
        for pat in self.GENERATED_FILE_PATTERNS:
            if pat[0] in fn_l:
                return True
        return False

    def _scan(self):
        lc = self.LANG_MAP
        ex = self.EXCLUDE_DIRS
        root_str = str(self.root)
        for dirpath, dirnames, filenames in os.walk(root_str):
            dirnames[:] = [d for d in dirnames if d not in ex]
            for fn in filenames:
                if self._is_generated_file(fn):
                    continue
                ext = os.path.splitext(fn)[1].lower()
                if ext not in lc:
                    if ext == "" and self._is_cpp_header_no_ext(Path(os.path.join(dirpath, fn))):
                        ext = ".h"
                    else:
                        continue
                fpath = os.path.join(dirpath, fn)
                rel = os.path.relpath(fpath, root_str)
                lang = lc.get(ext, "cpp")
                self.files.append({
                    "path": rel,
                    "abs_path": fpath,
                    "lang": lang,
                    "ext": ext,
                    "lines": 0,
                })
        if self.build_dir and self.build_dir.exists():
            self._scan_build_dir()
        self.files.sort(key=lambda x: x["path"])

    def _is_cpp_header_no_ext(self, fpath: Path) -> bool:
        parent = fpath.parent.name
        name = fpath.name
        if parent in ("Eigen", "unsupported", "boost"):
            return True
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(1024)
        except Exception:
            return False
        cpp_markers = ("#ifndef", "#define", "#include", "template", "namespace", "class ", "struct ", "//")
        return any(m in head for m in cpp_markers) and "#include" in head

    def _scan_build_dir(self):
        scanned = {f["abs_path"] for f in self.files}
        build_ext_map = {
            ".i": "swig",
            ".swg": "swig",
            ".cxx": "cpp",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".py": "python",
            ".pyi": "python",
        }
        for fpath in self.build_dir.rglob("*"):
            if not fpath.is_file():
                continue
            if any(part in self.EXCLUDE_DIRS for part in fpath.parts):
                continue
            ext = fpath.suffix.lower()
            if ext not in build_ext_map:
                continue
            if str(fpath) in scanned:
                continue
            filename = fpath.name.lower()
            is_wrap = filename.endswith("_wrap.cxx") or filename.endswith("_wrap.cpp")
            is_pyi = filename.endswith(".pyi") and ext == ".pyi"
            is_swig = ext in (".i", ".swg")
            if not (is_wrap or is_pyi or is_swig or ext in (".h", ".hpp")):
                continue
            lang = build_ext_map[ext]
            if is_wrap:
                lang = "cpp"
            lines = 0
            try:
                with open(fpath, "rb") as f:
                    lines = sum(1 for _ in f)
            except Exception:
                pass
            try:
                rel = str(fpath.relative_to(self.root))
            except ValueError:
                rel = str(fpath)
            entry = {
                "path": rel,
                "abs_path": str(fpath),
                "lang": lang,
                "ext": ext,
                "lines": lines,
                "from_build_dir": True,
            }
            if is_wrap:
                entry["is_swig_wrap"] = True
            if is_pyi:
                entry["is_pyi_stub"] = True
            if is_swig:
                entry["is_build_swig"] = True
            self.files.append(entry)
            scanned.add(str(fpath))

    def by_lang(self, lang: str):
        return [f for f in self.files if f["lang"] == lang]

    def total_files(self):
        return len(self.files)

    def total_lines(self, recalc: bool = False) -> int:
        total = 0
        for f in self.files:
            if f["lines"] == 0 or recalc:
                try:
                    with open(f["abs_path"], "rb") as fp:
                        f["lines"] = sum(1 for _ in fp)
                except Exception:
                    f["lines"] = 0
            total += f["lines"]
        return total


class DepGraph:
    """依赖图（含跨语言边）"""

    def __init__(self):
        self.nodes = {}         # {node_id: {"lang": str, "path": str}}
        self.edges = []         # [(src, dst)]
        self.cross_edges = []   # [(src, dst)]  仅跨语言边（两端均为项目节点且语言不同）

    def add_node(self, node_id: str, lang: str, path: str = ""):
        if node_id not in self.nodes:
            self.nodes[node_id] = {"lang": lang, "path": path}

    def add_edge(self, src: str, dst: str):
        self.edges.append((src, dst))
        src_lang = self.nodes.get(src, {}).get("lang")
        dst_lang = self.nodes.get(dst, {}).get("lang")
        if dst_lang is not None and src_lang is not None and src_lang != dst_lang:
            self.cross_edges.append((src, dst))

    @property
    def is_single_language(self):
        """项目是否仅包含单一语言"""
        langs = set(n.get("lang") for n in self.nodes.values() if n.get("lang"))
        return len(langs) <= 1

    @property
    def languages(self):
        """项目包含的语言集合"""
        return set(n.get("lang") for n in self.nodes.values() if n.get("lang"))

    def successors(self, node: str):
        return [d for s, d in self.edges if s == node]

    def predecessors(self, node: str):
        return [s for s, d in self.edges if d == node]

    def cross_successors(self, node: str):
        return [d for s, d in self.cross_edges if s == node]

    def cross_predecessors(self, node: str):
        return [s for s, d in self.cross_edges if d == node]

    def bfs_reachable(self, start: str, max_depth: int = 5, cross_only: bool = False):
        """BFS遍历可达节点，最多 max_depth 层"""
        edge_pool = self.cross_edges if cross_only else self.edges
        visited = {start}
        queue = [(start, 0)]
        while queue:
            node, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for s, d in edge_pool:
                if s == node and d not in visited:
                    visited.add(d)
                    queue.append((d, depth + 1))
        return visited

    def detect_cross_lang_cycles(self):
        """检测跨语言循环依赖，返回循环列表"""
        adj = defaultdict(list)
        for s, d in self.cross_edges:
            adj[s].append(d)

        cycles = []
        visited = set()
        stack = []

        def dfs(node, path):
            visited.add(node)
            stack.append(node)
            path_set = set(path)
            for neighbor in adj.get(node, []):
                if neighbor in path_set:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif neighbor not in visited:
                    dfs(neighbor, path + [neighbor])
            stack.pop()

        for node in list(adj.keys()):
            if node not in visited:
                dfs(node, [node])
        return cycles

    def detect_same_lang_cycles(self, lang=None):
        """检测同语言内模块级循环依赖

        参数:
            lang: 指定语言（如 'fortran'），为None时检测所有语言的内部循环

        返回:
            循环列表，每个循环为 [node_id, ..., node_id] 路径
        """
        lang_nodes = set()
        if lang:
            lang_nodes = {n for n, info in self.nodes.items() if info.get("lang") == lang}
        else:
            lang_nodes = set(self.nodes.keys())

        if not lang_nodes or len(self.edges) < 2:
            return []

        adj = defaultdict(set)
        for s, d in self.edges:
            if s in lang_nodes and d in lang_nodes:
                adj[s].add(d)

        cycles = []
        visited_global = set()

        def _dfs(node, path, path_set):
            visited_global.add(node)
            for neighbor in sorted(adj.get(node, set())):
                if neighbor in path_set:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif neighbor not in visited_global:
                    _dfs(neighbor, path + [neighbor], path_set | {neighbor})

        for node in sorted(lang_nodes):
            if node not in visited_global:
                _dfs(node, [node], {node})

        return cycles


class GitHistory:
    """Git 历史信息提取"""

    def __init__(self, root: str):
        self.root = Path(root)

    def _git(self, *args):
        try:
            result = subprocess.run(
                ["git"] + list(args),
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                cwd=self.root, timeout=30
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def recent_days_commits(self, days: int = 7):
        """最近 days 天内的提交数"""
        since = self._git("log", "--oneline", "--since", f"{days} days ago")
        return len(since.split("\n")) if since else 0

    def has_git(self):
        return bool(self._git("rev-parse", "--is-inside-work-tree"))

    def recent_commits(self, months: int = 3):
        """最近 months 个月内的提交数"""
        since = self._git("log", "--oneline", "--since", f"{months} months ago")
        return len(since.split("\n")) if since else 0

    def commit_count(self):
        """总提交数"""
        out = self._git("rev-list", "--count", "HEAD")
        try:
            return int(out)
        except (ValueError, TypeError):
            return 0

    def contributors_count(self):
        """贡献者人数"""
        out = self._git("shortlog", "-sn")
        return len([l for l in out.split("\n") if l.strip()]) if out else 0

    def avg_commit_size(self, n: int = 30):
        """最近 n 次提交的平均变更行数"""
        out = self._git("log", "--shortstat", f"-{n}")
        total = 0
        count = 0
        for line in out.split("\n"):
            m = re.search(r"(\d+) insertion", line)
            if m:
                total += int(m.group(1))
                count += 1
        return total / count if count > 0 else 0


def _central_base() -> Path:
    """集中模式根目录: %USERPROFILE%/.config/opencode/arch-reports/

    跨平台: Windows 用 USERPROFILE, Unix 用 HOME
    """
    base = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    return Path(base) / ".config" / "opencode" / "arch-reports"


def _project_slug(root: str) -> str:
    """从项目根目录提取稳定短名.

    规则:
    1. 取路径最后一段
    2. 文件系统不安全字符替换为 _
    3. 同名冲突检测: 若同 slug 已存在但 root 不同时, 追加 hash 短码
    """
    p = Path(root).resolve()
    name = p.name
    safe = re.sub(r'[<>:"/\\|?*]', "_", name).strip("_")
    if not safe:
        safe = "unnamed-project"
    base_dir = _central_base() / safe
    if not base_dir.exists():
        return safe
    marker = base_dir / ".project_root"
    if marker.exists():
        try:
            old_root = read_text_smart(marker).strip()
            if Path(old_root).resolve() == p:
                return safe
        except Exception:
            pass
    suffix = hashlib.md5(str(p).encode("utf-8")).hexdigest()[:6]
    return "{0}-{1}".format(safe, suffix)


def _resolve_report_dir(root: str, mode: str = "local", project_name: str = None) -> Path:
    """根据模式返回报告根目录 (不含 YYYY-MM-DD)"""
    if mode == "central":
        slug = project_name or _project_slug(root)
        return _central_base() / slug
    return Path(root) / ".opencode" / "arch-reports"


def _write_project_marker(root: str, mode: str, project_name: str = None):
    """集中模式下写入 .project_root 标记, 用于同名冲突检测"""
    if mode != "central":
        return
    slug = project_name or _project_slug(root)
    marker = _central_base() / slug / ".project_root"
    marker.parent.mkdir(parents=True, exist_ok=True)
    write_text_utf8(marker, str(Path(root).resolve()))


def load_history(root: str, mode: str = "local", project_name: str = None) -> list:
    """加载历史评估快照

    Args:
        root: 项目根目录
        mode: "local" (默认) 写到 <root>/.opencode/, "central" 写到集中目录
        project_name: 可选, 集中模式下的项目短名 (默认从 root 推断)
    """
    base = _resolve_report_dir(root, mode, project_name)
    path = base / "history.json"
    if path.exists():
        return json.loads(read_text_smart(path))
    return []


def save_history(root: str, entry: dict, mode: str = "local", project_name: str = None):
    """追加一条历史评估快照到 history.json"""
    base = _resolve_report_dir(root, mode, project_name)
    path = base / "history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if path.exists():
        history = json.loads(read_text_smart(path))
    history.append(entry)
    write_text_utf8(path, json.dumps(history, ensure_ascii=False, indent=2))
    _write_project_marker(root, mode, project_name)


def load_weights_from_skill(skill_path: str) -> dict:
    """从 skill Markdown 文件中解析权重表格

    Python 命令通过此函数保证权重与 skill 中声明的一致。
    只解析 ``## 权重分配`` 标题到下一个 ``##`` 标题之间的表格行，
    避免误匹配校准阈值等其他含百分号的表格。
    解析格式：| 维度名 | 数字% |
    权重和必须为 100%，否则抛出 ValueError。
    """
    if not os.path.exists(skill_path):
        raise FileNotFoundError(f"Skill file not found: {skill_path}")

    text = read_text_smart(skill_path)

    m = re.search(r"^##\s*权重分配\s*$", text, re.MULTILINE)
    if m:
        start = m.end()
        m2 = re.search(r"^## ", text[start:], re.MULTILINE)
        section = text[start:start + m2.start()] if m2 else text[start:]
    else:
        section = text

    pattern = r"^\|\s*(.+?)\s*\|\s*(\d+)%\s*\|"
    matches = re.findall(pattern, section, re.MULTILINE)

    if not matches:
        raise ValueError(
            f"Cannot parse any weights from {skill_path}. "
            "Expected Markdown table format: | Dimension Name | 15% |"
        )

    weights = {name.strip(): int(pct) / 100 for name, pct in matches}

    return weights


def ensure_output_dir(root: str, mode: str = "local", project_name: str = None) -> str:
    """确保输出目录存在，返回路径

    Args:
        root: 项目根目录
        mode: "local" (默认) 写到 <root>/.opencode/arch-reports/YYYY-MM-DD/
              "central" 写到 ~/.config/opencode/arch-reports/<project-slug>/YYYY-MM-DD/
        project_name: 可选, 集中模式下覆盖自动推断的 project slug
    """
    base = _resolve_report_dir(root, mode, project_name)
    out_dir = base / datetime.now().strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_project_marker(root, mode, project_name)
    return str(out_dir)


def get_report_base(root: str, mode: str = "local", project_name: str = None) -> str:
    """返回报告根目录 (不含 YYYY-MM-DD), 用于诊断/展示"""
    return str(_resolve_report_dir(root, mode, project_name))


def write_report(out_dir: str, name: str, data: dict):
    """写入 JSON 报告（UTF-8 BOM）"""
    path = Path(out_dir) / name
    write_text_utf8(path, json.dumps(data, ensure_ascii=False, indent=2))
    return str(path)


def write_markdown(out_dir: str, name: str, content: str):
    """写入 Markdown 报告（UTF-8 BOM）"""
    path = Path(out_dir) / name
    write_text_utf8(path, content)
    return str(path)
