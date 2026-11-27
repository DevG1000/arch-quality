"""H3 WP-8 E1: scientific kernel ACL extension tests."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from arch_quality.arch_metrics_anti_corruption import AntiCorruptionMetrics

PROJ = os.path.join(os.path.dirname(__file__), "mutation", "projects")


class TestScientificKernelSignals(unittest.TestCase):
    def test_direct_petsc_vtk_detected(self):
        m = AntiCorruptionMetrics(os.path.join(PROJ, "sci_kernel_direct"))
        r = m.all_metrics()
        self.assertTrue(r["is_acl"])
        d = r["dimensions"]["external_access"]["detail"]
        self.assertGreater(d["direct_access"]["direct_count"], 0)
        cov = r["dimensions"]["wrapper_coverage"]["detail"]["coverage"]["coverage"]
        self.assertLess(cov, 0.6)
        self.assertLess(r["overall"], 70)

    def test_wrapped_science_kernel_is_clean(self):
        m = AntiCorruptionMetrics(os.path.join(PROJ, "sci_kernel_wrapped"))
        r = m.all_metrics()
        self.assertTrue(r["is_acl"])
        d = r["dimensions"]["external_access"]["detail"]
        self.assertEqual(d["direct_access"]["direct_count"], 0)
        cov = r["dimensions"]["wrapper_coverage"]["detail"]["coverage"]
        self.assertGreaterEqual(cov["coverage"], 0.6)
        self.assertGreaterEqual(r["overall"], 80)

    def test_geometry_project_still_detected(self):
        m = AntiCorruptionMetrics(os.path.join(PROJ, "good_project_acl"))
        self.assertTrue(m.all_metrics()["is_acl"])


if __name__ == "__main__":
    unittest.main()
