#!/usr/bin/env python3
"""Export the frozen, blinded whole-game teaching-review evidence packet.

The production mode is read-only. It uses the Mongo credentials already
present in the backend container, prints base64 JSON, runs no engine or model,
and emits no source identity. Development and holdout membership are fixed by
the data lock dated 2026-09-13. Holdout content cannot be opened until a
separate implementation-freeze marker passes validation.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, Iterable, Mapping, Sequence

from pymongo import MongoClient

from scripts.export_full_game_chess_fact_audit import (
    EMAIL_RE,
    URL_RE,
    content_key,
    replay,
)


SCHEMA_VERSION = "whole_game_teaching_review_evidence.v1"
SELECTION_VERSION = "whole_game_teaching_review_selection.v1"
CUTOFF = datetime(2026, 9, 13, 8, 26, 28, tzinfo=timezone.utc)
RATING_BANDS = {
    "600-799": (600, 799),
    "800-999": (800, 999),
    "1000-1199": (1000, 1199),
    "1200-1399": (1200, 1399),
    "1400-1500": (1400, 1500),
}
DEVELOPMENT_QUOTAS = {
    "600-799": 19,
    "800-999": 11,
    "1000-1199": 30,
    "1200-1399": 31,
    "1400-1500": 9,
}
EXPECTED_CORPUS_SHA256 = (
    "1a302e7a618303cd2cb1895f9fd20ae079ba77921f402a21c1b4be45d4c0219f"
)
EXPECTED_DEVELOPMENT_SHA256 = (
    "91f8aacdb0d121fce9258509c84cc2b4bd1a840c3d63224a182ed9e875044496"
)
EXPECTED_HOLDOUT_SHA256 = (
    "87daa7089e35060cfaeb0164c9a0e741ad799634b74b94878f2f11dc5250020b"
)
FROZEN_DEVELOPMENT_ADJUDICATION_SHA256 = (
    "985c155d96bf9a74a95fd4d115cf51197763046bc894a1b3895a909ff57e34f2"
)
TEACHING_INTELLIGENCE_CYCLE = "deterministic-teaching-intelligence-v1"
TEACHING_INTELLIGENCE_SCHEMA_VERSION = (
    "deterministic_teaching_intelligence_evidence.v1"
)
TEACHING_INTELLIGENCE_SELECTION_VERSION = (
    "deterministic_teaching_intelligence_selection.v1"
)
TEACHING_INTELLIGENCE_CUTOFF = datetime(
    2026, 9, 13, 17, 26, 42, tzinfo=timezone.utc
)
TEACHING_INTELLIGENCE_MIN_PLAYER_GAMES = 8
TEACHING_INTELLIGENCE_PLAYER_CAP = 3
TEACHING_INTELLIGENCE_DEVELOPMENT_QUOTAS = dict(DEVELOPMENT_QUOTAS)
TEACHING_INTELLIGENCE_HOLDOUT_TAG = (
    "deterministic-teaching-intelligence-holdout-v1"
)
TEACHING_INTELLIGENCE_DEVELOPMENT_TAG = (
    "deterministic-teaching-intelligence-development-v1"
)
TEACHING_INTELLIGENCE_EXPECTED_CORPUS_SHA256 = (
    "9335599bf28d0926ce6b66f85c5b7ecee6d7d937c272eae56cb5fbcd4bb08a7f"
)
TEACHING_INTELLIGENCE_EXPECTED_DEVELOPMENT_SHA256 = (
    "e987cde54eb7df59aebf94ce710fef6991fcbb55787f5e2671956a286801a280"
)
TEACHING_INTELLIGENCE_EXPECTED_HOLDOUT_SHA256 = (
    "661fba3496d406205e4205db3a4122a05ddd1fe63ca78aa3755b9e819cb7063f"
)
TEACHING_INTELLIGENCE_FROZEN_REVIEW_SHA256 = (
    "ae933d3445ab4a4057ea6bb5b9ecad780b191ab4fa7eccb5787a0d051af504b6"
)
FORBIDDEN_KEYS = frozenset(
    {
        "_id",
        "user_id",
        "game_id",
        "email",
        "username",
        "chess_com_username",
        "chesscom_username",
        "lichess_username",
        "profile_id",
        "date_played",
        "imported_at",
        "analyzed_at",
        "created_at",
        "url",
        "source_url",
        "white",
        "black",
        "white_player",
        "black_player",
        "pgn",
        "caption",
        "narrative",
        "cognitive_gap",
        "detector_id",
        "quality_id",
        "selected_event_ids",
        "game_teaching_plan",
        "teachable_event",
        "reflection_prompt",
    }
)
SENSITIVE_VALUE_KEYS = (
    "game_id",
    "user_id",
    "email",
    "username",
    "chess_com_username",
    "chesscom_username",
    "lichess_username",
    "white",
    "black",
    "white_player",
    "black_player",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
COMPARISON_FORBIDDEN_KEYS = frozenset({
    "_id",
    "game_id",
    "user_id",
    "email",
    "username",
    "chess_com_username",
    "chesscom_username",
    "lichess_username",
    "profile_id",
    "date_played",
    "imported_at",
    "analyzed_at",
    "created_at",
    "url",
    "source_url",
    "white",
    "black",
    "white_player",
    "black_player",
    "pgn",
})


def _sha_members(values: Iterable[str]) -> str:
    """Canonical frozen membership digest."""
    return hashlib.sha256(
        "|".join(sorted(str(value) for value in values)).encode("utf-8")
    ).hexdigest()


def _rank(tag: str, value: str) -> str:
    return hashlib.sha256((tag + "|" + str(value)).encode("utf-8")).hexdigest()


def _rating_band(value: Any) -> str | None:
    try:
        rating = int(value)
    except (TypeError, ValueError):
        return None
    for name, (low, high) in RATING_BANDS.items():
        if low <= rating <= high:
            return name
    return None


def _phase_combination(rows: Sequence[Mapping[str, Any]]) -> str:
    phases = {
        str(row.get("phase") or "").strip().lower()
        for row in rows
        if isinstance(row, Mapping)
    }
    if phases == {"opening"}:
        return "opening_only"
    if phases == {"opening", "middlegame"}:
        return "opening_and_middlegame"
    if phases == {"opening", "endgame"}:
        return "opening_and_endgame"
    if phases == {"opening", "middlegame", "endgame"}:
        return "opening_middlegame_endgame"
    return "invalid"


def _eligible(game: Mapping[str, Any], analysis: Mapping[str, Any]) -> bool:
    rows = analysis.get("decryption_v5_data")
    return bool(
        _rating_band(game.get("user_rating"))
        and str(game.get("pgn") or "").strip()
        and isinstance(rows, list)
        and len(rows) >= 8
        and all(
            isinstance(row, Mapping)
            and str(row.get("move_san") or "").strip()
            and str(row.get("fen_before") or "").strip()
            and str(row.get("phase") or "").strip().lower()
            in {"opening", "middlegame", "endgame"}
            for row in rows
        )
    )


def load_eligible(
    db,
    *,
    cutoff: datetime = CUTOFF,
) -> list[Dict[str, Any]]:
    games = {
        row["game_id"]: row
        for row in db.games.find(
            {
                "pgn": {"$type": "string", "$ne": ""},
                "user_rating": {"$gte": 600, "$lte": 1500},
            },
            {
                "_id": 0,
                "game_id": 1,
                "user_id": 1,
                "user_rating": 1,
                "user_color": 1,
                "result": 1,
                "opening": 1,
                "pgn": 1,
                "time_control_category": 1,
                "platform": 1,
                **{key: 1 for key in SENSITIVE_VALUE_KEYS},
            },
        )
        if row.get("game_id")
    }
    # Preserve the natural scan order used by the frozen census. Applying an
    # analyzed_at predicate in Mongo can select a different index and change
    # max-flow edge order even when it returns the same membership.
    query = {
        "decryption_v5_data": {"$exists": True, "$ne": []},
    }
    projection = {
        "_id": 0,
        "game_id": 1,
        "user_id": 1,
        "analyzed_at": 1,
        "decryption_v5_version": 1,
        "decryption_v5_data.move_san": 1,
        "decryption_v5_data.fen_before": 1,
        "decryption_v5_data.phase": 1,
    }
    eligible = []
    for analysis in db.game_analyses.find(query, projection):
        analyzed_at = analysis.get("analyzed_at")
        if not isinstance(analyzed_at, datetime):
            continue
        if analyzed_at.tzinfo is None:
            analyzed_at = analyzed_at.replace(tzinfo=timezone.utc)
        if analyzed_at > cutoff:
            continue
        game = games.get(analysis.get("game_id"))
        if not game or not _eligible(game, analysis):
            continue
        eligible.append(
            {
                "source_game_id": str(analysis["game_id"]),
                "source_player_id": str(
                    analysis.get("user_id") or game.get("user_id") or ""
                ),
                "band": _rating_band(game.get("user_rating")),
                "phase_combination": _phase_combination(
                    analysis["decryption_v5_data"]
                ),
                "game": game,
            }
        )
    if any(
        not row["source_player_id"]
        or row["phase_combination"] == "invalid"
        for row in eligible
    ):
        raise ValueError("eligible corpus contains incomplete identity or phase")
    return eligible


class _Edge:
    def __init__(self, target: str, reverse: int, capacity: int):
        self.target = target
        self.reverse = reverse
        self.capacity = capacity


def _add_edge(
    graph: Dict[str, list[_Edge]],
    source: str,
    target: str,
    capacity: int,
) -> None:
    graph[source].append(_Edge(target, len(graph[target]), capacity))
    graph[target].append(_Edge(source, len(graph[source]) - 1, 0))


def _max_flow_allocations(
    cells: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    *,
    quotas: Mapping[str, int] = DEVELOPMENT_QUOTAS,
    player_cap: int = 3,
) -> Dict[tuple[str, str], int]:
    """Reproduce the max-flow allocation frozen by the 2026-09-13 census."""
    source = "source"
    sink = "sink"
    players = sorted({player for player, _ in cells})
    user_nodes = {
        player: "user:" + str(index)
        for index, player in enumerate(players)
    }
    band_nodes = {
        band: "band:" + band for band in quotas
    }
    graph: Dict[str, list[_Edge]] = {
        source: [],
        sink: [],
        **{node: [] for node in user_nodes.values()},
        **{node: [] for node in band_nodes.values()},
    }
    for player in players:
        _add_edge(graph, source, user_nodes[player], player_cap)
    # Iteration order is intentional: cells preserve the frozen source scan.
    for (player, band), rows in cells.items():
        _add_edge(
            graph,
            user_nodes[player],
            band_nodes[band],
            len(rows),
        )
    for band, demand in quotas.items():
        _add_edge(graph, band_nodes[band], sink, demand)

    total = 0
    while True:
        parent: Dict[str, tuple[str, int] | None] = {source: None}
        queue = [source]
        for node in queue:
            for index, edge in enumerate(graph[node]):
                if edge.capacity and edge.target not in parent:
                    parent[edge.target] = (node, index)
                    queue.append(edge.target)
        if sink not in parent:
            break
        increment = 10**9
        node = sink
        while node != source:
            previous, index = parent[node]
            increment = min(increment, graph[previous][index].capacity)
            node = previous
        node = sink
        while node != source:
            previous, index = parent[node]
            edge = graph[previous][index]
            edge.capacity -= increment
            graph[node][edge.reverse].capacity += increment
            node = previous
        total += increment
    if total != sum(quotas.values()):
        raise ValueError(f"development max-flow shortfall: {total}")

    allocations = {}
    for (player, band), _rows in cells.items():
        reverse_capacity = next(
            (
                edge.capacity
                for edge in graph[band_nodes[band]]
                if edge.target == user_nodes[player]
            ),
            0,
        )
        if reverse_capacity:
            allocations[(player, band)] = reverse_capacity
    return allocations


def select_memberships(
    eligible: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    by_player: Dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in eligible:
        by_player[row["source_player_id"]].append(row)
    holdout = [
        min(
            rows,
            key=lambda row: _rank(
                "whole-game-holdout-v1", row["source_game_id"]
            ),
        )
        for _, rows in sorted(by_player.items())
    ]
    holdout_ids = {row["source_game_id"] for row in holdout}
    cells: Dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in eligible:
        if row["source_game_id"] not in holdout_ids:
            cells[(row["source_player_id"], row["band"])].append(row)
    for rows in cells.values():
        rows.sort(
            key=lambda row: _rank(
                "whole-game-development-v1", row["source_game_id"]
            )
        )
    allocations = _max_flow_allocations(cells)
    development = []
    for cell, rows in cells.items():
        development.extend(rows[: allocations.get(cell, 0)])
    return development, holdout


def select_teaching_intelligence_memberships(
    eligible: Sequence[Mapping[str, Any]],
    *,
    prior_development: Sequence[Mapping[str, Any]],
    prior_holdout: Sequence[Mapping[str, Any]],
) -> tuple[
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
]:
    """Select the fresh, identity-hidden evidence cycle from stored games.

    Players need eight eligible games because the previous cycle consumed at
    most four, the fresh holdout reserves one, and the development cap is
    three. This makes corpus capacity a property of the selection rather than
    an optimistic operator assumption.
    """
    by_player: Dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in eligible:
        by_player[row["source_player_id"]].append(row)
    qualified_players = {
        player
        for player, rows in by_player.items()
        if len(rows) >= TEACHING_INTELLIGENCE_MIN_PLAYER_GAMES
    }
    qualified = [
        row
        for row in eligible
        if row["source_player_id"] in qualified_players
    ]
    consumed_ids = {
        row["source_game_id"]
        for row in (*prior_development, *prior_holdout)
    }
    fresh_by_player: Dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in qualified:
        if row["source_game_id"] not in consumed_ids:
            fresh_by_player[row["source_player_id"]].append(row)
    if set(fresh_by_player) != qualified_players:
        raise ValueError("a qualified player has no fresh holdout candidate")

    holdout = [
        min(
            rows,
            key=lambda row: _rank(
                TEACHING_INTELLIGENCE_HOLDOUT_TAG,
                row["source_game_id"],
            ),
        )
        for _, rows in sorted(fresh_by_player.items())
    ]
    holdout_ids = {row["source_game_id"] for row in holdout}

    cells: Dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in qualified:
        if (
            row["source_game_id"] not in consumed_ids
            and row["source_game_id"] not in holdout_ids
        ):
            cells[(row["source_player_id"], row["band"])].append(row)
    for rows in cells.values():
        rows.sort(
            key=lambda row: _rank(
                TEACHING_INTELLIGENCE_DEVELOPMENT_TAG,
                row["source_game_id"],
            )
        )
    allocations = _max_flow_allocations(
        cells,
        quotas=TEACHING_INTELLIGENCE_DEVELOPMENT_QUOTAS,
        player_cap=TEACHING_INTELLIGENCE_PLAYER_CAP,
    )
    development = []
    for cell, rows in cells.items():
        development.extend(rows[: allocations.get(cell, 0)])
    return development, holdout, qualified


def selection_summary(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    player_counts = Counter(row["source_player_id"] for row in rows)
    return {
        "games": len(rows),
        "players": len(player_counts),
        "maximum_games_from_one_player": max(player_counts.values(), default=0),
        "membership_sha256": _sha_members(
            row["source_game_id"] for row in rows
        ),
        "rating_band": dict(sorted(Counter(row["band"] for row in rows).items())),
        "phase_combination": dict(
            sorted(Counter(row["phase_combination"] for row in rows).items())
        ),
        "color": dict(
            sorted(
                Counter(
                    str(row["game"].get("user_color") or "unknown").lower()
                    for row in rows
                ).items()
            )
        ),
        "platform": dict(
            sorted(
                Counter(
                    str(row["game"].get("platform") or "unknown").lower()
                    for row in rows
                ).items()
            )
        ),
        "time_control": dict(
            sorted(
                Counter(
                    str(
                        row["game"].get("time_control_category") or "unknown"
                    ).lower()
                    for row in rows
                ).items()
            )
        ),
    }


def packet_selection_summary(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Return the same census without raw player-field-shaped color keys."""
    summary = selection_summary(rows)
    color_counts = summary.pop("color")
    summary["player_color"] = [
        {"value": color, "games": count}
        for color, count in sorted(color_counts.items())
    ]
    return summary


