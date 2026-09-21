"""Exact x-ray proof: a slider hits the square behind an enemy piece.

What the motif actually is, read off twelve Lichess `xRayAttack` puzzles rated
600-1500 that were played out move by move on 2026-09-22. In every one, a
friendly slider ends the combination by landing on a square that, earlier in the
same line, it could only "see" THROUGH an enemy piece:

  01GBu  Re5 -> e1 through the white Re2      Qxe1+ Rxe1 Rxe1#
  01rGp  Rb8 -> b1 through the white Rb2      Rxb1+ Rxb1 Rxb1#
  03eaM  Re1 -> e8 through the black Re6      Qxe8+ Rxe8 Rxe8#
  04hRz  Rc8 -> c1 through the white Rc7      Nxc1+ Rxc1 Rxc1
  05Gq4  Rf8 -> f1 through the white Rf2      Qe1+ Rf1 Qxf1+ Rxf1 Rxf1#
  05Gv1  Qa4 -> e8 through the black Bd7      Re8+ Bxe8 Qxe8#
  05Pp0  Re1 -> e8 through the black Re7      Qxe8+ Rxe8 Rxe8#
  05adP  Bg6 -> e8 through the black Bf7      Rxe8+ Bxe8 Bxe8
  069H6  Rd1 -> d8 through the black Rd7      Rc8 Rxd7 Rxd8+ Rxd8 Rxd8+
  06Ipb  Re6 -> e1 through the white Re4/Qe2  Qg1+ Qe1 Qxe1+ Rxe1 Rxe1#
  06Roa  Re1 -> e8 through the black Re7      Qb8+ Ne8 Qxe8+ Rxe8 Rxe8+
  0791B  Rc1 -> c8 through the black Rc2      Rc8+ Rxc8 Rxc8#

So the proof is a statement about ONE slider at TWO moments of the same line.
At the late moment it moves S -> T. At an earlier moment it stood on the same S
and the ray to T was occupied by enemy pieces and by nothing of ours. The
combination in between is whatever clears those enemy pieces -- usually a trade
chain, in 05Gv1 a deflection sacrifice. That difference does not need modelling:
if the slider gets to T, the blockers went.

Two things learned from the boards and encoded as gates:

* The x-ray is often NOT visible at move one. 069H6 and 0791B only line up after
  the first ply, so the earlier moment is searched over every position of the
  line, not just the root. Same lesson `fork_puzzle_proof` records.
* Friendly blockers do not count. Doubled rooks looking at the same square are
  a battery, not an x-ray, and calling a battery an x-ray teaches the student
  the wrong word.

Measured 2026-09-22 on Lichess theme labels, 600-1500 only:

  recall        1000 `xRayAttack`  detector 99.2%, verified 99.0%
  cross-fire     300 `mateIn2`     2.3%   (no `xRayAttack` tag in the sample)
  cross-fire     300 `fork`        0.3%
  cross-fire     200 `mateIn3`    13.0%   (the length-matched control)
  cross-fire     200 `skewer`      4.5%   `pin` 1.5%   `hangingPiece` 1.0%

The `mateIn3` number is coexistence, not error: all six fires read by hand
(00F6y, 00O9a, 00Pr6, 00Ycz, 00hdN, 014It) are textbook x-rays that Lichess
simply did not tag. `pin` at 1.5% is the useful signal -- a pin is also a line
through an enemy piece, and this fires only when the slider actually LANDS on
the far square, which a pin by definition never does.

06Ipb has TWO enemy blockers, so the cap is two, not one. Everything else in the
sample has exactly one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.caption_facts import PIECE_VALUE_CP
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.line_motif_geometry import (
    LINE_MOTIF_GEOMETRY_VERSION,
    LineWalk,
    blockers_between,
    is_slider,
    line_payoff_cp,
    same_piece,
    slider_travels,
    walk_line,
)
from services.stored_line_verifier import parse_legal_move
from services.verified_puzzle_admission import DetectorProof, VerifierProof


XRAY_PROOF_VERSION = f"xray_attack_puzzle_proof.v1+{LINE_MOTIF_GEOMETRY_VERSION}"
XRAY_QUALITY_ID = "tactic:xray_attack_with_stored_payoff"
XRAY_CONCEPT_ID = "tactic.xray_attack"

#: 06Ipb screens the e-file with a rook AND a queen. One blocker is the normal
#: shape; three is a traffic jam rather than an x-ray a student can see.
MAX_SCREENING_PIECES = 2

#: What landing on the far square has to be worth. A slider arriving on an empty
#: quiet square proves nothing, so the payoff square must hold a real piece or
#: the arrival must be mate.
MIN_XRAY_TARGET_CP = PIECE_VALUE_CP[chess.KNIGHT]


@dataclass(frozen=True)
class XRayAttackProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = XRAY_QUALITY_ID


def _arrival_is_worth_it(
    before: chess.Board, move: chess.Move
) -> Optional[dict]:
    """Price the slider's arrival on the far square: capture value, or mate."""
    captured = before.piece_at(move.to_square)
    if before.is_en_passant(move):
        captured = None
    value = (
        PIECE_VALUE_CP.get(captured.piece_type, 0)
        if captured is not None and captured.color != before.turn
        else 0
    )
    after = before.copy(stack=False)
    after.push(move)
    mate = after.is_checkmate()
    if not mate and value < MIN_XRAY_TARGET_CP:
        return None
    return {
        "target_piece": (
            chess.piece_name(captured.piece_type) if value else None
        ),
        "target_value_cp": value,
        "arrival_is_mate": mate,
    }


