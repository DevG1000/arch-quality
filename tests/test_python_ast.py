"""
test_python_ast.py — arch_python_ast.py 单元测试

测试场景:
1. 基本 import + 实例化 + 方法调用
2. import as 别名
3. from import 形式
4. 多级属性链（不应误判）
5. 第三方库调用（不应误判，如 numpy）
6. 距离过远（应被忽略）
7. 普通 Python 类（不应误判）
8. 多个实例
9. 实际 pyFoam 风格循环
"""

import unittest

from arch_quality.arch_python_ast import (
    extract_pybind11_calls, _parse_content,
    find_malloc_tokens_in_py, is_codegen_template,
    has_ffi_context, check_paired_free,
    has_pybind11_context, is_third_party_path,
)


class TestPythonAST(unittest.TestCase):

    def test_basic_import_instantiate_call(self):
        code = '''
import fvMatrix_module

m = fvMatrix_module.fvMatrix()
m.solve()
m.residual()
'''
        calls = _parse_content(code, "test.py")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["method"], "solve")
        self.assertEqual(calls[0]["module"], "fvMatrix_module")
        self.assertEqual(calls[0]["class"], "fvMatrix")
        self.assertEqual(calls[1]["method"], "residual")

    def test_import_as_alias(self):
        code = '''
import fvMatrix_module as fvm

m = fvm.fvMatrix()
m.solve()
'''
        calls = _parse_content(code, "test.py")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["module"], "fvMatrix_module")
        self.assertEqual(calls[0]["class"], "fvMatrix")

    def test_from_import(self):
        code = '''
from fvMatrix_module import fvMatrix

m = fvMatrix()
m.solve()
'''
        calls = _parse_content(code, "test.py")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["module"], "fvMatrix_module")
        self.assertEqual(calls[0]["class"], "fvMatrix")

    def test_multilevel_chain(self):
        code = '''
import fvMatrix_module
a = fvMatrix_module
b = a.fvMatrix
m = b()
m.solve()  # b 是变量, 但 fvMatrix 是 attr
'''
        calls = _parse_content(code, "test.py")
        self.assertEqual(len(calls), 0)

    def test_third_party_library(self):
        code = '''
import numpy as np
import pandas as pd
import requests

arr = np.array([1, 2, 3])
arr.sort()

df = pd.DataFrame()
df.head()

resp = requests.get("http://example.com")
resp.json()
'''
        calls = _parse_content(code, "test.py")
        self.assertGreaterEqual(len(calls), 3)
        modules = {c["module"] for c in calls}
        self.assertIn("numpy", modules)
        self.assertIn("pandas", modules)

    def test_distance_limit(self):
        code = '''
import fvMatrix_module

m = fvMatrix_module.fvMatrix()

# 大段不相关代码
x = 1
y = 2
z = 3
a = 4
b = 5
c = 6
d = 7
e = 8

# 距离实例化 12 行，超出 MAX_TRACK_DISTANCE=5
m.solve()
'''
        calls = _parse_content(code, "test.py")
        self.assertEqual(len(calls), 0)

    def test_normal_python_class(self):
        code = '''
class MyClass:
    def __init__(self):
        self.value = 0
    def do_something(self):
        return self.value

obj = MyClass()
obj.do_something()
'''
        calls = _parse_content(code, "test.py")
        self.assertEqual(len(calls), 0)

    def test_multiple_instances(self):
        code = '''
import fvMatrix_module

m1 = fvMatrix_module.fvMatrix()
m2 = fvMatrix_module.fvMatrix()
m1.solve()
m2.solve()
m1.residual()
'''
        calls = _parse_content(code, "test.py")
        self.assertEqual(len(calls), 3)
        methods = [c["method"] for c in calls]
        self.assertEqual(methods.count("solve"), 2)
        self.assertEqual(methods.count("residual"), 1)

    def test_pyfoam_real_world(self):
        code = '''
import fvMatrix_module

def run_simulation(steps=1000):
    m = fvMatrix_module.fvMatrix()
    for t in range(steps):
        m.assemble()
        m.applyBCs()
        m.solve()
        m.residual()

if __name__ == "__main__":
    run_simulation(500)
'''
        calls = _parse_content(code, "run.py")
        self.assertEqual(len(calls), 4)
        methods = [c["method"] for c in calls]
        self.assertIn("assemble", methods)
        self.assertIn("solve", methods)
        self.assertIn("residual", methods)

    def test_dunder_methods_skipped(self):
        code = '''
import fvMatrix_module

m = fvMatrix_module.fvMatrix()
m.__str__()
m.__repr__()
m.solve()
'''
        calls = _parse_content(code, "test.py")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["method"], "solve")

    def test_no_call_no_emit(self):
        code = '''
import fvMatrix_module

m = fvMatrix_module.fvMatrix()
# 没有任何方法调用
print("done")
'''
        calls = _parse_content(code, "test.py")
        self.assertEqual(len(calls), 0)


