"""verify_mistake_4parts.py — does every MISTAKE/BLUNDER caption carry the 4 teachings?

  1. WHAT  — names the move as a mistake/blunder (severity stated)
  2. WHY-BAD — why the played move is bad (concrete consequence: hangs/loses/allows...)
  3. BETTER — names a better move
  4. WHY-BETTER — why the better move is better (its purpose)

Renders USER moves fresh via build_move_teaching_decision (the V5 central layer),
filters to mistakes/blunders, and emits a JSONL with the caption + the engine facts
needed to judge each clause for ACCURACY (not just presence). Run in dev container.
"""
from __future__ import annotations
import os, sys, io, json, asyncio
sys.path.insert(0, "/app/backend")
import chess, chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@72.60.204.176:27017/?authSource=admin")
DB_NAME = os.environ.get("DB_NAME", "chess_coach")
OUT = "/app/backend/scripts/_mistake_4parts.jsonl"
LIMIT_GAMES = int(os.environ.get("LIMIT_GAMES", "80"))
# A "mistake" by the user's band (rating 1200 -> 1000-1399): mistake>=200, but we
# cast wider to catch everything the system might frame as a slip: cp_loss>=120.
MISTAKE_CP = int(os.environ.get("MISTAKE_CP", "120"))


def _fen4(f): return " ".join(f.split()[:4])


