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


# The transferable lesson for each kind, authored here, once.
#
# Mohit, 2026-10-22: "LLM should never infer the chess, it should only
# generate english". The prompt used to say "say what to learn, not just what
# happened", which asked the model to DERIVE a lesson from the facts -- chess
# inference, and exactly what the rule forbids. The lesson is a fact like any
# other, so it comes from here and the model only phrases it.
#
# Short, transferable, and in the words a 600-1500 player uses. These are the
# same shape as R12's authored teaching_principles, which is the one part of
# that file worth keeping.
LESSON = {
    "wins_hanging_piece":
        "before you move, look for an enemy piece that nothing defends",
    "traps_piece":
        "a piece with no safe square is as good as won; take its squares away",
    "attacks_loose_pawn":
        "loose pawns are free targets; put a piece on them before they are defended",
    "moves_to_safety":
        "when a piece is attacked, moving it to a safe square is usually the move",
    "defends_man":
        "a piece in danger can be saved by guarding it as well as by moving it",
    "avoids_attacked_square":
        "check whether a square is attacked before you move onto it",
    "pawn_attacks_piece":
        "a pawn that pokes a piece wins you time, because it must answer",
    "check_worsens_king":
        "a check that takes squares away from the king is worth more than a loud one",
    "stops_passer":
        "a passed pawn must be stopped early; blockade the square in front of it",
    "activates_rook":
        "rooks want open files and enemy pawns to attack",
    "trades_off":
        "trading off their most active piece is a way to take the sting out",
    "denies_counterplay":
        "when you are better, take away their checks before you push your own plan",
    "develops_with_tempo":
        "develop a piece and make a threat with the same move; you gain the "
        "time instead of spending it",
    "develops_a_piece":
        "early on, every move should bring a new piece into the game",
    "played_develops_nothing":
        "when you are behind in development, a quiet pawn move is a move you "
        "cannot afford",
    "wins_the_exchange":
        "attack a piece with a cheaper one; the trade wins material even if "
        "they can take back",
    "played_allows_fork":
        "before you move, check what one enemy move could attack twice",
    "played_leaves_king_exposed":
        "get the king out of the centre before you go material hunting",
    "promotion_race":
        "in an endgame a pawn near the last rank is the whole game; count "
        "the race before anything else",
    "king_activity":
        "in an endgame the king is a fighting piece; walk it toward the pawns",
    "advances_passer":
        "a passed pawn must be pushed; every square it gains costs them time",
    "rook_behind_passer":
        "put the rook behind a passed pawn, yours or theirs",
    "answers_threat":
        "deal with their threat before you start your own",
    "missed_forced_mate":
        "when you have a forced mate, check every check before anything else",
    "allowed_forced_mate":
        "before you move, ask what checks they get after it",
}


@dataclass(frozen=True)
class Purpose:
    """One true thing about the better move, with what proves it."""
    kind: str
    tier: int
    facts: Dict[str, Any] = field(default_factory=dict)
    proof: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "tier": self.tier,
                "facts": dict(self.facts), "proof": self.proof,
                "lesson": LESSON.get(self.kind, "")}


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



# Where the minor pieces start. A piece off its home square is developed --
# the crude definition, and the one a 900 would recognise.
_HOME = {
    chess.WHITE: {chess.KNIGHT: (chess.B1, chess.G1),
                  chess.BISHOP: (chess.C1, chess.F1)},
    chess.BLACK: {chess.KNIGHT: (chess.B8, chess.G8),
                  chess.BISHOP: (chess.C8, chess.F8)},
}


def _developed_minors(board: chess.Board, col: chess.Color) -> int:
    n = 0
    for pt in (chess.KNIGHT, chess.BISHOP):
        for sq in board.pieces(pt, col):
            if sq not in _HOME[col][pt]:
                n += 1
    return n


def _is_developing(board: chess.Board, mv: chess.Move) -> bool:
    p = board.piece_at(mv.from_square)
    if p is None or p.piece_type not in (chess.KNIGHT, chess.BISHOP):
        return False
    return (mv.from_square in _HOME[p.color][p.piece_type]
            and mv.to_square not in _HOME[p.color][p.piece_type])


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
                f"after the move, the waiting side's {NAME[p.piece_type]} on "
                f"{chess.square_name(sq)} is attacked and undefended")
    return None


