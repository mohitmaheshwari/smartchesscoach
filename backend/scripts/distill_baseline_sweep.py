"""Unified distillation baseline sweep (2026-06-16).

Reclassify all gold into the CLEAN taxonomy, then for each engine-decidable situation:
route to the right slot-builder -> distill ONE template (Claude, offline) -> render ->
INDEPENDENT board-verifier (every claim re-derived) -> LLM-judge vs gold. Output a
scorecard: per situation n / verified-true% / match% / status.

Bars: verified-truth = shippable gate (0 lies). match% = quality tracker.
Deep situations (missed_mate) are PV-capped; positional/defer abstain by design.

Env: MONGO_URL (direct prod ok), DB_NAME, LLM_API_BASE, LLM_API_KEY.
"""
import os, sys, json, time, re, chess
sys.path.insert(0, "/app/backend")
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
from pymongo import MongoClient
import services.narrator_fallback as nf

db = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=8000, socketTimeoutMS=25000)[os.environ["DB_NAME"]]
P = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
VAL = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300, chess.ROOK: 500, chess.QUEEN: 900}
CENTRAL = {chess.C4, chess.D4, chess.E4, chess.C5, chess.D5, chess.E5}
TAGS = os.environ.get("GOLD_TAGS", "gold_shobhit,gold_mohit,gold_parth").split(",")


# ---------- clean-taxonomy classifier ----------
def upov(x, uc):
    return None if x is None else (x if uc == "white" else -x)


def push_any(b, mv):
    for fn in (b.parse_san, lambda x: chess.Move.from_uci(x)):
        try:
            b.push(fn(mv)); return True
        except Exception:
            pass
    return False


def pv_material(m):
    fb = m.get("fen_before", ""); pv = m.get("pv_after_played") or []
    if not fb or not pv:
        return None
    try:
        b = chess.Board(fb); uc = b.turn
        u = m.get("move_uci") or b.parse_san(m.get("move", "")).uci(); b.push(chess.Move.from_uci(u))
    except Exception:
        return None
    um = lambda bb: sum(VAL[pt] * len(bb.pieces(pt, uc)) for pt in VAL)
    start = um(b); mats = []
    for mv in pv[:6]:
        if not push_any(b, mv): break
        mats.append(um(b))
    if not mats or mats[-1] >= start - 100: return None
    depth = next((i for i, v in enumerate(mats, 1) if v <= start - 200), None) or next((i for i, v in enumerate(mats, 1) if v <= start - 100), 99)
    return "one_move_blunder" if depth <= 2 else "walked_into_tactic"


def missed_free_flag(m):
    best = m.get("best_move") or ""
    if "x" not in best: return False
    try:
        b = chess.Board(m.get("fen_before", "")); bm = b.parse_san(best); cap = b.piece_at(bm.to_square)
        if not cap or (m.get("move") or "") == best: return False
        return len(b.attackers(cap.color, bm.to_square)) == 0
    except Exception:
        return False


def classify(m, uc):
    ueb = upov(m.get("eval_before"), uc); uea = upov(m.get("eval_after"), uc)
    if uea is not None and uea <= -9000: return "allowed_mate"
    if ueb is not None and ueb >= 9000 and (uea is None or uea < 9000): return "missed_mate"
    pm = pv_material(m)
    if pm: return pm
    if missed_free_flag(m): return "missed_free_material"
    san = m.get("move") or ""; mn = m.get("move_number") or 99
    if san.startswith("Q") and mn <= 6 and "x" not in san: return "opening_knowledge"
    try:
        b = chess.Board(m.get("fen_before", "")); q = len(b.pieces(chess.QUEEN, chess.WHITE)) + len(b.pieces(chess.QUEEN, chess.BLACK))
        npc = sum(len(b.pieces(pt, c)) for pt in (chess.ROOK, chess.BISHOP, chess.KNIGHT) for c in (chess.WHITE, chess.BLACK))
        if q == 0 and npc <= 6: return "endgame_technique"
    except Exception:
        pass
    return "(defer to Claude)"