async def main():
    from services.caption_pipeline import build_move_teaching_decision, MoveInputs, CrossMoveState
    try:
        from services.game_decryption_v5_service import detect_phase
    except Exception:
        detect_phase = None
    db = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=15000)[DB_NAME]

    games = await db.games.find({"is_analyzed": True},
                                {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1}
                                ).limit(LIMIT_GAMES).to_list(LIMIT_GAMES)
    rows = []
    for g in games:
        gid = g.get("game_id"); pgn = g.get("pgn") or ""
        uc = (g.get("user_color") or "white").lower()
        analysis = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
        if not analysis: continue
        mes = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        by_fen = {_fen4(m.get("fen_before", "")): m for m in mes if m.get("fen_before")}
        try:
            pgn_game = chess.pgn.read_game(io.StringIO(pgn))
        except Exception:
            continue
        if pgn_game is None: continue
        board = pgn_game.board(); history = []; state = CrossMoveState()
        user_is_white = (uc == "white")
        for mv in pgn_game.mainline_moves():
            is_user = (board.turn == chess.WHITE) == user_is_white
            try: san = board.san(mv)
            except Exception: break
            me = by_fen.get(_fen4(board.fen()))
            if me is None or not is_user:
                board.push(mv); history.append(san); continue
            cp = int(me.get("cp_loss") or 0)
            if cp < MISTAKE_CP:
                board.push(mv); history.append(san); continue
            fmn = board.fullmove_number
            ph = "opening"
            if detect_phase is not None:
                try: ph = detect_phase(board, fmn)
                except Exception: pass
            inp = MoveInputs(
                fen_before=board.fen(), played_san=san, mover_is_user=True,
                mover_is_white=(board.turn == chess.WHITE), user_color=uc,
                full_move_number=fmn, move_history_san=list(history),
                best_move_san=me.get("best_move"), cp_loss=cp,
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
                sev = dec.teaching_meta.severity if getattr(dec, "teaching_meta", None) else ""
            except Exception as e:
                cap, rule, sev = "", f"ERR:{repr(e)[:60]}", ""
            rows.append({
                "game": gid, "mv": fmn, "san": san, "cp": cp,
                "fen": board.fen(),
                "best": me.get("best_move"),
                "pv_played": (me.get("pv_after_played") or [])[:4],
                "pv_best": (me.get("pv_after_best") or [])[:4],
                "phase": ph, "severity": sev, "rule": rule, "caption": cap,
            })
            board.push(mv); history.append(san)

    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"WROTE {OUT} | mistake/blunder user moves (cp>={MISTAKE_CP}): {len(rows)}")

    # ── INDEPENDENT per-FEN verification of the NEW why-better claims ──
    # Re-derive from the board with the best move applied — do NOT trust the
    # generator's own computation (defense in depth, distill-skill law).
    import re as _re
    from services.caption_facts import static_exchange_eval as _see, PIECE_VALUE_CP as _PV
    _NM = {chess.PAWN:"pawn",chess.KNIGHT:"knight",chess.BISHOP:"bishop",
           chess.ROOK:"rook",chess.QUEEN:"queen",chess.KING:"king"}
    ok = lie = 0; lies = []
    for r in rows:
        c = r["caption"]
        m = _re.search(r"was better — it (.+?)\.", c)
        if not m or not r.get("best"):
            continue
        why = m.group(1).strip()
        try:
            b = chess.Board(r["fen"]); bm = b.parse_san(r["best"])
        except Exception:
            continue
        mover = b.turn; enemy = not mover
        after = b.copy(); after.push(bm)
        verdict = None  # True=verified, False=false claim, None=not a checked type
        am = _re.match(r"attacks the (\w+) on ([a-h][1-8])$", why)
        if am:
            sq = chess.parse_square(am.group(2)); p = after.piece_at(sq)
            verdict = bool(p and p.color == enemy and _NM.get(p.piece_type) == am.group(1)
                           and sq in after.attacks(bm.to_square))
        elif why.startswith("moves your ") and why.endswith("out of danger"):
            pn = why.split("moves your ")[1].split(" out")[0]
            moved = b.piece_at(bm.from_square)
            verdict = bool(moved and _NM.get(moved.piece_type) == pn
                           and (_see(b, bm.from_square, enemy) or 0) >= 100
                           and (_see(after, bm.to_square, enemy) or 0) <= 0)
        elif why.startswith("defends your "):
            dm = _re.match(r"defends your (\w+) on ([a-h][1-8])", why)
            if dm:
                sq = chess.parse_square(dm.group(2)); p = after.piece_at(sq)
                verdict = bool(p and p.color == mover and _NM.get(p.piece_type) == dm.group(1)
                               and (_see(b, sq, enemy) or 0) >= 100
                               and (_see(after, sq, enemy) or 0) <= 0
                               and bm.to_square in after.attackers(mover, sq))
        elif am is None and why.startswith(("wins ", "trades off", "gets your king",
                                            "takes the", "develops", "posts a knight",
                                            "takes the open")):
            verdict = None  # capture/principle whys — covered by existing tests
        if verdict is True:
            ok += 1
        elif verdict is False:
            lie += 1
            lies.append(f"  LIE: {r['game'][:12]} m{r['mv']} {r['san']}->{r['best']}: {c}")
    print(f"\nindependent why-better claim check (new types): verified={ok} FALSE={lie}")
    for s in lies[:25]:
        print(s)
    # quick structural tally (presence heuristics; accuracy judged by reading)
    import re
    def has_better(r):
        b = (r["best"] or "").replace("+","").replace("#","")
        c = r["caption"]
        return bool(b and b in c) or bool(re.search(r"\b(was (the )?(better|stronger)|Play |was the move)\b", c))
    def has_whatmistake(r):
        return bool(re.search(r"\b(mistake|blunder|inaccuracy|too greedy|drops|loses|hangs|gives up|walks into|lets|allows|misses|missed)\b", r["caption"], re.I))
    def has_whybad(r):
        return bool(re.search(r"\b(hangs?|loses?|drops?|allows?|lets|leaves|undefended|forks?|pins?|wins (the|your)|trapp|opens)\b", r["caption"], re.I))
    def has_whybetter(r):
        c = r["caption"]
        # a clause after the better move: "X was stronger — it ..." / "X ... , <verb-ing>"
        return bool(re.search(r"(better|stronger)\b[^.]*\b(it |to |—| develop| defend| win| trade| keep| activ| control| attack| save| protect)", c, re.I))
    n=len(rows)
    if n:
        from collections import Counter
        cnt=Counter()
        for r in rows:
            if has_whatmistake(r): cnt["1_what"]+=1
            if has_whybad(r): cnt["2_whybad"]+=1
            if has_better(r): cnt["3_better"]+=1
            if has_whybetter(r): cnt["4_whybetter"]+=1
            if has_whatmistake(r) and has_whybad(r) and has_better(r) and has_whybetter(r): cnt["all4"]+=1
            if not r["caption"].strip(): cnt["EMPTY"]+=1
        print("structural presence (heuristic, n=%d):"%n)
        for k in ["1_what","2_whybad","3_better","4_whybetter","all4","EMPTY"]:
            print(f"   {k:12s} {cnt[k]:4d}  ({100*cnt[k]//n}%)")


if __name__ == "__main__":
    asyncio.run(main())
    sys.stdout.flush()
    import os as _os; _os._exit(0)
