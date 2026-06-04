"""
arch_bindings_parser.py — C++ 端 PYBIND11_MODULE 绑定解析器

从 C++ 源文件提取 pybind11 绑定信息，构建 module → class → method 映射表。
供 arch_multilang_matcher.py 用于精确的 pybind11 跨语言边检测。

使用示例:
    idx = FileIndex(root)
    bmap = BindingMap(idx)
    bmap.parse()
    cpp_path = bmap.lookup("fvMatrix_module", "fvMatrix", "solve")
    # → "src/fvMatrix.cpp"
"""

import re
from pathlib import Path

from arch_quality.arch_core import FileIndex, read_text_smart


# 匹配 PYBIND11_MODULE(module_name, m_var) {
# 注: 不使用 \{...\} 匹配大括号，因为可能嵌套
PYBIND11_MODULE_RE = re.compile(
    r'PYBIND11_MODULE\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,'
    r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)',
    re.MULTILINE
)

# 匹配 py::class_<ClassName[, Bases...]>(m_var, "PythonName")
# 简化：只捕获 C++ 类名和 Python 暴露名
PYBIND11_CLASS_RE = re.compile(
    r'py::class_<\s*([A-Za-z_]\w*(?:::\w+)*(?:<[^>]*>)?)'
    r'(?:\s*,\s*[A-Za-z_]\w*(?:::\w+)*(?:<[^>]*>)?(?:\s*,\s*\w+(?:::\w+)*)*)*\s*>'
    r'\s*\(\s*[A-Za-z_]\w*\s*,\s*["\']([A-Za-z_]\w*)["\']',
    re.MULTILINE
)

# 匹配 .def("method_name", &Class::method, ...)
# 同时匹配 .def(py::init<>())
DEF_NAME_RE = re.compile(
    r'\.def\s*\(\s*py::init\s*(?:<[^>]*>)?\s*\(\s*\)',  # .def(py::init<>()) 单独处理
    re.MULTILINE
)
DEF_RE = re.compile(
    r'\.def\s*\(\s*["\']([A-Za-z_]\w*)["\']'
    r'\s*,\s*'
    r'(?:&([A-Za-z_]\w*(?:::\w+)*(?:<[^>]*>)?(?:::\w+)?)'
    r'|py::overload_cast[^)]*\([^)]*\)\s*,\s*&?\w+(?:::\w+)*'
    r'|\[([^\]]*)\]\s*\([A-Za-z_]\w*\s*\)'
    r'|py::init<[^>]*>\(\)'
    r')',
    re.MULTILINE
)


