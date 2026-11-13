#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""doc_lint.py — 架构评估文档 PR 门禁（垂直切片 P1）。

覆盖三类"机器可判"门禁：
  G0 结构：必需文件/章节、规则详情小节、相对链接、版本绑定与编制指南版本
  G1 权重：各文档权重和 = 100%，且 指南 = src Skill = OpenCode Skill
  G3 规则：severity/output_level 词表与映射、低置信度不得 ERROR、三份文档口径一致

另含两个契约校验：
  --review  Reviewer 报告（scripts/review_schema.json）
  --pr      PR front-matter（权重/阈值/severity 变更必须有人类批准记录）

用法：
  python scripts/doc_lint.py --dimension gcs
  python scripts/doc_lint.py --dimension gcs --json
  python scripts/doc_lint.py --guide <指南.md> --skill <src skill.md> \
      [--cases <案例集.md>] [--rationale <设计依据.md>] [--opencode-skill <SKILL.md>]
  python scripts/doc_lint.py --review review.json
  python scripts/doc_lint.py --pr pr.md
  python scripts/doc_lint.py --list-dimensions

退出码：0 = 无 ERROR；1 = 存在 ERROR；2 = 参数错误。
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path(__file__).with_name("review_schema.json")
META_GUIDE = ROOT / "docs" / "zh" / "AI 架构评估文档编制指南.md"

# 维度注册表：新增维度时在此登记一行即可（路径相对仓库根）
DIMENSIONS: Dict[str, Dict[str, str]] = {
    "gcs": {
        "guide": "docs/zh/几何内核与科学数据结构一致性评估/几何内核与科学数据结构一致性评估指南.md",
        "cases": "docs/zh/几何内核与科学数据结构一致性评估/几何内核与科学数据结构一致性评估验证案例集.md",
        "rationale": "docs/zh/几何内核与科学数据结构一致性评估/几何内核与科学数据结构一致性评估的设计依据.md",
        "skill": "src/arch_quality/skills/geometry-consistency.md",
        "opencode_skill": ".opencode/skills/geometry-consistency/SKILL.md",
    },
}

# 指南必需章节（正则，作用于整份文档）
REQUIRED_SECTIONS: List[Tuple[str, str]] = [
    ("概述", r"^##\s+概述\s*$"),
    ("置信度说明", r"^##\s+置信度说明\s*$"),
    ("一、子维度与权重分配", r"^##\s+一、"),
    ("二、子维度定义与评分算法", r"^##\s+二、"),
    ("五、内置规则", r"^##\s+五、"),
    ("七、实施建议", r"^##\s+七、"),
    ("版本历史", r"^##\s+版本历史\s*$"),
]

