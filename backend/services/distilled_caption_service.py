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
OPP_T = _DATA.get("opp_move_templates", {})  # opponent-voice good-move templates


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
            # 2026-07-14: on mate-score rows the stored best_move sometimes
            # EQUALS the played move ("play Bxe4 instead" after they played
            # Bxe4 — nonsense advice). No real alternative -> abstain and let
            # the narrator/floor handle it.
            if not best or best == inp.played_san:
                return None
        elif lab == "opening_knowledge":
            pass
        else:
            return None
    except Exception:
        return None
    is_user = bool(getattr(inp, "mover_is_user", True))
    if not is_user:
        # Opponent's error = a gift to the user. Only one_move_blunder reframes
        # cleanly (its slots carry no player-voice); abstain on the rest so we
        # never narrate the opponent's mistake in the player's voice.
        if lab != "one_move_blunder":
            return None
        tmpl = _OPP_MISTAKE["one_move_blunder"]
    else:
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


_OPP_MISTAKE = {
    "one_move_blunder": "{played_san} leaves the {hung_piece} on {hung_square} hanging — you can win it with {opp_reply_san}. When your opponent drops a piece, take the free material.",
}

_SEED_MISTAKE = {
    "one_move_blunder": "{played_san} hangs your {hung_piece} on {hung_square} to {opp_reply_san}; instead play {best_san} — {best_purpose}. Before any capture or move, check what can recapture and count the material first.",
    "walked_into_tactic": "{front}; {best_san} was stronger. Before a quiet move, check that none of your pieces can be won by a tactic.",
    "missed_free_material": "{played_san} missed {best_san} — it {win}. When an enemy piece sits undefended, grab the free material first.",
    "missed_mate": "{played_san} missed a forced mate — {win}. Always scan for forcing checks first; a mate ends the game.",
    "allowed_mate": "{played_san} allows a forced mate; {best_san} was needed. Check your king's safety before every move.",
    "opening_knowledge": "{played_san} brings the queen out too early — develop a knight or bishop like {best_san} first, before the queen can be chased.",
}


def _material(board, color):
    """Total material (pawns..queen; king excluded) for one side, in centipawns."""
    return sum(VAL[pt] * len(board.pieces(pt, color)) for pt in VAL)


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
        # "open file" requires NO pawns of EITHER colour on the file. A file with an
        # enemy pawn is HALF-open, not open -> use activity framing, never "no pawns".
        any_pawn = any((p := board.piece_at(chess.square(f, r))) and p.piece_type == chess.PAWN for r in range(8))
        return "rook_activity" if any_pawn else "rook_open_file"
    elif pt in (chess.KNIGHT, chess.BISHOP) and mv.to_square in CENTRAL:
        return "centralize"
    elif pt == chess.PAWN:
        ff = chess.square_file(mv.from_square); tf = chess.square_file(mv.to_square)
        adv = abs(chess.square_rank(mv.to_square) - chess.square_rank(mv.from_square))
        # luft = a shelter pawn one step ahead of the king -> only if the king is on
        # that side. An a/h-pawn push far from the king is just space, not king safety.
        ksq = board.king(mover)
        near_king = ksq is not None and abs(chess.square_file(ksq) - tf) <= 1
        if ff == tf and ff in (0, 7) and adv == 1 and near_king:
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
    is_user = bool(getattr(inp, "mover_is_user", True))
    TSET = GOOD_T if is_user else OPP_T
    prefix = "good_" if is_user else "opp_"
    pc = b.piece_at(mv.from_square)
    piece = P.get(pc.piece_type, "piece") if pc else "piece"
    to_sq = chess.square_name(mv.to_square)
    if san in ("O-O", "O-O-O"):
        gt = "castle"
    elif b.is_capture(mv):
        after = b.copy(); after.push(mv); target = b.piece_at(mv.to_square)
        recapturable = bool(target and len(after.attackers(not b.turn, mv.to_square)) > 0)
        # mover already behind => this capture is restoring lost material (a trade/
        # recapture), NOT winning free material.
        mover_behind = (_material(b, b.turn) - _material(b, not b.turn)) <= -100
        free = bool(target) and not recapturable and not mover_behind
        tgt = P.get(target.piece_type, "piece") if target else "piece"
        if is_user:
            if free:
                return ("good_capture_free", f"{san} wins the free {tgt} — when an enemy piece sits undefended and it is safe to take, take it.")
            return ("good_trade", f"{san} takes the {tgt}. A trade is fine when it keeps your material even — just count what comes off each side.")
        # opponent capturing the student's piece
        if free:
            return ("opp_capture_free", f"{san} grabs your undefended {tgt} — before each move, check which of your pieces are unguarded so you don't give material away.")
        return ("opp_trade", f"{san} takes your {tgt}. If you can, take back to keep the material even.")
    else:
        # don't PRAISE a sub-par move (31-99cp inaccuracy) as "active" / "a safer
        # square" — stay silent rather than reward a move that lost ground.
        if abs(getattr(inp, "cp_loss", 0) or 0) > 30:
            return None, None
        st = _subtype(b, mv)
        if st and TSET.get(st):
            gt = st
        elif pc and pc.piece_type == chess.PAWN:
            gt = "pawn"
        elif pc and pc.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(mv.from_square) in (0, 7):
            gt = "develop"
        else:
            gt = "other"
    tmpl = TSET.get(gt) or TSET.get("other")
    if not tmpl:
        return None, None
    try:
        cap = tmpl.format(move=san, piece=piece, to_square=to_sq)
    except Exception:
        return None, None
    import re
    return (prefix + gt, re.sub(r"\s{2,}", " ", cap).strip())


