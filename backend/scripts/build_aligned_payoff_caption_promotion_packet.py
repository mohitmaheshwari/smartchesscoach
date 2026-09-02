"""Build independent Caption evidence for aligned pin/skewer payoff.

The gold path rebuilds legal rays, piece ordering, creation mode and stored
payoff without importing the production aligned detector, proof, ray helper or
stored-line replay. Production proof is loaded only by the candidate grader.

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


SCHEMA_VERSION = "aligned_payoff.caption_promotion.v1"
QUALITY_ID = "tactic:aligned_with_stored_payoff"
SEED = "20260902-aligned-payoff-caption-v1"
POSITIVE_PER_KIND = 25
KINDS = ("pin", "skewer")
NEGATIVE_PER_STRATUM = 5
NEGATIVE_STRATA = (
    "no_created_alignment",
    "incomplete_line",
    "insufficient_net_gain",
    "attacker_left_before_payoff",
    "pin_front_escaped",
    "pin_target_not_captured",
    "skewer_front_not_cleared",
    "skewer_rear_escaped",
    "skewer_rear_not_captured",
    "insufficient_consequence",
)
POSITIVE_TARGET = POSITIVE_PER_KIND * len(KINDS)
NEGATIVE_TARGET = NEGATIVE_PER_STRATUM * len(NEGATIVE_STRATA)
CP_LOSS_FLOOR = 100
NET_GAIN_FLOOR = 100
POOLS = ("community_puzzles", "community_training_positions")
ATTACKER_PIECES = ("bishop", "rook", "queen")
CREATION_MODES = ("direct", "discovered")
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 10_000,
}
DIAGONALS = ((1, 1), (1, -1), (-1, 1), (-1, -1))
ORTHOGONALS = ((1, 0), (-1, 0), (0, 1), (0, -1))
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


def _directions(piece_type: int):
    if piece_type == chess.BISHOP:
        return DIAGONALS
    if piece_type == chess.ROOK:
        return ORTHOGONALS
    return DIAGONALS + ORTHOGONALS


def _independent_alignments(
    board: chess.Board,
    color: chess.Color,
) -> list[Dict[str, Any]]:
    """Rebuild every unequal-value two-opponent-blocker slider ray."""
    found = []
    for piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        for attacker in board.pieces(piece_type, color):
            for file_step, rank_step in _directions(piece_type):
                file_ = chess.square_file(attacker) + file_step
                rank_ = chess.square_rank(attacker) + rank_step
                hits = []
                while 0 <= file_ < 8 and 0 <= rank_ < 8:
                    square = chess.square(file_, rank_)
                    piece = board.piece_at(square)
                    if piece:
                        hits.append((square, piece))
                        if len(hits) == 2:
                            break
                    file_ += file_step
                    rank_ += rank_step
                if len(hits) != 2:
                    continue
                if any(piece.color == color for _square, piece in hits):
                    continue
                (front_square, front), (rear_square, rear) = hits
                front_value = PIECE_VALUES[front.piece_type]
                rear_value = PIECE_VALUES[rear.piece_type]
                kind = (
                    "pin" if front_value < rear_value
                    else "skewer" if front_value > rear_value
                    else None
                )
                if kind is None:
                    continue
                found.append({
                    "kind": kind,
                    "attacker_square": attacker,
                    "front_square": front_square,
                    "rear_square": rear_square,
                    "attacker_piece_type": piece_type,
                    "front_piece_type": front.piece_type,
                    "rear_piece_type": rear.piece_type,
                })
    return found


def _replay_payoff(
    board_before: chess.Board,
    best: chess.Move,
    continuation: Sequence[Any],
    alignment: Mapping[str, Any],
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
    identities = None
    used = False
    front_cleared = False
    front_escaped = False
    rear_escaped = False
    attacker_left = False

    for index, raw in enumerate(full):
        move = _parse_move(board, raw)
        if move is None:
            return {
                "reason": "incomplete_line",
                "net_material_gain_cp": None,
                "replayed_uci": tuple(replayed),
            }
        mover = board.turn
        is_capture = board.is_capture(move)
        moving_piece = board.piece_at(move.from_square)
        if index == 0:
            replayed.append(move.uci())
            board.push(move)
            attacker = board.piece_at(alignment["attacker_square"])
            front = board.piece_at(alignment["front_square"])
            rear = board.piece_at(alignment["rear_square"])
            if attacker is None or front is None or rear is None:
                return {
                    "reason": "incomplete_line",
                    "net_material_gain_cp": None,
                    "replayed_uci": tuple(replayed),
                }
            identities = (
                (attacker.piece_type, attacker.color),
                (front.piece_type, front.color),
                (rear.piece_type, rear.color),
            )
            continue

        attacker = board.piece_at(alignment["attacker_square"])
        front = board.piece_at(alignment["front_square"])
        rear = board.piece_at(alignment["rear_square"])
        original_attacker = bool(
            moving_piece
            and move.from_square == alignment["attacker_square"]
            and (moving_piece.piece_type, moving_piece.color) == identities[0]
        )
        original_front = bool(
            moving_piece
            and move.from_square == alignment["front_square"]
            and (moving_piece.piece_type, moving_piece.color) == identities[1]
        )
        original_rear = bool(
            moving_piece
            and move.from_square == alignment["rear_square"]
            and (moving_piece.piece_type, moving_piece.color) == identities[2]
        )

        if alignment["kind"] == "skewer":
            if original_front and mover != initiator:
                front_cleared = True
            if original_rear:
                rear_escaped = True
            if (
                mover == initiator
                and front_cleared
                and is_capture
                and original_attacker
                and move.to_square == alignment["rear_square"]
                and rear is not None
                and (rear.piece_type, rear.color) == identities[2]
            ):
                used = True
        else:
            if original_front:
                front_escaped = True
            if (
                mover == initiator
                and is_capture
                and original_attacker
                and move.to_square == alignment["front_square"]
                and front is not None
                and (front.piece_type, front.color) == identities[1]
            ):
                used = True
        if original_attacker and not used:
            attacker_left = True
        replayed.append(move.uci())
        board.push(move)
        if board.is_checkmate() and index != len(full) - 1:
            return {
                "reason": "incomplete_line",
                "net_material_gain_cp": None,
                "replayed_uci": tuple(replayed),
            }

    net_gain = (
        (_material(board, initiator) - own_before)
        - (_material(board, not initiator) - opponent_before)
    )
    if net_gain < NET_GAIN_FLOOR:
        reason = "insufficient_net_gain"
    elif used:
        reason = "payoff_exact"
    elif attacker_left:
        reason = "attacker_left_before_payoff"
    elif alignment["kind"] == "pin":
        reason = (
            "pin_front_escaped" if front_escaped
            else "pin_target_not_captured"
        )
    elif rear_escaped:
        reason = "skewer_rear_escaped"
    elif not front_cleared:
        reason = "skewer_front_not_cleared"
    else:
        reason = "skewer_rear_not_captured"
    return {
        "reason": reason,
        "net_material_gain_cp": net_gain,
        "replayed_uci": tuple(replayed),
    }


def independent_gold(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Rebuild pin/skewer semantics and payoff without production proof code."""
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
    before_pairs = {
        (item["front_square"], item["rear_square"])
        for item in _independent_alignments(board, initiator)
    }
    after = board.copy(stack=False)
    after.push(best)
    created = [
        item
        for item in _independent_alignments(after, initiator)
        if (item["front_square"], item["rear_square"])
        not in before_pairs
    ]
    if not created:
        return {
            "verified": False,
            "reason": "no_created_alignment",
            "played_move_uci": played.uci(),
            "best_move_uci": best.uci(),
        }
    alignment = max(
        created,
        key=lambda item: max(
            PIECE_VALUES[item["front_piece_type"]],
            PIECE_VALUES[item["rear_piece_type"]],
        ),
    )
    base = {
        "played_move_uci": played.uci(),
        "best_move_uci": best.uci(),
        "kind": alignment["kind"],
        "creation_mode": (
            "direct"
            if alignment["attacker_square"] == best.to_square
            else "discovered"
        ),
        "attacker_piece": chess.piece_name(
            alignment["attacker_piece_type"]
        ),
        "attacker_square": chess.square_name(
            alignment["attacker_square"]
        ),
        "front_piece": chess.piece_name(alignment["front_piece_type"]),
        "front_square": chess.square_name(alignment["front_square"]),
        "rear_piece": chess.piece_name(alignment["rear_piece_type"]),
        "rear_square": chess.square_name(alignment["rear_square"]),
    }
    replay = _replay_payoff(
        board, best, row.get("pv_after_best") or (), alignment
    )
    facts = {
        **base,
        "net_material_gain_cp": replay["net_material_gain_cp"],
        "replayed_uci": replay["replayed_uci"],
    }
    if replay["reason"] != "payoff_exact":
        return {
            "verified": False,
            "reason": replay["reason"],
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
    return {
        "verified": True,
        "reason": f"{alignment['kind']}_exact",
        **facts,
    }


def _candidate(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Replay the production candidate separately from independent gold."""
    board, played, best = _moves(row)
    if board is None or played is None or best is None:
        return {"fired": False, "kind": None}
    from services.aligned_tactic_puzzle_proof import (
        build_aligned_tactic_proof,
    )

    proof = build_aligned_tactic_proof(
        board,
        played.uci(),
        best.uci(),
        row.get("pv_after_best") or (),
        row.get("cp_loss"),
    )
    fired = bool(proof and proof.verifier.verified)
    kind = (
        proof.detector.concept_id.rsplit(".", 1)[-1]
        if fired and proof is not None
        else None
    )
    return {"fired": fired, "kind": kind}


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
                "best": row.get("best_move_uci")
                or row.get("best_move_san"),
                "played": row.get("played_move")
                or row.get("user_move_uci")
                or row.get("user_move_san"),
            },
            sort_keys=True,
        )
    )
    return _hash(source, namespace="aligned-payoff-source")


def _case_id(row: Mapping[str, Any], *, pool: str) -> str:
    payload = {
        "pool": pool,
        "source": _source_token(row, pool=pool),
        "fen": row.get("fen"),
        "best": row.get("best_move_uci") or row.get("best_move_san"),
        "played": row.get("played_move")
        or row.get("user_move")
        or row.get("move")
        or row.get("user_move_uci")
        or row.get("user_move_san"),
    }
    return _hash(
        json.dumps(payload, sort_keys=True),
        namespace="aligned-payoff-case",
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
        "kind": fact.get("kind"),
        "attacker_square": fact.get("attacker_square"),
        "front_square": fact.get("front_square"),
        "rear_square": fact.get("rear_square"),
        "net_material_gain_cp": fact.get("net_material_gain_cp"),
        "replayed_uci": list(fact.get("replayed_uci") or ()),
    }


def _gold_fact(gold: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "kind": gold.get("kind"),
        "attacker_square": gold.get("attacker_square"),
        "front_square": gold.get("front_square"),
        "rear_square": gold.get("rear_square"),
        "net_material_gain_cp": gold.get("net_material_gain_cp"),
        "replayed_uci": list(gold.get("replayed_uci") or ()),
    }


def _case(
    row: Mapping[str, Any],
    *,
    pool: str,
    gold: Mapping[str, Any],
) -> Dict[str, Any]:
    candidate = _candidate(row)
    return {
        "case_id": _case_id(row, pool=pool),
        "source_key": _source_token(row, pool=pool),
        "pool": pool,
        "fen_before": row.get("fen"),
        "played_move_uci": gold.get("played_move_uci"),
        "best_move_uci": gold.get("best_move_uci"),
        "pv_after_best": list(row.get("pv_after_best") or ()),
        "cp_loss": _cp_loss(row),
        "candidate_fired": candidate["fired"],
        "candidate_kind": candidate["kind"],
        "gold": {
            "reason": gold.get("reason"),
            "kind": gold.get("kind"),
            "creation_mode": gold.get("creation_mode"),
            "attacker_piece": gold.get("attacker_piece"),
            "attacker_square": gold.get("attacker_square"),
            "front_piece": gold.get("front_piece"),
            "front_square": gold.get("front_square"),
            "rear_piece": gold.get("rear_piece"),
            "rear_square": gold.get("rear_square"),
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
    cases = list(cases)
    selected = []
    used = set()

    for kind in KINDS:
        ordered = sorted(
            (case for case in cases if case["gold"]["kind"] == kind),
            key=lambda item: _rank(item, f"positive-{kind}"),
        )

        def take_first(predicate) -> None:
            for case in ordered:
                if case["source_key"] in used or not predicate(case):
                    continue
                selected.append(case)
                used.add(case["source_key"])
                return

        for pool in POOLS:
            take_first(lambda case, expected=pool: case["pool"] == expected)
        for piece in ATTACKER_PIECES:
            take_first(
                lambda case, expected=piece: (
                    case["gold"]["attacker_piece"] == expected
                )
            )
        for mode in CREATION_MODES:
            take_first(
                lambda case, expected=mode: (
                    case["gold"]["creation_mode"] == expected
                )
            )
        for case in ordered:
            kind_count = sum(
                item["gold"]["kind"] == kind for item in selected
            )
            if kind_count >= POSITIVE_PER_KIND:
                break
            if case["source_key"] in used:
                continue
            selected.append(case)
            used.add(case["source_key"])
    return selected


def _negative_sample(
    annotated: Iterable[Dict[str, Any]],
    *,
    used_sources: set[str],
) -> list[Dict[str, Any]]:
    selected = []
    used = set(used_sources)
    annotated = list(annotated)
    for stratum in NEGATIVE_STRATA:
        candidates = sorted(
            (
                {
                    "case_id": _case_id(item["row"], pool=item["pool"]),
                    "source_key": _source_token(
                        item["row"], pool=item["pool"]
                    ),
                    "item": item,
                    "gold": item["gold"],
                }
                for item in annotated
                if item["gold"].get("reason") == stratum
            ),
            key=lambda item: _rank(item, f"negative-{stratum}"),
        )
        taken = 0
        for candidate in candidates:
            if candidate["source_key"] in used:
                continue
            item = candidate["item"]
            selected.append(
                _case(
                    item["row"],
                    pool=item["pool"],
                    gold=candidate["gold"],
                )
            )
            used.add(candidate["source_key"])
            taken += 1
            if taken >= NEGATIVE_PER_STRATUM:
                break
    return selected


def build_report(db: Any) -> Dict[str, Any]:
    rows = _load_rows(db)
    annotated = [
        {**item, "gold": independent_gold(item["row"])}
        for item in rows
    ]
    stored = [
        item for item in annotated
        if (item["row"].get("verified_admission") or {}).get("quality_id")
        == QUALITY_ID
    ]
    population_outcomes: Counter[str] = Counter()
    population_kinds: Counter[str] = Counter()
    population_modes: Counter[str] = Counter()
    population_pools: Counter[str] = Counter()
    population_attackers: Counter[str] = Counter()
    population_sources = set()
    fact_mismatches = 0
    candidate_replay_failures = 0
    positive_cases = []

    for item in stored:
        row, pool, gold = item["row"], item["pool"], item["gold"]
        population_outcomes[str(gold.get("reason"))] += 1
        population_kinds[str(gold.get("kind"))] += 1
        population_modes[str(gold.get("creation_mode"))] += 1
        population_pools[pool] += 1
        population_attackers[str(gold.get("attacker_piece"))] += 1
        population_sources.add(_source_token(row, pool=pool))
        if _stored_fact(row) != _gold_fact(gold):
            fact_mismatches += 1
        candidate = _candidate(row)
        if not candidate["fired"] or candidate["kind"] != gold.get("kind"):
            candidate_replay_failures += 1
        positive_cases.append(_case(row, pool=pool, gold=gold))

    positives = _positive_sample(positive_cases)
    negatives = _negative_sample(
        annotated,
        used_sources={case["source_key"] for case in positives},
    )
    true_by_kind = Counter()
    for case in positives:
        kind = case["gold"]["kind"]
        if (
            case["candidate_fired"]
            and case["candidate_kind"] == kind
            and case["gold"]["reason"] == f"{kind}_exact"
        ):
            true_by_kind[kind] += 1
    true_positives = sum(true_by_kind.values())
    true_negatives = sum(
        not case["candidate_fired"]
        and case["gold"]["reason"] in NEGATIVE_STRATA
        for case in negatives
    )
    subtype_wilson = {
        kind: _wilson_lower(true_by_kind[kind], POSITIVE_PER_KIND)
        for kind in KINDS
    }
    combined_wilson = _wilson_lower(true_positives, len(positives))
    critical_errors = (
        (len(positives) - true_positives)
        + (len(negatives) - true_negatives)
        + fact_mismatches
        + candidate_replay_failures
    )
    positive_counts = Counter(case["gold"]["kind"] for case in positives)
    negative_counts = Counter(case["gold"]["reason"] for case in negatives)

    def kind_coverage(kind: str) -> bool:
        cases = [case for case in positives if case["gold"]["kind"] == kind]
        return all((
            {case["pool"] for case in cases} == set(POOLS),
            {case["gold"]["attacker_piece"] for case in cases}
            == set(ATTACKER_PIECES),
            {case["gold"]["creation_mode"] for case in cases}
            == set(CREATION_MODES),
        ))

    full_outcomes = Counter(
        str(item["gold"].get("reason")) for item in annotated
    )
    gate = all((
        len(positives) == POSITIVE_TARGET,
        len({case["source_key"] for case in positives}) == len(positives),
        all(positive_counts[kind] == POSITIVE_PER_KIND for kind in KINDS),
        all(true_by_kind[kind] == POSITIVE_PER_KIND for kind in KINDS),
        all(subtype_wilson[kind] >= 0.85 for kind in KINDS),
        combined_wilson >= 0.85,
        all(kind_coverage(kind) for kind in KINDS),
        len(negatives) == NEGATIVE_TARGET,
        len({case["source_key"] for case in negatives}) == len(negatives),
        not (
            {case["source_key"] for case in positives}
            & {case["source_key"] for case in negatives}
        ),
        true_negatives == len(negatives),
        all(
            negative_counts[name] == NEGATIVE_PER_STRATUM
            for name in NEGATIVE_STRATA
        ),
        critical_errors == 0,
        population_outcomes
        == Counter({
            "pin_exact": population_kinds["pin"],
            "skewer_exact": population_kinds["skewer"],
        }),
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
            "The stored best move creates a new pin or skewer with exact "
            "attacker, front and rear pieces and squares."
        ),
        "proof_contract": (
            "The complete legal stored line uses the original alignment "
            "attacker and target for at least one pawn of net material gain."
        ),
        "selection": {
            "seed": SEED,
            "positive_per_kind": POSITIVE_PER_KIND,
            "positive_target": POSITIVE_TARGET,
            "negative_target": NEGATIVE_TARGET,
            "negative_strata": {
                name: NEGATIVE_PER_STRATUM for name in NEGATIVE_STRATA
            },
            "distinct_source_fingerprints_required": True,
            "required_pools_per_kind": list(POOLS),
            "required_attacker_pieces_per_kind": list(ATTACKER_PIECES),
            "required_creation_modes_per_kind": list(CREATION_MODES),
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
            "stored_candidates": len(stored),
            "distinct_source_keys": len(population_sources),
            "by_pool": dict(sorted(population_pools.items())),
            "by_kind": dict(sorted(population_kinds.items())),
            "by_creation_mode": dict(sorted(population_modes.items())),
            "by_attacker_piece": dict(sorted(population_attackers.items())),
            "independent_outcomes": dict(sorted(population_outcomes.items())),
            "full_pool_outcomes": dict(sorted(full_outcomes.items())),
            "stored_fact_mismatches": fact_mismatches,
            "candidate_replay_failures": candidate_replay_failures,
        },
        "summary": {
            "reviewed_fires": len(positives),
            "true_positives": true_positives,
            "pin_true_positives": true_by_kind["pin"],
            "skewer_true_positives": true_by_kind["skewer"],
            "semantic_precision_pct": round(
                true_positives / max(len(positives), 1) * 100, 2
            ),
            "combined_wilson_lower_pct": round(combined_wilson * 100, 2),
            "pin_wilson_lower_pct": round(subtype_wilson["pin"] * 100, 2),
            "skewer_wilson_lower_pct": round(
                subtype_wilson["skewer"] * 100, 2
            ),
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
        output = report
        if os.environ.get("ALIGNED_PACKET_SUMMARY_ONLY") == "1":
            output = {
                "schema_version": report["schema_version"],
                "selection": report["selection"],
                "population": report["population"],
                "summary": report["summary"],
                "positive_coverage": {
                    kind: {
                        "pools": sorted({
                            case["pool"]
                            for case in report["fires"]
                            if case["gold"]["kind"] == kind
                        }),
                        "attacker_pieces": sorted({
                            case["gold"]["attacker_piece"]
                            for case in report["fires"]
                            if case["gold"]["kind"] == kind
                        }),
                        "creation_modes": sorted({
                            case["gold"]["creation_mode"]
                            for case in report["fires"]
                            if case["gold"]["kind"] == kind
                        }),
                    }
                    for kind in KINDS
                },
                "negative_counts": dict(sorted(Counter(
                    case["gold"]["reason"]
                    for case in report["negatives"]
                ).items())),
            }
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        return (
            0
            if report["summary"]["caption_promotion_gate_passed"]
            else 1
        )
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
