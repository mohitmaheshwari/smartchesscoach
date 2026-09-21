"""Exact attraction proof: an enemy piece is pulled ONTO a losing square.

Attraction is the opposite pull to deflection. Deflection drags a defender
away from a job; attraction drags a piece -- almost always the king -- onto
a square where a tactic is already waiting for it.

The shape was read off 12 hand-walked Lichess `attraction` puzzles rated
600-1500 before a line of this file was written. All twelve share the same
three beats:

    1. we put a piece on square X that the opponent must take, and we are
       investing more than we took there (a real sacrifice) -- or the piece
       that must take is the KING, which is its own kind of compulsion
    2. the forced reply captures on X, so the enemy piece P now stands on X
    3. later in the same stored line one of our moves lands somewhere ELSE
       and, from there, attacks X -- the square the piece was dragged to

Nine of the twelve dragged the king; the other three dragged a queen or a
rook onto a diagonal. The payoff was mate in four cases and a material win
in the rest, so the line must end in our mate, or a pawn of profit, or -- for
a `short` puzzle that Lichess truncated at the winning check -- a check that
demonstrably forks a piece off.

Deliberately NOT counted as attraction: a plain recapture chain
(Rxb2 Rxb2 Bxb2). There the last move lands ON X, so requiring the payoff
move to hit X *from another square* excludes exchanges while still catching
the real motif, where a tempo move (Bd4+, Nf3+, Be5+) has to arrive first.

Measured 2026-09-22 on Lichess puzzles rated 600-1500, `build_attraction_proof`
via `scripts/measure_deflection_attraction_detectors.py`:

    recall on 1000 `attraction`   89.6%
    cross-fire on 300 `mateIn2`    0.0%
    cross-fire on 300 `fork`       0.0%
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.caption_facts import PIECE_VALUE_CP
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.deflection_puzzle_proof import line_payoff_kind, replay_line_boards
from services.stored_line_verifier import parse_legal_move
from services.verified_puzzle_admission import DetectorProof, VerifierProof


ATTRACTION_PROOF_VERSION = "attraction_puzzle_proof.v1"
ATTRACTION_QUALITY_ID = "tactic:attraction_with_stored_payoff"
ATTRACTION_CONCEPT_ID = "tactic.attraction"


@dataclass(frozen=True)
class AttractionProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = ATTRACTION_QUALITY_ID


def _invested_cp(pre: chess.Board, sac: chess.Move) -> int:
    piece = pre.piece_at(sac.from_square)
    if piece is None:
        return 0
    if sac.promotion:
        return PIECE_VALUE_CP.get(sac.promotion, 0)
    return PIECE_VALUE_CP.get(piece.piece_type, 0)


def _taken_cp(pre: chess.Board, sac: chess.Move) -> int:
    if pre.is_en_passant(sac):
        return PIECE_VALUE_CP[chess.PAWN]
    captured = pre.piece_at(sac.to_square)
    if captured is None:
        return 0
    return PIECE_VALUE_CP.get(captured.piece_type, 0)


def _attraction_payoff(
    boards: Sequence[chess.Board],
    moves: Sequence[chess.Move],
    initiator: chess.Color,
    start_index: int,
    square: int,
    attracted: chess.Piece,
) -> Optional[dict]:
    """Find the later OUR move that attacks the square the piece was pulled to."""
    identity = (attracted.piece_type, attracted.color)
    for index in range(start_index, len(moves)):
        board = boards[index]
        move = moves[index]
        if board.turn != initiator:
            # The attracted piece escaping before we hit it kills the motif.
            if move.from_square == square:
                return None
            continue
        if move.to_square == square:
            # Landing on the square is a recapture, not an attraction payoff.
            return None
        standing = board.piece_at(square)
        if standing is None or (standing.piece_type, standing.color) != identity:
            return None
        after = board.copy(stack=False)
        after.push(move)
        if square not in after.attacks(move.to_square):
            continue
        still = after.piece_at(square)
        if still is None or (still.piece_type, still.color) != identity:
            continue
        # The attracted piece has to be the thing that suffers. Without this
        # the proof swallows every mate whose real mechanism is the square
        # the enemy piece VACATED, not the one it landed on: all 5 cross-fires
        # on 300 `mateIn2` puzzles were that shape (Qxc8+ Bxc8 Re8# is
        # removal-of-guard, Rxa6+ bxa6 Ra7# is the emptied b7). In both the
        # payoff move only grazes the landing square on its way to mating
        # elsewhere. A king pays by being checked on the square it was pulled
        # to; anything else pays by being captured there.
        if attracted.piece_type == chess.KING:
            if not after.is_check():
                continue
            punished = {"punished_by": "check_on_landing_square"}
        else:
            capture_ply = _captured_later_on(
                boards, moves, initiator, index + 1, square, identity
            )
            if capture_ply is None:
                continue
            punished = {
                "punished_by": "captured_on_landing_square",
                "capture_ply_in_line": capture_ply,
            }
        result = {
            "payoff_ply_in_line": index,
            "payoff_move": move.uci(),
            "payoff_gives_check": bool(after.is_check()),
            "payoff_is_mate": bool(
                after.is_checkmate() and after.turn != initiator
            ),
            "payoff_forks_off": _fork_spoils(board, after, initiator, move),
        }
        result.update(punished)
        return result
    return None


def _fork_spoils(
    before: chess.Board,
    after: chess.Board,
    initiator: chess.Color,
    move: chess.Move,
) -> tuple:
    """Enemy pieces the checking payoff move wins on the side.

    Lichess stops a `short` puzzle the moment the win is clear, so a line
    like `Rxe7+ Kxe7 Nc6+` ends at the check and the rook on d8 is never
    actually collected. The material ledger over the stored line is then
    still negative even though the position is winning. Naming the second
    fork target proves the profit from the board instead of from a truncated
    ledger: it counts only pieces worth a knight or more that are either
    undefended or worth more than the piece now attacking them.
    """
    if not after.is_check():
        return ()
    mover = before.piece_at(move.from_square)
    attacker_cp = PIECE_VALUE_CP.get(
        move.promotion or (mover.piece_type if mover else chess.PAWN), 0
    )
    spoils = []
    for square in after.attacks(move.to_square):
        piece = after.piece_at(square)
        if piece is None or piece.color == initiator:
            continue
        if piece.piece_type == chess.KING:
            continue
        value = PIECE_VALUE_CP.get(piece.piece_type, 0)
        if value < PIECE_VALUE_CP[chess.KNIGHT]:
            continue
        defended = bool(after.attackers(not initiator, square))
        if defended and value <= attacker_cp:
            continue
        spoils.append(chess.square_name(square))
    return tuple(sorted(spoils))


def _captured_later_on(
    boards: Sequence[chess.Board],
    moves: Sequence[chess.Move],
    initiator: chess.Color,
    start_index: int,
    square: int,
    identity: tuple,
) -> Optional[int]:
    """Ply at which WE capture the attracted piece on the square it was pulled to."""
    for index in range(start_index, len(moves)):
        board = boards[index]
        move = moves[index]
        if board.turn != initiator or move.to_square != square:
            continue
        standing = board.piece_at(square)
        if standing is None or (standing.piece_type, standing.color) != identity:
            return None
        if board.is_capture(move):
            return index
    return None


def _find_attraction(
    board_before: chess.Board,
    best: chess.Move,
    pv_after_best: Sequence[Any],
) -> Optional[dict]:
    replayed = replay_line_boards(board_before, best, pv_after_best)
    if replayed is None:
        return None
    boards, moves, final, net_gain = replayed
    initiator = board_before.turn
    defender_side = not initiator

    payoff_kind = line_payoff_kind(final, initiator, net_gain)

    for index in range(0, len(moves) - 1):
        pre = boards[index]
        if pre.turn != initiator:
            continue
        sac = moves[index]
        mid = boards[index + 1]
        reply = moves[index + 1]
        if mid.turn != defender_side:
            continue

        square = sac.to_square
        # The reply must be the capture of our piece on that exact square.
        if not mid.is_capture(reply) or reply.to_square != square:
            continue
        attracted = mid.piece_at(reply.from_square)
        if attracted is None or attracted.color != defender_side:
            continue

        invested = _invested_cp(pre, sac)
        taken = _taken_cp(pre, sac)
        king_must_take = attracted.piece_type == chess.KING
        # Either we genuinely paid to put the piece there, or the thing that
        # has to take is the king -- both are compulsion, not an exchange.
        #
        # Allowing an EVEN trade here (invested == taken) was measured and
        # rejected: recall 87.4% -> 92.2%, but cross-fire on 300 `fork`
        # puzzles went 0.0% -> 1.7%, and every recovered line was the same
        # shape as every new cross-fire -- Rxg3+ Bxg3 Rg5+ Kf7 Rxg3, a plain
        # recapture that walks into a fork. `fork_puzzle_proof` already owns
        # that position, and this repo keeps removal and deflection in
        # separate families rather than double-naming one motif. All four
        # non-king attractions in the hand-walked gold invested real material
        # (170-580cp), so the gold agrees with the strict reading.
        if not king_must_take and invested <= taken:
            continue

        payoff = _attraction_payoff(
            boards, moves, initiator, index + 2, square, attracted
        )
        if payoff is None:
            continue

        kind = payoff_kind
        if kind is None:
            # The stored line never paid. It is still an attraction if the
            # king was dragged onto a square where the very next check wins
            # a piece outright -- Lichess just stopped recording there.
            if not (
                payoff["payoff_gives_check"] and payoff["payoff_forks_off"]
            ):
                continue
            kind = "forced_gain_at_truncation"

        candidate = {
            "attraction_ply_in_line": index,
            "attraction_is_immediate": index == 0,
            "sacrifice_move": sac.uci(),
            "sacrifice_square": chess.square_name(square),
            "invested_cp": invested,
            "captured_on_square_cp": taken,
            "net_investment_cp": invested - taken,
            "attracted_piece": chess.piece_name(attracted.piece_type),
            "attracted_from": chess.square_name(reply.from_square),
            "attracted_reply": reply.uci(),
            "attracted_is_king": bool(king_must_take),
            "payoff_kind": kind,
            "net_material_gain_cp": net_gain,
        }
        candidate.update(payoff)
        return candidate
    return None


def verify_created_attraction(
    board_before: chess.Board,
    move: Any,
    continuation: Sequence[Any],
) -> Optional[dict]:
    """Prove an attraction from a raw position plus its stored continuation."""
    leading = parse_legal_move(board_before, move)
    if leading is None:
        return None
    return _find_attraction(board_before, leading, continuation)


def build_attraction_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[AttractionProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    independent = _find_attraction(board_before, best, pv_after_best)
    if independent is None:
        return None

    detector = DetectorProof(
        concept_id=ATTRACTION_CONCEPT_ID,
        family="tactics",
        detector_id="shape:attraction",
        detector_version=ATTRACTION_PROOF_VERSION,
        calculation_id="forced_capture_onto_square_then_renewed_attack_scan",
        facts=(
            {
                "sacrifice_move": independent["sacrifice_move"],
                "sacrifice_square": independent["sacrifice_square"],
                "attracted_piece": independent["attracted_piece"],
                "attracted_from": independent["attracted_from"],
                "attracted_is_king": independent["attracted_is_king"],
                "net_investment_cp": independent["net_investment_cp"],
                # 0 = the attraction is the best move itself. Anything higher
                # means the best move is a prep move and the sacrifice comes
                # later, so a caption must teach the line, not the square.
                "attraction_ply_in_line": independent["attraction_ply_in_line"],
                "attraction_is_immediate": independent["attraction_is_immediate"],
                "payoff_move": independent["payoff_move"],
                "payoff_ply_in_line": independent["payoff_ply_in_line"],
            },
        ),
        acceptable_moves=(best.uci(),),
        counterfactual={
            "played_move": played.uci(),
            "best_move": best.uci(),
            "cp_loss": loss,
        },
    )
    verifier = VerifierProof(
        concept_id=ATTRACTION_CONCEPT_ID,
        verifier_id="independent_forced_recapture_plus_renewed_attack",
        verifier_version=ATTRACTION_PROOF_VERSION,
        calculation_id="sacrifice_ledger_plus_legal_attack_map_on_landing_square",
        verified=True,
        acceptable_moves=(best.uci(),),
        facts=(independent,),
    )
    return AttractionProofBundle(detector=detector, verifier=verifier)
