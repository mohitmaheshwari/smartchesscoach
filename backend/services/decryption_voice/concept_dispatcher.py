"""
Concept dispatcher — runs the existing chess_brain detector registry
against a moment, picks the dominant detected pattern, renders a
deterministic caption from concept_templates.

This replaces the LLM call in the candidate-builder caption path. The
detectors already exist (services/chess_brain/detector_registry.py and
advanced_detectors.py). This module is the thin glue: position →
detector run → priority pick → caption.

No LLM. No hallucination. Every word in the caption comes from
detector facts or template constants.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import chess

from .concept_templates import render_caption, has_template

logger = logging.getLogger(__name__)


# ── Local detector — WALKED_INTO_MATE ────────────────────────────────
# Fires when the user's move allows the opponent forced mate in 1-2.
# Lives in the dispatcher (not chess_brain registry) because it needs
# the user's move to detect mate-AGAINST-the-user; the registry's
# missed_mate detector is the inverse (user MISSED mate FOR them).

def _detect_walked_into_mate(
    board: chess.Board,
    user_move_san: str,
    best_move_san: Optional[str],
    max_ply: int = 2,
    engine_mate_in_after: Optional[int] = None,
) -> Optional[Dict]:
    """If user's move allows forced mate against them, return facts;
    else None.

    Two-tier detection:

    1. Engine truth — if Stockfish's mate_in_after is set and positive,
       that's the truth. Trust the engine over local search; it covers
       mate-in-3+ which our local mate-in-2 search misses.

    2. Local search fallback — for moments where engine mate data isn't
       available, search for mate-in-1 and mate-in-2 on the board.
    """
    # Stockfish-verified mate detection takes precedence.
    if engine_mate_in_after is not None:
        # mate_in_after is the ply count to forced mate from after the
        # user's move, AGAINST the user (since they just moved).
        # A positive number means mate is coming for the user.
        if engine_mate_in_after > 0:
            # We don't have opp_mate_move from engine — just play it
            # out one ply for the SAN.
            opp_mate_move_san = None
            try:
                bb = board.copy()
                m = bb.parse_san(user_move_san)
                bb.push(m)
                # Best opp move (in mate-finding context) is whatever
                # makes mate happen. We don't iterate; just leave None
                # and the template handles missing opp_mate_move.
            except Exception:
                pass
            return {
                "mate_in": engine_mate_in_after,
                "opp_mate_move": opp_mate_move_san,
                "saving_move": best_move_san,
                "source": "engine",
            }
    try:
        b = board.copy()
        m = b.parse_san(user_move_san)
        b.push(m)
    except Exception:
        return None

    # Mate-in-1: any opponent legal move is checkmate.
    for opp_move in b.legal_moves:
        bb = b.copy()
        bb.push(opp_move)
        if bb.is_checkmate():
            return {
                "mate_in": 1,
                "opp_mate_move": b.san(opp_move),
                "saving_move": best_move_san,
            }

    if max_ply < 2:
        return None

    # Mate-in-2: find any opp move that gives check AND every user
    # response leads to checkmate.
    for opp_move in b.legal_moves:
        bb = b.copy()
        bb.push(opp_move)
        if not bb.is_check():
            continue
        # Every user reply must lead to mate.
        all_mate = True
        any_reply = False
        for user_reply in bb.legal_moves:
            any_reply = True
            bbb = bb.copy()
            bbb.push(user_reply)
            mate_found = False
            for opp_final in bbb.legal_moves:
                bbbb = bbb.copy()
                bbbb.push(opp_final)
                if bbbb.is_checkmate():
                    mate_found = True
                    break
            if not mate_found:
                all_mate = False
                break
        if any_reply and all_mate:
            return {
                "mate_in": 2,
                "opp_mate_move": b.san(opp_move),
                "saving_move": best_move_san,
            }

    return None


# ── Local detector — WALKED_INTO_CAPTURE ─────────────────────────────
# Fires when the user's just-moved piece is attacked by a cheaper
# opponent piece, or attacked and undefended. The chess_brain
# hanging_piece detector covers "any user piece is hanging" but loses
# the causal "this move did it" framing; walked_into_capture is
# specifically scoped to the moved piece, which is what the player
# experiences ("I just moved my bishop and now it dies").

_PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}

_PIECE_NAME = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


def _detect_walked_into_capture(
    board: chess.Board,
    user_move_san: str,
    best_move_san: Optional[str],
) -> Optional[Dict]:
    """If user's move puts their moved piece on a square where it's
    attacked-and-undefended OR attacked by something cheaper, return
    facts; else None.

    Limited to the moved piece (not all user pieces) — the framing is
    "this move created the danger." For unrelated pre-existing hanging
    pieces, the registry's hanging_piece detector handles it.
    """
    try:
        moved_piece = None
        dest_sq = None
        b = board.copy()
        m = b.parse_san(user_move_san)
        moved_piece = board.piece_at(m.from_square)
        dest_sq = m.to_square
        b.push(m)
    except Exception:
        return None

    if not moved_piece or moved_piece.piece_type == chess.KING:
        return None
    moved_value = _PIECE_VALUE.get(moved_piece.piece_type, 0)
    user_color = moved_piece.color

    # Find opponent attackers and user defenders of dest_sq on the
    # post-move board (b).
    attacker_squares = list(b.attackers(not user_color, dest_sq))
    if not attacker_squares:
        return None
    defender_squares = list(b.attackers(user_color, dest_sq))

    attacker_values = [
        _PIECE_VALUE.get((b.piece_at(sq).piece_type if b.piece_at(sq) else None), 99)
        for sq in attacker_squares
    ]
    cheapest_idx = min(range(len(attacker_values)), key=lambda i: attacker_values[i])
    cheapest_attacker_sq = attacker_squares[cheapest_idx]
    cheapest_attacker_piece = b.piece_at(cheapest_attacker_sq)
    cheapest_attacker_value = attacker_values[cheapest_idx]

    is_undefended = not defender_squares
    is_undercut = cheapest_attacker_value < moved_value

    if not (is_undefended or is_undercut):
        return None

    # Build the capturing move SAN (cheapest attacker takes).
    capture_san = None
    try:
        cap_move = chess.Move(cheapest_attacker_sq, dest_sq)
        if cap_move in b.legal_moves:
            capture_san = b.san(cap_move)
        else:
            # Promotion edge case for pawn captures on back rank.
            cap_move_q = chess.Move(cheapest_attacker_sq, dest_sq, promotion=chess.QUEEN)
            if cap_move_q in b.legal_moves:
                capture_san = b.san(cap_move_q)
    except Exception:
        capture_san = None

    return {
        "piece": _PIECE_NAME.get(moved_piece.piece_type, "piece"),
        "square": chess.square_name(dest_sq),
        "attacker_piece": _PIECE_NAME.get(
            cheapest_attacker_piece.piece_type if cheapest_attacker_piece else 0, "piece"
        ),
        "attacker_square": chess.square_name(cheapest_attacker_sq),
        "capture_san": capture_san,
        "saving_move": best_move_san,
        "moved_value": moved_value,
        "attacker_value": cheapest_attacker_value,
        "is_undefended": is_undefended,
    }


# ── Local detector — PAWN_RACE ───────────────────────────────────────
# Fires in endgames when an opponent passed pawn is racing to promotion
# and the user's king cannot catch it (square-of-the-pawn rule). The
# Move 54 case from Game 4db4149b: Black king on c7 can't catch white's
# e6-pawn (mate in 2 pushes), but Kd6 reaches e7 in time.

def _is_passed_pawn(board: chess.Board, sq: int, color: chess.Color) -> bool:
    """No enemy pawn on same or adjacent files ahead of this pawn."""
    f = chess.square_file(sq)
    r = chess.square_rank(sq)
    direction = 1 if color == chess.WHITE else -1
    nr = r + direction
    while 0 <= nr <= 7:
        for nf in (f - 1, f, f + 1):
            if 0 <= nf <= 7:
                p = board.piece_at(chess.square(nf, nr))
                if p and p.piece_type == chess.PAWN and p.color != color:
                    return False
        nr += direction
    return True


def _king_catches_pawn(
    king_sq: int,
    pawn_sq: int,
    pawn_color: chess.Color,
    pawn_to_move: bool,
) -> bool:
    """Square-of-the-pawn rule with explicit interception simulation.
    Returns True iff defending king can capture pawn (or block promotion
    square) before promotion."""
    pawn_file = chess.square_file(pawn_sq)
    pawn_rank = chess.square_rank(pawn_sq)
    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)
    direction = 1 if pawn_color == chess.WHITE else -1
    promo_rank = 7 if pawn_color == chess.WHITE else 0
    D = abs(promo_rank - pawn_rank)
    if D <= 0:
        return True

    if pawn_to_move:
        # King has D-1 moves before pawn promotes. Try interception
        # at any path-square r_i for i ∈ [1, D-1] AND blocking promo.
        for i in range(1, D):
            target_rank = pawn_rank + i * direction
            cheb = max(abs(target_rank - king_rank), abs(pawn_file - king_file))
            if cheb <= i:
                return True
        # Block promo square — king can sit on it before pawn arrives.
        cheb_promo = max(abs(promo_rank - king_rank), abs(pawn_file - king_file))
        if cheb_promo <= D - 1:
            return True
        return False
    else:
        # Defender to move first — king has D moves (one extra).
        for i in range(1, D + 1):
            target_rank = pawn_rank + i * direction
            cheb = max(abs(target_rank - king_rank), abs(pawn_file - king_file))
            if cheb <= i:
                return True
        return False


def _detect_pawn_race(
    board: chess.Board,
    user_move_san: str,
    best_move_san: Optional[str],
) -> Optional[Dict]:
    """Endgame: opponent has a passed pawn the user's king cannot catch."""
    try:
        b = board.copy()
        m = b.parse_san(user_move_san)
        b.push(m)
    except Exception:
        return None

    # Endgame gate — only fire when most pieces are off the board.
    piece_count = sum(1 for sq in chess.SQUARES if b.piece_at(sq))
    if piece_count > 12:
        return None

    user_color = not b.turn  # user just moved
    opp_color = b.turn
    user_king_sq = b.king(user_color)
    if user_king_sq is None:
        return None

    threats = []
    for sq in chess.SQUARES:
        piece = b.piece_at(sq)
        if not piece or piece.color != opp_color or piece.piece_type != chess.PAWN:
            continue
        if not _is_passed_pawn(b, sq, opp_color):
            continue
        # In our context the opp is always to-move (user just moved).
        if _king_catches_pawn(user_king_sq, sq, opp_color, pawn_to_move=True):
            continue
        # Does any user non-king piece already attack a square on the
        # pawn's path? If so, that piece can intercept and this isn't
        # really a pure race — let the LLM or another detector handle it.
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        direction = 1 if opp_color == chess.WHITE else -1
        promo_rank = 7 if opp_color == chess.WHITE else 0
        path_squares = []
        nr = r + direction
        while (direction > 0 and nr <= promo_rank) or (direction < 0 and nr >= promo_rank):
            path_squares.append(chess.square(f, nr))
            nr += direction
        path_attacked_by_non_king = False
        for psq in path_squares:
            attackers = b.attackers(user_color, psq)
            for asq in attackers:
                ap = b.piece_at(asq)
                if ap and ap.piece_type != chess.KING:
                    path_attacked_by_non_king = True
                    break
            if path_attacked_by_non_king:
                break
        if path_attacked_by_non_king:
            continue
        D = abs(promo_rank - r)
        threats.append({
            "square": chess.square_name(sq),
            "distance": D,
        })

    if not threats:
        return None

    threats.sort(key=lambda t: t["distance"])
    closest = threats[0]
    return {
        "pawn_square": closest["square"],
        "pawn_distance": closest["distance"],
        "saving_move": best_move_san,
    }


