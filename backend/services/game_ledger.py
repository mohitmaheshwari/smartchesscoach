"""The game's timeline and its event ledger: what happened, for both players.

docs/game_story_by_phase_scope.md (v2), signed off by Mohit 2026-10-22.

Two layers, both pure -- no database, no engine, no language model:

    TIMELINE  the player's evaluation at every position, both players' moves.
              Stored `move_evaluations` hold only the player's moves, but each
              row carries eval_before (after the OPPONENT's move) and
              eval_after (after the player's own), so chained in order they
              cover every position. Measured 2026-10-21: 197,000 of 197,000
              positions across 2,920 games had a stored evaluation. The
              opponent's moves themselves are recovered by matching the board
              after the player's move to the board before the next one.

    LEDGER    the events that matter, each with its evidence and a flag for
              whether it HAPPENED on the board or only COULD have. A missed
              queen trap is never recorded as a trap that happened.

Nothing here decides how a game is told. The story planner reads the ledger;
this module only says what is true and how sure it is.

What counts as a mistake is not decided here either. Both players' moves are
judged by `severity.classify_severity_practical`, which works from the change
in winning chances, the same judgement the rest of the product uses.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

import chess

from services.severity import classify_severity_practical

LEDGER_VERSION = "game_ledger.v1"

CLAMP = 1000  # mate scores and runaway evals flatten here, both sides

# Practical tiers that make a move an event. "inaccuracy" is left out: a
# story of a game is not a list of every small slip.
_EVENT_TIERS = ("mistake", "serious", "blunder")

# How much of a chance the opponent must hand back for it to count as not
# punished. Provisional, from the 2026-10-21 census of 3,000 games; to be
# locked against the ledger's own distribution.
_RECOVERED_SHARE = 0.6

# The opening ends where the material phase leaves "opening", or at this move,
# whichever is first. Measured over 561 games on 2026-10-22, the material phase
# leaves "opening" at move 15 at the median and only by move 12 in the earliest
# third -- too late for "how did the opening go" in a game with no early trades.
OPENING_LAST_MOVE = 12

_PIECE_VALUE = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
                chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}


def opening_phase_exit_move(pgn: Optional[str]) -> Optional[int]:
    """The move where the material phase first leaves "opening", or None.

    Uses the product's own phase measure (services.game_phase_service), so
    the story's start ends where the rest of the product's opening does.
    """
    if not pgn:
        return None
    try:
        import io

        import chess.pgn

        from services.game_phase_service import get_game_phase

        game = chess.pgn.read_game(io.StringIO(str(pgn)))
        if game is None:
            return None
        board = game.board()
        for move in game.mainline_moves():
            board.push(move)
            if get_game_phase(board)["phase_label"] != "opening":
                return board.fullmove_number
    except Exception:
        return None
    return None


# ─── Timeline ──────────────────────────────────────────────────────────


def _clamp(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return max(-CLAMP, min(CLAMP, int(value)))
    except (TypeError, ValueError):
        return None


def _player_pov(white_cp: Optional[int], player_is_white: bool) -> Optional[int]:
    if white_cp is None:
        return None
    return white_cp if player_is_white else -white_cp


def _placement(fen: str) -> str:
    """Board placement and side to move: what must match between two FENs."""
    parts = (fen or "").split(" ")
    return " ".join(parts[:2])


def _connecting_move(board_from: chess.Board, fen_to: str) -> Optional[chess.Move]:
    target = _placement(fen_to)
    for move in board_from.legal_moves:
        board_from.push(move)
        hit = _placement(board_from.fen()) == target
        board_from.pop()
        if hit:
            return move
    return None


def _player_rows(move_evaluations: Sequence[Mapping[str, Any]], player_is_white: bool):
    side = "w" if player_is_white else "b"
    rows = []
    for row in move_evaluations or []:
        fen = row.get("fen_before") or ""
        parts = fen.split(" ")
        if len(parts) < 2 or parts[1] != side or row.get("is_opponent_move"):
            continue
        rows.append(row)
    rows.sort(key=lambda r: (r.get("move_number") or 0))
    return rows


def build_timeline(
    move_evaluations: Sequence[Mapping[str, Any]],
    user_color: str,
) -> List[Dict[str, Any]]:
    """Every move of the game in order, both players, each with its evaluation.

    A point is one move: who played it, the move, and the player-side
    evaluation before and after it. Opponent moves the stored data cannot
    reconstruct are left out rather than guessed.
    """
    player_is_white = str(user_color or "white").lower() == "white"
    rows = _player_rows(move_evaluations, player_is_white)
    points: List[Dict[str, Any]] = []

    # The opponent's first move, when the player has Black.
    if rows and not player_is_white:
        start = chess.Board()
        move = _connecting_move(start, rows[0].get("fen_before") or "")
        if move is not None:
            points.append(_opponent_point(start, move, rows[0], None, player_is_white,
                                          eval_before=0))

    for index, row in enumerate(rows):
        fen_before = row.get("fen_before")
        try:
            board = chess.Board(fen_before)
            played = board.parse_san(str(row.get("move")))
        except (ValueError, TypeError):
            continue
        before = _player_pov(_clamp(row.get("eval_before")), player_is_white)
        after = _player_pov(_clamp(row.get("eval_after")), player_is_white)
        points.append({
            "side": "you",
            "move_number": row.get("move_number"),
            "san": row.get("move"),
            "uci": played.uci(),
            "fen_before": fen_before,
            "eval_before": before,
            "eval_after": after,
            "row": row,
        })
        nxt = rows[index + 1] if index + 1 < len(rows) else None
        if nxt is None:
            continue
        board.push(played)
        move = _connecting_move(board, nxt.get("fen_before") or "")
        if move is None:
            continue
        points.append(_opponent_point(board, move, nxt, row, player_is_white,
                                      eval_before=after))
    return points


def _opponent_point(board: chess.Board, move: chess.Move, next_row, prev_row,
                    player_is_white: bool, *, eval_before) -> Dict[str, Any]:
    return {
        "side": "them",
        "move_number": board.fullmove_number,
        "san": board.san(move),
        "uci": move.uci(),
        "fen_before": board.fen(),
        "eval_before": eval_before,
        "eval_after": _player_pov(_clamp(next_row.get("eval_before")), player_is_white),
        # What the engine wanted them to play here, when it was stored: the
        # first move of the line after the player's previous move.
        "best_san": ((prev_row or {}).get("pv_after_played") or [None])[0],
    }


# ─── Board proofs for "what could have happened" ────────────────────────


def _queen_trapped_after(board: chess.Board, owner: chess.Color) -> bool:
    """The owner's queen is attacked and every queen move lands on an attacked
    square, with the owner NOT in check (a check is not a trap)."""
    if board.turn != owner or board.is_check():
        return False
    queens = list(board.pieces(chess.QUEEN, owner))
    if len(queens) != 1:
        return False
    queen = queens[0]
    if not board.attackers(not owner, queen):
        return False
    for move in board.legal_moves:
        if move.from_square != queen:
            continue
        # Taking the enemy queen is a trade, not a loss: a way out.
        captured = board.piece_at(move.to_square)
        if captured is not None and captured.piece_type == chess.QUEEN:
            return False
        board.push(move)
        safe = not board.attackers(not owner, move.to_square)
        board.pop()
        if safe:
            return False
    return True


def _queen_lost_in_line(board: chess.Board, line: Sequence[str], owner: chess.Color,
                        plies: int = 6) -> bool:
    """Replaying the stored line, the owner's queen comes off and does not come
    back as material: the opponent ends at least a rook's worth up on it."""
    probe = board.copy(stack=False)

    def material(color):
        return sum(_PIECE_VALUE[p.piece_type] for p in probe.piece_map().values()
                   if p.color == color)

    start = material(owner) - material(not owner)
    had_queen = bool(probe.pieces(chess.QUEEN, owner))
    for san in list(line or [])[:plies]:
        try:
            probe.push_san(str(san))
        except ValueError:
            return False
    if not had_queen or probe.pieces(chess.QUEEN, owner):
        return False
    return (material(owner) - material(not owner)) - start <= -500


