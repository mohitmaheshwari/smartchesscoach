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
    #    an opp piece (Parth's m4 Be6 → d5 kicks the bishop). When the
    #    same push ALSO delivers check, it's a fork of king + piece —
    #    Parth fb_e0ac58846b5f: 'pawn forks the king and rook' was
    #    flagged because the framing said only 'kicks the rook' and
    #    missed the king attack on the same move.
    try:
        from services.shape_detectors import simulate_pawn_kicks_piece
        evs = simulate_pawn_kicks_piece(post_opp_fen, user_best_reply_san)
        if evs:
            facts["opp_user_reply_kicks_piece_type"] = evs[0].get("kicked_piece_type")
            facts["opp_user_reply_kicks_piece_square"] = evs[0].get("kicked_square")
            # SAN ending in '+' / '#' is a deliver-check / deliver-mate
            # signal already present at the caller. Combined with a
            # kicks-non-king-piece hit, that's a king+piece fork.
            _r = (user_best_reply_san or "").strip()
            if _r.endswith("+") or _r.endswith("#"):
                facts["opp_user_reply_kicks_with_check"] = True
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


def _is_prophylactic_wing_pawn(board, mv, opp_color) -> bool:
    """True when a wing-pawn push (a/h file) by opp controls a square
    reachable by the USER's same-colour bishop from its home square —
    i.e., the push preempts a future Bg5/Bb5/Bg4/Bb4 development.

    Geometry:
      - h6 (black) controls g5, which is on the c1-h6 diagonal of
        white's dark-squared bishop. If white's c1 bishop is home, h6
        is preempting Bg5.
      - a6 (black) controls b5, on the f1-a6 diagonal of white's light
        bishop. If white's f1 bishop is home, a6 is preempting Bb5
        (Ruy Lopez territory).
      - h3 (white) mirrors against black's c8 bishop / Bg4.
      - a3 (white) mirrors against black's f8 bishop / Bb4
        (Nimzo-Indian territory).

    Args:
      board     : chess.Board BEFORE opp's wing-pawn move was played.
      mv        : the opp's chess.Move for the wing-pawn push.
      opp_color : opp's chess.Color (the side that just played).
    """
    import chess as _ch
    user_color = not opp_color
    to_file = _ch.square_file(mv.to_square)
    to_rank = _ch.square_rank(mv.to_square)
    if to_file not in (0, 7):
        return False
    # The pawn's forward-diagonal attack square (one rank ahead toward
    # enemy, on the inside file).
    forward = -1 if opp_color == _ch.BLACK else 1
    inside_file = to_file - 1 if to_file == 7 else to_file + 1
    attack_rank = to_rank + forward
    if not (0 <= attack_rank <= 7):
        return False
    attacked_sq = _ch.square(inside_file, attack_rank)
    user_bishop_homes = (
        {_ch.C1, _ch.F1} if user_color == _ch.WHITE else {_ch.C8, _ch.F8}
    )
    for sq in board.pieces(_ch.BISHOP, user_color):
        if sq not in user_bishop_homes:
            continue
        sq_file = _ch.square_file(sq)
        sq_rank = _ch.square_rank(sq)
        # Bishop diagonal: |file_diff| == |rank_diff|
        if abs(sq_file - inside_file) == abs(sq_rank - attack_rank):
            return True
    return False