def _locate_xray(walk: LineWalk) -> Optional[dict]:
    initiator = walk.initiator
    for later, (before, move) in enumerate(zip(walk.positions, walk.moves)):
        if before.turn != initiator:
            continue
        slider = before.piece_at(move.from_square)
        if slider is None or not is_slider(slider.piece_type):
            continue
        if not slider_travels(slider.piece_type, move.from_square, move.to_square):
            continue
        arrival = _arrival_is_worth_it(before, move)
        if arrival is None:
            continue
        for earlier in range(0, later):
            screen_board = walk.positions[earlier]
            standing = screen_board.piece_at(move.from_square)
            if not same_piece(standing, slider):
                continue
            split = blockers_between(
                screen_board, move.from_square, move.to_square
            )
            if split is None:
                continue
            friendly, enemy = split
            # A friendly screen is a battery, not an x-ray.
            if friendly or not enemy:
                continue
            if len(enemy) > MAX_SCREENING_PIECES:
                continue
            # You cannot x-ray a king. It is not a screen that might stay put,
            # it is a piece that is legally obliged to move, and the square
            # behind it is a mating square rather than a second target.
            #
            # Measured 2026-09-22: three of the six inspected fires inside
            # `mateIn2` were exactly this -- 00HzH `Rxf8+ Kh7 Rh8#`, 00JfN
            # `Qf7+ Kd8 Qxd7#`, 00XqB `Qf4+ Kh5 Qh4#`. All three are mate nets
            # read as x-rays. None of the twelve hand-checked `xRayAttack`
            # puzzles screens through a king, so this costs nothing.
            if any(
                screen_board.piece_at(square).piece_type == chess.KING
                for square in enemy
            ):
                continue
            screening = []
            for square in enemy:
                piece = screen_board.piece_at(square)
                screening.append(
                    {
                        "square": chess.square_name(square),
                        "piece": chess.piece_name(piece.piece_type),
                        "value_cp": PIECE_VALUE_CP.get(piece.piece_type, 0),
                    }
                )
            return {
                "slider_piece": chess.piece_name(slider.piece_type),
                "slider_square": chess.square_name(move.from_square),
                "target_square": chess.square_name(move.to_square),
                "screening_pieces": tuple(screening),
                "screen_count": len(enemy),
                "xray_seen_at_ply": earlier,
                # 0 means the x-ray is already on the board when the student
                # is looking at it. Higher means the line has to build it
                # first, and a caption must say so instead of claiming the
                # student "missed an x-ray" in front of them.
                "xray_is_immediate": earlier == 0,
                "arrival_move": move.uci(),
                "arrival_ply_in_line": later,
                **arrival,
            }
    return None


def build_xray_attack_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[XRayAttackProofBundle]:
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
    located = _locate_xray(walk)
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
        concept_id=XRAY_CONCEPT_ID,
        family="tactics",
        detector_id="line_motif:xray_attack",
        detector_version=XRAY_PROOF_VERSION,
        calculation_id="slider_reaches_square_it_only_saw_through_enemy_screen",
        facts=(located,),
        acceptable_moves=(best.uci(),),
        counterfactual={
            "played_move": played.uci(),
            "best_move": best.uci(),
            "cp_loss": loss,
        },
    )
    verifier = VerifierProof(
        concept_id=XRAY_CONCEPT_ID,
        verifier_id="independent_screen_scan_and_settled_payoff",
        verifier_version=XRAY_PROOF_VERSION,
        calculation_id="enemy_only_screen_at_earlier_ply_plus_quiescent_material",
        verified=verified is not None,
        acceptable_moves=(best.uci(),) if verified else (),
        facts=(verified,) if verified else (),
    )
    return XRayAttackProofBundle(detector=detector, verifier=verifier)
