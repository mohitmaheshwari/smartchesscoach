"""Build validated per-move research inputs without exporting raw games."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import chess
import chess.pgn

_NUMERIC_TIME_CONTROL = re.compile(r"^(\d+)(?:\+(\d+))?$")


class CorpusInputError(ValueError):
    pass


def normalized_position_key(fen: str) -> str:
    """Full legal state, excluding clocks and move number."""
    board = chess.Board(fen)
    fields = board.fen(en_passant="fen").split()
    return " ".join(fields[:4])


def numeric_time_control(value: Optional[str]) -> Optional[Tuple[str, int, int]]:
    match = _NUMERIC_TIME_CONTROL.fullmatch(str(value or "").strip())
    if not match:
        return None
    base = int(match.group(1))
    increment = int(match.group(2) or 0)
    if base <= 0:
        return None
    return f"{base}+{increment}", base, increment


@dataclass(frozen=True)
class TrajectoryEntry:
    ply: int
    fen: str
    move_uci: str
    history_moves: Tuple[str, ...]
    time_control: Optional[str]
    clock_fraction: Optional[float]


def build_user_trajectory(pgn: str, user_color: str) -> List[TrajectoryEntry]:
    """Return pre-move context for each user move in one standard game.

    `%clk` is time remaining *after* the annotated move. Therefore the clock
    available before the current user move is that user's preceding `%clk`, or
    the base time before their first move. No missing clock is filled.
    """
    game = chess.pgn.read_game(io.StringIO(pgn or ""))
    if game is None or game.errors:
        raise CorpusInputError("PGN cannot be reconstructed without errors")
    parsed_tc = numeric_time_control(game.headers.get("TimeControl"))
    time_control = parsed_tc[0] if parsed_tc else None
    base_seconds = parsed_tc[1] if parsed_tc else None
    wanted_white = str(user_color or "").lower().startswith("w")
    board = game.board()
    history: List[str] = []
    prior_clock = {chess.WHITE: base_seconds, chess.BLACK: base_seconds}
    entries: List[TrajectoryEntry] = []

    for ply, node in enumerate(game.mainline(), start=1):
        mover = board.turn
        move_uci = node.move.uci()
        if mover == wanted_white:
            remaining = prior_clock[mover]
            fraction = None
            if base_seconds and remaining is not None:
                fraction = max(0.0, min(1.0, remaining / float(base_seconds)))
            entries.append(TrajectoryEntry(
                ply=ply,
                fen=board.fen(),
                move_uci=move_uci,
                history_moves=tuple(history),
                time_control=time_control,
                clock_fraction=fraction,
            ))
        board.push(node.move)
        history.append(move_uci)
        annotated = node.clock()
        prior_clock[mover] = None if annotated is None else int(float(annotated))
    return entries


def match_observations_to_trajectory(
    observations: Sequence[Mapping[str, Any]],
    trajectory: Sequence[TrajectoryEntry],
) -> Tuple[List[Tuple[Mapping[str, Any], TrajectoryEntry]], int]:
    """Deterministically join stored observations to reconstructed user plies."""
    unused = list(trajectory)
    matched: List[Tuple[Mapping[str, Any], TrajectoryEntry]] = []
    failures = 0
    ordered = sorted(
        observations,
        key=lambda row: (int(row.get("ply") or 0), int(row.get("move_number") or 0)),
    )
    for observation in ordered:
        try:
            fen_key = normalized_position_key(str(observation.get("fen_before") or ""))
        except ValueError:
            failures += 1
            continue
        move_uci = str(observation.get("move_uci") or "").lower()
        index = next((
            i for i, entry in enumerate(unused)
            if entry.move_uci == move_uci and normalized_position_key(entry.fen) == fen_key
        ), None)
        if index is None:
            failures += 1
            continue
        matched.append((observation, unused.pop(index)))
    return matched, failures


def split_game_records(
    manifest: Mapping[str, Any], split_key: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return chronological history/evaluation records from frozen cutoffs."""
    by_user: Dict[str, List[Dict[str, Any]]] = {}
    for game in manifest.get("games", []):
        by_user.setdefault(str(game["user_id"]), []).append(dict(game))
    users = {str(user["user_id"]): user for user in manifest.get("users", [])}
    history: List[Dict[str, Any]] = []
    evaluation: List[Dict[str, Any]] = []
    for user_id in sorted(by_user):
        cutoff = users.get(user_id, {}).get("split_cutoffs", {}).get(split_key)
        if not cutoff:
            continue
        rows = sorted(by_user[user_id], key=lambda row: (row["played_date"], row["game_id"]))
        start = int(cutoff["evaluation_start_inclusive"])
        end = int(cutoff["evaluation_end_exclusive"])
        history.extend(rows[:start])
        evaluation.extend(rows[start:end])
    return history, evaluation