def _normalize_line(item: Mapping[str, Any], key: str) -> list[str]:
    value = item.get(key) or []
    return [str(token) for token in value[:8] if token]


def _engine_row(
    item: Mapping[str, Any],
    matched_ply: int,
    *,
    user_color: str,
) -> Dict[str, Any]:
    side = str(item.get("is_white") or "").lower()
    if side not in {"true", "false"}:
        from chess import Board, WHITE

        actor_color = "white" if Board(item["fen_before"]).turn == WHITE else "black"
    else:
        actor_color = "white" if item.get("is_white") else "black"
    return {
        "ply": matched_ply,
        "actor": "player" if actor_color == user_color else "opponent",
        "fen_before": item.get("fen_before"),
        "played_san": item.get("move"),
        "played_uci": item.get("move_uci"),
        "best_move_san": item.get("best_move"),
        "best_move_uci": item.get("best_move_uci"),
        "eval_before": item.get("eval_before"),
        "eval_after": item.get("eval_after"),
        "cp_loss": int(item.get("cp_loss") or 0),
        "is_critical": bool(item.get("is_critical")),
        "pv_after_played": _normalize_line(item, "pv_after_played"),
        "pv_after_best": _normalize_line(item, "pv_after_best"),
        "mate_info": item.get("mate_info"),
        "threat": item.get("threat"),
        "engine_depth": item.get("depth"),
    }


