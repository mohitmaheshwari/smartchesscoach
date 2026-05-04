"""
Move Comparison — explains WHY one move is better than another.

Simulates both moves, runs detectors on both resulting positions,
and finds the differences. All from Stockfish + our detectors.
No LLM. No guessing.

Usage:
    why = compare_moves(board, played_move, best_move, user_color)
    # Returns: {"reason": "Ne5 attacks the rook on f7 which has no protection",
    #           "played_creates": [...], "best_creates": [...]}
"""

import chess
from typing import Optional, Dict, List
import logging

from services.tactical_safety import fork_threat_is_real

logger = logging.getLogger(__name__)

PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


def compare_moves(
    board: chess.Board,
    played_move_san: str,
    best_move_san: str,
    user_color: str,
    pv_after_best: Optional[List[str]] = None,
) -> Optional[Dict]:
    """
    Compare what the played move achieves vs what the best move achieves.
    Returns structured facts about the difference.
    """
    if not best_move_san or played_move_san == best_move_san:
        return None

    try:
        user_color_bool = chess.WHITE if user_color == "white" else chess.BLACK
        opp_color = not user_color_bool

        played_move = board.parse_san(played_move_san)
        best_move = board.parse_san(best_move_san)
    except Exception:
        return None

    # Simulate both positions
    board_after_played = board.copy()
    board_after_played.push(played_move)

    board_after_best = board.copy()
    board_after_best.push(best_move)

    result = {
        "played": played_move_san,
        "best": best_move_san,
        "reasons": [],
    }

    # ─── 1. What does the best move CAPTURE? ───
    best_captures = board.piece_at(best_move.to_square)
    played_captures = board.piece_at(played_move.to_square)

    if best_captures and not played_captures:
        cap_name = chess.piece_name(best_captures.piece_type)
        cap_sq = chess.square_name(best_move.to_square)
        result["reasons"].append(f"{best_move_san} takes the {cap_name} on {cap_sq}")
    elif best_captures and played_captures:
        best_val = PIECE_VALUES.get(best_captures.piece_type, 0)
        played_val = PIECE_VALUES.get(played_captures.piece_type, 0)
        if best_val > played_val:
            result["reasons"].append(
                f"{best_move_san} takes a {chess.piece_name(best_captures.piece_type)} "
                f"(worth more than the {chess.piece_name(played_captures.piece_type)} you took)"
            )

    # ─── 2. Does the best move give check? ───
    if board_after_best.is_check() and not board_after_played.is_check():
        result["reasons"].append(f"{best_move_san} gives check")

    # ─── 3. Does the best move create a fork? ───
    best_fork = _find_fork(board_after_best, user_color_bool, best_move.to_square)
    played_fork = _find_fork(board_after_played, user_color_bool, played_move.to_square)
    if best_fork and not played_fork:
        targets = [chess.piece_name(t) for t in best_fork[:2]]
        result["reasons"].append(
            f"{best_move_san} attacks the {' and '.join(targets)} at the same time"
        )

    # ─── 4. Does the best move attack undefended pieces? ───
    best_attacks = _find_attacks_on_undefended(board_after_best, user_color_bool)
    played_attacks = _find_attacks_on_undefended(board_after_played, user_color_bool)

    new_attacks = [a for a in best_attacks if a not in played_attacks]
    if new_attacks:
        for piece_name, sq_name in new_attacks[:2]:
            result["reasons"].append(
                f"{best_move_san} attacks the {piece_name} on {sq_name} which has no protection"
            )

    # ─── 4b. Does the played move lose castling rights? ───
    played_piece_type = board.piece_at(played_move.from_square)
    if played_piece_type and played_piece_type.piece_type == chess.KING:
        # King moved — lost castling rights
        had_castling = board.has_castling_rights(user_color_bool)
        if had_castling:
            result["reasons"].append(
                f"Moving your king means you can never castle — your king stays in the center"
            )

    # ─── 4c. Does the played move block a piece from developing? ───
    if played_piece_type:
        to_sq = played_move.to_square
        # Check if king on e2/e7 blocks bishop on f1/f8
        back_rank = 0 if user_color_bool == chess.WHITE else 7
        if played_piece_type.piece_type == chess.KING:
            bishop_sq = chess.square(5, back_rank)  # f1 or f8
            bishop = board.piece_at(bishop_sq)
            if bishop and bishop.piece_type == chess.BISHOP and bishop.color == user_color_bool:
                if to_sq == chess.square(4, back_rank + (1 if user_color_bool == chess.WHITE else -1)):
                    result["reasons"].append(
                        f"Your king on {chess.square_name(to_sq)} blocks your bishop from getting out"
                    )

    # ─── 4d. What can the OPPONENT do after the played move? ───
    # This catches forks, discovered attacks, and tactical punishments
    # When there's a devastating reply (fork/mate/queen capture),
    # ONLY show that — everything else is noise
    opp_threats_after_played = _find_opponent_threats(board_after_played, opp_color)
    if opp_threats_after_played:
        result["reasons"] = opp_threats_after_played[:2]  # Replace all — this IS the reason

    # ─── 5. Does the played move leave something hanging? ───
    user_hanging_after_played = _find_user_hanging(board_after_played, user_color_bool)
    user_hanging_after_best = _find_user_hanging(board_after_best, user_color_bool)

    new_hanging = [h for h in user_hanging_after_played if h not in user_hanging_after_best]
    if new_hanging:
        for piece_name, sq_name in new_hanging[:2]:
            result["reasons"].append(
                f"Your move leaves your {piece_name} on {sq_name} with no protection"
            )

    # ─── 6. Does the best move develop/castle? ───
    if board.is_castling(best_move) and not board.is_castling(played_move):
        result["reasons"].append(f"{best_move_san} gets your king safe with castling")

    # ─── 7. Checkmate? ───
    if board_after_best.is_checkmate():
        result["reasons"] = [f"{best_move_san} is checkmate!"]

    # ─── 8. What does the best move's piece attack? ───
    if not result["reasons"]:
        best_piece = board_after_best.piece_at(best_move.to_square)
        if best_piece:
            attacks = board_after_best.attacks(best_move.to_square)
            for sq in attacks:
                target = board_after_best.piece_at(sq)
                if target and target.color == opp_color:
                    # Skip lone pawn attacks, but include pawns attacked by 2+ pieces
                    attackers = list(board_after_best.attackers(user_color_bool, sq))
                    if target.piece_type == chess.PAWN and len(attackers) < 2:
                        continue
                    t_name = chess.piece_name(target.piece_type)
                    t_sq = chess.square_name(sq)
                    if len(attackers) >= 2 and target.piece_type == chess.PAWN:
                        result["reasons"].append(
                            f"{best_move_san} creates a double attack on {t_sq} — "
                            f"{len(attackers)} pieces now targeting that weak spot"
                        )
                    else:
                        result["reasons"].append(
                            f"{best_move_san} puts your {chess.piece_name(best_piece.piece_type)} "
                            f"where it attacks the {t_name} on {t_sq}"
                        )
                    break

    # ─── 9. Does the best move control more squares? ───
    if not result["reasons"]:
        best_piece = board_after_best.piece_at(best_move.to_square)
        played_piece = board_after_played.piece_at(played_move.to_square)
        if best_piece and played_piece:
            best_control = len(list(board_after_best.attacks(best_move.to_square)))
            played_control = len(list(board_after_played.attacks(played_move.to_square)))
            if best_control > played_control + 2:
                result["reasons"].append(
                    f"{best_move_san} controls {best_control} squares from {chess.square_name(best_move.to_square)} "
                    f"(your move only controls {played_control})"
                )

    # ─── 10. Is the best move a developing move vs a non-developing played move? ───
    if not result["reasons"]:
        best_piece_before = board.piece_at(best_move.from_square)
        played_piece_before = board.piece_at(played_move.from_square)
        back_rank = 0 if user_color_bool == chess.WHITE else 7

        best_is_develop = (
            best_piece_before and
            best_piece_before.piece_type in (chess.KNIGHT, chess.BISHOP) and
            chess.square_rank(best_move.from_square) == back_rank
        )
        played_is_develop = (
            played_piece_before and
            played_piece_before.piece_type in (chess.KNIGHT, chess.BISHOP) and
            chess.square_rank(played_move.from_square) == back_rank
        )
        if best_is_develop and not played_is_develop:
            # Add context about what the played move was
            if played_piece_before and played_piece_before.piece_type == chess.QUEEN:
                result["reasons"].append(
                    f"Moving your queen this early can be risky. "
                    f"{best_move_san} brings a new piece into the game instead"
                )
            elif played_piece_before and played_piece_before.piece_type == chess.KING:
                result["reasons"].append(
                    f"{best_move_san} develops a piece — your king move can wait"
                )
            else:
                result["reasons"].append(
                    f"{best_move_san} brings a new piece into the game"
                )

    # ─── 11. PV-based plan — what does the best line ACHIEVE? ───
    if pv_after_best and len(pv_after_best) >= 2:
        pv_plan = _describe_pv_plan(board, best_move, pv_after_best, user_color_bool)
        if pv_plan:
            result["plan"] = pv_plan
            if not result["reasons"]:
                result["reasons"].append(pv_plan)

    # Build a simple summary
    if result["reasons"]:
        result["summary"] = ". ".join(result["reasons"][:2]) + "."
    else:
        result["summary"] = f"{best_move_san} gives you a better position."

    return result


