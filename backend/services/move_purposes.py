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
    "develops_against_a_target":
        "bring a new piece out to a square where it attacks something; "
        "then it is doing a job straight away",
    "prepares_the_pawn_storm":
        "when their pawn moves up on the side, push your edge pawn at it; "
        "now they have to deal with it",
    "bishop_to_the_square_the_pawn_left":
        "move the pawn in front of a bishop; then put the bishop on the "
        "square that pawn just left",
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
    "castles_the_king_away":
        "castle early; a king left in the middle is what they play against",
    "played_check_achieved_nothing":
        "a check they can simply answer hands them a move; check with a "
        "purpose or not at all",
    "played_check_loses_the_checker":
        "before you check, look at what can take the checking piece",
    "offered_and_not_taken":
        "a man you can take is not always a man you should take; look for "
        "the stronger move first",
    "played_lost_the_colour_squares":
        "one bishop is the only piece that guards its colour; trade it off "
        "and those squares belong to them for the rest of the game",
    "prepares_the_pawn_chase":
        "when a rook pawn comes at you, look at what the next pawn push "
        "will hit; stop it with your own rook pawn or move the piece first",
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

# Where a pawn is worth pressing. Pressure on one of these is a real idea
# -- Bg7 pointing at d4 is the whole reason g6 was played -- while a bishop
# glancing at a defended a7 or h6 pawn is a true fact about nothing.
_CENTRE_SQUARES = frozenset((
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
))


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


def threat_check(fen_before: str, played_san: str,
                 threat_san: Optional[str]) -> Optional[Dict[str, Any]]:
    """What the waiting side's reply actually threatens, or None.

    `get_threat` in stockfish_service returns the opponent's best reply and
    nothing more -- its own docstring says so -- and every position has a
    best reply. build_facts then filed that string under
    `they_were_threatening`, so the model was told a quiet developing move
    was a threat and wrote correct English for it:

        "your d6 didn't stop their knight from moving to f3"

    Nf3 is not a threat and d6 cannot stop it. Measured over 8,200 faulted
    cards that carry a stored threat: 79.6% of those replies threaten
    NOTHING. The engine has to earn that word before the caption may use
    it.

    Earned means mate, or a capture of a man that is undefended or taken by
    something cheaper than itself -- the same simple test `_in_danger`
    uses, so the two halves of this file agree.

    Judged on the board the engine computed it on: fen_before plus the
    played move. Reading it on fen_before with the turn flipped is a
    different position, and on 12.9% of these cards the move is not even
    legal there.
    """
    if not threat_san or not isinstance(threat_san, str):
        return None
    try:
        board = chess.Board(fen_before)
        board.push(board.parse_san(str(played_san)))
        mv = board.parse_san(threat_san)
    except Exception:
        return None
    after = board.copy()
    after.push(mv)
    if after.is_checkmate():
        return {"move": threat_san, "it_would_win": "mate"}
    victim = board.piece_at(mv.to_square)
    if victim is None:
        return None
    taker = board.piece_at(mv.from_square)
    name = f"the {chess.piece_name(victim.piece_type)} on " \
           f"{chess.square_name(mv.to_square)}"
    if not board.attackers(victim.color, mv.to_square):
        return {"move": threat_san, "it_would_win": name,
                "because": "nothing is defending it"}
    if taker is not None and \
            VALUE[taker.piece_type] < VALUE[victim.piece_type]:
        return {"move": threat_san, "it_would_win": name,
                "because": f"it is taken by the cheaper "
                           f"{chess.piece_name(taker.piece_type)}"}
    return None


def _answers_threat(b, best_mv, after_best, us, threat,
                    played_san=None) -> Optional[Purpose]:
    """The residue's biggest shape: 94% of the cards nothing else explained
    carry a `threat` the engine already stores, and the better move deals
    with it.

    Proven in two steps, neither assumed. The threat must WIN something
    after the played move, and it must then be gone after the better one.

    The first step used to be missing and the board was wrong. This probed
    `b` -- fen_before -- with the turn flipped, while the stored threat is
    the engine's reply on the board AFTER the played move. Measured over
    8,200 cards: the two boards disagree on 18.5%, the flipped one calls
    1,060 threats illegal that are perfectly legal on the real board, and
    it confirms 9.0% where the truth is 20.4%. So it missed half the real
    threats and judged the rest in a position that never occurred.

    And nothing required the threat to threaten anything, so a quiet
    developing move counted whenever the better move happened to deny its
    square.
    """
    if not threat or not isinstance(threat, str) or not played_san:
        return None
    real = threat_check(b.fen(), str(played_san), threat)
    if real is None:
        return None
    wins = real.get("it_would_win")
    # Gone after the better move: illegal there, or no longer worth taking.
    still = _mv(after_best, threat)
    if still is not None:
        if wins == "mate":
            probe = after_best.copy()
            probe.push(still)
            if probe.is_checkmate():
                return None
        else:
            now = after_best.piece_at(still.to_square)
            taker = after_best.piece_at(still.from_square)
            defended = bool(after_best.attackers(us, still.to_square))
            cheaper = (now is not None and taker is not None
                       and VALUE[taker.piece_type] < VALUE[now.piece_type])
            if now is not None and now.color == us \
                    and (not defended or cheaper):
                return None          # still wins the same man
    return Purpose(
        "answers_threat", SAFETY,
        {"threat_san": threat, "threat_wins": wins},
        f"the waiting side was threatening {threat}, winning {wins}; "
        f"the better move takes it away")


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