def _collect_sensitive(row: Mapping[str, Any], analysis: Mapping[str, Any]) -> set[str]:
    values = set()
    for source in (row["game"], analysis):
        for key in SENSITIVE_VALUE_KEYS:
            value = source.get(key)
            if value is not None and len(str(value)) >= 3:
                values.add(str(value))
    values.add(row["source_game_id"])
    values.add(row["source_player_id"])
    return values


def _text_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _system_baseline(analysis: Mapping[str, Any]) -> Dict[str, Any]:
    """Project stored ChessGuru output after independent gold is frozen."""
    rows = []
    event_ply = {}
    for index, item in enumerate(analysis.get("decryption_v5_data") or [], 1):
        event = item.get("teachable_event")
        event_out = None
        if isinstance(event, Mapping):
            move = event.get("move") if isinstance(event.get("move"), Mapping) else {}
            evidence = (
                event.get("evidence")
                if isinstance(event.get("evidence"), Mapping)
                else {}
            )
            teaching = (
                event.get("teaching")
                if isinstance(event.get("teaching"), Mapping)
                else {}
            )
            display = (
                event.get("display")
                if isinstance(event.get("display"), Mapping)
                else {}
            )
            event_out = {
                "outcome": event.get("outcome"),
                "move": {
                    "ply": move.get("ply"),
                    "san": move.get("san"),
                    "actor": move.get("actor"),
                },
                "concept": dict(event.get("concept") or {}),
                "evidence": {
                    "quality_id": evidence.get("quality_id"),
                    "grade": evidence.get("grade"),
                    "source_version": evidence.get("source_version"),
                    "final_verified": evidence.get("final_verified"),
                    "authorized_surfaces": dict(
                        evidence.get("authorized_surfaces") or {}
                    ),
                },
                "teaching": {
                    "caption": teaching.get("caption"),
                    "principle": teaching.get("principle"),
                    "headline": teaching.get("headline"),
                    "practical_lead": teaching.get("practical_lead"),
                },
                "display": {
                    "requested_surface": display.get("requested_surface"),
                    "authorized": display.get("authorized"),
                },
                "cause": dict(event.get("cause") or {}),
                "practical": dict(event.get("practical") or {}),
            }
            event_id = _text_or_none(event.get("event_id"))
            if event_id:
                event_ply[event_id] = move.get("ply") or index
        rows.append({
            "ply": index,
            "phase": item.get("phase"),
            "actor": "player" if item.get("is_user_move") else "opponent",
            "played_san": item.get("move_san"),
            "best_move_san": item.get("best_move_san"),
            "cp_loss": item.get("cp_loss"),
            "caption": item.get("caption"),
            "caption_explanation": _text_or_none(
                item.get("caption_explanation")
            ),
            "principle_cue": item.get("principle_cue"),
            "rule_name": item.get("rule_name"),
            "shape_pattern_id": item.get("shape_pattern_id"),
            "shape_pattern_name": item.get("shape_pattern_name"),
            "caption_facts_primary_reason": item.get(
                "caption_facts_primary_reason"
            ),
            "teachable_event": event_out,
        })

    envelope = analysis.get("game_teaching_plan")
    plan_out = None
    if isinstance(envelope, Mapping):
        plan = envelope.get("plan")
        if isinstance(plan, Mapping):
            plan_out = {
                "formula_id": envelope.get("formula_id"),
                "source_v5_version": envelope.get("source_v5_version"),
                "opening": plan.get("opening"),
                "game_arc": plan.get("game_arc"),
                "takeaway": plan.get("takeaway"),
                "chapters": [
                    {
                        "ply": event_ply.get(str(chapter.get("event_id") or "")),
                        "role": chapter.get("role"),
                        "content_ref": chapter.get("content_ref"),
                        "canonical_source": chapter.get("canonical_source"),
                    }
                    for chapter in plan.get("chapters") or []
                    if isinstance(chapter, Mapping)
                ],
            }
    return {
        "source_v5_version": analysis.get("decryption_v5_version"),
        "moves": rows,
        "stored_plan": plan_out,
    }


