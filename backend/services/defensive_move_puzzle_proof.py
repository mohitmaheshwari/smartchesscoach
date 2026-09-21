"""Exact defensive-move proof: the quiet move that holds a position together.

Why this exists
---------------
`defensiveMove` is the second-largest endgame-heavy Lichess theme in the
600-1500 band (~204k puzzles), and the endgame is where our weakest accounts
are worst. Nothing in the repo covered it. The names that look close are not:
`defensive_pawn_push` is an opening-passivity caption shape, `stop_opp_pawn`
fires only when the engine's best move is itself a blocking pawn push, and
`endgame_loose_pawn_grab` is the opposite polarity (grabbing, not holding).

POLARITY -- read this before touching a gate
--------------------------------------------
Every other proof in this package ends with "and the line nets at least a
pawn". That gate would reject this entire theme. A defensive move's payoff is
a loss that never happens. There is deliberately no material-gain test here,
and none may be added: the proof obligation is that a concrete threat existed
and that the quiet move answered it.

What the motif actually is (14 stored lines played move by move, 2026-09-22)
----------------------------------------------------------------------------
The solver is under fire and one unglamorous move holds. Measured over 400
puzzles, the signature is a QUIET initiator move -- no capture, no check, no
promotion -- somewhere in the stored line: 100.0% of `defensiveMove` puzzles
have one, against 4.8% of `fork` and 0.5% of `mateIn2` puzzles that do not
also carry the theme. It is a king move 67.2% of the time, and the solver is
already in check 41.2% of the time.

What that quiet move is answering splits four ways, and playing the misses is
what found the third and fourth:

  0071K  Kxa7 Qh7+ Ka6        in check, two legal moves, one holds
  01Btz  Qxb3 Bb5+ Kf8        a piece hangs; the king step saves it
  00Erm  Rxd3 exd3 Rxe6 d2 Bf3   Bf3 stops a pawn one square from queening
  00InW  Kxf3 Kg1 Kxf4 h2 Ng3    Ng3 covers h1 against the h-pawn
  00m6L  Kb6 Ka3 Kb5 Ka2 Ka4     pure opposition -- see the ceiling note

The promotion-threat kind is not decoration: before it existed the detector
found no threat at all in 43.8% of the theme, and almost every one of those
misses was an enemy passed pawn about to queen. That is the defensive mirror
of `advanced_pawn_puzzle_proof`, which is why Lichess co-tags the two so
often.

Measured (2026-09-22, 1000 Lichess `defensiveMove` puzzles rated 600-1500)
--------------------------------------------------------------------------
  detector fires (quiet move answering a named threat)    61.9%
      in_check                                           49.8%
      loses_material                                      6.3%
      pawn_about_to_promote                               5.4%
      mate_in_one                                         0.4%
  cross-fire on 300 `fork` (excluding defensiveMove)       2.7%
  cross-fire on 300 `mateIn2` (excluding defensiveMove)    0.0%

Recall went 52.1% -> 61.1% -> 61.9% over two rounds of fixing, and cross-fire
did not move off 2.7% / 0.0% at any point. Nothing was loosened to get there:
the first round corrected an inverted mate probe and a promotion-path test
that only looked at the queening square, the second corrected a rule-of-the-
square comparison confounded by the defender's tempo.

The live numbers are produced by
`backend/scripts/measure_defensive_move_detector.py`, which runs this module
rather than a copy of it.

Ceiling
-------
38.0% of the theme reaches a quiet move with no threat this module can name,
and that residue is one shape: king-and-pawn endgames decided by opposition,
zugzwang or a distant pawn race (00m6L, 01Me6, 018FT, 00G81), plus a tail of
quiet ATTACKING moves Lichess also tags `defensiveMove` (0199s Rh1). The
board alone cannot license "this was the only move that held" in a zugzwang
-- it takes an engine, and an engine gate inside a proof builder is a
different piece of work. Another 0.8% names a threat it cannot prove was
answered. Both are left unfired on purpose rather than waved through.

`holding_move_count` is reported but never gated on. It is only 2.9% unique
across the theme, because the dominant `in_check` case is answered by most
legal moves; it is informative for the material and promotion kinds and
should be read as evidence, not as a filter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.board_concepts import (
    _passed_pawns,
    _path_clear,
    _steps_to_promote,
)
from services.caption_facts import PIECE_VALUE_CP
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.stored_line_verifier import parse_legal_move, replay_stored_line
from services.verified_puzzle_admission import DetectorProof, VerifierProof


DEFENSIVE_MOVE_PROOF_VERSION = "defensive_move_puzzle_proof.v1"
DEFENSIVE_MOVE_QUALITY_ID = "defense:quiet_move_that_answers_a_threat"

# A threat has to be worth defending against. One pawn is the floor: below it
# the "defence" is noise. This is not a tuned knob -- it is the smallest unit
# of material on the board.
_MIN_MATERIAL_THREAT_CP = PIECE_VALUE_CP[chess.PAWN]
# An enemy pawn this close to promoting, on a clear file, is a live threat.
# Two steps, not one: 00Erm and 00InW both answer a pawn still two moves out.
_PROMOTION_THREAT_STEPS = 2
# Counting how many legal moves also hold is O(legal^2) board work. Above this
# it is skipped and reported as None rather than guessed at.
_UNIQUENESS_SCAN_LIMIT = 48
# `caption_facts.PIECE_VALUE_CP` scores the king at 0 so that exchange walks
# stop before capturing it. Inside a swap-off that zero is actively wrong: it
# makes the king the least valuable attacker and every king recapture free.
# The swap therefore prices the king above a queen.
_KING_VALUE_SENTINEL_CP = 10_000


def _swap_value(piece_type: int) -> int:
    if piece_type == chess.KING:
        return _KING_VALUE_SENTINEL_CP
    return PIECE_VALUE_CP.get(piece_type, 0)


@dataclass(frozen=True)
class DefensiveMoveProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = DEFENSIVE_MOVE_QUALITY_ID


def static_exchange_value(board: chess.Board, move: chess.Move) -> int:
    """Standard swap-off static exchange evaluation, from the mover's side.

    python-chess 1.11 exposes no SEE, and a plain "victim value minus attacker
    value" is wrong the moment a square is defended twice. This is the classic
    gain-list swap: play out least-valuable-attacker recaptures on the target
    square and fold the list back, so a defended piece reads as the loss it
    really is.
    """
    target = move.to_square
    victim = board.piece_at(target)
    attacker = board.piece_at(move.from_square)
    if victim is None or attacker is None:
        return 0
    gain = [_swap_value(victim.piece_type)]
    side = not board.turn
    occupied = board.occupied & ~chess.BB_SQUARES[move.from_square]
    attacker_value = _swap_value(attacker.piece_type)
    depth = 0
    while True:
        depth += 1
        gain.append(attacker_value - gain[depth - 1])
        attackers = board.attackers_mask(side, target) & occupied
        if not attackers:
            break
        least_square = None
        least_value = _KING_VALUE_SENTINEL_CP + 1
        for square in chess.scan_forward(attackers):
            piece = board.piece_at(square)
            if piece is None:
                continue
            value = _swap_value(piece.piece_type)
            if value < least_value:
                least_value = value
                least_square = square
        if least_square is None:
            break
        occupied &= ~chess.BB_SQUARES[least_square]
        attacker_value = least_value
        side = not side
        if depth > 31:
            break
    while len(gain) > 1:
        gain[-2] = -max(-gain[-2], gain[-1])
        gain.pop()
    return gain[0]


def _best_material_threat(board: chess.Board):
    """If the side to move passed, what would the opponent win by capture?

    Returns (gain_cp, target_square) for the opponent's best SEE-positive
    capture, or (0, None).
    """
    if board.is_check():
        # A null move from a position in check produces an illegal board and
        # nonsense move generation. Nothing to read here.
        return 0, None
    passed = board.copy(stack=False)
    try:
        passed.push(chess.Move.null())
    except (AssertionError, ValueError):
        return 0, None
    best_gain = 0
    best_square = None
    for move in passed.legal_moves:
        if not passed.is_capture(move):
            continue
        gain = static_exchange_value(passed, move)
        if gain > best_gain:
            best_gain = gain
            best_square = move.to_square
    return best_gain, best_square


def _mate_threat_square(board: chess.Board) -> Optional[int]:
    """If the side to move passed, could the opponent mate in one?"""
    if board.is_check():
        return None
    passed = board.copy(stack=False)
    try:
        passed.push(chess.Move.null())
    except (AssertionError, ValueError):
        return None
    for move in passed.legal_moves:
        if not passed.gives_check(move):
            continue
        after = passed.copy(stack=False)
        after.push(move)
        if after.is_checkmate():
            return move.to_square
    return None


def _has_mate_in_one(board: chess.Board):
    """Can the side to move mate RIGHT NOW?

    Distinct from `_mate_threat_square`, which asks what the opponent could do
    if the side to move passed. The first version of `threat_is_answered`
    called the null-move probe on the post-move position, which asks whether
    the DEFENDER gets to mate -- exactly backwards, and it threw away most of
    the in-check half of the theme (023eI, 02DwR, 04QN1 all failed this way).
    """
    for move in board.legal_moves:
        if not board.gives_check(move):
            continue
        after = board.copy(stack=False)
        after.push(move)
        if after.is_checkmate():
            return move.to_square
    return None


def _remaining_path(pawn_square: int, color: chess.Color):
    """Every square the pawn still has to cross, promotion square included."""
    file_index = chess.square_file(pawn_square)
    rank = chess.square_rank(pawn_square)
    ranks = range(rank + 1, 8) if color == chess.WHITE else range(rank - 1, -1, -1)
    return [chess.square(file_index, r) for r in ranks]


def _king_box_state(board: chess.Board, pawn_square: int, color: chess.Color):
    """Rule of the square, for one named pawn: (catches, king_distance).

    Same arithmetic as `board_concepts.rule_of_the_square`, applied to one
    pawn instead of scanning the whole board. The distance comes back with
    the verdict because the verdict alone is confounded: the rule grants the
    defender a tempo when it is his move, so a king that is one square too
    far still reads as "catches" before he moves and again after. Comparing
    distances is what separates "the king stepped into the box" from "the
    king was always going to get there" (03Qyl, 0QaJP).
    """
    defender = not color
    king_square = board.king(defender)
    if king_square is None:
        return False, 99
    promo_square = chess.square(
        chess.square_file(pawn_square), 7 if color == chess.WHITE else 0
    )
    steps = _steps_to_promote(pawn_square, color)
    tempo = 1 if board.turn == defender else 0
    distance = chess.square_distance(king_square, promo_square)
    return distance <= steps + tempo, distance


def _promotion_threat(board: chess.Board):
    """An enemy passed pawn close enough to queening to have to be met.

    Reuses `board_concepts`' passed-pawn geometry rather than re-deriving it;
    that module is the single source of truth for what "passed" and "clear
    path" mean in this codebase.
    """
    defender = board.turn
    attacker = not defender
    best = None
    for pawn_square in _passed_pawns(board, attacker):
        if not _path_clear(board, pawn_square, attacker):
            continue
        steps = _steps_to_promote(pawn_square, attacker)
        if steps > _PROMOTION_THREAT_STEPS:
            continue
        if best is None or steps < best[1]:
            best = (pawn_square, steps)
    return best


def describe_threat(board: chess.Board) -> Optional[dict]:
    """What the side to move is actually facing, named and located.

    The order matters: a check is the most concrete thing on the board, then
    a forced mate, then material, then a pawn about to queen.
    """
    if board.is_check():
        king_square = board.king(board.turn)
        return {
            "threat_kind": "in_check",
            "threat_square": (
                chess.square_name(king_square) if king_square is not None else None
            ),
            "threat_value_cp": None,
        }
    mate_square = _mate_threat_square(board)
    if mate_square is not None:
        return {
            "threat_kind": "mate_in_one",
            "threat_square": chess.square_name(mate_square),
            "threat_value_cp": None,
        }
    gain, square = _best_material_threat(board)
    if gain >= _MIN_MATERIAL_THREAT_CP and square is not None:
        piece = board.piece_at(square)
        return {
            "threat_kind": "loses_material",
            "threat_square": chess.square_name(square),
            "threat_value_cp": gain,
            "threatened_piece": (
                chess.piece_name(piece.piece_type) if piece else None
            ),
        }
    promotion = _promotion_threat(board)
    if promotion is not None:
        pawn_square, steps = promotion
        attacker = not board.turn
        promo_square = chess.square(
            chess.square_file(pawn_square), 7 if attacker == chess.WHITE else 0
        )
        return {
            "threat_kind": "pawn_about_to_promote",
            "threat_square": chess.square_name(pawn_square),
            "promotion_square": chess.square_name(promo_square),
            "steps_to_promote": steps,
            "threat_value_cp": None,
        }
    return None


def threat_is_answered(
    board_before: chess.Board,
    move: chess.Move,
    threat: dict,
) -> bool:
    """Did this move actually deal with THAT threat?

    Deliberately targeted at the named threat rather than at the global worst
    thing on the board. An earlier version compared the whole post-move threat
    scan against the whole pre-move one and threw away half the theme, because
    a position that has just survived one threat usually still has a smaller
    one somewhere.
    """
    kind = threat.get("threat_kind")
    after = board_before.copy(stack=False)
    after.push(move)

    if kind == "in_check":
        # Legality already proves the check is gone. The only way this move
        # fails to defend is by walking into mate on the spot.
        return _has_mate_in_one(after) is None

    if kind == "mate_in_one":
        return _has_mate_in_one(after) is None

    if kind == "loses_material":
        if _has_mate_in_one(after) is not None:
            return False
        square = chess.parse_square(threat["threat_square"])
        if move.from_square == square:
            # The threatened piece stepped away. It has to land somewhere the
            # opponent cannot just take it for the same profit.
            gain, _ = _best_material_threat(after)
            return gain < max(_MIN_MATERIAL_THREAT_CP, threat["threat_value_cp"] - 50)
        passed = after.copy(stack=False)
        try:
            passed.push(chess.Move.null())
        except (AssertionError, ValueError):
            return False
        worst_on_square = 0
        for candidate in passed.legal_moves:
            if candidate.to_square != square or not passed.is_capture(candidate):
                continue
            worst_on_square = max(worst_on_square, static_exchange_value(passed, candidate))
        return worst_on_square < max(
            _MIN_MATERIAL_THREAT_CP, threat["threat_value_cp"] - 50
        )

    if kind == "pawn_about_to_promote":
        if _has_mate_in_one(after) is not None:
            return False
        pawn_square = chess.parse_square(threat["threat_square"])
        pawn = after.piece_at(pawn_square)
        if pawn is None or pawn.piece_type != chess.PAWN:
            return True  # captured or already resolved
        attacker = not board_before.turn
        defender = board_before.turn
        if not _path_clear(after, pawn_square, attacker):
            return True
        if after.attackers(defender, pawn_square):
            return True
        # Covering ANY square the pawn still has to cross stops it, not only
        # the queening square. 00IF1 is the case: Bg3 never touches h1, it
        # sits on the h2 crossing square, and an earlier version called that
        # a miss.
        for square in _remaining_path(pawn_square, attacker):
            if after.attackers(defender, square):
                return True
        # Walking the king into the pawn's box stops it too, with no contact
        # at all (03Qyl: Kf1; 0QaJP: Kd3). The king has to both end up inside
        # the box and have closed distance to the queening square -- "inside
        # the box" on its own is satisfied by standing still.
        catches_after, distance_after = _king_box_state(after, pawn_square, attacker)
        _, distance_before = _king_box_state(board_before, pawn_square, attacker)
        if catches_after and distance_after < distance_before:
            return True
        return False

    return False


def _count_holding_moves(board: chess.Board, threat: dict) -> Optional[int]:
    """How many legal moves answer this threat -- the "only move" evidence.

    Reported as a fact, never used as a gate. Cross-fire against `fork` and
    `mateIn2` is already zero once the threat has to be answered, so gating on
    uniqueness would only cost recall for nothing.
    """
    total = board.legal_moves.count()
    if total > _UNIQUENESS_SCAN_LIMIT:
        return None
    holding = 0
    for candidate in board.legal_moves:
        if threat_is_answered(board, candidate, threat):
            holding += 1
    return holding


def _is_quiet(board: chess.Board, move: chess.Move) -> bool:
    return (
        not board.is_capture(move)
        and not board.gives_check(move)
        and move.promotion is None
    )


def verify_defensive_move(
    board_before: chess.Board,
    move: Any,
) -> Optional[dict]:
    """Prove that one quiet legal move answers a concrete threat.

    Returns the threat it answers, or None when there is nothing to defend
    against or the move does not defend.
    """
    quiet = parse_legal_move(board_before, move)
    if quiet is None or not _is_quiet(board_before, quiet):
        return None
    threat = describe_threat(board_before)
    if threat is None:
        return None
    if not threat_is_answered(board_before, quiet, threat):
        return None
    piece = board_before.piece_at(quiet.from_square)
    return {
        **threat,
        "defending_move": quiet.uci(),
        "defending_piece": (
            chess.piece_name(piece.piece_type) if piece else None
        ),
        "defending_from": chess.square_name(quiet.from_square),
        "defending_to": chess.square_name(quiet.to_square),
    }


def _defence_anywhere_in_line(
    board_before: chess.Board,
    best: chess.Move,
    pv_after_best: Sequence[Any],
):
    """Find the quiet holding move on the best move, or later in the line.

    Same lesson as the fork proof: the defensive move is frequently NOT the
    first move. Lichess's own lines often open with a forced recapture and the
    quiet save arrives two or four plies later (004LZ ends on Ke2, 0039T on
    Kf8). Testing only `best_move` would throw those away.

    Returns (board_at_defence, defence_move, facts, ply_index) or None.
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
            facts = verify_defensive_move(board, move)
            if facts is not None:
                return board.copy(stack=False), move, facts, index
        board.push(move)
    return None


