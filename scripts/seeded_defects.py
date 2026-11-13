#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""seeded_defects.py — 植入缺陷回归集：测“门禁/Reviewer 能不能抓到已知坏改动”。

每个案例 = 冻结基线（opencode-harness/seeded/baseline，a3168bb）+ 一处已知缺陷。分两类：
  machine  : doc_lint 应当抓到（用于回归 G0/G1/G3 的召回）
  control  : 干净对照，门禁与 Reviewer 都应放行（测误报）
  semantic : doc_lint 抓不到，必须由 Reviewer Agent 依据证据判断
             （harness 会生成 review_task.json，供 Reviewer 审核）

用法：
  python scripts/seeded_defects.py --list
  python scripts/seeded_defects.py run  [--out .arch-reports/seeded-defects] [--only M1,S1]
  python scripts/seeded_defects.py emit --id S1 [--out ...]
  python scripts/seeded_defects.py grade --id S1 --review review.json [--out ...]

输出（默认 .arch-reports/seeded-defects/，已被 gitignore）：
  <out>/<ID>/workspace/       植入缺陷后的文档副本
  <out>/<ID>/ground_truth.json  期望（仅评分用，不给 Reviewer）
  <out>/<ID>/ground_truth_diff.patch
  <out>/<ID>/review_task.json   semantic 案例的审核任务（给 Reviewer）
  <out>/summary.json

