"""Distilled caption service (2026-06-16) — the production renderer for the validated
distilled-template system. Pure + deterministic: classify a move -> fill the distilled
template from engine facts -> verify every claim on the board -> return caption or None.
NO DB, NO LLM at runtime. Loaded by build_move_teaching_decision behind the
DISTILLED_CAPTIONS_ENABLED flag (default OFF).

Validated (backend/scripts/validate_everymove.py): 91% coverage / 99% truth on real games.
Templates: backend/data/distilled_templates.json (mistake + good_move templates).
"""
import os
import json
import chess
from typing import Optional, Tuple

P = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop", chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
VAL = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300, chess.ROOK: 500, chess.QUEEN: 900}
CENTRAL = {chess.C4, chess.D4, chess.E4, chess.C5, chess.D5, chess.E5, chess.D3, chess.E3, chess.D6, chess.E6}

_TPL_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "distilled_templates.json")
try:
    _DATA = json.load(open(_TPL_PATH))
except Exception:
    _DATA = {}
MISTAKE_T = _DATA.get("templates", {})
GOOD_T = _DATA.get("good_move_templates", {})


def _upov(x, uc):
    return None if x is None else (x if uc == "white" else -x)


def _push_any(b, mv):
    for fn in (b.parse_san, lambda x: chess.Move.from_uci(x)):
        try:
            b.push(fn(mv)); return True
        except Exception:
            pass
    return False


def _pv_material(fb, played, pvp):
    if not fb or not pvp:
        return None
    try:
        b = chess.Board(fb); uc = b.turn; b.push(chess.Move.from_uci(b.parse_san(played).uci()))
    except Exception:
        return None
    um = lambda bb: sum(VAL[pt] * len(bb.pieces(pt, uc)) for pt in VAL)
    start = um(b); mats = []
    for mv in pvp[:6]:
        if not _push_any(b, mv):
            break
        mats.append(um(b))
    if not mats or mats[-1] >= start - 100:
        return None
    depth = next((i for i, v in enumerate(mats, 1) if v <= start - 200), None) or next((i for i, v in enumerate(mats, 1) if v <= start - 100), 99)
    return "one_move_blunder" if depth <= 2 else "walked_into_tactic"


def _missed_free(fb, played, best):
    if not best or "x" not in best:
        return False
    try:
        b = chess.Board(fb); bm = b.parse_san(best); cap = b.piece_at(bm.to_square)
        if not cap or played == best:
            return False
        return len(b.attackers(cap.color, bm.to_square)) == 0
    except Exception:
        return False


def _classify_mistake(inp):
    uc = inp.user_color
    ueb = _upov(inp.eval_before_cp, uc); uea = _upov(inp.eval_after_cp, uc)
    if uea is not None and uea <= -9000:
        return "allowed_mate"
    if ueb is not None and ueb >= 9000 and (uea is None or uea < 9000):
        return "missed_mate"
    pm = _pv_material(inp.fen_before, inp.played_san, inp.pv_after_played or [])
    if pm:
        return pm
    if _missed_free(inp.fen_before, inp.played_san, inp.best_move_san):
        return "missed_free_material"
    san = inp.played_san or ""
    if san.startswith("Q") and (inp.full_move_number or 99) <= 6 and "x" not in san:
        return "opening_knowledge"
    return None


def _line_won(board, pv, mover):
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


def _best_purpose(fb, best, mover, hung_sq):
    try:
        bb = chess.Board(fb); bmv = bb.parse_san(best); bp = bb.piece_at(bmv.from_square)
        after = chess.Board(fb); after.push(bmv)
        develops = bp and bp.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(bmv.from_square) in (0, 7)
        sdef = hung_sq is not None and (hung_sq in after.attacks(bmv.to_square))
        weak = chess.F7 if mover == chess.WHITE else chess.F2
        if bb.is_capture(bmv):
            t = bb.piece_at(bmv.to_square)
            if t:
                return f"it captures the {P[t.piece_type]} on {chess.square_name(bmv.to_square)}", ("cap", t.piece_type, bmv.to_square)
        if develops and sdef:
            return f"it develops your {P[bp.piece_type]} and defends {chess.square_name(hung_sq)}", ("def", bmv.to_square, hung_sq, True)
        if sdef:
            return f"it defends {chess.square_name(hung_sq)}", ("def", bmv.to_square, hung_sq, False)
        if develops and weak in after.attacks(bmv.to_square):
            return f"it develops your {P[bp.piece_type]}, eyeing {chess.square_name(weak)}", ("eye", bmv.to_square, weak)
        if develops:
            return f"it develops your {P[bp.piece_type]} toward the center", ("dev", bmv.from_square)
    except Exception:
        pass
    return "", None


