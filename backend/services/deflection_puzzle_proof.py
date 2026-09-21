"""Exact deflection proof: a guard is lured off its job, then the job falls.

Deflection is NOT removal-of-the-guard. In removal the guard is captured
(see `removal_defender_puzzle_proof`). In deflection the guard is still on
the board -- it was *forced to move* by a check or by an unignorable
recapture, and the square it was guarding falls the moment it steps away.

The shape was read off 12 hand-walked Lichess `deflection` puzzles rated
600-1500 before a line of this file was written. All twelve share the same
four beats:

    1. we play a forcing move (a check, or a capture that must be recaptured)
    2. the forced reply moves one enemy piece D off square S
    3. D on S was the *only* enemy defender of some target square T
    4. later in the same stored line we land on T, capturing, promoting or
       mating there

Eleven of the twelve deflected the KING, whose job was guarding a pawn, a
piece, a mating square or a promotion square. That is the motif in one
sentence: the defender is not removed, it is handed something it cannot
refuse.

Measured 2026-09-22 on Lichess puzzles rated 600-1500, `build_deflection_proof`
via `scripts/measure_deflection_attraction_detectors.py`:

    recall on 1000 `deflection`   91.5%
    cross-fire on 300 `mateIn2`    1.3%
    cross-fire on 300 `fork`       0.7%

All six cross-fires were hand-walked and every one is a real deflection that
Lichess simply did not tag (Qg8+ Rxg8 Nf7# deflects the rook off f7;
Qxc6+ bxc6 Ba6# deflects the pawn off a6; Ne1+ Kc4 Nxc2 is a fork AND a
deflection). Motifs overlap, and overlap is not by itself a false positive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

import chess

from services.caption_facts import PIECE_VALUE_CP
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.stored_line_verifier import parse_legal_move, replay_stored_line
from services.verified_puzzle_admission import DetectorProof, VerifierProof


DEFLECTION_PROOF_VERSION = "deflection_puzzle_proof.v1"
DEFLECTION_QUALITY_ID = "tactic:deflection_with_stored_payoff"
DEFLECTION_CONCEPT_ID = "tactic.deflection"


@dataclass(frozen=True)
class DeflectionProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = DEFLECTION_QUALITY_ID


def replay_line_boards(
    board_before: chess.Board,
    best: chess.Move,
    pv_after_best: Sequence[Any],
) -> Optional[Tuple[List[chess.Board], List[chess.Move], chess.Board, int]]:
    """Per-ply boards for the stored line, or None if it does not replay."""
    replay = replay_stored_line(
        board_before,
        best,
        pv_after_best,
        resolve_ambiguous_continuation=True,
    )
    if not replay.complete or not replay.replayed_uci:
        return None
    boards: List[chess.Board] = []
    moves: List[chess.Move] = []
    board = board_before.copy(stack=False)
    for uci in replay.replayed_uci:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return None
        if move not in board.legal_moves:
            return None
        boards.append(board.copy(stack=False))
        moves.append(move)
        board.push(move)
    return boards, moves, board, replay.net_material_gain_cp


def line_payoff_kind(
    final: chess.Board,
    initiator: chess.Color,
    net_material_gain_cp: int,
) -> Optional[str]:
    """The line must actually pay: our mate, or at least a pawn of material."""
    if final.is_checkmate() and final.turn != initiator:
        return "checkmate"
    if net_material_gain_cp >= PIECE_VALUE_CP[chess.PAWN]:
        return "material"
    return None


def _defenders_of(
    board: chess.Board,
    defender_side: chess.Color,
    target: int,
    ghost: Optional[int],
) -> set:
    """Who covers `target`, asked on the position that will actually exist.

    `ghost` is one of OUR squares to empty first. It exists for one case: a
    pawn about to promote cannot block its own file, so a rook or queen
    sitting behind it does defend the promotion square even though
    `attackers()` on the current board says otherwise. Mohit's hand-verified
    puzzle 9OVqg (`8/2P5/8/1kr5/p4R2/8/4K3/8 w`, Rf5 Rxf5 c8=Q) is exactly
    this: the black rook on c5 guards c8 through White's own c7 pawn, and
    without lifting the pawn the proof cannot see the guard at all.
    """
    if ghost is None:
        return set(board.attackers(defender_side, target))
    probe = board.copy(stack=False)
    probe.remove_piece_at(ghost)
    return set(probe.attackers(defender_side, target))


def _promotion_ghosts(
    mid: chess.Board,
    boards: Sequence[chess.Board],
    moves: Sequence[chess.Move],
    initiator: chess.Color,
    start_index: int,
) -> dict:
    """Map each square WE promote on later in the line to that pawn's origin."""
    ghosts = {}
    for index in range(start_index, len(moves)):
        if boards[index].turn != initiator:
            continue
        move = moves[index]
        if move.promotion is None:
            continue
        pawn = mid.piece_at(move.from_square)
        if (
            pawn is not None
            and pawn.color == initiator
            and pawn.piece_type == chess.PAWN
        ):
            ghosts.setdefault(move.to_square, move.from_square)
    return ghosts