def _attacks_loose_pawn(b, best_mv, after_best, us) -> Optional[Purpose]:
    """The better move hits a pawn nothing defends.

    Separate from _wins_hanging_piece, which skips pawns on purpose: winning
    a pawn is not winning a piece and the two deserve different sentences.
    But excluding pawns entirely made whole cards unexplainable.

    Mohit, 2026-10-22, on an opponent card reading only "Opponent's c3 is an
    inaccuracy. Play c6.": "engine didn't tell why this is an inaccuracy  # allow-noncentral-caption
    here?" The answer was that Nf3 attacks the e5 pawn, which black has
    nothing defending -- the board says so plainly -- and no purpose in this
    file could see it, because the only one that looks for an undefended
    enemy man steps over pawns.
    """
    for sq in after_best.attacks(best_mv.to_square):
        t = after_best.piece_at(sq)
        if not t or t.color == us or t.piece_type != chess.PAWN:
            continue
        if after_best.attackers(not us, sq):
            continue
        mover = b.piece_at(best_mv.from_square)
        return Purpose(
            "attacks_loose_pawn", POSITIONAL,
            {"square": chess.square_name(sq),
             "attacker": NAME[mover.piece_type] if mover else "piece"},
            f"the move attacks the waiting side's pawn on "
            f"{chess.square_name(sq)}, which nothing defends")
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
                    f"the waiting side's {NAME[pt]} is attacked and every "
                    f"square it can reach is attacked too")
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
                f"the mover's {NAME[p.piece_type]} on {chess.square_name(s)} was "
                f"in danger and the move now guards it")
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
                f"the pawn now attacks the waiting side's {NAME[t.piece_type]} "
                f"on {chess.square_name(sq)} and is itself safe")
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
        f"the check leaves the waiting king {len(outs)} square(s) to "
        f"move to")


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
                    f"the waiting side's passed pawn on {chess.square_name(sq)} now "
                    f"meets a covered square on {chess.square_name(path)}")
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
            f"the rook now attacks {len(gained)} of the waiting side's "
            f"pawns, up from {len(had)}")
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
                    f"it offers to trade the mover's {NAME[ours.piece_type]} for "
                    f"the waiting side's on {chess.square_name(sq)}")
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
        f"the waiting side gets {cp_} checks after the played move and "
        f"none after the better move")


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
        f"the waiting side was threatening {threat}; the better move "
        f"takes it away")


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



def _develops_with_tempo(b, best_mv, after_best, us) -> Optional[Purpose]:
    """The better move brings a piece out AND makes them answer.

    The one Mohit found by hand on move 4 of a real game, where the engine
    could only talk about the alternative. Nf3 develops the last kingside
    minor, hits an undefended e5 pawn so Black must respond, and clears the
    way to castle -- three things in one move -- while the played c3
    developed nothing.

    It is a COMBINATION, which is the whole reason this file returns a ranked
    list instead of one winner: neither half alone is the lesson.
    """
    if not _is_developing(b, best_mv):
        return None
    hits = []
    for sq in after_best.attacks(best_mv.to_square):
        t = after_best.piece_at(sq)
        if t and t.color != us and not after_best.attackers(not us, sq):
            hits.append((NAME[t.piece_type], chess.square_name(sq)))
    if not hits:
        return None
    piece, square = hits[0]
    mover = b.piece_at(best_mv.from_square)
    return Purpose(
        "develops_with_tempo", SAFETY,
        {"piece": NAME[mover.piece_type],
         "to": chess.square_name(best_mv.to_square),
         "hits": piece, "hits_square": square},
        f"the move brings the {NAME[mover.piece_type]} out AND attacks the "
        f"waiting side's {piece} on {square}, which nothing defends, so they "
        f"must answer")


def _develops_a_piece(b, best_mv, after_best, us) -> Optional[Purpose]:
    """Plain development, when it does not also create a threat."""
    if not _is_developing(b, best_mv):
        return None
    mover = b.piece_at(best_mv.from_square)
    return Purpose(
        "develops_a_piece", POSITIONAL,
        {"piece": NAME[mover.piece_type],
         "to": chess.square_name(best_mv.to_square)},
        f"the move brings the {NAME[mover.piece_type]} off its starting "
        f"square to {chess.square_name(best_mv.to_square)}")