def _mistake_caption(inp, lab):
    """Build + verify a mistake caption. Returns caption or None (abstain on verify-fail)."""
    fb = inp.fen_before; best = inp.best_move_san; mover = chess.WHITE if inp.mover_is_white else chess.BLACK
    pvp = inp.pv_after_played or []; pvb = inp.pv_after_best or []
    slots = {"played_san": inp.played_san, "best_san": best, "hung_piece": "", "hung_square": "", "opp_reply_san": "", "front": "", "best_purpose": "", "win": ""}
    try:
        if lab in ("one_move_blunder",):
            b2 = chess.Board(fb); b2.push_san(inp.played_san)
            if not pvp:
                return None
            mv = b2.parse_san(pvp[0]); cap = b2.piece_at(mv.to_square)
            if not (cap and cap.color == mover):
                return None
            slots["hung_piece"] = P[cap.piece_type]; slots["hung_square"] = chess.square_name(mv.to_square); slots["opp_reply_san"] = pvp[0]
            bp, _ = _best_purpose(fb, best, mover, mv.to_square); slots["best_purpose"] = bp
        elif lab == "walked_into_tactic":
            b2 = chess.Board(fb); b2.push_san(inp.played_san); lost = None
            cpl = inp.cp_loss or 0
            for san in pvp[:6]:
                try:
                    mv = b2.parse_san(san)
                except Exception:
                    break
                c = b2.piece_at(mv.to_square)
                # only a CLEAN loss: opp captures our >=minor piece AND cp_loss is consistent with
                # actually losing it (>= ~half its value) — filters out recaptured trades.
                if (c and c.color == mover and b2.turn != mover and VAL[c.piece_type] >= 300
                        and cpl >= VAL[c.piece_type] * 0.5 and (not lost or VAL[c.piece_type] > VAL[lost[1]])):
                    lost = (san, c.piece_type, mv.to_square)
                b2.push(mv)
            if lost:
                slots["front"] = f"{inp.played_san} walks into {lost[0]}, losing your {P[lost[1]]} on {chess.square_name(lost[2])}"
                bp, _ = _best_purpose(fb, best, mover, lost[2]); slots["best_purpose"] = bp
            elif pvp:
                # net material is lost (classify confirmed) but no single clean piece-drop -> generic, true
                slots["front"] = f"{inp.played_san} walks into {pvp[0]}, and the line costs you material"
                bp, _ = _best_purpose(fb, best, mover, None); slots["best_purpose"] = bp
            else:
                return None
        elif lab == "missed_free_material":
            b = chess.Board(fb); bm = b.parse_san(best); cap = b.piece_at(bm.to_square)
            if not (cap and cap.color != mover and len(b.attackers(cap.color, bm.to_square)) == 0):
                return None
            slots["win"] = f"wins the {P[cap.piece_type]} on {chess.square_name(bm.to_square)} for free — it is undefended"
        elif lab == "missed_mate":
            ueb = _upov(inp.eval_before_cp, inp.user_color)
            if not (ueb is not None and ueb >= 9000):
                return None
            mv0 = pvb[0] if pvb else best
            slots["win"] = f"{mv0} starts a forcing line that wins on the spot"
        elif lab == "allowed_mate":
            uea = _upov(inp.eval_after_cp, inp.user_color)
            if not (uea is not None and uea <= -9000):
                return None
        elif lab == "opening_knowledge":
            pass
        else:
            return None
    except Exception:
        return None
    tmpl = MISTAKE_T.get(lab) or _SEED_MISTAKE.get(lab)
    if not tmpl:
        return None
    try:
        cap = tmpl.format(**{k: (v if v else "") for k, v in slots.items()})
    except Exception:
        return None
    import re
    # drop a dangling connector when its clause (best_purpose) came out empty
    cap = re.sub(r"\b(?:because|since)\s*,?\s*(?=whereas|,|\.|$)", "", cap, flags=re.I)
    cap = re.sub(r",?\s*(?:since|because|which)\s*\.", ".", cap)
    cap = re.sub(r"\s{2,}", " ", cap).replace(" .", ".").replace(" ,", ",").strip()
    return cap or None


