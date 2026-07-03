"""
Focus Area Badges — surface a per-move badge in the game-review caption
that names which coaching topic(s) this mistake fits under.

Consumes move_observations (schema v9) which already carries:
  - missed_pattern      (piece_safety / king_safety / missed_tactic / ...)
  - subtype             (simple_hang / ignored_king_attack / missed_fork / ...)
  - time_flag           (impulsive_critical / time_pressure_blunder / ...)
  - severity            (minor / moderate / critical)

Each move can carry ≥1 badge — a fast mistake that also weakens the king
gets BOTH a time badge AND a king_safety badge.

Feeds the review page (frontend/src/components/GameDecryptionV5.jsx).
"""
from typing import Any, Dict, List, Optional


# (emoji, short label, subtype short) per topic
_TOPIC_BADGE = {
    "piece_safety":       ("🎯", "Piece safety",       "piece safety"),
    "king_safety":        ("👑", "King safety",        "king safety"),
    "missed_tactic":      ("⚔",  "Tactical",           "tactic"),
    "tactical_oversight": ("👁", "Tactical oversight", "oversight"),
    "calculation_depth":  ("🧮", "Calculation",        "calculation"),
    "piece_activity":     ("🏃", "Piece activity",     "activity"),
    "opening_knowledge":  "\U0001F4D6 Opening",  # book emoji
    "endgame_technique":  ("♚", "Endgame",             "endgame"),
    "pawn_structure":     ("♟", "Structure",           "structure"),
}
# fix the tuple — Python string above was accidental; use tuple
_TOPIC_BADGE["opening_knowledge"] = ("📖", "Opening", "opening")


_TIME_BADGE = {
    "impulsive_critical":    ("⏱", "Time — impulse",         "played fast"),
    "time_pressure_blunder": ("⏱", "Time — pressure",        "under 30s left"),
    "slow_paralysis":        ("⏱", "Time — paralysis",       "burned clock"),
}


_SUBTYPE_SHORT = {
    "simple_hang":              "hung piece",
    "threat_ignored":           "ignored threat",
    "tactical_seq_loss":        "seq. miscalc",
    "quiet_blunder":            "quiet blunder",
    "small_slip":               "small slip",
    "ignored_king_attack":      "ignored king attack",
    "weakened_shelter":         "weakened shelter",
    "king_in_center":           "king in center",
    "king_walked_into_attack":  "king walked into attack",
    "missed_fork":              "missed fork",
    "missed_pin":               "missed pin",
    "missed_skewer":            "missed skewer",
    "missed_discovered_attack": "missed discovered attack",
    "missed_generic_tactic":    "missed tactic",
    "ignored_forcing_threat":   "ignored forcing threat",
    "overlooked_immediate_reply": "overlooked reply",
    "generic_oversight":        "tactical oversight",
    "shallow_horizon_2ply":     "2-ply blindspot",
    "broken_forcing_sequence":  "broken sequence",
    "generic_calc_gap":         "calculation gap",
    "queen_out_early":          "queen out early",
    "piece_parked_on_start":    "parked piece",
    "tempo_wasted_by_repeat":   "wasted tempo",
    "early_flank_pawn_move":    "early flank pawn",
    "passive_king_in_endgame":  "passive king",
    "passed_pawn_ignored":      "ignored passed pawn",
    "generic_endgame_slip":     "endgame slip",
    "isolated_pawn_created":    "isolated pawn",
    "doubled_pawn_created":     "doubled pawn",
    "backward_pawn_created":    "backward pawn",
    "generic_structure_slip":   "structural slip",
}


def _build_topic_badge(missed_pattern: str, subtype: Optional[str]) -> Optional[Dict[str, Any]]:
    """Badge for the cognitive-gap topic classification. None if it's a
    soft/unclassifiable bucket (unverified_hint, small_slip)."""
    if not missed_pattern:
        return None
    if subtype in ("unverified_hint", "small_slip"):
        return None  # honest silence — don't tag with unreliable buckets
    entry = _TOPIC_BADGE.get(missed_pattern)
    if not entry:
        return None
    emoji, label, short = entry
    subtype_short = _SUBTYPE_SHORT.get(subtype) if subtype else None
    return {
        "emoji": emoji,
        "label": label,
        "subtype_short": subtype_short or short,
        "topic_key": missed_pattern,
        "subtype_key": subtype,
        "kind": "topic",
    }


def _build_time_badge(time_flag: Optional[str], time_spent: Optional[float]) -> Optional[Dict[str, Any]]:
    """Badge for the time-management classification. None if no flag."""
    if not time_flag:
        return None
    entry = _TIME_BADGE.get(time_flag)
    if not entry:
        return None
    emoji, label, short = entry
    if time_spent is not None:
        subtype_short = f"{round(time_spent, 1)}s"
    else:
        subtype_short = short
    return {
        "emoji": emoji,
        "label": label,
        "subtype_short": subtype_short,
        "topic_key": "time_management",
        "subtype_key": time_flag,
        "kind": "time",
    }


async def get_badges_for_game(db, game_id: str, user_id: str) -> Dict[int, List[Dict[str, Any]]]:
    """Return {move_number: [badge, ...]} for the given game.

    Only includes moves where the classifier has real signal. Moves with
    no missed_pattern AND no time_flag return no badges (silent).
    """
    out: Dict[int, List[Dict[str, Any]]] = {}
    async for o in db.move_observations.find(
        {"game_id": game_id, "user_id": user_id},
        {"move_number": 1, "missed_pattern": 1, "subtype": 1,
         "time_flag": 1, "time_spent_seconds": 1, "cp_loss": 1,
         "severity": 1},
    ):
        mn = o.get("move_number")
        if mn is None:
            continue
        badges: List[Dict[str, Any]] = []
        # Topic badge (from missed_pattern + subtype)
        b_topic = _build_topic_badge(o.get("missed_pattern"), o.get("subtype"))
        if b_topic:
            b_topic["cp_loss"] = o.get("cp_loss")
            b_topic["severity"] = o.get("severity")
            badges.append(b_topic)
        # Time badge (from time_flag)
        b_time = _build_time_badge(o.get("time_flag"), o.get("time_spent_seconds"))
        if b_time:
            b_time["cp_loss"] = o.get("cp_loss")
            b_time["severity"] = o.get("severity")
            badges.append(b_time)
        if badges:
            out[mn] = badges
    return out
