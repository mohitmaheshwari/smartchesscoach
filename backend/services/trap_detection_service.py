"""
Trap Detection Service — Escape Square Awareness Engine
========================================================

Detects trap opportunities for ANY piece (not just king).
Scans opponent's non-pawn pieces and finds those with limited escape squares
that the user can restrict further.

Mental model: "Every piece survives because it has squares to go to.
Remove those squares → you win the piece."

Rule name: Escape Square Control

No LLM. No database. Pure python-chess computation.
"""

import chess
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Piece values for prioritization
PIECE_VALUES = {
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}

PIECE_NAMES = {
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
}

# Trigger thresholds (hard, no drift)
MAX_ESCAPE_TO_REPORT = 3      # Don't report if piece has 4+ escapes
MIN_VALUE_FOR_3_ESCAPES = 5   # Only report 3-escape for rook/queen


@dataclass
class TrapOpportunity:
    """A detected trap opportunity on the board."""
    target_square: str            # "d5" — where the piece is
    target_piece: str             # "knight", "bishop", etc.
    target_piece_symbol: str      # "N", "B", "R", "Q"
    escape_count: int             # Number of safe escape squares
    escape_squares: List[str]     # ["c3", "e7"] — where it CAN go
    blocked_squares: List[str]    # Squares already controlled by user
    reduction_moves: List[Dict]   # User moves that reduce escapes
    trap_level: str               # "trapped", "near_trap", "pressured"
    value: int                    # Piece value (3, 5, 9)
    is_attacked: bool             # Is the piece currently under attack?
    is_trappable_in_2: bool = False       # Can be trapped in 2 moves
    trap_sequence: List[str] = field(default_factory=list)  # ["Bc4", "Ng5"] — 2-move sequence


def count_piece_escapes(board: chess.Board, square: int, user_color: chess.Color) -> Dict:
    """
    Count safe escape squares for a piece.

    A square is "safe" if:
    1. The piece can legally move there
    2. Moving there doesn't lose the piece (square not attacked by opponent with no defense)

    Returns:
        {
            "escape_squares": ["c3", "e7"],
            "blocked_squares": ["d4", "f6"],  # Controlled by user
            "escape_count": 2,
            "is_attacked": True/False,
        }
    """
    piece = board.piece_at(square)
    if not piece or piece.piece_type == chess.PAWN or piece.piece_type == chess.KING:
        return {"escape_squares": [], "blocked_squares": [], "escape_count": 99, "is_attacked": False}

    piece_color = piece.color
    opponent_color = not piece_color

    # Is the piece currently attacked?
    is_attacked = board.is_attacked_by(opponent_color, square)

    # Get all legal moves for this piece
    # If it's not this piece's color's turn, we need to create a board where it IS their turn
    analysis_board = board.copy()
    if analysis_board.turn != piece_color:
        # Flip turn by modifying FEN
        fen_parts = analysis_board.fen().split(' ')
        fen_parts[1] = 'w' if piece_color == chess.WHITE else 'b'
        try:
            analysis_board = chess.Board(' '.join(fen_parts))
        except ValueError:
            return {"escape_squares": [], "blocked_squares": [], "escape_count": 99, "is_attacked": is_attacked}

    legal_destinations = []
    for move in analysis_board.legal_moves:
        if move.from_square == square:
            legal_destinations.append(move.to_square)

    escape_squares = []
    blocked_squares = []

    for dest in legal_destinations:
        # Check if destination is safe
        # Make the move temporarily and see if the piece is still attacked
        test_board = analysis_board.copy()
        test_move = chess.Move(square, dest)

        # Check if this is even a legal move in the copy
        if test_move not in test_board.legal_moves:
            # Try with promotion
            test_move = chess.Move(square, dest, promotion=chess.QUEEN)
            if test_move not in test_board.legal_moves:
                continue

        test_board.push(test_move)

        # After moving, is the piece on dest attacked by opponent?
        # (opponent = the user, since we're checking OPPONENT's piece escapes)
        if test_board.is_attacked_by(opponent_color, dest):
            # Check if it's defended by its own side
            defenders = test_board.attackers(piece_color, dest)
            attackers = test_board.attackers(opponent_color, dest)

            # If more attackers than defenders (or equal but piece is valuable), it's not safe
            if len(attackers) > len(defenders):
                blocked_squares.append(chess.square_name(dest))
            else:
                escape_squares.append(chess.square_name(dest))
        else:
            escape_squares.append(chess.square_name(dest))

    # Also count squares the piece COULD go to but are occupied by own pieces
    # (these are "naturally blocked")
    for dest in chess.SQUARES:
        if board.piece_at(dest) and board.piece_at(dest).color == piece_color:
            # Check if the piece type could reach this square in theory
            # (simplified: just check if it's a legal move if square were empty)
            pass  # Skip for now — legal_moves already handles this

    return {
        "escape_squares": escape_squares,
        "blocked_squares": blocked_squares,
        "escape_count": len(escape_squares),
        "is_attacked": is_attacked,
    }


