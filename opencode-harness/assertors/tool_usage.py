"""工具使用断言：检查 agent 是否按预期调用工具（约束/选择正确性）。"""

import re

from ._rules import load_rules

_RULES = load_rules()
# 评估命令白名单前缀（与 rules.json / opencode.json 一致）
EVAL_BASH_PREFIXES = tuple(_RULES["eval_bash_prefixes"])
# 只读探索命令（不算评估但应放行，避免误报）
READONLY_BASH_PREFIXES = tuple(_RULES["readonly_bash_prefixes"])
# 评估任务应只读，不应触发写操作
FORBIDDEN_TOOLS = tuple(_RULES["forbidden_tools"])


def extract_tool_calls(events: list[dict]) -> list[dict]:
    """从 JSON 事件流中提取工具调用序列。

    opencode run --format json 的 tool_use 事件结构：
      顶层 type == "tool_use"，part.type == "tool"，
      part.tool == 工具名，part.state 为 {status, input, output}。
    """
    calls = []
    for ev in events:
        part = ev.get("part") or {}
        if part.get("type") != "tool":
            continue
        state = part.get("state")
        if isinstance(state, dict):
            state_obj = state
        else:
            state_obj = {}
        calls.append({
            "tool": part.get("tool", ""),
            "state": state_obj.get("status", ""),
            "input": state_obj.get("input", {}) or part.get("input", {}),
            "output": state_obj.get("output", "") or "",
        })
    return calls


def _is_eval_command(cmd: str) -> bool:
    """判断命令是否命中评估命令白名单。

    兼容 bash 前置环境变量赋值，如 `$env:PYTHONIOENCODING="utf-8"; python -m arch_quality ...`
    """
    import re
    cleaned = re.sub(r'^\s*(?:\$env:[^;]+;|\$[A-Za-z_]\w*=.*?;|export\s+[A-Za-z_]\w*=.*?;)\s*',
                     '', cmd, flags=re.DOTALL)
    stripped = cleaned.strip()
    return any(stripped.startswith(p) for p in EVAL_BASH_PREFIXES)


def _is_readonly_command(cmd: str) -> bool:
    """判断命令是否为只读探索（含管道/参数均算，仅看首命令）。"""
    import re
    cleaned = re.sub(r'^\s*(?:\$env:[^;]+;|\$[A-Za-z_]\w*=.*?;)\s*', '', cmd)
    first = cleaned.strip().split("|")[0].strip()
    return any(first.startswith(p) for p in READONLY_BASH_PREFIXES)


def assert_tool_choice(tool_calls: list[dict]) -> list[str]:
    """断言：agent 实际调用了评估命令。

    至少一条 bash 命中评估白名单即通过；探索命令（只读）不算评估但也不报错。
    """
    errors = []
    if not tool_calls:
        return ["未捕获到任何工具调用（可能 agent 直接臆造结果）"]
    bash_calls = [c for c in tool_calls if c["tool"] == "bash"]
    if not bash_calls:
        return ["未调用 bash 工具（无法执行评估命令）"]
    for c in bash_calls:
        cmd = str(c.get("input", {}).get("command", ""))
        if _is_eval_command(cmd):
            return []  # 命中评估命令即视为正确
    # 有 bash 调用但都非评估命令
    return [f"bash 调用均未命中评估命令白名单（{len(bash_calls)} 条）"]


def assert_no_forbidden_write(tool_calls: list[dict]) -> list[str]:
    """断言：未调用写工具（评估任务应只读）。"""
    bad = [c for c in tool_calls if c["tool"] in FORBIDDEN_TOOLS]
    if bad:
        return [f"检测到越权写操作: {[c['tool'] for c in bad]}"]
    return []


def assert_no_doom_loop(tool_calls: list[dict]) -> list[str]:
    """断言：无相同工具调用重复 3 次（doom_loop 兜底未触发）。"""
    from collections import Counter
    keys = [(c.get("tool", ""), str(c.get("input", {}))) for c in tool_calls]
    for (tool, inp), cnt in Counter(keys).items():
        if cnt >= 3:
            return [f"疑似 doom_loop: 工具 {tool} 相同输入调用 {cnt} 次"]
    return []


def assert_all(tool_calls: list[dict]) -> list[str]:
    """运行全部工具断言，返回错误列表（空 = 通过）。"""
    errors = []
    errors += assert_tool_choice(tool_calls)
    errors += assert_no_forbidden_write(tool_calls)
    errors += assert_no_doom_loop(tool_calls)
    return errors
