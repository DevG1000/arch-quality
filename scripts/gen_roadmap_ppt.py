"""生成《工业软件架构质量评估体系 Roadmap》PPT。

参照 scripts/gen_harness_ppt.py 的视觉风格（浅色主题 + Blank 版式 + 自绘形状），
16:9。20 页。每页含页眉图标（左上角圆角方块 + Unicode 符号）+ 主题小图形。

运行: python scripts/gen_roadmap_ppt.py
输出: docs/ppt/工业软件架构质量评估体系Roadmap.pptx
"""

import os

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---- 配色（对齐现有 PPT 风格）----
NAVY = RGBColor(0x1F, 0x3A, 0x5F)       # 深蓝标题/主色
DARK = RGBColor(0x33, 0x33, 0x33)       # 深灰正文
GRAY = RGBColor(0x66, 0x66, 0x66)       # 浅灰副题
ACCENT = RGBColor(0xC0, 0x50, 0x4D)     # 强调红
LIGHT = RGBColor(0xF2, 0xF2, 0xF2)      # 浅灰背景
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x2E, 0x7D, 0x32)      # 通过绿
PENDING = RGBColor(0xB8, 0xB8, 0xB8)    # 待补灰
GOLD = RGBColor(0xC8, 0x9B, 0x3C)       # 琥珀（配属）
TEAL = RGBColor(0x1F, 0x7A, 0x8C)       # 青绿（治理）

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "ppt",
                        "工业软件架构质量评估体系Roadmap.pptx")


def _set_text(tf, text, size, color, bold=False, align=PP_ALIGN.LEFT,
              line_spacing=1.0):
    tf.word_wrap = True
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        run = p.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color


def add_textbox(slide, x, y, w, h, text, size=18, bold=False, color=DARK,
                align=PP_ALIGN.LEFT, line_spacing=1.0):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    _set_text(tb.text_frame, text, size, color, bold, align, line_spacing)
    return tb


def add_shape(slide, shape, x, y, w, h, fill=None, line=None, line_w=1.0):
    sp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w),
                                Inches(h))
    sp.shadow.inherit = False
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(line_w)
    return sp


def shape_text(sp, text, size=14, color=WHITE, bold=True,
               align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE):
    tf = sp.text_frame
    tf.vertical_anchor = anchor
    tf.margin_left = Inches(0.05)
    tf.margin_right = Inches(0.05)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    _set_text(tf, text, size, color, bold, align)


def add_icon(slide, symbol):
    """页眉图标：左上角深蓝圆角方块 + 白色符号"""
    sp = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE,
                   0.2, 0.15, 0.55, 0.55, fill=NAVY)
    shape_text(sp, symbol, size=22, color=WHITE, bold=True)


def add_title(slide, chapter, title, subtitle=None):
    add_icon(slide, "·")
    add_textbox(slide, 0.95, 0.38, 11.5, 0.4, chapter, size=13, bold=True,
                color=ACCENT)
    add_textbox(slide, 0.95, 0.78, 11.5, 0.9, title, size=30, bold=True,
                color=NAVY)
    if subtitle:
        add_textbox(slide, 0.95, 1.62, 11.5, 0.5, subtitle, size=15,
                    color=GRAY)


def add_footer(slide, page_no, tag="arch-quality Roadmap"):
    add_textbox(slide, 0.6, 7.05, 9, 0.3, tag, size=10, color=GRAY)
    add_textbox(slide, 12.3, 7.05, 0.8, 0.3, str(page_no), size=11,
                color=GRAY, align=PP_ALIGN.RIGHT)


def add_card(slide, x, y, w, h, header, items, head_fill=NAVY, body_fill=LIGHT,
             head_color=WHITE, item_size=13):
    sp = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h,
                   fill=body_fill)
    hp = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, 0.42,
                   fill=head_fill)
    shape_text(hp, header, size=14, color=head_color, bold=True)
    add_textbox(slide, x + 0.18, y + 0.55, w - 0.36, h - 0.7,
                "\n".join("· " + i for i in items),
                size=item_size, color=DARK, line_spacing=1.25)
    return sp


def add_table(slide, x, y, w, data, header=True, col_widths=None,
              font=12, row_h=0.34, col_h=None):
    rows, cols = len(data), len(data[0])
    if col_h is None:
        col_h = row_h
    shape = slide.shapes.add_table(rows, cols, Inches(x), Inches(y),
                                   Inches(w), Inches(col_h * rows)).table
    if col_widths:
        for ci, cw in enumerate(col_widths):
            shape.columns[ci].width = Inches(cw)
    else:
        for ci in range(cols):
            shape.columns[ci].width = Inches(w / cols)
    for ri in range(rows):
        shape.rows[ri].height = Inches(col_h if (ri == 0 and header) else row_h)
        for ci in range(cols):
            cell = shape.cell(ri, ci)
            cell.margin_left = Inches(0.06)
            cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.02)
            cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.text = str(data[ri][ci])
            for p in cell.text_frame.paragraphs:
                p.alignment = PP_ALIGN.LEFT
                for run in p.runs:
                    run.font.size = Pt(font)
                    run.font.color.rgb = WHITE if (header and ri == 0) else DARK
                    if header and ri == 0:
                        run.font.bold = True
            if header and ri == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = NAVY
            elif ri == 0 and ci == 0 and data[0][0] == "":
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE
    return shape


def draw_concentric(slide, cx, cy, rings, center_fill=GREEN):
    """rings: [(radius_in, fill/None, line_color, line_w)] 从外到内"""
    for r, fill, line, lw in rings:
        x, y = cx - r, cy - r
        sp = add_shape(slide, MSO_SHAPE.OVAL, x, y, 2 * r, 2 * r, fill=fill,
                       line=line, line_w=lw)
        sp.shadow.inherit = False
    return sp


def draw_layers(slide, x, y, w, labels, colors, h=0.55, gap=0.18,
                font=13):
    """自上而下堆叠色块。labels 按视觉从上到下排列"""
    for i, (label, color) in enumerate(zip(labels, colors)):
        yy = y + i * (h + gap)
        sp = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, yy, w, h,
                       fill=color)
        shape_text(sp, label, size=font, color=WHITE, bold=True)


