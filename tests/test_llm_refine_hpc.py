# -*- coding: utf-8 -*-
"""HPC LLM 语义精判（可选层）逻辑测试：不联网、不改评分/门禁。"""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import llm_refine_hpc as lr


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class FakeClient:
    def __init__(self, response='{"verdict":"confirm","evidence":"src/a.cpp:2 risk","confidence":"high"}'):
        self.response = response
        self.calls = 0

    def review(self, prompt):
        self.calls += 1
        return self.response


def _violation(rule="HPC-005", file="src/a.cpp", candidate=True, confirmed=False):
    return {
        "rule": rule, "name": "halo", "severity": "HIGH", "output_level": "WARNING",
        "count": 1, "candidate": candidate, "confirmed": confirmed,
        "files": [file] if file else [], "detail": "MPI_Isend 后未见 Wait",
    }


class TestParseReview(unittest.TestCase):
    def test_valid(self):
        r = lr.parse_review('{"verdict":"reject","evidence":"src/a.cpp:2 paired","confidence":"medium"}')
        self.assertEqual(r["verdict"], "reject")
        self.assertEqual(r["confidence"], "medium")

    def test_invalid(self):
        self.assertEqual(lr.parse_review("not json")["verdict"], "uncertain")
        self.assertEqual(lr.parse_review("")["verdict"], "uncertain")

    def test_confirm_without_evidence(self):
        r = lr.parse_review('{"verdict":"confirm","evidence":"","confidence":"high"}')
        self.assertEqual(r["verdict"], "uncertain")

    def test_mock(self):
        r = lr.parse_review(lr.MockClient().review("x"))
        self.assertEqual(r["verdict"], "uncertain")


class TestRefine(unittest.TestCase):
    def test_does_not_change_confirmed_gate_score(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "src/a.cpp",
                   "#include <mpi.h>\nvoid f(){ MPI_Request r;"
                   " MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,&r); }\n")
            client = FakeClient()
            enriched, stats = lr.refine_candidates(
                [_violation()], d, client, {}, "fake-model", max_items=10)
            v = enriched[0]
            self.assertFalse(v["confirmed"])          # 不自动确认
            self.assertEqual(v["llm_review"], "confirm")
            self.assertEqual(v["llm_model"], "fake-model")
            self.assertNotIn("gate_status", v)
            self.assertEqual(client.calls, 1)
            self.assertEqual(stats["reviewed"], 1)

    def test_cache(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "src/a.cpp",
                   "#include <mpi.h>\nvoid f(){ MPI_Request r;"
                   " MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,&r); }\n")
            client = FakeClient()
            cache = {}
            enriched, stats = lr.refine_candidates(
                [_violation(), _violation()], d, client, cache, "fake-model")
            self.assertEqual(client.calls, 1)
            self.assertEqual(stats["cached"], 1)
            self.assertEqual(len(cache), 1)

    def test_max_items(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.cpp", "#include <mpi.h>\nvoid a(){ MPI_Request r; MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,&r); }\n")
            _write(d, "b.cpp", "#include <mpi.h>\nvoid b(){ MPI_Request r; MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,&r); }\n")
            _write(d, "c.cpp", "#include <mpi.h>\nvoid c(){ MPI_Request r; MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,&r); }\n")
            client = FakeClient()
            enriched, stats = lr.refine_candidates(
                [_violation(file="a.cpp"), _violation(file="b.cpp"), _violation(file="c.cpp")],
                d, client, {}, "fake-model", max_items=1)
            self.assertEqual(len(enriched), 3)
            self.assertEqual(client.calls, 1)
            self.assertEqual(stats["reviewed"], 1)

    def test_no_file_is_uncertain_without_call(self):
        with tempfile.TemporaryDirectory() as d:
            client = FakeClient()
            enriched, stats = lr.refine_candidates(
                [_violation(rule="HPC-009", file="")], d, client, {}, "fake-model")
            self.assertEqual(enriched[0]["llm_review"], "uncertain")
            self.assertEqual(client.calls, 0)

    def test_snippet(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "src/a.cpp", "#include <mpi.h>\n\nvoid f(){\n"
                     "  MPI_Request r; MPI_Isend(0,0,MPI_INT,0,0,MPI_COMM_WORLD,&r);\n}\n")
            snippet, line = lr.extract_snippet(d, "src/a.cpp", "HPC-005")
            self.assertIn("MPI_Isend", snippet)
            self.assertGreaterEqual(line, 1)


if __name__ == "__main__":
    unittest.main()
