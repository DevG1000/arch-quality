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
