"""Change one thing, search again, and see how much of the loss comes back.

The judge. Nothing in this module decides what a move means or proposes why it
was bad -- it takes candidate causes from somewhere else and measures which of
them accounts for the evaluation gap.

Why it exists
-------------
Over one day, six positional mechanisms were written from reading positions and
five of them failed, every time with the same signature: the engine's own best
move had the identical property. A property of ONE move is nearly independent of
the gap between TWO moves, so a good move shares it about as often as a bad one.

Changing one thing and re-searching measures the same quantity the engine
reports, so it cannot have that failure. On
`rn3rk1/1ppq1pp1/3pb2p/p3p3/P1B1P2B/N1PP3P/1P3KP1/R2Q2N1 b - - 5 14` after Nc6,
teleporting the knight to a6 and changing nothing else recovered 100% of the
64cp; to e7 recovered 0; to c5 recovered 137. And on Mohit's e4 position it
corrected a reading of mine that would have shipped: I had the blocked bishop
diagonal as the reason, and the ablation put it at 14 of 66cp.

It is also the ranker. When several candidate causes are true at once, the one
that recovers most of the loss leads -- a measurement instead of an opinion.

What a hypothesis has to be
---------------------------
A change to the position. "The knight has no onward square" is testable: put it
somewhere else and look. "The structure is worse" is not, and must be rejected
before it can become a sentence. That constraint is what makes it safe to let a
model NOMINATE causes: the model proposes, the board decides.

Two traps, both paid for
------------------------
* A FRESH engine per probe. The same position evaluated twice inside one engine
  session returned -28 and -40, because the transposition table carries between
  calls and the second look is informed by the first. `evaluate` is injected so
  the caller owns that, and so this module is testable with no engine at all.
* Clear the en-passant square before moving a pawn. Placing a pawn on the ep
  target square makes the position illegal, and the first run of the e4
  ablation reported every probe "invalid" for that reason alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

import chess

# Evaluate a board from the POV of the side that played the move under test.
# Must be deterministic for the same board: in practice a fresh engine process
# at a fixed depth, with Threads=1.
Evaluator = Callable[[chess.Board], Optional[int]]

TELEPORT = "teleport"
PASS = "pass"
REMOVE = "remove"


@dataclass(frozen=True)
class Hypothesis:
    """A candidate cause, expressed as a change to the board.

    `label` is for the sentence layer and is never evidence. `kind` and the
    squares are the whole of it, because they are what can be applied.
    """
    kind: str
    label: str
    from_square: Optional[int] = None
    to_square: Optional[int] = None
    square: Optional[int] = None


def teleport(from_square: int, to_square: int, label: str = "") -> Hypothesis:
    """"This piece belonged on that square." The commonest testable cause."""
    return Hypothesis(kind=TELEPORT, label=label or "piece belongs elsewhere",
                      from_square=from_square, to_square=to_square)


def pass_instead(label: str = "") -> Hypothesis:
    """"The move achieved nothing." Compared against not moving at all.

    Separates a wasted tempo from a created weakness: on Mohit's e4 the move was
    worth about nothing against passing while the best move was worth +63.
    """
    return Hypothesis(kind=PASS, label=label or "the move achieved nothing")


def remove_piece(square: int, label: str = "") -> Hypothesis:
    """"That piece is the point." Deleting it changes material, so the number
    is directional evidence and never a payoff -- an agent reported 59 -> 26
    from removing a queen and it meant nothing. Use it to REFUTE a cause, which
    is what it is good for: if the loss is unchanged with the piece gone, the
    piece was not the reason."""
    return Hypothesis(kind=REMOVE, label=label or "that piece is the point",
                      square=square)


@dataclass(frozen=True)
class Attribution:
    """What one hypothesis is worth, in the engine's own units."""
    hypothesis: Hypothesis
    recovered_cp: Optional[int]
    share: Optional[float]          # recovered / cost; >1 is real and allowed
    probe_eval_cp: Optional[int]
    skipped: Optional[str] = None   # why it could not be measured


@dataclass(frozen=True)
class AblationResult:
    cost_cp: Optional[int]
    played_eval_cp: Optional[int]
    best_eval_cp: Optional[int]
    attributions: List[Attribution] = field(default_factory=list)

    @property
    def leader(self) -> Optional[Attribution]:
        """The cause that recovers most of the loss, or None."""
        scored = [a for a in self.attributions
                  if a.recovered_cp is not None and a.recovered_cp > 0]
        if not scored:
            return None
        return max(scored, key=lambda a: a.recovered_cp)


def _same_position(a: chess.Board, b: chess.Board) -> bool:
    """Same men on the same squares, same side to move, same castling rights.

    Not a FEN comparison: a position reached by pushing a move and the same
    position reached by teleporting a piece differ in the halfmove and
    fullmove counters, which say nothing about the board.
    """
    return (a.piece_map() == b.piece_map()
            and a.turn == b.turn
            and a.castling_rights == b.castling_rights)


def _clear_ep(board: chess.Board) -> chess.Board:
    board.ep_square = None
    return board


