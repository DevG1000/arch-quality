"""commands_meta.py — 7 个评估 CLI 入口的参数元数据（单一事实源）。

界面据此自动渲染表单，避免硬编码 UI。每个入口定义：
- entry / module: 命令调用形式（pyproject 命令或 python -m 模块）
- label / description: 界面展示
- params: 参数定义（类型、choices、默认值、联动规则）
- mutex: 互斥校验规则（前端提示 + 后端校验共用）

参数类型：
  path   -> 路径输入框 + 浏览按钮
  str    -> 文本框
  choice -> 下拉选择
  bool   -> 复选框
  multi  -> 多值输入（空格分隔，如 --test-dirs）
"""

COMMANDS = {
    "comprehensive": {
        "entry": "python -m arch_quality",
        "module": "arch_quality.arch_report:main",
        "label": "综合评估报告",
        "description": "全部 4 维指标 + 增强引擎（多语言/模板/数值/求解器/几何），输出 JSON + Markdown",
        "params": [
            {"name": "root", "type": "path", "default": ".", "required": True,
             "help": "项目根目录"},
            {"name": "build_dir", "flag": "--build-dir", "type": "path",
             "help": "构建目录（包含 SWIG 生成文件的目录，如 build/）"},
            {"name": "test_dirs", "flag": "--test-dirs", "type": "multi",
             "help": "out-of-tree 测试根目录（相对于项目根，多个用空格分隔）"},
            {"name": "report_mode", "flag": "--report-mode", "type": "choice",
             "choices": ["local", "central"], "default": "central",
             "help": "报告存储模式：local=项目内 .opencode/，central=用户配置目录集中存储"},
            {"name": "project_name", "flag": "--project-name", "type": "str",
             "visible_when": {"report_mode": "central"},
             "help": "集中模式下的项目名（默认从根目录推断）"},
            {"name": "profile", "flag": "--profile", "type": "multicheck",
             "choices": ["standard", "multilang", "numerical", "template",
                         "solver-physics", "geometry-consistency", "anti-corruption"],
             "help": "显式 profile（可多选，多个 profile 的引擎集取并集）"},
            {"name": "json", "flag": "--json", "type": "bool",
             "help": "输出 JSON 格式报告"},
            {"name": "md", "flag": "--md", "type": "bool",
             "help": "输出 Markdown 格式报告"},
        ],
        "mutex": [],
    },
    "standard": {
        "entry": "python -m arch_quality.arch_metrics_standard",
        "module": "arch_quality.arch_metrics_standard:main",
        "label": "标准评估",
        "description": "仅标准 4 维指标（结构/设计/文档/演进）",
        "params": [
            {"name": "root", "type": "path", "default": ".", "required": True,
             "help": "项目根目录"},
            {"name": "scan", "flag": "--scan", "type": "bool", "help": "全量扫描"},
            {"name": "metrics", "flag": "--metrics", "type": "bool", "help": "输出指标"},
        ],
        "mutex": [],
    },
    "multilang": {
        "entry": "python -m arch_quality.arch_metrics_multilang",
        "module": "arch_quality.arch_metrics_multilang:main",
        "label": "多语言评估",
        "description": "多语言混合依赖 6 维 + 12 MLR 规则",
        "params": [
            {"name": "root", "type": "path", "default": ".", "required": True,
             "help": "项目根目录"},
            {"name": "build_dir", "flag": "--build-dir", "type": "path",
             "help": "构建目录（包含 SWIG 生成文件的目录，如 build/）"},
            {"name": "full", "flag": "--full", "type": "bool",
             "help": "完整评估（6 维 + MLR）"},
            {"name": "scan", "flag": "--scan", "type": "bool", "help": "扫描并输出"},
            {"name": "mlr_only", "flag": "--mlr-only", "type": "bool", "help": "仅输出 MLR 规则"},
        ],
        "mutex": [["full", "mlr_only"]],
    },
    "template": {
        "entry": "python -m arch_quality.arch_metrics_template",
        "module": "arch_quality.arch_metrics_template:main",
        "label": "模板元编程",
        "description": "模板元编程与编译时依赖膨胀 6 维 + 12 MLR 规则",
        "params": [
            {"name": "root", "type": "path", "default": ".", "required": True,
             "help": "项目根目录"},
            {"name": "build_dir", "flag": "--build-dir", "type": "path",
             "help": "构建目录"},
            {"name": "full", "flag": "--full", "type": "bool",
             "help": "完整评估（6 维 + MLR）"},
            {"name": "mlr_only", "flag": "--mlr-only", "type": "bool", "help": "仅输出 MLR 规则"},
        ],
        "mutex": [["full", "mlr_only"]],
    },
    "numerical": {
        "entry": "python -m arch_quality.arch_metrics_numerical_accuracy",
        "module": "arch_quality.arch_metrics_numerical_accuracy:main",
        "label": "数值精度",
        "description": "数值算法正确性与精度保障 6 维 + 12 NVR 规则",
        "params": [
            {"name": "root", "type": "path", "default": ".", "required": True,
             "help": "项目根目录"},
            {"name": "mms_pobs", "flag": "--mms-pobs", "type": "str",
             "help": "MMS 观察点（如 2.001），超过则覆盖 MMS 案例"},
            {"name": "json", "flag": "--json", "type": "bool", "help": "输出 JSON 格式"},
            {"name": "full", "flag": "--full", "type": "bool",
             "help": "完整评估（6 维 + NVR）"},
            {"name": "nvr_only", "flag": "--nvr-only", "type": "bool", "help": "仅输出 NVR 规则"},
        ],
        "mutex": [["full", "nvr_only"]],
    },
    "solver": {
        "entry": "python -m arch_quality.arch_metrics_solver_physics",
        "module": "arch_quality.arch_metrics_solver_physics:main",
        "label": "求解器物理场",
        "description": "求解器与物理场模块化架构 4 维 + 12 MPR 规则",
        "params": [
            {"name": "root", "type": "path", "default": ".", "required": True,
             "help": "项目根目录"},
            {"name": "json", "flag": "--json", "type": "bool", "help": "输出 JSON 格式"},
            {"name": "mpr_only", "flag": "--mpr-only", "type": "bool", "help": "仅输出 MPR 规则"},
        ],
        "mutex": [],
    },
    "geometry": {
        "entry": "python -m arch_quality.arch_metrics_geometry_consistency",
        "module": "arch_quality.arch_metrics_geometry_consistency:main",
        "label": "几何一致性",
        "description": "几何内核与数学数据结构一致性评估",
        "params": [
            {"name": "root", "type": "path", "default": ".", "required": True,
             "help": "项目根目录"},
            {"name": "json", "flag": "--json", "type": "bool", "help": "输出 JSON 格式"},
            {"name": "gcs_only", "flag": "--gcs-only", "type": "bool", "help": "仅输出 GCS 规则"},
        ],
        "mutex": [],
    },
    "anti_corruption": {
        "entry": "python -m arch_quality.arch_metrics_anti_corruption",
        "module": "arch_quality.arch_metrics_anti_corruption:main",
        "label": "防腐层评估",
        "description": "外部内核/数据交换封装与防腐层评估",
        "params": [
            {"name": "root", "type": "path", "default": ".", "required": True,
             "help": "项目根目录"},
            {"name": "json", "flag": "--json", "type": "bool", "help": "输出 JSON 格式"},
            {"name": "acl_only", "flag": "--acl-only", "type": "bool", "help": "仅输出 ACL 规则"},
        ],
        "mutex": [],
    },
}

