"""
audit_lost_defender_lead.py — verify v83 lost-defender lead clause
across the pinned authoring queue games.

For each user move in the 10 pinned games:
  1. Re-run extract_facts (v83) on (fen_before, played_san, best_move_san, ...)
  2. Check whether lost_defender_lead_clause is populated.
  3. Inspect the stored caption to see whether a paired why_clause
     already fires (i.e., whether the new user_with_best_em_dash_with_lead
     variant would replace the existing caption with the BOTH-halves form).
  4. Print a corpus-wide report:
       - Fires count per game
       - Sample: game_id, move#, played, best, lead text, existing caption,
         predicted new caption (paired vs unchanged)

Run inside the backend container:
  docker exec chess-coach-backend python -m scripts.audit_lost_defender_lead

No DB writes; pure read + recompute.
"""
import asyncio
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, "/app")

from motor.motor_asyncio import AsyncIOMotorClient

from services.caption_facts import extract_facts
from services.caption_renderer import render_caption_dict
from services.shape_detectors import simulate_pawn_kicks_piece


PINNED_GAMES = [
    "game_85bd0169aa4f",
    "game_b5d23694a803",
    "game_f2c022e03856",
    "game_ef9f422a062d",
    "game_74fdbd74c468",
    "game_4177951c757f",
    "game_bc41022831e0",
    "game_4c0f48f6cc0a",
    "game_8efcc1db5aa4",
    "game_692ab776c5b1",
]


def _recompute_facts(m: Dict[str, Any]) -> Dict[str, Any]:
    """Re-run extract_facts at v83 using fields stored on the move."""
    return extract_facts(
        fen_before=m["fen_before"],
        played_san=m["move_san"],
        best_move_san=m.get("best_move_san") or "",
        eval_before_cp=m.get("eval_before") or 0,
        eval_after_cp=m.get("eval_after") or 0,
        cp_loss=m.get("cp_loss") or 0,
        pv_after_played=m.get("pv_after_played") or [],
        pv_after_best=m.get("pv_after_best") or [],
        move_history_san=[],
        full_move_number=m.get("move_number") or 1,
        mover_is_user=bool(m.get("is_user_move")),
    )


def _has_paired_why_clause(m: Dict[str, Any]) -> bool:
    """Heuristic: does the stored caption suggest a paired why_clause
    fires? Look for the em-dash continuation pattern or the
    'was better — ' phrase, OR for known why_clause-only variants.
    """
    cap = (m.get("caption") or "").strip()
    if not cap:
        return False
    # The user_with_best_em_dash variant is "{played} {phrase}. {best} was
    # better — {why_clause}" — the em dash AFTER 'was better' is the
    # tell. The non-em-dash with_why variant is "...was better. {why_clause}"
    # with an additional sentence after. Detect both.
    if " was better — " in cap:
        return True
    if " was better. " in cap and cap.count(".") >= 2:
        return True
    return False


async def main() -> None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client["chess_coach"]

    total_user_moves = 0
    total_lead_fires = 0
    total_lead_paired = 0  # would render with both halves
    total_lead_unpaired = 0  # lead fires but no why_clause — would stay silent in our paired-only design

    samples_paired: List[Dict[str, Any]] = []
    samples_unpaired: List[Dict[str, Any]] = []

    per_game = {}

    for gid in PINNED_GAMES:
        g = await db.game_analyses.find_one({"game_id": gid})
        if not g or not isinstance(g.get("decryption_v5_data"), list):
            print(f"[skip] {gid}: no decryption_v5_data list")
            continue
        moves = g["decryption_v5_data"]
        game_fires = 0
        for m in moves:
            if not m.get("is_user_move"):
                continue
            if not m.get("fen_before") or not m.get("move_san"):
                continue
            total_user_moves += 1
            try:
                facts = _recompute_facts(m)
            except Exception as e:
                continue
            lead = facts.get("lost_defender_lead_clause") or ""
            if not lead:
                continue
            total_lead_fires += 1
            game_fires += 1
            paired = _has_paired_why_clause(m)
            # Render a v84 caption preview. Inject the pawn_kicks_piece
            # fact when applicable so the why_clause priority survives —
            # this is the most common partner clause and the only V5
            # wiring step we re-run inline here. Other detectors that
            # contribute facts would require full V5 replay; for audit
            # purposes the preview is enough to spot polish wins.
            try:
                pk_evs = simulate_pawn_kicks_piece(m["fen_before"], m.get("best_move_san") or "")
                if pk_evs:
                    e = pk_evs[0]
                    facts["pawn_kicks_piece_square"] = e.get("kicked_square")
                    facts["pawn_kicks_piece_type"] = e.get("kicked_piece_type")
                    facts["why_clause_em_dash"] = True
            except Exception:
                pass
            try:
                rendered = render_caption_dict(facts)
                preview_caption = rendered.get("caption") or ""
            except Exception:
                preview_caption = "<render error>"
            sample = {
                "game_id": gid,
                "move_number": m.get("move_number"),
                "played_san": m.get("move_san"),
                "best_move_san": m.get("best_move_san"),
                "severity": m.get("severity"),
                "cp_loss": m.get("cp_loss"),
                "lead": lead,
                "existing_caption": (m.get("caption") or "").strip(),
                "v84_preview": preview_caption.strip(),
                "fen_before": m.get("fen_before"),
            }
            if paired:
                total_lead_paired += 1
                samples_paired.append(sample)
            else:
                total_lead_unpaired += 1
                samples_unpaired.append(sample)
        per_game[gid] = game_fires

    print("=" * 72)
    print(f"AUDIT: lost-defender lead clause @ v83 across {len(PINNED_GAMES)} pinned games")
    print("=" * 72)
    print(f"Total user moves scanned        : {total_user_moves}")
    print(f"Lead clause fires               : {total_lead_fires}")
    print(f"  paired with better-move why_clause (will render with lead): {total_lead_paired}")
    print(f"  unpaired (lead silenced, paired-only design)              : {total_lead_unpaired}")
    print()
    print("Per-game lead fire counts:")
    for gid, n in per_game.items():
        print(f"  {gid}: {n}")
    print()

    print("-" * 72)
    print(f"PAIRED samples — v83 will render with BOTH halves ({len(samples_paired)} total)")
    print("-" * 72)
    for s in samples_paired:
        print(f"\n[{s['game_id']} m{s['move_number']}] {s['played_san']} ({s['severity']}, cp={s['cp_loss']})")
        print(f"  best         : {s['best_move_san']}")
        print(f"  lead (new)   : {s['lead']}")
        print(f"  existing cap : {s['existing_caption']}")
        print(f"  v84 preview  : {s['v84_preview']}")

    print()
    print("-" * 72)
    print(f"UNPAIRED samples — lead fires but no better-move why_clause ({len(samples_unpaired)} total)")
    print("  (these stay UNCHANGED under v83's paired-only design)")
    print("-" * 72)
    for s in samples_unpaired:
        print(f"\n[{s['game_id']} m{s['move_number']}] {s['played_san']} ({s['severity']}, cp={s['cp_loss']})")
        print(f"  best         : {s['best_move_san']}")
        print(f"  lead (unused): {s['lead']}")
        print(f"  existing cap : {s['existing_caption']}")
        print(f"  v84 preview  : {s['v84_preview']}")


if __name__ == "__main__":
    asyncio.run(main())
