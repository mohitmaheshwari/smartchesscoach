"""Does a SOUND-AND-FINDABLE alternative usually exist in the player's mistakes?

The strongest idea in the human-model pivot is "teach the strongest move a
target-level player could actually find, not the engine's top choice". That
feature only exists if, in real mistake positions, there is more than one
acceptable move -- otherwise the only sound reply IS the engine's first
choice, and there is no easier-but-still-good move to teach.

Stored move_evaluations carry best_move and two PVs but NO alternative
candidates, so nothing on disk can answer this. It needs multi-PV.

For each sampled mistake this measures the ALTERNATIVE HEADROOM: how many
distinct legal moves sit within a tolerance of the best move's evaluation.

  headroom = 1   only the engine move is acceptable -> nothing teachable
  headroom > 1   a human-findable second-best exists -> the feature is real

This deliberately does NOT call Maia. It measures the ceiling on what any
human model could pick from. If headroom is ~1 nearly everywhere, no
human-behaviour provider can rescue the feature and the work should stop.

    python backend/scripts/probe_teachable_move_headroom.py --sample 150
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import chess
import chess.engine
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = (
    BACKEND_ROOT / "data" / "corpus_snapshots" / "teachable_move_headroom.json"
)

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/games/stockfish")
MULTIPV = 5
DEPTH = 14
MISTAKE_CP_LOSS = 150           # matches the D_live floor

# A move is "acceptable" if it costs no more than this vs the best move.
TOLERANCES_CP = (50, 100)


def _cp(score: chess.engine.PovScore, pov: chess.Color) -> Optional[int]:
    s = score.pov(pov)
    if s.is_mate():
        return 10000 if (s.mate() or 0) > 0 else -10000
    return s.score()


async def sample_mistakes(db, sample: int) -> List[Dict[str, Any]]:
    """Distinct mistake positions, one per game, to avoid clustering."""
    out: List[Dict[str, Any]] = []
    seen_fen = set()
    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations.0": {"$exists": True}},
        {"game_id": 1, "user_id": 1, "stockfish_analysis.move_evaluations": 1},
    )
    async for doc in cursor:
        for mv in doc.get("stockfish_analysis", {}).get("move_evaluations", []):
            if mv.get("is_opponent_move"):
                continue
            try:
                loss = float(mv.get("cp_loss") or 0)
            except (TypeError, ValueError):
                continue
            fen = mv.get("fen_before")
            if loss < MISTAKE_CP_LOSS or not fen or not mv.get("move_uci"):
                continue
            key = fen.split(" ")[0]
            if key in seen_fen:
                continue
            seen_fen.add(key)
            out.append({
                "game_id": doc.get("game_id"),
                "fen_before": fen,
                "played_uci": mv.get("move_uci"),
                "played_san": mv.get("move"),
                "stored_cp_loss": loss,
                "stored_best": mv.get("best_move"),
            })
            break                      # one position per game
        if len(out) >= sample:
            break
    return out


def analyse(engine: chess.engine.SimpleEngine, case: Dict[str, Any]) -> Optional[Dict]:
    try:
        board = chess.Board(case["fen_before"])
    except ValueError:
        return None
    if not board.is_valid() or board.is_game_over():
        return None
    try:
        infos = engine.analyse(board, chess.engine.Limit(depth=DEPTH), multipv=MULTIPV)
    except chess.engine.EngineError:
        return None
    if not infos:
        return None

    mover = board.turn
    ranked = []
    for info in infos:
        pv = info.get("pv") or []
        if not pv:
            continue
        cp = _cp(info["score"], mover)
        if cp is None:
            continue
        ranked.append({"uci": pv[0].uci(), "san": board.san(pv[0]), "cp": cp})
    if not ranked:
        return None

    best_cp = ranked[0]["cp"]
    result = {
        "fen": case["fen_before"],
        "played_san": case["played_san"],
        "best_san": ranked[0]["san"],
        "candidates": ranked,
    }
    for tol in TOLERANCES_CP:
        acceptable = [r for r in ranked if best_cp - r["cp"] <= tol]
        result[f"headroom_{tol}"] = len(acceptable)
        # the teachable slot: an acceptable move that is NOT the engine's first
        result[f"alternatives_{tol}"] = max(0, len(acceptable) - 1)
    return result


async def main_async(sample: int) -> Dict[str, Any]:
    url = os.environ.get("MONGO_URL")
    if not url:
        raise SystemExit("MONGO_URL is required")
    client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=8000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]
    cases = await sample_mistakes(db, sample)
    client.close()

    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    rows: List[Dict[str, Any]] = []
    try:
        for case in cases:
            row = analyse(engine, case)
            if row:
                rows.append(row)
    finally:
        engine.quit()

    stats: Dict[str, Any] = {"analysed": len(rows), "sampled": len(cases)}
    for tol in TOLERANCES_CP:
        counts = Counter(r[f"headroom_{tol}"] for r in rows)
        with_alt = sum(1 for r in rows if r[f"alternatives_{tol}"] >= 1)
        stats[f"tol_{tol}"] = {
            "headroom_distribution": dict(sorted(counts.items())),
            "positions_with_a_teachable_alternative": with_alt,
            "pct_with_alternative": round(100 * with_alt / len(rows), 1) if rows else 0,
            "median_headroom": statistics.median(
                [r[f"headroom_{tol}"] for r in rows]) if rows else 0,
        }
    return {
        "schema_version": "teachable_move_headroom.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "params": {"multipv": MULTIPV, "depth": DEPTH,
                   "mistake_cp_loss": MISTAKE_CP_LOSS,
                   "tolerances_cp": list(TOLERANCES_CP)},
        "stats": stats,
        "rows": rows[:40],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=150)
    args = parser.parse_args()
    report = asyncio.run(main_async(args.sample))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=1), encoding="utf-8")

    s = report["stats"]
    print(f"mistake positions analysed: {s['analysed']} of {s['sampled']} sampled")
    for tol in TOLERANCES_CP:
        t = s[f"tol_{tol}"]
        print(f"--- within {tol}cp of best")
        print(f"    headroom distribution : {t['headroom_distribution']}")
        print(f"    median headroom       : {t['median_headroom']}")
        print(f"    HAS a teachable alt   : {t['positions_with_a_teachable_alternative']}"
              f" ({t['pct_with_alternative']}%)")
    print(f"written -> {OUT_PATH}")


if __name__ == "__main__":
    main()
