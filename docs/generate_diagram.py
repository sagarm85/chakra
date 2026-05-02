#!/usr/bin/env python3
"""
Generate Chakra SDLC / CI-CD infinity-loop diagram.
Output: docs/chakra_cicd.png
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

# ── Canvas ────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(11, 6.5), facecolor="white")
ax = fig.add_subplot(111)
ax.set_aspect("equal")
ax.set_xlim(-5.4, 5.4)
ax.set_ylim(-2.8, 3.2)
ax.axis("off")

# ── Ring geometry ─────────────────────────────────────────────────────────────
R_OUT = 2.10
R_IN  = 1.22
LX, LY = -1.75, 0.0   # left  circle centre  (crossing at ≈±33.6°)
RX, RY =  1.75, 0.0   # right circle centre

# ── Palette ───────────────────────────────────────────────────────────────────
GREEN  = "#7CBF3F"
TEAL   = "#27AAE1"
ORANGE = "#F7941D"
PURPLE = "#9B59B6"
LBLUE  = "#3498DB"


# ── Drawing helpers ───────────────────────────────────────────────────────────

def ring_seg(cx, cy, a1, a2, color, zorder=3):
    """Filled ring arc from a1→a2 (degrees CCW from east). Handles wrap-around."""
    if a2 <= a1:
        a2 += 360
    fwd = np.linspace(np.radians(a1), np.radians(a2), 500)
    xs = np.concatenate([cx + R_OUT * np.cos(fwd),
                         cx + R_IN  * np.cos(fwd[::-1])])
    ys = np.concatenate([cy + R_OUT * np.sin(fwd),
                         cy + R_IN  * np.sin(fwd[::-1])])
    ax.add_patch(mpatches.Polygon(
        np.c_[xs, ys], closed=True,
        fc=color, ec="white", lw=3.0, zorder=zorder,
    ))


def arc_label(cx, cy, angle, text, fontsize=9.5, zorder=20):
    """White bold label at mid-ring, tangent-rotated for readability."""
    r_mid = (R_OUT + R_IN) / 2
    x = cx + r_mid * np.cos(np.radians(angle % 360))
    y = cy + r_mid * np.sin(np.radians(angle % 360))
    rot = (angle + 90) % 360
    if 90 < rot <= 270:
        rot -= 180
    ax.text(x, y, text,
            ha="center", va="center",
            fontsize=fontsize, fontweight="bold", color="white",
            rotation=rot, rotation_mode="anchor", zorder=zorder)


# ── LEFT circle — AI / SDLC (Claude-driven) ──────────────────────────────────
#
#  Four equal 90° segments, CCW from top-left:
#   PLAN    :  45° → 135°   green   — story → tasks
#   CODE    : 135° → 225°   teal    — per-task code generation
#   TEST    : 225° → 315°   orange  — pytest, ≥95% coverage
#   APPROVE : 315° → 405°   orange  — bridge: Sheets approval → PR opened
#
#  z-order 4 on APPROVE so it sits above the right circle's RELEASE bridge,
#  but below the right circle's REVIEW (z=5) at the top crossing.
#
ring_seg(LX, LY,  45,  135, GREEN,  zorder=3)   # PLAN
ring_seg(LX, LY, 135,  225, TEAL,   zorder=3)   # CODE
ring_seg(LX, LY, 225,  315, ORANGE, zorder=3)   # TEST
ring_seg(LX, LY, 315,  405, ORANGE, zorder=4)   # APPROVE bridge

#  Labels: wide segments get mid-arc label; narrow bridge uses offset angle
arc_label(LX, LY,  90,  "PLAN",    fontsize=10)   # mid 45→135
arc_label(LX, LY, 180,  "CODE",    fontsize=10)   # mid 135→225
arc_label(LX, LY, 270,  "TEST",    fontsize=10)   # mid 225→315
arc_label(LX, LY,  22,  "APPROVE", fontsize=8.5)  # upper portion of bridge


# ── RIGHT circle — GitHub / CI-CD ─────────────────────────────────────────────
#
#  Four equal 90° segments:
#   RELEASE :  135° → 225°  orange  — bridge: PR opened (connects to left)
#   TRACK   :  225° → 315°  lblue   — Google Sheets status updated
#   CI/CD   :  315° → 405°  purple  — GitHub Actions triggered on merge
#   REVIEW  :   45° → 135°  teal    — PR ready for human review
#
#  REVIEW at z=5 renders on top of APPROVE at the top crossing → right-over-left.
#  RELEASE at z=3 stays under APPROVE at the bottom crossing → left-over-right.
#
ring_seg(RX, RY, 135,  225, ORANGE, zorder=3)   # RELEASE bridge
ring_seg(RX, RY, 225,  315, LBLUE,  zorder=3)   # TRACK
ring_seg(RX, RY, 315,  405, PURPLE, zorder=3)   # CI/CD
ring_seg(RX, RY,  45,  135, TEAL,   zorder=5)   # REVIEW  (on top)

arc_label(RX, RY,  90,   "REVIEW",  fontsize=10)   # mid 45→135
arc_label(RX, RY, 270,   "TRACK",   fontsize=10)   # mid 225→315
arc_label(RX, RY,   0,   "CI/CD",   fontsize=10)   # mid 315→45
arc_label(RX, RY, 202,   "RELEASE", fontsize=8.5)  # lower portion of bridge


# ── White centre holes ────────────────────────────────────────────────────────
for cx, cy in [(LX, LY), (RX, RY)]:
    ax.add_patch(plt.Circle(
        (cx, cy), R_IN - 0.05,
        fc="white", ec="none", zorder=10,
    ))


# ── Centre labels ─────────────────────────────────────────────────────────────
kw = dict(ha="center", va="center", zorder=11)
ax.text(LX, LY + 0.23, "AI",   fontsize=28, fontweight="bold", color="#3A3A3A", **kw)
ax.text(LX, LY - 0.30, "SDLC", fontsize=13, color="#888888",   **kw)
ax.text(RX, RY + 0.23, "CI",   fontsize=28, fontweight="bold", color="#3A3A3A", **kw)
ax.text(RX, RY - 0.30, "CD",   fontsize=13, color="#888888",   **kw)


# ── Title ─────────────────────────────────────────────────────────────────────
ax.text(0, 2.72,
        "Chakra — Agentic SDLC Loop",
        ha="center", va="center",
        fontsize=16, fontweight="bold", color="#2C2C2C",
        zorder=20)


# ── Save ──────────────────────────────────────────────────────────────────────
out = Path(__file__).parent / "chakra_cicd.png"
plt.tight_layout(pad=0)
plt.savefig(out, dpi=160, bbox_inches="tight",
            facecolor="white", edgecolor="none")
print(f"✓  Written: {out}")