def export_game(
    row: Mapping[str, Any],
    analysis: Mapping[str, Any],
    *,
    include_system: bool = False,
) -> tuple[Dict[str, Any], set[str]]:
    stockfish = analysis.get("stockfish_analysis") or {}
    player_evaluations = list(stockfish.get("move_evaluations") or [])
    opponent_evaluations = list(
        stockfish.get("opponent_move_evaluations") or []
    )
    initial_fen, moves, player_plies = replay(
        row["game"].get("pgn"), player_evaluations
    )
    _opponent_initial_fen, _opponent_moves, opponent_plies = replay(
        row["game"].get("pgn"), opponent_evaluations
    )
    if len(player_plies) != len(player_evaluations):
        raise ValueError("stored player evidence did not align to legal replay")
    if len(opponent_plies) != len(opponent_evaluations):
        raise ValueError("stored opponent evidence did not align to legal replay")
    user_color = str(row["game"].get("user_color") or "").lower()
    if user_color not in {"white", "black"}:
        raise ValueError("invalid player color")
    phase_by_key = {
        (
            str(item.get("fen_before") or ""),
            str(item.get("move_san") or ""),
        ): str(item.get("phase") or "").lower()
        for item in analysis.get("decryption_v5_data") or []
    }
    full_moves = []
    for move in moves:
        full_moves.append(
            {
                "ply": move["ply"],
                "actor": (
                    "player"
                    if move["actor"] == user_color
                    else "opponent"
                ),
                "san": move["san"],
                "uci": move["uci"],
            }
        )
    evidence = [
        _engine_row(
            item,
            player_plies[index],
            user_color=user_color,
        )
        for index, item in enumerate(player_evaluations)
    ]
    evidence.extend(
        _engine_row(
            item,
            opponent_plies[index],
            user_color=user_color,
        )
        for index, item in enumerate(opponent_evaluations)
    )
    evidence.sort(key=lambda item: (item["ply"], item["actor"]))
    packet_game = {
        "anonymous_game_key": _rank(
            "whole-game-public-game-v1", row["source_game_id"]
        ),
        "anonymous_player_key": _rank(
            "whole-game-public-player-v1", row["source_player_id"]
        ),
        "rating_band": row["band"],
        "user_color": user_color,
        "result": row["game"].get("result"),
        "opening_identity": row["game"].get("opening"),
        "time_control_category": (
            row["game"].get("time_control_category") or "unknown"
        ),
        "initial_fen": initial_fen,
        "moves": full_moves,
        "stored_phase_rows": [
            {
                "move_san": item.get("move_san"),
                "fen_before": item.get("fen_before"),
                "phase": item.get("phase"),
            }
            for item in analysis.get("decryption_v5_data") or []
        ],
        "stored_engine_evidence": evidence,
        "legal_trace_sha256": content_key(initial_fen, moves),
        "source_v5_version": analysis.get("decryption_v5_version"),
    }
    if include_system:
        packet_game["system_baseline"] = _system_baseline(analysis)
    return packet_game, _collect_sensitive(row, analysis)