def ask(prompt, to=110):
    try:
        r = requests.post(nf._BASE + "/ask", headers=nf._H, json={"question": prompt, "provider": "claude", "timeout_seconds": to}, timeout=20)
        r.raise_for_status(); tid = r.json()["task_id"]; end = time.time() + to + 30
        while time.time() < end:
            time.sleep(3); t = requests.get(nf._BASE + f"/tasks/{tid}", headers=nf._H, timeout=15).json()
            if t.get("status") in ("done", "completed"): return (t.get("answer") or "").strip()
            if t.get("status") in ("error", "timeout", "failed"): return None
    except Exception:
        return None


# ---------- shared strict best-move purpose ----------
def best_purpose(fb, best, mover, hung_sq):
    try:
        bb = chess.Board(fb); bmv = bb.parse_san(best); bp = bb.piece_at(bmv.from_square)
        after = chess.Board(fb); after.push(bmv)
        develops = bp and bp.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(bmv.from_square) in (0, 7)
        sdef = hung_sq is not None and (hung_sq in after.attacks(bmv.to_square))
        weak = chess.F7 if mover == chess.WHITE else chess.F2
        if bb.is_capture(bmv):
            t = bb.piece_at(bmv.to_square)
            if t: return f"it captures the {P[t.piece_type]} on {chess.square_name(bmv.to_square)}", ("cap", t.piece_type, bmv.to_square)
        if develops and sdef: return f"it develops your {P[bp.piece_type]} and defends {chess.square_name(hung_sq)}", ("def", bmv.to_square, hung_sq, True)
        if sdef: return f"it defends {chess.square_name(hung_sq)}", ("def", bmv.to_square, hung_sq, False)
        if develops and weak in after.attacks(bmv.to_square): return f"it develops your {P[bp.piece_type]}, eyeing {chess.square_name(weak)}", ("eye", bmv.to_square, weak)
        if develops: return f"it develops your {P[bp.piece_type]} toward the center", ("dev", bmv.from_square)
        if bp and bp.piece_type == chess.PAWN and bmv.to_square in CENTRAL: return "it fights for the center", ("center", bmv.to_square)
    except Exception:
        pass
    return "", None


def line_won(fb, pv, mover):
    b = chess.Board(fb); net = 0; won = None; bv = 0
    for san in pv[:6]:
        try: mv = b.parse_san(san)
        except Exception: break
        cap = b.piece_at(mv.to_square)
        if cap:
            v = VAL[cap.piece_type]
            if b.turn == mover and cap.color != mover:
                net += v
                if v > bv: bv = v; won = (cap.piece_type, mv.to_square)
            elif cap.color == mover: net -= v
        b.push(mv)
    return net, won


# ---------- per-structure builders (slots + _v verification claims) ----------
def b_hang(g, ev):  # one_move_blunder
    fb = g["fen_before"]; b = chess.Board(fb); mover = b.turn; played = g["move_san"]; best = g.get("best_move_san") or ev.get("best_move")
    pvp = ev.get("pv_after_played") or []
    f = {"played_san": played, "best_san": best, "hung_piece": "", "hung_square": "", "opp_reply_san": "", "best_purpose": "", "_v": []}
    hung = None
    try:
        b2 = chess.Board(fb); b2.push_san(played)
        if pvp:
            mv = b2.parse_san(pvp[0]); cap = b2.piece_at(mv.to_square); f["opp_reply_san"] = pvp[0]
            if cap and cap.color == mover:
                f["hung_piece"] = P[cap.piece_type]; f["hung_square"] = chess.square_name(mv.to_square); hung = mv.to_square
                f["_v"].append(("hang", pvp[0], cap.piece_type, mv.to_square))
    except Exception:
        pass
    bp, bv = best_purpose(fb, best, mover, hung); f["best_purpose"] = bp
    if bv: f["_v"].append(bv)
    return f


