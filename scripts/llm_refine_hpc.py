# -*- coding: utf-8 -*-
"""HPC 候选规则的 LLM 语义精判（可选层，§7.7）

定位：
- 正则/静态分析只产出 candidate（风险信号）；
- 本脚本对 candidate 做语义复核，输出 llm_review（confirm/reject/uncertain）+ 证据；
- **不改变确定性评分**，**不自动 confirmed/BLOCK/封顶**；最终由 TAU/MUST/人工裁定。

用法：
    python scripts/llm_refine_hpc.py <project_root> [--backend auto|openai|opencode|mock]
        [--model MODEL] [--cache PATH] [--max-items 20] [--out PATH]

后端：
- openai : OpenAI 兼容 /chat/completions（temperature=0）
- opencode: 调用本地 `opencode run --format json`
- mock   : 返回 uncertain（测试/离线冒烟）
- auto   : 有 OPENAI_API_KEY 用 openai；否则有 opencode 用 opencode；否则 mock
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

from arch_quality.arch_core import read_text_smart
from arch_quality.arch_metrics_hpc import HpcArchitectureMetrics

PROMPT_VERSION = "hpc-llm-refine-v1"
DEFAULT_CACHE = os.path.join(
    os.path.expanduser("~"), ".config", "opencode", "arch-reports", "hpc_llm_cache.json")

RULE_SIGNALS = {
    "HPC-001": r"#\s*if(?:def)?\b[^\n]*(?:__CUDACC__|USE_CUDA|HAVE_CUDA)",
    "HPC-002": r"\b(cudaMalloc|cudaMemcpy|cudaFree|hipMalloc|hipMemcpy)\b|<<<",
    "HPC-003": r"\b(?:num_teams|thread_limit)\s*\(|<<<",
    "HPC-004": r"\b(cudaMemcpy|cudaMemcpyAsync)\b",
    "HPC-005": r"\bMPI_Isend\b",
    "HPC-006": r"\bMPI_(Allreduce|Bcast|Reduce|Allgather)\b",
    "HPC-007": r"\bMPI_(Send|Recv)\b",
    "HPC-008": r"\b(refineLocally|METIS_Part|p4est_partition|p4est_refine|loadBalance)\b",
    "HPC-009": r"\bMPI_COMM_WORLD\b",
    "HPC-010": r"#\s*pragma\s+omp\s+parallel",
    "HPC-011": r"#\s*pragma\s+omp\s+parallel\s+for",
    "HPC-012": r"#\s*pragma\s+omp\s+parallel",
}


def extract_snippet(root, rel_path, rule, context=8):
    """读取文件并截取规则信号附近 ±context 行；返回 (snippet, line_no)。"""
    if not rel_path:
        return "", 0
    path = os.path.join(root, rel_path)
    try:
        text = read_text_smart(path)
    except Exception:
        return "", 0
    lines = text.splitlines()
    idx = 0
    pat = RULE_SIGNALS.get(rule)
    if pat:
        rx = re.compile(pat)
        for i, line in enumerate(lines):
            if rx.search(line):
                idx = i
                break
    lo = max(0, idx - context)
    hi = min(len(lines), idx + context + 1)
    return "\n".join(lines[lo:hi]), idx + 1


def build_prompt(violation, rel_path, line_no, snippet):
    return f"""你是并行/异构架构评审专家。请只判断下面的“候选”是否为真实语义风险，不要判断实测性能事实，不要修改评分/门禁。

规则：{violation.get('rule')} {violation.get('name', '')}
文件：{rel_path}:{line_no}
候选说明：{violation.get('detail', '')}
触发计数：{violation.get('count', 1)}
候选/确认：candidate={violation.get('candidate')} confirmed={violation.get('confirmed')}

代码片段（可能不完整）：
```cpp
{snippet}
```

请只输出一个 JSON 对象：
{{"verdict":"confirm|reject|uncertain","evidence":"file:line + 简短理由","confidence":"high|medium|low"}}

