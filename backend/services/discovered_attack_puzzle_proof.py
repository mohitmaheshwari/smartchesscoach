"""Exact discovered-attack proof with independent ray and payoff replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import chess

from services.caption_facts import PIECE_VALUE_CP, _discovered_attack_evidence
from services.concept_detectors.evidence import require_nonnegative_cp_loss
from services.legal_exchange_verifier import independent_exchange_gain
from services.stored_line_verifier import parse_legal_move, replay_stored_line
from services.verified_puzzle_admission import DetectorProof, VerifierProof


DISCOVERED_ATTACK_PROOF_VERSION = "discovered_attack_puzzle_proof.v3"

# The discovered target must be WINNABLE, not merely attacked.
#
# Mohit ruled "unsure" on Nxh7 (2026-09-19): the discovery hits a knight on h6
# that the g7 pawn defends, so Bxh6 gxh6 Qxh6 nets +100 -- a bishop for a knight
# and a pawn. Materially true, and not what "this wins material with a
# discovered attack" tells a player.
#
# Read off the distribution rather than chosen: of 11 claims, 8 won the target
# outright, 2 won 200-299, and exactly one sat at 100. The cut removes that one.
#
# This lives in the detector, not in the review page, so the review queue, the
# caption path and verified_puzzle_builder cannot drift apart on it.
DISCOVERY_WINNABLE_CP = 200
DISCOVERED_ATTACK_QUALITY_ID = "tactic:discovered_attack_with_stored_payoff"


@dataclass(frozen=True)
class DiscoveredAttackProofBundle:
    detector: DetectorProof
    verifier: VerifierProof
    quality_id: str = DISCOVERED_ATTACK_QUALITY_ID


def _ray_step(origin: int, target: int) -> Optional[tuple[int, int]]:
    file_delta = chess.square_file(target) - chess.square_file(origin)
    rank_delta = chess.square_rank(target) - chess.square_rank(origin)
    if file_delta == 0 and rank_delta:
        return 0, 1 if rank_delta > 0 else -1
    if rank_delta == 0 and file_delta:
        return 1 if file_delta > 0 else -1, 0
    if abs(file_delta) == abs(rank_delta) and file_delta:
        return (
            1 if file_delta > 0 else -1,
            1 if rank_delta > 0 else -1,
        )
    return None


def _between(origin: int, target: int) -> tuple[int, ...]:
    step = _ray_step(origin, target)
    if step is None:
        return ()
    file_step, rank_step = step
    file_ = chess.square_file(origin) + file_step
    rank_ = chess.square_rank(origin) + rank_step
    squares = []
    while 0 <= file_ < 8 and 0 <= rank_ < 8:
        square = chess.square(file_, rank_)
        if square == target:
            return tuple(squares)
        squares.append(square)
        file_ += file_step
        rank_ += rank_step
    return ()


def _settled_net_gain(board_before: chess.Board, replay: Any) -> int:
    """Net material after charging back an exchange the line cut short.

    A stored line can stop MID-EXCHANGE, and then its "gain" is an artifact
    of where it was cut rather than a fact about the position.

    Mohit ruled this false on 2026-09-19 and he was right. On
    1rr3k1/4b1p1/1q2p2p/3pPp2/3NnP1P/2RbP1P1/6BK/1qB1R1Q1 the line
    Ba3 Nxc3 Rxb1 Qxb1 Qxb1 scores +800 -- and the very next ply is
    Rxb1, Nxb1 or Bxb1. The queen is taken back by any of three pieces and
    the true net is -100. The detector was recommending a move that loses
    material, with a caption calling it a discovered attack that wins some.

    Same shape as simple_hang's recapture bug: material counted at a moment
    when the exchange was still in flight.

    Extracted verbatim from the material payoff so the discovered-check
    payoff cannot drift away from the ruling that produced it.
    """
    us = board_before.turn
    final = board_before.copy(stack=False)
    last_capture_square = None
    for uci in replay.replayed_uci:
        step = chess.Move.from_uci(uci)
        if final.turn == us and final.is_capture(step):
            last_capture_square = step.to_square
        final.push(step)
    settled = replay.net_material_gain_cp
    if final.turn != us and last_capture_square is not None:
        occupant = final.piece_at(last_capture_square)
        if occupant is not None and occupant.color == us:
            settled -= independent_exchange_gain(final, last_capture_square)
    return settled


def _independent_discovery_payoff(
    board_before: chess.Board,
    best: chess.Move,
    slider_square: int,
    target_square: int,
    continuation: Sequence[Any],
) -> Optional[dict]:
    us = board_before.turn
    slider = board_before.piece_at(slider_square)
    blocker = board_before.piece_at(best.from_square)
    target = board_before.piece_at(target_square)
    if (
        slider is None
        or slider.color != us
        or slider.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN)
        or blocker is None
        or blocker.color != us
        or target is None
        or target.color == us
        or PIECE_VALUE_CP.get(target.piece_type, 0) < PIECE_VALUE_CP[chess.KNIGHT]
    ):
        return None
    step = _ray_step(slider_square, target_square)
    if step is None:
        return None
    file_step, rank_step = step
    if (
        slider.piece_type == chess.BISHOP
        and (file_step == 0 or rank_step == 0)
    ) or (
        slider.piece_type == chess.ROOK
        and file_step != 0
        and rank_step != 0
    ):
        return None
    between = _between(slider_square, target_square)
    occupied_before = tuple(
        square for square in between if board_before.piece_at(square)
    )
    if occupied_before != (best.from_square,):
        return None

    after = board_before.copy(stack=False)
    after.push(best)
    if any(after.piece_at(square) for square in between):
        return None
    if slider_square not in after.attackers(us, target_square):
        return None

    # The checks above prove the ray opens onto the target. They do not price
    # the target square, and a defended target survives all of them.
    probe = after.copy(stack=False)
    probe.turn = us
    if independent_exchange_gain(probe, target_square) < DISCOVERY_WINNABLE_CP:
        return None

    replay = replay_stored_line(board_before, best, continuation)
    if not replay.complete or replay.net_material_gain_cp < PIECE_VALUE_CP[chess.PAWN]:
        return None
    board = board_before.copy(stack=False)
    payoff_ply = None
    target_identity = (target.piece_type, target.color)
    slider_identity = (slider.piece_type, slider.color)
    for index, uci in enumerate(replay.replayed_uci):
        move = chess.Move.from_uci(uci)
        if index > 0 and move.from_square == target_square:
            return None
        if (
            index > 0
            and board.turn == us
            and move.from_square == slider_square
            and move.to_square == target_square
            and board.is_capture(move)
            and board.piece_at(slider_square) is not None
            and (
                board.piece_at(slider_square).piece_type,
                board.piece_at(slider_square).color,
            ) == slider_identity
            and board.piece_at(target_square) is not None
            and (
                board.piece_at(target_square).piece_type,
                board.piece_at(target_square).color,
            ) == target_identity
        ):
            payoff_ply = index + 1
        elif index > 0 and move.from_square == slider_square:
            return None
        board.push(move)
    if payoff_ply is None:
        return None

    settled = _settled_net_gain(board_before, replay)
    if settled < PIECE_VALUE_CP[chess.PAWN]:
        return None

    return {
        "slider_piece": chess.piece_name(slider.piece_type),
        "slider_square": chess.square_name(slider_square),
        "vacated_square": chess.square_name(best.from_square),
        "target_piece": chess.piece_name(target.piece_type),
        "target_square": chess.square_name(target_square),
        "payoff_ply": payoff_ply,
        "net_material_gain_cp": settled,
        "net_material_gain_cp_unsettled": replay.net_material_gain_cp,
        "replayed_uci": replay.replayed_uci,
    }


def _independent_discovered_check_payoff(
    board_before: chess.Board,
    mover: chess.Move,
    continuation: Sequence[Any],
) -> Optional[dict]:
    """Prove a discovered CHECK whose stored line pays off in mate or material.

    Measured 2026-09-22 on 300 Lichess `discoveredAttack` puzzles rated
    600-1500: the largest single miss cluster was the discovery landing on
    the KING rather than on a piece. `_discovered_attack_evidence` emits
    those, and the caller drops them because a king is priced at 0 cp while
    the material gate asks for at least a knight. 39 of 135 misses were
    exactly that, and most of the 30 with no >= knight evidence at all were
    the same shape one ply deeper. On Lichess's `discoveredCheck` theme the
    detector fired on 1.0% of 200 puzzles -- it was blind to the motif.

    The geometry is NOT loosened. It is the same single-blocker vacated ray,
    and it is proven more cheaply than the material case rather than less: a
    slider that is not the moved piece and that gives check after the move
    must have been discovered, because a position where that slider already
    attacked the enemy king could not have been the mover's turn.

    What the check case cannot borrow is the material target's payoff proof
    -- there is no capture of a king to look for -- so the payoff is the
    line's own settled outcome: checkmate, or material that survives the
    recapture charge-back. The opponent has to answer the check before
    anything else, which is the whole motif, so material won from the check
    onwards is the discovery's material.
    """
    us = board_before.turn
    after = board_before.copy(stack=False)
    after.push(mover)
    king_square = after.king(not us)
    if king_square is None:
        return None
    discoverers = [
        square for square in after.checkers() if square != mover.to_square
    ]
    if len(discoverers) != 1:
        return None
    slider_square = discoverers[0]
    slider = after.piece_at(slider_square)
    if (
        slider is None
        or slider.color != us
        or slider.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN)
    ):
        return None
    blocker = board_before.piece_at(mover.from_square)
    if blocker is None or blocker.color != us:
        return None
    between = _between(slider_square, king_square)
    occupied_before = tuple(
        square for square in between if board_before.piece_at(square)
    )
    if occupied_before != (mover.from_square,):
        return None
    if any(after.piece_at(square) for square in between):
        return None

    replay = replay_stored_line(board_before, mover, continuation)
    if not replay.complete:
        return None
    checkmate = bool(replay.checkmate) and replay.checkmating_color == us
    settled = _settled_net_gain(board_before, replay)
    if not checkmate and settled < PIECE_VALUE_CP[chess.PAWN]:
        return None

    return {
        "slider_piece": chess.piece_name(slider.piece_type),
        "slider_square": chess.square_name(slider_square),
        "vacated_square": chess.square_name(mover.from_square),
        "target_piece": chess.piece_name(chess.KING),
        "checked_square": chess.square_name(king_square),
        "checkmate": checkmate,
        "net_material_gain_cp": settled,
        "net_material_gain_cp_unsettled": replay.net_material_gain_cp,
        "replayed_uci": replay.replayed_uci,
    }


def _material_discovery_at(
    board_before: chess.Board,
    mover: chess.Move,
    continuation: Sequence[Any],
) -> Optional[tuple[dict, dict]]:
    """First verified (candidate, payoff) for a material discovery on `mover`.

    Every candidate is tried, highest-value target first. The previous
    version proved only the single highest-value candidate and threw the
    whole position away when that one failed, which discarded positions
    where a lower-value target was the one the stored line actually
    collected.
    """
    after = board_before.copy(stack=False)
    after.push(mover)
    candidates = [
        item
        for item in _discovered_attack_evidence(board_before, after, mover)
        if int(item.get("target_value_cp") or 0) >= PIECE_VALUE_CP[chess.KNIGHT]
    ]
    for candidate in sorted(
        candidates, key=lambda item: -int(item.get("target_value_cp") or 0)
    ):
        try:
            slider_square = chess.parse_square(
                candidate["discovered_attacker_square"])
            target_square = chess.parse_square(candidate["target_square"])
        except (ValueError, KeyError, TypeError):
            continue
        payoff = _independent_discovery_payoff(
            board_before.copy(stack=False),
            mover,
            slider_square,
            target_square,
            continuation,
        )
        if payoff is not None:
            return candidate, payoff
    return None


def _initiator_plies(
    board_before: chess.Board,
    best: chess.Move,
    pv_after_best: Sequence[Any],
) -> list:
    """The best move, then every later move by the same side in its line.

    Measured 2026-09-22 on 300 Lichess `discoveredAttack` puzzles: a large
    share of the misses were not detection failures at all -- the discovery
    simply is not on the best move. Those solutions open with a forcing prep
    move and the discovery lands two to four plies later.
    `fork_puzzle_proof` hit the same wall (66.8% -> 81.9% from walking the
    line) and the fix transfers unchanged: run the SAME scan and the SAME
    payoff proof at each of the side's own plies, proving the payoff from
    where the motif actually stands rather than from the head of the line.

    The best move is always the first entry and is always built from the raw
    caller-supplied continuation, so the immediate case behaves exactly as
    it did before the walk existed.
    """
    plies = [(board_before.copy(stack=False), best, tuple(pv_after_best), 0)]
    replay = replay_stored_line(
        board_before, best, pv_after_best,
        resolve_ambiguous_continuation=True,
    )
    if not replay.complete:
        return plies
    initiator = board_before.turn
    line = list(replay.replayed_uci)
    board = board_before.copy(stack=False)
    for index, uci in enumerate(line):
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in board.legal_moves:
            break
        if board.turn == initiator and index > 0:
            plies.append((
                board.copy(stack=False), move, tuple(line[index + 1:]), index,
            ))
        board.push(move)
    return plies


def _locate_discovery(
    board_before: chess.Board,
    best: chess.Move,
    pv_after_best: Sequence[Any],
) -> Optional[tuple]:
    """Return (detector_facts, verifier_facts, ply) for the first proof found.

    A material discovery beats a discovered check at the same ply because the
    material shape carries the stronger proof -- it names the piece that gets
    won and shows the stored line collecting it -- and an earlier ply beats a
    later one because that is the move the player is being told about.
    """
    for board, mover, continuation, ply in _initiator_plies(
        board_before, best, pv_after_best
    ):
        found = _material_discovery_at(board, mover, continuation)
        if found is not None:
            candidate, payoff = found
            return dict(candidate), dict(payoff), ply
        payoff = _independent_discovered_check_payoff(
            board, mover, continuation)
        if payoff is not None:
            candidate = {
                "discovered_attacker_square": payoff["slider_square"],
                "discovered_attacker_piece_type": payoff["slider_piece"],
                "moved_piece_from_square": payoff["vacated_square"],
                "target_square": payoff["checked_square"],
                "target_piece_type": "king",
                "target_value_cp": PIECE_VALUE_CP[chess.KING],
                "is_check": True,
            }
            return candidate, dict(payoff), ply
    return None


def build_discovered_attack_proof(
    board_before: chess.Board,
    played_move: str,
    best_move: str,
    pv_after_best: Sequence[Any],
    cp_loss: Any,
) -> Optional[DiscoveredAttackProofBundle]:
    try:
        played = parse_legal_move(board_before, played_move)
        best = parse_legal_move(board_before, best_move)
        loss = require_nonnegative_cp_loss(cp_loss)
    except (ValueError, TypeError):
        return None
    if played is None or best is None or played == best or loss < 100:
        return None

    located = _locate_discovery(board_before, best, pv_after_best)
    if located is None:
        # An unverified bundle still has to come back when the SHAPE alone is
        # on the best move: callers read `verified=False` as "the detector
        # looked and does not stand behind this", and one test asserts it.
        after = board_before.copy(stack=False)
        after.push(best)
        shapes = [
            item
            for item in _discovered_attack_evidence(board_before, after, best)
            if int(item.get("target_value_cp") or 0)
            >= PIECE_VALUE_CP[chess.KNIGHT]
        ]
        if not shapes:
            return None
        candidate = max(shapes, key=lambda item: int(item["target_value_cp"]))
        verified = None
        ply = 0
    else:
        candidate, verified, ply = located

    immediate = ply == 0
    # Where the discovery actually lands. 0 = on the best move itself.
    # Anything higher means the best move is a prep move and the discovery
    # arrives later, so a caption must NOT say "you missed a discovered
    # attack here" -- the honest lesson is the line, not the square.
    #
    # The two readers of these facts -- `caption_pipeline`'s
    # missed_discovery_* block and `admin_detector_review`'s claim card --
    # each build a sentence on the ORIGINAL board, and on a later ply they
    # would put the slider, the blocker and the target on squares nobody
    # occupies there. Neither file is edited: the later-ply facts simply
    # decline to supply the key each reader gates on, so both fall through
    # to their own "nothing to say" path. A discovered check declines by
    # arithmetic instead -- its target is a king, priced at 0 cp, which is
    # below every winnable-target gate downstream.
    facts = dict(candidate)
    facts["discovery_ply_in_line"] = ply
    facts["discovery_is_immediate"] = immediate
    facts["discovery_kind"] = (
        "discovered_check" if candidate.get("is_check") else "material"
    )
    if not immediate:
        facts.pop("discovered_attacker_square", None)

    verifier_facts = None
    if verified is not None:
        verifier_facts = dict(verified)
        verifier_facts["discovery_ply_in_line"] = ply
        verifier_facts["discovery_is_immediate"] = immediate
        if not immediate:
            verifier_facts.pop("target_square", None)

    concept_id = "tactic.discovered_attack"
    detector = DetectorProof(
        concept_id=concept_id,
        family="tactics",
        detector_id="canonical_discovered_attack_evidence",
        detector_version=DISCOVERED_ATTACK_PROOF_VERSION,
        calculation_id="canonical_vacated_ray_candidate",
        facts=(facts,),
        acceptable_moves=(best.uci(),),
        counterfactual={
            "played_move": played.uci(),
            "best_move": best.uci(),
            "cp_loss": loss,
        },
    )
    verifier = VerifierProof(
        concept_id=concept_id,
        verifier_id="independent_discovery_ray_and_payoff",
        verifier_version=DISCOVERED_ATTACK_PROOF_VERSION,
        calculation_id="fresh_single_blocker_ray_plus_exact_slider_capture",
        verified=verifier_facts is not None,
        acceptable_moves=(best.uci(),) if verifier_facts else (),
        facts=(verifier_facts,) if verifier_facts else (),
    )
    return DiscoveredAttackProofBundle(detector=detector, verifier=verifier)
