"""Exact interference proof: a defender's line is cut, then its charge falls.

What the motif actually is, read off twenty-six Lichess `interference` puzzles
rated 600-1500 that were played out move by move on 2026-09-22. The textbook
half is there:

  01GCT  Be4+ steps onto the e-file between Qe3 and Be6, then Rxe6
  01u7X  Rd2 steps onto rank 2 between Qe2 and Bc2, then Rxc2
  07fcs  Be2 steps onto the f3-d1 diagonal between Qf3 and Rd1, then Bxd1
  0EywV  Bd4 steps onto the b2-e5 diagonal between Qb2 and Ne5, then Bxe5

but it is the minority. The larger half of the family at this rating is the
opponent being FORCED to block his own defender, almost always by a check:

  08SOm  Rh5+ -> Kg7 lands on g7, cutting Rg8's defence of g4, then Kxg4
  0BCpo  Qa1+ -> Kd2 lands on d2, cutting Rd1's defence of d7, then Rxd7+
  0EFIo  Qh1+ -> Ke2 lands on e2, cutting Re1's defence of e8, then Rxe8+
  0Ejy9  Qxf4+ -> Bd2 interposes, cutting Rd1's defence of d4, then Qxd4
  0EnqC  Qxh5+ -> Kg8 lands on g8, cutting Rh8's defence of c8, then Rxc8#
  0ErhC  Rc6+ -> Kb3 lands on b3, cutting Rb2's defence of b6, then Rxb6+
  0FuFJ  Qg8+ -> Ke7 lands on e7, cutting Rc7's defence of g7, then Qxg7+
  0Gt4n  Qd7+ -> Kf8 lands on f8, cutting Rg8's defence of a8, then Rxa8+

A detector that only looked for OUR piece interposing would throw away most of
the theme, and would also teach the wrong lesson: at 600-1500 the transferable
idea is "check him onto his own rook's line", not only "sacrifice into the
line". So the arriving piece may belong to either side. Everything else is
identical in both halves, which is why one proof covers both:

  a piece ARRIVES on square X; an enemy slider D attacked square Y before that
  and no longer does; X lies strictly between D and Y; and the initiator then
  takes on Y and the line settles in profit.

Measured 2026-09-22 on Lichess theme labels, 600-1500 only:

  recall        1000 `interference`  detector 100.0%, verified 99.5%
  cross-fire     300 `mateIn2`       3.0%  (no `interference` tag in the sample)
  cross-fire     300 `fork`          1.0%
  cross-fire     200 `mateIn3`       6.5%  (the length-matched control)
  cross-fire     200 `hangingPiece`  0.0%  `pin` 0.5%   `skewer` 0.5%

A clean sweep of 1000 wants suspicion, so it got a negative control: on 200
`hangingPiece` puzzles it fires zero times, and the four `mateIn2` fires read
by hand (00a98, 00nZE, 015RS, 01BDV) are all the same real motif -- a check
driving the king onto the rank its own rook was guarding along.

The defender has to survive its own interference -- if D is captured, the
motif is removal-of-the-defender and there is already a detector for that.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.caption_facts import PIECE_VALUE_CP
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.legal_exchange_verifier import independent_exchange_gain
from services.line_motif_geometry import (
    LINE_MOTIF_GEOMETRY_VERSION,
    LineWalk,
    is_slider,
    line_payoff_cp,
    same_piece,
    slider_travels,
    squares_between,
    walk_line,
)
from services.stored_line_verifier import parse_legal_move
from services.verified_puzzle_admission import DetectorProof, VerifierProof


INTERFERENCE_PROOF_VERSION = (
    f"interference_puzzle_proof.v1+{LINE_MOTIF_GEOMETRY_VERSION}"
)
INTERFERENCE_QUALITY_ID = "tactic:interference_with_stored_payoff"
INTERFERENCE_CONCEPT_ID = "tactic.interference"

#: What is standing on the cut-off square has to be worth taking.
MIN_INTERFERENCE_TARGET_CP = PIECE_VALUE_CP[chess.PAWN]


@dataclass(frozen=True)
class InterferenceProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = INTERFERENCE_QUALITY_ID


def _cut_defenders(
    before: chess.Board,
    after: chess.Board,
    blocked_square: int,
    target: int,
    defender_color: chess.Color,
) -> Optional[dict]:
    """One enemy slider that defended `target` through `blocked_square`.

    Requires the defender to still be there afterwards: a captured defender is
    removal-of-the-defender, a different motif with a different lesson.
    """
    for square in before.attackers(defender_color, target):
        defender = before.piece_at(square)
        if defender is None or not is_slider(defender.piece_type):
            continue
        if not slider_travels(defender.piece_type, square, target):
            continue
        between = squares_between(square, target)
        if between is None or blocked_square not in between:
            continue
        if not same_piece(after.piece_at(square), defender):
            continue
        if square in after.attackers(defender_color, target):
            continue
        return {
            "defender_piece": chess.piece_name(defender.piece_type),
            "defender_square": chess.square_name(square),
        }
    return None


def _locate_interference(walk: LineWalk) -> Optional[dict]:
    initiator = walk.initiator
    defender_color = not initiator
    for index, (before, blocking) in enumerate(zip(walk.positions, walk.moves)):
        blocked_square = blocking.to_square
        after = before.copy(stack=False)
        after.push(blocking)
        for later in range(index + 1, len(walk.moves)):
            position = walk.positions[later]
            if position.turn != initiator:
                continue
            payoff_move = walk.moves[later]
            target = payoff_move.to_square
            if target == blocked_square:
                # Taking the blocker itself is not collecting on the cut line.
                continue
            captured = position.piece_at(target)
            resolved = position.copy(stack=False)
            resolved.push(payoff_move)
            mate = resolved.is_checkmate()
            if not position.is_capture(payoff_move) and not mate:
                continue
            value = (
                PIECE_VALUE_CP.get(captured.piece_type, 0)
                if captured is not None and captured.color == defender_color
                else 0
            )
            if not mate and value < MIN_INTERFERENCE_TARGET_CP:
                continue
            cut = _cut_defenders(
                before, after, blocked_square, target, defender_color
            )
            if cut is None:
                continue
            # The cut has to be what pays. If the exchange on the target square
            # still loses for us, the defence that was severed was not the one
            # holding the square.
            if not mate:
                try:
                    gain = independent_exchange_gain(
                        position, target, forced_first=payoff_move
                    )
                except ValueError:
                    continue
                if gain < MIN_INTERFERENCE_TARGET_CP:
                    continue
            else:
                gain = 0
            blocker = before.piece_at(blocking.from_square)
            by_initiator = before.turn == initiator
            return {
                "blocked_square": chess.square_name(blocked_square),
                "blocking_move": blocking.uci(),
                "blocking_piece": chess.piece_name(blocker.piece_type),
                "blocking_ply_in_line": index,
                # "own" = we interpose. "forced" = a check or threat drives the
                # opponent onto his own defender's line. A caption must not
                # tell a student he sacrificed a piece when the opponent
                # blocked himself.
                "interference_kind": "own" if by_initiator else "forced",
                "forced_by_check": (
                    not by_initiator
                    and index > 0
                    and walk.positions[index].is_check()
                ),
                "target_square": chess.square_name(target),
                "target_piece": (
                    chess.piece_name(captured.piece_type)
                    if captured is not None and value
                    else None
                ),
                "target_value_cp": value,
                "payoff_move": payoff_move.uci(),
                "payoff_ply_in_line": later,
                "payoff_is_mate": mate,
                "exchange_gain_cp": gain,
                **cut,
            }
    return None


def build_interference_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[InterferenceProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    walk = walk_line(board_before, best, pv_after_best)
    if walk is None:
        return None
    located = _locate_interference(walk)
    if located is None:
        return None

    payoff = line_payoff_cp(walk)
    verified = None
    if payoff is not None:
        verified = dict(located)
        verified["settled_payoff_cp"] = payoff
        verified["replayed_uci"] = walk.replay.replayed_uci
        verified["line_ends_in_mate"] = bool(
            walk.replay.checkmate
            and walk.replay.checkmating_color == walk.initiator
        )

    detector = DetectorProof(
        concept_id=INTERFERENCE_CONCEPT_ID,
        family="tactics",
        detector_id="line_motif:interference",
        detector_version=INTERFERENCE_PROOF_VERSION,
        calculation_id="arrival_between_slider_and_its_charge_kills_the_defence",
        facts=(located,),
        acceptable_moves=(best.uci(),),
        counterfactual={
            "played_move": played.uci(),
            "best_move": best.uci(),
            "cp_loss": loss,
        },
    )
    verifier = VerifierProof(
        concept_id=INTERFERENCE_CONCEPT_ID,
        verifier_id="independent_defence_loss_and_settled_payoff",
        verifier_version=INTERFERENCE_PROOF_VERSION,
        calculation_id="attacker_set_diff_plus_forced_exchange_plus_quiescent_material",
        verified=verified is not None,
        acceptable_moves=(best.uci(),) if verified else (),
        facts=(verified,) if verified else (),
    )
    return InterferenceProofBundle(detector=detector, verifier=verifier)
