#!/usr/bin/env python3
"""Build a blinded Caption-promotion packet for played checkmate facts.

The source is a bounded prefix of the official Lichess CC0 archive. Raw PGNs
remain temporary and may contain player names; this packet keeps only FENs,
legal moves, coarse rating bands, anonymous replay hashes and the exact copy
under review. No database, chess engine, model or production state is used.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Optional

import chess
import chess.pgn


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from scripts.build_community_game_study_review_packet import (  # noqa: E402
    MAX_SOURCE_BYTES_DEFAULT,
    PacketBuildError,
    _file_sha256,
    _moves_uci,
    _rating_band,
    _read_source_games,
)
from services.caption_facts import (  # noqa: E402
    EXACT_TERMINAL_FACT_VERSION,
    EXACT_TERMINAL_QUALITY_ID,
    build_exact_terminal_fact,
)
from services.caption_pipeline import (  # noqa: E402
    build_exact_terminal_teaching,
    render_exact_terminal_teaching_claim,
)
from services.community_game_study_service import replay_fingerprint  # noqa: E402


SCHEMA_VERSION = "exact_terminal_checkmate.caption_review_packet.v1"
ANSWER_KEY_SCHEMA_VERSION = "exact_terminal_checkmate.caption_answer_key.v1"
REVIEW_RESPONSE_SCHEMA_VERSION = (
    "exact_terminal_checkmate.independent_review_response.v1"
)
GENERATED_ON = "2026-09-15"
CAPTION_FIRE_MINIMUM = 50
TRUE_NEGATIVE_MINIMUM = 20
DEFAULT_OUTPUT = BACKEND / (
    "data/detector_gold/exact_terminal_checkmate_caption_review_v1.json"
)
DEFAULT_ANSWER_KEY_OUTPUT = BACKEND / (
    "data/corpus_snapshots/"
    "exact_terminal_checkmate_caption_answer_key_v1.json"
)
_CONTROL_FAMILIES = (
    "check_with_legal_reply",
    "nonchecking_game_end",
    "ordinary_legal_move",
    "stalemate",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _hash(value: str, *, namespace: str) -> str:
    return hashlib.sha256(f"{namespace}:{value}".encode("utf-8")).hexdigest()


def _standard_human_band(game: chess.pgn.Game) -> Optional[str]:
    headers = game.headers
    if str(headers.get("Variant") or "Standard").lower() != "standard":
        return None
    if str(headers.get("WhiteTitle") or "").upper() == "BOT" or str(
        headers.get("BlackTitle") or ""
    ).upper() == "BOT":
        return None
    try:
        white = int(headers.get("WhiteElo") or 0)
        black = int(headers.get("BlackElo") or 0)
    except (TypeError, ValueError):
        return None
    if not (600 <= white <= 1500 and 600 <= black <= 1500):
        return None
    white_band = _rating_band(white)
    return white_band if white_band == _rating_band(black) else None


def _record(
    *,
    game_key: str,
    rating_band: str,
    fen_before: str,
    move: chess.Move,
    move_san: str,
    family: str,
) -> dict[str, Any]:
    board = chess.Board(fen_before)
    if move not in board.legal_moves:
        raise PacketBuildError("terminal packet received an illegal source move")
    after = board.copy(stack=False)
    after.push(move)
    king = after.king(after.turn)
    if king is None:
        raise PacketBuildError("terminal packet source position has no king")
    signature = f"{fen_before}|{move.uci()}"
    return {
        "case_id": _hash(signature, namespace="exact-terminal-case")[:24],
        "source_unit": game_key,
        "rating_band": rating_band,
        "fen_before": fen_before,
        "move_uci": move.uci(),
        "move_san": move_san,
        "checked_king_square": chess.square_name(king),
        "control_family": family,
    }


def _scan_games(
    games: Iterable[chess.pgn.Game],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    fires: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    census: Counter[str] = Counter()
    seen_replays: set[str] = set()
    for game in games:
        census["games_scanned"] += 1
        band = _standard_human_band(game)
        if band is None:
            census["games_outside_population"] += 1
            continue
        moves = list(game.mainline_moves())
        if not moves:
            continue
        try:
            replay_sha = replay_fingerprint(game.board().fen(), _moves_uci(game))
        except (AssertionError, ValueError):
            census["illegal_games"] += 1
            continue
        if replay_sha in seen_replays:
            census["duplicate_games"] += 1
            continue
        seen_replays.add(replay_sha)
        game_key = _hash(replay_sha, namespace="exact-terminal-source")[:24]
        board = game.board()
        game_controls: dict[str, dict[str, Any]] = {}
        game_fire: Optional[dict[str, Any]] = None
        for index, move in enumerate(moves):
            if move not in board.legal_moves:
                census["illegal_games"] += 1
                game_fire = None
                game_controls = {}
                break
            fen_before = board.fen()
            move_san = board.san(move)
            fact = build_exact_terminal_fact(
                fen_before=fen_before,
                played_move=move.uci(),
            )
            after = board.copy(stack=False)
            after.push(move)
            if fact is not None:
                game_fire = _record(
                    game_key=game_key,
                    rating_band=band,
                    fen_before=fen_before,
                    move=move,
                    move_san=move_san,
                    family="candidate",
                )
            elif after.is_stalemate():
                game_controls.setdefault(
                    "stalemate",
                    _record(
                        game_key=game_key,
                        rating_band=band,
                        fen_before=fen_before,
                        move=move,
                        move_san=move_san,
                        family="stalemate",
                    ),
                )
            elif after.is_check():
                game_controls.setdefault(
                    "check_with_legal_reply",
                    _record(
                        game_key=game_key,
                        rating_band=band,
                        fen_before=fen_before,
                        move=move,
                        move_san=move_san,
                        family="check_with_legal_reply",
                    ),
                )
            elif index == len(moves) - 1:
                game_controls.setdefault(
                    "nonchecking_game_end",
                    _record(
                        game_key=game_key,
                        rating_band=band,
                        fen_before=fen_before,
                        move=move,
                        move_san=move_san,
                        family="nonchecking_game_end",
                    ),
                )
            else:
                game_controls.setdefault(
                    "ordinary_legal_move",
                    _record(
                        game_key=game_key,
                        rating_band=band,
                        fen_before=fen_before,
                        move=move,
                        move_san=move_san,
                        family="ordinary_legal_move",
                    ),
                )
            board.push(move)
        if game_fire is not None:
            fires.append(game_fire)
            census["exact_checkmate_games"] += 1
        else:
            controls.extend(game_controls.values())
            for family in game_controls:
                census[f"control_population:{family}"] += 1
    return fires, controls, census


def _stable(rows: Iterable[Mapping[str, Any]], *, namespace: str) -> list[dict[str, Any]]:
    return sorted(
        (dict(row) for row in rows),
        key=lambda row: _hash(str(row["case_id"]), namespace=namespace),
    )


def _select_controls(
    rows: Iterable[Mapping[str, Any]],
    *,
    excluded_sources: set[str],
) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row["source_unit"]) not in excluded_sources:
            by_family[str(row["control_family"])].append(dict(row))
    selected: list[dict[str, Any]] = []
    selected_sources: set[str] = set(excluded_sources)
    selected_cases: set[str] = set()
    for family in _CONTROL_FAMILIES:
        for row in _stable(
            by_family.get(family, ()),
            namespace=f"exact-terminal-control-family:{family}",
        ):
            if (
                row["source_unit"] not in selected_sources
                and row["case_id"] not in selected_cases
            ):
                selected.append(row)
                selected_sources.add(row["source_unit"])
                selected_cases.add(row["case_id"])
                break
    for row in _stable(rows, namespace="exact-terminal-control-fill"):
        if len(selected) >= TRUE_NEGATIVE_MINIMUM:
            break
        if (
            row["source_unit"] in selected_sources
            or row["case_id"] in selected_cases
        ):
            continue
        selected.append(dict(row))
        selected_sources.add(str(row["source_unit"]))
        selected_cases.add(str(row["case_id"]))
    if len(selected) < TRUE_NEGATIVE_MINIMUM:
        raise PacketBuildError(
            "public source prefix does not contain 20 distinct negative controls"
        )
    return selected[:TRUE_NEGATIVE_MINIMUM]


def _review_case(row: Mapping[str, Any]) -> dict[str, Any]:
    board = chess.Board(str(row["fen_before"]))
    move = chess.Move.from_uci(str(row["move_uci"]))
    if move not in board.legal_moves:
        raise PacketBuildError("review case move is illegal")
    move_san = board.san(move)
    visible = render_exact_terminal_teaching_claim(
        move_san=move_san,
        checked_king_square=str(row["checked_king_square"]),
    )
    return {
        "case_id": row["case_id"],
        "review_group": row["source_unit"],
        "rating_band": row["rating_band"],
        "position": {
            "fen": row["fen_before"],
            "side_to_move": "white" if board.turn else "black",
        },
        "played_move": {
            "uci": move.uci(),
            "san_without_check_suffix": move_san.rstrip("+#"),
        },
        "proposed_player_copy": {
            "headline": visible["headline"],
            "explanation": visible["explanation"],
            "principle": visible["principle"],
        },
        "reviewer_response": {
            "schema_version": REVIEW_RESPONSE_SCHEMA_VERSION,
            "verdict": None,
            "teaching_verdict": None,
            "critical_false_claim": None,
            "review_note": "",
        },
    }


def build_packet(
    *,
    source_path: Path,
    release_id: str,
    release_sha256: str,
    maximum_source_bytes: int = MAX_SOURCE_BYTES_DEFAULT,
    with_membership: bool = False,
) -> Any:
    if not str(release_id or "").strip():
        raise PacketBuildError("release id is required")
    if not _SHA256.fullmatch(str(release_sha256 or "").strip().lower()):
        raise PacketBuildError("release SHA-256 is malformed")
    fires, control_population, census = _scan_games(
        _read_source_games(source_path, maximum_bytes=maximum_source_bytes)
    )
    selected_fires = _stable(
        fires, namespace="exact-terminal-fire-selection"
    )[:CAPTION_FIRE_MINIMUM]
    if len(selected_fires) < CAPTION_FIRE_MINIMUM:
        raise PacketBuildError(
            "public source prefix does not contain 50 distinct played checkmates"
        )
    fire_sources = {str(row["source_unit"]) for row in selected_fires}
    selected_controls = _select_controls(
        control_population,
        excluded_sources=fire_sources,
    )
    selected = selected_fires + selected_controls
    public_cases = [_review_case(row) for row in selected]
    public_cases.sort(
        key=lambda row: _hash(
            str(row["case_id"]), namespace="exact-terminal-review-order"
        )
    )
    case_ids = [str(row["case_id"]) for row in public_cases]
    control_counts = Counter(
        str(row["control_family"]) for row in selected_controls
    )
    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_on": GENERATED_ON,
        "runtime_exposure": "none",
        "read_only": True,
        "stockfish_runs": 0,
        "llm_calls": 0,
        "database_reads": 0,
        "database_writes": 0,
        "quality_id": EXACT_TERMINAL_QUALITY_ID,
        "proof_version": EXACT_TERMINAL_FACT_VERSION,
        "source": {
            "provider": "lichess_open_database",
            "license": "CC0-1.0",
            "release_id": str(release_id),
            "release_sha256": str(release_sha256).lower(),
            "bounded_prefix_sha256": _file_sha256(source_path),
            "bounded_prefix_bytes": source_path.stat().st_size,
            "raw_identity_retained": False,
        },
        "selection": {
            "candidate_policy": (
                "50 distinct legal played moves whose reconstructed board is checkmate"
            ),
            "control_policy": (
                "20 distinct-source legal no-fires, covering every negative family "
                "available in the bounded public population before stable fill"
            ),
            "candidate_count_hidden": len(selected_fires),
            "control_count_hidden": len(selected_controls),
            "selection_fingerprint_sha256": hashlib.sha256(
                "|".join(case_ids).encode("utf-8")
            ).hexdigest(),
        },
        "population": {
            **dict(sorted(census.items())),
            "candidate_fires_available": len(fires),
            "negative_controls_available": len(control_population),
            "selected_control_families_hidden": dict(sorted(control_counts.items())),
        },
        "promotion_gate": {
            "caption_fire_minimum": CAPTION_FIRE_MINIMUM,
            "true_negative_minimum": TRUE_NEGATIVE_MINIMUM,
            "semantic_precision_minimum_pct": 95.0,
            "wilson_lower_minimum_pct": 85.0,
            "critical_false_claims_allowed": 0,
            "independent_review_complete": False,
            "caption_promotion_gate_passed": False,
            "status": "shadow",
        },
        "review_rubric": {
            "verdict_values": [
                "proved_exact_terminal_checkmate",
                "not_proved",
                "invalid_case",
            ],
            "teaching_verdict_values": [
                "correct_and_teachable",
                "correct_but_not_teachable",
                "incorrect_or_overclaimed",
            ],
            "required_checks": [
                "the displayed move is legal from the displayed FEN",
                "after the move the opposing king is in check",
                "the opposing side has exactly zero legal replies",
                "the position is checkmate rather than stalemate, resignation or timeout",
                "the proposed copy makes no claim beyond that exact board state",
                "the wording is understandable and useful for a 600-1500 player",
                "the demonstration starts with and legally replays the displayed move",
                "candidate and control membership is not inferred from move notation because check suffixes are removed",
            ],
        },
        "promotion_boundary": {
            "player_visible_terminal_chapters_allowed": False,
            "next_decision": (
                "freeze an independent review, reveal sealed membership only after "
                "the review is complete, score the Caption gate, then decide promotion"
            ),
        },
        "cases": public_cases,
    }
    if with_membership:
        return packet, {
            "candidate_case_ids": sorted(str(row["case_id"]) for row in selected_fires),
            "control_case_ids": sorted(str(row["case_id"]) for row in selected_controls),
        }
    return packet


def build_answer_key(
    *,
    packet: Mapping[str, Any],
    membership: Mapping[str, Any],
    packet_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": ANSWER_KEY_SCHEMA_VERSION,
        "generated_on": GENERATED_ON,
        "sealed": True,
        "do_not_open_before_independent_review_is_frozen": True,
        "source_packet": {
            "sha256": packet_sha256,
            "selection_fingerprint_sha256": packet["selection"][
                "selection_fingerprint_sha256"
            ],
        },
        "candidate_case_ids": list(membership["candidate_case_ids"]),
        "control_case_ids": list(membership["control_case_ids"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zst", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--release-sha256", required=True)
    parser.add_argument(
        "--maximum-source-bytes", type=int, default=MAX_SOURCE_BYTES_DEFAULT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--answer-key-output", type=Path, default=DEFAULT_ANSWER_KEY_OUTPUT
    )
    args = parser.parse_args()
    packet, membership = build_packet(
        source_path=args.source_zst.resolve(),
        release_id=args.release_id,
        release_sha256=args.release_sha256,
        maximum_source_bytes=args.maximum_source_bytes,
        with_membership=True,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    packet_sha = _file_sha256(args.output)
    answer_key = build_answer_key(
        packet=packet,
        membership=membership,
        packet_sha256=packet_sha,
    )
    args.answer_key_output.parent.mkdir(parents=True, exist_ok=True)
    args.answer_key_output.write_text(
        json.dumps(answer_key, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "packet": str(args.output),
        "packet_sha256": packet_sha,
        "sealed_answer_key": str(args.answer_key_output),
        "cases": len(packet["cases"]),
        "promotion_gate": packet["promotion_gate"],
    }, indent=2))


if __name__ == "__main__":
    main()
