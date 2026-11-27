"""H3 WP-8 F2: projects.yaml H1 ref/checksum gate tests."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fetch_project


class TestH1RefGate(unittest.TestCase):
    def test_all_h1_projects_have_ref_and_checksum(self):
        projects, checksums = fetch_project.load_projects()
        for name in fetch_project.H1_REQUIRED_REF:
            fetch = projects.get(name)
            self.assertIsNotNone(fetch, f"{name} missing from projects.yaml")
            repo = fetch.get("fetch", {}).get("repo", "")
            if fetch.get("fetch", {}).get("method") == "local" or repo == "local":
                continue
            self.assertTrue(fetch["fetch"].get("ref"), f"{name} missing fetch.ref")
            self.assertIn(f"git_ref:{repo}", checksums, f"{name} missing checksum")

    def test_check_all_passes_for_current_manifest(self):
        projects, checksums = fetch_project.load_projects()
        self.assertTrue(fetch_project.check_all(projects, checksums))

    def test_missing_h1_ref_fails(self):
        projects = {"openfoam": {"fetch": {"repo": "https://example.invalid/repo.git"}}}
        self.assertFalse(fetch_project.check_all(projects, {}))


if __name__ == "__main__":
    unittest.main()
