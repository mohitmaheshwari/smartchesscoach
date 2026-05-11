"""
Caption renderer configuration — thresholds and limits separated from
rule definitions so different coaching surfaces (1200 coach, 1800 coach,
puzzle mode, study mode) can override without touching the rule library.

Per user instruction 2026-05-11: never hardcode thresholds inside renderer
rules. Always reference these constants.
"""
from __future__ import annotations


# ── Caption length ──────────────────────────────────────────────────────
# Hard cap. The renderer truncates anything longer; rules should produce
# captions well under this. Per design doc §7.
MAX_CAPTION_WORDS = 25


# ── Tactic visibility thresholds ────────────────────────────────────────
# Missed-tactic evidence carries a human_visibility_score 1..5:
#   1 = trivial (immediate, ≥minor piece)
#   2 = visible to a 1200 (one forced reply, then clear)
#   3 = visible to a 1500 (2 plies of forcing)
#   4 = visible to a 1800 (precise calculation needed)
#   5 = engine-only (Stockfish ghost tactic)
#
# Default: only surface tactics with score ≤ 2 to a 1200 audience.
# Higher-rated coaches can raise this; puzzle mode might lower it.
DEFAULT_VISIBLE_TACTIC_THRESHOLD = 2


# ── Material thresholds ────────────────────────────────────────────────
# Below this gain, "wins material" captions get demoted — typically
# small pawn-trade differences that aren't the story of the move.
MIN_MATERIAL_CAPTION_GAIN_CP = 100


# ── Threat thresholds ──────────────────────────────────────────────────
# A "threat" must win at least this much SEE to be worth captioning.
MIN_THREAT_SEE_CP = 200


# ── Aligned-pieces (pin/skewer) significance ───────────────────────────
# Only render a pin/skewer caption when the rear piece is at least this
# valuable. Otherwise the alignment is geometrically real but trivially
# uninteresting (e.g. pawn pinned to another pawn).
MIN_ALIGNED_REAR_VALUE_CP = 500


# ── Tactic-celebration safety gate ──────────────────────────────────────
# A "tactic" caption (fork / pin / discovered attack / threat) only
# fires when the played move ISN'T itself a mistake or blunder. If the
# engine says the move loses this many centipawns, the story of the
# move is the cp_loss, not the geometry — the tactic is incidental and
# will be answered. From the d7ce40cf corpus review:
#   #19 USER Re7 (286 cp blunder) was rendered "forks c7 and f7"
#   #17 USER a3  (110 cp mistake) was rendered "threatens b4"
# Suppress at the primary_reason layer so R02/R03/R04/R10 don't ever
# get the chance to celebrate a losing move.
MAX_CP_LOSS_FOR_TACTIC_CELEBRATION = 100