# ── Severity scoring for dominant-pick ───────────────────────────────
# Replaces "first detector by registry priority" with a function that
# weights detections by actual decisiveness. A missed fork worth
# 9 + 5 = 14 should beat a hanging pawn worth 1.

def _severity_score(det: Dict) -> float:
    pt = det.get("pattern_type") or ""
    d = det.get("details") or {}

    # Mate is always max — nothing else compares.
    if pt == "walked_into_mate":
        # Weight by mate proximity (mate-in-1 most decisive).
        mate_in = d.get("mate_in", 1)
        return 1000 - mate_in  # 999 for mate-in-1, 998 for mate-in-2
    if pt == "missed_mate":
        return 950

    # Material-loss patterns weighted by piece value or fork total.
    if pt == "missed_fork":
        return float(d.get("total_value", 0)) * 2.0  # forks compound
    if pt == "missed_pin":
        return 12.0  # pins are decisive but not always material
    if pt == "missed_skewer":
        return 12.0
    if pt == "missed_discovery":
        return 12.0
    if pt == "missed_overload":
        return 10.0
    if pt == "missed_removal":
        return 11.0
    if pt == "missed_back_rank":
        return 50.0  # back-rank is mate-flavored
    if pt == "hanging_piece":
        # Single hanging piece — value of that piece.
        return float(d.get("piece_value", 0))
    if pt == "walked_into_capture":
        # The user's move directly hung the piece — score above
        # generic hanging_piece AND trapped_piece because the causal
        # story is sharper than either descriptive detector.
        return float(d.get("moved_value", 0)) * 2.0 + 4.0
    if pt == "pawn_race":
        # Decisive in endgame — opp pawn promotes if user can't catch.
        # Higher than fork (~14-18) because mate-in-N follows promo.
        return 30.0 - float(d.get("pawn_distance", 1))
    if pt == "trapped_piece":
        return 7.0
    if pt == "walked_into_fork":
        return 14.0
    if pt == "walked_into_pin":
        return 10.0

    # Strategic / endgame patterns — lower default unless decisive.
    if pt == "outside_passed_pawn":
        return 6.0
    if pt == "opposition":
        return 4.0

    return 1.0