def detect_opp_positional_mistake(
    pre_fen: str,
    opp_played_san: str,
    move_number: Optional[int] = None,
) -> Dict:
    """v80 (2026-05-25) — Mohit: "Opponent's a3 is a mistake. Your
    strongest reply is e5. where is the teaching here?? until you tell,
    why it's a mistake."

    Right. v77's opp punishment detectors describe what USER's reply
    does, not what OPP did wrong. For positional opp mistakes (wing
    pawn pushes in the opening, knights to the rim, queen out early)
    we need a SEPARATE detector class that names what's wrong with
    opp's MOVE — independent of any tactical punishment.

    Self-contained heuristics: takes (pre_fen, opp_played_san) and
    fires for known-suboptimal opening patterns. Doesn't need engine's
    preferred opp move (which isn't readily available for opp moves —
    move_evaluations only stores user-side entries).

    Returns a dict of fact keys (opp_played_*) that R12_blunder.json's
    why_clauses_opp section reads. Empty dict when no heuristic fires.
    """
    if not pre_fen or not opp_played_san:
        return {}
    if move_number is not None and move_number > 15:
        # Opening-phase heuristics only. After m15 the patterns are
        # context-dependent and a flat heuristic produces noise.
        return {}

    facts: Dict = {}
    try:
        import chess as _chess
        board = _chess.Board(pre_fen)
        mv = board.parse_san(opp_played_san)
    except Exception:
        return {}

    piece = board.piece_at(mv.from_square)
    if piece is None:
        return {}

    from_sq = mv.from_square
    to_sq = mv.to_square
    to_file = _chess.square_file(to_sq)  # 0=a … 7=h
    to_rank = _chess.square_rank(to_sq)
    from_rank = _chess.square_rank(from_sq)
    is_capture = board.piece_at(to_sq) is not None

    # ── Heuristic 1: wing pawn push in opening ──────────────────────
    # Opp played an a/h-file pawn (or a 1-square b/g push) when minors
    # weren't fully developed. Slow — doesn't develop, doesn't fight
    # for the center. Mohit's m7 a3 case.
    if piece.piece_type == _chess.PAWN and not is_capture:
        is_wing_pawn = to_file in (0, 7)  # a-file or h-file
        # Count opp's developed minor pieces (knights+bishops off home)
        opp_color = piece.color
        home_rank = 0 if opp_color == _chess.WHITE else 7
        developed = 0
        for sq in board.pieces(_chess.KNIGHT, opp_color):
            if _chess.square_rank(sq) != home_rank:
                developed += 1
        for sq in board.pieces(_chess.BISHOP, opp_color):
            if _chess.square_rank(sq) != home_rank:
                developed += 1
        # v80.1 — gate loosened from `< 3` to `< 4`. With <3 the detector
        # only fired when 2+ minors were still home, missing positions
        # where 3 minors are out + 1 still home + opp pushes wing pawn
        # (game_85bd0169 m7 a3 case: Nc3+Nf3+Be2 out, Bc1 home, white
        # plays a3). With <4 any undeveloped minor triggers — captures
        # the "still incomplete development" voice a coach would use.
        # v97 (2026-05-25) — Tier B Q5: intent-aware prophylactic
        # detection. Mohit 2026-05-25: "the real issue is your detector
        # lacks intent understanding. h6 in Italian is not merely 'wing
        # pawn + no development' — it's preventing Bg5, reducing pin
        # ideas, asking bishop intention." When the wing-pawn push
        # controls a square reachable by opp's user-color bishop from
        # the bishop's home square (h6 vs c1-bishop's g5; a6 vs f1-
        # bishop's b5), the push is preempting a future pin or attack
        # — that's prophylaxis, not lazy development. Skip flagging.
        if is_wing_pawn and developed < 4:
            if not _is_prophylactic_wing_pawn(board, mv, opp_color):
                facts["opp_played_wing_pawn_san"] = opp_played_san
                facts["opp_played_wing_pawn_file"] = "abcdefgh"[to_file]

    # ── Heuristic 2: knight to the rim (a-file/h-file) in opening ──
    if piece.piece_type == _chess.KNIGHT and to_file in (0, 7):
        facts["opp_played_knight_on_rim_san"] = opp_played_san
        facts["opp_played_knight_on_rim_square"] = _chess.square_name(to_sq)

    # ── Heuristic 3: queen out before minors developed ─────────────
    # Opp moved the queen off its home rank when fewer than 2 minors
    # are developed. The classic "queen comes out, gets chased" pattern.
    if piece.piece_type == _chess.QUEEN:
        opp_color = piece.color
        queen_home_rank = 0 if opp_color == _chess.WHITE else 7
        if from_rank == queen_home_rank and to_rank != queen_home_rank:
            # Count developed minors
            home_rank = 0 if opp_color == _chess.WHITE else 7
            developed = 0
            for sq in board.pieces(_chess.KNIGHT, opp_color):
                if _chess.square_rank(sq) != home_rank:
                    developed += 1
            for sq in board.pieces(_chess.BISHOP, opp_color):
                if _chess.square_rank(sq) != home_rank:
                    developed += 1
            if developed < 2:
                facts["opp_played_queen_early_san"] = opp_played_san

    # ── Heuristic 4: un-developing — piece returns to home square ──
    if piece.piece_type in (_chess.KNIGHT, _chess.BISHOP):
        opp_color = piece.color
        home_rank = 0 if opp_color == _chess.WHITE else 7
        if from_rank != home_rank and to_rank == home_rank:
            facts["opp_played_un_developed_piece"] = _chess.piece_name(piece.piece_type)
            facts["opp_played_un_developed_san"] = opp_played_san

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
