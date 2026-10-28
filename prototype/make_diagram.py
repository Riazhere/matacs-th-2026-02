import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

COL = {"ai": ("#DCEBFF", "#2B6CB0"), "rule": ("#E3F5E6", "#2F855A"),
       "human": ("#FFE9CC", "#C05621"), "flag": ("#FDE2E2", "#C53030"), "log": ("#EEEEEE", "#555555")}

steps = [
 ("human", "1  Reviewer uploads PDFs and picks a category", "Human input. Nothing else is needed from the reviewer."),
 ("rule", "2  Load criteria for that category and lock the version", "Rules. Read mandatory checks, weights and scoring methods from the admin database (for example v3). Never hard-coded."),
 ("rule", "3  PDF to text", "Rules. Text extraction, OCR if scanned. An unreadable or empty file goes to the flagged queue."),
 ("rule", "4  Injection tripwire", "Rules. Pattern scan for text aimed at an AI or reviewer (rank me first, ignore the rules). Any hit is flagged, never obeyed."),
 ("ai", "5  AI EXTRACTION (the only AI step)", "Reads the text and returns the facts the criteria ask for, each with an exact quote and page. Temperature 0, pinned model and prompt version. It never sees weights, never scores, never ranks. Anything missing or vague comes back as not_stated or unclear, not guessed."),
 ("rule", "6  Validate the AI output", "Rules. Check JSON schema and types. Check each quote really exists in the document (catches made-up facts). An optional second run must agree, or the field becomes unclear."),
 ("human", "7  CHECKPOINT 1: reviewer checks extracted facts", "Human. Facts shown beside their quotes. The reviewer can correct a value. Every edit is logged with a reason."),
 ("rule", "8  Mandatory gate", "Rules. Ontario licence held by the bidder; WSIB plus 5M insurance. Result is pass, fail or unclear. Fail = ineligible. Unclear = flagged."),
 ("rule", "9  Score and rank", "Plain code. Weights and formulas from the locked criteria version. Price and timeline are scored against ranked bids only. Sum to 0-100, sort, fixed tie-break. Reason text is built from the scorecard."),
 ("human", "10  CHECKPOINT 2: reviewer screen", "Human. Ranked list with a scorecard for each proposal (value, quote, formula, points), plus the flagged queue and the ineligible list."),
 ("human", "11  CHECKPOINT 3: override and final decision", "Human. The reviewer may reorder, reinstate or clear a flagged proposal, each with a written reason. A person makes the award. The tool never awards."),
]
WRAP, GAP, X, W = 66, 0.40, 4.6, 7.4

def height(body, wrap=WRAP):
    return 0.66 + 0.25 * len(textwrap.wrap(body, wrap)) + 0.10

heights = [height(s[2]) for s in steps]
total = sum(heights) + GAP * (len(steps) - 1)
TOP = total + 3.0           # room for title above, audit bar below
fig, ax = plt.subplots(figsize=(14, TOP * 0.95))
ax.set_xlim(0, 14); ax.set_ylim(-0.3, TOP + 0.2); ax.axis("off")