def extract_mate_against_user(
    move_evaluations: Optional[List[Dict]],
    move_number: int,
    move_san: str,
    user_color: str,
) -> Optional[int]:
    """Find Stockfish's mate_info.after for this move and convert to
    user-perspective: positive int = ply-count to mate AGAINST the user.

    Stockfish's mate_in_after is from White's perspective:
        +N means White mates in N
        -N means Black mates in N
    So mate-against-user is +after when user is black and after > 0,
    or -after when user is white and after < 0. Otherwise None (no
    walk-into-mate from this move).
    """
    if not move_evaluations:
        return None
    user_is_white = (user_color or "").lower() == "white"
    for entry in move_evaluations:
        if entry.get("move_number") != move_number:
            continue
        if entry.get("move") != move_san:
            continue
        mate_info = entry.get("mate_info") or {}
        after = mate_info.get("after")
        if after is None:
            return None
        if user_is_white and after < 0:
            return -after
        if (not user_is_white) and after > 0:
            return after
        return None
    return None


def detect_concepts(
    *,
    fen_before: str,
    user_move_san: str,
    best_move_san: Optional[str] = None,
    context: Optional[Dict] = None,
    engine_mate_in_after: Optional[int] = None,
) -> List[Dict]:
    """Run all chess_brain detectors against this moment.

    Returns a flat list of detector results (each a dict from
    DetectorResult: pattern_type, details, teaching_hook, key_squares,
    confidence, category) sorted by registration priority (already
    sorted in the registry).

    Pass engine_mate_in_after when V5/move_evaluations has Stockfish's
    pre-computed ply-to-mate after the user's move; this lets the
    walked_into_mate detector catch mate-in-3+ that local search misses.

    Returns [] on any exception so callers can fall through gracefully.
    """
    if not fen_before or not user_move_san:
        return []

    try:
        board = chess.Board(fen_before)
    except Exception as e:
        logger.warning(f"[concept_dispatcher] FEN parse failed: {e}")
        return []

    try:
        from services.chess_brain.detector_registry import get_detector_registry
        registry = get_detector_registry()
    except Exception as e:
        logger.warning(f"[concept_dispatcher] detector registry import failed: {e}")
        return []

    ctx = context or {}
    try:
        tactical, strategic, behavioral = registry.run_all(
            board=board,
            user_move=user_move_san,
            best_move=best_move_san or "",
            context=ctx,
        )
    except Exception as e:
        logger.warning(f"[concept_dispatcher] detector run failed: {e}")
        tactical, strategic, behavioral = [], [], []

    out: List[Dict] = []
    for r in tactical + strategic + behavioral:
        if not r.detected:
            continue
        out.append({
            "pattern_type": r.pattern_type,
            "details": r.details or {},
            "teaching_hook": r.teaching_hook,
            "key_squares": r.key_squares or [],
            "confidence": r.confidence,
            "category": r.category,
        })

    # Local detector — WALKED_INTO_MATE. Not in the chess_brain
    # registry (that one detects MISSED_MATE for the user, the
    # opposite). We add it here so a Kc6 → e8=Q+ mate gets the
    # decisive "walked into mate" caption.
    try:
        mate_facts = _detect_walked_into_mate(
            board,
            user_move_san,
            best_move_san,
            engine_mate_in_after=engine_mate_in_after,
        )
        if mate_facts:
            out.append({
                "pattern_type": "walked_into_mate",
                "details": mate_facts,
                "teaching_hook": "Allows forced mate",
                "key_squares": [],
                "confidence": 1.0,
                "category": "tactical",
            })
    except Exception as e:
        logger.warning(f"[concept_dispatcher] walked_into_mate detect failed: {e}")

    # Local detector — WALKED_INTO_CAPTURE. Specifically scopes to the
    # just-moved piece, which is the narrative the player needs.
    try:
        cap_facts = _detect_walked_into_capture(board, user_move_san, best_move_san)
        if cap_facts:
            out.append({
                "pattern_type": "walked_into_capture",
                "details": cap_facts,
                "teaching_hook": "Moved piece is now under attack",
                "key_squares": [cap_facts.get("square")] if cap_facts.get("square") else [],
                "confidence": 0.95,
                "category": "tactical",
            })
    except Exception as e:
        logger.warning(f"[concept_dispatcher] walked_into_capture detect failed: {e}")

    # Local detector — PAWN_RACE. Endgame: opp passed pawn promotes
    # because user-king is outside the square-of-the-pawn.
    try:
        race_facts = _detect_pawn_race(board, user_move_san, best_move_san)
        if race_facts:
            out.append({
                "pattern_type": "pawn_race",
                "details": race_facts,
                "teaching_hook": "Opponent's pawn promotes",
                "key_squares": [race_facts.get("pawn_square")] if race_facts.get("pawn_square") else [],
                "confidence": 0.9,
                "category": "strategic",
            })
    except Exception as e:
        logger.warning(f"[concept_dispatcher] pawn_race detect failed: {e}")

    return out


