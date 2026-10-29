"""The "Why" button: pick the good move that explains itself.

The problem this exists to solve
--------------------------------
Every other caption path computes the why under a page-render deadline.
When it cannot derive a reason it still has to emit a sentence, so it
emits one it does not know. Measured 2026-09-25 on 441 fresh mistake
captions: 25.6% named the punishment, 51.5% described only the
alternative move, 22.9% did neither. Rewording variant files cannot fix
that, because the shortage is of *derivable reasons*, not of prose.

Behind a button the deadline goes away. So instead of taking the
engine's single best move and struggling to explain it, we ask for
several good moves and keep the first one we can explain from the
board. Settings and their measurements are in
docs/why_button_scope.md; the short version, on 40 positions, server,
Threads=1: depth 18 / 8 candidates costs 5.5s median and leaves ~10%
with nothing explainable.

That remainder is the point of the design, not a defect. explain()
returns None there and the caller must say so. Manufacturing a sentence
for those positions is the bug we are removing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

import chess

from services.punishment_resolver import (
    Punishment,
    _line_material_gain,
    agent_owner,
    resolve_missed,
    resolve_received,
    victim_owner,
)
from services.severity import SEVERITY_THRESHOLDS

logger = logging.getLogger(__name__)

# How many engine candidates to consider. 8, not 4: top-4 halves the wait
# but doubles the share of positions with nothing explainable (18% vs 10%),
# and that share is exactly the bucket that produces invented captions.
CANDIDATE_COUNT = 8

# Matches the depth the stored analysis already uses, so a candidate's
# evaluation here is comparable with the cp_loss on the card.
CANDIDATE_DEPTH = 18

# We will not recommend a move that is materially worse than the engine's
# best just because it made a tidier story. Measured: the best move is
# itself explainable 25/36 times, and 31/36 land inside this bound.
#
# 2026-10-29: it is the CANONICAL INACCURACY FLOOR, not 50.
#
# Those two numbers disagreed, and the gap was the only source of wrong answers
# in the engine. services.severity calls a move 30cp or worse an inaccuracy, so
# at 50 this function was free to prescribe a move it would itself fault -- "c5
# wins their pawn" where the engine approves of Be7, Nc6 and Nf6; "g5 chases
# their bishop" where it approves of f5, Bxc4 and Na6.
#
# Measured over 309 faulted positions, the same positions at both settings:
#
#     window   answered    missed answers   wrong   received   wrong
#       50cp   248 (80%)        59            8       189        0
#       30cp   240 (78%)        51            0       189        0
#
# Tightening loses exactly 8 answers and ALL EIGHT are the wrong ones -- not one
# correct answer is lost. Two points of coverage for every incorrect
# recommendation in the sample. The diagnosis half (`received`) is untouched:
# 189 answers, zero errors, at either setting.
#
# Imported rather than restated so the two can never drift apart again.
CLOSENESS_CP = SEVERITY_THRESHOLDS["inaccuracy"]

# Mechanisms whose payoff_cp is real material, and so is comparable with a
# move's cp_loss. The others are not: MATE and PROMOTES pay a constant, and
# FORCES_RETREAT pays max(1, value // 10) -- a tempo proxy. A plain
# payoff/cost ratio applied to all six would have deleted 8 sound "chases
# your knight" captions to fix 5 bad ones, measured on 108 answers.
MATERIAL_MECHANISMS = ("WINS_MATERIAL", "FORK", "TRAPPED")

# Mate arrives in the SCORE, and the line walk threw it away.
#
# get_candidate_lines reports every eval through score(mate_score=100000), so a
# forced mate comes back as 100000 minus its distance. _consequences looks for
# mate by replaying `line[:_LINE_PLY]` instead -- six plies -- so a mate in nine
# moves is eighteen plies away and invisible, and the engine's own certainty is
# discarded in favour of a truncated replay.
#
# Measured on 320 positions: 4 carry a mate score and the button is silent on
# all 4, while 0 of the 242 it CAN explain carry one. A mate score predicts
# silence perfectly. Three of the four are stored at cp_loss 8640-9148, so these
# are not marginal positions -- they are the worst moves in the sample, and the
# one answer we are certain of is the one we drop.
#
# The floor is read off the encoding, not chosen: a mate is 100000 minus a
# distance of at most a few hundred plies, and a real centipawn eval never comes
# close -- measured over 192,112 stored evals, the non-mate maximum is 8308.
MATE_SCORE_BASE = 100_000
MATE_SCORE_FLOOR = 99_000

# When a move costs this much or more and the material we can name covers
# less than MISMATCH_MIN_RATIO of it, we have not found the real reason.
# Measured on 115 material answers: below 1000cp the claim covers at least
# half the loss on 67-96% of answers; at 1000+ only 14% do and 86% fall
# under a fifth. Those are mate swings, where material is not the story and
# R01_mate already speaks. Suppressing them costs 6 of 181 answers (3.3%).
# 20% and 25% suppress the same 6, so the edge is not knife-edge.
MISMATCH_MIN_CP_LOSS = 1000
MISMATCH_MIN_RATIO = 0.25


def _phrase(p: Punishment, played_san: str,
            mover_is_user: bool = True) -> Optional[str]:
    """One plain sentence. Short words, one idea, no numbers.

    Returns None for a mechanism we have no honest sentence for, which
    the caller treats exactly like no punishment at all.

    `mover_is_user` says whose move is being explained, and every pronoun
    below comes from it. Without it this function read "your" off
    `direction` alone, which is right for the player's own moves and wrong
    for every one of the opponent's -- 20 of 20 in a 320-position audit. See
    punishment_resolver.victim_owner for the rule and the measurement.
    """
    # No silent fallback to the word "piece". If the resolver could not
    # name what was lost, we say "material" -- vaguer, but not a word
    # pretending to carry information it does not have.
    named = (p.victim_piece or "").strip().lower()
    piece = named or "piece"
    agent = p.agent_move

    # The resolver may name a count ("two pawns"). "wins your two pawns"
    # is understandable but clumsy; "wins two of your pawns" is how a
    # person says it. Detected by the leading count word rather than by
    # pluralising, so a single "knight" is never mangled.
    _counts = ("two ", "three ", "four ", "several ")
    _plural = named.startswith(_counts)

    def _owned(whose: str) -> str:
        """'your knight' / 'two of your pawns'."""
        if not named:
            return f"{whose} piece"
        if _plural:
            count, _, rest = named.partition(" ")
            return f"{count} of {whose} {rest}"
        return f"{whose} {named}"

    # Whose man is punished, and whose man does the punishing. Read from the
    # direction AND from whose move it is -- never from the direction alone.
    victim_whose = victim_owner(p.direction, mover_is_user)
    agent_whose = agent_owner(p.direction, mover_is_user)
    # The side that cannot save both pieces of a fork is the victim's side.
    cannot_save = "You" if victim_whose == "your" else "They"
    where = f" on {p.victim_square}" if p.victim_square else ""

    if p.direction == "received":
        if p.mechanism == "MATE":
            return f"After {played_san}, {agent} leads to mate."
        if p.mechanism == "WINS_MATERIAL":
            if named:
                return f"After {played_san}, {agent} wins {_owned(victim_whose)}."
            return f"After {played_san}, {agent} wins material."
        if p.mechanism == "FORK":
            return (f"After {played_san}, {agent} attacks two things at once. "
                    f"{cannot_save} cannot save both.")
        if p.mechanism == "TRAPPED":
            return (f"After {played_san}, {victim_whose} {piece}{where} has no "
                    f"safe square left.")
        if p.mechanism == "PROMOTES":
            # The pawn that promotes belongs to the AGENT, not the victim --
            # the one mechanism where a single owner would have inverted the
            # sentence, which is why agent_owner exists separately.
            return (f"After {played_san}, {agent_whose} pawn runs through and "
                    f"becomes a queen.")
        if p.mechanism == "FORCES_RETREAT":
            back = (" straight back to where it came from"
                    if p.returns_home else "")
            return (f"After {played_san}, {agent} chases {victim_whose} "
                    f"{piece}{back}.")
        return None

    # direction == "missed": what the better move would have collected.
    if p.mechanism == "MATE":
        return f"{agent} leads to mate."
    if p.mechanism == "WINS_MATERIAL":
        if named:
            return f"{agent} wins {_owned(victim_whose)}."
        return f"{agent} wins material."
    if p.mechanism == "FORK":
        return (f"{agent} attacks two things at once. "
                f"{cannot_save} cannot save both.")
    if p.mechanism == "TRAPPED":
        return (f"{agent} leaves {victim_whose} {piece}{where} with no safe "
                f"square.")
    if p.mechanism == "PROMOTES":
        return (f"{agent} lets {agent_whose} pawn run through and become "
                f"a queen.")
    if p.mechanism == "FORCES_RETREAT":
        # "back" only when it really goes back, which is what the `received`
        # branch above already did. This one asserted the direction on every
        # card: measured over 400 games, 423 claims and not one piece returned
        # home, while 45.9% moved FORWARD. The knight in Mohit's position went
        # c3 -> e4, to the centre, and the card called it driven back.
        back = " back" if p.returns_home else ""
        return f"{agent} chases {victim_whose} {piece}{back}."
    return None


def _explains_the_loss(p: Punishment, cp_loss: Optional[int]) -> bool:
    """False when the named material is far too small for what was lost.

    "After Qxa7, Rg1+ wins your pawn" on a move that cost 9246cp is true
    and worse than silence: it tells a player a lost position is a lost
    pawn. The only claims this can judge are the material ones -- see
    MATERIAL_MECHANISMS.
    """
    if not cp_loss or cp_loss < MISMATCH_MIN_CP_LOSS:
        return True
    if p.mechanism not in MATERIAL_MECHANISMS:
        return True
    return (p.payoff_cp or 0) >= MISMATCH_MIN_RATIO * cp_loss


def _mate_from_score(
    candidates: Sequence[Dict[str, Any]],
    played_san: str,
    played_line: Sequence[str],
) -> Optional[Punishment]:
    """A forced mate, taken from the engine's score rather than a line walk.

    Two answers live here, and both are certainties rather than inferences --
    the engine is not estimating when it returns a mate score:

      the played move ALLOWS one : its own eval is mate against the mover while
                                   the best move's is not
      the played move MISSES one : the best move's eval is mate FOR the mover
                                   while the played move's is not

    Both need the played move's own evaluation, which exists only when it is
    among the candidates the engine returned. When it is not, this stays silent
    rather than guess -- the same right-or-silent rule as everywhere else.

    Deliberately NOT a seventh mechanism: it is the MATE mechanism, reading the
    field it should have read all along, so it inherits MATE's place at the top
    of MECHANISM_RANK and its two existing sentences.
    """
    cands = [c for c in (candidates or []) if c.get("eval_cp") is not None]
    if not cands:
        return None
    played_norm = str(played_san or "").strip()
    mine = None
    for c in cands:
        if str(c.get("move_san") or "").strip() == played_norm:
            mine = c
            break
    if mine is None:
        return None

    best_cp = cands[0]["eval_cp"]
    played_cp = mine["eval_cp"]
    best_is_mate_for_us = best_cp >= MATE_SCORE_FLOOR
    played_is_mate_for_us = played_cp >= MATE_SCORE_FLOOR
    played_is_mate_against = played_cp <= -MATE_SCORE_FLOOR
    best_is_mate_against = best_cp <= -MATE_SCORE_FLOOR

    # The move walked into a forced mate that was avoidable. Both-ways mate is
    # excluded on purpose: if every move loses to mate, the move caused nothing,
    # which is the same reasoning that stopped "already being mated" counting as
    # walking into mate (services/severity.py).
    if played_is_mate_against and not best_is_mate_against:
        reply = next((str(m).strip() for m in (played_line or [])
                      if str(m or "").strip()), None)
        if not reply:
            return None
        return Punishment(
            direction="received", mechanism="MATE", agent_move=reply,
            payoff_cp=MATE_SCORE_BASE - abs(int(played_cp)),
            line=[str(m).strip() for m in list(played_line or [])[:6]],
        )

    # A forced mate was there and the move let it go.
    if best_is_mate_for_us and not played_is_mate_for_us:
        line = [str(m).strip() for m in (cands[0].get("line_san") or [])
                if str(m or "").strip()]
        if not line:
            return None
        return Punishment(
            direction="missed", mechanism="MATE", agent_move=line[0],
            payoff_cp=MATE_SCORE_BASE - abs(int(best_cp)),
            line=line[1:7],
        )
    return None


def _arrows(fen_before: str, line_san: Sequence[str],
            limit: int = 3) -> List[Dict[str, str]]:
    """One arrow per move of the line we are showing, in board order.

    Built by pushing the moves, never by parsing the sentence -- the
    prose is downstream of the proof and must never be its source.
    """
    out: List[Dict[str, str]] = []
    try:
        board = chess.Board(fen_before)
    except ValueError:
        return out
    for san in list(line_san)[:limit]:
        try:
            mv = board.parse_san(str(san or "").strip())
        except (ValueError, AssertionError, KeyError):
            break
        out.append({
            "from": chess.square_name(mv.from_square),
            "to": chess.square_name(mv.to_square),
            "san": san,
        })
        board.push(mv)
    return out


def explain(
    fen_before: str,
    played_san: str,
    pv_after_played: Sequence[str],
    candidates: Sequence[Dict[str, Any]],
    cp_loss: Optional[int] = None,
    mover_is_user: bool = True,
) -> Optional[Dict[str, Any]]:
    """Why the played move was bad, or None if we cannot honestly say.

    `candidates` is stockfish_service.get_candidate_lines() output for the
    position BEFORE the played move -- best first, each with line_san.

    `mover_is_user` says whose move is being explained. It is an ARGUMENT and
    never inferred: both sides share a move number and both may have played
    "O-O", so guessing it from the position would put the wrong pronouns on
    exactly the cards where it matters. The endpoint already knows, from its
    `opponent` flag. Default True keeps the behaviour that was correct -- the
    player's own moves -- and fixes the half that was not.

    Order of attack:
      1. What their reply actually collects. This is the most direct
         answer to "why was my move bad" and needs no alternative.
      2. Failing that, the best move we can explain, provided it is not
         materially worse than the engine's best.
      3. Failing that, None.
    """
    if not fen_before or not played_san:
        return None

    # 0. A forced mate, read off the engine's score. First, because MATE is
    #    first in MECHANISM_RANK and because it is the one answer the engine
    #    states outright instead of leaving us to derive it. Everything below
    #    walks lines; this does not need to.
    _mate = _mate_from_score(candidates, played_san, pv_after_played)
    if _mate is not None:
        _mtext = _phrase(_mate, played_san, mover_is_user)
        if _mtext:
            _mline = ([played_san, _mate.agent_move] + list(_mate.line)
                      if _mate.direction == "received"
                      else [_mate.agent_move] + list(_mate.line))
            return {
                "found": True,
                "direction": _mate.direction,
                "mechanism": "MATE",
                "text": _mtext,
                "move_san": _mate.agent_move,
                "line_san": _mline,
                "arrows": _arrows(fen_before, _mline),
                "candidate_rank": None,
                "eval_gap_cp": 0,
                "payoff_cp": _mate.payoff_cp,
                # The resolver's own finding, for a phrasing layer that wants
                # to say more than _phrase()'s template. `text` above stays
                # the deterministic sentence and remains what ships unless a
                # caller replaces it. Additive: nothing reads this yet except
                # services/why_words.py.
                "punishment": _mate.as_dict(),
            }

    # 1. The punishment we took.
    got = resolve_received(fen_before, played_san, list(pv_after_played or []))
    if got is not None and not _explains_the_loss(got, cp_loss):
        got = None          # names a scrap on a catastrophe; say nothing
    if got is not None:
        text = _phrase(got, played_san, mover_is_user)
        if text and got.mechanism == "FORCES_RETREAT" and \
                not got.returns_home:
            # Name what the retreat COSTS, not just that it happened. A
            # knight chased to g1 is undeveloped, which is the lesson; the
            # bare sentence says only that it was chased. Skipped when
            # `returns_home` already added its own clause, so the two
            # flavours never stack.
            _back = _undeveloped_by_the_retreat(
                fen_before, played_san, list(pv_after_played or []))
            if _back:
                text = (text.rstrip(".") +
                        f", back to {_back['to']} where it started.")
        if text:
            return {
                "found": True,
                "direction": "received",
                "mechanism": got.mechanism,
                "text": text,
                "move_san": got.agent_move,
                # Punishment.line starts AFTER the agent move, and for this
                # direction the agent move is their reply -- which itself
                # comes after ours. From fen_before the board therefore
                # needs the played move and the reply prepended, or the
                # first SAN is illegal and no arrow is drawn at all. That
                # is exactly what shipped: a correct sentence with an
                # empty arrow list.
                "line_san": [played_san, got.agent_move] + list(got.line),
                "arrows": _arrows(
                    fen_before, [played_san, got.agent_move] + list(got.line)),
                "candidate_rank": None,
                "eval_gap_cp": 0,
                "payoff_cp": got.payoff_cp,
                "punishment": got.as_dict(),
            }

    # 2. The opportunity we missed -- but only credit the better move with
    #    material the played move did not already win. Without this guard
    #    we tell the player a move "wins a knight" when theirs did too.
    baseline = max(0, _line_material_gain(
        fen_before, played_san, list(pv_after_played or [])))

    best_cp = None
    for cand in candidates or []:
        if cand.get("eval_cp") is not None:
            best_cp = cand["eval_cp"]
            break

    for rank, cand in enumerate(candidates or [], 1):
        line = [str(x).strip() for x in (cand.get("line_san") or [])
                if str(x or "").strip()]
        san = cand.get("move_san")
        if not line or not san or san == played_san:
            continue
        cp = cand.get("eval_cp")
        gap = (best_cp - cp) if (best_cp is not None and cp is not None) else 0
        if gap > CLOSENESS_CP:
            # candidates are sorted, so everything after this is worse too
            break
        missed = resolve_missed(fen_before, san, line,
                                material_baseline_cp=baseline)
        if missed is None:
            continue
        if not _explains_the_loss(missed, cp_loss):
            continue
        text = _phrase(missed, played_san, mover_is_user)
        if not text:
            continue
        return {
            "found": True,
            "direction": "missed",
            "mechanism": missed.mechanism,
            "text": text,
            "move_san": missed.agent_move,
            # Same frame problem, one move shallower: the better move was
            # never played, so the line runs straight from fen_before.
            "line_san": [missed.agent_move] + list(missed.line),
            "arrows": _arrows(
                fen_before, [missed.agent_move] + list(missed.line)),
            "candidate_rank": rank,
            "eval_gap_cp": gap,
            "payoff_cp": missed.payoff_cp,
            "punishment": missed.as_dict(),
        }

    # 3. Nothing we can stand behind.
    return None


def _undeveloped_by_the_retreat(fen_before: str, played_san: str,
                                line: Sequence[str]) -> Optional[Dict]:
    """A piece chased back to the square it began the GAME on.

    Not the same thing as `Punishment.returns_home`, which this module
    already ships: that one means the piece went back to the square it left
    on THIS move -- `victim_origin` is literally `played.from_square` -- a
    wasted there-and-back. This is a developed piece being undeveloped,
    which is the shape the authored Rousseau caption teaches: "the knight
    often has very few good squares and may even have to retreat to g1".
    The engine's line after c3 is `fxe4 Ng1 d5 Bb3`, so the idea was in the
    PV all along.

    An enrichment of the sentence FORCES_RETREAT already produces, never a
    second mechanism competing with it. The first version of this WAS a
    second mechanism and it could never fire, because punishment_resolver
    answers these at step 1 -- which is the right place for them.
    """
    try:
        import chess as _chess

        from services.move_purposes import piece_driven_home

        b = _chess.Board(fen_before)
        us = b.turn
        b.push(b.parse_san(str(played_san)))
        return piece_driven_home(b, list(line or []), us)
    except Exception:
        return None
