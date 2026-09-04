"""caption_claim_verifier.py — verify a caption's CHESS CLAIM against engine
truth before it ships (2026-06-11, verified_detector_loop scope).

Complements caption_verifier.py (which scrubs hallucinated entity NAMES at the
text level). This layer checks whether the concrete CLAIM is true on the board:
"does the rook really attack e3?", "is this really the engine's best?", "does the
engine line actually win the material?".

Rule: a detector caption ships only if its primary-reason claim verifies. If it
can't be verified, the caller ABSTAINS (hands the move to the narrator) — never
ships an unverified claim. Detectors become "right or silent".

Uses python-chess + the facts we already store (fen_before, played_san,
pv_after_played, eval_*, cp_loss, and the per-category evidence dicts). NO new
Stockfish. Hooks onto caption_facts.extract_primary_reason() output.

verify(facts, primary_reason) -> (ok: bool, note: str)
  ok=True  -> claim is board/engine-true; render it.
  ok=False -> ABSTAIN (note=why) -> narrator.

V1 covers the cleanly-checkable categories. Categories not yet covered return
ok=False (abstain) — SAFE by construction (narrator handles them); the abstention
log says which checkers to build next.
"""
import chess
from typing import Any, Dict, Optional, Tuple


def _board_after(facts: Dict[str, Any]) -> chess.Board:
    b = chess.Board(facts["fen_before"])
    b.push_san(facts["played_san"])
    return b


def _attacks(board: chess.Board, from_sq: str, target_sq: str) -> bool:
    try:
        return chess.parse_square(target_sq) in board.attacks(chess.parse_square(from_sq))
    except Exception:
        return False


def _verify_threats(facts: Dict[str, Any], min_see: int = 0) -> bool:
    """A created-threat is real only if the named attacker actually attacks the
    named target on the post-move board AND the target holds an enemy piece.
    This is the check that rejects 'Re1 threatens the bishop on e3' when the e1
    rook does not attack e3."""
    threats = facts.get("threats_created") or []
    if not threats:
        return False
    b = _board_after(facts)
    opp = b.turn  # after our move, side-to-move == opponent; their pieces are 'opp'
    for t in threats:
        a, tg = t.get("attacker_square"), t.get("target_square")
        if not (a and tg):
            continue
        if not _attacks(b, a, tg):
            continue
        if (t.get("see_cp", 0) or 0) < min_see:
            continue
        pc = b.piece_at(chess.parse_square(tg))
        if pc is not None and pc.color == opp:
            return True
    return False


def _verify_tactic(facts: Dict[str, Any], ref_field: Optional[str]) -> bool:
    """multi_target / discovered / aligned: the named attacker actually attacks
    the named target(s) on the post-move board."""
    ev = facts.get(ref_field) or []
    if not ev:
        return False
    b = _board_after(facts)
    for e in ev:
        if not isinstance(e, dict):
            continue
        a = e.get("attacker_square") or e.get("from_square") or e.get("attacker_sq")
        cands = []
        if e.get("target_square"):
            cands.append(e["target_square"])
        for tgt in (e.get("targets") or []):
            cands.append(tgt.get("square") if isinstance(tgt, dict) else tgt)
        if a and any(_attacks(b, a, c) for c in cands if c):
            return True
    return False


def _san_in_pv(san: str, pv) -> bool:
    """Is a claimed SAN move actually in the engine line? Normalises +/#/!? so
    'Qh4+' matches 'Qh4'. pv is a list of SAN strings as stored."""
    if not san or not pv:
        return False
    def norm(s):
        return (s or "").replace("+", "").replace("#", "").replace("!", "").replace("?", "").strip()
    n = norm(san)
    return any(norm(m) == n for m in pv)