def pick_dominant_concept(detections: List[Dict]) -> Optional[Dict]:
    """Pick the most decisive detection that also has a caption template.

    Updated 2026-05-05: registry-priority ordering picked hanging-pawn
    over missed-fork on Game 4db4149b move 21 because the registry has
    hanging_piece at priority 95 vs fork at 90. The ACTUAL decisiveness
    flipped the call — a missed fork worth 14 material points is
    obviously bigger than a hanging pawn worth 1.

    New rule: among detections with templates, pick the one with the
    highest _severity_score. Mate beats forks beats hanging pieces
    beats endgame patterns. Score function lives next door.
    """
    candidates = [d for d in detections if has_template(d.get("pattern_type"))]
    if not candidates:
        return None
    return max(candidates, key=_severity_score)


def pick_dominant_renderable(detections: List[Dict]) -> Optional[Dict]:
    """Like pick_dominant_concept but skips detections whose template
    returns None due to missing details. Without this, a high-severity
    detection (e.g., a fork detector firing without attacker_square)
    can suppress a lower-severity detection (e.g., hanging_piece) that
    would have rendered fine."""
    from .concept_templates import render_caption
    candidates = [d for d in detections if has_template(d.get("pattern_type"))]
    if not candidates:
        return None
    candidates_sorted = sorted(candidates, key=_severity_score, reverse=True)
    for d in candidates_sorted:
        try:
            caption = render_caption(d.get("pattern_type"), d.get("details") or {})
        except Exception:
            caption = None
        if caption:
            return d
    return None


def caption_for_moment(
    *,
    fen_before: str,
    user_move_san: str,
    best_move_san: Optional[str] = None,
    context: Optional[Dict] = None,
    engine_mate_in_after: Optional[int] = None,
) -> Tuple[Optional[str], Optional[Dict]]:
    """Run detectors → pick dominant → render caption.

    Returns (caption, metadata) where metadata describes which detector
    fired (for diagnostics/UI) or both None if no template-matched
    pattern was detected.
    """
    detections = detect_concepts(
        fen_before=fen_before,
        user_move_san=user_move_san,
        best_move_san=best_move_san,
        context=context,
        engine_mate_in_after=engine_mate_in_after,
    )
    dominant = pick_dominant_renderable(detections)
    if not dominant:
        return None, None

    caption = render_caption(dominant["pattern_type"], dominant["details"])
    if not caption:
        return None, None

    return caption, {
        "pattern_type": dominant["pattern_type"],
        "category": dominant["category"],
        "key_squares": dominant["key_squares"],
        "confidence": dominant["confidence"],
        # Pass through the raw detector details so callers can tell
        # engine-verified mate from local-search mate (etc.) when
        # computing per-commentary confidence scores.
        "details": dominant.get("details") or {},
    }