def assert_private(packet: Mapping[str, Any], sensitive_values: Iterable[str]) -> str:
    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if str(key).lower() in FORBIDDEN_KEYS:
                    raise ValueError(f"forbidden output key: {key}")
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(packet)
    text = json.dumps(packet, ensure_ascii=True, sort_keys=True)
    if EMAIL_RE.search(text) or URL_RE.search(text):
        raise ValueError("email or URL pattern in output")
    lowered = text.lower()
    for sensitive in sensitive_values:
        token = str(sensitive)
        if len(token) >= 6 and token.lower() in lowered:
            raise ValueError("source identity survived anonymization")
    return text


def assert_comparison_private(
    packet: Mapping[str, Any],
    sensitive_values: Iterable[str],
) -> str:
    """Permit frozen captions and labels while still rejecting identity."""
    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if str(key).lower() in COMPARISON_FORBIDDEN_KEYS:
                    raise ValueError(f"forbidden comparison output key: {key}")
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(packet)
    text = json.dumps(packet, ensure_ascii=True, sort_keys=True)
    if EMAIL_RE.search(text) or URL_RE.search(text):
        raise ValueError("email or URL pattern in comparison output")
    lowered = text.lower()
    for sensitive in sensitive_values:
        token = str(sensitive)
        if len(token) >= 6 and token.lower() in lowered:
            raise ValueError("source identity survived comparison anonymization")
    return text