def build_defensive_move_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[DefensiveMoveProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    located = _defence_anywhere_in_line(board_before, best, pv_after_best)
    if located is None:
        return None
    defence_board, defence_move, facts, defence_ply = located

    holding = _count_holding_moves(defence_board, facts)
    legal_total = defence_board.legal_moves.count()

    concept_id = "defense.only_move_that_holds"
    detector = DetectorProof(
        concept_id=concept_id,
        family="defense",
        detector_id="shape:defensive_move",
        detector_version=DEFENSIVE_MOVE_PROOF_VERSION,
        calculation_id="quiet_move_answering_named_threat_over_stored_line",
        facts=({
            "threat_kind": facts["threat_kind"],
            "threat_square": facts.get("threat_square"),
            "threat_value_cp": facts.get("threat_value_cp"),
            "threatened_piece": facts.get("threatened_piece"),
            "promotion_square": facts.get("promotion_square"),
            "defending_move": facts["defending_move"],
            "defending_piece": facts["defending_piece"],
            "defending_from": facts["defending_from"],
            "defending_to": facts["defending_to"],
            # 0 means the defence IS the best move. Higher means the stored
            # line starts elsewhere and the save comes later -- a caption must
            # describe the sequence, not the first square.
            "defence_ply_in_line": defence_ply,
            "defence_is_immediate": defence_ply == 0,
            "legal_move_count": legal_total,
            "holding_move_count": holding,
            "is_only_move_that_holds": holding == 1 if holding is not None else None,
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
        verifier_id="independent_threat_reconstruction",
        verifier_version=DEFENSIVE_MOVE_PROOF_VERSION,
        calculation_id="null_move_threat_scan_plus_legal_answer_count",
        # Verified means: a named threat existed, this move answered it, and
        # the answer is not one of many. No material gain is required and none
        # may be -- the payoff of a defensive move is a loss that never
        # happened.
        verified=holding is not None and holding >= 1,
        acceptable_moves=(best.uci(),) if holding else (),
        facts=({
            "threat_kind": facts["threat_kind"],
            "threat_square": facts.get("threat_square"),
            "holding_move_count": holding,
            "legal_move_count": legal_total,
        },) if holding else (),
    )
    return DefensiveMoveProofBundle(detector=detector, verifier=verifier)