def _bishop_to_the_square_the_pawn_left(
        b, best_mv, after_best, us) -> Optional[Purpose]:
    """The pawn stepped aside to let this bishop out, and it has not come.

    Mohit, on the lessons the two facts above carried: "lessons are
    pathetic. generally when you play g3, idea is to play bg7, right?"

    Right -- as White g3 is played to get the bishop to g2, as Black g6 to
    get it to g7 -- and it exposes that both earlier facts were secondary.
    On his card (1.d4 g6 2.e4 e6) `Bg7` "bears on their pawn on d4" is a
    true CONSEQUENCE of the move. The IDEA is that g6 was played in order
    to put the bishop on g7, and e6 postponed the plan g6 had committed to.
    Nothing in the framework knew that idea existed: "fianchetto" appears
    only in jargon BAN lists (llm_caption.py:100, caption_principles.py:23),
    never in a detector.

    The geometry hands over the lesson without the banned word: in all four
    cases the bishop's destination is exactly the square its own pawn
    vacated. g6 -> Bg7, b6 -> Bb7, g3 -> Bg2, b3 -> Bb2.

    Registered BEFORE the two facts above so it leads the ranked list --
    `rank` is (-tier, -phase_bonus) and the sort is stable, so within a
    tier the order is registration order and no ranking basis moves.
    """
    mover = b.piece_at(best_mv.from_square)
    if mover is None or mover.piece_type != chess.BISHOP:
        return None
    if mover.color != us:
        return None

    home = _HOME[us][chess.BISHOP]
    if best_mv.from_square not in home:
        return None

    dest = best_mv.to_square
    spots = ((chess.G2, chess.B2) if us == chess.WHITE
             else (chess.G7, chess.B7))
    if dest not in spots:
        return None

    # Its own pawn must have stepped off that square -- that step is what
    # opened the diagonal, and it is the half of the plan already played.
    # If the pawn is still home the bishop has nowhere to go anyway, and
    # if the pawn is gone entirely this is not the same idea.
    f = chess.square_file(dest)
    our_pawn = None
    for sq in b.pieces(chess.PAWN, us):
        if chess.square_file(sq) == f:
            our_pawn = sq
            break
    if our_pawn is None or our_pawn == dest:
        return None
    steps = (chess.square_rank(our_pawn) - chess.square_rank(dest)
             if us == chess.WHITE
             else chess.square_rank(dest) - chess.square_rank(our_pawn))
    if steps <= 0:
        return None
    # ...and it must be a STEP, not a march. The first version asked only
    # whether the pawn was ahead of the square, so a black pawn on g4 came
    # back as "the pawn has already stepped to g4, which is what opened g7"
    # -- a pawn that left three moves ago and is doing something else
    # entirely. That case turned up while measuring a different idea.
    #
    # The cut is from the distribution, over the 91 cards where the
    # bishop's square is free and its own pawn is past it:
    #
    #     1 step   47  51.6%     <- g6, b6, g3, b3: the plan itself
    #     2 steps  20  22.0%     <- b5 before Bb7 is the same idea
    #     3 steps  24  26.4%     <- a marched pawn, not a preparation
    #
    # Three of the nine cards this fact fired on were in that last group.
    # They fall back to `develops_against_a_target`, which is true of them.
    if steps > 2:
        return None

    return Purpose(
        "bishop_to_the_square_the_pawn_left", POSITIONAL,
        {"piece": "bishop",
         "to": chess.square_name(dest),
         "pawn_on": chess.square_name(our_pawn),
         "bishop_still_on": chess.square_name(best_mv.from_square)},
        f"the pawn has already stepped to {chess.square_name(our_pawn)}, "
        f"which is what opened {chess.square_name(dest)} for the bishop, "
        f"and the bishop is still at home on "
        f"{chess.square_name(best_mv.from_square)}")


