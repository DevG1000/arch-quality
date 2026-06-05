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


def read_text_smart(path):
    """智能读取文本：自动尝试 UTF-8 (BOM) / UTF-8 / GBK / GB18030 / Latin-1

    返回解码后的字符串，所有非法字节替换为 \\ufffd。
    """
    p = Path(path)
    with open(p, "rb") as f:
        raw = f.read()
    for enc in _READ_ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


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
                    "build", "dist", ".vscode", ".idea", "platforms"}

    def __init__(self, root: str):
        self.root = Path(root)
        self.files = []
        self._scan()

    def _scan(self):
        for fpath in self.root.rglob("*"):
            if any(part in self.EXCLUDE_DIRS for part in fpath.parts):
                continue
            if not fpath.is_file():
                continue
            ext = fpath.suffix.lower()
            if ext not in self.LANG_MAP:
                continue
            lines = 0
            try:
                with open(fpath, "rb") as f:
                    lines = sum(1 for _ in f)
            except Exception:
                pass
            rel = str(fpath.relative_to(self.root))
            self.files.append({
                "path": rel,
                "abs_path": str(fpath),
                "lang": self.LANG_MAP[ext],
                "ext": ext,
                "lines": lines,
            })
        self.files.sort(key=lambda x: x["path"])

    def by_lang(self, lang: str):
        return [f for f in self.files if f["lang"] == lang]

    def total_files(self):
        return len(self.files)

    def total_lines(self):
        return sum(f["lines"] for f in self.files)


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
                    # 发现循环
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif neighbor not in visited:
                    dfs(neighbor, path + [neighbor])
            stack.pop()

        for node in list(adj.keys()):
            if node not in visited:
                dfs(node, [node])
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
                cwd=self.root, timeout=30
            )
            return result.stdout.strip()
        except Exception:
            return ""

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
    解析格式：| 维度名 | 数字% |
    权重和必须为 100%，否则抛出 ValueError。
    """
    if not os.path.exists(skill_path):
        raise FileNotFoundError(f"Skill file not found: {skill_path}")

    text = read_text_smart(skill_path)

    pattern = r"^\|\s*(.+?)\s*\|\s*(\d+)%\s*\|"
    matches = re.findall(pattern, text, re.MULTILINE)

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