要求：
- verdict=confirm 仅当片段本身足以证明风险；
- 证据不足/跨函数/依赖运行时 → uncertain；
- 不得臆造文件/行号。"""


def parse_review(text):
    """解析 LLM 响应；失败/非法 → uncertain。"""
    if not text:
        return {"verdict": "uncertain", "evidence": "empty response", "confidence": "low"}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"verdict": "uncertain", "evidence": "no json", "confidence": "low"}
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return {"verdict": "uncertain", "evidence": "invalid json", "confidence": "low"}
    verdict = obj.get("verdict")
    if verdict not in ("confirm", "reject", "uncertain"):
        verdict = "uncertain"
    evidence = str(obj.get("evidence", "")).strip()
    confidence = obj.get("confidence", "low")
    if confidence not in ("high", "medium", "low"):
        confidence = "low"
    if verdict in ("confirm", "reject") and not evidence:
        verdict = "uncertain"
        evidence = "missing evidence"
    return {"verdict": verdict, "evidence": evidence, "confidence": confidence}


def _cache_key(model, rule, rel_path, line_no, snippet):
    raw = "|".join([PROMPT_VERSION, model or "", rule or "", rel_path or "",
                    str(line_no), snippet or ""])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_cache(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cache(path, cache):
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
        f.write("\n")


class OpenAIClient:
    def __init__(self, model, base_url=None, api_key=None, timeout=60):
        self.model = model
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL")
                         or "https://api.openai.com/v1")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

    def review(self, prompt):
        body = json.dumps({
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.api_key},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


class OpencodeClient:
    def __init__(self, timeout=120):
        self.timeout = timeout

    def review(self, prompt):
        proc = subprocess.run(
            ["opencode", "run", "--format", "json", prompt],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=self.timeout,
        )
        texts = []
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            part = ev.get("part") or {}
            if part.get("type") == "text" and part.get("text"):
                texts.append(part["text"])
        return "\n".join(texts) or (proc.stdout or "")


class MockClient:
    def review(self, prompt):
        return json.dumps({"verdict": "uncertain",
                           "evidence": "mock backend",
                           "confidence": "low"})


def make_client(backend, model):
    if backend == "auto":
        if os.environ.get("OPENAI_API_KEY"):
            backend = "openai"
        elif _which("opencode"):
            backend = "opencode"
        else:
            backend = "mock"
    if backend == "openai":
        if not model:
            raise RuntimeError("--model is required for openai backend")
        return "openai", OpenAIClient(model)
    if backend == "opencode":
        return "opencode", OpencodeClient()
    return "mock", MockClient()


def _which(name):
    for p in os.environ.get("PATH", "").split(os.pathsep):
        cand = os.path.join(p, name + (".exe" if os.name == "nt" else ""))
        if os.path.exists(cand):
            return cand
    return None


def refine_candidates(violations, root, client, cache, model, max_items=20):
    """对 candidate 做 LLM 复核；不改变 confirmed/评分/gate。"""
    enriched = []
    calls = 0
    cached = 0
    reviewed = 0
    for v in violations:
        v2 = dict(v)
        if not v.get("candidate") or calls >= max_items:
            enriched.append(v2)
            continue
        files = v.get("files") or []
        rel = files[0] if files else ""
        snippet, line_no = extract_snippet(root, rel, v.get("rule", ""))
        if not rel or not snippet:
            v2["llm_review"] = "uncertain"
            v2["llm_evidence"] = "no file/snippet"
            v2["llm_confidence"] = "low"
            v2["llm_model"] = model or "default"
            v2["llm_prompt_version"] = PROMPT_VERSION
            enriched.append(v2)
            continue
        prompt = build_prompt(v, rel, line_no, snippet)
        key = _cache_key(model, v.get("rule", ""), rel, line_no, snippet)
        if key in cache:
            text = cache[key]
            cached += 1
        else:
            text = client.review(prompt)
            cache[key] = text
            calls += 1
        review = parse_review(text)
        v2["llm_review"] = review["verdict"]
        v2["llm_evidence"] = review["evidence"]
        v2["llm_confidence"] = review["confidence"]
        v2["llm_model"] = model or "default"
        v2["llm_prompt_version"] = PROMPT_VERSION
        enriched.append(v2)
        reviewed += 1
    return enriched, {"reviewed": reviewed, "calls": calls, "cached": cached}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="HPC candidate LLM semantic refinement")
    ap.add_argument("root", help="项目根目录")
    ap.add_argument("--backend", choices=["auto", "openai", "opencode", "mock"], default="auto")
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", ""))
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--max-items", type=int, default=20)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    m = HpcArchitectureMetrics(args.root)
    result = m.all_metrics()
    backend, client = make_client(args.backend, args.model)
    cache = load_cache(args.cache)
    enriched, stats = refine_candidates(
        result.get("hpc_violations", []), args.root, client, cache,
        args.model, max_items=args.max_items)
    if stats["calls"]:
        save_cache(args.cache, cache)

    result = dict(result)
    result["hpc_violations"] = enriched
    result["llm_meta"] = {
        "backend": backend,
        "model": args.model or "default",
        "prompt_version": PROMPT_VERSION,
        "temperature": 0,
        "reviewed": stats["reviewed"],
        "calls": stats["calls"],
        "cached": stats["cached"],
        "note": "llm_review is candidate-level evidence only; does not change score/gate/confirmed",
    }

    if args.out:
        out = args.out
    else:
        out_dir = os.path.join(
            os.path.expanduser("~"), ".config", "opencode", "arch-reports", "hpc-llm")
        out = os.path.join(
            out_dir, os.path.basename(os.path.abspath(args.root)) + ".llm.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"backend={backend} reviewed={stats['reviewed']} calls={stats['calls']} cached={stats['cached']}")
    print("out:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