def _prepares_the_pawn_storm(b, best_mv, after_best, us) -> Optional[Purpose]:
    """The rook pawn advances so its OWN next push hits their pawn chain.

    The other half of Mohit's card. On 1.d4 g6 2.e4 e6 the engine's move
    for White is h4 (+126 against +123), and the framework had nothing at
    all to say about it, so the card read "Play h4" bare -- a command with
    no reason, which is the thing he has objected to since the Bxe2 card.

    Sibling of `_prepares_the_pawn_chase`, and deliberately a separate
    function: the chase pushes the NEIGHBOURING pawn at a bishop (a4 then
    b4 against c5), while the storm pushes the same rook pawn one square
    further into their pawn (h4 then h5 against g6). Same family, different
    geometry, so sharing the table would need a mode flag and read worse.

    Rare and built anyway, on Mohit's own criterion for the chase: "it's a
    simple pattern and a great teaching, general rule... i can't really
    author everywhere." Measured over 3,308 fault cards, the better move
    starts this storm on 21, and 13 of those have no fact today -- 0.4%.
    An earlier count said 26 because the gate allowed any rook-pawn push
    against any b- or g-file pawn, which matched "h3 against their pawn on
    b6": opposite wings, unrelated.

    What is claimed is only the geometry: the push comes next and it
    attacks that pawn. Not that the h-file opens, not that their king comes
    under fire -- nobody has castled on move three, and neither is provable
    from the board here.
    """
    p = b.piece_at(best_mv.from_square)
    if p is None or p.piece_type != chess.PAWN or p.color != us:
        return None
    file_idx = chess.square_file(best_mv.to_square)
    if file_idx not in (0, 7):
        return None

    after = b.copy()
    after.push(best_mv)
    after.turn = us              # our move again, to read the plan

    push = next((m for m in after.legal_moves
                 if m.from_square == best_mv.to_square), None)
    if push is None:
        return None

    w = after.copy()
    push_san = after.san(push)
    w.push(push)

    neighbour = 1 if file_idx == 0 else 6
    target = None
    for sq in w.attacks(push.to_square):
        t = w.piece_at(sq)
        if (t is not None and t.color != us and t.piece_type == chess.PAWN
                and chess.square_file(sq) == neighbour):
            target = sq
            break
    if target is None:
        return None

    where = chess.square_name(target)
    return Purpose(
        "prepares_the_pawn_storm", POSITIONAL,
        {"next_push": push_san, "pawn_on": where,
         "rook_pawn_to": chess.square_name(best_mv.to_square)},
        f"the move puts the rook pawn on "
        f"{chess.square_name(best_mv.to_square)} so that {push_san} comes "
        f"next, attacking the waiting side's pawn on {where}")


def _develops_against_a_target(b, best_mv, after_best, us) -> Optional[Purpose]:
    """Development that already presses something worth pressing.

    Mohit opened a card on 1.d4 g6 2.e4 e6 that read "They missed Bg7 -- it
    brings a new piece into the game." Every claim on it was engine-true
    (e6 costs 54cp, Bg7 is the engine's move, h4 is White's), and the model
    had exactly ONE fact to work from: `develops_a_piece`, whose proof says
    "off its starting square" and whose lesson says "early on, every move
    should bring a new piece into the game". It phrased that faithfully.
    The engine under-supplied; the prompt was never the problem.

    What the board actually said is that Bg7 points down the long diagonal
    at d4 -- White's centre pawn, and the whole reason g6 was played. So the
    fact names the target.

    `develops_with_tempo` (SAFETY) already owns the case where the target is
    UNDEFENDED, so this requires a defended one: pressure, not a win, and
    the two never describe the same man.

    Narrow on purpose, because a true fact can still be worthless. Measured
    over the 107 cards where `develops_a_piece` was the only fact, 47 (44%)
    had some target -- but several were a bishop glancing at a defended a7
    or h6 pawn, which teaches nothing. So the target must be a CENTRE pawn
    or an actual piece. Nf3 bearing on e5, Nf6 on e4, Be6 on a knight on d5
    are the shape worth a sentence.
    """
    if not _is_developing(b, best_mv):
        return None
    mover = b.piece_at(best_mv.from_square)
    if mover is None:
        return None

    worth = []
    for sq in after_best.attacks(best_mv.to_square):
        t = after_best.piece_at(sq)
        if t is None or t.color == us or t.piece_type == chess.KING:
            continue
        if not after_best.attackers(not us, sq):
            continue          # undefended -> develops_with_tempo owns it
        is_centre_pawn = (t.piece_type == chess.PAWN
                          and sq in _CENTRE_SQUARES)
        if not is_centre_pawn and t.piece_type == chess.PAWN:
            continue          # a flank pawn under a long diagonal is noise
        worth.append((not is_centre_pawn, -t.piece_type,
                      chess.square_name(sq), t))
    if not worth:
        return None

    # Deterministic: the centre pawn first, then the most valuable man,
    # then the square's own name. Never an arbitrary first hit.
    worth.sort()
    _, _, square, target = worth[0]
    return Purpose(
        "develops_against_a_target", POSITIONAL,
        {"piece": NAME[mover.piece_type],
         "to": chess.square_name(best_mv.to_square),
         "hits": NAME[target.piece_type],
         "hits_square": square},
        f"the move brings the {NAME[mover.piece_type]} out and it bears on "
        f"their {NAME[target.piece_type]} on {square}, which they defend")


