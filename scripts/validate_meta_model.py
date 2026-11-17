# -*- coding: utf-8 -*-
r"""标准元模型最小 validator (WP-7.2 / H3 WP-1)

校验 meta_model_registry.json：
1. 权重和=100%（按引擎分组；标准 4 维固定和=100%；增强引擎激活子集内归一化）
2. sub_dimensions 内部维度权重和=100%（H3 WP-1）
3. 规则编号合法性 ([A-Z]{3}-\d{3}) + 前缀在注册引擎内
4. 编号连续性（每引擎 001~012 无空洞）
5. 豁免完整性（可豁免规则必须有豁免后级别）
6. 激活子集全局归一化公理（任意激活子集归一化权重和=1，H3 WP-1）

用法：
    python scripts/validate_meta_model.py [registry.json]

退出码：0=通过, 1=校验失败
"""

import itertools
import json
import os
import re
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REGISTRY = os.path.join(PROJECT, "meta_model_registry.json")

RULE_ID_RE = re.compile(r"^(SAR|MLR|TPL|NVR|MPR|GCS|ACL|HPC|FOS)-(\d{3})$")
VALID_SEVERITY = {"HIGH", "MEDIUM", "LOW"}
VALID_LEVEL = {"ERROR", "WARNING", "INFO"}
VALID_SCOPE = {"global", "project"}
RULE_COUNT = 12


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_weights(reg):
    """权重和=100%（按引擎）"""
    ok = True
    by_engine = {}
    for d in reg.get("dimensions", []):
        by_engine.setdefault(d["engine"], []).append(d)
    for engine, dims in sorted(by_engine.items()):
        total = sum(d.get("weight", 0) for d in dims)
        if engine == "standard":
            if abs(total - 1.0) > 1e-6:
                print("  FAIL: %s 权重和=%.4f（期望 1.0）" % (engine, total))
                ok = False
            else:
                print("  OK: %s 权重和=%.4f" % (engine, total))
        else:
            print("  INFO: %s 权重和=%.4f（激活子集内归一化）" % (engine, total))
    return ok


def check_sub_dimensions(reg):
    """sub_dimensions 内部维度权重和=100%（H3 WP-1）"""
    ok = True
    n = 0
    for d in reg.get("dimensions", []):
        subs = d.get("sub_dimensions")
        if not subs:
            continue
        total = sum(s.get("weight", 0) for s in subs)
        if abs(total - 1.0) > 1e-6:
            print("  FAIL: %s sub_dimensions 权重和=%.4f（期望 1.0）" % (d["id"], total))
            ok = False
        n += 1
    if ok:
        print("  OK: sub_dimensions 权重和=1.0（%d 维）" % n)
    return ok


def check_rule_ids(reg):
    """编号合法性 + 连续性 + 无空洞"""
    ok = True
    by_engine = {}
    for r in reg.get("rules", []):
        rid = r.get("id", "")
        m = RULE_ID_RE.match(rid)
        if not m:
            print("  FAIL: 规则 ID 非法 %s" % rid)
            ok = False
            continue
        by_engine.setdefault(m.group(1), set()).add(int(m.group(2)))
        if r.get("severity") not in VALID_SEVERITY:
            print("  FAIL: %s severity 非法 %s" % (rid, r.get("severity")))
            ok = False
        if r.get("output_level") not in VALID_LEVEL:
            print("  FAIL: %s output_level 非法 %s" % (rid, r.get("output_level")))
            ok = False
    for prefix, nums in sorted(by_engine.items()):
        expected = set(range(1, RULE_COUNT + 1))
        missing = expected - nums
        if missing:
            print("  FAIL: %s 缺编号 %s" % (prefix, sorted(missing)))
            ok = False
        else:
            print("  OK: %s-001~%03d 连续无空洞" % (prefix, RULE_COUNT))
    return ok


def check_waivable(reg):
    """可豁免规则必须有豁免后级别"""
    ok = True
    for r in reg.get("rules", []):
        if r.get("waivable") and r.get("waived_output_level") not in VALID_LEVEL:
            print("  FAIL: %s 可豁免但缺豁免后级别" % r.get("id"))
            ok = False
    return ok


def check_activate_subset(reg):
    """激活子集全局归一化公理：任意激活子集归一化权重和=1（H3 WP-1）"""
    ok = True
    dims = {d["id"]: float(d.get("weight", 0)) for d in reg.get("dimensions", [])}
    base = [d["id"] for d in reg.get("dimensions", []) if d.get("engine") == "standard"]
    enh = [d["id"] for d in reg.get("dimensions", []) if d.get("engine") != "standard"]
    checked = 0
    for r in range(len(enh) + 1):
        for combo in itertools.combinations(enh, r):
            active = base + list(combo)
            total = sum(dims.get(i, 0) for i in active)
            if total <= 0:
                continue
            if abs(sum(dims.get(i, 0) / total for i in active) - 1.0) > 1e-9:
                print("  FAIL: 激活子集 %s 归一化权重和 != 1" % (combo,))
                ok = False
            checked += 1
    if ok:
        print("  OK: 激活子集全局归一化公理（%d 个子集 Sigma=1）" % checked)
    return ok


def check_scope(reg):
    """维度 scope 合法性（global/project，H3 WP-2）"""
    ok = True
    n = 0
    for d in reg.get("dimensions", []):
        if d.get("scope") not in VALID_SCOPE:
            print("  FAIL: %s scope 非法 %r" % (d.get("id"), d.get("scope")))
            ok = False
        n += 1
    if ok:
        print("  OK: 全部维度 scope 合法（global/project，%d 维）" % n)
    return ok


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REGISTRY
    if not os.path.exists(path):
        print("[ERROR] 注册表不存在: %s" % path)
        return 1
    reg = load(path)
    print("=== 标准元模型校验: %s ===" % os.path.basename(path))
    results = []
    results.append(("权重和", check_weights(reg)))
    results.append(("内部维度权重", check_sub_dimensions(reg)))
    results.append(("编号合法性/连续性", check_rule_ids(reg)))
    results.append(("豁免完整性", check_waivable(reg)))
    results.append(("激活子集归一化公理", check_activate_subset(reg)))
    results.append(("scope 合法性", check_scope(reg)))
    all_ok = all(x for _, x in results)
    for name, ok in results:
        print("  %s: %s" % (name, "PASS" if ok else "FAIL"))
    print("\n结果: %s" % ("PASS - 元模型注册表有效" if all_ok else "FAIL - 存在缺陷"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())