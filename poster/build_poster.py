"""Build the PerceptionAI poster draft on the CS 4974 lab template (Poster - Copy.pptx).

Keeps the gradient header, both logos and the maroon section-bar style; replaces all
content. Every number that is not final is a yellow-highlighted [TBD ...] run.
"""
import copy
import sys
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt
from lxml import etree

SRC, OUT = sys.argv[1], sys.argv[2]
MAROON = RGBColor(0x86, 0x1F, 0x41)
ORANGE = RGBColor(0xE5, 0x75, 0x1F)
INK = RGBColor(0x1F, 0x1F, 0x1F)
MUTED = RGBColor(0x55, 0x55, 0x55)
TINT = RGBColor(0xF6, 0xEC, 0xEF)      # light maroon tint for panels
BUBBLE_IN = RGBColor(0xE9, 0xE9, 0xEB)
BUBBLE_OUT = RGBColor(0x2F, 0x7C, 0xF6)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BODY = 38

prs = Presentation(SRC)
slide = prs.slides[0]
by_name = {sh.name: sh for sh in slide.shapes}

# ------------------------------------------------------------------ keep / delete
KEEP = {"Rectangle 3", "TextBox 6", "Picture 37", "Picture 11", "Rectangle 10"}
bar_proto = copy.deepcopy(by_name["Rectangle 10"]._element)
for sh in list(slide.shapes):
    if sh.name not in KEEP:
        sh._element.getparent().remove(sh._element)
by_name["Rectangle 10"]._element.getparent().remove(by_name["Rectangle 10"]._element)


def highlight(run):
    rPr = run._r.get_or_add_rPr()
    hl = etree.SubElement(rPr, qn("a:highlight"))
    clr = etree.SubElement(hl, qn("a:srgbClr"))
    clr.set("val", "FFFF00")
    # a:highlight must come after fill/effects and before latin/ea/cs
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is not None:
            rPr.remove(el)
            rPr.append(el)


def add_runs(p, parts, size, color=INK, font=None):
    """parts: str or list of (text, style) where style has b/i/tbd/color."""
    if isinstance(parts, str):
        parts = [(parts, "")]
    for text, style in parts:
        r = p.add_run()
        r.text = text
        f = r.font
        f.size = Pt(size)
        f.bold = "b" in style
        f.italic = "i" in style
        f.color.rgb = WHITE if "w" in style else (MAROON if "m" in style else color)
        if font:
            f.name = font
        if "t" in style:
            highlight(r)


def bullet(p, size):
    pPr = p._p.get_or_add_pPr()
    indent = int(Inches(0.45))
    pPr.set("marL", str(indent))
    pPr.set("indent", str(-indent))
    bf = etree.SubElement(pPr, qn("a:buFont"))
    bf.set("typeface", "Arial")
    bc = etree.SubElement(pPr, qn("a:buChar"))
    bc.set("char", "•")


