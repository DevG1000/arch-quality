"""输出结构断言：检查 agent 汇报的评估结果是否包含必需字段、无幻觉字段。"""

import re

from ._rules import load_rules

_RULES = load_rules()
# 幻觉检测：不应出现的字段名（LLM 可能编造，来源 rules.json）
HALLUCINATED_PATTERNS = list(_RULES["hallucinated_patterns"])
# 非多物理场判定标记（来源 rules.json）
NON_MULTIPHYSICS_MARKERS = list(_RULES["non_multiphysics_markers"])


def extract_final_report(events: list[dict]) -> str:
    """从事件流中提取最终文本输出。

    优先聚合 text 事件；若 text 为空，则从 bash 工具的 output 中提取
    （agent 常把评估结果 JSON 放在命令输出里）。
    剥离 Python SyntaxWarning 等诊断前缀行（stderr 混入 stdout 的噪音）。
    """
    import re as _re
    texts = []
    for ev in events:
        part = ev.get("part") or {}
        if part.get("type") == "text" and part.get("text"):
            texts.append(part["text"])
        elif part.get("type") == "tool":
            state = part.get("state")
            out = ""
            if isinstance(state, dict):
                out = state.get("output", "")
            if isinstance(out, str) and len(out) > 50:
                texts.append(out)
    joined = "\n".join(texts)
    # 剥离 <unknown>:N: SyntaxWarning 行（Python 3.12+ 未加 r 前缀正则的警告）
    clean_lines = [
        ln for ln in joined.splitlines()
        if not _re.match(r"^\s*<unknown>:\d+:\s*SyntaxWarning", ln)
        and not _re.match(r"^\s*Did you mean", ln)
        and not _re.match(r"^\s*A raw string is also an option", ln)
    ]
    return "\n".join(clean_lines)


def extract_json_blocks(text: str) -> list[str]:
    """从文本中提取 JSON 代码块或大括号片段。"""
    blocks = re.findall(r"\{[^{}]*\}", text)
    return blocks


def assert_report_structure(text: str, dimension_fields: list[str]) -> list[str]:
    """断言：报告文本包含维度评分信息（维度字段名出现）。"""
    errors = []
    if not text.strip():
        return ["agent 未返回任何文本输出"]
    for field in dimension_fields:
        if field not in text:
            errors.append(f"报告缺失维度字段: {field}")
    return errors


def assert_no_hallucination(text: str) -> list[str]:
    """断言：无与评估无关的编造内容。"""
    errors = []
    for pat in HALLUCINATED_PATTERNS:
        if re.search(pat, text):
            errors.append(f"检测到疑似幻觉内容（匹配 {pat}）")
    return errors


def assert_overall_mentions(text: str, expected_range: list | None,
                            is_multiphysics: bool | None = None) -> list[str]:
    """断言：综合评分被提及且在期望区间内。

    expected_range 为 None 且 is_multiphysics 为 False 时，检查"不应出现评分"。
    """
    errors = []
    if expected_range is None:
        if is_multiphysics is False:
            m = re.search(r"overall[^0-9]{0,20}(\d+(?:\.\d+)?)", text, re.IGNORECASE)
            if m and float(m.group(1)) > 0:
                errors.append(f"非多物理场项目却出现 overall={m.group(1)}")
        # is_multiphysics 未知或 True 且无区间 → 不强制检查具体数字
        return errors
    m = re.search(r"overall[^0-9]{0,20}(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if not m:
        m = re.search(r"(?:综合评分|overall)[^0-9]{0,20}(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if not m:
        return ["未提及综合评分（overall）"]
    score = float(m.group(1))
    lo, hi = expected_range
    if not (lo <= score <= hi):
        errors.append(f"overall={score} 不在期望区间 [{lo}, {hi}]")
    return errors


def assert_non_multiphysics(text: str) -> list[str]:
    """断言：非多物理场判定（求解器物理场维度未激活，权重 0 或分数缺失）。

    CLI 综合报告始终有 overall_score（其他维度评分），故不能据此判断。
    判断依据（任一即通过）：
    1. 明确文字标记（"非多物理场/未激活"等，来自 rules.json）
    2. solver_physics 权重为 0% 或 enhancement 维度缺失
    3. 完整评估 JSON 中完全没有 solver_physics 提及（单语言/非多物理场项目）
    """
    errors = []
    if not text.strip():
        return ["无文本输出"]
    # 判据1：明确文字标记（来源 rules.json，含"未启用/未激活"等）
    if re.search(r"(?i)" + "|".join(NON_MULTIPHYSICS_MARKERS), text):
        return []
    # 判据2：solver_physics 权重 0% 或 enhancement 维度缺失
    if re.search(r"solver_physics\*?0%|solver_physics[^0-9]{0,10}0\.0|solver_physics_enhancement", text, re.IGNORECASE):
        if not re.search(r'"solver_physics_enhancement":\s*\{\s*"score"', text, re.IGNORECASE):
            return []
        return errors  # 有 enhancement 详情 → 非多物理场判定无法确认
    # 判据3：完整评估 JSON（含 project 字段）且全文本无任何 solver 提及 → 非多物理场
    if re.search(r'"project"\s*:\s*"[^"]+"', text) and not re.search(r"(?i)solver", text):
        return []
    errors.append("无法确认非多物理场判定（未找到 solver_physics 0% 或明确说明）")
    return errors


def assert_all(text: str, expect: dict) -> list[str]:
    """运行全部结构断言。expect 含 dimension_fields/overall_range/is_multiphysics。"""
    errors = []
    errors += assert_report_structure(text, expect.get("dimension_fields", []))
    errors += assert_no_hallucination(text)
    if expect.get("is_multiphysics") is True:
        errors += assert_overall_mentions(text, expect.get("overall_range"), True)
    elif expect.get("is_multiphysics") is False:
        errors += assert_non_multiphysics(text)
    return errors