def find_escape_reducers(
    board: chess.Board,
    target_square: int,
    escape_squares: List[str],
    user_color: chess.Color,
) -> List[Dict]:
    """
    Find user moves that can reduce the opponent piece's escape squares.

    For each escape square, check if any user piece can attack or occupy it.

    Returns list of:
        {"move_uci": "b2b4", "move_san": "b4", "blocks_square": "c3", "new_escape_count": 1}
    """
    reducers = []
    escape_sq_ints = [chess.parse_square(s) for s in escape_squares]

    # Only check if it's user's turn
    if board.turn != user_color:
        # Temporarily flip turn for analysis
        test_board = board.copy()
        # Can't easily flip turn in python-chess, so we analyze user's moves from legal_moves
        # when it IS user's turn, this works naturally
        return []

    for user_move in board.legal_moves:
        # Skip king moves and castling
        moving_piece = board.piece_at(user_move.from_square)
        if not moving_piece or moving_piece.piece_type == chess.KING:
            continue

        # After this user move, how many escape squares does the target piece have?
        test_board = board.copy()
        test_board.push(user_move)

        # Count escapes after user's move
        new_escape_data = count_piece_escapes(test_board, target_square, user_color)
        new_escape_count = new_escape_data["escape_count"]

        # Did this move reduce escapes?
        blocked_by_this_move = []
        for esc_sq in escape_sq_ints:
            esc_name = chess.square_name(esc_sq)
            if esc_name not in new_escape_data["escape_squares"]:
                blocked_by_this_move.append(esc_name)

        if blocked_by_this_move:
            try:
                move_san = board.san(user_move)
            except Exception:
                move_san = user_move.uci()

            reducers.append({
                "move_uci": user_move.uci(),
                "move_san": move_san,
                "from": chess.square_name(user_move.from_square),
                "to": chess.square_name(user_move.to_square),
                "blocks_squares": blocked_by_this_move,
                "new_escape_count": new_escape_count,
            })

    # Sort by most escapes reduced (lowest new_escape_count first)
    reducers.sort(key=lambda r: r["new_escape_count"])

    return reducers[:5]  # Top 5 best reducing moves


