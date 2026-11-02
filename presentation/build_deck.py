"""Build the IncidentLens final-presentation deck.

The deck is generated from the measured results in
``analysis/wp_d/reports/hardened144-20261101`` and the artifact inventory in
``docs/submission/source_of_truth.md``.  It contains no invented numbers.

Usage:
    .venv/Scripts/python.exe presentation/build_deck.py
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- design system
RED = RGBColor(0x9A, 0x09, 0x07)
RED_DARK = RGBColor(0x6F, 0x05, 0x04)
RED_SOFT = RGBColor(0xF7, 0xE9, 0xE8)
RED_LINE = RGBColor(0xD9, 0xA3, 0xA0)
NAVY = RGBColor(0x00, 0x30, 0x70)
NAVY_SOFT = RGBColor(0xE9, 0xEE, 0xF5)
INK = RGBColor(0x1D, 0x1D, 0x1F)
BODY = RGBColor(0x3A, 0x3A, 0x3E)
MUTED = RGBColor(0x6B, 0x6B, 0x72)
GREY = RGBColor(0xA6, 0xA6, 0xA6)
LIGHT = RGBColor(0xE8, 0xE9, 0xEF)
PALE = RGBColor(0xF4, 0xF4, 0xF6)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x1F, 0x6B, 0x4A)

SERIF = "Georgia"
SANS = "Calibri"

SW, SH = 13.333, 7.5
RAIL = 2.55
LEFT = 3.0
RIGHT = 12.92
WIDTH = RIGHT - LEFT

SECTIONS = ["PROBLEM", "DESIGN", "SYSTEM", "EVALUATION", "DISCUSSION"]
SECTION_INDEX = {"PROBLEM": 0, "DESIGN": 1, "SYSTEM": 2, "EVALUATION": 3, "DISCUSSION": 4}
PAGE = {"n": 0}

prs = Presentation()
prs.slide_width = Inches(SW)
prs.slide_height = Inches(SH)
BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------- primitives
def rgb(hex_value: str) -> RGBColor:
    value = hex_value.lstrip("#")
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def set_shape_fill(shape, color):
    if color is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = color


def set_shape_line(shape, color=None, width=1.0, dash=None):
    if color is None:
        shape.line.fill.background()
        return
    shape.line.color.rgb = color
    shape.line.width = Pt(width)
    if dash is not None:
        shape.line.dash_style = dash


def textbox(slide, x, y, w, h, text="", size=14, color=BODY, bold=False, italic=False,
            font=SANS, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.0,
            margins=(0.0, 0.0, 0.0, 0.0), wrap=True):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = wrap
    frame.margin_left, frame.margin_right, frame.margin_top, frame.margin_bottom = [
        Inches(m) for m in margins
    ]
    frame.vertical_anchor = anchor
    frame.clear()
    p = frame.paragraphs[0]
    p.alignment = align
    p.line_spacing = spacing
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = font
    run.font.color.rgb = color
    return box


def add_run(p, text, size=14, color=BODY, bold=False, italic=False, font=SANS):
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = font
    run.font.color.rgb = color
    return run


def rich_text(slide, x, y, w, h, parts, size=14, color=BODY, spacing=1.1,
              anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT):
    """parts: list of (text, dict overrides) or plain strings."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
    frame.vertical_anchor = anchor
    frame.clear()
    p = frame.paragraphs[0]
    p.alignment = align
    p.line_spacing = spacing
    for part in parts:
        if isinstance(part, str):
            add_run(p, part, size=size, color=color)
        else:
            text, overrides = part
            add_run(
                p,
                text,
                size=overrides.get("size", size),
                color=overrides.get("color", color),
                bold=overrides.get("bold", False),
                italic=overrides.get("italic", False),
                font=overrides.get("font", SANS),
            )
    return box


def bullets(slide, x, y, w, h, items, size=14, color=BODY, bullet_color=RED,
            spacing=1.08, after=7, font=SANS):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
    frame.clear()
    for index, item in enumerate(items):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.line_spacing = spacing
        p.space_after = Pt(after)
        pPr = p._p.get_or_add_pPr()
        pPr.set("marL", str(int(Inches(0.22))))
        pPr.set("indent", str(int(-Inches(0.22))))
        bu = pPr.makeelement(qn("a:buChar"), {"char": "•"})
        pPr.append(bu)
        add_run(p, item, size=size, color=color, font=font)
    return box


def rect(slide, x, y, w, h, fill=WHITE, line=LIGHT, line_w=1.0, shape=MSO_SHAPE.RECTANGLE,
         radius=None, dash=None):
    shp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        shp.adjustments[0] = radius
    set_shape_fill(shp, fill)
    set_shape_line(shp, line, line_w, dash)
    shp.shadow.inherit = False
    return shp


def card(slide, x, y, w, h, fill=WHITE, line=LIGHT, line_w=1.0, radius=0.08):
    return rect(slide, x, y, w, h, fill, line, line_w,
                MSO_SHAPE.ROUNDED_RECTANGLE, radius)


def arrow(slide, x, y, w, h, color=GREY, shape=MSO_SHAPE.RIGHT_ARROW):
    shp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    set_shape_fill(shp, color)
    set_shape_line(shp, None)
    shp.shadow.inherit = False
    return shp


def line(slide, x, y, w, h, color=LIGHT):
    shp = rect(slide, x, y, w, h, color, None, 0)
    return shp


def picture(slide, path, x, y, w=None, h=None):
    if w is not None and h is None:
        return slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w))
    if h is not None and w is None:
        return slide.shapes.add_picture(str(path), Inches(x), Inches(y), height=Inches(h))
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))


def chrome(slide, title, section, subtitle=None):
    PAGE["n"] += 1
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = WHITE

    # left section rail
    rect(slide, 0, 0, RAIL, SH, RED, None, 0)
    for i, name in enumerate(SECTIONS):
        y = 1.28 + i * 0.98
        if i == SECTION_INDEX[section]:
            rect(slide, 0, y - 0.02, 2.30, 0.64, LIGHT, None, 0)
            notch = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW, Inches(2.22), Inches(y - 0.02),
                Inches(0.44), Inches(0.64)
            )
            set_shape_fill(notch, LIGHT)
            set_shape_line(notch, None)
            notch.shadow.inherit = False
            textbox(slide, 0.30, y + 0.11, 1.95, 0.42, f"{i + 1:02d}  {name}",
                    size=13.5, color=RED_DARK, bold=True, font=SERIF)
        else:
            textbox(slide, 0.30, y + 0.11, 1.95, 0.42, f"{i + 1:02d}  {name}",
                    size=12.5, color=RGBColor(0xF2, 0xD6, 0xD4), font=SERIF)
        if i < len(SECTIONS) - 1:
            line(slide, 0.34, y + 0.72, 1.55, 0.008, RGBColor(0xB5, 0x4A, 0x47))
    textbox(slide, 0.30, 6.72, 1.95, 0.4, "COMP5584\nFinal Project",
            size=8.5, color=RGBColor(0xE8, 0xBF, 0xBC), spacing=1.15)

    # content title + identity (shrink long titles so they never collide with the rule)
    title_size = 27 if len(title) <= 40 else (24 if len(title) <= 50 else 21)
    textbox(slide, LEFT, 0.44, 7.85, 0.62, title, size=title_size, color=RED, bold=True,
            font=SERIF, spacing=0.95)
    if subtitle:
        textbox(slide, LEFT, 1.05, 7.9, 0.3, subtitle, size=11.5, color=MUTED, italic=True)
    line(slide, LEFT, 1.27, RIGHT - LEFT, 0.018, NAVY)
    picture(slide, ASSETS / "polyu_logo.png", 10.92, 0.40, w=1.95)

    textbox(slide, LEFT, 7.07, 6.0, 0.25, "IncidentLens  ·  Evidence-driven multi-agent incident investigation",
            size=8.5, color=GREY)
    textbox(slide, 12.25, 7.05, 0.65, 0.25, str(PAGE["n"]), size=9, color=MUTED,
            align=PP_ALIGN.RIGHT)


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text.strip()


def new_slide(title, section, subtitle=None):
    slide = prs.slides.add_slide(BLANK)
    chrome(slide, title, section, subtitle)
    return slide


def badge(slide, x, y, w, text, fill=RED_SOFT, color=RED, size=9.5, h=0.28):
    rect(slide, x, y, w, h, fill, None, 0, MSO_SHAPE.ROUNDED_RECTANGLE, 0.35)
    textbox(slide, x, y + 0.045, w, h - 0.05, text, size=size, color=color, bold=True,
            align=PP_ALIGN.CENTER)


def kpi(slide, x, y, w, h, value, label, note="", value_color=RED):
    card(slide, x, y, w, h, WHITE, LIGHT)
    textbox(slide, x + 0.18, y + 0.13, w - 0.3, 0.58, value, size=27, color=value_color,
            bold=True, font=SERIF)
    textbox(slide, x + 0.18, y + 0.70, w - 0.3, 0.28, label, size=11, color=INK, bold=True)
    if note:
        textbox(slide, x + 0.18, y + 1.00, w - 0.3, 0.34, note, size=9.5, color=MUTED)


