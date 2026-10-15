# -*- coding: utf-8 -*-
"""
arch_origin.py — 违规来源分类器（WP-6）

统一判定文件路径的来源类别，供各引擎与报告生成器共用，用于报告自动标注
[third-party] / [test]：

    classify_path(path) -> "third_party" | "test" | "first_party"

判定遵循"目录名 + 文件名模式"启发式（对齐既有各引擎的 THIRD_PARTY_DIR_NAMES /
_is_test_file 口径），并保持保守：无法确定时返回 first_party（不误标）。
"""

import re
from pathlib import PurePosixPath

# 第三方/外部代码目录名（并集，覆盖 GCS/ACL/solver/multilang 既有标记）
THIRD_PARTY_DIR_NAMES = {
    "third_party", "thirdparty", "3rdparty", "third-party",
    "external", "extern", "vendor", "vendored",
    "deps", "dependencies", "libs", "external_libs",
    "contrib", "umfpack", "subprojects", "_deps",
}

# 测试/QA/示例相关目录名片段
TEST_DIR_MARKERS = {
    "test", "tests", "testing", "qa", "qabugs", "draw",
    "sample", "samples", "example", "examples", "demo", "demos",
    "benchmark", "benchmarks", "unittest", "unittests",
    "testdata", "test_data", "fixtures", "gtests",
}

# 测试文件名模式：test_foo.*, foo_test.*, foo_test.cpp, foo.test.cpp 等
_TEST_FILE_RE = re.compile(
    r"(?:^|[/\\])(?:test|tests)[_\-.]|"
    r"[_\-.]test(?:s)?\.(?:cpp|cc|cxx|c|h|hpp|hxx|py|js|ts|java|go|rs)$|"
    r"(?:^|[/\\])test_[^/\\]+$|"
    r"\.test\.(?:cpp|py|js|ts)$",
    re.IGNORECASE,
)

# 第三方路径正则（与 arch_python_ast._THIRD_PARTY_MARKERS_RE 对齐）
_THIRD_PARTY_MARKERS_RE = re.compile(
    r"(?:third[_-]?party|vendor|external|contrib|3rd[_-]?party|thirdparty|"
    r"(?:^|[/\\])deps(?:[/\\]|$)|(?:^|[/\\])subprojects(?:[/\\]|$)|"
    r"(?:^|[/\\])_deps(?:[/\\]|$))[/\\]",
    re.IGNORECASE,
)


def _parts(path: str) -> list:
    p = str(path).replace("\\", "/")
    return [seg for seg in PurePosixPath(p).parts if seg not in ("", ".")]


def is_third_party_path(path: str) -> bool:
    """路径是否属第三方/外部代码。"""
    if _THIRD_PARTY_MARKERS_RE.search(str(path).replace("\\", "/") + "/"):
        return True
    return any(seg.lower() in THIRD_PARTY_DIR_NAMES for seg in _parts(path))


def is_test_path(path: str) -> bool:
    """路径是否属测试/QA/示例代码。"""
    p = str(path).replace("\\", "/")
    if _TEST_FILE_RE.search(p):
        return True
    return any(seg.lower() in TEST_DIR_MARKERS for seg in _parts(path))


def classify_path(path: str) -> str:
    """来源分类：third_party > test > first_party。

    第三方优先（一个 third_party 目录下的 test 文件仍归第三方，避免把
    外部代码计的债摊到本项目测试）。
    """
    if is_third_party_path(path):
        return "third_party"
    if is_test_path(path):
        return "test"
    return "first_party"


def classify_paths(paths) -> str:
    """对一组路径取"最重"来源：third_party > test > first_party。

    用于一条违规涉及多个文件时（如循环依赖），判定整体来源。
    """
    rank = {"first_party": 0, "test": 1, "third_party": 2}
    best = "first_party"
    for p in paths:
        c = classify_path(p)
        if rank[c] > rank[best]:
            best = c
    return best


ORIGIN_TAGS = {
    "third_party": "[third-party]",
    "test": "[test]",
}


def origin_tag(origin: str) -> str:
    """来源 → 报告标记；first_party 返回空串（不标注）。"""
    return ORIGIN_TAGS.get(origin, "")