def _develops_a_piece(b, best_mv, after_best, us) -> Optional[Purpose]:
    """Plain development, when it does not also create a threat.

    Kept for the 56% of developing moves that genuinely point at nothing.
    When the piece does press something, `_develops_against_a_target` says
    so instead -- and that one is listed first, so the ranked list leads
    with the target rather than with "off its starting square".
    """
    if not _is_developing(b, best_mv):
        return None
    mover = b.piece_at(best_mv.from_square)
    return Purpose(
        "develops_a_piece", POSITIONAL,
        {"piece": NAME[mover.piece_type],
         "to": chess.square_name(best_mv.to_square)},
        f"the move brings the {NAME[mover.piece_type]} off its starting "
        f"square to {chess.square_name(best_mv.to_square)}")


def _castles_the_king_away(b, best_mv, after_best, us,
                           played_san) -> Optional[Purpose]:
    """The better move castles and the played one did not.

    100 cards in the residue, and one of them is the card Mohit opened:
    6...Ng4 with the king still on e8, after which d4 opens the centre and
    Bb4+ comes with tempo. The caption that card got instead was written
    from the stored line with no purpose behind it -- "it let your opponent
    play d4 and then Bb4+" -- which reads the effect off the PV. The cause
    was on the board the whole time: the king had not left the centre.

    Everything claimed here is a board fact, which is the point. Castling
    moves the king off its file and brings a rook towards the middle; both
    are true of every castling move, so neither needs the engine's line to
    prove. Whether the centre is OPEN on that file is also on the board, so
    it is said only when it is.
    """
    king = b.piece_at(best_mv.from_square)
    if king is None or king.piece_type != chess.KING:
        return None
    if abs(chess.square_file(best_mv.from_square)
           - chess.square_file(best_mv.to_square)) < 2:
        return None              # a king step, not castling
    played = _mv(b, played_san)
    if played is None:
        return None
    moved = b.piece_at(played.from_square)
    if moved is not None and moved.piece_type == chess.KING:
        return None              # they moved the king too; different lesson
    kfile = chess.square_file(best_mv.from_square)
    blocked = any(
        b.piece_at(sq) is not None
        and b.piece_at(sq).piece_type == chess.PAWN
        for sq in chess.SQUARES if chess.square_file(sq) == kfile)
    where = chess.square_name(best_mv.from_square)
    tail = ("" if blocked else
            f", and no pawn is left on the {chess.FILE_NAMES[kfile]}-file "
            f"to shield it")
    return Purpose(
        "castles_the_king_away", SAFETY,
        {"from": where, "file_is_open": not blocked},
        f"the better move castles, taking the mover's king off {where} "
        f"and bringing a rook towards the middle{tail}")


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


HOME_SQUARES = {
    (chess.KNIGHT, chess.WHITE): (chess.B1, chess.G1),
    (chess.KNIGHT, chess.BLACK): (chess.B8, chess.G8),
    (chess.BISHOP, chess.WHITE): (chess.C1, chess.F1),
    (chess.BISHOP, chess.BLACK): (chess.C8, chess.F8),
    (chess.ROOK, chess.WHITE): (chess.A1, chess.H1),
    (chess.ROOK, chess.BLACK): (chess.A8, chess.H8),
    (chess.QUEEN, chess.WHITE): (chess.D1,),
    (chess.QUEEN, chess.BLACK): (chess.D8,),
}


