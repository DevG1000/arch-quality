# -*- coding: utf-8 -*-
"""HPC 规则变异测试（W2/W4 补强）

每个用例：健康基线 → 注入缺陷 → 断言对应 HPC 规则由“未触发”变为“触发”。
覆盖：HPC-002 守卫、HPC-003 launch 硬编码、HPC-005 配对、HPC-010 线程安全、HPC-011 竞态、HPC-012 嵌套。
"""

import os
import tempfile
import unittest

from arch_quality.arch_metrics_hpc import HpcArchitectureMetrics


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _rules(files):
    with tempfile.TemporaryDirectory() as d:
        for rel, text in files.items():
            _write(d, rel, text)
        m = HpcArchitectureMetrics(d)
        return {v["rule"] for v in m.check_hpc_rules()}


MPI_HEADER = "#include <mpi.h>\n"

CASES = [
    (
        "HPC-002-guard",
        "HPC-002",
        {"a.cpp": "#ifdef USE_CUDA\nvoid f(){ cudaMalloc(0,0); }\n#endif\n"},
        {"a.cpp": "void f(){ cudaMalloc(0,0); }\n"},
    ),
    (
        "HPC-003-launch",
        "HPC-003",
        {"a.cpp": "#pragma omp target teams num_teams(T) thread_limit(B)\nfor(int i=0;i<9;i++){}\n"},
        {"a.cpp": "#pragma omp target teams num_teams(1024) thread_limit(256)\nfor(int i=0;i<9;i++){}\n"},
    ),
    (
        "HPC-005-pairing",
        "HPC-005",
        {"a.cpp": MPI_HEADER + "void f(){ MPI_Request r; MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,&r); MPI_Wait(&r,MPI_STATUS_IGNORE); }\n"},
        {"a.cpp": MPI_HEADER + "void f(){ MPI_Request r; MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,&r); }\n"},
    ),
    (
        "HPC-010-thread-safe",
        "HPC-010",
        {"a.cpp": MPI_HEADER + "void f(){ int x=0; #pragma omp parallel\n{ #pragma omp master\n{ MPI_Allreduce(&x,&x,1,MPI_INT,MPI_SUM,MPI_COMM_WORLD); } } }\n"},
        {"a.cpp": MPI_HEADER + "void f(){ int x=0; #pragma omp parallel\n{ MPI_Allreduce(&x,&x,1,MPI_INT,MPI_SUM,MPI_COMM_WORLD); } }\n"},
    ),
    (
        "HPC-011-race",
        "HPC-011",
        {"a.cpp": "void f(){ double s=0; double a[9];\n#pragma omp parallel for reduction(+:s)\nfor(int i=0;i<9;i++){ s += a[i]; } }\n"},
        {"a.cpp": "void f(){ double s=0; double a[9];\n#pragma omp parallel for\nfor(int i=0;i<9;i++){ s += a[i]; } }\n"},
    ),
    (
        "HPC-012-nesting",
        "HPC-012",
        {"a.cpp": "#pragma omp parallel\n{ }\n"},
        {"a.cpp": "#pragma omp parallel\n{ #pragma omp parallel\n{ } }\n"},
    ),
]


class TestHpcMutation(unittest.TestCase):
    def test_rule_flips_on_mutation(self):
        for cid, rule, before, after in CASES:
            with self.subTest(case=cid):
                self.assertNotIn(rule, _rules(before), f"{cid}: 基线不应触发 {rule}")
                self.assertIn(rule, _rules(after), f"{cid}: 变异后应触发 {rule}")


if __name__ == "__main__":
    unittest.main()
