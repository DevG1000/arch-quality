#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""compare_reviewers.py — 用 seeded-defect 集对比 Reviewer 模型（OpenCode Go 网关）。

前置：python scripts/seeded_defects.py run
用法：
  python scripts/compare_reviewers.py --model kimi-k3
  python scripts/compare_reviewers.py --model deepseek-v4.1-flash
  python scripts/compare_reviewers.py --model kimi-k3 --tasks S1,S3 --effort low
  python scripts/compare_reviewers.py --model kimi-k3 --tasks N0 --tag retry

输出：.arch-reports/seeded-defects/comparison_<model>[_<effort>][_<tag>].json
凭据：~/.local/share/opencode/auth.json 的 opencode-go 条目（只读，不打印）
"""

# -*- coding: utf-8 -*-

import argparse, json, pathlib, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(r"D:\opensource\arch-quality")
sys.path.insert(0, str(ROOT / "scripts"))
import doc_lint
import seeded_defects as sd

OUT = ROOT / ".arch-reports" / "seeded-defects"
TASKS = ["S1", "S2", "S3", "S4", "N0"]
BASE_URL = "https://opencode.ai/inference/go/openai/v1/chat/completions"
UA = "assessment-doc-reviewer/1.0"

INSTRUCTIONS = """你是架构评估文档的独立 Reviewer。给你一个 PR 的 diff 和完整知识库文件，请独立审核。

检查清单（按优先级）：
1. 每条新断言是否有证据支持（证据引用/实测/源码行）；只凭常识或"示例轨迹"当实测 → P1 起。
2. 改写或删除是否丢掉限定条件、豁免条款、KNOWN_HOLES 归属。
3. 跨文档是否一致：规则 ID、severity、置信度、版本号、覆盖矩阵与正文。
4. 覆盖矩阵的 ✅ 能否在正文定位；数字是否虚报。
5. 是否夹带与证据无关的重排/术语替换/阈值放宽。
6. 权重/阈值/severity 变更是否有人类批准记录（HD-）；没有 → P0。
7. 若没有任何问题，判 approved；有 P0 必须 changes_requested。

输出：只输出一个 JSON 对象，不要 markdown 围栏，不要解释。格式：
{"pr_id":"PR-SEED-<ID>","reviewer":{"model":"<model>","provider":"opencode-go","role":"reviewer"},
 "verdict":"approved|changes_requested","p0":0,"p1":0,"p2":0,
 "comments":[{"file":"<相对路径>","line":<整数>,"severity":"P0|P1|P2","evidence":"<证据ID或路径>","message":"<问题>","suggestion":"<改法>"}]}

