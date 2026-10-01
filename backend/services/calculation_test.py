"""Showing your working: grade a line a player calculated without moving pieces.

docs/calculation_test_scope.md.

WHY THIS EXISTS
---------------
Every answer this product has ever asked for is ONE move -- `best_move_san` in
training, in the diagnostic, in missions, in play, and nothing anywhere accepts
a sequence. So we measure whether a player spots the first move and never
whether they can see the line through.

Games cannot close that. Measured 2026-09-30 over 10,679 mistakes and 46
players, what we can see is where the punishment lands and what shape it takes
-- calculation PERFORMANCE. The same good move comes from working it out, from
recognising the pattern, or from luck, and no game record separates those. A
test with no clock can.

WHAT IS GRADED, AND WHY IT IS THREE THINGS
------------------------------------------
Three separate skills, kept apart because a player can have one and not another:

    found_the_idea   did their first move keep the point of the position
    sound_through    how many half-moves their line stays sound
    judged_the_end   were they right about how it finishes

A player can see six half-moves correctly and still call a drawn position
winning. Folding that into one score would hide it.

THE LINE HAS NO FIXED LENGTH
----------------------------
Mohit, 2026-10-01: "calculation can be more than one step too, right?" A fixed
three-input box measures a three-ply horizon and nothing past it. Some positions
resolve in three half-moves and some in nine, so the POSITION carries its own
required depth and stopping short is recorded as stopping short -- a different
failure from going wrong, and a different thing to say to a player.

ALTERNATING STANDARDS
---------------------
The player's own moves and the opponent's are not judged the same way. Theirs
must keep the advantage; the opponent's must be the defence that tests them. A
player who answers their own best line with a feeble reply for the opponent has
not calculated anything, which is the trap the whole exercise exists to catch.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess

# How much a player's move may give up and still count as keeping the idea.
# Chosen to match the inaccuracy band the rest of the product uses rather than
# invented here; it is a product setting to validate against real submissions,
# not a measured constant.
PLAYER_SLACK_CP = 90

# How much worse than best the opponent's move may be and still count as the
# defence the player had to see. Tighter, because an easy reply for the
# opponent proves nothing about the player.
OPPONENT_SLACK_CP = 60

# A position is settled once the evaluation stops moving by more than this.
SETTLED_SWING_CP = 50
MAX_REQUIRED_PLY = 12

FOUND, MISSED = "found_the_idea", "missed_the_idea"
SOUND, UNSOUND = "sound", "unsound"
TOO_EASY = "gave_the_opponent_an_easy_move"


def _own_cp(score, mover: chess.Color) -> Optional[int]:
    """Centipawns from the mover's side. Mate is clamped, never scaled.

    `mate > 0` is NOT a safe test for "mating" because mate-in-0 means the mate
    has already been DELIVERED, and Python cannot tell Mate(-0) from Mate(+0) --
    both are the integer 0. Reading it as a loss told a player who had just
    found mate in one that they had missed the idea, scored at 20000
    centipawns given up.

    A terminal position is therefore read off the BOARD by `_eval_of`, and this
    function only ever sees non-terminal ones; the `>= 0` here is belt and
    braces for a score that arrives from somewhere else.
    """
    if score is None:
        return None
    pov = score.pov(mover)
    if pov.is_mate():
        mate = pov.mate()
        return 10000 if (mate is None or mate >= 0) else -10000
    return pov.score()


def _eval_of(board: chess.Board, engine, pov: chess.Color,
             depth: int) -> Optional[int]:
    """Evaluation from `pov`, correct on a finished position.

    Stockfish returns Mate(-0) on a board that is already mate, which is
    ambiguous in Python. The board is not: whoever is to move has been mated.
    """
    if board.is_checkmate():
        return 10000 if pov != board.turn else -10000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    return _own_cp(engine.analyse(board, chess.engine.Limit(depth=depth)).get("score"), pov)


def required_depth(board: chess.Board, engine, depth: int = 18) -> int:
    """How many half-moves before the outcome of this position is settled.

    Walks the engine's own best line and stops when the evaluation stops
    moving. This is what tells us whether a player who stopped at three
    half-moves stopped EARLY or stopped because there was nothing left to see.
    """
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    pv = list(info.get("pv") or [])[:MAX_REQUIRED_PLY]
    if not pv:
        return 0
    mover = board.turn
    walk = board.copy(stack=False)
    last = _own_cp(info.get("score"), mover)
    settled_for = 0
    for i, move in enumerate(pv, start=1):
        walk.push(move)
        if walk.is_game_over():
            return i
        here = _eval_of(walk, engine, mover, depth)
        if last is not None and here is not None and abs(here - last) <= SETTLED_SWING_CP:
            settled_for += 1
            if settled_for >= 2:
                return max(1, i - 1)
        else:
            settled_for = 0
        last = here
    return len(pv)


def grade_line(fen: str, submitted: List[str], engine,
               verdict: Optional[str] = None, depth: int = 18) -> Dict[str, Any]:
    """Grade a line the player worked out, half-move by half-move.

    `submitted` alternates: their move, the opponent's, theirs, and so on, in
    SAN or UCI. It may be any length, including one.

    Returns a per-half-move trace plus the three separate readings. Grading
    STOPS at the first unsound half-move, because everything after it is a
    line from a position that would not have arisen.
    """
    board = chess.Board(fen)
    mover = board.turn
    out: Dict[str, Any] = {
        "schema_version": "calculation_test.v1",
        "fen": fen,
        "plies": [],
        "found_the_idea": None,
        "sound_through": 0,
        "stopped_early": None,
        "judged_the_end": None,
        "required_depth": None,
    }

    try:
        out["required_depth"] = required_depth(board, engine, depth)
    except Exception:
        out["required_depth"] = None

    for index, raw in enumerate(submitted):
        theirs = (index % 2 == 0)        # the player moves on even indices
        info = engine.analyse(board, chess.engine.Limit(depth=depth))
        best_cp = _own_cp(info.get("score"), board.turn)
        best_move = (list(info.get("pv") or []) or [None])[0]

        move = _parse(board, raw)
        if move is None:
            out["plies"].append({"ply": index + 1, "by": "you" if theirs else "opponent",
                                 "move": str(raw), "verdict": "could not read that move"})
            break

        after = board.copy(stack=False)
        after.push(move)
        played_cp = _eval_of(after, engine, board.turn, depth)
        lost = (best_cp - played_cp) if (best_cp is not None and played_cp is not None) else 0

        if theirs:
            ok = lost <= PLAYER_SLACK_CP
            verdict_text = SOUND if ok else UNSOUND
        else:
            # The opponent must put up the defence the player had to see.
            ok = lost <= OPPONENT_SLACK_CP
            verdict_text = SOUND if ok else TOO_EASY

        out["plies"].append({
            "ply": index + 1,
            "by": "you" if theirs else "opponent",
            "move": board.san(move),
            "best": board.san(best_move) if best_move else None,
            "gave_up_cp": max(0, lost),
            "verdict": verdict_text,
        })

        if index == 0:
            out["found_the_idea"] = FOUND if ok else MISSED

        if not ok:
            break
        out["sound_through"] = index + 1
        board = after
        if board.is_game_over():
            break

    needed = out["required_depth"]
    if needed:
        out["stopped_early"] = (
            len(submitted) < needed and out["sound_through"] == len(submitted))

    if verdict:
        out["judged_the_end"] = _judge(board, engine, verdict, mover, depth)
    return out


def _parse(board: chess.Board, raw: str) -> Optional[chess.Move]:
    text = str(raw or "").strip()
    if not text:
        return None
    for reader in (board.parse_san, lambda t: chess.Move.from_uci(t)):
        try:
            move = reader(text)
        except Exception:
            continue
        if move in board.legal_moves:
            return move
    return None


def _judge(board: chess.Board, engine, verdict: str, mover: chess.Color,
           depth: int) -> Dict[str, Any]:
    """Was the player right about how the position ends?

    Graded against the position their line actually reached, not the one the
    engine would have reached, because that is the position they were looking
    at when they called it.
    """
    cp = _eval_of(board, engine, mover, depth)
    if cp is None:
        return {"said": verdict, "actually": None, "right": None}
    actually = "winning" if cp >= 200 else ("losing" if cp <= -200 else "level")
    said = str(verdict).strip().lower()
    return {"said": said, "actually": actually, "right": said == actually}