def box(cx, cy, w, h, kind, title, body, wrap=WRAP, fs=9.5):
    fc, ec = COL[kind]
    ax.add_patch(FancyBboxPatch((cx - w/2, cy - h/2), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", fc=fc, ec=ec, lw=2))
    ax.text(cx, cy + h/2 - 0.17, title, ha="center", va="top", fontsize=11.5, fontweight="bold", color=ec)
    ax.text(cx, cy + h/2 - 0.60, "\n".join(textwrap.wrap(body, wrap)), ha="center", va="top", fontsize=fs, color="#222", linespacing=1.4)

def arrow(x1, y1, x2, y2, dashed=False, color="#444"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.8, ls="--" if dashed else "-"))

def line(xs, ys, color="#444"):
    ax.plot(xs, ys, color=color, lw=1.8)

# main column
y = TOP - 1.6
pos = []
for (kind, t, b), h in zip(steps, heights):
    cy = y - h/2
    box(X, cy, W, h, kind, t, b)
    pos.append((cy, h))
    y -= h + GAP
for i in range(len(steps) - 1):
    arrow(X, pos[i][0] - pos[i][1]/2, X, pos[i+1][0] + pos[i+1][1]/2)

# side boxes
SX, SW = 11.0, 4.2
fl_body = "Injection text found, unreadable file, missing or unclear fact, or two AI runs that disagree. Held for a human. Nothing is guessed to fill the gap."
in_body = "Failed a mandatory check. Shown with the reason. A human can reinstate it with a note."
fl_h, in_h = height(fl_body, 34), height(in_body, 34)
fl_y = (pos[4][0] + pos[5][0]) / 2
in_y = pos[7][0]
box(SX, fl_y, SW, fl_h, "flag", "FLAGGED QUEUE (not ranked)", fl_body, 34)
box(SX, in_y, SW, in_h, "flag", "INELIGIBLE LIST", in_body, 34)
R = "#C53030"
arrow(X + W/2, pos[3][0], SX - SW/2 + 0.8, fl_y + fl_h/2, dashed=True, color=R)      # step 4 -> flagged
arrow(X + W/2, pos[5][0], SX - SW/2, fl_y - fl_h/2 + 0.35, dashed=True, color=R)     # step 6 -> flagged
ax.text(SX, fl_y - fl_h/2 - 0.25, "also fed by steps 3 and 8 (unclear)", ha="center", fontsize=8.5, style="italic", color=R)
arrow(X + W/2, in_y, SX - SW/2, in_y, color=R)
ax.text(X + W/2 + 0.55, in_y + 0.15, "fail", fontsize=9.5, color=R, ha="center")
ax.text(X + 0.2, (pos[7][0] - pos[7][1]/2 + pos[8][0] + pos[8][1]/2) / 2, "pass", fontsize=9.5, color="#2F855A", va="center")
bus = 13.6
line([SX + SW/2, bus], [fl_y, fl_y], R)
line([SX + SW/2, bus], [in_y, in_y], R)
line([bus, bus], [fl_y, pos[9][0]], R)
arrow(bus, pos[9][0], X + W/2, pos[9][0], color=R)

# audit bar
ax.add_patch(FancyBboxPatch((0.5, 0.1), 13.0, 1.0, boxstyle="round,pad=0.02,rounding_size=0.12", fc=COL["log"][0], ec=COL["log"][1], lw=2))
ax.text(7.0, 0.98, "AUDIT LOG (written at every step)", ha="center", va="top", fontsize=11.5, fontweight="bold", color=COL["log"][1])
ax.text(7.0, 0.42, "File hash, criteria version, prompt version, model version, raw AI output, validated facts,\nevery human edit (before, after, who, why), scores, flags, final decision.", ha="center", va="center", fontsize=9.5, color="#222")
arrow(X, pos[-1][0] - pos[-1][1]/2, X, 1.12)

# title + legend
ax.text(0.5, TOP + 0.05, "AI proposal triage: upload to ranked output", fontsize=17, fontweight="bold", va="top")
ax.text(0.5, TOP - 0.45, "AI reads. Code decides. A human awards.", fontsize=11.5, style="italic", va="top", color="#444")
for i, (k, lab) in enumerate([("ai", "AI step"), ("rule", "Rule / code step"), ("human", "Human checkpoint"), ("flag", "Held or rejected")]):
    yy = TOP - 0.1 - i * 0.38
    ax.add_patch(FancyBboxPatch((9.6, yy - 0.13), 0.4, 0.26, boxstyle="round,pad=0.01", fc=COL[k][0], ec=COL[k][1], lw=1.5))
    ax.text(10.15, yy, lab, va="center", fontsize=9.5)

plt.savefig(__import__("pathlib").Path(__file__).parent.parent / "diagram" / "process-flow.png", dpi=130, bbox_inches="tight", facecolor="white")
print("saved")
