"""Turn a played game into a teaching script, with the chess computed.

The shape of the script is taken from how a coach actually talks through a
position: the move you were going to play and why it fails, the move that
wins, then the opponent fighting back and getting smarter -- "if they try
this... their better try is this..." -- and the finish.

Every one of those is a search result, not a writing decision:

    the tempting move   = what players at this rating actually play (Maia)
    the only move       = the unique move above the winning threshold
    their tries         = the defender's replies, ranked, each answered
    "and this is forced"= how many of our replies still win

So this module emits a TREE. Rendering it into English is a separate step,
and whatever writes those sentences never chooses a move, a branch or a
verdict. That is the whole reason this content type is safe when our caption
text was not: a claim here is arithmetic, not an opinion.

Positions with at most five men and only kings and pawns are solved
EXHAUSTIVELY, so for those there is no evaluation involved at all.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import chess
import chess.engine

logger = logging.getLogger(__name__)

BUILDER_VERSION = "teaching_script.v1"

# A move "wins" above this, and the position is only teachable if the
# second-best is clearly below it. Two thresholds rather than one, so a
# position where the choice is between +600 and +580 never becomes a lesson
# about an "only move".
WIN_CP = 500
NOT_WIN_CP = 250

DEFAULT_DEPTH = 26
EXACT_MAX_MEN = 5

# Reject a position when this share of the player's own rating band already
# finds the only move. UNLOCKED: chosen to exclude the indefensible, not
# measured against a distribution of band solve-rates. Lock it with
# /lock-via-data before anyone reads anything into the cut-off.
MAX_BAND_SOLVE = 0.90

WIN, DRAW, LOSS = 1, 0, -1


# --------------------------------------------------------------------------
# exact solving, for the positions where no engine opinion is needed
# --------------------------------------------------------------------------

def is_exactly_solvable(board: chess.Board) -> bool:
    pm = board.piece_map()
    if len(pm) > EXACT_MAX_MEN or len(pm) < 3:
        return False
    if {p.piece_type for p in pm.values()} - {chess.KING, chess.PAWN}:
        return False
    return any(p.piece_type == chess.PAWN for p in pm.values())


def solve_exact(board: chess.Board, hero: chess.Color,
                depth: int = 0, memo: Optional[Dict] = None) -> int:
    """WIN / DRAW / LOSS for `hero`, by exhaustive search. No engine."""
    if memo is None:
        memo = {}
    key = (board.board_fen(), board.turn, board.ep_square)
    if key in memo:
        return memo[key]
    if depth > 60:
        return DRAW
    pm = board.piece_map()
    if not any(p.piece_type == chess.PAWN for p in pm.values()):
        return DRAW                      # no pawns left: nobody can mate
    if board.is_stalemate() or board.is_insufficient_material():
        return DRAW
    if board.is_checkmate():
        return LOSS if board.turn == hero else WIN

    memo[key] = DRAW                     # repetition guard: unresolved = draw
    ours = board.turn == hero
    best = LOSS if ours else WIN
    for mv in board.legal_moves:
        board.push(mv)
        if mv.promotion:
            mover = not board.turn
            if not board.attackers(not mover, mv.to_square):
                # a new queen nobody can take decides it
                result = WIN if mover == hero else LOSS
            else:
                result = solve_exact(board, hero, depth + 1, memo)
        else:
            result = solve_exact(board, hero, depth + 1, memo)
        board.pop()
        if ours:
            if result == WIN:
                memo[key] = WIN
                return WIN
            best = max(best, result)
        else:
            if result == LOSS:
                memo[key] = LOSS
                return LOSS
            best = min(best, result)
    memo[key] = best
    return best


# --------------------------------------------------------------------------
# the tree
# --------------------------------------------------------------------------

@dataclass
class MoveVerdict:
    san: str
    uci: str
    verdict: str                 # "wins" | "draws" | "loses"
    detail: str                  # "exact" or a centipawn/mate string
    human_pct: Optional[float] = None     # share of this rating who play it


@dataclass
class DefenderTry:
    san: str
    detail: str
    our_answer: Optional[str]
    our_winning_replies: int
    our_legal_replies: int
    forced: bool
    line: str


@dataclass
class TeachingTree:
    fen: str
    side_to_move: str
    men: int
    proof: str                            # "exhaustive" | "search"
    only_move: Optional[MoveVerdict]
    alternatives: List[MoveVerdict] = field(default_factory=list)
    defender_tries: List[DefenderTry] = field(default_factory=list)
    main_line: str = ""
    bare_race: Optional[Dict[str, str]] = None
    engine: Dict[str, Any] = field(default_factory=dict)
    maia: Dict[str, Any] = field(default_factory=dict)
    triage: Dict[str, Any] = field(default_factory=dict)

    def to_doc(self) -> Dict[str, Any]:
        return asdict(self)


def _score_cp(score: chess.engine.PovScore, pov: chess.Color) -> int:
    return score.pov(pov).score(mate_score=100000) or 0


def _verdict_from_cp(cp: int) -> str:
    if cp >= WIN_CP:
        return "wins"
    if cp <= -WIN_CP:
        return "loses"
    return "draws"


def rank_all_moves(board: chess.Board, engine: chess.engine.SimpleEngine,
                   depth: int = DEFAULT_DEPTH) -> List[Tuple[int, chess.Move, str]]:
    """Every legal move, scored from the mover's point of view."""
    hero = board.turn
    out = []
    for mv in board.legal_moves:
        san = board.san(mv)
        board.push(mv)
        info = engine.analyse(board, chess.engine.Limit(depth=depth))
        cp = _score_cp(info["score"], hero)
        board.pop()
        out.append((cp, mv, san))
    out.sort(key=lambda r: -r[0])
    return out


