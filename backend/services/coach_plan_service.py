"""The coach plan: costliest problem, the child's reflection, one sign, one rule.

docs/coach_assistant_plan_scope.md, signed by Mohit 2026-11-09 ("signed off, no
start with all detectors"). Every move-level PLAN detector takes part.

What this module owns:
  * ranking a player's problems by RESULTS LOST, not by frequency;
  * choosing the moments the child reflects on;
  * the board facts each tap question is graded against (python-chess, and
    Stockfish for "is this move good" -- computed in the background only);
  * the cause, read from the child's own answers;
  * the warning sign, the rule, and next week's check.

Every fact the child or coach is shown comes from the board or the engine.
Nothing here is written by an AI, and nothing here is a mastery verdict
(concept_mastery_service stays the owner of "learnt").
"""
from __future__ import annotations

import io
from collections import defaultdict
from statistics import median
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import chess
import chess.engine
import chess.pgn

from services import detector_quality as dq

# ---------------------------------------------------------------------------
# what takes part
# ---------------------------------------------------------------------------
# quality id -> (kind, pattern, coach label). Only move-level detectors: the
# three time-management PLAN ids write no per-move record (0 events across 56
# players on 2026-11-09), so there is no moment for a child to reflect on.
PROBLEMS: Dict[str, tuple] = {
    "gap:piece_safety:destination_safety_exact": ("landing", None, "Leaving a piece where it can be taken"),
    "gap:king_safety:ignored_king_attack": ("king_attack", None, "Not answering an attack on the king"),
    "gap:missed_tactic:missed_fork": ("missed_tactic", "fork", "Missing forks"),
    "gap:missed_tactic:missed_pin": ("missed_tactic", "pin", "Missing pins"),
    "gap:missed_tactic:missed_skewer": ("missed_tactic", "skewer", "Missing skewers"),
    "gap:missed_tactic:missed_mate": ("missed_tactic", "mate", "Missing checkmates"),
}

# LOCKED 2026-11-09 (/lock-via-data, 53 players with 20+ analysed games and the
# academy children): a moment costs a result when the position was within a
# pawn of level or better for the child before it (mover-relative eval >= -100)
# and the game was then lost or drawn. -100 vs 0 moved piece safety only from
# 271 to 232 events (no cliff); -100 is the "about level" band the academy
# already uses. Ranking by results lost picked a different top problem than
# frequency for 20 of 53 players, which is why the plan ranks this way.
RESULTS_LOST_FLOOR = -100
LOOKBACK_DAYS = 28
MOMENTS_PER_WEEK = 3
ENGINE_DEPTH = 12
GOOD_LOSS = 80          # within this of the engine's best counts as a good move
ACCEPT_LOSS = 50        # a "find the winning move" answer within this of best

VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5,
         chess.QUEEN: 9, chess.KING: 100}
ORIGIN_FILES = {chess.QUEEN: "d", chess.KING: "e", chess.ROOK: "ah", chess.BISHOP: "cf",
                chess.KNIGHT: "bg"}


def quality_id(obs: Mapping[str, Any]) -> Optional[str]:
    pattern = obs.get("missed_pattern")
    if not pattern:
        return None
    qid = dq.gap_quality_id(str(pattern), obs.get("subtype"))
    if qid not in PROBLEMS or not dq.can_influence(qid, dq.QualitySurface.PLAN):
        return None
    return qid


def mover_eval(cp: Any, color: str) -> Optional[int]:
    """Stored evals are white-relative centipawns."""
    try:
        v = int(cp)
    except (TypeError, ValueError):
        return None
    return v if color == "white" else -v


def costs_result(obs: Mapping[str, Any], game: Mapping[str, Any]) -> bool:
    ev = mover_eval(obs.get("eval_before"), game.get("user_color") or "white")
    return ev is not None and ev >= RESULTS_LOST_FLOOR and game.get("outcome") in ("loss", "draw")


