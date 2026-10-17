"""Checking a correction before a player is told they got something wrong.

A compliment is settled by the board: either a knight left its home square or
it did not. A correction -- "a move of this kind was better here" -- is a
claim about a move the player did NOT play, and that is settled by an engine,
at the depth the claim is made at.

WHY THIS EXISTS

The detectors decide a correction from the best move stored at analysis time.
Measured over 400 games against a fresh depth-18 look, that claim held:

    coached_development   53/60 = 88%
    opening_center        31/37 = 84%

against a 95% bar. One correction in eight named an improvement a deeper look
does not back. The worked case is game 02ea7f59 move 5: he played dxe5, the
stored best was Be2 which develops a piece, so the card would have said "a
piece was still sitting at home, and bringing it out was better here" -- while
at depth 18 the move order is Qd3 +179, Be3 +169, Be2 +151, dxe5 +90. The
strongest move is a queen move that develops nothing.

So every correction is verified here before it is allowed to speak, and the
ones that fail are simply not said.

HOW IT IS KEPT CHEAP AND SAFE

  * bounded: at most MAX_CHECKS_PER_GAME positions per review, so one game can
    never turn into an unbounded engine job on the box that serves the app
  * off the event loop: the caller runs `verify_corrections` in a thread and
    hands the main render a finished lookup, so nothing blocks
  * one game at a time: `ucinewgame` before every position, because reusing a
    warm table across unrelated boards was exactly what made the first
    measurement of this untrustworthy
  * fails closed: any error, any timeout, any missing engine means the
    correction is not shown
"""
from __future__ import annotations

import logging
import os
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import chess

logger = logging.getLogger(__name__)

# The depth the claim was measured at. Changing it changes the basis of the
# evidence in docs/detectors_speak_scope.md, so it is not a tuning knob.
VERIFY_DEPTH = 18
# How much better the concept move has to be before "was better here" is fair.
CLEARLY_BETTER_CP = 100
# A bound on what one review can ask of the engine.
MAX_CHECKS_PER_GAME = 3
MULTIPV = 3
ENGINE_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")

# (fen, played_san) -> True when a move of the concept's kind really is
# clearly better. Absent means not checked, which reads as "do not say it".
Verdict = Dict[Tuple[str, str], bool]


def _score(info, colour: chess.Color) -> Optional[int]:
    try:
        return info["score"].pov(colour).score(mate_score=1500)
    except Exception:
        return None


def verify_corrections(
    candidates: Sequence[Tuple[str, str, bool, Callable[[chess.Board, chess.Move, chess.Color], bool]]],
    *,
    depth: int = VERIFY_DEPTH,
    limit: int = MAX_CHECKS_PER_GAME,
) -> Verdict:
    """Check each (fen, played_san, colour, concept_predicate) candidate.

    Synchronous and engine-bound: call it through a thread, never on the
    event loop. Returns only the positions it actually settled.
    """
    out: Verdict = {}
    if not candidates:
        return out
    chosen = list(candidates)[:limit]

    try:
        import chess.engine
    except Exception:
        return out

    engine = None
    try:
        engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
    except Exception:
        logger.info("[CONCEPT_CORRECTION] no engine at %s; corrections stay silent", ENGINE_PATH)
        return out

    try:
        for fen, played_san, is_white, predicate in chosen:
            colour = chess.WHITE if is_white else chess.BLACK
            try:
                board = chess.Board(fen)
                played = None
                for move in board.legal_moves:
                    if board.san(move) == played_san:
                        played = move
                        break
                if played is None:
                    continue

                # A fresh game token forces ucinewgame, so this position is
                # judged on its own and not through the last one's table.
                infos = engine.analyse(
                    board, chess.engine.Limit(depth=depth), multipv=MULTIPV, game=object()
                )
                after_played = board.copy()
                after_played.push(played)
                played_cp = _score(
                    engine.analyse(after_played, chess.engine.Limit(depth=depth), game=object()),
                    colour,
                )
                if played_cp is None:
                    continue

                holds = False
                for info in infos:
                    pv = info.get("pv") or []
                    if not pv:
                        continue
                    candidate = pv[0]
                    if candidate == played:
                        continue
                    try:
                        if not predicate(board, candidate, colour):
                            continue
                    except Exception:
                        continue
                    after_candidate = board.copy()
                    after_candidate.push(candidate)
                    candidate_cp = _score(
                        engine.analyse(
                            after_candidate, chess.engine.Limit(depth=depth), game=object()
                        ),
                        colour,
                    )
                    if candidate_cp is None:
                        continue
                    if candidate_cp - played_cp >= CLEARLY_BETTER_CP:
                        holds = True
                        break
                out[(fen, played_san)] = holds
            except Exception:
                continue
    finally:
        try:
            if engine is not None:
                engine.quit()
        except Exception:
            pass
    return out


def verdict_lookup(verdicts: Verdict) -> Callable[[chess.Board, chess.Move, chess.Color], bool]:
    """Turn finished verdicts into the `verify_correction` the sentence layer
    expects. Anything not in the table is False: unchecked never means true."""

    def _verify(board: chess.Board, move: chess.Move, colour: chess.Color) -> bool:
        try:
            return bool(verdicts.get((board.fen(), board.san(move)), False))
        except Exception:
            return False

    return _verify