退出码：0 = 全部 machine 案例被抓到；1 = 有漏检/变异失效；2 = 参数错误。
"""

import argparse
import difflib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import doc_lint  # noqa: E402

DIMENSION = "gcs"
BASELINE_DIR = ROOT / "opencode-harness" / "seeded" / "baseline"
BASELINE_MANIFEST = BASELINE_DIR / "manifest.json"
DEFAULT_OUT = ROOT / ".arch-reports" / "seeded-defects"
SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2}


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------
def _read(p: Path) -> str:
    for _ in range(5):  # Windows：杀软/索引偶发占用
        try:
            return p.read_text(encoding="utf-8-sig")
        except PermissionError:
            time.sleep(0.05)
    return p.read_text(encoding="utf-8-sig")


def _write(p: Path, text: str) -> None:
    for _ in range(5):
        try:
            p.write_text(text, encoding="utf-8-sig")
            return
        except PermissionError:
            time.sleep(0.05)
    p.write_text(text, encoding="utf-8-sig")


def _line_of(text: str, marker: str) -> int:
    idx = text.find(marker)
    if idx < 0:
        raise AssertionError(f"marker not found after mutation: {marker!r}")
    return text[:idx].count("\n") + 1


def _replace(p: Path, old: str, new: str, marker: Optional[str] = None) -> Dict[str, Any]:
    t = _read(p)
    assert t.count(old) == 1, f"anchor not unique in {p.name}: {t.count(old)}"
    t = t.replace(old, new)
    _write(p, t)
    return {"file": p, "line": _line_of(t, marker or new or old), "detail": f"replace {old[:40]!r}"}


def _replace_all(p: Path, old: str, new: str) -> Dict[str, Any]:
    t = _read(p)
    assert t.count(old) >= 1, f"anchor not found in {p.name}: {old!r}"
    first = _line_of(t, old)
    _write(p, t.replace(old, new))
    return {"file": p, "line": first, "detail": f"replace_all {old[:40]!r}"}


def _remove_line(p: Path, line_text: str) -> Dict[str, Any]:
    t = _read(p)
    assert t.count(line_text) == 1, f"line anchor not unique in {p.name}: {t.count(line_text)}"
    idx = t.find(line_text)
    line = t[:idx].count("\n") + 1
    t = t.replace(line_text, "", 1)
    if not line_text.endswith("\n"):
        t = t.replace("\n\n\n", "\n\n", 1)
    _write(p, t)
    return {"file": p, "line": line, "detail": f"remove line {line}"}


def _append(p: Path, text: str) -> Dict[str, Any]:
    t = _read(p)
    if not t.endswith("\n"):
        t += "\n"
    t += text
    _write(p, t)
    return {"file": p, "line": _line_of(t, text.strip()), "detail": "append"}


def _insert_before(p: Path, anchor: str, text: str) -> Dict[str, Any]:
    t = _read(p)
    assert t.count(anchor) == 1, f"anchor not unique in {p.name}"
    t = t.replace(anchor, text + anchor, 1)
    _write(p, t)
    return {"file": p, "line": _line_of(t, text.strip()), "detail": "insert"}


def paths_of(ws: Path) -> Dict[str, Path]:
    return {k: ws / rel for k, rel in doc_lint.DIMENSIONS[DIMENSION].items()}


# --------------------------------------------------------------------------
# 缺陷定义
# --------------------------------------------------------------------------
def m1_weight_sum(ws: Path) -> Dict[str, Any]:
    return _replace(paths_of(ws)["guide"],
                    "| 数据表示与访问规范性 | 25% | GCS-010~012 | 中 |",
                    "| 数据表示与访问规范性 | 30% | GCS-010~012 | 中 |")


def m2_weight_cross(ws: Path) -> Dict[str, Any]:
    p = paths_of(ws)["skill"]
    _replace(p, "| 几何内核数据一致性 | 30% | §2.1 |",
             "| 几何内核数据一致性 | 35% | §2.1 |")
    return _replace(p, "| 内核精度/单位一致性 | 20% | §2.2 |",
                    "| 内核精度/单位一致性 | 15% | §2.2 |")


def m3_low_conf_error(ws: Path) -> Dict[str, Any]:
    return _replace(paths_of(ws)["guide"],
                    "| GCS-005 | 硬编码精度/容差魔法数字 | LOW | INFO | 低 | 2.2 |",
                    "| GCS-005 | 硬编码精度/容差魔法数字 | HIGH | ERROR | 低 | 2.2 |")


def m4_severity_cross(ws: Path) -> Dict[str, Any]:
    return _replace(paths_of(ws)["skill"],
                    "| GCS-002 | Handle 智能指针一致性 | MEDIUM | WARNING | 中 | 2.1 |",
                    "| GCS-002 | Handle 智能指针一致性 | HIGH | WARNING | 中 | 2.1 |")


def m5_missing_detail(ws: Path) -> Dict[str, Any]:
    return _remove_line(paths_of(ws)["guide"], "#### GCS-009：网格/场量维度匹配\n")


def m6_broken_link(ws: Path) -> Dict[str, Any]:
    return _append(paths_of(ws)["guide"], "\n[缺失的案例](missing_case.md)\n")


def m7_rule_gap(ws: Path) -> Dict[str, Any]:
    return _remove_line(paths_of(ws)["guide"],
                        "| GCS-011 | 深拷贝 vs 浅拷贝 | LOW | INFO | 低 | 2.4 |\n")


def s1_unsupported_claim(ws: Path) -> Dict[str, Any]:
    return _insert_before(
        paths_of(ws)["guide"], "## 六、",
        "**补充论断**：本维度实测表明 OCCT 的数据访问无需额外封装，直接成员访问不会影响一致性。\n\n")


def s2_drop_exemption(ws: Path) -> Dict[str, Any]:
    return _remove_line(
        paths_of(ws)["guide"],
        "  4. **跨格式转换适配器豁免**：显式转换函数（输入/输出分属不同网格格式，如 VTK→OpenFOAM 转换器）不触发，归维度⑧ ACL 防腐 / MPR-012 格式转换统一性\n")


def s3_false_coverage(ws: Path) -> Dict[str, Any]:
    return _replace(paths_of(ws)["cases"],
                    "| GCS-007 | | | | ✅(4.2) | ✅(4.2) | |",
                    "| GCS-007 | ✅(occt) | | | ✅(4.2) | ✅(4.2) | |")


def s4_heuristic_error_rule(ws: Path) -> Dict[str, Any]:
    return _replace(paths_of(ws)["guide"],
                    "**检测逻辑**（窄化，对齐 AI 专家自评第二轮 C-3）：",
                    "**检测逻辑**（语义启发式推断，依赖大模型判断）：")


def n1_format_only(ws: Path) -> Dict[str, Any]:
    """纯格式对照：只多一个空行，无任何语义变化；任何 P0/P1 都是误报。"""
    return _replace(paths_of(ws)["guide"], "\n## 版本历史", "\n\n## 版本历史")


def n0_clean(ws: Path) -> Dict[str, Any]:
    """干净对照：把整个文档包对齐到版本历史中的真实最新版 1.8（勘误 PR）。"""
    p = paths_of(ws)
    # 指南：标题/头部版本与文末声明 → 1.8（版本历史已列到 1.8）
    _replace(p["guide"], "评估指南（1.6版）", "评估指南（1.8版）")
    _replace(p["guide"],
             "**版本**：1.6（子维度章节补全，对齐求解器物理场指南结构）",
             "**版本**：1.8（版本号与文档包绑定统一；1.6-1.8 变更见版本历史）")
    _replace(p["guide"], "1.7 版待第二轮专家校对定稿", "1.8 版待复核定稿")
    _replace(p["guide"], "编制指南 1.7", "编制指南 1.8")
    # 案例集：绑定 1.8 + 编制指南 1.8
    _replace(p["cases"], "指南（1.5版）", "指南（1.8版）")
    _replace(p["cases"], "编制指南 1.7", "编制指南 1.8")
    # 设计依据：绑定 1.8 + 编制指南 1.8
    _replace(p["rationale"], "指南（1.2版）", "指南（1.8版）")
    _replace(p["rationale"], "编制指南 1.7", "编制指南 1.8")
    # 两份 Skill 的版本绑定
    _replace(p["skill"], "指南》**1.6 版**", "指南》**1.8 版**")
    _replace(p["skill"],
             '（`SKILL_VERSION = "1.0"`，对齐指南 1.6）',
             '（`SKILL_VERSION = "1.0"`，对齐指南 1.8）')
    _replace(p["skill"],
             "| 《几何内核与科学数据结构一致性评估指南》 | 1.6 |",
             "| 《几何内核与科学数据结构一致性评估指南》 | 1.8 |")
    return _replace(p["opencode_skill"], "指南版本：1.6", "指南版本：1.8")


DEFECTS: List[Dict[str, Any]] = [
    {"id": "M1", "kind": "machine", "title": "权重和 ≠ 100%（25→30）",
     "apply": m1_weight_sum, "expect": ["G1-sum"]},
    {"id": "M2", "kind": "machine", "title": "跨文档权重不一致（30/20 ↔ 35/15，和仍为 100）",
     "apply": m2_weight_cross, "expect": ["G1-cross"]},
    {"id": "M3", "kind": "machine", "title": "低置信度规则被设为 ERROR",
     "apply": m3_low_conf_error, "expect": ["G3-low-conf-error"]},
    {"id": "M4", "kind": "machine", "title": "Guide/Skill severity 口径不一致",
     "apply": m4_severity_cross, "expect": ["G3-cross"]},
    {"id": "M5", "kind": "machine", "title": "规则缺详情小节",
     "apply": m5_missing_detail, "expect": ["G0-rule-detail"]},
    {"id": "M6", "kind": "machine", "title": "相对链接失效",
     "apply": m6_broken_link, "expect": ["G0-link"]},
    {"id": "M7", "kind": "machine", "title": "规则编号不连续（删掉 GCS-011 行）",
     "apply": m7_rule_gap, "expect": ["G0-rule-gap"]},
    {"id": "S1", "kind": "semantic", "title": "新增无证据断言（“无需封装”）",
     "apply": s1_unsupported_claim, "expect": [],
     "review": {"file": "guide", "min_severity": "P1",
                "keywords": ["证据", "实测", "EV-"]}},
    {"id": "S2", "kind": "semantic", "title": "删除跨格式转换豁免（过度改写）",
     "apply": s2_drop_exemption, "expect": [],
     "review": {"file": "guide", "min_severity": "P1",
                "keywords": ["豁免", "转换", "误报"]}},
    {"id": "S3", "kind": "semantic", "title": "覆盖矩阵虚报 A 类（与覆盖说明矛盾）",
     "apply": s3_false_coverage, "expect": [],
     "review": {"file": "cases", "min_severity": "P1",
                "keywords": ["覆盖", "矩阵", "A 类", "矛盾"]}},
    {"id": "S4", "kind": "semantic", "title": "ERROR 级规则改为语义启发式检测",
     "apply": s4_heuristic_error_rule, "expect": [],
     "review": {"file": "guide", "min_severity": "P1",
                "keywords": ["启发式", "误报", "ERROR", "降级"]}},
    {"id": "N0", "kind": "control", "title": "勘误对照（文档包版本对齐 1.8）",
     "apply": n0_clean, "expect": [],
     "review": {"file": "guide", "min_severity": "P2", "keywords": []}},
    {"id": "N1", "kind": "control", "title": "纯格式对照（仅多一个空行，零语义变化）",
     "apply": n1_format_only, "expect": [],
     "review": {"file": "guide", "min_severity": "P2", "keywords": []}},
]


# --------------------------------------------------------------------------
# 运行
# --------------------------------------------------------------------------
def baseline_manifest() -> Dict[str, Any]:
    return json.loads(BASELINE_MANIFEST.read_text(encoding="utf-8"))


def build_baseline(ws: Path) -> None:
    """从冻结基线（opencode-harness/seeded/baseline）复制，避免仓库文档变动导致变异失效。"""
    manifest = baseline_manifest()
    for key, rel in doc_lint.DIMENSIONS[DIMENSION].items():
        src = BASELINE_DIR / manifest["files"][key]["file"]
        dst = ws / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def lint_ws(ws: Path) -> doc_lint.Report:
    p = paths_of(ws)
    return doc_lint.lint_paths(guide=p["guide"], skill=p.get("skill"),
                               opencode_skill=p.get("opencode_skill"),
                               cases=p.get("cases"), rationale=p.get("rationale"))


def _diff_for(defect_id: str, ws: Path) -> str:
    chunks = []
    for key, rel in doc_lint.DIMENSIONS[DIMENSION].items():
        base = ROOT / rel
        cur = ws / rel
        if not base.exists() or not cur.exists():
            continue
        a = base.read_text(encoding="utf-8-sig").splitlines()
        b = cur.read_text(encoding="utf-8-sig").splitlines()
        d = difflib.unified_diff(a, b, fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm="")
        text = "\n".join(d)
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def run_case(defect: Dict[str, Any], out: Path) -> Dict[str, Any]:
    case_dir = out / defect["id"]
    if case_dir.exists():
        shutil.rmtree(case_dir, ignore_errors=True)
    ws = case_dir / "workspace"
    build_baseline(ws)
    change = defect["apply"](ws)
    rep = lint_ws(ws)
    codes = sorted({f["code"] for f in rep.findings if f["level"] in ("ERROR", "WARNING")})
    errors = [f for f in rep.findings if f["level"] == "ERROR"]

    result: Dict[str, Any] = {
        "id": defect["id"], "kind": defect["kind"], "title": defect["title"],
        "changed_file": str(change["file"].relative_to(ws)).replace("\\", "/"),
        "changed_line": change["line"],
        "detected_codes": codes,
        "machine_error_count": len(errors),
        "expected_codes": defect["expect"],
        "caught": None,
    }
    if defect["kind"] == "machine":
        result["caught"] = all(c in codes for c in defect["expect"])
    elif defect["kind"] == "control":
        result["caught"] = None  # 对照：不算召回，单独看是否 0 error/0 warning
    else:
        result["caught"] = False  # semantic：机器门禁不应抓到（下一步断言无 ERROR）

    gt: Dict[str, Any] = {
        "id": defect["id"], "kind": defect["kind"], "title": defect["title"],
        "baseline_commit": baseline_manifest()["baseline_commit"],
        "expected_codes": defect["expect"],
        "changed_file": result["changed_file"],
        "changed_line": change["line"],
        "detail": change["detail"],
    }
    if defect["kind"] in ("semantic", "control"):
        gt["review_expect"] = {
            "file": str(paths_of(ws)[defect["review"]["file"]].relative_to(ws)).replace("\\", "/"),
            "line": change["line"],
            "min_severity": defect["review"]["min_severity"],
            "keywords": defect["review"]["keywords"],
            "must_verdict": "approved" if defect["kind"] == "control" else "changes_requested",
        }
        (case_dir / "review_task.json").write_text(json.dumps({
            "defect_id": defect["id"],
            "dimension": DIMENSION,
            "workspace": str(ws),
            "changed_files": [result["changed_file"]],
            "diff": _diff_for(defect["id"], ws),
            "instructions": (
                "按 .opencode/agents/assessment-reviewer.md 的检查清单独立审核；"
                "只依据工作区文档与证据，输出符合 scripts/review_schema.json 的 JSON。"
            ),
            "review_schema": "scripts/review_schema.json",
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    (case_dir / "ground_truth.json").write_text(
        json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
    (case_dir / "ground_truth_diff.patch").write_text(
        _diff_for(defect["id"], ws), encoding="utf-8")
    return result


def run(out: Path, only: Optional[List[str]] = None) -> Dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    selected = [d for d in DEFECTS if not only or d["id"] in only]
    results = [run_case(d, out) for d in selected]

    machine = [r for r in results if r["kind"] == "machine"]
    semantic = [r for r in results if r["kind"] == "semantic"]
    caught = sum(1 for r in machine if r["caught"])
    semantic_clean = sum(1 for r in semantic if r["machine_error_count"] == 0)
    control = [r for r in results if r["kind"] == "control"]
    control_ok = sum(1 for r in control if r["machine_error_count"] == 0)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dimension": DIMENSION,
        "baseline_commit": baseline_manifest()["baseline_commit"],
        "machine_total": len(machine),
        "machine_caught": caught,
        "machine_recall": round(caught / len(machine), 3) if machine else None,
        "semantic_total": len(semantic),
        "semantic_missed_by_machine": semantic_clean,
        "control_total": len(control),
        "control_ok": control_ok,
        "cases": results,
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def print_summary(s: Dict[str, Any]) -> None:
    print(f"seeded defects  dimension={s['dimension']}  baseline={s['baseline_commit'][:10]}")
    print(f"  {'ID':<3} {'kind':<8} {'caught':<7} detected_codes")
    for r in s["cases"]:
        if r["kind"] == "control":
            flag = "OK" if r["machine_error_count"] == 0 else "DIRTY"
        else:
            flag = "YES" if r["caught"] else ("--" if r["kind"] == "semantic" else "NO ")
        print(f"  {r['id']:<3} {r['kind']:<8} {flag:<7} {', '.join(r['detected_codes']) or '(none)'}")
    print(f"  machine recall: {s['machine_caught']}/{s['machine_total']}"
          f" = {s['machine_recall']}")
    print(f"  semantic cases not visible to machine gates: "
          f"{s['semantic_missed_by_machine']}/{s['semantic_total']}")
    if s.get("control_total"):
        print(f"  controls with 0 machine error: {s['control_ok']}/{s['control_total']}")


# --------------------------------------------------------------------------
# 评分（Reviewer 召回）
# --------------------------------------------------------------------------
def grade(case_dir: Path, review_path: Path) -> Dict[str, Any]:
    gt = json.loads((case_dir / "ground_truth.json").read_text(encoding="utf-8"))
    exp = gt.get("review_expect")
    if not exp:
        return {"ok": False, "reason": "该案例不是 semantic 类，无需 Reviewer 评分"}
    data = json.loads(review_path.read_text(encoding="utf-8"))
    reasons: List[str] = []
    if gt["kind"] == "control":
        p0 = data.get("p0", 0)
        p1 = data.get("p1", 0)
        # 干净对照允许 P2 风格建议，但不得出现 P0/P1（误报阻断）
        verdict_ok = p0 == 0 and p1 == 0
        if not verdict_ok:
            reasons.append(f"干净对照不得出现 P0/P1，实际 P0={p0} P1={p1}")
        return {"ok": verdict_ok, "verdict_ok": verdict_ok, "detected": None,
                "localized": None, "hits": [], "reasons": reasons, "defect_id": gt["id"]}

    verdict_ok = data.get("verdict") == exp["must_verdict"]
    if not verdict_ok:
        reasons.append(f"verdict={data.get('verdict')}，期望 {exp['must_verdict']}（存在缺陷不得批准）")
    exp_base = Path(exp["file"]).name
    hits = []
    detected = False
    localized = False
    for c in data.get("comments", []):
        text = (c.get("message", "") + " " + c.get("suggestion", "")).lower()
        kw_ok = any(k.lower() in text for k in exp["keywords"])
        got_base = Path(c.get("file", "")).name
        # 容忍长中文文件名的缩写（如漏掉“一致性”），但拒绝“指南.md”这类泛化名
        file_ok = (got_base == exp_base
                   or difflib.SequenceMatcher(None, got_base, exp_base).ratio() >= 0.8)
        try:
            line_ok = abs(int(c.get("line", 0)) - int(exp["line"])) <= 5
        except (TypeError, ValueError):
            line_ok = False
        sev_ok = SEVERITY_RANK.get(c.get("severity"), 9) <= SEVERITY_RANK[exp["min_severity"]]
        if kw_ok:
            detected = True
        if kw_ok and file_ok and line_ok and sev_ok:
            localized = True
            hits.append(c)
    if not detected:
        reasons.append(f"未检出缺陷（关键词 {exp['keywords']} 未出现在任何意见中）")
    elif not localized:
        reasons.append(
            f"检出但定位不符（要求 {exp['file']}:{exp['line']}±5、severity ≤ {exp['min_severity']}）")
    ok = verdict_ok and localized
    return {"ok": ok, "verdict_ok": verdict_ok, "detected": detected,
            "localized": localized, "hits": hits, "reasons": reasons, "defect_id": gt["id"]}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="植入缺陷回归集（machine/semantic）")
    ap.add_argument("command", nargs="?", default="run",
                    choices=["run", "list", "emit", "grade"])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--only", default=None, help="逗号分隔的案例 ID")
    ap.add_argument("--id", default=None)
    ap.add_argument("--review", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", action="store_true", dest="list_flag",
                    help="列出全部植入缺陷（等价于 list 子命令）")
    args = ap.parse_args(argv)
    if args.list_flag:
        args.command = "list"

    if args.command == "list":
        for d in DEFECTS:
            print(f"{d['id']:<3} {d['kind']:<8} {d['title']}")
        return 0

    if args.command in ("run", "emit"):
        only = [x.strip() for x in args.only.split(",")] if args.only else None
        if args.command == "emit":
            if not args.id:
                print("emit 需要 --id")
                return 2
            only = [args.id]
        try:
            s = run(args.out, only)
        except AssertionError as exc:
            print(f"变异失效（文档锚点已变化）：{exc}")
            return 1
        if args.json:
            print(json.dumps(s, ensure_ascii=False, indent=2))
        else:
            print_summary(s)
        if args.command == "emit" and args.id:
            case = args.out / args.id
            print(f"review_task: {case / 'review_task.json'}")
            print(f"workspace:   {case / 'workspace'}")
        ok = (s["machine_caught"] == s["machine_total"]
              and s["semantic_missed_by_machine"] == s["semantic_total"]
              and s["control_ok"] == s["control_total"])
        return 0 if ok else 1

    if args.command == "grade":
        if not (args.id and args.review):
            print("grade 需要 --id 与 --review")
            return 2
        res = grade(args.out / args.id, args.review)
        print(f"[{'PASS' if res['ok'] else 'FAIL'}] {args.id}")
        for r in res.get("reasons", []):
            print(f"  - {r}")
        return 0 if res["ok"] else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
