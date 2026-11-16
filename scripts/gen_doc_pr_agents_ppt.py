#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成《Proposer & Reviewer Agent》介绍 PPT（浅色 16:9，14 页，含演讲备注）。

用法：python scripts/gen_doc_pr_agents_ppt.py
输出：docs/ppt/Proposer-Reviewer-Agents.pptx（该目录 *.pptx 被 gitignore）
"""

import os

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# ---- 浅色主题（沿用 gen_harness_ppt.py）----
NAVY = RGBColor(0x1F, 0x3A, 0x5F)
DARK = RGBColor(0x33, 0x33, 0x33)
GRAY = RGBColor(0x66, 0x66, 0x66)
ACCENT = RGBColor(0xC0, 0x50, 0x4D)
LIGHT = RGBColor(0xF2, 0xF2, 0xF2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
AMBER = RGBColor(0xB2, 0x6A, 0x00)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
FONT_CN = "Microsoft YaHei"
FONT_MONO = "Consolas"

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "ppt",
                        "Proposer-Reviewer-Agents.pptx")
TOTAL = 14


def _font(run, size, bold=False, color=DARK, mono=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    name = FONT_MONO if mono else FONT_CN
    run.font.name = name
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", name)


def add_text(slide, x, y, w, h, text, size=16, bold=False, color=DARK,
             align=PP_ALIGN.LEFT, mono=False, spacing=1.0, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, line in enumerate(str(text).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        run = p.add_run()
        run.text = line
        _font(run, size, bold, color, mono)
    return tb


def add_title(slide, chapter, title_cn, title_en):
    # 顶部强调条
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT; bar.line.fill.background()
    add_text(slide, 0.6, 0.35, 12, 0.3, chapter, size=12, bold=True, color=ACCENT)
    add_text(slide, 0.6, 0.68, 12.1, 0.7, title_cn, size=28, bold=True, color=NAVY)
    add_text(slide, 0.6, 1.38, 12.1, 0.4, title_en, size=13, color=GRAY)


def add_footer(slide, page_no):
    add_text(slide, 0.6, 7.12, 9, 0.25, "Proposer & Reviewer Agent · arch-quality · 2026-11-16",
             size=9, color=GRAY)
    add_text(slide, 11.9, 7.12, 0.8, 0.25, f"{page_no} / {TOTAL}", size=9,
             color=GRAY, align=PP_ALIGN.RIGHT)


def add_card(slide, x, y, w, h, fill=LIGHT, line=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                                 Inches(w), Inches(h))
    shp.adjustments[0] = 0.06
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = Pt(1)
    shp.text_frame.text = ""
    return shp


def add_bullets(slide, x, y, w, h, items, size=14, color=DARK, spacing=1.25):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = spacing
        run = p.add_run(); run.text = "• " + item
        _font(run, size, False, color)
    return tb


def add_table(slide, x, y, w, h, data, col_widths=None, size=11, header_fill=NAVY):
    rows, cols = len(data), len(data[0])
    shape = slide.shapes.add_table(rows, cols, Inches(x), Inches(y), Inches(w), Inches(h)).table
    if col_widths:
        for i, cw in enumerate(col_widths):
            shape.columns[i].width = Inches(cw)
    for ri in range(rows):
        for ci in range(cols):
            cell = shape.cell(ri, ci)
            cell.text = str(data[ri][ci])
            cell.margin_left = Inches(0.06); cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.03); cell.margin_bottom = Inches(0.03)
            for p in cell.text_frame.paragraphs:
                p.alignment = PP_ALIGN.LEFT
                for run in p.runs:
                    _font(run, size, bold=(ri == 0),
                          color=WHITE if ri == 0 else DARK)
            if ri == 0:
                cell.fill.solid(); cell.fill.fore_color.rgb = header_fill
            elif ri % 2 == 0:
                cell.fill.solid(); cell.fill.fore_color.rgb = LIGHT
    return shape


def add_chevrons(slide, y, labels, x0=0.65, width=1.72, height=0.85, size=11):
    for i, label in enumerate(labels):
        shp = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(x0 + i * width), Inches(y),
                                     Inches(width - 0.02), Inches(height))
        shp.fill.solid()
        shp.fill.fore_color.rgb = NAVY if i < len(labels) - 1 else GREEN
        shp.line.fill.background()
        tf = shp.text_frame; tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        run = p.add_run(); run.text = label
        _font(run, size, True, WHITE)


def add_code(slide, x, y, w, h, text, size=10):
    box = add_card(slide, x, y, w, h, fill=RGBColor(0x1E, 0x1E, 0x1E))
    tb = slide.shapes.add_textbox(Inches(x + 0.12), Inches(y + 0.08),
                                  Inches(w - 0.24), Inches(h - 0.16))
    tf = tb.text_frame; tf.word_wrap = True
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        run = p.add_run(); run.text = line
        _font(run, size, False, RGBColor(0xE8, 0xE8, 0xE8), mono=True)
    return box


def add_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def build():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    # ---------------- 1 封面 ----------------
    s = prs.slides.add_slide(blank)
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.05), SLIDE_W, Inches(1.55))
    band.fill.solid(); band.fill.fore_color.rgb = NAVY; band.line.fill.background()
    add_text(s, 0.9, 2.2, 11.5, 0.7, "Proposer & Reviewer", size=44, bold=True, color=WHITE)
    add_text(s, 0.9, 2.95, 11.5, 0.5, "评估文档的 PR 化闭环：把知识库当代码库",
             size=20, color=WHITE)
    add_text(s, 0.9, 3.85, 11.5, 0.4, "A Proposer–Reviewer Agent Loop for Architecture Assessment Docs",
             size=14, color=GRAY)
    add_text(s, 0.9, 6.2, 11.5, 0.35, "arch-quality · 2026-11-16 · v1.0 · 15 min",
             size=11, color=GRAY)
    add_notes(s, "开场：这不是“让模型写文档”，而是“让模型走 PR”。"
                 "今天讲四件事：为什么、谁来做、怎么闭环、怎么证明有效。")

    # ---------------- 2 为什么 ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "01 · 问题", "为什么要把知识库当代码库", "Why Treat the Knowledge Base as Code")
    layers = [("证据层", "只增不改", "validation/、快照、专家记录"),
              ("知识层", "可修订", "指南 / 设计依据 / 案例集 / Skill"),
              ("服务层", "可重建", "索引、Skill bundle、报告产物")]
    for i, (name, tag, desc) in enumerate(layers):
        y = 2.0 + i * 1.45
        add_card(s, 0.7, y, 5.6, 1.2)
        add_text(s, 0.95, y + 0.12, 1.6, 0.4, name, size=17, bold=True, color=NAVY)
        add_text(s, 2.5, y + 0.12, 1.2, 0.35, tag, size=11, bold=True,
                 color=ACCENT if tag != "可重建" else GREEN)
        add_text(s, 0.95, y + 0.62, 5.0, 0.45, desc, size=11, color=GRAY)
    add_bullets(s, 6.9, 2.0, 5.8, 4.2, [
        "模型直接改主分支：没有差异审查、没有版本历史、无法一键回滚",
        "把每次知识变更做成 PR：diff、责任、批准记录、可回滚",
        "索引永远是“某个已合入 commit 的派生物”，不是真源",
        "生产环境不允许任何模型绕过审核写主分支或线上向量库",
    ], size=14)
    add_notes(s, "三层：证据层只增不改，知识层可修订，服务层可重建。"
                 "核心原则：Git 里已审核的知识才是真源，索引只是派生物。")

    # ---------------- 3 四个角色 ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "02 · 角色", "四个角色，权限分离", "Four Roles, Separated Permissions")
    data = [
        ["角色", "能做什么", "明确禁止"],
        ["Proposer", "写工作分支、开 PR、按意见修订", "合并、push main、改索引、定权重/阈值/severity"],
        ["Reviewer", "只读证据与 diff、提交结构化 review", "修改任何文件、批准自己参与的 PR"],
        ["Merger（CI bot）", "gates 全绿后机械合并、重建索引", "理解或修改内容"],
        ["Human Approver", "权重/阈值/severity 决策、最终 sign-off", "—"],
    ]
    add_table(s, 0.7, 2.05, 11.9, 3.4, data, col_widths=[2.2, 4.6, 5.1], size=12)
    add_text(s, 0.7, 5.8, 11.9, 0.5,
             "同一模型不得兼任两角色；Reviewer 上下文只给 base、diff、证据、gates 报告。",
             size=12, color=GRAY)
    add_notes(s, "权限不是口头约定，是 agent 配置：Reviewer 的 edit/write 为 deny。"
                 "合并只能由 Merger 在 signed_off 状态执行。")

    # ---------------- 4 状态机 ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "03 · 机制", "闭环状态机", "The Closed-Loop State Machine")
    add_chevrons(s, 2.2, ["draft", "selfcheck", "review", "approve",
                          "signoff", "merged", "closed"], size=10)
    add_bullets(s, 0.8, 3.5, 5.9, 3.0, [
        "selfcheck 失败 → selfcheck_failed（修好重跑）",
        "review 要求修改 → changes_requested → revise → draft",
        "第 3 轮仍未收敛 → needs_human（冻结，禁止自动放行）",
    ], size=12)
    add_bullets(s, 6.9, 3.5, 5.8, 3.0, [
        "approved 必须 P0=0；signed_off 必须有人类 HD 记录",
        "merge 前复核门禁；失败 → blocked",
        "合并后 reeval（修订后回评）→ closed 或勘误 PR",
    ], size=12)
    add_notes(s, "状态机是硬约束：每个动作都有前置状态，跳步会被拒绝。"
                 "迭代上限 3 轮，超限转人工，这是“不默认放行”的实现。")

    # ---------------- 5 门禁 ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "03 · 机制", "门禁：机器能判的交给机器", "Gates: Machines Decide What Machines Can")
    data = [
        ["门禁", "检查内容", "判定者"],
        ["G0", "结构、链接、版本绑定与版本历史一致性", "脚本"],
        ["G1", "权重和=100%，指南/Skill 逐项一致", "脚本"],
        ["G3", "置信度-严重级别、规则口径一致", "脚本"],
        ["R", "review 契约：计数、file:line、证据", "脚本"],
        ["PR", "关键决策必须有人类 HD 批准", "脚本"],
        ["语义", "证据是否支持、是否丢限定条件、是否过度改写", "LLM"],
    ]
    add_table(s, 0.7, 2.0, 11.9, 3.6, data, col_widths=[1.4, 8.3, 2.2], size=12)
    add_text(s, 0.7, 5.9, 11.9, 0.5,
             "机器能判的不要交给 LLM；LLM 只负责语义判断。",
             size=13, bold=True, color=ACCENT)
    add_notes(s, "G0/G1/G3 都是可脚本化的；Reviewer 只做语义判断。"
                 "这样既省成本，也避免“模型自己说没问题”。")

    # ---------------- 6 Proposer ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "04 · Proposer", "Proposer：从证据到最小 diff",
              "Proposer: From Evidence to a Minimal Diff")
    steps = ["检索已有知识", "提出最小 diff", "每条断言带证据", "自检 doc_lint", "写 PR 文件"]
    for i, step in enumerate(steps):
        y = 2.0 + i * 0.78
        add_card(s, 0.7, y, 5.6, 0.62, fill=WHITE if i % 2 else LIGHT)
        add_text(s, 0.95, y + 0.12, 5.1, 0.4, f"{i + 1}. {step}", size=13, color=DARK)
    add_code(s, 6.7, 2.0, 5.9, 3.6,
             "pr_type: errata\nevidence: [EV-REPO-..., EV-TEST-...]\nchanges:\n"
             "  files: [...]\n  weights_changed: []\n  severity_changed: []\n"
             "human_decisions: []\nreview: { verdict: changes_requested }")
    add_text(s, 6.7, 5.8, 5.9, 0.8,
             "不是把对话追加到文件末尾，而是增、删、改对应条目。",
             size=12, color=GRAY)
    add_notes(s, "Proposer 的关键不是“写得多”，而是“改得准”。"
                 "权重/阈值/severity 必须引用人类 HD 编号，否则门禁失败。")

    # ---------------- 7 Reviewer ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "05 · Reviewer", "Reviewer：独立审核，不跟着 Proposer 走",
              "Reviewer: Independent, Evidence-First")
    add_bullets(s, 0.7, 2.0, 5.8, 4.2, [
        "证据支持：每条新断言逐条回查",
        "限定条件：是否丢掉“仅当…/待定/KNOWN_HOLES”",
        "跨文档口径：ID、severity、置信度、版本",
        "覆盖矩阵：✅ 能否在正文定位",
        "过度修改：是否夹带无关重排",
        "关键决策：权重/阈值/severity 是否有人类批准",
    ], size=13)
    add_code(s, 6.7, 2.0, 5.9, 3.3,
             '{"pr_id":"PR-X",\n "verdict":"changes_requested",\n "p0":0,"p1":1,"p2":0,\n'
             ' "comments":[{"file":".../指南.md",\n  "line":281,"severity":"P1",\n'
             '  "evidence":"EV-REPO-...",\n  "message":"...","suggestion":"..."}]}')
    add_text(s, 6.7, 5.5, 5.9, 0.8,
             "approved 必须 P0=0；changes_requested 至少 1 条意见。",
             size=12, color=ACCENT)
    add_notes(s, "Reviewer 不看 Proposer 的论证长文，只看 base、diff、证据。"
                 "每条意见必须带 file:line 和 evidence，否则视为无效。")

    # ---------------- 8 真实运行 #1 ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "06 · 实证", "真实运行：一次 errata PR", "Real Run: An Errata PR")
    add_chevrons(s, 2.0, ["start", "selfcheck", "review#1", "signoff", "merge", "closed"],
                 width=1.95, height=0.8, size=10)
    add_table(s, 0.7, 3.3, 11.9, 2.0, [
        ["指标", "结果"],
        ["门禁", "3 warning → 0 error / 0 warning"],
        ["Reviewer", "approved，P0=0 / P1=0 / P2=4"],
        ["人工批准", "HD-2026-11-13-01（Guo）"],
        ["合并", "5 文件，+105/−11；索引从合并版本重建"],
    ], col_widths=[2.2, 9.7], size=12)
    add_text(s, 0.7, 5.7, 11.9, 0.5,
             "Reviewer 的 4 条 P2 成为下一轮输入——闭环不是一次通过，而是持续收敛。",
             size=12, color=GRAY)
    add_notes(s, "第一次真实合并：Reviewer 没有直接放行，留了 4 条 P2。"
                 "这正是闭环的价值：批准不等于没有改进空间。")

    # ---------------- 9 真实运行 #2 ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "06 · 实证", "迭代上限与转人工", "Iteration Cap and Human Escalation")
    add_chevrons(s, 2.0, ["review#1\nP1 GUIDE_VERSION", "review#2\nP1 consistency_check",
                          "review#3\nP1 证据自证", "needs_human\n第 3 轮冻结"],
                 width=2.9, height=0.95, size=10)
    box = add_card(s, 0.7, 3.4, 5.6, 1.4, fill=WHITE, line=ACCENT)
    add_text(s, 0.95, 3.55, 5.1, 0.4, "PR-P2-FOLLOWUP-01", size=15, bold=True, color=ACCENT)
    add_text(s, 0.95, 3.95, 5.1, 0.7, "3 轮 changes_requested → 冻结，不自动放行",
             size=11, color=DARK)
    box2 = add_card(s, 6.7, 3.4, 5.9, 1.4, fill=WHITE, line=GREEN)
    add_text(s, 6.95, 3.55, 5.4, 0.4, "PR-P2-FOLLOWUP-02", size=15, bold=True, color=GREEN)
    add_text(s, 6.95, 3.95, 5.4, 0.7, "人工决定开新 PR → approved 0/0/0（HD-2026-11-16-01）",
             size=11, color=DARK)
    add_text(s, 0.7, 5.4, 11.9, 1.0,
             "两轮之间，Reviewer 发现了 GUIDE_VERSION 过期、consistency_check 版本对过期、"
             "证据自证等真实问题——这些都不是脚本能发现的。",
             size=12, color=GRAY)
    add_notes(s, "这是“迭代上限 + 转人工”的真实案例：第 3 轮触发 needs_human，"
                 "人工决定开新 PR，第二次一轮通过。")

    # ---------------- 10 植入缺陷集 ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "07 · 验证", "植入缺陷集：证明门禁真的能抓",
              "Seeded Defects: Proving the Gates Work")
    add_table(s, 0.7, 2.0, 7.4, 2.8, [
        ["类别", "数量", "结果"],
        ["机器缺陷（G0/G1/G3）", "7", "7/7 抓到"],
        ["语义缺陷（需 LLM）", "4", "机器 0/4（设计如此）"],
        ["干净对照", "2", "0 误报"],
    ], col_widths=[3.4, 1.2, 2.8], size=12)
    add_card(s, 8.5, 2.0, 4.1, 2.8)
    add_text(s, 8.75, 2.15, 3.6, 0.4, "基线冻结", size=14, bold=True, color=NAVY)
    add_text(s, 8.75, 2.6, 3.6, 1.9,
             "opencode-harness/seeded/baseline/\n（a3168bb）\n\n文档后续修订不会让变异失效。",
             size=11, color=GRAY)
    add_text(s, 0.7, 5.3, 11.9, 0.9,
             "机器召回 100%，语义缺陷全部留给 Reviewer——分工清晰，才能量出“模型到底抓到了什么”。",
             size=12, color=GRAY)
    add_notes(s, "植入缺陷集是回归测试：把已知坏改动放进干净基线，看门禁/Reviewer 能不能抓到。"
                 "基线冻结，避免文档改动导致变异失效。")

    # ---------------- 11 模型选择 ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "07 · 验证", "Reviewer 用哪个模型", "Which Model for the Reviewer")
    add_table(s, 0.7, 2.0, 11.9, 1.8, [
        ["模型", "召回 S1–S4", "干净对照", "平均延迟", "额度成本 / 次"],
        ["kimi-k3", "4/4", "通过", "34s", "~$0.53"],
        ["deepseek-v4.1-flash", "4/4", "通过（偶发 token 耗尽需重试）", "41s", "~$0.004"],
    ], col_widths=[3.2, 2.0, 4.2, 1.2, 1.3], size=12)
    add_card(s, 0.7, 4.2, 11.9, 1.2, fill=WHITE, line=GREEN)
    add_text(s, 0.95, 4.35, 11.4, 0.4, "结论", size=14, bold=True, color=GREEN)
    add_text(s, 0.95, 4.75, 11.4, 0.5,
             "默认 deepseek-v4.1-flash（同召回、成本约 1/130）；kimi-k3 保留为争议条目的第二意见。",
             size=12, color=DARK)
    add_text(s, 0.7, 5.7, 11.9, 0.4,
             "评估方法：4 个语义缺陷 + 2 个干净对照，逐案评分（检测 / 定位 / verdict）。",
             size=10, color=GRAY)
    add_notes(s, "两个模型召回相同，但成本差两个数量级。"
                 "选型不是看“谁更强”，而是看“同等召回下谁更可持续”。")

    # ---------------- 12 安全与治理 ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "08 · 治理", "安全与治理", "Safety and Governance")
    cards = [
        ("权限隔离", "Proposer 只写分支；Reviewer 只读；Merger 只合并"),
        ("证据可追溯", "每条知识 = (kb_commit, evidence_ids, pr_id, approvals)"),
        ("人工硬门禁", "权重/阈值/severity 无 HD 记录 → CI 直接失败"),
        ("反橡皮图章", "file:line+证据、复述检测、植入缺陷召回、人工抽检"),
    ]
    for i, (title, desc) in enumerate(cards):
        x = 0.7 + (i % 2) * 6.1
        y = 2.0 + (i // 2) * 2.1
        add_card(s, x, y, 5.7, 1.75)
        add_text(s, x + 0.25, y + 0.15, 5.2, 0.4, title, size=16, bold=True, color=NAVY)
        add_text(s, x + 0.25, y + 0.7, 5.2, 0.85, desc, size=11, color=DARK)
    add_text(s, 0.7, 6.4, 11.9, 0.4,
             "异源互审：Proposer 与 Reviewer 用不同家族模型；Reviewer 主要核对证据，而不是复述结论。",
             size=11, color=GRAY)
    add_notes(s, "治理的核心不是“信任模型”，而是“让模型无法绕过”。"
                 "权限、证据、人工批准、反橡皮图章，四层叠加。")

    # ---------------- 13 怎么用 ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "09 · 使用", "怎么用：三条命令", "How to Use: Three Commands")
    add_code(s, 0.7, 2.0, 7.6, 3.2,
             "# 1) 交互\nopencode --agent assessment-reviewer\n\n"
             "# 2) 无头\nopencode run --agent assessment-reviewer \\\n"
             "  -m opencode-go/deepseek-v4.1-flash \"审核 <pr.md>\"\n\n"
             "# 3) 编排（推荐）\npython scripts\\run_doc_pr.py --pr-id PR-X \\\n"
             "  --pr-file <pr.md> --skip-proposer")
    add_card(s, 8.7, 2.0, 3.9, 3.2)
    add_text(s, 8.95, 2.15, 3.4, 0.4, "状态目录", size=14, bold=True, color=NAVY)
    add_text(s, 8.95, 2.6, 3.4, 3.0,
             ".doc-pr/<pr_id>/\n  state.json\n  review_1.json\n  run.log\n  index_rebuild.json\n\n"
             "（gitignored）",
             size=11, color=GRAY, mono=True)
    add_text(s, 0.7, 5.55, 11.9, 0.5,
             "人工批准：--human-decision HD-... --by <姓名>；否则停在 review_approved。",
             size=11, color=GRAY)
    add_notes(s, "三种用法：交互探索、无头单次、编排器。"
                 "编排器不会替你批准，没有 HD 就停在 review_approved。")

    # ---------------- 14 下一步 ----------------
    s = prs.slides.add_slide(blank)
    add_title(s, "10 · 展望", "下一步", "Next Steps")
    add_bullets(s, 0.7, 2.0, 11.9, 3.2, [
        "补齐 G2/G4/G5/G6 门禁：规则覆盖、覆盖矩阵、案例版本绑定、跨文档口径",
        "把更多评估维度注册进 doc_lint（ACL / HPC / MPR / NVR）",
        "接入 CI：ci_gate_docs.bat + pr_state 状态检查",
        "把 Reviewer 默认模型切到 deepseek-v4.1-flash，并加空响应重试",
    ], size=14)
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(5.6), SLIDE_W, Inches(1.1))
    band.fill.solid(); band.fill.fore_color.rgb = NAVY; band.line.fill.background()
    add_text(s, 0.9, 5.78, 11.5, 0.5, "谢谢 | Thank You", size=26, bold=True, color=WHITE)
    add_text(s, 0.9, 6.28, 11.5, 0.35, "问题与讨论 · arch-quality", size=12, color=WHITE)
    add_notes(s, "收尾：下一步是把门禁补齐、把更多维度接进来、把闭环接进 CI。"
                 "欢迎提问。")

    # 页脚
    for i, slide in enumerate(prs.slides, 1):
        if i > 1:
            add_footer(slide, i)

    prs.save(OUT_PATH)
    print("saved:", os.path.abspath(OUT_PATH), "slides:", len(prs.slides))


def check():
    from pptx import Presentation as P
    prs = P(OUT_PATH)
    sw, sh = prs.slide_width, prs.slide_height
    problems = []
    for i, slide in enumerate(prs.slides, 1):
        for shp in slide.shapes:
            if shp.left is None or shp.top is None or shp.width is None or shp.height is None:
                continue
            if shp.left < 0 or shp.top < 0 or shp.left + shp.width > sw + 1000 or shp.top + shp.height > sh + 1000:
                problems.append(f"slide {i}: out of bounds {shp.shape_type} "
                                f"({shp.left},{shp.top},{shp.width},{shp.height})")
    print("slides:", len(prs.slides), "| bounds problems:", len(problems))
    for p in problems[:10]:
        print(" ", p)
    missing_notes = [i for i, s in enumerate(prs.slides, 1)
                     if not s.notes_slide.notes_text_frame.text.strip()]
    print("missing notes:", missing_notes or "none")


if __name__ == "__main__":
    build()
    check()