def validate_freeze_marker(path: Path) -> Mapping[str, Any]:
    marker = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version": "whole_game_review_implementation_freeze.v1",
        "implementation_frozen": True,
        "holdout_open_authorized": True,
    }
    if any(marker.get(key) != value for key, value in required.items()):
        raise ValueError("holdout freeze marker is incomplete")
    if not _SHA256_RE.fullmatch(
        str(marker.get("development_adjudication_sha256") or "")
    ):
        raise ValueError("freeze marker lacks development adjudication SHA")
    if not _GIT_COMMIT_RE.fullmatch(str(marker.get("source_commit") or "")):
        raise ValueError("freeze marker lacks a full source commit")
    return marker


def _assert_memberships(
    eligible: Sequence[Mapping[str, Any]],
    development: Sequence[Mapping[str, Any]],
    holdout: Sequence[Mapping[str, Any]],
) -> None:
    checks = {
        "corpus": (_sha_members(r["source_game_id"] for r in eligible), EXPECTED_CORPUS_SHA256),
        "development": (_sha_members(r["source_game_id"] for r in development), EXPECTED_DEVELOPMENT_SHA256),
        "holdout": (_sha_members(r["source_game_id"] for r in holdout), EXPECTED_HOLDOUT_SHA256),
    }
    failures = {
        name: actual for name, (actual, expected) in checks.items()
        if actual != expected
    }
    if failures:
        raise ValueError(
            "frozen membership mismatch: " + json.dumps(failures, sort_keys=True)
        )
    if {r["source_game_id"] for r in development} & {
        r["source_game_id"] for r in holdout
    }:
        raise ValueError("development/holdout overlap")
    if Counter(r["band"] for r in development) != Counter(DEVELOPMENT_QUOTAS):
        raise ValueError("development rating quotas changed")


def load_cycle_memberships(
    db,
    *,
    cycle: str,
) -> tuple[
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    Dict[str, Any],
]:
    """Load one frozen selection cycle without exposing source identity."""
    if cycle == "whole-game-v1":
        eligible = load_eligible(db)
        development, holdout = select_memberships(eligible)
        _assert_memberships(eligible, development, holdout)
        return eligible, development, holdout, {
            "previously_consumed": 0,
            "previous_overlap": 0,
        }
    if cycle != TEACHING_INTELLIGENCE_CYCLE:
        raise ValueError(f"unknown evidence cycle: {cycle}")

    prior_eligible = load_eligible(db, cutoff=CUTOFF)
    prior_development, prior_holdout = select_memberships(prior_eligible)
    _assert_memberships(prior_eligible, prior_development, prior_holdout)
    eligible = load_eligible(db, cutoff=TEACHING_INTELLIGENCE_CUTOFF)
    development, holdout, qualified = select_teaching_intelligence_memberships(
        eligible,
        prior_development=prior_development,
        prior_holdout=prior_holdout,
    )
    consumed_ids = {
        row["source_game_id"]
        for row in (*prior_development, *prior_holdout)
    }
    selected_ids = {
        row["source_game_id"] for row in (*development, *holdout)
    }
    return qualified, development, holdout, {
        "eligible_before_player_floor": len(eligible),
        "eligible_players_before_player_floor": len({
            row["source_player_id"] for row in eligible
        }),
        "previously_consumed": len(consumed_ids),
        "previous_overlap": len(consumed_ids & selected_ids),
    }


