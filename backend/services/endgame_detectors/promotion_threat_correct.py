"""
Correct Promotion Threat Detector - Properly identifies threats and defenses.

Core logic:
1. Find opponent pawns that WILL promote in the near future (2-4 moves)
2. Check if we defend the promotion square BEFORE the move
3. Check if we defend the promotion square AFTER the move
4. Classify the move based on this change
"""

import chess
from typing import Optional, List, Tuple


def identify_promotion_threats(board: chess.Board, color: chess.Color) -> List[dict]:
    """
    Find opponent pawns that threaten to promote soon.

    Returns list of {pawn_sq, promotion_sq, moves_to_promotion, is_defended_now}
    """
    opponent_color = not color
    threats = []

    for pawn_sq in board.pieces(chess.PAWN, opponent_color):
        pawn_rank = chess.square_rank(pawn_sq)
        pawn_file = chess.square_file(pawn_sq)

        # Calculate moves until promotion
        if opponent_color == chess.WHITE:
            moves_to_promotion = 7 - pawn_rank
            promotion_sq = chess.square(pawn_file, 7)
        else:  # BLACK
            moves_to_promotion = pawn_rank
            promotion_sq = chess.square(pawn_file, 0)

        # Only care if pawn will promote in next 3-4 moves
        if moves_to_promotion > 4:
            continue

        # Is promotion square defended by us?
        is_defended = board.is_attacked_by(color, promotion_sq)

        threats.append({
            "pawn_sq": pawn_sq,
            "promotion_sq": promotion_sq,
            "moves_to_promotion": moves_to_promotion,
            "is_defended_now": is_defended,
            "pawn_rank": pawn_rank,
            "pawn_file": pawn_file,
        })

    return threats


def detect_promotion_threat_move(
    board: chess.Board,
    move: chess.Move,
    user_color: chess.Color,
) -> Optional[str]:
    """
    Analyze how the move affects promotion threat defense.

    Returns:
        "defends"    → Move improves defense against promotion threats
        "allows"     → Move loses defense, allows promotion
        "maintains"  → Move maintains defense status
        None         → No relevant promotion threats
    """

    # Identify threats in current position
    threats = identify_promotion_threats(board, user_color)

    if not threats:
        return None  # No promotion threats to worry about

    # Make the move and check if threats are still defended
    board.push(move)

    # For each threat, check if we still defend after the move
    changes = []

    for threat in threats:
        promotion_sq = threat["promotion_sq"]
        was_defended = threat["is_defended_now"]
        is_defended_after = board.is_attacked_by(user_color, promotion_sq)
        moves_to_promotion = threat["moves_to_promotion"]

        if was_defended and not is_defended_after:
            # We lost defense - this is bad
            changes.append("lost_defense")
        elif not was_defended and is_defended_after:
            # We gained defense - this is good
            changes.append("gained_defense")
        elif is_defended_after and not was_defended:
            # We just defended something that wasn't defended
            changes.append("gained_defense")
        elif is_defended_after and was_defended:
            # Still defending
            changes.append("maintains_defense")
        elif not is_defended_after:
            # Pawn is undefended after our move
            if moves_to_promotion <= 2:
                # Pawn is close to queening and undefended
                changes.append("allows_promotion")
            elif was_defended and not is_defended_after:
                # We lost defense
                changes.append("lost_defense")

    board.pop()

    # Determine verdict based on changes
    if "lost_defense" in changes or "allows_promotion" in changes:
        return "allows"
    elif "gained_defense" in changes:
        return "defends"
    elif "maintains_defense" in changes:
        return "maintains"

    # Edge case: If there was an undefended threat 3+ moves away and we didn't defend it,
    # and it's still undefended after our move, we're allowing it to advance
    for threat in threats:
        if not threat["is_defended_now"] and threat["moves_to_promotion"] <= 3:
            # Was this threat defended after the move?
            board.push(move)
            is_defended_after = board.is_attacked_by(user_color, threat["promotion_sq"])
            board.pop()

            if not is_defended_after:
                # We left an imminent promotion threat undefended
                return "allows"

    return None


def build_promotion_threat_caption(
    board: chess.Board,
    move: chess.Move,
    move_san: str,
    user_color: chess.Color,
    detection: Optional[str],
    eval_before: int,
    eval_after: int,
) -> Optional[str]:
    """Build a caption explaining the promotion threat impact."""

    if not detection:
        return None

    threats = identify_promotion_threats(board, user_color)
    if not threats:
        return None

    # Get the most critical threat
    most_critical = min(threats, key=lambda t: t["moves_to_promotion"])
    promotion_sq_name = chess.square_name(most_critical["promotion_sq"])
    pawn_sq_name = chess.square_name(most_critical["pawn_sq"])
    moves_left = most_critical["moves_to_promotion"]

    opponent_color = not user_color
    pawn_owner = "Black" if opponent_color == chess.BLACK else "White"

    if detection == "allows":
        cp_loss = eval_before - eval_after
        if moves_left <= 1 and cp_loss > 100:
            return (
                f"{move_san} allows {pawn_owner}'s pawn on {pawn_sq_name} to promote. "
                f"The promotion square {promotion_sq_name} is no longer defended."
            )
        else:
            return (
                f"{move_san} removes defense of {promotion_sq_name}. "
                f"{pawn_owner}'s pawn on {pawn_sq_name} is now threatening."
            )

    elif detection == "defends":
        return (
            f"{move_san} controls {promotion_sq_name}, stopping {pawn_owner}'s pawn from promoting. "
            f"Good defensive placement."
        )

    elif detection == "maintains":
        return (
            f"{move_san} keeps {promotion_sq_name} defended against {pawn_owner}'s pawn on {pawn_sq_name}."
        )

    return None
