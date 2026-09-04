#!/usr/bin/env python3
"""Validate Phase 3A.1 branch evidence on the locked offline packet.

No database, network, engine, user identity, or file write is used.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import chess


BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.caption_facts import (  # noqa: E402
    VERIFIED_LINE_CAUSE_VERSION,
    build_verified_branch_evidence,
    build_verified_line_cause,
)
from services.stored_line_verifier import replay_stored_line  # noqa: E402


PACKET = (
    BACKEND
    / "data/corpus_snapshots/"
    "hidden_opportunities_chess_gold_v1_2026-09-02.json"
)


def _oracle_after_leading(
    fen: str,
    leading_uci: str,
    continuation: list[str],
) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    """Replay the packet's documented format without using the verifier."""
    board = chess.Board(fen)
    raw_moves = [leading_uci, *continuation]
    uci_moves = []
    san_moves = []
    for raw in raw_moves:
        try:
            move = chess.Move.from_uci(raw)
            if move not in board.legal_moves:
                move = board.parse_san(raw)
        except (ValueError, AssertionError):
            move = board.parse_san(raw)
        if move not in board.legal_moves:
            raise ValueError(f"illegal oracle move: {raw}")
        uci_moves.append(move.uci())
        san_moves.append(board.san(move))
        board.push(move)
    return tuple(uci_moves), tuple(san_moves), board.fen()


def _legacy_core(payload: dict) -> dict:
    core = deepcopy(payload)
    core.pop("fingerprint", None)
    core.pop("branch_evidence", None)
    core["schema_version"] = VERIFIED_LINE_CAUSE_VERSION
    if isinstance(core.get("proof"), dict):
        core["proof"]["version"] = VERIFIED_LINE_CAUSE_VERSION
    return core


