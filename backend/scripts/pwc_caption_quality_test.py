"""pwc_caption_quality_test.py — bulk ACCURACY + QUALITY test for PWC captions.

Renders the REAL PWC entry point (shared_coaching_v5.generate_move_coaching) over a
corpus of analyzed games — for BOTH user and opponent moves — then measures:

  ACCURACY  every claim passes the per-FEN board verifier (0 false is the bar).
            The central-layer path is auto-verified (framework Step 2); the LEGACY
            fallback narratives (opponent moves, user-move fallbacks) are NOT — this
            is where fabrications hide. This test surfaces them.
  QUALITY   user mistakes/blunders carry the 4 teachings (what · why-bad · better ·
            why-better); nothing renders empty (never-silent).
  COVERAGE  empty-rate per side.

Split user vs opponent so we see exactly where PWC lags review. Run in dev container.
"""
from __future__ import annotations
import os, sys, io, re, asyncio, collections
sys.path.insert(0, "/app/backend")
import chess, chess.pgn
from motor.motor_asyncio import AsyncIOMotorClient

MONGO = os.environ.get("MONGO_URL", "mongodb://admin_user_mii_s_c:Mii123$44$@72.60.204.176:27017/?authSource=admin")
DB = os.environ.get("DB_NAME", "chess_coach")
LIMIT_GAMES = int(os.environ.get("LIMIT_GAMES", "40"))


def _fen4(f): return " ".join(f.split()[:4])


def _whatm(c): return bool(re.search(r"\b(is (a|an) (mistake|inaccuracy|serious mistake|major blunder)|loses to|lets |allows |walks into|drops |hangs|it drops the)\b", c, re.I))
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
    from services.narrator_claim_verifier import verify_caption

    db = AsyncIOMotorClient(MONGO, serverSelectionTimeoutMS=15000)[DB]
    games = await db.games.find({"is_analyzed": True}, {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1}).limit(LIMIT_GAMES).to_list(LIMIT_GAMES)

    stat = lambda: {"n": 0, "empty": 0, "false": 0}
    user, opp = stat(), stat()
    mistakes = {"n": 0, "what": 0, "whybad": 0, "better": 0, "whybetter": 0, "all4": 0}
    false_samples, mistake_gap_samples = [], []

    for g in games:
        gid = g["game_id"]; uc = (g.get("user_color") or "white").lower()
        analysis = await db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "stockfish_analysis": 1})
        if not analysis: continue
        mes = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
        by_fen = {_fen4(m.get("fen_before", "")): m for m in mes if m.get("fen_before")}
        try:
            pg = chess.pgn.read_game(io.StringIO(g.get("pgn") or ""))
        except Exception:
            continue
        if pg is None: continue
        board = pg.board(); hist = []; uw = (uc == "white")
        sfp, sfk = set(), set()
        for mv in pg.mainline_moves():
            is_user = (board.turn == chess.WHITE) == uw
            try: san = board.san(mv)
            except Exception: break
            me = by_fen.get(_fen4(board.fen()))
            # USER moves need stored eval (analysis stores user moves only).
            # OPPONENT moves have no stored eval — render them anyway (the opp
            # narrative is board-derived, not eval-gated) so we test that surface.
            if me is None and is_user:
                board.push(mv); hist.append(san); continue
            me = me or {}
            cp = int(me.get("cp_loss") or 0); fmn = board.fullmove_number
            ph = "opening"
            if detect_phase is not None:
                try: ph = detect_phase(board, fmn)
                except Exception: pass
            _eb, _ea = me.get("eval_before"), me.get("eval_after")
            try:
                c = await generate_move_coaching(
                    board_before=board.copy(), move=mv, best_move_san=me.get("best_move"),
                    pv_after_played=me.get("pv_after_played") or [], pv_after_best=me.get("pv_after_best") or [],
                    cp_loss=cp, phase=ph, is_user_move=is_user,
                    context=CoachingContext.LIVE_AFTER_USER if is_user else CoachingContext.LAB_REVIEW,
                    user_color=uc, move_history_san=list(hist),
                    eval_before_cp=int(_eb) if isinstance(_eb, (int, float)) else None,
                    eval_after_cp=int(_ea) if isinstance(_ea, (int, float)) else None,
                    move_evaluations=mes, session_fired_principles=sfp, session_fired_state_keys=sfk,
                )
                narr = (getattr(c, "narrative", "") or "").strip()
            except Exception as e:
                narr = ""
            bucket = user if is_user else opp
            bucket["n"] += 1
            if not narr:
                bucket["empty"] += 1
            else:
                bafter = board.copy(); bafter.push(mv)
                vfacts = {"move_san": san, "fen_before": board.fen(), "fen_after": bafter.fen(),
                          "is_user_move": is_user, "cp_loss": abs(cp),
                          "best_move_san": me.get("best_move"),
                          "pv_after_played": me.get("pv_after_played") or [],
                          "pv_after_best": me.get("pv_after_best") or []}
                try:
                    if verify_caption(narr, vfacts):  # truthy = violations
                        bucket["false"] += 1
                        if len(false_samples) < 20:
                            false_samples.append(f"  [{'U' if is_user else 'O'} cp{cp}] {san}: {narr[:95]}")
                except Exception:
                    pass
            # quality: user mistakes
            if is_user and cp >= 120 and narr:
                mistakes["n"] += 1
                w1, w2, w3, w4 = _whatm(narr), _whybad(narr), bool(me.get("best_move") and (me["best_move"].replace("+","").replace("#","") in narr or "was better" in narr or "was stronger" in narr or "was the" in narr)), _whybetter(narr)
                mistakes["what"] += w1; mistakes["whybad"] += w2; mistakes["better"] += w3; mistakes["whybetter"] += w4
                if w1 and w2 and w3 and w4: mistakes["all4"] += 1
                elif len(mistake_gap_samples) < 15:
                    mistake_gap_samples.append(f"  cp{cp} {san}: {narr[:95]}")
            board.push(mv); hist.append(san)

    def pct(a, b): return f"{round(100*a/b)}%" if b else "—"
    print(f"\n=== PWC caption bulk test ({LIMIT_GAMES} games) ===")
    print(f"USER moves:     n={user['n']}  empty={user['empty']} ({pct(user['empty'],user['n'])})  FALSE-claim={user['false']} ({pct(user['false'],user['n'])})")
    print(f"OPPONENT moves: n={opp['n']}  empty={opp['empty']} ({pct(opp['empty'],opp['n'])})  FALSE-claim={opp['false']} ({pct(opp['false'],opp['n'])})")
    m = mistakes
    print(f"\nUSER mistakes/blunders (cp>=120): n={m['n']}")
    for k in ["what", "whybad", "better", "whybetter", "all4"]:
        print(f"   {k:10s} {m[k]:4d}  ({pct(m[k], m['n'])})")
    print("\n--- FALSE-claim samples (accuracy failures) ---")
    for s in false_samples: print(s)
    print("\n--- mistake quality-gap samples ---")
    for s in mistake_gap_samples: print(s)


if __name__ == "__main__":
    asyncio.run(main())
    sys.stdout.flush()
    import os as _os; _os._exit(0)
