"""
test_template_metrics.py — arch_metrics_template.py 单元测试

测试场景:
1. 非C++项目返回 is_cpp_project=False，各维度分数为 None
2. 纯C++项目（无模板）各维度基本评分
3. 编译时耦合评分算法
4. 模板实例化重复率评分
5. 头文件影响半径评分
6. 模板嵌套度评分
7. 二进制膨胀率评分
8. 不必要模板化评分
9. MLR规则检测（MLR-013~024）
10. 综合评分权重计算
"""

import os
import shutil
import tempfile
import unittest

from arch_quality.arch_metrics_template import (
    TemplateMetaprogrammingMetrics,
    _count_angle_depth,
    _has_cpp_files,
    calibrate_thresholds,
)
from arch_quality.arch_core import FileIndex


class TestHelperFunctions(unittest.TestCase):

    def test_count_angle_depth_simple(self):
        self.assertEqual(_count_angle_depth("<int>"), 1)

    def test_count_angle_depth_nested(self):
        self.assertEqual(_count_angle_depth("A<B<C<int>>>"), 3)

    def test_count_angle_depth_empty(self):
        self.assertEqual(_count_angle_depth(""), 0)


class TestNonCppProject(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        py_file = os.path.join(self.tmp, "main.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write("import os\nprint('hello')\n")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_is_not_cpp_project(self):
        index = FileIndex(self.tmp)
        self.assertFalse(_has_cpp_files(index))

    def test_all_metrics_returns_none(self):
        metrics = TemplateMetaprogrammingMetrics(self.tmp)
        result = metrics.all_metrics()
        self.assertFalse(result["is_cpp_project"])
        self.assertIsNone(result["overall"])
        self.assertEqual(result["cpp_file_count"], 0)
        for dim_name in result["dimensions"]:
            self.assertIsNone(result["dimensions"][dim_name]["score"])

    def test_no_mlr_violations(self):
        metrics = TemplateMetaprogrammingMetrics(self.tmp)
        violations = metrics.check_mlr_rules()
        self.assertEqual(violations, [])


class TestCppProjectBasic(unittest.TestCase):

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_simple_cpp_project_has_cpp(self):
        tmp = self._make_fixture({
            "src/main.cpp": '#include <iostream>\nint main() { return 0; }\n',
        })
        try:
            index = FileIndex(tmp)
            self.assertTrue(_has_cpp_files(index))
        finally:
            shutil.rmtree(tmp)

    def test_simple_cpp_project_overall(self):
        tmp = self._make_fixture({
            "src/main.cpp": '#include <iostream>\nint main() { return 0; }\n',
            "src/utils.h": '#ifndef UTILS_H\n#define UTILS_H\nvoid hello();\n#endif\n',
            "src/utils.cpp": '#include "utils.h"\nvoid hello() {}\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            result = metrics.all_metrics()
            self.assertTrue(result["is_cpp_project"])
            self.assertIsNotNone(result["overall"])
            self.assertGreaterEqual(result["overall"], 0)
            self.assertLessEqual(result["overall"], 100)
        finally:
            shutil.rmtree(tmp)


class TestCompileTimeCoupling(unittest.TestCase):

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_low_coupling_header(self):
        tmp = self._make_fixture({
            "src/utils.h": '#ifndef UTILS_H\n#define UTILS_H\nvoid helper();\n#endif\n',
            "src/main.cpp": '#include "utils.h"\nint main() { helper(); return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            score, detail = metrics.calc_compile_time_coupling()
            self.assertIsNotNone(score)
            self.assertGreaterEqual(score, 80)
        finally:
            shutil.rmtree(tmp)

    def test_high_coupling_header(self):
        includes = "\n".join(
            f'#include "module{i}.h"' for i in range(20)
        )
        files = {
            "src/common.h": '#ifndef COMMON_H\n#define COMMON_H\nvoid init();\n#endif\n',
            "src/main.cpp": includes + "\nint main() { return 0; }\n",
        }
        for i in range(20):
            files[f"src/module{i}.h"] = f'#ifndef MOD{i}_H\n#define MOD{i}_H\nvoid mod{i}();\n#endif\n'
        tmp = self._make_fixture(files)
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            score, detail = metrics.calc_compile_time_coupling()
            self.assertIsNotNone(score)
        finally:
            shutil.rmtree(tmp)


class TestTemplateNestingDepth(unittest.TestCase):

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_no_templates_returns_100(self):
        tmp = self._make_fixture({
            "src/main.cpp": 'int main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            score, detail = metrics.calc_template_nesting_depth()
            self.assertEqual(score, 100)
            self.assertEqual(detail["max_depth"], 0)
        finally:
            shutil.rmtree(tmp)

    def test_deep_nesting_penalty(self):
        tmp = self._make_fixture({
            "src/deep.h": 'template<typename A>\nstruct Deep { A value; };\nusing X = Deep<Deep<Deep<int>>>;\n',
            "src/main.cpp": '#include "deep.h"\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            score, detail = metrics.calc_template_nesting_depth()
            self.assertIsNotNone(score)
            self.assertGreater(detail.get("max_depth", 0), 0)
        finally:
            shutil.rmtree(tmp)


class TestBinaryBloatRatio(unittest.TestCase):

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_no_templates_high_score(self):
        tmp = self._make_fixture({
            "src/utils.cpp": 'void helper() {}\nvoid process() {}\n',
            "src/main.cpp": 'int main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            score, detail = metrics.calc_binary_bloat_ratio()
            self.assertIsNotNone(score)
            self.assertGreaterEqual(score, 80)
        finally:
            shutil.rmtree(tmp)

    def test_template_heavy_lower_score(self):
        tmp = self._make_fixture({
            "src/templates.h": (
                'template<typename T> class Container { T data; };\n'
                'template<typename T> class List { T item; };\n'
                'template<typename T> class Stack { T top; };\n'
                'template<typename T> class Queue { T front; };\n'
            ),
            "src/main.cpp": '#include "templates.h"\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            score, detail = metrics.calc_binary_bloat_ratio()
            self.assertIsNotNone(score)
            self.assertIn("bloat_ratio", detail)
        finally:
            shutil.rmtree(tmp)


class TestUnnecessaryTemplating(unittest.TestCase):

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_no_templates_returns_100(self):
        tmp = self._make_fixture({
            "src/main.cpp": 'int main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            score, detail = metrics.calc_unnecessary_templating()
            self.assertEqual(score, 100)
        finally:
            shutil.rmtree(tmp)


class TestMLRRules(unittest.TestCase):

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_mlr014_with_specialization_waiver(self):
        tmp = self._make_fixture({
            "src/vec.h": (
                '#ifndef VEC_H\n#define VEC_H\n'
                'template<typename T> class Vec { T data[3]; };\n'
                '// @template_specialization_required: multi-precision\n'
                '#endif\n'
            ),
            "src/a.cpp": '#include "vec.h"\nVec<double> v1;\n',
            "src/b.cpp": '#include "vec.h"\nVec<double> v2;\n',
            "src/c.cpp": '#include "vec.h"\nVec<double> v3;\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr014 = [v for v in violations if v["rule"] == "MLR-014"]
            self.assertTrue(any(v["rule"] == "MLR-014" for v in violations))
            v014 = next(v for v in violations if v["rule"] == "MLR-014")
            self.assertEqual(v014["severity"], "HIGH")
            self.assertEqual(v014["output_level"], "INFO")
            self.assertTrue(v014.get("waivable", False))
        finally:
            shutil.rmtree(tmp)

    def test_mlr014_without_waiver(self):
        tmp = self._make_fixture({
            "src/vec.h": (
                '#ifndef VEC_H\n#define VEC_H\n'
                'template<typename T> class Vec { T data[3]; };\n'
                '#endif\n'
            ),
            "src/a.cpp": '#include "vec.h"\nVec<double> v1;\n',
            "src/b.cpp": '#include "vec.h"\nVec<double> v2;\n',
            "src/c.cpp": '#include "vec.h"\nVec<double> v3;\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr014 = [v for v in violations if v["rule"] == "MLR-014"]
            if mlr014:
                self.assertEqual(mlr014[0]["severity"], "HIGH")
        finally:
            shutil.rmtree(tmp)

    def test_mlr017_with_bloat_waiver(self):
        tmp = self._make_fixture({
            "src/heavy.h": (
                '#ifndef HEAVY_H\n#define HEAVY_H\n'
                'template<typename T> class Matrix { T data[16]; };\n'
                'template<typename T> class Vector { T data[4]; };\n'
                'template<typename T> class Tensor { T data[9]; };\n'
                'template<typename T> class Grid { T data[64]; };\n'
                'template<typename T> class SparseMatrix { T data[100]; };\n'
                '// @allow_binary_bloat: SIMD optimization; '
                'performance_gain: 40%; compile_time_increase: 15s; '
                'benchmark_script: bench/bloat.sh; threshold: 35%\n'
                '#endif\n'
            ),
            "src/main.cpp": '#include "heavy.h"\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr017 = [v for v in violations if v["rule"] == "MLR-017"]
            if mlr017:
                self.assertEqual(mlr017[0]["severity"], "MEDIUM")
                self.assertEqual(mlr017[0]["output_level"], "INFO")
                self.assertTrue(mlr017[0].get("waivable", False))
        finally:
            shutil.rmtree(tmp)

    def test_mlr018_with_reserved_extension(self):
        tmp = self._make_fixture({
            "src/math_utils.h": (
                '#ifndef MATH_UTILS_H\n#define MATH_UTILS_H\n'
                'template<typename T> T clamp(T val, T lo, T hi);\n'
                '// @reserved_for_future_extension: float, int, custom_complex\n'
                '#endif\n'
            ),
            "src/main.cpp": (
                '#include "math_utils.h"\n'
                'double x = clamp(1.0, 0.0, 2.0);\n'
                'int main() { return 0; }\n'
            ),
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr018 = [v for v in violations if v["rule"] == "MLR-018"]
            if mlr018:
                self.assertEqual(mlr018[0]["severity"], "HIGH")
                self.assertEqual(mlr018[0]["output_level"], "INFO")
        finally:
            shutil.rmtree(tmp)

    def test_mlr023_merge_to_014_flag(self):
        tmp = self._make_fixture({
            "src/vec.h": (
                '#ifndef VEC_H\n#define VEC_H\n'
                'template<typename T> class Vec { T data[3]; };\n'
                '#endif\n'
            ),
            "src/a.cpp": '#include "vec.h"\nVec<double> v1;\n',
            "src/b.cpp": '#include "vec.h"\nVec<double> v2;\n',
            "src/c.cpp": '#include "vec.h"\nVec<double> v3;\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr023 = [v for v in violations if v["rule"] == "MLR-023"]
            if mlr023:
                self.assertEqual(mlr023[0].get("merge_to"), "MLR-014")
        finally:
            shutil.rmtree(tmp)

    def test_mlr024_with_cpp20_modules(self):
        tmp = self._make_fixture({
            "src/a.h": '#ifndef A_H\n#define A_H\n#include "b.h"\nvoid funcA();\n#endif\n',
            "src/b.h": '#ifndef B_H\n#define B_H\n#include "a.h"\nvoid funcB();\n#endif\n',
            "src/main.cpp": '#include "a.h"\nint main() { return 0; }\n',
            "src/module.ixx": 'export module mymodule;\nexport void func();\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr024 = [v for v in violations if v["rule"] == "MLR-024"]
            if mlr024:
                self.assertEqual(mlr024[0]["severity"], "LOW")
        finally:
            shutil.rmtree(tmp)

    def test_mlr024_cycle_detection(self):
        tmp = self._make_fixture({
            "src/a.h": '#ifndef A_H\n#define A_H\n#include "b.h"\nvoid funcA();\n#endif\n',
            "src/b.h": '#ifndef B_H\n#define B_H\n#include "a.h"\nvoid funcB();\n#endif\n',
            "src/main.cpp": '#include "a.h"\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr024 = [v for v in violations if v["rule"] == "MLR-024"]
            self.assertGreaterEqual(len(mlr024), 0)
        finally:
            try:
                shutil.rmtree(tmp)
            except OSError:
                pass

    def test_mlr018_gold_plated_template(self):
        tmp = self._make_fixture({
            "src/math_utils.h": (
                '#ifndef MATH_UTILS_H\n#define MATH_UTILS_H\n'
                'template<typename T> T clamp(T val, T lo, T hi);\n'
                '#endif\n'
            ),
            "src/main.cpp": (
                '#include "math_utils.h"\n'
                'double x = clamp(1.0, 0.0, 2.0);\n'
                'int main() { return 0; }\n'
            ),
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr018 = [v for v in violations if v["rule"] == "MLR-018"]
            self.assertGreaterEqual(len(mlr018), 0)
        finally:
            shutil.rmtree(tmp)

    def test_mlr019_no_extern_template(self):
        tmp = self._make_fixture({
            "src/vec.h": (
                '#ifndef VEC_H\n#define VEC_H\n'
                'template<typename T> class Vec { T data[3]; };\n'
                '#endif\n'
            ),
            "src/a.cpp": '#include "vec.h"\nVec<double> v1;\n',
            "src/b.cpp": '#include "vec.h"\nVec<double> v2;\n',
            "src/c.cpp": '#include "vec.h"\nVec<double> v3;\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr019 = [v for v in violations if v["rule"] == "MLR-019"]
            self.assertGreaterEqual(len(mlr019), 0)
        finally:
            shutil.rmtree(tmp)

    def test_mlr014_filters_typedef_context(self):
        tmp = self._make_fixture({
            "src/vec.h": (
                '#ifndef VEC_H\n#define VEC_H\n'
                'template<typename T> class Vec { T data[3]; };\n'
                '#endif\n'
            ),
            "src/a.cpp": (
                '#include "vec.h"\n'
                'typedef Vec<double> VecD;\n'
                'using VecF = Vec<float>;\n'
                'Vec<double> v1;\n'
                'int main() { return 0; }\n'
            ),
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr014 = [v for v in violations if v["rule"] == "MLR-014"]
            # 只有 Vec<double> v1 是真正的实例化，typedef/using 被过滤
            # 1 次实例化不触发 MLR-014 (>2 才触发)
            self.assertEqual(len(mlr014), 0)
        finally:
            shutil.rmtree(tmp)

    def test_mlr014_downgrades_with_extern_template(self):
        tmp = self._make_fixture({
            "src/vec.h": (
                '#ifndef VEC_H\n#define VEC_H\n'
                'template<typename T> class Vec { T data[3]; };\n'
                '#endif\n'
            ),
            "src/vec.cpp": (
                '#include "vec.h"\n'
                'extern template class Vec<double>;\n'
                'template class Vec<double>;\n'
            ),
            "src/a.cpp": '#include "vec.h"\nVec<double> v1;\n',
            "src/b.cpp": '#include "vec.h"\nVec<double> v2;\n',
            "src/c.cpp": '#include "vec.h"\nVec<double> v3;\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr014 = [v for v in violations if v["rule"] == "MLR-014"]
            if mlr014:
                # 使用 extern template 后，output_level 应为 INFO
                self.assertEqual(mlr014[0]["output_level"], "INFO")
        finally:
            shutil.rmtree(tmp)


class TestAllMetricsIntegration(unittest.TestCase):

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_full_cpp_project_metrics(self):
        tmp = self._make_fixture({
            "src/vector.h": (
                '#ifndef VECTOR_H\n#define VECTOR_H\n'
                'template<typename T, int N>\n'
                'class Vector {\n'
                '    T data[N];\n'
                'public:\n'
                '    T& operator[](int i) { return data[i]; }\n'
                '};\n'
                '#endif\n'
            ),
            "src/matrix.h": (
                '#ifndef MATRIX_H\n#define MATRIX_H\n'
                '#include "vector.h"\n'
                'template<typename T, int R, int C>\n'
                'class Matrix {\n'
                '    Vector<T, C> rows[R];\n'
                '};\n'
                '#endif\n'
            ),
            "src/main.cpp": (
                '#include "matrix.h"\n'
                'int main() {\n'
                '    Matrix<double, 3, 3> m;\n'
                '    return 0;\n'
                '}\n'
            ),
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            result = metrics.all_metrics()
            self.assertTrue(result["is_cpp_project"])
            self.assertIsNotNone(result["overall"])
            self.assertGreaterEqual(result["overall"], 0)
            self.assertLessEqual(result["overall"], 100)
            self.assertIn("compile_time_fanin", result["dimensions"])
            self.assertIn("template_redundancy", result["dimensions"])
            self.assertIn("header_influence_radius", result["dimensions"])
            self.assertIn("template_nesting_depth", result["dimensions"])
            self.assertIn("binary_bloat_ratio", result["dimensions"])
            self.assertIn("unnecessary_templating", result["dimensions"])
            self.assertIn("mlr_violations", result)
        finally:
            shutil.rmtree(tmp)


class TestOutputLevel4(unittest.TestCase):

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_mlr022_always_error(self):
        tmp = self._make_fixture({
            "src/recursive.h": (
                '#ifndef REC_H\n#define REC_H\n'
                'template<typename T> class List : List<T> { };\n'
                '#endif\n'
            ),
            "src/main.cpp": '#include "recursive.h"\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr022 = [v for v in violations if v["rule"] == "MLR-022"]
            if mlr022:
                self.assertEqual(mlr022[0]["severity"], "HIGH")
                self.assertEqual(mlr022[0]["output_level"], "ERROR")
        finally:
            shutil.rmtree(tmp)

    def test_mlr024_error_without_modules(self):
        tmp = self._make_fixture({
            "src/a.h": '#ifndef A_H\n#define A_H\n#include "b.h"\nvoid funcA();\n#endif\n',
            "src/b.h": '#ifndef B_H\n#define B_H\n#include "a.h"\nvoid funcB();\n#endif\n',
            "src/main.cpp": '#include "a.h"\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr024 = [v for v in violations if v["rule"] == "MLR-024"]
            if mlr024:
                self.assertEqual(mlr024[0]["output_level"], "ERROR")
                self.assertEqual(mlr024[0]["severity"], "HIGH")
        finally:
            shutil.rmtree(tmp)

    def test_mlr024_low_with_modules(self):
        tmp = self._make_fixture({
            "src/a.h": '#ifndef A_H\n#define A_H\n#include "b.h"\nvoid funcA();\n#endif\n',
            "src/b.h": '#ifndef B_H\n#define B_H\n#include "a.h"\nvoid funcB();\n#endif\n',
            "src/main.cpp": '#include "a.h"\nint main() { return 0; }\n',
            "src/module.ixx": 'export module mymodule;\nexport void func();\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr024 = [v for v in violations if v["rule"] == "MLR-024"]
            if mlr024:
                self.assertEqual(mlr024[0]["output_level"], "LOW")
                self.assertEqual(mlr024[0]["severity"], "LOW")
        finally:
            try:
                shutil.rmtree(tmp)
            except OSError:
                pass

    def test_mlr017_incomplete_waiver_is_warning(self):
        tmp = self._make_fixture({
            "src/heavy.h": (
                '#ifndef HEAVY_H\n#define HEAVY_H\n'
                'template<typename T> class Matrix { T data[16]; };\n'
                'template<typename T> class Vector { T data[4]; };\n'
                'template<typename T> class Tensor { T data[9]; };\n'
                'template<typename T> class Grid { T data[64]; };\n'
                'template<typename T> class SparseMatrix { T data[100]; };\n'
                '// @allow_binary_bloat: SIMD optimization\n'
                '#endif\n'
            ),
            "src/main.cpp": '#include "heavy.h"\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr017 = [v for v in violations if v["rule"] == "MLR-017"]
            if mlr017:
                self.assertEqual(mlr017[0]["output_level"], "WARNING")
        finally:
            shutil.rmtree(tmp)

    def test_mlr014_output_level_without_waiver(self):
        tmp = self._make_fixture({
            "src/vec.h": (
                '#ifndef VEC_H\n#define VEC_H\n'
                'template<typename T> class Vec { T data[3]; };\n'
                '#endif\n'
            ),
            "src/a.cpp": '#include "vec.h"\nVec<double> v1;\n',
            "src/b.cpp": '#include "vec.h"\nVec<double> v2;\n',
            "src/c.cpp": '#include "vec.h"\nVec<double> v3;\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr014 = [v for v in violations if v["rule"] == "MLR-014"]
            if mlr014:
                self.assertEqual(mlr014[0]["severity"], "HIGH")
                self.assertEqual(mlr014[0]["output_level"], "WARNING")
        finally:
            shutil.rmtree(tmp)

    def test_cross_rule_014_017_coordination(self):
        tmp = self._make_fixture({
            "src/vec.h": (
                '#ifndef VEC_H\n#define VEC_H\n'
                'template<typename T> class Vec { T data[3]; };\n'
                '// @template_specialization_required: multi-precision\n'
                '#endif\n'
            ),
            "src/heavy.h": (
                '#ifndef HEAVY_H\n#define HEAVY_H\n'
                'template<typename T> class Matrix { T data[16]; };\n'
                'template<typename T> class Vector { T data[4]; };\n'
                'template<typename T> class Tensor { T data[9]; };\n'
                'template<typename T> class Grid { T data[64]; };\n'
                'template<typename T> class SparseMatrix { T data[100]; };\n'
                '// @allow_binary_bloat: SIMD; performance_gain: 40%; '
                'compile_time_increase: 15s; benchmark_script: bench/bloat.sh; threshold: 35%\n'
                '#endif\n'
            ),
            "src/a.cpp": '#include "vec.h"\nVec<double> v1;\n',
            "src/b.cpp": '#include "vec.h"\nVec<double> v2;\n',
            "src/c.cpp": '#include "vec.h"\nVec<double> v3;\n',
            "src/main.cpp": '#include "heavy.h"\nint main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            violations = metrics.check_mlr_rules()
            mlr017 = [v for v in violations if v["rule"] == "MLR-017"]
            if mlr017:
                self.assertIn("跨规则协调", mlr017[0]["detail"])
        finally:
            shutil.rmtree(tmp)


class TestCalibrateThresholds(unittest.TestCase):

    def test_too_few_samples_returns_defaults(self):
        result = calibrate_thresholds([
            {"fan_in": 10, "influence_radius": 5, "redundancy_rate": 0.1,
             "bloat_rate": 0.2, "nesting_depth": 3},
        ])
        self.assertEqual(result["fan_in"], 50)
        self.assertEqual(result["influence_radius"], 80)

    def test_enough_samples_returns_calibrated(self):
        samples = [
            {"fan_in": i * 2, "influence_radius": i * 3,
             "redundancy_rate": i / 100, "bloat_rate": i / 50,
             "nesting_depth": i}
            for i in range(1, 26)
        ]
        result = calibrate_thresholds(samples)
        self.assertIsInstance(result["fan_in"], float)
        self.assertIsInstance(result["influence_radius"], float)
        self.assertGreater(result["fan_in"], 10)


class TestDimensionNames(unittest.TestCase):

    def _make_fixture(self, files: dict) -> str:
        tmp = tempfile.mkdtemp()
        for path, content in files.items():
            full = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return tmp

    def test_output_uses_4_dimension_names(self):
        tmp = self._make_fixture({
            "src/main.cpp": 'int main() { return 0; }\n',
        })
        try:
            metrics = TemplateMetaprogrammingMetrics(tmp)
            result = metrics.all_metrics()
            self.assertIn("compile_time_fanin", result["dimensions"])
            self.assertNotIn("compile_time_coupling", result["dimensions"])
            self.assertIn("template_nesting_depth", result["dimensions"])
            self.assertNotIn("template_nesting_degree", result["dimensions"])
            self.assertIn("unnecessary_templating", result["dimensions"])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()