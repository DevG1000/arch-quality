"""
test_bindings_parser.py — arch_bindings_parser.py 单元测试

测试场景:
1. 单个 PYBIND11_MODULE + 多个 .def()
2. 多行 PYBIND11_MODULE
3. 模板类绑定 (template)
4. lambda 绑定（应被跳过）
5. 没有 PYBIND11_MODULE 的纯 C++ 文件
6. 嵌套大括号（应正确处理）
"""

import os
import shutil
import tempfile
import unittest

from arch_quality.arch_core import FileIndex
from arch_quality.arch_bindings_parser import BindingMap

SEP = os.sep


class TestBindingParser(unittest.TestCase):

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_single_class_basic(self):
        cpp = '''#include <pybind11/pybind11.h>
namespace py = pybind11;

class fvMatrix {
public:
    void solve();
    double residual();
};

PYBIND11_MODULE(fvMatrix_module, m) {
    py::class_<fvMatrix>(m, "fvMatrix")
        .def(py::init<>())
        .def("solve", &fvMatrix::solve)
        .def("residual", &fvMatrix::residual)
    ;
}
'''
        tmp = self._make_fixture({f"src{SEP}fvMatrix.cpp": cpp})
        try:
            idx = FileIndex(tmp)
            bmap = BindingMap(idx)
            bmap.parse()
            self.assertIn("fvMatrix_module", bmap.map)
            self.assertIn("fvMatrix", bmap.map["fvMatrix_module"])
            methods = bmap.map["fvMatrix_module"]["fvMatrix"]["methods"]
            self.assertEqual(methods["solve"], f"src{SEP}fvMatrix.cpp")
            self.assertEqual(methods["residual"], f"src{SEP}fvMatrix.cpp")
            self.assertEqual(bmap.total_bindings(), 2)
        finally:
            import shutil
            shutil.rmtree(tmp)

    def test_multiline_pybind11_module(self):
        cpp = '''#include <pybind11/pybind11.h>
namespace py = pybind11;

class Solver {};

PYBIND11_MODULE(
    solver_module,
    m
) {
    py::class_<Solver>(m, "Solver")
        .def(py::init<>())
        .def("run", &Solver::run)
        .def("stop", &Solver::stop)
    ;
}
'''
        tmp = self._make_fixture({f"src{SEP}solver.cpp": cpp})
        try:
            idx = FileIndex(tmp)
            bmap = BindingMap(idx)
            bmap.parse()
            self.assertIn("solver_module", bmap.map)
            methods = bmap.map["solver_module"]["Solver"]["methods"]
            self.assertEqual(methods["run"], f"src{SEP}solver.cpp")
            self.assertEqual(methods["stop"], f"src{SEP}solver.cpp")
        finally:
            shutil.rmtree(tmp)

    def test_template_class(self):
        cpp = '''#include <pybind11/pybind11.h>
namespace py = pybind11;

template<typename T>
class Container {
public:
    void push(T value);
    T pop();
};

PYBIND11_MODULE(container_module, m) {
    py::class_<Container<int>>(m, "Container")
        .def(py::init<>())
        .def("push", &Container<int>::push)
        .def("pop", &Container<int>::pop)
    ;
}
'''
        tmp = self._make_fixture({f"src{SEP}container.cpp": cpp})
        try:
            idx = FileIndex(tmp)
            bmap = BindingMap(idx)
            bmap.parse()
            self.assertIn("container_module", bmap.map)
            methods = bmap.map["container_module"]["Container"]["methods"]
            self.assertIn("push", methods)
            self.assertIn("pop", methods)
        finally:
            shutil.rmtree(tmp)

    def test_lambda_def(self):
        cpp = '''#include <pybind11/pybind11.h>
namespace py = pybind11;

class Helper {};

PYBIND11_MODULE(helper_module, m) {
    py::class_<Helper>(m, "Helper")
        .def(py::init<>())
        .def("name", [](const Helper&) { return "helper"; })
        .def("real", &Helper::real)
    ;
}
'''
        tmp = self._make_fixture({f"src{SEP}helper.cpp": cpp})
        try:
            idx = FileIndex(tmp)
            bmap = BindingMap(idx)
            bmap.parse()
            methods = bmap.map["helper_module"]["Helper"]["methods"]
            self.assertIn("real", methods)
            self.assertNotIn("name", methods)
        finally:
            shutil.rmtree(tmp)

    def test_no_pybind11(self):
        cpp = '''#include <iostream>
class Pure { void run(); };
'''
        tmp = self._make_fixture({f"src{SEP}pure.cpp": cpp})
        try:
            idx = FileIndex(tmp)
            bmap = BindingMap(idx)
            bmap.parse()
            self.assertEqual(bmap.total_bindings(), 0)
        finally:
            shutil.rmtree(tmp)

    def test_nested_braces(self):
        cpp = '''#include <pybind11/pybind11.h>
namespace py = pybind11;

class Engine {
public:
    void start() {
        if (true) {
            for (int i = 0; i < 10; i++) {
                // nested logic
            }
        }
    }
    void stop();
};

PYBIND11_MODULE(engine_module, m) {
    py::class_<Engine>(m, "Engine")
        .def(py::init<>())
        .def("start", &Engine::start)
        .def("stop", &Engine::stop)
    ;
}
'''
        tmp = self._make_fixture({f"src{SEP}engine.cpp": cpp})
        try:
            idx = FileIndex(tmp)
            bmap = BindingMap(idx)
            bmap.parse()
            methods = bmap.map["engine_module"]["Engine"]["methods"]
            self.assertIn("start", methods)
            self.assertIn("stop", methods)
        finally:
            shutil.rmtree(tmp)

    def test_lookup_constructor(self):
        cpp = '''#include <pybind11/pybind11.h>
namespace py = pybind11;

class A {
public:
    A();
    void run();
};

PYBIND11_MODULE(a_mod, m) {
    py::class_<A>(m, "A")
        .def(py::init<>())
        .def("run", &A::run)
    ;
}
'''
        tmp = self._make_fixture({f"src{SEP}a.cpp": cpp})
        try:
            idx = FileIndex(tmp)
            bmap = BindingMap(idx)
            bmap.parse()
            ctor = bmap.lookup("a_mod", "A", "<init>")
            self.assertEqual(ctor, f"src{SEP}a.cpp")
            run = bmap.lookup("a_mod", "A", "run")
            self.assertEqual(run, f"src{SEP}a.cpp")
            missing = bmap.lookup("a_mod", "A", "missing")
            self.assertIsNone(missing)
        finally:
            shutil.rmtree(tmp)

    def test_real_world_fvMatrix(self):
        cpp = '''#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "fvMatrix.h"

namespace py = pybind11;

PYBIND11_MODULE(fvMatrix_module, m) {
    py::class_<fvMatrix>(m, "fvMatrix")
        .def(py::init<>())
        .def("solve", &fvMatrix::solve, "Solve the matrix")
        .def("residual", &fvMatrix::residual, "Get residual")
        .def("setCoeff", &fvMatrix::setCoeff, "Set coefficient")
        .def("setRHS", &fvMatrix::setRHS, "Set RHS")
        .def("getSolution", &fvMatrix::getSolution, "Get solution")
        .def("assemble", &fvMatrix::assemble, "Assemble matrix")
        .def("applyBCs", &fvMatrix::applyBCs, "Apply BCs")
        .def("reset", &fvMatrix::reset, "Reset state")
        .def("size", &fvMatrix::size, "Get size")
        .def("iterations", &fvMatrix::iterations, "Iteration count")
        .def("setTolerance", &fvMatrix::setTolerance, "Set tolerance")
    ;
}
'''
        tmp = self._make_fixture({"src/fvMatrix_bindings.cpp": cpp})
        try:
            idx = FileIndex(tmp)
            bmap = BindingMap(idx)
            bmap.parse()
            methods = bmap.map["fvMatrix_module"]["fvMatrix"]["methods"]
            expected = ["solve", "residual", "setCoeff", "setRHS",
                       "getSolution", "assemble", "applyBCs", "reset",
                       "size", "iterations", "setTolerance"]
            for m in expected:
                self.assertIn(m, methods, f"Missing method: {m}")
            self.assertEqual(len(methods), 11)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    import shutil
    unittest.main(verbosity=2)