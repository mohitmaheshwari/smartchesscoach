"""Build the independent Caption packet for tactic:free_piece_exact.

The candidate and the gold take different paths:

* candidate truth is the existing canonical proof bundle;
* gold truth is rebuilt below from legal board state without calling that
  detector, its verifier, or the stored verdict.

The script reads stored Stockfish results and puzzle admissions. It never runs
an engine, writes to Mongo, or emits user/game/account identity.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
import math
import os
from typing import Any, Dict, Iterable, Mapping, Optional

import chess
from pymongo import MongoClient


SCHEMA_VERSION = "free_piece_exact.caption_promotion.v1"
QUALITY_ID = "tactic:free_piece_exact"
SEED = "20260902-free-piece-caption-v1"
POSITIVE_TARGET = 50
NEGATIVE_TARGET = 20
NEGATIVE_PER_STRATUM = 5
CP_LOSS_FLOOR = 100
TARGET_VALUE_FLOOR = 300
POOLS = ("community_puzzles", "community_training_positions")
NEGATIVE_STRATA = (
    "immediate_recapture",
    "lower_value_target",
    "non_capture",
    "insufficient_consequence",
)
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
PROJECTION = {
    "_id": 0,
    "fen": 1,
    "best_move_uci": 1,
    "best_move_san": 1,
    "played_move": 1,
    "user_move": 1,
    "move": 1,
    "user_move_uci": 1,
    "user_move_san": 1,
    "cp_loss": 1,
    "source": 1,
    "verified_admission": 1,
    "source_game_id": 1,
    "game_id": 1,
    "position_id": 1,
}


def _hash(value: object, *, namespace: str, length: int = 20) -> str:
    return hashlib.sha256(
        f"{namespace}\x1f{value}".encode("utf-8")
    ).hexdigest()[:length]


def _parse_move(board: chess.Board, raw: Any) -> Optional[chess.Move]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    token = raw.strip()
    try:
        move = chess.Move.from_uci(token.lower())
        return move if move in board.legal_moves else None
    except ValueError:
        pass
    try:
        return board.parse_san(token)
    except (ValueError, AssertionError):
        return None


def _moves(
    row: Mapping[str, Any],
) -> tuple[
    Optional[chess.Board],
    Optional[chess.Move],
    Optional[chess.Move],
]:
    try:
        board = chess.Board(str(row.get("fen") or ""))
    except (TypeError, ValueError):
        return None, None, None
    best = _parse_move(
        board, row.get("best_move_uci") or row.get("best_move_san")
    )
    played = _parse_move(
        board,
        row.get("played_move")
        or row.get("user_move")
        or row.get("move")
        or row.get("user_move_uci")
        or row.get("user_move_san"),
    )
    return board, played, best


def _cp_loss(row: Mapping[str, Any]) -> Optional[float]:
    value = row.get("cp_loss")
    if isinstance(value, bool):
        return None
    try:
        loss = float(value)
    except (TypeError, ValueError):
        return None
    return loss if math.isfinite(loss) and loss >= 0 else None


def independent_gold(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Rebuild the exact semantic claim without the production detector."""
    board, played, best = _moves(row)
    if board is None:
        return {"verified": False, "reason": "invalid_fen"}
    if played is None:
        return {"verified": False, "reason": "invalid_played_move"}
    if best is None:
        return {"verified": False, "reason": "invalid_best_move"}
    if played == best:
        return {"verified": False, "reason": "same_move"}
    if not board.is_capture(best):
        return {"verified": False, "reason": "non_capture"}

    captured_square = best.to_square
    if board.is_en_passant(best):
        captured_square += -8 if board.turn == chess.WHITE else 8
    captured = board.piece_at(captured_square)
    if (
        captured is None
        or captured.color == board.turn
        or captured.piece_type == chess.KING
    ):
        return {"verified": False, "reason": "invalid_capture_target"}
    value = PIECE_VALUES.get(captured.piece_type, 0)
    base_facts = {
        "captured_piece": chess.piece_name(captured.piece_type),
        "captured_square": chess.square_name(captured_square),
        "captured_value_cp": value,
    }
    if value < TARGET_VALUE_FLOOR:
        return {
            "verified": False,
            "reason": "lower_value_target",
            **base_facts,
        }

    after = board.copy(stack=False)
    after.push(best)
    recaptures = tuple(sorted(
        reply.uci()
        for reply in after.legal_moves
        if after.is_capture(reply) and reply.to_square == best.to_square
    ))
    if recaptures:
        return {
            "verified": False,
            "reason": "immediate_recapture",
            "recaptures": recaptures,
            **base_facts,
        }

    loss = _cp_loss(row)
    if loss is None:
        return {
            "verified": False,
            "reason": "invalid_consequence",
            "recaptures": (),
            **base_facts,
        }
    if loss < CP_LOSS_FLOOR:
        return {
            "verified": False,
            "reason": "insufficient_consequence",
            "recaptures": (),
            **base_facts,
        }
    return {
        "verified": True,
        "reason": "free_piece_exact",
        "played_move_uci": played.uci(),
        "best_move_uci": best.uci(),
        "cp_loss": loss,
        "recaptures": (),
        **base_facts,
    }


