"""Read-only production evidence lock for Game Review Quality V2.

The script uses stored engine/V5 evidence and legal-board verification only.
It performs no engine runs, LLM calls, or database writes. Output is aggregate
except for the already-approved Bh6 regression fixture.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
from typing import Any, Iterable, Mapping

import chess
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quick_tag_registry import generate_quick_tags
from reflect_predicates import BoardFacts
from services.caption_facts import legally_hanging_pieces
from services.detector_quality import gap_quality_id, grade_for


REFERENCE_GAME_ID = "100897b9-0989-47db-b114-fe7064cecd4d"
REFERENCE_MOVE_NUMBER = 25
SCHEMA_MIN = 16


def _chunks(values: list[str], size: int = 300) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _percent(part: int, whole: int) -> float | None:
    return round(100.0 * part / whole, 2) if whole else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return round(ordered[lower] * (1 - fraction) + ordered[upper] * fraction, 3)


def _position_key(fen: str) -> str:
    return " ".join(str(fen or "").split()[:4])


def _parse_san(board: chess.Board, san: str) -> chess.Move | None:
    try:
        return board.parse_san(str(san or ""))
    except (ValueError, AssertionError):
        return None


def _piece_label(piece: chess.Piece | None) -> str | None:
    return chess.piece_name(piece.piece_type) if piece else None


def _king_ring(board: chess.Board, color: chess.Color) -> set[int]:
    king = board.king(color)
    return set(chess.SquareSet(chess.BB_KING_ATTACKS[king])) if king is not None else set()


def _purpose_facts(fen: str, played_san: str) -> dict[str, bool]:
    try:
        board = chess.Board(fen)
    except ValueError:
        return {}
    move = _parse_san(board, played_san)
    if move is None:
        return {}
    piece = board.piece_at(move.from_square)
    opponent = not board.turn
    was_capture = board.is_capture(move)
    board.push(move)
    moved_piece = board.piece_at(move.to_square)
    ring = _king_ring(board, opponent)
    attacks_ring = bool(moved_piece and set(board.attacks(move.to_square)) & ring)
    home_squares = {
        chess.B1, chess.G1, chess.C1, chess.F1,
        chess.B8, chess.G8, chess.C8, chess.F8,
    }
    develops = bool(
        piece
        and piece.piece_type in {chess.KNIGHT, chess.BISHOP}
        and move.from_square in home_squares
    )
    attacks_piece = any(
        board.piece_at(square)
        and board.piece_at(square).color == opponent
        for square in board.attacks(move.to_square)
    )
    return {
        "gives_check": board.is_check(),
        "captures": was_capture,
        "develops": develops,
        "pressures_king_ring": attacks_ring,
        "attacks_opponent_piece": attacks_piece,
    }


def _simple_hang_cause(row: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild the concrete loose piece with canonical legal-exchange truth."""
    fen = str(row.get("fen_before") or "")
    try:
        before = chess.Board(fen)
    except ValueError:
        return {"verified": False, "reason": "invalid_fen"}
    played = _parse_san(before, str(row.get("move_san") or ""))
    best = _parse_san(before, str(row.get("best_move_san") or ""))
    if played is None or best is None:
        return {"verified": False, "reason": "invalid_move"}

    player = before.turn
    opponent = not player
    after_played = before.copy()
    after_played.push(played)
    hanging = legally_hanging_pieces(after_played, player, 150)
    if not hanging:
        return {"verified": False, "reason": "no_legal_exchange_hang"}
    target_fact = hanging[0]
    target_square = chess.parse_square(str(target_fact["square"]))
    target = after_played.piece_at(target_square)
    reply_uci = str(target_fact.get("winning_capture_uci") or "")
    try:
        reply = chess.Move.from_uci(reply_uci)
    except ValueError:
        return {"verified": False, "reason": "no_legal_winning_capture"}
    if reply not in after_played.legal_moves or not after_played.is_capture(reply):
        return {"verified": False, "reason": "no_legal_winning_capture"}
    attacker = after_played.piece_at(reply.from_square)
    if not target or target.color != player or not attacker or attacker.color != opponent:
        return {"verified": False, "reason": "winning_capture_identity_error"}

    after_best = before.copy()
    best_is_capture = before.is_capture(best)
    captured_by_best = before.piece_at(best.to_square) if best_is_capture else None
    after_best.push(best)
    hanging_after_best = legally_hanging_pieces(after_best, player, 150)
    hanging_squares_after_best = {str(item.get("square") or "") for item in hanging_after_best}
    best_purpose = None
    if (
        best.from_square == target_square
        and chess.square_name(best.to_square) not in hanging_squares_after_best
    ):
        best_purpose = "moves_affected_piece"
    elif (
        captured_by_best
        and best.to_square == reply.from_square
        and chess.square_name(target_square) not in hanging_squares_after_best
    ):
        best_purpose = "removes_attacker"
    elif (
        chess.square_name(target_square) not in hanging_squares_after_best
        and best.to_square in after_best.attackers(player, target_square)
    ):
        best_purpose = "adds_defender"

    return {
        "verified": True,
        "affected_piece": _piece_label(target),
        "affected_square": chess.square_name(target_square),
        "attacker_piece": _piece_label(attacker),
        "attacker_square": chess.square_name(reply.from_square),
        "punishment_san": str(target_fact.get("winning_capture_san") or ""),
        "material_loss_cp": int(target_fact.get("material_loss_cp") or 0),
        "best_move_san": str(row.get("best_move_san") or ""),
        "best_move_purpose": best_purpose,
        "best_move_purpose_verified": best_purpose is not None,
    }