def main() -> int:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    failures = []
    counts = {
        "positions": 0,
        "branch_traces": 0,
        "events": 0,
        "captures": 0,
        "checks": 0,
        "checkmates": 0,
        "promotions": 0,
        "single_legal_reply_events": 0,
        "relation_changes": 0,
        "line_geometry_changes": 0,
        "verified_line_causes": 0,
        "branch_evidence_builds": 0,
        "independent_oracle_traces": 0,
        "default_contract_mismatches": 0,
    }

    for row in packet["positions"]:
        counts["positions"] += 1
        traces = {}
        for branch in ("played", "best"):
            first = row[f"{branch}_move"]
            replay = replay_stored_line(
                chess.Board(row["fen"]),
                first["uci"],
                row["stored_four_ply"][f"after_{branch}"],
                include_events=True,
                resolve_ambiguous_continuation=True,
            )
            traces[branch] = replay
            counts["branch_traces"] += 1
            counts["events"] += len(replay.events)
            counts["captures"] += len(replay.captures)
            counts["checks"] += sum(
                event.gave_check for event in replay.events
            )
            counts["checkmates"] += sum(
                event.checkmate for event in replay.events
            )
            counts["promotions"] += sum(
                event.promotion_piece is not None for event in replay.events
            )
            counts["single_legal_reply_events"] += sum(
                event.legal_reply_count == 1 for event in replay.events
            )
            counts["relation_changes"] += sum(
                len(event.relation_changes) for event in replay.events
            )
            counts["line_geometry_changes"] += sum(
                len(event.line_geometry_changes) for event in replay.events
            )

            if not replay.complete:
                failures.append(
                    f"{row['position_id']}:{branch}:incomplete"
                )
                continue
            try:
                oracle_uci, oracle_san, oracle_final_fen = (
                    _oracle_after_leading(
                        row["fen"],
                        first["uci"],
                        row["stored_four_ply"][f"after_{branch}"],
                    )
                )
            except (ValueError, AssertionError) as exc:
                failures.append(
                    f"{row['position_id']}:{branch}:oracle:{exc}"
                )
            else:
                counts["independent_oracle_traces"] += 1
                if replay.replayed_uci != oracle_uci:
                    failures.append(
                        f"{row['position_id']}:{branch}:oracle_uci"
                    )
                if replay.replayed_san != oracle_san:
                    failures.append(
                        f"{row['position_id']}:{branch}:oracle_san"
                    )
                if replay.final_fen != oracle_final_fen:
                    failures.append(
                        f"{row['position_id']}:{branch}:oracle_fen"
                    )
            if len(replay.events) != len(replay.replayed_uci):
                failures.append(
                    f"{row['position_id']}:{branch}:event_count"
                )
            if (
                replay.events
                and replay.events[0].move_uci != first["uci"]
            ):
                failures.append(
                    f"{row['position_id']}:{branch}:leading_move"
                )
            for index, event in enumerate(replay.events):
                expected_actor = (
                    "initiator" if index % 2 == 0 else "opponent"
                )
                if event.actor != expected_actor:
                    failures.append(
                        f"{row['position_id']}:{branch}:actor:{index + 1}"
                    )
                if event.move_uci != replay.replayed_uci[index]:
                    failures.append(
                        f"{row['position_id']}:{branch}:move:{index + 1}"
                    )
                oracle_board = chess.Board(event.fen_before)
                oracle_move = chess.Move.from_uci(event.move_uci)
                if oracle_move not in oracle_board.legal_moves:
                    failures.append(
                        f"{row['position_id']}:{branch}:event_legal:{index + 1}"
                    )
                else:
                    if oracle_board.san(oracle_move) != event.move_san:
                        failures.append(
                            f"{row['position_id']}:{branch}:event_san:{index + 1}"
                        )
                    oracle_board.push(oracle_move)
                    if oracle_board.fen() != event.fen_after:
                        failures.append(
                            f"{row['position_id']}:{branch}:event_fen:{index + 1}"
                        )
                if (
                    index > 0
                    and replay.events[index - 1].fen_after
                    != event.fen_before
                ):
                    failures.append(
                        f"{row['position_id']}:{branch}:continuity:{index + 1}"
                    )
            rerun = replay_stored_line(
                chess.Board(row["fen"]),
                first["uci"],
                row["stored_four_ply"][f"after_{branch}"],
                include_events=True,
                resolve_ambiguous_continuation=True,
            )
            if replay.fingerprint != rerun.fingerprint:
                failures.append(
                    f"{row['position_id']}:{branch}:nondeterministic"
                )
            json.dumps(replay.contract_dict(), sort_keys=True)

        kwargs = {
            "fen_before": row["fen"],
            "played_san": row["played_move"]["san"],
            "best_move_san": row["best_move"]["san"],
            "pv_after_played": tuple(
                row["stored_four_ply"]["after_played"]
            ),
            "pv_after_best": tuple(row["stored_four_ply"]["after_best"]),
            "cp_loss": row["cp_loss"],
        }
        branch_evidence = build_verified_branch_evidence(
            fen_before=kwargs["fen_before"],
            played_san=kwargs["played_san"],
            best_move_san=kwargs["best_move_san"],
            pv_after_played=kwargs["pv_after_played"],
            pv_after_best=kwargs["pv_after_best"],
        )
        if branch_evidence is None:
            failures.append(
                f"{row['position_id']}:branch_evidence_missing"
            )
        else:
            counts["branch_evidence_builds"] += 1
        default_cause = build_verified_line_cause(**kwargs)
        causal_cause = build_verified_line_cause(
            **kwargs, include_branch_evidence=True
        )
        if (default_cause is None) != (causal_cause is None):
            counts["default_contract_mismatches"] += 1
            failures.append(
                f"{row['position_id']}:cause_presence_changed"
            )
        elif default_cause is not None and causal_cause is not None:
            counts["verified_line_causes"] += 1
            if (
                _legacy_core(default_cause.contract_dict())
                != _legacy_core(causal_cause.contract_dict())
            ):
                counts["default_contract_mismatches"] += 1
                failures.append(
                    f"{row['position_id']}:cause_core_changed"
                )

    result = {
        "schema_version": "hidden_opportunities_branch_evidence_validation.v1",
        "fresh_engine_runs": 0,
        "production_reads": 0,
        "database_writes": 0,
        **counts,
        "failures": failures,
        "passed": not failures,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
