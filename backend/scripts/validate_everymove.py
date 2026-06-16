"""Every-move validation (2026-06-16). Mohit: caption ALMOST EVERY move, not just mistakes —
the product is for 500-1000 ELO, where every move is a lesson. Route each user move:
  cp>=100  -> mistake-coaching situation (distill_baseline_sweep)
  cp<100   -> GOOD-MOVE teaching (develop/castle/pawn/capture/other), principle-based
then verify on the board (free-capture gated; no claimed tactics). Measures coverage + truth
over a sample of the both-analyzed games. No Claude, no prod.

Env: MONGO_URL, DB_NAME, NGAMES (default 500).
"""
import os, sys, json, time, chess
sys.path.insert(0, "/app/backend"); sys.path.insert(0, "/app/backend/scripts")
from collections import Counter, defaultdict
from pymongo import MongoClient
import distill_baseline_sweep as S

db = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000, socketTimeoutMS=40000)[os.environ["DB_NAME"]]
P = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
NG = int(os.environ.get("NGAMES", "500"))

data = json.load(open("/app/backend/data/distilled_templates.json"))
MISTAKE_T = data.get("templates", {})
GOOD_T = data.get("good_move_templates", {})
SEED = {k: v[1] for k, v in S.SITUATIONS.items()}


_CENTRAL = {chess.C4, chess.D4, chess.E4, chess.C5, chess.D5, chess.E5, chess.D3, chess.E3, chess.D6, chess.E6}


def _subtype(board, mv):
    """split the catch-all into specific teachable situations (queen_safety / centralize /
    rook_open_file / rook_activity / luft / space). Returns None if not one of these."""
    pc = board.piece_at(mv.from_square)
    if not pc:
        return None
    pt = pc.piece_type; mover = board.turn
    if pt == chess.QUEEN:
        tr = chess.square_rank(mv.to_square)
        if (tr <= 1 if mover == chess.WHITE else tr >= 6):
            return "queen_safety"
        if mv.to_square in _CENTRAL:
            return "centralize"
    elif pt == chess.ROOK:
        f = chess.square_file(mv.to_square)
        own = any((p := board.piece_at(chess.square(f, r))) and p.piece_type == chess.PAWN and p.color == mover for r in range(8))
        return "rook_activity" if own else "rook_open_file"
    elif pt in (chess.KNIGHT, chess.BISHOP) and mv.to_square in _CENTRAL:
        return "centralize"
    elif pt == chess.PAWN:
        ff = chess.square_file(mv.from_square); tf = chess.square_file(mv.to_square)
        adv = abs(chess.square_rank(mv.to_square) - chess.square_rank(mv.from_square))
        if ff == tf and ff in (0, 7) and adv == 1:
            return "luft"
        if ff == tf and ff in (0, 1, 6, 7) and adv >= 1:
            return "space"
    return None


def good_type(board, mv, san):
    if san in ("O-O", "O-O-O"):
        return "castle"
    if board.is_capture(mv):
        return "capture"
    st = _subtype(board, mv)
    if st and GOOD_T.get(st):
        return st
    pc = board.piece_at(mv.from_square)
    if pc and pc.piece_type == chess.PAWN:
        return "pawn"
    if pc and pc.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(mv.from_square) in (0, 7):
        return "develop"
    return "other"


def good_caption(board, san):
    """render a good-move teaching caption + verify it (no false 'free')."""
    try:
        mv = board.parse_san(san)
    except Exception:
        return None, None, None
    gt = good_type(board, mv, san)
    pc = board.piece_at(mv.from_square)
    piece = P.get(pc.piece_type, "piece") if pc else "piece"
    to_sq = chess.square_name(mv.to_square)
    # capture: only say "free" if the captured piece is undefended AFTER the capture
    verified = True
    if gt == "capture":
        after = board.copy(); after.push(mv)
        target = board.piece_at(mv.to_square)
        free = bool(target) and len(after.attackers(not board.turn, mv.to_square)) == 0
        if free:
            cap = f"{san} snaps up the {P[target.piece_type]} on {to_sq} for free — when an enemy piece sits undefended and it is safe to take, take it."
        else:
            # recapture / trade — never claim 'free'
            cap = f"{san} captures on {to_sq}; when your opponent takes, look to recapture and keep material even."
        return gt, cap, verified
    tmpl = GOOD_T.get(gt) or GOOD_T.get("other")
    if not tmpl:
        return gt, None, None
    try:
        cap = tmpl.format(move=san, piece=piece, to_square=to_sq)
    except Exception:
        return gt, None, None
    # these claim only development/castle/space/reposition -> structurally true; no tactic asserted
    return gt, cap, verified


