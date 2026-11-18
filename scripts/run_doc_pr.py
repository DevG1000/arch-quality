#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_doc_pr.py — 用真实 Agent 跑通评估文档 PR 闭环。

流程：Proposer（可选）→ selfcheck → Reviewer Agent → pr_state.review
      →（changes_requested 时带反馈回到 Proposer，最多 max_iterations 轮）
      →（可选）人工批准 → merge → reeval

用法：
  # 只审已有 PR（不跑 Proposer）
  python scripts/run_doc_pr.py --pr-id PR-1 --workspace <ws> \
      --pr-file docs/zh/.../pr-errata-version.md --skip-proposer \
      --human-decision HD-2026-11-13-01 --by 张三 --what "接受勘误"

  # 让 Proposer 先产出/修订
  python scripts/run_doc_pr.py --pr-id PR-1 --workspace <ws> --task "<任务描述>"

前置：workspace 内需有 scripts/{doc_lint,pr_state}.py、docs 文档包、
      .opencode/agents/{assessment-proposer,assessment-reviewer}.md。
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "opencode-go/deepseek-v4.1-flash"


def log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")


def run_cmd(args: List[str], cwd: Path, timeout: int = 900) -> Tuple[int, str, str]:
    proc = subprocess.run(args, cwd=str(cwd), capture_output=True, timeout=timeout)
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


def run_agent(ws: Path, agent: str, model: str, prompt: str,
              timeout: int = 900) -> Tuple[int, str]:
    code, out, err = run_cmd(
        ["opencode", "run", "--dir", str(ws), "--agent", agent, "-m", model, prompt],
        cwd=ws, timeout=timeout)
    if err.strip():
        out = out + "\n[stderr]\n" + err
    return code, out


def extract_json(text: str, must_have: str = "verdict") -> Optional[Dict[str, Any]]:
    decoder = json.JSONDecoder()
    pos = text.rfind("{")
    while pos != -1:
        try:
            cand, _ = decoder.raw_decode(text[pos:])
            if isinstance(cand, dict) and must_have in cand:
                return cand
        except json.JSONDecodeError:
            pass
        pos = text.rfind("{", 0, pos)
    return None


def pr_state(ws: Path, *args: str) -> Tuple[int, str]:
    code, out, err = run_cmd(
        [sys.executable, str(ws / "scripts" / "pr_state.py"), *args, "--workspace", str(ws)],
        cwd=ws)
    return code, (out + ("\n" + err if err.strip() else ""))


def review_prompt(ws: Path, pr_file: str, pr_id: str, dimension: str) -> str:
    return (
        f"审核任务：PR {pr_id}（dimension={dimension}）。\n"
        f"PR 文件：{pr_file}（含 front-matter 与变更说明）。\n"
        "工作区就是当前目录；请用 read/glob/grep 读取 PR 文件与 changes.files 列出的文件。"
        "工作区里其他未提交修改与本次 PR 无关（例如预先存在的无关文件），不要评论。"
        f"并运行 `python scripts/doc_lint.py --dimension {dimension}` 复核机器门禁。\n"
        "按 .opencode/agents/assessment-reviewer.md 的检查清单独立审核：证据是否支持新断言、"
        "是否丢限定条件、跨文档口径是否一致、是否有过度修改、关键决策是否有人类批准。\n"
        f"只输出一个符合 scripts/review_schema.json 的 JSON 对象（pr_id 用 {pr_id}）；"
        "changes_requested 必须至少 1 条 comment，没有问题就判 approved；"
        "不要 markdown 围栏，不要解释。"
    )


