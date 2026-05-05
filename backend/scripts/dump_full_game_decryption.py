"""
Dump the complete coaching output for ONE game — Truth + Player
Decryption + Plan Decryption + per-move commentary.

For voice review: paste the output and read it cold as if you're a
1200-rated player who just lost the game. If you skip past sections,
that section is failing; we redesign.

Usage (inside the backend container):
    python scripts/dump_full_game_decryption.py <game_id>
    python scripts/dump_full_game_decryption.py 2085fc68-e1e8-4878-9762-a4d2d86758f4
    python scripts/dump_full_game_decryption.py <game_id> --moves all   # show every move
    python scripts/dump_full_game_decryption.py <game_id> --moves mistakes  # only mistakes/blunders (default)
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(BACKEND_DIR / ".env")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")

SEP_THICK = "=" * 78
SEP_THIN = "-" * 78


def _truncate(text, max_len=600):
    if not text:
        return ""
    text = str(text).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


async def dump_game(game_id: str, moves_filter: str) -> None:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    game = await db.games.find_one({"game_id": game_id}, {"_id": 0})
    analysis = await db.game_analyses.find_one({"game_id": game_id}, {"_id": 0})

    if not game:
        print(f"No game record found for {game_id}")
        client.close()
        return
    if not analysis:
        print(f"No analysis found for {game_id}")
        client.close()
        return

    # ── Header ────────────────────────────────────────────────────
    print(SEP_THICK)
    print(f"GAME {game_id}")
    print(SEP_THICK)
    print(f"opening    : {game.get('opening', 'unknown')}")
    print(f"result     : {game.get('result', '?')}    user_color: {game.get('user_color', '?')}")
    print(f"opponent   : {game.get('opponent', '?')}")
    print(f"platform   : {game.get('platform', '?')}    imported: {game.get('imported_at', '?')}")
    print()

    # ── Truth ─────────────────────────────────────────────────────
    print(SEP_THIN)
    print("TRUTH (top of post-game screen — 3 lines, mutterable)")
    print(SEP_THIN)
    truth = analysis.get("truth_line")
    if truth:
        print(f"  identity : {truth.get('identity', '')}")
        print(f"  anchor   : {truth.get('anchor', '')}")
        print(f"  trigger  : {truth.get('trigger', '')}")
        print(f"  scenario : {truth.get('scenario', '?')}")
    else:
        print("  (no truth_line — user won OR voice generation skipped)")
    print()

    # ── Player Decryption ────────────────────────────────────────
    print(SEP_THIN)
    print("PLAYER DECRYPTION ('this is how you played' — Story / Pattern / Carry-forward)")
    print(SEP_THIN)
    pd = analysis.get("player_decryption")
    if pd:
        print(f"  story         : {pd.get('story', '')}")
        print(f"  pattern       : {pd.get('pattern', '')}")
        print(f"  carry_forward : {pd.get('carry_forward', '')}")
        print(f"  scenario      : {pd.get('scenario', '?')}")
    else:
        print("  (no player_decryption — likely cached game without new fields)")
    print()

    # ── Plan Decryption ─────────────────────────────────────────
    print(SEP_THIN)
    print("PLAN DECRYPTION ('what was happening on the board' — gated under Show me why)")
    print(SEP_THIN)
    pb = analysis.get("decryption_block")
    if pb:
        print(f"  text          : {_truncate(pb.get('text', ''), 800)}")
        print(f"  source        : {pb.get('source', '?')}    attempts: {pb.get('attempts', '?')}")
        print(f"  critical_move : {pb.get('critical_move_san', '?')} on move {pb.get('critical_move_number', '?')}")
        failed = pb.get("failed_attempts") or []
        if failed:
            print()
            print(f"  REJECTED LLM ATTEMPTS ({len(failed)}):")
            for f in failed:
                print(f"    [attempt {f.get('attempt')}] reason: {f.get('reason')}")
                print(f"      text: {_truncate(f.get('text', ''), 500)}")

        # Multi-moment list — the post-game page renders one block per
        # moment so the user sees ALL turning points, not just one.
        moments = pb.get("moments") or []
        if moments:
            print()
            print(f"  MOMENTS ({len(moments)} turning points):")
            for i, m in enumerate(moments, 1):
                print(f"    [{i}] move {m.get('move_number')}  {m.get('move_san')}  cp_loss={m.get('cp_loss')}  pivot={m.get('is_pivot')}")
                print(f"        text: {_truncate(m.get('text', ''), 500)}")
                print(f"        source: {m.get('source')}    attempts: {m.get('attempts')}")
                fa = m.get("failed_attempts") or []
                if fa:
                    for f in fa:
                        print(f"        rejected[{f.get('attempt')}]: {f.get('reason')}")
                        print(f"          text: {_truncate(f.get('text',''), 300)}")
                print()
    else:
        print("  (no decryption_block — likely cached game without new fields)")
    print()

    # ── CCT narrative + habits report (existing surfaces, for context) ──
    cct = analysis.get("cct_narrative")
    if cct:
        print(SEP_THIN)
        print("CCT NARRATIVE (top-line discipline note when present)")
        print(SEP_THIN)
        print(f"  {cct}")
        print()

    # ── Per-move commentary (V5 narratives) ──────────────────────
    moves = analysis.get("decryption_v5_data") or []
    if not moves:
        print("(no V5 per-move data)")
        client.close()
        return

    print(SEP_THIN)
    print(f"PER-MOVE COMMENTARY ({len(moves)} moves total — filter='{moves_filter}')")
    print(SEP_THIN)

    if moves_filter == "mistakes":
        shown = [m for m in moves if m.get("is_user_move") and (m.get("cp_loss") or 0) >= 50]
        print(f"Showing {len(shown)} user moves with cp_loss >= 50:")
    else:
        shown = moves
        print(f"Showing all {len(shown)} moves:")
    print()

    for m in shown:
        is_user = m.get("is_user_move")
        san = m.get("move_san", "?")
        ply = m.get("move_number", "?")
        cp = m.get("cp_loss", 0)
        sev = m.get("severity", "?")
        prefix = "USER" if is_user else "OPP "
        narr = m.get("narrative") or ""
        print(f"  [{prefix}] move {ply} {san:8s}  cp_loss={cp:4d}  severity={sev}")
        if narr:
            print(f"         narrative: {_truncate(narr, 300)}")
        plan = m.get("plan")
        if isinstance(plan, dict):
            for k in ("goal", "current_problem", "consequence", "better_approach", "transferable_learning"):
                v = plan.get(k)
                if v:
                    print(f"         {k}: {_truncate(v, 240)}")
        ypn = m.get("your_plan_now")
        if ypn:
            print(f"         your_plan_now: {_truncate(ypn, 240)}")
        print()

    print(SEP_THICK)
    print("END")
    client.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("game_id", help="game_id to dump")
    p.add_argument(
        "--moves", default="mistakes",
        choices=["mistakes", "all"],
        help="'mistakes' (default) or 'all'",
    )
    args = p.parse_args()
    asyncio.run(dump_game(args.game_id, args.moves))


if __name__ == "__main__":
    main()