def _played_develops_nothing(b, best_mv, after_best, us,
                             played_san) -> Optional[Purpose]:
    """Behind in development, king still home, and the move played did not
    help either. This one describes the PLAYED move, which the rest of the
    vocabulary does not -- and which is what a reader is actually asking
    about."""
    played = _mv(b, played_san)
    if played is None or _is_developing(b, played):
        return None
    ours, theirs = _developed_minors(b, us), _developed_minors(b, not us)
    if ours >= theirs:
        return None
    home = chess.E1 if us == chess.WHITE else chess.E8
    if b.king(us) != home:
        return None
    return Purpose(
        "played_develops_nothing", POSITIONAL,
        {"ours": ours, "theirs": theirs},
        f"the mover has {ours} minor piece(s) out against {theirs}, the king "
        f"is still on its starting square, and the move played brought "
        f"nothing new out")



def _wins_the_exchange(b, best_mv, after_best, us) -> Optional[Purpose]:
    """The better move attacks a piece with something CHEAPER.

    _wins_hanging_piece needs the target undefended, so it misses the plain
    "knight attacks rook" idea -- the most common way material changes hands
    below 1500. Found in the uncovered set on Re8+/Ne3, where Ne3 hits a rook
    on g2 that its neighbour on f2 defends: defended, and still losing a rook
    for a knight.
    """
    attacker = b.piece_at(best_mv.from_square)
    if attacker is None or attacker.piece_type == chess.KING:
        return None
    for sq in after_best.attacks(best_mv.to_square):
        t = after_best.piece_at(sq)
        if not t or t.color == us:
            continue
        if VALUE[t.piece_type] <= VALUE[attacker.piece_type]:
            continue
        # and the attacker is not simply lost for free where it stands
        if _in_danger(after_best, best_mv.to_square, us):
            continue
        return Purpose(
            "wins_the_exchange", MATERIAL,
            {"their_piece": NAME[t.piece_type],
             "square": chess.square_name(sq),
             "our_piece": NAME[attacker.piece_type]},
            f"the {NAME[attacker.piece_type]} attacks the waiting side's "
            f"{NAME[t.piece_type]} on {chess.square_name(sq)}, which is worth "
            f"more, so the trade wins material even if it is defended")
    return None


def _played_allows_fork(b, best_mv, after_best, us,
                        played_san, pv_played) -> Optional[Purpose]:
    """Their reply to the played move hits two of ours at once.

    The uncovered set is full of this and nothing described it: Nxc2 grabs a
    pawn and runs into Qc3+, which takes the king and the knight. Proven by
    pushing their actual reply and counting what it attacks -- never inferred
    from the shape.
    """
    after_played = _after(b, played_san)
    if after_played is None or not pv_played:
        return None
    reply = _mv(after_played, str(pv_played[0]))
    if reply is None:
        return None
    nb = after_played.copy()
    nb.push(reply)
    hit = []
    for sq in nb.attacks(reply.to_square):
        t = nb.piece_at(sq)
        if t and t.color == us and (t.piece_type == chess.KING
                                    or not nb.attackers(us, sq)):
            hit.append((NAME[t.piece_type], chess.square_name(sq)))
    if len(hit) < 2:
        return None
    a, c = hit[0], hit[1]
    return Purpose(
        "played_allows_fork", MATERIAL,
        {"reply": str(pv_played[0]),
         "targets": [f"{p}{q}" for p, q in hit[:3]]},
        f"after the played move they answer {pv_played[0]}, which attacks "
        f"the mover's {a[0]} on {a[1]} and {c[0]} on {c[1]} at once")


def _played_leaves_king_exposed(b, best_mv, after_best, us,
                                played_san, pv_played) -> Optional[Purpose]:
    """The king is still home, and the played move lets the checks start.

    Found on Qxc5/O-O: a pawn grabbed with the king on e1 while their queen
    was active, and Qe4+ followed. The better move castled first.
    """
    home = chess.E1 if us == chess.WHITE else chess.E8
    if b.king(us) != home:
        return None
    after_played = _after(b, played_san)
    if after_played is None or not pv_played:
        return None
    checks = _checks_in(after_played, pv_played, not us)
    if not checks:
        return None
    best_is_castle = str(best_mv and b.san(best_mv) or "").startswith("O-O")
    return Purpose(
        "played_leaves_king_exposed", SAFETY,
        {"checks_allowed": checks, "better_castles": best_is_castle},
        f"the mover's king is still on its starting square and the played "
        f"move lets {checks} check(s) begin")



