"""pwc_why_gap_examples.py — dump REAL positions where the PWC mistake caption
is missing WHY-BAD and/or WHY-BETTER, with full caption + FEN + engine lines, so
each miss can be diagnosed (every miss is a bug report).
"""
from __future__ import annotations
import os, sys, io, re, asyncio
sys.path.insert(0, "/app/backend")
import chess, chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

MONGO = os.environ.get("MONGO_URL")
DB = os.environ.get("DB_NAME", "chess_coach")
LIMIT_GAMES = int(os.environ.get("LIMIT_GAMES", "40"))
WANT = int(os.environ.get("WANT", "14"))

def _fen4(f): return " ".join(f.split()[:4])

# same predicates the quality test uses
def _whybad(c): return bool(re.search(r"(loses to \S+|lets \S+ (win|capture)|allows \S+ (fork|forking|pin|skew)|walks into \S+|drops the \w+|\bhangs\b|win your \w+ on|forking your|losing material|loses material|it drops the)", c, re.I))
def _whybetter(c):
    m = re.search(r"was (?:the )?(?:better|stronger)\b\s*[—-]\s*(.*?)(?:\.|$)", c)
    if not m: return False
    t = m.group(1).lower()
    return bool(re.search(r"\b(it )?(attacks?|captures?|wins?|forks?|develops?|defends?|trades?|recaptur|sacrifices?|opens|keeps?|puts your|hits|breaks|protects?|saves?|covers?|untangl|connects?|pins?|skewers?|moves your|gets your king|takes the)\b", t))

async def main():
    from services.shared_coaching_v5 import generate_move_coaching, CoachingContext
    try:
        from services.game_decryption_v5_service import detect_phase
    except Exception:
        detect_phase = None
    db = AsyncIOMotorClient(MONGO, serverSelectionTimeoutMS=15000)[DB]
    games = await db.games.find({"is_analyzed": True}, {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1}).limit(LIMIT_GAMES).to_list(LIMIT_GAMES)
    shown = 0
    for g in games:
        if shown >= WANT: break
        gid = g["game_id"]; uc = (g.get("user_color") or "white").lower()
        analysis = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
        if not analysis: continue
        mes = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        by_fen = {_fen4(m.get("fen_before", "")): m for m in mes if m.get("fen_before")}
        try: pg = chess.pgn.read_game(io.StringIO(g.get("pgn") or ""))
        except Exception: continue
        if pg is None: continue
        board = pg.board(); hist = []; uw = (uc == "white")
        for mv in pg.mainline_moves():
            if shown >= WANT: break
            is_user = (board.turn == chess.WHITE) == uw
            try: san = board.san(mv)
            except Exception: break
            me = by_fen.get(_fen4(board.fen()))
            if me is None:
                board.push(mv); hist.append(san); continue
            cp = int(me.get("cp_loss") or 0); fmn = board.fullmove_number
            if not (is_user and cp >= 120):
                board.push(mv); hist.append(san); continue
            ph = "opening"
            if detect_phase is not None:
                try: ph = detect_phase(board, fmn)
                except Exception: pass
            _eb, _ea = me.get("eval_before"), me.get("eval_after")
            try:
                c = await generate_move_coaching(
                    board_before=board.copy(), move=mv, best_move_san=me.get("best_move"),
                    pv_after_played=me.get("pv_after_played") or [], pv_after_best=me.get("pv_after_best") or [],
                    cp_loss=cp, phase=ph, is_user_move=True,
                    context=CoachingContext.LIVE_AFTER_USER, user_color=uc, move_history_san=list(hist),
                    eval_before_cp=int(_eb) if isinstance(_eb,(int,float)) else None,
                    eval_after_cp=int(_ea) if isinstance(_ea,(int,float)) else None,
                    move_evaluations=mes)
                narr = (getattr(c,"narrative","") or "").strip()
            except Exception:
                narr = ""
            wb, wbet = _whybad(narr), _whybetter(narr)
            if narr and not (wb and wbet):
                shown += 1
                miss = []
                if not wb: miss.append("WHY-BAD")
                if not wbet: miss.append("WHY-BETTER")
                print(f"\n{'='*78}\n#{shown}  missing: {', '.join(miss)}   (cp_loss {cp})")
                print(f"  move played : {san}   |   engine best : {me.get('best_move')}")
                print(f"  FEN before  : {board.fen()}")
                print(f"  CAPTION     : {narr}")
                pvp = me.get('pv_after_played') or []
                pvb = me.get('pv_after_best') or []
                print(f"  line after PLAYED (what punishes it): {' '.join(pvp[:6]) if pvp else '(none stored)'}")
                print(f"  line after BEST   (why best is good): {' '.join(pvb[:6]) if pvb else '(none stored)'}")
            board.push(mv); hist.append(san)
    print(f"\n\nshown {shown} missing-why examples.")

if __name__ == "__main__":
    asyncio.run(main())
    sys.stdout.flush()
    import os as _os; _os._exit(0)
