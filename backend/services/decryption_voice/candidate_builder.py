"""
Candidate builder — produces move options for the post-game
"What would you play here?" interaction:

  1. User's actual move — wrong. Continuation from the real game.
  2. Engine's best move — correct. Continuation from V5's pv_after_best.
  3. Equally-good alternatives — also correct. Discovered via
     Stockfish multi-PV; any move within EQUIV_THRESHOLD_CP of best
     is presented as another valid answer. (Mohit 2026-05-21: many
     positions have multiple solutions; showing only one teaches
     the wrong lesson that chess has unique answers.)
  4. Distractor — wrong. A plausible third option, included only
     when there's a SINGLE clear best (no equally-good alternatives).

Each candidate carries a short caption that's shown AFTER the player
clicks and watches the line animate.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import chess
import chess.engine

logger = logging.getLogger(__name__)

# Multi-PV configuration.
_STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
_MULTIPV_DEPTH = 14   # depth tradeoff: 14 is fast enough at runtime,
                      # deep enough to identify true "equally good" moves.
_MULTIPV_N = 5        # max alternatives to consider.
EQUIV_THRESHOLD_CP = 30  # within this cp of best = "equally good"


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

    Source-of-truth order (Mohit 2026-05-27, [[one-source-of-truth-for-
    coaching]]):
      1. v5_user_record.plan.consequence — already in coach voice from
         the central caption pipeline. Trimmed to first sentence.
      2. v5_user_record.caption — the full R12/R_PROMOTED caption from
         build_move_teaching_decision. First sentence captures "what
         happened" without overclaim.
      3. Silence (empty string) — better than a hardcoded python-literal
         fallback that overclaims (see fb_1305644d72e9: "Your move lost
         the game from here" overclaimed for a single blunder).

    The third branch fires only when the V5 pipeline produced no caption
    — should not happen in practice after the central-layer migration
    (PR-1 → PR-5 / commit abbd7f88, PR-6 / commit aa474534). Returning
    "" lets the caller decide UX (typically: omit the outcome line).
    """
    plan = v5_user_record.get("plan") or {}
    if isinstance(plan, dict):
        consequence = plan.get("consequence")
        if consequence and isinstance(consequence, str):
            first = consequence.split(".")[0].strip()
            if first and len(first) > 5:
                return first + "."

    # Fall through to the V5 caption itself — already deterministic,
    # already in voice, already severity-aware (its severity_phrase
    # carries "is a mistake" / "is a major blunder" etc.).
    v5_caption = (v5_user_record.get("caption") or "").strip()
    if v5_caption:
        first = v5_caption.split(".")[0].strip()
        if first and len(first) > 5:
            return first + "."

    return ""


def _find_equivalent_alternatives(
    fen_before: str,
    best_uci: str,
    user_uci: str,
    user_color: Optional[str],
) -> List[Tuple[str, str, List[str]]]:
    """Find moves within EQUIV_THRESHOLD_CP of best via multi-PV analysis.

    Excludes the user's actual move (which is presumably the "wrong"
    one we want to contrast against) and the best move itself (which
    is already in the candidate list separately).

    Returns list of (uci, san, line_san) tuples, ordered by eval
    descending. Empty list if multipv can't run, no alternatives
    qualify, or all alternatives equal the user's move / best.
    """
    if not os.path.isfile(_STOCKFISH_PATH):
        return []
    try:
        board = chess.Board(fen_before)
    except Exception:
        return []

    is_user_white = (user_color or "white").lower() == "white"
    try:
        with chess.engine.SimpleEngine.popen_uci(_STOCKFISH_PATH) as engine:
            infos = engine.analyse(
                board,
                chess.engine.Limit(depth=_MULTIPV_DEPTH),
                multipv=_MULTIPV_N,
            )
    except Exception as exc:
        logger.warning(f"[candidate_builder] multipv analyse failed: {exc}")
        return []

    if not infos:
        return []

    # First entry is the best move per multi-PV convention.
    def _user_pov_cp(info: Dict) -> Optional[int]:
        score = info.get("score")
        if score is None:
            return None
        try:
            return score.white().score(mate_score=10000) * (1 if is_user_white else -1)
        except Exception:
            return None

    best_cp = _user_pov_cp(infos[0])
    if best_cp is None:
        return []

    alternatives: List[Tuple[str, str, List[str]]] = []
    for info in infos:
        pv = info.get("pv") or []
        if not pv:
            continue
        first_move = pv[0]
        first_uci = first_move.uci()
        if first_uci == best_uci or first_uci == user_uci:
            continue
        cp = _user_pov_cp(info)
        if cp is None:
            continue
        if cp + EQUIV_THRESHOLD_CP < best_cp:
            continue  # too much worse than best — not "equally good"

        # Build SAN line from the PV.
        try:
            tmp_board = chess.Board(fen_before)
            sans: List[str] = []
            for mv in pv[:3]:
                san = _safe_san(tmp_board, mv)
                if not san:
                    break
                sans.append(san)
                tmp_board.push(mv)
            if not sans:
                continue
        except Exception:
            continue

        alternatives.append((first_uci, sans[0], sans))

    return alternatives


def build_candidates(
    *,
    fen_before: str,
    move_uci: str,
    move_san: str,
    move_number: int,
    decryption_v5_data: List[Dict],
    engine_caption: str = "",
    move_evaluations: Optional[List[Dict]] = None,
    user_color: Optional[str] = None,
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
        from .concept_dispatcher import caption_for_moment, extract_mate_against_user
        engine_mate = None
        if move_evaluations and user_color:
            engine_mate = extract_mate_against_user(
                move_evaluations, move_number, move_san, user_color,
            )
        concept_caption, _meta = caption_for_moment(
            fen_before=fen_before,
            user_move_san=move_san,
            best_move_san=best_san,
            engine_mate_in_after=engine_mate,
            pv_after_best=user_v5.get("pv_after_best") or [],
            pv_after_played=user_v5.get("pv_after_played") or [],
            user_color=user_color,
        )
    except Exception:
        concept_caption = None

    correct_caption = (
        concept_caption
        or engine_caption
        or "This is the move. It holds the position."
    )

    # 3. EQUALLY-GOOD ALTERNATIVES (Mohit 2026-05-21) — surfaced via
    # multi-PV when the engine sees multiple moves within
    # EQUIV_THRESHOLD_CP of best. The whole point of teaching: chess
    # often has multiple correct answers; the puzzle should reflect
    # that. When alternatives exist, the distractor is dropped — we
    # have real "right" choices to fill the slots.
    alternatives = _find_equivalent_alternatives(
        fen_before=fen_before,
        best_uci=best_uci,
        user_uci=move_uci,
        user_color=user_color,
    )

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

    for _alt_uci, _alt_san, _alt_line in alternatives[:3]:  # cap at 3
        candidates.append({
            "san": _alt_san,
            "line": _alt_line,
            "caption": "Also good — keeps the same advantage.",
            "isCorrect": True,
        })

    # Only add a distractor when there are NO equally-good
    # alternatives. With multiple correct answers there's already
    # enough material for the puzzle without inventing a wrong move.
    if not alternatives:
        distractor = _pick_distractor(fen_before, [move_uci, best_uci])
        if distractor:
            candidates.append({
                "san": distractor["san"],
                "line": [distractor["san"]],
                "caption": "Doesn't address the threat. The pressure stays.",
                "isCorrect": False,
            })

    return candidates
