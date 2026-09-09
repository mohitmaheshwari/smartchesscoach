"""Produce reproducible Stockfish evidence for every legal trap-line step.

This is a research audit. It never edits ``traps.json`` and never promotes a
detector. Opening tags, authored prose, and Maia predictions are not chess
truth; the output records only reconstructable board and engine evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

import chess
import chess.engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.trap_library_audit import audit_trap_library_file
from stockfish_service import StockfishEngine


DEFAULT_TRAPS_PATH = BACKEND_DIR / "data" / "traps.json"


def _iter_traps(data: Dict[str, Any]) -> Iterable[tuple[str, Dict[str, Any]]]:
    for family, traps in data.items():
        if family.startswith("_") or not isinstance(traps, list):
            continue
        for trap in traps:
            if isinstance(trap, dict):
                yield family, trap


def _line_moves(trap: Dict[str, Any]) -> List[str]:
    return [
        str(step.get("move") or "") if isinstance(step, dict) else str(step or "")
        for step in (trap.get("trap_line") or [])
    ]


def _score(score: chess.engine.PovScore, color: chess.Color) -> Dict[str, int | None]:
    relative = score.pov(color)
    return {
        "cp_equivalent": relative.score(mate_score=100_000),
        "mate_in": relative.mate(),
    }


def _pv_san(board: chess.Board, pv: List[chess.Move], limit: int = 8) -> List[str]:
    result: List[str] = []
    copy = board.copy()
    for move in pv[:limit]:
        try:
            result.append(copy.san(move))
            copy.push(move)
        except Exception:
            break
    return result


def _distribution(values: List[int]) -> Dict[str, int | float | None]:
    if not values:
        return {"count": 0, "minimum": None, "median": None, "p75": None, "p90": None, "maximum": None}
    ordered = sorted(values)

    def percentile(fraction: float) -> int:
        return ordered[int(fraction * (len(ordered) - 1))]

    return {
        "count": len(ordered),
        "minimum": ordered[0],
        "median": statistics.median(ordered),
        "p75": percentile(0.75),
        "p90": percentile(0.90),
        "maximum": ordered[-1],
    }


def run_audit(
    traps_path: Path,
    stockfish_path: str,
    nodes: int,
    multipv: int,
) -> Dict[str, Any]:
    source_audit = audit_trap_library_file(traps_path)
    data = json.loads(traps_path.read_text(encoding="utf-8"))
    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    with StockfishEngine(path=stockfish_path, threads=1, hash_mb=128) as wrapper:
        engine = wrapper.engine
        engine_id = dict(engine.id)
        for family, trap in _iter_traps(data):
            entry = f"{family}/{trap.get('name') or '?'}"
            trap_color_name = str(trap.get("trap_color") or "").lower()
            if trap_color_name not in {"white", "black"}:
                errors.append({"entry": entry, "error": "invalid trap_color"})
                continue
            trap_color = chess.WHITE if trap_color_name == "white" else chess.BLACK
            setup = [str(move or "") for move in (trap.get("setup_moves") or [])]
            line = _line_moves(trap)
            board = chess.Board()
            sequence_ok = True

            for san in setup:
                try:
                    board.push_san(san)
                except Exception as exc:
                    errors.append({"entry": entry, "phase": "setup", "move": san, "error": str(exc)})
                    sequence_ok = False
                    break
            if not sequence_ok:
                continue

            for step_index, san in enumerate(line):
                fen_before = board.fen(en_passant="legal")
                mover = board.turn
                try:
                    authored_move = board.parse_san(san)
                except Exception as exc:
                    errors.append({
                        "entry": entry,
                        "phase": "trap_line",
                        "line_step_index": step_index,
                        "move": san,
                        "fen_before": fen_before,
                        "error": str(exc),
                    })
                    break

                legal_count = board.legal_moves.count()
                infos = engine.analyse(
                    board,
                    chess.engine.Limit(nodes=nodes),
                    multipv=min(max(1, multipv), legal_count),
                )
                if isinstance(infos, dict):
                    infos = [infos]
                alternatives: List[Dict[str, Any]] = []
                authored_info: Dict[str, Any] | None = None
                for info in infos:
                    pv = info.get("pv") or []
                    if not pv:
                        continue
                    item = {
                        "move_uci": pv[0].uci(),
                        "move_san": board.san(pv[0]),
                        "score": _score(info["score"], mover),
                        "pv_san": _pv_san(board, pv),
                    }
                    alternatives.append(item)
                    if pv[0] == authored_move:
                        authored_info = info

                if not alternatives:
                    errors.append({"entry": entry, "line_step_index": step_index, "error": "engine returned no PV"})
                    board.push(authored_move)
                    continue

                if authored_info is None:
                    authored_info = engine.analyse(
                        board,
                        chess.engine.Limit(nodes=nodes),
                        root_moves=[authored_move],
                    )
                best_score = alternatives[0]["score"]
                authored_score = _score(authored_info["score"], mover)
                best_cp = best_score["cp_equivalent"]
                authored_cp = authored_score["cp_equivalent"]
                cp_loss = None
                if best_cp is not None and authored_cp is not None:
                    cp_loss = max(0, best_cp - authored_cp)

                rows.append({
                    "entry": entry,
                    "family": family,
                    "trap_name": trap.get("name"),
                    "trap_color": trap_color_name,
                    "line_step_index": step_index,
                    "role": "setter" if mover == trap_color else "victim",
                    "side_to_move": "white" if mover else "black",
                    "fen_before": fen_before,
                    "authored_move_san": san,
                    "authored_move_uci": authored_move.uci(),
                    "authored_score": authored_score,
                    "best_score": best_score,
                    "cp_loss": cp_loss,
                    "top_alternatives": alternatives,
                })
                board.push(authored_move)

    setter_losses = [row["cp_loss"] for row in rows if row["role"] == "setter" and row["cp_loss"] is not None]
    victim_losses = [row["cp_loss"] for row in rows if row["role"] == "victim" and row["cp_loss"] is not None]
    return {
        "source": source_audit["source"],
        "engine": {
            "path": stockfish_path,
            "id": engine_id,
            "nodes_per_search": nodes,
            "threads": 1,
            "hash_mb": 128,
            "multipv": multipv,
            "mate_score_cp": 100_000,
        },
        "summary": {
            "scored_line_steps": len(rows),
            "errors": len(errors),
            "setter_authored_move_loss": _distribution(setter_losses),
            "victim_authored_move_loss": _distribution(victim_losses),
        },
        "errors": errors,
        "moves": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traps", type=Path, default=DEFAULT_TRAPS_PATH)
    parser.add_argument("--stockfish", default=os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish"))
    parser.add_argument("--nodes", type=int, default=20_000)
    parser.add_argument("--multipv", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.nodes <= 0 or args.multipv <= 0:
        parser.error("--nodes and --multipv must be positive")

    report = run_audit(args.traps, args.stockfish, args.nodes, args.multipv)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(json.dumps({"output": str(args.output), **report["summary"]}, indent=2))
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
