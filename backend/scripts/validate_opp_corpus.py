"""Opponent-move validation (2026-06-16). We ignored opponent moves in the rollout — this fixes
that. Coach opponent moves FROM THE USER'S SEAT ("Black's move lets you ..."), deterministically:
classify each analyzed opp move -> render a user-framed template -> verify the user's punishment
on the board. Measures coverage + truth over the ~20k opponent moves we have.

Situations (user POV after the opponent's move):
  opp_allowed_mate  -> "Black's {mv} allows mate — play {your_reply} ..."
  opp_hung_material -> "Black's {mv} drops the {piece} on {sq} — take it with {your_reply}."
  opp_inaccuracy    -> abstain (no clean punishment).

Env: MONGO_URL, DB_NAME. No Claude, no prod.
"""
import os, sys, time, chess
from collections import Counter, defaultdict
from pymongo import MongoClient

db = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000, socketTimeoutMS=40000)[os.environ["DB_NAME"]]
P = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
VAL = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300, chess.ROOK: 500, chess.QUEEN: 900}


def upov(x, uc):
    return None if x is None else (x if uc == "white" else -x)


def line_won(board, pv, mover):
    """net material for `mover` over pv (list of SAN), + biggest enemy piece won."""
    b = board.copy(); net = 0; won = None; bv = 0
    for san in pv[:6]:
        try:
            mv = b.parse_san(san)
        except Exception:
            break
        cap = b.piece_at(mv.to_square)
        if cap:
            v = VAL[cap.piece_type]
            if b.turn == mover and cap.color != mover:
                net += v
                if v > bv:
                    bv = v; won = (cap.piece_type, mv.to_square)
            elif cap.color == mover:
                net -= v
        b.push(mv)
    return net, won


def analyze_opp(m, uc):
    """Return (situation, caption, verified_bool) for one opponent move, user-framed."""
    fb = m.get("fen_before")
    oppmv = m.get("move")
    pvp = m.get("pv_after_played") or []
    if not fb or not oppmv or not pvp:
        return "opp_inaccuracy", None, None
    try:
        b = chess.Board(fb)
        b.push_san(oppmv)  # now the USER is to move
    except Exception:
        return "opp_inaccuracy", None, None
    user = b.turn
    your_reply = pvp[0]
    # 1. opponent allowed a forced mate for the user?
    upe = upov(m.get("eval_after"), uc)
    mate_for_user = False
    bb = b.copy()
    for san in pvp[:7]:
        try:
            bb.push_san(san)
        except Exception:
            break
        if bb.is_checkmate() and bb.turn != user:  # user delivered mate
            mate_for_user = True; break
    if mate_for_user or (upe is not None and upe >= 9000):
        cap = f"Black's {oppmv} allows a forced mate — play {your_reply} and finish the attack. When your opponent leaves the king exposed, scan for the mating sequence before anything else."
        return "opp_allowed_mate", cap, mate_for_user
    # 2. opponent hung material the user can win?
    net, won = line_won(b, pvp, user)
    if net >= 200 and won:
        cap = f"Black's {oppmv} drops the {P[won[0]]} on {chess.square_name(won[1])} — take it with {your_reply}. When your opponent blunders material, grab it before continuing your plan."
        # verify: user's reply actually wins that piece in the line
        ok = (net >= 200)
        return "opp_hung_material", cap, ok
    return "opp_inaccuracy", None, None


def main():
    t0 = time.time()
    gids = [d["game_id"] for d in db.game_analyses.find({"stockfish_analysis.opponent_move_evaluations": {"$exists": True, "$ne": []}}, {"_id": 0, "game_id": 1})]
    print(f"games with opponent analysis: {len(gids)} / 7837", flush=True)
    ucache = {g["game_id"]: (g.get("user_color") or "white").lower() for g in db.games.find({}, {"_id": 0, "game_id": 1, "user_color": 1})}
    total = captioned = verified = abstain = processed = 0
    by_sit = defaultdict(lambda: {"cap": 0, "ver": 0})
    CH = 400
    for i in range(0, len(gids), CH):
        chunk = gids[i:i + CH]
        for attempt in range(4):
            try:
                docs = list(db.game_analyses.find({"game_id": {"$in": chunk}}, {"_id": 0, "game_id": 1, "stockfish_analysis.opponent_move_evaluations": 1}))
                break
            except Exception as e:
                print(f"  [retry {i} #{attempt}] {str(e)[:50]}", flush=True); time.sleep(3); docs = []
        for an in docs:
            uc = ucache.get(an["game_id"], "white")
            for m in (an.get("stockfish_analysis", {}) or {}).get("opponent_move_evaluations") or []:
                if (m.get("cp_loss") or 0) < 100:  # only notable opp errors (parallels user cp>=100)
                    continue
                total += 1
                try:
                    sit, cap, ok = analyze_opp(m, uc)
                except Exception:
                    abstain += 1; continue
                if cap is None:
                    abstain += 1
                else:
                    captioned += 1; by_sit[sit]["cap"] += 1
                    if ok:
                        verified += 1; by_sit[sit]["ver"] += 1
            processed += 1
        if processed and processed % 800 == 0:
            print(f"  {processed}/{len(gids)} games | {total} opp-errors | cap {captioned} ver {verified} ({time.time()-t0:.0f}s)", flush=True)
    print("\n============ OPPONENT-MOVE VALIDATION ============", flush=True)
    print(f"games w/ opp analysis: {len(gids)} | opponent errors (cp>=100): {total}", flush=True)
    print(f"COVERAGE: {captioned}/{total} = {100*captioned//max(total,1)}%  (abstain {abstain})", flush=True)
    print(f"TRUTH:    {verified}/{captioned} = {100*verified//max(captioned,1)}%", flush=True)
    for s, c in sorted(by_sit.items(), key=lambda kv: -kv[1]["cap"]):
        print(f"  {s:20} cap {c['cap']:>6}  ver {c['ver']:>6}  ({100*c['ver']//max(c['cap'],1)}% true)", flush=True)


main()
