#!/usr/bin/env python3
"""Build an identity-free, blinded community-game coaching review packet.

The population comes from a bounded prefix of an official Lichess CC0 monthly
archive.  For selected games, the public Lichess export supplies its already-
stored analysis variations.  The script never runs an engine, calls a model,
connects to ChessGuru's database, or writes production state.

Raw PGNs contain player names and must remain temporary.  Output contains only
legal moves, anonymous rating bands, replay fingerprints and neutral projections
of current Caption-authorized typed Review causes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

import chess
import chess.pgn
import requests


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from deterministic_coach_service import get_rating_band  # noqa: E402
from services.caption_pipeline import (  # noqa: E402
    CrossMoveState,
    MoveInputs,
    build_move_teaching_decision,
)
from services.community_game_study_service import (  # noqa: E402
    ADMISSION_POLICY_VERSION,
    APPROVED_LICENSE,
    APPROVED_PROVIDER,
    CommunityGameStudyError,
    SAFE_PROJECTION_VERSION,
    SCHEMA_VERSION as STUDY_SCHEMA_VERSION,
    principle_identity,
    project_neutral_chapter,
    public_guided_interaction,
    replay_fingerprint,
    validate_guided_interaction,
    validate_study,
)
from services.game_context_enricher import classify_time_control  # noqa: E402
from services.game_review_planner import (  # noqa: E402
    COHERENT_STORY_FORMULA,
    build_shadow_game_teaching_plan,
)
from services.game_review_shadow_runtime import (  # noqa: E402
    adapt_exact_terminal_event,
    adapt_review_event,
    derive_current_review_observations,
)


SCHEMA_VERSION = "community_game_study.neutral_review_packet.v4"
REVIEW_RESPONSE_SCHEMA_VERSION = (
    "community_game_study.independent_review_response.v1"
)
GENERATED_ON = "2026-09-15"
TERMS_REVIEWED_AT = "2026-09-15"
DEFAULT_OUTPUT = BACKEND / (
    "data/detector_gold/community_game_study_neutral_review_v4.json"
)
MAX_SOURCE_BYTES_DEFAULT = 16 * 1024 * 1024
QUALITY_ENV = {
    "PERSONALIZED_GAME_REVIEW_COACH_ENABLED": "true",
    "PERSONALIZED_GAME_REVIEW_QUALITY_V2_ENABLED": "true",
}
BEST_RE = re.compile(r"(?:Inaccuracy|Mistake|Blunder)\.\s+(.+?)\s+was best\.")


class PacketBuildError(RuntimeError):
    pass


def blank_reviewer_response() -> dict[str, Any]:
    """Return the frozen, machine-checkable independent-review form."""
    return {
        "schema_version": REVIEW_RESPONSE_SCHEMA_VERSION,
        "would_assign_to_a_player_in_this_band": None,
        "chapter_verdicts": [],
        "whole_game_story_is_coherent": None,
        "repeats_primary_principle_as_separate_chapters": None,
        "most_memorable_chapter_number": None,
        "notes": "",
    }


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _position_key(fen: Any) -> str:
    return " ".join(str(fen or "").split()[:4])


def _score_white(node: Optional[chess.pgn.GameNode]) -> Optional[int]:
    score = node.eval() if node is not None else None
    if score is None:
        return None
    return score.pov(chess.WHITE).score(mate_score=100000)


def _cp_loss(before: Optional[int], after: Optional[int], mover_white: bool) -> int:
    if before is None or after is None:
        return 0
    delta = before - after if mover_white else after - before
    return max(0, int(delta))


def _rating_band(rating: int) -> str:
    return str(get_rating_band(int(rating))["name"])


def _moves_uci(game: chess.pgn.Game) -> list[str]:
    return [move.uci() for move in game.mainline_moves()]


def _moves_san(game: chess.pgn.Game) -> list[str]:
    board = game.board()
    result = []
    for move in game.mainline_moves():
        result.append(board.san(move))
        board.push(move)
    return result


def _anonymous_game_id(replay_sha: str) -> str:
    return f"community_{_sha('community-game:' + replay_sha)[:20]}"


def _read_source_games(path: Path, *, maximum_bytes: int) -> Iterable[chess.pgn.Game]:
    if path.stat().st_size > maximum_bytes:
        raise PacketBuildError(
            f"source prefix is {path.stat().st_size} bytes; cap is {maximum_bytes}"
        )
    try:
        import zstandard
    except ImportError as exc:
        raise PacketBuildError(
            "zstandard is required; install zstandard==0.23.0 in the research task environment"
        ) from exc
    chunks: list[bytes] = []
    with path.open("rb") as raw:
        with zstandard.ZstdDecompressor().stream_reader(raw) as reader:
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                chunks.append(chunk)
    text = b"".join(chunks).decode("utf-8", errors="ignore")
    # A range download can end inside the final game.  Parsing each complete-
    # looking block independently prevents that tail from poisoning the sample.
    for raw_block in text.split("\n\n[Event ")[1:]:
        game = chess.pgn.read_game(io.StringIO("[Event " + raw_block))
        if game is None or game.errors or not list(game.mainline_moves()):
            continue
        yield game


def _dense_eval_game(game: chess.pgn.Game) -> bool:
    nodes = list(game.mainline())
    evaluated = sum(node.eval() is not None for node in nodes)
    if evaluated < max(8, len(nodes) // 2):
        return False
    losses = 0
    previous: Optional[int] = None
    for ply, node in enumerate(nodes, start=1):
        after = _score_white(node)
        if _cp_loss(previous, after, mover_white=ply % 2 == 1) >= 50:
            losses += 1
        previous = after
    return losses >= 2


def _source_candidate(game: chess.pgn.Game) -> Optional[dict[str, Any]]:
    headers = game.headers
    if str(headers.get("Variant") or "Standard").lower() != "standard":
        return None
    if str(headers.get("WhiteTitle") or "").upper() == "BOT" or str(
        headers.get("BlackTitle") or ""
    ).upper() == "BOT":
        return None
    try:
        white_rating = int(headers.get("WhiteElo") or 0)
        black_rating = int(headers.get("BlackElo") or 0)
    except (TypeError, ValueError):
        return None
    if not (
        600 <= white_rating <= 1500
        and 600 <= black_rating <= 1500
        and _rating_band(white_rating) == _rating_band(black_rating)
    ):
        return None
    category = classify_time_control(str(headers.get("TimeControl") or ""))
    if category is None or not _dense_eval_game(game):
        return None
    site = str(headers.get("Site") or "")
    match = re.fullmatch(r"https://lichess\.org/([A-Za-z0-9]{8})", site)
    if not match:
        return None
    initial_fen = game.board().fen()
    moves = _moves_uci(game)
    replay_sha = replay_fingerprint(initial_fen, moves)
    return {
        "source_game_id": match.group(1),
        "initial_fen": initial_fen,
        "moves_uci": moves,
        "replay_fingerprint": replay_sha,
        "rating_band": _rating_band(white_rating),
        "time_control_category": category,
    }


def fetch_literate_game(source_game_id: str) -> str:
    response = requests.get(
        f"https://lichess.org/game/export/{source_game_id}",
        params={
            "evals": "true",
            "clocks": "false",
            "literate": "true",
            "opening": "true",
        },
        headers={
            "Accept": "application/x-chess-pgn",
            "User-Agent": "ChessGuru community evidence builder",
        },
        timeout=30,
    )
    if response.status_code == 429:
        raise PacketBuildError("Lichess rate limit reached; stop and resume later")
    response.raise_for_status()
    return response.text


def _matching_best_variation(
    parent: chess.pgn.GameNode,
    played: chess.pgn.ChildNode,
) -> Optional[chess.pgn.ChildNode]:
    match = BEST_RE.search(str(played.comment or ""))
    if not match:
        return None
    expected = match.group(1).strip()
    board = parent.board()
    for candidate in parent.variations[1:]:
        try:
            if board.san(candidate.move) == expected:
                return candidate
        except (AssertionError, ValueError):
            continue
    return None


def rows_from_literate_game(game: chess.pgn.Game) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_eval: Optional[int] = None
    parent: chess.pgn.GameNode = game
    ply = 0
    while parent.variations:
        played = parent.variations[0]
        ply += 1
        board = parent.board()
        mover_white = board.turn == chess.WHITE
        after_eval = _score_white(played)
        loss = _cp_loss(previous_eval, after_eval, mover_white)
        best = _matching_best_variation(parent, played)
        best_san = board.san(best.move) if best is not None else None
        best_line = (
            [node.san() for node in list(best.mainline())[:5]]
            if best is not None
            else []
        )
        if chess.pgn.NAG_BLUNDER in played.nags:
            evaluation = "blunder"
        elif chess.pgn.NAG_MISTAKE in played.nags:
            evaluation = "mistake"
        elif chess.pgn.NAG_DUBIOUS_MOVE in played.nags:
            evaluation = "inaccuracy"
        else:
            evaluation = "best" if loss < 30 else "good"
        rows.append(
            {
                "ply": ply,
                "move_number": board.fullmove_number,
                "move": board.san(played.move),
                "move_san": board.san(played.move),
                "move_uci": played.move.uci(),
                "fen_before": board.fen(),
                "eval_before": previous_eval,
                "eval_after": after_eval,
                "cp_loss": loss,
                "evaluation": evaluation,
                "is_critical": loss >= 150,
                "best_move": best_san,
                "best_move_san": best_san,
                "best_move_uci": best.move.uci() if best is not None else None,
                # Lichess supplies the best branch but not a counterfactual
                # engine branch after the played move.  Leave it absent: the
                # central pipeline may use board-exact causes and must abstain
                # from any claim that requires both stored branches.
                "pv_after_played": [],
                "pv_after_best": best_line,
                "is_opponent_move": False,
            }
        )
        previous_eval = after_eval
        parent = played
    return rows


def _sanitized_movetext(game: chess.pgn.Game) -> str:
    return game.accept(
        chess.pgn.StringExporter(
            headers=False,
            variations=False,
            comments=True,
        )
    )


def _phase_for_event(
    event_id: str,
    event_rows: Mapping[str, Mapping[str, Any]],
) -> str:
    phase = str((event_rows.get(event_id) or {}).get("phase") or "")
    return phase if phase in {"opening", "middlegame", "endgame"} else "middlegame"


def _validated_demonstration(
    *,
    fen_before: str,
    played_san: str,
    value: Any,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CommunityGameStudyError(
            "neutral chapter lacks a verified demonstration"
        )
    kind = str(value.get("kind") or "")
    moves = value.get("moves_san")
    if kind not in {"played_refutation", "better_line"}:
        raise CommunityGameStudyError(
            "neutral chapter demonstration kind is invalid"
        )
    if not isinstance(moves, list) or not moves or any(
        not str(move or "").strip() for move in moves
    ):
        raise CommunityGameStudyError(
            "neutral chapter demonstration moves are invalid"
        )
    normalized = [str(move).strip() for move in moves]
    if kind == "played_refutation" and normalized[0] != played_san:
        raise CommunityGameStudyError(
            "played refutation does not start with the played move"
        )
    if kind == "better_line" and normalized[0] == played_san:
        raise CommunityGameStudyError("better line repeats the played move")
    try:
        board = chess.Board(fen_before)
        for san in normalized:
            board.push_san(san)
    except (ValueError, AssertionError) as exc:
        raise CommunityGameStudyError(
            "neutral chapter demonstration is not legal"
        ) from exc
    return {"kind": kind, "moves_san": normalized}


def _events_for_color(
    *,
    game: chess.pgn.Game,
    rows: Sequence[Mapping[str, Any]],
    anonymous_game_id: str,
    user_color: str,
    user_rating: int,
) -> tuple[list[Any], dict[str, Any], dict[str, Mapping[str, Any]], list[str]]:
    user_white = user_color == "white"
    user_rows = [row for row in rows if (int(row["ply"]) % 2 == 1) == user_white]
    opponent_rows = [row for row in rows if row not in user_rows]
    observations = derive_current_review_observations(
        game_id=anonymous_game_id,
        user_id=f"anonymous_{user_color}",
        user_color=user_color,
        pgn=_sanitized_movetext(game),
        move_evaluations=user_rows,
        opponent_move_evaluations=opponent_rows,
    )
    events: list[Any] = []
    features: dict[str, Any] = {}
    event_rows: dict[str, Mapping[str, Any]] = {}
    errors: list[str] = []
    state = CrossMoveState()
    shapes: set[str] = set()
    window: list[dict[str, Any]] = []
    history: list[str] = []
    by_fen = {_position_key(row["fen_before"]): row for row in rows}
    board = game.board()
    opening = str(game.headers.get("Opening") or "") or None
    eco = str(game.headers.get("ECO") or "") or None
    for row, move in zip(rows, game.mainline_moves()):
        san = board.san(move)
        mover_is_white = board.turn == chess.WHITE
        mover_is_user = mover_is_white == user_white
        observation = observations.get(board.fullmove_number) or {}
        try:
            decision = build_move_teaching_decision(
                MoveInputs(
                    fen_before=board.fen(),
                    played_san=san,
                    mover_is_user=mover_is_user,
                    mover_is_white=mover_is_white,
                    user_color=user_color,
                    full_move_number=board.fullmove_number,
                    move_history_san=list(history),
                    prev_move_san=history[-1] if history else None,
                    prev_move_uci=(
                        rows[int(row["ply"]) - 2]["move_uci"]
                        if int(row["ply"]) > 1
                        else None
                    ),
                    best_move_san=row.get("best_move_san"),
                    best_move_uci=row.get("best_move_uci"),
                    eval_before_cp=row.get("eval_before"),
                    eval_after_cp=row.get("eval_after"),
                    cp_loss=int(row.get("cp_loss") or 0),
                    pv_after_played=list(row.get("pv_after_played") or []),
                    pv_after_best=list(row.get("pv_after_best") or []),
                    eco_code=eco,
                    opening_name=opening,
                    user_rating=user_rating,
                    allow_fresh_engine_verification=False,
                ),
                state,
                shapes_fired_this_game=shapes,
                bs_recent_window=window,
                eval_lookup=by_fen,
                move_evaluations=rows,
            )
            if mover_is_user:
                pair = adapt_review_event(
                    decision=decision,
                    observation=observation,
                    game_id=anonymous_game_id,
                    ply=int(row["ply"]),
                    move_number=board.fullmove_number,
                    san=san,
                    env=QUALITY_ENV,
                )
                if pair is not None and pair[0].player_authorized:
                    event, feature = pair
                    events.append(event)
                    features[event.event_id] = feature
                    event_rows[event.event_id] = {
                        "fen_before": board.fen(),
                        "phase": observation.get("phase"),
                        "side_to_move": user_color,
                    }
        except Exception as exc:
            errors.append(
                f"ply_{row['ply']}:{type(exc).__name__}:{str(exc)[:120]}"
            )
        if mover_is_user:
            try:
                terminal_pair = adapt_exact_terminal_event(
                    fen_before=board.fen(),
                    played_move=san,
                    game_id=anonymous_game_id,
                    ply=int(row["ply"]),
                    move_number=board.fullmove_number,
                    phase=str(observation.get("phase") or "endgame"),
                )
                if terminal_pair is not None:
                    terminal_event, terminal_feature = terminal_pair
                    events.append(terminal_event)
                    features[terminal_event.event_id] = terminal_feature
                    event_rows[terminal_event.event_id] = {
                        "fen_before": board.fen(),
                        "phase": terminal_feature.phase,
                        "side_to_move": user_color,
                    }
            except Exception as exc:
                errors.append(
                    f"ply_{row['ply']}:terminal:{type(exc).__name__}:"
                    f"{str(exc)[:120]}"
                )
        board.push(move)
        history.append(san)
    return events, features, event_rows, errors


def build_study_candidate(
    source: Mapping[str, Any],
    literate_pgn: str,
    *,
    release_id: str,
    release_sha256: str,
) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]], list[str]]:
    game = chess.pgn.read_game(io.StringIO(literate_pgn))
    if game is None or game.errors:
        return None, None, ["invalid_literate_export"]
    if _moves_uci(game) != list(source["moves_uci"]):
        return None, None, ["monthly_and_literate_replay_disagree"]
    rows = rows_from_literate_game(game)
    anonymous_game_id = _anonymous_game_id(str(source["replay_fingerprint"]))
    try:
        white_rating = int(game.headers.get("WhiteElo") or 0)
        black_rating = int(game.headers.get("BlackElo") or 0)
    except (TypeError, ValueError):
        return None, None, ["literate_export_missing_ratings"]
    events = []
    features = {}
    event_rows: dict[str, Mapping[str, Any]] = {}
    errors: list[str] = []
    for color, rating in (("white", white_rating), ("black", black_rating)):
        color_events, color_features, color_rows, color_errors = _events_for_color(
            game=game,
            rows=rows,
            anonymous_game_id=anonymous_game_id,
            user_color=color,
            user_rating=rating,
        )
        events.extend(color_events)
        features.update(color_features)
        event_rows.update(color_rows)
        errors.extend(color_errors)
    event_index = {event.event_id: event for event in events}
    coherent_features = {}
    interactive_events = []
    for event in events:
        context = event_rows[event.event_id]
        draft_reference = {
            "event_id": event.event_id,
            "concept_id": event.concept.concept_id,
            "quality_id": event.evidence.quality_id,
            "phase": _phase_for_event(event.event_id, event_rows),
            "ply": event.move.ply,
            "move_number": event.move.number,
            "role": "turning_point",
            "primary_principle_id": "pending",
        }
        try:
            draft = project_neutral_chapter(
                event.contract_dict(), draft_reference
            )
            draft["demonstration"] = _validated_demonstration(
                fen_before=str(context["fen_before"]),
                played_san=str(draft["move_san"]),
                value=draft.get("demonstration"),
            )
            draft["interaction"] = validate_guided_interaction(
                draft,
                fen_before=str(context["fen_before"]),
            )
        except CommunityGameStudyError as exc:
            errors.append(f"event_{event.event_id}:interaction:{exc}")
            continue
        interactive_events.append(event)
        coherent_features[event.event_id] = replace(
            features[event.event_id],
            phase=draft_reference["phase"],
            primary_principle_id=principle_identity(draft),
            primary_family=event.evidence.quality_id,
        )
    result = build_shadow_game_teaching_plan(
        game_id=anonymous_game_id,
        events=tuple(interactive_events),
        features=coherent_features,
        generated_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
        formula_id=COHERENT_STORY_FORMULA,
    )
    if result.plan is None or len(result.plan.chapters) < 2:
        return None, None, errors + [
            f"authorized_chapters_{0 if result.plan is None else len(result.plan.chapters)}"
        ]
    refs = []
    neutral = []
    for chapter in result.plan.chapters:
        event = event_index[chapter.event_id]
        reference = {
            "event_id": event.event_id,
            "concept_id": event.concept.concept_id,
            "quality_id": event.evidence.quality_id,
            "phase": _phase_for_event(event.event_id, event_rows),
            "ply": event.move.ply,
            "move_number": event.move.number,
            "role": chapter.role.value,
            "primary_principle_id": coherent_features[
                event.event_id
            ].primary_principle_id,
        }
        refs.append(reference)
        projected = project_neutral_chapter(event.contract_dict(), reference)
        context = event_rows[event.event_id]
        projected["demonstration"] = _validated_demonstration(
            fen_before=str(context["fen_before"]),
            played_san=str(projected["move_san"]),
            value=projected.get("demonstration"),
        )
        projected["interaction"] = validate_guided_interaction(
            projected,
            fen_before=str(context["fen_before"]),
        )
        neutral.append(
            {
                **projected,
                "story_role": chapter.role.value,
                "position": {
                    "fen": context["fen_before"],
                    "side_to_move": context["side_to_move"],
                },
            }
        )
    replay_sha = str(source["replay_fingerprint"])
    study_id = f"study_{_sha('community-study:' + replay_sha)[:20]}"
    study = {
        "schema_version": STUDY_SCHEMA_VERSION,
        "admission_policy_version": ADMISSION_POLICY_VERSION,
        "study_id": study_id,
        "game_id": anonymous_game_id,
        "status": "shadow",
        "source": {
            "provider": APPROVED_PROVIDER,
            "license": APPROVED_LICENSE,
            "release_id": release_id,
            "source_checksum": release_sha256,
            "record_key_hash": _sha(f"{release_id}:{replay_sha}"),
            "terms_reviewed_at": TERMS_REVIEWED_AT,
        },
        "game": {
            "initial_fen": str(source["initial_fen"]),
            "moves_uci": list(source["moves_uci"]),
            "rating_band": str(source["rating_band"]),
            "time_control_category": str(source["time_control_category"]),
        },
        "replay": {"legal": True, "fingerprint": replay_sha},
        "plan": {
            "plan_id": result.plan.plan_id,
            "input_fingerprint": result.plan.input_fingerprint,
            "safe_projection_version": SAFE_PROJECTION_VERSION,
            "story_formula": COHERENT_STORY_FORMULA,
            "chapters": refs,
        },
        "evidence": {
            "events": [
                event_index[reference["event_id"]].contract_dict()
                for reference in refs
            ],
            "chapter_positions": [
                {
                    "event_id": reference["event_id"],
                    "ply": reference["ply"],
                    "fen": str(event_rows[reference["event_id"]]["fen_before"]),
                }
                for reference in refs
            ],
        },
        "privacy": {
            "identity_state": "anonymous",
            "contains_identity_fields": False,
        },
    }
    validate_study(study)
    review = {
        "case_id": _sha(f"neutral-review:{study_id}")[:20],
        "game": {
            "initial_fen": str(source["initial_fen"]),
            "moves_uci": list(source["moves_uci"]),
            "moves_san": _moves_san(game),
            "rating_band": str(source["rating_band"]),
            "time_control_category": str(source["time_control_category"]),
            "result": str(game.headers.get("Result") or "*"),
            "opening": str(game.headers.get("Opening") or "") or None,
        },
        "chapters": [
            {
                key: (
                    public_guided_interaction(value)
                    if key == "interaction"
                    else value
                )
                for key, value in chapter.items()
                if key not in {"event_id", "concept_id", "quality_id"}
            }
            for chapter in neutral
        ],
        "reviewer_response": blank_reviewer_response(),
    }
    return study, review, errors


def build_packet(
    *,
    source_path: Path,
    release_id: str,
    release_sha256: str,
    fetch_limit: int,
    maximum_source_bytes: int,
    fetcher: Callable[[str], str] = fetch_literate_game,
    request_delay_seconds: float = 0.15,
    admission_sink: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", release_sha256):
        raise PacketBuildError("release_sha256 must be a lowercase SHA-256")
    counters: Counter[str] = Counter()
    reviews = []
    study_fingerprints = []
    seen_replays = set()
    for game in _read_source_games(source_path, maximum_bytes=maximum_source_bytes):
        counters["source_games_parsed"] += 1
        candidate = _source_candidate(game)
        if candidate is None:
            continue
        counters["source_candidates"] += 1
        replay_sha = candidate["replay_fingerprint"]
        if replay_sha in seen_replays:
            counters["duplicate_replays"] += 1
            continue
        if counters["literate_exports_requested"] >= fetch_limit:
            break
        seen_replays.add(replay_sha)
        counters["literate_exports_requested"] += 1
        try:
            pgn = fetcher(str(candidate["source_game_id"]))
            study, review, errors = build_study_candidate(
                candidate,
                pgn,
                release_id=release_id,
                release_sha256=release_sha256,
            )
        except Exception as exc:
            counters[f"fetch_or_build_error:{type(exc).__name__}"] += 1
            if isinstance(exc, PacketBuildError):
                raise
            continue
        for error in errors:
            counters[f"pipeline_note:{error.split(':', 1)[0]}"] += 1
        if study is None or review is None:
            counters["not_admitted_to_review_packet"] += 1
        else:
            counters["review_cases"] += 1
            reviews.append(review)
            study_fingerprints.append(study["replay"]["fingerprint"])
            if admission_sink is not None:
                admission_sink.append({
                    "case_id": review["case_id"],
                    "study": study,
                })
        if request_delay_seconds:
            time.sleep(request_delay_seconds)
    reviews.sort(key=lambda row: row["case_id"])
    case_ids = [row["case_id"] for row in reviews]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_on": GENERATED_ON,
        "status": "independent_coach_review_pending",
        "runtime_exposure": "none",
        "source": {
            "provider": APPROVED_PROVIDER,
            "license": APPROVED_LICENSE,
            "release_id": release_id,
            "release_sha256": release_sha256,
            "local_prefix_sha256": _file_sha256(source_path),
            "local_prefix_bytes": source_path.stat().st_size,
            "raw_identity_bearing_pgn_retained": False,
        },
        "execution": {
            "production_database_reads": 0,
            "production_database_writes": 0,
            "stockfish_runs": 0,
            "llm_or_model_calls": 0,
            "player_visible_changes": 0,
            "public_literate_exports_requested": counters[
                "literate_exports_requested"
            ],
        },
        "selection": {
            "population": "rated standard games with both players 600-1500",
            "rating_rule": "both players share one canonical ChessGuru rating band",
            "evidence_rule": "dense stored evals and at least two 50cp decisions",
            "review_rule": (
                "two or three distinct-principle Caption-authorized neutral "
                "chapters selected by coherent_role_then_quality.v1"
            ),
            "source_order": "official monthly archive order",
            "fetch_limit": fetch_limit,
            "selection_fingerprint_sha256": _sha("|".join(case_ids)),
            "replay_population_fingerprint_sha256": _sha(
                "|".join(sorted(study_fingerprints))
            ),
        },
        "measurement": dict(sorted(counters.items())),
        "blinding": {
            "source_game_ids_exposed": False,
            "player_names_or_usernames_exposed": False,
            "exact_player_ratings_exposed": False,
            "detector_or_quality_ids_exposed": False,
            "source_player_personalization_exposed": False,
        },
        "review_rubric": {
            "response_schema_version": REVIEW_RESPONSE_SCHEMA_VERSION,
            "chapter_verdict_values": [
                "correct_and_teachable",
                "correct_but_not_teachable",
                "unclear_or_too_generic",
                "incorrect_or_overclaimed",
            ],
            "required_checks": [
                "the board and move support every sentence",
                "the chapter explains why rather than announcing a verdict",
                "the wording is understandable for a 600-1500 player",
                "the lesson is memorable enough to assign",
                "the selected chapters form a coherent whole-game walkthrough",
                "every headline begins with a pattern, geometry or chess idea rather than SAN",
                "no study repeats one primary principle as separate teaching",
                "the prediction options are position-specific and the hidden answer agrees with the proof",
                "the proof-supporting answer does not occupy one fixed option position across the packet",
                "no source-player identity or private diagnosis is visible",
            ],
            "required_chapter_response_fields": {
                "chapter_index": "zero-based index into this case's chapters",
                "move_number": "must match the displayed chapter",
                "move_san": "must match the displayed chapter",
                "verdict": "one of chapter_verdict_values",
                "headline_is_pattern_geometry_or_idea_led": "boolean",
                "demonstration_legally_proves_visible_claim": "boolean",
                "critical_false_claim": "boolean",
                "why": "concise independent reason for the verdict",
            },
        },
        "promotion_boundary": {
            "player_visible_community_studies_allowed": False,
            "next_decision": (
                "freeze independent coach review, measure accepted chapter and "
                "whole-game rates, then lock personal-versus-community source mix"
            ),
        },
        "cases": reviews,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zst", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--release-sha256", required=True)
    parser.add_argument("--fetch-limit", type=int, default=60)
    parser.add_argument(
        "--maximum-source-bytes", type=int, default=MAX_SOURCE_BYTES_DEFAULT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--admission-output",
        type=Path,
        help=(
            "Optional sealed anonymous runtime-candidate packet. Do not give "
            "this answer-bearing artifact to the independent reviewer."
        ),
    )
    args = parser.parse_args()
    if args.fetch_limit < 1:
        raise PacketBuildError("fetch_limit must be positive")
    admissions: list[dict[str, Any]] = []
    packet = build_packet(
        source_path=args.source_zst.resolve(),
        release_id=args.release_id,
        release_sha256=args.release_sha256,
        fetch_limit=args.fetch_limit,
        maximum_source_bytes=args.maximum_source_bytes,
        admission_sink=admissions,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if args.admission_output:
        admission_packet = {
            "schema_version": "community_game_study.admission_packet.v1",
            "generated_on": GENERATED_ON,
            "runtime_exposure": "none",
            "review_packet_schema_version": SCHEMA_VERSION,
            "selection_fingerprint_sha256": packet["selection"][
                "selection_fingerprint_sha256"
            ],
            "source": packet["source"],
            "records": sorted(admissions, key=lambda item: item["case_id"]),
        }
        args.admission_output.parent.mkdir(parents=True, exist_ok=True)
        args.admission_output.write_text(
            json.dumps(admission_packet, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "output": str(args.output),
        "admission_output": (
            str(args.admission_output) if args.admission_output else None
        ),
        "cases": len(packet["cases"]),
        "measurement": packet["measurement"],
    }, indent=2))


if __name__ == "__main__":
    main()