class BindingMap:
    """pybind11 绑定映射表

    数据结构:
    {
        module_name: {
            "class_name": {
                "constructor": "cpp_file",
                "methods": {
                    "method_name": "cpp_file"
                }
            }
        }
    }
    """

    def __init__(self, file_index: FileIndex):
        self.idx = file_index
        self.map = {}

    def parse(self) -> dict:
        """扫描所有 C++ 源文件，提取 pybind11 绑定"""
        for f in self.idx.files:
            if f["ext"] not in (".cpp", ".cxx", ".cc"):
                continue
            try:
                content = read_text_smart(f["abs_path"])
            except Exception:
                continue
            self._parse_file(content, f["path"])
        return self.map

    def _parse_file(self, content: str, cpp_path: str):
        """解析单个 C++ 文件中的所有 pybind11 绑定"""
        # 1. 找出所有 PYBIND11_MODULE(module, m) 块的范围
        for module_match in PYBIND11_MODULE_RE.finditer(content):
            module_name = module_match.group(1)
            # 跳过 PYBIND11_MODULE(...) 后到 { 之间的空白
            i = module_match.end()
            while i < len(content) and content[i] in " \t\n\r":
                i += 1
            if i >= len(content) or content[i] != "{":
                continue
            m_start = i + 1
            # 找到匹配的右大括号（处理嵌套）
            body_end = self._find_matching_brace(content, m_start)
            if body_end == -1:
                continue
            body = content[m_start:body_end]

            # 2. 在 body 中提取 py::class_<...>(m, "Name")
            class_to_py = {}  # C++ 类名 → Python 类名
            for cls_match in PYBIND11_CLASS_RE.finditer(body):
                cpp_class = cls_match.group(1)
                py_name = cls_match.group(2)
                class_to_py[cpp_class] = py_name

            # 3. 在 body 中提取 .def("name", ...)
            if module_name not in self.map:
                self.map[module_name] = {}

            # 处理 .def(py::init<>())
            has_ctor = bool(DEF_NAME_RE.search(body))

            # 处理 .def("method", &Class::method)
            for def_match in DEF_RE.finditer(body):
                py_method = def_match.group(1)
                cpp_method_full = def_match.group(2)
                if cpp_method_full is None:
                    continue  # 跳过 lambda/overload_cast/init

                # 提取类名（如 "fvMatrix::solve" → "fvMatrix"）
                parts = cpp_method_full.split("::")
                cpp_class = "::".join(parts[:-1]) if len(parts) > 1 else ""
                # 去掉模板（如 "fvMatrix<Type>" → "fvMatrix"）
                cpp_class = re.sub(r'<[^>]*>$', '', cpp_class)
                # 获取 Python 类名
                py_class = class_to_py.get(cpp_class, cpp_class)

                if py_class not in self.map[module_name]:
                    self.map[module_name][py_class] = {
                        "constructor": None,
                        "methods": {}
                    }
                self.map[module_name][py_class]["methods"][py_method] = cpp_path

            # 标记构造函数
            if has_ctor:
                for py_class in self.map[module_name]:
                    if not self.map[module_name][py_class]["constructor"]:
                        self.map[module_name][py_class]["constructor"] = cpp_path

    @staticmethod
    def _find_matching_brace(content: str, start: int) -> int:
        """从 start 开始找到匹配的右大括号位置"""
        depth = 1
        i = start
        in_string = False
        in_char = False
        in_line_comment = False
        in_block_comment = False
        string_char = None
        while i < len(content):
            c = content[i]
            # 处理注释
            if in_line_comment:
                if c == "\n":
                    in_line_comment = False
                i += 1
                continue
            if in_block_comment:
                if c == "*" and i + 1 < len(content) and content[i + 1] == "/":
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            # 处理字符串
            if in_string:
                if c == "\\" and i + 1 < len(content):
                    i += 2
                    continue
                if c == string_char:
                    in_string = False
                i += 1
                continue
            if in_char:
                if c == "\\" and i + 1 < len(content):
                    i += 2
                    continue
                if c == string_char:
                    in_char = False
                i += 1
                continue
            # 正常代码
            if c == "/" and i + 1 < len(content):
                if content[i + 1] == "/":
                    in_line_comment = True
                    i += 2
                    continue
                if content[i + 1] == "*":
                    in_block_comment = True
                    i += 2
                    continue
            if c == '"':
                in_string = True
                string_char = c
                i += 1
                continue
            if c == "'":
                in_char = True
                string_char = c
                i += 1
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return -1

    def lookup(self, module: str, cls: str, method: str) -> str | None:
        """查表返回 C++ 文件路径，若不存在返回 None

        参数:
            module: Python 端 import 的模块名（如 "fvMatrix_module"）
            cls: 类名（如 "fvMatrix"）
            method: 方法名（如 "solve"），若为 "<init>" 查构造函数

        返回:
            C++ 文件相对路径（如 "src/fvMatrix.cpp"），未命中返回 None
        """
        if module not in self.map:
            return None
        if cls not in self.map[module]:
            return None
        if method == "<init>":
            return self.map[module][cls].get("constructor")
        if method not in self.map[module][cls]["methods"]:
            return None
        return self.map[module][cls]["methods"][method]

    def total_bindings(self) -> int:
        """返回总绑定数（用于统计）"""
        count = 0
        for module in self.map.values():
            for cls in module.values():
                count += len(cls["methods"])
        return count

    def summary(self) -> dict:
        """返回摘要信息"""
        modules = list(self.map.keys())
        total_classes = sum(len(m) for m in self.map.values())
        total_methods = self.total_bindings()
        return {
            "modules": modules,
            "total_modules": len(modules),
            "total_classes": total_classes,
            "total_methods": total_methods
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pybind11 绑定解析器")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    args = parser.parse_args()

    idx = FileIndex(args.root)
    bmap = BindingMap(idx)
    bmap.parse()
    summary = bmap.summary()
    print(f"扫描文件数: {idx.total_files()}")
    print(f"绑定模块数: {summary['total_modules']}")
    print(f"绑定类数:   {summary['total_classes']}")
    print(f"绑定方法数: {summary['total_methods']}")
    print(f"模块列表:   {summary['modules']}")
    print()
    for mod_name, classes in bmap.map.items():
        print(f"=== {mod_name} ===")
        for cls_name, info in classes.items():
            methods = list(info["methods"].keys())
            print(f"  {cls_name}: {len(methods)} methods")
            for m in methods:
                print(f"    .{m}() -> {info['methods'][m]}")


if __name__ == "__main__":
    main()