def _promotion_race(b, best_mv, after_best, us, played_san) -> Optional[Purpose]:
    """A pawn is one or two squares from queening. In an endgame nothing on
    the board outranks that.

    Found by reasoning over endgame cards, 2026-10-22. On one of them Black's
    king stood on d5 with a WHITE PAWN ON c7 -- one square from queening with
    check -- and the only purpose that fired was `attacks_loose_pawn`, about
    a b4 pawn on the far side of the board. The lesson was the promotion and
    the engine talked about something else.

    That is what a borrowed middlegame purpose does in an endgame, and it is
    why this is MATERIAL tier: a queen appearing beats a pawn being attacked.
    """
    if len(b.piece_map()) > 12:
        return None
    them = not us
    out = []
    for sq, p in b.piece_map().items():
        if p.piece_type != chess.PAWN:
            continue
        rank = chess.square_rank(sq)
        to_go = (7 - rank) if p.color == chess.WHITE else rank
        if to_go > 2:
            continue
        if not _passed(b, sq, p.color):
            continue
        out.append((p.color, chess.square_name(sq), to_go))
    if not out:
        return None
    # theirs first: a pawn about to queen AGAINST us is the more urgent fact
    out.sort(key=lambda r: (r[0] == us, r[2]))
    owner, square, to_go = out[0]
    whose = "the mover's" if owner == us else "the waiting side's"
    return Purpose(
        "promotion_race", MATERIAL,
        {"square": square, "squares_to_go": to_go,
         "owner": "mover" if owner == us else "waiting"},
        f"{whose} passed pawn on {square} is {to_go} square(s) from queening")



def _pawn_squares(board) -> list:
    return [sq for sq, p in board.piece_map().items()
            if p.piece_type == chess.PAWN]


def _king_activity(b, best_mv, after_best, us, played_san) -> Optional[Purpose]:
    """The king walks toward the fight, and the played move did not.

    The first thing anyone teaches about endgames below 1500, and the engine
    had no concept of it: three of the sampled endgame cards turned on where
    the king went and nothing fired.

    "Toward the fight" is measured, not guessed: the distance from the king
    to the nearest pawn on the board. It drops after the better move and does
    not after the played one.
    """
    if len(b.piece_map()) > 12:
        return None
    if b.piece_at(best_mv.from_square).piece_type != chess.KING:
        return None
    pawns = _pawn_squares(b)
    if not pawns:
        return None

    def nearest(frm):
        return min(chess.square_distance(frm, s) for s in pawns)

    before = nearest(best_mv.from_square)
    after = nearest(best_mv.to_square)
    if after >= before:
        return None
    played = _mv(b, played_san)
    if played is not None and played.from_square == best_mv.from_square:
        if nearest(played.to_square) <= after:
            return None          # the played move was just as active
    return Purpose(
        "king_activity", POSITIONAL,
        {"to": chess.square_name(best_mv.to_square),
         "closer_by": before - after},
        f"the king steps toward the pawns, {before - after} square(s) "
        f"closer than where it stood")


def _advances_passer(b, best_mv, after_best, us,
                     played_san) -> Optional[Purpose]:
    """Run your own passed pawn. `stops_passer` covers theirs; nothing
    covered ours, and in the sampled endgames the better move was often
    simply the push."""
    mover = b.piece_at(best_mv.from_square)
    if mover is None or mover.piece_type != chess.PAWN:
        return None
    if not _passed(b, best_mv.from_square, us):
        return None
    rank = chess.square_rank(best_mv.to_square)
    to_go = (7 - rank) if us == chess.WHITE else rank
    return Purpose(
        "advances_passer", POSITIONAL,
        {"from": chess.square_name(best_mv.from_square),
         "to": chess.square_name(best_mv.to_square),
         "squares_to_go": to_go},
        f"it pushes the mover's passed pawn to "
        f"{chess.square_name(best_mv.to_square)}, {to_go} square(s) from "
        f"queening")