def proposer_prompt(task: str, feedback: Optional[str]) -> str:
    base = task.strip()
    if feedback:
        base += ("\n\n上一轮 Reviewer 的意见（请逐条处理，仍只做最小改动）：\n" + feedback)
    return base


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Agent 驱动的评估文档 PR 闭环")
    ap.add_argument("--pr-id", required=True)
    ap.add_argument("--workspace", type=Path, default=REPO_ROOT)
    ap.add_argument("--dimension", default="gcs")
    ap.add_argument("--pr-file", default=None, help="相对 workspace 的 PR 文件路径")
    ap.add_argument("--task", default=None, help="Proposer 任务描述（不填则跳过 Proposer）")
    ap.add_argument("--skip-proposer", action="store_true")
    ap.add_argument("--proposer-model", default=DEFAULT_MODEL)
    ap.add_argument("--reviewer-model", default=DEFAULT_MODEL)
    ap.add_argument("--max-iterations", type=int, default=3)
    ap.add_argument("--human-decision", default=None)
    ap.add_argument("--by", default=None)
    ap.add_argument("--what", default="")
    args = ap.parse_args(argv)

    ws = args.workspace.resolve()
    state_dir = ws / ".doc-pr" / args.pr_id
    run_log = state_dir / "run.log"
    if state_dir.exists():
        import shutil
        shutil.rmtree(state_dir, ignore_errors=True)

    def step(name: str, code: int, output: str = "") -> bool:
        log(run_log, f"\n===== {name} (exit={code}) =====\n{output}")
        print(f"[{name}] exit={code}")
        if output.strip():
            print(output.strip()[:1500])
        return code == 0

    # 1) Proposer（可选）
    if not args.skip_proposer and args.task:
        code, out = run_agent(ws, "assessment-proposer", args.proposer_model,
                              proposer_prompt(args.task, None))
        step("proposer", code, out)
        if code != 0:
            return 1
        if not args.pr_file:
            print("Proposer 完成后请用 --pr-file 指定 PR 文件")
            return 2

    if not args.pr_file:
        print("需要 --pr-file（或提供 --task 让 Proposer 产出后指定）")
        return 2

    # 2) start + selfcheck
    if not step("start", *pr_state(ws, "start", "--pr-id", args.pr_id,
                                   "--dimension", args.dimension,
                                   "--pr-file", args.pr_file,
                                   "--max-iterations", str(args.max_iterations))):
        return 1
    if not step("selfcheck", *pr_state(ws, "selfcheck", "--pr-id", args.pr_id)):
        return 1

    # 3) Reviewer 循环
    feedback: Optional[str] = None
    approved = False
    for attempt in range(1, args.max_iterations + 1):
        code, out = run_agent(ws, "assessment-reviewer", args.reviewer_model,
                              review_prompt(ws, args.pr_file, args.pr_id, args.dimension))
        log(run_log, f"\n===== reviewer#{attempt} (exit={code}) =====\n{out}")
        obj = extract_json(out)
        if not obj:
            print(f"[reviewer#{attempt}] 未解析出 review JSON")
            return 1
        obj["pr_id"] = args.pr_id
        obj.setdefault("reviewer", {})
        obj["reviewer"].update({"model": args.reviewer_model.split("/")[-1],
                                "provider": args.reviewer_model.split("/")[0],
                                "role": "reviewer"})
        review_path = state_dir / f"review_{attempt}.json"
        review_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[reviewer#{attempt}] verdict={obj.get('verdict')} "
              f"P0={obj.get('p0')} P1={obj.get('p1')} P2={obj.get('p2')}")
        if not step(f"review#{attempt}", *pr_state(
                ws, "review", "--pr-id", args.pr_id, "--review", str(review_path))):
            return 1
        if obj.get("verdict") == "approved":
            approved = True
            break
        feedback = json.dumps(obj.get("comments") or [], ensure_ascii=False, indent=2)
        if attempt >= args.max_iterations:
            break
        if args.skip_proposer or not args.task:
            print("changes_requested，但未提供 --task，无法自动修订；停在 changes_requested")
            return 1
        step("revise", *pr_state(ws, "revise", "--pr-id", args.pr_id, "--note", "按 review 修订"))
        code, out = run_agent(ws, "assessment-proposer", args.proposer_model,
                              proposer_prompt(args.task, feedback))
        step(f"proposer-revise#{attempt}", code, out)
        if code != 0:
            return 1
        if not step(f"selfcheck#{attempt + 1}",
                    *pr_state(ws, "selfcheck", "--pr-id", args.pr_id)):
            return 1

    if not approved:
        print("未在迭代上限内收敛，状态见 pr_state status")
        return 1

    # 4) 人工批准 + 合并 + 回评（可选）
    if not args.human_decision:
        print("\nReview 已通过，等待人工批准。下一步：")
        print(f"  python scripts/pr_state.py signoff --pr-id {args.pr_id} "
              f"--decision <HD-id> --by <name> --what \"...\" --workspace {ws}")
        print(f"  python scripts/pr_state.py merge   --pr-id {args.pr_id} --workspace {ws}")
        print(f"  python scripts/pr_state.py reeval  --pr-id {args.pr_id} --workspace {ws}")
        return 0
    if not args.by:
        print("--human-decision 需要同时提供 --by")
        return 2

    if not step("signoff", *pr_state(ws, "signoff", "--pr-id", args.pr_id,
                                     "--decision", args.human_decision,
                                     "--by", args.by, "--what", args.what)):
        return 1
    if not step("merge", *pr_state(ws, "merge", "--pr-id", args.pr_id)):
        return 1
    if not step("reeval", *pr_state(ws, "reeval", "--pr-id", args.pr_id)):
        return 1
    code, out = pr_state(ws, "status", "--pr-id", args.pr_id)
    print(out)
    return code


if __name__ == "__main__":
    sys.exit(main())
