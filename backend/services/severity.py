"""
severity — single canonical move-severity evaluator.

Mohit 2026-05-25: "If move classification, caption gating, and severity
rendering use different thresholds, your entire system becomes incoherent.
This should be unified centrally: one canonical severity evaluator,
imported everywhere, never duplicated."

Before this module, three sources of severity thresholds existed and
disagreed:

  V5 service (game_decryption_v5_service.py, inline):
    user side: cp<30 good, <100 inaccuracy, <250 mistake, else blunder
    opp side : cp<50 context, <100 opp_inaccuracy, <250 opp_mistake, else opp_blunder
    — no "serious" tier; opp threshold for inaccuracy floor 50 vs user 30

  R12_blunder.json severity_tiers (v79.3):
    cp<100 inaccuracy, <250 mistake, <400 serious, ≥400 blunder

  R_PROMOTED_basic_mistake.json severity_tiers:
    cp<250 mistake, <400 serious, ≥400 blunder
    — no inaccuracy, no good

This module is the new source of truth. The thresholds below are the
ones every consumer must agree on. JSON consumers stay JSON for the
JSON predicate engine — but their numeric boundaries MUST match
SEVERITY_THRESHOLDS below. Run `validate_json_severity_tiers()` to
audit (used by tests + the regen scripts).

Tier semantics (Mohit-locked, 2026-05-25):
  good        : <30cp  — within human-irrelevant noise of best
  inaccuracy  : 30-99  — small drift, only worth mentioning if there's
                          a concrete why (tactical / curriculum / etc.)
  mistake     : 100-249 — meaningful eval drop
  serious     : 250-399 — real chunk of advantage lost
  blunder     : ≥400    — game-altering

The mate sentinel (cp_loss ≥ 3000) is a special case: the move walked
into mate. Always classified as blunder regardless of nominal cp_loss
(Stockfish encodes mate as huge positive/negative cp).

Q1 follow-up (relative severity scaling) lives in a separate function
`classify_severity_practical()` — coming next. This base function
gives the structural tier; the practical wrapper layers win-probability
delta on top to downgrade "winning → still winning" cases.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# Canonical thresholds (Mohit-locked 2026-05-25).
# Order: lower bounds for each tier, ascending.
SEVERITY_THRESHOLDS = {
    "inaccuracy": 30,
    "mistake":    100,
    "serious":    250,
    "blunder":    400,
}

# Mate sentinel — Stockfish encodes mate as ~10000cp. Catch any value
# this large as a mate-walked-into-by-played-move signal regardless
# of the nominal cp_loss number.
MATE_SENTINEL_CP = 3000

# Catastrophic cp_loss floor — practical-severity softening is disabled
# above this threshold. See classify_severity_practical() docstring.
CATASTROPHIC_CP_LOSS_FLOOR = 1000

# Canonical tier list (lowest severity → highest).
TIER_ORDER = ["good", "inaccuracy", "mistake", "serious", "blunder"]


@dataclass(frozen=True)
class SeverityClassification:
    """The full severity story for one move.

    tier            : canonical tier name ("good" / "inaccuracy" / etc.)
                      independent of which side moved.
    user_facing_tier: the tier with "opp_" prefix added when the mover
                      isn't the user (e.g. "opp_mistake"). Special: "good"
                      stays "good" for opp; "inaccuracy" becomes
                      "opp_inaccuracy". Convention matches the existing
                      caption pipeline.
    cp_loss         : the raw cp_loss the classification was based on.
    walked_into_mate: True when the played move walked into a mate
                      sequence (cp_loss past MATE_SENTINEL_CP).
    """
    tier: str
    user_facing_tier: str
    cp_loss: int
    walked_into_mate: bool


def classify_severity(
    cp_loss: int,
    *,
    mover_is_user: bool,
    user_post_eval_cp: Optional[int] = None,
) -> SeverityClassification:
    """Map cp_loss → canonical severity tier.

    Args:
      cp_loss          : centipawn loss for THIS move from the mover's POV.
                         Always non-negative.
      mover_is_user    : True when the user played the move; False for opp.
                         Affects only `user_facing_tier` (prefixes "opp_").
      user_post_eval_cp: optional user-POV eval after the move. Used only
                         for the mate-walked-into check: a user_post_eval
                         <= -MATE_SENTINEL_CP means the user just walked
                         into a mate, regardless of cp_loss. (V5 had this
                         escape hatch inline; preserving it here.)

    Returns:
      A SeverityClassification with tier + user_facing_tier + flags.

    Edge cases:
      - cp_loss < 0 normalised to 0 (engine never gives negative loss to
        the played move; defensive).
      - Mate-walked-into: tier = "blunder" regardless of nominal cp_loss.
        This matches the existing V5 service behaviour for the "stored
        cp_loss is small but eval is mate" case (fb_a9ac9f02affa).
    """
    cp_loss = max(int(cp_loss or 0), 0)
    walked_into_mate = (
        user_post_eval_cp is not None
        and user_post_eval_cp <= -MATE_SENTINEL_CP
    )

    if walked_into_mate:
        tier = "blunder"
    elif cp_loss >= SEVERITY_THRESHOLDS["blunder"]:
        tier = "blunder"
    elif cp_loss >= SEVERITY_THRESHOLDS["serious"]:
        tier = "serious"
    elif cp_loss >= SEVERITY_THRESHOLDS["mistake"]:
        tier = "mistake"
    elif cp_loss >= SEVERITY_THRESHOLDS["inaccuracy"]:
        tier = "inaccuracy"
    else:
        tier = "good"

    if mover_is_user:
        user_facing = tier
    else:
        # opp-prefix convention from the existing caption pipeline.
        # "good" → "context" (a fine opp move worth narrating but not
        # critiquing); other tiers gain the "opp_" prefix.
        if tier == "good":
            user_facing = "context"
        else:
            user_facing = f"opp_{tier}"

    return SeverityClassification(
        tier=tier,
        user_facing_tier=user_facing,
        cp_loss=cp_loss,
        walked_into_mate=walked_into_mate,
    )


def win_prob_from_cp(eval_cp: int) -> float:
    """Convert engine cp eval (mover-POV) to win-probability in [0,1].

    Uses the Stockfish-style logistic: wp = 1 / (1 + exp(-cp/400)).
    Caps inputs at ±5000 to avoid overflow on mate sentinels.
    """
    cp = max(min(int(eval_cp or 0), 5000), -5000)
    try:
        return 1.0 / (1.0 + math.exp(-cp / 400.0))
    except OverflowError:
        return 0.5


# Decisiveness thresholds — cp eval boundaries that define "winning"
# vs "balanced" vs "losing" from MOVER's POV.
DECISIVENESS_WINNING_CP = 200
DECISIVENESS_LOSING_CP = -200


def _decisiveness_state(eval_cp: int) -> str:
    """Bucket an eval into 'winning' / 'balanced' / 'losing' from mover POV."""
    if eval_cp >= DECISIVENESS_WINNING_CP:
        return "winning"
    if eval_cp <= DECISIVENESS_LOSING_CP:
        return "losing"
    return "balanced"


# Practical tier thresholds — based on |Δwin_prob| from mover POV.
# Mohit 2026-05-25 examples to honour:
#   +4.0 → +3.3  (Δwp ~ 0.045) → "good"/"inaccuracy" — soften
#   +2.0 → +0.2  (Δwp ~ 0.219) → "mistake" — the flip out of winning
#   +6.0 → +2.0  (Δwp ~ 0.115) → "inaccuracy" if stayed winning
# These thresholds + the decisiveness-change overlay below should
# match those intuitions.
PRACTICAL_WP_THRESHOLDS = {
    "inaccuracy": 0.05,
    "mistake":    0.15,
    "serious":    0.30,
    "blunder":    0.50,
}


@dataclass(frozen=True)
class PracticalSeverity:
    """Practical severity adds win-probability context to the canonical tier.

    Fields:
      practical_tier      : tier derived from |Δwin_prob| (good /
                            inaccuracy / mistake / serious / blunder).
      canonical_tier      : tier from raw cp_loss (the v92 evaluator).
      mover_winprob_before: mover-POV win-probability before the move.
      mover_winprob_after : mover-POV win-probability after the move.
      winprob_delta       : after - before (negative if move hurts mover).
      state_before        : 'winning' / 'balanced' / 'losing' (mover POV).
      state_after         : same, post-move.
      decisiveness_changed: True when state_before != state_after AND
                            state_before == 'winning' (the most pedagogically
                            important transition — losing the winning edge).
      stayed_winning      : True when both states are 'winning'. The
                            softening signal — caption can downgrade
                            the harshness even on mid-cp losses.
    """
    practical_tier: str
    canonical_tier: str
    mover_winprob_before: float
    mover_winprob_after: float
    winprob_delta: float
    state_before: str
    state_after: str
    decisiveness_changed: bool
    stayed_winning: bool


def classify_severity_practical(
    cp_loss: int,
    *,
    mover_is_user: bool,
    mover_is_white: bool,
    eval_before_cp: Optional[int],
    eval_after_cp: Optional[int],
) -> PracticalSeverity:
    """Compute practical severity from cp_loss + eval trajectory.

    Mohit 2026-05-25 Tier B Q1:
      "don't purely threshold on cp_loss. combine: eval_before, eval_after,
      win-prob delta, tactical-collapse presence, and 'position simplification
      risk.' Use relative severity scaling."

    This function delivers the win-prob delta + decisiveness-change axes.
    Tactical-collapse and simplification-risk are NOT covered yet
    (require pv inspection — future work).

    The practical tier is computed from |Δwin_prob| from MOVER's POV,
    NOT from cp_loss directly. This naturally softens "+4.0 → +3.3"
    (small Δwp) and emphasises "+2.0 → +0.2" (large Δwp out of winning).

    Args:
      cp_loss        : mover-POV centipawn loss (always ≥0).
      mover_is_user  : True if the user played the move.
      mover_is_white : True if the mover is white. Used to sign-flip the
                       engine eval (which is always white-POV in our data)
                       into mover POV.
      eval_before_cp : engine eval BEFORE the move, white POV.
      eval_after_cp  : engine eval AFTER the move, white POV.

    Returns a PracticalSeverity dict with both tiers + winprob trajectory.
    """
    canonical = classify_severity(cp_loss, mover_is_user=mover_is_user).tier

    # Default neutral practical severity if evals missing.
    if eval_before_cp is None or eval_after_cp is None:
        return PracticalSeverity(
            practical_tier=canonical,
            canonical_tier=canonical,
            mover_winprob_before=0.5,
            mover_winprob_after=0.5,
            winprob_delta=0.0,
            state_before="balanced",
            state_after="balanced",
            decisiveness_changed=False,
            stayed_winning=False,
        )

    # Flip evals to MOVER POV (engine evals in our data are white POV).
    sign = 1 if mover_is_white else -1
    mover_eval_before = sign * int(eval_before_cp)
    mover_eval_after = sign * int(eval_after_cp)

    wp_before = win_prob_from_cp(mover_eval_before)
    wp_after = win_prob_from_cp(mover_eval_after)
    dwp = wp_after - wp_before

    state_before = _decisiveness_state(mover_eval_before)
    state_after = _decisiveness_state(mover_eval_after)
    # decisiveness_changed = mover's state WORSENED across the move:
    #   winning → balanced/losing  OR  balanced → losing
    # When this happens the move is practically more important than
    # raw Δwp alone suggests — the mover crossed a decisiveness
    # boundary, not just lost some win-probability. Bumps practical
    # tier up by one level.
    _ranks = {"winning": 2, "balanced": 1, "losing": 0}
    decisiveness_changed = _ranks[state_after] < _ranks[state_before]
    stayed_winning = (state_before == "winning" and state_after == "winning")

    # Map |Δwp| to a practical tier.
    abs_dwp = abs(dwp)
    if abs_dwp >= PRACTICAL_WP_THRESHOLDS["blunder"]:
        practical = "blunder"
    elif abs_dwp >= PRACTICAL_WP_THRESHOLDS["serious"]:
        practical = "serious"
    elif abs_dwp >= PRACTICAL_WP_THRESHOLDS["mistake"]:
        practical = "mistake"
    elif abs_dwp >= PRACTICAL_WP_THRESHOLDS["inaccuracy"]:
        practical = "inaccuracy"
    else:
        practical = "good"

    # Decisiveness-change overlay (Mohit 2026-05-25 examples):
    #   "+4.0 → +3.3 = 'misses something stronger'" (stayed winning, soft)
    #   "+2.0 → +0.2 = serious mistake" (winning → not winning, BIG bump)
    #   "+6 → +2 no tactic = 'lets the position become messy'" (still winning)
    # Lost-winning is the most important transition — bump TWO levels.
    # Other worsenings (balanced → losing) bump ONE level.
    if decisiveness_changed:
        bump = 2 if state_before == "winning" else 1
        tier_idx = TIER_ORDER.index(practical)
        practical = TIER_ORDER[min(tier_idx + bump, len(TIER_ORDER) - 1)]

    # Stayed-losing override (Mohit feedback fb_f1025f698252, 2026-05-26):
    # practical-severity softening was designed for stayed-winning /
    # balanced cases (small Δwp shouldn't read 'mistake' when you're
    # still winning by +3). Applied to stayed-losing it under-reports —
    # a player who's already losing -4 and drops another 218cp ends up
    # with a tiny Δwp (their win-prob was near zero anyway), so the
    # logic softens 'mistake' to 'inaccuracy'. But the player DID make
    # a real mistake and should hear it. Fall back to canonical when
    # state stayed losing AND no decisiveness change (the decisiveness
    # bump path, e.g. balanced→losing, stays in effect via the bump
    # block above).
    if state_after == "losing" and not decisiveness_changed:
        practical = canonical

    # Cap practical tier at canonical (we never make a move look WORSE
    # than its cp_loss-based classification) — EXCEPT when the move
    # lost the winning state. In that case the move IS practically
    # more important than its cp_loss suggests (Mohit "+2.0 -> +0.2 =
    # serious mistake" — cp_loss=180 is canonically mistake-tier, but
    # losing the winning edge bumps practical importance higher).
    # Allow practical = canonical + 1 in lost-winning cases.
    can_idx = TIER_ORDER.index(canonical)
    prac_idx = TIER_ORDER.index(practical)
    lost_winning = (
        decisiveness_changed and state_before == "winning"
    )
    max_allowed_idx = can_idx + 1 if lost_winning else can_idx
    max_allowed_idx = min(max_allowed_idx, len(TIER_ORDER) - 1)
    if prac_idx > max_allowed_idx:
        practical = TIER_ORDER[max_allowed_idx]

    # Catastrophic-cpl floor (Mohit 2026-05-28, game 2d7ade57 m31 Rxf4
    # cp_loss=8774): when you're winning so heavily that any move keeps
    # the win-prob near 1.0, the Δwp is tiny even for absurd cp_loss
    # values. The stayed-winning logic above softens practical to 'good'
    # in that case, and the cap above caps it at canonical = 'blunder'
    # but doesn't raise it from 'good'. Result: a near-mate move is
    # framed as "fine, still winning". Honest framing requires that
    # cp_loss this large CANNOT be softened below canonical.
    # Threshold = 1000cp (10 pawns of evaluation lost) — well above the
    # canonical blunder threshold of 400, conservative enough that
    # normal "stayed winning" softening (cp_loss 100-500 cases) is
    # unaffected.
    if cp_loss >= CATASTROPHIC_CP_LOSS_FLOOR:
        if TIER_ORDER.index(practical) < TIER_ORDER.index(canonical):
            practical = canonical

    return PracticalSeverity(
        practical_tier=practical,
        canonical_tier=canonical,
        mover_winprob_before=wp_before,
        mover_winprob_after=wp_after,
        winprob_delta=dwp,
        state_before=state_before,
        state_after=state_after,
        decisiveness_changed=decisiveness_changed,
        stayed_winning=stayed_winning,
    )


def validate_json_severity_tiers(file_to_tier_map: dict) -> list:
    """Audit helper: given a {file_name: severity_tier_list} dict, check
    that every JSON file's thresholds match SEVERITY_THRESHOLDS.

    Each severity_tier_list is a list of dicts shaped like:
      [{"when": {"cp_loss": {"gte": 400}}, "tier": "blunder"},
       {"when": {"cp_loss": {"gte": 250}}, "tier": "serious"},
       ...]
    The terminal "default" entry (no when block) is allowed.

    Returns a list of (file_name, mismatch_message) tuples. Empty list
    means everything matches.
    """
    out = []
    for fname, tiers in file_to_tier_map.items():
        # Build {tier_name: gte_threshold} from the JSON entries.
        json_thresholds: dict = {}
        for entry in tiers:
            tier = entry.get("tier")
            when = entry.get("when") or {}
            cp = when.get("cp_loss") or {}
            gte = cp.get("gte")
            if tier and gte is not None:
                json_thresholds[tier] = gte
        # Compare against canonical.
        for tier_name, canonical in SEVERITY_THRESHOLDS.items():
            if tier_name in json_thresholds:
                if json_thresholds[tier_name] != canonical:
                    out.append((
                        fname,
                        f"tier={tier_name} json gte={json_thresholds[tier_name]} "
                        f"≠ canonical {canonical}"
                    ))
    return out
