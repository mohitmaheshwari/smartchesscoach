"""
Coaching Answer Generator

Turns raw Stockfish analysis into coaching-quality explanations.
Instead of "4.2 pawns worse", explains WHY in human terms:
- What the user was probably thinking
- What actually happens after their move
- The principle they should learn

Also detects the user's thinking pattern from their question,
which is stored as coaching data for personalization.
"""

import chess
from typing import Dict, Any, Optional, List


# Piece values for material counting
PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0
}

PIECE_NAMES = {
    chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
    chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"
}


def analyze_move_character(board: chess.Board, move_san: str) -> Dict[str, Any]:
    """
    Analyze what a move DOES — capture, trade, check, develop, etc.
    Returns a description of the move's character.
    """
    try:
        move = board.parse_san(move_san)
    except (ValueError, chess.IllegalMoveError, chess.AmbiguousMoveError):
        return {"type": "unknown"}

    result = {
        "type": "quiet",
        "is_capture": board.is_capture(move),
        "gives_check": board.gives_check(move),
        "piece_moved": PIECE_NAMES.get(board.piece_at(move.from_square).piece_type, "piece"),
        "piece_moved_type": board.piece_at(move.from_square).piece_type,
    }

    if result["is_capture"]:
        captured = board.piece_at(move.to_square)
        if captured:
            result["type"] = "capture"
            result["captured_piece"] = PIECE_NAMES.get(captured.piece_type, "piece")
            result["captured_value"] = PIECE_VALUES.get(captured.piece_type, 0)
            result["mover_value"] = PIECE_VALUES.get(result["piece_moved_type"], 0)

            # Is this a trade (same value piece)?
            if result["captured_value"] == result["mover_value"]:
                result["is_trade"] = True
            # Is this winning material?
            elif result["captured_value"] > result["mover_value"]:
                result["is_winning_capture"] = True
            else:
                result["is_losing_capture"] = True

    # Check if it attacks something valuable
    board_after = board.copy()
    board_after.push(move)
    attacked_pieces = []
    for sq in chess.SQUARES:
        if board_after.is_attacked_by(board.turn, sq):
            piece = board_after.piece_at(sq)
            if piece and piece.color != board.turn:
                attacked_pieces.append(PIECE_NAMES.get(piece.piece_type, "piece"))
    if attacked_pieces:
        result["attacks_after"] = attacked_pieces

    return result


def trace_material_change(board: chess.Board, pv_moves: List[str], depth: int = 4) -> Dict[str, Any]:
    """
    Walk the PV line and track material changes.
    Detects: recaptures, trades, material loss sequences.
    """
    sim = board.copy()
    material_events = []
    player_color = board.turn

    for i, san in enumerate(pv_moves[:depth]):
        try:
            move = sim.parse_san(san)
        except (ValueError, chess.IllegalMoveError, chess.AmbiguousMoveError):
            break

        if sim.is_capture(move):
            captured = sim.piece_at(move.to_square)
            mover = sim.piece_at(move.from_square)
            if captured and mover:
                side = "player" if sim.turn == player_color else "opponent"
                material_events.append({
                    "ply": i,
                    "san": san,
                    "side": side,
                    "captures": PIECE_NAMES.get(captured.piece_type, "piece"),
                    "with": PIECE_NAMES.get(mover.piece_type, "piece"),
                    "value_gained": PIECE_VALUES.get(captured.piece_type, 0),
                    "value_risked": PIECE_VALUES.get(mover.piece_type, 0),
                })

        sim.push(move)

    # Calculate net material change for player
    net = 0
    for ev in material_events:
        if ev["side"] == "player":
            net += ev["value_gained"]
        else:
            net -= ev["value_gained"]

    return {
        "events": material_events,
        "net_material": net,
        "is_trade_sequence": len(material_events) >= 2 and abs(net) <= 1,
        "player_loses_material": net < -1,
        "player_gains_material": net > 1,
    }


