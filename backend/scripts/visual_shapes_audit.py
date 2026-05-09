"""
Visual-shape detector audit.

Same rigor as cognitive_gap_audit.py — walks N analyzed games, runs the
shape detectors with their built-in verifiers, reports distribution +
manual-inspection samples.

For Rule 1 (queen_too_early) the verifier is already inside the detector
(queen must be chased within 4 plies). The audit reports every fire so
we can eyeball whether the verifier catches the real cases without
firing on safe Qh5/Qxd5 etc.

Usage:
    python scripts/visual_shapes_audit.py --output /tmp/shapes_audit.txt
    python scripts/visual_shapes_audit.py --limit 1000
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

from services.visual_shapes import detect_shapes_for_move

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

SHAPE_LOOKAHEAD = 6  # mirrors interpret_moves slice size


async def run(args) -> str:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations": {"$exists": True, "$ne": []}},
        {
            "_id": 0,
            "game_id": 1,
            "stockfish_analysis.move_evaluations": 1,
        },
    )
    if args.limit:
        cursor = cursor.limit(args.limit)

    shape_total: Counter = Counter()
    samples: Dict[str, List[Dict]] = defaultdict(list)
    games_processed = 0
    games_with_any_shape = 0
    moves_seen = 0

    async for ga in cursor:
        sa = ga.get("stockfish_analysis") or {}
        moves = sa.get("move_evaluations") or []
        if not moves:
            continue

        # Per-game dedup: only the FIRST occurrence of each shape type
        # surfaces. Mirrors the dedup pass in analysis_interpreter so the
        # audit numbers match what users see.
        seen_types_in_game: set = set()
        game_had_shape = False
        for idx, me in enumerate(moves):
            moves_seen += 1
            future = moves[idx + 1: idx + 1 + SHAPE_LOOKAHEAD]
            shapes = detect_shapes_for_move(me, future) or []
            for shape in shapes:
                stype = shape["type"]
                if stype in seen_types_in_game:
                    continue  # already counted earlier in this game
                seen_types_in_game.add(stype)
                shape_total[stype] += 1
                game_had_shape = True
                if len(samples[stype]) < args.samples_per_type:
                    samples[stype].append({
                        "game_id": ga.get("game_id", "?"),
                        "move_number": me.get("move_number"),
                        "move_san": me.get("move_san") or me.get("move"),
                        "fen_before": (me.get("fen_before") or "")[:80],
                        "evidence": shape.get("evidence", ""),
                        "coach": shape.get("coach_line", ""),
                        "future_moves": [
                            (fm.get("move_san") or fm.get("move"))
                            for fm in future
                        ],
                    })

        if game_had_shape:
            games_with_any_shape += 1
        games_processed += 1
        if games_processed % 100 == 0:
            print(f"  ... {games_processed} games processed", flush=True)

    client.close()

    # ── Build report ────────────────────────────────────────────────
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("VISUAL SHAPES — DETECTOR AUDIT")
    lines.append("=" * 78)
    lines.append(f"  games processed:        {games_processed}")
    lines.append(f"  moves walked:           {moves_seen}")
    lines.append(f"  games with any shape:   {games_with_any_shape}")
    lines.append(f"  shape fires (total):    {sum(shape_total.values())}")
    lines.append("")

    lines.append("SHAPE DISTRIBUTION:")
    lines.append("-" * 78)
    if shape_total:
        for shape_type, n in shape_total.most_common():
            pct_games = 100.0 * n / max(games_processed, 1)
            lines.append(f"  {n:6d}  {shape_type}  ({pct_games:.1f}% of games — multiple fires possible)")
    else:
        lines.append("  (no shapes detected)")
    lines.append("")

    if samples:
        lines.append("SAMPLE FIRES (for manual verification):")
        lines.append("-" * 78)
        for shape_type, sample_list in samples.items():
            lines.append(f"\n  {shape_type}:")
            for s in sample_list:
                lines.append(f"    game={s['game_id']} move={s['move_number']} {s['move_san']}")
                lines.append(f"      coach: {s['coach']}")
                lines.append(f"      evidence: {s['evidence']}")
                lines.append(f"      next plies: {s['future_moves']}")
                lines.append(f"      fen: {s['fen_before']}")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=1000, help="cap to first N analyzed games")
    p.add_argument("--samples-per-type", type=int, default=20, help="how many fires to print per shape type")
    p.add_argument("--output", default=None)
    args = p.parse_args()

    report = asyncio.run(run(args))
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\nReport written to {args.output}")
    print(report)
