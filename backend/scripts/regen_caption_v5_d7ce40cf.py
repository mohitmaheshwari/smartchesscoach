"""
Side-by-side V5 caption pipeline review for game d7ce40cf.

Runs the live V5 decryption pipeline on game
`d7ce40cf-2856-4f1f-b61b-29167deef219` and prints, per move:

    move # | SAN | severity | LEGACY narrative | NEW caption | rule_name

Per the proof gate in `feedback_v5_caption_rewrite_no_patches.md`,
this is the corpus the user reviews before the new pipeline retires
the legacy dispatcher.

Usage (inside the backend container OR with backend/.env loadable):

    python scripts/regen_caption_v5_d7ce40cf.py
    python scripts/regen_caption_v5_d7ce40cf.py --game-id <other-id>
    python scripts/regen_caption_v5_d7ce40cf.py --write-to ../caption_v5_d7ce40cf.txt
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

DEFAULT_GAME_ID = "d7ce40cf-2856-4f1f-b61b-29167deef219"


def _shorten(text: Optional[str], n: int = 110) -> str:
    if not text:
        return ""
    s = str(text).replace("\n", " ").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _fmt_primary_reason(pr: Optional[Dict[str, Any]]) -> str:
    if not pr:
        return "—"
    cat = pr.get("category", "?")
    ref = pr.get("ref_field", "")
    return f"{cat}({ref})" if ref else cat


def _format_table(rows: List[Dict[str, Any]]) -> str:
    """Render move-by-move side-by-side review. Wraps long cells."""
    out_lines: List[str] = []
    header = (
        "─" * 132 + "\n"
        f"{'#':<3} {'side':<4} {'move':<7} {'sev':<11} {'rule_name':<27} "
        f"{'caption':<70}\n"
        f"{'':3} {'':4} {'':7} {'cp':<11} {'primary_reason':<27} "
        f"{'legacy narrative':<70}\n"
        + "─" * 132
    )
    out_lines.append(header)
    for r in rows:
        cap = _shorten(r.get("caption") or "(silent)", 70)
        leg = _shorten(r.get("narrative") or "(silent)", 70)
        rule = _shorten(r.get("rule_name") or "—", 27)
        pr = _shorten(_fmt_primary_reason(r.get("primary_reason")), 27)
        sev = _shorten(r.get("severity") or "—", 11)
        cpl = r.get("cp_loss")
        cpl_s = f"{cpl:>4}cpl" if cpl is not None else "—"
        side = "USER" if r.get("is_user_move") else "OPP"
        out_lines.append(
            f"{r['move_number']:<3} {side:<4} {_shorten(r.get('move_san'), 7):<7} "
            f"{sev:<11} {rule:<27} {cap:<70}"
        )
        out_lines.append(
            f"{'':3} {'':4} {'':7} {cpl_s:<11} {pr:<27} {leg:<70}"
        )
        out_lines.append("·" * 132)
    return "\n".join(out_lines)


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--game-id", default=DEFAULT_GAME_ID,
                   help=f"Game id to regenerate (default: {DEFAULT_GAME_ID}).")
    p.add_argument("--write-to", default=None,
                   help="Also write the full side-by-side dump to this path "
                        "(relative to repo root if not absolute).")
    p.add_argument("--no-db-write", action="store_true",
                   help="Run the pipeline but do not overwrite "
                        "game_analyses.decryption_v5_data.")
    args = p.parse_args()

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    game = await db.games.find_one({"game_id": args.game_id}, {"_id": 0})
    if not game:
        print(f"[ERR] no game with game_id={args.game_id}")
        client.close()
        return 1
    analysis = await db.game_analyses.find_one({"game_id": args.game_id}, {"_id": 0})
    if not analysis:
        print(f"[ERR] no game_analyses doc for game_id={args.game_id}")
        client.close()
        return 1

    sf = analysis.get("stockfish_analysis") or {}
    move_evaluations = sf.get("move_evaluations") or []
    pgn = game.get("pgn") or ""
    user_color = (game.get("user_color") or "white").lower()
    user_id = game.get("user_id") or "unknown"

    if not pgn or not move_evaluations:
        print(f"[ERR] pgn or move_evaluations empty for {args.game_id}")
        client.close()
        return 1

    print(f"Game     : {args.game_id}")
    print(f"User     : {user_id}  ({user_color})")
    print(f"Opening  : {game.get('opening', 'unknown')}")
    print(f"Result   : {game.get('result', '?')}")
    print(f"Moves    : {len(move_evaluations)} evaluations")
    print()

    # Run the live pipeline. Feature flag is on by default; the new
    # caption fields will land on every move record alongside the
    # legacy narrative/plan.
    from services.game_decryption_v5_service import generate_game_decryption_v5

    decryption = await generate_game_decryption_v5(
        pgn=pgn,
        user_color=user_color,
        move_evaluations=move_evaluations,
        user_id=user_id,
        db=db,
    )

    # Project the columns we care about for the review.
    rows: List[Dict[str, Any]] = []
    for mv in decryption:
        rows.append({
            "move_number": mv.get("move_number"),
            "move_san": mv.get("move_san"),
            "is_user_move": mv.get("is_user_move"),
            "severity": mv.get("severity"),
            "cp_loss": mv.get("cp_loss"),
            "narrative": mv.get("narrative"),
            "caption": mv.get("caption"),
            "rule_name": mv.get("rule_name"),
            "primary_reason": mv.get("caption_facts_primary_reason"),
        })

    out = _format_table(rows)
    print(out)

    # Inventory
    rule_counts: Dict[str, int] = {}
    silent = 0
    for r in rows:
        rn = r.get("rule_name") or "—"
        rule_counts[rn] = rule_counts.get(rn, 0) + 1
        if not r.get("caption"):
            silent += 1
    print()
    print("Rule histogram:")
    for rn, n in sorted(rule_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {rn:<32} {n}")
    print(f"Silent moves (caption empty): {silent}/{len(rows)}")

    if args.write_to:
        out_path = Path(args.write_to)
        if not out_path.is_absolute():
            out_path = (BACKEND_DIR.parent / args.write_to).resolve()
        out_path.write_text(
            f"Game {args.game_id}\nUser {user_id} ({user_color})\n\n"
            + out
            + "\n\nRule histogram:\n"
            + "\n".join(f"  {rn:<32} {n}" for rn, n in sorted(rule_counts.items(), key=lambda kv: -kv[1]))
            + f"\nSilent moves: {silent}/{len(rows)}\n",
            encoding="utf-8",
        )
        print(f"\n[wrote] {out_path}")

    if not args.no_db_write:
        from datetime import datetime, timezone
        await db.game_analyses.update_one(
            {"game_id": args.game_id},
            {"$set": {
                "decryption_v5_data": decryption,
                "decryption_v5_regen_at": datetime.now(timezone.utc),
            }},
        )
        print(f"\n[db] wrote {len(decryption)} records to decryption_v5_data")

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
