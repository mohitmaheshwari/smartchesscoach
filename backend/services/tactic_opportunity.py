"""Was the chance there at all? An opportunity denominator from the board.

Mohit, 2026-11-27: "first I need all the detectors to evaluate and fire."
The thing standing in the way is not detectors -- it is denominators. Before
this module the system had four:

    kept a piece safe        115,295 chances    destination_safety_exact
    answered their threat     82,092 chances    paired booleans
    punished their mistake    26,109 chances    paired booleans
    found best when critical  144,116 chances   paired booleans

Everything else was a numerator: 79,277 `missed_pattern` rows recorded only
when something went wrong, with no record of how often the same chance came
and went fine. "He missed 1,073 forks" cannot be turned into a rate, so it
cannot be compared between players, tracked over time, or used to decide
whether he still needs a drill.

WHY THIS NEEDS NO ENGINE TIME
-----------------------------
`tactic_tags` already carries Lichess-validated board provers (forced mate
100%, free piece 99.6%, discovered attack 98.3%, pin 98.3%, skewer 97.8%,
fork 96.4%). Each answers one question: "is THIS move the tactic?" The
cp_loss gate that made `found`/`missed` useless as a ratio belongs to the
CALLER, not the prover -- and `ASSUMED_CP_LOSS = 300` is the convention the
Lichess validation itself used.

So the chance can be read straight off the board:

    eligible = some legal move is proved to be the tactic
    fires    = the move he played was not one of them

Measured 2026-11-27 on 600 real positions: **3.1 ms a position**, which is
about 0.7 hours single-threaded over all 766,419 stored moves. No Stockfish,
no PV, no new analysis pass.

WHAT IS IN HERE, AND WHAT IS NOT
--------------------------------
Only the two motifs whose proof needs nothing but the position:

  mate_in_one     exact. `board.is_checkmate()` after the move -- there is
                  nothing to approximate and no prover to trust.
  free_material   the free-piece prover, measured 99.6% on Lichess, and the
                  one that takes no line (`_no_line` in tactic_tags).

Fork, pin, skewer and discovered attack are NOT here, and that is a measured
decision rather than an omission. Their provers need the engine's line to
walk the material payoff: on 120 positions that `tactic_tags` had already
tagged as missed forks, the geometric pre-filter below found the right move
in 96, and `build_fork_proof` refused all 120 when handed an empty line.
Those motifs need either a stored PV (present on 30.9% of moves) or a
board-only payoff proof of their own, validated against the 4.4M-row Lichess
puzzle corpus the existing provers were measured on. Until one of those
exists they would be a guess wearing a denominator.

A NOTE ON THE KING, WHICH COST THE FIRST ATTEMPT
------------------------------------------------
The first version of the fork pre-filter scored the king at 0, on the
obvious reading that a king is never captured. A check must be ANSWERED,
which is the whole mechanism of a fork, so that made every check-fork
invisible: the fork path returned zero on 600 real positions and zero on 120
positions the validated prover had already tagged. The king is the most
forkable man on the board. `_VALUE` says so.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

import chess

from services.free_piece_puzzle_proof import build_free_piece_proof

TACTIC_OPPORTUNITY_VERSION = "tactic_opportunity.v1"

# The same constant tactic_tags uses when it asks a prover about a move it
# already believes in: a proved tactic is winning by construction, and the
# provers refuse a cp_loss under 100 outright.
ASSUMED_CP_LOSS = 300

# See the module docstring: the king is 100, not 0.
_VALUE: Mapping[int, int] = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100,
}

QUALITY_IDS = {
    "mate_in_one": "gap:missed_tactic:mate_in_one",
    "free_material": "gap:missed_tactic:free_material",
}


def _stand_in(board: chess.Board, move: chess.Move) -> Optional[str]:
    """Any other legal move, which is what the provers compare against.

    The provers answer "is `best` the tactic where `played` was not", so
    asking about a move requires something to contrast it with. The same
    convention as tactic_tags._stand_in.
    """
    for other in board.legal_moves:
        if other != move:
            return other.uci()
    return None


def mate_in_one_moves(board: chess.Board) -> List[chess.Move]:
    """Every legal move that is checkmate. Exact, and no prover involved."""
    out: List[chess.Move] = []
    for mv in board.legal_moves:
        board.push(mv)
        try:
            if board.is_checkmate():
                out.append(mv)
        finally:
            board.pop()
    return out


def free_material_candidates(board: chess.Board) -> List[chess.Move]:
    """Captures worth asking about: of an undefended man, or of a bigger one.

    A cheap geometric sieve so the prover is asked about a handful of moves
    rather than all thirty-odd. It may over-offer -- the prover is what
    decides -- but it must never miss a real one, so the test for "free"
    stays deliberately loose.
    """
    out: List[chess.Move] = []
    for mv in board.legal_moves:
        if not board.is_capture(mv):
            continue
        victim = board.piece_at(mv.to_square)
        taker = board.piece_at(mv.from_square)
        if victim is None or taker is None:
            # en passant: the captured pawn is not on the target square
            continue
        defended = bool(board.attackers(victim.color, mv.to_square))
        if not defended or _VALUE[victim.piece_type] > _VALUE[taker.piece_type]:
            out.append(mv)
    return out


def _proved_free(board: chess.Board, candidate: chess.Move) -> bool:
    other = _stand_in(board, candidate)
    if other is None:
        return False
    try:
        bundle = build_free_piece_proof(
            board, other, candidate.uci(), ASSUMED_CP_LOSS)
    except Exception:                                          # noqa: BLE001
        # A prover must never take the analysis pipeline down over one move.
        return False
    return bool(bundle and getattr(bundle.verifier, "verified", False))


def free_material_moves(board: chess.Board) -> List[chess.Move]:
    """Captures the validated free-piece prover confirms win material."""
    return [mv for mv in free_material_candidates(board)
            if _proved_free(board, mv)]


def _verdict(motif: str, takers: Sequence[chess.Move],
             played: Optional[chess.Move]) -> Dict[str, Any]:
    eligible = bool(takers)
    return {
        "quality_id": QUALITY_IDS[motif],
        "version": TACTIC_OPPORTUNITY_VERSION,
        "eligible": eligible,
        # Not eligible means no chance arose, which is NOT a failure. Keeping
        # `fires` False here is what makes the pair a rate: the denominator
        # counts chances, never positions.
        "fires": eligible and (played is None or played not in takers),
        "chances": [mv.uci() for mv in takers],
    }


def opportunities(fen: str, played_uci: Optional[str]) -> Optional[Dict[str, Dict[str, Any]]]:
    """Per motif: did the chance exist, and did he take it?

    Returns None only when the position itself cannot be read. A missing or
    illegal played move still yields the denominator -- the chance existed
    whatever he did with it -- and counts as not taken, because the move we
    cannot read is not one of the proved winners.
    """
    try:
        board = chess.Board(fen)
    except (ValueError, TypeError):
        return None
    if not board.is_valid():
        return None

    played: Optional[chess.Move] = None
    if played_uci:
        try:
            candidate = chess.Move.from_uci(str(played_uci))
        except (ValueError, TypeError):
            candidate = None
        if candidate is not None and candidate in board.legal_moves:
            played = candidate

    return {
        "mate_in_one": _verdict("mate_in_one", mate_in_one_moves(board), played),
        "free_material": _verdict("free_material", free_material_moves(board), played),
    }