def _danger(point: Mapping[str, Any], player_is_white: bool) -> Optional[Dict[str, Any]]:
    """What the punishing reply would have done, when the board proves it."""
    row = point.get("row") or {}
    owner = chess.WHITE if player_is_white else chess.BLACK
    info = row.get("mate_info") if isinstance(row.get("mate_info"), dict) else {}
    after_mate = info.get("after")
    if isinstance(after_mate, int) and after_mate != 0 and (after_mate > 0) != player_is_white:
        return {"kind": "mate_allowed", "reply": (row.get("pv_after_played") or [None])[0]}
    line = row.get("pv_after_played") or []
    if not line:
        return None
    try:
        board = chess.Board(point["fen_before"])
        board.push_uci(point["uci"])
        reply_board = board.copy(stack=False)
        reply_board.push_san(str(line[0]))
    except ValueError:
        return None
    if _queen_trapped_after(reply_board, owner):
        return {"kind": "queen_trapped", "reply": line[0]}
    if _queen_lost_in_line(board, line, owner):
        return {"kind": "queen_lost", "reply": line[0]}
    return {"kind": "chance", "reply": line[0]}


# ─── Ledger ────────────────────────────────────────────────────────────


def _tier(point: Mapping[str, Any], player_is_white: bool) -> Optional[Any]:
    before, after = point.get("eval_before"), point.get("eval_after")
    if before is None or after is None:
        return None
    mover_is_user = point["side"] == "you"
    mover_is_white = player_is_white if mover_is_user else not player_is_white
    loss = max(0, before - after) if mover_is_user else max(0, after - before)
    white_before = before if player_is_white else -before
    white_after = after if player_is_white else -after
    return classify_severity_practical(
        int(loss), mover_is_user=mover_is_user, mover_is_white=mover_is_white,
        eval_before_cp=white_before, eval_after_cp=white_after)