def draw_grid(slide, items, x0, y0, w, h, cols, gap=0.14, font=11):
    """items: [(num, name, color)] 按行填充"""
    rows = (len(items) + cols - 1) // cols
    cw = (w - (cols - 1) * gap) / cols
    ch = (h - (rows - 1) * gap) / rows
    for idx, item in enumerate(items):
        num, name, color = item[0], item[1], item[2]
        badge = item[3] if len(item) > 3 else None
        r, c = divmod(idx, cols)
        x = x0 + c * (cw + gap)
        y = y0 + r * (ch + gap)
        sp = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, cw, ch,
                       fill=color)
        tf = sp.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.1)
        tf.margin_right = Inches(0.1)
        tf.margin_top = Inches(0.02)
        tf.margin_bottom = Inches(0.02)
        _set_text(tf, num, size=16, color=WHITE, bold=True,
                  align=PP_ALIGN.LEFT)
        p = tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = name
        run.font.size = Pt(font)
        run.font.color.rgb = WHITE
        run.font.bold = False
        if badge:
            pb = tf.add_paragraph()
            pb.alignment = PP_ALIGN.LEFT
            rb = pb.add_run()
            rb.text = badge
            rb.font.size = Pt(7.5)
            rb.font.bold = True
            rb.font.color.rgb = GOLD


# ================================================================
# 各页
# ================================================================

def s01_cover(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    draw_concentric(s, 6.67, 1.85, [
        (1.15, None, NAVY, 2.5),
        (0.78, None, ACCENT, 2.0),
        (0.34, GREEN, None, 0),
    ])
    add_textbox(s, 1.0, 2.7, 11.33, 1.1, "工业软件架构质量评估体系 Roadmap",
                size=40, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    add_textbox(s, 1.0, 3.85, 11.33, 0.6,
                "编制标准体系 · 开发 AI agent 评估系统 · 形成开发能力",
                size=20, color=GRAY, align=PP_ALIGN.CENTER)
    draw_layers(slide, 4.2, 4.75, 5.0,
                ["能力层 · 开发能力", "产品层 · AI agent 评估系统",
                 "内容层 · 标准体系"],
                [GREEN, ACCENT, NAVY], h=0.55, gap=0.16, font=13)
    add_footer(slide, 1, "基于 arch-quality 项目 · 2026-08")


def s02_toc(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "CONTENTS", "目录",
              "背景与现状 → 远景与演进 → 回顾 P0–P4 → 前瞻 H1–H4 → 验证与能力 → 指标与治理")
    chapters = [
        ("01", "背景与现状", "八项工业维度 · 四维已落地", NAVY),
        ("02", "远景与演进", "三层架构 · 从 P0 到 H4 的完整时间轴", ACCENT),
        ("03", "回顾 P0–P4", "历史开发阶段：奠基→深化→验证→评审→智能体", GREEN),
        ("04", "前瞻 H1–H4", "可信化→扩展化→全维化→生态化", GOLD),
        ("05", "验证与能力", "双交叉验证 · 三方一致性 · 能力体系", PENDING),
        ("06", "指标与治理", "KPI · 风险 · 季度评审与知识沉淀", TEAL),
    ]
    y = 1.75
    for num, t, sub, color in chapters:
        bar = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 1.0, y, 0.18, 0.82,
                        fill=color)
        add_textbox(slide, 1.45, y + 0.02, 1.0, 0.8, num, size=20, bold=True,
                    color=color)
        add_textbox(slide, 2.45, y + 0.02, 9.5, 0.45, t, size=18, bold=True,
                    color=NAVY)
        add_textbox(slide, 2.45, y + 0.40, 9.5, 0.4, sub, size=11.5,
                    color=GRAY)
        y += 0.85
    add_footer(s, 2)
def s03_background(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "01 背景与现状", "工业软件为何需要专属评估体系",
              "通用维度覆盖不了工业软件计算栈的特殊性")
    # 左卡：普通软件
    add_card(slide, 0.85, 2.3, 5.7, 1.75, "普通软件", [
        "标准架构质量 4 维即可覆盖：",
        "结构质量 / 设计质量 / 文档质量 / 演进质量",
    ], head_fill=NAVY, item_size=13)
    # 右卡：工业软件
    add_card(slide, 6.75, 2.3, 5.75, 1.75, "工业软件", [
        "计算栈特殊性：多语言混编 · 模板元编程 · 数值求解 ·",
        "几何内核 · 多物理场 · HPC 异构 · 10-30 年寿命 · 外部科学内核",
    ], head_fill=ACCENT, item_size=13)
    add_textbox(slide, 0.85, 4.25, 11.7, 0.4,
                "→ 在通用维度之上，新增 8 项工业软件特有维度（全称，编号对应《工业软件与普通软件异同分析》§2.1-2.8）",
                size=14, bold=True, color=NAVY)
    items = [
        ("1", "多语言混合架构的跨语言依赖", NAVY),
        ("2", "模板元编程与编译时依赖膨胀", NAVY),
        ("3", "数值算法正确性与精度保障", NAVY),
        ("4", "几何内核与科学数据结构一致性", NAVY, "待完备性证明"),
        ("5", "求解器与物理场模块化架构模式识别", NAVY),
        ("6", "并行/异构计算架构（HPC/GPU）", NAVY, "待完备性证明"),
        ("7", "超长生命周期中的“化石代码”与技术债", NAVY, "待完备性证明"),
        ("8", "外部科学内核与几何内核的封装与防腐层", NAVY, "待完备性证明"),
    ]
    draw_grid(slide, items, 0.85, 4.8, 11.7, 1.85, 4, font=10)
    add_footer(s, 3)

def s04_vision(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "02 远景与演进", "三层架构：一个体系、一个系统、一种能力",
              "知识为基（下）· 系统为用（中）· 能力为纲（上）")
    draw_layers(slide, 1.2, 2.6, 4.4,
                ["能力层 · 开发能力\n（方法论 + 验证体系 + 治理机制）",
                 "产品层 · AI agent 评估系统\n（引擎 (AI skill) + 智能体编排 + 报告 + CI 门禁）",
                 "内容层 · 标准体系\n（评什么、怎么评：维度/规则/权重/案例库）"],
                [GREEN, ACCENT, NAVY], h=1.15, gap=0.2, font=14)
    # 下箭头：能力层 → 产品层（验证保障可信）
    add_shape(slide, MSO_SHAPE.DOWN_ARROW, 5.9, 3.76, 0.5, 0.34, fill=GRAY)
    add_textbox(slide, 6.6, 3.66, 5.9, 0.6, "能力层 → 产品层：验证保障可信",
                size=13, color=GRAY, bold=True)
    # 上箭头：内容层 → 产品层（标准落地为评估）
    add_shape(slide, MSO_SHAPE.UP_ARROW, 5.9, 5.14, 0.5, 0.34, fill=GRAY)
    add_textbox(slide, 6.6, 5.04, 5.9, 0.6, "内容层 → 产品层：标准落地为评估",
                size=13, color=GRAY, bold=True)
    add_textbox(slide, 6.6, 2.95, 5.9, 0.7,
                "标准为产品提供权威性；产品把标准落地为可执行评估；\n"
                "能力层通过验证体系保障产品可信，并持续产出标准。",
                size=13.5, color=DARK, line_spacing=1.2)
    add_textbox(slide, 6.6, 4.35, 5.9, 0.5,
                "智能体编排：AI 智能体自动调度评估流程\n（扫描 → 评分 → 规则检查 → 报告），与确定性引擎 (AI skill)互补",
                size=12, color=GRAY, line_spacing=1.15)
    add_textbox(slide, 6.6, 6.2, 5.9, 0.5,
                "三者互相依赖，但每个阶段只有一个主攻方向",
                size=14, color=ACCENT, bold=True)
    add_footer(s, 4)
def add_labeled_text(slide, x, y, w, h, lines, label_color, font=10.5):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, (label, content) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = 1.05
        r1 = p.add_run()
        r1.text = label
        r1.font.size = Pt(font)
        r1.font.bold = True
        r1.font.color.rgb = label_color
        r2 = p.add_run()
        r2.text = content
        r2.font.size = Pt(font)
        r2.font.color.rgb = DARK
    return tb


def add_phase_card(slide, x, y, w, h, phase, date, color, body_lines, font=10.5):
    card = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=WHITE,
                     line=GRAY, line_w=1.0)
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, 0.12, h, fill=color)
    hp = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x + 0.28, y + 0.07, 1.8,
                   h - 0.14, fill=color)
    shape_text(hp, phase + "\n" + date, size=11, color=WHITE, bold=True)
    add_labeled_text(slide, x + 2.28, y + 0.02, w - 2.5, h - 0.04, body_lines,
                     color, font=font)


