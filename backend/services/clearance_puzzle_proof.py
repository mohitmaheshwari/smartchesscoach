"""Exact clearance proof: one friendly piece steps out of another's way.

What the motif actually is, read off twelve Lichess `clearance` puzzles rated
600-1500 that were played out move by move on 2026-09-22:

  00Aae  Rf8+  vacates b8, then b8=Q          -- the pawn moves ONTO b8
  00AhO  Bb7   vacates c8, then Rf8-a8        -- the rook travels THROUGH c8
  00M92  Ng6+  vacates h4, then Re4-h4#       -- onto h4
  00PHg  Re8+  vacates a8, then a8=Q          -- onto a8
  00Pc8  Nxd7  vacates e5, then Re1-e7        -- through e5
  00Yy4  Ng3+  vacates h5, then Qf5-h5#       -- onto h5
  00aCb  Nf6+  vacates e4, then Qd3-h7#       -- through e4
  00oYS  Rd1+  vacates c1, then c1=Q          -- onto c1
  01EUl  Bxc3+ vacates d4, then Qd8-d1#       -- through d4
  01LlS  Nf6+  vacates e4, then Qd3-h7#       -- through e4
  01f0q  Nf6+  vacates e4, then Qd3-h7#       -- through e4
  01gA2  Ng6   vacates f8, then Rd8-h8        -- through f8

Twelve for twelve, the SAME sentence covers both halves of the family: a
friendly piece leaves square V, and a later friendly move in the same line was
blocked by NOTHING BUT that piece standing on V. "Onto V" and "through V" stop
being two cases the moment the test is phrased as legality of the later move.

That phrasing is also the proof. Take the position immediately before the
clearance move, where our piece still sits on V. The follow-up move is illegal
there. Lift our piece off V and nothing else, and the follow-up becomes legal.
Then V was the only thing in the way, and the clearance move is what paid for
it. Nothing about tempo, checks or sacrifices is required -- 01gA2 is a quiet
move -- so none is gated on.

01gA2 is also the one of the twelve this refuses, and knowingly: the rook's
path to h8 is blocked by our own knight on f8 AND by the enemy queen on g8, so
"nothing but our own piece was in the way" is false there. Loosening that to
"our piece plus enemy pieces the line removes" is how a clearance detector
turns into a worse copy of the x-ray one, so the miss is kept.

Measured 2026-09-22 on Lichess theme labels, 600-1500 only:

  recall        1000 `clearance`  detector 94.9%, verified 83.0%
  cross-fire     300 `mateIn2`    6.3%      (no `clearance` tag in the sample)
  cross-fire     300 `fork`       1.3%
  cross-fire     200 `mateIn3`   12.5%      (the length-matched control)
  cross-fire     200 `pin`        5.0%   `skewer` 2.0%   `hangingPiece` 3.5%

The detector/verifier gap is the payoff gate: about 12% of tagged `clearance`
puzzles are defensive or races where the stored line settles under a pawn, and
those stay unverified on purpose. `mateIn3` is the honest ceiling -- six fires
read by hand were four genuine untagged clearances and two doubled-rook ladder
mates (00QW1, 00gNl) where the front rook slides one square further down the
same file. Geometry cannot separate a ladder from a clearance, only a taxonomy
call can, so that residue is left standing rather than gated away by a number.

Deliberately NOT built on `detect_clearance_for_attack` /
`detect_clearance_then_check` in shape_detectors. Measured on 300 Lichess
`clearance` puzzles at 600-1500 those two fire on 32.3% (37.0% if run at every
ply of the line). They are not a weak version of this motif, they are a
different and narrower one: both require the cleared line to end in the
opponent's KING ZONE, because they were written for the Legal's-Mate / Fried
Liver family and they feed live caption variants in R12_blunder.json. Widening
them to the general motif would silently rewrite shipped captions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.line_motif_geometry import (
    LINE_MOTIF_GEOMETRY_VERSION,
    LineWalk,
    line_payoff_cp,
    same_piece,
    squares_between,
    walk_line,
)
from services.stored_line_verifier import parse_legal_move
from services.verified_puzzle_admission import DetectorProof, VerifierProof


CLEARANCE_PROOF_VERSION = f"clearance_puzzle_proof.v1+{LINE_MOTIF_GEOMETRY_VERSION}"
CLEARANCE_QUALITY_ID = "tactic:clearance_with_stored_payoff"
CLEARANCE_CONCEPT_ID = "tactic.clearance"


@dataclass(frozen=True)
class ClearanceProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = CLEARANCE_QUALITY_ID


def _blocked_only_by_own_piece(
    board: chess.Board,
    vacated: int,
    follow_up: chess.Move,
    follow_up_piece: Optional[chess.Piece],
) -> bool:
    """Is `follow_up` illegal here, and legal the instant `vacated` empties?

    This is the whole motif in one counterfactual. Both directions are
    load-bearing: illegal-before rules out a follow-up that never needed the
    clearance, legal-after rules out a follow-up blocked by something else too.
    """
    occupant = board.piece_at(vacated)
    if occupant is None or occupant.color != board.turn:
        return False
    # The king may never be the clearing piece, for two separate reasons.
    #
    # Correctness first: this counterfactual lifts the piece off the board, and
    # a board with no king has no check rule, so EVERY reply becomes "legal"
    # and the test answers yes to anything. Measured 2026-09-22 inside
    # `hangingPiece`: 00B8m `Kxf5`, 00tbH `Kxd2` and 021Lo `Kxf7` all fired,
    # and in all three the position was CHECK -- the follow-up was illegal only
    # because the king was attacked, not because the king was in the way.
    #
    # And teaching second: "the king stepped aside" is not the lesson a 600-1500
    # player takes from a clearance.
    if occupant.piece_type == chess.KING:
        return False
    mover = board.piece_at(follow_up.from_square)
    if mover is None or mover.color != board.turn:
        return False
    # The follow-up must be made by the same piece that stands here now, or
    # "the clearance enabled it" is a claim about a different piece.
    if not same_piece(mover, follow_up_piece):
        return False
    candidate = chess.Move(
        follow_up.from_square, follow_up.to_square, follow_up.promotion
    )
    if candidate in board.legal_moves:
        return False
    probe = board.copy(stack=False)
    probe.remove_piece_at(vacated)
    return candidate in probe.legal_moves


def _left_the_way(
    between: Optional[tuple],
    follow_up: chess.Move,
    clearance: chess.Move,
) -> bool:
    """Did the clearing piece actually leave the follow-up's path?

    Measured 2026-09-22: without this, 28 of 150 `mateIn2` puzzles carrying no
    `clearance` tag fired, and the inspected ones were all the same shape --
    007mr `Rd1+ Rxd1 Rxd1#`, 009IO `Rxf7+ Rxf7 Rxf7#`, 00EXP, 00HAM, 00HEh.
    Doubled heavy pieces on an open file: the front one slides DOWN the file,
    gets traded, and the back one recaptures. The vacated square is on the back
    piece's path, so the bare counterfactual is satisfied, and yet nothing got
    out of anything's way. It is a battery trade, and calling it a clearance
    would teach a beginner the wrong word for the most ordinary move in chess.

    So the clearing piece must not end up on the follow-up's path -- neither
    between it and its destination, nor on the destination itself. Costs zero
    of the twelve hand-checked `clearance` puzzles: every real one steps OFF
    the line (h4->g6, c8->b7, d4->c3), which is the motif in one word.
    """
    if clearance.to_square == follow_up.to_square:
        return False
    if between is not None and clearance.to_square in between:
        return False
    return True


def _locate_clearance(walk: LineWalk) -> Optional[dict]:
    """First (clearance move, follow-up move) pair in the line that proves out.

    Walked over every initiator ply rather than tested on the best move alone,
    for the reason `fork_puzzle_proof._fork_anywhere_in_line` documents: the
    motif frequently is not on move one, and refusing to look further loses
    recall that no threshold change can buy back.
    """
    initiator = walk.initiator
    for index, (before, move) in enumerate(zip(walk.positions, walk.moves)):
        if before.turn != initiator:
            continue
        vacated = move.from_square
        for later in range(index + 1, len(walk.moves)):
            if walk.positions[later].turn != initiator:
                continue
            follow_up = walk.moves[later]
            if follow_up.from_square == vacated:
                # The clearing piece coming back is not a clearance.
                continue
            between = squares_between(follow_up.from_square, follow_up.to_square)
            if not _left_the_way(between, follow_up, move):
                continue
            follow_up_piece = walk.positions[later].piece_at(follow_up.from_square)
            if not _blocked_only_by_own_piece(
                before, vacated, follow_up, follow_up_piece
            ):
                continue
            through = between is not None and vacated in between
            clearing = before.piece_at(vacated)
            return {
                "vacated_square": chess.square_name(vacated),
                "clearing_piece": chess.piece_name(clearing.piece_type),
                "clearance_move": move.uci(),
                "clearance_ply_in_line": index,
                "clearance_is_immediate": index == 0,
                "follow_up_move": follow_up.uci(),
                "follow_up_piece": chess.piece_name(follow_up_piece.piece_type),
                "follow_up_ply_in_line": later,
                # "through" = a slider travels across the vacated square,
                # "onto" = a piece lands on it. Captions must not swap these.
                "clearance_kind": "line" if through else "square",
                "clearance_move_is_capture": before.is_capture(move),
                "clearance_move_gives_check": before.gives_check(move),
                # What the follow-up actually achieves. Recorded, not gated:
                # the geometry is a clearance either way and puzzle extraction
                # still wants it. But a caption needs to point at something,
                # and measured 2026-09-25 on 400 real games, 44.1% of
                # follow-ups were quiet moves achieving nothing visible --
                # the `Rxf2 ... Kf1` shape, where the rook leaves f1 and the
                # king simply steps onto the empty square. The lesson there is
                # "take the free knight on f2", not a clearance.
                "follow_up_is_capture": walk.positions[later].is_capture(follow_up),
                "follow_up_gives_check": walk.positions[later].gives_check(follow_up),
                "follow_up_promotes": follow_up.promotion is not None,
            }
    return None


def build_clearance_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[ClearanceProofBundle]:
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
    located = _locate_clearance(walk)
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
        concept_id=CLEARANCE_CONCEPT_ID,
        family="tactics",
        detector_id="line_motif:clearance",
        detector_version=CLEARANCE_PROOF_VERSION,
        calculation_id="vacated_square_unblocks_later_friendly_move",
        facts=(located,),
        acceptable_moves=(best.uci(),),
        counterfactual={
            "played_move": played.uci(),
            "best_move": best.uci(),
            "cp_loss": loss,
        },
    )
    verifier = VerifierProof(
        concept_id=CLEARANCE_CONCEPT_ID,
        verifier_id="independent_vacancy_counterfactual_and_settled_payoff",
        verifier_version=CLEARANCE_PROOF_VERSION,
        calculation_id="legality_flip_on_empty_square_plus_quiescent_material",
        verified=verified is not None,
        acceptable_moves=(best.uci(),) if verified else (),
        facts=(verified,) if verified else (),
    )
    return ClearanceProofBundle(detector=detector, verifier=verifier)
