"""agent harness 命令行入口。

用法：
    python scripts/run_agent_harness.py                 # 运行全部用例
    python scripts/run_agent_harness.py --case case-1   # 单个用例
    python scripts/run_agent_harness.py --timeout 600   # 自定义超时
"""

import argparse
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "opencode-harness"))

from harness_runner import (  # noqa: E402
    CASES_DIR, load_cases, run_case, save_report, DEFAULT_TIMEOUT,
)


def main():
    parser = argparse.ArgumentParser(description="architecture-quality 智能体验证 harness")
    parser.add_argument("--case", default=None, help="只运行指定 case id（默认全部）")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"单次 agent 运行超时秒数（默认 {DEFAULT_TIMEOUT}）")
    parser.add_argument("--verbose", action="store_true", help="打印详细事件流")
    args = parser.parse_args()

    cases = load_cases(CASES_DIR)
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"未找到用例: {args.case}")
            return 1

    print(f"=== agent harness: {len(cases)} 用例 ===")
    passed = failed = 0
    for case in cases:
        print(f"\n[{case['id']}] {case['name']}")
        result = run_case(case, timeout=args.timeout)
        report_path = save_report(result)
        print(f"  状态: {result['status']} | 尝试: {len(result['attempts'])}")
        if result.get("errors"):
            for e in result["errors"]:
                print(f"    ERROR: {e}")
        elif args.verbose and result.get("final_text"):
            print(f"    agent 输出: {result['final_text'][:300]}")
        print(f"  报告: {report_path}")
        if result["status"] == "PASS":
            passed += 1
        else:
            failed += 1

    print(f"\n=== 汇总: PASS {passed} / FAIL {failed} ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
