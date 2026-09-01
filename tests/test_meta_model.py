# -*- coding: utf-8 -*-
"""WP-7 元模型 validator 测试"""

import json
import os
import subprocess
import sys
import unittest

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALIDATOR = os.path.join(PROJECT, "scripts", "validate_meta_model.py")
REGISTRY = os.path.join(PROJECT, "meta_model_registry.json")


class TestMetaModelValidator(unittest.TestCase):
    def setUp(self):
        with open(REGISTRY, encoding="utf-8") as f:
            self.reg = json.load(f)

    def test_registry_exists(self):
        self.assertTrue(os.path.exists(REGISTRY))
        self.assertIn("rules", self.reg)
        self.assertEqual(len(self.reg["rules"]), 60)

    def test_validator_passes(self):
        r = subprocess.run([sys.executable, VALIDATOR], capture_output=True,
                           text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS", r.stdout)

    def test_rule_count_per_engine(self):
        from collections import Counter
        c = Counter()
        for rule in self.reg["rules"]:
            prefix = rule["id"].split("-")[0]
            c[prefix] += 1
        for prefix in ["SAR", "MLR", "TPL", "NVR", "MPR"]:
            self.assertEqual(c.get(prefix, 0), 12)

    def test_rule_id_format(self):
        for rule in self.reg["rules"]:
            rid = rule["id"]
            prefix, num = rid.split("-")
            self.assertIn(prefix, ["SAR", "MLR", "TPL", "NVR", "MPR"])
            self.assertTrue(1 <= int(num) <= 12)

    def test_no_holes(self):
        from collections import defaultdict
        by_prefix = defaultdict(set)
        for rule in self.reg["rules"]:
            prefix, num = rule["id"].split("-")
            by_prefix[prefix].add(int(num))
        for prefix, nums in by_prefix.items():
            self.assertEqual(nums, set(range(1, 13)), prefix)

    def test_standard_weights_sum_1(self):
        std_dims = [d for d in self.reg["dimensions"] if d["engine"] == "standard"]
        self.assertAlmostEqual(sum(d["weight"] for d in std_dims), 1.0, places=6)

    def test_waivable_has_waived_level(self):
        for rule in self.reg["rules"]:
            if rule.get("waivable"):
                self.assertIn(rule.get("waived_output_level"),
                              ["ERROR", "WARNING", "INFO"], rule["id"])


if __name__ == "__main__":
    unittest.main()
