"""
audit_trap_firing.py — measure current trap-caption firing across the
corpus + identify gaps before adding the victim-warning feature.

Reports:
  1. Total moves where trap_record is set (any step_label)
  2. Breakdown by step_label (setup_completed / victim_falls /
     trap_player_punishes)
  3. Breakdown by who completed the setup (user vs opp)
  4. Per-trap firing counts — which traps actually appear in real games
  5. Coverage gap: how many setup_completed fires would qualify as a
     victim WARNING moment (user is the victim side), and how many of
     those traps have trap_color filled in vs are unknown

Run inside the backend container:
  docker exec chess-coach-backend bash -c \\
    "cd /app/backend && python -m scripts.audit_trap_firing"
"""
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient


def _load_traps_with_color() -> Dict[str, Dict[str, Any]]:
    """Return {trap_name: trap_dict} with the trap_color field surfaced.
    Many entries leave trap_color blank — track that gap."""
    path = "/app/backend/data/traps.json"
    with open(path, encoding="utf-8") as f:
        tree = json.load(f)
    out: Dict[str, Dict[str, Any]] = {}
    for opening, traps in tree.items():
        if not isinstance(traps, list):
            continue
        for t in traps:
            name = t.get("name")
            if not name:
                continue
            out[name] = {
                "opening": opening,
                "trap_color": t.get("trap_color") or None,
                "setup_moves": t.get("setup_moves") or [],
                "trap_line": t.get("trap_line") or [],
            }
    return out


async def main() -> None:
    traps_meta = _load_traps_with_color()
    print(f"Loaded {len(traps_meta)} traps from data/traps.json")
    with_color = sum(1 for t in traps_meta.values() if t["trap_color"])
    print(f"  with trap_color field    : {with_color}")
    print(f"  WITHOUT trap_color field : {len(traps_meta) - with_color}")
    print()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client["chess_coach"]

    total_games = 0
    games_with_any_trap = 0
    total_trap_records = 0
    by_step: Dict[str, int] = {}
    by_trap_name: Dict[str, int] = {}
    setup_completed_user_victim: int = 0
    setup_completed_user_setter: int = 0
    setup_completed_opp_either: int = 0
    setup_completed_unknown_color: int = 0

    # Stream games one at a time to avoid loading all 4,974 v5 docs
    # into memory (got OOM-killed on first run).
    cursor = db.game_analyses.find(
        {"decryption_v5_data": {"$exists": True}},
        {"_id": 0, "game_id": 1, "decryption_v5_data": 1, "user_color": 1},
    )
    print("Streaming games (no preload)...")
    print()

    async for doc in cursor:
        total_games += 1
        had_trap = False
        moves = doc.get("decryption_v5_data") or []
        if not isinstance(moves, list):
            continue
        for m in moves:
            t = m.get("trap")
            if not t:
                continue
            had_trap = True
            total_trap_records += 1
            step = t.get("step_label") or "unknown"
            by_step[step] = by_step.get(step, 0) + 1
            tname = t.get("name") or "?"
            by_trap_name[tname] = by_trap_name.get(tname, 0) + 1
            if step == "setup_completed":
                this_by_user = bool(t.get("this_move_by_user"))
                meta = traps_meta.get(tname) or {}
                tc = meta.get("trap_color")
                if not tc:
                    setup_completed_unknown_color += 1
                    continue
                # Who completed setup?
                is_white_move = bool(m.get("is_white"))
                completer = "white" if is_white_move else "black"
                victim_color = "black" if tc == "white" else "white"
                if this_by_user:
                    if completer == victim_color:
                        setup_completed_user_victim += 1
                    else:
                        setup_completed_user_setter += 1
                else:
                    setup_completed_opp_either += 1
        if had_trap:
            games_with_any_trap += 1

    print("=" * 72)
    print("TRAP CAPTION FIRING AUDIT")
    print("=" * 72)
    print(f"Games scanned                 : {total_games}")
    print(f"Games with at least one trap  : {games_with_any_trap} "
          f"({100*games_with_any_trap/max(total_games,1):.1f}%)")
    print(f"Total trap records (any step) : {total_trap_records}")
    print()
    print("Breakdown by step_label:")
    for step, n in sorted(by_step.items(), key=lambda x: -x[1]):
        print(f"  {step}: {n}")
    print()
    print("setup_completed breakdown by user role (when trap_color is known):")
    print(f"  user is VICTIM (warning opportunity) : {setup_completed_user_victim}")
    print(f"  user is SETTER (existing 'you set up'): {setup_completed_user_setter}")
    print(f"  opp completed setup                   : {setup_completed_opp_either}")
    print(f"  setup with no trap_color (gap)        : {setup_completed_unknown_color}")
    print()
    print("Top 20 traps by firing frequency:")
    for name, n in sorted(by_trap_name.items(), key=lambda x: -x[1])[:20]:
        meta = traps_meta.get(name) or {}
        tc = meta.get("trap_color") or "?"
        print(f"  {n:>4}× {name} (trap_color={tc})")


if __name__ == "__main__":
    asyncio.run(main())
