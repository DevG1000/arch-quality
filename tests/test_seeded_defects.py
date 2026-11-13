# -*- coding: utf-8 -*-
"""seeded_defects.py 测试：机器召回 + semantic 任务生成 + Reviewer 评分。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import doc_lint  # noqa: E402
import seeded_defects as sd  # noqa: E402


class TestMutationSet(unittest.TestCase):
    def test_ids_unique_and_complete(self):
        ids = [d["id"] for d in sd.DEFECTS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len([d for d in sd.DEFECTS if d["kind"] == "machine"]), 7)
        self.assertEqual(len([d for d in sd.DEFECTS if d["kind"] == "semantic"]), 4)

    def test_baseline_is_clean(self):
        with tempfile.TemporaryDirectory() as d:
            ws = Path(d) / "ws"
            sd.build_baseline(ws)
            rep = sd.lint_ws(ws)
            self.assertEqual([f for f in rep.findings if f["level"] == "ERROR"], [])

    def test_all_machine_defects_caught(self):
        with tempfile.TemporaryDirectory() as d:
            summary = sd.run(Path(d))
            self.assertEqual(summary["machine_recall"], 1.0)
            for case in summary["cases"]:
                if case["kind"] == "machine":
                    self.assertTrue(case["caught"], case)

    def test_semantic_defects_invisible_to_machine(self):
        with tempfile.TemporaryDirectory() as d:
            summary = sd.run(Path(d), only=[x["id"] for x in sd.DEFECTS
                                            if x["kind"] == "semantic"])
            self.assertEqual(summary["semantic_total"], 4)
            self.assertEqual(summary["semantic_missed_by_machine"], 4)
            for case in summary["cases"]:
                self.assertEqual(case["machine_error_count"], 0)

    def test_semantic_case_emits_review_task(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            sd.run(out, only=["S1"])
            task = out / "S1" / "review_task.json"
            gt = out / "S1" / "ground_truth.json"
            self.assertTrue(task.exists() and gt.exists())
            data = json.loads(task.read_text(encoding="utf-8"))
            self.assertIn("diff", data)
            self.assertIn("instructions", data)
            self.assertNotIn("review_expect", data)  # 期望答案不能给 Reviewer


class TestControl(unittest.TestCase):
    def test_clean_control_passes_gates_and_review(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            summary = sd.run(out, only=["N0"])
            self.assertEqual(summary["control_ok"], 1)
            case = summary["cases"][0]
            self.assertEqual(case["detected_codes"], [])
            rv = out / "review.json"
            rv.write_text(json.dumps({
                "pr_id": "PR-1",
                "reviewer": {"model": "kimi-k3", "provider": "opencode-go", "role": "reviewer"},
                "verdict": "approved", "p0": 0, "p1": 0, "p2": 0, "comments": [],
            }, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(sd.grade(out / "N0", rv)["ok"])

    def test_clean_control_rejects_false_alarm(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            sd.run(out, only=["N0"])
            rv = out / "review.json"
            rv.write_text(json.dumps({
                "pr_id": "PR-1",
                "reviewer": {"model": "kimi-k3", "provider": "opencode-go", "role": "reviewer"},
                "verdict": "changes_requested", "p0": 0, "p1": 1, "p2": 0,
                "comments": [{"file": "x.md", "line": 1, "severity": "P1",
                              "evidence": "EV-X", "message": "误报"}],
            }, ensure_ascii=False), encoding="utf-8")
            self.assertFalse(sd.grade(out / "N0", rv)["ok"])


class TestGrading(unittest.TestCase):
    def _review(self, gt, **over):
        exp = gt["review_expect"]
        data = {
            "pr_id": "PR-1",
            "reviewer": {"model": "kimi-k3", "provider": "opencode-go", "role": "reviewer"},
            "verdict": "changes_requested",
            "p0": 0, "p1": 1, "p2": 0,
            "comments": [{
                "file": exp["file"], "line": exp["line"], "severity": exp["min_severity"],
                "evidence": "EV-REPO-gcs-guide",
                "message": "该论断缺少证据，且与既有实践矛盾",
                "suggestion": "补充实测或删除",
            }],
        }
        data.update(over)
        return data

    def test_grade_pass(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            sd.run(out, only=["S1"])
            gt = json.loads((out / "S1" / "ground_truth.json").read_text(encoding="utf-8"))
            rv = out / "review.json"
            rv.write_text(json.dumps(self._review(gt), ensure_ascii=False), encoding="utf-8")
            self.assertTrue(sd.grade(out / "S1", rv)["ok"])

    def test_grade_fails_on_approved(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            sd.run(out, only=["S1"])
            gt = json.loads((out / "S1" / "ground_truth.json").read_text(encoding="utf-8"))
            rv = out / "review.json"
            rv.write_text(json.dumps(self._review(gt, verdict="approved"), ensure_ascii=False),
                          encoding="utf-8")
            res = sd.grade(out / "S1", rv)
            self.assertFalse(res["ok"])
            self.assertTrue(any("verdict" in r for r in res["reasons"]))

    def test_grade_fails_on_wrong_location(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            sd.run(out, only=["S1"])
            gt = json.loads((out / "S1" / "ground_truth.json").read_text(encoding="utf-8"))
            rv = out / "review.json"
            data = self._review(gt)
            data["comments"][0]["file"] = "docs/zh/other/其它.md"
            rv.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.assertFalse(sd.grade(out / "S1", rv)["ok"])


if __name__ == "__main__":
    unittest.main()
