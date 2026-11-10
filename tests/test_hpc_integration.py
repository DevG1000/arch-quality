# -*- coding: utf-8 -*-
"""HPC 集成/E2E：ComprehensiveReport 合并、权重归一化、报告生成、封顶展示。"""

import copy
import os
import tempfile
import unittest

from arch_quality.arch_report import ComprehensiveReport
from arch_quality.arch_report_generator import ReportGenerator


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class TestHpcIntegration(unittest.TestCase):
    def _hpc_project(self, d):
        _write(d, "halo.cpp",
               "#include <mpi.h>\n"
               "void f(){ MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,0); }\n")
        _write(d, "main.cpp",
               "#include <mpi.h>\n"
               "int main(){ MPI_Init(0,0); MPI_Barrier(MPI_COMM_WORLD); return 0; }\n")

    def test_report_merge_and_normalization(self):
        with tempfile.TemporaryDirectory() as d:
            self._hpc_project(d)
            r = ComprehensiveReport(d).generate()

            self.assertIn("hpc", r["dimensions"])
            self.assertIsNotNone(r["dimensions"]["hpc"]["score"])
            self.assertTrue(r["hpc_applicability_set"])
            self.assertEqual(r["hpc_score_scope"], "subset")
            self.assertIn(r["hpc_gate_status"], {"PASS", "WARN", "BLOCK"})
            self.assertIsInstance(r["hpc_waiver_audit"], dict)
            self.assertIn("hpc_version_info", r)

            weights = r["score_breakdown"]["normalized_weights"]
            self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)
            self.assertIn("dim.hpc", weights)

            hpc_rules = [v["rule"] for v in r["mlr_violations"]
                         if str(v.get("rule", "")).startswith("HPC")]
            self.assertTrue(hpc_rules, "期望 HPC 违规被合并进 mlr_violations")

            md = ReportGenerator(d, r, []).generate()
            self.assertIn("并行/异构计算架构增强评估", md)
            self.assertIn("**门禁**", md)
            self.assertIn("**适用集**", md)
            self.assertIn("**豁免审计**", md)

    def test_cap_display(self):
        with tempfile.TemporaryDirectory() as d:
            self._hpc_project(d)
            r = ComprehensiveReport(d).generate()
            r = copy.deepcopy(r)
            r["hpc_confirmed_max_severity"] = "HIGH"
            r["hpc_gate_status"] = "WARN"
            r["dimensions"]["hpc"]["score"] = 90.0
            r["dimensions"]["structural"]["hpc_enhancement"]["score"] = 90.0

            md = ReportGenerator(d, r, []).generate()
            self.assertIn("受封顶", md)
            self.assertIn("需改进", md)
            # 数值分保持原值
            self.assertIn("90.0/100", md)

    def test_topology_advisory_section(self):
        with tempfile.TemporaryDirectory() as d:
            self._hpc_project(d)
            _write(d, "system/decomposeParDict",
                   "numberOfSubdomains 4;\nmethod multiLevel;\n")
            _write(d, "run.slurm",
                   "#!/bin/bash\nsrun --cpu-bind=cores --gpus-per-task=1 ./solver\n")
            r = ComprehensiveReport(d).generate()
            self.assertIn("topology_advisory", r)
            self.assertEqual(r["topology_advisory"]["multi_level_decomposition"], "present")
            md = ReportGenerator(d, r, []).generate()
            self.assertIn("拓扑与亲和性建议", md)
            self.assertIn("advisory", md)

    def test_non_hpc_project(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "main.cpp", "int add(int a,int b){return a+b;}\n")
            r = ComprehensiveReport(d).generate()
            self.assertNotIn("hpc", r["dimensions"])
            self.assertEqual(r["hpc_applicability_set"], [])
            self.assertEqual(r["hpc_gate_status"], "PASS")


if __name__ == "__main__":
    unittest.main()