def _phase_strip(slide, ty, nodes, color):
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 1.3, ty + 0.14, 10.7, 0.04,
              fill=GRAY)
    for name, x in nodes:
        add_shape(slide, MSO_SHAPE.OVAL, x - 0.14, ty + 0.05, 0.28, 0.28,
                  fill=None, line=color, line_w=1.5)
        add_shape(slide, MSO_SHAPE.OVAL, x - 0.08, ty + 0.11, 0.16, 0.16,
                  fill=color)
        add_textbox(slide, x - 0.6, ty - 0.38, 1.2, 0.3, name, size=12,
                    bold=True, color=color, align=PP_ALIGN.CENTER)


def _add_alt_card(slide, cx, top, w, h, phase, date, color, body_lines,
                  font=9):
    x = cx - w / 2.0
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, top, w, h, fill=WHITE,
              line=GRAY, line_w=1.0)
    hp = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, top, w, 0.5,
                   fill=color)
    shape_text(hp, phase + "\n" + date, size=9.5, color=WHITE, bold=True)
    add_labeled_text(slide, x + 0.12, top + 0.56, w - 0.24, h - 0.62,
                     body_lines, color, font=font)


def _add_connector(slide, cx, y1, y2):
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, cx - 0.02, y1, 0.04,
              y2 - y1, fill=GRAY)


def _add_node(slide, cx, y, color):
    add_shape(slide, MSO_SHAPE.OVAL, cx - 0.13, y - 0.13, 0.26, 0.26,
              fill=None, line=color, line_w=1.5)
    add_shape(slide, MSO_SHAPE.OVAL, cx - 0.07, y - 0.07, 0.14, 0.14,
              fill=color)


def s05_p_cards(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "03 回顾 P0–P4", "演进回顾：P0–P4 阶段卡片",
              "时间轴按 P0→P4 顺序排列，卡片上下交错：P0 P2 P4 在上、P1 P3 在下")
    LINE_Y = 4.0
    COL = [1.6, 4.0, 6.4, 8.8, 11.2]
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 1.0, LINE_Y - 0.02, 11.3,
              0.04, fill=GRAY)
    for cx in COL:
        _add_node(slide, cx, LINE_Y, NAVY)
    cards = {
        0: ("P0 奠基", "2026-06-04", [
            ("已完成：", "v1.0 标准架构质量 4 维引擎 (AI skill)"),
            ("系统层：", "引擎 (AI skill) + 12 条规则 + 项目级报告"),
            ("能力层：", "初版回归框架（5 项目快照）")]),
        1: ("P1 多语言深化", "2026-06", [
            ("已完成：", "多语言混合架构的跨语言依赖维度 v1.1→v1.8"),
            ("系统层：", "引擎 (AI skill) + pybind11/SWIG/Tcl/内存检测"),
            ("能力层：", "5 项目回归 + CalculiX/Code_Aster 全规则验证")]),
        2: ("P2 数值精度与验证", "2026-06下–07", [
            ("已完成：", "数值算法正确性与精度保障维度（6 维+12 条）"),
            ("系统层：", "引擎 (AI skill) + 10 项目验证"),
            ("能力层：", "变异 / k 折 / 人工评审 / 动态-静态交叉验证")]),
        3: ("P3 模板元编程与评审", "2026-06-30", [
            ("已完成：", "模板元编程与编译时依赖膨胀维度（6 维+12 条）"),
            ("系统层：", "引擎 (AI skill) + O(n²)→O(1) 性能"),
            ("能力层：", "三方评审 4.36/5 + 4 项改进建议")]),
        4: ("P4 物理场与智能体", "2026-07底–08", [
            ("已完成：", "求解器与物理场模块化架构模式识别（4 维+12 条）"),
            ("系统层：", "引擎 (AI skill) + CI 门禁 + agent harness"),
            ("能力层：", "97 测试 + 9 回归 + skill 开发指南")]),
    }
    for idx in (0, 2, 4):
        phase, date, lines = cards[idx]
        cx = COL[idx]
        _add_alt_card(slide, cx, 2.25, 2.35, 1.6, phase, date, GREEN, lines)
        _add_connector(slide, cx, 3.87, 3.95)
    for idx in (1, 3):
        phase, date, lines = cards[idx]
        cx = COL[idx]
        _add_alt_card(slide, cx, 4.3, 2.35, 1.75, phase, date, GREEN, lines)
        _add_connector(slide, cx, 4.05, 4.3)
    add_textbox(slide, 1.0, 6.2, 11.3, 0.5,
                "P0–P4 五阶段全部落地，验证体系同步成形 → 为 H1–H4 提供输入",
                size=14, color=ACCENT, bold=True, align=PP_ALIGN.CENTER)
    add_footer(s, 5)