def find_only_move(board: chess.Board,
                   engine: Optional[chess.engine.SimpleEngine],
                   depth: int = DEFAULT_DEPTH
                   ) -> Tuple[Optional[chess.Move], List[MoveVerdict], str]:
    """The unique winning move, if there is exactly one.

    Returns (move, every move's verdict, proof kind). `move` is None when the
    position is not an only-move position -- either nothing wins, or more than
    one thing does, or the gap to the second best is too small to teach.
    """
    hero = board.turn

    if is_exactly_solvable(board):
        if solve_exact(board.copy(), hero) != WIN:
            return None, [], "exhaustive"
        verdicts, winners = [], []
        for mv in board.legal_moves:
            san = board.san(mv)
            board.push(mv)
            r = solve_exact(board.copy(), hero)
            board.pop()
            name = {WIN: "wins", DRAW: "draws", LOSS: "loses"}[r]
            verdicts.append(MoveVerdict(san, mv.uci(), name, "exact"))
            if r == WIN:
                winners.append(mv)
        if len(winners) != 1:
            return None, verdicts, "exhaustive"
        return winners[0], verdicts, "exhaustive"

    if engine is None:
        return None, [], "search"

    # Cheap rejection first. Scoring every legal move is 20-40 engine calls,
    # and almost every position we look at is not an only-move position, so
    # paying that up front made the builder unusable -- minutes per game.
    #
    # This probe is NOT exact: a shallow search can under-rate the winning
    # move, so a position it rejects might have been teachable. It can only
    # ever lose us lessons, never admit a bad one, because everything that
    # passes still goes through the full-depth ranking below, which makes the
    # actual decision. Generous margins keep the false-negative rate low;
    # yield matters less here than never shipping a wrong "only move".
    try:
        probe = engine.analyse(board, chess.engine.Limit(depth=min(14, depth)),
                               multipv=2)
    except Exception:
        probe = []
    if probe:
        top = _score_cp(probe[0]["score"], hero)
        if top < WIN_CP // 2:
            return None, [], "search"
        if len(probe) > 1 and _score_cp(probe[1]["score"], hero) > WIN_CP:
            return None, [], "search"

    ranked = rank_all_moves(board, engine, depth)
    if not ranked:
        return None, [], "search"
    verdicts = [
        MoveVerdict(san, mv.uci(), _verdict_from_cp(cp), f"{cp:+d}cp")
        for cp, mv, san in ranked
    ]
    best_cp, best_mv, _ = ranked[0]
    if best_cp < WIN_CP:
        return None, verdicts, "search"
    if len(ranked) > 1 and ranked[1][0] > NOT_WIN_CP:
        # more than one move keeps it: not an only-move lesson
        return None, verdicts, "search"
    return best_mv, verdicts, "search"


