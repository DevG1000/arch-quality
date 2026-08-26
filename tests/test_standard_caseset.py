"""
test_standard_caseset.py — 案例集验证（对照验证案例集 1.3）

对照案例集 A 类可复现项目，验证工具检测正确性（防误报/漏报）：
  案例 1.3 FreeCAD Document.cpp（低内聚阳性）→ FreeCAD App 模块 cohesion < 90
  案例 1.2 OpenFOAM Tensor.H（高耦合阳性）→ OpenFOAM src/OpenFOAM 耦合检测

说明：
- 仅在本机有对应 checkout 时执行（skipUnless）
- 合成案例（DBCP God Class / JDK 接口 / Spring 文档）已在单元测试/变异测试覆盖
- 属 B3.5 开源项目验证：验证"检测是否正确"而非"评分是否漂移"
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from arch_quality.arch_metrics_standard import StandardMetrics

FREECAD_APP = r"D:\OPENSOURCE\FreeCAD\src\App"
OPENFOAM_PRIMITIVES = r"D:\OPENSOURCE\OpenFOAM-v2512\src\OpenFOAM"


class TestFreeCadCase(unittest.TestCase):
    """案例 1.3: FreeCAD Document.cpp 低内聚（阳性 WARNING）"""

    @unittest.skipUnless(os.path.isdir(FREECAD_APP), "FreeCAD App 不可用")
    def test_document_cpp_large_file(self):
        m = StandardMetrics(FREECAD_APP)
        m.index.total_lines()  # 填充惰性 lines
        # Document.cpp 应为超大文件（>1000 行）
        doc_lines = None
        for f in m.index.files:
            if f["path"].endswith("Document.cpp"):
                doc_lines = f["lines"]
                break
        self.assertIsNotNone(doc_lines, "Document.cpp 未索引")
        self.assertGreater(doc_lines, 1000, "Document.cpp 应 >1000 行")
        # 内聚度应低于 90（有超大文件）
        self.assertLess(m.calc_cohesion(), 90)


class TestOpenFoamCase(unittest.TestCase):
    """案例 1.2: OpenFOAM Tensor.H 高耦合（阳性 WARNING）"""

    @unittest.skipUnless(os.path.isdir(OPENFOAM_PRIMITIVES), "OpenFOAM 不可用")
    def test_tensor_h_coupling(self):
        m = StandardMetrics(OPENFOAM_PRIMITIVES)
        coupling = m.calc_coupling()
        # 高耦合应使耦合度 < 90（2047 文件的大型头文件库）
        self.assertLess(coupling, 90, f"OpenFOAM 耦合度应 <90, 实际={coupling}")


if __name__ == "__main__":
    unittest.main()