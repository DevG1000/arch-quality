#!/usr/bin/env python3
"""aggregate_runtime_checks.py — summarize H3 WP-5 runtime check JSON (non-blocking)."""
import json, sys

def main():
    if len(sys.argv) < 2:
        print("usage: aggregate_runtime_checks.py <runtime_checks.json>")
        return 0
    try:
        with open(sys.argv[1], encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except Exception as exc:
        print(f"runtime aggregate: unreadable ({exc})")
        return 0
    checks = data.get("checks") or []
    statuses = {c.get("check"): c.get("status") for c in checks}
    print(f"OCCT {data.get('occt_version','unknown')}: "
          f"euler={statuses.get('euler','MISSING')} "
          f"closure={statuses.get('closure','MISSING')} "
          f"api_compat={statuses.get('api_compat','MISSING')}")
    for c in checks:
        if c.get("status") == "WARN":
            print(f"  WARN {c.get('check')}: {c}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
