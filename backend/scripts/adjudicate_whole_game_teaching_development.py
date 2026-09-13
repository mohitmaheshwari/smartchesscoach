#!/usr/bin/env python3
"""Build a conservative, detector-blind whole-game coaching worksheet.

This is offline evaluation tooling, not a runtime coach.  It consumes the
identity-free development packet, legally replays stored branches and records
only causes that the board itself proves.  Engine preference without a
board-level reason remains unsupported.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import chess

from scripts.export_full_game_chess_fact_audit import parse_move


SCHEMA_VERSION = "whole_game_teaching_review_codex_worksheet.v1"
EXPECTED_PACKET_SCHEMA = "whole_game_teaching_review_evidence.v1"
EXPECTED_MEMBERSHIP = (
    "91f8aacdb0d121fce9258509c84cc2b4bd1a840c3d63224a182ed9e875044496"
)
PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}
PIECE_VALUE_CP = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
RATING_THRESHOLDS = {
    "600-799": 150,
    "800-999": 150,
    "1000-1199": 100,
    "1200-1399": 75,
    "1400-1500": 50,
}


def _packet_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(
        len(board.pieces(piece_type, color)) * value
        for piece_type, value in PIECE_VALUE_CP.items()
    )


def _material_edge(board: chess.Board, color: chess.Color) -> int:
    return _material(board, color) - _material(board, not color)


def _capture(board: chess.Board, move: chess.Move) -> Dict[str, Any] | None:
    if not board.is_capture(move):
        return None
    square = move.to_square
    if board.is_en_passant(move):
        square += -8 if board.turn == chess.WHITE else 8
    piece = board.piece_at(square)
    if piece is None:
        raise ValueError("capture has no victim")
    return {
        "piece": PIECE_NAMES[piece.piece_type],
        "square": chess.square_name(square),
        "value_cp": PIECE_VALUE_CP[piece.piece_type],
    }


def _line(
    fen: str,
    first_token: str,
    continuation: Sequence[str],
) -> Dict[str, Any]:
    board = chess.Board(fen)
    mover = board.turn
    root_edge = _material_edge(board, mover)
    first = parse_move(board, first_token)
    steps = []
    first_capture = _capture(board, first)
    first_san = board.san(first)
    first_check = board.gives_check(first)
    board.push(first)
    steps.append({
        "actor": "mover",
        "san": first_san,
        "uci": first.uci(),
        "capture": first_capture,
        "gives_check": first_check,
    })
    for index, token in enumerate(continuation[:8]):
        try:
            move = parse_move(board, token)
        except Exception:
            if index == 0 and str(token) in {first_token, first.uci(), first_san}:
                continue
            raise
        capture = _capture(board, move)
        san = board.san(move)
        gives_check = board.gives_check(move)
        actor = "mover" if board.turn == mover else "opponent"
        board.push(move)
        steps.append({
            "actor": actor,
            "san": san,
            "uci": move.uci(),
            "capture": capture,
            "gives_check": gives_check,
        })
    mate_for = None
    if board.is_checkmate() and steps:
        mate_for = steps[-1]["actor"]
    return {
        "steps": steps,
        "material_delta_cp": _material_edge(board, mover) - root_edge,
        "mate_for": mate_for,
        "terminal": board.is_game_over(claim_draw=True),
    }


def _phase_for(
    game: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> str:
    exact = {
        (
            str(item.get("fen_before") or ""),
            str(item.get("move_san") or ""),
        ): str(item.get("phase") or "")
        for item in game.get("stored_phase_rows") or []
    }
    return exact.get(
        (
            str(evidence.get("fen_before") or ""),
            str(evidence.get("played_san") or ""),
        ),
        "",
    )


def _safe_missed_capture(
    fen: str,
    best_token: str,
) -> Dict[str, Any] | None:
    board = chess.Board(fen)
    move = parse_move(board, best_token)
    victim = _capture(board, move)
    if not victim or victim["value_cp"] < 100:
        return None
    destination = move.to_square
    board.push(move)
    recaptures = [
        reply
        for reply in board.legal_moves
        if board.is_capture(reply) and reply.to_square == destination
    ]
    if recaptures:
        return None
    return victim


def _fork_targets(
    fen: str,
    best_token: str,
) -> list[Dict[str, Any]]:
    board = chess.Board(fen)
    mover = board.turn
    move = parse_move(board, best_token)
    if board.is_capture(move):
        return []
    board.push(move)
    piece = board.piece_at(move.to_square)
    if piece is None or piece.color != mover:
        return []
    if any(
        reply.to_square == move.to_square and board.is_capture(reply)
        for reply in board.legal_moves
    ):
        return []
    targets = []
    for square in board.attacks(move.to_square):
        target = board.piece_at(square)
        if (
            target is None
            or target.color == mover
            or target.piece_type == chess.PAWN
        ):
            continue
        targets.append({
            "piece": PIECE_NAMES[target.piece_type],
            "square": chess.square_name(square),
            "value_cp": PIECE_VALUE_CP[target.piece_type],
        })
    targets.sort(key=lambda item: (-item["value_cp"], item["square"]))
    if len(targets) < 2:
        return []
    if not any(item["piece"] == "king" for item in targets) and sum(
        item["value_cp"] for item in targets[:2]
    ) < 600:
        return []
    return targets[:2]


def adjudicate_evidence(
    evidence: Mapping[str, Any],
) -> Dict[str, Any]:
    """Adjudicate one engine-marked decision without product detectors."""
    try:
        fen = str(evidence["fen_before"])
        played = _line(
            fen,
            str(evidence.get("played_uci") or evidence["played_san"]),
            evidence.get("pv_after_played") or [],
        )
        best = _line(
            fen,
            str(evidence.get("best_move_uci") or evidence["best_move_san"]),
            evidence.get("pv_after_best") or [],
        )
        root = chess.Board(fen)
        mover_name = "White" if root.turn == chess.WHITE else "Black"
    except Exception as exc:
        return {
            "evidence_verdict": "contradicted",
            "critical_false_claim": True,
            "reason": f"stored branch failed legal replay: {type(exc).__name__}",
        }

    played_reply = (
        played["steps"][1]
        if len(played["steps"]) > 1
        and played["steps"][1]["actor"] == "opponent"
        else None
    )
    played_capture = played["steps"][0]["capture"]
    if played["mate_for"] == "opponent":
        return {
            "evidence_verdict": "proved",
            "critical_false_claim": False,
            "cause_family": "allowed_forced_mate",
            "causal_chess_fact": (
                f"{evidence['played_san']} allowed the stored line to end "
                "in checkmate."
            ),
            "legal_settlement": [step["san"] for step in played["steps"]],
            "memory_cue": "Before moving, check every forcing reply: checks first.",
        }
    if best["mate_for"] == "mover":
        return {
            "evidence_verdict": "proved",
            "critical_false_claim": False,
            "cause_family": "missed_forced_mate",
            "causal_chess_fact": (
                f"{mover_name} had a forced checkmate beginning with "
                f"{evidence['best_move_san']}."
            ),
            "legal_settlement": [step["san"] for step in best["steps"]],
            "memory_cue": "When the king is exposed, calculate checks before anything else.",
        }
    if played_reply and played_reply["capture"]:
        lost = played_reply["capture"]
        gained = (played_capture or {}).get("value_cp", 0)
        if lost["value_cp"] - gained >= 100:
            return {
                "evidence_verdict": "proved",
                "critical_false_claim": False,
                "cause_family": "immediate_material_loss",
                "causal_chess_fact": (
                    f"After {evidence['played_san']}, "
                    f"{played_reply['san']} took the {lost['piece']} on "
                    f"{lost['square']}."
                ),
                "legal_settlement": [step["san"] for step in played["steps"]],
                "memory_cue": "After choosing a move, scan what the opponent can capture.",
            }
    missed = _safe_missed_capture(
        fen,
        str(evidence.get("best_move_uci") or evidence["best_move_san"]),
    )
    if missed:
        return {
            "evidence_verdict": "proved",
            "critical_false_claim": False,
            "cause_family": "safe_missed_capture",
            "causal_chess_fact": (
                f"{evidence['best_move_san']} could take the "
                f"{missed['piece']} on {missed['square']} without an "
                "immediate recapture."
            ),
            "legal_settlement": [step["san"] for step in best["steps"]],
            "memory_cue": "Before planning, look for an undefended piece you can take.",
        }
    targets = _fork_targets(
        fen,
        str(evidence.get("best_move_uci") or evidence["best_move_san"]),
    )
    if targets and best["material_delta_cp"] - played["material_delta_cp"] >= 200:
        return {
            "evidence_verdict": "proved",
            "critical_false_claim": False,
            "cause_family": "fork_geometry",
            "causal_chess_fact": (
                f"{evidence['best_move_san']} attacked the "
                f"{targets[0]['piece']} on {targets[0]['square']} and the "
                f"{targets[1]['piece']} on {targets[1]['square']} together."
            ),
            "legal_settlement": [step["san"] for step in best["steps"]],
            "memory_cue": "Before committing, look for one move that attacks two targets.",
        }
    best_move = parse_move(root, str(
        evidence.get("best_move_uci") or evidence["best_move_san"]
    ))
    if best_move.promotion and best["material_delta_cp"] > played["material_delta_cp"]:
        return {
            "evidence_verdict": "proved",
            "critical_false_claim": False,
            "cause_family": "promotion_race",
            "causal_chess_fact": (
                f"{evidence['best_move_san']} promoted the pawn in the "
                "stored line."
            ),
            "legal_settlement": [step["san"] for step in best["steps"]],
            "memory_cue": "In a pawn race, count moves to promotion before moving.",
        }
    return {
        "evidence_verdict": "unsupported",
        "critical_false_claim": False,
        "reason": (
            "The stored evaluation proves a move difference, but this "
            "packet does not prove a reusable causal lesson."
        ),
        "played_line_material_delta_cp": played["material_delta_cp"],
        "best_line_material_delta_cp": best["material_delta_cp"],
    }


def _priority(evidence: Mapping[str, Any]) -> tuple[int, int, int]:
    return (
        1 if evidence.get("is_critical") else 0,
        int(evidence.get("cp_loss") or 0),
        -int(evidence.get("ply") or 0),
    )


def adjudicate_game(game: Mapping[str, Any]) -> Dict[str, Any]:
    threshold = RATING_THRESHOLDS[str(game["rating_band"])]
    candidates = [
        item
        for item in game.get("stored_engine_evidence") or []
        if int(item.get("cp_loss") or 0) >= threshold
    ]
    candidates.sort(key=_priority, reverse=True)
    moments = []
    used_plies = []
    unsupported = 0
    for evidence in candidates:
        if any(abs(int(evidence["ply"]) - ply) <= 2 for ply in used_plies):
            continue
        verdict = adjudicate_evidence(evidence)
        if verdict["evidence_verdict"] != "proved":
            unsupported += 1
            continue
        phase = _phase_for(game, evidence)
        if phase not in {"opening", "middlegame", "endgame"}:
            raise ValueError("selected evidence lacks its stored phase")
        moments.append({
            "actor": evidence["actor"],
            "ply": int(evidence["ply"]),
            "side_to_move": (
                "white" if chess.Board(evidence["fen_before"]).turn else "black"
            ),
            "phase": phase,
            "played_decision": evidence["played_san"],
            "proposed_alternative": evidence["best_move_san"],
            "cp_loss": int(evidence.get("cp_loss") or 0),
            **verdict,
        })
        used_plies.append(int(evidence["ply"]))
        if len(moments) == 3:
            break

    phases = sorted({
        str(item.get("phase"))
        for item in game.get("stored_phase_rows") or []
        if item.get("phase")
    })
    central = None
    if moments:
        source = moments[0]
        central = {
            "phase": source["phase"],
            "source_ply": source["ply"],
            "cause_family": source["cause_family"],
            "statement": source["causal_chess_fact"],
        }
    return {
        "anonymous_game_key": game["anonymous_game_key"],
        "anonymous_player_key": game["anonymous_player_key"],
        "rating_band": game["rating_band"],
        "phases_reached": phases,
        "central_story": central,
        "no_provable_central_story": central is None,
        "moments": sorted(moments, key=lambda item: item["ply"]),
        "candidate_decisions_considered": len(candidates),
        "unsupported_candidate_decisions": unsupported,
    }


def build_worksheet(packet: Mapping[str, Any], packet_sha256: str) -> Dict[str, Any]:
    if packet.get("schema_version") != EXPECTED_PACKET_SCHEMA:
        raise ValueError("unexpected packet schema")
    if packet.get("membership_sha256") != EXPECTED_MEMBERSHIP:
        raise ValueError("development membership changed")
    if packet.get("sample") != "development" or packet.get("blinded") is not True:
        raise ValueError("only the blinded development packet may be adjudicated")
    games = packet.get("games")
    if not isinstance(games, list) or len(games) != 100:
        raise ValueError("development packet must contain exactly 100 games")
    rows = [adjudicate_game(game) for game in games]
    keys = [row["anonymous_game_key"] for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate anonymous game")
    moments = [moment for row in rows for moment in row["moments"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "codex_manual_review_required",
        "source": {
            "packet_schema_version": packet["schema_version"],
            "packet_sha256": packet_sha256,
            "membership_sha256": packet["membership_sha256"],
            "games": 100,
        },
        "method": (
            "Detector-blind legal replay of complete games and stored branches. "
            "No ChessGuru caption, selected event, detector label, engine run "
            "or model call was used. This worksheet is not gold until Codex "
            "reviews every proposed cause and freezes the file."
        ),
        "summary": {
            "games": len(rows),
            "games_with_proved_story": sum(
                not row["no_provable_central_story"] for row in rows
            ),
            "proved_moments": len(moments),
            "cause_family": dict(sorted(Counter(
                moment["cause_family"] for moment in moments
            ).items())),
            "critical_false_claims": sum(
                bool(moment["critical_false_claim"]) for moment in moments
            ),
        },
        "games": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    worksheet = build_worksheet(packet, _packet_sha256(args.packet))
    print(json.dumps(worksheet, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
