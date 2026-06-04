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

from arch_quality.arch_python_ast import extract_pybind11_calls, _parse_content


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


if __name__ == "__main__":
    unittest.main(verbosity=2)