# ---------------------------------------------------------------- charts
PALETTE = {
    "Single": "#A6A6A6",
    "Fixed-4": "#C3C6D1",
    "Dynamic": "#9A0907",
    "Full": "#003070",
}
SHORT = {"Single": "Single", "Fixed-4": "Fixed-4", "Dynamic": "Dynamic", "Full": "Full"}


def _style_axes(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#D8D8DC")
    ax.tick_params(colors="#4A4A50", labelsize=9.5, length=0)
    ax.grid(axis="x", color="#E7E7EB", linewidth=0.8)
    ax.set_axisbelow(True)


def chart_quality():
    names = ["Single", "Fixed-4", "Dynamic", "Full"]
    labels = ["Single", "Fixed-4", "Dynamic", "Dynamic + Verifier"]
    values = [32, 22, 33, 30]
    fig, ax = plt.subplots(figsize=(7.2, 2.9), dpi=240)
    y = list(range(len(names)))[::-1]
    bars = ax.barh(y, values, height=0.55,
                   color=[PALETTE[n] for n in names], edgecolor="none")
    for yi, value in zip(y, values):
        ax.text(value + 0.45, yi, f"{value}/36", va="center", fontsize=10.5,
                color="#1D1D1F", fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10.5, color="#1D1D1F")
    ax.set_xlim(0, 38.4)
    ax.set_xticks([0, 9, 18, 27, 36])
    ax.set_xlabel("Quality success (technical failures retained)", fontsize=9.5, color="#6B6B72")
    _style_axes(ax)
    fig.tight_layout(pad=0.4)
    path = ASSETS / "chart_quality.png"
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def chart_cost():
    names = ["Single", "Fixed-4", "Dynamic", "Full"]
    labels = ["Single", "Fixed-4", "Dynamic", "Dynamic + Verifier"]
    tokens = [245.971, 58.042, 149.216, 233.772]
    latency = [680.9, 196.3, 412.9, 503.8]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.85), dpi=240)
    for ax, values, title, unit, limit, fmt in [
        (axes[0], tokens, "Tokens per completed run", "k", 290, "{:.1f}k"),
        (axes[1], latency, "Latency per completed run", "s", 790, "{:.0f}s"),
    ]:
        y = list(range(len(names)))[::-1]
        ax.barh(y, values, height=0.55, color=[PALETTE[n] for n in names], edgecolor="none")
        for yi, value in zip(y, values):
            ax.text(value + limit * 0.025, yi, fmt.format(value), va="center",
                    fontsize=9.5, color="#1D1D1F", fontweight="bold")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8.8, color="#1D1D1F")
        ax.set_xlim(0, limit)
        ax.set_title(title, fontsize=10.5, color="#1D1D1F", fontweight="bold", loc="left")
        ax.set_xlabel(unit, fontsize=8.5, color="#6B6B72")
        _style_axes(ax)
    fig.tight_layout(pad=0.6, w_pad=1.6)
    path = ASSETS / "chart_cost.png"
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def chart_levers():
    levers = ["Competing", "Counterfactual", "Standard", "Boundary",
              "Missing discr.", "Misleading"]
    columns = ["Single", "Fixed-4", "Dynamic", "Full"]
    column_labels = ["Single", "Fixed-4", "Dynamic", "Dyn + Verifier"]
    values = [
        [6 / 7, 4 / 7, 7 / 7, 6 / 7],
        [5 / 6, 3 / 6, 6 / 6, 4 / 6],
        [6 / 7, 3 / 7, 6 / 7, 6 / 7],
        [6 / 7, 4 / 7, 6 / 7, 5 / 7],
        [7 / 7, 7 / 7, 6 / 7, 7 / 7],
        [2 / 2, 1 / 2, 2 / 2, 2 / 2],
    ]
    fig, ax = plt.subplots(figsize=(6.5, 3.35), dpi=240)
    cmap = LinearSegmentedColormap.from_list("polyu", ["#F2F0EF", "#E7C9C6", "#C97A74", "#9A0907"])
    ax.imshow(values, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(4))
    ax.set_xticklabels(column_labels, fontsize=9.2, color="#1D1D1F")
    ax.set_yticks(range(len(levers)))
    ax.set_yticklabels(levers, fontsize=9.2, color="#1D1D1F")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for i, row in enumerate(values):
        for j, value in enumerate(row):
            total = [7, 6, 7, 7, 7, 2][i]
            color = "white" if value >= 0.8 else "#1D1D1F"
            ax.text(j, i, f"{round(value * total)}/{total}", ha="center", va="center",
                    fontsize=9.3, color=color, fontweight="bold")
    fig.tight_layout(pad=0.25)
    path = ASSETS / "chart_levers.png"
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


# ---------------------------------------------------------------- tables
def table(slide, x, y, w, rows, col_widths, font_size=10.5, header_size=10.5,
          row_h=0.36, header_fill=NAVY, highlight=None, align=None, first_col_bold=False):
    shape = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y),
                                   Inches(w), Inches(row_h * len(rows)))
    tbl = shape.table
    tbl.first_row = True
    tbl.horz_banding = False
    total = sum(col_widths)
    for i, width in enumerate(col_widths):
        tbl.columns[i].width = Inches(w * width / total)
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(row_h)
        for c, value in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.05)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            if r == 0:
                fill = header_fill
                color = WHITE
                bold = True
            elif highlight is not None and r == highlight:
                fill = RED_SOFT
                color = RED_DARK
                bold = True
            else:
                fill = WHITE if r % 2 else PALE
                color = BODY
                bold = first_col_bold and c == 0
            cell.fill.solid()
            cell.fill.fore_color.rgb = fill
            frame = cell.text_frame
            frame.word_wrap = True
            frame.clear()
            p = frame.paragraphs[0]
            p.alignment = (align[c] if align else (PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER))
            add_run(p, str(value), size=header_size if r == 0 else font_size,
                    color=color, bold=bold)
    return shape


# ---------------------------------------------------------------- slide 1
def slide_title():
    slide = prs.slides.add_slide(BLANK)
    PAGE["n"] += 1
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = RED

    # white academic flag with stacked university mark
    rect(slide, 0.85, 0.55, 2.55, 4.55, WHITE, None, 0)
    flag = slide.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE, Inches(0.85), Inches(5.10),
                                  Inches(2.55), Inches(0.72))
    set_shape_fill(flag, WHITE)
    set_shape_line(flag, None)
    flag.rotation = 180
    flag.shadow.inherit = False
    picture(slide, ASSETS / "polyu_logo_stacked.png", 1.14, 2.62, w=2.00)

    textbox(slide, 4.05, 1.42, 8.5, 0.4, "COMP5584  ·  LARGE LANGUAGE MODELS FOR AGENTS",
            size=11.5, color=RGBColor(0xF3, 0xCF, 0xCD), bold=True)
    textbox(slide, 4.05, 1.92, 8.7, 0.92, "IncidentLens", size=52, color=WHITE, bold=True,
            font=SERIF)
    textbox(slide, 4.05, 2.86, 8.55, 1.0,
            "Evidence-driven multi-agent incident investigation",
            size=25, color=WHITE, italic=True, font=SERIF, spacing=1.0)
    line(slide, 4.08, 4.02, 4.1, 0.035, RGBColor(0xF0, 0xC9, 0xC6))
    textbox(slide, 4.05, 4.28, 8.2, 0.95,
            "Cited root causes, or explicit abstention — measured against three\n"
            "matched multi-agent architectures.",
            size=15, color=RGBColor(0xFA, 0xE6, 0xE4), spacing=1.15)

    textbox(slide, 4.05, 6.18, 5.6, 0.6,
            "Final Project  ·  Fall 2026  ·  Group ID: ____________",
            size=11.5, color=WHITE, bold=True)
    textbox(slide, 4.05, 6.50, 6.4, 0.35,
            "Team members to be completed by the group",
            size=9.5, color=RGBColor(0xE8, 0xBF, 0xBC), italic=True)
    textbox(slide, 10.35, 6.55, 2.15, 0.35, "LangGraph · Python · Starlette",
            size=8.5, color=RGBColor(0xE8, 0xBF, 0xBC), align=PP_ALIGN.RIGHT)
    notes(slide, """
Opening (Speaker 1, 20 s):
Good morning. We are presenting IncidentLens, a multi-agent system that investigates
software incidents. Its contract is simple: every accepted root cause must cite the
records that support it, and when the evidence is insufficient the system must say so.
We report a matched four-architecture evaluation on a 36-case development corpus.
""")