def _opening_caption(inp):
    """Name the opening (highest teaching value in the opening phase) using the
    deterministic opening_book recognizer. Fires only when the just-played move
    COMPLETES a recognized named line — returns its curated teaching caption."""
    # only in the opening phase — else a recurring SAN (e.g. ...c5 on move 56) gets
    # wrongly named as the opening.
    if int(getattr(inp, "full_move_number", 0) or 0) > 12:
        return None
    try:
        from services.decryption_voice.opening_book import recognize_opening_from_history
        hist = list(getattr(inp, "move_history_san", []) or []) + [inp.played_san]
        ob = recognize_opening_from_history(hist)
        if ob and ob.get("caption"):
            return (ob["caption"], "distilled:opening:" + (ob.get("name") or "book"))
    except Exception:
        pass
    return None


def _passes_verify(inp, cap):
    """Self-verify the caption's claims on the board (free piece / recapture / piece
    on square / mate). Returns False if any claim is board-false -> caller abstains.
    This is the safety net: never ship a board-false claim, even if a template slips."""
    try:
        b = chess.Board(inp.fen_before); b.push_san(inp.played_san); fen_after = b.fen()
    except Exception:
        fen_after = None
    facts = {"move_san": inp.played_san, "fen_before": inp.fen_before, "fen_after": fen_after,
             "is_user_move": bool(getattr(inp, "mover_is_user", True)), "cp_loss": abs(inp.cp_loss or 0),
             "best_move_san": inp.best_move_san, "pv_after_best": inp.pv_after_best or [],
             "pv_after_played": inp.pv_after_played or []}
    try:
        from services.narrator_claim_verifier import verify_caption
        return not verify_caption(cap, facts)
    except Exception:
        return True  # verifier unavailable -> don't block


def _facts_caption(inp):
    """Why-Now Coach Layer (proof slice): consume the CANONICAL verified facts from
    caption_facts (single-source — do NOT recompute) to produce a POSITION-SPECIFIC
    capture/material caption that names the real defender(s), instead of a generic
    move-type template. Returns (caption, rule) or None to fall through."""
    try:
        from services.caption_facts import extract_facts
        f = extract_facts(
            fen_before=inp.fen_before, played_san=inp.played_san, best_move_san=inp.best_move_san,
            eval_before_cp=inp.eval_before_cp, eval_after_cp=inp.eval_after_cp, cp_loss=abs(inp.cp_loss or 0),
            pv_after_played=inp.pv_after_played or [], pv_after_best=inp.pv_after_best or [],
            move_history_san=list(getattr(inp, "move_history_san", []) or []),
            full_move_number=int(getattr(inp, "full_move_number", 0) or 0),
            mover_is_user=bool(getattr(inp, "mover_is_user", True)))
    except Exception:
        return None
    is_user = bool(getattr(inp, "mover_is_user", True))
    cap = f.get("captured_piece_type")
    if not cap:
        return None
    san = inp.played_san
    defs = f.get("effective_defenders_on_target") or []
    # net-material guard: a capture while BEHIND is restoring lost material (a
    # recapture/trade), not "free" — even if nothing guards the square this ply.
    try:
        _b = chess.Board(inp.fen_before)
        behind = (_material(_b, _b.turn) - _material(_b, not _b.turn)) <= -100
    except Exception:
        behind = False
    if behind:
        return ((f"{san} takes the {cap} back to level the material — an even trade. Count both sides before you swap.", "facts:recapture")
                if is_user else
                (f"{san} takes your {cap} to level the material — an even trade.", "facts:opp_recapture"))
    if is_user:
        if not defs:
            return (f"{san} wins the {cap} for free — nothing of theirs guards it. When an enemy piece sits with no defender, take it.", "facts:capture_free")
        dn = " and ".join(f"their {p}" for _, p in defs[:2])
        return (f"{san} takes the {cap}, but {dn} can take back — so it is an even trade. Count attackers and defenders before you swap.", "facts:trade")
    # opponent captured the student's piece
    if not defs:
        return (f"{san} grabs your {cap} and nothing takes back. Before each move, check that your pieces are guarded.", "facts:opp_capture_free")
    dn = " and ".join(f"your {p}" for _, p in defs[:2])
    return (f"{san} takes your {cap}, but {dn} can take back — an even trade. Recapture to keep material level.", "facts:opp_trade")


def try_distilled_caption(inp) -> Optional[Tuple[str, str]]:
    """Entry point. Returns (caption, rule_name) or None (abstain). NO LLM, NO DB."""
    if not GOOD_T and not MISTAKE_T:
        return None
    try:
        cp = inp.cp_loss or 0
        result = None
        # Opening identity first: a book move that completes a named opening is
        # taught by NAME (Sicilian/Italian/...) — more valuable than a generic
        # move-type caption. Only for non-mistakes; a blunder's coaching wins.
        if cp < 100:
            result = _opening_caption(inp)
        # Why-Now proof slice: prefer position-specific facts (names the real
        # defender) over a generic capture template, for non-mistake captures.
        if result is None and cp < 100:
            result = _facts_caption(inp)
        if result is None:
            if cp >= 100:
                lab = _classify_mistake(inp)
                cap = _mistake_caption(inp, lab) if lab else None
                result = (cap, "distilled:" + lab) if cap else None
            else:
                rn, cap = _good_caption(inp)
                result = (cap, "distilled:" + rn) if cap else None
        if not result or not result[0]:
            return None
        # Safety net: abstain if the finished caption makes any board-false claim.
        if not _passes_verify(inp, result[0]):
            return None
        return result
    except Exception:
        return None