def _describe_pv_plan(
    board: chess.Board,
    best_move: chess.Move,
    pv: List[str],
    user_color: chess.Color,
) -> Optional[str]:
    """
    Describe what the Stockfish PV achieves in simple terms.
    Walks through the PV and notes key events: captures, checks, mate.
    """
    sim = board.copy()
    sim.push(best_move)

    events = []
    best_san = board.san(best_move)
    moves_described = [best_san]

    for pv_move_san in pv[:4]:
        try:
            pv_move = sim.parse_san(pv_move_san)
            is_user = sim.turn == user_color
            piece = sim.piece_at(pv_move.from_square)
            captured = sim.piece_at(pv_move.to_square)

            sim.push(pv_move)

            if sim.is_checkmate():
                events.append("checkmate")
                moves_described.append(pv_move_san)
                break
            elif sim.is_check() and is_user:
                events.append(f"{pv_move_san} with check")
                moves_described.append(pv_move_san)
            elif captured and is_user:
                events.append(f"take the {chess.piece_name(captured.piece_type)}")
                moves_described.append(pv_move_san)
            elif captured and not is_user:
                # Opponent takes something
                events.append(f"they take your {chess.piece_name(captured.piece_type)}")
        except Exception:
            break

    if not events:
        return None

    if "checkmate" in events:
        return f"After {', '.join(moves_described[:3])}, it's checkmate"

    # Build plan description
    user_events = [e for e in events if not e.startswith("they")]
    if user_events:
        return f"The plan: {best_san}, then {', '.join(user_events[:2])}"

    return None