def _observation_for(point, observations_by_key):
    return observations_by_key.get((point.get("move_number"), point.get("san")))


def build_ledger(
    *,
    move_evaluations: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    user_color: str,
    outcome: Optional[str] = None,
    termination: Optional[str] = None,
    opening_name: Optional[str] = None,
    opening_deviation: Optional[Mapping[str, Any]] = None,
    phase_exit_move: Optional[int] = None,
) -> Dict[str, Any]:
    """The game's events, in order, each with evidence.

    `phase_exit_move` is the move where the material phase leaves "opening",
    when the caller knows it; the opening is cut at the earlier of that and
    OPENING_LAST_MOVE.
    """
    player_is_white = str(user_color or "white").lower() == "white"
    timeline = build_timeline(move_evaluations, user_color)
    obs = {(o.get("move_number"), o.get("move_san")): o for o in observations or []}
    events: List[Dict[str, Any]] = []

    for index, point in enumerate(timeline):
        practical = _tier(point, player_is_white)
        if practical is None:
            continue
        nxt = timeline[index + 1] if index + 1 < len(timeline) else None
        base = {
            "move_number": point["move_number"],
            "san": point["san"],
            "side": point["side"],
            "eval_before": point["eval_before"],
            "eval_after": point["eval_after"],
            "tier": practical.practical_tier,
            "decisive": bool(practical.decisiveness_changed),
            "fen_before": point["fen_before"],
            "uci": point["uci"],
        }
        observation = _observation_for(point, obs) if point["side"] == "you" else None

        if point["side"] == "you":
            row = point.get("row") or {}
            info = row.get("mate_info") if isinstance(row.get("mate_info"), dict) else {}
            mine = lambda v: isinstance(v, int) and v != 0 and (v > 0) == player_is_white  # noqa: E731
            if mine(info.get("before")) and not mine(info.get("after")):
                events.append({**base, "kind": "missed_mate", "happened": False,
                               "evidence": {"best": row.get("best_move")}})
                continue
            if practical.practical_tier in _EVENT_TIERS:
                punished = None
                if nxt is not None and nxt.get("eval_after") is not None:
                    drop = (point["eval_before"] or 0) - (point["eval_after"] or 0)
                    recovered = (nxt["eval_after"] or 0) - (point["eval_after"] or 0)
                    punished = not (drop > 0 and recovered >= _RECOVERED_SHARE * drop)
                events.append({
                    **base,
                    "kind": "your_mistake",
                    "happened": True,
                    "punished": punished,
                    "label": (observation or {}).get("subtype"),
                    "label_quality_id": (
                        f"gap:{observation.get('missed_pattern')}:{observation.get('subtype')}"
                        if observation and observation.get("subtype") else None),
                    "danger": _danger(point, player_is_white),
                    "evidence": {"best": row.get("best_move"),
                                 "their_reply": (nxt or {}).get("san")},
                })
                continue
            good = _good_move(observation)
            if good:
                events.append({**base, "kind": "your_good_move", "happened": True,
                               "label": good, "evidence": {}})
            continue

        # Their move.
        if practical.practical_tier in _EVENT_TIERS:
            taken = None
            if nxt is not None and nxt.get("eval_after") is not None:
                gain = (point["eval_after"] or 0) - (point["eval_before"] or 0)
                kept = (nxt["eval_after"] or 0) - (point["eval_before"] or 0)
                taken = gain > 0 and kept >= _RECOVERED_SHARE * gain
            events.append({**base, "kind": "their_mistake", "happened": True,
                           "taken": taken,
                           "your_answer": (nxt or {}).get("san"),
                           "evidence": {"their_best": point.get("best_san"),
                                        # What would have punished it: the
                                        # engine's move on the player's turn.
                                        "your_best": ((nxt or {}).get("row") or {}).get("best_move")}})

    return {
        "version": LEDGER_VERSION,
        "outcome": outcome,
        "events": events,
        "opening": _opening(timeline, opening_name, opening_deviation, phase_exit_move),
        "finish": _finish(timeline, outcome, termination),
        "curve": [p["eval_after"] for p in timeline if p.get("eval_after") is not None],
        "positions": len(timeline),
    }


