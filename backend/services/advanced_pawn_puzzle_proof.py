"""Exact advanced-pawn proof: a deep pawn whose promotion is the point.

Why this exists
---------------
Measured across 41-52 players, the endgame is where our weakest accounts
lose the most, and `advancedPawn` is the single largest endgame-heavy theme
Lichess publishes for the 600-1500 band (~244k puzzles). We had no detector
for it. The three adjacent shapes we already own are not it:
`stop_opp_pawn` fires on the DEFENDER blocking an enemy pawn,
`defensive_pawn_push` is an opening passivity shape, and
`endgame_loose_pawn_grab` is about grabbing a stray pawn.

What the motif actually is (learned by playing 14 stored lines move by move,
2026-09-22, not by reading a definition)
----------------------------------------------------------------------------
In every example the solver already owns a pawn deep in enemy territory
(relative rank 5 or better in 91.5% of 400 sampled puzzles), and the stored
solution drives that pawn home. The supporting moves are almost never about
the pawn itself -- they are sacrifices, checks and deflections that clear the
promotion path or drag the blockader away:

  001w5  g7 pawn   Qh7+ Kxh7 g8=Q#            queen sac attracts the king
  00GuD  g6 pawn   Rxh6+ gxh6 g7+ Kh7 g8=Q#   rook sac opens the g-file
  00AOH  a4 pawn   Rxb6 Nxb6 a3 Nd7 a2        rook sac removes the blockader
  004Lu  e6 pawn   d6+ cxd6 cxd6+ Kxd6 e7     two pawn sacs clear the escort
  007fJ  c3 pawn   c2#                        the pawn move itself is mate

So the tell is NOT on the best move. Measured on 400 puzzles, the pawn's
decisive advance is on the best move only 31.0% of the time -- it lands two
to five plies in. Testing only `best_move` would cap recall near 31%; walking
the stored line the way `fork_puzzle_proof._fork_anywhere_in_line` does takes
it to 100%.

Measured (2026-09-22, 1000 Lichess `advancedPawn` puzzles rated 600-1500)
------------------------------------------------------------------------
  detector geometry fires            100.0%
  verifier proves a real payoff       83.6%
      unstoppable_next_move           43.2%
      promotes                        23.3%
      pawn_move_checks                12.2%
      pawn_move_mates                  2.7%
      promotes_later_in_line           2.2%
  cross-fire on 300 `fork`             0.0%
  cross-fire on 300 `mateIn2`          0.0%

Cross-fire is measured on puzzles that do NOT also carry `advancedPawn`,
because Lichess co-tags the theme freely (a promotion mate is legitimately
both `mateIn2` and `advancedPawn`).

Polarity note: this detector DOES accept a material-flavoured payoff, because
a promotion really is a material event. `defensive_move_puzzle_proof` is the
opposite case and deliberately has no such gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.stored_line_verifier import parse_legal_move, replay_stored_line
from services.verified_puzzle_admission import DetectorProof, VerifierProof


ADVANCED_PAWN_PROOF_VERSION = "advanced_pawn_puzzle_proof.v1"
ADVANCED_PAWN_QUALITY_ID = "endgame:advanced_pawn_with_stored_payoff"

# Relative rank (0-indexed from the mover's own back rank) that counts as
# "deep". 6 is the seventh rank -- one square from promoting. This is not a
# tuned knob: it is the geometric definition of the motif, and the 400-puzzle
# distribution showed 100% of advancedPawn lines contain such a move against
# 0.0% of fork and mateIn2 lines that do not also carry the theme.
_DEEP_RELATIVE_RANK = 6
# The pawn is already advanced before the line starts. Fact only, never a
# gate: requiring it would have cost 8.5% recall and bought nothing, since
# cross-fire is already zero.
_PRE_ADVANCED_RELATIVE_RANK = 4


@dataclass(frozen=True)
class AdvancedPawnProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = ADVANCED_PAWN_QUALITY_ID


def _relative_rank(square: int, color: chess.Color) -> int:
    rank = chess.square_rank(square)
    return rank if color == chess.WHITE else 7 - rank


def _promotion_square(square: int, color: chess.Color) -> int:
    return chess.square(chess.square_file(square), 7 if color == chess.WHITE else 0)


def verify_advanced_pawn_push(
    board_before: chess.Board,
    move: Any,
) -> Optional[dict]:
    """Prove that one legal move drives a pawn into the promotion zone.

    Geometry only. It does not claim the push wins anything; the puzzle proof
    below still needs the stored continuation to show a payoff.
    """
    pushed = parse_legal_move(board_before, move)
    if pushed is None:
        return None
    color = board_before.turn
    piece = board_before.piece_at(pushed.from_square)
    if piece is None or piece.color != color or piece.piece_type != chess.PAWN:
        return None
    landing_rank = _relative_rank(pushed.to_square, color)
    if landing_rank < _DEEP_RELATIVE_RANK and pushed.promotion is None:
        return None
    promo_sq = _promotion_square(pushed.to_square, color)
    return {
        "pawn_from": chess.square_name(pushed.from_square),
        "pawn_to": chess.square_name(pushed.to_square),
        "relative_rank": landing_rank + 1,
        "promotion_square": chess.square_name(promo_sq),
        "promotes_now": pushed.promotion is not None,
        "promotion_piece": (
            chess.piece_name(pushed.promotion) if pushed.promotion else None
        ),
    }


def _advance_anywhere_in_line(
    board_before: chess.Board,
    best: chess.Move,
    pv_after_best: Sequence[Any],
):
    """Find the decisive pawn advance on the best move, or later in the line.

    Measured on 400 puzzles: the advance sits on the best move in only 31.0%
    of cases. Walking the line is what takes recall from ~31% to 100%, and it
    loosens no gate -- the same geometry test runs, just at the ply where the
    pawn actually moves.

    Returns (board_at_push, push_move, geometry, ply_index, remaining_line)
    or None. ply_index 0 means the advance IS the best move.
    """
    replay = replay_stored_line(
        board_before, best, pv_after_best,
        resolve_ambiguous_continuation=True,
    )
    if not replay.complete:
        return None

    initiator = board_before.turn
    board = board_before.copy(stack=False)
    line = list(replay.replayed_uci)
    for index, uci in enumerate(line):
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return None
        if move not in board.legal_moves:
            return None
        if board.turn == initiator:
            geometry = verify_advanced_pawn_push(board, move)
            if geometry is not None:
                return (
                    board.copy(stack=False), move, geometry, index,
                    tuple(line[index + 1:]),
                )
        board.push(move)
    return None


def _independent_promotion_payoff(
    board_at_push: chess.Board,
    push: chess.Move,
    remaining_line: Sequence[Any],
) -> Optional[dict]:
    """Prove the deep pawn actually pays off, four ways, all board-checkable.

    (a) it promotes on this move;
    (b) the push itself gives check or mate (007fJ: c2# is the whole puzzle);
    (c) it lands one square from queening and nothing can stop it -- the
        promotion square is empty, the opponent attacks neither the pawn nor
        the promotion square, so queening is threatened next move;
    (d) a pawn of ours promotes later in the same stored line.

    Measured 2026-09-22 on 1000 puzzles: one of the four holds 83.6% of the
    time. The 16.4% residue was played through by hand and is NOT forced: in
    every case the deep pawn never queens in the stored line, and what the
    advance actually wins is material (0040n gxh2 takes a rook; 01M89 fxe2
    wins the exchange; 01ysM d7 forces Rxd8). Those are true positions and
    false promotion claims. Admitting them would mean adding a material gate,
    which belongs to `fork_puzzle_proof` and `free_piece_puzzle_proof`, not
    here -- this module's claim is specifically that the pawn queens or
    cannot be stopped from queening.
    """
    initiator = board_at_push.turn
    after = board_at_push.copy(stack=False)
    after.push(push)

    if push.promotion is not None:
        return {
            "payoff_kind": "promotes",
            "promoted_to": chess.piece_name(push.promotion),
            "promotion_square": chess.square_name(push.to_square),
        }

    if after.is_checkmate():
        return {
            "payoff_kind": "pawn_move_mates",
            "pawn_square": chess.square_name(push.to_square),
        }
    if after.is_check():
        return {
            "payoff_kind": "pawn_move_checks",
            "pawn_square": chess.square_name(push.to_square),
        }

    promo_sq = _promotion_square(push.to_square, initiator)
    if (
        _relative_rank(push.to_square, initiator) == 6
        and after.piece_at(promo_sq) is None
        and not after.attackers(not initiator, push.to_square)
        and not after.attackers(not initiator, promo_sq)
    ):
        return {
            "payoff_kind": "unstoppable_next_move",
            "pawn_square": chess.square_name(push.to_square),
            "promotion_square": chess.square_name(promo_sq),
        }

    # (d) the same pawn, or another of ours, queens further down the stored
    # line. Walk it legally; a line that will not replay proves nothing.
    replay = replay_stored_line(
        board_at_push, push, remaining_line,
        resolve_ambiguous_continuation=True,
    )
    if replay.complete:
        board = board_at_push.copy(stack=False)
        for uci in replay.replayed_uci:
            try:
                move = chess.Move.from_uci(uci)
            except ValueError:
                break
            if move not in board.legal_moves:
                break
            if board.turn == initiator and move.promotion is not None:
                return {
                    "payoff_kind": "promotes_later_in_line",
                    "promoted_to": chess.piece_name(move.promotion),
                    "promotion_square": chess.square_name(move.to_square),
                }
            board.push(move)
    return None


def build_advanced_pawn_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[AdvancedPawnProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    located = _advance_anywhere_in_line(board_before, best, pv_after_best)
    if located is None:
        return None
    push_board, push_move, geometry, push_ply, remaining = located

    initiator = board_before.turn
    pre_advanced = tuple(
        chess.square_name(square)
        for square in board_before.pieces(chess.PAWN, initiator)
        if _relative_rank(square, initiator) >= _PRE_ADVANCED_RELATIVE_RANK
    )
    payoff = _independent_promotion_payoff(push_board, push_move, remaining)

    concept_id = "endgame.advanced_pawn"
    detector = DetectorProof(
        concept_id=concept_id,
        family="endgame",
        detector_id="shape:advanced_pawn",
        detector_version=ADVANCED_PAWN_PROOF_VERSION,
        calculation_id="pawn_promotion_zone_scan_over_stored_line",
        facts=({
            "pawn_from": geometry["pawn_from"],
            "pawn_to": geometry["pawn_to"],
            "relative_rank": geometry["relative_rank"],
            "promotion_square": geometry["promotion_square"],
            "promotes_now": geometry["promotes_now"],
            "executing_move": push_move.uci(),
            # Where the advance actually lands. 0 = the best move itself.
            # Anything higher means the best move is a prep move -- a caption
            # must not say "push the pawn here"; the lesson is the whole
            # escort, not the square.
            "advance_ply_in_line": push_ply,
            "advance_is_immediate": push_ply == 0,
            # Fact, never a gate: 91.5% of the theme already has a deep pawn
            # before the line starts.
            "pre_advanced_pawns": pre_advanced,
        },),
        acceptable_moves=(best.uci(),),
        counterfactual={
            "played_move": played.uci(),
            "best_move": best.uci(),
            "cp_loss": loss,
        },
    )
    verifier = VerifierProof(
        concept_id=concept_id,
        verifier_id="independent_promotion_payoff_walk",
        verifier_version=ADVANCED_PAWN_PROOF_VERSION,
        calculation_id="promotion_or_check_or_unstoppable_square_proof",
        verified=payoff is not None,
        acceptable_moves=(best.uci(),) if payoff else (),
        facts=(payoff,) if payoff else (),
    )
    return AdvancedPawnProofBundle(detector=detector, verifier=verifier)
