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
        "sound_continuation": [],
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
        best_pv = list(info.get("pv") or [])
        best_move = (best_pv or [None])[0]

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
            # The teaching, not just the verdict. Being told "c6 was the move"
            # and nothing else is the same empty card this product has been
            # criticised for all week; the line is what makes it a lesson.
            out["sound_continuation"] = _line_san(board, best_pv)
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


def _line_san(board: chess.Board, moves: List[chess.Move], limit: int = 6) -> List[str]:
    """The engine's line from here, in notation a player can read."""
    walk = board.copy(stack=False)
    out: List[str] = []
    for move in moves[:limit]:
        if move not in walk.legal_moves:
            break
        out.append(walk.san(move))
        walk.push(move)
        if walk.is_game_over():
            break
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


# ── choosing a position worth being tested on ─────────────────────────

# A position with nothing to work out teaches nothing. Three half-moves is the
# floor: your move, their answer, your follow-up.
MIN_REQUIRED_PLY = 3
# Already decided positions are excluded. A line you miss when the game is
# gone is not a calculation failure worth a player's time.
MIN_HEADROOM = 0.10
CANDIDATE_MIN_CP_LOSS = 150


async def pick_test_positions(db, user_id: str, count: int = 3,
                              engine=None, depth: int = 16) -> List[Dict[str, Any]]:
    """Positions from this player's OWN games where they missed a line.

    Their own games on purpose: a position they have already sat in is one they
    can be shown going wrong in, and it is the difference between an exercise
    and a diagnosis.

    DEPTH-MATCHED. The scope's second validation check is that the test agrees
    with itself across positions, and three positions needing 3, 5 and 9
    half-moves would produce three different answers from a perfectly
    consistent player. That spread would read as noise when it is the
    instrument. So candidates are grouped by required depth and all of them are
    drawn from one group.
    """
    from services.expected_points import headroom

    games = await db.games.find(
        {"user_id": user_id, "is_analyzed": True},
        {"_id": 0, "game_id": 1, "user_color": 1},
    ).to_list(400)
    colour = {g["game_id"]: str(g.get("user_color", "")).lower().startswith("w")
              for g in games}
    if not colour:
        return []

    raw: List[Dict[str, Any]] = []
    async for doc in db.game_analyses.find(
        {"game_id": {"$in": list(colour)}},
        {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ):
        white = colour.get(doc.get("game_id"))
        if white is None:
            continue
        for mv in (doc.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            if mv.get("is_opponent_move") or mv.get("mate_info"):
                continue
            cp_loss, eval_before = mv.get("cp_loss"), mv.get("eval_before")
            fen, best = mv.get("fen_before"), mv.get("best_move")
            pv = mv.get("pv_after_best") or []
            if not fen or not best or len(pv) < MIN_REQUIRED_PLY:
                continue
            if not isinstance(cp_loss, (int, float)) or cp_loss < CANDIDATE_MIN_CP_LOSS:
                continue
            if not isinstance(eval_before, (int, float)):
                continue
            own = eval_before if white else -eval_before
            if (headroom(own) or 0) < MIN_HEADROOM:
                continue
            raw.append({
                "game_id": doc["game_id"],
                "move_number": mv.get("move_number"),
                "fen": fen,
                "you_played": mv.get("move"),
                "cp_loss": int(cp_loss),
                # pv_after_best is the continuation AFTER the best move and
                # does NOT contain it, so the best move is put back on the
                # front. Without this the line starts one half-move in and its
                # first move is not even legal from the test position -- which
                # is what grading the engine's own line as "unsound at ply 1"
                # was telling us.
                "stored_line": [str(best)] + [str(x) for x in pv[:11]],
            })

    if not raw or engine is None:
        return raw[:count]

    # Measure the real depth of the best candidates, then take one depth band.
    raw.sort(key=lambda r: -r["cp_loss"])
    measured: List[Dict[str, Any]] = []
    for item in raw[:40]:
        try:
            need = required_depth(chess.Board(item["fen"]), engine, depth)
        except Exception:
            continue
        if need < MIN_REQUIRED_PLY:
            continue
        item["required_depth"] = need
        measured.append(item)
        if len(measured) >= 24:
            break

    if not measured:
        return []
    bands: Dict[int, List[Dict[str, Any]]] = {}
    for item in measured:
        bands.setdefault(item["required_depth"], []).append(item)
    best_band = max(bands.values(), key=len)
    return best_band[:count]