def piece_driven_home(board: chess.Board, line: Sequence[str],
                      owner: chess.Color) -> Optional[Dict[str, Any]]:
    """The first move in `line` that sends one of `owner`'s pieces back to
    a square it started the game on, while something attacks it there.

    This is the shape behind the sentence Mohit praised in the authored
    Rousseau caption -- "the knight often has very few good squares and may
    even have to retreat to g1" -- and the engine already produces it: the
    line after c3 is `fxe4 Ng1 d5 Bb3`. The idea was in the PV the whole
    time; nothing was reading it.

    Pawns and kings are excluded. A pawn cannot return home, and a king on
    e1 is usually castling or safe rather than driven.

    Returns the piece, the square it left, and the square it went back to,
    or None. Pure: no engine, no DB, so the caption layer can use it on a
    stored line and the Why button on a fresh one.
    """
    w = board.copy()
    for san in list(line or []):
        try:
            mv = w.parse_san(str(san))
        except Exception:
            return None
        p = w.piece_at(mv.from_square)
        if p is not None and p.color == owner and \
                mv.to_square in HOME_SQUARES.get((p.piece_type, p.color), ()):
            # Driven, not merely regrouping: it must have been under attack
            # on the square it LEFT. The first version of this asked whether
            # it was attacked where it LANDED and found nothing on the one
            # case it was written for -- a driven piece retreats INTO safety,
            # which is the whole point. On the Rousseau line `fxe4 Ng1`, the
            # e4 pawn hits the knight on f3 and g1 is quiet.
            if w.attackers(not owner, mv.from_square):
                return {
                    "san": str(san),
                    "piece": NAME[p.piece_type],
                    "from": chess.square_name(mv.from_square),
                    "to": chess.square_name(mv.to_square),
                }
        w.push(mv)
    return None


# ── named shapes: what a move SETS UP ────────────────────────────────
#
# Mohit: "it's a simple pattern and a great teaching, general rule for a4,
# you know is to do b4 for bishop trap... i can't really author everywhere".
#
# This table is the answer to both halves. It is authoring -- somebody wrote
# these rows -- but generic: four rows, written once, apply to every game
# forever with no per-opening work. New patterns arrive as rows.
#
# Each row is (the rook pawn's destination, the enemy bishop's square, the
# push that hits it). The claim needs no search and no guess about what the
# opponent intends: a4 supports b4, and b4 attacks c5, always.
#
# Measured on 400 games: 0.05% of moves and 1.5% of GAMES -- about one
# teaching moment every 67 games. Rare per card, which is the wrong
# denominator for a pattern you recognise. Unlike the fuzzy 0.4% probe that
# was cut earlier, this cannot misfire: every clause is table-driven
# geometry.
PAWN_CHASE_SHAPES = {
    chess.WHITE: (("a4", chess.C5, "b4"), ("h4", chess.F5, "g4")),
    chess.BLACK: (("a5", chess.C4, "b5"), ("h5", chess.F4, "g5")),
}


def _prepares_the_pawn_chase(b: chess.Board, played_san: str,
                             reply: Optional[str]) -> Optional[Purpose]:
    """The rook pawn advances and the next push will hit their bishop.

    A PLAN fact, not a fault. The move that starts this is usually fine --
    Mohit's a4 card is about 5cp -- so nothing in the rest of this file
    would ever look at it. That is why it has its own entry point.
    """
    try:
        us = b.turn
        mv = b.parse_san(str(played_san))
    except Exception:
        return None
    p = b.piece_at(mv.from_square)
    if p is None or p.piece_type != chess.PAWN or p.color != us:
        return None
    dest = chess.square_name(mv.to_square)
    for rook_dest, bishop_sq, hitter in PAWN_CHASE_SHAPES.get(us, ()):
        if dest != rook_dest:
            continue
        bp = b.piece_at(bishop_sq)
        if bp is None or bp.color == us or bp.piece_type != chess.BISHOP:
            continue
        after = b.copy()
        after.push(mv)
        after.turn = us              # our move again, to read the plan
        push = None
        for m in after.legal_moves:
            if after.san(m) == hitter:
                push = m
                break
        if push is None:
            continue
        w = after.copy()
        w.push(push)
        if bishop_sq not in w.attacks(push.to_square):
            continue
        guards = [s for s in w.attackers(us, push.to_square)
                  if w.piece_at(s) and w.piece_at(s).piece_type == chess.PAWN]
        where = chess.square_name(bishop_sq)
        held = (f", and the {chess.square_name(guards[0])} pawn holds "
                f"{hitter} so the bishop cannot simply take it"
                if guards else "")
        facts: Dict[str, Any] = {
            "next_push": hitter, "bishop_on": where,
            "pawn_defended": bool(guards),
        }
        if reply:
            # The waiting side's answer, taken from the engine's own reply
            # rather than chosen here.
            facts["their_answer"] = str(reply)
        return Purpose(
            "prepares_the_pawn_chase", POSITIONAL, facts,
            f"the move puts the rook pawn on {dest} so that {hitter} comes "
            f"next, attacking the waiting side's bishop on {where}{held}")
    return None