def detect_thinking_pattern(
    board: chess.Board,
    user_move_san: str,
    better_move_san: Optional[str],
    move_char: Dict,
    eval_diff: int,
) -> Dict[str, Any]:
    """
    Detect what the user was probably thinking when they asked about this move.
    Returns a thinking pattern classification + human description.
    """
    pattern = {
        "id": "unknown",
        "label": "Unknown",
        "description": "The user considered an alternative move.",
        "coaching_signal": "neutral",
    }

    abs_diff = abs(eval_diff)

    # Check if the piece gets immediately recaptured (short calculation)
    try:
        move = board.parse_san(user_move_san)
        sim = board.copy()
        sim.push(move)
        for opp_move in sim.legal_moves:
            if opp_move.to_square == move.to_square and sim.is_capture(opp_move):
                if abs_diff > 150:
                    pattern = {
                        "id": "short_calculation",
                        "label": "Short Calculation",
                        "description": "You're calculating one step but missing the reply. After you move there, can your opponent just take your piece? Always check.",
                        "coaching_signal": "concerning",
                    }
                    break
    except Exception:
        pass

    # Only continue to other patterns if we haven't found one yet
    if pattern["id"] == "unknown":
        # Capture-based patterns
        if move_char.get("is_capture"):
            if move_char.get("is_trade"):
                pattern = {
                    "id": "trade_seeking",
                    "label": "Trade Seeking",
                    "description": "You're thinking about trading pieces. Good — but make sure you're trading in the RIGHT direction.",
                    "coaching_signal": "neutral" if abs_diff < 100 else "concerning",
                }
            elif move_char.get("captured_piece") == "pawn":
                if abs_diff > 200:
                    pattern = {
                        "id": "pawn_grabbing",
                        "label": "Pawn Grabbing",
                        "description": "You see a free pawn and want to take it. But is it really free? Check what happens AFTER the capture.",
                        "coaching_signal": "concerning",
                    }
                else:
                    pattern = {
                        "id": "material_awareness",
                        "label": "Material Awareness",
                        "description": "You spotted a capture. That's good tactical awareness.",
                        "coaching_signal": "positive",
                    }
            elif move_char.get("is_winning_capture"):
                pattern = {
                    "id": "tactical_temptation",
                    "label": "Tactical Temptation",
                    "description": "You see a big capture. But winning material isn't always winning — check the consequences.",
                    "coaching_signal": "concerning" if abs_diff > 150 else "neutral",
                }
            else:
                pattern = {
                    "id": "capture_instinct",
                    "label": "Capture Instinct",
                    "description": "You're drawn to captures. That's natural, but the best move isn't always a capture.",
                    "coaching_signal": "neutral",
                }

        # Check-based patterns
        elif move_char.get("gives_check"):
            if abs_diff > 150:
                pattern = {
                    "id": "check_first",
                    "label": "Check-First Mentality",
                    "description": "You see a check and want to play it. But 'always check, it might be mate' is a beginner trap. Many checks just waste time.",
                    "coaching_signal": "concerning",
                }
            else:
                pattern = {
                    "id": "check_awareness",
                    "label": "Check Awareness",
                    "description": "You spotted a check. That's good — checks are forcing moves worth considering.",
                    "coaching_signal": "positive",
                }

        # Development / quiet move patterns
        elif move_char.get("type") == "quiet":
            if abs_diff < 50:
                pattern = {
                    "id": "positional_sense",
                    "label": "Positional Sense",
                    "description": "You're thinking about improving your pieces. That shows good positional understanding.",
                    "coaching_signal": "positive",
                }
            else:
                pattern = {
                    "id": "positional_misread",
                    "label": "Positional Misread",
                    "description": "This looks natural but misses something concrete. Always check for tactics before playing a quiet move.",
                    "coaching_signal": "concerning",
                }

    # Severity adjustment
    if abs_diff > 300:
        pattern["severity"] = "major"
    elif abs_diff > 100:
        pattern["severity"] = "moderate"
    else:
        pattern["severity"] = "minor"

    return pattern


