#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""pr_state.py — 评估文档 PR 闭环状态机（Proposer → Reviewer → 人工 → CI → 合并 → 回评）。

状态目录：<workspace>/.doc-pr/<pr_id>/state.json
可用命令（除 status 外均会推进状态）：

  start      创建 PR 状态（校验 front-matter 契约）
  selfcheck  跑 doc_lint（G0/G1/G3）；有 ERROR 则停在 selfcheck_failed
  review     提交 Reviewer 报告（scripts/review_schema.json）；approved 需 p0=0
  revise     收到 changes_requested 后修订（回到 draft，需重新 selfcheck）
  signoff    人类批准（记录 HD 编号；权重/阈值/severity 变更必须走这一步）
  merge      Merger 动作：复核门禁后合并，并生成 index_rebuild.json
  reeval     合并后回评（《编制指南》1.8“修订后回评”）
  status     打印状态与时间线

状态流转：
  draft → ready_for_review → review_approved → signed_off → merged → closed
                ↑                    │
                │              changes_requested ── revise ──┘
                └── selfcheck_failed（修好后重新 selfcheck）
  任一轮 review 后仍未收敛（iteration ≥ max_iterations）→ needs_human（冻结）

退出码：0 = 成功；1 = 被门禁阻断；2 = 参数/状态错误。
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import doc_lint  # noqa: E402

STATE_DIRNAME = ".doc-pr"
DEFAULT_MAX_ITERATIONS = 3

PHASES = (
    "draft", "selfcheck_failed", "ready_for_review", "review_approved",
    "changes_requested", "signed_off", "merged", "closed",
    "needs_human", "blocked",
)


# --------------------------------------------------------------------------
# 状态读写
# --------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_dir(ws: Path, pr_id: str) -> Path:
    return ws / STATE_DIRNAME / pr_id


def state_file(ws: Path, pr_id: str) -> Path:
    return state_dir(ws, pr_id) / "state.json"


def load_state(ws: Path, pr_id: str) -> Dict[str, Any]:
    path = state_file(ws, pr_id)
    if not path.exists():
        raise SystemExit(f"PR 状态不存在：{path}（先执行 start）")
    st = json.loads(path.read_text(encoding="utf-8"))
    if Path(st["workspace"]).resolve() != ws.resolve():
        raise SystemExit(f"workspace 不一致：状态记录 {st['workspace']}，当前 {ws}")
    return st


