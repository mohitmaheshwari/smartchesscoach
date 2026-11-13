"""Tactic tags for one move, proved on the board.

Scope: docs/observation_detectors_scope.md (signed 2026-11-13). Each tag says
what a move did with a tactic -- MISSED it, FOUND it, or ALLOWED the opponent
one -- and is written only when one of the board provers below confirms it with
its independent verifier (`bundle.verifier.verified`), never from a model.

Only provers that passed the Lichess precision gate are used (2026-11-13,
strict verifier, puzzles rated <= 1800, 1,500 per side, other tactics as the
control): forced mate 100%, free piece 99.6%, discovered attack 98.3%, pin
98.3% / skewer 97.8% (one prover; its pin/skewer label matched the Lichess
theme 99.0% / 100%), fork 96.4%, back-rank mate 100%. Trapped piece measured
42% and is not used.

How a prover is asked. Every prover answers one question: "is `best` the
tactic, where `played` was not?" given the position, both moves, the line
after `best`, and a cp loss of at least 100. So:

  missed   the real played move, the real best move, the real line, the real
           cp loss: exactly the prover's own question.
  found    the played move asked as `best`, with any other legal move as the
           stand-in `played` and the line after the played move. The caller
           decides how close to the engine's move a found tactic must be.
  allowed  on the board after the played move, the opponent's engine reply
           (first move of the line after the played move) asked as `best`.

The stand-in move and the constant cp loss are the same convention the
Lichess measurement used (scripts/validate_motif_prover_against_lichess.py).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import chess

from services.aligned_tactic_puzzle_proof import build_aligned_tactic_proof
from services.back_rank_mate_puzzle_proof import build_back_rank_mate_proof
from services.discovered_attack_puzzle_proof import build_discovered_attack_proof
from services.forced_mate_puzzle_proof import build_forced_mate_proof
from services.fork_puzzle_proof import build_fork_proof
from services.free_piece_puzzle_proof import build_free_piece_proof
from services.stored_line_verifier import parse_legal_move

TACTIC_TAGS_VERSION = "tactic_tags.v1"
ASSUMED_CP_LOSS = 300  # a proved tactic is winning by construction
# A played tactic counts as FOUND only when it cost less than this against the
# engine's best. Measured 2026-11-13 on 40 of Mohit's games, both sides: 139 of
# 170 played tactics cost under 50 cp (118 of 133 free-piece captures cost 0),
# and every played fork cost 50 or more -- a real fork, with something better
# on the board. Calling those "found" would praise a move the card grades as
# a mistake.
FOUND_MAX_CP_LOSS = 49


def _no_line(fn: Callable) -> Callable:
    return lambda board, played, best, line, cp: fn(board, played, best, cp)


# Order is the precedence when one move carries several tags: mate first,
# then the larger material ideas (signed scope, open question 4).
PROVERS: Tuple[Tuple[str, Callable], ...] = (
    ("forced_mate", build_forced_mate_proof),
    ("back_rank_mate", _no_line(build_back_rank_mate_proof)),
    ("fork", build_fork_proof),
    ("discovered_attack", build_discovered_attack_proof),
    ("line_attack", build_aligned_tactic_proof),   # named pin / skewer below
    ("free_piece", _no_line(build_free_piece_proof)),
)


def _motif_name(motif: str, bundle: Any) -> str:
    if motif != "line_attack":
        return motif
    concept = str(getattr(bundle.detector, "concept_id", "") or "")
    return "skewer" if concept.endswith("skewer") else "pin"


def _tactic_ply(board: chess.Board, first: chess.Move, line: Sequence[Any],
                facts: Dict[str, Any]) -> int:
    """Where in the line the tactic happens: 0 = on the tagged move itself.

    Half the forks and discovered attacks in Mohit's games (2026-11-13 hand
    check) happen later in the engine line -- "b4" whose fork is Qb3+ five
    plies on. A card must not call b4 the fork, so every tag carries this.
    Counted on the line replayed from the tagged move; the prover's own
    `replayed_uci` starts wherever its proof starts, not at the tagged move.
    """
    fork_sq = facts.get("fork_square")
    vacated = facts.get("vacated_square")
    attacker_sq = (facts.get("attacker_square")
                   if facts.get("creation_mode") == "direct" else None)
    if not (fork_sq or vacated or attacker_sq):
        return 0
    b = board.copy(stack=False)
    moves = [first]
    b.push(first)
    for raw in line or ():
        mv = parse_legal_move(b, raw)
        if mv is None:
            break
        moves.append(mv)
        b.push(mv)
    for k, mv in enumerate(moves):
        if k % 2:            # only the side that plays the tactic
            continue
        u = mv.uci()
        if fork_sq and u[2:4] == fork_sq:
            return k
        if vacated and u[0:2] == vacated:
            return k
        if attacker_sq and u[2:4] == attacker_sq:
            return k
    return 0


def _stand_in(board: chess.Board, move: chess.Move) -> Optional[str]:
    for other in board.legal_moves:
        if other != move:
            return other.uci()
    return None


def prove(board: chess.Board, played: Any, best: Any, line: Sequence[Any],
          cp_loss: Any) -> List[Dict[str, Any]]:
    """Every gated prover that verifies `best` as its tactic. Facts are the
    prover's own (pieces, squares, payoff), kept so a caption and an arrow can
    be built from exactly what was proved."""
    out: List[Dict[str, Any]] = []
    for motif, fn in PROVERS:
        try:
            bundle = fn(board, played, best, list(line or ()), cp_loss)
        except Exception:                                   # noqa: BLE001
            continue
        if bundle is None or not getattr(bundle.verifier, "verified", False):
            continue
        out.append({
            "motif": _motif_name(motif, bundle),
            "concept_id": getattr(bundle.detector, "concept_id", None),
            "detector_facts": [dict(f) for f in (bundle.detector.facts or ())],
            "verifier_facts": [dict(f) for f in (bundle.verifier.facts or ())],
            "prover_version": getattr(bundle.verifier, "verifier_version", None),
        })
        facts = (out[-1]["verifier_facts"] or out[-1]["detector_facts"] or [{}])[0]
        first = parse_legal_move(board, best)
        out[-1]["at_ply"] = (_tactic_ply(board, first, line, facts)
                             if first is not None else 0)
    return out


def tag_move(
    fen_before: str,
    played: str,
    *,
    best: Optional[str],
    pv_after_best: Sequence[Any] = (),
    pv_after_played: Sequence[Any] = (),
    cp_loss: Any = 0,
    found_max_cp_loss: int = FOUND_MAX_CP_LOSS,
) -> List[Dict[str, Any]]:
    """Tags for one move. Empty when nothing is proved.

    `found_max_cp_loss`: a played tactic counts as FOUND only when the move
    lost at most this much against the engine's best (FOUND_MAX_CP_LOSS).
    """
    try:
        board = chess.Board(fen_before)
    except ValueError:
        return []
    played_move = parse_legal_move(board, played)
    if played_move is None:
        return []
    best_move = parse_legal_move(board, best) if best else None
    loss = int(cp_loss or 0)
    tags: List[Dict[str, Any]] = []

    # MISSED: the engine's move was the tactic and the played move was not.
    if best_move is not None and best_move != played_move and loss >= 100:
        for t in prove(board, played_move.uci(), best_move.uci(),
                       pv_after_best, loss):
            t.update(kind="missed", move=board.san(best_move))
            tags.append(t)

    # FOUND: the played move is the tactic, and it was (close to) best.
    if loss <= found_max_cp_loss:
        stand_in = _stand_in(board, played_move)
        if stand_in:
            line = list(pv_after_played or ())
            for t in prove(board, stand_in, played_move.uci(), line,
                           ASSUMED_CP_LOSS):
                t.update(kind="found", move=board.san(played_move))
                tags.append(t)

    # ALLOWED: the move hands the opponent a tactic (their engine reply).
    if loss >= 100 and pv_after_played:
        after = board.copy(stack=False)
        after.push(played_move)
        reply = parse_legal_move(after, pv_after_played[0])
        stand_in = _stand_in(after, reply) if reply is not None else None
        if reply is not None and stand_in:
            for t in prove(after, stand_in, reply.uci(),
                           list(pv_after_played[1:]), ASSUMED_CP_LOSS):
                t.update(kind="allowed", move=after.san(reply))
                tags.append(t)

    for t in tags:
        t["version"] = TACTIC_TAGS_VERSION
    return tags