# ---------------------------------------------------------------- slide 2
def slide_problem():
    slide = new_slide("Incident review is an evidence problem", "PROBLEM",
                      "Why a general-purpose LLM agent is not enough")
    textbox(slide, LEFT, 1.55, 5.0, 0.35, "One incident, four partial views", size=13,
            color=NAVY, bold=True)
    sources = [
        ("Logs", "error chronology, propagation"),
        ("Metrics", "scope, saturation, dependencies"),
        ("Database", "sessions, locks, slow queries"),
        ("Changes", "deploys, config, onset alignment"),
    ]
    for i, (name, desc) in enumerate(sources):
        col, row = i % 2, i // 2
        x = LEFT + col * 2.45
        y = 1.98 + row * 1.02
        card(slide, x, y, 2.30, 0.86, PALE, LIGHT)
        textbox(slide, x + 0.15, y + 0.12, 2.0, 0.26, name, size=12.5, color=RED,
                bold=True)
        textbox(slide, x + 0.15, y + 0.42, 2.0, 0.36, desc, size=9.3, color=MUTED)

    textbox(slide, LEFT, 4.20, 5.0, 0.95,
            "No single source establishes causation. An investigator must align time, "
            "service identity and mechanism across all four — and say what remains unexplained.",
            size=12.2, color=BODY, spacing=1.12)

    rect(slide, LEFT, 5.48, 5.05, 1.34, PALE, None, 0)
    textbox(slide, LEFT + 0.18, 5.58, 4.6, 0.26, "THE REVIEWER'S TEST", size=8.6, color=RED,
            bold=True)
    for i, item in enumerate([
        "Follow every claim to a record.",
        "See which agent observed it, and when.",
        "Check why the alternatives were rejected.",
    ]):
        textbox(slide, LEFT + 0.18, 5.90 + i * 0.27, 4.7, 0.24, "— " + item, size=9.4,
                color=BODY)

    # right: three failure cards
    items = [
        ("01", "Plausible stories", "An LLM can produce a fluent cause with no record-level support."),
        ("02", "Permission blindness", "A general agent reads whatever is in context, including evaluator-only data."),
        ("03", "Confident guessing", "When evidence is thin, the default is still to answer."),
    ]
    for i, (number, title, body) in enumerate(items):
        y = 1.55 + i * 1.62
        card(slide, 8.40, y, 4.48, 1.42, WHITE, LIGHT)
        line(slide, 8.40, y, 0.075, 1.42, RED)
        textbox(slide, 8.62, y + 0.14, 0.55, 0.35, number, size=14, color=RED,
                bold=True, font=SERIF)
        textbox(slide, 9.18, y + 0.12, 3.5, 0.3, title, size=12.8, color=INK, bold=True)
        textbox(slide, 9.18, y + 0.47, 3.45, 0.8, body, size=10.5, color=BODY, spacing=1.08)
    badge(slide, 8.40, 6.38, 4.48, "Contract: cite exact records — or abstain",
          fill=RED, color=WHITE, size=11, h=0.38)
    notes(slide, """
Speaker 1 (42 s):
Incident review is not a summarisation task. Logs, metrics, database state and changes
each show only part of the mechanism. A generic agent can write a convincing story
without citing a single record, can read data it should not see, and will usually answer
even when the evidence is thin. IncidentLens is built around the opposite contract:
every accepted conclusion cites exact records, or the system returns INCONCLUSIVE.
""")


# ---------------------------------------------------------------- slide 3
def slide_question():
    slide = new_slide("The question we set out to test", "PROBLEM",
                      "Scope: synthetic, read-only incident packs; no production changes")
    rect(slide, LEFT, 1.58, 5.55, 2.45, NAVY, None, 0)
    textbox(slide, LEFT + 0.32, 1.78, 4.95, 1.85,
            "Can a coordinated multi-agent system investigate incidents with evidence "
            "a reviewer can audit, and abstain when the visible evidence is insufficient "
            "— at an acceptable cost?",
            size=18.5, color=WHITE, font=SERIF, italic=True, spacing=1.08)
    textbox(slide, LEFT + 0.32, 3.52, 4.9, 0.3, "RESEARCH QUESTION", size=9.5,
            color=RGBColor(0xBF, 0xCF, 0xE6), bold=True)

    textbox(slide, LEFT, 4.30, 5.55, 0.35, "Why multi-agent, specifically", size=12.5,
            color=RED, bold=True)
    textbox(slide, LEFT, 4.68, 5.55, 1.10,
            "The four evidence sources need different tools and different questions. "
            "Roles create scoped access; a coordinator decides which gap matters next. "
            "This is specialisation and coordination — not four independent LLM calls.",
            size=11.8, color=BODY, spacing=1.12)
    textbox(slide, LEFT, 5.86, 5.55, 0.28,
            "Non-goals: production changes, real telemetry, a model leaderboard.",
            size=9.4, color=MUTED, italic=True)

    contributions = [
        ("01", "Dynamic coordination", "A supervisor allocates 1–2 specialist tasks per round from the current evidence gap, inside a hard budget."),
        ("02", "Cited-or-abstain gates", "Merge and FinalizeGate are deterministic: model confidence never decides acceptance."),
        ("03", "Matched measurement", "Four architectures, 144 slots, six difficulty levers, and an explicit failure analysis."),
    ]
    for i, (number, title, body) in enumerate(contributions):
        y = 1.60 + i * 1.52
        card(slide, 8.75, y, 4.12, 1.33, WHITE, LIGHT)
        textbox(slide, 8.95, y + 0.12, 0.5, 0.35, number, size=12.5, color=RED, bold=True,
                font=SERIF)
        textbox(slide, 9.42, y + 0.11, 3.2, 0.3, title, size=12.2, color=INK, bold=True)
        textbox(slide, 9.42, y + 0.44, 3.2, 0.82, body, size=10.2, color=BODY, spacing=1.06)

    rect(slide, LEFT, 6.36, 9.87, 0.44, RED_SOFT, None, 0)
    textbox(slide, LEFT + 0.15, 6.44, 9.55, 0.28,
            "Evaluation in one line: 4 matched architectures × 36 cases × 1 repeat = 144 runs; 136 completed.",
            size=10.5, color=RED_DARK, bold=True)
    notes(slide, """
Speaker 1 (38 s):
Our research question has two halves: can the system produce an auditable answer, and
can it refuse when the evidence is thin, without paying an unreasonable cost? Multi-agent
design is justified by evidence specialisation and by coordination: the coordinator
chooses the next gap, rather than running every specialist every time. We test this with
four matched architectures and 144 attempted runs.
""")


# ---------------------------------------------------------------- slide 4
def slide_architecture():
    slide = new_slide("One auditable investigation pipeline", "DESIGN",
                      "Model-driven steps are light; deterministic state and gates are outlined")
    # input
    card(slide, LEFT, 1.62, 1.55, 2.25, PALE, LIGHT)
    textbox(slide, LEFT + 0.12, 1.74, 1.3, 0.3, "PUBLIC INPUT", size=8.5, color=NAVY,
            bold=True)
    for i, label in enumerate(["logs", "metrics", "database", "changes"]):
        textbox(slide, LEFT + 0.14, 2.10 + i * 0.38, 1.25, 0.3, "• " + label, size=10.2,
                color=BODY)
    textbox(slide, LEFT + 0.12, 3.55, 1.35, 0.3, "Optional monitor", size=8.5,
            color=MUTED, italic=True)

    # coordinator
    rect(slide, 4.78, 1.62, 2.05, 0.82, NAVY, None, 0)
    textbox(slide, 4.90, 1.72, 1.85, 0.3, "COORDINATOR", size=10.2, color=WHITE, bold=True)
    textbox(slide, 4.90, 2.02, 1.82, 0.3, "supervisor · budget owner", size=8.2,
            color=RGBColor(0xC9, 0xD6, 0xE8))
    arrow(slide, LEFT + 1.55, 1.93, 0.42, 0.18, GREY)

    # specialists inside one pool
    card(slide, 4.68, 2.56, 2.28, 1.62, PALE, LIGHT, 0.8, 0.04)
    textbox(slide, 4.74, 2.60, 1.3, 0.18, "SPECIALIST POOL", size=6.6, color=MUTED,
            bold=True)
    roles = [("Logs", "chronology"), ("Metrics", "scope"), ("Database", "locks / pools"),
             ("Changes", "triggers")]
    for i, (name, sub) in enumerate(roles):
        col, row = i % 2, i // 2
        x = 4.78 + col * 1.08
        y = 2.80 + row * 0.64
        card(slide, x, y, 1.00, 0.56, WHITE, RED_LINE, 0.8)
        textbox(slide, x + 0.06, y + 0.06, 0.9, 0.24, name, size=8.8, color=INK, bold=True,
                align=PP_ALIGN.CENTER)
        textbox(slide, x + 0.04, y + 0.29, 0.92, 0.22, sub, size=7.0, color=MUTED,
                align=PP_ALIGN.CENTER)
    arrow(slide, 5.66, 2.45, 0.16, 0.14, GREY, MSO_SHAPE.DOWN_ARROW)
    textbox(slide, 5.88, 2.42, 1.1, 0.22, "1–2 tasks / round", size=7.2, color=MUTED)

    # merge
    rect(slide, 4.78, 4.40, 2.05, 0.62, RED_SOFT, RED, 1.0)
    textbox(slide, 4.86, 4.50, 1.92, 0.26, "MERGE  deterministic", size=9.4, color=RED_DARK,
            bold=True, align=PP_ALIGN.CENTER)
    textbox(slide, 4.86, 4.73, 1.90, 0.22, "identity · citations · reconciliation", size=7.1,
            color=MUTED, align=PP_ALIGN.CENTER)
    arrow(slide, 5.68, 4.20, 0.16, 0.18, GREY, MSO_SHAPE.DOWN_ARROW)

    # state board
    card(slide, 7.12, 4.40, 1.55, 0.62, PALE, LIGHT)
    textbox(slide, 7.18, 4.50, 1.42, 0.42, "Hypothesis\nboard", size=9.0, color=INK,
            bold=True, align=PP_ALIGN.CENTER)
    arrow(slide, 6.84, 4.62, 0.24, 0.18, GREY)

    # verifier (its review returns to the coordinator; drawn without an implied data edge)
    card(slide, 4.78, 5.24, 3.9, 0.56, WHITE, NAVY, 0.9)
    textbox(slide, 4.92, 5.33, 3.65, 0.38,
            "Verifier (ablation): reviews hypotheses; its review returns to the coordinator.",
            size=7.9, color=NAVY, spacing=1.0)

    # right column
    rect(slide, 9.45, 1.62, 3.45, 0.82, WHITE, NAVY, 1.4)
    textbox(slide, 9.62, 1.71, 3.15, 0.28, "FINALIZE GATE", size=10.2, color=NAVY, bold=True)
    textbox(slide, 9.62, 2.02, 3.1, 0.3, "citations · causal chain · blockers", size=8.0,
            color=MUTED)
    arrow(slide, 6.84, 1.94, 2.52, 0.18, GREY)

    card(slide, 9.45, 2.70, 3.45, 0.88, RED_SOFT, RED_LINE, 0.9)
    textbox(slide, 9.62, 2.80, 3.1, 0.28, "Report  ·  RESOLVED", size=10.0, color=RED_DARK,
            bold=True)
    textbox(slide, 9.62, 3.08, 3.1, 0.28, "cited root cause + causal chain", size=8.0,
            color=BODY)
    card(slide, 9.45, 3.70, 3.45, 0.88, PALE, LIGHT)
    textbox(slide, 9.62, 3.80, 3.1, 0.28, "Abstain  ·  INCONCLUSIVE", size=10.0, color=INK,
            bold=True)
    textbox(slide, 9.62, 4.08, 3.1, 0.28, "what is missing, what to check next", size=8.0,
            color=BODY)

    card(slide, 9.45, 4.90, 3.45, 0.70, WHITE, LIGHT)
    textbox(slide, 9.62, 5.00, 3.1, 0.26, "Remediation  ·  PLAN_ONLY", size=9.2, color=NAVY,
            bold=True)
    textbox(slide, 9.62, 5.25, 3.1, 0.24, "proposal only; no execution", size=7.8, color=MUTED)
    arrow(slide, 9.62, 4.62, 0.14, 0.22, GREY, MSO_SHAPE.DOWN_ARROW)

    # gate -> outcomes
    arrow(slide, 11.06, 2.44, 0.14, 0.22, GREY, MSO_SHAPE.DOWN_ARROW)

    # state -> gate elbow
    line(slide, 8.68, 4.71, 0.35, 0.025, GREY)
    line(slide, 9.01, 2.03, 0.025, 2.70, GREY)
    arrow(slide, 9.22, 1.94, 0.20, 0.18, GREY, MSO_SHAPE.RIGHT_ARROW)

    textbox(slide, LEFT, 5.98, 9.8, 0.8,
            "Budgets: 4 rounds · 12 tool calls · 16 LLM requests · 600 s.  Dynamic = primary runtime; "
            "single, fixed-4 and dynamic+verifier are ablation controls.",
            size=9.4, color=MUTED, spacing=1.1)
    notes(slide, """
Speaker 2 (45 s):
This is the whole system. Public evidence enters; an optional monitor can raise an alert.
The coordinator owns the budget and assigns at most two specialist tasks per round.
Specialists can only call tools allowed for their role. Merge validates identity, task,
role and every citation, then updates a shared hypothesis board. FinalizeGate makes the
deterministic accept/abstain decision. Remediation runs only after acceptance and is
plan-only. The verifier is an optional ablation, not part of the primary runtime.
""")


