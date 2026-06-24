"""select_parth_batch.py — pick gold-covered games that best exercise the CHANGED
caption surfaces (2026-06-23 endgame-silence fix + earlier deltas), so Parth's
review tests what changed rather than re-confirming green areas.

Scans every gold-covered game, fresh-renders each USER+OPP move via the central
layer (build_move_teaching_decision), tags the rule_name into a stratum, and
reports per-game stratum hit-counts + a greedy stratified pick.

Run inside chess-coach-backend-dev (direct prod DB). Gold list from the host
_gold_records_wg.jsonl (copied into the container alongside this script).
"""
from __future__ import annotations
import os, sys, io, json, collections, asyncio
sys.path.insert(0, "/app/backend")
import chess, chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@72.60.204.176:27017/?authSource=admin")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")
GOLD = "/app/backend/scripts/_gold_records_wg.jsonl"

# Changed-surface strata → matcher on rule_name (substring) / caption.
STRATA = {
    "endgame_kingactive": lambda r, c, ph: "END_KING_ACTIVE" in r,
    "endgame_floor": lambda r, c, ph: ph == "endgame" and r.startswith("R_TIER"),
    "develop_variant": lambda r, c, ph: r in ("R15_good_move",) and ("develop" in c or "eyeing" in c),
    "develop_tier": lambda r, c, ph: "R_TIER2_develop" in r,
    "pawn_break": lambda r, c, ph: "pawn break" in c or "striking at the pawn" in c,
    "near_best_tier": lambda r, c, ph: r.startswith("R_TIER") and ph != "endgame",
    "rook_trap": lambda r, c, ph: "rook" in c.lower() and ("trap" in c.lower() or "entomb" in c.lower()),
    "opp_missed_tactic": lambda r, c, ph: "they missed" in c.lower(),
}


def _fen4(f): return " ".join(f.split()[:4])


async def main():
    from services.caption_pipeline import build_move_teaching_decision, MoveInputs, CrossMoveState
    try:
        from services.game_decryption_v5_service import detect_phase
    except Exception:
        detect_phase = None

    gold_games = sorted({json.loads(l)["game"] for l in open(GOLD, encoding="utf-8")})
    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=15000)[DB_NAME]

    per_game = {}   # gid -> Counter(stratum -> n)
    for gid in gold_games:
        game = await db.games.find_one({"game_id": gid}, {"_id": 0, "pgn": 1, "user_color": 1})
        analysis = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
        if not game or not analysis:
            continue
        mes = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        by_fen = {_fen4(m.get("fen_before", "")): m for m in mes if m.get("fen_before")}
        try:
            pgn_game = chess.pgn.read_game(io.StringIO(game.get("pgn") or ""))
        except Exception:
            continue
        if pgn_game is None:
            continue
        board = pgn_game.board(); history = []
        user_is_white = ((game.get("user_color") or "white").lower() == "white")
        state = CrossMoveState(); hits = collections.Counter()
        for mv in pgn_game.mainline_moves():
            is_user = (board.turn == chess.WHITE) == user_is_white
            try:
                san = board.san(mv)
            except Exception:
                break
            me = by_fen.get(_fen4(board.fen()))
            if me is None:
                board.push(mv); history.append(san); continue
            fmn = board.fullmove_number
            ph = "opening"
            if detect_phase is not None:
                try: ph = detect_phase(board, fmn)
                except Exception: pass
            inp = MoveInputs(
                fen_before=board.fen(), played_san=san, mover_is_user=is_user,
                mover_is_white=(board.turn == chess.WHITE),
                user_color=(game.get("user_color") or "white").lower(),
                full_move_number=fmn, move_history_san=list(history),
                best_move_san=me.get("best_move"), cp_loss=int(me.get("cp_loss") or 0),
                pv_after_played=me.get("pv_after_played") or [],
                pv_after_best=me.get("pv_after_best") or [],
                eval_before_cp=me.get("eval_before"), eval_after_cp=me.get("eval_after"),
                user_rating=1200,
            )
            try:
                dec = build_move_teaching_decision(inp, state)
                txt = getattr(dec, "text", None)
                cap = (getattr(txt, "caption", "") if txt else "") or ""
                rule = (getattr(txt, "rule_name", "") if txt else "") or ""
            except Exception:
                cap, rule = "", ""
            for sname, fn in STRATA.items():
                try:
                    if fn(rule, cap, ph): hits[sname] += 1
                except Exception:
                    pass
            board.push(mv); history.append(san)
        if hits:
            per_game[gid] = hits

    # Report per-stratum top games.
    print("=== per-stratum top gold-covered games ===")
    for s in STRATA:
        ranked = sorted(((g, h[s]) for g, h in per_game.items() if h.get(s)), key=lambda x: -x[1])[:6]
        print(f"\n{s}:")
        for g, n in ranked:
            print(f"   {n:3d}  {g}")

    # Greedy stratified pick: cover each stratum, prefer multi-stratum games.
    target = {s: 0 for s in STRATA}
    picked = []
    pool = dict(per_game)
    while len(picked) < 10:
        best_g, best_score = None, -1
        for g, h in pool.items():
            # score = strata still under target that this game contributes to
            score = sum(1 for s in STRATA if target[s] < 2 and h.get(s))
            score += 0.01 * sum(h.values())  # tiebreak: total changed-surface volume
            if score > best_score:
                best_g, best_score = g, score
        if best_g is None or best_score <= 0:
            break
        picked.append(best_g)
        for s in STRATA:
            if pool[best_g].get(s): target[s] += 1
        del pool[best_g]
        if all(target[s] >= 2 for s in STRATA):
            # keep going a couple more for volume but stop at 8
            if len(picked) >= 8:
                break
    print("\n=== greedy stratified pick ===")
    print(" ".join(picked))
    print("\ncoverage:", dict(target))


if __name__ == "__main__":
    asyncio.run(main())
    sys.stdout.flush(); sys.stderr.flush()
    import os as _os; _os._exit(0)
