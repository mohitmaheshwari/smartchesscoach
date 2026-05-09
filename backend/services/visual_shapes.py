"""
Visual Shapes — geometric pattern detectors (the visual danger language layer).

Architecture (per project_visual_danger_language.md memo):
  Layer 1 — Geometric: pure math, boolean. The shape is on the board or it isn't.
  Layer 2 — Verifier:  confirms the shape actually creates concrete danger.
                       Without this gate, we ship a 30%+ false-alarm rate.

Both layers must pass before a shape is emitted.

Rules ship one at a time, each end-to-end audited before the next starts.
First rule: queen_too_early (Rule 8 in the canonical 23).

Shape output format (one entry per detected shape, attached to the
move_evaluation that triggered the detection):

    {
      "type":         "queen_too_early",   # canonical key
      "move_number":  int,                  # ply or full-move number
      "square":       str | None,           # focal square (e.g. "h5")
      "evidence":     str,                  # one-line reason for debugging
      "coach_line":   str,                  # 1200-friendly coach voice
    }
"""
from __future__ import annotations

from typing import Dict, List, Optional

import chess


# Canonical shape keys (mirror the visual_danger_language memory naming)
SHAPE_QUEEN_TOO_EARLY = "queen_too_early"


# ────────────────────────────────────────────────────────────────────
# Rule 8: Queen too early
#
# Detector (geometric, mechanical):
#   - move_number <= 10
#   - the played move IS a queen move
#   - after the move, fewer than 2 minor pieces (knights+bishops) of
#     the same colour have been developed off their starting squares
#
# Verifier (next 4 plies — needs future moves from move_evaluations):
#   - the queen is attacked by an enemy minor piece (knight/bishop), OR
#   - the user's queen is forced to move again from the same square
#     while under minor attack (forced retreat / relocation)
#
# If detector AND verifier both pass → shape emitted. If detector
# fires but verifier rejects, the queen sortie was justified by
# context (no tempo lost) → silent.
# ────────────────────────────────────────────────────────────────────

_QUEEN_EARLY_MAX_MOVE = 10
# How many future move-evaluations to inspect for the chase. The
# production move_evaluations array contains ONLY the user's moves —
# opponent moves are not stored as events; their effect is captured
# in the FEN snapshots between user moves. So 4 here means "inspect
# the user's next 4 turns" — which covers 4 opponent responses in
# user-only data and 4 plies of game time in interleaved data.
_QUEEN_EARLY_VERIFIER_WINDOW = 4


def _count_developed_minors(board: chess.Board, color: bool) -> int:
    """Knights+bishops of `color` that have left their starting squares."""
    if color == chess.WHITE:
        starts = [
            (chess.B1, chess.KNIGHT), (chess.G1, chess.KNIGHT),
            (chess.C1, chess.BISHOP), (chess.F1, chess.BISHOP),
        ]
    else:
        starts = [
            (chess.B8, chess.KNIGHT), (chess.G8, chess.KNIGHT),
            (chess.C8, chess.BISHOP), (chess.F8, chess.BISHOP),
        ]
    developed = 0
    for sq, piece_type in starts:
        piece = board.piece_at(sq)
        if piece is None or piece.color != color or piece.piece_type != piece_type:
            developed += 1
    return developed