def save_state(ws: Path, st: Dict[str, Any]) -> None:
    st["updated_at"] = _now()
    path = state_file(ws, st["pr_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(st, ensure_ascii=False, indent=2)
    tmp = path.with_suffix(".tmp")
    last: Optional[Exception] = None
    for _ in range(5):  # Windows：杀软/索引短暂占用新文件时 os.replace 可能 PermissionError
        try:
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(path)
            return
        except PermissionError as exc:  # pragma: no cover - 平台相关
            last = exc
            time.sleep(0.05)
    path.write_text(payload, encoding="utf-8")  # 兜底：直接写
    if last is not None:
        tmp.unlink(missing_ok=True)


def log(st: Dict[str, Any], action: str, result: str, detail: str = "") -> None:
    st["history"].append({
        "at": _now(), "action": action, "result": result,
        "phase": st["phase"], "detail": detail,
    })


def require_phase(st: Dict[str, Any], allowed: List[str], action: str) -> Optional[str]:
    if st["phase"] not in allowed:
        return (f"当前状态 {st['phase']} 不允许 {action}；"
                f"允许的状态：{', '.join(allowed)}")
    return None


# --------------------------------------------------------------------------
# 门禁
# --------------------------------------------------------------------------
def lint_workspace(ws: Path, dimension: str) -> doc_lint.Report:
    paths = doc_lint.dimension_paths(dimension, ws)
    return doc_lint.lint_paths(
        guide=paths["guide"],
        skill=paths.get("skill"),
        opencode_skill=paths.get("opencode_skill"),
        cases=paths.get("cases"),
        rationale=paths.get("rationale"),
    )


def _gate_result(rep: doc_lint.Report) -> Dict[str, Any]:
    return {"ok": not rep.has_error(), "summary": rep.summary(),
            "findings": rep.findings}


def _print_findings(rep: doc_lint.Report) -> None:
    doc_lint.print_report(rep, "gate", as_json=False)


def _index_digest(dimension: str, ws: Path) -> Dict[str, str]:
    paths = doc_lint.dimension_paths(dimension, ws)
    h = hashlib.sha256()
    files = {}
    for key, p in sorted(paths.items()):
        if not p.exists():
            continue
        data = p.read_bytes()
        files[key] = hashlib.sha256(data).hexdigest()
        h.update(key.encode())
        h.update(data)
    return {"kb_commit_sha256": h.hexdigest(), "files": files}


# --------------------------------------------------------------------------
# 命令实现
# --------------------------------------------------------------------------
def cmd_start(args: argparse.Namespace, ws: Path) -> int:
    if state_file(ws, args.pr_id).exists():
        print(f"PR 已存在：{state_file(ws, args.pr_id)}")
        return 2
    pr_file = Path(args.pr_file)
    if not pr_file.is_absolute():
        pr_file = ws / pr_file
    if not pr_file.exists():
        print(f"PR 文件不存在：{pr_file}")
        return 2
    rep = doc_lint.lint_pr_file(pr_file)
    if rep.has_error():
        _print_findings(rep)
        return 1
    fm = doc_lint.parse_front_matter(doc_lint.read_text(pr_file)) or {}
    changes = fm.get("changes") or {}
    risky = any(changes.get(k) for k in
                ("weights_changed", "thresholds_changed", "severity_changed"))
    st: Dict[str, Any] = {
        "pr_id": args.pr_id,
        "dimension": args.dimension,
        "workspace": str(ws.resolve()),
        "pr_file": str(pr_file),
        "phase": "draft",
        "iteration": 0,
        "max_iterations": args.max_iterations,
        "risky": risky,
        "started_at": _now(),
        "updated_at": _now(),
        "review": None,
        "human_decisions": [],
        "gates": {},
        "merged_at": None,
        "index": None,
        "history": [],
    }
    log(st, "start", "ok", f"dimension={args.dimension} risky={risky}")
    save_state(ws, st)
    print(f"PR {args.pr_id} 已创建：{state_file(ws, args.pr_id)}")
    print(f"  phase={st['phase']}  risky={st['risky']}  max_iterations={st['max_iterations']}")
    return 0


def cmd_selfcheck(args: argparse.Namespace, ws: Path) -> int:
    st = load_state(ws, args.pr_id)
    err = require_phase(st, ["draft", "selfcheck_failed"], "selfcheck")
    if err:
        print(err)
        return 2
    rep = lint_workspace(ws, st["dimension"])
    st["gates"]["selfcheck"] = _gate_result(rep)
    _print_findings(rep)
    if rep.has_error():
        st["phase"] = "selfcheck_failed"
        log(st, "selfcheck", "error", "G1/G3/G0 存在 ERROR")
        save_state(ws, st)
        return 1
    st["phase"] = "ready_for_review"
    log(st, "selfcheck", "ok", "0 error")
    save_state(ws, st)
    print("selfcheck 通过，进入 ready_for_review")
    return 0


def cmd_review(args: argparse.Namespace, ws: Path) -> int:
    st = load_state(ws, args.pr_id)
    err = require_phase(st, ["ready_for_review"], "review")
    if err:
        print(err)
        return 2
    review_path = Path(args.review)
    if not review_path.is_absolute():
        review_path = ws / review_path
    rep = doc_lint.lint_review_file(review_path)
    if rep.has_error():
        _print_findings(rep)
        return 1
    data = json.loads(doc_lint.read_text(review_path))
    if data.get("pr_id") != st["pr_id"]:
        print(f"review.pr_id={data.get('pr_id')} 与状态 {st['pr_id']} 不一致")
        return 1

    st["iteration"] += 1
    st["review"] = {
        "verdict": data["verdict"],
        "p0": data["p0"], "p1": data["p1"], "p2": data["p2"],
        "reviewer": data["reviewer"],
        "iteration": st["iteration"],
    }
    if data["verdict"] == "approved":
        st["phase"] = "review_approved"
        log(st, "review", "approved", f"iteration={st['iteration']}")
        save_state(ws, st)
        print(f"Review 通过（第 {st['iteration']} 轮）→ review_approved")
        return 0

    if st["iteration"] >= st["max_iterations"]:
        st["phase"] = "needs_human"
        log(st, "review", "changes_requested",
            f"达到迭代上限 {st['max_iterations']}，转人工")
        save_state(ws, st)
        print(f"第 {st['iteration']} 轮仍未收敛 → needs_human（冻结，禁止自动放行）")
        return 1

    st["phase"] = "changes_requested"
    log(st, "review", "changes_requested", f"iteration={st['iteration']}")
    save_state(ws, st)
    print(f"Review 要求修改（第 {st['iteration']}/{st['max_iterations']} 轮）→ changes_requested")
    return 0


def cmd_revise(args: argparse.Namespace, ws: Path) -> int:
    st = load_state(ws, args.pr_id)
    err = require_phase(st, ["changes_requested"], "revise")
    if err:
        print(err)
        return 2
    st["phase"] = "draft"
    log(st, "revise", "ok", args.note or "")
    save_state(ws, st)
    print("已接受修订，回到 draft（需重新 selfcheck）")
    return 0


def cmd_signoff(args: argparse.Namespace, ws: Path) -> int:
    st = load_state(ws, args.pr_id)
    err = require_phase(st, ["review_approved"], "signoff")
    if err:
        print(err)
        return 2
    st["human_decisions"].append({
        "id": args.decision, "by": args.by, "what": args.what, "at": _now(),
    })
    st["phase"] = "signed_off"
    log(st, "signoff", "ok", f"{args.decision} by {args.by}")
    save_state(ws, st)
    print(f"人工批准已登记：{args.decision}（{args.by}）")
    return 0


def cmd_merge(args: argparse.Namespace, ws: Path) -> int:
    st = load_state(ws, args.pr_id)
    err = require_phase(st, ["signed_off"], "merge")
    if err:
        print(err)
        return 2
    if st["risky"] and not st["human_decisions"]:
        print("权重/阈值/severity 变更缺少人工批准记录，禁止合并")
        return 1

    rep = lint_workspace(ws, st["dimension"])
    st["gates"]["pre_merge"] = _gate_result(rep)
    _print_findings(rep)
    if rep.has_error():
        st["phase"] = "blocked"
        log(st, "merge", "blocked", "pre-merge 门禁失败")
        save_state(ws, st)
        return 1

    st["phase"] = "merged"
    st["merged_at"] = _now()
    st["index"] = _index_digest(st["dimension"], ws)
    (state_dir(ws, st["pr_id"]) / "index_rebuild.json").write_text(
        json.dumps(st["index"], ensure_ascii=False, indent=2), encoding="utf-8")
    log(st, "merge", "ok", "gates 全绿，索引已从合并版本重建")
    save_state(ws, st)
    print(f"已合并。kb_commit_sha256={st['index']['kb_commit_sha256'][:16]}…")
    print("index_rebuild.json 已生成（索引为派生物）")
    return 0


def cmd_reeval(args: argparse.Namespace, ws: Path) -> int:
    st = load_state(ws, args.pr_id)
    err = require_phase(st, ["merged"], "reeval")
    if err:
        print(err)
        return 2
    rep = lint_workspace(ws, st["dimension"])
    st["gates"]["reeval"] = _gate_result(rep)
    _print_findings(rep)
    if rep.has_error():
        st["phase"] = "reeval_failed"
        log(st, "reeval", "error", "修订后回评发现新问题，建议开勘误 PR")
        save_state(ws, st)
        return 1
    st["phase"] = "closed"
    log(st, "reeval", "ok", "回评通过")
    save_state(ws, st)
    print("回评通过 → closed")
    return 0


def cmd_status(args: argparse.Namespace, ws: Path) -> int:
    st = load_state(ws, args.pr_id)
    print(f"PR {st['pr_id']}  dimension={st['dimension']}  phase={st['phase']}")
    print(f"  iteration={st['iteration']}/{st['max_iterations']}  risky={st['risky']}")
    if st.get("review"):
        r = st["review"]
        print(f"  review#{r['iteration']}: {r['verdict']}  "
              f"P0={r['p0']} P1={r['p1']} P2={r['p2']}  reviewer={r['reviewer']['model']}")
    for d in st["human_decisions"]:
        print(f"  decision {d['id']} by {d['by']}: {d['what']}")
    print("  timeline:")
    for h in st["history"]:
        print(f"    {h['at'][11:19]}  {h['action']:<10} {h['result']:<16} {h['detail']}")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="评估文档 PR 闭环状态机")
    ap.add_argument("command", choices=[
        "start", "selfcheck", "review", "revise", "signoff",
        "merge", "reeval", "status"])
    ap.add_argument("--pr-id", required=True)
    ap.add_argument("--dimension", default="gcs")
    ap.add_argument("--workspace", default=str(ROOT))
    ap.add_argument("--pr-file", default=None)
    ap.add_argument("--review", default=None)
    ap.add_argument("--note", default="")
    ap.add_argument("--decision", default=None)
    ap.add_argument("--by", default=None)
    ap.add_argument("--what", default="")
    ap.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    ws = Path(args.workspace).resolve()

    if args.command == "start" and not args.pr_file:
        print("start 需要 --pr-file")
        return 2
    if args.command == "review" and not args.review:
        print("review 需要 --review <json>")
        return 2
    if args.command == "signoff" and not (args.decision and args.by):
        print("signoff 需要 --decision <HD-id> --by <人名>")
        return 2

    handlers = {
        "start": cmd_start, "selfcheck": cmd_selfcheck, "review": cmd_review,
        "revise": cmd_revise, "signoff": cmd_signoff, "merge": cmd_merge,
        "reeval": cmd_reeval, "status": cmd_status,
    }
    return handlers[args.command](args, ws)


if __name__ == "__main__":
    sys.exit(main())
