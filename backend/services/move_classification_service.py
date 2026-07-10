"""
Move Classification Service — 15-category move type system

Integrated into analysis_worker to classify each move as it's analyzed.
Complements cognitive_gap (9 categories) with deeper fundamentals.

Categories (ordered by precedence):
  1. allowed_mate — you allowed checkmate (failed defense)
  2. one_move_blunder — hangs material immediately (pv depth 1-2)
  3. walked_into_tactic — material lost via pv depth 3+ (2-move combo)
  4. bad_trade — net material loss in a trade
  5. missed_mate — had mate, didn't take it
  6. missed_tactic — missed fork/pin/skewer opportunity
  7. missed_free_material — opponent piece hanging, you ignored it
  8. conversion — threw winning game
  9. king_safety — exposed your king unnecessarily
  10. endgame_technique — endgame-specific mistake
  11. calculation_depth — shallow calculation (saw 1 move, missed line)
  12. ignore_threat — didn't address opponent threat
  13. pawn_structure — weakened your pawns
  14. piece_activity — moved piece to passive square
  15. opening_knowledge — violated opening principles

Engine-hard (verified Stockfish):
  - allowed_mate, one_move_blunder, walked_into_tactic, missed_mate,
    missed_free_material, opening_knowledge (early-queen only), endgame_technique

Deferred to Claude: bad_trade, missed_tactic, conversion, king_safety,
  pawn_structure, piece_activity, calculation_depth, ignore_threat

Shipped 2026-06-12 as scripts/classify_fundamentals.py.
Integrated into analysis_worker 2026-07-10.
"""

import chess
from typing import Optional, Dict, Any

# Material values for PV analysis
MATERIAL_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}


def _material_count_for_side(board: chess.Board, color: bool) -> int:
    """Sum material value for one side (excluding king)."""
    total = 0
    for piece_type, value in MATERIAL_VALUES.items():
        total += len(board.pieces(piece_type, color)) * value
    return total


def _push_move_any(board: chess.Board, move_str: str) -> bool:
    """Try to push a move (SAN or UCI). Return True if successful."""
    for parse_fn in (board.parse_san, lambda x: chess.Move.from_uci(x)):
        try:
            board.push(parse_fn(move_str))
            return True
        except Exception:
            pass
    return False


def _pv_material_loss(move_data: Dict[str, Any], user_color: str) -> Optional[str]:
    """
    Analyze principal variation to determine blunder type.

    Returns:
      "one_move_blunder" if material lost in ply 1-2
      "walked_into_tactic" if material lost in ply 3+
      None if no significant material loss
    """
    fen_before = move_data.get("fen_before", "")
    pv_after = move_data.get("pv_after_played") or []
    move_uci = move_data.get("move_uci") or ""

    if not fen_before or not pv_after or not move_uci:
        return None

    try:
        board = chess.Board(fen_before)
        user_is_white = user_color == "white"
        user_side = chess.WHITE if user_is_white else chess.BLACK

        # Apply the user's played move
        try:
            move_obj = chess.Move.from_uci(move_uci)
        except Exception:
            move_obj = board.parse_san(move_data.get("move", ""))

        if move_obj not in board.legal_moves:
            return None

        board.push(move_obj)

        # Get baseline material after user's move
        baseline_material = _material_count_for_side(board, user_side)

        # Walk the PV and find when material is lost (depth)
        material_values = []
        for pv_move in pv_after[:6]:
            if not _push_move_any(board, pv_move):
                break
            material = _material_count_for_side(board, user_side)
            material_values.append(material)

        if not material_values:
            return None

        # No material lost in PV (depth 6)
        if material_values[-1] >= baseline_material - 100:
            return None

        # Find depth where material is lost
        # Depth 1-2 = one_move_blunder (immediate recapture)
        # Depth 3+ = walked_into_tactic (2+ move combo)
        for depth, mat in enumerate(material_values, 1):
            if mat <= baseline_material - 200:  # Significant loss
                return "one_move_blunder" if depth <= 2 else "walked_into_tactic"
            elif mat <= baseline_material - 100:  # Minor loss
                # Keep looking for deeper damage
                if depth > 2:
                    return "walked_into_tactic"

        return None

    except Exception:
        return None