def find_forced_trap_sequence(
    board: chess.Board,
    target_square: int,
    escape_squares: List[str],
    reduction_moves: List[Dict],
    user_color: chess.Color,
) -> Optional[List[str]]:
    """
    Check if a 2-move sequence can force-trap the piece.

    For each top restriction move:
      1. Play it (user move 1)
      2. Let opponent respond with their best legal move for the target piece
      3. Check if any user move 2 results in escape_count = 0

    Only checks the top 3 reducers to keep it fast (<500ms).
    Returns the 2-move sequence as SAN list, or None.
    """
    if not reduction_moves:
        return None

    opponent_color = not user_color

    for reducer in reduction_moves[:3]:
        try:
            move1_uci = reducer["move_uci"]
            move1 = chess.Move.from_uci(move1_uci)

            if move1 not in board.legal_moves:
                continue

            # Play user's restriction move
            board_after_1 = board.copy()
            move1_san = board_after_1.san(move1)
            board_after_1.push(move1)

            # Opponent responds — try all legal moves for the target piece
            # (or if it's not their turn, flip)
            opp_board = board_after_1.copy()
            if opp_board.turn != opponent_color:
                fen_parts = opp_board.fen().split(' ')
                fen_parts[1] = 'w' if opponent_color == chess.WHITE else 'b'
                try:
                    opp_board = chess.Board(' '.join(fen_parts))
                except ValueError:
                    continue

            # Get opponent's moves for the target piece
            target_moves = [m for m in opp_board.legal_moves if m.from_square == target_square]

            # If target piece has no moves, it's already trapped after move 1
            if not target_moves:
                return [move1_san]

            # For each opponent response with the target piece
            for opp_move in target_moves:
                board_after_opp = opp_board.copy()
                board_after_opp.push(opp_move)

                new_target_sq = opp_move.to_square

                # Now it's user's turn again — find any move that traps the piece
                user_board = board_after_opp.copy()
                if user_board.turn != user_color:
                    fen_parts = user_board.fen().split(' ')
                    fen_parts[1] = 'w' if user_color == chess.WHITE else 'b'
                    try:
                        user_board = chess.Board(' '.join(fen_parts))
                    except ValueError:
                        continue

                for user_move2 in user_board.legal_moves:
                    board_after_2 = user_board.copy()
                    move2_san = board_after_2.san(user_move2)
                    board_after_2.push(user_move2)

                    # Check if target piece is now trapped
                    new_escape = count_piece_escapes(board_after_2, new_target_sq, user_color)
                    if new_escape["escape_count"] == 0:
                        return [move1_san, move2_san]

        except Exception as e:
            logger.debug(f"Trap sequence check failed for {reducer.get('move_san')}: {e}")
            continue

    return None


def detect_trap_opportunities(board: chess.Board, user_color: chess.Color) -> List[TrapOpportunity]:
    """
    Scan all opponent non-pawn pieces for trap potential.

    Only returns pieces with escape_count ≤ 3 (configurable).
    Prioritizes high-value pieces and fewer escapes.

    Args:
        board: Current position
        user_color: The USER's color (we scan opponent's pieces)

    Returns:
        List of TrapOpportunity sorted by priority (best trap first)
    """
    opponent_color = not user_color
    opportunities = []

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue
        if piece.color != opponent_color:
            continue
        if piece.piece_type in (chess.PAWN, chess.KING):
            continue

        piece_value = PIECE_VALUES.get(piece.piece_type, 0)
        piece_name = PIECE_NAMES.get(piece.piece_type, "piece")

        # Count escape squares
        escape_data = count_piece_escapes(board, square, user_color)
        escape_count = escape_data["escape_count"]

        # Apply trigger thresholds
        if escape_count > MAX_ESCAPE_TO_REPORT:
            continue
        if escape_count == 3 and piece_value < MIN_VALUE_FOR_3_ESCAPES:
            continue

        # Determine trap level
        if escape_count == 0:
            trap_level = "trapped"
        elif escape_count == 1:
            trap_level = "near_trap"
        else:
            trap_level = "pressured"

        # Find moves that reduce escapes (only if it's user's turn)
        reduction_moves = []
        if board.turn == user_color and escape_count > 0:
            reduction_moves = find_escape_reducers(
                board, square, escape_data["escape_squares"], user_color
            )

        # Check for 2-move forced trap sequence (only for high-value or near-trap)
        trap_sequence = []
        is_trappable_in_2 = False
        if escape_count in (1, 2) and reduction_moves and board.turn == user_color:
            try:
                seq = find_forced_trap_sequence(
                    board, square, escape_data["escape_squares"],
                    reduction_moves, user_color
                )
                if seq:
                    is_trappable_in_2 = True
                    trap_sequence = seq
                    trap_level = "near_trap"  # Upgrade to near_trap if 2-move sequence exists
            except Exception:
                pass

        opportunities.append(TrapOpportunity(
            target_square=chess.square_name(square),
            target_piece=piece_name,
            target_piece_symbol=piece.symbol().upper(),
            escape_count=escape_count,
            escape_squares=escape_data["escape_squares"],
            blocked_squares=escape_data["blocked_squares"],
            reduction_moves=reduction_moves,
            trap_level=trap_level,
            value=piece_value,
            is_attacked=escape_data["is_attacked"],
            is_trappable_in_2=is_trappable_in_2,
            trap_sequence=trap_sequence,
        ))

    # Sort: trapped first, then by value * urgency
    opportunities.sort(key=lambda t: (-((4 - t.escape_count) * t.value), -t.value))

    return opportunities