# ---------------------------------------------------------------- slide 5
def slide_agents():
    slide = new_slide("Roles are real; permissions are code", "DESIGN",
                      "Access ceilings are enforced by the runtime, not by prompt wording")
    rows = [
        ["Agent", "Responsibility", "Allowed read-only tools"],
        ["Coordinator", "Reads the evidence gap; assigns or replans 1–2 tasks; chooses finalize or abstain", "none (state only)"],
        ["Log Investigator", "Reconstructs error chronology and separates cause from symptom", "query_logs"],
        ["Metrics & Dependency", "Locates scope, saturation and dependency anomalies", "query_metrics · get_dependencies"],
        ["Database Investigator", "Inspects sessions, locks, pools and slow queries", "5 database tools"],
        ["Change Investigator", "Aligns deployments and config changes with onset", "query_changes · get_config_diff"],
        ["Verifier (ablation)", "Challenges a candidate and requests a discriminating check", "fetch_evidence_by_ids"],
        ["Remediation", "Produces a plan with preconditions, risks, verification and rollback", "none (accepted findings only)"],
    ]
    table(slide, LEFT, 1.55, 9.9, rows, [1.55, 4.85, 2.6], font_size=9.8, header_size=9.8,
          row_h=0.47, highlight=1, first_col_bold=True)
    textbox(slide, LEFT, 5.72, 9.85, 0.28,
            "The single-agent baseline receives the union of investigator tools; every other role is scoped.",
            size=9.3, color=MUTED, italic=True)
    for i, (label, color) in enumerate([
        ("Immutable AgentContext", NAVY),
        ("Actual-query ledger", RED),
        ("Public file allowlist", NAVY),
    ]):
        x = LEFT + i * 3.35
        rect(slide, x, 6.13, 3.10, 0.48, WHITE, color, 1.0)
        textbox(slide, x + 0.12, 6.23, 2.9, 0.28, label, size=9.6, color=color, bold=True)
    notes(slide, """
Speaker 2 (38 s):
Roles are not personas in a prompt. The coordinator has no evidence tools; each
specialist has only the tools for its source. The verifier can fetch only records already
observed, by ID. The context object is immutable, an actual-query ledger records what was
read, and the data provider exposes only public files. These are code-level boundaries,
which is what makes the architecture meaningful rather than cosmetic.
""")