def develop_why(board, move) -> Optional[Dict[str, Any]]:
    """What a developing move actually does, for the OTHER caption path.

    This module feeds `llm_caption`. The rule cascade has its own,
    independent answer to "why is this move good" --
    `caption_facts._recommended_move_why` -- and Mohit's card went down
    THAT path: its record carries no `llm_caption` at all, so the three
    facts added here never touched it. The card he flagged said "it brings
    a new piece into the game" because `caption_facts.py:9706` maps the
    principle `develop` to exactly that string.

    Two writers for one question is the duplication this repo keeps
    paying for, so the geometry stays here and only the PHRASING differs:
    the detectors above return a proof for a model to rewrite, this
    returns the same facts for the cascade to slot into "it {why}".

    Returns the facts of whichever fires, idea before consequence, or None.
    """
    try:
        us = board.turn
        after = board.copy()
        after.push(move)
        for fn in (_bishop_to_the_square_the_pawn_left,
                   _develops_against_a_target):
            p = fn(board, move, after, us)
            if p is not None:
                out = dict(p.facts)
                out["kind"] = p.kind
                return out
    except Exception:
        # This module is pure and has no logger; a caption path must never
        # fail because a board helper threw.
        pass
    return None


def pawn_storm_why(board, move) -> Optional[Dict[str, Any]]:
    """The reason behind a rook-pawn advance, for the cascade.

    The other half of Mohit's card: it said "Play h4." and stopped. The
    cascade asks `caption_facts._recommended_move_why` for every
    recommended reply, and h4 hits nothing, checks nothing and develops
    nothing, so every branch there abstained and the card commanded a move
    with no reason -- the thing he has objected to since the Bxe2 card.

    Same arrangement as `develop_why`: the geometry stays here, the caller
    renders it. Returns the facts or None.
    """
    try:
        us = board.turn
        after = board.copy()
        after.push(move)
        p = _prepares_the_pawn_storm(board, move, after, us)
        if p is not None:
            out = dict(p.facts)
            out["kind"] = p.kind
            return out
    except Exception:
        pass
    return None