每条 comment 必须包含 file / line / severity / evidence / message 五个字段（message 必填，不能省略）。
要求：comments 的 file 必须**逐字复制**下面【变更位置】给出的相对路径（不要改写、不要缩写）；line 用该文件中的行号；p0/p1/p2 与 comments 中对应 severity 的条数一致；verdict 与 P0 一致性必须正确。"""


def api_key():
    auth = json.loads((pathlib.Path.home() / ".local/share/opencode/auth.json").read_text(encoding="utf-8"))
    return auth["opencode-go"]["key"]


def build_prompt(task_id: str) -> str:
    task = json.loads((OUT / task_id / "review_task.json").read_text(encoding="utf-8"))
    ws = pathlib.Path(task["workspace"])
    gt = json.loads((OUT / task_id / "ground_truth.json").read_text(encoding="utf-8"))
    parts = [INSTRUCTIONS, f"\nPR_ID: PR-SEED-{task_id}\n",
             "【变更位置】",
             f"- 文件：{gt['changed_file']}",
             f"- 行号：{gt['changed_line']} 附近",
             "\n【变更 diff】", task["diff"], "\n【知识库全文】"]
    for key, rel in doc_lint.DIMENSIONS["gcs"].items():
        p = ws / rel
        if p.exists():
            parts.append(f"\n===== {rel} =====\n" + p.read_text(encoding="utf-8-sig"))
    return "\n".join(parts)


def call_model(model: str, prompt: str, key: str, effort: str = None):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 16000,
    }
    if effort:
        payload["reasoning_effort"] = effort
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE_URL, data=body, headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "User-Agent": UA,
        "x-opencode-session": "seed-review-" + model.replace(".", "-"),
    })
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return None, {"http_error": e.code, "body": e.read().decode("utf-8", "replace")[:500]}, time.time() - t0
    except Exception as e:
        return None, {"error": f"{type(e).__name__}: {e}"}, time.time() - t0
    return data, None, time.time() - t0


def parse_json(text: str):
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        lines = [l for l in t.splitlines() if not l.strip().startswith("```")]
        t = "\n".join(lines).strip()
    start = t.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(t[start:])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def run(model: str, tasks, effort: str = None, tag: str = None):
    key = api_key()
    results = []
    for tid in tasks:
        prompt = build_prompt(tid)
        data, err, latency = call_model(model, prompt, key, effort)
        rec = {"task": tid, "latency_s": round(latency, 1), "effort": effort}
        review_path = OUT / tid / f"review_{model.replace('.', '_')}.json"
        if err or not data:
            rec.update({"ok": False, "error": err or "no data"})
            results.append(rec)
            print(f"  {tid}: ERROR {rec.get('error')}")
            continue
        msg = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        rec["finish_reason"] = ((data.get("choices") or [{}])[0].get("finish_reason"))
        obj = parse_json(msg)
        rec["usage"] = {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "allowance": (usage.get("opencode") or {}).get("allowance"),
        }
        if not obj:
            rec.update({"ok": False, "error": "unparsable JSON", "raw": msg[:300]})
            results.append(rec)
            print(f"  {tid}: UNPARSABLE ({len(msg)} chars)")
            continue
        obj["pr_id"] = f"PR-SEED-{tid}"
        obj.setdefault("reviewer", {})
        obj["reviewer"]["model"] = model
        obj["reviewer"]["provider"] = "opencode-go"
        obj["reviewer"]["role"] = "reviewer"
        review_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        schema_rep = doc_lint.lint_review_file(review_path)
        schema_ok = not schema_rep.has_error()
        schema_errors = [f["message"] for f in schema_rep.findings if f["level"] == "ERROR"]
        graded = sd.grade(OUT / tid, review_path)
        rec.update({
            "schema_ok": schema_ok,
            "schema_errors": schema_errors,
            "ok": graded["ok"] and schema_ok,
            "verdict": obj.get("verdict"),
            "verdict_ok": graded.get("verdict_ok"),
            "detected": graded.get("detected"),
            "localized": graded.get("localized"),
            "p0": obj.get("p0"), "p1": obj.get("p1"), "p2": obj.get("p2"),
            "comments": len(obj.get("comments") or []),
            "reasons": graded.get("reasons", []),
            "hits": [{"file": c.get("file"), "line": c.get("line"), "severity": c.get("severity")}
                     for c in graded.get("hits", [])],
        })
        results.append(rec)
        print(f"  {tid}: {'PASS' if rec['ok'] else 'FAIL'}  verdict_ok={rec['verdict_ok']} "
              f"detected={rec['detected']} localized={rec['localized']}  "
              f"schema={'ok' if rec.get('schema_ok') else 'VIOLATION'} comments={rec['comments']}  {rec['latency_s']}s  "
              f"tok={rec['usage'].get('prompt_tokens')}+{rec['usage'].get('completion_tokens')}")
        if not rec["ok"]:
            for r in rec["reasons"]:
                print(f"      - {r}")
    suffix = (f"_{effort}" if effort else "") + (f"_{tag}" if tag else "")
    out_path = OUT / f"comparison_{model.replace('.', '_')}{suffix}.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    passed = sum(1 for r in results if r.get("ok"))
    print(f"[{model}] {passed}/{len(tasks)} pass; saved {out_path}")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", default=",".join(TASKS))
    ap.add_argument("--effort", default=None, help="reasoning_effort: low/high/max")
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    run(a.model, [t.strip() for t in a.tasks.split(",") if t.strip()], a.effort, a.tag)
