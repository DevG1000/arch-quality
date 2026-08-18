"""规则加载：从 rules.json 单一事实源读取断言规则。

Python 断言器与 opencode 插件 hook（agent-assert.js）共享此文件。
rules.json 缺失时回退到内置默认值。
"""

import json
import os

_RULES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules.json"
)

_DEFAULTS = {
    "eval_bash_prefixes": ["arch-quality", "python -m arch_quality"],
    "readonly_bash_prefixes": [
        "Test-Path", "Get-ChildItem", "Get-Content",
        "git status", "git log", "git diff",
        "Select-String", "where.exe",
    ],
    "forbidden_tools": ["edit", "write", "apply_patch"],
    "forbidden_bash_patterns": [r"^\s*rm\s"],
    "overall_range": [0, 100],
    "required_solver_fields": ["solver_physics_enhancement"],
    "non_multiphysics_markers": [
        "非多物理场", "不是多物理场", "未识别为多物理场",
        "未启用", "未激活", "not a multiphysics",
    ],
    "hallucinated_patterns": [
        r"(?i)approval\s+number", r"(?i)patent", r"(?i)invoice",
        r"(?i)refund", r"(?i)transaction\s+id",
    ],
    "dimension_fields": [
        "boundary_integrity", "coupling_architecture",
        "extension_support", "data_transfer",
    ],
    "assert_mode": "log",
}


def load_rules() -> dict:
    """加载规则；rules.json 缺失或损坏时回退默认值。"""
    try:
        with open(_RULES_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULTS)
    merged = dict(_DEFAULTS)
    merged.update({k: v for k, v in data.items() if v is not None})
    return merged
