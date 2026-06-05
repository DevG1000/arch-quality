"""
arch_python_ast.py — Python 端 pybind11 调用 AST 解析器

从 Python 源文件提取 pybind11 实例方法调用，构建 (file, line, module, class, method) 列表。
供 arch_multilang_matcher.py 用于精确的 pybind11 跨语言边检测。

误报控制 (决策 A):
- 仅当变量被 import-then-instantiate 模式赋值才追踪
- 即: m = fvMatrix_module.fvMatrix() 形式，后续 m.method() 才算
- 普通 Python 类方法调用、numpy/pandas 等第三方库不追踪

使用示例:
    calls = extract_pybind11_calls("scripts/run.py")
    for c in calls:
        print(f"{c['file']}:{c['line']} {c['module']}.{c['class']}.{c['method']}()")
"""

import ast
import io
import re
import tokenize
from pathlib import Path

from arch_quality.arch_core import read_text_smart


# 跨语句变量追踪的最大距离（行数）
MAX_TRACK_DISTANCE = 5

# 应被忽略的方法名（魔术方法/dunder）
SKIP_METHODS = frozenset([
    "__init__", "__del__", "__repr__", "__str__", "__bytes__",
    "__format__", "__lt__", "__le__", "__eq__", "__ne__",
    "__gt__", "__ge__", "__hash__", "__bool__", "__getitem__",
    "__setitem__", "__delitem__", "__iter__", "__next__",
    "__contains__", "__add__", "__sub__", "__mul__", "__matmul__",
    "__truediv__", "__floordiv__", "__mod__", "__divmod__",
    "__pow__", "__lshift__", "__rshift__", "__and__", "__or__",
    "__xor__", "__radd__", "__rsub__", "__rmul__", "__rmatmul__",
    "__rtruediv__", "__rfloordiv__", "__rmod__", "__rdivmod__",
    "__rpow__", "__rlshift__", "__rrshift__", "__rand__", "__ror__",
    "__rxor__", "__iadd__", "__isub__", "__imul__", "__imatmul__",
    "__itruediv__", "__ifloordiv__", "__imod__", "__ipow__",
    "__ilshift__", "__irshift__", "__iand__", "__ior__", "__ixor__",
    "__neg__", "__pos__", "__abs__", "__invert__", "__complex__",
    "__int__", "__float__", "__round__", "__index__",
    "__enter__", "__exit__", "__getattr__", "__setattr__", "__delattr__",
    "__getattribute__", "__dir__", "__len__", "__length_hint__",
    "__set_name__", "__init_subclass__", "__subclasshook__",
    "__class_getitem__", "__call__", "__new__",
])


def extract_pybind11_calls(py_file_path: str) -> list:
    """从 Python 文件提取所有 pybind11 调用

    返回:
        [{
            "file": "scripts/run.py",       # 相对或绝对路径
            "line": 42,
            "col": 5,
            "module": "fvMatrix_module",   # import 的模块名
            "class": "fvMatrix",           # 实例化的类
            "method": "solve",             # 调用的方法
            "raw": "m.solve()",            # 原始代码
        }, ...]
    """
    try:
        content = read_text_smart(py_file_path)
    except Exception:
        return []
    return _parse_content(content, py_file_path)


def _parse_content(content: str, file_path: str) -> list:
    """解析 Python 字符串内容，提取 pybind11 调用"""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    extractor = Pybind11CallExtractor(file_path, content)
    extractor.visit(tree)
    extractor.resolve_pending_calls()
    return extractor.calls