# ---------------------------------------------------------------- slide 6
def slide_coordination():
    slide = new_slide("Coordination follows the evidence gap", "DESIGN",
                      "Dynamic dispatch, bounded rounds, deterministic merge")
    textbox(slide, LEFT, 1.55, 5.2, 0.32, "ONE ROUND, FOUR MOVES", size=9.5, color=RED,
            bold=True)
    steps = [
        ("1", "Read the gap", "Coordinator sees the public summary, current hypotheses and unresolved questions."),
        ("2", "Assign ≤ 2 tasks", "Each task names a role, a question and a cause-specific discriminator."),
        ("3", "Investigate", "Specialists query within their ACL; results return as cited findings."),
        ("4", "Merge + reconcile", "Validated batches update stable hypotheses; conflicts become OPEN, never silently closed."),
    ]
    for i, (number, title, body) in enumerate(steps):
        y = 1.95 + i * 0.98
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(LEFT), Inches(y),
                                        Inches(0.38), Inches(0.38))
        set_shape_fill(circle, RED if i == 0 else WHITE)
        set_shape_line(circle, RED, 1.1)
        textbox(slide, LEFT, y + 0.075, 0.38, 0.24, number, size=9.2,
                color=WHITE if i == 0 else RED, bold=True, align=PP_ALIGN.CENTER)
        textbox(slide, LEFT + 0.56, y - 0.02, 4.5, 0.28, title, size=11.8, color=INK,
                bold=True)
        textbox(slide, LEFT + 0.56, y + 0.28, 4.55, 0.6, body, size=9.6, color=BODY,
                spacing=1.05)

    textbox(slide, 8.55, 1.55, 4.3, 0.3, "COORDINATOR DECISION CONTRACT", size=9.5,
            color=RED, bold=True)
    decisions = [
        ("INVESTIGATE", "1–2 assignments; no selected hypothesis", RED_SOFT, RED),
        ("FINALIZE", "One selected hypothesis; stop reason", NAVY_SOFT, NAVY),
        ("ABSTAIN", "No selection; explicit stop reason", PALE, MUTED),
    ]
    for i, (name, desc, fill, color) in enumerate(decisions):
        y = 1.92 + i * 0.92
        rect(slide, 8.55, y, 4.32, 0.76, fill, None, 0, MSO_SHAPE.ROUNDED_RECTANGLE, 0.08)
        textbox(slide, 8.72, y + 0.10, 1.5, 0.26, name, size=10.3, color=color, bold=True)
        textbox(slide, 8.72, y + 0.38, 3.95, 0.28, desc, size=8.8, color=BODY)

    textbox(slide, 8.55, 4.92, 4.3, 0.3, "HARD BOUNDS", size=9.5, color=RED, bold=True)
    budget = [("4", "rounds"), ("12", "tool calls"), ("16", "LLM requests"), ("600 s", "wall clock")]
    for i, (value, label) in enumerate(budget):
        x = 8.55 + (i % 2) * 2.18
        y = 5.26 + (i // 2) * 0.72
        textbox(slide, x, y, 0.9, 0.3, value, size=15, color=RED, bold=True, font=SERIF)
        textbox(slide, x + 0.72, y + 0.06, 1.3, 0.26, label, size=8.8, color=MUTED)
    textbox(slide, 8.55, 6.66, 4.3, 0.25,
            "Exhaustion = runtime failure; insufficiency = INCONCLUSIVE.", size=8.3,
            color=MUTED, italic=True)
    rect(slide, LEFT, 5.98, 5.25, 0.58, PALE, None, 0)
    textbox(slide, LEFT + 0.14, 6.09, 5.0, 0.38,
            "An assignment without a discriminator cannot change the answer.",
            size=9.4, color=RED_DARK, italic=True)
    notes(slide, """
Speaker 2 (42 s):
Dynamic coordination is the core design claim. Each round starts from the current
evidence gap, not from a fixed checklist. The coordinator emits one of three contracts:
investigate, finalize or abstain. It can assign at most two tasks, each with a
discriminator that would move the hypothesis. Merge reconciles support and conflict, and
hypothesis IDs stay stable across rounds. Budgets are physical requests and retries, so
the loop cannot run forever.
""")


# ---------------------------------------------------------------- slide 7
def slide_gates():
    slide = new_slide("Grounding is a deterministic gate", "DESIGN",
                      "Not a prompt style: citations, identity and blockers are checked in code")
    flow = ["Candidate\nhypothesis", "Citations exist\nin observed set", "Identity + state\nmatch",
            "Gate decision", "Report or\nabstain"]
    for i, label in enumerate(flow):
        x = LEFT + i * 2.02
        fill = RED if i == 4 else (NAVY if i == 3 else PALE)
        color = WHITE if i >= 3 else INK
        border = RED if i == 4 else (NAVY if i == 3 else LIGHT)
        rect(slide, x, 1.58, 1.74, 0.80, fill, border, 1.0, MSO_SHAPE.ROUNDED_RECTANGLE, 0.08)
        textbox(slide, x + 0.08, 1.68, 1.58, 0.6, label, size=9.4, color=color, bold=True,
                align=PP_ALIGN.CENTER, spacing=1.0)
        if i < 4:
            arrow(slide, x + 1.78, 1.89, 0.20, 0.18, GREY)

    textbox(slide, LEFT, 2.78, 5.55, 0.3, "FOUR CHECKS, ALL DETERMINISTIC", size=9.5,
            color=RED, bold=True)
    bullets(slide, LEFT, 3.13, 5.55, 1.70, [
        "Every cited evidence ID exists in the records actually observed in this run.",
        "Finding identity matches run, incident, task and role before it can influence a hypothesis.",
        "A resolved root cause needs a supported hypothesis and a causal chain, not just a top score.",
        "Unresolved blockers, open contradictions and missing discriminators force abstention.",
    ], size=10.3, color=BODY, after=7)
    card(slide, LEFT, 4.98, 5.55, 1.00, PALE, LIGHT)
    textbox(slide, LEFT + 0.16, 5.07, 5.2, 0.24, "WHAT THE GATE USES — AND NEVER USES", size=8.2,
            color=RED, bold=True)
    textbox(slide, LEFT + 0.16, 5.34, 5.25, 0.55,
            "Uses: hypothesis, findings, cited IDs, observed-ID set, blocker list.\n"
            "Never: model confidence, chain-of-thought, evaluator labels.",
            size=9.1, color=BODY, spacing=1.06)

    # outcomes
    card(slide, 8.75, 2.85, 3.45, 1.45, RED_SOFT, RED_LINE, 1.0)
    textbox(slide, 8.95, 2.96, 3.0, 0.3, "RESOLVED", size=11, color=RED, bold=True)
    textbox(slide, 8.95, 3.28, 3.05, 0.95,
            "A root cause with supporting citations, a causal chain, and no blocking gap.",
            size=9.4, color=BODY, spacing=1.08)
    card(slide, 8.75, 4.45, 3.45, 1.45, PALE, LIGHT)
    textbox(slide, 8.95, 4.56, 3.0, 0.3, "INCONCLUSIVE", size=11, color=INK, bold=True)
    textbox(slide, 8.95, 4.88, 3.05, 0.95,
            "No cause accepted. The report preserves observations, gaps and next checks.",
            size=9.4, color=BODY, spacing=1.08)

    rect(slide, LEFT, 6.12, 9.9, 0.50, NAVY, None, 0)
    textbox(slide, LEFT + 0.18, 6.21, 9.55, 0.30,
            "BEST_SUPPORTED_AVAILABLE is still not proof: it is the strongest supported explanation given visible evidence.",
            size=9.6, color=WHITE, italic=True)
    notes(slide, """
Speaker 3 (33 s):
This is the trust mechanism. A candidate must cite records that were actually observed;
the finding must match the run, task and role that produced it; a resolved answer needs a
supported chain; and any unresolved blocker forces abstention. The gate does not ask the
model how confident it feels. The strongest accepted statement is
BEST_SUPPORTED_AVAILABLE, which is deliberately weaker than proof.
""")


# ---------------------------------------------------------------- slide 8
def slide_implementation():
    slide = new_slide("Implementation is reproducible", "SYSTEM",
                      "Failure-aware and offline-capable; the same contracts behind CLI, web and replay")
    tech = ["Python 3.11+", "LangGraph StateGraph", "Pydantic v2", "Starlette + ES modules",
            "pytest"]
    x = LEFT
    width = (9.9 - 0.12 * (len(tech) - 1)) / len(tech)
    for label in tech:
        rect(slide, x, 1.55, width, 0.42, NAVY_SOFT, None, 0, MSO_SHAPE.ROUNDED_RECTANGLE, 0.3)
        textbox(slide, x, 1.63, width, 0.26, label, size=8.6, color=NAVY, bold=True,
                align=PP_ALIGN.CENTER)
        x += width + 0.12

    textbox(slide, LEFT, 2.30, 4.7, 0.3, "REPRODUCIBLE BY DEFAULT", size=9.5, color=RED,
            bold=True)
    bullets(slide, LEFT, 2.65, 4.65, 2.5, [
        "Deterministic Mock provider: no API key, no model weights, same public evidence.",
        "40 public incident packs; 36 hardened development cases used for evaluation.",
        "Replay validates a saved trace and re-renders it without calling graph, tools or provider.",
        "CLI and web share the same runtime contracts; downloaded trace.json is the artifact.",
    ], size=9.8, color=BODY, after=7)

    textbox(slide, 8.00, 2.30, 4.8, 0.3, "FAILURE HANDLING IS PART OF THE DESIGN", size=9.5,
            color=RED, bold=True)
    bullets(slide, 8.00, 2.65, 4.80, 2.5, [
        "Bounded provider recovery with atomic request permits and classified transport errors.",
        "One targeted structured-output repair per stage; truncation is recorded as a technical failure.",
        "Task-local stage budgets; partial batch failure can continue when safe.",
        "Unified stop protocol with acknowledgement and a bounded timeout.",
    ], size=9.8, color=BODY, after=7)

    rect(slide, LEFT, 4.30, 9.9, 0.92, PALE, LIGHT)
    textbox(slide, LEFT + 0.18, 4.40, 1.6, 0.24, "CURRENT TEST SUITE", size=8.3, color=RED,
            bold=True)
    textbox(slide, LEFT + 0.18, 4.64, 5.1, 0.40,
            "1,179 passed · 3 skipped · no failures", size=16.5, color=INK, bold=True, font=SERIF)
    textbox(slide, 8.55, 4.55, 4.15, 0.45,
            "Full pytest run · 2026-11-02 · 381 s\nExit code 0",
            size=8.6, color=MUTED, align=PP_ALIGN.RIGHT, spacing=1.1)

    rect(slide, LEFT, 5.52, 9.9, 1.18, PALE, LIGHT)
    textbox(slide, LEFT + 0.18, 5.63, 1.3, 0.25, "RUN IT", size=8.5, color=RED, bold=True)
    code = (".venv/Scripts/python.exe -m incident_lens.cli validate-data\n"
            ".venv/Scripts/python.exe -m incident_lens.cli run --case incident_001 --provider mock --out results/demo\n"
            ".venv/Scripts/python.exe -m incident_lens.cli replay --trace results/demo/trace.json")
    textbox(slide, LEFT + 0.18, 5.90, 9.55, 0.72, code, size=8.8, color=INK, font="Consolas",
            spacing=1.12)
    notes(slide, """
Speaker 3 (33 s):
The implementation is a LangGraph state machine with typed Pydantic contracts. The same
runtime powers the CLI and the web console; a saved trace can be replayed without touching
the graph, tools or model provider. Failure handling is explicit: bounded recovery,
request permits, one structured-output repair, task budgets and a unified stop protocol.
This matters because the evaluation counts technical failures rather than hiding them.
""")


# ---------------------------------------------------------------- slide 9
def slide_demo():
    slide = new_slide("Demo: live run, then replay", "SYSTEM",
                      "The console exposes the same evidence the gates used")
    shot = ASSETS / "demo_console.png"
    if shot.exists():
        picture(slide, shot, LEFT, 1.55, w=6.55)
        rect(slide, LEFT, 1.55, 6.55, 4.42, None, LIGHT, 0.8)
    else:
        rect(slide, LEFT, 1.55, 6.55, 4.42, PALE, LIGHT, 1.0)
        textbox(slide, LEFT, 3.40, 6.55, 0.5, "Console screenshot to be captured",
                size=12, color=MUTED, italic=True, align=PP_ALIGN.CENTER)

    textbox(slide, 9.85, 1.55, 3.0, 0.3, "THREE CUES", size=9.5, color=RED, bold=True)
    cues = [
        ("1", "Run live", "Mock provider, incident_001; watch IDs, budget and gate status change."),
        ("2", "Replay", "Open the same trace; confirm the badge says Recorded Replay."),
        ("3", "Audit", "Click a citation: source file, query, agent and timestamp are shown."),
    ]
    for i, (number, title, body) in enumerate(cues):
        y = 1.95 + i * 1.15
        textbox(slide, 9.85, y, 0.4, 0.3, number, size=15, color=RED, bold=True, font=SERIF)
        textbox(slide, 10.30, y - 0.02, 2.55, 0.28, title, size=11.3, color=INK, bold=True)
        textbox(slide, 10.30, y + 0.30, 2.52, 0.70, body, size=9.1, color=BODY, spacing=1.05)

    rect(slide, 9.85, 5.60, 3.0, 0.74, NAVY_SOFT, None, 0)
    textbox(slide, 9.98, 5.70, 2.75, 0.58,
            "The UI labels Live vs Recorded Replay and Mock vs Real. Screenshots are captured from the running app.",
            size=8.4, color=NAVY, spacing=1.08)
    notes(slide, """
Speaker 3 (70 s, includes demo):
We will run incident_001 with the Mock provider. Point out that the coordinator chooses
two tasks, then a second round; the budget counters move; FinalizeGate accepts only after
citations are present. Then we open the same trace as a recorded replay: the badge changes
and the graph, tools and provider are not called. Finally we click one citation to show
its source file, the query that produced it, the agent and the timestamp.
""")


# ---------------------------------------------------------------- slide 10
def slide_evaluation_design():
    slide = new_slide("Does coordination earn its cost?", "EVALUATION",
                      "Matched comparisons on a development-visible corpus")
    stats = [
        ("36", "hardened cases", "29 identifiable · 7 must abstain"),
        ("4", "matched architectures", "Single · Fixed-4 · Dynamic · Dynamic + verifier"),
        ("144", "attempted slots", "136 completed; failures retained"),
        ("6", "difficulty levers", "competing · counterfactual · boundary · missing · misleading · standard"),
    ]
    for i, (value, label, note) in enumerate(stats):
        col, row = i % 2, i // 2
        kpi(slide, LEFT + col * 5.05, 1.58 + row * 1.62, 4.80, 1.42, value, label, note)

    textbox(slide, LEFT, 4.90, 9.85, 0.3, "SCORING DISCIPLINE", size=9.5, color=RED,
            bold=True)
    rows = [
        ["Principle", "Consequence"],
        ["Technical failure stays in the attempted denominator", "Quality is success / 36, not success / completed"],
        ["Root correctness uses identifiable completed runs only", "27/27 is not inflated by abstentions"],
        ["Abstention uses unidentifiable completed runs only", "6/6 or 7/7 is separate from root accuracy"],
    ]
    table(slide, LEFT, 5.22, 9.87, rows, [5.1, 4.7], font_size=9.4, header_size=9.4,
          row_h=0.35, align=[PP_ALIGN.LEFT, PP_ALIGN.LEFT])
    textbox(slide, LEFT, 6.75, 9.85, 0.25,
            "Labels are evaluator-only and provisional; the corpus is not a blind test set.",
            size=8.5, color=MUTED, italic=True)
    notes(slide, """
Speaker 4 (38 s):
The evaluation is a matched comparison, not a leaderboard. All four architectures use
the same public evidence, tools, budgets, model and decoding settings. Technical failures
stay in the denominator, root accuracy is computed only on identifiable completed runs,
and abstention only on unidentifiable completed runs. The labels are evaluator-only and
provisional, and the corpus is development-visible.
""")


# ---------------------------------------------------------------- slide 11
def slide_quality():
    slide = new_slide("Dynamic leads on quality", "EVALUATION",
                      "Hardened 36-case batch, 2026-11-01; zero wrong root causes")
    rows = [
        ["Architecture", "Completed", "Root correct", "Abstain", "Quality", "Latency", "Tokens"],
        ["Single", "35/36", "25/28", "7/7", "32/36", "680.9 s", "246.0k"],
        ["Fixed-4", "34/36", "15/27", "7/7", "22/36", "196.3 s", "58.0k"],
        ["Dynamic (primary)", "33/36", "27/27", "6/6", "33/36", "412.9 s", "149.2k"],
        ["Dynamic + Verifier", "34/36", "23/27", "7/7", "30/36", "503.8 s", "233.8k"],
    ]
    table(slide, LEFT, 1.58, 9.9, rows, [2.5, 1.15, 1.3, 1.05, 1.1, 1.15, 1.15],
          font_size=10.2, header_size=9.6, row_h=0.46, highlight=3,
          align=[PP_ALIGN.LEFT] + [PP_ALIGN.CENTER] * 6)
    textbox(slide, LEFT, 3.92, 9.85, 0.3,
            "Quality success counts technical failures; root correct and abstention use their own eligible denominators.",
            size=8.4, color=MUTED, italic=True)
    kpi(slide, LEFT, 4.40, 3.12, 1.42, "33/36", "Quality success", "highest of the four")
    kpi(slide, LEFT + 3.38, 4.40, 3.12, 1.42, "27/27", "Root correct",
        "every identifiable completed run", value_color=NAVY)
    kpi(slide, LEFT + 6.76, 4.40, 3.12, 1.42, "0", "Wrong root causes",
        "19 misses, all INCONCLUSIVE")
    textbox(slide, LEFT, 6.10, 9.85, 0.62,
            "Fixed-4 is cheap but wrongly abstains on 12 of 27 identifiable cases. Dynamic is the only variant at "
            "7/7 on competing causes and 6/6 on counterfactual pairs.",
            size=9.1, color=BODY, spacing=1.1)
    notes(slide, """
Speaker 4 (42 s):
On quality, Dynamic completes 33 of 36 and is the only architecture to get every
identifiable completed case right: 27 of 27. The more important result is the zero:
across 144 attempts, no run named a wrong root cause. All 19 identifiable misses ended in
INCONCLUSIVE. Fixed-4 is cheaper but wrongly abstains on 12 of 27 identifiable cases.
Dynamic is also strongest on competing causes and counterfactual pairs.
""")


# ---------------------------------------------------------------- slide 12
def slide_cost():
    slide = new_slide("Coordination pays for itself", "EVALUATION",
                      "The verifier added cost without a measured gain; one model, one repeat")
    chart = chart_cost()
    picture(slide, chart, LEFT, 1.62, w=6.45)
    textbox(slide, LEFT, 4.60, 6.4, 0.28, "Per completed run; lower is better.", size=8.5,
            color=MUTED, italic=True)

    textbox(slide, 9.80, 1.58, 3.1, 0.3, "RELATIVE TO DYNAMIC", size=9.5, color=RED,
            bold=True)
    comps = [
        ("vs Single", "+1 quality", "−39.4% latency", "−39.3% tokens"),
        ("vs Dynamic + Verifier", "+3 quality", "−18.0% latency", "−36.2% tokens"),
        ("Verifier loop", "no measured gain", "+56.7% tokens", ""),
    ]
    for i, (title, a, b, c) in enumerate(comps):
        y = 1.96 + i * 1.42
        card(slide, 9.80, y, 3.10, 1.22, WHITE, LIGHT)
        textbox(slide, 9.94, y + 0.10, 2.85, 0.28, title, size=10.2, color=INK, bold=True)
        textbox(slide, 9.94, y + 0.40, 2.8, 0.72,
                f"{a}\n{b}" + (f"\n{c}" if c else ""), size=8.9, color=BODY, spacing=1.08)
    rect(slide, LEFT, 4.98, 6.45, 0.98, PALE, None, 0)
    textbox(slide, LEFT + 0.16, 5.09, 6.12, 0.76,
            "Fixed-4 is the cheapest design, but 11 quality successes behind Dynamic. "
            "The difference is targeted evidence, not more calls.",
            size=9.6, color=BODY, spacing=1.08)
    textbox(slide, LEFT, 6.35, 9.85, 0.52,
            "Latency and tokens are averaged over completed runs only; the verifier is an ablation, not the primary architecture.",
            size=8.8, color=MUTED, italic=True)
    notes(slide, """
Speaker 4 (42 s):
Cost changes the conclusion. Dynamic beats Single on quality by one while using about
39 percent less latency and 39 percent fewer tokens. Against the verifier variant it gains
three quality successes while using 18 percent less latency and 36 percent fewer tokens.
The verifier cost 57 percent more tokens and produced no measurable quality gain in this
batch. These are descriptive differences from one model and one repeat; we do not claim
statistical significance.
""")


# ---------------------------------------------------------------- slide 13
def slide_failures():
    slide = new_slide("The failure mode is conservative", "EVALUATION",
                      "The dominant error is a missed conclusion, not an invented cause")
    chart = chart_levers()
    picture(slide, chart, LEFT, 1.60, w=6.05)
    textbox(slide, LEFT, 5.28, 6.0, 0.28, "Correct / eligible runs by lever and architecture.",
            size=8.5, color=MUTED, italic=True)

    textbox(slide, 9.45, 1.58, 3.4, 0.3, "WHAT WENT WRONG", size=9.5, color=RED, bold=True)
    stats = [
        ("19", "identifiable misses", "all ended INCONCLUSIVE — none named a wrong cause"),
        ("8 / 144", "technical failures", "6 truncated structured outputs · 2 identity mismatches"),
        ("12 / 27", "Fixed-4 over-abstentions", "one fixed batch cannot recover a missed gap"),
    ]
    for i, (value, label, note) in enumerate(stats):
        y = 1.95 + i * 1.35
        textbox(slide, 9.45, y, 1.25, 0.45, value, size=19, color=RED, bold=True,
                font=SERIF)
        textbox(slide, 10.75, y + 0.02, 2.05, 0.30, label, size=9.6, color=INK, bold=True)
        textbox(slide, 10.75, y + 0.32, 2.05, 0.78, note, size=8.3, color=BODY, spacing=1.05)
        line(slide, 9.45, y + 1.12, 3.35, 0.008, LIGHT)
    rect(slide, LEFT, 6.10, 9.85, 0.62, RED_SOFT, None, 0)
    textbox(slide, LEFT + 0.16, 6.20, 9.55, 0.42,
            "Dynamic is strongest on the hard levers; its remaining errors are missed conclusions, not invented ones.",
            size=9.7, color=RED_DARK, bold=True)
    notes(slide, """
Speaker 5 (38 s):
This slide is the honest failure analysis. The dominant error is over-abstention: 19
identifiable cases ended INCONCLUSIVE, including 12 under Fixed-4. There were eight
technical failures out of 144, six truncated structured outputs and two identity
mismatches, and we keep them in the denominator. Dynamic is strongest on competing
causes and counterfactual pairs. The risk profile is conservative: missed conclusions,
not fabricated causes.
""")


# ---------------------------------------------------------------- slide 14
def slide_limits():
    slide = new_slide("What this evaluation does not establish", "DISCUSSION",
                      "Boundaries are part of the result, not a disclaimer at the end")
    limits = [
        ("No blind test", "The corpus is development-visible; labels are evaluator-only and provisional."),
        ("One model, one repeat", "No confidence intervals, significance tests or cross-model replication."),
        ("Over-abstention", "19 identifiable runs ended INCONCLUSIVE (Fixed-4 12, verifier variant 4, Single 3, Dynamic 0); none named a wrong cause."),
        ("Replay-estimated guard", "The −44% / −22% / −12% token estimates are replayed, not live."),
        ("Mock-only recovery", "Cache and recovery paths are validated on Mock traces, not production traffic."),
        ("Synthetic corpus", "Read-only packs; no production telemetry, users or remediation execution."),
    ]
    for i, (title, body) in enumerate(limits):
        col, row = i % 2, i // 2
        x = LEFT + col * 5.02
        y = 1.58 + row * 1.53
        card(slide, x, y, 4.83, 1.14, WHITE, LIGHT)
        line(slide, x, y, 0.065, 1.14, RED)
        textbox(slide, x + 0.22, y + 0.12, 4.4, 0.28, title, size=11.4, color=INK,
                bold=True)
        textbox(slide, x + 0.22, y + 0.44, 4.42, 0.64, body, size=9.2, color=BODY,
                spacing=1.07)
    rect(slide, LEFT, 6.22, 9.85, 0.46, NAVY, None, 0)
    textbox(slide, LEFT + 0.16, 6.31, 9.55, 0.28,
            "Not claimed: production-ready · state-of-the-art · hallucination eliminated.",
            size=9.6, color=WHITE, bold=True)
    notes(slide, """
Speaker 5 (36 s):
We are explicit about the boundary: no blind test, provisional labels, one model, one
repeat, and no significance claim. The dominant error is over-abstention. The cost-guard
savings are replay estimates, not live savings, and cache and recovery were validated on
Mock traces. This is a research and teaching prototype: we do not claim production
readiness or state-of-the-art performance.
""")


# ---------------------------------------------------------------- slide 15
def slide_conclusion():
    slide = new_slide("What we learned", "DISCUSSION",
                      "Three design lessons, three concrete next steps")
    lessons = [
        ("01", "Coordinate around evidence gaps", "A fixed expert batch wastes queries; two targeted tasks per round recovered cases Fixed-4 could not."),
        ("02", "Make grounding deterministic", "Citations, identity and blockers belong in code — model confidence is not an acceptance signal."),
        ("03", "Measure abstention as a first-class outcome", "The main failure mode was over-abstention, not fabrication; it belongs in the headline metrics."),
    ]
    for i, (number, title, body) in enumerate(lessons):
        y = 1.60 + i * 1.30
        textbox(slide, LEFT, y, 0.55, 0.35, number, size=14, color=RED, bold=True, font=SERIF)
        textbox(slide, LEFT + 0.60, y - 0.02, 4.8, 0.30, title, size=12.6, color=INK,
                bold=True)
        textbox(slide, LEFT + 0.60, y + 0.32, 4.85, 0.90, body, size=9.9, color=BODY,
                spacing=1.08)
        if i < 2:
            line(slide, LEFT, y + 1.12, 5.35, 0.008, LIGHT)

    textbox(slide, 8.80, 1.58, 4.0, 0.3, "NEXT", size=9.5, color=RED, bold=True)
    bullets(slide, 8.80, 1.94, 4.12, 2.6, [
        "Blind holdout with independent human labels, then a significance-tested replication.",
        "Live evaluation of the evidence-gap cost guard and conservative abstention thresholds.",
        "A verifier triggered only on conflict, instead of an always-on feedback loop.",
    ], size=10.2, color=BODY, after=9)
    rect(slide, 8.80, 4.62, 4.12, 1.28, RED_SOFT, None, 0)
    textbox(slide, 8.98, 4.74, 3.8, 1.05,
            "IncidentLens turns agent investigation into an auditable evidence process — "
            "and reports what it cannot conclude.",
            size=11.2, color=RED_DARK, font=SERIF, italic=True, spacing=1.1)
    textbox(slide, LEFT, 5.88, 6.0, 0.42, "Thank you.", size=22, color=RED, bold=True,
            font=SERIF)
    textbox(slide, LEFT, 6.42, 9.8, 0.30,
            "Code, traces, evaluation scripts and the full limitations note are in the repository.",
            size=9.2, color=MUTED, italic=True)
    notes(slide, """
Speaker 6 (40 s):
To close, three lessons: coordination should follow evidence gaps; grounding must be
deterministic, because model confidence is not an acceptance signal; and abstention has to
be measured as a first-class outcome. Next steps: a blind holdout with independent labels,
a live test of the cost guard, and a verifier that runs only on conflict. IncidentLens makes
investigation auditable, and it reports what it cannot conclude. Thank you; we welcome
questions.
""")


# ---------------------------------------------------------------- backups
def slide_backup_decision():
    slide = new_slide("Backup · Decision semantics", "DISCUSSION",
                      "Every terminal path is typed and testable")
    rows = [
        ["Decision / terminal", "Required payload", "Meaning"],
        ["INVESTIGATE", "1–2 assignments; no selected hypothesis", "A concrete gap can still be closed"],
        ["FINALIZE", "One selected hypothesis; stop reason", "Evidence satisfies the cited-or-abstain gate"],
        ["ABSTAIN", "No selection; explicit stop reason", "Visible evidence cannot identify a cause"],
        ["INCONCLUSIVE", "Report with observations, gaps, next checks", "Normal abstention, not a runtime failure"],
        ["BUDGET_EXHAUSTED", "Failure stage + cost snapshot", "Runtime failure; retained in denominator"],
    ]
    table(slide, LEFT, 1.60, 9.9, rows, [2.2, 4.1, 3.6], font_size=9.5, header_size=9.5,
          row_h=0.55, align=[PP_ALIGN.LEFT] * 3)
    for i, (label, body) in enumerate([
        ("Stable hypothesis IDs", "IDs never change across rounds, so reviews and citations stay attached."),
        ("No silent closure", "A contradiction stays OPEN until new evidence resolves it."),
        ("Frozen termination", "Stop cancels in-flight work and freezes tools before reporting."),
    ]):
        x = LEFT + i * 3.32
        card(slide, x, 5.22, 3.12, 0.88, PALE, LIGHT)
        textbox(slide, x + 0.14, 5.31, 2.85, 0.26, label, size=9.2, color=INK, bold=True)
        textbox(slide, x + 0.14, 5.58, 2.82, 0.44, body, size=7.9, color=BODY, spacing=1.02)
    textbox(slide, LEFT, 6.38, 9.85, 0.34,
            "Stop reasons also include PLAN_READY, DIAGNOSIS_READY, PLAN_FAILED, NO_ALERT, "
            "UNRECOVERABLE_ERROR and STOP_TIMEOUT.",
            size=8.6, color=MUTED, italic=True)
    notes(slide, "Backup: use if asked how the coordinator can terminate.")


def slide_backup_metrics():
    slide = new_slide("Backup · Metrics and denominators", "EVALUATION",
                      "Each number on the results slides is defined here")
    rows = [
        ["Metric", "Numerator / denominator", "Why"],
        ["Technical completion", "completed runs / attempted runs", "Availability of the pipeline"],
        ["Root correct", "correct roots / identifiable completed runs", "Accuracy only where a cause exists"],
        ["Correct abstention", "abstentions / unidentifiable completed runs", "Calibration on missing evidence"],
        ["Quality success", "resolved-correct + correctly-abstained / 36", "One headline that retains failures"],
        ["Tokens / latency", "mean over completed runs", "Cost of the runs that finished"],
    ]
    table(slide, LEFT, 1.60, 9.9, rows, [2.2, 4.4, 3.3], font_size=9.5, header_size=9.5,
          row_h=0.55, align=[PP_ALIGN.LEFT] * 3)
    rect(slide, LEFT, 5.02, 9.9, 0.94, PALE, LIGHT)
    textbox(slide, LEFT + 0.16, 5.11, 1.7, 0.24, "WORKED EXAMPLE (DYNAMIC)", size=8.2,
            color=RED, bold=True)
    textbox(slide, LEFT + 0.16, 5.38, 9.55, 0.50,
            "33 completed = 27 root-correct + 6 correct abstentions; + 3 technical failures → 33/36 quality. "
            "Root correct is 27/27; abstention is 6/6.",
            size=9.2, color=BODY, spacing=1.06)
    textbox(slide, LEFT, 6.28, 9.85, 0.45,
            "A run that fails to produce a schema-valid result is not silently dropped.",
            size=8.8, color=MUTED, italic=True)
    notes(slide, "Backup: use if asked why 33/36 rather than 33/33.")


def slide_backup_paired():
    slide = new_slide("Backup · Paired outcomes and levers", "EVALUATION",
                      "Dynamic versus each control, case by case")
    table(slide, LEFT, 1.58, 5.0, [
        ["Comparison", "Wins", "Losses", "Ties"],
        ["Dynamic vs Single", "3", "2", "31"],
        ["Dynamic vs Fixed-4", "12", "1", "23"],
        ["Dynamic vs Dyn+Ver", "5", "2", "29"],
    ], [2.2, 0.9, 1.0, 0.9], font_size=9.8, header_size=9.5, row_h=0.5,
        align=[PP_ALIGN.LEFT] + [PP_ALIGN.CENTER] * 3)
    textbox(slide, LEFT, 3.90, 5.0, 0.6,
            "A win means Dynamic succeeds where the control fails; a loss is the reverse. "
            "Ties dominate because most cases are solvable by every architecture.",
            size=9.0, color=MUTED, spacing=1.1)
    card(slide, LEFT, 5.05, 5.0, 1.00, PALE, LIGHT)
    textbox(slide, LEFT + 0.15, 5.14, 4.7, 0.26, "THE 12 WINS VS FIXED-4", size=8.2, color=RED,
            bold=True)
    textbox(slide, LEFT + 0.15, 5.40, 4.68, 0.55,
            "Mostly identifiable cases where one fixed batch never revisited a missed source.",
            size=8.8, color=BODY, spacing=1.05)
    card(slide, 8.15, 5.05, 4.75, 1.00, PALE, LIGHT)
    textbox(slide, 8.30, 5.14, 4.4, 0.26, "WHY ONLY 3 WINS VS SINGLE", size=8.2, color=RED,
            bold=True)
    textbox(slide, 8.30, 5.40, 4.42, 0.55,
            "Single is already strong; Dynamic's larger advantage is cost, not raw quality.",
            size=8.8, color=BODY, spacing=1.05)
    table(slide, 8.15, 1.58, 4.75, [
        ["Lever", "Single", "Fixed-4", "Dynamic", "Dyn+Ver"],
        ["Competing", "6/7", "4/7", "7/7", "6/7"],
        ["Counterfactual", "5/6", "3/6", "6/6", "4/6"],
        ["Standard", "6/7", "3/7", "6/7", "6/7"],
        ["Boundary", "6/7", "4/7", "6/7", "5/7"],
        ["Missing", "7/7", "7/7", "6/7", "7/7"],
        ["Misleading", "2/2", "1/2", "2/2", "2/2"],
    ], [1.55, 0.8, 0.8, 0.8, 0.8], font_size=9.2, header_size=8.5, row_h=0.40,
        align=[PP_ALIGN.LEFT] + [PP_ALIGN.CENTER] * 4)
    notes(slide, "Backup: paired outcomes and per-lever detail.")


def slide_backup_failures():
    slide = new_slide("Backup · Failures and evidence", "EVALUATION",
                      "Eight technical failures, six of one kind")
    rows = [
        ["Failure", "Count", "Handling"],
        ["Truncated structured output", "6", "One targeted repair; if still invalid, technical failure"],
        ["Identity-mismatched finding", "2", "Merge rejects the finding; run fails or continues without it"],
        ["Wrong root cause", "0", "No accepted answer contradicted the evaluator label"],
        ["Total", "8 / 144", "All retained in attempted denominators"],
    ]
    table(slide, LEFT, 1.58, 9.9, rows, [3.0, 1.2, 5.7], font_size=9.8, header_size=9.5,
          row_h=0.52, align=[PP_ALIGN.LEFT] * 3)
    textbox(slide, LEFT, 4.55, 9.8, 1.5,
            "The 8 technical failures were spread across all four variants, so they do not "
            "explain the quality ordering. The corpus labels are evaluator-only and provisional; "
            "the public development packs share encoder lineage and are not independent blind Test data.\n\n"
            "The cost-guard figures on the limitations slide are replay estimates over frozen traces, "
            "not live savings; the default 4-round budget means the 5-round guard cannot fire in the stock configuration.",
            size=9.4, color=BODY, spacing=1.12)
    notes(slide, "Backup: use if asked about failures or label provenance.")


def slide_backup_security():
    slide = new_slide("Backup · Security and replay", "DESIGN",
                      "What the system can read, and what replay can open")
    left_items = [
        ("Role ACL", "Coordinator has no evidence tools; each specialist is limited to its source; verifier fetches only observed IDs."),
        ("Immutable context", "The agent context is frozen at issuance; a finding must match the identity that produced it."),
        ("Public allowlist", "Only incident.json, logs.jsonl, metrics.csv, changes.jsonl, configs.jsonl and database.jsonl are readable."),
        ("Path safety", "Symlinks, traversal and private/oracle paths are rejected before any read."),
    ]
    right_items = [
        ("Replay root", "Trace paths are confined to results/ and the filename must be trace.json."),
        ("Offline replay", "The orchestrator, tools and provider are not called; only saved state is read."),
        ("Download guard", "Downloaded artifacts are resolved inside the run directory and reject reparse points."),
        ("Secrets", "The repository contains .env.example only; no API key or endpoint is committed."),
    ]
    textbox(slide, LEFT, 1.58, 4.2, 0.3, "RUNTIME", size=9.5, color=RED, bold=True)
    textbox(slide, 7.75, 1.58, 4.4, 0.3, "REPLAY AND PACKAGING", size=9.5, color=RED, bold=True)
    for column, width, items in [(LEFT, 4.20, left_items), (7.75, 4.45, right_items)]:
        for i, (title, body) in enumerate(items):
            y = 1.95 + i * 1.17
            textbox(slide, column, y, width, 0.28, title, size=10.8, color=INK, bold=True)
            textbox(slide, column, y + 0.30, width, 0.78, body, size=9.2, color=BODY,
                    spacing=1.08)
            line(slide, column, y + 1.02, width - 0.20, 0.008, LIGHT)
    notes(slide, "Backup: use if asked about prompt injection, privacy or replay safety.")


def slide_backup_reproduce():
    slide = new_slide("Backup · Reproduce the demonstration", "SYSTEM",
                      "From a clean checkout to a saved trace")
    commands = [
        ("Install", "python -m venv .venv\n"
                    ".venv\\Scripts\\python.exe -m pip install -r requirements.lock\n"
                    ".venv\\Scripts\\python.exe -m pip install -e \".[dev]\""),
        ("Validate", ".venv\\Scripts\\python.exe -m incident_lens.cli validate-data"),
        ("Run", ".venv\\Scripts\\python.exe -m incident_lens.cli run --case incident_001\n"
                "        --provider mock --cache-mode off --out results/quickstart"),
        ("Replay", ".venv\\Scripts\\python.exe -m incident_lens.cli replay --trace results/quickstart/trace.json"),
        ("Web", ".venv\\Scripts\\python.exe -m incident_lens.cli web"),
    ]
    for i, (label, command) in enumerate(commands):
        y = 1.58 + i * 1.02
        textbox(slide, LEFT, y + 0.05, 1.05, 0.3, label, size=10.0, color=RED, bold=True)
        rect(slide, LEFT + 1.10, y, 8.75, 0.78, PALE, LIGHT)
        textbox(slide, LEFT + 1.22, y + 0.09, 8.5, 0.62, command, size=8.0, color=INK,
                font="Consolas", spacing=1.12)
    textbox(slide, LEFT, 6.78, 9.8, 0.25,
            "Mock is offline and deterministic. Real provider settings live in .env; the repository ships .env.example only.",
            size=8.4, color=MUTED, italic=True)
    notes(slide, "Backup: use for a live reproduction request.")


# ---------------------------------------------------------------- build
def main():
    slide_title()
    slide_problem()
    slide_question()
    slide_architecture()
    slide_agents()
    slide_coordination()
    slide_gates()
    slide_implementation()
    slide_demo()
    slide_evaluation_design()
    slide_quality()
    slide_cost()
    slide_failures()
    slide_limits()
    slide_conclusion()
    slide_backup_decision()
    slide_backup_metrics()
    slide_backup_paired()
    slide_backup_failures()
    slide_backup_security()
    slide_backup_reproduce()

    # cache generated charts that are not tied to a slide
    chart_quality()
    chart_levers()

    out = ROOT / "IncidentLens_Final.pptx"
    prs.save(out)
    print(f"Wrote {out} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
