# -*- coding: utf-8 -*-
"""HPC 交叉验证（B3.7）逻辑与语料测试。"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cross_validate_hpc as cv


class TestHpcCrossValidate(unittest.TestCase):
    def test_corpus(self):
        samples = cv.load_samples()
        self.assertEqual(len(samples), 9)
        labels = [s.get("label") for s in samples.values()]
        self.assertGreaterEqual(labels.count("healthy"), 5)
        self.assertGreaterEqual(labels.count("unhealthy"), 4)
        for s in samples.values():
            self.assertIsNotNone(s.get("overall"))

    def test_loocv_expected(self):
        samples = {
            "h1": {"overall": 100.0, "label": "healthy"},
            "h2": {"overall": 100.0, "label": "healthy"},
            "h3": {"overall": 86.5, "label": "healthy"},
            "h4": {"overall": 100.0, "label": "healthy"},
            "h5": {"overall": 100.0, "label": "healthy"},
            "u1": {"overall": 58.5, "label": "unhealthy"},
            "u2": {"overall": 67.0, "label": "unhealthy"},
            "u3": {"overall": 62.0, "label": "unhealthy"},
            "u4": {"overall": 75.0, "label": "unhealthy"},
        }
        result = cv.run_loocv(samples)
        self.assertEqual(result["n"], 9)
        self.assertEqual(result["passed"], 8)  # 最低的 58.5 是离群
        self.assertTrue(result["ok"])

    def test_loocv_all_identical(self):
        samples = {f"s{i}": {"overall": 100.0, "label": "healthy"} for i in range(9)}
        result = cv.run_loocv(samples)
        self.assertEqual(result["passed"], 9)

    def test_real_corpus_meets_threshold(self):
        result = cv.run_loocv(cv.load_samples())
        self.assertGreaterEqual(result["passed"], 7)
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