def _find_fork(board: chess.Board, attacker_color: chess.Color, from_square: int) -> Optional[List]:
    """Find if the piece on from_square forks opponent pieces."""
    piece = board.piece_at(from_square)
    if not piece or piece.color != attacker_color:
        return None

    attacks = board.attacks(from_square)
    targets = []
    for sq in attacks:
        target = board.piece_at(sq)
        if target and target.color != attacker_color and target.piece_type != chess.PAWN:
            targets.append(target.piece_type)

    return targets if len(targets) >= 2 else None


def _find_attacks_on_undefended(board: chess.Board, attacker_color: chess.Color) -> List:
    """Find opponent pieces attacked by attacker_color with no defenders."""
    opp = not attacker_color
    results = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == opp and piece.piece_type not in (chess.KING, chess.PAWN):
            if board.is_attacked_by(attacker_color, sq):
                defenders = list(board.attackers(opp, sq))
                if not defenders:
                    results.append((chess.piece_name(piece.piece_type), chess.square_name(sq)))
    return results


def _find_user_hanging(board: chess.Board, user_color: chess.Color) -> List:
    """Find user pieces that are hanging (attacked and undefended)."""
    opp = not user_color
    results = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == user_color and piece.piece_type not in (chess.KING, chess.PAWN):
            if board.is_attacked_by(opp, sq):
                defenders = list(board.attackers(user_color, sq))
                if not defenders:
                    results.append((chess.piece_name(piece.piece_type), chess.square_name(sq)))
    return results


def _find_opponent_threats(board: chess.Board, opp_color: chess.Color) -> List[str]:
    """
    Find what the opponent can do in the resulting position.
    Checks for: forks, checks that win material, free captures, checkmate.
    """
    user_color = not opp_color
    threats = []

    for move in board.legal_moves:
        piece = board.piece_at(move.from_square)
        if not piece or piece.color != opp_color:
            continue

        move_san = board.san(move)

        # Simulate the opponent's move
        board.push(move)

        # Check for checkmate
        if board.is_checkmate():
            board.pop()
            threats.append(f"After your move, {move_san} is checkmate!")
            return threats

        board.pop()

        # Check for forks — opponent piece attacks 2+ of our valuable pieces
        board.push(move)
        attacked_targets = []
        for sq in board.attacks(move.to_square):
            target = board.piece_at(sq)
            if target and target.color == user_color and target.piece_type != chess.PAWN:
                attacked_targets.append(target.piece_type)
        board.pop()

        # SEE-based safety gate. Real exchange evaluation, not a binary
        # "cheapest attacker < forker" heuristic. Tester reported
        # "Ne3 forks your queen and rook" warnings when e3 is defended
        # by a pawn — and even one-defender cases where SEE is still
        # negative (knight on pawn-defended square + one defender =
        # still loses 2 net pawns). The helper handles both. Check
        # forces user to address the check first, so we keep those
        # threats even when SEE says forker would die.
        if len(attacked_targets) >= 2 and not fork_threat_is_real(
            board, move, user_color
        ):
            continue

        if len(attacked_targets) >= 2:
            piece_name = chess.piece_name(piece.piece_type)
            target_names = [chess.piece_name(t) for t in
                          sorted(attacked_targets,
                                key=lambda t: PIECE_VALUES.get(t, 0), reverse=True)[:2]]
            threats.append(
                f"After your move, {move_san} forks your {' and '.join(target_names)}"
            )
            return threats

        # Check for free captures of high-value pieces
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured and captured.color == user_color:
                cap_val = PIECE_VALUES.get(captured.piece_type, 0)
                attacker_val = PIECE_VALUES.get(piece.piece_type, 0)

                board.push(move)
                is_defended = board.is_attacked_by(user_color, move.to_square)
                board.pop()

                if not is_defended and cap_val >= 3:
                    threats.append(
                        f"After your move, your {chess.piece_name(captured.piece_type)} on "
                        f"{chess.square_name(move.to_square)} can be taken for free"
                    )
                elif cap_val > attacker_val + 1:
                    threats.append(
                        f"After your move, the opponent can take your "
                        f"{chess.piece_name(captured.piece_type)} with a "
                        f"{chess.piece_name(piece.piece_type)}"
                    )

    return threats[:2]
