"""Pattern catalog loader + caption_facts → pattern_ids resolver.

The catalog itself lives in `backend/data/pattern_catalog.json` (one JSON
entry per pattern with human_name/short_description/family). Voice is
Mohit's domain; this module only owns the LOOKUP path: given the
caption_facts dict produced for a move, which pattern_ids fired?

Used by:
  - services/pattern_event_logger.py — when a user move triggers a
    detector, log a miss event keyed on the resolved pattern_id(s).
  - future P2 phase 2 — when detectors run on user GOOD moves too,
    same resolver decides whether to log a hit event.

Design notes:
  * Resolver is pure: in → caption_facts (dict), out → list of pattern
    IDs that are present in the facts. Order matches the catalog's
    priority intuition (mate > piece capture > tactical > positional)
    but a position can fire multiple at once and we return all of them.
  * Catalog read once at import time and cached. Reload via
    `_refresh_catalog()` if you edit pattern_catalog.json in dev.
  * pattern_ids are STABLE — once a pattern ships and event docs use
    its ID, the ID must never change. Only the displayed name/text
    can be tuned.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "pattern_catalog.json",
)

_catalog_cache: Optional[Dict] = None


def _refresh_catalog() -> Dict:
    global _catalog_cache
    try:
        with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
            _catalog_cache = json.load(f)
    except Exception as e:
        logger.warning(f"[pattern_catalog] failed to load: {e}")
        _catalog_cache = {"patterns": {}}
    return _catalog_cache


def get_catalog() -> Dict:
    if _catalog_cache is None:
        return _refresh_catalog()
    return _catalog_cache


def get_pattern(pattern_id: str) -> Optional[Dict]:
    """Return the catalog entry for a pattern_id, or None if unknown."""
    return get_catalog().get("patterns", {}).get(pattern_id)


def resolve_pattern_ids(caption_facts: Dict) -> List[str]:
    """Given a caption_facts dict from V5 generation, return the list of
    pattern_ids that fired in that position. Empty list when no
    catalog-tracked pattern was present.

    The mapping reflects which detector populated which fact key. When
    a fact key is set with a non-empty value, the corresponding
    pattern fired.
    """
    if not caption_facts:
        return []
    ids: List[str] = []

    # Tactic detector (missed_tactic in caption_rules.py) — highest-
    # priority why-clauses, so log these first.
    kind = caption_facts.get("missed_tactic_kind")
    if kind == "mate":
        ids.append("missed_mate")
    elif kind == "piece_capture":
        ids.append("missed_piece")

    # Shape detector (clearance_for_attack)
    if caption_facts.get("missed_clearance_attack_square"):
        ids.append("clearance_for_attack")

    # Shape detector (clearance_then_check / Légal's family)
    if caption_facts.get("missed_clearance_then_check_follow_up_san"):
        ids.append("clearance_then_check")

    # Queen fork sub-kinds
    qfk = caption_facts.get("queen_fork_sub_kind")
    if qfk == "capture_with_check":
        ids.append("queen_fork_capture_with_check")
    elif qfk == "fork":
        ids.append("queen_fork")

    # Attack with tempo
    if caption_facts.get("attack_with_tempo_piece"):
        ids.append("attack_with_tempo")

    # Endgame loose pawn sub-kinds
    elk = caption_facts.get("endgame_loose_pawn_sub_kind")
    if elk == "direct_capture":
        ids.append("endgame_loose_pawn_capture")
    elif elk == "attack":
        ids.append("endgame_loose_pawn_attack")

    # Opening-principle detectors
    if caption_facts.get("un_developing_piece"):
        ids.append("un_developing")
    if caption_facts.get("defensive_pawn_user_san"):
        ids.append("defensive_pawn_push")
    if caption_facts.get("knight_outpost_destination"):
        ids.append("knight_outpost")
    if caption_facts.get("stop_opp_pawn_blocking_san"):
        ids.append("stop_opp_pawn")
    if caption_facts.get("knight_on_rim_square"):
        ids.append("knight_on_rim")
    if caption_facts.get("pawn_kicks_piece_square"):
        ids.append("pawn_kicks_piece")

    # Tactical/positional helpers
    if caption_facts.get("active_defense_defended_square"):
        ids.append("active_defense")
    if caption_facts.get("same_piece_better_extra_square"):
        ids.append("same_piece_better_square")
    if caption_facts.get("discovered_vac_exposed_square"):
        ids.append("discovered_vacating_check")

    # Principle detector — blocked own pawn
    if caption_facts.get("blocked_pawn_file"):
        ids.append("blocked_own_pawn")

    # Shape: king_pawn_lifted (kingside attack geometry)
    if caption_facts.get("shape_pattern_id") == "king_pawn_lifted":
        ids.append("king_pawn_lifted")

    # Trap context (v69) — the user missed punishing a known trap
    if caption_facts.get("trap_context_name"):
        ids.append("trap_punishment")

    return ids


# v73 (2026-05-23) — Pattern IDs eligible for HIT detection.
#
# Two categories of detectors live in the codebase:
#   - POSITION-BASED — pattern presence depends ONLY on (fen, best_move).
#     If the engine's best move triggers the pattern at this position,
#     the user "hit" it by playing best_move. Listed below.
#   - CONTRASTIVE — pattern is defined as user move ≠ engine's best in a
#     specific way (e.g. "user retreated a piece"). Inherently a miss
#     concept; we never log a hit for them. Excluded.
#
# Mohit 2026-05-23 — P2 phase 2: enables "you played the pattern move"
# tracking on user GOOD moves so insights can say "you understand X" /
# "you've got this 3 games in a row" instead of only miss counts.
_HIT_ELIGIBLE_PATTERN_IDS = {
    "missed_mate",                       # forced mate in PV
    "missed_piece",                      # clean piece win in PV
    "clearance_for_attack",
    "clearance_then_check",
    "queen_fork_capture_with_check",
    "queen_fork",
    "attack_with_tempo",
    "endgame_loose_pawn_capture",
    "endgame_loose_pawn_attack",
    "knight_outpost",
    "active_defense",
    "discovered_vacating_check",
    "pawn_kicks_piece",
    "king_pawn_lifted",
    "trap_punishment",
}

# Patterns intentionally excluded from hit detection (contrastive).
_HIT_INELIGIBLE_PATTERN_IDS = {
    "un_developing",
    "defensive_pawn_push",
    "same_piece_better_square",
    "stop_opp_pawn",
    "knight_on_rim",
    "blocked_own_pawn",
}


def is_hit_eligible(pattern_id: str) -> bool:
    """True iff this pattern can be 'hit' by playing the engine's best
    move (vs. only being a 'miss' when the user diverges)."""
    return pattern_id in _HIT_ELIGIBLE_PATTERN_IDS


def detect_opp_move_punishments(
    post_opp_fen: str,
    user_best_reply_san: str,
    post_opp_pv_after_best: Optional[List[str]] = None,
    user_color: Optional[str] = None,
    post_opp_eval_before_cp: Optional[int] = None,
) -> Dict:
    """v77 (2026-05-23) — Mohit + Parth: opp-mistake explanation layer.

    Symmetric to the user-mistake detector path. When an opp move is
    classified as a mistake by cp_loss, we now analyze USER's best
    reply against the POST-OPP position to surface a concrete WHY in
    the caption. The same shape detectors used for user mistakes apply
    here unchanged — they take (fen, best_move) and don't care whose
    perspective; what changes is the INTERPRETATION (the move + facts
    describe the user's punishment, not the user's mistake).

    Returns a dict of opp-prefixed fact keys (so the user-mistake path
    can't collide with this) that R12_blunder.json's why_clauses_opp
    section reads.

    Detectors run:
      - simulate_pawn_kicks_piece — user's reply pushes a pawn that
        attacks an opp piece (e.g. Parth's m4 Be6 → user's d5 kicks
        the bishop).
      - simulate_attack_with_tempo — user's reply attacks opp piece
        with tempo.
      - simulate_queen_fork_with_check — user's reply queen-forks
        king + piece.
      - simulate_endgame_loose_pawn_grab — user's reply grabs / eyes
        an undefended opp pawn in the endgame.
      - simulate_clearance_for_attack / clearance_then_check —
        user's reply opens lines for tactical follow-ups.
      - detect_missed_tactic — user's reply leads to mate or piece-win
        in the PV (uses post_opp_pv_after_best).

    Contrastive detectors (un_developing, knight_on_rim, etc.) are
    intentionally excluded — they're definitionally about USER moves
    diverging from engine; they don't fit the symmetric opp path.
    """
    if not post_opp_fen or not user_best_reply_san:
        return {}

    facts: Dict = {}
    pv = post_opp_pv_after_best or []

    # 1. pawn_kicks_piece — user's reply is a pawn push that kicks
    #    an opp piece (Parth's m4 Be6 → d5 kicks the bishop).
    try:
        from services.shape_detectors import simulate_pawn_kicks_piece
        evs = simulate_pawn_kicks_piece(post_opp_fen, user_best_reply_san)
        if evs:
            facts["opp_user_reply_kicks_piece_type"] = evs[0].get("kicked_piece_type")
            facts["opp_user_reply_kicks_piece_square"] = evs[0].get("kicked_square")
    except Exception:
        pass

    # 2. attack_with_tempo — user's reply attacks opp non-king piece
    #    + opp's forced retreat is in PV.
    try:
        from services.shape_detectors import simulate_attack_with_tempo
        evs = simulate_attack_with_tempo(post_opp_fen, user_best_reply_san, pv)
        if evs:
            facts["opp_user_reply_attack_piece"] = evs[0].get("attacked_piece_type")
            facts["opp_user_reply_attack_square"] = evs[0].get("attacked_square")
    except Exception:
        pass

    # 3. queen_fork_with_check — user's queen forks king + piece.
    try:
        from services.shape_detectors import simulate_queen_fork_with_check
        evs = simulate_queen_fork_with_check(post_opp_fen, user_best_reply_san)
        if evs and evs[0].get("sub_kind"):
            facts["opp_user_reply_queen_fork_sub_kind"] = evs[0].get("sub_kind")
            facts["opp_user_reply_queen_fork_secondary_piece"] = evs[0].get("secondary_piece")
            facts["opp_user_reply_queen_fork_secondary_square"] = evs[0].get("secondary_square")
    except Exception:
        pass

    # 4. endgame_loose_pawn_grab — user's reply grabs/attacks undefended pawn.
    try:
        from services.shape_detectors import simulate_endgame_loose_pawn_grab
        evs = simulate_endgame_loose_pawn_grab(post_opp_fen, user_best_reply_san)
        if evs and evs[0].get("sub_kind"):
            facts["opp_user_reply_endgame_pawn_sub_kind"] = evs[0].get("sub_kind")
            facts["opp_user_reply_endgame_pawn_square"] = evs[0].get("pawn_square")
    except Exception:
        pass

    # 5. clearance_then_check / clearance_for_attack — user's reply opens
    #    a line for queen/slider to attack king or key target.
    try:
        from services.shape_detectors import simulate_clearance_then_check
        evs = simulate_clearance_then_check(post_opp_fen, user_best_reply_san)
        if evs and evs[0].get("follow_up_san"):
            facts["opp_user_reply_clearance_follow_up_san"] = evs[0].get("follow_up_san")
            facts["opp_user_reply_clearance_piece"] = evs[0].get("clearer_piece_type")
    except Exception:
        pass
    try:
        from services.shape_detectors import simulate_clearance_for_attack
        evs = simulate_clearance_for_attack(post_opp_fen, user_best_reply_san)
        if evs:
            tgts = evs[0].get("targets") or []
            if tgts:
                facts["opp_user_reply_clearance_attack_square"] = tgts[0]
                facts["opp_user_reply_clearance_attacker_piece"] = evs[0].get("clearer_piece_type")
    except Exception:
        pass

    # 6. missed_tactic — user's reply leads to mate or wins a piece
    #    in the PV. Highest-leverage: when user has forced mate after
    #    opp's blunder, we should say so.
    try:
        from services.best_move_tactic_detector import detect_missed_tactic
        tactic = detect_missed_tactic(
            fen_before=post_opp_fen,
            best_move_san=user_best_reply_san,
            pv_after_best=pv,
            user_color=user_color or "white",
            eval_before_cp=post_opp_eval_before_cp,
        )
        if tactic:
            facts["opp_user_reply_tactic_kind"] = tactic.get("kind")
            facts["opp_user_reply_tactic_target_piece"] = tactic.get("piece_type")
            facts["opp_user_reply_tactic_target_square"] = tactic.get("square")
            if tactic.get("ply"):
                facts["opp_user_reply_tactic_ply"] = tactic.get("ply")
    except Exception:
        pass

    return facts


def detect_position_patterns(
    fen_before: str,
    best_move_san: str,
    pv_after_best: Optional[List[str]] = None,
    user_color: Optional[str] = None,
    eval_before_cp: Optional[int] = None,
    shape_pattern_id: Optional[str] = None,
    trap_context_name: Optional[str] = None,
) -> List[str]:
    """Pattern presence at a position — independent of what the user
    actually played. Used by P2 phase 2 hit detection: when the user
    plays best_move, this returns the patterns they 'hit' by playing it.

    Only runs POSITION-BASED detectors (see _HIT_ELIGIBLE_PATTERN_IDS).
    Contrastive detectors (un_developing, knight_on_rim, etc.) are
    inherently miss concepts and excluded.

    Imports detectors lazily so a missing optional service doesn't
    break the caller; each detector is wrapped in a try/except so one
    bad detector doesn't kill the rest.
    """
    if not fen_before or not best_move_san:
        return []

    synthetic_facts: Dict = {}

    # missed_tactic: mate / piece_capture
    try:
        from services.best_move_tactic_detector import detect_missed_tactic
        tactic = detect_missed_tactic(
            fen_before=fen_before,
            best_move_san=best_move_san,
            pv_after_best=pv_after_best or [],
            user_color=user_color or "white",
            eval_before_cp=eval_before_cp,
        )
        if tactic:
            synthetic_facts["missed_tactic_kind"] = tactic.get("kind")
    except Exception:
        pass

    # clearance_for_attack
    try:
        from services.shape_detectors import simulate_clearance_for_attack
        evs = simulate_clearance_for_attack(fen_before, best_move_san)
        if evs:
            targets = evs[0].get("targets") or []
            if targets:
                synthetic_facts["missed_clearance_attack_square"] = targets[0]
    except Exception:
        pass

    # clearance_then_check
    try:
        from services.shape_detectors import simulate_clearance_then_check
        evs = simulate_clearance_then_check(fen_before, best_move_san)
        if evs and evs[0].get("follow_up_san"):
            synthetic_facts["missed_clearance_then_check_follow_up_san"] = evs[0].get("follow_up_san")
    except Exception:
        pass

    # attack_with_tempo
    try:
        from services.shape_detectors import simulate_attack_with_tempo
        evs = simulate_attack_with_tempo(fen_before, best_move_san, pv_after_best or [])
        if evs and evs[0].get("attacked_piece_type"):
            synthetic_facts["attack_with_tempo_piece"] = evs[0].get("attacked_piece_type")
    except Exception:
        pass

    # queen_fork_with_check
    try:
        from services.shape_detectors import simulate_queen_fork_with_check
        evs = simulate_queen_fork_with_check(fen_before, best_move_san)
        if evs and evs[0].get("sub_kind"):
            synthetic_facts["queen_fork_sub_kind"] = evs[0].get("sub_kind")
    except Exception:
        pass

    # endgame_loose_pawn_grab
    try:
        from services.shape_detectors import simulate_endgame_loose_pawn_grab
        evs = simulate_endgame_loose_pawn_grab(fen_before, best_move_san)
        if evs and evs[0].get("sub_kind"):
            synthetic_facts["endgame_loose_pawn_sub_kind"] = evs[0].get("sub_kind")
    except Exception:
        pass

    # knight_outpost
    try:
        from services.shape_detectors import simulate_knight_outpost
        evs = simulate_knight_outpost(fen_before, best_move_san)
        if evs and evs[0].get("knight_destination"):
            synthetic_facts["knight_outpost_destination"] = evs[0].get("knight_destination")
    except Exception:
        pass

    # active_defense
    try:
        from services.shape_detectors import simulate_active_defense
        evs = simulate_active_defense(fen_before, best_move_san)
        if evs and evs[0].get("defended_square"):
            synthetic_facts["active_defense_defended_square"] = evs[0].get("defended_square")
    except Exception:
        pass

    # discovered_attack_vacating_check
    try:
        from services.shape_detectors import simulate_discovered_attack_vacating_check
        evs = simulate_discovered_attack_vacating_check(fen_before, best_move_san)
        if evs and evs[0].get("exposed_square"):
            synthetic_facts["discovered_vac_exposed_square"] = evs[0].get("exposed_square")
    except Exception:
        pass

    # pawn_kicks_piece
    try:
        from services.shape_detectors import simulate_pawn_kicks_piece
        evs = simulate_pawn_kicks_piece(fen_before, best_move_san)
        if evs and evs[0].get("kicked_square"):
            synthetic_facts["pawn_kicks_piece_square"] = evs[0].get("kicked_square")
    except Exception:
        pass

    # Shape patterns + trap_context: caller passes these in (they're
    # computed elsewhere in V5 generation, no point re-running here).
    if shape_pattern_id:
        synthetic_facts["shape_pattern_id"] = shape_pattern_id
    if trap_context_name:
        synthetic_facts["trap_context_name"] = trap_context_name

    return [p for p in resolve_pattern_ids(synthetic_facts) if is_hit_eligible(p)]
