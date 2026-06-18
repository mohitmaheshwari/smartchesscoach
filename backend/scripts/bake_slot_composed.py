"""Slot-composer (Why-Now Coach Layer): build each caption from 6 VERIFIED slots —
opening / assessment(cp-class) / what-it-does(board) / better-move(Stockfish multipv) /
plan(Stockfish PV, principle-aligned) / principle. All computed OFFLINE at bake time,
verified, cached. Implements the architecture derived from the d3 ground-truth sheet.

Env: PMONGO. Usage: python scripts/bake_slot_composed.py <game_id> [--apply]
"""
import os, sys, re, shutil
sys.path.insert(0, "/app/backend"); sys.path.insert(0, "/app/backend/scripts")
import pymongo, chess, chess.engine
from services.distilled_caption_service import (P, _subtype, _material, _classify_mistake,
                                                _mistake_caption, _opening_caption, _passes_verify)
from services.caption_pipeline import MoveInputs

SF = shutil.which("stockfish") or "/usr/games/stockfish"
BACK_RANKS = (0, 7)


def classify(cp):
    cp = abs(cp or 0)
    return "best" if cp <= 10 else "good" if cp <= 40 else "inacc" if cp < 100 else "mistake"


def move_phrase(b, mv, is_user=True):
    """(piece, 'what it does' — easy English, board-true). Possessive flips for the
    opponent: 'your' -> 'the opponent's'/'their'; a capture takes YOUR piece."""
    pc = b.piece_at(mv.from_square); pt = pc.piece_type if pc else None
    piece = P.get(pt, "piece")
    own = "your" if is_user else "the opponent's"   # the mover's own pieces
    pl = "your" if is_user else "their"             # plural possessive for the mover
    king = "your king" if is_user else "their king"
    if b.is_castling(mv):
        return "king", f"gets {king} safe and brings a rook toward the middle"
    if b.is_capture(mv):
        tgt = b.piece_at(mv.to_square)
        tn = P.get(tgt.piece_type, "piece") if tgt else "piece"
        return piece, (f"takes the {tn}" if is_user else f"takes your {tn}")
    st = _subtype(b, mv)
    ph = {
        "centralize": f"puts {own} {piece} on an active square in the middle",
        "queen_safety": f"tucks {own} {piece} back to a safe square",
        "space": "grabs a little space",
        "luft": f"gives {king} some air",
        "rook_open_file": f"puts {own} {piece} on an open file",
        "rook_activity": f"makes {own} {piece} more active",
    }
    if st in ph:
        return piece, ph[st]
    if pt == chess.PAWN:
        return piece, f"fights for the middle and opens lines for {pl} pieces"
    if pt in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(mv.from_square) in BACK_RANKS:
        return piece, f"brings {own} {piece} out toward the middle"
    return piece, f"improves {own} {piece}"


def undeveloped_minors(b, color):
    n = 0
    for pt in (chess.KNIGHT, chess.BISHOP):
        for sq in b.pieces(pt, color):
            if chess.square_rank(sq) in (0 if color == chess.WHITE else 7,):
                n += 1
    return n


def plan_clause(eng, fen_after, is_user, user_color):
    """Principle-aligned next step. If the user still has pieces at home, teach
    DEVELOP (name a developing next move if the engine plays one; else the general
    rule) rather than echoing a quiet flank pawn."""
    try:
        b = chess.Board(fen_after)
    except Exception:
        return ""
    if b.is_game_over():
        return ""
    try:
        pv = eng.analyse(b, chess.engine.Limit(depth=14)).get("pv") or []
    except Exception:
        pv = []
    # user's next move ply in the PV
    idx = 1 if is_user else 0
    nxt_mv = pv[idx] if len(pv) > idx else None
    nxt_san = None
    if nxt_mv is not None:
        bb = chess.Board(fen_after)
        for j, x in enumerate(pv[:idx + 1]):
            try:
                s = bb.san(x)
            except Exception:
                break
            if j == idx:
                nxt_san = s
            bb.push(x)
    uc = chess.WHITE if user_color == "white" else chess.BLACK
    home = undeveloped_minors(b, uc)
    # is the engine's next user move a developing move?
    dev_next = False
    if nxt_mv is not None:
        pc = b.piece_at(nxt_mv.from_square) if (is_user is False) else None
        # only trust dev-detection when it's the user to move now (opp just moved)
        if not is_user and pc and pc.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(nxt_mv.from_square) in BACK_RANKS:
            dev_next = True
    if home >= 1:
        if dev_next and nxt_san:
            return f"Keep developing — {nxt_san} is a good next move."
        return "Keep getting your pieces out and aim to castle soon."
    if nxt_san:
        return f"A good next move is {nxt_san}."
    return ""


def principle(cls, phase, is_user):
    if not is_user:
        return "Answer your opponent's moves, but keep finishing your own development."
    if phase == "opening":
        return "In the opening, get your pieces out fast and make your king safe."
    if phase == "endgame":
        return "In the endgame, use your king and push your passed pawns."
    return "Each move, improve your worst-placed piece or make a real threat."