def _bare_race(board: chess.Board,
               engine: Optional[chess.engine.SimpleEngine]
               ) -> Optional[Dict[str, str]]:
    """Strip to kings and the mover's passed pawn, to show the pure race.

    This is what lets a script say "count first -- their king is in time"
    and prove it, rather than assert it.
    """
    pm = board.piece_map()
    mover = board.turn
    # ONLY for positions that already are king-and-pawn. Stripping a rook off
    # the board produces a different position with a different answer, and a
    # script that then says "count -- the king is in time" is stating, as a
    # fact about the game in front of the student, the result of a position
    # that never existed. Caught on the first real row the generator wrote:
    # 1k6/8/1p6/7P/8/6P1/1r1R3K/8 is a ROOK endgame and the beat fired anyway.
    if {p.piece_type for p in pm.values()} - {chess.KING, chess.PAWN}:
        return None
    pawns = [(sq, p) for sq, p in pm.items()
             if p.piece_type == chess.PAWN and p.color == mover]
    if len(pawns) != 1:
        return None
    stripped = chess.Board(None)
    stripped.clear()
    for sq, p in pm.items():
        if p.piece_type == chess.KING or (sq, p) in pawns:
            stripped.set_piece_at(sq, p)
    stripped.turn = mover
    if not stripped.is_valid():
        return None
    if is_exactly_solvable(stripped):
        r = solve_exact(stripped.copy(), mover)
        return {"fen": stripped.fen(),
                "result": {WIN: "the pawn queens", DRAW: "the king is in time",
                           LOSS: "the king is in time"}[r],
                "proof": "exhaustive"}
    if engine is None:
        return None
    info = engine.analyse(stripped, chess.engine.Limit(depth=30))
    cp = _score_cp(info["score"], mover)
    pv = info.get("pv", [])[:10]
    return {"fen": stripped.fen(),
            "result": "the pawn queens" if cp >= WIN_CP else "the king is in time",
            "line": stripped.variation_san(pv) if pv else "",
            "proof": "search"}


