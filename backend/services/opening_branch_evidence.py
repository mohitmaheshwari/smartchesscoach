"""Transposition-safe opening decision evidence from analyzed games.

The canonical curriculum remains the only theory source. This service indexes
its authored paths by normalized position and records what the player did when
that position later appeared in a real game.
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone
from typing import Dict, List, Optional

import chess
import chess.pgn

from services.opening_mastery_tracker import SOUND_ALTERNATIVE_MAX_CP
from services.opening_theory_json_service import (
    get_all_lesson_move_paths,
    get_opening_theory,
    resolve_opening_key,
)


def normalized_position_key(board_or_fen) -> str:
    board = (
        board_or_fen
        if isinstance(board_or_fen, chess.Board)
        else chess.Board(str(board_or_fen))
    )
    return " ".join(board.fen().split()[:4])


def decision_id(opening_key: str, player_color: str, position_key: str) -> str:
    identity = f"{opening_key}|{player_color}|{position_key}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def _authored_decisions(opening_key: str, player_color: str) -> Dict[str, set]:
    color = chess.WHITE if player_color == "white" else chess.BLACK
    decisions: Dict[str, set] = {}
    for path in get_all_lesson_move_paths(opening_key):
        board = chess.Board()
        for step in path:
            try:
                move = board.parse_san(str(step.get("move") or ""))
            except (ValueError, AssertionError):
                break
            if board.turn == color:
                decisions.setdefault(normalized_position_key(board), set()).add(
                    move.uci()
                )
            board.push(move)
    return decisions


def _analysis_by_position(move_evaluations: List[Dict]) -> Dict[str, List[Dict]]:
    result: Dict[str, List[Dict]] = {}
    for rec in move_evaluations or []:
        if not isinstance(rec, dict) or not rec.get("fen_before"):
            continue
        try:
            key = normalized_position_key(rec["fen_before"])
        except (ValueError, TypeError):
            continue
        result.setdefault(key, []).append(rec)
    return result


def _matching_analysis(
    candidates: List[Dict],
    move: chess.Move,
    move_san: str,
) -> Optional[Dict]:
    norm_san = str(move_san).replace("+", "").replace("#", "").casefold()
    for rec in candidates or []:
        if str(rec.get("move_uci") or "").lower() == move.uci():
            return rec
        stored_san = str(rec.get("move_san") or rec.get("move") or "")
        if stored_san.replace("+", "").replace("#", "").casefold() == norm_san:
            return rec
    return candidates[0] if len(candidates or []) == 1 else None


def build_opening_branch_events(
    opening_key: str,
    player_color: str,
    pgn: str,
    move_evaluations: List[Dict],
    game_id: str,
) -> List[Dict]:
    """Build factual decision events; return [] when evidence is incomplete."""
    resolved = resolve_opening_key(opening_key) or opening_key
    theory = get_opening_theory(resolved) or {}
    color = "black" if str(player_color).lower() == "black" else "white"
    authored = _authored_decisions(resolved, color)
    if not authored or not pgn:
        return []

    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return []
    analysis = _analysis_by_position(move_evaluations)
    player_turn = chess.BLACK if color == "black" else chess.WHITE
    authored_color = str(theory.get("color") or "white").lower()
    role = "chosen_opening" if color == authored_color else "answering_opponent"
    board = game.board()
    events = []

    for ply_index, move in enumerate(game.mainline_moves()):
        before_key = normalized_position_key(board)
        move_san = board.san(move)
        expected = authored.get(before_key)
        if board.turn == player_turn and expected:
            rec = _matching_analysis(analysis.get(before_key, []), move, move_san)
            cp_loss = rec.get("cp_loss") if rec else None
            try:
                cp_loss = max(0, int(cp_loss)) if cp_loss is not None else None
            except (TypeError, ValueError):
                cp_loss = None

            if move.uci() in expected:
                outcome = "authored_move"
            elif cp_loss is not None and cp_loss <= SOUND_ALTERNATIVE_MAX_CP:
                outcome = "sound_alternative"
            elif cp_loss is not None:
                outcome = "engine_mistake"
            else:
                outcome = "unverified_deviation"

            events.append({
                "decision_id": decision_id(resolved, color, before_key),
                "opening_key": resolved,
                "position_key": before_key,
                "player_color": color,
                "role": role,
                "game_id": game_id,
                "move_number": ply_index // 2 + 1,
                "played_move": move_san,
                "expected_moves": sorted(expected),
                "cp_loss": cp_loss,
                "outcome": outcome,
                "source": "real_game",
            })
        board.push(move)
    return events


async def record_opening_branch_evidence(
    db,
    user_id: str,
    opening_key: str,
    player_color: str,
    pgn: str,
    move_evaluations: List[Dict],
    game_id: str,
) -> Dict:
    """Persist a game's authored-decision events once."""
    events = build_opening_branch_events(
        opening_key,
        player_color,
        pgn,
        move_evaluations,
        game_id,
    )
    if not events:
        return {"recorded": False, "events": 0}

    update = {
        "$addToSet": {"_branch_evaluated_games": game_id},
        "$inc": {},
        "$set": {},
        "$push": {},
    }
    now = datetime.now(timezone.utc).isoformat()
    for event in events:
        base = f"branch_evidence.{event['decision_id']}"
        encounters_key = f"{base}.encounters"
        update["$inc"][encounters_key] = (
            update["$inc"].get(encounters_key, 0) + 1
        )
        outcome_counter = {
            "authored_move": "authored_moves",
            "sound_alternative": "sound_alternatives",
            "engine_mistake": "engine_mistakes",
            "unverified_deviation": "unverified_deviations",
        }[event["outcome"]]
        outcome_key = f"{base}.{outcome_counter}"
        update["$inc"][outcome_key] = (
            update["$inc"].get(outcome_key, 0) + 1
        )
        if event["outcome"] in {"authored_move", "sound_alternative"}:
            success_key = f"{base}.independent_successes"
            update["$inc"][success_key] = (
                update["$inc"].get(success_key, 0) + 1
            )
        update["$set"].update({
            f"{base}.decision_id": event["decision_id"],
            f"{base}.position_key": event["position_key"],
            f"{base}.player_color": event["player_color"],
            f"{base}.role": event["role"],
            f"{base}.last_outcome": event["outcome"],
            f"{base}.last_encountered": now,
            f"{base}.last_game_id": game_id,
        })
        recent = update["$push"].setdefault(
            f"{base}.recent_outcomes",
            {"$each": [], "$slice": -5},
        )
        recent["$each"].append({
                "game_id": game_id,
                "outcome": event["outcome"],
                "played_move": event["played_move"],
                "cp_loss": event["cp_loss"],
                "recorded_at": now,
        })

    result = await db.user_opening_mastery.update_one(
        {
            "user_id": user_id,
            "opening_key": opening_key,
            "_branch_evaluated_games": {"$ne": game_id},
        },
        update,
    )
    return {
        "recorded": bool(result.modified_count),
        "events": len(events) if result.modified_count else 0,
    }
