"""Group a game's easy-English gold captions by the distilled template-TYPE the move
would use, so we can see how many gold examples we have per situation to distill from.
NON-DESTRUCTIVE. Env: PMONGO. Usage: python scripts/group_gold_by_type.py <game_id>
"""
import os, sys, json
sys.path.insert(0, "/app/backend")
import pymongo, chess
from services.distilled_caption_service import _subtype, _material, P

def move_type(m):
    """Replicate the distilled engine's type routing (without cp/verify gates)."""
    fb = m.get("fen_before"); san = m.get("move_san")
    is_user = bool(m.get("is_user_move"))
    pre = "good_" if is_user else "opp_"
    try:
        b = chess.Board(fb); mv = b.parse_san(san)
    except Exception:
        return "unparsable"
    cp = abs(int(m.get("cp_loss") or 0))
    if cp >= 100:
        return "mistake"  # mistakes grouped separately (different template family)
    if san in ("O-O", "O-O-O"):
        return pre + "castle"
    if b.is_capture(mv):
        after = b.copy(); after.push(mv); target = b.piece_at(mv.to_square)
        recap = bool(target and len(after.attackers(not b.turn, mv.to_square)) > 0)
        behind = (_material(b, b.turn) - _material(b, not b.turn)) <= -100
        free = bool(target) and not recap and not behind
        return pre + ("capture_free" if free else "trade")
    st = _subtype(b, mv)
    pc = b.piece_at(mv.from_square)
    if st:
        return pre + st
    if pc and pc.piece_type == chess.PAWN:
        return pre + "pawn"
    if pc and pc.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(mv.from_square) in (0, 7):
        return pre + "develop"
    return pre + "other"


def main():
    gid = sys.argv[1]
    db = pymongo.MongoClient(os.environ["PMONGO"])["chess_coach"]
    dd = (db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "decryption_v5_data": 1}) or {}).get("decryption_v5_data") or []
    gold = {f"{r['move_number']}:{r['move_san']}": r.get("caption") for r in db.gold_tester_captions.find({"game_id": gid})}
    groups = {}
    for m in dd:
        key = f"{m.get('move_number')}:{m.get('move_san')}"
        g = (gold.get(key) or "").strip()
        if not g:
            continue
        t = move_type(m)
        groups.setdefault(t, []).append((key, g))
    print(f"{'type':22} n   examples")
    for t in sorted(groups, key=lambda x: -len(groups[x])):
        ex = groups[t]
        print(f"{t:22} {len(ex):<3} e.g. {ex[0][0]} \"{ex[0][1][:55]}\"")
    # dump for the distill step
    with open(f"/app/backend/scripts/_goldgroups_{gid[:8]}.json", "w", encoding="utf-8") as f:
        json.dump({t: [e[1] for e in ex] for t, ex in groups.items()}, f, ensure_ascii=False, indent=1)
    print(f"\nwrote _goldgroups_{gid[:8]}.json")


if __name__ == "__main__":
    main()
