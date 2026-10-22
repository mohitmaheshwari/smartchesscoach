"""What the better move achieves, as structured facts. Pure, no engine, no DB.

Mohit, 2026-10-22: "our engine is our backbone and spine... analyse the moves
better with stockfish and give better engine outputs so our LLM can do a good
job there", and then, on the draft spec: "engine should give us something for
everything".

WHY THIS EXISTS
---------------
`distilled_caption_service._best_purpose` knows two things in practice --
"it captures something" (20.8% of cards) and "it develops" (6.2%) -- and
returns an empty string for everything else, at which point the template
drops its why-clause. It is also an if-chain returning the FIRST match, so on
a capture that also forks and defends it reports only the capture.

This vocabulary was not invented. It came from reasoning over 23 mined
positions one at a time, then measuring every candidate on 7,346 flagged
cards (scratchpad/purpose_prevalence.py):

    attacks a piece that cannot escape  21.7%   avoids a square they attack 14.4%
    moves the attacked piece to safety  14.1%   check that worsens the king  7.1%
    defends the attacked piece           6.9%   a pawn attacks a piece       6.4%
    activates the rook                   6.3%   trades off their piece       5.9%
    denies their counterplay             4.3%   stops their passed pawn      3.5%

    at least one purpose 61.7%   two or more 23.5%

Three findings shaped the design. The vocabulary is about danger and time,
not development -- the top three are 50.2% between them and development never
appeared once in 23 mined positions. On 23.5% of cards there is more than one
true thing to say, so this returns a RANKED LIST and never a winner. And the
residue that nothing explained was not exotica: 94% of it carries a `threat`
the engine already stores, and 23% is mate in one direction or the other.

WHAT CHANGED FROM THE MEASURED LIST
-----------------------------------
`D` is split. It was the largest number and the least disciplined probe,
merging "an enemy piece is hanging" with "every retreat lands on a square we
attack" -- different lessons, and the name overclaimed on the first. The
trapped half routes through game_ledger._piece_trapped_after, which is
already proven on the board and is stricter than what this file would have
written: it requires the owner to be on move, refuses when they are in check,
and counts a capture of equal-or-greater value as a way out.

`F` (supports our passed pawn) is dropped. 0.4%, 28 cards -- not a detector.

PURITY
------
No database, no engine, no caption layer. It takes a position and the stored
lines and returns facts. That is what makes it usable at analysis time, by
the game story, by the tags, and on all 18,920 existing games with no
re-analysis -- and what keeps it away from the arrows, which are built from
`pv_after_played` and must not move.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import chess

VALUE = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
         chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}
NAME = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
        chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}

# How strong a lesson each kind is. The caption layer and the LLM both need
# an order, and leaving it to the position of an `if` is how the old code
# ended up reporting a capture and hiding the fork underneath it.
MATE = 4        # someone is getting mated; nothing else matters
MATERIAL = 3    # material changes hands
SAFETY = 2      # a man was in danger, or walked into it
POSITIONAL = 1  # activity, tempo, structure


@dataclass(frozen=True)
class Purpose:
    """One true thing about the better move, with what proves it."""
    kind: str
    tier: int
    facts: Dict[str, Any] = field(default_factory=dict)
    proof: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "tier": self.tier,
                "facts": dict(self.facts), "proof": self.proof}


# ── board helpers, deliberately small and checkable ───────────────────

def _undefended(board: chess.Board, sq: int, owner: chess.Color) -> bool:
    return bool(board.attackers(not owner, sq)) and \
        not board.attackers(owner, sq)


def _in_danger(board: chess.Board, sq: int, owner: chess.Color) -> bool:
    """Attacked by something cheaper than itself, or attacked and undefended.

    Not a full static exchange: deliberately the simple, checkable version,
    because a purpose that cannot be explained in one sentence to a 900 is
    not a purpose this product needs.
    """
    p = board.piece_at(sq)
    if p is None or p.color != owner:
        return False
    attackers = board.attackers(not owner, sq)
    if not attackers:
        return False
    if not board.attackers(owner, sq):
        return True
    cheapest = min(VALUE[board.piece_at(a).piece_type] for a in attackers)
    return cheapest < VALUE[p.piece_type]


def _after(board: chess.Board, san: str) -> Optional[chess.Board]:
    try:
        b = board.copy()
        b.push(b.parse_san(str(san)))
        return b
    except Exception:
        return None


def _mv(board: chess.Board, san: str) -> Optional[chess.Move]:
    try:
        return board.parse_san(str(san))
    except Exception:
        return None


def _passed(board: chess.Board, sq: int, owner: chess.Color) -> bool:
    f, r = chess.square_file(sq), chess.square_rank(sq)
    step = 1 if owner == chess.WHITE else -1
    ranks = range(r + step, 8) if owner == chess.WHITE else range(r + step, -1, -1)
    for rr in ranks:
        for ff in (f - 1, f, f + 1):
            if 0 <= ff <= 7:
                p = board.piece_at(chess.square(ff, rr))
                if p and p.piece_type == chess.PAWN and p.color != owner:
                    return False
    return True


def _open_file(board: chess.Board, f: int, us: chess.Color) -> bool:
    for r in range(8):
        p = board.piece_at(chess.square(f, r))
        if p and p.piece_type == chess.PAWN and p.color == us:
            return False
    return True


def _checks_in(board: chess.Board, line: Sequence[str],
               by: chess.Color, limit: int = 6) -> Optional[int]:
    w = board.copy()
    n = 0
    for san in list(line)[:limit]:
        mv = _mv(w, san)
        if mv is None:
            return None
        if w.turn == by and w.gives_check(mv):
            n += 1
        w.push(mv)
    return n


# ── the purposes ──────────────────────────────────────────────────────

def _wins_hanging_piece(b, best_mv, after_best, us) -> Optional[Purpose]:
    """Half one of the old `D`: after the better move an enemy man is
    attacked and undefended. Says nothing about whether it can run."""
    for sq, p in after_best.piece_map().items():
        if p.color == us or p.piece_type in (chess.PAWN, chess.KING):
            continue
        if sq not in after_best.attacks(best_mv.to_square):
            continue
        if _undefended(after_best, sq, not us):
            return Purpose(
                "wins_hanging_piece", MATERIAL,
                {"piece": NAME[p.piece_type], "square": chess.square_name(sq),
                 "value_cp": VALUE[p.piece_type]},
                f"after the move, their {NAME[p.piece_type]} on "
                f"{chess.square_name(sq)} is attacked and undefended")
    return None


def _traps_piece(b, best_mv, after_best, us) -> Optional[Purpose]:
    """Half two of the old `D`, routed through the proven check in
    game_ledger rather than re-implemented here."""
    try:
        from services.game_ledger import _piece_trapped_after
    except Exception:
        return None
    for pt in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
        try:
            if _piece_trapped_after(after_best, not us, pt):
                return Purpose(
                    "traps_piece", MATERIAL, {"piece": NAME[pt]},
                    f"their {NAME[pt]} is attacked and every square it can "
                    f"reach is attacked too")
        except Exception:
            continue
    return None


def _moves_to_safety(b, best_mv, after_best, us) -> Optional[Purpose]:
    if b.piece_at(best_mv.from_square).piece_type == chess.KING:
        return None
    if not _in_danger(b, best_mv.from_square, us):
        return None
    if _in_danger(after_best, best_mv.to_square, us):
        return None
    p = b.piece_at(best_mv.from_square)
    return Purpose(
        "moves_to_safety", SAFETY,
        {"piece": NAME[p.piece_type],
         "from": chess.square_name(best_mv.from_square),
         "to": chess.square_name(best_mv.to_square)},
        f"the {NAME[p.piece_type]} on "
        f"{chess.square_name(best_mv.from_square)} was in danger and "
        f"{chess.square_name(best_mv.to_square)} is not attacked")


def _defends_man(b, best_mv, after_best, us) -> Optional[Purpose]:
    danger = [s for s, p in b.piece_map().items()
              if p.color == us and p.piece_type != chess.KING
              and _in_danger(b, s, us) and s != best_mv.from_square]
    for s in danger:
        if after_best.piece_at(s) and s in after_best.attacks(best_mv.to_square) \
                and not _in_danger(after_best, s, us):
            p = b.piece_at(s)
            return Purpose(
                "defends_man", SAFETY,
                {"piece": NAME[p.piece_type], "square": chess.square_name(s)},
                f"your {NAME[p.piece_type]} on {chess.square_name(s)} was in "
                f"danger and the move now guards it")
    return None


def _avoids_attacked_square(b, best_mv, after_best, us,
                            played_san) -> Optional[Purpose]:
    played = _mv(b, played_san)
    after_played = _after(b, played_san)
    if played is None or after_played is None:
        return None
    if not _in_danger(after_played, played.to_square, us):
        return None
    if _in_danger(after_best, best_mv.to_square, us):
        return None
    p = b.piece_at(played.from_square)
    return Purpose(
        "avoids_attacked_square", SAFETY,
        {"piece": NAME[p.piece_type] if p else "piece",
         "played_square": chess.square_name(played.to_square),
         "safe_square": chess.square_name(best_mv.to_square)},
        f"{chess.square_name(played.to_square)} is attacked and "
        f"{chess.square_name(best_mv.to_square)} is not")


def _pawn_attacks_piece(b, best_mv, after_best, us) -> Optional[Purpose]:
    if b.piece_at(best_mv.from_square).piece_type != chess.PAWN:
        return None
    if _in_danger(after_best, best_mv.to_square, us):
        return None
    for sq in after_best.attacks(best_mv.to_square):
        t = after_best.piece_at(sq)
        if t and t.color != us and VALUE[t.piece_type] > VALUE[chess.PAWN]:
            return Purpose(
                "pawn_attacks_piece", POSITIONAL,
                {"piece": NAME[t.piece_type], "square": chess.square_name(sq),
                 "pawn_square": chess.square_name(best_mv.to_square)},
                f"the pawn now attacks their {NAME[t.piece_type]} on "
                f"{chess.square_name(sq)} and is itself safe")
    return None


def _check_worsens_king(b, best_mv, after_best, us) -> Optional[Purpose]:
    if not b.gives_check(best_mv):
        return None
    them = not us
    ks = after_best.king(them)
    if ks is None:
        return None
    outs = [m for m in after_best.legal_moves if m.from_square == ks]
    if len(outs) > 2:
        return None
    return Purpose(
        "check_worsens_king", SAFETY,
        {"king_squares_left": len(outs)},
        f"the check leaves their king {len(outs)} square(s) to move to")


def _stops_passer(b, best_mv, after_best, us) -> Optional[Purpose]:
    them = not us
    for sq, p in b.piece_map().items():
        if p.color != them or p.piece_type != chess.PAWN:
            continue
        if not _passed(b, sq, them):
            continue
        f, r = chess.square_file(sq), chess.square_rank(sq)
        step = 1 if them == chess.WHITE else -1
        ranks = range(r + step, 8) if them == chess.WHITE else range(r + step, -1, -1)
        for rr in list(ranks)[:3]:
            path = chess.square(f, rr)
            was = bool(b.attackers(us, path)) or b.piece_at(path) is not None
            now = bool(after_best.attackers(us, path)) or \
                after_best.piece_at(path) is not None
            covered = path in after_best.attacks(best_mv.to_square) or \
                path == best_mv.to_square
            if now and not was and covered:
                return Purpose(
                    "stops_passer", POSITIONAL,
                    {"pawn_square": chess.square_name(sq),
                     "blocked_square": chess.square_name(path)},
                    f"their passed pawn on {chess.square_name(sq)} now meets "
                    f"a covered square on {chess.square_name(path)}")
    return None


def _activates_rook(b, best_mv, after_best, us) -> Optional[Purpose]:
    if b.piece_at(best_mv.from_square).piece_type != chess.ROOK:
        return None
    ff, tf = chess.square_file(best_mv.from_square), \
        chess.square_file(best_mv.to_square)
    if tf != ff and _open_file(after_best, tf, us) and not _open_file(b, ff, us):
        return Purpose(
            "activates_rook", POSITIONAL,
            {"file": chess.FILE_NAMES[tf]},
            f"the rook moves to the open {chess.FILE_NAMES[tf]}-file")
    gained = [s for s in after_best.attacks(best_mv.to_square)
              if (p := after_best.piece_at(s)) and p.color != us
              and p.piece_type == chess.PAWN]
    had = [s for s in b.attacks(best_mv.from_square)
           if (p := b.piece_at(s)) and p.color != us
           and p.piece_type == chess.PAWN]
    if len(gained) > len(had):
        return Purpose(
            "activates_rook", POSITIONAL,
            {"pawns_attacked": len(gained)},
            f"the rook now attacks {len(gained)} of their pawns, up from "
            f"{len(had)}")
    return None


def _trades_off(b, best_mv, after_best, us) -> Optional[Purpose]:
    ours = b.piece_at(best_mv.from_square)
    if ours.piece_type in (chess.PAWN, chess.KING):
        return None
    for sq in after_best.attacks(best_mv.to_square):
        t = after_best.piece_at(sq)
        if t and t.color != us and t.piece_type == ours.piece_type:
            if after_best.attackers(not us, best_mv.to_square):
                return Purpose(
                    "trades_off", POSITIONAL,
                    {"piece": NAME[t.piece_type],
                     "square": chess.square_name(sq)},
                    f"it offers to trade your {NAME[ours.piece_type]} for "
                    f"theirs on {chess.square_name(sq)}")
    return None


def _denies_counterplay(b, us, played_san, best_san,
                        pv_played, pv_best) -> Optional[Purpose]:
    after_played = _after(b, played_san)
    after_best = _after(b, best_san)
    if after_played is None or after_best is None:
        return None
    theirs = not us
    cp_ = _checks_in(after_played, pv_played, theirs)
    cb = _checks_in(after_best, pv_best, theirs)
    if cp_ is None or cb is None or cp_ < 2 or cb != 0:
        return None
    return Purpose(
        "denies_counterplay", POSITIONAL,
        {"checks_allowed": cp_},
        f"their line after your move has {cp_} checks; after the better move "
        f"it has none")


def _answers_threat(b, best_mv, after_best, us, threat) -> Optional[Purpose]:
    """The residue's biggest shape: 94% of the cards nothing else explained
    carry a `threat` the engine already stores, and the better move deals
    with it.

    Proven, never assumed: the threatened move must be legal for them now and
    must NOT be available after the better move, or must no longer win what
    it won.
    """
    if not threat or not isinstance(threat, str):
        return None
    probe = b.copy()
    probe.turn = not us          # give them the move, to read their threat
    tm = _mv(probe, threat)
    if tm is None:
        return None
    victim = probe.piece_at(tm.to_square)
    after = after_best.copy()
    after.turn = not us
    still = _mv(after, threat)
    if still is not None:
        # still legal -- is it still worth anything?
        now = after.piece_at(still.to_square)
        if victim is None or (now is not None
                              and now.color == us
                              and VALUE[now.piece_type] >= VALUE[victim.piece_type]
                              and not after.attackers(us, still.to_square)):
            return None
    return Purpose(
        "answers_threat", SAFETY,
        {"threat_san": threat},
        f"they were threatening {threat}; the better move takes it away")


def _mate_transition(mate_info) -> Optional[Purpose]:
    """The residue's other shape, 23% of it, and the highest-stakes cards in
    the corpus at 8,000-10,000cp. Both directions live in `mate_info`."""
    if not isinstance(mate_info, dict):
        return None
    before, after = mate_info.get("before"), mate_info.get("after")
    if before is not None and after is None:
        return Purpose(
            "missed_forced_mate", MATE, {"mate_in": abs(int(before))},
            f"a forced mate in {abs(int(before))} was available and the move "
            f"gave it up")
    if before is None and after is not None:
        return Purpose(
            "allowed_forced_mate", MATE, {"mate_in": abs(int(after))},
            f"the move allows a forced mate in {abs(int(after))}")
    return None


def purposes_for(
    fen_before: str,
    played_san: str,
    best_san: Optional[str],
    pv_played: Optional[Sequence[str]] = None,
    pv_best: Optional[Sequence[str]] = None,
    threat: Optional[str] = None,
    mate_info: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Everything true about what the better move achieves, ranked.

    A LIST, never one winner: on 23.5% of cards more than one purpose holds,
    and the old if-chain discarded the rest. Ranked by tier so a consumer --
    the caption layer, or an LLM holding the player's history -- chooses from
    facts instead of from the order the code happened to check them in.

    Returns [] only when the position will not parse. A move with no purpose
    is not silence: the floor facts live beside this and are always emitted.
    """
    out: List[Purpose] = []
    try:
        b = chess.Board(fen_before)
    except Exception:
        return []

    m = _mate_transition(mate_info)
    if m:
        out.append(m)

    best_mv = _mv(b, best_san) if best_san else None
    if best_mv is not None and b.piece_at(best_mv.from_square) is not None:
        after_best = b.copy()
        after_best.push(best_mv)
        us = b.turn
        for fn in (_wins_hanging_piece, _traps_piece, _moves_to_safety,
                   _defends_man, _pawn_attacks_piece, _check_worsens_king,
                   _stops_passer, _activates_rook, _trades_off):
            try:
                p = fn(b, best_mv, after_best, us)
            except Exception:
                p = None
            if p:
                out.append(p)
        try:
            p = _avoids_attacked_square(b, best_mv, after_best, us, played_san)
            if p:
                out.append(p)
        except Exception:
            pass
        try:
            p = _answers_threat(b, best_mv, after_best, us, threat)
            if p:
                out.append(p)
        except Exception:
            pass
        try:
            p = _denies_counterplay(b, us, played_san, best_san,
                                    list(pv_played or []), list(pv_best or []))
            if p:
                out.append(p)
        except Exception:
            pass

    out.sort(key=lambda p: -p.tier)
    return [p.as_dict() for p in out]