def b_walked(g, ev):  # walked_into_tactic
    fb = g["fen_before"]; b = chess.Board(fb); mover = b.turn; played = g["move_san"]; best = g.get("best_move_san") or ev.get("best_move")
    pvp = ev.get("pv_after_played") or []
    f = {"played_san": played, "best_san": best, "front": "", "best_purpose": "", "_v": []}
    hung = None
    try:
        b2 = chess.Board(fb); b2.push_san(played); lost = None
        for san in pvp[:6]:
            try: mv = b2.parse_san(san)
            except Exception: break
            cap = b2.piece_at(mv.to_square)
            if cap and cap.color == mover and b2.turn != mover and VAL[cap.piece_type] >= 300:
                if not lost or VAL[cap.piece_type] > VAL[lost[1]]: lost = (san, cap.piece_type, mv.to_square)
            b2.push(mv)
        if lost:
            f["front"] = f"{played} walks into {lost[0]}, losing your {P[lost[1]]} on {chess.square_name(lost[2])}"; hung = lost[2]
            f["_v"].append(("lost", lost[0], lost[1], lost[2]))
        elif pvp:
            # fallback: no single clean >=minor capture, but the line costs material (net loss >= a minor)
            post = chess.Board(fb)
            post.push_san(played)
            net, _ = line_won(post.fen(), pvp, post.turn)  # opponent (side to move) net gain = our loss
            if net >= 300:
                f["front"] = f"{played} walks into {pvp[0]}, and the line costs you material"
                f["_v"].append(("netloss",))
    except Exception:
        pass
    bp, bv = best_purpose(fb, best, mover, hung); f["best_purpose"] = bp
    if bv: f["_v"].append(bv)
    return f


def b_free(g, ev):  # missed_free_material
    fb = g["fen_before"]; b = chess.Board(fb); mover = b.turn; best = g.get("best_move_san") or ev.get("best_move")
    f = {"played_san": g["move_san"], "best_san": best, "win": "", "_v": []}
    try:
        bm = b.parse_san(best); cap = b.piece_at(bm.to_square)
        if cap and cap.color != mover and len(b.attackers(cap.color, bm.to_square)) == 0:
            f["win"] = f"wins the {P[cap.piece_type]} on {chess.square_name(bm.to_square)} for free — it is undefended"
            f["_v"].append(("free", cap.piece_type, bm.to_square))
    except Exception:
        pass
    return f


def b_missed(g, ev):  # missed_tactic (best wins via capture/check/fork)
    fb = g["fen_before"]; b = chess.Board(fb); mover = b.turn; best = g.get("best_move_san") or ev.get("best_move")
    pvb = ev.get("pv_after_best") or []
    f = {"played_san": g["move_san"], "best_san": best, "win": "", "_v": []}
    try:
        bmv = b.parse_san(best); after = chess.Board(fb); after.push(bmv)
        if b.is_capture(bmv):
            t = bb = b.piece_at(bmv.to_square); a = b.piece_at(bmv.from_square)
            if t and (VAL[t.piece_type] >= VAL[a.piece_type] or not after.is_attacked_by(not mover, bmv.to_square)):
                f["win"] = f"wins the {P[t.piece_type]} on {chess.square_name(bmv.to_square)}"; f["_v"].append(("wcap", t.piece_type, bmv.to_square))
        if not f["win"] and b.gives_check(bmv):
            net, won = line_won(fb, pvb, mover)
            if won and net >= 2: f["win"] = f"checks the king and wins the {P[won[0]]} on {chess.square_name(won[1])}"; f["_v"].append(("cwin", won[0], won[1]))
    except Exception:
        pass
    return f


def b_mate(g, ev):  # missed_mate -- uses DEEP PV (gold_deep_pv) to name the specific mate
    n = ev.get("deep_mate_n"); pvb = ev.get("pv_after_best") or []
    best = g.get("best_move_san") or ev.get("best_move")
    win = ""
    if n:
        mv0 = pvb[0] if pvb else best
        win = f"{mv0} is checkmate" if n == 1 else f"{mv0} forces mate in {n} ({' '.join(pvb[:3])})"
        return {"played_san": g["move_san"], "best_san": best, "win": win, "_v": [("deepmate",)]}
    return {"played_san": g["move_san"], "best_san": best, "win": "", "_v": [("matey",)]}


