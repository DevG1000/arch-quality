# -*- coding: utf-8 -*-
"""HPC 引擎 W1 单元测试：启用检测 / 权重 / 适用性 / 豁免 / 输出结构。"""

import os
import tempfile
import unittest

from arch_quality.arch_core import load_weights_from_skill
from arch_quality.arch_metrics_hpc import (
    HpcArchitectureMetrics, SKILL_PATH, DIMENSIONS,
)


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class TestSkillWeights(unittest.TestCase):
    def test_weights_sum_100(self):
        w = load_weights_from_skill(SKILL_PATH)
        self.assertEqual(len(w), 4)
        self.assertAlmostEqual(sum(w.values()), 1.0, places=9)


class TestDetection(unittest.TestCase):
    def test_non_hpc(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "main.cpp", "int main(){return 0;}\n")
            m = HpcArchitectureMetrics(d)
            self.assertFalse(m._is_hpc)
            r = m.all_metrics()
            self.assertFalse(r["is_hpc"])
            self.assertIsNone(r["overall"])

    def test_mpi(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "halo.cpp", '#include <mpi.h>\nvoid f(){MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,0);}\n')
            m = HpcArchitectureMetrics(d)
            self.assertTrue(m._is_hpc)
            app = m._applicability()
            self.assertTrue(app["mpi_halo"])
            self.assertTrue(app["load_topology"])
            self.assertFalse(app["backend_consistency"])

    def test_openmp(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "loop.cpp", "#pragma omp parallel for\nfor(int i=0;i<10;i++){}\n")
            m = HpcArchitectureMetrics(d)
            self.assertTrue(m._is_hpc)
            self.assertTrue(m._applicability()["hybrid_parallel"])

    def test_cuda(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "k.cu", "__global__ void k(){} int f(){cudaMalloc(0,0);}\n")
            m = HpcArchitectureMetrics(d)
            self.assertTrue(m._is_hpc)
            self.assertTrue(m._applicability()["backend_consistency"])

    def test_kokkos_build_backend(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "CMakeLists.txt", "set(KOKKOS_ENABLE_CUDA ON)\n")
            m = HpcArchitectureMetrics(d)
            self.assertTrue(m._is_hpc)
            self.assertTrue(m._applicability()["backend_consistency"])

    def test_kokkos_generic_is_not_gpu(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "pf.cpp", "void f(){Kokkos::parallel_for(0,0);}\n")
            m = HpcArchitectureMetrics(d)
            self.assertTrue(m._is_hpc)
            app = m._applicability()
            self.assertFalse(app["backend_consistency"])
            self.assertTrue(app["hybrid_parallel"])