# ---------------------------------------------------------------------------
# ranking
# ---------------------------------------------------------------------------
def rank_problems(games: Mapping[str, Mapping[str, Any]],
                  observations: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Problems ordered by games lost or drawn from level-or-better, then by
    how often they happened. `games` is keyed by game_id and carries
    `outcome` (loss/draw/win) and `user_color`."""
    rows: Dict[str, Dict[str, Any]] = {}
    for o in observations:
        qid = quality_id(o)
        game = games.get(o.get("game_id"))
        if not qid or not game:
            continue
        r = rows.setdefault(qid, {"quality_id": qid, "label": PROBLEMS[qid][2],
                                  "kind": PROBLEMS[qid][0], "pattern": PROBLEMS[qid][1],
                                  "games": set(), "games_lost": set(), "moments": 0,
                                  "evidence": []})
        r["moments"] += 1
        r["games"].add(o["game_id"])
        lost = costs_result(o, game)
        if lost:
            r["games_lost"].add(o["game_id"])
        r["evidence"].append({**dict(o), "_costs_result": lost,
                              "_played_at": game.get("played_at") or ""})
    out = []
    for r in rows.values():
        out.append({**r, "games": len(r["games"]), "games_lost": len(r["games_lost"])})
    out.sort(key=lambda r: (-r["games_lost"], -r["moments"], r["quality_id"]))
    return out


def choose_moments(problem: Mapping[str, Any], n: int = MOMENTS_PER_WEEK) -> List[Dict[str, Any]]:
    """Moments that cost a result first, newest first, one per game."""
    ev = sorted(problem.get("evidence") or [], key=lambda o: o.get("ply") or 0)
    ev = sorted(ev, key=lambda o: o["_played_at"], reverse=True)  # newest first (stable)
    ev = sorted(ev, key=lambda o: not o["_costs_result"])         # result-losing first
    seen, out = set(), []
    for o in ev:
        if o["game_id"] in seen or not o.get("fen_before") or not o.get("move_uci"):
            continue
        seen.add(o["game_id"])
        out.append(o)
        if len(out) >= n:
            break
    return out


def moment_key(obs: Mapping[str, Any]) -> str:
    return f"{obs['game_id']}:{obs.get('ply') or obs.get('move_number') or 0}:{obs['move_uci']}"


# ---------------------------------------------------------------------------
# board facts for one moment
# ---------------------------------------------------------------------------
def _name(board: chess.Board, sq: int) -> str:
    return chess.piece_name(board.piece_type_at(sq))


def _kind(board: chess.Board, frm: int, to: int):
    pt = board.piece_type_at(frm)
    if pt == chess.KNIGHT:
        return "knight", []
    if chess.square_distance(frm, to) <= 1:
        return "near", []
    between = sorted(chess.SquareSet(chess.between(frm, to)),
                     key=lambda s: chess.square_distance(frm, s))
    diag = chess.square_file(frm) != chess.square_file(to) and chess.square_rank(frm) != chess.square_rank(to)
    return ("far_diagonal" if diag else "far_line"), [chess.square_name(s) for s in between]


def _pinner(board: chess.Board, color: bool, sq: int) -> Optional[Dict[str, str]]:
    if not board.is_pinned(color, sq):
        return None
    for s in chess.SquareSet(board.pin(color, sq)):
        if s != sq and board.color_at(s) == (not color):
            return {"sq": chess.square_name(s), "piece": _name(board, s)}
    return None


def develops(color: str, piece_type: int, from_sq: int) -> bool:
    home = 0 if color == "white" else 7
    return (chess.square_rank(from_sq) == home
            and chess.FILE_NAMES[chess.square_file(from_sq)] in ORIGIN_FILES.get(piece_type, ""))


def intents(before: chess.Board, move: chess.Move) -> Dict[str, Any]:
    """What the move did, read off the board: pieces it attacks, own pieces it
    now guards that were under attack, whether it moved a threatened piece,
    whether it left the piece's starting square."""
    me = before.turn
    after = before.copy()
    after.push(move)
    to = move.to_square
    out: List[Dict[str, Any]] = []
    for s in after.attacks(to):
        c = after.color_at(s)
        if c is None or after.piece_type_at(s) == chess.KING:
            continue
        if c != me:
            out.append({"kind": "attack", "sq": chess.square_name(s), "piece": _name(after, s),
                        "already_attacked": bool(before.attackers(me, s)),
                        "guarded_by_them": bool(after.attackers(not me, s))})
            continue
        attackers = list(before.attackers(not me, s))
        if not attackers:
            continue
        guards = [{"sq": chess.square_name(g), "piece": _name(before, g),
                   "pinned": before.is_pinned(me, g), "pinned_by": _pinner(before, me, g)}
                  for g in before.attackers(me, s) if g != move.from_square]
        cheaper = min(VALUE[before.piece_type_at(a)] for a in attackers) < VALUE[before.piece_type_at(s)]
        live = [g for g in guards if not g["pinned"]]
        verdict = "cheaper_attacker" if cheaper else ("needed" if not live else "already_guarded")
        out.append({"kind": "defend", "sq": chess.square_name(s), "piece": _name(before, s),
                    "verdict": verdict,
                    "attackers": [{"sq": chess.square_name(a), "piece": _name(before, a)} for a in attackers],
                    "guards": guards})
    color = "white" if me == chess.WHITE else "black"
    return {"intents": out,
            "escape": bool(before.attackers(not me, move.from_square)),
            "develops": develops(color, before.piece_type_at(move.from_square), move.from_square)}


def _reply(pgn: str, fen_before: str, uci: str) -> Optional[chess.Move]:
    """The opponent's answer in the game, found by replaying the PGN to the
    exact position and move (ply numbering differs between writers)."""
    if not pgn:
        return None
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return None
    if game is None:
        return None
    board = game.board()
    want = fen_before.split(" ")[:4]
    moves = list(game.mainline_moves())
    for i, mv in enumerate(moves):
        if board.fen().split(" ")[:4] == want and mv.uci() == uci:
            return moves[i + 1] if i + 1 < len(moves) else None
        board.push(mv)
    return None


def _score(info, me) -> int:
    return info["score"].pov(me).score(mate_score=100000)


def grade_all_moves(board: chess.Board, engine, depth: int = ENGINE_DEPTH) -> Dict[str, Any]:
    """Every legal move with its loss against the best (mover's point of view)
    and what it does on the board. Background only."""
    me = board.turn
    legal = list(board.legal_moves)
    if not legal:
        return {"best": None, "moves": {}}
    infos = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=len(legal))
    best = max(infos, key=lambda i: _score(i, me))
    best_score = _score(best, me)
    pinned_before = {s for s in chess.SQUARES if board.color_at(s) == me and board.is_pinned(me, s)}
    moves: Dict[str, Any] = {}
    mate_for_best = best["score"].pov(me).is_mate() and (best["score"].pov(me).mate() or 0) > 0
    for i in infos:
        if not i.get("pv"):
            continue
        mv = i["pv"][0]
        after = board.copy()
        san = board.san(mv)
        after.push(mv)
        t = mv.to_square
        moves[mv.uci()] = {
            "san": san,
            "loss": max(0, best_score - _score(i, me)),
            "safe": not after.attackers(not me, t),
            "takers": [{"sq": chess.square_name(a), "piece": _name(after, a), "kind": _kind(after, a, t)[0]}
                       for a in after.attackers(not me, t)],
            "guards": [chess.square_name(s) for s in after.attacks(t) if after.color_at(s) == me],
            "attacks": [chess.square_name(s) for s in after.attacks(t) if after.color_at(s) == (not me)],
            "frees": [{"sq": chess.square_name(s), "piece": _name(after, s),
                       "now_guards": [chess.square_name(x) for x in after.attacks(s)
                                      if after.color_at(x) == me and after.attackers(not me, x)]}
                      for s in pinned_before if after.piece_at(s) and not after.is_pinned(me, s)],
        }
    b = best["pv"][0]
    return {"best": {"uci": b.uci(), "san": board.san(b), "mate": bool(mate_for_best)}, "moves": moves}