def _row_for_observation(rows: list[dict[str, Any]], observation: Mapping[str, Any]) -> dict[str, Any] | None:
    move_number = int(observation.get("move_number") or 0)
    san = str(observation.get("move_san") or "")
    candidates = [
        row for row in rows
        if row.get("is_user_move") is True
        and int(row.get("move_number") or 0) == move_number
    ]
    exact = [row for row in candidates if str(row.get("move_san") or "") == san]
    return (exact or candidates or [None])[0]


def _teaching_completeness(row: Mapping[str, Any]) -> int:
    event = row.get("teachable_event") or {}
    teaching = event.get("teaching") or {}
    visual = teaching.get("visual") or {}
    return sum((
        bool(str(teaching.get("caption") or "").strip()),
        bool(str(teaching.get("principle") or "").strip()),
        bool(visual.get("arrows") or visual.get("highlights")),
    ))


def _ranking_key(row: Mapping[str, Any], formula: str) -> tuple[Any, ...]:
    complete = _teaching_completeness(row)
    cp_loss = float(row.get("cp_loss") or 0)
    move_number = int(row.get("move_number") or 0)
    transition = int(bool(row.get("decisiveness_changed")))
    did_not_stay_winning = int(not bool(row.get("stayed_winning")))
    winprob_loss = max(0.0, -float(row.get("mover_winprob_delta") or 0.0))
    if formula == "D_teaching_then_critical":
        return (complete, 1, cp_loss, -move_number)
    if formula == "E_transition_then_teaching":
        return (transition, did_not_stay_winning, complete, winprob_loss, cp_loss, -move_number)
    if formula == "F_teaching_then_transition":
        return (complete, transition, did_not_stay_winning, winprob_loss, cp_loss, -move_number)
    raise ValueError(formula)