def _assert_teaching_intelligence_memberships(
    qualified: Sequence[Mapping[str, Any]],
    development: Sequence[Mapping[str, Any]],
    holdout: Sequence[Mapping[str, Any]],
    *,
    metadata: Mapping[str, Any],
) -> None:
    expected = {
        "corpus": TEACHING_INTELLIGENCE_EXPECTED_CORPUS_SHA256,
        "development": TEACHING_INTELLIGENCE_EXPECTED_DEVELOPMENT_SHA256,
        "holdout": TEACHING_INTELLIGENCE_EXPECTED_HOLDOUT_SHA256,
    }
    if any(not _SHA256_RE.fullmatch(value) for value in expected.values()):
        raise ValueError(
            "teaching-intelligence membership is not pinned; run "
            "--fingerprint-only, review the aggregate, then freeze digests"
        )
    actual = {
        "corpus": _sha_members(row["source_game_id"] for row in qualified),
        "development": _sha_members(
            row["source_game_id"] for row in development
        ),
        "holdout": _sha_members(row["source_game_id"] for row in holdout),
    }
    failures = {
        name: value
        for name, value in actual.items()
        if value != expected[name]
    }
    if failures:
        raise ValueError(
            "teaching-intelligence membership mismatch: "
            + json.dumps(failures, sort_keys=True)
        )
    if len(holdout) != 34 or len({
        row["source_player_id"] for row in holdout
    }) != 34:
        raise ValueError("fresh holdout must contain one game from 34 players")
    if len(development) != sum(
        TEACHING_INTELLIGENCE_DEVELOPMENT_QUOTAS.values()
    ):
        raise ValueError("fresh development size changed")
    if Counter(row["band"] for row in development) != Counter(
        TEACHING_INTELLIGENCE_DEVELOPMENT_QUOTAS
    ):
        raise ValueError("fresh development rating quotas changed")
    per_player = Counter(row["source_player_id"] for row in development)
    if max(per_player.values(), default=0) > TEACHING_INTELLIGENCE_PLAYER_CAP:
        raise ValueError("fresh development player cap exceeded")
    development_ids = {row["source_game_id"] for row in development}
    holdout_ids = {row["source_game_id"] for row in holdout}
    if development_ids & holdout_ids:
        raise ValueError("fresh development/holdout overlap")
    if int(metadata.get("previous_overlap") or 0):
        raise ValueError("fresh cycle overlaps previously consumed evidence")


