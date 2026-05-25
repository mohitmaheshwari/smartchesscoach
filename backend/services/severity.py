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
