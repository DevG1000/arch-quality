"""Harness 主 Runner：驱动 architecture-quality 智能体并对结果断言。

通过 `opencode run --agent architecture-quality --format json` 子进程
执行评估，解析 JSON 事件流，运行断言器，输出 PASS/FAIL 报告。

用法：
    python -m opencode_harness.harness_runner [cases_dir]
"""

import json
import os
import subprocess
import sys
import time
import datetime

HARNESS_DIR = os.path.dirname(os.path.abspath(__file__))
CASES_DIR = os.path.join(HARNESS_DIR, "cases")
REPORTS_DIR = os.path.join(HARNESS_DIR, "reports")

DEFAULT_TIMEOUT = 600  # 单次 agent 运行超时（秒）
AGENT_NAME = "architecture-quality"


def run_opencode(prompt: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, list[dict], str]:
    """运行 opencode run，返回 (returncode, events, raw_output)。

    事件流为 JSONL（每行一个 JSON 事件）。
    """
    cmd = [
        "opencode", "run",
        "--agent", AGENT_NAME,
        "--format", "json",
        prompt,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return -1, [], f"TIMEOUT after {timeout}s"
    events = []
    raw = (proc.stdout or "") + (proc.stderr or "")
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return proc.returncode, events, raw


def load_cases(cases_dir: str = CASES_DIR) -> list[dict]:
    cases = []
    for fname in sorted(os.listdir(cases_dir)):
        if fname.endswith(".json"):
            with open(os.path.join(cases_dir, fname), encoding="utf-8") as f:
                cases.append(json.load(f))
    return cases


def run_case(case: dict, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """运行单个用例，返回完整结果。"""
    prompt = case["prompt"]
    expect = case.get("expect", {})
    max_retries = expect.get("max_retries", 2)

    result = {
        "case_id": case["id"],
        "name": case["name"],
        "status": "FAIL",
        "attempts": [],
        "errors": [],
        "passed": [],
        "timestamp": datetime.datetime.now().isoformat(),
    }

    for attempt in range(1, max_retries + 1):
        code, events, raw = run_opencode(prompt, timeout=timeout)
        attempt_rec = {"attempt": attempt, "returncode": code,
                       "event_count": len(events)}
        result["attempts"].append(attempt_rec)

        if code == -1:
            # 超时：尝试纠正重试
            attempt_rec["error"] = "timeout"
            continue

        # 解析事件
        from assertors import tool_usage, output_schema, score_sanity
        tool_calls = tool_usage.extract_tool_calls(events)
        final_text = output_schema.extract_final_report(events)

        # 运行断言器
        errors = []
        errors += tool_usage.assert_all(tool_calls)
        errors += output_schema.assert_all(final_text, expect)
        errors += score_sanity.assert_all(final_text)

        result["tool_calls"] = tool_calls
        result["final_text"] = final_text[:2000]
        if errors:
            result["errors"] = errors
            attempt_rec["error"] = "; ".join(errors[:3])
            continue  # 重试
        # 通过：清空重试阶段残留的 errors，记录最终状态
        result["errors"] = []
        result["status"] = "PASS"
        result["passed"] = ["全部断言通过"]
        result["retries_used"] = attempt - 1
        return result
        return result

    if not result["errors"]:
        result["errors"] = [f"重试 {max_retries} 次均超时"]
    return result


def save_report(result: dict) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    fname = os.path.join(REPORTS_DIR, f"{result['case_id']}.json")
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return fname


def main():
    cases_dir = sys.argv[1] if len(sys.argv) > 1 else CASES_DIR
    timeout = int(os.environ.get("HARNESS_TIMEOUT", DEFAULT_TIMEOUT))
    cases = load_cases(cases_dir)
    print(f"=== agent harness: {len(cases)} 用例 ===")
    summary = {"pass": 0, "fail": 0}
    for case in cases:
        print(f"\n[{case['id']}] {case['name']}")
        result = run_case(case, timeout=timeout)
        report_path = save_report(result)
        print(f"  状态: {result['status']} | 尝试: {len(result['attempts'])}")
        if result["errors"]:
            for e in result["errors"]:
                print(f"    ERROR: {e}")
        print(f"  报告: {report_path}")
        summary[result["status"].lower()] += 1

    print(f"\n=== 汇总: PASS {summary['pass']} / FAIL {summary['fail']} ===")
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