def _candidate_fires(row: Mapping[str, Any]) -> bool:
    """Replay the production candidate separately from independent gold."""
    board, played, best = _moves(row)
    if board is None or played is None or best is None:
        return False
    from services.free_piece_puzzle_proof import build_free_piece_proof

    proof = build_free_piece_proof(
        board, played.uci(), best.uci(), row.get("cp_loss")
    )
    return bool(proof and proof.verifier.verified)


def _source_token(row: Mapping[str, Any], *, pool: str) -> str:
    admission = row.get("verified_admission") or {}
    source = (
        admission.get("source_fingerprint")
        or row.get("source_game_id")
        or row.get("game_id")
        or row.get("position_id")
        or json.dumps(
            {
                "pool": pool,
                "fen": row.get("fen"),
                "best": row.get("best_move_uci") or row.get("best_move_san"),
                "played": (
                    row.get("played_move")
                    or row.get("user_move_uci")
                    or row.get("user_move_san")
                ),
            },
            sort_keys=True,
        )
    )
    return _hash(source, namespace="free-piece-source")


def _case_id(row: Mapping[str, Any], *, pool: str) -> str:
    payload = {
        "pool": pool,
        "source": _source_token(row, pool=pool),
        "fen": row.get("fen"),
        "best": row.get("best_move_uci") or row.get("best_move_san"),
        "played": (
            row.get("played_move")
            or row.get("user_move")
            or row.get("move")
            or row.get("user_move_uci")
            or row.get("user_move_san")
        ),
    }
    return _hash(
        json.dumps(payload, sort_keys=True),
        namespace="free-piece-case",
    )


def _rank(case: Mapping[str, Any], label: str) -> str:
    return hashlib.sha256(
        f"{SEED}\x1f{label}\x1f{case['case_id']}".encode("utf-8")
    ).hexdigest()


def _stored_fact(row: Mapping[str, Any]) -> Dict[str, Any]:
    admission = row.get("verified_admission") or {}
    facts = admission.get("verifier_facts") or ()
    fact = facts[0] if facts and isinstance(facts[0], Mapping) else {}
    return {
        "captured_piece": fact.get("captured_piece"),
        "captured_square": fact.get("captured_square"),
        "captured_value_cp": fact.get("captured_value_cp"),
        "recaptures": list(fact.get("recaptures") or ()),
    }


def _positive_case(row: Mapping[str, Any], *, pool: str) -> Dict[str, Any]:
    gold = independent_gold(row)
    return {
        "case_id": _case_id(row, pool=pool),
        "source_key": _source_token(row, pool=pool),
        "pool": pool,
        "fen_before": row.get("fen"),
        "played_move_uci": gold.get("played_move_uci"),
        "best_move_uci": gold.get("best_move_uci"),
        "cp_loss": gold.get("cp_loss"),
        "candidate_fired": _candidate_fires(row),
        "gold": {
            "reason": gold.get("reason"),
            "captured_piece": gold.get("captured_piece"),
            "captured_square": gold.get("captured_square"),
            "captured_value_cp": gold.get("captured_value_cp"),
        },
    }