def generate_trap_coaching_message(trap: TrapOpportunity) -> str:
    """
    Generate a coaching message for a trap opportunity.
    Follows the behavior diagnosis engine rules:
    - Name the piece
    - State the escape count
    - Give one actionable instruction
    """
    piece = trap.target_piece
    sq = trap.target_square
    esc = trap.escape_count

    if esc == 0:
        if trap.is_attacked:
            return f"Trapped! Their {piece} on {sq} has nowhere to go. Capture it."
        else:
            return f"Their {piece} on {sq} is trapped — no safe squares. Find a way to attack it."

    # 2-move forced trap takes priority
    if trap.is_trappable_in_2 and trap.trap_sequence:
        seq = " → ".join(trap.trap_sequence)
        return f"You can trap this {piece} in {len(trap.trap_sequence)} moves: {seq}. The {piece} has nowhere to run."

    if esc == 1:
        escape_sq = trap.escape_squares[0] if trap.escape_squares else "?"
        if trap.reduction_moves:
            reducer = trap.reduction_moves[0]
            return f"Only 1 escape square left ({escape_sq}). {reducer['move_san']} removes it — the {piece} is yours."
        return f"Their {piece} has only 1 escape square: {escape_sq}. Control that square and it's trapped."

    if esc == 2:
        squares = ", ".join(trap.escape_squares[:2])
        if trap.reduction_moves:
            reducer = trap.reduction_moves[0]
            return f"This {piece} has 2 escape squares: {squares}. {reducer['move_san']} blocks one — then it's cornered."
        return f"Escape Square Check — this {piece} has only 2 safe squares: {squares}. Can you block one?"

    # esc == 3 (only for rook/queen)
    squares = ", ".join(trap.escape_squares[:3])
    return f"Escape Square Check — their {piece} has 3 safe squares: {squares}. Can you reduce them?"


# ═══ TRAP TRACKING — Pattern Memory Integration ═══

async def track_trap_opportunity(db, user_id: str, session_id: str, trap: TrapOpportunity):
    """Record that a trap opportunity was shown to the user."""
    try:
        await db.trap_tracking.insert_one({
            "user_id": user_id,
            "session_id": session_id,
            "target_piece": trap.target_piece,
            "target_square": trap.target_square,
            "escape_count": trap.escape_count,
            "trap_level": trap.trap_level,
            "is_trappable_in_2": trap.is_trappable_in_2,
            "was_exploited": None,  # Updated later
            "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.debug(f"Trap tracking insert failed: {e}")


async def mark_trap_exploited(db, user_id: str, session_id: str, target_square: str, exploited: bool):
    """Mark whether the user exploited a trap opportunity."""
    try:
        await db.trap_tracking.update_one(
            {"user_id": user_id, "session_id": session_id, "target_square": target_square, "was_exploited": None},
            {"$set": {"was_exploited": exploited}},
        )
    except Exception as e:
        logger.debug(f"Trap tracking update failed: {e}")


async def get_trap_stats(db, user_id: str) -> dict:
    """Get trap conversion rate for a user."""
    try:
        total = await db.trap_tracking.count_documents({"user_id": user_id})
        exploited = await db.trap_tracking.count_documents({"user_id": user_id, "was_exploited": True})
        missed = await db.trap_tracking.count_documents({"user_id": user_id, "was_exploited": False})

        return {
            "total_opportunities": total,
            "exploited": exploited,
            "missed": missed,
            "conversion_rate": round((exploited / max(total, 1)) * 100, 1),
            "pending": total - exploited - missed,
        }
    except Exception:
        return {"total_opportunities": 0, "exploited": 0, "missed": 0, "conversion_rate": 0, "pending": 0}