def build_packet(
    db,
    *,
    sample: str,
    cycle: str = "whole-game-v1",
    freeze_marker: Path | None = None,
    include_system: bool = False,
    adjudication_sha256: str | None = None,
) -> Dict[str, Any]:
    eligible, development, holdout, cycle_metadata = load_cycle_memberships(
        db,
        cycle=cycle,
    )
    if cycle == TEACHING_INTELLIGENCE_CYCLE:
        _assert_teaching_intelligence_memberships(
            eligible,
            development,
            holdout,
            metadata=cycle_metadata,
        )
    if sample == "holdout":
        if cycle == TEACHING_INTELLIGENCE_CYCLE:
            raise ValueError(
                "teaching-intelligence holdout is sealed until a new "
                "implementation-freeze contract is committed"
            )
        if include_system:
            raise ValueError("holdout cannot include system output")
        if freeze_marker is None:
            raise ValueError("holdout requires --freeze-marker")
        validate_freeze_marker(freeze_marker)
        selected = holdout
    elif sample == "development":
        selected = development
    else:
        raise ValueError("sample must be development or holdout")
    if include_system:
        validate_system_comparison_gate(
            cycle=cycle,
            adjudication_sha256=adjudication_sha256,
        )
    selected_ids = [row["source_game_id"] for row in selected]
    projection = {
        "_id": 0,
        "game_id": 1,
        "user_id": 1,
        "decryption_v5_version": 1,
        "decryption_v5_data": 1,
        "stockfish_analysis.move_evaluations": 1,
        "stockfish_analysis.opponent_move_evaluations": 1,
        "game_teaching_plan": 1,
    }
    analyses = {
        str(item["game_id"]): item
        for item in db.game_analyses.find(
            {"game_id": {"$in": selected_ids}},
            projection,
        )
    }
    games_out = []
    sensitive = set()
    for row in sorted(selected, key=lambda item: item["source_game_id"]):
        analysis = analyses.get(row["source_game_id"])
        if not analysis:
            raise ValueError("selected analysis disappeared")
        game_out, game_sensitive = export_game(
            row,
            analysis,
            include_system=include_system,
        )
        if include_system:
            game_out["system_baseline"] = _system_baseline(analysis)
        games_out.append(game_out)
        sensitive.update(game_sensitive)
    packet = {
        "schema_version": (
            TEACHING_INTELLIGENCE_SCHEMA_VERSION
            if cycle == TEACHING_INTELLIGENCE_CYCLE
            else SCHEMA_VERSION
        ),
        "selection_version": (
            TEACHING_INTELLIGENCE_SELECTION_VERSION
            if cycle == TEACHING_INTELLIGENCE_CYCLE
            else SELECTION_VERSION
        ),
        "sample": sample,
        "analysis_cutoff_utc": (
            TEACHING_INTELLIGENCE_CUTOFF
            if cycle == TEACHING_INTELLIGENCE_CYCLE
            else CUTOFF
        ).isoformat(),
        "membership_sha256": _sha_members(selected_ids),
        "source": "read-only production export of stored analysis",
        "read_only": True,
        "database_writes": 0,
        "stockfish_runs": 0,
        "model_calls": 0,
        "blinded": not include_system,
        "hidden_from_reviewer": [
            "ChessGuru captions",
            "selected teaching events",
            "detector and quality labels",
            "reflection answer keys",
            "planner ranks",
        ],
        "privacy": (
            "No source IDs, names, usernames, emails, dates, URLs, PGN "
            "headers, credentials, captions, detector labels or learner profiles."
        ),
        "selection_summary": packet_selection_summary(selected),
        "games": games_out,
    }
    if cycle == TEACHING_INTELLIGENCE_CYCLE:
        packet["evidence_cycle"] = cycle
        packet["selection_guards"] = {
            "minimum_eligible_games_per_player": (
                TEACHING_INTELLIGENCE_MIN_PLAYER_GAMES
            ),
            "development_player_cap": TEACHING_INTELLIGENCE_PLAYER_CAP,
            "previously_consumed_games": cycle_metadata[
                "previously_consumed"
            ],
            "previous_cycle_overlap": cycle_metadata["previous_overlap"],
            "holdout_open": False,
        }
    if include_system:
        lock_field = (
            "development_review_sha256"
            if cycle == TEACHING_INTELLIGENCE_CYCLE
            else "development_adjudication_sha256"
        )
        packet[lock_field] = adjudication_sha256
        packet["hidden_from_reviewer"] = []
        packet["system_recomposition"] = {
            "performed": False,
            "source": "stored production output",
            "persist_learning_side_effects": False,
            "allow_llm_polish": False,
            "stockfish_runs": 0,
            "model_calls": 0,
            "database_writes": 0,
        }
        assert_comparison_private(packet, sensitive)
    else:
        assert_private(packet, sensitive)
    return packet


def validate_system_comparison_gate(
    *,
    cycle: str,
    adjudication_sha256: str | None,
) -> str:
    """Open stored system output only after the matching blind review froze."""
    expected = (
        TEACHING_INTELLIGENCE_FROZEN_REVIEW_SHA256
        if cycle == TEACHING_INTELLIGENCE_CYCLE
        else FROZEN_DEVELOPMENT_ADJUDICATION_SHA256
    )
    if adjudication_sha256 != expected:
        label = (
            "frozen complete-game review"
            if cycle == TEACHING_INTELLIGENCE_CYCLE
            else "frozen development adjudication"
        )
        raise ValueError(f"system comparison requires the {label}")
    return expected


def _connect():
    return MongoClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cycle",
        choices=("whole-game-v1", TEACHING_INTELLIGENCE_CYCLE),
        default="whole-game-v1",
    )
    parser.add_argument(
        "--sample",
        choices=("development", "holdout"),
        default="development",
    )
    parser.add_argument("--freeze-marker", type=Path)
    parser.add_argument("--include-system", action="store_true")
    parser.add_argument("--development-adjudication-sha256")
    parser.add_argument(
        "--fingerprint-only",
        action="store_true",
        help="Print aggregate selection metadata; never export chess content.",
    )
    args = parser.parse_args()
    db = _connect()
    if args.fingerprint_only:
        eligible, development, holdout, cycle_metadata = (
            load_cycle_memberships(db, cycle=args.cycle)
        )
        report = {
            "evidence_cycle": args.cycle,
            "corpus": selection_summary(eligible),
            "development": selection_summary(development),
            "holdout": selection_summary(holdout),
            "overlap": len(
                {r["source_game_id"] for r in development}
                & {r["source_game_id"] for r in holdout}
            ),
            "selection_guards": cycle_metadata,
        }
        print(json.dumps(report, sort_keys=True))
        return
    include_system = bool(args.include_system)
    packet = build_packet(
        db,
        sample=args.sample,
        cycle=args.cycle,
        freeze_marker=args.freeze_marker,
        include_system=include_system,
        adjudication_sha256=args.development_adjudication_sha256,
    )
    text = (
        assert_comparison_private(packet, ())
        if include_system
        else assert_private(packet, ())
    )
    print(base64.b64encode(text.encode("utf-8")).decode("ascii"))


if __name__ == "__main__":
    main()