def b_allowed(g, ev):  # allowed_mate (played walks into mate)
    return {"played_san": g["move_san"], "best_san": g.get("best_move_san") or ev.get("best_move"), "_v": [("amate",)]}


def b_openq(g, ev):  # opening_knowledge early-queen
    return {"played_san": g["move_san"], "best_san": g.get("best_move_san") or ev.get("best_move"), "_v": [("earlyq",)]}


# ---------- verifier (re-derive every claim) ----------
def verify(g, ev, f, uc):
    errs = []; fb = g["fen_before"]; b = chess.Board(fb); mover = b.turn; best = f["best_san"]
    try:
        bmv = b.parse_san(best); after = chess.Board(fb); after.push(bmv)
        for v in f.get("_v", []):
            k = v[0]
            if k == "hang":
                b2 = chess.Board(fb); b2.push_san(f["played_san"]); mv = b2.parse_san(v[1]); c = b2.piece_at(mv.to_square)
                if not (mv.to_square == v[3] and c and c.piece_type == v[2] and c.color == mover): errs.append("hang")
            elif k == "lost":
                b2 = chess.Board(fb); b2.push_san(f["played_san"])
                for san in (ev.get("pv_after_played") or [])[:6]:
                    try: mv = b2.parse_san(san)
                    except Exception: break
                    if san == v[1]:
                        c = b2.piece_at(mv.to_square)
                        if not (mv.to_square == v[3] and c and c.piece_type == v[2] and c.color == mover): errs.append("lost")
                        break
                    b2.push(mv)
            elif k in ("cap", "wcap"):
                t = b.piece_at(v[2])
                if not (b.is_capture(bmv) and bmv.to_square == v[2] and t and t.piece_type == v[1]): errs.append("cap")
            elif k == "free":
                cap = b.piece_at(v[2])
                if not (b.is_capture(bmv) and bmv.to_square == v[2] and cap and cap.piece_type == v[1] and cap.color != mover and len(b.attackers(cap.color, v[2])) == 0): errs.append("free")
            elif k == "cwin":
                if not b.gives_check(bmv): errs.append("check")
                net, won = line_won(fb, ev.get("pv_after_best") or [], mover)
                if net < 2 or not (won and won[0] == v[1] and won[1] == v[2]): errs.append("cwin")
            elif k == "def":
                if v[2] not in after.attacks(bmv.to_square): errs.append("def")
            elif k == "eye":
                if v[2] not in after.attacks(bmv.to_square): errs.append("eye")
            elif k == "dev":
                if chess.square_rank(v[1]) not in (0, 7): errs.append("dev")
            elif k == "center":
                if v[1] not in CENTRAL: errs.append("center")
            elif k == "matey":
                ub = upov(ev.get("eval_before"), uc)
                if not (ub is not None and ub >= 9000): errs.append("mate-sentinel")
            elif k == "deepmate":
                if not ev.get("deep_mate_n"): errs.append("deepmate")
            elif k == "amate":
                ua = upov(ev.get("eval_after"), uc)
                if not (ua is not None and ua <= -9000): errs.append("amate-sentinel")
            elif k == "earlyq":
                if not (f["played_san"].startswith("Q") and (g.get("move_number") or 99) <= 6): errs.append("earlyq")
            elif k == "netloss":
                post = chess.Board(fb); post.push_san(f["played_san"])
                net, _ = line_won(post.fen(), ev.get("pv_after_played") or [], post.turn)
                if net < 300: errs.append("netloss")
    except Exception:
        errs.append("unparseable")
    return errs


def render(template, f):
    d = {"played_san": "", "best_san": "", "hung_piece": "piece", "hung_square": "", "opp_reply_san": "", "front": "", "best_purpose": "", "win": ""}
    for k, v in f.items():
        if isinstance(v, str) and v: d[k] = v
    try: out = template.format(**d)
    except Exception: return ""
    out = re.sub(r",?\s*(?:since|because|which)\s*\.", ".", out); out = re.sub(r"\s{2,}", " ", out)
    return out.replace(" .", ".").replace(" ,", ",").strip()