def _good_move(observation: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not observation:
        return None
    if observation.get("tactical_pattern_executed"):
        return str(observation["tactical_pattern_executed"])
    for flag in ("found_best_in_critical", "punished_opponent_blunder"):
        if observation.get(flag) is True:
            return flag
    return None


def _opening(timeline, opening_name, deviation, phase_exit_move) -> Dict[str, Any]:
    last = OPENING_LAST_MOVE if phase_exit_move is None else min(OPENING_LAST_MOVE, phase_exit_move)
    mine = [p for p in timeline if p["side"] == "you" and (p.get("move_number") or 99) <= last]
    costliest = None
    all_engine = bool(mine)
    for p in mine:
        row = p.get("row") or {}
        loss = row.get("cp_loss") or 0
        if loss > 0:
            all_engine = False
        if costliest is None or loss > costliest["cp_loss"]:
            costliest = {"san": p["san"], "move_number": p["move_number"], "cp_loss": int(loss),
                         "best": row.get("best_move"), "eval_after": p["eval_after"]}
    end_eval = mine[-1]["eval_after"] if mine else None
    dev = (deviation or {}).get("deviation") or {}
    name = opening_name or dev.get("last_opening_name")
    return {
        "name": name,
        "last_move": last,
        "eval_at_end": end_eval,
        "costliest": costliest,
        "every_move_engine_best": all_engine,
        "left_book": ({"played": dev.get("played_san"), "book": dev.get("expected_san"),
                       "move_number": dev.get("user_move_number")} if dev else None),
    }


def _finish(timeline, outcome, termination) -> Dict[str, Any]:
    curve = [p["eval_after"] for p in timeline if p.get("eval_after") is not None]
    final = curve[-1] if curve else None
    # A winning position held to the end: the last stretch never dropped out
    # of clearly winning once it got there.
    kept_winning = False
    if curve and outcome == "win":
        tail_start = next((i for i in range(len(curve) - 1, -1, -1) if curve[i] < 150), -1)
        kept_winning = tail_start < len(curve) - 1 and max(curve[tail_start + 1:], default=0) >= 300
    return {"outcome": outcome, "termination": termination, "final_eval": final,
            "kept_winning": kept_winning,
            "was_winning_and_did_not_win": bool(curve) and outcome != "win" and max(curve) >= 300}