def _line_targets(board_after: chess.Board, sq: int, me: bool) -> List[Dict[str, str]]:
    """Two enemy pieces on one line from `sq` (front piece attacked, another
    behind it): the geometry of a pin or a skewer, checked on the board."""
    piece = board_after.piece_at(sq)
    if piece is None or piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return []
    dirs = []
    if piece.piece_type in (chess.BISHOP, chess.QUEEN):
        dirs += [9, 7, -7, -9]
    if piece.piece_type in (chess.ROOK, chess.QUEEN):
        dirs += [8, -8, 1, -1]
    for d in dirs:
        hits, cur = [], sq
        while True:
            nxt = cur + d
            if not 0 <= nxt < 64 or chess.square_distance(cur, nxt) != 1:
                break
            cur = nxt
            p = board_after.piece_at(cur)
            if p is None:
                continue
            if p.color == me:
                break
            hits.append(cur)
            if len(hits) == 2:
                break
        if len(hits) == 2:
            return [{"sq": chess.square_name(h), "piece": _name(board_after, h)} for h in hits]
    return []


def build_moment(obs: Mapping[str, Any], game: Mapping[str, Any], engine) -> Optional[Dict[str, Any]]:
    """All facts for one moment. Returns None when the stored position and
    move do not replay (never show a question the board cannot grade)."""
    qid = quality_id(obs)
    if not qid:
        return None
    kind, pattern, _label = PROBLEMS[qid]
    try:
        before = chess.Board(obs["fen_before"])
        move = chess.Move.from_uci(obs["move_uci"])
    except Exception:
        return None
    if move not in before.legal_moves:
        return None
    me = before.turn
    color = "white" if me == chess.WHITE else "black"
    after = before.copy()
    san = before.san(move)
    after.push(move)
    to = move.to_square

    m: Dict[str, Any] = {
        "key": moment_key(obs), "quality_id": qid, "kind": kind, "pattern": pattern,
        "game_id": obs["game_id"], "date": (game.get("played_at") or "")[:10], "color": color,
        "san": san, "uci": move.uci(), "from": chess.square_name(move.from_square),
        "to": chess.square_name(to), "moved": _name(after, to),
        "fen_before": before.fen(), "fen_after": after.fen(),
        "fen_reply": None, "reply_san": None, "reply_from": None,
        "think_s": obs.get("time_spent_seconds"),
        "costs_result": bool(obs.get("_costs_result")),
        **intents(before, move),
    }
    reply = _reply(game.get("pgn") or "", obs["fen_before"], move.uci())
    if reply is not None and reply in after.legal_moves:
        m["reply_san"] = after.san(reply)
        m["reply_from"] = chess.square_name(reply.from_square)
        r = after.copy()
        r.push(reply)
        m["fen_reply"] = r.fen()
        if reply.to_square == to and after.is_capture(reply):
            m["cost"] = {"lost": m["moved"], "won": chess.piece_name(after.piece_type_at(reply.from_square)),
                         "can_recapture": bool(r.attackers(me, to))}

    graded = grade_all_moves(before, engine)
    best = graded["best"] or {}
    moves = graded["moves"]
    bm = moves.get(best.get("uci") or "", {})
    m["best"] = {"uci": best.get("uci"), "san": best.get("san"), "frees": bm.get("frees", []),
                 "attacks": bm.get("attacks", []), "safe": bm.get("safe", False)}

    if kind == "landing":
        m["test"] = {"kind": "tap_pieces",
                     "answer": [{"sq": chess.square_name(a), "piece": _name(after, a),
                                 "kind": _kind(after, a, to)[0], "path": _kind(after, a, to)[1]}
                                for a in after.attackers(not me, to)]}
        m["practice"] = {"from": m["from"],
                         "moves": {u: v for u, v in moves.items() if u[:2] == m["from"]}}
        if not m["test"]["answer"]:
            return None  # nothing can take it: the detector and board disagree; do not ask
    elif kind == "king_attack":
        king = after.king(me)
        ring = [s for s in chess.SQUARES if king is not None and chess.square_distance(s, king) <= 2
                and after.attackers(not me, s)]
        attackers = sorted({a for s in ring for a in after.attackers(not me, s)})
        m["test"] = {"kind": "tap_pieces", "king": chess.square_name(king) if king is not None else None,
                     "ring": [chess.square_name(s) for s in ring],
                     "answer": [{"sq": chess.square_name(a), "piece": _name(after, a), "kind": "", "path": []}
                                for a in attackers]}
        m["practice"] = {"from": None, "moves": moves}
        if not attackers:
            return None
    else:  # missed tactic: the test is to find the move
        accept = [u for u, v in moves.items() if v["loss"] <= ACCEPT_LOSS]
        explain: Dict[str, Any] = {"targets": [], "mate": bool(best.get("mate"))}
        if best.get("uci"):
            b = chess.Move.from_uci(best["uci"])
            ba = before.copy()
            ba.push(b)
            if pattern == "fork":
                explain["targets"] = [{"sq": chess.square_name(s), "piece": _name(ba, s)}
                                      for s in ba.attacks(b.to_square)
                                      if ba.color_at(s) == (not me) and VALUE[ba.piece_type_at(s)] >= 3]
            elif pattern in ("pin", "skewer"):
                explain["targets"] = _line_targets(ba, b.to_square, me)
        m["test"] = {"kind": "find_move", "accept": accept,
                     "best": {"uci": best.get("uci"), "san": best.get("san")}, "explain": explain}
        m["practice"] = {"from": None, "moves": moves}
        if not accept:
            return None
    return m


