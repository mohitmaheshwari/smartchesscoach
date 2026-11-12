"""A tiny MCP server that gives the Why queue's agents a chess engine, nothing else.

    python backend/scripts/why_engine_mcp.py --engine PATH

Speaks MCP (JSON-RPC 2.0, one message per line) on stdin/stdout. No dependency
beyond python-chess. The agent gets two tools:

  analyse  the engine's best lines from a position (after optional SAN moves),
           at a depth it chooses, scores from both sides' point of view
  board    the board as text, material, check, and which pieces of each side
           are attacked with nothing guarding them

Why it exists (Mohit, 2026-11-12): the agents studied with no tools and one turn,
reasoning over a fixed depth-20 packet. A shallow line in that packet misled the
checker on Bc5; with an engine it can check a line itself, as a person would.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import chess
import chess.engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MAX_DEPTH = 30
MAX_SECONDS = 25
MAX_LINES = 5
PV_PLIES = 12
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
NAMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook",
         chess.QUEEN: "queen", chess.KING: "king"}

TOOLS = [
    {
        "name": "analyse",
        "description": ("Stockfish's best lines from a position. Give the FEN of the position before the move "
                        "played and, optionally, SAN moves to play from it first (e.g. [\"Bc5\", \"c3\"]). Returns "
                        "each line as SAN moves (no move numbers) starting with the side to move, with its score in centipawns for White and for the side to move, and "
                        "mate when there is one. Depth 18-30 (default 22); deeper is slower."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "fen": {"type": "string"},
                "moves": {"type": "array", "items": {"type": "string"}},
                "depth": {"type": "integer", "minimum": 8, "maximum": MAX_DEPTH},
                "lines": {"type": "integer", "minimum": 1, "maximum": MAX_LINES},
            },
            "required": ["fen"],
        },
    },
    {
        "name": "board",
        "description": ("The position (after optional SAN moves) as text: the board, whose move, material for each "
                        "side, whether the side to move is in check, its legal moves, and every piece of each side "
                        "that is attacked with nothing guarding it."),
        "inputSchema": {
            "type": "object",
            "properties": {"fen": {"type": "string"}, "moves": {"type": "array", "items": {"type": "string"}}},
            "required": ["fen"],
        },
    },
]


def _position(fen: str, moves: Optional[List[str]]) -> chess.Board:
    board = chess.Board(fen)
    for i, san in enumerate(moves or []):
        try:
            board.push_san(str(san))
        except ValueError as exc:
            raise ValueError(f"move {i + 1} ({san}) is not legal here: {exc}") from None
    return board


def _score(score: chess.engine.PovScore, pov: chess.Color) -> Dict[str, Any]:
    s = score.pov(pov)
    return {"mate_in": s.mate()} if s.is_mate() else {"cp": s.score()}


def _material(board: chess.Board, color: chess.Color) -> Dict[str, Any]:
    pieces = {NAMES[p]: len(board.pieces(p, color)) for p in VALUES}
    return {"points": sum(VALUES[p] * len(board.pieces(p, color)) for p in VALUES), "pieces": pieces}


def _unguarded(board: chess.Board, color: chess.Color) -> List[str]:
    out = []
    for sq, piece in board.piece_map().items():
        if piece.color != color or piece.piece_type == chess.KING:
            continue
        if board.is_attacked_by(not color, sq) and not board.is_attacked_by(color, sq):
            out.append(f"{NAMES[piece.piece_type]} on {chess.square_name(sq)}")
    return out


class Engine:
    def __init__(self, path: str):
        self.path = path
        self.eng: Optional[chess.engine.SimpleEngine] = None

    def get(self) -> chess.engine.SimpleEngine:
        if self.eng is None:
            self.eng = chess.engine.SimpleEngine.popen_uci(self.path)
            try:
                self.eng.configure({"Threads": 2, "Hash": 256})
            except Exception:                           # noqa: BLE001
                pass
        return self.eng

    def close(self) -> None:
        if self.eng is not None:
            try:
                self.eng.quit()
            except Exception:                           # noqa: BLE001
                pass


def tool_analyse(engine: Engine, args: Dict[str, Any]) -> Dict[str, Any]:
    board = _position(args["fen"], args.get("moves"))
    if board.is_game_over():
        return {"game_over": board.result(claim_draw=True), "checkmate": board.is_checkmate()}
    depth = max(8, min(int(args.get("depth") or 22), MAX_DEPTH))
    lines = max(1, min(int(args.get("lines") or 3), MAX_LINES))
    infos = engine.get().analyse(board, chess.engine.Limit(depth=depth, time=MAX_SECONDS), multipv=lines)
    if isinstance(infos, dict):
        infos = [infos]
    out = []
    for info in infos:
        pv = info.get("pv") or []
        if not pv:
            continue
        # Plain SAN, no move numbers: the stored FENs carry none, so numbers would be wrong.
        walk, sans = board.copy(), []
        for move in pv[:PV_PLIES]:
            sans.append(walk.san(move))
            walk.push(move)
        out.append({"line": " ".join(sans),
                    "for_white": _score(info["score"], chess.WHITE),
                    "for_side_to_move": _score(info["score"], board.turn),
                    "depth": info.get("depth")})
    return {"side_to_move": "white" if board.turn else "black", "fen": board.fen(), "lines": out}


def tool_board(_engine: Engine, args: Dict[str, Any]) -> Dict[str, Any]:
    board = _position(args["fen"], args.get("moves"))
    return {
        "board": str(board),
        "side_to_move": "white" if board.turn else "black",
        "fen": board.fen(),
        "in_check": board.is_check(),
        "legal_moves": [board.san(m) for m in board.legal_moves],
        "material": {"white": _material(board, chess.WHITE), "black": _material(board, chess.BLACK)},
        "attacked_with_nothing_guarding": {"white": _unguarded(board, chess.WHITE),
                                           "black": _unguarded(board, chess.BLACK)},
    }


HANDLERS = {"analyse": tool_analyse, "board": tool_board}


def handle(engine: Engine, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One JSON-RPC message in, its reply out (None for a notification)."""
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion") or "2024-11-05"
        result: Dict[str, Any] = {"protocolVersion": version, "capabilities": {"tools": {}},
                                  "serverInfo": {"name": "chess", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = msg.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        if name not in HANDLERS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {name}"}}
        try:
            text, is_error = json.dumps(HANDLERS[name](engine, args)), False
        except Exception as exc:                        # noqa: BLE001
            text, is_error = f"{type(exc).__name__}: {exc}", True
        result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"no method {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    args = ap.parse_args()
    engine = Engine(args.engine)
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            reply = handle(engine, msg)
            if reply is not None:
                sys.stdout.write(json.dumps(reply) + "\n")
                sys.stdout.flush()
    finally:
        engine.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