def s06_h_cards(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "04 前瞻 H1–H4", "演进前瞻：H1–H4 阶段卡片",
              "时间轴按 H1→H4 顺序排列，卡片上下交错：H1 H3 在上、H2 H4 在下")
    LINE_Y = 4.0
    COL = [2.6, 5.5, 8.4, 11.3]
    add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 1.0, LINE_Y - 0.02, 11.3,
              0.04, fill=GRAY)
    for cx in COL:
        _add_node(slide, cx, LINE_Y, GREEN)
    cards = {
        0: ("H1 可信化", "2026 Q3", [
            ("规划：", "存量能力完整可信可发布"),
            ("系统层：", "引擎 (AI skill)：覆盖度升级 / 回归 / 性能 / CI / 试点"),
            ("能力层：", "一致性入 CI + 标准元模型 v1.0 草案")]),
        1: ("H2 扩展化", "26 Q4–27 Q1", [
            ("规划：", "标准覆盖 6/8（几何内核、防腐层）"),
            ("系统层：", "引擎 (AI skill)：两维落地 + 语义分析 + 标注"),
            ("能力层：", "新维度流程 v1 + 交叉验证扩展")]),
        2: ("H3 全维化", "2027", [
            ("规划：", "标准全集 8/8（HPC、化石代码）+ 智能体深化"),
            ("系统层：", "引擎 (AI skill)：权重归一化 + 协同 + 看板"),
            ("能力层：", "ISO 映射公开 + 流程固化")]),
        3: ("H4 生态化", "2028", [
            ("规划：", "标准发布 + 产品化 + 能力输出"),
            ("系统层：", "引擎 (AI skill)：企业级 CI 门禁 + 社区"),
            ("能力层：", "白皮书 + 开发能力对外输出")]),
    }
    for idx in (0, 2):
        phase, date, lines = cards[idx]
        cx = COL[idx]
        _add_alt_card(slide, cx, 2.25, 2.5, 1.6, phase, date, GOLD, lines)
        _add_connector(slide, cx, 3.87, 3.95)
    for idx in (1, 3):
        phase, date, lines = cards[idx]
        cx = COL[idx]
        _add_alt_card(slide, cx, 4.3, 2.5, 1.75, phase, date, GOLD, lines)
        _add_connector(slide, cx, 4.05, 4.3)
    add_textbox(slide, 1.0, 6.2, 11.3, 0.5,
                "H1–H4 四阶段规划 → 达成远景：标准体系 · AI agent 评估系统 · 开发能力",
                size=14, color=ACCENT, bold=True, align=PP_ALIGN.CENTER)
    add_footer(s, 6)

def s06_p0p1(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "03 回顾 P0–P4", "P0 奠基 + P1 多语言深化",
              "从标准 4 维引擎 (AI skill)到多语言规则逐条工程化")
    add_table(s, 0.9, 2.4, 11.5, [
        ["阶段", "时间", "关键成果"],
        ["P0 奠基", "2026-06-04",
         "v1.0 初始引擎 (AI skill)：标准架构质量 4 维（结构/设计/文档/演进）\n12 条多语言规则 + 项目级报告"],
        ["P1 多语言深化", "2026-06-05~08",
         "多语言混合架构的跨语言依赖维度 v1.1→v1.8：\n"
         "规则工程化（pybind11 / SWIG / Tcl / 回调链 / 内存检测 / 豁免注解 / --build-dir）\n"
         "5 项目回归基线 + CalculiX / Code_Aster 全规则验证"],
    ], col_widths=[2.0, 1.9, 7.6], font=12, row_h=0.5, col_h=0.42)
    add_textbox(s, 0.9, 6.4, 11.5, 0.5,
                "P1 成果 → 多语言维度全量规则可在真实大型项目上复现",
                size=14, color=ACCENT, bold=True)
    add_footer(s, 7)


def s07_p2(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "03 回顾 P0–P4", "P2 数值精度与验证体系",
              "数值算法正确性与精度保障维度 + 能力层验证体系成形")
    add_table(s, 0.9, 2.4, 11.5, [
        ["维度/能力", "内容", "验证强度"],
        ["数值算法正确性与精度保障维度",
         "6 维 + 12 条数值规则；10 个开源项目验证", "★★★"],
        ["能力层·变异测试 P1", "合成项目定向变异，检验检测灵敏度", "★★★"],
        ["能力层·人工评审框架 P2", "专家逐条评审打分", "★★☆"],
        ["能力层·k 折交叉验证 P3", "验证评分泛化能力（未见项目）", "★★★"],
        ["能力层·动态-静态交叉验证",
         "FEniCSx 最小实验 + Valgrind 端到端（静态 vs 动态比对）", "★★☆"],
    ], col_widths=[3.4, 5.4, 2.7], font=11.5, row_h=0.6, col_h=0.42)
    add_footer(s, 8)


