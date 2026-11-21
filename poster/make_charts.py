"""Poster charts from the model-coder labels (run after `py study0.py judge-report`).

Usage (from the repo root):  py poster/make_charts.py
Writes poster/chart_negative.png and poster/chart_hedged.png at the size they are placed
on the poster, so font sizes are true poster points. Descriptive only (decisions.md §6).
"""
import collections
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "runs" / "judge" / "ea34f421e7a9" / "judge_labels.csv"
OUT = ROOT / "poster"

MODELS = [("gpt-oss-120b", "gpt-oss-120b"), ("DeepSeek-V4.1-Flash", "DeepSeek-V4.1-Flash")]
FRAMINGS = [("neutral", "Neutral"), ("negatively_leading", "“Passive-\naggressive?”"),
            ("positively_leading", "“Sincere?”")]
COLORS = {"neutral": "#8C8C8C", "negatively_leading": "#861F41", "positively_leading": "#E5751F"}
INK, MUTED, GRID = "#1F1F1F", "#555555", "#E4E0E1"

plt.rcParams.update({"font.family": "Calibri", "font.size": 32, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": MUTED})

rows = [r for r in csv.DictReader(open(LABELS, encoding="utf-8-sig")) if r["main_reading"]]
cell = collections.defaultdict(list)
scen = collections.defaultdict(list)
for r in rows:
    cell[(r["model"], r["framing"])].append(r)
    scen[(r["model"], r["framing"], int(r["scenario"]))].append(r["main_reading"] == "negative")


def half_up(v):
    return int(v + 0.5)


def pct(rs, field, value):
    return 100 * sum(r[field] == value for r in rs) / len(rs)


def style(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_ylim(0, 108)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.yaxis.grid(True, color=GRID, linewidth=1.2)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0, pad=10)


# ---- Chart 1: negative-reading rate by framing, one panel per model, dots = 20 conversations
fig, axes = plt.subplots(1, 2, figsize=(13.6, 9.0), sharey=True)
for ax, (model, title) in zip(axes, MODELS):
    for i, (fr, lab) in enumerate(FRAMINGS):
        rs = cell[(model, fr)]
        v = pct(rs, "main_reading", "negative")
        bx = i - 0.2
        ax.bar(bx, v, width=0.42, color=COLORS[fr], edgecolor="white", linewidth=2, zorder=2)
        ax.text(bx, v + 2.5, f"{half_up(v)}%", ha="center", va="bottom", fontsize=36, fontweight="bold",
                color=INK, zorder=4)
        # one dot per conversation, in a strip to the right of the bar; ties spread sideways
        dots = sorted(100 * sum(x) / len(x) for (m, f, s), x in scen.items() if m == model and f == fr)
        seen = collections.Counter()
        for d in dots:
            k = seen[d]
            seen[d] += 1
            ax.scatter(i + 0.1 + (k % 5) * 0.05, d + (k // 5) * 2.6, s=60, color="white", edgecolor=INK,
                       linewidth=1.3, zorder=3, clip_on=False)
        ax.text(i, -4, lab, ha="center", va="top", fontsize=26, color=INK, linespacing=0.95)
        ax.text(i, -19, f"n = {len(rs)}", ha="center", va="top", fontsize=22, color=MUTED)
    ax.set_xticks([])
    ax.set_xlim(-0.55, 2.55)
    ax.set_title(title, fontsize=39, fontweight="bold", color=INK, pad=14)
    style(ax)
axes[0].set_ylabel("Answers reading the sender as negative", fontsize=27)
fig.tight_layout(rect=(0, 0.075, 1, 1))
fig.text(0.5, 0.012, "Bars: all answers.  Dots: each of the 20 conversations (about 10 answers each).",
         ha="center", fontsize=26, color=MUTED)
fig.savefig(OUT / "chart_negative.png", dpi=400)
plt.close(fig)

# ---- Chart 2: % hedged by framing, grouped by model
fig, ax = plt.subplots(figsize=(11.0, 7.0))
w = 0.26
for g, (model, title) in enumerate(MODELS):
    for i, (fr, lab) in enumerate(FRAMINGS):
        v = pct(cell[(model, fr)], "certainty", "hedged")
        x = g + (i - 1) * (w + 0.02)
        ax.bar(x, v, width=w, color=COLORS[fr], edgecolor="white", linewidth=2, zorder=2,
               label=lab.replace("\n", "") if g == 0 else None)
        ax.text(x, v + 2, f"{half_up(v)}%", ha="center", va="bottom", fontsize=30, fontweight="bold", color=INK)
ax.set_xticks([0, 1])
ax.set_xticklabels([t for _, t in MODELS], fontsize=30, fontweight="bold")
style(ax)
ax.set_ylabel("Answers that hedge", fontsize=28)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, frameon=False, fontsize=26,
          handlelength=1.2, columnspacing=1.4)
fig.tight_layout()
fig.savefig(OUT / "chart_hedged.png", dpi=400)
plt.close(fig)
print("wrote poster/chart_negative.png and poster/chart_hedged.png")
