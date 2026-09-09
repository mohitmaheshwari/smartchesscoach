#!/usr/bin/env python3
"""Attach reproducible Stockfish evidence to the positional-reason queue.

The output is an offline authoring artifact. It does not mutate MongoDB or make
captions eligible at runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import chess
import chess.engine


MATE_SCORE = 100_000


def san_line(board: chess.Board, pv: list[chess.Move], plies: int = 10) -> list[str]:
    copy = board.copy()
    result: list[str] = []
    for move in pv[:plies]:
        if move not in copy.legal_moves:
            break
        result.append(copy.san(move))
        copy.push(move)
    return result


def score_payload(board: chess.Board, info: dict[str, Any]) -> dict[str, Any]:
    pov = info["score"].pov(board.turn)
    wdl = info["score"].wdl(model="sf", ply=board.ply()).pov(board.turn)
    pv = list(info.get("pv") or [])
    return {
        "score_cp": pov.score(mate_score=MATE_SCORE),
        "mate": pov.mate(),
        "wdl": {"wins": wdl.wins, "draws": wdl.draws, "losses": wdl.losses},
        "first_uci": pv[0].uci() if pv else None,
        "pv_uci": [move.uci() for move in pv[:10]],
        "pv_san": san_line(board, pv),
        "depth": info.get("depth"),
        "seldepth": info.get("seldepth"),
        "nodes": info.get("nodes"),
    }


def move_facts(board: chess.Board, uci: str) -> dict[str, Any]:
    move = chess.Move.from_uci(uci)
    piece = board.piece_at(move.from_square)
    if piece is None or move not in board.legal_moves:
        raise ValueError(f"illegal stored move {uci}")
    captured = board.piece_at(move.to_square)
    if board.is_en_passant(move):
        captured = chess.Piece(chess.PAWN, not board.turn)
    before_attackers = [chess.square_name(s) for s in board.attackers(not board.turn, move.to_square)]
    copy = board.copy()
    copy.push(move)
    own_defenders = [chess.square_name(s) for s in copy.attackers(not copy.turn, move.to_square)]
    enemy_attackers = [chess.square_name(s) for s in copy.attackers(copy.turn, move.to_square)]
    return {
        "uci": uci,
        "san": board.san(move),
        "piece": chess.piece_name(piece.piece_type),
        "from": chess.square_name(move.from_square),
        "to": chess.square_name(move.to_square),
        "capture": board.is_capture(move),
        "captured_piece": chess.piece_name(captured.piece_type) if captured else None,
        "check": copy.is_check(),
        "castle": board.is_castling(move),
        "promotion": chess.piece_name(move.promotion) if move.promotion else None,
        "destination_attacked_before": before_attackers,
        "destination_defended_after": own_defenders,
        "destination_attacked_after": enemy_attackers,
    }


def material(board: chess.Board) -> dict[str, dict[str, int]]:
    names = {
        chess.PAWN: "pawn",
        chess.KNIGHT: "knight",
        chess.BISHOP: "bishop",
        chess.ROOK: "rook",
        chess.QUEEN: "queen",
    }
    return {
        color_name: {
            names[piece_type]: len(board.pieces(piece_type, color))
            for piece_type in names
        }
        for color_name, color in (("white", chess.WHITE), ("black", chess.BLACK))
    }


def enrich_row(engine: chess.engine.SimpleEngine, row: dict[str, Any], nodes: int) -> dict[str, Any]:
    board = chess.Board(row["fen"])
    played = chess.Move.from_uci(row["played_uci"])
    best = chess.Move.from_uci(row["best_uci"])
    if played not in board.legal_moves or best not in board.legal_moves:
        raise ValueError("stored played/best move is illegal")

    root_infos = engine.analyse(board, chess.engine.Limit(nodes=nodes), multipv=min(5, board.legal_moves.count()))
    played_info = engine.analyse(
        board,
        chess.engine.Limit(nodes=nodes),
        root_moves=[played],
    )
    lines = [score_payload(board, info) for info in root_infos]
    forced_played = score_payload(board, played_info)
    fresh_best = lines[0]["first_uci"] if lines else None
    best_score = lines[0]["score_cp"] if lines else None
    second_score = lines[1]["score_cp"] if len(lines) > 1 else None
    played_score = forced_played["score_cp"]

    enriched = dict(row)
    enriched["engine_evidence"] = {
        "engine": engine.id.get("name", "Stockfish"),
        "nodes_per_search": nodes,
        "root_top_lines": lines,
        "played_line": forced_played,
        "fresh_best_uci": fresh_best,
        "stored_best_is_fresh_best": fresh_best == row["best_uci"],
        "best_to_second_margin_cp": (
            best_score - second_score
            if best_score is not None and second_score is not None
            else None
        ),
        "fresh_loss_cp": (
            max(0, best_score - played_score)
            if best_score is not None and played_score is not None
            else None
        ),
    }
    enriched["board_evidence"] = {
        "turn": "white" if board.turn else "black",
        "legal_move_count": board.legal_moves.count(),
        "in_check": board.is_check(),
        "material": material(board),
        "played": move_facts(board, row["played_uci"]),
        "best": move_facts(board, row["best_uci"]),
    }
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--engine", default="/usr/games/stockfish")
    parser.add_argument("--nodes", type=int, default=30_000)
    args = parser.parse_args()

    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = source["queue"] if isinstance(source, dict) else source
    output: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    engine = chess.engine.SimpleEngine.popen_uci(args.engine)
    try:
        engine.configure({"Threads": 2, "Hash": 128})
        for index, row in enumerate(rows, 1):
            try:
                output.append(enrich_row(engine, row, args.nodes))
            except Exception as exc:
                failed = dict(row)
                failed["engine_error"] = str(exc)
                output.append(failed)
                errors.append({"index": index, "fen": row.get("fen"), "error": str(exc)})
            if index % 10 == 0 or index == len(rows):
                print(json.dumps({"processed": index, "total": len(rows), "errors": len(errors)}), flush=True)
    finally:
        engine.quit()

    Path(args.output).write_text(
        json.dumps({"schema_version": "positional_engine_evidence.v1", "rows": output, "errors": errors}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