def s08_p3(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "03 回顾 P0–P4", "P3 模板元编程与评审",
              "模板元编程与编译时依赖膨胀维度 · 三方专家评审通过")
    add_table(s, 0.9, 2.35, 11.5, [
        ["项", "结果"],
        ["维度与规则", "6 维 + 12 条规则；4.1 验证 100% 覆盖"],
        ["性能", "O(n²) → O(1)，支撑 20 万文件级项目"],
        ["三方专家评审", "综合 4.36 / 5（创新性 4.35 / 可信度 5.00）— 通过"],
        ["评审产出 4 项改进建议",
         "语义升级（实例化意图推断）· 报告自动标注 · CI 模板 · 试点推广"],
    ], col_widths=[3.2, 8.3], font=12, row_h=0.62, col_h=0.42)
    add_textbox(s, 0.9, 5.9, 11.5, 0.5,
                "评审建议 → 已纳入 H1–H4 阶段规划（语义分析、报告标注、CI、试点）",
                size=14, color=ACCENT, bold=True)
    add_footer(s, 9)


def s09_p4(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "03 回顾 P0–P4", "P4 求解器物理场与智能体",
              "求解器与物理场模块化架构模式识别维度 + AI agent 能力沉淀")
    add_table(s, 0.9, 2.35, 11.5, [
        ["项", "结果"],
        ["维度与规则", "4 维 + 12 条模块化模式规则"],
        ["工程验证", "97 测试 + 9 回归基线 + k 折交叉验证 + CI 门禁"],
        ["AI agent 验证", "agent harness（工具/输出/评分三断言器 + rules.json 单一事实源）"],
        ["能力沉淀", "skill 开发指南 + 三方一致性脚本 + MMS 验证 + 知识库/日报机制"],
    ], col_widths=[2.6, 8.9], font=12, row_h=0.62, col_h=0.42)
    add_footer(s, 10)


def s10_gaps(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(slide, "04 现状基线", "评估能力现状：4 项已落地 / 4 项待补",
              "回顾 P0-P4 之后的基线盘点，构成 H1-H4 的输入")
    # 状态条
    done = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.85, 2.3, 5.75, 1.2,
                     fill=GREEN)
    shape_text(done, "已落地 4 项（指南 + Skill + 案例库 + 回归基线）：\n"
                     "多语言混合架构的跨语言依赖 · 模板元编程与编译时依赖膨胀\n"
                     "数值算法正确性与精度保障 · 求解器与物理场模块化架构模式识别",
               size=10.5)
    pend = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 6.75, 2.3, 5.75, 1.2,
                     fill=PENDING)
    shape_text(pend, "待补 4 项：\n"
                     "几何内核与科学数据结构一致性 · 外部科学内核与几何内核的封装与防腐层\n"
                     "并行/异构计算架构（HPC/GPU） · 超长生命周期中的“化石代码”与技术债",
               size=10.5)
    add_textbox(slide, 0.85, 3.65, 11.7, 0.35, "三层缺口：", size=14,
                bold=True, color=NAVY)
    cols = [
        ("内容层 · 标准体系", NAVY, [
            "4 个维度待补（见上）",
            "标准元模型未建立（统一 维度×规则×权重×豁免 schema）",
        ]),
        ("产品层 · AI agent 评估系统", ACCENT, [
            "测试覆盖度升级（P0）未实施",
            "3 条多语言规则缺项目级回归覆盖",
            "性能优化（缓存/增量扫描）与报告矩阵待办",
        ]),
        ("能力层 · 开发能力", GREEN, [
            "动态-静态交叉验证有框架、无真实运行输出",
            "一致性检查未纳入 CI",
        ]),
    ]
    x = 0.8
    for head, color, items in cols:
        add_card(slide, x, 4.15, 3.85, 2.7, head, items, head_fill=color,
                 item_size=12)
        x += 4.05
    add_footer(s, 11)
def s11_h1(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "04 前瞻 H1–H4", "H1 可信化（2026 Q3）",
              "主目标：存量能力完整、可信、可发布")
    # 主题图形：盾形 + ✓
    shield = add_shape(slide, MSO_SHAPE.PENTAGON, 0.95, 2.6, 1.3, 1.3,
                       fill=GREEN)
    shape_text(shield, "✓", size=40, color=WHITE, bold=True)
    add_textbox(slide, 0.85, 4.0, 1.5, 0.4, "可信", size=14, bold=True,
                color=GREEN, align=PP_ALIGN.CENTER)
    add_table(s, 2.7, 2.3, 9.9, [
        ["层", "交付要点", "验收 KPI"],
        ["产品层", "测试覆盖度 5 层升级（目录/语言/文件比/绑定层）\n"
                   "规则回归补全 + 性能（缓存/增量扫描）+ 报告 MLR 矩阵\n"
                   "CI 模板 + 试点 1–2 个核心项目", "全部规则有项目级回归\nFreeCAD 全量评估 < 10 分钟"],
        ["内容层", "标准元模型 v1.0 草案（统一 维度×规则×权重×豁免 schema）", "元模型草案发布"],
        ["能力层", "一致性检查纳入 CI", "CI 自动化通过"],
    ], col_widths=[1.5, 5.4, 3.0], font=12, row_h=0.78, col_h=0.42)
    add_footer(s, 12)


def s12_h2(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "04 前瞻 H1–H4", "H2 扩展化（2026 Q4 – 2027 Q1）",
              "主目标：标准体系覆盖 6/8")
    # 主题图形：十字扩展箭头 + 2 个新块
    cx, cy = 1.5, 4.1
    for shp, dx, dy in [(MSO_SHAPE.UP_ARROW, 0, -0.85),
                        (MSO_SHAPE.DOWN_ARROW, 0, 0.85),
                        (MSO_SHAPE.LEFT_ARROW, -0.85, 0),
                        (MSO_SHAPE.RIGHT_ARROW, 0.85, 0)]:
        add_shape(slide, shp, cx - 0.25 + dx, cy - 0.25 + dy, 0.5, 0.5,
                  fill=ACCENT)
    add_shape(slide, MSO_SHAPE.OVAL, cx - 0.35, cy - 0.35, 0.7, 0.7,
              fill=NAVY)
    add_textbox(slide, 0.6, 5.4, 1.9, 0.4, "扩展维度", size=14, bold=True,
                color=ACCENT, align=PP_ALIGN.CENTER)
    add_table(s, 2.7, 2.3, 9.9, [
        ["层", "交付要点", "验收 KPI"],
        ["内容层", "新增维度① 几何内核与科学数据结构一致性\n"
                   "新增维度② 外部科学内核与几何内核的封装与防腐层\n"
                   "每维四件套：指南 + Skill + 案例库 + 设计依据",
         "6/8 维度覆盖"],
        ["产品层", "两维引擎 (AI skill)落地\n语义分析：实例化意图推断（假阳性降 50%+）\n"
                   "报告自动标注 [third-party] / [test]",
         "新维度通过 k 折与动态-静态交叉验证"],
        ["能力层", "新维度开发流程 v1（用本次两维实测有效性）", "流程文档 v1 发布"],
    ], col_widths=[1.5, 5.4, 3.0], font=12, row_h=0.78, col_h=0.42)
    add_footer(s, 13)