def _target_payoff(
    boards: Sequence[chess.Board],
    moves: Sequence[chess.Move],
    initiator: chess.Color,
    start_index: int,
    target: int,
    ghost: Optional[int] = None,
) -> Optional[dict]:
    """Find the later ply where WE land on the square the guard abandoned."""
    defender_side = not initiator
    for index in range(start_index, len(moves)):
        board = boards[index]
        move = moves[index]
        if board.turn != initiator or move.to_square != target:
            continue
        # The guard must still be gone when we cash in. A defender that
        # wandered back and got captured is an exchange, not a deflection.
        #
        # `attackers()` is PSEUDO-legal, so this also rejects lines where the
        # only remaining "defender" is pinned or would be capturing into
        # check -- puzzle 063lr (Re8+ Rd8 Qxb7#) misses because the black
        # king merely looks like it covers b7. Relaxing this to "no LEGAL
        # recapture after our landing move" was measured and reverted: it
        # bought recall 91.5% -> 92.3% while cross-fire on 300 `mateIn2`
        # went 1.3% -> 12.0% and on 300 `fork` 0.7% -> 3.0%. Eight tenths of
        # a recall point is not worth a 9x cross-fire, so the strict test
        # stays and those lines stay uncalled.
        if _defenders_of(board, defender_side, target, ghost):
            return None
        captured = board.piece_at(move.to_square)
        is_capture = board.is_capture(move)
        after = board.copy(stack=False)
        after.push(move)
        is_mate = after.is_checkmate() and after.turn != initiator
        if not (is_capture or move.promotion is not None or is_mate):
            continue
        return {
            "payoff_ply_in_line": index,
            "payoff_move": move.uci(),
            "payoff_is_capture": bool(is_capture),
            "payoff_is_promotion": move.promotion is not None,
            "payoff_is_mate": bool(is_mate),
            "payoff_captured_piece": (
                chess.piece_name(captured.piece_type) if captured else None
            ),
        }
    return None


def _rank(candidate: dict) -> tuple:
    return (
        1 if candidate.get("payoff_is_mate") else 0,
        1 if candidate.get("payoff_is_promotion") else 0,
        int(candidate.get("target_value_cp") or 0),
    )