RULE_ID_RE = re.compile(r"^[A-Z]{2,6}-\d{3}$")
RULE_HEAD_RE = re.compile(r"^#{3,5}\s*([A-Z]{2,6}-\d{3})\b")
TABLE_SEP_RE = re.compile(r"^:?-{2,}:?$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
PCT_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*%$")
SEVERITIES = ("HIGH", "MEDIUM", "LOW")
OUTPUT_LEVELS = ("ERROR", "WARNING", "INFO")
CONFIDENCES = ("高", "中", "低")
SEV_TO_OUTPUT = {"HIGH": "ERROR", "MEDIUM": "WARNING", "LOW": "INFO"}


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def read_text(path: Path) -> str:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def split_row(line: str) -> List[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip().strip("*").strip() for c in s.split("|")]


def parse_tables(text: str) -> List[Dict[str, Any]]:
    """返回 [{'header': [...], 'rows': [(line_no, cells)], 'line': n}]，跳过代码块。"""
    tables: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    in_code = False
    for no, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            cur = None
            continue
        if in_code:
            continue
        if line.lstrip().startswith("|"):
            cells = split_row(line)
            if cur is None:
                cur = {"header": cells, "rows": [], "line": no}
            elif cells and all(TABLE_SEP_RE.match(c) for c in cells if c):
                continue
            else:
                cur["rows"].append((no, cells))
        else:
            if cur is not None:
                tables.append(cur)
                cur = None
    if cur is not None:
        tables.append(cur)
    return tables


def norm_name(s: str) -> str:
    return s.replace("与", "/").replace(" ", "").strip()


def first_in(cells: List[str], allowed: Tuple[str, ...]) -> Optional[str]:
    for c in cells:
        if c in allowed:
            return c
    return None


def parse_weights(text: str) -> Dict[str, Tuple[float, int]]:
    out: Dict[str, Tuple[float, int]] = {}
    for table in parse_tables(text):
        header = table["header"]
        if not any("权重" in h for h in header):
            continue
        for no, cells in table["rows"]:
            if len(cells) < 2 or not cells[0]:
                continue
            pct = None
            for c in cells[1:]:
                m = PCT_RE.match(c)
                if m:
                    pct = float(m.group(1))
                    break
            if pct is None:
                continue
            out[norm_name(cells[0])] = (pct, no)
    return out


def parse_rules(text: str) -> Dict[str, Dict[str, Any]]:
    rules: Dict[str, Dict[str, Any]] = {}
    for table in parse_tables(text):
        for no, cells in table["rows"]:
            if not cells:
                continue
            rid = cells[0].replace(" ", "")
            if not RULE_ID_RE.match(rid):
                continue
            rules[rid] = {
                "id": rid,
                "line": no,
                "severity": first_in(cells, SEVERITIES),
                "output_level": first_in(cells, OUTPUT_LEVELS),
                "confidence": first_in(cells, CONFIDENCES),
            }
    return rules


def guide_version(text: str) -> Optional[str]:
    m = re.search(r"（\s*(\d+\.\d+)\s*版\s*）", text)
    if m:
        return m.group(1)
    m = re.search(r"\*\*版本\*\*\s*[：:]\s*(\d+\.\d+)", text)
    return m.group(1) if m else None


def version_history_versions(text: str) -> List[str]:
    """解析“## 版本历史”表格第一列的 x.y 版本号。"""
    marker = "## 版本历史"
    if marker not in text:
        return []
    body = text.split(marker, 1)[1]
    return re.findall(r"^\|\s*(\d+\.\d+)\s*\|", body, re.MULTILINE)


def bound_guide_version(text: str) -> Optional[str]:
    patterns = (
        r"指南（\s*(\d+\.\d+)\s*版\s*）",
        r"指南》[^\n]{0,24}?(\d+\.\d+)\s*版",
        r"指南版本\s*[：:]\s*(\d+\.\d+)",
    )
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------
class Report:
    def __init__(self) -> None:
        self.findings: List[Dict[str, Any]] = []

    def add(self, gate: str, level: str, code: str, message: str,
            file: Optional[str] = None, line: Optional[int] = None) -> None:
        self.findings.append({
            "gate": gate, "level": level, "code": code,
            "message": message, "file": file, "line": line,
        })

    def has_error(self) -> bool:
        return any(f["level"] == "ERROR" for f in self.findings)

    def summary(self) -> Dict[str, int]:
        c = Counter(f["level"] for f in self.findings)
        return {"error": c.get("ERROR", 0), "warning": c.get("WARNING", 0),
                "info": c.get("INFO", 0)}


def _rel(p: Optional[Path]) -> Optional[str]:
    if p is None:
        return None
    try:
        return str(Path(p).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


# --------------------------------------------------------------------------
# G0 结构
# --------------------------------------------------------------------------
def check_structure(rep: Report, guide: Path, text: str,
                    cases: Optional[Path], rationale: Optional[Path],
                    skill: Optional[Path], opencode_skill: Optional[Path],
                    strict_versions: bool) -> None:
    for name, pat in REQUIRED_SECTIONS:
        if not re.search(pat, text, re.MULTILINE):
            rep.add("G0", "ERROR", "G0-section",
                    f"指南缺少必需章节：{name}", _rel(guide))

    rules = parse_rules(text)
    detail = {m.group(1) for m in
              (RULE_HEAD_RE.match(l) for l in text.splitlines()) if m}
    for rid in sorted(rules):
        if rid not in detail:
            rep.add("G0", "ERROR", "G0-rule-detail",
                    f"{rid} 在规则表中但缺少 `#### {rid}` 详情小节",
                    _rel(guide), rules[rid]["line"])

    ids = sorted(int(r.split("-")[1]) for r in rules)
    if ids:
        expected = set(range(ids[0], ids[0] + len(ids)))
        gaps = sorted(expected - set(ids))
        if gaps:
            rep.add("G0", "ERROR", "G0-rule-gap",
                    f"规则编号不连续，缺：{', '.join('###') if False else ', '.join('%03d' % g for g in gaps)}",
                    _rel(guide))

    for p in (guide, skill, opencode_skill, cases, rationale):
        if p is None:
            continue
        if not p.exists():
            rep.add("G0", "ERROR", "G0-file", f"文件不存在：{_rel(p)}")
            continue
        _check_links(rep, p, read_text(p))

    gv = guide_version(text)
    if not gv:
        rep.add("G0", "ERROR", "G0-version", "指南未声明版本号（如“（1.6版）”）", _rel(guide))
    else:
        level = "ERROR" if strict_versions else "WARNING"
        for p in (cases, rationale, skill, opencode_skill):
            if p is None or not p.exists():
                continue
            bv = bound_guide_version(read_text(p))
            if bv and bv != gv:
                rep.add("G0", level, "G0-version-drift",
                        f"{p.name} 绑定指南 {bv}，当前指南 {gv}", _rel(p))

    if gv:
        hist = version_history_versions(text)
        if hist:
            latest = max(hist, key=lambda v: tuple(int(x) for x in v.split(".")))
            if latest != gv:
                rep.add("G0", level, "G0-version-history",
                        f"标题/头部版本 {gv} 与版本历史最新版本 {latest} 不一致",
                        _rel(guide))

    if META_GUIDE.exists():
        meta = guide_version(read_text(META_GUIDE))
        ref = re.search(r"编制指南\s*(\d+\.\d+)", text)
        if meta and ref and ref.group(1) != meta:
            rep.add("G0", "WARNING", "G0-meta-guide",
                    f"指南引用《AI 架构评估文档编制指南 {ref.group(1)}》，当前为 {meta}",
                    _rel(guide))


def _check_links(rep: Report, path: Path, text: str) -> None:
    in_code = False
    for no, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        for m in LINK_RE.finditer(line):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#", "<")):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            if not (path.parent / target).exists():
                rep.add("G0", "ERROR", "G0-link",
                        f"相对链接不存在：{target}", _rel(path), no)


# --------------------------------------------------------------------------
# G1 权重
# --------------------------------------------------------------------------
def check_weights(rep: Report, guide: Path, text: str,
                  skill: Optional[Path], opencode_skill: Optional[Path]) -> None:
    g = parse_weights(text)
    if not g:
        rep.add("G1", "ERROR", "G1-missing", "指南未找到权重表", _rel(guide))
        return
    _check_sum(rep, guide, g, "指南")
    for p, label in ((skill, "src Skill"), (opencode_skill, "OpenCode Skill")):
        if p is None or not p.exists():
            continue
        other = parse_weights(read_text(p))
        if not other:
            rep.add("G1", "ERROR", "G1-missing", f"{label} 未找到权重表", _rel(p))
            continue
        _check_sum(rep, p, other, label)
        for name, (pct, no) in g.items():
            if name not in other:
                rep.add("G1", "ERROR", "G1-cross",
                        f"权重项“{name}”在 {label} 缺失", _rel(p), no)
            elif abs(other[name][0] - pct) > 0.01:
                rep.add("G1", "ERROR", "G1-cross",
                        f"权重不一致：{name} 指南 {pct:g}% vs {label} {other[name][0]:g}%",
                        _rel(p), other[name][1])
        for name in other:
            if name not in g:
                rep.add("G1", "ERROR", "G1-cross",
                        f"权重项“{name}”只出现在 {label}", _rel(p))


def _check_sum(rep: Report, path: Path, weights: Dict[str, Tuple[float, int]],
               label: str) -> None:
    total = sum(v[0] for v in weights.values())
    if abs(total - 100.0) > 0.01:
        rep.add("G1", "ERROR", "G1-sum",
                f"{label} 权重和为 {total:g}%，应为 100%", _rel(path))
    for name, (pct, no) in weights.items():
        if pct <= 0:
            rep.add("G1", "ERROR", "G1-nonpositive",
                    f"{name} 权重 {pct:g}% 应大于 0", _rel(path), no)


# --------------------------------------------------------------------------
# G3 规则口径
# --------------------------------------------------------------------------
def check_rules(rep: Report, guide: Path, text: str,
                skill: Optional[Path], opencode_skill: Optional[Path]) -> None:
    g = parse_rules(text)
    if not g:
        rep.add("G3", "ERROR", "G3-missing", "指南未找到规则表", _rel(guide))
        return

    for rid, r in sorted(g.items()):
        if r["severity"] not in SEVERITIES:
            rep.add("G3", "ERROR", "G3-vocab",
                    f"{rid} severity 非法：{r['severity']}", _rel(guide), r["line"])
        if r["output_level"] not in OUTPUT_LEVELS:
            rep.add("G3", "ERROR", "G3-vocab",
                    f"{rid} output_level 非法：{r['output_level']}", _rel(guide), r["line"])
        if r["confidence"] not in CONFIDENCES:
            rep.add("G3", "ERROR", "G3-vocab",
                    f"{rid} 置信度非法：{r['confidence']}", _rel(guide), r["line"])
        if r["confidence"] == "低" and r["output_level"] == "ERROR":
            rep.add("G3", "ERROR", "G3-low-conf-error",
                    f"{rid} 为低置信度却设为 ERROR（指南：低置信度仅 INFO，不阻断）",
                    _rel(guide), r["line"])
        expected = SEV_TO_OUTPUT.get(r["severity"] or "", None)
        if expected and r["output_level"] != expected:
            rep.add("G3", "WARNING", "G3-mapping",
                    f"{rid} severity={r['severity']} 与 output_level={r['output_level']} 不匹配（约定 {expected}）",
                    _rel(guide), r["line"])

    _check_heuristic_high(rep, guide, text, g)
    _compare_rules(rep, guide, g, skill, "src Skill", full=True)
    _compare_rules(rep, guide, g, opencode_skill, "OpenCode Skill", full=False)


def _check_heuristic_high(rep: Report, guide: Path, text: str,
                          rules: Dict[str, Dict[str, Any]]) -> None:
    blocks: Dict[str, str] = {}
    cur = None
    buf: List[str] = []
    for line in text.splitlines():
        m = RULE_HEAD_RE.match(line)
        if m:
            if cur:
                blocks[cur] = "\n".join(buf)
            cur, buf = m.group(1), []
        elif line.startswith("## "):
            if cur:
                blocks[cur] = "\n".join(buf)
            cur, buf = None, []
        elif cur:
            buf.append(line)
    if cur:
        blocks[cur] = "\n".join(buf)
    for rid, r in rules.items():
        block = blocks.get(rid, "")
        if r["confidence"] == "高" and re.search(r"启发式|推断", block):
            rep.add("G3", "WARNING", "G3-high-heuristic",
                    f"{rid} 标“高”置信度但检测含启发式/推断表述", _rel(guide), r["line"])


def _compare_rules(rep: Report, guide: Path, ref: Dict[str, Dict[str, Any]],
                   other_path: Optional[Path], label: str, full: bool) -> None:
    if other_path is None or not other_path.exists():
        return
    other = parse_rules(read_text(other_path))
    if not other:
        rep.add("G3", "ERROR", "G3-missing", f"{label} 未找到规则表", _rel(other_path))
        return
    for rid, r in ref.items():
        if rid not in other:
            rep.add("G3", "ERROR", "G3-cross", f"{rid} 在 {label} 缺失", _rel(other_path))
            continue
        o = other[rid]
        if r["output_level"] and o["output_level"] and r["output_level"] != o["output_level"]:
            rep.add("G3", "ERROR", "G3-cross",
                    f"{rid} output_level 不一致：指南 {r['output_level']} vs {label} {o['output_level']}",
                    _rel(other_path), o["line"])
        if full:
            for key, cn in (("severity", "severity"), ("confidence", "置信度")):
                if r[key] and o[key] and r[key] != o[key]:
                    rep.add("G3", "ERROR", "G3-cross",
                            f"{rid} {cn} 不一致：指南 {r[key]} vs {label} {o[key]}",
                            _rel(other_path), o["line"])
    for rid in other:
        if rid not in ref:
            rep.add("G3", "ERROR", "G3-cross", f"{rid} 只出现在 {label}", _rel(other_path))


# --------------------------------------------------------------------------
# 入口：维度 lint
# --------------------------------------------------------------------------
def lint_paths(guide: Path, skill: Optional[Path] = None,
               opencode_skill: Optional[Path] = None,
               cases: Optional[Path] = None,
               rationale: Optional[Path] = None,
               strict_versions: bool = False) -> Report:
    rep = Report()
    if not guide.exists():
        rep.add("G0", "ERROR", "G0-file", f"文件不存在：{guide}")
        return rep
    text = read_text(guide)
    check_structure(rep, guide, text, cases, rationale, skill, opencode_skill,
                    strict_versions)
    check_weights(rep, guide, text, skill, opencode_skill)
    check_rules(rep, guide, text, skill, opencode_skill)
    return rep


def dimension_paths(name: str, root: Path = ROOT) -> Dict[str, Path]:
    """返回某维度各文档的绝对路径（root 可为临时 workspace）。"""
    spec = DIMENSIONS.get(name)
    if spec is None:
        raise SystemExit(f"未注册的维度：{name}（可用：{', '.join(DIMENSIONS)}）")
    return {key: Path(root) / rel for key, rel in spec.items()}


def lint_dimension(name: str, strict_versions: bool = False,
                   root: Path = ROOT) -> Report:
    paths = dimension_paths(name, root)
    return lint_paths(
        guide=paths["guide"],
        skill=paths.get("skill"),
        opencode_skill=paths.get("opencode_skill"),
        cases=paths.get("cases"),
        rationale=paths.get("rationale"),
        strict_versions=strict_versions,
    )


# --------------------------------------------------------------------------
# Review 报告契约
# --------------------------------------------------------------------------
def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def validate_schema(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """最小 JSON-Schema 子集：type/required/properties/items/enum/minimum/minLength/
    minItems/additionalProperties。"""
    errs: List[str] = []
    t = schema.get("type")
    ok = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
    }
    if t and t in ok and not ok[t](value):
        return [f"{path}: 期望 {t}，实际 {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: 取值 {value!r} 不在 {schema['enum']}")
    if t == "string" and "minLength" in schema and len(value) < schema["minLength"]:
        errs.append(f"{path}: 长度 < {schema['minLength']}")
    if t in ("integer", "number") and "minimum" in schema and value < schema["minimum"]:
        errs.append(f"{path}: 小于最小值 {schema['minimum']}")
    if t == "object":
        for key in schema.get("required", []):
            if key not in value:
                errs.append(f"{path}: 缺少必需字段 {key}")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in value:
                errs.extend(validate_schema(value[key], sub, f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(props)
            if extra:
                errs.append(f"{path}: 出现未定义字段 {sorted(extra)}")
    if t == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            errs.append(f"{path}: 元素数 < {schema['minItems']}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                errs.extend(validate_schema(item, item_schema, f"{path}[{i}]"))
    return errs


def lint_review_file(review_path: Path, schema_path: Path = SCHEMA_PATH) -> Report:
    rep = Report()
    if not review_path.exists():
        rep.add("R", "ERROR", "R-file", f"文件不存在：{review_path}")
        return rep
    schema = load_json(schema_path)
    try:
        data = load_json(review_path)
    except json.JSONDecodeError as exc:
        rep.add("R", "ERROR", "R-json", f"不是合法 JSON：{exc}", _rel(review_path))
        return rep
    for err in validate_schema(data, schema):
        rep.add("R", "ERROR", "R-schema", err, _rel(review_path))
    if rep.has_error():
        return rep

    p0_comments = [c for c in data["comments"] if c["severity"] == "P0"]
    if data["p0"] != len(p0_comments):
        rep.add("R", "ERROR", "R-p0-count",
                f"p0 字段为 {data['p0']}，但 P0 评论有 {len(p0_comments)} 条",
                _rel(review_path))
    if data["verdict"] == "approved" and (data["p0"] > 0 or p0_comments):
        rep.add("R", "ERROR", "R-approve-with-p0",
                "verdict=approved 但仍有 P0 问题，禁止批准", _rel(review_path))
    dup = len({(c["file"], c["line"], c["message"]) for c in data["comments"]})
    if dup != len(data["comments"]):
        rep.add("R", "WARNING", "R-dup", "存在重复评论", _rel(review_path))
    return rep


# --------------------------------------------------------------------------
# PR front-matter 契约
# --------------------------------------------------------------------------
PR_REQUIRED = ["pr_type", "kb_version", "guide_version", "evidence",
               "changes", "human_decisions", "review"]
PR_TYPES = {"guide", "rationale", "cases", "tooling", "errata"}


def parse_front_matter(text: str) -> Optional[Dict[str, Any]]:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    raw = text[3:end]
    try:
        import yaml  # 可选依赖；缺失时跳过 PR 检查
    except ImportError:
        return {"__error__": "PyYAML 未安装，跳过 PR front-matter 校验"}
    try:
        data = yaml.safe_load(raw)
    except Exception as exc:
        return {"__error__": f"front-matter YAML 解析失败：{exc}"}
    return data if isinstance(data, dict) else {"__error__": "front-matter 不是映射"}


def lint_pr_file(pr_path: Path) -> Report:
    rep = Report()
    if not pr_path.exists():
        rep.add("PR", "ERROR", "PR-file", f"文件不存在：{pr_path}")
        return rep
    data = parse_front_matter(read_text(pr_path))
    if data is None:
        rep.add("PR", "ERROR", "PR-frontmatter", "缺少 `---` front-matter", _rel(pr_path))
        return rep
    if "__error__" in data:
        level = "INFO" if "PyYAML" in data["__error__"] else "ERROR"
        rep.add("PR", level, "PR-frontmatter", data["__error__"], _rel(pr_path))
        return rep

    for key in PR_REQUIRED:
        if key not in data:
            rep.add("PR", "ERROR", "PR-required", f"缺少字段 {key}", _rel(pr_path))
    if data.get("pr_type") not in PR_TYPES:
        rep.add("PR", "ERROR", "PR-type",
                f"pr_type 必须是 {'/'.join(sorted(PR_TYPES))}", _rel(pr_path))
    evidence = data.get("evidence") or []
    if not isinstance(evidence, list) or not evidence:
        rep.add("PR", "ERROR", "PR-evidence", "evidence 必须是非空列表", _rel(pr_path))

    changes = data.get("changes") or {}
    if not isinstance(changes, dict):
        rep.add("PR", "ERROR", "PR-changes", "changes 必须是映射", _rel(pr_path))
        changes = {}
    if not changes.get("files"):
        rep.add("PR", "ERROR", "PR-files", "changes.files 不能为空", _rel(pr_path))
    risky = bool(changes.get("weights_changed")) or bool(changes.get("severity_changed")) \
        or bool(changes.get("thresholds_changed"))
    approvals = data.get("human_decisions") or []
    if risky and not approvals:
        rep.add("PR", "ERROR", "PR-human-approval",
                "权重/阈值/severity 变更必须有人类批准记录（human_decisions）",
                _rel(pr_path))

    review = data.get("review") or {}
    if not isinstance(review, dict):
        rep.add("PR", "ERROR", "PR-review", "review 必须是映射", _rel(pr_path))
    else:
        if review.get("verdict") not in ("approved", "changes_requested"):
            rep.add("PR", "ERROR", "PR-verdict", "review.verdict 缺失或非法", _rel(pr_path))
        if review.get("verdict") == "approved" and review.get("p0", 0) != 0:
            rep.add("PR", "ERROR", "PR-approve-with-p0",
                    "review.verdict=approved 但 p0 != 0", _rel(pr_path))
    return rep


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def print_report(rep: Report, title: str, as_json: bool) -> None:
    if as_json:
        print(json.dumps({
            "title": title,
            "ok": not rep.has_error(),
            "summary": rep.summary(),
            "findings": rep.findings,
        }, ensure_ascii=False, indent=2))
        return
    print(f"doc_lint  {title}")
    for f in rep.findings:
        loc = f["file"] or ""
        if f.get("line"):
            loc += f":{f['line']}"
        tag = {"ERROR": "[ERROR]", "WARNING": "[WARN ]", "INFO": "[INFO ]"}[f["level"]]
        print(f"  {tag} {f['gate']}/{f['code']}  {f['message']}"
              + (f"  ({loc})" if loc else ""))
    s = rep.summary()
    print(f"  summary: {s['error']} error / {s['warning']} warning / {s['info']} info")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="架构评估文档 PR 门禁（G0/G1/G3 + 契约校验）")
    ap.add_argument("--dimension", help="已注册维度，如 gcs")
    ap.add_argument("--guide", type=Path)
    ap.add_argument("--cases", type=Path)
    ap.add_argument("--rationale", type=Path)
    ap.add_argument("--skill", type=Path)
    ap.add_argument("--opencode-skill", type=Path, dest="opencode_skill")
    ap.add_argument("--review", type=Path, help="校验 Reviewer 报告 JSON")
    ap.add_argument("--pr", type=Path, help="校验 PR front-matter")
    ap.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    ap.add_argument("--strict-versions", action="store_true",
                    help="版本漂移按 ERROR 处理")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list-dimensions", action="store_true")
    args = ap.parse_args(argv)

    if args.list_dimensions:
        for name in DIMENSIONS:
            print(name)
        return 0

    try:
        if args.review:
            rep = lint_review_file(args.review, args.schema)
            print_report(rep, f"review={args.review}", args.json)
        elif args.pr:
            rep = lint_pr_file(args.pr)
            print_report(rep, f"pr={args.pr}", args.json)
        elif args.dimension:
            rep = lint_dimension(args.dimension, args.strict_versions)
            print_report(rep, f"dimension={args.dimension}", args.json)
        elif args.guide:
            rep = lint_paths(args.guide, args.skill, args.opencode_skill,
                             args.cases, args.rationale, args.strict_versions)
            print_report(rep, f"guide={args.guide.name}", args.json)
        else:
            ap.error("需要 --dimension / --guide / --review / --pr 之一")
            return 2
    except SystemExit:
        raise
    except Exception as exc:  # 内部错误不要伪装成通过
        print(f"doc_lint internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 1 if rep.has_error() else 0


if __name__ == "__main__":
    sys.exit(main())
