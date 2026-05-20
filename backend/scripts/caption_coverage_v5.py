"""Caption coverage audit — measures how often V5 blunder captions
surface specific tactical content vs fall back to generic phrasings.

Run inside the backend container:

    docker exec chess-coach-backend python /app/backend/scripts/caption_coverage_v5.py
    docker exec chess-coach-backend python /app/backend/scripts/caption_coverage_v5.py --sample 100
    docker exec chess-coach-backend python /app/backend/scripts/caption_coverage_v5.py --user user_8b599930d7ef

The audit walks `decryption_v5_data` for a sample of games, picks user
moves with cp_loss >= 100 (the R12_blunder threshold), and classifies
the caption's why-clause by template-match:

  HIGH specificity (named tactical concept):
    - why_user_missed_mate              ('mate in N')
    - why_user_missed_piece             ('wins the {piece} on {sq}')
    - why_user_missed_clearance_attack  ('clears the line — your slider...')
    - why_user_missed_king_pawn_pressure ('keeps the pressure on {sq}')

  MID specificity (concrete consequence):
    - why_user_attacks_played, hanging, capture, check, exchange_losing

  LOW specificity (generic fallback):
    - why_user_missed_material   ('wins material in the resulting line')
    - why_user_reply             ('Opponent's strongest reply:')

  NONE (silent / no why-clause):
    - bare severity caption ('Ng1 is a serious mistake. Nxe5 was better.')

The output:
  1. Aggregate counts + percentages per tier
  2. Per-template frequency table
  3. Sample LOW-specificity positions (game_id + move + FEN + caption)
     — these are the positions worth authoring better content for

This is the FREQUENCY-PRIORITIZED CONTENT BACKLOG. Don't author
patterns blindly — author the ones that appear most in LOW-specificity
captions.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

# Make `services.*` importable when this script runs from /app/backend/scripts
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.motor_asyncio import AsyncIOMotorClient

# Shared classifier — auto-loads every variant from data/captions/.
# See services/caption_classifier.py for the regex+tier map.
from services.caption_classifier import classifier as _classifier


def classify_caption(caption: str, rule_name: str = "") -> Tuple[str, str, Optional[str]]:
    """Return (tier, variant_key, json_path) for a caption. Uses
    rule_name (when provided) to route to the correct JSON file
    before matching variants — eliminates identical-structure
    template clashes."""
    r = _classifier.classify(caption, rule_name=rule_name)
    return (r["tier"], r["variant_key"], r["json_path"])


# ── Audit ────────────────────────────────────────────────────────────

async def audit(sample_size: int, user_filter: Optional[str], force_regen: bool) -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    from services.game_decryption_v5_service import (
        generate_game_decryption_v5, V5_COACHING_VERSION,
    )
    from datetime import datetime, timezone

    # Pick recently-analyzed games with V5 data
    query: Dict[str, Any] = {"decryption_v5_data": {"$exists": True, "$ne": None}}
    if user_filter:
        query["user_id"] = user_filter

    games = []
    cursor = (db.game_analyses.find(
        query, {"_id": 0, "game_id": 1, "user_id": 1, "decryption_v5_data": 1, "decryption_v5_version": 1}
    ).sort("created_at", -1).limit(sample_size))
    async for g in cursor:
        games.append(g)

    if not games:
        print("No analyzed games found. Exiting.")
        return

    # Force regenerate any game whose stored V5 version is below the
    # currently-shipped V5_COACHING_VERSION. Without this the audit
    # measures stale cached captions, not what current code produces.
    # Default: force-regen on (use --no-force-regen to measure the
    # historical cache instead).
    if force_regen:
        stale_games = [g for g in games if g.get("decryption_v5_version", 0) < V5_COACHING_VERSION]
        if stale_games:
            print(f"Forcing regen of {len(stale_games)}/{len(games)} stale games at v{V5_COACHING_VERSION}...")
            for i, g in enumerate(stale_games):
                gid = g["game_id"]
                full_game = await db.games.find_one({"game_id": gid}, {"_id": 0, "pgn": 1, "user_color": 1, "user_id": 1})
                full_analysis = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
                if not full_game or not full_analysis:
                    continue
                sa = full_analysis.get("stockfish_analysis") or {}
                move_evals = sa.get("move_evaluations") or sa.get("moves") or []
                if not full_game.get("pgn") or not move_evals:
                    continue
                try:
                    new_v5 = await generate_game_decryption_v5(
                        full_game["pgn"],
                        full_game.get("user_color", "white"),
                        move_evals,
                        full_game.get("user_id") or "",
                        db,
                    )
                except Exception as exc:
                    print(f"  [{i+1}/{len(stale_games)}] {gid[:8]} regen failed: {exc}")
                    continue
                if not new_v5:
                    continue
                await db.game_analyses.update_one(
                    {"game_id": gid},
                    {"$set": {
                        "decryption_v5_data": new_v5,
                        "decryption_v5_version": V5_COACHING_VERSION,
                        "decryption_v5_generated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                # Update in-memory game with fresh data so the
                # classification pass below measures it.
                g["decryption_v5_data"] = new_v5
                g["decryption_v5_version"] = V5_COACHING_VERSION
                if (i + 1) % 5 == 0:
                    print(f"  [{i+1}/{len(stale_games)}] regenerated...")
            print(f"Regen complete. All {len(games)} games at v{V5_COACHING_VERSION}.")
            print()

    # Walk EVERY user move with a caption — full-coverage audit
    # across all 20 caption JSON files, not just blunders.
    by_tier = Counter()
    by_file_tier: Dict[str, Counter] = {}  # per-file tier breakdown
    by_template = Counter()
    json_path_for_template: Dict[Tuple[str, str], Optional[str]] = {}
    version_dist = Counter()
    low_examples: List[Dict[str, Any]] = []
    none_examples: List[Dict[str, Any]] = []
    total_moves = 0
    silent_moves = 0

    for game in games:
        gid = game["game_id"]
        version_dist[game.get("decryption_v5_version", "unknown")] += 1
        for m in game.get("decryption_v5_data") or []:
            if not m.get("is_user_move"):
                continue
            cap = m.get("caption") or ""
            if not cap:
                silent_moves += 1
                continue
            total_moves += 1
            tier, key, jp = classify_caption(cap, rule_name=m.get("rule_name", ""))
            by_tier[tier] += 1
            by_template[(tier, key)] += 1
            json_path_for_template[(tier, key)] = jp
            file_name = jp.split(" ")[0] if jp else "(unclassified)"
            by_file_tier.setdefault(file_name, Counter())[tier] += 1

            sample = {
                "game_id": gid[:8],
                "move_number": m.get("move_number"),
                "move_san": m.get("move_san"),
                "cp_loss": m.get("cp_loss") or 0,
                "fen_before": m.get("fen_before"),
                "caption": cap,
                "rule_name": m.get("rule_name"),
            }
            if tier == "LOW" and len(low_examples) < 15:
                low_examples.append(sample)
            elif tier == "NONE" and len(none_examples) < 10:
                none_examples.append(sample)

    # ── Print report ────────────────────────────────────────────────
    print(f"Games scanned: {len(games)}")
    print(f"V5 version distribution: {dict(version_dist)}")
    print(f"User moves with captions: {total_moves}")
    print(f"User moves silent (no caption): {silent_moves}")
    print()

    if not total_moves:
        print("No blunder moves found — nothing to classify.")
        return

    print("=" * 60)
    print("COVERAGE BY TIER")
    print("=" * 60)
    for tier in ("HIGH", "MID", "LOW", "NONE"):
        n = by_tier[tier]
        pct = 100.0 * n / total_moves
        bar = "█" * int(pct / 2)
        print(f"  {tier:5} {n:5d} ({pct:5.1f}%)  {bar}")
    print()
    high_pct = 100.0 * by_tier["HIGH"] / total_moves
    print(f"Specific-content rate (HIGH): {high_pct:.1f}%")
    print(f"Fallback rate (LOW + NONE):   {100.0 * (by_tier['LOW'] + by_tier['NONE']) / total_moves:.1f}%")
    print()

    # Per-file breakdown
    print("=" * 60)
    print("PER-FILE COVERAGE (each JSON file in backend/data/captions/)")
    print("=" * 60)
    for file_name in sorted(by_file_tier.keys(), key=lambda f: -sum(by_file_tier[f].values())):
        counts = by_file_tier[file_name]
        total = sum(counts.values())
        tier_str = " ".join(
            f"{t}={counts.get(t, 0)}"
            for t in ("HIGH", "MID", "LOW", "NONE")
        )
        print(f"  {file_name:40} {total:4d}  ({tier_str})")
    print()

    print("=" * 60)
    print("PER-TEMPLATE FREQUENCY (authoring backlog — edit the JSON path to improve)")
    print("=" * 60)
    for (tier, key), n in by_template.most_common():
        pct = 100.0 * n / total_moves
        jp = json_path_for_template.get((tier, key)) or "(no JSON edit — needs new detector)"
        print(f"  [{tier}] {key:30} {n:5d} ({pct:5.1f}%)")
        print(f"         → {jp}")
    print()

    # Top-3 authoring targets, weighted by frequency and tier urgency.
    print("=" * 60)
    print("TOP AUTHORING TARGETS (highest leverage edits)")
    print("=" * 60)
    # Score = pct × urgency where urgency: NONE=3, LOW=2, MID=1, HIGH=0
    URGENCY = {"NONE": 3, "LOW": 2, "MID": 1, "HIGH": 0}
    ranked = sorted(
        by_template.items(),
        key=lambda kv: (URGENCY.get(kv[0][0], 0), kv[1]),
        reverse=True,
    )
    for i, ((tier, key), n) in enumerate(ranked[:5]):
        if URGENCY.get(tier, 0) == 0:
            continue  # skip HIGH tier — already good
        pct = 100.0 * n / total_moves
        jp = json_path_for_template.get((tier, key)) or "(needs new detector)"
        print(f"  #{i+1}. [{tier}] {key} — {n} hits ({pct:.1f}%)")
        print(f"      Edit: {jp}")
        print()

    print("=" * 60)
    print("LOW-SPECIFICITY SAMPLE POSITIONS (generic fallback fired)")
    print("These are content-authoring candidates — what's the right caption?")
    print("=" * 60)
    for s in low_examples:
        print(f"  game {s['game_id']} m{s['move_number']} {s['move_san']} cp={s['cp_loss']}")
        print(f"    FEN: {s['fen_before']}")
        print(f"    CAPTION: {s['caption']}")
        print()

    if none_examples:
        print("=" * 60)
        print("NONE / bare-severity captions (no why-clause)")
        print("=" * 60)
        for s in none_examples:
            print(f"  game {s['game_id']} m{s['move_number']} {s['move_san']} cp={s['cp_loss']}")
            print(f"    CAPTION: {s['caption']}")
            print()


def main():
    parser = argparse.ArgumentParser(description="V5 caption coverage audit")
    parser.add_argument("--sample", type=int, default=50, help="Number of games to scan (default 50)")
    parser.add_argument("--user", type=str, default=None, help="Restrict to one user_id")
    parser.add_argument(
        "--no-force-regen", action="store_true",
        help="Skip force-regen; measure whatever's stored (use only to compare historical cache vs current code).",
    )
    args = parser.parse_args()
    asyncio.run(audit(args.sample, args.user, not args.no_force_regen))


if __name__ == "__main__":
    main()