_SEED_MISTAKE = {
    "one_move_blunder": "{played_san} hangs your {hung_piece} on {hung_square} to {opp_reply_san}; instead play {best_san} — {best_purpose}. Before any capture or move, check what can recapture and count the material first.",
    "walked_into_tactic": "{front}; {best_san} was stronger. Before a quiet move, check that none of your pieces can be won by a tactic.",
    "missed_free_material": "{played_san} missed {best_san} — it {win}. When an enemy piece sits undefended, grab the free material first.",
    "missed_mate": "{played_san} missed a forced mate — {win}. Always scan for forcing checks first; a mate ends the game.",
    "allowed_mate": "{played_san} allows a forced mate; {best_san} was needed. Check your king's safety before every move.",
    "opening_knowledge": "{played_san} brings the queen out too early — develop a knight or bishop like {best_san} first, before the queen can be chased.",
}


def _subtype(board, mv):
    pc = board.piece_at(mv.from_square)
    if not pc:
        return None
    pt = pc.piece_type; mover = board.turn
    if pt == chess.QUEEN:
        tr = chess.square_rank(mv.to_square)
        if (tr <= 1 if mover == chess.WHITE else tr >= 6):
            return "queen_safety"
        if mv.to_square in CENTRAL:
            return "centralize"
    elif pt == chess.ROOK:
        f = chess.square_file(mv.to_square)
        own = any((p := board.piece_at(chess.square(f, r))) and p.piece_type == chess.PAWN and p.color == mover for r in range(8))
        return "rook_activity" if own else "rook_open_file"
    elif pt in (chess.KNIGHT, chess.BISHOP) and mv.to_square in CENTRAL:
        return "centralize"
    elif pt == chess.PAWN:
        ff = chess.square_file(mv.from_square); tf = chess.square_file(mv.to_square)
        adv = abs(chess.square_rank(mv.to_square) - chess.square_rank(mv.from_square))
        if ff == tf and ff in (0, 7) and adv == 1:
            return "luft"
        if ff == tf and ff in (0, 1, 6, 7) and adv >= 1:
            return "space"
    return None


def _good_caption(inp):
    """Good-move (cp<100) teaching caption + verify. Returns caption or None."""
    fb = inp.fen_before; san = inp.played_san
    try:
        b = chess.Board(fb); mv = b.parse_san(san)
    except Exception:
        return None, None
    pc = b.piece_at(mv.from_square)
    piece = P.get(pc.piece_type, "piece") if pc else "piece"
    to_sq = chess.square_name(mv.to_square)
    if san in ("O-O", "O-O-O"):
        gt = "castle"
    elif b.is_capture(mv):
        # gate "free": only if the captured piece is undefended after the capture
        after = b.copy(); after.push(mv); target = b.piece_at(mv.to_square)
        if target and len(after.attackers(not b.turn, mv.to_square)) == 0:
            return ("good_capture_free", f"{san} snaps up the free {P[target.piece_type]}, winning material — when an enemy piece sits undefended and it is safe to take, take it.")
        return ("good_recapture", f"{san} recaptures to keep material even — when your opponent takes, take back so you don't fall behind.")
    else:
        st = _subtype(b, mv)
        if st and GOOD_T.get(st):
            gt = st
        elif pc and pc.piece_type == chess.PAWN:
            gt = "pawn"
        elif pc and pc.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(mv.from_square) in (0, 7):
            gt = "develop"
        else:
            gt = "other"
    tmpl = GOOD_T.get(gt) or GOOD_T.get("other")
    if not tmpl:
        return None, None
    try:
        cap = tmpl.format(move=san, piece=piece, to_square=to_sq)
    except Exception:
        return None, None
    import re
    return ("good_" + gt, re.sub(r"\s{2,}", " ", cap).strip())


def try_distilled_caption(inp) -> Optional[Tuple[str, str]]:
    """Entry point. Returns (caption, rule_name) or None (abstain). NO LLM, NO DB."""
    if not GOOD_T and not MISTAKE_T:
        return None
    try:
        cp = inp.cp_loss or 0
        if cp >= 100:
            lab = _classify_mistake(inp)
            if not lab:
                return None
            cap = _mistake_caption(inp, lab)
            return (cap, "distilled:" + lab) if cap else None
        else:
            rn, cap = _good_caption(inp)
            return (cap, "distilled:" + rn) if cap else None
    except Exception:
        return None
