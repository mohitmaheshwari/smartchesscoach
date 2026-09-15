#!/usr/bin/env python3
"""Measure coherent community-game story supply without product writes.

This research-only command reuses the frozen community packet population,
central Review event adapter, existing exact tactic proof services and the
detector-quality registry.  It performs no database access, engine run or
model call.  Identity-bearing PGN input remains outside the output.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

import chess
import chess.pgn


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from scripts.build_community_game_study_review_packet import (  # noqa: E402
    PacketBuildError,
    QUALITY_ENV,
    _anonymous_game_id,
    _file_sha256,
    _moves_uci,
    _read_source_games,
    _source_candidate,
    _events_for_color,
    fetch_literate_game,
    rows_from_literate_game,
)
from services.aligned_tactic_puzzle_proof import (  # noqa: E402
    ALIGNED_QUALITY_ID,
    build_aligned_tactic_proof,
)
from services.detector_quality import (  # noqa: E402
    QualitySurface,
    get_authorization,
    is_authorized,
)
from services.forced_mate_puzzle_proof import (  # noqa: E402
    FORCED_MATE_QUALITY_ID,
    build_forced_mate_proof,
)
from services.free_piece_puzzle_proof import (  # noqa: E402
    FREE_PIECE_QUALITY_ID,
    build_free_piece_proof,
)
from services.fork_puzzle_proof import (  # noqa: E402
    FORK_QUALITY_ID,
    build_fork_proof,
)
from services.move_observation_deriver import _classify_phase  # noqa: E402


SCHEMA_VERSION = "community_game_coherent_walkthrough_measurement.v1"
GENERATED_ON = "2026-09-15"
V2_PACKET_SHA256 = (
    "1d92050c950d3cfa2a17eae7b07208f2156096596b582f00254bef7b68def974"
)
EXPECTED_PREFIX_SHA256 = (
    "d8e9c900da9dbcd275a84e4fa08097fcca2c164ba183c04f2659929c10c8ab38"
)
EXPECTED_V2_CASES = 41
EXPECTED_V2_CHAPTERS = 110
PROOF_BUILDERS = (
    (
        FORCED_MATE_QUALITY_ID,
        lambda board, row: build_forced_mate_proof(
            board,
            str(row.get("move_uci") or ""),
            str(row.get("best_move_uci") or ""),
            tuple(row.get("pv_after_best") or ()),
            row.get("cp_loss"),
        ),
    ),
    (
        FORK_QUALITY_ID,
        lambda board, row: build_fork_proof(
            board,
            str(row.get("move_uci") or ""),
            str(row.get("best_move_uci") or ""),
            tuple(row.get("pv_after_best") or ()),
            row.get("cp_loss"),
        ),
    ),
    (
        ALIGNED_QUALITY_ID,
        lambda board, row: build_aligned_tactic_proof(
            board,
            str(row.get("move_uci") or ""),
            str(row.get("best_move_uci") or ""),
            tuple(row.get("pv_after_best") or ()),
            row.get("cp_loss"),
        ),
    ),
    (
        FREE_PIECE_QUALITY_ID,
        lambda board, row: build_free_piece_proof(
            board,
            str(row.get("move_uci") or ""),
            str(row.get("best_move_uci") or ""),
            row.get("cp_loss"),
        ),
    ),
)
FAMILY_PRIORITY = {
    "terminal:checkmate": 100,
    FORCED_MATE_QUALITY_ID: 90,
    FORK_QUALITY_ID: 80,
    ALIGNED_QUALITY_ID: 70,
    FREE_PIECE_QUALITY_ID: 60,
    "review:verified_single_game_cause": 20,
}


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _percentile(values: Sequence[int], fraction: float) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    index = round((len(ordered) - 1) * fraction)
    return int(ordered[index])


def _authorization(quality_id: str) -> dict[str, Any]:
    value = get_authorization(quality_id)
    return {
        "grade": value.grade.value,
        "caption_authorized": is_authorized(
            quality_id, QualitySurface.CAPTION
        ),
        "plan_authorized": is_authorized(quality_id, QualitySurface.PLAN),
        "evidence_ref": value.evidence_ref,
        "limitations": list(value.limitations),
    }


def _event_moment(event: Any, feature: Any, phase: str) -> dict[str, Any]:
    principle = str(event.teaching.principle or "").strip()
    quality_id = str(event.evidence.quality_id)
    return {
        "ply": int(event.move.ply),
        "phase": phase,
        "quality_ids": {quality_id},
        "concept_ids": {str(event.concept.concept_id)},
        "principle_keys": {
            "principle:" + _sha(principle)[:16]
            if principle
            else "quality:" + quality_id
        },
        "cp_loss": float(feature.cp_loss),
        "current_rank": (
            int(feature.decisiveness_changed),
            int(not feature.stayed_winning),
            int(bool(event.teaching.caption.strip()))
            + int(bool(principle))
            + int(
                bool(
                    event.teaching.visual.arrows
                    or event.teaching.visual.highlights
                    or event.teaching.visual.relationship_arrows
                )
            ),
            max(0.0, -float(feature.mover_winprob_delta)),
            float(feature.cp_loss),
            -int(event.move.ply),
        ),
        "sources": {"current_review_event"},
    }


def _proof_moment(row: Mapping[str, Any], quality_id: str) -> dict[str, Any]:
    ply = int(row["ply"])
    return {
        "ply": ply,
        "phase": _classify_phase(int(row["move_number"])),
        "quality_ids": {quality_id},
        "concept_ids": {"proof:" + quality_id},
        "principle_keys": {"quality:" + quality_id},
        "cp_loss": float(row.get("cp_loss") or 0),
        "current_rank": (0, 1, 3, 0.0, float(row.get("cp_loss") or 0), -ply),
        "sources": {"existing_caption_authorized_proof"},
    }


def _terminal_moment(game: chess.pgn.Game) -> Optional[dict[str, Any]]:
    board = game.board()
    moves = list(game.mainline_moves())
    for move in moves:
        board.push(move)
    if not board.is_checkmate() or not moves:
        return None
    ply = len(moves)
    return {
        "ply": ply,
        "phase": _classify_phase(board.fullmove_number),
        "quality_ids": {"terminal:checkmate"},
        "concept_ids": {"terminal.checkmate"},
        "principle_keys": {"terminal:checkmate"},
        "cp_loss": 0.0,
        "current_rank": (1, 1, 3, 0.0, 0.0, -ply),
        "sources": {"legal_terminal_replay"},
    }


def _merge_moments(values: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ply: dict[int, dict[str, Any]] = {}
    for value in values:
        ply = int(value["ply"])
        existing = by_ply.get(ply)
        if existing is None:
            by_ply[ply] = {
                **value,
                "quality_ids": set(value["quality_ids"]),
                "concept_ids": set(value["concept_ids"]),
                "principle_keys": set(value["principle_keys"]),
                "sources": set(value["sources"]),
            }
            continue
        for key in ("quality_ids", "concept_ids", "principle_keys", "sources"):
            existing[key].update(value[key])
        existing["cp_loss"] = max(existing["cp_loss"], value["cp_loss"])
        existing["current_rank"] = max(
            existing["current_rank"], value["current_rank"]
        )
    for moment in by_ply.values():
        moment["primary_family"] = max(
            moment["quality_ids"],
            key=lambda item: (FAMILY_PRIORITY.get(item, 10), item),
        )
        moment["primary_principle"] = (
            "quality:" + moment["primary_family"]
            if moment["primary_family"] in FAMILY_PRIORITY
            and moment["primary_family"]
            not in {"review:verified_single_game_cause"}
            else sorted(moment["principle_keys"])[0]
        )
    return sorted(by_ply.values(), key=lambda item: item["ply"])


def _current_ranked(moments: Sequence[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    current = [
        moment
        for moment in moments
        if "current_review_event" in moment["sources"]
    ]
    return sorted(
        sorted(current, key=lambda item: item["current_rank"], reverse=True)[:cap],
        key=lambda item: item["ply"],
    )


def _severity_ranked(moments: Sequence[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    return sorted(
        sorted(
            moments,
            key=lambda item: (item["cp_loss"], -item["ply"]),
            reverse=True,
        )[:cap],
        key=lambda item: item["ply"],
    )


def _coherent_ranked(moments: Sequence[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    """Role-first selection using no fitted numeric weights."""
    if not moments or cap < 1:
        return []
    selected: list[dict[str, Any]] = []

    terminal = next(
        (
            item
            for item in reversed(moments)
            if item["primary_family"] == "terminal:checkmate"
        ),
        None,
    )
    # Reuse the current verified Review quality order for importance.  Raw
    # engine swing is only its final tie-breaker, never the story objective.
    climax = max(moments, key=lambda item: item["current_rank"])
    selected.append(climax)
    if terminal is not None and terminal not in selected and len(selected) < cap:
        selected.append(terminal)

    def novelty(item: dict[str, Any]) -> tuple[int, int]:
        principles = {value["primary_principle"] for value in selected}
        phases = {value["phase"] for value in selected}
        return (
            int(item["primary_principle"] not in principles),
            int(item["phase"] not in phases),
        )

    before = [item for item in moments if item["ply"] < climax["ply"]]
    if before and len(selected) < cap:
        setup = max(
            before,
            key=lambda item: (
                novelty(item),
                -item["ply"],
                item["current_rank"],
            ),
        )
        if setup not in selected:
            selected.append(setup)

    after = [item for item in moments if item["ply"] > climax["ply"]]
    if after and len(selected) < cap:
        finish = max(
            after,
            key=lambda item: (
                novelty(item),
                item["ply"],
                item["current_rank"],
            ),
        )
        if finish not in selected:
            selected.append(finish)

    while len(selected) < min(cap, len(moments)):
        remaining = [item for item in moments if item not in selected]
        if not remaining:
            break
        selected.append(
            max(
                remaining,
                key=lambda item: (
                    novelty(item),
                    item["current_rank"],
                ),
            )
        )
    return sorted(selected, key=lambda item: item["ply"])


def _formula_metrics(
    games: Sequence[dict[str, Any]],
    chooser: Callable[[Sequence[dict[str, Any]], int], list[dict[str, Any]]],
    cap: int,
) -> dict[str, Any]:
    rows = []
    for game in games:
        selected = chooser(game["moments"], cap)
        if len(selected) < 2:
            continue
        principles = [item["primary_principle"] for item in selected]
        phases = {item["phase"] for item in selected}
        terminal = any(
            item["primary_family"] == "terminal:checkmate" for item in selected
        )
        finish = terminal or max(item["ply"] for item in selected) * 4 >= (
            game["total_plies"] * 3
        )
        rows.append(
            {
                "chapter_count": len(selected),
                "distinct_principles": len(set(principles)),
                "distinct_phases": len(phases),
                "repeated_principle_chapters": len(principles)
                - len(set(principles)),
                "finish": finish,
                "terminal": terminal,
                "checkmate": game["checkmate"],
            }
        )
    if not rows:
        return {"eligible_games": 0}
    mate_rows = [row for row in rows if row["checkmate"]]
    return {
        "eligible_games": len(rows),
        "mean_chapters": round(
            statistics.mean(row["chapter_count"] for row in rows), 3
        ),
        "games_with_two_or_more_principles": sum(
            row["distinct_principles"] >= 2 for row in rows
        ),
        "games_with_two_or_more_phases": sum(
            row["distinct_phases"] >= 2 for row in rows
        ),
        "games_reaching_final_quarter_or_terminal": sum(
            row["finish"] for row in rows
        ),
        "repeated_principle_chapters": sum(
            row["repeated_principle_chapters"] for row in rows
        ),
        "checkmate_games": len(mate_rows),
        "checkmate_games_with_terminal_chapter": sum(
            row["terminal"] for row in mate_rows
        ),
    }


def build_measurement(
    *,
    source_path: Path,
    release_id: str,
    release_sha256: str,
    fetch_limit: int,
    maximum_source_bytes: int,
    fetcher: Callable[[str], str] = fetch_literate_game,
    request_delay_seconds: float = 0.15,
) -> dict[str, Any]:
    if _file_sha256(source_path) != EXPECTED_PREFIX_SHA256:
        raise PacketBuildError("source prefix does not match the frozen v2 population")

    counters: Counter[str] = Counter()
    family_fires: Counter[str] = Counter()
    family_games: dict[str, set[str]] = defaultdict(set)
    family_unique_moments: Counter[str] = Counter()
    family_current_overlap: Counter[str] = Counter()
    family_new_moments: Counter[str] = Counter()
    family_newly_eligible_games: Counter[str] = Counter()
    overlap: Counter[str] = Counter()
    games: list[dict[str, Any]] = []
    source_replays: list[str] = []
    seen_replays: set[str] = set()

    for monthly_game in _read_source_games(
        source_path, maximum_bytes=maximum_source_bytes
    ):
        counters["source_games_parsed"] += 1
        candidate = _source_candidate(monthly_game)
        if candidate is None:
            continue
        counters["source_candidates"] += 1
        replay_sha = str(candidate["replay_fingerprint"])
        if replay_sha in seen_replays:
            counters["duplicate_replays"] += 1
            continue
        if counters["literate_exports_requested"] >= fetch_limit:
            break
        seen_replays.add(replay_sha)
        counters["literate_exports_requested"] += 1
        literate = chess.pgn.read_game(
            io.StringIO(fetcher(str(candidate["source_game_id"])))
        )
        if literate is None or literate.errors:
            counters["invalid_literate_export"] += 1
            continue
        if _moves_uci(literate) != list(candidate["moves_uci"]):
            counters["monthly_and_literate_replay_disagree"] += 1
            continue

        rows = rows_from_literate_game(literate)
        anonymous_game_id = _anonymous_game_id(replay_sha)
        source_replays.append(replay_sha)
        try:
            ratings = {
                "white": int(literate.headers.get("WhiteElo") or 0),
                "black": int(literate.headers.get("BlackElo") or 0),
            }
        except (TypeError, ValueError):
            counters["literate_export_missing_ratings"] += 1
            continue

        moment_values: list[dict[str, Any]] = []
        current_quality_ids: set[str] = set()
        for color in ("white", "black"):
            events, features, event_rows, errors = _events_for_color(
                game=literate,
                rows=rows,
                anonymous_game_id=anonymous_game_id,
                user_color=color,
                user_rating=ratings[color],
            )
            counters["pipeline_errors"] += len(errors)
            for event in events:
                quality_id = str(event.evidence.quality_id)
                if not event.player_authorized:
                    continue
                current_quality_ids.add(quality_id)
                context = event_rows[event.event_id]
                moment_values.append(
                    _event_moment(event, features[event.event_id], context["phase"])
                )
                family_fires[quality_id] += 1
                family_games[quality_id].add(replay_sha)

        row_family_sets: list[set[str]] = []
        tablebase_eligible = 0
        for row in rows:
            board = chess.Board(str(row["fen_before"]))
            if len(board.piece_map()) <= 7 and not board.is_game_over():
                tablebase_eligible += 1
            row_families: set[str] = set()
            if row.get("best_move_uci"):
                for quality_id, builder in PROOF_BUILDERS:
                    bundle = builder(board, row)
                    if (
                        bundle is None
                        or not bundle.verifier.verified
                        or not is_authorized(quality_id, QualitySurface.CAPTION)
                    ):
                        continue
                    row_families.add(quality_id)
                    moment_values.append(_proof_moment(row, quality_id))
                    family_fires[quality_id] += 1
                    family_games[quality_id].add(replay_sha)
            if row_families:
                row_family_sets.append(row_families)
                for left in sorted(row_families):
                    for right in sorted(row_families):
                        if left < right:
                            overlap[f"{left}|{right}"] += 1

        terminal = _terminal_moment(literate)
        if terminal is not None:
            moment_values.append(terminal)
            family_fires["terminal:checkmate"] += 1
            family_games["terminal:checkmate"].add(replay_sha)

        moments = _merge_moments(moment_values)
        current_moment_count = sum(
            "current_review_event" in item["sources"] for item in moments
        )
        measured_families = (
            set().union(*(item["quality_ids"] for item in moments))
            if moments
            else set()
        )
        for quality_id in measured_families:
            family_moments = [
                item for item in moments if quality_id in item["quality_ids"]
            ]
            family_unique_moments[quality_id] += len(family_moments)
            overlap_count = sum(
                "current_review_event" in item["sources"]
                for item in family_moments
            )
            family_current_overlap[quality_id] += overlap_count
            family_new_moments[quality_id] += len(family_moments) - overlap_count
            with_family_count = sum(
                "current_review_event" in item["sources"]
                or quality_id in item["quality_ids"]
                for item in moments
            )
            if current_moment_count < 2 <= with_family_count:
                family_newly_eligible_games[quality_id] += 1
        games.append(
            {
                "game_key": _sha("story-measurement:" + replay_sha)[:20],
                "replay_sha256": replay_sha,
                "rating_band": str(candidate["rating_band"]),
                "total_plies": len(list(literate.mainline_moves())),
                "checkmate": bool(terminal),
                "current_event_count": current_moment_count,
                "combined_moment_count": len(moments),
                "distinct_primary_principles": len(
                    {item["primary_principle"] for item in moments}
                ),
                "distinct_primary_families": len(
                    {item["primary_family"] for item in moments}
                ),
                "tablebase_eligible_positions_without_pinned_evidence": (
                    tablebase_eligible
                ),
                "moments": moments,
                "current_quality_ids": sorted(current_quality_ids),
            }
        )
        if request_delay_seconds:
            time.sleep(request_delay_seconds)

    total_plies = [game["total_plies"] for game in games]
    current_counts = [game["current_event_count"] for game in games]
    combined_counts = [game["combined_moment_count"] for game in games]
    current_admitted = sum(value >= 2 for value in current_counts)
    current_chapters = sum(min(value, 3) for value in current_counts if value >= 2)
    if current_admitted != EXPECTED_V2_CASES or current_chapters != EXPECTED_V2_CHAPTERS:
        raise PacketBuildError(
            "current runtime no longer reproduces the frozen v2 case/chapter counts: "
            f"{current_admitted}/{current_chapters}"
        )

    formula_comparison: dict[str, Any] = {}
    for cap in (2, 3, 4, 5):
        formula_comparison[f"current_rank_cap_{cap}"] = _formula_metrics(
            games, _current_ranked, cap
        )
        formula_comparison[f"combined_severity_cap_{cap}"] = _formula_metrics(
            games, _severity_ranked, cap
        )
        formula_comparison[f"combined_role_first_cap_{cap}"] = _formula_metrics(
            games, _coherent_ranked, cap
        )

    quality_ids = sorted(
        set(family_fires)
        | {
            FORCED_MATE_QUALITY_ID,
            FORK_QUALITY_ID,
            ALIGNED_QUALITY_ID,
            FREE_PIECE_QUALITY_ID,
            "review:exact_endgame_result_change",
            "curriculum:opening_exact_decision",
            "curriculum:opening_exact_position",
        }
    )
    public_games = []
    for game in games:
        public_games.append(
            {
                key: value
                for key, value in game.items()
                if key not in {"moments", "replay_sha256"}
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_on": GENERATED_ON,
        "status": "precode_data_lock_measurement",
        "runtime_exposure": "none",
        "source": {
            "provider": "lichess_open_database",
            "license": "CC0-1.0",
            "release_id": release_id,
            "release_sha256": release_sha256,
            "local_prefix_sha256": _file_sha256(source_path),
            "local_prefix_bytes": source_path.stat().st_size,
            "v2_packet_sha256": V2_PACKET_SHA256,
            "raw_identity_bearing_pgn_retained": False,
        },
        "execution": {
            "production_database_reads": 0,
            "production_database_writes": 0,
            "stockfish_runs": 0,
            "fathom_or_tablebase_probes": 0,
            "llm_or_model_calls": 0,
            "player_visible_changes": 0,
            "public_literate_exports_requested": counters[
                "literate_exports_requested"
            ],
        },
        "population": {
            "games": len(games),
            "current_v2_eligible_games": current_admitted,
            "current_v2_chapters": current_chapters,
            "checkmate_games": sum(game["checkmate"] for game in games),
            "game_length_plies": {
                "minimum": min(total_plies),
                "p25": _percentile(total_plies, 0.25),
                "median": _percentile(total_plies, 0.5),
                "p75": _percentile(total_plies, 0.75),
                "maximum": max(total_plies),
            },
            "current_event_count": {
                "minimum": min(current_counts),
                "p25": _percentile(current_counts, 0.25),
                "median": _percentile(current_counts, 0.5),
                "p75": _percentile(current_counts, 0.75),
                "maximum": max(current_counts),
            },
            "combined_moment_count": {
                "minimum": min(combined_counts),
                "p25": _percentile(combined_counts, 0.25),
                "median": _percentile(combined_counts, 0.5),
                "p75": _percentile(combined_counts, 0.75),
                "maximum": max(combined_counts),
            },
            "tablebase_eligible_positions_without_pinned_evidence": sum(
                game["tablebase_eligible_positions_without_pinned_evidence"]
                for game in games
            ),
        },
        "family_incidence": {
            quality_id: {
                "verified_fires": family_fires[quality_id],
                "games": len(family_games[quality_id]),
                "unique_moments": family_unique_moments[quality_id],
                "overlap_with_current_review_moments": (
                    family_current_overlap[quality_id]
                ),
                "new_moments_beyond_current_review": family_new_moments[
                    quality_id
                ],
                "newly_eligible_games_if_only_this_family_is_added": (
                    family_newly_eligible_games[quality_id]
                ),
                "authorization": _authorization(quality_id)
                if not quality_id.startswith("terminal:")
                else {
                    "grade": "board_terminal_fact",
                    "caption_authorized": False,
                    "plan_authorized": False,
                    "evidence_ref": "legal full-game replay",
                    "limitations": [
                        "Incidence only; a player-visible finish still requires an admitted central Review fact."
                    ],
                },
            }
            for quality_id in quality_ids
        },
        "proof_family_overlap_by_position": dict(sorted(overlap.items())),
        "formula_comparison": formula_comparison,
        "game_level_measurement": public_games,
        "reproducibility": {
            "source_replay_population_fingerprint_sha256": _sha(
                "|".join(sorted(source_replays))
            ),
            "measurement_fingerprint_sha256": _sha(
                json.dumps(
                    {
                        "family_fires": dict(sorted(family_fires.items())),
                        "formula_comparison": formula_comparison,
                        "games": public_games,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
        },
        "notes": [
            "Existing exact endgame result-change authority was recorded but not fired because this machine has no pinned Fathom/Syzygy bundle; eligible positions are counted, never inferred.",
            "Exact opening families are Shadow and therefore measured as unauthorized with zero player-facing contribution.",
            "Terminal checkmate is measured as a legal replay fact only; it is not treated as Caption-authorized until a central Review fact contract admits it.",
            "Combined formula rows measure candidate supply and ordering, not caption quality or rollout authority.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zst", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--release-sha256", required=True)
    parser.add_argument("--fetch-limit", type=int, default=60)
    parser.add_argument("--maximum-source-bytes", type=int, default=16 * 1024 * 1024)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = build_measurement(
        source_path=args.source_zst.resolve(),
        release_id=args.release_id,
        release_sha256=args.release_sha256,
        fetch_limit=args.fetch_limit,
        maximum_source_bytes=args.maximum_source_bytes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "population": packet["population"],
                "family_incidence": packet["family_incidence"],
                "formula_comparison": packet["formula_comparison"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