# ---------------------------------------------------------------------------
# the cause, from the child's answers
# ---------------------------------------------------------------------------
CAUSE_WORDS = {
    "not_looking": "Not looking: finds it when asked, did not see it in the game. Coach the habit of looking every time.",
    "unknown_pattern": "Does not see this pattern yet: could not find it even when asked. Practise the pattern.",
    "misjudged": "Saw it but misjudged: saw the piece in the game and thought it was fine. Coach counting what the trade costs.",
    "mixed": "Mixed: the answers point different ways. Read the moments.",
    "not_yet": "Not reflected yet.",
}


def cause_of(answer: Mapping[str, Any]) -> Optional[str]:
    seen = answer.get("seen_in_game")
    found = answer.get("found_when_asked")
    if seen == "ok":
        return "misjudged"
    if found is True and seen == "no":
        return "not_looking"
    if found is False and seen in ("no", "unsure"):
        return "unknown_pattern"
    return None


def cause_from(answers: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = defaultdict(int)
    for a in answers:
        c = cause_of(a)
        if c:
            counts[c] += 1
    if not answers:
        kind = "not_yet"
    elif not counts:
        kind = "mixed"
    else:
        top = max(counts.values())
        leaders = [k for k, v in counts.items() if v == top]
        kind = leaders[0] if len(leaders) == 1 and top * 2 > len(answers) else "mixed"
    return {"kind": kind, "counts": dict(counts), "answered": len(answers), "words": CAUSE_WORDS[kind]}


# ---------------------------------------------------------------------------
# the warning sign and the rule (general signs in V1; a child's own sign
# needs the baseline bar in docs/coach_assistant_plan_scope.md, not locked yet)
# ---------------------------------------------------------------------------
SIGNS = {
    "landing": ("The three looks",
                "Before any piece lands, look from that square: pieces close by, knight jumps, and long lines to the edge."),
    "king_attack": ("Who is near my king?",
                    "When his pieces gather near your king, ask what he is threatening there, and answer it before your own plan."),
    "fork": ("Two at once", "Before every move, look for a move that attacks two of his pieces at once."),
    "pin": ("Pieces on one line", "When two of his pieces stand on one line, look for a piece of yours that can hit that line."),
    "skewer": ("Pieces on one line", "When two of his pieces stand on one line, look for a piece of yours that can hit that line."),
    "mate": ("Every check", "Before every move, look at every check you can give."),
}
RULES = {
    "landing": [("three_looks_every_move", "Do the three looks before every move that puts a piece on a new square."),
                ("three_looks_big_pieces", "Do the three looks before every queen and rook move."),
                ("ask_what_can_take", "Before you let go of a piece, ask: what can take it there?")],
    "king_attack": [("count_near_king", "Every move, count his pieces near your king. Two or more: deal with them first."),
                    ("ask_threat", "Before your own plan, ask: what did his last move threaten?")],
    "fork": [("forks_first", "Before every move, look for a fork, for you and for him."),
             ("checks_captures_attacks", "Before every move: checks, captures, then attacks.")],
    "pin": [("lines_first", "Before every move, look along the lines his king and queen stand on."),
            ("checks_captures_attacks", "Before every move: checks, captures, then attacks.")],
    "skewer": [("lines_first", "Before every move, look along the lines his king and queen stand on."),
               ("checks_captures_attacks", "Before every move: checks, captures, then attacks.")],
    "mate": [("every_check", "Before every move, look at every check you can give."),
             ("checks_captures_attacks", "Before every move: checks, captures, then attacks.")],
}


def sign_for(kind: str, pattern: Optional[str]) -> Dict[str, str]:
    title, text = SIGNS[pattern or kind]
    return {"title": title, "text": text, "own": False}


def rule_options(kind: str, pattern: Optional[str]) -> List[Dict[str, str]]:
    return [{"id": i, "text": t} for i, t in RULES[pattern or kind]]


# ---------------------------------------------------------------------------
# next week's check
# ---------------------------------------------------------------------------
def week_check(qid: str, games: Mapping[str, Mapping[str, Any]],
               observations: Iterable[Mapping[str, Any]],
               baseline: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """Did the problem happen in fewer of this week's games, and did the child
    take longer on those moves? Coach-facing; compared with the baseline
    stored when the plan was approved."""
    if not baseline or not games:
        return None
    hit_games, times = set(), []
    for o in observations:
        if quality_id(o) == qid and o.get("game_id") in games:
            hit_games.add(o["game_id"])
            if o.get("time_spent_seconds") is not None:
                times.append(float(o["time_spent_seconds"]))
    n = len(games)
    before_rate = baseline.get("rate")
    now_rate = len(hit_games) / n if n else None
    words = f"This week: in {len(hit_games)} of {n} games"
    if baseline.get("games"):
        words += f", against {baseline['hit_games']} of {baseline['games']} before the plan"
    words += "."
    slower = None
    if times and baseline.get("median_think_s") is not None:
        slower = median(times) > baseline["median_think_s"]
        words += " Took longer on those moves: " + ("yes." if slower else "no.")
    return {"games": n, "hit_games": len(hit_games), "rate": now_rate, "rate_before": before_rate,
            "fewer": (now_rate < before_rate) if (now_rate is not None and before_rate is not None) else None,
            "slower": slower, "words": words}


def baseline_for(problem: Mapping[str, Any], games: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    ev = problem.get("evidence") or []
    hit = {o["game_id"] for o in ev}
    times = [float(o["time_spent_seconds"]) for o in ev if o.get("time_spent_seconds") is not None]
    return {"games": len(games), "hit_games": len(hit),
            "rate": (len(hit) / len(games)) if games else None,
            "median_think_s": median(times) if times else None}


# ---------------------------------------------------------------------------
# what the coach and the child see
# ---------------------------------------------------------------------------
TAKER_KIND_WORDS = {"knight": "a knight jump", "near": "a piece close by",
                    "far_diagonal": "a long diagonal", "far_line": "a long straight line"}


def taker_words(m: Mapping[str, Any]) -> str:
    test = m.get("test") or {}
    if test.get("kind") == "find_move":
        return f"the move was {test['best']['san']}"
    ans = test.get("answer") or []
    if m.get("kind") == "king_attack":
        return "pieces near the king: " + ", ".join(f"{a['piece']} {a['sq']}" for a in ans)
    if not ans:
        return ""
    a = ans[0]
    return f"{a['piece']} on {a['sq']} ({TAKER_KIND_WORDS.get(a['kind'], a['kind'])})"


def answer_card(m: Mapping[str, Any], answer: Mapping[str, Any]) -> Dict[str, Any]:
    wanted = []
    for p in answer.get("picks") or []:
        k = p.get("kind")
        if k == "attack":
            wanted.append(f"attack the {_piece_on(m, p.get('sq'))}")
        elif k == "defend":
            wanted.append(f"guard the {_piece_on(m, p.get('sq'), own=True)}")
        elif k == "develop":
            wanted.append(f"bring the {m.get('moved')} into play")
        elif k == "escape":
            wanted.append(f"move the {m.get('moved')} out of danger")
        elif k == "other":
            wanted.append("something else")
    seen = {"no": "did not see it", "ok": "saw it, thought it was fine", "unsure": "not sure"}
    return {"wanted": wanted or ["not sure"], "taker_words": taker_words(m),
            "found_when_asked": bool(answer.get("found_when_asked")),
            "seen_in_game": seen.get(answer.get("seen_in_game"), "not asked"),
            "cause": cause_of(answer)}


def _piece_on(m: Mapping[str, Any], sq: Optional[str], own: bool = False) -> str:
    for it in m.get("intents") or []:
        if it.get("sq") == sq:
            return f"{it['piece']} on {sq}"
    return f"piece on {sq}" if sq else "piece"


def public_moment(m: Mapping[str, Any]) -> Dict[str, Any]:
    """What the child's page needs. Drops game ids and engine scores it does
    not grade with."""
    keep = ("key", "quality_id", "kind", "pattern", "date", "color", "san", "uci", "from", "to",
            "moved", "fen_before", "fen_after", "fen_reply", "reply_san", "reply_from", "think_s",
            "intents", "escape", "develops", "test", "cost", "practice", "best")
    return {k: m.get(k) for k in keep}
