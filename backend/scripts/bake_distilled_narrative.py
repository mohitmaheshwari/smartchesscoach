"""Bake distilled every-move captions into ONE game's served narrative (ChessGuru
column for the tester demo). Per-game only — does NOT flip the global
DISTILLED_CAPTIONS_ENABLED flag, does NOT touch any other game/user.

Uses correctly-scaled evals (decryption eval_before/eval_after are already cp).
Fills only BLANK narratives; preserves existing live captions.

Env: PMONGO (prod)
Usage: python scripts/bake_distilled_narrative.py <game_id> [--apply]
"""
import os, sys
sys.path.insert(0, "/app/backend")
import pymongo
from services.caption_pipeline import MoveInputs
from services.distilled_caption_service import try_distilled_caption


def main():
    gid = sys.argv[1]
    apply = "--apply" in sys.argv
    db = pymongo.MongoClient(os.environ["PMONGO"])["chess_coach"]
    ga = db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "decryption_v5_data": 1})
    dd = (ga or {}).get("decryption_v5_data") or []

    hist, filled, kept, abstain, bytype = [], 0, 0, 0, {}
    for m in dd:
        san = m.get("move_san")
        existing = (m.get("narrative") or "").strip()
        # Regenerate our OWN prior distilled output (so template fixes take
        # effect on re-run); preserve any non-distilled (live/original) caption.
        is_ours = str(m.get("rule_name") or "").startswith("distilled:")
        if existing and not is_ours:
            kept += 1
            hist.append(san)
            continue
        try:
            inp = MoveInputs(
                fen_before=m.get("fen_before"), played_san=san,
                mover_is_user=bool(m.get("is_user_move")), mover_is_white=bool(m.get("is_white")),
                user_color="white", full_move_number=int(m.get("move_number") or 0),
                move_history_san=list(hist), best_move_san=m.get("best_move_san"),
                eval_before_cp=m.get("eval_before"), eval_after_cp=m.get("eval_after"),
                cp_loss=abs(int(m.get("cp_loss") or 0)),
                pv_after_played=m.get("pv_after_played") or [], pv_after_best=m.get("pv_after_best") or [])
            r = try_distilled_caption(inp)
        except Exception:
            r = None
        if r and r[0]:
            t = r[1].split(":")[-1]
            bytype[t] = bytype.get(t, 0) + 1
            filled += 1
            if apply:
                m["narrative"] = r[0]
                m["caption"] = r[0]
                m["rule_name"] = r[1]
        else:
            abstain += 1
        hist.append(san)

    print(f"total={len(dd)} kept_existing={kept} distilled_filled={filled} abstained={abstain} apply={apply}")
    print("by type:", dict(sorted(bytype.items(), key=lambda x: -x[1])))
    if apply:
        db.game_analyses.update_one({"game_id": gid}, {"$set": {"decryption_v5_data": dd}})
        print("SAVED decryption_v5_data")


if __name__ == "__main__":
    main()