def _missed_free_material(move_data: Dict[str, Any]) -> bool:
    """Did best_move capture an undefended piece that played_move ignored?"""
    best_move = move_data.get("best_move", "")
    played_move = move_data.get("move", "")
    fen_before = move_data.get("fen_before", "")

    # Best move must be a capture
    if "x" not in best_move:
        return False

    # Best move must be different from played move
    if played_move == best_move:
        return False

    try:
        board = chess.Board(fen_before)
        best_move_obj = board.parse_san(best_move)
        captured_piece = board.piece_at(best_move_obj.to_square)

        # Captured square must have a piece
        if not captured_piece:
            return False

        # That piece must be undefended (no defenders for opponent's piece)
        defenders = board.attackers(captured_piece.color, best_move_obj.to_square)
        return len(defenders) == 0

    except Exception:
        return False


def _early_queen(move_data: Dict[str, Any]) -> bool:
    """Violates opening principle: moving queen in opening (moves 1-6) without capture."""
    move_san = move_data.get("move", "")
    move_number = move_data.get("move_number", 99)

    # Queen move, no capture, in early opening (moves 1-6)
    return move_san.startswith("Q") and move_number <= 6 and "x" not in move_san


def _piece_count_for_endgame(board: chess.Board) -> int:
    """Count non-pawn, non-king pieces (used to detect endgame phase)."""
    count = 0
    for pt in (chess.ROOK, chess.BISHOP, chess.KNIGHT):
        for color in (chess.WHITE, chess.BLACK):
            count += len(board.pieces(pt, color))
    return count


def classify_move(move_data: Dict[str, Any], user_color: str) -> Optional[str]:
    """
    Classify a move into one of the 15 fundamental types.

    Args:
        move_data: Move evaluation dict with fen_before, move, cp_loss, eval_before/after, pv_after_played, etc.
        user_color: "white" or "black" — which side the user played

    Returns:
        One of the 15 category strings, or "(deferred)" if needs Claude
    """

    fen_before = move_data.get("fen_before", "")
    eval_before = move_data.get("eval_before")
    eval_after = move_data.get("eval_after")
    cp_loss = move_data.get("cp_loss", 0)

    # Only classify real mistakes (cp_loss >= 100)
    if cp_loss < 100:
        return None

    # Convert evals to user's perspective
    is_white = user_color == "white"
    ue_before = eval_before if is_white else (-eval_before if eval_before is not None else None)
    ue_after = eval_after if is_white else (-eval_after if eval_after is not None else None)

    # 1. allowed_mate — you allowed checkmate
    if ue_after is not None and ue_after <= -9000:
        return "allowed_mate"

    # 2. missed_mate — you had mate, didn't take it
    if ue_before is not None and ue_before >= 9000 and (ue_after is None or ue_after < 9000):
        return "missed_mate"

    # 3-4. one_move_blunder / walked_into_tactic (via PV material loss)
    pv_result = _pv_material_loss(move_data, user_color)
    if pv_result:
        return pv_result

    # 7. missed_free_material — best move captures undefended piece
    if _missed_free_material(move_data):
        return "missed_free_material"

    # 15. opening_knowledge — early queen principle (only one verified)
    if _early_queen(move_data):
        return "opening_knowledge"

    # 10. endgame_technique — mistakes in pure endgame (queens off, few pieces)
    try:
        if not fen_before:
            return "(deferred)"
        board = chess.Board(fen_before)
        queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
        other_pieces = _piece_count_for_endgame(board)
        if queens == 0 and other_pieces <= 6:
            return "endgame_technique"
    except Exception:
        pass

    # Everything else defers to Claude (needs positional reasoning)
    # bad_trade, missed_tactic, conversion, king_safety, pawn_structure,
    # piece_activity, calculation_depth, ignore_threat
    return "(deferred)"


def enrich_move_with_classification(move_data: Dict[str, Any], user_color: str) -> Dict[str, Any]:
    """
    Add move_classification field to a move_data dict.

    Returns the enriched dict with "move_classification" field added.
    """
    classification = classify_move(move_data, user_color)
    result = dict(move_data)
    if classification:
        result["move_classification"] = classification
    return result