class TestMetrics(unittest.TestCase):
    def test_mpi_metrics_structure(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "halo.cpp", "#include <mpi.h>\nvoid f(){MPI_Barrier(MPI_COMM_WORLD);}\n")
            m = HpcArchitectureMetrics(d)
            r = m.all_metrics()
            self.assertEqual(set(r["dimensions"]), set(DIMENSIONS))
            self.assertEqual(r["score_scope"], "subset")
            self.assertEqual(r["gate_status"], "PASS")
            self.assertEqual(r["overall"], 100.0)
            self.assertEqual(r["version_info"]["guide_version"], "0.8")

    def test_waiver_audit(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "bench.cpp",
                   "/* @hpc_benchmark_ok: microbench */\n#pragma omp parallel\nfor(int i=0;i<1;i++){}\n")
            m = HpcArchitectureMetrics(d)
            r = m.all_metrics()
            self.assertEqual(r["waiver_audit"]["benchmark_ok"]["count"], 1)

    def test_abuse_warning(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.cpp", "/* @hpc_benchmark_ok: microbench */\n#pragma omp parallel\n{}\n")
            _write(d, "b.cpp", "/* @hpc_deferred: todo */\n#pragma omp parallel\n{}\n")
            _write(d, "c.cpp", "#pragma omp parallel\n{}\n")
            m = HpcArchitectureMetrics(d)
            audit = m.all_metrics()["waiver_audit"]
            self.assertIsNotNone(audit["abuse_warning"])

    def test_invalid_waiver(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "bad.cpp", "/* @hpc_benchmark_ok */\n#pragma omp parallel\n{}\n")
            m = HpcArchitectureMetrics(d)
            audit = m.all_metrics()["waiver_audit"]
            self.assertEqual(len(audit["invalid_waivers"]), 1)


class TestHpc010ThreadSupport(unittest.TestCase):
    """HPC-010：按实际/条件线程级别判断，不得因别处出现 MULTIPLE 而整项目跳过。"""

    BAD = ("#include <mpi.h>\n"
           "void g(){ int x=0; #pragma omp parallel\n"
           "{ MPI_Allreduce(&x,&x,1,MPI_INT,MPI_SUM,MPI_COMM_WORLD); } }\n")

    def test_conditional_multiple_does_not_suppress(self):
        files = {
            "init.cpp": "#include <mpi.h>\nvoid f(int needsThread){ int p;"
                        " int req = needsThread ? MPI_THREAD_MULTIPLE : MPI_THREAD_SINGLE;"
                        " MPI_Init_thread(0,0,req,&p); }\n",
            "bad.cpp": self.BAD,
        }
        self.assertIn("HPC-010", _rules(files))

    def test_literal_multiple_is_safe(self):
        files = {
            "init.cpp": "#include <mpi.h>\nvoid f(){ int p;"
                        " MPI_Init_thread(0,0,MPI_THREAD_MULTIPLE,&p); }\n",
            "bad.cpp": self.BAD,
        }
        self.assertNotIn("HPC-010", _rules(files))

    def test_funneled_triggers(self):
        files = {
            "init.cpp": "#include <mpi.h>\nvoid f(){ int p;"
                        " MPI_Init_thread(0,0,MPI_THREAD_FUNNELED,&p); }\n",
            "bad.cpp": self.BAD,
        }
        self.assertIn("HPC-010", _rules(files))

    def test_query_thread_only_triggers(self):
        files = {
            "init.cpp": "#include <mpi.h>\nvoid f(){ int p; MPI_Query_thread(&p); }\n",
            "bad.cpp": self.BAD,
        }
        self.assertIn("HPC-010", _rules(files))

    def test_parallel_for_mpi_triggers(self):
        files = {
            "a.cpp": "#include <mpi.h>\nvoid g(){ int x=0; #pragma omp parallel for\n"
                     "for(int i=0;i<9;i++){ MPI_Allreduce(&x,&x,1,MPI_INT,MPI_SUM,MPI_COMM_WORLD); } }\n",
        }
        self.assertIn("HPC-010", _rules(files))

    def test_parallel_for_followed_by_mpi_loop_no_false_positive(self):
        files = {
            "a.cpp": (
                "#include <mpi.h>\n"
                "void g(){ double loc=0, glob=0; int n=9, maxIter=9;\n"
                "#pragma omp parallel for reduction(+:loc)\n"
                "for (int i=0;i<n;i++) loc += i;\n"
                "for (int iter=0;iter<maxIter;iter++) {\n"
                "  MPI_Allreduce(&loc,&glob,1,MPI_DOUBLE,MPI_SUM,MPI_COMM_WORLD);\n"
                "}\n}\n"),
        }
        self.assertNotIn("HPC-010", _rules(files))

    def test_master_protected_no_trigger(self):
        files = {
            "a.cpp": "#include <mpi.h>\nvoid g(){ int x=0; #pragma omp parallel\n"
                     "{ #pragma omp master\n{ MPI_Allreduce(&x,&x,1,MPI_INT,MPI_SUM,MPI_COMM_WORLD); } } }\n",
        }
        self.assertNotIn("HPC-010", _rules(files))


class TestTopologyAdvisory(unittest.TestCase):
    """多级计算结构 advisory：存在/缺失信号，且不计分。"""

    def _mpi_source(self, d):
        _write(d, "a.cpp", "#include <mpi.h>\nvoid f(){ MPI_Barrier(MPI_COMM_WORLD); }\n")

    def test_signals_present(self):
        with tempfile.TemporaryDirectory() as d:
            self._mpi_source(d)
            _write(d, "system/decomposeParDict",
                   "numberOfSubdomains 8;\nmethod multiLevel;\n"
                   "multiLevelCoeffs { nodes { numberOfSubdomains 2; method hierarchical;"
                   " coeffs { n (2 1 1); } } }\n")
            _write(d, "run.slurm",
                   "#!/bin/bash\nsrun --cpu-bind=cores --gpus-per-task=1 ./solver\n")
            m = HpcArchitectureMetrics(d)
            r = m.all_metrics()
            a = r["topology_advisory"]
            self.assertFalse(a["scored"])
            self.assertEqual(a["multi_level_decomposition"], "present")
            self.assertEqual(a["cpu_binding"], "present")
            self.assertEqual(a["gpu_binding"], "present")
            self.assertEqual(a["weighted_partition"], "absent")
            self.assertEqual(r["overall"], 100.0)
            self.assertEqual(r["gate_status"], "PASS")

    def test_no_config_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            self._mpi_source(d)
            a = HpcArchitectureMetrics(d).all_metrics()["topology_advisory"]
            self.assertEqual(a["scanned_config_files"], 0)
            self.assertEqual(a["multi_level_decomposition"], "unknown")
            self.assertEqual(a["cpu_binding"], "unknown")

    def test_advisory_does_not_change_score(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            self._mpi_source(d1)
            self._mpi_source(d2)
            _write(d2, "system/decomposeParDict", "numberOfSubdomains 4;\nmethod multiLevel;\n")
            r1 = HpcArchitectureMetrics(d1).all_metrics()
            r2 = HpcArchitectureMetrics(d2).all_metrics()
            self.assertEqual(r1["overall"], r2["overall"])
            self.assertEqual(r1["gate_status"], r2["gate_status"])


if __name__ == "__main__":
    unittest.main()


RULE_CASES = {
    "HPC-001": (
        {"a.cpp": "#include <mpi.h>\n#ifdef __CUDACC__\nvoid k(){}\n#else\nvoid f(){ for(int i=0;i<9;i++){} }\n#endif\n"},
        {"a.cpp": "#include <mpi.h>\n#ifdef MFEM_USE_CUDA\nvoid k(){}\n#else\nvoid f(){ for(int i=0;i<9;i++){} }\n#endif\n"},
    ),
    "HPC-002": (
        {"a.cpp": "void f(){ cudaMalloc(0,0); }\n"},
        {"a.cpp": "#ifdef USE_CUDA\nvoid f(){ cudaMalloc(0,0); }\n#endif\n"},
    ),
    "HPC-003": (
        {"a.cpp": "#pragma omp target teams num_teams(1024) thread_limit(256)\nfor(int i=0;i<9;i++){}\n"},
        {"a.cpp": "#pragma omp target teams num_teams(T) thread_limit(B)\nfor(int i=0;i<9;i++){}\n"},
    ),
    "HPC-004": (
        {"a.cpp": "void f(){ for(int s=0;s<9;s++){ cudaMemcpy(0,0,0,0); } }\n"},
        {"a.cpp": "#pragma omp target data map(tofrom:a[0:n])\nvoid f(){ for(int s=0;s<9;s++){ cudaMemcpy(0,0,0,0); } }\n"},
    ),
    "HPC-005": (
        {"a.cpp": "#include <mpi.h>\nvoid f(){ MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,0); }\n"},
        {"a.cpp": "#include <mpi.h>\nvoid f(){ MPI_Request r; MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,&r); MPI_Wait(&r,MPI_STATUS_IGNORE); }\n"},
    ),
    "HPC-006": (
        {"a.cpp": "#include <mpi.h>\nvoid f(){ for(int i=0;i<9;i++){ MPI_Allreduce(0,0,1,MPI_INT,MPI_SUM,MPI_COMM_WORLD); } }\n"},
        {"a.cpp": "#include <mpi.h>\nvoid f(){ for(int iter=0;iter<9;iter++){ MPI_Allreduce(0,0,1,MPI_INT,MPI_SUM,MPI_COMM_WORLD); } }\n"},
    ),
    "HPC-007": (
        {"a.cpp": "#include <mpi.h>\nvoid f(){ MPI_Send(0,0,MPI_INT,0,0,MPI_COMM_WORLD); compute(); }\n"},
        {"a.cpp": "#include <mpi.h>\nvoid f(){ MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,0); compute(); }\n"},
    ),
    "HPC-008": (
        {"a.cpp": "#include <mpi.h>\nvoid f(){ refineLocally(); METIS_PartGraphKway(0); }\n"},
        {"a.cpp": "#include <mpi.h>\nvoid f(){ PartitionWeights w; refineLocally(); METIS_PartGraphKway(0); }\n"},
    ),
    "HPC-009": (
        {"a.cpp": "#include <mpi.h>\nvoid a(){ MPI_Barrier(MPI_COMM_WORLD); }\n",
         "b.cpp": "#include <mpi.h>\nvoid b(){ MPI_Barrier(MPI_COMM_WORLD); }\n"},
        {"a.cpp": "#include <mpi.h>\nvoid a(){ MPI_Comm_split(MPI_COMM_WORLD,0,0,0); }\n",
         "b.cpp": "#include <mpi.h>\nvoid b(){ MPI_Barrier(MPI_COMM_WORLD); }\n"},
    ),
    "HPC-010": (
        {"a.cpp": "#include <mpi.h>\nvoid f(){ int x=0; #pragma omp parallel\n{ MPI_Allreduce(&x,&x,1,MPI_INT,MPI_SUM,MPI_COMM_WORLD); } }\n"},
        {"a.cpp": "#include <mpi.h>\nvoid f(){ int x=0; #pragma omp parallel\n{ #pragma omp master\n{ MPI_Allreduce(&x,&x,1,MPI_INT,MPI_SUM,MPI_COMM_WORLD); } } }\n"},
    ),
    "HPC-011": (
        {"a.cpp": "void f(){ double sum=0; double a[9];\n#pragma omp parallel for\nfor(int i=0;i<9;i++){ sum += a[i]; } }\n"},
        {"a.cpp": "void f(){ double sum=0; double a[9];\n#pragma omp parallel for reduction(+:sum)\nfor(int i=0;i<9;i++){ sum += a[i]; } }\n"},
    ),
    "HPC-012": (
        {"a.cpp": "#pragma omp parallel\n{ #pragma omp parallel\n{ } }\n"},
        {"a.cpp": "#pragma omp parallel\n{ }\n"},
    ),
}


def _rules(files):
    with tempfile.TemporaryDirectory() as d:
        for rel, text in files.items():
            _write(d, rel, text)
        m = HpcArchitectureMetrics(d)
        return {v["rule"] for v in m.check_hpc_rules()}


class TestRules(unittest.TestCase):
    def test_positive(self):
        for rule, (pos, _neg) in RULE_CASES.items():
            with self.subTest(rule=rule):
                self.assertIn(rule, _rules(pos), f"{rule} 正例应触发")

    def test_negative(self):
        for rule, (_pos, neg) in RULE_CASES.items():
            with self.subTest(rule=rule):
                self.assertNotIn(rule, _rules(neg), f"{rule} 负例不应触发")