def text_box(name, x, y, w, h, paras, size=BODY, color=INK, space_after=10, anchor=MSO_ANCHOR.TOP,
             align=None, font=None, margin=0.1):
    """paras: list of (kind, parts) where kind is 'p' or 'b' (bullet)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, Inches(margin))
    first = True
    for kind, parts in paras:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        sz = size
        if kind.startswith("h"):  # sub-heading
            parts = [(parts, "bm")] if isinstance(parts, str) else parts
        if kind == "small":
            sz = int(size * 0.75)
        if kind == "b":
            bullet(p, sz)
        if align is not None:
            p.alignment = align
        p.space_after = Pt(space_after)
        add_runs(p, parts, sz, color, font)
    return tb


def bar(title, x, y, w, h=1.5):
    el = copy.deepcopy(bar_proto)
    slide.shapes._spTree.append(el)
    sh = slide.shapes[-1]
    sh.left, sh.top, sh.width, sh.height = Inches(x), Inches(y), Inches(w), Inches(h)
    sh.name = f"Bar - {title}"
    run = sh.text_frame.paragraphs[0].runs[0]
    run.text = title
    run.font.size = Pt(60 if len(title) <= 20 else 50)
    return sh


def box(name, shape, x, y, w, h, fill, text=None, size=28, color=WHITE, bold=True, line=None):
    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.name = name
    sh.shadow.inherit = False
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(2.5)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = 0.12
    tf = sh.text_frame
    tf.word_wrap = True
    for side in ("margin_left", "margin_right"):
        setattr(tf, side, Inches(0.15))
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    if text:
        lines = text if isinstance(text, list) else [text]
        for i, line_parts in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            if isinstance(line_parts, str):
                line_parts = [(line_parts, "b" if bold else "")]
            add_runs(p, line_parts, size, color)
    return sh


def arrow(name, x1, y1, x2, y2, color=MAROON):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.name = name
    c.line.color.rgb = color
    c.line.width = Pt(5)
    ln = c.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")
    return c


def table(name, x, y, w, rows, col_w, size=28, header_fill=MAROON, row_h=0.62, tbd_cols=()):
    nrows, ncols = len(rows), len(rows[0])
    gf = slide.shapes.add_table(nrows, ncols, Inches(x), Inches(y), Inches(w), Inches(row_h * nrows))
    gf.name = name
    tbl = gf.table
    # plain grid style, like the template's tables
    tbl._tbl.tblPr.find(qn("a:tableStyleId")).text = "{5940675A-B579-460E-94D1-54222C63F5DA}"
    tbl.first_row = True
    tbl.horz_banding = False
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        tbl.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            cell = tbl.cell(i, j)
            cell.margin_left = cell.margin_right = Inches(0.1)
            cell.margin_top = cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            parts = val if isinstance(val, list) else [(val, "")]
            if i == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = header_fill
                parts = [(t, s + "bw") for t, s in parts]
            elif i % 2 == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = TINT
            else:
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE
            add_runs(p, parts, size, INK)
    return gf


TBD = lambda s: (f"[{s}]", "t")

# ------------------------------------------------------------------ header
title_box = by_name["TextBox 6"]
tf = title_box.text_frame
paras = tf.paragraphs
title_p, author_p = paras[0], paras[1]
for p in paras[2:]:
    p._p.getparent().remove(p._p)


def set_para(p, parts, size, font):
    keep_pPr = p._p.find(qn("a:pPr"))
    for child in list(p._p):
        if child is not keep_pPr:
            p._p.remove(child)
    add_runs(p, parts, size, WHITE, font)


set_para(title_p, [("Did They Really Mean That? How AI Interpretations Shape Perceptions of Ambiguous Messages", "bw")],
         60, "Arial")
set_para(author_p, [("Ifzaal Ahamed Imdad, Vikas Chowdary Meka, Vishal Meka", "w")], 40, "Open Sans")
adv = tf.add_paragraph()
add_runs(adv, [("Advisor: Dr. Sehrish Basir Nizamani  ·  Department of Computer Science, Virginia Tech", "w")],
         40, WHITE, "Open Sans")

# status badge, right of the advisor line: Part 2 done, Part 1 (human survey) still running
box("Status badge", MSO_SHAPE.ROUNDED_RECTANGLE, 34.1, 3.66, 6.3, 0.82, WHITE,
    [[("ONGOING", "bm"), ("  ·  human survey next", "m")]], size=26, color=MAROON)
slide.shapes[-1].adjustments[0] = 0.5

# ------------------------------------------------------------------ layout grid
TOP = 5.65
A_X, A_W = 0.5, 11.2
B_X, B_W = 12.3, 23.4
C_X, C_W = 36.3, 11.2

# ============ Column A
bar("Background", A_X, TOP, A_W)
text_box("Background text", A_X, TOP + 1.6, A_W, 7.2, [
    ("p", [("People increasingly ask AI assistants what an ambiguous text message ", ""), ("really", "i"),
           (" meant.", "")]),
    ("p", [("The ", ""), ("wording of the question", "b"), (" may steer the answer: “Is Alex being "
           "passive-aggressive?” invites a different reading than “What did Alex mean?”", "")]),
    ("p", [("If AI answers then shape how people read the sender, a leading question could ", ""),
           ("change how someone sees a friend", "b"), (".", "")]),
])

# chat-bubble example (scenario 1, fictional)
cy = TOP + 7.9
text_box("Example label", A_X, cy, A_W, 0.7, [("p", [("Example scenario (fictional)", "bm")])], size=30)
text_box("Example context", A_X, cy + 0.75, A_W, 0.7,
         [("p", [("Alex and Jordan are classmates working on a group project.", "i")])], size=26, color=MUTED)
box("Bubble 1", MSO_SHAPE.ROUNDED_RECTANGLE, A_X + 0.2, cy + 1.6, 7.6, 1.0, BUBBLE_IN,
    [[("Alex: ", "b"), ("Did you finish your part of the project?", "")]], size=26, color=INK)
box("Bubble 2", MSO_SHAPE.ROUNDED_RECTANGLE, A_X + 3.4, cy + 2.8, 7.6, 1.0, BUBBLE_OUT,
    [[("Jordan: ", "bw"), ("I'll finish it tonight.", "w")]], size=26)
box("Bubble 3", MSO_SHAPE.ROUNDED_RECTANGLE, A_X + 0.2, cy + 4.0, 5.6, 1.0, BUBBLE_IN,
    [[("Alex: ", "b"), ("Sure, that's fine.", "")]], size=26, color=INK)
text_box("Example question", A_X, cy + 5.2, A_W, 1.4,
         [("p", [("Is Alex fine with it, or annoyed? We asked two AI models, three different ways.", "bi")])],
         size=28, color=MAROON)

bar("Research Questions", A_X, 20.6, A_W)
text_box("RQ text", A_X, 22.2, A_W, 3.4, [
    ("p", [("RQ1  ", "bm"), ("Does leading question wording change how AI models interpret ambiguous messages?", "")]),
    ("p", [("RQ2  ", "bm"), ("Can a third AI model code those answers as reliably as trained human coders?", "")]),
], size=34)

bar("Two-Part Project", A_X, 25.9, A_W)
text_box("Two part text", A_X, 27.5, A_W, 3.6, [
    ("p", [("Part 1  Human survey ", "bm"), ("(VT IRB #26-1078, exempt): a pilot picks 12 of the 20 conversations; "
           "the main survey then shows each with a confident, hedged or no AI interpretation.", "")]),
    ("p", [("Part 2  Model study ", "bm"), ("(this poster): how the wording of the question changes what the AI says.", "")]),
], size=28, space_after=6)

# Pilot box: aggregates from results/pilot_summary.csv (pilot_summary.py, Nov 20 export:
# 13 responses, 10 passed the attention check; all 20 scenarios met mean 3-5 and both readings >= 4).
PY = 31.3
box("Pilot panel", MSO_SHAPE.ROUNDED_RECTANGLE, A_X, PY, A_W, 4.3, TINT)
text_box("Pilot title", A_X + 0.2, PY + 0.15, A_W - 0.4, 0.7,
         [("p", [("Pilot so far: are the messages ambiguous?", "bm")])], size=28)
stats = [("10", "people", "13 responded; 3 failed the attention check"),
         ("3.9–5.0", "mean negative intent", "per message, on a 1–7 scale"),
         ("20 / 20", "messages ambiguous", "both readings rated reasonable (mean ≥ 4)")]
sw = (A_W - 0.4) / 3
for k, (big, label, note) in enumerate(stats):
    sx = A_X + 0.2 + k * sw
    text_box(f"Pilot stat {k + 1}", sx, PY + 0.9, sw, 2.6, [
        ("p", [(big, "bm")]),
        ("p", [(label, "b")]),
        ("small", [(note, "")]),
    ], size=26, space_after=2, align=PP_ALIGN.CENTER, margin=0.05)
    slide.shapes[-1].text_frame.paragraphs[0].runs[0].font.size = Pt(54)
text_box("Pilot note", A_X + 0.2, PY + 3.55, A_W - 0.4, 0.6,
         [("p", [("Pilot still collecting responses; numbers as of Nov 20.", "i")])], size=18, color=MUTED)

# ============ Column B: Methodology
bar("Methodology", B_X, TOP, B_W)
# pipeline
py = TOP + 1.85
bw, bh, gap = 3.35, 2.3, 0.66
labels = [
    ["20", ("fictional conversations", "")],
    ["× 3", ("question framings", "")],
    ["× 2 models", ("via VT ARC, 10 repeats", "")],
    ["1,200", ("AI answers", "")],
]
xs = []
for i, lab in enumerate(labels):
    x = B_X + 0.1 + i * (bw + gap)
    xs.append(x)
    fill = MAROON if i < 3 else ORANGE
    box(f"Step {i + 1}", MSO_SHAPE.ROUNDED_RECTANGLE, x, py, bw, bh, fill,
        [[(lab[0], "bw")], [(lab[1][0], "w")]], size=30)
    if i:
        arrow(f"Arrow {i}", x - gap + 0.05, py + bh / 2, x - 0.05, py + bh / 2)
# fan out to two coders
cx = xs[-1] + bw + gap
cw, ch = 3.6, 1.05
box("Human coders", MSO_SHAPE.ROUNDED_RECTANGLE, cx, py - 0.05, cw, ch, WHITE,
    [[("Human coders", "bm")], [("blind, rotating pairs", "")]], size=24, color=INK, line=MAROON)
box("Model coder", MSO_SHAPE.ROUNDED_RECTANGLE, cx, py + bh - ch + 0.05, cw, ch, WHITE,
    [[("Model coder", "bm")], [("GLM-5.3, blind", "")]], size=24, color=INK, line=MAROON)
arrow("Arrow to humans", xs[-1] + bw + 0.05, py + bh / 2, cx - 0.05, py + 0.45)
arrow("Arrow to model", xs[-1] + bw + 0.05, py + bh / 2, cx - 0.05, py + bh - 0.45)
ax = cx + cw + gap
box("Analysis", MSO_SHAPE.ROUNDED_RECTANGLE, ax, py, B_X + B_W - ax - 0.1, bh, ORANGE,
    [[("Analysis", "bw")], [("κ + rates by framing", "w")]], size=28)
arrow("Arrow analysis", cx + cw + 0.05, py + bh / 2, ax - 0.05, py + bh / 2)

my = py + bh + 0.55
text_box("Framings", B_X, my, 11.4, 7.5, [
    ("h", "The same conversation, three questions"),
    ("b", [("Neutral: ", "b"), ("“What did {sender} mean by the last message?”", "i")]),
    ("b", [("Negatively leading: ", "b"), ("“Is {sender} being passive-aggressive in the last message?”", "i")]),
    ("b", [("Positively leading: ", "b"), ("“Is {sender} being sincere in the last message?”", "i")]),
    ("small", [("Models: gpt-oss-120b and DeepSeek-V4.1-Flash, temperature 0.7, one fresh conversation per answer.", "")]),
], size=34, space_after=10)
text_box("Coding", B_X + 11.9, my, 11.5, 7.5, [
    ("h", "Each answer is coded on four fields"),
    ("b", [("Main reading: ", "b"), ("negative / neutral / positive", "")]),
    ("b", [("Mentions an alternative reading: ", "b"), ("yes / no", "")]),
    ("b", [("Certainty: ", "b"), ("confident / hedged", "")]),
    ("b", [("No clear preference: ", "b"), ("yes / no", "")]),
    ("small", [("Coders see only the conversation and the answer, never the model or the question. "
                "Agreement: Cohen’s κ. The model coder uses a frozen prompt, never tuned on human labels.", "")]),
], size=34, space_after=10)

# ============ Column B: Results
RY = 16.9
bar("Results", B_X, RY, B_W)
# main chart (poster/make_charts.py, from the model-coder labels)
slide.shapes.add_picture("chart_negative.png", Inches(B_X), Inches(RY + 1.75), Inches(13.6), Inches(9.0)).name = "Main chart"

text_box("Agreement title", B_X + 14.0, RY + 1.8, 9.4, 0.8,
         [("p", [("Can a model code like a person?", "bm")])], size=30)
table("Agreement table", B_X + 14.0, RY + 2.75, 9.4, [
    ["Field", "Human–human κ", "Model–human κ"],
    ["Main reading", "0.69", [("0.72", "b")]],
    ["Alternative", "0.52", [("0.59", "b")]],
    ["Certainty", "0.64", [("0.70", "b")]],
    ["No clear pref.", [("0.64", "b")], "0.53"],
], col_w=[3.1, 3.3, 3.0], size=28, row_h=0.9)
text_box("Agreement note", B_X + 14.0, RY + 7.4, 9.4, 3.4, [
    ("p", [("Human–human: 3 coder pairs, 25 answers each (n = 75). Model–human: the model coder against "
            "every human label on the same answers (n = 154).", "")]),
    ("p", [("The model coder matched people about as well as people matched each other, except on ", ""),
           ("no clear preference", "i"), (".", "")]),
], size=23, color=MUTED, space_after=8)

text_box("Table title", B_X, RY + 11.3, B_W, 0.8,
         [("p", [("All answers by model and question (model-coder labels, % of coded answers)", "bm")])], size=30)
TABLE = {  # results/judge_table.csv
    ("gpt-oss-120b", "Neutral"): (200, 26.5, 62.0, 11.5, 15.0, 2.5),
    ("gpt-oss-120b", "“Passive-aggressive?”"): (200, 47.5, 46.5, 6.0, 99.0, 89.5),
    ("gpt-oss-120b", "“Sincere?”"): (200, 60.0, 29.5, 10.5, 93.5, 79.0),
    ("DeepSeek-V4.1-Flash", "Neutral"): (199, 37.2, 55.8, 7.0, 42.7, 55.8),
    ("DeepSeek-V4.1-Flash", "“Passive-aggressive?”"): (197, 53.3, 45.7, 1.0, 96.4, 94.4),
    ("DeepSeek-V4.1-Flash", "“Sincere?”"): (198, 51.0, 49.0, 0.0, 93.9, 94.9),
}
r0 = lambda v: str(int(v + 0.5))
t_rows = [["Model", "Question", "n", "% negative", "% neutral", "% positive", "% mention other reading", "% hedged"]]
for (model, fr), (n, *vals) in TABLE.items():
    t_rows.append([model, fr, str(n)] + [r0(v) for v in vals])
table("Descriptive table", B_X, RY + 12.2, B_W, t_rows,
      col_w=[5.0, 4.6, 1.4, 2.3, 2.2, 2.3, 3.3, 2.3], size=26, row_h=0.72)
text_box("Table note", B_X, RY + 12.2 + 7 * 0.72 + 0.1, B_W, 0.6, [
    ("p", [("6 of 1,200 answers (all DeepSeek) could not be coded by the model coder and are left out.", "i")]),
], size=20, color=MUTED)

# ============ Column C
bar("Key Findings", C_X, TOP, C_W)
text_box("Findings", C_X, TOP + 1.6, C_W, 8.6, [
    ("p", [("1  Leading questions pushed the AI toward a negative reading. ", "bm"),
           ("gpt-oss: 27% negative with the neutral question, 48% with the passive-aggressive one, 60% with the "
            "sincere one. DeepSeek: 37%, 53%, 51%.", "")]),
    ("p", [("2  Asking “Is Alex sincere?” did not help. ", "bm"),
           ("It raised negative readings about as much as asking “Is Alex being passive-aggressive?”, "
            "and for gpt-oss even more.", "")]),
    ("p", [("3  A model can code these answers about as well as a person. ", "bm"),
           ("Main reading κ = 0.72 against humans, vs. 0.69 between humans.", "")]),
], size=30, space_after=16)

# ---- hedging (replaces the missing-data box; the 6 missing labels are a footnote under the table)
MY = 14.6
bar("Leading Questions Add Doubt", C_X, MY, C_W)
slide.shapes.add_picture("chart_hedged.png", Inches(C_X + 0.1), Inches(MY + 1.65), Inches(C_W - 0.2),
                         Inches((C_W - 0.2) * 7.0 / 11.0)).name = "Hedging chart"
text_box("Hedging note", C_X, MY + 8.4, C_W, 2.2, [
    ("p", [("A leading question also made the AI bring up the other reading in 94–99% of answers "
            "(15% and 43% with a neutral question).", "")]),
], size=27)

LY = 25.9
bar("Limitations & Next Steps", C_X, LY, C_W)
text_box("Limitations", C_X, LY + 1.6, C_W, 7.0, [
    ("b", "Fictional, English-only conversations; 2 models"),
    ("b", "Most conversations got the same reading in all 10 repeats, so a few of them carry each shift"),
    ("b", "Rates use the model coder’s labels, checked against people on 150 answers"),
    ("b", [("Next: ", "b"), ("pick 12 conversations from the pilot, then run the survey to see whether a "
                             "confident or hedged AI answer changes how people read the sender", "")]),
], size=27, space_after=8)
text_box("Acknowledgments", C_X, 34.4, C_W, 1.4, [
    ("p", [("Compute: Virginia Tech Advanced Research Computing (ARC) LLM API.", "")]),
], size=22, color=MUTED)

prs.save(OUT)
print("saved", OUT)