def _opp_reply_forks(facts: Dict[str, Any]) -> bool:
    """The claimed fork is real only if the opponent's reply piece, on its
    landing square, attacks >=2 of the user's non-pawn pieces."""
    opp = facts.get("opp_reply_san")
    if not opp:
        return False
    b = _board_after(facts)  # opponent to move
    try:
        mv = b.parse_san(opp)
        land = mv.to_square
        b.push(mv)
    except Exception:
        return False
    user = b.turn  # after opp's reply, side-to-move == the user
    n = 0
    for s in b.attacks(land):
        pc = b.piece_at(s)
        if pc is not None and pc.color == user and pc.piece_type != chess.PAWN:
            n += 1
    return n >= 2


def _opp_reply_is_capture(facts: Dict[str, Any]) -> bool:
    """A 'they take / recapture / win the piece' clause is real only if the
    opponent's engine reply is actually a capture."""
    opp = facts.get("opp_reply_san")
    if not opp:
        return False
    b = _board_after(facts)
    try:
        return b.is_capture(b.parse_san(opp))
    except Exception:
        return False


_PIECE_VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
              chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


def _played_capture_net(facts: Dict[str, Any]) -> Optional[int]:
    """Net material of the played move ASSUMING the moved piece is then
    recaptured on its landing square: value(piece the played move captured) -
    value(the played piece itself).

    Returns None when the played move was NOT a capture (the recapture framing
    does not apply). A result >= -1 means an even-or-better trade — i.e. the
    moved piece was NOT hung; it was traded. That makes any "you hang / lose
    your {piece}" material claim false: it is a (positionally bad) trade, which
    is narrator territory, not a material hang. NO Stockfish — board geometry
    only, consistent with this module's contract."""
    try:
        b = chess.Board(facts["fen_before"])
        mv = b.parse_san(facts["played_san"])
        if not b.is_capture(mv):
            return None
        cap_v = 1 if b.is_en_passant(mv) else _PIECE_VAL.get(
            (b.piece_at(mv.to_square) or chess.Piece(chess.PAWN, True)).piece_type, 0)
        played_v = _PIECE_VAL.get(b.piece_at(mv.from_square).piece_type, 0)
        return cap_v - played_v
    except Exception:
        return None


def _verify_blunder(facts: Dict[str, Any]) -> Tuple[bool, str]:
    """Blunder why-clause. The engine PV is the arbiter (a tactical win counts,
    not just a simple hang). Verify:
      1. the '{best} was better' half — best_move is a legal move,
      2. the loss is real — cp_loss is present (the category gate already
         required >=30; we re-confirm it is set), and
      3. any SPECIFIC tactical failure clause (fork / recapture / wins-piece)
         holds geometrically on the post-move board. A present-but-false
         specific claim => ABSTAIN (that is the confabulation class)."""
    cpl = facts.get("cp_loss")
    if cpl is None or cpl < 30:
        return (False, "blunder_no_loss")
    best = facts.get("best_move_san")
    if best:
        try:
            chess.Board(facts["fen_before"]).parse_san(best)
        except Exception:
            return (False, "blunder_best_illegal")
    # Specific tactical claims that R12 turns into prose must verify.
    if facts.get("opp_reply_creates_fork") and not _opp_reply_forks(facts):
        return (False, "blunder_fork_geom_fail")
    if (facts.get("opp_reply_recaptures_on_played_square")
            or facts.get("opp_reply_captures_piece_type")):
        if not _opp_reply_is_capture(facts):
            return (False, "blunder_reply_not_capture")
        # "hangs your {piece} — opponent recaptures on {sq}" is a MATERIAL claim.
        # If the played move was itself a capture and the recapture nets even-or-
        # better material (>= -1), the piece was TRADED, not hung — the move is a
        # positional mistake, not a material loss. Shipping "you hang it" is then
        # a confident false claim (53 such moves in a 3k-game scan, e.g. Nxf5
        # exf5, Bxd5 cxd5: net 0, cp_loss>=100 for positional reasons). Abstain
        # so the narrator explains the real (positional) why. See CAPTION_BACKLOG #24.
        net = _played_capture_net(facts)
        if net is not None and net >= -1:
            return (False, "blunder_recapture_even_trade")
    # "best opens the line, your {piece} plays {follow_up} to chase the king"
    # (Légal-family clearance-then-check). The named follow-up move is a claim
    # about the engine's BEST line — it must actually appear in pv_after_best,
    # else it is the "chase the king" confabulation (m9 Qh4+, m13 Bf2+ — the
    # engine plays Nf3/Bxc4, never the claimed check).
    fu = facts.get("missed_clearance_then_check_follow_up_san")
    if fu and not _san_in_pv(fu, facts.get("pv_after_best")):
        return (False, "blunder_clearance_followup_not_in_pv")
    ofu = facts.get("opp_user_reply_clearance_follow_up_san")
    if ofu and not _san_in_pv(ofu, facts.get("pv_after_played")):
        return (False, "blunder_opp_clearance_followup_not_in_pv")
    return (True, "blunder_pv_verified")