def build_tree(fen: str,
               engine: Optional[chess.engine.SimpleEngine],
               depth: int = DEFAULT_DEPTH,
               human_probs: Optional[Dict[str, float]] = None,
               maia_meta: Optional[Dict[str, Any]] = None,
               max_band_solve: float = MAX_BAND_SOLVE,
               candidate: Optional[Dict[str, Any]] = None
               ) -> Optional[TeachingTree]:
    """The whole tree for one position, or None if it is not teachable."""
    board = chess.Board(fen)
    only, verdicts, proof = find_only_move(board, engine, depth)
    if only is None:
        return None

    if human_probs:
        for v in verdicts:
            p = human_probs.get(v.uci)
            if p is not None:
                v.human_pct = round(100.0 * p, 1)

        # A position this rating already solves is not a lesson. The first
        # row the generator ever wrote was one where Maia put 99.7% of
        # 1180-rated players on the only move -- technically an only-move
        # position, pedagogically worthless, and it produced the line "About
        # 0 in 100 players rated 1180 play it here" about the alternative.
        #
        # The cut-off below is NOT locked against a measured distribution
        # yet, so it is deliberately loose: it rejects the indefensible
        # rather than pretending to know where "too easy" begins. See the
        # open question in docs/guided_concept_curriculum_scope.md.
        solved_by = next(
            (v.human_pct for v in verdicts if v.uci == only.uci()), None)
        if solved_by is not None and solved_by >= max_band_solve * 100.0:
            return None

    only_v = next(v for v in verdicts if v.uci == only.uci())

    # Sort the mistake BEFORE paying for the defender tries and the main
    # line. An execution failure needs no lesson, so building one would be
    # both wasted engine time and the wrong product: a drill for something
    # the player already knew.
    verdict: Dict[str, Any] = {}
    if candidate is not None:
        verdict = triage(candidate, band_solve_pct=only_v.human_pct)
        if verdict["verdict"] == "execution_failure":
            return TeachingTree(
                fen=fen,
                side_to_move="white" if board.turn == chess.WHITE else "black",
                men=len(board.piece_map()),
                proof="exhaustive" if proof == "exhaustive" else "search",
                only_move=only_v,
                alternatives=[v for v in verdicts if v.uci != only.uci()][:4],
                engine={"depth": depth} if proof == "search" else {"exhaustive": True},
                maia=maia_meta or {},
                triage=verdict,
            )
    alts = [v for v in verdicts if v.uci != only.uci()]
    # order the alternatives the way the student would reach for them, so the
    # script answers the likely mistake first rather than the engine's second
    # choice. Falls back to the search order when there is no human model.
    alts.sort(key=lambda v: -(v.human_pct if v.human_pct is not None else 0.0))

    tree = TeachingTree(
        fen=fen,
        side_to_move="white" if board.turn == chess.WHITE else "black",
        men=len(board.piece_map()),
        proof="exhaustive" if proof == "exhaustive" else "search",
        only_move=only_v,
        alternatives=alts[:6],
        bare_race=_bare_race(board, engine),
        triage=verdict,
        engine={"depth": depth} if proof == "search" else {"exhaustive": True},
        maia=maia_meta or {},
    )

    # the defender fights back
    board.push(only)
    hero = not board.turn
    tries: List[Tuple[int, chess.Move, str]] = []
    for mv in board.legal_moves:
        san = board.san(mv)
        if engine is None:
            tries.append((0, mv, san))
            continue
        board.push(mv)
        info = engine.analyse(board, chess.engine.Limit(depth=depth))
        tries.append((_score_cp(info["score"], hero), mv, san))
        board.pop()
    tries.sort(key=lambda r: r[0])          # their best defence first

    for cp, mv, san in tries[:5]:
        board.push(mv)
        replies, winning = [], []
        for rm in board.legal_moves:
            rsan = board.san(rm)
            if engine is None:
                continue
            board.push(rm)
            rinfo = engine.analyse(board, chess.engine.Limit(depth=max(18, depth - 6)))
            rcp = _score_cp(rinfo["score"], hero)
            board.pop()
            replies.append((rcp, rsan))
            if rcp >= WIN_CP:
                winning.append((rcp, rsan))
        line, pv_first = "", None
        if engine is not None:
            info = engine.analyse(board, chess.engine.Limit(depth=depth))
            pv = info.get("pv", [])[:10]
            if pv:
                line = board.variation_san(pv)
                pv_first = board.san(pv[0])
        board.pop()
        winning.sort(reverse=True)
        # Name the move the line actually plays. Taking the highest-scoring
        # reply instead produced scripts that said "you answer a5" above a
        # line beginning 2...Nxg5+ -- both winning, but a coach reading a
        # recommendation that contradicts the variation under it stops
        # trusting the whole script, and they would be right to.
        answer = None
        if winning:
            names = {w[1] for w in winning}
            answer = pv_first if pv_first in names else winning[0][1]
        tree.defender_tries.append(DefenderTry(
            san=san,
            detail=f"{cp:+d}cp" if engine is not None else "",
            our_answer=answer,
            our_winning_replies=len(winning),
            our_legal_replies=len(replies),
            forced=len(winning) == 1,
            line=line,
        ))
    board.pop()

    if engine is not None:
        mb = chess.Board(fen)
        moves: List[chess.Move] = []
        for _ in range(16):
            info = engine.analyse(mb, chess.engine.Limit(depth=depth))
            pv = info.get("pv", [])
            if not pv:
                break
            moves.append(pv[0])
            mb.push(pv[0])
            if mb.is_game_over():
                break
        # Numbered, because an unnumbered run of sixteen plies is unreadable
        # and a coach has to be able to follow it on a board.
        tree.main_line = chess.Board(fen).variation_san(moves) if moves else ""

    return tree


# --------------------------------------------------------------------------
# finding positions worth teaching, inside a game we already analysed
# --------------------------------------------------------------------------