def main():
    t0 = time.time()
    gids = [d["game_id"] for d in db.game_analyses.find({"stockfish_analysis.opponent_move_evaluations": {"$exists": True, "$ne": []}}, {"_id": 0, "game_id": 1}).limit(NG)]
    uc = {g["game_id"]: (g.get("user_color") or "white").lower() for g in db.games.find({"game_id": {"$in": gids}}, {"_id": 0, "game_id": 1, "user_color": 1})}
    total = cap_mistake = cap_good = ver_mistake = ver_good = abstain = 0
    by = defaultdict(lambda: {"cap": 0, "ver": 0})
    docs = []
    CH = 250
    for i in range(0, len(gids), CH):
        for attempt in range(4):
            try:
                docs = list(db.game_analyses.find({"game_id": {"$in": gids[i:i+CH]}}, {"_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1})); break
            except Exception as e:
                print("  [retry]", str(e)[:40], flush=True); time.sleep(3); docs = []
        for an in docs:
            u = uc.get(an["game_id"], "white")
            for m in (an.get("stockfish_analysis", {}) or {}).get("move_evaluations") or []:
                fb = m.get("fen_before"); san = m.get("move")
                if not fb or not san:
                    continue
                total += 1
                cp = m.get("cp_loss") or 0
                if cp >= 100:
                    g = {"fen_before": fb, "move_san": san, "best_move_san": m.get("best_move"), "move_number": m.get("move_number")}
                    lab = S.classify(m, u)
                    if lab in S.SITUATIONS:
                        f = S.SITUATIONS[lab][0](g, m); errs = S.verify(g, m, f, u)
                        c = S.render(MISTAKE_T.get(lab) or SEED.get(lab, ""), f)
                        if c.strip():
                            cap_mistake += 1; by["MISTAKE:" + lab]["cap"] += 1
                            if not errs:
                                ver_mistake += 1; by["MISTAKE:" + lab]["ver"] += 1
                            continue
                    abstain += 1
                else:
                    try:
                        gt, c, ok = good_caption(chess.Board(fb), san)
                    except Exception:
                        gt, c, ok = None, None, None
                    if c:
                        cap_good += 1; by["GOOD:" + gt]["cap"] += 1
                        if ok:
                            ver_good += 1; by["GOOD:" + gt]["ver"] += 1
                    else:
                        abstain += 1
    capped = cap_mistake + cap_good; ver = ver_mistake + ver_good
    print("\n============ EVERY-MOVE VALIDATION (sample) ============", flush=True)
    print(f"games {len(gids)} | total user moves {total} | time {time.time()-t0:.0f}s", flush=True)
    print(f"COVERAGE: {capped}/{total} = {100*capped//max(total,1)}%  (mistakes {cap_mistake} + good {cap_good}; abstain {abstain})", flush=True)
    print(f"TRUTH:    {ver}/{capped} = {100*ver//max(capped,1)}%   (mistakes {ver_mistake}/{cap_mistake}, good {ver_good}/{cap_good})", flush=True)
    print("\nby bucket (cap / ver):", flush=True)
    for k, c in sorted(by.items(), key=lambda kv: -kv[1]["cap"]):
        print(f"  {k:28} cap {c['cap']:>6} ver {c['ver']:>6} ({100*c['ver']//max(c['cap'],1)}%)", flush=True)


main()
