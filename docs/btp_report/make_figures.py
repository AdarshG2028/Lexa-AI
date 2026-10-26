"""Generate the original diagrams used in the B.Tech report.

Every figure is drawn from primitives so that it can be regenerated and edited
without depending on a proprietary diagram editor.  Run with:

    uv run --with matplotlib python make_figures.py
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 10,
        "axes.linewidth": 0,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    }
)

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

NAVY = "#1F3864"
BLUE = "#2F5597"
MID_BLUE = "#DCE8F7"
LIGHT_BLUE = "#EEF4FB"
TEAL = "#0F6B6B"
LIGHT_TEAL = "#E2F2F1"
AMBER = "#8A5A00"
LIGHT_AMBER = "#FFF2CC"
GREY = "#595959"
LIGHT_GREY = "#F2F2F2"
RED = "#9C0006"
LIGHT_RED = "#FCE4E4"
GREEN = "#375623"
LIGHT_GREEN = "#E2EFDA"


def canvas(width: float, height: float):
    fig, ax = plt.subplots(figsize=(width, height))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    return fig, ax


def box(
    ax,
    x,
    y,
    w,
    h,
    text,
    fc=LIGHT_BLUE,
    ec=BLUE,
    fs=10,
    bold=False,
    lw=1.2,
    align="center",
    radius=0.08,
    text_color="#111111",
):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.015,rounding_size={radius}",
        linewidth=lw,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(patch)
    ha = {"center": "center", "left": "left"}[align]
    tx = x + w / 2 if align == "center" else x + 0.12
    ax.text(
        tx,
        y + h / 2,
        text,
        ha=ha,
        va="center",
        fontsize=fs,
        fontweight="bold" if bold else "normal",
        color=text_color,
        linespacing=1.18,
    )
    return patch


def layer(ax, x, y, w, h, label, fc="#F7F9FC", ec="#B4C6E7"):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.01,rounding_size=0.12",
            linewidth=1.0,
            edgecolor=ec,
            facecolor=fc,
            linestyle=(0, (4, 3)),
        )
    )
    ax.text(x + 0.18, y + h - 0.18, label, ha="left", va="top", fontsize=8.5, color=GREY, style="italic")


def arrow(
    ax,
    start,
    end,
    color=BLUE,
    lw=1.4,
    style="-|>",
    ls="-",
    rad=0.0,
    text=None,
    tx=None,
    ty=None,
    fs=8.5,
    text_color=GREY,
    ha="center",
    va="center",
    zorder=4,
):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle=style,
            mutation_scale=13,
            linewidth=lw,
            color=color,
            linestyle=ls,
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=1.5,
            shrinkB=1.5,
            zorder=zorder,
        )
    )
    if text:
        if tx is None:
            tx = (start[0] + end[0]) / 2
        if ty is None:
            ty = (start[1] + end[1]) / 2 + 0.12
        ax.text(tx, ty, text, ha=ha, va=va, fontsize=fs, color=text_color, zorder=zorder + 1,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))


def diamond(ax, cx, cy, w, h, text, fc=LIGHT_AMBER, ec=AMBER, fs=9):
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=fc, edgecolor=ec, linewidth=1.2))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color="#111111", linespacing=1.1)


def terminator(ax, cx, cy, w, h, text, fc=LIGHT_GREEN, ec=GREEN):
    ax.add_patch(
        FancyBboxPatch(
            (cx - w / 2, cy - h / 2),
            w,
            h,
            boxstyle=f"round,pad=0.01,rounding_size={h/2}",
            linewidth=1.2,
            edgecolor=ec,
            facecolor=fc,
        )
    )
    ax.text(cx, cy, text, ha="center", va="center", fontsize=9.5, color="#111111")


def entity(ax, x, y, w, h, name, rows, fc=LIGHT_BLUE, ec=BLUE):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.015,rounding_size=0.06",
            linewidth=1.1,
            edgecolor=ec,
            facecolor="white",
        )
    )
    ax.add_patch(Rectangle((x, y + h - 0.32), w, 0.32, facecolor=fc, edgecolor=ec, linewidth=1.1))
    ax.text(x + 0.1, y + h - 0.16, name, ha="left", va="center", fontsize=8.6, fontweight="bold", color=NAVY)
    for i, row in enumerate(rows):
        ax.text(x + 0.12, y + h - 0.48 - i * 0.205, row, ha="left", va="center", fontsize=7.4, color="#222222")


# ---------------------------------------------------------------------------
# Figure 1 - overall architecture
# ---------------------------------------------------------------------------
def figure_architecture():
    fig, ax = canvas(12, 8.4)
    layer(ax, 0.35, 6.55, 11.3, 1.45, "CLIENT (browser)")
    layer(ax, 0.35, 4.95, 11.3, 1.25, "API LAYER (FastAPI)")
    layer(ax, 0.35, 2.95, 11.3, 1.65, "DOMAIN SERVICES")
    layer(ax, 0.35, 1.05, 5.55, 1.45, "PERSISTENCE", fc="#FAFAFA")
    layer(ax, 6.1, 1.05, 5.55, 1.45, "PROVIDER ADAPTERS", fc="#FAFAFA")

    box(ax, 0.65, 6.85, 3.15, 0.85, "React 19 + TanStack Router\nbrowser interface", fs=9.4)
    box(ax, 4.05, 6.85, 3.15, 0.85, "MediaRecorder + Silero VAD\nautomatic turn taking", fs=9.4)
    box(ax, 7.45, 6.85, 3.85, 0.85, "HTTPS / JSON / multipart\nno audio leaves the page unencrypted", fs=9.0, fc=LIGHT_GREY, ec=GREY)

    box(ax, 0.65, 5.2, 2.55, 0.72, "Session & turn\n/api/v1/sessions", fs=8.8)
    box(ax, 3.35, 5.2, 2.75, 0.72, "Analyses\n/analysis/{kind}", fs=8.8)
    box(ax, 6.25, 5.2, 2.15, 0.72, "Video\n/api/v1/videos", fs=8.8)
    box(ax, 8.55, 5.2, 2.75, 0.72, "Health, limits, CORS\nrate limiting", fs=8.4, fc=LIGHT_GREY, ec=GREY)

    # services, two rows
    box(ax, 0.65, 3.72, 1.85, 0.62, "Conversation\nservice", fs=8.5)
    box(ax, 2.65, 3.72, 1.85, 0.62, "Video\nservice", fs=8.5)
    box(ax, 4.65, 3.72, 1.80, 0.62, "Grammar\nservice", fs=8.5)
    box(ax, 6.60, 3.72, 1.80, 0.62, "Vocabulary\nservice", fs=8.5)
    box(ax, 8.55, 3.72, 1.80, 0.62, "Fluency\nservice", fs=8.5)
    box(ax, 2.55, 3.08, 2.05, 0.52, "Pronunciation\nservice", fs=8.3)
    box(ax, 4.75, 3.08, 2.05, 0.52, "Alternatives\nservice", fs=8.3)
    box(ax, 6.95, 3.08, 2.05, 0.52, "Audio processing\nFFmpeg normalise", fs=8.0, fc=LIGHT_AMBER, ec=AMBER)

    box(ax, 0.65, 1.35, 2.45, 0.85, "SQLAlchemy 2\nSQLite / Postgres", fs=8.6)
    box(ax, 3.25, 1.35, 2.35, 0.85, "Audio storage\nnormalised WAV", fs=8.6)

    box(ax, 6.40, 1.35, 1.60, 0.85, "Groq\nWhisper, LLM,\nTTS", fs=7.8)
    box(ax, 8.10, 1.35, 1.45, 0.85, "Sarvam\nsaaras:v4", fs=7.8)
    box(ax, 9.65, 1.35, 1.75, 0.85, "Deepgram TTS\nfallback", fs=7.8)
    box(ax, 11.45, 1.35, 0.0, 0.0, "", fc="white", ec="white")

    # arrows
    arrow(ax, (7.5, 6.55), (7.5, 6.20), text="audio, mode, language", tx=8.95, ty=6.38, fs=8.0)
    arrow(ax, (4.3, 6.20), (4.3, 6.55), color=TEAL, text="transcript, reply audio", tx=3.0, ty=6.37, fs=8.0)
    arrow(ax, (5.8, 6.20), (5.8, 4.95), text="", color=BLUE)
    arrow(ax, (5.8, 4.95), (5.8, 4.60), text="", color=BLUE)
    arrow(ax, (4.0, 4.60), (4.0, 4.35), color=BLUE)
    arrow(ax, (5.0, 4.60), (5.0, 4.35), color=BLUE)
    arrow(ax, (6.7, 4.60), (6.7, 4.35), color=BLUE)
    arrow(ax, (2.6, 4.60), (2.6, 4.35), color=BLUE)
    arrow(ax, (9.2, 4.60), (9.2, 4.35), color=BLUE)
    arrow(ax, (2.0, 3.08), (2.0, 2.20), text="read / write", tx=0.95, ty=2.60, fs=7.6)
    arrow(ax, (4.6, 3.08), (4.6, 2.20), text="", color=BLUE)
    arrow(ax, (7.0, 3.08), (7.0, 2.20), text="requests", tx=7.9, ty=2.62, fs=7.6)
    arrow(ax, (8.8, 3.08), (8.8, 2.20), text="", color=BLUE)
    arrow(ax, (3.9, 3.08), (3.9, 2.20), text="", color=BLUE)
    arrow(ax, (10.3, 3.08), (10.3, 2.20), text="", color=BLUE)

    # legend note
    ax.text(0.45, 0.55, "Solid arrows: synchronous request path.  Dashed layer boundaries are logical, not process boundaries.",
            fontsize=8.0, color=GREY, ha="left")
    ax.text(0.45, 0.25, "The conversation service depends on interfaces, not vendor SDKs; the registry chooses an adapter at start-up.",
            fontsize=8.0, color=GREY, ha="left")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / "fig01_architecture.png", dpi=220, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2 - one conversation turn as a sequence diagram
# ---------------------------------------------------------------------------
def figure_sequence():
    fig, ax = canvas(13, 8.8)
    actors = [
        ("Learner /\nbrowser", 1.15, MID_BLUE),
        ("FastAPI\nservice", 3.55, MID_BLUE),
        ("Speech-to-text\nadapter", 5.95, LIGHT_TEAL),
        ("LLM\nadapter", 8.10, LIGHT_TEAL),
        ("Text-to-speech\nadapter", 10.25, LIGHT_TEAL),
        ("Session +\naudio store", 12.15, LIGHT_GREY),
    ]
    top = 8.05
    bottom = 0.65
    for label, x, color in actors:
        box(ax, x - 0.95, top, 1.9, 0.58, label, fc=color, ec=BLUE if color != LIGHT_GREY else GREY, fs=8.4)
        ax.plot([x, x], [top - 0.03, bottom], color="#7F7F7F", lw=0.8, ls=(0, (3, 3)), zorder=1)

    msgs = [
        (7.55, 1.15, 3.55, "1  POST /api/v1/sessions", BLUE),
        (7.20, 3.55, 1.15, "2  session id, mode, status", TEAL),
        (6.78, 1.15, 3.55, "3  POST /turns (audio multipart)", BLUE),
        (6.36, 3.55, 5.95, "4  validate + normalise", BLUE),
        (5.96, 5.95, 3.55, "5  transcript + word timings", TEAL),
        (5.55, 3.55, 12.15, "6  load trimmed history", BLUE),
        (5.15, 12.15, 3.55, "7  recent messages", TEAL),
        (4.74, 3.55, 8.10, "8  system + history + user turn", BLUE),
        (4.34, 8.10, 3.55, "9  reply text", TEAL),
        (3.93, 3.55, 10.25, "10  synthesise reply", BLUE),
        (3.53, 10.25, 3.55, "11  reply audio", TEAL),
        (3.12, 3.55, 12.15, "12  persist turn, audio, timings", BLUE),
        (2.72, 12.15, 3.55, "13  committed", TEAL),
        (2.31, 3.55, 1.15, "14  transcript, reply text, audio URL, timings", TEAL),
    ]
    for y, x1, x2, label, color in msgs:
        arrow(ax, (x1, y), (x2, y), color=color, lw=1.35, fs=8.2, text=label,
              tx=(x1 + x2) / 2, ty=y + 0.09)

    # browser playback and VAD note
    ax.add_patch(FancyBboxPatch((0.55, 1.15), 2.3, 0.62, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc=LIGHT_AMBER, ec=AMBER, lw=1.0))
    ax.text(1.7, 1.46, "15  play audio; VAD re-arms\nfor the next turn", ha="center", va="center", fontsize=8.0)
    arrow(ax, (2.85, 1.46), (3.35, 1.46), color=AMBER, style="-|>", lw=1.1)

    ax.text(0.55, 0.28, "The model sees only a bounded history window; the full transcript remains stored for later analysis.",
            fontsize=8.0, color=GREY, ha="left")
    ax.text(0.55, 0.02, "STT, LLM and TTS are replaceable adapters.  The API does not import a vendor SDK directly.",
            fontsize=8.0, color=GREY, ha="left")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / "fig02_sequence.png", dpi=220, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 3 - pronunciation pipeline
# ---------------------------------------------------------------------------
def figure_pronunciation():
    fig, ax = canvas(14, 7.8)
    # lanes
    ax.add_patch(FancyBboxPatch((0.4, 5.25), 13.2, 1.95, boxstyle="round,pad=0.02,rounding_size=0.10",
                                fc="#F8FBFF", ec="#B4C6E7", ls=(0, (4, 3))))
    ax.text(0.6, 7.02, "ACOUSTIC PATH", fontsize=8.2, color=GREY, style="italic")
    ax.add_patch(FancyBboxPatch((0.4, 3.05), 13.2, 1.95, boxstyle="round,pad=0.02,rounding_size=0.10",
                                fc="#F8FCFB", ec="#B7DEDB", ls=(0, (4, 3))))
    ax.text(0.6, 4.82, "REFERENCE PATH", fontsize=8.2, color=GREY, style="italic")

    box(ax, 0.7, 5.55, 2.0, 0.78, "Normalised\n16 kHz WAV", fs=8.8)
    box(ax, 3.05, 5.55, 2.45, 0.78, "wav2vec2 CTC\nphoneme model", fs=8.8, fc=LIGHT_TEAL, ec=TEAL)
    box(ax, 5.85, 5.55, 2.25, 0.78, "IPA posterior\n+ confidence", fs=8.8, fc=LIGHT_TEAL, ec=TEAL)
    box(ax, 8.45, 5.55, 2.15, 0.78, "Per-word\nphoneme path", fs=8.8)
    box(ax, 10.95, 5.55, 2.25, 0.78, "Observed\nsequence", fs=8.8)

    box(ax, 0.7, 3.35, 2.0, 0.78, "Stored\ntranscript", fs=8.8)
    box(ax, 3.05, 3.35, 1.75, 0.78, "g2p_en\nG2P", fs=8.8, fc=LIGHT_AMBER, ec=AMBER)
    box(ax, 5.15, 3.35, 1.75, 0.78, "ARPAbet\nlabels", fs=8.8, fc=LIGHT_AMBER, ec=AMBER)
    box(ax, 7.25, 3.35, 1.55, 0.78, "IPA\nmapping", fs=8.8, fc=LIGHT_AMBER, ec=AMBER)
    box(ax, 9.15, 3.35, 2.05, 0.78, "Expected\nsequence", fs=8.8)
    box(ax, 11.55, 3.35, 1.65, 0.78, "Dictionary\nstress", fs=8.4, fc=LIGHT_GREY, ec=GREY)

    arrow(ax, (2.7, 5.94), (3.05, 5.94))
    arrow(ax, (5.5, 5.94), (5.85, 5.94))
    arrow(ax, (8.1, 5.94), (8.45, 5.94))
    arrow(ax, (10.6, 5.94), (10.95, 5.94))
    arrow(ax, (2.7, 3.74), (3.05, 3.74))
    arrow(ax, (4.8, 3.74), (5.15, 3.74))
    arrow(ax, (6.9, 3.74), (7.25, 3.74))
    arrow(ax, (8.8, 3.74), (9.15, 3.74))
    arrow(ax, (11.2, 3.74), (11.55, 3.74))

    # merge
    box(ax, 2.25, 2.15, 3.15, 0.68, "Global alignment\nNeedleman–Wunsch", fs=8.8, fc=MID_BLUE, ec=NAVY)
    arrow(ax, (12.05, 5.55), (4.2, 2.83), text="", color=TEAL, rad=-0.12)
    arrow(ax, (12.2, 3.35), (4.2, 2.83), text="", color=AMBER, rad=0.12)

    box(ax, 5.75, 2.15, 2.15, 0.68, "Candidate\nsubstitutions", fs=8.8)
    arrow(ax, (5.4, 2.49), (5.75, 2.49))

    # filters
    ax.add_patch(FancyBboxPatch((8.15, 1.55), 5.35, 1.28, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=LIGHT_RED, ec=RED, lw=1.0))
    ax.text(8.30, 2.66, "EVIDENCE FILTERS", fontsize=8.2, color=RED, fontweight="bold")
    ax.text(8.30, 2.34, "1  notation folding (ʌ/ɐ, ɚ/ɜː, vowel length)\n"
                          "2  reduced vowels in function words are not judged\n"
                          "3  recurrence ≥ 3 and mean confidence ≥ 0.55\n"
                          "4  at least two distinct words",
            fontsize=7.55, color="#333333", ha="left", va="top", linespacing=1.3)
    arrow(ax, (7.9, 2.49), (8.15, 2.49), color=RED)

    box(ax, 8.15, 0.55, 2.35, 0.68, "Score and\nranked findings", fs=8.8, fc=LIGHT_GREEN, ec=GREEN)
    arrow(ax, (10.0, 1.55), (9.35, 1.23), color=GREEN)
    ax.text(10.6, 0.88, "max 8 findings;\nno invented errors", fontsize=7.6, color=GREY)

    ax.text(0.45, 0.30, "CMUdict and the acoustic model use different alphabets; both are folded to IPA before comparison.",
            fontsize=8.0, color=GREY, ha="left")
    ax.text(0.45, 0.05, "The model proposes sounds.  Code decides which recurring patterns are trustworthy enough to report.",
            fontsize=8.0, color=GREY, ha="left")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / "fig03_pronunciation.png", dpi=220, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 4 - entity relationship model
# ---------------------------------------------------------------------------
def figure_er():
    fig, ax = canvas(14, 9.4)
    entity(ax, 0.55, 7.05, 3.55, 1.65, "sessions",
           ["id  (PK)", "mode, spoken_language", "status, started_at", "ended_at, last_turn_at"], fc=MID_BLUE)
    entity(ax, 4.75, 7.05, 3.55, 1.65, "turns",
           ["id  (PK)", "session_id  (FK)", "index, speaker", "transcript, audio_key", "duration, words_json"], fc=MID_BLUE)
    entity(ax, 8.95, 7.05, 4.15, 1.65, "speech_analyses",
           ["session_id  (PK/FK)", "grammar/vocabulary/fluency", "pronunciation scores", "provider, analyzed_at"], fc=LIGHT_TEAL, ec=TEAL)

    entity(ax, 0.45, 4.55, 2.95, 1.55, "grammar_issues",
           ["id, session_id", "original, corrected", "rule, explanation", "confidence, position"], fc=LIGHT_AMBER, ec=AMBER)
    entity(ax, 3.65, 4.55, 3.10, 1.55, "vocabulary_issues",
           ["id, session_id", "type, text, occurrences", "suggestion, example", "severity"], fc=LIGHT_AMBER, ec=AMBER)
    entity(ax, 7.00, 4.55, 3.05, 1.55, "fluency_findings",
           ["id, session_id", "type, detail", "start/end or count", "value"], fc=LIGHT_AMBER, ec=AMBER)
    entity(ax, 10.30, 4.55, 3.10, 1.55, "pronunciation_issues",
           ["id, session_id", "expected, heard", "occurrences, confidence", "examples, drill words"], fc=LIGHT_AMBER, ec=AMBER)

    entity(ax, 2.45, 1.55, 3.45, 1.45, "english_alternatives",
           ["session_id  (PK/FK)", "language, provider", "generated_at"], fc=LIGHT_GREEN, ec=GREEN)
    entity(ax, 7.55, 1.55, 3.55, 1.45, "alternative_items",
           ["id, session_id", "original, english", "kind, rank, note"], fc=LIGHT_GREEN, ec=GREEN)
    ax.add_patch(FancyBboxPatch((11.75, 1.55), 1.75, 1.45, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc="#FAFAFA", ec=GREY, ls=(0, (3, 3))))
    ax.text(12.62, 2.28, "audio files\nlive in object\nstorage, not in\nthe database", ha="center", va="center",
            fontsize=7.8, color=GREY)

    # sessions 1:N turns
    arrow(ax, (4.10, 7.55), (4.75, 7.55), color=NAVY, style="-", lw=1.1)
    ax.text(4.18, 7.70, "1", fontsize=8, color=NAVY)
    ax.text(4.58, 7.70, "N", fontsize=8, color=NAVY)

    # sessions 1:1 speech_analyses, routed above the turns box
    ax.plot([2.2, 2.2, 10.7, 10.7], [8.70, 9.02, 9.02, 8.70], color=NAVY, lw=1.1)
    ax.add_patch(FancyArrowPatch((10.7, 8.95), (10.7, 8.72), arrowstyle="-|>", mutation_scale=11, color=NAVY, lw=1.1))
    ax.text(2.30, 8.90, "1", fontsize=8, color=NAVY)
    ax.text(10.45, 8.90, "1", fontsize=8, color=NAVY)
    ax.text(6.45, 9.12, "summarised by", fontsize=7.6, color=GREY, ha="center", style="italic")

    # speech_analyses 1:N issue tables, drawn as a clean bus
    ax.plot([11.02, 11.02], [7.05, 6.35], color=NAVY, lw=1.1)
    ax.plot([1.92, 11.02], [6.35, 6.35], color=NAVY, lw=1.1)
    for x in (1.92, 5.20, 8.52, 11.85):
        ax.plot([x, x], [6.35, 6.10], color=NAVY, lw=1.1)
        ax.add_patch(FancyArrowPatch((x, 6.18), (x, 6.11), arrowstyle="-|>", mutation_scale=10, color=NAVY, lw=1.1))
        ax.text(x + 0.08, 6.20, "N", fontsize=7.6, color=NAVY)
    ax.text(11.12, 6.78, "1", fontsize=8, color=NAVY)
    ax.text(3.9, 6.20, "contains", fontsize=7.4, color=GREY, style="italic")

    # sessions 1:1 english_alternatives, routed along the far left
    ax.plot([0.55, 0.16, 0.16, 2.45], [7.55, 7.55, 2.28, 2.28], color=NAVY, lw=1.1)
    ax.add_patch(FancyArrowPatch((2.30, 2.28), (2.46, 2.28), arrowstyle="-|>", mutation_scale=10, color=NAVY, lw=1.1))
    ax.text(0.24, 5.0, "1", fontsize=8, color=NAVY)
    ax.text(2.32, 2.42, "1", fontsize=8, color=NAVY)

    # english_alternatives 1:N alternative_items
    arrow(ax, (5.90, 2.28), (7.55, 2.28), color=NAVY, style="-", lw=1.1)
    ax.text(5.98, 2.42, "1", fontsize=8, color=NAVY)
    ax.text(7.36, 2.42, "N", fontsize=8, color=NAVY)

    # foreign key notes
    ax.text(0.35, 0.65, "All child tables carry session_id; deleting a session cascades to its turns and analyses.",
            fontsize=8.0, color=GREY, ha="left")
    ax.text(0.35, 0.30, "Word timings are stored with the user turn; they are the input to the fluency analysis.",
            fontsize=8.0, color=GREY, ha="left")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / "fig04_er.png", dpi=220, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 5 - context diagram
# ---------------------------------------------------------------------------
def figure_context():
    fig, ax = canvas(12, 7.2)
    ax.add_patch(Circle((6.0, 3.45), 1.35, facecolor=MID_BLUE, edgecolor=NAVY, linewidth=1.6))
    ax.text(6.0, 3.62, "0", ha="center", va="center", fontsize=18, fontweight="bold", color=NAVY)
    ax.text(6.0, 3.15, "Lexa\nvoice coach", ha="center", va="center", fontsize=12, fontweight="bold", color=NAVY)

    box(ax, 0.55, 5.35, 3.0, 1.0, "Learner\n(browser, microphone)", fs=9.6)
    box(ax, 8.45, 5.35, 3.0, 1.0, "Speech / language providers\n(Groq, Sarvam, Deepgram)", fs=8.8, fc=LIGHT_TEAL, ec=TEAL)
    box(ax, 8.45, 1.15, 3.0, 1.0, "Persistent stores\n(database + audio storage)", fs=8.8, fc=LIGHT_GREY, ec=GREY)
    box(ax, 0.55, 1.15, 3.0, 1.0, "Uploaded video\n(local file)", fs=9.2, fc=LIGHT_AMBER, ec=AMBER)

    arrow(ax, (3.55, 5.60), (4.85, 4.25), text="audio, video, mode,\nlanguage, control", tx=3.35, ty=4.95, fs=8.2, rad=-0.1)
    arrow(ax, (4.85, 3.75), (3.55, 5.15), color=TEAL, text="reply audio, transcript,\nreport, scores", tx=3.10, ty=4.30, fs=8.2, rad=-0.1)
    arrow(ax, (7.35, 4.15), (8.45, 5.55), text="STT / LLM / TTS\nrequests", tx=8.85, ty=4.62, fs=8.2, rad=-0.1)
    arrow(ax, (8.45, 5.85), (7.35, 4.45), color=TEAL, text="transcripts, replies,\nsynthesised audio", tx=7.20, ty=5.55, fs=8.2, rad=-0.1)
    arrow(ax, (7.35, 2.75), (8.45, 1.85), text="sessions, turns,\naudio, analyses", tx=8.85, ty=2.38, fs=8.2, rad=0.1)
    arrow(ax, (8.45, 1.45), (7.35, 2.45), color=TEAL, text="stored records", tx=7.10, ty=1.72, fs=8.2, rad=0.1)
    arrow(ax, (2.05, 2.15), (4.95, 2.65), text="video file", tx=3.65, ty=2.52, fs=8.2, rad=0.08)

    ax.text(0.55, 0.45, "Level-0 data-flow diagram.  The learner is the only human actor; providers and stores are external systems.",
            fontsize=8.0, color=GREY, ha="left")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / "fig05_context_dfd.png", dpi=220, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 6 - level-1 data-flow diagram
# ---------------------------------------------------------------------------
def figure_level1():
    fig, ax = canvas(13.6, 8.8)

    def process(x, y, label, fc=MID_BLUE, ec=NAVY):
        ax.add_patch(FancyBboxPatch((x, y), 2.35, 0.92, boxstyle="round,pad=0.02,rounding_size=0.10",
                                    fc=fc, ec=ec, lw=1.1))
        ax.text(x + 1.17, y + 0.46, label, ha="center", va="center", fontsize=8.4, linespacing=1.12)

    def store(x, y, label):
        ax.add_patch(FancyBboxPatch((x, y), 2.55, 0.68, boxstyle="round,pad=0.01,rounding_size=0.04",
                                    fc="white", ec=GREY, lw=1.1))
        ax.plot([x, x], [y, y + 0.68], color=GREY, lw=3.0)
        ax.text(x + 0.17, y + 0.34, label, ha="left", va="center", fontsize=7.9)

    # external entities
    box(ax, 0.25, 6.55, 1.45, 0.80, "Learner", fs=9.0, fc=LIGHT_GREEN, ec=GREEN)
    box(ax, 8.65, 6.45, 3.40, 0.90, "Cloud providers\nSTT · LLM · TTS", fs=8.6, fc=LIGHT_TEAL, ec=TEAL)
    box(ax, 10.85, 1.65, 2.20, 0.90, "Uploaded\nvideo", fs=8.5, fc=LIGHT_AMBER, ec=AMBER)

    # top row
    process(2.10, 6.48, "1.0\nCapture and\nvalidate")
    process(4.85, 6.48, "2.0\nTranscribe and\ngenerate reply")
    process(4.85, 4.95, "3.0\nPersist")
    process(1.55, 1.60, "4.0\nAnalyse\nEnglish speech", LIGHT_TEAL, TEAL)
    process(4.85, 1.60, "5.0\nBuild language\nbridge", LIGHT_TEAL, TEAL)
    process(8.15, 1.60, "6.0\nIngest\nvideo", LIGHT_AMBER, AMBER)

    # data stores
    store(1.45, 3.60, "D1  sessions, turns")
    store(4.85, 3.60, "D2  analyses")
    store(7.85, 3.60, "D3  audio files")

    # learner -> capture -> transcribe/reply -> cloud
    arrow(ax, (1.70, 6.95), (2.10, 6.95), text="audio, video,\nmode", tx=1.62, ty=7.47, fs=7.5)
    arrow(ax, (4.45, 6.95), (4.85, 6.95), text="validated\naudio", tx=4.65, ty=7.47, fs=7.5)
    arrow(ax, (7.20, 7.02), (8.65, 7.02), text="audio → transcript", tx=7.92, ty=7.18, fs=7.4)
    arrow(ax, (8.65, 6.72), (7.20, 6.72), color=TEAL, text="text + reply", tx=7.92, ty=6.56, fs=7.4)

    # turn persistence
    arrow(ax, (6.02, 6.48), (6.02, 5.87), text="turn, reply,\ntimings", tx=6.48, ty=6.18, fs=7.4)
    arrow(ax, (4.85, 5.40), (3.05, 4.28), text="sessions\n+ turns", tx=3.55, ty=5.02, fs=7.3)
    arrow(ax, (6.05, 4.95), (6.05, 4.28), text="analysis\nrecords", tx=6.50, ty=4.60, fs=7.3)
    arrow(ax, (7.20, 5.40), (8.55, 4.28), text="audio", tx=8.12, ty=4.92, fs=7.3)

    # post-session analyses
    arrow(ax, (2.75, 3.60), (2.75, 2.52), text="read\nturns", tx=3.10, ty=3.07, fs=7.3)
    # D1 -> P5, routed below the two analysis boxes to avoid crossing P4 -> D2
    ax.plot([4.00, 4.00, 5.60, 5.60], [3.60, 3.10, 3.10, 2.52], color=BLUE, lw=1.2)
    ax.add_patch(FancyArrowPatch((5.60, 2.62), (5.60, 2.54), arrowstyle="-|>", mutation_scale=10, color=BLUE, lw=1.2))
    ax.text(4.25, 3.18, "read turns", fontsize=7.3, color=GREY)
    # P4 -> D2, routed above the analysis boxes
    ax.plot([3.55, 3.55, 5.55, 5.55], [2.52, 3.34, 3.34, 3.60], color=BLUE, lw=1.2)
    ax.add_patch(FancyArrowPatch((5.55, 3.53), (5.55, 3.61), arrowstyle="-|>", mutation_scale=10, color=BLUE, lw=1.2))
    ax.text(5.65, 3.40, "scores", fontsize=7.3, color=GREY)
    arrow(ax, (6.00, 2.52), (6.00, 3.60), text="alternatives", tx=6.45, ty=3.05, fs=7.3)

    # video ingest
    arrow(ax, (10.85, 2.10), (10.50, 2.10), text="", fs=7.3)
    arrow(ax, (9.35, 2.52), (9.35, 3.60), text="normalised\naudio", tx=9.78, ty=3.05, fs=7.3)
    # session row written along the bottom, avoiding the analysis boxes
    ax.plot([8.15, 7.55, 7.55], [1.92, 1.92, 4.05], color=BLUE, lw=1.2)
    ax.add_patch(FancyArrowPatch((7.55, 3.94), (7.55, 4.02), arrowstyle="-|>", mutation_scale=10, color=BLUE, lw=1.2))
    ax.text(8.65, 1.22, "new session", fontsize=7.3, color=GREY)

    ax.text(0.30, 0.62, "Level-1 DFD.  Analyses read the persisted transcript; only the pronunciation sub-process re-reads D3.",
            fontsize=7.9, color=GREY, ha="left")
    ax.text(0.30, 0.30, "Rounded boxes are processes, open left-edged rectangles are data stores, plain boxes are external entities.",
            fontsize=7.9, color=GREY, ha="left")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / "fig06_level1_dfd.png", dpi=220, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 7 - video workflow
# ---------------------------------------------------------------------------
def figure_video():
    fig, ax = canvas(12, 10.2)
    terminator(ax, 4.0, 9.55, 2.2, 0.55, "Start")
    box(ax, 2.95, 8.55, 2.1, 0.60, "Select video file", fs=9.0)
    diamond(ax, 4.0, 7.55, 2.55, 1.10, "Extension and\nsize valid?", fs=8.6)
    box(ax, 7.55, 7.30, 3.0, 0.55, "Reject: 400 / 413", fs=8.8, fc=LIGHT_RED, ec=RED)
    box(ax, 2.95, 6.10, 2.1, 0.60, "Stream to temp file", fs=8.8)
    diamond(ax, 4.0, 5.05, 2.55, 1.10, "Duration\n≤ 300 s?", fs=8.6)
    box(ax, 7.55, 4.80, 3.0, 0.55, "Reject: 422", fs=8.8, fc=LIGHT_RED, ec=RED)
    box(ax, 2.55, 3.55, 2.9, 0.65, "FFmpeg: extract\n16 kHz mono WAV", fs=8.8, fc=LIGHT_AMBER, ec=AMBER)
    diamond(ax, 4.0, 2.55, 2.55, 1.10, "Speech\nfound?", fs=8.6)
    box(ax, 7.55, 2.30, 3.0, 0.55, "Reject: empty\ntranscript", fs=8.8, fc=LIGHT_RED, ec=RED)
    box(ax, 2.95, 1.30, 2.1, 0.62, "STT: English\npinned", fs=8.8, fc=LIGHT_TEAL, ec=TEAL)
    box(ax, 2.55, 0.30, 2.9, 0.68, "Completed VIDEO_COACH\nsession + one user turn", fs=8.4, fc=LIGHT_GREEN, ec=GREEN)
    box(ax, 7.15, 0.30, 3.55, 0.68, "Client runs grammar,\nvocabulary and fluency", fs=8.4)

    arrow(ax, (4.0, 9.27), (4.0, 9.15))
    arrow(ax, (4.0, 8.55), (4.0, 8.10))
    arrow(ax, (5.28, 7.55), (7.55, 7.55), text="no", tx=5.8, ty=7.70, fs=8.0)
    arrow(ax, (4.0, 7.00), (4.0, 6.70), text="yes", tx=4.35, ty=6.88, fs=8.0)
    arrow(ax, (4.0, 6.10), (4.0, 5.60))
    arrow(ax, (5.28, 5.05), (7.55, 5.05), text="no", tx=5.8, ty=5.20, fs=8.0)
    arrow(ax, (4.0, 4.50), (4.0, 4.20), text="yes", tx=4.35, ty=4.38, fs=8.0)
    arrow(ax, (4.0, 3.55), (4.0, 3.10))
    arrow(ax, (5.28, 2.55), (7.55, 2.55), text="no", tx=5.8, ty=2.70, fs=8.0)
    arrow(ax, (4.0, 2.00), (4.0, 1.92), text="yes", tx=4.35, ty=1.98, fs=8.0)
    arrow(ax, (4.0, 1.30), (4.0, 0.98))
    arrow(ax, (5.45, 0.64), (7.15, 0.64), text="session id", tx=6.28, ty=0.80, fs=8.0)

    ax.text(0.35, 9.70, "Video review workflow", fontsize=11, color=NAVY, fontweight="bold")
    ax.text(0.35, 0.02, "The uploaded video is deleted after extraction; only the normalised audio, transcript and timings are retained.",
            fontsize=8.0, color=GREY, ha="left")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / "fig07_video_workflow.png", dpi=220, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 8 - language bridge
# ---------------------------------------------------------------------------
def figure_bridge():
    fig, ax = canvas(13, 8.8)
    box(ax, 0.45, 7.15, 2.35, 0.80, "Learner selects\nspoken language", fs=8.8)
    box(ax, 3.15, 7.15, 2.50, 0.80, "Session mode =\nLANGUAGE_BRIDGE", fs=8.5)
    diamond(ax, 7.10, 7.55, 2.45, 1.05, "language in\n{kn, ta, te}?", fs=8.4)
    box(ax, 4.55, 5.95, 2.90, 0.78, "Sarvam saaras:v4\nBCP-47 language code", fs=8.5, fc=LIGHT_TEAL, ec=TEAL)
    box(ax, 8.55, 5.95, 2.90, 0.78, "Groq Whisper\n(Hindi / English)", fs=8.5, fc=LIGHT_TEAL, ec=TEAL)
    box(ax, 6.25, 4.85, 2.70, 0.72, "Pinned-language\ntranscript", fs=8.8)
    box(ax, 9.65, 4.85, 2.70, 0.72, "LLM: simple English\nreply + JSON items", fs=8.4, fc=MID_BLUE, ec=NAVY)
    box(ax, 9.65, 3.75, 2.70, 0.68, "English reply →\nTTS playback", fs=8.5, fc=LIGHT_TEAL, ec=TEAL)

    ax.add_patch(FancyBboxPatch((1.15, 1.70), 10.85, 1.55, boxstyle="round,pad=0.03,rounding_size=0.10",
                                fc=LIGHT_RED, ec=RED, lw=1.0))
    ax.text(1.35, 3.02, "DETERMINISTIC VALIDATION (applied after the model, not instead of it)",
            fontsize=8.5, color=RED, fontweight="bold")
    checks = [
        "1  original must occur in the transcript (similarity ≥ 0.8)",
        "2  original must use the language's native script",
        "3  known loanwords and Latin-script English are dropped",
        "4  at most six words; no duplicate original/English pair",
        "5  English side must be useful, non-empty and not a translation of a full clause",
    ]
    ax.text(1.40, 2.72, "\n".join(checks), fontsize=7.9, color="#333333", ha="left", va="top", linespacing=1.38)

    box(ax, 2.55, 0.65, 2.65, 0.70, "Rank by common-word\nfrequency and confidence", fs=7.9)
    box(ax, 5.65, 0.65, 2.10, 0.70, "Cap at 12 items", fs=8.2)
    box(ax, 8.20, 0.65, 2.35, 0.70, "Store alternatives\nreport", fs=8.2, fc=LIGHT_GREEN, ec=GREEN)
    box(ax, 2.55, 0.02, 8.00, 0.42, "Browser renders native word → English alternative → short example",
        fs=7.8, fc=LIGHT_GREY, ec=GREY)

    arrow(ax, (2.80, 7.55), (3.15, 7.55))
    arrow(ax, (5.65, 7.55), (5.88, 7.55))
    arrow(ax, (6.55, 7.55), (6.55, 7.12), text="", fs=8.0)
    arrow(ax, (6.55, 6.85), (5.85, 6.73), text="yes", tx=6.30, ty=6.88, fs=7.8, rad=-0.05)
    arrow(ax, (7.65, 6.85), (9.65, 6.73), text="no", tx=8.75, ty=6.88, fs=7.8, rad=0.05)
    arrow(ax, (6.00, 5.95), (6.85, 5.57), text="", fs=8.0)
    arrow(ax, (9.85, 5.95), (8.55, 5.57), text="", fs=8.0)
    arrow(ax, (8.95, 5.21), (9.65, 5.21), text="transcript", tx=9.28, ty=5.36, fs=7.6)
    arrow(ax, (10.95, 4.85), (10.95, 4.43), text="reply", tx=11.35, ty=4.64, fs=7.6)
    # LLM alternatives leave on the right, bypassing the TTS box and entering the validation panel
    ax.plot([12.35, 12.70, 12.70, 12.00], [5.21, 5.21, 3.25, 3.25], color=BLUE, lw=1.2)
    ax.add_patch(FancyArrowPatch((12.08, 3.25), (11.98, 3.25), arrowstyle="-|>", mutation_scale=10, color=BLUE, lw=1.2))
    ax.text(12.42, 4.10, "items", fontsize=7.4, color=GREY, rotation=90, va="center", ha="center")
    arrow(ax, (5.50, 1.70), (3.95, 1.35), text="", fs=8.0, rad=0.05)
    arrow(ax, (5.20, 1.00), (5.65, 1.00))
    arrow(ax, (7.75, 1.00), (8.20, 1.00))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / "fig08_language_bridge.png", dpi=220, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 9 - deployment topology
# ---------------------------------------------------------------------------
def figure_deployment():
    fig, ax = canvas(12.5, 7.6)
    box(ax, 0.5, 5.55, 2.2, 0.85, "Learner\nbrowser", fs=9.4)
    box(ax, 3.35, 5.55, 2.5, 0.85, "Vercel\nReact / TanStack Start", fs=9.0, fc=LIGHT_GREY, ec=GREY)
    box(ax, 6.55, 5.55, 2.7, 0.85, "Render (Docker)\nFastAPI + FFmpeg", fs=9.0, fc=MID_BLUE, ec=NAVY)
    box(ax, 9.95, 5.55, 2.15, 0.85, "Neon\nPostgres", fs=9.2, fc=LIGHT_TEAL, ec=TEAL)
    box(ax, 6.55, 3.35, 2.7, 0.85, "External APIs\nGroq · Sarvam · Deepgram", fs=8.4, fc=LIGHT_TEAL, ec=TEAL)
    box(ax, 9.95, 3.35, 2.15, 0.85, "Render disk\naudio WAV", fs=8.8, fc=LIGHT_GREY, ec=GREY)
    box(ax, 0.5, 3.35, 2.2, 0.85, "GitHub\nrepository", fs=8.8, fc=LIGHT_GREY, ec=GREY)
    box(ax, 3.35, 1.15, 8.75, 0.72, "Configuration: environment variables for provider keys, DATABASE_URL, CORS origins; no secret is shipped to the browser.",
        fs=8.4, fc=LIGHT_AMBER, ec=AMBER)

    arrow(ax, (2.7, 5.98), (3.35, 5.98), text="HTTPS", tx=3.0, ty=6.13, fs=8.0)
    arrow(ax, (5.85, 5.98), (6.55, 5.98), text="API + audio", tx=6.2, ty=6.13, fs=8.0)
    arrow(ax, (9.25, 5.98), (9.95, 5.98), text="SQL", tx=9.6, ty=6.13, fs=8.0)
    arrow(ax, (7.9, 5.55), (7.9, 4.20), text="HTTPS", tx=8.15, ty=4.82, fs=8.0)
    arrow(ax, (9.25, 5.75), (9.95, 4.20), text="read/write", tx=9.95, ty=4.85, fs=8.0, rad=0.0)
    arrow(ax, (1.7, 4.20), (3.35, 5.40), text="push", tx=2.2, ty=4.55, fs=7.6, rad=-0.1)
    arrow(ax, (1.7, 3.75), (6.55, 5.40), text="deploy", tx=3.0, ty=4.45, fs=7.6, rad=-0.12)

    ax.add_patch(FancyBboxPatch((3.35, 2.25), 5.3, 0.62, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc=LIGHT_RED, ec=RED, lw=0.9, ls=(0, (4, 3))))
    ax.text(6.0, 2.56, "Pronunciation model disabled on the free instance (~1.6 GB RAM);\nall other analyses remain available.",
            ha="center", va="center", fontsize=8.0, color=RED)

    ax.text(0.5, 0.55, "The database is the only durable store shared by instances; local audio storage is suitable for a single demonstration instance.",
            fontsize=8.0, color=GREY, ha="left")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / "fig09_deployment.png", dpi=220, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 10 - frontend routes
# ---------------------------------------------------------------------------
def figure_frontend():
    fig, ax = canvas(12, 7.2)
    box(ax, 4.5, 5.75, 2.7, 0.75, "Landing  /\nchoose a mode", fs=9.2, fc=MID_BLUE, ec=NAVY)
    box(ax, 1.0, 3.95, 3.0, 0.85, "Live conversation\n/conversation", fs=9.0)
    box(ax, 5.0, 3.95, 3.0, 0.85, "Live bridge\n/conversation?lang=kn", fs=8.8)
    box(ax, 9.0, 3.95, 2.6, 0.85, "Video review\n/video", fs=9.0)
    box(ax, 0.9, 2.10, 3.0, 0.85, "Session report\n/insights?session=…", fs=8.8, fc=LIGHT_TEAL, ec=TEAL)
    box(ax, 5.0, 2.10, 3.0, 0.85, "English alternatives\n/alternatives?session=…", fs=8.6, fc=LIGHT_GREEN, ec=GREEN)
    box(ax, 9.0, 2.10, 2.6, 0.85, "Session report\n/insights?session=…", fs=8.6, fc=LIGHT_TEAL, ec=TEAL)
    box(ax, 1.5, 0.55, 3.8, 0.70, "Insights: grammar, vocabulary,\nfluency, pronunciation", fs=8.1, fc=LIGHT_GREY, ec=GREY)
    box(ax, 6.4, 0.55, 4.0, 0.70, "Alternatives: English alternatives\nfor native-language words", fs=8.1, fc=LIGHT_GREEN, ec=GREEN)

    arrow(ax, (5.2, 5.75), (2.8, 4.80), text="English", tx=3.5, ty=5.25, fs=8.0)
    arrow(ax, (6.0, 5.75), (6.5, 4.80), text="Hindi / Kannada /\nTamil / Telugu", tx=6.35, ty=5.20, fs=7.8)
    arrow(ax, (6.9, 5.75), (10.0, 4.80), text="upload", tx=9.0, ty=5.25, fs=8.0)
    arrow(ax, (2.5, 3.95), (2.4, 2.95), text="end call", tx=2.9, ty=3.45, fs=8.0)
    arrow(ax, (6.5, 3.95), (6.5, 2.95), text="end call →\nalternatives", tx=7.0, ty=3.45, fs=7.8)
    arrow(ax, (10.3, 3.95), (10.3, 2.95), text="session id", tx=10.85, ty=3.45, fs=8.0)
    arrow(ax, (3.4, 2.10), (3.4, 1.25), text="", fs=8.0)
    arrow(ax, (8.3, 2.10), (8.4, 1.25), text="", fs=8.0)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(OUT / "fig10_frontend_flow.png", dpi=220, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


def main():
    figure_architecture()
    figure_sequence()
    figure_pronunciation()
    figure_er()
    figure_context()
    figure_level1()
    figure_video()
    figure_bridge()
    figure_deployment()
    figure_frontend()
    print(f"Wrote figures to {OUT}")


if __name__ == "__main__":
    main()
