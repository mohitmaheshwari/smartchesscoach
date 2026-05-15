"""
Shape-layer facade (TIER 3 selection logic).

`select_shape_for_position(board, eval_data, shapes_fired_this_game)`
runs the geometric detectors, applies the engine verifier, suppresses
patterns already fired in this game, sorts by priority (HIGHER first),
and returns the single highest-priority surviving pattern as a dict
ready to drop into a per-move output record:

    {
        "pattern_id":   "knight_fork",
        "pattern_name": "Knight Fork",
        "pattern_desc": "Your knight attacks two big pieces at once. They can save only one.",
        "mover":        "c7",
        "targets":      ["a8", "e8"],
        "executing_move": "c7e8",
        "evidence":     "knight jumps to e8 attacking 2 pieces",
    }

Returns None if no pattern passes verification + suppression.

Design notes:
  - Side to move on `board` is treated as 'us'; the pattern fires from
    that side's perspective. Use the pre-move board so the engine's
    best_move_uci aligns naturally with what we detect.
  - Suppression is once-per-game per pattern_id by default (matches the
    TIER 2 caption-principle convention). The caller maintains the set
    and we mutate it on fire.
  - The engine verifier is strict: patterns with executing_move only
    fire if the engine's best move (or top-3 if available) matches.
    Heuristic-only patterns pass through.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set
import chess

from services.shape_detectors import detect_all_shapes, verify_with_engine_data
from services.shape_patterns import PATTERNS_BY_ID


def _is_relevant_to_move(
    ev: Dict,
    played_move: Optional[chess.Move],
    best_move_uci: str,
) -> bool:
    """Move-relevance gate: a pattern fires only when the played move is
    actually INVOLVED in the pattern. Without this, every pattern whose
    geometry holds anywhere on the board surfaces under every move —
    producing teaching that has nothing to do with what the player did.

    Two cases:
      1. Pattern has an executing_move (e.g. a fork move, capture):
         fires if played_move matches (player executed it) OR engine's
         best move matches (player missed it — surface as a lesson).
      2. Pattern is positional (no executing_move): fires if the played
         move's from or to square overlaps mover/targets — i.e., the
         move involves a piece named in the pattern.

    Pin/Skewer exception (added 2026-05-15 after Parth flagged Bxf3):
      For pin/skewer, the played move CAPTURING the front piece
      (targets[0]) means the pattern was just cashed in as a trade,
      not exploited as a tactical setup. The geometry exists pre-move,
      but after the capture the pinned/skewered piece is gone and the
      "pin/skewer" framing misleads (the player just made a trade).
      Suppress in that case.
    """
    ex = ev.get("executing_move")
    played_uci = played_move.uci() if played_move else ""
    if ex:
        return played_uci == ex or best_move_uci == ex
    if played_move is None:
        # No move context — can't gate. Pass through (used for tests).
        return True

    # Pin/skewer execution-by-capture: suppress.
    if ev.get("pattern_id") in ("pin", "skewer"):
        targets = ev.get("targets") or []
        if targets:
            front_target = targets[0]
            if isinstance(front_target, str):
                try:
                    front_target = chess.parse_square(front_target)
                except Exception:
                    front_target = None
            if isinstance(front_target, int) and played_move.to_square == front_target:
                return False

    involved: Set[int] = set()
    if ev.get("mover"):
        try:
            mover_val = ev["mover"]
            if isinstance(mover_val, int):
                involved.add(mover_val)
            else:
                involved.add(chess.parse_square(str(mover_val)))
        except Exception:
            pass
    for t in ev.get("targets") or []:
        try:
            if isinstance(t, int):
                involved.add(t)
            else:
                involved.add(chess.parse_square(str(t)))
        except Exception:
            pass
    return played_move.from_square in involved or played_move.to_square in involved


def select_shape_for_position(
    board: chess.Board,
    eval_data: Optional[Dict] = None,
    shapes_fired_this_game: Optional[Set[str]] = None,
    prev_move: Optional[chess.Move] = None,
) -> Optional[Dict]:
    """Return the single highest-priority shape pattern this move surfaces,
    or None. `shapes_fired_this_game` is mutated on fire so duplicates don't
    repeat across the rest of the game.
    """
    if shapes_fired_this_game is None:
        shapes_fired_this_game = set()

    try:
        candidates = detect_all_shapes(board, prev_move=prev_move)
    except Exception:
        return None
    if not candidates:
        return None

    # Move-relevance gate: only surface patterns where the played move is
    # actually involved. Without this, a pin/fork/discovery on the other
    # side of the board fires under a routine developing move. The user's
    # move-4 Nf6 firing back_rank_trap and hidden_attack was exactly this.
    best_move_uci = (eval_data or {}).get("best_move_uci", "") if eval_data else ""
    candidates = [ev for ev in candidates if _is_relevant_to_move(ev, prev_move, best_move_uci)]
    if not candidates:
        return None

    # Engine verifier (best/top_3/heuristic) filtering.
    verified = verify_with_engine_data(candidates, eval_data)
    if not verified:
        return None

    # Suppress patterns already fired this game.
    verified = [ev for ev in verified if ev["pattern_id"] not in shapes_fired_this_game]
    if not verified:
        return None

    # Sort: HIGHER priority number wins (opposite of caption principles).
    def _prio(ev):
        spec = PATTERNS_BY_ID.get(ev["pattern_id"], {})
        return -spec.get("priority", 0)
    verified.sort(key=_prio)

    top = verified[0]
    spec = PATTERNS_BY_ID.get(top["pattern_id"], {})
    shapes_fired_this_game.add(top["pattern_id"])

    return {
        "pattern_id":     top["pattern_id"],
        "pattern_name":   spec.get("name", ""),
        "pattern_desc":   spec.get("description", ""),
        "mover":          top.get("mover"),
        "targets":        top.get("targets", []),
        "executing_move": top.get("executing_move"),
        "evidence":       top.get("evidence", ""),
    }


def tally_shapes_across_games(
    per_move_records_by_game: List[List[Dict]],
) -> List[Dict]:
    """Aggregate shape-pattern fires across a list of games (each game is a
    list of per-move records that already contain `shape_pattern_id`).
    Returns a list of dicts sorted by frequency:

        [{"pattern_id": "free_piece", "name": "Free Piece",
          "description": "...", "count": 7, "games": 4}, ...]

    Used by Pattern-of-the-Day on the home dashboard.
    """
    from collections import Counter
    pattern_counts = Counter()
    pattern_games = {}
    for game_records in per_move_records_by_game:
        seen_this_game = set()
        for rec in game_records:
            pid = rec.get("shape_pattern_id")
            if not pid:
                continue
            pattern_counts[pid] += 1
            seen_this_game.add(pid)
        for pid in seen_this_game:
            pattern_games[pid] = pattern_games.get(pid, 0) + 1

    out = []
    for pid, count in pattern_counts.most_common():
        spec = PATTERNS_BY_ID.get(pid, {})
        out.append({
            "pattern_id":  pid,
            "name":        spec.get("name", ""),
            "description": spec.get("description", ""),
            "count":       count,
            "games":       pattern_games.get(pid, 0),
        })
    return out
