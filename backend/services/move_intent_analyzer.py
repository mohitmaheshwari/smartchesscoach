"""
Move Intent Analyzer
=====================

Given a board position and a move, figure out WHAT the player was trying to do.
No guessing, no generic options — analyze the actual board.

Returns:
- What the move accomplishes (attack, defend, develop, push, castle, trade)
- Whether the intent is reasonable
- If bad: why it doesn't work + what would achieve the same goal better
"""

import chess
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MoveIntent:
    """What the player was trying to do with their move."""
    intent: str           # "attack", "defend", "develop", "push", "trade", "retreat", "castle", "unclear"
    target: str           # What they're targeting: "bishop on c5", "control e5", "kingside attack"
    description: str      # "You moved your knight to attack their bishop on c5"
    is_reasonable: bool   # Was this a reasonable idea regardless of execution?
    feedback: str         # Coach response acknowledging their intent


def analyze_move_intent(fen: str, move_san: str, best_move_san: str = "", cp_loss: int = 0) -> MoveIntent:
    """Analyze what a player was trying to do with their move."""
    try:
        board = chess.Board(fen)
        move = board.parse_san(move_san)
    except Exception:
        return MoveIntent("unclear", "", f"You played {move_san}.", False, "Let's look at this position.")

    piece = board.piece_at(move.from_square)
    if not piece:
        return MoveIntent("unclear", "", f"You played {move_san}.", False, "")

    piece_name = _piece_name(piece)
    to_name = chess.square_name(move.to_square)
    user_color = board.turn

    # Make the move to see what happens after
    board_after = board.copy()
    board_after.push(move)

    # ─── 1. CASTLING ───
    if board.is_castling(move):
        return MoveIntent(
            "castle", "king safety",
            "You castled to get your king safe.",
            True,
            "Good — king safety is important. Your rook is also more active now."
        )

    # ─── 2. CAPTURE ───
    captured = board.piece_at(move.to_square)
    if captured:
        captured_name = _piece_name(captured)
        piece_val = _piece_value(piece)
        captured_val = _piece_value(captured)

        if captured_val > piece_val:
            return MoveIntent(
                "trade", f"winning {captured_name}",
                f"You took their {captured_name} with your {piece_name}.",
                True,
                "Good trade — you won material."
            )
        elif captured_val == piece_val:
            return MoveIntent(
                "trade", f"trading {captured_name}",
                f"You traded your {piece_name} for their {captured_name}.",
                cp_loss < 50,
                "Even trade." if cp_loss < 50 else "The trade looks equal, but it helped their position more than yours."
            )
        else:
            return MoveIntent(
                "trade", f"taking {captured_name}",
                f"You gave up your {piece_name} for their {captured_name}.",
                cp_loss < 100,
                "You lost material on this trade." if cp_loss >= 100 else "Interesting sacrifice."
            )

    # ─── 3. CHECK ───
    if board_after.is_check():
        return MoveIntent(
            "attack", "giving check",
            f"You gave check with your {piece_name}.",
            cp_loss < 100,
            "Check forces them to respond." if cp_loss < 100 else "Check, but it wasn't the best one. Sometimes a quiet move is stronger than a check."
        )

    # ─── 4. CREATES A NEW ATTACK on an opponent piece ───
    opp_color = not user_color
    new_attacks = []
    for sq in chess.SQUARES:
        target = board_after.piece_at(sq)
        if target and target.color == opp_color and target.piece_type != chess.KING:
            was_attacked = board.is_attacked_by(user_color, sq)
            now_attacked = board_after.is_attacked_by(user_color, sq)
            now_defended = board_after.is_attacked_by(opp_color, sq)
            if now_attacked and not was_attacked:
                new_attacks.append((sq, target, now_defended))

    if new_attacks:
        # Sort by value — most valuable target first
        new_attacks.sort(key=lambda x: _piece_value(x[1]), reverse=True)
        best_target = new_attacks[0]
        target_name = _piece_name(best_target[1])
        target_sq = chess.square_name(best_target[0])
        target_defended = best_target[2]

        if len(new_attacks) >= 2:
            names = [_piece_name(a[1]) for a in new_attacks[:2]]
            return MoveIntent(
                "attack", f"attacking {names[0]} and {names[1]}",
                f"Your {piece_name} on {to_name} attacks their {names[0]} and {names[1]}.",
                cp_loss < 100,
                "Double attack! Nice." if cp_loss < 100 else "Good idea — attacking two pieces. But there was something even stronger."
            )

        return MoveIntent(
            "attack", f"attacking {target_name} on {target_sq}",
            f"Your {piece_name} is now attacking their {target_name} on {target_sq}.",
            cp_loss < 100,
            f"You're putting pressure on their {target_name}." if cp_loss < 100 else f"I see you're going after their {target_name}. But it's defended — the attack doesn't work."
        )

    # ─── 5. DEFENDING a piece that was under attack ───
    for sq in chess.SQUARES:
        our_piece = board.piece_at(sq)
        if our_piece and our_piece.color == user_color and sq != move.from_square:
            was_defended = board.is_attacked_by(user_color, sq)
            now_defended = board_after.is_attacked_by(user_color, sq)
            is_attacked = board.is_attacked_by(opp_color, sq)
            if is_attacked and now_defended and not was_defended:
                defended_name = _piece_name(our_piece)
                return MoveIntent(
                    "defend", f"defending {defended_name}",
                    f"Your {piece_name} now defends your {defended_name}.",
                    cp_loss < 80,
                    f"Good — you spotted the threat to your {defended_name}." if cp_loss < 80 else "Defending makes sense, but there was a stronger way to deal with this."
                )

    # ─── 6. DEVELOPMENT (minor piece from back rank) ───
    back_rank = 0 if user_color == chess.WHITE else 7
    if piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
        if chess.square_rank(move.from_square) == back_rank:
            to_file = chess.square_file(move.to_square)
            to_rank = chess.square_rank(move.to_square)
            center_dist = abs(to_file - 3.5) + abs(to_rank - 3.5)
            if center_dist <= 3:
                return MoveIntent(
                    "develop", f"developing {piece_name} toward center",
                    f"You brought your {piece_name} into the game, aiming at the center.",
                    cp_loss < 80,
                    "Developing pieces is always good." if cp_loss < 80 else f"Development is the right idea, but this square isn't the best for your {piece_name}."
                )
            return MoveIntent(
                "develop", f"developing {piece_name}",
                f"You brought your {piece_name} out to {to_name}.",
                cp_loss < 100,
                f"Getting pieces out is good, but {to_name} is a bit passive for this piece." if cp_loss >= 50 else "Piece development — good."
            )

    # ─── 7. PAWN PUSH ───
    if piece.piece_type == chess.PAWN:
        to_file = chess.square_file(move.to_square)
        if to_file in [3, 4]:  # d or e file
            return MoveIntent(
                "push", "fighting for the center",
                f"You pushed your pawn to {to_name}, fighting for central space.",
                cp_loss < 80,
                "Central pawn push — good idea." if cp_loss < 80 else "The idea is right — control the center. But the timing wasn't perfect."
            )
        elif to_file <= 2:
            return MoveIntent(
                "push", "queenside expansion",
                "You pushed your pawn on the queenside.",
                cp_loss < 100,
                "Queenside push." if cp_loss < 80 else "Pushing on the side — are you sure the action is there? The center might need attention first."
            )
        else:
            return MoveIntent(
                "push", "kingside push",
                "You pushed your pawn on the kingside.",
                cp_loss < 100,
                "Kingside push — make sure your king is safe first." if cp_loss >= 50 else "Pushing forward."
            )

    # ─── 8. RETREAT ───
    our_rank = chess.square_rank(move.from_square)
    new_rank = chess.square_rank(move.to_square)
    if (user_color == chess.WHITE and new_rank < our_rank) or (user_color == chess.BLACK and new_rank > our_rank):
        return MoveIntent(
            "retreat", f"pulling back {piece_name}",
            f"You moved your {piece_name} back to {to_name}.",
            cp_loss < 80,
            "Sometimes retreat is the right call." if cp_loss < 80 else "Retreating — but was your piece actually in danger? There might have been a more active move."
        )

    # ─── 9. ROOK to open file ───
    if piece.piece_type == chess.ROOK:
        to_file = chess.square_file(move.to_square)
        file_pawns = 0
        for r in range(8):
            sq = chess.square(to_file, r)
            p = board.piece_at(sq)
            if p and p.piece_type == chess.PAWN:
                file_pawns += 1
        if file_pawns == 0:
            return MoveIntent(
                "attack", "rook to open file",
                f"You put your rook on the open {chr(97 + to_file)}-file.",
                cp_loss < 80,
                "Rook on an open file — that's powerful." if cp_loss < 80 else "Open file for the rook — right idea, but there's something more urgent."
            )

    # ─── DEFAULT ───
    return MoveIntent(
        "unclear", "repositioning",
        f"You moved your {piece_name} to {to_name}.",
        cp_loss < 50,
        "Solid move." if cp_loss < 50 else "I'm not sure what you were aiming for here. What's the plan?"
    )


def _piece_name(piece: chess.Piece) -> str:
    names = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
             chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
    return names.get(piece.piece_type, "piece")


def _piece_value(piece: chess.Piece) -> int:
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
              chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
    return values.get(piece.piece_type, 0)