def render_script(tree: TeachingTree,
                  rating: Optional[int] = None) -> List[Dict[str, str]]:
    """Turn the tree into the coach's lines, deterministically.

    Shape taken from how a coach actually talks it through: the tempting move
    dismissed in a sentence, then the whole of the time spent on the win with
    the defender fighting back and getting smarter. Not a table of refutations
    -- that reads like a scoreboard and teaches nothing.

    No model is involved. Every sentence below is assembled from a field of
    the tree, so nothing here can assert a chess fact the search did not
    produce. A model may later rewrite these lines for tone; if it does, it
    gets the tree too, and it still never chooses a move or a verdict.
    """
    out: List[Dict[str, str]] = []
    if tree.only_move is None:
        return out

    out.append({"beat": "hook",
                "text": f"You are {tree.side_to_move.title()}, and you are "
                        f"winning. There is exactly one move that keeps it."})

    # The tempting move, named by what this rating actually plays. If no
    # alternative reaches a real share, there is no tempting move and the beat
    # is dropped -- it used to fall back to the top alternative regardless and
    # produce "About 0 in 100 players rated 1180 play it here", which is both
    # absurd and a sign the position was not worth teaching in the first place.
    tempting = next((a for a in tree.alternatives
                     if a.human_pct is not None and a.human_pct >= 5.0), None)
    if tempting is None and all(a.human_pct is None for a in tree.alternatives):
        # No human model at all: fall back to the engine's runner-up, and say
        # nothing about how many people play it, because we do not know.
        tempting = tree.alternatives[0] if tree.alternatives else None
    if tempting is not None:
        who = ""
        if tempting.human_pct is not None:
            who = (f" About {tempting.human_pct:.0f} in 100 players"
                   f"{f' rated {rating}' if rating else ''} play it here.")
        out.append({"beat": "tempting",
                    "text": f"The move that will occur to you is "
                            f"{tempting.san}.{who} It only {tempting.verdict}."})

    if tree.bare_race:
        out.append({"beat": "count",
                    "text": "Strip the board down to the king and the running "
                            f"pawn and count: {tree.bare_race['result']}."
                            + (f" {tree.bare_race.get('line', '')}".rstrip()
                               if tree.bare_race.get("line") else "")})

    out.append({"beat": "the move",
                "text": f"The move is {tree.only_move.san}. It is the only move "
                        f"on the board that wins"
                        + (" -- proved by searching it to the end."
                           if tree.proof == "exhaustive"
                           else f" ({tree.only_move.detail}).")})

    for t in tree.defender_tries:
        sharp = ""
        if t.forced:
            sharp = (f" Be careful here: {t.our_answer} is the only reply of "
                     f"{t.our_legal_replies} that still wins.")
        elif t.our_answer:
            sharp = f" You answer {t.our_answer}."
        out.append({"beat": "their try",
                    "text": f"If they try {t.san}.{sharp}"
                            + (f" {t.line}" if t.line else "")})

    if tree.main_line:
        out.append({"beat": "finish", "text": f"The win: {tree.main_line}"})

    return out


_CLK = re.compile(r"\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]")


def _clock_seconds(comment: Optional[str]) -> Optional[float]:
    """Seconds left on the mover's clock after this move, from [%clk h:mm:ss]."""
    if not comment:
        return None
    m = _CLK.search(comment)
    if not m:
        return None
    h, mm, ss = m.groups()
    return int(h) * 3600 + int(mm) * 60 + float(ss)


def _increment_seconds(time_control: Optional[str]) -> float:
    """The increment from a PGN TimeControl like "900+10"."""
    if not time_control or "+" not in str(time_control):
        return 0.0
    try:
        return float(str(time_control).split("+", 1)[1])
    except (TypeError, ValueError):
        return 0.0


# --------------------------------------------------------------------------
# the triage: did they not know it, or did they know it and miss it?
# --------------------------------------------------------------------------

# Mohit, 2026-11-26: "Even best players like Magnus can sometimes let a piece
# undefended... human coaches don't give you exercise when you blunder
# something from eyesight, because they know you know this."
#
# A lesson handed to someone for something they already know is the fastest
# way to lose them. So every mistake is sorted first, and only a genuine
# knowledge gap earns a lesson. The rest become behaviour findings: the clock,
# the rush, where their attention was.
#
# BOTH THRESHOLDS BELOW ARE UNLOCKED. They are set to catch the obvious cases,
# not because a distribution was measured. Lock them with /lock-via-data
# before anyone reads meaning into the exact numbers.
# Measured 2026-11-26 over 12,337 think times from 203 real games: median
# 3.9s, p10 0.0s, p90 20.2s, and 42% of ALL moves come in at 3s or under. So
# a flat 3-second rule would call nearly half of every game rushed, which is
# useless. What matters is a move played much faster than THIS player thinks
# on THIS day, so the test is relative to their own median for the game, with
# an absolute floor for moves that were plainly instant.
RUSHED_SECONDS = 1.5          # instant by any standard
RUSHED_FRACTION = 0.33        # ...or a third of their own pace this game
LOW_CLOCK_SECONDS = 60.0      # at this little remaining, seeing it is the problem


