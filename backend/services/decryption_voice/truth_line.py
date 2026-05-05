"""
Truth-line generator — produces the 3-line headline (identity / anchor /
forward trigger) shown FIRST on the post-game screen. Coach Voice.

Strictly separate from the Decryption generator. Truth never sees
Decryption output, never reads V5 plan prose. It only looks at structural
move data (move_number, san, cp_loss, severity, is_user_move) and the
game-reason classification. This is the "do not let voices blend" rule
from project_decryption_voice.md enforced at the input boundary.

No LLM. Deterministic templates per scenario, with hash-based variant
selection so the same line doesn't appear game after game. Hard-validated
on output via validators.validate_truth_block().
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .validators import validate_truth_block, TRUTH_LINE_MAX_WORDS

logger = logging.getLogger(__name__)


# ── Scenario archetypes ───────────────────────────────────────────────
# Map game_reason_classifier categories to four behavioral archetypes
# that drive Truth voice. Each archetype gets its own pool of identity,
# anchor verb-phrase, and trigger lines.

SCENARIO_BLUNDERED = "blundered"     # decisive blunder, was equal/winning
SCENARIO_THREW = "threw"             # was winning, simplified/relaxed away
SCENARIO_EQUALIZED = "equalized"     # was losing, opp let you back in, you gave it back
SCENARIO_SQUEEZED = "squeezed"       # gradual passivity, no single moment
SCENARIO_OUTPLAYED = "outplayed"     # opponent saw a plan; no clear failure


# Pivot tiers — different shades of "the game flipped on this move".
# "won":      user was at-or-below equal, opp blunder pushed them to clearly
#             winning, user then gave it back. The strongest narrative.
# "equalized": user was clearly losing (eval ≤ -2 pawns from their POV), opp
#             blunder brought them back to roughly even, user then sent it
#             back to losing. Different felt experience — "I had a chance to
#             come back, I didn't take it."

PIVOT_TIER_WON = "won"
PIVOT_TIER_EQUALIZED = "equalized"


_REASON_TO_SCENARIO = {
    "threw_winning": SCENARIO_THREW,
    "one_move_blunder": SCENARIO_BLUNDERED,
    "tactical_miss": SCENARIO_BLUNDERED,
    "calculation_error": SCENARIO_BLUNDERED,
    "opening_disaster": SCENARIO_BLUNDERED,
    "positional": SCENARIO_SQUEEZED,
    "endgame_collapse": SCENARIO_SQUEEZED,
    "time_collapse": SCENARIO_BLUNDERED,
}


def classify_scenario(game_reason: str, blunder_count: int) -> str:
    """Map game_reason_classifier output → behavioral scenario.

    Public so player_decryption.py can route to the same scenario as
    Truth without duplicating the mapping.
    """
    s = _REASON_TO_SCENARIO.get(game_reason or "")
    if s:
        return s
    # Fallback: a loss with no clear blunder pattern is "outplayed".
    # A loss with blunders but no clean classification falls back to
    # "squeezed" which has the safest copy.
    if blunder_count == 0:
        return SCENARIO_OUTPLAYED
    return SCENARIO_SQUEEZED


# Backwards-compat alias for any in-module callers below.
_classify_scenario = classify_scenario


# ── Identity lines (line 1 of Truth) ──────────────────────────────────
# All <= 12 words. Identity-level: about a habit, not a single move.

IDENTITY_BY_SCENARIO: Dict[str, List[str]] = {
    SCENARIO_BLUNDERED: [
        "You didn't lose this. You stopped looking at their pieces.",
        "You didn't lose this. You attacked without checking their reply.",
        "You didn't lose this. You stopped seeing what they could do.",
    ],
    SCENARIO_THREW: [
        "You didn't get outplayed. You relaxed.",
        "You didn't get outplayed. You stopped working when you started winning.",
        "You didn't lose to them. You traded the game away.",
    ],
    SCENARIO_EQUALIZED: [
        "You didn't lose this. You eased off after the comeback.",
        "You fought back. Then you stopped fighting.",
        "You didn't lose to them. You stopped after equalizing.",
    ],
    SCENARIO_SQUEEZED: [
        "You didn't lose to them. You let them run the game.",
        "You didn't get outplayed. You went passive.",
        "You didn't lose this. You stopped having a plan.",
    ],
    SCENARIO_OUTPLAYED: [
        "They outplayed you. There's no move to undo.",
        "You were playing moves. They were playing a plan.",
        "They saw a plan you didn't.",
    ],
}


# ── Anchor verb phrases (line 2 of Truth) ─────────────────────────────
# Slotted into "Move N — {phrase}." or "Move N — you {phrase}."
# Kept short so the full anchor stays under the 12-word cap even with
# higher move numbers.

ANCHOR_PHRASES_BY_SCENARIO: Dict[str, List[str]] = {
    SCENARIO_BLUNDERED: [
        "you played {san} without checking their reply",
        "you went after {san} and missed their threat",
        "{san} walked into their answer",
    ],
    SCENARIO_THREW: [
        "you traded thinking the game was over",
        "you stopped pressing when {san} came",
        "{san} simplified into a lost position",
    ],
    SCENARIO_EQUALIZED: [
        "{san} sent you straight back into trouble",
        "{san} undid the comeback in one move",
        "you'd just got back in — {san} sent you out",
    ],
    SCENARIO_SQUEEZED: [
        "you had no piece free to challenge them",
        "your pieces were already tied down",
        "{san} was still defending",
    ],
    SCENARIO_OUTPLAYED: [
        "their pieces were already converging",
        "their pieces had a direction yours didn't",
        "{san} answered their threat — not yours",
    ],
}


# ── Catastrophic anchors ─────────────────────────────────────────────
# When the critical move was the one that ended the game (forced mate,
# queen hangs the win, etc.), anchor intensity must match. The general
# scenario pools sound too neutral for moves of this weight.
# Threshold = cp_loss >= 1000 (covers forced-mate evaluations and the
# full-piece-hangs-it-all class).

CATASTROPHIC_CP_LOSS = 1000

CATASTROPHIC_ANCHOR_PHRASES: List[str] = [
    "{san} ended the game on the spot",
    "{san} walked into a forced sequence",
    "{san} gave away the game",
]


# Threw-winning pivot anchors. In chess, white's Nth move and black's
# Nth move share full-move number N, so the opp blunder + user pivot
# frequently land on the SAME move number — using two distinct numbers
# in that case reads as a typo. Two pools, picked by whether the
# numbers match.

# Same move number — back-to-back blunder phrasing.
PIVOT_SAME_NUMBER_ANCHORS: List[str] = [
    "Move {pivot_n} — they blundered, you blundered right back.",
    "Move {pivot_n} — they slipped, you slipped right back.",
    "Move {pivot_n} — they handed you the game, you gave it back.",
]

# Different move numbers — full two-move story.
PIVOT_DIFF_NUMBER_ANCHORS: List[str] = [
    "Move {opp_n} they blundered. Move {pivot_n} you gave it back.",
    "Move {opp_n} the game was yours. Move {pivot_n} you handed it over.",
    "Move {opp_n} they slipped. Move {pivot_n} {san} slipped right back.",
]


# ── Equalized-tier pivot anchors ─────────────────────────────────────
# User was clearly losing, opp slipped, user came back to even, then
# user sent it right back. NOT "the win was yours" — they were never
# winning, just back in the game. Two pools matched to same/diff
# move numbers, same as PIVOT_*_ANCHORS above.

EQUALIZED_PIVOT_SAME_NUMBER_ANCHORS: List[str] = [
    "Move {pivot_n} — they slipped, you slipped right back.",
    "Move {pivot_n} — they opened the door, you closed it yourself.",
    "Move {pivot_n} — they slipped, then you slipped back out.",
]

EQUALIZED_PIVOT_DIFF_NUMBER_ANCHORS: List[str] = [
    "Move {opp_n} they slipped. Move {pivot_n} you sent it back.",
    "Move {opp_n} the door opened. Move {pivot_n} you closed it.",
    "Move {opp_n} they slipped. Move {pivot_n} {san} let it go.",
]


# ── Forward triggers (line 3 of Truth) ────────────────────────────────
# Mutterable mid-game. Short — most under 7 words.

TRIGGER_BY_SCENARIO: Dict[str, List[str]] = {
    SCENARIO_BLUNDERED: [
        "What are they threatening?",
        "Before every move: what changed for them?",
        "Every move: check their reply first.",
    ],
    SCENARIO_THREW: [
        "Winning is when the work starts.",
        "When you're winning, slow down.",
        "Don't relax when you're winning.",
    ],
    SCENARIO_EQUALIZED: [
        "After they slip, the work starts.",
        "Don't ease off after a comeback.",
        "Equal isn't over. Keep working.",
    ],
    SCENARIO_SQUEEZED: [
        "Find work for every piece.",
        "Every piece needs a job that isn't defending.",
        "Stop reacting. Start choosing.",
    ],
    SCENARIO_OUTPLAYED: [
        "Watch their plan, not just yours.",
        "Notice what their pieces are pointed at.",
        "Their plan is half the game.",
    ],
}


def pick_variant(pool: List[str], game_id: str) -> str:
    """Deterministic pick — same game always yields the same variant.
    Hashing on game_id spreads variants across users so the same scenario
    doesn't always render the same phrasing on every screen.

    Public so player_decryption.py can use the same hash strategy with
    salted keys ("g123" + "p" / + "c") to vary lines across layers.
    """
    if not pool:
        return ""
    idx = hash(game_id or "") % len(pool)
    return pool[idx]


# Backwards-compat alias for the existing in-module callers.
_pick_variant = pick_variant


def _format_anchor(critical_move: Dict, scenario: str, game_id: str) -> str:
    """Build line 2 — the anchor.

    Three template paths in priority order:

    1. Threw-winning pivot WITH a known opp preceding blunder →
       two-move narrative anchor: "Move N they blundered. Move M you
       gave it back." Captures the actual game pivot story.

    2. Catastrophic cp_loss (>= CATASTROPHIC_CP_LOSS) without pivot →
       decisive-tone pool ({san} ended the game on the spot, etc.).
       Anchor intensity must match consequence.

    3. Otherwise → scenario-specific pool.
    """
    move_num = critical_move.get("move_number") or critical_move.get("ply") or "?"
    move_san = critical_move.get("move_san") or "?"
    cp_loss = critical_move.get("cp_loss") or 0
    is_pivot = critical_move.get("is_pivot", False)
    pivot_tier = critical_move.get("pivot_tier")
    opp_n = critical_move.get("opp_preceding_move_number")

    # Path 1: pivot + we know the opp's preceding mistake → narrative anchor.
    # Tier picks pool: 'equalized' uses comeback-tone, 'won' (default) keeps
    # the "win was yours, then it wasn't" tone.
    # Same move number (chess full-move pair) → back-to-back phrasing.
    # Different numbers → two-move story.
    if is_pivot and opp_n:
        if pivot_tier == PIVOT_TIER_EQUALIZED:
            pool = EQUALIZED_PIVOT_SAME_NUMBER_ANCHORS if opp_n == move_num else EQUALIZED_PIVOT_DIFF_NUMBER_ANCHORS
        else:
            pool = PIVOT_SAME_NUMBER_ANCHORS if opp_n == move_num else PIVOT_DIFF_NUMBER_ANCHORS
        phrase_template = _pick_variant(pool, game_id)
        line = phrase_template.format(opp_n=opp_n, pivot_n=move_num, san=move_san)
        return line

    if cp_loss >= CATASTROPHIC_CP_LOSS:
        pool = CATASTROPHIC_ANCHOR_PHRASES
    else:
        pool = ANCHOR_PHRASES_BY_SCENARIO.get(scenario) or ANCHOR_PHRASES_BY_SCENARIO[SCENARIO_BLUNDERED]

    phrase_template = _pick_variant(pool, game_id)
    phrase = phrase_template.format(san=move_san)

    line = f"Move {move_num} — {phrase}."
    return line


def _shrink_to_budget(line: str, max_words: int = TRUTH_LINE_MAX_WORDS) -> str:
    """Pull words off the END until the line fits the budget. Keeps the
    period if there is one. Used as the last-resort safety so a stretched
    template never ships an over-budget line.
    """
    if len(line.split()) <= max_words:
        return line
    period = line.endswith(".")
    words = line.split()
    while len(words) > max_words:
        words.pop()
    out = " ".join(words)
    if period and not out.endswith("."):
        out += "."
    return out


# ── Public API ────────────────────────────────────────────────────────

def _find_opp_preceding_mistake(
    decryption_v5_data: List[Dict],
    user_pivot_move: Dict,
) -> Optional[Dict]:
    """Find the opponent's mistake immediately before the user's pivot.

    Walks back from the user's pivot move; returns the first opponent
    move whose severity indicates an error (opp_blunder/opp_mistake/
    blunder/mistake on a non-user move). Returns None if no such move
    exists in the few moves before the pivot.
    """
    if not decryption_v5_data or not user_pivot_move:
        return None
    pivot_n = user_pivot_move.get("move_number")
    pivot_san = user_pivot_move.get("move_san")
    if pivot_n is None or pivot_san is None:
        return None

    # Locate pivot's index in the V5 list.
    pivot_idx = None
    for i, m in enumerate(decryption_v5_data):
        if (m.get("is_user_move")
                and m.get("move_number") == pivot_n
                and m.get("move_san") == pivot_san):
            pivot_idx = i
            break
    if pivot_idx is None:
        return None

    # Walk back at most 4 entries (covers user-good + opp-normal + opp-blunder + buffer).
    for j in range(pivot_idx - 1, max(-1, pivot_idx - 5), -1):
        m = decryption_v5_data[j]
        if m.get("is_user_move"):
            continue
        sev = m.get("severity", "")
        if sev in ("opp_blunder", "opp_mistake", "blunder", "mistake"):
            return m
    return None


def detect_top_moments(
    decryption_v5_data: List[Dict],
    max_moments: int = 4,
    min_separation: int = 3,
    user_color: str = "white",
) -> List[Dict]:
    """Find the top N user mistakes/blunders that defined the game.

    Real coaching shows multiple turning points. We don't pick "the
    one critical moment" — we pick up to `max_moments` user errors
    ranked by cp_loss, with an anti-clustering rule so two adjacent
    blunders don't both surface (we want the king march, the queen
    blunder, the throw-back, the final mate — not all four moves of
    one cluster).

    Args:
        decryption_v5_data: V5 per-move records.
        max_moments: cap on returned moments (default 4).
        min_separation: minimum move-number gap between two picked
            moments (default 3 — adjacent moves like 54 and 55 won't
            both fire; eg 14 and 21 will).

    Returns:
        Sorted by move_number ascending. Each item has the same
        structural fields as pick_critical_move output: move_number,
        move_san, cp_loss, severity, is_pivot, opp_preceding_move_number.
    """
    if not decryption_v5_data:
        return []

    candidates = [
        m for m in decryption_v5_data
        if m.get("is_user_move")
        and m.get("severity") in ("blunder", "mistake")
        and (m.get("cp_loss") or 0) >= 200
    ]
    if not candidates:
        return []

    # Rank by cp_loss desc, then walk and apply anti-clustering filter.
    candidates.sort(key=lambda m: -(m.get("cp_loss") or 0))
    picked: List[Dict] = []
    for m in candidates:
        mn = m.get("move_number") or 0
        # Skip if too close to an already-picked moment.
        if any(abs(mn - (p.get("move_number") or 0)) < min_separation for p in picked):
            continue
        # Promote pivots in the same way pick_critical_move does — they
        # carry the THREW or EQUALIZED narrative even when cp_loss is
        # smaller. Tier ('won' vs 'equalized') drives downstream voice.
        pivot_tier = None
        opp_preceding = None
        idx = decryption_v5_data.index(m)
        user_prior = None
        for i in range(idx - 1, -1, -1):
            if decryption_v5_data[i].get("is_user_move"):
                user_prior = decryption_v5_data[i]
                break
        if user_prior:
            pivot_tier = _classify_pivot_tier(user_prior, m, user_color)
            if pivot_tier:
                opp_preceding = _find_opp_preceding_mistake(decryption_v5_data, m)
                opp_preceding = (opp_preceding or {}).get("move_number") if opp_preceding else None

        picked.append({
            "move_number": m.get("move_number"),
            "move_san": m.get("move_san"),
            "cp_loss": m.get("cp_loss"),
            "severity": m.get("severity"),
            "is_pivot": pivot_tier is not None,
            "pivot_tier": pivot_tier,
            "opp_preceding_move_number": opp_preceding,
        })
        if len(picked) >= max_moments:
            break

    # Return chronological so the page reads start-to-end.
    picked.sort(key=lambda p: p.get("move_number") or 0)
    return picked


def _user_eval(eval_white: Optional[int], user_color: str) -> Optional[int]:
    """Convert white-perspective centipawn eval to user-perspective.
    Engine evals come from white's POV; flip for black users so positive
    always means 'better for the user'."""
    if eval_white is None:
        return None
    return int(eval_white) if (user_color or "").lower() == "white" else -int(eval_white)


def _classify_pivot_tier(
    user_prior: Dict,
    current: Dict,
    user_color: str,
) -> Optional[str]:
    """Classify the eval swing on opp's preceding move into a pivot tier.

    Inputs:
      user_prior: the V5 record for the user move BEFORE the current
                  blunder. Its eval_after is the eval just before opp
                  moved (i.e., the user-side starting point).
      current:    the V5 record for the user blunder being evaluated.
                  Its eval_before is the eval just AFTER opp's move
                  (i.e., the post-opp-blunder position the user faced).
      user_color: 'white' | 'black' — used to flip eval polarity.

    Returns:
      "won":       opp blunder put user from non-winning to clearly winning
                   (≥ +1.5 pawns) AND swing in user's favor ≥ 3 pawns.
      "equalized": user was clearly losing (≤ -2 pawns) and opp blunder
                   brought them to roughly even (-2 ≤ eval ≤ +2) with
                   swing ≥ 2.5 pawns.
      None:        no qualifying swing.

    Falls back to the legacy cp_loss-on-good-move heuristic when eval
    data is missing on either record (treats it as "won" tier).
    """
    pre_eval = _user_eval(user_prior.get("eval_after"), user_color)
    post_eval = _user_eval(current.get("eval_before"), user_color)

    if pre_eval is not None and post_eval is not None:
        swing = post_eval - pre_eval
        # WON: opp blunder pushed user into a winning position.
        if post_eval >= 150 and pre_eval < 150 and swing >= 300:
            return PIVOT_TIER_WON
        # EQUALIZED: user was clearly losing, came back to roughly even.
        if -200 <= post_eval <= 200 and pre_eval <= -200 and swing >= 250:
            return PIVOT_TIER_EQUALIZED
        return None

    # Legacy fallback when eval data isn't available — V5 overloaded
    # cp_loss on good moves to encode swing magnitude.
    prev_sev = user_prior.get("severity")
    prev_cp = user_prior.get("cp_loss") or 0
    if prev_sev in ("good", "best") and prev_cp >= 1000:
        return PIVOT_TIER_WON
    return None


def detect_pivot_move(
    decryption_v5_data: List[Dict],
    user_color: str = "white",
) -> Optional[Dict]:
    """Find the user move that flipped the game.

    Two stacked conditions must hold:

      1. The current user move is a blunder/mistake with cp_loss >= 300
         (a real, decisive error — not a small slip).

      2. The eval swing on opp's preceding move qualifies for a pivot
         tier ('won' or 'equalized'). See _classify_pivot_tier.

    Returns the move dict augmented with `pivot_tier` ('won' or
    'equalized'). Returns None when no qualifying pivot exists.
    """
    if not decryption_v5_data:
        return None
    user_moves = [m for m in decryption_v5_data if m.get("is_user_move")]
    for i in range(1, len(user_moves)):
        m = user_moves[i]
        sev = m.get("severity")
        cp_loss = m.get("cp_loss") or 0
        if sev not in ("blunder", "mistake"):
            continue
        if cp_loss < 300:
            continue
        prev = user_moves[i - 1]
        tier = _classify_pivot_tier(prev, m, user_color)
        if tier:
            out = dict(m)
            out["pivot_tier"] = tier
            return out
    return None


def pick_critical_move(decryption_v5_data: List[Dict], user_color: str = "white") -> Optional[Dict]:
    """Find the move that defines the game from V5 structural data.

    Priority:
      1. Pivot move (user had it, threw it) — narratively the game's
         decisive moment, even when not the largest cp swing.
      2. Otherwise, max cp_loss user mistake — biggest single error
         when no clear pivot exists.

    Returns only structural fields (move_number, move_san, cp_loss,
    severity, is_pivot). We do NOT read narrative, plan, or any V5
    prose — Truth must not see Decryption inputs.

    is_pivot=True signals downstream generators (Truth, Player
    Decryption) to route this game to the THREW scenario regardless
    of what game_reason_classifier returned, because the in-game pivot
    is the most reliable signal for "you had a winning position."
    """
    if not decryption_v5_data:
        return None

    pivot = detect_pivot_move(decryption_v5_data, user_color=user_color)
    if pivot:
        # For pivot games, also try to find the opponent's preceding
        # mistake/blunder so the anchor can render "Move N they blundered.
        # Move N+1 you gave it back" — the two-move story frame.
        opp_preceding = _find_opp_preceding_mistake(decryption_v5_data, pivot)
        return {
            "move_number": pivot.get("move_number"),
            "move_san": pivot.get("move_san"),
            "cp_loss": pivot.get("cp_loss"),
            "severity": pivot.get("severity"),
            "is_pivot": True,
            "pivot_tier": pivot.get("pivot_tier"),
            "opp_preceding_move_number": (opp_preceding.get("move_number") if opp_preceding else None),
        }

    user_mistakes = [
        m for m in decryption_v5_data
        if m.get("is_user_move") and m.get("is_mistake")
        and (m.get("cp_loss") or 0) >= 50
    ]
    if not user_mistakes:
        return None
    user_mistakes.sort(key=lambda m: -(m.get("cp_loss") or 0))
    chosen = user_mistakes[0]
    return {
        "move_number": chosen.get("move_number"),
        "move_san": chosen.get("move_san"),
        "cp_loss": chosen.get("cp_loss"),
        "severity": chosen.get("severity"),
        "is_pivot": False,
    }


def generate_truth_line(
    *,
    decryption_v5_data: List[Dict],
    game_reason: str,
    game_id: str,
    user_won: bool = False,
    user_color: str = "white",
) -> Optional[Dict[str, str]]:
    """Build the 3-line Truth headline for a finished game.

    Args:
        decryption_v5_data: list of move dicts (V5 schema). Read for
            structural fields only.
        game_reason: output of game_reason_classifier (e.g.
            "threw_winning", "one_move_blunder", "positional"). Drives
            scenario selection.
        game_id: stable hash key for variant selection.
        user_won: skip Truth generation entirely if the user won.

    Returns:
        {"identity": str, "anchor": str, "trigger": str, "scenario": str}
        or None if Truth shouldn't render (user won, no decisive move,
        or validation could not be satisfied even with fallbacks).
    """
    if user_won:
        return None

    critical = pick_critical_move(decryption_v5_data, user_color=user_color)
    if not critical:
        return None

    blunder_count = sum(
        1 for m in (decryption_v5_data or [])
        if m.get("is_user_move") and m.get("severity") == "blunder"
    )

    # Pivot detection overrides classifier output — the in-game flip is
    # the most reliable signal. Tier picks scenario: 'won' → THREW (you
    # had a winning position), 'equalized' → EQUALIZED (you got back to
    # even and gave it back).
    pivot_tier = critical.get("pivot_tier")
    if pivot_tier == PIVOT_TIER_EQUALIZED:
        scenario = SCENARIO_EQUALIZED
    elif critical.get("is_pivot"):
        scenario = SCENARIO_THREW
    else:
        scenario = _classify_scenario(game_reason or "", blunder_count)

    identity = _pick_variant(IDENTITY_BY_SCENARIO[scenario], game_id)
    anchor = _format_anchor(critical, scenario, game_id)
    trigger = _pick_variant(TRIGGER_BY_SCENARIO[scenario], game_id)

    # Apply final budget trim (rare safety net for very long move SANs).
    identity = _shrink_to_budget(identity)
    anchor = _shrink_to_budget(anchor)
    trigger = _shrink_to_budget(trigger)

    ok, reason = validate_truth_block(identity, anchor, trigger)
    if not ok:
        logger.warning(
            f"[truth_line] validation failed for game={game_id} scenario={scenario}: {reason}"
            f" — falling back to safe variants"
        )
        identity = IDENTITY_BY_SCENARIO[scenario][0]
        # Ultra-short anchor fallback that always fits the budget AND
        # passes concreteness (uses "played" + the move SAN).
        move_num = critical.get("move_number") or "?"
        move_san = critical.get("move_san") or ""
        if move_san:
            anchor = f"Move {move_num} — you played {move_san}."
        else:
            anchor = f"Move {move_num} — you missed their threat."
        trigger = TRIGGER_BY_SCENARIO[scenario][0]
        ok2, reason2 = validate_truth_block(identity, anchor, trigger)
        if not ok2:
            logger.error(f"[truth_line] safe fallback also invalid: {reason2}")
            return None

    return {
        "identity": identity,
        "anchor": anchor,
        "trigger": trigger,
        "scenario": scenario,
    }
