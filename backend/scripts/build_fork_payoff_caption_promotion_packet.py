"""Build independent Caption evidence for tactic:fork_with_stored_payoff.

Candidate truth uses the existing canonical proof bundle. Gold truth below
rebuilds geometry, legality, material and target payoff without importing the
fork detectors, fork proof, stored-line replay helper or stored verdict.

The script reads stored evidence only. It never runs an engine, writes to
Mongo, or emits user/game/account identity.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
import math
import os
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import chess
from pymongo import MongoClient


SCHEMA_VERSION = "fork_payoff.caption_promotion.v1"
QUALITY_ID = "tactic:fork_with_stored_payoff"
SEED = "20260902-fork-payoff-caption-v1"
POSITIVE_TARGET = 50
NEGATIVE_PER_STRATUM = 5
NEGATIVE_STRATA = (
    "fewer_than_two_targets",
    "incomplete_line",
    "insufficient_net_gain",
    "no_original_target_captured",
    "insufficient_consequence",
)
NEGATIVE_TARGET = len(NEGATIVE_STRATA) * NEGATIVE_PER_STRATUM
CP_LOSS_FLOOR = 100
NET_GAIN_FLOOR = 100
TARGET_VALUE_FLOOR = 300
POOLS = ("community_puzzles", "community_training_positions")
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
    "pv_after_best": 1,
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
    if isinstance(raw, chess.Move):
        return raw if raw in board.legal_moves else None
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


def _token(raw: Any) -> Optional[str]:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, Mapping):
        value = raw.get("move") or raw.get("san") or raw.get("uci")
        return str(value) if value else None
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


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(
        len(board.pieces(piece_type, color)) * PIECE_VALUES[piece_type]
        for piece_type in (
            chess.PAWN,
            chess.KNIGHT,
            chess.BISHOP,
            chess.ROOK,
            chess.QUEEN,
        )
    )


def _qualifying_targets(
    board_after: chess.Board,
    *,
    square: chess.Square,
    attacker: chess.Color,
) -> tuple[tuple[chess.Square, int, chess.Color], ...]:
    targets = []
    for target_square in board_after.attacks(square):
        piece = board_after.piece_at(target_square)
        if piece is None or piece.color == attacker:
            continue
        value = PIECE_VALUES.get(piece.piece_type, 0)
        if piece.piece_type == chess.KING or value >= TARGET_VALUE_FLOOR:
            targets.append((target_square, piece.piece_type, piece.color))
    return tuple(targets)


def _replay_payoff(
    board_before: chess.Board,
    best: chess.Move,
    continuation: Sequence[Any],
    targets: Sequence[tuple[chess.Square, int, chess.Color]],
) -> Dict[str, Any]:
    tokens = [
        token for raw in continuation if (token := _token(raw))
    ]
    first = _parse_move(board_before, tokens[0]) if tokens else None
    full = ([] if first == best else [best.uci()]) + tokens

    initiator = board_before.turn
    board = board_before.copy(stack=False)
    own_before = _material(board, initiator)
    opponent_before = _material(board, not initiator)
    replayed = []
    live_targets = {
        square: (piece_type, color)
        for square, piece_type, color in targets
    }
    captured_target = None
    complete = True

    for index, raw in enumerate(full):
        move = _parse_move(board, raw)
        if move is None:
            complete = False
            break
        if index > 0:
            if move.from_square in live_targets:
                live_targets.pop(move.from_square, None)
            original = live_targets.get(move.to_square)
            captured = board.piece_at(move.to_square)
            if (
                original
                and board.turn == initiator
                and board.is_capture(move)
                and captured is not None
                and (captured.piece_type, captured.color) == original
            ):
                captured_target = move.to_square
        replayed.append(move.uci())
        board.push(move)
        if board.is_checkmate() and index != len(full) - 1:
            complete = False
            break

    net_gain = (
        (_material(board, initiator) - own_before)
        - (_material(board, not initiator) - opponent_before)
    )
    return {
        "complete": complete,
        "replayed_uci": tuple(replayed),
        "net_material_gain_cp": net_gain,
        "captured_target": captured_target,
    }


def independent_gold(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Rebuild exact fork/payoff truth without production proof code."""
    board, played, best = _moves(row)
    if board is None:
        return {"verified": False, "reason": "invalid_fen"}
    if played is None:
        return {"verified": False, "reason": "invalid_played_move"}
    if best is None:
        return {"verified": False, "reason": "invalid_best_move"}
    if played == best:
        return {"verified": False, "reason": "same_move"}

    initiator = board.turn
    after = board.copy(stack=False)
    after.push(best)
    moved = after.piece_at(best.to_square)
    if moved is None or moved.color != initiator:
        return {"verified": False, "reason": "invalid_mover"}
    targets = _qualifying_targets(
        after, square=best.to_square, attacker=initiator
    )
    base = {
        "played_move_uci": played.uci(),
        "best_move_uci": best.uci(),
        "forking_piece": chess.piece_name(moved.piece_type),
        "fork_square": chess.square_name(best.to_square),
        "targets": tuple(
            chess.square_name(square) for square, _piece, _color in targets
        ),
        "target_count": len(targets),
    }
    if len(targets) < 2:
        return {
            "verified": False,
            "reason": "fewer_than_two_targets",
            **base,
        }

    replay = _replay_payoff(
        board, best, row.get("pv_after_best") or (), targets
    )
    facts = {
        **base,
        "captured_target": (
            chess.square_name(replay["captured_target"])
            if replay["captured_target"] is not None
            else None
        ),
        "net_material_gain_cp": replay["net_material_gain_cp"],
        "replayed_uci": replay["replayed_uci"],
    }
    if not replay["complete"]:
        return {
            "verified": False,
            "reason": "incomplete_line",
            **facts,
        }
    if replay["net_material_gain_cp"] < NET_GAIN_FLOOR:
        return {
            "verified": False,
            "reason": "insufficient_net_gain",
            **facts,
        }
    if replay["captured_target"] is None:
        return {
            "verified": False,
            "reason": "no_original_target_captured",
            **facts,
        }

    loss = _cp_loss(row)
    facts["cp_loss"] = loss
    if loss is None:
        return {
            "verified": False,
            "reason": "invalid_consequence",
            **facts,
        }
    if loss < CP_LOSS_FLOOR:
        return {
            "verified": False,
            "reason": "insufficient_consequence",
            **facts,
        }
    return {"verified": True, "reason": "fork_exact", **facts}


