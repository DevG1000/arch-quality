"""H3 WP-8 F1: validate WP7 reference case set (6 dimensions x 9 samples)."""

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED = ["standard", "multilang", "numerical", "solver_physics", "gcs", "acl"]


def find_case_list():
    matches = glob.glob(os.path.join(ROOT, "docs", "zh", "**", "WP7*.json"), recursive=True)
    if not matches:
        raise FileNotFoundError("WP7 case list not found")
    return matches[0]


def validate(data):
    errors = []
    for dim in REQUIRED:
        sec = data.get(dim)
        if not isinstance(sec, dict):
            errors.append(f"{dim}: missing section")
            continue
        samples = sec.get("samples") or {}
        if len(samples) != 9:
            errors.append(f"{dim}: expected 9 samples, got {len(samples)}")
        health = [s.get("health") for s in samples.values() if isinstance(s, dict)]
        if health.count("healthy") != 5 or health.count("unhealthy") != 4:
            errors.append(
                f"{dim}: expected 5 healthy + 4 unhealthy, got "
                f"{health.count('healthy')} healthy + {health.count('unhealthy')} unhealthy")
        for name, s in samples.items():
            if not isinstance(s, dict):
                errors.append(f"{dim}/{name}: sample must be object")
                continue
            if not isinstance(s.get("path"), str) or not s.get("path"):
                errors.append(f"{dim}/{name}: missing path")
            if not isinstance(s.get("overall"), (int, float)):
                errors.append(f"{dim}/{name}: overall must be numeric")
            if s.get("health") not in ("healthy", "unhealthy"):
                errors.append(f"{dim}/{name}: invalid health label")
    return errors


def main():
    path = find_case_list()
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    errors = validate(data)
    print(f"case_list: {path}")
    for dim in REQUIRED:
        sec = data.get(dim, {})
        print(f"  {dim}: {len(sec.get('samples', {}))} samples")
    if errors:
        for e in errors:
            print(f"  [FAIL] {e}")
        return 1
    print("  [PASS] 6 dimensions x 9 samples; 5 healthy + 4 unhealthy each")
    return 0


if __name__ == "__main__":
    sys.exit(main())