def _queen_chased_in_future(
    fen_before: str,
    queen_move_uci: str,
    future_moves: List[Dict],
    user_color: bool,
    max_window: int = _QUEEN_EARLY_VERIFIER_WINDOW,
) -> bool:
    """
    Verifier — does the queen get chased in the next several positions?

    The production `move_evaluations` array contains only the user's
    moves; opponent moves aren't stored as events. So we inspect the
    FEN snapshots of subsequent user moves: each `fen_before` of a
    later user move = position right after the opponent's response.

    This works for both user-only arrays (production) and interleaved
    arrays (smoke tests) — every entry's fen_before is just "some
    snapshot in the game's future" and we check the queen's status in
    each one. No reliance on whose-turn-it-is in the array.

    Returns True iff in any of the inspected future positions:
      - the user's queen is attacked by an enemy minor (knight/bishop), OR
      - the user is forced to move their queen FROM a square that's
        currently under attack by an enemy minor (forced retreat).

    Conservative: missing/illegal data → False (fail-closed).
    """
    # Sanity-check the queen move is legal in fen_before.
    try:
        legality_board = chess.Board(fen_before)
        queen_mv = chess.Move.from_uci(queen_move_uci)
        if queen_mv not in legality_board.legal_moves:
            return False
    except Exception:
        return False

    # Walk the next several future moves. For each, inspect BOTH
    # fen_before and fen_after — this covers both data shapes:
    #   • user-only array: fen_before of user's next move = right
    #     after opponent responded → chase visible there.
    #   • interleaved array: fen_after of opponent's move = right
    #     after opponent moved → chase visible there.
    # Some FENs will appear twice; that's harmless.
    for fm in future_moves[:max_window]:
        for fen_key in ("fen_before", "fen_after"):
            fen = fm.get(fen_key, "")
            if not fen:
                continue
            try:
                board = chess.Board(fen)
            except Exception:
                continue

            user_queens = [
                sq for sq, p in board.piece_map().items()
                if p.piece_type == chess.QUEEN and p.color == user_color
            ]
            if not user_queens:
                # Queen captured/promoted-off — different dynamic, bail.
                return False

            for qsq in user_queens:
                attackers = board.attackers(not user_color, qsq)
                for asq in attackers:
                    apiece = board.piece_at(asq)
                    if apiece and apiece.piece_type in (chess.KNIGHT, chess.BISHOP):
                        return True

        # Forced retreat — only meaningful at fen_before of the move
        # being inspected (the position the user is acting on).
        fen_b = fm.get("fen_before", "")
        next_uci = fm.get("move_uci", "")
        if not fen_b or not next_uci or len(next_uci) < 4:
            continue
        try:
            board = chess.Board(fen_b)
            next_mv = chess.Move.from_uci(next_uci)
            if next_mv not in board.legal_moves:
                continue
            moving = board.piece_at(next_mv.from_square)
            if (moving
                    and moving.piece_type == chess.QUEEN
                    and moving.color == user_color):
                attackers = board.attackers(not user_color, next_mv.from_square)
                for asq in attackers:
                    apiece = board.piece_at(asq)
                    if apiece and apiece.piece_type in (chess.KNIGHT, chess.BISHOP):
                        return True
        except Exception:
            pass

    return False


def detect_queen_too_early(
    fen_before: str,
    move_uci: str,
    move_number: int,
    future_moves: List[Dict],
) -> Optional[Dict]:
    """
    Returns a shape dict if the played move triggers the queen-too-early
    pattern AND the verifier confirms tempo loss. None otherwise.
    """
    if not fen_before or not move_uci or len(move_uci) < 4:
        return None
    if move_number <= 0 or move_number > _QUEEN_EARLY_MAX_MOVE:
        return None

    try:
        board = chess.Board(fen_before)
        mv = chess.Move.from_uci(move_uci)
        if mv not in board.legal_moves:
            return None
        moving = board.piece_at(mv.from_square)
        if moving is None or moving.piece_type != chess.QUEEN:
            return None
        user_color = moving.color
        played_san = board.san(mv)
        board.push(mv)
    except Exception:
        return None

    # Detector: minor-piece development count after the queen sortie.
    developed = _count_developed_minors(board, user_color)
    if developed >= 2:
        return None  # Justified — enough development to back the queen.

    # Verifier: did the queen actually get chased?
    if not _queen_chased_in_future(fen_before, move_uci, future_moves, user_color):
        return None

    queen_sq_after = mv.to_square
    return {
        "type": SHAPE_QUEEN_TOO_EARLY,
        "move_number": move_number,
        "square": chess.square_name(queen_sq_after),
        "evidence": (
            f"{played_san} brought queen out on move {move_number} with "
            f"{developed} minor piece{'s' if developed != 1 else ''} developed; "
            f"verifier confirmed queen was chased within "
            f"{_QUEEN_EARLY_VERIFIER_WINDOW} plies"
        ),
        "coach_line": (
            f"{played_san} brings the queen out before your knights and bishops. "
            f"Every time they hit her with a minor piece, they develop AND chase you for free."
        ),
    }


# ────────────────────────────────────────────────────────────────────
# Public entry point — runs every shape detector on a single move.
# ────────────────────────────────────────────────────────────────────

def detect_shapes_for_move(
    move: Dict,
    future_moves: Optional[List[Dict]] = None,
) -> List[Dict]:
    """
    Run every visual-shape detector on a single move evaluation.

    Returns a list of shape dicts — empty when no shape fires.
    Each detector is independent; a single move can carry multiple shapes.
    """
    fen_before = move.get("fen_before", "")
    move_uci = move.get("move_uci", "")
    move_number = move.get("move_number", 0) or 0
    future = future_moves or []

    shapes: List[Dict] = []

    qte = detect_queen_too_early(fen_before, move_uci, move_number, future)
    if qte:
        shapes.append(qte)

    # Future rules plug in here — one per release, each end-to-end audited.

    return shapes
