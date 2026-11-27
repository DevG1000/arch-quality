"""H3 WP-8 F1: WP7 reference case set validation tests."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import validate_reference_cases as v


class TestReferenceCases(unittest.TestCase):
    def test_layout(self):
        import json
        path = v.find_case_list()
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        self.assertEqual(v.validate(data), [])
        for dim in v.REQUIRED:
            self.assertEqual(len(data[dim]["samples"]), 9)

    def test_bad_health_distribution_fails(self):
        data = {"standard": {"samples": {
            f"s{i}": {"path": "x", "overall": i, "health": "healthy"}
            for i in range(9)
        }}}
        errors = v.validate(data)
        self.assertTrue(any("9 samples" in e or "5 healthy" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