def plan_purposes_for(
    fen_before: str,
    played_san: str,
    eval_line: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """What this move SETS UP, for moves that are not faults.

    Separate from `purposes_for` on purpose. That one answers "why was this
    worse than the engine's move", and most of its facts describe what the
    BETTER move achieves -- meaningless on a move that IS the best one. So
    running it on a good move would produce nonsense, which is why only the
    plan family lives here.

    `eval_line` is the engine's own continuation after the played move, so
    its first move is the waiting side's answer. Every move carries one
    since the floor line shipped; before that, a non-faulted move had no
    line at all and none of this was possible.
    """
    try:
        b = chess.Board(fen_before)
    except Exception:
        return []
    reply = None
    for san in list(eval_line or []):
        reply = str(san)
        break
    out: List[Purpose] = []
    try:
        p = _prepares_the_pawn_chase(b, played_san, reply)
        if p:
            out.append(p)
    except Exception:
        pass
    return [p.as_dict() for p in out]


def _colour_of(sq: int) -> int:
    """0 for a dark square, 1 for a light one."""
    return (chess.square_file(sq) + chess.square_rank(sq)) % 2


def _bishops_on_colour(board: chess.Board, colour: chess.Color,
                       comp: int) -> list:
    return [s for s, p in board.piece_map().items()
            if p.color == colour and p.piece_type == chess.BISHOP
            and _colour_of(s) == comp]


def _played_lost_the_colour_squares(b, best_mv, after_best, us, played_san,
                                    pv_played) -> Optional[Purpose]:
    """The line trades off the mover's last bishop of one colour, and the
    waiting side keeps the bishop that works those squares.

    Mohit's Bg4 card, and the question that produced this: Bg4 pins the f3
    knight against the QUEEN, White plays h3, and every square the bishop
    can reach is worse than the one it left -- so it takes the knight. The
    trade is materially even and the move still costs 142cp. Asked why,
    the board answers: that bishop was Black's only light-squared piece,
    White keeps Bc4, and e6, b5 and d5 are all attacked more than they are
    defended. Measured on the same card: keeping the bishop is +155, giving
    it for the knight is +274. **119 of the 142 is the trade, not the
    tempo.**

    Stockfish gates this and the board only explains it. The engine says the
    move is a fault and its line is what shows the bishop coming off; this
    walks that line and counts. No extra search.

    Three clauses, and two of them exist because the loose version failed a
    control:

      the square must be OUTNUMBERED, not undefended. Written as "they
      attack it and we do not defend it at all", this missed the card it was
      built from: e6 is White 2 / Black 1, contested and lost, which is the
      whole point.

      their surviving bishop must be ON the colour we lost. Written as "any
      bishop", it fired where the dark squares went and the only enemy
      bishop was light-squared -- a true sentence about a weakness nobody
      could exploit.

    4.7% of faulted cards that carry a line, which makes it the second
    largest purpose in this file.
    """
    if not pv_played:
        return None
    try:
        w = b.copy()
        w.push(w.parse_san(str(played_san)))
        for san in list(pv_played)[:10]:
            w.push(w.parse_san(str(san)))
    except Exception:
        return None

    lost = None
    for comp in (0, 1):
        if _bishops_on_colour(b, us, comp) and \
                not _bishops_on_colour(w, us, comp):
            lost = comp
            break
    if lost is None:
        return None

    theirs = _bishops_on_colour(w, not us, lost)
    if not theirs:
        return None

    weak = []
    for sq in chess.SQUARES:
        if _colour_of(sq) != lost:
            continue
        # Only squares on the mover's own side are worth naming.
        rank = chess.square_rank(sq)
        if (rank > 3) if us == chess.WHITE else (rank < 4):
            continue
        att = len(w.attackers(not us, sq))
        if att and att > len(w.attackers(us, sq)):
            weak.append(chess.square_name(sq))
    if not weak:
        return None

    shade = "dark" if lost == 0 else "light"
    squares = sorted(weak)[:3]
    return Purpose(
        "played_lost_the_colour_squares", POSITIONAL,
        {"colour": shade, "weak_squares": squares,
         "their_bishop": chess.square_name(theirs[0])},
        f"this line trades off the mover's last bishop on the {shade} "
        f"squares while the waiting side keeps the bishop on "
        f"{chess.square_name(theirs[0])}, and "
        f"{', '.join(squares)} are attacked more than they are defended")


def _offered_and_not_taken(b, best_mv, after_best, us,
                           played_san, pv_played) -> Optional[Purpose]:
    """The man just played can be taken for free, and the engine declines.

    Mohit's Rousseau card: Black plays f5, exf5 takes the pawn with nothing
    defending it, and the engine's answer is d4 instead. The authored
    caption for that position reads "because of this idea, exf5 is usually
    a mistake" -- and that conclusion is derivable from the line already
    stored, which is why it belongs in a caption rather than behind the
    button.

    What is NOT claimed here is WHY taking is wrong. On that card the
    reason is that after exf5 e4 hits the knight on f3, and seeing it needs
    a search of a line the engine never returns, because the engine does
    not play exf5. So the reason goes to the Why button, which already pays
    for an engine, and this states only what the board and the stored line
    prove.

    Tightened before shipping. "A man that can be captured where the engine
    prefers another move" fires on 16.3% of faulted cards -- every pawn
    trade ever offered. Requiring the capture to WIN material statically,
    which is what makes declining a lesson rather than a shrug, brings it
    to 2.2% (263 cards).
    """
    if not pv_played:
        return None
    played = _mv(b, played_san)
    after_played = _after(b, played_san)
    if played is None or after_played is None:
        return None
    reply = _mv(after_played, str(pv_played[0]))
    if reply is None:
        return None
    target = played.to_square
    takers = [m for m in after_played.legal_moves
              if m.to_square == target and after_played.is_capture(m)]
    if not takers or reply.to_square == target:
        return None              # nothing to take, or the engine takes it
    victim = after_played.piece_at(target)
    if victim is None:
        return None
    cheapest = min(VALUE[after_played.piece_at(m.from_square).piece_type]
                   for m in takers)
    defended = bool(after_played.attackers(victim.color, target))
    if defended and cheapest >= VALUE[victim.piece_type]:
        return None              # taking is a trade, not a free man
    taker = after_played.san(takers[0])
    return Purpose(
        "offered_and_not_taken", POSITIONAL,
        {"man": NAME[victim.piece_type],
         "square": chess.square_name(target),
         "capture": taker, "answered_with": str(pv_played[0])},
        f"the {NAME[victim.piece_type]} on {chess.square_name(target)} can "
        f"be taken by {taker} with nothing to win it back, and the waiting "
        f"side's best answer is {pv_played[0]} instead")


def _played_check_achieved_nothing(b, best_mv, after_best, us,
                                   played_san,
                                   pv_played) -> Optional[Purpose]:
    """The played move checks, they answer it, and nothing was won.

    131 cards in the residue and one of the few lessons in this file a 900
    can apply the same evening: a check they simply answer hands them a
    move. Mohit's own phrasing of it is that checking for the sake of
    checking is a habit, not a plan.

    "Achieved nothing" is proven, not assumed. Push the check, push their
    answer, and compare material: if the check won a man, this is not the
    lesson and one of the material purposes already has it. The second half
    -- the checking piece has to move again -- is what makes it a lost
    tempo rather than merely a quiet move, so it is claimed only when the
    board shows the piece attacked afterwards.
    """
    after_played = _after(b, played_san)
    played = _mv(b, played_san)
    if after_played is None or played is None or not pv_played:
        return None
    if not b.gives_check(played):
        return None
    reply = _mv(after_played, str(pv_played[0]))
    if reply is None:
        return None
    piece = b.piece_at(played.from_square)
    if piece is None or piece.piece_type == chess.KING:
        return None
    # contrastive_reasoner owns both the material count and the
    # taken-and-kept walk, and caption_facts already reuses the first. A
    # second answer to either question here would be a second answer.
    from services.contrastive_reasoner import _material_swing, _taken_and_kept
    line = [str(s) for s in pv_played]
    # The WHOLE line, not two plies. Ne7+ Bxe7 reads as a lost knight until
    # Rxe7 takes the bishop back on the very next ply, and the first version
    # of this purpose called six such cards "wins nothing" -- a sentence
    # that understates giving a piece away and overstates an even trade in
    # the same breath.
    swing = _material_swing(b, [str(played_san)] + line, us)
    if swing is None or swing > 0:
        return None              # the check won something; not this lesson
    where = chess.square_name(played.to_square)
    lost = _taken_and_kept(after_played, line, played.to_square, us)
    if lost is not None:
        # They simply took the piece that checked, and kept it. A bigger
        # lesson than a wasted move, so it ranks with the material ones.
        return Purpose(
            "played_check_loses_the_checker", MATERIAL,
            {"reply": lost["san"], "piece": NAME[piece.piece_type],
             "square": where, "taken_by": lost["by"]},
            f"the checking {NAME[piece.piece_type]} on {where} is taken by "
            f"the {lost['by']} with {lost['san']}, and it does not come "
            f"back")
    if swing < 0:
        # The line costs material for some other reason. Whatever that is,
        # it is not "the check achieved nothing", and saying so here would
        # describe a lost piece as a wasted tempo.
        return None
    nb = after_played.copy()
    nb.push(reply)
    chased = bool(nb.attackers(not us, played.to_square)) and \
        nb.piece_at(played.to_square) is not None and \
        nb.piece_at(played.to_square).color == us
    tail = (f", and the {NAME[piece.piece_type]} on {where} is attacked "
            f"there and has to move again" if chased else "")
    return Purpose(
        "played_check_achieved_nothing", POSITIONAL,
        {"reply": str(pv_played[0]), "chased": chased},
        f"the check is answered by {pv_played[0]} and wins nothing{tail}")


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
                   _bishop_to_the_square_the_pawn_left,
                   _develops_against_a_target, _prepares_the_pawn_storm,
                   _develops_a_piece, _wins_the_exchange):
            try:
                p = fn(b, best_mv, after_best, us)
            except Exception:
                p = None
            if p:
                out.append(p)
        for fn2 in (_avoids_attacked_square, _played_develops_nothing,
                    _castles_the_king_away,
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
        for fn3 in (_played_allows_fork, _played_leaves_king_exposed,
                    _played_check_achieved_nothing,
                    _offered_and_not_taken,
                    _played_lost_the_colour_squares):
            try:
                p = fn3(b, best_mv, after_best, us, played_san,
                        list(pv_played or []))
                if p:
                    out.append(p)
            except Exception:
                pass
        try:
            p = _answers_threat(b, best_mv, after_best, us, threat,
                                played_san=played_san)
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

    # One pair of purposes CONTRADICTS rather than merely competing, so
    # ranking cannot settle it and one of them has to go.
    #
    # Mohit's Rousseau card: Black plays f5, and the list came back with
    # "f5 is attacked and f6 is not" second and "the pawn on f5 can be
    # taken and the engine answers d4 instead" last. Both read the same
    # board. But if the engine declines the free man, the square being
    # attacked is the POINT of the move, not a reason against it -- and
    # `avoids_attacked_square` says the mover should have gone somewhere
    # safe, which on an offer is false teaching.
    #
    # The offer is the proven one: it rests on the engine's own answer.
    # So when both describe the same square, the offer survives.
    _offer_squares = {p.facts.get("square") for p in out
                      if p.kind == "offered_and_not_taken"}
    if _offer_squares:
        out = [p for p in out
               if not (p.kind == "avoids_attacked_square"
                       and p.facts.get("played_square") in _offer_squares)]

    # The same move cannot be told twice, once with content and once as
    # filler. When the developed piece is named with what it bears on,
    # `develops_a_piece` describes the identical move and adds only "off
    # its starting square" -- and its lesson, "early on, every move should
    # bring a new piece into the game", is the exact sentence Mohit flagged
    # on his Bg7 card. Leaving it in the bundle leaves the model free to
    # reach for it.
    if any(p.kind in ("develops_against_a_target",
                     "bishop_to_the_square_the_pawn_left") for p in out):
        out = [p for p in out if p.kind != "develops_a_piece"]

    out.sort(key=rank)
    return [p.as_dict() for p in out]