def _rook_behind_passer(b, best_mv, after_best, us,
                        played_san) -> Optional[Purpose]:
    """A rook belongs behind a passed pawn -- either one.

    `activates_rook` only counts open files and attacked pawns, so a rook
    repositioning for exactly this reason was invisible.
    """
    mover = b.piece_at(best_mv.from_square)
    if mover is None or mover.piece_type != chess.ROOK:
        return None
    tf, tr = chess.square_file(best_mv.to_square),         chess.square_rank(best_mv.to_square)
    for sq, p in b.piece_map().items():
        if p.piece_type != chess.PAWN or not _passed(b, sq, p.color):
            continue
        if chess.square_file(sq) != tf:
            continue
        pr = chess.square_rank(sq)
        behind = (tr < pr) if p.color == chess.WHITE else (tr > pr)
        if not behind:
            continue
        whose = "the mover's" if p.color == us else "the waiting side's"
        return Purpose(
            "rook_behind_passer", POSITIONAL,
            {"rook_to": chess.square_name(best_mv.to_square),
             "pawn": chess.square_name(sq),
             "owner": "mover" if p.color == us else "waiting"},
            f"the rook goes behind {whose} passed pawn on "
            f"{chess.square_name(sq)}")
    return None


def purposes_for(
    fen_before: str,
    played_san: str,
    best_san: Optional[str],
    pv_played: Optional[Sequence[str]] = None,
    pv_best: Optional[Sequence[str]] = None,
    threat: Optional[str] = None,
    mate_info: Optional[Dict[str, Any]] = None,
    eval_line: Optional[Sequence[str]] = None,
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

    # The punishment line is only computed for moves the analysis classified
    # as inaccuracy-or-worse, so small mistakes often have none. Measured
    # over 6,371 faulted cards:
    #
    #     40-99cp    72.3% have a line, 59.1% a threat
    #     100-299    94.0%              73.9%
    #     300+       97.5%              82.0%
    #
    # That starved band is the weakest cell in the whole engine and most of
    # what a review page shows -- not because the vocabulary is thin but
    # because the INPUT is missing. `eval_line_played` now gives every move a
    # line from the evaluation search that already ran, so use it when the
    # punishment line is absent. Without this wire the floor work reaches
    # nothing.
    if not pv_played and eval_line:
        pv_played = list(eval_line)

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
                   _stops_passer, _activates_rook, _trades_off,
                   _attacks_loose_pawn, _develops_with_tempo,
                   _develops_a_piece, _wins_the_exchange):
            try:
                p = fn(b, best_mv, after_best, us)
            except Exception:
                p = None
            if p:
                out.append(p)
        for fn2 in (_avoids_attacked_square, _played_develops_nothing,
                    _promotion_race, _king_activity, _advances_passer,
                    _rook_behind_passer):
            try:
                p = fn2(b, best_mv, after_best, us, played_san)
                if p:
                    out.append(p)
            except Exception:
                pass
        # What the PLAYED move allows. The vocabulary was one-sided: 13 of 14
        # purposes described what the BETTER move achieves, while the reader
        # is asking why THEIRS was bad.
        for fn3 in (_played_allows_fork, _played_leaves_king_exposed):
            try:
                p = fn3(b, best_mv, after_best, us, played_san,
                        list(pv_played or []))
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

    # Phase-aware ranking. Tier alone is not enough: in an endgame card
    # sampled on 2026-10-22, Black's king stood beside a white pawn on c7 --
    # one square from queening -- and the top purpose was `attacks_loose_pawn`
    # about a b4 pawn on the far side of the board. A middlegame purpose had
    # outranked the whole game.
    #
    # So in an endgame the endgame ideas come first within their tier. This
    # does not silence anything -- the other purposes stay in the list, they
    # just stop leading.
    endgame = len(b.piece_map()) <= 12
    ENDGAME_FIRST = ("promotion_race", "advances_passer", "stops_passer",
                     "king_activity", "rook_behind_passer")

    def rank(p: Purpose):
        phase_bonus = 1 if (endgame and p.kind in ENDGAME_FIRST) else 0
        return (-p.tier, -phase_bonus)

    out.sort(key=rank)
    return [p.as_dict() for p in out]