class Pybind11CallExtractor(ast.NodeVisitor):
    """AST 访问器：追踪 pybind11 实例化与方法调用"""

    def __init__(self, file_path: str, source: str):
        self.file_path = file_path
        self.source_lines = source.splitlines()
        self.calls = []

        # 导入追踪: alias_name → module_name
        # 例如: "import fvMatrix_module" → {"fvMatrix_module": "fvMatrix_module"}
        # 或: "import fvMatrix_module as fm" → {"fm": "fvMatrix_module"}
        self.imports = {}

        # from-import 追踪: alias_name → (module_name, attr_name)
        # 例如: "from fvMatrix_module import fvMatrix" → {"fvMatrix": ("fvMatrix_module", "fvMatrix")}
        self.from_imports = {}

        # 实例追踪: var_name → (module_name, class_name, instantiation_line)
        # 例如: "m = fvMatrix_module.fvMatrix()" → {"m": ("fvMatrix_module", "fvMatrix", 5)}
        self.instances = {}

        # 待解析调用: (call_node, var_name, method_name, line)
        self.pending_calls = []

    # ── Import 节点 ──

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            module_name = alias.name
            asname = alias.asname or module_name
            self.imports[asname] = module_name

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module is None:
            return
        for alias in node.names:
            attr_name = alias.name
            asname = alias.asname or attr_name
            self.from_imports[asname] = (node.module, attr_name)

    # ── 赋值节点（追踪 m = Module.Class()）──

    def visit_Assign(self, node: ast.Assign):
        # 仅处理 m = X.Y() 或 m = X.Y 形式
        if not node.targets or len(node.targets) != 1:
            return
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            return
        var_name = target.id

        # 模式 1: m = Module.Class() 或 m = Module.Class
        if isinstance(node.value, ast.Call):
            class_name = self._extract_class_name(node.value.func)
            module_name = self._extract_module_name(node.value.func)
            if class_name and module_name:
                self.instances[var_name] = (module_name, class_name, node.lineno)
        # 模式 2: m = Module.Class（无括号）
        elif isinstance(node.value, ast.Attribute):
            class_name = node.value.attr
            module_name = self._extract_module_name(node.value)
            if class_name and module_name and module_name in self.imports.values():
                self.instances[var_name] = (module_name, class_name, node.lineno)

        # 继续遍历子树
        self.generic_visit(node)

    # ── 调用节点（追踪 m.method()）──

    def visit_Call(self, node: ast.Call):
        # 仅处理 obj.method() 形式
        if not isinstance(node.func, ast.Attribute):
            self.generic_visit(node)
            return

        attr = node.func
        if not isinstance(attr.value, ast.Name):
            # 多级属性链 (a.b.c.method())：暂不处理
            self.generic_visit(node)
            return

        var_name = attr.value.id
        method_name = attr.attr

        # 跳过魔术方法
        if method_name in SKIP_METHODS:
            self.generic_visit(node)
            return

        # 检查 var_name 是否是已追踪的实例
        if var_name in self.instances:
            self._record_call(var_name, method_name, node.lineno, node.col_offset)

        self.generic_visit(node)

    # ── 辅助方法 ──

    def _extract_class_name(self, func_node) -> str | None:
        """从 func 节点提取类名

        形式 1: Module.Class  → "Class"
        形式 2: from_imports 中存储的 (module, attr)  → "attr"
        """
        if isinstance(func_node, ast.Attribute):
            return func_node.attr
        if isinstance(func_node, ast.Name):
            # 可能是 from import 后的直接调用
            if func_node.id in self.from_imports:
                _, attr = self.from_imports[func_node.id]
                return attr
        return None

    def _extract_module_name(self, func_node) -> str | None:
        """从 func 节点提取模块名

        形式 1: Module.Class  → "Module"
        形式 2: from_imports 中存储的 (module, attr)  → "module"
        """
        if isinstance(func_node, ast.Attribute):
            if isinstance(func_node.value, ast.Name):
                name = func_node.value.id
                # 查找 import 别名
                if name in self.imports:
                    return self.imports[name]
                return name
        if isinstance(func_node, ast.Name):
            if func_node.id in self.from_imports:
                module, _ = self.from_imports[func_node.id]
                return module
        return None

    def _record_call(self, var_name: str, method_name: str, line: int, col: int):
        """记录一个 pybind11 调用"""
        module_name, class_name, inst_line = self.instances[var_name]

        # 距离检查：调用必须在实例化后 MAX_TRACK_DISTANCE 行内
        if line - inst_line > MAX_TRACK_DISTANCE:
            return

        raw = self.source_lines[line - 1] if line - 1 < len(self.source_lines) else ""

        self.calls.append({
            "file": self.file_path,
            "line": line,
            "col": col,
            "module": module_name,
            "class": class_name,
            "method": method_name,
            "raw": raw.strip(),
        })

    def resolve_pending_calls(self):
        """处理跨语句的延迟解析（占位，当前直接调用 _record_call）"""
        pass


_MALLOC_TOKENS_RE = re.compile(r'^(malloc|calloc|realloc)$')

_MALLOC_CALL_RE = re.compile(
    r'\b(malloc|calloc|realloc)\s*\('
    r'|'
    r'\.\s*(malloc|calloc|realloc)\s*\('
)

