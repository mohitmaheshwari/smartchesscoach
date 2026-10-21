"""A deterministic reasoner: a bank of contrastive questions, ranked.

Mohit 2026-10-21: "how do I make this deterministically reasoning model".

What I actually did on his Nc3 card was not understanding. It was six
mechanical questions asked of four objects already on disk -- the board
before, the board after, the engine's best line, and the engine's line after
the played move. Each question is a set operation or a legality test. The
intelligence is in WHICH questions get asked and HOW the answers are ranked,
not in answering them.

The ranking matters as much as the questions. "The knight walks back to b1"
and "Nc3 blocks the c-pawn" are the same finding at different depths: one is
a SYMPTOM, the other its CAUSE. The shipped caption picked the symptom
because nothing told it that causes outrank consequences. So every question
carries a tier, and the card speaks the highest tier that answered.

    CAUSE       what your move made impossible / allowed
    EVIDENCE    what the engine's own behaviour reveals about your move
    SYMPTOM     what visibly happens afterwards

A question returns evidence or nothing. Nothing is a valid answer; a question
that cannot prove its claim stays quiet rather than guessing.
"""
from typing import Any, Dict, List, Optional, Sequence
import chess

CAUSE, EVIDENCE, SYMPTOM = 3, 2, 1


def _our_line_moves(board, first_san, line, limit=6):
    us = board.turn
    b = board.copy()
    out = []
    try:
        b.push(b.parse_san(str(first_san)))
    except Exception:
        return out
    for san in list(line)[:limit]:
        try:
            mv = b.parse_san(str(san))
        except Exception:
            break
        if b.turn == us:
            out.append((str(san), mv))
        b.push(mv)
    return out


# ── Q1 (CAUSE) ── did your move forbid a move the better line plays? ──
def q_blocked_a_plan(ctx) -> Optional[Dict[str, Any]]:
    b, after = ctx["before"], ctx["after"]
    for san, mv in _our_line_moves(b, ctx["best_san"], ctx["pv_best"]):
        legal_before = any(m.from_square == mv.from_square
                           and m.to_square == mv.to_square
                           for m in b.legal_moves)
        if not legal_before:
            continue
        probe = after.copy()
        probe.turn = b.turn
        probe.ep_square = None
        if probe.is_check() or not probe.is_valid():
            continue
        if any(m.from_square == mv.from_square and m.to_square == mv.to_square
               for m in probe.legal_moves):
            continue
        piece = b.piece_at(mv.from_square)
        return {"tier": CAUSE, "id": "blocked_a_plan", "san": san,
                "piece": chess.piece_name(piece.piece_type) if piece else "piece",
                "square": chess.square_name(mv.to_square)}
    return None


# ── Q2 (EVIDENCE) ── does the engine retreat the piece you just moved,
#                     with nothing attacking it? ──
def q_engine_undoes_it(ctx) -> Optional[Dict[str, Any]]:
    b = ctx["before"]
    try:
        played = b.parse_san(ctx["played_san"])
    except Exception:
        return None
    home, here = played.from_square, played.to_square
    walk = b.copy()
    walk.push(played)
    for san in list(ctx["pv_played"] or [])[:8]:
        try:
            mv = walk.parse_san(str(san))
        except Exception:
            return None
        if mv.from_square == here and walk.turn == b.turn:
            attacked = bool(walk.attackers(not b.turn, here))
            if mv.to_square == home and not attacked:
                piece = walk.piece_at(here)
                return {"tier": EVIDENCE, "id": "engine_undoes_it",
                        "piece": chess.piece_name(piece.piece_type)
                        if piece else "piece",
                        "home": chess.square_name(home),
                        "unattacked": True}
            here = mv.to_square
        walk.push(mv)
    return None


# ── Q3 (SYMPTOM) ── does the piece simply end up back home? ──
def q_returns_home(ctx) -> Optional[Dict[str, Any]]:
    b = ctx["before"]
    try:
        played = b.parse_san(ctx["played_san"])
    except Exception:
        return None
    home, here = played.from_square, played.to_square
    walk = b.copy()
    walk.push(played)
    for san in list(ctx["pv_played"] or [])[:8]:
        try:
            mv = walk.parse_san(str(san))
        except Exception:
            return None
        if mv.from_square == here:
            if mv.to_square == home:
                return {"tier": SYMPTOM, "id": "returns_home",
                        "home": chess.square_name(home)}
            here = mv.to_square
        walk.push(mv)
    return None