def s13_h3(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "04 前瞻 H1–H4", "H3 全维化（2027）",
              "主目标：标准全集 8/8 + AI agent 智能体深化")
    items = [
        ("1", "多语言混合架构的跨语言依赖", GREEN),
        ("2", "模板元编程与编译时依赖膨胀", GREEN),
        ("3", "数值算法正确性与精度保障", GREEN),
        ("4", "求解器与物理场模块化架构模式识别", GREEN),
        ("5", "几何内核与科学数据结构一致性", GREEN),
        ("6", "外部科学内核与几何内核的封装与防腐层", GREEN),
        ("7", "并行/异构计算架构（HPC/GPU）", GREEN),
        ("8", "超长生命周期中的“化石代码”与技术债", GREEN),
    ]
    draw_grid(s, items, 0.85, 2.3, 11.7, 1.9, 4, font=11.5)
    badge = add_shape(slide, MSO_SHAPE.OVAL, 11.6, 1.95, 1.1, 1.1, fill=GOLD)
    shape_text(badge, "8/8", size=18, color=WHITE, bold=True)
    add_table(s, 0.9, 4.5, 11.5, [
        ["层", "交付要点", "验收 KPI"],
        ["内容层", "新增维度③ 并行/异构计算架构（HPC/GPU）\n"
                   "新增维度④ 超长生命周期中的“化石代码”与技术债\n"
                   "ISO/IEC 25010 / CK / SQALE 映射公开",
         "8/8 全覆盖 · 每维回归基线 ≥ 5 项目"],
        ["产品层", "多增强权重归一化完善 · AI agent 多模块协同编排 · 评分趋势看板",
         "多增强组合评分稳定"],
    ], col_widths=[1.5, 6.2, 3.8], font=12, row_h=0.6, col_h=0.42)
    add_footer(s, 14)


def s14_h4(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "04 前瞻 H1–H4", "H4 生态化（2028）",
              "主目标：标准发布 + 产品化 + 能力输出")
    # 主题图形：大圆环 + 生态节点
    add_shape(slide, MSO_SHAPE.OVAL, 4.7, 2.2, 3.2, 3.2, fill=None,
              line=GREEN, line_w=3)
    add_shape(slide, MSO_SHAPE.OVAL, 5.8, 3.3, 1.0, 1.0, fill=NAVY)
    for ex, ey in [(3.9, 2.6), (6.9, 1.9), (8.9, 3.6), (3.6, 4.6), (7.6, 5.3)]:
        add_shape(slide, MSO_SHAPE.OVAL, ex, ey, 0.3, 0.3, fill=ACCENT)
    add_textbox(slide, 1.0, 6.0, 11.3, 0.5,
                "标准发布与行业推广 · 企业级 CI 门禁 · 社区共建 · 开发能力对外输出",
                size=15, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    add_table(s, 0.9, 2.2, 3.3, [
        ["交付", "KPI"],
        ["团体标准/事实标准 + 测量规程白皮书", "外部采用项目数"],
        ["企业级 CI 门禁产品化", "集成企业数"],
        ["社区共建", "社区贡献者数"],
    ], col_widths=[2.0, 1.3], font=11, row_h=0.6, col_h=0.42)
    add_textbox(s, 4.7, 6.6, 8.0, 0.4,
                "愿景达成：标准体系立得住、系统用得起、能力传得出去",
                size=14, color=ACCENT, bold=True)
    add_footer(s, 15)


def s15_matrix(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "04 前瞻 H1–H4", "三支柱 × 阶段全景矩阵",
              "● 主攻 / ◐ 配套 / ○ 未涉及")
    phases = ["P0", "P1", "P2", "P3", "P4", "H1", "H2", "H3", "H4"]
    rows = {
        "内容层 · 标准体系": ["○", "○", "●", "●", "●", "◐", "●", "●", "●"],
        "产品层 · AI agent 评估系统": ["●", "●", "●", "●", "●", "●", "●", "●", "●"],
        "能力层 · 开发能力": ["○", "◐", "●", "◐", "●", "●", "◐", "◐", "●"],
    }
    data = [[""] + phases]
    for row, marks in rows.items():
        data.append([row] + marks)
    tbl = add_table(s, 0.7, 2.4, 11.9, data, col_widths=[3.3] + [0.95] * 9,
                    font=11.5, row_h=0.55, col_h=0.45)
    for ri in range(1, 4):
        for ci in range(1, 10):
            mark = data[ri][ci]
            cell = tbl.cell(ri, ci)
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    run.font.bold = mark != "○"
                    if mark == "●":
                        run.font.color.rgb = GREEN
                    elif mark == "◐":
                        run.font.color.rgb = GOLD
                    else:
                        run.font.color.rgb = PENDING
                p.alignment = PP_ALIGN.CENTER
    add_textbox(s, 0.7, 6.3, 11.9, 0.5,
                "每个阶段只有一个主攻方向，其余两层做配套交付，避免齐头并进",
                size=14, color=GRAY)
    add_footer(s, 16)


def s16_verification(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "05 验证与能力", "开发能力：两条交叉验证，各司其职",
              "一个验证“稳不稳”（泛化），一个验证“对不对”（正确性）")
    panels = [
        ("k 折交叉验证", GREEN, [
            "方法：验证案例集切 K 折，重复评测评分",
            "回答：评分泛化能力（“稳不稳”）",
            "状态：数值精度、求解器物理场维度已实施",
        ]),
        ("动态-静态交叉验证", ACCENT, [
            "方法：Valgrind/Verrou/CADNA 实际运行输出\n与静态工具结果比对（一致/误报/漏报）",
            "回答：判定正确性（“对不对”）",
            "状态：框架就绪，待真实可运行项目输出",
        ]),
    ]
    x = 0.9
    for head, color, items in panels:
        add_card(s, x, 2.35, 5.6, 3.6, head, items, head_fill=color,
                 item_size=13)
        x += 5.95
    add_textbox(s, 0.9, 6.3, 11.5, 0.6,
                "能力层 = 验证体系（回归快照 / 变异测试 / 双交叉验证 / 三方一致性）+ 治理机制（季度评审 / 版本化 / 知识库）",
                size=14, color=DARK, bold=True)
    add_footer(s, 17)


def s17_kpi(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "06 指标与治理", "KPI：三层各一条主线",
              "每阶段验收均有量化口径，指标随阶段演进")
    add_table(s, 0.9, 2.4, 11.5, [
        ["层", "主线指标", "演进方向", "目标"],
        ["内容层", "工业维度覆盖数", "4 → 6 → 8 → 标准发布", "8/8 + ISO 映射公开"],
        ["产品层", "规则回归 / 验证通过率", "补全 → 全通过 → 外部采用", "全规则回归 + 外部采用"],
        ["能力层", "新维度交付周期", "P2–P4 → H1 → H2–H3", "每阶段递减（能力成长）"],
    ], col_widths=[1.6, 3.2, 3.8, 2.9], font=12, row_h=0.6, col_h=0.42)
    # 上升折线小图
    pts = [(2.4, 5.1), (4.6, 4.6), (6.8, 3.9), (9.0, 3.0)]
    for i in range(1, len(pts)):
        x1, y1 = pts[i - 1]
        x2, y2 = pts[i]
        add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE,
                  min(x1, x2) + 0.02, min(y1, y2), abs(x2 - x1) - 0.04, 0.05,
                  fill=GREEN)
    for i, (x, y) in enumerate(pts):
        add_shape(slide, MSO_SHAPE.OVAL, x - 0.12, y - 0.12, 0.24, 0.24,
                  fill=NAVY if i < len(pts) - 1 else ACCENT)
        add_textbox(slide, x - 0.7, y - 0.55, 1.4, 0.35,
                    ["P4", "H1", "H2", "H3–H4"][i], size=11, bold=True,
                    color=GRAY, align=PP_ALIGN.CENTER)
    add_textbox(slide, 9.6, 4.7, 2.6, 0.9, "持续上升：\n可信度与覆盖度双增长",
                size=13, color=ACCENT, bold=True)
    add_footer(s, 18)