def _find_deflection(
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
    if payoff_kind is None:
        return None

    for index in range(0, len(moves) - 1):
        if boards[index].turn != initiator:
            continue
        lure = moves[index]
        mid = boards[index + 1]           # after our lure, opponent to move
        reply = moves[index + 1]
        if mid.turn != defender_side:
            continue

        # The reply has to be forced, not chosen: either the lure checks, or
        # the reply recaptures the piece we just parked on that square.
        gives_check = mid.is_check()
        is_recapture = mid.is_capture(reply) and reply.to_square == lure.to_square
        if not (gives_check or is_recapture):
            continue

        guard_square = reply.from_square
        guard = mid.piece_at(guard_square)
        if guard is None or guard.color != defender_side:
            continue

        post = boards[index + 2] if index + 2 < len(boards) else final

        ghosts = _promotion_ghosts(mid, boards, moves, initiator, index + 2)
        candidate_targets = set(mid.attacks(guard_square)) | set(ghosts)

        best_candidate: Optional[dict] = None
        for target in candidate_targets:
            # A guard that moves ONTO the square is a recapture chain, not a
            # deflection -- it never abandoned anything.
            if target == reply.to_square:
                continue
            ghost = ghosts.get(target)
            if guard_square not in _defenders_of(
                mid, defender_side, target, ghost
            ):
                continue
            # Sole defender: once it steps away, nothing of theirs covers the
            # square at all.
            if _defenders_of(post, defender_side, target, ghost):
                continue
            payoff = _target_payoff(
                boards, moves, initiator, index + 2, target, ghost
            )
            if payoff is None:
                continue
            target_piece = mid.piece_at(target)
            # A king standing next to an empty square is not doing a job, it
            # is just standing there. Without this the proof swallows every
            # "Qh7+ Kf8 Qh8#" king-walk mate: 25 of 28 cross-fires on 300
            # `mateIn2` puzzles were exactly that shape, and Lichess tagged
            # none of them `deflection`. All 12 hand-walked gold deflections
            # had the king guarding real material or a promotion square, so
            # this costs nothing there. Non-king guards keep the mating-square
            # case, because a rook or pawn dragged off a mating square (the
            # smothered-mate and Boden's-mate shapes) really is a deflection.
            if (
                guard.piece_type == chess.KING
                and target_piece is None
                and not payoff["payoff_is_promotion"]
            ):
                continue
            candidate = {
                "deflection_ply_in_line": index,
                "deflection_is_immediate": index == 0,
                "lure_move": lure.uci(),
                "lure_gives_check": bool(gives_check),
                "lure_is_recaptured": bool(is_recapture),
                "guard_piece": chess.piece_name(guard.piece_type),
                "guard_square": chess.square_name(guard_square),
                "guard_forced_to": chess.square_name(reply.to_square),
                "guard_reply": reply.uci(),
                "target_square": chess.square_name(target),
                "target_piece": (
                    chess.piece_name(target_piece.piece_type)
                    if target_piece is not None
                    else None
                ),
                "target_value_cp": (
                    PIECE_VALUE_CP.get(target_piece.piece_type, 0)
                    if target_piece is not None
                    else 0
                ),
                "payoff_kind": payoff_kind,
                "net_material_gain_cp": net_gain,
            }
            candidate.update(payoff)
            if best_candidate is None or _rank(candidate) > _rank(best_candidate):
                best_candidate = candidate
        if best_candidate is not None:
            return best_candidate
    return None


def verify_created_deflection(
    board_before: chess.Board,
    move: Any,
    continuation: Sequence[Any],
) -> Optional[dict]:
    """Prove a deflection from a raw position plus its stored continuation."""
    leading = parse_legal_move(board_before, move)
    if leading is None:
        return None
    return _find_deflection(board_before, leading, continuation)


def build_deflection_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[DeflectionProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    independent = _find_deflection(board_before, best, pv_after_best)
    if independent is None:
        return None

    detector = DetectorProof(
        concept_id=DEFLECTION_CONCEPT_ID,
        family="tactics",
        detector_id="shape:deflection",
        detector_version=DEFLECTION_PROOF_VERSION,
        calculation_id="forced_reply_sole_guard_departure_scan",
        facts=(
            {
                "guard_piece": independent["guard_piece"],
                "guard_square": independent["guard_square"],
                "guard_forced_to": independent["guard_forced_to"],
                "target_square": independent["target_square"],
                "target_piece": independent["target_piece"],
                "lure_move": independent["lure_move"],
                # Where the deflection actually lands. 0 = on the best move
                # itself. Anything higher means the best move is a prep move,
                # so a caption must not say "the deflection is here" -- the
                # lesson is the line, not the square.
                "deflection_ply_in_line": independent["deflection_ply_in_line"],
                "deflection_is_immediate": independent["deflection_is_immediate"],
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
        concept_id=DEFLECTION_CONCEPT_ID,
        verifier_id="independent_guard_set_before_and_after_forced_reply",
        verifier_version=DEFLECTION_PROOF_VERSION,
        calculation_id="fresh_attackers_of_target_plus_stored_payoff_landing",
        verified=True,
        acceptable_moves=(best.uci(),),
        facts=(independent,),
    )
    return DeflectionProofBundle(detector=detector, verifier=verifier)