def triage(candidate: Dict[str, Any],
           band_solve_pct: Optional[float] = None,
           rushed_seconds: float = RUSHED_SECONDS,
           low_clock_seconds: float = LOW_CLOCK_SECONDS,
           rushed_fraction: float = RUSHED_FRACTION) -> Dict[str, Any]:
    """Knowledge gap, or execution failure? Returns a verdict and its reason.

    Only "knowledge_gap" earns a lesson. "execution_failure" earns a sentence
    about the circumstance instead, which is what a human coach would say.
    "unclear" means we have no evidence either way -- treated as teachable,
    because withholding a lesson on no evidence helps nobody.
    """
    think = candidate.get("think_seconds")
    clock = candidate.get("clock_seconds")

    pace = candidate.get("game_median_think")
    if think is not None:
        bar = rushed_seconds
        if pace:
            bar = max(rushed_seconds, rushed_fraction * pace)
        if think <= bar:
            detail = f"played in {think:.0f}s"
            if pace:
                detail += f", against {pace:.0f}s typical for them this game"
            return {"verdict": "execution_failure", "cause": "rushed",
                    "detail": detail, "think_seconds": think,
                    "clock_seconds": clock, "pace_seconds": pace}

    if clock is not None and clock <= low_clock_seconds:
        return {"verdict": "execution_failure", "cause": "time_pressure",
                "detail": f"{clock:.0f}s left on the clock",
                "think_seconds": think, "clock_seconds": clock}

    if band_solve_pct is not None and band_solve_pct >= 75.0:
        # Most players at their own rating find this move. Being told the
        # concept is being told something they demonstrably already have.
        return {"verdict": "execution_failure", "cause": "known_by_their_level",
                "detail": f"{band_solve_pct:.0f}% of their rating find it",
                "think_seconds": think, "clock_seconds": clock}

    if think is None and clock is None and band_solve_pct is None:
        return {"verdict": "unclear", "cause": "no_evidence", "detail": "",
                "think_seconds": None, "clock_seconds": None}

    return {"verdict": "knowledge_gap", "cause": "had_time_and_missed_it",
            "detail": (f"spent {think:.0f}s with {clock:.0f}s left"
                       if think is not None and clock is not None else ""),
            "think_seconds": think, "clock_seconds": clock}


def candidate_positions_from_pgn(pgn: str,
                                 user_color: Optional[str] = None,
                                 max_men: int = 7) -> List[Dict[str, Any]]:
    """Positions in one game that might carry a lesson, read from its PGN.

    Deliberately NOT from game_analyses. Those documents hold a few hundred
    kilobytes of move evaluations each, and pulling them only to discover the
    game never reached an endgame cost about 2.9 seconds per game over the
    tunnel -- with roughly one game in thirteen having any position small
    enough to be worth looking at. The PGN is about two kilobytes, replays
    locally, and already says what the player actually played.

    Ordered so the best teaching material comes first: a position where it
    was the player's own move is worth more than one of the opponent's.
    """
    import io
    import chess.pgn as pgn_mod

    try:
        game = pgn_mod.read_game(io.StringIO(pgn or ""))
    except Exception:
        return []
    if game is None:
        return []

    hero: Optional[chess.Color] = None
    if user_color:
        hero = chess.WHITE if str(user_color).lower().startswith("w") else chess.BLACK

    increment = _increment_seconds(game.headers.get("TimeControl"))
    board = game.board()
    node = game
    last_clock: Dict[bool, Optional[float]] = {True: None, False: None}
    out: List[Dict[str, Any]] = []
    ply = 0
    for node in game.mainline():
        move = node.move
        if move is None:
            continue
        ply += 1
        mover = board.turn
        clock = _clock_seconds(node.comment)
        # Think time is the player's own clock before minus after, plus the
        # increment they just earned. It is what tells a rushed move from a
        # considered one, and it is the single strongest signal that a player
        # knew better and simply had no time to see it.
        think = None
        if clock is not None and last_clock[mover] is not None:
            think = max(0.0, last_clock[mover] - clock + increment)
        if len(board.piece_map()) <= max_men:
            out.append({
                "fen": board.fen(),
                "ply": ply,
                "move_number": board.fullmove_number,
                "played": board.san(move),
                "is_opponent_move": hero is not None and mover != hero,
                "clock_seconds": clock,
                "think_seconds": round(think, 1) if think is not None else None,
            })
        if clock is not None:
            last_clock[mover] = clock
        try:
            board.push(move)
        except Exception:
            break

    # Each side's own pace for THIS game, so a rushed move is judged against
    # how that player was actually thinking rather than a global constant.
    import statistics as _stats
    for side in (False, True):
        mine = [c["think_seconds"] for c in out
                if c["is_opponent_move"] is side and c["think_seconds"] is not None]
        pace = _stats.median(mine) if len(mine) >= 4 else None
        for c in out:
            if c["is_opponent_move"] is side:
                c["game_median_think"] = round(pace, 1) if pace else None

    # The endgame is where the small positions are, and the sharpest moment
    # is usually the first time the position got small, not the last.
    out.sort(key=lambda c: (c["is_opponent_move"], c["ply"]))
    return out