# ── Q4 (CAUSE) ── did your move walk away from one of your own guards,
#                  and does the engine's own line then collect what it guarded? ──
def q_abandoned_own_defender(ctx):
    """The mirror of removing-the-defender: here YOU remove your own.

    Mohit's e5 card, 2026-10-21, cp_loss 100:

        r2qk2r/ppp2ppp/2nbpn2/3p1b2/3P4/P1N1PN2/1PP1BPPP/R1BQ1RK1 b kq - 3 7

    The e6 pawn guards d5. Push it to e5 and d5 is a guard short; the stored
    line goes dxe5 Nxe5 Nxd5 and the pawn is simply gone. The shipped card
    said "This move cost you something" -- true, useless, and mine.

    Four clauses, three on the board and one on the engine's stored line:

      1 the moved man was covering one of our own men (never the king: a king
        "guard" is a different lesson and often an illegal-capture story)
      2 our cover of that square really dropped -- counted, so a discovered
        defender or the same piece still covering from its new home both
        mean silence
      3 they attack it once we have moved
      4 and in THEIR line they take it, and we do not win it back on that
        square next move
      5 and the man who walked away is not himself captured for nothing,
        because then the headline is the piece we just lost, not the job it
        stopped doing
      6 and nobody gets mated in the line, because then the lesson is the mate
      7 and nothing much bigger than the abandoned man falls, because
        explaining a pawn while a queen is going is the same failure as
        explaining nothing
      8 and the line actually costs us something, because a man we get paid
        for was traded, not lost

    Clause 4 is the one that makes this honest. Geometry alone would also fire
    on d5 in that same position after a quiet move, and on the f5 bishop,
    which loses a guard and nothing else. The engine's line is what separates
    "a guard left" from "a guard left and it cost you".

    Clause 5 came from reading eight of these on the board. Seven were the
    right lesson; the eighth was `Nd7` with the reply `Qxd7`, where the knight
    we moved is taken on its new square. Every clause held and the sentence
    would still have been absurd -- "you stopped guarding g4" about a move
    that drops a knight. True is not the same as worth saying.

    Clauses 6, 7 and 8 came from reading the rendered sentences, which is a
    separate audit from reading the clauses. One card explained a pawn on g7
    to a player who was being mated on h7; another explained a knight on c6
    while `Nxc6+` was winning the queen behind it; a third explained a knight
    on g4 in a line that wins us their queen, leaving us seven pawns up. Every
    claim was true. Every one of those cards would have taught the wrong thing.

    Clause 8 is worth its own line because 7 does not imply it. Clause 7 asks
    whether something much BIGGER went, and clause 8 whether anything went at
    all: 16.1% of 218 firing cards ended the line even or ahead, where the man
    was traded rather than lost.
    """
    b, after = ctx["before"], ctx["after"]
    us = b.turn
    try:
        played = b.parse_san(str(ctx["played_san"]))
    except Exception:
        return None
    frm, to = played.from_square, played.to_square
    mover = b.piece_at(frm)
    if mover is None or mover.piece_type == chess.KING:
        return None

    line = list(ctx.get("pv_played") or [])
    if not line:
        return None

    # 5) if they simply take the piece we moved, that is the lesson instead.
    if _taken_and_kept(after, line, to, us):
        return None

    # 6) a mate in the line owns the card outright.
    if _line_ends_in_mate(after, line):
        return None

    swing = _material_swing(after, line, us)

    for t in sorted(b.attacks(frm)):
        held = b.piece_at(t)
        if held is None or held.color != us or held.piece_type == chess.KING:
            continue
        # 2) did our cover of t really drop?
        if len(after.attackers(us, t)) >= len(b.attackers(us, t)):
            continue
        if t in after.attacks(to):          # still covering it from the new square
            continue
        # 3) do they hit it now?
        if not after.attackers(not us, t):
            continue
        # 4) do they take it in their own line, and keep it?
        taken = _taken_and_kept(after, line, t, us)
        if not taken:
            continue
        # 7) is this man the story, or did something much bigger go?
        if swing is not None and swing < -(_VALUE[held.piece_type] + 2):
            continue
        if _beyond_this_man(ctx.get("cp_loss"), held.piece_type):
            continue
        # 8) did the line actually cost us anything? Measured over 218 firing
        #    cards, 16.1% come out EVEN OR AHEAD on material: the man was
        #    traded, often for something bigger, and "they took it" reads as a
        #    loss the player did not suffer. Clause 7 caps the loss from above
        #    and this caps it from below.
        if swing is None or swing >= 0:
            continue
        # The shape lives here because two surfaces render this answer -- the
        # one-clause form the caption rules compose into a sentence
        # (R12_blunder's `failure_abandoned_own_guard` and
        # R_PROMOTED_basic_mistake's `with_abandoned_guard`) and the full
        # three-sentence card in `self_removal_caption.py` -- and a concept
        # whose shape is decided twice will eventually disagree with itself.
        guards_left = len(after.attackers(us, t))
        if guards_left == 0:
            shape = "NO_GUARD"
        elif taken["gives_check"]:
            shape = "SHORT_CHECK"
        else:
            shape = "SHORT_QUIET"
        return {"tier": CAUSE, "id": "abandoned_own_defender",
                "played_san": str(ctx["played_san"]),
                "shape": shape,
                "guards_left": guards_left,
                "guard": chess.piece_name(mover.piece_type),
                "guard_from": chess.square_name(frm),
                "guard_verb": ("pushed" if (mover.piece_type == chess.PAWN
                                            and not b.is_capture(played))
                               else "moved"),
                "lost": chess.piece_name(held.piece_type),
                "square": chess.square_name(t),
                "gives_check": taken["gives_check"],
                "taken_by": taken["by"],
                "taken_san": taken["san"],
                "taker_square": taken["from"]}
    return None


_VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
          chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


# Where this sits is the distribution's choice, not mine. Over 461 real cases
# the excess -- how far cp_loss runs past the value of the man being explained
# -- climbs smoothly to about 900 (97.3% of cases sit at or below it) and then
# jumps straight to 9,000-plus for 5.4% of them. That upper cluster is mate
# scores: the player is being mated and the card would be discussing a pawn.
# The gap between the two populations is where the gate belongs.
MATE_LIKE_EXCESS_CP = 900


def _beyond_this_man(cp_loss, piece_type):
    """Did the move cost so much more than this man that he is not the story?

    A mate is why this exists and why the material swing cannot replace it:
    in the g7 case the stored line WINS us a rook on the way to being mated,
    so the swing is positive and only the engine's own number tells the truth.
    """
    if cp_loss is None:
        return False
    try:
        cp = abs(int(cp_loss))
    except (TypeError, ValueError):
        return False
    return cp - _VALUE[piece_type] * 100 > MATE_LIKE_EXCESS_CP


def _line_ends_in_mate(after, line_san):
    """Checkmate anywhere in the line. Played on the board, not read off
    mate_info, which is white-relative and signed and easy to misread."""
    w = after.copy()
    if w.is_checkmate():
        return True
    for san in line_san:
        try:
            w.push(w.parse_san(str(san)))
        except Exception:
            return False
        if w.is_checkmate():
            return True
    return False


def _material_swing(after, line_san, us):
    """What the whole line costs us, in pawns. None if the line will not
    replay. Negative means we came out behind."""
    def count(board):
        return sum(_VALUE[p.piece_type] * (1 if p.color == us else -1)
                   for p in board.piece_map().values())
    w = after.copy()
    start = count(w)
    for san in line_san:
        try:
            w.push(w.parse_san(str(san)))
        except Exception:
            return None
    return count(w) - start


def _taken_and_kept(after, line_san, target, us):
    """Walk THEIR stored line: do they capture our man on `target`, and is it
    still theirs after our very next move?"""
    w = after.copy()
    for i, san in enumerate(line_san):
        try:
            mv = w.parse_san(str(san))
        except Exception:
            return None
        if w.turn != us and mv.to_square == target:
            victim = w.piece_at(target)
            if victim is None or victim.color != us:
                return None
            taker = w.piece_at(mv.from_square)
            gives_check = w.gives_check(mv)
            w.push(mv)
            # our next move: do we win it back on that square?
            if len(line_san) > i + 1:
                try:
                    reply = w.parse_san(str(line_san[i + 1]))
                except Exception:
                    reply = None
                if reply is not None and reply.to_square == target:
                    return None
            return {"by": chess.piece_name(taker.piece_type) if taker else "piece",
                    "from": chess.square_name(mv.from_square),
                    "san": str(san),
                    "gives_check": gives_check}
        w.push(mv)
    return None


QUESTIONS = [q_blocked_a_plan, q_abandoned_own_defender,
             q_engine_undoes_it, q_returns_home]


def reason(board_before: chess.Board, played_san: str, best_san: str,
           pv_best: Sequence[str], pv_played: Sequence[str]) -> List[Dict]:
    """Ask every question; return the answers, strongest tier first."""
    after = board_before.copy()
    try:
        after.push(board_before.parse_san(str(played_san)))
    except Exception:
        return []
    ctx = {"before": board_before, "after": after, "played_san": played_san,
           "best_san": best_san, "pv_best": pv_best or [],
           "pv_played": pv_played or []}
    found = []
    for q in QUESTIONS:
        try:
            r = q(ctx)
        except Exception:
            r = None
        if r:
            found.append(r)
    return sorted(found, key=lambda r: -r["tier"])