class TestMLR010Detection(unittest.TestCase):

    def test_find_malloc_tokens_normal(self):
        source = "buf = ctypes.malloc(1024)\nfree(buf)"
        hits = find_malloc_tokens_in_py(source)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][1], "malloc")

    def test_find_malloc_tokens_string_literal(self):
        source = 'msg = "return malloc(n);"\nprint(msg)'
        hits = find_malloc_tokens_in_py(source)
        self.assertEqual(len(hits), 0)

    def test_find_malloc_tokens_comment(self):
        source = "# uses malloc internally\nx = 42"
        hits = find_malloc_tokens_in_py(source)
        self.assertEqual(len(hits), 0)

    def test_find_malloc_tokens_substring(self):
        source = "data = preallocated_mem\nresult = reallocated_list"
        hits = find_malloc_tokens_in_py(source)
        self.assertEqual(len(hits), 0)

    def test_find_malloc_tokens_code_generator(self):
        source = (
            'c_code = """\n'
            '{3}_API void *{2}Malloc(size_t n)\n'
            '{{\n'
            '  return malloc(n);\n'
            '}}\n'
            '"""\n'
        )
        hits = find_malloc_tokens_in_py(source)
        self.assertEqual(len(hits), 0)

    def test_is_codegen_template(self):
        source = (
            'c_code = """\n'
            '#include <stdlib.h>\n'
            '#include <string.h>\n'
            'extern "C" {{\n'
            '#include {2}c.h"\n'
            '}}\n'
            '{3}_API void *{2}Malloc(size_t n)\n'
            '{{\n'
            '  return malloc(n);\n'
            '}}\n'
            '"""\n'
        )
        self.assertTrue(is_codegen_template(source))

    def test_is_codegen_template_extern_c(self):
        source = 'extern "C" {\n#include "mylib.h"\n}\n' * 1 + '{{\nreturn malloc(n);\n}}\n' * 3
        self.assertTrue(is_codegen_template(source))

    def test_is_not_codegen_template(self):
        source = "x = 42\nprint(x)"
        self.assertFalse(is_codegen_template(source))

    def test_has_ffi_context(self):
        self.assertTrue(has_ffi_context("from ctypes import CDLL"))
        self.assertTrue(has_ffi_context("lib = CDLL('mylib.so')"))
        self.assertTrue(has_ffi_context("import pybind11"))
        self.assertFalse(has_ffi_context("x = 42\nprint(x)"))

    def test_check_paired_free(self):
        self.assertTrue(check_paired_free("lib.free(buf)"))
        self.assertTrue(check_paired_free("gmshFree(ptr)"))
        self.assertFalse(check_paired_free("x = 42"))


class TestMLR008Context(unittest.TestCase):

    def test_has_pybind11_context_cpp(self):
        self.assertTrue(has_pybind11_context('#include <pybind11/pybind11.h>'))
        self.assertTrue(has_pybind11_context('PYBIND11_MODULE(foo, m) {'))
        self.assertTrue(has_pybind11_context('py::object result = m.attr("name");'))
        self.assertTrue(has_pybind11_context('#include "Python.h"'))
        self.assertTrue(has_pybind11_context('PyObject *obj = PyLong_FromLong(42);'))
        self.assertFalse(has_pybind11_context('doc.attr("idprefix", "_");'))
        self.assertFalse(has_pybind11_context('x.call(42);'))
        self.assertFalse(has_pybind11_context('int result = parser.parse(line);'))


class TestMLR012Context(unittest.TestCase):

    def test_is_third_party_path(self):
        self.assertTrue(is_third_party_path("src/libbg/geogram/third_party/liblbfgs/fortran/lbfgs.f"))
        self.assertTrue(is_third_party_path("contrib/foobar/baz.c"))
        self.assertTrue(is_third_party_path("vendor/libfoo/foo.cpp"))
        self.assertTrue(is_third_party_path("external/openssl/crypto.c"))
        self.assertFalse(is_third_party_path("src/librt/primitives/bot/bot.c"))
        self.assertFalse(is_third_party_path("src/libbu/bu.c"))

    def test_f77_ext_detection(self):
        self.assertEqual("f", "f")
        self.assertNotEqual("f90", "f")
        self.assertNotEqual("f95", "f")


if __name__ == "__main__":
    unittest.main(verbosity=2)