# 各命令顺序（界面 Tab 展示顺序）
COMMAND_ORDER = ["comprehensive", "standard", "multilang", "template",
                 "numerical", "solver", "geometry", "anti_corruption"]


def get_command(cmd_id: str) -> dict:
    """按 id 取命令定义；未知 id 抛 KeyError。"""
    return COMMANDS[cmd_id]


def check_mutex(cmd_id: str, selected: dict) -> list:
    """检查互斥规则，返回违反项列表（每条为 (flagA, flagB)）。"""
    cmd = COMMANDS[cmd_id]
    violations = []
    for group in cmd.get("mutex", []):
        active = [flag for flag in group if selected.get(flag)]
        if len(active) > 1:
            violations.append(tuple(active))
    return violations


def build_argv(cmd_id: str, values: dict) -> list:
    """根据表单值构造命令行 argv 列表。

    values 为 {参数名: 值} 字典。仅包含非空/非默认的参数。
    """
    cmd = COMMANDS[cmd_id]
    argv = []
    for p in cmd["params"]:
        name = p["name"]
        val = values.get(name)
        flag = p.get("flag")
        ptype = p["type"]

        if name == "root":
            # root 是位置参数
            argv.append(str(val) if val else ".")
            continue
        if flag is None:
            continue
        # 联动规则：不满足 visible_when 时跳过该参数
        rule = p.get("visible_when")
        if rule is not None:
            if not all(str(values.get(k)) == str(v) for k, v in rule.items()):
                continue
        if ptype == "bool":
            if val:
                argv.append(flag)
        elif ptype == "multicheck":
            # 值为数组：每个选中项追加一次 flag + 值
            items = val if isinstance(val, (list, tuple)) else []
            for item in items:
                argv.append(flag)
                argv.append(str(item))
        elif ptype in ("str", "path", "choice"):
            if val not in (None, ""):
                argv.append(flag)
                argv.append(str(val))
        elif ptype == "multi":
            if val:
                items = [x for x in str(val).split() if x]
                if items:
                    argv.append(flag)
                    argv.extend(items)
    return argv


def build_command_string(cmd_id: str, values: dict) -> str:
    """构造可直接复制的命令行字符串。"""
    cmd = COMMANDS[cmd_id]
    argv = build_argv(cmd_id, values)
    return " ".join([cmd["entry"]] + argv)