def s18_risks(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "06 指标与治理", "风险与缓解",
              "识别先行，缓解措施随阶段落地")
    risks = [
        ("动态交叉验证依赖真实运行项目", [
            "现状：框架就绪、无实际运行输出",
            "缓解：选取可编译项目做端到端实验\n（H1 试点项目内完成）",
        ]),
        ("语义分析投入大、收益需验证", [
            "现状：假阳性是主要用户负担",
            "缓解：优先高收益规则（实例化意图推断）\n量化前后假阳性对比（H2）",
        ]),
        ("标准推广需外部资源", [
            "现状：仅内部验证",
            "缓解：先内部 1–2 项目试点，产出数据\n再推广（H1 试点 → H4 生态）",
        ]),
    ]
    x = 0.9
    for title, items in risks:
        add_card(s, x, 2.4, 3.7, 3.6, title, items, head_fill=ACCENT,
                 item_size=12.5)
        x += 3.95
    add_footer(s, 19)


def s19_governance(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title(s, "06 指标与治理", "治理与里程碑",
              "季度评审循环 + 版本化发布 + 知识沉淀")
    # 循环图形
    add_shape(slide, MSO_SHAPE.OVAL, 1.6, 2.7, 3.0, 3.0, fill=None,
              line=NAVY, line_w=2.5)
    qpts = [(1.75, 2.55), (4.45, 2.55), (4.45, 4.95), (1.75, 4.95)]
    for qx, qy in qpts:
        add_shape(slide, MSO_SHAPE.OVAL, qx, qy, 0.3, 0.3, fill=ACCENT)
    add_textbox(slide, 2.45, 3.95, 1.5, 0.5, "Q1→Q4", size=16, bold=True,
                color=NAVY, align=PP_ALIGN.CENTER)
    add_textbox(slide, 0.6, 6.1, 4.2, 0.4, "季度评审（业务/技术/过程三方专家）",
                size=12, color=GRAY, align=PP_ALIGN.CENTER)
    add_table(s, 5.3, 2.5, 7.2, [
        ["机制", "说明"],
        ["季度评审", "沿用既有评审机制，每季度验收阶段交付"],
        ["版本化发布", "指南 / Skill / 工具三件套同步，三方一致性检查"],
        ["知识沉淀", "知识库 + 每日报告（CST）持续积累，支撑能力沉淀"],
    ], col_widths=[2.0, 5.2], font=12, row_h=0.62, col_h=0.42)
    add_footer(s, 20)


def s20_end(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    add_shape(slide, MSO_SHAPE.OVAL, 5.9, 1.4, 1.5, 1.5, fill=NAVY)
    star = add_textbox(s, 5.9, 1.4, 1.5, 1.5, "★", size=40, bold=True,
                       color=WHITE, align=PP_ALIGN.CENTER)
    star.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    add_textbox(s, 1.0, 3.4, 11.3, 0.9,
                "让 AI agent 评估系统成为工业软件架构质量的“标准尺”",
                size=28, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    add_textbox(s, 1.0, 4.6, 11.3, 0.5,
                "一份标准 · 一套系统 · 一种能力", size=18, color=GRAY,
                align=PP_ALIGN.CENTER)
    add_textbox(s, 1.0, 6.3, 11.3, 0.4,
                "感谢聊听 · Q & A", size=14, color=GRAY,
                align=PP_ALIGN.CENTER)
    add_footer(s, 21)


def _appendix_layout(slide, chapter, title, subtitle, left_head, left_items,
                    right_head, right_items, bottom, page_no,
                    left_fill=ACCENT, right_fill=GREEN):
    add_title(slide, chapter, title, subtitle)
    add_card(slide, 0.85, 2.35, 5.75, 3.05, left_head, left_items,
             head_fill=left_fill, item_size=12)
    add_card(slide, 6.75, 2.35, 5.75, 3.05, right_head, right_items,
             head_fill=right_fill, item_size=12)
    bar = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 0.85, 5.65, 11.65,
                    1.0, fill=LIGHT)
    add_textbox(slide, 1.05, 5.78, 11.3, 0.75, bottom, size=13, color=DARK,
                line_spacing=1.3)
    add_footer(slide, page_no, "arch-quality Roadmap · 附录")


def s21_appendix_meta(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    _appendix_layout(
        slide, "附录 A · 术语说明",
        "标准元模型 v1.0 草案：标准的“标准”",
        "统一 维度/规则/权重/豁免/验证资产 的 schema，新维度按模板填空",
        "现状 v1.x（各自为政）", [
            "规则编码不一：多语言 MLR / 数值 NVR / 物理场 MPR",
            "权重格式各异：各维度各自声明、各自解析",
            "豁免语法不同：注解与必填字段不统一",
            "验证资产不齐：指南/技能/案例库/回归基线多寡不一",
        ],
        "v2.0 元模型统一内容", [
            "维度：标识 / 全称 / 权重 / 评分算法引用",
            "规则：统一编码、触发条件、严重度、证据来源",
            "权重：统一声明格式，强制“和为 100%”校验",
            "豁免：统一注解语法 + 必填字段 + 跨规则协调",
            "验证资产：四件套标准模板（指南/技能/案例库/回归基线）",
        ],
        "价值：新增维度按模板填空 · 引擎/报告/一致性检查只认一套 schema · 可机器校验、可对外发布\n落地：H1 草案 → H2/H3 新维度套用 → H4 团体标准/事实标准",
        22)


def s22_appendix_weights(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    _appendix_layout(
        slide, "附录 B · 术语说明",
        "多增强权重归一化完善：让总分可比",
        "任意增强组合下，基础结构质量 + 各增强权重和恒等于 100%",
        "现状（arch_report.py 实现）", [
            "按激活数量分档基础权重：1 增强→85% / 2→70% / 3→60% / 4→55%",
            "增强自带权重：多语言/模板/物理场 15%、数值 10%",
            "归一化：仅当总和 >100% 时等比缩放",
        ],
        "缺陷 → 完善目标", [
            "只缩不放：单数值增强 95%，总分被系统性低估",
            "数量分档与类型定权口径不统一，组合间不可比",
            "4 增强=16 组合靠手写 if/else；扩到 8 增强=256 组合不可维护",
            "升级：统一权重模型 + 双向归一化（缩放+补足）+ 新维度自动纳入",
            "经 k 折 / 案例库验证跨项目分数可比性",
        ],
        "目标：任意增强组合下 基础+增强权重和 恒等于 100%，总分可比\n落地：H3",
        23)


def s23_appendix_orchestration(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    _appendix_layout(
        slide, "附录 C · 术语说明",
        "AI agent 多模块协同编排：从“写死合并”到“动态指挥”",
        "智能体按项目特征动态编排多引擎模块",
        "现状（确定性管线）", [
            "ComprehensiveReport 固定顺序调用 5 引擎：标准 / 多语言 / 模板 / 数值 / 物理场",
            "模块启停、评估顺序、权重分配全部写死",
        ],
        "编排三步（H3 目标）", [
            "① 先识别：项目类型 → 决定启用哪些模块",
            "② 再排程：评估顺序、模块间数据传递、跨模块权重归一化",
            "③ 后解释：跨模块冲突处理、综合评估结论",
        ],
        "引擎负责“算得对”，编排负责“流程跑得顺、工具选得对”\n落地：H3（智能体深化）",
        24)



def s24_appendix_completeness(prs):
    slide = s = prs.slides.add_slide(prs.slide_layouts[6])
    _appendix_layout(
        slide, "附录 D · 术语说明",
        "维度完备性证明与边界裁决",
        "自上而下校验 8 维，补齐数据交换/互操作，消除双重计分",
        "自上而下校验（ISO/IEC 25010）", [
            "8 维为 P0-P4 自下而上归纳，需对照 ISO 25010 校验",
            "漏维补齐：数据交换/互操作（STEP/IGES/IFC/单位制/公差）并入⑧防腐层规则族",
            "⑥ 更名“并行/异构计算架构（HPC/GPU）”：接口一致性降为规则族（MPI 域分解/halo/负载均衡/GPU 路径发散）",
            "④ 保留单维分族：几何内核族 / 科学数据结构族",
        ],
        "边界裁决矩阵（防双重计分）", [
            "NVR×MPR：共享 fvSchemes/fvSolution 文件，先 NVR 后 MPR，MPR 豁免重复计分",
            "①多语言×⑧防腐层：wrapper 源按主关切归属，先 ① 后 ⑧",
            "④×⑧：B-Rep 操作点先 ④ 后 ⑧",
            "⑦×演进质量：⑦ 管形态检测，演进质量仅管趋势",
            "生成文件/构建产物/third_party：统一过滤不计分",
        ],
        "落地：H1 WP-2 固化为正式四栏表 · WP-7 固化进元模型与注册表（含数据交换族占位）",
        25)

def build():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    for fn in (s01_cover, s02_toc, s03_background, s04_vision, s05_p_cards, s06_h_cards,
               s06_p0p1, s07_p2, s08_p3, s09_p4, s10_gaps,
               s11_h1, s12_h2, s13_h3, s14_h4, s15_matrix,
               s16_verification, s17_kpi, s18_risks, s19_governance, s20_end,
               s21_appendix_meta, s22_appendix_weights,
               s23_appendix_orchestration,
               s24_appendix_completeness):
        fn(prs)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    prs.save(OUT_PATH)
    print(f"已生成: {OUT_PATH} ({len(prs.slides._sldIdLst)} 页)")


if __name__ == "__main__":
    build()