def _candidate_fires(row: Mapping[str, Any]) -> bool:
    """Replay the production candidate separately from independent gold."""
    board, played, best = _moves(row)
    if board is None or played is None or best is None:
        return False
    from services.fork_puzzle_proof import build_fork_proof

    proof = build_fork_proof(
        board,
        played.uci(),
        best.uci(),
        row.get("pv_after_best") or (),
        row.get("cp_loss"),
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
    return _hash(source, namespace="fork-payoff-source")


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
        namespace="fork-payoff-case",
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
        "forking_piece": fact.get("forking_piece"),
        "fork_square": fact.get("fork_square"),
        "targets": list(fact.get("targets") or ()),
        "captured_target": fact.get("captured_target"),
        "net_material_gain_cp": fact.get("net_material_gain_cp"),
        "replayed_uci": list(fact.get("replayed_uci") or ()),
    }


def _gold_fact(gold: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "forking_piece": gold.get("forking_piece"),
        "fork_square": gold.get("fork_square"),
        "targets": list(gold.get("targets") or ()),
        "captured_target": gold.get("captured_target"),
        "net_material_gain_cp": gold.get("net_material_gain_cp"),
        "replayed_uci": list(gold.get("replayed_uci") or ()),
    }


def _case(
    row: Mapping[str, Any],
    *,
    pool: str,
    gold: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "case_id": _case_id(row, pool=pool),
        "source_key": _source_token(row, pool=pool),
        "pool": pool,
        "fen_before": row.get("fen"),
        "played_move_uci": gold.get("played_move_uci"),
        "best_move_uci": gold.get("best_move_uci"),
        "pv_after_best": list(row.get("pv_after_best") or ()),
        "cp_loss": _cp_loss(row),
        "candidate_fired": _candidate_fires(row),
        "gold": {
            "reason": gold.get("reason"),
            "forking_piece": gold.get("forking_piece"),
            "fork_square": gold.get("fork_square"),
            "targets": list(gold.get("targets") or ()),
            "captured_target": gold.get("captured_target"),
            "net_material_gain_cp": gold.get("net_material_gain_cp"),
            "replayed_uci": list(gold.get("replayed_uci") or ()),
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
    rows = []
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
    selected = []
    used = set()

    def take_first(predicate) -> None:
        for case in ordered:
            if case["source_key"] in used or not predicate(case):
                continue
            selected.append(case)
            used.add(case["source_key"])
            return

    for pool in POOLS:
        take_first(lambda case, expected=pool: case["pool"] == expected)
    for piece in ("knight", "bishop", "rook", "pawn"):
        take_first(
            lambda case, expected=piece: (
                case["gold"]["forking_piece"] == expected
            )
        )
    for target_count in (2, 3):
        take_first(
            lambda case, expected=target_count: (
                len(case["gold"]["targets"]) == expected
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
    selected = []
    used = set()
    for stratum in NEGATIVE_STRATA:
        candidates = []
        for item in rows:
            gold = independent_gold(item["row"])
            if gold.get("reason") != stratum:
                continue
            candidates.append(
                _case(
                    item["row"],
                    pool=item["pool"],
                    gold=gold,
                )
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
    population_target_counts: Counter[int] = Counter()
    population_pools: Counter[str] = Counter()
    population_sources = set()
    fact_mismatches = 0
    candidate_replay_failures = 0
    positive_cases = []

    for item in stored_candidates:
        row, pool = item["row"], item["pool"]
        gold = independent_gold(row)
        population_outcomes[str(gold.get("reason"))] += 1
        population_pools[pool] += 1
        population_pieces[str(gold.get("forking_piece"))] += 1
        population_target_counts[len(gold.get("targets") or ())] += 1
        population_sources.add(_source_token(row, pool=pool))
        if _stored_fact(row) != _gold_fact(gold):
            fact_mismatches += 1
        if not _candidate_fires(row):
            candidate_replay_failures += 1
        positive_cases.append(
            _case(row, pool=pool, gold=gold)
        )

    positives = _positive_sample(positive_cases)
    negatives = _negative_sample(rows)
    true_positives = sum(
        case["candidate_fired"]
        and case["gold"]["reason"] == "fork_exact"
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
        + candidate_replay_failures
    )
    pieces = {case["gold"]["forking_piece"] for case in positives}
    target_counts = {
        len(case["gold"]["targets"]) for case in positives
    }
    pools = {case["pool"] for case in positives}
    strata = Counter(case["gold"]["reason"] for case in negatives)
    gate = all((
        len(positives) == POSITIVE_TARGET,
        len({case["source_key"] for case in positives}) == len(positives),
        precision >= 0.95,
        wilson >= 0.85,
        len(negatives) == NEGATIVE_TARGET,
        true_negatives == len(negatives),
        pieces == {"knight", "bishop", "rook", "pawn"},
        target_counts == {2, 3},
        pools == set(POOLS),
        all(
            strata[name] == NEGATIVE_PER_STRATUM
            for name in NEGATIVE_STRATA
        ),
        critical_errors == 0,
        population_outcomes
        == Counter({"fork_exact": len(stored_candidates)}),
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
        "caption_claim": (
            "The stored best move puts the moved knight, bishop, rook or pawn "
            "where it attacks at least two qualifying opponent pieces at once."
        ),
        "proof_contract": (
            "The complete stored best line gains at least one pawn of net "
            "material and captures an original fork target before it moves."
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
            "required_forking_pieces": [
                "knight", "bishop", "rook", "pawn"
            ],
            "required_target_counts": [2, 3],
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
            "by_forking_piece": dict(sorted(population_pieces.items())),
            "by_target_count": {
                str(key): value
                for key, value in sorted(population_target_counts.items())
            },
            "independent_outcomes": dict(
                sorted(population_outcomes.items())
            ),
            "stored_fact_mismatches": fact_mismatches,
            "candidate_replay_failures": candidate_replay_failures,
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
