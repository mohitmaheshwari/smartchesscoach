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
    dominant = pick_dominant_concept(detections)
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
    }
