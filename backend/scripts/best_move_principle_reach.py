"""Reach test for missed-opportunity detection: on the transferable-principle-miss
moves, classify what PRINCIPLE the engine's BEST move embodies (center / develop /
castle / rook-to-open-file / capture). If most misses have a classifiable best-move
principle, a 'X was passive — [best] was stronger, it [principle]' caption covers them.

Env: PMONGO. Usage: python scripts/best_move_principle_reach.py
"""
import os, sys, json, re, asyncio, collections
sys.path.insert(0, "/app/backend")
import chess
from motor.motor_asyncio import AsyncIOMotorClient

_CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
_PRINCIPLE = {
    "early_queen": r"queen out early|early queen|gets? chased|gain(s|ing)? time on (the|your|his) queen",
    "develop": r"\bdevelop|bring(s|ing)? .*piece|new piece into",
    "center": r"\b(center|centre|central)\b|fight for the cent",
    "king_safety": r"\bcastl|king('s)? saf|king to safety|tuck",
    "open_file": r"open file|open .-file|rook behind|rooks love",
}


def gold_is_principle(text):
    t = (text or "").lower()
    return any(re.search(rx, t) for rx in _PRINCIPLE.values())


def best_move_principle(fen_before, best_san):
    if not fen_before or not best_san:
        return None
    try:
        b = chess.Board(fen_before)
        mv = b.parse_san(best_san)
    except Exception:
        return None
    if b.is_castling(mv):
        return "castle"
    pc = b.piece_at(mv.from_square)
    if mv.to_square in _CENTER and pc and pc.piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP):
        return "center"
    if pc and pc.piece_type in (chess.KNIGHT, chess.BISHOP):
        r = chess.square_rank(mv.from_square)
        if (pc.color == chess.WHITE and r == 0) or (pc.color == chess.BLACK and r == 7):
            return "develop"
    if b.is_capture(mv):
        return "capture"
    if pc and pc.piece_type == chess.ROOK:
        f = chess.square_file(mv.to_square)
        own_pawn = any(b.piece_at(chess.square(f, rr)) == chess.Piece(chess.PAWN, pc.color) for rr in range(8))
        if not own_pawn:
            return "rook_open_file"
    return None


async def main():
    from services import game_decryption_v5_service as v5_mod
    from services.game_decryption_v5_service import generate_game_decryption_v5
    async def _noop(*_a, **_kw): return []
    v5_mod._get_stockfish_candidates = _noop

    recs = [json.loads(l) for l in open("/app/backend/scripts/_gold_records_wg.jsonl", encoding="utf-8")]
    gold = {(r["game"], r.get("move_number"), r["move_san"]): r for r in recs}
    game_ids = list({r["game"] for r in recs})
    db = AsyncIOMotorClient(os.environ["PMONGO"])["chess_coach"]

    miss = 0
    classifiable = collections.Counter()
    examples = collections.defaultdict(list)
    done = 0
    for gid in game_ids:
        game = await db.games.find_one({"game_id": gid}, {"_id": 0})
        analysis = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
        if not game or not analysis:
            continue
        mevals = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        if not (game.get("pgn") and mevals):
            continue
        fresh = await generate_game_decryption_v5(
            pgn=game.get("pgn"), user_color=(game.get("user_color") or "white").lower(),
            move_evaluations=mevals, user_id=game.get("user_id") or "unknown", db=db)
        for m in fresh:
            g = gold.get((gid, m.get("move_number"), m.get("move_san")))
            if not g or not gold_is_principle(g["caption"]):
                continue
            # gold teaches a principle; only the user's own moves are "missed opportunities"
            if not m.get("is_user_move"):
                continue
            miss += 1
            pr = best_move_principle(m.get("fen_before"), m.get("best_move_san"))
            classifiable[pr or "none"] += 1
            if pr and len(examples[pr]) < 3:
                examples[pr].append((m.get("move_san"), m.get("best_move_san"),
                                     int(m.get("cp_loss") or 0), g["caption"][:75]))
        done += 1
        if done % 25 == 0:
            print(f"  {done}/{len(game_ids)} games", flush=True)

    print(f"\n=== user-move principle-misses: {miss} ===")
    tot = sum(v for k, v in classifiable.items() if k != "none")
    print(f"best-move principle classifiable: {tot} ({tot*100//max(1,miss)}%)")
    for k, v in classifiable.most_common():
        print(f"  {v:5}  {k}")
    print("\nexamples (played -> best [cp]):")
    for pr, exs in examples.items():
        print(f"### {pr}")
        for played, best, cp, gc in exs:
            print(f"   {played} -> {best} [{cp}cp]  GOLD: {gc}")
    import os as _os
    print("DONE", flush=True); _os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