def _negative_case(row: Mapping[str, Any], *, pool: str) -> Dict[str, Any]:
    gold = independent_gold(row)
    _, played, best = _moves(row)
    return {
        "case_id": _case_id(row, pool=pool),
        "source_key": _source_token(row, pool=pool),
        "pool": pool,
        "fen_before": row.get("fen"),
        "played_move_uci": played.uci() if played else None,
        "best_move_uci": best.uci() if best else None,
        "cp_loss": _cp_loss(row),
        "candidate_fired": _candidate_fires(row),
        "gold": {
            "reason": gold.get("reason"),
            "captured_piece": gold.get("captured_piece"),
            "captured_square": gold.get("captured_square"),
            "captured_value_cp": gold.get("captured_value_cp"),
        },
    }


def _wilson_lower(successes: int, total: int) -> float:
    if total <= 0:
        return 0.0
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt(
        (p * (1 - p) + z * z / (4 * total)) / total
    )
    return (centre - margin) / denominator


def _load_rows(db: Any) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for pool in POOLS:
        for row in db[pool].find({}, PROJECTION):
            rows.append({"pool": pool, "row": row})
    return rows


def _positive_sample(
    cases: Iterable[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    unique: Dict[str, Dict[str, Any]] = {}
    for case in sorted(cases, key=lambda item: _rank(item, "positive")):
        unique.setdefault(str(case["source_key"]), case)
    ordered = list(unique.values())
    selected: list[Dict[str, Any]] = []
    used: set[str] = set()

    def take_first(predicate) -> None:
        for case in ordered:
            if case["source_key"] in used or not predicate(case):
                continue
            selected.append(case)
            used.add(case["source_key"])
            return

    for pool in POOLS:
        take_first(lambda case, expected=pool: case["pool"] == expected)
    for piece in ("knight", "bishop", "rook", "queen"):
        take_first(
            lambda case, expected=piece: (
                case["gold"]["captured_piece"] == expected
            )
        )
    for case in ordered:
        if len(selected) >= POSITIVE_TARGET:
            break
        if case["source_key"] in used:
            continue
        selected.append(case)
        used.add(case["source_key"])
    return selected


def _negative_sample(
    rows: Iterable[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    selected: list[Dict[str, Any]] = []
    used: set[str] = set()
    for stratum in NEGATIVE_STRATA:
        candidates = []
        for item in rows:
            gold = independent_gold(item["row"])
            if gold.get("reason") != stratum:
                continue
            candidates.append(
                _negative_case(item["row"], pool=item["pool"])
            )
        taken = 0
        for case in sorted(
            candidates, key=lambda item: _rank(item, stratum)
        ):
            if case["source_key"] in used:
                continue
            selected.append(case)
            used.add(case["source_key"])
            taken += 1
            if taken >= NEGATIVE_PER_STRATUM:
                break
    return selected


def build_report(db: Any) -> Dict[str, Any]:
    rows = _load_rows(db)
    stored_candidates = [
        item for item in rows
        if (item["row"].get("verified_admission") or {}).get("quality_id")
        == QUALITY_ID
    ]
    population_outcomes: Counter[str] = Counter()
    population_pieces: Counter[str] = Counter()
    population_pools: Counter[str] = Counter()
    population_sources: set[str] = set()
    fact_mismatches = 0
    detector_replay_failures = 0
    positive_cases: list[Dict[str, Any]] = []

    for item in stored_candidates:
        row, pool = item["row"], item["pool"]
        gold = independent_gold(row)
        population_outcomes[str(gold.get("reason"))] += 1
        population_pools[pool] += 1
        if gold.get("captured_piece"):
            population_pieces[str(gold["captured_piece"])] += 1
        population_sources.add(_source_token(row, pool=pool))
        stored = _stored_fact(row)
        expected = {
            "captured_piece": gold.get("captured_piece"),
            "captured_square": gold.get("captured_square"),
            "captured_value_cp": gold.get("captured_value_cp"),
            "recaptures": list(gold.get("recaptures") or ()),
        }
        if stored != expected:
            fact_mismatches += 1
        if not _candidate_fires(row):
            detector_replay_failures += 1
        positive_cases.append(_positive_case(row, pool=pool))

    positives = _positive_sample(positive_cases)
    negatives = _negative_sample(rows)
    true_positives = sum(
        case["candidate_fired"]
        and case["gold"]["reason"] == "free_piece_exact"
        for case in positives
    )
    true_negatives = sum(
        not case["candidate_fired"]
        and case["gold"]["reason"] in NEGATIVE_STRATA
        for case in negatives
    )
    precision = true_positives / max(len(positives), 1)
    wilson = _wilson_lower(true_positives, len(positives))
    critical_errors = (
        (len(positives) - true_positives)
        + (len(negatives) - true_negatives)
        + fact_mismatches
        + detector_replay_failures
    )
    pieces = {
        case["gold"]["captured_piece"] for case in positives
    }
    pools = {case["pool"] for case in positives}
    strata = Counter(
        case["gold"]["reason"] for case in negatives
    )
    gate = all((
        len(positives) >= POSITIVE_TARGET,
        len({case["source_key"] for case in positives}) == len(positives),
        precision >= 0.95,
        wilson >= 0.85,
        len(negatives) >= NEGATIVE_TARGET,
        true_negatives == len(negatives),
        pieces == {"knight", "bishop", "rook", "queen"},
        pools == set(POOLS),
        all(
            strata[name] == NEGATIVE_PER_STRATUM
            for name in NEGATIVE_STRATA
        ),
        critical_errors == 0,
        population_outcomes
        == Counter({"free_piece_exact": len(stored_candidates)}),
    ))
    selection_manifest = {
        "fires": [case["case_id"] for case in positives],
        "negatives": [case["case_id"] for case in negatives],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": date.today().isoformat(),
        "read_only": True,
        "stockfish_runs": 0,
        "llm_calls": 0,
        "database_writes": 0,
        "quality_id": QUALITY_ID,
        "claim": (
            "The stored best move captures an opponent knight, bishop, rook "
            "or queen, and the opponent has no legal immediate recapture on "
            "that square."
        ),
        "selection": {
            "seed": SEED,
            "positive_target": POSITIVE_TARGET,
            "negative_target": NEGATIVE_TARGET,
            "negative_strata": {
                name: NEGATIVE_PER_STRATUM for name in NEGATIVE_STRATA
            },
            "distinct_source_fingerprints_required": True,
            "required_pools": list(POOLS),
            "required_target_pieces": [
                "knight", "bishop", "rook", "queen"
            ],
            "selection_fingerprint_sha256": hashlib.sha256(
                json.dumps(
                    selection_manifest,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        },
        "population": {
            "documents_scanned": len(rows),
            "stored_candidates": len(stored_candidates),
            "distinct_source_keys": len(population_sources),
            "by_pool": dict(sorted(population_pools.items())),
            "by_target_piece": dict(sorted(population_pieces.items())),
            "independent_outcomes": dict(
                sorted(population_outcomes.items())
            ),
            "stored_fact_mismatches": fact_mismatches,
            "candidate_replay_failures": detector_replay_failures,
        },
        "summary": {
            "reviewed_fires": len(positives),
            "true_positives": true_positives,
            "semantic_precision_pct": round(precision * 100, 2),
            "wilson_lower_pct": round(wilson * 100, 2),
            "true_negative_cases": len(negatives),
            "true_negatives": true_negatives,
            "critical_adversarial_errors": critical_errors,
            "caption_promotion_gate_passed": gate,
        },
        "fires": positives,
        "negatives": negatives,
    }


def main() -> int:
    client = MongoClient(
        os.environ["MONGO_URL"],
        serverSelectionTimeoutMS=10_000,
    )
    try:
        report = build_report(
            client[os.environ.get("DB_NAME", "chess_coach")]
        )
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return (
            0
            if report["summary"]["caption_promotion_gate_passed"]
            else 1
        )
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