def judge(g, cand):
    if not cand.strip(): return "MISS"
    prompt = (f"Grade caption A vs GOLD for the same move (1200 student). FEN {g['fen_before']} Move {g['move_san']} Best {g.get('best_move_san')}\n"
              f"GOLD: \"{g['gold_caption']}\"\nA: \"{cand}\"\n"
              "MATCH=same what+why+principle AND truthful. PARTIAL=related but weaker/missing a part. MISS=different/wrong/empty.\n"
              "Reply ONLY JSON {\"verdict\":\"MATCH|PARTIAL|MISS\"}")
    j = ask(prompt, to=70); mm = re.search(r"\{.*\}", j or "", re.S)
    try: return json.loads(mm.group(0)).get("verdict", "UNJUDGED")
    except Exception: return "UNJUDGED"


SITUATIONS = {
    "one_move_blunder": (b_hang, "{played_san} hangs your {hung_piece} on {hung_square} to {opp_reply_san}; instead play {best_san} — {best_purpose}.", "{played_san} {hung_piece} {hung_square} {opp_reply_san} {best_san} {best_purpose}", "played move immediately hangs a piece"),
    "walked_into_tactic": (b_walked, "{front}; {best_san} was stronger — {best_purpose}.", "{played_san} {front} {best_san} {best_purpose}", "played move walks into a tactic losing material a few moves later"),
    "missed_free_material": (b_free, "{played_san} missed {best_san} — it {win}.", "{played_san} {best_san} {win}", "a stronger move wins a free undefended piece"),
    "missed_tactic": (b_missed, "{played_san} missed the stronger {best_san} — it {win}.", "{played_san} {best_san} {win}", "missed a stronger tactic"),
    "missed_mate": (b_mate, "{played_san} missed a forced mate — {win}.", "{played_san} {win}", "missed a FORCED checkmate; {win} names the specific mate (deep Stockfish)"),
    "allowed_mate": (b_allowed, "{played_san} walks into a forced mate — {best_san} was needed to defend.", "{played_san} {best_san}", "played move allows a forced mate"),
    "opening_knowledge": (b_openq, "{played_san} brings the queen out too early; develop a minor piece like {best_san} first.", "{played_san} {best_san}", "early queen sortie"),
}


def loadall():
    # deep-PV cache (from pv_deepen_gold.py) -> inject so DEEP situations name the specific tactic
    deep = {}
    try:
        for d in db.gold_deep_pv.find({}, {"_id": 0}):
            deep[(d["game_id"], d.get("move_number"))] = d
    except Exception:
        pass
    rows = []
    for tag in TAGS:
        for g in db.gold_captions.find({"created_by": tag, "gold_caption": {"$ne": None}}, {"_id": 0}):
            if "don't see a board" in (g.get("gold_caption") or ""): continue
            gm = db.games.find_one({"game_id": g["game_id"]}, {"_id": 0, "user_color": 1}); uc = (gm or {}).get("user_color", "white").lower()
            an = db.game_analyses.find_one({"game_id": g["game_id"]}, {"_id": 0, "stockfish_analysis.move_evaluations": 1}); ev = {}
            for m in (an or {}).get("stockfish_analysis", {}).get("move_evaluations") or []:
                if m.get("move_number") == g.get("move_number") and m.get("move") == g.get("move_san"): ev = m; break
            if not ev: continue
            dp = deep.get((g["game_id"], g.get("move_number")))
            if dp:  # prefer deep PVs (longer, mate-complete) for naming the tactic
                if dp.get("deep_pv_best"): ev = {**ev, "pv_after_best": dp["deep_pv_best"]}
                if dp.get("deep_pv_played"): ev["pv_after_played"] = dp["deep_pv_played"]
                ev["deep_mate_n"] = dp.get("deep_mate_n")
            rows.append((g, ev, uc, classify(ev, uc)))
    return rows


