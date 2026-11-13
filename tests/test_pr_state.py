# -*- coding: utf-8 -*-
"""pr_state.py 闭环状态机测试（Proposer→Reviewer→人工→合并→回评）。"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import doc_lint  # noqa: E402
import pr_state  # noqa: E402
from test_doc_lint import CASES, GUIDE, OPENCODE_SKILL, SKILL  # noqa: E402

PR_ID = "PR-TEST-001"
PR = """---
pr_type: errata
kb_version: 1.0 -> 1.0
guide_version: 1.0
evidence: [EV-TEST-abc12345]
changes:
  files: [docs/zh/x/指南.md]
human_decisions: []
review:
  verdict: changes_requested
  p0: 0
---
正文
"""


def make_ws(tmp: str) -> Path:
    ws = Path(tmp)
    contents = {
        "guide": GUIDE,
        "skill": SKILL,
        "opencode_skill": OPENCODE_SKILL,
        "cases": CASES,
        "rationale": CASES,
    }
    for key, text in contents.items():
        p = ws / doc_lint.DIMENSIONS["gcs"][key]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return ws


def write_pr(ws: Path, text: str = PR) -> Path:
    p = ws / "pr.md"
    p.write_text(text, encoding="utf-8")
    return p


def write_review(ws: Path, verdict: str, p0: int = 0,
                 comments=None, pr_id: str = PR_ID) -> Path:
    data = {
        "pr_id": pr_id,
        "reviewer": {"model": "kimi-k3", "provider": "opencode-go", "role": "reviewer"},
        "verdict": verdict,
        "p0": p0,
        "p1": 0 if comments is None else sum(1 for c in comments if c["severity"] == "P1"),
        "p2": 0,
        "comments": comments or [],
    }
    p = ws / "review.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def run(ws: Path, *args) -> int:
    buf = io.StringIO()
    with redirect_stdout(buf):
        return pr_state.main([*args, "--workspace", str(ws), "--pr-id", PR_ID])


def state(ws: Path) -> dict:
    return json.loads((ws / ".doc-pr" / PR_ID / "state.json").read_text(encoding="utf-8"))


class TestClosedLoop(unittest.TestCase):
    def test_happy_path_reaches_closed(self):
        with tempfile.TemporaryDirectory() as d:
            ws = make_ws(d)
            pr = write_pr(ws)

            self.assertEqual(run(ws, "start", "--pr-file", str(pr)), 0)

            # 未 selfcheck 不能 review
            rv = write_review(ws, "changes_requested", comments=[{
                "file": "docs/zh/x/指南.md", "line": 1, "severity": "P1",
                "evidence": "EV-TEST-abc12345", "message": "x"}])
            self.assertEqual(run(ws, "review", "--review", str(rv)), 2)

            self.assertEqual(run(ws, "selfcheck"), 0)
            self.assertEqual(run(ws, "review", "--review", str(rv)), 0)
            self.assertEqual(state(ws)["phase"], "changes_requested")

            self.assertEqual(run(ws, "revise", "--note", "按意见修订"), 0)
            self.assertEqual(run(ws, "selfcheck"), 0)

            rv2 = write_review(ws, "approved")
            self.assertEqual(run(ws, "review", "--review", str(rv2)), 0)
            self.assertEqual(state(ws)["phase"], "review_approved")

            # 未人工批准不能合并
            self.assertEqual(run(ws, "merge"), 2)

            self.assertEqual(run(ws, "signoff", "--decision", "HD-2026-11-12-01",
                                 "--by", "张三", "--what", "接受勘误"), 0)
            self.assertEqual(run(ws, "merge"), 0)
            self.assertEqual(state(ws)["phase"], "merged")
            self.assertTrue((ws / ".doc-pr" / PR_ID / "index_rebuild.json").exists())

            self.assertEqual(run(ws, "reeval"), 0)
            st = state(ws)
            self.assertEqual(st["phase"], "closed")
            self.assertEqual(st["iteration"], 2)

            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(pr_state.main(
                    ["status", "--workspace", str(ws), "--pr-id", PR_ID]), 0)
            self.assertIn("closed", buf.getvalue())

    def test_merge_blocked_by_gate_after_signoff(self):
        with tempfile.TemporaryDirectory() as d:
            ws = make_ws(d)
            pr = write_pr(ws)
            run(ws, "start", "--pr-file", str(pr))
            run(ws, "selfcheck")
            run(ws, "review", "--review", str(write_review(ws, "approved")))
            run(ws, "signoff", "--decision", "HD-1", "--by", "李四", "--what", "ok")

            guide = ws / doc_lint.DIMENSIONS["gcs"]["guide"]
            guide.write_text(GUIDE.replace("| 维度乙 | 40%", "| 维度乙 | 45%"),
                             encoding="utf-8")
            self.assertEqual(run(ws, "merge"), 1)
            self.assertEqual(state(ws)["phase"], "blocked")

    def test_iteration_cap_goes_to_human(self):
        with tempfile.TemporaryDirectory() as d:
            ws = make_ws(d)
            pr = write_pr(ws)
            run(ws, "start", "--pr-file", str(pr), "--max-iterations", "1")
            run(ws, "selfcheck")
            rv = write_review(ws, "changes_requested", comments=[{
                "file": "docs/zh/x/指南.md", "line": 1, "severity": "P1",
                "evidence": "EV-TEST-abc12345", "message": "x"}])
            self.assertEqual(run(ws, "review", "--review", str(rv)), 1)
            self.assertEqual(state(ws)["phase"], "needs_human")

    def test_review_pr_id_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            ws = make_ws(d)
            pr = write_pr(ws)
            run(ws, "start", "--pr-file", str(pr))
            run(ws, "selfcheck")
            rv = write_review(ws, "approved", pr_id="PR-OTHER")
            self.assertEqual(run(ws, "review", "--review", str(rv)), 1)
            self.assertEqual(state(ws)["phase"], "ready_for_review")


if __name__ == "__main__":
    unittest.main()
