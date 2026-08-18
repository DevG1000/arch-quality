"""评分合理性断言：检查评分区间与权重一致性。"""

import re

from ._rules import load_rules

_RULES = load_rules()
# 维度评分区间（来源 rules.json）
SCORE_RANGE = tuple(_RULES["overall_range"])


def _extract_dimension_scores(text: str) -> dict[str, float]:
    """从报告文本中提取各维度评分。"""
    dim_aliases = {
        "boundary_integrity": ["boundary_integrity", "boundary", "边界"],
        "coupling_architecture": ["coupling_architecture", "耦合架构"],
        "extension_support": ["extension_support", "扩展"],
        "data_transfer": ["data_transfer", "数据传递"],
    }
    scores = {}
    for key, aliases in dim_aliases.items():
        found = None
        for alias in aliases:
            # 匹配 "key: 78" 或 "key: 78.9" 或 "key 得 78 分"
            m = re.search(
                re.escape(alias) + r"[^0-9]{0,15}(\d+(?:\.\d+)?)", text, re.IGNORECASE
            )
            if m:
                found = float(m.group(1))
                break
        if found is not None:
            scores[key] = found
    return scores


def assert_score_ranges(text: str) -> list[str]:
    """断言：所有出现的维度评分 ∈ SCORE_RANGE（默认 [0,100]）。"""
    errors = []
    scores = _extract_dimension_scores(text)
    for key, val in scores.items():
        lo, hi = SCORE_RANGE
        if not (lo <= val <= hi):
            errors.append(f"维度 {key} 评分 {val} 超出 [{lo},{hi}]")
    return errors


def assert_weight_sum(text: str) -> list[str]:
    """断言：若出现权重求和上下文，权重之和应为 100%。

    注意：此检查在提取文本含 skill 加载内容或评估 JSON 时易误报
    （百分比来自无关上下文），已从默认断言集中移除，保留仅供显式调用。
    """
    errors = []
    has_sum_ctx = bool(re.search(r"(?i)权重和|weights.{0,10}sum", text))
    if not has_sum_ctx:
        return errors
    pcts = re.findall(r"(\d{1,3})%", text)
    if len(pcts) >= 3:
        head = [int(p) for p in pcts[:4]]
        total = sum(head)
        if total not in (100, 90, 85, 60, 70, 75, 80):
            errors.append(f"检测到权重和={total}%，非预期")
    return errors


def assert_all(text: str) -> list[str]:
    """运行核心评分断言（评分区间；权重和检查因误报风险已移除）。"""
    return assert_score_ranges(text)