def apply_hypothesis(after_played: chess.Board,
                     h: Hypothesis) -> Optional[chess.Board]:
    """The position with that one thing changed, or None if it cannot be made.

    Side to move, castling rights and everything else are held: the point is to
    change exactly one thing, so that whatever the evaluation does is caused by
    it and not by a second difference nobody is tracking.
    """
    b = after_played.copy(stack=False)
    _clear_ep(b)
    try:
        if h.kind == TELEPORT:
            if h.from_square is None or h.to_square is None:
                return None
            piece = b.piece_at(h.from_square)
            if piece is None or b.piece_at(h.to_square) is not None:
                return None
            if piece.piece_type == chess.KING:
                return None        # moving a king changes legality wholesale
            b.remove_piece_at(h.from_square)
            b.set_piece_at(h.to_square, piece)
        elif h.kind == REMOVE:
            if h.square is None or b.piece_at(h.square) is None:
                return None
            if b.piece_at(h.square).piece_type == chess.KING:
                return None
            b.remove_piece_at(h.square)
        elif h.kind == PASS:
            return None            # handled by the caller; see attribute()
        else:
            return None
        b.clear_stack()
    except Exception:
        return None
    return b if b.is_valid() else None


def attribute(
    fen_before: str,
    played_san: str,
    best_san: Optional[str],
    hypotheses: Sequence[Hypothesis],
    evaluate: Evaluator,
) -> AblationResult:
    """Measure each candidate cause against the loss the engine reports.

    `evaluate` returns centipawns from the POV of the side that played
    `played_san`, for any board handed to it, and must be deterministic for the
    same board -- see the note on fresh engine processes above.

    The cost is the gap between the best move and the played move, measured by
    the SAME evaluator as the probes, so the share is a ratio of like with like
    rather than a fresh number over a stored one. A share above 1.0 is real and
    kept: on the Nc6 position the teleport recovered 69 of a 64cp cost, because
    the probe position is better than the engine's own best move was.
    """
    try:
        board = chess.Board(fen_before)
        played = board.parse_san(str(played_san or "").strip())
    except (ValueError, AssertionError, KeyError):
        return AblationResult(None, None, None, [])
    mover = board.turn

    after = board.copy(stack=False)
    after.push(played)
    played_eval = evaluate(after)

    best_eval = None
    best_board = None
    if best_san:
        try:
            bb = board.copy(stack=False)
            bb.push(bb.parse_san(str(best_san).strip()))
            best_board = bb
            best_eval = evaluate(bb)
        except (ValueError, AssertionError, KeyError):
            best_eval = None
            best_board = None

    cost = None
    if played_eval is not None and best_eval is not None:
        cost = best_eval - played_eval

    out: List[Attribution] = []
    for h in hypotheses:
        if h.kind == PASS:
            # Not a change to the post-move board: it asks what the position
            # was worth without the move at all, so it is measured on the
            # position BEFORE, with the side to move unchanged.
            probe = board.copy(stack=False)
            _clear_ep(probe)
            try:
                probe.push(chess.Move.null())
            except Exception:
                out.append(Attribution(h, None, None, None,
                                       skipped="null move refused"))
                continue
            probe.clear_stack()
        else:
            probe = apply_hypothesis(after, h)
            if probe is None:
                out.append(Attribution(h, None, None, None,
                                       skipped="position not reachable"))
                continue

        # A probe that reconstructs the position after the BEST move carries no
        # information. If the played move is Nb8-c6 and the best move is
        # Nb8-a6, then teleporting the knight from c6 to a6 IS the best move's
        # position, so it recovers exactly the cost every time, by
        # construction. I quoted that 100% twice as evidence the method works
        # before noticing it proves only that the best move scores what the
        # best move scores.
        #
        # Compared on the piece placement and the side to move, not on the FEN,
        # because the move counters differ between a pushed move and a teleport
        # while the position is the same.
        if best_board is not None and _same_position(probe, best_board):
            out.append(Attribution(h, None, None, None,
                                   skipped="reconstructs the best move; "
                                           "nothing to learn"))
            continue

        probe_eval = evaluate(probe)
        if probe_eval is None or played_eval is None:
            out.append(Attribution(h, None, None, probe_eval,
                                   skipped="no evaluation"))
            continue
        recovered = probe_eval - played_eval
        share = (float(recovered) / cost) if cost else None
        out.append(Attribution(h, recovered, share, probe_eval))

    return AblationResult(cost_cp=cost, played_eval_cp=played_eval,
                          best_eval_cp=best_eval, attributions=out)


def fresh_engine_evaluator(engine_path: str, depth: int,
                           pov: bool) -> Evaluator:
    """One process per call, so no probe is informed by the one before it.

    This is the expensive, correct evaluator. It lives here rather than in the
    caller because getting it wrong is silent: the same board inside one engine
    session returned -28 and -40, and nothing in the output says which probe
    warmed the table for which.
    """
    import chess.engine

    def _eval(board: chess.Board) -> Optional[int]:
        try:
            with chess.engine.SimpleEngine.popen_uci(engine_path) as eng:
                eng.configure({"Threads": 1})
                info = eng.analyse(board, chess.engine.Limit(depth=depth))
            score = info.get("score")
            if score is None:
                return None
            return score.pov(pov).score(mate_score=100000)
        except Exception:
            return None

    return _eval