def generate_coaching_answer(
    user_move: str,
    better_move: Optional[str],
    user_analysis: Optional[Dict],
    better_analysis: Optional[Dict],
    board: chess.Board,
    eval_diff: int,
) -> str:
    """
    Generate a coaching-quality answer instead of raw eval dump.
    """
    move_char = analyze_move_character(board, user_move)
    parts = []

    abs_diff = abs(eval_diff)

    # Parse the user's actual move to get from/to squares
    try:
        user_chess_move = board.parse_san(user_move)
        user_to_sq = user_chess_move.to_square
        user_piece = board.piece_at(user_chess_move.from_square)
        user_piece_name = PIECE_NAMES.get(user_piece.piece_type, "piece") if user_piece else "piece"
    except Exception:
        user_to_sq = None
        user_piece_name = "piece"

    # 1. Acknowledge what they were thinking
    if move_char.get("is_capture"):
        captured = move_char.get("captured_piece", "piece")
        parts.append(f"I see — you want to capture the {captured} with {user_move}.")
    elif move_char.get("gives_check"):
        parts.append("You see a check — that's always worth considering.")
    else:
        # Check if the user THINKS it's a capture (move has 'x') but square is empty
        if "x" in user_move:
            parts.append(f"You're looking at playing {user_move}.")
        else:
            parts.append(f"You're considering {user_move}.")

    # 2. What ACTUALLY happens — trace the PV
    piece_recaptured = False
    if user_analysis and user_analysis.get("pv"):
        pv = user_analysis["pv"]
        mat_trace = trace_material_change(board, [user_move] + pv, depth=6)

        # Detect the "piece gets immediately recaptured" pattern
        opponent_first = pv[0] if pv else None
        piece_recaptured = False
        if opponent_first and user_to_sq is not None:
            try:
                sim = board.copy()
                sim.push(board.parse_san(user_move))
                opp_move = sim.parse_san(opponent_first)
                if opp_move.to_square == user_to_sq and sim.is_capture(opp_move):
                    piece_recaptured = True
            except Exception:
                pass

        if piece_recaptured:
            if move_char.get("is_capture"):
                # User captures, then opponent recaptures — it's a trade
                captured = move_char.get("captured_piece", "piece")
                parts.append(
                    f"But after {user_move}, your opponent recaptures with {opponent_first}. "
                    f"You take a {captured} but lose your {user_piece_name} — "
                )
                net = mat_trace["net_material"]
                if net < -1:
                    parts.append(f"and you come out {abs(net)} points worse.")
                elif abs(net) <= 1:
                    parts.append("it's an even trade, but you end up in a worse position.")
                else:
                    parts.append("actually a favorable exchange!")
            else:
                # User moves piece to square, opponent captures it
                # Special case: pawn exchange (d5 exd5 — both sides lose a pawn)
                opp_is_pawn_capture = False
                try:
                    sim = board.copy()
                    sim.push(board.parse_san(user_move))
                    opp_move_obj = sim.parse_san(opponent_first)
                    opp_mover = sim.piece_at(opp_move_obj.from_square)
                    if opp_mover and opp_mover.piece_type == chess.PAWN and user_piece_name == "pawn":
                        opp_is_pawn_capture = True
                except Exception:
                    pass

                if opp_is_pawn_capture:
                    # Pawn exchange — material is even, but position gets worse
                    rest_pv = pv[1:4] if len(pv) > 1 else []
                    parts.append(
                        f"After {user_move} {opponent_first}, the pawns are exchanged — material is even. "
                        f"But the position after {' '.join(rest_pv)} is much worse for you."
                    )
                else:
                    parts.append(
                        f"But your opponent immediately plays {opponent_first}, "
                        f"capturing your {user_piece_name}. "
                        f"You lose a {user_piece_name} for nothing."
                    )

        elif mat_trace["is_trade_sequence"]:
            events = mat_trace["events"]
            if len(events) >= 2:
                parts.append(
                    f"After {user_move}, your opponent plays {pv[0]}. "
                    f"It's a trade — you take a {events[0]['captures']} "
                    f"but they take back your {events[1]['captures']}. You don't actually gain anything."
                )
            else:
                parts.append(
                    f"After {user_move} {pv[0]}, the position simplifies but you don't gain material."
                )

        elif mat_trace["player_loses_material"]:
            parts.append(
                f"After {user_move}, the continuation {' '.join(pv[:3])} "
                f"leaves you down material."
            )

        elif mat_trace["player_gains_material"] and abs_diff < 100:
            parts.append(f"After {user_move}, you do win some material. It's not bad!")

        else:
            if abs_diff > 200:
                parts.append(
                    f"After {user_move}, your opponent responds {pv[0]} and your position gets significantly worse."
                )
            elif abs_diff > 50:
                parts.append(
                    f"After {user_move} {pv[0]}, your position is slightly worse."
                )

    # 3. Why the better move is better
    if better_move and better_analysis and better_analysis.get("pv"):
        better_char = analyze_move_character(board, better_move)
        better_pv = better_analysis["pv"]

        if better_char.get("type") == "capture":
            parts.append(
                f"{better_move} is better — it wins material cleanly."
            )
        elif better_char.get("gives_check"):
            parts.append(f"{better_move} gives check and gains initiative.")
        elif better_char.get("attacks_after"):
            targets = better_char["attacks_after"]
            high_value = [t for t in targets if t in ("queen", "rook", "bishop", "knight")]
            if high_value:
                parts.append(
                    f"{better_move} is better because it attacks the {high_value[0]}, "
                    f"forcing your opponent to react to YOUR threat."
                )
            else:
                parts.append(f"{better_move} is more active, putting pressure on your opponent.")
        else:
            if abs_diff > 200:
                parts.append(
                    f"{better_move} keeps your position strong. "
                    f"The line continues: {' '.join(better_pv[:3])}."
                )
            else:
                parts.append(f"{better_move} is slightly more accurate here.")

    # 4. The principle / takeaway
    if abs_diff > 300:
        if piece_recaptured:
            parts.append(
                "Principle: Before moving a piece to a square, check: "
                "can my opponent just take it? If yes, make sure you get something in return."
            )
        elif move_char.get("is_capture"):
            parts.append(
                "Principle: Before capturing, always check if your opponent can recapture "
                "or create a stronger threat."
            )
        elif move_char.get("gives_check"):
            parts.append("Principle: Not every check is good. A check that doesn't lead anywhere wastes a move.")
        else:
            parts.append(
                "Principle: Before committing, ask: 'What does my opponent do after this?'"
            )
    elif abs_diff > 100:
        parts.append("Tip: Before your move, always ask: 'What is my opponent's BEST reply?'")

    return " ".join(parts)