def compose(m, eng, hist):
    fb = m.get("fen_before"); san = m.get("move_san"); is_user = bool(m.get("is_user_move"))
    user_color = "white"
    phase = m.get("phase") or "middlegame"
    cpl = abs(int(m.get("cp_loss") or 0))
    try:
        b = chess.Board(fb); mv = b.parse_san(san)
    except Exception:
        return None
    inp = MoveInputs(fen_before=fb, played_san=san, mover_is_user=is_user, mover_is_white=bool(m.get("is_white")),
                     user_color=user_color, full_move_number=int(m.get("move_number") or 0),
                     move_history_san=list(hist), best_move_san=m.get("best_move_san"),
                     eval_before_cp=m.get("eval_before"), eval_after_cp=m.get("eval_after"), cp_loss=cpl,
                     pv_after_played=m.get("pv_after_played") or [], pv_after_best=m.get("pv_after_best") or [])
    cls = classify(cpl)
    plan = plan_clause(eng, m.get("fen_after"), is_user, user_color)
    prin = principle(cls, phase, is_user)
    # slot 1: opening name (recognized line, opening phase) — leads with the opening
    # name (gold-quality) + the plan; restores the Sicilian/Bowdler naming.
    oc = _opening_caption(inp)
    if oc and oc[0]:
        return _join([oc[0], plan])

    if is_user:
        if cls == "mistake":
            from services.distilled_caption_service import try_distilled_caption
            base = try_distilled_caption(inp)
            head = base[0] if base and base[0] else None
            if not head:
                return None
            return _join([head, plan])  # mistake caption already carries best+why+principle
        # good / best / inacc -> compose slots 2+3+4
        piece, phrase = move_phrase(b, mv)
        # better move via Stockfish multipv
        best_san, rank = _best_and_rank(eng, b, mv)
        if cls == "best" or rank == 1:
            head = f"{san} is the best move here — it {phrase}."
        elif cls == "good":
            head = f"{san} is a good move — it {phrase}."
        else:
            head = f"{san} is okay — it {phrase}."
        better = ""
        if rank and rank > 1 and best_san and cls != "best":
            try:
                bphrase = move_phrase(b, b.parse_san(best_san))[1]
                better = f"A move like {best_san} was a little better, since it {bphrase}."
            except Exception:
                better = f"A move like {best_san} was a little sharper here."
        return _join([head, better, plan, prin])
    else:
        # opponent move
        if cls == "mistake":
            from services.distilled_caption_service import try_distilled_caption
            base = try_distilled_caption(inp)
            head = base[0] if base and base[0] else None
            if not head:
                return None
            return _join([head, plan])
        piece, phrase = move_phrase(b, mv, is_user=False)
        head = f"Your opponent played {san} — it {phrase}."
        return _join([head, plan, prin])


def _best_and_rank(eng, b, mv):
    try:
        infos = eng.analyse(b, chess.engine.Limit(depth=16), multipv=5)
        ranked = [i.get("pv", [None])[0] for i in infos]
        best_san = b.san(ranked[0]) if ranked and ranked[0] else None
        rank = next((i + 1 for i, x in enumerate(ranked) if x == mv), None)
        return best_san, rank
    except Exception:
        return None, None


def _join(parts):
    s = " ".join(p.strip() for p in parts if p and p.strip())
    return re.sub(r"\s{2,}", " ", s).strip()


def main():
    gid = sys.argv[1]; apply = "--apply" in sys.argv
    db = pymongo.MongoClient(os.environ["PMONGO"])["chess_coach"]
    ga = db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "decryption_v5_data": 1})
    dd = (ga or {}).get("decryption_v5_data") or []
    eng = chess.engine.SimpleEngine.popen_uci(SF)
    done = held = 0
    hist = []
    try:
        for m in dd:
            san0 = m.get("move_san")
            if not san0 or not m.get("fen_before"):
                if san0:
                    hist.append(san0)
                continue
            cap = compose(m, eng, hist)
            hist.append(san0)
            if not cap:
                continue
            # verify (reuse the self-verifier)
            inp = MoveInputs(fen_before=m.get("fen_before"), played_san=m.get("move_san"),
                             mover_is_user=bool(m.get("is_user_move")), mover_is_white=bool(m.get("is_white")),
                             user_color="white", full_move_number=int(m.get("move_number") or 0),
                             move_history_san=[], best_move_san=m.get("best_move_san"),
                             eval_before_cp=m.get("eval_before"), eval_after_cp=m.get("eval_after"),
                             cp_loss=abs(int(m.get("cp_loss") or 0)),
                             pv_after_played=m.get("pv_after_played") or [], pv_after_best=m.get("pv_after_best") or [])
            if not _passes_verify(inp, cap):
                held += 1
                continue
            done += 1
            print(f"  {m.get('move_number')}:{m.get('move_san'):6} {cap[:96]}", flush=True)
            if apply:
                m["narrative"] = cap; m["caption"] = cap; m["rule_name"] = "slot_composed"
    finally:
        eng.quit()
    print(f"composed={done} held={held} apply={apply}", flush=True)
    if apply:
        db.game_analyses.update_one({"game_id": gid}, {"$set": {"decryption_v5_data": dd}})
        print("SAVED")


if __name__ == "__main__":
    main()