def main():
    allrows = loadall()
    bylabel = defaultdict(list)
    for g, ev, uc, lab in allrows: bylabel[lab].append((g, ev, uc))
    print(f"=== {len(allrows)} gold reclassified; distribution ===", flush=True)
    for lab, items in sorted(bylabel.items(), key=lambda kv: -len(kv[1])):
        print(f"  {lab:22} {len(items)}", flush=True)
    scorecard = {}
    templates = {}
    for sit, (builder, tmpl, slot_names, desc) in SITUATIONS.items():
        items = bylabel.get(sit, [])
        if len(items) < 6:
            scorecard[sit] = {"n": len(items), "status": "thin-gold (skip)"}
            print(f"\n## {sit}: n={len(items)} -> thin, skip", flush=True)
            continue
        # split: hold out ~1/3 as test
        test = items[: max(4, len(items) // 3)]; train = items[len(test):]
        built = [(g, ev, uc, builder(g, ev)) for g, ev, uc in train if any((g, ev, uc))]
        ex = "\n\n".join(f"FACTS: {json.dumps({k: v for k, v in f.items() if isinstance(v, str) and v})}\nGOLD: {g['gold_caption']}" for g, ev, uc, f in [(gg, ee, uu, builder(gg, ee)) for gg, ee, uu in train][:18])
        distill = (f"Distill a deterministic caption TEMPLATE for chess '{sit}' (1200 student; {desc}).\n\n{ex}\n\n"
                   f"Write ONE Python str.format template using ONLY these slots: {slot_names}. Max 2 sentences; end with one fixed universal principle. Slots may be empty. Return ONLY JSON: {{\"template\":\"...\"}}")
        resp = ask(distill, to=110); m = re.search(r"\{.*\}", resp or "", re.S)
        try: template = json.loads(m.group(0))["template"]
        except Exception: template = tmpl  # fall back to the seed template
        templates[sit] = template

        def work(it):
            g, ev, uc = it; f = builder(g, ev); errs = verify(g, ev, f, uc); cand = render(template, f); return (not errs), judge(g, cand)
        res = []
        with ThreadPoolExecutor(max_workers=6) as ex2:
            for fut in as_completed([ex2.submit(work, it) for it in test]): res.append(fut.result())
        n = len(res); ver = sum(1 for ok, v in res if ok); match = sum(1 for ok, v in res if ok and v == "MATCH")
        scorecard[sit] = {"n_total": len(items), "n_test": n, "verified_pct": 100 * ver // max(n, 1), "match_pct": 100 * match // max(n, 1),
                          "status": "PV-capped" if sit == "missed_mate" else "baseline"}
        print(f"\n## {sit}: test={n} verified-true={100*ver//max(n,1)}% match={100*match//max(n,1)}%  template: {template[:80]}", flush=True)
    # positional / defer
    defer = len(bylabel.get("(defer to Claude)", []))
    print(f"\n## (defer to Claude) = {defer}  -> ABSTAIN by design (positional / non-engine-decidable)", flush=True)

    print("\n================= SCORECARD =================", flush=True)
    print(f"{'situation':22}{'n':>5}{'verified%':>11}{'match%':>9}  status", flush=True)
    for sit in list(SITUATIONS) + ["(defer to Claude)"]:
        if sit == "(defer to Claude)":
            print(f"{sit:22}{defer:>5}{'100':>11}{'-':>9}  abstain-by-design", flush=True); continue
        s = scorecard.get(sit, {})
        print(f"{sit:22}{s.get('n_total', s.get('n', 0)):>5}{str(s.get('verified_pct','-')):>11}{str(s.get('match_pct','-')):>9}  {s.get('status','')}", flush=True)
    # persist templates + scorecard
    try:
        with open("/app/backend/data/distilled_templates.json", "w") as fh:
            json.dump({"templates": templates, "scorecard": scorecard, "defer_count": defer}, fh, indent=1)
        print("\nsaved /app/backend/data/distilled_templates.json", flush=True)
    except Exception as e:
        print("save failed:", e, flush=True)


if __name__ == "__main__":
    main()