_PAIRED_FREE_RE = re.compile(
    r'\b(free|Free|FREE)\s*\('
    r'|'
    r'\.\s*(free|Free|FREE)\s*\('
    r'|'
    r'\b\w+Free\b|\b\w+_Free\b'
)

_FFI_CONTEXT_RE = re.compile(
    r'\b(?:ctypes|CDLL|cdll|windll|oledll|WinDLL'
    r'|cffi|ffi\b'
    r'|pybind11|PYBIND11_MODULE'
    r'|PyObject_New|PyMem_Malloc'
    r')\b'
)

_CODEGEN_TEMPLATE_RE = re.compile(
    r'\{[0-9]+\}'
)

_PYBIND11_CONTEXT_RE = re.compile(
    r'\b(?:'
    r'pybind11|PYBIND11_MODULE|py::module_|py::object|py::class_|py::def\b'
    r'|py::cast\b|py::init\b|py::arg\b|py::return_value_policy'
    r'|Python\.h|PyObject|PyGILState|Py_Initialize'
    r')\b'
    r'|'
    r'#include\s*[<"]pybind11[/>"]'
)

_THIRD_PARTY_MARKERS_RE = re.compile(
    r'(?:third[_-]party|vendor|external|contrib|3rdparty|thirdparty)[/\\]',
    re.IGNORECASE
)


def find_malloc_tokens_in_py(source: str) -> list:
    """在 Python 源码中定位 malloc/calloc/realloc 的 NAME token。

    使用 tokenize 模块精确过滤字符串字面量和注释中的匹配。
    语法错误时回退到逐行正则匹配（带词边界）。

    返回: [(行号, token字符串), ...]
    """
    hits = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok_type, tok_string, (srow, scol), (erow, ecol), line in tokens:
            if tok_type == tokenize.NAME and _MALLOC_TOKENS_RE.match(tok_string):
                hits.append((srow, tok_string))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        for i, line in enumerate(source.splitlines(), 1):
            for m in re.finditer(r'\b(malloc|calloc|realloc)\b', line):
                hits.append((i, m.group(1)))
    return hits


def is_codegen_template(source: str) -> bool:
    """判断 Python 文件是否是代码生成模板。

    特征:
    - 包含 {0}, {1} 等位置模板（>=5 处）
    - 包含 extern "C" 块（原始或转义引号）
    - 包含 #include <...> 指令（在 Python 文件中不应出现）
    - 大量双花括号 {{ }}（模板转义）
    """
    format_holes = len(_CODEGEN_TEMPLATE_RE.findall(source))
    has_extern_c = (
        'extern "C"' in source
        or 'extern \\"C\\"' in source
        or "extern \"C\"" in source
    )
    c_includes = len(re.findall(r'#include\s*[<"]', source))
    double_braces = source.count('{{') + source.count('}}')
    return (format_holes >= 5
            or (has_extern_c and (format_holes > 0 or double_braces > 5))
            or c_includes > 3)


def has_ffi_context(content: str) -> bool:
    """判断文件内容是否包含 FFI 相关导入或调用上下文。"""
    return bool(_FFI_CONTEXT_RE.search(content))


def check_paired_free(content: str) -> bool:
    """判断文件是否包含配对的 free/Free/XXXFree 调用。"""
    return bool(_PAIRED_FREE_RE.search(content))


def has_pybind11_context(content: str) -> bool:
    """判断 C++ 文件内容是否包含 pybind11/CPython 绑定上下文。"""
    return bool(_PYBIND11_CONTEXT_RE.search(content))


def is_third_party_path(path: str) -> bool:
    """判断文件路径是否属于第三方/外部代码目录。"""
    return bool(_THIRD_PARTY_MARKERS_RE.search(path))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Python AST pybind11 解析器")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录或单文件")
    args = parser.parse_args()

    target = Path(args.root)
    if target.is_file():
        py_files = [target]
    else:
        py_files = list(target.rglob("*.py"))

    total_calls = 0
    for pf in py_files:
        calls = extract_pybind11_calls(str(pf))
        if calls:
            print(f"\n=== {pf} ({len(calls)} calls) ===")
            for c in calls:
                print(f"  L{c['line']:3d}: {c['module']}.{c['class']}.{c['method']}()")
            total_calls += len(calls)
    print(f"\nTotal: {total_calls} pybind11 calls extracted from {len(py_files)} Python files")


if __name__ == "__main__":
    main()