def _verify_mate_transition(facts: Dict[str, Any]) -> Tuple[bool, str]:
    evidence = facts.get("mate_threat_evidence")
    if not isinstance(evidence, dict):
        return (False, "mate_unconfirmed")
    transition = evidence.get("transition")
    if transition not in {
        "delivered", "preserved", "missed", "allowed", "already_lost"
    }:
        return (False, "mate_transition_missing")
    played = evidence.get("played_branch")
    best = evidence.get("best_branch")
    if not isinstance(played, dict) or not isinstance(best, dict):
        return (False, "mate_branch_missing")
    if played.get("evidence_conflict") or best.get("evidence_conflict"):
        return (False, "mate_branch_conflict")

    mover = evidence.get("mover_color") or facts.get("moving_piece_color")
    if mover not in {"white", "black"}:
        return (False, "mate_mover_missing")
    opponent = "black" if mover == "white" else "white"

    def proves(branch: Dict[str, Any], side: str) -> bool:
        return bool(
            branch.get("has_forced_mate")
            and branch.get("side_delivering_mate") == side
        )

    if transition == "delivered":
        ok = bool(facts.get("is_checkmate")) and proves(played, mover)
    elif transition == "preserved":
        ok = proves(played, mover)
    elif transition == "missed":
        ok = proves(best, mover) and not played.get("has_forced_mate")
    elif transition == "allowed":
        ok = proves(played, opponent) and not proves(best, opponent)
    else:  # already_lost
        ok = proves(best, opponent)
    return (ok, f"mate_{transition}" if ok else f"mate_{transition}_invalid")


def verify(facts: Dict[str, Any],
           primary_reason: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    if not facts or not primary_reason:
        return (False, "no_primary")
    cat = primary_reason.get("category")
    ref = primary_reason.get("ref_field")
    try:
        if cat == "mate":
            return _verify_mate_transition(facts)
        if cat == "check_plain":
            return (_board_after(facts).is_check(), "check")
        if cat == "check_extra":
            ok = _board_after(facts).is_check() and _verify_threats(facts)
            return (ok, "check_extra" if ok else "check_extra_unverified")
        if cat == "threat":
            ok = _verify_threats(facts, min_see=200)
            return (ok, "threat_geom" if ok else "threat_unverified")
        if cat == "forced_recapture":
            b = chess.Board(facts["fen_before"])
            ok = b.is_capture(b.parse_san(facts["played_san"]))
            return (ok, "recapture" if ok else "not_capture")
        if cat == "material":
            b = chess.Board(facts["fen_before"])
            ok = (b.is_capture(b.parse_san(facts["played_san"]))
                  and (facts.get("material_delta_played_cp") or 0) > 0)
            return (ok, "material" if ok else "material_unverified")
        if cat == "king_safety":
            return (bool(facts.get("is_castling")), "castle")
        if cat == "tactic_played":
            ok = _verify_tactic(facts, ref)
            return (ok, "tactic_geom" if ok else "tactic_unverified")
        if cat == "blunder":
            return _verify_blunder(facts)
    except Exception as e:
        return (False, f"verify_err:{e}")
    # Anything not yet covered (incl. R12 blunder why-clauses) -> abstain.
    # SAFE: narrator handles it; the abstention log queues the checker to build.
    return (False, f"uncovered:{cat}")