def main() -> None:
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    observations = list(db.move_observations.find(
        {"schema_version": {"$gte": SCHEMA_MIN}, "subtype": "simple_hang"},
        {"_id": 0, "user_id": 0},
    ))
    game_ids = sorted({str(item.get("game_id") or "") for item in observations if item.get("game_id")})
    analyses: dict[str, list[dict[str, Any]]] = {}
    for batch in _chunks(game_ids):
        for doc in db.game_analyses.find(
            {"game_id": {"$in": batch}},
            {"_id": 0, "game_id": 1, "decryption_v5_data": 1},
        ):
            analyses[str(doc.get("game_id") or "")] = list(doc.get("decryption_v5_data") or [])

    joined: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, bool], list[str]]] = []
    join_failures = Counter()
    for observation in observations:
        rows = analyses.get(str(observation.get("game_id") or ""))
        if not rows:
            join_failures["missing_v5_game"] += 1
            continue
        row = _row_for_observation(rows, observation)
        if not row:
            join_failures["missing_v5_move"] += 1
            continue
        cause = _simple_hang_cause(row)
        purposes = _purpose_facts(str(row.get("fen_before") or ""), str(row.get("move_san") or ""))
        try:
            tags = generate_quick_tags(
                fen_before=str(row.get("fen_before") or ""),
                user_move=str(row.get("move_san") or ""),
                best_move=str(row.get("best_move_san") or ""),
                mistake_category="missed_forcing_move",
                rating=1200,
                cp_loss=float(row.get("cp_loss") or 0),
                move_number=int(row.get("move_number") or 0),
                include_honest_escapes=True,
            )
            tag_ids = [str(item.get("id") or "") for item in tags.get("tags") or []]
        except Exception:
            tag_ids = []
            join_failures["quick_tag_error"] += 1
        joined.append((observation, row, cause, purposes, tag_ids))

    total = len(joined)
    cause_counts = Counter()
    reflection_counts = Counter()
    practical_counts = Counter()
    mismatch_counts = Counter()
    cp_losses: list[float] = []
    winprob_losses: list[float] = []
    reference = None
    by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation, row, cause, purposes, tag_ids in joined:
        cp_losses.append(float(row.get("cp_loss") or 0))
        winprob_losses.append(max(0.0, -float(row.get("mover_winprob_delta") or 0.0)))
        practical_counts[f"state:{row.get('mover_state_before')}->{row.get('mover_state_after')}"] += 1
        practical_counts["stayed_winning"] += int(bool(row.get("stayed_winning")))
        practical_counts["decisiveness_changed"] += int(bool(row.get("decisiveness_changed")))
        practical_counts[f"severity:{row.get('severity_practical')}"] += 1
        cause_counts["verified"] += int(bool(cause.get("verified")))
        cause_counts["best_move_purpose_verified"] += int(bool(cause.get("best_move_purpose_verified")))
        if cause.get("verified"):
            cause_counts[f"best_purpose:{cause.get('best_move_purpose') or 'unproved'}"] += 1
        else:
            cause_counts[f"failure:{cause.get('reason') or 'unknown'}"] += 1
        for purpose, present in purposes.items():
            reflection_counts[f"purpose:{purpose}"] += int(present)
        has_attack_option = bool({"chose_attack_over_safety", "attacked_ignored_threat"} & set(tag_ids))
        reflection_counts["current_attack_option_shown"] += int(has_attack_option)
        board_attack_intent = bool(purposes.get("pressures_king_ring") or purposes.get("attacks_opponent_piece"))
        reflection_counts["board_possible_attack_intent"] += int(board_attack_intent)
        reflection_counts["attack_option_coverage_gap"] += int(board_attack_intent and not has_attack_option)

        explanation = row.get("caption_explanation") or {}
        provenance = [str(item) for item in explanation.get("provenance") or []]
        caption = str(explanation.get("board_explanation") or row.get("caption") or "")
        facts = BoardFacts(
            str(row.get("fen_before") or ""),
            str(row.get("move_san") or ""),
            str(row.get("best_move_san") or ""),
            float(row.get("cp_loss") or 0),
            move_number=int(row.get("move_number") or 0),
        )
        missed_mate = any(item == "distilled:missed_mate" for item in provenance)
        wrong_forcing_claim = missed_mate and not (facts.best_move_gives_check or facts.best_move_is_capture)
        mismatch_counts["distilled_missed_mate"] += int(missed_mate)
        mismatch_counts["missed_mate_best_not_check_or_capture"] += int(wrong_forcing_claim)
        mismatch_counts["caption_mentions_forcing_or_checks"] += int(
            "forcing move" in caption.lower() or "checks and forcing" in caption.lower()
        )
        mismatch_counts["forcing_language_without_best_check_or_capture"] += int(
            ("forcing move" in caption.lower() or "checks and forcing" in caption.lower())
            and not (facts.best_move_gives_check or facts.best_move_is_capture)
        )

        game_id = str(observation.get("game_id") or "")
        by_game[game_id].append(row)
        if game_id == REFERENCE_GAME_ID and int(row.get("move_number") or 0) == REFERENCE_MOVE_NUMBER:
            reference = {
                "move": row.get("move_san"),
                "best_move": row.get("best_move_san"),
                "cause": cause,
                "purposes": purposes,
                "current_reflection_option_ids": tag_ids,
                "practical": {
                    "before": row.get("mover_state_before"),
                    "after": row.get("mover_state_after"),
                    "stayed_winning": row.get("stayed_winning"),
                    "decisiveness_changed": row.get("decisiveness_changed"),
                    "winprob_delta": row.get("mover_winprob_delta"),
                },
                "current_rule": row.get("rule_name"),
                "current_visual": (row.get("teachable_event") or {}).get("teaching", {}).get("visual"),
            }

    formulas = ["D_teaching_then_critical", "E_transition_then_teaching", "F_teaching_then_transition"]
    selections: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in formulas}
    ranking_metrics: dict[str, dict[str, Any]] = {}
    multi_event_games = {game_id: rows for game_id, rows in by_game.items() if len(rows) > 1}
    for formula in formulas:
        picks = []
        for game_id, rows in multi_event_games.items():
            pick = max(rows, key=lambda row: _ranking_key(row, formula))
            selections[formula][game_id] = {
                "move_number": int(pick.get("move_number") or 0),
                "stayed_winning": bool(pick.get("stayed_winning")),
                "decisiveness_changed": bool(pick.get("decisiveness_changed")),
                "winprob_loss": max(0.0, -float(pick.get("mover_winprob_delta") or 0.0)),
            }
            picks.append(pick)
        ranking_metrics[formula] = {
            "games": len(picks),
            "selected_stayed_winning_pct": _percent(sum(bool(p.get("stayed_winning")) for p in picks), len(picks)),
            "selected_decisiveness_changed_pct": _percent(sum(bool(p.get("decisiveness_changed")) for p in picks), len(picks)),
            "mean_selected_winprob_loss": round(statistics.mean(max(0.0, -float(p.get("mover_winprob_delta") or 0.0)) for p in picks), 4) if picks else None,
            "mean_selected_cp_loss": round(statistics.mean(float(p.get("cp_loss") or 0) for p in picks), 2) if picks else None,
        }
    ranking_disagreement = {}
    for i, left in enumerate(formulas):
        for right in formulas[i + 1:]:
            common = sorted(set(selections[left]) & set(selections[right]))
            different = sum(selections[left][gid]["move_number"] != selections[right][gid]["move_number"] for gid in common)
            ranking_disagreement[f"{left}__vs__{right}"] = {
                "common_games": len(common),
                "different_top_event_pct": _percent(different, len(common)),
            }

    pipeline = [
        {"$match": {"schema_version": {"$gte": SCHEMA_MIN}, "missed_pattern": {"$ne": None}}},
        {"$group": {
            "_id": {"pattern": "$missed_pattern", "subtype": "$subtype"},
            "observations": {"$sum": 1},
            "games": {"$addToSet": "$game_id"},
            "users": {"$addToSet": "$user_id"},
        }},
    ]
    candidates = []
    for item in db.move_observations.aggregate(pipeline, allowDiskUse=True):
        pattern = str((item.get("_id") or {}).get("pattern") or "")
        subtype = str((item.get("_id") or {}).get("subtype") or "")
        quality_id = gap_quality_id(pattern, subtype or None)
        candidates.append({
            "quality_id": quality_id,
            "grade": grade_for(quality_id).value,
            "observations": int(item.get("observations") or 0),
            "games": len(item.get("games") or []),
            "users": len(item.get("users") or []),
        })
    candidates.sort(key=lambda item: (item["grade"] != "shadow", -item["games"], -item["users"], item["quality_id"]))

    identity_present = db.move_observations.count_documents({
        "schema_version": {"$gte": SCHEMA_MIN},
        "$or": [
            {"deriver_identity": {"$exists": True}},
            {"deriver_version": {"$exists": True}},
            {"deriver_hash": {"$exists": True}},
        ],
    })
    current_schema_count = db.move_observations.count_documents({"schema_version": {"$gte": SCHEMA_MIN}})

    def count_block(counter: Counter[str]) -> dict[str, dict[str, Any]]:
        return {
            key: {"count": int(value), "pct_of_joined": _percent(int(value), total)}
            for key, value in sorted(counter.items())
        }

    script_hash = os.environ.get("MEASUREMENT_SCRIPT_SHA256")
    if not script_hash:
        script_path = Path(__file__)
        script_hash = (
            hashlib.sha256(script_path.read_bytes()).hexdigest()
            if script_path.exists()
            else "unavailable"
        )
    output = {
        "schema_version": "personalized_game_review_quality_v2.data_lock.v1",
        "generated_at": date.today().isoformat(),
        "read_only": True,
        "engine_runs": 0,
        "llm_calls": 0,
        "database_writes": 0,
        "privacy": {
            "aggregate_only_except_approved_regression": True,
            "contains_user_ids": False,
            "contains_credentials": False,
        },
        "counts": {
            "simple_hang_observations": len(observations),
            "games": len(game_ids),
            "joined_v5_events": total,
            "join_failures": dict(sorted(join_failures.items())),
            "multi_event_games": len(multi_event_games),
        },
        "cause_verification": count_block(cause_counts),
        "reflection_purpose_coverage": count_block(reflection_counts),
        "practical_state": count_block(practical_counts),
        "caption_cause_conflicts": count_block(mismatch_counts),
        "distributions": {
            "cp_loss": {"p25": _percentile(cp_losses, .25), "median": _percentile(cp_losses, .5), "p75": _percentile(cp_losses, .75), "p90": _percentile(cp_losses, .9)},
            "winprob_loss": {"p25": _percentile(winprob_losses, .25), "median": _percentile(winprob_losses, .5), "p75": _percentile(winprob_losses, .75), "p90": _percentile(winprob_losses, .9)},
        },
        "moment_ranking_bakeoff": {
            "population": "games with at least two joined current-schema simple_hang events",
            "candidate_metrics": ranking_metrics,
            "pairwise_disagreement": ranking_disagreement,
            "final_formula_locked": False,
            "reason_not_locked": "No independent human importance labels exist for this population; candidates must enter blinded validation rather than be promoted by proxy metrics.",
        },
        "deriver_identity": {
            "current_schema_observations": current_schema_count,
            "observations_with_any_explicit_deriver_identity": identity_present,
            "coverage_pct": _percent(identity_present, current_schema_count),
        },
        "detector_promotion_candidates": {
            "ranking_rule": "shadow grade, then games reached, then users reached; quality evidence still controls promotion",
            "top_20": candidates[:20],
        },
        "approved_reference_regression": reference,
        "locks": {
            "ranking": "Keep the deployed ranking for visible V1; measure practical-state candidates in validation because proxy metrics cannot establish coaching importance.",
            "practical_framing": "Use mover_state_before/after, decisiveness_changed, stayed_winning, and mover_winprob_delta; raw cp_loss never supplies turning-point language by itself.",
            "reflection": "Offer only independently board-possible purposes plus not_sure and none_of_these; self-report does not mutate board truth.",
            "cause": "A simple_hang visible cause requires a legal stored-PV capture of the exact undefended player piece; each named square and piece is rebuilt from the board.",
            "best_move_purpose": "Name a best-move purpose only when it moves the affected piece, removes the exact attacker, or adds a defender; otherwise abstain.",
            "deriver_identity": "Use a versioned manifest hash covering detector implementation plus semantic dependencies, stored alongside the human-readable semantic version.",
        },
        "provenance": {"measurement_script_sha256": script_hash},
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
