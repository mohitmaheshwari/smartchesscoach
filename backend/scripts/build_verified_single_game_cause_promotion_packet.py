"""Build a deterministic, read-only promotion packet from stored analyses.

The script reuses the production review reconstruction. It never invokes a
fresh chess engine, an LLM, or a database write. Output identifiers are
one-way hashes so the versioned packet contains no account identity.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
import os
from typing import Any, Iterable, Mapping

from pymongo import MongoClient

from scripts.audit_personalized_review_ten_games import GAME_IDS, _replay_game


SCHEMA_VERSION = "verified_single_game_cause.promotion_packet.v1"
DEFAULT_FIRE_TARGET = 70
DEFAULT_NEGATIVE_TARGET = 30
DEFAULT_MAX_GAMES = 40
DEFAULT_MAX_FIRES_PER_GAME = 3
DEFAULT_MAX_NEGATIVES_PER_GAME = 2
DEFAULT_ACCOUNT_EMAIL = "bhutramohit@gmail.com"


def _stable_hash(value: object, *, namespace: str) -> str:
    payload = f"{namespace}:{value}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _selected_fields(
    event: Mapping[str, Any],
    *,
    player_key: str,
    game_key: str,
    source_set: str,
) -> dict[str, Any]:
    return {
        "case_id": _stable_hash(
            f"{game_key}:{event.get('ply')}", namespace="review-cause-case"
        ),
        "player_key": player_key,
        "game_key": game_key,
        "source_set": source_set,
        "ply": event.get("ply"),
        "move_number": event.get("move_number"),
        "move_san": event.get("move_san"),
        "fen_before": event.get("fen_before"),
        "best_move_san": event.get("best_move_san"),
        "cp_loss": event.get("cp_loss"),
        "pv_after_played": event.get("pv_after_played") or [],
        "pv_after_best": event.get("pv_after_best") or [],
        "severity_practical": event.get("severity_practical"),
        "stayed_winning": bool(event.get("stayed_winning")),
        "decisiveness_changed": bool(event.get("decisiveness_changed")),
        "cause": event.get("v2_cause"),
        "caption": event.get("v2_caption"),
        "principle": event.get("v2_principle"),
        "visual": event.get("event_visual"),
        "reflection_option_ids": event.get("reflection_option_ids") or [],
        "claim_violations": event.get("v2_claim_violations") or [],
        "automated_quality_issues": event.get("v2_issues") or [],
    }


def _authorized_account_games(
    db: Any,
) -> Iterable[tuple[Mapping[str, Any], Mapping[str, Any], str]]:
    excluded = set(GAME_IDS)
    account_email = os.environ.get(
        "PROMOTION_ACCOUNT_EMAIL", DEFAULT_ACCOUNT_EMAIL
    )
    user = db.users.find_one(
        {"email": account_email}, {"_id": 0, "user_id": 1}
    ) or {}
    user_id = str(user.get("user_id") or "")
    if not user_id:
        raise RuntimeError("authorized promotion account was not found")
    fixed_games = {
        row["game_id"]: row
        for row in db.games.find(
            {
                "user_id": user_id,
                "game_id": {"$in": list(GAME_IDS)},
            },
            {"_id": 0},
        )
    }
    for game_id in GAME_IDS:
        game = fixed_games.get(game_id)
        if not game:
            continue
        analysis = db.game_analyses.find_one({"game_id": game_id}, {"_id": 0})
        if analysis:
            yield game, analysis, "fixed_ten_game_gold"
    candidates = [
        row
        for row in db.games.find(
            {
                "user_id": user_id,
                "pgn": {"$exists": True},
                "game_id": {"$nin": list(excluded)},
            },
            {"_id": 0},
        )
        if row.get("game_id")
    ]
    candidates.sort(
        key=lambda row: _stable_hash(
            row.get("game_id"), namespace="review-cause-game"
        )
    )
    maximum = int(os.environ.get("PROMOTION_MAX_GAMES", DEFAULT_MAX_GAMES))
    for game in candidates[:maximum]:
        analysis = db.game_analyses.find_one(
            {"game_id": game.get("game_id")}, {"_id": 0}
        )
        if analysis:
            yield game, analysis, "expanded_authorized_account"


def main() -> None:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    fire_target = int(os.environ.get("PROMOTION_FIRE_TARGET", DEFAULT_FIRE_TARGET))
    negative_target = int(
        os.environ.get("PROMOTION_NEGATIVE_TARGET", DEFAULT_NEGATIVE_TARGET)
    )
    max_fires_per_game = int(
        os.environ.get("PROMOTION_MAX_FIRES_PER_GAME", DEFAULT_MAX_FIRES_PER_GAME)
    )
    max_negatives_per_game = int(
        os.environ.get(
            "PROMOTION_MAX_NEGATIVES_PER_GAME", DEFAULT_MAX_NEGATIVES_PER_GAME
        )
    )
    fires: list[dict[str, Any]] = []
    negatives: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    processed_games = 0
    processed_players: set[str] = set()

    for game, analysis, source_set in _authorized_account_games(db):
        game_id = str(game.get("game_id"))
        user_id = str(game.get("user_id"))
        player_key = _stable_hash(user_id, namespace="review-cause-player")
        game_key = _stable_hash(game_id, namespace="review-cause-game")
        try:
            result = _replay_game(game, analysis)
        except Exception as exc:
            failures.append(
                {
                    "game_key": game_key,
                    "error": f"{type(exc).__name__}:{str(exc)[:160]}",
                }
            )
            continue
        processed_games += 1
        processed_players.add(player_key)
        events = list(result.get("significant_events") or [])
        game_fires = [event for event in events if event.get("v2_cause")]
        game_negatives = [event for event in events if not event.get("v2_cause")]
        per_game_fire_limit = (
            len(events)
            if source_set == "fixed_ten_game_gold"
            else max_fires_per_game
        )
        fire_room = max(0, fire_target - len(fires))
        fires.extend(
            _selected_fields(
                event,
                player_key=player_key,
                game_key=game_key,
                source_set=source_set,
            )
            for event in game_fires[: min(per_game_fire_limit, fire_room)]
        )
        negative_room = max(0, negative_target - len(negatives))
        negatives.extend(
            _selected_fields(
                event,
                player_key=player_key,
                game_key=game_key,
                source_set=source_set,
            )
            for event in game_negatives[
                : min(max_negatives_per_game, negative_room)
            ]
            if source_set == "expanded_authorized_account"
        )
        if len(fires) >= fire_target and len(negatives) >= negative_target:
            break

    output = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": date.today().isoformat(),
        "read_only": True,
        "engine_runs": 0,
        "llm_calls": 0,
        "database_writes": 0,
        "selection": {
            "method": "sha256_ordered_authorized_account_games",
            "account_identity_in_output": False,
            "fixed_ten_game_gold_first": True,
            "fire_target": fire_target,
            "negative_target": negative_target,
            "max_fires_per_game": max_fires_per_game,
            "max_negatives_per_game": max_negatives_per_game,
        },
        "summary": {
            "players": len(processed_players),
            "games_processed": processed_games,
            "fires": len(fires),
            "negatives": len(negatives),
            "fires_with_automated_quality_issues": sum(
                bool(case["automated_quality_issues"]) for case in fires
            ),
            "fires_with_claim_violations": sum(
                bool(case["claim_violations"]) for case in fires
            ),
            "failures": len(failures),
        },
        "fires": fires,
        "negatives": negatives,
        "failures": failures,
    }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
