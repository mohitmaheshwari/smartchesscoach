"""
Candidate builder — produces 3 move options for the post-game
"What would you play here?" interaction:

  1. User's actual move — wrong. Continuation from the real game.
  2. Engine's best move — correct. Continuation from V5's pv_after_best.
  3. Distractor — wrong. Another legal move of the same piece type.

Each candidate carries a short caption that's shown AFTER the player
clicks and watches the line animate.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import chess

logger = logging.getLogger(__name__)


def _safe_san(board: chess.Board, move: chess.Move) -> Optional[str]:
    try:
        if move in board.legal_moves:
            return board.san(move)
    except Exception:
        pass
    return None


def _pv_to_sans(
    fen_before: str,
    first_uci: str,
    rest_pv: List[str],
    max_ply: int = 3,
) -> List[str]:
    """Convert (first move UCI + PV continuation) into a sequence of SANs.
    Returns [] if first move is illegal.
    """
    try:
        board = chess.Board(fen_before)
        first_move = chess.Move.from_uci(first_uci)
        first_san = _safe_san(board, first_move)
        if not first_san:
            return []
        board.push(first_move)
    except Exception:
        return []

    out = [first_san]
    for uci in (rest_pv or [])[: max_ply - 1]:
        try:
            mv = chess.Move.from_uci(uci)
            san = _safe_san(board, mv)
            if not san:
                break
            out.append(san)
            board.push(mv)
        except Exception:
            break
    return out


def _actual_continuation(
    v5_data: List[Dict],
    move_number: int,
    move_san: str,
    max_ply: int = 2,
) -> List[str]:
    """Pull the next moves from V5 data AFTER the critical move."""
    found = False
    out: List[str] = []
    for m in v5_data:
        if not found:
            if (m.get("is_user_move")
                    and m.get("move_number") == move_number
                    and m.get("move_san") == move_san):
                found = True
            continue
        san = m.get("move_san")
        if san:
            out.append(san)
        if len(out) >= max_ply:
            break
    return out


def _pick_distractor(fen: str, exclude_ucis: List[str]) -> Optional[Dict]:
    """Pick a plausible third move different from the excluded ones.
    Prefers a move of the SAME piece type as the excluded moves
    (so if user/best are king moves, distractor is also a king move).
    Returns {san, uci} or None.
    """
    try:
        board = chess.Board(fen)
    except Exception:
        return None

    excluded = set(exclude_ucis)

    # Identify piece type of one of the excluded moves
    target_piece_type = None
    for uci in exclude_ucis:
        try:
            mv = chess.Move.from_uci(uci)
            piece = board.piece_at(mv.from_square)
            if piece:
                target_piece_type = piece.piece_type
                break
        except Exception:
            continue

    same_type_options = []
    other_options = []
    for mv in board.legal_moves:
        if mv.uci() in excluded:
            continue
        piece = board.piece_at(mv.from_square)
        if piece and target_piece_type and piece.piece_type == target_piece_type:
            same_type_options.append(mv)
        else:
            other_options.append(mv)

    chosen = None
    if same_type_options:
        chosen = same_type_options[0]
    elif other_options:
        chosen = other_options[0]

    if not chosen:
        return None

    san = _safe_san(board, chosen)
    if not san:
        return None
    return {"san": san, "uci": chosen.uci()}


def _outcome_caption_for_user_move(v5_user_record: Dict, severity: str) -> str:
    """One-line caption for the user's actual (wrong) move.
    Uses V5 plan.consequence when available — that's already in voice."""
    plan = v5_user_record.get("plan") or {}
    if isinstance(plan, dict):
        consequence = plan.get("consequence")
        if consequence and isinstance(consequence, str):
            # Trim to first sentence for brevity
            first = consequence.split(".")[0].strip()
            if first and len(first) > 5:
                return first + "."
    if severity == "blunder":
        return "Your move lost the game from here."
    return "The position got worse after this."


def build_candidates(
    *,
    fen_before: str,
    move_uci: str,
    move_san: str,
    move_number: int,
    decryption_v5_data: List[Dict],
    engine_caption: str = "",
) -> List[Dict]:
    """Build the 3 candidate moves for one critical moment.

    Returns a list of {san, line, caption, isCorrect} dicts. Empty
    list if we can't build a meaningful set (e.g., no engine best
    move, or best == user move).
    """
    if not fen_before or not move_uci:
        return []

    user_v5 = next(
        (
            m for m in decryption_v5_data
            if m.get("is_user_move")
            and m.get("move_number") == move_number
            and m.get("move_san") == move_san
        ),
        None,
    )
    if not user_v5:
        return []

    best_uci = user_v5.get("best_move_uci") or ""
    best_san = user_v5.get("best_move_san") or ""
    pv = user_v5.get("pv_after_best") or []
    severity = user_v5.get("severity") or "mistake"

    if not best_uci or best_uci == move_uci or not best_san:
        return []

    # 1. USER'S ACTUAL — wrong
    user_line = [move_san] + _actual_continuation(
        decryption_v5_data, move_number, move_san, max_ply=2
    )
    user_caption = _outcome_caption_for_user_move(user_v5, severity)

    # 2. ENGINE'S BEST — correct
    best_line = _pv_to_sans(fen_before, best_uci, pv, max_ply=3)
    if not best_line:
        best_line = [best_san]

    # Concept-driven caption — runs the chess_brain detector registry
    # against this position, picks the dominant tactical/strategic
    # pattern, renders a deterministic caption from a template. Falls
    # back to engine_caption (LLM-generated text) when no template
    # matches, then to a generic line. Goal: zero-hallucination captions
    # for the common 600-1400 patterns; LLM only as last resort.
    concept_caption = None
    try:
        from .concept_dispatcher import caption_for_moment
        concept_caption, _meta = caption_for_moment(
            fen_before=fen_before,
            user_move_san=move_san,
            best_move_san=best_san,
        )
    except Exception:
        concept_caption = None

    correct_caption = (
        concept_caption
        or engine_caption
        or "This is the move. It holds the position."
    )

    # 3. DISTRACTOR — wrong, plausible
    distractor = _pick_distractor(fen_before, [move_uci, best_uci])

    candidates = [
        {
            "san": move_san,
            "line": user_line,
            "caption": user_caption,
            "isCorrect": False,
        },
        {
            "san": best_san,
            "line": best_line,
            "caption": correct_caption,
            "isCorrect": True,
        },
    ]

    if distractor:
        candidates.append({
            "san": distractor["san"],
            "line": [distractor["san"]],
            "caption": "Doesn't address the threat. The pressure stays.",
            "isCorrect": False,
        })

    return candidates
